#!/usr/bin/env python3
"""Freeze pre-implementation remedies for offset-aware range overlap."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks/aider-dates-and-clocks/offset-aware-range-overlap"
REQUESTED_LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/offset-aware-range-overlap"
OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/offset-aware-range-overlap"
GENERATOR = "src/w8_biayn/integrations/moonlight_offset_aware_range_overlap_aider_tasks.py"
GENERATOR_REVISION = "sha256:2db9e7687bd3fa68be0e800aa107b3b4a83f7cf8b033b3afdbb973f5f0529b3a"
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-text-grid-reshaping-offset-aware-range-overlap-v3"
IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"


@dataclass(frozen=True)
class Plan:
    legacy_id: str
    task_id: str
    disposition: str
    objective: str
    public_api: str
    mechanism: str
    invalid_rule: str
    negative: str


PLANS = (
    Plan("offset-build-freeze", "offset-build-freeze", "repair-in-place", "Classify releases against normalized regional freeze ranges and return the first blocker under jurisdiction precedence.", "BuildFreezeAudit::classify(Release, vector<FreezeWindow>) -> FreezeFinding", "normalized interval stabbing with explicit precedence and stable jurisdiction ties", "invalid offsets/ranges, duplicate jurisdictions, or an invalid release reject atomically; touching a half-open freeze is allowed", "choosing the first input window without testing normalized membership or precedence"),
    Plan("offset-crossborder-delivery", "offset-border-slot-enumerator", "replace", "Enumerate maximal delivery slots that remain after intersecting dispatch and acceptance ranges and subtracting customs closures.", "enumerate_border_slots(DispatchWindow, AcceptanceWindow, vector<Closure>, int) -> SlotReport", "two-range intersection, closure union, interval subtraction, and minimum-duration filtering", "malformed ranges, duplicate closure IDs, bad offsets, or nonpositive duration reject; touching closures merge", "returning the raw endpoint intersection while ignoring interior closures"),
    Plan("offset-distributed-deploy", "offset-deployment-quorum-sweep", "replace", "Find every normalized span in which a weighted service quorum is simultaneously available.", "deployment_quorum(vector<ServiceWindow>, int) -> QuorumReport", "weighted boundary-event sweep with end-before-start half-open ordering", "duplicate services, nonpositive weights/threshold, invalid offsets/ranges, or threshold above total weight reject", "intersecting every service window instead of sweeping weighted quorum changes"),
    Plan("offset-emergency-escalation", "offset-relay-capacity-matching", "replace", "Match incident coverage segments to qualified relay teams without exceeding team capacity.", "RelayMatcher::assign(vector<Incident>, vector<RelayTeam>) -> RelayPlan", "deterministic bipartite augmenting-path matching over normalized overlap and skill eligibility", "duplicate IDs, invalid intervals/offsets, empty skills, or nonpositive capacities reject without partial assignments", "greedily selecting the lowest team ID without an augmenting path"),
    Plan("offset-flight-crew-rest", "offset-rest-gap-compliance", "replace", "Measure legal common rest after subtracting duty fragments from each crew member's normalized rest envelope.", "audit_rest(RestEnvelope, RestEnvelope, vector<DutyFragment>, int) -> RestAudit", "per-crew duty union/subtraction followed by two-pointer free-span intersection", "bad offsets/ranges, duplicate duty IDs, unknown crew IDs, or nonpositive required rest reject", "comparing only the two outer rest envelopes and ignoring duty fragments"),
    Plan("offset-market-auction", "offset-auction-liquidity-intersection", "replace", "Select the session pair whose normalized intersection maximizes executable liquidity under venue and lot constraints.", "select_liquidity_pair(vector<TradingSession>, int) -> AuctionChoice", "pairwise normalized intersection scored by min liquidity and duration with deterministic multi-key ties", "duplicate IDs, invalid offsets/ranges, nonpositive liquidity/lot, or incompatible venues reject or skip as documented", "choosing the longest overlap while ignoring executable liquidity and lot size"),
    Plan("offset-remote-support", "offset-support-coverage-chain", "replace", "Cover one normalized support request continuously with the fewest compatible shifts, recording each frontier-extending handoff.", "plan_support_chain(SupportRequest, vector<SupportShift>) -> SupportChainPlan", "minimum-cardinality interval cover by a farthest-reaching frontier sweep with stable ID ties", "duplicate IDs, invalid offsets/ranges, empty languages, or an invalid request reject; incompatible shifts are ignored and an uncovered frontier is a valid incomplete result", "choosing the earliest-ending compatible shift instead of the farthest frontier extension"),
    Plan("offset-research-coverage", "offset-observation-coverage-subtraction", "replace", "Compute per-instrument and combined observation coverage after normalized calibration blackouts are removed.", "measure_coverage(vector<ObservationWindow>, vector<CalibrationWindow>) -> CoverageReport", "grouped clipping, interval union/subtraction, then global coverage union", "unknown instrument references, duplicates, invalid offsets/ranges, or calibration outside its observation horizon reject", "summing raw window lengths and double counting overlap or calibration"),
    Plan("offset-satellite-contact", "offset-station-contact-weighted-schedule", "replace", "Choose a maximum-value non-overlapping contact schedule after fixed-offset normalization and station setup gaps.", "schedule_contacts(vector<ContactPass>, int) -> ContactPlan", "weighted interval scheduling dynamic program with predecessor search and lexicographic reconstruction ties", "duplicate IDs, invalid offsets/ranges, negative value, or negative setup gap reject", "earliest-finish greedy selection that ignores pass value"),
    Plan("offset-telehealth-roster", "offset-clinic-capacity-assignment", "replace", "Maintain a transactional appointment booking ledger over normalized clinician availability and local-day capacity.", "ClinicRoster(vector<Clinician>); valid; book; cancel; lookup; assignments", "stateful booking/cancellation ledger with per-clinician local-day counters and deterministic least-used selection", "an invalid roster is inert; invalid, duplicate, unavailable, unknown-cancel, or cap-exhausted operations return false without mutation", "counting a clinician's capacity by UTC day instead of that clinician's local day"),
)


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def markdown(plan: Plan) -> str:
    return f"""# Remedy Specification: {plan.task_id}

