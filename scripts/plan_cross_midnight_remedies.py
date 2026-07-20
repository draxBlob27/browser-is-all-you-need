#!/usr/bin/env python3
"""Freeze the pre-implementation remedy plan for cross-midnight intervals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks/aider-dates-and-clocks/cross-midnight-intervals"
REQUESTED_LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/cross-midnight-intervals"
OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/cross-midnight-intervals"
GENERATOR = "src/w8_biayn/integrations/moonlight_cross_midnight_aider_tasks.py"
GENERATOR_REVISION = "sha256:1d72b11bf007ab70fdc5d23b7ea82aaba394b84421d170699ec6db7cda64aee1"
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-text-grid-reshaping-cross-midnight-intervals-v2"
IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
REJECTED_TASK_IDS = frozenset({"sleep-interruption-ledger", "transit-entitlement-audit"})


@dataclass(frozen=True)
class Plan:
    legacy_id: str
    task_id: str
    objective: str
    public_api: str
    mechanism: str
    invalid_rule: str
    negative: str


PLANS = (
    Plan("midnight-parking-rate", "overnight-parking-ledger", "Split one wrapping visit over ordered tariff bands and produce an exact per-band charge ledger.", "ParkingLedger::price(Visit, vector<TariffBand>) -> ParkingCharge", "boundary-event sweep over an unwrapped visit with per-band accumulation", "invalid visit/band/rate or overlapping bands returns valid=false atomically; an empty visit costs zero", "a whole-visit single-rate shortcut"),
    Plan("midnight-security-patrol", "patrol-gap-union", "Union wrapping patrol spans inside a requested watch window and return maximal uncovered gaps.", "uncovered_watch(WatchWindow, vector<Patrol>) -> GapReport", "clip, sort, and merge unwrapped coverage before complement extraction", "invalid identifiers/endpoints or a zero watch window returns valid=false; touching patrols merge", "reporting one gap per input patrol rather than the complement of the union"),
    Plan("midnight-dock-allocation", "dock-booking-calendar", "Maintain per-dock overnight bookings with atomic conflict rejection and deterministic availability queries.", "DockCalendar::reserve(Booking) -> ReserveResult; DockCalendar::next_free(int,int,int) -> int", "mutable per-dock ordered interval calendar with insertion and gap search", "bad dock/id/endpoints, duplicates, or conflicts reject without mutation; touching is allowed", "a global booking vector that ignores dock ownership during conflict checks"),
    Plan("midnight-sleep-tracker", "sleep-interruption-ledger", "Measure the union of clipped wake episodes within a wrapping sleep session and return uninterrupted sleep blocks.", "analyze_sleep(SleepSession, vector<WakeEpisode>) -> SleepLedger", "session-relative clipping plus wake-interval union and complement", "wake episodes outside the session, duplicate IDs, invalid endpoints, or empty sleep invalidate atomically", "summing wake durations without merging overlapping wake episodes"),
    Plan("midnight-radio-silence", "quiet-window-violations", "Classify transmission points against multiple quiet windows and return first-window violations in input order.", "audit_silence(vector<QuietWindow>, vector<Transmission>) -> SilenceAudit", "window normalization followed by stable point-membership selection", "duplicate transmission IDs or invalid windows/minutes invalidate; a point at a half-open end is legal", "checking only one quiet window or treating the end boundary as closed"),
    Plan("midnight-bakery-oven", "oven-capacity-scheduler", "Assign overnight batches to the lowest available oven while respecting release times and capacity.", "schedule_batches(int, vector<Batch>) -> BakeSchedule", "event-ordered interval partitioning with busy/free min-heaps", "nonpositive capacity/duration, duplicate IDs, invalid starts, or unsorted releases invalidate; touching frees an oven", "round-robin assignment that ignores current oven finish times"),
    Plan("midnight-transit-pass", "transit-entitlement-audit", "Determine whether a trip is fully covered by pass validity minus blackout intervals plus end-only grace.", "check_entitlement(PassWindow, Trip, vector<Blackout>) -> Entitlement", "interval subtraction and complete-coverage scan on an unwrapped entitlement axis", "invalid/grace-negative/multi-cycle inputs invalidate; an exact grace endpoint is excluded", "endpoint-only containment that ignores an interior blackout"),
    Plan("midnight-hospital-handoff", "handoff-continuity-audit", "Audit an ordered shift chain for overlap, gaps, and the first unsafe handoff under a required overlap.", "audit_handoffs(vector<Shift>, int) -> HandoffAudit", "adjacent-pair timeline normalization with continuity-state accumulation", "duplicate IDs, invalid shifts, negative threshold, or nonchronological starts invalidate; equality meets the threshold", "sorting caller input and thereby hiding a nonchronological handoff chain"),
    Plan("midnight-noise-budget", "noise-budget-breach", "Charge the union of noisy operations inside protected bands and identify the operation that first pushes cumulative union charge over budget.", "audit_noise(int, vector<ProtectedBand>, vector<NoiseOperation>) -> NoiseAudit", "incremental interval-union growth with causal marginal-minute accounting", "invalid bands/operations, duplicate IDs, or negative budget invalidate; overlapping operations are not double charged", "summing per-operation overlap and double charging shared minutes"),
    Plan("midnight-delivery-curfew", "curfew-dispatch-selector", "Select the earliest candidate dispatch whose route duration avoids every curfew interval, with an ID tie break.", "select_dispatch(vector<Curfew>, vector<RouteCandidate>) -> DispatchChoice", "candidate ordering plus interval-intersection feasibility search", "invalid duration/start/id or duplicate IDs invalidates; touching a curfew is legal; no legal route is valid with found=false", "selecting the earliest start without testing the full route interval"),
)


def sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def markdown(plan: Plan) -> str:
    disposition = "reject" if plan.task_id in REJECTED_TASK_IDS else "replace"
    rejection = (
        " This proposal is rejected from the counted v2 family because its primary interval "
        "logic is a semantic near-duplicate of a retained root; it is preserved only as audit "
        "history and must not be materialized."
        if disposition == "reject"
        else ""
    )
    return f"""## Identity

