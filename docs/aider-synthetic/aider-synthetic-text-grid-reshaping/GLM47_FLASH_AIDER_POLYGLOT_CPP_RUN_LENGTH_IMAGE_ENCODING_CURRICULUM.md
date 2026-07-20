# Run-Length Image Encoding Curriculum: Remediated Capability

Status: `local_family_verified`. This is local clean-room task material, not an
SFT dataset, release, training authorization, or benchmark result.

The immutable legacy family used one shared row encoder/decoder plus selected
aggregate policies. Its twenty v2 replacements instead require materially
different image-RLE algorithms and deterministic false-substitute rejection.

## Decontamination Boundary

All 26 official Aider C++ roots and excluded generic RLE source families are
permanent holdouts. The owner screens emitted docs, APIs, references, visible
and private tests, and negative fixtures. Runs remain row-local, positive, and
canonical; every root adds its own pixel model, validation, selection, and
algorithmic invariant.

## Verified Replacement Inventory

| Replacement root | Core mechanism |
| --- | --- |
| `crop-row-histogram-codec` | canonical row encoding with stable first-seen histogram |
| `radar-column-threshold-decoder` | decoded per-column threshold maxima |
| `mask-component-bounds-codec` | four-connected BFS component boxes |
| `aisle-reachability-decoder` | stack-based orthogonal reachability |
| `lesion-component-boxes-codec` | scanline interval component merging |
| `cloud-clear-window-decoder` | rolling largest-clear-square dynamic program |
| `quilt-seam-transition-canonicalizer` | horizontal/vertical seam accounting |
| `mosaic-palette-row-encoder` | stable palette-index run encoding |
| `canopy-block-density-index` | integral-image block density |
| `wildfire-border-perimeter-decoder` | border-connected perimeter traversal |
| `vacancy-rectangle-run-index` | row-vacancy audit plus monotone-stack largest rectangle |
| `coral-component-histogram-codec` | union-find component histogram |
| `panel-defect-interval-decoder` | panel projection and interval merging |
| `snow-map-delta-codec` | row-wise XOR delta runs |
| `lane-blockage-run-auditor` | lane-specific consecutive blockage limits |
| `shelf-empty-span-index` | ordered maximal empty-span selection |
| `conductor-pad-connectivity-decoder` | conductive-pad union connectivity |
| `dry-bed-span-merger` | cross-bed dry interval intersection |
| `transparent-border-crop-decoder` | transparent-border validation and crop bounds |
| `safe-channel-widest-path-codec` | maximum-bottleneck west/east channel search |

## Verification Contract and Result

Materialize only under the parallel reverify root:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_run_length_image_encoding_aider_tasks.sh --force --verify-core
```

The owner compares all 190 unordered pairs conjunctively across the seven hard
rule dimensions after removing family-common boilerplate. Focused tests prove
that identifier/domain renames, constants-or-policy-only clones, and
opposite-end-selection clones make nonempty changes across the required emitted
roles. The same controls remain coherent, compile in normal and sanitizer
modes, pass their transformed reference contract, and are rejected by the
production semantic evaluator.

The final network-disabled Docker sanity receipt binds generator
`sha256:0cc49d2b4ed6bce8d57dcda9d9489c535fc9285a3808fce5654832a2bd093d8a`,
GCC 13.4.0, CMake 3.25.1, and the pinned image digest. All twenty roots passed
four normal and four fresh ASan/UBSan tests: visible, hidden, dedicated
discriminator on the reference, and the executed `WILL_FAIL` false algorithm.
All false algorithms and clone-control false algorithms exited `1` without
sanitizer diagnostics. Dataset handoff remains `not_requested`.
