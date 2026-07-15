# Repository Development Guide

`AGENTS.md` and `CLAUDE.md` must stay symlinks to this file. Update this file
once; do not fork the guidance.

## Active Project

This repository is a C++ performance-RL project. The active training direction
is SLIME-based Moonlight and GLM training on PIE C++ optimization tasks.

Current goal: train open-weight models that rewrite correct C++20 programs to
run faster while preserving behavior, then prove uplift on held-out PIE tasks.

SkyRL/rLLM, SkyPilot renderers, MLflow run-status parsing, and old GCP launch
helpers are legacy compatibility/reference surfaces. Do not use them for new
active training work unless the user explicitly asks for legacy maintenance.

Out of scope unless a later phase is explicitly requested:

- BrowserGym
- DOMDiff
- Harbor
- WebArena
- MiniWoB
- AndroidWorld
- Go
- Custom GPU kernel labs or unrelated performance experiments

## Required Reading

Before changing behavior, read:

1. `README.md`
2. `ROADMAP.md`
3. `.agents/skills/w8-biayn-framework/SKILL.md`
4. `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md` when implementing or
   changing Aider-style SFT task generation
5. Relevant implementation files under `src/w8_biayn/`

The previous `/tmp/ENGINEERING_SPEC_v2_cpp_only.md` may not exist on every
machine. Treat checked-in guidance as the active source when that file is
missing.

## Non-Negotiable Boundaries

Use SLIME, Megatron, and SGLang for active SFT/GRPO work.

Do not write a custom trainer.

Do not use PIE's old Hugging Face Trainer path or any SuperCoder trainer as the
active trainer.

Do not reintroduce SkyRL/rLLM as the active stack unless the user explicitly
requests a rollback or legacy compatibility task.

Allowed upstream use:

- SLIME: active SFT/GRPO framework.
- PIE: source C++ slower-to-faster pairs, official tests, and data/eval lessons.
- LearningOpt PIE: gem5 reference/calibration lessons when relevant.
- SuperCoder: schema, correctness/eval lessons, and examples only.
- SkyRL/rLLM: legacy reference only.

Use `uv run w8-biayn upstreams clone` for pinned repo copies under
`.cache/upstreams/`. Temporary study clones may live under `/tmp`; do not
vendor upstream repos or data.

## Fresh-Machine Contract

A clean clone should support:

```bash
./scripts/bootstrap.sh
uv run w8-biayn data doctor
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime doctor
uv run w8-biayn slime setup
uv run w8-biayn cpp harness preflight --dry-run
```

If a change invalidates this path, update implementation, tests, README, this
file, and `.agents/skills/w8-biayn-framework/SKILL.md` in the same logical
change.

Do not rely on globally installed tools unless bootstrap installs them or
`doctor` reports a clear missing prerequisite with the exact next action.

## Data Discipline

Dataset conversion is a deliverable. No one-off PIE or SuperCoder munging is
allowed.

The authoritative contract for the primary SFT dataset generation pipeline is
`docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`. Its implementation lives in
`src/w8_biayn/aider_sft/` and is exposed through the repo-owned
`w8-biayn data aider-sft ...` CLI. The pilot profile remains draft. The
source-only profile records a frozen operator environment and promoted source
inventory, but `plan` must revalidate them and all admission/review/release
gates still fail closed. Claim a source-only release as ready only after both
`finalize` and producer `verify` report `ready`; generated release bytes remain
ignored by Git. Do not claim a ready 96-task pilot merely because the profile
or CLI exists. The pilot
targets 96 total admitted Aider-style C++ roots (72 train, 12 validation, 12
internal test), starts from an exact 75-task
non-benchmark Exercism inventory (60 practice plus 15 concept roots), and
admits at least 21 human-approved LLM-assisted roots, with LLM backfill for
rejected or category-deferred source candidates. Complete source admission and
classification before paid authoring, compute exact missing cells, and require
three times remaining candidate capacity. It keeps tests/references hidden from
rows, excludes all 26 official Aider C++ roots and related copies, and defines
readiness without
model responses, repair rows, training, benchmarking, or uplift. V1 is
semi-autonomous: mechanical work may run automatically, but source inventory,
LLM usage terms, every LLM task, contamination near-matches, the final split,
and the exact final release package need scope-specific fingerprint-bound human
approval. Read and update that document before
implementing or changing this pipeline.

The separate `aider-sft-source-only-75-v1` profile is the supported no-LLM
75/0/0 lane. It assigns the exact 75 approved non-benchmark Exercism roots to
train, forbids `[llm]` configuration and paid-call acknowledgement, and has no
backfill path. A rejected, deferred, or mechanically failed source makes that
release incomplete. This does not weaken admission, contamination, token/mask,
final split/release review, or producer/consumer verification gates, and it
does not replace or satisfy the 96-root pilot.

Prepare tokenizer-only and seccomp assets through the repo-owned
`prepare-tokenizer` and `prepare-seccomp` subcommands. Bind the tokenizer's
exact `fix_mistral_regex=true` load kwarg, Transformers version, and Jinja
version. `plan` must measure the locked compiler path, full version, and binary hash inside the
exact grader image; host compiler identity is not admissible evidence.
Require the exact clean pinned SLIME checkout during `plan` and finalization.
Load its mask utility from `SLIME_ROOT` or `.cache/upstreams/slime` without
requiring SLIME on `PYTHONPATH`, and initialize it as a run-level preflight
before any task-scoped final screen.

