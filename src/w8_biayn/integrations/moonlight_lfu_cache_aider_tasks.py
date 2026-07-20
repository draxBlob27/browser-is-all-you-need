"""Materialize and verify the logic-diverse LFU-cache v3 Aider family."""

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
from w8_biayn.integrations.moonlight_lfu_cache_cases import (
    DIVERSITY_PROFILES,
    NEGATIVES,
    ORACLE_TESTS,
    REFERENCES,
    REJECTED,
    STARTERS,
    TASKS,
    TESTS,
    TaskSpec,
    header_for,
)

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/lfu-cache")
LEGACY_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/lfu-cache")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_LFU_CACHE_CURRICULUM.md"
AUDIT_REPORT = "docs/aider-tasks-spec/aider-dsa/lfu-cache.md"
SELECTED_PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-dsa-lfu-cache-v3"
MANIFEST_SCHEMA = "aider-lfu-materialization-v3"
NORMALIZER_VERSION = "lfu-family-semantic-v3"
MIN_FAMILY_ROOTS = 15
MAX_FAMILY_ROOTS = 20
FAMILY_SIMILARITY_LIMIT = 0.76
HOLDOUT_SIMILARITY_LIMIT = 0.68
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
HOLDOUT_SUPPORT_ALLOWLIST = frozenset({"test/catch.hpp", "test/tests-main.cpp"})
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table",
    "Implementation invariant", "Starter and reference", "Tests",
    "Files and metadata", "Build/oracle", "Family/contamination",
    "Optional dataset handoff", "Acceptance",
)
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset({
    "all-your-base", "allergies", "bank-account", "binary-search-tree",
    "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
    "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
    "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
    "perfect-numbers", "phone-number", "queen-attack", "robot-name",
    "space-age", "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
})

