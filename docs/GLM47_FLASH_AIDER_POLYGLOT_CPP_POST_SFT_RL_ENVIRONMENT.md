# GLM-4.7-Flash Aider C++ Post-SFT RL Environment

Status: implementation contract with the one-shot repository lane present.
The failure catalog, rubric-aware grader/reward, mutant admission, and canary
analyzer are implemented. The clean-room RL dataset, real task oracle/mutation
receipts, and no-update rollout evidence are still pending. This document does
not authorize a dataset release, GRPO run, cloud spend, or benchmark-uplift
claim until those gates pass.

Current-repository implementation target: `glm47_posttraining` with Miles,
Megatron, and SGLang. Historical `w8_biayn` and SLIME artifacts cited below are
research inputs, not importable implementation surfaces in this worktree.

## Purpose

This document specifies how to build a post-SFT reinforcement-learning
environment intended to improve GLM-4.7-Flash on the official Aider Polyglot
C++ benchmark without training on that benchmark.

It takes the structure and hard-earned design principles from
[`PIE_CPP_RL_ENVIRONMENT.md`](PIE_CPP_RL_ENVIRONMENT.md), then changes the
task interface and reward to match Aider whole-file editing:

- PIE asks for one behavior-preserving, faster replacement program.
- Aider asks for complete replacements of one or more named files that satisfy
  a public API and pass executable tests.
- PIE rewards correctness-gated runtime improvement.
- Aider RL must reward correctness-gated whole-file editing and, in a
  controlled second track, repair from real compiler/test feedback.

The target is **benchmark capability uplift**, not benchmark memorization. All
26 official Aider Polyglot C++ tasks, their prompts, tests, references, model
responses, and close semantic copies remain permanent external holdouts.

## Executive Conclusion

Create a repo-owned **Aider-style C++ RL-with-verifiable-rewards environment**
as a sibling of `glm47_posttraining.cpp_perf`, using the repository's existing
Miles, Megatron, and SGLang training stack. Do not add an Aider mode inside the
PIE task classes: the trainer plumbing is reusable, but the task, parser,
grader, reward, and evaluation contracts are not.

The first version should be a constrained whole-edit environment, not a
general-purpose SWE-agent loop:

1. start from the exact SFT checkpoint;
2. show only task documentation and editable starter files;
3. require strict Aider `whole` file blocks for every allowed solution file;
4. apply the replacements to a fresh isolated task copy;
5. compile and run grader-only visible and hidden tests in a pinned,
   network-disabled Docker sandbox;
6. run a fresh ASan/UBSan build before granting full correctness reward;
7. optionally allow one bounded same-trajectory repair turn;
8. score the executable final file state, not prose or apparent reasoning;
9. train with GRPO groups of eight initially; and
10. select checkpoints on clean-room held-out tasks, using the official 26-task
    Modal evaluation only for frozen milestone comparisons.

The environment should reproduce the parts of the Aider protocol that affect
the model: prompt, whole-file response contract, edit application, test
execution, bounded failure feedback, and at most two sequential attempts. It
should not run the complete official Aider benchmark harness in every training
rollout. A pinned Aider installation should instead be used for protocol
conformance tests and the final official evaluation.

### Why this conclusion

- The base run produced only 1 first-try pass in 208 trajectories, so first-edit
  semantic correctness is the central problem.
- The same run reached 36 cumulative passes after one repair, so executable
  feedback contains useful learning signal.
- Only one response was malformed, so a large format-only RL phase would target
  the wrong bottleneck.
- The local SFT projection contains direct whole-file final answers, not
  multi-turn repair trajectories. RL is therefore the natural place to add
  on-policy execution and repair experience after the direct-answer prior has
  been learned.
- A constrained environment matches the SFT output contract and the official
  benchmark more closely than an unrestricted shell agent, while avoiding
  unrelated tool-selection and repository-navigation variance.
- Reusing Miles avoids a custom trainer. The current asynchronous custom reward
  hook is sufficient for one-shot whole-file GRPO; bounded repair needs a
  separate multi-turn rollout bridge and explicit token credit assignment.

## 1. Research

### 1.1 Repository evidence examined

| Evidence | What was investigated | Design consequence |
|---|---|---|
| `docs/PIE_CPP_RL_ENVIRONMENT.md` | Task schema, prompt/private boundary, candidate lifecycle, correctness-gated scalar reward, grouped rollout loop, receipts, and held-out evaluation | Reuse its environment shape and operational discipline, but replace speed with whole-edit correctness and repair. |
| `src/glm47_posttraining/cpp_perf/{schema,dataset,reward,sandbox,eval}.py` | The task, single-code-block protocol, single-file harness, runtime reward, and speed-centric evaluation are PIE-specific | Add a sibling `aider_rl` package; do not extend `CppTask` with Aider flags. |
| `src/glm47_posttraining/integrations/miles_cpp_perf.py` | Miles JSONL shape, asynchronous batch scoring, task-path resolution, reward records, and debug aggregation | Reuse the Miles hook shape, but load `AiderTask`, fail closed on task identity, and keep infrastructure aborts out of policy reward. |
| `scripts/train_grpo.sh` and `examples/grpo.sh` | Data preparation, reward import, eval name, environment variables, preflight, and W&B defaults are hard-coded to PIE | Add an Aider launch profile and grader preflight while retaining the model, checkpoint, LoRA, SGLang, and Megatron arguments. |
| `src/glm47_posttraining/integrations/wandb_posttraining.py` | Published tables and promotion gates assume runtime speedup and `pie-cpp` tags | Add Aider correctness, repair, file-compliance, and infrastructure metrics rather than mapping them into speed fields. |
| `README.md` Aider SFT input contract | The documented Aider bundle contains `manifest.json` and `sft/train.jsonl`, which is enough for SFT but not executable rollout scoring | GRPO additionally requires immutable starter task trees, private tests, build metadata, references, and oracle receipts. |
| `.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-20260712095217/report.md` | First-try and repair success across all 26 tasks and eight trajectories | Make `pass@1_try1` primary and include a bounded repair track. |
| `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md` | Formatting, context exhaustion, category weaknesses, and failure interpretation | Do not overinvest in format shaping; prioritize semantic task families and concise responses. |
| `.w8-biayn/data/aider-tasks-reverify/` | Actual generated task layout, editable files, grader-only tests, references, provenance, and family structure | Build the RL task schema as an admitted projection of these roots, not as one-off task munging. |
| `.w8-biayn/data/aider-tasks-reverify-sft/manifest.json` | SFT row count, family composition, prompt boundary, source hashes, and status | Freeze exact SFT lineage; do not treat the current projection as an RL-ready split or release. |
| `docs/AIDER_SFT_SCOPE.md` | Meaning of `local_family_verified` and the limits of the local SFT projection | Require a new, explicit RL admission contract before training. |
| `docs/AIDER_TASK_MATERIALIZATION_GUIDE.md` | Generator ownership, public/private files, Docker oracle evidence, and contamination controls | Preserve all admission and secrecy gates in the RL builder and runtime. |
| Historical `w8_biayn` Aider/SLIME integrations | Whole-file parsing, immutable oracle fingerprints, Docker isolation, token capture, abort metadata, and multi-turn credit assignment | Treat these as upstream design evidence only. They are not present in this worktree and must not be referenced as runtime imports. |
| Four checked-in GLM Aider weakness taxonomies and generated curricula | Which latent capabilities the task families are intended to teach | Build a capability-balanced task sampler rather than uniform row sampling. |

