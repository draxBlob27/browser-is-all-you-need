# GLM-4.7-Flash Aider Polyglot C++ Base Eval On Modal

Status: the repository source, export-only wrapper, no-spend plan renderer,
offline contract tests, and operator documentation are implemented. No paid
Modal validation or benchmark result has been produced from this checkout.
The live CPU/Volume, real-weight SGLang, two-task smoke, and full 26-task gates
below remain mandatory before this lane can be called operationally proven or
used to report a model result.

Target: one operator-owned shell script, configured only through exported
environment variables, runs the official Aider Polyglot C++ base evaluation of
`zai-org/GLM-4.7-Flash` on Modal infrastructure. Modal hosts both the SGLang
inference service and the Aider benchmark runner. The script performs a
redacted dry run by default, runs a blocking smoke before the full paid
benchmark, persists official Aider artifacts, downloads a local copy, and
terminates all paid compute.

The canonical operator runbook lives in
`examples/modal/glm47_flash_aider_polyglot_cpp/README.md`.
This document remains the design boundary and implementation checklist.

## Objective

Answer exactly this question:

> How does the base `zai-org/GLM-4.7-Flash` checkpoint perform on the C++
> subset of `Aider-AI/polyglot-benchmark` when evaluated by Aider's own
> benchmark harness, with model serving and benchmark execution hosted on
> Modal?

The result is an Aider-harness result. Aider owns:

- the benchmark prompt and conversation;
- the chosen edit format;
- parsing and applying model edits;
- test-failure feedback between tries;
- the C++ Exercism test command;
- `pass_rate_1`, `pass_rate_2`, malformed-response, token, timing, and other
  official benchmark statistics.

Modal owns:

- model-weight caching;
- the SGLang OpenAI-compatible server;
- the CPU benchmark container;
- durable result storage;
- ephemeral application lifecycle and teardown.

This repository owns only orchestration, configuration validation, redacted
receipts, artifact transfer, and completeness checks. It must not implement a
second Polyglot prompt, edit parser, grader, or pass-rate calculation.

## Scope Boundaries

This evaluation is separate from every SLIME lane and from active PIE
performance RL.

It is not:

- PIE `v0 -> v1` optimization;
- SFT, GRPO, or any other training;
- the custom Moonlight Polyglot rollout-only lane;
- a speed benchmark;
- a pass@k sampling experiment;
- a reason to add Modal to the active SLIME training stack;
- a reason to change the existing SkyPilot/GCP training architecture;
- automatically a leaderboard submission.

Do not import or call
`w8_biayn.integrations.slime_polyglot_cpp` from the new evaluation. That module
implements a different repo-owned prompt/parser/reward contract. Its results
must remain labeled separately.

An Aider run with `--tries 2` reports cumulative success after sequential
repair turns. It is not equivalent to two independent samples and must never be
labeled pass@2.

## Required Reading For Implementing Agents

Before changing source, an implementing agent must read:

1. `AGENTS.md`
2. `README.md`
3. `ROADMAP.md`
4. `.agents/skills/w8-biayn-framework/SKILL.md`
5. this document
6. `docs/MOONLIGHT_POLYGLOT_CPP_BASE_EVAL_PLAN.md`
7. `examples/slime/moonlight_polyglot_cpp/README.md`
8. Aider's pinned `benchmark/README.md`, `benchmark/benchmark.py`,
   `benchmark/cpp-test.sh`, `benchmark/prompts.py`, and benchmark Dockerfile
9. the pinned GLM-4.7-Flash model card
10. the pinned SGLang release notes and launch help
11. Modal documentation for Servers, Images, Volumes, tokens, GPU selection,
    billing, budgets, and application teardown

Official references:

- Aider harness: <https://github.com/Aider-AI/aider/tree/main/benchmark>
- Aider OpenAI-compatible endpoints:
  <https://aider.chat/docs/llms/openai-compat.html>
- Polyglot exercises: <https://github.com/Aider-AI/polyglot-benchmark>
- GLM-4.7-Flash model card:
  <https://huggingface.co/zai-org/GLM-4.7-Flash>
- Modal SGLang server example:
  <https://modal.com/docs/examples/very_large_models>
- Modal GPU guide: <https://modal.com/docs/guide/gpu>
- Modal Volume semantics: <https://modal.com/docs/guide/volumes>

## Architecture

```text
operator shell
  |
  |  run.sh: validate exports, render redacted plan, require paid-run ack
  v
Modal ephemeral App: w8-aider-polyglot-cpp-<run-id>
  |
  +-- preload_model()                    CPU, network allowed
  |     |
  |     +-- public HF snapshot at exact revision
  |     +-- explicit model manifest and Volume commit
  |     `-- persistent model Volume
  |
  +-- SGLangServer                       strict H100:4 by default
  |     |
  |     +-- exact cached model revision
  |     +-- OpenAI-compatible /v1 API
  |     +-- temporary bearer key
  |     `-- min_containers=0, short scale-down window
  |
  `-- run_aider_benchmark()              CPU container
        |
        +-- pinned Aider checkout
        +-- pinned Polyglot checkout
        +-- exact Aider C++ harness
        +-- smoke, then full C++ run
        +-- stats and run receipts
        `-- persistent results Volume
              |
              `-- local artifact copy under .w8-biayn/
