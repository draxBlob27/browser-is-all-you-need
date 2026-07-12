# GLM-4.7-Flash Multi-SWE C++ Base Eval On Modal

Status: implementation specification only. No source lane, paid Modal smoke, or
model result described here exists yet. An implementing agent must not present
this benchmark as implemented, operationally proven, or scored until every
offline gate and the paid validation ladder in this document has passed.

Target: add an optional, repo-owned base evaluation of
`zai-org/GLM-4.7-Flash` on the 50 C++ instances in
`ByteDance-Seed/Multi-SWE-bench_mini`. Modal hosts the four-H100 SGLang server,
the per-task isolated grading sandboxes, and durable artifacts. The evaluation
must reuse the existing Multi-SWE prompt, strict patch parser, path policy,
official-image test contract, oracle proof, and summary semantics.

This document is written as the implementation contract for an AI coding
agent. It deliberately separates decisions already made from work still to be
proved with source, tests, and paid receipts.

## Objective

Answer exactly this question:

> How does the base `zai-org/GLM-4.7-Flash` checkpoint perform on the C++
> subset of `ByteDance-Seed/Multi-SWE-bench_mini` under the repository's
> existing single-turn unified-diff prompt and correctness harness, when model
> serving and isolated grading run on Modal?

The first implementation is a parity lane for
`examples/slime/moonlight_multi_swe_cpp/`. It changes the model and execution
infrastructure, not the task contract.

The result is:

- a repo-owned Multi-SWE C++ result;
- one independent model response per task;
- strict task-level pass rate with one sample per task;
- correctness-only, with no PIE speed metrics;
- suitable for a descriptive comparison with a Moonlight run only when all
  task, prompt, image, harness, sampling, and timeout identities match.

The result is not an official Multi-SWE leaderboard result. Do not use the
words "official Multi-SWE score" or "leaderboard score" in receipts, summaries,
documentation, or reports.

## Fixed Scope And Non-Goals

The initial lane is intentionally narrow.

It must:

- evaluate only the 50 allowlisted C++ tasks;
- use the existing single-turn issue-to-patch prompt;
- accept exactly one fenced unified diff in strict scoring;
- keep recovered-format grading diagnostic-only;
- grade with the dataset `test_patch` and the official per-instance image;
- run the dataset `fix_patch` through the same Modal grader before model load;
- use base GLM-4.7-Flash weights without fine-tuning;
- use an ephemeral Modal App and durable Modal Volumes;
- default to a redacted, no-spend plan;
- require explicit acknowledgement before any paid phase;
- run a blocking two-task smoke before a full run;
- explicitly terminate every Sandbox and stop/verify the App on every exit.

It must not:

- run PIE optimization, SFT, GRPO, SLIME, Megatron, or SkyPilot;
- write a trainer;
- call Aider or label the result as an Aider result;
- add SWE-agent, repository browsing, shell tools, or multi-turn editing;
- show `fix_patch`, `test_patch`, hidden test buckets, or oracle-derived hunk
  locations to the model;
- replace the current Moonlight Multi-SWE lane;
- use the generic `w8-biayn-multi-swe-cpp` image for a standard result;
- use mutable model, dataset, SGLang, or grader image identities;
- silently relax the parser when GLM returns reasoning or tokenizer markers;
- report pass@k, because the initial contract has exactly one sample per task;
- report PIE runtime speedup or `correct_and_faster_rate`.

If a later experiment needs SWE-agent or another agentic file-state workflow,
create a separately named lane and result family. Do not silently change this
single-turn baseline.

## Required Reading For The Implementing Agent

Before changing source, read completely:

1. `AGENTS.md`
2. `README.md`
3. `ROADMAP.md`
4. `.agents/skills/w8-biayn-framework/SKILL.md`
5. this document
6. `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_MODAL_BASE_EVAL_PLAN.md`
7. `examples/modal/glm47_flash_aider_polyglot_cpp/README.md`
8. `examples/modal/glm47_flash_aider_polyglot_cpp/modal_app.py`
9. `src/w8_biayn/modal_aider_polyglot_cpp.py`
10. `tests/test_modal_aider_polyglot_cpp.py`
11. `docs/MOONLIGHT_MULTI_SWE_CPP_BASE_EVAL_IMPLEMENTATION_PLAN.md`
12. `examples/slime/moonlight_multi_swe_cpp/README.md`
13. `src/w8_biayn/integrations/slime_multi_swe_cpp.py`
14. `tests/test_slime_multi_swe_cpp.py`

The implementing agent must also verify the APIs against the repository-pinned
Modal SDK rather than coding from memory. Relevant current official references:

- Modal Sandboxes: <https://modal.com/docs/guide/sandboxes>
- Sandbox networking and `block_network`:
  <https://modal.com/docs/guide/sandbox-networking>
- Sandbox filesystem transfer: <https://modal.com/docs/guide/sandbox-files>
- External registry images: <https://modal.com/docs/guide/existing-images>
- Volume semantics and read-only subpath mounts:
  <https://modal.com/docs/guide/volumes>
- Ephemeral Apps and local entrypoints: <https://modal.com/docs/guide/apps>
- App stop/list commands: <https://modal.com/docs/cli/latest/app>

The repository currently pins `modal==1.5.2`. If that pin changes during
implementation, rerun all source-shape tests and the CPU Sandbox validation
before any GPU work.

## Architecture Decision

Use one native, gVisor-isolated Modal Sandbox per oracle or candidate patch.
Create each Sandbox directly from the exact digest-locked official
`mswebench/*` image and set `block_network=True`.

Do not use:

- a long-lived CPU Function that executes generated C++ in its own container;
- nested Docker in a normal Modal Function;
- the experimental VM-Sandbox Docker runtime for the first implementation;
- a generic compiler image plus fresh GitHub clones;
- a shared writable repository checkout between tasks.

