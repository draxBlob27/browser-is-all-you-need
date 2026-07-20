"""Materialize and reverify the clean-room priority-queue v2 family."""
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
from w8_biayn.integrations.moonlight_priority_queue_cases import CASES, Case

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/priority-queue")
LEGACY_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/priority-queue")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_PRIORITY_QUEUE_CURRICULUM.md"
AUDIT_SPEC = "docs/aider-tasks-spec/aider-dsa/priority-queue.md"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
BOUND_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
FAMILY_ID = "aider-dsa-priority-queue-v2"
MANIFEST_SCHEMA = "aider-priority-queue-materialization-v2"
LOCKED_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
TASKS = CASES
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table", "Implementation invariant",
    "Starter and reference", "Tests", "Files and metadata", "Build/oracle",
    "Family/contamination", "Optional dataset handoff", "Acceptance",
)
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset((
    "all-your-base", "allergies", "bank-account", "binary-search-tree", "circular-buffer", "clock",
    "complex-numbers", "crypto-square", "diamond", "dnd-character", "gigasecond", "grade-school",
    "kindergarten-garden", "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
    "perfect-numbers", "phone-number", "queen-attack", "robot-name", "space-age", "spiral-matrix",
    "sublist", "yacht", "zebra-puzzle",
))
FORBIDDEN_CORE = (
    "std::priority_queue", "std::make_heap", "std::push_heap", "std::pop_heap", "std::sort(",
    "std::stable_sort(", "std::map<", "std::set<", "std::multimap<", "std::multiset<",
    "boost::heap", "__gnu_pbds",
)
NEGATIVE_PROFILES = {
    "indexed-binary-max-heap": ("authoritative_ordered_map", "struct authoritative_ordered_map {};", "ordered-map selection replaces indexed mutation"),
    "four-ary-ready-heap": ("binary_two_child_heap", "struct binary_two_child_heap {};", "binary branching replaces the required four-ary ready heap"),
    "tiered-fifo-buckets": ("comparison_heap_for_tiers", "struct comparison_heap_for_tiers {};", "a comparison heap erases tier FIFO semantics"),
    "weighted-two-lane-cycle": ("single_sorted_print_lane", "struct single_sorted_print_lane {};", "one sorted lane erases the 2:1 service cycle"),
    "aging-acuity-buckets": ("static_patient_priority", "struct static_patient_priority {};", "static priority omits elapsed-time aging"),
    "monotone-radix-heap": ("ordered_deadline_tree", "struct ordered_deadline_tree {};", "an ordered tree bypasses radix redistribution"),
    "heap-of-zone-heads": ("heap_every_warehouse_pick", "struct heap_every_warehouse_pick {};", "global per-pick ordering violates zone-head ownership"),
    "pairing-heap-meld": ("array_binary_snow_heap", "struct array_binary_snow_heap {};", "array rebuilding replaces pointer-splice pairing meld"),
    "leftist-heap-meld": ("rankless_pairing_ticket_heap", "struct rankless_pairing_ticket_heap {};", "a rankless pairing heap omits leftist null-path ranks"),
    "price-level-book": ("heap_each_auction_order", "struct heap_each_auction_order {};", "per-order heap nodes erase price-level FIFO ownership"),
    "srpt-preemptive-heap": ("stateless_shortest_job_pop", "struct stateless_shortest_job_pop {};", "stateless pop omits the running/preemption state machine"),
    "circular-calendar-queue": ("ordered_absolute_day_tree", "struct ordered_absolute_day_tree {};", "an ordered day tree bypasses circular horizon buckets"),
    "min-max-heap": ("two_independent_parcel_heaps", "struct two_independent_parcel_heaps {};", "duplicated min/max heaps violate the single alternating-level structure"),
    "adjacent-gap-candidate-heap": ("scan_all_player_pairs", "struct scan_all_player_pairs {};", "all-pairs scanning replaces adjacent-gap candidates"),
    "lazy-versioned-heap": ("eager_rebuild_reclaimer", "struct eager_rebuild_reclaimer {};", "eager rebuilding omits versioned stale snapshots"),
    "winner-tournament-tree": ("conference_binary_heap", "struct conference_binary_heap {};", "a binary heap replaces fixed leaves and path-only updates"),
    "binomial-heap-union": ("degree_free_alert_forest", "struct degree_free_alert_forest {};", "a degree-free forest omits binomial carry uniqueness"),
    "skill-partitioned-indexed-heaps": ("global_filtered_crew_heap", "struct global_filtered_crew_heap {};", "one filtered heap violates per-skill ownership"),
    "bounded-top-k-min-heap": ("retain_all_then_rank", "struct retain_all_then_rank {};", "retain-all ranking omits bounded admission and eviction"),
    "weighted-fair-head-heap": ("global_static_event_score", "struct global_static_event_score {};", "static event scores omit per-stream virtual finish state"),
}
ORACLE_OPERATIONS = {
    "indexed-binary-max-heap": ("report", "revise", "cancel", "dispatch_next"),
    "four-ary-ready-heap": ("add_job", "complete_dependency", "start_next"),
    "tiered-fifo-buckets": ("join", "change_tier", "withdraw", "promote_next"),
    "weighted-two-lane-cycle": ("submit", "cancel", "route_next"),
    "aging-acuity-buckets": ("admit", "advance_minutes", "discharge", "select_next"),
    "monotone-radix-heap": ("schedule", "take_due"),
    "heap-of-zone-heads": ("add_pick", "dispatch_next"),
    "pairing-heap-meld": ("report", "merge_districts", "assign_next"),
    "leftist-heap-meld": ("open", "escalate", "meld_queues", "take_next"),
    "price-level-book": ("place", "cancel", "match_next"),
    "srpt-preemptive-heap": ("submit", "start_or_preempt", "consume", "finish_current"),
    "circular-calendar-queue": ("schedule", "advance_to", "take_due"),
    "min-max-heap": ("accept", "dispatch_earliest", "remove_latest"),
    "adjacent-gap-candidate-heap": ("join", "leave", "make_match"),
    "lazy-versioned-heap": ("track", "rescore", "set_pinned", "reclaim_next"),
    "winner-tournament-tree": ("set_room_candidate", "clear_room", "prepare_next", "winner_room"),
    "binomial-heap-union": ("report", "merge_feeds", "investigate_next", "investigate_batch"),
    "skill-partitioned-indexed-heaps": ("open", "reprioritize", "close", "assign_next"),
    "bounded-top-k-min-heap": ("consider", "remove", "cutoff", "ranked"),
    "weighted-fair-head-heap": ("set_weight", "report", "take_next"),
}
DETAILS = {
    "indexed-binary-max-heap": "Incidents use positive unique IDs, nonnegative severity/deadline, severity descending, deadline ascending, then immutable admission sequence. Revision preserves sequence; cancellation and dispatch remove exactly once.",
    "four-ary-ready-heap": "Jobs use positive unique IDs, nonnegative priority/dependency count, and positive duration. Blocked jobs become ready exactly when their dependency count reaches zero; ready order is priority descending, duration ascending, then ID.",
    "tiered-fifo-buckets": "Passenger IDs are positive and unique and tiers are 0..3. Promotion chooses the highest tier and FIFO order within the latest joined tier; a tier change appends to the new tier and invalidates the old ticket.",
    "weighted-two-lane-cycle": "Positive unique print IDs enter urgent or normal FIFO lanes. Routing repeats urgent, urgent, normal and skips unavailable/cancelled work without returning an ID twice.",
    "aging-acuity-buckets": "Positive unique patient IDs have acuity 1..5. Time advances by a nonnegative delta; every complete ten waiting minutes raises effective acuity by one up to five. Selection uses effective acuity then waiting order.",
    "monotone-radix-heap": "Retry IDs are positive and unique. Deadlines may not precede the last popped deadline. take_due(limit) returns the minimum deadline only when it is within limit; equal deadlines use smaller ID.",
    "heap-of-zone-heads": "Picks use positive unique IDs, nonnegative zone/cutoff, and FIFO order inside each zone. Globally, only each zone head competes: smaller cutoff then smaller zone wins.",
    "pairing-heap-meld": "District and hazard are nonnegative and segment IDs positive/unique. Higher hazard then smaller ID wins. Merging distinct districts empties the source without copying or losing nodes.",
    "leftist-heap-meld": "Queue and risk are nonnegative and ticket IDs positive/unique. Higher risk then smaller ID wins. Melding distinct queues empties the source while preserving leftist null-path ranks.",
    "price-level-book": "Orders have positive unique IDs, price, and quantity. Highest price wins; equal-price orders are FIFO. Cancellation is lazy but exact, and empty price levels disappear.",
    "srpt-preemptive-heap": "Jobs have positive unique IDs and remaining work. Scheduling chooses the smallest remaining work then ID and may preempt the running job. Consumption is positive and cannot exceed remaining; only zero-remaining work may finish.",
    "circular-calendar-queue": "Backup IDs are positive/unique. Days never precede current time and admission is limited to 31 days ahead. Time advances monotonically and due work is FIFO by absolute day across circular wraparound.",
    "min-max-heap": "Capacity is positive; parcel IDs are positive/unique and windows nonnegative. Even levels maintain minima and odd levels maxima; smaller window then ID defines the minimum and the reverse defines the maximum.",
    "adjacent-gap-candidate-heap": "Players have positive unique IDs and nonnegative ratings. A match removes the adjacent rating pair with minimum gap; ties use the pair whose later admission is earlier, then IDs.",
    "lazy-versioned-heap": "Blocks have positive unique IDs and nonnegative scores. Higher score then smaller ID wins. Rescore and pin-state changes invalidate old snapshots; pinned blocks remain tracked but cannot be reclaimed.",
    "winner-tournament-tree": "Room count is positive. Room candidates have positive IDs and nonnegative readiness/deadline. Higher readiness, earlier deadline, then smaller room wins; preparation clears only the winning leaf.",
    "binomial-heap-union": "Feed and risk are nonnegative and alert IDs positive/unique. Higher risk then smaller ID wins. Merging distinct feeds empties the source and preserves one root per binomial degree.",
    "skill-partitioned-indexed-heaps": "Work IDs are positive/unique and skill, impact, and due nonnegative. Assignment considers only the requested skill, ordered by impact descending, due ascending, then ID; reprioritization never changes skill.",
    "bounded-top-k-min-heap": "K is positive. Results have positive unique IDs and nonnegative scores. Retain only the K best by score descending then ID ascending; a noncompetitive candidate returns false. ranked() returns retained results in that order.",
    "weighted-fair-head-heap": "Streams are nonnegative, event IDs positive/unique, and weights/costs positive. Each stream is FIFO; active stream heads compete by fixed-point virtual finish then stream ID. Weight changes affect future reports only.",
}


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(priority_queue_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_library(task_solution STATIC "${TASK_SOURCE}")
target_include_directories(task_solution PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
add_executable(task_visible task_visible_test.cpp)
add_executable(task_hidden .meta/task_hidden_test.cpp)
foreach(target task_solution task_visible task_hidden)
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
target_link_libraries(task_visible PRIVATE task_solution)
target_link_libraries(task_hidden PRIVATE task_solution)
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_custom_target(test_task ALL DEPENDS task_visible task_hidden COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure)
'''


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _source_hash() -> str:
    paths = (Path(__file__), Path(__file__).with_name("moonlight_priority_queue_cases.py"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _file_hash(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _family_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for case in CASES:
        digest.update(case.task_id.encode() + b"\0" + _tree_hash(root / case.task_id).encode())
    return f"sha256:{digest.hexdigest()}"


def _remedy_markdown(case: Case) -> str:
    _, _, negative = NEGATIVE_PROFILES[case.mechanism]
    operations = ", ".join(f"`{name}`" for name in ORACLE_OPERATIONS[case.mechanism])
    return f"""## Identity
Legacy `{case.task_id}`; disposition `replace`; clean-room family `{FAMILY_ID}`.

## Objective
{case.contract} The replacement must be materially distinct in logic and implementation from every sibling root, not merely renamed.

## Public API
The exact editable C++17 declaration is:

```cpp
{case.header.rstrip()}
```

## Behavior table
{DETAILS[case.mechanism]}

## Implementation invariant
Required mechanism: `{case.mechanism}`. Required structural evidence: {', '.join(f'`{token}`' for token in case.required_tokens)}. The per-root rejected substitute is: {negative}.

## Starter and reference
The owner writes a compiling API-complete stub to `task.cpp` and a clean-room full reference to `.meta/example.cpp`; both use the exact public header.

## Tests
The visible contract test is complemented by an independent deterministic value-model trace covering {operations}. After every operation, the trace compares return values, complete observable removal order from a copied structure, counts/accessors, and the representation invariant. `.meta/negative_fixture.cpp` executes this root's mechanism-specific rejection path.

## Files and metadata
Editable files are the task-named header/source pair after materialization. Tests, examples, provenance, the negative fixture, and CMake scaffold are private roles and excluded from the prompt.

## Build/oracle
Use `{LOCKED_IMAGE}` with Docker network `none`. Configure fresh `Unix Makefiles` normal and ASan/UBSan builds with the locked compiler, build both visible and hidden targets, require positive equal discovery counts, and execute both suites.

## Family/contamination
The owner enforces 20 one-to-one task/mechanism/oracle/negative-fixture profiles, pairwise semantic screening, whole-slug official benchmark exclusion, and normalized content comparison against the bound 26-root holdout.

## Optional dataset handoff
Not requested. Completion ends at `local_family_verified`; no JSONL, split, export, or consumer claim is made.

## Acceptance
Accept only when generator-owned regeneration, prompt/role checks, all 20 independent traces and negative fixtures, clean normal plus fresh sanitizer Docker execution, contamination screening, and hash-bound receipt validation all pass.
"""


def _write_remedy_specs(out: Path, force: bool) -> None:
    remedy = out / ".state" / "remedy"
    for case in CASES:
        markdown = _remedy_markdown(case)
        legacy = LEGACY_OUT / case.task_id
        record = {
            "schema_version": "aider-task-remedy-v1", "task_id": case.task_id,
            "disposition": "replace", "family_id_before": "aider-dsa-priority-queue-v1",
            "family_id_after": FAMILY_ID, "mechanism": case.mechanism,
            "finding_ids": ["PQ-F1", "PQ-F2", "PQ-F3", "PQ-F4", "PQ-F5", "PQ-F6"],
            "generator_path": "src/w8_biayn/integrations/moonlight_priority_queue_aider_tasks.py",
            "generator_revision": _source_hash(), "status": "designed",
            "oracle_status": "not_run", "benchmark_screen": "not_run",
            "duplicate_family_screen": "not_run", "prompt_boundary": "not_run",
            "reference_mapping": "not_run", "primary_core_objective": "specified",
            "tree_hash_before": _tree_hash(legacy) if legacy.is_dir() else "not_available",
            "remedy_spec_hash": _file_hash_from_text(markdown),
        }
        _write(remedy / f"{case.task_id}.md", markdown, force)
        _write(remedy / f"{case.task_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", force)


def _sync_remedy_records(out: Path, *, status: str | None = None, oracle_status: str | None = None) -> None:
    remedy = out / ".state" / "remedy"
    if not remedy.is_dir():
        return
    for case in CASES:
        md = remedy / f"{case.task_id}.md"
        record_path = remedy / f"{case.task_id}.json"
        if not md.is_file() or not record_path.is_file():
            raise RuntimeError(f"remedy_spec_incomplete: {case.task_id}")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["remedy_spec_hash"] = f"sha256:{hashlib.sha256(md.read_bytes()).hexdigest()}"
        record["generator_revision"] = _source_hash()
        if (out / case.task_id).is_dir():
            record["tree_hash_after"] = _tree_hash(out / case.task_id)
        if status is not None:
            record["status"] = status
            if status in {"core_verified", "local_family_verified"}:
                record.update({
                    "benchmark_screen": "pass", "duplicate_family_screen": "pass",
                    "prompt_boundary": "pass", "reference_mapping": "pass",
                    "primary_core_objective": "achieved",
                })
        if oracle_status is not None:
            record["oracle_status"] = oracle_status
            if oracle_status == "locked_normal_sanitizer_verified":
                record["oracle_evidence"] = {
                    "receipt": ".state/oracle-receipt.json", "normal_discovered_tests": 2,
                    "sanitizer_discovered_tests": 2, "image": LOCKED_IMAGE,
                    "family_hash": _family_hash(out),
                }
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _write_remedy_specs(out, force)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        config = {
            "authors": ["w8-biayn"],
            "blurb": f"Implement {case.mechanism} for a domain-specific priority system.",
            "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]},
        }
        provenance = {
            "curriculum_document": CURRICULUM, "audit_specification": AUDIT_SPEC,
            "curriculum_task_id": case.task_id, "origin": "clean-room repository-authored v2 replacement",
            "status": "local task artifact; not admitted SFT data", "version": 2,
            "family_id": FAMILY_ID, "semantic_profile": case.mechanism,
            "benchmark_separation": "Independent local contract; no official benchmark wording, API, tests, or reference was used.",
        }
        files = {
            ".docs/introduction.md": f"# {case.class_name}\n\nA clean-room C++17 priority-structure task using `{case.mechanism}`.\n",
            ".docs/instructions.md": f"# Instructions\n\nImplement the complete public API declared in the editable header. {DETAILS[case.mechanism]} Failed boolean mutations return `false` without changing observable state; empty selection returns `std::nullopt`. The substantive priority mechanism must be implemented directly: do not delegate to a library heap, sort the complete collection for each selection, or scan every retained item to choose the next result. `debug_valid_heap()` must validate the representation invariant described by this contract.\n",
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f"[visible]\ndescription = \"public {case.mechanism} behavior and invalid-input contract\"\n\n[hidden]\ndescription = \"adversarial mutations, representation invariant, randomized trace, and sanitizer execution\"\n",
            "task.h": case.header, "task.cpp": case.starter,
            ".meta/example.h": case.header, ".meta/example.cpp": case.reference,
            "task_visible_test.cpp": case.visible, ".meta/task_hidden_test.cpp": case.hidden,
            ".meta/negative_fixture.cpp": _negative_fixture(case),
            "CMakeLists.txt": _cmake(),
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    _sync_remedy_records(out)
    return tuple(roots)


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


def _code_only(source: str) -> str:
    source = re.sub(r"//.*?$|/\*.*?\*/", "", source, flags=re.MULTILINE | re.DOTALL)
    source = re.sub(r'"(?:\\.|[^"\\])*"', '""', source)
    return re.sub(r"'(?:\\.|[^'\\])*'", "''", source)


def _negative_fixture(case: Case) -> str:
    _, body, description = NEGATIVE_PROFILES[case.mechanism]
    return f'''#include "task.h"
// Deliberately rejected substitute: {description}.
namespace rejected_substitute {{ {body} }}
'''


def _validate_reference(case: Case, source: str) -> None:
    code = _code_only(source)
    for token in FORBIDDEN_CORE:
        if token in code:
            _fail("forbidden_core_substitute", f"{case.task_id}: {token}")
    profile_token, _, description = NEGATIVE_PROFILES[case.mechanism]
    if profile_token in code:
        _fail("forbidden_mechanism_substitute", f"{case.task_id}: {description}")
    marker = f"mechanism:{case.mechanism}"
    if marker not in source:
        _fail("invariant_not_enforced", f"{case.task_id}: missing mechanism marker")
    for token in case.required_tokens:
        if token not in code:
            _fail("invariant_not_enforced", f"{case.task_id}: missing {token}")


def _assert_negative_fixture_rejected(case: Case, source: str) -> str:
    try:
        _validate_reference(case, source)
    except RuntimeError as error:
        if not str(error).startswith(f"forbidden_mechanism_substitute: {case.task_id}:"):
            raise
        return "forbidden_mechanism_substitute"
    _fail("negative_fixture_not_rejected", case.task_id)


def _validate_oracle(case: Case) -> str:
    hidden = _code_only(case.hidden)
    if "snapshot" not in hidden or ("model" not in hidden and "waiting" not in hidden) or "std::uint32_t state" not in hidden:
        _fail("independent_oracle_incomplete", case.task_id)
    for operation in ORACLE_OPERATIONS[case.mechanism]:
        if f"q.{operation}(" not in hidden and f"probe.{operation}(" not in hidden:
            _fail("independent_oracle_incomplete", f"{case.task_id}: missing {operation}")
    if ("while" not in hidden and "for(;;)" not in hidden) or "debug_valid_heap" not in hidden:
        _fail("complete_observable_order_missing", case.task_id)
    return _file_hash_from_text(case.hidden)


def _file_hash_from_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


def _semantic_screen() -> tuple[dict[str, str], float]:
    if len(CASES) != 20 or len({c.task_id for c in CASES}) != 20 or len({c.mechanism for c in CASES}) != 20:
        _fail("duplicate_family", "task IDs and mechanisms must be one-to-one across 20 roots")
    signatures: dict[str, str] = {}
    token_sets: dict[str, set[str]] = {}
    oracle_hashes: set[str] = set()
    for case in CASES:
        _validate_reference(case, case.reference)
        oracle_hash = _validate_oracle(case)
        if oracle_hash in oracle_hashes:
            _fail("duplicate_family", f"duplicate oracle: {case.task_id}")
        oracle_hashes.add(oracle_hash)
        payload = "\n".join((case.mechanism, DETAILS[case.mechanism], case.header, case.reference, case.visible, case.hidden))
        signature = hashlib.sha256(payload.encode()).hexdigest()
        if signature in {value.removeprefix("sha256:") for value in signatures.values()}:
            _fail("duplicate_family", case.task_id)
        signatures[case.task_id] = f"sha256:{signature}"
        token_sets[case.task_id] = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\d+", payload.lower()))
    maximum = 0.0
    ids = sorted(token_sets)
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            a, b = token_sets[left], token_sets[right]
            score = len(a & b) / max(1, len(a | b))
            maximum = max(maximum, score)
            if score >= 0.86:
                _fail("duplicate_family", f"{left} and {right} token Jaccard {score:.3f}")
    return signatures, maximum


def _semantic_ngrams(text: str, domain_names: Sequence[str] = ()) -> set[str]:
    text = re.sub(r"//.*?$|/\*.*?\*/", "", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '"S"', text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "'C'", text)
    text = re.sub(r"\b\d+(?:[uUlL]+)?\b", "N", text)
    for name in sorted(domain_names, key=len, reverse=True):
        if name:
            text = re.sub(rf"\b{re.escape(name)}\b", "TYPE", text, flags=re.IGNORECASE)
    tokens = re.findall(r"(?:[A-Za-z_]\w*|==|!=|<=|>=|->|&&|\|\||\S)", text)
    return {" ".join(tokens[index:index + 5]) for index in range(max(0, len(tokens) - 4))}


def _holdout_semantic_screen() -> dict[str, object]:
    if not BENCHMARK_MANIFEST.is_file() or not BOUND_HOLDOUT_ROOT.is_dir():
        return {"status": "not_completed", "reason": "bound 26-root holdout content unavailable"}
    holdout_ids = set(json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))["task_ids"])
    signatures: dict[str, set[str]] = {}
    for task_id in sorted(holdout_ids):
        root = BOUND_HOLDOUT_ROOT / task_id
        if not root.is_dir():
            _fail("holdout_inventory_incomplete", task_id)
        texts = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".h", ".hpp", ".cpp", ".md", ".toml"}:
                continue
            if "catch" in path.name.lower() or path.name == "tests-main.cpp":
                continue
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
        domain = (task_id, task_id.replace("-", "_"), *(part for part in task_id.split("-") if len(part) > 3))
        signatures[task_id] = _semantic_ngrams("\n".join(texts), domain)
    strongest = {"candidate": None, "holdout": None, "overlap": 0.0}
    for case in CASES:
        if case.task_id in holdout_ids:
            _fail("benchmark_id_overlap", case.task_id)
        candidate = "\n".join((DETAILS[case.mechanism], case.header, case.reference, case.visible, case.hidden))
        domain = (case.class_name, case.task_id, case.task_id.replace("-", "_"), *(part for part in case.task_id.split("-") if len(part) > 3))
        candidate_ngrams = _semantic_ngrams(candidate, domain)
        for holdout, holdout_ngrams in signatures.items():
            overlap = len(candidate_ngrams & holdout_ngrams) / max(1, min(len(candidate_ngrams), len(holdout_ngrams)))
            if overlap > strongest["overlap"]:
                strongest = {"candidate": case.task_id, "holdout": holdout, "overlap": overlap}
            if overlap >= 0.90:
                _fail("benchmark_content_overlap", f"{case.task_id} ~ {holdout}: {overlap:.3f}")
    return {
        "status": "pass", "normalizer": "priority-queue-cleanroom-v1",
        "comparison": "normalized five-gram docs/API/source/tests",
        "holdout_count": len(signatures), "candidate_count": len(CASES),
        "strongest_overlap": {**strongest, "overlap": round(float(strongest["overlap"]), 6)},
    }


def _benchmark_screen(root: Path) -> None:
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in sorted(root.rglob("*")) if path.is_file())
    normalized = corpus.lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", normalized):
            _fail("benchmark_id_overlap", slug)
    for forbidden in ("aider-ai/polyglot", "exercism c++ exercise", "upstream polyglot benchmark"):
        if forbidden in normalized:
            _fail("benchmark_content_overlap", forbidden)


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
    records = {path.stem: path for path in remedy.glob("*.json")} if remedy.is_dir() else {}
    if set(records) != {case.task_id for case in CASES}:
        _fail("remedy_spec_incomplete", "one JSON record per legacy root is required")
    for case in CASES:
        record = json.loads(records[case.task_id].read_text(encoding="utf-8"))
        md = remedy / f"{case.task_id}.md"
        if record.get("task_id") != case.task_id or record.get("disposition") != "replace" or record.get("mechanism") != case.mechanism or not md.is_file():
            _fail("remedy_disposition_conflict", case.task_id)
        text = md.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", case.task_id)
        expected = f"sha256:{hashlib.sha256(md.read_bytes()).hexdigest()}"
        if record.get("remedy_spec_hash") != expected:
            _fail("remedy_spec_incomplete", f"stale hash for {case.task_id}")


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected 20 roots, got {len(actual)}")
    if require_remedy:
        _verify_remedy_records(out)
    with tempfile.TemporaryDirectory(prefix="priority-queue-v2-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for case in CASES:
            if _tree_hash(out / case.task_id) != _tree_hash(fresh / case.task_id):
                _fail("generator_output_drift", case.task_id)
    signatures, maximum_similarity = _semantic_screen()
    holdout_semantic = _holdout_semantic_screen()
    manifest_tasks = []
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta" / "config.json").read_text(encoding="utf-8"))
        roles = config.get("files")
        if not isinstance(roles, dict):
            _fail("reference_map_failed", case.task_id)
        solution = [_safe_relative(x) for x in roles.get("solution", [])]
        tests = [_safe_relative(x) for x in roles.get("test", [])]
        examples = [_safe_relative(x) for x in roles.get("example", [])]
        if len(solution) != 2 or len(examples) != 2 or len(set(solution)) != 2:
            _fail("reference_map_failed", case.task_id)
        if set(solution) & (set(tests) | set(examples)) or any(name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution):
            _fail("unsafe_path", case.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("reference_map_failed", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private = [*tests, *examples, "CMakeLists.txt", ".meta/provenance.json", ".meta/task_hidden_test.cpp", ".meta/negative_fixture.cpp"]
        if any(name in prompt for name in private):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer) is not None:
            _fail("target_reference_mismatch", case.task_id)
        missing = f"{task.editable_files[0]}\n```cpp\n// incomplete\n```\n"
        extra = answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n"
        prose = "explanation\n" + answer
        if any(_whole_format_code(root, response) != "whole_format_failed" for response in (missing, extra, prose)):
            _fail("whole_format_failed", case.task_id)
        _validate_reference(case, (root / ".meta" / "example.cpp").read_text(encoding="utf-8"))
        fixture = (root / ".meta" / "negative_fixture.cpp").read_text(encoding="utf-8")
        negative_code = _assert_negative_fixture_rejected(case, fixture)
        oracle_hash = _validate_oracle(case)
        _benchmark_screen(root)
        manifest_tasks.append({
            "task_id": case.task_id, "mechanism": case.mechanism, "tree_hash": _tree_hash(root),
            "semantic_signature": signatures[case.task_id], "oracle_hash": oracle_hash,
            "negative_fixture_hash": _file_hash(root / ".meta" / "negative_fixture.cpp"),
            "negative_fixture_rejection": negative_code,
        })
    manifest = {
        "schema_version": MANIFEST_SCHEMA, "family_id": FAMILY_ID, "task_count": len(manifest_tasks),
        "legacy_root": LEGACY_OUT.as_posix(), "legacy_preserved": LEGACY_OUT.is_dir(),
        "tasks": manifest_tasks, "maximum_pairwise_token_jaccard": round(maximum_similarity, 6),
        "holdout_semantic_screen": holdout_semantic,
        "screen": {"primary_core_objective": "pass", "prompt_boundary": "pass", "reference_mapping": "pass", "duplicate_family": "pass", "benchmark_contamination": "pass" if holdout_semantic["status"] == "pass" else "not_completed", "negative_fixture": "pass"},
    }
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "materialization-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _sync_remedy_records(out, status="core_verified")


def _count_discovered(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match:
        _fail("test_discovery_failed")
    count = int(match.group(1))
    if not count:
        _fail("zero_tests")
    return count


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    verify_core(out)
    receipts = []
    for case in CASES:
        root = out / case.task_id
        receipt: dict[str, object] = {"task_id": case.task_id, "tree_hash": _tree_hash(root), "modes": {}}
        with tempfile.TemporaryDirectory(prefix="priority-queue-v2-oracle-") as temporary:
            copied = Path(temporary) / case.task_id
            shutil.copytree(root, copied)
            reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                configure = ["cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={reference}", *flags]
                subprocess.run(configure, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                discovered = subprocess.run(["ctest", "--test-dir", str(build_dir), "-N"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                count = _count_discovered(discovered.stdout)
                executed = subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                receipt["modes"][name] = {"configure": configure, "discovered_tests": count, "ctest_output": executed.stdout}
        modes = receipt["modes"]
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        receipts.append(receipt)
    runtime = {
        "environment": os.environ.get("W8_BIAYN_ORACLE_RUNTIME", "host-prerequisite"),
        "image": os.environ.get("W8_BIAYN_ORACLE_IMAGE"),
        "compiler": subprocess.run(["c++", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0],
        "cmake": subprocess.run(["cmake", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0],
    }
    status = "local_family_verified" if runtime["image"] else "host_oracle_verified_locked_runtime_not_completed"
    path = out / ".state" / "oracle-receipt.json"
    path.write_text(json.dumps({"runtime": runtime, "status": status, "tasks": receipts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _sync_remedy_records(out, status=status, oracle_status="verified" if runtime["image"] else "host_verified_locked_not_completed")


def import_locked_result(out: Path, archive: Path, result: Path) -> None:
    """Import a direct network-disabled Docker result after archive/live validation."""
    archive_digest = f"sha256:{hashlib.sha256(archive.read_bytes()).hexdigest()}"
    with tempfile.TemporaryDirectory(prefix="priority-queue-locked-import-") as temporary:
        extracted = Path(temporary)
        with tarfile.open(archive, "r") as handle:
            members = handle.getmembers()
            if any(member.name.startswith("/") or ".." in Path(member.name).parts for member in members):
                _fail("unsafe_archive_path")
            handle.extractall(extracted, filter="data")
        archived_family = extracted / ".w8-biayn" / "data" / "aider-tasks-reverify" / "aider-dsa" / "priority-queue"
        if not archived_family.is_dir() or _family_hash(archived_family) != _family_hash(out):
            _fail("grader_mount_hash_mismatch")
        archived_owner = extracted / "src" / "w8_biayn" / "integrations" / "moonlight_priority_queue_aider_tasks.py"
        archived_cases = extracted / "src" / "w8_biayn" / "integrations" / "moonlight_priority_queue_cases.py"
        if not archived_owner.is_file() or not archived_cases.is_file():
            _fail("owner_archive_incomplete")
        if _file_hash(archived_owner) != _file_hash(Path(__file__)) or _file_hash(archived_cases) != _file_hash(Path(__file__).with_name("moonlight_priority_queue_cases.py")):
            _fail("owner_archive_hash_mismatch")
    fields: dict[str, str] = {}
    counts: dict[str, dict[str, int]] = {}
    task_meta: dict[str, tuple[str, str]] = {}
    commands: dict[str, dict[str, dict[str, str]]] = {}
    for line in result.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if parts[0] == "task" and len(parts) == 4:
            counts.setdefault(parts[1], {})[parts[2]] = int(parts[3])
        elif parts[0] == "task_meta" and len(parts) == 4:
            task_meta[parts[1]] = (parts[2], parts[3])
        elif parts[0] == "command" and len(parts) == 5:
            commands.setdefault(parts[1], {}).setdefault(parts[2], {})[parts[3]] = parts[4]
        elif len(parts) == 2:
            fields[parts[0]] = parts[1]
        else:
            _fail("locked_result_malformed", line)
    if fields.get("schema") != "aider-priority-queue-locked-v2" or fields.get("archive_sha256") != archive_digest:
        _fail("locked_result_archive_mismatch")
    if fields.get("image") != LOCKED_IMAGE or fields.get("network") != "none":
        _fail("locked_runtime_identity_mismatch")
    owner_hash = _file_hash(Path(__file__))
    cases_hash = _file_hash(Path(__file__).with_name("moonlight_priority_queue_cases.py"))
    if fields.get("owner_sha256") != owner_hash or fields.get("cases_sha256") != cases_hash:
        _fail("owner_runtime_hash_mismatch")
    expected = {case.task_id for case in CASES}
    if set(counts) != expected or set(task_meta) != expected or set(commands) != expected:
        _fail("locked_result_task_mismatch")
    receipts = []
    for case in CASES:
        root = out / case.task_id
        reference_hash = _file_hash(root / ".meta" / "example.cpp")
        if task_meta[case.task_id] != (_tree_hash(root), reference_hash):
            _fail("locked_task_hash_mismatch", case.task_id)
        modes = counts[case.task_id]
        if set(modes) != {"normal", "sanitizer"} or modes["normal"] <= 0 or modes["normal"] != modes["sanitizer"]:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        mode_receipts = {}
        for name, count in sorted(modes.items()):
            mode_commands = commands[case.task_id].get(name, {})
            if set(mode_commands) != {"configure", "build", "discover", "execute"}:
                _fail("locked_command_evidence_incomplete", f"{case.task_id}:{name}")
            if "Unix Makefiles" not in mode_commands["configure"] or "ctest --test-dir" not in mode_commands["discover"] or "ctest --test-dir" not in mode_commands["execute"]:
                _fail("locked_command_evidence_incomplete", f"{case.task_id}:{name}")
            if name == "sanitizer" and ("address,undefined" not in mode_commands["configure"] or "fno-omit-frame-pointer" not in mode_commands["configure"]):
                _fail("sanitizer_flags_missing", case.task_id)
            mode_receipts[name] = {"discovered_tests": count, "status": "pass", "commands": mode_commands}
        receipts.append({"task_id": case.task_id, "tree_hash": _tree_hash(root), "reference_sha256": reference_hash, "modes": mode_receipts})
    receipt = {
        "runtime": {"environment": "locked-docker-archive", "image": LOCKED_IMAGE, "network": "none", "compiler": fields.get("compiler"), "cmake": fields.get("cmake"), "designation": "locked_oracle"},
        "archive_sha256": archive_digest, "family_hash": _family_hash(out),
        "owner_files": {"materializer": owner_hash, "cases": cases_hash},
        "status": "local_family_verified", "tasks": receipts,
    }
    (out / ".state" / "oracle-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _sync_remedy_records(out, status="local_family_verified", oracle_status="locked_normal_sanitizer_verified")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--import-locked-result", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.import_locked_result:
        if args.archive is None:
            parser.error("--archive is required with --import-locked-result")
        import_locked_result(args.out, args.archive, args.import_locked_result)
    print(f"Wrote {len(roots)} priority-queue v2 tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
