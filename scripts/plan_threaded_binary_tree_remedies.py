#!/usr/bin/env python3
"""Freeze legacy threaded-tree audit inputs and write planned remedy records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from w8_biayn.integrations.moonlight_threaded_binary_tree_cases import (
    NEGATIVE_MUTATIONS,
)


LEGACY = Path(".w8-biayn/data/aider-tasks/aider-dsa/threaded-binary-tree")
OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/threaded-binary-tree")
OWNER = Path("src/w8_biayn/integrations/moonlight_threaded_binary_tree_aider_tasks.py")
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY = "aider-dsa-threaded-binary-tree-v3-hard-rule"

# Legacy ID, disposition, remediated ID, public declaration summary, logic tag.
CASES = (
    ("threaded-appointment-book", "repair-in-place", "threaded-appointment-book", "bool reserve(int); bool release(int); optional<int> before(int) const; optional<int> at_or_after(int) const; vector<int> schedule() const", "direct-double-threaded-mutation"),
    ("threaded-auction-bids", "replace", "threaded-bid-multiplicity-index", "bool place(int); bool withdraw(int); size_t count(int) const; optional<int> next_level(int) const; vector<pair<int,size_t>> levels() const", "multiplicity-nodes-and-distinct-level-threads"),
    ("threaded-audit-browser", "replace", "threaded-audit-tombstone-index", "bool append(int); bool redact(int); bool restore(int); optional<int> next_live(int) const; vector<int> live_records() const; size_t compact()", "lazy-tombstones-and-threaded-compaction"),
    ("threaded-calendar-navigator", "replace", "threaded-calendar-cursor", "bool add(int); bool cancel(int); bool seek(int); optional<int> next(); optional<int> previous(); optional<int> current() const", "stateful-thread-cursor-with-delete-fallback"),
    ("threaded-cargo-manifest", "replace", "threaded-cargo-interval-tree", "bool add(int,int,int); bool remove(int); vector<int> overlapping(int,int) const; vector<int> cargo_order() const", "augmented-interval-max-end-threaded-search"),
    ("threaded-document-anchors", "replace", "threaded-anchor-rank-tree", "bool add(int); bool remove(int); optional<int> select(size_t) const; size_t rank(int) const; vector<int> anchors() const", "subtree-cardinality-rank-select"),
    ("threaded-fare-tiers", "replace", "threaded-fare-prefix-tree", "bool set(int,int); bool erase(int); optional<long long> prefix_total(int) const; optional<int> lower_bound_total(long long) const", "subtree-sum-prefix-selection"),
    ("threaded-file-version-browser", "replace", "threaded-version-access-index", "bool retain(int); bool discard(int); bool access(int); optional<int> most_accessed() const; vector<pair<int,size_t>> versions() const", "per-node-access-count-and-threaded-tie-scan"),
    ("threaded-flight-departures", "replace", "threaded-departure-day-index", "bool schedule(int,int); bool cancel(int); optional<int> next_gate(int,int) const; vector<int> departures() const", "time-ordered-payload-filtered-thread-scan"),
    ("threaded-inventory-catalog", "replace", "threaded-catalog-stock-index", "bool add(int,int); bool restock(int,int); bool consume(int,int); bool erase_empty(int); optional<int> next_in_stock(int) const", "stock-payload-transitions-and-filtered-successor"),
    ("threaded-library-shelves", "replace", "threaded-shelf-bulk-builder", "bool rebuild(const vector<int>&); vector<int> forward() const; vector<int> reverse() const; int height() const", "linear-balanced-build-and-thread-overlay"),
    ("threaded-medication-times", "replace", "threaded-dose-range-pruner", "bool schedule(int); size_t cancel_between(int,int); vector<int> doses() const; vector<int> reverse_doses() const", "successor-driven-direct-range-erasure"),
    ("threaded-museum-waypoints", "replace", "threaded-waypoint-split-tree", "bool add(int); pair<vector<int>,vector<int>> split_snapshot(int) const; bool erase_side(int,bool); vector<int> tour() const", "thread-boundary-pivot-split"),
    ("threaded-network-ports", "replace", "threaded-port-gap-tree", "bool reserve(int); bool release(int); optional<int> first_free(int,int) const; vector<pair<int,int>> reserved_runs() const", "thread-gap-and-run-detection"),
    ("threaded-parking-space-guide", "replace", "threaded-space-state-tree", "bool define(int); bool occupy(int); bool vacate(int); optional<int> next_free(int) const; vector<int> free_spaces() const", "payload-state-filtered-thread-scan"),
    ("threaded-route-stations", "replace", "threaded-station-rekey-tree", "bool open(int); bool close(int); bool rekey(int,int); vector<int> stations() const", "atomic-key-replacement-with-thread-repair"),
    ("threaded-score-history", "replace", "threaded-score-thread-auditor", "bool add(int); bool corrupt_successor_for_test(int); optional<int> first_broken_thread() const; bool repair_threads(); vector<int> scores() const", "independent-child-inorder-thread-audit-and-repair"),
    ("threaded-sensor-thresholds", "replace", "threaded-threshold-hysteresis-tree", "bool add(int,int); bool erase(int); optional<int> transition(int); optional<int> active_band() const; vector<int> thresholds() const", "stateful-hysteresis-transition-over-threads"),
    ("threaded-ticket-browser", "replace", "threaded-ticket-priority-tree", "bool open(int,int); bool reprioritize(int,int); bool resolve(int); optional<int> next_ticket() const; vector<int> queue() const", "composite-priority-order-and-rekey"),
    ("threaded-transit-service", "replace", "threaded-service-wrap-tree", "bool add(int); bool cancel(int); optional<int> next_wrapped(int) const; optional<int> previous_wrapped(int) const; vector<int> day_order() const", "cyclic-boundary-thread-view"),
)

BEHAVIORS = {
    "threaded-appointment-book": "`reserve(k)` accepts a unique positive key; `release(k)` removes only an existing key; predecessor is strict and lower-bound is inclusive; empty navigation returns null; all failures are atomic.",
    "threaded-auction-bids": "`place(k)` accepts positive keys and increments an existing node count; `withdraw(k)` decrements then deletes at zero; absent withdrawal fails; `next_level(k)` is strictly greater; levels are ascending with counts.",
    "threaded-audit-browser": "`append(k)` accepts a unique positive key; redaction/restoration toggle only existing records and reject repeated state; live navigation skips tombstones; compaction physically deletes every tombstone and returns its count.",
    "threaded-calendar-navigator": "Adds are positive and unique; seek selects only an existing event; next/previous move strictly along threads; canceling the cursor selects successor then predecessor; boundary movement returns null without changing the cursor.",
    "threaded-cargo-manifest": "Cargo IDs are unique positive integers; intervals require `start <= end`; remove requires an existing ID; overlap is closed-interval intersection ordered by start then ID; max-end augmentation prunes nonoverlapping subtrees.",
    "threaded-document-anchors": "Anchors are unique positive offsets; rank is the number of stored offsets strictly below the query; zero-based select returns null out of range; deletion repairs counts and threads; empty rank is zero.",
    "threaded-fare-tiers": "Tier keys are positive and unique; fare values are nonnegative and `set` updates an existing node; prefix sums include keys at or below the query; lower-bound-total returns the first tier reaching the positive target and null otherwise; checked sums reject overflow atomically.",
    "threaded-file-version-browser": "Versions are positive and unique; access increments a node-local counter; most-accessed scans inorder threads and breaks ties by smaller version; checked counter overflow and absent access/discard fail atomically.",
    "threaded-flight-departures": "Departure minutes are unique in `[0,1439]` and gates are positive; schedule/cancel are atomic; next-gate scans at-or-after the cursor for the requested gate without wrapping; output is chronological.",
    "threaded-inventory-catalog": "SKUs are unique positive keys and stock is nonnegative; restock/consume are checked and atomic; only zero-stock nodes may be erased; next-in-stock is inclusive and skips empty payloads through successor threads.",
    "threaded-library-shelves": "Rebuild accepts only a strictly increasing positive vector and is atomic on invalid input; it creates a minimum-height balanced child topology and both thread directions; empty input clears the tree; forward/reverse are exact inverses.",
    "threaded-medication-times": "Dose minutes are unique in `[0,1439]`; reversed ranges cancel nothing; inclusive range cancellation follows successor threads while deleting each matching node directly; it returns the removed count and preserves remaining order.",
    "threaded-museum-waypoints": "Waypoints are unique positive keys; split snapshots partition strictly below pivot versus at-or-above pivot; `erase_side` deletes exactly one partition chosen by the flag and reports whether anything changed; empty partitions are valid.",
    "threaded-network-ports": "Ports are unique in `[1,65535]`; first-free validates an inclusive range and returns its lowest unreserved port; reserved runs coalesce only consecutive ports; invalid ranges and absent release are atomic failures.",
    "threaded-parking-space-guide": "Positive space IDs are defined once; occupy/vacate require the opposite current state; `next_free(k)` is inclusive and skips occupied payloads through successor threads; free-space output is ascending; empty queries return null.",
    "threaded-route-stations": "Station codes are unique positive keys; rekey requires an existing old key and unused new key, validates first, then replaces it through direct erase/insert thread repair; equal rekey succeeds without mutation; close absent fails.",
    "threaded-score-history": "Scores are unique positive keys; the test-only corruption changes one successor thread only; audit derives expected inorder from child edges and returns the first mismatched key; repair restores every thread without changing child topology or keys.",
    "threaded-sensor-thresholds": "Each positive band key has a nonnegative hysteresis width; transition selects the greatest threshold not above the reading but retains the active band while reading remains inside its hysteresis interval; absent/invalid mutations fail atomically.",
    "threaded-ticket-browser": "Ticket IDs are unique positive integers and severity is nonnegative; order is severity descending then ID ascending; reprioritize atomically detaches/reinserts the same node; next ticket is the threaded minimum composite key; resolving absent IDs fails.",
    "threaded-transit-service": "Service minutes are unique in `[0,1439]`; wrapped next is the first at-or-after the cursor or the day minimum; wrapped previous is the last at-or-before the cursor or day maximum; empty queries return null and cancellation is atomic.",
}


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def remedy_markdown(legacy_id: str, disposition: str, task_id: str, declarations: str, logic_tag: str) -> str:
    return f"""# Remedy specification: {legacy_id}

