"""Ephemeral Modal app for agentic GLM-4.7-Flash Multi-SWE C++."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from typing import Any
from urllib.request import Request, urlopen

import modal
from modal.volume import FileEntryType


IS_LOCAL = modal.is_local()
ROOT = Path(__file__).resolve().parents[3] if IS_LOCAL else Path("/opt/w8-src")
if IS_LOCAL:
    sys.path.insert(0, str(ROOT / "src"))

from w8_biayn.integrations.modal_swe_agent_driver import (  # noqa: E402
    run_pinned_swe_agent,
    workspace_finalizer_program,
    workspace_sanitizer_program,
)
from w8_biayn.integrations.slime_multi_swe_cpp import (  # noqa: E402
    ORACLE_PROTOCOL_VERSION,
    REPO_HARNESSES,
    SCHEMA_VERSION as MULTI_SWE_SCHEMA_VERSION,
    SIMDJSON_OFFLINE_INSTANCE_IDS,
    build_public_issue_context,
    load_multi_swe_rows,
    normalized_task,
    prepare_repo_harness_revisions,
    prepare_simdjson_offline_dependencies,
    repo_harness_for_row,
)
from w8_biayn.modal_agentic_multi_swe_cpp import (  # noqa: E402
    AGENT_SANDBOX_CPU,
    AGENT_SANDBOX_LIFETIME_SECONDS,
    AGENT_SANDBOX_MEMORY_MIB,
    RESULT_FAMILY,
    SERVER_EXECUTION_TIMEOUT_SECONDS,
    SWE_AGENT_COMMIT,
    SWE_AGENT_CONFIG_BLOB,
    SWE_AGENT_CONFIG_SHA256,
    SWE_AGENT_DEPENDENCY_LOCK_SHA256,
    SWE_AGENT_EDIT_TREE,
    SWE_AGENT_REVIEW_TREE,
    SWE_AGENT_TOOLS_TREE,
    WORKSPACE_CANARY_REVISION,
    ModalAgenticMultiSweConfig,
    agent_problem_statement,
    ModalAgenticMultiSweError,
    prepare_local_plan,
    resume_identity_mismatches,
    validate_final_patch,
)
from w8_biayn.modal_glm47 import (  # noqa: E402
    MODEL_REPO,
    SERVED_MODEL_NAME,
    SGLANG_POST_GENERATION_WINDOW_SECONDS,
    SGLANG_SCALEDOWN_WINDOW_SECONDS,
    TRANSFORMERS_COMMIT,
    TRANSFORMERS_REPO_URL,
    sha256_file,
    sglang_server_command,
    validate_model_snapshot,
    validate_sglang_help,
)
from w8_biayn.modal_multi_swe_cpp import (  # noqa: E402
    DATASET_REPO,
    SIMDJSON_MODAL_MOUNT_PATH,
    SIMDJSON_MODAL_MOUNT_RELATIVE,
    build_artifact_manifest,
    modal_sandbox_instance_script,
    summarize_modal_execution_output,
    validate_image_lock,
    write_json,
)


def _config(payload: dict[str, Any]) -> ModalAgenticMultiSweConfig:
    names = {item.name for item in fields(ModalAgenticMultiSweConfig)}
    values = {key: value for key, value in payload.items() if key in names}
    values["smoke_task_ids"] = tuple(values["smoke_task_ids"])
    values["modal_token_id"] = "<not-attached>"
    values["modal_token_secret"] = "<not-attached>"
    values["hf_token"] = (
        "<downloader-only>" if payload.get("hf_token_present") else ""
    )
    return ModalAgenticMultiSweConfig(**values)


if IS_LOCAL:
    CONFIG = ModalAgenticMultiSweConfig.from_env(repo_root=ROOT)
    RUNTIME = CONFIG.runtime_mapping()
    LOCK = validate_image_lock(ROOT / CONFIG.image_lock_path)
else:
    RUNTIME = json.loads(
        os.environ["W8_MODAL_AGENTIC_MULTI_SWE_RUNTIME_CONFIG"]
    )
    CONFIG = _config(RUNTIME)
    LOCK = json.loads(
        os.environ["W8_MODAL_AGENTIC_MULTI_SWE_IMAGE_LOCK"]
    )
RUNTIME_JSON = json.dumps(RUNTIME, sort_keys=True)
LOCK_JSON = json.dumps(LOCK, sort_keys=True)
SGLANG_API_KEY = secrets.token_urlsafe(48) if IS_LOCAL else ""

app = modal.App(CONFIG.app_name)
model_volume = modal.Volume.from_name(
    CONFIG.model_volume, create_if_missing=True
)
data_volume = modal.Volume.from_name(
    CONFIG.data_volume, create_if_missing=True
)
results_volume = modal.Volume.from_name(
    CONFIG.results_volume, create_if_missing=True
)
server_secret = modal.Secret.from_dict(
    {"SGLANG_API_KEY": SGLANG_API_KEY} if IS_LOCAL else {}
)
downloader_secrets = (
    [modal.Secret.from_dict({"HF_TOKEN": CONFIG.hf_token})]
    if IS_LOCAL and CONFIG.hf_token
    else []
)

if IS_LOCAL:
    source_root = str(ROOT / "src" / "w8_biayn")
    common_env = {
        "PYTHONPATH": "/opt/w8-src",
        "W8_MODAL_AGENTIC_MULTI_SWE_RUNTIME_CONFIG": RUNTIME_JSON,
        "W8_MODAL_AGENTIC_MULTI_SWE_IMAGE_LOCK": LOCK_JSON,
    }
    control_image = (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install("huggingface-hub[hf-transfer]>=0.24", "pydantic>=2.7")
        .env(common_env)
        .add_local_dir(source_root, "/opt/w8-src/w8_biayn")
    )
    agent_runner_image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("git")
        .pip_install_from_requirements(
            str(ROOT / "examples/modal/glm47_flash_agentic_multi_swe_cpp/swe-agent.requirements.lock")
        )
        .run_commands(
            "git clone " + "https://github.com/SWE-agent/SWE-agent.git /opt/swe-agent",
            "git -C /opt/swe-agent checkout --detach " + SWE_AGENT_COMMIT,
            (
                'test "$(git -C /opt/swe-agent rev-parse HEAD)" = '
                + SWE_AGENT_COMMIT
            ),
            (
                'test "$(git -C /opt/swe-agent rev-parse '
                'HEAD:config/default_backticks.yaml)" = '
                + SWE_AGENT_CONFIG_BLOB
            ),
            (
                'test "$(git -C /opt/swe-agent rev-parse HEAD:tools/registry)" = '
                + SWE_AGENT_TOOLS_TREE
            ),
            (
                'test "$(git -C /opt/swe-agent rev-parse '
                'HEAD:tools/edit_anthropic)" = '
                + SWE_AGENT_EDIT_TREE
            ),
            (
                'test "$(git -C /opt/swe-agent rev-parse '
                'HEAD:tools/review_on_submit_m)" = '
                + SWE_AGENT_REVIEW_TREE
            ),
            "pip install --no-deps -e /opt/swe-agent",
        )
        .env(common_env)
        .add_local_dir(source_root, "/opt/w8-src/w8_biayn")
    )
    server_image = (
        modal.Image.from_registry(CONFIG.sglang_image)
        .pip_install("pydantic>=2.7")
        .pip_install(
            "git+" + TRANSFORMERS_REPO_URL + "@" + TRANSFORMERS_COMMIT
        )
        .run_commands(
            'python -c "from transformers.models.auto.configuration_auto '
            "import CONFIG_MAPPING; assert 'glm4_moe_lite' in CONFIG_MAPPING\""
        )
        .env(common_env)
        .add_local_dir(source_root, "/opt/w8-src/w8_biayn")
    )
else:
    control_image = modal.Image.debian_slim()
    agent_runner_image = modal.Image.debian_slim()
    server_image = modal.Image.debian_slim()


@app.function(
    image=control_image,
    volumes={"/data": data_volume},
    secrets=downloader_secrets,
    timeout=CONFIG.max_run_seconds,
    retries=0,
)
def prepare_dataset(
    payload: dict[str, Any], lock: dict[str, Any]
) -> dict[str, Any]:
    """Stage the exact 50-task dataset and offline grader dependencies."""

    from huggingface_hub import hf_hub_download

    config = _config(payload)
    revision_root = Path("/data/revisions") / config.dataset_revision
    source = revision_root / "multi_swe_bench_mini.jsonl"
    revision_root.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        downloaded = hf_hub_download(
            repo_id=DATASET_REPO,
            repo_type="dataset",
            filename="multi_swe_bench_mini.jsonl",
            revision=config.dataset_revision,
            token=os.environ.get("HF_TOKEN") or None,
        )
        source.write_bytes(Path(downloaded).read_bytes())
    all_rows = load_multi_swe_rows(source)
    rows = sorted(
        (row for row in all_rows if repo_harness_for_row(row)),
        key=lambda row: str(row["instance_id"]),
    )
    if len(rows) != 50 or set(lock["tasks"]) != {
        str(row["instance_id"]) for row in rows
    }:
        raise ModalAgenticMultiSweError(
            "dataset does not produce locked 50-task set"
        )
    prepared = revision_root / "prepared"
    pairs = []
    prompts = {}
    for row in rows:
        harness = repo_harness_for_row(row)
        assert harness is not None
        task_id = str(row["instance_id"])
        task = normalized_task(
            row, harness=harness, instance_id=task_id
        )
        lock_row = lock["tasks"][task_id]
        if task["sandbox_image"] != lock_row["tag"]:
            raise ModalAgenticMultiSweError(
                "dataset/image-lock mismatch for " + task_id
            )
        task["sandbox_image_digest"] = lock_row["digest"]
        issue_context = build_public_issue_context(
            row, harness=harness, instance_id=task_id
        )
        task["agent_problem_statement"] = agent_problem_statement(
            row, harness=harness, instance_id=task_id
        )
        task["issue_context_sha256"] = hashlib.sha256(
            issue_context.encode()
        ).hexdigest()
        task["agent_problem_statement_sha256"] = hashlib.sha256(
            task["agent_problem_statement"].encode()
        ).hexdigest()
        path = prepared / "tasks" / task_id / "task.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, task)
        pairs.append((path, task))
        prompts[task_id] = {
            "prompt_sha256": hashlib.sha256(
                task["agent_problem_statement"].encode()
            ).hexdigest()
        }
    prepare_simdjson_offline_dependencies(prepared, pairs)
    prepare_repo_harness_revisions(pairs)
    tasks = [
        json.loads(path.read_text(encoding="utf-8"))
        for path, _ in pairs
    ]
    receipt = {
        "status": "complete",
        "dataset_repo": DATASET_REPO,
        "dataset_revision": config.dataset_revision,
        "raw_bytes": source.stat().st_size,
        "raw_sha256": sha256_file(source),
        "source_rows": len(all_rows),
        "cpp_rows": len(tasks),
        "task_ids": [task["instance_id"] for task in tasks],
        "multi_swe_schema_version": MULTI_SWE_SCHEMA_VERSION,
        "oracle_protocol_version": ORACLE_PROTOCOL_VERSION,
        "prompts": prompts,
        "image_lock_sha256": lock["sha256"],
    }
    write_json(prepared / "dataset.receipt.json", receipt)
    data_volume.commit()
    return {"tasks": tasks, "receipt": receipt}


@app.function(
    image=control_image,
    volumes={"/models": model_volume},
    secrets=downloader_secrets,
    timeout=CONFIG.max_run_seconds,
    retries=0,
)
def preload_model(payload: dict[str, Any]) -> dict[str, Any]:
    from huggingface_hub import snapshot_download

    config = _config(payload)
    target = (
        Path("/models/zai-org--GLM-4.7-Flash")
        / config.model_revision
    )
    manifest_path = target.parent / (
        config.model_revision + ".manifest.json"
    )
    cache_hit = False
    if target.is_dir() and manifest_path.is_file():
        try:
            manifest = validate_model_snapshot(
                target, expected_revision=config.model_revision
            )
            cache_hit = True
        except Exception:
            cache_hit = False
    if not cache_hit:
        if target.exists():
            target.rename(
                target.with_name(
                    target.name + ".incomplete-" + str(int(time.time()))
                )
            )
        snapshot_download(
            repo_id=MODEL_REPO,
            revision=config.model_revision,
            local_dir=target,
            token=os.environ.get("HF_TOKEN") or None,
        )
        manifest = validate_model_snapshot(
            target, expected_revision=config.model_revision
        )
        write_json(manifest_path, manifest)
        model_volume.commit()
    return {
        "status": "complete",
        "cache_hit": cache_hit,
        "model_repo": MODEL_REPO,
        "model_revision": config.model_revision,
        "manifest_sha256": manifest["manifest_sha256"],
    }


@app.function(
    image=control_image,
    volumes={"/results": results_volume},
    timeout=300,
    retries=0,
)
def persist_files(
    payload: dict[str, Any], files: dict[str, Any]
) -> None:
    config = _config(payload)
    root = Path("/results") / config.remote_run_path.lstrip("/")
    for relative, value in files.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ModalAgenticMultiSweError(
                "unsafe persisted artifact path"
            )
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            target.write_text(value, encoding="utf-8")
        else:
            write_json(target, value)
    results_volume.commit()

def _run_process(process: Any) -> tuple[int, str, str]:
    with ThreadPoolExecutor(max_workers=2) as pool:
        stdout = pool.submit(process.stdout.read)
        stderr = pool.submit(process.stderr.read)
        return process.wait(), str(stdout.result()), str(stderr.result())


@app.function(
    image=server_image,
    gpu=CONFIG.gpu,
    volumes={
        "/models": model_volume.with_mount_options(read_only=True),
        "/results": results_volume,
    },
    secrets=[server_secret],
    timeout=SERVER_EXECUTION_TIMEOUT_SECONDS,
    startup_timeout=CONFIG.startup_timeout_seconds,
    min_containers=0,
    max_containers=1,
    buffer_containers=0,
    scaledown_window=SGLANG_SCALEDOWN_WINDOW_SECONDS,
)
@modal.web_server(
    port=8000,
    startup_timeout=CONFIG.startup_timeout_seconds,
    requires_proxy_auth=False,
)
def SGLangServer() -> None:
    """Start one authenticated four-H100 SGLang replica."""

    config = _config(
        json.loads(
            os.environ[
                "W8_MODAL_AGENTIC_MULTI_SWE_RUNTIME_CONFIG"
            ]
        )
    )
    help_result = subprocess.run(
        ["python", "-m", "sglang.launch_server", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    validate_sglang_help(help_result.stdout + help_result.stderr)
    gpus = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=uuid",
            "--format=csv,noheader",
        ],
        text=True,
    ).splitlines()
    if len([line for line in gpus if line.strip()]) != 4:
        raise ModalAgenticMultiSweError(
            "SGLang requires exactly four visible GPUs"
        )
    command = sglang_server_command(
        config, api_key=os.environ["SGLANG_API_KEY"]
    )
    log = Path("/tmp/sglang.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        command, stdout=log, stderr=subprocess.STDOUT
    )
    deadline = time.monotonic() + config.startup_timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log.flush()
            raw = Path("/tmp/sglang.log").read_bytes()
            key = os.environ["SGLANG_API_KEY"].encode()
            tail = raw[-65_536:].replace(key, b"<redacted>")
            failure = {
                "status": "failed",
                "error_type": "SGLangEarlyExit",
                "returncode": process.returncode,
                "tail": tail.decode(errors="replace"),
                "tail_sha256": hashlib.sha256(tail).hexdigest(),
            }
            target = (
                Path("/results")
                / config.remote_run_path.lstrip("/")
                / "server.failure.json"
            )
            write_json(target, failure)
            results_volume.commit()
            raise ModalAgenticMultiSweError(
                "SGLang exited during startup"
            )
        try:
            with urlopen(
                Request(
                    "http://127.0.0.1:8000/health",
                    headers={
                        "Authorization": (
                            "Bearer "
                            + os.environ["SGLANG_API_KEY"]
                        )
                    },
                ),
                timeout=10,
            ):
                break
        except Exception:
            time.sleep(5)
    else:
        raise ModalAgenticMultiSweError(
            "SGLang startup timed out"
        )
    write_json(
        (
            Path("/results")
            / config.remote_run_path.lstrip("/")
            / "server.runtime.json"
        ),
        {
            "status": "ready",
            "server_execution_timeout_seconds": (
                SERVER_EXECUTION_TIMEOUT_SECONDS
            ),
            "served_model": SERVED_MODEL_NAME,
            "sglang_image": config.sglang_image,
            "transformers_commit": TRANSFORMERS_COMMIT,
            "launch_argv": [
                "<redacted>"
                if item == os.environ["SGLANG_API_KEY"]
                else item
                for item in command
            ],
        },
    )
    results_volume.commit()


def _sandbox_volumes(task: dict[str, Any]) -> dict[str, Any]:
    if task["instance_id"] not in SIMDJSON_OFFLINE_INSTANCE_IDS:
        return {}
    prefix = (
        "revisions/"
        + CONFIG.dataset_revision
        + "/prepared/"
        + SIMDJSON_MODAL_MOUNT_RELATIVE
    )
    return {
        SIMDJSON_MODAL_MOUNT_PATH: data_volume.with_mount_options(
            read_only=True, sub_path=prefix
        )
    }


def grade_patch(task: dict[str, Any], patch: str) -> dict[str, Any]:
    harness = REPO_HARNESSES[
        (task["org"].lower(), task["repo"].lower())
    ]
    script = modal_sandbox_instance_script(
        task, harness, timeout_s=1200
    )
    sandbox = None
    started = time.monotonic()
    try:
        sandbox = modal.Sandbox.create(
            "bash",
            "-lc",
            "sleep 86400",
            app=app,
            image=modal.Image.from_registry(
                task["sandbox_image_digest"]
            ),
            timeout=1320,
            cpu=(2.0, 2.0),
            memory=(2048, 2048),
            block_network=True,
            volumes=_sandbox_volumes(task),
            secrets=[],
        )
        sandbox.filesystem.write_text(patch, "/home/fix.patch")
        process = sandbox.exec(
            "bash", "-lc", script, timeout=1200, text=True
        )
        returncode, stdout, stderr = _run_process(process)
        captured = summarize_modal_execution_output(
            stdout, stderr, returncode=returncode
        )
        return {
            "returncode": returncode,
            "timed_out": returncode == 124,
            **captured,
            "elapsed_seconds": round(
                time.monotonic() - started, 3
            ),
            "sandbox_id": sandbox.object_id,
            "image": task["sandbox_image_digest"],
            "block_network": True,
        }
    finally:
        if sandbox is not None:
            try:
                sandbox.terminate(wait=True)
            finally:
                sandbox.detach()


def grade_with_retry(
    task: dict[str, Any], patch: str
) -> dict[str, Any]:
    failures = []
    for attempt in (1, 2):
        try:
            result = grade_patch(task, patch)
            result["infrastructure_retries"] = attempt - 1
            return result
        except Exception as exc:
            failures.append(type(exc).__name__)
    raise ModalAgenticMultiSweError(
        "grader infrastructure failed twice: " + ",".join(failures)
    )


@app.function(
    image=agent_runner_image,
    timeout=AGENT_SANDBOX_LIFETIME_SECONDS,
    retries=0,
)
def workspace_probe(task: dict[str, Any]) -> dict[str, Any]:
    """Prove one exact image can be sanitized before any GPU starts."""

    sandbox = None
    try:
        sandbox = modal.Sandbox.create(
            "bash",
            "-lc",
            "sleep 86400",
            app=app,
            image=modal.Image.from_registry(
                task["sandbox_image_digest"]
            ),
            timeout=AGENT_SANDBOX_LIFETIME_SECONDS,
            cpu=(AGENT_SANDBOX_CPU, AGENT_SANDBOX_CPU),
            memory=(
                AGENT_SANDBOX_MEMORY_MIB,
                AGENT_SANDBOX_MEMORY_MIB,
            ),
            block_network=True,
            volumes={},
            secrets=[],
        )
        sanitizer = sandbox.exec(
            "python3",
            "-c",
            workspace_sanitizer_program(task),
            timeout=300,
            text=True,
        )
        returncode, stdout, stderr = _run_process(sanitizer)
        if returncode:
            raise ModalAgenticMultiSweError(
                "workspace sanitizer failed: "
                + (stdout + stderr)[-2000:]
            )
        canary = sandbox.exec(
            "runuser",
            "-u",
            "w8agent",
            "--",
            "env",
            "-i",
            "HOME=/workspace/home",
            "TMPDIR=/workspace/tmp",
            "PATH=/usr/local/bin:/usr/bin:/bin",
            "bash",
            "--noprofile",
            "--norc",
            "-lc",
            (
                "set -e; "
                "test ! -r /root; test ! -r /home; "
                "test ! -r /opt/w8-trusted; test ! -r /opt/w8-output; "
                "test ! -e /home/test.patch; test ! -e /home/fix.patch; "
                "test ! -e /home/fix-run.sh; test ! -e /results; "
                "test ! -e /models; test -w /workspace/repo; "
                "test $(git -C /workspace/repo rev-list --count HEAD) -eq 1; "
                "test -z \"$(git -C /workspace/repo status --porcelain)\"; "
                "printf '#include <iostream>\nint main(){std::cout << 17;}' "
                "> /workspace/tmp/w8-canary.cpp; "
                "c++ /workspace/tmp/w8-canary.cpp "
                "-o /workspace/tmp/w8-canary; "
                "test $(/workspace/tmp/w8-canary) = 17; "
                "printf writable > /workspace/repo/.w8-workspace-canary; "
                "rm -f /workspace/repo/.w8-workspace-canary "
                "/workspace/tmp/w8-canary.cpp /workspace/tmp/w8-canary"
            ),
            timeout=120,
            text=True,
        )
        canary_code, _, _ = _run_process(canary)
        finalizer = sandbox.exec(
            "python3",
            "-c",
            workspace_finalizer_program(task),
            timeout=300,
            text=True,
        )
        finalizer_code, finalizer_stdout, finalizer_stderr = _run_process(
            finalizer
        )
        if finalizer_code:
            raise ModalAgenticMultiSweError(
                "workspace proof finalizer failed: "
                + (finalizer_stdout + finalizer_stderr)[-2000:]
            )
        receipt = json.loads(
            sandbox.filesystem.read_text(
                "/opt/w8-output/sanitizer.receipt.json"
            )
        )
        finalizer_receipt = json.loads(
            sandbox.filesystem.read_text(
                "/opt/w8-output/finalizer.receipt.json"
            )
        )
        finalizer_clean = finalizer_receipt.get("status") == "no_changes"
        return {
            "passed": (
                returncode == 0
                and canary_code == 0
                and finalizer_code == 0
                and finalizer_clean
            ),
            "sanitizer": receipt,
            "finalizer": finalizer_receipt,
            "canary_unreadable": canary_code == 0,
            "canary_revision": WORKSPACE_CANARY_REVISION,
            "scripted_read_write_compile_output_canary": canary_code == 0,
            "sandbox_id": sandbox.object_id,
            "image": task["sandbox_image_digest"],
            "block_network": True,
            "secrets": [],
            "volumes": [],
        }
    finally:
        if sandbox is not None:
            try:
                sandbox.terminate(wait=True)
            finally:
                sandbox.detach()


@app.function(
    image=agent_runner_image,
    timeout=AGENT_SANDBOX_LIFETIME_SECONDS,
    retries=0,
)
def run_agent_trajectory(
    task: dict[str, Any],
    attempt: int,
    server_url: str,
    api_key: str,
) -> dict[str, Any]:
    """Run one controller-side SWE-agent against one secret-free Sandbox."""

    sandbox = None
    try:
        sandbox = modal.Sandbox.create(
            "bash",
            "-lc",
            "sleep 86400",
            app=app,
            image=modal.Image.from_registry(
                task["sandbox_image_digest"]
            ),
            timeout=AGENT_SANDBOX_LIFETIME_SECONDS,
            cpu=(AGENT_SANDBOX_CPU, AGENT_SANDBOX_CPU),
            memory=(
                AGENT_SANDBOX_MEMORY_MIB,
                AGENT_SANDBOX_MEMORY_MIB,
            ),
            block_network=True,
            volumes={},
            secrets=[],
        )
        sanitizer = sandbox.exec(
            "python3",
            "-c",
            workspace_sanitizer_program(task),
            timeout=300,
            text=True,
        )
        returncode, stdout, stderr = _run_process(sanitizer)
        if returncode:
            raise ModalAgenticMultiSweError(
                "workspace sanitizer failed: "
                + (stdout + stderr)[-2000:]
            )
        workspace_receipt = json.loads(
            sandbox.filesystem.read_text(
                "/opt/w8-output/sanitizer.receipt.json"
            )
        )
        stage = str(task.get("_agentic_stage") or "")
        if stage not in {"smoke", "full"}:
            raise ModalAgenticMultiSweError(
                "trajectory callback is missing its fixed stage"
            )

        def persist_incremental(event: dict[str, Any]) -> None:
            step = int(event["step"])
            persist_files.remote(
                RUNTIME,
                {
                    (
                        f"{stage}/trajectory-attempts/"
                        f"{task['instance_id']}/attempt-{attempt}/"
                        f"steps/{step:04d}.json"
                    ): event
                },
            )

        trajectory = run_pinned_swe_agent(
            sandbox=sandbox,
            problem_statement=task["agent_problem_statement"],
            server_url=server_url,
            api_key=api_key,
            output_dir=(
                Path("/tmp/agent-output")
                / task["instance_id"]
                / str(attempt)
            ),
            event_sink=persist_incremental,
        )
        finalizer = sandbox.exec(
            "python3",
            "-c",
            workspace_finalizer_program(task),
            timeout=300,
            text=True,
        )
        final_code, final_stdout, final_stderr = _run_process(
            finalizer
        )
        if final_code:
            raise ModalAgenticMultiSweError(
                "trusted finalizer failed: "
                + (final_stdout + final_stderr)[-2000:]
            )
        finalization = json.loads(
            sandbox.filesystem.read_text(
                "/opt/w8-output/finalizer.receipt.json"
            )
        )
        finalization["patch"] = sandbox.filesystem.read_text(
            "/opt/w8-output/final.patch"
        )
        final_state_manifest = json.loads(
            sandbox.filesystem.read_text(
                "/opt/w8-output/final-state.manifest.json"
            )
        )
        if finalization.get("status") == "valid_patch":
            try:
                validated_paths = validate_final_patch(
                    task, str(finalization["patch"])
                )
            except ModalAgenticMultiSweError as exc:
                finalization["status"] = "invalid_files"
                finalization["error"] = "forbidden final patch path"
                finalization["error_sha256"] = hashlib.sha256(
                    str(exc).encode()
                ).hexdigest()
            else:
                if sorted(validated_paths) != sorted(
                    finalization.get("changed_paths") or []
                ):
                    raise ModalAgenticMultiSweError(
                        "trusted changed-path receipt mismatch"
                    )
                finalization["path_policy_validated"] = True
        return {
            "trajectory": trajectory,
            "finalization": finalization,
            "final_state_manifest": final_state_manifest,
            "workspace_receipt": workspace_receipt,
            "sandbox": {
                "sandbox_id": sandbox.object_id,
                "image": task["sandbox_image_digest"],
                "block_network": True,
                "secrets": [],
                "volumes": [],
            },
        }
    finally:
        if sandbox is not None:
            try:
                sandbox.terminate(wait=True)
            finally:
                sandbox.detach()

@app.function(
    image=control_image,
    volumes={"/results": results_volume},
    timeout=300,
    retries=0,
)
def load_remote_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Admit resume/import state on CPU before any GPU allocation."""

    config = _config(payload)
    results_volume.reload()
    root = Path("/results") / config.remote_run_path.lstrip("/")
    present = root.is_dir() and any(root.iterdir())
    if present and not config.resume:
        raise ModalAgenticMultiSweError(
            "remote run id already has artifacts"
        )
    state: dict[str, Any] = {
        "oracle_records": {},
        "workspace_records": {},
        "smoke": {},
        "full": {},
    }
    def validate_source(
        run_id: str,
        *,
        summary_relative: str,
        require_agentic: bool,
    ) -> Path:
        source_root = Path("/results/runs") / run_id
        receipt_path = source_root / "run_receipt.json"
        manifest_path = source_root / "artifact_manifest.json"
        summary_path = source_root / summary_relative
        source_config_path = source_root / "config.redacted.json"
        if not all(
            path.is_file()
            for path in (
                receipt_path,
                manifest_path,
                summary_path,
                source_config_path,
            )
        ):
            raise ModalAgenticMultiSweError(
                "source proof is missing receipt, manifest, or summary"
            )
        source_config = json.loads(
            source_config_path.read_text(encoding="utf-8")
        )
        if (
            source_config.get("run_id") != run_id
            or source_config.get("dataset_revision")
            != config.dataset_revision
            or source_config.get("results_volume") != config.results_volume
        ):
            raise ModalAgenticMultiSweError(
                "source proof configuration identity mismatch"
            )
        receipt = json.loads(
            receipt_path.read_text(encoding="utf-8")
        )
        if (
            receipt.get("modal_app_stopped") is not True
            or receipt.get("teardown_status") != "verified"
            or receipt.get("status") not in {"complete", "smoke_complete"}
        ):
            raise ModalAgenticMultiSweError(
                "source proof has no completed stopped-App receipt"
            )
        if require_agentic and receipt.get("result_family") != RESULT_FAMILY:
            raise ModalAgenticMultiSweError(
                "workspace source is not an agentic result"
            )
        stored_manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        if stored_manifest != build_artifact_manifest(source_root):
            raise ModalAgenticMultiSweError(
                "source proof artifact manifest does not reconcile"
            )
        summary = json.loads(
            summary_path.read_text(encoding="utf-8")
        )
        if summary.get("all_passed") is not True:
            raise ModalAgenticMultiSweError(
                "source proof summary did not pass"
            )
        return source_root

    if present:
        prior_config = root / "config.redacted.json"
        if not prior_config.is_file():
            raise ModalAgenticMultiSweError(
                "resume has no prior redacted config"
            )
        prior_mapping = json.loads(
            prior_config.read_text(encoding="utf-8")
        )
        mismatches = resume_identity_mismatches(config, prior_mapping)
        if mismatches:
            raise ModalAgenticMultiSweError(
                f"remote resume identity mismatch: {mismatches}"
            )
        receipt_path = root / "run_receipt.json"
        if receipt_path.is_file() and json.loads(
            receipt_path.read_text(encoding="utf-8")
        ).get("status") in {"complete", "smoke_complete"}:
            raise ModalAgenticMultiSweError(
                "completed runs are immutable"
            )
    current_root = Path("/results/runs") / config.run_id
    oracle_source_root = (
        validate_source(
            config.oracle_source_run_id,
            summary_relative="data/oracle.summary.json",
            require_agentic=False,
        )
        if config.oracle_source_run_id
        else current_root
    )
    workspace_source_root = (
        validate_source(
            config.workspace_source_run_id,
            summary_relative="data/workspace.summary.json",
            require_agentic=True,
        )
        if config.workspace_source_run_id
        else current_root
    )
    oracle_root = oracle_source_root / "data/oracle.records"
    workspace_root = workspace_source_root / "data/workspace.records"
    for path, key in (
        (oracle_root, "oracle_records"),
        (workspace_root, "workspace_records"),
    ):
        if path.is_dir():
            for record_path in path.glob("*.json"):
                record = json.loads(
                    record_path.read_text(encoding="utf-8")
                )
                state[key][str(record["task_id"])] = record
    if config.oracle_source_run_id and len(
        state["oracle_records"]
    ) != 50:
        raise ModalAgenticMultiSweError(
            "oracle source run is incomplete"
        )
    if config.workspace_source_run_id and len(
        state["workspace_records"]
    ) != 50:
        raise ModalAgenticMultiSweError(
            "workspace source run is incomplete"
        )
    for stage in ("smoke", "full"):
        stage_root = root / stage / "trajectory-results"
        if stage_root.is_dir():
            state[stage] = {
                path.stem: json.loads(
                    path.read_text(encoding="utf-8")
                )
                for path in stage_root.glob("*.json")
            }
    return state