### 1.2 External primary references

- The official Aider benchmark evaluates whether a model can edit existing
  source files into a test-passing state, supports `whole` format, and
  recommends Docker isolation for generated code:
  <https://github.com/Aider-AI/aider/blob/main/benchmark/README.md>.
- GRPO estimates relative advantages from groups of sampled outputs without a
  separate learned critic: <https://arxiv.org/abs/2402.03300>.
- SWE-Gym is supporting evidence that executable software-agent environments
  should bind natural-language tasks to isolated code state and deterministic
  tests: <https://arxiv.org/abs/2412.21139>.

### 1.3 What the complete base evaluation says

The canonical independent run contains 26 tasks times eight independent
trajectories, or 208 task/sample cells.

| Metric | Result | Interpretation |
|---|---:|---|
| `pass@1_try1` | 0.0048076923 | Only 1 of 208 initial edits passed. |
| `pass@1_try2` | 0.1730769231 | 36 of 208 passed after at most one repair. |
| `pass@8_try1` | 0.0384615385 | Only 1 of 26 tasks had any first-try success. |
| `pass@8_try2` | 0.4230769231 | 11 of 26 tasks had some success after repair. |

The final cell outcomes were:

- 1 first-try pass;
- 35 additional try-2 recoveries;
- 131 final test failures;
- 41 final context-exhausted outcomes;
- 1 malformed response; and
- no recorded syntax-error or timeout events.

#### Why these findings matter

- **Why prioritize semantic execution over formatting?** Only one response was
  malformed, while 131 ended in failed tests. The dominant error occurs after
  parsing.
- **Why preserve a first-try objective?** One initial pass in 208 is the
  clearest reliability deficit and is what a user experiences before paying
  for repair.
- **Why include repair at all?** Repair converted 35 of 207 initial failures,
  approximately 16.9 percent, proving that same-trajectory feedback can expose
  useful behavior.
- **Why constrain output length?** Context exhaustion was a material outcome,
  and the desired answer is only complete file content. More reasoning text is
  not itself progress.
- **Why not organize only by Easy/Medium/Hard?** Easy date and formatting-like
  tasks also failed. Capability family and failure mode are more informative
  than the repository's presentation difficulty label.

### 1.4 Capability map from the base run

| Capability group | Cumulative try-2 result | RL implication |
|---|---:|---|
| Time and date | 0/24 | Highest priority; teach normalization, boundaries, and calendar state transitions. |
| Text and parsing | 1/32 | Add validation, canonicalization, delimiter, and exact-output tasks. |
| Logic, grids, and games | 4/32 | Add coordinate, traversal, ownership, and constraint tasks without copying holdouts. |
| State and concurrency | 5/32 | Reinforce mutation invariants, atomicity, determinism, and bounded containers. |
| Algorithms and data structures | 14/48 | Use as a large mixed-difficulty source, but cap sibling families. |
| Numerical reasoning | 12/40 | Preserve with anchors while targeting radix, overflow, and invalid-input gaps. |

### 1.5 What the local SFT projection establishes

The historical upstream saved manifest records:

- 715 train rows;
- 44 families;
- 3,884,675 JSONL bytes;
- all rows assigned to `train`;
- strict user/assistant whole-file examples;
- exclusion of private prompt markers; and
- status `user_requested_local_projection_not_dataset_release`.

A fresh read-only render of the current task tree produces 709 rows from the
same 44 families: 30 date/clock roots, 379 DSA roots, and 300 text/grid roots.
The saved JSONL no longer exactly matches the evolving source roots.

Separately, this repository's current README documents a later 401-row Aider
SFT JSONL, a completed Miles SFT run, and a 26-task evaluation where Pass@1
changed from 0/26 to 1/26 and cumulative Pass@2 changed from 4/26 to 5/26. The
401-row run and the historical 715-row projection are distinct lineages. Never
substitute one manifest, source tree, or row count for the other.

The historical 715-row projection does not establish:

- a clean validation or internal-test split;
- tokenizer and assistant-loss-mask proof;
- a finalized dataset release;
- training authorization; or
- a completed SFT checkpoint.

The README establishes the current SFT and evaluation claim, but an RL launch
must still freeze and verify the exact 401-row manifest, checkpoint, tokenizer,
adapter, Aider/benchmark commits, and evaluation receipts. Neither the 401-row
public SFT contract nor the historical projection supplies the immutable
private task bundle required for executable GRPO reward. The base capability
map remains only a prior; use the fixed post-SFT evaluation and clean-room
rollout canary to choose the actual curriculum.

#### Why consumed SFT rows change the evaluation plan

Any row consumed by SFT, whether from the documented 401-row run or a historical
715-row projection, cannot become a clean generalization example merely by
being withheld from RL. The SFT model has already seen it.

The post-SFT RL program therefore needs three distinct clean-room evaluation
roles:

1. **SFT-seen/RL-held-out anchors:** old roots withheld from GRPO to measure
   forgetting, not unseen generalization.
2. **Never-seen clean-room evaluation:** newly admitted families and lineages
   absent from both SFT and GRPO, used for checkpoint selection.
3. **Official Aider holdout:** the exact 26 tasks, used only for frozen
   milestone evaluation.

For the documented completed SFT run, preserve its exact 401-row lineage and
create new unseen evaluation families rather than retroactively relabeling
consumed rows. Any experiment based on the historical 715-row projection must
preserve that lineage separately and apply the same rule.

### 1.6 Current codebase gap analysis

The current repository is a complete PIE C++ training path, not a generic
code-editing RL environment:

- `CppTask` stores one `prompt_code`, inline stdin/stdout tests, one oracle
  program, C++20 compile metadata, and reference runtime data. Aider needs an
  ordered set of editable files, a starter repository, C++17 build/test
  metadata, private test identities, lineage, and immutable grader receipts.
- `cpp_perf.dataset` exposes visible tests and requests one reasoning block plus
  one C++ block. Aider must preserve the SFT whole-file interface, hide all
  tests, and require one named block for every editable file.
- `cpp_perf.sandbox` writes `candidate.cpp` and `reference.cpp`, runs flattened
  stdin/stdout fixtures, then times both binaries. Aider must copy a task tree,
  apply allowlisted file replacements, configure/build/test it, and perform a
  separate fresh sanitizer build. There is no online reference comparison.
