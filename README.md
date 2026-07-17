# w8-biayn

`w8-biayn` is the command-and-control repository for C++ performance RL. The
current active work is SLIME-based training for Moonlight and GLM models on PIE
C++ optimization tasks.

The training target is narrow:

```text
correct but slower C++20 program -> correct and faster C++20 program
```

Correctness is mandatory. Runtime improvement only matters after the generated
program preserves behavior on visible and hidden tests.

## Active Goal

- Data: official PIE C++ slower-to-faster pairs plus official, merged, and
  generated tests.
- Task: prompt with slower PIE `v0`; generate a complete optimized C++20
  program.
- Reward: strict response format, compile and sanitizer success, visible and
  hidden tests, then bounded child-process CPU-time efficiency.
- Training: SLIME with Megatron training and SGLang rollouts. Active model
  lanes are Moonlight and GLM.
- Proof: compare base, SFT, and GRPO outputs on the same held-out PIE tasks
  with pass rate, correct-and-faster rate, mean reward, speedup, and
  missing-runtime rate.

SkyRL/rLLM, SkyPilot renderers, MLflow run-status parsing, and older GCP
training commands were removed from this branch. They remain available in git
history, and the CLI keeps only thin legacy shims (for example
`data skyrl build`) that fail with a clear legacy-unavailable message. Do not
use them for new active training work unless a task explicitly asks for legacy
maintenance.

Out of scope unless a later phase explicitly asks for it: BrowserGym, DOMDiff,
Harbor, WebArena, MiniWoB, AndroidWorld, Go, custom GPU kernel labs, and
unrelated performance experiments.

## Boundaries And Artifact Hygiene

Do not write a custom trainer. Use SLIME, Megatron, and SGLang for active
training work. Do not reintroduce SkyRL/rLLM as the active training stack unless
the user explicitly asks for legacy maintenance or rollback.

Do not delete local evidence files just because they are no longer tracked. If a
generated artifact is in git, use `git rm --cached` so the working-tree file
remains available, then ignore future generated copies. Generated `RUN_REPORT*`
files and report asset directories should not be committed.

## Current SLIME Lanes

Use repo-owned wrappers rather than editing `.cache/upstreams/slime` directly.

- Moonlight C++ performance lane: `examples/slime/moonlight_cpp_perf/`
- Moonlight Polyglot C++ base-eval lane: `examples/slime/moonlight_polyglot_cpp/`
- Moonlight Multi-SWE C++ base-eval lane: `examples/slime/moonlight_multi_swe_cpp/`
- Moonlight rank-16 LoRA C++ performance lane: `examples/slime/moonlight_lora_cpp_perf/`
- GLM C++ performance lane: `examples/slime/glm47_cpp_perf/`
- GLM agentic SWE-agent C++ lane (multi-turn, file-state scored): `examples/slime/glm47_swe_agent_cpp_perf/`
- Moonlight ReTool lane: `examples/slime/retool/`
- Moonlight MoE smoke: `examples/slime/moonlight_moe_smoke/`
- Generic text-only SLIME smoke: `examples/slime/multi_agent/`

The separate official Aider/Modal base-eval surface is
`examples/modal/glm47_flash_aider_polyglot_cpp/`; it is not a SLIME lane or
part of the active PIE training stack.
Its SGLang cold-start gate allows up to 3600 seconds, polls the server child
process, and persists only a bearer-redacted `server.failure.json` tail when
startup fails; raw server output stays ephemeral.
The server image overlays the official pinned Transformers commit
`76732b4e7120808ff989edbd16401f61fa6a0afa` and build-checks
`glm4_moe_lite` before any GPU allocation.
A CPU-only results-Volume preflight rejects stale run IDs before model loading
or GPU startup. Once admitted, a restarted server container accepts only its
own identity-compatible config instead of rejecting artifacts written by the
live benchmark runner.
The authenticated chat admission probe uses up to 2048 of the configured
completion tokens so GLM reasoning cannot consume the old 128-token allowance
before producing editable content. It persists only response keys, field
presence, character counts, finish reason, and numeric usage; generated
reasoning and answer text are never stored in admission diagnostics.
The Aider checkout stays at upstream's `/aider` container path because the
pinned benchmark invokes `/aider/benchmark/cpp-test.sh` absolutely. Runner
image construction verifies that executable path. Exception-only rows emit a
bearer-redacted task/type/final-line summary instead of only an aggregate
count. GLM reasoning can consume an 8192-token completion without reaching
editable content, so the admitted Aider request budget is 32768 tokens within
the pinned model's 202752-position context. Failed admission summaries include
only per-task counters, and committed failure artifacts are downloaded locally
before the original remote exception is re-raised.
The singleton SGLang endpoint uses Modal's public timeout-capable
`@app.function` plus `@modal.web_server` path. Pinned Modal SDK 1.5.2's
`App.server` hides an internal 300-second Function execution timeout, which
otherwise recycles the four-H100 container about every five minutes. The
explicit server lifetime is cold-start timeout plus the complete runner timeout
plus 600 seconds of teardown slack (18600 seconds for independent full), and is
recorded in plans and receipts. The definition retains static
`min_containers=0`; after CPU/Volume admission and model-cache preparation,
the launcher dynamically holds exactly one replica with `min_containers=1`
for the entire benchmark. On success or error it returns to
`min_containers=0` with a two-second drain before artifact transfer, then
explicitly stops and verifies the App. The 1200-second scaledown window remains
a fallback. These operational lifecycle safeguards are resume-compatible
because they do not change model requests.
Artifact download uses Modal SDK 1.5.2's explicit `FileEntryType.FILE`; it
skips directories and every other non-regular entry before byte reads while
retaining byte-for-byte reconciliation for downloaded files. The client first
validates the complete entry list, then downloads regular files through the
SDK's async API with at most 16 reads in flight and periodic progress output.
After the remote benchmark result is durable, it reduces the server scaledown
window to two seconds so the four H100s can exit during local artifact transfer.


The Moonlight and GLM C++ lanes reuse the project PIE task schema, prompt
builder, Docker C++ sandbox, reward function, and eval aggregation through
`src/w8_biayn/integrations/slime_cpp_perf.py`.

The Moonlight Polyglot C++ lane is an optional rollout-only base-eval benchmark
for the C++ subset of `Aider-AI/polyglot-benchmark`. It uses
`src/w8_biayn/integrations/slime_polyglot_cpp.py` for whole-file replacement
prompts and Exercism C++ tests in Docker. Data preparation must first map the
upstream `files.example` references onto solution files and pass them through
the same Docker grader. Schema-v2 records are flushed per task and bind the
copied exercise plus grader configuration to the immutable Docker image ID;
`verify-data` recomputes the summary and cross-checks records, eval rows,
fingerprints, mappings, and counts. Only that all-passing proof admits the eval
manifest. It is not part of the PIE training proof and is not an official
Aider leaderboard run; keep detailed setup and artifact semantics in
`examples/slime/moonlight_polyglot_cpp/README.md`.
Its base-eval launcher enables SLIME special-token skipping so terminal
tokenizer markers such as `<|im_end|>` do not become false prose outside the
required whole-file response blocks; the strict parser itself is not relaxed.

The Moonlight Multi-SWE C++ lane is an optional rollout-only base-eval
benchmark for the C++ subset of `ByteDance-Seed/Multi-SWE-bench_mini`. It uses
`src/w8_biayn/integrations/slime_multi_swe_cpp.py` for single-patch prompts,
forbidden-path preflight, dataset `test_patch` application, and
repo-specific C++ tests in Docker. Data preparation is blocking: it selects
the official lowercase per-instance `mswebench` image, pins its immutable
identity, and grades directly in that image's exact checkout, prepared build
tree, and offline test assets. It runs every dataset `fix_patch`, requires
CTest to report a positive test count, persists proof after each task, and
resumes only fingerprint-matching passes before admitting the manifest. It is not part of the PIE
training proof, does not report speed metrics, and is not an official Multi-SWE
leaderboard run; keep detailed setup and artifact semantics in
`examples/slime/moonlight_multi_swe_cpp/README.md`.
Its base-eval launcher likewise enables SLIME special-token skipping before
the strict single-diff parser; existing saved artifacts require a fresh eval
and are not retroactively normalized.

The four historical simdjson images whose CMake files otherwise download
Google Benchmark or an uninitialized submodule use a data-local, SHA-256-pinned
`cxxopts`/simdjson-data cache prepared outside the grader and mounted
read-only; the grading container remains network-disabled.
PR 958 also keeps GCC 7's external-cxxopts `-Weffc++` diagnostics visible but
non-fatal while preserving all other warning-as-error checks and the full test
build: the compatibility flag propagates from the cxxopts interface after
simdjson's `-Werror`, an ephemeral wrapper demotes the full `-Weffc++` group
while keeping its diagnostics visible, and only the network-dependent checkperf
include is removed from the checkout. For nlohmann PR 2099, the image's two opt-in roundtrip cases have
known float-serialization fixture mismatches unrelated to the PR. Admission
runs the dataset's other 49 CTests plus the PR-relevant `CBOR` and `MessagePack`
doctest cases explicitly, rather than dropping those changed test executables.

