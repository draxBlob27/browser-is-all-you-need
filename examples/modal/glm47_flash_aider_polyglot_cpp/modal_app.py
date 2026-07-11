"""Ephemeral Modal app for the official GLM-4.7-Flash Aider C++ benchmark.

Run only through ``run.sh``.  Modal imports are intentionally confined to this
thin boundary; the contract and all admission logic live in the pure
``w8_biayn.modal_aider_polyglot_cpp`` module.
"""

from __future__ import annotations

from dataclasses import fields
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import modal


IS_LOCAL = modal.is_local()
ROOT = Path(__file__).resolve().parents[3] if IS_LOCAL else Path("/opt/w8-src")
if IS_LOCAL:
    sys.path.insert(0, str(ROOT / "src"))

from w8_biayn.modal_aider_polyglot_cpp import (  # noqa: E402
    AIDER_REPO_URL,
    BENCHMARK_LABEL,
    MODEL_REPO,
    MODEL_SETTINGS_PATH,
    MODAL_SDK_PIN,
    POLYGLOT_REPO_URL,
    SCHEMA_VERSION,
    SERVED_MODEL_NAME,
    TRANSFORMERS_COMMIT,
    TRANSFORMERS_REPO_URL,
    ModalAiderConfig,
    ModalAiderError,
    aider_benchmark_command,
    assert_resume_compatible,
    aider_stats_command,
    build_artifact_manifest,
    ensure_secret_free,
    model_settings,
    parse_aider_stats,
    render_plan,
    sha256_file,
    sglang_server_command,
    utc_now,
    validate_aider_results,
    validate_authoritative_stats,
    validate_model_snapshot,
    validate_remote_preflight,
    validate_sglang_help,
    write_json,
)


def _config_from_payload(payload: dict[str, Any]) -> ModalAiderConfig:
    names = {item.name for item in fields(ModalAiderConfig)}
    values = {key: value for key, value in payload.items() if key in names}
    values.update(
        {
            "modal_token_id": "<not-attached>",
            "modal_token_secret": "<not-attached>",
            "hf_token": "<downloader-only>" if payload.get("hf_token_present") else "",
        }
    )
    return ModalAiderConfig(**values)


if IS_LOCAL:
    CONFIG = ModalAiderConfig.from_env(repo_root=ROOT)
    RUNTIME = CONFIG.runtime_mapping()
else:
    RUNTIME = json.loads(os.environ["W8_MODAL_AIDER_RUNTIME_CONFIG"])
    CONFIG = _config_from_payload(RUNTIME)
RUNTIME_JSON = json.dumps(RUNTIME, sort_keys=True)
SGLANG_API_KEY = secrets.token_urlsafe(48) if IS_LOCAL else ""

app = modal.App(
    CONFIG.app_name,
    tags={
        "benchmark": "aider-polyglot-cpp",
        "model": "glm-4-7-flash",
        "run-id": CONFIG.run_id,
        "owner": CONFIG.modal_profile,
        "ttl": "ephemeral",
    },
)
model_volume = modal.Volume.from_name(CONFIG.model_volume, create_if_missing=True)
results_volume = modal.Volume.from_name(CONFIG.results_volume, create_if_missing=True)

secret_payload = {"SGLANG_API_KEY": SGLANG_API_KEY} if IS_LOCAL else {}
server_secret = modal.Secret.from_dict(secret_payload)
runner_secret = modal.Secret.from_dict(secret_payload)
downloader_secrets = (
    [modal.Secret.from_dict({"HF_TOKEN": CONFIG.hf_token})] if IS_LOCAL and CONFIG.hf_token else []
)