The native Sandbox path is the closest Modal equivalent to the current
one-container-per-patch Docker grader. It retains the official image's prepared
checkout, build tree, compiler, and offline assets while isolating each patch
and blocking outbound network. It does not reproduce Docker flags such as
`--pids-limit`, `--cap-drop`, or the exact tmpfs declaration. Therefore this is
a new, explicitly fingerprinted Modal harness backend. The dataset `fix_patch`
oracle and the paid CPU parity ladder are mandatory evidence that the backend
is valid; do not assume Docker/Modal equivalence.

```text
operator shell
  |
  | run.sh: validate exports, render plan, require paid acknowledgement
  v
ephemeral Modal App: w8-glm47-multi-swe-cpp-<run-id>
  |
  +-- preflight_remote_run()                 CPU, no GPU
  |     `-- reject stale/concurrent run state
  |
  +-- prepare_dataset_and_oracle()           CPU control + Modal Sandboxes
  |     +-- exact dataset revision and JSONL hash
  |     +-- checked-in 50-image digest lock
  |     +-- pinned simdjson offline dependencies
  |     +-- one network-blocked official-image Sandbox per fix_patch
  |     `-- blocking all-task oracle proof
  |
  +-- preload_model()                        CPU, model Volume only
  |     `-- complete exact-revision HF snapshot and manifest
  |
  +-- SGLangServer                           H100!:4, one replica
  |     +-- authenticated OpenAI-compatible API
  |     +-- separated reasoning_content/content
  |     `-- scale-to-zero after generation
  |
  +-- local orchestrator
  |     +-- two-task generation + grading smoke
  |     +-- generate and persist all 50 full responses
  |     +-- release GPU server
  |     +-- grade full responses in bounded parallel Sandboxes
  |     `-- recompute summaries and validate completeness
  |
  `-- results Volume
        +-- immutable identities and oracle proof
        +-- per-task requests/responses/records/logs
        +-- summary, receipt, artifact manifest
        `-- bounded, reconciled local download under .w8-biayn/
```

The ordering is deliberate. The full oracle gate finishes before model loading
or GPU startup. After smoke admission, all full model responses are generated
and durably persisted before long C++ grading. The SGLang scale-down window is
then reduced to two seconds so four H100s do not stay allocated during builds,
tests, and artifact transfer.

## Reuse Versus New Code

Do not fork benchmark semantics.

| Concern | Source of truth | Required implementation action |
| --- | --- | --- |
| C++ task filtering and normalization | `slime_multi_swe_cpp.py` | Reuse public functions; do not re-parse the dataset differently. |
| Prompt text | `build_prompt` | Reuse byte-for-byte and persist its SHA-256. |
| Strict/recovery parsing | `parse_patch_response`, `recover_patch_response` | Reuse; pass only `message.content`. |
| Forbidden path policy | `preflight_patch_paths` | Reuse unchanged. |
| Official-image shell contract | current official-instance script | Extract a public backend-neutral builder and use it from Docker and Modal. |
| Test result classification | current Docker result handling | Extract one public classifier used by both backends. |
| Oracle cache key and summary | current Multi-SWE integration | Add the Modal backend identity without changing correctness semantics. |
| Eval aggregation | `aggregate_multi_swe_records` | Reuse and add Modal provenance outside the metric payload. |
| GLM model snapshot and SGLang admission | existing Modal/Aider lane | Extract or reuse shared pure helpers; do not fork model completeness rules. |
| Modal lifecycle and artifact download | existing Modal/Aider lane | Reuse the proven pattern with lane-specific config and receipts. |

The current Multi-SWE module has a SLIME-oriented filename, but its prompt,
parser, grader, and aggregation are repository benchmark logic. Do not perform
a risky 2,900-line rename solely for aesthetics. A small extraction of public,
backend-neutral helpers is appropriate; a wholesale rewrite is not.

The current Modal/Aider module contains GLM-serving logic that is not
Aider-specific. Prefer extracting pure shared helpers into a small module such
as `src/w8_biayn/modal_glm47.py`, while keeping compatibility wrappers so the
existing Aider lane and its tests do not change behavior.

## Intended Repository Files

Add:

```text
examples/modal/glm47_flash_multi_swe_cpp/
  README.md                         canonical operator runbook
  run.sh                            only supported operator entrypoint
  modal_app.py                      Modal resources and orchestration boundary
  mswebench-images.lock.json        checked-in exact linux/amd64 image lock
src/w8_biayn/modal_multi_swe_cpp.py
                                    pure config, plan, request, receipt,
                                    resume, aggregation, and artifact logic