The GLM agentic SWE-agent lane grades the final edited FILE instead of model
text: SWE-agent edits `candidate.cpp` over many turns, the hardened Docker
grader scores the file it leaves behind (compile + visible and hidden tests +
child-process CPU time), and reward flows through SLIME's OpenAI adapter
`finish_session`. This dissolves the GLM thinking-mode truncation that made
single-turn responses unscoreable. It uses SWE-agent (not claude-code) and the
repo's Docker grader (not E2B), via
`src/w8_biayn/integrations/slime_swe_agent_cpp_perf.py` (the `generate` hook)
and `src/w8_biayn/integrations/swe_agent_driver.py`. SWE-agent runs its
edit/bash loop in-process on the rollout worker through swerex `LocalDeployment`
(`{"type": "local"}`) — no sibling execution container and no `--network host`
(which collided with Ray) — and each concurrent rollout copies the repo to a
unique basename so the drivers do not fight over one working tree. Only the
final-file grading crosses back into the hardened Docker sandbox.

**Status: the pipeline is proven END-TO-END.** Run `w8swe-20260707091714`
completed all seven stages in 78 minutes on an A100-80GB:8 spot box —
base-eval → SFT → sft-eval → **GRPO with a clean weight update** → grpo-eval →
compare — with the verdict on the live panels: `train/ppo_kl` finite,
`grad_norm` 5.6, `zero_variance_group_fraction` 0, `trained_tokens_mean` 161,
1/16 aborts, 87.5% eval pass across all three model stages, and the run's
checkpoints + HF exports fully persisted to GCS (resumable). The
eight-smoke campaign that got here converted every failure into a committed
fix and a regression lint (`tests/test_regression_lints.py`, one guard per
paid incident); the load-bearing lessons:

- **swerex LocalDeployment shares one filesystem across every episode and
  stage.** Its `upload` is a bare `shutil.copytree` (no `dirs_exist_ok`), and
  SWE-agent uploads tool bundles to the fixed path `/root/tools/{bundle}` —
  so episode 2+ died with `FileExistsError` before the first model call. The
  driver monkeypatches the upload to be idempotent, gives each attempt a
  unique repo basename, and removes the root-FS copy afterward.
- **HF-export gates must demand real weight shards.** A GCS persist that fails
  partway leaves `config.json` + `model.safetensors.index.json` without
  shards; the old existence gate accepted that and SGLang hung ~85 min on a
  weightless model. Gates now require `*.safetensors`/`*.bin`, restores prune
  weightless exports, and the persist rsync is loud with a retry.
- **Every sample that reaches the trainer must carry
  `metadata.round_number`** — slime's `--log-multi-turn` does a direct dict
  access, and abort husks do reach the trainer (also the mechanism behind the
  original all-abort NaN). Success and abort paths both stamp it.
- **GRPO needs exactly one trainable sample per episode.** GLM's chat template
  strips `<think>` from history, so turns re-tokenize past the adapter's fork
  threshold and a 3-turn episode drained 3 samples (48 rewards where the
  `(prompts × n_samples)` reshape expected 16). The lane raises the merge
  threshold and the hook keeps the fork with the most trained tokens,
  reporting drops as `rollout_health/fork_samples_dropped_mean`.
- **Spot preemption is a delay, not a hang.** A vanished cluster returns
  `CLUSTER_LOST` into the provisioning retry loop (it once ghost-polled for
  two hours); network reachability is preflighted before any spend and
  watchdogged throughout (`net_degraded`/`net_recovered` launch events,
  `w8-biayn ops net-check` for the manual probe).
- Earlier fixes hold: Ray vs `--network host` (dissolved by LocalDeployment),
  `tokenizers` pinned via frozen-env `--constraint`, group size
  `--grpo-n-samples-per-prompt` (default 8; 1 zeroes every group-relative
  advantage), sid carried in the request body besides the bearer, pinned
  upstream fetches skipped when the commit is already local.

Open before a full run: the fork-merge threshold did not actually prevent
3-way episode forks (the keep-best guard preserved group math but discards
~2/3 of captured tokens — investigate adapter REALIGN vs GLM think-stripping),
plus the pre-existing full-run gates (thinking budget, PIE admission
coverage, model/torch_dist GCS cache).

## Fresh Machine Setup

Run from a clean clone:

```bash
./scripts/bootstrap.sh
uv run w8-biayn data doctor
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime doctor
uv run w8-biayn slime setup
uv run w8-biayn cpp harness preflight --dry-run
```

Generated data, upstream clones, rendered launchers, secrets, logs,
checkpoints, model exports, run reports, and evaluation artifacts are local
state and must stay out of git.

If cloud/GCS helpers are used for a specific run, keep credentials local at
`.gcp-service-account.json`; never print credential contents or mutate global
`gcloud` configuration.

## PIE Data Workflow

Dataset conversion is a deliverable. Do not use one-off notebooks, shell
history, or untracked munging for PIE data.

Build admitted PIE task JSON:

```bash
RUN_ID="r$(date -u +%Y%m%d%H%M%S)"

uv run w8-biayn data pie download --out .w8-biayn/data/pie
uv run w8-biayn data pie prepare-full \
  --source-root .w8-biayn/data/pie \
  --out .w8-biayn/data/pie-full \
  --force

uv run w8-biayn data pie measure-coverage \
  --prepared-root .w8-biayn/data/pie-full \
  --out .w8-biayn/data/pie-full/coverage.json \
  --report-out .w8-biayn/data/pie-full/coverage-report.json

uv run w8-biayn data pie build-full-tasks \
  --prepared-root .w8-biayn/data/pie-full \
  --coverage-json .w8-biayn/data/pie-full/coverage.json \
  --out .w8-biayn/data/tasks-full \
  --min-train 1000 \
  --min-validation 100 \
  --min-test 100 \
  --force
```

Admission gates:

- train tasks >= 1000;
- validation/test tasks >= 100;
- coverage >= 95 percent line and 85 percent branch;
- visible and hidden tests exist;
- reference performance exists;
- train/validation/test split stays by problem.

Build SLIME-ready JSONL from the admitted task JSON with the lane wrapper:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_data.sh
```

For the GLM lane, use the matching wrapper under
`examples/slime/glm47_cpp_perf/` when that lane is present in the workspace.

## Task And Reward Contract

A valid task contains:

- `prompt_code`: slower correct PIE C++ `v0`;
- `oracle_solution`: faster PIE C++ `v1`, used for SFT, coverage, reference
  timing, and oracle material only;
- visible `unit_tests` and grading-only `hidden_tests`;
- `test_coverage` at or above 95 percent line and 85 percent branch;
- positive reference performance metadata;
- split `train`, `validation`, or `test`.

During GRPO, the prompt may include visible tests and `v0`. It must not include
hidden tests or `v1`.

Model outputs must contain exactly:

````text
<reasoning>...</reasoning>
```cpp
// complete optimized C++20 program
```
````

Reward order:

- unrecoverable invalid format: negative;
- recoverable C++ with missing wrapper/fence format: shaped below the
  correctness-only fallback;
- compile or sanitizer failure: negative;
- timeout: negative;
- partial tests: below any fully correct answer;
- fully correct with missing non-timeout runtime measurement: correctness-only
  fallback below any measured fully correct answer;
- fully correct: base reward plus bounded runtime-efficiency bonus.

The sandbox compiles the candidate and PIE `v1` oracle, runs all visible and
hidden tests, then benchmarks both binaries in the same Docker sandbox with the
same CPU pinning, compiler flags, and tests. Runtime reward uses
child-process CPU time in nanoseconds. Wall-clock nanoseconds are diagnostics.

Do not add PMU, Linux perf, PERFMON, or `perf_event_paranoid` dependencies to
the active reward path.

## SLIME Setup

Clone or refresh the pinned SLIME checkout:

```bash
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime doctor
```

Generate the Docker-first launcher and in-container bootstrap helper:

```bash
uv run w8-biayn slime setup
.w8-biayn/slime/run-container.sh
```

The generated launcher starts the SLIME container with this repository mounted,
mounts `/var/run/docker.sock` plus the host Docker CLI (override path with
`SLIME_DOCKER_CLI`) for the Docker reward backend, and bootstraps SLIME with
`/root/Megatron-LM` on `PYTHONPATH`. It also creates a short
host-visible temp root (`SLIME_HOST_TMPDIR`, default
`/tmp/w8-biayn-slime-${USER:-user}`), mounts it at the same absolute path, and
exports `TMPDIR` plus `RAY_TMPDIR` inside the container. This keeps nested
Docker reward bind mounts visible to the host daemon while avoiding Ray's
Unix-socket path-length limit.

The generated Docker launcher keeps `--ulimit stack=67108864` enabled by
default. It leaves `--ulimit memlock=-1` off because some managed GPU hosts
reject that rlimit before the container starts. On hosts that allow locked
memory, opt in with:

```bash
SLIME_DOCKER_MEMLOCK_ULIMIT=1 .w8-biayn/slime/run-container.sh
```

It also raises the in-container open-file soft limit to
`SLIME_NOFILE_SOFT_LIMIT=65536` before bootstrapping SLIME.

## Primary SFT Dataset Generation Pipeline

`docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md` is the authoritative
contract for the repository-level primary SFT dataset generation pipeline for
Aider-style C++ tasks. The implementation lives in
`src/w8_biayn/aider_sft/` and is exposed through
`w8-biayn data aider-sft ...`. The 96-root pilot profile deliberately remains
draft. The separate source-only profile contains a frozen, operator-bound
toolchain/sandbox/tokenizer identity and its promoted reviewed inventory, but
`plan` revalidates every local identity before `build`. A frozen preflight is
not dataset readiness. The source-only profile has been exercised through a
verified local 75-row release; its generated bytes remain ignored by Git. No
ready 96-root pilot is claimed.

The no-spend discovery surface is runnable now:

```bash
uv run --extra aider-sft w8-biayn upstreams clone exercism-cpp
uv run --extra aider-sft w8-biayn upstreams clone aider
uv run --extra aider-sft w8-biayn upstreams clone aider-polyglot
uv run --extra aider-sft w8-biayn upstreams clone slime
uv run --extra aider-sft w8-biayn data aider-sft prepare-tokenizer \
  --out .w8-biayn/models/glm-4.7-flash-tokenizer-7dd20894