## Identity

Task ID: `{legacy_id}`. Task-spec revision: 3. Family ID: `{FAMILY}`. Disposition: `{disposition}`. Remediated task ID: `{task_id}`. Source inventory ID: `legacy-threaded-binary-tree-20`. License result: pass (repository-authored clean-room material). Generator: `{OWNER}`. Benchmark screen: pending semantic screen; official `binary-search-tree` is a permanent holdout. Selected prompt: `{PROMPT}`.

## Objective

Implement and deterministically test the threaded-tree capability `{logic_tag}`. Child links and inorder predecessor/successor threads must be distinct observable implementation state; output vectors are observations only.

## Public API

C++17 namespace `curriculum`; editable order `{task_id}.h`, `{task_id}.cpp`. Public declarations: `{declarations}`. The generated header gives the exact class and value types. The class owns its nodes and is non-copyable.

## Behavior table

{BEHAVIORS[legacy_id]} Invalid, duplicate, absent, empty, ordering, tie, range, and overflow behavior not applicable to this API is explicitly `not_applicable`. Boundary example: an operation naming absent key `999` on an empty instance fails or returns `std::nullopt` without mutation.

## Implementation invariant

Heap-owned nodes distinguish real children from threads with explicit left/right thread markers. Real-child traversal is acyclic and ordered; every left thread names the inorder predecessor or null and every right thread names the inorder successor or null. `{logic_tag}` is mandatory. Forbidden substitutes: authoritative `std::set`, `std::map`, sorted vector/list/deque storage, full-tree rebuild for a single-key mutation, hard-coded traces, or a degenerate unthreaded BST.

