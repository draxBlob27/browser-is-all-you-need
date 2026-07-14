# Moonlight Single-Sample SFT Handoff

## Goal

Implement a local supervised fine-tuning smoke that trains
`moonshotai/Moonlight-16B-A3B-Instruct` on the single Aider `whole` edit-format
sample documented in `single_sample_for_sft.md`.

This is a format-discipline experiment. It is not PIE performance training, not
GRPO, not the Modal/Aider benchmark, and not LoRA.

## Hard Requirements

- Use the existing full Moonlight SLIME lane:
  `examples/slime/moonlight_cpp_perf/sft.sh`.
- Do not use `examples/slime/moonlight_lora_cpp_perf/`.
- Do not set `SLIME_LORA_ENABLED`, `SLIME_LORA_RANK`, or
  `SLIME_LORA_EXTRA_ARGS`.
- Do not use GLM paths; GLM does not fit the target machine.
- Do not run `prepare_data.sh` for this experiment, because it rebuilds PIE data
  and will overwrite the custom sample data path.
- Keep all generated data, checkpoints, logs, and exports under `.w8-biayn/`.
- Do not edit SLIME upstream directly.

## Existing Wiring To Reuse

The Moonlight lane already supports SFT over chat-message JSONL:

```text
examples/slime/moonlight_cpp_perf/moonlight_cpp_perf.sh
```

For the `sft` stage it passes:

```text
--prompt-data "${DATA_DIR}/sft/train.jsonl"
--input-key messages
--metadata-key metadata
--loss-type sft_loss
--debug-train-only
```

Therefore the implementation only needs to materialize a tiny custom
`DATA_DIR` with a valid `sft/train.jsonl` and `manifest.json`, then run the
normal Moonlight SFT wrapper with `SLIME_CPP_DATA_DIR` pointed at that custom
directory.

The repo-owned writer is:

```bash
uv run python -m w8_biayn.integrations.moonlight_single_sample_sft \
  --out .w8-biayn/data/aider-whole-single
```

The equivalent lane-local wrapper is:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_single_sample_sft_data.sh
```

## Data To Materialize

Create:

```text
.w8-biayn/data/aider-whole-single/
  manifest.json
  sft/
    train.jsonl
```

`sft/train.jsonl` must contain exactly one JSON object on one line. The
`messages` content should come from `single_sample_for_sft.md`; add stable
metadata so the SLIME SFT loader has the expected keys:

```json
{"messages":[{"role":"user","content":"Use whole edit format. Modify the supplied files `leap.cpp` and `leap.h` to implement a leap-year checker. Return only complete file listings. Each fenced block must be preceded by its filename."},{"role":"assistant","content":"leap.h\n```\n#if !defined(LEAP_H)\n#define LEAP_H\n\nnamespace leap {\n\nbool is_leap_year(int year);\n\n}  // namespace leap\n\n#endif\n```\n\nleap.cpp\n```\n#include \"leap.h\"\n\nnamespace leap {\n\nbool is_leap_year(int year) {\n    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);\n}\n\n}  // namespace leap\n```"}],"label":"aider-whole-format-001","task_id":"aider-whole-format-001","metadata":{"task_id":"aider-whole-format-001","source":"single_sample_for_sft.md","subset":"train","format":"aider-whole","model_family":"moonlight","purpose":"single-sample-sft-smoke"}}
```

`manifest.json` can be minimal, but it should make the custom dataset explicit:

```json
{
  "kind": "single-sample-aider-whole-sft",
  "schema_version": 1,
  "source": "single_sample_for_sft.md",
  "model_family": "moonlight",
  "train_count": 1,
  "files": {
    "sft_train": "sft/train.jsonl"
  }
}
```

If the implementation creates a script or CLI helper to write these files, keep
it deterministic and idempotent. Do not parse the markdown with brittle string
slicing if the sample can be represented as a small checked-in fixture or a
structured Python constant.

## Runtime Commands

From the host, prepare the SLIME runtime once:

```bash
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime setup
```

Materialize the custom one-row SFT data from the host. Do this instead of
running `examples/slime/moonlight_cpp_perf/prepare_data.sh`:

```bash
uv run python -m w8_biayn.integrations.moonlight_single_sample_sft \
  --out .w8-biayn/data/aider-whole-single
```

If running from a plain shell without `uv`, the lane wrapper writes the same
files and also respects `SLIME_CPP_DATA_DIR`:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_single_sample_sft_data.sh
```

Enter the generated container:

```bash
.w8-biayn/slime/run-container.sh
```

Inside the container, run the non-LoRA Moonlight SFT stage:

```bash
export SLIME_RUN_ID=moonlight-aider-whole-single-sft
export SLIME_CPP_DATA_DIR="$PWD/.w8-biayn/data/aider-whole-single"
export SLIME_CPP_AUTO_PREPARE_DATA=0

export SLIME_SFT_ROLLOUT_BATCH_SIZE=2
export SLIME_SFT_GLOBAL_BATCH_SIZE=2
export SLIME_SFT_NUM_ROLLOUT=1
export SLIME_SFT_NUM_EPOCH=1
export SLIME_SAVE_INTERVAL=1

bash examples/slime/moonlight_cpp_perf/sft.sh
```

