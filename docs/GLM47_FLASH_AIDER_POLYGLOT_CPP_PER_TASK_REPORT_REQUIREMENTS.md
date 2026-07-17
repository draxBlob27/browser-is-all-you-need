# GLM-4.7-Flash Aider Polyglot C++ Per-Task Report Requirements

Status: requirements only. This document defines the report that must be
produced later. It intentionally contains no per-task answers, copied model
responses, correctness judgments, error diagnoses, or task-specific SFT
recommendations.

The finished report is a capability narrative, not a flat collection of task
notes. It must first establish the benchmark and its grading method, then show
what one-shot attempts reveal, what same-trajectory test feedback changes,
what those observations imply for SFT data, and finally how eight independent
attempts change the result. Per-task analysis is the evidence within that
narrative.

## Purpose

Produce a copy-paste-ready Markdown report with the following required flow.
The headings may be refined for readability, but their order and substance are
mandatory.

1. **Benchmark, task format, and passing methodology.** Explain the official
   Aider Polyglot C++ benchmark used here, the model-visible starter/edit
   format, the independent trajectory and sequential-try definitions, and
   exactly how Aider's authoritative tests determine a pass. State that this
   is a base-evaluation diagnostic, not PIE training evidence or an official
   leaderboard claim.
2. **Pass@1, single try.** Analyze one-shot performance first. For every task,
   show where the selected `sample-01` try-1 attempt failed (or passed), the
   observed error, the causal diagnosis, and a concise task-level takeaway.
   Follow the task analysis with a section summary, findings, and the
   one-shot visualizations.
3. **Pass@1 with same-trajectory test feedback.** Explain that Aider supplies
   the try-1 test error only to the same trajectory before try 2; it is not an
   independent sample. For every task with a try-2 attempt, explain what the
   model changed, whether it repaired the reported defect, and what that
   recovery or persistence indicates about model capability.
4. **SFT implications from the pass@1 evidence.** Deduplicate the recurring
   one-shot and feedback-resistant failure modes into a proposed SFT
   curriculum. Explain the likely reason for each gap and how a
   contamination-safe, non-benchmark SFT example would teach the missing
   capability.
5. **Pass@8, single try.** Move from the selected one-shot projection to all
   eight independent first tries per task. Report observations and explain how
   this changes the picture relative to pass@1 single try and pass@1 with
   feedback; do not present it as eight retries of one answer.
6. **Pass@8 with same-trajectory test feedback.** Analyze cumulative try-2
   results across the eight trajectories. Use the same repair-versus-persistent
   framing as the pass@1 feedback section and state what the result says about
   feedback use at broader sampling coverage.
7. **Integrated visual findings and SFT impact.** Close with the required
   visualizations, a synthesis of the findings, limitations, and the resulting
   prioritized SFT-data implications. Include any evidence-quality,
   diagnostics, or sampling-stability finding that materially changes the
   interpretation.

Across those sections, the report must explain, for every question in the
completed GLM-4.7-Flash official Aider Polyglot C++ evaluation:

1. the exact question shown to the model;
2. every model response from the single selected canonical trajectory, or an
   exact local file link with line numbers when the response should not be
   reproduced inline;
3. whether each attempted response was correct;
4. the observed error for every incorrect response;
5. what the model did wrong at the implementation or problem-solving level;
6. what SFT data would teach the missing capability without contaminating the
   held-out benchmark.

The finished report must answer all six items for every task. It must be
understandable without reading terminal output or reconstructing the run.

For this document, **one response per task** means exactly one deterministic
canonical trajectory per task: `sample-01`. Because Aider may make a
sequential repair call inside that trajectory, analyze every attempted try in
`sample-01`. Do not analyze `sample-02` through `sample-08` as additional
per-task responses.

## Evidence In Scope

Use only the canonical completed run and the verified source-only SFT release
below.

### Evaluation run

- Run ID: `glm47-p8b-20260712095217`
- Run root:
  `.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/glm47-p8b-20260712095217`
- Evaluation mode: `independent-pass-at-1-and-8`
- Model: `zai-org/GLM-4.7-Flash`
- Model revision: `7dd20894a642a0aa287e9827cb1a1f7f91386b67`
- Aider commit: `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`
- Polyglot commit: `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`
- Canonical run samples per task: 8
- Maximum sequential Aider tries per trajectory: 2
- Canonical sample directories: `sample-01` through `sample-08`
- Reported trajectories per task: 1 (`sample-01` only)

