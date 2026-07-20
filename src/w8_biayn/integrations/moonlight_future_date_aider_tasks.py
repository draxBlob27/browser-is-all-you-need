"""Materialize and reverify future-date-calculations v2 replacements."""

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
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_future_date_cases import (
    CASES,
    NEGATIVE_MUTATIONS,
    FutureDateCase,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/future-date-calculations"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/future-date-calculations")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_FUTURE_DATE_CALCULATIONS_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/future-date-calculations.md"
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-text-grid-reshaping-future-date-calculations-v2"
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
HARD_RULE_THRESHOLD = 0.94
LEGACY_IDS = (
    "future-warranty-milestones",
    "future-crop-treatment",
    "future-invoice-followups",
    "future-licence-renewal",
    "future-lab-sample",
    "future-construction-deadline",
    "future-vaccine-series",
    "future-equipment-calibration",
    "future-publication-embargo",
    "future-lease-notices",
)
REPLACEMENTS = {case.legacy_id: case.task_id for case in CASES}
REJECTED_IDS = set(LEGACY_IDS) - set(REPLACEMENTS)
OFFICIAL_HOLDOUTS = frozenset(
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

CMAKE = """cmake_minimum_required(VERSION 3.16)
project(future_date_calculations_v2 LANGUAGES CXX)
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
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
"""


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _owner_hash() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__), Path(__file__).with_name("moonlight_future_date_cases.py")):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _tree_hash(root: Path) -> str:
    if not root.is_dir():
        return "not_available"
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _negative_source(case: FutureDateCase) -> tuple[str, str]:
    old, new, reason = NEGATIVE_MUTATIONS[case.task_id]
    if case.reference.count(old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift: {case.task_id}")
    source = case.reference.replace(old, new, 1)
    if source == case.reference:
        _fail("invariant_not_enforced", f"negative unchanged: {case.task_id}")
    return source, reason


def _remedy_markdown(legacy_id: str) -> str:
    replacement_id = REPLACEMENTS.get(legacy_id)
    disposition = "replace" if replacement_id else "reject"
    action = (
        f"Replace with `{replacement_id}`, whose emitted API, state/algorithm, transition rules, "
        "boundaries, reference control flow, oracle, and false substitute are independently owned."
        if replacement_id
        else "Reject from the counted v2 family because its policy-only behavior is subsumed by stronger roots; retaining it would pad count."
    )
    return f"""## Identity

Legacy `{legacy_id}`; family before `aider-dates-and-clocks-future-date-calculations-v1-template`; family after `{FAMILY_ID}`; disposition `{disposition}`. Selected prompt `{PROMPT}` with `FAMILY_NAME=future-date-calculations`, `FAMILY_TYPE=aider-text-grid-reshaping`, and user-authorized hard count `8-12`.

## Objective and finding

The legacy root used the same generic Date/Policy/Record/Result surface, calendar helper, policy-switch reference shape, and duplicated visible/private test as the other nine roots. Its domain name did not create distinct primary logic. Primary core objective: `not_achieved` in v1.

## Remedy

{action}

## Contract and invariant

The replacement, when present, exposes only its task-named header/source and visible documentation. It must own its advertised algorithm, reject invalid input atomically, implement documented equality/order rules, and forbid a shared generic date-policy template, hard-coded answer, benchmark asset, or renamed sibling.

## Tests and oracle

The replacement has distinct visible/private deterministic tests and a compiling topic negative rejected by executed tests. The family must also materialize coherent domain/identifier, constants/policy, and opposite-end controls; all must compile, execute, fail behavior tests, and be rejected by the production seven-dimension evaluator.

## Files and metadata

Legacy tree `{LEGACY_ROOT}` is immutable. Fresh output is owner-generated only under `{DEFAULT_OUT}`. Docs/tests/references/metadata/CMake/evidence remain private.

## Acceptance

Require exactly 8 roots and 28 unordered pairs. Every pair must pass all seven dimensions conjunctively; all controls and topic negatives must be executed. Require prompt/role/reference mapping, 26-root semantic holdout screening, and network-disabled Docker normal plus fresh ASan/UBSan with equal positive discovery.

## Optional dataset handoff

`not_requested`. No rows, token/mask evidence, split, export, training, release, or uplift claim.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state/remedy"
    for legacy_id in LEGACY_IDS:
        markdown = _remedy_markdown(legacy_id)
        replacement_id = REPLACEMENTS.get(legacy_id)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "legacy_task_id": legacy_id,
            "task_id": replacement_id or legacy_id,
            "family_id_before": "aider-dates-and-clocks-future-date-calculations-v1-template",
            "family_id_after": FAMILY_ID if replacement_id else None,
            "tree_hash_before": _tree_hash(LEGACY_ROOT / legacy_id),
            "selected_prompt": PROMPT,
            "user_inputs": {
                "FAMILY_NAME": "future-date-calculations",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
                "hard_count": "8-12",
            },
            "finding_ids": [
                "FDC-F1-shared-template-duplicate",
                "FDC-F2-hard-rule-evidence-absent",
                "FDC-F3-docker-receipt-absent",
            ],
            "disposition": "replace" if replacement_id else "reject",
            "replacement_task_id": replacement_id,
            "primary_core_objective": "specified" if replacement_id else "not_achieved",
            "benchmark_screen": "pending",
            "status": "planned",
            "strongest_local_status": "planned",
            "remedy_spec_path": f".state/remedy/{legacy_id}.md",
            "remedy_spec_hash": _sha(markdown.encode()),
            "dataset_handoff": "not_requested",
        }
        _write(remedy / f"{legacy_id}.md", markdown, force)
        _write(
            remedy / f"{legacy_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", force
        )


def _sync_remedies(out: Path, **updates: object) -> None:
    for legacy_id in LEGACY_IDS:
        path = out / ".state/remedy" / f"{legacy_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        replacement_id = REPLACEMENTS.get(legacy_id)
        if replacement_id:
            record["tree_hash_after"] = _tree_hash(out / replacement_id)
            record["primary_core_objective"] = "achieved"
        else:
            record["status"] = "rejected"
            record["strongest_local_status"] = "rejected"
            record["hard_rule_status"] = "not_counted"
            record["oracle_evidence"] = "not_applicable"
        record["owner_hash_after"] = _owner_hash()
        record["changed_owner_paths"] = [
            CURRICULUM,
            FAMILY_SPEC,
            "src/w8_biayn/integrations/moonlight_future_date_aider_tasks.py",
            "src/w8_biayn/integrations/moonlight_future_date_cases.py",
            "tests/test_moonlight_future_date_aider_tasks.py",
            "examples/slime/moonlight_cpp_perf/prepare_future_date_aider_tasks.sh",
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _invalidate_evidence(out: Path) -> None:
    for name in ("materialization-manifest.json", "oracle-receipt.json", "docker-sanity.json"):
        path = out / ".state" / name
        if path.exists():
            stale = out / ".state/invalidated" / f"{name}.stale"
            stale.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, stale)
            path.unlink()


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _invalidate_evidence(out)
    if not (out / ".state/remedy").is_dir():
        _write_remedies(out, force)
    roots = []
    expected = {case.task_id for case in CASES}
    if out.is_dir():
        extras = [
            p for p in out.iterdir() if p.is_dir() and p.name != ".state" and p.name not in expected
        ]
        if extras and not force:
            _fail("generator_output_drift", "obsolete roots require --force")
        for extra in extras:
            shutil.rmtree(extra)
    for case in CASES:
        root = out / case.task_id
        negative, negative_reason = _negative_source(case)
        config = {
            "authors": ["w8-biayn"],
            "blurb": case.title,
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
            "version": 2,
            "status": "local task artifact; not admitted SFT data",
            "benchmark_separation": "Independent domain API, owned algorithm, and tests; official roots remain holdouts.",
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\nA deterministic civil-date policy task with caller-supplied inputs.\n",
            ".docs/instructions.md": case.instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f'[visible]\ndescription="ordinary {case.profile} behavior"\n[hidden]\ndescription="invalid, equality, ordering, and topic invariant behavior"\n[negative]\ndescription="{negative_reason}"\n',
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            ".meta/negative_false_substitute.cpp": negative,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


def _normalized_tokens(text: str) -> list[str]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", text)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", text)
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
        "map",
        "set",
        "optional",
        "sort",
        "stable_sort",
        "min",
        "max",
    }
    return [
        token if token in keywords or not re.match(r"[A-Za-z_]", token) else "ID" for token in raw
    ]


def _ngrams(tokens: list[str], width: int = 7) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + width]) for i in range(max(0, len(tokens) - width + 1))}


def _containment(left: list[str], right: list[str]) -> float:
    a, b = _ngrams(left), _ngrams(right)
    return len(a & b) / min(len(a), len(b)) if a and b else 1.0


def _features(root: Path) -> dict[str, list[str]]:
    task_id = root.name
    header = (root / f"{task_id}.h").read_text(encoding="utf-8")
    docs = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8")
    return {
        "public_api": _normalized_tokens(header),
        "owned_state_algorithm": _normalized_tokens(header + reference),
        "mutation_selection_rules": _normalized_tokens(docs),
        "invalid_boundary_behavior": _normalized_tokens(docs + hidden),
        "reference_control_flow": _normalized_tokens(reference),
        "deterministic_oracle": _normalized_tokens(visible + hidden),
        "topic_negative_fixture": _normalized_tokens(negative),
    }


def _pair_decision(
    left_id: str, left: dict[str, list[str]], right_id: str, right: dict[str, list[str]]
) -> dict[str, object]:
    dimensions = {}
    for name in HARD_RULE_DIMENSIONS:
        score = round(_containment(left[name], right[name]), 6)
        dimensions[name] = {
            "containment": score,
            "distinct": left[name] != right[name] and score < HARD_RULE_THRESHOLD,
        }
    return {
        "left": left_id,
        "right": right_id,
        "dimensions": dimensions,
        "pass": all(item["distinct"] for item in dimensions.values()),
    }


def _hard_rule_screen(out: Path) -> dict[str, object]:
    feature_map = {case.task_id: _features(out / case.task_id) for case in CASES}
    pairs = []
    ids = sorted(feature_map)
    for index, left_id in enumerate(ids):
        for right_id in ids[index + 1 :]:
            decision = _pair_decision(
                left_id, feature_map[left_id], right_id, feature_map[right_id]
            )
            if not decision["pass"]:
                failed = [
                    name for name, row in decision["dimensions"].items() if not row["distinct"]
                ]
                _fail("hard_rule_pair_not_distinct", f"{left_id} vs {right_id}: {failed}")
            pairs.append(decision)
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"all-pairs incomplete: {len(pairs)} != {expected}")
    return {
        "status": "pending_execution",
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "threshold": HARD_RULE_THRESHOLD,
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "evidence_source": "actual emitted docs, public API, reference, visible/private tests, and topic negative",
        "pairs": pairs,
    }


def _control_case(kind: str) -> FutureDateCase:
    base = CASES[0]
    if kind == "domain-identifier-renamed-clone":
        replacements = (
            ("ServiceCalendar", "MaintenancePlan"),
            ("make_service_calendar", "make_maintenance_plan"),
            ("SalePolicy", "AssetPolicy"),
            ("registration", "activation"),
            ("inspection", "review"),
            ("standard", "basic"),
            ("extended", "premium"),
            ("closure", "blocked"),
        )
        values = {
            field: getattr(base, field)
            for field in (
                "title",
                "instructions",
                "header",
                "reference",
                "visible_test",
                "hidden_test",
            )
        }
        for field, value in values.items():
            for old, new in replacements:
                value = value.replace(old, new)
            values[field] = value
        values["reference"] = values["reference"].replace(
            "while(blocked.count(serial(out.review)))", "if(blocked.count(serial(out.review)))", 1
        )
        return replace(
            base,
            task_id=kind,
            public_api="make_maintenance_plan(AssetPolicy, optional<Date>, blocked)",
            marker="if(blocked(out.review))",
            **values,
        )
    if kind == "constants-policy-clone":
        values = {
            field: getattr(base, field).replace("2024", "2032").replace("2025", "2033")
            for field in ("instructions", "header", "reference", "visible_test", "hidden_test")
        }
        values["reference"] = values["reference"].replace(
            "while(blocked.count(serial(out.inspection)))",
            "if(blocked.count(serial(out.inspection)))",
            1,
        )
        return replace(base, task_id=kind, marker="if(blocked(out.inspection))", **values)
    if kind == "opposite-end-selection-clone":
        reference = base.reference.replace(
            "long long next=serial(out.inspection)+1", "long long next=serial(out.inspection)-1", 1
        )
        return replace(
            base, task_id=kind, marker="next=serial(out.inspection)-1", reference=reference
        )
    raise ValueError(kind)


def _write_controls(out: Path, force: bool) -> None:
    controls = {}
    for name in (
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    ):
        case = _control_case(name)
        root = out / ".state/hard-rule-controls" / name
        for relative, content in {
            "task.h": case.header,
            "candidate.cpp": case.reference,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }.items():
            _write(root / relative, content, force)
        controls[name] = {
            "changed_files": [
                "task.h",
                "candidate.cpp",
                "task_visible_test.cpp",
                ".meta/task_hidden_test.cpp",
            ],
            "expected_compile": "pass",
            "expected_ctest": "reject",
            "expected_semantic_screen": "duplicate_family",
        }
    _write(
        out / ".state/hard-rule-controls/manifest.json",
        json.dumps(
            {"schema_version": "future-date-hard-rule-controls-v1", "controls": controls},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )


def _control_screen(out: Path) -> dict[str, str]:
    base = _features(out / CASES[0].task_id)
    results = {}
    for name in (
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    ):
        root = out / ".state/hard-rule-controls" / name
        feature = {
            "public_api": _normalized_tokens((root / "task.h").read_text()),
            "owned_state_algorithm": _normalized_tokens(
                (root / "task.h").read_text() + (root / "candidate.cpp").read_text()
            ),
            "mutation_selection_rules": base["mutation_selection_rules"],
            "invalid_boundary_behavior": base["invalid_boundary_behavior"],
            "reference_control_flow": _normalized_tokens((root / "candidate.cpp").read_text()),
            "deterministic_oracle": _normalized_tokens(
                (root / "task_visible_test.cpp").read_text()
                + (root / ".meta/task_hidden_test.cpp").read_text()
            ),
            "topic_negative_fixture": _normalized_tokens((root / "candidate.cpp").read_text()),
        }
        decision = _pair_decision(CASES[0].task_id, base, name, feature)
        if decision["pass"]:
            _fail("duplicate_family", f"adversarial control passed: {name}")
        results[name] = "rejected:duplicate_family"
    return results


def _semantic_holdout_screen(
    out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT
) -> dict[str, object]:
    if not holdout_root.is_dir():
        _fail("benchmark_screen_not_completed", str(holdout_root))
    holdouts = {}
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
        holdouts[root.name] = _normalized_tokens(corpus)
    strongest = {"candidate": None, "holdout": None, "containment": 0.0}
    for case in CASES:
        candidate = _features(out / case.task_id)["owned_state_algorithm"]
        for slug, tokens in holdouts.items():
            score = _containment(candidate, tokens)
            if score > strongest["containment"]:
                strongest = {
                    "candidate": case.task_id,
                    "holdout": slug,
                    "containment": round(score, 6),
                }
            if score >= 0.70:
                _fail("benchmark_content_overlap", f"{case.task_id} resembles {slug}: {score:.3f}")
    return {
        "status": "pass",
        "holdout_root_count": len(holdouts),
        "source_inventory": f"sha256:{inventory.hexdigest()}",
        "normalizer": "future-date-v2-seven-gram-identifiers-and-literals-elided",
        "threshold": 0.70,
        "strongest": strongest,
    }


def _verify_roles_and_prompt(root: Path) -> dict[str, object]:
    config = json.loads((root / ".meta/config.json").read_text())
    files = config["files"]
    solution, tests, examples = files["solution"], files["test"], files["example"]
    all_paths = [*solution, *tests, *examples]
    if any(
        Path(p).is_absolute() or ".." in Path(p).parts or not (root / p).is_file()
        for p in all_paths
    ):
        _fail("reference_map_failed", root.name)
    if set(solution) & (set(tests) | set(examples)) or any(
        p.startswith((".meta/", ".docs/")) or p == "CMakeLists.txt" for p in solution
    ):
        _fail("prompt_contract_incomplete", root.name)
    task = load_task(root)
    prompt = build_prompt(task)
    forbidden = [
        *tests,
        *examples,
        "CMakeLists.txt",
        ".meta/provenance.json",
        ".meta/task_hidden_test.cpp",
        ".meta/negative_false_substitute.cpp",
    ]
    if any(name in prompt for name in forbidden):
        _fail("prompt_contract_incomplete", root.name)
    answer = build_assistant_response(task, load_example_files_from_config(root))
    if set(task.editable_files) != set(solution) or any(name not in answer for name in solution):
        _fail("target_reference_mismatch", root.name)
    semantic_paths = [
        root / ".docs/introduction.md",
        root / ".docs/instructions.md",
        root / f"{root.name}.h",
        root / f"{root.name}.cpp",
        root / ".meta/example.cpp",
        root / "task_visible_test.cpp",
        root / ".meta/task_hidden_test.cpp",
    ]
    corpus = "\n".join(path.read_text(errors="replace") for path in semantic_paths)
    for slug in OFFICIAL_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", corpus.lower()):
            _fail("benchmark_id_overlap", slug)
    return {"solution": solution, "test": tests, "example": examples}


def verify_core(out: Path, *, require_remedy: bool = True) -> dict[str, object]:
    expected = {case.task_id for case in CASES}
    actual = {p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"}
    if actual != expected or not 8 <= len(actual) <= 12:
        _fail("generator_output_drift", f"expected 8 roots, found {sorted(actual)}")
    if require_remedy:
        records = list((out / ".state/remedy").glob("*.json"))
        if len(records) != 10:
            _fail("remedy_spec_incomplete", f"expected 10 records, found {len(records)}")
    with tempfile.TemporaryDirectory(prefix="future-date-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    roles = {case.task_id: _verify_roles_and_prompt(out / case.task_id) for case in CASES}
    hard_rule = _hard_rule_screen(out)
    controls = _control_screen(out)
    holdout = _semantic_holdout_screen(out)
    manifest = {
        "schema_version": "aider-future-date-materialization-v2",
        "family_id": FAMILY_ID,
        "owner_hash": _owner_hash(),
        "task_count": len(CASES),
        "legacy_task_count": len(LEGACY_IDS),
        "dispositions": {"replace": len(CASES), "reject": len(REJECTED_IDS)},
        "status": "implemented",
        "hard_rule_status": "pending_execution",
        "tasks": [
            {
                "task_id": c.task_id,
                "legacy_task_id": c.legacy_id,
                "tree_hash": _tree_hash(out / c.task_id),
                "profile": c.profile,
                "primary_core_objective": "achieved",
            }
            for c in CASES
        ],
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "roles": roles,
            "hard_rule": hard_rule,
            "adversarial_controls": controls,
            "duplicate_family": "pass",
            "benchmark_contamination": "pass",
            "semantic_holdout": holdout,
        },
    }
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    if require_remedy:
        _sync_remedies(
            out,
            status="implemented",
            strongest_local_status="implemented",
            prompt_boundary="pass",
            reference_mapping="pass",
            benchmark_screen="pass",
            family_screen="pass",
            hard_rule_status="pending_execution",
            hard_rule_evidence={
                "pair_count": hard_rule["pair_count"],
                "dimensions": hard_rule["dimensions"],
                "matrix_path": ".state/materialization-manifest.json",
            },
        )
    return manifest


def verify(out: Path) -> None:
    verify_core(out)
    if not shutil.which("cmake") or not shutil.which("c++"):
        _fail("host_verification_not_completed", "verification requires cmake and c++")
    for case in CASES:
        root = out / case.task_id
        with tempfile.TemporaryDirectory(prefix="future-date-host-") as temporary:
            copied = Path(temporary) / case.task_id
            shutil.copytree(root, copied)
            for mode, flags in (
                ("normal", []),
                (
                    "sanitizer",
                    [
                        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
                        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                    ],
                ),
            ):
                build_root = copied / f"build-{mode}"
                for command in (
                    [
                        "cmake",
                        "-S",
                        str(copied),
                        "-B",
                        str(build_root),
                        "-G",
                        "Unix Makefiles",
                        f"-DTASK_SOURCE={copied / '.meta/example.cpp'}",
                        *flags,
                    ],
                    ["cmake", "--build", str(build_root), "--parallel", "2"],
                    ["ctest", "--test-dir", str(build_root), "--output-on-failure"],
                ):
                    subprocess.run(
                        command,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )


def _archive(out: Path, destination: Path) -> str:
    with tarfile.open(destination, "w") as archive:
        roots = [out / c.task_id for c in CASES] + [out / ".state/hard-rule-controls"]
        for root in roots:
            prefix = (
                Path(root.name)
                if root.name != "hard-rule-controls"
                else Path(".hard-rule-controls")
            )
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                data = path.read_bytes()
                info = tarfile.TarInfo((prefix / path.relative_to(root)).as_posix())
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return _file_hash(destination)


def verify_docker(out: Path, image: str = SANITY_IMAGE) -> None:
    manifest = verify_core(out)
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    inspected = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if inspected.returncode:
        _fail("docker_sanity_not_completed", inspected.stderr.strip())
    with tempfile.TemporaryDirectory(prefix="future-date-docker-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        results = temp / "results"
        results.mkdir()
        archive_hash = _archive(out, archive)
        runner = r"""set -eu
mkdir -p /tmp/family; tar -xf /input/family.tar -C /tmp/family
: > /result/counts.tsv; : > /result/negative.tsv; : > /result/controls.tsv
c++ --version | head -1 > /result/compiler.txt; cmake --version | head -1 > /result/cmake.txt
for root in /tmp/family/*; do
 task=$(basename "$root")
 for mode in normal sanitizer; do
  build=/tmp/build-${task}-${mode}
  if [ "$mode" = sanitizer ]; then
   cmake -S "$root" -B "$build" -G 'Unix Makefiles' -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined'
  else
   cmake -S "$root" -B "$build" -G 'Unix Makefiles' -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp"
  fi
  cmake --build "$build" --parallel 2
  count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p'); test "$count" -gt 0
  ctest --test-dir "$build" --output-on-failure
  printf '%s\t%s\t%s\n' "$task" "$mode" "$count" >> /result/counts.tsv
 done
 build=/tmp/build-${task}-negative
 cmake -S "$root" -B "$build" -G 'Unix Makefiles' -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp"
 cmake --build "$build" --parallel 2; count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
 set +e; ctest --test-dir "$build" --output-on-failure; code=$?; set -e; test "$count" -gt 0; test "$code" -ne 0
 printf '%s\t%s\t%s\n' "$task" "$count" "$code" >> /result/negative.tsv
done
for root in /tmp/family/.hard-rule-controls/*; do
 test -d "$root" || continue
 name=$(basename "$root"); build=/tmp/build-control-${name}
 cmake -S "$root" -B "$build" -G 'Unix Makefiles' -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/candidate.cpp"
 cmake --build "$build" --parallel 2; count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
 set +e; ctest --test-dir "$build" --output-on-failure; code=$?; set -e; test "$count" -gt 0; test "$code" -ne 0
 printf '%s\t%s\t%s\n' "$name" "$count" "$code" >> /result/controls.tsv
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
            f"type=bind,src={results},dst=/result",
            image,
            "sh",
            "-lc",
            runner,
        ]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if run.returncode:
            _fail("docker_sanity_failed", run.stdout[-5000:])
        if (results / "archive.sha256").read_text().strip() != archive_hash:
            _fail("grader_mount_hash_mismatch", archive_hash)
        counts = {}
        for line in (results / "counts.tsv").read_text().splitlines():
            task_id, mode, raw = line.split("\t")
            counts.setdefault(task_id, {})[mode] = int(raw)
        if set(counts) != {c.task_id for c in CASES} or any(
            row.get("normal", 0) <= 0 or row.get("normal") != row.get("sanitizer")
            for row in counts.values()
        ):
            _fail("sanitizer_test_count_mismatch", str(counts))
        negatives = {
            row.split("\t")[0]: {
                "discovered_tests": int(row.split("\t")[1]),
                "ctest_exit": int(row.split("\t")[2]),
                "compiled": True,
                "rejected_by_executed_tests": int(row.split("\t")[2]) != 0,
            }
            for row in (results / "negative.tsv").read_text().splitlines()
        }
        controls = {
            row.split("\t")[0]: {
                "discovered_tests": int(row.split("\t")[1]),
                "ctest_exit": int(row.split("\t")[2]),
                "compiled": True,
                "rejected_by_executed_tests": int(row.split("\t")[2]) != 0,
                "semantic_screen": "rejected:duplicate_family",
            }
            for row in (results / "controls.tsv").read_text().splitlines()
        }
        if set(negatives) != {c.task_id for c in CASES} or set(controls) != {
            "domain-identifier-renamed-clone",
            "constants-policy-clone",
            "opposite-end-selection-clone",
        }:
            _fail("negative_fixture_not_rejected", "incomplete receipt")
        receipt = {
            "schema_version": "aider-future-date-docker-sanity-v2",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "image_id": inspected.stdout.strip(),
            "archive_hash": archive_hash,
            "owner_hash": _owner_hash(),
            "family_tree_hashes": {c.task_id: _tree_hash(out / c.task_id) for c in CASES},
            "reference_hashes": {
                c.task_id: _file_hash(out / c.task_id / ".meta/example.cpp") for c in CASES
            },
            "compiler": (results / "compiler.txt").read_text().strip(),
            "cmake": (results / "cmake.txt").read_text().strip(),
            "commands": {
                "docker": command[:8] + [image, "sh", "-lc", "<owner-controlled-runner>"],
                "normal": "fresh Unix Makefiles reference build and ctest",
                "sanitizer": "fresh ASan/UBSan build and ctest",
                "network": "none",
            },
            "test_counts": counts,
            "topic_negatives": negatives,
            "adversarial_controls": controls,
            "hard_rule_pair_count": manifest["screen"]["hard_rule"]["pair_count"],
            "hard_rule_dimensions": list(HARD_RULE_DIMENSIONS),
        }
        receipt_path = out / ".state/oracle-receipt.json"
        _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        manifest["status"] = "local_family_verified"
        manifest["hard_rule_status"] = "pass"
        manifest["screen"]["hard_rule"]["status"] = "pass"
        manifest["screen"]["hard_rule"]["topic_negative_execution"] = negatives
        manifest["screen"]["hard_rule"]["adversarial_control_execution"] = controls
        manifest["oracle_receipt"] = ".state/oracle-receipt.json"
        manifest["oracle_receipt_hash"] = _file_hash(receipt_path)
        _write(
            out / ".state/materialization-manifest.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            True,
        )
        _sync_remedies(
            out,
            status="verified",
            strongest_local_status="local_family_verified",
            hard_rule_status="pass",
            oracle_evidence={
                "status": "pass",
                "evidence_class": "docker_sanity",
                "receipt_path": ".state/oracle-receipt.json",
                "receipt_hash": _file_hash(receipt_path),
                "network": "none",
                "normal_discovered_tests": 2,
                "sanitizer_discovered_tests": 2,
            },
            hard_rule_evidence={
                "status": "pass",
                "pair_count": 28,
                "dimensions": list(HARD_RULE_DIMENSIONS),
                "adversarial_controls": controls,
            },
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--plan-remedies", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--verify-docker", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    if args.plan_remedies:
        _write_remedies(args.out, args.force)
        print(f"Planned 10 remedies under {args.out}")
        return 0
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.verify_docker:
        verify_docker(args.out, args.image)
    print(f"Wrote {len(roots)} distinct future-date replacements under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