```

There must be exactly one GPU server replica. Do not autoscale to a second
four-GPU replica. Aider concurrency feeds SGLang continuous batching inside
the one replica.

The Modal App must be ephemeral and launched with `modal run`, not permanently
deployed. `min_containers` must remain zero. The local entrypoint must wait for
the benchmark, persist artifacts, and return before the App exits.

## Intended Repository Files

The implementation should add this source layout:

```text
examples/modal/glm47_flash_aider_polyglot_cpp/
  README.md                         canonical operator runbook
  run.sh                            only supported operator entrypoint
  modal_app.py                      Modal resources and orchestration
  Dockerfile.aider                  pinned Aider benchmark runtime
  glm47_flash.model.settings.yml    Aider model-settings template
src/w8_biayn/modal_aider_polyglot_cpp.py
                                    pure config, validation, receipts,
                                    artifact checks, and stats parsing
tests/test_modal_aider_polyglot_cpp.py
```

Also update:

```text
pyproject.toml
README.md
ROADMAP.md
.agents/REPO_GUIDE.md
.agents/skills/w8-biayn-framework/SKILL.md
.gitignore
```

Keep Modal imports out of `src/w8_biayn/modal_aider_polyglot_cpp.py`. The pure
module must remain importable in the default development environment so all
configuration and receipt logic can be tested without Modal credentials or
network access.

Add a dedicated optional dependency extra, rather than putting Modal in core
dependencies:

```toml
modal = [
  "modal==<verified-pin>",
]
```

The wrapper should invoke the extra with `uv run --extra modal ...`.

## Single-Script Operator Contract

The only supported entrypoint is:

```bash
bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

The script accepts no positional configuration. All configuration comes from
exported environment variables. `--help` may print the export contract, but
must not become a second configuration surface.

The script must:

1. validate every required export before contacting Modal;
2. ensure the current directory is the repository root;
3. ensure `uv` is present;
4. verify Modal authentication with `modal token info` without printing token
   values;
5. render and persist a redacted plan;
6. exit without creating paid resources by default;
7. require an explicit paid-run acknowledgement;
8. run the Modal application;
9. stream useful progress without secrets;
10. download the committed run artifacts to ignored local state;
11. validate the local artifact set;
12. print the official Aider summary and exact artifact path;
13. stop the named Modal App on failure or interruption;
14. never leave a deployed or warm GPU service.

No command in the documented happy path should require manual cloning,
interactive shell access to Modal, hand-edited YAML, or a second script.

## Exported Configuration

All names added by this surface use the `W8_MODAL_AIDER_` prefix. Existing
`SLIME_*` and GCP variables must not be reused.

### Required credentials

```bash
export MODAL_TOKEN_ID='<secret>'
export MODAL_TOKEN_SECRET='<secret>'
export MODAL_PROFILE='<profile-name>'
```

The token variables are local control-plane credentials only. Never attach
them to a Modal Image, Function, Server, Secret, subprocess environment, or
receipt.

`MODAL_ENVIRONMENT` may select a non-default Modal environment. If unset, use
the profile's configured environment.

### Required immutable identities

Full runs must require exact immutable identities:

```bash
export W8_MODAL_AIDER_RUN_ID="glm47-flash-aider-cpp-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AIDER_MODEL_REPO='zai-org/GLM-4.7-Flash'
export W8_MODAL_AIDER_MODEL_REVISION='<40-hex-hugging-face-commit>'
export W8_MODAL_AIDER_AIDER_COMMIT='<40-hex-git-commit>'
export W8_MODAL_AIDER_POLYGLOT_COMMIT='<40-hex-git-commit>'
export W8_MODAL_AIDER_SGLANG_IMAGE='lmsysorg/sglang@sha256:<digest>'
```

The digest-pinned SGLang base must be deterministically overlaid with the
official GLM-4.7-Flash Transformers commit
`76732b4e7120808ff989edbd16401f61fa6a0afa`. Image construction must fail
unless Transformers recognizes `glm4_moe_lite`, and receipts must record this
commit.
A CPU-only results-Volume preflight must reject every stale run ID before
model loading or GPU startup. After admission, a restarted SGLang container
must accept the runner-written config only when its immutable identity remains
compatible; that active config is not evidence of operator run-ID reuse.
The authenticated chat probe must use at most 2048 tokens, further bounded by
the configured benchmark completion budget. This prevents GLM's thinking phase
from consuming a 128-token probe before editable content appears. Persist
`admission.response.json` or `admission.failure.json` with response-shape
metadata only: keys, presence flags, character counts, finish reason, and
numeric token usage. Do not persist generated reasoning or answer text.
The runner must clone Aider at `/aider`, matching the pinned official
benchmark's absolute `/aider/benchmark/cpp-test.sh` command. Image construction
must verify that script is executable and still referenced by the dispatcher.
If official rows contain exceptions, commit and print a bearer-redacted
`<stage>/exception.summary.json` containing only task, exception type, and the
final traceback line before blocking admission.
The singleton SGLang Server must retain `min_containers=0` and use a fixed
1200-second scaledown window, Modal's maximum, to remain loaded across Aider's
generation and C++ compile/test gaps. Plans, resume identity, server receipts,
and final receipts must record this value. The wrapper's explicit stop and
control-plane verification must still tear the App down immediately on every
exit rather than waiting for the idle window.
Recursive results-Volume download under pinned Modal SDK 1.5.2 must compare
the public `FileEntry.type` directly with `FileEntryType.FILE`. It must skip
directories, symlinks, FIFOs, sockets, and unspecified entries before calling
`read_file`, while retaining path-safety and byte-for-byte reconciliation for
every downloaded regular file. Enumerate and validate the complete regular-file
set before local writes, then use the SDK async API with a fixed bound of 16
concurrent file reads and periodic progress output. Immediately after the
durable remote benchmark result returns, reduce the SGLang server scaledown
window to two seconds before local transfer; the 1200-second run-identity value
continues to protect generation and compilation gaps, but does not keep H100s
alive while the client copies artifacts.
Do not accept `main`, `latest`, branch names, abbreviated Git commits, or an
untagged/undigested SGLang image for a full result. A smoke may allow a pinned
version tag only with an explicitly recorded unsafe-development override.