uv run --extra aider-sft w8-biayn data aider-sft prepare-seccomp \
  --out .w8-biayn/runtime/moby-seccomp-v0.2.1.json
W8_AIDER_SFT_SECCOMP_PROFILE="$PWD/.w8-biayn/runtime/moby-seccomp-v0.2.1.json" \
  uv run --extra aider-sft w8-biayn data aider-sft plan \
    --config configs/aider_sft/source-only-75-v1.toml
uv run --extra aider-sft w8-biayn data aider-sft inventory \
  --config configs/aider_sft/source-only-75-v1.toml \
  --out .w8-biayn/data/aider-sft-source-only-75-v1
```

The tokenizer command fetches tokenizer/config files only, never checkpoint
weights. The seccomp command hash-checks the pinned Moby profile. `plan`
measures the compiler version and binary hash inside the exact grader image;
the host compiler is not accepted as oracle identity evidence. The
`aider-sft` extra installs only the tokenizer/template utilities (Transformers
and Jinja), not the full training stack: finalization loads
the loss-mask utility from the exact clean `SLIME_ROOT` checkout, or the
repo-owned `.cache/upstreams/slime` checkout, even when SLIME is absent from
`PYTHONPATH`. That runtime is initialized before per-task final screening, so
a missing or mismatched checkout reports run-level `profile_not_frozen` and
does not reject a source task. On `--resume`, historical source records
misclassified by that old behavior are retried from preserved candidate
evidence.

The authoritative document contains the complete review, build, finalize,
verify, sanitized-export, and consumer-verification loop.

For a no-authoring dataset, use
`configs/aider_sft/source-only-75-v1.toml`. That separate profile requires
exactly 75 source-backed train roots, zero validation/test roots, and zero LLM
roots. It rejects the paid-call acknowledgement and never backfills: one failed
or rejected source root leaves the release incomplete. It retains the same
C++17 Docker/sanitizer, contamination, rendering, token/mask, human split and
release approval, and producer/consumer verification gates. A ready result is
`.w8-biayn/data/aider-sft-source-only-75-v1/sft/train.jsonl` with exactly 75
rows.

For a deliberately minimal internal handoff matching the established
Moonlight Aider-task row shape, `data aider-sft export-minimal` reads that ready
file without changing it and writes a sibling directory containing only
`train.jsonl`. Each projected row keeps only `label`, `messages` with
`role`/`content`, the six compact metadata fields, and `task_id`; message text
is byte-for-byte preserved. This one-file projection is convenient for a
trusted recipient, but it is not a substitute for the provenance-bearing
`slime-sft` export.

The revised data-only pilot admits exactly 96 roots, split into 72 train, 12
validation, and 12 internal-test roots with exactly 16 roots in each of the six
Aider C++ topic groups. It starts from a frozen 75-root non-benchmark Exercism
inventory (60 practice plus 15 concept roots) and admits at least 21
LLM-assisted roots; any rejected or category-deferred source root is replaced
by an additional LLM root without weakening gates. Source admission and
classification finish before any paid curator call; the pipeline computes the
exact missing cells and requires candidate capacity of at least three times the
resulting required LLM admissions instead of assuming a fixed candidate cap.
It requires hidden executable tests and verified references for admission, but
tests and references never enter model-visible prompts. All 26 official Aider Polyglot
C++ roots and related copies stay excluded.

This Aider pilot is distinct from the C++20 PIE pipeline. It preserves the
pinned Exercism tasks' actual C++17 grader dialect and uses a repo-owned C++17
CMake/Catch scaffold for LLM-assisted tasks. The adapter compiles the exercise
target separately, discovers and runs the Catch executable without CTest, and
runs a fresh ASan/UBSan reference build.
Normal and sanitizer builds pass the explicit `Unix Makefiles` generator and
locked compiler path inside the same enforced, fingerprinted network-disabled
sandbox; sanitizer admission performs its own positive test discovery and must
match the normal test count. The Docker file-size limit converts MiB to bytes,
and pinned Catch v1 discovery accepts only exit zero or the exact parsed
positive test count. Stale source-admission implementation fingerprints are
rerun on `--resume`; an empty pool reports a structured source-only shortfall.
Repeated `catch.hpp`/`tests-main.cpp` files live in
one content-addressed grader-support bundle, so their shared
hashes and the 656,882-byte Catch header neither violate task-file limits nor
become false benchmark contamination. LLM output may not define build scripts,
commands, or dependencies.

Pipeline readiness means deterministic rows, passing normal/sanitizer oracles,
role-aware contamination and family isolation, per-row token/mask evidence,
reconciled manifests, and a schema-v2 receipt binding every lock, ledger,
support bundle, tokenizer policy, training JSONL, and token-record ledger.
Human review is an optional fingerprint-bound audit, not a readiness or
finalization gate.
Candidate admission and dataset split/release have separate states. Final-row
screening matches denylisted IDs as whole slugs, so a valid compound source ID
such as `simple-linked-list` does not become a false `linked-list` hit. An
exact held-out mention still invalidates the frozen split and returns to
quota-preserving backfill before release review. Late rejection journals bind
the renderer and final-screen policy fingerprints, allowing `--resume` to
retry preserved evidence after either policy is corrected. Mutable run state
and locks live in a sibling `.state/` directory; the ready root is immutable.
V1 is autonomous once mechanical gates pass. Source inventory, LLM usage
terms, LLM-assisted admission, contamination near-matches, the final split,
and the final release package may be exported for fingerprint-bound human
audit, but approval is not required.

Rows use final-answer-only Aider `whole` supervision and reach SLIME as raw
message lists. The format/reminder prose stays compact so every frozen
source-only row fits the locked 4096-token sequence without truncation. A thin
repo-owned rollout/mask adapter forwards the exact locked
chat-template kwargs (including disabled thinking) and applies explicit qwen
assistant-only loss; dataset-loader `--apply-chat-template` is forbidden. The
sanitized internal-research export includes the training rows and recomputable
per-row token/mask ledger while excluding tests, references, candidates,
evaluator indexes, and review material. The producer runs full `verify`; the
GLM consumer runs `verify-export` using only the sanitized bundle, pins the
exact model/tokenizer/adapter identities, disables auto-prepare, and rejects any
token, mask, template, or sequence mismatch before SFT. Dataset readiness still
requires no training, target-model responses, repair rows, benchmark evaluation,
or uplift. Existing one-row helpers remain seed fixtures rather than primary
pipeline evidence.

## Moonlight C++ Performance

Run inside the SLIME container:

```bash
cd /workspace/<repo-name>

export SLIME_RUN_ID="moonlight_cpp_perf_$(date -u +%Y%m%d%H%M%S)"
export SLIME_HF_CHECKPOINT=/root/models/Moonlight-16B-A3B-Instruct
export SLIME_REF_LOAD_DIR=/root/models/Moonlight-16B-A3B-Instruct_torch_dist

bash examples/slime/moonlight_cpp_perf/prepare_data.sh
bash examples/slime/moonlight_cpp_perf/eval_base.sh
bash examples/slime/moonlight_cpp_perf/sft.sh
bash examples/slime/moonlight_cpp_perf/eval_sft.sh
bash examples/slime/moonlight_cpp_perf/grpo.sh
bash examples/slime/moonlight_cpp_perf/eval_grpo.sh
bash examples/slime/moonlight_cpp_perf/compare.sh
```

The lane writes local state under
`.w8-biayn/slime/moonlight-cpp-perf/runs/${SLIME_RUN_ID}/`.

### Moonlight Single-Sample Aider Whole SFT

For the compact Aider-like single-sample smoke in
`docs/moonlight_single_sample_sft.md`, build the one-row Aider `whole` dataset
and run only the existing non-LoRA Moonlight SFT stage. The row includes task
text plus complete pre-edit `leap.h` and `leap.cpp` contents. This is not PIE
performance training, GRPO, or benchmark evidence.

From the host:

```bash
uv run python -m w8_biayn.integrations.moonlight_single_sample_sft \
  --out .w8-biayn/data/aider-whole-single
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime setup
```

If you want the materialized local Leap task folder to be the SFT source
instead, create the task and convert its `.docs` plus `.meta/example.*`
reference files into one training row:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_task.sh --force
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_sft_data.sh --force
```

