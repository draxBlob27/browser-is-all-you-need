from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from types import SimpleNamespace
from typing import Any, Callable

import pytest

import w8_biayn.modal_agentic_multi_swe_cpp as contract
import w8_biayn.modal_agentic_multi_swe_runtime as runtime
from w8_biayn.integrations.modal_swe_agent_driver import (
    ModalSandboxRuntime,
    _bounded_observation,
    ModalSandboxSWEEnv,
    _rewrite_root_paths,
    workspace_finalizer_program,
    workspace_sanitizer_program,
)
from w8_biayn.integrations.slime_multi_swe_cpp import (
    MultiSweRepoHarness,
    build_prompt,
    build_public_issue_context,
)
from w8_biayn.modal_multi_swe_cpp import build_artifact_manifest
from w8_biayn.modal_agentic_multi_swe_cpp import (
    AGENT_CALL_LIMIT,
    AGENT_CUMULATIVE_COMPLETION_TOKENS,
    AGENT_MAX_INPUT_TOKENS,
    AGENT_SANDBOX_CPU,
    AGENT_SANDBOX_MEMORY_MIB,
    AGENT_TURN_MAX_COMPLETION_TOKENS,
    BENCHMARK_LABEL,
    DATASET_REVISION,
    EXPECTED_CPP_TASKS,
    FULL_MAX_RUN_SECONDS,
    MODEL_REPO,
    OBSERVATION_CHAR_LIMIT,
    PERSISTED_STREAM_BYTE_LIMIT,
    RESULT_FAMILY,
    SWE_AGENT_COMMIT,
    SERVER_EXECUTION_TIMEOUT_SECONDS,
    ModalAgenticMultiSweConfig,
    ModalAgenticMultiSweError,
    agent_problem_statement,
    aggregate_agentic_records,
    build_workspace_summary,
    classify_agentic_result,
    render_plan,
    safe_trajectory_event,
    validate_final_patch,
    validate_local_artifacts,
    workspace_cache_key,
)


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "examples/modal/glm47_flash_agentic_multi_swe_cpp"
MODAL_APP = LANE / "modal_app.py"
RUN_SH = LANE / "run.sh"
LOCKFILE = LANE / "swe-agent.requirements.lock"
DRIVER = ROOT / "src/w8_biayn/integrations/modal_swe_agent_driver.py"
RUNTIME = ROOT / "src/w8_biayn/modal_agentic_multi_swe_runtime.py"


def valid_env(**overrides: str) -> dict[str, str]:
    env = {
        "MODAL_TOKEN_ID": "modal-id-sentinel",
        "MODAL_TOKEN_SECRET": "modal-secret-sentinel",
        "MODAL_PROFILE": "test-profile",
        "HF_TOKEN": "hf-secret-sentinel",
        "W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID": "agentic-mswe-test",
        "W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REPO": MODEL_REPO,
        "W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REVISION": "a" * 40,
        "W8_MODAL_AGENTIC_MULTI_SWE_DATASET_REVISION": DATASET_REVISION,
        "W8_MODAL_AGENTIC_MULTI_SWE_SWE_AGENT_REVISION": SWE_AGENT_COMMIT,
        "W8_MODAL_AGENTIC_MULTI_SWE_SGLANG_IMAGE": (
            "lmsysorg/sglang@sha256:" + "b" * 64
        ),
        "W8_MODAL_AGENTIC_MULTI_SWE_PHASE": "plan",
    }
    env.update(overrides)
    return env


def config(tmp_path: Path, **overrides: str) -> ModalAgenticMultiSweConfig:
    return ModalAgenticMultiSweConfig.from_env(
        valid_env(**overrides), repo_root=tmp_path
    )


def task(task_id: str = "fmtlib__fmt-1171") -> dict[str, object]:
    return {
        "instance_id": task_id,
        "org": "fmtlib",
        "repo": "fmt",
        "repo_full_name": "fmtlib/fmt",
        "base_ref": "a" * 40,
        "test_patch": "",
        "fix_patch": valid_patch(),
        "sandbox_image_digest": (
            "mswebench/fmtlib_m_fmt@sha256:" + "c" * 64
        ),
    }


def valid_patch() -> str:
    return """diff --git a/include/fmt/core.h b/include/fmt/core.h
--- a/include/fmt/core.h
+++ b/include/fmt/core.h
@@ -1 +1 @@
-old
+new
"""


def harness() -> MultiSweRepoHarness:
    return MultiSweRepoHarness(
        org="fmtlib",
        repo="fmt",
        git_url="https://invalid/fmt.git",
        test_command="true",
    )