tests/test_modal_multi_swe_cpp.py
docs/GLM47_FLASH_MULTI_SWE_CPP_MODAL_BASE_EVAL_IMPLEMENTATION_PLAN.md
```

Optionally add a small shared pure module:

```text
src/w8_biayn/modal_glm47.py
```

Modify only as needed:

```text
src/w8_biayn/modal_aider_polyglot_cpp.py
src/w8_biayn/integrations/slime_multi_swe_cpp.py
tests/test_modal_aider_polyglot_cpp.py
tests/test_slime_multi_swe_cpp.py
```

Update with the implementation:

```text
README.md
ROADMAP.md
.agents/REPO_GUIDE.md
.agents/skills/w8-biayn-framework/SKILL.md
.gitignore                         only if .w8-biayn/ is no longer sufficient
```

Keep `modal` imports out of `src/w8_biayn/modal_multi_swe_cpp.py` and any
shared pure contract module. Only `modal_app.py` should require the optional
Modal extra. Offline tests must import every pure contract without credentials,
network, Docker, or GPUs.

## Single-Script Operator Contract

The only supported entrypoint will be:

```bash
bash examples/modal/glm47_flash_multi_swe_cpp/run.sh
```

It accepts no positional configuration. `--help` may print the export
contract, but configuration remains export-only.

The wrapper must:

1. install cleanup traps before authentication or any paid command;
2. verify it is running from the repository root;
3. require `uv` and the pinned Modal extra;
4. parse all exports through the pure Python config model;
5. write deterministic `plan.json` and `config.redacted.json` locally;
6. verify Modal authentication without printing tokens;
7. exit in `plan` phase before `modal run` or Sandbox/Image creation;
8. require `W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1` for smoke/full;
9. reject another active App with the deterministic run App name;
10. run the ephemeral Modal App;
11. download committed success or failure artifacts;
12. lower the server scale-down window after generation;
13. explicitly stop the App on success, error, signal, or interruption;
14. verify stopped state through the control plane;
15. reconcile the local artifact copy byte-for-byte with the results Volume;
16. revalidate summaries and receipts locally before printing any score.

The wrapper must never deploy an App or create a schedule.

## Exported Configuration

Use the `W8_MODAL_MULTI_SWE_` prefix. Do not reuse `SLIME_*`,
`W8_MODAL_AIDER_*`, GCP, or W&B configuration.

### Local control-plane credentials

```bash
export MODAL_TOKEN_ID='<secret>'
export MODAL_TOKEN_SECRET='<secret>'
export MODAL_PROFILE='<profile-name>'
export MODAL_ENVIRONMENT='<optional-environment>'
```

Modal tokens stay in the local process. Never attach them to an Image,
Function, Server, Sandbox, subprocess, or receipt.

`HF_TOKEN` is optional for model/dataset download. If present, it reaches only
the relevant CPU downloader. It must not reach the SGLang server, local
orchestrator request artifacts, grading Sandboxes, or results.

### Required immutable identities

```bash
export W8_MODAL_MULTI_SWE_RUN_ID='glm47-mswe-cpp-<utc-suffix>'
export W8_MODAL_MULTI_SWE_MODEL_REPO='zai-org/GLM-4.7-Flash'
export W8_MODAL_MULTI_SWE_MODEL_REVISION='<40-lowercase-hex-HF-commit>'
export W8_MODAL_MULTI_SWE_DATASET_REVISION='<40-lowercase-hex-HF-commit>'
export W8_MODAL_MULTI_SWE_SGLANG_IMAGE='lmsysorg/sglang@sha256:<64-hex>'
```

The dataset repository URL, expected filename, five allowlisted repositories,
and Transformers compatibility commit remain fixed in source. The existing
official Transformers commit
`76732b4e7120808ff989edbd16401f61fa6a0afa` remains required unless a separate
validated migration changes both Modal lanes.

The checked-in image lock is also immutable input. Its file SHA-256, schema,
dataset revision, expected task set, and all image digests must appear in the
plan and receipt.

### Supported phases

```text
W8_MODAL_MULTI_SWE_PHASE=plan   # default, no paid resources
W8_MODAL_MULTI_SWE_PHASE=smoke  # full oracle + real model + two model tasks
W8_MODAL_MULTI_SWE_PHASE=full   # full oracle + smoke + all 50 model tasks
```

Full cannot skip smoke. Smoke cannot skip the all-task oracle gate. There is
no `skip_oracle`, `skip_smoke`, mutable-image, or generic-image override.

### Fixed first-run defaults

```text
expected_cpp_tasks                 50
samples_per_task                   1
smoke_tasks                        2, fixed by checked-in task IDs
gpu                                H100!:4
tensor_parallel_size               4
server_replicas                    1
server_min_containers              0
server_max_containers              1
server_scaledown_window_seconds    1200 before generation ends
server_post_generation_window      2
sglang_mem_fraction                0.8
sglang_max_running_requests        16
startup_timeout_seconds            3600
max_tokens                         32768
temperature                        0.0
top_p                              1.0
test_timeout_seconds               1200
sandbox_cpu_request_and_limit      2.0
sandbox_memory_request_and_limit   2048 MiB
sandbox_lifetime_seconds           1320 or greater bounded overhead
grader_concurrency                 4
generation_concurrency             8
artifact_download_concurrency      16
resume                             false
```

Any configurable override must be range-validated and included in the
identity mapping. The initial full benchmark should keep the defaults above.
A sampling, token, resource, timeout, or concurrency change creates a distinct
run configuration and requires a fresh run ID unless exact resume compatibility
is proven.

GLM-4.7-Flash can spend more than 8,192 completion tokens in reasoning before
emitting editable content. Keep the 32,768-token response bound used by the
existing Modal lane. It remains inside the pinned checkpoint's declared
context window. Do not lower it for the full run without a new smoke and
distinct identity.

### Volumes and local root

Recommended defaults:

```text
W8_MODAL_MULTI_SWE_MODEL_VOLUME=w8-glm47-flash-models
W8_MODAL_MULTI_SWE_DATA_VOLUME=w8-multi-swe-cpp-data
W8_MODAL_MULTI_SWE_RESULTS_VOLUME=w8-multi-swe-cpp-results
W8_MODAL_MULTI_SWE_LOCAL_ROOT=.w8-biayn/modal/glm47-flash-multi-swe-cpp
```

All three Volume names must be distinct except that the exact-revision model
cache may deliberately reuse the existing Modal/Aider model Volume. The model
Volume must never be mounted into a grader. The results Volume must never be
mounted into a grader. Only checksum-pinned simdjson dependency subpaths may be
mounted read-only into affected graders.

## Configuration Validation And Redaction

The pure config model must reject:

- missing credential variable names without echoing their values;
- mutable `main`, branches, abbreviated SHAs, uppercase SHAs, and image tags;
- model repositories other than `zai-org/GLM-4.7-Flash`;
- dataset task counts other than 50 for the first full configuration;
- GPU values other than strict `H100!:4`;
- more than one server replica or a nonzero warm pool;
- samples per task other than one;
- smoke task lists not equal to the checked-in list;
- nonzero temperature for the first full configuration;
- unsafe run IDs, Volume names, or local paths;
- a local artifact root outside `.w8-biayn/`;
- smoke/full without explicit paid acknowledgement;
- resume against a complete or identity-mismatched run;
- full evaluation from a dirty Git tree.

Plan output must redact:

- Modal token ID and secret;
- `HF_TOKEN`;
- the per-run SGLang bearer;
- any future value whose name includes token, secret, password, key, or
  credential.

Tests must search nested mappings, argv arrays, logs, errors, receipts, and
artifact files for sentinel secret values.

## Dataset And Image Lock Contract

The source dataset is the exact-revision Hugging Face snapshot of
`ByteDance-Seed/Multi-SWE-bench_mini`, file
`multi_swe_bench_mini.jsonl`.

CPU preparation must record:

- dataset repository and exact 40-hex revision;
- raw JSONL byte count and SHA-256;
- total source row count;
- selected C++ row count, exactly 50;
- sorted task IDs and repo counts;
- prompt SHA-256 and task JSON SHA-256 per task;
- the exact shared dataset/oracle schema versions;
- simdjson dependency commits, URLs, SHA-256 values, and bundle fingerprint.

The source lock file
`examples/modal/glm47_flash_multi_swe_cpp/mswebench-images.lock.json` is a
reviewed benchmark input, not run evidence. It must contain:

```json
{
  "schema_version": 1,
  "dataset_repo": "ByteDance-Seed/Multi-SWE-bench_mini",
  "dataset_revision": "<40-hex>",
  "platform": "linux/amd64",
  "expected_tasks": 50,
  "tasks": {
    "<instance-id>": {
      "tag": "mswebench/<lowercase-org>_m_<lowercase-repo>:pr-<number>",
      "digest": "mswebench/<repo>@sha256:<64-hex>"
    }
  }
}
```

Normal plan/smoke/full runs must consume the checked-in lock; they must not
resolve mutable tags on the fly. Add a maintainer-only, repo-owned lock
generation/verification command. It must resolve the `linux/amd64` manifest,
verify the task/tag mapping, write deterministic sorted JSON, and never run as
an implicit part of a paid benchmark.

Modal must construct each grader Image from the exact `repository@sha256`
reference. Modal's external-image cache treats pulled tags as immutable, which
is another reason mutable tags are forbidden here.

Before GPU allocation, eagerly build/import every selected Modal Image and
prove that a Sandbox can execute `bash`, `git`, `sha256sum`, `timeout`, CMake,
and the task image's `/home/fix-run.sh` contract. A missing binary or failed
Image import is infrastructure failure, not a model result.

## Prompt And Inference Contract

Call the existing `build_prompt` byte-for-byte. The prompt contains:

- repository full name;
- instance ID;
- base ref;
- title;
- issue/PR body, deterministically truncated by the existing limits;
- resolved issue context;
- the exact single fenced-diff output contract.

It must not contain:

- `fix_patch` or its hashes/hunk locations;
- `test_patch` or its hashes/hunk locations;
- test buckets or stored run results;
- official image filesystem contents;
- oracle logs or failure messages;
- the correct answer.

Send one non-streaming OpenAI-compatible request per task:

```json
{
  "model": "glm-4.7-flash",
  "messages": [{"role": "user", "content": "<exact saved prompt>"}],
  "max_tokens": 32768,
  "temperature": 0.0,
  "top_p": 1.0,
  "stream": false
}
```

Persist the exact secret-free request and raw response. The bearer belongs only
in the HTTP header and must never be serialized.

SGLang must expose separated `reasoning_content` and editable `content`. Feed
only `message.content` to the strict Multi-SWE parser. Do not concatenate,
strip, repair, or place reasoning in the patch. Record reasoning presence,
character count, token usage, finish reason, and response keys. Raw reasoning
may be retained in the per-task raw API response because it contains no hidden
benchmark material, but summaries and console output should use lengths and
counts rather than printing it.

The strict parser remains authoritative:

````text
```diff
diff --git a/path/file.cpp b/path/file.cpp
...
```
````

Prose, a second block, raw diffs, binary patches, unsafe paths, forbidden
files, or a literal terminal tokenizer marker outside the block remain strict
failures. Recovery parsing remains diagnostic and cannot alter reward, pass
rate, or `all_tests_pass`.

## Shared GLM Server Contract

Reuse the existing Modal GLM-4.7-Flash server invariants:

- exact public model revision cached in a model Volume;
- reject an index without every referenced weight shard;
- digest-pinned SGLang base Image;
- official Transformers commit
  `76732b4e7120808ff989edbd16401f61fa6a0afa` overlaid and recorded;
- image build fails unless `glm4_moe_lite` is registered;
- strict `H100!:4`, tensor parallel size four;
- one replica, `min_containers=0`, `max_containers=1`;
- GLM tool and reasoning parser flags required by the pinned SGLang surface;
- existing EAGLE speculative-decoding flags, unless a separately tested
  migration intentionally changes both Modal lanes;
- per-run random bearer passed only to server and local orchestrator;
- startup ceiling 3,600 seconds with child-process early-exit polling;
- `/health`, `/v1/models`, and authenticated chat admission;
- served model list exactly `glm-4.7-flash`;
- response-shape diagnostics never containing the bearer;
- raw SGLang log remains ephemeral;
- only a bearer-redacted bounded tail may enter `server.failure.json`.

The authenticated admission prompt must allow up to
`min(max_tokens, 2048)` completion tokens and require both a
`reasoning_content` field and nonempty editable `content`. This is server
admission, not a model benchmark task.

## Modal Grader Sandbox Contract

For every oracle or model patch:

1. Create a fresh Sandbox from the task's exact digest-locked Image.
2. Set `block_network=True`.
3. Set CPU request and hard limit to two cores.
4. Set memory request and hard limit to 2,048 MiB.
5. Set a finite Sandbox lifetime exceeding the 1,200-second test timeout only
   by bounded orchestration overhead.
6. Do not attach any Secret.
7. Do not attach model or results Volumes.
8. For affected simdjson tasks only, attach the two exact checksum-pinned data
   Volume subpaths read-only at the current expected dependency locations.
9. Write the candidate patch to `/home/fix.patch` through the Sandbox
   filesystem API.
10. Execute the shared official-instance shell script with an exec timeout.
11. Drain stdout and stderr while the process runs; do not leave unconsumed
    buffered output.
12. Record return code, parsed CTest count, bounded log tail, total output
    bytes, output SHA-256, truncation flag, elapsed time, Sandbox ID, Modal
    Image identity, source digest, and resource limits.
13. Terminate with `wait=True` and detach in `finally`, including timeout,
    cancellation, parser errors, and client exceptions.

The shared shell contract must continue to verify:

- repository checkout exists at the task's expected `/home/<repo>` path;
- current HEAD exactly matches the task base ref;
- image `/home/test.patch` SHA-256 matches the dataset test patch;
- trusted test patch applies;
- candidate patch applies without editing forbidden paths;
- CTest reports a positive discovered-test count;
- the four simdjson offline-dependency fixes remain narrow;
- PR 958 preserves its GCC 7 `-Weffc++` compatibility behavior;
- nlohmann PR 2099 runs the 49 unaffected CTests and explicit CBOR/MessagePack
  cases.

Do not copy the entire repository out of the Sandbox. Do not expose the
prepared checkout, tests, or oracle patch to the model server.

## Blocking Oracle Admission

Smoke and full both require an all-task oracle gate before model loading.

For each of the 50 tasks:

- use `fix_patch` as the candidate patch;
- grade through the exact Modal Sandbox backend used for model responses;
- require return code zero;
- require `tests_collected > 0`;
- require no harness, trusted-patch, base-ref, image, or timeout failure;
- persist one record immediately after completion;
- compute an oracle cache key over task patches, base ref, image digest,
  platform, shared script hash, protocol version, resource limits, offline
  dependency bundle, and Modal backend version.

Resume may reuse only passing oracle records with an identical cache key.
Missing, failed, provisional, or stale records are rerun. Persist a summary and
provisional manifest after every task so interruption cannot erase progress.

Admission requires:

```text
manifest.admitted                           true
oracle.summary.complete                     true
oracle.summary.all_passed                   true
oracle.summary.expected_task_count          50
oracle.summary.record_count                 50
oracle.summary.passed_count                 50
every record.tests_collected                 > 0
every task/image-lock/cache-key mapping      exact
```

Copy the admitted proof into the final eval artifact set. Do not rerun it
during aggregation and do not infer setup cleanliness from model results.

## Smoke And Full Sequence

### Plan

Plan is local and no-spend. It validates config, Git cleanliness rules, dataset
and image-lock source shape, redaction, local paths, and expected commands. It
may call `modal token info`, but it must not run `modal run`, build Images,
create Sandboxes, call Functions, or allocate GPUs.

### Smoke

Smoke is paid and performs:

1. remote stale-run admission;
2. exact dataset staging;
3. all-50-task Modal oracle admission;
4. exact model snapshot preload;
5. real four-H100 SGLang startup and authenticated admission;
6. one response for each of two fixed smoke task IDs;
7. one Modal grader Sandbox per smoke response;
8. per-task artifact persistence;
9. smoke summary/completeness checks;
10. GPU scale-down, artifact download, Sandbox cleanup, App stop, and stopped
    verification.

The two smoke tasks should be checked in and chosen to cover two repositories.
Oracle preparation already exercises the special simdjson/nlohmann paths, so
do not choose a pathologically slow smoke solely for setup coverage.

Smoke admission does not require a model pass. It requires:

- two successful API transports;
- two complete raw response artifacts;
- no exception-only or missing record;
- two grading executions reaching a model-outcome classification;
- no Sandbox/image/base/test-patch/harness infrastructure failure;
- valid summaries and durable artifacts.

An invalid patch, compile failure, timeout caused by the candidate, or failing
tests is a legitimate model outcome. Server auth failure, Sandbox creation
failure, missing official assets, zero oracle tests, or incomplete artifacts
is infrastructure failure.

### Full

Full always includes the smoke above, then:

1. generate all 50 full responses with bounded concurrency;
2. persist each request/response immediately under its task ID;
3. require a complete 50-response generation set;
4. reduce SGLang scale-down to two seconds;
5. grade responses with at most four concurrent Sandboxes;
6. persist each grader record and bounded log separately;
7. aggregate exactly 50 records;
8. copy the oracle proof into full eval artifacts;
9. validate summary, artifact manifest, and receipt;
10. download, stop, verify stopped state, and locally revalidate.

Do not keep the GPU server warm while the full C++ build/test phase runs.

## Model Outcome And Infrastructure Taxonomy

Model outcomes included in the denominator:

- `passed`;
- `invalid_format`;
- `invalid_files`;
- `patch_apply_error`;
- `compile_error`;
- `timeout` after the candidate was admitted and executed;
- `tests_failed`;
- candidate-caused `no_tests_collected`, if the oracle for the same immutable
  setup passed and the classifier can prove the Sandbox itself was healthy.

Infrastructure failures block run admission:

- dataset/image-lock mismatch;
- missing or failed oracle proof;
- official Image import or Sandbox startup failure;
- base ref or trusted test patch mismatch;
- missing offline dependency mount;
- SGLang startup, auth, health, model identity, or transport failure;
- missing response/record/log/receipt artifacts;
- unsafe artifact paths or byte mismatch;
- inability to terminate a Sandbox or verify the App stopped.

A transient Sandbox API failure may receive one bounded infrastructure retry
using the same saved response. Never regenerate the model response as an
implicit grader retry. Record the retry and both Sandbox IDs. A second
infrastructure failure blocks the run.

## Metrics And Interpretation

Reuse the current Multi-SWE summary fields:

- `task_count` and `sample_count`;
- strict `pass_rate`;
- `mean_reward` and `mean_best_reward`;
- invalid-format and invalid-file rates;
- patch-apply, compile-error, timeout, tests-failed, harness-error, and
  no-tests-collected rates;
- reason counts;
- per-repository summaries;
- diagnostic `recovered_*` rates;
- `oracle_setup_check`.

Add provenance outside the existing metric calculation:

- model and dataset revisions;
- SGLang/Transformers/Modal identities;
- prompt/parser/harness versions and hashes;
- image-lock hash and per-task digest set;
- sampling and token configuration;
- Sandbox resource/network policy;
- generation/grading elapsed time and infrastructure retries;
- response finish-reason and token-usage distributions.

Recovered passes remain diagnostics. They never become strict passes. A run
with any infrastructure-failed task is incomplete and must not print a model
score.

For a descriptive Moonlight comparison, require identical task IDs, prompt
hashes, official image digests, oracle cache keys, parser/path policy, timeout,
and one-sample configuration. If the Moonlight run used Docker and this run
used Modal Sandboxes, label the backend difference as a confounder even when
both oracle proofs pass.

## Artifact Contract

Remote and reconciled local layout:

```text
.w8-biayn/modal/glm47-flash-multi-swe-cpp/runs/<run-id>/
  plan.json
  config.redacted.json
  source.receipt.json
  dataset.receipt.json
  model-cache.receipt.json
  image-lock.json
  image-lock.sha256
  server.failure.json                 # failure only, bearer-redacted
  admission.failure.json              # failure only, response shape only
  admission.response.json             # success, response shape only
  server.runtime.json
  server.receipt.json
  data/
    manifest.json
    eval/cpp.jsonl
    tasks/<instance-id>/task.json
    sandbox-images.json
    offline-dependencies.json
    oracle.records.jsonl
    oracle.summary.json
  smoke/
    requests/<instance-id>.json
    responses/<instance-id>.json
    records/<instance-id>.json
    logs/<instance-id>.log
    records.jsonl
    summary.json
  full/
    requests/<instance-id>.json
    responses/<instance-id>.json
    records/<instance-id>.json
    logs/<instance-id>.log
    records.jsonl
    oracle.records.jsonl
    summary.json
  run_receipt.json
  artifact_manifest.json