Primary Aider SFT implementation must preserve the pinned source tasks' C++17
dialect, use a repo-owned C++17 CMake/Catch scaffold for LLM tasks, and reject
LLM-authored build commands. Compile the exercise target separately, discover
and run Catch without CTest/default-`ALL` ambiguity, and rerun the reference in
a fresh locked sanitizer build. Pass the explicit `Unix Makefiles` generator
and locked compiler to normal/sanitizer configure, enforce the fingerprinted
sandbox, and require separate positive sanitizer discovery with matching test
counts. Convert the Docker `fsize` limit from MiB to bytes; accept Catch v1
discovery status only when it is zero or exactly the parsed positive test
count. Reuse source terminal records only under the current admission
fingerprint so `--resume` reruns stale mechanical failures and historical
late rejections caused by run-level preflight errors, and report an empty pool
as structured `source_only_shortfall`. Store repeated Catch support once by digest;
exclude only allowlisted support/scaffold roles from semantic contamination.
Keep candidate admission separate from reviewed dataset split/release. A late
task-scoped render/token/contamination failure invalidates the frozen split and
returns to quota-preserving backfill before exact `dataset_release` approval.
Run-level profile/consumer preflight failures must leave admitted candidates
and the frozen split intact. Match benchmark IDs only as whole slugs, not as
hyphen-delimited substrings of valid source IDs. Bind renderer and final-screen
policy fingerprints into every late rejection so `--resume` retries preserved
evidence after a policy correction. Keep mutable
state/locks in the sibling `.state/` directory, make the ready root immutable,
use scope-specific decision fingerprints, and bind the token-record ledger and
release subject in schema-v2 readiness.
Rows are final-answer-only raw message lists. A thin repo-owned SLIME adapter
must forward the exact template kwargs (thinking disabled), apply explicit qwen
assistant loss, and persist/recompute per-row token/mask hashes and counts;
dataset-loader `--apply-chat-template` is forbidden. Export a private-asset-free
internal SLIME bundle with its token ledger. The producer runs full `verify`;
the GLM lane runs `verify-export` on only the sanitized bundle, pins exact
model/tokenizer/template/adapter identities, rejects token/mask/sequence drift,
and disables auto-prepare before training.

For an explicitly requested one-file Moonlight-style handoff, use the
repo-owned `data aider-sft export-minimal` projection. It must verify the ready
source, write only `train.jsonl` in a sibling output directory, preserve both
message contents exactly, and retain only the reference-compatible
`label`/`messages`/six-field `metadata`/`task_id` shape. Never write into or
change the immutable ready root, and never describe this reduced projection as
the provenance-bearing `slime-sft` bundle.

All source downloads, archive normalization, coverage measurement, task construction, SkyRL conversion, SLIME conversion, GCS upload, and GCS restore must be represented as `w8-biayn data ...` commands with tests and docs.

Build admitted PIE task JSON:

```bash
RUN_ID="r$(date -u +%Y%m%d%H%M%S)"
uv run w8-biayn data pie download --out .w8-biayn/data/pie
uv run w8-biayn data pie prepare-full --source-root .w8-biayn/data/pie --out .w8-biayn/data/pie-full --force
uv run w8-biayn data pie measure-coverage --prepared-root .w8-biayn/data/pie-full --out .w8-biayn/data/pie-full/coverage.json --report-out .w8-biayn/data/pie-full/coverage-report.json
uv run w8-biayn data pie build-full-tasks --prepared-root .w8-biayn/data/pie-full --coverage-json .w8-biayn/data/pie-full/coverage.json --out .w8-biayn/data/tasks-full --min-train 1000 --min-validation 100 --min-test 100 --force
uv run w8-biayn data skyrl build --tasks-dir .w8-biayn/data/tasks-full --out .w8-biayn/data/skyrl-full --profile full-official --run-id "$RUN_ID" --min-train-tasks 1000 --min-validation-tasks 100
# Optional explicit SLIME C++ lane; keep prompt-only JSONL plus task metadata for the SLIME reward hook.
uv run w8-biayn data slime build --tasks-dir .w8-biayn/data/tasks-full --out .w8-biayn/data/slime-pie --profile full-official --run-id "$RUN_ID" --min-train-tasks 1000 --min-validation-tasks 100
uv run w8-biayn data cache upload --path .w8-biayn/data/skyrl-full --gcs-prefix "gs://<project>-w8-biayn/datasets/cpp-perf/cpp-perf-v1/full-official/${RUN_ID}/skyrl" --credentials .gcp-service-account.json
```

