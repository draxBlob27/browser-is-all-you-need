# GLM-4.7-Flash Agentic Multi-SWE C++ Base Eval On Modal

Status: source, no-spend planning, runbook, and offline tests are implemented.
Paid CPU canaries, real model/SGLang admission, one trajectory, fixed smoke,
and full stopped-App evidence remain pending. No paid agentic result exists.

Target: add a separately named, repo-owned evaluation of exact-revision base
`zai-org/GLM-4.7-Flash` on the 50 C++ instances in
`ByteDance-Seed/Multi-SWE-bench_mini`. The model works through a bounded
multi-turn SWE-agent edit/test loop in an isolated repository workspace. The
harness converts final repository state into a unified diff and grades it in a
second, fresh Modal Sandbox using the existing admitted Multi-SWE grader.

This document is the implementation and paid-acceptance contract.
Decisions marked **fixed** must be implemented as written unless the user
explicitly approves a protocol revision. Unchecked boxes are work to do, not
claims about current source.

## Why This Successor Exists

The completed single-turn baseline `glm47-mswe-full-20260712174928` has
reconciled local artifacts, a 50/50 oracle proof, 50 responses and records, and
verified stopped-App evidence. It scored 0/50: 43 strict response-format
failures and seven patch-application failures.

That result does not prove GLM cannot solve the issues. It shows the
single-turn text-to-diff interface was the dominant failure boundary. This
successor asks:

> How does base GLM-4.7-Flash perform on the same 50 C++ Multi-SWE tasks when
> it may inspect and edit a sanitized repository over multiple tool turns, but
> its final source changes are graded by the same hidden-test-isolated Modal
> Sandbox harness?

The completed single-turn run remains immutable baseline evidence. Do not
change its parser, artifacts, result family, or summaries to add agentic
behavior.

## Fixed Protocol

- Framework: pinned SWE-agent, not claude-code, Codex CLI, Aider, or a custom
  agent loop.
- Model: exact-revision base `zai-org/GLM-4.7-Flash`.
- Dataset: the existing exact-revision 50-task C++ Multi-SWE mini set.
- Samples: exactly one isolated trajectory per task.
- Interaction: bounded multi-turn model/tool loop.
- Submission: harness-generated diff from final repository state, never raw
  model response text.
- Grading: the existing fresh, network-blocked official-image Modal grader.
- Metric: strict task pass rate with one trajectory per task.
- Interpretation: pass@1-style agentic evaluation, not pass@8 and not an
  official Multi-SWE leaderboard result.
- Run identity: 3-40 lowercase letters, digits, or hyphens, keeping the
  derived Modal App name at most 62 characters and admitting every documented
  timestamp form.

Use:

```text
benchmark: glm47-flash-agentic-multi-swe-cpp-modal-base-eval
result_family: repo-owned-agentic-swe-agent-multi-swe-cpp
```

Multiple turns are not multiple samples. Tool calls, repair attempts, test
runs, or model steps inside one trajectory do not make the result pass@k.
Infrastructure retries also do not create additional model samples.

## Design Checklist

- [x] Keep the new lane separate from the single-turn lane.
- [x] Use one isolated multi-turn trajectory per task for phase one.
- [x] Reuse dataset, image lock, oracle, path policy, grader, classifier, and
      correctness aggregation.
- [x] Use SWE-agent with an exact source and dependency identity.
- [x] Separate the model-controlled workspace from the hidden-test grader.
- [x] Remove hidden grader assets before the model receives shell access.
- [x] Synthesize the final diff from file state in trusted harness code.
- [x] Hold the four-H100 server only while trajectories need it.
- [x] Release the GPU before final all-task grading.
- [x] Make plan no-spend and paid work explicitly acknowledged.
- [x] Resume only complete task units; never splice partial conversations.
- [x] Treat pass@8 as a later, separate result family.

## Scope And Non-Goals

The first implementation must:

- evaluate the same 50 allowlisted C++ tasks;
- preserve the exact dataset revision and reviewed linux/amd64 image lock;
- run or import an exact all-50 `fix_patch` oracle before GPU startup;
- admit a sanitized agent workspace for every task before GPU startup;
- bound calls, tokens, commands, wall time, filesystem size, and output;
- give the model only public issue context and sanitized base source;
- allow inspection of public source and base-revision tests;
- block networking in every agent and grader Sandbox;
- export tracked, untracked, deleted, and renamed final source changes;
- apply the existing forbidden-path policy to the synthesized patch;
- grade in a separate fresh Sandbox the model never controlled;
- persist one complete trajectory, final patch, and record per task;
- terminate/detach every Sandbox and stop/verify the Modal App.

It must not:

