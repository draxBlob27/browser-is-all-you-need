# Transpose Family Remediation Audit

## Scope and controlling inputs

This audit accounts for all 20 legacy roots beneath
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/transpose/` and the
owner-generated v2 roots beneath the parallel `aider-tasks-reverify` tree.
Review date: 2026-07-18. Purpose: local family remediation only. The controlling
prompt is `docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with
`FAMILY_NAME=transpose` and
`FAMILY_TYPE=aider-text-grid-reshaping`.

The legacy root is read-only. No JSONL, token/mask evidence, split, export,
training run, dataset release, or benchmark-uplift claim is authorized.

## Commands and exact outcomes

- Focused pytest: `8 passed`, including the final Docker-receipt binding.
- Owner `--verify-core`: passed role/reference mapping, prompt boundaries, all
  190 family pairs, all 520 comparisons against the exact 26 bound official
  C++ holdouts, and the three required coherent clone controls.
- Maximum all-pairs overlaps were aggregate `0.740741`, public API `0.770833`,
  owned state/algorithm `0.638132`, mutation/selection `0.563725`,
  invalid/boundary behavior `0.648936`, reference control flow `0.640244`,
  deterministic oracle `0.798450`, and topic negative `0.662698`. Every
  seven-dimensional value is below its `0.85` hard threshold. Maximum bound
  holdout overlap was `0.055224`.
- Host `--verify`: `not_completed`; host `cmake` is unavailable. The recorded
  blocked command is `cmake -S <task> -B <build> -G Unix Makefiles`.
- Owner `--docker-sanity`: passed with Docker network `none` in
  `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
  Every root discovered and passed three normal and three fresh ASan/UBSan
  CTests. Every strict false substitute executed and exited one with empty
  diagnostics in both modes. All three coherent clone controls compiled and
  passed three tests in both modes while the family screen rejected each clone
  in all seven dimensions.
- Docker toolchain: `/usr/local/bin/c++`, GCC 13.4.0, compiler hash
  `sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
  CMake 3.25.1. Archive hash:
  `sha256:4184edb93cd839615540ea68cf99353fc8b1b782cbd0d6366c6a53e1f18a900a`.
  Owner revision:
  `sha256:1daea6998394be3c9d438b71b4cb987c585d411065ffbfa95b8c6d0d73082142`.
  Receipt SHA-256:
  `30b7156b15eb992849c3a17a22fdce6e161a23add49da59e95c0215bfbebd8bd`.

## Audit findings

### TRANSPOSE-001 — Shared core template

**Severity:** major

**Scope:** all 20 legacy roots.

**Observed evidence:** every legacy reference selected a width policy, allocated
column records, and ran the same nested `column`/`source` loop. Domain class,
row, record, report, metric, and ragged-policy names changed; the substantive
transpose mechanism did not.

**Why it matters:** the family represented one generic algorithm twenty times,
not twenty independent learning objectives.

**Root cause:** task rows parameterized one renderer instead of owning distinct
APIs, representations, control flow, or oracles.

**Remedy:** repair the lexicographically smallest independently justified dense
root and replace the other 19 roots with distinct packed, sparse, encoded,
graph, relation, tensor, tiled, streaming, lazy, triangular, banded, block, and
permutation mechanisms.

**Verification after remedy:** owner `--verify-core`, executed negatives, all
pairs, and Docker sanity.

**Status:** resolved and reverified.

### TRANSPOSE-002 — Semantic duplicate family

**Severity:** major

**Scope:** all 190 unordered legacy pairs.

**Observed evidence:** after erasing identifiers, literals, and domain nouns,
the legacy APIs, reference control flow, and test assertion shapes remain one
template with policy/metric branches.

**Why it matters:** renamed ledgers do not establish independent training
capacity.

**Root cause:** the legacy owner had no artifact-derived all-pairs gate or
adversarial clone controls.

**Remedy:** compare actual emitted docs, APIs, references, visible/private
tests, and negative fixtures in seven separate dimensions; prove the same
screen rejects domain-renamed, constants/policy-only, and opposite-end clones.

**Verification after remedy:** 190 passing pair records and three controls
classified `duplicate_family` in all seven dimensions.

**Status:** resolved and reverified.

### TRANSPOSE-003 — Tests did not discriminate the claimed domains

**Severity:** major

**Scope:** every legacy root.

**Observed evidence:** visible/private tests repeated the same dense coordinate
examples and selected only one aggregate field. They did not require compressed
storage conversion, packed indexing, in-place swaps, axis strides, edge
reversal, run recompression, block transforms, inverse queries, or cycle
decomposition.

**Why it matters:** the generic legacy implementation could satisfy every root.

**Root cause:** tests were generated from the same policy/metric template as
the reference.

**Remedy:** provide a task-specific visible and private oracle and one strict,
compilable, executed false substitute per v2 root.

**Verification after remedy:** every negative compiles with the reference flags
and is rejected by executed tests in normal and sanitizer modes.

