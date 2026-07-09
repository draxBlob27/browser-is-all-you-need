# Modal 8x H100 Lane (GLM-4.7-Flash Miles)

Status (2026-07-10): conversion, fit probe, full SFT, base eval, and SFT eval
have completed on Modal. Production GRPO is intentionally blocked on CPU
runtime timing integrity in [issue #13](https://github.com/tokenbender/browser-is-all-you-need/issues/13).
This is an active runner, not a planning stub.

## Verified state

The lane uses `examples/modal/modal_app.py` to run one stage at a time in a
single Modal 8x H100 container. Modal Volumes preserve inputs and evidence:

- `glm47-models`: 59 GiB Hugging Face checkpoint;
- `glm47-models2`: VolumeFS v2 exact-layout Megatron checkpoint;
- `glm47-data`: PIE tasks, prepared Miles data, and warm-start adapters;
- `glm47-runs`: logs, receipts, eval outputs, checkpoints, and W&B working data.

The converted checkpoint is TP4 / PP1 / EP8 / ETP1. A checkpoint is admissible
only when its tracker resolves to a finalized directory containing `.metadata`.
The runner enforces this before Ray starts. The old VolumeFS v1 conversion is
not a fallback because it previously exposed inconsistent checkpoint views.

Verified receipts on `glm47-runs`:

| Stage | Run | Evidence |
| --- | --- | --- |
| Fit probe | `glm47_h100_probe_20260709T071239Z` | Completed end to end in 770.7 s; DeepEP flex active; peak VRAM 25,737 MiB; adapter checkpoint saved. |
| Full SFT | `glm47_h100_sft_20260709T074419Z` | Completed 245 steps in 11,005.2 s; final adapter at iteration 244. |
| Base eval | `glm47_h100_eval_20260709T112536Z` | Full 1,259-task generation and scoring artifacts preserved. |
| SFT eval | `glm47_h100_eval_20260709T114311Z` | Full 1,259-task generation and scoring artifacts preserved. |

The stage durations above are receipt wall times. They do not establish that
the current profile is the fastest possible profile, and they do not make the
per-program speed measurements trustworthy.

## Current eval result

The H100-native SFT checkpoint has a clear correctness and format uplift over
the H100-native base checkpoint on the same full validation set:

| Checkpoint | Pass rate | Invalid format | Truncated | Mean reward |
| --- | ---: | ---: | ---: | ---: |
| Base | 0.192216 | 0.625099 | 0.676728 | See preserved summary |
| SFT | 0.907863 | 0.023034 | 0.023034 | 0.897978 |

Do not publish the current `correct_and_faster` rates or runtime speedups as
clean results. Base has 32 missing runtime/reference measurements and a 2 ns
outlier; SFT has 192 missing runtime/reference measurements. Issue #13 owns the
timer fix and CPU-only re-score of the preserved generations. No GPU generation
is needed for that repair.

## Serving fixes

The standalone eval path is deliberately pinned to the working image behavior:

- The image's SGLang and `sglang-kernel` pair is kept intact, with SGLang's
  supported kernel-version assertion bypass. Installing the available newer
  kernel wheel pulls a CUDA 13 build that does not load in this CUDA 12.9 image.
- Eval uses TP4 because GLM-4.7-Flash has 20 attention heads and MLA rejects TP8.
  Training still uses all eight GPUs through expert parallelism and SGLang DP
  attention.
- Trainer adapters contain MTP layer tensors that disk serving cannot consume;
  `scripts/strip_mtp_adapter.py` creates a serve-only copy before eval.
- Eval uses FlashInfer because this image's automatic FA3 path calls an
  unsupported `only_qv` interface in its installed FlashAttention build.
- EAGLE speculative decoding remains off by default. It is an experiment to
  validate with LoRA serving, not part of the proven fast profile.

## Canonical W&B surface

The no-GPU backfill is publicly visible in the
[canonical experiment group](https://wandb.ai/ahm-rimer/glm47-pie-cpp-posttraining/groups/glm47-h100-proof-20260709/workspace).
Verified runs are
[base eval](https://wandb.ai/ahm-rimer/glm47-pie-cpp-posttraining/runs/glm47-h100-proof-20260709-base-eval),
[SFT eval](https://wandb.ai/ahm-rimer/glm47-pie-cpp-posttraining/runs/glm47-h100-proof-20260709-sft-eval),
[checkpoint comparison](https://wandb.ai/ahm-rimer/glm47-pie-cpp-posttraining/runs/glm47-h100-proof-20260709-checkpoint-comparison),
and [pipeline evidence](https://wandb.ai/ahm-rimer/glm47-pie-cpp-posttraining/runs/glm47-h100-proof-20260709-proof-pipeline).
Both eval runs contain 1,259-row sample tables and source artifacts; the
comparison intentionally reports `grpo` as the only missing required label.
All four run records were verified through the unauthenticated W&B API.

Set one stable experiment id for every stage. Each stage keeps its own run id
and explicit W&B `job_type`, while all runs share the experiment group:

```bash
EXPERIMENT_ID="glm47-h100-$(date -u +%Y%m%d)"

modal run examples/modal/modal_app.py::convert --experiment-id "${EXPERIMENT_ID}"
modal run examples/modal/modal_app.py::probe --experiment-id "${EXPERIMENT_ID}"
modal run examples/modal/modal_app.py::sft --experiment-id "${EXPERIMENT_ID}"
modal run examples/modal/modal_app.py::evaluate --experiment-id "${EXPERIMENT_ID}"
modal run examples/modal/modal_app.py::grpo --experiment-id "${EXPERIMENT_ID}"
```

The Modal runner checks W&B authentication before stage work. It appends
resumable `started`, `completed`, or `failed` events to one pipeline run and
records wall time, repo SHA, image, error, and receipt. Miles SFT/GRPO runs are
resumed after exit to add curated stage summaries and a vetted artifact
manifest without replacing their native training metric history.

Eval runs publish:

- `tables/eval_samples`: per-sample correctness, failure reason, runtime,
  token, truncation, finish reason, and response preview;
- `tables/failure_buckets`: failure counts and rates by label and split;
- `tables/checkpoint_comparison`: base/SFT/GRPO aggregate comparison;
- summaries for standard PIE eval metrics, stage status, lineage, and timing
  trust state;
- generated JSONL, records, summaries, receipts, VRAM traces, and SHA-256
  manifests as W&B artifacts.

Only allowlisted text formats are uploaded. Secret-shaped filenames, files
containing credential assignments, symlinks, model weights, and files larger
than 128 MiB are rejected. W&B remains lazily imported, so local tests do not
need credentials.

## Run order

The remaining production order is strict:

1. Fix issue #13 and CPU re-score the preserved base/SFT generations.
2. Verify zero unexplained missing runtimes and audit the speedup distribution.
3. Probe H100 headroom, including `MILES_RECOMPUTE_GRANULARITY=none` and larger
   packing/batches, before making a fastest-profile claim.
4. Run the no-training exploration-temperature gate on the H100 SFT adapter.
5. Launch GRPO from that adapter with the optimizer warm-start fix, KL-disabled
   no-ref configuration, and explicit greedy eval.
6. Preserve the GRPO checkpoint and complete the held-out comparison.

The runtime preflight must pass before reward-bearing stages. Modal gVisor has
no Docker daemon, so the lane uses `W8_CPP_SANDBOX_BACKEND=local` with the same
compiler and CPU-time contract for candidate and oracle.

## Relationship to `slime-sss`

The `origin/slime-sss` SkyPilot/GCP provisioning code stays on its branch. This
lane reimplements its useful operational discipline on Modal: fail-fast W&B,
stage receipts, VRAM evidence, explicit milestones, and staged stop conditions.
The canonical training implementation is this branch because it also carries
the validated GLM bridge, exact EP8 conversion, DeepEP fit probe, completed SFT,
serving fixes, eval artifacts, and timing-integrity gate.

## Non-goals

- No SkyPilot or GCP provisioning in the Modal app.
- No change to the reward ladder, prompt/template contract, or held-out split.
- No production GRPO while issue #13 is open.
- No claim that the current H100 profile is fastest until the headroom probes
  are measured.
