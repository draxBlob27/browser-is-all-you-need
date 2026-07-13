# GLM-4.7-Flash Agentic Multi-SWE C++ On Modal

This optional lane evaluates exact-revision base GLM-4.7-Flash on the 50 C++
tasks in Multi-SWE-bench mini through one bounded SWE-agent trajectory per
task. It is repo-owned, correctness-only, and not an official Multi-SWE
leaderboard run.

Source and offline tests are implemented. No paid agentic smoke or full result
has been admitted yet. Do not publish a score from source inspection, plan
output, partial artifacts, or an unstopped Modal App.

The only entrypoint is:

~~~bash
bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
~~~

Configuration is export-only. Plan is the default and creates no paid
resources.

## What Is Fixed

- Model: zai-org/GLM-4.7-Flash at an exact 40-hex revision.
- Dataset: ByteDance-Seed/Multi-SWE-bench_mini at
  d0fab3ccc7dff232fcaac234cf8af9a2efeaccf6.
- Images: the reviewed 50-image linux/amd64 lock from the single-turn lane.
- Agent: SWE-agent 1.1.0 at
  5f40e63360d654adcd91e30ed11473389bc4909b.
- SWE-ReX: 1.4.0.
- Agent config: the pinned `config/default_backticks.yaml` blob with the
  `thought_action` parser; registry/edit/review tool trees and the exact
  100-package dependency lock are receipt-bound.
- Sampling: one deterministic trajectory per task, temperature 0, top-p 1.
- Model calls: at most 40.
- Model completion budget: 32768 tokens per turn and 131072 cumulative.
- Maximum model input: 196608 tokens.
- Agent command timeout: 120 seconds.
- Agent trajectory timeout: 1200 seconds.
- Agent Sandbox: 4 CPU, 8192 MiB, 1500-second lifetime.
- Agent concurrency: 4.
- Grader Sandbox: 2 CPU, 2048 MiB, 1200-second test timeout.
- Grader concurrency: 4.
- Full run ceiling: 43200 seconds.
- Server execution lifetime: 3600 + 43200 + 600 = 47400 seconds.
- GPU: exactly H100!:4, with one active replica only during trajectories.
- Run IDs: 3-40 lowercase letters, digits, or hyphens. The derived Modal App
  name is therefore at most 62 characters; the documented plan/smoke/full
  timestamp forms are admitted unchanged.

Turns, commands, repair steps, and infrastructure retries are not additional
samples. This lane is one-trajectory-per-task pass@1-style evidence, not
pass@8.

## Trust Boundary

The model never receives fix_patch, test_patch, oracle records, grader logs,
hidden prepared assets, Modal credentials, model/result Volumes, or the SGLang
bearer.

Each task uses two different Sandboxes:

1. The agent Sandbox starts from the exact official task image. Trusted root
   code verifies the base revision and clean tracked/submodule state,
   materializes only Git-indexed regular bytes and modes, preserves exact
   empty directories for uninitialized gitlinks, and receipt-binds their
   indexed commits and state. Populated submodules must match their indexed
   commits; mismatches and conflicts block. It removes original history and
   hidden image assets, creates an
   unprivileged w8agent account, and keeps the baseline and canary root-only.
   It has blocked network, no Secret, and no Volume.
2. Trusted root code stops the agent, rejects symlinks, special files,
   hardlinks, binary changes, traversal, forbidden paths, and oversized final
   trees, then synthesizes a unified diff from final file state. It proves the
   diff applies to a second pristine reconstruction.
3. After every required trajectory is complete, the controller lowers the
   SGLang lease to zero and drains it.
4. A separate fresh official-image grader Sandbox receives only the synthesized
   patch and, for affected simdjson tasks, the existing narrow read-only
   dependency mount.

Agent commands run through separate Sandbox.exec calls as w8agent with a clean
environment. The adapter preserves one logical working directory without a
persistent privileged shell. Upstream tool paths that hard-code root-owned
state files are rewritten into the agent-owned tools directory. The scripted
compile/output probe intentionally uses each exact official image's default C++
mode because some reviewed images predate C++20 flag support. This probe does
not change the task's pinned grader commands or acceptance policy.