- retrofit the single-turn result family;
- run SLIME, PIE training, SFT, GRPO, Megatron, SkyPilot, or a trainer;
- use Aider or call this an Aider result;
- write a replacement agent framework;
- expose `fix_patch`, `test_patch`, test buckets, oracle records, grader logs,
  target-solution history, or prepared hidden assets to the model;
- execute untrusted model shell commands in a normal Modal Function;
- grade inside the model-controlled workspace;
- accept model prose or a fenced diff as the authoritative answer;
- count turns, retries, or test-feedback iterations as new trajectories;
- report pass@8, pass@k, PIE speedup, or `correct_and_faster_rate`;
- claim an official Multi-SWE or leaderboard score;
- silently fall back to the single-turn parser.

## Required Reading For The Implementing Agent

Read completely before changing behavior:

1. `AGENTS.md`
2. `README.md`
3. `ROADMAP.md`
4. `.agents/skills/w8-biayn-framework/SKILL.md`
5. this document
6. `docs/GLM47_FLASH_MULTI_SWE_CPP_MODAL_BASE_EVAL_IMPLEMENTATION_PLAN.md`
7. `examples/modal/glm47_flash_multi_swe_cpp/README.md`
8. `examples/modal/glm47_flash_multi_swe_cpp/modal_app.py`
9. `src/w8_biayn/modal_glm47.py`
10. `src/w8_biayn/modal_multi_swe_cpp.py`
11. `src/w8_biayn/modal_multi_swe_runtime.py`
12. `tests/test_modal_multi_swe_cpp.py`
13. `src/w8_biayn/integrations/slime_multi_swe_cpp.py`
14. `src/w8_biayn/integrations/swe_agent_driver.py`
15. `src/w8_biayn/integrations/slime_swe_agent_cpp_perf.py`
16. `tests/test_slime_swe_agent_cpp_perf.py`
17. `examples/slime/glm47_swe_agent_cpp_perf/README.md`
18. the exact pinned SWE-agent and SWE-ReX source

Do not implement remembered SWE-agent, SWE-ReX, LiteLLM, SGLang, or Modal
APIs. Confirm the repository pins and add source-shape tests for every upstream
seam.

## Architecture

Use two native Modal Sandboxes with different trust domains:

1. **Agent Sandbox**: a sanitized base-revision repository plus public
   development tools. SWE-agent may inspect, edit, compile, and run commands.
   It has no secrets, network, Volume, oracle patch, dataset test patch, target
   history, or grader assets.
2. **Grader Sandbox**: a fresh exact official `mswebench` image used by the
   existing grader. It receives only the harness-synthesized final patch and
   the existing narrow read-only simdjson dependency mount when required. The
   model never receives tools in it.

The trusted controller sends model requests and implements the SWE-agent
environment through bounded `Sandbox.exec` and filesystem operations.
Generated shell commands never run in the controller Function.

```text
operator
  |
  v
agentic run.sh -> ephemeral Modal App
  |
  +-- CPU preflight
  |     +-- dataset + reviewed image lock
  |     +-- all-50 grader oracle proof
  |     `-- all-50 sanitized-workspace proof
  |
  +-- exact model preload
  +-- one H100!:4 SGLang web server, active lease = 1
  |
  +-- agent trajectories, concurrency <= 4
  |     +-- fresh Agent Sandbox
  |     +-- trusted sanitization
  |     +-- pinned SWE-agent loop
  |     +-- trusted final-state diff
  |     `-- terminate(wait=True) + detach
  |
  +-- require complete trajectory/patch set
  +-- release server lease and set two-second scale-down
  |
  +-- final grading, concurrency <= 4
  |     +-- separate fresh Grader Sandbox
  |     +-- existing grader/classifier
  |     `-- terminate(wait=True) + detach
  |
  `-- reconcile artifacts -> stop App -> verify stopped
```

The GPU must not remain allocated during final all-task grading or artifact
transfer. Unlike single-turn generation, each later model turn depends on
earlier tool output, so the lease spans the trajectory phase only.

## Hidden-Test Boundary

The official image contains `/home/test.patch`, `/home/fix-run.sh`, original
Git metadata, and prepared build/test assets. Arbitrary model shell access in
that state would leak grading-only information.

The Agent Sandbox may start from the same digest-locked task image to retain
public compilers and system packages, but trusted setup must sanitize it before
the first model request. The model then runs as an unprivileged user and never
regains access to the original `/home` tree. Final grading is always a new
Sandbox; never restore hidden assets after the agent has modified a workspace.

## Sanitized Workspace Contract

Trusted bootstrap runs before any model-authored command:

1. Verify the official checkout and exact base ref.
2. Verify the tracked tree is clean.
3. Materialize a deterministic snapshot from tracked files at HEAD. Include a
   submodule only after verifying its exact gitlink commit.
4. Store a root-owned baseline archive and path/type/mode/size/SHA-256
   manifest outside the writable workspace.
