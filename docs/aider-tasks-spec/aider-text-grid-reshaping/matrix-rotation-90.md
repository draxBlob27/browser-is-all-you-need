# Matrix Rotation 90 Family Remediation Audit

## Scope and controlling inputs

This audit accounts for all 20 legacy roots beneath
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/matrix-rotation-90/` and
the owner-generated v2 family beneath the parallel `aider-tasks-reverify`
root. Review date: 2026-07-18. Purpose: local family remediation only.
Controlling prompt:
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with
`FAMILY_NAME=matrix-rotation-90` and
`FAMILY_TYPE=aider-text-grid-reshaping`.

The legacy root is read-only. No JSONL, token/mask evidence, split, export,
training run, dataset release, or benchmark-uplift claim is authorized.

## Commands and exact outcomes

- Focused pytest: `8 passed`, including direct inspection of all 190
  seven-dimensional decisions, coherent clone contents, root-count failure,
  and the final Docker receipt.
- Owner `--verify-core`: passed prompt/role/reference mapping and all 190
  family pairs separately in all seven hard-rule dimensions at threshold
  `0.85`. Maximum overlaps were public API `0.760417`, owned state/algorithm
  `0.657795`, mutation/selection `0.582888`, invalid/boundary `0.814815`,
  reference control flow `0.613497`, deterministic oracle `0.795082`, and
  topic-specific negative fixture `0.652344`. The retained aggregate screen
  had maximum `0.725296`; it is supplementary, not hard-rule evidence. All 520
  comparisons against the exact 26 bound official C++ holdouts passed with
  maximum overlap `0.058496`.
- Host `--verify`: `not_completed`; host `cmake` is unavailable. The receipt
  records the blocked command `cmake -S <task> -B <build> -G Unix Makefiles`
  and does not promote host evidence.
- Owner `--docker-sanity`: passed with network `none` in
  `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
  All 20 roots discovered and passed three normal tests and three fresh
  ASan/UBSan tests. Every compiled false substitute was rejected in both modes.
  The three coherent clone controls also compiled and passed three tests in
  each mode, while the family screen classified every control as a duplicate
  in all seven dimensions. Archive hash:
  `sha256:c75fd89d1d5a17f352d566565835c444a0dad2c00aa8b0c54ba1383d3556c619`.
  Owner revision:
  `sha256:f48ed3bfba15de48d12d6f46ad2deae9dfb2834d7ac5a9a034af4f121c79fba4`.
  Receipt SHA-256:
  `655283915ec729454e9db4af29e80942a38c8c7184ca6fde9d957588baad09be`.