## Starter and reference

The header exposes the complete API and private node state; the source is a coherent incomplete implementation. The independent reference directly implements `{logic_tag}` and repairs affected adjacent threads during mutation. It does not import the legacy renderer, benchmark assets, or a banned authoritative container.

## Tests

Visible tests cover the public transition and boundary example. Private tests cover empty/singleton/extreme nodes, thread/child combinations, task-specific failure atomicity, forward/reverse agreement, and a deterministic trace. The private topic-specific false implementation is `{NEGATIVE_MUTATIONS[task_id][2]}`. It must compile under the ordinary strict flags, discover the same two tests as the reference, execute them, and be rejected. The separate `legacy-rebuild-template` structural control must fail `invariant_not_enforced`; the real emitted-artifact family screen must reject domain/identifier-renamed, constants-or-policy-only, and opposite-end-selection clones through `duplicate_family`.

## Files and metadata

Solutions: `{task_id}.h`, `{task_id}.cpp`; tests: `task_visible_test.cpp`, `.meta/task_hidden_test.cpp`; references: `.meta/example.h`, `.meta/example.cpp`; private negative evidence: `.meta/negative_fixture.cpp`, `.meta/negative_fixture.json`; private support: `test/catch.hpp`, `test/tests-main.cpp`; plus `.docs`, `.meta/config.json`, `.meta/provenance.json`, `.meta/tests.toml`, and `CMakeLists.txt`. Reference mapping is header-to-header and source-to-source in solution order. Provenance binds curriculum/spec/prompt/owner hashes and content-addressed Catch support. Neither negative file is prompt-visible or declared editable.

