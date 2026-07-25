# Integer Classification And Number Theory: Independent Audit Cycle 01

Status: `not_completed` (`40 repair-and-reverify`, `0 train`, `0 reject`,
`0 eval-only`). All 40 retained roots have unresolved hard gates. This is a
read-only audit of local task roots, not an SFT release or training-readiness
decision.

## Frozen audit subject

The audited family is
`.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/integer-classification-number-theory/`.
At audit time it contained 566 files: 520 non-state task files (13 per root)
and 46 state/control files. The immutable audit-subject hash is:

`sha256:aa2036aacb11c4bfa12acf4184744874f2043679aa657065fb456ae9d10bc5ab`

This hash is the SHA-256 of the sorted stream of `sha256sum` records for every
regular file below the family root, with paths relative to that root. The
generator's non-state tree hash is
`sha256:dfaf184cbe1bd2c3e2c627e0381e9d6e6da21f7e0dd18194e26d8607893dead1`.
Any change to a task, owner, policy, receipt, or state artifact makes this
report stale.

Companion inputs:

| Input | SHA-256 |
| --- | --- |
| curriculum | `18543211047ce6d1061c5dff83f4373edc7f704ea6abb9bb259173f273ceb2a4` |
| generator/owner | `c6602bfd6c822232e0e9b9c4941ace83194560815ac0e52b4af521f3627f772b` |
| focused tests | `d8adbbfdbe7c708e11ebdb363220fdb0b61a1854c0d73313abfc3c773e878957` |
| 2,500-root plan | `1eb72a6ff9df0311b4a83712789f6259da046e83dcf26f0603e8f1860c8b6acf` |
| family manifest | `737df44aac49f3d9dc6dae97960f8d10a7590ca9ec37221a9bbf446829e9271c` |
| creator preflight | `a0adef08cb51fa6d68a7af1ba2e96045df9943457071d52b52792931b228ff9e` |
| diversity screen | `975363d0321ba0207af049ffcc83b9ab7f8243cfd1541a3602c3dce9c1ce3f7a` |
| Docker sanity | `b113f11c401cf8db0a624c393d7232dbff97a97763430c5348f814ec128edf7b` |
| runtime receipt | `e76f2de3b53d5eddbce548a4530737d69841503e7bec178e5731db0d8a4a85a5` |
| cycle ledger | `c516509be50002abfb09954de2e327e2c49e7d74ef9539f642866c50bd8c2e2e` |
| clone-control manifest | `e83562a8048652fcd53d13d595ee30f0a0a49d787c9c2b789d3e6c1443a40538` |

## Behavior contract used by the audit

| Field | Audit contract |
| --- | --- |
| Task | Implement the named bounded classification or number-theory routine in the two declared C++17 editable files. |
| Inputs | Only the visible introduction, instructions, header starter, and source starter; no private tests, reference, build files, or receipts. |
| Output | Whole replacements for the declared header and source, preserving the namespace, function signature, and total four-field `Result`. |
| Invariants | Deterministic integer arithmetic; exact task-specific `member`, `value`, and `witness`; no floating point, hard-coded examples, external commands, or third-party number-theory libraries. |
| Failure behavior | Out-of-contract arguments return `{false,false,-1,-1}`; valid non-members remain valid and return the specified deterministic values. |
| Resource limits | Published finite bounds, signed 64-bit arithmetic, C++17, strict warnings, offline execution. |
| Evaluation | Visible and private deterministic tests, a coherent named wrong implementation, normal plus fresh ASan/UBSan execution, and network-disabled Docker sanity. |
| Generalization target | Forty distinct new roots in the plan's integer-classification and bounded-number-theory cell, without semantic lineage or benchmark-holdout duplication. |

## Confirmed evidence

- Structural accounting is exact: 40 unique manifest IDs, 40 task roots, 40
  configs, 40 provenance records, no symlinks, and no multiply-linked files.
  Each root has two visible docs, two editable starters, visible/private tests,
  complete two-file references, one negative source, CMake, test metadata,
  config, and provenance.
- Prompt-role inspection found no `.meta`, private-test, reference, CMake,
  provenance, or receipt leakage in the declared prompt files. The whole-file
  role mapping is structurally consistent in all 40 roots.
