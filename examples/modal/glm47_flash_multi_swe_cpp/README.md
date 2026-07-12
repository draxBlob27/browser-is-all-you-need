# GLM-4.7-Flash Multi-SWE C++ Base Eval On Modal

This optional lane evaluates base zai-org/GLM-4.7-Flash on the 50 C++ tasks in
ByteDance-Seed/Multi-SWE-bench_mini. It reuses the repository single-turn
unified-diff prompt, strict parser, forbidden-path policy, official-image test
contract, oracle proof, and correctness summary.

It is separate from PIE training, the Moonlight SLIME Multi-SWE lane, and the
official Multi-SWE evaluator. It is a repo-owned result, not a leaderboard
score. Source and offline tests are implemented; paid Modal validation remains
pending. Do not quote a model score until a complete 50-task receipt proves
modal_app_stopped: true and the local artifact copy revalidates.

## One entrypoint

Run from the repository root:

    bash examples/modal/glm47_flash_multi_swe_cpp/run.sh

Configuration is export-only. Plan is the default and creates no paid
resources. Smoke/full require explicit acknowledgement. Full always runs the
all-task oracle and fixed two-task smoke first.

## Required exports

    export MODAL_TOKEN_ID='<secret>'
    export MODAL_TOKEN_SECRET='<secret>'
    export MODAL_PROFILE='<profile>'

    export W8_MODAL_MULTI_SWE_RUN_ID="glm47-mswe-cpp-$(date -u +%Y%m%d%H%M%S)"
    export W8_MODAL_MULTI_SWE_MODEL_REPO='zai-org/GLM-4.7-Flash'
    export W8_MODAL_MULTI_SWE_MODEL_REVISION='<40-lowercase-hex-commit>'
    export W8_MODAL_MULTI_SWE_DATASET_REVISION='d0fab3ccc7dff232fcaac234cf8af9a2efeaccf6'
    export W8_MODAL_MULTI_SWE_SGLANG_IMAGE='lmsysorg/sglang@sha256:<64-hex>'

HF_TOKEN is optional and downloader-only. Modal credentials stay in the local
control plane. The random SGLang bearer reaches only the server and request
orchestrator. Grading Sandboxes receive no secrets.

## Plan

    export W8_MODAL_MULTI_SWE_PHASE=plan
    bash examples/modal/glm47_flash_multi_swe_cpp/run.sh

Plan validates immutable identities, the checked-in 50-image linux/amd64 lock,
resource bounds, redaction, local paths, and expected commands. It authenticates
with Modal but exits before modal run, Image imports, Sandboxes, or GPU use.

## Image-lock maintenance

Normal plan, smoke, and full runs only consume the reviewed checked-in lock.
They never contact the registry to resolve mutable tags. A maintainer updating
the pinned dataset may explicitly regenerate and review the lock:

    uv run python -m w8_biayn.modal_multi_swe_cpp generate-lock \
      --dataset-jsonl /path/to/multi_swe_bench_mini.jsonl \
      --out examples/modal/glm47_flash_multi_swe_cpp/mswebench-images.lock.json
    uv run python -m w8_biayn.modal_multi_swe_cpp verify-lock \
      --lock examples/modal/glm47_flash_multi_swe_cpp/mswebench-images.lock.json

Generation resolves only the linux/amd64 manifest for each exact official
lowercase task tag and writes deterministic sorted JSON. It is a deliberate
networked maintenance action, never an implicit benchmark step.

## Smoke and full

    export W8_MODAL_MULTI_SWE_PHASE=smoke
    export W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1
    bash examples/modal/glm47_flash_multi_swe_cpp/run.sh

Smoke still runs all 50 fix_patch oracles before model loading, then admits the
real four-H100 server and grades two fixed model responses. Model failure is
allowed; transport, image, Sandbox, harness, oracle, or artifact failure blocks.

    export W8_MODAL_MULTI_SWE_PHASE=full
    export W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1
    export W8_MODAL_MULTI_SWE_GPU='H100!:4'
    export W8_MODAL_MULTI_SWE_MAX_TOKENS=32768
    export W8_MODAL_MULTI_SWE_TEMPERATURE=0
    export W8_MODAL_MULTI_SWE_TOP_P=1
    bash examples/modal/glm47_flash_multi_swe_cpp/run.sh