Repository URLs are source constants and must remain hardcoded to the official
public repositories. Do not accept arbitrary repository URLs through exports;
that would turn validated commit fields into shell/network injection surfaces.

### Execution and safety

```bash
export W8_MODAL_AIDER_PHASE='full'              # plan | smoke | full
export W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN='1'  # required for smoke/full
export W8_MODAL_AIDER_EXPECTED_CPP_TASKS='26'
```

Default phase is `plan`. `full` always runs the blocking smoke first. There is
no supported `skip-smoke` flag.

The run ID must match `^[a-z0-9][a-z0-9-]{2,37}$`. The 38-character maximum
keeps the deterministic prefixed Modal App name within a conservative
63-character bound. Reject path separators, whitespace, shell metacharacters,
uppercase normalization ambiguity, and reuse of a completed run ID unless an
explicit resume contract is selected.

### Hardware and serving

```bash
export W8_MODAL_AIDER_GPU='H100!:4'
export W8_MODAL_AIDER_SGLANG_MEM_FRACTION='0.8'
export W8_MODAL_AIDER_SGLANG_MAX_RUNNING_REQUESTS='16'
export W8_MODAL_AIDER_STARTUP_TIMEOUT_SECONDS='3600'
export W8_MODAL_AIDER_MAX_RUN_SECONDS='7200'
```

`H100!:4` is the first supported production profile: four H100s match the
GLM-4.7-Flash model card's tensor-parallel launch, while Modal's strict `!`
selector prevents an automatic H100-to-H200 substitution. A later single-H200
profile may be admitted only after a separate live compatibility and
performance receipt. Do not silently fall back to another GPU type or count in
a benchmark run.

The GPU server timeout is a hard spend guard. Do not permit zero, unlimited, or
greater-than-four-hour values without changing this design and tests.

### Aider run settings

```bash
export W8_MODAL_AIDER_EDIT_FORMAT='whole'
export W8_MODAL_AIDER_TRIES='2'
export W8_MODAL_AIDER_THREADS='8'
export W8_MODAL_AIDER_MAX_TOKENS='32768'
export W8_MODAL_AIDER_TEMPERATURE='0.7'
export W8_MODAL_AIDER_TOP_P='1.0'
export W8_MODAL_AIDER_SMOKE_TESTS='2'
```

The first supported result uses `whole`, the edit format Aider recommends for
an experimental model. A paid smoke demonstrated that GLM can consume an
8192-token completion entirely in reasoning; 32768 preserves thinking while
remaining well inside the pinned checkpoint's 202752-position context.
Changing edit format, tries, temperature, top-p, thinking configuration, or
token budget creates a different benchmark configuration and must produce a
separate run ID.

`--tries 2` is intentional: the same full run yields Aider's first-attempt and
cumulative second-attempt rates. A smoke uses one try and one thread regardless
of the full settings.

The model is a thinking model. SGLang must separate reasoning with the `glm45`
reasoning parser so Aider receives editable response content. The smoke must
prove that response content, not only `reasoning_content`, reaches Aider. If
the pinned Aider/LiteLLM pair needs explicit reasoning handling, freeze it in
the model-settings file and record that file's SHA-256.

### Storage and local artifacts

```bash
export W8_MODAL_AIDER_MODEL_VOLUME='w8-glm47-flash-models'
export W8_MODAL_AIDER_RESULTS_VOLUME='w8-aider-polyglot-cpp-results'
export W8_MODAL_AIDER_LOCAL_ROOT='.w8-biayn/modal/glm47-flash-aider-polyglot-cpp'
export W8_MODAL_AIDER_RESUME='0'
```

The model path inside its Volume is keyed by the exact Hugging Face revision.
The results path is keyed by run ID. One run has one writer. Do not concurrently
launch the same run ID.

`RESUME=1` may continue only an incomplete, identity-matching Aider run through
Aider's own `--cont` behavior. It must reject completed runs and any changed
model, upstream, image, hardware, sampling, or harness identity.

### Optional public-model credential

`HF_TOKEN` is optional because GLM-4.7-Flash is public. If supplied, attach it
only to the model downloader. Do not attach it to the SGLang server after the
model is cached, and never attach it to the Aider benchmark runner.