Build active SLIME JSONL through lane wrappers:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_data.sh
bash examples/slime/glm47_cpp_perf/prepare_data.sh  # when the GLM lane is present
```

Admission gates:

- train tasks >= 1000;
- validation/test tasks >= 100;
- coverage >= 95 percent line and 85 percent branch;
- visible and hidden tests exist;
- reference performance exists.

Default schema version: `cpp-perf-v1`.

## Task Rules

Preserve PIE task discipline:

- `v0` slower C++ becomes the prompt.
- `v1` faster C++ is not shown during GRPO.
- `v1` may be used as SFT target, oracle/reference material, and coverage
  measurement input.
- Train/validation/test split stays by problem.
- A task requires visible tests, hidden tests, reference performance, and
  coverage passing 95 percent line / 85 percent branch.

The prompt may include visible tests and `v0`. It must not include hidden tests
or `v1`.

## Reward Rules

The reward is correctness gated:

- Invalid format is negative.
- Recoverable C++ with missing wrapper/fence format is shaped below the
  correctness-only fallback.
- Compile or sanitizer failure is negative.
- Timeout is negative.
- Partial tests remain below any fully correct answer.
- Fully correct answers with missing non-timeout runtime measurement get a
  correctness-only fallback below any measured fully correct answer.
- Fully correct answers get a base reward plus bounded runtime-efficiency.
- child-process CPU time in nanoseconds is the fast RL reward metric.
- Wall-clock nanoseconds are diagnostics.

Model outputs must contain exactly one `<reasoning>...</reasoning>` block
followed by exactly one fenced C++ code block. The code may start on the next
line or after whitespace on the opening C++ fence line; any second code block is
invalid.

The sandbox compiles the candidate and PIE `v1` oracle, runs all visible and
hidden tests, then benchmarks both binaries in the same Docker sandbox with the
same CPU pinning, compiler flags, and tests.

Do not add PMU, Linux perf, PERFMON, or `perf_event_paranoid` dependencies to
the active reward path.

## Training Rules

Active training runs through the repo-owned SLIME lane wrappers. Enter the
SLIME runtime through the generated `.w8-biayn/slime/run-container.sh`, not an
ad hoc `docker run`; the launcher owns the repo mount, docker socket, host
Docker CLI, model cache, and short shared `SLIME_HOST_TMPDIR` exported as
`TMPDIR`/`RAY_TMPDIR`
for nested Docker rewards and Ray.

Moonlight C++ lane:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_data.sh
bash examples/slime/moonlight_cpp_perf/eval_base.sh
bash examples/slime/moonlight_cpp_perf/sft.sh
bash examples/slime/moonlight_cpp_perf/eval_sft.sh
bash examples/slime/moonlight_cpp_perf/grpo.sh
bash examples/slime/moonlight_cpp_perf/eval_grpo.sh
bash examples/slime/moonlight_cpp_perf/compare.sh
```

Primary Aider-style SFT dataset generation is specified in
`docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`. The multi-task implementation
is in `src/w8_biayn/aider_sft/` and the repo-owned
`w8-biayn data aider-sft ...` CLI. It includes canonical tasks, image-bound
oracle admission, contamination/family checks, root-level split rollback and
release review, raw-message GLM adapter/token evidence, LLM-authoring
provenance, producer `verify`, sanitized `export`, and consumer
`verify-export`. The pilot profile remains draft and no ready 96-root dataset
is claimed. Existing one-task converters and graders remain seed surfaces, not
primary-pipeline evidence.

Optional Moonlight single-sample Aider `whole` format SFT smoke. This is a
compact Aider-like task-text-plus-starter-files check only, not PIE training
evidence. Build the one-row data with:

```bash
uv run python -m w8_biayn.integrations.moonlight_single_sample_sft \
  --out .w8-biayn/data/aider-whole-single
```