def test_plan_is_deterministic_redacted_and_no_spend(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    plan = render_plan(cfg)

    assert plan == render_plan(cfg)
    assert plan["benchmark"] == BENCHMARK_LABEL
    assert plan["result_family"] == RESULT_FAMILY
    assert plan["action"] == "no paid resources"
    assert plan["blocking_gates"] == {
        "all_50_oracles_before_gpu": True,
        "all_50_workspace_proofs_before_gpu": True,
        "fixed_smoke_before_full": False,
        "release_gpu_before_grading": True,
        "stopped_app_before_score": False,
    }
    assert plan["agent"]["call_limit"] == AGENT_CALL_LIMIT == 40
    assert (
        plan["agent"]["per_turn_completion_tokens"]
        == AGENT_TURN_MAX_COMPLETION_TOKENS
        == 32768
    )
    assert (
        plan["agent"]["cumulative_completion_tokens"]
        == AGENT_CUMULATIVE_COMPLETION_TOKENS
        == 131072
    )
    assert plan["agent"]["max_input_tokens"] == AGENT_MAX_INPUT_TOKENS
    assert plan["agent"]["sandbox"]["cpu"] == AGENT_SANDBOX_CPU == 4.0
    assert (
        plan["agent"]["sandbox"]["memory_mib"]
        == AGENT_SANDBOX_MEMORY_MIB
        == 8192
    )
    assert plan["agent"]["sandbox"]["secrets"] == []
    assert plan["agent"]["sandbox"]["volumes"] == []
    assert plan["grader"]["after_gpu_release"] is True
    assert plan["server"]["execution_timeout_seconds"] == 47400
    assert SERVER_EXECUTION_TIMEOUT_SECONDS == 3600 + 43200 + 600
    assert cfg.max_run_seconds == FULL_MAX_RUN_SECONDS == 43200
    rendered = json.dumps(plan)
    for secret in (
        "modal-id-sentinel",
        "modal-secret-sentinel",
        "hf-secret-sentinel",
    ):
        assert secret not in rendered


def test_documented_run_ids_fit_the_modal_app_name_limit(
    tmp_path: Path,
) -> None:
    for phase in ("plan", "smoke", "full"):
        run_id = f"glm47-agentic-mswe-{phase}-20260713123456"
        cfg = config(
            tmp_path,
            W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID=run_id,
        )
        assert len(run_id) <= 40
        assert len(cfg.app_name) <= 63

    with pytest.raises(ModalAgenticMultiSweError, match="unsafe value"):
        config(
            tmp_path,
            W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID="a" * 41,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_PHASE": "smoke"},
            "ACKNOWLEDGE_PAID_RUN",
        ),
        (
            {
                "W8_MODAL_AGENTIC_MULTI_SWE_PHASE": "full",
                "W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN": "1",
            },
            "ACKNOWLEDGE_LONG_GPU_LEASE",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_AGENT_CALL_LIMIT": "41"},
            "agent calls",
        ),
        (
            {
                "W8_MODAL_AGENTIC_MULTI_SWE_AGENT_CUMULATIVE_COMPLETION_TOKENS": (
                    "131073"
                )
            },
            "cumulative completion tokens",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_SAMPLES_PER_TASK": "2"},
            "one trajectory",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_MAX_RUN_SECONDS": "14400"},
            "maximum run time",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_MODEL_REPO": "mutable/model"},
            "model repository",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_SWE_AGENT_REVISION": "b" * 40},
            "SWE-agent revision",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_DATASET_REVISION": "b" * 40},
            "dataset revision",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_SGLANG_IMAGE": "latest"},
            "digest-pinned",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_GPU": "H100:4"},
            "GPU",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_SGLANG_MEM_FRACTION": "0.7"},
            "memory fraction",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_AGENT_CONCURRENCY": "5"},
            "agent concurrency",
        ),
        (
            {"W8_MODAL_AGENTIC_MULTI_SWE_IMAGE_LOCK": "/tmp/lock.json"},
            "image lock path",
        ),
        (
            {
                "W8_MODAL_AGENTIC_MULTI_SWE_PHASE": "smoke",
                "W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN": "1",
                "W8_MODAL_AGENTIC_MULTI_SWE_WORKSPACE_SOURCE_RUN_ID": "source-run",
            },
            "workspace proof import",
        ),
    ],
)
def test_config_rejects_noncanonical_or_unacknowledged_values(
    tmp_path: Path, overrides: dict[str, str], message: str
) -> None:
    with pytest.raises(ModalAgenticMultiSweError, match=message):
        config(tmp_path, **overrides)


def test_full_acknowledgements_are_launch_gates_not_identity(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path)
    assert "acknowledge_paid_run" not in cfg.identity_mapping()
    assert "acknowledge_long_gpu_lease" not in cfg.identity_mapping()
    assert "phase" not in cfg.identity_mapping()


def test_public_context_extraction_preserves_single_turn_prompt() -> None:
    row = {
        "title": "Fix formatting",
        "body": "The formatter mishandles one input.",
        "resolved_issues": ["No hidden tests here."],
        "base": {"sha": "a" * 40},
        "fix_patch": "W8_HIDDEN_FIX_SENTINEL",
        "test_patch": "W8_HIDDEN_TEST_SENTINEL",
        "target_commit": "W8_HIDDEN_TARGET_SENTINEL",
        "image_inventory": "W8_HIDDEN_IMAGE_SENTINEL",
        "oracle_failure": "W8_HIDDEN_ORACLE_SENTINEL",
        "test_buckets": "W8_HIDDEN_BUCKET_SENTINEL",
    }
    public = build_public_issue_context(
        row, harness=harness(), instance_id="fmtlib__fmt-1171"
    )
    strict = build_prompt(
        row, harness=harness(), instance_id="fmtlib__fmt-1171"
    )
    agentic = agent_problem_statement(
        row, harness=harness(), instance_id="fmtlib__fmt-1171"
    )

    assert strict.startswith(public + "\n\n")
    assert "Return exactly one unified diff" in strict
    assert agentic.startswith(public + "\n\n")
    assert "Work directly in the repository" in agentic
    assert "fix_patch" not in agentic
    assert "test_patch" not in agentic

    assert "W8_HIDDEN_FIX_SENTINEL" not in agentic
    assert "W8_HIDDEN_TEST_SENTINEL" not in agentic
    assert "W8_HIDDEN_TARGET_SENTINEL" not in agentic
    assert "W8_HIDDEN_IMAGE_SENTINEL" not in agentic
    assert "W8_HIDDEN_ORACLE_SENTINEL" not in agentic
    assert "W8_HIDDEN_BUCKET_SENTINEL" not in agentic

def test_safe_trajectory_hashes_model_io_without_persisting_it() -> None:
    step = {
        "query": "private request",
        "output": "private reasoning and answer",
        "thought": "never persist",
        "action": "sed -n '1,20p' src/a.cpp",
        "observation": "x" * 40000,
    }
    event = safe_trajectory_event(step, 3)

    assert event["request_sha256"] == hashlib.sha256(
        step["query"].encode()
    ).hexdigest()
    assert event["response_sha256"] == hashlib.sha256(
        step["output"].encode()
    ).hexdigest()
    assert event["observation_truncated"] is True
    serialized = json.dumps(event)
    assert step["query"] not in serialized
    assert step["output"] not in serialized
    assert step["thought"] not in serialized
    assert "reasoning" not in serialized


def test_agentic_final_state_has_distinct_model_outcomes() -> None:
    no_changes = classify_agentic_result(
        task=task(),
        finalization={"status": "no_changes", "patch": ""},
        execution=None,
        trajectory={"event_count": 1},
    )
    invalid = classify_agentic_result(
        task=task(),
        finalization={"status": "invalid_final_state", "patch": ""},
        execution=None,
        trajectory={"event_count": 1},
    )

    assert no_changes["reason"] == "no_changes"
    assert invalid["reason"] == "invalid_submission"
    assert no_changes["invalid_format"] is False
    assert invalid["invalid_format"] is False


