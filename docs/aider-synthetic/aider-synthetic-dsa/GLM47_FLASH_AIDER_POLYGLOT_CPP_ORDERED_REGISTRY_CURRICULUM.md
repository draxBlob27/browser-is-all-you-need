# Ordered Registry Curriculum: Decontaminated Grade-School Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

The official Aider Polyglot C++ `grade-school` task is a permanent benchmark
holdout. This document does **not** propose twenty renamed roster exercises.
It targets the more general capability—maintaining an ordered registry under
identity, grouping, membership, reassignment, and query constraints—through
materially different domain contracts.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

Do not use the holdout task's wording, API, classes, field names, examples,
tests, reference implementation, expected ordering rules, or student/grade
scenario. Do not construct a source candidate by paraphrasing or translating
the holdout.

Each candidate below must be independently authored from a new behavior
specification and must materially differ in at least three of these dimensions:

- entity model and stable identity;
- group meaning and membership cardinality;
- ordering key and tie-breaking;
- mutation model, such as reassignment, capacity, expiry, or state transition;
- query shape, aggregate, or error behavior;
- visible C++ API and data representation.

Before admission, run the repository's whole-slug benchmark denylist and
semantic contamination checks against all official Aider C++ roots. A
near-match, including a straightforward group-and-sort registry that merely
renames the holdout, is rejected. Preserve the rejection evidence and backfill
with a new independently designed candidate; never weaken the checker.

## Online Material Status

Online collection and registry exercises are useful for private concept study
or source discovery only. They are not a drop-in SFT source inventory: every
external source needs explicit license and semantic-contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `registry-incident-routing` | Incident routing | Route uniquely identified incidents by service and severity; query the oldest unresolved incident per service. |
| `registry-library-loans` | Library loans | Assign books to patrons, reject a second active loan of one copy, and query overdue loans by due date. |
| `registry-warehouse-batches` | Warehouse batches | Place batches in storage zones with capacity limits, move a batch, and list expiring batches. |
| `registry-clinic-triage` | Clinic triage | Register patients by triage band, update condition, and select the next patient by severity then arrival time. |
| `registry-conference-seats` | Conference seats | Reserve a session seat, cancel or transfer it, and list waitlisted attendees by request timestamp. |
| `registry-parking-permits` | Parking permits | Issue permits by zone and expiry, revoke them, and query the next permit to expire. |
| `registry-feature-enrollment` | Feature enrollment | Assign accounts to rollout cohorts, migrate an account, and compute cohort utilization. |
| `registry-hotel-rooms` | Hotel rooms | Assign reservations to room classes, check in/out guests, and find the earliest available room. |
| `registry-cargo-customs` | Cargo customs | Track cargo declarations by risk lane, update clearance status, and enumerate pending inspections by deadline. |
| `registry-maintenance-crews` | Maintenance crews | Assign work orders to crews, prevent double assignment, and query crew workload totals. |
| `registry-museum-assets` | Museum assets | Place assets in galleries, transfer assets, and list insurance renewal deadlines. |
| `registry-vaccine-inventory` | Vaccine inventory | Allocate lot doses to clinics, enforce nonnegative stock, and prioritize soonest-expiring lots. |
| `registry-subscription-plans` | Subscription plans | Register accounts under plans, upgrade or cancel memberships, and report active counts by billing cycle. |
| `registry-flight-gates` | Flight gates | Assign flights to compatible gates, resolve gate conflicts, and query the next departure at a gate. |
| `registry-grant-reviews` | Grant reviews | Assign reviewers subject to conflict rules, withdraw assignments, and find under-reviewed proposals. |
| `registry-device-fleet` | Device fleet | Group devices by deployment ring, move a device, and list stale check-ins by timestamp. |
| `registry-support-escalations` | Support escalations | Group cases by escalation policy, alter priority, and select the oldest SLA breach candidate. |
| `registry-food-allergens` | Food allergens | Register dishes with allergen sets, update a recipe, and query safe dishes for a forbidden set. |
| `registry-shipping-contracts` | Shipping contracts | Register contracts by region and weight band, retire contracts, and resolve the best applicable contract. |
| `registry-audit-retention` | Audit retention | Place audit records in retention classes, apply legal holds, and enumerate records eligible for deletion. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose an API shaped
like a generic group-to-sorted-name roster. Include each task's distinct
identity, ordering, constraints, transition rules, and query result types in
the starter interface.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- identity collision and duplicate-registration behavior;
- the task-specific reassignment, cancellation, expiry, capacity, or state
  transition semantics;
- ordering and tie-breaking over multi-field keys;
- invalid cross-group transitions and failed operations with no state mutation;
- removal of the final member of a group and empty-query behavior;
- aggregate/count behavior where exposed;
- randomized mutation sequences checked against a straightforward map/vector
  oracle;
- a final contamination screen proving the candidate remains outside the
  benchmark holdout family.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