5. Remove original Git history, repository, `/home/test.patch`,
   `/home/fix.patch`, `/home/fix-run.sh`, build trees, dataset patches, oracle
   artifacts, and task-specific hidden assets.
6. Clear temporary state and close all hidden-material file descriptors.
7. Extract only the sanitized tree at `/workspace/repo`.
8. Initialize a synthetic one-commit Git repo with no target-solution history.
9. Create unprivileged user `w8agent`, writable only in the workspace and its
   bounded temporary directory.
10. Make `/root`, `/home`, trusted manifests, and finalizer paths unreadable to
    `w8agent`.
11. Upload only the exact pinned SWE-agent tool bundle and record its hash.
12. Run hostile-path canaries as `w8agent`; hidden paths, result/model paths,
    and secret environment must be absent or unreadable.
13. Persist only hashes and presence flags in `workspace.receipt.json`, never
    hidden patch text.

Public tests tracked at the base revision may remain. Dataset `test_patch`
content and files created by applying it may not.

Workspace admission is blocking. Smoke proves all 50 task workspace
fingerprints. Full may import that proof only from a completed agentic source
run with exact workspace-protocol cache keys.

## SWE-Agent Integration

Use the current proven SWE-agent commit as the initial candidate pin:

```text
5f40e63360d654adcd91e30ed11473389bc4909b
```

Verify it before retaining it. If a different exact commit is required for a
Modal adapter, pin and explain it, lock all transitive runtime versions, and
repeat the full validation ladder. Never install mutable HEAD or the unrelated
PyPI `sweagent` stub.

Reuse these lessons from `swe_agent_driver.py`:

- start from shipped `default_backticks.yaml` with `thought_action`;
- use an exact OpenAI-compatible served-model label;
- set LiteLLM monetary cost limits to `0.0`;
- enforce call, token, command, and wall-clock bounds instead;
- persist exact sampling fields;
- capture final file state before closing the environment;
- keep SWE-agent imports out of pure contract modules.

Do not use `LocalDeployment`, which would run model commands in the trusted
controller. Add a narrow repo-owned adapter for the exact pinned agent
environment protocol, for example `ModalSandboxSWEEnv`. It exposes only the
methods the pin calls and implements them with Modal Sandbox APIs. Do not fork
SWE-agent.

## Agent Problem Statement

Do not reuse the single-turn “return exactly one diff” contract. Extract or
reuse the deterministic public issue-context builder and append:

```text
Work on the issue in the repository at /workspace/repo.

Inspect the code, edit the implementation, and run useful public checks. Do
not modify tests, examples, documentation, build configuration, CI, generated
files, or files outside the repository. Hidden tests will grade the final
source changes after the session. When satisfied, submit; the harness will
derive the patch from final repository state.
```

The prompt may contain repository, instance ID, base ref, title, issue body,
resolved public context, workspace path, and general hidden-test notice. It
must not contain:

- `fix_patch` or `test_patch` text, paths, hashes, hunks, or changed-file list;
- test buckets or oracle-derived failures;
- target-solution commits or branches;
- image filesystem inventories;
- per-task outcomes from the single-turn run;
- grader logs or CTest counts.

Persist `issue_context_sha256` and `agent_problem_statement_sha256`. Tests must
inject unique sentinels into every hidden field and prove none enter prompts,
requests, traces, or tool observations.

## Model And Turn Bounds

SGLang keeps separated `reasoning_content` and `content`. Only assistant
`content` enters SWE-agent's action parser; reasoning never becomes a command.

Fixed first-run values:

```text
samples_per_task                         1
temperature                              0.0
top_p                                    1.0
max_agent_calls                          40
per_turn_max_completion_tokens           32768
max_cumulative_completion_tokens         131072
max_input_context_tokens                 196608
agent_total_execution_timeout_seconds    1200
tool_command_timeout_seconds              120
agent_concurrency                           4
tool_output_persisted_bytes_per_stream    65536
tool_output_observation_chars             32768
```

The per-turn ceiling stays 32,768 because paid GLM evidence showed 8,192 can
be all reasoning. The cumulative limits keep it bounded. If SWE-agent/LiteLLM
cannot enforce a limit, the adapter must enforce and receipt it.

Call, token, parser, or agent-time limits are model trajectory terminations.
Export and grade any valid final source state. They become infrastructure
failures only when the controller cannot produce a complete trace and
final-state receipt.

## Tool Execution Contract

Commands run as `w8agent` in the Agent Sandbox:

- default cwd `/workspace/repo`;
- `block_network=True`, no Secret, no Volume;
- hard per-command timeout and kill-after grace;
- concurrent stdout/stderr draining;
- bounded observation with explicit truncation;
- persisted return code, duration, timeout, stream byte counts, hashes, and
  retained head/tail;
