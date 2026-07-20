# Elapsed-Time Accumulation Family Remediation

## Scope and inputs

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
with `FAMILY_NAME=elapsed-time-accumulation` and
`FAMILY_TYPE=aider-text-grid-reshaping`. The user authorizes a family-specific
hard count of 8–12. The derived requested legacy path under
`aider-text-grid-reshaping` is absent. The actual ten-root legacy owner output
is preserved at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/elapsed-time-accumulation/`;
fresh output goes only to
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/elapsed-time-accumulation/`.

## Legacy audit findings

### ETA-F1 — advertised mechanisms are absent

**Severity:** major

**Scope:** all ten legacy roots

**Observed evidence:** every legacy root was emitted by
`moonlight_elapsed_time_accumulation_aider_tasks.py` from one generic
`id/minutes/contributes` record, one `std::set<std::string>` duplicate check,
and one shared accumulation loop. Daily caps, interval conflict detection,
signed corrections, event transitions, weights, interval union, retry
selection, and per-incident budgets were not implemented.

**Root cause:** titles and policy prose varied while the API, owned state,
control flow, tests, and reference stayed one template.

**Remedy:** replace the owner with eight independently implemented mechanisms;
reject two objectives that collapse into retained roots.

**Status:** resolved and reverified.

### ETA-F2 — semantic family duplication

**Severity:** major

**Scope:** all ten legacy roots

**Observed evidence:** normalized APIs/references/tests are identical apart
from domain identifiers and method names.

**Remedy:** retain exactly eight roots that differ conjunctively in public API,
owned state/algorithm, mutation/selection, invalid/boundary behavior,
reference control flow, deterministic oracle, and topic negative. Reject
`elapsed-battery-test-log` and `elapsed-lab-equipment-booking`.

**Status:** resolved and reverified: all 28 pairs passed all seven dimensions,
and all three coherent adversarial controls were rejected by the production
evaluator.

### ETA-F3 — legacy runtime evidence is stale and host-only

**Severity:** blocker

**Scope:** all legacy roots

**Observed evidence:** the old `--verify` path used host CMake and wrote no
image-bound receipt, mounted-tree hash, compiler identity, positive discovery
ledger, or executed false-substitute evidence.

**Remedy:** use the pinned repository C++ sanity image with Docker network
`none`, deterministic archive reconciliation, fresh normal and sanitizer
builds, equal positive discovery counts, and executed topic negatives.

**Status:** resolved and reverified by `.state/oracle-receipt.json`.

### ETA-F4 — mandatory hard-rule controls were absent

**Severity:** major

**Scope:** family evaluator

**Remedy:** owner-generate coherent domain/identifier, constants/policy, and
opposite-end controls. Each must change intended files, compile, pass its
coherent behavior tests, and be rejected by the exact production pair
evaluator.

**Status:** resolved and reverified by focused independent assertions and the
Docker control receipt.

## Per-root dispositions

| Legacy root | Disposition | Replacement / result |
|---|---|---|
| `elapsed-consulting-invoice` | replace | `capped-client-day-ledger`: per-client/day cap ledger |
| `elapsed-machine-utilization` | replace | `machine-state-coverage-audit`: sorted half-open interval conflict audit |
| `elapsed-reading-challenge` | replace | `reading-session-correction-ledger`: atomic session correction ledger |
| `elapsed-freelance-breaks` | replace | `freelance-event-reconciler`: per-worker transition state machine |
| `elapsed-training-load` | replace | `weighted-training-load`: checked weighted sum and post-sum cap |
| `elapsed-network-uptime` | replace | `service-outage-interval-union`: per-service clipped interval union |
| `elapsed-podcast-production` | replace | `podcast-attempt-selector`: latest-sequence replacement by job |
| `elapsed-incident-response` | replace | `incident-budget-frontier`: per-incident ordinal/budget frontier |
| `elapsed-battery-test-log` | reject | duplicate of latest-attempt selection |
| `elapsed-lab-equipment-booking` | reject | duplicate of capped allocation |

## Verification contract

The owner must regenerate exactly eight counted roots, preserve all ten legacy
roots, validate prompt and role/reference boundaries, compare all 28 unordered
pairs in exactly seven independently asserted dimensions, reject all three
coherent controls, and compare 8 × 26 candidate/holdout pairs using the bound
upstream inventory. Each counted reference must discover and pass two tests in
clean normal and fresh ASan/UBSan Docker builds. Each topic negative must build
and then fail executed tests. Receipts bind owner, archive, mounted archive,
tree, reference, negative, image, compiler, CMake, commands, and network policy.

The pinned image is repository `docker_sanity`, not a family-designated locked
oracle. `local_family_verified` is permitted only after every structural,
semantic, hard-rule, Docker, and receipt reconciliation gate passes. Dataset
handoff is `not_requested`.

## Final evidence

A post-handoff self-audit found that the first hard-rule receipt partially
derived mutation/selection evidence from the case table and that focused tests
inspected the production matrix without independently recomputing it. The owner
archived that receipt and manifest under `.state/invalidated/`, recorded why
the prior `local_family_verified` claim was insufficient, removed the live
receipt, and returned the family to `planned` before regeneration.

After the last owner and artifact-affecting edit, the owner regenerated all
eight roots. Focused pytest reported 9 passing tests. Production and independent
test code separately reread the emitted docs, public header, reference source,
visible/private tests, and reference-to-negative diff. Both record
`task_count: 8`, the exact seven dimension names, and 28/28 conjunctively
passing unordered pairs after identifier/literal/comparator normalization. The
three controls have independently recomputed nonempty changed-file sets and
per-dimension decisions. The bound holdout screen reads the same emitted roots,
compares them with all 26 official C++ roots (208 comparisons), and passes.

The final network-disabled Docker sanity run used image ID
`sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
Every root discovered and passed exactly two normal and two fresh
ASan/UBSan tests. All eight topic negatives compiled and were rejected by
executed tests. All three coherent hard-rule controls compiled, discovered and
passed two tests, changed intended files, and were rejected by the exact
production family evaluator. The receipt reconciles the deterministic archive,
mounted archive, owner, live trees, references, negative sources, image, and
toolchain. All eight retained remedy records reached `local_family_verified`;
the two rejected records remain terminal. No record reached that status before
the hard-rule and Docker gates passed.
