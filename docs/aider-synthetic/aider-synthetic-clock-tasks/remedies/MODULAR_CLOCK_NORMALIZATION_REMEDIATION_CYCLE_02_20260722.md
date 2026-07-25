# Modular Clock Normalization Remediation — Cycle 02

Status: **regeneration and fresh re-audit required**. This record binds the
owner response to fresh independent audit cycle 02. It does not admit dataset
rows, authorize training, or establish `local_family_verified` by itself.

## Bound audit

- Report: `docs/aider-synthetic/aider-synthetic-clock-tasks/audits/MODULAR_CLOCK_NORMALIZATION_FRESH_REAUDIT_CYCLE_02_20260722.md`
- Report SHA-256: `d16ed3e9d9262613e12604a5207592da60f17013d1dcadc9101d297f6319d1a1`
- Audited tree: `sha256:3771cdc12b009190261af4ae2e8b82297c2dbf461455ba5be80132956bee8492`
- Failed audit is preserved by append-only creation cycle 12.

## Owner remedies

### Strict-after overflow

`mcn-dual-cycle-rendezvous` no longer evaluates `gap / repeat + 1`
unchecked. It first computes the quotient, rejects `LLONG_MAX`, then performs
the increment. Its hidden oracle now calls
`next(LLONG_MAX, 0, 1, 0, 1)` and requires the declared empty overflow result
under non-recovering UBSan.

### Provenance-independent diversity

Provenance anchors remain evidence fields but no longer enter any of the seven
artifact dimensions or cap their scores. Within-family decisions use weighted
six-gram Jaccard over identifier-preserving artifact tokens. This retains
semantic API and contract vocabulary while remaining insensitive to comments,
strings, and literal-value padding. Cross-tree and official-holdout screening
take the maximum of identifier-preserving and identifier-neutral six-gram
similarity, so a domain rename cannot weaken contamination detection.

Every adversarial control now carries ordinary fresh new-root provenance. A
control is correctly rejected when at least one hard dimension collides: the
domain-identifier rename collides in the owned algorithm, mutation/selection,
and reference-control-flow dimensions, while constants/policy and
opposite-end controls collide in all seven. Changing provenance cannot change
the decision, which has a focused regression test.

### Semantic-duplicate replacement

`mcn-angular-dms-normalizer` is rejected as a domain-renamed duplicate of
`mcn-signed-hms-normalizer`. It is not renamed or retained. The mechanism-
distinct backfill `mcn-weighted-phase-histogram` Euclidean-normalizes signed
phases, checked-aggregates weights in ordered buckets, elides zero totals, and
atomically rejects overflow. Generator state preserves the rejected ID,
duplicate relation, replacement ID, and cycle-02 finding.

### Stable full-expansion binding

The complete cross-tree screen now takes a second inventory after all existing
roots have been read and compared. Any legacy, reverify, or expansion hash
change during the full screen fails closed and retries from a new snapshot.
Only a before/after-identical inventory can reach the creator receipt.

## Required closure evidence

- exactly 60 regenerated retained roots, including the backfill and excluding
  the rejected duplicate;
- all 1,770 retained pair decisions from task artifacts, with no provenance
  influence;
- three realistic fresh-provenance clone controls rejected;
- stable before/after full existing-tree inventory and all official holdouts;
- clean normal plus fresh non-recovering ASan/UBSan reference and negative
  evidence for all 60 roots and all controls;
- a passing focused test suite, a new append-only creator-preflight cycle, and
  a fresh independent audit of the exact regenerated hashes.

## Regenerated creator evidence

The first values below are preserved cycle-14 evidence and were superseded
after the shared expansion inventory changed. Cycle 15 preserves the later
full Docker receipt that was likewise followed by external inventory drift.
Neither is the subject of the next audit.

- retained tree: `sha256:8f0f96857f4c4fc9b08444dd3e047b29e1102b6e98fdd4801113cbda5d2e05f9`
- owner aggregate: `sha256:9f512d7609704bc281475a4062630f1ace5aa64aaf06df8ea689ff4271e3ad19`
- creator receipt internal: `sha256:77e160f029de9d13a284a94d72c36cd16a79756785454d903d4e1d612baed213`
- creator receipt file: `sha256:6c2a94da07f9d5deb288fe33f6e5ac8e39eaa6aacde27c97dbdb99049ccfd736`
- hard-rule screen file: `sha256:94176cece2d44a394c9043073e5dfc36d1d77222e0f53ceea3308716613112df`
- source-inventory file: `sha256:eba4d1fedb50911ec0e62ca5e5061a94e1cc76135ecdaf90370b640183194a55`
- inventory counts: 731 legacy, 709 reverify, 1,605 non-subject expansion
- comparisons: 1,770 within-family, 182,700 existing-tree, 1,560 official holdout
- Docker evidence: 60 roots with three normal and three fresh
  non-recovering sanitizer CTests each; all 60 compiled false substitutes
  rejected in both modes; three controls with two passing tests in both modes
- append-only cycle 13 preserves the sandbox Docker-socket denial; cycle 14
  records `remediated_creator_preflight_pass`, the rejected/replaced DMS root,
  the new retained set, and all four audit findings.

Fresh independent re-audit remains mandatory.

## Final refreshed audit subject

The generator validated every task and control tree hash against the preserved
Docker receipt, then reran the full external screen as the final gate. An
immediate independent inventory snapshot matched all three frozen hashes.

- retained tree: `sha256:8f0f96857f4c4fc9b08444dd3e047b29e1102b6e98fdd4801113cbda5d2e05f9`
- owner aggregate: `sha256:1f783dbec2f52c392e8b7ac1bad4d71a766c04e8163a2134b94543329ca74b75`
- creator receipt internal: `sha256:48ea7b2149a40519b26f11543820820055ec6727e9d693c98d7c3c16f3c79217`
- creator receipt file/snapshot: `sha256:af692f29d8710e1694c5bf5e558cda3cc17800b2d606f8eb9e148d6dee3fb125`
- materialization manifest: `sha256:2c46b1695f2430425216e2f8277413058cf62a541d74c1217ba6f13b020278c6`
- hard-rule screen: `sha256:19c8ec9bc06db1333d1412f6e3f74908fb52ef30eeef3c2764617b8ae4fa5ce2`
- source-inventory file: `sha256:9bc5f97c61f67cbe2660b3f6e6fe48f509141bd1ef5c3afafa7247f03a20b37c`
- live expansion inventory: 1,665 roots,
  `sha256:5580ac5ae40ea749f6c776f19860c7da86c4eb4f2720a7418f9e32bb92030cbe`
- append-only cycle 16: `sha256:2dcb0256cfdbd3a1b1c8cf739ef99c01bf91babd7be0eb378891b071e54aeb2b`
- focused tests on the remediated policy: `12 passed`

Cycle 16 is the only creator evidence nominated for the next fresh audit.
