# Ordered Registry Family Audit And V2 Remedy

## Scope

This report applies `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
with `FAMILY_NAME=ordered-registry` and `FAMILY_TYPE=aider-dsa`. It audits all
20 v1 roots under `.w8-biayn/data/aider-tasks/aider-dsa/ordered-registry/`,
preserves that tree, and records the v2 family under
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/ordered-registry/`.

The review purpose is local task-family remediation only. It creates no JSONL,
split, token/mask evidence, release, training authorization, or benchmark
claim.

## Legacy Audit

`primary_core_objective: not_achieved` for every v1 root. Although domain nouns
and method names varied, the owner rendered the same `Entry { id, group, rank,
stamp, amount, active }`, `std::vector<Entry>`, constructor-wide group limit,
register, generic transition, rank/stamp sort, find, and active-count algorithm
for all 20 roots. Visible and hidden tests were also the same template. This
failed the primary-content and duplicate-family requirements: the proposed
workflow, waitlist, interval, set, heap, allocation, and conservation behaviors
did not exist in their references.

### OR-001 — Generic implementation replaces advertised objectives

**Severity:** major

**Scope:** every v1 root

**Observed evidence:** the v1 owner `_header`, `_reference`, and `_test`
functions produced one state and algorithm skeleton for every `_ROWS` entry.

**Why it matters:** names alone provide no different learning logic or
implementation.

**Root cause:** task rows parameterized nouns and labels rather than complete
contracts and reference mechanisms.

**Remedy:** retain only the lexicographically first independently salvageable
root ID and replace the other 19 with the exact v2 contracts below.

**Verification after remedy:** `--verify-core` requires unique semantic
signatures and task-specific markers, then executes the rejection path after
removing each marker and after injecting the v1 generic entry signature.

**Status:** resolved and reverified.

### OR-002 — V1 tests cannot distinguish semantic duplicates

**Severity:** major

**Scope:** every v1 root

**Observed evidence:** all roots exercised the same duplicate, capacity,
rank/stamp ordering, and generic transition trace.

**Why it matters:** a renamed v1 solution could pass another root.

**Root cause:** tests were generated from the shared template rather than the
advertised state transition.

**Remedy:** each v2 root has separate behavior tests and a named negative
fixture in its pre-implementation remedy specification.

**Verification after remedy:** focused tests require 20 different references,
class names, objectives, and core-marker tuples; normal and sanitizer tests
pass per root.

**Status:** resolved and reverified.

### OR-003 — Role and evidence quality lag current contract

**Severity:** moderate

**Scope:** family

**Observed evidence:** v1 used generic editable filenames and did not persist
family/core/benchmark screens or oracle receipts.

**Why it matters:** a passing build did not bind prompt safety, family
independence, or current tree bytes.

**Root cause:** the original materializer predates the deterministic remedy
contract.

**Remedy:** slug-named editable files, per-root remedy records/specs, prompt and
whole-file validation, all-holdout semantic screening, deterministic fresh-tree
comparison, and task-tree-bound normal/sanitizer receipts.

**Verification after remedy:** manifest and oracle receipt report all required
passes with matching tree hashes.

**Status:** resolved and reverified.

## Deterministic Dispositions

Duplicate disposition rules retain the lexicographically smallest independently
justified representative and replace every other duplicate. Replacement is a
new task ID and contract, never a rename-only overwrite.

| V1 root | Disposition | V2 root | Distinct primary mechanism |
|---|---|---|---|
| `registry-audit-retention` | repair-in-place | same ID | expiry/hold eligibility ledger |
| `registry-cargo-customs` | replace | `customs-clearance-workflow` | guarded three-stage FSM |
| `registry-clinic-triage` | replace | `triage-priority-board` | destructive mutable priority selection |
| `registry-conference-seats` | replace | `session-seat-waitlist` | seated/waiting promotion state |
| `registry-device-fleet` | replace | `device-heartbeat-index` | monotonic heartbeat index |
| `registry-feature-enrollment` | replace | `rollout-token-ring` | clockwise consistent-hash successor routing |
| `registry-flight-gates` | replace | `gate-conflict-scheduler` | compatibility plus interval calendars |
| `registry-food-allergens` | replace | `dish-allergen-catalog` | canonical set disjointness |
| `registry-grant-reviews` | replace | `proposal-review-matcher` | conflict and assignment relations |
| `registry-hotel-rooms` | replace | `room-stay-calendar` | multi-stay half-open calendars |
| `registry-incident-routing` | replace | `service-incident-queue` | maintained per-service priority index |
| `registry-library-loans` | replace | `copy-loan-ledger` | copy lifecycle/forward renewal |
| `registry-maintenance-crews` | replace | `crew-workload-ledger` | weighted-load conservation |
| `registry-museum-assets` | replace | `asset-custody-history` | append-only history/predecessor query |
| `registry-parking-permits` | replace | `permit-expiry-wheel` | extendable modular expiry wheel |
| `registry-shipping-contracts` | replace | `shipping-rate-resolver` | cost/width interval resolution |
| `registry-subscription-plans` | replace | `billing-cycle-counter` | reconciled 2-D aggregates |
| `registry-support-escalations` | replace | `sla-escalation-heap` | indexed binary heap |
| `registry-vaccine-inventory` | replace | `vaccine-lot-fefo` | transactional multi-lot FEFO |
| `registry-warehouse-batches` | replace | `warehouse-batch-splitter` | split/merge unit conservation |