Legacy task ID `{plan.legacy_id}`; proposed v2 task ID `{plan.task_id}`; task-spec revision 3; family ID `{FAMILY_ID}/{plan.task_id}`; disposition `{disposition}`; source inventory `cross-midnight-legacy-v1`; license result repository-authored/pass; generator `{GENERATOR}`; benchmark screen pending. Selected prompt `{PROMPT}` with `FAMILY_NAME=cross-midnight-intervals`, `FAMILY_TYPE=aider-text-grid-reshaping`, and the user-authorized hard count 8–12. The requested legacy grid path is absent; the historical owner-bound legacy root at `{LEGACY_ROOT.relative_to(REPO_ROOT)}` is the preserved audit input.{rejection}

## Objective

{plan.objective}

## Public API

C++17 namespace `curriculum`; editable order is `{plan.task_id}.h`, then `{plan.task_id}.cpp`. `{plan.public_api}`. Public records own their values; no borrowed lifetime or host-clock state is used.

## Behavior table

Valid input executes the objective and returns the documented deterministic report. {plan.invalid_rule}. Duplicate, absent, empty, ordering, tie, endpoint, and arithmetic behavior must be visible in the emitted instructions and independently asserted by visible/private tests. Rejection is atomic.

## Implementation invariant

Required mechanism: {plan.mechanism}. Forbidden substitutes are the legacy shared `Span`/generic result template, any other selected root's mechanism under renamed nouns, hard-coded cases, host time APIs, and official benchmark assets. Private tests must reject {plan.negative}.

## Starter and reference

The task-named header declares the complete API; the task-named source is coherent and intentionally incomplete. `.meta/example.h` and `.meta/example.cpp` form an independently authored complete reference using the required mechanism, with no legacy renderer or hidden-fixture dependency.

## Tests

Visible tests cover the normal mechanism and a public midnight boundary. Private tests cover invalid, duplicate/absent/empty, exact endpoint, ordering/tie, and topic-specific adversarial behavior. The named compilable negative substitutes {plan.negative}; both tests execute and at least one rejects it. Coherent domain/identifier-renamed, constants-or-policy-only, and opposite-end-selection controls must change emitted files, build, pass their own behavior tests, and be rejected by the exact production hard-rule evaluator.

## Files and metadata

Solutions: `{plan.task_id}.h`, `{plan.task_id}.cpp`; test: `task_visible_test.cpp`; private test: `.meta/task_hidden_test.cpp`; references: `.meta/example.h`, `.meta/example.cpp` mapped in solution order. Docs, tests, metadata, references, CMake, negative sources, manifests, and receipts stay private. Provenance records both the requested family type and historical legacy path.