To convert the local Leap task folder itself into one-row SFT data, first create
the task and then build the SFT JSONL from its `.docs`, starter files, and
`.meta/example.*` reference files:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_task.sh --force
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_sft_data.sh --force
```

This writes `.w8-biayn/data/aider-leap-sft`; point `SLIME_CPP_DATA_DIR` there
for the SFT stage when training on the task-folder version.

Then run the existing non-LoRA `examples/slime/moonlight_cpp_perf/sft.sh` with
`SLIME_CPP_DATA_DIR` pointed at that directory and
`SLIME_CPP_AUTO_PREPARE_DATA=0`. Do not run `prepare_data.sh`, GRPO, GLM, or
the LoRA lane for this smoke.


For response-only inspection with no training, first create the local Leap task
with `examples/slime/moonlight_cpp_perf/prepare_leap_aider_task.sh --force`,
then use `examples/slime/moonlight_cpp_perf/probe_and_grade_aider_task.sh`
against an already running OpenAI-compatible model server and that task
directory. It builds the Aider-like prompt from `.docs` plus editable starter
files, saves `response.txt`, applies returned whole-file blocks to a clean copy,
runs CMake, and writes `grade/summary.json` plus configure/build logs.


Optional Moonlight Polyglot C++ base-eval benchmark. This is not active PIE
training and not an official Aider leaderboard run; it is a repo-owned
SLIME rollout-only eval of base Moonlight on C++ Exercism tasks. Keep detailed
setup, response contract, artifact fields, category summaries, blocking
`files.example` same-grader oracle preflight, schema-v2 incremental oracle
records, task/grader/image fingerprints, strict on-disk reconciliation, and
`recovered_*` diagnostics in `examples/slime/moonlight_polyglot_cpp/README.md`
instead of duplicating them
across repo-wide docs:

Keep `--rollout-skip-special-tokens` enabled in the launcher. Terminal
tokenizer markers such as `<|im_end|>` are a decoding concern; do not weaken
the strict whole-file parser to accept them as response content.

Historical Polyglot pass@k comparisons use the repo-owned `compare-runs`
command. It must derive a uniform sample count from records, require successful
receipts and passing embedded oracle proofs, recompute summaries, and match task
sets, immutable oracle fingerprints, and relevant run configuration before
writing local evidence. Keep the source fine-grained multi-label categories,
but use the six mutually-exclusive presentation groups documented in the lane
README for category bars. Include the admitted `files.example` answer in every
overall and category view as a 100%-passing same-grader setup reference, never
as a generated model series or official Aider score. Report empirical pass@k at
task level, model outcome distributions at sample level, and the oracle outcome
row as blocking setup preflights; recovered diagnostics never become passes.

Only intentional `eval_temperature` or `eval_top_p` differences may use the
field-specific `--allow-config-mismatch` override. Mark those reports
descriptive, persist every per-run value and mismatch, label series with the
sampling settings, and state that differences cannot be attributed to `k`
alone. Never extend this override to model, task, oracle, or grader identity.

The optional `gemini-sanity` command is limited to one admitted Polyglot task
and must reuse the exact saved prompt, raw API response, strict parser, and
Docker grader. Dry-run before spending; take `GOOGLE_API_KEY` or
`GEMINI_API_KEY` from the environment without persisting its value; pin an
exact model id; expose no oracle/tests; and label the result a cross-model
sanity check rather than pass@k or an official Aider comparison. Recovery is
diagnostic only. Preflight a host-writable artifact path before spending the
paid API request.

```bash
bash examples/slime/moonlight_polyglot_cpp/prepare_data.sh
bash examples/slime/moonlight_polyglot_cpp/eval_base.sh
```

Optional official Aider/Modal C++ base evaluation. This is not active PIE
training, not a SLIME lane, and not the repo-owned Moonlight Polyglot harness.
It runs base `zai-org/GLM-4.7-Flash` through Aider's exact edit/test/retry
benchmark on an ephemeral Modal App. The only entrypoint is export-only
`examples/modal/glm47_flash_aider_polyglot_cpp/run.sh`; plan is the default
and no-spend, while smoke/full require explicit acknowledgement and full always
runs the real two-task smoke first.

Keep Modal tokens local, optional `HF_TOKEN` downloader-only, and the random
SGLang bearer limited to the server and Aider runner. Pin exact model, Aider,
Polyglot, SGLang-image, Modal-SDK, settings, and strict `H100!:4` identities.
Use separate model/results Volumes, one server replica, `min_containers=0`,
bounded timeouts, explicit stop plus control-plane verification, and ignored
local artifacts. Preserve official Aider rows/histories/stats; `pass_rate_2`
is sequential second-try success, never pass@2. Source/offline completion is
not live evidence: do not report a model result before the two-task smoke and
complete 26-task stopped-App receipt.
Allow a 3600-second cold-start ceiling, poll the SGLang child process for early
exit, and persist/print only a bearer-redacted `server.failure.json` tail on
startup failure; raw SGLang output stays ephemeral.
Overlay the SGLang base with official Transformers commit
`76732b4e7120808ff989edbd16401f61fa6a0afa`, fail image construction unless
`glm4_moe_lite` is registered, and persist that identity in plans and
receipts.
Run stale-result admission on CPU before model loading or GPU startup. A
server restart may accept only the active run's identity-compatible config;
do not let the server freshness guard reject artifacts written by its own
benchmark runner.
Use up to 2048 configured completion tokens for the authenticated chat probe;
128 tokens can be consumed entirely by GLM reasoning. Admission diagnostics
may store only response keys, presence flags, lengths, finish reason, and
numeric usage, never generated reasoning or answer text.
Keep the Aider checkout at `/aider`, matching its absolute official C++ grader
path `/aider/benchmark/cpp-test.sh`, and build-check that executable contract.
On exception-only rows, print and persist only bearer-redacted task names,
exception types, and final traceback lines in `exception.summary.json`.
Set the Aider completion budget to 32768: a paid smoke showed that GLM can
spend all 8192 tokens reasoning without editable content, while the pinned
checkpoint has a 202752-position context. Admission-failure output may include
only safe per-task counters; download committed failure artifacts locally
before re-raising the remote exception.
Pinned Modal SDK 1.5.2's `App.server` path silently inherits the underlying
Function's 300-second execution timeout. Do not use it for this long-lived
SGLang endpoint: it recycles the four-H100 container approximately every five
minutes. Use `@app.function` plus `@modal.web_server` and set the explicit
execution timeout to startup timeout plus the complete runner timeout plus 600
seconds. Persist the derived value in plans and receipts. Keep static
`min_containers=0`, then dynamically hold exactly one replica with
`min_containers=1` after CPU/Volume admission and model-cache preparation.
Keep that active lease through all Aider work. On success or error, restore
`min_containers=0` with a two-second drain before transfer; explicit stop plus
control-plane verification remains mandatory. The 1200-second scaledown window
is an identity-bound fallback. The explicit lifetime and active lease are
operational, so compatible earlier artifacts may resume without an identity
mismatch.
Modal SDK 1.5.2 Volume entries expose an `IntEnum`; never classify them through
`str(entry.type)`. Download only `FileEntryType.FILE`, skip every non-regular
entry, and retain strict byte reconciliation. Validate the full entry list
before writing locally, then download with the SDK async API at a fixed
16-file concurrency bound. After the committed benchmark result returns,
lower the server scaledown window to two seconds before transfer so the H100s
do not remain allocated for artifact copying.


```bash
bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

