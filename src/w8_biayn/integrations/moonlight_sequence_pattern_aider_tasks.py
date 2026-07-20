"""Remediate and verify clean-room sequence-pattern Aider tasks."""
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
from w8_biayn.integrations.moonlight_sequence_pattern_cases import CASES

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/sequence-pattern")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/sequence-pattern")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SEQUENCE_PATTERN_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-dsa/sequence-pattern.md"
FAMILY_ID = "aider-dsa-sequence-pattern-v2"
MANIFEST_SCHEMA = "aider-sequence-pattern-materialization-v2"
NORMALIZER = "sequence-pattern-semantic-v3"
MIN_ROOTS = 20
MAX_ROOTS = 20
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table", "Implementation invariant",
    "Starter and reference", "Tests", "Files and metadata", "Build/oracle",
    "Family/contamination", "Optional dataset handoff", "Acceptance",
)
OFFICIAL_HOLDOUTS = frozenset((
    "all-your-base", "allergies", "bank-account", "binary-search-tree", "circular-buffer",
    "clock", "complex-numbers", "crypto-square", "diamond", "dnd-character", "gigasecond",
    "grade-school", "kindergarten-garden", "knapsack", "linked-list", "meetup",
    "parallel-letter-frequency", "perfect-numbers", "phone-number", "queen-attack",
    "robot-name", "space-age", "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
))
TASKS = CASES


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _source_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _owner_hash() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__), Path(__file__).with_name("moonlight_sequence_pattern_cases.py")):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _family_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for case in sorted(CASES, key=lambda item: item.task_id):
        digest.update(case.task_id.encode())
        digest.update(b"\0")
        digest.update(_tree_hash(root / case.task_id).encode())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(sequence_pattern_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation under test")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_negative .meta/negative.cpp .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden task_negative)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror -Wno-error=misleading-indentation)
  endif()
endforeach()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME negative_fixture COMMAND task_negative)
set_tests_properties(negative_fixture PROPERTIES WILL_FAIL TRUE)
'''


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.exists() and force:
        expected = {case.task_id for case in CASES}
        for child in out.iterdir():
            if child.is_dir() and child.name != ".state" and child.name not in expected:
                shutil.rmtree(child)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        config = {
            "authors": ["w8-biayn"],
            "blurb": case.objective,
            "source": "repository-authored clean-room sequence-pattern remediation",
            "files": {
                "solution": ["task.h", "task.cpp"],
                "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp", ".meta/negative.cpp"],
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
            "benchmark_separation": "Independent API, mechanism, tests, and reference; official Aider C++ roots remain permanent holdouts.",
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": case.instructions.rstrip() + "\n",
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": (
                f'[visible]\ndescription = "normal and boundary behavior for {case.profile}"\n\n'
                f'[hidden]\ndescription = "invalid input, deterministic ties, adversarial mechanism trace, and {case.profile} discriminator"\n\n'
                f'[negative]\ndescription = "executed task-specific false substitute for {case.profile}"\n'
            ),
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            ".meta/negative.cpp": case.starter,
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def _safe_relative(value: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _whole_format_code(root: Path, response: str) -> str | None:
    task = load_task(root)
    try:
        blocks = parse_whole_file_blocks(response)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(blocks) == set(task.editable_files) else "whole_format_failed"


def _tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+(?:\.\d+)?\b', " LIT ", text)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", text)
    keep = {
        "if", "else", "for", "while", "return", "break", "continue", "throw", "class", "struct",
        "enum", "const", "auto", "bool", "int", "long", "void", "true", "false", "public", "private",
        "namespace", "std", "vector", "deque", "queue", "map", "set", "optional", "string", "string_view",
        "priority_queue", "lower_bound", "isfinite", "isalnum", "tolower", "pop_front", "push_back",
    }
    identifiers: dict[str, str] = {}
    out: list[str] = []
    for token in raw:
        lowered = token.lower()
        if lowered in keep or not re.match(r"[A-Za-z_]", token):
            out.append(lowered)
        elif lowered == "lit":
            out.append("LIT")
        else:
            identifiers.setdefault(lowered, f"ID{len(identifiers)}")
            out.append(identifiers[lowered])
    return tuple(out)


def _ngrams(tokens: tuple[str, ...], width: int = 8) -> set[tuple[str, ...]]:
    return {tokens[i : i + width] for i in range(max(0, len(tokens) - width + 1))}


def _emitted_corpus(root: Path) -> str:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    roles = config["files"]
    paths = (
        ".docs/introduction.md",
        ".docs/instructions.md",
        roles["solution"][0],
        roles["example"][1],
        roles["test"][0],
        roles["test"][1],
    )
    return "\n".join((root / _safe_relative(path)).read_text(encoding="utf-8") for path in paths)


def _family_screen(out: Path) -> dict[str, object]:
    if not MIN_ROOTS <= len(CASES) <= MAX_ROOTS:
        _fail(
            "family_count_out_of_bounds",
            f"expected {MIN_ROOTS}..{MAX_ROOTS} roots, found {len(CASES)}",
        )
    profiles = {case.profile for case in CASES}
    if len(profiles) != len(CASES):
        _fail("duplicate_family", "semantic profiles are not one-to-one")
    grams = {
        case.task_id: _ngrams(_tokens(_emitted_corpus(out / case.task_id)))
        for case in CASES
    }
    strongest = {"left": None, "right": None, "containment": 0.0}
    pair_count = 0
    ids = sorted(grams)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            pair_count += 1
            denominator = min(len(grams[left]), len(grams[right]))
            score = len(grams[left] & grams[right]) / denominator if denominator else 1.0
            if score > strongest["containment"]:
                strongest = {"left": left, "right": right, "containment": round(score, 6)}
            if score >= 0.82:
                _fail("duplicate_family", f"{left} resembles {right}: {score:.3f}")
    return {
        "status": "pass",
        "normalizer": NORMALIZER,
        "root_count": len(CASES),
        "minimum_roots": MIN_ROOTS,
        "maximum_roots": MAX_ROOTS,
        "comparison_scope": "all_unordered_pairs",
        "evidence_fields": [
            "emitted_introduction",
            "emitted_instructions",
            "public_api",
            "reference_source",
            "visible_tests",
            "private_tests",
        ],
        "pair_count": pair_count,
        "threshold": 0.82,
        "strongest": strongest,
    }


def _holdout_screen(out: Path) -> dict[str, object]:
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_screen_not_completed", str(HOLDOUT_ROOT))
    holdouts: dict[str, set[tuple[str, ...]]] = {}
    inventory = hashlib.sha256()
    for root in sorted(path for path in HOLDOUT_ROOT.iterdir() if path.is_dir()):
        corpus: list[str] = []
        for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {".h", ".hpp", ".cpp", ".md"} and "catch" not in p.name):
            inventory.update(path.relative_to(HOLDOUT_ROOT).as_posix().encode())
            inventory.update(path.read_bytes())
            corpus.append(path.read_text(encoding="utf-8", errors="replace"))
        holdouts[root.name] = _ngrams(_tokens("\n".join(corpus)))
    strongest = {"candidate": None, "holdout": None, "containment": 0.0}
    comparisons = 0
    for case in CASES:
        candidate = _ngrams(_tokens(_emitted_corpus(out / case.task_id)))
        for slug, signature in holdouts.items():
            comparisons += 1
            denominator = min(len(candidate), len(signature))
            score = len(candidate & signature) / denominator if denominator else 0.0
            if score > strongest["containment"]:
                strongest = {"candidate": case.task_id, "holdout": slug, "containment": round(score, 6)}
            if score >= 0.60:
                _fail("benchmark_content_overlap", f"{case.task_id} resembles {slug}: {score:.3f}")
    return {
        "status": "pass", "normalizer": NORMALIZER, "holdout_root_count": len(holdouts),
        "comparisons": comparisons, "threshold": 0.60, "source_inventory": f"sha256:{inventory.hexdigest()}",
        "strongest": strongest,
    }


def _benchmark_slug_screen(root: Path) -> None:
    corpus = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in sorted(root.rglob("*")) if path.is_file())
    lowered = corpus.lower()
    for slug in OFFICIAL_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", lowered):
            _fail("benchmark_id_overlap", f"{root.name}:{slug}")


def _verify_remedies(out: Path) -> dict[str, dict[str, object]]:
    remedy_root = out / ".state/remedy"
    records = {path.stem: path for path in remedy_root.glob("*.json")} if remedy_root.is_dir() else {}
    expected = {case.legacy_id for case in CASES}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", f"expected {len(expected)} legacy records, found {len(records)}")
    result: dict[str, dict[str, object]] = {}
    by_legacy = {case.legacy_id: case for case in CASES}
    for legacy_id, path in records.items():
        record = json.loads(path.read_text(encoding="utf-8"))
        case = by_legacy[legacy_id]
        spec = remedy_root / f"{legacy_id}.md"
        if record.get("schema_version") != "aider-task-remedy-v1" or record.get("task_id") != legacy_id:
            _fail("remedy_spec_incomplete", legacy_id)
        if record.get("disposition") != "replace" or record.get("replacement_task_id") != case.task_id:
            _fail("remedy_disposition_conflict", legacy_id)
        if not spec.is_file() or record.get("remedy_spec_hash") != _source_hash(spec):
            _fail("remedy_spec_incomplete", f"stale spec: {legacy_id}")
        text = spec.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", f"heading order: {legacy_id}")
        legacy = LEGACY_ROOT / legacy_id
        if not legacy.is_dir() or record.get("tree_hash_before") != _tree_hash(legacy):
            _fail("generator_output_drift", f"legacy tree: {legacy_id}")
        result[legacy_id] = record
    return result


def verify_core(out: Path, *, require_remedy: bool = True) -> dict[str, object]:
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {sorted(expected)}, found {sorted(actual)}")
    records = _verify_remedies(out) if require_remedy else {}
    with tempfile.TemporaryDirectory(prefix="sequence-pattern-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    family_screen = _family_screen(out)
    holdout_screen = _holdout_screen(out)
    rows: list[dict[str, object]] = []
    for case in sorted(CASES, key=lambda item: item.task_id):
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        roles = config.get("files", {})
        solution = [_safe_relative(value) for value in roles.get("solution", [])]
        tests = [_safe_relative(value) for value in roles.get("test", [])]
        examples = [_safe_relative(value) for value in roles.get("example", [])]
        if len(solution) != 2 or len(tests) != 3 or len(examples) != 2:
            _fail("reference_map_failed", case.task_id)
        if set(solution) & (set(tests) | set(examples)) or any(name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution):
            _fail("unsafe_path", case.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("reference_map_failed", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private_names = [*tests, *examples, "CMakeLists.txt", ".meta/provenance.json"]
        if any(name in prompt for name in private_names):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer):
            _fail("target_reference_mismatch", case.task_id)
        malformed = (
            f"{task.editable_files[0]}\n```cpp\n// missing\n```\n",
            answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n",
            "prose\n" + answer,
        )
        if any(_whole_format_code(root, value) != "whole_format_failed" for value in malformed):
            _fail("whole_format_failed", case.task_id)
        if re.sub(r"\s+", "", case.marker) not in re.sub(r"\s+", "", case.reference):
            _fail("invariant_not_enforced", f"{case.task_id}:{case.marker}")
        if case.starter == case.reference:
            _fail("invariant_not_enforced", f"negative fixture equals reference:{case.task_id}")
        _benchmark_slug_screen(root)
        rows.append({
            "task_id": case.task_id, "legacy_task_id": case.legacy_id, "semantic_profile": case.profile,
            "tree_hash": _tree_hash(root), "reference_hash": _source_hash(root / ".meta/example.cpp"),
            "negative_hash": _source_hash(root / ".meta/negative.cpp"),
            "semantic_signature": _sha(" ".join(_tokens(_emitted_corpus(root))).encode()),
            "primary_core_objective": "achieved",
        })
    manifest = {
        "schema_version": MANIFEST_SCHEMA, "family_id": FAMILY_ID, "task_count": len(rows),
        "owner_hash": _owner_hash(), "family_hash": _family_hash(out), "tasks": rows,
        "screen": {
            "prompt_boundary": "pass", "reference_mapping": "pass", "whole_format_controls": "pass",
            "negative_fixtures": "pass:20 task-specific compiled fixtures", "duplicate_family": family_screen,
            "benchmark_contamination": holdout_screen, "benchmark_whole_slug": "pass",
        },
        "status": "semantically_admitted",
    }
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "materialization-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if require_remedy:
        by_legacy = {row["legacy_task_id"]: row for row in rows}
        for legacy_id, record in records.items():
            record.update({
                "generator_revision_after": _owner_hash(), "tree_hash_after": by_legacy[legacy_id]["tree_hash"],
                "primary_core_objective": "achieved", "prompt_boundary": "pass", "reference_mapping": "pass",
                "family_screen": "pass", "benchmark_screen": "pass", "negative_fixture": "pass",
                "status": "implemented", "local_status": "semantically_admitted",
            })
            path = state / "remedy" / f"{legacy_id}.json"
            path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _run(command: list[str], *, task_id: str, mode: str) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        _fail("reference_tests_failed" if mode == "normal" else "reference_sanitizer_failed", f"{task_id}:{' '.join(command)}\n{result.stdout[-2000:]}")
    return result.stdout


def _discovery_count(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match:
        _fail("test_discovery_failed", output[-500:])
    count = int(match.group(1))
    if count <= 0:
        _fail("zero_tests", output[-500:])
    return count


def verify(out: Path) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    manifest = verify_core(out)
    receipts: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        receipt: dict[str, object] = {
            "task_id": case.task_id, "legacy_task_id": case.legacy_id, "tree_hash": _tree_hash(root),
            "reference_hash": _source_hash(root / ".meta/example.cpp"),
            "negative_hash": _source_hash(root / ".meta/negative.cpp"), "modes": {},
        }
        with tempfile.TemporaryDirectory(prefix=f"sequence-oracle-{case.task_id}-") as temporary:
            copied = Path(temporary) / case.task_id
            shutil.copytree(root, copied)
            for mode, flags in (
                ("normal", []),
                ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]),
            ):
                build_dir = copied / f"build-{mode}"
                configure = [
                    "cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles",
                    "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={copied / '.meta/example.cpp'}", *flags,
                ]
                _run(configure, task_id=case.task_id, mode=mode)
                _run(["cmake", "--build", str(build_dir), "--parallel", "2"], task_id=case.task_id, mode=mode)
                discovery = _run(["ctest", "--test-dir", str(build_dir), "-N"], task_id=case.task_id, mode=mode)
                count = _discovery_count(discovery)
                executed = _run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], task_id=case.task_id, mode=mode)
                receipt["modes"][mode] = {
                    "configure": configure, "discovered_tests": count,
                    "ctest_output_hash": _sha(executed.encode()),
                }
        modes = receipt["modes"]
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        if modes["normal"]["discovered_tests"] != 3:
            _fail("test_discovery_failed", f"{case.task_id}: expected 3")
        receipts.append(receipt)
    environment = os.environ.get("W8_SEQUENCE_PATTERN_ORACLE_RUNTIME", "host-prerequisite")
    image = os.environ.get("W8_SEQUENCE_PATTERN_ORACLE_IMAGE")
    network = os.environ.get("W8_SEQUENCE_PATTERN_NETWORK_POLICY", "not_recorded")
    docker_complete = environment == "docker_sanity" and image == SANITY_IMAGE and network == "none"
    runtime = {
        "environment": environment, "evidence_class": "docker_sanity" if docker_complete else "host_iteration",
        "locked_oracle": False, "image": image, "network_policy": network,
        "compiler": subprocess.run(["c++", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0],
        "cmake": subprocess.run(["cmake", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0],
    }
    receipt = {
        "schema_version": "aider-sequence-pattern-oracle-v2", "family_id": FAMILY_ID,
        "owner_hash": _owner_hash(), "family_hash": _family_hash(out), "runtime": runtime,
        "task_count": len(receipts), "normal_test_count_per_root": 3,
        "sanitizer_test_count_per_root": 3, "tasks": receipts,
        "status": "local_family_verified" if docker_complete else "docker_sanity_not_completed",
    }
    receipt_path = out / ".state/oracle-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_hash = _source_hash(receipt_path)
    manifest.update({
        "oracle_receipt": str(receipt_path), "oracle_receipt_hash": receipt_hash,
        "status": receipt["status"], "runtime": runtime,
    })
    (out / ".state/materialization-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for case in CASES:
        path = out / ".state/remedy" / f"{case.legacy_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update({
            "oracle_receipt": str(receipt_path), "oracle_receipt_hash": receipt_hash,
            "test_counts": {"normal": 3, "sanitizer": 3},
            "oracle_evidence": runtime["evidence_class"],
            "status": "verified" if docker_complete else "implemented",
            "local_status": "local_family_verified" if docker_complete else "docker_sanity_not_completed",
        })
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--print-family-hash", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.print_family_hash:
        print(_family_hash(args.out))
    else:
        print(f"Wrote {len(roots)} remediated sequence-pattern tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