The report must cite the run identity and completion evidence from:

- `run_receipt.json`
- `config.redacted.json`
- `independent-pass-at-1-and-8/samples.jsonl`
- `independent-pass-at-1-and-8/success-matrix.try1.json`
- `independent-pass-at-1-and-8/success-matrix.try2.json`
- `independent-pass-at-1-and-8/pass-at-1-and-8-by-try.json`
- each selected `sample-01` task's `.aider.results.json`
- each selected `sample-01` task's `.aider.chat.history.md`

The eight-sample run, frozen seed schedule, matrices, and admitted aggregate
metrics remain unchanged. `sample-01` is only the reporting projection. Never
substitute another sample because its response is more interesting, more
complete, or more successful. If a required `sample-01` artifact is missing
or invalid, stop and report the evidence problem rather than selecting
`sample-02` through `sample-08`.

Do not treat anything under `incomplete-attempts/` as an authoritative model
result. Those directories are archived interrupted attempts. Do not combine
the legacy `smoke/`, corrected `sampling-smoke-v1/`, or any historical run
with the canonical 26-task result.

### Existing SFT release

- Dataset ID: `aider-sft-source-only-75-v1-78ffe58ddc52`
- Release root: `.w8-biayn/data/aider-sft-source-only-75-v1`
- Training rows: `.w8-biayn/data/aider-sft-source-only-75-v1/sft/train.jsonl`
- Token ledger:
  `.w8-biayn/data/aider-sft-source-only-75-v1/sft/token-records.jsonl`
- Readiness evidence:
  `.w8-biayn/data/aider-sft-source-only-75-v1/readiness.json`

This release contains 75 immutable source-backed training rows and no
validation or test rows. It has zero task-ID overlap with the 26-task
benchmark. The report may identify relevant existing rows, but it must not
modify this ready release or describe proposed new rows as if they were
already part of it.

## Units Of Analysis And Metric Interpretation

The report has a top-level narrative section for each required stage in the
flow above. The Pass@1 sections contain one task subsection per benchmark task
using exactly one trajectory: sample-01. That subsection contains a try-1
analysis and, when Aider made a second model call, a separate try-2 analysis.
The Pass@8 sections use the complete eight-trajectory aggregate only; do not
select additional individual responses merely to illustrate pass@8.

Use metric names precisely. pass@1_try1 means the admitted one-trajectory,
first-try metric; pass@1_try2 is cumulative after same-trajectory feedback.
pass@8_try1 and pass@8_try2 describe the eight independent trajectories, with
the latter cumulative within each trajectory. Aider's raw pass_rate_1 and
pass_rate_2 remain Aider statistics and must never be renamed pass@1 or pass@8.

This distinction is mandatory:

- a **task/question** is one pinned Polyglot exercise;
- a **trajectory** is one independent fresh tree with one fixed sample seed;
- a **try** is one Aider model response inside that trajectory;
- try-2 success is cumulative after feedback from only that trajectory's
  try 1;
- the selected trajectory can contain both an incorrect try 1 and a correct
  try 2.

Never write a single unqualified “the model was correct” or “the model was
wrong” when the selected trajectory contains multiple attempted tries. State
the per-try verdicts and analyze each attempted response separately.

## Required Task Coverage

The finished report must contain exactly these 26 task sections, in this
order:

1. `all-your-base`
2. `allergies`
3. `bank-account`
4. `binary-search-tree`
5. `circular-buffer`
6. `clock`
7. `complex-numbers`
8. `crypto-square`
9. `diamond`
10. `dnd-character`
11. `gigasecond`
12. `grade-school`
13. `kindergarten-garden`
14. `knapsack`
15. `linked-list`
16. `meetup`
17. `parallel-letter-frequency`
18. `perfect-numbers`
19. `phone-number`
20. `queen-attack`
21. `robot-name`
22. `space-age`
23. `spiral-matrix`
24. `sublist`
25. `yacht`
26. `zebra-puzzle`

Before writing the report, reconcile this list against `samples.jsonl` and
both success matrices. Stop rather than silently omit, rename, or add a task
when the sets differ. Then verify that every task has exactly one authoritative
`sample-01` record and its matching result and history artifacts.

## Required Report Front Matter

The finished report must begin with a short evidence block containing:

