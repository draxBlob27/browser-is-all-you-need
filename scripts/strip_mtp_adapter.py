"""Copy a PEFT adapter, dropping MTP tensors SGLang cannot serve.

The Miles trainer saves LoRA adapters that include the MTP head's tensors
(GLM-4.7-Flash layer 47). SGLang serves layers 0-46 only, so a disk load of
the raw adapter fails with an index-out-of-range. Usage:

    python scripts/strip_mtp_adapter.py <trainer_adapter_dir> <serve_dir>
    python scripts/strip_mtp_adapter.py --include-native <trainer_adapter_dir> <hybrid_dir>
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


_LAYER_PATTERN = re.compile(r"\.layers\.(\d+)\.")


def filter_served_layers(state_dict: dict[str, Any], *, num_layers: int) -> tuple[dict[str, Any], list[str]]:
    dropped = []
    kept = {}
    for key, value in state_dict.items():
        match = _LAYER_PATTERN.search(key)
        if match and int(match.group(1)) >= num_layers:
            dropped.append(key)
        else:
            kept[key] = value
    return kept, dropped


def copy_native_state(src: Path, dst: Path) -> list[Path]:
    copied = []
    for pattern in ("adapter_megatron_tp*_pp*.pt", "training_state_rank*.pt"):
        for source in sorted(src.glob(pattern)):
            target = dst / source.name
            shutil.copy2(source, target)
            copied.append(target)
    return copied


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--num-layers", type=int, default=47)
    parser.add_argument("--include-native", action="store_true")
    args = parser.parse_args(argv)

    import torch

    src = Path(args.src).resolve()
    dst = Path(args.dst).resolve()
    if src == dst:
        raise SystemExit("source and destination adapter directories must differ")
    dst.mkdir(parents=True, exist_ok=True)

    source_model = src / "adapter_model.bin"
    output_model = dst / "adapter_model.bin"
    state_dict = torch.load(source_model, map_location="cpu", weights_only=True)
    kept, dropped = filter_served_layers(state_dict, num_layers=args.num_layers)
    torch.save(kept, output_model)
    shutil.copy2(src / "adapter_config.json", dst / "adapter_config.json")
    native_files = copy_native_state(src, dst) if args.include_native else []

    manifest = {
        "source": str(src),
        "num_layers": args.num_layers,
        "source_tensor_count": len(state_dict),
        "kept_tensor_count": len(kept),
        "stripped_tensor_count": len(dropped),
        "first_stripped_tensor": dropped[0] if dropped else None,
        "source_adapter_model_sha256": _sha256(source_model),
        "output_adapter_model_sha256": _sha256(output_model),
        "native_files": {path.name: _sha256(path) for path in native_files},
    }
    (dst / "mtp_strip_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"kept {len(kept)}/{len(state_dict)} tensors (stripped {len(dropped)} MTP tensors)")
    print("HYBRID_ADAPTER_READY" if args.include_native else "SERVE_COPY_READY", dst)


if __name__ == "__main__":
    main()
