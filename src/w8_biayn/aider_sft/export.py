"""Private-asset-free internal SLIME bundle export and consumer verification."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .config import GLM_REPOSITORY, GLM_REVISION, MASK_ADAPTER, profile_contract
from .errors import AiderSftError
from .receipts import _verify_rows_and_tokens, verify_ready_bundle
from .tokenization import load_locked_tokenizer
from .util import (
    manifest_entries,
    read_json,
    sha256_file,
    verify_manifest_entries,
    write_json,
)

ALLOWED_EXPORT_FILES = {
    "DATASET_CARD.md",
    "NOTICE",
    "licenses.json",
    "readiness.json",
    "consumer-lock.json",
    "sft/train.jsonl",
    "sft/token-records.jsonl",
}


def export_slime_bundle(
    *,
    source_root: Path,
    output_root: Path,
    verify_tokenizer: bool = True,
) -> dict[str, Any]:
    verify_ready_bundle(source_root, require_tokenizer=verify_tokenizer)
    if output_root.exists() and any(output_root.iterdir()):
        raise AiderSftError(
            "consumer_export_manifest_mismatch", f"export root is not empty: {output_root}"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    mapping = {
        "DATASET_CARD.md": "DATASET_CARD.md",
        "NOTICE": "NOTICE",
        "licenses.json": "licenses.json",
        "readiness.json": "readiness.json",
        "consumer-lock.json": "consumer-lock.json",
        "sft/train.jsonl": "sft/train.jsonl",
        "sft/token-records.jsonl": "sft/token-records.jsonl",
    }
    for source_relative, destination_relative in mapping.items():
        destination = output_root / destination_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / source_relative, destination)
        destination.chmod(0o444)
    source_readiness = read_json(source_root / "readiness.json")
    export_manifest = {
        "schema_version": "aider-sft-slime-export-manifest-v1",
        "audience": "slime-sft",
        "distribution_scope": "internal_research",
        "source": {
            "dataset_id": source_readiness["dataset_id"],
            "readiness_sha256": sha256_file(source_root / "readiness.json"),
            "manifest_sha256": source_readiness["bindings"]["manifest_sha256"],
        },
        "entries": manifest_entries(output_root, exclude={"manifest.json"}),
        "private_assets_included": False,
    }
    write_json(output_root / "manifest.json", export_manifest)
    return verify_export_bundle(output_root, require_tokenizer=verify_tokenizer)


def verify_export_bundle(
    root: Path,
    *,
    require_tokenizer: bool = True,
) -> dict[str, Any]:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise AiderSftError("consumer_export_manifest_mismatch", "export manifest is missing")
    manifest = read_json(manifest_path)
    if (
        manifest.get("schema_version") != "aider-sft-slime-export-manifest-v1"
        or manifest.get("audience") != "slime-sft"
        or manifest.get("distribution_scope") != "internal_research"
        or manifest.get("private_assets_included") is not False
    ):
        raise AiderSftError("consumer_export_manifest_mismatch", "export policy differs")
    observed = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if observed != ALLOWED_EXPORT_FILES | {"manifest.json"}:
        raise AiderSftError(
            "consumer_export_manifest_mismatch",
            f"export contains missing/private files: {sorted(observed ^ (ALLOWED_EXPORT_FILES | {'manifest.json'}))}",
        )
    verify_manifest_entries(root, manifest["entries"], exclude={"manifest.json"})
    readiness = read_json(root / "readiness.json")
    if readiness.get("status") != "ready" or readiness.get("schema_version") != 2:
        raise AiderSftError("consumer_readiness_missing", "source readiness is absent or invalid")
    if sha256_file(root / "readiness.json") != manifest["source"]["readiness_sha256"]:
        raise AiderSftError("consumer_export_manifest_mismatch", "source readiness hash differs")
    if manifest["source"].get("dataset_id") != readiness.get("dataset_id"):
        raise AiderSftError("consumer_export_manifest_mismatch", "source dataset identity differs")
    if manifest["source"].get("manifest_sha256") != readiness.get("bindings", {}).get(
        "manifest_sha256"
    ):
        raise AiderSftError("consumer_export_manifest_mismatch", "source manifest chain differs")
    consumer_lock = read_json(root / "consumer-lock.json")
    exact_identity = {"repository": GLM_REPOSITORY, "revision": GLM_REVISION}
    if consumer_lock.get("model") != exact_identity:
        raise AiderSftError("consumer_model_revision_mismatch", "model identity differs")
    tokenizer_identity = consumer_lock.get("tokenizer", {})
    if {
        "repository": tokenizer_identity.get("repository"),
        "revision": tokenizer_identity.get("revision"),
    } != exact_identity:
        raise AiderSftError("consumer_tokenizer_mismatch", "tokenizer identity differs")
    if (
        consumer_lock.get("message_mode") != "raw_messages"
        or consumer_lock.get("dataset_apply_chat_template") is not False
    ):
        raise AiderSftError("consumer_raw_messages_required", "consumer lock permits templating")
    if consumer_lock.get("adapter") != MASK_ADAPTER:
        raise AiderSftError("consumer_adapter_mismatch", "consumer adapter differs")
    if consumer_lock.get("loss_mask_type") != "qwen":
        raise AiderSftError("consumer_loss_mask_mismatch", "consumer loss mask differs")
    if consumer_lock.get("sequence_length") != 4096:
        raise AiderSftError("consumer_sequence_length_mismatch", "consumer sequence differs")
    if consumer_lock.get("apply_chat_template_kwargs") != {"enable_thinking": False}:
        raise AiderSftError("consumer_template_policy_mismatch", "template kwargs differ")
    if (
        consumer_lock.get("rollout_function") != "w8_biayn.aider_sft.handoff.generate_sft_rollout"
        or consumer_lock.get("input_key") != "messages"
        or consumer_lock.get("metadata_key") != "metadata"
        or consumer_lock.get("loss_type") != "sft_loss"
    ):
        raise AiderSftError("consumer_adapter_mismatch", "consumer handoff contract differs")
    tokenizer = load_locked_tokenizer(consumer_lock) if require_tokenizer else None
    contract = profile_contract(str(readiness.get("dataset_profile")))
    _verify_rows_and_tokens(
        root,
        tokenizer=tokenizer,
        consumer_lock=consumer_lock,
        expected_train_rows=contract.total_targets["train"],
    )
    return {
        "root": str(root),
        "status": "verified",
        "dataset_id": readiness["dataset_id"],
        "train_rows": readiness["counts"]["train_rows"],
        "manifest_sha256": sha256_file(manifest_path),
    }
