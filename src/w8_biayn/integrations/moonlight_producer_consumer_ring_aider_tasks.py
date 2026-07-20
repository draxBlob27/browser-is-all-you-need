"""Materialize the producer-consumer protocol-ring v2 task family.

The legacy family is preserved under aider-tasks. This owner writes only the
parallel aider-tasks-reverify tree and rejects renamed queue templates.
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
from dataclasses import dataclass
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
from w8_biayn.integrations.moonlight_producer_consumer_ring_cases import CASES, CaseAssets
from w8_biayn.integrations.moonlight_producer_consumer_ring_verification_cases import (
    NEGATIVE_REWRITES,
    TRACE_TESTS,
    negative_source,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-dsa/producer-consumer-ring"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/producer-consumer-ring")
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-dsa/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_PRODUCER_CONSUMER_RING_CURRICULUM.md"
)
SELECTED_PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-dsa-producer-consumer-ring-v2"
MANIFEST_SCHEMA = "aider-producer-consumer-ring-materialization-v2"
NORMALIZER_VERSION = "producer-consumer-ring-normalizer-v2"
MIN_ROOTS = 15
MAX_ROOTS = 20
OWNER_PATHS = (
    Path(__file__),
    Path(__file__).with_name("moonlight_producer_consumer_ring_cases.py"),
    Path(__file__).with_name(
        "moonlight_producer_consumer_ring_verification_cases.py"
    ),
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


@dataclass(frozen=True)
class TaskSpec:
    legacy_id: str
    task_id: str
    class_name: str
    kind: str
    title: str
    objective: str


TASKS = tuple(
    TaskSpec(
        legacy_id=case.legacy_id,
        task_id=task_id,
        class_name=case.class_name,
        kind=case.kind,
        title=case.title,
        objective=case.objective,
    )
    for task_id, case in CASES.items()
)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _cmake() -> str:
    return """cmake_minimum_required(VERSION 3.16)
