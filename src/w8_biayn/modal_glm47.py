"""Pure shared contracts for GLM-4.7-Flash serving on Modal.

The benchmark-specific Modal lanes keep orchestration at their thin
``modal_app.py`` boundaries.  This module contains the immutable model/server
contract and deliberately imports neither Modal nor a benchmark harness.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence


MODEL_REPO = "zai-org/GLM-4.7-Flash"
SERVED_MODEL_NAME = "glm-4.7-flash"
TRANSFORMERS_REPO_URL = "https://github.com/huggingface/transformers.git"
TRANSFORMERS_COMMIT = "76732b4e7120808ff989edbd16401f61fa6a0afa"
MODAL_SDK_PIN = "1.5.2"
DEFAULT_MAX_TOKENS = 32_768
SGLANG_ADMISSION_MAX_TOKENS = 2_048
SGLANG_SCALEDOWN_WINDOW_SECONDS = 20 * 60
SGLANG_POST_GENERATION_WINDOW_SECONDS = 2
ARTIFACT_DOWNLOAD_CONCURRENCY = 16
SUPPORTED_GPU = "H100!:4"
REQUIRED_SGLANG_FLAGS = (
    "--model-path",
    "--tp-size",
    "--tool-call-parser",
    "--reasoning-parser",
    "--speculative-algorithm",
    "--speculative-num-steps",
    "--speculative-eagle-topk",
    "--speculative-num-draft-tokens",
    "--mem-fraction-static",
    "--max-running-requests",
    "--served-model-name",
    "--api-key",
    "--host",
    "--port",
)


class Glm47Config(Protocol):
    model_revision: str
    sglang_mem_fraction: float
    sglang_max_running_requests: int


class ModalGlm47Error(RuntimeError):
    """An immutable model cache or SGLang admission contract failed."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_model_snapshot(
    snapshot: str | Path,
    *,
    expected_revision: str,
    expected_repo: str = MODEL_REPO,
    minimum_weight_bytes: int = 1_000_000_000,
) -> dict[str, Any]:
    """Validate a HF snapshot, including every indexed weight shard."""

    root = Path(snapshot)
    required = [root / "config.json", root / "model.safetensors.index.json"]
    tokenizer_candidates = [
        root / "tokenizer.json",
        root / "tokenizer_config.json",
        root / "tokenizer.model",
    ]
    missing = [path.name for path in required if not path.is_file()]
    if not any(path.is_file() for path in tokenizer_candidates):
        missing.append("tokenizer material")
    if missing:
        raise ModalGlm47Error(f"model snapshot is incomplete; missing {missing}")
    try:
        index = json.loads((root / "model.safetensors.index.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ModalGlm47Error("model safetensors index is unreadable") from exc
    weight_map = index.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        raise ModalGlm47Error("model safetensors index has no weight_map")
    shard_names = sorted(set(weight_map.values()))
    if not all(isinstance(name, str) and Path(name).name == name for name in shard_names):
        raise ModalGlm47Error("model safetensors index contains unsafe shard names")
    absent = [name for name in shard_names if not (root / name).is_file()]
    if absent:
        raise ModalGlm47Error(f"model snapshot is missing indexed shards: {absent[:5]}")
    weight_bytes = sum((root / name).stat().st_size for name in shard_names)
    if weight_bytes < minimum_weight_bytes:
        raise ModalGlm47Error(
            f"model weight bytes are implausibly small: {weight_bytes} < {minimum_weight_bytes}"
        )
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        size = path.stat().st_size
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": size,
                "sha256": sha256_file(path) if size <= 64 * 1024 * 1024 else None,
            }
        )
    manifest = {
        "schema_version": 1,
        "model_repo": expected_repo,
        "model_revision": expected_revision,
        "weight_shards": shard_names,
        "weight_bytes": weight_bytes,
        "files": files,
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    return manifest


def sglang_server_command(
    config: Glm47Config,
    *,
    api_key: str,
    model_root: str = "/models",
) -> list[str]:
    model_path = f"{model_root}/zai-org--GLM-4.7-Flash/{config.model_revision}"
    return [
        "python",
        "-m",
        "sglang.launch_server",
        "--model-path",
        model_path,
        "--tp-size",
        "4",
        "--tool-call-parser",
        "glm47",
        "--reasoning-parser",
        "glm45",
        "--speculative-algorithm",
        "EAGLE",
        "--speculative-num-steps",
        "3",
        "--speculative-eagle-topk",
        "1",
        "--speculative-num-draft-tokens",
        "4",
        "--mem-fraction-static",
        str(config.sglang_mem_fraction),
        "--max-running-requests",
        str(config.sglang_max_running_requests),
        "--served-model-name",
        SERVED_MODEL_NAME,
        "--api-key",
        api_key,
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]


def validate_sglang_help(help_text: str) -> None:
    missing = [flag for flag in REQUIRED_SGLANG_FLAGS if flag not in help_text]
    if missing:
        raise ModalGlm47Error(f"pinned SGLang image is missing required flags: {missing}")


def summarize_sglang_admission(
    completion: Mapping[str, Any], *, requested_max_tokens: int
) -> dict[str, Any]:
    """Return response-shape diagnostics without generated text."""

    choices = completion.get("choices")
    choice = (
        choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    )
    message_value = choice.get("message")
    message = message_value if isinstance(message_value, dict) else {}
    content = message.get("content")
    reasoning = message.get("reasoning_content")
    usage_value = completion.get("usage")
    usage = (
        {
            str(key): value
            for key, value in usage_value.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        if isinstance(usage_value, dict)
        else {}
    )
    return {
        "requested_max_tokens": requested_max_tokens,
        "choices_count": len(choices) if isinstance(choices, list) else 0,
        "choice_keys": sorted(choice),
        "message_keys": sorted(message),
        "finish_reason": choice.get("finish_reason"),
        "content_present": isinstance(content, str) and bool(content.strip()),
        "content_chars": len(content) if isinstance(content, str) else 0,
        "reasoning_content_field_present": "reasoning_content" in message,
        "reasoning_content_present": isinstance(reasoning, str) and bool(reasoning.strip()),
        "reasoning_content_chars": len(reasoning) if isinstance(reasoning, str) else 0,
        "usage": usage,
    }


def validate_sglang_admission(summary: Mapping[str, Any]) -> None:
    missing = []
    if not summary.get("reasoning_content_field_present"):
        missing.append("reasoning_content field")
    if not summary.get("content_present"):
        missing.append("editable content")
    if missing:
        raise ModalGlm47Error(
            "SGLang admission response is missing "
            + " and ".join(missing)
            + f" (finish_reason={summary.get('finish_reason')!r})"
        )


def ensure_secret_free(value: Any, secrets: Sequence[str]) -> None:
    rendered = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    if any(secret and secret in rendered for secret in secrets):
        raise ModalGlm47Error("secret value appeared in printable or persisted content")