## Build/oracle

C++17, explicit Unix Makefiles and locked compiler in network-disabled `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`. Run separate clean normal and fresh `-fsanitize=address,undefined -fno-omit-frame-pointer` builds. Expected discovery is two positive CTest entries in each mode. Receipts bind tree/reference/owner/image/compiler/CMake/Catch/commands/network policy.

## Family/contamination

Compare actual emitted docs, public API, owned state/algorithm, mutation/selection rules, invalid/boundary behavior, reference control flow, deterministic oracle, and topic negative fixture against every other remediated root with normalizer `aider-threaded-tree-artifact-semantics-v3`. All seven dimensions must differ for every one of the 190 unordered pairs. Compare the primary artifacts against all 26 bound official C++ holdouts. `{logic_tag}` is the independent family decision. Whole-slug, semantic overlap, a missing dimension, or any required adversarial clone that survives rejects the root.

## Optional dataset handoff

`not_requested`. No renderer row, token/mask evidence, split, producer verification, export, consumer verification, training, or release claim is part of this workflow.

## Acceptance

Run the focused pytest, owner `--verify-core`, owner host verifier for iteration, and the network-disabled Docker verifier. Require prompt/role/reference pass, `legacy-rebuild-template -> invariant_not_enforced`, all seven dimensions across all 190 pairs, executed rejection of all three required emitted adversarial clones, all-26 holdout pass, equal positive normal/sanitizer discovery, and twenty strictly compiling topic negatives rejected by the same discovered tests. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `hard_rule_pair_not_distinct`, `negative_fixture_ambiguous`, `negative_fixture_not_rejected`, `benchmark_content_overlap`, `generator_output_drift`, and `sanitizer_test_count_mismatch`.
"""


def main() -> int:
    if not LEGACY.is_dir():
        raise SystemExit(f"missing legacy family: {LEGACY}")
    actual = {path.name for path in LEGACY.iterdir() if path.is_dir()}
    expected = {case[0] for case in CASES}
    if actual != expected:
        raise SystemExit(f"legacy inventory mismatch: {sorted(actual ^ expected)}")
    remedy = OUT / ".state" / "remedy"
    remedy.mkdir(parents=True, exist_ok=True)
    owner_hash = digest_bytes(OWNER.read_bytes())
    for legacy_id, disposition, task_id, declarations, logic_tag in CASES:
        markdown = remedy_markdown(legacy_id, disposition, task_id, declarations, logic_tag)
        md_path = remedy / f"{legacy_id}.md"
        md_path.write_text(markdown, encoding="utf-8")
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": legacy_id,
            "remediated_task_id": task_id,
            "family_id_before": "aider-dsa-threaded-binary-tree-v1",
            "family_id_after": FAMILY,
            "tree_hash_before": tree_hash(LEGACY / legacy_id),
            "generator_path": str(OWNER),
            "generator_revision": owner_hash,
            "finding_ids": ["TBT-F1-template-duplicate", "TBT-F2-rebuild-deletion", "TBT-F3-current-evidence-gap"],
            "disposition": disposition,
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": str(md_path),
            "remedy_spec_hash": digest_bytes(markdown.encode()),
            "selected_prompt": PROMPT,
            "user_inputs": {"FAMILY_NAME": "threaded-binary-tree", "FAMILY_TYPE": "aider-dsa"},
            "primary_core_objective": "not_achieved",
            "status": "planned",
        }
        (remedy / f"{legacy_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"planned {len(CASES)} remedies under {remedy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
