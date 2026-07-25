#!/usr/bin/env python3
"""Export one fixed26-style Aider C++ task folder to SFT train.jsonl."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from glm47_posttraining.aider_polyglot.dataset import build_aider_messages  # noqa: E402
from glm47_posttraining.aider_polyglot.parser import parse_whole_file_response  # noqa: E402


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_listing(filename: str, content: str) -> str:
    return f"{filename}\n```cpp\n{content.rstrip()}\n```\n"


def build_assistant_answer(task_dir: Path, editable_files: list[str], example_files: list[str]) -> str:
    if len(editable_files) != len(example_files):
        raise ValueError("config files.solution and files.example must have the same length")

    listings = []
    for editable, example in zip(editable_files, example_files, strict=True):
        example_path = task_dir / example
        if not example_path.is_file():
            raise FileNotFoundError(f"missing example target: {example_path}")
        listings.append(file_listing(editable, example_path.read_text(encoding="utf-8")))

    return (
        "I will update the implementation to preserve one audit slot per input item, "
        "mark invalid entries explicitly, and keep scanning after the first error.\n\n"
        + "\n".join(listings)
    )


def export_task(task_dir: Path, output_dir: Path) -> dict[str, Path]:
    task_dir = task_dir.resolve()
    output_dir = output_dir.resolve()
    config = read_json(task_dir / ".meta" / "config.json")
    files = config.get("files")
    if not isinstance(files, dict):
        raise ValueError("missing files mapping in .meta/config.json")

    editable_files = [Path(name).name for name in files.get("solution", [])]
    example_files = [str(name) for name in files.get("example", [])]
    if not editable_files:
        raise ValueError("config files.solution must name at least one editable file")
    for name in editable_files:
        if Path(name).name != name:
            raise ValueError(f"solution file must be a root editable filename: {name}")
        if not (task_dir / name).is_file():
            raise FileNotFoundError(f"missing starter editable file: {task_dir / name}")

    prompt = build_aider_messages(task_dir, editable_files)
    answer = build_assistant_answer(task_dir, editable_files, example_files)
    parsed = parse_whole_file_response(answer, editable_files)
    for editable, example in zip(editable_files, example_files, strict=True):
        expected = (task_dir / example).read_text(encoding="utf-8").rstrip() + "\n"
        if parsed.files.get(editable) != expected:
            raise ValueError(f"parsed answer does not match target example for {editable}")

    task_id = task_dir.name
    row = {
        "messages": [*prompt, {"role": "assistant", "content": answer}],
        "label": f"aider-sft-cpp/{task_id}",
        "task_id": f"aider-sft-cpp/{task_id}",
        "problem_id": task_id,
        "split": "train",
        "metadata": {
            "data_source": "fixed26-aider-analog-sft",
            "task_id": f"aider-sft-cpp/{task_id}",
            "problem_id": task_id,
            "split": "train",
            "harness_kind": "shadow_cpp17_sft",
            "source_task_dir": str(task_dir),
            "editable_files": editable_files,
            "example_files": example_files,
            "config_sha256": sha256_path(task_dir / ".meta" / "config.json"),
            "answer_format_valid": parsed.format_valid,
        },
    }

    train_jsonl = output_dir / "sft" / "train.jsonl"
    train_jsonl.parent.mkdir(parents=True, exist_ok=True)
    train_jsonl.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "kind": "fixed26-aider-analog-sft-data",
        "schema_version": 1,
        "source_task_dir": str(task_dir),
        "counts": {"train": 1},
        "files": {"sft_train": "sft/train.jsonl"},
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"manifest": manifest_path, "sft_train": train_jsonl}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paths = export_task(args.task_dir, args.out)
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