def _request_json(
    url: str,
    key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    request = Request(
        url,
        data=(
            None
            if payload is None
            else json.dumps(payload).encode()
        ),
        method="GET" if payload is None else "POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read() or b"{}")
    if not isinstance(value, dict):
        raise ModalAgenticMultiSweError(
            "SGLang returned a non-object response"
        )
    return value


def _wait_server(url: str, key: str) -> dict[str, Any]:
    deadline = time.monotonic() + CONFIG.startup_timeout_seconds
    errors: dict[str, int] = {}
    while time.monotonic() < deadline:
        try:
            _request_json(
                url.rstrip("/") + "/health", key, timeout=10
            )
            models = _request_json(
                url.rstrip("/") + "/v1/models", key, timeout=30
            )
            rows = models.get("data")
            ids = (
                [
                    row.get("id")
                    for row in rows
                    if isinstance(row, dict)
                ]
                if isinstance(rows, list)
                else []
            )
            if ids != [SERVED_MODEL_NAME]:
                raise ModalAgenticMultiSweError(
                    "served-model identity mismatch"
                )
            response = _request_json(
                url.rstrip("/") + "/v1/chat/completions",
                key,
                {
                    "model": SERVED_MODEL_NAME,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Reply with exactly READY.",
                        }
                    ],
                    "max_tokens": 2048,
                    "temperature": 0,
                    "stream": False,
                },
                timeout=900,
            )
            choices = response.get("choices")
            choice = (
                choices[0]
                if isinstance(choices, list) and choices
                else {}
            )
            message = (
                choice.get("message")
                if isinstance(choice, dict)
                and isinstance(choice.get("message"), dict)
                else {}
            )
            content = message.get("content")
            return {
                "status": "ready",
                "models": ids,
                "response_keys": sorted(response),
                "message_keys": sorted(message),
                "content_present": isinstance(content, str),
                "content_chars": (
                    len(content) if isinstance(content, str) else 0
                ),
                "finish_reason": choice.get("finish_reason"),
                "usage": {
                    key: value
                    for key, value in (
                        response.get("usage") or {}
                    ).items()
                    if isinstance(value, (int, float))
                    and not isinstance(value, bool)
                },
                "transient_errors": errors,
            }
        except Exception as exc:
            label = type(exc).__name__
            errors[label] = errors.get(label, 0) + 1
            time.sleep(5)
    raise ModalAgenticMultiSweError(
        "external SGLang admission timed out"
    )


