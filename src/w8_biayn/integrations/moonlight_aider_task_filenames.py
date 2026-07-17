"""Migrate local Aider task editable filenames to their task-ID slug."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

GENERIC_SOLUTION = ("task.h", "task.cpp")


def task_filenames(task_root: Path) -> tuple[str, str]:
    return (f"{task_root.name}.h", f"{task_root.name}.cpp")


def task_named_files(task_root: Path, files: Mapping[str, str]) -> dict[str, str]:
    """Render generic task file templates with the root task-ID filenames."""
    header_name, source_name = task_filenames(task_root)
    rendered: dict[str, str] = {}
    for relative, content in files.items():
        relative = relative.replace("task.h", header_name).replace("task.cpp", source_name)
        content = content.replace("task.h", header_name)
        content = content.replace("task.cpp", source_name)
        rendered[relative] = content
    return rendered


def migrate_task(task_root: Path) -> bool:
    """Rename one generic local task in place; return whether it changed."""
    config_path = task_root / ".meta" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if tuple(config.get("files", {}).get("solution", ())) != GENERIC_SOLUTION:
        return False
    header_name, source_name = task_filenames(task_root)
    header_path, source_path = task_root / "task.h", task_root / "task.cpp"
    if not header_path.is_file() or not source_path.is_file():
        raise ValueError(f"{task_root}: generic solution files are missing")
    if (task_root / header_name).exists() or (task_root / source_name).exists():
        raise ValueError(f"{task_root}: target task-ID filenames already exist")
    header_path.rename(task_root / header_name)
    source_path.rename(task_root / source_name)
    for relative in (source_name, ".meta/example.cpp", "task_visible_test.cpp", ".meta/task_hidden_test.cpp"):
        path = task_root / relative
        if path.is_file():
            path.write_text(path.read_text(encoding="utf-8").replace('#include "task.h"', f'#include "{header_name}"'), encoding="utf-8")
    cmake_path = task_root / "CMakeLists.txt"
    cmake_path.write_text(cmake_path.read_text(encoding="utf-8").replace("task.cpp", source_name), encoding="utf-8")
    config["files"]["solution"] = [header_name, source_name]
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def migrate_tree(root: Path) -> tuple[Path, ...]:
    changed: list[Path] = []
    for config_path in sorted(root.rglob(".meta/config.json")):
        task_root = config_path.parent.parent
        if migrate_task(task_root):
            changed.append(task_root)
    return tuple(changed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    for task_root in migrate_tree(parser.parse_args().root):
        print(task_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
