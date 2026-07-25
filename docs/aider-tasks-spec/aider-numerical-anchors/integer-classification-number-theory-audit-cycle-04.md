# Integer Classification And Number Theory: Independent Audit Cycle 04

Status: `not_completed`. Exact task-local passing count: 40. Exact cycle-04
retained count: 0. Dispositions: 40 `review`, 0 `retain`, 0
`repair-and-reverify`, 0 `reject`, and 0 `eval-only`.

Exact blocker: the external expansion-v1 comparison corpus changed repeatedly
during the bounded final audit, including after apparently stable snapshots.
The 40 audited roots themselves are frozen and pass every task-local gate, but
cycle 04 cannot bind a terminal contamination decision to a stable complete
external inventory. No defect in a candidate task is currently known.

This is a fresh, read-only audit of the exact local Aider task family. It does
not inherit cycle 03's desired verdict. It does not create JSONL, select a
dataset split, establish tokenizer or assistant-loss-mask evidence, authorize
training, or claim benchmark uplift. The only repository artifact written by
this cycle is this report.

## Frozen behavior contract

The audited behavior is forty independent, stateless C++17 whole-file tasks.
For each task the model receives introduction/instructions plus one editable
header and source file, and must implement the named bounded number-theory
routine. Every routine returns the exact four-field `Result` contract
(`valid`, `member`, `value`, and `witness`). Invalid input must return the
specified sentinel; valid false classifications are not errors; value/witness
ordering and tie behavior are exact. Prompt-visible files may not expose
private tests, references, negative fixtures, build files, provenance, or
state. Evaluation replaces both editable files with a candidate or reference,
then requires strict compilation, visible/private behavior, a coherent wrong
implementation that passes the visible case but fails its named discriminator,
and fresh normal plus ASan/UBSan CTests in the pinned network-disabled image.
Generalization is across distinct bounded classification, factorization,
congruence, sequence, digit/base, valuation, and Diophantine contracts rather
than paraphrases of one executable task.

## Exact subject freeze

Audited root:
`.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/integer-classification-number-theory/`

The root contains exactly 918 regular files: 600 non-state task files (15 per
root) and 318 state/history/control/remedy/verification files. There are no
symlinks or hardlink aliases.

Cycle 04 uses this explicit reproducible algorithm:

1. enumerate every regular file recursively;
2. encode its path relative to the audited root as a POSIX UTF-8 path;
3. sort records bytewise by that relative path;
4. for each file emit lowercase `SHA256(file-bytes)`, two ASCII spaces, the
   relative path, and one LF;
5. SHA-256 the concatenated record stream.

The resulting exact subject is:

`sha256:88c86864d4034f55cb08d08cf1088fb8b3465d3cf6432d9f80d1629ce517211e`

The generator's state-excluding path/NUL/content/NUL tree hash remains:

`sha256:cd8c118c907f04af98068f666f777482a2f8d29596d8e776482a1ade91585504`

### Reconciliation with cycle 03

Cycle 03 reported the same 918-file count and state-excluding tree hash but
published `sha256:049c65f4f9dd37cedf7f15a70b7b2a1cbbd5d4f138f93a34f153015ab81bc389`
as the result of the algorithm above. That value is not reproducible from the
current bytes using the stated algorithm. This is a cycle-03 hash-reporting
error, not evidence of family drift: every cycle-03 listed curriculum, owner,
test, plan, manifest, preflight, diversity, inventory, Docker, runtime, and
cycle-ledger digest remains byte-for-byte identical, the root still contains
918 files, all 600 owner-rendered task files match regeneration, and the
state-excluding tree hash is unchanged. Cycle 04 therefore supersedes only the
misreported all-file subject identity; it does not silently reuse it.