## Blocking CPU Admission

Paid model work is forbidden until both all-task gates pass:

- all 50 fix_patch oracles pass the unchanged fresh Modal grader with positive
  test discovery;
- all 50 exact image/base combinations pass the sanitizer, unprivileged access,
  canary, no-secret, no-Volume, and finalizer setup checks.

An explicitly named oracle source may be the completed single-turn run. A
workspace source must be a completed agentic run. Imports require all 50 exact
current cache keys and have no fallback to execution. They import no model
responses and never mutate the source run.

The agentic and single-turn lanes share the results Volume so a single-turn
oracle proof is reachable, but they use distinct benchmark labels, result
families, run IDs, local roots, configs, and artifact schemas.

## Plan

Export Modal credentials and immutable identities locally. Never commit them.

~~~bash
export MODAL_TOKEN_ID='<local>'
export MODAL_TOKEN_SECRET='<local>'
export MODAL_PROFILE='<profile>'
export W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID="glm47-agentic-mswe-plan-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REPO='zai-org/GLM-4.7-Flash'
export W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REVISION='<40-hex>'
export W8_MODAL_AGENTIC_MULTI_SWE_DATASET_REVISION='d0fab3ccc7dff232fcaac234cf8af9a2efeaccf6'
export W8_MODAL_AGENTIC_MULTI_SWE_SGLANG_IMAGE='lmsysorg/sglang@sha256:<64-hex>'
export W8_MODAL_AGENTIC_MULTI_SWE_SWE_AGENT_REVISION='5f40e63360d654adcd91e30ed11473389bc4909b'
export W8_MODAL_AGENTIC_MULTI_SWE_PHASE='plan'
bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
~~~

Expected ending:

~~~text
phase: plan
paid_resources_created: false
~~~

Plan writes redacted local evidence under:

    .w8-biayn/modal/glm47-flash-agentic-multi-swe-cpp/runs/<run-id>/

## Paid Smoke

The smoke uses the fixed task IDs catchorg__Catch2-1608 and
fmtlib__fmt-1171. It still requires or imports all 50 oracle proofs and creates
or imports all 50 workspace proofs before GPU startup.

~~~bash
export W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID="glm47-agentic-mswe-smoke-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AGENTIC_MULTI_SWE_PHASE='smoke'
export W8_MODAL_AGENTIC_MULTI_SWE_ORACLE_SOURCE_RUN_ID='glm47-mswe-full-20260712174928'
export W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1
export W8_MODAL_AGENTIC_MULTI_SWE_RESUME=0
bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
~~~

A smoke is infrastructure admission, not a publishable 50-task model result.

## Paid Full

Run full only after a clean fixed smoke and use that completed agentic run as
the workspace-proof source.

~~~bash
export W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID="glm47-agentic-mswe-full-$(date -u +%Y%m%d%H%M%S)"
export W8_MODAL_AGENTIC_MULTI_SWE_PHASE='full'
export W8_MODAL_AGENTIC_MULTI_SWE_ORACLE_SOURCE_RUN_ID='glm47-mswe-full-20260712174928'
export W8_MODAL_AGENTIC_MULTI_SWE_WORKSPACE_SOURCE_RUN_ID='<agentic-smoke-run>'
export W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1
export W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_LONG_GPU_LEASE=1
export W8_MODAL_AGENTIC_MULTI_SWE_MAX_RUN_SECONDS=43200
export W8_MODAL_AGENTIC_MULTI_SWE_RESUME=0
bash examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh
~~~

The two acknowledgements are launch-safety gates and are excluded from immutable
benchmark identity. Full first repeats the fixed two-task smoke inside the new
run, releases the server for smoke grading, reacquires and re-admits it, then
runs the 50-task result stage and releases it again before final grading. This
is in addition to requiring a previously completed clean smoke as the
workspace-proof source.

## Resume

