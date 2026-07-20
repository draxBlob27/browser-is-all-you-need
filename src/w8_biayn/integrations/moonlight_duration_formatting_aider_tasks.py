"""Remediate and locally reverify the duration-formatting Aider task family."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_duration_formatting_cases import CASES, DurationCase

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/duration-formatting"
)
LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-dates-and-clocks/duration-formatting"
)
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_DURATION_FORMATTING_ARITHMETIC_CURRICULUM.md"
)
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/duration-formatting.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-text-grid-reshaping-duration-formatting-v2"
FAMILY_ID_BEFORE = "aider-dates-and-clocks-duration-formatting-v1-template"
GENERATOR_PATH = "src/w8_biayn/integrations/moonlight_duration_formatting_aider_tasks.py"
CASES_PATH = "src/w8_biayn/integrations/moonlight_duration_formatting_cases.py"
TEST_PATH = "tests/test_moonlight_duration_formatting_aider_tasks.py"
WRAPPER_PATH = "examples/slime/moonlight_cpp_perf/prepare_duration_formatting_aider_tasks.sh"
NORMALIZER = "duration-formatting-seven-dimension-v1"
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
MIN_TASKS = 8
MAX_TASKS = 12
DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table",
    "Implementation invariant", "Starter and reference", "Tests",
    "Files and metadata", "Build/oracle", "Family/contamination",
    "Optional dataset handoff", "Acceptance",
)
OFFICIAL_HOLDOUTS = frozenset((
    "all-your-base", "allergies", "bank-account", "binary-search-tree",
    "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
    "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
    "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
    "perfect-numbers", "phone-number", "queen-attack", "robot-name",
    "space-age", "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
))
TASKS = CASES


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _source_hash(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(
        p for p in root.rglob("*")
        if p.is_file() and ".state" not in p.relative_to(root).parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


CMAKE = """cmake_minimum_required(VERSION 3.16)
project(duration_formatting_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
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


def _negative_source(case: DurationCase) -> str:
    if case.reference.count(case.negative_old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift: {case.task_id}")
    return case.reference.replace(case.negative_old, case.negative_new, 1)


def _remedy_dir(out: Path) -> Path:
    return out / ".state" / "remedy"


def _verify_remedies(out: Path) -> None:
    expected = {case.task_id for case in CASES}
    records = {path.stem: path for path in _remedy_dir(out).glob("*.json")}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per replacement is required")
    legacy_ids = {case.legacy_id for case in CASES}
    actual_legacy = {p.name for p in LEGACY_ROOT.iterdir() if p.is_dir()}
    if actual_legacy != legacy_ids:
        _fail("generator_output_drift", "legacy inventory changed")
    for case in CASES:
        record = json.loads(records[case.task_id].read_text(encoding="utf-8"))
        spec = _remedy_dir(out) / f"{case.task_id}.md"
        if record.get("disposition") != "replace":
            _fail("remedy_disposition_conflict", case.task_id)
        if record.get("legacy_task_id") != case.legacy_id or not spec.is_file():
            _fail("remedy_spec_incomplete", case.task_id)
        if record.get("tree_hash_before") != _tree_hash(LEGACY_ROOT / case.legacy_id):
            _fail("generator_output_drift", f"legacy hash: {case.legacy_id}")
        text = spec.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", case.task_id)
        if record.get("remedy_spec_hash") != _sha_bytes(text.encode()):
            _fail("remedy_spec_incomplete", f"spec hash: {case.task_id}")
        inputs = record.get("user_inputs", {})
        if inputs.get("FAMILY_TYPE") != "aider-text-grid-reshaping" or inputs.get(
            "hard_rule_count"
        ) != "8-12":
            _fail("remedy_spec_incomplete", f"user inputs: {case.task_id}")


def _sync_remedies(out: Path, **updates: object) -> None:
    for case in CASES:
        path = _remedy_dir(out) / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["generator_revision_after"] = _source_hash(Path(GENERATOR_PATH))
        record["case_revision_after"] = _source_hash(Path(CASES_PATH))
        record["changed_owner_paths"] = [
            CURRICULUM, FAMILY_SPEC, GENERATOR_PATH, CASES_PATH, TEST_PATH, WRAPPER_PATH,
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _prune_owned_roots(out: Path, force: bool) -> None:
    expected = {case.task_id for case in CASES}
    extras = [p for p in out.iterdir() if p.is_dir() and p.name != ".state" and p.name not in expected]
    if extras and not force:
        _fail("generator_output_drift", f"obsolete roots require --force: {[p.name for p in extras]}")
    for root in extras:
        provenance = root / ".meta" / "provenance.json"
        if not provenance.is_file():
            _fail("generator_output_drift", f"refuse foreign root: {root}")
        data = json.loads(provenance.read_text(encoding="utf-8"))
        if data.get("family_id") != FAMILY_ID:
            _fail("generator_output_drift", f"refuse foreign root: {root}")
        shutil.rmtree(root)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out != DEFAULT_OUT and not _remedy_dir(out).is_dir():
        shutil.copytree(_remedy_dir(DEFAULT_OUT), _remedy_dir(out))
    _verify_remedies(out)
    if not MIN_TASKS <= len(CASES) <= MAX_TASKS:
        _fail("hard_rule_count_out_of_bounds", str(len(CASES)))
    _prune_owned_roots(out, force)
    roots: list[Path] = []
    for case in CASES:
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
            "algorithm_profile": case.algorithm_profile,
            "origin": "repository-authored clean-room replacement",
            "license": "repository-authored",
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
            "selected_prompt": PROMPT_PATH,
            "user_family_type": "aider-text-grid-reshaping",
            "legacy_family_type": "aider-dates-and-clocks",
            "benchmark_separation": (
                "Independent duration-policy API, algorithm, and tests; all 26 "
                "official Aider C++ roots remain permanent holdouts."
            ),
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": case.instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": (
                f'[visible]\ndescription = "{case.algorithm_profile} public behavior"\n\n'
                '[hidden]\ndescription = "invalid, empty, boundary, ordering, and overflow oracle"\n\n'
                f'[negative]\ndescription = "{case.negative_reason}"\n'
            ),
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            ".meta/negative_false_substitute.cpp": _negative_source(case),
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        root = out / case.task_id
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    _sync_remedies(
        out,
        status="implemented",
        strongest_local_status="implemented",
        primary_core_objective="achieved",
        prompt_boundary="pending",
        family_screen="pending",
        benchmark_screen="pending",
        oracle_evidence="not_completed",
        invalidated_prior_evidence="legacy generic-template host results do not bind v2",
    )
    return tuple(roots)


SEMANTIC_WORDS = frozenset((
    "aggregate", "allowance", "boundary", "bucket", "ceiling", "checked",
    "clamp", "complete", "contiguous", "division", "duplicate", "earliest",
    "empty", "excess", "failure", "fastest", "floor", "gap", "greatest",
    "independent", "invalid", "latest", "lookup", "maximum", "minimum",
    "multiply", "overflow", "partition", "pause", "precedence", "rank",
    "reserve", "resume", "selection", "stable", "state", "strict", "sum",
    "tie", "total", "transition", "unknown", "validate",
))
CPP_WORDS = frozenset((
    "if", "else", "for", "while", "return", "class", "struct", "enum",
    "const", "auto", "bool", "int", "long", "void", "true", "false",
    "public", "private", "namespace", "std", "vector", "string", "size_t",
    "unordered_set", "unordered_map", "sort", "min", "max", "break",
))


def normalized_tokens(content: str) -> tuple[str, ...]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        content,
    )
    result: list[str] = []
    for token in raw:
        lower = token.lower()
        if token == "LIT":
            result.append("LIT")
        elif lower in CPP_WORDS or lower in SEMANTIC_WORDS or not re.match(r"[A-Za-z_]", token):
            result.append(lower)
        else:
            result.append("ID")
    return tuple(result)


def _ngrams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    return {tokens[index:index + width] for index in range(max(0, len(tokens) - width + 1))}


def _containment(left: str, right: str) -> float:
    a, b = _ngrams(normalized_tokens(left)), _ngrams(normalized_tokens(right))
    denominator = min(len(a), len(b))
    return len(a & b) / denominator if denominator else 1.0


def artifact_dimensions(case: DurationCase, root: Path) -> dict[str, str]:
    reference = (root / ".meta" / "example.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta" / "task_hidden_test.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    return {
        "public_api": (root / f"{case.task_id}.h").read_text(encoding="utf-8"),
        "owned_state_or_algorithm": reference,
        "mutation_or_selection_rules": (root / ".docs" / "instructions.md").read_text(encoding="utf-8"),
        "invalid_and_boundary_behavior": hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden,
        "topic_specific_negative_fixture": (
            root / ".meta" / "negative_false_substitute.cpp"
        ).read_text(encoding="utf-8"),
    }


def pair_decisions(left: dict[str, str], right: dict[str, str]) -> dict[str, dict[str, object]]:
    decisions: dict[str, dict[str, object]] = {}
    for dimension in DIMENSIONS:
        left_tokens = normalized_tokens(left[dimension])
        right_tokens = normalized_tokens(right[dimension])
        containment = _containment(left[dimension], right[dimension])
        distinct = left_tokens != right_tokens and containment < 0.995
        decisions[dimension] = {
            "decision": "materially_distinct" if distinct else "not_materially_distinct",
            "pass": distinct,
            "containment": round(containment, 6),
            "left_normalized_hash": _sha_bytes(" ".join(left_tokens).encode()),
            "right_normalized_hash": _sha_bytes(" ".join(right_tokens).encode()),
        }
    return decisions


def _hard_rule_matrix(out: Path) -> dict[str, object]:
    artifacts = {case.task_id: artifact_dimensions(case, out / case.task_id) for case in CASES}
    ids = sorted(artifacts)
    pairs: list[dict[str, object]] = []
    for index, left_id in enumerate(ids):
        for right_id in ids[index + 1:]:
            decisions = pair_decisions(artifacts[left_id], artifacts[right_id])
            if set(decisions) != set(DIMENSIONS) or not all(
                bool(row["pass"]) for row in decisions.values()
            ):
                failed = [name for name, row in decisions.items() if not row["pass"]]
                _fail("duplicate_family", f"{left_id}/{right_id}: {failed}")
            pairs.append({"left": left_id, "right": right_id, "dimensions": decisions, "pass": True})
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"incomplete all-pairs: {len(pairs)}")
    return {
        "status": "pass",
        "normalizer": NORMALIZER,
        "dimensions": list(DIMENSIONS),
        "task_count": len(CASES),
        "minimum_task_count": MIN_TASKS,
        "maximum_task_count": MAX_TASKS,
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "conjunctive_decision": True,
        "pairs": pairs,
    }


def _replace_files(root: Path, replacements: tuple[tuple[str, str], ...]) -> None:
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.suffix not in {".h", ".cpp", ".md", ".json", ".toml", ".txt"}:
            continue
        content = path.read_text(encoding="utf-8")
        updated = content
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != content:
            path.write_text(updated, encoding="utf-8")


def _build_controls(out: Path) -> dict[str, object]:
    controls_root = out / ".state" / "hard-rule-controls"
    if controls_root.exists():
        shutil.rmtree(controls_root)
    controls_root.mkdir(parents=True)
    by_id = {case.task_id: case for case in CASES}
    definitions = (
        (
            "domain-identifier-renamed",
            "parking-block-receipt",
            (("Parking", "Garage"), ("parked", "stayed")),
        ),
        (
            "constants-or-policy-only",
            "parking-block-receipt",
            (
                ("at or below the free allowance", "strictly below the free allowance"),
                ("minutes<=t.free_minutes", "minutes<t.free_minutes"),
                ("f.make(20,{20,15,3})", "f.make(19,{20,15,3})"),
                ("a.text==\"free: 20 min\"", "a.text==\"free: 19 min\""),
            ),
        ),
        (
            "opposite-end-selection",
            "pipeline-stage-digest",
            (
                ("earliest stage", "latest stage"),
                ("s.seconds>longest", "s.seconds>=longest"),
                ("r.longest_stage==\"compile\"", "r.longest_stage==\"link\""),
                ("tie.longest_stage==\"first\"", "tie.longest_stage==\"second\""),
            ),
        ),
    )
    results: dict[str, object] = {}
    for name, source_id, replacements in definitions:
        control = controls_root / name
        shutil.copytree(out / source_id, control)
        before = _tree_hash(control)
        _replace_files(control, replacements)
        after = _tree_hash(control)
        if before == after:
            _fail("hard_rule_control_noop", name)
        case = by_id[source_id]
        source_artifacts = artifact_dimensions(case, out / source_id)
        control_artifacts = artifact_dimensions(case, control)
        decisions = pair_decisions(source_artifacts, control_artifacts)
        rejected = not all(bool(row["pass"]) for row in decisions.values())
        if not rejected:
            _fail("duplicate_family", f"control escaped evaluator: {name}")
        results[name] = {
            "source_task": source_id,
            "tree_hash_before": before,
            "tree_hash_after": after,
            "changed": True,
            "coherent_build": "pending",
            "evaluator_result": "rejected:duplicate_family",
            "dimensions": decisions,
        }
    return results


def _holdout_screen(out: Path) -> dict[str, object]:
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_screen_not_completed", str(HOLDOUT_ROOT))
    holdouts: dict[str, str] = {}
    inventory = hashlib.sha256()
    for root in sorted(p for p in HOLDOUT_ROOT.iterdir() if p.is_dir()):
        chunks: list[str] = []
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if path.suffix not in {".h", ".hpp", ".cpp", ".md"}:
                continue
            inventory.update(path.relative_to(HOLDOUT_ROOT).as_posix().encode())
            inventory.update(b"\0")
            inventory.update(path.read_bytes())
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        holdouts[root.name] = "\n".join(chunks)
    if set(holdouts) != OFFICIAL_HOLDOUTS:
        _fail("benchmark_screen_not_completed", "official holdout inventory drift")
    strongest: dict[str, object] = {"candidate": None, "holdout": None, "containment": 0.0}
    for case in CASES:
        candidate = "\n".join(artifact_dimensions(case, out / case.task_id).values())
        for slug, content in holdouts.items():
            score = _containment(candidate, content)
            if score > float(strongest["containment"]):
                strongest = {"candidate": case.task_id, "holdout": slug, "containment": round(score, 6)}
            if score >= 0.72:
                _fail("benchmark_content_overlap", f"{case.task_id}/{slug}: {score:.3f}")
    return {
        "status": "pass",
        "normalizer": NORMALIZER,
        "holdout_root_count": len(holdouts),
        "source_inventory": "sha256:" + inventory.hexdigest(),
        "strongest": strongest,
    }


def _prompt_and_roles(case: DurationCase, root: Path) -> None:
    task = load_task(root)
    if tuple(task.editable_files) != (f"{case.task_id}.h", f"{case.task_id}.cpp"):
        _fail("target_reference_mismatch", case.task_id)
    prompt = build_prompt(task)
    answer = build_assistant_response(task, load_example_files_from_config(root))
    forbidden = (
        ".meta/example", "task_hidden_test", "CMakeLists", "provenance",
        "negative_false_substitute", "docker-sanity", "materialization-manifest",
    )
    if any(value in prompt for value in forbidden):
        _fail("prompt_contract_incomplete", case.task_id)
    if ".meta/example" in answer:
        _fail("target_reference_mismatch", case.task_id)
    config = json.loads((root / ".meta" / "config.json").read_text(encoding="utf-8"))
    if config["files"]["test"] != ["task_visible_test.cpp"]:
        _fail("unsafe_path", case.task_id)
    if config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
        _fail("target_reference_mismatch", case.task_id)


def verify_core(out: Path, *, require_remedy: bool = True) -> dict[str, object]:
    expected = {case.task_id for case in CASES}
    actual = {p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", str(sorted(expected ^ actual)))
    if require_remedy:
        _verify_remedies(out)
    if not MIN_TASKS <= len(CASES) <= MAX_TASKS:
        _fail("hard_rule_count_out_of_bounds", str(len(CASES)))
    if len({case.algorithm_profile for case in CASES}) != len(CASES):
        _fail("duplicate_family", "algorithm profiles are not one-to-one")
    for case in CASES:
        _prompt_and_roles(case, out / case.task_id)
    matrix = _hard_rule_matrix(out)
    controls = _build_controls(out)
    holdouts = _holdout_screen(out)
    manifest = {
        "schema_version": "duration-formatting-materialization-v2",
        "family_id": FAMILY_ID,
        "legacy_root": str(LEGACY_ROOT),
        "reverify_root": str(out),
        "task_count": len(CASES),
        "generator_hash": _source_hash(Path(GENERATOR_PATH)),
        "case_hash": _source_hash(Path(CASES_PATH)),
        "tasks": [
            {
                "task_id": case.task_id,
                "legacy_task_id": case.legacy_id,
                "algorithm_profile": case.algorithm_profile,
                "tree_hash": _tree_hash(out / case.task_id),
                "reference_hash": _source_hash(out / case.task_id / ".meta" / "example.cpp"),
            }
            for case in CASES
        ],
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "hard_rule": matrix,
            "adversarial_controls": controls,
            "semantic_holdout": holdouts,
        },
    }
    _write(
        out / ".state" / "materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    _sync_remedies(
        out,
        status="semantically_admitted",
        strongest_local_status="semantically_admitted",
        primary_core_objective="achieved",
        prompt_boundary="pass",
        reference_mapping="pass",
        family_screen="pass",
        benchmark_screen="pass",
        hard_rule_status="pass",
        family_pair_count=45,
        hard_rule_dimensions=list(DIMENSIONS),
        holdout_root_count=26,
        adversarial_controls="changed_coherent_build_pending_rejected",
        oracle_evidence="not_completed",
    )
    return manifest


def _run_configure_build_test(task: Path, source: Path, build: Path, sanitizer: bool) -> int:
    args = [
        "cmake", "-S", str(task), "-B", str(build), "-G", "Unix Makefiles",
        f"-DTASK_SOURCE={source}",
    ]
    if sanitizer:
        args += [
            "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
            "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
        ]
    subprocess.run(args, check=True, text=True, capture_output=True)
    subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], check=True, text=True, capture_output=True)
    shown = subprocess.run(
        ["ctest", "--test-dir", str(build), "--show-only=json-v1"],
        check=True, text=True, capture_output=True,
    )
    count = len(json.loads(shown.stdout)["tests"])
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    subprocess.run(
        ["ctest", "--test-dir", str(build), "--output-on-failure"],
        check=True, text=True, capture_output=True, env=env,
    )
    return count


