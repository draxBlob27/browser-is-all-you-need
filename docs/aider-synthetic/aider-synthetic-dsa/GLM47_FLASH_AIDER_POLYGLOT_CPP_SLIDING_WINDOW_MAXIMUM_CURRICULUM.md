# Sliding-Window Maximum Curriculum: Topic 1, Sliding-Window Maximum

Status: v2 local-family remediation. The legacy 20-root monotonic-deque
template remains preserved under `.w8-biayn/data/aider-tasks/`; its one-to-one
replacements are owned under `.w8-biayn/data/aider-tasks-reverify/`. This does
not claim dataset admission, training authorization, or benchmark uplift.

This curriculum teaches monotonic-deque maintenance over a bounded moving
window: expire out-of-window entries, preserve decreasing candidate values,
handle equal-value tie policy, and report the correct current maximum.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Online Material Status

Sliding-window-maximum examples are readily available online in algorithm
resources and online judges. They are useful for private concept study or
source discovery only. They are not a drop-in SFT source inventory: every
external source needs explicit license and semantic-contamination review.

The legacy tasks below were audited as semantic template duplicates. The v2
owner replaces every root with the distinct ID and mechanism specified in
`docs/aider-tasks-spec/aider-dsa/sliding-window-maximum.md`.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `swmax-stock-peaks` | Stock peaks | Report the highest price in each rolling tick window with deterministic equal-price ties. |
| `swmax-temperature-alerts` | Temperature alerts | Track the maximum recent temperature and emit an alert above a threshold. |
| `swmax-network-latency` | Network latency | Return worst latency across the most recent N probes. |
| `swmax-cpu-bursts` | CPU bursts | Identify the peak CPU load in each fixed sample window. |
| `swmax-power-demand` | Power demand | Compute maximum demand over rolling meter intervals. |
| `swmax-heart-rate` | Heart-rate monitor | Find the highest reading in a recent beat window and preserve its sample index. |
| `swmax-wind-gusts` | Wind gusts | Report strongest gust during a rolling time-duration window. |
| `swmax-video-bitrate` | Video bitrate | Detect maximum recent bitrate over segment windows with missing-segment rules. |
| `swmax-warehouse-throughput` | Warehouse throughput | Calculate peak completed picks across rolling intervals. |
| `swmax-game-score-streak` | Game score streak | Return the highest score observed in the last K turns. |
| `swmax-web-traffic` | Web traffic | Track the maximum requests-per-second over a rolling observation window. |
| `swmax-log-severity` | Log severity | Maintain maximum severity within the latest event-count window. |
| `swmax-machine-vibration` | Machine vibration | Return maximum vibration amplitude in each sensor window. |
| `swmax-route-speed` | Route speed | Identify maximum recent vehicle speed over a distance-sample window. |
| `swmax-battery-drain` | Battery drain | Track the largest drain rate among the most recent measurements. |
| `swmax-auction-bids` | Auction bids | Report the highest bid in a bounded recent-bid window. |
| `swmax-support-load` | Support load | Calculate highest open-ticket count over a rolling daily window. |
| `swmax-production-defects` | Production defects | Find the maximum defect count in the latest N manufacturing batches. |
| `swmax-rainfall` | Rainfall intensity | Report peak rainfall intensity over a rolling time horizon. |
| `swmax-delivery-delay` | Delivery delay | Track the worst delay among the most recent delivery scans. |

## V2 remediation requirements

Every replacement needs a task-specific C++17 API, owned state or offline
index, algorithm, invalid/boundary behavior, and private discriminator. Count
and timestamp deques alone do not establish family diversity. The owner must
derive evidence from emitted docs, APIs, references, and tests; compare all
190 unordered replacement pairs; and execute renamed-domain,
constants/policy-only, opposite-end-selection, and missing-mechanism controls.

For each replacement, author a documented provenance record, coherent starter,
independent reference, visible and private deterministic tests, and per-root
remedy record/specification. The legacy tree must not be regenerated.

Hidden tests must cover:

- window sizes zero, one, equal to input length, and larger than the available
  sample count under the task contract;
- strictly increasing and strictly decreasing sequences;
- repeated equal maxima and the explicit earliest/latest tie policy;
- alternating high and low values that require deque-front expiry;
- a maximum that expires immediately before a lower value becomes visible;
- timestamp gaps and duration-boundary inclusivity where applicable;
- empty/reset/batch behavior and invalid measurement handling;
- large adversarial streams that distinguish linear monotonic-deque maintenance
  from repeated full-window rescans;
- randomized streams checked against a simple brute-force window oracle.

## Reverification command

```bash
bash examples/slime/moonlight_cpp_perf/prepare_sliding_window_maximum_aider_tasks.sh \
  --force --verify-core --verify-docker
```

The Docker verifier uses the repository-pinned C++ sanity image with network
disabled and records the result as `docker_sanity`, not `locked_oracle`.

## Local-only boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
