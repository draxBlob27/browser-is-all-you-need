# Integer Classification And Bounded Number Theory Curriculum

Status: implementation-grade clean-room specification, revision 4. This
curriculum owns exactly 40 new roots in the `Integer classification and bounded
number-theory routines` cell of the 2,500-task count plan. It creates local task
candidates only: no JSONL, dataset release, training authorization, or benchmark
uplift follows from it.

## Identity and boundary

- Family ID: `integer-classification-number-theory-v1`.
- Output: `.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/integer-classification-number-theory/`.
- Owner: `src/w8_biayn/integrations/moonlight_integer_classification_number_theory_aider_tasks.py`.
- Focused tests: `tests/test_moonlight_integer_classification_number_theory_aider_tasks.py`.
- Creation prompt: `docs/aider-tasks-spec/prompts/generate-family-spec.md`.
- Implementation prompt: `docs/aider-tasks-spec/prompts/implement-family-for-sft.md`.
- Lineage: every retained ID below is a new root. Neither legacy generated tree
  is an output or a source of task semantics.
- License and provenance: repository-authored clean-room material, CC0-1.0.

The permanent 26-root Aider Polyglot C++ holdout is used only as a contamination
inventory. In particular, this family contains no perfect-number classifier,
base-conversion exercise, allergy/flag wrapper, or complex-number API.

## Public result contract

Every root owns a unique namespace and function declared in two editable files,
`<task-id>.h` then `<task-id>.cpp`. Its argument list is specified by the table.
All functions return:

```cpp
struct Result {
    bool valid;
    bool member;
    std::int64_t value;
    std::int64_t witness;
};
```

`valid=false` means an argument violated the published bound; the other fields
must then be `false, -1, -1`. For valid input, `member` is the advertised
classification. `value` and `witness` are task-specific, are stated in the
visible prompt, and are checked exactly. All arithmetic is C++17 integer
arithmetic. Floating-point tests, external commands, third-party number-theory
libraries, hard-coded examples, and unchecked overflow are forbidden.

## Fixed 40-root inventory

Each row is a distinct executable contract. The named bad substitute must
compile, satisfy the visible example, and be rejected by a private boundary or
counterexample.

| ID | Parameters | Core mechanism | Required private discriminator |
|---|---|---|---|
| `prime-interval-profile` | `lo, hi` | closed-interval trial division and greatest-prime selection | half-open or odd-endpoint scan |
| `factor-exponent-signature` | `n` | ordered prime-exponent extraction | distinct count used as multiplicity |
| `semiprime-factor-pair` | `n` | exactly-two multiplicity proof and ordered pair | any two divisors accepted |
| `k-almost-prime-membership` | `n, k` | complete exact total multiplicity | distinct factors counted |
| `squarefree-certificate` | `n` | first exponent-above-one certificate | only divisibility by four checked |
| `powerful-number-witness` | `n` | all prime exponents at least two | square-only or residual-blind check |
| `smoothness-bound-profile` | `n, bound` | largest prime factor versus inclusive bound | residual prime ignored |
| `roughness-bound-profile` | `n, bound` | smallest prime factor versus inclusive floor | largest factor substituted |
| `radical-square-kernel` | `n` | product of distinct primes and complementary quotient | multiplicity retained in radical |
| `liouville-parity` | `n` | total factor multiplicity parity | distinct-factor parity |
| `mobius-squarefree-sign` | `n` | square rejection then distinct parity | Liouville value on repeated factors |
| `totient-density-class` | `n` | multiplicative totient reduction | subtract-one-per-prime shortcut |
| `carmichael-exponent-bound` | `n` | prime-power lambda values joined by lcm | raw Euler totient |
| `multiplicative-order` | `a, modulus` | first-return modular orbit | unproved phi/modulus result |
| `modular-inverse` | `a, modulus` | normalized extended Euclid | division or non-coprime acceptance |
| `linear-congruence-solver` | `a, b, modulus` | gcd reduction then inverse | inverse required before reduction |
| `crt-pair-merge` | `r1, m1, r2, m2` | compatibility-gated generalized CRT | product modulus with assumed coprimality |
| `quadratic-residue-witness` | `residue, prime` | least modular square-root scan | symbol-only result without witness |
| `jacobi-symbol` | `a, odd_modulus` | binary reciprocity reductions | residue/primality interpretation |
| `primitive-root-verifier` | `generator, prime` | exact multiplicative-order verification | nonzero-only classification |
| `fibonacci-index-membership` | `n` | checked two-term recurrence | floating square identity |
| `lucas-index-membership` | `n` | Lucas seeds and ordered overshoot | Fibonacci seeds |
| `triangular-index-membership` | `n` | monotone triangular accumulation | rounded quadratic root |
| `polygonal-index-membership` | `n, sides` | growing-difference s-gonal recurrence | triangular/square-only policy |
| `centered-polygonal-membership` | `n, sides` | centered ring-size recurrence | ordinary polygonal formula |
| `consecutive-sum-profile` | `n` | positive-start length divisibility | zero/negative starts admitted |
| `happy-cycle-class` | `n` | explicit square-digit orbit and repeat table | fixed iteration cap |
| `narcissistic-base-class` | `n, base` | digit-count-dependent base power sum | decimal cubes for every input |
| `kaprekar-split-witness` | `n, base` | nonempty radix split of checked square | empty/zero right split |
| `automorphic-suffix-class` | `n, base` | full digit-width square suffix | last decimal digit only |
| `harshad-quotient` | `n, base` | radix digit sum and exact quotient | decimal digit sum in all bases |
| `smith-composite-class` | `n` | multiplicity-preserving factor digit sum | primes or distinct factors admitted |
| `emirp-reversal-class` | `n` | decimal reversal plus two prime proofs | palindromic primes admitted |
| `palindromic-prime-base` | `n, base` | radix reversal plus primality | decimal text in all bases |
| `additive-persistence` | `n, base` | repeated digit-sum descent | digital-root formula used as rounds |
| `multiplicative-persistence` | `n, base` | repeated digit-product descent | zero digits dropped |
| `factorial-prime-valuation` | `n, prime` | Legendre quotient layers | multiples of p counted once |
| `binomial-base-trailing-zeros` | `n, k, base` | factorial valuations over every base factor | decimal two/five-only rule |
| `linear-diophantine-class` | `a, b, c` | gcd divisibility with zero-pair handling | each coefficient required to divide c |
| `primitive-pythagorean-triple` | `a, b, c` | ordered square identity and three-way gcd | scaled triples or assumed argument order |