- `cpp_perf.reward` gives runtime-speed credit and positive shaped credit to
  recoverable invalid responses. Aider needs strict named-file validity and
  correctness-only reward tiers.
- `cpp_perf.eval` and W&B promotion logic use `correct_and_faster_rate`, runtime
  speedup, and missing-runtime gates. Those fields have no Aider meaning.
- `miles_cpp_perf.reward_func` provides useful concurrent batch scoring, but it
  loads `CppTask`, invokes the PIE sandbox, and currently converts unexpected
  exceptions to `-1.0`. Aider infrastructure failures must be removed and
  retried, not treated as model failures.
- `scripts/train_grpo.sh`, `examples/grpo.sh`, and the Modal profile select the
  PIE data builder, PIE reward import, `pie_cpp` eval name, PIE sandbox image,
  and `GLM47_CPP_*` variables. They need an Aider-specific profile or a
  task-agnostic launcher configuration.

The 401-row Aider SFT JSONL described in the repository is therefore only a
model-training projection. It cannot support verifiable GRPO by itself. Before
implementation can reach an end-to-end rollout, the source task roots must be
materialized with starter files, private visible and hidden tests, build files,
reference files, provenance, and oracle evidence. Official Aider benchmark
roots must not be used to fill this gap.

The recommended migration boundary is:

- reuse checkpoint conversion, LoRA setup, SGLang rollout serving, Megatron
  updates, Miles GRPO grouping, JSONL prompt/metadata transport, and generic
  run receipts;
- add Aider-specific schema, admission, renderer, parser, grader, reward,
  evaluation, and observability code; and
- leave `glm47_posttraining.cpp_perf` behavior and existing PIE entry points
  unchanged for reproducibility.

## 2. What to Reuse from the PIE Environment

| PIE component | Aider decision | Why |
|---|---|---|
| Typed task record | Reuse with an Aider-specific schema | Rollouts need deterministic public inputs, private oracle assets, and immutable identity. |
| Prompt/private boundary | Reuse strictly | Neither hidden tests nor reference answers may become model context. |
| Self-contained GRPO/eval data directory | Reuse | It makes task counts, splits, hashes, and run inputs reproducible. |
| Reference full-marks preflight | Reuse, but run once at admission | A broken reference or grader would teach false rewards. Aider has no runtime comparison requiring the reference every rollout. |
| Fresh Docker scratch environment | Reuse and strengthen | Generated C++ is untrusted and mutable state must not leak across trajectories. |
| Correctness-gated scalar reward | Reuse | Executable success must dominate format, length, and partial progress. |
| Partial-test shaping | Reuse with bounded visible/hidden weighting | Binary correctness is too sparse at the observed base success rate. |
| Grouped GRPO sampling | Reuse with group size eight initially | One sample produces zero group-relative advantage; eight matches the base evaluation. |
| Base/SFT/GRPO held-out comparison | Reuse | Training reward alone does not prove benchmark capability. |
| Run receipts and per-sample records | Reuse | Every claimed improvement must be attributable to a fixed model, task, grader, and policy. |
| Runtime speed bonus | Remove | Aider uplift is functional correctness, not PIE optimization. |
| One reasoning block plus one C++ block | Replace | Aider SFT and benchmark behavior require named whole-file blocks, often for multiple files. |
| Visible tests in the prompt | Do not inherit | Current Aider task prompts exclude tests; changing that would create SFT/RL/eval interface drift. |
| Recoverable-format positive reward | Do not inherit initially | Base formatting is already reliable; recovery should remain diagnostic so strict benchmark behavior cannot regress. |
| Local unsandboxed reward fallback | Do not use for evidence | Multi-file generated builds require the locked Docker security and identity boundary. |

## 3. Proposed Aider RL Task Contract

### 3.1 One admitted task contains

An RL task should project one generated root into an immutable record containing:

- `schema_version`, `task_id`, `family_id`, and semantic-lineage ID;
- `train`, `validation`, `internal_test`, or `anchor_eval` split;
- capability and failure-mode tags;
- `.docs/introduction.md` and `.docs/instructions.md` content;
- the ordered `files.solution` list and starter-file bytes;
- grader-only visible and hidden test identities and positive test counts;
- private reference-file mapping;
- exact C++17 dialect and configure/build/test commands owned by the
  repository, never by an authored task response;
- normal and sanitizer oracle receipts;
- task-tree, prompt, reference, test, grader-image, compiler, parser, and
  reward-policy fingerprints;
- provenance and contamination-screen receipts; and
- token-length and response-budget admission evidence under the exact SFT/RL
  tokenizer and chat template.

The model-visible JSONL contains public prompt content and safe metadata only.
Private references, tests, receipts, and build files stay in a grader-only task
bundle resolved by `task_path` or immutable task digest on the rollout host.

### Why this task contract

- **Why store ordered solution files?** Whole-file answers must map blocks to
  exact paths deterministically.
- **Why preserve starter hashes?** A candidate is meaningful only relative to
  the exact initial file state.
- **Why keep visible tests grader-only?** The SFT prompt did not show tests;
  revealing them in RL would train a different interface and encourage
  example-specific patching.
- **Why record semantic lineage, not only task ID?** Generated siblings can be
  near duplicates even with unique IDs.
- **Why bind parser and reward versions?** A reward change alters the meaning
  of every stored rollout.
- **Why require token evidence?** The Modal run showed material output
  exhaustion, while the current local projection has no locked token/mask
  proof.

### 3.2 Proposed generated data layout

```text
.glm47-posttraining/data/aider-cpp-rl-v1/
  manifest.json
  task-manifest.jsonl
  admission.records.jsonl
  oracle.records.jsonl
  tasks/                         immutable grader-side task copies
  grpo/train.jsonl               public prompts plus safe task pointers
  eval/anchor.jsonl              SFT-seen but RL-held-out regression anchors
  eval/validation.jsonl          never-seen family/lineage validation
  eval/internal-test.jsonl       never-seen final clean-room test
```

All conversion must be owned by the installable `glm47_posttraining` package,
with build and verify modes. There should be no shell-only projection or manual
JSONL edit.

### Why this layout

- It mirrors the useful PIE separation between task records, GRPO prompts,
  evaluation prompts, and the source manifest.
- It makes private assets available to the grader without placing them in
  model messages.
- It keeps immutable admission evidence separate from mutable rollout and run
  artifacts.
- It allows verification to recompute exact task and oracle identities before
  any GPU work.

## 4. Model Interface

### 4.1 Prompt

The prompt should be built with the same public renderer used by the local SFT
projection:

- Aider whole-edit instruction;
- task introduction;
- complete task instructions;
- every editable starter file, in `files.solution` order; and
- a final reminder to preserve required names and use only permitted
  dependencies.