The updated independent design uses exactly eight isolated trajectories per
task and up to two sequential Aider tries per trajectory. Report only
`pass@1_try1`, `pass@1_try2`, `pass@8_try1`, and `pass@8_try2`; try-2 success
is cumulative and may use feedback only from the same trajectory's try 1.
Require separate try-depth matrices, the frozen seed schedule, the extra paid
acknowledgement, a 2-by-8-by-try smoke, complete artifacts, and stopped-App
proof. Source and offline tests implement this contract; paid seed inspection,
the sampling smoke, and the complete stopped-App full receipt remain mandatory.
Paid acknowledgements are launch safety gates rather than immutable benchmark
identity and may change from false in plan mode to true for the first paid run.
Pin every sampling-smoke trajectory to `binary-search-tree` and `grade-school`
with Aider's comma-separated keyword filter. Store corrected evidence under
`sampling-smoke-v1`; preserve randomized legacy smoke artifacts as diagnostics
but never reuse them on resume.
Independent full requires `W8_MODAL_AIDER_MAX_RUN_SECONDS=14400`; a prior
7200-second run must get a fresh ID because timeout remains immutable identity.
Aider's `num_exhausted_context_windows` field counts provider
`finish_reason=length` output-limit events. Keep it diagnostic; never reject
otherwise complete non-exception rows with C++ test invocations solely because
that counter is nonzero.
Persist `runner.identity.json` before benchmark work and bind non-resume worker
re-entry to the same Modal App plus immutable config. Explicit independent
resume reuses only validated complete sample rows with stats, archives an
interrupted sample under `incomplete-attempts/`, and restarts only that sample
from the pinned tree and seed. Preserve the prior local failure download under
`resume-download-archives/` before exact resumed transfer. The active-server
lease is compatible with pre-lease artifacts. Generate offline visual reports
with `python -m w8_biayn.modal_aider_visualization`; it reads only local
evidence, supports explicit partial-prefix diagnostics, and writes under
`reports/<run-id>/` instead of the canonical run tree. Keep its stable
six-group topic taxonomy (3-6 tasks per group) and balanced 8/9/9
Easy/Medium/Hard task-complexity taxonomy distinct from model-derived outcome
rates.

Optional Moonlight Multi-SWE C++ base-eval benchmark. This is not active PIE
training and not an official Multi-SWE leaderboard run; it is a repo-owned
SLIME rollout-only eval of base Moonlight on C++ issue-resolution tasks from
`ByteDance-Seed/Multi-SWE-bench_mini`. Preparation is a blocking admission
gate: select the official lowercase per-instance `mswebench` image, pin its
immutable identity, and grade in its exact prepared checkout/build/test assets
without per-task GitHub clones. Run every dataset `fix_patch`, require a
positive CTest count, persist after each task, and reuse only
fingerprint-matching passing records on resume. The proof lives in `data/oracle.records.jsonl`,
`data/oracle.summary.json`, `data/sandbox-images.json`, and the schema-v3
manifest; aggregation copies it into `eval/base.oracle.records.jsonl` plus
`oracle_setup_check` in `eval/base.summary.json`. Keep detailed setup, response
contract, artifact fields, repo summaries, oracle proof, and `recovered_*`
diagnostics in `examples/slime/moonlight_multi_swe_cpp/README.md` instead of
duplicating them across repo-wide docs. For simdjson PRs 958, 1615, 1712, and
2016, preparation must populate the checksum-pinned data-local
`cxxopts`/simdjson-data cache and the grader must mount it read-only while
retaining `--network none`. PR 958 must propagate only
`-Wno-error=effc++` from the external cxxopts target after simdjson's
target-level `-Werror`, use an external-header wrapper that keeps the full
`-Weffc++` group visible but non-fatal, and remove only the network-dependent
checkperf include; do not disable
warnings-as-errors or the ordinary benchmark/test build globally. Nlohmann PR
2099 must run the dataset's other 49 CTests plus the PR-relevant `CBOR` and
`MessagePack` doctest cases explicitly, excluding only their unrelated
historical roundtrip fixture cases:

Keep `--rollout-skip-special-tokens` enabled in the launcher. Terminal
tokenizer markers such as `<|im_end|>` are a decoding concern; do not weaken
the strict single-diff parser to accept them as response content.

```bash
bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh
```

Moonlight rank-16 LoRA C++ lane:

```bash
bash examples/slime/moonlight_lora_cpp_perf/prepare_data.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_base.sh
bash examples/slime/moonlight_lora_cpp_perf/sft.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_sft.sh
bash examples/slime/moonlight_lora_cpp_perf/grpo.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_grpo.sh
bash examples/slime/moonlight_lora_cpp_perf/compare.sh
```

GLM C++ lane when present:

```bash
bash examples/slime/glm47_cpp_perf/prepare_data.sh
bash examples/slime/glm47_cpp_perf/eval_base.sh
bash examples/slime/glm47_cpp_perf/sft.sh
bash examples/slime/glm47_cpp_perf/eval_sft.sh
bash examples/slime/glm47_cpp_perf/grpo.sh
bash examples/slime/glm47_cpp_perf/eval_grpo.sh
bash examples/slime/glm47_cpp_perf/compare.sh
```

