# GLM-4.7-Flash Post-Training on 8x H100

A focused Miles pipeline for supervised fine-tuning and GRPO on the PIE C++
performance task.

The repository provides one configuration:

| Component | Configuration |
| --- | --- |
| Model | GLM-4.7-Flash |
| Hardware | 8x NVIDIA H100 80 GB with NVLink |
| Training | Miles, Megatron-Core, LoRA rank 16 |
| Parallelism | TP4 / PP1 / EP8 / ETP1 |
| Sequence length | 4,096 |
| Packed tokens per GPU | 16,384 |
| MoE dispatch | DeepEP flex |
| Rollout serving | SGLang DP8 with FlashInfer |
| Tracking | W&B scalars, samples, evaluation tables, and checkpoint manifests |

## Results

Measurements were collected on a dedicated 8x H100 80 GB node with the
configuration in this repository.

| Method | Result |
| --- | --- |
| SFT full evaluation | 90.79% pass rate across 1,259 held-out tasks |
| SFT valid format rate | 97.70% |
| SFT correct and faster rate | 28.36% |
| SFT mean speedup when correct and faster | 1.43x |
| SFT | Four measured optimizer steps completed with finite loss |
| SFT steady actor time | 14.88 seconds per step |
| SFT peak memory | 72,397 MiB per GPU |
| GRPO | Complete rollout, reward, policy update, adapter sync, checkpoint, and evaluation cycle |
| Actor throughput | 6,735.5 tokens/second across 8 GPUs |
| Estimated active-MoE MFU | 2.0691% |

The W&B integration records training curves, rollout samples, evaluation
samples, reward outcomes, metric catalogs, per-rank adapter synchronization
fingerprints, and checkpoint manifests.

## Requirements

- One 8x H100 80 GB NVLink node
- Docker with NVIDIA Container Toolkit
- Access to the GLM-4.7-Flash base model
- A W&B API key for online experiment tracking

The Miles base image supplies Miles, Megatron-Core, SGLang, Ray, and the
GLM-4.7 model definition.

## Assets

Download the exact prepared dataset and the validated SFT and GRPO adapters:

```bash
python3 scripts/download_assets.py all
```

The downloader verifies every file against the SHA-256 manifest published with
each Hugging Face repository. It writes:

```text
.glm47-posttraining/assets/data
.glm47-posttraining/assets/adapters/sft
.glm47-posttraining/assets/adapters/grpo
```

Base model:
[`zai-org/GLM-4.7-Flash`](https://huggingface.co/zai-org/GLM-4.7-Flash)

Dataset:
[`TokenBender/glm47-pie-cpp-posttraining-data`](https://huggingface.co/datasets/TokenBender/glm47-pie-cpp-posttraining-data/tree/5bb3330550cbf96d09f71e47453703d2a36a34c7)

Adapters:
[`SFT`](https://huggingface.co/TokenBender/glm47-flash-pie-cpp-lora-r16-sft-h100/tree/f1ac8df367080cc040f7cf769db219ee58f20f63)
and
[`GRPO`](https://huggingface.co/TokenBender/glm47-flash-pie-cpp-lora-r16-grpo-h100/tree/1fbac6f6fd59829a64776937102351c6318a7fd4)

These revisions are pinned in `scripts/download_assets.py`; environment
variables can override them when intentionally testing a newer release.

## Runtime

Build the aligned H100 image:

```bash
docker build -t glm47-h100-posttraining .
```

Start the container with the repository and model directory mounted:

```bash
docker run --rm -it \
  --gpus all \
  --ipc host \
  --network host \
  -v "$PWD:/workspace/glm47-h100-posttraining" \
  -v /root/models:/root/models \
  -v "$PWD/.glm47-posttraining/assets:/workspace/assets:ro" \
  glm47-h100-posttraining \
  bash
```

Inside the container:

```bash
cd /workspace/glm47-h100-posttraining
python3 -m pip install -e .
export MILES_CPP_DATA_DIR=/workspace/assets/data
export WANDB_API_KEY=...
```

## Convert

Create the TP4/PP1/EP8 Megatron checkpoint:

```bash
bash scripts/convert_checkpoint.sh
```

The default output is:

```text
/root/models/GLM-4.7-Flash_torch_dist_tp4_pp1_ep8
```

## SFT

```bash
bash examples/sft.sh
```

Runs are written under:

```text
.glm47-posttraining/miles/glm47-h100-cpp-perf/runs/
```

Each run contains the prepared dataset, training log, VRAM trace, receipt,
LoRA checkpoints, and W&B artifact manifest.

## GRPO

Start GRPO from an SFT adapter:

```bash
export MILES_LORA_ADAPTER_PATH=/workspace/assets/adapters/sft
bash examples/grpo.sh
```

The launcher prepares a serving-compatible adapter, starts SGLang across all
eight H100s, performs C++ reward scoring, updates the LoRA policy, synchronizes
the adapter, evaluates the checkpoint, and publishes the run results.

The default GRPO schedule uses 32 prompts, 8 samples per prompt, 100 rollouts,
evaluation every 20 rollouts, and checkpointing every 10 rollouts.

## Evaluate

Prepare a serving copy of any trainer adapter:

```bash
python3 scripts/prepare_grpo_adapter.py \
  /path/to/trainer/adapter \
  /path/to/serving/adapter
```

Run held-out evaluation:

```bash
PYTHONPATH=src python3 scripts/evaluate.py \
  --data-dir /path/to/run/data \
  --model /root/models/GLM-4.7-Flash \
  --adapter /path/to/serving/adapter \
  --output-dir /path/to/eval \
  --label grpo \
  --tp-size 4 \
  --batch-size 32 \
  --attention-backend flashinfer \
  --experts-shared-outer-loras \
  --lora-use-virtual-experts \
  --wandb-project glm47-pie-cpp-posttraining \
  --wandb-timing-status verified
```

Evaluation writes generated samples, scored records, an aggregate summary,
quality metrics, and the corresponding W&B tables.

## Repository

```text
Dockerfile                         H100 runtime
examples/sft.sh                    canonical SFT configuration
examples/grpo.sh                   canonical GRPO configuration
scripts/convert_checkpoint.sh      TP4/PP1/EP8 conversion
scripts/download_assets.py         verified Hugging Face asset download
scripts/evaluate.py                held-out generation and scoring
scripts/prepare_grpo_adapter.py    serving adapter preparation
scripts/publish_results.py         W&B results publishing
src/glm47_posttraining/            GLM-4.7 Miles integration and PIE reward
```