- no bearer or controller environment in commands;
- background process cleanup between commands and before finalization;
- nonzero command exit is an observation, not infrastructure failure.

Fixed Agent Sandbox identity:

```text
cpu                    4.0
memory_mib             8192
lifetime_seconds       1500
block_network          true
secrets                none
volumes                none
```

Change resources only with a fresh run ID and new smoke. Do not change final
grader resources to compensate.

## Trusted Final-State Export

Raw assistant text is not the answer. Trusted root code derives the submission:

1. Reap all `w8agent` processes.
2. Walk final state with `lstat`; reject traversal, absolute paths, devices,
   sockets, FIFOs, hardlink tricks, and symlinks.
3. Enforce fixed file-count and byte ceilings.
4. Reconstruct a trusted repo from the root-owned baseline archive.
5. Preserve its trusted `.git`, clear its working tree, then overlay regular
   final workspace files excluding agent-owned `.git`.
6. Run `git add -A` so additions, deletions, and renames are represented.
7. Produce `git diff --cached --binary --full-index <baseline> --`.
8. Classify empty diff as `no_changes`.
9. Reject binary patches with the existing validator.
10. Apply `preflight_patch_paths` unchanged.
11. Verify `git apply --check` on another pristine reconstruction.
12. Persist patch bytes/hash, changed paths/lines, final manifest, and receipt
    before destroying the Agent Sandbox.

Agent Git commands or commits cannot change the root-owned baseline. Do not
persist the entire final repository; persist a manifest and final patch.

## Final Grader Contract

Reuse current `grade_patch`, `grade_with_retry`, and the backend-neutral
classifier:

1. Fresh exact digest-locked official image.
2. `block_network=True`.
3. Exactly 2 CPU and 2,048 MiB request/limit.
4. No Secret, model Volume, or results Volume.
5. Existing read-only simdjson parent mount only when required.
6. Final patch written to `/home/fix.patch`.
7. Existing official script and 1,200-second timeout.
8. CTest count parsed from complete in-memory streams before truncation.
9. Existing stream/hash/tail, Image, Sandbox, elapsed, and retry receipts.
10. `terminate(wait=True)` and detach in `finally`.

No hidden grader output returns to the model in this pass@1-style protocol.

## Outcome Taxonomy

Complete model outcomes include:

- `passed`;
- `no_changes`;
- `invalid_files`;
- `invalid_submission` for unsupported final state or binary patch;
- `patch_apply_error`;
- `compile_error`;
- candidate-caused `timeout`;
- `tests_failed`;
- candidate-caused `no_tests_collected` with an exact passing oracle;
- agent call/token/time/parser limit followed by grading of valid final state.

Infrastructure failures block admission:

- dataset, lock, source, dependency, oracle, or workspace-proof mismatch;
- hidden-material canary failure;
- Agent/Grader Sandbox unavailable after one retry;
- SGLang startup, auth, identity, or transport failure;
- controller exception preventing a complete trajectory receipt;
- missing/corrupt prompt, trace, patch, record, manifest, or receipt;
- unsafe artifact path or byte mismatch;
- inability to terminate/detach or verify the App stopped.

One infrastructure retry may restart from the pristine base with the same
identity. Preserve the failed attempt under `incomplete-attempts/`; do not
continue uncertain conversation/tool state or count the retry as a sample.

## Blocking CPU Admission

Two proofs finish before model preload:

### Grader oracle

Reuse the exact current all-50 `fix_patch` proof. Smoke/full may import the
completed single-turn proof only after existing local/remote manifest,
stopped-App, task, lock, dataset, script, dependency, resource, and 50
cache-key checks pass. Import no model request, response, or record.

### Agent workspace

For all 50 tasks, create an Agent Sandbox, sanitize, run scripted
read/write/compile/output canaries as `w8agent`, prove hidden paths and secrets
inaccessible, record the public tree fingerprint, then terminate/detach.
Preserve exact empty directories for uninitialized gitlinks and receipt-bind
their indexed object IDs and state; populated submodules must resolve to the
indexed commit, while mismatches/conflicts block. The compile/output probe uses
the exact image's default C++ mode because reviewed
legacy images may reject a C++20 flag; the unchanged task grader remains the
only task-language acceptance surface.

Its cache key includes task/base/image/platform, sanitizer and protocol hashes,
submodule identities, user/path/resource/network policy, tool bundle,
filesystem ceilings, canary version, Modal SDK, and adapter version. Import is
allowed only from a completed agentic run with 50 exact keys and no fallback.

## SGLang Lifecycle

Reuse `modal_glm47.py` for exact model shards, digest-pinned SGLang, exact
Transformers compatibility commit, `glm4_moe_lite` assertion, strict
`H100!:4` TP4, one model/replica, reasoning separation, authenticated API,
cold-start 503 polling, response-shape-only admission, and bearer-redacted
failure tails.

