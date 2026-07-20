# Run-Length-Encoding Family Remediation

## Scope and result

Selected workflow prompt:
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`.
Inputs were `FAMILY_NAME=run-length-encoding` and `FAMILY_TYPE=aider-dsa`.
The immutable legacy root is
`.w8-biayn/data/aider-tasks/aider-dsa/run-length-encoding/`; the v2 owner writes
only `.w8-biayn/data/aider-tasks-reverify/aider-dsa/run-length-encoding/`.

The family reached `local_family_verified`. This is pinned, network-disabled
Docker sanity evidence for local task authoring, not a locked-oracle, dataset,
training, release, or benchmark-uplift claim.

## Audit findings

### RLE-F01 — one renamed bounded-run template

All 20 legacy roots used the same `vector<Run>` authority, nonempty symbol and
positive-units validation, scalar append plus transactional chunk append,
split-at-255 behavior, expansion, longest-run query, and tests. Normalizing
identifiers and literals produced only two reference signatures: one shared by
18 roots and one shared by two roots. The declared domains therefore did not
create materially distinct primary logic or implementations.

Disposition follows the deterministic rule: the lexicographically smallest
independently repairable representative, `rle-access-badges`, is
`repair-in-place`; the other 19 roots are `replace` with new IDs. Rename-only
retention is forbidden.

### RLE-F02 — curriculum contracts were not implemented

The curriculum promised row boundaries, timestamp spans, duration caps,
state-machine transitions, tolerance buckets, binary-record validation,
protected regions, calendar gaps, partial decode cursors, and offset indexes.
The legacy generator ignored those rules and emitted the generic template for
every row. The v2 references implement one distinct mechanism per root and the
hidden tests exercise its observable invariant and boundary.

### RLE-F03 — negative fixtures and evidence were incomplete

The legacy owner had no prompt/role verifier, artifact-derived all-pairs family
screen, bound semantic holdout screen, compiled false substitute, positive test
discovery receipt, explicit `Unix Makefiles` compiler binding, or Docker-bound
normal/sanitizer receipt. The v2 owner fails closed for each of these gates and
records 39 remedy record/specification pairs: 20 legacy identities plus the 19
new replacement identities.

### RLE-F04 — declaration-derived hard-rule overclaim

The first v2 screen compared in-memory `CASES` declarations even though its
report called the evidence artifact-derived. Its focused test asserted pair
counts and declared profiles but did not inject clones into copied generated
roots. The resulting `local_family_verified` claim and receipt SHA-256
`36f8b7c845768f43b97ae9433ee3bc10c800e66164caef71157d4d0542eedfaa`
were invalidated through the owner-controlled force path and are not reusable.

The corrected screen rereads the actual emitted docs, public header, mapped
reference files, visible/private tests, and compiled negative substitute for
every root. It records normalized evidence for public API, owned state and
algorithm, mutation/selection, invalid and boundary behavior, reference
control flow, deterministic oracle, and topic-specific negative fixture. The
wrong substitute remains excluded from the combined primary-logic corpus, so
it cannot manufacture apparent diversity.

## Legacy dispositions and replacements

| Legacy root | Disposition | Retained/replacement root | Primary v2 mechanism |
| --- | --- | --- | --- |
| `rle-access-badges` | repair-in-place | `rle-access-badges` | per-door independent denial streaks |
| `rle-audio-silence` | replace | `amplitude-tolerance-runs` | fixed-representative tolerance buckets |
| `rle-barcode-scans` | replace | `barcode-batch-cursor` | partial run decoder cursor |
| `rle-bus-occupancy` | replace | `occupancy-plateau-index` | timestamped open/closed plateaus |
| `rle-chat-reactions` | replace | `reaction-cluster-editor` | canonical run-level splice editor |
| `rle-dna-quality` | replace | `quality-delta-runs` | signed-delta run codec |
| `rle-document-whitespace` | replace | `protected-whitespace-runs` | mode-aware whitespace canonicalizer |
| `rle-factory-defects` | replace | `defect-threshold-index` | online first-threshold index |
| `rle-game-terrain` | replace | `terrain-row-decoder` | row-addressed checksum decoder |
| `rle-inventory-shelves` | replace | `shelf-gap-index` | split/merge maximal free intervals |
| `rle-log-severity-spans` | replace | `severity-time-spans` | contiguous timestamp span coalescing |
| `rle-medication-adherence` | replace | `adherence-calendar-streaks` | calendar-contiguous missed streaks |
| `rle-monochrome-raster` | replace | `raster-row-runs` | row-bounded binary encoding |
| `rle-network-flags` | replace | `flag-record-decoder` | compact binary count-record parser |
| `rle-power-modes` | replace | `power-energy-runs` | exact numerator energy ledger |
| `rle-pricing-bands` | replace | `price-offset-index` | prefix-end binary-search index |
| `rle-telemetry-packets` | replace | `packet-run-stream` | bounded pending/emitted packet stream |
| `rle-traffic-lights` | replace | `signal-phase-coalescer` | legal-transition state machine |
| `rle-video-frame-holds` | replace | `frame-duration-runs` | capped duration holds and time lookup |
| `rle-weather-stations` | replace | `station-chunk-carry` | transactional chunk carry and finish |

Every row has `primary_core_objective: achieved` in its current remedy record.

## Structural and semantic evidence

The focused test and owner `--verify-core` check deterministic regeneration,
safe role maps, exact reference ordering, whole-file response rejection cases,
prompt completeness, private-file exclusion, task-specific core markers, the
legacy-template negative screen, benchmark slug separation, and semantic
content comparison.

Normalizer `run-length-semantic-v3-emitted-artifact-dimensions-9gram` reads the
actual generated tree. All 190 unordered family pairs passed; maximum combined
overlap is `0.450253`, below the blocking `0.72` threshold. Maximum overlap by
required dimension is:

| Hard-rule dimension | Maximum overlap |
| --- | ---: |
| public API | `0.594203` |
| owned state / algorithm | `0.426332` |
| mutation / selection | `0.468599` |
| invalid / boundary behavior | `0.634921` |
| reference control flow | `0.318182` |
| deterministic oracle | `0.669202` |
| topic-specific negative fixture | `0.634021` |

For every stateful root, the emitted hidden oracle now invokes every public
operation and uses an independent expected value/vector state after each
mutation to compare the complete observable ordering and query results. The
owner derives the operation-presence check from the actual emitted public
header and hidden test and fails with `trace_contract_incomplete` when an
operation or state oracle is removed.

The focused tests copy an emitted `rle-access-badges` root, mutate its actual
artifacts into domain/identifier-renamed, constants/policy-only, and
opposite-end-selection clones, and pass each copy through the production pair
screen. Every clone has combined overlap `1.0`, violates all seven dimensions,
and raises `duplicate_family`. A separate fixture proves that changing only a
bad substitute cannot rescue duplicated primary logic.

All 20 candidates were compared with all 26 bound official Aider C++ holdouts.
The strongest comparison was `price-offset-index` versus `meetup` at
`0.130208`, below the blocking `0.60` threshold. The bound source inventory
digest is persisted in `.state/family-screen.json`.

## Docker sanity evidence

Host oracle execution was `not_completed` because the host has no `c++`
executable. The mandatory verifier then ran as UID/GID 1000 in:

```text
w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991
```

Networking was disabled. The compiler was `/usr/local/bin/g++`, GCC 13.4.0,
binary SHA-256
`152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`;
CMake/CTest were 3.25.1. Every reference passed three normal tests and three
tests in a separate fresh `-fsanitize=address,undefined` build. The third test
compiled each task's incomplete substitute and required its hidden behavioral
test to reject it.

Receipt `.state/docker-sanity.json` has SHA-256
`d574d1bda7be59a975ca3f1bfff82476922957a79b17ab9b75c444090eed8691`.
It binds owner, current task trees and references, image, toolchain, commands,
network policy, family screen, and equal positive discovery counts. The combined
owner-plus-case-source generator hash is
`sha256:0586a2ad58937a9cf3ffa0748e7a7b26f25633c31a0fd9206578a0d7e8f33997`.
All 39 current remedy records bind findings `RLE-F01` through `RLE-F04` and
that generator revision.

## Current task-tree hashes

| Task | Tree hash |
| --- | --- |
| `rle-access-badges` | `sha256:04bb24c630a9ed2b425ca6f44f35425405ed8f3ba5a7a989b1c47957b85faa78` |
| `packet-run-stream` | `sha256:ae6e5c2c1fd67c922e66c3c55b7dcf9561643952b5749225eca045215b8cca75` |
| `raster-row-runs` | `sha256:4c31f503b55154cc95fcb8c73edcb60302cbf38652afc753d7fb4571a6724ef7` |
| `quality-delta-runs` | `sha256:afd8ee9cc9cf9776d5f265a2788f87e5c713d3ff25052c6ef3b72eb9a8603040` |
| `severity-time-spans` | `sha256:0fac4433a01fcec60b14a0ea78181ef88cadddb3bf5c6f736ebfe3da209c98e2` |
| `frame-duration-runs` | `sha256:76a280f148a3cf49448862cccd1f1feba86a2601dd09491662c4b6a7c64055c0` |
| `signal-phase-coalescer` | `sha256:0125c54ab38bbebf221d1b191c5dc82bf1c2f094330dd95bfde7b4aeacaf84f2` |
| `defect-threshold-index` | `sha256:3a1ab06489e64c2a2e93c50f5c65896a9f1a10cedd53007502a773fc9f7b3e84` |
| `amplitude-tolerance-runs` | `sha256:1f3107f60e44df0147bd271a6944751ebcaf163549efa869181ac01cc613aca5` |
| `station-chunk-carry` | `sha256:a8d1c4c4c8d316049f003b3ef19f31fddc0c713fe102e759d030cee7e5ab114a` |
| `flag-record-decoder` | `sha256:230feb880237ae99e0ab41f85299a0ddb559b14c038703ce4873fa449e2a588a` |
| `shelf-gap-index` | `sha256:a53869f3a79678237c774db8bf7d8f320b019c5f7ccad0a879ca1fb9d1b0569c` |
| `protected-whitespace-runs` | `sha256:07c9871d1e424b5a2d321e8f4757d6151e732aefb5ade03897dcc871e860e382` |
| `terrain-row-decoder` | `sha256:1632335f5a0855bc844e40a75dd960d3c28558f5cd6e197cf4cf66151fd2ff1c` |
| `adherence-calendar-streaks` | `sha256:c8fa92e5ba0e4cac00966897bd5f9796309f14880ea2a68866891b5d322aef4e` |
| `power-energy-runs` | `sha256:ecc41d98e60aaf6640b43fd1ef7958917cb6f0eea402daa4f74d1bb975b62a65` |
| `reaction-cluster-editor` | `sha256:1b1292658cc522ab9ba8447f1a1dda36019a3e95c3f9331649a1672f40057fc4` |
| `occupancy-plateau-index` | `sha256:a095d233ed8e8ae92a4b832ebc5f9ad3ca0db87ba6215f2a1464a460fa9ed224` |
| `barcode-batch-cursor` | `sha256:07fd1947592df2b8cc2d3f36c661e074b2162aa18770cae39cb92b5c959a3d89` |
| `price-offset-index` | `sha256:831df49c8e7962bf029f5f418dd676e9801cf238eb6d757ae77ddbe6ff44b5bb` |

## Gate separation and conclusion

| Gate | Result |
| --- | --- |
| Legacy preservation | pass; no legacy task file changed |
| Primary objective | pass for 20/20 v2 roots |
| Prompt/roles/reference mapping | pass |
| Deterministic stateful traces | pass; every emitted public operation and complete public state/order checked after mutations |
| Compiled topic-specific negative fixture | pass for 20/20 in both modes |
| Hard diversity / duplicate-family screen | pass, 190/190 actual emitted-artifact pairs across seven dimensions; all three copied-root clone controls rejected |
| Benchmark contamination | pass, 20 × 26 comparisons |
| Docker normal and fresh ASan/UBSan | pass, 3/3 tests per root and mode |
| Locked oracle | not claimed; evidence class is `docker_sanity` |
| Local remediation | `local_family_verified` |
| Dataset/release/training | not requested and not evaluated |

Changed owner surfaces are the run-length owner, its new case definitions,
focused test, wrapper, curriculum, this audit, and the materialization guide.
Generated output is confined to the reverify root. The legacy tree and bound
official holdout checkout were reused read-only.