It must not include tests, references, `.meta`, `.state`, `CMakeLists.txt`,
provenance, receipts, or benchmark material.

### 4.2 Required answer

Require one complete block for every allowed solution file:

````text
task-name.h
```cpp
// complete replacement header
```

task-name.cpp
```cpp
// complete replacement implementation
```
````

No prose, diff, test file, build file, second implementation, or unlisted path
is accepted. Terminal tokenizer markers remain a decoding concern and must be
removed with the supported rollout special-token setting, not accepted by a
weaker parser.

### Why this interface

- It exactly matches the direct whole-file behavior taught by the local SFT
  rows.
- Complete replacements make the final state deterministic and eliminate
  ambiguous patch application.
- Requiring every solution file prevents a model from relying on stale starter
  content that differs across tasks.
- Omitting chain-of-thought text reduces the output-exhaustion failure seen in
  the Modal run and focuses loss on the artifact the grader evaluates.
- A strict parser prevents the environment from rewarding behavior the
  official benchmark would reject.

### 4.3 Response budget

Do not copy the official Modal 32,768-token completion ceiling into training
by default. Determine the RL response budget from the locked tokenizer:

1. render every admitted prompt with the exact SFT/RL chat template;
2. tokenize every reference whole-file answer;
3. set a budget above the admitted maximum or a declared high-percentile plus
   bounded headroom;
4. reject tasks that cannot fit the total context without truncation; and
5. record prompt, answer, loss-mask, and total sequence hashes and counts.

The official benchmark may retain its larger ceiling for comparability.

### Why measure instead of guessing

A short budget can turn correct programs into artificial failures; an
unnecessarily large budget increases rollout cost and permits the long,
meandering behavior that already caused context exhaustion.

## 5. Candidate Evaluation Lifecycle

For every sampled response:

1. Resolve the task only through its immutable manifest entry.
2. Create a fresh unique scratch task and build root.
3. Parse strict whole-file blocks.
4. Require exactly the ordered allowlisted solution paths; reject missing,
   duplicate, extra, absolute, traversal, symlink, hardlink, special-file, or
   oversized outputs.
5. Write replacements only into the trusted scratch copy.
6. Configure the normal build with the locked compiler and explicit `Unix
   Makefiles` generator.
7. Build the exercise target separately from the test target.
8. Discover a positive visible and hidden test count.
9. Run normal visible and hidden tests separately under resource limits.
10. If all normal tests pass, create a second fresh sanitizer build, rediscover
    the tests, require matching positive counts, and run ASan/UBSan tests.
11. Convert the result into a versioned scalar reward and a rich private
    receipt.
12. Delete the scratch environment and all mutable build state.

The Docker grader must use a read-only root filesystem, no network, dropped
capabilities, no new privileges, unprivileged execution, bounded CPU/memory/
PIDs/file size/time, and only the necessary scratch mount writable.

Unlike PIE, the reference answer should not be compiled during every rollout.
It should be run through the exact normal and sanitizer grader during admission
and bound by digest in `oracle.records.jsonl`. There is no online reference
runtime comparison in this environment.

### Why this lifecycle

- **Why a fresh copy per trajectory?** Concurrent rollouts and repeated stages
  must not share generated files or build state.
- **Why test discovery before execution?** An empty or skipped suite can
  otherwise look like success.
- **Why separate visible and hidden execution?** It supports diagnostic reward
  shaping while preserving hidden-test secrecy and detecting visible-only
  overfitting.
- **Why a fresh sanitizer build?** Reusing the normal build can conceal stale
  artifacts or missing instrumentation.
- **Why preflight the reference once?** Correctness proof is necessary, but
  recompiling it on every rollout adds cost without producing a comparative
  signal as it does in PIE.
- **Why Docker only?** The reward executes untrusted multi-file C++; a host
  fallback is unsuitable for training or evaluation evidence.

## 6. One-Shot and Repair Environments

### 6.1 Track A: one-shot whole edit

The policy sees the task once and produces one complete file state. This track
should be the majority of early training and the primary evaluation target.

### Why

The base model's largest failure was first-try correctness. A repair-only
curriculum could improve `pass@1_try2` while leaving or even worsening
`pass@1_try1`.

### 6.2 Track B: one bounded repair

When the first edit parses and reaches the grader but fails, the environment
may return one bounded diagnostic message from the same trajectory. The model
then emits another complete replacement for all solution files.

Allowed feedback can include:

- compiler error class and bounded compiler excerpts;
- sanitizer failure class;
- the fact that visible or hidden tests failed;
- bounded public assertion information already implied by the contract; and
- counts or summaries that do not expose private expected values.

Feedback must not include hidden test source, private reference output,
reference code, private paths, unrestricted logs, or a diff against the
answer. Repair context from one trajectory must never be shared with another.

### 6.3 Credit assignment requirement

A successful second edit must not positively train the failed first edit.
Implement one of these before scale-up:

- mask first-response tokens from the repair reward and train only the repair
  response; or
- materialize the repair response as the single trainable sample conditioned
  on a detached on-policy failed state and feedback.

Every episode must still return exactly one trainer-reaching sample, including
abort husks, and every such sample must contain `metadata.round_number`.

### Why

Assigning the final successful reward to both turns can teach deliberate or
careless first-turn failure. The environment needs repair competence without
making repair dependence optimal.

### 6.4 Why not use unrestricted SWE-agent in version 1

The target benchmark interaction is narrow: edit named files, run tests, and
possibly repair once. A general shell agent adds tool selection, navigation,
command construction, and long-horizon state as additional learning problems.
Those skills are valuable for SWE benchmarks but are not the diagnosed Aider
Polyglot bottleneck. Start with the smallest environment that matches the
evaluation behavior. Revisit a fuller agent only if post-RL evidence shows the
whole-edit environment cannot transfer to official Aider.

## 7. Reward Design

### 7.1 Correctness-gated, rubric-aware scalar tiers

Task schema version 2 partitions all private normal tests into reusable
failure-derived behavior rubrics. For rubric `r`, let `q_r` be its passed cases
divided by its admitted case count. The partial semantic score is:

```text
p = sum(weight_r * q_r) / sum(weight_r)
```

This weights behavior specifications rather than raw test count, preventing a
large group of near-duplicate cases from dominating reward. When any critical
rubric is incomplete, cap `p` at `0.5`. Aggregate visible and hidden fractions
remain diagnostic metrics and must equal the sums of their rubric partitions.
Full correctness still requires every normal rubric and a clean fresh
sanitizer run.

| Outcome | Proposed starting reward |
|---|---:|
| Infrastructure/grader failure | remove sample and retry; no policy reward |
| Unsafe path, forbidden file, missing/extra file, or invalid whole format | `-1.0` |
| Edit applies but configure/compile fails or times out | `-0.5` |
| Compiles but not all normal tests pass | `-0.2 + 0.4 * p` |
| All normal tests pass but sanitizer build/tests fail | `0.3` |
| All tests and sanitizers pass after repair | `0.8` |
| All tests and sanitizers pass on the first edit | `1.0` |