Do not use Modal SDK 1.5.2 `App.server`. Use `@app.function` plus
`@modal.web_server` and an explicit lifetime. The server image must not require
the control-only image-lock env during hydration.

Static server settings remain `min_containers=0`, `max_containers=1`. After
CPU admission and preload, dynamically hold one replica with
`min_containers=1`. Release it after all trajectory/final-patch artifacts are
durable, restore `min_containers=0`, set two-second scale-down, drain, then
grade.

Initial full ceiling:

```text
max_run_seconds = 43200
server_timeout >= startup 3600 + run 43200 + teardown 600 = 47400
```

Validate the bound against the pinned Modal SDK. Persist formula/value. Full
requires a second acknowledgement for the potentially multi-hour H100 lease.

## Operator Contract And Configuration

Only entrypoint:

```bash
bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
```

It accepts export-only configuration and must install traps first, validate a
pure redacted plan, exit plan before resource creation, enforce both paid
gates, reject stale state, run the ephemeral App, download success/failure
artifacts, release GPU before grading/transfer, stop on every exit, verify
stopped, reconcile bytes, and locally recompute before printing a score.
Never deploy or schedule an App.

Use a distinct prefix:

```bash
export W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID='glm47-agentic-mswe-<utc>'
export W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REPO='zai-org/GLM-4.7-Flash'
export W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REVISION='<40-hex>'
export W8_MODAL_AGENTIC_MULTI_SWE_DATASET_REVISION='<40-hex>'
export W8_MODAL_AGENTIC_MULTI_SWE_SGLANG_IMAGE='lmsysorg/sglang@sha256:<64-hex>'
export W8_MODAL_AGENTIC_MULTI_SWE_SWE_AGENT_REVISION='5f40e63360d654adcd91e30ed11473389bc4909b'
export W8_MODAL_AGENTIC_MULTI_SWE_PHASE='plan'

export W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1
export W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_LONG_GPU_LEASE=1  # full only

export W8_MODAL_AGENTIC_MULTI_SWE_ORACLE_SOURCE_RUN_ID='<completed-run>'
export W8_MODAL_AGENTIC_MULTI_SWE_WORKSPACE_SOURCE_RUN_ID='<agentic-smoke>'
```

Recommended shared Volumes:

```text
model_volume     w8-glm47-flash-models
data_volume      w8-multi-swe-cpp-data
results_volume   w8-multi-swe-cpp-results
local_root       .w8-biayn/modal/glm47-flash-agentic-multi-swe-cpp
```

Sharing permits exact model/data/proof reuse. Agent Sandboxes still mount no
Volume. The pure config rejects mutable pins, wrong task/sample/model/GPU,
nonzero temperature, multiple/warm replicas, changed smoke tasks, missing paid
gates, unsafe paths/names, dirty full source, incompatible resume/import,
workspace proof from a non-agentic run, agent Sandbox secrets/network/Volumes,
or grader drift from the oracle.

## Smoke And Full

Smoke:

1. stale-run admission;
2. exact dataset/image lock;
3. all-50 oracle execution/import;
4. all-50 workspace admission;
5. model preload and real SGLang admission;
6. scripted non-model tool bridge canary;
7. two fixed real trajectories;
8. complete final-state export;
9. GPU release;
10. two fresh final graders;
11. summary, manifest, download, stop, and stopped verification.

Smoke does not require a model pass. A model that submits without tools is a
model outcome; the scripted canary proves the tool path.

Full always runs the same two-task smoke, then:

1. exactly one isolated trajectory for all 50 tasks;
2. incremental prompt/trace/tool/response/final-patch persistence;
3. complete 50-trajectory/final-state set;
4. GPU release and two-second scale-down;
5. separate fresh final grading;
6. exactly 50 model-outcome records;
7. both setup proofs copied into full artifacts;
8. manifest/receipt reconciliation, download, stop, and local validation.

## Artifact Contract

```text
.w8-biayn/modal/glm47-flash-agentic-multi-swe-cpp/runs/<run-id>/
  plan.json
  config.redacted.json
  source.receipt.json
  dataset.receipt.json
  model-cache.receipt.json
  image-lock.json
  swe-agent.identity.json
  admission.response.json
  server.runtime.json
  server.receipt.json
  data/
    manifest.json
    tasks/<id>/task.json
    oracle.records.jsonl
    oracle.summary.json
    oracle-import.json
    agent-workspace.records/<id>.json
    agent-workspace.records.jsonl
    agent-workspace.summary.json
    agent-workspace-import.json
  smoke/
    prompts/<id>.txt
    trajectories/<id>/
      identity.json
      workspace.receipt.json
      events.jsonl
      summary.json
      final-state.manifest.json
      final.patch
      final-patch.receipt.json
      tool-logs/<turn>.json
    incomplete-attempts/<id>/<attempt>/...
    records/<id>.json
    grader-logs/<id>.log
    records.jsonl
    summary.json
  full/
    prompts/<id>.txt
    trajectories/<id>/...
    incomplete-attempts/<id>/<attempt>/...
    records/<id>.json
    grader-logs/<id>.log
    records.jsonl
    oracle.records.jsonl
    agent-workspace.records.jsonl
    summary.json
  run_receipt.json
  artifact_manifest.json
```

