"""Ephemeral Modal app for the GLM-4.7-Flash Multi-SWE C++ benchmark."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.request import Request, urlopen

import modal
from modal.volume import FileEntryType


IS_LOCAL = modal.is_local()
ROOT = Path(__file__).resolve().parents[3] if IS_LOCAL else Path("/opt/w8-src")
if IS_LOCAL:
    sys.path.insert(0, str(ROOT / "src"))

from w8_biayn.integrations.slime_multi_swe_cpp import (  # noqa: E402
    REPO_HARNESSES,
    ORACLE_PROTOCOL_VERSION,
    SIMDJSON_OFFLINE_INSTANCE_IDS,
    SCHEMA_VERSION as MULTI_SWE_SCHEMA_VERSION,
    build_prompt,
    load_multi_swe_rows,
    normalized_task,
    prepare_repo_harness_revisions,
    prepare_simdjson_offline_dependencies,
    repo_harness_for_row,
)
from w8_biayn.modal_glm47 import (  # noqa: E402
    MODEL_REPO,
    SERVED_MODEL_NAME,
    SGLANG_ADMISSION_MAX_TOKENS,
    SGLANG_POST_GENERATION_WINDOW_SECONDS,
    SGLANG_SCALEDOWN_WINDOW_SECONDS,
    TRANSFORMERS_COMMIT,
    TRANSFORMERS_REPO_URL,
    ensure_secret_free,
    sha256_file,
    sglang_server_command,
    summarize_sglang_admission,
    validate_model_snapshot,
    validate_sglang_admission,
    validate_sglang_help,
)
from w8_biayn.modal_multi_swe_cpp import (  # noqa: E402
    DATASET_REPO,
    ModalMultiSweConfig,
    ModalMultiSweError,
    SIMDJSON_MODAL_MOUNT_LAYOUT,
    SIMDJSON_MODAL_MOUNT_PATH,
    SIMDJSON_MODAL_MOUNT_RELATIVE,
    assert_resume_compatible,
    build_artifact_manifest,
    modal_sandbox_instance_script,
    resume_identity_mismatches,
    response_metadata,
    summarize_modal_execution_output,
    utc_now,
    validate_image_lock,
    write_json,
)


def _config(payload: dict[str, Any]) -> ModalMultiSweConfig:
    names = {item.name for item in fields(ModalMultiSweConfig)}
    values = {key: value for key, value in payload.items() if key in names}
    values["smoke_task_ids"] = tuple(values["smoke_task_ids"])
    values["modal_token_id"] = "<not-attached>"
    values["modal_token_secret"] = "<not-attached>"
    values["hf_token"] = "<downloader-only>" if payload.get("hf_token_present") else ""
    return ModalMultiSweConfig(**values)


if IS_LOCAL:
    CONFIG = ModalMultiSweConfig.from_env(repo_root=ROOT)
    RUNTIME = CONFIG.runtime_mapping()
    LOCK = validate_image_lock(ROOT / CONFIG.image_lock_path)
else:
    RUNTIME = json.loads(os.environ["W8_MODAL_MULTI_SWE_RUNTIME_CONFIG"])
    CONFIG = _config(RUNTIME)
    LOCK = json.loads(os.environ["W8_MODAL_MULTI_SWE_IMAGE_LOCK"])
RUNTIME_JSON = json.dumps(RUNTIME, sort_keys=True)
LOCK_JSON = json.dumps(LOCK, sort_keys=True)
SGLANG_API_KEY = secrets.token_urlsafe(48) if IS_LOCAL else ""

app = modal.App(CONFIG.app_name)
model_volume = modal.Volume.from_name(CONFIG.model_volume, create_if_missing=True)
data_volume = modal.Volume.from_name(CONFIG.data_volume, create_if_missing=True)
results_volume = modal.Volume.from_name(CONFIG.results_volume, create_if_missing=True)
server_secret = modal.Secret.from_dict({"SGLANG_API_KEY": SGLANG_API_KEY} if IS_LOCAL else {})
downloader_secrets = (
    [modal.Secret.from_dict({"HF_TOKEN": CONFIG.hf_token})] if IS_LOCAL and CONFIG.hf_token else []
)

if IS_LOCAL:
    pure_source = str(ROOT / "src" / "w8_biayn")
    control_image = (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install("huggingface-hub[hf-transfer]>=0.24", "pydantic>=2.7")
        .env(
            {
                "PYTHONPATH": "/opt/w8-src",
                "W8_MODAL_MULTI_SWE_RUNTIME_CONFIG": RUNTIME_JSON,
                "W8_MODAL_MULTI_SWE_IMAGE_LOCK": LOCK_JSON,
            }
        )
        .add_local_dir(pure_source, "/opt/w8-src/w8_biayn")
    )
    server_image = (
        modal.Image.from_registry(CONFIG.sglang_image)
        .pip_install("pydantic>=2.7")
        .pip_install("git+" + TRANSFORMERS_REPO_URL + "@" + TRANSFORMERS_COMMIT)
        .run_commands(
            'python -c "from transformers.models.auto.configuration_auto '
            "import CONFIG_MAPPING; assert 'glm4_moe_lite' in CONFIG_MAPPING\""
        )
        .env(
            {
                "PYTHONPATH": "/opt/w8-src",
                "W8_MODAL_MULTI_SWE_RUNTIME_CONFIG": RUNTIME_JSON,
            }
        )
        .add_local_dir(pure_source, "/opt/w8-src/w8_biayn")
    )
else:
    control_image = modal.Image.debian_slim()
    server_image = modal.Image.debian_slim()


@app.function(image=control_image, volumes={"/results": results_volume}, timeout=120, retries=0)
def preflight_remote_run(payload: dict[str, Any]) -> dict[str, Any]:
    config = _config(payload)
    results_volume.reload()
    root = Path("/results") / config.remote_run_path.lstrip("/")
    present = list(root.iterdir()) if root.is_dir() else []
    if present and not config.resume:
        raise ModalMultiSweError("remote run id already has artifacts")
    if not present:
        return {}
    post_oracle_paths = (
        "model-cache.receipt.json",
        "server.failure.json",
        "server.receipt.json",
        "server.runtime.json",
        "admission.failure.json",
        "admission.response.json",
        "run_receipt.json",
        "smoke",
        "full",
    )
    oracle_only = not any((root / relative).exists() for relative in post_oracle_paths)
    prior_config = root / "config.redacted.json"
    mismatches = resume_identity_mismatches(config, prior_config)
    assert_resume_compatible(
        config,
        prior_config,
        allow_oracle_source_migration=oracle_only,
    )
    receipt = root / "run_receipt.json"
    if receipt.is_file() and json.loads(receipt.read_text()).get("status") in {
        "complete",
        "smoke_complete",
    }:
        raise ModalMultiSweError("completed runs are immutable")
    state: dict[str, Any] = {"oracle_records": {}, "smoke": {}, "full": {}}
    if mismatches:
        prior = json.loads(prior_config.read_text(encoding="utf-8"))
        state["oracle_source_migration"] = {
            "schema_version": 1,
            "kind": "oracle-only-source-migration",
            "mismatched_fields": mismatches,
            "prior_source_commit": prior.get("source_commit"),
            "current_source_commit": config.source_commit,
            "exact_oracle_cache_keys_required": True,
            "migrated_at_utc": utc_now(),
        }
    dataset_receipt = root / "dataset.receipt.json"
    if dataset_receipt.is_file():
        state["dataset_receipt"] = json.loads(dataset_receipt.read_text())
    oracle_root = root / "data" / "oracle.records"
    if oracle_root.is_dir():
        for path in oracle_root.glob("*.json"):
            record = json.loads(path.read_text())
            state["oracle_records"][str(record["task_id"])] = record
    for stage in ("smoke", "full"):
        stage_state: dict[str, Any] = {}
        for kind in ("requests", "responses", "records"):
            directory = root / stage / kind
            rows: dict[str, Any] = {}
            if directory.is_dir():
                for path in directory.glob("*.json"):
                    rows[path.stem] = json.loads(path.read_text())
            stage_state[kind] = rows
        state[stage] = stage_state
    return state


@app.function(
    image=control_image,
    volumes={"/data": data_volume},
    secrets=downloader_secrets,
    timeout=CONFIG.max_run_seconds,
    retries=0,
)
def prepare_dataset(payload: dict[str, Any], lock: dict[str, Any]) -> dict[str, Any]:
    """Stage the exact dataset and pinned dependencies on CPU."""

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
    if len(rows) != 50 or set(lock["tasks"]) != {str(row["instance_id"]) for row in rows}:
        raise ModalMultiSweError("exact dataset does not produce the locked 50-task set")
    prepared = revision_root / "prepared"
    pairs = []
    prompts = {}
    for row in rows:
        harness = repo_harness_for_row(row)
        assert harness is not None
        instance_id = str(row["instance_id"])
        task = normalized_task(row, harness=harness, instance_id=instance_id)
        lock_row = lock["tasks"][instance_id]
        if task["sandbox_image"] != lock_row["tag"]:
            raise ModalMultiSweError("dataset/image-lock tag mismatch for " + instance_id)
        task["sandbox_image_digest"] = lock_row["digest"]
        task["sandbox_image_source"] = "checked-in-modal-lock"
        path = prepared / "tasks" / instance_id / "task.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, task)
        pairs.append((path, task))
        prompt = build_prompt(row, harness=harness, instance_id=instance_id)
        prompts[instance_id] = {
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        }
    write_json(
        prepared / "manifest.json",
        {
            "schema_version": 3,
            "admitted": False,
            "task_count": 50,
            "files": {"tasks": [str(path.relative_to(prepared)) for path, _ in pairs]},
        },
    )
    prepare_simdjson_offline_dependencies(prepared, pairs)
    prepare_repo_harness_revisions(pairs)
    tasks = [json.loads(path.read_text(encoding="utf-8")) for path, _ in pairs]
    repo_counts: dict[str, int] = {}
    for task in tasks:
        task_id = task["instance_id"]
        task_path = prepared / "tasks" / task_id / "task.json"
        prompts[task_id]["task_json_sha256"] = sha256_file(task_path)
        repo_name = task["repo_full_name"]
        repo_counts[repo_name] = repo_counts.get(repo_name, 0) + 1
    offline_path = prepared / "offline-dependencies.json"
    offline_dependencies = (
        json.loads(offline_path.read_text(encoding="utf-8")) if offline_path.is_file() else None
    )
    modal_sandbox_dependencies = None
    if offline_dependencies is not None:
        cache_root = prepared / str(offline_dependencies["cache_root"])
        mount_root = prepared / SIMDJSON_MODAL_MOUNT_RELATIVE
        marker = mount_root / ".w8-biayn-bundle-sha256"
        bundle_sha256 = str(offline_dependencies["simdjson_bundle_sha256"])
        mount_valid = (
            marker.is_file()
            and marker.read_text(encoding="utf-8").strip() == bundle_sha256
            and (mount_root / "cxxopts").is_dir()
            and (mount_root / ".cache" / "simdjson-data").is_dir()
        )
        if not mount_valid:
            if mount_root.exists():
                shutil.rmtree(mount_root)
            shutil.copytree(cache_root / "cxxopts", mount_root / "cxxopts")
            shutil.copytree(cache_root / "simdjson-data", mount_root / ".cache" / "simdjson-data")
            marker.write_text(bundle_sha256 + "\n", encoding="utf-8")
        modal_sandbox_dependencies = {
            "layout": SIMDJSON_MODAL_MOUNT_LAYOUT,
            "sub_path": SIMDJSON_MODAL_MOUNT_RELATIVE,
            "mount_path": SIMDJSON_MODAL_MOUNT_PATH,
            "simdjson_bundle_sha256": bundle_sha256,
            "read_only": True,
        }
    receipt = {
        "status": "complete",
        "dataset_repo": DATASET_REPO,
        "dataset_revision": config.dataset_revision,
        "raw_bytes": source.stat().st_size,
        "raw_sha256": sha256_file(source),
        "source_rows": len(all_rows),
        "cpp_rows": len(tasks),
        "task_ids": [task["instance_id"] for task in tasks],
        "repo_counts": dict(sorted(repo_counts.items())),
        "multi_swe_schema_version": MULTI_SWE_SCHEMA_VERSION,
        "oracle_protocol_version": ORACLE_PROTOCOL_VERSION,
        "prompts": prompts,
        "image_lock_sha256": lock["sha256"],
        "completed_at_utc": utc_now(),
        "offline_dependencies": offline_dependencies,
        "modal_sandbox_dependencies": modal_sandbox_dependencies,
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
    target = Path("/models/zai-org--GLM-4.7-Flash") / config.model_revision
    manifest_path = target.parent / (config.model_revision + ".manifest.json")
    cache_hit = False
    if target.is_dir() and manifest_path.is_file():
        try:
            manifest = validate_model_snapshot(target, expected_revision=config.model_revision)
            cache_hit = True
        except Exception:
            cache_hit = False
    if not cache_hit:
        if target.exists():
            target.rename(target.with_name(target.name + ".incomplete-" + str(int(time.time()))))
        snapshot_download(
            repo_id=MODEL_REPO,
            revision=config.model_revision,
            local_dir=target,
            token=os.environ.get("HF_TOKEN") or None,
        )
        manifest = validate_model_snapshot(target, expected_revision=config.model_revision)
        write_json(manifest_path, manifest)
        model_volume.commit()
    return {
        "status": "complete",
        "cache_hit": cache_hit,
        "model_repo": MODEL_REPO,
        "model_revision": config.model_revision,
        "manifest_sha256": manifest["manifest_sha256"],
    }


@app.function(image=control_image, volumes={"/results": results_volume}, timeout=300, retries=0)
def persist_files(payload: dict[str, Any], files: dict[str, Any]) -> None:
    config = _config(payload)
    root = Path("/results") / config.remote_run_path.lstrip("/")
    for relative, value in files.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ModalMultiSweError("unsafe persisted artifact path")
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            target.write_text(value, encoding="utf-8")
        else:
            write_json(target, value)
    results_volume.commit()


def _request(url: str, key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = Request(
        url,
        data=None if payload is None else json.dumps(payload).encode(),
        method="GET" if payload is None else "POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=CONFIG.max_run_seconds) as response:
        value = json.loads(response.read() or b"{}")
    if not isinstance(value, dict):
        raise ModalMultiSweError("server response is not a JSON object")
    return value


@app.server(
    image=server_image,
    gpu=CONFIG.gpu,
    volumes={
        "/models": model_volume.with_mount_options(read_only=True),
        "/results": results_volume,
    },
    secrets=[server_secret],
    min_containers=0,
    max_containers=1,
    buffer_containers=0,
    scaledown_window=SGLANG_SCALEDOWN_WINDOW_SECONDS,
    startup_timeout=CONFIG.startup_timeout_seconds,
    port=8000,
    unauthenticated=True,
)
class SGLangServer:
    @modal.enter()
    def start(self) -> None:
        config = _config(json.loads(os.environ["W8_MODAL_MULTI_SWE_RUNTIME_CONFIG"]))
        self.log = Path("/tmp/sglang.log").open("w", encoding="utf-8")
        try:
            help_result = subprocess.run(
                ["python", "-m", "sglang.launch_server", "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            validate_sglang_help(help_result.stdout + help_result.stderr)
            command = sglang_server_command(config, api_key=os.environ["SGLANG_API_KEY"])
            self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + config.startup_timeout_seconds
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise ModalMultiSweError("SGLang exited during startup")
                try:
                    _request("http://127.0.0.1:8000/health", os.environ["SGLANG_API_KEY"])
                    return
                except Exception:
                    time.sleep(5)
            raise ModalMultiSweError("SGLang startup timed out")
        except BaseException as exc:
            if getattr(self, "process", None) and self.process.poll() is None:
                self.process.terminate()
            self.log.flush()
            raw = Path("/tmp/sglang.log").read_bytes()
            bearer = os.environ["SGLANG_API_KEY"].encode()
            tail = raw[-65536:].replace(bearer, b"<redacted>")
            failure = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "tail": tail.decode(errors="replace"),
                "tail_bytes": len(tail),
                "raw_log_bytes": len(raw),
                "raw_log_sha256": hashlib.sha256(raw).hexdigest(),
                "tail_truncated": len(raw) > 65536,
                "failed_at_utc": utc_now(),
            }
            ensure_secret_free(failure, [os.environ["SGLANG_API_KEY"]])
            target = Path("/results") / config.remote_run_path.lstrip("/") / "server.failure.json"
            write_json(target, failure)
            results_volume.commit()
            raise ModalMultiSweError("SGLang startup failed (" + type(exc).__name__ + ")") from None

    @modal.exit()
    def stop(self) -> None:
        if getattr(self, "process", None) and self.process.poll() is None:
            self.process.terminate()
        if getattr(self, "log", None):
            self.log.close()


def _sandbox_volumes(task: dict[str, Any]) -> dict[str, Any]:
    if task["instance_id"] not in SIMDJSON_OFFLINE_INSTANCE_IDS:
        return {}
    prefix = "revisions/" + CONFIG.dataset_revision + "/prepared/" + SIMDJSON_MODAL_MOUNT_RELATIVE
    return {
        SIMDJSON_MODAL_MOUNT_PATH: data_volume.with_mount_options(read_only=True, sub_path=prefix)
    }


def grade_patch(task: dict[str, Any], patch: str) -> dict[str, Any]:
    """Create a fresh secret-free network-blocked Sandbox for one patch."""

    harness = REPO_HARNESSES[(task["org"].lower(), task["repo"].lower())]
    script = modal_sandbox_instance_script(
        task,
        harness,
        timeout_s=CONFIG.test_timeout_seconds,
    )
    sandbox = None
    started = time.monotonic()
    try:
        sandbox = modal.Sandbox.create(
            "bash",
            "-lc",
            "sleep 86400",
            app=app,
            image=modal.Image.from_registry(task["sandbox_image_digest"]),
            timeout=CONFIG.sandbox_lifetime_seconds,
            cpu=(CONFIG.sandbox_cpu, CONFIG.sandbox_cpu),
            memory=(CONFIG.sandbox_memory_mib, CONFIG.sandbox_memory_mib),
            block_network=True,
            volumes=_sandbox_volumes(task),
            secrets=[],
        )
        sandbox.filesystem.write_text(patch, "/home/fix.patch")
        process = sandbox.exec(
            "bash", "-lc", script, timeout=CONFIG.test_timeout_seconds, text=True
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            stdout = pool.submit(process.stdout.read)
            stderr = pool.submit(process.stderr.read)
            returncode = process.wait()
            output = summarize_modal_execution_output(
                stdout.result(),
                stderr.result(),
                returncode=returncode,
            )
        return {
            "returncode": returncode,
            "timed_out": returncode == 124,
            **output,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "sandbox_id": sandbox.object_id,
            "image": task["sandbox_image_digest"],
            "block_network": True,
            "cpu": [2.0, 2.0],
            "memory_mib": [2048, 2048],
        }
    finally:
        if sandbox is not None:
            try:
                sandbox.terminate(wait=True)
            finally:
                sandbox.detach()


def grade_with_retry(task: dict[str, Any], patch: str) -> dict[str, Any]:
    ids = []
    for attempt in range(2):
        try:
            result = grade_patch(task, patch)
            result["infrastructure_retries"] = attempt
            result["sandbox_ids"] = ids + [result["sandbox_id"]]
            return result
        except Exception as exc:
            ids.append(type(exc).__name__)
            if attempt:
                raise ModalMultiSweError("Sandbox infrastructure failed twice") from exc
    raise AssertionError("unreachable")


async def _download(prefix: str, local_root: Path) -> int:
    files = []
    seen: set[str] = set()
    async for entry in results_volume.iterdir.aio(prefix, recursive=True):
        if entry.type != FileEntryType.FILE:
            continue
        remote = str(entry.path).lstrip("/")
        relative = Path(remote).relative_to(prefix)
        relative_name = relative.as_posix()
        if relative_name in {"", "."} or relative.is_absolute() or ".." in relative.parts:
            raise ModalMultiSweError("unsafe Volume artifact path")
        if relative_name in seen:
            raise ModalMultiSweError("duplicate Volume artifact path")
        seen.add(relative_name)
        files.append((remote, local_root / relative))
    semaphore = asyncio.Semaphore(16)

    async def one(remote: str, target: Path) -> None:
        async with semaphore:
            data = b"".join([chunk async for chunk in results_volume.read_file.aio(remote)])
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                raise ModalMultiSweError("local artifact differs from Volume")
            target.write_bytes(data)

    await asyncio.gather(*(one(remote, target) for remote, target in files))
    return len(files)


def download_run() -> Path:
    root = CONFIG.local_run_path(ROOT)
    root.mkdir(parents=True, exist_ok=True)
    if not asyncio.run(_download("runs/" + CONFIG.run_id, root)):
        raise ModalMultiSweError("no committed run artifacts")
    return root


@app.local_entrypoint()
def main() -> None:
    """Enforce oracle-before-model ordering, smoke, full, download, and release."""

    resume_state = preflight_remote_run.remote(RUNTIME)
    # Dataset staging and all-task oracle execution are intentionally delegated
    # to the checked-in production helpers below before this call is allowed to
    # allocate model weights or the SGLang Server.
    from w8_biayn.modal_multi_swe_runtime import prepare_and_admit, evaluate

    staged = prepare_dataset.remote(RUNTIME, LOCK)
    admitted = prepare_and_admit(
        config=CONFIG,
        lock=LOCK,
        tasks=staged["tasks"],
        dataset_receipt=staged["receipt"],
        grade=grade_with_retry,
        persist=lambda files: persist_files.remote(RUNTIME, files),
        resume_state=resume_state,
    )
    cache = preload_model.remote(RUNTIME)
    persist_files.remote(RUNTIME, {"model-cache.receipt.json": cache})
    url = SGLangServer.get_url()
    key = SGLANG_API_KEY
    admission_response = None
    models_response = None
    try:
        models_response = _request(url.rstrip("/") + "/v1/models", key)
        model_rows = models_response.get("data")
        model_ids = (
            [row.get("id") for row in model_rows if isinstance(row, dict)]
            if isinstance(model_rows, list)
            else []
        )
        if model_ids != [SERVED_MODEL_NAME]:
            raise ModalMultiSweError("SGLang served-model identity mismatch")
        admission_response = _request(
            url.rstrip("/") + "/v1/chat/completions",
            key,
            {
                "model": SERVED_MODEL_NAME,
                "messages": [{"role": "user", "content": "Reply with exactly READY."}],
                "max_tokens": min(CONFIG.max_tokens, SGLANG_ADMISSION_MAX_TOKENS),
                "temperature": 0,
                "stream": False,
            },
        )
        admission = summarize_sglang_admission(
            admission_response,
            requested_max_tokens=min(CONFIG.max_tokens, SGLANG_ADMISSION_MAX_TOKENS),
        )
        validate_sglang_admission(admission)
    except Exception as exc:
        failure = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "response_metadata": (
                response_metadata(admission_response) if admission_response is not None else None
            ),
            "models_response_keys": sorted(models_response) if models_response else [],
            "served_model_count": len(model_ids) if models_response else 0,
            "failed_at_utc": utc_now(),
        }
        ensure_secret_free(failure, [key])
        persist_files.remote(RUNTIME, {"admission.failure.json": failure})
        raise ModalMultiSweError(
            "authenticated SGLang admission failed (" + type(exc).__name__ + ")"
        ) from None
    ensure_secret_free(admission, [key])
    persist_files.remote(RUNTIME, {"admission.response.json": admission})
    persist_files.remote(
        RUNTIME,
        {
            "server.receipt.json": {
                "status": "ready",
                "model": SERVED_MODEL_NAME,
                "sglang_image": CONFIG.sglang_image,
                "gpu": CONFIG.gpu,
                "admission": admission,
            },
            "server.runtime.json": {
                "scaledown_window_seconds": SGLANG_SCALEDOWN_WINDOW_SECONDS,
                "served_models": model_ids,
                "post_generation_window_seconds": SGLANG_POST_GENERATION_WINDOW_SECONDS,
                "server_argv": sglang_server_command(CONFIG, api_key="<redacted>"),
                "transformers_commit": TRANSFORMERS_COMMIT,
            },
        },
    )
    result = evaluate(
        config=CONFIG,
        lock=LOCK,
        staged=admitted,
        server_url=url,
        api_key=key,
        grade=grade_with_retry,
        persist=lambda files: persist_files.remote(RUNTIME, files),
        release_gpu=lambda: SGLangServer.update_autoscaler(
            scaledown_window=SGLANG_POST_GENERATION_WINDOW_SECONDS
        ),
        resume_state=resume_state,
    )
    result["receipt"]["modal_app_id"] = app.app_id
    persist_files.remote(RUNTIME, {"run_receipt.json": result["receipt"]})
    root = download_run()
    persist_files.remote(RUNTIME, {"artifact_manifest.json": build_artifact_manifest(root)})
    download_run()
    print("remote_status: " + result["receipt"]["status"])
    print("downloaded_artifacts: " + str(root))
