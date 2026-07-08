"""Run Miles' HF->torch_dist converter with the GLM-4.7 bridge registered.

Stock mbridge/megatron-bridge cannot map Glm4MoeLite; the converter needs the
same lazy bridge hooks the trainer uses. Mirror of miles_train_with_glm47_bridge.

The current Miles converter also repurposes pipeline parallelism for conversion
speed: when launched with PP=1 on multiple ranks it silently overrides
PP := world_size, which makes an exact-training-layout conversion (TP4/PP1/EP8
on 8 GPUs) fail Megatron's world-size divisibility check (TP4 x PP8 = 32 > 8).
W8_CONVERT_KEEP_PP1=1 disables that override via an anchored source patch so
the checkpoint is written in the exact layout training will load — dist-ckpt
resharding at load is the seam that produced extra_state corruption in the
sibling SLIME lane, and we do not want to depend on it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from w8_biayn.integrations.miles_glm47_bridge import register_glm47_bridge

PP_OVERRIDE_MARKER = "if args.pipeline_model_parallel_size == 1 and world_size > 1:"
PP_OVERRIDE_REPLACEMENT = (
    "if False:  # w8: keep requested PP1; do not repurpose PP for conversion parallelism"
)


def _convert_py_path() -> Path:
    configured = os.environ.get("MILES_CONVERT_PY", "").strip()
    if configured:
        return Path(configured)
    default = Path("/root/miles/tools/convert_hf_to_torch_dist.py")
    if default.exists():
        return default
    return Path.cwd() / "tools" / "convert_hf_to_torch_dist.py"


def _load_source(convert_py: Path) -> str:
    source = convert_py.read_text(encoding="utf-8")
    if os.environ.get("W8_CONVERT_KEEP_PP1", "0") != "1":
        return source
    if PP_OVERRIDE_MARKER not in source:
        raise RuntimeError(
            f"W8_CONVERT_KEEP_PP1=1 but the PP-override marker is missing in {convert_py}; "
            "inspect the converter before forcing PP1"
        )
    return source.replace(PP_OVERRIDE_MARKER, PP_OVERRIDE_REPLACEMENT, 1)


def main() -> None:
    convert_py = _convert_py_path()
    register_glm47_bridge()
    source = _load_source(convert_py)
    sys.argv[0] = str(convert_py)
    globals_ns = {"__name__": "__main__", "__file__": str(convert_py), "__builtins__": __builtins__}
    exec(compile(source, str(convert_py), "exec"), globals_ns)  # noqa: S102 - trusted in-image tool source


if __name__ == "__main__":
    main()
