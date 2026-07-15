"""Deterministic compact Aider whole renderer and strict target parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import RENDERER_VERSION
from .errors import AiderSftError
from .schema import CanonicalTask, SftRow
from .util import (
    canonical_json_bytes,
    fingerprint,
    normalize_relative_path,
    normalize_text_bytes,
    read_json,
)

FORMAT_CONTRACT = (
    "Use Aider whole edit format. Solve the task by returning only complete editable-file "
    "listings. Put each exact relative filename immediately before its fenced block. "
    "Do not return a diff, "
    "tests, metadata, reference filenames, or explanatory prose."
)
PRESERVATION_REMINDER = (
    "Preserve existing function, class, namespace, and file names unless the task requires "
    "changes. Use only C++17 and supplied context."
)


def renderer_policy_fingerprint() -> str:
    return fingerprint(
        "aider-sft-renderer-policy-v1",
        RENDERER_VERSION,
        FORMAT_CONTRACT,
        PRESERVATION_REMINDER,
    )


def _read_normalized(path: Path, label: str) -> str:
    return normalize_text_bytes(path.read_bytes(), label=label).decode("utf-8")


def _file_block(relative: str, content: str) -> str:
    normalize_relative_path(relative)
    normalized = normalize_text_bytes(content.encode("utf-8"), label=relative).decode("utf-8")
    return f"{relative}\n\x60\x60\x60cpp\n{normalized}\x60\x60\x60"


def render_prompt(task_root: Path, task: CanonicalTask | None = None) -> str:
    task = task or CanonicalTask.model_validate(read_json(task_root / "task.json"))
    sections = [FORMAT_CONTRACT]
    introduction = task_root / "docs/introduction.md"
    if introduction.is_file():
        sections.extend(
            ["# Introduction", _read_normalized(introduction, "introduction").rstrip("\n")]
        )
    sections.extend(
        [
            "# Instructions",
            _read_normalized(task_root / "docs/instructions.md", "instructions").rstrip("\n"),
        ]
    )
    appended = task_root / "docs/instructions.append.md"
    if appended.is_file():
        sections.extend(
            [
                "# Additional instructions",
                _read_normalized(appended, "instructions.append").rstrip("\n"),
            ]
        )
    editable_blocks = [
        _file_block(
            relative,
            _read_normalized(task_root / "workspace/starter" / relative, relative),
        )
        for relative in sorted(task.files.editable)
    ]
    sections.extend(["# Editable starter files", "\n\n".join(editable_blocks)])
    if task.files.model_context:
        context_blocks = [
            _file_block(
                relative,
                _read_normalized(task_root / "workspace/context" / relative, relative),
            )
            for relative in sorted(task.files.model_context)
        ]
        sections.extend(
            [
                "# Read-only context files (do not return these)",
                "\n\n".join(context_blocks),
            ]
        )
    sections.append(PRESERVATION_REMINDER)
    return "\n\n".join(sections).rstrip("\n") + "\n"


def render_target(task_root: Path, task: CanonicalTask | None = None) -> str:
    task = task or CanonicalTask.model_validate(read_json(task_root / "task.json"))
    blocks = [
        _file_block(
            relative,
            _read_normalized(task_root / "workspace/reference" / relative, relative),
        )
        for relative in sorted(task.files.editable)
    ]
    target = "\n\n".join(blocks).rstrip("\n") + "\n"
    parsed = parse_target(target, expected_files=task.files.editable)
    expected = {
        relative: _read_normalized(task_root / "workspace/reference" / relative, relative)
        for relative in sorted(task.files.editable)
    }
    if parsed != expected:
        raise AiderSftError("target_reference_mismatch", f"target differs for {task.task_id}")
    return target


def parse_target(content: str, *, expected_files: list[str] | None = None) -> dict[str, str]:
    if not content.endswith("\n") or content.endswith("\n\n"):
        raise AiderSftError("whole_format_failed", "target must end in exactly one newline")
    lines = content.splitlines(keepends=True)
    result: dict[str, str] = {}
    index = 0
    while index < len(lines):
        filename_line = lines[index]
        if not filename_line.endswith("\n"):
            raise AiderSftError("whole_format_failed", "filename line lacks newline")
        filename = filename_line[:-1]
        normalize_relative_path(filename)
        if filename != filename.strip() or filename in result:
            raise AiderSftError(
                "whole_format_failed", f"invalid or duplicate filename: {filename!r}"
            )
        index += 1
        if index >= len(lines) or lines[index] != "```cpp\n":
            raise AiderSftError("whole_format_failed", f"{filename} lacks an exact cpp fence")
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index] != "```\n":
            if lines[index].lstrip(" ").startswith("```"):
                raise AiderSftError("whole_format_failed", f"ambiguous fence in {filename}")
            body.append(lines[index])
            index += 1
        if index >= len(lines):
            raise AiderSftError("whole_format_failed", f"unclosed fence for {filename}")
        index += 1
        if not body:
            raise AiderSftError("whole_format_failed", f"empty file listing for {filename}")
        result[filename] = normalize_text_bytes(
            "".join(body).encode("utf-8"), label=filename
        ).decode("utf-8")
        if index == len(lines):
            break
        if lines[index] != "\n":
            raise AiderSftError("whole_format_failed", "only one blank line may separate blocks")
        index += 1
        if index == len(lines):
            raise AiderSftError("whole_format_failed", "trailing prose or blank line")
    if not result:
        raise AiderSftError("whole_format_failed", "target contains no whole-file blocks")
    observed = list(result)
    if observed != sorted(observed):
        raise AiderSftError("whole_format_failed", "file listings are not sorted")
    if expected_files is not None and observed != sorted(expected_files):
        raise AiderSftError(
            "whole_format_failed",
            f"expected exactly {sorted(expected_files)}, observed {observed}",
        )
    return result


def apply_target(
    starter: dict[str, bytes],
    target: str,
    *,
    expected_files: list[str],
) -> dict[str, bytes]:
    parsed = parse_target(target, expected_files=expected_files)
    applied = dict(starter)
    for relative, content in parsed.items():
        if relative not in starter:
            raise AiderSftError("target_apply_failed", f"target creates undeclared file {relative}")
        applied[relative] = content.encode("utf-8")
    return applied


def render_row(
    *,
    task_root: Path,
    config_lock: dict[str, Any],
    oracle_fingerprint: str,
) -> dict[str, Any]:
    task = CanonicalTask.model_validate(read_json(task_root / "task.json"))
    prompt = render_prompt(task_root, task)
    target = render_target(task_root, task)
    tokenizer = config_lock["config"]["tokenizer"]
    row = {
        "schema_version": "aider-sft-row-v1",
        "task_id": task.task_id,
        "label": task.task_id,
        "messages": [
            {"role": "user", "content": prompt, "step_loss_mask": 0},
            {"role": "assistant", "content": target, "step_loss_mask": 1},
        ],
        "metadata": {
            "schema_version": "aider-sft-row-v1",
            "purpose": "primary-aider-sft-dataset",
            "format": "aider-whole",
            "subset": "train",
            "task_id": task.task_id,
            "root_task_id": task.root_task_id,
            "task_family_id": task.task_family_id,
            "source_kind": task.source.kind.value,
            "source_revision": task.source.revision,
            "language_standard": task.language_standard,
            "tokenizer_repository": tokenizer["repository"],
            "tokenizer_revision": tokenizer["revision"],
            "chat_template_sha256": tokenizer["chat_template_sha256"],
            "chat_template_policy": tokenizer["policy"],
            "chat_template_kwargs_sha256": config_lock["resolved"]["chat_template_kwargs_sha256"],
            "sft_mask_adapter": tokenizer["mask_adapter"],
            "loss_mask_type": tokenizer["loss_mask_type"],
            "sequence_length": tokenizer["sequence_length"],
            "primary_category": task.classification.primary_category.value,
            "tags": task.classification.tags,
            "difficulty": task.classification.difficulty.value,
            "editable_files": task.files.editable,
            "context_files": task.files.model_context,
            "oracle_fingerprint": oracle_fingerprint,
            "renderer_version": RENDERER_VERSION,
        },
    }
    SftRow.model_validate(row)
    return row


def row_sha256(row: dict[str, Any]) -> str:
    from .util import sha256_bytes

    return sha256_bytes(canonical_json_bytes(row))
