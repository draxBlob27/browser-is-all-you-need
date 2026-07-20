"""Materialize and reverify the semantically diverse nested-structure v2 family."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
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
from w8_biayn.integrations.moonlight_nested_structure_cases import CASES, Case


DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/nested-structure")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/nested-structure")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_NESTED_STRUCTURE_CURRICULUM.md"
SELECTED_PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-dsa-nested-structure-v2"
MANIFEST_SCHEMA = "nested-structure-materialization-v2"
NORMALIZER = "aider-cleanroom-family-v2"
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table",
    "Implementation invariant", "Starter and reference", "Tests",
    "Files and metadata", "Build/oracle", "Family/contamination",
    "Optional dataset handoff", "Acceptance",
)
TASKS = CASES
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset({
    "all-your-base", "allergies", "bank-account", "binary-search-tree",
    "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
    "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
    "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
    "perfect-numbers", "phone-number", "queen-attack", "robot-name",
    "space-age", "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
})


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


def _starter(case: Case) -> str:
    return f'#include "task.h"\n// TODO: implement the {case.kind} contract declared in the header.\n'


def _negative(case: Case) -> str:
    source = case.reference
    replacements = (
        ("return{true", "return{false"),
        ("return {true", "return {false"),
        ("complete_=true", "complete_=false"),
        ("RegexGroups r{true", "RegexGroups r{false"),
        ("return r;", "r.valid=false;return r;"),
    )
    for before, after in replacements:
        if before in source:
            return source.replace(before, after, 1)
    raise AssertionError(f"no deterministic negative mutation for {case.task_id}")


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(nested_structure_v2 LANGUAGES CXX)
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


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
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
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_task_id,
            "origin": "clean-room repository-authored replacement after semantic-duplicate audit",
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
            "family_id": FAMILY_ID,
            "semantic_mechanism": case.kind,
            "selected_prompt": SELECTED_PROMPT,
            "benchmark_separation": "Not derived from official Aider Polyglot wording, APIs, tests, or reference code.",
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\nA clean-room local task for {case.objective.lower()}\n",
            ".docs/instructions.md": f"# Instructions\n\n{case.instructions}\n\nImplement the complete C++17 API declared in the editable header. This is local candidate material, not a dataset release.\n",
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": (
                f'[visible]\ndescription = "public {case.kind} behavior"\n\n'
                f'[private]\ndescription = "boundary, first-error, and {case.negative_name} discriminator"\n'
            ),
            "task.h": case.header,
            "task.cpp": _starter(case),
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_private_test.cpp": case.private_test,
            f".meta/negative/{case.negative_name}/task.cpp": _negative(case),
            "CMakeLists.txt": _cmake(),
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def _tree_hash(root: Path) -> str:
    lines: list[bytes] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  ./{path.relative_to(root).as_posix()}\n".encode())
    return "sha256:" + hashlib.sha256(b"".join(lines)).hexdigest()


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("unsafe_path", "empty or non-string path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _normalize(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", " LIT ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", " NUM ", text)
    return tuple(re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||->|\S", text.lower()))


def _grams(tokens: tuple[str, ...], width: int = 5) -> set[tuple[str, ...]]:
    return {tokens[i:i + width] for i in range(max(0, len(tokens) - width + 1))}


def _similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a, b = _grams(left), _grams(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def _holdout_corpora() -> dict[str, tuple[str, ...]]:
    base = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
    if not base.is_dir():
        _fail("benchmark_content_overlap", "bound upstream C++ holdouts unavailable")
    corpora: dict[str, tuple[str, ...]] = {}
    for slug in sorted(OFFICIAL_AIDER_CPP_HOLDOUTS):
        root = base / slug
        if not root.is_dir():
            _fail("benchmark_content_overlap", f"missing holdout {slug}")
        content = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.suffix in {".md", ".h", ".hpp", ".cpp", ".toml"}
            and path.name != "catch.hpp"
        )
        corpora[slug] = _normalize(content)
    excluded = Path(".cache/upstreams/exercism-cpp/exercises/practice/matching-brackets")
    if not excluded.is_dir():
        _fail("benchmark_content_overlap", "excluded matching-brackets source unavailable")
    excluded_content = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(excluded.rglob("*"))
        if path.is_file() and path.suffix in {".md", ".h", ".hpp", ".cpp", ".toml"}
        and path.name != "catch.hpp"
    )
    corpora["excluded-source:matching-brackets"] = _normalize(excluded_content)
    return corpora


def _benchmark_slug_screen(text: str, task_id: str) -> None:
    normalized = text.lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", normalized):
            _fail("benchmark_id_overlap", f"{task_id}:{slug}")


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    expected = {case.task_id for case in CASES}
    records = {path.stem: path for path in remedy.glob("*.json")} if remedy.is_dir() else {}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per replacement root is required")
    for task_id, path in records.items():
        record = json.loads(path.read_text(encoding="utf-8"))
        spec_path = remedy / f"{task_id}.md"
        if record.get("task_id") != task_id or record.get("disposition") != "replace":
            _fail("remedy_disposition_conflict", task_id)
        if record.get("generator_revision") != "sha256:0bb42bfd9ce0678704b1bd91366193ac25976d15b3ec60440ab9bb8052fae26b":
            _fail("remedy_disposition_conflict", f"unfrozen legacy generator for {task_id}")
        if not spec_path.is_file():
            _fail("remedy_spec_incomplete", task_id)
        text = spec_path.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", task_id)
        digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        if record.get("remedy_spec_hash") != digest:
            _fail("remedy_spec_incomplete", f"stale specification hash for {task_id}")


def _whole_format_code(root: Path, content: str) -> str | None:
    task = load_task(root)
    try:
        parsed = parse_whole_file_blocks(content)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(parsed) == set(task.editable_files) else "whole_format_failed"


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {len(expected)} roots, found {len(actual)}")
    if require_remedy:
        _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="nested-v2-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)

    holdouts = _holdout_corpora()
    family_tokens: dict[str, tuple[str, ...]] = {}
    task_rows: list[dict[str, object]] = []
    prompt_hashes: dict[str, str] = {}
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config.get("files", {})
        solution = [_safe_relative(item) for item in files.get("solution", [])]
        tests = [_safe_relative(item) for item in files.get("test", [])]
        examples = [_safe_relative(item) for item in files.get("example", [])]
        if solution != [f"{case.task_id}.h", f"{case.task_id}.cpp"] or examples != [".meta/example.h", ".meta/example.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        if set(solution) & (set(tests) | set(examples)) or any(name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution):
            _fail("unsafe_path", case.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("target_reference_mismatch", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private_names = [*tests, *examples, "CMakeLists.txt", ".meta/provenance.json", ".meta/task_private_test.cpp"]
        if any(name in prompt for name in private_names):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer) is not None:
            _fail("target_reference_mismatch", case.task_id)
        missing = f"{task.editable_files[0]}\n```cpp\n// incomplete\n```\n"
        if _whole_format_code(root, missing) != "whole_format_failed" or _whole_format_code(root, "prose\n" + answer) != "whole_format_failed":
            _fail("whole_format_failed", case.task_id)
        corpus = "\n".join((case.instructions, case.header, case.reference, case.visible_test, case.private_test))
        _benchmark_slug_screen(corpus, case.task_id)
        tokens = _normalize(corpus)
        family_tokens[case.task_id] = tokens
        strongest = max((_similarity(tokens, value), slug) for slug, value in holdouts.items())
        if strongest[0] >= 0.55:
            _fail("benchmark_content_overlap", f"{case.task_id}:{strongest[1]}:{strongest[0]:.3f}")
        prompt_hashes[case.task_id] = "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
        task_rows.append({
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_task_id,
            "mechanism": case.kind,
            "tree_hash": _tree_hash(root),
            "strongest_holdout_similarity": round(strongest[0], 6),
            "strongest_holdout": strongest[1],
        })
    pairs: list[dict[str, object]] = []
    ids = sorted(family_tokens)
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            score = _similarity(family_tokens[left], family_tokens[right])
            pairs.append({"left": left, "right": right, "similarity": round(score, 6)})
            if score >= 0.72:
                _fail("duplicate_family", f"{left}:{right}:{score:.3f}")
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "task_count": len(task_rows),
        "status": "semantically_admitted",
        "tasks": task_rows,
        "screen": {
            "primary_core_objective": "achieved",
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "negative_fixtures": "pending locked execution",
            "duplicate_family": "pass",
            "benchmark_contamination": "pass",
            "official_holdout_inventory": len(OFFICIAL_AIDER_CPP_HOLDOUTS),
            "excluded_source_inventory": 1,
            "semantic_screen_sources": len(holdouts),
            "normalizer": NORMALIZER,
        },
        "prompt_hashes": prompt_hashes,
        "family_pairs": pairs,
    }
    _write(state / "materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def _docker_script() -> str:
    return r'''set -eu
trap 'cat /tmp/configure.log /tmp/build.log /tmp/negative-configure.log /tmp/negative-build.log /tmp/negative-test.log 2>/dev/null || true' EXIT
for root in /tasks/nest-*-v2; do
 task="$(basename "$root")"
 hash="$(cd "$root" && find . -type f | LC_ALL=C sort | while IFS= read -r file; do sha256sum "$file"; done | sha256sum | awk '{print $1}')"
 counts=""
 for mode in normal sanitizer; do
 build="/tmp/${task}-${mode}"
  if [ "$mode" = sanitizer ]; then
   CXXFLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer" LDFLAGS="-fsanitize=address,undefined" cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" >/tmp/configure.log 2>&1
  else
   cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" >/tmp/configure.log 2>&1
  fi
  cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1
  count="$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: *//p')"
  [ "$count" = 2 ]
  ctest --test-dir "$build" --output-on-failure
  counts="${counts}|${count}"
 done
 neg="$(find "$root/.meta/negative" -name "*.cpp" -type f)"
 nbuild="/tmp/${task}-negative"
 cmake -S "$root" -B "$nbuild" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$neg" >/tmp/negative-configure.log 2>&1
 cmake --build "$nbuild" --parallel 2 >/tmp/negative-build.log 2>&1
 if ctest --test-dir "$nbuild" --output-on-failure >/tmp/negative-test.log 2>&1; then echo "negative fixture passed:$task"; exit 31; fi
 echo "RESULT|${task}|sha256:${hash}${counts}|rejected"
done
c++ --version | head -1
cmake --version | head -1
trap - EXIT
'''


def _update_verified_records(out: Path, receipts: dict[str, dict[str, object]], runtime: dict[str, object]) -> None:
    remedy = out / ".state/remedy"
    for case in CASES:
        path = remedy / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update({
            "benchmark_screen": "pass",
            "status": "verified",
            "primary_core_objective": "achieved",
            "tree_hash_after": _tree_hash(out / case.task_id),
            "changed_owner_paths": [
                "src/w8_biayn/integrations/moonlight_nested_structure_aider_tasks.py",
                "src/w8_biayn/integrations/moonlight_nested_structure_cases.py",
                "tests/test_moonlight_nested_structure_aider_tasks.py",
            ],
            "oracle": receipts[case.task_id],
            "runtime": runtime,
            "prompt_boundary": "pass",
            "duplicate_family": "pass",
            "strongest_local_status": "local_family_verified",
        })
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def verify(out: Path) -> None:
    verify_core(out)
    image = os.environ.get("W8_NESTED_STRUCTURE_GRADER_IMAGE")
    if not image:
        _fail("oracle_runtime_not_completed", "set W8_NESTED_STRUCTURE_GRADER_IMAGE to the designated locked C++ image")
    docker = shutil.which("docker")
    if not docker:
        _fail("oracle_runtime_not_completed", "docker is unavailable")
    inspect = subprocess.run([docker, "image", "inspect", image, "--format", "{{.Id}}"], check=True, stdout=subprocess.PIPE, text=True)
    image_id = inspect.stdout.strip()
    command = [docker, "run", "--rm", "--network", "none", "-v", f"{out.resolve()}:/tasks:ro", image, "sh", "-lc", _docker_script()]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as error:
        _fail("locked_oracle_failed", error.stdout or "container exited without diagnostics")
    receipts: dict[str, dict[str, object]] = {}
    compiler = "not_recorded"
    cmake = "not_recorded"
    for line in result.stdout.splitlines():
        if line.startswith("RESULT|"):
            _, task_id, docker_hash, normal, sanitizer, negative = line.split("|")
            owner_hash = _tree_hash(out / task_id)
            if docker_hash != owner_hash:
                _fail("grader_mount_hash_mismatch", task_id)
            if normal != sanitizer or normal != "2":
                _fail("sanitizer_test_count_mismatch", task_id)
            if negative != "rejected":
                _fail("invariant_not_enforced", task_id)
            receipts[task_id] = {
                "status": "pass", "tree_hash": owner_hash, "docker_tree_hash": docker_hash,
                "normal_tests": 2, "sanitizer_tests": 2, "negative_fixture": "rejected",
            }
        elif line.startswith("c++ ") or "g++" in line.lower() or "gcc" in line.lower():
            compiler = line
        elif line.startswith("cmake version"):
            cmake = line
    if set(receipts) != {case.task_id for case in CASES}:
        _fail("test_discovery_failed", f"received {len(receipts)} of {len(CASES)} receipts")
    runtime = {"image": image, "image_id": image_id, "network": "none", "compiler": compiler, "cmake": cmake, "command": command[:-1] + ["<owner verifier script>"]}
    _write(out / ".state/oracle-receipt.json", json.dumps({"runtime": runtime, "tasks": receipts}, indent=2, sort_keys=True) + "\n", True)
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "local_family_verified"
    manifest["screen"]["negative_fixtures"] = "pass: executed and rejected"
    manifest["oracle"] = {"status": "pass", "normal_tests_per_root": 2, "sanitizer_tests_per_root": 2, "root_count": len(CASES), "image_id": image_id}
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _update_verified_records(out, receipts, runtime)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} semantically distinct nested-structure v2 tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