## Configuration Validation And Redaction

Implement one frozen dataclass or Pydantic model for the complete configuration.
Both the wrapper's plan and the Modal app must consume the same serialized,
validated configuration. Do not independently parse exports in shell and
Python with different defaults.

Validation must cover:

- required token variables are nonempty, but values are never returned;
- exact 40-character lowercase hexadecimal revisions;
- exact SGLang registry digest for full mode;
- numeric ranges for all counts, fractions, timeouts, and sampling values;
- `tries` in `1..2` for the first implementation;
- full threads in `1..16`;
- smoke tests in `1..3`;
- expected task count greater than zero;
- allowed phase and edit format;
- safe run, Volume, profile, and environment names;
- local artifact root contained inside the repository's ignored `.w8-biayn/`;
- no existing nonempty local run directory unless identity-matching resume is
  requested.

Every printable mapping must replace these fields with `<redacted>`:

- `MODAL_TOKEN_ID`
- `MODAL_TOKEN_SECRET`
- `HF_TOKEN`
- generated SGLang bearer key
- any header or URL containing a credential

Tests must scan rendered plans, exceptions, logs, and receipts using sentinel
secret values and fail if any sentinel appears.

## Modal Resources

### Application identity and lifecycle

Name the ephemeral App deterministically:

```text
w8-aider-polyglot-cpp-<run-id>
```

Set tags for benchmark, model, run ID, owner/profile, and TTL when supported by
the pinned SDK. The App must use:

- `min_containers=0`;
- exactly one GPU replica;
- a short scale-down window, at most 120 seconds;
- a bounded startup timeout;
- a bounded benchmark timeout;
- no scheduled or deployed service.

The wrapper must install signal/exit handling. On an unsuccessful local
process, issue the pinned SDK/CLI equivalent of:

```bash
modal app stop "w8-aider-polyglot-cpp-${W8_MODAL_AIDER_RUN_ID}" --yes
```

Then verify through `modal app list --json` that the named App is stopped. A
failed teardown is a loud run failure with the exact manual recovery command.

### Model Volume and downloader

The downloader runs on CPU before GPU allocation. It must:

1. resolve only the hardcoded model repository;
2. download the exact exported revision;
3. use a deterministic path such as
   `/models/zai-org--GLM-4.7-Flash/<revision>/`;
4. use Hugging Face high-performance transfer support when available;
5. write an incremental download receipt outside the snapshot directory;
6. validate `config.json`, tokenizer/chat-template material, the safetensors
   index, every shard named by the index, and a plausible aggregate byte size;
7. write a manifest containing filenames, sizes, and SHA-256 where practical;
8. call `model_volume.commit()` explicitly;
9. skip the network when an identity-matching complete manifest already
   exists;
10. never allocate a GPU for model download.

An index without all weight shards is not a cache hit. Remove or quarantine an
incomplete revision directory before retrying so SGLang cannot hang on a torn
snapshot.

### SGLang GPU server

Base the GPU Image on the exact exported digest. Run the model with the pinned
release's supported equivalent of:

```bash
python -m sglang.launch_server \
  --model-path /models/zai-org--GLM-4.7-Flash/<revision> \
  --tp-size 4 \
  --tool-call-parser glm47 \
  --reasoning-parser glm45 \
  --speculative-algorithm EAGLE \
  --speculative-num-steps 3 \
  --speculative-eagle-topk 1 \
  --speculative-num-draft-tokens 4 \
  --mem-fraction-static 0.8 \
  --max-running-requests 16 \
  --served-model-name glm-4.7-flash \
  --api-key "$SGLANG_API_KEY" \
  --host 0.0.0.0 \
  --port 8000
```

Do not copy flags blindly across SGLang versions. At implementation time,
compare them to `python -m sglang.launch_server --help` in the exact Image and
add a regression test for every required flag.

The endpoint may use Modal's unauthenticated routing only because SGLang itself
requires a cryptographically random, per-run bearer key. Generate that key in
the local orchestration process, pass it through an ephemeral `modal.Secret`,
attach the Secret only to the server and benchmark runner, and never persist
it.

Server admission requires:

- `/health` returns success;
- `/v1/models` contains exactly the served model name;
- the server reports the expected model path and tensor-parallel size;
- all four requested GPUs are visible;
- a short OpenAI-compatible chat completion succeeds;
- reasoning and final content are separated as expected;
- the server receipt records Modal GPU type, count, region/provider, Image
  identity, startup seconds, and model manifest identity.

Only after these checks may the Aider smoke begin.

### Aider CPU benchmark runner

Build the runner from `Dockerfile.aider`. It must reproduce the pinned Aider
benchmark Dockerfile's C++ environment closely enough that
`benchmark/cpp-test.sh` remains unchanged. Record the upstream Dockerfile SHA
and the local Dockerfile SHA in the receipt.

The Image must contain:

- the pinned Aider source checkout;
- Aider's development dependencies required by `benchmark.py`;
- Git;
- GCC/G++;
- CMake;
- GNU Make;
- Boost components required by the C++ exercise set;
- the pinned Polyglot checkout at the path expected by Aider;
- a generated, validated model-settings file.

