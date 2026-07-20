"""Materialize the logic-diverse interval-scheduling v2 Aider family."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from w8_biayn.integrations.moonlight_interval_scheduling_cases import (
    REFERENCES,
    STARTERS,
    TASKS,
    TESTS,
    TaskSpec,
    header_for,
)
from w8_biayn.integrations.moonlight_interval_scheduling_negatives import (
    DIVERSITY_PROFILES,
    NEGATIVES,
    ORACLE_TESTS,
)

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/interval-scheduling")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/interval-scheduling")
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-dsa/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_INTERVAL_SCHEDULING_CURRICULUM.md"
)
SELECTED_PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-dsa-interval-scheduling-v2"
MANIFEST_SCHEMA = "aider-interval-materialization-v3"
NORMALIZER_VERSION = "interval-family-semantic-v3"
MIN_FAMILY_ROOTS = 15
MAX_FAMILY_ROOTS = 20
FAMILY_SIMILARITY_LIMIT = 0.72
HOLDOUT_SIMILARITY_LIMIT = 0.68
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
HOLDOUT_SUPPORT_ALLOWLIST = frozenset({"test/catch.hpp", "test/tests-main.cpp"})
DESIGNATED_GRADER_IMAGE = (
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

CMAKE = """cmake_minimum_required(VERSION 3.16)
project(interval_scheduling_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_oracle "${TASK_SOURCE}" .meta/task_oracle_test.cpp)
foreach(target task_visible task_hidden task_oracle)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME oracle COMMAND task_oracle)
"""


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(
                path.relative_to(root).as_posix().encode("utf-8") + b"\0" + path.read_bytes()
            )
    return f"sha256:{digest.hexdigest()}"


def _instructions(spec: TaskSpec) -> str:
    return (
        f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract} "
        f"{spec.rules} {spec.boundary_example} The substantive algorithm is "
        f"`{spec.mode}`; invalid batches return a result with `valid == false` "
        "or the documented failure value without partial mutation. This is local "
        "candidate material, not an SFT release.\n"
    )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots: list[Path] = []
    for spec in TASKS:
        root = out / spec.task_id
        header = header_for(spec)
        config = {
            "authors": ["w8-biayn"],
            "blurb": spec.contract,
            "files": {
                "solution": ["task.h", "task.cpp"],
                "test": ["task_visible_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "benchmark_separation": (
                "Clean-room v2 replacement with a unique algorithm, API, state, "
                "reference marker, and adversarial fixture."
            ),
            "curriculum_document": CURRICULUM,
            "family_id": FAMILY_ID,
            "legacy_task_id": spec.legacy_id,
            "origin": "newly authored in-repository replacement",
            "selected_prompt": SELECTED_PROMPT,
            "status": "local task artifact; not admitted SFT data",
            "task_spec_revision": 2,
        }
        files = {
            ".docs/introduction.md": (
                f"# {spec.title}\n\nA clean-room interval algorithm task using `{spec.mode}`.\n"
            ),
            ".docs/instructions.md": _instructions(spec),
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": (json.dumps(provenance, indent=2, sort_keys=True) + "\n"),
            ".meta/tests.toml": (
                "[visible]\n"
                f'description = "public {spec.mode} contract and boundary example"\n\n'
                "[hidden]\n"
                f'description = "{spec.negative_fixture}, invalid input, ties, and sanitizer"\n'
            ),
            "task.h": header,
            "task.cpp": STARTERS[spec.mode].replace("CLASS", spec.class_name),
            ".meta/example.h": header,
            ".meta/example.cpp": REFERENCES[spec.mode].replace("CLASS", spec.class_name),
            "task_visible_test.cpp": TESTS[spec.mode][0].replace("CLASS", spec.class_name),
            ".meta/task_hidden_test.cpp": TESTS[spec.mode][1].replace("CLASS", spec.class_name),
            ".meta/task_oracle_test.cpp": ORACLE_TESTS[spec.mode].replace("CLASS", spec.class_name),
            ".meta/negative.cpp": NEGATIVES[spec.mode].replace("CLASS", spec.class_name),
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


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


def _verify_remedy_records(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    expected = {spec.task_id for spec in TASKS}
    records = {path.stem: path for path in remedy.glob("*.json")}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per replacement is required")
    by_id = {spec.task_id: spec for spec in TASKS}
    for task_id, path in records.items():
        record = json.loads(path.read_text(encoding="utf-8"))
        spec = by_id[task_id]
        remedy_spec = remedy / f"{task_id}.md"
        if (
            record.get("task_id") != task_id
            or record.get("legacy_task_id") != spec.legacy_id
            or record.get("disposition") != "replace"
            or not remedy_spec.is_file()
        ):
            _fail("remedy_disposition_conflict", task_id)
        text = remedy_spec.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", task_id)
        digest = f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
        if record.get("remedy_spec_hash") != digest:
            _fail("remedy_spec_incomplete", f"stale specification hash for {task_id}")
        legacy = LEGACY_ROOT / spec.legacy_id
        if not legacy.is_dir() or record.get("tree_hash_before") != _tree_hash(legacy):
            _fail("generator_output_drift", f"legacy input changed for {task_id}")


def _benchmark_screen(root: Path) -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.rglob("*")) if path.is_file()
    ).lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", corpus):
            _fail("benchmark_id_overlap", f"{root.name}:{slug}")
    for phrase in (
        "aider-ai/polyglot",
        "exercism c++ exercise",
        "upstream polyglot benchmark",
    ):
        if phrase in corpus:
            _fail("benchmark_content_overlap", f"{root.name}:{phrase}")


_SEMANTIC_KEYWORDS = frozenset(
    {
        "break",
        "case",
        "class",
        "const",
        "continue",
        "do",
        "else",
        "false",
        "for",
        "if",
        "namespace",
        "private",
        "public",
        "return",
        "static",
        "struct",
        "switch",
        "true",
        "using",
        "while",
        "sort",
        "stable_sort",
        "upper_bound",
        "lower_bound",
        "priority_queue",
        "map",
        "set",
        "vector",
        "optional",
        "function",
        "lexicographical_compare",
        "min",
        "max",
        "find",
        "erase",
        "insert",
        "push_back",
        "pop",
        "front",
        "back",
        "empty",
        "size",
    }
)


def _semantic_tokens(text: str) -> tuple[str, ...]:
    """Normalize nouns/literals while retaining control flow and assertions."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", text)
    raw = re.findall(
        r"::|<=|>=|==|!=|&&|\|\||\+\+|--|->|[A-Za-z_][A-Za-z0-9_]*|"
        r"\d+|[{}()\[\];,.:?+*/%<>=!&|~-]",
        text.lower(),
    )
    normalized: list[str] = []
    for token in raw:
        if token.isdigit():
            normalized.append("NUM")
        elif re.fullmatch(r"[a-z_][a-z0-9_]*", token):
            normalized.append(token if token in _SEMANTIC_KEYWORDS else "ID")
        else:
            normalized.append(token)
    return tuple(normalized)


