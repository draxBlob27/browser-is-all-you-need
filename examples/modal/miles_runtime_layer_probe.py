"""CPU-only probe for the Dockerfile runtime layer above the Miles base image."""

from __future__ import annotations

import modal


MILES_IMAGE = (
    "radixark/miles:latest-cu12@"
    "sha256:efc8027fc47aaa9687dc4f1046093ed4e2f9789e52a932fcefb7031402aeff37"
)
image = (
    modal.Image.from_registry(MILES_IMAGE)
    .env({"FLASHINFER_VERSION": "0.6.12", "FLASHINFER_CUDA_INDEX": "129"})
    .run_commands(
        "python3 -m pip install --no-cache-dir --no-deps --upgrade "
        "flashinfer-python==0.6.12 flashinfer-cubin==0.6.12",
        "python3 -m pip install --no-cache-dir --no-deps --upgrade "
        "flashinfer-jit-cache==0.6.12 --index-url https://flashinfer.ai/whl/cu129/",
        "python3 -m pip install --no-cache-dir --no-deps --force-reinstall "
        "sglang-kernel==0.4.4 --index-url https://docs.sglang.ai/whl/cu129/",
        "python3 -m pip install --no-cache-dir --no-deps --upgrade torch-memory-saver==0.0.9.post1",
    )
)

app = modal.App("glm47-miles-runtime-layer-probe")


@app.function(image=image, cpu=2.0, memory=4096, timeout=900)
def run() -> dict[str, str]:
    from importlib import metadata

    packages = (
        "flashinfer-python",
        "flashinfer-cubin",
        "flashinfer-jit-cache",
        "sglang-kernel",
        "torch-memory-saver",
    )
    return {package: metadata.version(package) for package in packages}


@app.local_entrypoint()
def probe() -> None:
    print(run.remote())
