"""Own the 110-root quoted and nested records expansion family."""

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
from typing import Iterable, Sequence

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
from w8_biayn.integrations.moonlight_quoted_nested_records_cases import (
    ARCHITECTURES,
    CASES,
    OPERATIONS,
    Case,
    header,
    instructions,
    negative,
    private_test,
    reference,
    visible_test,
)


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/quoted-nested-records"
)
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-validation-input-parsing/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUCTURED_DELIMITERS_QUOTES_AND_RECORDS_CURRICULUM.md"
)
FAMILY_SPEC = (
    "docs/aider-tasks-spec/aider-validation-input-parsing/quoted-nested-records.md"
)
SELECTED_PROMPTS = (
    "docs/aider-tasks-spec/prompts/generate-family-spec.md",
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
)
COUNT_PLAN = "docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md"
FAMILY_ID = "validation-parsing-quoted-nested-records-expansion-v1"
SCHEMA = "aider-quoted-nested-records-materialization-v1"
NORMALIZER = "quoted-nested-role-aware-v1"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
EXPECTED_ROOTS = 110
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset(
    {
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
    }
)


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write(path: Path, content: str, force: bool = False) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; use --force through the owner")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _json(path: Path, value: object, force: bool = True) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n", force)


def _tree_hash(root: Path) -> str:
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        records.append(f"{_sha_file(path)}\0{relative}\n")
    return _sha_bytes("".join(records).encode())


def _owner_hash() -> str:
    paths = (
        Path(__file__),
        Path(__file__).with_name("moonlight_quoted_nested_records_cases.py"),
        Path(CURRICULUM),
        Path(FAMILY_SPEC),
        Path("tests/test_moonlight_quoted_nested_records_aider_tasks.py"),
    )
    return _sha_bytes(
        "".join(f"{path.as_posix()}\0{_sha_file(path)}\n" for path in paths).encode()
    )