## Behavior, state, and bounds

The table and generated instructions jointly define normal, false-member,
invalid, empty/zero, boundary, ordering, and tie behavior. Factor lists are
ascending; first/least witnesses are deterministic; interval endpoints and
bounds are inclusive unless the task explicitly says otherwise. Functions do
not own persistent state and never mutate caller data. A false classification
is a valid result, not an error. Values outside the stated finite bounds are
invalid before any arithmetic. There are no duplicate records or absent keys;
the analogous cases are repeated factors, non-coprime congruences, and missing
sequence membership, all explicitly represented by `member=false`.

## Starter, reference, files, and roles

The starter returns only the invalid sentinel and is intentionally incomplete.
The independent reference emits only the helpers selected by that root and its
own algorithm body; it never dispatches through a family-wide mode switch.
References replace both editable files exactly. Visible tests contain one
boundary-bearing example. Private tests bind exact assertions for the visible
example, member and non-member behavior, invalid input, the published upper
surface, an input just above that surface, ordering/ties, and the named
counterexample. Every negative is a coherent task-specific algorithm mutation:
it compiles, passes the visible executable, and fails a dedicated one-assertion
negative test for the row's named semantic discriminator.

Prompt-visible files are limited to `.docs/introduction.md`,
`.docs/instructions.md`, and the two editable files. `.meta/example.*`, private
tests, negative fixtures, config, provenance, CMake, receipts, and `.state` are
private and must never appear in a prompt.

## Diversity and adversarial clones

The production screen reads emitted docs, API, reference, private oracle, and
negative descriptions. It checks all `40*39/2 = 780` unordered pairs and
requires a separate material difference in all seven dimensions:
`public_api`, `owned_state_or_algorithm`, `mutation_or_selection_rules`,
`invalid_and_boundary_behavior`, `reference_control_flow`,
`deterministic_oracle`, and `topic_specific_negative_fixture`.

Three coherent controls are materialized only beneath `.state`: a consistent
domain rename, a maximum-constant-only policy change, and a closed-to-half-open
endpoint change with updated reference/tests. Each changes real emitted files,
must compile in normal and sanitizer modes, and must be rejected by the exact
production evaluator through an identical dimension or the aggregate clone
floor.

## Build, oracle, and contamination gates

Each task uses C++17, Unix Makefiles, `c++`, and
`-Wall -Wextra -Wpedantic -Werror`. CTest discovers four tests: visible,
private, negative-visible smoke, and expected private rejection. The mandatory
Docker run uses the repository-pinned image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with `--network none`; normal and fresh ASan/UBSan discovery must both equal
four for all 40 roots and all three controls. The receipt binds compiler path,
version and binary hash, CMake, image, owner, exact tree, test counts, negative
outcomes, and network policy. This image provides `docker_sanity`, not a
family-designated locked oracle.

Admission also requires exact task-ID absence across both prior trees and the
rest of expansion-v1, no symlink/hardlink escape, all 1,440 prior config roots,
all 26 official holdout slugs, semantic comparisons over holdout and existing
visible contracts, and no exact prompt/reference/test hashes or reserved
lineage. The creator captures the complete five-surface inventory twice before
screening, screens only the frozen second capture, captures it again afterward,
and requires identical source counts, source-list digests, and surface digests
across all three observations. The receipt retains the frozen surface records;
a missing role surface or any inventory revision change fails closed.

## Acceptance and non-claims

Creator preflight requires owner regeneration, focused tests, prompt/role
validation, 780 conjunctive diversity passes, three rejected coherent controls,
cross-tree and holdout screens, and the mandatory Docker evidence. A read-only
independent audit must then catalog all 40 roots. Findings require immutable
records, owner repairs, full regeneration, and a fresh audit. Only a clean
fresh audit of the exact final tree may record `local_family_verified`.

No local completion is an SFT release, row projection, split, training
authorization, model evaluation, or benchmark-uplift claim.

## Docs Alignment (Remediation Docs Phase)

The model-facing `.docs` follow the official Aider Polyglot C++ conventions.
`.docs/introduction.md` is a `# <Title>` header plus a domain-motivating
narrative about integer classification questions; it never states the contract
or mentions the evaluation harness. `.docs/instructions.md` starts with
`# Instructions`, keeps the complete result contract (valid/member/value/
witness semantics, tie and bound rules, non-member diagnostics), the concrete
`Public boundary example:` line, and expresses the algorithm requirement
naturally ("Compute the result by <algorithm>: <how>. In particular,
<substitute> does not satisfy this contract.") instead of "Required
mechanism / Do not substitute" scaffolding. The generator's focused test
asserts this docs shape and rejects meta/audit vocabulary in both docs files.