Events record ordered type/index, time, request/response hashes, response shape
and numeric usage, action/secret-free command, tool return/timeout/stream
hashes and retained output, cumulative limits, and termination reason. Never
serialize the bearer or Authorization header. Do not print generated reasoning,
source, commands, or grader logs in the console summary.

Build JSONL/summaries from sorted per-task files, never concurrent appends.
Download exact `FileEntryType.FILE` entries only, validate all paths, retain
the existing 16-read async bound, and reconcile bytes.

## Metrics And Interpretation

Reuse strict correctness fields: task/sample count, pass rate, reward,
invalid-file, patch-apply, compile, timeout, tests-failed, harness, no-tests,
reason/repo summaries, and passing `oracle_setup_check`.

Add agentic fields: no-change/invalid-submission rates, termination reasons,
calls/turns/tools/nonzero exits/timeouts, token distributions, agent/grader
time, changed files/lines, retries, and passing
`agent_workspace_setup_check`.

Do not report agentic `invalid_format`: raw response text is not the
submission. Action parser errors are trajectory diagnostics.

Single-turn and agentic runs may be shown side by side only as a descriptive
protocol comparison. Match immutable model/data/task/image/oracle/grader and
sampling fields, and disclose prompt, tools, workspace, interaction budget,
and submission differences.

No score may be printed or documented until 50 trajectories and 50 records
reconcile with both setup proofs and verified stopped-App evidence.

## Resume

Identity covers source, model/data/images/Transformers/SGLang/Modal, SWE-agent
commit/dependency lock/config/parser/tool bundle/adapter hashes, prompts,
sanitizer/workspace fingerprints, every agent limit/resource/network field,
finalizer/path policy, grader/oracle identities, task/smoke sets, concurrency,
and sampling.

- Completed runs are immutable.
- Proof imports are dedicated and fail closed.
- Reuse a trajectory only with complete prompt, identity, events, summary,
  final manifest, patch, and hashes.
- Reuse a record only with exact patch hash and grader key.
- Archive and restart interrupted trajectories from pristine state.
- Never resume at a turn or reuse uncertain live Sandboxes.
- Infrastructure retry does not increase sample count.
- Model-limit outcomes are not automatically retried.
- Reject simultaneous writers.

## Intended Files

Add:

```text
examples/modal/glm47_flash_agentic_multi_swe_cpp/
  README.md
  run.sh
  modal_app.py
  swe-agent.requirements.lock
src/w8_biayn/modal_agentic_multi_swe_cpp.py
src/w8_biayn/modal_agentic_multi_swe_runtime.py
src/w8_biayn/integrations/modal_swe_agent_driver.py
tests/test_modal_agentic_multi_swe_cpp.py
```

Reuse small helpers from `modal_glm47.py`, `modal_multi_swe_cpp.py`,
`modal_multi_swe_runtime.py`, and `slime_multi_swe_cpp.py`. Reuse the existing
checked-in image lock; do not duplicate it.

Keep Modal/SWE-agent imports out of the pure contract module. Offline tests
must need no network, credentials, Docker, Modal, SWE-agent, or GPU.

With implementation, update `README.md`, `ROADMAP.md`,
`.agents/REPO_GUIDE.md`, `.agents/skills/w8-biayn-framework/SKILL.md`, lane
README, and relevant tests. Keep `AGENTS.md` and `CLAUDE.md` as symlinks.

## Implementation Checklist

### Phase A: pure contracts

- [x] Add strict agentic config, redaction, identity, and plan.
- [x] Add distinct labels and paths.
- [x] Extract/reuse public issue context and build the agent prompt.
- [x] Add hidden-field sentinel tests.
- [x] Add SWE-agent/dependency/tool identity.
- [x] Add timeout/spend formulas.
- [x] Add workspace, trajectory, patch, record, receipt, and summary schemas.
- [x] Add resume/import and local artifact validation.
- [x] Preserve single-turn behavior exactly.

### Phase B: workspace and tools

- [x] Implement tracked-tree/submodule snapshot.
- [x] Remove hidden assets and original history.
- [x] Configure unprivileged `w8agent`.
- [x] Add hidden-path/history/secret canaries.
- [x] Add root-owned baseline and final manifest.
- [x] Implement pinned SWE-agent Modal Sandbox adapter.
- [x] Add bounded command execution and cleanup.
- [x] Add trusted final-state diff and path validation.
- [x] Terminate/detach on every path.

