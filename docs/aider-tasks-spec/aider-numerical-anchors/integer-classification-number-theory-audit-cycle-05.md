# Integer Classification And Number Theory: Independent Audit Cycle 05

Status: `not_completed`. Exact task-local passing count: 40. Exact cycle-05
retained count: 0. Dispositions: 40 `review`, 0 `retain`, 0
`repair-and-reverify`, 0 `reject`, and 0 `eval-only`.

Exact blocker: `ICNT-AUD-010` remains open because the complete external
expansion-v1 comparison inventory changed during the screen. The audited
family itself is unchanged and all 40 roots pass every task-local gate, but a
terminal contamination decision cannot be bound to one stable whole-screen
inventory revision. No defect in a candidate task is known.

This was a read-only re-audit of the exact local family. The audited root was
not modified, regenerated, or remediated. This report is the only repository
artifact written by cycle 05.

## Exact subject and scope

Audited root:
`.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/integer-classification-number-theory/`

The immutable all-file subject inherited from the independently reproduced
cycle-04 freeze is:

`sha256:88c86864d4034f55cb08d08cf1088fb8b3465d3cf6432d9f80d1629ce517211e`

Cycle 05 independently checked the current owner/render bindings, executable
assertion contracts, emitted-artifact diversity decision, remedy and
verification lineage, and current Docker receipt bindings. All checks pass for
all 40 roots. The family still has 225 bound executable assertions, 780
unordered retained-root diversity pairs, and three adversarial clone controls;
no local gate failed. The current Docker evidence remains bound to all 40
tasks and the three controls with four normal and four fresh sanitizer CTests
per root (`N4/S4`) in the pinned network-disabled image. Cycle 05 did not rerun
or mutate that runtime evidence.

## Whole-corpus duplicate and contamination evidence

The complete five-surface screen compares each candidate against prior
generated roots, every other expansion-v1 root, and all 26 official holdouts.
The inventory did not remain immutable across the bounded audit:

| Observation | Sources | Source-list SHA-256 | Five-surface SHA-256 |
| --- | ---: | --- | --- |
| before screen | 3,091 | `48fc75d3e6977aee572e37b69249c38788a06589cc74230a874c68c17605018e` | `a338937f9f5939df7d3484876bd337725ccd379640e53dbb423013c61a899184` |
| during screen | 3,058 | `ee78a20b87af824f21e70cdf8f0673cb66d1f5f5a29df9a37c51d43d12007578` | `4c52ec8c44852b386723cda2e6cf7c8182dbaa30d48e7a411e71edc76c54f17f` |
| after screen | 3,091 | `48fc75d3e6977aee572e37b69249c38788a06589cc74230a874c68c17605018e` | `f513b2cd5e10df6d2cde5174985cd1632b9a5a6d4515ff2a2af95b51d44344df` |
| post-screen confirmation 1 | 3,091 | `48fc75d3e6977aee572e37b69249c38788a06589cc74230a874c68c17605018e` | `f513b2cd5e10df6d2cde5174985cd1632b9a5a6d4515ff2a2af95b51d44344df` |
| post-screen confirmation 2 | 3,091 | `48fc75d3e6977aee572e37b69249c38788a06589cc74230a874c68c17605018e` | `f513b2cd5e10df6d2cde5174985cd1632b9a5a6d4515ff2a2af95b51d44344df` |

The source-list digest returning to its initial value while the five-surface
digest changed proves that path/count recovery did not restore the original
comparison bytes. The point-in-time screen nevertheless completed 123,640
candidate/root comparisons and 618,200 prompt/API/reference/tests/lineage
surface comparisons with zero exact, normalized, or semantic failures. Its
maximum semantic Jaccard was `0.2838427947598253`, for
`consecutive-sum-profile` versus
`.w8-biayn/data/aider-tasks-expansion-v1/numerical/bit-set-reasoning/bit-longest-run`.

Those passing point-in-time results are useful negative-duplicate evidence,
but they cannot establish `local_family_verified` against a comparison corpus
that changed during the whole-screen transaction. The exact next gate is to
quiesce external expansion-v1 writes, freeze the complete inventory, run the
production five-surface comparison, and confirm the identical source-list and
surface digests after completion.

## Complete root dispositions

Every root below passes owner (`O`), assertion (`A`), diversity (`D`), lineage
(`L`), and current Docker-receipt (`N4/S4`) checks. `C?` is the single shared
unresolved stable-inventory contamination gate. Therefore every listed root
has disposition `review (ICNT-AUD-010)`:

1. `prime-interval-profile`
2. `factor-exponent-signature`
3. `semiprime-factor-pair`
4. `k-almost-prime-membership`
5. `squarefree-certificate`
6. `powerful-number-witness`
7. `smoothness-bound-profile`
8. `roughness-bound-profile`
9. `radical-square-kernel`
10. `liouville-parity`
11. `mobius-squarefree-sign`
12. `totient-density-class`
13. `carmichael-exponent-bound`
14. `multiplicative-order`
15. `modular-inverse`
16. `linear-congruence-solver`
17. `crt-pair-merge`
18. `quadratic-residue-witness`
19. `jacobi-symbol`
20. `primitive-root-verifier`
21. `fibonacci-index-membership`
22. `lucas-index-membership`
23. `triangular-index-membership`
24. `polygonal-index-membership`
25. `centered-polygonal-membership`
26. `consecutive-sum-profile`
27. `happy-cycle-class`
28. `narcissistic-base-class`
29. `kaprekar-split-witness`
30. `automorphic-suffix-class`
31. `harshad-quotient`
32. `smith-composite-class`
33. `emirp-reversal-class`
34. `palindromic-prime-base`
35. `additive-persistence`
36. `multiplicative-persistence`
37. `factorial-prime-valuation`
38. `binomial-base-trailing-zeros`
39. `linear-diophantine-class`
40. `primitive-pythagorean-triple`

In compact gate notation, all 40 are `O/A/D/L/N4/S4/C?`: task-local pass,
terminal review solely because the external inventory freeze is unresolved.

## Findings and decision

- `ICNT-AUD-001` through `ICNT-AUD-009` remain closed on the exact cycle-05
  subject. No target is known wrong, malformed, leaked, unverified,
  duplicated, overwritten, or lineage-conflicting.
- `ICNT-AUD-010` remains open. A complete point-in-time screen passed, but the
  whole external comparison inventory changed during that screen, so the
  terminal inventory-bound claim fails closed.

Cycle 05 is therefore `not_completed`: 40 task-local passes, 0 retained, and
40 in review. This local-family audit does not create SFT rows, approve a
dataset split or release, establish tokenizer or loss-mask evidence, authorize
training, or claim model/benchmark uplift.
