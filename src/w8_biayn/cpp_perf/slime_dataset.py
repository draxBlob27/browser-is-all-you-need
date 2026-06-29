"""Build SLIME-ready C++ GRPO prompt datasets from validated task JSON."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from .data import write_data_manifest
from .schema import CppTask
from .skyrl_dataset import DATA_SOURCE, build_prompt, load_tasks


def task_to_slime_grpo_row(task: CppTask, *, task_path: str) -> dict[str, Any]:
    """Convert one C++ task into the JSONL shape consumed by SLIME launchers."""

    return {
        "data_source": DATA_SOURCE,
        "prompt": build_prompt(task),
        "label": task.task_id,
        "metadata": {
            "task_id": task.task_id,
            "problem_id": task.problem_id,
            "split": task.split,
            "task_path": task_path,
            "reference_metric": task.reference.metric,
            "reference_value": task.reference.value,
            "gem5_cycles": task.reference.gem5_cycles,
            "visible_tests": [case.model_dump() for case in task.unit_tests],
            "hidden_test_count": len(task.hidden_tests),
            "source": task.source,
        },
    }


def build_slime_cpp_datasets(
    tasks_dir: str | Path,
    output_dir: str | Path,
    *,
    validation_splits: Iterable[str] = ("validation", "test"),
    profile: str = "smoke",
    run_id: str | None = None,
    min_train_tasks: int = 1,
    min_validation_tasks: int = 1,
    limit_train: int | None = None,
    limit_validation: int | None = None,
    force: bool = False,
) -> dict[str, Path]:
    """Write SLIME GRPO JSONL prompt data and copied task JSON files."""

    loaded = load_tasks(tasks_dir)
    if not loaded:
        raise ValueError(f"No task JSON files found under {tasks_dir}")

    validation_names = set(validation_splits)
    train_loaded = [(path, task) for path, task in loaded if task.split == "train"]
    validation_loaded = [(path, task) for path, task in loaded if task.split in validation_names]

    if limit_train is not None:
        train_loaded = train_loaded[:limit_train]
    if limit_validation is not None:
        validation_loaded = validation_loaded[:limit_validation]

    if len(train_loaded) < min_train_tasks:
        raise ValueError(
            f"SLIME C++ dataset build requires at least {min_train_tasks} train tasks; "
            f"found {len(train_loaded)}"
        )
    if len(validation_loaded) < min_validation_tasks:
        raise ValueError(
            f"SLIME C++ dataset build requires at least {min_validation_tasks} validation tasks "
            f"in {sorted(validation_names)}; found {len(validation_loaded)}"
        )

    output = Path(output_dir)
    if force and output.exists():
        shutil.rmtree(output)
    tasks_out = output / "tasks"
    grpo_out = output / "grpo"
    for directory in (tasks_out, grpo_out):
        directory.mkdir(parents=True, exist_ok=True)

    copied: dict[Path, str] = {}
    for source_path, _task in train_loaded + validation_loaded:
        if source_path in copied:
            continue
        rel_source = source_path.relative_to(Path(tasks_dir))
        destination = tasks_out / rel_source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        copied[source_path] = destination.relative_to(output).as_posix()

    train_rows = [
        task_to_slime_grpo_row(task, task_path=copied[path])
        for path, task in train_loaded
    ]
    validation_rows = [
        task_to_slime_grpo_row(task, task_path=copied[path])
        for path, task in validation_loaded
    ]

    train_path = grpo_out / "train.jsonl"
    validation_path = grpo_out / "validation.jsonl"
    _write_jsonl(train_rows, train_path)
    _write_jsonl(validation_rows, validation_path)

    manifest = write_data_manifest(
        output,
        kind="slime-cpp-grpo-dataset",
        sources=[str(tasks_dir)],
        options={
            "validation_splits": sorted(validation_names),
            "profile": profile,
            "run_id": run_id,
            "format": "jsonl",
            "prompt_key": "prompt",
            "label_key": "label",
            "metadata_task_path": "metadata.task_path",
            "limit_train": limit_train,
            "limit_validation": limit_validation,
            "counts": {
                "train": len(train_loaded),
                "validation_effective": len(validation_loaded),
            },
        },
    )
    return {
        "grpo_train": train_path,
        "grpo_validation": validation_path,
        "manifest": manifest,
    }


def _write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