Do not vendor the Aider or Polyglot repositories into this repository. Clone
them in the Modal Image at exact commits. Validate Git HEAD before each run.

The runner receives no Modal token and no Hugging Face token. Its only secret
is the short-lived SGLang bearer key. It mounts only the results Volume, not the
model Volume.

Set `AIDER_DOCKER=1` because Modal already executes the runner inside a
container. Do not attempt Docker-in-Docker. Record this environment difference
in the receipt. Before describing a result as leaderboard-submittable, compare
the Modal runner Image with the pinned official Aider benchmark Dockerfile and
document any remaining differences.

## Aider Model Settings

Generate the final YAML from a checked-in template after validating the
exports. The intended first configuration is conceptually:

```yaml
- name: openai/glm-4.7-flash
  edit_format: whole
  use_repo_map: false
  use_temperature: true
  streaming: false
  extra_params:
    max_tokens: 32768
    temperature: 0.7
    top_p: 1.0
```

The exact keys must be verified against the pinned Aider `ModelSettings` class
and LiteLLM behavior. If chat-template kwargs are needed to keep thinking
enabled or preserved across Aider's second try, place them in this file only
after a focused request/response test. Record the final YAML content and
SHA-256, but never a secret.

Do not configure a weak model, editor model, architect mode, repo map, tool
calling, or external fallback model in the first implementation. Every model
request must go to the one GLM-4.7-Flash SGLang service.

## Exact Benchmark Commands

The smoke command must be the pinned harness's supported equivalent of:

```bash
./benchmark/benchmark.py "${RUN_ID}-smoke" \
  --model openai/glm-4.7-flash \
  --edit-format whole \
  --languages cpp \
  --tries 1 \
  --threads 1 \
  --num-tests 2 \
  --exercises-dir polyglot-benchmark \
  --read-model-settings /run/glm47_flash.model.settings.yml
```

The full command must be the pinned harness's supported equivalent of:

```bash
./benchmark/benchmark.py "${RUN_ID}-full" \
  --model openai/glm-4.7-flash \
  --edit-format whole \
  --languages cpp \
  --tries 2 \
  --threads 8 \
  --exercises-dir polyglot-benchmark \
  --read-model-settings /run/glm47_flash.model.settings.yml
```

Set only these provider variables in the runner subprocess:

```bash
export OPENAI_API_BASE="${SGLANG_URL%/}/v1"
export OPENAI_API_KEY="$SGLANG_API_KEY"
```

Capture stdout and stderr separately, preserve the exit code, and record the
exact argv as a JSON array. Do not build a shell command from unquoted exports.
Use `subprocess.run([...], check=False, ...)` with validated values.

After each phase, invoke the harness's own stats mode and store raw output:

```bash
./benchmark/benchmark.py --stats <exact-result-directory>
```

A repo-owned parser may convert the raw stats to JSON for easier inspection,
but the raw Aider results and stats output are authoritative. The parser must
not recompute test outcomes or change pass-rate semantics.

## Run Sequence And Blocking Gates

### Stage 0: local plan and authentication

Checklist:

- [ ] Parse and validate all exports through the pure Python config module.
- [ ] Verify the Modal token/profile with `modal token info`.
- [ ] Verify the local artifact root is ignored and writable.
- [ ] Write `plan.json` containing only redacted configuration.
- [ ] Print model, upstream, hardware, timeout, phase, and artifact identities.
- [ ] Exit before creating Modal resources when phase is `plan`.
- [ ] Require `W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN=1` otherwise.

### Stage 1: cache the exact model

Checklist:

- [ ] Create or open the named model Volume.
- [ ] Reuse only a complete identity-matching snapshot.
- [ ] Download on CPU when missing.
- [ ] Verify all indexed shards and required tokenizer/config files.
- [ ] Commit the Volume.
- [ ] Persist a model-cache receipt.

### Stage 2: start and admit SGLang

Checklist:

- [ ] Allocate exactly the configured strict GPU profile.
- [ ] Start the exact SGLang Image and flags.
- [ ] Verify health, model listing, GPU count, and model identity.
- [ ] Send one short authenticated chat completion.
- [ ] Prove editable content survives reasoning separation.
- [ ] Persist a redacted server receipt.

### Stage 3: blocking Aider smoke

Checklist:

- [ ] Verify pinned Aider and Polyglot HEADs.
- [ ] Verify the expected C++ exercise count.
- [ ] Run two tasks, one try, one thread.
- [ ] Require one `.aider.results.json` per selected task.
- [ ] Reject transport, authentication, context-window, runner, or harness
      exceptions.
- [ ] Require at least one completed model response and one completed C++ test
      invocation.
- [ ] Reject an all-truncated smoke.
- [ ] Do not require either task to pass; wrong code is a valid model outcome.
- [ ] Commit smoke artifacts before full evaluation.

Infrastructure failures block the full run. Model-quality failures such as a
well-formed edit that fails tests do not.

### Stage 4: full Aider C++ evaluation

Checklist:

- [ ] Run every pinned C++ exercise with the frozen configuration.
- [ ] Use Aider's retry/test-feedback loop unchanged.
- [ ] Persist incremental benchmark files through the results Volume.
- [ ] Capture raw per-task chat histories and result JSON.
- [ ] Capture raw benchmark stdout/stderr.
- [ ] Run Aider stats after completion.
- [ ] Commit all results and receipts.

