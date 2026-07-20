# ASCII Art Scaling Family Remediation Audit

## Scope and controlling inputs

This audit covers all 20 legacy roots beneath
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/ascii-art-scaling/` and
the owner-generated v2 family beneath the parallel `aider-tasks-reverify`
root. Review date: 2026-07-18. Purpose: local family remediation only.
Controlling prompt: `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
with `FAMILY_NAME=ascii-art-scaling` and
`FAMILY_TYPE=aider-text-grid-reshaping`.

The legacy root was not modified. No JSONL rows, token/mask evidence, split,
export, training run, dataset release, or benchmark-uplift claim was created.

## Commands and exact outcomes

- Focused pytest passed. The final post-receipt result is recorded under
  validation below.
- Owner `--verify-core` passed prompt boundaries, role/reference mapping, 190
  unordered emitted-family comparisons after removing identifiers, literals,
  clean-room domain nouns, and endpoint direction; three adversarial clone
  controls; and 520 comparisons against all 26 bound official C++ holdouts.
- Host `--verify` is `not_completed`. The blocked command starts
  `cmake -S <task> -B <build> -G Unix Makefiles` because host `cmake` is absent.
  This host-only iteration result was not promoted.
- Owner `--docker-sanity` passed with network `none` in the pinned image
  `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
  All 20 roots discovered and passed three tests in normal mode and three in a
  fresh ASan/UBSan mode. Each root's distinct semantic false substitute built
  with the exact strict reference flags and was then executed separately; all
  40 executions returned exactly 1 with no sanitizer diagnostics. Docker
  independently recomputed every mounted-tree digest with the owner byte
  algorithm, and all 20 matched. Archive hash:
  `sha256:c43e028f3d17f0c08ddf12f1d8bad4c520418095edc39836fa4dba1e9e230d56`.
  Owner revision:
  `sha256:7b73f3607ee79e1f0412a1460b2ce3b3729d1c3bc7d2a1cdd1e5dfad324335a1`.
  Snapshot-safe live-owner import receipt hash:
  `sha256:8bd1492635af870fe355d1df90bc23d1b4dc1ee3470074a0832cded82aa88035`.

## Structural verification matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| Prompt visibility | pass | Only docs and the two declared task-named editable files enter the whole-file prompt. |
| Role/reference mapping | pass | Every config has safe ordered solution/reference paths; build, meta, docs, and tests are non-editable. |
| Primary core objective | achieved | Twenty distinct emitted APIs/mechanisms plus complete behavior checks and executed false substitutes. |
| Family duplication | pass | All 190 name/literal/domain-blind pair scores are below 0.84 (maximum 0.679739); all three full-root clone classes score 1.0 and yield `duplicate_family`. |
| Benchmark contamination | pass | All 520 comparisons against 26 bound official C++ roots are below 0.72 (maximum 0.075391); no slug match. |
| Normal Docker sanity | pass | 20/20 roots, three positive discoveries each. |
| Fresh ASan/UBSan sanity | pass | 20/20 roots, three positive discoveries each, matching normal. |
| Topic-specific negative fixtures | pass | 20 distinct wrong policies compile strictly; 20 normal and 20 sanitizer executions return exactly 1 with empty diagnostics. |
| Mounted-tree identity | pass | Docker independently computes the exact length-prefixed path/byte digest; 20/20 equal the live owner digest. |
| Locked oracle | not claimed | No designated grader exists; evidence is `docker_sanity` with `locked_oracle: false`. |

## Findings

### ASCII-SCALE-001 — Claimed family collapsed to one scaler

**Severity:** major

**Scope:** every legacy root.

**Observed evidence:** the old owner emitted one rectangular nearest-neighbor
implementation and report shape; only class/domain and one counted marker
changed.

**Why it matters:** 20 compiling directories did not provide 20 independent
learning objectives.

**Root cause:** curriculum entries were parameters to one template.

**Remedy:** repair the independently justified archive-stamp representative and
replace the other 19 roots with distinct APIs, algorithms, validation,
diagnostics, references, and tests.

**Verification after remedy:** emitted API/reference signatures are unique and
every compiled false substitute is rejected.

**Status:** resolved and reverified.

### ASCII-SCALE-002 — Semantic duplicate family

**Severity:** major

**Scope:** every unordered legacy pair.

**Observed evidence:** normalized control flow and tests were identical after
removing domain nouns, class names, literals, and marker constants.

**Why it matters:** domain renaming cannot count as independent capacity.

**Root cause:** no artifact-derived all-pairs screen or adversarial controls.

**Remedy:** add all-pairs emitted-artifact screening and renamed,
constants/policy-only, and opposite-selection clone controls.

**Verification after remedy:** 190/190 v2 pairs pass below 0.84 after the v3
normalization, and all three controls fail with `duplicate_family`.

**Status:** resolved and reverified.

### ASCII-SCALE-003 — Tests did not discriminate the contracts

**Severity:** major

**Scope:** every legacy root.

**Observed evidence:** visible/private tests repeated one happy path; invalid,
boundary, ordering, role, prompt, and false-substitute behavior was absent.

**Why it matters:** a default or generic scaler could survive much of the
advertised family.

**Root cause:** tests were generated from the same example template.

**Remedy:** specify public rules per root, add separate visible/private cases,
role/prompt fixtures, and compile one known-wrong implementation per root as an
expected-failing CTest.

**Verification after remedy:** prompt/role fixtures pass; normal and fresh
ASan/UBSan each discover and pass three tests for all roots.

**Status:** resolved and reverified.

### ASCII-SCALE-004 — Prior false substitutes could fail before execution

**Severity:** blocker

**Scope:** every v2 root in the superseded receipt.

**Observed evidence:** `task_negative` lacked the reference target's strict
warning flags, and every generated substitute returned a default report while
leaving its parameters unused. A compile failure could therefore satisfy an
expected-failing CTest without proving semantic rejection.

**Remedy:** replace the common default body with 20 named policy mutations of
the complete references; compile each with `-Wall -Wextra -Wpedantic -Werror`;
then execute it outside CTest and require exact exit status 1 with empty normal
and sanitizer diagnostics.

**Verification after remedy:** all 40 direct executions meet that contract.

**Status:** prior evidence withdrawn; corrected and reverified.

### ASCII-SCALE-005 — Prior family score retained name-derived evidence

**Severity:** blocker

**Scope:** the v2 family screen and focused regression test.

**Observed evidence:** the v2 token sets and regression assertions retained
task-specific identifiers, profile labels, and unequal hashes as diversity
signals.

**Remedy:** use role-prefixed lexical shingles from actual emitted docs, API,
reference, visible tests, and private tests; normalize identifiers, literals,
domain nouns, and endpoint direction; and route full copied-root adversarial
clones through the same pair decision.

**Verification after remedy:** all 190 family pairs are below 0.84 (maximum
0.679739); domain rename, constants/policy-only, and opposite-end clones all
score 1.0 and are rejected as `duplicate_family`.

**Status:** prior evidence withdrawn; corrected and reverified.

### ASCII-SCALE-006 — Mounted tree digest was not independently attested

**Severity:** blocker

**Scope:** the superseded Docker receipt.

**Observed evidence:** the receipt recorded owner-side live hashes but the
container did not independently calculate the mounted task hashes.

**Remedy:** calculate the exact length-prefixed relative-path and file-byte
digest independently inside Docker, export direct evidence through `/tmp` when
the escalated filesystem snapshot is stale, and let the current owner accept
the result only after live task/reference/revision reconciliation.

**Verification after remedy:** 20/20 mounted hashes equal their live owner
hashes; the imported receipt is bound to the current generator revision.

**Status:** prior evidence withdrawn; corrected and reverified.

## Per-root accounting

Full hashes remain in each `.state/remedy/<legacy-id>.json`; abbreviated hashes
are shown here.

| Legacy root | V2 root | Disposition | Before hash | After hash | Status |
| --- | --- | --- | --- | --- | --- |
| `scale-archive-stamps` | `scale-archive-stamps` | `repair-in-place` | `ebe030718a46…` | `9d45f400e92a…` | `local_family_verified` |
| `scale-cave-warning` | `nine-slice-cave-frame` | `replace` | `534675ea09ee…` | `b85d73269cd4…` | `local_family_verified` |
| `scale-circuit-icons` | `connector-grid-dilation` | `replace` | `628c221f9e4a…` | `f429d0cb9f61…` | `local_family_verified` |
| `scale-evacuation-signs` | `route-map-aspect-fit` | `replace` | `263afc4db190…` | `3bad0a0ad861…` | `local_family_verified` |
| `scale-factory-status` | `status-panel-decimator` | `replace` | `3ea561d10e00…` | `7d81c3010720…` | `local_family_verified` |
| `scale-flood-warning` | `flood-map-majority-downsample` | `replace` | `5cde7abf4c00…` | `7613511a3666…` | `local_family_verified` |
| `scale-game-minimap` | `minimap-viewport-zoom` | `replace` | `98916934a55d…` | `d1188cb9da24…` | `local_family_verified` |
| `scale-garden-plans` | `garden-tile-repeat` | `replace` | `a8f3d2d5e4d3…` | `c4bbde906033…` | `local_family_verified` |
| `scale-harbor-flags` | `flag-stripe-resampler` | `replace` | `01a0b8b10cc5…` | `dae2b474f120…` | `local_family_verified` |
| `scale-lab-plate-map` | `plate-coordinate-expander` | `replace` | `aaf35a3ec26e…` | `84d7ec29f65c…` | `local_family_verified` |
| `scale-museum-wayfinding` | `wayfinding-letterbox` | `replace` | `dcfc3bb97ada…` | `821503fcbecc…` | `local_family_verified` |
| `scale-orchard-layout` | `orchard-sparse-expander` | `replace` | `d2894219f3db…` | `29915a8a9445…` | `local_family_verified` |
| `scale-quilt-preview` | `quilt-block-magnifier` | `replace` | `e79839a20fcd…` | `b99a4a8ae47f…` | `local_family_verified` |
| `scale-radar-glyphs` | `radar-center-anchored-scale` | `replace` | `524100999556…` | `c434f1b3da33…` | `local_family_verified` |
| `scale-school-seating` | `seating-aisle-preserving-scale` | `replace` | `a4456d92eeb4…` | `ced762a3fe25…` | `local_family_verified` |
| `scale-ski-trail-map` | `trail-polyline-raster-scale` | `replace` | `6c0db048f660…` | `7b083fc0058d…` | `local_family_verified` |
| `scale-solar-dashboard` | `solar-palette-quantizer` | `replace` | `c3e583e55f09…` | `1557f73415fb…` | `local_family_verified` |
| `scale-theater-backdrop` | `backdrop-layer-compositor` | `replace` | `c81a2a776681…` | `3cf91fbae7fe…` | `local_family_verified` |
| `scale-warehouse-labels` | `label-runlength-expander` | `replace` | `67c7eaecf6ff…` | `7a98ed0791bd…` | `local_family_verified` |
| `scale-weather-symbols` | `weather-frame-atlas-scale` | `replace` | `9c21e16f02dd…` | `5b3ca6e9d0be…` | `local_family_verified` |

## Changed owners and generated/reused files

Changed checked-in owners: the curriculum, materialization guide, wrapper,
`moonlight_ascii_art_scaling_aider_tasks.py`, its cases module, this audit, and
the focused pytest. The owner regenerated all v2 task directories and updated
the family screen, host receipt, Docker receipt, and 20 remedy records. The 20
legacy directories and bound official checkout were reused read-only.

## Final validation

- `uv run pytest -q tests/test_moonlight_ascii_art_scaling_aider_tasks.py`:
  `6 passed`.
- `uv run pytest -q tests/test_aider_sft_scope_docs.py`: `4 passed`.
- Targeted Ruff on the owner, cases, and focused test: passed.
- Remediation skill validation: passed.
- Python compilation of both owner modules: passed.

## Conclusion

All 20 v2 roots have `primary_core_objective: achieved`, are structurally valid,
pass the strongest available image-bound normal and sanitizer check, pass
family and bound-holdout screens, and reached `local_family_verified`. This is
local candidate evidence only—not locked-oracle evidence, dataset admission,
training authorization, a release, or benchmark uplift.