def test_final_patch_uses_existing_forbidden_path_policy() -> None:
    assert validate_final_patch(task(), valid_patch()) == (
        "include/fmt/core.h",
    )
    bad = valid_patch().replace(
        "include/fmt/core.h", "tests/core-test.cpp"
    )
    with pytest.raises(ModalAgenticMultiSweError):
        validate_final_patch(task(), bad)


def test_workspace_cache_binds_sanitizer_finalizer_image_and_base() -> None:
    row = task()
    key = workspace_cache_key(
        row, str(row["sandbox_image_digest"])
    )
    changed = workspace_cache_key(
        {**row, "base_ref": "d" * 40},
        str(row["sandbox_image_digest"]),
    )
    assert key != changed
    assert len(key) == 64


def test_workspace_summary_requires_all_50_exact_passes() -> None:
    rows = [{"passed": True} for _ in range(EXPECTED_CPP_TASKS)]
    assert build_workspace_summary(rows)["all_passed"] is True
    rows[-1] = {"passed": False}
    assert build_workspace_summary(rows)["all_passed"] is False


def test_prepare_proofs_finishes_all_oracles_before_workspaces(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = config(tmp_path)
    tasks = [
        {
            **task(f"task-{index:02d}"),
            "base_ref": f"{index:040x}",
        }
        for index in range(EXPECTED_CPP_TASKS)
    ]
    lock = {
        "tasks": {
            row["instance_id"]: {
                "digest": row["sandbox_image_digest"]
            }
            for row in tasks
        }
    }
    events: list[str] = []
    persisted: dict[str, object] = {}

    monkeypatch.setattr(
        runtime,
        "_oracle_key",
        lambda row, lock_row: "oracle-" + row["instance_id"],
    )
    monkeypatch.setattr(
        runtime,
        "classify_response",
        lambda **kwargs: {
            "all_tests_pass": True,
            "tests_collected": 1,
            "reason": "passed",
        },
    )

    def grade(row: dict[str, Any], patch: str) -> dict[str, Any]:
        events.append("oracle:" + row["instance_id"])
        return {"returncode": 0}

    def workspace(row: dict[str, Any]) -> dict[str, Any]:
        events.append("workspace:" + row["instance_id"])
        return {"passed": True}

    staged = runtime.prepare_proofs(
        config=cfg,
        lock=lock,
        tasks=tasks,
        dataset_receipt={"status": "complete"},
        grade=grade,
        workspace_probe=workspace,
        persist=lambda files: persisted.update(files),
    )

    assert staged["oracle_summary"]["all_passed"] is True
    assert staged["workspace_summary"]["all_passed"] is True
    assert all(
        event.startswith("oracle:") for event in events[:50]
    )
    assert all(
        event.startswith("workspace:") for event in events[50:]
    )
    assert "data/oracle.summary.json" in persisted
    assert "data/workspace.summary.json" in persisted


def test_sanitizer_and_finalizer_enforce_trusted_boundary() -> None:
    row = task()
    sanitizer = workspace_sanitizer_program(row)
    finalizer = workspace_finalizer_program(row)

    compile(sanitizer, "<workspace-sanitizer>", "exec")
    compile(finalizer, "<workspace-finalizer>", "exec")

    for required in (
        '"status",',
        '"--porcelain",',
        '"--untracked-files=all",',
        '"submodule", "status", "--recursive"',
        "tracked symlinks are forbidden",
        'line.startswith(("+", "U"))',
        '"state": "uninitialized-empty"',
        '"state": "materialized"',
        "--user-group",
        "tracked_entries",
        "baseline.manifest.json",
        "synthetic_commit_count",
        "source_checkout_removed",
        "agent-must-not-read",
        '"w8agent:w8agent"',
        "network_blocked_by_controller",
        "secrets_mounted",
        "volumes_mounted",
    ):
        assert required in sanitizer
    assert (
        contract.SANITIZER_REVISION
        == "modal-agent-workspace-sanitizer-v2"
    )
    for required in (
        "pkill",
        "st_nlink != 1",
        "GIT binary patch",
        '"apply", "--check", "-"',
        "trusted_apply_check",
        "final.patch",
        "final-state.manifest.json",
        '"--numstat"',
        '"-M"',
    ):
        assert required in finalizer


def test_root_path_rewriter_and_agent_shell_keep_state_in_workspace() -> None:
    rewritten = _rewrite_root_paths(
        "cat /root/state.json && cp /root/model.patch /tmp/x"
    )
    assert "/root/state.json" not in rewritten
    assert "/root/model.patch" not in rewritten
    assert "/workspace/tools/state.json" in rewritten
    assert "/workspace/tools/model.patch" in rewritten

    class Stub:
        pass

    command = ModalSandboxSWEEnv(Stub())._command("pwd")
    joined = " ".join(command)
    assert "runuser -u w8agent" in joined
    assert "env -i" in joined
    assert "SGLANG_API_KEY" not in joined
    assert "MODAL_TOKEN" not in joined


def test_dependency_lock_and_source_pins_are_exact() -> None:
    rows = LOCKFILE.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 100
    assert "swe-rex==1.4.0" in rows
    assert "litellm==1.92.0" in rows
    assert "pydantic==2.13.4" in rows
    assert not any(row.startswith("swe-agent==") for row in rows)
    source = MODAL_APP.read_text(encoding="utf-8")
    assert "git -C /opt/swe-agent checkout --detach " in source
    assert "HEAD:config/default_backticks.yaml" in source
    assert "pip install --no-deps -e /opt/swe-agent" in source
    assert 'config_path: str | Path = "/opt/swe-agent/config/default_backticks.yaml"' in DRIVER.read_text(encoding="utf-8")


def test_modal_source_preserves_resource_and_lifetime_ordering() -> None:
    app_source = MODAL_APP.read_text(encoding="utf-8")
    runtime_source = RUNTIME.read_text(encoding="utf-8")
    driver_source = DRIVER.read_text(encoding="utf-8")

    assert "@app.server" not in app_source
    assert "@modal.web_server(" in app_source
    assert "timeout=SERVER_EXECUTION_TIMEOUT_SECONDS" in app_source
    assert "min_containers=0" in app_source
    assert "min_containers=1" in app_source
    assert (
        "scaledown_window=SGLANG_POST_GENERATION_WINDOW_SECONDS"
        in app_source
    )
    assert "block_network=True" in app_source
    assert "volumes={}" in app_source
    assert "secrets=[]" in app_source
    release_index = runtime_source.index("release_gpu()")
    grading_index = runtime_source.index(
        "execution = grade(task", release_index
    )
    assert release_index < grading_index
    assert "raw_trajectory_persisted" in driver_source
    assert "reasoning_persisted" in driver_source
    assert "SafeIncrementalHook" in driver_source
    assert "event_sink=persist_incremental" in app_source
    workspace_probe_source = app_source[
        app_source.index("def workspace_probe") : app_source.index(
            "def run_agent_trajectory"
        )
    ]
    assert "workspace_finalizer_program(task)" in workspace_probe_source
    assert "c++ /workspace/tmp/w8-canary.cpp" in workspace_probe_source
    assert "c++ -std=c++20 /workspace/tmp/w8-canary.cpp" not in (
        workspace_probe_source
    )
    assert (
        contract.WORKSPACE_CANARY_REVISION
        == "hostile-path-tool-compile-v2"
    )


def test_wrapper_is_plan_first_export_only_and_double_gated() -> None:
    source = RUN_SH.read_text(encoding="utf-8")
    assert "positional configuration is unsupported" in source
    assert "modal_agentic_multi_swe_cpp plan" in source
    assert "paid_resources_created: false" in source
    assert "W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN" in source
    assert "W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_LONG_GPU_LEASE" in source
    assert source.index("trap cleanup") < source.index("modal token info")
    assert 'run_modal app stop "$APP_NAME" --yes' in source
    assert "validate-artifacts" in source
    assert "volume get --force" in source
    assert source.index("volume get --force") < source.index(
        "modal_agentic_multi_swe_cpp mark-stopped"
    )
    assert "modal deploy" not in source
    assert "modal serve" not in source

def test_exact_upload_request_stages_and_rewrites_tool_tree(
    tmp_path: Path,
) -> None:
    source = tmp_path / "registry"
    (source / "bin").mkdir(parents=True)
    (source / "bin/state").write_text(
        "#!/bin/sh\ncat /root/state.json\n",
        encoding="utf-8",
    )

    class Process:
        stdout = SimpleNamespace(read=lambda: "")
        stderr = SimpleNamespace(read=lambda: "")

        def wait(self) -> int:
            return 0

    class Filesystem:
        def __init__(self) -> None:
            self.writes: dict[str, bytes] = {}

        def write_bytes(self, value: bytes, path: str) -> None:
            self.writes[path] = value

    class Sandbox:
        def __init__(self) -> None:
            self.filesystem = Filesystem()
            self.commands: list[tuple[str, ...]] = []


        def exec(self, *args: str, **kwargs: Any) -> Process:
            self.commands.append(args)
            return Process()

    sandbox = Sandbox()
    adapter = ModalSandboxRuntime(sandbox)
    request = SimpleNamespace(
        source_path=str(source),
        target_path="/root/tools/registry",
    )
    asyncio.run(adapter.upload(request))

    target = "/workspace/tools/registry/bin/state"
    assert target in sandbox.filesystem.writes
    staged = sandbox.filesystem.writes[target].decode()
    assert "/root/state.json" not in staged
    assert "/workspace/tools/state.json" in staged
    assert (
        "chown",
        "-R",
        "w8agent:w8agent",
        "/workspace/tools/registry",
    ) in sandbox.commands



def _execute_finalizer(
    tmp_path: Path,
    mutate: Any,
    *,
    program_transform: Callable[[str], str] | None = None,
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    baseline = tmp_path / "baseline" / "repo"
    workspace = tmp_path / "workspace" / "repo"
    trusted = tmp_path / "trusted"
    output = tmp_path / "output"
    baseline.mkdir(parents=True)
    (baseline / "src").mkdir()
    (baseline / "src/original.cpp").write_text("int value = 1;\n")
    (baseline / "src/delete.cpp").write_text("int deleted = 1;\n")
    (baseline / "src/rename.cpp").write_text("int renamed = 1;\n")
    shutil.copytree(baseline, workspace)
    trusted.mkdir()
    output.mkdir()
    with tarfile.open(trusted / "baseline.tar", "w") as archive:
        archive.add(baseline, arcname="repo")
    mutate(workspace)
    program = workspace_finalizer_program(task())
    if program_transform is not None:
        program = program_transform(program)
    replacements = {
        "/workspace/repo": workspace.as_posix(),
        "/opt/w8-trusted": trusted.as_posix(),
        "/opt/w8-output": output.as_posix(),
        "/opt/w8-reconstruct-current": (tmp_path / "reconstruct-current").as_posix(),
        "/opt/w8-reconstruct-check": (tmp_path / "reconstruct-check").as_posix(),
    }
    for source, target in replacements.items():
        program = program.replace(source, target)
    program = program.replace(
        'subprocess.run(["pkill", "-KILL", "-u", "w8agent"], check=False)',
        'subprocess.run(["true"], check=False)',
    )
    exec(compile(program, "<workspace-finalizer-test>", "exec"), {})
    receipt = json.loads(
        (output / "finalizer.receipt.json").read_text(encoding="utf-8")
    )
    patch = (output / "final.patch").read_text(encoding="utf-8")
    manifest = json.loads(
        (output / "final-state.manifest.json").read_text(encoding="utf-8")
    )
    return receipt, patch, manifest


def test_trusted_finalizer_captures_edits_adds_deletes_and_renames(
    tmp_path: Path,
) -> None:
    def mutate(workspace: Path) -> None:
        (workspace / "src/original.cpp").write_text("int value = 2;\n")
        (workspace / "src/delete.cpp").unlink()
        (workspace / "src/rename.cpp").rename(workspace / "src/moved.cpp")
        (workspace / "src/added.cpp").write_text("int added = 1;\n")

    receipt, patch, manifest = _execute_finalizer(tmp_path, mutate)

    assert receipt["status"] == "valid_patch"
    assert receipt["trusted_apply_check"] is True
    assert receipt["changed_file_count"] >= 4
    assert receipt["changed_line_count"] >= 3
    assert "src/original.cpp" in patch
    assert "src/delete.cpp" in patch
    assert "src/added.cpp" in patch
    assert any(row["path"] == "src/moved.cpp" for row in manifest)


def test_trusted_finalizer_rejects_symlink_final_state(tmp_path: Path) -> None:
    def mutate(workspace: Path) -> None:
        (workspace / "src/escape.cpp").symlink_to("/etc/passwd")

    receipt, patch, _ = _execute_finalizer(tmp_path, mutate)

    assert receipt["status"] == "invalid_final_state"
    assert receipt["trusted_apply_check"] is False
    assert patch == ""


def test_tool_receipt_bounds_streams_hashes_exit_and_cleanup() -> None:
    marker = "\n__W8_MODAL_CWD__/workspace/repo\n"

    class Reader:
        def __init__(self, value: str) -> None:
            self.value = value

        def read(self) -> str:
            return self.value

    class Process:
        def __init__(self, stdout: str, stderr: str, code: int) -> None:
            self.stdout = Reader(stdout)
            self.stderr = Reader(stderr)
            self.code = code

        def wait(self) -> int:
            return self.code

    class Sandbox:
        def __init__(self) -> None:
            self.commands: list[tuple[str, ...]] = []

        def exec(self, *args: str, **kwargs: Any) -> Process:
            self.commands.append(args)
            if args[0] == "runuser":
                return Process("x" * 70000 + marker, "y" * 70000, 7)
            return Process("", "", 1)

    sandbox = Sandbox()
    environment = ModalSandboxSWEEnv(sandbox)
    observation = environment.communicate("printf test", check="ignore")
    event = environment.tool_events[-1]

    assert len(observation) == OBSERVATION_CHAR_LIMIT
    assert event["returncode"] == 7
    assert event["timed_out"] is False
    assert event["background_cleanup_ok"] is True
    assert event["stdout"]["byte_count"] == 70000
    assert event["stderr"]["byte_count"] == 70000
    assert event["stdout"]["truncated"] is True
    assert len(event["stdout"]["head"].encode()) == PERSISTED_STREAM_BYTE_LIMIT // 2
    assert any(command[:4] == ("pkill", "-KILL", "-u", "w8agent") for command in sandbox.commands)
    assert len(_bounded_observation("z" * 100000)) == OBSERVATION_CHAR_LIMIT


def test_workspace_cache_key_binds_canary_and_tool_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = task()
    original = workspace_cache_key(row, str(row["sandbox_image_digest"]))
    monkeypatch.setattr(contract, "WORKSPACE_CANARY_REVISION", "changed-canary")
    changed = workspace_cache_key(row, str(row["sandbox_image_digest"]))
    assert original != changed


def test_full_runs_fixed_smoke_then_reacquires_before_all_50(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path)
    object.__setattr__(cfg, "phase", "full")
    task_ids = list(contract.SMOKE_TASK_IDS) + [
        f"task-{index:02d}" for index in range(EXPECTED_CPP_TASKS - 2)
    ]
    tasks = [
        {
            **task(task_id),
            "agent_problem_statement": f"public prompt {task_id}",
            "agent_problem_statement_sha256": hashlib.sha256(
                f"public prompt {task_id}".encode()
            ).hexdigest(),
            "issue_context_sha256": "d" * 64,
        }
        for task_id in task_ids
    ]
    lock = {
        "sha256": "e" * 64,
        "tasks": {
            row["instance_id"]: {"digest": row["sandbox_image_digest"]}
            for row in tasks
        },
    }
    staged = {
        "tasks": tasks,
        "oracle_summary": {"all_passed": True, "passed_count": 50},
        "workspace_summary": {"all_passed": True, "passed": 50},
    }
    calls: list[str] = []
    lifecycle: list[str] = []
    persisted: dict[str, Any] = {}

    def run(row: dict[str, Any], attempt: int) -> dict[str, Any]:
        calls.append(row["instance_id"])
        return {
            "trajectory": {
                "events": [],
                "tool_events": [],
                "event_count": 0,
                "tool_event_count": 0,
                "exit_status": "submitted",
                "model_stats": {"api_calls": 1, "tokens_received": 2},
            },
            "finalization": {
                "status": "no_changes",
                "patch": "",
                "changed_file_count": 0,
                "changed_line_count": 0,
            },
            "final_state_manifest": [],
            "workspace_receipt": {"task_id": row["instance_id"]},
        }

    result = runtime.evaluate(
        config=cfg,
        lock=lock,
        staged=staged,
        run_trajectory=run,
        grade=lambda row, patch: pytest.fail("no-change state must not grade"),
        release_gpu=lambda: lifecycle.append("release"),
        acquire_gpu=lambda: lifecycle.append("acquire"),
        persist=lambda files: persisted.update(files),
    )

    assert len(calls) == 52
    assert all(calls.count(task_id) == 2 for task_id in contract.SMOKE_TASK_IDS)
    assert lifecycle == ["release", "acquire", "release"]
    assert result["receipt"]["completed_tasks"] == 50
    assert result["summary"]["task_count"] == 50
    assert result["summary"]["no_changes_rate"] == 1.0
    assert "smoke/summary.json" in persisted
    assert "full/summary.json" in persisted


def test_infrastructure_retry_archives_failure_without_extra_sample(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path)
    object.__setattr__(cfg, "phase", "smoke")
    tasks = [
        {
            **task(task_id),
            "agent_problem_statement": f"prompt {task_id}",
            "agent_problem_statement_sha256": hashlib.sha256(
                f"prompt {task_id}".encode()
            ).hexdigest(),
        }
        for task_id in contract.SMOKE_TASK_IDS
    ]
    lock = {"sha256": "e" * 64, "tasks": {}}
    staged = {
        "tasks": tasks,
        "oracle_summary": {"all_passed": True, "passed_count": 50},
        "workspace_summary": {"all_passed": True, "passed": 50},
    }
    attempts: dict[str, int] = {}
    persisted: dict[str, Any] = {}

    def run(row: dict[str, Any], attempt: int) -> dict[str, Any]:
        attempts[row["instance_id"]] = attempt
        if attempt == 1:
            raise RuntimeError("transient sentinel")
        return {
            "trajectory": {"events": [], "tool_events": [], "exit_status": "exit"},
            "finalization": {"status": "no_changes", "patch": ""},
            "final_state_manifest": [],
            "workspace_receipt": {},
        }

    result = runtime.evaluate(
        config=cfg,
        lock=lock,
        staged=staged,
        run_trajectory=run,
        grade=lambda row, patch: {},
        release_gpu=lambda: None,
        persist=lambda files: persisted.update(files),
    )

    assert result["receipt"]["completed_tasks"] == 2
    assert attempts == {task_id: 2 for task_id in contract.SMOKE_TASK_IDS}
    records = [
        json.loads(line)
        for line in persisted["smoke/records.jsonl"].splitlines()
    ]
    assert all(row["infrastructure_retries"] == 1 for row in records)
    assert len(
        [key for key in persisted if key.startswith("smoke/incomplete-attempts/")]
    ) == 2



def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _complete_smoke_artifacts(
    tmp_path: Path,
) -> tuple[ModalAgenticMultiSweConfig, Path]:
    cfg = config(tmp_path)
    object.__setattr__(cfg, "phase", "smoke")
    root = cfg.local_run_path(tmp_path)
    root.mkdir(parents=True)
    task_ids = list(contract.SMOKE_TASK_IDS) + [
        f"safe-task-{index:02d}" for index in range(EXPECTED_CPP_TASKS - 2)
    ]
    oracle_records = [
        {"task_id": task_id, "setup_valid": True}
        for task_id in task_ids
    ]
    workspace_records = [
        {"task_id": task_id, "passed": True}
        for task_id in task_ids
    ]
    oracle_summary = {
        "all_passed": True,
        "passed_count": EXPECTED_CPP_TASKS,
        "record_count": EXPECTED_CPP_TASKS,
    }
    workspace_summary = {
        "all_passed": True,
        "passed": EXPECTED_CPP_TASKS,
        "task_count": EXPECTED_CPP_TASKS,
    }
    records = []
    trajectories = []
    patches = []
    for task_id in contract.SMOKE_TASK_IDS:
        row = task(task_id)
        trajectory = {
            "task_id": task_id,
            "events": [],
            "tool_events": [],
            "event_count": 0,
            "tool_event_count": 0,
            "exit_status": "submitted",
            "model_stats": {"api_calls": 1, "tokens_received": 2},
        }
        record = contract.classify_agentic_result(
            task=row,
            finalization={"status": "no_changes", "patch": ""},
            execution=None,
            trajectory=trajectory,
        )
        record["infrastructure_retries"] = 0
        records.append(record)
        trajectories.append(trajectory)
        patches.append(
            {
                "task_id": task_id,
                "patch_sha256": hashlib.sha256(b"").hexdigest(),
                "status": "no_changes",
            }
        )
        prompt = f"public prompt {task_id}"
        prompt_path = root / "smoke/prompts" / f"{task_id}.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt)
        trajectory_root = root / "smoke/trajectories" / task_id
        _write_json(
            trajectory_root / "identity.json",
            {
                "task_id": task_id,
                "identity_sha256": cfg.identity_sha256(),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            },
        )
        (trajectory_root / "events.jsonl").write_text("")
        _write_json(trajectory_root / "summary.json", trajectory)
        _write_json(trajectory_root / "workspace.receipt.json", {"task_id": task_id})
        _write_json(trajectory_root / "final-state.manifest.json", [])
        (trajectory_root / "final.patch").write_text("")
        _write_json(
            trajectory_root / "final-patch.receipt.json",
            {"task_id": task_id, "status": "no_changes"},
        )
    provenance = {"result_family": RESULT_FAMILY, "task_ids": sorted(contract.SMOKE_TASK_IDS)}
    summary = aggregate_agentic_records(
        records,
        oracle_summary=oracle_summary,
        workspace_summary=workspace_summary,
        provenance=provenance,
    )
    for relative, value in {
        "plan.json": {"action": "ephemeral paid run"},
        "config.redacted.json": cfg.redacted_mapping(),
        "source.receipt.json": {"source_commit": cfg.source_commit},
        "dataset.receipt.json": {"status": "complete"},
        "model-cache.receipt.json": {"status": "complete"},
        "image-lock.json": {"sha256": "a" * 64},
        "swe-agent.identity.json": {"commit": SWE_AGENT_COMMIT},
        "admission.response.json": {"status": "ready"},
        "server.runtime.json": {"status": "ready"},
        "server.receipt.json": {"status": "ready"},
        "data/oracle.summary.json": oracle_summary,
        "data/workspace.summary.json": workspace_summary,
        "smoke/summary.json": summary,
        "run_receipt.json": {
            "status": "smoke_complete",
            "result_family": RESULT_FAMILY,
            "modal_app_stopped": True,
            "teardown_status": "verified",
        },
    }.items():
        _write_json(root / relative, value)
    (root / "data/oracle.records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in oracle_records)
    )
    (root / "data/workspace.records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in workspace_records)
    )
    for task_id in task_ids:
        _write_json(
            root / "data/tasks" / task_id / "task.json",
            {"instance_id": task_id},
        )
    (root / "smoke/records.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in records)
    )
    (root / "smoke/trajectories.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in trajectories)
    )
    (root / "smoke/patches.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in patches)
    )
    _write_json(root / "artifact_manifest.json", build_artifact_manifest(root))
    return cfg, root


def test_local_artifacts_recompute_and_require_stopped_proof(
    tmp_path: Path,
) -> None:
    cfg, root = _complete_smoke_artifacts(tmp_path)
    validated = validate_local_artifacts(cfg, repo_root=tmp_path)
    assert validated["summary"]["task_count"] == 2

    receipt_path = root / "run_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["modal_app_stopped"] = False
    _write_json(receipt_path, receipt)
    _write_json(root / "artifact_manifest.json", build_artifact_manifest(root))
    with pytest.raises(ModalAgenticMultiSweError, match="stopped App"):
        validate_local_artifacts(cfg, repo_root=tmp_path)


def test_local_artifacts_reject_summary_and_unsafe_file_tampering(
    tmp_path: Path,
) -> None:
    cfg, root = _complete_smoke_artifacts(tmp_path)
    summary_path = root / "smoke/summary.json"
    summary = json.loads(summary_path.read_text())
    summary["pass_rate"] = 0.5
    _write_json(summary_path, summary)
    _write_json(root / "artifact_manifest.json", build_artifact_manifest(root))
    with pytest.raises(ModalAgenticMultiSweError, match="does not recompute"):
        validate_local_artifacts(cfg, repo_root=tmp_path)

    _write_json(
        summary_path,
        aggregate_agentic_records(
            [json.loads(line) for line in (root / "smoke/records.jsonl").read_text().splitlines()],
            oracle_summary=json.loads((root / "data/oracle.summary.json").read_text()),
            workspace_summary=json.loads((root / "data/workspace.summary.json").read_text()),
            provenance=summary["provenance"],
        ),
    )
    (root / "unsafe-link").symlink_to("/etc/passwd")
    with pytest.raises(ModalAgenticMultiSweError, match="unsafe local artifact type"):
        validate_local_artifacts(cfg, repo_root=tmp_path)


def test_hidden_fields_never_enter_agent_prompt_or_sanitizer_payload() -> None:
    sentinels = {
        "fix_patch": "W8_PRIVATE_FIX_PATCH",
        "test_patch": "W8_PRIVATE_TEST_PATCH",
        "target_commit": "W8_PRIVATE_TARGET_COMMIT",
        "oracle_execution": "W8_PRIVATE_ORACLE_EXECUTION",
        "image_inventory": "W8_PRIVATE_IMAGE_INVENTORY",
    }
    row = {
        **task(),
        "title": "Public title",
        "body": "Public body",
        **sentinels,
    }

    rendered = agent_problem_statement(
        row, harness=harness(), instance_id=str(row["instance_id"])
    )
    sanitizer = workspace_sanitizer_program(row)
    event = safe_trajectory_event(
        {
            "query": rendered,
            "output": "public model answer",
            "action": "pwd",
            "observation": "/workspace/repo",
        },
        0,
    )
    serialized = rendered + sanitizer + json.dumps(event, sort_keys=True)
    for sentinel in sentinels.values():
        assert sentinel not in serialized


@pytest.mark.parametrize("bad_record", ["missing", "stale"])
def test_workspace_import_fails_closed_on_missing_or_stale_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bad_record: str,
) -> None:
    lock_path = tmp_path / contract.DEFAULT_LOCK_PATH
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text("{}\n")
    cfg = config(
        tmp_path,
        W8_MODAL_AGENTIC_MULTI_SWE_PHASE="full",
        W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN="1",
        W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_LONG_GPU_LEASE="1",
        W8_MODAL_AGENTIC_MULTI_SWE_WORKSPACE_SOURCE_RUN_ID="source-agentic-run",
    )
    tasks = [
        {
            **task(f"task-{index:02d}"),
            "base_ref": f"{index:040x}",
        }
        for index in range(EXPECTED_CPP_TASKS)
    ]
    lock = {
        "sha256": "e" * 64,
        "tasks": {
            str(row["instance_id"]): {
                "digest": row["sandbox_image_digest"]
            }
            for row in tasks
        },
    }
    monkeypatch.setattr(
        runtime,
        "_oracle_key",
        lambda row, lock_row: "oracle-" + str(row["instance_id"]),
    )
    oracle_records = {
        str(row["instance_id"]): {
            "task_id": row["instance_id"],
            "oracle_cache_key": "oracle-" + str(row["instance_id"]),
            "setup_valid": True,
            "tests_collected": 1,
        }
        for row in tasks
    }
    workspace_records = {
        str(row["instance_id"]): {
            "task_id": row["instance_id"],
            "workspace_cache_key": workspace_cache_key(
                row,
                str(lock["tasks"][str(row["instance_id"])]["digest"]),
            ),
            "passed": True,
            "proof": {"sanitizer": {"submodule_identities": {}}},
        }
        for row in tasks
    }
    broken_id = str(tasks[-1]["instance_id"])
    if bad_record == "missing":
        del workspace_records[broken_id]
    else:
        workspace_records[broken_id]["workspace_cache_key"] = "stale"

    with pytest.raises(
        ModalAgenticMultiSweError,
        match="workspace import cache mismatch",
    ):
        runtime.prepare_proofs(
            config=cfg,
            lock=lock,
            tasks=tasks,
            dataset_receipt={"status": "complete"},
            grade=lambda *_args: pytest.fail(
                "exact imported oracles must be reused"
            ),
            workspace_probe=lambda _row: pytest.fail(
                "workspace imports must never fall back to execution"
            ),
            persist=lambda _files: None,
            oracle_records=oracle_records,
            workspace_records=workspace_records,
        )


def test_tool_cleanup_runs_when_stream_collection_raises() -> None:
    class BrokenReader:
        def read(self) -> str:
            raise RuntimeError("stream collection failed")

    class Reader:
        def read(self) -> str:
            return ""

    class BrokenProcess:
        stdout = BrokenReader()
        stderr = Reader()

        def wait(self) -> int:
            return 0

    class CleanupProcess:
        def wait(self) -> int:
            return 0

    class Sandbox:
        def __init__(self) -> None:
            self.commands: list[tuple[str, ...]] = []

        def exec(self, *args: str, **kwargs: Any) -> Any:
            self.commands.append(args)
            if args[0] == "runuser":
                return BrokenProcess()
            return CleanupProcess()

    sandbox = Sandbox()
    with pytest.raises(RuntimeError, match="stream collection failed"):
        ModalSandboxSWEEnv(sandbox).communicate("true")

    assert (
        "pkill",
        "-KILL",
        "-u",
        "w8agent",
    ) in sandbox.commands


@pytest.mark.parametrize(
    ("case", "expected_status"),
    [
        ("empty", "no_changes"),
        ("binary", "invalid_final_state"),
        ("hardlink", "invalid_final_state"),
        ("fifo", "invalid_final_state"),
        ("oversized", "invalid_final_state"),
    ],
)
def test_trusted_finalizer_classifies_unsafe_and_empty_states(
    tmp_path: Path,
    case: str,
    expected_status: str,
) -> None:
    def mutate(workspace: Path) -> None:
        if case == "binary":
            (workspace / "src/original.cpp").write_bytes(
                bytes((0, 1, 2, 3))
            )
        elif case == "hardlink":
            os.link(
                workspace / "src/original.cpp",
                workspace / "src/hardlink.cpp",
            )
        elif case == "fifo":
            os.mkfifo(workspace / "src/pipe")
        elif case == "oversized":
            (workspace / "src/large.cpp").write_text("x" * 64)

    def transform(program: str) -> str:
        if case != "oversized":
            return program
        updated = program.replace(
            '"max_final_bytes": 2147483648',
            '"max_final_bytes": 16',
        )
        assert updated != program
        return updated

    receipt, patch, _ = _execute_finalizer(
        tmp_path,
        mutate,
        program_transform=transform,
    )

    assert receipt["status"] == expected_status
    if expected_status != "valid_patch":
        assert patch == ""

    traversal = valid_patch().replace(
        "include/fmt/core.h", "../outside.cpp"
    )
    with pytest.raises(ModalAgenticMultiSweError):
        validate_final_patch(task(), traversal)


def test_agent_commit_cannot_replace_trusted_baseline(tmp_path: Path) -> None:
    def mutate(workspace: Path) -> None:
        (workspace / "src/original.cpp").write_text("int value = 9;\n")
        subprocess.run(["git", "-C", str(workspace), "init", "-q"], check=True)
        subprocess.run(
            ["git", "-C", str(workspace), "config", "user.email", "agent@invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(workspace), "config", "user.name", "agent"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(workspace), "add", "-A"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(workspace), "commit", "-qm", "agent baseline"],
            check=True,
        )

    receipt, patch, manifest = _execute_finalizer(tmp_path, mutate)

    assert receipt["status"] == "valid_patch"
    assert "-int value = 1;" in patch
    assert "+int value = 9;" in patch
    assert all(not row["path"].startswith(".git") for row in manifest)


def test_agent_limit_exit_still_grades_a_valid_final_state() -> None:
    record = classify_agentic_result(
        task=task(),
        finalization={
            "status": "valid_patch",
            "patch": valid_patch(),
            "changed_file_count": 1,
            "changed_line_count": 2,
        },
        execution={
            "returncode": 0,
            "timed_out": False,
            "logs": "100% tests passed, 0 tests failed out of 12\n",
            "image": task()["sandbox_image_digest"],
            "sandbox_id": "sandbox-agent-limit",
        },
        trajectory={
            "exit_status": "call_limit",
            "event_count": AGENT_CALL_LIMIT,
            "tool_event_count": 3,
        },
    )

    assert record["all_tests_pass"] is True
    assert record["reason"] == "passed"
    assert record["trajectory"]["exit_status"] == "call_limit"


def test_resume_reuses_complete_unit_and_restarts_partial_unit(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path)
    object.__setattr__(cfg, "phase", "smoke")
    tasks = [
        {
            **task(task_id),
            "agent_problem_statement": f"prompt {task_id}",
            "agent_problem_statement_sha256": hashlib.sha256(
                f"prompt {task_id}".encode()
            ).hexdigest(),
        }
        for task_id in contract.SMOKE_TASK_IDS
    ]
    staged = {
        "tasks": tasks,
        "oracle_summary": {"all_passed": True, "passed_count": 50},
        "workspace_summary": {"all_passed": True, "passed": 50},
    }
    calls: list[str] = []

    def value(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "trajectory": {
                "events": [],
                "tool_events": [],
                "event_count": 0,
                "tool_event_count": 0,
                "exit_status": "submitted",
                "model_stats": {"api_calls": 1, "tokens_received": 2},
            },
            "finalization": {
                "status": "no_changes",
                "patch": "",
                "changed_file_count": 0,
                "changed_line_count": 0,
            },
            "final_state_manifest": [],
            "workspace_receipt": {"task_id": row["instance_id"]},
        }

    complete_task = tasks[0]
    complete_prompt = str(complete_task["agent_problem_statement"])
    complete = {
        "schema_version": 1,
        "task_id": complete_task["instance_id"],
        "identity_sha256": cfg.identity_sha256(),
        "prompt_sha256": hashlib.sha256(complete_prompt.encode()).hexdigest(),
        "complete": True,
        "attempt": 1,
        **value(complete_task),
    }
    partial_task = tasks[1]
    partial = {
        "task_id": partial_task["instance_id"],
        "identity_sha256": cfg.identity_sha256(),
        "complete": False,
    }

    result = runtime.evaluate(
        config=cfg,
        lock={"sha256": "e" * 64, "tasks": {}},
        staged=staged,
        run_trajectory=lambda row, attempt: (
            calls.append(str(row["instance_id"])) or value(row)
        ),
        grade=lambda *_args: pytest.fail("no-change state must not grade"),
        release_gpu=lambda: None,
        persist=lambda _files: None,
        resume_state={
            "smoke": {
                str(complete_task["instance_id"]): complete,
                str(partial_task["instance_id"]): partial,
            }
        },
    )

    assert calls == [partial_task["instance_id"]]
    assert result["receipt"]["completed_tasks"] == 2


def test_local_artifacts_reject_hardlinks_and_manifest_mismatch(
    tmp_path: Path,
) -> None:
    cfg, root = _complete_smoke_artifacts(tmp_path)
    os.link(root / "plan.json", root / "plan-hardlink.json")
    with pytest.raises(ModalAgenticMultiSweError, match="hard-linked"):
        validate_local_artifacts(cfg, repo_root=tmp_path)

    (root / "plan-hardlink.json").unlink()
    plan = json.loads((root / "plan.json").read_text())
    plan["tampered"] = True
    _write_json(root / "plan.json", plan)
    with pytest.raises(
        ModalAgenticMultiSweError,
        match="artifact manifest",
    ):
        validate_local_artifacts(cfg, repo_root=tmp_path)