def verify(out: Path) -> dict[str, object]:
    if not shutil.which("cmake") or not shutil.which("c++"):
        _fail("oracle_not_completed", "verification requires cmake and c++")
    manifest = verify_core(out)
    rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="duration-formatting-host-") as temp_name:
        temp = Path(temp_name)
        for case in CASES:
            task = temp / case.task_id
            shutil.copytree(out / case.task_id, task)
            counts: dict[str, int] = {}
            for mode, sanitizer in (("normal", False), ("sanitizer", True)):
                count = _run_configure_build_test(
                    task, task / ".meta" / "example.cpp", temp / "build" / case.task_id / mode, sanitizer
                )
                counts[mode] = count
                negative_build = temp / "build" / case.task_id / f"{mode}-negative"
                try:
                    _run_configure_build_test(
                        task, task / ".meta" / "negative_false_substitute.cpp", negative_build, sanitizer
                    )
                except subprocess.CalledProcessError:
                    negative_rejected = True
                else:
                    negative_rejected = False
                if not negative_rejected:
                    _fail("invariant_not_enforced", f"{case.task_id}/{mode}")
            if counts != {"normal": 2, "sanitizer": 2}:
                _fail("sanitizer_test_count_mismatch", case.task_id)
            rows.append({"task_id": case.task_id, "counts": counts, "negative_rejected": True})
        control_rows: list[dict[str, object]] = []
        controls = out / ".state" / "hard-rule-controls"
        for control in sorted(p for p in controls.iterdir() if p.is_dir()):
            copied = temp / "controls" / control.name
            shutil.copytree(control, copied)
            counts = {}
            for mode, sanitizer in (("normal", False), ("sanitizer", True)):
                counts[mode] = _run_configure_build_test(
                    copied,
                    copied / ".meta" / "example.cpp",
                    temp / "control-build" / control.name / mode,
                    sanitizer,
                )
            if counts != {"normal": 2, "sanitizer": 2}:
                _fail("hard_rule_control_incoherent", control.name)
            control_rows.append({"control": control.name, "counts": counts, "coherent_build": True})
    receipt = {
        "schema_version": "duration-formatting-host-iteration-v1",
        "status": "pass",
        "evidence_class": "host_iteration",
        "local_family_verified": False,
        "task_count": len(CASES),
        "generator_hash": manifest["generator_hash"],
        "case_hash": manifest["case_hash"],
        "results": rows,
        "control_results": control_rows,
    }
    _write(out / ".state" / "host-oracle-iteration.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out,
        status="semantically_admitted",
        strongest_local_status="semantically_admitted",
        oracle_evidence="host_iteration_not_completion_evidence",
        normal_test_count=2,
        sanitizer_test_count=2,
        negative_fixture_status="compiled_and_rejected_normal_and_sanitizer",
        adversarial_controls="changed_coherent_build_pass_rejected",
    )
    return receipt


