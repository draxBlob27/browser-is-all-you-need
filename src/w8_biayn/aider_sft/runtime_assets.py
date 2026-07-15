"""Pinned local runtime assets required before an Aider SFT profile can freeze."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from .config import GLM_REPOSITORY, GLM_REVISION
from .errors import AiderSftError
from .util import atomic_write, sha256_bytes, sha256_file, validate_regular_file, write_json

MOBY_SECCOMP_PROFILE_VERSION = "seccomp/v0.2.1"
MOBY_SECCOMP_PROFILE_URL = (
    "https://raw.githubusercontent.com/moby/profiles/refs/tags/seccomp/v0.2.1/seccomp/default.json"
)
MOBY_SECCOMP_PROFILE_SHA256 = "536529b665dd0972c37bfb569f5d4ac8a53592e7b00752bc39ff063ca9864c74"
TOKENIZER_SNAPSHOT_FILES = (
    "chat_template.jinja",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
)


def prepare_seccomp_profile(*, output_path: Path) -> dict[str, Any]:
    """Download one exact official Moby profile and verify it before writing."""

    if output_path.is_symlink():
        raise AiderSftError("unsafe_path", f"seccomp output is a symlink: {output_path}")
    if output_path.is_file():
        observed = sha256_file(output_path)
        if observed != MOBY_SECCOMP_PROFILE_SHA256:
            raise AiderSftError(
                "sandbox_policy_mismatch",
                f"existing seccomp profile hash differs: {output_path}",
            )
        return {
            "output": str(output_path.resolve()),
            "sha256": observed,
            "bytes": output_path.stat().st_size,
            "source": MOBY_SECCOMP_PROFILE_URL,
            "version": MOBY_SECCOMP_PROFILE_VERSION,
            "reused": True,
        }
    try:
        with urllib.request.urlopen(MOBY_SECCOMP_PROFILE_URL, timeout=30) as response:
            payload = response.read()
    except OSError as exc:
        raise AiderSftError(
            "sandbox_policy_mismatch",
            f"cannot download pinned seccomp profile: {exc}",
        ) from exc
    observed = sha256_bytes(payload)
    if observed != MOBY_SECCOMP_PROFILE_SHA256:
        raise AiderSftError(
            "sandbox_policy_mismatch",
            "downloaded seccomp profile hash differs from the repository pin",
        )
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AiderSftError("sandbox_policy_mismatch", "seccomp profile is not JSON") from exc
    if not isinstance(decoded, dict) or not isinstance(decoded.get("syscalls"), list):
        raise AiderSftError("sandbox_policy_mismatch", "seccomp profile schema differs")
    atomic_write(output_path, payload)
    return {
        "output": str(output_path.resolve()),
        "sha256": observed,
        "bytes": len(payload),
        "source": MOBY_SECCOMP_PROFILE_URL,
        "version": MOBY_SECCOMP_PROFILE_VERSION,
        "reused": False,
    }


def prepare_tokenizer_snapshot(*, output_root: Path) -> dict[str, Any]:
    """Download only the exact tokenizer files; never fetch model weight shards."""

    if output_root.is_symlink():
        raise AiderSftError("unsafe_path", f"tokenizer output is a symlink: {output_root}")
    marker = {
        "repository": GLM_REPOSITORY,
        "revision": GLM_REVISION,
        "schema_version": "w8-aider-sft-model-snapshot-v1",
    }
    marker_path = output_root / ".w8-aider-sft-model.json"
    if marker_path.is_file():
        try:
            existing = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AiderSftError("consumer_model_revision_mismatch", str(exc)) from exc
        if existing != marker:
            raise AiderSftError(
                "consumer_model_revision_mismatch",
                "existing tokenizer marker belongs to another model revision",
            )
    output_root.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=GLM_REPOSITORY,
            revision=GLM_REVISION,
            local_dir=str(output_root),
            allow_patterns=list(TOKENIZER_SNAPSHOT_FILES),
        )
    except Exception as exc:  # noqa: BLE001 - normalize downloader failures
        raise AiderSftError(
            "consumer_tokenizer_mismatch",
            f"cannot download pinned tokenizer snapshot: {type(exc).__name__}: {exc}",
        ) from exc
    files: dict[str, dict[str, Any]] = {}
    for relative in TOKENIZER_SNAPSHOT_FILES:
        path = output_root / relative
        if not path.is_file():
            raise AiderSftError(
                "consumer_tokenizer_mismatch",
                f"pinned tokenizer file is missing: {relative}",
            )
        validate_regular_file(path, root=output_root)
        files[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    if any(output_root.glob("*.safetensors")):
        raise AiderSftError(
            "consumer_tokenizer_mismatch",
            "tokenizer-only snapshot unexpectedly contains model weights",
        )
    try:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            str(output_root),
            local_files_only=True,
            trust_remote_code=False,
            fix_mistral_regex=True,
        )
    except Exception as exc:  # noqa: BLE001 - normalize local tokenizer failures
        raise AiderSftError(
            "consumer_tokenizer_mismatch",
            f"cannot load pinned tokenizer snapshot: {type(exc).__name__}: {exc}",
        ) from exc
    template = getattr(tokenizer, "chat_template", None)
    if not isinstance(template, str):
        raise AiderSftError("consumer_tokenizer_mismatch", "tokenizer lacks chat_template")
    chat_template_sha256 = sha256_bytes(template.encode("utf-8"))
    write_json(marker_path, marker)
    write_json(
        output_root / "w8-aider-sft-tokenizer-manifest.json",
        {
            "schema_version": "w8-aider-sft-tokenizer-snapshot-v1",
            "repository": GLM_REPOSITORY,
            "revision": GLM_REVISION,
            "chat_template_sha256": chat_template_sha256,
            "load_kwargs": {"fix_mistral_regex": True},
            "files": files,
            "weights_included": False,
        },
    )
    return {
        "output": str(output_root.resolve()),
        "repository": GLM_REPOSITORY,
        "revision": GLM_REVISION,
        "chat_template_sha256": chat_template_sha256,
        "files": len(files),
        "weights_included": False,
    }