```

Write per-task files first and derive JSONL/summary files from them. This avoids
concurrent append corruption and makes resume deterministic. Each task file has
one writer. Canonical JSONL is sorted by task ID and recomputed before final
admission.

The artifact manifest must include safe relative paths, sizes, SHA-256 values,
and total bytes. Recursive download must:

- use Modal SDK 1.5.2's exact `FileEntryType.FILE` classification;
- skip directories, symlinks, and all non-regular entries;
- validate the complete remote path list before writing locally;
- reject absolute paths, traversal, duplicates, and prefix escapes;
- use the async Volume API with at most 16 reads in flight;
- require byte equality for an existing local file;
- print bounded progress without response content or secrets.

Generated data and artifacts remain under `.w8-biayn/` and must not be
committed.

## Resume And Idempotency

Fresh run IDs are the normal path. `W8_MODAL_MULTI_SWE_RESUME=1` is only for an
incomplete exact-identity run.

Identity comparison must cover:

- repository Git commit and source file hashes;
- model repo/revision and model manifest;
- dataset repo/revision/JSONL hash/task IDs;
- image-lock hash and every per-task digest;
- shared Multi-SWE schema, oracle protocol, prompt, parser, path policy, shell
  script, and result classifier versions;
- simdjson dependency bundle and special-case harness revisions;
- Modal SDK, SGLang Image, Transformers commit, server argv, and GPU;
- token/sampling/request fields;
- Sandbox network/resource/time/output-capture policy;
- smoke task list and all concurrency values that affect execution.

Resume rules:

- completed runs are immutable and cannot resume;
- successful oracle records reuse only by exact oracle cache key;
- saved model responses reuse only by exact request hash and model identity;
- complete model-outcome grader records reuse only by response hash and grader
  cache key;
- infrastructure-failed records retry once; they are never counted;
- local downloads overwrite only hash-identical files;
- stopping an already stopped App succeeds;
- simultaneous writers for one run ID are unsupported and must be rejected by
  the active-App preflight.

## Security Contract

- Modal control credentials stay local.
- `HF_TOKEN` reaches CPU downloaders only.
- The random SGLang bearer reaches the server and request orchestrator only.
- Grading Sandboxes receive no secrets and no model/results Volume.
- Grading Sandboxes have outbound networking fully blocked.
- Only pinned simdjson dependency subpaths are mounted, read-only, when needed.
- The model request contains public issue context only, never oracle fields.
- Generated patches are untrusted and run only in fresh isolated Sandboxes.
- Server raw logs remain ephemeral because argv may contain the bearer.
- Console errors and failure summaries must be bearer-redacted.
- No generated code, reasoning, or test log should be printed in the final
  concise summary.
- Plans, receipts, and artifacts are scanned for sentinel secrets in tests.
- A dirty source tree cannot produce an admitted full benchmark result.

## Spend And Lifecycle Controls

- `plan` is the default and creates no paid resources.
- Smoke/full require explicit acknowledgement.
- Workspace budget/spend alerts are an operator prerequisite.
- Dataset/image/oracle work runs before model load or GPU allocation.
- Full is impossible before the real two-task smoke.
- Exactly one strict four-H100 server replica is allowed.
- Server `min_containers=0`; no persistent warm pool.
- Generate all full responses before long grading.
- Reduce the server scale-down window to two seconds after generation.
- Every Sandbox has a finite lifetime and per-exec timeout.
- Every Sandbox terminates/detaches in `finally`.
- The wrapper stops the App on normal exit and signals.
- Control-plane stopped-state verification is required for result admission.
- Do not encode a dollar estimate as a correctness rule; pricing changes.

## Offline Test Plan

No offline test may contact Modal, Docker Hub, Hugging Face, GitHub, or a GPU.
Mock Modal only at the thin boundary.

### Pure configuration and plan

- valid deterministic redacted plan;
- missing credential names without values;
- invalid run IDs, Volume names, and path escapes;
- immutable model/dataset/Image identities only;
- strict `H100!:4`, one replica, zero warm containers;
- paid acknowledgement for smoke/full;
- full always includes smoke and oracle;
- samples per task fixed to one;
- numeric bounds for tokens, timeouts, memory, CPU, and concurrency;
- dirty Git full-run rejection;
- every sentinel secret absent from nested plan content.

### Dataset and image lock

- exact 50-task C++ set across the five allowlisted repositories;
- raw JSONL and per-task hashes recorded;
- lock schema, dataset revision, platform, task IDs, lowercase tags, and exact
  digests validated;
- missing, duplicate, mutable, cross-repository, or non-amd64 lock rows rejected;
- prompt bytes match the existing shared builder;
- prompt/request excludes every oracle and hidden-test sentinel;
- lock generator output is deterministic from registry fixtures.

### Inference

- request JSON is deterministic and secret-free;
- server command retains model, TP, parser, EAGLE, auth, memory, and served-name
  flags;
- model snapshot rejects missing indexed shards;
- admission requires separated reasoning metadata and editable content;
- only `message.content` enters the strict parser;
- empty/truncated content and terminal token behavior are classified correctly;
- raw response persistence never captures the HTTP authorization header.

### Sandbox adapter

Use a fake Sandbox object to assert:

- exact digest-locked Image, never a tag;
- `block_network=True`;
- exact CPU/memory/lifetime settings;
- no secrets, model Volume, or results Volume;
- read-only simdjson mounts only on affected tasks;
- `/home/fix.patch` receives exact bytes;
- shared shell script and exec timeout are used;
- stdout/stderr are drained and bounded;
- timeout and contract exit codes classify identically to Docker fixtures;
- one infrastructure retry reuses the same response;
- terminate and detach happen on success, timeout, cancellation, and exception.

### Oracle, aggregation, resume, and artifacts

- oracle remains provisional until all 50 exact-key passes exist;
- zero tests never pass;
- stale/missing/failed oracle records rerun while exact passes reuse;
- per-task persistence survives an injected interruption;
- model outcomes and infrastructure failures remain distinct;
- summary recomputes from per-task records and rejects mismatches;
- recovered diagnostics never alter strict metrics;
- no PIE speed metrics appear;
- resume rejects every identity mismatch listed above;
- completed run cannot resume;
- artifact manifest paths and hashes are safe;
- download accepts only exact `FileEntryType.FILE` and reconciles bytes;
- no receipt can be admitted before App stopped verification.

### Source-shape regressions

- `run.sh` is executable and passes `bash -n`;
- cleanup trap is installed before the first paid command;
- plan exits before `modal run`;
- no `modal deploy` or schedule exists;
- no `SLIME_*`, Aider, SkyPilot, or trainer import exists in the new lane;
- server is one replica with `min_containers=0`;
- grader construction always sets `block_network=True`;
- no mutable `latest` or `main` identities appear;
- all generated paths remain under `.w8-biayn/`;
- the canonical lane README documents the complete operator contract.

Run the existing focused suites too. Shared helper extraction must not regress
the proven lanes.

## Paid Validation Ladder

Never jump directly to the full run. Execute and retain receipts in order:

1. offline focused tests and static checks;
2. real plan and `modal token info`;
3. CPU Function hello-world plus results Volume put/readback;
4. one digest-locked official Image import and shell probe;
5. one network-blocked Sandbox filesystem/write/exec/terminate test;
6. one ordinary task `fix_patch` parity: local Docker result versus Modal;
7. one special simdjson/nlohmann oracle parity task;
8. all 50 Modal oracle tasks with complete passing proof;
9. exact model cache download/validation only;
10. real-weight four-H100 SGLang health/models/admission probe;
11. one saved Multi-SWE prompt through model, parser, and Sandbox;
12. fixed two-task blocking smoke;
13. full 50-response generation, early GPU release, and full grading;
14. local artifact reconciliation, summary recomputation, and stopped-App
    verification.

Each step blocks the next. Convert every paid infrastructure failure into an
offline regression test before continuing.

The local-Docker-versus-Modal parity steps compare setup behavior only. They do
not make the Modal backend identical to Docker; the final receipt must still
name `modal-sandbox` as its harness backend.

## Documentation Work Required With Implementation

Update every required surface in the same logical change:

- `examples/modal/glm47_flash_multi_swe_cpp/README.md`: canonical runbook,
  exports, phases, task/prompt/grader contract, artifacts, resume, teardown,
  troubleshooting, interpretation, and paid ladder;
- `README.md`: add the optional lane, clearly separate it from PIE, Moonlight
  Multi-SWE, and official leaderboard claims, and link to the runbook;
- `ROADMAP.md`: add the benchmark question, blocking decision gate, and
  evidence requirements;
- `.agents/REPO_GUIDE.md`: add repository map, boundaries, commands, security,
  artifact, and validation invariants;
- `.agents/skills/w8-biayn-framework/SKILL.md`: add the operator path and all
  hard-won Modal/Multi-SWE invariants;
- `.gitignore`: confirm all local run data and generated locks/receipts stay
  ignored while the reviewed source image lock remains tracked;
- tests: encode every safety or correctness issue found during paid validation.

Repo-wide docs must say "planned" until source, offline tests, and no-spend plan
exist. They must say "implemented, paid validation pending" until the real
two-task smoke passes. They must not quote a model result until a complete
50-task receipt has `modal_app_stopped: true` and the local artifact copy
revalidates.

`AGENTS.md` and `CLAUDE.md` must remain symlinks to `.agents/REPO_GUIDE.md`.
Update the shared target once; never replace or fork the symlinks.

## Implementation Phases

### Phase A: shared contracts and pure module

- [ ] Extract shared GLM pure helpers without changing the Aider lane.
- [ ] Expose backend-neutral Multi-SWE official script/result helpers.
- [ ] Add `ModalMultiSweConfig`, identity mapping, validation, and redaction.
- [ ] Add deterministic plan and request builders.
- [ ] Add image-lock parsing and verification.
- [ ] Add receipt, resume, summary, and artifact validation.
- [ ] Add offline tests for all pure logic.
- [ ] Run both existing reference test files.

### Phase B: dataset and Modal Sandbox backend

- [ ] Pin the dataset revision and generate the reviewed 50-image lock.
- [ ] Implement CPU dataset/offline-dependency staging.
- [ ] Implement exact external Image construction.
- [ ] Implement network-blocked per-task Sandbox grading.
- [ ] Implement output draining, bounded logs, result classification, and
      unconditional terminate/detach.
- [ ] Implement incremental oracle persistence and exact-key resume.
- [ ] Prove all-task oracle admission before GPU work.

### Phase C: GLM serving and evaluation orchestration

- [ ] Implement/reuse exact model cache validation.
- [ ] Implement the one-replica four-H100 SGLang Server.
- [ ] Implement authenticated response-shape admission.
- [ ] Implement fixed two-task smoke.
- [ ] Implement full generation-first, grading-second flow.
- [ ] Reduce GPU scale-down after generation.
- [ ] Implement per-task durable uploads and summary recomputation.

### Phase D: wrapper, artifacts, and teardown

- [ ] Add export-only `run.sh` with default plan.
- [ ] Add early cleanup traps and paid acknowledgement.
- [ ] Add stale/concurrent App/run preflight.
- [ ] Add bounded regular-file-only artifact download.
- [ ] Add explicit App stop and control-plane verification.
- [ ] Add final local validation and concise summary.

### Phase E: docs and live validation

- [ ] Write canonical lane README.
- [ ] Update all repo-wide guidance surfaces.
- [ ] Run focused and full offline validation.
- [ ] Execute paid ladder through two-task smoke.
- [ ] Turn each paid failure into a regression.
- [ ] Execute full only after clean smoke.
- [ ] Record immutable first-run evidence without committing generated files.

## Validation Commands

Focused implementation checks:

```bash
uv run --extra dev pytest \
  tests/test_modal_multi_swe_cpp.py \
  tests/test_modal_aider_polyglot_cpp.py \
  tests/test_slime_multi_swe_cpp.py