These coefficients are canary defaults, not immutable constants. Calibration
must prove that adjacent tiers do not overlap and that observed groups have
useful variance.

The initial versioned taxonomy, task-authoring rules, mutation admission, and
canary contract are specified in
`docs/AIDER_RL_FAILURE_DERIVED_CURRICULUM.md` and
`configs/aider_rl/failure_rubric_catalog.v1.json`.

Optionally add at most `0.05` within a full-correctness tier for bounded token
or edit efficiency. This bonus must never let a repaired solution equal a
first-try solution or let an incorrect answer exceed a correct one.

### 7.2 Strict format and diagnostic recovery

The existing Polyglot parser can attempt recovery for diagnostics, but
recovered answers should retain the strict invalid-format reward in RL version
1. Record whether recovered files would compile or pass only as a debugging
field.

### Why

The base run had only one malformed response. Positive recovery reward would
spend learning capacity on a nearly solved behavior and could weaken the exact
protocol required by the target benchmark.

### 7.3 Why no runtime reward

Runtime optimization belongs to PIE. Adding it here would:

- mix functional correctness and optimization objectives;
- encourage unnecessary rewrites;
- make Aider uplift harder to attribute;
- introduce timing noise; and
- allow a faster partial or brittle implementation to influence learning.

Record build and test duration only as infrastructure telemetry.

## 8. Tasks to Include

### 8.1 Hard admission gates

Only admit a root when all of the following are current and fingerprint-bound:

- generator-owned regeneration;
- prompt and role-boundary validation;
- strongest available locked normal and fresh ASan/UBSan reference evidence;
- positive visible and hidden test discovery;
- exact visible/hidden partitioning into at least two catalog-backed rubrics;
- a compiling targeted mutant for every rubric plus unrelated-pass evidence;
- a current failure-rubric catalog fingerprint and private mutation receipts;
- family duplicate and benchmark-contamination screening;
- reference-to-solution-file mapping;
- clean provenance and semantic-lineage identity;
- exact Docker image and in-image compiler identity;
- exact prompt/parser/reward/tokenizer identities; and
- no unresolved `review`, `not_completed`, or stale receipt state.

`local_family_verified` is a prerequisite, not by itself RL admission. The
new RL contract also needs immutable splits, token evidence, runtime reward
compatibility, and a current task-level manifest.

### 8.2 Initial capability-balanced sampler

These are proposed sampling weights after admission, not target root counts.
Recompute them from the post-SFT evaluation.

| Capability | Initial weight | Included clean-room behaviors | Why |
|---|---:|---|---|
| Time/date | 25% | Clock normalization, calendar arithmetic, date difference, leap boundaries, nth/final occurrences, cross-midnight and offset-aware ranges, overflow-safe date math | Base solved 0/24 time/date cells. |
| Validation/parsing | 20% | Radix/digit checks, lexical canonicalization, quoted records, delimiters, coordinate bounds, cross-field constraints, deterministic expiration policies | This was a major base weakness and is not a materialized top-level collection in the current reverify tree. |
| State/concurrency | 20% | Bounded queues, producer-consumer rings, state transitions, ordered registries, deterministic parallel reduction, atomic rejection | Base results were weak and these tasks expose subtle invariant failures. |
| Algorithms/data structures | 15% | Trees, linked structures, circular containers, caches, intervals, tries, subsequences, heaps, sliding windows | Current corpus is large here; family caps prevent it from dominating while retaining useful mixed outcomes. |
| Text/grid/logic | 10% | Transpose, rotation, sparse encoding, flood fill, maze graphs, table reshaping, ownership mapping, exact rendering | Base text/grid capability was weak, but official task semantics and rejected spiral copies must remain excluded. |
| Numerical anchors | 10% | Overflow-safe loops, radix conversion, bitmask sets, classifications, value semantics | Preserve the model's relative strength and prevent catastrophic regression. |

Do not admit:

- any official Aider C++ root or related copy;
- target-model benchmark responses or official retry histories;
- the rejected spiral-matrix candidate family;
- stale or mechanically failed task roots;
- adversarial contamination controls as positive tasks;
- references, tests, or build files in prompts;
- hand-edited generated roots; or
- sibling variants whose only difference is cosmetic renaming.

### 8.3 Sampling rules

- Sample by family and capability, not uniformly by row.
- Cap siblings from one generator template per rollout window.
- Preserve a low-weight verified anchor set from relatively strong categories.
- Oversample tasks with mixed rewards under the SFT policy.
- Down-weight always-passing tasks after they have served as regression anchors.
- Defer uniformly impossible tasks until their prerequisites are taught.
- Record every dynamic sampling rejection and the resulting effective task
  distribution.

### Why

GRPO learns from relative differences inside a prompt group. Always-pass and
always-fail groups have little or no useful advantage variance. The current
corpus is also highly skewed toward large generated families, so uniform row
sampling would optimize family abundance rather than benchmark-relevant
capability.

## 9. Splits and Holdouts

### 9.1 If SFT has not run

Finish remediation, add the missing validation/parsing material, and freeze
train/validation/internal-test by complete family and semantic lineage before
SFT. A 70/15/15 family-stratified starting allocation is reasonable, subject
to minimum category coverage.

### 9.2 If SFT already consumed the candidate roots

Do not call a post-hoc split of those roots unseen. Instead:

- use admitted old roots for GRPO train;
- reserve some old roots as SFT-seen/RL-held-out forgetting anchors;
- author and admit new family-disjoint roots for validation and internal test;
- keep the official 26 tasks untouched for external evaluation.

### Why

Split integrity is about complete training history, not only the current
stage. An example seen during SFT is not a clean generalization test merely
because GRPO did not sample it.

## 10. GRPO Training Loop

The proposed active lane is Miles-based:

- SFT checkpoint as actor and reference initialization;
- SGLang rollouts;
- Megatron updates;
- group size eight initially;
- global batch derived from rollout prompts times samples per prompt;
- one trainable sample per prompt/sample cell in version 1;
- explicit KL monitoring against the frozen SFT checkpoint;
- no custom trainer; and
- W&B plus local receipts as observability and evidence.

Start with two canaries rather than a large fixed schedule:

1. **No-update rollout canary:** 16 to 32 capability-balanced tasks, eight
   samples each, one-shot only. Measure reward distribution and group variance.
2. **Short update canary:** the same one-shot task budget, frequent internal
   evaluation, and several recoverable checkpoints.

The existing `--custom-rm-path` integration is enough for version 1 because it
scores one completed response. Do not block the one-shot canary on repair.
Implement repair only after the direct environment has passed its no-update
and short-update gates; repair requires a Miles-compatible custom generation
or environment bridge that can append bounded grader feedback and return the
correct trainable token span.

