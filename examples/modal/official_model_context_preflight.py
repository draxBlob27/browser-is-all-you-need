"""Bootstrap the official GLM checkpoint and preflight packaged SFT context."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import modal


MODEL_ID = "zai-org/GLM-4.7-Flash"
MODEL_REVISION = "7dd20894a642a0aa287e9827cb1a1f7f91386b67"
MILES_IMAGE = (
    "radixark/miles:latest-cu12@"
    "sha256:efc8027fc47aaa9687dc4f1046093ed4e2f9789e52a932fcefb7031402aeff37"
)
MODELS_DIR = "/root/models"
ASSETS_DIR = "/workspace/assets"
MODEL_DIR = f"{MODELS_DIR}/GLM-4.7-Flash"

app = modal.App("glm47-pie-cpp-official-context-preflight")
models = modal.Volume.from_name("glm47-models", create_if_missing=True)
assets = modal.Volume.from_name("glm47-assets", create_if_missing=False)
bootstrap_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "huggingface-hub[hf-transfer]==1.23.0"
)
preflight_image = modal.Image.from_registry(MILES_IMAGE)


@app.function(
    image=bootstrap_image,
    cpu=4.0,
    memory=16_384,
    timeout=14_400,
    volumes={MODELS_DIR: models},
)
def bootstrap_official_model() -> str:
    """Download the pinned upstream model snapshot to the persistent Volume."""
    from huggingface_hub import HfApi, snapshot_download

    resolved = HfApi().model_info(MODEL_ID, revision=MODEL_REVISION).sha
    if resolved != MODEL_REVISION:
        raise RuntimeError(f"model revision mismatch: {resolved} != {MODEL_REVISION}")
    target = Path(MODEL_DIR)
    snapshot_download(repo_id=MODEL_ID, revision=MODEL_REVISION, local_dir=target)
    target.joinpath("MODEL_REVISION").write_text(f"{MODEL_REVISION}\n", encoding="utf-8")
    models.commit()
    return str(target)


@app.function(
    image=preflight_image,
    cpu=4.0,
    memory=16_384,
    timeout=7_200,
    volumes={MODELS_DIR: models, ASSETS_DIR: assets},
)
def run() -> dict[str, object]:
    """Verify every packaged row against the official training checkpoint tokenizer."""
    from transformers import AutoTokenizer

    prepared_dir = Path(ASSETS_DIR, "prepared")
    manifest = json.loads(prepared_dir.joinpath("manifest.json").read_text(encoding="utf-8"))
    if Path(MODEL_DIR, "MODEL_REVISION").read_text(encoding="utf-8").strip() != MODEL_REVISION:
        raise RuntimeError("official model revision marker is missing or mismatched")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True, fix_mistral_regex=True)
    template_sha256 = hashlib.sha256(Path(MODEL_DIR, "chat_template.jinja").read_bytes()).hexdigest()
    max_tokens = int(manifest["training"]["sequence_length"])
    overlength: list[dict[str, object]] = []
    token_counts: list[int] = []
    train_path = prepared_dir / manifest["files"]["sft_train"]
    for line_number, line in enumerate(train_path.read_text(encoding="utf-8").splitlines(), start=1):
        row = json.loads(line)
        token_count = len(tokenizer.apply_chat_template(row["messages"], tokenize=True, add_generation_prompt=False))
        token_counts.append(token_count)
        if token_count > max_tokens:
            overlength.append({"task_id": row["task_id"], "line": line_number, "token_count": token_count})
    report = {
        "schema_version": 1,
        "status": "passed" if not overlength else "failed",
        "cpu_only": True,
        "input": str(train_path),
        "row_count": len(token_counts),
        "sequence_length": max_tokens,
        "max_rendered_tokens": max(token_counts, default=0),
        "overlength_rows": overlength,
        "tokenizer": {
            "path": MODEL_DIR,
            "repository": MODEL_ID,
            "revision": MODEL_REVISION,
            "load_kwargs": {"fix_mistral_regex": True},
            "chat_template_sha256": template_sha256,
        },
        "rendering": {"add_generation_prompt": False},
    }
    prepared_dir.joinpath("official_context_preflight_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    assets.commit()
    if overlength:
        raise RuntimeError(f"{len(overlength)} prepared SFT rows exceed {max_tokens} tokens")
    return report


@app.local_entrypoint()
def bootstrap_model() -> None:
    print(bootstrap_official_model.remote())


@app.local_entrypoint()
def preflight_context() -> None:
    print(run.remote())
