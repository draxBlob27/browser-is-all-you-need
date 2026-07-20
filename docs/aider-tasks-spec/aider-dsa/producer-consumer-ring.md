# Producer-Consumer Ring Reverification Audit

## Scope

This report covers all 20 legacy roots under
`.w8-biayn/data/aider-tasks/aider-dsa/producer-consumer-ring` and their
generator-owned replacements under the parallel `aider-tasks-reverify` root.
The selected workflow is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`. The legacy tree
was audit input only and was not regenerated or edited. No dataset handoff was
requested.

## Primary finding and disposition

`PCR-F1-CORE-SUBSTITUTE` and `PCR-F2-TEMPLATE-DUPLICATION` were major
findings. Every legacy root used the same `std::deque<int>` state, the same
publish/take/close implementation, the same public shape, and nearly the same
tests. Domain nouns, method names, cardinality strings, and four overflow
branches did not create independent learning objectives. The core advertised
ring mechanisms were therefore not achieved.

All roots received `replace` dispositions before owner changes. The v2 family
contains 20 independent state models: slot cursors, generation overwrite,
per-source fair subrings, fragment assembly, weighted severity lanes, inverse
transition reduction, sequence reordering, keyed coalescing, watermark
release, epoch barriers, reservation/commit state, watermarked k-way merge,
aging priority, hash-chain admission, change algebra, dispatch/ack retry,
broadcast cursors, stamped aggregates, sealed snapshots, and generation-window
deduplication.

## Commands and evidence

- Focused materialization tests: `UV_CACHE_DIR=/tmp/w8-uv-cache uv run pytest
  -q tests/test_moonlight_producer_consumer_ring_aider_tasks.py`.
- Owner core verifier: `PYTHONPATH=src python3 -m
  w8_biayn.integrations.moonlight_producer_consumer_ring_aider_tasks --force
  --verify-core`.
- Locked oracle verifier: `docker run --rm --network none ... 4cff5e0d746a
  python3 -m
  w8_biayn.integrations.moonlight_producer_consumer_ring_aider_tasks --force
  --verify`.
- Exact image:
  `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`;
  CMake 3.25.1; GCC 13.4.0.
- Every root discovered three normal and three fresh ASan/UBSan tests
  (visible, hidden, and independent model trace), with all 120 reference test
  executions passing.
- Every root also compiled a task-specific broken reference and executed its
  independent-model rejection path. All 20 negative fixtures were rejected; a
  compile failure or timeout was not accepted as negative evidence.
- `.state/materialization-manifest.json` records prompt-boundary,
  reference-mapping, duplicate-family, benchmark-ID, and semantic-contamination
  passes. The strongest normalized holdout similarity was 0.024348, far below
  the rejection threshold.
- `.state/oracle-receipt.json` binds the image, compiler, CMake, network-none
  policy, commands, owner-source hashes, generated-tree hashes, reference and
  model-test hashes, all 20 equal positive test counts, and all 20 executable
  negative outcomes. The separate owner `--verify-receipt` pass recomputed
  those hashes from the live tree before marking remedies verified.

## Structural verification matrix

| Gate | Result |
| --- | --- |
| Primary core objective | achieved for all 20 v2 roots |
| Prompt exposes only docs and two declared editable files | pass |
| References map one-to-one in editable-file order | pass |
| Missing/extra/prose whole-file substitutions | rejected |
| Legacy deque/queue substitute | rejected by static screen and 20 executable task-specific negative fixtures |
| Independent stateful model trace | pass; every public operation class checked against a separate value/container model |
| Duplicate semantic kind/signature/control flow | pass; 20 of 20 unique and no normalized structural pair reached the 0.82 rejection threshold |
| Official 26-root ID/content screen | pass |
| Locked normal reference | pass; 3 tests per root |
| Fresh locked ASan/UBSan reference | pass; 3 tests per root |
| Topic-specific broken reference | pass; 20 of 20 compiled and were rejected by independent-model execution without timeout |
| Dataset handoff | not_requested |

## Per-root remedies

| Legacy root | Replacement root | Disposition | Before tree | After tree | Status |
| --- | --- | --- | --- | --- | --- |
| `pcr-audio-capture` | `audio-spsc-frame-pipe` | replace | `1db74284d664` | `6eae8f6a8207` | local_family_verified |
| `pcr-build-events` | `build-epoch-barrier-ring` | replace | `23a755e066ec` | `c11c0cec0c25` | local_family_verified |
| `pcr-camera-frames` | `camera-generation-overwrite` | replace | `5ae211095af4` | `010d98f7b006` | local_family_verified |
| `pcr-can-bus` | `can-sequence-reorder-window` | replace | `498cb37a1ccd` | `2a012d609c6c` | local_family_verified |
| `pcr-file-watch` | `file-change-debounce-ring` | replace | `d75c8a1d2e64` | `262374625557` | local_family_verified |
| `pcr-game-input` | `game-tick-snapshot-ring` | replace | `eac6f0b95dbc` | `59e8c414b8f5` | local_family_verified |
| `pcr-gps-samples` | `gps-watermark-batch-ring` | replace | `dd06b0f2acda` | `319c2d8bb890` | local_family_verified |
| `pcr-keyboard-events` | `keyboard-transition-coalescer` | replace | `f7cdad09ddcd` | `23c632aa9e53` | local_family_verified |
| `pcr-log-ingest` | `log-severity-lane-ring` | replace | `86e6c4c8fdd7` | `85385006d707` | local_family_verified |
| `pcr-market-ticks` | `market-symbol-coalescing-ring` | replace | `f495afdab32d` | `f12adf023277` | local_family_verified |
| `pcr-network-receiver` | `network-fragment-assembly-ring` | replace | `2dd4ed256ac0` | `e122fd42154c` | local_family_verified |
| `pcr-payment-events` | `payment-hash-chain-ring` | replace | `2bd42d2f1c45` | `721b74bb5592` | local_family_verified |
| `pcr-print-pipeline` | `print-aging-priority-ring` | replace | `8fdff87cfb05` | `836d74d9cd42` | local_family_verified |
| `pcr-robot-commands` | `robot-command-retry-ring` | replace | `430bd7699187` | `0b2ea7daca80` | local_family_verified |
| `pcr-sensor-fusion` | `sensor-timestamp-merge-ring` | replace | `9522a0325580` | `3df12b3b430f` | local_family_verified |
| `pcr-support-notifications` | `support-broadcast-cursor-ring` | replace | `e374a1923307` | `3c08453943e6` | local_family_verified |
| `pcr-telemetry-uplink` | `telemetry-source-quota-ring` | replace | `f759242df0f9` | `339fd83c4438` | local_family_verified |
| `pcr-video-segments` | `video-reservation-commit-ring` | replace | `e7a8dcc970f2` | `df7f9f9a2510` | local_family_verified |
| `pcr-warehouse-scans` | `warehouse-dedup-window-ring` | replace | `85578724583d` | `d0b139c62e23` | local_family_verified |
| `pcr-weather-station` | `weather-aggregation-bucket-ring` | replace | `7ae47580eb60` | `21c3b30089f7` | local_family_verified |

## Changed and reused paths

Changed owners are the curriculum, the producer-consumer generator, its
case-assets and executable-verification modules, focused tests, wrapper, and
this report. Generated v2
roots and their remedy/oracle state were regenerated only through the owner.
The legacy 20-root tree and the canonical 26-root holdout material were reused
read-only.

## Conclusion

The primary core objective is achieved separately for every v2 root, and all
secondary local gates pass. Every replacement reached
`local_family_verified`. This conclusion does not authorize SFT rows,
training, release, or benchmark-uplift claims.
