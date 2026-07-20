# Circular-Buffer Family Remediation: Cyclic Slot Systems

## Scope and result

Selected workflow prompt:
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`.

Inputs were `FAMILY_NAME=circular-buffer` and `FAMILY_TYPE=aider-dsa`. The
binding user count is 15–20 roots; this remediation emits exactly 15. The
legacy root `.w8-biayn/data/aider-tasks/aider-dsa/circular-buffer/` was absent
and remains absent. Its historical 20-root tree was reconstructed only under
`/tmp` from Git revision `854a7d99e0185129a971e443bb86b4a91a39b456` for
auditing. The replacement owner refuses the legacy output path and owns only:

`.w8-biayn/data/aider-tasks-reverify/aider-dsa/circular-buffer/`.

The result is `local_family_verified`. This status is bound to a pinned,
network-disabled Docker sanity receipt and is not a locked-oracle, dataset
release, training, or benchmark-uplift claim.

## Audit findings

### CB-F01 — official circular-buffer semantic overlap

All 20 legacy `ring-*` roots implemented fixed-capacity FIFO storage,
oldest-value removal, full-write rejection, or overwrite-oldest behavior. Those
are primary observable rules of the bound official `circular-buffer` holdout.
All 20 roots are rejected; noun and method renaming cannot decontaminate them.
The 15 replacements forbid FIFO, oldest-item, and forced-overwrite solutions
and pass whole-role screening against all 26 bound C++ holdouts.

### CB-F02 — noun-template family duplication

The 20 legacy references reduced to three shared implementation shapes with
only domain nouns and overflow policies changed. Repeating that shape would not
create independent learning objectives. The replacement family instead uses 15
different APIs, state representations, mutation rules, boundary behavior,
control flow, reference algorithms, and task-specific oracles.

Verification uses `cyclic-slot-semantic-v4-artifact-derived`. Its evidence is
derived from each emitted prompt, API, reference, public test, and hidden test,
not task IDs, kind labels, declared signatures, or hashes. It compares every
unordered pair: 105/105 pairs were screened. The highest overlap was 0.184049
for `clockwise-token-router` versus `generation-arrival-barrier`, below the
blocking 0.70 threshold.

Focused adversarial controls also reject all required superficial variants:

| Clone class | Measured overlap | Result |
| --- | ---: | --- |
| domain/identifier renamed | 1.000000 | `duplicate_family` |
| constants-or-policy-only | 0.997238 | `duplicate_family` |
| opposite-end selection | 1.000000 | `duplicate_family` |

### CB-F03 — incomplete observable-state and rejection gates

The first replacement revision did not expose complete state after every
operation and did not execute every documented rejection path. The final owner
uses task-specific observable-state APIs and independent deterministic oracles,
checks state after every mutation, and executes whole-format, role safety,
missing/misordered reference, prompt-contract, mechanism-removal,
topic-substitute, cross-root-substitution, and duplicate-file rejection
fixtures for every root.

### CB-F04 — binding root-count shortfall

An earlier three-root replacement did not satisfy the updated binding request
of 15–20 roots. The owner now enforces `MIN_ROOTS = 15` and `MAX_ROOTS = 20` at
module load and verification time. Negative fixtures reject 14 and 21 roots;
boundary fixtures accept 15 and 20. The generated inventory contains exactly
15 task roots.

## Legacy dispositions

Every legacy root has a schema-v1 JSON record and a 12-section Markdown remedy
specification under the re-verification root's `.state/remedy/` directory.

| Legacy root | Core objective | Disposition | Findings |
| --- | --- | --- | --- |
| `ring-audio-frame-store` | bounded FIFO, reject-full | reject | CB-F01, CB-F02 |
| `ring-build-events` | bounded FIFO, overwrite-oldest | reject | CB-F01, CB-F02 |
| `ring-bus-messages` | bounded FIFO, optional overwrite | reject | CB-F01, CB-F02 |
| `ring-camera-preview` | bounded FIFO, optional overwrite | reject | CB-F01, CB-F02 |
| `ring-currency-quotes` | bounded FIFO, overwrite-oldest | reject | CB-F01, CB-F02 |
| `ring-customer-arrivals` | bounded FIFO, reject-full | reject | CB-F01, CB-F02 |
| `ring-delivery-scans` | bounded FIFO, reject-full | reject | CB-F01, CB-F02 |
| `ring-game-replay` | bounded FIFO, overwrite-oldest | reject | CB-F01, CB-F02 |
| `ring-gps-trail` | bounded FIFO, overwrite-oldest | reject | CB-F01, CB-F02 |
| `ring-keyboard-input` | bounded FIFO, reject-full | reject | CB-F01, CB-F02 |
| `ring-log-tail` | bounded FIFO, overwrite-oldest | reject | CB-F01, CB-F02 |
| `ring-machine-alerts` | bounded FIFO, optional overwrite | reject | CB-F01, CB-F02 |
| `ring-medication-reminders` | bounded FIFO, optional overwrite | reject | CB-F01, CB-F02 |
| `ring-network-packets` | bounded FIFO, reject-full | reject | CB-F01, CB-F02 |
| `ring-print-spool` | bounded FIFO, reject-full | reject | CB-F01, CB-F02 |
| `ring-stock-ticks` | bounded FIFO, overwrite-oldest | reject | CB-F01, CB-F02 |
| `ring-telemetry-history` | bounded FIFO, optional overwrite | reject | CB-F01, CB-F02 |
| `ring-ui-event-queue` | bounded FIFO, reject-full | reject | CB-F01, CB-F02 |
| `ring-weather-readings` | bounded FIFO, overwrite-oldest | reject | CB-F01, CB-F02 |
| `ring-workout-laps` | bounded FIFO, overwrite-oldest | reject | CB-F01, CB-F02 |

## Replacement diversity matrix

| Replacement root | Primary mechanism and authoritative state | Distinct mutation/control-flow objective | Tree hash |
| --- | --- | --- | --- |
| `parking-permit-slot-allocator` | occupancy bits plus search cursor | circular first-fit reserve/release/acquire scan | `sha256:4a064f2b146fd27c32ed95741956b61e9340f01fb56530f7207426958f0d73d3` |
| `maintenance-duty-wheel` | tick-indexed ID buckets plus current tick | delayed scheduling, cancellation, and tick advancement | `sha256:4b10f82e5bfb85278c9f00aa15a05861bab10b8480f7278723b064fc8cb67977` |
| `api-sampling-window-counter` | stamped modular aggregate buckets | timestamp record and recent-window aggregation | `sha256:cc6028f703df27a514ef8f63004d528187f868dd673ebc775cf5c198c313ef40` |
| `weighted-service-rotor` | per-service smooth weights and scores | score accumulation, maximum selection, and weight subtraction | `sha256:2b769afbaa902668e25a21b96cdea86fed1996f2ea11d3bc37df8a57f07aae0d` |
| `generation-arrival-barrier` | generation counter plus arrival bitmap | duplicate-safe arrival and generation rollover | `sha256:2dc13ef7aa4e5c01d564da22d8190503bb31465237ac388736a9f4da5a27be40` |
| `traffic-phase-controller` | phase sequence, durations, and elapsed offset | multi-transition duration consumption | `sha256:571287b69bebb9d62096ede15cecad6dd35db10b0620fcf4d01b1c9de8fbbbf4` |
| `circular-signal-convolution` | immutable modular signal/kernel vectors | modular-index convolution over all output positions | `sha256:97085ff571963de0d0be4e10dbe83381eb0a00cca7bf19a6c2d67482c5b10756` |
| `modular-arc-set` | canonical disjoint modular intervals | wrapped-arc insertion, merge, and membership | `sha256:b4e874fdcc7c021fecfe7545a65799248f6de6798753c133e43002fc87b06699` |
| `clockwise-token-router` | sorted token positions and ownership | modular lower-bound successor routing | `sha256:dd93aa8af24193c34c11f82f385bc107cd33675e0c75d01d000bdbcb9e30793b` |
| `functional-cycle-index` | successor graph with depth/cycle metadata | path walk, cycle detection, and indexed jump behavior | `sha256:490ba050dd71c5e5e01b38d16a38deb538a2474b08962c4b85b8cc3071a76689` |
| `round-robin-pairing-table` | rotating participant order | circle-method schedule generation with byes | `sha256:83ae7071c7337e075cddf51cc4132908092bd4d400dfa03a4e4bd72baa6e6c4a` |
| `crc-byte-register` | fixed-width polynomial register | byte/bit feedback shifts and polynomial reduction | `sha256:2d4d39dc19fe63e0776a30cb97cfee14fa8d7e8ff3374b9a4093ed9659201a70` |
| `epoch-stamped-sparse-table` | values plus generation stamps | O(1) logical clear and lazy slot initialization | `sha256:0ab1e9d02a2739622ac27393711cabfc249a3875bd5f3e17fa9edd5f6b96d8fb` |
| `rotating-bloom-membership` | time-sliced bitsets and hash probes | slice rotation, expiry, and probabilistic membership | `sha256:3a54474c1d07ba47ad1967d309e616873c5f32d1dbe837a033e1b6aeb263b7fb` |
| `serial-replay-window` | wrap-safe newest serial plus replay bitmap | modular ordering, window shift, duplicate/old rejection | `sha256:b01bd3036a8619a8d2f760773246f0c4605b4fd674b4c4d566cbeef17339f3f1` |

All 15 replacement records report `primary_core_objective: achieved`. A
different task name or `kind` is not counted as diversity evidence.

## Structural, semantic, and oracle evidence

The owner regenerated the exact 15-root inventory and passed `--verify-core`:

```text
PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_cyclic_slot_systems_aider_tasks \
  --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/circular-buffer \
  --force --verify-core