### Stage 5: completeness and local artifact copy

Checklist:

- [ ] Count exactly the expected full-run result files.
- [ ] Reject exception-only or malformed result JSON files.
- [ ] Require Aider stats `test_cases` to equal the expected count.
- [ ] Record, without reinterpretation, `pass_rate_1`, `pass_rate_2`, malformed
      responses, timeouts, token counts, duration, and model/edit identities.
- [ ] Write `run_receipt.json` with final status.
- [ ] Commit the results Volume.
- [ ] Download the complete run subtree to the local ignored artifact root.
- [ ] Re-run completeness validation on the local copy.

### Stage 6: teardown

Checklist:

- [ ] Let the ephemeral App exit after artifacts are durable.
- [ ] Confirm no server replica remains warm.
- [ ] On error or signal, stop the named App explicitly.
- [ ] Verify stopped state through Modal's control plane.
- [ ] Print the manual stop command if verification fails.

Teardown failure changes the final run status to failure even when benchmark
results exist.

## Smoke And Full Admission Rules

Classify failures into three families.

Infrastructure failures block attribution to the model:

- Modal authentication, budget, or GPU allocation failure;
- incomplete model cache;
- SGLang startup/OOM/crash;
- wrong model, Image, or GPU identity;
- HTTP authentication or transport errors;
- Aider/Polyglot checkout mismatch;
- missing compiler/test dependencies;
- results Volume or artifact-copy failure;
- incomplete task/result count.

Harness failures block attribution to the model:

- Aider exception-only result;
- C++ test command unavailable;
- no test invocation recorded;
- stats mode cannot read the completed result directory;
- Modal runner differs materially from the pinned Aider environment without a
  recorded compatibility decision.

Model outcomes remain benchmark data:

- malformed edit response;
- lazy or incomplete edit;
- compile failure caused by generated code;
- unit-test failure;
- first-try failure repaired on the second try;
- context use within the frozen output budget, including an individual
  response hitting the recorded limit after the smoke has passed.

Do not hide or retry model outcomes outside Aider's own `--tries` behavior.

## Artifact Contract

Remote results Volume:

```text
/runs/<run-id>/
  plan.json
  config.redacted.json
  upstreams.json
  model-cache.receipt.json
  server.receipt.json
  model-settings.yml
  model-settings.sha256
  smoke/
    command.json
    stdout.log
    stderr.log
    stats.txt
    <official-aider-result-directory>/
  full/
    command.json
    stdout.log
    stderr.log
    stats.txt
    stats.json
    <official-aider-result-directory>/
  run_receipt.json
  artifact_manifest.json
```

Local copy:

```text
.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/<run-id>/
  <same committed run subtree>
```

The official Aider result directory must retain, for every task, files such as
`.aider.results.json` and `.aider.chat.history.md`. Do not flatten, rename, or
discard upstream artifacts.

`artifact_manifest.json` records relative path, byte size, and SHA-256 for all
receipts, commands, summaries, and small text/JSON artifacts. It may omit
hashing large redundant exercise trees, but must record their file count and
aggregate size.

`run_receipt.json` must contain:

- schema version and status;
- run ID and UTC timestamps;
- Modal profile and environment, never token values;
- Modal App ID/name and stopped-state verification;
- model repo, exact revision, and cache-manifest digest;
- Aider and Polyglot exact commits;
- SGLang Image digest and launch flags;
- Modal SDK pin;
- GPU requested and GPU observed;
- model-settings content hash;
- Aider argv and frozen sampling/edit settings;
- expected, completed, and exception task counts;
- authoritative Aider stats fields;
- server startup, smoke, full, and total elapsed seconds;
- remote Volume path and local artifact path;
- teardown status;
- a clear label: `aider-polyglot-cpp-modal-base-eval`.

## Security Contract

- Never print, persist, or remotely attach Modal token credentials.
- Never store credentials in `.env`, source, command arguments, receipts, or
  generated artifacts.
- Generate a new SGLang bearer key for every run and never persist it.
- Attach optional `HF_TOKEN` only to the downloader.
- Do not expose the SGLang server without its own bearer check.
- The benchmark runner must not receive `HF_TOKEN` or Modal credentials.
- Treat model-generated C++ as untrusted. Modal container isolation protects
  the operator host, but the initial Aider-parity runner still executes code in
  the runner container. Give that container no long-lived secret.
- Do not mount the model Volume into the runner.
- Keep generated code and all artifacts outside git.
- Scan plans, logs, exceptions, and artifacts for sentinel secrets in tests.

A future stronger sandbox may isolate each C++ test with network disabled, but
that changes the official Aider execution environment and requires a separate
parity decision. Do not silently add it to the first implementation.

## Spend And Runtime Controls

The design must minimize accidental spend:

- redacted plan is the default action;
- explicit paid acknowledgement is mandatory;
- model download happens on CPU before GPU allocation;
- full evaluation is impossible before smoke admission;
- exactly one GPU replica is allowed;
- `min_containers=0` is fixed;
- App is ephemeral, never deployed;
- startup and total timeouts are finite;
- wrapper stops the App on signal/error;
- operator documentation requires a Modal workspace/environment budget;
- no automatic retry of a full run;
- no silent GPU fallback.