DOCKER_RUNNER = r'''import hashlib,json,os,pathlib,shutil,subprocess,tarfile
archive=pathlib.Path("/input/family.tar")
root=pathlib.Path("/tmp/family")
root.mkdir()
with tarfile.open(archive) as tar: tar.extractall(root)
expected=json.loads(pathlib.Path("/input/expected.json").read_text())
def tree_hash(path):
 d=hashlib.sha256()
 for p in sorted(x for x in path.rglob("*") if x.is_file() and ".state" not in x.parts):
  d.update(p.relative_to(path).as_posix().encode());d.update(b"\0");d.update(p.read_bytes());d.update(b"\0")
 return "sha256:"+d.hexdigest()
def run(task,source,build,sanitizer,expect_pass):
 args=["cmake","-S",str(task),"-B",str(build),"-G","Unix Makefiles","-DCMAKE_CXX_COMPILER=/usr/local/bin/g++","-DTASK_SOURCE="+str(source)]
 if sanitizer:args += ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
 subprocess.run(args,check=True,text=True)
 subprocess.run(["cmake","--build",str(build),"--parallel","2"],check=True,text=True)
 shown=subprocess.run(["ctest","--test-dir",str(build),"--show-only=json-v1"],check=True,capture_output=True,text=True)
 count=len(json.loads(shown.stdout)["tests"])
 env=dict(os.environ);env["ASAN_OPTIONS"]="detect_leaks=0"
 tested=subprocess.run(["ctest","--test-dir",str(build),"--output-on-failure"],env=env,capture_output=True,text=True)
 if count!=2 or (tested.returncode==0)!=expect_pass:raise SystemExit("test_expectation_failed:"+task.name+":"+str(sanitizer)+":"+str(tested.returncode))
 return count
results=[]
for task_id,want in expected["tasks"].items():
 task=root/"tasks"/task_id;got=tree_hash(task)
 if got!=want:raise SystemExit("grader_mount_hash_mismatch:"+task_id+":"+got+":"+want)
 for mode,sanitizer in (("normal",False),("sanitizer",True)):
  count=run(task,task/".meta/example.cpp",pathlib.Path("/tmp/build")/task_id/mode,sanitizer,True)
  ncount=run(task,task/".meta/negative_false_substitute.cpp",pathlib.Path("/tmp/build")/task_id/(mode+"-negative"),sanitizer,False)
  results.append({"task_id":task_id,"mode":mode,"test_count":count,"negative_test_count":ncount,"negative_rejected":True,"mounted_tree_hash":got})
controls=[]
for name,want in expected["controls"].items():
 task=root/"controls"/name;got=tree_hash(task)
 if got!=want:raise SystemExit("grader_mount_hash_mismatch:control:"+name)
 for mode,sanitizer in (("normal",False),("sanitizer",True)):
  count=run(task,task/".meta/example.cpp",pathlib.Path("/tmp/control-build")/name/mode,sanitizer,True)
  controls.append({"control":name,"mode":mode,"test_count":count,"coherent_build":True,"mounted_tree_hash":got})
toolchain={"compiler_path":"/usr/local/bin/g++","compiler_version":subprocess.run(["/usr/local/bin/g++","--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0],"compiler_hash":"sha256:"+hashlib.sha256(pathlib.Path("/usr/local/bin/g++").read_bytes()).hexdigest(),"cmake_version":subprocess.run(["cmake","--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0]}
pathlib.Path("/output/result.json").write_text(json.dumps({"results":results,"controls":controls,"toolchain":toolchain},sort_keys=True))
'''