```

This proves generator-output parity, prompt boundaries, complete and safe role
maps, reference ordering, full negative-fixture execution, exact-count bounds,
all-pairs duplicate screening, and 26-root benchmark screening. The largest
candidate-to-holdout overlap was 0.040268456375838924 for
`serial-replay-window` against `perfect-numbers`, below the blocking 0.80
threshold.

The final runtime command used the pinned image by digest and disabled the
network:

```text
docker run --rm --network none \
  --mount type=bind,src=/data/sanil/browser-is-all-you-need,dst=/workspace \
  --workdir /workspace \
  w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991 \
  sh -lc 'PYTHONPATH=/workspace/src python3 -m \
    w8_biayn.integrations.moonlight_cyclic_slot_systems_aider_tasks \
    --out /workspace/.w8-biayn/data/aider-tasks-reverify/aider-dsa/circular-buffer \
    --force --verify-core --verify'
```

Image ID and digest are both
`sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
The compiler was `/usr/local/bin/g++`, GCC 13.4.0, with binary SHA-256
`152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`;
CMake and CTest were 3.25.1. Every root passed 2 normal tests and 2 tests in a
separate fresh `-fsanitize=address,undefined` build. Receipt
`.state/docker-sanity.json` validates the current owner revision, all 15 tree
and reference hashes, the container/host mount match, toolchain, command, and
network policy. Its SHA-256 is
`69efdb15f4796914431d1fc047c7546e914dd7ba25eff6400d91cc39b35d224d`.