- The focused test file passed independently: `10 passed in 0.84s`.
- The network-disabled Docker receipt binds the intended image digest,
  GCC 13.4.0 compiler hash, CMake 3.25.1, owner hash, and non-state tree hash.
  It records 40 task and three clone-control builds, with four normal and four
  fresh sanitizer tests discovered and passing per root/control. This is valid
  build/sanitizer evidence, but it cannot compensate for weak semantic oracles.
- All 40 negative sources compiled, passed the public example, and were
  rejected by the current private binary. The audit does not accept that as
  the required discriminator because the implemented negative is the same
  generic visible-example hardcode in every root (finding ICNT-AUD-002).

## Root catalog and dispositions

`N4/S4` means the receipt records four normal and four sanitizer tests.
`P/N/O` means prompt-solvability, named-negative, and independent-oracle hard
gates; every entry fails all three for the reasons in ICNT-AUD-001 through
ICNT-AUD-003.

| # | Root | Capability tag | Runtime | Gates | Disposition |
| ---: | --- | --- | --- | --- | --- |
| 1 | `prime-interval-profile` | interval prime enumeration | N4/S4 | P/N/O fail | repair-and-reverify |
| 2 | `factor-exponent-signature` | prime multiplicity extraction | N4/S4 | P/N/O fail | repair-and-reverify |
| 3 | `semiprime-factor-pair` | factor-pair classification | N4/S4 | P/N/O fail | repair-and-reverify |
| 4 | `k-almost-prime-membership` | multiplicity threshold | N4/S4 | P/N/O fail | repair-and-reverify |
| 5 | `squarefree-certificate` | repeated-prime certificate | N4/S4 | P/N/O fail | repair-and-reverify |
| 6 | `powerful-number-witness` | exponent-floor classification | N4/S4 | P/N/O fail | repair-and-reverify |
| 7 | `smoothness-bound-profile` | largest-factor bound | N4/S4 | P/N/O fail | repair-and-reverify |
| 8 | `roughness-bound-profile` | smallest-factor bound | N4/S4 | P/N/O fail | repair-and-reverify |
| 9 | `radical-square-kernel` | radical/kernel decomposition | N4/S4 | P/N/O fail | repair-and-reverify |
| 10 | `liouville-parity` | multiplicity parity | N4/S4 | P/N/O fail | repair-and-reverify |
| 11 | `mobius-squarefree-sign` | square-free sign | N4/S4 | P/N/O fail | repair-and-reverify |
| 12 | `totient-density-class` | multiplicative totient | N4/S4 | P/N/O fail | repair-and-reverify |
| 13 | `carmichael-exponent-bound` | prime-power lcm | N4/S4 | P/N/O fail | repair-and-reverify |
| 14 | `multiplicative-order` | modular orbit | N4/S4 | P/N/O fail | repair-and-reverify |
| 15 | `modular-inverse` | extended Euclid | N4/S4 | P/N/O fail | repair-and-reverify |
| 16 | `linear-congruence-solver` | gcd reduction | N4/S4 | P/N/O fail | repair-and-reverify |
| 17 | `crt-pair-merge` | generalized CRT | N4/S4 | P/N/O fail | repair-and-reverify |
| 18 | `quadratic-residue-witness` | least modular root | N4/S4 | P/N/O fail | repair-and-reverify |
| 19 | `jacobi-symbol` | binary reciprocity | N4/S4 | P/N/O fail | repair-and-reverify |
| 20 | `primitive-root-verifier` | exact modular order | N4/S4 | P/N/O fail | repair-and-reverify |
| 21 | `fibonacci-index-membership` | sequence membership | N4/S4 | P/N/O fail | repair-and-reverify |
| 22 | `lucas-index-membership` | sequence membership | N4/S4 | P/N/O fail | repair-and-reverify |
| 23 | `triangular-index-membership` | figurate recurrence | N4/S4 | P/N/O fail | repair-and-reverify |
| 24 | `polygonal-index-membership` | parameterized figurate recurrence | N4/S4 | P/N/O fail | repair-and-reverify |
| 25 | `centered-polygonal-membership` | centered figurate recurrence | N4/S4 | P/N/O fail | repair-and-reverify |
| 26 | `consecutive-sum-profile` | positive-run enumeration | N4/S4 | P/N/O fail | repair-and-reverify |
| 27 | `happy-cycle-class` | digit-orbit cycle detection | N4/S4 | P/N/O fail | repair-and-reverify |
| 28 | `narcissistic-base-class` | base-digit power sum | N4/S4 | P/N/O fail | repair-and-reverify |
| 29 | `kaprekar-split-witness` | radix split witness | N4/S4 | P/N/O fail | repair-and-reverify |
| 30 | `automorphic-suffix-class` | radix suffix | N4/S4 | P/N/O fail | repair-and-reverify |
| 31 | `harshad-quotient` | radix digit sum | N4/S4 | P/N/O fail | repair-and-reverify |
| 32 | `smith-composite-class` | factor digit sums | N4/S4 | P/N/O fail | repair-and-reverify |
| 33 | `emirp-reversal-class` | decimal reversal/primality | N4/S4 | P/N/O fail | repair-and-reverify |
| 34 | `palindromic-prime-base` | radix reversal/primality | N4/S4 | P/N/O fail | repair-and-reverify |
| 35 | `additive-persistence` | digit-sum descent | N4/S4 | P/N/O fail | repair-and-reverify |
| 36 | `multiplicative-persistence` | digit-product descent | N4/S4 | P/N/O fail | repair-and-reverify |
| 37 | `factorial-prime-valuation` | Legendre layers | N4/S4 | P/N/O fail | repair-and-reverify |
| 38 | `binomial-base-trailing-zeros` | valuation bottleneck | N4/S4 | P/N/O fail | repair-and-reverify |
| 39 | `linear-diophantine-class` | Bezout divisibility | N4/S4 | P/N/O fail | repair-and-reverify |
| 40 | `primitive-pythagorean-triple` | identity and gcd | N4/S4 | P/N/O fail | repair-and-reverify |