Resume reuses only a complete task unit whose immutable run identity matches.
A complete unit contains its safe trajectory receipt, finalizer receipt, patch,
and model outcome. An interrupted attempt is archived with only safe exception
metadata and restarts once from a pristine Sandbox. Partial conversations are
never spliced or continued.

Set:

~~~bash
export W8_MODAL_AGENTIC_MULTI_SWE_RESUME=1
~~~

Do not change model, task, image, agent, tool, budget, prompt, grader, or source
identity during benchmark-stage resume.

## Artifacts

The remote and reconciled local run contains:

~~~text
plan.json
config.redacted.json
source.receipt.json
dataset.receipt.json
image-lock.json
model-cache.receipt.json
swe-agent.identity.json
admission.response.json
server.receipt.json
server.runtime.json
server.reacquisition.json                  # full only
data/tasks/<id>/task.json                  # public metadata and hashes only
data/oracle.records/<id>.json
data/oracle.records.jsonl
data/oracle.summary.json
data/workspace.records/<id>.json
data/workspace.records.jsonl
data/workspace.summary.json
smoke|full/prompts/<id>.txt
smoke|full/trajectory-attempts/<id>/attempt-<n>/steps/<step>.json
smoke|full/trajectories/<id>/identity.json
smoke|full/trajectories/<id>/workspace.receipt.json
smoke|full/trajectories/<id>/events.jsonl
smoke|full/trajectories/<id>/summary.json
smoke|full/trajectories/<id>/tool-logs/<turn>.json
smoke|full/trajectories/<id>/final-state.manifest.json
smoke|full/trajectories/<id>/final.patch
smoke|full/trajectories/<id>/final-patch.receipt.json
smoke|full/trajectories.jsonl
smoke|full/patches/<id>.patch
smoke|full/patches.jsonl
smoke|full/records/<id>.json
smoke|full/records.jsonl
smoke|full/summary.json
run_receipt.json
artifact_manifest.json
~~~

Persisted trajectory events contain request/response hashes and lengths,
model actions, bounded observations, numeric token counters, and stop reasons.
After every completed agent step, the pinned hook durably writes only this safe
event plus newly bounded tool stream receipts to the stage/attempt path. It
does not contain raw model responses, private reasoning, bearer values, or raw
SWE-agent trajectory files. Final patches are retained because they are the
benchmark submission.

Artifact transfer validates the complete Modal Volume listing before writing,
accepts only regular files, rejects duplicate/unsafe paths, uses the pinned
16-file asynchronous bound, and reconciles bytes. Every Sandbox terminates with
wait and detach. On success or failure the wrapper explicitly stops the App,
checks the control plane, downloads committed artifacts, updates any complete
stopped receipt and manifest, and then admits a score only through local
recomputation and validation.

## Reporting Gate

Do not print or document a model score until all of these are true:

- exactly 50 task records and exactly 50 complete trajectories exist;
- every oracle proof and workspace proof passes with exact current cache keys;
- the strict summary recomputes from per-task records;
- remote and local artifacts reconcile byte-for-byte;
- the run receipt proves the Modal App is stopped;
- no infrastructure-failed record enters the denominator.

Label any eventual evidence repo-owned, agentic, correctness-only, and
modal-sandbox. Never call it an official leaderboard result, an Aider result,
pass@8, or PIE performance evidence.

## Offline Validation

~~~bash
uv run --extra dev pytest -q tests/test_modal_agentic_multi_swe_cpp.py
uv run --extra dev ruff check \
  src/w8_biayn/modal_agentic_multi_swe_cpp.py \
  src/w8_biayn/modal_agentic_multi_swe_runtime.py \
  src/w8_biayn/integrations/modal_swe_agent_driver.py \
  examples/modal/glm47_flash_agentic_multi_swe_cpp/modal_app.py \
  tests/test_modal_agentic_multi_swe_cpp.py
uv run python -m compileall src tests
~~~

These checks spend nothing. Real CPU sanitizer canaries, SGLang admission, one
trajectory, fixed smoke, and full evidence remain paid acceptance stages.
