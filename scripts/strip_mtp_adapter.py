"""Copy a HF PEFT adapter dir, dropping MTP (layer-47) tensors SGLang cannot serve.

The Miles trainer saves LoRA adapters that include the MTP head's tensors
(GLM-4.7-Flash layer 47). SGLang serves layers 0-46 only, so a disk load of
the raw adapter fails with an index-out-of-range. Usage:

    python scripts/strip_mtp_adapter.py <trainer_adapter_dir> <serve_dir>
"""

import os
import re
import shutil
import sys

import torch


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    sd = torch.load(os.path.join(src, "adapter_model.bin"), map_location="cpu", weights_only=True)
    keep = {k: v for k, v in sd.items() if not re.search(r"\.layers\.47\.", k)}
    print(f"kept {len(keep)}/{len(sd)} tensors (stripped {len(sd) - len(keep)} MTP tensors)")
    torch.save(keep, os.path.join(dst, "adapter_model.bin"))
    shutil.copy(os.path.join(src, "adapter_config.json"), os.path.join(dst, "adapter_config.json"))
    print("SERVE_COPY_READY", dst)


if __name__ == "__main__":
    main()
