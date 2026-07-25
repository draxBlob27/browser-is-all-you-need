"""Create and verify the 30-root Reflow and layout expansion family."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_reflow_layout_expansion_cases import CASES, LayoutCase

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/text-grid-layout/reflow-layout"
)
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_REFLOW_LAYOUT_EXPANSION_CURRICULUM.md"
)
GENERATOR_PATH = Path(
    "src/w8_biayn/integrations/moonlight_reflow_layout_expansion_aider_tasks.py"
)
CASE_PATH = Path(
    "src/w8_biayn/integrations/moonlight_reflow_layout_expansion_cases.py"
)
TEST_PATH = Path("tests/test_moonlight_reflow_layout_expansion_aider_tasks.py")
WRAPPER_PATH = Path(
    "examples/slime/moonlight_cpp_perf/prepare_reflow_layout_expansion_aider_tasks.sh"
)
FAMILY_ID = "aider-expansion-v1-reflow-layout-v1"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
HOLDOUT_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square",
        "diamond", "dnd-character", "gigasecond", "grade-school",
        "kindergarten-garden", "knapsack", "linked-list", "meetup",
        "parallel-letter-frequency", "perfect-numbers", "phone-number",
        "queen-attack", "robot-name", "space-age", "spiral-matrix", "sublist",
        "yacht", "zebra-puzzle",
    }
)
HARD_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
CONTROL_NAMES = (
    "domain-identifier-renamed",
    "constants-policy-only",
    "opposite-end-selection",
)
CONTROL_BASE_ID = "reflow-alternating-justification"

CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(reflow_layout_expansion LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
enable_testing()
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
'''


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    if not root.is_dir():
        return "not_available"
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _inventory(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    if not root.is_dir():
        return records
    for config in sorted(root.rglob(".meta/config.json")):
        if ".state" in config.parts:
            continue
        task_root = config.parent.parent
        tree_hash = config_hash = None
        for _attempt in range(3):
            try:
                tree_hash = _tree_hash(task_root)
                config_hash = _file_hash(config)
                break
            except FileNotFoundError:
                continue
        if tree_hash is None or config_hash is None:
            _fail("inventory_unstable", f"foreign root changed while hashing: {task_root}")
        records.append(
            {
                "task_id": task_root.name,
                "relative_root": task_root.relative_to(root).as_posix(),
                "tree_hash": tree_hash,
                "config_hash": config_hash,
            }
        )
    return records


def _validate_output(out: Path) -> None:
    resolved = out.resolve()
    expansion = EXPANSION_ROOT.resolve()
    if resolved == expansion or expansion not in resolved.parents:
        _fail("unsafe_path", f"output must be a family below {EXPANSION_ROOT}: {out}")
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("unsafe_path", f"existing tree is read-only: {out}")
    cursor = out
    while cursor != EXPANSION_ROOT.parent and cursor != cursor.parent:
        if cursor.is_symlink():
            _fail("unsafe_path", f"symlink component: {cursor}")
        cursor = cursor.parent


def _negative_source(case: LayoutCase) -> str:
    if case.reference.count(case.negative_old) != 1:
        _fail("invariant_not_enforced", f"mutation marker count for {case.task_id}")
    changed = case.reference.replace(case.negative_old, case.negative_new, 1)
    if changed == case.reference:
        _fail("invariant_not_enforced", f"negative is a no-op: {case.task_id}")
    return changed


def _control_transform(files: dict[str, str], name: str) -> dict[str, str]:
    changed = dict(files)
    if name == "domain-identifier-renamed":
        substitutions = (
            ("CadenceLayout", "RhythmLayout"),
            ("justify_cadence", "space_rhythm"),
            ("Cadence", "Rhythm"),
            ("cadence", "rhythm"),
        )
        for path, content in tuple(changed.items()):
            if path.endswith((".md", ".h", ".cpp", ".json", ".toml")):
                for old, new in substitutions:
                    content = content.replace(old, new)
                changed[path] = content
    elif name == "constants-policy-only":
        for path, content in tuple(changed.items()):
            changed[path] = content.replace("3..40", "3..36").replace(
                "width>40U", "width>36U"
            )
    elif name == "opposite-end-selection":
        for path, content in tuple(changed.items()):
            content = content.replace(
                "row%2U==0U?g<extra:g>=gaps-extra",
                "row%2U==0U?g>=gaps-extra:g<extra",
            )
            content = content.replace(
                'std::vector<std::string>{"a  b c","d e  f","g"}',
                'std::vector<std::string>{"a b  c","d  e f","g"}',
            )
            content = content.replace(
                "On nonfinal line zero distribute remainder spaces left-to-right, "
                "on line one right-to-left",
                "On nonfinal line zero distribute remainder spaces right-to-left, "
                "on line one left-to-right",
            )
            changed[path] = content
    else:
        raise ValueError(name)
    return changed


def _render_files(case: LayoutCase, *, control: str | None = None) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.title,
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "benchmark_separation": (
            "All official Aider Polyglot C++ roots are permanent holdouts; "
            "no holdout assets were used."
        ),
        "count_plan_cell": (
            "text normalization, reflow, justification, and whitespace-sensitive "
            "layout / 30"
        ),
        "curriculum_document": str(CURRICULUM),
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "mechanism": case.mechanism,
        "origin": "repository-authored clean-room expansion",
        "status": "local task artifact; not admitted SFT data",
        "task_id": case.task_id,
        "version": 1,
    }
    files = {
        ".docs/introduction.md": (
            f"# {case.title}\n\nA clean-room C++17 task for {case.mechanism}.\n"
        ),
        ".docs/instructions.md": (
            f"# Instructions\n\nImplement `{case.title}`.\n\n"
            f"Public API: `{case.api}`. {case.instructions}\n\n"
            f"Required mechanism: {case.mechanism}. Implement it directly; do not "
            "delegate to formatting, locale, regex, Markdown, terminal, Unicode, "
            "or other layout libraries; do not use precomputed answers, files, "
            "networking, threads, or randomness.\n"
        ),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            '[visible]\ndescription="deterministic public behavior"\n'
            '[hidden]\ndescription="empty, invalid, boundary, ordering, and tie behavior"\n'
            f'[negative]\ndescription="{case.negative_reason}"\n'
        ),
        f"{case.task_id}.h": case.header,
        f"{case.task_id}.cpp": case.starter,
        ".meta/example.h": case.header,
        ".meta/example.cpp": case.reference,
        ".meta/negative_false_substitute.cpp": _negative_source(case),
        "task_visible_test.cpp": case.visible_test,
        ".meta/task_hidden_test.cpp": case.hidden_test,
        "CMakeLists.txt": CMAKE,
    }
    rendered = task_named_files(Path(case.task_id), files)
    if control is not None:
        rendered = _control_transform(rendered, control)
    return rendered


def _write_root(root: Path, case: LayoutCase, force: bool, *, control: str | None = None) -> None:
    files = _render_files(case, control=control)
    for relative, content in files.items():
        _write(root / relative, content, force)


def _freeze_inventory(out: Path, force: bool) -> dict[str, object]:
    relative_family = out.resolve().relative_to(EXPANSION_ROOT.resolve()).as_posix()
    expansion_records = [
        record
        for record in _inventory(EXPANSION_ROOT)
        if not record["relative_root"].startswith(relative_family + "/")
    ]
    inventories = {
        "legacy": _inventory(LEGACY_ROOT),
        "reverify": _inventory(REVERIFY_ROOT),
        "expansion_before": expansion_records,
    }
    payload: dict[str, object] = {
        "schema_version": "reflow-layout-source-inventory-v1",
        "roots": {},
    }
    for name, records in inventories.items():
        serialized = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
        payload["roots"][name] = {
            "count": len(records),
            "sha256": _sha(serialized),
            "records": records,
        }
    _write(out / ".state/source-inventory.json", json.dumps(payload, indent=2, sort_keys=True) + "\n", force)
    return payload


def _remedy_spec(case: LayoutCase) -> str:
    return f'''## Identity

Task ID `{case.task_id}`; task-spec revision 1; family `{FAMILY_ID}`;
disposition `new-root`; source inventory `.state/source-inventory.json`;
license `repository-authored clean-room`; generator `{GENERATOR_PATH}`;
benchmark screen pending until creator preflight.

## Objective

Implement and expose {case.mechanism}.

## Public API

C++17 API `{case.api}`. Editable order is `{case.task_id}.h`, then
`{case.task_id}.cpp`. Callers own inputs and returned values.

## Behavior table

{case.instructions} Invalid input is atomic. Duplicate, absent, empty,
ordering, tie, boundary, and bounded-overflow behavior are part of this public
contract and are exercised by the visible or private deterministic test.

## Implementation invariant

The substantive mechanism is `{case.mechanism}`. Forbidden substitutes are
`{case.negative_reason}`, a renamed sibling contract, a constants-only policy,
an endpoint-only variant, generic formatter delegation, regex/locale/Markdown
layout delegation, and precomputed visible examples.

## Starter and reference

The task-named header declares the complete API; the task-named source is a
coherent incomplete starter. `.meta/example.h` and `.meta/example.cpp` are
independent complete replacements and import no benchmark or sibling root.

## Tests

`task_visible_test.cpp` covers the public example. The private test covers
empty/invalid/boundary/tie behavior. The compiling false source mutates exactly
one mechanism rule: {case.negative_reason}; both test executables reject it.

## Files and metadata

Only the task-named header/source are editable. Tests, examples, provenance,
CMake, receipts, controls, and this specification remain private.

## Build/oracle

Strict C++17, `Unix Makefiles`, two positive normal tests and two equal fresh
ASan/UBSan tests in network-disabled `{SANITY_IMAGE}`. Receipt fields bind the
owner, case inventory, curriculum, focused tests, exact tree/archive/mount,
compiler path/version/hash, CMake version, commands, and outcomes.

## Family/contamination

Compare all 435 retained pairs conjunctively in the seven hard dimensions,
the three coherent clone controls, all roots in both existing generated trees,
and all 26 official C++ holdouts.

## Optional dataset handoff

`not_requested`.

## Acceptance

Owner regeneration, focused tests, prompt/role/reference validation, unique
prompt/reference hashes, all-pairs diversity, clone rejection, cross-tree and
holdout screens, equal normal/sanitizer passes, and compiled/executed rejection
of this false source must all pass. Stable failures include `unsafe_path`,
`duplicate_task`, `duplicate_family`, `benchmark_content_overlap`,
`prompt_contract_incomplete`, `target_reference_mismatch`,
`negative_fixture_not_rejected`, `grader_mount_hash_mismatch`, and
`sanitizer_test_count_mismatch`.
'''


def _write_controls(out: Path, force: bool) -> None:
    case = next(item for item in CASES if item.task_id == CONTROL_BASE_ID)
    base_files = _render_files(case)
    controls: dict[str, object] = {}
    for name in CONTROL_NAMES:
        root = out / ".state/adversarial-clone-controls" / name
        _write_root(root, case, force, control=name)
        current = _render_files(case, control=name)
        changed = sorted(path for path in current if current[path] != base_files[path])
        if not changed:
            _fail("duplicate_family", f"control is a no-op: {name}")
        if name == "opposite-end-selection" and set(changed) != {
            ".docs/instructions.md",
            ".meta/example.cpp",
            "task_visible_test.cpp",
        }:
            _fail("incoherent_clone_control", f"{name} changed {changed}")
        controls[name] = {
            "changed_files": changed,
            "tree_hash": _tree_hash(root, include_state=True),
        }
    _write(
        out / ".state/adversarial-clone-controls/manifest.json",
        json.dumps(
            {
                "schema_version": "reflow-layout-clone-controls-v1",
                "base_task_id": CONTROL_BASE_ID,
                "controls": controls,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )


def _write_remedy_records(out: Path, force: bool) -> None:
    audit = out / ".state/audits/initial-cycle-02/audit-report.json"
    if not audit.is_file():
        _fail("missing_audit_evidence", str(audit))
    remedies = {
        "RFL-AUD-001": {
            "affected_roots": [case.task_id for case in CASES if case.task_id != "reflow-stream-fragments"],
            "actions": [
                "generate warning-clean exact editable starters",
                "compile every starter in normal and fresh sanitizer modes",
                "persist per-root starter outcomes",
            ],
        },
        "RFL-AUD-002": {
            "affected_roots": [
                "layout-footnote-pages", "layout-template-slots",
                "reflow-markdown-blocks", "reflow-punctuation-glue",
                "reflow-stream-fragments",
            ],
            "actions": [
                "repair all five reference contract counterexamples",
                "add every counterexample to the hidden deterministic oracle",
            ],
        },
        "RFL-AUD-003": {
            "affected_roots": ["all-30-roots"],
            "actions": [
                "separate state-algorithm and control-flow material extractors",
                "derive all seven dimensions independently in focused tests",
            ],
        },
        "RFL-AUD-004": {
            "affected_roots": [CONTROL_BASE_ID],
            "actions": [
                "transform opposite-end public contract, reference, and oracle coherently",
                "assert the exact coherent changed-file set",
            ],
        },
        "RFL-AUD-005": {
            "affected_roots": ["all-30-roots"],
            "actions": [
                "persist a per-subject per-mode Docker execution ledger",
                "bind command, policy, input, and result hashes directly in the receipt",
            ],
        },
    }
    for finding_id, remedy in remedies.items():
        payload = {
            "schema_version": "aider-task-family-remedy-v1",
            "finding_id": finding_id,
            "source_audit": audit.relative_to(out).as_posix(),
            "source_audit_hash": _file_hash(audit),
            "family_id": FAMILY_ID,
            "disposition": "repair-in-place-owned-new-roots",
            "status": "remediated_pending_regeneration_and_fresh_audit",
            "artifact_family_tree_hash": _tree_hash(out),
            **remedy,
        }
        _write(
            out / ".state/remedy" / f"{finding_id}.json",
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            force,
        )
    fresh_audit = out / ".state/audits/fresh-cycle-03/audit-report.json"
    if fresh_audit.is_file():
        payload = {
            "schema_version": "aider-task-family-remedy-v1",
            "finding_id": "RFL-AUD-006",
            "source_audit": fresh_audit.relative_to(out).as_posix(),
            "source_audit_hash": _file_hash(fresh_audit),
            "family_id": FAMILY_ID,
            "disposition": "repair-owner-evidence-metadata",
            "status": "remediated_pending_regeneration_and_fresh_audit",
            "affected_roots": ["all-30-roots"],
            "actions": [
                "bind the cycle grader_policy_hash directly from its Docker receipt",
                "preserve one semantic field name for one exact policy fingerprint",
            ],
        }
        _write(
            out / ".state/remedy/RFL-AUD-006.json",
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            force,
        )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _validate_output(out)
    inventory = _freeze_inventory(out, force)
    existing = {
        record["task_id"]
        for name in ("legacy", "reverify", "expansion_before")
        for record in inventory["roots"][name]["records"]
    }
    requested = {case.task_id for case in CASES}
    if collisions := sorted(existing & requested):
        _fail("duplicate_task", ",".join(collisions))
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        if root.exists():
            for item in root.rglob("*"):
                if item.is_symlink() or (item.is_file() and item.stat().st_nlink > 1):
                    _fail("unsafe_path", f"link in owned root: {item}")
        _write_root(root, case, force)
        _write(out / ".state/specifications" / f"{case.task_id}.md", _remedy_spec(case), force)
        roots.append(root)
    _write_controls(out, force)
    _write_remedy_records(out, force)
    return tuple(roots)


_DOMAIN_WORDS = re.compile(
    r"\b(cadence|rhythm|reflow|layout|text|line|row|word|terminal|path|comment|"
    r"paragraph|annotation|margin|glyph|query|header|region|sentence|stream)\w*\b",
    re.I,
)
_ENDPOINT_WORDS = re.compile(
    r"\b(left|right|first|last|earlier|later|minimum|maximum|front|back|"
    r"ascending|descending|stable|reverse|endpoint|start|end)\w*\b",
    re.I,
)


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", text)
    text = _DOMAIN_WORDS.sub(" DOMAIN ", text)
    text = _ENDPOINT_WORDS.sub(" ENDPOINT ", text)
    text = re.sub(r"\b[A-Za-z_][A-Za-z_0-9]*-(?:[A-Za-z_0-9]+-)*[A-Za-z_0-9]+\b", " ID ", text)
    return tuple(
        token.lower()
        for token in re.findall(
            r"[A-Za-z_][A-Za-z_0-9]*|==|!=|&&|\|\||<=|>=|[-+*/%{}()[\];,?:=<>]",
            text,
        )
    )


def _reference_segments(reference: str) -> tuple[str, ...]:
    return tuple(
        segment.strip()
        for segment in re.split(r"(?<=[;{}])", reference)
        if segment.strip()
    )


def _owned_state_material(header: str, docs: str, reference: str) -> tuple[str, ...]:
    state_segments = " ".join(
        segment
        for segment in _reference_segments(reference)
        if not re.search(r"\b(?:if|else|for|while|switch|return)\b", segment)
    )
    return _normalized_tokens(header + "\n" + docs + "\n" + state_segments)


def _control_flow_material(reference: str) -> tuple[str, ...]:
    control_segments = " ".join(
        segment
        for segment in _reference_segments(reference)
        if re.search(r"\b(?:if|else|for|while|switch|return)\b", segment)
    )
    return _normalized_tokens(control_segments)


def _dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    header = next(root.glob("*.h")).read_text(encoding="utf-8")
    docs = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8")
    return {
        "public_api": _normalized_tokens(header + docs),
        "owned_state_algorithm": _owned_state_material(header, docs, reference),
        "mutation_selection_rules": _normalized_tokens(docs + reference),
        "invalid_boundary_behavior": _normalized_tokens(docs + hidden),
        "reference_control_flow": _control_flow_material(reference),
        "deterministic_oracle": _normalized_tokens(docs + visible + hidden),
        "topic_negative_fixture": _normalized_tokens(negative),
    }


def _token_distance(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = Counter(left), Counter(right)
    shared = sum((a & b).values())
    total = sum((a | b).values())
    return 1.0 if total == 0 else 1.0 - shared / total


def _pair_decisions(left: Path, right: Path) -> dict[str, dict[str, object]]:
    a, b = _dimension_material(left), _dimension_material(right)
    decisions: dict[str, dict[str, object]] = {}
    for dimension in HARD_DIMENSIONS:
        distance = _token_distance(a[dimension], b[dimension])
        decisions[dimension] = {
            "materially_different": distance >= 0.08,
            "multiset_distance": round(distance, 6),
            "left_token_count": len(a[dimension]),
            "right_token_count": len(b[dimension]),
        }
    return decisions


def _semantic_screen(out: Path) -> dict[str, object]:
    roots = sorted((out / case.task_id for case in CASES), key=lambda path: path.name)
    pairs: list[dict[str, object]] = []
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions = _pair_decisions(left, right)
            if not all(item["materially_different"] for item in decisions.values()):
                _fail("duplicate_family", f"{left.name} vs {right.name}: {decisions}")
            pairs.append({"left": left.name, "right": right.name, "decisions": decisions})
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"pair count {len(pairs)} != {expected}")
    base = out / CONTROL_BASE_ID
    controls: dict[str, object] = {}
    control_manifest = json.loads(
        (out / ".state/adversarial-clone-controls/manifest.json").read_text(encoding="utf-8")
    )
    for name in CONTROL_NAMES:
        root = out / ".state/adversarial-clone-controls" / name
        decisions = _pair_decisions(base, root)
        if any(item["materially_different"] for item in decisions.values()):
            _fail("duplicate_family", f"clone control escaped: {name}: {decisions}")
        changed = control_manifest["controls"][name]["changed_files"]
        if not changed:
            _fail("duplicate_family", f"empty clone changes: {name}")
        controls[name] = {
            "changed_files": changed,
            "decisions": decisions,
            "production_rejected": True,
        }
    return {
        "status": "pass",
        "root_count": len(CASES),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "dimensions": list(HARD_DIMENSIONS),
        "minimum_multiset_distance": 0.08,
        "normalizer": "reflow-layout-domain-literal-endpoint-neutral-v1",
        "pairs": pairs,
        "controls": controls,
    }


def _ngrams(tokens: tuple[str, ...], width: int = 9) -> set[tuple[str, ...]]:
    return {
        tokens[index : index + width]
        for index in range(max(0, len(tokens) - width + 1))
    }


def _root_text(root: Path) -> str:
    return " ".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.stat().st_size < 1_000_000 and ".state" not in path.parts
    )


def _holdout_screen(out: Path) -> dict[str, object]:
    manifest = json.loads(HOLDOUT_MANIFEST.read_text(encoding="utf-8"))
    if set(manifest["task_ids"]) != OFFICIAL_HOLDOUTS:
        _fail("benchmark_content_overlap", "holdout manifest does not bind exact 26 IDs")
    found = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    if missing := sorted(OFFICIAL_HOLDOUTS - found):
        _fail("benchmark_content_overlap", f"bound holdouts unavailable: {missing}")
    candidates = {
        case.task_id: _ngrams(_normalized_tokens(_root_text(out / case.task_id)))
        for case in CASES
    }
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    for holdout_id in sorted(OFFICIAL_HOLDOUTS):
        holdout = _ngrams(_normalized_tokens(_root_text(HOLDOUT_ROOT / holdout_id)))
        for task_id, candidate in candidates.items():
            denominator = min(len(candidate), len(holdout))
            score = len(candidate & holdout) / denominator if denominator else 0.0
            comparisons += 1
            if score > strongest:
                strongest, strongest_pair = score, [task_id, holdout_id]
            if score >= 0.80:
                _fail("benchmark_content_overlap", f"{task_id} vs {holdout_id}: {score:.3f}")
    return {
        "status": "pass",
        "holdout_root_count": 26,
        "comparison_count": comparisons,
        "threshold": 0.80,
        "strongest_pair": strongest_pair,
        "strongest_containment": round(strongest, 6),
        "manifest_hash": _file_hash(HOLDOUT_MANIFEST),
    }


def _cross_tree_semantic_screen(out: Path) -> dict[str, object]:
    candidate_tokens = {
        case.task_id: set(_normalized_tokens(_root_text(out / case.task_id)))
        for case in CASES
    }
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    for tree_name, tree in (
        ("legacy", LEGACY_ROOT),
        ("reverify", REVERIFY_ROOT),
        ("expansion", EXPANSION_ROOT),
    ):
        for config in sorted(tree.rglob(".meta/config.json")) if tree.is_dir() else ():
            if ".state" in config.parts:
                continue
            root = config.parent.parent
            if root == out or out in root.parents:
                continue
            other = set(_normalized_tokens(_root_text(root)))
            for task_id, current in candidate_tokens.items():
                denominator = min(len(current), len(other))
                score = len(current & other) / denominator if denominator else 0.0
                comparisons += 1
                if score > strongest:
                    strongest = score
                    strongest_pair = [task_id, f"{tree_name}:{root.relative_to(tree).as_posix()}"]
                if score >= 0.92:
                    _fail("duplicate_family", f"cross-tree semantic overlap {score:.3f}: {strongest_pair}")
    return {
        "status": "pass",
        "comparison_count": comparisons,
        "threshold": 0.92,
        "strongest_pair": strongest_pair,
        "strongest_score": round(strongest, 6),
    }


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    if len(CASES) != 30 or len({case.task_id for case in CASES}) != 30:
        _fail("duplicate_task", f"expected exactly 30 unique roots, got {len(CASES)}")
    rows: list[dict[str, object]] = []
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        if config["files"]["solution"] != [f"{case.task_id}.h", f"{case.task_id}.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        if config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        forbidden = (
            ".meta/", "CMakeLists", "task_visible_test", "provenance",
            "negative_false_substitute", "example.cpp",
        )
        if any(token in prompt for token in forbidden):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if not answer.startswith(f"{case.task_id}.h\n```") or f"{case.task_id}.cpp\n```" not in answer:
            _fail("target_reference_mismatch", case.task_id)
        prompt_hash = _sha(prompt.encode())
        reference_hash = _sha(
            (root / ".meta/example.h").read_bytes()
            + b"\0"
            + (root / ".meta/example.cpp").read_bytes()
        )
        if prompt_hash in prompt_hashes or reference_hash in reference_hashes:
            _fail("duplicate_family", f"duplicate prompt/reference hash: {case.task_id}")
        prompt_hashes.add(prompt_hash)
        reference_hashes.add(reference_hash)
        rows.append(
            {
                "task_id": case.task_id,
                "mechanism": case.mechanism,
                "tree_hash": _tree_hash(root),
                "prompt_hash": prompt_hash,
                "starter_hash": _file_hash(root / f"{case.task_id}.cpp"),
                "reference_hash": reference_hash,
                "visible_test_hash": _file_hash(root / "task_visible_test.cpp"),
                "hidden_test_hash": _file_hash(root / ".meta/task_hidden_test.cpp"),
                "negative_hash": _file_hash(root / ".meta/negative_false_substitute.cpp"),
                "metadata_hash": _file_hash(root / ".meta/config.json"),
                "provenance_hash": _file_hash(root / ".meta/provenance.json"),
                "primary_core_objective": "achieved",
            }
        )
    diversity = _semantic_screen(out)
    holdout = _holdout_screen(out)
    cross_tree = _cross_tree_semantic_screen(out)
    manifest: dict[str, object] = {
        "schema_version": "reflow-layout-materialization-v1",
        "family_id": FAMILY_ID,
        "task_count": 30,
        "owner_hash": _file_hash(Path(__file__)),
        "case_hash": _file_hash(CASE_PATH),
        "curriculum_hash": _file_hash(CURRICULUM),
        "focused_test_hash": _file_hash(TEST_PATH),
        "wrapper_hash": _file_hash(WRAPPER_PATH),
        "family_tree_hash": _tree_hash(out),
        "tasks": rows,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "diversity": diversity,
            "benchmark_holdout": holdout,
            "cross_tree": cross_tree,
        },
        "strongest_local_status": "pending_execution",
        "dataset_handoff": "not_requested",
    }
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    return manifest


def _archive(out: Path, target: Path) -> str:
    roots = [out / case.task_id for case in CASES] + [
        out / ".state/adversarial-clone-controls" / name for name in CONTROL_NAMES
    ]
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for root in roots:
            prefix = "tasks" if root.parent == out else "controls"
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(
                    str(path),
                    arcname=f"{prefix}/{root.name}/{path.relative_to(root).as_posix()}",
                )
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = stat.S_IFREG | 0o644
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
    return _file_hash(target)


def verify_docker(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["family_tree_hash"] != _tree_hash(out):
        _fail("generator_output_drift", "manifest does not bind current task tree")
    if manifest["owner_hash"] != _file_hash(Path(__file__)) or manifest["case_hash"] != _file_hash(CASE_PATH):
        _fail("generator_output_drift", "manifest does not bind current owner")
    with tempfile.TemporaryDirectory(prefix="reflow-layout-docker-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        result = temp / "result"
        result.mkdir()
        archive_hash = _archive(out, archive)
        script = r'''set -Eeuo pipefail
mkdir -p /work /result
tar -xf /input/family.tar -C /work
sha256sum /input/family.tar | awk '{print "archive\t"$1}' > /result/results.tsv
command -v c++ > /result/compiler.path
c++ --version | head -1 > /result/compiler.version
sha256sum "$(command -v c++)" | awk '{print $1}' > /result/compiler.sha256
cmake --version | head -1 > /result/cmake.version
trap 'status=$?; for log in /tmp/config.log /tmp/build.log /tmp/test.log; do if [ -f "$log" ]; then echo "===== $log =====" >&2; tail -160 "$log" >&2; fi; done; exit "$status"' ERR
run_one(){
  kind="$1"; id="$2"; mode="$3"; role="$4"; source="$5"
  root="/work/${kind}/${id}"; build="/tmp/${kind}-${id}-${mode}-${role}"
  flags=()
  if [ "$mode" = sanitizer ];then
    flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined")
  fi
  : >/tmp/config.log; : >/tmp/build.log; : >/tmp/test.log
  cmake -S "$root" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$root/$source" "${flags[@]}" >/tmp/config.log 2>&1
  cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1
  count=$(ctest --test-dir "$build" -N | sed -n 's/^Total Tests: //p')
  test "$count" = 2
  outcome=compile_pass
  if [ "$role" = negative ];then
    if ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1;then
      echo "negative passed $id $mode" >&2
      exit 71
    fi
    outcome=expected_test_failure
  elif [ "$role" != starter ];then
    ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1
    outcome=test_pass
  fi
  config_hash=$(sha256sum /tmp/config.log | awk '{print $1}')
  build_hash=$(sha256sum /tmp/build.log | awk '{print $1}')
  test_hash=$(sha256sum /tmp/test.log | awk '{print $1}')
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$kind" "$id" "$mode" "$role" "$source" "$count" "$outcome" "$config_hash" "$build_hash" "$test_hash" >>/result/results.tsv
}
for root in /work/tasks/*;do
  id=${root##*/}
  run_one tasks "$id" normal starter "$id.cpp"
  run_one tasks "$id" sanitizer starter "$id.cpp"
  run_one tasks "$id" normal reference .meta/example.cpp
  run_one tasks "$id" sanitizer reference .meta/example.cpp
  run_one tasks "$id" normal negative .meta/negative_false_substitute.cpp
  run_one tasks "$id" sanitizer negative .meta/negative_false_substitute.cpp
done
for root in /work/controls/*;do
  id=${root##*/}
  run_one controls "$id" normal control .meta/example.cpp
  run_one controls "$id" sanitizer control .meta/example.cpp
done
'''
        completed = subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none",
                "--mount", f"type=bind,src={archive},dst=/input/family.tar,readonly",
                "--mount", f"type=bind,src={result},dst=/result",
                image, "bash", "-lc", script,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            _fail("docker_sanity_failed", (completed.stdout + completed.stderr)[-16000:])
        rows = [line.split("\t") for line in (result / "results.tsv").read_text().splitlines()]
        mounted = "sha256:" + rows[0][1]
        if mounted != archive_hash:
            _fail("grader_mount_hash_mismatch", f"{mounted} != {archive_hash}")
        execution_rows: list[dict[str, object]] = []
        for fields in rows[1:]:
            if len(fields) != 10:
                _fail("execution_ledger_invalid", repr(fields))
            kind, task_id, mode, role, source, count, outcome, config_hash, build_hash, test_hash = fields
            command_policy = {
                "configure": "cmake -G Unix Makefiles -DTASK_SOURCE=<exact-source>",
                "build": "cmake --build <fresh-build> --parallel 2",
                "test": "not-run" if role == "starter" else "ctest --output-on-failure",
                "mode": mode,
                "role": role,
            }
            execution_rows.append(
                {
                    "subject_kind": kind,
                    "task_id": task_id,
                    "mode": mode,
                    "role": role,
                    "source": source,
                    "discovered_test_count": int(count),
                    "outcome": outcome,
                    "configure_log_hash": "sha256:" + config_hash,
                    "build_log_hash": "sha256:" + build_hash,
                    "test_log_hash": "sha256:" + test_hash,
                    "command_policy_hash": _sha(
                        json.dumps(command_policy, sort_keys=True).encode()
                    ),
                }
            )
        references = [row for row in execution_rows if row["subject_kind"] == "tasks" and row["role"] == "reference"]
        negatives = [row for row in execution_rows if row["subject_kind"] == "tasks" and row["role"] == "negative"]
        starters = [row for row in execution_rows if row["subject_kind"] == "tasks" and row["role"] == "starter"]
        controls = [row for row in execution_rows if row["subject_kind"] == "controls"]
        if len(references) != 60 or len(negatives) != 60 or len(starters) != 60 or len(controls) != 6:
            _fail(
                "sanitizer_test_count_mismatch",
                f"references={len(references)} negatives={len(negatives)} "
                f"starters={len(starters)} controls={len(controls)}",
            )
        if any(row["discovered_test_count"] != 2 for row in execution_rows):
            _fail("sanitizer_test_count_mismatch", "discovery is not exactly two")
        compiler = {
            "path": (result / "compiler.path").read_text().strip(),
            "version": (result / "compiler.version").read_text().strip(),
            "sha256": "sha256:" + (result / "compiler.sha256").read_text().strip(),
        }
        grader_policy_hash = _sha((image + "\0" + CMAKE + "\0" + script).encode())
        ledger: dict[str, object] = {
            "schema_version": "reflow-layout-docker-execution-ledger-v1",
            "status": "pass",
            "image": image,
            "network_policy": "none",
            "archive_hash": archive_hash,
            "mounted_archive_hash": mounted,
            "family_tree_hash": _tree_hash(out),
            "compiler": compiler,
            "cmake": (result / "cmake.version").read_text().strip(),
            "cmake_policy_hash": _sha(CMAKE.encode()),
            "docker_script_hash": _sha(script.encode()),
            "grader_policy_hash": grader_policy_hash,
            "raw_result_hash": _file_hash(result / "results.tsv"),
            "row_count": len(execution_rows),
            "rows": execution_rows,
        }
        ledger_path = out / ".state/docker-execution-ledger.json"
        _write(ledger_path, json.dumps(ledger, indent=2, sort_keys=True) + "\n", True)
        receipt: dict[str, object] = {
            "schema_version": "reflow-layout-docker-sanity-v2",
            "status": "pass",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "image_digest_locked": True,
            "network_policy": "none",
            "image": image,
            "archive_hash": archive_hash,
            "mounted_archive_hash": mounted,
            "family_tree_hash": _tree_hash(out),
            "owner_hash": _file_hash(Path(__file__)),
            "case_hash": _file_hash(CASE_PATH),
            "curriculum_hash": _file_hash(CURRICULUM),
            "focused_test_hash": _file_hash(TEST_PATH),
            "wrapper_hash": _file_hash(WRAPPER_PATH),
            "cmake_policy_hash": _sha(CMAKE.encode()),
            "docker_script_hash": _sha(script.encode()),
            "grader_policy_hash": grader_policy_hash,
            "materialization_subject_hash": _sha(
                json.dumps(manifest, sort_keys=True).encode()
            ),
            "execution_ledger": ".state/docker-execution-ledger.json",
            "execution_ledger_hash": _file_hash(ledger_path),
            "execution_row_count": len(execution_rows),
            "compiler": compiler,
            "cmake": (result / "cmake.version").read_text().strip(),
            "normal_starter_count": 30,
            "sanitizer_starter_count": 30,
            "normal_reference_count": 30,
            "sanitizer_reference_count": 30,
            "normal_negative_count": 30,
            "sanitizer_negative_count": 30,
            "normal_test_count_per_subject": 2,
            "sanitizer_test_count_per_subject": 2,
            "control_count": 3,
            "control_mode_count": 6,
        }
        _write(
            out / ".state/docker-sanity.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["docker_sanity"] = {
        "status": "pass",
        "receipt": ".state/docker-sanity.json",
        "execution_ledger": ".state/docker-execution-ledger.json",
        "execution_ledger_hash": receipt["execution_ledger_hash"],
        "execution_row_count": receipt["execution_row_count"],
        "normal_starter_count": 30,
        "sanitizer_starter_count": 30,
        "normal_test_count_per_subject": 2,
        "sanitizer_test_count_per_subject": 2,
        "negative_fixture_count": 30,
        "control_count": 3,
    }
    manifest["strongest_local_status"] = "creator_preflight_passed_pending_independent_audit"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return receipt


def _host_subject_matrix(out: Path) -> list[tuple[str, str, str, str, str]]:
    plans: list[tuple[str, str, str, str, str]] = []
    for case in CASES:
        for mode in ("normal", "sanitizer"):
            plans.append(("tasks", case.task_id, mode, "starter", f"{case.task_id}.cpp"))
            plans.append(("tasks", case.task_id, mode, "reference", ".meta/example.cpp"))
            plans.append(
                ("tasks", case.task_id, mode, "negative", ".meta/negative_false_substitute.cpp")
            )
    for name in CONTROL_NAMES:
        for mode in ("normal", "sanitizer"):
            plans.append(("controls", name, mode, "control", ".meta/example.cpp"))
    return plans


def _run_host_subject(
    out: Path, build_parent: Path, plan: tuple[str, str, str, str, str]
) -> dict[str, object]:
    kind, task_id, mode, role, source = plan
    root = out / task_id if kind == "tasks" else out / ".state/adversarial-clone-controls" / task_id
    build = build_parent / f"{kind}-{task_id}-{mode}-{role}"
    flags: list[str] = []
    if mode == "sanitizer":
        flags = [
            "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
            "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
        ]
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, check=False,
        )

    configure = run(
        [
            "cmake", "-S", str(root), "-B", str(build), "-G", "Unix Makefiles",
            f"-DTASK_SOURCE={root / source}", *flags,
        ]
    )
    if configure.returncode != 0:
        code = "starter_compile_failed" if role == "starter" else "reference_compile_failed"
        _fail(code, f"{kind}/{task_id}/{mode}/{role}: {configure.stdout[-2000:]}")
    compiled = run(["cmake", "--build", str(build), "--parallel", "2"])
    if compiled.returncode != 0:
        code = "starter_compile_failed" if role == "starter" else "reference_compile_failed"
        _fail(code, f"{kind}/{task_id}/{mode}/{role}: {compiled.stdout[-2000:]}")
    discovery = run(["ctest", "--test-dir", str(build), "-N"])
    match = re.search(r"^Total Tests: (\d+)$", discovery.stdout, flags=re.M)
    count = int(match.group(1)) if match else 0
    if count != 2:
        _fail(
            "sanitizer_test_count_mismatch",
            f"{kind}/{task_id}/{mode}/{role}: discovery {count} != 2",
        )
    test_log = ""
    outcome = "compile_pass"
    if role == "negative":
        executed = run(["ctest", "--test-dir", str(build), "--output-on-failure"])
        test_log = executed.stdout
        if executed.returncode == 0:
            _fail(
                "negative_fixture_not_rejected",
                f"{kind}/{task_id}/{mode}: false substitute passed the production tests",
            )
        outcome = "expected_test_failure"
    elif role != "starter":
        executed = run(["ctest", "--test-dir", str(build), "--output-on-failure"])
        test_log = executed.stdout
        if executed.returncode != 0:
            code = (
                "reference_sanitizer_failed" if mode == "sanitizer" else "reference_tests_failed"
            )
            _fail(code, f"{kind}/{task_id}/{mode}: {executed.stdout[-2000:]}")
        outcome = "test_pass"
    command_policy = {
        "configure": "cmake -G Unix Makefiles -DTASK_SOURCE=<exact-source>",
        "build": "cmake --build <fresh-build> --parallel 2",
        "test": "not-run" if role == "starter" else "ctest --output-on-failure",
        "mode": mode,
        "role": role,
    }
    return {
        "subject_kind": kind,
        "task_id": task_id,
        "mode": mode,
        "role": role,
        "source": source,
        "discovered_test_count": count,
        "outcome": outcome,
        "configure_log_hash": _sha(configure.stdout.encode()),
        "build_log_hash": _sha(compiled.stdout.encode()),
        "test_log_hash": _sha(test_log.encode()),
        "command_policy_hash": _sha(json.dumps(command_policy, sort_keys=True).encode()),
    }


def verify_host(out: Path = DEFAULT_OUT, jobs: int = 8) -> dict[str, object]:
    """Run the full normal/sanitizer subject matrix on the host toolchain.

    This is the owner-designated host verification used by host-only
    campaigns. It reruns every starter, reference, negative fixture, and
    coherent clone control through a clean normal build and a fresh
    ASan/UBSan build with the host CMake/C++ toolchain, requiring exactly
    two discovered tests per subject, passing references, and rejected
    negatives. It never replaces the mandatory network-disabled Docker
    sanity gate required for ``local_family_verified``.
    """
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["family_tree_hash"] != _tree_hash(out):
        _fail("generator_output_drift", "manifest does not bind current task tree")
    if manifest["owner_hash"] != _file_hash(Path(__file__)) or manifest["case_hash"] != _file_hash(CASE_PATH):
        _fail("generator_output_drift", "manifest does not bind current owner")
    cmake = shutil.which("cmake")
    cxx = shutil.which("c++")
    if cmake is None or cxx is None:
        _fail("host_toolchain_missing", f"cmake={cmake} c++={cxx}")
    compiler_path = str(Path(cxx).resolve())
    compiler = {
        "path": compiler_path,
        "version": subprocess.run(
            [compiler_path, "--version"], text=True, stdout=subprocess.PIPE, check=False
        ).stdout.splitlines()[0],
        "sha256": _file_hash(Path(compiler_path)),
    }
    cmake_version = subprocess.run(
        [cmake, "--version"], text=True, stdout=subprocess.PIPE, check=False
    ).stdout.splitlines()[0]
    plans = _host_subject_matrix(out)
    with tempfile.TemporaryDirectory(prefix="reflow-layout-host-") as temporary:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            rows = list(
                pool.map(lambda plan: _run_host_subject(out, Path(temporary), plan), plans)
            )
    references = [row for row in rows if row["subject_kind"] == "tasks" and row["role"] == "reference"]
    negatives = [row for row in rows if row["subject_kind"] == "tasks" and row["role"] == "negative"]
    starters = [row for row in rows if row["subject_kind"] == "tasks" and row["role"] == "starter"]
    controls = [row for row in rows if row["subject_kind"] == "controls"]
    if len(references) != 60 or len(negatives) != 60 or len(starters) != 60 or len(controls) != 6:
        _fail(
            "sanitizer_test_count_mismatch",
            f"references={len(references)} negatives={len(negatives)} "
            f"starters={len(starters)} controls={len(controls)}",
        )
    if any(row["discovered_test_count"] != 2 for row in rows):
        _fail("sanitizer_test_count_mismatch", "discovery is not exactly two")
    host_policy = {
        "configure": "cmake -G Unix Makefiles -DTASK_SOURCE=<exact-source>",
        "build": "cmake --build <fresh-build> --parallel 2",
        "test": "ctest --output-on-failure (skipped for starters)",
        "sanitizer_flags": "-fsanitize=address,undefined -fno-omit-frame-pointer",
    }
    grader_policy_hash = _sha(
        ("host\0" + CMAKE + "\0" + json.dumps(host_policy, sort_keys=True)).encode()
    )
    receipt: dict[str, object] = {
        "schema_version": "reflow-layout-host-verify-v1",
        "status": "pass",
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "network_policy": "host-local; no sandbox (campaign gate: host verify only)",
        "family_tree_hash": _tree_hash(out),
        "owner_hash": _file_hash(Path(__file__)),
        "case_hash": _file_hash(CASE_PATH),
        "curriculum_hash": _file_hash(CURRICULUM),
        "focused_test_hash": _file_hash(TEST_PATH),
        "wrapper_hash": _file_hash(WRAPPER_PATH),
        "cmake_policy_hash": _sha(CMAKE.encode()),
        "grader_policy_hash": grader_policy_hash,
        "compiler": compiler,
        "cmake": cmake_version,
        "materialization_subject_hash": _sha(
            json.dumps(manifest, sort_keys=True).encode()
        ),
        "row_count": len(rows),
        "rows": rows,
        "normal_starter_count": 30,
        "sanitizer_starter_count": 30,
        "normal_reference_count": 30,
        "sanitizer_reference_count": 30,
        "normal_negative_count": 30,
        "sanitizer_negative_count": 30,
        "normal_test_count_per_subject": 2,
        "sanitizer_test_count_per_subject": 2,
        "control_count": 3,
        "control_mode_count": 6,
    }
    receipt_path = out / ".state/host-verify.json"
    _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["host_verify"] = {
        "status": "pass",
        "receipt": ".state/host-verify.json",
        "receipt_hash": _file_hash(receipt_path),
        "execution_row_count": len(rows),
        "evidence_class": "host_verify",
        "note": (
            "host-only campaign evidence; does not replace the mandatory "
            "network-disabled Docker sanity gate for local_family_verified"
        ),
    }
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return receipt


def _append_cycle(out: Path, status: str) -> Path:
    cycles = out / ".state/cycles"
    cycles.mkdir(parents=True, exist_ok=True)
    prior_paths = sorted(cycles.glob("cycle-*.json"))
    number = len(prior_paths) + 1
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    receipt_path = out / ".state/docker-sanity.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
    remedy_records = {
        path.stem: _file_hash(path)
        for path in sorted((out / ".state/remedy").glob("RFL-AUD-*.json"))
    }
    current_subject = {
        "family_tree_hash": _tree_hash(out),
        "curriculum_hash": _file_hash(CURRICULUM),
        "generator_hash": _file_hash(Path(__file__)),
        "case_hash": _file_hash(CASE_PATH),
        "focused_test_hash": _file_hash(TEST_PATH),
        "grader_policy_hash": (
            receipt["grader_policy_hash"] if receipt is not None else "not_available"
        ),
    }
    invalidated: list[dict[str, object]] = []
    for prior_path in prior_paths:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        changed = [key for key, value in current_subject.items() if prior.get(key) != value]
        if changed:
            invalidated.append(
                {
                    "cycle": prior.get("cycle"),
                    "path": prior_path.relative_to(out).as_posix(),
                    "reason": "subject_or_policy_changed",
                    "changed_fields": changed,
                }
            )
    record = {
        "schema_version": "aider-task-creator-cycle-v1",
        "cycle": number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "family_id": FAMILY_ID,
        "candidate_manifest": ".state/materialization-manifest.json",
        **current_subject,
        "retained_root_ids": [case.task_id for case in CASES],
        "replaced_root_ids": [],
        "rejected_root_ids": [],
        "review_root_ids": [],
        "blocked_root_ids": [],
        "manifest_subject_hash": _sha(json.dumps(manifest, sort_keys=True).encode()),
        "docker_receipt": receipt,
        "remedy_record_hashes": remedy_records,
        "prior_evidence_invalidated": invalidated,
    }
    path = cycles / f"cycle-{number:02d}.json"
    _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", False)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--host-jobs", type=int, default=8)
    parser.add_argument("--record-cycle", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core or args.docker_sanity or args.verify_host:
        verify_core(args.out)
    if args.docker_sanity:
        verify_docker(args.out)
    if args.verify_host:
        verify_host(args.out, jobs=args.host_jobs)
    if args.record_cycle:
        if args.verify_host and not args.docker_sanity:
            cycle_status = "campaign_host_verify"
        elif args.docker_sanity and (args.out / ".state/remedy").is_dir():
            cycle_status = "remediated_creator_preflight"
        else:
            cycle_status = "creator_preflight" if args.docker_sanity else "generated"
        _append_cycle(args.out, cycle_status)
    print(f"Wrote {len(roots)} Reflow and layout roots under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