## Build/oracle

C++17, strict warnings, explicit `Unix Makefiles`, two positive CTest targets, clean normal and separate fresh ASan/UBSan builds in `{IMAGE}` with Docker network `none`. Expected discovery is two tests in each mode. Receipt binds archive/mount/live tree hashes, owner/reference hashes, immutable image/toolchain identities, commands, network policy, counts, and negative outcomes.

## Family/contamination

Compare the complete 8-root counted family across the exact seven dimensions `public_api`, `owned_state_or_algorithm`, `mutation_selection_rules`, `invalid_boundary_behavior`, `reference_control_flow`, `deterministic_oracle`, and `topic_negative_fixture`; all 28 unordered pairs must pass every dimension separately. Rejected proposals remain outside the generated family. Screen normalized docs/API/reference/tests against all 26 official Aider C++ holdouts. No waiver is allowed.

## Optional dataset handoff

`not_requested`. No rows, token/mask evidence, splits, exports, training, or release are authorized.

## Acceptance

Run focused pytest, owner `--verify-core`, owner `--verify`, and owner `--docker-sanity`. For `replace`, require exact 8-root regeneration (within 8–12), strict prompt/role/reference mapping, all 28 seven-dimension material decisions, independent per-decision assertions, three coherent adversarial controls, one compiling/executed topic negative per root, benchmark separation, and equal positive normal/sanitizer counts. For `reject`, require absence from the generated root inventory and a preserved rejection record. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `negative_fixture_not_rejected`, `benchmark_content_overlap`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def main() -> int:
    if REQUESTED_LEGACY_ROOT.exists():
        raise SystemExit(f"unexpected requested legacy root now exists: {REQUESTED_LEGACY_ROOT}")
    if not LEGACY_ROOT.is_dir():
        raise SystemExit(f"historical legacy root missing: {LEGACY_ROOT}")
    remedy = OUT / ".state/remedy"
    remedy.mkdir(parents=True, exist_ok=True)
    for plan in PLANS:
        source = LEGACY_ROOT / plan.legacy_id
        text = markdown(plan)
        rejected = plan.task_id in REJECTED_TASK_IDS
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": plan.task_id,
            "legacy_task_id": plan.legacy_id,
            "family_id_before": "aider-dates-and-clocks-cross-midnight-intervals-v1-template",
            "family_id_after": f"{FAMILY_ID}/{plan.task_id}",
            "tree_hash_before": tree_hash(source),
            "generator_path": GENERATOR,
            "generator_revision": GENERATOR_REVISION,
            "finding_ids": [
                "CMI-F1-shared-template-semantic-duplicate",
                "CMI-F2-advertised-objective-not-implemented",
                "CMI-F3-task-named-file-role-drift",
                "CMI-F4-oracle-and-hard-rule-evidence-missing",
                "CMI-F5-requested-family-type-does-not-match-historical-owner",
            ],
            "disposition": "reject" if rejected else "replace",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{plan.task_id}.md",
            "remedy_spec_hash": sha_bytes(text.encode()),
            "status": "rejected" if rejected else "planned",
            "primary_core_objective": "not_achieved" if rejected else "specified",
            "selected_prompt": PROMPT,
            "user_inputs": {
                "FAMILY_NAME": "cross-midnight-intervals",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
                "hard_rule_count": "8-12",
            },
            "legacy_root_requested": str(REQUESTED_LEGACY_ROOT.relative_to(REPO_ROOT)),
            "legacy_root_audited": str(LEGACY_ROOT.relative_to(REPO_ROOT)),
            "legacy_root_requested_status": "absent",
            "legacy_audit": {
                "primary_core_objective": "not_achieved",
                "shared_api": "Span plus one generic accepted/policy/outside/related/spans/assignments result",
                "shared_reference_control_flow": "10 of 10",
                "shared_tests": "10 of 10 except substituted method/class names",
            },
            "rejection_reason": (
                "v2 semantic near-duplicate under the strict material seven-dimension hard rule"
                if rejected
                else None
            ),
            "hard_rule_invalidation": (
                "prior normalized-digest inequality proof withdrawn; replacement evidence pending"
            ),
            "dataset_handoff": "not_requested",
        }
        (remedy / f"{plan.task_id}.md").write_text(text, encoding="utf-8")
        (remedy / f"{plan.task_id}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(f"planned {len(PLANS)} remedies under {remedy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