uv run --extra dev ruff check \
  src/w8_biayn/modal_multi_swe_cpp.py \
  src/w8_biayn/modal_glm47.py \
  src/w8_biayn/integrations/slime_multi_swe_cpp.py \
  examples/modal/glm47_flash_multi_swe_cpp/modal_app.py \
  tests/test_modal_multi_swe_cpp.py

uv run python -m compileall src tests
bash -n examples/modal/glm47_flash_multi_swe_cpp/run.sh
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/w8-biayn-framework
```

If `modal_glm47.py` is not introduced, omit that path rather than creating an
empty module. Before handoff, also run the repository-wide required checks:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/w8-biayn-framework
```

## Acceptance Criteria

Implementation is complete only when all of the following are true:

1. A clean clone with Modal credentials and exact exported identities can run
   a no-spend plan through one documented script.
2. The normal path requires no SLIME, GCP, SkyPilot, Aider, or local Docker.
3. The exact dataset revision produces exactly the checked-in 50-task set.
4. Every task uses a checked-in exact linux/amd64 official image digest.
5. Every dataset `fix_patch` passes the same Modal Sandbox backend with a
   positive test count before GPU startup.
6. Model, dataset, task, image, prompt, parser, harness, dependency, Modal,
   SGLang, Transformers, GPU, and sampling identities are in the receipt.