- report title and generation date;
- run ID and absolute local run-root link;
- exact model repository and revision;
- exact Aider and Polyglot commits;
- edit format, temperature, top-p, maximum completion tokens, and seed
  schedule, plus the selected `sample-01` seed;
- task, selected-trajectory, and selected attempted-response counts reconciled
  from artifacts;
- run completion and Modal App teardown status;
- SFT dataset ID and absolute local release-root link;
- a statement that the evaluation tasks remain a permanent held-out set.

The front matter may include the four admitted aggregate metrics for context,
but those metrics must not replace the response-level analysis.

## Evidence And Citation Rules

Every factual judgment must be traceable to local evidence.

### Evidence priority

Use this priority order:

1. `.aider.results.json` for Aider's authoritative `tests_outcomes` and
   response diagnostics;
2. `.aider.chat.history.md` for the model-visible question, assistant edits,
   test feedback, and sequential repair history;
3. `samples.jsonl` for task/sample indexing, seeds, hashes, attempts made, raw
   outcomes, and normalized try success;
4. success matrices for task-level reconciliation;
5. `run_receipt.json` for immutable run identity and completion/teardown
   evidence.

The existing
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md` may guide taxonomy
and cross-task interpretation, but it is not a substitute for citing the
canonical response artifacts.

### Local links with line numbers

Use clickable absolute local Markdown links. A citation must point to the
first relevant line and state the complete line range in visible text:

```markdown
[model response, lines 120-181](/data/sanil/browser-is-all-you-need/.w8-biayn/.../.aider.chat.history.md:120)
```

For a single-line JSONL record, cite its exact line:

```markdown
[trajectory record](/data/sanil/browser-is-all-you-need/.w8-biayn/.../samples.jsonl:37)
```

Do not cite only a directory or a multi-megabyte manifest when a precise
history, result, or JSONL line exists. Verify all line numbers against the
final unchanged files immediately before delivering the report.

### Showing model responses

Include the model's editable answer inline when all of the following are true:

- the assistant answer can be cleanly isolated from the Aider history;
- it is reasonably short enough for the report to remain readable;
- it contains no secret, credential, hidden reference, hidden test body, or
  private chain-of-thought;
- its formatting can be preserved exactly.

Otherwise, write a one-sentence description of what the response attempted
and provide an exact history link with line numbers. Never invent, normalize,
or silently repair the response. Never reproduce private reasoning. It is
acceptable to show the final editable file blocks while omitting private
reasoning, as long as the omission is stated and the exact artifact is linked.

When a try produced no usable editable content, say so directly and cite the
history and result evidence. Do not manufacture a response from the final
working tree.

## Correctness Rules

Correctness must be reported per attempted try.

- Try 1 is correct only when the first entry in authoritative
  `tests_outcomes` is `true`.
- Try 2 is correct only when a second model response was attempted and the
  second entry in `tests_outcomes` is `true`.
- A try-1 pass skips try 2. Report try 2 as “not attempted because try 1
  passed,” not as another pass or failure.
- A try-2 pass is a recovery after same-trajectory test feedback. It does not
  make the try-1 response correct.
- Aggregate pass@8 metrics describe all eight run trajectories. They may
  appear as context, but they must not determine or replace the correctness
  verdict for the selected `sample-01` trajectory.
- A complete compile/test failure is a model outcome, not infrastructure
  failure.
- An exception-only or incomplete artifact is infrastructure evidence and
  must not be mislabeled as an incorrect model answer.

Aider's `num_exhausted_context_windows` records provider output-limit events.
It is a useful behavior diagnostic, but it is not by itself a correctness
verdict. A length-finished response can still apply a valid edit and pass.
Always use `tests_outcomes` for the verdict.

## Error Diagnosis Requirements

For every incorrect attempted response, provide all of the following.

### Observed error

State the most specific evidence-backed failure:

- no usable edit or output/context exhaustion;
- malformed Aider whole-file response or edit-application failure;
- missing or wrong file;
- compile error;
- link error;
- public API, namespace, type, signature, or const-correctness mismatch;
- runtime exception or timeout;
- test failure caused by wrong behavior;
- state, ownership, concurrency, or nondeterminism defect;
- edge-case or invalid-input defect;
- incomplete repair after try-1 feedback;
- another clearly named failure class.

Quote only the shortest diagnostic needed to establish the error and cite its
history line. Do not paste complete test files, reference implementations, or
large compiler logs.

### What the model did wrong

Explain the causal implementation mistake, not merely the symptom. The
analysis must answer questions such as:

- Which required contract did the answer misunderstand or violate?
- Which code choice caused the compiler or test result?
- Was the algorithm wrong, incomplete, or applied to the wrong API?
- Did the model preserve required file, class, function, namespace, and type
  names?
- Did it mishandle boundaries, invalid inputs, state transitions, ownership,
  determinism, formatting, or complexity?
- On try 2, did it use the feedback correctly, fix only part of the problem,
  preserve the original defect, or introduce a new defect?

Separate observation from inference. Use “The artifact shows …” for directly
observed facts and “This suggests …” for causal inference. Assign
`high`, `medium`, or `low` confidence to each inferred root cause.

For a correct response, use:

- **Observed error:** None; the authoritative tests passed.
- **What the model did wrong:** No correctness defect was observed in this
  response.

Do not invent a weakness merely to fill the template.

## Per-Task SFT Recommendation Requirements

Give one consolidated SFT recommendation per task after analyzing the selected
`sample-01` trajectory. Do not repeat a generic sentence after every response.

Each recommendation must contain these fields.

### Capability gap

Name the smallest reusable capability that would address the observed failure
pattern, such as exact C++ interface preservation, bounded whole-file output,
modular arithmetic, parser edge cases, ownership, circular indexing,
deterministic state, or compile-before-answer discipline.

### Relevant existing SFT rows

Search the 75-row source-only release and list any semantically relevant
non-benchmark rows by task ID. Link each row to the exact line in
`sft/train.jsonl`. Explain what it already teaches and what gap remains.

If no existing row is relevant, write “No sufficiently relevant existing row
was found” rather than forcing a weak match.

### Proposed additional SFT data

Describe new training examples at the capability level. For each proposed
example family, specify:

- a semantically distinct non-benchmark task concept;
- the target C++ skill and failure mode it addresses;
- suggested number and difficulty of rows;
- variation axes and edge cases;
- required starter/API constraints;
- what the correct final Aider whole-file answer must demonstrate;
- oracle tests needed to verify the target behavior;
- expected category and difficulty metadata;
- why the proposal is likely to improve one-shot correctness.

Recommendations must be concrete enough that a later dataset author can turn
them into candidate tasks, but this report must not author or admit those tasks
itself.

### Contamination and release controls

Every recommendation must state that:

- the exact benchmark prompt, starter, tests, reference, model response,
  repair transcript, and close semantic copies are forbidden as training data;
- official Aider task IDs are capability labels and denylist entries only;
- benchmark failures may motivate a skill category but may not be converted
  directly into SFT repair rows;
- new tasks require licensed, pinned provenance or separately approved
  original authoring;
- prompts must exclude tests, references, private paths, and evaluator data;
- references, normal tests, sanitizer tests, contamination screens, and
  token/mask evidence must pass through the repo-owned Aider SFT pipeline;
  human audit is optional and never replaces those mechanical gates;
- the immutable `aider-sft-source-only-75-v1` release must not be changed;
- accepted additions require a new reviewed dataset version/profile and must
  not be claimed ready before producer verification;
- training on any exact held-out task would invalidate future evaluation on
  that task.

Proposed rows should retain the established consumer shape where applicable:
C++17, Aider whole-file final answers, raw two-message conversations, thinking
disabled, explicit Qwen assistant loss, and the locked 4096-token admission
budget.

## Required Report Structure And Visualizations

Use the following top-level report structure. The Pass@1 task subsections use
the template below; place each task's try-1 material in section 2 and its
try-2 feedback material in section 3. Do not repeat the full task prompt or
try-1 response in the feedback section; link back to the one-shot analysis.

1. Benchmark, task format, and passing methodology
2. Pass@1, single try: per-task failures, findings, and visuals
3. Pass@1 with same-trajectory test feedback: repairs and capability
4. SFT curriculum implied by pass@1 and feedback
5. Pass@8, single try: independent-sampling observations
6. Pass@8 with same-trajectory test feedback: cumulative repair observations
7. Integrated visual findings, prioritized SFT impact, contamination audit, and limitations

Use the existing immutable visualization assets from the canonical report
directory. Embed them in the finished report rather than recreating their
numbers. Introduce every figure with the question it answers and follow it
with an evidence-backed finding; a gallery without interpretation is not
sufficient.

### Required figure placement

- **Benchmark and metric orientation:** 01-four-metrics.svg and
  14-evidence-completeness.svg.
- **Pass@1, single try:** 02-try1-matrix.svg, 04-task-difficulty.svg,
  05-topic-category-performance.svg, 06-difficulty-category-performance.svg,
  10-outcome-patterns.svg, and 11-diagnostics.svg.
- **Pass@1 feedback / retry capability:** 03-try2-transition-matrix.svg and
  07-retry-transitions.svg.
- **Pass@8, single try and sampling effects:** 08-cumulative-coverage.svg
  and 09-sample-stability.svg.
- **Pass@8 feedback and final synthesis:** reuse the retry-transition figures
  with the cumulative pass@8 interpretation, then include
  12-token-efficiency.svg and 13-runtime-interactions.svg when their
  diagnostics affect an SFT recommendation or a limitation.

The requirements document embeds the source assets below. The delivered report
must copy or link the equivalent run-specific assets as appropriate.

![Four admitted metrics](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/01-four-metrics.svg)
![Try-1 outcome matrix](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/02-try1-matrix.svg)
![Try-2 transition matrix](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/03-try2-transition-matrix.svg)
![Task difficulty](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/04-task-difficulty.svg)
![Topic performance](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/05-topic-category-performance.svg)
![Difficulty performance](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/06-difficulty-category-performance.svg)
![Retry transitions](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/07-retry-transitions.svg)
![Cumulative coverage](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/08-cumulative-coverage.svg)
![Sample stability](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/09-sample-stability.svg)
![Outcome patterns](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/10-outcome-patterns.svg)
![Diagnostics](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/11-diagnostics.svg)
![Token efficiency](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/12-token-efficiency.svg)
![Runtime interactions](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/13-runtime-interactions.svg)
![Evidence completeness](/data/sanil/browser-is-all-you-need/.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/figures/14-evidence-completeness.svg)

## Required Per-Task Section Template

Use the following template exactly enough that sections remain comparable.
Replace every placeholder with evidence-backed prose in the finished report.

```markdown
## <N>. `<task-id>`