GLM agentic SWE-agent file-state lane. SWE-agent (not claude-code) edits
`candidate.cpp` over many turns; the final FILE is graded in the repo's Docker
sandbox (not E2B) and the correctness-gated reward flows via the OpenAI adapter
`finish_session` (no `--custom-rm-path`). SFT stays single-turn; base/sft/grpo
evals and GRPO are agentic. Lane invariants (each cost a paid smoke): swerex
LocalDeployment shares one filesystem across episodes and stages, so the driver
patches its non-idempotent `upload`, uses unique per-attempt repo basenames,
and cleans the root-FS copy; HF-export gates require real weight shards (an
index without shards hangs SGLang); every trainer-reaching sample — abort husks
included — must carry `metadata.round_number` or slime's `--log-multi-turn`
KeyErrors:

```bash
bash examples/slime/glm47_swe_agent_cpp_perf/prepare_data.sh
bash examples/slime/glm47_swe_agent_cpp_perf/eval_base.sh
bash examples/slime/glm47_swe_agent_cpp_perf/sft.sh
bash examples/slime/glm47_swe_agent_cpp_perf/eval_sft.sh
bash examples/slime/glm47_swe_agent_cpp_perf/grpo.sh
bash examples/slime/glm47_swe_agent_cpp_perf/eval_grpo.sh
bash examples/slime/glm47_swe_agent_cpp_perf/compare.sh
```

W&B is the primary observability surface; local receipts (`run.log`,
`run_receipt.txt`, `vram_usage.csv`, `vram_peak.txt`, debug rollout dumps, eval
summaries under `.w8-biayn/slime/...`) remain the on-disk source of truth. The
contract lives in `src/w8_biayn/wandb_report.py` and the README Observability
section: one launch = one group (= run id) with deterministic per-stage run
ids/names; SLIME logs `train/*`/`rollout/*` natively; the agentic generate hook
logs live `rollout_health/*` (abort reasons, zero-variance group fraction,
correctness-gate rates) into the same stage run; the offline scorer publishes
`eval/*` + per-task tables onto the stage's own run; uplift and launch outcome
land on `<run-id>-pipeline`; failures fire `wandb.alert`. Debug detail rides as
queryable tables: dataset composition (`publish-dataset`), per-stage GPU memory
(`publish-vram`), the SkyPilot lifecycle (`pipeline/launch_events`), and live
token capture (`rollout_health/trained_tokens_*`). Push the curated
saved view with `uv run --extra cloud w8-biayn wandb workspace`. GRPO group
size must stay >= 2 (`--grpo-n-samples-per-prompt`, default 8; a group of one
zeroes every group-relative advantage), with the global batch derived as
rollout_batch_size * n_samples_per_prompt unless explicitly overridden.

The paid GCP GLM full
launch is `uv run --extra cloud w8-biayn launch glm47-full` (implementation
`src/w8_biayn/cloud_launch.py`; the old
`examples/slime/glm47_cpp_perf/launch_gcp_h100_full.py` is a thin shim). Keep
it a provisioning wrapper around the repo-owned GLM SLIME lane, with dry-run
rendering, scoped secrets, downloaded local artifacts, labels, spot support via
`--use-spot`, and automatic teardown. SkyPilot manages the cloud hardware only;
all training runs through SLIME inside the lane container. SkyPilot is pinned
in `w8_biayn.constants.SKYPILOT_PIN` (installed through the `cloud` extra) and
the launch must wait for a terminal job state after `sky.launch` (API-server
builds resolve the launch request at job submission, not completion).

For Moonlight local attention/RMSNorm compatibility, keep the `src/local.py`
Megatron layer-spec shim in sync with lane defaults.

## Legacy Surface

The legacy SkyRL/rLLM/GCP control-plane modules (SkyRL dataset conversion,
SkyPilot renderers, GRPO readiness and run-status tooling, MLflow metric
readers, the SkyRL integration patches, and their tests) were removed from
this branch. They remain available in git history. The CLI keeps thin shims
(for example `data skyrl build`) that fail with a clear legacy-unavailable
message instead of importing the removed modules; do not extend those shims
for new training work.

Do not resurrect legacy modules unless the user explicitly asks for a rollback
or a legacy compatibility task. If a file is generated evidence rather than
source, untrack it with `git rm --cached` and ignore future copies instead of
deleting the working-tree file.

## Cloud Rules

The cloud architecture is fixed: SkyPilot manages the cloud hardware
(provision, sync, artifact download, teardown) and SLIME runs the training on
that hardware. Any cloud helper must:

- support dry-run rendering before paid launches;
- use `.gcp-service-account.json` through scoped env vars;
- avoid `gcloud auth activate-service-account`;
- avoid mutating global `gcloud config`;
- avoid printing credential contents;
- pin the SkyPilot client version it invokes and treat `sky.launch` as
  submission-only, waiting for a terminal job state before any teardown;
- preflight network reachability before spending and watchdog it for the whole
  launch (`net_degraded`/`net_recovered` launch events via
  `w8_biayn.net_health`; manual probe `w8-biayn ops net-check`), and treat a
  vanished cluster as terminal (`CLUSTER_LOST` re-enters the provisioning
  retry loop; never ghost-poll a preempted box);
