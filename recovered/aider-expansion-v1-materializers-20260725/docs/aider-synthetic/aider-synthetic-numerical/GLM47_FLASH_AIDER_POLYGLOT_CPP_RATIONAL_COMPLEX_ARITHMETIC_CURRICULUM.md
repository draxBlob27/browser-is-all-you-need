# Rational And Complex Value-Arithmetic Expansion Curriculum

Status: generator-owned clean-room creation curriculum for the binding 40-root
`Rational, complex, and value-semantic arithmetic APIs` cell in the 2,500-task
count plan. These are local candidate roots only. This document creates no SFT
rows, release, training authorization, model evaluation, or uplift claim.

## Scope and ownership

The owner is
`src/w8_biayn/integrations/moonlight_rational_complex_arithmetic_expansion.py`.
It may write task roots only below
`.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/rational-complex-value-arithmetic/`.
The legacy and reverify trees and every other expansion family are immutable
inventory and semantic-screen inputs. The owner must reject unsafe output
roots, symlinks or hardlinks into existing trees, ID collisions, duplicate
prompt/reference hashes, semantic-lineage overlap, and all official Aider C++
holdouts.

The exact retained count is 40: twenty exact-rational algorithms and twenty
higher-order complex or Gaussian-integer algorithms. The official
`complex-numbers` root remains a permanent holdout. No retained task is a
basic renamed complex-number operator exercise. Rational parsing is limited to
one repeating-decimal conversion algorithm and must not reproduce the existing
lexical rational-token task.

## Public value foundations

Rational roots expose a compact `Rational { long long numerator,
denominator; }` value and task-specific input/result records. A valid rational
has a nonzero denominator. Every returned rational is reduced, has a positive
denominator, and uses checked 64-bit arithmetic; an invalid input or an
intermediate that cannot be represented returns `std::nullopt`.

Complex roots expose either an integral `Gaussian { long long real, imag; }`
or a floating `ComplexValue { long double real, imag; }` value plus
task-specific records. Floating inputs and results must be finite. Algorithms
use explicit value operations as incidental support, never `std::complex` as a
substitute for the advertised core. Floating tests use a documented absolute
tolerance and include zero/degenerate rejection.

## Binding root inventory

