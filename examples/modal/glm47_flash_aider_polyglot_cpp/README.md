# GLM-4.7-Flash Official Aider Polyglot C++ Base Eval On Modal

This optional lane answers one narrow question:

> How does the base `zai-org/GLM-4.7-Flash` checkpoint perform on the C++
> subset of `Aider-AI/polyglot-benchmark` under Aider's own benchmark harness,
> with inference and benchmark execution hosted on Modal?

This is an Aider-harness result. Aider owns the prompt, edit format, edit
application, sequential test-feedback retries, C++ test command, and reported
statistics. The repository only validates identities, orchestrates Modal,
persists redacted receipts, transfers artifacts, and checks completeness.

It is separate from PIE training and from
`examples/slime/moonlight_polyglot_cpp/`. The Moonlight lane uses a repo-owned
prompt/parser/grader and reports empirical pass@k. This lane uses official
Aider `--tries 2`: `pass_rate_2` is cumulative success after a sequential
repair turn, not pass@2.

Status: the source, no-spend plan path, and offline tests are implemented.
The paid validation ladder and first 26-task result have not been run from this
checkout. Do not cite a model score until a complete receipt says
`modal_app_stopped: true` and all 26 official Aider result rows are present.

## One Supported Entrypoint

Run from the repository root:

```bash
bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

The script accepts no positional configuration. `--help` only prints the
export contract. All settings use `W8_MODAL_AIDER_*`; no `SLIME_*`, GCP, W&B,
or `.env` configuration is read.

The default phase is `plan`, which writes a redacted local plan and exits
without creating paid resources. Smoke and full phases require the explicit
paid-run acknowledgement. A full run always performs the blocking two-task
smoke first; there is no skip-smoke option.

## Prerequisites

- A Modal workspace with an environment budget/spend alert configured.
- A Modal token/profile exported in the current shell.
- `uv`, installed by `./scripts/bootstrap.sh`.
- Exact immutable commits for the model, Aider, and Polyglot inputs.
- The Aider checkout mounted at upstream's `/aider` path. The pinned C++
  dispatcher invokes `/aider/benchmark/cpp-test.sh` absolutely, so image
  construction verifies both that reference and the script's executable bit.
- A digest-pinned SGLang image whose launch help exposes every required GLM
  parser and EAGLE speculative-decoding flag.
- The official GLM-4.7-Flash Transformers commit
  `76732b4e7120808ff989edbd16401f61fa6a0afa`, installed over the pinned
  SGLang base and build-checked for the `glm4_moe_lite` architecture.
- Capacity for exactly `H100!:4`. The strict `!` prevents Modal from silently
  substituting H200 hardware.

The Modal client is pinned by the `modal` extra in `pyproject.toml`. Do not
install an unpinned global Modal CLI for this path.

## Required Exports

Control-plane credentials stay local. They are never attached to a Modal
Image, Function, Server, Secret, subprocess, or receipt:

```bash
export MODAL_TOKEN_ID='<secret>'
export MODAL_TOKEN_SECRET='<secret>'
export MODAL_PROFILE='<profile-name>'
# Optional when the profile does not already select the intended environment:
export MODAL_ENVIRONMENT='<environment-name>'
```

Freeze every run identity:

```bash
export W8_MODAL_AIDER_RUN_ID="glm47-flash-aider-cpp-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AIDER_MODEL_REPO='zai-org/GLM-4.7-Flash'
export W8_MODAL_AIDER_MODEL_REVISION='<40-lowercase-hex-HF-commit>'
export W8_MODAL_AIDER_AIDER_COMMIT='<40-lowercase-hex-git-commit>'
export W8_MODAL_AIDER_POLYGLOT_COMMIT='<40-lowercase-hex-git-commit>'
export W8_MODAL_AIDER_SGLANG_IMAGE='lmsysorg/sglang@sha256:<64-lowercase-hex-digest>'
```

Repository URLs are fixed in source to the official public repositories. They
are intentionally not configurable exports.

`HF_TOKEN` is optional because the model is public. If set, it is attached
only to the CPU downloader. The GPU server and Aider runner never receive it.

## Plan: No Paid Resources

```bash
export W8_MODAL_AIDER_PHASE='plan'
bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

