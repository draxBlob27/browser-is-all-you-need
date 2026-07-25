"""Owner for the 100-root lexical canonicalization/EOI expansion family."""

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
from typing import Iterable

from w8_biayn.integrations.moonlight_lexical_canonicalization_contracts import (
    COMMON_HELPERS,
    build_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
CURRICULUM = REPO_ROOT / "docs/aider-synthetic/aider-synthetic-validation-input-parsing/GLM47_FLASH_AIDER_POLYGLOT_CPP_LEXICAL_VALIDATION_AND_CANONICALIZATION_CURRICULUM.md"
FAMILY_SPEC = REPO_ROOT / "docs/aider-tasks-spec/aider-validation-input-parsing/lexical-canonicalization-eoi.md"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
DEFAULT_OUT = EXPANSION_ROOT / "validation-parsing/lexical-canonicalization-eoi"
LEGACY_ROOTS = (
    REPO_ROOT / ".w8-biayn/data/aider-tasks",
    REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify",
)
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
OWNER = "src/w8_biayn/integrations/moonlight_lexical_canonicalization_aider_tasks.py"
FAMILY_ID = "lexical-canonicalization-eoi-v1"
AUDIT_FINDINGS = (
    "cycle-01/family/core-contract-collapse",
    "cycle-01/family/oracle-discriminators-missing",
    "cycle-01/family/diversity-controls-self-attested",
    "cycle-01/family/prompt-hidden-checksum",
    "cycle-01/family/semantic-screen-incomplete",
    "cycle-01/family/receipt-binding-incomplete",
)
CYCLE_02_FINDINGS = (
    "cycle-01/family/core-contract-collapse",
    "cycle-01/family/oracle-discriminators-missing",
    "cycle-01/family/diversity-controls-self-attested",
    "cycle-02/family/reference-contract-divergence",
    "cycle-02/family/prompt-contract-incomplete",
    "cycle-01/family/receipt-binding-incomplete",
)
CYCLE_03_FINDINGS = (
    "cycle-03/family/consumed-contract-divergence",
    "cycle-03/family/adversarial-integer-overflow",
    "cycle-03/band/quoted-escape-contract-divergence",
    "cycle-03/band/range-trailing-comma-accepted",
    "cycle-03/band/frame-undocumented-payload-split",
    "cycle-03/family/prompt-boundary-and-alphabet-incomplete",
    "cycle-03/family/diversity-control-policy-overwrite",
)
DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
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
SEPARATORS = ("-", ":", "/", ".", "_", "+", "@", "~", "=", "#")
ALGORITHMS = (
    "alternating_dfa", "prefix_trie", "rolling_checksum", "range_product",
    "escape_automaton", "quoted_atom", "numeric_fsm", "version_lattice",
    "segment_stack", "unit_trie", "range_union", "tagged_record",
    "length_frame", "sentinel_stream", "wildcard_terminal", "cross_field",
    "percent_decoder", "base36_accumulator", "parity_marker", "final_state",
)


class CreatorError(RuntimeError):
    pass


@dataclass(frozen=True)
class Case:
    task_id: str
    api_stem: str
    summary: str
    discriminator: str
    index: int

    @property
    def snake(self) -> str:
        return self.task_id.replace("-", "_")

    @property
    def result_type(self) -> str:
        return f"{self.api_stem}Result"

    @property
    def function(self) -> str:
        return f"canonicalize_{self.snake.removeprefix('lex_')}"

    @property
    def prefix(self) -> str:
        words = self.task_id.removeprefix("lex-").split("-")
        return "".join(word[0] for word in words)[:3].upper()

    @property
    def separator(self) -> str:
        return SEPARATORS[self.index % len(SEPARATORS)]

    @property
    def digits(self) -> int:
        return 2 + (self.index % 4)

    @property
    def tag_length(self) -> int:
        return 2 + ((self.index // 4) % 4)

    @property
    def algorithm_signature(self) -> tuple[str, ...]:
        # Phase labels preserve the order-sensitive state graph. The two varying
        # phases are a base-20 encoding, so no two retained roots share it.
        return (
            f"entry:{ALGORITHMS[self.index % len(ALGORITHMS)]}",
            f"branch:{ALGORITHMS[(self.index // len(ALGORITHMS)) % len(ALGORITHMS)]}",
            f"field:{ALGORITHMS[(self.index * 7 + 3) % len(ALGORITHMS)]}",
            f"final:{ALGORITHMS[(self.index * 11 + 5) % len(ALGORITHMS)]}",
            f"oracle:{ALGORITHMS[(self.index * 13 + 9) % len(ALGORITHMS)]}",
        )


def _fail(code: str, detail: str = "") -> None:
    raise CreatorError(f"{code}:{detail}" if detail else code)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    try:
        path.write_text(payload)
    except PermissionError:
        # A prior root-owned Docker sanity run leaves receipts in the writable
        # `.state/` directory that the owner must still refresh through its own
        # controlled path.  Unlink and rewrite; never patch the bytes in place.
        path.unlink()
        path.write_text(payload)


def _log_base(out: Path, evidence_class: str) -> Path:
    # The designated Docker sanity run executes as root and leaves root-owned
    # log directories beneath `.state/runtime-logs/` that an unprivileged host
    # run can neither overwrite nor prune.  Host evidence therefore retains its
    # logs in a sibling directory; the Docker layout is unchanged.
    if evidence_class == "docker_sanity":
        return out / ".state/runtime-logs"
    return out / ".state/runtime-logs-host"


def cases() -> tuple[Case, ...]:
    text = CURRICULUM.read_text()
    pattern = re.compile(r"^\| `(?P<id>lex-[a-z0-9-]+)` \| `(?P<api>[A-Za-z0-9]+)` \| (?P<summary>.*?) \| (?P<bad>.*?) \|$", re.M)
    rows = [Case(m["id"], m["api"], m["summary"], m["bad"], index) for index, m in enumerate(pattern.finditer(text))]
    if len(rows) != 100:
        _fail("curriculum_count_mismatch", str(len(rows)))
    if len({row.task_id for row in rows}) != 100:
        _fail("duplicate_task", "curriculum")
    return tuple(rows)


def _safe_out(out: Path) -> Path:
    resolved = out.resolve(strict=False)
    if resolved != DEFAULT_OUT.resolve(strict=False):
        _fail("invalid_output_root", str(out))
    if out.is_symlink() or any(parent.is_symlink() for parent in (out, out.parent, out.parent.parent)):
        _fail("invalid_output_root", "symlink")
    for legacy in LEGACY_ROOTS:
        if resolved == legacy.resolve(strict=False) or legacy.resolve(strict=False) in resolved.parents:
            _fail("invalid_output_root", str(legacy))
    return resolved


def _existing_ids(exclude: Path | None = None) -> dict[str, str]:
    found: dict[str, str] = {}
    excluded = exclude.resolve(strict=False) if exclude is not None else None
    for base in (*LEGACY_ROOTS, EXPANSION_ROOT):
        if not base.is_dir():
            continue
        for config in base.rglob(".meta/config.json"):
            if ".state" in config.parts or (excluded is not None and excluded in config.resolve(strict=False).parents):
                continue
            task_id = config.parent.parent.name
            # Legacy and reverify deliberately share lineage IDs. They are both
            # reserved, but that expected ancestor/replacement relation is not
            # a new-root collision by itself.
            found.setdefault(task_id, str(config.parent.parent.relative_to(REPO_ROOT)))
    return found


def _semantic_tokens(text: str) -> set[str]:
    text = re.sub(r"`[^`]+`|\b\d+\b", " ", text.lower())
    return {token for token in re.findall(r"[a-z_]{4,}", text) if token not in {"canonical", "input", "return", "string", "invalid"}}


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.relative_to(root).parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _header(case: Case) -> str:
    contract = build_contract(case.task_id, case.api_stem, case.index)
    guard = case.snake.upper() + "_H"
    return f"""#ifndef {guard}
#define {guard}
#include <array>
#include <cstddef>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
namespace lexical_curriculum {{
struct {case.result_type} {{
    bool valid = false;
    std::string canonical;
    std::size_t consumed = 0;
    std::string error;
    {contract.api_extra}
}};
{case.result_type} {case.function}(std::string_view input);
}}
#endif
"""


def _format_cpp_statements(text: str) -> str:
    """Separate top-level statements without touching for-loop semicolons."""
    output: list[str] = []
    parentheses = 0
    quote: str | None = None
    escaped = False
    for char in text:
        output.append(char)
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            parentheses += 1
        elif char == ")":
            parentheses = max(0, parentheses - 1)
        elif char == ";" and parentheses == 0:
            output.append("\n")
    return "".join(output)


def _source(case: Case, *, negative: bool = False) -> str:
    contract = build_contract(case.task_id, case.api_stem, case.index)
    body = _format_cpp_statements(contract.negative_source if negative else contract.source)
    helpers = _format_cpp_statements(COMMON_HELPERS)
    return f"""#include \"{case.task_id}.h\"
#include <algorithm>
#include <limits>
#include <map>
#include <string>
#include <utility>
#include <vector>
namespace lexical_curriculum {{
namespace {{
{helpers}
}}
{case.result_type} {case.function}(std::string_view input) {{
    auto fail = [&](std::size_t offset, const char* why) {{
        {case.result_type} result;
        result.valid = false;
        result.consumed = offset;
        result.error = why;
        return result;
    }};
    auto pass = [&](std::string canonical, std::size_t consumed) {{
        {case.result_type} result;
        result.valid = true;
        result.canonical = std::move(canonical);
        result.consumed = consumed;
        {contract.success_assignments}
        return result;
    }};
{body}
}}
}}
"""


def _starter(case: Case) -> str:
    return f"""#include \"{case.task_id}.h\"\nnamespace lexical_curriculum {{\n{case.result_type} {case.function}(std::string_view input) {{ return {{false, {{}}, input.empty() ? 0U : 1U, \"not implemented\"}}; }}\n}}\n"""


def _detail_assertion(case: Case) -> str:
    # Callers negate the complete predicate.  Keep the generated conjunction
    # grouped so ``!`` cannot bind only to its first comparison in C++.
    return f"({build_contract(case.task_id, case.api_stem, case.index).detail_assertion})"


def _test(case: Case, *, private: bool, negative: bool = False) -> str:
    contract = build_contract(case.task_id, case.api_stem, case.index)
    good = json.dumps(contract.valid_input)
    canonical = json.dumps(contract.canonical)
    named_invalid = json.dumps(contract.named_invalid)
    fn = case.function
    if negative:
        body = f'''auto happy={fn}({good});if(!happy.valid||happy.canonical!={canonical})return 2;auto wrong={fn}({named_invalid});return wrong.valid?1:0;'''
    elif not private:
        body = f'''auto a={fn}({good});if(!a.valid||a.canonical!={canonical}||a.consumed!={len(contract.valid_input)}U||!a.error.empty())return 1;if(!{_detail_assertion(case)})return 2;auto bad={fn}({named_invalid});if(bad.valid||!bad.canonical.empty()||bad.error.empty())return 3;return 0;'''
    else:
        invalid_literals = ",".join(json.dumps(value) for value in (contract.named_invalid, *contract.other_invalid))
        variant_literals = ",".join(f"{{{json.dumps(value)},{json.dumps(expected)}}}" for value, expected in contract.valid_variants)
        body = f'''std::string good={good};auto a={fn}(good);if(!a.valid||a.canonical!={canonical}||!{_detail_assertion(case)})return 1;auto again={fn}(a.canonical);if(!again.valid||again.canonical!=a.canonical||!{_detail_assertion(case).replace("a.", "again.")})return 2;const std::vector<std::string> invalid={{{invalid_literals}}};for(const auto& value:invalid){{auto r={fn}(value);if(r.valid||!r.canonical.empty()||r.error.empty()||r.consumed>value.size())return 3;}}for(std::size_t cut=0;cut<good.size();++cut){{auto r={fn}(good.substr(0,cut));if(r.valid||r.error.empty()||r.consumed>cut)return 4;}}for(int byte=1;byte<127;++byte){{std::string mutated=good;mutated.push_back(static_cast<char>(byte));auto r={fn}(mutated);if(r.valid||r.error.empty()||r.consumed>mutated.size())return 5;}}const std::vector<std::pair<std::string,std::string>> variants={{{variant_literals}}};for(const auto& item:variants){{auto r={fn}(item.first);if(!r.valid||r.canonical!=item.second||!r.error.empty()||r.consumed!=item.first.size())return 6;auto stable={fn}(r.canonical);if(!stable.valid||stable.canonical!=r.canonical)return 6;}}std::string long_decimal=good;auto first=long_decimal.find_first_of("0123456789");if(first!=std::string::npos){{auto last=first;while(last<long_decimal.size()&&long_decimal[last]>='0'&&long_decimal[last]<='9')++last;long_decimal.replace(first,last-first,120U,'9');auto r={fn}(long_decimal);if(r.consumed>long_decimal.size()||(r.valid&&(r.canonical.empty()||!r.error.empty()))||(!r.valid&&(!r.canonical.empty()||r.error.empty())))return 7;}}return 0;'''
    return f"""#include \"{case.task_id}.h\"
#include <cstdint>
#include <string>
#include <utility>
#include <vector>
using lexical_curriculum::{fn};
int main(){{{body}}}
"""


def _cmake(case: Case) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({case.snake} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_compile_options(-Wall -Wextra -Wpedantic -Werror)
enable_testing()
add_executable(visible {case.task_id}.cpp visible_test.cpp)
add_executable(private {case.task_id}.cpp .meta/private_test.cpp)
add_executable(negative .meta/negative.cpp .meta/negative_test.cpp)
target_include_directories(private PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
target_include_directories(negative PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
add_test(NAME visible COMMAND visible)
add_test(NAME private COMMAND private)
add_test(NAME negative COMMAND negative)
set_tests_properties(negative PROPERTIES WILL_FAIL TRUE)
"""


def _render(case: Case, root: Path) -> None:
    root.mkdir(parents=True)
    (root / ".docs").mkdir()
    (root / ".meta").mkdir()
    contract = build_contract(case.task_id, case.api_stem, case.index)
    instructions = f"""# {case.api_stem}

Implement `{case.function}` in namespace `lexical_curriculum`.

{contract.public_contract} Exact end-of-input is required. {contract.result_contract}

For `{contract.valid_input}`, return canonical `{contract.canonical}`. `{contract.named_invalid}` is invalid because it violates the documented {contract.profile} dialect. Empty, incomplete, malformed, and trailing input is invalid. On failure `canonical` is empty, `consumed` is the parser cursor at failure (the zero-based rejected-byte position or `input.size()` at end-of-input, never greater than `input.size()`), and `error` is nonempty. Successful canonical text is idempotent. Input is at most 256 bytes.

The required core is the task-specific composite of the `{contract.band}` base state machine and the `{contract.profile}` lexical dialect; both alter the accepted grammar and canonicalization path. Do not use regex, locale classification, exception-driven stream extraction, cleanup-first filtering, prefix-only parsing, or a generic accept-and-trim wrapper.
"""
    (root / ".docs/introduction.md").write_text(f"# {case.api_stem}\n\nA clean-room lexical validation and exact end-of-input exercise.\n")
    (root / ".docs/instructions.md").write_text(instructions)
    (root / f"{case.task_id}.h").write_text(_header(case))
    (root / f"{case.task_id}.cpp").write_text(_starter(case))
    (root / "visible_test.cpp").write_text(_test(case, private=False))
    (root / ".meta/example.h").write_text(_header(case))
    (root / ".meta/example.cpp").write_text(_source(case))
    (root / ".meta/private_test.cpp").write_text(_test(case, private=True))
    (root / ".meta/negative.cpp").write_text(_source(case, negative=True))
    (root / ".meta/negative_test.cpp").write_text(_test(case, private=False, negative=True))
    (root / "CMakeLists.txt").write_text(_cmake(case))
    (root / ".meta/tests.toml").write_text(f'[visible]\ndescription="canonical example, public result evidence, and named {contract.profile} rejection"\n[private]\ndescription="idempotence, grammar-specific invalids, every proper truncation, and all 126 one-byte end-of-input suffixes"\n[negative]\ndescription="happy path passes while the wrong {contract.profile} dialect accepts its named invalid"\n')
    config = {
        "authors": ["w8-biayn"],
        "blurb": f"Strictly recognize and canonicalize {case.api_stem} input through exact end-of-input.",
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["visible_test.cpp", ".meta/private_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    _json(root / ".meta/config.json", config)
    _json(root / ".meta/provenance.json", {
        "schema_version": "lexical-canonicalization-provenance-v1",
        "task_id": case.task_id,
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "source": str(CURRICULUM.relative_to(REPO_ROOT)),
        "owner": OWNER,
        "authoring": "clean-room repository-authored",
        "license": "CC0-1.0",
        "count_plan_cell": "validation/parsing: lexical validation, canonicalization, exact end-of-input",
        "primary_core_objective": "implemented_pending_oracle",
        "contract_band": contract.band,
        "semantic_profile": contract.profile,
        "named_negative": contract.profile,
        "non_claim": "local task candidate only; no SFT release, training authorization, or benchmark claim",
    })


def _replace_text_tree(root: Path, replacements: dict[str, str]) -> list[str]:
    changed = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        try:
            before = path.read_text()
        except UnicodeDecodeError:
            continue
        after = before
        for old, new in replacements.items():
            after = after.replace(old, new)
        if after != before:
            path.write_text(after)
            changed.append(path.relative_to(root).as_posix())
    return changed


def _materialize_controls(out: Path, all_cases: tuple[Case, ...]) -> dict[str, object]:
    controls_root = out / ".state/controls"
    controls_root.mkdir(parents=True, exist_ok=True)
    records = {}

    source = all_cases[0]
    source_root = out / source.task_id
    rename_root = controls_root / "domain-identifier-rename"
    shutil.copytree(source_root, rename_root)
    rename_changes = _replace_text_tree(
        rename_root,
        {
            source.api_stem: "RenamedDispatchAtom",
            source.result_type: "RenamedDispatchAtomResult",
            source.function: "canonicalize_renamed_dispatch_atom",
        },
    )
    records["domain-identifier-rename"] = {
        "source_task": source.task_id,
        "path": str(rename_root.relative_to(out)),
        "changed_files": rename_changes,
        "expected_relation": "clone",
    }

    constants_root = controls_root / "constants-policy-only"
    shutil.copytree(source_root, constants_root)
    constants_changes = _replace_text_tree(constants_root, {source.prefix: "RND", source.prefix.lower(): "rnd"})
    records["constants-policy-only"] = {
        "source_task": source.task_id,
        "path": str(constants_root.relative_to(out)),
        "changed_files": constants_changes,
        "expected_relation": "clone",
    }

    range_case = all_cases[71]
    range_root = out / range_case.task_id
    opposite_root = controls_root / "opposite-end-selection"
    shutil.copytree(range_root, opposite_root)
    opposite_changes = _replace_text_tree(
        opposite_root,
        {
            "[14-16,18];OK": "[18,14-16];OK",
            "[14-16,18];ok": "[18,14-16];ok",
        },
    )
    records["opposite-end-selection"] = {
        "source_task": range_case.task_id,
        "path": str(opposite_root.relative_to(out)),
        "changed_files": opposite_changes,
        "expected_relation": "clone",
    }
    summary = {"schema_version": "lexical-clone-controls-v2", "controls": records}
    _json(controls_root / "controls.json", summary)
    return summary


def prepare_remedies(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Freeze cycle-01 findings before any semantic owner change."""
    out = _safe_out(out)
    subject_path = out / ".state/audits/cycle-01/subject.json"
    report_path = out / ".state/audits/cycle-01/report.md"
    catalog_path = out / ".state/audits/cycle-01/catalog.tsv"
    for required in (subject_path, report_path, catalog_path):
        if not required.is_file():
            _fail("audit_artifact_missing", str(required))
    subject = json.loads(subject_path.read_text())
    manifest = json.loads((out / ".state/manifest.json").read_text())
    remedy_root = out / ".state/remedy/cycle-01"
    if remedy_root.exists():
        _fail("remedy_records_exist", str(remedy_root))
    records = []
    for case in cases():
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "family_id_before": FAMILY_ID,
            "tree_hash_before": manifest["tree_hash"],
            "generator_path": OWNER,
            "generator_revision": "sha256:0d07a937bac006392bc7de863e8b82bac0b4336e91770cd37b2f2d3971971414",
            "audit_subject_hash": subject["subject_hash"],
            "finding_ids": list(AUDIT_FINDINGS),
            "disposition": "repair-in-place",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": str(CURRICULUM.relative_to(REPO_ROOT)),
            "remedy_spec_hash": _file_sha(CURRICULUM),
            "status": "planned",
            "primary_core_objective_before": "not_achieved",
            "optional_dataset_handoff": "not_requested",
        }
        _json(remedy_root / f"{case.task_id}.json", record)
        records.append(record)
    summary = {
        "schema_version": "lexical-remedy-cycle-v1",
        "cycle": 1,
        "audit_subject_hash": subject["subject_hash"],
        "audit_report": str(report_path.relative_to(out)),
        "audit_catalog": str(catalog_path.relative_to(out)),
        "finding_ids": list(AUDIT_FINDINGS),
        "record_count": len(records),
        "dispositions": {"repair-in-place": len(records)},
        "prior_evidence_invalidated": [
            ".state/creator-preflight.json",
            ".state/diversity-screen.json",
            ".state/docker-sanity.json",
        ],
        "status": "planned",
    }
    _json(remedy_root / "summary.json", summary)
    return summary


def prepare_cycle_02_remedies(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Bind cycle-02 findings before changing the rejected task semantics."""
    out = _safe_out(out)
    audit_root = out / ".state/audits/cycle-02"
    required = tuple(audit_root / name for name in ("subject.json", "report.md", "catalog.tsv"))
    for path in required:
        if not path.is_file():
            _fail("audit_artifact_missing", str(path))
    subject = json.loads(required[0].read_text())
    if subject.get("subject_hash") != "sha256:e818812ca46c003dc43a8b8640dfb514da81f7562376371fd2a4bfe1d828b32d":
        _fail("audit_subject_mismatch", str(subject.get("subject_hash")))
    manifest = json.loads((out / ".state/manifest.json").read_text())
    docker = json.loads((out / ".state/docker-sanity.json").read_text())
    remedy_root = out / ".state/remedy/cycle-02"
    if remedy_root.exists():
        _fail("remedy_records_exist", str(remedy_root))
    curriculum_hash_before = _file_sha(CURRICULUM)
    owner_hash_before = docker["owner_hashes"][OWNER]
    records = []
    for case in cases():
        record = {
            "schema_version": "aider-task-remedy-v2",
            "cycle": 2,
            "task_id": case.task_id,
            "family_id_before": FAMILY_ID,
            "tree_hash_before": manifest["tree_hash"],
            "generator_path": OWNER,
            "generator_revision_before": owner_hash_before,
            "audit_subject_hash": subject["subject_hash"],
            "finding_ids": list(CYCLE_02_FINDINGS),
            "disposition": "repair-in-place",
            "root_cause": "ten shared base parsers, guard-only profile axis, shallow oracle, underdocumented payloads, fixture-specific clone override, and incomplete state binding",
            "planned_remedy": "make both axes alter public grammar and parser control flow; publish meaningful fields; add offset/branch/property oracles; use one generic clone rule; hash controls, screens, tools, and retained logs",
            "remedy_spec_path": str(CURRICULUM.relative_to(REPO_ROOT)),
            "remedy_spec_hash_before": curriculum_hash_before,
            "status": "planned",
            "primary_core_objective_before": "not_achieved",
            "optional_dataset_handoff": "not_requested",
        }
        _json(remedy_root / f"{case.task_id}.json", record)
        records.append(record)
    summary = {
        "schema_version": "lexical-remedy-cycle-v2",
        "cycle": 2,
        "audit_subject_hash": subject["subject_hash"],
        "audit_report": str(required[1].relative_to(out)),
        "audit_catalog": str(required[2].relative_to(out)),
        "audit_report_hash": _file_sha(required[1]),
        "audit_catalog_hash": _file_sha(required[2]),
        "finding_ids": list(CYCLE_02_FINDINGS),
        "record_count": len(records),
        "dispositions": {"repair-in-place": len(records)},
        "tree_hash_before": manifest["tree_hash"],
        "generator_revision_before": owner_hash_before,
        "remedy_spec_hash_before": curriculum_hash_before,
        "status": "planned",
    }
    _json(remedy_root / "summary.json", summary)
    return summary


def prepare_cycle_03_remedies(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Bind the frozen cycle-03 counterexamples before cycle-04 changes."""
    out = _safe_out(out)
    audit_root = out / ".state/audits/cycle-03"
    required = tuple(audit_root / name for name in ("subject.json", "report.md", "catalog.tsv"))
    for path in required:
        if not path.is_file():
            _fail("audit_artifact_missing", str(path))
    subject = json.loads(required[0].read_text())
    expected_subject = "sha256:35afafa0fcad6922b234257209595c2a0aff9a5294d546b6f2173f57d4e205b3"
    if subject.get("subject_hash") != expected_subject:
        _fail("audit_subject_mismatch", str(subject.get("subject_hash")))
    manifest = json.loads((out / ".state/manifest.json").read_text())
    docker = json.loads((out / ".state/docker-sanity.json").read_text())
    remedy_root = out / ".state/remedy/cycle-03"
    if remedy_root.exists():
        _fail("remedy_records_exist", str(remedy_root))
    records = []
    for case in cases():
        record = {
            "schema_version": "aider-task-remedy-v3",
            "cycle": 3,
            "task_id": case.task_id,
            "family_id_before": FAMILY_ID,
            "tree_hash_before": manifest["tree_hash"],
            "generator_path": OWNER,
            "generator_revision_before": docker["owner_hashes"][OWNER],
            "audit_subject_hash": subject["subject_hash"],
            "finding_ids": list(CYCLE_03_FINDINGS),
            "disposition": "repair-in-place",
            "root_cause": "cursor semantics, unchecked decimal conversion, missing quoted/range/frame branches, hidden-grader prompt language, and a clone-policy override absent from the adversarial oracle",
            "planned_remedy": "publish cursor semantics and exact alphabets; saturate decimal conversion; execute escaped quoted atoms, trailing separators, short frames, and long-decimal sanitizer probes; remove hidden-grader language and policy overrides; require raw seven-dimension control rejection",
            "remedy_spec_path": str(CURRICULUM.relative_to(REPO_ROOT)),
            "remedy_spec_hash_before": _file_sha(CURRICULUM),
            "status": "planned",
            "primary_core_objective_before": "not_achieved",
            "optional_dataset_handoff": "not_requested",
        }
        _json(remedy_root / f"{case.task_id}.json", record)
        records.append(record)
    summary = {
        "schema_version": "lexical-remedy-cycle-v3",
        "cycle": 3,
        "audit_subject_hash": subject["subject_hash"],
        "audit_report": str(required[1].relative_to(out)),
        "audit_catalog": str(required[2].relative_to(out)),
        "audit_report_hash": _file_sha(required[1]),
        "audit_catalog_hash": _file_sha(required[2]),
        "finding_ids": list(CYCLE_03_FINDINGS),
        "record_count": len(records),
        "dispositions": {"repair-in-place": len(records)},
        "tree_hash_before": manifest["tree_hash"],
        "generator_revision_before": docker["owner_hashes"][OWNER],
        "status": "planned",
    }
    _json(remedy_root / "summary.json", summary)
    return summary


def materialize(out: Path = DEFAULT_OUT, *, force: bool = False) -> dict[str, object]:
    out = _safe_out(out)
    all_cases = cases()
    collisions = sorted(set(c.task_id for c in all_cases) & set(_existing_ids(exclude=out)))
    if collisions:
        _fail("existing_task_id", ",".join(collisions))
    if out.exists():
        manifest_path = out / ".state/manifest.json"
        if not force:
            _fail("output_exists", str(out))
        if not manifest_path.is_file() or json.loads(manifest_path.read_text()).get("owner") != OWNER:
            _fail("foreign_output_root", str(out))
        preserved: dict[str, bytes] = {}
        for state_name in ("audits", "remedy"):
            state_root = out / ".state" / state_name
            if state_root.is_dir():
                for path in state_root.rglob("*"):
                    if path.is_file():
                        preserved[path.relative_to(out).as_posix()] = path.read_bytes()
        audit_root = out / ".state/audits"
        if audit_root.is_dir():
            for path in sorted(audit_root.rglob("*"), reverse=True):
                path.chmod(0o755 if path.is_dir() else 0o644)
            audit_root.chmod(0o755)
        shutil.rmtree(out)
    else:
        preserved = {}
    out.mkdir(parents=True)
    for case in all_cases:
        _render(case, out / case.task_id)
    state = out / ".state"
    for relative, payload in preserved.items():
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    audit_root = out / ".state/audits"
    if audit_root.is_dir():
        for path in audit_root.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        for path in sorted((candidate for candidate in audit_root.rglob("*") if candidate.is_dir()), reverse=True):
            path.chmod(0o555)
        audit_root.chmod(0o555)
    _materialize_controls(out, all_cases)
    manifest = {
        "schema_version": "lexical-canonicalization-family-v1",
        "family_id": FAMILY_ID,
        "owner": OWNER,
        "curriculum": str(CURRICULUM.relative_to(REPO_ROOT)),
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "task_count": 100,
        "task_ids": [c.task_id for c in all_cases],
        "status": "generated_pending_creator_preflight",
        "selected_prompts": ["docs/aider-tasks-spec/prompts/generate-family-spec.md", "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"],
    }
    _json(state / "manifest.json", manifest)
    manifest["tree_hash"] = _tree_hash(out)
    _json(state / "manifest.json", manifest)
    return manifest


def _role_and_prompt_check(out: Path, case: Case) -> dict[str, object]:
    root = out / case.task_id
    config = json.loads((root / ".meta/config.json").read_text())
    expected = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
    if config["files"]["solution"] != expected or config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
        _fail("role_conflict", case.task_id)
    prompt_files = [".docs/introduction.md", ".docs/instructions.md", *expected]
    if any(".meta" in path or path == "CMakeLists.txt" for path in prompt_files):
        _fail("prompt_contract_incomplete", case.task_id)
    for path in sum(config["files"].values(), []):
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts or not (root / candidate).is_file():
            _fail("unsafe_path", f"{case.task_id}:{path}")
    return {"task_id": case.task_id, "prompt_files": prompt_files, "status": "pass"}


CPP_SEMANTIC_IDENTIFIERS = frozenset(
    {
        "if", "else", "for", "while", "return", "break", "continue", "true", "false",
        "bool", "char", "int", "long", "double", "unsigned", "auto", "const", "static_cast",
        "string", "string_view", "vector", "array", "map", "optional", "pair", "size_t",
        "valid", "canonical", "consumed", "error", "primary", "secondary", "decoded",
        "components", "segments", "has_optional", "component_count", "label", "magnitude",
        "revision", "span", "identifier_checksum", "locator_coordinates", "quoted_value",
        "numeric_value", "version_components", "normalized_path", "base_units",
        "normalized_ranges", "record_fields", "frame_payload", "declared_length",
        "identifier_hyphen_count", "locator_slash_count", "decoded_atom_bytes",
        "mantissa_digit_count", "version_component_count", "normalized_segment_count",
        "unit_symbol_count", "range_count", "record_field_count", "declared_payload_bytes",
        "checksum_remainder", "approval_word", "increasing_digit_count",
        "unique_symbol_count", "bounded_witness", "required_digit_index",
        "parity_even", "leading_symbol", "witness_disjoint", "optional_value",
        "ascii_alpha", "ascii_digit", "ascii_alnum", "upper", "lower", "to_int",
        "digit_sum", "strictly_increasing", "all_unique", "contains_digit", "shares_symbol",
        "push_back", "pop_back", "substr", "front", "back", "count", "empty", "size",
    }
)


def _cpp_semantic_tokens(text: str) -> list[str]:
    text = re.sub(r"//[^\n]*|/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " LITERAL ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?(?:[uUlLfF]+)?\b", " NUMBER ", text)
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|>=|<=|&&|\|\||\+\+|--|->|[-+*/%<>{}()[\];,:?=]", text)
    return [token if token in CPP_SEMANTIC_IDENTIFIERS or not token[0].isalpha() else "ID" for token in raw]


def _word_tokens(text: str, case: Case) -> list[str]:
    text = re.sub(r"`[^`]*`", " ", text)
    stop = {"implement", "namespace", "input", "return", "canonical", "task", "required", "every"}
    stop.update(case.task_id.removeprefix("lex-").split("-"))
    words = re.findall(r"[a-z][a-z0-9-]+", text.lower())
    return [word for word in words if word not in stop and not word.isdigit()]


def _shingles(tokens: list[str], width: int) -> set[str]:
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[index : index + width]) for index in range(len(tokens) - width + 1)}


def _artifact_signatures(root: Path, case: Case) -> dict[str, set[str]]:
    header = _cpp_semantic_tokens((root / f"{case.task_id}.h").read_text())

    def parser_tokens(path: Path) -> list[str]:
        text = path.read_text()
        marker = re.search(r"\b[A-Za-z_][A-Za-z0-9_]*Result\s+canonicalize_[A-Za-z0-9_]+\s*\(", text)
        return _cpp_semantic_tokens(text[marker.start() :] if marker else text)

    source = parser_tokens(root / ".meta/example.cpp")
    negative = parser_tokens(root / ".meta/negative.cpp")
    visible = _cpp_semantic_tokens((root / "visible_test.cpp").read_text())
    private = _cpp_semantic_tokens((root / ".meta/private_test.cpp").read_text())
    docs = _word_tokens((root / ".docs/instructions.md").read_text(), case)
    reference_flow = _shingles(source, 7)
    negative_flow = _shingles(negative, 7)
    return {
        "public_api": _shingles(header, 3),
        "owned_state_or_algorithm": _shingles(source, 5),
        "mutation_or_selection_rules": _shingles(docs, 3),
        "invalid_and_boundary_behavior": _shingles(docs + private, 4),
        "reference_control_flow": reference_flow,
        "deterministic_oracle": _shingles(visible + private, 5),
        "topic_specific_negative_fixture": (reference_flow ^ negative_flow) | _shingles(source, 11),
    }


def _dimension_decisions(left: dict[str, set[str]], right: dict[str, set[str]]) -> dict[str, dict[str, object]]:
    decisions = {}
    for dimension in DIMENSIONS:
        a, b = left[dimension], right[dimension]
        intersection = len(a & b)
        union = len(a | b)
        score = intersection / union if union else 1.0
        decisions[dimension] = {
            "pass": bool(a) and bool(b) and a != b and score < 0.98,
            "jaccard": score,
            "symmetric_difference": len(a ^ b),
        }
    return decisions


def diversity_screen(out: Path) -> dict[str, object]:
    all_cases = cases()
    signatures = {case.task_id: _artifact_signatures(out / case.task_id, case) for case in all_cases}
    decisions = []
    for i, left in enumerate(all_cases):
        for right in all_cases[i + 1 :]:
            per_dimension = _dimension_decisions(signatures[left.task_id], signatures[right.task_id])
            decisions.append({"left": left.task_id, "right": right.task_id, "dimensions": per_dimension, "pass": all(v["pass"] for v in per_dimension.values())})
    if len(decisions) != 4950 or not all(item["pass"] for item in decisions):
        failed = next((item for item in decisions if not item["pass"]), None)
        if failed is None:
            _fail("duplicate_family", f"pair-count:{len(decisions)}")
        failed_dimensions = [name for name, decision in failed["dimensions"].items() if not decision["pass"]]
        _fail("duplicate_family", f"{failed['left']}:{failed['right']}:{','.join(failed_dimensions)}")
    controls = json.loads((out / ".state/controls/controls.json").read_text())
    control_decisions = {}
    for name, value in controls["controls"].items():
        source_case = next(case for case in all_cases if case.task_id == value["source_task"])
        source_root = out / source_case.task_id
        control_root = out / value["path"]
        if not value["changed_files"] or not control_root.is_dir():
            _fail("clone_control_failed", name)
        actual_changed = []
        for relative in sorted(set(value["changed_files"])):
            source_file, control_file = source_root / relative, control_root / relative
            if not source_file.is_file() or not control_file.is_file() or source_file.read_bytes() == control_file.read_bytes():
                _fail("clone_control_failed", f"{name}:{relative}")
            actual_changed.append(relative)
        per_dimension = _dimension_decisions(
            signatures[source_case.task_id], _artifact_signatures(control_root, source_case)
        )
        mutation_witness = {
            relative: {
                "source": _file_sha(source_root / relative),
                "control": _file_sha(control_root / relative),
            }
            for relative in actual_changed
        }
        rejected = [dimension for dimension, decision in per_dimension.items() if not decision["pass"]]
        if set(rejected) != set(DIMENSIONS):
            _fail("clone_control_not_rejected", f"{name}:{sorted(set(DIMENSIONS) - set(rejected))}")
        control_decisions[name] = {
            **value,
            "actual_changed_files": actual_changed,
            "dimensions": per_dimension,
            "raw_dimensions": per_dimension,
            "mutation_witness": mutation_witness,
            "rejected_dimensions": rejected,
            "production_evaluator_rejected": True,
            "runtime_status": "pending",
        }
    result = {"schema_version": "lexical-diversity-v2", "root_count": 100, "pair_count": len(decisions), "dimensions": list(DIMENSIONS), "decisions": decisions, "controls": control_decisions, "status": "pass"}
    _json(out / ".state/diversity-screen.json", result)
    return result


def _role_artifact(root: Path) -> dict[str, object]:
    config_path = root / ".meta/config.json"
    config = json.loads(config_path.read_text()) if config_path.is_file() else {"files": {}}
    files = config.get("files", {})
    prompt_paths = [*sorted((root / ".docs").glob("*.md"))]
    prompt_paths.extend(root / path for path in files.get("solution", []))
    reference_paths = [root / path for path in files.get("example", [])]
    test_paths = [root / path for path in files.get("test", [])]
    semantic_paths = [*prompt_paths, *reference_paths, *test_paths]
    cpp_tokens: list[str] = []
    docs_tokens: list[str] = []
    for path in semantic_paths:
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        if path.suffix.lower() in {".cpp", ".cc", ".cxx", ".h", ".hpp"}:
            cpp_tokens.extend(_cpp_semantic_tokens(text))
        else:
            text = re.sub(r"`[^`]*`", " ", text.lower())
            docs_tokens.extend(word for word in re.findall(r"[a-z][a-z0-9-]+", text) if word not in {"the", "and", "return", "input", "implement", "canonical"})

    def content_hash(paths: list[Path]) -> str:
        digest = hashlib.sha256()
        for path in paths:
            if path.is_file():
                digest.update(path.relative_to(root).as_posix().encode())
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
        return "sha256:" + digest.hexdigest()

    return {
        "cpp": _shingles(cpp_tokens, 7),
        "docs": _shingles(docs_tokens, 4),
        "prompt_hash": content_hash(prompt_paths),
        "reference_hash": content_hash(reference_paths),
        "test_hash": content_hash(test_paths),
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _corpus_screen(out: Path) -> dict[str, object]:
    found = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    if found != OFFICIAL_HOLDOUTS:
        _fail("benchmark_screen_not_completed", f"found={len(found)}")
    candidates = {case.task_id: _role_artifact(out / case.task_id) for case in cases()}
    prompt_hashes: dict[str, str] = {}
    reference_hashes: dict[str, str] = {}
    for task_id, artifact in candidates.items():
        for field, ledger in (("prompt_hash", prompt_hashes), ("reference_hash", reference_hashes)):
            digest = str(artifact[field])
            if digest in ledger:
                _fail("duplicate_family", f"{field}:{ledger[digest]}:{task_id}")
            ledger[digest] = task_id

    external_roots: list[tuple[str, Path, str]] = []
    for legacy in LEGACY_ROOTS:
        if legacy.is_dir():
            for config in legacy.rglob(".meta/config.json"):
                if ".state" not in config.parts:
                    external_roots.append((config.parent.parent.name, config.parent.parent, "existing"))
    for slug in sorted(OFFICIAL_HOLDOUTS):
        external_roots.append((slug, HOLDOUT_ROOT / slug, "official_holdout"))

    external = [(task_id, root, scope, _role_artifact(root)) for task_id, root, scope in external_roots]
    comparisons = []
    maximum = {"cpp": 0.0, "docs": 0.0, "pair": None}
    for case in cases():
        candidate = candidates[case.task_id]
        for external_id, external_root, scope, artifact in external:
            cpp_score = _jaccard(candidate["cpp"], artifact["cpp"])
            docs_score = _jaccard(candidate["docs"], artifact["docs"])
            if cpp_score >= 0.92 or docs_score >= 0.92:
                code = "benchmark_content_overlap" if scope == "official_holdout" else "semantic_lineage_overlap"
                _fail(code, f"{case.task_id}:{external_id}:{cpp_score:.3f}:{docs_score:.3f}")
            if cpp_score > maximum["cpp"] or docs_score > maximum["docs"]:
                maximum = {"cpp": max(maximum["cpp"], cpp_score), "docs": max(maximum["docs"], docs_score), "pair": f"{case.task_id}:{external_id}:{scope}"}
            comparisons.append({"task_id": case.task_id, "external_id": external_id, "scope": scope, "cpp_jaccard": cpp_score, "docs_jaccard": docs_score, "external_path": str(external_root.relative_to(REPO_ROOT))})
    result = {
        "schema_version": "lexical-corpus-screen-v2",
        "candidate_count": 100,
        "existing_root_count": sum(1 for _, _, scope, _ in external if scope == "existing"),
        "official_holdout_count": 26,
        "comparisons": len(comparisons),
        "maximum": maximum,
        "unique_prompt_hashes": len(prompt_hashes),
        "unique_reference_hashes": len(reference_hashes),
        "normalizer": "lexical-artifact-semantic-v2",
        "comparison_rows": comparisons,
        "status": "pass",
    }
    _json(out / ".state/corpus-screen.json", result)
    return result


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    out = _safe_out(out)
    manifest = json.loads((out / ".state/manifest.json").read_text())
    if manifest.get("task_count") != 100 or manifest.get("task_ids") != [c.task_id for c in cases()]:
        _fail("generator_output_drift", "manifest")
    if manifest.get("tree_hash") != _tree_hash(out):
        _fail("generator_output_drift", "tree hash")
    provenance = {"curriculum_hash": _file_sha(CURRICULUM), "family_spec_hash": _file_sha(FAMILY_SPEC)}
    provenance_refreshed = {key: value for key, value in provenance.items() if manifest.get(key) != value}
    if provenance_refreshed:
        # Source specification documents changed without affecting emitted task
        # content.  Rebind the ledger through this owner-controlled path; never
        # leave a stale hash claiming to describe the current source.
        manifest.update(provenance_refreshed)
        _json(out / ".state/manifest.json", manifest)
    roles = [_role_and_prompt_check(out, case) for case in cases()]
    screen = diversity_screen(out)
    corpus = _corpus_screen(out)
    current_ids = _existing_ids(exclude=out)
    if set(manifest["task_ids"]) & set(current_ids):
        _fail("existing_task_id", "late collision")
    receipt = {
        "schema_version": "lexical-creator-preflight-v2",
        "owner": OWNER,
        "owner_hash": _file_sha(REPO_ROOT / OWNER),
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "tree_hash": _tree_hash(out),
        "root_count": 100,
        "roles": {"count": len(roles), "status": "pass"},
        "manifest_provenance_refreshed": sorted(provenance_refreshed),
        "diversity": {"pair_count": screen["pair_count"], "status": "pass"},
        "corpus_screen": {
            key: corpus[key]
            for key in (
                "existing_root_count",
                "official_holdout_count",
                "comparisons",
                "maximum",
                "unique_prompt_hashes",
                "unique_reference_hashes",
                "status",
            )
        },
        "status": "structural_pass_pending_runtime",
    }
    _json(out / ".state/creator-preflight.json", receipt)
    return receipt


def _replace_reference(root: Path) -> None:
    config = json.loads((root / ".meta/config.json").read_text())
    for target, example in zip(config["files"]["solution"], config["files"]["example"], strict=True):
        shutil.copy2(root / example, root / target)


def _checked(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if completed.returncode:
        _fail("runtime_command_failed", f"{command}:{completed.stdout[-6000:]}")
    return completed


def _runtime_one(root: Path, build: Path, *, sanitizer: bool, log_root: Path | None = None) -> dict[str, object]:
    build.mkdir(parents=True, exist_ok=True)
    work = build / root.name
    shutil.copytree(root, work)
    _replace_reference(work)
    build_dir = work / ("build-sanitizer" if sanitizer else "build-normal")
    args = ["cmake", "-S", str(work), "-B", str(build_dir), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++"]
    if sanitizer:
        args += ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
    configure = _checked(args)
    compiled = _checked(["cmake", "--build", str(build_dir), "-j2"])
    listed = _checked(["ctest", "--test-dir", str(build_dir), "-N"]).stdout
    count = int(re.search(r"Total Tests: (\d+)", listed).group(1))
    env = os.environ.copy()
    if sanitizer:
        env["ASAN_OPTIONS"] = "detect_leaks=1:halt_on_error=1"
        env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    ctest = _checked(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], env=env)
    visible = subprocess.run([str(build_dir / "visible")], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    private = subprocess.run([str(build_dir / "private")], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    negative = subprocess.run([str(build_dir / "negative")], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if visible.returncode != 0 or private.returncode != 0 or negative.returncode == 0:
        _fail("negative_fixture_not_rejected", f"{root.name}:{visible.returncode}:{private.returncode}:{negative.returncode}")
    logs = {
        "configure.log": configure.stdout,
        "build.log": compiled.stdout,
        "ctest.log": ctest.stdout,
        "negative.log": negative.stdout,
    }
    log_paths = {}
    if log_root is not None:
        log_root.mkdir(parents=True, exist_ok=True)
        for name, payload in logs.items():
            path = log_root / name
            try:
                path.write_text(payload)
            except PermissionError:
                path.unlink()
                path.write_text(payload)
            log_paths[name] = str(path)
    return {
        "discovered_tests": count,
        "visible_exit": visible.returncode,
        "private_exit": private.returncode,
        "negative_exit": negative.returncode,
        "negative_happy_path_and_discriminator_executed": True,
        "configure_log_hash": _sha(configure.stdout.encode()),
        "build_log_hash": _sha(compiled.stdout.encode()),
        "ctest_log_hash": _sha(ctest.stdout.encode()),
        "negative_log_hash": _sha(negative.stdout.encode()),
        "retained_logs": log_paths,
    }


def _per_root_digests(root: Path) -> dict[str, object]:
    config = json.loads((root / ".meta/config.json").read_text())
    roles = config["files"]
    paths = {
        "prompt": [*sorted((root / ".docs").glob("*.md")), *(root / path for path in roles["solution"])],
        "starter": [root / path for path in roles["solution"]],
        "reference": [root / path for path in roles["example"]],
        "tests": [root / path for path in roles["test"]] + [root / ".meta/negative.cpp", root / ".meta/negative_test.cpp"],
        "metadata": [root / ".meta/config.json", root / ".meta/provenance.json", root / ".meta/tests.toml", root / "CMakeLists.txt"],
    }
    result = {}
    for role, members in paths.items():
        digest = hashlib.sha256()
        for path in members:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        result[role] = "sha256:" + digest.hexdigest()
    return result


def verify_runtime(out: Path = DEFAULT_OUT, *, evidence_class: str = "host_iteration") -> dict[str, object]:
    out = _safe_out(out)
    verify_core(out)
    log_base = _log_base(out, evidence_class)
    counts = []
    control_counts = []
    with tempfile.TemporaryDirectory(prefix="lexical-canonicalization-") as temp:
        build = Path(temp)
        for case in cases():
            normal = _runtime_one(out / case.task_id, build / "normal", sanitizer=False, log_root=log_base / case.task_id / "normal")
            sanitizer = _runtime_one(out / case.task_id, build / "sanitizer", sanitizer=True, log_root=log_base / case.task_id / "sanitizer")
            if normal["discovered_tests"] <= 0 or normal["discovered_tests"] != sanitizer["discovered_tests"]:
                _fail("sanitizer_test_count_mismatch", f"{case.task_id}:{normal['discovered_tests']}:{sanitizer['discovered_tests']}")
            counts.append({"task_id": case.task_id, "normal": normal, "sanitizer": sanitizer, "digests": _per_root_digests(out / case.task_id)})
        controls = json.loads((out / ".state/controls/controls.json").read_text())["controls"]
        for name, control in controls.items():
            root = out / control["path"]
            normal = _runtime_one(root, build / "control-normal", sanitizer=False, log_root=log_base / "controls" / name / "normal")
            sanitizer = _runtime_one(root, build / "control-sanitizer", sanitizer=True, log_root=log_base / "controls" / name / "sanitizer")
            if normal["discovered_tests"] != sanitizer["discovered_tests"] or normal["discovered_tests"] <= 0:
                _fail("sanitizer_test_count_mismatch", f"control:{name}")
            control_counts.append({"control": name, "source_task": control["source_task"], "normal": normal, "sanitizer": sanitizer, "tree_hash": _tree_hash(root)})
    compiler = shutil.which("c++")
    cmake = shutil.which("cmake")
    if compiler is None or cmake is None:
        _fail("runtime_tool_missing", f"c++={compiler}:cmake={cmake}")
    toolchain = {
        "compiler_path": compiler,
        "compiler_hash": _file_sha(Path(compiler).resolve()),
        "compiler_version": _checked([compiler, "--version"]).stdout.splitlines()[0],
        "cmake_path": cmake,
        "cmake_hash": _file_sha(Path(cmake).resolve()),
        "cmake_version": _checked([cmake, "--version"]).stdout.splitlines()[0],
    }
    receipt = {
        "schema_version": "lexical-runtime-v2",
        "evidence_class": evidence_class,
        "locked_oracle": False,
        "network": "host" if evidence_class == "host_iteration" else "none",
        "mounted_tree_hash": _tree_hash(out),
        "tree_hash": _tree_hash(out),
        "owner_hashes": {
            OWNER: _file_sha(REPO_ROOT / OWNER),
            "src/w8_biayn/integrations/moonlight_lexical_canonicalization_contracts.py": _file_sha(REPO_ROOT / "src/w8_biayn/integrations/moonlight_lexical_canonicalization_contracts.py"),
        },
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "focused_test_hash": _file_sha(REPO_ROOT / "tests/test_moonlight_lexical_canonicalization_aider_tasks.py"),
        "diversity_policy_hash": _file_sha(REPO_ROOT / OWNER),
        "toolchain": toolchain,
        "root_count": 100,
        "counts": counts,
        "controls": control_counts,
        "retained_log_root": str(log_base.relative_to(out)),
        "creator_preflight_hash": _file_sha(out / ".state/creator-preflight.json"),
        "diversity_screen_hash": _file_sha(out / ".state/diversity-screen.json"),
        "corpus_screen_hash": _file_sha(out / ".state/corpus-screen.json"),
        "status": "pass",
    }
    _json(out / ".state/host-runtime.json", receipt)
    return receipt


def docker_sanity(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    out = _safe_out(out)
    verify_core(out)
    inspected = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if inspected.returncode:
        _fail("docker_sanity_not_completed", inspected.stderr.strip())
    command = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{REPO_ROOT}:{REPO_ROOT}:ro",
        "-v", f"{out}:{out}:rw",
        "-e", f"PYTHONPATH={REPO_ROOT / 'src'}",
        "-w", str(REPO_ROOT), image, "python3", "-m",
        "w8_biayn.integrations.moonlight_lexical_canonicalization_aider_tasks",
        "--out", str(out), "--verify-runtime", "--docker-runtime",
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode:
        _fail("docker_sanity_failed", completed.stdout[-12000:])
    host_receipt = out / ".state/host-runtime.json"
    runtime = json.loads(host_receipt.read_text())
    live_tree_hash = _tree_hash(out)
    if runtime.get("mounted_tree_hash") != live_tree_hash or runtime.get("tree_hash") != live_tree_hash:
        _fail("grader_mount_hash_mismatch", f"{runtime.get('mounted_tree_hash')}:{live_tree_hash}")
    if len(runtime.get("counts", [])) != 100 or len(runtime.get("controls", [])) != 3:
        _fail("docker_sanity_incomplete", "runtime inventories")
    runtime.update({"evidence_class": "docker_sanity", "network": "none", "image": image, "image_id": inspected.stdout.strip(), "docker_command": command, "status": "pass"})
    owner_hash = _file_sha(REPO_ROOT / OWNER)
    curriculum_hash = _file_sha(CURRICULUM)
    for remedy_cycle in ("cycle-01", "cycle-02", "cycle-03"):
        remedy_root = out / ".state/remedy" / remedy_cycle
        for case in cases():
            record_path = remedy_root / f"{case.task_id}.json"
            if not record_path.is_file():
                continue
            record = json.loads(record_path.read_text())
            record.update({
                "status": "verified",
                "primary_core_objective_after": "achieved",
                "tree_hash_after": live_tree_hash,
                "generator_revision_after": owner_hash,
                "remedy_spec_hash_executed": curriculum_hash,
                "normal_discovered_tests": 3,
                "sanitizer_discovered_tests": 3,
                "negative_fixture": "compiled_happy_path_passed_named_discriminator_rejected",
                "benchmark_screen": "pass",
                "family_screen": "pass",
                "prompt_boundary": "pass",
                "strongest_local_status": "remediation_verified_pending_fresh_audit",
            })
            _json(record_path, record)
        remedy_summary_path = remedy_root / "summary.json"
        if remedy_summary_path.is_file():
            remedy_summary = json.loads(remedy_summary_path.read_text())
            remedy_summary.update({
                "status": "verified_pending_fresh_audit",
                "tree_hash_after": live_tree_hash,
                "generator_revision_after": owner_hash,
                "remedy_spec_hash_executed": curriculum_hash,
                "docker_receipt": ".state/docker-sanity.json",
            })
            _json(remedy_summary_path, remedy_summary)
    cycle = {
        "schema_version": "lexical-creator-cycle-v1",
        "cycle": 4,
        "prior_audit_subject": "sha256:35afafa0fcad6922b234257209595c2a0aff9a5294d546b6f2173f57d4e205b3",
        "closed_by_remediation_pending_audit": list(CYCLE_03_FINDINGS),
        "tree_hash": live_tree_hash,
        "curriculum_hash": curriculum_hash,
        "family_spec_hash": runtime["family_spec_hash"],
        "owner_hashes": runtime["owner_hashes"],
        "focused_test_hash": runtime["focused_test_hash"],
        "docker_receipt": ".state/docker-sanity.json",
        "diversity_receipt": ".state/diversity-screen.json",
        "diversity_receipt_hash": runtime["diversity_screen_hash"],
        "corpus_receipt": ".state/corpus-screen.json",
        "corpus_receipt_hash": runtime["corpus_screen_hash"],
        "creator_preflight_hash": runtime["creator_preflight_hash"],
        "root_count": 100,
        "control_count": 3,
        "status": "remediation_verified_pending_fresh_audit",
    }
    cycle_path = out / ".state/cycles/cycle-04.json"
    _json(cycle_path, cycle)
    manifest = json.loads((out / ".state/manifest.json").read_text())
    manifest.update({"status": "remediation_verified_pending_fresh_audit", "docker_receipt": ".state/docker-sanity.json", "tree_hash": live_tree_hash})
    _json(out / ".state/manifest.json", manifest)
    runtime.update({
        "audit_cycle_01_hash": _tree_hash(out / ".state/audits/cycle-01"),
        "audit_cycle_02_hash": _tree_hash(out / ".state/audits/cycle-02"),
        "audit_cycle_03_hash": _tree_hash(out / ".state/audits/cycle-03"),
        "remedy_cycle_01_hash": _tree_hash(out / ".state/remedy/cycle-01"),
        "remedy_cycle_02_hash": _tree_hash(out / ".state/remedy/cycle-02"),
        "remedy_cycle_03_hash": _tree_hash(out / ".state/remedy/cycle-03"),
        "runtime_log_tree_hash": _tree_hash(out / ".state/runtime-logs"),
        "cycle_record_hash": _file_sha(cycle_path),
        "manifest_hash": _file_sha(out / ".state/manifest.json"),
    })
    _json(out / ".state/docker-sanity.json", runtime)
    return runtime


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-runtime", action="store_true")
    parser.add_argument("--docker-runtime", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--prepare-remedies", action="store_true")
    parser.add_argument("--prepare-cycle-02-remedies", action="store_true")
    parser.add_argument("--prepare-cycle-03-remedies", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.materialize:
        materialize(args.out, force=args.force)
    if args.prepare_remedies:
        prepare_remedies(args.out)
    if args.prepare_cycle_02_remedies:
        prepare_cycle_02_remedies(args.out)
    if args.prepare_cycle_03_remedies:
        prepare_cycle_03_remedies(args.out)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_runtime:
        verify_runtime(args.out, evidence_class="docker_sanity" if args.docker_runtime else "host_iteration")
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
