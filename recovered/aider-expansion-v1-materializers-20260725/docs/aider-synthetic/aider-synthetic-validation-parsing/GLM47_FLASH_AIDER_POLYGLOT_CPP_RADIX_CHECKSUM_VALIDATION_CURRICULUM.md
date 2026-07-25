# Radix And Checksum Validation Expansion Curriculum

Status: executable clean-room creation contract for exactly 100 new local task
roots in the binding validation/parsing count-plan cell “Radix, digit alphabet,
position-weighted, and checksum validation.” This document is the output of
`docs/aider-tasks-spec/prompts/generate-family-spec.md`. It creates no SFT
rows, dataset release, training authorization, or benchmark-uplift claim.

## Identity and output boundary

- Family ID: `aider-expansion-radix-checksum-validation-v1`.
- Lineage: every retained task is a new root with no parent or replacement.
- Owner: `src/w8_biayn/integrations/moonlight_radix_checksum_validation_aider_tasks.py`.
- Focused test: `tests/test_moonlight_radix_checksum_validation_aider_tasks.py`.
- Selected creation prompt: `docs/aider-tasks-spec/prompts/generate-family-spec.md`.
- Selected implementation prompt: `docs/aider-tasks-spec/prompts/implement-family-for-sft.md`.
- Generated root:
  `.w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/radix-checksum-validation/`.
- Mutable manifests, controls, receipts, audits, and cycle records live only in
  that family's `.state/` directory and never count as task roots.
- Required retained count: exactly 100.

The owner must refuse both existing generated trees as output, refuse any
output outside the exact expansion family, reject symlinks or hardlinks into
an existing tree, reserve IDs across all three generated trees, and compare
normalized contracts, APIs, references, tests, and oracle logic before it
materializes a candidate. `--force` may replace only roots whose provenance
names this owner; it may not weaken collision or semantic-lineage checks.

## Common whole-file contract

Each task exposes a task-local `Input`, task-local `Policy`, `Audit`, and one
static `Validator::inspect` operation in namespace `radix_checksum`. The model
receives the visible contract plus exactly `<task-id>.h` and `<task-id>.cpp`.
It returns complete replacements for those two files in order. Tests,
references, CMake, provenance, manifests, receipts, and controls are private.

`inspect` validates the complete digit representation before checksum
arithmetic. Invalid alphabets, bases, positions, widths, duplicate sparse
positions, malformed tokens, empty payloads, digit-range violations, invalid
policy moduli, arithmetic overflow, and trailing/unconsumed material return a
non-accepted audit with the first bad position and no partial accepted value.
For a well-formed representation it derives the canonical digit sequence and
numeric value, computes the named checksum using overflow-safe integer
operations, and accepts only an exactly matching claimed check value.

The official Aider `all-your-base` task is a permanent holdout. No task in
this family converts an arbitrary digit sequence between caller-selected
bases, and no task may copy its wording, API, tests, reference, or semantic
contract. The other 25 official C++ roots are equally permanent holdouts.

## Ten substantive radix/input mechanisms

The prefix in the first column is part of every generated task ID. The owned
input state and decoder are reflected in the public `Input` shape, reference
control flow, boundary tests, and negative fixture; they are not labels.

| Prefix | Required mechanism | Required invalid/boundary behavior |
| --- | --- | --- |
| `alphabet` | Scan a caller-supplied unique symbol alphabet, map each character exactly once, and checked-Horner accumulate. | Reject alphabet sizes outside 2–36, duplicate symbols, unmapped symbols, empty text, and overflow. |
| `digits` | Validate a fixed-radix integer digit vector and checked-Horner accumulate it. | Reject radix outside 2–36, empty input, out-of-range digits, and a forbidden leading zero. |
| `mixed` | Validate one radix per position and accumulate a heterogeneous mixed-radix word. | Reject length mismatch, any radix below two, out-of-range digits, empty input, and overflow. |
| `balanced` | Validate signed digits in the centered interval of an odd radix and accumulate them without coercion. | Reject even/small radices, digits outside `[-r/2,r/2]`, empty input, and overflow. |
| `bijective` | Interpret digits in `1..radix`, with zero forbidden, using checked bijective positional accumulation. | Reject radix outside 2–26, zero/out-of-range digits, empty input unless explicitly allowed, and overflow. |
| `negabase` | Accumulate canonical nonnegative digits under a caller-supplied base at most `-2`. | Reject nonnegative bases, excess width, out-of-range digits, empty input, and overflow. |
| `packed` | Extract a fixed number of equal-width bit groups from a packed word in declared high/low order. | Reject zero or over-wide groups, count/width products above 64, unused nonzero high bits, and zero groups. |
| `tokens` | Map a token vector through an exact, duplicate-free token alphabet before positional accumulation. | Reject duplicate/empty alphabet tokens, unknown tokens, empty payloads, and optional case-fold collisions. |
| `sparse` | Validate unique explicit digit positions, reconstruct missing zeros, then accumulate from the highest declared position. | Reject duplicate/out-of-range positions, width zero, out-of-range digits, and missing most-significant content. |
| `unary-runs` | Convert separated repeated-mark runs to bounded digit lengths before checked positional accumulation. | Reject the separator as a digit mark, zero/over-radix run lengths, adjacent incompatible marks, empty input, and overflow. |

