"""Materialize and reverify clean-room sliding-window-maximum replacements."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_sliding_window_maximum_cases import CASES, SlidingCase
from w8_biayn.integrations.moonlight_sliding_window_maximum_hard_rule import (
    NEGATIVE_MUTATIONS,
    TRACE_OPERATION_TOKENS,
    TRACE_SNIPPETS,
)

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/sliding-window-maximum")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/sliding-window-maximum")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SLIDING_WINDOW_MAXIMUM_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-dsa/sliding-window-maximum.md"
FAMILY_ID = "aider-dsa-sliding-window-maximum-v2"
MANIFEST_SCHEMA = "aider-sliding-window-maximum-materialization-v3"
SEMANTIC_NORMALIZER = "sliding-window-v2-control-flow-9gram"
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
REMEDY_HEADINGS = (
    "Identity",
    "Objective",
    "Public API",
    "Behavior table",
    "Implementation invariant",
    "Starter and reference",
    "Tests",
    "Files and metadata",
    "Build/oracle",
    "Family/contamination",
    "Optional dataset handoff",
    "Acceptance",
)
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset(
    (
        "all-your-base",
        "allergies",
        "bank-account",
        "binary-search-tree",
        "circular-buffer",
        "clock",
        "complex-numbers",
        "crypto-square",
        "diamond",
        "dnd-character",
        "gigasecond",
        "grade-school",
        "kindergarten-garden",
        "knapsack",
        "linked-list",
        "meetup",
        "parallel-letter-frequency",
        "perfect-numbers",
        "phone-number",
        "queen-attack",
        "robot-name",
        "space-age",
        "spiral-matrix",
        "sublist",
        "yacht",
        "zebra-puzzle",
    )
)
TASKS = CASES


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _source_hash(path: Path | None = None) -> str:
    return _sha_bytes((path or Path(__file__)).read_bytes())


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


CMAKE = """cmake_minimum_required(VERSION 3.16)
project(sliding_window_maximum_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror -Wno-error=misleading-indentation)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
"""

TREE_DIGEST_HELPER = r'''from __future__ import annotations
import hashlib
from pathlib import Path

family = Path("/tmp/family")
lines = []
for root in sorted(path for path in family.iterdir() if path.is_dir()):
    digest = hashlib.sha256()
    paths = sorted(
        path for path in root.rglob("*") if path.is_file() and ".state" not in path.parts
    )
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    lines.append(f"{root.name}\tsha256:{digest.hexdigest()}")
Path("/result/tree-digests.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
'''


def _remedy_markdown(case: SlidingCase) -> str:
    return f"""## Identity