- arm a cluster-side autostop-down (`idle_minutes_to_autostop` with
  `down=True`) so a killed launcher process cannot orphan a paid box; the
  manual reaper `w8-biayn ops down-run <run-id> --execute` stays the last
  resort;
- label paid resources with project, phase, pipeline, run id, owner, and TTL
  when resources are created;
- stamp the launch outcome, redacted config, and a GCS checkpoint reference
  artifact on the `<run-id>-pipeline` W&B run, and alert on failure.

Do not infer paid-resource count from local SkyPilot executor processes. Use
explicit provider/status commands for actual resource accounting.

## Repository Map

```text
docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md
                                             primary Aider-style SFT dataset implementation contract
configs/aider_sft/pilot-v1.toml              strict draft primary-SFT profile
manifests/aider_sft/                         benchmark/support manifests; source manifest after review
src/w8_biayn/aider_sft/                      primary Aider-style SFT implementation
tests/test_aider_sft_pipeline.py             no-spend primary-SFT regression coverage
scripts/bootstrap.sh                         fresh-machine bootstrap
scripts/prepare_dapo_math_dataset.py         optional SLIME text-smoke data prep
scripts/wandb_milestone.py                   standalone pipeline-milestone logger (elapsed curve + timeline table)
examples/slime/moonlight_cpp_perf/           active Moonlight C++ lane
examples/slime/moonlight_lora_cpp_perf/      rank-16 LoRA Moonlight C++ lane
examples/slime/moonlight_polyglot_cpp/       optional Moonlight base eval on Aider Polyglot C++
examples/modal/glm47_flash_aider_polyglot_cpp/
                                             official Aider C++ base eval on Modal
src/w8_biayn/modal_aider_polyglot_cpp.py     pure config/receipt/artifact contract (no Modal import)
tests/test_modal_aider_polyglot_cpp.py       offline Modal/Aider safety and command contract
examples/slime/moonlight_multi_swe_cpp/      optional Moonlight base eval on Multi-SWE C++
examples/slime/glm47_cpp_perf/               active GLM C++ lane when present
examples/slime/glm47_swe_agent_cpp_perf/     agentic SWE-agent file-state C++ lane
examples/slime/retool/                       Moonlight ReTool lane
examples/slime/moonlight_moe_smoke/          light Moonlight MoE smoke
examples/slime/multi_agent/                  generic text-only SLIME smoke
src/local.py                                 Moonlight Megatron local-layer shim
src/w8_biayn/cloud_launch.py                 SkyPilot-backed paid GLM launch (w8-biayn launch glm47-full)
src/w8_biayn/wandb_report.py                 W&B data->surface contract (eval/health metrics, tables, artifacts, alerts, workspace template)
src/w8_biayn/net_health.py                   reachability probes, launch preflight, net watchdog (ops net-check)
tests/test_regression_lints.py               one guard per bug the GPU smoke campaign paid to find
src/w8_biayn/cpp_perf/                       PIE task, prompt, sandbox, reward, eval code
src/w8_biayn/slime_integration/              SLIME doctor/setup/sandbox helpers
src/w8_biayn/integrations/slime_cpp_perf.py  SLIME C++ data/reward/eval bridge
src/w8_biayn/integrations/slime_polyglot_cpp.py
                                             SLIME Polyglot C++ data/reward/eval bridge
src/w8_biayn/integrations/slime_multi_swe_cpp.py
                                             SLIME Multi-SWE C++ data/reward/eval bridge
src/w8_biayn/integrations/slime_swe_agent_cpp_perf.py
                                             agentic SWE-agent generate() hook (file-state reward)
src/w8_biayn/integrations/swe_agent_driver.py
                                             single-instance SWE-agent run + candidate.cpp extraction
src/w8_biayn/integrations/slime_train_entry.py
                                             repo-owned SLIME train entry wrapper
src/w8_biayn/integrations/slime_moonlight_hf_export.py
                                             Moonlight Megatron-to-HF export shim
```

## Documentation Rules

When commands, setup, dataset shape, cache behavior, task schema, reward logic,
launch flow, benchmark protocol, or supported active pipelines change, update:

1. `README.md`
2. `ROADMAP.md`
3. this file
4. `.agents/skills/w8-biayn-framework/SKILL.md`
5. `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md` when its SFT pipeline
   contract is affected
6. tests when command behavior changes

Do not commit generated `RUN_REPORT*` files, report asset directories, checkpoints,
model exports, PIE data, CodeNet data, SuperCoder data, gem5 outputs, logs, or
credentials.

## Validation

