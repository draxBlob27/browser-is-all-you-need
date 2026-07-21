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
configuration in this repository. Base and SFT use the same 1,259 held-out
tasks, greedy decoding, a 1,536-token response cap, and the same C++ sandbox
scorer.

| Stage | Model or adapter | Evaluation data | Pass rate | Valid format | Correct and faster | Mean successful speedup |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Base | [`zai-org/GLM-4.7-Flash`](https://huggingface.co/zai-org/GLM-4.7-Flash/tree/7dd20894a642a0aa287e9827cb1a1f7f91386b67) | [`TokenBender/glm47-pie-cpp-posttraining-data`](https://huggingface.co/datasets/TokenBender/glm47-pie-cpp-posttraining-data/tree/09bc0276a0ff8ab84a8db81880ca7f739057e654) | 20.89% | 40.03% | 10.56% | 1.31x |
| SFT | [`TokenBender/glm47-flash-pie-cpp-lora-r16-sft-h100`](https://huggingface.co/TokenBender/glm47-flash-pie-cpp-lora-r16-sft-h100/tree/f1ac8df367080cc040f7cf769db219ee58f20f63) | [`TokenBender/glm47-pie-cpp-posttraining-data`](https://huggingface.co/datasets/TokenBender/glm47-pie-cpp-posttraining-data/tree/09bc0276a0ff8ab84a8db81880ca7f739057e654) | **90.79%** | **97.70%** | **28.36%** | **1.43x** |

The selected SFT profile completed four measured optimizer steps with finite
loss, a 14.88-second steady actor time, and 72,397 MiB peak memory per GPU.
The verified GRPO runtime completed rollout, reward scoring, policy update,
adapter synchronization, checkpointing, and evaluation at 6,735.5 actor
tokens/second across eight GPUs. Estimated active-MoE MFU was 2.0691%.

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

## Replication BOM

The published training and evaluation results were produced on one node with
eight H100 80 GB GPUs, full NVLink connectivity, 1 TiB of host memory, and
10 TB of local storage.

| Component | Exact experiment configuration | Measured size |
| --- | --- | ---: |
| Base model | [`zai-org/GLM-4.7-Flash`](https://huggingface.co/zai-org/GLM-4.7-Flash/tree/7dd20894a642a0aa287e9827cb1a1f7f91386b67), revision `7dd20894a642a0aa287e9827cb1a1f7f91386b67` | 62.5 GB |
| GPUs | 8x NVIDIA H100 80 GB with NVLink | 75,957 MiB peak per GPU |
| Host memory | 1 TiB installed on the experiment node | About 130 GiB run delta |
| Local storage | 10 TB installed on the experiment node | 250 GB practical clean-run footprint |
| Training image | `radixark/miles:latest-cu12@sha256:efc8027fc47aaa9687dc4f1046093ed4e2f9789e52a932fcefb7031402aeff37` plus this repository's `Dockerfile`; Modal builds it directly through `examples/modal/modal_app.py` | 53.3 GB base image |
| Training and evaluation data | [`TokenBender/glm47-pie-cpp-posttraining-data`](https://huggingface.co/datasets/TokenBender/glm47-pie-cpp-posttraining-data/tree/09bc0276a0ff8ab84a8db81880ca7f739057e654) | 60 MB download; about 107 MB extracted |
| SFT adapter | [`TokenBender/glm47-flash-pie-cpp-lora-r16-sft-h100`](https://huggingface.co/TokenBender/glm47-flash-pie-cpp-lora-r16-sft-h100/tree/f1ac8df367080cc040f7cf769db219ee58f20f63) | 772 MB |
| Converted TP4/PP1/EP8 base checkpoint | Created by `scripts/convert_checkpoint.sh` | Reserve 65 GB |
| LoRA checkpoint and run evidence | Adapter, native shards, logs, samples, and metrics | Reserve 2 GB per saved run |

Provision at least 250 GB of free local storage for a clean installation. This
covers the base model, converted checkpoint, unpacked training image, adapter,
run artifacts, and temporary image-download/build space. Use 500 GB or more
when retaining multiple checkpoints or evaluation generations.

## Assets

Download the exact base model, prepared dataset, and validated SFT adapter:

```bash
python3 scripts/download_assets.py model --output-root /root/models
python3 scripts/download_assets.py data
python3 scripts/download_assets.py sft
```

The base model is frozen to its Hugging Face commit. Dataset and adapter files
are additionally verified against the SHA-256 manifests published with their
repositories. The commands write:

```text
/root/models/GLM-4.7-Flash
.glm47-posttraining/assets/data
.glm47-posttraining/assets/adapters/sft
```

These revisions are pinned in `scripts/download_assets.py`; environment
variables can override them when intentionally testing a newer release.

## Modal 8x H100

The canonical Modal launcher is `examples/modal/modal_app.py`. It reproduces
the recorded machine and image configuration without requiring a separately
published project image:

| Modal setting | Value |
| --- | --- |
| GPU | `H100!:8` |
| CPU | 48 cores |
| Host memory | 256 GiB requested, 1 TiB limit |
| Timeout | 24 hours per stage |
| Base image | `radixark/miles:latest-cu12@sha256:efc8027fc47aaa9687dc4f1046093ed4e2f9789e52a932fcefb7031402aeff37` |
| Runtime additions | Repository `Dockerfile`, GCC/G++ 13, `rsync`, `gawk`, `util-linux`, and `git` |
| Persistent storage | `glm47-models`, `glm47-assets`, and `glm47-runs` Modal Volumes |
| Tracking secret | Modal secret `wandb-glm47` containing `WANDB_API_KEY` |

Install the Modal client, authenticate to a workspace, and create the W&B
secret once:

```bash
python3 -m pip install "modal==1.2.6"
modal secret create wandb-glm47 WANDB_API_KEY="$WANDB_API_KEY"
```

Prepare the pinned model and assets, convert the checkpoint, and run either
training stage:

```bash
modal run examples/modal/modal_app.py::prepare
modal run examples/modal/modal_app.py::convert
modal run examples/modal/modal_app.py::sft
modal run examples/modal/modal_app.py::grpo
```

GRPO defaults to the published SFT adapter. To use a newly produced SFT
checkpoint, pass its path on the `glm47-runs` volume:

```bash
modal run examples/modal/modal_app.py::grpo \
  --adapter-path /workspace/runs/<sft-run>/checkpoints/sft_lora_r16/<adapter>
```

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

Run the base-model evaluation on the complete held-out set:

```bash
PYTHONPATH=src python3 scripts/evaluate.py \
  --data-dir .glm47-posttraining/assets/data \
  --model /root/models/GLM-4.7-Flash \
  --output-dir .glm47-posttraining/eval/base \
  --label base \
  --tp-size 4 \
  --batch-size 32 \
  --temperature 0 \
  --top-p 1 \
  --max-tokens 1536 \
  --attention-backend flashinfer \
  --apply-chat-template \
  --chat-template-kwargs '{"enable_thinking": false}' \
  --score-workers 32
```

Run the same evaluation with the SFT adapter:

```bash
PYTHONPATH=src python3 scripts/evaluate.py \
  --data-dir .glm47-posttraining/assets/data \
  --model /root/models/GLM-4.7-Flash \
  --adapter .glm47-posttraining/assets/adapters/sft \
  --output-dir .glm47-posttraining/eval/sft \
  --label sft \
  --tp-size 4 \
  --batch-size 32 \
  --temperature 0 \
  --top-p 1 \
  --max-tokens 1536 \
  --attention-backend flashinfer \
  --apply-chat-template \
  --chat-template-kwargs '{"enable_thinking": false}' \
  --lora-target-modules q_a_proj,kv_a_proj_with_mqa,o_proj,gate_proj,up_proj,down_proj \
  --experts-shared-outer-loras \
  --lora-use-virtual-experts \
  --score-workers 32
```

Evaluation writes generated samples, scored records, an aggregate summary,
quality metrics, and a run receipt under the selected output directory. Add
`--wandb-project glm47-pie-cpp-posttraining --wandb-timing-status verified`
to either command to publish the same metrics and sample tables to W&B.

### Aider Polyglot C++

The Aider SFT adapter was evaluated on all 26 C++ problems with whole edit
format and two attempts. Both runs used Aider commit
`5dc9490bb35f9729ef2c95d00a19ccd30c26339c` and benchmark commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.

| Metric | Base | SFT | Change |
|---|---:|---:|---:|
| Pass@1 | 0.0% (0/26) | **3.8% (1/26)** | +3.8 pp |
| Pass@2 | 15.4% (4/26) | **19.2% (5/26)** | +3.8 pp |
| Well-formed responses | 100.0% | 100.0% | Preserved |
| Total tokens | 2,212,419 | **1,732,287** | -21.7% |

The expanded Aider SFT set uses the existing Miles input contract. Place the
data later under one root with these exact paths:

```text
<aider-data-root>/manifest.json
<aider-data-root>/sft/train.jsonl
```

`sft/train.jsonl` contains 401 unique rows with `task_id`, `label`, `messages`,
and `metadata`; its task IDs are disjoint from the 26 evaluation tasks. Launch
the existing SFT path without rebuilding data from PIE task files:

```bash
MILES_CPP_DATA_DIR=<aider-data-root> \
MILES_CPP_AUTO_PREPARE_DATA=0 \
MILES_WANDB_PROJECT=glm47-aider-v1-sft \
bash examples/sft.sh
```

Training metrics and sample tables are available in the
[W&B run](https://wandb.ai/ahm-rimer/glm47-aider-v1-sft/runs/glm47-aider-v1-sft-20260717T130336Z).
For SGLang evaluation, prepare the existing training checkpoint with
`scripts/prepare_grpo_adapter.py`; this preserves the source adapter and omits
the auxiliary next-token-prediction layer from the serving copy.

#### Aider clean-room RL lane

The Aider RL code path is implemented as a separate sibling of the PIE lane in
`src/glm47_posttraining/aider_rl/`. It does not turn the public 401-row SFT
JSONL into reward tasks. The clean-room RL dataset is not checked in yet, so no
training run is authorized until the readiness checks below pass. The
failure-derived catalog, rubric-test authoring contract, mutant admission, and
no-update canary gate are documented in
`docs/AIDER_RL_FAILURE_DERIVED_CURRICULUM.md`. A private admitted root must contain, for each
task, an immutable `task.json` and sibling `tree/` with starter files, private
visible and hidden tests, build files, `.reference/` files, provenance and
contamination evidence, measured tokenizer evidence, and a successful normal
plus ASan/UBSan oracle receipt. Families and semantic lineages may occur in
only one split.

Build the pinned grader once and record the image/compiler identities printed
by the command. Inspect the exact task schema before materializing data:

```bash
bash scripts/build_aider_grader.sh
python -m glm47_posttraining.aider_rl.dataset draft-schema > aider-task-draft.schema.json
python -m glm47_posttraining.aider_rl.dataset schema > admitted-aider-task.schema.json
```

Each source task is a `task.draft.json` plus sibling `tree/`. The draft contains
human-authored task/family/split metadata, editable and private-test paths,
trusted argv build commands, catalog rubric partitions, diagnostic mutants,
expected positive test counts, and passed provenance/contamination receipts.
Admission computes all starter, test, mutant, reference, tree, prompt,
tokenizer, split, image, compiler, oracle, and task
identities:

```bash
python -m glm47_posttraining.aider_rl.dataset admit \
  --source <draft-task-roots> \
  --out <admitted-task-roots> \
  --tokenizer <exact-sft-checkpoint-or-tokenizer> \
  --grader-lock docker/aider_cpp_grader.lock.json \
  --curriculum configs/aider_rl/failure_rubric_catalog.v1.json
```

Project those admitted roots into a self-contained bundle and re-verify all
token evidence with the exact SFT/checkpoint tokenizer before any GPU work:

```bash
python -m glm47_posttraining.aider_rl.dataset build \
  --source <admitted-task-roots> \
  --out <private-aider-rl-bundle> \
  --tokenizer <exact-sft-checkpoint-or-tokenizer>
python -m glm47_posttraining.aider_rl.dataset verify \
  --root <private-aider-rl-bundle> \
  --tokenizer <exact-sft-checkpoint-or-tokenizer>
python -m glm47_posttraining.aider_rl.dataset oracle \
  --root <private-aider-rl-bundle> \
  --tokenizer <exact-sft-checkpoint-or-tokenizer>
python -m glm47_posttraining.aider_rl.dataset summarize \
  --root <private-aider-rl-bundle> \
  --tokenizer <exact-sft-checkpoint-or-tokenizer>
python -m glm47_posttraining.aider_rl.dataset ready \
  --root <private-aider-rl-bundle> \
  --tokenizer <exact-sft-checkpoint-or-tokenizer>
```

The public rollout rows contain only the rendered prompt and safe immutable
identity metadata. Tests, references, build files, receipts, and provenance
remain under the grader-side task tree. Candidate responses must contain
exactly one complete named C++ block for every editable file in admitted order.
Grading is Docker-only, network-disabled, capability-dropped, and uses separate
fresh normal and sanitizer task/build roots. Infrastructure failures receive
two bounded retries by default; exhaustion aborts the rollout instead of
creating a policy penalty. Override only with
`GLM47_AIDER_INFRASTRUCTURE_RETRIES`.

Before an update run, analyze a capability-balanced 16-to-32-task,
eight-sample no-update rollout. Training remains blocked unless the report says
`ready`:

```bash
python -m glm47_posttraining.aider_rl.curriculum analyze-canary \
  --catalog configs/aider_rl/failure_rubric_catalog.v1.json \
  --records <no-update.records.jsonl> \
  --group-size 8
```

Launch the one-shot lane from the SFT adapter with a verified private bundle:

```bash
MILES_AIDER_DATA_DIR=<private-aider-rl-bundle> \
MILES_LORA_ADAPTER_PATH=<sft-native-adapter> \
bash examples/aider_grpo.sh
```

The launcher uses eight samples per prompt by default, derives response limits
from admitted token evidence, runs bundle and oracle preflight, selects
`glm47_posttraining.integrations.miles_aider_rl.reward_func`, and evaluates
under the `aider_cpp` name. `scripts/evaluate_aider.py` scores saved sample
JSONL or aggregates records with Aider correctness, compliance, sanitizer,
reward-variance, and infrastructure metrics. The official 26 Aider Polyglot
C++ tasks remain an external milestone holdout and must never be placed in this
bundle.

The launcher deliberately repeats bundle, tokenizer, grader-image, compiler,
reference-oracle, positive-test, and sequence-budget checks. Once the dataset
exists, the intended handoff is therefore: build the bundle once, set
`MILES_AIDER_DATA_DIR` and `MILES_LORA_ADAPTER_PATH`, then run the wrapper. Run
a no-update rollout canary and inspect reward variance before allowing policy
updates.

## Repository

```text
Dockerfile                         H100 runtime
examples/sft.sh                    canonical SFT configuration
examples/grpo.sh                   canonical GRPO configuration
examples/modal/modal_app.py        Modal 8x H100 reproduction
scripts/convert_checkpoint.sh      TP4/PP1/EP8 conversion
scripts/download_assets.py         verified Hugging Face asset download
scripts/evaluate.py                held-out generation and scoring
scripts/prepare_grpo_adapter.py    serving adapter preparation
scripts/publish_results.py         W&B results publishing
src/glm47_posttraining/            GLM-4.7 Miles integration and PIE reward
```