def _semantic_ngrams(tokens: tuple[str, ...], width: int = 5) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tokens}
    return {tokens[index : index + width] for index in range(len(tokens) - width + 1)}


def _semantic_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_grams = _semantic_ngrams(left)
    right_grams = _semantic_ngrams(right)
    union = left_grams | right_grams
    return len(left_grams & right_grams) / len(union) if union else 1.0


def _semantic_corpus(root: Path, *, candidate: bool) -> str:
    chunks: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".h", ".hpp", ".cpp"}:
            continue
        relative = path.relative_to(root).as_posix()
        if candidate and relative == ".meta/negative.cpp":
            continue
        if not candidate and relative in HOLDOUT_SUPPORT_ALLOWLIST:
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def _semantic_screen(out: Path) -> dict[str, object]:
    if not MIN_FAMILY_ROOTS <= len(TASKS) <= MAX_FAMILY_ROOTS:
        _fail("duplicate_family", "family count is outside the 15-20 hard bound")
    if set(DIVERSITY_PROFILES) != {spec.mode for spec in TASKS}:
        _fail("duplicate_family", "diversity profile inventory mismatch")
    for dimension in range(4):
        values = {profile[dimension] for profile in DIVERSITY_PROFILES.values()}
        if len(values) != len(TASKS):
            _fail("duplicate_family", f"duplicate diversity dimension {dimension}")
    profiles: set[tuple[str, ...]] = set()
    tokens_by_task: dict[str, tuple[str, ...]] = {}
    signatures: dict[str, str] = {}
    for spec in TASKS:
        profile = (
            spec.mode,
            spec.api,
            spec.contract,
            spec.rules,
            spec.negative_fixture,
        )
        if profile in profiles:
            _fail("duplicate_family", f"self-declared semantic profile:{spec.task_id}")
        profiles.add(profile)
        if NEGATIVES[spec.mode] == REFERENCES[spec.mode]:
            _fail("invariant_not_enforced", f"identical false substitute:{spec.task_id}")
        if spec.mode not in ORACLE_TESTS or "check(" not in ORACLE_TESTS[spec.mode]:
            _fail("invariant_not_enforced", f"missing independent oracle:{spec.task_id}")
        tokens = _semantic_tokens(_semantic_corpus(out / spec.task_id, candidate=True))
        tokens_by_task[spec.task_id] = tokens
        signatures[spec.task_id] = (
            "sha256:" + hashlib.sha256("\0".join(tokens).encode("utf-8")).hexdigest()
        )

    family_pairs: list[dict[str, object]] = []
    for index, left in enumerate(TASKS):
        for right in TASKS[index + 1 :]:
            score = _semantic_similarity(
                tokens_by_task[left.task_id], tokens_by_task[right.task_id]
            )
            family_pairs.append({"left": left.task_id, "right": right.task_id, "similarity": score})
            if score >= FAMILY_SIMILARITY_LIMIT:
                _fail(
                    "duplicate_family",
                    f"{left.task_id}:{right.task_id}:{score:.4f}",
                )

    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_screen_not_completed", str(HOLDOUT_ROOT))
    holdout_dirs = {
        path.name: path
        for path in HOLDOUT_ROOT.iterdir()
        if path.is_dir() and path.name in OFFICIAL_AIDER_CPP_HOLDOUTS
    }
    if set(holdout_dirs) != OFFICIAL_AIDER_CPP_HOLDOUTS:
        _fail("benchmark_screen_not_completed", "official holdout inventory incomplete")
    holdout_inventory = {slug: _tree_hash(root) for slug, root in sorted(holdout_dirs.items())}
    excluded_support: dict[str, list[str]] = {}
    for relative in sorted(HOLDOUT_SUPPORT_ALLOWLIST):
        excluded_support[relative] = sorted(
            {
                _file_hash(root / relative)
                for root in holdout_dirs.values()
                if (root / relative).is_file()
            }
        )
    holdout_tokens = {
        slug: _semantic_tokens(_semantic_corpus(root, candidate=False))
        for slug, root in holdout_dirs.items()
    }
    holdout_pairs: list[dict[str, object]] = []
    for spec in TASKS:
        for slug in sorted(holdout_tokens):
            score = _semantic_similarity(tokens_by_task[spec.task_id], holdout_tokens[slug])
            holdout_pairs.append({"candidate": spec.task_id, "holdout": slug, "similarity": score})
            if score >= HOLDOUT_SIMILARITY_LIMIT:
                _fail(
                    "benchmark_content_overlap",
                    f"{spec.task_id}:{slug}:{score:.4f}",
                )
    return {
        "family_pairs": family_pairs,
        "family_similarity_limit": FAMILY_SIMILARITY_LIMIT,
        "holdout_inventory": holdout_inventory,
        "holdout_pairs": holdout_pairs,
        "holdout_similarity_limit": HOLDOUT_SIMILARITY_LIMIT,
        "holdout_support_allowlist": excluded_support,
        "signatures": signatures,
    }


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {spec.task_id for spec in TASKS}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {len(expected)}, found {len(actual)}")
    if require_remedy:
        _verify_remedy_records(out)
    with tempfile.TemporaryDirectory(prefix="interval-v2-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    semantic = _semantic_screen(out)
    signatures = semantic["signatures"]
    manifest_tasks: list[dict[str, object]] = []
    for spec in TASKS:
        root = out / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config.get("files", {})
        solution = [_safe_relative(item) for item in files.get("solution", [])]
        tests = [_safe_relative(item) for item in files.get("test", [])]
        examples = [_safe_relative(item) for item in files.get("example", [])]
        expected_solution = [f"{spec.task_id}.h", f"{spec.task_id}.cpp"]
        if solution != expected_solution or len(examples) != 2:
            _fail("target_reference_mismatch", spec.task_id)
        if set(solution) & (set(tests) | set(examples)):
            _fail("unsafe_path", spec.task_id)
        if any(
            name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution
        ):
            _fail("unsafe_path", spec.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("target_reference_mismatch", spec.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private = [
            *tests,
            *examples,
            "CMakeLists.txt",
            ".meta/provenance.json",
            ".meta/negative.cpp",
            ".meta/task_hidden_test.cpp",
            ".meta/task_oracle_test.cpp",
        ]
        if any(name in prompt for name in private):
            _fail("prompt_contract_incomplete", spec.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer) is not None:
            _fail("target_reference_mismatch", spec.task_id)
        malformed = (
            f"{task.editable_files[0]}\n```cpp\n// missing file\n```\n",
            answer + "\nunknown.cpp\n```cpp\n// extra\n```\n",
            "prose\n" + answer,
        )
        if any(_whole_format_code(root, item) != "whole_format_failed" for item in malformed):
            _fail("whole_format_failed", spec.task_id)
        _benchmark_screen(root)
        manifest_tasks.append(
            {
                "legacy_task_id": spec.legacy_id,
                "mode": spec.mode,
                "primary_core_objective": "achieved",
                "negative_fixture": spec.negative_fixture,
                "diversity_profile": DIVERSITY_PROFILES[spec.mode],
                "oracle_kind": (
                    "independent_state_trace"
                    if spec.mode == "ordered_mutable_calendar"
                    else "independent_direct_value"
                ),
                "semantic_signature": signatures[spec.task_id],
                "task_id": spec.task_id,
                "tree_hash": _tree_hash(root),
            }
        )
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    manifest = {
        "family_id": FAMILY_ID,
        "normalizer_version": NORMALIZER_VERSION,
        "schema_version": MANIFEST_SCHEMA,
        "screen": {
            "benchmark_contamination": "pass",
            "duplicate_family": "pass",
            "negative_fixture": "pending_execution",
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
        },
        "task_count": len(manifest_tasks),
        "tasks": manifest_tasks,
    }
    (state / "materialization-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (state / "semantic-screen.json").write_text(
        json.dumps(
            {
                "normalizer_version": NORMALIZER_VERSION,
                "result": "pass",
                **semantic,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _count_discovered(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match:
        _fail("test_discovery_failed")
    count = int(match.group(1))
    if count <= 0:
        _fail("zero_tests")
    return count


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError(f"command failed: {' '.join(command)}\n{result.stdout}")
    return result


def _update_remedies(
    out: Path, receipts: list[dict[str, object]], receipt_id: str | None = None
) -> None:
    by_id = {item["task_id"]: item for item in receipts}
    for spec in TASKS:
        path = out / ".state/remedy" / f"{spec.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(
            {
                "benchmark_screen": "pass",
                "changed_owner_paths": [
                    CURRICULUM,
                    "docs/aider-tasks-spec/aider-dsa/interval-scheduling.md",
                    "examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh",
                    "src/w8_biayn/integrations/moonlight_interval_scheduling_aider_tasks.py",
                    "src/w8_biayn/integrations/moonlight_interval_scheduling_cases.py",
                    "src/w8_biayn/integrations/moonlight_interval_scheduling_negatives.py",
                    "tests/test_moonlight_interval_scheduling_aider_tasks.py",
                ],
                "oracle_receipt": by_id[spec.task_id],
                "oracle_receipt_id": receipt_id,
                "primary_core_objective": "achieved",
                "prompt_boundary": "pass",
                "semantic_screen": "pass",
                "semantic_screen_receipt": _file_hash(out / ".state/semantic-screen.json"),
                "status": "verified",
                "strongest_local_status": "local_family_verified",
                "tree_hash_after": _tree_hash(out / spec.task_id),
            }
        )
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _owner_hashes() -> dict[str, str]:
    paths = (
        Path("src/w8_biayn/integrations/moonlight_interval_scheduling_aider_tasks.py"),
        Path("src/w8_biayn/integrations/moonlight_interval_scheduling_cases.py"),
        Path("src/w8_biayn/integrations/moonlight_interval_scheduling_negatives.py"),
        Path("examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh"),
    )
    return {path.as_posix(): _file_hash(path) for path in paths}


def _mark_executable_fixtures_pass(out: Path) -> None:
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["screen"]["negative_fixture"] = "pass"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _docker_verify(out: Path, image: str) -> None:
    if image != DESIGNATED_GRADER_IMAGE:
        _fail("grader_image_mismatch", image)
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("oracle_not_completed: docker is required")
    verify_core(out)
    expected_hashes = {spec.task_id: _tree_hash(out / spec.task_id) for spec in TASKS}
    owner_hashes = _owner_hashes()
    with tempfile.TemporaryDirectory(prefix="interval-v2-docker-") as temporary:
        archive = Path(temporary) / "family.tar"
        with tarfile.open(archive, "w") as bundle:
            for spec in TASKS:
                bundle.add(out / spec.task_id, arcname=spec.task_id, recursive=True)
        task_words = " ".join(spec.task_id for spec in TASKS)
        archive_hash = _file_hash(archive)
        script = f"""set -eu
mkdir -p /tmp/interval-input
tar -xf /input.tar -C /tmp/interval-input
echo "runtime|compiler|$(/usr/local/bin/g++ --version | head -1)"
echo "runtime|compiler_path|/usr/local/bin/g++"
echo "runtime|compiler_sha256|sha256:$(sha256sum /usr/local/bin/g++ | awk '{{print $1}}')"
echo "runtime|cmake|$(cmake --version | head -1)"
for task in {task_words}; do
  root="/tmp/interval-input/$task"
  hash=$(python3 - "$root" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
digest = hashlib.sha256()
for path in sorted(root.rglob("*")):
    if path.is_file():
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\\0" + path.read_bytes())
print("sha256:" + digest.hexdigest())
PY
)
  echo "$task|tree_hash|$hash"
  for mode in normal sanitizer; do
    build="/tmp/build-$task-$mode"
    if [ "$mode" = sanitizer ]; then
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=/usr/local/bin/g++ -DTASK_SOURCE="$root/.meta/example.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined" >/dev/null
    else
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=/usr/local/bin/g++ -DTASK_SOURCE="$root/.meta/example.cpp" >/dev/null
    fi
    cmake --build "$build" --parallel 2 >/dev/null
    count=$(ctest --test-dir "$build" -N | awk '/Total Tests:/ {{print $3}}')
    test "$count" -gt 0
    log="$build/ctest.log"
    if ! ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir "$build" --output-on-failure >"$log" 2>&1; then cat "$log"; exit 1; fi
    cat "$log"
    output_hash=$(sha256sum "$log" | awk '{{print $1}}')
    echo "$task|$mode|$count,sha256:$output_hash"
  done
  negative_build="/tmp/build-$task-negative"
  cmake -S "$root" -B "$negative_build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=/usr/local/bin/g++ -DTASK_SOURCE="$root/.meta/negative.cpp" >/dev/null
  cmake --build "$negative_build" --parallel 2 >/dev/null
  negative_count=$(ctest --test-dir "$negative_build" -N | awk '/Total Tests:/ {{print $3}}')
  test "$negative_count" -gt 0
  negative_log="$negative_build/ctest.log"
  set +e
  ctest --test-dir "$negative_build" --output-on-failure >"$negative_log" 2>&1
  negative_status=$?
  set -e
  test "$negative_status" -ne 0
  failed=$(sed -n 's/.* \\([0-9][0-9]*\\) tests failed out of.*/\\1/p' "$negative_log" | tail -1)
  test -n "$failed"
  test "$failed" -gt 0
  negative_hash=$(sha256sum "$negative_log" | awk '{{print $1}}')
  echo "$task|negative|$negative_count,$failed,sha256:$negative_hash"
done
"""
        docker_command = [
            docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--mount",
            f"type=bind,src={archive},dst=/input.tar,readonly",
            image,
            "sh",
            "-lc",
            script,
        ]
        result = subprocess.run(
            docker_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(f"locked docker verifier failed\n{result.stdout}")
    runtime: dict[str, object] = {
        "environment": "designated-locked-docker",
        "image": image,
        "network": "none",
    }
    evidence: dict[str, dict[str, object]] = {
        spec.task_id: {
            "commands": {
                "normal": [
                    f"cmake -S /tmp/interval-input/{spec.task_id} -B /tmp/build-{spec.task_id}-normal -G Unix Makefiles -DCMAKE_CXX_COMPILER=/usr/local/bin/g++ -DTASK_SOURCE=/tmp/interval-input/{spec.task_id}/.meta/example.cpp",
                    f"cmake --build /tmp/build-{spec.task_id}-normal --parallel 2",
                    f"ctest --test-dir /tmp/build-{spec.task_id}-normal -N",
                    f"ctest --test-dir /tmp/build-{spec.task_id}-normal --output-on-failure",
                ],
                "sanitizer": [
                    f"cmake -S /tmp/interval-input/{spec.task_id} -B /tmp/build-{spec.task_id}-sanitizer -G Unix Makefiles -DCMAKE_CXX_COMPILER=/usr/local/bin/g++ -DTASK_SOURCE=/tmp/interval-input/{spec.task_id}/.meta/example.cpp -DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                    f"cmake --build /tmp/build-{spec.task_id}-sanitizer --parallel 2",
                    f"ctest --test-dir /tmp/build-{spec.task_id}-sanitizer -N",
                    f"ctest --test-dir /tmp/build-{spec.task_id}-sanitizer --output-on-failure",
                ],
                "negative": [
                    f"cmake -S /tmp/interval-input/{spec.task_id} -B /tmp/build-{spec.task_id}-negative -G Unix Makefiles -DCMAKE_CXX_COMPILER=/usr/local/bin/g++ -DTASK_SOURCE=/tmp/interval-input/{spec.task_id}/.meta/negative.cpp",
                    f"cmake --build /tmp/build-{spec.task_id}-negative --parallel 2",
                    f"ctest --test-dir /tmp/build-{spec.task_id}-negative --output-on-failure",
                ],
            },
            "negative_fixture": spec.negative_fixture,
            "reference_hashes": {
                ".meta/example.cpp": _file_hash(out / spec.task_id / ".meta/example.cpp"),
                ".meta/example.h": _file_hash(out / spec.task_id / ".meta/example.h"),
            },
            "task_id": spec.task_id,
            "tree_hash": expected_hashes[spec.task_id],
            "modes": {},
        }
        for spec in TASKS
    }
    mounted_hashes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        first, kind, value = parts
        if first == "runtime":
            runtime[kind] = value
        elif kind == "tree_hash":
            mounted_hashes[first] = value
        elif kind in {"normal", "sanitizer"}:
            count, output_hash = value.split(",", 1)
            evidence[first]["modes"][kind] = {
                "discovered_tests": int(count),
                "result": "pass",
                "test_output_sha256": output_hash,
            }
        elif kind == "negative":
            count, failed, output_hash = value.split(",", 2)
            evidence[first]["negative"] = {
                "build_result": "pass",
                "discovered_tests": int(count),
                "failed_tests": int(failed),
                "result": "rejected_by_tests",
                "test_output_sha256": output_hash,
            }
    for spec in TASKS:
        task_id = spec.task_id
        if mounted_hashes.get(task_id) != expected_hashes[task_id]:
            _fail("grader_mount_hash_mismatch", task_id)
        modes = evidence[task_id]["modes"]
        if set(modes) != {"normal", "sanitizer"}:
            _fail("test_discovery_failed", task_id)
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            _fail("sanitizer_test_count_mismatch", task_id)
        negative = evidence[task_id].get("negative", {})
        if negative.get("failed_tests", 0) <= 0:
            _fail("invariant_not_enforced", task_id)
    receipts = [evidence[spec.task_id] for spec in TASKS]
    receipt_path = out / ".state/oracle-receipt.json"
    receipt_payload = {
        "archive_sha256": archive_hash,
        "docker_command": docker_command,
        "generator_hash": "sha256:"
        + hashlib.sha256(
            "\n".join(f"{key}={value}" for key, value in owner_hashes.items()).encode("utf-8")
        ).hexdigest(),
        "owner_hashes": owner_hashes,
        "runtime": runtime,
        "schema_version": "aider-interval-oracle-receipt-v3",
        "tasks": receipts,
        "verifier_script_sha256": "sha256:" + hashlib.sha256(script.encode("utf-8")).hexdigest(),
    }
    receipt_id = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(receipt_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    receipt_payload["receipt_id"] = receipt_id
    receipt_path.write_text(
        json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _mark_executable_fixtures_pass(out)
    _update_remedies(out, receipts, receipt_id)


def verify(out: Path) -> None:
    docker_image = os.environ.get("W8_INTERVAL_GRADER_IMAGE")
    if docker_image:
        _docker_verify(out, docker_image)
        return
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError(
            "oracle_not_completed: verification requires cmake and c++; "
            "set W8_INTERVAL_GRADER_IMAGE to the designated immutable image"
        )
    verify_core(out)
    receipts: list[dict[str, object]] = []
    for spec in TASKS:
        root = out / spec.task_id
        receipt: dict[str, object] = {
            "task_id": spec.task_id,
            "tree_hash": _tree_hash(root),
            "modes": {},
        }
        with tempfile.TemporaryDirectory(prefix="interval-v2-oracle-") as temporary:
            copied = Path(temporary) / spec.task_id
            shutil.copytree(root, copied)
            reference = copied / ".meta/example.cpp"
            for name, flags in (
                ("normal", []),
                (
                    "sanitizer",
                    [
                        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
                        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                    ],
                ),
            ):
                build_dir = copied / f"build-{name}"
                configure = [
                    "cmake",
                    "-G",
                    "Unix Makefiles",
                    "-S",
                    str(copied),
                    "-B",
                    str(build_dir),
                    "-DCMAKE_CXX_COMPILER=c++",
                    f"-DTASK_SOURCE={reference}",
                    *flags,
                ]
                _run(configure)
                _run(["cmake", "--build", str(build_dir), "--parallel", "2"])
                discovered = _run(["ctest", "--test-dir", str(build_dir), "-N"])
                count = _count_discovered(discovered.stdout)
                executed = _run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"])
                receipt["modes"][name] = {
                    "configure": configure,
                    "discovered_tests": count,
                    "result": "pass",
                    "test_output_sha256": hashlib.sha256(
                        executed.stdout.encode("utf-8")
                    ).hexdigest(),
                }
        modes = receipt["modes"]
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            _fail("sanitizer_test_count_mismatch", spec.task_id)
        receipts.append(receipt)
    runtime = {
        "cmake": _run(["cmake", "--version"]).stdout.splitlines()[0],
        "compiler": _run(["c++", "--version"]).stdout.splitlines()[0],
        "environment": os.environ.get("W8_BIAYN_ORACLE_RUNTIME", "host-prerequisite"),
        "image": os.environ.get("W8_BIAYN_ORACLE_IMAGE"),
    }
    receipt_path = out / ".state/oracle-receipt.json"
    receipt_path.write_text(
        json.dumps({"runtime": runtime, "tasks": receipts}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _update_remedies(out, receipts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize logic-diverse interval-scheduling v2 tasks."
    )
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
    print(f"Wrote {len(roots)} interval-scheduling v2 tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