## Ten substantive checksum mechanisms

The suffix in the first column is part of every generated task ID. Each policy
has a structurally different public shape and each reference expands the
algorithm directly; no generic checksum dispatcher is emitted.

| Suffix | Required mechanism | Coherent plausible-but-wrong substitute that production tests reject |
| --- | --- | --- |
| `weighted` | Cyclic position weights with explicit left/right anchoring and Euclidean residue. | Anchor weights at the wrong end. |
| `alternating` | Alternate two factors from a declared end, folding each product before summation. | Alternate from the other end without compensating parity. |
| `luhn-fold` | Double selected positions, fold by the digit radix, then take the declared modulus. | Subtract a decimal constant regardless of radix. |
| `fletcher-pair` | Maintain two modular running sums and combine the ordered pair. | Return only the first running sum. |
| `adler-pair` | Seed the first accumulator, include optional length, then combine both residues. | Reset the seed after the first digit. |
| `polynomial` | Evaluate a coefficient-driven rolling polynomial with a checked initial state. | Sum coefficients and digits independently. |
| `crc-bits` | Feed canonical digit bits through a width-bounded polynomial register with optional reflection. | XOR whole digits without bit division. |
| `quasigroup` | Walk a validated square transition table and return the terminal state. | Use digit-sum modulo table order. |
| `complement` | Form an index-aware residue and return the complement needed to hit a target residue. | Return the residue itself. |
| `diagonal` | Traverse a row/column layout with zigzag selection and row weights before modular reduction. | Flatten and apply one constant weight. |

## Exact 100-root inventory

The family is the complete Cartesian product of the ten rows above and the
ten checksum columns below. This matrix explicitly reserves every task ID;
there are no implicit or optional roots.

| Radix/input | weighted | alternating | luhn-fold | fletcher-pair | adler-pair | polynomial | crc-bits | quasigroup | complement | diagonal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| alphabet | `rcv-alphabet-weighted` | `rcv-alphabet-alternating` | `rcv-alphabet-luhn-fold` | `rcv-alphabet-fletcher-pair` | `rcv-alphabet-adler-pair` | `rcv-alphabet-polynomial` | `rcv-alphabet-crc-bits` | `rcv-alphabet-quasigroup` | `rcv-alphabet-complement` | `rcv-alphabet-diagonal` |
| digits | `rcv-digits-weighted` | `rcv-digits-alternating` | `rcv-digits-luhn-fold` | `rcv-digits-fletcher-pair` | `rcv-digits-adler-pair` | `rcv-digits-polynomial` | `rcv-digits-crc-bits` | `rcv-digits-quasigroup` | `rcv-digits-complement` | `rcv-digits-diagonal` |
| mixed | `rcv-mixed-weighted` | `rcv-mixed-alternating` | `rcv-mixed-luhn-fold` | `rcv-mixed-fletcher-pair` | `rcv-mixed-adler-pair` | `rcv-mixed-polynomial` | `rcv-mixed-crc-bits` | `rcv-mixed-quasigroup` | `rcv-mixed-complement` | `rcv-mixed-diagonal` |
| balanced | `rcv-balanced-weighted` | `rcv-balanced-alternating` | `rcv-balanced-luhn-fold` | `rcv-balanced-fletcher-pair` | `rcv-balanced-adler-pair` | `rcv-balanced-polynomial` | `rcv-balanced-crc-bits` | `rcv-balanced-quasigroup` | `rcv-balanced-complement` | `rcv-balanced-diagonal` |
| bijective | `rcv-bijective-weighted` | `rcv-bijective-alternating` | `rcv-bijective-luhn-fold` | `rcv-bijective-fletcher-pair` | `rcv-bijective-adler-pair` | `rcv-bijective-polynomial` | `rcv-bijective-crc-bits` | `rcv-bijective-quasigroup` | `rcv-bijective-complement` | `rcv-bijective-diagonal` |
| negabase | `rcv-negabase-weighted` | `rcv-negabase-alternating` | `rcv-negabase-luhn-fold` | `rcv-negabase-fletcher-pair` | `rcv-negabase-adler-pair` | `rcv-negabase-polynomial` | `rcv-negabase-crc-bits` | `rcv-negabase-quasigroup` | `rcv-negabase-complement` | `rcv-negabase-diagonal` |
| packed | `rcv-packed-weighted` | `rcv-packed-alternating` | `rcv-packed-luhn-fold` | `rcv-packed-fletcher-pair` | `rcv-packed-adler-pair` | `rcv-packed-polynomial` | `rcv-packed-crc-bits` | `rcv-packed-quasigroup` | `rcv-packed-complement` | `rcv-packed-diagonal` |
| tokens | `rcv-tokens-weighted` | `rcv-tokens-alternating` | `rcv-tokens-luhn-fold` | `rcv-tokens-fletcher-pair` | `rcv-tokens-adler-pair` | `rcv-tokens-polynomial` | `rcv-tokens-crc-bits` | `rcv-tokens-quasigroup` | `rcv-tokens-complement` | `rcv-tokens-diagonal` |
| sparse | `rcv-sparse-weighted` | `rcv-sparse-alternating` | `rcv-sparse-luhn-fold` | `rcv-sparse-fletcher-pair` | `rcv-sparse-adler-pair` | `rcv-sparse-polynomial` | `rcv-sparse-crc-bits` | `rcv-sparse-quasigroup` | `rcv-sparse-complement` | `rcv-sparse-diagonal` |
| unary-runs | `rcv-unary-runs-weighted` | `rcv-unary-runs-alternating` | `rcv-unary-runs-luhn-fold` | `rcv-unary-runs-fletcher-pair` | `rcv-unary-runs-adler-pair` | `rcv-unary-runs-polynomial` | `rcv-unary-runs-crc-bits` | `rcv-unary-runs-quasigroup` | `rcv-unary-runs-complement` | `rcv-unary-runs-diagonal` |

