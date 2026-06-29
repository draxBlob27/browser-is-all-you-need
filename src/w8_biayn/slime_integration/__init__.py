"""Generic helpers for the pinned SLIME upstream integration."""

from .cpp_reward import (
    SlimeCppRewardError,
    load_slime_cpp_task,
    resolve_slime_cpp_task_path,
    score_slime_cpp_row,
    slime_cpp_metadata,
)
from .cpp_metrics import aggregate_cpp_reward_metrics
from .doctor import run_slime_doctor, slime_root
from .sandbox import DockerSandbox, SandboxError, create_sandbox, sandbox_backend_from_env
from .setup import (
    DEFAULT_SLIME_IMAGE,
    SlimeSetupPlan,
    build_slime_setup_plan,
    write_slime_setup_files,
)

__all__ = [
    "DEFAULT_SLIME_IMAGE",
    "DockerSandbox",
    "SandboxError",
    "SlimeCppRewardError",
    "SlimeSetupPlan",
    "aggregate_cpp_reward_metrics",
    "build_slime_setup_plan",
    "create_sandbox",
    "load_slime_cpp_task",
    "resolve_slime_cpp_task_path",
    "run_slime_doctor",
    "sandbox_backend_from_env",
    "score_slime_cpp_row",
    "slime_cpp_metadata",
    "slime_root",
    "write_slime_setup_files",
]
