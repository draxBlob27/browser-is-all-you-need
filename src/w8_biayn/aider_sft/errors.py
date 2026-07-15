"""Stable pipeline errors and outcome classification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AiderSftError(RuntimeError):
    """An expected, machine-classified pipeline failure."""

    reason_code: str
    message: str
    outcome: str | None = None

    def __post_init__(self) -> None:
        from .schema import reason_outcome

        object.__setattr__(self, "outcome", self.outcome or reason_outcome(self.reason_code))
        RuntimeError.__init__(self, f"{self.reason_code}: {self.message}")

    def as_dict(self) -> dict[str, str]:
        return {
            "outcome": str(self.outcome),
            "reason_code": self.reason_code,
            "message": self.message,
        }