Plan mode:

1. checks that the command runs from the repo root and `uv` exists;
2. parses every export through the pure Python configuration model;
3. validates immutable identities, bounds, safe names, and artifact paths;
4. writes only redacted `plan.json` and `config.redacted.json`;
5. verifies the active Modal token/profile with `modal token info`;
6. exits before `modal run`.

The plan is written under:

```text
.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/<run-id>/plan.json
```

Inspect it before acknowledging spend.

Every paid invocation first checks the results Volume in a CPU-only function.
A fresh run rejects any pre-existing remote artifact before model loading or
GPU startup. After that admission, an SGLang container restart accepts only
the same identity-compatible configuration written by the active benchmark
runner, avoiding a false run-ID collision during Modal lifecycle recovery.

## Blocking Smoke

Smoke allocates the real four-GPU server, but runs only two C++ tasks with one
try and one thread:

```bash
export W8_MODAL_AIDER_PHASE='smoke'
export W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN='1'
export W8_MODAL_AIDER_SMOKE_TESTS='2'

bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

Smoke admission requires:

- a complete exact-revision model snapshot, including every indexed shard;
- four visible GPUs and the exact SGLang served-model identity;
- successful `/health`, `/v1/models`, and authenticated chat completion;
- separated `reasoning_content` while editable `content` reaches Aider;
- exact Aider and Polyglot Git HEADs and the expected C++ exercise count;
- one non-exception `.aider.results.json` and nonempty chat history per task;
- at least one completed C++ test invocation and a readable Aider stats run;
- a committed Volume artifact copy and verified stopped Modal App.

The generated code may fail to compile or pass tests. That is a model outcome,
not an infrastructure failure. Transport/auth failures, exception-only rows,
missing compiler/test dependencies, missing test invocations, or incomplete
artifacts block the run. Aider's misleading
`num_exhausted_context_windows` field counts provider
`finish_reason=length` output-limit events. Preserve the counter as a model
diagnostic, but do not reject complete non-exception rows with C++ test
invocations because of it; length-finished responses can still apply valid
edits and pass.
When official rows contain exceptions, the runner commits and prints
`<stage>/exception.summary.json` with bearer-redacted task names, exception
types, and final traceback lines. Full tracebacks remain in the official result
rows and stage logs on the results Volume.

Cold SGLang initialization may include model loading and kernel compilation, so
the supported startup ceiling is 3600 seconds. The launcher polls the child
process and fails early if it exits. A startup failure prints and commits only
a bearer-redacted log tail as `server.failure.json`; raw SGLang output remains
ephemeral.

The server uses Modal's public `@app.function` plus `@modal.web_server`
composition rather than pinned SDK 1.5.2's `App.server`. The latter does not
expose its underlying Function execution timeout and silently inherits 300
seconds, which a paid run showed as repeated five-minute CUDA/tunnel recycling.
The explicit server execution timeout is
`startup_timeout_seconds + max_run_seconds + 600`; independent full therefore
gets 18600 seconds. Plans, server runtime evidence, and final receipts record
the derived value.

The Function remains scale-to-zero with static `min_containers=0`. After
CPU/Volume preflight and model-cache preparation succeed, the launcher
dynamically sets `min_containers=1` to lease exactly one four-H100 replica for
all Aider work. On success or error it restores `min_containers=0` and a
two-second drain before artifact transfer, then explicitly stops and verifies
the App. The 1200-second scaledown window remains an identity-bound fallback.
The timeout and active lease are operational safeguards, not benchmark
identity, so a compatible pre-fix run can resume with them enabled.

The authenticated chat admission request uses
`min(W8_MODAL_AIDER_MAX_TOKENS, 2048)` completion tokens. GLM's thinking phase
can consume a 128-token probe before producing editable `content`. A passing
probe writes `admission.response.json`; a failure writes
`admission.failure.json`. Both contain only response keys, field-presence
flags, character counts, finish reason, and numeric token usage. Neither file
contains the generated reasoning or answer text.

## Full 26-Task Run

The first supported full configuration is:

```bash
export W8_MODAL_AIDER_PHASE='full'
export W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN='1'
export W8_MODAL_AIDER_EXPECTED_CPP_TASKS='26'