After that bridge exists, an initial 60/40 one-shot/repair episode mixture is
reasonable only if the post-SFT run shows both residual first-turn failures
and repairable states. Increase direct one-shot weight if repair improves while
first-turn accuracy falls.

### Miles and multi-turn invariants

- `n_samples_per_prompt` must stay at least two; use eight initially.
- For repair, every trainer-reaching sample, including abort husks, must carry
  `metadata.round_number`.
- For repair, exactly one trainable sample may return per episode so group
  reshaping stays valid, and the failed first response must not receive the
  final success reward.
- Record and investigate adapter forks rather than silently multiplying group
  samples.
- Unique per-attempt workspaces and idempotent setup are mandatory.
- An HF export is ready only when real weight shards exist.
- Infrastructure aborts must be removed from policy learning and reported by
  reason.

### Why canary first

The base first-turn success rate is so low that binary rewards may produce
zero-variance groups. SFT may fix this, but only a no-update rollout can show
whether the proposed tasks and reward yield learnable variation. Scaling an
all-zero environment wastes compute and can disguise data problems as an
optimizer problem.

## 11. Metrics

### 11.1 Primary official uplift metrics

Use the same complete official Modal protocol for base, SFT, and selected GRPO
checkpoints:

- `pass@1_try1` as the primary metric;
- `pass@1_try2` as cumulative same-trajectory repair success;
- `pass@8_try1` as task-level support without repair;
- `pass@8_try2` as task-level support with one repair;
- repair conversion conditional on try-1 failure;
- tasks solved at each try depth;
- six-category success and coverage; and
- per-task gains and regressions.

Keep model-serving, tokenizer, Aider commit, Polyglot commit, task set, seed
schedule, temperature, top-p, completion ceiling, tries, grader, and timeout
identical. Aider `pass_rate_2` remains cumulative second-try success and must
never be renamed `pass@2`.

### 11.2 Clean-room evaluation metrics

- strict `pass@1` and empirical `pass@8`;
- first-edit full correctness;
- cumulative second-edit correctness;
- repair conversion rate;
- family-disjoint and capability-disjoint performance;
- SFT-seen/RL-held-out anchor retention;
- format validity and allowed-file compliance;
- configure, compile, visible-test, hidden-test, and sanitizer pass rates;
- failure transitions such as compile failure to partial tests to full pass;
- tokens, calls, and wall time per successful task; and
- context-exhaustion rate.

### 11.3 Training-health metrics

- reward mean, standard deviation, and histogram;
- zero-variance group fraction;
- groups with at least one full pass;
- KL to the SFT reference;
- entropy, policy ratio, clipping fraction, and gradient norm;
- trained assistant tokens and response length;
- one-shot versus repair reward distribution;
- agent rounds and repair-feedback bytes;
- removed/aborted samples by reason;
- dropped adapter forks;
- grader latency and throughput; and
- GPU memory and rollout utilization.

### 11.4 Safety and integrity metrics

- forbidden path and file attempts;
- missing, duplicate, and extra solution files;
- traversal, symlink, hardlink, special-file, and oversized-output rejection;
- private marker leakage in prompts and feedback;
- stale task/oracle/grader fingerprint rejection;
- positive test-discovery rate;
- infrastructure failures separated from model failures; and
- contamination-control pass rate.

### 11.5 Statistical treatment

Report uncertainty with tasks as the clustering unit because eight
trajectories from one task are not 208 independent tasks. Use paired,
task-clustered bootstrap comparisons when the same task/seed cells exist for
SFT and GRPO. Predeclare an acceptable non-regression margin for secondary
metrics rather than choosing one after observing results.

### Why these metrics

- Aggregate reward can rise through easier sampling without generalization.
- `pass@8` can rise while first-response reliability stays poor.
- Repair can improve while one-shot behavior regresses.
- Formatting can remain perfect while semantics stay flat.
- Category averages can hide collapse on particular tasks or families.
- Infrastructure aborts can look like model failures unless they have a
  separate denominator.

## 12. Promotion and Stop Gates

### Gate 0: freeze SFT lineage

- Record the exact consumed JSONL, manifest, and SHA-256.
- Record the SFT checkpoint, tokenizer, chat template, thinking policy, and
  adapter identities.
- Never substitute the historical 715-row manifest, its current 709-row
  rerender, and the documented 401-row Miles SFT dataset for one another.

### Gate 1: fixed post-SFT evaluation

Verify the documented official evaluation receipts or rerun the complete
26-by-8 evaluation on the exact SFT checkpoint. Also run the internal
clean-room baseline if a valid unseen set exists.

Stop and return to SFT/data work if:

- first-turn success remains essentially zero;
- nearly every RL prompt group has zero reward variance;
- validation/parsing and other prerequisite gaps remain unmaterialized; or
- format improves but executable correctness does not.

### Gate 2: separately authorize RL admission

Publish a contract that explicitly names the eligible local roots and requires
current family, task, oracle, token, contamination, split, and runtime evidence.
The present local-family and SFT-projection scope is not training authorization.

### Gate 3: build and verify the RL bundle

Require exact regeneration, full oracle success, positive tests, private/public
separation, split integrity, immutable fingerprints, and no stale source rows.

### Gate 4: no-update environment canary

Require:

- correct reward tiers on controlled fixtures;
- references passing the exact grader;
- negligible infrastructure failure;
- useful group reward variance;
- no private prompt or feedback leakage; and
- exact one-sample-per-episode group shape.

### Gate 5: short GRPO canary

Require:

- finite KL and gradients;
- increasing executable success rather than only lower format failures;
- stable response length;
- no family or category collapse;
- correct repair credit assignment; and
- recoverable checkpoints and receipts.

### Gate 6: internal held-out promotion

Promote a checkpoint only when never-seen clean-room performance improves and
anchor regressions stay inside the predeclared margin.

### Gate 7: frozen official evaluation

Run the complete paid Modal evaluation once for the selected checkpoint and
compare against both base and SFT. Do not use official task results for routine
checkpoint or hyperparameter selection.

## 13. Proposed Implementation Surfaces

The implementation should be a sibling environment inside the package that is
actually built by this repository:

```text
src/glm47_posttraining/aider_rl/
  __init__.py
  schema.py          admitted task and receipt schemas
  admission.py       source/family/token/oracle/split gates
  curriculum.py      failure catalog and no-update canary gates
  dataset.py         deterministic GRPO/eval projection
  prompt.py          SFT-compatible public renderer
  parser.py          strict named whole-file parser
  sandbox.py         locked multi-file normal/sanitizer grader
  reward.py          versioned scalar tiers and feedback redaction
  eval.py            records, summaries, comparisons, confidence intervals

configs/aider_rl/
  failure_rubric_catalog.v1.json

src/glm47_posttraining/integrations/
  miles_aider_rl.py      one-shot Miles reward bridge
  miles_aider_repair.py  optional later multi-turn bridge

docker/
  aider_cpp_grader.Dockerfile

scripts/
  train_aider_grpo.sh
  evaluate_aider.py

examples/
  aider_grpo.sh

tests/
  test_aider_schema.py
  test_aider_parser.py
  test_aider_dataset.py
  test_aider_sandbox.py
  test_aider_reward.py
  test_miles_aider_rl.py
```