That writes `sft/train.jsonl` and `manifest.json` under
`.w8-biayn/data/aider-leap-sft`. The user message is the same Aider-style prompt
used by the response-only probe; the assistant message is the complete
`leap.h` and `leap.cpp` reference answer from `.meta/example.*`.

Inside the SLIME container:

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

Do not run `examples/slime/moonlight_cpp_perf/prepare_data.sh` for this smoke;
it rebuilds PIE data instead of using the custom one-row SFT JSONL.

### Response-Only Aider Task Probe And Grade

To inspect a model on the local Leap task without training, first materialize
the task folder, then run the probe-and-grade helper against an already served
OpenAI-compatible model endpoint:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_task.sh --force

export SLIME_RUN_ID=moonlight-response-only-leap

bash examples/slime/moonlight_cpp_perf/probe_and_grade_aider_task.sh \
  --task-dir .w8-biayn/data/aider-tasks/aider-dsa/leap \
  --base-url http://127.0.0.1:30000 \
  --model auto \
  --max-tokens 2048
```

For another custom task without `.meta/config.json` `files.solution`, pass
editable files explicitly:

```bash
bash examples/slime/moonlight_cpp_perf/probe_and_grade_aider_task.sh \
  --task-dir /path/to/my-task \
  --editable-file my_task.h \
  --editable-file my_task.cpp \
  --base-url http://127.0.0.1:30000 \
  --model auto
```

The helper saves `prompt.txt`, `prompt.json`, `response.json`, `response.txt`,
`grade/summary.json`, CMake configure/build logs, and a clean graded worktree.
Use `--response path/to/response.txt` to skip model generation and grade an
already saved response.


To save a fresh model response after the SFT export exists, serve
`${SLIME_RUN_ID}/hf/sft/rollout_0` with SGLang and run:

```bash
bash examples/slime/moonlight_cpp_perf/probe_single_sample_sft_response.sh \
  --base-url http://127.0.0.1:30000 --model auto
```

The response is written under
`.w8-biayn/slime/moonlight-cpp-perf/runs/${SLIME_RUN_ID}/probes/aider-whole-heldout-two-fer/response.txt`.

Compile and test that saved held-out response with:

```bash
bash examples/slime/moonlight_cpp_perf/grade_single_sample_sft_response.sh
```

Its pass/fail receipt is written to the same probe tree at
`grade/two-fer/summary.json`, with separate compiler and test logs.


## Moonlight Polyglot C++ Base Eval

This optional benchmark lane evaluates the base Moonlight checkpoint on the C++
subset of `Aider-AI/polyglot-benchmark` using SLIME rollout-only eval. It is a
repo-owned whole-file prompt/parser/reward loop, not an official Aider
leaderboard run.

Detailed setup, runtime knobs, response contract, artifacts, and failure checks
live in `examples/slime/moonlight_polyglot_cpp/README.md`. Quick smoke:

```bash
git clone https://github.com/Aider-AI/polyglot-benchmark \
  .w8-biayn/data/polyglot-benchmark
uv run python -m w8_biayn.integrations.slime_polyglot_cpp sandbox-image
```

Inside the SLIME container:

```bash
export SLIME_RUN_ID="moonlight_polyglot_cpp_$(date -u +%Y%m%d%H%M%S)"
export SLIME_POLYGLOT_SOURCE=/workspace/browser-is-all-you-need/.w8-biayn/data/polyglot-benchmark
export SLIME_POLYGLOT_EVAL_LIMIT=10
export SLIME_EVAL_MAX_RESPONSE_LEN=4096

bash examples/slime/moonlight_polyglot_cpp/prepare_data.sh
bash examples/slime/moonlight_polyglot_cpp/eval_base.sh
```

Artifacts are written under
`.w8-biayn/slime/moonlight-polyglot-cpp/runs/${SLIME_RUN_ID}/`, including
`data/oracle.records.jsonl`, `data/oracle.summary.json`,
`eval/base.records.jsonl`, `eval/base.summary.json`, and
`stages/base-eval/run_receipt.txt`. Preparation blocks unless every upstream
`files.example` reference passes the same Docker grader used for model
responses. The base summary embeds that `oracle_setup_check` alongside strict
pass/fail rates, repo-owned category breakdowns, and `recovered_*` diagnostics
for format-teachable failures; it deliberately omits PIE speed metrics such as
`correct_and_faster_rate`.

Completed Polyglot runs can be compared without rerunning inference:
`python -m w8_biayn.integrations.slime_polyglot_cpp compare-runs --run
<pass1-run> --run <pass8-run> --out <report-dir>`. The reporter validates
successful receipts, recomputed summaries, passing oracle proof, identical
task/fingerprint sets, uniform per-task sample counts, and comparable model,
sampling, sandbox, and timeout settings. It produces category-focused grouped
and stacked bar charts plus a compact dot/range view, JSON, CSV, and Markdown.
All views include the admitted `files.example` oracle as a 100%-passing
same-grader setup ceiling; it is explicitly labeled as reference setup, not a
model run or official Aider score. The six mutually-exclusive presentation
groups are separate from the existing fine-grained multi-label diagnostic
categories. Empirical pass@k is task-level; model outcome bars are sample-level,
while the oracle outcome row records setup preflights. The complete command and
artifact contract lives in the lane README.

For intentional historical comparisons with different sampling, repeat
`--allow-config-mismatch` for `eval_temperature` and/or `eval_top_p`.
Those are the only overridable fields; the result is labeled and persisted as
a descriptive mixed-sampling comparison, not a controlled pass@k claim.

After admission, an optional one-task Gemini API sanity command can send the
exact saved prompt to an exact model id and grade the raw response with the
same strict parser and Docker harness. It is a paid cross-model canary, not a
pass@k benchmark or official Aider result; it never exposes `files.example`,
repairs output, or awards recovered diagnostics. Use
`uv run --extra gemini python -m
w8_biayn.integrations.slime_polyglot_cpp gemini-sanity --dry-run ...` first;
the complete credential, artifact, and interpretation contract lives in the
lane README. The command checks output and parent permissions before the paid
request; use a host-owned output path rather than a root-owned SLIME run path.


## GLM-4.7-Flash Official Aider Polyglot C++ Base Eval On Modal

This optional benchmark runs the base `zai-org/GLM-4.7-Flash` checkpoint
against the C++ subset of `Aider-AI/polyglot-benchmark` through Aider's own
benchmark harness. Modal hosts one four-H100 SGLang server plus a CPU Aider
runner. It is neither a SLIME lane nor the custom Moonlight Polyglot evaluator,
and Aider's cumulative `pass_rate_2` after a repair turn must not be called
pass@2.

The only operator entrypoint is:

```bash
bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

It is export-only, defaults to a redacted no-spend plan, requires explicit paid
acknowledgement for smoke/full, always gates full behind the real two-task
smoke, persists official Aider artifacts in a Modal Volume and ignored local
state, and verifies the ephemeral App stopped before admitting a result.
Source and offline tests are implemented; paid validation and the first
complete 26-task receipt remain pending. The full export contract, artifact
semantics, security boundaries, and recovery commands live in the
[canonical lane runbook](examples/modal/glm47_flash_aider_polyglot_cpp/README.md).

The updated target for the distinct `independent-pass-at-1-and-8` result family
is eight independent trajectories per task with up to two sequential Aider
tries inside each trajectory. It reports exactly `pass@1_try1`,
`pass@1_try2`, `pass@8_try1`, and `pass@8_try2`; try 2 may consume feedback
only from its own try 1. Source and offline tests implement the four-metric
protocol; paid seed inspection, the sampling smoke, a complete full run, and
stopped-App evidence remain pending. The canonical lane runbook contains the
formulas, smoke, artifact, and spend contract. The offline visualization
surface is `uv run python -m w8_biayn.modal_aider_visualization --run-root
<runs/run-id> --output-root <reports/run-id>`; it is read-only, supports
explicit partial-prefix diagnostics, and writes outside canonical evidence.
Visualization schema v2 assigns every pinned task to one of six stable topic
groups (3-6 tasks each) and to a balanced Easy/Medium/Hard split (8/9/9), then
reports initial and cumulative-try-2 performance for both dimensions. The
difficulty label is a repo-owned task-complexity taxonomy, not a value inferred
from the evaluated model's outcomes.
The paid acknowledgements are launch safety gates rather than immutable result
identity, so the same planned run ID may move from false acknowledgements in
no-spend plan mode to true acknowledgements for its first paid invocation.
The sampling smoke pins `binary-search-tree` and `grade-school` for all eight
trajectories and stores the corrected proof under `sampling-smoke-v1`; random
legacy smoke subsets are diagnostic-only and cannot be resumed as evidence.
Because the paid smoke consumed about 70 minutes, independent full runs require
`W8_MODAL_AIDER_MAX_RUN_SECONDS=14400`; changing the old 7200-second identity
requires a fresh run ID.
Aider's `num_exhausted_context_windows` field records provider
`finish_reason=length` output-limit events, not proof of an input-context or
infrastructure failure. Preserve it as a diagnostic, but never reject an
otherwise complete non-exception row with a test invocation solely because the
counter is nonzero.
The runner commits `runner.identity.json` before benchmark work, binding the
immutable config to one Modal App so a platform worker restart can re-enter
without confusing its own artifacts for a stale run. Explicit independent
resume validates and reuses only samples with complete official rows plus
`stats.json`; it archives an interrupted sample under `incomplete-attempts/`
and recreates that sample from the pinned tree and seed. Before resumed artifact
transfer, the prior local failure download moves under
`resume-download-archives/` so strict reconciliation sees a fresh target
without deleting diagnostics. Enabling the active-server lease remains
compatible with pre-lease artifacts.

