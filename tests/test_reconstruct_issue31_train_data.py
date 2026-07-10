from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path("scripts/reconstruct_issue31_train_data.py")


def _module():
    spec = importlib.util.spec_from_file_location(
        "reconstruct_issue31_train_data_under_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample(label: str) -> dict:
    return {
        "prompt": [
            {"role": "system", "content": "Compile as C++20."},
            {"role": "user", "content": label},
        ],
        "metadata": {"label": label, "ordinal": int(label.split("-")[-1])},
        "ignored": "not serialized",
    }


def _fixture(tmp_path: Path, module, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    payloads = {
        f"sft_{index}.pt": {
            "rollout_id": index,
            "samples": [
                _sample(f"row-{index * module.EXPECTED_SAMPLES_PER_SHARD + offset}")
                for offset in range(module.EXPECTED_SAMPLES_PER_SHARD)
            ],
        }
        for index in range(4)
    }
    input_hashes = {}
    for index in range(4):
        name = f"sft_{index}.pt"
        path = input_dir / name
        path.write_bytes(f"fixture-shard-{index}".encode())
        input_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    rendered = b"".join(
        (
            json.dumps(
                {"messages": sample["prompt"], "metadata": sample["metadata"]},
                sort_keys=True,
            )
            + "\n"
        ).encode()
        for index in range(4)
        for sample in payloads[f"sft_{index}.pt"]["samples"]
    )
    monkeypatch.setattr(module, "INPUT_SHA256", input_hashes)
    monkeypatch.setattr(module, "OUTPUT_SHA256", hashlib.sha256(rendered).hexdigest())
    loaded: list[str] = []

    def loader(path: Path):
        loaded.append(path.name)
        return payloads[path.name]

    return input_dir, payloads, rendered, loaded, loader


def test_production_hashes_are_frozen_exactly() -> None:
    module = _module()

    assert module.INPUT_SHA256 == {
        "sft_0.pt": "99197988fe81e8e71f5589516a1a47e6d4369806d233e5f07315958130d57467",
        "sft_1.pt": "5f652d9148ad011d8743e79c04c9a8f38922aedc753bc782673d439848770a95",
        "sft_2.pt": "0e10eefe742b7d85287c4a59ee6be5e0c64e0ad667f56aa51c8c386d5400d2d4",
        "sft_3.pt": "7397d7dba38058c282895f328aec15ac38ba58cb5130e4f8695076ce5366f4d1",
    }
    assert (
        module.OUTPUT_SHA256 == "f1f5f70b1e77dbb6da51d075a35b2e48f784f4080873f356c9c4bd3c83a3d783"
    )
    assert module.EXPECTED_SAMPLES_PER_SHARD == 32


def test_reconstructs_in_index_order_with_exact_serialization_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    input_dir, _, rendered, loaded, loader = _fixture(tmp_path, module, monkeypatch)
    output = tmp_path / "out/train.jsonl"
    manifest_path = tmp_path / "out/manifest.json"

    manifest = module.reconstruct(
        input_dir,
        output,
        manifest_path,
        loader=loader,
    )

    assert loaded == ["sft_0.pt", "sft_1.pt", "sft_2.pt", "sft_3.pt"]
    assert output.read_bytes() == rendered
    assert hashlib.sha256(output.read_bytes()).hexdigest() == module.OUTPUT_SHA256
    assert manifest["output"]["row_count"] == 128
    assert [row["rollout_id"] for row in manifest["inputs"]] == [0, 1, 2, 3]
    assert [row["row_count"] for row in manifest["inputs"]] == [32, 32, 32, 32]
    assert all(row["post_load_hash_verified"] for row in manifest["inputs"])
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert not list(output.parent.glob(".*.tmp"))


def test_all_input_hashes_are_checked_before_any_shard_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    input_dir, _, _, loaded, loader = _fixture(tmp_path, module, monkeypatch)
    (input_dir / "sft_3.pt").write_bytes(b"tampered")
    output = tmp_path / "train.jsonl"
    output.write_bytes(b"existing-output")
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(b"existing-manifest")

    with pytest.raises(module.ReconstructionFailure, match="Input hash mismatch"):
        module.reconstruct(input_dir, output, manifest, loader=loader)

    assert loaded == []
    assert output.read_bytes() == b"existing-output"
    assert manifest.read_bytes() == b"existing-manifest"


def test_invalid_sample_structure_does_not_replace_existing_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    input_dir, payloads, _, _, loader = _fixture(tmp_path, module, monkeypatch)
    payloads["sft_2.pt"]["samples"][0] = {
        "prompt": "not-a-list",
        "metadata": {},
    }
    output = tmp_path / "train.jsonl"
    output.write_bytes(b"old-output")
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(b"old-manifest")

    with pytest.raises(module.ReconstructionFailure, match="prompt"):
        module.reconstruct(input_dir, output, manifest, loader=loader)

    assert output.read_bytes() == b"old-output"
    assert manifest.read_bytes() == b"old-manifest"


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("wrong-rollout-id", "rollout_id_mismatch"),
        ("missing-rollout-id", "invalid_shard_structure"),
        ("missing-samples", "invalid_shard_structure"),
        ("extra-wrapper-key", "invalid_shard_structure"),
    ],
)
def test_requires_exact_rollout_wrapper_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_code: str,
) -> None:
    module = _module()
    input_dir, payloads, _, _, loader = _fixture(tmp_path, module, monkeypatch)
    target = payloads["sft_1.pt"]
    if case == "wrong-rollout-id":
        target["rollout_id"] = 9
    elif case == "missing-rollout-id":
        target.pop("rollout_id")
    elif case == "missing-samples":
        target.pop("samples")
    else:
        target["unexpected"] = True

    with pytest.raises(module.ReconstructionFailure) as raised:
        module.reconstruct(
            input_dir,
            tmp_path / "train.jsonl",
            tmp_path / "manifest.json",
            loader=loader,
        )

    assert raised.value.code == expected_code
    assert not (tmp_path / "train.jsonl").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_rechecks_shard_hash_immediately_after_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    input_dir, _, _, loaded, base_loader = _fixture(tmp_path, module, monkeypatch)

    def swapping_loader(path: Path):
        payload = base_loader(path)
        if path.name == "sft_1.pt":
            path.write_bytes(b"post-verification-swap")
        return payload

    with pytest.raises(module.ReconstructionFailure) as raised:
        module.reconstruct(
            input_dir,
            tmp_path / "train.jsonl",
            tmp_path / "manifest.json",
            loader=swapping_loader,
        )

    assert raised.value.code == "input_changed_during_load"
    assert loaded == ["sft_0.pt", "sft_1.pt"]
    assert not (tmp_path / "train.jsonl").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_output_hash_mismatch_installs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    input_dir, _, _, _, loader = _fixture(tmp_path, module, monkeypatch)
    monkeypatch.setattr(module, "OUTPUT_SHA256", "0" * 64)
    output = tmp_path / "train.jsonl"
    manifest = tmp_path / "manifest.json"

    with pytest.raises(module.ReconstructionFailure, match="frozen SHA-256"):
        module.reconstruct(input_dir, output, manifest, loader=loader)

    assert not output.exists()
    assert not manifest.exists()
