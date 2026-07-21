"""Strict parser for Aider ``whole`` named-file responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from .schema import validate_relative_path


OPEN_FENCE_RE = re.compile(r"```(?:cpp|c\+\+|cc)[ \t]*\r?\n", re.IGNORECASE)
CLOSE_FENCE_RE = re.compile(r"(?:\r?\n)?```[ \t]*(?:\r?\n|\Z)")


@dataclass(frozen=True)
class ParsedEdit:
    files: Mapping[str, str]
    ordered_paths: tuple[str, ...]
    total_bytes: int


class WholeEditParseError(ValueError):
    """The response is not one exact, safe, complete whole-file edit."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def parse_whole_edit(
    model_output: str,
    allowed_paths: Sequence[str],
    *,
    max_bytes_by_path: Mapping[str, int] | None = None,
) -> ParsedEdit:
    """Parse exactly one ordered fenced C++ block for every allowed file."""

    if not model_output or "\x00" in model_output:
        raise WholeEditParseError("invalid_format", "response is empty or contains NUL")
    expected = tuple(validate_relative_path(path) for path in allowed_paths)
    if not expected or len(expected) != len(set(expected)):
        raise ValueError("allowed_paths must contain unique safe paths")

    cursor = 0
    files: dict[str, str] = {}
    parsed_paths: list[str] = []
    length = len(model_output)
    while cursor < length:
        while cursor < length and model_output[cursor] in "\r\n":
            cursor += 1
        if cursor >= length:
            break
        line_end = model_output.find("\n", cursor)
        if line_end < 0:
            raise WholeEditParseError("invalid_format", "file name must be followed by a fenced block")
        path = model_output[cursor:line_end].rstrip("\r")
        try:
            validate_relative_path(path)
        except ValueError as exc:
            raise WholeEditParseError("unsafe_path", str(exc)) from exc
        cursor = line_end + 1
        opening = OPEN_FENCE_RE.match(model_output, cursor)
        if opening is None:
            raise WholeEditParseError("invalid_format", f"{path} is not followed by a C++ fence")
        code_start = opening.end()
        closing = CLOSE_FENCE_RE.search(model_output, code_start)
        if closing is None:
            raise WholeEditParseError("invalid_format", f"{path} has no closing fence")
        code = model_output[code_start : closing.start()]
        if code.endswith("\r"):
            code = code[:-1]
        code = code + "\n"
        if path in files:
            raise WholeEditParseError("duplicate_file", f"duplicate file block: {path}")
        files[path] = code
        parsed_paths.append(path)
        cursor = closing.end()

    parsed = tuple(parsed_paths)
    if len(parsed) < len(expected):
        missing = [path for path in expected if path not in files]
        raise WholeEditParseError("missing_file", f"missing file blocks: {missing}")
    if len(parsed) > len(expected) or any(path not in expected for path in parsed):
        extra = [path for path in parsed if path not in expected]
        raise WholeEditParseError("extra_file", f"extra file blocks: {extra}")
    if parsed != expected:
        raise WholeEditParseError("wrong_file_order", "file blocks must follow the admitted order")

    limits = dict(max_bytes_by_path or {})
    total = 0
    for path, code in files.items():
        size = len(code.encode("utf-8"))
        if size > limits.get(path, 262_144):
            raise WholeEditParseError("oversized_file", f"{path} exceeds its byte limit")
        total += size
    return ParsedEdit(files=files, ordered_paths=parsed, total_bytes=total)
