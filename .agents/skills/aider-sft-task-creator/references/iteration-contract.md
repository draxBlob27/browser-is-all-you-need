# Creation, Audit, and Remediation Handoff Contract

Use this contract for every cycle driven by `aider-sft-task-creator`.

## Cycle states

| State | Owner | May modify task artifacts? | Exit condition |
| --- | --- | --- | --- |
| `designing` | creator | Curriculum and owner only | Contract and lineage recorded |
| `generating` | creator | Owner and generated output through owner | Exact tree materialized |
| `creator_preflight` | creator | Owner, then regenerate | All creation gates pass |
| `auditing` | audit skill | No | Immutable findings and dispositions written |
| `remediating` | remediation skill | Owner, then regenerate | Every finding has a disposition and current evidence |
| `re_auditing` | audit skill | No | Current exact tree independently rechecked |
| `local_family_verified` | audit closes | No | Clean fresh audit of current tree |
| `not_completed` | any owner | Only after blocker clears | Exact external blocker recorded |

An audit never repairs its subject. A remediation verification never closes an
audit. Creation never self-admits a root.

## Cycle manifest

Record one append-only entry per cycle containing:

- cycle number and timestamp;
- task-family and candidate-manifest identifiers;
- curriculum, generator, focused-test, generated-tree, and grader-policy hashes;
- per-root prompt, editable-file, starter, reference, visible/hidden-test,
  metadata, and provenance hashes;
- compiler path/version/hash, image identity, CMake version, commands, network
  policy, and normal/sanitizer discovery counts;
- negative-fixture identities and observed rejection outcomes;
- benchmark/semantic/family screen policies and results;
- for Aider fixed-26 improvement batches, analog family coverage,
  file-layout/API-shape counts, interaction-mode counts, duplicate instruction
  header scan, boilerplate/copy-risk summary, repair-support inventory,
  count-target fit, and separation between new benchmark-shaped rows/tasks and
  filtered current synthetic anchors;
- request-batch ID, included root count, included root IDs, deferred backlog,
  prior-batch overlap checks, and justification for any request outside the
  normal 40-100-root authoring window;
- audit subject hash, report path, and finding IDs;
- remediation disposition and remedy-record path for every finding;
- prior evidence invalidated by the cycle;
- retained, replaced, rejected, review, and blocked root IDs;
- terminal status and exact remaining blockers.

Do not overwrite an earlier cycle to make the current one appear clean.

## Audit input boundary

Give the audit skill raw evidence sufficient to reproduce conclusions:

- immutable source and candidate manifests;
- exact task roots and owning source paths;
- public contracts, starters, references, tests, metadata, and receipts;
- benchmark-holdout inventory and semantic-screen configuration;
- requested root-count and diversity requirements.

Do not give it a desired pass result, omit rejected candidates, or summarize
away failed logs. Keep hidden tests and references inside the audit boundary and
out of model-facing prompts or rows.

## Finding lifecycle

Use stable IDs such as `cycle-02/root-slug/lineage-conflict`. A finding closes
only when a later audit, not the remediation pass itself, verifies its remedy on
the regenerated exact tree. Preserve these relations:

```text
finding -> remedy record -> owner change -> regenerated tree
        -> remediation receipt -> fresh audit disposition
```

If remediation reveals a new issue, create a new finding ID. Do not broaden an
old finding until its original meaning is ambiguous.

## Convergence rules

Continue without an arbitrary iteration cap while findings are actionable and
the requested scope is unchanged. Stop successfully only on a clean fresh
audit. Stop as `not_completed` only for a concrete missing prerequisite,
unresolved contract choice, unavailable locked execution environment, or
authority that cannot be inferred from the request.

Never converge by:

- weakening tests, compiler flags, sanitizer settings, contamination screens,
  diversity thresholds, or prompt boundaries;
- relabeling a defect as review-only without evidence;
- deleting a finding, failed receipt, or rejected candidate from history;
- accepting a host pass in place of required Docker/locked-image proof;
- counting rejected, replaced, duplicate, or unverified roots toward quotas;
- treating model confidence, judge preference, or training loss as a substitute
  for deterministic task evidence.