## Identity

Legacy task `{plan.legacy_id}`; replacement task `{plan.task_id}`; task-spec revision 3; family `{FAMILY_ID}`; disposition `{plan.disposition}`; source inventory `offset-aware-range-overlap-legacy-v1`; license `repository-authored-clean-room/pass`; generator `{GENERATOR}`; benchmark screen `pending`. Selected prompt `{PROMPT}` with `FAMILY_NAME=offset-aware-range-overlap`, `FAMILY_TYPE=aider-text-grid-reshaping`, and the user-authorized hard-rule count 8–12. The requested legacy text-grid path is absent; `{LEGACY_ROOT.relative_to(REPO_ROOT)}` is the preserved owner-bound audit input. The earlier v2 semantic claim is archived and invalidated because its identifier-preserving normalizer and 0.98 threshold admitted two augmenting-path matching roots.

## Objective

{plan.objective}

## Public API

C++17 namespace `curriculum`; editable order is `{plan.task_id}.h`, `{plan.task_id}.cpp`. `{plan.public_api}`. Inputs are caller-owned values and no host clock or time-zone database is used.

## Behavior table

| Operation | Success | Invalid/duplicate/absent/empty | Mutation/order/tie/overflow | Public boundary |
| --- | --- | --- | --- | --- |
| Task API | Executes the stated normalized-range mechanism and returns the typed report. | {plan.invalid_rule}. Empty valid collections and absent matches return the documented non-error result. | Rejection is atomic; normalized arithmetic uses checked bounded minutes; ordering and ties are explicit. | Offsets at -840/840, touching half-open endpoints, date rollover, equality at the required duration, and deterministic ties are visible rules. |

## Implementation invariant

Required mechanism: {plan.mechanism}. Forbidden substitutes are the legacy shared generic record/result template, any other selected root under renamed nouns, a bare overlap helper, host clock/time-zone APIs, hard-coded cases, and official benchmark assets. Private tests reject {plan.negative}.

## Starter and reference

The task-named header is complete and the task-named source is coherent but incomplete. `.meta/example.h` and `.meta/example.cpp` form an independently authored reference using the required mechanism. The owner may share only incidental validation helpers; it may not render one policy-switch implementation for the family.

## Tests

Visible tests cover the normal mechanism and a public offset/endpoint boundary. Private tests cover invalid, duplicate/absent/empty, exact endpoint, ordering/tie, and the named negative fixture. Deterministic traces use fixed literal records and compare complete typed results. The negative compiles under strict flags and must be rejected by executed tests. Domain/identifier-renamed, constants-or-policy-only, and opposite-end-selection coherent controls must change emitted files, build in both modes, pass their own behavior tests, and be rejected by the production seven-dimension evaluator.

## Files and metadata

Solutions are `{plan.task_id}.h` and `{plan.task_id}.cpp`; tests are `task_visible_test.cpp` and `.meta/task_hidden_test.cpp`; references are `.meta/example.h` and `.meta/example.cpp` mapped in solution order. Docs, tests, references, metadata, CMake, negative sources, screens, remedies, and receipts remain private. No bundled support asset is required.

## Build/oracle

C++17, strict `-Wall -Wextra -Wpedantic -Werror`, explicit `Unix Makefiles`, pinned `{IMAGE}` Docker sanity (not locked oracle), and network `none`. Clean normal and fresh ASan/UBSan each require three positive CTest discoveries: visible, private, and WILL_FAIL topic-negative. Receipt binds live/archive/mounted tree hashes, owner/reference hashes, immutable image and toolchain, commands, counts, negative exits, and network policy.

## Family/contamination