export W8_MODAL_AIDER_GPU='H100!:4'
export W8_MODAL_AIDER_SGLANG_MEM_FRACTION='0.8'
export W8_MODAL_AIDER_SGLANG_MAX_RUNNING_REQUESTS='16'
export W8_MODAL_AIDER_STARTUP_TIMEOUT_SECONDS='3600'
export W8_MODAL_AIDER_MAX_RUN_SECONDS='7200'

export W8_MODAL_AIDER_EDIT_FORMAT='whole'
export W8_MODAL_AIDER_TRIES='2'
export W8_MODAL_AIDER_THREADS='8'
export W8_MODAL_AIDER_MAX_TOKENS='32768'
export W8_MODAL_AIDER_TEMPERATURE='0.7'
export W8_MODAL_AIDER_TOP_P='1.0'
export W8_MODAL_AIDER_SMOKE_TESTS='2'

bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

Changing edit format, tries, threads, sampling, token budget, image, model,
hardware, or upstream commit makes a different benchmark configuration. Use a
fresh run ID.

The 32768-token bound is intentional. A paid smoke exhausted both 8192-token
responses in GLM reasoning before editable content, while the exact pinned
checkpoint declares a 202752-position context. Do not reuse the failed run ID
when changing this identity-bound setting.

The script caches weights on CPU, starts one authenticated SGLang replica,
runs the blocking smoke, executes all C++ tasks through Aider, runs Aider's own
stats mode, commits results, downloads a local copy, explicitly stops the App,
verifies stopped state through `modal app list --json`, revalidates local
artifacts, and prints the authoritative summary.

Success ends with this shape:

```text
status: complete
benchmark: aider-polyglot-cpp-modal-base-eval
model: zai-org/GLM-4.7-Flash@<revision>
tasks: 26/26
pass_rate_1: <Aider value>
pass_rate_2: <Aider value>
modal_app_stopped: true
artifacts: .../.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/<run-id>
```

Anything less is incomplete infrastructure evidence, not a model result.

## Independent Pass@1/Pass@8 By Try

Status: implemented in source and covered by offline contract tests. Paid seed
transport inspection, the 2-by-8-by-try smoke, and the first complete
26-by-8-by-try result remain mandatory before reporting live metrics.

The updated target runs eight independent trajectories per task, with up to two
sequential Aider tries inside each trajectory:

```bash
export W8_MODAL_AIDER_EVAL_MODE='independent-pass-at-1-and-8'
export W8_MODAL_AIDER_SAMPLES_PER_TASK='8'
export W8_MODAL_AIDER_BASE_SEED='<fixed-integer>'
export W8_MODAL_AIDER_TRIES='2'
export W8_MODAL_AIDER_TEMPERATURE='0.7'
export W8_MODAL_AIDER_TOP_P='1.0'
export W8_MODAL_AIDER_MAX_RUN_SECONDS='14400'
export W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN='1'
export W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8='1'
```

Each trajectory starts from a fresh tree and seed. Its second try may consume
only its own first try's test feedback; no state crosses between trajectories.
A first-try pass skips the second model call but remains cumulatively passing at
try 2. A first-try failure must have a completed second-try outcome.
Because Aider derives stats depth from observed outcomes, it may omit
`pass_rate_2` when every task in one pass succeeds on try 1. Admit that omission
only in this all-first-try-pass case; otherwise missing `pass_rate_2` blocks.

### Four reported metrics

Use explicit `_try1`/`_try2` suffixes rather than ambiguous names such as
`pass@8_2`:

| Metric | Independent breadth | Cumulative try depth | Meaning |
| --- | ---: | ---: | --- |
| `pass@1_try1` | 1 | 1 | Single-trajectory initial success |
| `pass@1_try2` | 1 | 2 | Single-trajectory success after its repair opportunity |
| `pass@8_try1` | 8 | 1 | Any of eight trajectories succeeds initially |
| `pass@8_try2` | 8 | 2 | Any of eight succeeds by its repair opportunity |