7. Grading Sandboxes have no secrets or sensitive Volumes and have networking
   blocked.
8. The server uses one strict four-H100 replica and releases it before full
   grading.
9. Full is impossible before the real two-task smoke.
10. Exactly 50 saved responses map to exactly 50 complete grader records.
11. Strict summary metrics recompute from per-task records and embed a passing
    oracle setup check.
12. Recovered diagnostics never change strict pass rate.
13. Remote and local artifacts reconcile byte-for-byte.
14. Every Sandbox is terminated/detached and the App is control-plane verified
    stopped.
15. No credential appears in source, logs, plans, requests, receipts, or
    artifacts.
16. Offline tests pass without network, credentials, Docker, Modal resources,
    or GPUs.
17. Existing Modal/Aider and Moonlight Multi-SWE tests still pass.
18. All required documentation and the repository skill match implemented
    behavior.
19. No model score is printed or documented before a complete stopped-App
    receipt exists.

## Expected Operator Flow After Implementation

No-spend plan:

```bash
export MODAL_TOKEN_ID='<secret>'
export MODAL_TOKEN_SECRET='<secret>'
export MODAL_PROFILE='<profile>'

export W8_MODAL_MULTI_SWE_RUN_ID="glm47-mswe-cpp-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_MULTI_SWE_MODEL_REPO='zai-org/GLM-4.7-Flash'
export W8_MODAL_MULTI_SWE_MODEL_REVISION='<40-hex-commit>'
export W8_MODAL_MULTI_SWE_DATASET_REVISION='<40-hex-commit>'
export W8_MODAL_MULTI_SWE_SGLANG_IMAGE='lmsysorg/sglang@sha256:<64-hex>'
export W8_MODAL_MULTI_SWE_PHASE='plan'

bash examples/modal/glm47_flash_multi_swe_cpp/run.sh
```