Suggested CLI ownership:

```text
python -m glm47_posttraining.aider_rl.dataset draft-schema
python -m glm47_posttraining.aider_rl.dataset admit ...
python -m glm47_posttraining.aider_rl.dataset build ...
python -m glm47_posttraining.aider_rl.dataset verify ...
python -m glm47_posttraining.aider_rl.dataset oracle ...
python -m glm47_posttraining.aider_rl.dataset summarize ...
python -m glm47_posttraining.aider_rl.curriculum validate-catalog ...
python -m glm47_posttraining.aider_rl.curriculum analyze-canary ...
```

The precise names may change during implementation, but all conversion,
verification, and summarization must remain repo-owned and testable. Do not
implement a standalone trainer or a one-off dataset script.

### 13.1 New Aider package responsibilities

`schema.py` must define a separate `AiderTask` and result/receipt models. It
must not add optional Aider fields to `CppTask`; doing so would create a union
of two incompatible execution models. The Aider result needs separate normal
visible, normal hidden, sanitizer visible, and sanitizer hidden counts, plus
configure, compile, timeout, unsafe-edit, and infrastructure status.

`prompt.py` must reproduce the exact SFT public renderer and deterministic file
order. `parser.py` must require exactly one complete named block per editable
path and reject missing, duplicate, extra, absolute, traversal, symlink,
hardlink, special-file, and oversized outputs. Recovery may be recorded for
diagnosis but may not turn strict invalid format into a positive reward.

`admission.py` and `dataset.py` must consume original task roots, not SFT JSONL
alone. They must freeze family-disjoint splits, copy immutable grader-side task
bundles, run reference preflight once, verify positive tests, compute tokenizer
budgets, screen official benchmark contamination, and emit safe Miles rows
whose metadata contains an immutable task pointer or digest.

`sandbox.py` must use a dedicated pinned grader image with CMake, the selected
C++17 compiler, test dependencies, and sanitizers. It must create a fresh task
copy and separate fresh sanitizer build for every candidate. The Aider evidence
path is Docker-only: do not expose the PIE `local` backend through an Aider
environment variable or silently fall back to host execution.

`reward.py` must remove runtime comparison completely. It should implement the
versioned correctness tiers in Section 7 and return rich private receipts.
Infrastructure failures must have a separate result type that the Miles bridge
removes and retries; they must not be flattened into `score=-1.0`.

`eval.py` must aggregate strict one-shot and eventual repair correctness,
file-compliance, build/test/sanitizer transitions, family/capability results,
zero-variance groups, and task-clustered uncertainty. It must not reuse
`correct_and_faster_rate` or missing-runtime promotion gates.

### 13.2 Miles bridge and launcher changes

The one-shot `miles_aider_rl.reward_func` can reuse the concurrency shape of
`miles_cpp_perf.reward_func`: accept a sample or list, resolve safe metadata,
score items in bounded worker threads, and return dictionaries under the
configured reward key. It must instead load `AiderTask`, invoke the multi-file
grader, and emit Aider fields. Relative and absolute task paths supplied by
sample metadata must resolve inside the configured immutable Aider data root;
the bridge must reject escape paths, stale digests, and arbitrary current
working directory fallbacks.

Add an Aider launcher rather than changing the canonical PIE defaults in
place. It may initially share or source generic model/checkpoint code from
`scripts/train_grpo.sh`, but its effective arguments must include:

```text
--prompt-data <aider-data-root>/grpo/train.jsonl
--input-key prompt
--label-key label
--metadata-key metadata
--custom-rm-path glm47_posttraining.integrations.miles_aider_rl.reward_func
--reward-key score
--eval-prompt-data aider_cpp <aider-eval-jsonl>
```

Use `MILES_AIDER_DATA_DIR`, `MILES_AIDER_TASKS_DIR`,
`GLM47_AIDER_GRADER_IMAGE`, and `GLM47_AIDER_REWARD_WORKERS` rather than
overloading the existing `MILES_CPP_*` and `GLM47_CPP_*` meanings. The launcher
must preflight the exact grader image and a reference fixture before starting
GPU work. The rollout and evaluation response limits must come from recorded
token admission evidence rather than inheriting PIE's 1,536-token default.

The existing Modal profile sets the PIE sandbox to local execution. That is
not an acceptable Aider reward configuration. A Modal Aider profile must either
provide the locked container isolation boundary on the rollout host or route
grading to separately isolated reward workers. If neither is available, Modal
may generate responses for frozen official evaluation but must not run the
Aider GRPO reward path.

The existing GLM bridge, checkpoint conversion, LoRA configuration, SGLang
serving, Megatron update arguments, GRPO group size, and rollout dump plumbing
remain reusable. The current Aider SFT path may continue to consume prebuilt
Miles `messages` rows without invoking an RL grader.

### 13.3 One-shot first, repair second

Version 1 should implement only one-shot whole-edit GRPO. That path fits the
current Miles custom reward contract and addresses the primary benchmark
metric directly.

Bounded repair is not only a different reward function. It needs a new rollout
bridge that:

- evaluates the first response before the episode ends;
- redacts and bounds compiler/test feedback;
- appends that feedback only to the same trajectory;
- samples a second complete file state;
- returns exactly one trainer-reaching sample with `metadata.round_number`;
- masks or detaches failed first-response tokens from final success credit; and
- preserves abort metadata without training on infrastructure failure.

Do not simulate repair by concatenating two independent Miles samples or by
assigning the final reward to both responses.

### 13.4 Why not reuse one existing PIE module unchanged

- `cpp_perf.schema.CppTask` assumes one program, inline tests, C++20, and a
  runtime reference.
- `cpp_perf.dataset` exposes visible tests and asks for reasoning plus one code
  block.
- `cpp_perf.sandbox` creates `candidate.cpp` and `reference.cpp`, then performs
  stdin/stdout comparison and runtime measurement.
- `cpp_perf.reward` rewards speed and gives shaped positive credit to some
  invalid formats.
- `cpp_perf.eval` and `wandb_posttraining` promote on runtime-speed metrics.
- `miles_cpp_perf` is valuable as a Miles integration example, but its task
  loader, exception policy, reward record, and CLI remain PIE-specific.

The correct reuse unit is trainer and orchestration plumbing, not the PIE task
model or grader.

### 13.5 Existing files that require Aider-aware changes