For task `i`, let `c[i,t]` be the number of its eight trajectories that have
succeeded cumulatively by try depth `t`:

```text
task_pass_at_1_try_t(i) = c[i,t] / 8
task_pass_at_8_try_t(i) = 1 if c[i,t] > 0 else 0
```

The four reported values are the means of those task values across the exact
26 tasks. Admission must enforce:

```text
pass@1_try1 <= pass@1_try2
pass@8_try1 <= pass@8_try2
pass@1_try1 <= pass@8_try1
pass@1_try2 <= pass@8_try2
```

There is no required ordering between `pass@1_try2` and `pass@8_try1`. Do not
emit pass@2 through pass@7. Raw Aider `pass_rate_1`/`pass_rate_2` remain
per-trajectory statistics and are not renamed.

### Smoke, artifacts, resume, and spend

The sampling smoke is two tasks by eight independent trajectories, each with
`--tries 2`. It must build both try-depth matrices and all four metrics using
production aggregation code. A model pass is not required.
The task set is pinned to `binary-search-tree` and `grade-school` through
Aider's official comma-separated `--keywords` filter before its random shuffle.
Corrected evidence lives under `sampling-smoke-v1`; any older `smoke/`
trajectories with randomized task subsets remain diagnostic-only and are never
reused on resume.
Paid evidence showed this smoke alone can take about 70 minutes, so independent
full runs require `W8_MODAL_AIDER_MAX_RUN_SECONDS=14400`; the former 7200-second
identity must use a fresh run ID rather than resume across the timeout change.

The full run contains 208 independent task trajectories and at most 416 model
edit attempts. Artifacts must include separate try-1 and cumulative-try-2
matrices plus `pass-at-1-and-8-by-try.json`, CSV, `samples.jsonl`, and Markdown.
Every sample row records the seed, attempts made, raw outcomes, try-1 success,
cumulative try-2 success, hashes, token usage, and immutable config identity.

Resume remains scoped to one exact sample index and its task set. A sample is
reused only when its official result directory, every required row/history, and
`stats.json` all validate. An interrupted sample is preserved under
`incomplete-attempts/`, then only that sample is recreated from the pinned
Polyglot tree with its original seed; completed model failures are never
regenerated and state never crosses trajectories. The extra paid
acknowledgement, bounded timeout, early GPU scale-down, artifact reconciliation,
and verified App stop remain mandatory.
Paid acknowledgements are operator safety gates, not benchmark identity fields:
they may change from false in a no-spend plan to true for the paid launch without
forcing a new run ID or `W8_MODAL_AIDER_RESUME=1`.

An existing one-sample pass@1 result remains separate historical evidence; it
is not merged into the new 26-by-8-by-try matrices. See the checked-in design
document for formulas, artifact names, admission rules, and required tests.

## Storage And Resume

Defaults:

```bash
export W8_MODAL_AIDER_MODEL_VOLUME='w8-glm47-flash-models'
export W8_MODAL_AIDER_RESULTS_VOLUME='w8-aider-polyglot-cpp-results'
export W8_MODAL_AIDER_LOCAL_ROOT='.w8-biayn/modal/glm47-flash-aider-polyglot-cpp'
export W8_MODAL_AIDER_RESUME='0'
```

The model Volume is keyed by exact HF revision. An index without all referenced
shards is quarantined and redownloaded. The Aider runner mounts only the
results Volume; it never mounts weights. The model and results Volume names
must differ.

Recursive local download uses Modal SDK 1.5.2's public `FileEntryType` and
reads only exact `FILE` entries. Directories, the Polyglot source symlink, and
all other non-regular entries are skipped before `read_file`; regular files
still require byte-for-byte agreement with any existing local copy. The client
validates the complete entry list first, then uses the SDK async API with at
most 16 file reads in flight and prints progress every 250 files. When remote
work succeeds or errors, the client restores `min_containers=0` and lowers the
server scaledown window to two seconds before download so the four H100s can
shut down during transfer.
On remote admission failure, the same bounded downloader copies committed
diagnostics locally before re-raising the original error. The printed failure
summary contains only task names and numeric result/token counters, never model
reasoning or editable content.