The lane defaults to:

```text
SLIME_HF_MODEL_ID=moonshotai/Moonlight-16B-A3B-Instruct
SLIME_HF_CHECKPOINT=/root/models/Moonlight-16B-A3B-Instruct
SLIME_NUM_GPUS=4
SLIME_TENSOR_MODEL_PARALLEL_SIZE=2
SLIME_EXPERT_MODEL_PARALLEL_SIZE=4
SLIME_SEQ_LENGTH=1024
```

Only change the GPU parallelism knobs if the target hardware and Megatron
layout are understood. This document does not claim the full Moonlight lane
fits on a single GPU.

## Expected Outputs

The run should create local receipts and checkpoints under:

```text
.w8-biayn/slime/moonlight-cpp-perf/runs/moonlight-aider-whole-single-sft/
```

Important files:

```text
stages/sft/run.log
stages/sft/run_receipt.txt
stages/sft/vram_peak.txt
checkpoints/sft/latest_checkpointed_iteration.txt
hf/sft/rollout_0/
```

`run_receipt.txt` should show `status=0`. If HuggingFace export is enabled,
`hf/sft/rollout_0/` should contain `config.json` and model weight files.

## Validation Scope

Do not use `examples/slime/moonlight_cpp_perf/eval_sft.sh` as the main proof
for this experiment. That evaluator expects PIE C++ optimization prompts and
the repo C++ performance reward, while this sample trains Aider `whole` edit
format.

The useful validation is a format probe against the exported SFT checkpoint:

1. Load the exported Moonlight SFT checkpoint with the same inference stack used
   for local Moonlight generation.
2. Send an Aider-style prompt that requests `whole` edit format.
3. Verify the response contains no explanatory prose.
4. Verify each fenced file body is immediately preceded by the filename.
5. Verify the file body is a complete file listing, not a patch fragment.

Use a held-out prompt for the probe; do not only ask the exact `leap.cpp` /
`leap.h` training prompt.


### Saving A Model Response

The SFT training command does not generate a fresh answer. After SFT finishes
and `hf/sft/rollout_0/` exists, start an OpenAI-compatible SGLang server for
that exported checkpoint:

```bash
export SLIME_RUN_ID=moonlight-aider-whole-single-sft-b2-r1
export SFT_EXPORT="$PWD/.w8-biayn/slime/moonlight-cpp-perf/runs/${SLIME_RUN_ID}/hf/sft/rollout_0"

python -m sglang.launch_server \
  --model-path "$SFT_EXPORT" \
  --tp-size "${SLIME_NUM_GPUS:-4}" \
  --mem-fraction-static 0.45 \
  --served-model-name moonlight-single-sft \
  --host 127.0.0.1 \
  --port 30000
```

In a second shell inside the same SLIME container, send the held-out Aider
`whole` prompt and save the response:

```bash
cd /workspace/browser-is-all-you-need
export SLIME_RUN_ID=moonlight-aider-whole-single-sft-b2-r1

bash examples/slime/moonlight_cpp_perf/probe_single_sample_sft_response.sh \
  --base-url http://127.0.0.1:30000 \
  --model auto
```

The probe writes:

```text
.w8-biayn/slime/moonlight-cpp-perf/runs/${SLIME_RUN_ID}/probes/aider-whole-heldout-two-fer/prompt.json
.w8-biayn/slime/moonlight-cpp-perf/runs/${SLIME_RUN_ID}/probes/aider-whole-heldout-two-fer/response.json
.w8-biayn/slime/moonlight-cpp-perf/runs/${SLIME_RUN_ID}/probes/aider-whole-heldout-two-fer/response.txt
.w8-biayn/slime/moonlight-cpp-perf/runs/${SLIME_RUN_ID}/probes/aider-whole-heldout-two-fer/summary.json
```

Open `response.txt` to inspect the generated answer. `summary.json` records
basic whole-format diagnostics, including fence count and whether each opening
fence had a filename immediately before it.

## Failure Modes To Check

- The SFT stage rebuilt PIE data: `SLIME_CPP_AUTO_PREPARE_DATA` was not `0`, or
  `SLIME_CPP_DATA_DIR` was wrong.
- The LoRA wrapper ran accidentally: the command path contains
  `moonlight_lora_cpp_perf` or LoRA environment variables are set.
- The dataset is JSON, not JSONL: `sft/train.jsonl` must have one complete JSON
  object per line.
- The JSONL row lacks `messages`: Moonlight SFT uses `--input-key messages`.
- Existing custom data differs from the checked-in sample: rerun the writer
  with `--force` only if you intentionally want to restore the canonical row.
- The model still emits prose before code fences: the sample did not teach the
  intended Aider `whole` output discipline, or one sample is insufficient.

## Reporting

Report this as a single-sample format SFT smoke only. Do not report it as a PIE
uplift result, Aider benchmark score, pass@k result, or general model
improvement.