| Input/evidence | SHA-256 |
| --- | --- |
| curriculum revision 3 | `572967c6d030ff098665768d481e64405f2a58ddda05280afec264e840d869d7` |
| cycle-02 remedy specification | `6c65920a8dd8fa4a88a91c88d3fc5acca03fe6e0a85a190e6f8876561bb3e1fa` |
| owner/generator | `26ee48438cdb31750a644974d86d554cbebab2d7f1bdcf7f631fe0f86d288b83` |
| focused tests | `eefb7bf9084193a8567a4d7bb881feb2c134bae4471f26258b67eefcbc1ede27` |
| 2,500-task count plan | `1eb72a6ff9df0311b4a83712789f6259da046e83dcf26f0603e8f1860c8b6acf` |
| family manifest | `d1c523f5f8a25304f120c7b0faca99e06c074d163db04038fef9ceaca377fb9e` |
| historical creator preflight | `aa87de95acdb75b04ae6d349f3342a5c1bfb6d27fe49884ba572b2905a8e45a8` |
| retained-pair diversity receipt | `202285727021b775fdaf7687b7c6d0e5dbb4bbbecd8ddd785c5b0e32a3eeb96a` |
| historical cross-corpus screen | `b01973e0c3366a51c5f977c535789bf07d7918e58057abe70e6d739a9b2ae2ab` |
| historical source inventory | `1b7b1e42b708b9325256f3539924901ef6dc2b48517b3069fc9f77ba0b3096a6` |
| Docker sanity receipt | `e99ccf615aaf5d72584f9369fe9235ab67988ccba7206fb4ddd7e671bfb5eb9c` |
| runtime receipt | `7f715269e4505344949ba3f9e6934cf09ecb005f290e70f91704f981313b558f` |
| cycle ledger | `6714b60151a5b31bd1221794907162478dfc0bb3a659654588b839c8a0e58f47` |

Any subsequent family, owner, policy, oracle, or comparison-inventory change
makes this report stale.

## Independent gate results

- Exactly 40 unique IDs and task roots exist only under the authorized family.
  There is no candidate-ID collision in either prior generated tree, the rest
  of expansion-v1, or the 26 holdouts. No old root was overwritten or used as
  semantic lineage.
- A disposable owner render produced 600 expected task files; all 600
  byte-match the audited task files. Forty configs have exact solution,
  example, and test roles. All prompt-visible files are nonempty and contain
  the exact `valid`/`member`/`value`/`witness` contract without private role or
  reference leakage.
- Forty coverage ledgers bind exactly 225 executable private assertions: 73
  valid-member, 72 valid-nonmember, and 80 invalid-input bindings. They include
  exactly 40 published-upper-bound, 40 above-upper-bound, 40 ordering/tie, and
  40 named-negative bindings. Each ledger's arguments and four expected fields
  occur in the private test; its named negative assertion occurs in the
  dedicated negative-rejection test.
- Every reference and every coherent task-specific negative byte-matches the
  owner render. Every negative differs from its reference, compiles, passes the
  visible smoke, and is rejected by the named private discriminator.
- `k-almost-prime-membership` has the exact `(72,1)` contract in both the full
  private oracle and negative test: `{valid=true, member=false, value=5,
  witness=3}`. Its current reference has no early `total > k` exit.
- The focused suite passed independently in disposable pytest/cache roots:
  `15 passed in 15.78s`.
