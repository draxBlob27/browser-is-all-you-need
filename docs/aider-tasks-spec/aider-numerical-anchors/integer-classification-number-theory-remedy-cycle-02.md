# Integer Classification And Number Theory Remedy Cycle 02

## Identity and immutable input

This cycle repairs all 40 roots in `integer-classification-number-theory-v1`
in place. Its immutable input is independent audit cycle 02, subject
`sha256:5dec634b096d9133a0ea4744433edaf3043fc487ae1faa6d1263082fc0bf2ef7`.
The open findings are `ICNT-AUD-001`, `ICNT-AUD-003`, `ICNT-AUD-005`,
`ICNT-AUD-006`, `ICNT-AUD-007`, and `ICNT-AUD-008`; cycle-02 findings
`ICNT-AUD-002` and `ICNT-AUD-004` remain closed. All dispositions are
`repair-in-place`; no root is renamed, copied, replaced, rejected, or added.

## Prompt and correctness repair

The 12 roots listed by `ICNT-AUD-001` state their exact boolean `member`
predicate independently of examples. `k-almost-prime-membership` performs a
complete factor-exponent sum before returning, including for non-members, so
`value` is always exact. The counterexample `(72, 1)` must return total
multiplicity five and greatest factor three.

## Executable requirement coverage

Every private oracle contains a valid published-upper-surface assertion and an
invalid just-above-upper assertion, in addition to member, non-member, invalid,
ordering/tie, public-example, and named-negative coverage. Each coverage ledger
binds requirement names to assertion IDs and exact expected tuples. A separate
one-assertion negative test binds the named coherent wrong substitute to its
specific counterexample; it must compile, pass the public example, and fail
that exact private assertion. CTest discovery remains four tests per root.

## Inventory and contamination repair

The cross-corpus screen must either normalize a configured test path to an
existing same-root role file or fail closed with `inventory_surface_missing`.
It may not silently omit a config root. The digest-bound source receipt must
include all 1,440 roots from the two prior generated trees, the remainder of
expansion-v1, and all 26 official holdouts before comparing prompt, API,
reference, test, and lineage surfaces.

## Evidence lineage

The revision-1 curriculum is superseded by its revision-3 contract. Existing
cycle-01 remedy records and cycle-02 receipts are preserved beneath immutable
history before regeneration. New remedy records bind the cycle-02 audit
subject, actual pre/post per-root hashes, current generator hash, this remedy
hash, and exact finding IDs. Runtime verification is written separately under
`.state/remedy-verification/`; it never overwrites the remedy record.

## Verification and endpoint

Regenerate all 40 roots through the owner, run focused and scope tests, require
all 780 emitted-artifact diversity decisions and all three adversarial-control
rejections, screen the complete inventory, and rerun all normal and fresh
ASan/UBSan tests in the pinned network-disabled Docker image. Only a subsequent
fresh independent audit of those exact artifacts may close this cycle and set
the strongest truthful status to `local_family_verified`. No JSONL, dataset
release, split, training authorization, model evaluation, or uplift claim is
part of this remedy.
