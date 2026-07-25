"""Project constants and upstream pins for Aider SFT task tooling."""

from __future__ import annotations

from dataclasses import dataclass

SLIME_REPO = "https://github.com/THUDM/slime.git"
EXERCISM_CPP_REPO = "https://github.com/exercism/cpp.git"
AIDER_REPO = "https://github.com/Aider-AI/aider.git"
AIDER_POLYGLOT_REPO = "https://github.com/Aider-AI/polyglot-benchmark.git"

SLIME_PIN = "a897e1f40357fdf3b148f1eb4ce26e1aeccfcd2c"
EXERCISM_CPP_PIN = "d2babb2bd750c884abf86ce52dde274ae7de9749"
AIDER_PIN = "5dc9490bb35f9729ef2c95d00a19ccd30c26339c"
AIDER_POLYGLOT_PIN = "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f"

DEFAULT_DATA_ROOT = ".w8-biayn/data"


@dataclass(frozen=True)
class Upstream:
    name: str
    repo: str
    pin: str


UPSTREAMS = {
    "slime": Upstream("slime", SLIME_REPO, SLIME_PIN),
    "exercism-cpp": Upstream("exercism-cpp", EXERCISM_CPP_REPO, EXERCISM_CPP_PIN),
    "aider": Upstream("aider", AIDER_REPO, AIDER_PIN),
    "aider-polyglot": Upstream(
        "aider-polyglot", AIDER_POLYGLOT_REPO, AIDER_POLYGLOT_PIN
    ),
}