Task ID: `{case.task_id}`; legacy root: `{case.legacy_id}`; task-spec revision: 2; family ID: `{FAMILY_ID}/{case.task_id}`; disposition: `replace`; source inventory: `sliding-window-maximum-clean-room-v2`; license result: repository-authored/pass; generator: `src/w8_biayn/integrations/moonlight_sliding_window_maximum_aider_tasks.py`; benchmark screen: pending. Selected prompt: `docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with `FAMILY_NAME=sliding-window-maximum`, `FAMILY_TYPE=aider-dsa`.

## Objective

{case.objective}

## Public API

C++17 namespace `curriculum`; editable order is `{case.task_id}.h`, then `{case.task_id}.cpp`. API: `{case.public_api}`. Inputs and return values are owned values; results preserve the documented deterministic ordering and ties.

## Behavior table

Valid inputs execute the objective and return the documented maximum record or state. Invalid bounds, dimensions, domains, timestamps, or empty state return the documented false/empty sentinel without partial mutation. Duplicate maxima follow the task-specific tie rule. Expiry removes only observations outside the task's count, timestamp, generation, range, or explicit FIFO boundary. Arithmetic is checked before indexing. The visible test contains the public boundary example; private tests cover empty, singleton, duplicate-maximum, expiry, and invalid-input behavior.

## Implementation invariant

Required mechanism: {case.invariant}. Required source evidence: {", ".join(f"`{token}`" for token in case.required_tokens)}. Forbidden substitutes are the legacy shared count/time monotonic-deque template, renamed copies of another v2 root, full-window rescans where the contract requires indexed state, hard-coded answers, and benchmark assets.

## Starter and reference

The task-named header declares the complete API. The task-named source is a coherent incomplete implementation. `.meta/example.cpp` is an independently authored reference that owns and maintains the required mechanism. It does not import legacy renderers or hidden fixtures.

## Tests

The visible executable covers the normal contract. The private executable covers task-specific boundaries and the prior family defect. Stateful APIs add a deterministic model trace that invokes every public operation and compares complete observable state after each mutation. A private topic-specific false substitute must compile with the same strict flags, discover both designated tests, execute them, and be rejected. The emitted `renamed-domain-clone`, `constants-policy-clone`, `opposite-end-clone`, and `missing-mechanism-token` controls must execute the duplicate/invariant rejection path.

## Files and metadata

Solutions: `{case.task_id}.h`, `{case.task_id}.cpp`. Test: `task_visible_test.cpp`; private test: `.meta/task_hidden_test.cpp`. References: `.meta/example.h`, `.meta/example.cpp`, mapped by suffix and solution order. Docs, tests, metadata, references, CMake, manifests, and receipts remain private. Provenance binds the legacy root, family/profile, prompt, and repository-authored origin.

## Build/oracle

C++17, strict warnings, explicit `Unix Makefiles`, locked `c++`, two CTest targets. Run clean normal and separate fresh ASan/UBSan reference builds in `{SANITY_IMAGE}` with Docker network `none`, then compile and execute the false substitute against the same suite. Expected discovery is two tests in every mode; references pass and the substitute fails. The receipt binds the deterministic archive, independently recomputed mounted task-tree hashes, task/reference/owner hashes, image identity, resolved compiler path/version/binary hash, CMake version, commands, and counts.

## Family/contamination

Compare normalized public APIs, references, and tests across all 20 v2 roots, all legacy roots, and all 26 bound official C++ holdouts using `{SEMANTIC_NORMALIZER}`. Family and permanent-holdout decisions remain pending until owner verification passes; no waiver is allowed.

## Optional dataset handoff

`not_requested`. No JSONL, token/mask evidence, split, export, consumer verification, training, or release is authorized.

## Acceptance

Run focused pytest, owner `--verify-core`, and owner `--verify-docker`. Require exact generator regeneration, prompt/role/reference safety, 20 unique mechanisms and six-dimension all-pairs evidence, execution of all four emitted adversarial controls, benchmark separation, equal positive normal/sanitizer counts, independent mounted task-tree hashes, and 20 strictly compiling false substitutes rejected by their executed tests. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `hard_rule_pair_not_distinct`, `negative_fixture_not_rejected`, `benchmark_content_overlap`, `generator_output_drift`, `grader_mount_tree_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state" / "remedy"
    owner_hash = _source_hash()
    for case in CASES:
        markdown = _remedy_markdown(case)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id_before": "aider-dsa-sliding-window-maximum-v1",
            "family_id_after": f"{FAMILY_ID}/{case.task_id}",
            "tree_hash_before": _tree_hash(LEGACY_ROOT / case.legacy_id),
            "generator_path": "src/w8_biayn/integrations/moonlight_sliding_window_maximum_aider_tasks.py",
            "generator_revision": owner_hash,
            "selected_prompt": "docs/aider-tasks-spec/prompts/remediate-family-reverify.md",
            "user_inputs": {"FAMILY_NAME": "sliding-window-maximum", "FAMILY_TYPE": "aider-dsa"},
            "finding_ids": [
                "SWM-F1-template-semantic-duplicate",
                "SWM-F2-objective-mechanism-collapse",
                "SWM-F3-oracle-evidence-stale",
                "SWM-F4-hard-rule-evidence-gap",
            ],
            "disposition": "replace",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{case.task_id}.md",
            "remedy_spec_hash": _sha_bytes(markdown.encode()),
            "status": "planned",
            "primary_core_objective": "specified",
            "dataset_handoff": "not_requested",
        }
        _write(remedy / f"{case.task_id}.md", markdown, force)
        _write(
            remedy / f"{case.task_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            force,
        )


def _sync_remedies(out: Path, **updates: object) -> None:
    remedy = out / ".state" / "remedy"
    for case in CASES:
        path = remedy / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["generator_revision_after"] = _source_hash()
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _negative_source(case: SlidingCase) -> tuple[str, str]:
    try:
        old, new, reason = NEGATIVE_MUTATIONS[case.task_id]
    except KeyError:
        _fail("negative_fixture_missing", case.task_id)
    if case.reference.count(old) != 1:
        _fail(
            "negative_fixture_ambiguous",
            f"{case.task_id}: expected one mutation target, found {case.reference.count(old)}",
        )
    source = case.reference.replace(old, new, 1)
    if source == case.reference:
        _fail("negative_fixture_missing", case.task_id)
    return source, reason


