---
name: aider-output-diagnoser
description: Diagnose Aider Polyglot benchmark model inputs and outputs against the actual reference solution in a local polyglot-benchmark checkout. Use when Codex must inspect a model prompt, model response, optional eval log, or failed Aider C++ task and produce a line-level report explaining where the model lacked, what underlying issue caused the failure, and what training, prompt, or exporter change would improve the behavior.
---

# Aider Output Diagnoser

## Purpose

Use this skill to turn a model input, model output, and optional failure log into an evidence-based failure report for Aider Polyglot tasks. Treat the benchmark exercise directory as the source of truth, especially:

`/data/sanil/browser-is-all-you-need-worktrees/H100/polyglot-benchmark/cpp/exercises/practice/<task>/.meta/example.*`

The root files in an exercise directory are usually starter files. Do not score against those root starter files unless `.meta/example.*` is missing and the report explicitly calls out the fallback.

## Workflow

1. Identify the exercise.
   - Prefer an explicit exercise directory, for example `cpp/exercises/practice/all-your-base`.
   - Otherwise infer the task slug from the prompt, response, log path, or filenames.
   - Convert between hyphen and underscore forms when matching task slugs and filenames.

2. Locate the reference solution.
   - Prefer `.meta/example.cpp`, `.meta/example.h`, and other source-like `.meta/example.*` files in the exercise directory.
   - Include headers as first-class references. Many C++ failures are signature, namespace, include, or declaration errors visible only in the header.
   - If no `.meta/example.*` exists, stop and report that the source-of-truth solution is missing rather than guessing silently.

3. Extract the model's candidate files.
   - Parse Aider-style file listings with a filename line followed by a fenced code block.
   - Map model filenames such as `all_your_base.cpp` and `all_your_base.h` to `.meta/example.cpp` and `.meta/example.h` by extension and task stem.
   - Flag malformed responses that contain prose, tests, patches, or no parseable file blocks.

4. Compare with line-level evidence.
   - Show reference line numbers and model line numbers for changed or missing regions.
   - Separate hard evidence from inference. A line diff proves mismatch; the root cause category is an inference unless supported by compiler/test log lines.
   - Use the optional eval log to quote short failure evidence with line numbers: compile errors, failed assertions, timeouts, malformed output, context exhaustion, or no visible change.

5. Explain what the model lacked.
   - Identify concrete issues such as wrong signature, missing namespace, missing include, exception policy mismatch, edge-case handling gap, overflow/ownership/state semantics, incomplete implementation, wrong output format, malformed Aider file listing, no-op/starter-copy response, or context exhaustion.
   - Tie each issue to a reference line, model line, and log line when available.

6. Recommend improvements.
   - For prompt/exporter issues, recommend changes to the training prompt format, file-listing contract, retry prompts, truncation policy, or reference-file selection.
   - For model behavior issues, recommend targeted SFT rows, repair examples, failure-conditioned retries, or contrastive examples that teach the missing API/edge case.
   - Avoid generic advice. Every recommendation should be connected to an observed failure.

7. Create or update a persistent learning document.
   - For every diagnosed failed task, maintain a task-specific "learnables" markdown file under `docs/aider-learnings/<task>.md` unless the user gives another path.
   - The learning document is not a short report. It is the durable dataset-preparation note that explains how this exact task should influence future SFT data.
   - Include these sections:
     - Task identity, source-of-truth files, and evaluated model response/log pointers.
     - Benchmark contract: exact public API, namespace, file set, exception policy, edge cases, and output-format constraints.
     - Failure anatomy: what the model did, where it diverged, why that caused compile/test/format failure, and which evidence proves each point.
     - Generalizable learnables: reusable rules the model should learn beyond this one prompt.
     - SFT dataset creation plan: row archetypes, prompt shape, target answer shape, negative/contrastive examples, repair turns, validation gates, and sampling/weighting suggestions.
     - Acceptance checks for including rows in training: parser validity, compile/test receipts, hidden-edge coverage, contamination checks, and exact whole-file output formatting.
   - Keep the document answer-blind with respect to official benchmark tests/prompts when creating synthetic training data: use the reference only to diagnose the failure and derive abstract requirements, not to copy protected benchmark fixtures into training rows.
   - If a learning document already exists, append a new dated failure note and reconcile the SFT recommendations instead of creating a duplicate.

## Helper Script

Use `scripts/aider_output_diagnose.py` for repeatable reports:

```bash
python3 skills/aider-output-diagnoser/scripts/aider_output_diagnose.py \
  --exercise-dir /data/sanil/browser-is-all-you-need-worktrees/H100/polyglot-benchmark/cpp/exercises/practice/all-your-base \
  --model-input /path/to/model_prompt.txt \
  --model-output /path/to/model_response.txt \
  --log /path/to/benchmark.log \
  --out /path/to/report.md
```

If only a task slug is known:

```bash
python3 skills/aider-output-diagnoser/scripts/aider_output_diagnose.py \
  --task all-your-base \
  --model-input prompt.txt \
  --model-output response.txt \
  --benchmark-root /data/sanil/browser-is-all-you-need-worktrees/H100/polyglot-benchmark \
  --out report.md
```

The generated report should be reviewed and tightened by Codex before sending if the task is high value. The script gives a disciplined first pass; Codex should add any domain-specific reasoning visible in the tests, prompt, or log.