## Findings

### ICNT-AUD-001 — public output contracts are not solvable from the prompt

Severity: hard gate. Scope: all 40 roots. Disposition: `repair-and-reverify`.

Every prompt uses the same sentence that `value` and `witness` have the
meanings "demonstrated by" one public example. It does not state those meanings
for the member, non-member, tie, or boundary cases. The reference frequently
returns information not inferable from the summary and single tuple: for
example a largest factor, factor count, first violating prime, reduced modulus,
overshoot value, cycle-repeat value, or tie-breaking factor. Multiple coherent
implementations therefore satisfy the visible prose but disagree with the
private tuple. This is evaluator-private target information, not a difficult
but specified task. The curriculum promises explicit task-specific output
semantics, so the emitted prompts do not implement their own contract.

Remedy: state the exact meaning of every result field for valid members and
valid non-members, including ordering and tie rules, without exposing tests or
reference code; then regenerate all 40 roots and invalidate every receipt.

### ICNT-AUD-002 — no declared plausible-but-wrong implementation is executed

Severity: hard gate. Scope: all 40 roots. Disposition: `repair-and-reverify`.

All 40 `.meta/negative.cpp` files implement a parameter equality check for the
one visible example, return its expected tuple, and otherwise return the same
generic `{true,false,0,-1}` tuple. None implements the root's declared named
mistake (distinct-versus-total multiplicity, half-open scan, ignored residual,
wrong radix, assumed coprimality, and so on). The focused test explicitly calls
this a `visible-case-only-hardcode`, while the curriculum requires a coherent
named algorithmic substitute. The Docker receipt proves only that the generic
hardcode is rejected; it does not prove that the tests discriminate the
plausible misconception the task claims to teach.

Remedy: generate a separate coherent negative implementation per root that
implements the named mistake, require clean compilation and visible pass, and
prove private rejection. A generic hardcode may be an additional mutation but
cannot replace the named discriminator.

### ICNT-AUD-003 — the private oracle is example replay, not requirement coverage

Severity: hard gate. Scope: all 40 roots. Disposition: `repair-and-reverify`.

Each private source contains exactly three fixed calls: the visible example and
two additional tuples. This does not cover the curriculum's normal, invalid,
duplicate/analogue, absent, boundary, ordering, and tie obligations, and it is
not an independently computed property oracle. Concrete omissions show that
this is not merely conservative scoring: `liouville-parity` has no valid
`member=true` case, and `crt-pair-merge` has no invalid-input case. Bounds and
tie/least-witness rules are generally asserted only in prose or provenance.
The reference passing those three tuples cannot establish answer correctness
or reject nearby coherent bugs.

Remedy: add deterministic property/independent-oracle coverage and explicit
material-requirement assertions per root; include both valid membership
branches where reachable, invalid minima/maxima, ordering/ties, and the named
negative's counterexample. Regenerate and rerun normal, fresh sanitizer, and
Docker evidence.