### Phase C: orchestration and grading

- [x] Build pinned, dependency-locked SWE-agent runner Image.
- [x] Reuse exact model cache and SGLang admission.
- [x] Use `@app.function` plus `@modal.web_server`.
- [x] Acquire/release one active server replica.
- [x] Run one isolated bounded trajectory per task.
- [x] Persist trace/final state incrementally.
- [x] Add one infrastructure restart from pristine state.
- [x] Require a complete patch/outcome set before GPU release.
- [x] Reuse the fresh grader/classifier.
- [x] Aggregate one outcome per task.

### Phase D: proofs, resume, wrapper

- [x] Reuse/import all-50 oracle proof.
- [x] Add all-50 workspace proof/import.
- [x] Add task-granular trajectory/record reuse.
- [x] Archive incomplete attempts.
- [x] Add export-only, default-plan `run.sh`.
- [x] Install cleanup traps before paid commands.
- [x] Add both paid gates and stale-App preflight.
- [x] Add regular-file-only transfer and byte reconciliation.
- [x] Stop/verify App before score.

### Phase E: tests, docs, paid ladder

- [x] Write lane runbook and complete commands.
- [x] Update required repository guidance.
- [x] Run focused/full offline validation.
- [ ] Run CPU sanitizer/tool canaries.
- [ ] Run real model/SGLang admission.
- [ ] Run one trajectory.
- [ ] Run fixed two-task agentic smoke.
- [ ] Convert each paid incident into a regression.
- [ ] Run full only after clean smoke.
- [ ] Reconcile all 50 and stopped-App evidence.

## Offline Test Checklist

- [x] Config rejects every mutable/wrong/unsafe identity and missing gate.
- [x] Plan is deterministic, redacted, and no-spend.
- [x] Wrapper trap precedes paid commands; no deploy/schedule exists.
- [x] Server uses function/web-server, one replica, no static warm pool.
- [x] Hidden sentinels never enter prompt/request/trace/tool observation.
- [x] Sanitizer preserves tracked base bytes and removes hidden/history/build
      inputs.
- [x] Synthetic Git history has one commit; hostile paths are unreadable.
- [x] Workspace proof rejects missing/stale tasks and bad imports.
- [x] Fake SWE-agent/fake Sandbox cover exact config and every cleanup path.
- [x] Commands run unprivileged with no network/secret/Volume.
- [x] Tool streams are drained, hashed, bounded, and observable.
- [x] Edits/adds/deletes/renames enter final patch.
- [x] Agent commits cannot change trusted baseline.
- [x] Empty, forbidden, binary, symlink, special-file, traversal, and oversized
      final states classify correctly.
- [x] Valid patch applies to pristine base.
- [x] Final grader is a separate fresh Sandbox with unchanged policy.
- [x] Agent-limit outcomes grade valid final state.
- [x] Infrastructure failures never enter denominator.
- [x] Exactly one sample per task despite retries/turns.
- [x] Resume reuses complete units and restarts partial ones.
- [x] Manifest/download reject unsafe/nonregular/mismatched artifacts.
- [x] No score admits before stopped-App proof.
- [x] Existing Modal Multi-SWE, Modal/Aider, SLIME Multi-SWE, and SWE-agent
      tests remain green.

## Paid Validation Ladder

1. Focused and repository-wide offline validation.
2. Real no-spend plan and Modal auth.
3. Pinned SWE-agent runner Image assertion.
4. One ordinary sanitize/tool/finalize canary without model.
5. One special simdjson/nlohmann workspace canary.
6. All-50 workspace proof.
7. All-50 grader-oracle import validation.
8. Exact model cache.
9. Four-H100 health/models/chat admission.
10. Scripted live tool bridge.
11. One real trajectory through final grader.
12. Fixed two-task agentic smoke and stopped proof.
13. Validate smoke as workspace-proof source.
14. Full 50 trajectories.
15. Early GPU release and full grading.
16. Local reconciliation, recomputation, and stopped verification.

Every paid infrastructure failure becomes an offline regression before the
next step.

## Validation Commands After Implementation

```bash
uv run --extra dev pytest \
  tests/test_modal_agentic_multi_swe_cpp.py \
  tests/test_modal_multi_swe_cpp.py \
  tests/test_modal_aider_polyglot_cpp.py \
  tests/test_slime_multi_swe_cpp.py \
  tests/test_slime_swe_agent_cpp_perf.py

uv run --extra dev ruff check \
  src/w8_biayn/modal_agentic_multi_swe_cpp.py \
  src/w8_biayn/modal_agentic_multi_swe_runtime.py \
  src/w8_biayn/integrations/modal_swe_agent_driver.py \
  examples/modal/glm47_flash_agentic_multi_swe_cpp/modal_app.py \
  tests/test_modal_agentic_multi_swe_cpp.py

bash -n examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
uv run python -m compileall src tests

uv run --extra dev pytest
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/w8-biayn-framework
```

