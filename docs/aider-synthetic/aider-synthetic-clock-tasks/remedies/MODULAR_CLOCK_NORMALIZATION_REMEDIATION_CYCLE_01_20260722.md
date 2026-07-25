# Modular Clock Normalization Remediation — Cycle 01

Status: `remediated_creator_preflight_pass`; fresh independent re-audit is
required. This record does not close its source audit and does not authorize a
dataset release or training.

## Immutable source finding set

- Source report:
  `docs/aider-synthetic/aider-synthetic-clock-tasks/audits/MODULAR_CLOCK_NORMALIZATION_INDEPENDENT_AUDIT_CYCLE_01_20260722.md`
- Audited subject:
  `sha256:178870b164782d3f1d59b076f388411f7e07e87077adbdc17fd42b2d938bafd3`
- Audited creator receipt:
  `sha256:9f1bb2dc238b2e9895964a2f09285e01b1ac3d99b8987490470124fc044a40a7`
- Findings remediated:
  `cycle-01/family/signed-modular-overflow`,
  `cycle-01/cyclic-range-family/boundary-coalescing-oracle-drift`,
  `cycle-01/mcn-dual-cycle-rendezvous/crt-mechanism-not-implemented`,
  `cycle-01/contracts/normalization-policy-drift`,
  `cycle-01/family/expansion-semantic-screen-omitted`, and
  `cycle-01/family/passing-preflight-cycle-unrecorded`.

## Owner changes

1. Added portable Euclidean residue, overflow-safe modular add/subtract,
   forward-distance, modular multiplication, and coefficient-safe modular
   inverse helpers. Replaced unsafe signed `difference + period` expressions,
   unchecked absolute lifts, and unchecked accumulators across the affected
   roots. Extreme `LLONG_MAX` discriminators cover the reproduced distance and
   CRT patterns.
2. Coalesced period/zero-connected pieces in both cyclic overlap and periodic
   cover, and aligned their deterministic tests and prompt contracts.
3. Replaced the dual-cycle linear scan with generalized non-coprime CRT and a
   checked strict-after ceiling lift; a billion-scale coprime-period case
   distinguishes it from enumeration.
4. Aligned modular mode with Euclidean-normalized samples and nearest-free with
   normalized/unique blocked phases plus an explicit one-million-period memory
   bound. Curriculum, instructions, references, tests, and clone controls now
   agree.
5. Extended the semantic screen to a frozen inventory of legacy, reverify, and
   every non-subject expansion root. It streams deterministic 64-bit six-gram
   fingerprints to avoid weakening the complete comparison under memory
   pressure and fails closed on inventory drift.
6. Preserved cycles 01–09, recorded a control-only failed remediation preflight
   as cycle 10, and appended cycle 11 binding the passing remediated creator
   preflight.

## Regenerated subject and evidence

| Evidence | Exact value |
| --- | --- |
| Regenerated tree | `sha256:3771cdc12b009190261af4ae2e8b82297c2dbf461455ba5be80132956bee8492` |
| Owner aggregate | `sha256:c111cc348699cfbbc7f27af35ed5ee871b6234d2c46de1902b38760ba87516f6` |
| Creator receipt internal hash | `sha256:9084ade8eb803c732604def2b43627bbb901a9a8eccca3cbda2ae6fb299b6bb2` |
| Creator receipt file hash | `sha256:c37b3b1a3cbd4f5e93ae43575f099c1dbf461474f43d1891db1d9a5b2ac7dd51` |
| Within-family hard-rule comparisons | 1,770 × seven dimensions, pass |
| Cross-tree comparisons | 182,700, pass |
| Cross-tree roots | 731 legacy + 709 reverify + 1,605 non-subject expansion |
| Official holdout comparisons | 1,560 across 26 roots, pass |
| Focused pytest | 11 passed |
| Normal Docker evidence | 60 × 3 CTests; 3 controls × 2 CTests, pass |
| Fresh sanitizer evidence | same positive counts under ASan/UBSan with `-fno-sanitize-recover=all` and `UBSAN_OPTIONS=halt_on_error=1`, pass |
| Topic negatives | 60 compiled false substitutes rejected in both modes |

The current disposition is `re_audit_required`. Only a fresh read-only audit
of the exact regenerated tree and receipt may set `local_family_verified`.
