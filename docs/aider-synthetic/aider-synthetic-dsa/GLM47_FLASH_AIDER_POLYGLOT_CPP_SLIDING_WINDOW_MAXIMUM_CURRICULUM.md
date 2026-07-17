# Sliding-Window Maximum Curriculum: Topic 1, Sliding-Window Maximum

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches monotonic-deque maintenance over a bounded moving
window: expire out-of-window entries, preserve decreasing candidate values,
handle equal-value tie policy, and report the correct current maximum.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Sliding-window-maximum examples are readily available online in algorithm
resources and online judges. They are useful for private concept study or
source discovery only. They are not a drop-in SFT source inventory: every
external source needs explicit license and semantic-contamination review.

The tasks below materialize as newly authored C++17 roots. Their interfaces,
tests, reference implementations, and provenance must be created in-repo and
pass the normal original-task admission process.

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

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose only a
generic `max_sliding_window(values, k)` assignment. The input model
(event-count versus timestamp duration), tie policy, invalid/missing-value
policy, threshold behavior, index reporting, and batch/stream semantics must
materially differ between roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

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

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
