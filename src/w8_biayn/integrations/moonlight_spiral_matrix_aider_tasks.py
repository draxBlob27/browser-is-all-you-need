"""Audit and reject the contaminated legacy spiral-matrix task family.

The legacy roots are immutable audit input.  They all implement one shrinking
rectangle/ring walker and divide the permanent official Aider `spiral-matrix`
holdout's inward boundary-order capability across renamed domains.  The
normative first-match remedy rule therefore requires rejection, not repair or
rename-only replacement.  This owner writes only rejection evidence beneath
the parallel re-verification root; it never emits C++ candidate roots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/"
    "aider-text-grid-reshaping/spiral-matrix"
)
LEGACY_OUT = Path(
    ".w8-biayn/data/aider-tasks/"
    "aider-text-grid-reshaping/spiral-matrix"
)
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_SPIRAL_MATRIX_CURRICULUM.md"
)
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/spiral-matrix.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
PLANNER_PATH = "scripts/plan_spiral_matrix_remedies.py"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
NORMALIZER = "spiral-matrix-rejection-v2-seven-dimension-artifacts"
PAIR_THRESHOLD = 0.72
HOLDOUT_THRESHOLD = 0.72
DIVERSITY_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
TASK_IDS = (
    "spiral-archive-boxes",
    "spiral-board-game-setup",
    "spiral-cargo-inspection",
    "spiral-circuit-probe",
    "spiral-courtyard-lights",
    "spiral-drone-photography",
    "spiral-evacuation-search",
    "spiral-greenhouse-seeding",
    "spiral-ice-core-display",
    "spiral-irrigation-valves",
    "spiral-library-shelving",
    "spiral-museum-tour",
    "spiral-orchard-harvest",
    "spiral-paint-mixer",
    "spiral-radar-sweep",
    "spiral-sand-tray",
    "spiral-satellite-panels",
    "spiral-soil-sampler",
    "spiral-warehouse-robot",
    "spiral-water-quality",
)
CHANGED_OWNER_PATHS = (
    CURRICULUM,
    FAMILY_SPEC,
    PLANNER_PATH,
    "src/w8_biayn/integrations/moonlight_spiral_matrix_aider_tasks.py",
    "tests/test_moonlight_spiral_matrix_aider_tasks.py",
    "examples/slime/moonlight_cpp_perf/prepare_spiral_matrix_aider_tasks.sh",
    "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
)


class VerificationError(RuntimeError):
    pass


def _fail(code: str, detail: str) -> None:
    raise VerificationError(f"{code}: {detail}")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _generator_revision() -> str:
    digest = hashlib.sha256()
    for relative in CHANGED_OWNER_PATHS:
        path = Path(relative)
        if path.is_file():
            digest.update(relative.encode())
            digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _task_roots(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for path in root.iterdir() if path.is_dir() and path.name != ".state"))


def _safe_relative(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _role_failure(root: Path, files: object) -> str | None:
    if not isinstance(files, dict):
        return "unsafe_path"
    expected = {"solution", "test", "example"}
    if set(files) != expected:
        return "unsafe_path"
    lists: dict[str, list[str]] = {}
    for role in expected:
        values = files.get(role)
        if not isinstance(values, list) or not values or not all(isinstance(item, str) for item in values):
            return "unsafe_path"
        lists[role] = values
    flattened = [item for values in lists.values() for item in values]
    if len(flattened) != len(set(flattened)):
        return "unsafe_path"
    if any(not _safe_relative(item) or not (root / item).is_file() for item in flattened):
        return "unsafe_path"
    if any(item.startswith(".meta/") or item.startswith(".docs/") or item == "CMakeLists.txt" for item in lists["solution"]):
        return "unsafe_path"
    if len(lists["solution"]) != len(lists["example"]):
        return "target_reference_mismatch"
    expected_solution = [f"{root.name}.h", f"{root.name}.cpp"]
    if lists["solution"] != expected_solution:
        return "target_reference_mismatch"
    return None


def _normalized_text_tokens(text: str, width: int = 7) -> set[str]:
    text = text.lower()
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " literal ", text)
    # Domain/API names and the policy toggles are precisely the superficial
    # variations that must not manufacture family diversity.
    text = re.sub(r"\b(?:top|bottom|left|right|clockwise|counter|true|false)\b", " policy ", text)
    tokens = re.findall(r"[a-z_]+|==|!=|<=|>=|\+\+|--|&&|\|\|", text)
    generic = ["identifier" if token not in {
        "while", "for", "if", "return", "vector", "optional", "size", "push_back",
        "begin", "end", "find", "row", "column", "blocked", "valid", "visited",
        "completed_rings", "first_flagged", "boundary", "ring", "policy", "literal",
        "static_cast", "empty", "front", "namespace", "class", "struct", "using",
        "const", "auto", "int", "bool", "std", "size_t", "continue", "break",
        "operator", "include", "main", "check", "failures", "public", "private",
        "==", "!=", "<=", ">=", "++", "--", "&&", "||",
    } else token for token in tokens]
    if len(generic) < width:
        return set(generic)
    return {
        " ".join(generic[index:index + width])
        for index in range(len(generic) - width + 1)
    }


def _role_paths(root: Path) -> dict[str, list[str]]:
    config = json.loads((root / ".meta/config.json").read_text())
    files = config.get("files")
    failure = _role_failure(root, files)
    if failure is not None:
        _fail(failure, root.name)
    return files


def _read_paths(root: Path, paths: Sequence[str]) -> str:
    return "\n".join((root / relative).read_text() for relative in paths)


def _dimension_features(root: Path) -> dict[str, set[str]]:
    files = _role_paths(root)
    header = _read_paths(root, [path for path in files["solution"] if path.endswith(".h")])
    reference = _read_paths(root, files["example"])
    docs = _read_paths(root, [path.relative_to(root).as_posix() for path in sorted((root / ".docs").glob("*.md"))])
    test_paths = list(files["test"])
    hidden_test = root / ".meta/task_hidden_test.cpp"
    if hidden_test.is_file():
        test_paths.append(".meta/task_hidden_test.cpp")
    tests = _read_paths(root, test_paths)
    negative_path = root / ".meta/negative.cpp"
    negative = (
        negative_path.read_text()
        if negative_path.is_file()
        else "missing topic specific negative fixture"
    )
    return {
        "public_api": _normalized_text_tokens(header, 5),
        "owned_state_algorithm": _normalized_text_tokens(reference, 7),
        "mutation_selection": _normalized_text_tokens(reference, 5),
        "invalid_boundary_behavior": _normalized_text_tokens(docs + "\n" + tests, 5),
        "reference_control_flow": _normalized_text_tokens(reference, 9),
        "deterministic_oracle": _normalized_text_tokens(tests, 7),
        "topic_negative_fixture": _normalized_text_tokens(negative, 3),
    }


def _normalized_tokens(root: Path) -> set[str]:
    dimensions = _dimension_features(root)
    return {
        f"{dimension}:{shingle}"
        for dimension, shingles in dimensions.items()
        for shingle in shingles
    }


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def _pair_result(left: Path, right: Path) -> dict[str, object]:
    left_dimensions = _dimension_features(left)
    right_dimensions = _dimension_features(right)
    dimensions = {
        name: _overlap(left_dimensions[name], right_dimensions[name])
        for name in DIVERSITY_DIMENSIONS
    }
    overall = _overlap(_normalized_tokens(left), _normalized_tokens(right))
    highly_similar_dimensions = sum(score >= 0.70 for score in dimensions.values())
    duplicate = (
        overall >= PAIR_THRESHOLD
        or dimensions["reference_control_flow"] >= 0.80
        or highly_similar_dimensions >= 5
    )
    return {
        "left": left.name,
        "right": right.name,
        "overlap": overall,
        "dimensions": dimensions,
        "highly_similar_dimensions": highly_similar_dimensions,
        "result": "duplicate_family" if duplicate else "pass",
    }


def _replace_text_tree(root: Path, replacements: Sequence[tuple[str, str]]) -> None:
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for old, new in replacements:
            text = text.replace(old, new)
        path.write_text(text)


def _copy_named_clone(source: Path, target: Path) -> None:
    shutil.copytree(source, target)
    old_id = source.name
    new_id = target.name
    old_header = target / f"{old_id}.h"
    old_source = target / f"{old_id}.cpp"
    old_header.rename(target / f"{new_id}.h")
    old_source.rename(target / f"{new_id}.cpp")
    _replace_text_tree(
        target,
        (
            (old_id, new_id),
            (old_id.replace("-", "_"), new_id.replace("-", "_")),
        ),
    )


def _create_adversarial_clone(source: Path, target: Path, kind: str) -> None:
    _copy_named_clone(source, target)
    if kind == "domain-identifier-renamed":
        replacements = (
            ("MuseumTour", "FacilitySurvey"),
            ("TourReport", "SurveyReport"),
            ("visit_rooms", "evaluate_zones"),
            ("museum", "facility"),
            ("Museum", "Facility"),
            ("rooms", "zones"),
            ("room", "zone"),
            ("ticket", "metric"),
            ("category", "reading"),
            ("closed-for-restoration", "flagged-for-service"),
        )
    elif kind == "constants-or-policy-only":
        replacements = (
            ("value < 0", "value < -7"),
            ("negative category", "category below -7"),
            ("{{-4,5,6}}", "{{-8,5,6}}"),
        )
    elif kind == "opposite-end-selection":
        replacements = (
            ("const GridCoordinate begin{top, left};", "const GridCoordinate begin{top, right};"),
            ("top-left", "top-right"),
        )
    else:
        raise ValueError(f"unknown adversarial clone kind: {kind}")
    before = _tree_hash(target)
    _replace_text_tree(target, replacements)
    if _tree_hash(target) == before:
        _fail("adversarial_clone_drift", kind)
    files = json.loads((target / ".meta/config.json").read_text()).get("files")
    failure = _role_failure(target, files)
    if failure is not None:
        _fail(failure, f"{kind}:{target}")


def _adversarial_clone_results(source: Path) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="spiral-hard-rule-") as temporary:
        temporary_root = Path(temporary)
        for kind in (
            "domain-identifier-renamed",
            "constants-or-policy-only",
            "opposite-end-selection",
        ):
            clone = temporary_root / kind
            _create_adversarial_clone(source, clone, kind)
            result = _pair_result(source, clone)
            if result["result"] != "duplicate_family":
                _fail("duplicate_family_control_missed", kind)
            result["source_tree_hash"] = _tree_hash(source)
            result["clone_tree_hash"] = _tree_hash(clone)
            result["mutation_executed"] = result["clone_tree_hash"] != result["source_tree_hash"]
            results[kind] = result
    return results


def _semantic_features(root: Path) -> set[str]:
    paths = list((root / ".docs").glob("*.md"))
    config_path = root / ".meta/config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        files = config.get("files", {})
        for role in ("solution", "test", "example"):
            for relative in files.get(role, []):
                path = root / relative
                if path.is_file():
                    paths.append(path)
    text = "\n".join(path.read_text(errors="replace") for path in sorted(set(paths)))
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text.lower(), flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " literal ", text)
    stop = {
        "a", "an", "and", "are", "as", "at", "be", "bool", "by", "class",
        "const", "cpp", "else", "false", "for", "from", "if", "in", "include",
        "int", "is", "namespace", "of", "on", "or", "return", "static", "std",
        "struct", "the", "this", "to", "true", "using", "vector", "void", "with",
    }
    words = [word for word in re.findall(r"[a-z][a-z0-9_]+", text) if word not in stop]
    if len(words) < 5:
        return set(words)
    return {" ".join(words[index:index + 5]) for index in range(len(words) - 4)}


def _bound_holdouts(repo_root: Path) -> tuple[Path, ...]:
    bases = (
        repo_root / ".cache/upstreams/aider-polyglot/cpp/exercises/practice",
        repo_root / ".w8-biayn/data/polyglot-benchmark/cpp/exercises/practice",
    )
    base = next((path for path in bases if path.is_dir()), None)
    if base is None:
        return ()
    return tuple(sorted(path for path in base.iterdir() if (path / ".meta/config.json").is_file()))


def _official_spiral_root(repo_root: Path) -> Path | None:
    candidates = (
        repo_root / ".cache/upstreams/aider-polyglot/cpp/exercises/practice/spiral-matrix",
        repo_root / ".w8-biayn/data/polyglot-benchmark/cpp/exercises/practice/spiral-matrix",
    )
    return next((path for path in candidates if path.is_dir()), None)


def _prompt_boundary(root: Path) -> dict[str, object]:
    task = load_task(root)
    prompt = build_prompt(task)
    private_markers = (
        ".meta/example",
        "task_hidden_test",
        "CMakeLists.txt",
        "provenance.json",
        "tests.toml",
    )
    if any(marker in prompt for marker in private_markers):
        _fail("prompt_contract_incomplete", root.name)
    if any(path not in prompt for path in task.editable_files):
        _fail("prompt_contract_incomplete", root.name)
    return {
        "status": "pass",
        "editable_files": list(task.editable_files),
        "private_markers_absent": list(private_markers),
        "prompt_hash": _sha256(prompt.encode()),
    }


def _validate_remedy_records(out: Path, roots: tuple[Path, ...]) -> None:
    remedy_root = out / ".state/remedy"
    for root in roots:
        json_path = remedy_root / f"{root.name}.json"
        markdown_path = remedy_root / f"{root.name}.md"
        if not json_path.is_file() or not markdown_path.is_file():
            _fail("remedy_spec_incomplete", root.name)
        record = json.loads(json_path.read_text())
        required = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": root.name,
            "tree_hash_before": _tree_hash(root),
            "disposition": "reject",
            "benchmark_screen": "reject",
            "license_screen": "pass",
            "status": "rejected",
            "primary_core_objective": "achieved",
            "selected_prompt": PROMPT_PATH,
        }
        for key, expected in required.items():
            if record.get(key) != expected:
                _fail("remedy_disposition_conflict", f"{root.name}:{key}")
        if record.get("remedy_spec_hash") != _sha256(markdown_path.read_bytes()):
            _fail("remedy_spec_incomplete", f"{root.name}:hash")
        headings = re.findall(r"^## (.+)$", markdown_path.read_text(), flags=re.MULTILINE)
        expected_headings = [
            "Identity", "Objective", "Public API", "Behavior table",
            "Implementation invariant", "Starter and reference", "Tests",
            "Files and metadata", "Build/oracle", "Family/contamination",
            "Optional dataset handoff", "Acceptance",
        ]
        if headings != expected_headings:
            _fail("remedy_spec_incomplete", f"{root.name}:headings")


def verify_core(
    out: Path = DEFAULT_OUT,
    *,
    legacy_root: Path = LEGACY_OUT,
    repo_root: Path | None = None,
    require_remedies: bool = True,
) -> dict[str, object]:
    repo_root = repo_root or Path.cwd()
    roots = _task_roots(legacy_root)
    if tuple(root.name for root in roots) != TASK_IDS:
        _fail("generator_output_drift", "legacy task inventory")
    emitted = _task_roots(out) if out.is_dir() else ()
    if emitted:
        _fail("benchmark_content_overlap", "re-verification root must contain no candidate tasks")
    if require_remedies:
        _validate_remedy_records(out, roots)

    task_evidence: dict[str, dict[str, object]] = {}
    roots_by_id = {root.name: root for root in roots}
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        failure = _role_failure(root, config.get("files"))
        if failure is not None:
            _fail(failure, root.name)
        reference = (root / ".meta/example.cpp").read_text()
        required_markers = (
            "std::vector<GridCoordinate> ring",
            "while (top <= bottom && left <= right",
            "++top; ++left; --bottom; --right",
        )
        if any(marker not in reference for marker in required_markers):
            _fail("generator_output_drift", f"{root.name}:legacy ring template")
        task_evidence[root.name] = {
            "tree_hash_before": _tree_hash(root),
            "primary_core_objective": "achieved",
            "disposition": "reject",
            "benchmark_screen": "reject",
            "duplicate_family": True,
            "prompt_boundary": _prompt_boundary(root),
            "role_reference_mapping": "pass",
            "local_status": "rejected_benchmark_overlap",
        }

    pairs: list[dict[str, object]] = []
    for left, right in combinations(TASK_IDS, 2):
        result = _pair_result(roots_by_id[left], roots_by_id[right])
        pairs.append(result)
        if result["result"] != "duplicate_family":
            _fail(
                "generator_output_drift",
                f"legacy template pair {left}/{right}: {result['overlap']:.3f}",
            )

    adversarial_results = _adversarial_clone_results(
        roots_by_id["spiral-museum-tour"]
    )

    official = _official_spiral_root(repo_root)
    holdouts = _bound_holdouts(repo_root)
    benchmark_comparisons: list[dict[str, object]] = []
    if holdouts:
        holdout_features = {root.name: _semantic_features(root) for root in holdouts}
        candidate_features = {root.name: _semantic_features(root) for root in roots}
        for task_id in TASK_IDS:
            for holdout in holdouts:
                score = _overlap(candidate_features[task_id], holdout_features[holdout.name])
                result = "benchmark_content_overlap" if holdout.name == "spiral-matrix" else "pass"
                if holdout.name != "spiral-matrix" and score >= HOLDOUT_THRESHOLD:
                    result = "benchmark_content_overlap"
                benchmark_comparisons.append(
                    {
                        "task_id": task_id,
                        "holdout": holdout.name,
                        "overlap": score,
                        "result": result,
                    }
                )
    if official is None:
        benchmark = {
            "status": "not_completed",
            "reason": "bound official spiral-matrix root unavailable",
        }
    else:
        instructions = (official / ".docs/instructions.md").read_text().lower()
        example = (official / ".meta/example.cpp").read_text()
        if "inward, clockwise spiral order" not in instructions or "rotate_clockwise" not in example:
            _fail("generator_output_drift", "official holdout identity")
        benchmark = {
            "status": "reject",
            "reason_code": "benchmark_content_overlap",
            "holdout": "spiral-matrix",
            "holdout_tree_hash": _tree_hash(official),
            "shared_semantic_contract": (
                "ordered inward boundary traversal from a corner; domain nouns, "
                "blocked-cell filtering, predicates, and aggregates do not create "
                "an independent capability"
            ),
        }

    out.mkdir(parents=True, exist_ok=True)
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    receipt_path = state / "legacy-docker-audit.json"
    oracle_evidence: object = "not_completed_before_disposition"
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        receipt_tasks = receipt.get("tasks", {})
        current_revision = _generator_revision()
        hashes_match = isinstance(receipt_tasks, dict) and set(receipt_tasks) == set(TASK_IDS) and all(
            receipt_tasks[task_id].get("tree_hash") == _tree_hash(legacy_root / task_id)
            for task_id in TASK_IDS
        )
        if receipt.get("generator_revision") == current_revision and hashes_match:
            oracle_evidence = {
                "status": receipt.get("status"),
                "receipt": receipt_path.as_posix(),
                "evidence_class": "historical_docker_audit",
                "normal_total": sum(item["normal"] for item in receipt_tasks.values()),
                "asan_ubsan_total": sum(item["asan_ubsan"] for item in receipt_tasks.values()),
                "failed_tasks": receipt.get("failed_tasks", []),
                "effect_on_disposition": "none; benchmark rejection remains terminal",
            }
        else:
            oracle_evidence = "not_completed_stale_docker_receipt"
    audit = {
        "schema_version": "spiral-matrix-family-rejection-v2",
        "family_name": "spiral-matrix",
        "family_type": "aider-text-grid-reshaping",
        "legacy_root": legacy_root.as_posix(),
        "reverify_root": out.as_posix(),
        "selected_prompt": PROMPT_PATH,
        "normalizer": NORMALIZER,
        "pair_threshold": PAIR_THRESHOLD,
        "task_count": len(roots),
        "candidate_task_count": 0,
        "pairwise_count": len(pairs),
        "all_pairs_duplicate": True,
        "hard_rule_dimensions": list(DIVERSITY_DIMENSIONS),
        "hard_rule_scope": "rejected_legacy_roots; zero counted candidate roots",
        "hard_rule_result": "duplicate_family_rejection_reverified",
        "benchmark_screen": benchmark,
        "benchmark_inventory": [root.name for root in holdouts],
        "benchmark_comparisons": benchmark_comparisons,
        "adversarial_clone_controls": adversarial_results,
        "task_evidence": task_evidence,
        "pairwise_semantic_overlap": pairs,
        "changed_owner_paths": list(CHANGED_OWNER_PATHS),
        "generator_revision": _generator_revision(),
        "oracle_evidence": oracle_evidence,
        "strongest_local_status": "rejected_benchmark_overlap",
        "dataset_handoff": "not_requested",
    }
    audit_path = state / "family-audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    if require_remedies:
        control_summary = {
            kind: {
                "result": item["result"],
                "overlap": item["overlap"],
                "mutation_executed": item["mutation_executed"],
                "source_tree_hash": item["source_tree_hash"],
                "clone_tree_hash": item["clone_tree_hash"],
            }
            for kind, item in adversarial_results.items()
        }
        for task_id in TASK_IDS:
            record_path = state / "remedy" / f"{task_id}.json"
            record = json.loads(record_path.read_text())
            record["hard_rule_screen"] = "duplicate_family"
            record["hard_rule_normalizer"] = NORMALIZER
            record["hard_rule_dimensions"] = list(DIVERSITY_DIMENSIONS)
            record["hard_rule_family_pair_count"] = len(pairs)
            record["hard_rule_pairs_for_root"] = len(TASK_IDS) - 1
            record["hard_rule_adversarial_controls"] = control_summary
            record["family_screen_receipt"] = audit_path.as_posix()
            record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return audit


def build(
    out: Path = DEFAULT_OUT,
    force: bool = False,
    *,
    legacy_root: Path = LEGACY_OUT,
) -> tuple[Path, ...]:
    del force
    if out.resolve() == legacy_root.resolve():
        _fail("legacy_root_immutable", out.as_posix())
    verify_core(out, legacy_root=legacy_root, require_remedies=out.resolve() == DEFAULT_OUT.resolve())
    return ()


def _ctest_count(build_dir: Path) -> int:
    result = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"Total Tests:\s+(\d+)", result.stdout)
    if match is None:
        _fail("test_discovery_failed", build_dir.as_posix())
    count = int(match.group(1))
    if count <= 0:
        _fail("zero_tests", build_dir.as_posix())
    return count


def verify_legacy_references(legacy_root: Path, result_out: Path) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("runtime_prerequisite_missing", "cmake and c++ are required")
    tasks: dict[str, dict[str, object]] = {}
    for task_id in TASK_IDS:
        root = legacy_root / task_id
        with tempfile.TemporaryDirectory(prefix="spiral-legacy-audit-") as temporary:
            copied = Path(temporary) / task_id
            shutil.copytree(root, copied)
            counts: dict[str, int] = {}
            outcomes: dict[str, str] = {}
            failure_hashes: dict[str, str] = {}
            for mode, flags in (
                ("normal", []),
                (
                    "asan_ubsan",
                    [
                        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
                        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                    ],
                ),
            ):
                build_dir = Path(temporary) / f"build-{mode}"
                command = [
                    "cmake", "-S", str(copied), "-B", str(build_dir),
                    "-G", "Unix Makefiles",
                    f"-DTASK_SOURCE={copied / '.meta/example.cpp'}",
                    *flags,
                ]
                subprocess.run(command, check=True, capture_output=True, text=True)
                subprocess.run(
                    ["cmake", "--build", str(build_dir), "--parallel", "2"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                counts[mode] = _ctest_count(build_dir)
                test_run = subprocess.run(
                    ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
                    capture_output=True,
                    text=True,
                )
                if test_run.returncode != 0:
                    outcomes[mode] = "reference_tests_failed"
                    failure_hashes[mode] = _sha256(
                        (test_run.stdout + "\n" + test_run.stderr).encode()
                    )
                else:
                    outcomes[mode] = "pass"
            if counts["normal"] != counts["asan_ubsan"]:
                _fail("sanitizer_test_count_mismatch", task_id)
            tasks[task_id] = {
                "tree_hash": _tree_hash(root),
                "normal": counts["normal"],
                "asan_ubsan": counts["asan_ubsan"],
                "normal_status": outcomes["normal"],
                "asan_ubsan_status": outcomes["asan_ubsan"],
                "failure_output_hashes": failure_hashes,
            }
    compiler = subprocess.run(["c++", "--version"], check=True, capture_output=True, text=True).stdout
    cmake = subprocess.run(["cmake", "--version"], check=True, capture_output=True, text=True).stdout
    failed_tasks = sorted(
        task_id
        for task_id, item in tasks.items()
        if item["normal_status"] != "pass" or item["asan_ubsan_status"] != "pass"
    )
    result = {
        "schema_version": "spiral-matrix-legacy-docker-audit-v1",
        "status": "fail" if failed_tasks else "pass",
        "evidence_class": "historical_docker_audit",
        "locked_oracle": False,
        "network": "none",
        "image": SANITY_IMAGE,
        "generator_revision": _generator_revision(),
        "compiler_version": compiler.splitlines()[0],
        "cmake_version": cmake.splitlines()[0],
        "failed_tasks": failed_tasks,
        "tasks": tasks,
    }
    result_out.parent.mkdir(parents=True, exist_ok=True)
    result_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def _import_docker_audit(out: Path, result_path: Path, legacy_root: Path) -> dict[str, object]:
    result = json.loads(result_path.read_text())
    if result.get("status") not in {"pass", "fail"} or result.get("network") != "none":
        _fail("docker_audit_failed", "status/network")
    if result.get("image") != SANITY_IMAGE or result.get("locked_oracle") is not False:
        _fail("docker_audit_failed", "image/evidence class")
    if result.get("generator_revision") != _generator_revision():
        _fail("docker_audit_failed", "generator revision")
    tasks = result.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != set(TASK_IDS):
        _fail("docker_audit_failed", "task inventory")
    for task_id in TASK_IDS:
        item = tasks[task_id]
        if item.get("tree_hash") != _tree_hash(legacy_root / task_id):
            _fail("grader_mount_hash_mismatch", task_id)
        if item.get("normal") != item.get("asan_ubsan") or item.get("normal", 0) <= 0:
            _fail("sanitizer_test_count_mismatch", task_id)
        if item.get("normal_status") not in {"pass", "reference_tests_failed"}:
            _fail("docker_audit_failed", f"{task_id}:normal status")
        if item.get("asan_ubsan_status") not in {"pass", "reference_tests_failed"}:
            _fail("docker_audit_failed", f"{task_id}:sanitizer status")
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    receipt = state / "legacy-docker-audit.json"
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    audit_path = state / "family-audit.json"
    audit = json.loads(audit_path.read_text())
    audit["oracle_evidence"] = {
        "status": result["status"],
        "receipt": receipt.as_posix(),
        "evidence_class": "historical_docker_audit",
        "normal_total": sum(item["normal"] for item in tasks.values()),
        "asan_ubsan_total": sum(item["asan_ubsan"] for item in tasks.values()),
        "failed_tasks": result.get("failed_tasks", []),
        "effect_on_disposition": "none; benchmark rejection remains terminal",
    }
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    for task_id in TASK_IDS:
        record_path = state / "remedy" / f"{task_id}.json"
        record = json.loads(record_path.read_text())
        item = tasks[task_id]
        passed = item["normal_status"] == item["asan_ubsan_status"] == "pass"
        record["oracle_evidence"] = (
            "historical_docker_audit_pass" if passed else "historical_docker_audit_failed"
        )
        record["oracle_receipt"] = receipt.as_posix()
        record["normal_test_count"] = item["normal"]
        record["sanitizer_test_count"] = item["asan_ubsan"]
        record["normal_oracle_status"] = item["normal_status"]
        record["sanitizer_oracle_status"] = item["asan_ubsan_status"]
        if not passed:
            record["late_finding_ids"] = ["SM-ORACLE-CARGO-FAILURE"]
        record["changed_owner_paths"] = list(CHANGED_OWNER_PATHS)
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return result


def docker_audit(out: Path = DEFAULT_OUT, legacy_root: Path = LEGACY_OUT) -> dict[str, object]:
    verify_core(out, legacy_root=legacy_root)
    repo_root = Path.cwd().resolve()
    try:
        legacy_relative = legacy_root.resolve().relative_to(repo_root)
    except ValueError as error:
        raise VerificationError("legacy root must be beneath the repository") from error
    with tempfile.TemporaryDirectory(prefix="spiral-docker-audit-") as temporary:
        result_path = Path(temporary) / "result.json"
        container_result = "/result/result.json"
        command = [
            "docker", "run", "--rm", "--network", "none",
            "-v", f"{repo_root}:/workspace:ro",
            "-v", f"{temporary}:/result",
            "-e", "PYTHONPATH=/workspace/src",
            "-w", "/workspace", SANITY_IMAGE,
            "python3", "-m", "w8_biayn.integrations.moonlight_spiral_matrix_aider_tasks",
            "--verify-legacy-references",
            "--legacy-root", f"/workspace/{legacy_relative.as_posix()}",
            "--result-out", container_result,
        ]
        environment = dict(os.environ)
        subprocess.run(command, check=True, env=environment)
        return _import_docker_audit(out, result_path, legacy_root)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--legacy-root", type=Path, default=LEGACY_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--docker-audit", action="store_true")
    parser.add_argument("--verify-legacy-references", action="store_true")
    parser.add_argument("--result-out", type=Path)
    args = parser.parse_args(argv)
    if args.verify_legacy_references:
        if args.result_out is None:
            parser.error("--verify-legacy-references requires --result-out")
        verify_legacy_references(args.legacy_root, args.result_out)
        return 0
    build(args.out, args.force, legacy_root=args.legacy_root)
    if args.verify_core:
        verify_core(args.out, legacy_root=args.legacy_root)
    if args.docker_audit:
        docker_audit(args.out, args.legacy_root)
    print(f"Rejected {len(TASK_IDS)} contaminated legacy roots; emitted 0 candidates under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
