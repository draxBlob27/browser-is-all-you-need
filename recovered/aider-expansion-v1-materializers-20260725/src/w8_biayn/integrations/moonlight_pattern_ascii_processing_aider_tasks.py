"""Own the expansion-v1 Pattern and ASCII processing family."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_pattern_ascii_processing_cases import (
    CASES,
    EXAMPLES,
    INTRODUCTIONS,
    Case,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
DEFAULT_OUT = EXPANSION_ROOT / "text-grid-logic/pattern-ascii-processing"
CURRICULUM_RELPATH = (
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_PATTERN_ASCII_PROCESSING_EXPANSION_CURRICULUM.md"
)
FAMILY_SPEC_RELPATH = "docs/aider-tasks-spec/aider-text-grid-logic/pattern-ascii-processing.md"
GENERATOR_RELPATH = (
    "src/w8_biayn/integrations/moonlight_pattern_ascii_processing_aider_tasks.py"
)
CASES_RELPATH = (
    "src/w8_biayn/integrations/moonlight_pattern_ascii_processing_cases.py"
)
CURRICULUM = REPO_ROOT / CURRICULUM_RELPATH
FAMILY_SPEC = REPO_ROOT / FAMILY_SPEC_RELPATH
SELECTED_PROMPTS = (
    "docs/aider-tasks-spec/prompts/generate-family-spec.md",
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
)
FAMILY_ID = "expansion-v1-pattern-ascii-processing-v1"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square",
        "diamond", "dnd-character", "gigasecond", "grade-school",
        "kindergarten-garden", "knapsack", "linked-list", "meetup",
        "parallel-letter-frequency", "perfect-numbers", "phone-number",
        "queen-attack", "robot-name", "space-age", "spiral-matrix",
        "sublist", "yacht", "zebra-puzzle",
    }
)
HARD_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
HARD_THRESHOLDS = {dimension: 0.86 for dimension in HARD_DIMENSIONS}
CONTROL_KINDS = (
    "domain-identifier-renamed",
    "constants-or-policy-only",
    "opposite-end-selection",
)
NORMALIZER = "pattern-ascii-v3-role-aware-contract-neutral-wide-cpp-shingles"
REMEDY_SPEC_RELPATH = (
    ".w8-biayn/data/aider-tasks-expansion-v1/text-grid-logic/pattern-ascii-processing/"
    ".state/remedy/cycle-02-remedy-spec.md"
)


class VerificationError(RuntimeError):
    pass


def _fail(code: str, detail: str = "") -> None:
    raise VerificationError(f"{code}: {detail}")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha256(path.read_bytes())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if not include_state and relative.startswith(".state/"):
            continue
        name = relative.encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _reference_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in (".meta/example.h", ".meta/example.cpp"):
        data = (root / relative).read_bytes()
        digest.update(relative.encode())
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _reference_content_hash(root: Path) -> str:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    paths = config.get("files", {}).get("example", [])
    return _sha256(b"".join((root / relative).read_bytes() for relative in paths))


def _generator_revision() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__), Path(__file__).with_name("moonlight_pattern_ascii_processing_cases.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str, *, force: bool = False) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, value: object, *, force: bool = True) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n", force=force)


def _header(case: Case) -> str:
    return (
        "#pragma once\n"
        "#include <cstddef>\n#include <cstdint>\n#include <map>\n"
        "#include <string>\n#include <tuple>\n#include <utility>\n#include <vector>\n"
        "namespace curriculum {\n"
        f"{case.types}\n{case.return_type} {case.function}({case.params});\n"
        "}\n"
    )


def _separate_terminal_statements(body: str) -> str:
    """Keep compact case definitions warning-clean without touching loop headers."""
    rendered: list[str] = []
    quote = ""
    escaped = False
    parenthesis_depth = 0
    for character in body:
        rendered.append(character)
        if escaped:
            escaped = False
            continue
        if quote and character == "\\":
            escaped = True
            continue
        if quote:
            if character == quote:
                quote = ""
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "(":
            parenthesis_depth += 1
        elif character == ")":
            parenthesis_depth -= 1
        elif character == ";" and parenthesis_depth == 0:
            rendered.append("\n")
    return "".join(rendered)


def _source(case: Case, body: str | None = None, *, header_prefix: str = "") -> str:
    implementation = _separate_terminal_statements(body or case.body)
    return (
        f'#include "{header_prefix}{case.task_id}.h"\n'
        "#include <algorithm>\n#include <cmath>\n#include <limits>\n"
        "#include <map>\n#include <set>\n#include <string>\n#include <tuple>\n"
        "#include <utility>\n#include <vector>\n"
        "namespace curriculum {\n"
        f"{case.return_type} {case.function}({case.params}) {{\n{implementation}\n}}\n"
        "}\n"
    )


def _negative(case: Case) -> str:
    if case.body.count(case.negative_old) != 1:
        _fail("negative_fixture_drift", case.task_id)
    return _source(
        case,
        case.body.replace(case.negative_old, case.negative_new),
        header_prefix="../",
    )


def _test(case: Case, body: str) -> str:
    return (
        f'#include "{case.task_id}.h"\n'
        "#include <map>\n#include <string>\n#include <tuple>\n"
        "#include <utility>\n#include <vector>\n"
        "using namespace curriculum;\nint main() {\n"
        f"{_separate_terminal_statements(body)}\n"
        "}\n"
    )


def _starter(case: Case) -> str:
    return (
        f'#include "{case.task_id}.h"\n'
        "namespace curriculum {\n"
        f"{case.return_type} {case.function}({case.params}) {{ return {{}}; }}\n"
        "}\n"
    )


def _cmake(case: Case) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.cpp" CACHE FILEPATH "Solution source")
foreach(target task_visible task_hidden)
  if(target STREQUAL "task_visible")
    add_executable(${{target}} ${{TASK_SOURCE}} task_visible_test.cpp)
  else()
    add_executable(${{target}} ${{TASK_SOURCE}} .meta/task_hidden_test.cpp)
  endif()
  target_include_directories(${{target}} PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
add_executable(task_negative .meta/negative.cpp task_visible_test.cpp)
target_include_directories(task_negative PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(task_negative PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME negative_fixture COMMAND task_negative)
set_tests_properties(negative_fixture PROPERTIES WILL_FAIL TRUE)
'''


def _instructions(case: Case) -> str:
    return f"""# Instructions

Implement `{case.function}` in namespace `curriculum` using the exact public
declarations in `{case.task_id}.h`.

