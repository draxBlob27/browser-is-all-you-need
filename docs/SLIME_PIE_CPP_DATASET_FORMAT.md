# SLIME PIE C++ Dataset Format

This document defines the required Hugging Face JSONL format for PIE-style C++
optimization tasks sent to an oracle writer and returned as verified SFT chat
data. The required shape is the same as:

https://huggingface.co/datasets/TokenBender/dummy-pie-cpp-oracle-seed

That dataset is a synthetic format skeleton, not a benchmark. Real PIE C++
rows should preserve this interface while using real admitted PIE task content.

## Dataset Files

A compatible dataset has this layout:

```text
README.md
ORACLE_WRITER_INSTRUCTIONS.md
data/oracle_seed.jsonl
data/oracle_return_example.jsonl
schema/oracle_seed.schema.json
schema/oracle_return.schema.json
```

`data/oracle_seed.jsonl` is the prompt-only handoff to an oracle writer.
`data/oracle_return_example.jsonl` shows the solved SFT chat-row shape. The
schema files are the validation contract for both stages.

## Oracle Seed Rows

Each line in `data/oracle_seed.jsonl` is one strict JSON object with no extra
top-level fields. Required fields:

| Field | Required shape |
| --- | --- |
| `task_id` | Stable string identifier for the row. |
| `source` | Source name string, for real data usually PIE-derived. |
| `split` | Constant string `oracle_seed`. |
| `language` | Constant string `cpp20`. |
| `prompt_template_id` | String identifying the prompt style. |
| `messages` | Canonical chat input array. Items have `role` and `content`; `role` is `system` or `user`. |
| `prompt` | Flattened fallback string for tooling that cannot consume chat messages. |
| `source_code` | Correct but slower C++20 program to optimize. |
| `visible_tests` | Non-empty array of public tests. Each item has `name`, `stdin`, and `stdout`. |
| `public_checker` | Object with `type: "exact_stdout"` and `strip_trailing_whitespace`. |
| `compile` | Object with `command` and `timeout_sec`. |
| `run` | Object with `timeout_sec` and `memory_mb`. |
| `constraints` | Object describing output and correctness requirements. |
| `metadata` | Object for task notes, problem ids, expected complexity, and policy metadata. |

`messages` is the source of truth. `prompt` exists only for non-chat loaders and
must not diverge semantically from `messages`.

`visible_tests` are the only tests included in the seed row and prompt. Hidden
tests, generated tests, and PIE `v1` oracle code are not included in
`oracle_seed` rows.

The required `constraints` object has:

```json
{
  "assistant_format": "one_reasoning_block_then_one_cpp_fence",
  "must_preserve_io": true,
  "must_compile": true,
  "must_pass_visible_tests": true,
  "target": "optimize runtime without changing outputs"
}
```

## Oracle Return Rows

Each line returned by the oracle writer is one strict JSON object with:

| Field | Required shape |
| --- | --- |
| `task_id` | Same id as the seed row. |
| `messages` | The original input `messages`, unchanged, plus one appended `assistant` message. |
| `verification` | Object containing the oracle writer's verification claims. |

The appended assistant message must contain exactly:

````text
<reasoning>Short optimization rationale.</reasoning>
```cpp
// complete optimized C++20 program
```
````

There must be no extra prose before, between, or after those two parts.

The required `verification` object has:

```json
{
  "compile_ok": true,
  "all_visible_tests_pass": true,
  "all_hidden_tests_pass": null,
  "score": 1.0,
  "runtime_ms": null,
  "notes": "Verified locally by oracle writer."
}
```

`all_hidden_tests_pass` and `runtime_ms` may be `null` when the oracle writer
does not have hidden tests or runtime measurement. Treat `verification` as a
claim, not as final proof.

## Training Admission

Returned rows are not SFT data until the repo verifier confirms:

- response format is valid;
- generated C++ compiles with the configured command;
- visible tests pass;
- hidden or generated tests pass when available;
- the row receives full credit.

Rows with invalid format, compile failures, failed tests, partial credit, or
unverified behavior must be excluded from SFT.

## Relationship To The Active SLIME Lane

The oracle-seed format above is the required external contract for creating
verified optimized solutions. The active repo-owned SLIME lane then converts
admitted task data into runtime artifacts.

The lane wrappers:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_data.sh
bash examples/slime/moonlight_lora_cpp_perf/prepare_data.sh
bash examples/slime/glm47_cpp_perf/prepare_data.sh
```

write a local bundle under the lane run directory with:

- `sft/train.jsonl`: supervised chat rows with `messages`, `label`, `task_id`,
  `problem_id`, `split`, and `metadata`;
- `grpo/train.jsonl`: prompt-only RL rows with `prompt`, `label`, `task_id`,
  `problem_id`, `split`, and `metadata`;
- `eval/validation.jsonl`: prompt-only eval rows with the same GRPO row shape;
- `tasks/`: copied task JSON files used by the reward hook;
- `manifest.json`: counts, source paths, profile, run id, and file map.

Those generated SLIME files are downstream artifacts. They should not be used
to redefine the oracle-seed dataset interface.

For GRPO and eval, model prompts may include the slower PIE `v0` and visible
tests only. Hidden tests and PIE `v1` remain behind the reward hook through
`metadata.task_path`.