def _archive_family(out: Path, archive: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    task_hashes = {case.task_id: _tree_hash(out / case.task_id) for case in CASES}
    controls_root = out / ".state" / "hard-rule-controls"
    control_hashes = {p.name: _tree_hash(p) for p in controls_root.iterdir() if p.is_dir()}
    with tarfile.open(archive, "w") as tar:
        entries = [(Path("tasks") / case.task_id, out / case.task_id) for case in CASES]
        entries += [(Path("controls") / name, controls_root / name) for name in sorted(control_hashes)]
        for prefix, root in entries:
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                relative = prefix / path.relative_to(root)
                info = tarfile.TarInfo(relative.as_posix())
                content = path.read_bytes()
                info.size = len(content);info.mode = 0o644;info.mtime = 0
                info.uid = info.gid = 0;info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(content))
    return _source_hash(archive), task_hashes, control_hashes


def docker_sanity(out: Path, image: str = SANITY_IMAGE) -> dict[str, object]:
    manifest = verify_core(out)
    if image != SANITY_IMAGE:
        _fail("grader_image_mismatch", image)
    if not shutil.which("docker"):
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    inspected = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        text=True, capture_output=True,
    )
    if inspected.returncode != 0:
        _fail("docker_sanity_not_completed", inspected.stderr.strip())
    image_id = inspected.stdout.strip()
    with tempfile.TemporaryDirectory(prefix="duration-formatting-docker-") as temp_name:
        temp = Path(temp_name)
        archive = temp / "family.tar"
        archive_hash, task_hashes, control_hashes = _archive_family(out, archive)
        (temp / "expected.json").write_text(
            json.dumps({"tasks": task_hashes, "controls": control_hashes}), encoding="utf-8"
        )
        (temp / "runner.py").write_text(DOCKER_RUNNER, encoding="utf-8")
        output = temp / "output"
        output.mkdir()
        command = [
            "docker", "run", "--rm", "--network", "none",
            "-v", f"{temp}:/input:ro", "-v", f"{output}:/output",
            image, "python3", "/input/runner.py",
        ]
        run = subprocess.run(command, text=True, capture_output=True)
        if run.returncode != 0:
            _fail("docker_sanity_failed", (run.stdout + "\n" + run.stderr)[-6000:])
        result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    rows = result["results"]
    controls = result["controls"]
    if len(rows) != len(CASES) * 2 or len(controls) != 3 * 2:
        _fail("test_discovery_failed", "Docker result inventory")
    for row in rows:
        if row["test_count"] != 2 or row["negative_test_count"] != 2 or not row["negative_rejected"]:
            _fail("test_discovery_failed", row["task_id"])
    for row in controls:
        if row["test_count"] != 2 or not row["coherent_build"]:
            _fail("hard_rule_control_incoherent", row["control"])
    for name, control in manifest["screen"]["adversarial_controls"].items():
        matched = [row for row in controls if row["control"] == name]
        if len(matched) != 2 or {row["mode"] for row in matched} != {"normal", "sanitizer"}:
            _fail("hard_rule_control_incoherent", name)
        control["coherent_build"] = "pass_normal_and_sanitizer"
        control["docker_test_count_per_mode"] = 2
    manifest["screen"]["docker_runtime"] = {
        "status": "pass",
        "evidence_class": "docker_sanity",
        "network_policy": "none",
        "image": image,
        "image_id": image_id,
        "normal_test_count_per_task": 2,
        "sanitizer_test_count_per_task": 2,
        "negative_fixture_count": len(CASES),
        "coherent_control_count": 3,
    }
    _write(
        out / ".state" / "materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    receipt = {
        "schema_version": "duration-formatting-docker-sanity-v1",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "local_family_verified": True,
        "network_policy": "none",
        "image": image,
        "image_id": image_id,
        "archive_hash": archive_hash,
        "generator_hash": manifest["generator_hash"],
        "case_hash": manifest["case_hash"],
        "toolchain": result["toolchain"],
        "task_count": len(CASES),
        "normal_test_count_per_task": 2,
        "sanitizer_test_count_per_task": 2,
        "topic_negatives_compiled_and_rejected": len(CASES),
        "hard_rule_controls_changed_coherent_and_rejected": 3,
        "results": rows,
        "control_results": controls,
        "command": command,
    }
    receipt_path = out / ".state" / "docker-sanity.json"
    _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out,
        status="verified",
        strongest_local_status="local_family_verified",
        primary_core_objective="achieved",
        prompt_boundary="pass",
        reference_mapping="pass",
        family_screen="pass",
        benchmark_screen="pass",
        hard_rule_status="pass",
        oracle_evidence="docker_sanity",
        oracle_receipt=str(receipt_path),
        normal_test_count=2,
        sanitizer_test_count=2,
        negative_fixture_status="compiled_and_rejected_normal_and_sanitizer",
        adversarial_controls="changed_coherent_build_pass_rejected",
        image=image,
        image_id=image_id,
        network_policy="none",
    )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core or args.verify or args.docker_sanity:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    print(f"Wrote {len(roots)} duration-formatting replacement tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