if IS_LOCAL:
    pure_source = str(ROOT / "src" / "w8_biayn")
    downloader_image = (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install("huggingface-hub[hf-transfer]>=0.24", "PyYAML>=6.0")
        .env(
            {
                "PYTHONPATH": "/opt/w8-src",
                "HF_HUB_ENABLE_HF_TRANSFER": "1",
                "W8_MODAL_AIDER_RUNTIME_CONFIG": RUNTIME_JSON,
            }
        )
        # Mount-mode local additions must remain after every image build step.
        .add_local_dir(pure_source, "/opt/w8-src/w8_biayn")
    )
    server_image = (
        modal.Image.from_registry(CONFIG.sglang_image)
        .pip_install(f"git+{TRANSFORMERS_REPO_URL}@{TRANSFORMERS_COMMIT}")
        .run_commands(
            'python -c "from transformers.models.auto.configuration_auto import '
            "CONFIG_MAPPING; assert 'glm4_moe_lite' in CONFIG_MAPPING\""
        )
        .env({"PYTHONPATH": "/opt/w8-src", "W8_MODAL_AIDER_RUNTIME_CONFIG": RUNTIME_JSON})
        .add_local_dir(pure_source, "/opt/w8-src/w8_biayn")
    )
    runner_image = (
        modal.Image.from_dockerfile(
            ROOT / "examples/modal/glm47_flash_aider_polyglot_cpp/Dockerfile.aider",
            context_dir=ROOT / "examples/modal/glm47_flash_aider_polyglot_cpp",
            build_args={
                "AIDER_COMMIT": CONFIG.aider_commit,
                "POLYGLOT_COMMIT": CONFIG.polyglot_commit,
            },
        )
        .env({"PYTHONPATH": "/opt/w8-src", "W8_MODAL_AIDER_RUNTIME_CONFIG": RUNTIME_JSON})
        .add_local_dir(pure_source, "/opt/w8-src/w8_biayn")
    )
else:
    downloader_image = modal.Image.debian_slim()
    server_image = modal.Image.debian_slim()
    runner_image = modal.Image.debian_slim()


def _remote_config(payload: dict[str, Any]) -> ModalAiderConfig:
    return _config_from_payload(payload)


@app.function(
    image=downloader_image,
    volumes={"/results": results_volume},
    timeout=120,
    retries=0,
)
def preflight_remote_run(config_payload: dict[str, Any]) -> None:
    """Reject stale result state on CPU before model loading or GPU startup."""

    config = _remote_config(config_payload)
    results_volume.reload()
    run_root = Path("/results") / config.remote_run_path.lstrip("/")
    validate_remote_preflight(config, run_root)


@app.function(
    image=downloader_image,
    volumes={"/models": model_volume},
    secrets=downloader_secrets,
    timeout=CONFIG.max_run_seconds,
    retries=0,
)
def preload_model(config_payload: dict[str, Any]) -> dict[str, Any]:
    """Download and validate the exact public HF revision on CPU only."""

    from huggingface_hub import snapshot_download

    config = _remote_config(config_payload)
    target = Path("/models/zai-org--GLM-4.7-Flash") / config.model_revision
    manifest_path = target.parent / f"{config.model_revision}.manifest.json"
    started = time.monotonic()
    cache_hit = False
    if target.is_dir() and manifest_path.is_file():
        try:
            prior = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                prior.get("model_repo") == MODEL_REPO
                and prior.get("model_revision") == config.model_revision
            ):
                manifest = validate_model_snapshot(
                    target,
                    expected_revision=config.model_revision,
                )
                cache_hit = True
        except (ModalAiderError, json.JSONDecodeError, OSError):
            cache_hit = False
    if not cache_hit:
        if target.exists():
            quarantine = target.with_name(f"{target.name}.incomplete-{int(time.time())}")
            target.rename(quarantine)
        target.mkdir(parents=True, exist_ok=False)
        snapshot_download(
            repo_id=MODEL_REPO,
            revision=config.model_revision,
            local_dir=target,
            token=os.environ.get("HF_TOKEN") or None,
        )
        manifest = validate_model_snapshot(target, expected_revision=config.model_revision)
        write_json(manifest_path, manifest)
        model_volume.commit()
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete",
        "cache_hit": cache_hit,
        "model_repo": MODEL_REPO,
        "model_revision": config.model_revision,
        "manifest_sha256": manifest["manifest_sha256"],
        "weight_bytes": manifest["weight_bytes"],
        "weight_shards": len(manifest["weight_shards"]),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "completed_at_utc": utc_now(),
    }
    receipt_path = Path("/models/receipts") / f"{config.run_id}.json"
    write_json(receipt_path, receipt)
    model_volume.commit()
    return receipt


def _request_json(
    url: str,
    *,
    api_key: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw.decode(errors="replace")}
    if not isinstance(parsed, dict):
        raise ModalAiderError(f"endpoint did not return a JSON object: {url}")
    return parsed