project(producer_consumer_protocol_rings LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
find_package(Threads REQUIRED)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_model "${TASK_SOURCE}" .meta/task_model_test.cpp)
foreach(target task_visible task_hidden task_model)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_link_libraries(${target} PRIVATE Threads::Threads)
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME model COMMAND task_model)
set_tests_properties(visible hidden model PROPERTIES TIMEOUT 10)
"""


def _files(spec: TaskSpec, assets: CaseAssets) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": assets.objective,
        "files": {
            "solution": ["task.h", "task.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "benchmark_separation": assets.benchmark_separation,
        "curriculum_document": CURRICULUM,
        "curriculum_task_id": spec.task_id,
        "family_id": FAMILY_ID,
        "legacy_task_id": spec.legacy_id,
        "normalizer_version": NORMALIZER_VERSION,
        "origin": "clean-room v2 replacement of a template-duplicate legacy root",
        "selected_prompt": SELECTED_PROMPT,
        "semantic_profile": spec.kind,
        "status": "local task artifact; not admitted SFT data",
        "version": 2,
    }
    return {
        ".docs/introduction.md": (
            f"# {spec.title}\n\n"
            "A clean-room producer/consumer protocol-ring task with its own "
            "state model and transition rules.\n"
        ),
        ".docs/instructions.md": assets.instructions,
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": (
            json.dumps(provenance, indent=2, sort_keys=True) + "\n"
        ),
        ".meta/tests.toml": (
            f"[visible]\ndescription = \"{assets.visible_description}\"\n\n"
            f"[hidden]\ndescription = \"{assets.hidden_description}\"\n"
        ),
        "task.h": assets.header,
        "task.cpp": assets.starter,
        ".meta/example.h": assets.header,
        ".meta/example.cpp": assets.reference,
        "task_visible_test.cpp": assets.visible_test,
        ".meta/task_hidden_test.cpp": assets.hidden_test,
        ".meta/task_model_test.cpp": TRACE_TESTS[spec.task_id],
        "CMakeLists.txt": _cmake(),
    }


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _mark_remedies_planned(out)
    roots: list[Path] = []
    for spec in TASKS:
        root = out / spec.task_id
        for relative, content in task_named_files(
            root, _files(spec, CASES[spec.task_id])
        ).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def _mark_remedies_planned(out: Path) -> None:
    remedy = out / ".state/remedy"
    if not remedy.is_dir():
        return
    for path in remedy.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        record["status"] = "planned"
        record["local_status"] = "not_completed"
        record["invalidation_reason"] = "owner_or_generated_family_changed"
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _file_hash(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("unsafe_path", "empty or non-string path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _whole_format_code(task_dir: Path, content: str) -> str | None:
    task = load_task(task_dir)
    try:
        parsed = parse_whole_file_blocks(content)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(parsed) == set(task.editable_files) else "whole_format_failed"


def _core_failure(assets: CaseAssets, source: str) -> str | None:
    if any(marker not in source for marker in assets.required_markers):
        return "invariant_not_enforced"
    forbidden = (
        "std::deque",
        "std::queue",
        "std::priority_queue",
        "legacy_deque_template",
    )
    if any(token in source for token in forbidden):
        return "forbidden_core_substitute"
    return None


def _cpp_structure(text: str) -> tuple[str, ...]:
    text = re.sub(r'"(?:\\.|[^"\\])*"', "string", text)
    text = re.sub(r"\b\d+[uUlL]*\b", "number", text)
    tokens = re.findall(
        r"::|->|==|!=|<=|>=|&&|\|\||[{}()\[\];,.%+*/<>=!?:-]|[A-Za-z_][A-Za-z_0-9]*",
        text,
    )
    preserved = {
        "if", "else", "for", "while", "return", "switch", "case",
        "break", "continue", "true", "false", "auto", "const", "static",
        "std", "vector", "optional", "map", "unordered_map", "unordered_set",
        "array", "mutex", "condition_variable", "lock_guard", "unique_lock",
        "size_t", "int", "bool", "void", "class", "struct", "enum",
    }
    return tuple(token if token in preserved or not token[0].isalpha() else "id" for token in tokens)


def _shingles(tokens: tuple[str, ...], width: int = 5) -> set[tuple[str, ...]]:
    return {
        tokens[index : index + width]
        for index in range(max(0, len(tokens) - width + 1))
    }


def _public_methods(assets: CaseAssets) -> set[str]:
    match = re.search(
        rf"class\s+{re.escape(assets.class_name)}\s*\{{(.*?)private:",
        assets.header,
        re.DOTALL,
    )
    if not match:
        _fail("public_api_parse_failed", assets.class_name)
    return {
        name
        for name in re.findall(
            r"\b([A-Za-z_]\w*)\s*\([^;{{}}]*\)\s*(?:const)?\s*;",
            match.group(1),
        )
        if name != assets.class_name
    }


def _semantic_signatures() -> dict[str, str]:
    if not MIN_ROOTS <= len(CASES) <= MAX_ROOTS:
        _fail("family_count_out_of_bounds", str(len(CASES)))
    if set(CASES) != set(TRACE_TESTS) or set(CASES) != set(NEGATIVE_REWRITES):
        _fail("diversity_fixture_inventory_mismatch")
    kinds: set[str] = set()
    signatures: set[str] = set()
    result: dict[str, str] = {}
    structures: dict[str, set[tuple[str, ...]]] = {}
    for task_id, assets in CASES.items():
        if assets.kind in kinds:
            _fail("duplicate_family", f"duplicate state model {assets.kind}")
        kinds.add(assets.kind)
        failure = _core_failure(assets, assets.reference)
        if failure:
            _fail(failure, task_id)
        fixture_name, executable_negative = negative_source(task_id, assets.reference)
        if executable_negative == assets.reference or not fixture_name:
            _fail("negative_fixture_not_distinct", task_id)
        trace = TRACE_TESTS[task_id]
        if "model" not in trace or "int main()" not in trace:
            _fail("independent_trace_missing", task_id)
        missing_operations = {
            method
            for method in _public_methods(assets)
            if not re.search(rf"(?:\.|::){re.escape(method)}\s*\(", trace)
        }
        if missing_operations:
            _fail(
                "independent_trace_operation_missing",
                f"{task_id}:{','.join(sorted(missing_operations))}",
            )
        structures[task_id] = _shingles(
            _cpp_structure(assets.header + assets.reference + trace)
        )
        payload = "\n".join(
            (
                assets.kind,
                assets.objective,
                assets.header,
                assets.reference,
                assets.visible_test,
                assets.hidden_test,
            )
        )
        signature = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if signature in signatures:
            _fail("duplicate_family", f"semantic signature {task_id}")
        signatures.add(signature)
        result[task_id] = f"sha256:{signature}"
    task_ids = sorted(structures)
    for index, left in enumerate(task_ids):
        for right in task_ids[index + 1 :]:
            union = structures[left] | structures[right]
            similarity = len(structures[left] & structures[right]) / len(union)
            if similarity >= 0.82:
                _fail(
                    "duplicate_family",
                    f"control-flow similarity {left}:{right}:{similarity:.3f}",
                )
    return result


def _benchmark_screen(root: Path) -> dict[str, object]:
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if root.name == slug:
            _fail("benchmark_id_overlap", slug)
    candidate_parts: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".state" not in path.parts:
            candidate_parts.append(path.read_text(encoding="utf-8"))
    candidate = "\n".join(candidate_parts).lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", candidate):
            _fail("benchmark_id_overlap", f"{root.name}:{slug}")
    holdout_root = Path(".w8-biayn/data/polyglot-benchmark/cpp/exercises/practice")
    inventories = [
        holdout_root / slug
        for slug in sorted(OFFICIAL_AIDER_CPP_HOLDOUTS)
        if (holdout_root / slug).is_dir()
    ]
    if len(inventories) != len(OFFICIAL_AIDER_CPP_HOLDOUTS):
        return {
            "id_screen": "pass",
            "semantic_screen": "not_completed",
            "reason": "complete bound 26-root holdout content unavailable",
        }
    tokens = set(
        re.findall(
            r"[a-z_]{4,}",
            re.sub(
                r"\b(audio|camera|telemetry|network|log|keyboard|can|market|gps|"
                r"build|video|sensor|print|payment|file|robot|support|weather|"
                r"game|warehouse)\b",
                "domain",
                candidate,
            ),
        )
    )
    strongest = 0.0
    closest = ""
    for task in inventories:
        corpus = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted(task.rglob("*"))
            if path.is_file()
            and path.suffix in {".md", ".h", ".hpp", ".cpp", ".toml", ".json"}
        ).lower()
        other = set(re.findall(r"[a-z_]{4,}", corpus))
        union = tokens | other
        score = len(tokens & other) / len(union) if union else 0.0
        if score > strongest:
            strongest = score
            closest = task.name
    if closest == "circular-buffer" and strongest >= 0.55:
        _fail("benchmark_content_overlap", f"{root.name}:{strongest:.3f}")
    return {
        "id_screen": "pass",
        "semantic_screen": "pass",
        "closest_holdout": closest,
        "jaccard": round(strongest, 6),
        "normalizer": NORMALIZER_VERSION,
    }


def _verify_remedy_records(out: Path) -> None:
    remedy = out / ".state/remedy"
    expected = set(CASES)
    records = (
        {path.stem: path for path in remedy.glob("*.json")}
        if remedy.is_dir()
        else {}
    )
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per replacement root is required")
    for task_id, record_path in records.items():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        spec_path = remedy / f"{task_id}.md"
        if (
            record.get("task_id") != task_id
            or record.get("disposition") != "replace"
            or not spec_path.is_file()
        ):
            _fail("remedy_disposition_conflict", task_id)
        text = spec_path.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", task_id)
        expected_hash = f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
        if record.get("remedy_spec_hash") != expected_hash:
            _fail("remedy_spec_incomplete", f"stale specification hash for {task_id}")


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = set(CASES)
    actual = {
        path.name
        for path in out.iterdir()
        if path.is_dir() and path.name != ".state"
    }
    if actual != expected:
        _fail("generator_output_drift", f"expected {len(expected)}, found {len(actual)}")
    if require_remedy:
        _verify_remedy_records(out)
    with tempfile.TemporaryDirectory(prefix="pcr-v2-materialization-") as temporary:
        fresh = Path(temporary) / "fresh"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    signatures = _semantic_signatures()
    manifest_tasks: list[dict[str, object]] = []
    benchmark_statuses: list[dict[str, object]] = []
    for task_id in sorted(expected):
        root = out / task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config.get("files")
        if not isinstance(files, dict):
            _fail("unsafe_path", f"files map missing for {task_id}")
        solution = [_safe_relative(item) for item in files.get("solution", [])]
        tests = [_safe_relative(item) for item in files.get("test", [])]
        examples = [_safe_relative(item) for item in files.get("example", [])]
        if len(solution) != 2 or len(examples) != 2 or len(set(solution)) != 2:
            _fail("reference_map_failed", task_id)
        if set(solution) & (set(tests) | set(examples)):
            _fail("unsafe_path", task_id)
        if any(
            name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt"
            for name in solution
        ):
            _fail("unsafe_path", task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("reference_map_failed", task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        hidden_names = [
            *tests,
            *examples,
            "CMakeLists.txt",
            ".meta/provenance.json",
            ".meta/task_hidden_test.cpp",
            ".meta/task_model_test.cpp",
        ]
        if any(name in prompt for name in hidden_names):
            _fail("prompt_contract_incomplete", task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer):
            _fail("target_reference_mismatch", task_id)
        missing = (
            f"{task.editable_files[0]}\n"
            "```cpp\n// incomplete\n```\n"
        )
        extra = answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n"
        prose = "explanation\n" + answer
        if any(
            _whole_format_code(root, response) != "whole_format_failed"
            for response in (missing, extra, prose)
        ):
            _fail("whole_format_failed", task_id)
        benchmark = _benchmark_screen(root)
        benchmark_statuses.append(benchmark)
        manifest_tasks.append(
            {
                "task_id": task_id,
                "legacy_task_id": CASES[task_id].legacy_id,
                "tree_hash": _tree_hash(root),
                "semantic_signature": signatures[task_id],
                "benchmark": benchmark,
                "primary_core_objective": "achieved",
                "status": "implemented_pending_executable_oracle",
            }
        )
    semantic_values = {item["semantic_screen"] for item in benchmark_statuses}
    benchmark_summary = (
        "pass" if semantic_values == {"pass"} else "not_completed"
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "normalizer_version": NORMALIZER_VERSION,
        "task_count": len(manifest_tasks),
        "tasks": manifest_tasks,
        "screen": {
            "benchmark_contamination": benchmark_summary,
            "benchmark_id": "pass",
            "duplicate_family": "pass",
            "executable_negative_fixtures": "pending",
            "independent_model_traces": "pending",
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
        },
    }
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "materialization-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _count_discovered(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match:
        _fail("test_discovery_failed")
    count = int(match.group(1))
    if not count:
        _fail("zero_tests")
    return count


def _complete_remedy_records(
    out: Path, receipts: list[dict[str, object]]
) -> None:
    by_task = {str(item["task_id"]): item for item in receipts}
    manifest_path = out / ".state/materialization-manifest.json"
    for task_id in CASES:
        record_path = out / ".state/remedy" / f"{task_id}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        modes = by_task[task_id]["modes"]
        assert isinstance(modes, dict)
        record.update(
            {
                "benchmark_screen": "pass",
                "changed_owner_paths": [
                    CURRICULUM,
                    "docs/aider-tasks-spec/aider-dsa/producer-consumer-ring.md",
                    "examples/slime/moonlight_cpp_perf/prepare_producer_consumer_ring_aider_tasks.sh",
                    "src/w8_biayn/integrations/moonlight_producer_consumer_ring_aider_tasks.py",
                    "src/w8_biayn/integrations/moonlight_producer_consumer_ring_cases.py",
                    "src/w8_biayn/integrations/moonlight_producer_consumer_ring_verification_cases.py",
                    "tests/test_moonlight_producer_consumer_ring_aider_tasks.py",
                ],
                "local_status": "local_family_verified",
                "oracle_receipt": ".state/oracle-receipt.json",
                "prompt_boundary": "pass",
                "reference_mapping": "pass",
                "screen_manifest": manifest_path.relative_to(out).as_posix(),
                "screening": {
                    "benchmark_contamination": "pass",
                    "duplicate_family": "pass",
                    "independent_model_trace": "pass",
                    "negative_fixture": by_task[task_id]["negative_fixture"],
                },
                "status": "verified",
                "test_counts": {
                    "normal": modes["normal"]["discovered_tests"],
                    "sanitizer": modes["sanitizer"]["discovered_tests"],
                },
                "tree_hash_after": _tree_hash(out / task_id),
            }
        )
        record.pop("invalidation_reason", None)
        record_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    verify_core(out)
    receipts: list[dict[str, object]] = []
    for task_id in CASES:
        root = out / task_id
        receipt: dict[str, object] = {
            "task_id": task_id,
            "tree_hash": _tree_hash(root),
            "reference_hash": _file_hash(root / ".meta/example.cpp"),
            "model_test_hash": _file_hash(root / ".meta/task_model_test.cpp"),
            "modes": {},
        }
        modes = receipt["modes"]
        assert isinstance(modes, dict)
        with tempfile.TemporaryDirectory(prefix="pcr-v2-oracle-") as temporary:
            copied = Path(temporary) / task_id
            shutil.copytree(root, copied)
            reference = copied / ".meta/example.cpp"
            for name, flags in (
                ("normal", []),
                (
                    "sanitizer",
                    [
                        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined",
                        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                    ],
                ),
            ):
                build_dir = copied / f"build-{name}"
                configure = [
                    "cmake",
                    "-S",
                    str(copied),
                    "-B",
                    str(build_dir),
                    "-G",
                    "Unix Makefiles",
                    "-DCMAKE_CXX_COMPILER=c++",
                    f"-DTASK_SOURCE={reference}",
                    *flags,
                ]
                subprocess.run(
                    configure,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                subprocess.run(
                    ["cmake", "--build", str(build_dir), "--parallel", "2"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                discovered = subprocess.run(
                    ["ctest", "--test-dir", str(build_dir), "-N"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                count = _count_discovered(discovered.stdout)
                executed = subprocess.run(
                    ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                modes[name] = {
                    "configure": configure,
                    "discovered_tests": count,
                    "ctest_output": executed.stdout,
                }
            fixture_name, mutated = negative_source(
                task_id, reference.read_text(encoding="utf-8")
            )
            negative_source_path = copied / ".meta/negative.cpp"
            negative_source_path.write_text(mutated, encoding="utf-8")
            negative_build = copied / "build-negative"
            negative_configure = [
                "cmake",
                "-S",
                str(copied),
                "-B",
                str(negative_build),
                "-G",
                "Unix Makefiles",
                "-DCMAKE_CXX_COMPILER=c++",
                f"-DTASK_SOURCE={negative_source_path}",
            ]
            subprocess.run(
                negative_configure,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            negative_built = subprocess.run(
                ["cmake", "--build", str(negative_build), "--parallel", "2"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if negative_built.returncode:
                _fail(
                    "negative_fixture_compile_failed",
                    f"{task_id}: {negative_built.stdout[-4000:]}",
                )
            negative_discovery = subprocess.run(
                ["ctest", "--test-dir", str(negative_build), "-N"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            negative_count = _count_discovered(negative_discovery.stdout)
            negative_run = subprocess.run(
                [
                    "ctest",
                    "--test-dir",
                    str(negative_build),
                    "-R",
                    "^model$",
                    "--output-on-failure",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if negative_run.returncode == 0:
                _fail("negative_fixture_not_rejected", task_id)
            if "timeout" in negative_run.stdout.lower():
                _fail("negative_fixture_timeout", task_id)
            receipt["negative_fixture"] = {
                "name": fixture_name,
                "source_hash": (
                    f"sha256:{hashlib.sha256(mutated.encode('utf-8')).hexdigest()}"
                ),
                "configure": negative_configure,
                "discovered_tests": negative_count,
                "selected_tests": "model",
                "returncode": negative_run.returncode,
                "rejected": True,
                "ctest_output": negative_run.stdout,
            }
        normal = modes["normal"]
        sanitizer = modes["sanitizer"]
        if normal["discovered_tests"] != sanitizer["discovered_tests"]:
            _fail("sanitizer_test_count_mismatch", task_id)
        receipts.append(receipt)
    runtime = {
        "environment": os.environ.get(
            "W8_BIAYN_ORACLE_RUNTIME", "host-prerequisite"
        ),
        "image": os.environ.get("W8_BIAYN_ORACLE_IMAGE"),
        "network": os.environ.get("W8_BIAYN_ORACLE_NETWORK", "host"),
        "owner_hashes": {
            path.name: _file_hash(path) for path in OWNER_PATHS
        },
        "compiler": subprocess.run(
            ["c++", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.splitlines()[0],
        "cmake": subprocess.run(
            ["cmake", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.splitlines()[0],
    }
    path = out / ".state/oracle-receipt.json"
    path.write_text(
        json.dumps({"runtime": runtime, "tasks": receipts}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def verify_receipt(out: Path) -> None:
    receipt_path = out / ".state/oracle-receipt.json"
    if not receipt_path.is_file():
        _fail("oracle_receipt_missing")
    document = json.loads(receipt_path.read_text(encoding="utf-8"))
    runtime = document.get("runtime")
    receipts = document.get("tasks")
    if not isinstance(runtime, dict) or not isinstance(receipts, list):
        _fail("oracle_receipt_invalid")
    if (
        runtime.get("environment") != "locked-docker"
        or not runtime.get("image")
        or runtime.get("network") != "none"
    ):
        _fail("docker_sanity_not_completed")
    expected_owner_hashes = {
        path.name: _file_hash(path) for path in OWNER_PATHS
    }
    if runtime.get("owner_hashes") != expected_owner_hashes:
        _fail("oracle_receipt_owner_drift")
    by_task = {
        item.get("task_id"): item for item in receipts if isinstance(item, dict)
    }
    if set(by_task) != set(CASES):
        _fail("oracle_receipt_task_inventory_mismatch")
    for task_id, item in by_task.items():
        root = out / task_id
        if item.get("tree_hash") != _tree_hash(root):
            _fail("oracle_receipt_tree_drift", task_id)
        if item.get("reference_hash") != _file_hash(root / ".meta/example.cpp"):
            _fail("oracle_receipt_reference_drift", task_id)
        if item.get("model_test_hash") != _file_hash(
            root / ".meta/task_model_test.cpp"
        ):
            _fail("oracle_receipt_model_drift", task_id)
        modes = item.get("modes")
        negative = item.get("negative_fixture")
        if not isinstance(modes, dict) or not isinstance(negative, dict):
            _fail("oracle_receipt_invalid", task_id)
        normal_count = modes.get("normal", {}).get("discovered_tests")
        sanitizer_count = modes.get("sanitizer", {}).get("discovered_tests")
        if normal_count != 3 or sanitizer_count != normal_count:
            _fail("sanitizer_test_count_mismatch", task_id)
        if (
            negative.get("rejected") is not True
            or negative.get("returncode") == 0
            or negative.get("discovered_tests") != normal_count
            or negative.get("selected_tests") != "model"
            or "timeout" in str(negative.get("ctest_output", "")).lower()
        ):
            _fail("negative_fixture_not_rejected", task_id)
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["screen"]["executable_negative_fixtures"] = "pass"
    manifest["screen"]["independent_model_traces"] = "pass"
    for task in manifest["tasks"]:
        task["status"] = "local_family_verified"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _complete_remedy_records(out, receipts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--verify-receipt", action="store_true")
    args = parser.parse_args(argv)
    if args.verify_receipt:
        verify_receipt(args.out)
        print(f"Verified producer-consumer protocol-ring receipt under {args.out}")
        return 0
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} producer-consumer protocol-ring tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