### Question

<Exact model-visible task question, excluding later test feedback and hidden
assets. If too long, provide a concise faithful summary and an exact artifact
link with line numbers. List the editable starter files.>

Question evidence: [task prompt, lines X-Y](/absolute/path/.aider.chat.history.md:X)

### Task-level result

- Selected trajectories: 1 (`sample-01`)
- Try-1 correct trajectories: <X>/1
- Cumulatively correct by try 2: <Y>/1
- Solved at least once by try 1: <Yes/No>
- Solved at least once by try 2: <Yes/No>
- Main observed failure classes: <comma-separated list>

Task evidence: [selected trajectory record](/absolute/path/samples.jsonl:X),
[try-1 matrix](/absolute/path/success-matrix.try1.json:Y),
[try-2 matrix](/absolute/path/success-matrix.try2.json:Y)

### Selected trajectory — sample-01, seed <seed>

#### Try 1 model response

<Exact editable response, or concise description plus a link with line range.>

Response evidence: [try-1 response, lines X-Y](/absolute/path/.aider.chat.history.md:X)

#### Was try 1 correct?

<Yes or No.>

#### If not, what was the error?

<Specific observed compiler/test/protocol/output error, or “Not applicable.”>

Error evidence: [diagnostic, lines X-Y](/absolute/path/.aider.chat.history.md:X),
[official result](/absolute/path/.aider.results.json:Y)