Full run, which always includes the all-task oracle and two-task smoke:

```bash
export W8_MODAL_MULTI_SWE_PHASE='full'
export W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN='1'
export W8_MODAL_MULTI_SWE_GPU='H100!:4'
export W8_MODAL_MULTI_SWE_MAX_TOKENS='32768'
export W8_MODAL_MULTI_SWE_TEMPERATURE='0.0'
export W8_MODAL_MULTI_SWE_TOP_P='1.0'
export W8_MODAL_MULTI_SWE_RESUME='0'

bash examples/modal/glm47_flash_multi_swe_cpp/run.sh
```

Only a fully admitted run may end with a result summary like:

```text
status: complete
benchmark: glm47-flash-multi-swe-cpp-modal-base-eval
result_family: repo-owned-single-turn-multi-swe-cpp
model: zai-org/GLM-4.7-Flash@<revision>
dataset: ByteDance-Seed/Multi-SWE-bench_mini@<revision>
tasks: 50/50
strict_pass_rate: <recomputed value>
oracle_setup: 50/50 passed
harness_backend: modal-sandbox
modal_app_stopped: true
artifacts: .w8-biayn/modal/glm47-flash-multi-swe-cpp/runs/<run-id>
```

Anything less is incomplete infrastructure evidence, not a model result.