def _safe_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("unsafe_path", "empty or non-string path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _assert_output_root(out: Path) -> None:
    repo = Path.cwd().resolve()
    absolute = (repo / out).resolve() if not out.is_absolute() else out.resolve()
    expansion = (repo / EXPANSION_ROOT).resolve()
    legacy = (repo / LEGACY_ROOT).resolve()
    reverify = (repo / REVERIFY_ROOT).resolve()
    if absolute == expansion or expansion not in absolute.parents:
        _fail("unsafe_output_root", str(out))
    if absolute == legacy or legacy in absolute.parents or absolute == reverify or reverify in absolute.parents:
        _fail("unsafe_output_root", str(out))
    current = repo
    for part in absolute.relative_to(repo).parts:
        current /= part
        if current.is_symlink():
            _fail("unsafe_output_root", f"symlink component {current}")


def _normalize(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " LITERAL ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?(?:u|ul|ull|l|ll)?\b", " NUMBER ", text, flags=re.I)
    text = re.sub(r"\b(first|last|front|back|left|right|reverse|forward)\b", " ENDPOINT ", text, flags=re.I)
    text = re.sub(r"\b(harbor|clinic|library|record|packet|feed|ledger|batch)\b", " DOMAIN ", text, flags=re.I)
    return tuple(re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||->|\S", text.lower()))


def _grams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    return {tokens[index : index + width] for index in range(max(0, len(tokens) - width + 1))}


def _similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a, b = _grams(left), _grams(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def _cmake() -> str:
    return r'''cmake_minimum_required(VERSION 3.16)
project(quoted_nested_record_task LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_private "${TASK_SOURCE}" .meta/task_private_test.cpp)
foreach(target task_visible task_private)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME private COMMAND task_private)
'''


def _task_files(case: Case) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": f"Implement {case.mechanism} and {case.operation.objective}.",
        "files": {
            "solution": ["task.h", "task.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "schema_version": "aider-clean-room-provenance-v1",
        "family_id": FAMILY_ID,
        "task_id": case.task_id,
        "origin": "clean-room repository-authored new expansion root",
        "lineage": "new-root; no parent or replacement ancestor",
        "task_spec_revision": 2,
        "license": "repository-authored project material",
        "curriculum_document": CURRICULUM,
        "family_specification": FAMILY_SPEC,
        "count_plan": COUNT_PLAN,
        "selected_prompts": list(SELECTED_PROMPTS),
        "architecture": case.architecture.key,
        "operation": case.operation.key,
        "semantic_mechanism": case.mechanism,
        "primary_core_objective": "achieved by generated reference and discriminator",
        "remedy_record": f".state/remedy/{case.task_id}.json",
        "remedy_specification": f".state/remedy/specs/{case.task_id}.md",
        "benchmark_separation": "not derived from official Aider prompts, APIs, tests, references, responses, or histories",
        "status": "generated candidate pending creator preflight and independent audit",
        "dataset_handoff": "not_requested",
    }
    return {
        ".docs/introduction.md": (
            f"# {case.title}\n\n"
            "This clean-room local task exercises quoted or nested record processing.\n"
        ),
        ".docs/instructions.md": f"# Instructions\n\n{instructions(case)}\n",
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            "[visible]\n"
            f'description = "exact valid {case.architecture.mechanism} plus {case.operation.key} result"\n\n'
            "[private]\n"
            f'description = "exact replay, structural and operation boundaries, architecture regression, and wrong {case.operation.key} reducer"\n'
        ),
        "task.h": header(case),
        "task.cpp": '#include "task.h"\n// TODO: implement the documented parser and record operation.\n',
        ".meta/example.h": header(case),
        ".meta/example.cpp": reference(case),
        ".meta/negative_false_substitute.cpp": negative(case),
        "task_visible_test.cpp": visible_test(case),
        ".meta/task_private_test.cpp": private_test(case),
        "CMakeLists.txt": _cmake(),
    }


def _discover_config_roots(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path.parent.parent for path in root.rglob(".meta/config.json") if ".state" not in path.parts)


def _inventory(roots: Iterable[Path]) -> dict[str, object]:
    rows = []
    for root in sorted(roots):
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        rows.append(
            {
                "task_id": root.name,
                "root": root.as_posix(),
                "config_hash": _sha_file(root / ".meta/config.json"),
                "solution": config.get("files", {}).get("solution", []),
            }
        )
    digest = _sha_bytes("".join(f"{row['task_id']}\0{row['root']}\0{row['config_hash']}\n" for row in rows).encode())
    return {"count": len(rows), "sha256": digest, "rows": rows}


def _freeze_source_inventory(out: Path) -> dict[str, object]:
    legacy = _discover_config_roots(LEGACY_ROOT)
    reverify = _discover_config_roots(REVERIFY_ROOT)
    other_expansion = [
        root
        for root in _discover_config_roots(EXPANSION_ROOT)
        if out not in root.parents and not _owned_existing(root)
    ]
    ids: dict[str, list[str]] = {}
    for root in [*legacy, *reverify, *other_expansion]:
        ids.setdefault(root.name, []).append(root.as_posix())
    collisions = {case.task_id: ids[case.task_id] for case in CASES if case.task_id in ids}
    if collisions:
        _fail("duplicate_task", json.dumps(collisions, sort_keys=True))
    value = {
        "schema_version": "aider-expansion-source-inventory-v1",
        "legacy": _inventory(legacy),
        "reverify": _inventory(reverify),
        "other_expansion": _inventory(other_expansion),
        "reserved_id_count": len(ids),
        "candidate_id_count": len(CASES),
        "candidate_ids": sorted(case.task_id for case in CASES),
        "task_id_collision": "pass",
    }
    _json(out / ".state/source-inventory.json", value)
    return value


def _owned_existing(root: Path) -> bool:
    path = root / ".meta/provenance.json"
    if not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("family_id") == FAMILY_ID
    except json.JSONDecodeError:
        return False


def build(
    out: Path = DEFAULT_OUT, force: bool = False, *, _internal_scratch: bool = False
) -> tuple[Path, ...]:
    if not _internal_scratch:
        _assert_output_root(out)
    out.mkdir(parents=True, exist_ok=True)
    if not _internal_scratch:
        _freeze_source_inventory(out)
    expected = {case.task_id for case in CASES}
    foreign = [root for root in _discover_config_roots(out) if root.name not in expected or not _owned_existing(root)]
    if foreign:
        _fail("generator_output_drift", f"foreign roots: {[path.as_posix() for path in foreign]}")
    roots = []
    for case in CASES:
        root = out / case.task_id
        if root.exists() and force:
            if not _owned_existing(root):
                _fail("generator_output_drift", f"refuse to replace unowned root {root}")
            shutil.rmtree(root)
        rendered = task_named_files(root, _task_files(case))
        for relative, content in rendered.items():
            _write(root / relative, content, force)
        roots.append(root)
    candidate_rows = []
    for case, root in zip(CASES, roots, strict=True):
        candidate_rows.append(
            {
                "task_id": case.task_id,
                "architecture": case.architecture.key,
                "operation": case.operation.key,
                "lineage": "new-root",
                "tree_hash": _tree_hash(root),
                "status": "generated",
            }
        )
    if not _internal_scratch:
        _json(
            out / ".state/candidate-manifest.json",
            {
                "schema_version": "aider-expansion-candidates-v1",
                "family_id": FAMILY_ID,
                "requested_count": EXPECTED_ROOTS,
                "candidate_count": len(candidate_rows),
                "candidates": candidate_rows,
                "rejected": [],
                "replaced": [],
            },
        )
        _json(out / ".state/rejected-candidates.json", {"schema_version": "aider-expansion-rejections-v1", "rows": []})
    return tuple(roots)


def _dimension_text(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    header_name = next(
        name for name in config["files"]["solution"] if Path(name).suffix in {".h", ".hpp"}
    )
    return {
        "public_api": (root / header_name).read_text(encoding="utf-8"),
        "owned_state_algorithm": (root / ".meta/example.cpp").read_text(encoding="utf-8"),
        "mutation_selection_rules": (root / ".docs/instructions.md").read_text(encoding="utf-8"),
        "invalid_boundary_behavior": "\n".join(
            [
                (root / ".docs/instructions.md").read_text(encoding="utf-8"),
                (root / ".meta/task_private_test.cpp").read_text(encoding="utf-8"),
            ]
        ),
        "reference_control_flow": (root / ".meta/example.cpp").read_text(encoding="utf-8"),
        "deterministic_oracle": "\n".join(
            [
                (root / "task_visible_test.cpp").read_text(encoding="utf-8"),
                (root / ".meta/task_private_test.cpp").read_text(encoding="utf-8"),
            ]
        ),
        "topic_specific_negative_fixture": (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8"),
    }


def _dimension_profiles(root: Path) -> dict[str, dict[str, object]]:
    profiles = {}
    for dimension, text in _dimension_text(root).items():
        tokens = _normalize(text)
        profiles[dimension] = {
            "hash": _sha_bytes("\0".join(tokens).encode()),
            "tokens": tokens,
        }
    return profiles


def _pair_decision(left: Path, right: Path) -> dict[str, object]:
    left_profiles = _dimension_profiles(left)
    right_profiles = _dimension_profiles(right)
    dimensions = {}
    for name in HARD_RULE_DIMENSIONS:
        left_tokens = left_profiles[name]["tokens"]
        right_tokens = right_profiles[name]["tokens"]
        symmetric = len(set(left_tokens) ^ set(right_tokens))
        similarity = _similarity(left_tokens, right_tokens)
        dimensions[name] = {
            "different": left_profiles[name]["hash"] != right_profiles[name]["hash"] and symmetric >= 1 and similarity < 0.999,
            "symmetric_token_difference": symmetric,
            "similarity": round(similarity, 6),
        }
    return {
        "left": left.name,
        "right": right.name,
        "dimensions": dimensions,
        "pass": all(row["different"] for row in dimensions.values()),
    }


def _whole_format_ok(root: Path, content: str) -> bool:
    task = load_task(root)
    try:
        parsed = parse_whole_file_blocks(content)
    except WholeFormatError:
        return False
    return set(parsed) == set(task.editable_files) and len(parsed) == len(task.editable_files)


def _corpus(root: Path) -> str:
    allowed = {".md", ".h", ".hpp", ".cpp", ".toml"}
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in allowed and path.name != "catch.hpp" and ".state" not in path.parts
    )


def _cross_tree_screen(out: Path, candidate_tokens: dict[str, tuple[str, ...]]) -> dict[str, object]:
    sources = [*(_discover_config_roots(LEGACY_ROOT)), *(_discover_config_roots(REVERIFY_ROOT))]
    sources += [root for root in _discover_config_roots(EXPANSION_ROOT) if out not in root.parents]
    existing = [(root, _normalize(_corpus(root))) for root in sources]
    corpus_records = [
        f"{root.as_posix()}\0{_sha_bytes(chr(0).join(tokens).encode())}\n"
        for root, tokens in existing
    ]
    comparison_corpus_hash = _sha_bytes("".join(corpus_records).encode())
    exact = {_sha_bytes("\0".join(tokens).encode()): root for root, tokens in existing}
    rows = []
    for task_id, tokens in candidate_tokens.items():
        digest = _sha_bytes("\0".join(tokens).encode())
        if digest in exact:
            _fail("duplicate_family", f"{task_id}:{exact[digest]}")
        strongest = (0.0, "")
        for root, other in existing:
            score = _similarity(tokens, other)
            if score > strongest[0]:
                strongest = (score, root.as_posix())
        if strongest[0] >= 0.82:
            _fail("duplicate_family", f"{task_id}:{strongest[1]}:{strongest[0]:.4f}")
        rows.append({"task_id": task_id, "strongest_similarity": round(strongest[0], 6), "strongest_root": strongest[1]})
    return {
        "status": "pass",
        "compared_existing_roots": len(existing),
        "comparison_corpus_hash": comparison_corpus_hash,
        "normalizer": NORMALIZER,
        "threshold": 0.82,
        "rows": rows,
    }


def _holdout_screen(candidate_tokens: dict[str, tuple[str, ...]]) -> dict[str, object]:
    base = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
    holdouts = []
    inventory = []
    for slug in sorted(OFFICIAL_AIDER_CPP_HOLDOUTS):
        root = base / slug
        if not root.is_dir():
            _fail("benchmark_content_overlap", f"missing bound holdout {slug}")
        tokens = _normalize(_corpus(root))
        holdouts.append((slug, tokens))
        inventory.append(
            {
                "slug": slug,
                "root": root.as_posix(),
                "normalized_content_hash": _sha_bytes(chr(0).join(tokens).encode()),
            }
        )
    rows = []
    for task_id, tokens in candidate_tokens.items():
        for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
            if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", " ".join(tokens)):
                _fail("benchmark_id_overlap", f"{task_id}:{slug}")
        strongest = max((_similarity(tokens, tokens2), slug) for slug, tokens2 in holdouts)
        if strongest[0] >= 0.65:
            _fail("benchmark_content_overlap", f"{task_id}:{strongest[1]}:{strongest[0]:.4f}")
        rows.append({"task_id": task_id, "strongest_similarity": round(strongest[0], 6), "holdout": strongest[1]})
    inventory_hash = _sha_bytes(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    )
    return {
        "status": "pass",
        "holdout_count": len(holdouts),
        "holdout_inventory": inventory,
        "holdout_inventory_hash": inventory_hash,
        "normalizer": NORMALIZER,
        "threshold": 0.65,
        "rows": rows,
    }


def _copy_control(
    source: Path,
    target: Path,
    transforms: dict[str, tuple[str, str] | tuple[tuple[str, str], ...]],
) -> list[str]:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    changed = []
    for relative, replacements in transforms.items():
        path = target / relative
        content = path.read_text(encoding="utf-8")
        pairs = (replacements,) if isinstance(replacements[0], str) else replacements
        for before, after in pairs:
            if before not in content:
                _fail("adversarial_control_not_pure", f"{target.name}:{relative}:needle")
            content = content.replace(before, after)
        path.write_text(content, encoding="utf-8")
        changed.append(relative)
    return changed


def _materialize_controls(out: Path) -> dict[str, object]:
    controls_root = out / ".state/adversarial-controls"
    controls_root.mkdir(parents=True, exist_ok=True)
    base_project = out / "qr-quoted-row-project"
    base_flatten = out / "qr-quoted-row-flatten"
    specs = {
        "domain-identifier-renamed-clone": (
            base_project,
            {".docs/introduction.md": ("Quoted delimiter row", "Harbor cargo row")},
        ),
        "constants-policy-only-clone": (
            base_flatten,
            {
                "task_visible_test.cpp": ("32U", "64U"),
                ".meta/task_private_test.cpp": ("32U", "64U"),
            },
        ),
        "opposite-end-selection-clone": (
            base_project,
            {
                "task_visible_test.cpp": (
                    ("{0U,1U}", "{1U,0U}"),
                    (
                        'std::vector<std::string>{"alpha","beta,gamma"}',
                        'std::vector<std::string>{"beta,gamma","alpha"}',
                    ),
                ),
                ".meta/task_private_test.cpp": (
                    ("{0U,1U}", "{1U,0U}"),
                    (
                        'std::vector<std::string>{"alpha","beta,gamma"}',
                        'std::vector<std::string>{"beta,gamma","alpha"}',
                    ),
                ),
            },
        ),
    }
    rows = {}
    for name, (base, transforms) in specs.items():
        target = controls_root / name
        changed = _copy_control(base, target, transforms)
        decision = _pair_decision(base, target)
        if decision["pass"]:
            _fail("adversarial_clone_accepted", name)
        if not changed or _tree_hash(base) == _tree_hash(target):
            _fail("adversarial_control_not_pure", name)
        rows[name] = {
            "base": base.name,
            "changed_files": changed,
            "tree_hash": _tree_hash(target),
            "production_decision": decision,
            "coherent_runtime": "pending docker creator preflight",
        }
    return rows


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    _assert_output_root(out)
    roots = _discover_config_roots(out)
    expected = {case.task_id for case in CASES}
    actual = {root.name for root in roots}
    if len(roots) != EXPECTED_ROOTS or actual != expected:
        _fail("generator_output_drift", f"expected {EXPECTED_ROOTS}, found {len(roots)}")
    with tempfile.TemporaryDirectory(prefix="quoted-records-regeneration-") as temporary:
        fresh = Path(temporary) / EXPANSION_ROOT / "validation-parsing/quoted-nested-records"
        build(fresh, _internal_scratch=True)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    prompt_hashes = {}
    reference_hashes = {}
    test_hashes = {}
    artifact_hashes = {}
    candidate_tokens = {}
    profiles = {}
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config.get("files", {})
        solution = [_safe_path(value) for value in files.get("solution", [])]
        tests = [_safe_path(value) for value in files.get("test", [])]
        examples = [_safe_path(value) for value in files.get("example", [])]
        if solution != [f"{case.task_id}.h", f"{case.task_id}.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        if examples != [".meta/example.h", ".meta/example.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        if set(solution) & (set(tests) | set(examples)) or any(
            name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution
        ):
            _fail("unsafe_path", case.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("target_reference_mismatch", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private_markers = [*tests, *examples, "CMakeLists.txt", ".meta/", "negative_false_substitute"]
        if any(marker in prompt for marker in private_markers):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if not _whole_format_ok(root, answer):
            _fail("target_reference_mismatch", case.task_id)
        missing = f"{solution[0]}\n```cpp\n// omitted source\n```\n"
        if _whole_format_ok(root, missing) or _whole_format_ok(root, "prose\n" + answer):
            _fail("whole_format_failed", case.task_id)
        if any(os.stat(path).st_nlink != 1 for path in root.rglob("*") if path.is_file()):
            _fail("unsafe_output_root", f"hardlink in {case.task_id}")
        prompt_hashes[case.task_id] = _sha_bytes(prompt.encode())
        reference_hashes[case.task_id] = _sha_file(root / ".meta/example.cpp")
        test_hashes[case.task_id] = _sha_bytes(
            ((root / "task_visible_test.cpp").read_bytes() + (root / ".meta/task_private_test.cpp").read_bytes())
        )
        artifact_hashes[case.task_id] = {
            "editable_header": _sha_file(root / solution[0]),
            "editable_source": _sha_file(root / solution[1]),
            "reference_header": _sha_file(root / examples[0]),
            "reference_source": _sha_file(root / examples[1]),
            "visible_test": _sha_file(root / tests[0]),
            "private_test": _sha_file(root / ".meta/task_private_test.cpp"),
            "negative_fixture": _sha_file(root / ".meta/negative_false_substitute.cpp"),
            "config": _sha_file(root / ".meta/config.json"),
            "provenance": _sha_file(root / ".meta/provenance.json"),
        }
        candidate_tokens[case.task_id] = _normalize(_corpus(root))
        profiles[case.task_id] = {
            name: {"hash": row["hash"], "token_count": len(row["tokens"])}
            for name, row in _dimension_profiles(root).items()
        }
    pairs = []
    sorted_roots = sorted(roots)
    for index, left in enumerate(sorted_roots):
        for right in sorted_roots[index + 1 :]:
            decision = _pair_decision(left, right)
            if not decision["pass"]:
                failed = [name for name, row in decision["dimensions"].items() if not row["different"]]
                _fail("duplicate_family", f"{left.name}:{right.name}:{','.join(failed)}")
            pairs.append(decision)
    if len(pairs) != EXPECTED_ROOTS * (EXPECTED_ROOTS - 1) // 2:
        _fail("duplicate_family", "pair inventory")
    controls = _materialize_controls(out)
    cross_tree = _cross_tree_screen(out, candidate_tokens)
    holdouts = _holdout_screen(candidate_tokens)
    diversity_report = {
        "schema_version": "aider-seven-dimension-diversity-v1",
        "normalizer": NORMALIZER,
        "root_count": len(roots),
        "pair_count": len(pairs),
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "pairs": pairs,
        "controls": controls,
        "status": "pass",
    }
    subject = {
        "family_id": FAMILY_ID,
        "owner_hash": _owner_hash(),
        "normalizer": NORMALIZER,
        "curriculum_hash": _sha_file(Path(CURRICULUM)),
        "family_spec_hash": _sha_file(Path(FAMILY_SPEC)),
        "count_plan_hash": _sha_file(Path(COUNT_PLAN)),
        "source_inventory_hash": _sha_file(out / ".state/source-inventory.json"),
        "candidate_manifest_hash": _sha_file(out / ".state/candidate-manifest.json"),
        "rejected_candidates_hash": _sha_file(out / ".state/rejected-candidates.json"),
        "cross_tree_screen_hash": _sha_bytes(
            json.dumps(cross_tree, sort_keys=True, separators=(",", ":")).encode()
        ),
        "benchmark_screen_hash": _sha_bytes(
            json.dumps(holdouts, sort_keys=True, separators=(",", ":")).encode()
        ),
        "diversity_report_hash": _sha_bytes(
            (json.dumps(diversity_report, indent=2, sort_keys=True) + "\n").encode()
        ),
        "task_tree_hashes": {root.name: _tree_hash(root) for root in roots},
        "prompt_hashes": prompt_hashes,
        "reference_hashes": reference_hashes,
        "test_hashes": test_hashes,
        "artifact_hashes": artifact_hashes,
    }
    subject_hash = _sha_bytes(json.dumps(subject, sort_keys=True, separators=(",", ":")).encode())
    manifest = {
        "schema_version": SCHEMA,
        "family_id": FAMILY_ID,
        "status": "creator_core_preflight_passed",
        "root_count": len(roots),
        "architecture_count": len(ARCHITECTURES),
        "operation_count": len(OPERATIONS),
        "pair_count": len(pairs),
        "hard_rule_dimensions": list(HARD_RULE_DIMENSIONS),
        "hard_rule_status": "pass",
        "profiles": profiles,
        "pair_decisions": pairs,
        "adversarial_controls": controls,
        "cross_tree_screen": cross_tree,
        "benchmark_screen": holdouts,
        "prompt_boundary": "pass",
        "reference_mapping": "pass",
        "negative_fixture_execution": "pending docker creator preflight",
        "oracle": "pending docker creator preflight",
        "audit_subject": subject,
        "audit_subject_hash": subject_hash,
        "audit_subject_stage": "core_preflight_pending_docker",
        "dataset_handoff": "not_requested",
    }
    _json(out / ".state/materialization-manifest.json", manifest)
    _json(out / ".state/diversity-report.json", diversity_report)
    return manifest


def _deterministic_archive(out: Path, destination: Path) -> str:
    entries = [(Path(case.task_id), out / case.task_id) for case in CASES]
    controls = out / ".state/adversarial-controls"
    entries.extend((Path(".controls") / path.name, path) for path in sorted(controls.iterdir()) if path.is_dir())
    with tarfile.open(destination, "w") as archive:
        for prefix, root in entries:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                data = path.read_bytes()
                info = tarfile.TarInfo((prefix / path.relative_to(root)).as_posix())
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return _sha_file(destination)


def _preflight_cycle(out: Path) -> int:
    cycles = out / ".state/cycles"
    paths = sorted(cycles.glob("cycle-*.json")) if cycles.is_dir() else []
    if not paths:
        return 1
    latest = json.loads(paths[-1].read_text(encoding="utf-8"))
    if latest.get("status") in {"audit_findings", "creator_subject_invalidated"}:
        return int(latest["cycle"]) + 1
    _fail("stale_cycle_manifest", f"latest cycle is {latest.get('status')}")


def _remedy_paths(out: Path) -> list[Path]:
    remedy = out / ".state/remedy"
    if not remedy.is_dir():
        return []
    paths = sorted(remedy.glob("qr-*.json"))
    if paths and len(paths) != EXPECTED_ROOTS:
        _fail("remedy_spec_incomplete", f"expected {EXPECTED_ROOTS}, found {len(paths)}")
    return paths


def docker_sanity(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    manifest = verify_core(out)
    cycle_number = _preflight_cycle(out)
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
    image_id = inspected.stdout.strip()
    with tempfile.TemporaryDirectory(prefix="quoted-records-docker-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        results = temp / "results"
        results.mkdir()
        archive_hash = _deterministic_archive(out, archive)
        runner = r'''set -eu
mkdir -p /tmp/family
tar -xf /input/family.tar -C /tmp/family
: > /result/counts.tsv
: > /result/negatives.tsv
: > /result/controls.tsv
c++ --version | head -1 > /result/compiler.txt
cmake --version | head -1 > /result/cmake.txt
command -v c++ | xargs sha256sum | awk '{print "sha256:" $1}' > /result/compiler.sha256
for root in /tmp/family/qr-*; do
 task=$(basename "$root")
 for mode in normal sanitizer; do
  build="/tmp/build-${task}-${mode}"
  if [ "$mode" = sanitizer ]; then
   cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"
  else
   cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp"
  fi
  cmake --build "$build" --parallel 2
  count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: *\([0-9][0-9]*\).*/\1/p')
  test -n "$count" && test "$count" -gt 0
  ctest --test-dir "$build" --output-on-failure
  printf '%s\t%s\t%s\n' "$task" "$mode" "$count" >> /result/counts.tsv
 done
 for nmode in normal sanitizer; do
  negative="/tmp/build-${task}-negative-${nmode}"
  if [ "$nmode" = sanitizer ]; then
   cmake -S "$root" -B "$negative" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"
  else
   cmake -S "$root" -B "$negative" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp"
  fi
  cmake --build "$negative" --parallel 2
  ncount=$(ctest --test-dir "$negative" -N | sed -n 's/.*Total Tests: *\([0-9][0-9]*\).*/\1/p')
  set +e; ctest --test-dir "$negative" --output-on-failure; code=$?; set -e
  test "$ncount" -gt 0 && test "$code" -ne 0
  printf '%s\t%s\t%s\t%s\n' "$task" "$nmode" "$ncount" "$code" >> /result/negatives.tsv
 done
done
for root in /tmp/family/.controls/*; do
 name=$(basename "$root")
 for mode in normal sanitizer; do
  build="/tmp/build-control-${name}-${mode}"
  if [ "$mode" = sanitizer ]; then
   cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"
  else
   cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp"
  fi
  cmake --build "$build" --parallel 2
  count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: *\([0-9][0-9]*\).*/\1/p')
  ctest --test-dir "$build" --output-on-failure
  printf '%s\t%s\t%s\n' "$name" "$mode" "$count" >> /result/controls.tsv
 done
done
sha256sum /input/family.tar | awk '{print "sha256:" $1}' > /result/archive.sha256
'''
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
            failure_root = out / ".state/failed-preflights"
            failure_root.mkdir(parents=True, exist_ok=True)
            attempt = len(list(failure_root.glob(f"cycle-{cycle_number:02d}-attempt-*.log"))) + 2
            failure_log = failure_root / f"cycle-{cycle_number:02d}-attempt-{attempt:02d}.log"
            _write(failure_log, run.stdout, force=True)
            _json(
                failure_log.with_suffix(".json"),
                {
                    "schema_version": "aider-creator-preflight-failure-v1",
                    "cycle": cycle_number,
                    "attempt": attempt,
                    "status": "failed",
                    "failure_code": "docker_sanity_failed",
                    "image_id": image_id,
                    "network_policy": "none",
                    "log": failure_log.relative_to(out).as_posix(),
                    "log_hash": _sha_file(failure_log),
                    "terminal": False,
                },
            )
            _fail("docker_sanity_failed", run.stdout[-12000:])
        mounted_hash = (results / "archive.sha256").read_text(encoding="utf-8").strip()
        if mounted_hash != archive_hash:
            _fail("grader_mount_hash_mismatch", f"owner={archive_hash} docker={mounted_hash}")
        counts: dict[str, dict[str, int]] = {}
        for line in (results / "counts.tsv").read_text(encoding="utf-8").splitlines():
            task_id, mode, raw = line.split("\t")
            counts.setdefault(task_id, {})[mode] = int(raw)
        expected = {case.task_id for case in CASES}
        if set(counts) != expected:
            _fail("test_discovery_failed", f"received {len(counts)} of {len(expected)} roots")
        for task_id, modes in counts.items():
            if modes.get("normal", 0) <= 0 or modes.get("normal") != modes.get("sanitizer"):
                _fail("sanitizer_test_count_mismatch", task_id)
        negatives: dict[str, dict[str, object]] = {}
        for line in (results / "negatives.tsv").read_text(encoding="utf-8").splitlines():
            task_id, mode, raw_count, raw_code = line.split("\t")
            negatives.setdefault(task_id, {})[mode] = {
                "compiled": True,
                "discovered_tests": int(raw_count),
                "ctest_exit": int(raw_code),
                "rejected_by_executed_tests": int(raw_code) != 0,
            }
        if set(negatives) != expected or any(
            set(row) != {"normal", "sanitizer"}
            or row["normal"]["discovered_tests"] <= 0
            or row["normal"]["discovered_tests"]
            != row["sanitizer"]["discovered_tests"]
            or not row["normal"]["rejected_by_executed_tests"]
            or not row["sanitizer"]["rejected_by_executed_tests"]
            for row in negatives.values()
        ):
            _fail("invariant_not_enforced", "negative fixture inventory")
        control_counts: dict[str, dict[str, int]] = {}
        for line in (results / "controls.tsv").read_text(encoding="utf-8").splitlines():
            name, mode, raw = line.split("\t")
            control_counts.setdefault(name, {})[mode] = int(raw)
        expected_controls = {
            "domain-identifier-renamed-clone",
            "constants-policy-only-clone",
            "opposite-end-selection-clone",
        }
        if set(control_counts) != expected_controls or any(
            row.get("normal", 0) <= 0 or row.get("normal") != row.get("sanitizer")
            for row in control_counts.values()
        ):
            _fail("adversarial_control_not_pure", "runtime inventory")
        receipt = {
            "schema_version": "aider-quoted-nested-records-docker-sanity-v1",
            "cycle": cycle_number,
            "status": "pass",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "image_id": image_id,
            "archive_hash": archive_hash,
            "owner_hash": _owner_hash(),
            "compiler": (results / "compiler.txt").read_text(encoding="utf-8").strip(),
            "compiler_hash": (results / "compiler.sha256").read_text(encoding="utf-8").strip(),
            "cmake": (results / "cmake.txt").read_text(encoding="utf-8").strip(),
            "commands": {
                "docker": command[:10] + ["<owner-controlled-runner>"],
                "normal": "fresh CMake Unix Makefiles reference build plus positive CTest",
                "sanitizer": "fresh ASan/UBSan CMake build plus equal positive CTest",
                "negative": "fresh normal and ASan/UBSan wrong-reducer builds plus executed CTest rejection",
                "controls": "normal and sanitizer behavior passage",
            },
            "task_tree_hashes": {case.task_id: _tree_hash(out / case.task_id) for case in CASES},
            "reference_hashes": {case.task_id: _sha_file(out / case.task_id / ".meta/example.cpp") for case in CASES},
            "test_counts": counts,
            "negative_fixtures": negatives,
            "adversarial_controls": control_counts,
        }
        receipt_name = (
            ".state/creator-preflight-receipt.json"
            if cycle_number == 1
            else f".state/creator-preflight-receipt-cycle-{cycle_number:02d}.json"
        )
        receipt_path = out / receipt_name
        if receipt_path.exists():
            _fail("stale_cycle_manifest", receipt_name)
        _json(receipt_path, receipt)
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    remedy_paths = _remedy_paths(out)
    remediation_receipt_path: Path | None = None
    if cycle_number > 1:
        if len(remedy_paths) != EXPECTED_ROOTS:
            _fail("remedy_spec_incomplete", "cycle requires one remedy per root")
        remedy_rows = []
        for path in remedy_paths:
            record = json.loads(path.read_text(encoding="utf-8"))
            task_id = record.get("task_id")
            if (
                record.get("schema_version") != "aider-task-remedy-v1"
                or record.get("disposition") != "repair-in-place"
                or record.get("status") not in {"planned", "implemented"}
                or task_id not in {case.task_id for case in CASES}
            ):
                _fail("remedy_disposition_conflict", path.name)
            spec_path = out / str(record.get("remedy_spec_path", ""))
            if not spec_path.is_file() or _sha_file(spec_path) != record.get("remedy_spec_hash"):
                _fail("remedy_spec_incomplete", path.name)
            record.update(
                {
                    "status": "implemented",
                    "tree_hash_after": _tree_hash(out / str(task_id)),
                    "generator_revision_after": _owner_hash(),
                    "primary_core_objective": "achieved",
                    "changed_owner_paths": [
                        "src/w8_biayn/integrations/moonlight_quoted_nested_records_cases.py",
                        "src/w8_biayn/integrations/moonlight_quoted_nested_records_aider_tasks.py",
                        "tests/test_moonlight_quoted_nested_records_aider_tasks.py",
                    ],
                    "oracle_evidence": {
                        "image_id": receipt["image_id"],
                        "compiler_hash": receipt["compiler_hash"],
                        "normal_tests": receipt["test_counts"][str(task_id)]["normal"],
                        "sanitizer_tests": receipt["test_counts"][str(task_id)]["sanitizer"],
                        "negative_normal_rejected": receipt["negative_fixtures"][str(task_id)]["normal"]["rejected_by_executed_tests"],
                        "negative_sanitizer_rejected": receipt["negative_fixtures"][str(task_id)]["sanitizer"]["rejected_by_executed_tests"],
                    },
                    "prompt_boundary": "pass",
                    "family_screen": manifest["cross_tree_screen"]["status"],
                    "benchmark_screen": manifest["benchmark_screen"]["status"],
                    "strongest_truthful_status": "semantically_admitted_awaiting_fresh_audit",
                }
            )
            _json(path, record)
            remedy_rows.append(
                {
                    "task_id": task_id,
                    "record": path.relative_to(out).as_posix(),
                    "record_hash": _sha_file(path),
                    "tree_hash_before": record["tree_hash_before"],
                    "tree_hash_after": record["tree_hash_after"],
                    "finding_ids": record["finding_ids"],
                    "disposition": record["disposition"],
                    "status": record["status"],
                }
            )
        remediation_receipt_path = out / f".state/remediation-receipt-cycle-{cycle_number:02d}.json"
        remediation_receipt = {
            "schema_version": "aider-family-remediation-receipt-v1",
            "cycle": cycle_number,
            "family_id": FAMILY_ID,
            "status": "semantically_admitted_awaiting_fresh_audit",
            "creator_preflight_receipt": receipt_name,
            "root_count": len(remedy_rows),
            "rows": remedy_rows,
            "prompt_boundary": "pass",
            "family_screen": manifest["cross_tree_screen"],
            "benchmark_screen": manifest["benchmark_screen"],
            "normal_and_sanitizer": "pass with equal positive discovery",
            "operation_specific_negatives": "pass normal and sanitizer rejection",
            "dataset_handoff": "not_requested",
        }
        _json(remediation_receipt_path, remediation_receipt)
        receipt["remediation_receipt"] = remediation_receipt_path.relative_to(out).as_posix()
        receipt["remediation_receipt_hash"] = _sha_file(remediation_receipt_path)
        _json(receipt_path, receipt)
    grader_policy = {
        "image": image,
        "image_id": image_id,
        "network": "none",
        "normalizer": NORMALIZER,
        "cross_tree_threshold": manifest["cross_tree_screen"]["threshold"],
        "holdout_threshold": manifest["benchmark_screen"]["threshold"],
        "commands": receipt["commands"],
    }
    final_subject = dict(manifest["audit_subject"])
    final_subject.update(
        {
            "creator_preflight_receipt": receipt_name,
            "creator_preflight_receipt_hash": _sha_file(receipt_path),
            "grader_policy": grader_policy,
            "grader_policy_hash": _sha_bytes(
                json.dumps(grader_policy, sort_keys=True, separators=(",", ":")).encode()
            ),
            "image": receipt["image"],
            "image_id": receipt["image_id"],
            "compiler": receipt["compiler"],
            "compiler_hash": receipt["compiler_hash"],
            "cmake": receipt["cmake"],
            "archive_hash": receipt["archive_hash"],
            "remediation_receipt_hash": receipt.get("remediation_receipt_hash"),
        }
    )
    final_subject_hash = _sha_bytes(
        json.dumps(final_subject, sort_keys=True, separators=(",", ":")).encode()
    )
    manifest["status"] = "creator_preflight_passed"
    manifest["negative_fixture_execution"] = "pass"
    manifest["oracle"] = {
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "normal_tests_per_root": 2,
        "sanitizer_tests_per_root": 2,
        "root_count": EXPECTED_ROOTS,
        "receipt": receipt_name,
    }
    manifest["audit_subject"] = final_subject
    manifest["audit_subject_hash"] = final_subject_hash
    manifest["audit_subject_stage"] = "creator_preflight_complete"
    if remediation_receipt_path is not None:
        prior_cycle = json.loads(
            (
                out
                / f".state/cycles/cycle-{cycle_number - 1:02d}.json"
            ).read_text(encoding="utf-8")
        )
        manifest["remediation"] = {
            "status": "semantically_admitted_awaiting_fresh_audit",
            "receipt": remediation_receipt_path.relative_to(out).as_posix(),
            "receipt_hash": _sha_file(remediation_receipt_path),
            "open_finding_ids": prior_cycle["finding_ids"],
        }
    for row in manifest["adversarial_controls"].values():
        row["coherent_runtime"] = "pass normal and fresh sanitizer"
    _json(manifest_path, manifest)
    cycle = {
        "schema_version": "aider-creator-cycle-v1",
        "cycle": cycle_number,
        "family_id": FAMILY_ID,
        "status": "awaiting_independent_audit",
        "requested_count": EXPECTED_ROOTS,
        "retained_count": EXPECTED_ROOTS,
        "candidate_manifest": ".state/candidate-manifest.json",
        "curriculum_hash": _sha_file(Path(CURRICULUM)),
        "generator_hash": _owner_hash(),
        "focused_test_hash": _sha_file(Path("tests/test_moonlight_quoted_nested_records_aider_tasks.py")),
        "generated_tree_subject_hash": manifest["audit_subject_hash"],
        "grader_policy_hash": _sha_bytes(json.dumps({"image": image_id, "network": "none", "normalizer": NORMALIZER}, sort_keys=True).encode()),
        "creator_preflight_receipt": receipt_name,
        "audit_report": None,
        "finding_ids": (
            []
            if cycle_number == 1
            else json.loads(
                (
                    out
                    / f".state/cycles/cycle-{cycle_number - 1:02d}.json"
                ).read_text(encoding="utf-8")
            )["finding_ids"]
        ),
        "remediation": [path.relative_to(out).as_posix() for path in remedy_paths],
        "retained": sorted(case.task_id for case in CASES),
        "replaced": [],
        "rejected": [],
        "review": [],
        "blocked": [],
        "invalidated_evidence": (
            []
            if cycle_number == 1
            else sorted(
                path.relative_to(out).as_posix()
                for pattern in (
                    ".state/creator-preflight-receipt*.json",
                    ".state/remediation-receipt-*.json",
                    ".state/audits/*.json",
                    ".state/failed-preflights/*.json",
                )
                for path in out.glob(pattern)
                if path != receipt_path and path != remediation_receipt_path
            )
        ),
        "terminal_status": None,
    }
    cycles = out / ".state/cycles"
    cycles.mkdir(parents=True, exist_ok=True)
    cycle["compiler"] = receipt["compiler"]
    cycle["compiler_hash"] = receipt["compiler_hash"]
    cycle["image_id"] = receipt["image_id"]
    cycle["cmake"] = receipt["cmake"]
    cycle["network_policy"] = receipt["network_policy"]
    cycle["task_artifact_hashes"] = final_subject["artifact_hashes"]
    cycle["semantic_screen_hashes"] = {
        "cross_tree": final_subject["cross_tree_screen_hash"],
        "holdout": final_subject["benchmark_screen_hash"],
        "diversity": final_subject["diversity_report_hash"],
    }
    cycle_path = cycles / f"cycle-{cycle_number:02d}.json"
    if cycle_path.exists():
        _fail("stale_cycle_manifest", cycle_path.name)
    _json(cycle_path, cycle)
    return receipt


HOST_RECEIPT_NAME = ".state/host-verify-receipt.json"
HOST_SANITIZER_FLAGS = "-fsanitize=address,undefined -fno-omit-frame-pointer"


def _host_build_and_test(
    source_root: Path,
    build_root: Path,
    task_source: Path,
    sanitizer: bool,
    env: dict[str, str],
) -> tuple[int, int]:
    configure = [
        "cmake",
        "-S",
        str(source_root),
        "-B",
        str(build_root),
        "-G",
        "Unix Makefiles",
        "-DCMAKE_CXX_COMPILER=c++",
        f"-DTASK_SOURCE={task_source}",
    ]
    if sanitizer:
        configure += [
            f"-DCMAKE_CXX_FLAGS={HOST_SANITIZER_FLAGS}",
            f"-DCMAKE_EXE_LINKER_FLAGS={HOST_SANITIZER_FLAGS}",
        ]
    for command in (configure, ["cmake", "--build", str(build_root), "--parallel", "2"]):
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        if run.returncode:
            _fail("reference_compile_failed", f"{source_root.name}:{build_root.name}:{run.stdout[-4000:]}")
    discover = subprocess.run(
        ["ctest", "--test-dir", str(build_root), "-N"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    match = re.search(r"Total Tests:\s*(\d+)", discover.stdout)
    count = int(match.group(1)) if match else 0
    run = subprocess.run(
        ["ctest", "--test-dir", str(build_root), "--output-on-failure"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    return count, run.returncode


def verify_host(out: Path = DEFAULT_OUT) -> dict[str, object]:
    manifest = verify_core(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("host_toolchain_not_completed", "cmake or c++ missing")
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1"
    env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    compiler_path = shutil.which("c++") or "c++"
    compiler = subprocess.run(
        ["c++", "--version"], stdout=subprocess.PIPE, text=True
    ).stdout.splitlines()[0].strip()
    compiler_hash = _sha_file(Path(compiler_path))
    cmake_version = subprocess.run(
        ["cmake", "--version"], stdout=subprocess.PIPE, text=True
    ).stdout.splitlines()[0].strip()
    counts: dict[str, dict[str, int]] = {}
    negatives: dict[str, dict[str, object]] = {}
    control_counts: dict[str, dict[str, int]] = {}
    with tempfile.TemporaryDirectory(prefix="quoted-records-host-") as temporary:
        builds = Path(temporary)
        for case in CASES:
            root = out / case.task_id
            modes: dict[str, int] = {}
            negative_modes: dict[str, dict[str, object]] = {}
            for mode, sanitizer in (("normal", False), ("sanitizer", True)):
                count, code = _host_build_and_test(
                    root, builds / f"{case.task_id}-{mode}", root / ".meta/example.cpp", sanitizer, env
                )
                if count <= 0 or code != 0:
                    _fail("reference_tests_failed", f"{case.task_id}:{mode}:count={count}:exit={code}")
                modes[mode] = count
                negative_count, negative_code = _host_build_and_test(
                    root,
                    builds / f"{case.task_id}-negative-{mode}",
                    root / ".meta/negative_false_substitute.cpp",
                    sanitizer,
                    env,
                )
                if negative_count <= 0:
                    _fail("test_discovery_failed", f"{case.task_id}:negative:{mode}")
                if negative_code == 0:
                    _fail("invariant_not_enforced", f"{case.task_id}:negative:{mode}")
                negative_modes[mode] = {
                    "compiled": True,
                    "discovered_tests": negative_count,
                    "ctest_exit": negative_code,
                    "rejected_by_executed_tests": True,
                }
            if modes["normal"] != modes["sanitizer"]:
                _fail("sanitizer_test_count_mismatch", case.task_id)
            if negative_modes["normal"]["discovered_tests"] != negative_modes["sanitizer"]["discovered_tests"]:
                _fail("sanitizer_test_count_mismatch", f"{case.task_id}:negative")
            counts[case.task_id] = modes
            negatives[case.task_id] = negative_modes
        controls_root = out / ".state/adversarial-controls"
        for control in sorted(path for path in controls_root.iterdir() if path.is_dir()):
            modes = {}
            for mode, sanitizer in (("normal", False), ("sanitizer", True)):
                count, code = _host_build_and_test(
                    control,
                    builds / f"control-{control.name}-{mode}",
                    control / ".meta/example.cpp",
                    sanitizer,
                    env,
                )
                if count <= 0 or code != 0:
                    _fail("adversarial_control_not_pure", f"{control.name}:{mode}:count={count}:exit={code}")
                modes[mode] = count
            if modes["normal"] != modes["sanitizer"]:
                _fail("sanitizer_test_count_mismatch", f"control:{control.name}")
            control_counts[control.name] = modes
    expected_controls = {
        "domain-identifier-renamed-clone",
        "constants-policy-only-clone",
        "opposite-end-selection-clone",
    }
    if set(control_counts) != expected_controls:
        _fail("adversarial_control_not_pure", "host runtime inventory")
    receipt = {
        "schema_version": "aider-quoted-nested-records-host-verify-v1",
        "status": "pass",
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "network_policy": "host process without container; campaign gate is host verify only",
        "owner_hash": _owner_hash(),
        "audit_subject_hash": manifest["audit_subject_hash"],
        "task_tree_hashes": {case.task_id: _tree_hash(out / case.task_id) for case in CASES},
        "reference_hashes": {
            case.task_id: _sha_file(out / case.task_id / ".meta/example.cpp") for case in CASES
        },
        "compiler": compiler,
        "compiler_path": compiler_path,
        "compiler_hash": compiler_hash,
        "cmake": cmake_version,
        "commands": {
            "normal": "fresh CMake Unix Makefiles reference build plus positive CTest",
            "sanitizer": "fresh ASan/UBSan CMake build plus equal positive CTest",
            "negative": "fresh normal and ASan/UBSan wrong-reducer builds plus executed CTest rejection",
            "controls": "normal and sanitizer behavior passage",
        },
        "test_counts": counts,
        "negative_fixtures": negatives,
        "adversarial_controls": control_counts,
    }
    receipt_path = out / HOST_RECEIPT_NAME
    _json(receipt_path, receipt)
    manifest["host_verify"] = {
        "status": "pass",
        "evidence_class": "host_verify",
        "receipt": HOST_RECEIPT_NAME,
        "receipt_hash": _sha_file(receipt_path),
        "root_count": EXPECTED_ROOTS,
        "note": "campaign gate is host verify only; docker sanity evidence stays in creator-preflight receipts",
    }
    _json(out / ".state/materialization-manifest.json", manifest)
    return receipt


def record_audit(out: Path, report_path: Path) -> dict[str, object]:
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema_version") != "aider-family-independent-audit-v1":
        _fail("audit_report_invalid", "schema")
    if report.get("subject_hash") != manifest.get("audit_subject_hash"):
        _fail("audit_report_invalid", "subject hash")
    if report.get("root_count") != EXPECTED_ROOTS:
        _fail("audit_report_invalid", "root count")
    if report.get("audit_mode") != "independent-read-only":
        _fail("audit_report_invalid", "audit mode")
    findings = report.get("findings")
    if report.get("status") != "clean" or findings != []:
        _fail("audit_findings_open", json.dumps(findings, sort_keys=True))
    dispositions = report.get("dispositions", {})
    if set(dispositions) != {case.task_id for case in CASES} or set(dispositions.values()) != {"retain"}:
        _fail("audit_report_invalid", "dispositions")
    matching_cycles = []
    for candidate in sorted((out / ".state/cycles").glob("cycle-*.json")):
        value = json.loads(candidate.read_text(encoding="utf-8"))
        if value.get("generated_tree_subject_hash") == report["subject_hash"]:
            matching_cycles.append(candidate)
    if len(matching_cycles) != 1:
        _fail("audit_report_invalid", "cycle binding")
    cycle_path = matching_cycles[0]
    cycle = json.loads(cycle_path.read_text(encoding="utf-8"))
    if report.get("audit_cycle") != cycle.get("cycle"):
        _fail("audit_report_invalid", "cycle number")
    if cycle.get("finding_ids"):
        if sorted(report.get("resolved_finding_ids", [])) != sorted(cycle["finding_ids"]):
            _fail("audit_report_invalid", "resolved findings")
    cycle["status"] = "local_family_verified"
    cycle["audit_report"] = report_path.relative_to(out).as_posix()
    cycle["audit_report_hash"] = _sha_file(report_path)
    cycle["resolved_finding_ids"] = list(cycle.get("finding_ids", []))
    cycle["terminal_status"] = "local_family_verified"
    _json(cycle_path, cycle)
    for path in _remedy_paths(out):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") != "implemented":
            _fail("remedy_disposition_conflict", path.name)
        record.update(
            {
                "status": "verified",
                "fresh_audit_report": report_path.relative_to(out).as_posix(),
                "fresh_audit_report_hash": _sha_file(report_path),
                "resolved_finding_ids": record["finding_ids"],
                "strongest_truthful_status": "local_family_verified",
            }
        )
        _json(path, record)
    manifest["status"] = "local_family_verified"
    manifest["fresh_independent_audit"] = {
        "status": "clean",
        "report": report_path.relative_to(out).as_posix(),
        "report_hash": _sha_file(report_path),
        "subject_hash": report["subject_hash"],
        "findings": [],
    }
    if "remediation" in manifest:
        manifest["remediation"]["status"] = "local_family_verified"
        manifest["remediation"]["resolved_finding_ids"] = list(
            cycle.get("resolved_finding_ids", [])
        )
    _json(manifest_path, manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    parser.add_argument("--record-audit", type=Path)
    args = parser.parse_args(argv)
    if args.record_audit:
        record_audit(args.out, args.record_audit)
        print(f"Recorded clean independent audit for {EXPECTED_ROOTS} roots under {args.out}")
        return 0
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    print(f"Wrote {len(roots)} quoted/nested record tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
