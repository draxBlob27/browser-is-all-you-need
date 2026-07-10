#!/usr/bin/env python3
"""Reconstruct the frozen issue-31 SFT JSONL from four preserved rollout shards."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


MANIFEST_SCHEMA = "issue31-train-data-reconstruction/v1"
EXPECTED_SAMPLES_PER_SHARD = 32
INPUT_SHA256 = {
    "sft_0.pt": "99197988fe81e8e71f5589516a1a47e6d4369806d233e5f07315958130d57467",
    "sft_1.pt": "5f652d9148ad011d8743e79c04c9a8f38922aedc753bc782673d439848770a95",
    "sft_2.pt": "0e10eefe742b7d85287c4a59ee6be5e0c64e0ad667f56aa51c8c386d5400d2d4",
    "sft_3.pt": "7397d7dba38058c282895f328aec15ac38ba58cb5130e4f8695076ce5366f4d1",
}
OUTPUT_SHA256 = "f1f5f70b1e77dbb6da51d075a35b2e48f784f4080873f356c9c4bd3c83a3d783"


class ReconstructionFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    manifest = (
        Path(args.manifest).resolve()
        if args.manifest
        else output.with_name(output.name + ".manifest.json")
    )
    try:
        result = reconstruct(
            Path(args.input_dir).resolve(),
            output,
            manifest,
        )
    except ReconstructionFailure as exc:
        _emit(
            {
                "schema": MANIFEST_SCHEMA,
                "status": "ERROR",
                "error": exc.code,
                "message": exc.message,
            }
        )
        return 2
    except Exception:
        _emit(
            {
                "schema": MANIFEST_SCHEMA,
                "status": "ERROR",
                "error": "reconstruction_failed",
                "message": "Train-data reconstruction failed",
            }
        )
        return 3
    _emit(result)
    return 0


def reconstruct(
    input_dir: Path,
    output_path: Path,
    manifest_path: Path,
    *,
    loader: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    shard_paths = [input_dir / f"sft_{index}.pt" for index in range(4)]
    destinations = {output_path.resolve(), manifest_path.resolve()}
    if len(destinations) != 2 or destinations & {path.resolve() for path in shard_paths}:
        raise ReconstructionFailure(
            "path_collision", "Output and manifest paths must be distinct from all inputs"
        )
    input_records = []
    for index, path in enumerate(shard_paths):
        actual_sha, size = _verified_file_digest(path)
        expected_sha = INPUT_SHA256[path.name]
        if actual_sha != expected_sha:
            raise ReconstructionFailure(
                "input_hash_mismatch", f"Input hash mismatch for {path.name}"
            )
        input_records.append(
            {
                "index": index,
                "path": str(path.resolve()),
                "sha256": actual_sha,
                "size_bytes": size,
            }
        )

    shard_loader = loader or _load_torch_shard
    rows: list[bytes] = []
    row_counts: list[int] = []
    for index, path in enumerate(shard_paths):
        try:
            payload = shard_loader(path)
        except ReconstructionFailure:
            raise
        except Exception as exc:
            raise ReconstructionFailure(
                "shard_load_failed", f"Could not load sft_{index}.pt"
            ) from exc
        post_load_sha, post_load_size = _verified_file_digest(path)
        if (
            post_load_sha != input_records[index]["sha256"]
            or post_load_size != input_records[index]["size_bytes"]
        ):
            raise ReconstructionFailure(
                "input_changed_during_load",
                f"{path.name} changed while its verified payload was loading",
            )
        if type(payload) is not dict or set(payload) != {"rollout_id", "samples"}:
            raise ReconstructionFailure(
                "invalid_shard_structure",
                f"sft_{index}.pt must contain exactly rollout_id and samples",
            )
        rollout_id = payload["rollout_id"]
        if isinstance(rollout_id, bool) or not isinstance(rollout_id, int):
            raise ReconstructionFailure(
                "invalid_rollout_id", f"sft_{index}.pt rollout_id must be an integer"
            )
        if rollout_id != index:
            raise ReconstructionFailure(
                "rollout_id_mismatch",
                f"sft_{index}.pt rollout_id does not match its shard index",
            )
        samples = payload["samples"]
        if type(samples) is not list:
            raise ReconstructionFailure(
                "invalid_shard_structure", f"sft_{index}.pt samples must be a list"
            )
        if len(samples) != EXPECTED_SAMPLES_PER_SHARD:
            raise ReconstructionFailure(
                "sample_count_mismatch",
                f"sft_{index}.pt must contain exactly {EXPECTED_SAMPLES_PER_SHARD} samples",
            )
        shard_count = 0
        for sample_index, sample in enumerate(samples):
            _validate_sample(sample, shard_index=index, sample_index=sample_index)
            row = {"messages": sample["prompt"], "metadata": sample["metadata"]}
            try:
                rendered = json.dumps(row, sort_keys=True) + "\n"
            except (TypeError, ValueError) as exc:
                raise ReconstructionFailure(
                    "sample_not_json_serializable",
                    f"Sample {sample_index} in sft_{index}.pt is not JSON serializable",
                ) from exc
            rows.append(rendered.encode("utf-8"))
            shard_count += 1
        row_counts.append(shard_count)
        input_records[index]["rollout_id"] = rollout_id
        input_records[index]["row_count"] = shard_count
        input_records[index]["post_load_hash_verified"] = True

    output_bytes = b"".join(rows)
    output_sha = hashlib.sha256(output_bytes).hexdigest()
    if output_sha != OUTPUT_SHA256:
        raise ReconstructionFailure(
            "output_hash_mismatch", "Reconstructed output does not match frozen SHA-256"
        )
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "status": "RECONSTRUCTED",
        "inputs": input_records,
        "serialization": 'json.dumps({"messages": sample["prompt"], '
        '"metadata": sample["metadata"]}, sort_keys=True) + "\\n"',
        "output": {
            "path": str(output_path.resolve()),
            "sha256": output_sha,
            "size_bytes": len(output_bytes),
            "row_count": sum(row_counts),
        },
    }
    _install_atomically(output_path, output_bytes)
    _install_atomically(
        manifest_path,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return manifest


def _load_torch_shard(path: Path) -> Any:
    try:
        import torch
    except ImportError as exc:
        raise ReconstructionFailure(
            "torch_unavailable", "PyTorch is required to load preserved shards"
        ) from exc
    return torch.load(path, map_location="cpu", weights_only=False)


def _validate_sample(sample: Any, *, shard_index: int, sample_index: int) -> None:
    location = f"sft_{shard_index}.pt sample {sample_index}"
    if not isinstance(sample, Mapping):
        raise ReconstructionFailure("invalid_sample_structure", f"{location} is not a mapping")
    prompt = sample.get("prompt")
    metadata = sample.get("metadata")
    if not isinstance(prompt, list) or not prompt:
        raise ReconstructionFailure(
            "invalid_sample_structure", f"{location} prompt is not a non-empty list"
        )
    for message_index, message in enumerate(prompt):
        if not isinstance(message, Mapping):
            raise ReconstructionFailure(
                "invalid_sample_structure",
                f"{location} message {message_index} is not a mapping",
            )
        if not isinstance(message.get("role"), str) or not message["role"]:
            raise ReconstructionFailure(
                "invalid_sample_structure",
                f"{location} message {message_index} has no role",
            )
        if "content" not in message or not isinstance(message["content"], str):
            raise ReconstructionFailure(
                "invalid_sample_structure",
                f"{location} message {message_index} has invalid content",
            )
    if not isinstance(metadata, Mapping):
        raise ReconstructionFailure(
            "invalid_sample_structure", f"{location} metadata is not a mapping"
        )


def _verified_file_digest(path: Path) -> tuple[str, int]:
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ReconstructionFailure("invalid_input_file", f"{path.name} is not a file")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except ReconstructionFailure:
        raise
    except OSError as exc:
        raise ReconstructionFailure("input_unavailable", f"Could not read {path.name}") from exc
    return digest.hexdigest(), metadata.st_size


def _install_atomically(path: Path, content: bytes) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(temporary, flags, 0o644)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise ReconstructionFailure("atomic_write_failed", f"Could not write {path.name}") from exc


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _emit(payload: Mapping[str, Any]) -> None:
    print(
        json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":")),
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