async def _download(prefix: str, local_root: Path) -> int:
    files = []
    seen: set[str] = set()
    async for entry in results_volume.iterdir.aio(
        prefix, recursive=True
    ):
        if entry.type != FileEntryType.FILE:
            continue
        remote = str(entry.path).lstrip("/")
        relative = Path(remote).relative_to(prefix)
        name = relative.as_posix()
        if (
            name in {"", "."}
            or relative.is_absolute()
            or ".." in relative.parts
            or name in seen
        ):
            raise ModalAgenticMultiSweError(
                "unsafe or duplicate Volume artifact path"
            )
        seen.add(name)
        files.append((remote, local_root / relative))
    semaphore = asyncio.Semaphore(16)

    async def one(remote: str, target: Path) -> None:
        async with semaphore:
            data = b"".join(
                [
                    chunk
                    async for chunk in results_volume.read_file.aio(
                        remote
                    )
                ]
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                raise ModalAgenticMultiSweError(
                    "local artifact differs from Volume"
                )
            target.write_bytes(data)

    await asyncio.gather(
        *(one(remote, target) for remote, target in files)
    )
    return len(files)


def download_run() -> Path:
    root = CONFIG.local_run_path(ROOT)
    root.mkdir(parents=True, exist_ok=True)
    if not asyncio.run(
        _download("runs/" + CONFIG.run_id, root)
    ):
        raise ModalAgenticMultiSweError(
            "no committed run artifacts"
        )
    return root


@app.local_entrypoint()
def main() -> None:
    """Run CPU gates, hold one GPU server, release it, then grade."""

    from w8_biayn.modal_agentic_multi_swe_runtime import (
        evaluate,
        prepare_proofs,
    )

    prepare_local_plan(CONFIG, repo_root=ROOT)
    state = load_remote_state.remote(RUNTIME)
    staged = prepare_dataset.remote(RUNTIME, LOCK)

    persist_lock = threading.Lock()

    def persist(files: dict[str, Any]) -> None:
        with persist_lock:
            persist_files.remote(RUNTIME, files)

    admitted = prepare_proofs(
        config=CONFIG,
        lock=LOCK,
        tasks=staged["tasks"],
        dataset_receipt=staged["receipt"],
        grade=grade_with_retry,
        workspace_probe=lambda task: workspace_probe.remote(task),
        persist=persist,
        oracle_records=state["oracle_records"],
        workspace_records=state["workspace_records"],
    )
    if CONFIG.oracle_source_run_id:
        persist(
            {
                "data/oracle-import.json": {
                    "source_run_id": CONFIG.oracle_source_run_id,
                    "exact_cache_keys": True,
                    "fallback_to_execution": False,
                }
            }
        )
    if CONFIG.workspace_source_run_id:
        persist(
            {
                "data/workspace-import.json": {
                    "source_run_id": CONFIG.workspace_source_run_id,
                    "exact_cache_keys": True,
                    "fallback_to_execution": False,
                }
            }
        )
    persist(
        {
            "swe-agent.identity.json": {
                "commit": SWE_AGENT_COMMIT,
                "config_blob": SWE_AGENT_CONFIG_BLOB,
                "config_sha256": SWE_AGENT_CONFIG_SHA256,
                "dependency_lock_sha256": SWE_AGENT_DEPENDENCY_LOCK_SHA256,
                "tool_trees": {
                    "registry": SWE_AGENT_TOOLS_TREE,
                    "edit": SWE_AGENT_EDIT_TREE,
                    "review": SWE_AGENT_REVIEW_TREE,
                },
            }
        }
    )
    cache = preload_model.remote(RUNTIME)
    persist({"model-cache.receipt.json": cache})
    SGLangServer.update_autoscaler(
        min_containers=1,
        scaledown_window=SGLANG_SCALEDOWN_WINDOW_SECONDS,
    )
    url = SGLangServer.get_web_url()
    released = False

    def release_gpu() -> None:
        nonlocal released
        if released:
            return
        SGLangServer.update_autoscaler(
            min_containers=0,
            scaledown_window=SGLANG_POST_GENERATION_WINDOW_SECONDS,
        )
        time.sleep(2)
        released = True

    def acquire_gpu() -> None:
        nonlocal released
        if not released:
            return
        SGLangServer.update_autoscaler(
            min_containers=1,
            scaledown_window=SGLANG_SCALEDOWN_WINDOW_SECONDS,
        )
        released = False
        readmission = _wait_server(url, SGLANG_API_KEY)
        persist({"server.reacquisition.json": readmission})

    try:
        admission = _wait_server(url, SGLANG_API_KEY)
        persist(
            {
                "admission.response.json": admission,
                "server.receipt.json": {
                    "status": "ready",
                    "model": SERVED_MODEL_NAME,
                    "sglang_image": CONFIG.sglang_image,
                    "gpu": CONFIG.gpu,
                    "active_lease": 1,
                    "server_execution_timeout_seconds": (
                        SERVER_EXECUTION_TIMEOUT_SECONDS
                    ),
                    "admission": admission,
                },
            }
        )
        result = evaluate(
            config=CONFIG,
            lock=LOCK,
            staged=admitted,
            run_trajectory=lambda task, attempt: (
                run_agent_trajectory.remote(
                    task,
                    attempt,
                    url,
                    SGLANG_API_KEY,
                )
            ),
            grade=grade_with_retry,
            release_gpu=release_gpu,
            acquire_gpu=acquire_gpu,
            persist=persist,
            resume_state=state,
        )
    finally:
        release_gpu()
    result["receipt"]["modal_app_id"] = app.app_id
    persist({"run_receipt.json": result["receipt"]})
    root = download_run()
    persist(
        {
            "artifact_manifest.json": build_artifact_manifest(
                root
            )
        }
    )
    download_run()
    print("remote_status: " + result["receipt"]["status"])
    print("downloaded_artifacts: " + str(root))
