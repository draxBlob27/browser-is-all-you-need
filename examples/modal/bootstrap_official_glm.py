"""CPU-only bootstrap of the pinned official GLM-4.7-Flash checkpoint."""

from __future__ import annotations

from pathlib import Path

import modal


MODEL_ID = "zai-org/GLM-4.7-Flash"
MODEL_REVISION = "7dd20894a642a0aa287e9827cb1a1f7f91386b67"
MODELS_DIR = "/root/models"
MODEL_DIR = f"{MODELS_DIR}/GLM-4.7-Flash"

app = modal.App("glm47-official-model-bootstrap")
models = modal.Volume.from_name("glm47-models", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "huggingface-hub[hf-transfer]==1.23.0"
)


@app.function(
    image=image,
    cpu=4.0,
    memory=16_384,
    timeout=14_400,
    volumes={MODELS_DIR: models},
)
def run() -> str:
    from huggingface_hub import HfApi, snapshot_download

    resolved = HfApi().model_info(MODEL_ID, revision=MODEL_REVISION).sha
    if resolved != MODEL_REVISION:
        raise RuntimeError(f"model revision mismatch: {resolved} != {MODEL_REVISION}")
    target = Path(MODEL_DIR)
    snapshot_download(repo_id=MODEL_ID, revision=MODEL_REVISION, local_dir=target)
    target.joinpath("MODEL_REVISION").write_text(f"{MODEL_REVISION}\n", encoding="utf-8")
    models.commit()
    return str(target)


@app.local_entrypoint()
def bootstrap_model() -> None:
    print(run.remote())
