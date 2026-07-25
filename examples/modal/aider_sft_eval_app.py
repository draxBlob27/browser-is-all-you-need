"""Pinned fixed-26 Aider C++ evaluation for raw SFT LoRA adapters on Modal."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import modal


MODEL_PATH = "/models/GLM-4.7-Flash"
AIDER_COMMIT = "5dc9490bb35f9729ef2c95d00a19ccd30c26339c"
POLYGLOT_COMMIT = "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_SOURCE_TENSORS = 9_741
EXPECTED_LAYER_47_TENSORS = 207
EXPECTED_SERVING_TENSORS = 9_534
EVAL_LORA_RANK = int(os.environ.get("GLM47_EVAL_LORA_RANK", "16"))
MODEL_NAME = "glm-4.7-flash-sft"
PORTS = (8000, 8001)

app = modal.App("glm47-aider-sft-fixed26-eval")
image = (
    modal.Image.from_registry(
        "radixark/miles:latest-cu12@sha256:efc8027fc47aaa9687dc4f1046093ed4e2f9789e52a932fcefb7031402aeff37",
    )
    .env(
        {
            "FLASHINFER_VERSION": "0.6.12",
            "FLASHINFER_CUDA_INDEX": "129",
            "GLM47_EVAL_LORA_RANK": str(EVAL_LORA_RANK),
        }
    )
    .run_commands(
        "python3 -m pip install --no-cache-dir --no-deps --upgrade "
        "flashinfer-python==0.6.12 flashinfer-cubin==0.6.12",
        "python3 -m pip install --no-cache-dir --no-deps --upgrade "
        "flashinfer-jit-cache==0.6.12 --index-url https://flashinfer.ai/whl/cu129/",
        "python3 -m pip install --no-cache-dir --no-deps --force-reinstall "
        "sglang-kernel==0.4.4 --index-url https://docs.sglang.ai/whl/cu129/",
        "python3 -m pip install --no-cache-dir --no-deps --upgrade "
        "torch-memory-saver==0.0.9.post1",
    )
    .apt_install("git", "cmake", "make", "g++", "curl", "python3-venv")
    .run_commands(
        f"git clone https://github.com/Aider-AI/aider.git /aider && git -C /aider checkout {AIDER_COMMIT}",
        f"git clone https://github.com/Aider-AI/polyglot-benchmark.git /aider/tmp.benchmarks/polyglot-benchmark && git -C /aider/tmp.benchmarks/polyglot-benchmark checkout {POLYGLOT_COMMIT}",
        "python3 -m venv /opt/aider-venv && /opt/aider-venv/bin/pip install -e '/aider[dev]'",
    )
)

models = modal.Volume.from_name("glm47-models", create_if_missing=False)
runs = modal.Volume.from_name("glm47-runs", create_if_missing=False)
results = modal.Volume.from_name("glm47-aider-sft-eval-results", create_if_missing=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_run_id(run_id: str) -> str:
    value = run_id.strip() if run_id else (
        f"glm47-aider-sft-fixed26-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-"
        f"{uuid.uuid4().hex[:8]}"
    )
    if not RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id must contain only letters, digits, dot, underscore, and hyphen")
    return value


def validate_sha256(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not SHA256_PATTERN.fullmatch(normalized):
        raise ValueError(f"{label} must be an explicit lowercase SHA-256")
    return normalized


def validate_adapter_path(adapter_path: str) -> Path:
    path = PurePosixPath(adapter_path)
    if not path.is_absolute() or len(path.parts) < 4 or path.parts[1] != "runs" or ".." in path.parts:
        raise ValueError("adapter_path must be an absolute checkpoint path beneath /runs")
    return Path(str(path))


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_adapter_files(adapter_path: Path) -> None:
    for name in ("adapter_model.bin", "adapter_config.json"):
        if not (adapter_path / name).is_file():
            raise FileNotFoundError(f"adapter is incomplete: {adapter_path / name}")


def prepare_serving_adapter(source: Path, expected_adapter_sha256: str, run_id: str) -> tuple[Path, dict[str, object]]:
    import torch

    validate_adapter_files(source)
    adapter_sha256 = validate_sha256(expected_adapter_sha256, "expected_adapter_sha256")
    if sha256_path(source / "adapter_model.bin") != adapter_sha256:
        raise RuntimeError("selected adapter bytes do not match the caller-bound SHA-256")

    destination = Path("/tmp") / f"{run_id}-serving-adapter"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=False)

    state = torch.load(source / "adapter_model.bin", map_location="cpu", weights_only=True, mmap=True)
    layer_47_keys = [key for key in state if ".layers.47." in key]
    if len(state) != EXPECTED_SOURCE_TENSORS or len(layer_47_keys) != EXPECTED_LAYER_47_TENSORS:
        raise RuntimeError("adapter tensor structure does not match the GLM-4.7 serving conversion")
    filtered = {key: value for key, value in state.items() if ".layers.47." not in key}
    if len(filtered) != EXPECTED_SERVING_TENSORS or any(".layers.47." in key for key in filtered):
        raise RuntimeError("serving adapter conversion produced an unexpected tensor domain")

    torch.save(filtered, destination / "adapter_model.bin")
    shutil.copy2(source / "adapter_config.json", destination / "adapter_config.json")
    receipt = {
        "schema_version": 1,
        "kind": "glm47-sft-serving-adapter-conversion",
        "source_adapter_path": str(source),
        "source_adapter_sha256": adapter_sha256,
        "source_adapter_config_sha256": sha256_path(source / "adapter_config.json"),
        "source_tensor_count": len(state),
        "removed_layer_47_tensor_count": len(layer_47_keys),
        "serving_tensor_count": len(filtered),
        "serving_adapter_path": str(destination),
        "serving_adapter_sha256": sha256_path(destination / "adapter_model.bin"),
        "serving_adapter_config_sha256": sha256_path(destination / "adapter_config.json"),
    }
    (destination / "conversion_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return destination, receipt


def wait_for_server(proc: subprocess.Popen[str], timeout: int, port: int, log_path: Path) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-12000:]
            raise RuntimeError(f"SGLang on port {port} exited with {proc.returncode}\n{tail}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(5)
    raise TimeoutError(f"SGLang on port {port} did not become healthy")


def load_adapter(serving_path: Path, port: int) -> str:
    payload = json.dumps({"lora_name": MODEL_NAME, "lora_path": str(serving_path)}).encode()
    for endpoint in ("/load_lora_adapter", "/v1/load_lora_adapter"):
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{endpoint}",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer local-eval"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                if response.status == 200:
                    return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc
    raise RuntimeError(f"SGLang on port {port} exposes no LoRA load endpoint")


def create_cpp_shard(run_id: str, shard_index: int) -> tuple[Path, list[str]]:
    if shard_index not in (0, 1):
        raise ValueError("shard_index must be 0 or 1")
    source = Path("/aider/tmp.benchmarks/polyglot-benchmark/cpp/exercises/practice")
    tasks = sorted(path for path in source.iterdir() if path.is_dir())
    if len(tasks) != 26:
        raise RuntimeError(f"fixed C++ benchmark task count mismatch: {len(tasks)} != 26")
    selected = tasks[shard_index * 13 : (shard_index + 1) * 13]
    shard_root = Path("/tmp") / f"{run_id}-polyglot-shard-{shard_index}"
    destination = shard_root / "cpp/exercises/practice"
    destination.mkdir(parents=True, exist_ok=False)
    for task in selected:
        shutil.copytree(task, destination / task.name)
    return shard_root, [task.name for task in selected]


def model_settings(path: Path) -> None:
    path.write_text(
        f"""- name: openai/{MODEL_NAME}
  edit_format: whole
  use_repo_map: false
  use_temperature: true
  streaming: false
  extra_params:
    max_tokens: 32768
    temperature: 0.7
    top_p: 1.0
