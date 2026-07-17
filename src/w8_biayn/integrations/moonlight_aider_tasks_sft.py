"""Build one minimal-metadata SFT JSONL from local Aider task directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from w8_biayn.integrations.moonlight_aider_task_sft import (
    _stable_json,
    build_train_row,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_aider_task_eval import load_task


def build_rows(tasks_root: Path) -> list[dict[str, Any]]:
    """Build deterministic train rows, one for every materialized task config."""
    rows: list[dict[str, Any]] = []
    for config_path in sorted(tasks_root.rglob(".meta/config.json")):
        task_root = config_path.parent.parent
        task = load_task(task_root)
        task_id = task_root.name
        row = build_train_row(
            task=task,
            example_files=load_example_files_from_config(task_root),
            task_id=task_id,
            label=task_id,
            purpose=task_root.parent.name,
        )
        row["metadata"] = {
            "purpose": task_root.parent.name,
            "subset": "train",
            "task_id": task_id,
        }
        rows.append(row)
    return rows


def build_dataset(*, tasks_root: Path, out: Path, force: bool = False) -> Path:
    train_jsonl = out / "sft" / "train.jsonl"
    content = "".join(_stable_json(row) + "\n" for row in build_rows(tasks_root))
    if train_jsonl.exists() and train_jsonl.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{train_jsonl} differs; pass --force to replace it")
    train_jsonl.parent.mkdir(parents=True, exist_ok=True)
    train_jsonl.write_text(content, encoding="utf-8")
    return train_jsonl


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    print(build_dataset(tasks_root=args.tasks_root, out=args.out, force=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
