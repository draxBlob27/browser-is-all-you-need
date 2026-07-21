"""Public Aider whole-file prompt rendering with a hard private-data boundary."""

from __future__ import annotations

from collections.abc import Mapping

from .schema import AiderTask


WHOLE_EDIT_INSTRUCTION = (
    "Replace every listed solution file with its complete corrected contents.\n"
    "Return only the file name followed by one fenced cpp block for that file. "
    "Do not return prose, diffs, tests, build files, or unlisted paths."
)


def build_prompt(task: AiderTask, starter_files: Mapping[str, str]) -> str:
    """Render only public documentation and ordered editable starter files."""

    expected = task.allowed_paths
    if tuple(starter_files) != expected:
        raise ValueError("starter files must exactly match admitted editable-file order")
    sections = [
        WHOLE_EDIT_INSTRUCTION,
        "Introduction:\n" + task.introduction.strip(),
        "Instructions:\n" + task.instructions.strip(),
    ]
    for path in expected:
        sections.append(f"{path}\n```cpp\n{starter_files[path].rstrip()}\n```")
    sections.append(
        "Return one complete replacement block for every file above, in the same order. "
        "Preserve required names and use only permitted dependencies."
    )
    return "\n\n".join(sections)


def render_whole_edit(task: AiderTask, files: Mapping[str, str]) -> str:
    """Render a strict target/reference whole-file answer."""

    if tuple(files) != task.allowed_paths:
        raise ValueError("answer files must exactly match admitted editable-file order")
    return "\n\n".join(f"{path}\n```cpp\n{files[path].rstrip()}\n```" for path in task.allowed_paths) + "\n"
