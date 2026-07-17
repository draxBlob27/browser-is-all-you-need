"""Aider-only SFT launcher using Modal's native image builder.

This intentionally avoids the existing PIE launcher's ``from_dockerfile``
path, which currently fails while Modal unpacks the OCI image.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import modal


APP_NAME = "glm47-aider-v1-sft"
MODEL_REVISION = "7dd20894a642a0aa287e9827cb1a1f7f91386b67"
MILES_IMAGE = (
    "radixark/miles:latest-cu12@"
    "sha256:efc8027fc47aaa9687dc4f1046093ed4e2f9789e52a932fcefb7031402aeff37"
)
# Modal imports this module from a flattened function mount inside the remote
# container, where ``__file__`` is `/root/aider_sft_native.py`.  The repository
# path is needed only while the local client constructs ``training_image``.
_SOURCE_FILE = Path(__file__).resolve()
LOCAL_REPO = _SOURCE_FILE.parents[2] if len(_SOURCE_FILE.parents) > 2 else Path.cwd()
REMOTE_REPO = "/workspace/glm47-h100-posttraining"
MODELS_DIR = "/root/models"
ASSETS_DIR = "/workspace/assets"
RUNS_DIR = "/workspace/runs"

app = modal.App(APP_NAME)
models = modal.Volume.from_name("glm47-models", create_if_missing=False)
assets = modal.Volume.from_name("glm47-assets", create_if_missing=False)
runs = modal.Volume.from_name("glm47-runs", create_if_missing=True)

source_ignore = [
    ".git",
    ".agents",
    ".cache",
    ".glm47-posttraining",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp-patch-probe",
    ".venv",
    ".w8-biayn",
    "wandb",
    ".gcp-service-account.json",
    "hf_token.txt",
    "wandb_api_key.txt",
    "README.md.orig",
    "ROADMAP.md.orig",
]

# Matches the runtime dependency layer in Dockerfile, but uses Modal's native
# registry-image builder rather than Image.from_dockerfile().
training_image = (
    modal.Image.from_registry(MILES_IMAGE)
    .env({"FLASHINFER_VERSION": "0.6.12", "FLASHINFER_CUDA_INDEX": "129"})
    .run_commands(
        "python3 -m pip install --no-cache-dir --no-deps --upgrade "
        "flashinfer-python==0.6.12 flashinfer-cubin==0.6.12",
        "python3 -m pip install --no-cache-dir --no-deps --upgrade "
        "flashinfer-jit-cache==0.6.12 --index-url https://flashinfer.ai/whl/cu129/",
        "python3 -m pip install --no-cache-dir --no-deps --force-reinstall "
        "sglang-kernel==0.4.4 --index-url https://docs.sglang.ai/whl/cu129/",
        "python3 -m pip install --no-cache-dir --no-deps --upgrade torch-memory-saver==0.0.9.post1",
    )
    .apt_install("software-properties-common", "rsync", "gawk", "util-linux", "git")
    .run_commands(
        "add-apt-repository -y ppa:ubuntu-toolchain-r/test "
        "&& apt-get update "
        "&& DEBIAN_FRONTEND=noninteractive apt-get install -y gcc-13 g++-13 "
        "&& update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-13 100 "
        "&& update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-13 100"
    )
    .add_local_dir(LOCAL_REPO, remote_path=REMOTE_REPO, copy=True, ignore=source_ignore)
)


def run(command: str, *, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["bash", "-lc", command],
        cwd=REMOTE_REPO,
        env={**os.environ, **(env or {})},
        check=True,
    )


def stage_env(run_id: str) -> dict[str, str]:
    return {
        "MILES_RUN_ID": run_id,
        "MILES_RUN_ROOT": f"{RUNS_DIR}/{run_id}",
        "MILES_HF_CHECKPOINT": f"{MODELS_DIR}/GLM-4.7-Flash",
        "MILES_REF_LOAD_DIR": f"{MODELS_DIR}/GLM-4.7-Flash_torch_dist_tp4_pp1_ep8",
        "MILES_CPP_DATA_DIR": f"{ASSETS_DIR}/prepared",
        "GLM47_MODEL_REVISION": MODEL_REVISION,
        "GLM47_TRAINING_IMAGE": MILES_IMAGE,
        "GLM47_EXPERIMENT_ID": run_id,
        "MILES_WANDB_PROJECT": "glm47-aider-v1-sft",
        "MILES_WANDB_GROUP": run_id,
        "MILES_WANDB_RUN_ID": run_id,
        "MILES_WANDB_JOB_TYPE": "sft",
        "WANDB_RUN_GROUP": run_id,
        "WANDB_JOB_TYPE": "sft",
        "WANDB_TAGS": "aider-v1,modal,8xh100,sft",
    }


@app.function(
    image=training_image,
    cpu=4.0,
    memory=32_768,
    timeout=7_200,
    volumes={MODELS_DIR: models, ASSETS_DIR: assets},
)
def smoke_runtime() -> dict[str, object]:
    """Verify the native image, source install, model, and Aider SFT package."""
    from importlib import metadata

    run("python3 -m pip install --no-deps -e .")
    run("python3 scripts/check_runtime.py")
    train_path = Path(ASSETS_DIR, "prepared", "sft", "train.jsonl")
    if not train_path.is_file():
        raise FileNotFoundError(train_path)
    if Path(MODELS_DIR, "GLM-4.7-Flash", "MODEL_REVISION").read_text(encoding="utf-8").strip() != MODEL_REVISION:
        raise RuntimeError("official model revision marker is missing or mismatched")
    report = {
        "status": "passed",
        "train_rows": sum(1 for _ in train_path.open(encoding="utf-8")),
        "packages": {
            package: metadata.version(package)
            for package in ("flashinfer-python", "flashinfer-cubin", "flashinfer-jit-cache", "sglang-kernel", "torch-memory-saver")
        },
    }
    Path(ASSETS_DIR, "prepared", "aider_v1_native_runtime_smoke_report.json").write_text(
        __import__("json").dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    assets.commit()
    return report


@app.function(
    image=training_image,
    gpu="H100!:8",
    cpu=48.0,
    memory=(262_144, 1_048_576),
    timeout=86_400,
    volumes={MODELS_DIR: models, ASSETS_DIR: assets, RUNS_DIR: runs},
    secrets=[modal.Secret.from_name("wandb-glm47")],
)
def run_sft(run_id: str = "") -> str:
    """Run the Aider-only SFT stage after smoke_runtime passes."""
    resolved_run_id = run_id or f"glm47-aider-v1-sft-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    try:
        run("python3 -m pip install --no-deps -e .")
        run("python3 scripts/check_runtime.py")
        run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
        run("bash examples/sft.sh", env=stage_env(resolved_run_id))
    finally:
        models.commit()
        assets.commit()
        runs.commit()
    return resolved_run_id


@app.local_entrypoint()
def smoke() -> None:
    print(smoke_runtime.remote())


@app.local_entrypoint()
def sft(run_id: str = "") -> None:
    print(run_sft.remote(run_id=run_id))