def _hidden_test_with_trace(case: SlidingCase) -> str:
    snippet = TRACE_SNIPPETS.get(case.task_id, "")
    if not snippet:
        return case.hidden_test
    marker = "  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;"
    if case.hidden_test.count(marker) != 1:
        _fail("deterministic_trace_missing", case.task_id)
    return case.hidden_test.replace(marker, snippet + "\n" + marker, 1)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _write_remedies(out, force)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        negative_source, negative_reason = _negative_source(case)
        config = {
            "authors": ["w8-biayn"],
            "blurb": case.objective,
            "files": {
                "solution": ["task.h", "task.cpp"],
                "test": ["task_visible_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "curriculum_document": CURRICULUM,
            "family_specification": FAMILY_SPEC,
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id": FAMILY_ID,
            "semantic_profile": case.profile,
            "origin": "newly authored in-repository clean-room replacement",
            "license": "repository-authored",
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
            "benchmark_separation": "Independent API, owned state, algorithm, and tests; official Aider C++ roots remain permanent holdouts.",
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": case.instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f'[visible]\ndescription = "normal {case.profile} behavior and public boundary"\n\n[hidden]\ndescription = "invalid, empty, duplicate, expiry, and task-specific mechanism regression"\n',
            ".meta/negative_fixture.json": json.dumps(
                {
                    "task_id": case.task_id,
                    "kind": "compiling_topic_specific_false_substitute",
                    "expected": "strict compile succeeds; designated CTest suite rejects",
                    "reason": negative_reason,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            ".meta/negative_fixture.cpp": negative_source,
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": _hidden_test_with_trace(case),
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def _safe_relative(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value:
        _fail("unsafe_path", value)
    return path.as_posix()


def _whole_format_code(root: Path, response: str) -> str | None:
    task = load_task(root)
    try:
        blocks = parse_whole_file_blocks(response)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(blocks) == set(task.editable_files) else "whole_format_failed"


def _normalized_code_tokens(content: str) -> list[str]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", content)
    keywords = {
        "if",
        "else",
        "for",
        "while",
        "return",
        "class",
        "struct",
        "const",
        "auto",
        "bool",
        "int",
        "long",
        "void",
        "true",
        "false",
        "public",
        "private",
        "namespace",
        "std",
        "vector",
        "deque",
        "queue",
        "priority_queue",
        "optional",
        "array",
        "unique_ptr",
        "shared_ptr",
    }
    return [
        token if token in keywords or not re.match(r"[A-Za-z_]", token) else "ID" for token in raw
    ]


def _ngrams(tokens: list[str], width: int = 9) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + width]) for i in range(max(0, len(tokens) - width + 1))}


def _semantic_signatures(cases: Sequence[SlidingCase] | None = None) -> dict[str, str]:
    selected = tuple(cases or CASES)
    signatures: dict[str, str] = {}
    fingerprints: dict[str, set[tuple[str, ...]]] = {}
    for case in selected:
        mechanism_source = case.header + "\n" + case.reference
        if case.marker not in mechanism_source or any(
            token not in mechanism_source for token in case.required_tokens
        ):
            _fail("invariant_not_enforced", f"missing-mechanism-token: {case.task_id}")
        tokens = _normalized_code_tokens(
            case.header + "\n" + case.reference + "\n" + case.visible_test + "\n" + case.hidden_test
        )
        signature = _sha_bytes(" ".join(tokens).encode())
        grams = _ngrams(tokens)
        for other, other_grams in fingerprints.items():
            denominator = min(len(grams), len(other_grams))
            similarity = len(grams & other_grams) / denominator if denominator else 1.0
            if similarity >= 0.78:
                _fail("duplicate_family", f"{case.task_id} resembles {other}: {similarity:.3f}")
        fingerprints[case.task_id] = grams
        signatures[case.task_id] = signature
    if len({case.profile for case in selected}) != len(selected) or len(
        {case.public_api for case in selected}
    ) != len(selected):
        _fail("duplicate_family", "profiles and public APIs must be one-to-one")
    return signatures


def _artifact_parts(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = [_safe_relative(value) for value in config["files"]["solution"]]
    examples = [_safe_relative(value) for value in config["files"]["example"]]
    header = next(value for value in solution if value.endswith((".h", ".hpp")))
    reference = next(value for value in examples if value.endswith(".cpp"))
    return {
        "docs": (root / ".docs/instructions.md").read_text(encoding="utf-8"),
        "api": (root / header).read_text(encoding="utf-8"),
        "reference": (root / reference).read_text(encoding="utf-8"),
        "visible": (root / "task_visible_test.cpp").read_text(encoding="utf-8"),
        "hidden": (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8"),
        "negative": (root / ".meta/negative_fixture.cpp").read_text(encoding="utf-8"),
    }


def _dimension_hash(content: str) -> str:
    return _sha_bytes(" ".join(_normalized_code_tokens(content)).encode())


def _projected_dimension_hash(content: str, allowed: frozenset[str]) -> str:
    projected = [token for token in _normalized_code_tokens(content) if token in allowed]
    return _sha_bytes(" ".join(projected).encode())


CONTROL_FLOW_TOKENS = frozenset(
    {
        "if",
        "else",
        "for",
        "while",
        "return",
        "true",
        "false",
        "==",
        "!=",
        "<=",
        ">=",
        "&&",
        "||",
        "++",
        "--",
        "<",
        ">",
        "?",
        ":",
        ";",
        "{",
        "}",
    }
)
MUTATION_SELECTION_TOKENS = frozenset(
    {
        "ID",
        "=",
        "++",
        "--",
        "return",
        "?",
        "[",
        "]",
        "std",
        "vector",
        "deque",
        "queue",
        "priority_queue",
        "optional",
        "array",
        "unique_ptr",
        "shared_ptr",
        "<",
        ">",
        "<=",
        ">=",
        "==",
        "!=",
    }
)


def _screen_artifact_roots(
    roots: Sequence[tuple[str, Path]], *, threshold: float = 0.78, enforce_dimensions: bool = True
) -> tuple[dict[str, str], dict[str, object]]:
    signatures: dict[str, str] = {}
    fingerprints: dict[str, set[tuple[str, ...]]] = {}
    strongest: dict[str, object] = {"left": None, "right": None, "containment": 0.0}
    dimensions: dict[str, dict[str, str]] = {}
    pair_evidence: list[dict[str, object]] = []
    comparisons = 0
    for task_id, root in sorted(roots):
        parts = _artifact_parts(root)
        tokens = _normalized_code_tokens(
            parts["docs"] + parts["api"] + parts["reference"] + parts["visible"] + parts["hidden"]
        )
        grams = _ngrams(tokens)
        signatures[task_id] = _sha_bytes(" ".join(tokens).encode())
        dimensions[task_id] = {
            "public_api": _dimension_hash(parts["api"]),
            "state_algorithm": _dimension_hash(parts["api"] + parts["reference"]),
            "mutation_selection": _projected_dimension_hash(
                parts["reference"], MUTATION_SELECTION_TOKENS
            ),
            "invalid_boundary": _dimension_hash(parts["docs"] + parts["visible"] + parts["hidden"]),
            "control_flow": _projected_dimension_hash(parts["reference"], CONTROL_FLOW_TOKENS),
            "deterministic_oracle": _dimension_hash(parts["visible"] + parts["hidden"]),
            "topic_negative_fixture": _dimension_hash(parts["negative"]),
        }
        for other, other_grams in fingerprints.items():
            comparisons += 1
            denominator = min(len(grams), len(other_grams))
            similarity = len(grams & other_grams) / denominator if denominator else 1.0
            differing = sorted(
                name
                for name, value in dimensions[task_id].items()
                if value != dimensions[other][name]
            )
            required = {
                "public_api",
                "state_algorithm",
                "mutation_selection",
                "invalid_boundary",
                "control_flow",
                "deterministic_oracle",
                "topic_negative_fixture",
            }
            if enforce_dimensions and not required.issubset(differing):
                same = sorted(required - set(differing))
                _fail("hard_rule_pair_not_distinct", f"{other} vs {task_id}: {same}")
            pair_evidence.append(
                {
                    "left": other,
                    "right": task_id,
                    "differing_dimensions": differing,
                    "containment": round(similarity, 6),
                }
            )
            if similarity > float(strongest["containment"]):
                strongest = {
                    "left": other,
                    "right": task_id,
                    "containment": round(similarity, 6),
                }
            if similarity >= threshold:
                _fail(
                    "duplicate_family",
                    f"emitted {task_id} resembles {other}: {similarity:.3f}",
                )
        fingerprints[task_id] = grams
    expected = len(roots) * (len(roots) - 1) // 2
    if comparisons != expected:
        _fail("duplicate_family", f"all-pairs incomplete: {comparisons} != {expected}")
    return signatures, {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "comparison_scope": "emitted docs, public API, reference, visible and hidden tests",
        "pair_count": comparisons,
        "threshold": threshold,
        "strongest": strongest,
        "dimension_hashes": dimensions,
        "pair_evidence": pair_evidence,
        "negative_fixtures_excluded_from_similarity": True,
    }


def _verify_emitted_mechanism(root: Path, case: SlidingCase) -> None:
    parts = _artifact_parts(root)
    mechanism_source = parts["api"] + "\n" + parts["reference"]
    if case.marker not in mechanism_source or any(
        token not in mechanism_source for token in case.required_tokens
    ):
        _fail("invariant_not_enforced", f"emitted artifact lacks mechanism: {case.task_id}")


def _artifact_family_screen(out: Path) -> tuple[dict[str, str], dict[str, object]]:
    for case in CASES:
        _verify_emitted_mechanism(out / case.task_id, case)
        parts = _artifact_parts(out / case.task_id)
        if case.task_id in TRACE_SNIPPETS:
            hidden = parts["hidden"]
            if f"hard_rule_trace:{case.task_id}" not in hidden:
                _fail("deterministic_trace_missing", case.task_id)
            for operation in TRACE_OPERATION_TOKENS[case.task_id]:
                if operation not in hidden:
                    _fail("deterministic_trace_incomplete", f"{case.task_id}: {operation}")
    return _screen_artifact_roots([(case.task_id, out / case.task_id) for case in CASES])


def _replace_emitted_text(root: Path, old: str, new: str) -> None:
    changed = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path == root / ".meta/config.json":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if old in content:
            path.write_text(content.replace(old, new), encoding="utf-8")
            changed += 1
    if changed == 0:
        _fail("adversarial_control_invalid", f"{old!r} absent")


def _run_adversarial_controls(out: Path) -> dict[str, str]:
    base = CASES[0]
    outcomes: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="sliding-window-emitted-controls-") as temporary:
        temporary_root = Path(temporary)
        for name in ("renamed-domain-clone", "constants-policy-clone", "opposite-end-clone"):
            shutil.copytree(out / base.task_id, temporary_root / name)
        shutil.copytree(out / base.task_id, temporary_root / "missing-mechanism-token")
        _replace_emitted_text(temporary_root / "renamed-domain-clone", "Trade", "Quote")
        _replace_emitted_text(temporary_root / "renamed-domain-clone", "trade", "quote")
        _replace_emitted_text(temporary_root / "constants-policy-clone", "width == 0", "width == 00")
        _replace_emitted_text(
            temporary_root / "opposite-end-clone", "candidates.front()", "candidates.back()"
        )
        for name in ("renamed-domain-clone", "constants-policy-clone", "opposite-end-clone"):
            try:
                _screen_artifact_roots(
                    [(base.task_id, out / base.task_id), (name, temporary_root / name)],
                    enforce_dimensions=False,
                )
            except RuntimeError as error:
                if "duplicate_family" not in str(error):
                    raise
                outcomes[name] = "rejected:duplicate_family:emitted_artifacts"
            else:
                _fail("duplicate_family", f"emitted adversarial control passed: {name}")
        _replace_emitted_text(
            temporary_root / "missing-mechanism-token",
            base.required_tokens[0],
            "never_present_token",
        )
        try:
            _verify_emitted_mechanism(temporary_root / "missing-mechanism-token", base)
        except RuntimeError as error:
            if "invariant_not_enforced" not in str(error):
                raise
            outcomes["missing-mechanism-token"] = (
                "rejected:invariant_not_enforced:emitted_artifacts"
            )
        else:
            _fail("invariant_not_enforced", "emitted missing-mechanism control passed")
    return outcomes


def _semantic_holdout_screen(holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    if not holdout_root.is_dir():
        _fail("benchmark_screen_not_completed", str(holdout_root))
    holdouts: dict[str, set[tuple[str, ...]]] = {}
    inventory = hashlib.sha256()
    for root in sorted(path for path in holdout_root.iterdir() if path.is_dir()):
        corpus = ""
        for path in sorted(
            p
            for p in root.rglob("*")
            if p.is_file() and p.suffix in {".h", ".hpp", ".cpp"} and "catch" not in p.name
        ):
            inventory.update(path.relative_to(holdout_root).as_posix().encode())
            inventory.update(path.read_bytes())
            corpus += "\n" + path.read_text(encoding="utf-8", errors="replace")
        holdouts[root.name] = _ngrams(_normalized_code_tokens(corpus))
    strongest: dict[str, object] = {"candidate": None, "holdout": None, "containment": 0.0}
    for case in CASES:
        candidate = _ngrams(
            _normalized_code_tokens(
                case.header + case.reference + case.visible_test + case.hidden_test
            )
        )
        for slug, grams in holdouts.items():
            denominator = min(len(candidate), len(grams))
            score = len(candidate & grams) / denominator if denominator else 0.0
            if score > float(strongest["containment"]):
                strongest = {
                    "candidate": case.task_id,
                    "holdout": slug,
                    "containment": round(score, 6),
                }
            if score >= 0.60:
                _fail("benchmark_content_overlap", f"{case.task_id} resembles {slug}: {score:.3f}")
    return {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "source_inventory": f"sha256:{inventory.hexdigest()}",
        "holdout_root_count": len(holdouts),
        "comparison_scope": "public API, reference, visible and hidden tests",
        "threshold": 0.60,
        "strongest": strongest,
    }


def _benchmark_screen(root: Path) -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.rglob("*")) if path.is_file()
    )
    normalized = corpus.lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", normalized):
            _fail("benchmark_id_overlap", slug)
    for forbidden in ("aider-ai/polyglot", "exercism c++ exercise"):
        if forbidden in normalized:
            _fail("benchmark_content_overlap", forbidden)


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    expected = {case.task_id for case in CASES}
    records = {path.stem: path for path in remedy.glob("*.json")} if remedy.is_dir() else {}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per replacement is required")
    for task_id, path in records.items():
        record = json.loads(path.read_text(encoding="utf-8"))
        spec = remedy / f"{task_id}.md"
        if record.get("disposition") != "replace" or not spec.is_file():
            _fail("remedy_disposition_conflict", task_id)
        text = spec.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if (
            -1 in positions
            or positions != sorted(positions)
            or record.get("remedy_spec_hash") != _sha_bytes(text.encode())
        ):
            _fail("remedy_spec_incomplete", task_id)


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {len(expected)} roots, found {len(actual)}")
    if require_remedy:
        _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="sliding-window-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    _semantic_signatures()
    signatures, artifact_family = _artifact_family_screen(out)
    controls = _run_adversarial_controls(out)
    holdout = _semantic_holdout_screen()
    manifest_tasks = []
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config["files"]
        solution = [_safe_relative(item) for item in files["solution"]]
        tests = [_safe_relative(item) for item in files["test"]]
        examples = [_safe_relative(item) for item in files["example"]]
        private_negative = root / ".meta/negative_fixture.cpp"
        if len(solution) != 2 or len(examples) != 2 or set(solution) & (set(tests) | set(examples)):
            _fail("reference_map_failed", case.task_id)
        if not private_negative.is_file() or ".meta/negative_fixture.cpp" in {
            *solution,
            *tests,
            *examples,
        }:
            _fail("negative_fixture_role_leak", case.task_id)
        old, new, _ = NEGATIVE_MUTATIONS[case.task_id]
        emitted_reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        if emitted_reference.count(old) != 1:
            _fail("negative_fixture_ambiguous", case.task_id)
        expected_negative = emitted_reference.replace(old, new, 1)
        if private_negative.read_text(encoding="utf-8") != expected_negative:
            _fail("negative_fixture_drift", case.task_id)
        if any(
            name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution
        ):
            _fail("unsafe_path", case.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("reference_map_failed", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        if any(
            name in prompt
            for name in [
                *tests,
                *examples,
                "CMakeLists.txt",
                ".meta/provenance.json",
                ".meta/task_hidden_test.cpp",
            ]
        ):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer) is not None:
            _fail("target_reference_mismatch", case.task_id)
        malformed = (
            f"{task.editable_files[0]}\n```cpp\n// missing\n```\n",
            answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n",
            "prose\n" + answer,
        )
        if any(_whole_format_code(root, value) != "whole_format_failed" for value in malformed):
            _fail("whole_format_failed", case.task_id)
        _benchmark_screen(root)
        manifest_tasks.append(
            {
                "task_id": case.task_id,
                "legacy_task_id": case.legacy_id,
                "tree_hash": _tree_hash(root),
                "semantic_profile": case.profile,
                "semantic_signature": signatures[case.task_id],
                "negative_fixture_hash": _source_hash(private_negative),
                "deterministic_trace": (
                    "operation_complete" if case.task_id in TRACE_SNIPPETS else "not_stateful"
                ),
                "primary_core_objective": "achieved",
            }
        )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "task_count": len(CASES),
        "owner_hash": _source_hash(),
        "status": "pending_execution",
        "tasks": manifest_tasks,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "emitted_adversarial_controls": controls,
            "compiled_negative_fixtures": "pending_docker_execution",
            "duplicate_family": "pass",
            "artifact_family": artifact_family,
            "benchmark_contamination": "pass",
            "semantic_holdout": holdout,
        },
    }
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    _sync_remedies(
        out,
        status="pending_execution",
        primary_core_objective="achieved",
        prompt_boundary="pass",
        reference_mapping="pass",
        family_screen=artifact_family,
        benchmark_screen="pass",
        semantic_holdout_screen=holdout,
        emitted_adversarial_controls=controls,
        compiled_negative_fixtures="pending_docker_execution",
        strongest_local_status="semantically_admitted",
    )


def _deterministic_archive(out: Path, destination: Path) -> str:
    with tarfile.open(destination, "w") as archive:
        for case in sorted(CASES, key=lambda item: item.task_id):
            root = out / case.task_id
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                relative = Path(case.task_id) / path.relative_to(root)
                info = tarfile.TarInfo(relative.as_posix())
                data = path.read_bytes()
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return _sha_bytes(destination.read_bytes())


def verify_docker(out: Path, image: str = SANITY_IMAGE) -> None:
    verify_core(out)
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if inspect.returncode:
        _fail("docker_sanity_not_completed", inspect.stderr.strip())
    image_id = inspect.stdout.strip()
    with tempfile.TemporaryDirectory(prefix="sliding-window-docker-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        digest_helper = temp / "tree_digest.py"
        results = temp / "results"
        results.mkdir()
        archive_hash = _deterministic_archive(out, archive)
        digest_helper.write_text(TREE_DIGEST_HELPER, encoding="utf-8")
        runner = r"""set -eu
mkdir -p /tmp/family
tar -xf /input/family.tar -C /tmp/family
: > /result/counts.tsv
compiler_path=$(command -v c++)
readlink -f "$compiler_path" > /result/compiler-path.txt
"$compiler_path" --version | head -1 > /result/compiler.txt
sha256sum "$(readlink -f "$compiler_path")" | awk '{print "sha256:" $1}' > /result/compiler.sha256
cmake --version | head -1 > /result/cmake.txt
python3 /input/tree_digest.py
for root in /tmp/family/*; do
  task=$(basename "$root")
  for mode in normal sanitizer; do
    build="/tmp/build-${task}-${mode}"
    if [ "$mode" = sanitizer ]; then
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER="$compiler_path" -DTASK_SOURCE="$root/.meta/example.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"
    else
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER="$compiler_path" -DTASK_SOURCE="$root/.meta/example.cpp"
    fi
    cmake --build "$build" --parallel 2
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
    test -n "$count" && test "$count" -gt 0
    ctest --test-dir "$build" --output-on-failure
    printf '%s\t%s\t%s\n' "$task" "$mode" "$count" >> /result/counts.tsv
  done
  negative_build="/tmp/build-${task}-negative"
  cmake -S "$root" -B "$negative_build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER="$compiler_path" -DTASK_SOURCE="$root/.meta/negative_fixture.cpp"
  cmake --build "$negative_build" --parallel 2
  negative_count=$(ctest --test-dir "$negative_build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  test -n "$negative_count" && test "$negative_count" -gt 0
  set +e
  ctest --test-dir "$negative_build" --output-on-failure > "/result/${task}-negative.log" 2>&1
  negative_rc=$?
  set -e
  test "$negative_rc" -ne 0
  negative_log_hash=$(sha256sum "/result/${task}-negative.log" | awk '{print "sha256:" $1}')
  printf '%s\tnegative\t%s\t%s\t%s\n' "$task" "$negative_count" "$negative_rc" "$negative_log_hash" >> /result/counts.tsv
done
sha256sum /input/family.tar | awk '{print "sha256:" $1}' > /result/archive.sha256
"""
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--mount",
            f"type=bind,src={archive},dst=/input/family.tar,readonly",
            "--mount",
            f"type=bind,src={digest_helper},dst=/input/tree_digest.py,readonly",
            "--mount",
            f"type=bind,src={results},dst=/result",
            image,
            "sh",
            "-lc",
            runner,
        ]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if run.returncode:
            _fail("docker_sanity_failed", run.stdout[-4000:])
        mounted_hash = (results / "archive.sha256").read_text(encoding="utf-8").strip()
        if mounted_hash != archive_hash:
            _fail("grader_mount_hash_mismatch", f"owner={archive_hash} docker={mounted_hash}")
        mounted_tree_hashes: dict[str, str] = {}
        for line in (results / "tree-digests.tsv").read_text(encoding="utf-8").splitlines():
            task_id, digest = line.split("\t")
            mounted_tree_hashes[task_id] = digest
        owner_tree_hashes = {case.task_id: _tree_hash(out / case.task_id) for case in CASES}
        if mounted_tree_hashes != owner_tree_hashes:
            _fail(
                "grader_mount_tree_hash_mismatch",
                f"owner={owner_tree_hashes} docker={mounted_tree_hashes}",
            )
        counts: dict[str, dict[str, int]] = {}
        negative_results: dict[str, dict[str, object]] = {}
        for line in (results / "counts.tsv").read_text(encoding="utf-8").splitlines():
            fields = line.split("\t")
            task_id, mode, raw = fields[:3]
            if mode == "negative":
                negative_results[task_id] = {
                    "discovered_tests": int(raw),
                    "test_returncode": int(fields[3]),
                    "log_hash": fields[4],
                    "strict_compile": "pass",
                    "designated_tests": "rejected_false_substitute",
                }
            else:
                counts.setdefault(task_id, {})[mode] = int(raw)
        if set(counts) != {case.task_id for case in CASES}:
            _fail("test_discovery_failed", "incomplete Docker receipt")
        for task_id, modes in counts.items():
            if modes.get("normal", 0) <= 0 or modes.get("normal") != modes.get("sanitizer"):
                _fail("sanitizer_test_count_mismatch", task_id)
        if set(negative_results) != {case.task_id for case in CASES}:
            _fail("negative_fixture_execution_incomplete", "incomplete Docker negative receipt")
        for task_id, result in negative_results.items():
            if result["discovered_tests"] != counts[task_id]["normal"] or int(
                result["test_returncode"]
            ) == 0:
                _fail("negative_fixture_not_rejected", task_id)
        receipt = {
            "schema_version": "aider-sliding-window-docker-sanity-v3",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "image_id": image_id,
            "archive_hash": archive_hash,
            "owner_hash": _source_hash(),
            "family_tree_hashes": owner_tree_hashes,
            "mounted_family_tree_hashes": mounted_tree_hashes,
            "reference_hashes": {
                case.task_id: _source_hash(out / case.task_id / ".meta/example.cpp")
                for case in CASES
            },
            "compiler": (results / "compiler.txt").read_text(encoding="utf-8").strip(),
            "compiler_path": (results / "compiler-path.txt").read_text(encoding="utf-8").strip(),
            "compiler_hash": (results / "compiler.sha256").read_text(encoding="utf-8").strip(),
            "cmake": (results / "cmake.txt").read_text(encoding="utf-8").strip(),
            "commands": {
                "docker": command[:8] + [image, "sh", "-lc", "<owner-controlled-runner>"],
                "normal": "fresh Unix Makefiles reference build and ctest",
                "sanitizer": "fresh ASan/UBSan Unix Makefiles reference build and ctest",
                "negative": "fresh strict Unix Makefiles false-substitute build; CTest must reject",
            },
            "test_counts": counts,
            "negative_fixture_results": negative_results,
        }
        receipt_path = out / ".state/oracle-receipt.json"
        _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        receipt_hash = _source_hash(receipt_path)
        _sync_remedies(
            out,
            status="verified",
            oracle_evidence={
                "status": "pass",
                "evidence_class": "docker_sanity",
                "locked_oracle": False,
                "receipt_path": ".state/oracle-receipt.json",
                "receipt_hash": receipt_hash,
                "image": image_id,
                "network": "none",
                "normal_discovered_tests": 2,
                "sanitizer_discovered_tests": 2,
                "negative_compiled_fixtures": len(negative_results),
                "negative_rejected_fixtures": len(negative_results),
            },
            strongest_local_status="local_family_verified",
        )
        manifest_path = out / ".state/materialization-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update(
            {
                "status": "local_family_verified",
                "oracle_receipt": ".state/oracle-receipt.json",
                "oracle_receipt_hash": receipt_hash,
                "evidence_class": "docker_sanity",
                "locked_oracle": False,
            }
        )
        manifest["screen"]["compiled_negative_fixtures"] = {
            "status": "pass",
            "compiled": len(negative_results),
            "rejected": len(negative_results),
            "receipt_path": ".state/oracle-receipt.json",
        }
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-docker", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_docker:
        verify_docker(args.out, args.image)
    print(
        f"Wrote {len(roots)} algorithmically distinct sliding-window-maximum replacements under {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