CMAKE = """cmake_minimum_required(VERSION 3.16)
project(lfu_cache_v3 LANGUAGES CXX)
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


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _all_legacy_ids() -> set[str]:
    return {spec.legacy_id for spec in TASKS} | set(REJECTED)


def _remedy_markdown(legacy_id: str, spec: TaskSpec | None) -> str:
    disposition = "replace" if spec else "reject"
    task_id = spec.task_id if spec else f"{legacy_id}-rejected-v3"
    if spec:
        objective = f"Implement `{spec.mode}` with materially independent API, state, control flow, oracle, and `{spec.negative_fixture}` fixture."
        api = spec.api
        invariant = DIVERSITY_PROFILES[spec.mode][1]
        fixture = spec.negative_fixture
    else:
        objective = f"Reject this legacy root because it {REJECTED[legacy_id]}; a renamed or policy-toggled replacement would violate the hard diversity rule."
        api = "No replacement API is admitted."
        invariant = "No counted implementation state is assigned to a rejected duplicate."
        fixture = "duplicate-family screen rejects attempted admission"
    sections = {
        "Identity": f"Legacy `{legacy_id}`; remedy `{task_id}`; disposition `{disposition}`; selected prompt `{SELECTED_PROMPT}`.",
        "Objective": objective,
        "Public API": api,
        "Behavior table": "Valid operations commit exactly; invalid, absent, duplicate, and boundary operations follow the visible contract without partial mutation.",
        "Implementation invariant": invariant,
        "Starter and reference": "The owner emits a coherent incomplete starter and independent complete reference; rejected roots emit no task.",
        "Tests": f"Visible behavior, private deterministic operation trace, complete observable state after each operation, and executed false substitute `{fixture}`.",
        "Files and metadata": "Only documentation and declared solution files are prompt-visible; tests, reference, negative fixture, CMake, provenance, and receipts remain private.",
        "Build/oracle": "Owner-controlled network-disabled Docker sanity builds clean normal and fresh ASan/UBSan trees with three equal positive tests.",
        "Family/contamination": "Normalize real docs, API, reference control flow, and tests across every counted root and all 26 official C++ holdouts.",
        "Optional dataset handoff": "not_requested; no rows, split, token/mask evidence, export, training, or release.",
        "Acceptance": "Replace roots require executed negative rejection, family/holdout screens, prompt mapping, and Docker sanity; rejected roots remain unmaterialized.",
    }
    return "# LFU remediation specification\n\n" + "\n\n".join(
        f"## {heading}\n\n{sections[heading]}" for heading in REMEDY_HEADINGS
    ) + "\n"


def _write_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state/remedy"
    by_legacy = {spec.legacy_id: spec for spec in TASKS}
    expected_names = {
        *(f"{spec.task_id}{suffix}" for spec in TASKS for suffix in (".md", ".json")),
        *(f"{legacy}-rejected-v3{suffix}" for legacy in REJECTED for suffix in (".md", ".json")),
    }
    if force and remedy.is_dir():
        for path in remedy.iterdir():
            if path.is_file() and path.name not in expected_names:
                path.unlink()
    for legacy_id in sorted(_all_legacy_ids()):
        spec = by_legacy.get(legacy_id)
        record_id = spec.task_id if spec else f"{legacy_id}-rejected-v3"
        markdown = _remedy_markdown(legacy_id, spec)
        record = {
            "disposition": "replace" if spec else "reject",
            "family_id": FAMILY_ID,
            "legacy_task_id": legacy_id,
            "primary_core_objective": "planned" if spec else "not_achieved_duplicate",
            "selected_prompt": SELECTED_PROMPT,
            "status": "planned" if spec else "rejected",
            "strongest_local_status": "planned" if spec else "rejected",
            "task_id": record_id,
            "tree_hash_before": _tree_hash(LEGACY_OUT / legacy_id),
            "remedy_spec_hash": "sha256:" + hashlib.sha256(markdown.encode()).hexdigest(),
        }
        _write(remedy / f"{record_id}.md", markdown, force)
        _write(remedy / f"{record_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", force)


def _instructions(spec: TaskSpec) -> str:
    return (
        f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract} {spec.rules} "
        f"The substantive mechanism is `{spec.mode}` and the public operation set is `{spec.api}`. "
        "The diagnostic view is the complete deterministic observable state after every operation. "
        "Reject invalid identifiers, capacities, weights, time movement, or commands without partial mutation.\n"
    )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_OUT.resolve():
        _fail("unsafe_path", "legacy LFU root is immutable")
    expected = {spec.task_id for spec in TASKS}
    if force and out.is_dir():
        stale_receipt = out / ".state/oracle-receipt.json"
        if stale_receipt.is_file():
            stale_receipt.unlink()
        for child in out.iterdir():
            if not child.is_dir() or child.name in expected or child.name == ".state":
                continue
            provenance_path = child / ".meta/provenance.json"
            if not provenance_path.is_file():
                _fail("unsafe_path", f"refusing to prune unowned directory:{child}")
            provenance = json.loads(provenance_path.read_text())
            if provenance.get("curriculum_document") != CURRICULUM:
                _fail("unsafe_path", f"refusing to prune foreign directory:{child}")
            shutil.rmtree(child)
    roots: list[Path] = []
    for spec in TASKS:
        root = out / spec.task_id
        header = header_for(spec)
        config = {
            "authors": ["w8-biayn"], "blurb": spec.contract,
            "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]},
        }
        provenance = {
            "benchmark_separation": "Clean-room LFU mechanism with independent API, state, control flow, oracle, and executed false substitute.",
            "curriculum_document": CURRICULUM, "family_id": FAMILY_ID,
            "legacy_task_id": spec.legacy_id, "origin": "newly authored in-repository v3 replacement",
            "selected_prompt": SELECTED_PROMPT, "status": "local task artifact; not admitted SFT data",
            "task_spec_revision": 3,
        }
        files = {
            ".docs/introduction.md": f"# {spec.title}\n\nA clean-room diagnostic for `{spec.mode}`.\n",
            ".docs/instructions.md": _instructions(spec),
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f"[visible]\ndescription = \"public {spec.mode} behavior\"\n\n[hidden]\ndescription = \"complete operation trace and {spec.negative_fixture}\"\n",
            "task.h": header, "task.cpp": STARTERS[spec.mode], ".meta/example.h": header,
            ".meta/example.cpp": REFERENCES[spec.mode].replace("CLASS", spec.class_name),
            "task_visible_test.cpp": TESTS[spec.mode][0], ".meta/task_hidden_test.cpp": TESTS[spec.mode][1],
            ".meta/task_oracle_test.cpp": ORACLE_TESTS[spec.mode],
            ".meta/negative.cpp": NEGATIVES[spec.mode].replace("CLASS", spec.class_name),
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_remedies(out, force)
    return tuple(roots)


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("unsafe_path", "empty path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _whole_format_code(task_dir: Path, content: str) -> str | None:
    try:
        parsed = parse_whole_file_blocks(content)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(parsed) == set(load_task(task_dir).editable_files) else "whole_format_failed"


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state/remedy"
    expected = {*(spec.task_id for spec in TASKS), *(f"{legacy}-rejected-v3" for legacy in REJECTED)}
    records = {path.stem: path for path in remedy.glob("*.json")}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "20 audited legacy roots are required")
    for record_id, path in records.items():
        record = json.loads(path.read_text())
        markdown_path = remedy / f"{record_id}.md"
        if record.get("task_id") != record_id or not markdown_path.is_file():
            _fail("remedy_disposition_conflict", record_id)
        expected_disposition = "reject" if record_id.endswith("-rejected-v3") else "replace"
        if record.get("disposition") != expected_disposition:
            _fail("remedy_disposition_conflict", record_id)
        text = markdown_path.read_text()
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", record_id)
        if record.get("remedy_spec_hash") != "sha256:" + hashlib.sha256(text.encode()).hexdigest():
            _fail("remedy_spec_incomplete", f"stale hash:{record_id}")
        legacy = LEGACY_OUT / record["legacy_task_id"]
        if not legacy.is_dir() or record.get("tree_hash_before") != _tree_hash(legacy):
            _fail("generator_output_drift", f"legacy changed:{record_id}")


_SEMANTIC_KEYWORDS = frozenset({
    "break", "case", "class", "const", "continue", "else", "false", "for", "if",
    "private", "public", "return", "struct", "switch", "true", "while", "sort",
    "lower_bound", "min_element", "priority_queue", "map", "set", "vector", "list",
    "deque", "optional", "erase", "insert", "push_back", "pop_front", "front", "size",
})


def _semantic_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", text)
    raw = re.findall(r"::|<=|>=|==|!=|&&|\|\||\+\+|--|->|[A-Za-z_][A-Za-z0-9_]*|\d+|[{}()\[\];,.:?+*/%<>=!&|~-]", text.lower())
    return tuple("NUM" if token.isdigit() else (token if token in _SEMANTIC_KEYWORDS else "ID") if re.fullmatch(r"[a-z_][a-z0-9_]*", token) else token for token in raw)


def _ngrams(tokens: tuple[str, ...], width: int = 5) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tokens}
    return {tokens[i:i + width] for i in range(len(tokens) - width + 1)}


def _similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a, b = _ngrams(left), _ngrams(right)
    return len(a & b) / len(a | b) if a | b else 1.0


def _semantic_corpus(root: Path, *, candidate: bool) -> str:
    chunks = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".h", ".hpp", ".cpp"}:
            continue
        relative = path.relative_to(root).as_posix()
        if candidate and relative == ".meta/negative.cpp":
            continue
        if not candidate and relative in HOLDOUT_SUPPORT_ALLOWLIST:
            continue
        chunks.append(path.read_text(errors="replace"))
    return "\n".join(chunks)


def _benchmark_slug_screen(root: Path) -> None:
    corpus = "\n".join(path.read_text(errors="ignore") for path in root.rglob("*") if path.is_file()).lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", corpus):
            _fail("benchmark_id_overlap", f"{root.name}:{slug}")
    for phrase in ("aider-ai/polyglot", "exercism c++ exercise", "upstream polyglot benchmark"):
        if phrase in corpus:
            _fail("benchmark_content_overlap", f"{root.name}:{phrase}")


def _semantic_screen(out: Path) -> dict[str, object]:
    if not MIN_FAMILY_ROOTS <= len(TASKS) <= MAX_FAMILY_ROOTS:
        _fail("duplicate_family", "count outside hard 15-20 bound")
    if set(DIVERSITY_PROFILES) != {spec.mode for spec in TASKS}:
        _fail("duplicate_family", "profile inventory mismatch")
    for dimension in range(7):
        if len({profile[dimension] for profile in DIVERSITY_PROFILES.values()}) != len(TASKS):
            _fail("duplicate_family", f"duplicate diversity dimension:{dimension}")
    tokens: dict[str, tuple[str, ...]] = {}
    signatures: dict[str, str] = {}
    for spec in TASKS:
        if REFERENCES[spec.mode] == NEGATIVES[spec.mode] or "check(" not in ORACLE_TESTS[spec.mode]:
            _fail("invariant_not_enforced", spec.task_id)
        value = _semantic_tokens(_semantic_corpus(out / spec.task_id, candidate=True))
        tokens[spec.task_id] = value
        signatures[spec.task_id] = "sha256:" + hashlib.sha256("\0".join(value).encode()).hexdigest()
    family_pairs = []
    for i, left in enumerate(TASKS):
        for right in TASKS[i + 1:]:
            score = _similarity(tokens[left.task_id], tokens[right.task_id])
            family_pairs.append({"left": left.task_id, "right": right.task_id, "similarity": score})
            if score >= FAMILY_SIMILARITY_LIMIT:
                _fail("duplicate_family", f"{left.task_id}:{right.task_id}:{score:.4f}")
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_screen_not_completed", str(HOLDOUT_ROOT))
    holdouts = {p.name: p for p in HOLDOUT_ROOT.iterdir() if p.is_dir() and p.name in OFFICIAL_AIDER_CPP_HOLDOUTS}
    if set(holdouts) != OFFICIAL_AIDER_CPP_HOLDOUTS:
        _fail("benchmark_screen_not_completed", "official inventory incomplete")
    holdout_tokens = {name: _semantic_tokens(_semantic_corpus(root, candidate=False)) for name, root in holdouts.items()}
    holdout_pairs = []
    for spec in TASKS:
        for name, value in holdout_tokens.items():
            score = _similarity(tokens[spec.task_id], value)
            holdout_pairs.append({"candidate": spec.task_id, "holdout": name, "similarity": score})
            if score >= HOLDOUT_SIMILARITY_LIMIT:
                _fail("benchmark_content_overlap", f"{spec.task_id}:{name}:{score:.4f}")
    return {
        "family_pairs": family_pairs, "family_similarity_limit": FAMILY_SIMILARITY_LIMIT,
        "holdout_inventory": {name: _tree_hash(root) for name, root in sorted(holdouts.items())},
        "holdout_pairs": holdout_pairs, "holdout_similarity_limit": HOLDOUT_SIMILARITY_LIMIT,
        "signatures": signatures,
    }


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {spec.task_id for spec in TASKS}
    actual = {p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {len(expected)}, found {len(actual)}")
    if require_remedy:
        _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="lfu-v3-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    semantic = _semantic_screen(out)
    manifest_tasks = []
    for spec in TASKS:
        root = out / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        files = config.get("files", {})
        solution = [_safe_relative(x) for x in files.get("solution", [])]
        tests = [_safe_relative(x) for x in files.get("test", [])]
        examples = [_safe_relative(x) for x in files.get("example", [])]
        if solution != [f"{spec.task_id}.h", f"{spec.task_id}.cpp"] or len(examples) != 2:
            _fail("target_reference_mismatch", spec.task_id)
        if set(solution) & (set(tests) | set(examples)) or any(
            name.startswith((".docs/", ".meta/")) or name == "CMakeLists.txt"
            for name in solution
        ):
            _fail("unsafe_path", spec.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("target_reference_mismatch", spec.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private = [
            *tests, *examples, "CMakeLists.txt", ".meta/provenance.json",
            ".meta/negative.cpp", ".meta/task_hidden_test.cpp",
            ".meta/task_oracle_test.cpp",
        ]
        if any(name in prompt for name in private):
            _fail("prompt_contract_incomplete", spec.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        malformed = (
            f"{task.editable_files[0]}\n```cpp\n// missing\n```\n",
            answer + "\nunknown.cpp\n```cpp\n// extra\n```\n",
            "prose\n" + answer,
        )
        if _whole_format_code(root, answer) or any(
            _whole_format_code(root, value) != "whole_format_failed" for value in malformed
        ):
            _fail("whole_format_failed", spec.task_id)
        _benchmark_slug_screen(root)
        manifest_tasks.append({
            "diversity_profile": DIVERSITY_PROFILES[spec.mode],
            "legacy_task_id": spec.legacy_id,
            "mode": spec.mode,
            "negative_fixture": spec.negative_fixture,
            "oracle_kind": "independent_value_trace_after_every_operation",
            "primary_core_objective": "achieved",
            "semantic_signature": semantic["signatures"][spec.task_id],
            "task_id": spec.task_id,
            "tree_hash": _tree_hash(root),
        })
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    manifest = {
        "audited_legacy_count": len(_all_legacy_ids()),
        "family_id": FAMILY_ID,
        "normalizer_version": NORMALIZER_VERSION,
        "rejected": [
            {"legacy_task_id": key, "reason": value} for key, value in sorted(REJECTED.items())
        ],
        "schema_version": MANIFEST_SCHEMA,
        "screen": {
            "benchmark_contamination": "pass", "duplicate_family": "pass",
            "negative_fixture": "pending_execution", "prompt_boundary": "pass",
            "reference_mapping": "pass",
        },
        "status": "semantically_admitted_pending_docker",
        "task_count": len(manifest_tasks),
        "tasks": manifest_tasks,
    }
    (state / "materialization-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (state / "semantic-screen.json").write_text(
        json.dumps(
            {"normalizer_version": NORMALIZER_VERSION, "result": "pass", **semantic},
            indent=2,
            sort_keys=True,
        ) + "\n"
    )


def _owner_hashes() -> dict[str, str]:
    paths = (
        Path("src/w8_biayn/integrations/moonlight_lfu_cache_aider_tasks.py"),
        Path("src/w8_biayn/integrations/moonlight_lfu_cache_cases.py"),
        Path("examples/slime/moonlight_cpp_perf/prepare_lfu_cache_aider_tasks.sh"),
    )
    return {path.as_posix(): _file_hash(path) for path in paths}


def _update_verified_state(out: Path, receipts: list[dict[str, object]], receipt_id: str) -> None:
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["screen"]["negative_fixture"] = "pass"
    manifest["status"] = "local_family_verified"
    manifest["oracle_receipt"] = ".state/oracle-receipt.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    by_id = {row["task_id"]: row for row in receipts}
    for spec in TASKS:
        path = out / ".state/remedy" / f"{spec.task_id}.json"
        record = json.loads(path.read_text())
        record.update({
            "benchmark_screen": "pass", "family_screen": "pass",
            "changed_owner_paths": [
                CURRICULUM,
                AUDIT_REPORT,
                "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
                "examples/slime/moonlight_cpp_perf/prepare_lfu_cache_aider_tasks.sh",
                "src/w8_biayn/integrations/moonlight_lfu_cache_aider_tasks.py",
                "src/w8_biayn/integrations/moonlight_lfu_cache_cases.py",
                "tests/test_moonlight_lfu_cache_aider_tasks.py",
            ],
            "oracle_receipt": by_id[spec.task_id], "oracle_receipt_id": receipt_id,
            "primary_core_objective": "achieved", "prompt_boundary": "pass",
            "semantic_screen": "pass",
            "semantic_screen_receipt": _file_hash(out / ".state/semantic-screen.json"),
            "status": "verified",
            "strongest_local_status": "local_family_verified",
            "tree_hash_after": _tree_hash(out / spec.task_id),
        })
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def _docker_script(task_words: str) -> str:
    return rf'''set -eu
mkdir -p /tmp/lfu-input
tar -xf /input.tar -C /tmp/lfu-input
echo "runtime|compiler|$(/usr/local/bin/g++ --version | head -1)"
echo "runtime|compiler_path|/usr/local/bin/g++"
echo "runtime|compiler_sha256|sha256:$(sha256sum /usr/local/bin/g++ | awk '{{print $1}}')"
echo "runtime|cmake|$(cmake --version | head -1)"
for task in {task_words}; do
 root="/tmp/lfu-input/$task"
 hash=$(python3 - "$root" <<'PY'
import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1]);d=hashlib.sha256()
for p in sorted(r.rglob("*")):
 if p.is_file():d.update(p.relative_to(r).as_posix().encode()+b"\0"+p.read_bytes())
print("sha256:"+d.hexdigest())
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
  ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ctest --test-dir "$build" --output-on-failure >"$log" 2>&1
  echo "$task|$mode|$count,sha256:$(sha256sum "$log" | awk '{{print $1}}')"
 done
 build="/tmp/build-$task-negative"
 cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=/usr/local/bin/g++ -DTASK_SOURCE="$root/.meta/negative.cpp" >/dev/null
 cmake --build "$build" --parallel 2 >/dev/null
 count=$(ctest --test-dir "$build" -N | awk '/Total Tests:/ {{print $3}}')
 test "$count" -gt 0
 set +e
 ctest --test-dir "$build" --output-on-failure >"$build/ctest.log" 2>&1
 status=$?
 set -e
 test "$status" -ne 0
 failed=$(sed -n 's/.* \([0-9][0-9]*\) tests failed out of.*/\1/p' "$build/ctest.log" | tail -1)
 test "$failed" -gt 0
 echo "$task|negative|$count,$failed,sha256:$(sha256sum "$build/ctest.log" | awk '{{print $1}}')"
done
'''


def _docker_verify(out: Path, image: str) -> None:
    if image != SANITY_IMAGE:
        _fail("grader_image_mismatch", image)
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("oracle_not_completed: docker is required for mandatory Docker sanity")
    verify_core(out)
    expected_hashes = {spec.task_id: _tree_hash(out / spec.task_id) for spec in TASKS}
    owner_hashes = _owner_hashes()
    with tempfile.TemporaryDirectory(prefix="lfu-v3-docker-") as temporary:
        archive = Path(temporary) / "family.tar"
        with tarfile.open(archive, "w") as bundle:
            for spec in TASKS:
                bundle.add(out / spec.task_id, arcname=spec.task_id)
        script = _docker_script(" ".join(spec.task_id for spec in TASKS))
        command = [
            docker, "run", "--rm", "--network", "none", "--mount",
            f"type=bind,src={archive},dst=/input.tar,readonly", image, "sh", "-lc", script,
        ]
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        if result.returncode:
            raise RuntimeError(f"docker sanity verifier failed\n{result.stdout}")
        archive_hash = _file_hash(archive)
    runtime: dict[str, object] = {
        "environment": "docker_sanity", "image": image, "network": "none"
    }
    evidence: dict[str, dict[str, object]] = {
        spec.task_id: {
            "commands": {
                kind: [
                    f"cmake/ctest {kind} in /tmp/lfu-input/{spec.task_id} with /usr/local/bin/g++"
                ] for kind in ("normal", "sanitizer", "negative")
            },
            "negative_fixture": spec.negative_fixture,
            "reference_hashes": {
                name: _file_hash(out / spec.task_id / name)
                for name in (".meta/example.h", ".meta/example.cpp")
            },
            "task_id": spec.task_id,
            "tree_hash": expected_hashes[spec.task_id],
            "modes": {},
        } for spec in TASKS
    }
    mounted: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        first, kind, value = parts
        if first == "runtime":
            runtime[kind] = value
        elif kind == "tree_hash":
            mounted[first] = value
        elif kind in {"normal", "sanitizer"}:
            count, output_hash = value.split(",", 1)
            evidence[first]["modes"][kind] = {
                "discovered_tests": int(count), "result": "pass",
                "test_output_sha256": output_hash,
            }
        elif kind == "negative":
            count, failed, output_hash = value.split(",", 2)
            evidence[first]["negative"] = {
                "discovered_tests": int(count), "failed_tests": int(failed),
                "result": "rejected_by_tests", "test_output_sha256": output_hash,
            }
    for spec in TASKS:
        task_id = spec.task_id
        if mounted.get(task_id) != expected_hashes[task_id]:
            _fail("grader_mount_hash_mismatch", task_id)
        modes = evidence[task_id]["modes"]
        if set(modes) != {"normal", "sanitizer"}:
            _fail("test_discovery_failed", task_id)
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            _fail("sanitizer_test_count_mismatch", task_id)
        if evidence[task_id].get("negative", {}).get("failed_tests", 0) <= 0:
            _fail("invariant_not_enforced", task_id)
    receipts = [evidence[spec.task_id] for spec in TASKS]
    payload = {
        "archive_sha256": archive_hash,
        "docker_command": command,
        "generator_hash": "sha256:" + hashlib.sha256(
            "\n".join(f"{key}={value}" for key, value in owner_hashes.items()).encode()
        ).hexdigest(),
        "owner_hashes": owner_hashes,
        "runtime": runtime,
        "schema_version": "aider-lfu-oracle-receipt-v3",
        "tasks": receipts,
        "verifier_script_sha256": "sha256:" + hashlib.sha256(script.encode()).hexdigest(),
    }
    receipt_id = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload["receipt_id"] = receipt_id
    (out / ".state/oracle-receipt.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    _update_verified_state(out, receipts, receipt_id)


def verify(out: Path) -> None:
    _docker_verify(out, os.environ.get("W8_LFU_SANITY_IMAGE", SANITY_IMAGE))


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
    print(
        f"Wrote {len(roots)} LFU-cache v3 tasks; rejected {len(REJECTED)} duplicates under {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