{case.contract}

Work the answer out from the inputs on every call by {case.objective}; a
stored table of precomputed answers or a general-purpose library routine
would only cover the inputs someone anticipated, not every valid call.

## Example

{EXAMPLES[case.task_id]}

The operation is deterministic and must not mutate its inputs. Any invalid,
duplicate, absent, or out-of-bound input described above returns the default
result with `valid == false`, empty output containers, and zero diagnostics.
Do not clamp, sort away, or partially apply invalid input. Preserve the stated
ordering and tie behavior exactly.
"""


def _task_files(case: Case) -> dict[str, str]:
    header = _header(case)
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.objective.capitalize() + ".",
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "schema_version": "aider-expansion-provenance-v1",
        "family_id": FAMILY_ID,
        "task_id": case.task_id,
        "lineage": "new-root",
        "parent_task_id": None,
        "origin": "clean-room repository-authored expansion task",
        "curriculum_document": CURRICULUM_RELPATH,
        "family_specification": FAMILY_SPEC_RELPATH,
        "selected_prompts": list(SELECTED_PROMPTS),
        "mechanism": case.objective,
        "semantic_profile": {
            "dimensions": list(HARD_DIMENSIONS),
            "mechanism_witnesses": list(case.profile),
        },
        "official_benchmark_assets_used": False,
        "license": "repository clean-room task material",
        "status": "local candidate artifact; not admitted SFT data",
    }
    files = {
        ".docs/introduction.md": (
            f"# {case.title}\n\n{INTRODUCTIONS[case.task_id]}\n"
        ),
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            '[visible]\ndescription = "principal transformation and exact diagnostics"\n\n'
            '[hidden]\ndescription = "invalid, absent, boundary, ordering, tie, and discriminator cases"\n'
        ),
        ".meta/example.h": header,
        ".meta/example.cpp": _source(case),
        ".meta/task_hidden_test.cpp": _test(case, case.hidden),
        ".meta/negative.cpp": _negative(case),
        f"{case.task_id}.h": header,
        f"{case.task_id}.cpp": _starter(case),
        "task_visible_test.cpp": _test(case, case.visible),
        "CMakeLists.txt": _cmake(case),
    }
    return task_named_files(Path(case.task_id), files)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_output(out: Path) -> Path:
    resolved = out.resolve()
    expansion = EXPANSION_ROOT.resolve()
    if not _is_relative_to(resolved, expansion):
        _fail("unsafe_path", f"output must be beneath {expansion}: {resolved}")
    if _is_relative_to(resolved, LEGACY_ROOT.resolve()) or _is_relative_to(resolved, REVERIFY_ROOT.resolve()):
        _fail("unsafe_path", "existing generated trees are read-only")
    cursor = resolved
    while cursor != expansion.parent and cursor != cursor.parent:
        if cursor.is_symlink():
            _fail("unsafe_path", f"symlinked output component: {cursor}")
        if cursor == expansion:
            break
        cursor = cursor.parent
    return resolved


def _real_task_roots(tree: Path) -> list[Path]:
    if not tree.is_dir():
        return []
    return sorted(
        path.parent.parent
        for path in tree.rglob(".meta/config.json")
        if ".state" not in path.parts
    )


def _semantic_text(root: Path) -> str:
    pieces: list[str] = []
    for relative in (
        ".docs/introduction.md", ".docs/instructions.md", ".meta/example.h",
        ".meta/example.cpp", "task_visible_test.cpp", ".meta/task_hidden_test.cpp",
    ):
        path = root / relative
        if path.is_file():
            pieces.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(pieces)


def _inventory_entry(root: Path, tree_name: str) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    task_id = root.name
    prompt_material = "\n".join(
        (root / path).read_text(encoding="utf-8", errors="ignore")
        for path in (".docs/introduction.md", ".docs/instructions.md")
        if (root / path).is_file()
    )
    reference_paths = config.get("files", {}).get("example", [])
    test_paths = config.get("files", {}).get("test", [])
    reference = b"".join((root / path).read_bytes() for path in reference_paths if (root / path).is_file())
    tests = b"".join((root / path).read_bytes() for path in test_paths if (root / path).is_file())
    public_api = (root / reference_paths[0]).read_bytes() if reference_paths and (root / reference_paths[0]).is_file() else b""
    contract = (root / ".docs/instructions.md").read_bytes() if (root / ".docs/instructions.md").is_file() else b""
    provenance_path = root / ".meta/provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.is_file() else {}
    return {
        "tree": tree_name,
        "task_id": task_id,
        "root": root.relative_to(REPO_ROOT).as_posix(),
        "tree_hash": _tree_hash(root),
        "prompt_hash": _sha256(prompt_material.encode()),
        "reference_hash": _sha256(reference),
        "api_hash": _sha256(public_api),
        "tests_hash": _sha256(tests),
        "contract_hash": _sha256(contract),
        "lineage_hash": _sha256(json.dumps({
            "family_id": provenance.get("family_id"),
            "lineage": provenance.get("lineage"),
            "parent_task_id": provenance.get("parent_task_id"),
        }, sort_keys=True, separators=(",", ":")).encode()),
        "semantic_hash": _sha256(" ".join(_normalized_tokens(_semantic_text(root))).encode()),
    }


def _freeze_source_inventory(out: Path) -> dict[str, object]:
    resolved_out = out.resolve()
    expansion_roots = [
        root for root in _real_task_roots(EXPANSION_ROOT)
        if not _is_relative_to(root.resolve(), resolved_out)
    ]
    entries = [
        *(_inventory_entry(root, "legacy") for root in _real_task_roots(LEGACY_ROOT)),
        *(_inventory_entry(root, "reverify") for root in _real_task_roots(REVERIFY_ROOT)),
        *(_inventory_entry(root, "expansion") for root in expansion_roots),
    ]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    inventory = {
        "schema_version": "pattern-ascii-source-inventory-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "legacy_count": sum(entry["tree"] == "legacy" for entry in entries),
        "reverify_count": sum(entry["tree"] == "reverify" for entry in entries),
        "expansion_count": sum(entry["tree"] == "expansion" for entry in entries),
        "excluded_owned_family": resolved_out.relative_to(REPO_ROOT).as_posix(),
        "plan_snapshot_reverify_count": 709,
        "entries_hash": _sha256(canonical),
        "entries": entries,
    }
    _write_json(out / ".state/source-inventory.json", inventory)
    return inventory


def _clear_owned_roots(out: Path) -> None:
    if not out.exists():
        return
    for root in _real_task_roots(out):
        provenance_path = root / ".meta/provenance.json"
        if not provenance_path.is_file():
            _fail("foreign_generated_root", str(root))
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance.get("family_id") != FAMILY_ID:
            _fail("foreign_generated_root", str(root))
        shutil.rmtree(root)
    controls = out / ".state/adversarial-controls"
    if controls.exists():
        shutil.rmtree(controls)
    receipts = out / ".state/task-receipts"
    if receipts.exists():
        shutil.rmtree(receipts)
    for stale in (
        "audit-subject.json",
        "core-verification.json",
        "creator-preflight.json",
        "docker-sanity.json",
        "family-screen.json",
        "host-iteration.json",
    ):
        path = out / ".state" / stale
        if path.exists():
            path.unlink()


def _write_root(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        _write(root / relative, content)


def _replace_case_files(files: dict[str, str], replacements: Sequence[tuple[str, str]]) -> dict[str, str]:
    changed: dict[str, str] = {}
    for relative, content in files.items():
        new_relative = relative
        new_content = content
        for old, new in replacements:
            new_relative = new_relative.replace(old, new)
            new_content = new_content.replace(old, new)
        changed[new_relative] = new_content
    return changed


def _control_files(kind: str) -> tuple[str, dict[str, str], str]:
    if kind == "domain-identifier-renamed":
        base = CASES[0]
        files = _replace_case_files(
            _task_files(base),
            (
                (base.task_id, "recursive-banner-tiles"),
                ("Sierpinski", "Recursive banner"),
                ("sierpinski", "recursive_banner"),
                ("CarpetStencil", "BannerTiles"),
                ("cut_sierpinski_carpet", "cut_recursive_banner"),
                ("carpet", "banner"),
            ),
        )
        return base.task_id, files, "complete domain and identifier rename"
    if kind == "constants-or-policy-only":
        base = CASES[1]
        files = _replace_case_files(
            _task_files(base),
            (
                ("generation_count > 32", "generation_count > 33"),
                ("[1,32]", "[1,33]"),
                ("generation_count is in [1,32]", "generation_count is in [1,33]"),
            ),
        )
        return base.task_id, files, "maximum-generation constant changed only"
    if kind == "opposite-end-selection":
        base = next(case for case in CASES if case.task_id == "vertical-seam-carve")
        files = _replace_case_files(
            _task_files(base),
            (
                ("p<best", "p>best"),
                (
                    "if(cost.back()[c]<cost.back()[end])end=c",
                    "if(cost.back()[c]<cost.back()[end]||(cost.back()[c]==cost.back()[end]&&c>end))end=c",
                ),
                ("smaller predecessor column", "larger predecessor column"),
                ("smaller column", "larger column"),
                ("{0,0}", "{1,1}"),
                ("std::vector<std::string>{\"b\",\"d\"}", "std::vector<std::string>{\"a\",\"c\"}"),
            ),
        )
        negative = files[".meta/negative.cpp"]
        files[".meta/negative.cpp"] = negative.replace(
            "p>best",
            "p<best",
            1,
        )
        return base.task_id, files, "leftmost seam ties changed coherently to rightmost"
    _fail("unknown_adversarial_control", kind)


def _write_controls(out: Path) -> dict[str, object]:
    records: dict[str, object] = {}
    for kind in CONTROL_KINDS:
        base_id, files, mutation = _control_files(kind)
        root = out / ".state/adversarial-controls" / kind
        _write_root(root, files)
        records[kind] = {
            "base_task_id": base_id,
            "mutation": mutation,
            "changed_file_count": sum(
                _task_files(next(case for case in CASES if case.task_id == base_id)).get(path) != content
                for path, content in files.items()
            ),
            "root": root.relative_to(out).as_posix(),
            "tree_hash": _tree_hash(root),
        }
    _write_json(out / ".state/adversarial-controls.json", records)
    return records


def materialize(out: Path = DEFAULT_OUT, *, force: bool = False) -> dict[str, object]:
    out = _validate_output(out)
    if force:
        _clear_owned_roots(out)
    out.mkdir(parents=True, exist_ok=True)
    inventory = _freeze_source_inventory(out)
    existing_ids: dict[str, list[str]] = {}
    for entry in inventory["entries"]:
        existing_ids.setdefault(entry["task_id"], []).append(entry["root"])
    collisions = sorted(case.task_id for case in CASES if case.task_id in existing_ids)
    if collisions:
        _fail("duplicate_task", ",".join(collisions))
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        if root.exists() and not force:
            _fail("generator_output_drift", f"existing root requires --force: {root}")
        _write_root(root, _task_files(case))
        roots.append(root)
    controls = _write_controls(out)
    manifest = {
        "schema_version": "pattern-ascii-candidate-manifest-v1",
        "family_id": FAMILY_ID,
        "capability_cell": "text-grid-logic/symmetric-rendering-pattern-generation-ascii-scaling",
        "requested_count": 20,
        "root_count": len(roots),
        "task_ids": [case.task_id for case in CASES],
        "lineage": {case.task_id: {"relation": "new-root", "parent": None} for case in CASES},
        "generator": GENERATOR_RELPATH,
        "generator_revision": _generator_revision(),
        "curriculum": CURRICULUM_RELPATH,
        "family_specification": FAMILY_SPEC_RELPATH,
        "selected_prompts": list(SELECTED_PROMPTS),
        "source_inventory_hash": inventory["entries_hash"],
        "controls": controls,
        "status": "generated_pending_creator_preflight",
        "strongest_local_status": "generated",
        "non_claims": ["no SFT release", "no training authorization", "no benchmark uplift"],
    }
    _write_json(out / ".state/candidate-manifest.json", manifest)
    return manifest


_CPP_KEEP = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char "
    "class compl concept const consteval constexpr constinit const_cast continue "
    "co_await co_return co_yield decltype default delete do double dynamic_cast else "
    "enum explicit export extern false float for friend goto if inline int long mutable "
    "namespace new noexcept not not_eq nullptr operator or or_eq private protected public "
    "register reinterpret_cast requires return short signed sizeof static static_assert "
    "static_cast struct switch template this thread_local throw true try typedef typeid "
    "typename union unsigned using virtual void volatile wchar_t while xor xor_eq std "
    "size_t string vector map set tuple pair min max count sort abs lround isfinite "
    "begin end front back size empty push_back insert erase assign append fill at".split()
)
_CONTRACT_KEEP = frozenset(
    "above after all allowed at atomic before below between bottom bound boundary "
    "clockwise count counted default deterministic distinct duplicate empty equal "
    "exact exactly exterior false finite first forbidden greater inclusive input "
    "invalid last left less maximum minimum nonempty none only opposite order ordered "
    "outside overflow positive preserve preserved range reject rejected required right "
    "row rows same smaller stable top true unique valid value values width without "
    "zero".split()
)


def _case_ignored(case: Case) -> set[str]:
    text = " ".join((case.task_id, case.title, case.function, case.return_type, case.types))
    return {token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)}


def _normalized_tokens(text: str, case: Case | None = None, *, cpp: bool = False) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    if cpp:
        # Includes and preprocessor directives are shared grader/scaffold material,
        # not evidence that two task-owned roles implement different behavior.
        text = re.sub(r"^\s*#.*$", " ", text, flags=re.M)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+(?:\.\d+)?\b', " literal ", text)
    ignored = _case_ignored(case) if case is not None else set()
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\|\||<<|>>|\+\+|--|[-+*/%<>=!&|?:{}()[\],.;]", text)
    tokens: list[str] = []
    for token in raw:
        lowered = token.lower()
        if lowered in ignored:
            tokens.append("id")
        elif cpp and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token) and lowered not in _CPP_KEEP:
            tokens.append("id")
        elif lowered not in {"literal"}:
            tokens.append(lowered)
        else:
            tokens.append(lowered)
    return tuple(tokens)


def _shingles(tokens: Sequence[str], width: int = 5) -> set[str]:
    if not tokens:
        return set()
    if len(tokens) < width:
        return {" ".join(tokens)}
    return {" ".join(tokens[index:index+width]) for index in range(len(tokens)-width+1)}


def _prefixed(role: str, tokens: Sequence[str], width: int = 5) -> set[str]:
    """Build role-aware shingles wide enough to suppress shared harness syntax."""
    return {f"{role}:{item}" for item in _shingles(tokens, width + 5)}


def _plain_prefixed(role: str, tokens: Sequence[str], width: int = 5) -> set[str]:
    return {f"{role}:{item}" for item in _shingles(tokens, width)}


def _role_prefixed(role: str, tokens: Sequence[str], width: int = 5) -> set[str]:
    """Use enough local context that shared C++ harness syntax cannot dominate."""
    return _prefixed(role, tokens, width)


def _instruction_contract_features(text: str, case: Case) -> set[str]:
    """Retain contract semantics while excluding domain prose and identifiers."""
    del case  # All public/task identifiers and domain labels are excluded together.
    text = re.sub(r"`[^`]*`|\b\d+(?:\.\d+)?\b", " ", text)
    words = re.findall(r"[A-Za-z]+", text.lower())
    return {f"contract-semantic:{word}" for word in words if word in _CONTRACT_KEEP}


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8", errors="ignore")


def _config(root: Path) -> dict[str, object]:
    return json.loads(_read(root, ".meta/config.json"))


def _role_paths(root: Path) -> tuple[list[str], list[str], list[str]]:
    files = _config(root).get("files")
    if not isinstance(files, dict):
        _fail("role_conflict", str(root))
    solution = files.get("solution")
    tests = files.get("test")
    examples = files.get("example")
    if not all(isinstance(value, list) and all(isinstance(item, str) for item in value) for value in (solution, tests, examples)):
        _fail("role_conflict", str(root))
    return solution, tests, examples


def _dimension_features(root: Path, case: Case) -> dict[str, set[str]]:
    solution, tests, examples = _role_paths(root)
    header = _read(root, solution[0])
    source = _read(root, examples[1])
    instructions = _read(root, ".docs/instructions.md")
    visible = _read(root, tests[0])
    hidden = _read(root, tests[1])
    negative = _read(root, ".meta/negative.cpp")
    contract_features = _instruction_contract_features(instructions, case)
    source_tokens = _normalized_tokens(source, case, cpp=True)
    mutation_tokens = tuple(
        token
        for token in source_tokens
        if token in {"if", "else", "for", "while", "return", "break", "continue", "=", "+=", "-=", "++", "--", "<", ">", "<=", ">=", "==", "!=", "&&", "||", "%", "&", "|", "<<", ">>"}
    )
    return {
        "public_api": (
            _role_prefixed("api", _normalized_tokens(header, case, cpp=True), 4)
            | contract_features
        ),
        "owned_state_or_algorithm": (
            _role_prefixed("owned", source_tokens, 6)
            | contract_features
        ),
        "mutation_selection_rules": (
            _role_prefixed("mutation", mutation_tokens, 4)
            | contract_features
        ),
        "invalid_boundary_behavior": (
            _role_prefixed("hidden", _normalized_tokens(hidden, case, cpp=True), 5)
            | contract_features
        ),
        "reference_control_flow": (
            _role_prefixed("flow", mutation_tokens, 6)
            | contract_features
        ),
        "deterministic_oracle": (
            _role_prefixed("visible", _normalized_tokens(visible, case, cpp=True), 5)
            | _role_prefixed("hidden", _normalized_tokens(hidden, case, cpp=True), 5)
            | contract_features
        ),
        "topic_specific_negative_fixture": (
            _role_prefixed("negative", _normalized_tokens(negative, case, cpp=True), 6)
            | contract_features
        ),
    }


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def _pair_decisions(left: Path, left_case: Case, right: Path, right_case: Case) -> dict[str, dict[str, object]]:
    left_features = _dimension_features(left, left_case)
    right_features = _dimension_features(right, right_case)
    decisions: dict[str, dict[str, object]] = {}
    for dimension in HARD_DIMENSIONS:
        score = _overlap(left_features[dimension], right_features[dimension])
        symmetric_difference = len(left_features[dimension] ^ right_features[dimension])
        decisions[dimension] = {
            "pass": score < HARD_THRESHOLDS[dimension] and symmetric_difference >= 4,
            "overlap": round(score, 6),
            "symmetric_difference": symmetric_difference,
            "threshold": HARD_THRESHOLDS[dimension],
            "left_feature_count": len(left_features[dimension]),
            "right_feature_count": len(right_features[dimension]),
        }
    return decisions


def _family_screen(out: Path) -> dict[str, object]:
    pairs: list[dict[str, object]] = []
    for left_case, right_case in combinations(CASES, 2):
        decisions = _pair_decisions(out / left_case.task_id, left_case, out / right_case.task_id, right_case)
        if not all(item["pass"] for item in decisions.values()):
            failed = [dimension for dimension, item in decisions.items() if not item["pass"]]
            _fail("duplicate_family", f"{left_case.task_id}:{right_case.task_id}:{','.join(failed)}")
        pairs.append({"left": left_case.task_id, "right": right_case.task_id, "decisions": decisions})
    if len(pairs) != 190:
        _fail("family_pair_count_mismatch", str(len(pairs)))
    controls: dict[str, object] = {}
    control_manifest = json.loads(_read(out, ".state/adversarial-controls.json"))
    for kind in CONTROL_KINDS:
        record = control_manifest[kind]
        base = next(case for case in CASES if case.task_id == record["base_task_id"])
        root = out / record["root"]
        decisions = _pair_decisions(out / base.task_id, base, root, base)
        production_rejected = not all(item["pass"] for item in decisions.values())
        if not production_rejected:
            _fail("adversarial_clone_accepted", kind)
        controls[kind] = {
            **record,
            "decisions": decisions,
            "production_rejected": production_rejected,
        }
    screen = {
        "schema_version": "pattern-ascii-family-screen-v1",
        "status": "pass",
        "normalizer": NORMALIZER,
        "root_count": len(CASES),
        "pair_count": len(pairs),
        "expected_pair_count": 190,
        "dimensions": list(HARD_DIMENSIONS),
        "thresholds": HARD_THRESHOLDS,
        "pairs": pairs,
        "controls": controls,
    }
    _write_json(out / ".state/family-screen.json", screen)
    return screen


def _content_features(root: Path, case: Case | None = None) -> set[str]:
    return _plain_prefixed("semantic", _normalized_tokens(_semantic_text(root), case), 8)


def _holdout_screen(out: Path) -> dict[str, object]:
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_screen_not_completed", str(HOLDOUT_ROOT))
    found = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()}
    if found != OFFICIAL_HOLDOUTS:
        _fail("benchmark_inventory_mismatch", f"expected={len(OFFICIAL_HOLDOUTS)} found={len(found)}")
    holdout_features = {slug: _content_features(HOLDOUT_ROOT / slug) for slug in sorted(OFFICIAL_HOLDOUTS)}
    comparisons: list[dict[str, object]] = []
    for case in CASES:
        if case.task_id in OFFICIAL_HOLDOUTS:
            _fail("benchmark_id_overlap", case.task_id)
        candidate = _content_features(out / case.task_id, case)
        for slug, features in holdout_features.items():
            score = _overlap(candidate, features)
            if score >= 0.90:
                _fail("benchmark_content_overlap", f"{case.task_id}:{slug}:{score:.6f}")
            comparisons.append({"task_id": case.task_id, "holdout": slug, "overlap": round(score, 6)})
    return {
        "status": "pass",
        "holdout_count": len(OFFICIAL_HOLDOUTS),
        "comparison_count": len(comparisons),
        "inventory_hash": _sha256("\n".join(sorted(found)).encode()),
        "threshold": 0.90,
        "comparisons": comparisons,
    }


def _cross_tree_screen(out: Path) -> dict[str, object]:
    inventory = json.loads(_read(out, ".state/source-inventory.json"))
    existing_by_id: dict[str, list[dict[str, str]]] = {}
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    api_hashes: set[str] = set()
    test_hashes: set[str] = set()
    contract_hashes: set[str] = set()
    for entry in inventory["entries"]:
        existing_by_id.setdefault(entry["task_id"], []).append(entry)
        prompt_hashes.add(entry["prompt_hash"])
        reference_hashes.add(entry["reference_hash"])
        api_hashes.add(entry["api_hash"])
        test_hashes.add(entry["tests_hash"])
        contract_hashes.add(entry["contract_hash"])
    old_roots = [REPO_ROOT / entry["root"] for entry in inventory["entries"]]
    old_features = [(root, _content_features(root)) for root in old_roots]
    records: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        if case.task_id in existing_by_id:
            _fail("duplicate_task", case.task_id)
        prompt_hash = _sha256((
            _read(root, ".docs/introduction.md") + "\n" + _read(root, ".docs/instructions.md")
        ).encode())
        reference_hash = _reference_content_hash(root)
        api_hash = _file_hash(root / ".meta/example.h")
        tests_hash = _sha256((
            _read(root, "task_visible_test.cpp") + _read(root, ".meta/task_hidden_test.cpp")
        ).encode())
        contract_hash = _file_hash(root / ".docs/instructions.md")
        if prompt_hash in prompt_hashes:
            _fail("duplicate_prompt", case.task_id)
        if reference_hash in reference_hashes:
            _fail("duplicate_reference", case.task_id)
        if api_hash in api_hashes and tests_hash in test_hashes:
            _fail("duplicate_family", f"api-test:{case.task_id}")
        if contract_hash in contract_hashes:
            _fail("semantic_lineage_overlap", f"contract:{case.task_id}")
        candidate = _content_features(root, case)
        maximum = (0.0, "")
        for old_root, features in old_features:
            score = _overlap(candidate, features)
            if score > maximum[0]:
                maximum = (score, old_root.relative_to(REPO_ROOT).as_posix())
            if score >= 0.92:
                _fail("semantic_lineage_overlap", f"{case.task_id}:{old_root}:{score:.6f}")
        records.append({"task_id": case.task_id, "max_overlap": round(maximum[0], 6), "nearest_root": maximum[1]})
    existing_inodes = {
        (path.stat().st_dev, path.stat().st_ino)
        for root in old_roots
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    for case in CASES:
        for path in (out / case.task_id).rglob("*"):
            if path.is_symlink():
                _fail("unsafe_path", f"candidate symlink: {path}")
            if path.is_file() and (path.stat().st_dev, path.stat().st_ino) in existing_inodes:
                _fail("hardlink_lineage_conflict", str(path))
    return {
        "status": "pass",
        "threshold": 0.92,
        "screened_counts": {
            "legacy": inventory["legacy_count"],
            "reverify": inventory["reverify_count"],
            "expansion": inventory["expansion_count"],
        },
        "records": records,
    }


def _prompt_role_check(root: Path, case: Case) -> dict[str, object]:
    solution, tests, examples = _role_paths(root)
    expected_solution = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
    if solution != expected_solution or tests != ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"] or examples != [".meta/example.h", ".meta/example.cpp"]:
        _fail("role_conflict", case.task_id)
    all_paths = solution + tests + examples
    if len(all_paths) != len(set(all_paths)) or any(Path(path).is_absolute() or ".." in Path(path).parts for path in all_paths):
        _fail("unsafe_path", case.task_id)
    if any(not (root / path).is_file() for path in all_paths):
        _fail("missing_role_file", case.task_id)
    task = load_task(root)
    prompt = build_prompt(task)
    private_markers = (".meta/", "CMakeLists.txt", "task_visible_test.cpp", "negative.cpp", "provenance.json")
    if any(marker in prompt for marker in private_markers):
        _fail("prompt_private_leak", case.task_id)
    response = "\n\n".join(
        f"{target}\n```cpp\n{_read(root, example).rstrip()}\n```"
        for target, example in zip(solution, examples, strict=True)
    )
    try:
        parsed = parse_whole_file_blocks(response)
    except WholeFormatError as error:
        _fail("whole_format_failed", f"{case.task_id}:{error}")
    if list(parsed) != solution or any(parsed[target] != _read(root, example) for target, example in zip(solution, examples, strict=True)):
        _fail("target_reference_mismatch", case.task_id)
    provenance = json.loads(_read(root, ".meta/provenance.json"))
    if provenance.get("family_id") != FAMILY_ID or provenance.get("lineage") != "new-root":
        _fail("lineage_conflict", case.task_id)
    return {
        "task_id": case.task_id,
        "prompt_hash": _sha256(prompt.encode()),
        "starter_hash": _sha256(b"".join((root / path).read_bytes() for path in solution)),
        "reference_hash": _reference_hash(root),
        "prompt_boundary": "pass",
        "whole_file_boundary": "pass",
    }


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    out = _validate_output(out)
    if not CURRICULUM.is_file() or not FAMILY_SPEC.is_file():
        _fail("source_contract_missing", f"{CURRICULUM};{FAMILY_SPEC}")
    roots = _real_task_roots(out)
    if [root.name for root in roots] != sorted(case.task_id for case in CASES):
        _fail("candidate_inventory_mismatch", f"expected=20 found={len(roots)}")
    prompt_records = [_prompt_role_check(out / case.task_id, case) for case in CASES]
    prompt_hashes = [record["prompt_hash"] for record in prompt_records]
    references = [record["reference_hash"] for record in prompt_records]
    if len(set(prompt_hashes)) != 20:
        _fail("duplicate_prompt", "within family")
    if len(set(references)) != 20:
        _fail("duplicate_reference", "within family")
    family = _family_screen(out)
    holdouts = _holdout_screen(out)
    cross_tree = _cross_tree_screen(out)
    result = {
        "schema_version": "pattern-ascii-core-verification-v1",
        "status": "pass",
        "root_count": 20,
        "pair_count": family["pair_count"],
        "dimensions": list(HARD_DIMENSIONS),
        "prompt_records": prompt_records,
        "family_screen_hash": _file_hash(out / ".state/family-screen.json"),
        "holdout_screen": holdouts,
        "cross_tree_screen": cross_tree,
        "generator_revision": _generator_revision(),
        "tree_hash": _tree_hash(out),
    }
    _write_json(out / ".state/core-verification.json", result)
    return result


def _verification_roots(out: Path) -> dict[str, Path]:
    roots = {case.task_id: out / case.task_id for case in CASES}
    for kind in CONTROL_KINDS:
        roots[f"control--{kind}"] = out / ".state/adversarial-controls" / kind
    return roots


def _test_count(build: Path) -> int:
    proc = subprocess.run(
        ["ctest", "--test-dir", str(build), "-N"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"Total Tests:\s*(\d+)", proc.stdout)
    if match is None:
        _fail("test_discovery_failed", str(build))
    return int(match.group(1))


def _verify_one_host(root: Path, build: Path, *, sanitizer: bool) -> dict[str, object]:
    flags = "-fsanitize=address,undefined -fno-omit-frame-pointer" if sanitizer else ""
    command = [
        "cmake", "-S", str(root), "-B", str(build), "-G", "Unix Makefiles",
        f"-DTASK_SOURCE={root / '.meta/example.cpp'}",
    ]
    if flags:
        command.append(f"-DCMAKE_CXX_FLAGS={flags}")
    subprocess.run(command, check=True, capture_output=True, text=True)
    subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], check=True, capture_output=True, text=True)
    count = _test_count(build)
    if count != 3:
        _fail("test_discovery_failed", f"{root}:{count}")
    subprocess.run(["ctest", "--test-dir", str(build), "--output-on-failure"], check=True, capture_output=True, text=True)
    negative = subprocess.run([str(build / "task_negative")], check=False, capture_output=True, text=True)
    if negative.returncode != 1 or negative.stdout or negative.stderr:
        _fail("negative_fixture_not_rejected", str(root))
    return {"test_count": count, "negative_exit": negative.returncode}


def verify_host(out: Path = DEFAULT_OUT) -> dict[str, object]:
    verify_core(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("host_prerequisite_missing", "cmake and c++ are required for iteration")
    records: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="pattern-ascii-host-") as temp:
        temp_root = Path(temp)
        for key, root in _verification_roots(out).items():
            normal = _verify_one_host(root, temp_root / f"{key}-normal", sanitizer=False)
            sanitized = _verify_one_host(root, temp_root / f"{key}-sanitized", sanitizer=True)
            if normal["test_count"] != sanitized["test_count"]:
                _fail("sanitizer_test_count_mismatch", key)
            records[key] = {"normal": normal, "asan_ubsan": sanitized}
    receipt = {
        "schema_version": "pattern-ascii-host-iteration-v1",
        "status": "pass",
        "evidence_class": "host_iteration",
        "root_count": 20,
        "control_count": 3,
        "records": records,
        "generator_revision": _generator_revision(),
        "tree_hash": _tree_hash(out),
    }
    _write_json(out / ".state/host-iteration.json", receipt)
    return receipt


def _archive(out: Path, target: Path) -> tuple[str, dict[str, str]]:
    roots = _verification_roots(out)
    hashes: dict[str, str] = {}
    with tarfile.open(target, "w") as archive:
        for key, root in roots.items():
            hashes[key] = _tree_hash(root)
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                relative = path.relative_to(root).as_posix()
                info = archive.gettarinfo(str(path), arcname=f"family/{key}/{relative}")
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
    return _sha256(target.read_bytes()), hashes


def _accept_docker_receipt(out: Path, receipt: dict[str, object]) -> dict[str, object]:
    if (
        receipt.get("schema_version") != "pattern-ascii-docker-sanity-v1"
        or receipt.get("status") != "pass"
        or receipt.get("network_policy") != "none"
        or receipt.get("image") != SANITY_IMAGE
        or receipt.get("generator_revision") != _generator_revision()
    ):
        _fail("docker_result_identity_mismatch", "receipt header")
    records = receipt.get("records")
    expected = _verification_roots(out)
    if not isinstance(records, dict) or set(records) != set(expected):
        _fail("docker_sanity_incomplete", "root/control inventory")
    for key, root in expected.items():
        record = records[key]
        if not isinstance(record, dict):
            _fail("docker_sanity_incomplete", key)
        live_hash = _tree_hash(root)
        if record.get("tree_hash") != live_hash or record.get("mounted_tree_hash") != live_hash:
            _fail("grader_mount_hash_mismatch", key)
        if record.get("normal_tests") != 3 or record.get("asan_ubsan_tests") != 3:
            _fail("sanitizer_test_count_mismatch", key)
        if record.get("negative_normal") != "semantic_rejection_exit_1" or record.get("negative_asan_ubsan") != "semantic_rejection_exit_1":
            _fail("negative_fixture_not_rejected", key)
    core = verify_core(out)
    if receipt.get("family_screen_hash") != core["family_screen_hash"]:
        _fail("docker_result_identity_mismatch", "family screen")
    _write_json(out / ".state/docker-sanity.json", receipt)
    return receipt


def docker_sanity(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    out = _validate_output(out)
    core = verify_core(out)
    if image != SANITY_IMAGE:
        _fail("docker_image_identity_mismatch", image)
    with tempfile.TemporaryDirectory(prefix="pattern-ascii-docker-") as temp:
        archive = Path(temp) / "family.tar"
        archive_hash, root_hashes = _archive(out, archive)
        image_id = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        script = r'''set -eu
mkdir -p /tmp/pattern-ascii
tar -xf /input/family.tar -C /tmp/pattern-ascii
compiler=$(command -v c++)
echo "W8TOOL compiler_path $compiler"
echo "W8TOOL compiler_hash sha256:$(sha256sum "$compiler" | sed 's/ .*//')"
echo "W8TOOL compiler_version $(c++ --version | head -1)"
echo "W8TOOL cmake_version $(cmake --version | head -1)"
for root in /tmp/pattern-ascii/family/*; do
  key=${root##*/}
  mounted_hash=$(python3 -c 'import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1]);d=hashlib.sha256()
for p in sorted(x for x in r.rglob("*") if x.is_file()):
 q=p.relative_to(r).as_posix().encode();b=p.read_bytes();d.update(len(q).to_bytes(8,"big"));d.update(q);d.update(len(b).to_bytes(8,"big"));d.update(b)
print("sha256:"+d.hexdigest())' "$root")
  echo "W8HASH $key $mounted_hash"
  for mode in normal asan_ubsan; do
    flags=
    if [ "$mode" = asan_ubsan ]; then flags='-fsanitize=address,undefined -fno-omit-frame-pointer'; fi
    build="/tmp/build-$key-$mode"
    cmake -S "$root" -B "$build" -G 'Unix Makefiles' -DTASK_SOURCE="$root/.meta/example.cpp" -DCMAKE_CXX_FLAGS="$flags" >/dev/null
    cmake --build "$build" --parallel 2 >/dev/null
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: *//p')
    test "$count" = 3
    ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure
    set +e
    negative_output=$(ASAN_OPTIONS=detect_leaks=0 "$build/task_negative" 2>&1)
    negative_status=$?
    set -e
    test "$negative_status" = 1
    test -z "$negative_output"
    echo "W8NEG $key $mode semantic_rejection_exit_1"
    echo "W8COUNT $key $mode $count"
  done
done'''
        proc = subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none",
                "-v", f"{archive}:/input/family.tar:ro",
                image, "bash", "-lc", script,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            _fail("docker_sanity_failed", (proc.stdout + "\n" + proc.stderr)[-16000:])
    counts: dict[str, dict[str, int]] = {}
    for key, mode, count in re.findall(r"^W8COUNT (\S+) (\S+) (\d+)$", proc.stdout, re.M):
        counts.setdefault(key, {})[mode] = int(count)
    mounted = dict(re.findall(r"^W8HASH (\S+) (sha256:[0-9a-f]{64})$", proc.stdout, re.M))
    negatives = {
        (key, mode): result
        for key, mode, result in re.findall(r"^W8NEG (\S+) (\S+) (\S+)$", proc.stdout, re.M)
    }
    expected = _verification_roots(out)
    if set(counts) != set(expected):
        _fail("docker_sanity_incomplete", f"expected={len(expected)} found={len(counts)}")
    records: dict[str, object] = {}
    for key, root in expected.items():
        if counts[key] != {"normal": 3, "asan_ubsan": 3}:
            _fail("sanitizer_test_count_mismatch", key)
        if mounted.get(key) != root_hashes[key]:
            _fail("grader_mount_hash_mismatch", key)
        if any(negatives.get((key, mode)) != "semantic_rejection_exit_1" for mode in ("normal", "asan_ubsan")):
            _fail("negative_fixture_not_rejected", key)
        records[key] = {
            "tree_hash": root_hashes[key],
            "mounted_tree_hash": mounted[key],
            "normal_tests": 3,
            "asan_ubsan_tests": 3,
            "negative_normal": negatives[(key, "normal")],
            "negative_asan_ubsan": negatives[(key, "asan_ubsan")],
            "reference_hash": _reference_hash(root),
        }
    receipt = {
        "schema_version": "pattern-ascii-docker-sanity-v1",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network_policy": "none",
        "image": image,
        "image_id": image_id,
        "archive_hash": archive_hash,
        "generator_revision": _generator_revision(),
        "family_screen_hash": core["family_screen_hash"],
        "compiler_and_cmake": dict(re.findall(r"^W8TOOL (\S+) (.+)$", proc.stdout, re.M)),
        "commands": [
            "explicit Unix Makefiles normal configure/build/ctest",
            "direct normal negative execution requiring exit 1 and empty diagnostics",
            "fresh ASan/UBSan configure/build/ctest",
            "direct ASan/UBSan negative execution requiring exit 1 and empty diagnostics",
        ],
        "root_count": 20,
        "control_count": 3,
        "records": records,
    }
    return _accept_docker_receipt(out, receipt)


def _audit_subject(out: Path) -> dict[str, object]:
    out = out.resolve()
    remedy_spec = REPO_ROOT / REMEDY_SPEC_RELPATH
    remedy_records = [out / ".state/remedy" / f"{case.task_id}.json" for case in CASES]
    paths = [
        out / ".state/candidate-manifest.json",
        out / ".state/source-inventory.json",
        out / ".state/core-verification.json",
        out / ".state/family-screen.json",
        out / ".state/docker-sanity.json",
        CURRICULUM,
        FAMILY_SPEC,
        Path(__file__),
        Path(__file__).with_name("moonlight_pattern_ascii_processing_cases.py"),
        remedy_spec,
        *remedy_records,
    ]
    stable_paths = {
        CURRICULUM: CURRICULUM_RELPATH,
        FAMILY_SPEC: FAMILY_SPEC_RELPATH,
        Path(__file__): GENERATOR_RELPATH,
        Path(__file__).with_name("moonlight_pattern_ascii_processing_cases.py"): CASES_RELPATH,
        remedy_spec: REMEDY_SPEC_RELPATH,
    }
    files = {
        (stable_paths[path] if path in stable_paths else path.relative_to(REPO_ROOT).as_posix()): _file_hash(path)
        for path in paths
    }
    roots = {
        case.task_id: {
            "tree_hash": _tree_hash(out / case.task_id),
            "reference_hash": _reference_hash(out / case.task_id),
        }
        for case in CASES
    }
    subject_without_hash = {
        "schema_version": "pattern-ascii-audit-subject-v1",
        "family_id": FAMILY_ID,
        "root_count": 20,
        "files": files,
        "roots": roots,
        "requested_status_ceiling": "local_family_verified",
    }
    subject_hash = _sha256(json.dumps(subject_without_hash, sort_keys=True, separators=(",", ":")).encode())
    return {**subject_without_hash, "audit_subject_hash": subject_hash}


def _append_cycle(out: Path, state: str, *, audit: dict[str, object] | None = None) -> dict[str, object]:
    cycles = out / ".state/cycles"
    cycles.mkdir(parents=True, exist_ok=True)
    existing = sorted(cycles.glob("cycle-*.json"))
    number = len(existing) + 1
    subject = _audit_subject(out)
    cycle = {
        "schema_version": "aider-task-creator-cycle-v1",
        "cycle": number,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "family_id": FAMILY_ID,
        "candidate_manifest": ".state/candidate-manifest.json",
        "curriculum_hash": _file_hash(CURRICULUM),
        "generator_hash": _generator_revision(),
        "focused_test": "tests/test_moonlight_pattern_ascii_processing_aider_tasks.py",
        "generated_tree_hash": _tree_hash(out),
        "grader_policy_hash": _file_hash(out / ".state/docker-sanity.json"),
        "audit_subject_hash": subject["audit_subject_hash"],
        "retained_ids": [case.task_id for case in CASES],
        "replaced_ids": [],
        "rejected_ids": [],
        "review_ids": [],
        "blocked_ids": [],
        "invalidated_evidence": [],
        "audit": audit,
        "terminal_status": "pending_independent_audit" if state == "creator_preflight" else state,
    }
    _write_json(cycles / f"cycle-{number:02d}-{state}.json", cycle)
    return cycle


def creator_preflight(out: Path = DEFAULT_OUT) -> dict[str, object]:
    core = verify_core(out)
    receipt_path = out / ".state/docker-sanity.json"
    if receipt_path.is_file():
        docker = _accept_docker_receipt(out, json.loads(receipt_path.read_text(encoding="utf-8")))
    else:
        docker = docker_sanity(out)
    manifest_path = out / ".state/candidate-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "status": "creator_preflight_passed_pending_independent_audit",
            "strongest_local_status": "creator_preflight_passed_pending_independent_audit",
            "docker_receipt": ".state/docker-sanity.json",
            "core_receipt": ".state/core-verification.json",
        }
    )
    _write_json(manifest_path, manifest)
    subject = _audit_subject(out)
    _write_json(out / ".state/audit-subject.json", subject)
    task_receipts = out / ".state/task-receipts"
    for case in CASES:
        root = out / case.task_id
        record = docker["records"][case.task_id]
        _write_json(
            task_receipts / f"{case.task_id}.json",
            {
                "schema_version": "pattern-ascii-task-receipt-v1",
                "task_id": case.task_id,
                "lineage": "new-root",
                "disposition": "verified-candidate-pending-independent-audit",
                "tree_hash": _tree_hash(root),
                "prompt_hash": next(item["prompt_hash"] for item in core["prompt_records"] if item["task_id"] == case.task_id),
                "starter_hash": next(item["starter_hash"] for item in core["prompt_records"] if item["task_id"] == case.task_id),
                "reference_hash": _reference_hash(root),
                "tests_hash": _sha256((_read(root, "task_visible_test.cpp") + _read(root, ".meta/task_hidden_test.cpp")).encode()),
                "generator_revision": _generator_revision(),
                "image": docker["image"],
                "image_id": docker["image_id"],
                "compiler_and_cmake": docker["compiler_and_cmake"],
                "network_policy": "none",
                "normal_tests": record["normal_tests"],
                "asan_ubsan_tests": record["asan_ubsan_tests"],
                "negative_outcomes": [record["negative_normal"], record["negative_asan_ubsan"]],
                "family_screen_hash": core["family_screen_hash"],
                "audit_subject_hash": subject["audit_subject_hash"],
            },
        )
    cycle = _append_cycle(out, "creator_preflight")
    result = {
        "status": "pass",
        "root_count": 20,
        "creator_preflight": "pass",
        "audit_subject_hash": subject["audit_subject_hash"],
        "cycle": cycle["cycle"],
        "next_state": "independent_audit",
    }
    _write_json(out / ".state/creator-preflight.json", result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--creator-preflight", action="store_true")
    args = parser.parse_args(argv)
    if args.force or not args.out.exists():
        materialize(args.out, force=args.force)
    if args.verify_core:
        print(json.dumps(verify_core(args.out), sort_keys=True))
    if args.verify_host:
        print(json.dumps(verify_host(args.out), sort_keys=True))
    if args.docker_sanity:
        print(json.dumps(docker_sanity(args.out), sort_keys=True))
    if args.creator_preflight:
        print(json.dumps(creator_preflight(args.out), sort_keys=True))
    if not any((args.verify_core, args.verify_host, args.docker_sanity, args.creator_preflight)):
        print(json.dumps(materialize(args.out, force=args.force), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