## Acceptance Criteria

1. One script produces a deterministic no-spend plan.
2. Agentic App/root/labels/result family are distinct.
3. Exact 50-task dataset and image lock are unchanged.
4. Exact 50/50 grader oracle passes/imports before GPU.
5. Exact 50/50 workspace proof passes/imports before GPU.
6. Model sees only public issue context and sanitized base source.
7. Hidden patches/history/grader assets/credentials/Volumes are inaccessible.
8. SWE-agent, dependencies, parser, tools, and adapter are receipt-bound.
9. Exactly one isolated bounded trajectory runs per task.
10. Trusted code synthesizes final patches from file state.
11. Existing final path policy is unchanged.
12. Final grading uses a separate fresh network-blocked official image.
13. Exactly 50 complete trajectories map to 50 outcome records.
14. Agent-limit exits are outcomes; infrastructure failures block.
15. Turns and infrastructure retries never inflate sample count.
16. H100 server releases before final grading/transfer.
17. Every Sandbox terminates/detaches; App is verified stopped.
18. Remote/local artifacts reconcile.
19. Summaries recompute and embed both passing proofs.
20. No secret or hidden sentinel occurs in artifacts.
21. Existing reference lanes remain green.
22. Required docs and skill match implementation.
23. No score appears before complete stopped-App evidence.

## Expected Operator Flow

Plan:

```bash
export MODAL_TOKEN_ID='<secret>'
export MODAL_TOKEN_SECRET='<secret>'
export MODAL_PROFILE='<profile>'
export W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID="glm47-agentic-mswe-plan-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REPO='zai-org/GLM-4.7-Flash'
export W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REVISION='<40-hex>'
export W8_MODAL_AGENTIC_MULTI_SWE_DATASET_REVISION='d0fab3ccc7dff232fcaac234cf8af9a2efeaccf6'
export W8_MODAL_AGENTIC_MULTI_SWE_SGLANG_IMAGE='lmsysorg/sglang@sha256:<64-hex>'
export W8_MODAL_AGENTIC_MULTI_SWE_SWE_AGENT_REVISION='5f40e63360d654adcd91e30ed11473389bc4909b'
export W8_MODAL_AGENTIC_MULTI_SWE_PHASE='plan'
bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
```

Smoke imports only the existing grader oracle and creates the workspace proof:

```bash
export W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID="glm47-agentic-mswe-smoke-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AGENTIC_MULTI_SWE_PHASE='smoke'
export W8_MODAL_AGENTIC_MULTI_SWE_ORACLE_SOURCE_RUN_ID='glm47-mswe-full-20260712174928'
export W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1
export W8_MODAL_AGENTIC_MULTI_SWE_RESUME=0
bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
```

Full imports both proofs:

```bash
export W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID="glm47-agentic-mswe-full-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AGENTIC_MULTI_SWE_PHASE='full'
export W8_MODAL_AGENTIC_MULTI_SWE_ORACLE_SOURCE_RUN_ID='glm47-mswe-full-20260712174928'
export W8_MODAL_AGENTIC_MULTI_SWE_WORKSPACE_SOURCE_RUN_ID='<agentic-smoke-run>'
export W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1
export W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_LONG_GPU_LEASE=1
export W8_MODAL_AGENTIC_MULTI_SWE_MAX_RUN_SECONDS=43200
export W8_MODAL_AGENTIC_MULTI_SWE_RESUME=0
bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
```

Only a fully admitted run may print:

```text
status: complete
benchmark: glm47-flash-agentic-multi-swe-cpp-modal-base-eval
result_family: repo-owned-agentic-swe-agent-multi-swe-cpp
tasks: 50/50
trajectories_per_task: 1
strict_pass_rate: <recomputed>
oracle_setup: 50/50 passed
agent_workspace_setup: 50/50 passed
harness_backend: modal-sandbox
modal_app_stopped: true
```

## Later Pass@8 — Not Phase One

Pass@8 needs a new result family: eight independently initialized Sandboxes and
conversations per task, frozen seeds, genuinely stochastic sampling, separate
sample artifacts, and task-level any-of-eight aggregation.

Do not call any of these pass@8:

- eight turns in one conversation;
- infrastructure retries;
- repeated grading of one patch;
- continued work in one workspace;
- eight nominal seeds at deterministic temperature zero;
- best-patch selection without all eight complete trajectories.

Its smoke would be 2 tasks × 8 isolated trajectories and needs separate spend,
acknowledgement, resume matrix, and acceptance proof.