Compare all ten emitted roots across all 45 unordered pairs and each of the seven dimensions `public_api`, `owned_state_or_algorithm`, `mutation_selection_rules`, `invalid_boundary_behavior`, `reference_control_flow`, `deterministic_oracle`, and `topic_specific_negative_fixture`. Compare normalized docs/APIs/references/tests with all 26 permanent Aider C++ holdouts, especially `clock`, `gigasecond`, and `meetup`. Every dimension is conjunctive; no aggregate waiver is allowed.

## Optional dataset handoff

`not_requested`. No JSONL, token/mask evidence, split, export, training, producer/consumer verification, release, or uplift claim is authorized.

## Acceptance

Run this planner with `--check`, focused pytest, owner `--verify-core`, host `--verify` for iteration, and owner `--docker-sanity`. Require exact 10-root regeneration (within 8–12), strict prompt/role/reference mapping, all 45 seven-dimension decisions, independent per-decision assertions, nonempty coherent controls, one compiling/executed topic negative per root, all-26 holdout separation, and three equal positive normal/sanitizer discoveries for roots and controls. Stable failures include `remedy_spec_incomplete`, `hard_rule_root_count`, `hard_rule_evidence_incomplete`, `prompt_contract_incomplete`, `target_reference_mismatch`, `invariant_not_enforced`, `duplicate_family`, `negative_fixture_not_rejected`, `benchmark_content_overlap`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def expected() -> dict[Path, str]:
    records: dict[Path, str] = {}
    remedy = OUT / ".state/remedy"
    for plan in PLANS:
        source = LEGACY_ROOT / plan.legacy_id
        text = markdown(plan)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": plan.task_id,
            "legacy_task_id": plan.legacy_id,
            "family_id_before": "aider-dates-and-clocks-offset-aware-range-overlap-v1-template",
            "family_id_after": FAMILY_ID,
            "tree_hash_before": tree_hash(source),
            "generator_path": GENERATOR,
            "generator_revision": GENERATOR_REVISION,
            "finding_ids": ["OARO-F1-shared-template", "OARO-F2-nondiscriminating-tests", "OARO-F3-hard-rule-evidence-missing", "OARO-F4-docker-receipt-stale-or-absent", "OARO-F5-requested-family-type-mismatch"],
            "disposition": plan.disposition,
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{plan.task_id}.md",
            "remedy_spec_hash": sha(text.encode()),
            "status": "planned",
            "primary_core_objective": "specified",
            "local_status": "pending_execution",
            "selected_prompt": PROMPT,
            "user_inputs": {"FAMILY_NAME": "offset-aware-range-overlap", "FAMILY_TYPE": "aider-text-grid-reshaping", "hard_rule_count": "8-12"},
            "legacy_root_requested": str(REQUESTED_LEGACY_ROOT.relative_to(REPO_ROOT)),
            "legacy_root_audited": str(LEGACY_ROOT.relative_to(REPO_ROOT)),
            "legacy_root_requested_status": "absent",
            "legacy_audit": {"primary_core_objective": "not_achieved", "shared_record_result_shape": "10 of 10", "single_policy_renderer": "10 of 10", "nondiscriminating_test_shape": "10 of 10"},
            "dataset_handoff": "not_requested",
            "prior_local_family_verified_claim": "invalidated-v2-identifier-dependent-screen-and-duplicate-matching",
        }
        records[remedy / f"{plan.task_id}.md"] = text
        records[remedy / f"{plan.task_id}.json"] = json.dumps(record, indent=2, sort_keys=True) + "\n"
    return records


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if REQUESTED_LEGACY_ROOT.exists():
        raise SystemExit(f"unexpected requested legacy root exists: {REQUESTED_LEGACY_ROOT}")
    if not LEGACY_ROOT.is_dir():
        raise SystemExit(f"legacy root missing: {LEGACY_ROOT}")
    remedy_root = OUT / ".state/remedy"
    archive_root = OUT / ".state/invalidated/remedies-v2-pre-v3"
    if not args.check and remedy_root.is_dir() and not archive_root.exists():
        archive_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(remedy_root, archive_root)
    if not args.check:
        for suffix in (".json", ".md"):
            obsolete = remedy_root / f"offset-support-bipartite-handoff{suffix}"
            if obsolete.exists():
                obsolete.unlink()
    mismatches: list[str] = []
    for path, content in expected().items():
        if args.check:
            if not path.is_file():
                mismatches.append(path.as_posix())
            elif path.suffix==".md" and path.read_text(encoding="utf-8")!=content:
                mismatches.append(path.as_posix())
            elif path.suffix==".json":
                actual=json.loads(path.read_text(encoding="utf-8"));planned=json.loads(content)
                mutable={"status","primary_core_objective","local_status","benchmark_screen"}
                if any(actual.get(key)!=value for key,value in planned.items() if key not in mutable):
                    mismatches.append(path.as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if mismatches:
        raise SystemExit("stale offset-aware remedy records: " + ", ".join(mismatches))
    print(f"{'checked' if args.check else 'planned'} {len(PLANS)} remedies under {OUT / '.state/remedy'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