Use `W8_MODAL_AIDER_RESUME=1` only for an incomplete, identity-matching run.
Sequential mode uses Aider's `--cont`. Independent mode validates and reuses
complete samples, archives only the interrupted sample, and restarts it fresh
with the same seed. Resumed local download first moves the prior failure tree
under `resume-download-archives/`, then downloads into an empty canonical run
path for exact manifest reconciliation. Completed runs and changed identities
remain rejected; a fresh run ID remains the normal path.

The runner commits `runner.identity.json` before Aider execution. A Modal
worker restart with `W8_MODAL_AIDER_RESUME=0` may re-enter only when that file
binds the artifacts to the same active App ID and immutable config. A different
App still requires explicit compatible resume, and CPU preflight continues to
reject stale IDs before GPU startup.

Do not launch the same run ID concurrently. One run has one results writer.

## Artifacts

Remote Volume subtree and local copy:

```text
runs/<run-id>/
  plan.json
  config.redacted.json
  runner.identity.json
  upstreams.json
  model-cache.receipt.json
  server.failure.json        # failure-only, bearer-redacted
  admission.failure.json     # failure-only response shape; no generated text
  admission.response.json    # passing response shape; no generated text
  server.runtime.json
  server.receipt.json
  model-settings.yml
  model-settings.sha256
  smoke/
    command.json
    exception.summary.json   # failure-only, bearer-redacted row summaries
    stdout.log
    stderr.log
    stats.txt
    stats.json
    <timestamp>--<run-id>-smoke/
  independent-pass-at-1-and-8/
    sample-01/ ... sample-08/
    incomplete-attempts/   # preserved interrupted full-sample attempts
    success-matrix.try1.json
    success-matrix.try2.json
    pass-at-1-and-8-by-try.json
    sampling-smoke-v1/
      sample-01/ ... sample-08/
      incomplete-attempts/ # preserved interrupted sampling-smoke attempts
      success-matrix.try1.json
      success-matrix.try2.json
      pass-at-1-and-8-by-try.json
  full/
    command.json
    stdout.log
    stderr.log
    stats.txt
    stats.json
    <timestamp>--<run-id>-full/
  run_receipt.json
  artifact_manifest.json
```

Official result directories retain per-task `.aider.results.json` and
`.aider.chat.history.md` files. They are never flattened or rescored. The
repo-owned `stats.json` parser only preserves fields printed by Aider; it does
not recalculate pass rates.

The read-only offline visualization report is implemented as:

```bash
uv run python -m w8_biayn.modal_aider_visualization \
  --run-root .w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/<run-id> \
  --output-root .w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/<run-id>
```