The exact APIs, behavior tables, invariants, forbidden substitutes, deterministic
fixtures, file roles, and acceptance commands were frozen before generator
implementation under `.state/remedy/<v1-root>.md`; the companion JSON records
bind their hashes and v1 tree hashes.

## Commands And Results

Focused structural regression:

```text
UV_CACHE_DIR=/tmp/ordered-registry-uv-cache uv run pytest -q tests/test_moonlight_ordered_registry_aider_tasks.py
6 passed.
```

Core, prompt, role/reference, deterministic generation, duplicate-family, and
benchmark screen:

```text
PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_ordered_registry_aider_tasks \
  --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/ordered-registry \
  --force --verify-core
Wrote 20 ordered-registry v2 tasks ...
```

The benchmark screen loaded all 26 bound upstream C++ holdouts, used
`ordered-registry-contract-v3`, and passed. It removes comments, strings,
literals, and domain identifiers while preserving API arity, control flow,
invariants, and assertions. The strongest holdout similarity was 0.162755 and
the strongest all-family pair was 0.713810 (blocking threshold 0.94). A focused
fixture copies a complete task under changed nouns/class/objective and proves
the same screen raises `duplicate_family`. The prompt screen
passed for every root; reference code, private tests, CMake, provenance, and
private paths remained absent.

The host lacked `cmake`, so the first host verifier truthfully recorded
`not_completed`. Locked verification then ran with networking disabled in:

```text
w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991
```

The owner regenerated the mounted live tree and ran explicit Unix Makefiles,
the locked `c++`, strict warnings, clean normal builds, and fresh ASan/UBSan
builds. For each root it also generated a named topic-specific false
implementation, required that implementation to compile, and required its
three discovered tests to reject it. The third test is a private deterministic
model trace that compares every return and complete public ordering after every
operation and covers every public operation class. Final result: 20/20
references passed; normal discovery = 3 per root; sanitizer discovery = 3 per
root; counts equal; no zero-test root; 20/20 compiled false substitutes
rejected. The receipt binds the current owner/generator/curriculum/audit hashes
and identical owner/Docker family hash
`sha256:25c27d8cd8058aec9b392478d1a54332c0a34fea94dd40ca500853277e806b43`,
with `network_policy: none`, GCC 13.4.0, and CMake 3.25.1.

Manual review of the first v3 screen rejected two pairs even though they were
below the mechanical threshold: cohort capacity versus weighted crew capacity,
and device heartbeat versus asset renewal. The former was replaced by the
token ring and the latter by custody history. Audit retention and incident
routing were also changed from map-filter-sort queries to maintained ordered
indices. Timing-wheel extension and heap priority-front observables were added
after compiled false substitutes exposed previously untestable implementation
claims. Those failed attempts did not count as evidence.

## Changed Owners And Evidence

- Curriculum: `docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ORDERED_REGISTRY_CURRICULUM.md`
- Normative audit: this file
- Owner: `src/w8_biayn/integrations/moonlight_ordered_registry_aider_tasks.py`
- Task-specific cases: `src/w8_biayn/integrations/moonlight_ordered_registry_cases.py`
- Independent traces/false substitutes: `src/w8_biayn/integrations/moonlight_ordered_registry_verification_cases.py`
- Focused tests: `tests/test_moonlight_ordered_registry_aider_tasks.py`
- Wrapper: `examples/slime/moonlight_cpp_perf/prepare_ordered_registry_aider_tasks.sh`
- Materialization guide: `docs/AIDER_TASK_MATERIALIZATION_GUIDE.md`

The v1 and v2 per-root tree hashes are in each remedy JSON record. Current v2
hashes are also bound in `.state/materialization-manifest.json`; oracle records
repeat the same task-tree hashes. Regeneration invalidates those receipts and
forces reverification.

## Conclusion

- **Core objective implemented (primary):** achieved for all 20 v2 roots, with
  separate state/algorithm mechanisms and executed negative-fixture screens.
- **Structurally valid:** pass for all 20 roots.
- **Oracle verified:** pass in the immutable network-disabled grader for normal
  and fresh ASan/UBSan, three tests per mode per root.
- **Training-suitable:** local family independence and all-26-holdout screens
  pass; this wording does not admit the roots to a dataset.
- **No release claim:** no dataset handoff was requested or created.

Strongest truthful local state: `local_family_verified` for every v2 root.