| # | Task ID | Advertised core mechanism | Primary false substitute rejected |
| ---: | --- | --- | --- |
| 1 | `rational-continued-fraction-convergents` | recurrence for every continued-fraction convergent | returning only the final convergent |
| 2 | `rational-stern-brocot-locate` | bounded Stern-Brocot left/right search | denominator-limited decimal rounding |
| 3 | `rational-farey-neighbor-gap` | ordered Farey adjacency and determinant certificate | checking only numeric ordering |
| 4 | `rational-egyptian-decomposition` | greedy unit-fraction decomposition | splitting into repeated unit denominators |
| 5 | `rational-bounded-approximation` | best-denominator search with exact error comparison | nearest fixed-denominator rounding |
| 6 | `rational-polynomial-horner` | exact Horner fold over rational coefficients | summing coefficients without powers |
| 7 | `rational-lagrange-interpolation` | exact Lagrange basis accumulation | nearest-sample selection |
| 8 | `rational-linear-system` | pivoted rational Gaussian elimination | diagonal-only division |
| 9 | `rational-determinant-elimination` | exact elimination determinant with row-swap sign | diagonal product |
| 10 | `rational-distribution-convolution` | exact probability-mass convolution | pointwise multiplication |
| 11 | `rational-markov-transition` | row-vector by stochastic-matrix transition | selecting the largest outgoing edge |
| 12 | `rational-interval-union-measure` | sorted merge and exact union measure | sum of unmerged interval lengths |
| 13 | `rational-piecewise-rate-integral` | clipped segment integration over a query window | full-segment total without clipping |
| 14 | `rational-segment-intersection` | exact 2-D line parameter intersection | bounding-box midpoint |
| 15 | `rational-polygon-centroid` | shoelace signed-area centroid | arithmetic mean of vertices |
| 16 | `rational-bezier-split` | de Casteljau split at a rational parameter | independent endpoint interpolation |
| 17 | `rational-conversion-path` | multiplicative ratio propagation through a graph | direct-edge-only conversion |
| 18 | `rational-amortization-schedule` | exact sequential accrued-balance recurrence with payoff floor | simple interest from original principal |
| 19 | `rational-largest-remainder` | quota floors plus stable fractional-remainder seats | round every quota independently |
| 20 | `rational-repeating-decimal` | exact signed nonrepeating/repeating decimal conversion | treating the repeated block as finite digits |
| 21 | `gaussian-euclidean-gcd` | Gaussian-integer Euclidean descent with nearest quotient | component-wise integer gcd |
| 22 | `gaussian-divisibility-lattice` | norm-divisibility lattice enumeration | rectangular component divisibility |
| 23 | `complex-polynomial-horner` | complex Horner evaluation | coefficient sum |
| 24 | `complex-polynomial-derivative` | derivative coefficient weighting and evaluation | evaluating the original polynomial |
| 25 | `complex-newton-iteration` | guarded complex Newton steps for a polynomial | fixed real-axis decrement |
| 26 | `complex-dft-selected-bin` | selected-bin discrete Fourier accumulation | sample sum independent of bin |
| 27 | `complex-linear-convolution` | full non-circular complex convolution | pointwise product |
| 28 | `complex-cross-correlation` | conjugating lagged cross-correlation | convolution without conjugation |
| 29 | `complex-impedance-reduction` | postfix series/parallel impedance reduction | summing every component |
| 30 | `complex-phasor-prefix` | cumulative phasor multiplication and prefix emission | independent, non-cumulative phasors |
| 31 | `complex-mobius-transform` | guarded fractional linear transform | affine numerator only |
| 32 | `complex-cross-ratio` | ordered four-point cross ratio | pairwise distance ratio |
| 33 | `complex-contour-integral` | exact piecewise-linear integral of an affine field | endpoint-only field sampling |
| 34 | `complex-matrix-determinant` | pivoted complex elimination determinant | diagonal product |
| 35 | `complex-linear-system` | pivoted complex Gaussian elimination | diagonal-only solve |
| 36 | `complex-quantum-gate` | 2x2 complex gate application with norm preservation | component-wise gate diagonal only |
| 37 | `complex-state-normalization` | finite vector norm and canonical phase normalization | magnitude scaling without phase canonicalization |
| 38 | `complex-bilinear-surface` | two-axis bilinear interpolation | averaging four corners |
| 39 | `complex-roots-unity-filter` | selected roots-of-unity spectral sum | counting selected indices |
| 40 | `complex-mandelbrot-escape` | guarded quadratic orbit and first-escape iteration | one-step magnitude classification |

Cycle-01 rejected `rational-weighted-median`: its representation differed, but
its stable cumulative-half selection mechanism duplicated the existing
`weighted-median-mark` root. `rational-amortization-schedule` is the clean-room
replacement; no rejected task is retained or renamed into the count.

The complete C++17 signatures, behavior tables, examples, test vectors, and
negative fixtures are normative in
`docs/aider-tasks-spec/aider-numerical/rational-complex-value-arithmetic-expansion.md`.

## Artifact and prompt contract

Each root contains exactly two task-ID-named editable files in header/source
order, complete private reference replacements, one visible test, one hidden
test, one coherent compiling false substitute, C++17 CMake, role metadata, and
clean-room provenance. Prompts expose only `.docs/*.md` and those two starter
files. Tests, references, CMake, provenance, receipts, clone controls, and
audit state stay private.

The owner must prove the reference and false substitute with the same strict
warnings. Normal and fresh ASan/UBSan configurations must discover the same
two positive tests. The reference must pass both; every false substitute must
compile and then be rejected by at least one executed task test.

## Diversity and adversarial controls