### ICNT-AUD-004 — seven-dimension diversity and clone rejection are tautological

Severity: family hard gate. Scope: production evaluator and all retained roots.
Disposition: `repair-in-place` in the owner, regenerate, and re-audit.

The 780-pair screen compares author-supplied provenance arrays. Several
dimensions contain a unique task ID, a hash of the owner-authored reference
body, or task-specific fixed samples, which force inequality without
demonstrating a material semantic difference. The three clone controls copy
the base provenance unchanged; the evaluator then rejects them because it
compares those copied signatures, not because it derives semantics from the
changed docs/reference/tests. Thus 780/780 `pass` and three/three `rejected`
are internally consistent but do not test the required seven dimensions.

Independent inspection found related clusters—factor multiplicity, square-free
signs, smooth/rough bounds, sequence/figurate membership, and digit
persistence—with intended distinct outputs, and found no exact retained pair.
That does not close the semantic-clone gate while outputs are under-specified
and the production screen is self-attested.

Remedy: derive dimension evidence from normalized emitted prompt/API/reference/
oracle/negative content, exclude IDs and raw hashes as novelty evidence, and
make the controls pass through exactly that derivation.

### ICNT-AUD-005 — cross-corpus contamination and lineage evidence is incomplete

Severity: family hard gate. Scope: creator receipt. Disposition:
`repair-in-place` in the owner, regenerate receipts, and re-audit.

The creator records 3,005 existing visible contracts, all 26 official holdout
roots, 121,240 prompt-token comparisons, and maximum Jaccard
`0.15037593984962405`. Its implementation screens exact IDs and a token set
from instructions, but does not bind an immutable source-inventory digest and
does not perform the promised normalized prompt, answer/reference, test/API,
or semantic-lineage comparisons. Consequently the receipt cannot show which
revisions were compared or detect a renamed executable contract with disjoint
surface tokens.

As an independent check for this cycle, the 40 IDs did not collide with the
two prior trees or the other expansion roots; 320 unique candidate role-file
hashes had zero exact matches among 33,841 unique files from those trees plus
the holdout inventory. Manual holdout review found no perfect-number,
all-your-base conversion, allergies/flags, or complex-number contract. These
are useful negative observations, not a substitute for the missing normalized
cross-corpus and inventory-bound gate.

Remedy: persist digest-bound inventories of both prior trees, the rest of the
expansion, and all 26 holdouts; compare exact and normalized prompt composites,
references/answers, tests, APIs, task IDs, and semantic lineage; include the
policy and result digests in the creator receipt.

## Duplicate, lineage, and contamination dispositions

- Exact candidate IDs: 40 unique; exact collisions observed: 0.
- Exact candidate role-file hashes against existing/holdout files: 0.
- Declared lineage: 40 `new-root`; no ancestor/replacement relation was found.
- Exact within-family prompt/reference/test duplicate: none observed.
- Related-concept pairs are not rejected at this cycle, but all remain
  `repair-and-reverify` because their executable distinctions are not yet
  prompt-solvable or validated by a sound seven-dimension screen.
- Benchmark contamination: no positive match found; gate remains unresolved
  under ICNT-AUD-005 because the evidence policy is incomplete.

## Corpus composition and scope limits

The 40 roots are repository-authored, clean-room, CC0-1.0, synthetic, C++17,
stateless, deterministic, two-file whole-edit tasks. Composition is 13
prime/factor-function roots (1–13), seven modular/congruence roots (14–20), six
sequence/figurate roots (21–26), ten digit/base classification roots (27–36),
and four valuation/equation roots (37–40). All use the same four-field result
shape and the same three-example private-test template, producing a strong
format and oracle monoculture despite topic variety.

Tokenizer, assistant-loss masking, split selection, JSONL row shape, and model
context length are not applicable at this local-family stage: no dataset
release or row projection was authorized. No train/validation manifests are
created by this audit.

## Terminal decision

This exact cycle cannot reach `local_family_verified`. Findings
ICNT-AUD-001 through ICNT-AUD-005 are open; every root is
`repair-and-reverify`. Remediation must preserve this report unchanged, repair
the curriculum/owner/focused tests, regenerate the complete 40-root family,
invalidate the subject and creator receipts above, and submit the new exact
tree to a fresh independent audit. No SFT release, training authorization, or
benchmark-uplift claim follows from this report.