Before handing off:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/w8-biayn-framework
```

For setup or CLI-surface changes:

```bash
./scripts/bootstrap.sh --no-sky
uv run w8-biayn --help
uv run w8-biayn data doctor
uv run w8-biayn slime doctor
uv run w8-biayn slime setup --force
uv run w8-biayn cpp harness preflight --dry-run
```


## Optional GLM Multi-SWE Modal Lane

The repo-owned single-turn GLM Multi-SWE C++ Modal implementation lives at
examples/modal/glm47_flash_multi_swe_cpp/, with pure contracts in
src/w8_biayn/modal_glm47.py, src/w8_biayn/modal_multi_swe_cpp.py, and
src/w8_biayn/modal_multi_swe_runtime.py. Its only entrypoint is run.sh; plan is
no-spend by default and paid phases require explicit acknowledgement.

Keep this lane separate from SLIME, PIE training, the Moonlight Multi-SWE lane,
and official leaderboard claims. It fixes the dataset revision and reviewed
50-image linux/amd64 lock, runs all fix_patch oracles before model loading,
uses one secret-free network-blocked Modal Sandbox per patch, and releases the
one strict H100!:4 SGLang replica before artifact transfer. Only
message.content enters the existing strict parser. Sandboxes must receive no
credentials/model/results Volumes, must stage affected simdjson dependencies
under one checksum-pinned parent, mount that data-Volume subpath once read-only
at a fresh /mnt path, and must terminate with wait plus detach in finally.
Modal SDK 1.5.2 rejects both mounting the same Volume object at multiple
Sandbox paths and mounting over the official image's non-empty dependency
directory. After patch preflight, trusted shell setup may replace only the two
expected dependency locations with symlinks into the detached mount before
tests. Source-only resume migration is allowed solely before any model/server
artifact exists; passing oracle reuse remains exact-cache-key only and is
audit-recorded. Parse CTest discovery from complete in-memory stdout/stderr
before persistence truncation, store the numeric count and per-stream
hashes/sizes, and retain bounded tails from both streams. Large non-fatal
compiler stderr must not hide the stdout test summary or weaken the
positive-test gate.
Keep the Server at min_containers=0 and poll external health through Modal's
zero-to-one HTTP 503 window before models/chat admission. Bound every stage,
retry only the checked-in transient statuses, and persist HTTP status/body
size/hash/truncation/JSON keys without body text. Source-only migration may
cross preparation and admission-failure artifacts with exact oracle/model
identities, but successful admission or any benchmark-stage artifact restores
strict identity.
Keep the dataset image lock off the GPU server image. Modal Server hydration
must tolerate that control-only environment variable being absent, while local
orchestration must require the reviewed lock before preflight, dataset/oracle,
or paid work. A fresh full run may name a completed source run for oracle-proof
import. Require local and remote artifact-manifest reconciliation, stopped-App
proof, the exact image lock and task set, and all 50 current cache-key matches;
persist import lineage and fail without oracle execution fallback on any
mismatch. Never import source model responses or mutate the completed run.

Source and offline tests are implemented; the fixed paid smoke is clean and
full paid validation remains pending.
Never print or document a score until 50 responses/records, passing oracle
proof, artifact reconciliation, and control-plane verified stopped-App evidence
are complete.

## Optional Agentic GLM Multi-SWE Modal Lane

The separately named multi-turn lane lives at
examples/modal/glm47_flash_agentic_multi_swe_cpp/, with offline contracts in
src/w8_biayn/modal_agentic_multi_swe_cpp.py,
src/w8_biayn/modal_agentic_multi_swe_runtime.py, and
src/w8_biayn/integrations/modal_swe_agent_driver.py. Its only entrypoint is
run.sh. Plan is no-spend; smoke/full require the paid acknowledgement and full
also requires the long-GPU-lease acknowledgement. Keep run IDs to 3-40
lowercase letters, digits, or hyphens; this admits the documented timestamp
forms and keeps the derived Modal App name at most 62 characters.

Keep this lane distinct from the single-turn Modal lane, SLIME, PIE training,
Aider, and official leaderboard claims. Preserve exactly one bounded,
deterministic SWE-agent trajectory per task; the fixed SWE-agent commit and
dependency lock; all-50 oracle and workspace admission before GPU startup; and
one H100!:4 active lease only while trajectories need the model.

Agent Sandboxes must use the exact official task image with blocked network,
no Secrets, no Volumes, and the unprivileged w8agent user. Trusted root code
must verify and sanitize the base checkout, remove original history and hidden
assets, preserve and receipt-bind exact empty uninitialized gitlink directories,
require populated submodules to match their indexed commits, own the baseline
and canaries, stop the agent, reject unsafe or
oversized final trees, synthesize the final diff, apply the existing forbidden
path policy, and prove the patch against a second pristine reconstruction.
Use the exact image's default C++ mode for the workspace compile/output canary
because reviewed legacy images may reject C++20 flags; do not change task
grader commands. Never persist raw model reasoning or the upstream raw
trajectory.

Persist each completed step incrementally through the pinned hook, but only as
request/response hashes, actions, bounded observations, numeric usage, and
bounded tool receipts. Full must repeat the fixed smoke, lower the server for
smoke grading, re-acquire and re-admit it, then run all 50. Require each complete
patch/outcome set before lowering the server to zero and draining it. Grade only
afterward in separate fresh official-image Sandboxes, using the existing narrow
simdjson mount where required. Resume may reuse only complete
identity-compatible task units; restart an interrupted unit once from pristine
state and archive only safe failure diagnostics.

Source and offline tests are implemented; paid CPU canaries, SGLang admission,
one trajectory, fixed smoke, and full evidence remain pending. Never print or
document a score before 50 complete trajectories/records, exact passing oracle
and workspace proofs, byte reconciliation, and a control-plane-verified
stopped-App receipt. Keep detailed commands, budgets, schemas, artifacts, and
reporting gates in the lane README.