- A new cycle-04 Docker execution mounted the repository read-only and used
  `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
  with `--network none`. All 40 tasks and all three controls independently
  passed four normal and four fresh ASan/UBSan CTests (`N4/S4`). Nothing from
  that run was written to the audited tree. This independently confirms the
  existing receipt's 43-record N4/S4 result, GCC 13.4.0/CMake 3.25.1 identity,
  negative outcomes, owner hash, and non-state tree hash.
- All 780 unordered retained-root pairs were recomputed from emitted docs,
  header, reference, private test, coverage, and negative artifacts. Every pair
  differs in all seven required dimensions and remains below the aggregate
  threshold; maximum aggregate Jaccard is `0.6955948298601952`.
- The three real-artifact controls are all changed and rejected by the same
  production decision. Aggregate similarities are `0.9506060606060606`
  (domain rename), `0.9741219963031423` (constants/policy), and
  `0.9598528961078762` (opposite endpoint), each above the clone floor where a
  dimension match had not already rejected it.
- All 40 cycle-02 remedy records bind the current generator, exact current task
  tree, a distinct before-tree hash, the invalidated cycle-02 subject, and the
  remedy specification. All 40 verification records bind their remedy record,
  current task tree, and Docker receipt. Preserved history contains
  `pre-remediation-cycle-01`, `pre-remediation-cycle-02`, and the separate
  `cycle-02-regeneration-attempt-01`; no current record overwrote history.

## Current duplicate and contamination screen

The saved creator screen remains valid evidence for the family bytes and the
inventory revision present when creator preflight ran, but it is not the
current external inventory receipt. Expansion-v1 has since replaced 62
same-count external paths with 62 different paths. Accordingly, its saved
source/surface digests
(`sha256:f499ebf6d31a16b0e1057491af9137b575db4c180795d2d3877d93a395d92c6d`
and
`sha256:d9938d389db36429ef673f9d905ae99fdc84f6f9bfad0d81c62eb7213b4542e1`)
must not be presented as the live revision.

Cycle 04 repeatedly waited for the live inventory to stabilize and performed
complete screens, but the apparent stable points did not remain stable through
the bounded final check. Observed full-inventory surface digests included
`sha256:6216f2be2328f99abd762059843f400ff85054604f36a4d8873302e163d5f313`,
`sha256:d77a98ab84ce9a9d832ea99ff4578f00b3d87a4036b9c8406e4f0282a9438831`,
`sha256:77153578bf9b14883588aa6e5687707bf14fe03d2907ba3fd1ccd3840199d7f8`,
`sha256:ca519fe18df0079c7c8db4248b37f589b4668813d8f6a1753f05cf03b3794b66`,
`sha256:2bb1134b17d83e4db23766e058494d0a88bf76ae30f79d4df76d1ae60d8fbbc8`,
and
`sha256:c25396e83cf4fde681ac9a48e193ee55faae03cf4e0138458730401c22d7a2c0`.
Intermediate enumerations also observed 3,014, 3,021, and 3,036 sources before
returning to 3,091. This is active external-corpus mutation, not a path-filter
artifact.

The bounded final check recorded 3,091 sources with source digest
`sha256:f19287f41d2d7e735d29040eaedd9dd018f2b07a09f07d36a2bfe3a5919114d7`
and surface digest `sha256:ca519fe18df0079c7c8db4248b37f589b4668813d8f6a1753f05cf03b3794b66`
at both `2026-07-22T10:13:52.063390+00:00` and
`2026-07-22T10:14:05.552217+00:00`. A subsequent complete screen had stable
before/after surface digest `sha256:2bb1134b...`; another exact snapshot at
`2026-07-22T10:16:47.517853+00:00` had changed again to
`sha256:c25396e83cf4fde681ac9a48e193ee55faae03cf4e0138458730401c22d7a2c0`
with the same 3,091 count and source digest. Two matching samples were therefore
not sufficient to establish quiescence.

The latest complete screen was internally stable between its before/after
snapshots and had the following point-in-time result:

| Evidence | Result |
| --- | --- |
| prior generated roots | 1,440 exactly (731 + 709) |
| other expansion-v1 roots | 1,625 |
| official holdouts | 26 exactly |
| total comparison sources | 3,091 |
| point-in-time source-list digest | `sha256:f19287f41d2d7e735d29040eaedd9dd018f2b07a09f07d36a2bfe3a5919114d7` |
| point-in-time five-surface inventory digest | `sha256:2bb1134b17d83e4db23766e058494d0a88bf76ae30f79d4df76d1ae60d8fbbc8` |
| candidate/source comparisons | 123,640 |
| prompt/API/reference/tests/lineage comparisons | 618,200 |
| maximum semantic Jaccard | `0.3004694835680751` |
| maximum pair | `consecutive-sum-profile` vs `numerical/bit-set-reasoning/bit-first-zero-run` |
| exact/normalized/semantic failures | 0 |

Every complete point-in-time screen found no ID, prompt, API, reference, test,
lineage, or semantic overlap, including the latest 123,640-comparison screen.
That is useful evidence but does not substitute for a stable terminal freeze.
The stale creator-inventory receipt plus continuing live-inventory mutation is
therefore a hard cycle-04 blocker under `local_family_verified`. The exact next
gate is to quiesce expansion-v1 writes, enumerate one complete 1,440-prior plus
expansion plus 26-holdout inventory, run the production five-surface screen,
and confirm the same source and surface digests again after comparison before
issuing a fresh audit.

## Composition and teaching value

All 40 roots are clean-room repository-authored, CC0-1.0, new-root lineage,
C++17, stateless, two-editable-file whole-edit tasks with deterministic exact
oracles. The capability composition is 13 factor/prime/classification roots,
7 modular/congruence roots, 6 sequence/figurate roots, 10 digit/base roots,
and 4 valuation/Diophantine/triple roots. Each contributes a distinct public
contract and a named plausible-but-wrong discriminator. The corpus does share
the four-field result schema and task scaffold by design; the emitted-artifact
pair gate and adversarial clones show that this common scaffolding has not
collapsed the family into template duplicates.

No SFT rows exist here, so tokenizer length, message-role order, assistant loss
masking, train/validation manifests, and row-level token buckets are inapplicable
to local-family verification and remain mandatory dataset-release gates. The
tasks are candidates, not a selected training mixture.

## Complete root catalog and dispositions

`N4/S4` means four passing normal and four passing fresh sanitizer CTests in
the new cycle-04 run. `A`, `D`, and `R` respectively denote passing exact
assertion/contract, diversity, and remedy-lineage gates. `C?` denotes the
unresolved stable-current-corpus contamination freeze; each point-in-time
screen passed, but the external subject continued changing.

| # | Root | Runtime | Gates | Disposition |
| ---: | --- | --- | --- | --- |
| 1 | `prime-interval-profile` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 2 | `factor-exponent-signature` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 3 | `semiprime-factor-pair` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 4 | `k-almost-prime-membership` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 5 | `squarefree-certificate` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 6 | `powerful-number-witness` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 7 | `smoothness-bound-profile` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 8 | `roughness-bound-profile` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 9 | `radical-square-kernel` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 10 | `liouville-parity` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 11 | `mobius-squarefree-sign` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 12 | `totient-density-class` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 13 | `carmichael-exponent-bound` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 14 | `multiplicative-order` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 15 | `modular-inverse` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 16 | `linear-congruence-solver` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 17 | `crt-pair-merge` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 18 | `quadratic-residue-witness` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 19 | `jacobi-symbol` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 20 | `primitive-root-verifier` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 21 | `fibonacci-index-membership` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 22 | `lucas-index-membership` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 23 | `triangular-index-membership` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 24 | `polygonal-index-membership` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 25 | `centered-polygonal-membership` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 26 | `consecutive-sum-profile` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 27 | `happy-cycle-class` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 28 | `narcissistic-base-class` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 29 | `kaprekar-split-witness` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 30 | `automorphic-suffix-class` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 31 | `harshad-quotient` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 32 | `smith-composite-class` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 33 | `emirp-reversal-class` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 34 | `palindromic-prime-base` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 35 | `additive-persistence` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 36 | `multiplicative-persistence` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 37 | `factorial-prime-valuation` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 38 | `binomial-base-trailing-zeros` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 39 | `linear-diophantine-class` | N4/S4 | A/D/C?/R | review (external inventory freeze) |
| 40 | `primitive-pythagorean-triple` | N4/S4 | A/D/C?/R | review (external inventory freeze) |

## Findings and terminal decision

- `ICNT-AUD-001` through `ICNT-AUD-008`: remain closed on the exact cycle-04
  subject. Prompt semantics, coherent negatives, assertion coverage, emitted-
  artifact diversity, complete prior-root inventory, exact `(72,1)` behavior,
  curriculum alignment, and remedy lineage all pass fresh inspection.
- `ICNT-AUD-009` (cycle-03 all-file hash reporting): resolved in this report.
  The prior value is not reproducible under its claimed algorithm; cycle 04
  publishes an explicit reproducible replacement and independently proves no
  family-content drift.
- `ICNT-AUD-010` (historical creator inventory revision): open. The historical
  receipt is retained honestly as prior-revision evidence and is not relabeled
  current. Fresh point-in-time screens pass, but repeated external-corpus
  changes prevent a terminal current-inventory receipt.

No target is known wrong, malformed, leaked, unverified, duplicated, or
lineage-conflicting. Nevertheless, cycle 04 is `not_completed`: all 40 roots
remain in `review` until a stable current external inventory can be frozen and
screened. Dataset projection, release, training, and model-validation gates
also remain out of scope.