Add `--allow-partial` only for a validated contiguous prefix diagnostic. The
visualizer follows
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_VISUALIZATION_SPEC.md`, recomputes
admitted rows before rendering, never reads credentials, and writes generated
figures under the separate ignored `reports/<run-id>/` tree rather than inside
canonical `runs/<run-id>/` evidence.

Visualization schema v2 gives every pinned task one stable topic and one stable
difficulty label. Topics are deliberately medium-grained: six
mutually-exclusive groups with 3-6 tasks each, enough to expose meaningful
capability differences without producing tiny one-task categories.

| Topic | Pinned tasks |
|---|---|
| Algorithms & data structures | binary-search-tree, circular-buffer, grade-school, knapsack, linked-list, sublist |
| Text & parsing | crypto-square, diamond, kindergarten-garden, phone-number |
| Numerical reasoning | all-your-base, allergies, complex-numbers, perfect-numbers, space-age |
| Time & date | clock, gigasecond, meetup |
| State & concurrency | bank-account, dnd-character, parallel-letter-frequency, robot-name |
| Logic, grids & games | queen-attack, spiral-matrix, yacht, zebra-puzzle |

The separate Easy/Medium/Hard label is a repo-owned complexity taxonomy based
on algorithmic depth, ownership/state/concurrency, and test-surface complexity.
It is fixed across runs and must not be rewritten from a particular model's
observed successes. The existing per-task success-count chart remains the
empirical difficulty view.

| Difficulty | Count | Pinned tasks |
|---|---:|---|
| Easy | 8 | allergies, clock, complex-numbers, diamond, gigasecond, perfect-numbers, queen-attack, space-age |
| Medium | 9 | all-your-base, crypto-square, dnd-character, grade-school, kindergarten-garden, meetup, phone-number, sublist, yacht |
| Hard | 9 | bank-account, binary-search-tree, circular-buffer, knapsack, linked-list, parallel-letter-frequency, robot-name, spiral-matrix, zebra-puzzle |

The HTML, Markdown, normalized JSON, `cells.csv`, and `tasks.csv` expose both
labels. `topic-categories.csv` and `difficulty-categories.csv` provide task
membership, initial/cumulative-try-2 trajectory success, retry recovery, and
task coverage. The matching SVGs are
`05-topic-category-performance.svg` and
`06-difficulty-category-performance.svg`.

All state under `.w8-biayn/` is ignored. Never commit results, histories,
generated settings, model weights, tokens, or receipts.

## Security And Spend Controls

- Plan is the default and creates no paid resources.
- Smoke/full require `W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN=1`.
- The model download runs on CPU before GPU allocation.
- Exactly one strict four-H100 replica is allowed.
- The Server is statically `min_containers=0`, `max_containers=1`; after paid
  admission the launcher leases one active replica with `min_containers=1`.
  Success and error paths restore `min_containers=0` plus a two-second drain,
  preventing a persistent warm pool.
- `modal run` creates an ephemeral App; this lane never deploys or schedules.
- A random per-run bearer protects the otherwise unauthenticated Modal route.
- The bearer is attached only to SGLang and Aider and is never persisted.
- Modal credentials remain local; HF credentials reach only the downloader.
- Timeouts are bounded, retries are disabled, and full cannot skip smoke.
- Exit/signal cleanup stops the deterministic App name and verifies state.
- Generated C++ runs only inside the secret-free Aider runner container.

Configure a workspace/environment budget in Modal before paid validation.
Pricing is intentionally not encoded as a correctness rule.

## Failure Recovery

If cleanup cannot verify stopped state, the script fails loudly and prints the
manual recovery command. Run it immediately:

```bash
uv run --extra modal modal app stop \
  "w8-aider-polyglot-cpp-${W8_MODAL_AIDER_RUN_ID}" --yes
uv run --extra modal modal app list --json
```

Common failures:

- `digest-pinned SGLang image`: replace a tag with an exact registry digest.
- missing SGLang flag: the exported image is incompatible; do not silently
  drop GLM reasoning/tool parser or EAGLE flags.
- incomplete model snapshot: inspect the model-cache receipt; the next run
  quarantines the torn revision and downloads it on CPU.
- served model mismatch: stop; do not let Aider run against another model.
- C++ task-count mismatch: the Polyglot commit does not match the frozen
  expected count. Verify the commit and choose a new run ID if intentional.
- exception-only result: inspect stage stderr and task history. Do not count it
  as a model failure or retry it outside Aider's own continuation behavior.
- nonempty local run directory: use a fresh run ID, or resume only when every
  immutable/behavioral field matches.

## Validation

Offline validation never contacts Modal, GitHub, Hugging Face, or a GPU:

```bash
uv run --extra dev pytest tests/test_modal_aider_polyglot_cpp.py
uv run --extra dev ruff check \
  src/w8_biayn/modal_aider_polyglot_cpp.py \
  examples/modal/glm47_flash_aider_polyglot_cpp/modal_app.py \
  tests/test_modal_aider_polyglot_cpp.py
uv run python -m compileall src tests
bash -n examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

Paid validation must proceed in order: real plan/token check, CPU/Volume
readback, model cache, real-weight SGLang admission, one task, two-task smoke,
then the full 26-task run. Convert every paid infrastructure failure into an
offline regression test before progressing.