For each matrix cell, the complete C++17 API consists of the radix row's
task-local `Input` fields, the checksum column's task-local `Policy` fields,
`Audit { accepted, bad_index, numeric_value, expected_check, digit_count }`,
and `Validator::inspect(const Input&, long long claimed, const Policy&)`.
The two selected mechanisms together define owned state, valid and invalid
inputs, mutation/selection behavior, reference control flow, deterministic
oracle, and the named negative. No cell may delegate either half to a generic
base converter, regex, checksum library, precomputed table of answers, or an
emitted cross-task dispatcher.

## Tests and evidence

Every root has one visible and one private deterministic executable. Together
they cover a valid example, the wrong claimed check, empty input, malformed
alphabet/radix/policy, duplicate or absent material where applicable, exact
digit boundaries, first-error ordering, and overflow/no-partial-acceptance.
Each root also contains one strict-compiling false source that preserves its
API and generic happy-path shape but implements the checksum column's named
wrong substitute. The exact production tests must execute and reject it.

The owner derives seven independent dimensions from emitted artifacts:
`public_api`, `owned_state_or_algorithm`, `mutation_selection_rules`,
`invalid_boundary_behavior`, `reference_control_flow`,
`deterministic_oracle`, and `topic_specific_negative_fixture`. It evaluates
all `100*99/2 = 4,950` unordered pairs conjunctively. Each pair must differ in
every dimension after identifiers, story nouns, comments, and literals are
normalized; raw IDs, declared labels, and unequal hashes are not evidence.

The owner materializes three non-counted controls from an emitted root under
`.state/controls/`: a coherent domain/identifier rename, a coherent
constants/policy-only variant, and a coherent opposite-end-selection variant.
Each control must change files, retain safe roles, build and pass its own
normal and fresh ASan/UBSan tests, and be rejected as a duplicate by the exact
production evaluator in every dimension. Focused tests independently reopen
the decision matrix and controls; they may not trust one top-level pass flag.

Creator preflight additionally requires deterministic regeneration,
whole-file/parser boundary rejection cases, exact role mapping, frozen legacy
and reverify inventories, no IDs/prompt/reference hashes or semantic lineage
collisions, all 26 official holdouts present and screened, 100 positive normal
and 100 equal fresh sanitizer test discoveries, 100 compiled/executed negative
rejections in both modes, three passing controls in both modes, and a receipt
binding all content, owner, compiler/image, command, policy, and result hashes.

The owner also provides a host verification mode (`--verify-host`) that runs
the same owner-controlled verification script used by the Docker sanity path
against the packaged current tree with the host toolchain: clean normal and
fresh ASan/UBSan reference builds with positive equal discovery counts,
executed negative-fixture rejection for every root, and coherent control
builds in both modes. It writes a bound `.state/receipts/host-verify.json`
recording the tree hash, owner revision, host CMake/compiler identities,
counts, and command. Audits treat a missing host receipt as a moderate
finding and a stale one (tree or owner mismatch) as a blocker. Host evidence
is `host_verify` class; it never upgrades to `docker_sanity` or locked-oracle
evidence, and any owner regeneration invalidates it like every other
exact-tree receipt.

## Audit loop and acceptance

The exact generated tree receives a read-only `audit-sft-data-quality` pass.
Every finding is immutable and stable-ID-bound. Findings route through
`aider-task-family-remediation`, an owner change, complete regeneration,
remediation verification, and a fresh audit. Rejected roots do not count and
require genuinely new backfills in this same count-plan cell.

Completion requires exactly 100 retained roots, zero unresolved hard-gate
findings, zero retained review/repair/conflict/contamination dispositions,
current normal/sanitizer/negative/prompt/diversity/lineage evidence, and a
fresh audit bound to the final tree. The strongest truthful state is
`local_family_verified`. Dataset handoff is `not_requested`; no JSONL,
token/mask ledger, split, release, export, training, evaluation, or uplift is
authorized.