#### What did the model do wrong?

<Causal technical explanation. Distinguish evidence from inference and include
root-cause confidence. For a pass, state that no correctness defect was
observed.>

#### Try 2 model response

<Exact response or line-linked fallback. If not attempted, state why.>

#### Was try 2 correct?

<Yes, No, or Not attempted.>

#### If not, what was the error?

<Specific error, “Not applicable,” or “Not attempted because try 1 passed.”>

#### What did the model do wrong on try 2?

<Explain how it used or failed to use its own try-1 feedback.>

### Selected-trajectory diagnosis

<Explain the observed failure or success, any try-1-to-try-2 repair, and the
most likely reusable capability gap in the selected trajectory. Do not infer
cross-sample recurrence or variance from the seven unreported trajectories.>

### SFT data recommendation

#### Capability gap

<Reusable skill gap.>

#### Relevant existing source-only SFT rows

- [`<existing-task-id>`](/data/sanil/browser-is-all-you-need/.w8-biayn/data/aider-sft-source-only-75-v1/sft/train.jsonl:<line>):
  <what it covers and what remains missing>

#### Proposed additional SFT data

- Task family: <semantically distinct non-benchmark concept>
- Suggested rows and difficulty: <count and mix>
- Skills and variation axes: <specific list>
- Required API/starter constraints: <specific list>
- Oracle coverage: <specific checks>
- Desired final-answer behavior: <what the target demonstrates>
- Expected benefit: <why this addresses the observed failure>

