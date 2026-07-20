"""Materialize clean-room, algorithmically distinct robot-simulation replacements."""
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
from w8_biayn.integrations.moonlight_robot_simulation_cases import CASES, RobotCase

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/robot-simulation")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/robot-simulation")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ROBOT_SIMULATION_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-dsa/robot-simulation.md"
FAMILY_ID = "aider-dsa-robot-simulation-v2"
MANIFEST_SCHEMA = "aider-robot-simulation-materialization-v2"
SEMANTIC_NORMALIZER = "robot-semantic-v2-control-flow-9gram"
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
REMEDY_HEADINGS = ("Identity", "Objective", "Public API", "Behavior table", "Implementation invariant", "Starter and reference", "Tests", "Files and metadata", "Build/oracle", "Family/contamination", "Optional dataset handoff", "Acceptance")
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset((
    "all-your-base", "allergies", "bank-account", "binary-search-tree", "circular-buffer", "clock",
    "complex-numbers", "crypto-square", "diamond", "dnd-character", "gigasecond", "grade-school",
    "kindergarten-garden", "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
    "perfect-numbers", "phone-number", "queen-attack", "robot-name", "space-age", "spiral-matrix",
    "sublist", "yacht", "zebra-puzzle",
))
TASKS = CASES


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _format_cpp(content: str) -> str:
    """Keep compact authored snippets unambiguous under GCC -Wmisleading-indentation."""
    return re.sub(r";(?=(?:for|if|while)\s*\()", ";\n", content)


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _source_hash(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


CMAKE = '''cmake_minimum_required(VERSION 3.16)
project(robot_simulation_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror -Wno-error=misleading-indentation)
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
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
            "family_specification": FAMILY_SPEC,
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id": FAMILY_ID,
            "semantic_profile": case.profile,
            "origin": "newly authored in-repository clean-room replacement",
            "license": "repository-authored",
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
            "benchmark_separation": "Independent API, state representation, algorithm, and tests; official Aider C++ roots remain holdouts.",
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": case.instructions.rstrip() + "\n",
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f'[visible]\ndescription = "{case.visible_description}"\n\n[hidden]\ndescription = "{case.hidden_description}"\n',
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        for name, content in task_named_files(root, files).items():
            if Path(name).suffix in {".h", ".cpp"}:
                content = _format_cpp(content)
            _write(root / name, content, force)
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
    if set(blocks) != set(task.editable_files):
        return "whole_format_failed"
    return None


def _normalized_code_tokens(content: str) -> list[str]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", content)
    keywords = {"if", "else", "for", "while", "switch", "case", "return", "break", "continue", "throw", "try", "catch", "class", "struct", "enum", "const", "auto", "bool", "int", "long", "void", "true", "false", "public", "private", "namespace", "std", "vector", "queue", "priority_queue", "optional", "map", "set", "string"}
    return [token if token in keywords or not re.match(r"[A-Za-z_]", token) else "ID" for token in raw]


def _ngrams(tokens: list[str], width: int = 9) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + width]) for i in range(max(0, len(tokens) - width + 1))}


def _semantic_signatures() -> dict[str, str]:
    signatures: dict[str, str] = {}
    fingerprints: dict[str, set[tuple[str, ...]]] = {}
    banned_legacy = ("MoveForward", "TurnClockwise", "TurnCounterClockwise", "4x4 map")
    for case in CASES:
        corpus = "\n".join((case.header, case.reference, case.visible_test, case.hidden_test))
        if case.marker not in case.reference:
            _fail("invariant_not_enforced", f"{case.task_id} lacks {case.marker}")
        if sum(token in corpus for token in banned_legacy) >= 2:
            _fail("duplicate_family", f"legacy-template-clone: {case.task_id}")
        tokens = _normalized_code_tokens(case.reference)
        normalized = " ".join(tokens)
        signature = hashlib.sha256(normalized.encode()).hexdigest()
        grams = _ngrams(tokens)
        for other, other_grams in fingerprints.items():
            denominator = min(len(grams), len(other_grams))
            similarity = len(grams & other_grams) / denominator if denominator else 1.0
            if similarity >= 0.80:
                _fail("duplicate_family", f"{case.task_id} resembles {other}: {similarity:.3f}")
        fingerprints[case.task_id] = grams
        signatures[case.task_id] = f"sha256:{signature}"
    if len({case.profile for case in CASES}) != len(CASES):
        _fail("duplicate_family", "semantic profiles are not one-to-one")
    return signatures


def _semantic_holdout_screen(out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    if not holdout_root.is_dir():
        _fail("benchmark_screen_not_completed", str(holdout_root))
    holdouts: dict[str, set[tuple[str, ...]]] = {}
    inventory = hashlib.sha256()
    for root in sorted(path for path in holdout_root.iterdir() if path.is_dir()):
        files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in {".h", ".hpp", ".cpp"} and "catch" not in path.name)
        corpus = ""
        for path in files:
            inventory.update(path.relative_to(holdout_root).as_posix().encode())
            inventory.update(path.read_bytes())
            corpus += "\n" + path.read_text(encoding="utf-8", errors="replace")
        holdouts[root.name] = _ngrams(_normalized_code_tokens(corpus))
    strongest = {"candidate": None, "holdout": None, "containment": 0.0}
    for case in CASES:
        candidate = _ngrams(_normalized_code_tokens(case.header + "\n" + case.reference + "\n" + case.visible_test + "\n" + case.hidden_test))
        for slug, grams in holdouts.items():
            denominator = min(len(candidate), len(grams))
            score = len(candidate & grams) / denominator if denominator else 0.0
            if score > strongest["containment"]:
                strongest = {"candidate": case.task_id, "holdout": slug, "containment": round(score, 6)}
            if score >= 0.60:
                _fail("benchmark_content_overlap", f"{case.task_id} resembles {slug}: {score:.3f}")
    return {"status": "pass", "normalizer": SEMANTIC_NORMALIZER, "source_inventory": f"sha256:{inventory.hexdigest()}", "holdout_root_count": len(holdouts), "comparison_scope": "docs-excluded; public API, reference, visible and hidden tests", "threshold": 0.60, "strongest": strongest}


def _benchmark_screen(root: Path) -> None:
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in sorted(root.rglob("*")) if path.is_file())
    normalized = corpus.lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", normalized):
            _fail("benchmark_id_overlap", slug)
    for forbidden in ("aider-ai/polyglot", "exercism c++ exercise", "robot_name", "robot-name"):
        if forbidden in normalized:
            _fail("benchmark_content_overlap", forbidden)


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    records = {path.stem: path for path in remedy.glob("*.json")} if remedy.is_dir() else {}
    expected = {case.task_id for case in CASES}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per replacement is required")
    for task_id, path in records.items():
        record = json.loads(path.read_text(encoding="utf-8"))
        spec_path = remedy / f"{task_id}.md"
        if record.get("disposition") != "replace" or record.get("task_id") != task_id or not spec_path.is_file():
            _fail("remedy_disposition_conflict", task_id)
        text = spec_path.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", task_id)
        if record.get("remedy_spec_hash") != f"sha256:{hashlib.sha256(text.encode()).hexdigest()}":
            _fail("remedy_spec_incomplete", f"stale specification hash for {task_id}")


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {len(expected)} roots, found {len(actual)}")
    if require_remedy:
        _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="robot-simulation-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    signatures = _semantic_signatures()
    holdout_screen = _semantic_holdout_screen(out)
    manifest_tasks = []
    for task_id in sorted(expected):
        root = out / task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config.get("files", {})
        solution = [_safe_relative(item) for item in files.get("solution", [])]
        tests = [_safe_relative(item) for item in files.get("test", [])]
        examples = [_safe_relative(item) for item in files.get("example", [])]
        if len(solution) != 2 or len(examples) != 2 or set(solution) & (set(tests) | set(examples)):
            _fail("reference_map_failed", task_id)
        if any(name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution):
            _fail("unsafe_path", task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("reference_map_failed", task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        if any(name in prompt for name in [*tests, *examples, "CMakeLists.txt", ".meta/provenance.json", ".meta/task_hidden_test.cpp"]):
            _fail("prompt_contract_incomplete", task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer) is not None:
            _fail("target_reference_mismatch", task_id)
        malformed = (f"{task.editable_files[0]}\n```cpp\n// missing file\n```\n", answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n", "prose\n" + answer)
        if any(_whole_format_code(root, value) != "whole_format_failed" for value in malformed):
            _fail("whole_format_failed", task_id)
        _benchmark_screen(root)
        manifest_tasks.append({"task_id": task_id, "tree_hash": _tree_hash(root), "semantic_profile": next(c.profile for c in CASES if c.task_id == task_id), "semantic_signature": signatures[task_id]})
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": MANIFEST_SCHEMA, "family_id": FAMILY_ID, "task_count": len(CASES), "owner_hash": _source_hash(Path(__file__)), "tasks": manifest_tasks, "screen": {"prompt_boundary": "pass", "reference_mapping": "pass", "negative_fixture": "pass:legacy-template-clone", "duplicate_family": "pass", "benchmark_contamination": "pass", "semantic_holdout": holdout_screen}}
    (state / "materialization-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _count_discovered(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match:
        _fail("test_discovery_failed", output[-300:])
    count = int(match.group(1))
    if count == 0:
        _fail("zero_tests", "ctest -N")
    return count


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    verify_core(out)
    receipts = []
    for case in CASES:
        root = out / case.task_id
        receipt: dict[str, object] = {"task_id": case.task_id, "tree_hash": _tree_hash(root), "reference_hash": _source_hash(root / ".meta/example.cpp"), "modes": {}}
        with tempfile.TemporaryDirectory(prefix="robot-oracle-") as temporary:
            copied = Path(temporary) / root.name
            shutil.copytree(root, copied)
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                configure = ["cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={copied/'.meta/example.cpp'}", *flags]
                def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
                    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    if result.returncode:
                        raise RuntimeError(f"oracle_command_failed: {case.task_id} {name}: {' '.join(command)}\n{result.stdout}")
                    return result
                run_checked(configure)
                run_checked(["cmake", "--build", str(build_dir), "--parallel", "2"])
                discovered = subprocess.run(["ctest", "--test-dir", str(build_dir), "-N"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                count = _count_discovered(discovered.stdout)
                executed = run_checked(["ctest", "--test-dir", str(build_dir), "--output-on-failure"])
                receipt["modes"][name] = {"configure": configure, "discovered_tests": count, "ctest_output": executed.stdout}
        modes = receipt["modes"]
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        receipts.append(receipt)
    runtime = {"environment": os.environ.get("W8_BIAYN_ORACLE_RUNTIME", "host-prerequisite"), "image": os.environ.get("W8_BIAYN_ORACLE_IMAGE"), "compiler": subprocess.run(["c++", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0], "cmake": subprocess.run(["cmake", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0]}
    path = out / ".state/oracle-receipt.json"
    path.write_text(json.dumps({"schema_version": "aider-robot-oracle-v2", "generator": "src/w8_biayn/integrations/moonlight_robot_simulation_aider_tasks.py", "owner_hash": _source_hash(Path(__file__)), "network": "none" if runtime["environment"] == "locked-docker" else "not_recorded", "runtime": runtime, "tasks": receipts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
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
    print(f"Wrote {len(roots)} algorithmically distinct robot-simulation tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
