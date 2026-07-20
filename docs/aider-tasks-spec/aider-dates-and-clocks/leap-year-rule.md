# Leap-Year Rule Family Audit and Remedy

## Scope

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
for `FAMILY_NAME=leap-year-rule`,
`FAMILY_TYPE=aider-text-grid-reshaping`, and the authorized 8–12 count range.
The supplied legacy path is absent. The immutable five-root predecessor was
discovered and audited under `aider-dates-and-clocks/leap-year-rule`; the eight
replacement roots materialize only under the supplied reverify family type.

## Findings

### LYR-F1 — Five-root count misses the authorized lower bound

**Severity:** blocker

**Scope:** legacy family

**Observed evidence:** five discovered task directories; the controlling count
is 8–12.

**Root cause:** the predecessor curriculum was authored before the binding hard
count rule.

**Remedy:** replace the five roots and add three independently justified
backfills, producing exactly eight counted roots.

**Verification after remedy:** focused test asserts eight roots and 28 pairs.

**Status:** resolved in owner; runtime re-verification is recorded in the live
manifest and receipt.

### LYR-F2 — Shared thin February-policy template

**Severity:** major

**Scope:** all five legacy roots

**Observed evidence:** one shared Gregorian helper and thin one-shot collection
wrappers; no artifact-derived conjunctive seven-dimension proof.

**Root cause:** domain renaming and policy variation were treated as sufficient
curriculum diversity.

**Remedy:** `replace` every legacy root with the eight mechanism-specific roots
listed in the curriculum. Each owns a different algorithm/state model and a
different compiling false substitute.

**Verification after remedy:** owner rereads emitted artifacts and requires all
28 pairs to pass every dimension.

**Status:** resolved in source; final evidence is receipt-bound.

### LYR-F3 — Required adversarial hard-rule evidence absent

**Severity:** blocker

**Scope:** family screen

**Observed evidence:** no coherent domain rename, constants/policy, or
opposite-end controls and no independent focused assertions over each decision.

**Root cause:** predecessor tests checked only materialization and whole-file
answer shape.

**Remedy:** generate coherent controls from emitted mechanisms, prove nonempty
changes and successful behavior builds, and reject each through the exact
production evaluator in all seven dimensions.

**Verification after remedy:** focused tests inspect the exact root/pair counts,
dimension set, per-dimension decisions, changed controls, and rejection results.

**Status:** resolved in owner/tests; runtime evidence is recorded separately.

### LYR-F4 — Oracle evidence is not Docker/tree bound

**Severity:** blocker

**Scope:** every legacy root

**Observed evidence:** predecessor `--verify` was host-only and persisted no
snapshot-safe network-disabled receipt or executed false-substitute result.

**Root cause:** the original owner predates mandatory Docker sanity evidence.

**Remedy:** deterministic archive, independent mounted hashes, pinned image,
network none, exact normal/fresh sanitizer counts, and executed topic negatives.

**Verification after remedy:** owner `--docker-sanity` and post-run receipt
reconciliation.

**Status:** final status is whatever the live receipt truthfully records.

### LYR-F5 — Supplied family type and discovered legacy location differ

**Severity:** moderate

**Scope:** family path resolution

**Observed evidence:** the supplied legacy path does not exist; the actual
predecessor is under `aider-dates-and-clocks`.

**Root cause:** orchestration input reclassifies the family without moving a
legacy tree.

**Remedy:** preserve and audit the discovered legacy tree, record the mismatch
in every predecessor remedy record, and write replacements only to the exact
supplied reverify path.

**Verification after remedy:** manifest binds both paths and asserts the legacy
tree was not generated.

**Status:** resolved and recorded.

## Per-root dispositions

| Legacy root | Disposition | Replacement |
|---|---|---|
| `leap-february-inventory` | replace | `leap-capacity-calendar` |
| `leap-payroll-accrual` | replace | `leap-benefit-apportionment` |
| `leap-weather-archive` | replace | `leap-archive-gap-index` |
| `leap-facility-booking` | replace | `leap-maintenance-ledger` |
| `leap-publication-cycle` | replace | `leap-cadence-wheel` |
| — | replace/backfill | `leap-coverage-segments` |
| — | replace/backfill | `leap-shift-matching` |
| — | replace/backfill | `leap-policy-replay` |

## Acceptance and evidence locations

The final source contract expects owner hash
`sha256:159adc8c531f304bd3af90046315ae79649bcfe9674e636ee19796f369008faa`
and generated family hash
`sha256:5695370393a910eb33e71ba88e687a91ea99a88ae8f2af6d0a5e9ca2b21bec6a`.
Per-root replacement hashes are:

| Root | Generated tree hash |
|---|---|
| `leap-archive-gap-index` | `sha256:0f76a22012001fea669069e4a355ea1c8c694276d8d2ce092be9a083ebb62ee6` |
| `leap-benefit-apportionment` | `sha256:9f30cc25780d151ad07594cb07c2e54ae66a4c429124555470e0b1a9314739e4` |
| `leap-cadence-wheel` | `sha256:935833ca546e5b363ff25019b73336397da82cd992a63b65b999ae3c727484fc` |
| `leap-capacity-calendar` | `sha256:2ebddc35f227fb478f4ca73d1648fdc08a298fb6b5d81958be10b0cf43e99e27` |
| `leap-coverage-segments` | `sha256:2156e0e0f6141f59a54a1b26e1ab59d0113abad46a5f4ea612d0149a03c06d56` |
| `leap-maintenance-ledger` | `sha256:6a977ebbe4024273141d59bdf53a5fde70cafeaf1db0055e4b5d35ce9e1001e3` |
| `leap-policy-replay` | `sha256:4375f0f22ad2a86f9cffe7039b757054e2dd4c936d654a0ba6c6ce4acbca5d14` |
| `leap-shift-matching` | `sha256:65912beb68a5353713673467b5d9b07e7de3066ffb36efc53b127e14844360e7` |

The five predecessor hashes remain in the corresponding planned remedy
records. Any mismatch with these owner/replacement hashes forces regeneration
and a fresh Docker receipt.

Run:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_leap_year_rule_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

The mutable evidence lives under the generated sibling `.state/` directory:
per-root remedies, `materialization-manifest.json`, coherent controls, and
`docker-sanity-receipt.json`. Those records contain exact before/after tree
hashes, owner/reference hashes, test counts, semantic comparisons, and the
strongest truthful local status for the final tree. Dataset handoff remains
`not_requested`.
