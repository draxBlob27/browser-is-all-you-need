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
missing compiler/test dependencies, all-truncated output, or incomplete
artifacts block the run.
When official rows contain exceptions, the runner commits and prints
`<stage>/exception.summary.json` with bearer-redacted task names, exception
types, and final traceback lines. Full tracebacks remain in the official result
rows and stage logs on the results Volume.

Cold SGLang initialization may include model loading and kernel compilation, so
the supported startup ceiling is 3600 seconds. The launcher polls the child
process and fails early if it exits. A startup failure prints and commits only
a bearer-redacted log tail as `server.failure.json`; raw SGLang output remains
ephemeral.

The singleton server remains scale-to-zero with `min_containers=0`, but its
scaledown window is 1200 seconds. This keeps the loaded four-H100 replica warm
across model-generation and C++ compile/test gaps instead of repeating CUDA
banners and tunnel cold starts. The wrapper explicitly stops and verifies the
App as soon as the run succeeds or fails, so it does not wait 20 minutes to
tear down. The window is immutable run identity and appears in plans and
receipts.

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
most 16 file reads in flight and prints progress every 250 files. When the
remote result is committed, the client lowers the server scaledown window to
two seconds before download so the four H100s can shut down during transfer.
On remote admission failure, the same bounded downloader copies committed
diagnostics locally before re-raising the original error. The printed failure
summary contains only task names and numeric result/token counters, never model
reasoning or editable content.

Use `W8_MODAL_AIDER_RESUME=1` only for an incomplete, identity-matching run.
Resume uses Aider's `--cont`, refuses completed runs and changed identities,
and never fabricates completed task rows. A fresh run ID remains the normal
path.

Do not launch the same run ID concurrently. One run has one results writer.

## Artifacts

Remote Volume subtree and local copy:

```text
runs/<run-id>/
  plan.json
  config.redacted.json
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

All state under `.w8-biayn/` is ignored. Never commit results, histories,
generated settings, model weights, tokens, or receipts.

## Security And Spend Controls

- Plan is the default and creates no paid resources.
- Smoke/full require `W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN=1`.
- The model download runs on CPU before GPU allocation.
- Exactly one strict four-H100 replica is allowed.
- `min_containers=0`, `max_containers=1`, and a 60-second scale-down window
  prevent a persistent warm pool.
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
