# Moonlight Single-Sample SFT Handoff

## Goal

This is a subordinate plumbing handoff. The implementation contract for the
multi-task primary SFT dataset generation pipeline is
`docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`. Do not scale this hard-coded
one-row writer into a parallel pipeline or treat this smoke as the production
dataset builder.

The one-row artifact retains its historical top-level filename and unlabeled
assistant-fence representation. The primary V1.3 pipeline instead renders
exact canonical POSIX relative paths with `cpp` fences and verifies application
with the same Docker grader. Its 96-root pilot starts from 75 frozen Exercism
candidates, requires at least 21 human-approved LLM-assisted admissions, and is
semi-autonomous. Its production GLM handoff uses raw messages through the
kwargs-aware repo adapter, binds per-row token/mask evidence, and requires
consumer `verify-export`; this smoke proves none of those dataset-readiness or
consumer-admission gates.

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
`messages` content comes from `single_sample_for_sft.md`: the user turn is
compact but Aider-like, with task text plus complete pre-edit `leap.h` and
`leap.cpp` contents. Add stable metadata so the SLIME SFT loader has the
expected keys:

```json
{"label":"aider-whole-format-001","messages":[{"content":"Use Aider whole edit format. Modify the supplied editable files to solve the task. Return only complete file listings. Each fenced block must be preceded by the bare filename on the line immediately before the fence. Do not return a diff. Do not include test files, reference example files, or explanatory prose in the answer.\n\n# Introduction\n\nLeap years keep the calendar year synchronized with the astronomical year.\n\n# Instructions\n\nImplement a leap-year checker.\n\nA leap year is evenly divisible by 4, except years evenly divisible by 100 are not leap years unless they are also evenly divisible by 400.\n\n# Supplied editable files\n\nleap.h\n```cpp\n#if !defined(LEAP_H)\n#define LEAP_H\n\nnamespace leap {\n\n}  // namespace leap\n\n#endif\n```\n\nleap.cpp\n```cpp\n#include \"leap.h\"\n\nnamespace leap {\n\n}  // namespace leap\n```\n\nDo not change the names of existing functions, classes, namespaces, or files, as they may be referenced from unit tests. Only use standard libraries unless the starter task already requires a provided dependency.","role":"user"},{"content":"leap.h\n```\n#if !defined(LEAP_H)\n#define LEAP_H\n\nnamespace leap {\n\nbool is_leap_year(int year);\n\n}  // namespace leap\n\n#endif\n```\n\nleap.cpp\n```\n#include \"leap.h\"\n\nnamespace leap {\n\nbool is_leap_year(int year) {\n    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);\n}\n\n}  // namespace leap\n```","role":"assistant"}],"metadata":{"format":"aider-whole","model_family":"moonlight","purpose":"aider-like-single-sample-sft","source":"single_sample_for_sft.md","subset":"train","task_id":"aider-whole-format-001"},"task_id":"aider-whole-format-001"}
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

If you want the local Leap task folder created for response-only grading to be
the SFT source, materialize that task first and then convert it into the same
SLIME SFT directory shape:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_task.sh --force
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_sft_data.sh --force
```

That writes `.w8-biayn/data/aider-leap-sft/sft/train.jsonl`. The user turn is
the task prompt built from `.docs` plus editable starter files. The assistant
turn is built from `.meta/example.h` and `.meta/example.cpp`, but the response
filenames remain `leap.h` and `leap.cpp`.

Enter the generated container:

```bash
.w8-biayn/slime/run-container.sh
```

Inside the container, run the non-LoRA Moonlight SFT stage:

```bash
export SLIME_RUN_ID=moonlight-aider-whole-single-sft
export SLIME_CPP_DATA_DIR="$PWD/.w8-biayn/data/aider-whole-single"  # or "$PWD/.w8-biayn/data/aider-leap-sft"
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

Compile and test the saved held-out `two-fer` response with the local grader:

```bash
bash examples/slime/moonlight_cpp_perf/grade_single_sample_sft_response.sh
```

The grader parses the strict whole-file blocks, materializes `two_fer.h` and
`two_fer.cpp`, compiles them with the local C++20 test, and writes
`grade/two-fer/summary.json` plus compile and test logs beneath the probe
directory. This remains a one-sample plumbing check, not evidence for the
primary SFT dataset pipeline.

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