- `scripts/train_grpo.sh`: preferably factor task-neutral Miles/model arguments
  into a shared helper; otherwise leave it PIE-only and add
  `scripts/train_aider_grpo.sh` with explicit Aider data, reward, eval, grader,
  and preflight settings.
- `examples/grpo.sh`: leave the canonical PIE profile unchanged and add an
  Aider wrapper with Aider W&B names, measured response limits, Docker-only
  grading, and an SFT adapter input.
- `examples/modal/modal_app.py`: add a distinct Aider application/profile only
  after its isolation strategy is resolved; do not reuse the local PIE grader.
- `src/glm47_posttraining/integrations/wandb_posttraining.py`: add or factor an
  Aider publisher with correctness, repair, file-compliance, family, abort,
  and grader-throughput fields. Do not populate runtime columns with Aider
  values.
- `scripts/evaluate.py`: retain it for PIE and add `scripts/evaluate_aider.py`
  for clean-room generation/grading. Run the pinned official Aider harness
  separately for milestone evaluation.
- `README.md`: document the private GRPO task-bundle contract in addition to
  the existing public SFT JSONL contract, plus the one-shot canary and external
  official-evaluation workflow.
- `pyproject.toml` and the grader Dockerfile: declare any tokenizer/build-time
  Python dependency used by admission and pin the grader toolchain separately
  from the H100 training image.
- Tests: preserve all current PIE tests and add parser path-safety fixtures,
  public/private leakage checks, oracle/stale-digest rejection, positive test
  discovery, sanitizer freshness, reward tier boundaries, infrastructure
  removal/retry, Miles batch shape, and launch-profile assertions.

## 14. Operational Evidence and Observability

One launch should remain one W&B group with deterministic stage runs. Preserve
local receipts as the on-disk source of truth.

Publish:

- Miles `train/*` and `rollout/*` metrics;
- `rollout_health/*` correctness gates, abort reasons, zero-variance groups,
  attempts, and token counts;
- `eval/*` one-shot, repair, family, category, and task tables on each stage;
- a base/SFT/GRPO uplift table on the pipeline run;
- dataset composition and family/split tables;
- grader-image/compiler/parser/reward fingerprints;
- VRAM and grader-throughput evidence; and
- alerts for all-abort evaluation, high abort rate, missing test discovery,
  failed oracle preflight, and failed launches.

### Why both W&B and local receipts

W&B supports live diagnosis and cross-stage comparison. Immutable local
records are needed to recompute results, investigate failures, and prove that
the dashboard was derived from exact task and grader identities.

## 15. Risks and Countermeasures

| Risk | Countermeasure | Why |
|---|---|---|
| Benchmark contamination | Permanent 26-task denylist, semantic screens, clone controls, family-aware review | Exact-ID filtering cannot catch renamed copies. |
| SFT/RL interface drift | Reuse exact public renderer, file order, template, tokenizer, and thinking policy | RL should improve the behavior SFT taught, not replace it with another protocol. |
| Reward sparsity | Post-SFT no-update canary, partial-test shaping, mixed-difficulty sampling | All-zero groups provide no GRPO advantage. |
| Reward hacking through visible behavior | Hidden-weighted partial reward and full hidden/sanitizer gate | Public-contract success alone is insufficient. |
| Repair dependence | Majority one-shot track, higher try-1 reward, masked first-turn repair credit | The model must not learn to fail first. |
| Test leakage through feedback | Bounded redaction and private-source exclusion | Feedback must teach debugging, not reveal answers. |
| Synthetic-family domination | Family caps, lineage deduplication, capability-balanced sampling | Row count is not behavioral diversity. |
| False held-out claims after all-train SFT | New never-seen families plus explicit SFT-seen anchors | Stage-local withholding cannot erase prior SFT exposure. |
| Context exhaustion | Final-answer-only targets, measured budgets, token-efficiency metrics | The Modal run already showed output-limit failures. |
| Infrastructure failures becoming reward | Remove and retry; separate denominators and alerts | The policy cannot control Docker or image failures. |
| Parser becoming more permissive than Aider | Strict reward, recovery diagnostic-only, pinned Aider conformance fixtures | Local success must transfer to the target protocol. |
| Stale task or oracle evidence | Fingerprint every policy input and fail closed on mismatch | Ongoing remediation has already made the saved projection stale. |

## 16. Definition of Success

Training reward or loss is not success. The environment succeeds only if it
produces a checkpoint for which:

1. strict first-edit correctness improves on never-seen clean-room tasks;
2. repair success improves without reducing first-edit reliability;
3. format validity, safety, and anchor capabilities do not regress;
4. official `pass@1_try1` improves over the exact SFT checkpoint under the
   same 26-by-8 protocol;
5. official `pass@1_try2`, `pass@8_try1`, and `pass@8_try2` remain stable or
   improve within predeclared margins;
6. no official task or semantic copy entered SFT or RL; and
7. every result is reproducible from immutable task, model, tokenizer, Aider,
   grader, sampling, and reward receipts.

## 17. Immediate Next Actions

1. Freeze and verify the documented 401-row SFT dataset, checkpoint, tokenizer,
   adapter, and evaluation receipts; keep the historical 715/709-row lineage
   separate.
2. Finish the currently changing task-family remediation and do not overwrite
   the old projection in place.
3. Run the exact post-SFT 26-by-8 Modal evaluation before choosing RL weights.
4. Materialize the original clean-room task roots with starter repositories,
   private rubric-labeled tests, diagnostic mutants, build files, references,
   provenance, and oracle evidence; do
   not attempt to reconstruct rewards from SFT JSONL alone.
5. Materialize and verify clean-room validation/input-parsing families, then
   create new never-seen validation and internal-test lineages if SFT used all
   existing roots.
6. Use the checked-in failure taxonomy and rubric catalog; add new abstract
   modes only through clean-room review, never by copying official material.
7. Materialize candidate roots against the checked-in `AiderTask` JSON schema,
   then run the implemented deterministic builder, tokenizer verifier, strict
   parser, oracle preflight, and Docker-only grader on real fixtures.
8. Validate the implemented one-shot `miles_aider_rl` reward bridge, Aider GRPO
   launcher, evaluator, and Aider-native W&B finalizer with a no-update dump;
   canonical PIE behavior remains unchanged.
9. Run a no-update SFT-policy rollout canary and require the implemented
   curriculum analyzer to report `ready`.
10. Run a small, balanced one-shot GRPO canary only if reward variance and
    infrastructure gates pass.
11. Implement bounded repair only after one-shot promotion gates pass and the
    multi-turn token-credit contract is tested.
12. Select on internal held-out evidence and reserve the official Modal run for
    the chosen checkpoint.

The most important sequencing decision is deliberate: **measure the SFT model
first, then let residual failures choose the RL curriculum**. The base run
explains why the task families were created; it cannot by itself prove what the
post-SFT policy still needs.