def _wait_for_json(url: str, api_key: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        try:
            return _request_json(url, api_key=api_key, timeout=10)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = type(exc).__name__
            time.sleep(5)
    raise ModalAiderError(f"server admission timed out ({last_error})")


def _scrub(value: str, secret: str) -> str:
    return value.replace(secret, "<redacted>") if secret else value


def _redacted_log_tail(path: Path, secret: str, *, max_chars: int = 12_000) -> str:
    try:
        value = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"<log unavailable: {type(exc).__name__}>"
    return _scrub(value, secret)[-max_chars:]


def _wait_for_process_json(
    url: str,
    api_key: str,
    timeout_seconds: int,
    process: subprocess.Popen[Any],
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        returncode = process.poll()
        if returncode is not None:
            raise ModalAiderError(f"SGLang process exited during startup with code {returncode}")
        try:
            return _request_json(url, api_key=api_key, timeout=10)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = type(exc).__name__
            time.sleep(5)
    raise ModalAiderError(f"SGLang process startup timed out ({last_error})")


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
    scaledown_window=60,
    startup_timeout=CONFIG.startup_timeout_seconds,
    port=8000,
    unauthenticated=True,
    exit_grace_period=30,
)
class SGLangServer:
    """Exactly one authenticated four-GPU SGLang server replica."""

    @modal.enter()
    def start(self) -> None:
        config = _remote_config(json.loads(os.environ["W8_MODAL_AIDER_RUNTIME_CONFIG"]))
        run_root = Path("/results") / config.remote_run_path.lstrip("/")
        run_root.mkdir(parents=True, exist_ok=True)
        failure_path = run_root / "server.failure.json"
        failure_path.unlink(missing_ok=True)
        prior_config = run_root / "config.redacted.json"
        if prior_config.is_file():
            # The benchmark runner writes this while the server is live. A
            # Modal container restart must accept its own compatible run state;
            # stale-run admission already happened on CPU before GPU startup.
            assert_resume_compatible(config, prior_config, allow_plan=True)
        elif config.resume:
            raise ModalAiderError("resume requested but the remote run has no prior config")
        help_result = subprocess.run(
            ["python", "-m", "sglang.launch_server", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        validate_sglang_help(help_result.stdout + help_result.stderr)
        gpu_result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,uuid,memory.total",
                "--format=csv,noheader",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        observed_gpus = [line.strip() for line in gpu_result.stdout.splitlines() if line.strip()]
        if len(observed_gpus) != 4:
            raise ModalAiderError(f"expected four visible GPUs, observed {len(observed_gpus)}")
        command = sglang_server_command(config, api_key=os.environ["SGLANG_API_KEY"])
        started = time.monotonic()
        # SGLang may print its parsed arguments. Keep raw output ephemeral so
        # the command-line bearer can never enter Modal logs or run artifacts.
        self.log_handle = Path("/tmp/sglang.log").open("w", encoding="utf-8")
        self.process = subprocess.Popen(command, stdout=self.log_handle, stderr=subprocess.STDOUT)
        api_key = os.environ["SGLANG_API_KEY"]
        try:
            health = _wait_for_process_json(
                "http://127.0.0.1:8000/health",
                api_key,
                max(30, config.startup_timeout_seconds - 30),
                self.process,
            )
        except Exception as exc:
            self.log_handle.flush()
            log_tail = _redacted_log_tail(Path("/tmp/sglang.log"), api_key)
            failure = {
                "schema_version": SCHEMA_VERSION,
                "status": "failed",
                "run_id": config.run_id,
                "sglang_image": config.sglang_image,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "transformers_commit": TRANSFORMERS_COMMIT,
                "process_returncode": self.process.poll(),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "launch_argv": ["<redacted>" if part == api_key else part for part in command],
                "redacted_log_tail": log_tail,
                "failed_at_utc": utc_now(),
            }
            ensure_secret_free(failure, [api_key])
            write_json(failure_path, failure)
            results_volume.commit()
            if log_tail:
                print(f"SGLang startup failure (redacted tail):\n{log_tail}", file=sys.stderr)
            raise ModalAiderError(
                f"SGLang startup failed ({type(exc).__name__}: {exc}); see server.failure.json"
            ) from exc
        models = _request_json(
            "http://127.0.0.1:8000/v1/models",
            api_key=api_key,
        )
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "status": "ready",
            "run_id": config.run_id,
            "requested_gpu": config.gpu,
            "observed_gpus": observed_gpus,
            "gpu_count": len(observed_gpus),
            "model_path": f"/models/zai-org--GLM-4.7-Flash/{config.model_revision}",
            "served_model_name": SERVED_MODEL_NAME,
            "sglang_image": config.sglang_image,
            "transformers_commit": TRANSFORMERS_COMMIT,
            "launch_argv": [
                "<redacted>" if part == os.environ["SGLANG_API_KEY"] else part for part in command
            ],
            "health": health,
            "models": models,
            "startup_seconds": round(time.monotonic() - started, 3),
            "ready_at_utc": utc_now(),
        }
        write_json(
            Path("/results") / config.remote_run_path.lstrip("/") / "server.runtime.json", receipt
        )
        results_volume.commit()

    @modal.exit()
    def stop(self) -> None:
        if getattr(self, "process", None) and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if getattr(self, "log_handle", None):
            self.log_handle.close()


def _run_aider_stage(
    config: ModalAiderConfig, root: Path, stage: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    stage_root = root / stage
    stage_root.mkdir(parents=True, exist_ok=True)
    source = Path("/opt/aider/tmp.benchmarks/polyglot-benchmark")
    exercises_link = stage_root / "polyglot-benchmark"
    if not exercises_link.exists():
        exercises_link.symlink_to(source, target_is_directory=True)
    prior_matches = sorted(stage_root.glob(f"*--{config.run_id}-{stage}"))
    prior_stats_path = stage_root / "stats.json"
    if stage == "smoke" and len(prior_matches) == 1 and prior_stats_path.is_file():
        expected = config.smoke_tests
        admission = validate_aider_results(prior_matches[0], expected_tasks=expected)
        stats = json.loads(prior_stats_path.read_text(encoding="utf-8"))
        validate_authoritative_stats(stats, expected_tasks=expected)
        return (
            stats,
            {
                **admission.as_mapping(),
                "elapsed_seconds": 0.0,
                "argv": aider_benchmark_command(config, stage=stage),
                "reused": True,
            },
        )
    command = aider_benchmark_command(config, stage=stage)
    write_json(
        stage_root / "command.json",
        {"argv": command, "provider_env": ["OPENAI_API_BASE", "OPENAI_API_KEY"]},
    )
    env = dict(os.environ)
    api_key = env.pop("SGLANG_API_KEY")
    for name in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "HF_TOKEN"):
        env.pop(name, None)
    env.update(
        {
            "OPENAI_API_BASE": env["W8_SGLANG_URL"].rstrip("/") + "/v1",
            "OPENAI_API_KEY": api_key,
            "AIDER_DOCKER": "1",
            "AIDER_BENCHMARK_DIR": str(stage_root),
            "NO_COLOR": "1",
            "TERM": "dumb",
        }
    )
    started = time.monotonic()
    result = subprocess.run(
        command, check=False, capture_output=True, text=True, env=env, cwd="/opt/aider"
    )
    (stage_root / "stdout.log").write_text(_scrub(result.stdout, api_key), encoding="utf-8")
    (stage_root / "stderr.log").write_text(_scrub(result.stderr, api_key), encoding="utf-8")
    if result.returncode:
        raise ModalAiderError(f"Aider {stage} command failed with exit code {result.returncode}")
    matches = sorted(stage_root.glob(f"*--{config.run_id}-{stage}"))
    if len(matches) != 1:
        raise ModalAiderError(f"Aider {stage} did not create exactly one official result directory")
    expected = config.smoke_tests if stage == "smoke" else config.expected_cpp_tasks
    admission = validate_aider_results(matches[0], expected_tasks=expected)
    stats_command = aider_stats_command(matches[0])
    stats_result = subprocess.run(
        stats_command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd="/opt/aider",
    )
    (stage_root / "stats.txt").write_text(_scrub(stats_result.stdout, api_key), encoding="utf-8")
    (stage_root / "stats.stderr.log").write_text(
        _scrub(stats_result.stderr, api_key), encoding="utf-8"
    )
    if stats_result.returncode:
        raise ModalAiderError(f"Aider stats failed for {stage}")
    stats = parse_aider_stats(stats_result.stdout)
    validate_authoritative_stats(stats, expected_tasks=expected)
    write_json(stage_root / "stats.json", stats)
    return (
        stats,
        {
            **admission.as_mapping(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "argv": command,
        },
    )


@app.function(
    image=runner_image,
    volumes={"/results": results_volume},
    secrets=[runner_secret],
    cpu=16,
    memory=32768,
    timeout=CONFIG.max_run_seconds,
    retries=0,
)
def run_aider_benchmark(
    config_payload: dict[str, Any],
    server_url: str,
    model_cache_receipt: dict[str, Any],
    app_id: str,
) -> dict[str, Any]:
    """Admit SGLang, run blocking smoke, then run official Aider C++."""

    config = _remote_config(config_payload)
    os.environ["W8_SGLANG_URL"] = server_url
    api_key = os.environ["SGLANG_API_KEY"]
    root = Path("/results") / config.remote_run_path.lstrip("/")
    root.mkdir(parents=True, exist_ok=True)
    prior_config = root / "config.redacted.json"
    prior_receipt = root / "run_receipt.json"
    if prior_config.is_file():
        if not config.resume:
            raise ModalAiderError("remote run id already has artifacts; use a fresh run id")
        assert_resume_compatible(config, prior_config)
        if prior_receipt.is_file():
            prior_status = json.loads(prior_receipt.read_text(encoding="utf-8")).get("status")
            if prior_status == "complete":
                raise ModalAiderError("a completed full run cannot be resumed")
    elif config.resume:
        raise ModalAiderError("resume requested but the remote run has no prior config")
    started_utc = utc_now()
    total_started = time.monotonic()
    write_json(root / "plan.json", render_plan(config))
    write_json(root / "config.redacted.json", config.redacted_mapping())
    write_json(root / "model-cache.receipt.json", model_cache_receipt)
    settings = model_settings(config)
    Path(MODEL_SETTINGS_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(MODEL_SETTINGS_PATH).write_text(settings, encoding="utf-8")
    (root / "model-settings.yml").write_text(settings, encoding="utf-8")
    (root / "model-settings.sha256").write_text(
        hashlib.sha256(settings.encode()).hexdigest() + "\n", encoding="utf-8"
    )

    aider_head = subprocess.check_output(
        ["git", "-C", "/opt/aider", "rev-parse", "HEAD"], text=True
    ).strip()
    polyglot_root = "/opt/aider/tmp.benchmarks/polyglot-benchmark"
    polyglot_head = subprocess.check_output(
        ["git", "-C", polyglot_root, "rev-parse", "HEAD"], text=True
    ).strip()
    if aider_head != config.aider_commit or polyglot_head != config.polyglot_commit:
        raise ModalAiderError("runner upstream checkout identity mismatch")
    cpp_tasks = len(list(Path(polyglot_root).glob("cpp/exercises/practice/*")))
    if cpp_tasks != config.expected_cpp_tasks:
        raise ModalAiderError(
            f"expected {config.expected_cpp_tasks} C++ exercises, found {cpp_tasks}"
        )
    upstreams = {
        "aider": {"url": AIDER_REPO_URL, "commit": aider_head},
        "polyglot": {"url": POLYGLOT_REPO_URL, "commit": polyglot_head},
        "upstream_aider_dockerfile_sha256": sha256_file("/opt/aider/benchmark/Dockerfile"),
        "local_aider_dockerfile_sha256": sha256_file("/opt/w8/Dockerfile.aider"),
        "runner_difference": "Modal is already the container; AIDER_DOCKER=1, no Docker-in-Docker; C++ dependencies only.",
        "transformers": {"url": TRANSFORMERS_REPO_URL, "commit": TRANSFORMERS_COMMIT},
    }
    write_json(root / "upstreams.json", upstreams)

    _wait_for_json(server_url.rstrip("/") + "/health", api_key, config.startup_timeout_seconds)
    models = _request_json(server_url.rstrip("/") + "/v1/models", api_key=api_key)
    model_ids = [item.get("id") for item in models.get("data", []) if isinstance(item, dict)]
    if model_ids != [SERVED_MODEL_NAME]:
        raise ModalAiderError(f"SGLang served model list mismatch: {model_ids}")
    completion = _request_json(
        server_url.rstrip("/") + "/v1/chat/completions",
        api_key=api_key,
        method="POST",
        timeout=120,
        payload={
            "model": SERVED_MODEL_NAME,
            "messages": [
                {"role": "user", "content": "Think briefly, then reply with exactly READY."}
            ],
            "max_tokens": 128,
            "temperature": 0,
        },
    )
    message = completion.get("choices", [{}])[0].get("message", {})
    if not str(message.get("content") or "").strip() or "reasoning_content" not in message:
        raise ModalAiderError("SGLang did not separate reasoning while preserving editable content")
    results_volume.reload()
    runtime_path = root / "server.runtime.json"
    if not runtime_path.is_file():
        raise ModalAiderError("SGLang server did not persist its runtime receipt")
    server_receipt = json.loads(runtime_path.read_text(encoding="utf-8"))
    server_receipt.update(
        {
            "server_url": server_url,
            "model_listing": models,
            "admission_content_present": True,
            "reasoning_content_field_present": True,
            "model_manifest_sha256": model_cache_receipt["manifest_sha256"],
        }
    )
    ensure_secret_free(server_receipt, [api_key])
    write_json(root / "server.receipt.json", server_receipt)

    smoke_stats, smoke_admission = _run_aider_stage(config, root, "smoke")
    results_volume.commit()
    final_stats = smoke_stats
    final_admission = smoke_admission
    if config.phase == "full":
        final_stats, final_admission = _run_aider_stage(config, root, "full")
        results_volume.commit()

    status = "complete" if config.phase == "full" else "smoke_complete"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "benchmark": BENCHMARK_LABEL,
        "run_id": config.run_id,
        "started_at_utc": started_utc,
        "completed_at_utc": utc_now(),
        "modal_profile": config.modal_profile,
        "modal_environment": config.modal_environment,
        "modal_app_id": app_id,
        "modal_app_name": config.app_name,
        "modal_app_stopped": False,
        "teardown_status": "pending_local_control_plane_verification",
        "model_repo": MODEL_REPO,
        "model_revision": config.model_revision,
        "model_cache_manifest_sha256": model_cache_receipt["manifest_sha256"],
        "aider_commit": config.aider_commit,
        "polyglot_commit": config.polyglot_commit,
        "sglang_image": config.sglang_image,
        "modal_sdk_pin": MODAL_SDK_PIN,
        "gpu_requested": config.gpu,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "gpu_observed": server_receipt["observed_gpus"],
        "model_settings_sha256": hashlib.sha256(settings.encode()).hexdigest(),
        "aider_argv": final_admission["argv"],
        "edit_format": config.edit_format,
        "tries": 1 if config.phase == "smoke" else config.tries,
        "threads": 1 if config.phase == "smoke" else config.threads,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "expected_tasks": config.smoke_tests
        if config.phase == "smoke"
        else config.expected_cpp_tasks,
        "completed_tasks": final_admission["completed_tasks"],
        "exception_tasks": final_admission["exception_tasks"],
        "authoritative_aider_stats": final_stats,
        "server_startup_seconds": server_receipt["startup_seconds"],
        "smoke_elapsed_seconds": smoke_admission["elapsed_seconds"],
        "full_elapsed_seconds": final_admission["elapsed_seconds"]
        if config.phase == "full"
        else None,
        "total_elapsed_seconds": round(time.monotonic() - total_started, 3),
        "remote_volume_path": config.remote_run_path,
        "local_artifact_path": f"{config.local_root}/runs/{config.run_id}",
    }
    ensure_secret_free(receipt, [api_key])
    write_json(root / "run_receipt.json", receipt)
    write_json(root / "artifact_manifest.json", build_artifact_manifest(root))
    results_volume.commit()
    return {"status": status, "stats": final_stats, "receipt": receipt}


def _download_run() -> Path:
    prefix = f"runs/{CONFIG.run_id}"
    local_root = CONFIG.local_run_path(ROOT)
    local_root.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for entry in results_volume.iterdir(prefix, recursive=True):
        remote = str(entry.path).lstrip("/")
        kind = str(getattr(entry, "type", "")).lower()
        if "dir" in kind:
            continue
        relative = Path(remote).relative_to(prefix)
        if relative.is_absolute() or ".." in relative.parts:
            raise ModalAiderError(f"unsafe Modal Volume artifact path: {remote}")
        target = local_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = b"".join(results_volume.read_file(remote))
        if target.exists() and target.read_bytes() != data:
            raise ModalAiderError(f"local artifact differs from committed Volume file: {target}")
        target.write_bytes(data)
        downloaded += 1
    if not downloaded:
        raise ModalAiderError(f"no artifacts downloaded from {CONFIG.results_volume}:{prefix}")
    return local_root


@app.local_entrypoint()
def main() -> None:
    """Cache weights, run the benchmark, and download committed artifacts."""

    preflight_remote_run.remote(RUNTIME)
    cache_receipt = preload_model.remote(RUNTIME)
    server_url = SGLangServer.get_url()
    result = run_aider_benchmark.remote(RUNTIME, server_url, cache_receipt, app.app_id)
    local_root = _download_run()
    print(f"remote_status: {result['status']}")
    print(f"downloaded_artifacts: {local_root}")