The owner rereads emitted artifacts and compares all 780 unordered task pairs
over the repository's seven mandatory dimensions: public API, owned state or
algorithm, mutation/selection rules, invalid/boundary behavior, reference
control flow, deterministic oracle, and topic-specific negative fixture. The
decision is conjunctive and records every per-dimension result. IDs, declared
mechanism labels, raw hashes, and wrong substitutes outside their own
dimension are not diversity evidence.

Four non-counted controls are materialized under `.state`: a coherent
domain/identifier rename, a constants-or-policy-only variant, an
opposite-end-selection variant, and the rejected representation-changed
weighted-selection semantic clone. Each changes real files, remains buildable,
passes its own normal and sanitizer reference tests, and is rejected by the
production diversity or representation-invariant semantic rule. Focused tests
independently reopen and check the exact root, pair, dimension, control-change,
content-digest, and control-rejection records.

## Evidence and closure

Raw proposals, selected roots, rejected controls, frozen cross-tree inventory,
prompt boundary, lineage, benchmark, duplicate-family, normal/sanitizer,
negative-fixture, and per-root receipts remain separate under the family
`.state/`. Any owner, curriculum, specification, focused test, generated
artifact, normalizer, image, compiler, or policy change invalidates prior
receipts.

The frozen cross-tree inventory and lineage screen form an immutable
point-in-time subject. The private inventory keeps a content-addressed
screening index—not copied task roots—with each root's tree/payload,
prompt/reference, normalized-token, and representation-invariant signature
evidence. The creator derives and screens that index only between equal live
full-content start/end hashes. The screen record binds the inventory-file and
canonical semantic-snapshot digests, internal inventory hash, counts,
normalizer, and comparison result. A fresh auditor validates every index
record and independently recomputes the exact screen from the bound snapshot.
Later materializing an unrelated family cannot rewrite that completed source
observation; corrupt or unbound snapshot evidence fails closed.

Creator preflight hands an immutable exact-tree subject to a read-only
`audit-sft-data-quality` pass. Findings route through
`aider-task-family-remediation`, owner changes, complete regeneration, and a
fresh audit. Only the fresh audit can close the family at
`local_family_verified`.

## Required commands

```bash
uv run python -m w8_biayn.integrations.moonlight_rational_complex_arithmetic_expansion \
  --out .w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/rational-complex-value-arithmetic \
  --force --verify-core

uv run python -m w8_biayn.integrations.moonlight_rational_complex_arithmetic_expansion \
  --out .w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/rational-complex-value-arithmetic \
  --verify-host

uv run python -m w8_biayn.integrations.moonlight_rational_complex_arithmetic_expansion \
  --out .w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/rational-complex-value-arithmetic \
  --docker-sanity --creator-preflight
```

`--verify-host` reruns the per-root oracle on the host toolchain (clean normal
plus fresh ASan/UBSan builds with positive equal discovery counts and executed
negative-fixture rejection for every root and adversarial control) and records
a `host_verify` receipt. It is host evidence only and does not replace the
mandatory network-disabled Docker sanity run.

The strongest possible local status is `local_family_verified`. It is not a
dataset release, SFT authorization, training result, or benchmark claim.

## Docs Alignment (Remediation Docs Phase)

The model-facing `.docs` follow the official Aider Polyglot C++ conventions.
`.docs/introduction.md` is a `# <Title>` header plus a domain-motivating
narrative about exact rational/complex arithmetic; it never states the
contract or mentions the evaluation harness. `.docs/instructions.md` starts
with `# Instructions`, keeps the complete Public API / Valid behavior /
Invalid and boundary / Mutation-ordering-ties contract, adds a `## Examples`
section rendering the visible check's concrete cases, and renames the
"Advertised mechanism" section to "Mechanism" with natural requirement
phrasing ("Implement this mechanism directly: a generic library, a
precomputed answer, or <substitute> cannot reproduce the documented
behavior."). The harness-speak "Replace both supplied editable files
completely." line is removed. The generator's focused test asserts this docs
shape and rejects meta/audit vocabulary in both docs files.