The first result family fixes one response per task, temperature zero, top-p
one, 32,768 completion tokens, one SGLang replica, four strict H100s, and four
concurrent graders. It reports strict pass rate, not pass@k or PIE speed.

## Grader contract

Every oracle or candidate patch receives a fresh Modal Sandbox built from the
task's exact checked-in mswebench image digest. Networking is blocked. CPU and
memory request/limit are both 2 cores and 2,048 MiB. The Sandbox has a bounded
lifetime and the test exec has a 1,200-second ceiling.

The candidate is written to /home/fix.patch through Modal's filesystem API.
The shared official-image shell verifies the base ref and trusted test.patch,
applies the candidate, runs the prepared build/tests, and requires positive
CTest discovery. The simdjson dependency trees are checksum-pinned and staged
beneath one dedicated parent that is mounted once, read-only, at the fresh
/mnt/w8-biayn-simdjson-dependencies-v2 path. The trusted grader shell runs
after patch preflight and replaces only the expected cxxopts and
.cache/simdjson-data locations with symlinks into that mount before the test
body. This detached-parent layout is required because Modal SDK 1.5.2 rejects
both mounting the same Volume object at multiple paths and mounting over the
official image's already non-empty /home/simdjson/dependencies directory.
CTest discovery is parsed from the complete in-memory stdout/stderr streams
before persistence truncation; the artifact keeps the numeric count, per-stream
sizes/hashes, and bounded tails from both streams. This prevents PR 958's large
non-fatal GCC stderr from hiding the successful CTest summary on stdout without
relaxing the positive-test gate. The PR 958 capture strategy is cache-key
bound. Every Sandbox is terminated with wait and detached in finally.

Strict model output is exactly one fenced diff and nothing else. Reasoning is
kept separate by SGLang; only message.content enters the parser. Recovery is
diagnostic only.

## Artifacts and resume

Artifacts live under:

    .w8-biayn/modal/glm47-flash-multi-swe-cpp/runs/<run-id>/

The run stores redacted config/source/dataset/model/server/image identities,
incremental oracle records, per-task requests/responses/records/bounded logs,
summaries, receipt, and a SHA-256 artifact manifest. Modal SDK 1.5.2 downloads
only exact FileEntryType.FILE entries, validates all paths, uses 16 concurrent
reads, and reconciles bytes.

Resume is normally only for an incomplete exact-identity run. One narrow
recovery exception exists for a run that has only oracle artifacts and has not
persisted any model-cache, SGLang, admission, smoke, full, or final receipt:
source commit and file hashes may migrate so an infrastructure fix can continue
the same paid oracle run. The migration is audit-recorded, and passing oracle
records still reuse only by their exact cache keys. Once model/server work has
begun, source identity is strict again. Saved responses and grader records
always require their exact identities and cache keys. Completed runs are
immutable. A fresh run ID remains the normal path.

## Teardown and failure recovery

The wrapper installs traps before authentication. It explicitly stops the
deterministic App on success, error, or signal, verifies stopped state through
the control plane, updates the receipt, reconciles artifacts, and only then
prints a score.

Manual recovery:

    uv run --extra modal modal app stop       "w8-glm47-multi-swe-cpp-${W8_MODAL_MULTI_SWE_RUN_ID}" --yes
    uv run --extra modal modal app list --json

## Validation and paid ladder

Offline:

    uv run --extra dev pytest       tests/test_modal_multi_swe_cpp.py       tests/test_modal_aider_polyglot_cpp.py       tests/test_slime_multi_swe_cpp.py
    uv run --extra dev ruff check       src/w8_biayn/modal_glm47.py       src/w8_biayn/modal_multi_swe_cpp.py       src/w8_biayn/modal_multi_swe_runtime.py       examples/modal/glm47_flash_multi_swe_cpp/modal_app.py       tests/test_modal_multi_swe_cpp.py
    bash -n examples/modal/glm47_flash_multi_swe_cpp/run.sh

Paid validation must proceed through plan/auth, CPU Volume readback, exact image
probe, network-blocked filesystem/exec/terminate test, ordinary and special
oracle parity, all 50 oracles, model cache, SGLang admission, one task, fixed
smoke, then full. Every infrastructure failure becomes an offline regression
before continuing.
