"""Build a one-row SFT dataset from an Aider-style C++ task folder."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    AiderTask,
    TaskEvalError,
    _validate_relative_file,
    build_prompt,
    load_task,
)


DEFAULT_OUT = Path(".w8-biayn/data/aider-task-sft")
DEFAULT_MODEL_FAMILY = "moonlight"
DEFAULT_PURPOSE = "aider-task-sft"


@dataclass(frozen=True)
class DatasetPaths:
    root: Path
    manifest: Path
    train_jsonl: Path


def dataset_paths(root: Path | str) -> DatasetPaths:
    root_path = Path(root)
    return DatasetPaths(
        root=root_path,
        manifest=root_path / "manifest.json",
        train_jsonl=root_path / "sft" / "train.jsonl",
    )


def _stable_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _stable_pretty_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def _write_if_same_or_forced(path: Path, content: str, *, force: bool) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
        if not force:
            raise FileExistsError(
                f"{path} already exists with different content; pass --force to rewrite it"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _load_config(task_dir: Path) -> dict[str, Any]:
    config_path = task_dir / ".meta" / "config.json"
    if not config_path.exists():
        raise TaskEvalError(f"missing task config: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise TaskEvalError(f"task config must be an object: {config_path}")
    return config


def load_example_files_from_config(task_dir: Path | str) -> tuple[str, ...]:
    config = _load_config(Path(task_dir))
    files = config.get("files")
    example = files.get("example") if isinstance(files, dict) else None
    if not isinstance(example, list) or not example:
        raise TaskEvalError("task config must define files.example for SFT targets")
    result: list[str] = []
    for item in example:
        if not isinstance(item, str):
            raise TaskEvalError(f"non-string example file in task config: {item!r}")
        result.append(_validate_relative_file(item))
    return tuple(result)


def build_assistant_response(task: AiderTask, example_files: Sequence[str]) -> str:
    if len(task.editable_files) != len(example_files):
        raise TaskEvalError(
            "files.example must have the same length and order as files.solution "
            f"({len(example_files)} examples for {len(task.editable_files)} editable files)"
        )

    blocks: list[str] = []
    for output_filename, example_filename in zip(task.editable_files, example_files, strict=True):
        example_path = task.task_dir / _validate_relative_file(example_filename)
        if not example_path.exists():
            raise TaskEvalError(f"example file missing from task directory: {example_path}")
        content = example_path.read_text(encoding="utf-8").rstrip()
        blocks.append(f"{output_filename}\n```\n{content}\n```")
    return "\n\n".join(blocks)


def build_train_row(
    *,
    task: AiderTask,
    example_files: Sequence[str],
    task_id: str | None = None,
    label: str | None = None,
    source: str | None = None,
    model_family: str = DEFAULT_MODEL_FAMILY,
    purpose: str = DEFAULT_PURPOSE,
) -> dict[str, Any]:
    resolved_task_id = task_id or task.task_id
    resolved_label = label or resolved_task_id
    resolved_source = source or str(task.task_dir)
    return {
        "label": resolved_label,
        "messages": [
            {"role": "user", "content": build_prompt(task)},
            {"role": "assistant", "content": build_assistant_response(task, example_files)},
        ],
        "metadata": {
            "format": "aider-whole",
            "model_family": model_family,
            "purpose": purpose,
            "source": resolved_source,
            "subset": "train",
            "task_id": resolved_task_id,
        },
        "task_id": resolved_task_id,
    }


def build_manifest(
    *,
    task: AiderTask,
    example_files: Sequence[str],
    row: dict[str, Any],
    model_family: str = DEFAULT_MODEL_FAMILY,
) -> dict[str, Any]:
    return {
        "editable_files": list(task.editable_files),
        "example_files": list(example_files),
        "files": {"sft_train": "sft/train.jsonl"},
        "kind": "aider-task-whole-sft",
        "label": row["label"],
        "model_family": model_family,
        "schema_version": 1,
        "source_task_dir": str(task.task_dir),
        "task_id": row["task_id"],
        "train_count": 1,
    }


def build_dataset(
    *,
    task_dir: Path | str,
    out: Path | str = DEFAULT_OUT,
    editable_files: Sequence[str] | None = None,
    task_id: str | None = None,
    label: str | None = None,
    source: str | None = None,
    model_family: str = DEFAULT_MODEL_FAMILY,
    purpose: str = DEFAULT_PURPOSE,
    force: bool = False,
) -> DatasetPaths:
    task = load_task(task_dir, editable_files=editable_files)
    example_files = load_example_files_from_config(task.task_dir)
    row = build_train_row(
        task=task,
        example_files=example_files,
        task_id=task_id,
        label=label,
        source=source,
        model_family=model_family,
        purpose=purpose,
    )
    manifest = build_manifest(task=task, example_files=example_files, row=row, model_family=model_family)
    paths = dataset_paths(out)
    _write_if_same_or_forced(paths.train_jsonl, _stable_json(row) + "\n", force=force)
    _write_if_same_or_forced(paths.manifest, _stable_pretty_json(manifest), force=force)
    return paths


def _split_files(values: Sequence[str]) -> tuple[str, ...] | None:
    if not values:
        return None
    result: list[str] = []
    for value in values:
        result.extend(part for part in value.split(",") if part)
    return tuple(result)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize one-row Aider whole-format SFT data from a task folder."
    )
    parser.add_argument("--task-dir", type=Path, required=True, help="Aider/Polyglot-style C++ task directory.")
    parser.add_argument(
        "--editable-file",
        action="append",
        default=[],
        help="Editable solution file. Repeat or pass comma-separated values. Defaults to .meta/config.json files.solution.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output dataset directory. Defaults to {DEFAULT_OUT}.")
    parser.add_argument("--task-id", default=None, help="Task id to write in the JSONL row. Defaults to task directory name.")
    parser.add_argument("--label", default=None, help="Row label. Defaults to the resolved task id.")
    parser.add_argument("--source", default=None, help="Metadata source string. Defaults to the task directory path.")
    parser.add_argument("--model-family", default=DEFAULT_MODEL_FAMILY)
    parser.add_argument("--purpose", default=DEFAULT_PURPOSE)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rewrite existing manifest/JSONL files if their content differs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = build_dataset(
        task_dir=args.task_dir,
        out=args.out,
        editable_files=_split_files(args.editable_file),
        task_id=args.task_id,
        label=args.label,
        source=args.source,
        model_family=args.model_family,
        purpose=args.purpose,
        force=args.force,
    )
    print(f"Wrote Aider task SFT data under {paths.root}")
    print(f"manifest={paths.manifest}")
    print(f"sft_train={paths.train_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