Expected planning envelope for the first implementation, not a guarantee:

| Phase | Expected time |
| --- | ---: |
| First model cache | 5–20 minutes |
| GPU allocation and server start | 3–12 minutes |
| Two-task smoke | 2–6 minutes |
| Full 26-task, one-try-equivalent work | 8–20 minutes |
| Full run with up to two Aider tries | 15–40 minutes |
| First complete run | 35–90 minutes |

Do not encode a dollar price as a correctness rule because Modal pricing can
change. The dry-run plan may calculate an estimate only from an exported or
freshly verified price, and must label it an estimate with retrieval date.

## Resume And Idempotency

The happy path uses a fresh run ID. Idempotency rules:

- model cache: reuse by exact model revision and complete manifest;
- Image builds: reuse only when every build input and pin is unchanged;
- smoke: do not repeat after an identity-matching successful smoke receipt;
- full: do not overwrite a completed result;
- artifacts: local download may resume or replace only hash-matching files;
- teardown: stopping an already stopped App is successful.

For `W8_MODAL_AIDER_RESUME=1`:

1. load the prior redacted config and receipt;
2. compare every immutable and behavioral field;
3. reject any mismatch;
4. require the prior status to be incomplete or failed infrastructure;
5. use Aider's supported `--cont` flow on the single matching full directory;
6. never manufacture completed rows or rerun already completed task results;
7. rerun stats and completeness checks after continuation.

Do not resume across changes to commits, model revision, Image, hardware,
thinking behavior, edit format, tries, threads, sampling, or token limits.

## Offline Test Plan

No unit test may contact Modal, Hugging Face, GitHub, or allocate a GPU.

`tests/test_modal_aider_polyglot_cpp.py` should cover:

### Pure configuration tests

- [ ] valid plan configuration;
- [ ] missing credential names reported without values;
- [ ] invalid run IDs and Volume names;
- [ ] branch names and abbreviated revisions rejected;
- [ ] undigested SGLang Image rejected for full runs;
- [ ] numeric bounds for GPU, threads, tries, tests, sampling, and timeouts;
- [ ] paid acknowledgement required for smoke/full;
- [ ] full phase cannot skip smoke;
- [ ] local path escape rejected;
- [ ] redaction removes every sentinel secret.

### Render and command tests

- [ ] redacted plan is deterministic;
- [ ] Aider commands are argv lists, not interpolated shell strings;
- [ ] smoke command fixes C++, one try, one thread, and bounded tests;
- [ ] full command fixes C++, configured tries/threads, and no task limit;
- [ ] both commands use Aider's model-settings path and `whole` edit format;
- [ ] only `openai/glm-4.7-flash` is configured;
- [ ] SGLang flags include GLM tool/reasoning parsers, speculative decoding,
      exact TP, memory fraction, served name, and bearer auth;
- [ ] no SLIME module or custom Polyglot integration is referenced.

### Receipt and artifact tests

- [ ] model manifest rejects missing indexed shards;
- [ ] smoke gate separates infrastructure failure from wrong model code;
- [ ] full completeness requires the expected per-task result count;
- [ ] exception-only result rows fail admission;
- [ ] raw Aider pass-rate fields are preserved without pass@k relabeling;
- [ ] resume rejects identity/config mismatch;
- [ ] artifact manifest uses relative safe paths and hashes;
- [ ] receipts never contain credentials or bearer tokens.

### Source-shape tests

- [ ] `run.sh` is executable and passes `bash -n`;
- [ ] it defaults to plan mode;
- [ ] it installs a cleanup trap before any paid command;
- [ ] it verifies stopped App state;
- [ ] `modal_app.py` uses `min_containers=0` and one replica;
- [ ] runner Image receives no Modal/HF secrets;
- [ ] model downloader receives no GPU;
- [ ] results and model use separate Volumes;
- [ ] no floating `latest`/`main` identities appear in full defaults;
- [ ] example README documents the complete export-only flow.

Mock Modal objects only at the thin `modal_app.py` boundary. Most logic belongs
in the pure module and should be covered without importing Modal.

## Live Validation Ladder

Paid validation must progress in this order. Never jump directly to full:

1. offline unit tests of the pure plan renderer with fake sentinel credentials
   and no network;
2. real `plan` plus `modal token info`;
3. Modal CPU hello-world and Volume commit/readback;
4. model-cache download/verification only;
5. SGLang dummy-weight or short health bring-up when supported;
6. real-weight SGLang health and one short completion;
7. one Polyglot task, one try, one thread;
8. two-task blocking smoke;
9. full 26-task run;
10. local artifact revalidation and stopped-App verification.

Each paid step needs its own receipt. A failure must stop progression and tear
down resources.

## Documentation Work Required With Implementation

When implementation begins, update all required surfaces in the same logical
change:

- `README.md`: add the optional official Aider/Modal base-eval surface and
  distinguish it from the custom Moonlight lane;
- `ROADMAP.md`: add the question, decision gate, and evidence requirements;
- `.agents/REPO_GUIDE.md`: add repository map, boundaries, commands, security,
  and validation rules;
