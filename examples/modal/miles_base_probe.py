"""CPU-only probe for the pinned Miles base image."""

from __future__ import annotations

import modal


MILES_IMAGE = (
    "radixark/miles:latest-cu12@"
    "sha256:efc8027fc47aaa9687dc4f1046093ed4e2f9789e52a932fcefb7031402aeff37"
)

app = modal.App("glm47-miles-base-probe")
image = modal.Image.from_registry(MILES_IMAGE)


@app.function(image=image, cpu=2.0, memory=4096, timeout=900)
def run() -> dict[str, str]:
    import sys
    from importlib import metadata

    packages = ("transformers", "torch", "sglang-kernel", "flashinfer-python")
    return {
        "python": sys.version.split()[0],
        **{package: metadata.version(package) for package in packages},
    }


@app.local_entrypoint()
def probe() -> None:
    print(run.remote())