## Gate separation

| Gate | Result | Meaning |
| --- | --- | --- |
| Binding count | pass: exactly 15 | satisfies the explicit 15–20 request; 14/21 fail and 15/20 pass |
| Primary core objective | pass for 15/15 | each emitted reference implements its distinct stated mechanism |
| Structural/prompt/role/negative screen | pass | regeneration parity and all fail-closed family checks passed |
| Artifact-derived duplicate screen | pass: 105/105 pairs | maximum overlap 0.184049; all three adversarial clone classes rejected |
| Pinned Docker normal plus fresh ASan/UBSan | pass: 2/2 per root | network-disabled sanity evidence bound to image, owner, tree, references, commands, and toolchain |
| Locked oracle | not claimed | the accepted local evidence class is `docker_sanity`, with `locked_oracle: false` |
| Local family remediation | `local_family_verified` | all local family gates are complete |
| Dataset/training/release suitability | not evaluated | release-only gates were not authorized or run |

## Changed, regenerated, and reused paths

Changed owner surfaces are the cyclic-slot owner module, focused tests,
preparation wrapper, curriculum, this audit, and the materialization guide.
Regeneration is confined to the re-verification root: 15 task roots, 35 remedy
record/spec pairs (20 reject and 15 replace), the family screen, and the
owner-imported Docker sanity receipt. The 26-root benchmark manifest and bound
upstream checkout were reused without modification. The absent legacy generated
root was not recreated.

## Conclusion

All 20 contaminated/template-clone legacy roots remain rejected. Exactly 15
replacement roots are emitted, and their differences are in logic and
implementation—not merely names. All local remediation gates passed, including
the updated exact-count hard rule, all 105 emitted-artifact comparisons, the
three mandatory superficial-clone rejection controls, and pinned
network-disabled normal plus fresh sanitizer verification. The family is
`local_family_verified`; no dataset handoff, release, training, or uplift claim
is made.