- Docker toolchain: `/usr/local/bin/c++`, GCC 13.4.0, compiler hash
  `sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
  CMake 3.25.1.

## Audit findings

### MATRIX-ROTATION-001 — Shared core template

**Severity:** major

**Scope:** all 20 legacy roots.

**Observed evidence:** every reference used one square-grid allocation loop,
`next[c][n - 1 - r] = cells[r][c]`, with domain nouns substituted into the
class/action/report names. The five measurement variants were edge or corner
sums and did not change the rotation mechanism.

**Why it matters:** the family did not genuinely contain 20 independent
objectives; successful builds only proved one template repeatedly.

**Root cause:** curriculum rows were treated as parameters to a generic
renderer rather than one-to-one task specifications.

**Remedy:** repair the independently justified aerial layer-cycle root and
replace the other 19 roots with distinct APIs, representations, validation,
control flow, diagnostics, tests, and false substitutes.

**Verification after remedy:** owner `--verify-core`, executed negative
fixtures, all-pairs screen, and Docker sanity.

**Status:** resolved and reverified.

### MATRIX-ROTATION-002 — Semantic duplicate family

**Severity:** major

**Scope:** all 190 unordered legacy pairs.

**Observed evidence:** after removing class/domain/report identifiers and
literals, references and tests retain the same control flow and assertion
shape.

**Why it matters:** domain renaming cannot establish learning capacity.

**Root cause:** the legacy owner had no artifact-derived duplicate screen and
no adversarial clone controls.

**Remedy:** compare emitted docs, public APIs, references, visible tests, and
private tests for every v2 pair; prove the same screen rejects renamed,
constants/policy-only, and opposite-end clones.

**Verification after remedy:** 190 pair records below the production threshold
and all three controls report `duplicate_family`.

**Status:** resolved and reverified.

### MATRIX-ROTATION-003 — Tests did not discriminate advertised contracts

**Severity:** major

**Scope:** every legacy root.

**Observed evidence:** tests repeated one 3-by-3 rotation and one common
invalid/ragged sequence. They did not distinguish sparse, packed, directional,
metadata, subwindow, encoded, graph, or other advertised domain mechanisms.

**Why it matters:** a generic dense rotation and edge sum could satisfy the
entire family.

**Root cause:** tests were emitted from the same example template as the
reference.

**Remedy:** generate one task-specific visible and private oracle plus one
strictly compiled, executed false substitute for each v2 root.

**Verification after remedy:** each mode discovers visible, hidden, and
expected-failing negative CTests; the negative executable exits one only
because the task contract rejects it.

**Status:** resolved and reverified.

### MATRIX-ROTATION-004 — Prior hard-rule evidence was invalid

**Severity:** major

**Scope:** the first v2 completion claim and its family screen.

**Observed evidence:** the earlier verifier used one aggregate overlap for a
pair instead of seven conjunctive artifact-derived decisions. Its
domain/identifier-renamed mutation changed zero files, while focused tests
only repeated the same production helper and did not establish that a genuine
clone existed.

**Why it matters:** IDs, profiles, raw tree hashes, aggregate diversity, and a
deliberately wrong negative source cannot prove that every counted pair differs
materially in every hard-rule dimension.

**Root cause:** the screen encoded the broad duplicate heuristic but not the
skill's exact hard acceptance rule, and it did not validate mutation coherence
before treating adversarial results as evidence.

**Remedy:** invalidate the prior receipt and all 20 verified remedy states;
derive seven independent feature sets from each emitted API, reference, docs,
visible/private oracle, and negative fixture; compare all 190 pairs
conjunctively; require genuine cross-file clones with nonempty changed-file
sets; and compile each coherent control in both Docker modes.

**Verification after remedy:** family-screen schema v4 contains 190 passing
seven-dimensional records. All three coherent controls have overlap `1.0` and
`duplicate_family` in all seven dimensions. Docker-sanity schema v4 binds
matching owner/mounted hashes and three normal plus three fresh ASan/UBSan
tests for every control.

**Status:** resolved and reverified.

## Per-root disposition

| Legacy root | V2 root | Disposition | Primary mechanism | Current status |
| --- | --- | --- | --- | --- |
| `rotate-aerial-tiles` | `rotate-aerial-tiles` | `repair-in-place` | Concentric in-place four-cycles | `local_family_verified` |
| `rotate-archive-shelves` | `rotate-rectangular-scan` | `replace` | Rectangular out-of-place remap | `local_family_verified` |
| `rotate-circuit-board` | `rotate-sparse-board-coordinates` | `replace` | Sparse coordinate transform | `local_family_verified` |
| `rotate-chess-analysis` | `rotate-packed-occupancy-mask` | `replace` | Packed-bit permutation | `local_family_verified` |
| `rotate-escape-map` | `rotate-directional-vector-field` | `replace` | Vector-basis transform | `local_family_verified` |
| `rotate-factory-inspection` | `rotate-directional-glyph-map` | `replace` | Glyph orientation automaton | `local_family_verified` |
| `rotate-garden-bed` | `rotate-oriented-tile-atlas` | `replace` | Tile metadata composition | `local_family_verified` |
| `rotate-ice-rink-drills` | `rotate-square-subwindow` | `replace` | Atomic subwindow rotation | `local_family_verified` |
| `rotate-lab-sample-rack` | `rotate-perimeter-conveyor` | `replace` | Perimeter cyclic shift | `local_family_verified` |
| `rotate-museum-floorplan` | `rotate-voxel-slice-stack` | `replace` | Slice transform and depth reversal | `local_family_verified` |
| `rotate-orchard-spray` | `rotate-row-run-encoding` | `replace` | RLE recompression | `local_family_verified` |
| `rotate-puzzle-tile` | `rotate-rectangular-regions` | `replace` | Half-open region transform | `local_family_verified` |
| `rotate-quilt-block` | `rotate-polyline-waypoints` | `replace` | Signed point transform | `local_family_verified` |
| `rotate-radar-sector` | `rotate-lazy-grid-view` | `replace` | Lazy inverse query mapping | `local_family_verified` |
| `rotate-satellite-camera` | `compose-orientation-commands` | `replace` | Dihedral composition | `local_family_verified` |
| `rotate-solar-panel` | `rotate-stencil-kernel` | `replace` | Kernel and anchor transform | `local_family_verified` |
| `rotate-storm-grid` | `rotate-embedded-route-graph` | `replace` | Embedded graph transform | `local_family_verified` |
| `rotate-tactical-map` | `rotate-planar-channels` | `replace` | Synchronized planar channels | `local_family_verified` |
| `rotate-theater-lights` | `rotate-block-sparse-layout` | `replace` | Two-level block rotation | `local_family_verified` |
| `rotate-warehouse-pallets` | `rotate-quadtree-leaf-bounds` | `replace` | Aligned leaf/Morton transform | `local_family_verified` |

Every legacy root has a JSON remedy record and twelve-heading Markdown
specification under the reverify root's `.state/remedy/` directory before its
replacement files are materialized.

Full legacy and v2 tree hashes are bound in the 20 remedy records; the final
live and independently mounted v2 hashes are also bound in the Docker receipt.
The audit intentionally does not duplicate abbreviated values that can become
stale after generator-owned documentation changes.

## Acceptance gates

- exact generator-owned regeneration under the reverify root;
- legacy-root immutability and complete legacy-to-v2 accounting;
- prompt visibility limited to docs and two declared task-named editable files;
- safe role/reference mapping and strict whole-file answer order;
- primary mechanism evidence plus one executed negative fixture per root;
- all 190 v2 family pairs pass separately in all seven hard-rule dimensions;
- all three coherent adversarial controls change emitted files, are rejected
  in all seven dimensions, and compile/run in both Docker modes;
- all 520 bound-holdout pairs screened;
- three positive equal CTest discoveries in clean normal and fresh ASan/UBSan
  modes in the pinned network-disabled Docker sanity image;
- owner and independently mounted task-tree hashes match; and
- remedy records bind final hashes, receipt, results, and
  `local_family_verified` before that status is claimed.

## Changed owners and generated/reused files

Changed checked-in owners: the curriculum, this family specification, the
materialization guide, wrapper, owner module, cases module, and focused pytest.
The owner regenerated all 20 v2 roots, 20 JSON remedy records, 20 twelve-heading
remedy specifications, the family screen, host receipt, and Docker receipt.
The 20 legacy roots and exact bound official checkout were reused read-only.

## Strongest current conclusion

All 20 v2 roots have `primary_core_objective: achieved`, are structurally
valid, pass prompt/role/reference mapping, pass the strongest available
network-disabled image normal and fresh ASan/UBSan check, reject their executed
false substitutes, and pass family plus bound-holdout screens. All 20 reached
`local_family_verified`. Evidence class is `docker_sanity` with
`locked_oracle: false`; this is not dataset admission, training authorization,
a release, or benchmark uplift.