#### Contamination and release note

<Confirm that no exact benchmark material or model response will enter
training, that the existing ready release remains unchanged, and that any new
candidate requires a new reviewed and verified dataset version.>
```

## Required Cross-Task Sections

After the seven narrative stages and all 26 task subsections, add:

1. **Failure taxonomy summary** — counts of selected attempted responses by
   primary and secondary failure class, reconciled to every attempted try in
   the 26 selected `sample-01` trajectories.
2. **Retry analysis** — which failure classes were often repaired on try 2,
   which persisted, and whether the repair addressed the original diagnostic.
3. **Existing SFT coverage map** — benchmark capability gaps mapped to relevant
   lines in the 75-row source-only dataset, without claiming task overlap.
4. **Proposed SFT curriculum** — deduplicated recommendations grouped by
   capability, priority, row count, difficulty, and expected coverage.
5. **Contamination audit statement** — confirmation that recommendations are
   capability-derived and contain no held-out prompts, responses, tests,
   references, repair transcripts, or semantic copies.
6. **Limitations** — distinguish observed test outcomes from inferred root
   causes, state that the one-trajectory reporting projection does not measure
   cross-sample variance or replace the admitted pass@8 metrics, and state
   that suggested SFT improvements remain hypotheses until a newly trained
   model is evaluated on a fresh clean holdout.

## Writing Requirements

- Write complete sentences suitable for direct copy/paste into a report.
- Use plain technical language and define any benchmark-specific term once.
- Preserve exact task IDs, sample indices, seeds, try numbers, filenames, and
  API identifiers.
- Keep “question,” “trajectory,” “try,” and “task-level result” distinct.
- Do not call Aider `pass_rate_2` pass@2.
- Do not call retry feedback an independent sample.
- Do not claim that an SFT recommendation is proven to work.
- Do not claim the 75-row source-only release contains target-model responses,
  repair rows, benchmark tasks, validation data, or test data.
- Do not expose credentials, bearer tokens, private reasoning, hidden
  references, complete test bodies, or private evaluator mappings.
- Do not copy a reference solution into the analysis. Describe the required
  behavior and the model's defect using the minimum evidence needed.
- If evidence is ambiguous, state the ambiguity and confidence instead of
  guessing.

## Completion Checklist

The report is complete only when all of the following are true:

- [ ] The run receipt is complete and teardown-verified.
- [ ] The exact 26-task set is reconciled across samples and both matrices.
- [ ] Exactly one authoritative `sample-01` trajectory is selected for every
      task; `sample-02` through `sample-08` are not used for response analysis.
- [ ] Every attempted try in each selected trajectory has a response or a
      precise line-linked fallback.
- [ ] Every attempted try in each selected trajectory has a correctness
      verdict backed by
      `tests_outcomes`.
- [ ] Every incorrect try has a specific observed error and artifact link.
- [ ] Every selected response has a causal “what the model did wrong”
      explanation, or an explicit no-defect statement for a passing response.
- [ ] Every task has a selected-trajectory diagnosis.
- [ ] Every task has relevant existing SFT-row links or an explicit no-match
      statement.
- [ ] Every task has a concrete, non-benchmark SFT data recommendation.
- [ ] Proposed SFT examples are semantically distinct and contamination-safe.
- [ ] The existing immutable 75-row release is not modified or misrepresented.
- [ ] Cross-task counts reconcile to the selected `sample-01` records in
      `samples.jsonl` and their official results.
- [ ] All local links and line numbers resolve against the unchanged evidence.
- [ ] The document contains no credentials, private reasoning, hidden
      references, complete tests, or benchmark-derived training rows.