""",
        encoding="utf-8",
    )


def server_command(port: int) -> list[str]:
    return [
        "python3",
        "-m",
        "sglang.launch_server",
        "--model-path",
        MODEL_PATH,
        "--tp-size",
        "4",
        "--tool-call-parser",
        "glm47",
        "--reasoning-parser",
        "glm45",
        "--mem-fraction-static",
        "0.8",
        "--max-running-requests",
        "16",
        "--served-model-name",
        MODEL_NAME,
        "--api-key",
        "local-eval",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--enable-lora",
        "--max-lora-rank",
        str(EVAL_LORA_RANK),
        "--lora-backend",
        "triton",
        "--lora-target-modules",
        "q_a_proj",
        "kv_a_proj_with_mqa",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
        "--experts-shared-outer-loras",
        "--lora-use-virtual-experts",
    ]


def benchmark(
    run_id: str,
    shard_index: int,
    shard_root: Path,
    settings_path: Path,
    port: int,
    log_path: Path,
) -> dict[str, object]:
    command = [
        "/opt/aider-venv/bin/python",
        "/aider/benchmark/benchmark.py",
        f"{run_id}-shard-{shard_index}",
        "--model",
        f"openai/{MODEL_NAME}",
        "--edit-format",
        "whole",
        "--languages",
        "cpp",
        "--tries",
        "2",
        "--threads",
        "8",
        "--exercises-dir",
        str(shard_root),
        "--read-model-settings",
        str(settings_path),
    ]
    env = os.environ.copy()
    env.update(
        {
            "AIDER_DOCKER": "1",
            "OPENAI_API_BASE": f"http://127.0.0.1:{port}/v1",
            "OPENAI_API_KEY": "local-eval",
        }
    )
    with log_path.open("w", encoding="utf-8") as handle:
        subprocess.run(command, cwd="/aider", check=True, env=env, stdout=handle, stderr=subprocess.STDOUT, text=True)
    candidates = sorted(Path("/aider/tmp.benchmarks").glob(f"*--{run_id}-shard-{shard_index}"))
    if not candidates:
        raise RuntimeError(f"No benchmark output found for shard {shard_index}")
    return {"command": command, "output_dir": str(candidates[-1])}


def validate_output(output_dir: Path, selected_tasks: list[str]) -> dict[str, object]:
    result_paths = sorted(output_dir.rglob(".aider.results.json"))
    if len(result_paths) != 13:
        raise RuntimeError(f"terminal result count mismatch: {len(result_paths)} != 13")
    rows = []
    for path in result_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        outcomes = payload.get("tests_outcomes")
        if (
            payload.get("model") != f"openai/{MODEL_NAME}"
            or payload.get("edit_format") != "whole"
            or not isinstance(payload.get("testcase"), str)
            or not isinstance(outcomes, list)
            or not 1 <= len(outcomes) <= 2
            or any(not isinstance(value, bool) for value in outcomes)
            or (len(outcomes) < 2 and not outcomes[-1])
            or (len(outcomes) > 1 and outcomes[0])
        ):
            raise RuntimeError(f"malformed or incomplete benchmark result: {path}")
        rows.append((path, payload))
    testcases = sorted(payload["testcase"] for _, payload in rows)
    if testcases != sorted(selected_tasks):
        raise RuntimeError("terminal task identities do not match the fixed shard")
    return {
        "terminal_tasks": len(rows),
        "terminal_attempts": sum(len(payload["tests_outcomes"]) for _, payload in rows),
        "maximum_attempts": 26,
        "short_circuited_after_first_pass": sum(
            len(payload["tests_outcomes"]) == 1 and payload["tests_outcomes"][0]
            for _, payload in rows
        ),
        "unique_testcases": len(set(testcases)),
        "testcases": testcases,
        "pass_at_1": sum(bool(payload["tests_outcomes"][0]) for _, payload in rows),
        "pass_at_k": sum(any(payload["tests_outcomes"]) for _, payload in rows),
        "well_formed_tasks": sum(int(payload.get("num_malformed_responses", 0)) == 0 for _, payload in rows),
        "malformed_responses": sum(int(payload.get("num_malformed_responses", 0)) for _, payload in rows),
        "error_outputs": sum(int(payload.get("num_error_outputs", 0)) for _, payload in rows),
        "context_exhaustions": sum(int(payload.get("num_exhausted_context_windows", 0)) for _, payload in rows),
        "test_timeouts": sum(int(payload.get("test_timeouts", 0)) for _, payload in rows),
        "prompt_tokens": sum(int(payload.get("prompt_tokens", 0)) for _, payload in rows),
        "completion_tokens": sum(int(payload.get("completion_tokens", 0)) for _, payload in rows),
        "result_sha256": {str(path.relative_to(output_dir)): sha256_path(path) for path, _ in rows},
        "outcomes": {payload["testcase"]: payload["tests_outcomes"] for _, payload in rows},
    }


@app.function(
    image=image,
    gpu="H100:4",
    cpu=16.0,
    memory=(131_072, 524_288),
    timeout=7_200,
    volumes={"/models": models, "/runs": runs, "/results": results},
)
def evaluate_shard(
    adapter_path: str,
    expected_adapter_sha256: str,
    shard_index: int,
    run_id: str = "",
    data_manifest_sha256: str = "",
) -> dict[str, object]:
    started = utc_now()
    resolved_run_id = validate_run_id(run_id)
    if shard_index not in (0, 1):
        raise ValueError("shard_index must be 0 or 1")
    source = validate_adapter_path(adapter_path)
    serving_path, conversion_receipt = prepare_serving_adapter(
        source, expected_adapter_sha256, f"{resolved_run_id}-shard-{shard_index}"
    )

    destination = Path("/results/runs") / f"{resolved_run_id}-shard-{shard_index}"
    if destination.exists():
        raise FileExistsError(f"refusing to reuse evaluation path: {destination}")
    destination.mkdir(parents=True, exist_ok=False)

    settings_path = Path("/tmp") / f"{resolved_run_id}-shard-{shard_index}-model-settings.yml"
    model_settings(settings_path)
    shard_root, selected_tasks = create_cpp_shard(resolved_run_id, shard_index)

    server: subprocess.Popen[str] | None = None
    server_log = None
    try:
        log_path = destination / "sglang.log"
        server_log = log_path.open("w", encoding="utf-8")
        server = subprocess.Popen(
            server_command(8000),
            stdout=server_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        wait_for_server(server, timeout=1800, port=8000, log_path=log_path)
        adapter_load = load_adapter(serving_path, 8000)
        phase = benchmark(
            resolved_run_id,
            shard_index,
            shard_root,
            settings_path,
            8000,
            destination / "benchmark.log",
        )
        validation = validate_output(Path(str(phase["output_dir"])), selected_tasks)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                server.kill()
        if server_log is not None:
            server_log.close()

    shard_receipt = {
        "status": "complete",
        "run_id": resolved_run_id,
        "shard_index": shard_index,
        "selected_tasks": selected_tasks,
        "output_dir": phase["output_dir"],
        "server_command": server_command(8000),
        "benchmark_command": phase["command"],
        "adapter_load": adapter_load,
        "adapter_path": str(source),
        "adapter_sha256": validate_sha256(expected_adapter_sha256, "expected_adapter_sha256"),
        "adapter_config_sha256": sha256_path(source / "adapter_config.json"),
        "training_data_manifest_sha256": data_manifest_sha256,
        "serving_conversion_receipt": conversion_receipt,
        "aider_commit": AIDER_COMMIT,
        "polyglot_commit": POLYGLOT_COMMIT,
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": 32768,
        "tries": 2,
        "lora_rank": EVAL_LORA_RANK,
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "validation": validation,
    }
    (destination / "shard_receipt.json").write_text(
        json.dumps(shard_receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    results.commit()
    return shard_receipt


@app.function(image=image, cpu=1.0, memory=2_048, volumes={"/results": results})
def merge_shards(run_id: str, shard_receipts: list[dict[str, object]]) -> dict[str, object]:
    resolved_run_id = validate_run_id(run_id)
    destination = Path("/results/runs") / resolved_run_id
    if destination.exists():
        raise FileExistsError(f"refusing to reuse evaluation path: {destination}")
    destination.mkdir(parents=True, exist_ok=False)
    fields = (
        "terminal_tasks",
        "terminal_attempts",
        "maximum_attempts",
        "short_circuited_after_first_pass",
        "pass_at_1",
        "pass_at_k",
        "well_formed_tasks",
        "malformed_responses",
        "error_outputs",
        "context_exhaustions",
        "test_timeouts",
        "prompt_tokens",
        "completion_tokens",
    )
    validation = {
        field: sum(int(receipt["validation"][field]) for receipt in shard_receipts)
        for field in fields
    }
    testcases = sorted(
        testcase
        for receipt in shard_receipts
        for testcase in receipt["validation"]["testcases"]
    )
    if len(testcases) != 26 or len(set(testcases)) != 26:
        raise RuntimeError("merged fixed-26 evaluation is incomplete or duplicated")
    validation.update(
        {
            "unique_testcases": 26,
            "testcases": testcases,
            "outcomes": {
                testcase: outcomes
                for receipt in shard_receipts
                for testcase, outcomes in receipt["validation"]["outcomes"].items()
            },
        }
    )
    receipt = {
        "status": "complete",
        "run_id": resolved_run_id,
        "benchmark": "aider-polyglot-cpp-sft-eval",
        "parallel_topology": "2x independent Modal H100:4 TP4 shards",
        "adapter_path": shard_receipts[0]["adapter_path"],
        "adapter_sha256": shard_receipts[0]["adapter_sha256"],
        "adapter_config_sha256": shard_receipts[0]["adapter_config_sha256"],
        "training_data_manifest_sha256": shard_receipts[0]["training_data_manifest_sha256"],
        "serving_conversion_receipts": [
            receipt["serving_conversion_receipt"] for receipt in shard_receipts
        ],
        "aider_commit": AIDER_COMMIT,
        "polyglot_commit": POLYGLOT_COMMIT,
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": 32768,
        "tries": 2,
        "lora_rank": EVAL_LORA_RANK,
        "started_at_utc": min(str(receipt["started_at_utc"]) for receipt in shard_receipts),
        "completed_at_utc": utc_now(),
        "validation": validation,
        "shards": shard_receipts,
    }
    receipt_path = destination / "run_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    results.commit()
    return receipt


@app.local_entrypoint()
def main(
    adapter_path: str,
    expected_adapter_sha256: str,
    run_id: str = "",
    data_manifest_sha256: str = "",
) -> None:
    resolved_run_id = validate_run_id(run_id)
    calls = [
        evaluate_shard.spawn(
            adapter_path=adapter_path,
            expected_adapter_sha256=expected_adapter_sha256,
            shard_index=index,
            run_id=resolved_run_id,
            data_manifest_sha256=data_manifest_sha256,
        )
        for index in range(2)
    ]
    shard_receipts = [call.get() for call in calls]
    print(
        json.dumps(
            merge_shards.remote(
                run_id=resolved_run_id,
                shard_receipts=shard_receipts,
            ),
            indent=2,
            sort_keys=True,
        )
    )
