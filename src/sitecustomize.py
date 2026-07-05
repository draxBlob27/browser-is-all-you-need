from __future__ import annotations

import os


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


if _truthy_env("W8_REGISTER_GLM47_BRIDGE"):
    from w8_biayn.integrations.miles_glm47_bridge import register_glm47_bridge

    register_glm47_bridge()