## Moonlight Multi-SWE C++ Base Eval

This optional benchmark lane evaluates the base Moonlight checkpoint on the C++
subset of `ByteDance-Seed/Multi-SWE-bench_mini` using SLIME rollout-only eval.
It is a repo-owned patch prompt/parser/reward loop, not an official Multi-SWE
leaderboard run.

Detailed setup, runtime knobs, response contract, artifacts, and failure checks
live in `examples/slime/moonlight_multi_swe_cpp/README.md`. Quick smoke:

```bash
git lfs install
git clone https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini \
  .w8-biayn/data/multi-swe-bench-mini
git -C .w8-biayn/data/multi-swe-bench-mini lfs pull
```

Inside the SLIME container:

```bash
export SLIME_RUN_ID="moonlight_multi_swe_cpp_$(date -u +%Y%m%d%H%M%S)"
export SLIME_MULTI_SWE_SOURCE=/workspace/browser-is-all-you-need/.w8-biayn/data/multi-swe-bench-mini
export SLIME_MULTI_SWE_EVAL_LIMIT=3
export SLIME_EVAL_MAX_RESPONSE_LEN=16384
unset W8_SLIME_MULTI_SWE_SANDBOX_IMAGE  # use official per-task images

bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh
```

Artifacts are written under
`.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${SLIME_RUN_ID}/`. Blocking data
admission is recorded incrementally in `data/oracle.records.jsonl`,
`data/oracle.summary.json`, `data/sandbox-images.json`, and
`data/manifest.json`; the latter must say `admitted: true` before evaluation.
Standard setup performs no per-task GitHub clones: the official image supplies
the exact repository and required offline test data. Re-running
`prepare_data.sh` reuses prepared data, cached images, and matching passing
oracle records by default.
Eval artifacts include `eval/base.records.jsonl`,
`eval/base.oracle.records.jsonl`, `eval/base.summary.json`, and
`stages/base-eval/run_receipt.txt`. The summary includes strict pass/fail rates,
repo-level breakdowns, patch/harness and `no_tests_collected` rates,
`recovered_*` diagnostics, and the copied `oracle_setup_check`. It deliberately
omits PIE speed metrics such as `correct_and_faster_rate`.

For the lighter Moonlight MoE smoke, use:

```bash
bash examples/slime/moonlight_moe_smoke/run_moonlight_16b_a3b_int4_smoke.sh
```

## Moonlight Rank-16 LoRA C++ Performance

The rank-16 LoRA variant wraps the active Moonlight C++ lane and applies LoRA
arguments only to SFT, GRPO, and their eval stages. It checks the active
SLIME/Megatron `--help` surface before training so unsupported LoRA flags are
not silently ignored.

Run inside the SLIME container:

```bash
export SLIME_RUN_ID="moonlight_lora16_cpp_perf_$(date -u +%Y%m%d%H%M%S)"
export SLIME_CPP_TASKS_DIR=/workspace/browser-is-all-you-need/.w8-biayn/data/tasks-full
export SLIME_HF_CHECKPOINT=/root/models/Moonlight-16B-A3B-Instruct
export SLIME_REF_LOAD_DIR=/root/models/Moonlight-16B-A3B-Instruct_torch_dist
export SLIME_LORA_RANK=16
export SLIME_WANDB_PROJECT=slime-moonlight-lora-cpp-perf
export SLIME_WANDB_GROUP="${SLIME_RUN_ID}"

bash examples/slime/moonlight_lora_cpp_perf/prepare_data.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_base.sh
bash examples/slime/moonlight_lora_cpp_perf/sft.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_sft.sh
bash examples/slime/moonlight_lora_cpp_perf/grpo.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_grpo.sh
bash examples/slime/moonlight_lora_cpp_perf/compare.sh
```

The LoRA lane writes under
`.w8-biayn/slime/moonlight-lora-cpp-perf/runs/${SLIME_RUN_ID}/` and uses W&B
when `WANDB_API_KEY` or an existing W&B login is present.

### SLIME PIE C++ Path

For the SLIME version of the PIE C++ experiment, keep the normal PIE task build
and convert those tasks to SLIME JSONL:

```bash
uv run w8-biayn data slime build \
  --tasks-dir .w8-biayn/data/tasks-full \
  --out .w8-biayn/data/slime-pie \
  --profile full-official \
  --run-id "$RUN_ID" \
  --min-train-tasks 1000 \
  --min-validation-tasks 100
```

Then launch `examples/slime/cpp_perf/run_moonlight_cpp_perf_rl.sh` with the AIME
4-GPU resource profile and the C++ reward hook:

```bash
SLIME_PROMPT_DATA=.w8-biayn/data/slime-pie/train.jsonl \
W8_BIAYN_SLIME_TASK_ROOT=.w8-biayn/data/slime-pie \
SLIME_CUSTOM_GENERATE_FUNCTION_PATH= \
SLIME_CUSTOM_RM_PATH=generate_with_cpp_perf.reward_func \
SLIME_REWARD_KEY=score \
SLIME_NUM_GPUS=4 \
SLIME_ROLLOUT_BATCH_SIZE=4 \
SLIME_N_SAMPLES_PER_PROMPT=1 \
SLIME_GLOBAL_BATCH_SIZE=4 \
SLIME_MAX_RESPONSE_LEN=256 \
SLIME_MAX_TOKENS_PER_GPU=4096 \
bash examples/slime/cpp_perf/run_moonlight_cpp_perf_rl.sh
```

`generate_with_cpp_perf.reward_func` lives under `examples/slime/cpp_perf/` and
calls the repo C++ reward harness, so the SLIME path still compiles, tests, and
benchmarks candidates against the PIE `v1` oracle. `SLIME_CUSTOM_GENERATE_FUNCTION_PATH=`
disables the Python-tool ReTool trajectory for C++; SLIME's stock one-turn
generation is used instead.

## GLM C++ Performance

When the GLM lane is present, run inside the SLIME container:

```bash
cd /workspace/<repo-name>

export SLIME_RUN_ID="glm47_cpp_perf_$(date -u +%Y%m%d%H%M%S)"
export SLIME_HF_CHECKPOINT=/root/models/GLM-4.7-Flash
export SLIME_REF_LOAD_DIR=/root/models/GLM-4.7-Flash_torch_dist

bash examples/slime/glm47_cpp_perf/prepare_data.sh
bash examples/slime/glm47_cpp_perf/eval_base.sh
bash examples/slime/glm47_cpp_perf/sft.sh
bash examples/slime/glm47_cpp_perf/eval_sft.sh
bash examples/slime/glm47_cpp_perf/grpo.sh
bash examples/slime/glm47_cpp_perf/eval_grpo.sh
bash examples/slime/glm47_cpp_perf/compare.sh
```

Keep GLM defaults conservative until SGLang startup, Megatron training, and C++
reward throughput are stable on the target GPU host. For the paid one-command
GCP full run, use the CLI (dry-run first, always):

```bash
uv run --extra cloud w8-biayn launch glm47-full --dry-run
uv run --extra cloud w8-biayn launch glm47-full \
  --accelerators H100:8 --use-spot --max-attempts 12
```

It loops for capacity in `asia-southeast1` by default (repeat `--region` for
the other allowed regions; pass `--use-spot` when the project only holds
preemptible GPU quota; `--accelerators A100-80GB:8` is the drop-in
80GB-class alternative), runs base eval, SFT, SFT eval, GRPO, GRPO eval, and
compare, copies W&B/local artifacts under `.w8-biayn/slime/glm47-cpp-perf/`,
and tears the provisioned node down. The W&B key resolves from
`--wandb-api-key-file`, `WANDB_API_KEY`, or a `WANDB_KEY` entry in `.env`
(copy `.env.sample` — it documents the only key the tooling reads from
`.env`; GCP credentials live in `.gcp-service-account.json`, not `.env`).
Cloud hardware is managed by SkyPilot behind the CLI (pinned via the `cloud`
extra; see `w8_biayn.constants.SKYPILOT_PIN`), the training itself is pure
SLIME inside the lane container, and the launch tracks the submitted job to a
terminal state before declaring success or tearing down. Implementation:
`src/w8_biayn/cloud_launch.py`
(`examples/slime/glm47_cpp_perf/launch_gcp_h100_full.py` is a thin
compatibility shim).