- `.agents/skills/w8-biayn-framework/SKILL.md`: add the operator path and
  invariants;
- example `README.md`: become the canonical export list, runbook, artifacts,
  cost controls, and troubleshooting guide;
- `.gitignore`: ignore local Modal run artifacts and any generated settings;
- tests: pin every command and safety invariant introduced by paid smokes.

Do not describe the surface as implemented in repo-wide docs before the source,
tests, and dry-run path exist.

## Implementation Checklist

### Phase A: pure contract

- [ ] Add the optional Modal dependency pin.
- [ ] Implement the pure configuration model.
- [ ] Implement validation and redaction.
- [ ] Implement redacted plan rendering.
- [ ] Implement command builders.
- [ ] Implement receipt schemas.
- [ ] Implement Aider stats parsing without rescoring.
- [ ] Implement artifact and completion validation.
- [ ] Add pure offline tests.

### Phase B: Modal infrastructure

- [ ] Implement separate model and results Volumes.
- [ ] Implement CPU model download and manifest verification.
- [ ] Implement the digest-pinned SGLang Image.
- [ ] Implement the four-GPU server and readiness gate.
- [ ] Implement per-run bearer authentication.
- [ ] Implement the pinned Aider runner Image.
- [ ] Implement smoke/full runner functions.
- [ ] Implement explicit Volume commits/reloads.
- [ ] Implement local artifact download.
- [ ] Implement bounded lifecycle and teardown verification.

### Phase C: one-command wrapper

- [ ] Implement export-only `run.sh`.
- [ ] Default to unpaid plan mode.
- [ ] Add token/profile preflight.
- [ ] Add paid acknowledgement.
- [ ] Add signal/error cleanup trap.
- [ ] Add local receipt/log capture.
- [ ] Add deterministic final summary.

### Phase D: documentation and validation

- [ ] Write the canonical example README.
- [ ] Update all repo-wide guidance listed above.
- [ ] Run focused tests and static checks.
- [ ] Run the live validation ladder through the two-task smoke.
- [ ] Convert every paid failure into a regression test.
- [ ] Run the full C++ benchmark only after smoke admission.
- [ ] Record the first complete run's immutable identities and artifact path.

## Acceptance Criteria

The setup is complete only when all of the following are true:

1. A clean clone plus `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, and
   `MODAL_PROFILE` can reach plan mode without other credentials.
2. All material run constants are supplied by exports and recorded redacted.
3. One documented script performs preflight, model caching, server start,
   smoke, full evaluation, stats, persistence, local download, and teardown.
4. No SLIME, Megatron, PIE, custom trainer, or custom Polyglot scorer is used.
5. Model, Aider, Polyglot, SGLang, Modal SDK, settings, and hardware identities
   are immutable and present in the receipt.
6. The smoke blocks infrastructure/harness failures without requiring a model
   pass.
7. The full artifact set contains exactly the pinned C++ task set and official
   Aider per-task results/histories.
8. Reported pass rates come directly from Aider and retain try semantics.
9. Model and results survive container teardown in separate Modal Volumes.
10. A local ignored artifact copy passes the same completeness checks.
11. Modal control-plane verification proves the paid App is stopped.
12. No credential appears in source, logs, plans, receipts, or artifacts.
13. Offline tests pass without Modal credentials or network.
14. Repo-wide documentation and the framework skill match the implemented
    behavior.

## Expected Operator Flow After Implementation

The final operator experience should be limited to exports plus one script.

Plan, with no paid resources:

```bash
export MODAL_TOKEN_ID='<secret>'
export MODAL_TOKEN_SECRET='<secret>'
export MODAL_PROFILE='<profile>'

export W8_MODAL_AIDER_RUN_ID="glm47-flash-aider-cpp-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AIDER_MODEL_REPO='zai-org/GLM-4.7-Flash'
export W8_MODAL_AIDER_MODEL_REVISION='<40-hex-commit>'
export W8_MODAL_AIDER_AIDER_COMMIT='<40-hex-commit>'
export W8_MODAL_AIDER_POLYGLOT_COMMIT='<40-hex-commit>'
export W8_MODAL_AIDER_SGLANG_IMAGE='lmsysorg/sglang@sha256:<digest>'
export W8_MODAL_AIDER_PHASE='plan'

bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

Full run, always including the blocking smoke:

```bash
export W8_MODAL_AIDER_PHASE='full'
export W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN='1'
export W8_MODAL_AIDER_GPU='H100!:4'
export W8_MODAL_AIDER_TRIES='2'
export W8_MODAL_AIDER_THREADS='8'
export W8_MODAL_AIDER_MAX_TOKENS='32768'
export W8_MODAL_AIDER_TEMPERATURE='0.7'
export W8_MODAL_AIDER_TOP_P='1.0'

bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

On success, the last lines must state:

```text
status: complete
benchmark: aider-polyglot-cpp-modal-base-eval
model: zai-org/GLM-4.7-Flash@<revision>
tasks: 26/26
pass_rate_1: <authoritative Aider value>
pass_rate_2: <authoritative Aider value>
modal_app_stopped: true
artifacts: .w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/<run-id>
```

Anything less is an incomplete evaluation, not a model result.
