"""Aider-style whole-file C++ reinforcement-learning environment."""

from .parser import ParsedEdit, parse_whole_edit
from .curriculum import CurriculumCatalog, analyze_no_update_canary
from .prompt import build_prompt, render_whole_edit
from .reward import RewardBreakdown, compute_reward
from .schema import AiderHarnessResult, AiderTask

__all__ = [
    "AiderHarnessResult",
    "AiderTask",
    "CurriculumCatalog",
    "ParsedEdit",
    "RewardBreakdown",
    "build_prompt",
    "analyze_no_update_canary",
    "compute_reward",
    "parse_whole_edit",
    "render_whole_edit",
]
