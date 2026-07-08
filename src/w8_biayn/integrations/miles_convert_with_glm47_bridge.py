"""Run Miles' HF->torch_dist converter with the GLM-4.7 bridge registered.

Stock mbridge/megatron-bridge cannot map Glm4MoeLite; the converter needs the
same lazy bridge hooks the trainer uses. Mirror of miles_train_with_glm47_bridge.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

from w8_biayn.integrations.miles_glm47_bridge import register_glm47_bridge


def _convert_py_path() -> Path:
    configured = os.environ.get("MILES_CONVERT_PY", "").strip()
    if configured:
        return Path(configured)
    default = Path("/root/miles/tools/convert_hf_to_torch_dist.py")
    if default.exists():
        return default
    return Path.cwd() / "tools" / "convert_hf_to_torch_dist.py"


def main() -> None:
    convert_py = _convert_py_path()
    register_glm47_bridge()
    sys.argv[0] = str(convert_py)
    runpy.run_path(str(convert_py), run_name="__main__")


if __name__ == "__main__":
    main()