Key launch flags:

- `--accelerators` — `H100:8` (default) or `A100-80GB:8`. On non-Hopper GPUs
  the lane must use the `alltoall` MoE dispatcher (now the default); DeepEP's
  `flex` dispatcher is Hopper-only and opt-in via
  `SLIME_GLM_MOE_TOKEN_DISPATCHER_TYPE=flex`.
- `--use-spot` — request preemptible capacity (on-demand H100 quota is often 0;
  spot/preemptible quota is self-service).
- `--disk-size` — boot disk GB (default 1024). The 30B model is staged ~4x
  (HF download, torch_dist conversion, SFT checkpoint, HF export); the 256GB
  default overflows mid-export.
- `--min-train-tasks` / `--min-validation-tasks` / `--min-test-tasks` — PIE
  admission gates (defaults 1000/100/100). Lower them for a bounded pilot.
- `--train-limit` / `--eval-limit` — task caps (default: all admitted).
- `--resume-from-run <run-id>` — restore that run's persisted checkpoints and
  skip the training stages it already finished (see below).

**Checkpoint persistence and resume.** On exit — including a partial run where,
say, SFT finished but GRPO failed — the launch rsyncs the run's Megatron
checkpoints and HF exports to `gs://<project>-w8-biayn/runs/glm47/<run-id>/`.
Because the node is ephemeral and gets torn down, this is what makes a run
recoverable. To continue a run, relaunch with a new run id and
`--resume-from-run <old-run-id>`: it restores the old checkpoints into the new
run and the lane skips any training stage whose Megatron checkpoint *and* HF
export are already present, re-running only what's left (evals always re-run).
Persist/restore run on the node's ambient credentials and are best-effort.

**Dataset cache.** The launch restores `tasks-full` from a project-scoped,
gate-keyed GCS path (`gs://<project>-w8-biayn/cache/<version>/tasks-full/...`)
before building, only builds on a cache miss, and repopulates the cache after.
The path is a pure function of the cache version and admission gates, so every
user in the project shares the same cache and different inputs never collide.
The first run for a given key pays the ~20-minute PIE build; later runs and
other users restore in seconds. Cache ops use the node's ambient credentials
and are best-effort — a node without bucket write still trains.

**Teardown.** Three layers, so a dead launcher process can never orphan a paid
box:

1. *Launcher teardown (fast path).* When the launch process is alive it
   downloads artifacts and downs the cluster on exit.
2. *Cluster-side autostop (automatic backstop).* The launch arms SkyPilot
   `idle_minutes_to_autostop` (default 20, `--idle-autostop-minutes`) with
   `down=True`, so once the job ends and the node goes idle SkyPilot
   *terminates* the cluster on its own — independent of the launcher process.
   This closes the gap that once left a cluster UP for ~6 hours when a
   background launcher was killed mid-teardown and its `finally` block never
   ran. Set `0` to disable and rely on launcher-only teardown.
3. *Manual reaper (last resort).* Every instance is tagged
   `labels.run_id=<run-id>` (the same id as the W&B group), so
   `uv run --extra cloud w8-biayn ops down-run <run-id> --execute` downs the
   cluster and deletes any instance still carrying the tag.

After a run, verify with
`gcloud compute instances list --filter=labels.project=w8-biayn`.

**Network honesty.** Every launch probes its dependencies
(compute/storage.googleapis.com, GitHub, W&B) BEFORE spending — unreachable
GCP endpoints fail the launch fast — and a watchdog thread reports
`net_degraded` / `net_still_degraded` / `net_recovered` transitions into the
console log and the `pipeline/launch_events` table for the whole run (a local
DNS blip once stalled provisioning in silent client retries). A vanished spot
cluster is terminal (`CLUSTER_LOST`) and re-enters the provisioning retry
loop instead of being polled forever. Manual probe:
`uv run w8-biayn ops net-check`.

**Observability (W&B).** One launch = one W&B group (= the run id) containing
per-stage runs with deterministic ids and distinct names (`<run-id>-<stage>`;
the lanes pin `WANDB_RUN_ID` and the train-entry shim renames the live run,
because pinned slime ignores `--wandb-run-id` and would name every run after
the group). Each kind of data has one home, following the drill path
*curve → distribution → sample → artifact*:

| Data | Where |
|---|---|
| Training dynamics (kl, clipfrac, grad_norm, logprob drift) | SLIME `train/*`, `rollout/*` (native) |
| Live rollout health (reward mean/std, **zero-variance group fraction** — the GRPO signal heartbeat, abort/format/compile/test/timeout rates, agent steps, wall time) | `rollout_health/*` in the same stage run, logged by the generate hook via SLIME's shared mode |
| Distributions (reward, speedup, agent steps) | `wandb.Histogram` panels |
| Eval outcomes per stage | `eval/*` on the stage's own run (same keys across base/sft/grpo → one overlay panel) + per-task `wandb.Table` + `eval/abort/<reason>` counts, from the offline scorer |
| Uplift verdict | comparison `wandb.Table` + `uplift/*` summary on `<run-id>-pipeline` |
| Token capture (trained tokens/episode, zero-trained-token rate, captured response length) | `rollout_health/trained_tokens_*` — drained directly from the samples in the generate hook |
| Dataset composition (per-task table, counts, gates, GCS link) | `dataset/tasks` table + `dataset_*` config on the pipeline run (`publish-dataset` after prepare-data) |
| Cloud lifecycle (provision attempts, job ids, terminal states, teardown) | `pipeline/launch_events` table + provenance config (git SHA, pins, checkpoint GCS link) |
| GPU memory per stage | `vram/<stage>_usage` table + peak summary (`publish-vram` from each stage's nvidia-smi trace) |
| Setup timeline | `pipeline/elapsed_seconds` curve + one `pipeline/timeline` table (never raw unix scalars) |
| Launch knobs / outcome / lineage | `wandb.config` (redacted `LaunchOptions`), `pipeline/outcome` summary, GCS checkpoint reference artifact |
| Catastrophes | `wandb.alert`: all-abort evals, >30% abort rate with top reason, failed/interrupted launches |

`uv run --extra cloud w8-biayn wandb workspace` pushes the curated saved view
(sections: Uplift & Eval Comparison, Rollout Health, Training Dynamics,
Pipeline) so the project does not render as an unordered metric dump. The
agentic lane also enables SLIME's `--log-passrate`/`--log-multi-turn`
(`passrate/*`, `multi_turn_metric/*`). GRPO group size is
`--grpo-n-samples-per-prompt` (default 8; it must be >= 2 — one sample per
prompt collapses every group-relative advantage to zero, the kl-NaN failure)
and the global batch derives as `rollout_batch_size * n_samples_per_prompt`
unless overridden.

## SSH Manual Run

Use this when you SSH into a GPU machine you already own (no GCP, no SkyPilot,
no Google keys) and want to run the GLM lanes by hand. Everything the paid
launcher automates is reproducible from the repo checkout; the GCS dataset
cache, checkpoint persist, autostop, and reaper simply do not apply — your
box, your disk, your checkpoints. Assumptions: the repo source is on the node,
Docker + the NVIDIA container toolkit work (`docker run --gpus all` succeeds),
and `.env` at the repo root carries `WANDB_KEY` (see `.env.sample`; W&B is
optional — without a key the lanes skip it). 8× 80GB GPUs match the default
GLM parallelism (TP2 · PP2 · CP2 · EP4). Before a long run,
`uv run w8-biayn ops net-check` (keyless) probes connectivity — on a manual
box GitHub (SWE-agent clone, model download) and `api.wandb.ai` are the ones
that matter; the googleapis probes are only relevant with GCP.

1. Host setup (installs `uv`, checks tools, pulls the SLIME image, builds the
   C++ grader image on the HOST daemon — the reward sandbox runs through the
   mounted docker socket):

   ```bash
   ./scripts/bootstrap.sh --no-sky
   uv run w8-biayn data doctor
   uv run w8-biayn upstreams clone slime
   uv run w8-biayn slime doctor
   uv run w8-biayn slime setup          # writes .w8-biayn/slime/run-container.sh
   uv run w8-biayn cpp harness preflight --cpu 3
   ```

2. Build the dataset locally on the node (downloads PIE, prepares, measures
   coverage, admits tasks into `.w8-biayn/data/tasks-full`):

   ```bash
   uv run w8-biayn data pie download --out .w8-biayn/data/pie
   uv run w8-biayn data pie prepare-full --source-root .w8-biayn/data/pie --out .w8-biayn/data/pie-full --force
   uv run w8-biayn data pie measure-coverage --prepared-root .w8-biayn/data/pie-full \
     --out .w8-biayn/data/pie-full/coverage.json --report-out .w8-biayn/data/pie-full/coverage-report.json
   uv run w8-biayn data pie build-full-tasks --prepared-root .w8-biayn/data/pie-full \
     --coverage-json .w8-biayn/data/pie-full/coverage.json --out .w8-biayn/data/tasks-full \
     --min-train 1000 --min-validation 100 --min-test 100 --force
   ```

3. Enter the training container. It mounts the repo at
   `/workspace/<repo-name>`, `$HOME/models` at `/root/models` (override with
   `HOST_MODELS_DIR`), the host docker socket and CLI (for the grader), and a
   short shared temp root for nested Docker and Ray (override with
   `SLIME_HOST_TMPDIR`; override Docker CLI path with `SLIME_DOCKER_CLI`):

   ```bash
   bash .w8-biayn/slime/run-container.sh
   ```

4. Inside the container, set the run knobs. The env is NOT inherited from the
   host shell, so export what you need here (the GLM checkpoint auto-downloads
   to `/root/models/GLM-4.7-Flash` and torch_dist-converts on first use):

   ```bash
   cd /workspace/<repo-name>
   # W&B (optional): the only key the tooling reads from .env
   export WANDB_API_KEY="$(grep -m1 '^WANDB_KEY=' .env | cut -d= -f2-)"
   export SLIME_WANDB_PROJECT=slime-glm47-cpp-perf   # enables W&B logging

   export SLIME_RUN_ID="manual-$(date -u +%Y%m%d%H%M%S)"   # = W&B group
   export SLIME_CPP_TRAIN_LIMIT=8 SLIME_CPP_EVAL_LIMIT=8   # bound the smoke; unset for full
   export SLIME_GRPO_NUM_ROLLOUT=1                          # bump for real training
   # Group size must stay >= 2 (defaults to 8); global batch derives from it.
   # export SLIME_GRPO_N_SAMPLES_PER_PROMPT=8
   # export SLIME_NUM_GPUS=8   # with fewer GPUs also override the parallelism
   #                           # envs (SLIME_EXPERT_MODEL_PARALLEL_SIZE etc.)
   # Adapter fork/merge threshold (defaults 4096; keep > the response budget).
   # Watch rollout_health/fork_samples_dropped_mean in W&B: persistently high
   # means trained tokens are being discarded to keep GRPO's group shape.
   # export SLIME_SWE_FORK_MERGE_MAX_RESPONSE_TOKENS=4096
   ```

5. Run the agentic lane stage by stage (single-turn lane: swap the directory
   for `glm47_cpp_perf`):

   ```bash
   bash examples/slime/glm47_swe_agent_cpp_perf/prepare_data.sh
   bash examples/slime/glm47_swe_agent_cpp_perf/eval_base.sh
   bash examples/slime/glm47_swe_agent_cpp_perf/sft.sh
   bash examples/slime/glm47_swe_agent_cpp_perf/eval_sft.sh
   bash examples/slime/glm47_swe_agent_cpp_perf/grpo.sh
   bash examples/slime/glm47_swe_agent_cpp_perf/eval_grpo.sh
   bash examples/slime/glm47_swe_agent_cpp_perf/compare.sh
   ```

6. Results land under
   `.w8-biayn/slime/glm47-cpp-perf/runs/<run-id>/` — per-stage
   `run_receipt.txt`, `run.log`, VRAM traces, eval records/summaries, and
   `eval/comparison.json` (the uplift verdict). With a W&B key the same run id
   is the W&B group: per-stage runs, `rollout_health/*` live panels, eval
   tables, and the pipeline timeline.

Notes for manual boxes: checkpoints stay on the node (nothing persists to GCS
— copy `runs/<run-id>/checkpoints` + `hf/` yourself if you need durability);
there is no autostop or reaper, so nothing tears the machine down; the lane
re-clones SWE-agent into `.cache/sweagent` at a pinned commit on first agentic
stage; keep the swerex LocalDeployment invariants in mind if you hack on the
driver (see the lane status section above).

## Moonlight MoE Smoke

For the lightest MoE smoke, start with the repo-owned Moonlight wrapper under `examples/slime/moonlight_moe_smoke/`. It uses a Moonlight-16B-A3B Instruct checkpoint, a four-row local math JSONL, one rollout, one sample per prompt, short responses, and the real colocated Megatron + SGLang training path. It does not require E2B, browser sandboxes, DAPO-Math downloads, or W&B by default.

Prerequisites are intentionally narrow: a 4x A100 80 GB node, the pinned SLIME sidecar, `/root/Megatron-LM`, a local Moonlight HF checkpoint, and its converted Megatron torch_dist checkpoint. The launcher defaults are `/root/Moonlight-16B-A3B-Instruct` and `/root/Moonlight-16B-A3B-Instruct_torch_dist`; override with `SLIME_HF_CHECKPOINT` and `SLIME_REF_LOAD_DIR`. The current Moonlight smoke also depends on the generated `.w8-biayn/slime/run-container.sh` including `-v "${HOST_MODELS_DIR:-$HOME/models}":/root/models \`; add that mount before starting the GPU container so the model files are visible inside the SLIME runtime.

Start the SLIME container:

```bash
.w8-biayn/slime/run-container.sh
```

Then launch the smoke inside the container:

```bash
cd /workspace/<repo-name>

SLIME_NUM_GPUS=4 \
SLIME_NUM_ROLLOUT=1 \
SLIME_ROLLOUT_BATCH_SIZE=4 \
SLIME_N_SAMPLES_PER_PROMPT=1 \
SLIME_MAX_RESPONSE_LEN=128 \
SLIME_MAX_TOKENS_PER_GPU=1024 \
bash examples/slime/moonlight_moe_smoke/run_moonlight_16b_a3b_int4_smoke.sh
```

If the torch_dist checkpoint is not already present, the same script can do the conversion explicitly:

```bash
SLIME_CONVERT_IF_MISSING=1 \
SLIME_CONVERT_NPROC=4 \
bash examples/slime/moonlight_moe_smoke/run_moonlight_16b_a3b_int4_smoke.sh
```

Keep `SLIME_ENABLE_DEEPEP=0` for the first pass. Set `SLIME_ENABLE_DEEPEP=1` only after the default all-to-all smoke is healthy on that host/container stack.

The launcher samples `nvidia-smi` during the run and writes `vram_usage.csv` plus `vram_peak.txt` under `.w8-biayn/slime/moonlight-16b-a3b-int4-smoke/runs/<timestamp>/`; use `vram_peak.txt` as the peak-VRAM receipt.

## Moonlight ReTool

Runbook and launchers:

- `examples/slime/retool/README.md`
- `examples/slime/retool/retool_moonlight_sft.sh`
- `examples/slime/retool/retool_moonlight_rl.sh`

This lane runs a local Python tool sandbox only: no E2B dependency, no external
browser sandbox, and no hosted tool service.

## SLIME Multi-Agent Text Example

Runbook and launcher:

- `examples/slime/multi_agent/README.md`
- `examples/slime/multi_agent/run_multi_agent_text.sh`

This is the generic text-only SLIME smoke. It prepares the DAPO-Math-17k JSONL
and runs upstream SLIME's multi-agent generate function with a small Qwen3-4B
default model.

## Evaluation

For SLIME C++ lanes, aggregate debug rollout dumps and compare summaries through
the project SLIME bridge:

```bash
python -m w8_biayn.integrations.slime_cpp_perf aggregate-debug \
  --label base \
  --debug-rollout <path-to-debug-rollout.pt-or-jsonl> \
  --out .w8-biayn/slime/<lane>/runs/${SLIME_RUN_ID}/eval/base

python -m w8_biayn.integrations.slime_cpp_perf compare \
  --summary base=.w8-biayn/slime/<lane>/runs/${SLIME_RUN_ID}/eval/base.summary.json \
  --summary sft=.w8-biayn/slime/<lane>/runs/${SLIME_RUN_ID}/eval/sft.summary.json \
  --summary grpo=.w8-biayn/slime/<lane>/runs/${SLIME_RUN_ID}/eval/grpo.summary.json \
  --out .w8-biayn/slime/<lane>/runs/${SLIME_RUN_ID}/eval/comparison.json
```

Formal uplift requires GRPO to beat base and SFT on
`correct_and_faster_rate` and mean best reward, with no missing runtime rows.

## Repository Map

```text
docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md
                                             primary Aider-style SFT dataset implementation contract
configs/aider_sft/pilot-v1.toml              strict draft profile; operator-owned identities remain unset
manifests/aider_sft/                         pinned benchmark/support manifests; source inventory after review
src/w8_biayn/aider_sft/                      primary Aider-style SFT implementation
tests/test_aider_sft_pipeline.py             no-spend pipeline and GLM handoff regression coverage
scripts/bootstrap.sh                         fresh-machine bootstrap
scripts/prepare_dapo_math_dataset.py         optional SLIME text-smoke data prep
scripts/wandb_milestone.py                   standalone pipeline-milestone logger (elapsed curve + timeline table)
examples/slime/moonlight_cpp_perf/           active Moonlight C++ lane
examples/slime/moonlight_polyglot_cpp/      optional Moonlight base eval on Aider Polyglot C++
examples/modal/glm47_flash_aider_polyglot_cpp/
                                             official Aider C++ base eval on Modal
examples/slime/moonlight_multi_swe_cpp/     optional Moonlight base eval on Multi-SWE C++
examples/slime/moonlight_lora_cpp_perf/      rank-16 LoRA Moonlight C++ lane
examples/slime/glm47_cpp_perf/               active GLM C++ lane when present
examples/slime/glm47_swe_agent_cpp_perf/     agentic SWE-agent file-state C++ lane
examples/slime/cpp_perf/                     single-launcher Moonlight C++ RL profile
examples/slime/retool/                       Moonlight ReTool lane
examples/slime/moonlight_moe_smoke/          light Moonlight MoE smoke
examples/slime/multi_agent/                  generic text-only SLIME smoke
src/local.py                                 Moonlight Megatron local-layer shim
src/w8_biayn/cli.py                          CLI surface
src/w8_biayn/cloud_launch.py                 SkyPilot-backed paid GLM launch (w8-biayn launch glm47-full)
src/w8_biayn/cpp_perf/data.py                downloads, full PIE prep, manifests, cache
src/w8_biayn/cpp_perf/coverage.py            gcov coverage measurement
src/w8_biayn/cpp_perf/pie.py                 PIE parsing and task construction
src/w8_biayn/cpp_perf/schema.py              task and harness schema
src/w8_biayn/cpp_perf/prompts.py             prompt builder and task loading
src/w8_biayn/cpp_perf/slime_dataset.py       SLIME prompt/metadata JSONL builder
src/w8_biayn/cpp_perf/eval.py                eval aggregation
src/w8_biayn/cpp_perf/judge.py               contest-style stdout comparison
src/w8_biayn/cpp_perf/sandbox.py             Docker compile/test/runtime harness
src/w8_biayn/cpp_perf/reward.py              correctness-gated efficiency reward
src/w8_biayn/integrations/slime_cpp_perf.py  SLIME C++ data/reward/eval bridge
src/w8_biayn/integrations/slime_polyglot_cpp.py
                                             SLIME Polyglot C++ data/reward/eval bridge
src/w8_biayn/integrations/slime_multi_swe_cpp.py
                                             SLIME Multi-SWE C++ data/reward/eval bridge
src/w8_biayn/integrations/slime_swe_agent_cpp_perf.py
                                             agentic SWE-agent generate() hook (file-state reward + rollout health)
src/w8_biayn/integrations/swe_agent_driver.py
                                             single-instance SWE-agent run + candidate.cpp extraction
src/w8_biayn/integrations/slime_train_entry.py
                                             repo-owned SLIME train entry wrapper
src/w8_biayn/integrations/slime_moonlight_hf_export.py
                                             Moonlight Megatron-to-HF export shim
src/w8_biayn/slime_integration/doctor.py     pinned SLIME clone doctor
src/w8_biayn/slime_integration/setup.py      SLIME container launcher/bootstrap writer
src/w8_biayn/slime_integration/sandbox.py    SLIME agent sandbox backends
src/w8_biayn/slime_integration/lora.py       runtime-native LoRA flag resolution
src/w8_biayn/wandb_report.py                 W&B data->surface contract (eval/health metrics, tables, artifacts, alerts, workspace template)
src/w8_biayn/net_health.py                   reachability probes, launch preflight, net watchdog (ops net-check)
src/w8_biayn/reporting.py                    raw Markdown/CSV/SVG run evidence reports
src/w8_biayn/shell.py                        dry-run-aware subprocess wrapper
src/w8_biayn/gcp_auth.py                     scoped GCP auth
src/w8_biayn/secrets.py                      credential metadata only
src/w8_biayn/constants.py                    upstream pins and defaults
src/w8_biayn/upstreams.py                    upstream clone management
src/w8_biayn/benchmarks.py                   benchmark ladder
.agents/REPO_GUIDE.md                        shared AGENTS.md and CLAUDE.md target
.agents/skills/w8-biayn-framework/SKILL.md   AI coding-agent workflow skill
```

## Validation

Before handing off normal code/docs work:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/w8-biayn-framework
```

For SLIME setup changes, also run:

```bash
uv run w8-biayn slime doctor
uv run w8-biayn slime setup --force
uv run w8-biayn cpp harness preflight --dry-run
```

For documentation-only changes, run the skill validator and the docs guardrail
tests when practical.


## GLM-4.7-Flash Multi-SWE C++ Base Eval On Modal

The optional source lane at
examples/modal/glm47_flash_multi_swe_cpp/ runs the base GLM checkpoint on the
50 C++ Multi-SWE-bench mini tasks with the existing repo-owned single-diff
contract. It is separate from PIE training, the Moonlight SLIME Multi-SWE lane,
and official Multi-SWE leaderboard evaluation.

The only entrypoint is:

    bash examples/modal/glm47_flash_multi_swe_cpp/run.sh

It defaults to a redacted no-spend plan. Paid smoke/full require explicit
acknowledgement; both require an all-50 fix_patch proof before model loading.
Normally it runs through exact digest-locked, network-blocked Modal Sandboxes;
a fresh full run may instead import an explicitly named completed run's proof
only after local and remote manifest reconciliation plus all 50 current oracle
cache-key matches. Full is also gated by a real two-task smoke. Source,
immutable image lock, runbook, and offline tests are implemented; the paid
two-task smoke is clean and full paid validation remains. No model score
may be reported before a complete 50-task local artifact reconciliation and
control-plane verified stopped-App receipt. Affected simdjson dependencies use
one checksum-pinned read-only parent mount at a fresh /mnt path because Modal
SDK 1.5.2 rejects both mounting one Volume at multiple paths and mounting over
the official image's non-empty dependency directory. After patch preflight,
the trusted grader links only cxxopts and simdjson-data from that detached
mount into their expected checkout paths. Incomplete oracle-only runs may
migrate source identity for an infrastructure fix, but reuse remains
exact-cache-key only and any persisted model/server artifact restores strict
source identity. The grader parses positive CTest discovery from complete
in-memory stdout/stderr before retaining bounded tails from both streams, so
large non-fatal compiler stderr cannot erase the numeric test proof.
With min_containers=0, external health polling absorbs Modal Server zero-to-one
HTTP 503 responses before models/chat admission. Retry receipts contain only
endpoint/status/count/hash/key metadata, never HTTP response text. Source-only
repair may continue a preparation or admission-failure run with an exact
model-cache receipt, but successful admission or any benchmark-stage artifact
restores strict identity.
The GPU server image intentionally omits the dataset image-lock environment;
remote module hydration tolerates that absence, while the local orchestrator
still validates and requires the reviewed lock before any remote or paid work.
Cross-run oracle import is full-only, records source lineage, imports no model
responses, and has no execution fallback: any missing, stale, non-passing, or
unreconciled source evidence blocks before model load or GPU allocation.

## GLM-4.7-Flash Agentic Multi-SWE C++ Base Eval On Modal

The optional successor lane at
examples/modal/glm47_flash_agentic_multi_swe_cpp/ evaluates the same locked 50
C++ Multi-SWE tasks with one isolated, deterministic SWE-agent trajectory per
task. It has a distinct benchmark and result family from the completed
single-turn baseline. The only entrypoint is:

    bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh

Plan is no-spend by default. Paid phases require
W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1; full also requires
W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_LONG_GPU_LEASE=1. SWE-agent is fixed at
5f40e63360d654adcd91e30ed11473389bc4909b with a checked-in dependency lock.
Agentic run IDs admit 3-40 lowercase letters, digits, or hyphens, so the
documented timestamp names fit while the derived Modal App name stays within
62 characters. All 50 unchanged grader oracles and all 50 sanitized-workspace
proofs must pass
or import by exact cache key before model loading or GPU startup.

The agent runs unprivileged in a network-blocked, secret-free, Volume-free
official-image Sandbox. Trusted root code materializes only the exact tracked
tree, removes original history and hidden assets, owns the baseline, synthesizes
and validates the final file-state diff, and applies the existing forbidden-path
policy. Empty uninitialized gitlink directories are preserved and receipt-bound
to their indexed commits; populated submodules must match exactly. The workspace
compile/output probe uses each exact image's default C++
mode because some reviewed legacy images reject a C++20 flag; task grader
commands remain unchanged. Safe hashed/bounded step and tool receipts persist
incrementally; raw model reasoning and the upstream trajectory never do. Full
repeats the fixed
smoke, releases and re-admits the server, then runs all 50. Every stage lowers
the H100!:4 lease to zero before its patches are graded in separate fresh
official-image Sandboxes.

Source, no-spend planning, the runner lock, wrapper, runbook, and offline tests
are implemented. Paid CPU canaries, real SGLang/model admission, one
trajectory, fixed two-task smoke, and full validation remain pending. Do not
report a model score before 50 complete trajectories/records, passing oracle
and workspace proofs, byte-reconciled artifacts, and control-plane-verified
stopped-App evidence. See the lane README for exports, budgets, artifact
schemas, resume rules, and the reporting gate.