**Status:** resolved and reverified.

### TRANSPOSE-004 — Runtime evidence required fixture corrections

**Severity:** moderate

**Scope:** banded, common-rectangle, lazy-view, ragged-mask, and tensor roots,
plus the opposite-end clone control.

**Observed evidence:** iterative pinned-image runs found one incorrect banded
expected slot order, unsafe common-rectangle and lazy-view substitutes, a
ragged negative not observed by the visible test, a tensor negative that was
not warning-clean, and a clone negative that had become correct under the
clone's revised contract.

**Why it matters:** compilation failure, undefined behavior, or a passing false
substitute is not semantic rejection evidence.

**Root cause:** source-level inspection had not yet exercised the exact strict
flags and direct exit-one/empty-diagnostic contract.

**Remedy:** correct the banded oracle expectation; make every substitute
bounds-safe and warning-clean; assert the ragged provenance bit; and give the
opposite-end control its own coherently wrong cyclic mapping.

**Verification after remedy:** the final Docker receipt records all 20 task
negatives and all three controls across both modes.

**Status:** resolved and reverified.

## Per-root disposition

| Legacy root | V2 root | Disposition | Primary mechanism | Status |
| --- | --- | --- | --- | --- |
| `transpose-call-center` | `transpose-call-center` | repair-in-place | dense rectangular bijection | `local_family_verified` |
| `transpose-choir-rehearsal` | `transpose-square-in-place` | replace | upper-triangle in-place swaps | `local_family_verified` |
| `transpose-class-register` | `transpose-ragged-pad-mask` | replace | zip-longest plus occupancy mask | `local_family_verified` |
| `transpose-diet-diary` | `transpose-csr-to-csc` | replace | CSR count-prefix-scatter to CSC | `local_family_verified` |
| `transpose-energy-meters` | `transpose-coordinate-coalesce` | replace | coordinate swap/coalescing | `local_family_verified` |
| `transpose-exam-markbook` | `transpose-packed-bitboard` | replace | packed 8-by-8 bit permutation | `local_family_verified` |
| `transpose-factory-shifts` | `transpose-tiled-grid` | replace | cache-tiled clipped traversal | `local_family_verified` |
| `transpose-freight-manifest` | `transpose-stream-batches` | replace | bounded streaming column batches | `local_family_verified` |
| `transpose-garden-plots` | `transpose-tensor-axes` | replace | rank-three axis/stride permutation | `local_family_verified` |
| `transpose-inventory-cycle` | `transpose-directed-graph` | replace | directed-edge reversal | `local_family_verified` |
| `transpose-lab-readings` | `transpose-relation-index` | replace | many-to-many relation inversion | `local_family_verified` |
| `transpose-library-loans` | `transpose-run-encoded-image` | replace | run decode/column recompression | `local_family_verified` |
| `transpose-market-quotes` | `transpose-channel-planes` | replace | interleaved-to-planar channels | `local_family_verified` |
| `transpose-museum-visits` | `transpose-symmetric-triangle` | replace | packed triangular mirroring | `local_family_verified` |
| `transpose-network-probes` | `transpose-lazy-view` | replace | checked inverse-coordinate queries | `local_family_verified` |
| `transpose-river-samples` | `transpose-anti-diagonal` | replace | anti-diagonal coordinate reflection | `local_family_verified` |
| `transpose-seat-audit` | `transpose-banded-matrix` | replace | compact diagonal-band reindexing | `local_family_verified` |
| `transpose-survey-answers` | `transpose-common-rectangle` | replace | shortest-row rectangle/tail audit | `local_family_verified` |
| `transpose-training-load` | `transpose-block-sparse` | replace | block and in-block transpose | `local_family_verified` |
| `transpose-weather-log` | `transpose-permutation-ledger` | replace | inverse permutation/cycle ledger | `local_family_verified` |

Every legacy root has a JSON remedy record and twelve-heading Markdown remedy
specification under the reverify root's `.state/remedy/` directory. Those
records bind legacy and v2 tree hashes, owner/reference hashes, prompt and role
results, family/holdout evidence, and the final Docker receipt.

## Acceptance gates and changed owners

The accepted owner paths are the curriculum, this specification, materializer,
case inventory, wrapper, focused pytest, and the materialization guide. The
owner regenerated 20 v2 roots, 20 JSON records, 20 Markdown remedy specs, the
family screen, host receipt, and Docker receipt. The legacy roots and bound
official checkout were reused read-only.

## Strongest current conclusion

All 20 v2 roots have `primary_core_objective: achieved`, are structurally
valid, pass prompt/role/reference mapping, pass network-disabled normal and
fresh ASan/UBSan checks, reject their executed false substitutes, and pass
family plus bound-holdout screens. All reached `local_family_verified`.
Evidence class is `docker_sanity` with `locked_oracle: false`; this is not
dataset admission, training authorization, a release, or benchmark uplift.
