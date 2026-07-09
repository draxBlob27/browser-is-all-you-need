from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from w8_biayn.cpp_perf.sandbox import sandbox_backend
from w8_biayn.cpp_perf.schema import CppTask
from w8_biayn.integrations.slime_cpp_perf import _oracle_filter_row, _score_oracle_full_marks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit PIE oracle compile, test, and timing validity.")
    parser.add_argument("--data-dir", required=True, help="SLIME C++ dataset root.")
    parser.add_argument(
        "--rows",
        default="eval/validation.jsonl",
        help="Prompt rows JSONL, relative to --data-dir unless absolute.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=32)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_task_rows(data_dir: Path, rows_path: Path) -> list[tuple[Path, CppTask]]:
    selected: list[tuple[Path, CppTask]] = []
    seen: set[str] = set()
    for row in read_jsonl(rows_path):
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        task_path_value = metadata.get("task_path")
        if not task_path_value:
            raise ValueError(f"row has no metadata.task_path: {row.get('task_id') or row.get('label')}")
        task_path = Path(str(task_path_value))
        if not task_path.is_absolute():
            task_path = data_dir / task_path
        task = CppTask.read_json(task_path)
        if task.task_id in seen:
            continue
        seen.add(task.task_id)
        selected.append((task_path, task))
    return selected


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir).resolve()
    rows_path = Path(args.rows)
    if not rows_path.is_absolute():
        rows_path = data_dir / rows_path
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_task_rows(data_dir, rows_path)
    if not tasks:
        raise ValueError(f"No task rows found in {rows_path}")
    started = time.time()
    results = _score_oracle_full_marks(tasks, workers=max(1, args.workers))
    elapsed_seconds = time.time() - started

    rows = [_oracle_filter_row(result) for result in results]
    write_jsonl(output_dir / "oracle_audit.jsonl", rows)
    kept_task_ids = [result.task.task_id for result in results if result.keep]
    dropped_task_ids = [result.task.task_id for result in results if not result.keep]
    write_json(output_dir / "keep_task_ids.json", kept_task_ids)
    write_json(output_dir / "drop_task_ids.json", dropped_task_ids)

    reason_counts = Counter(result.reason for result in results)
    summary = {
        "schema_version": 1,
        "data_dir": str(data_dir),
        "rows_path": str(rows_path),
        "repo_sha": repo_sha(),
        "sandbox_backend": sandbox_backend(),
        "sandbox_image": os.environ.get("W8_CPP_SANDBOX_IMAGE", ""),
        "compiler": compiler_version(),
        "workers": max(1, args.workers),
        "elapsed_seconds": elapsed_seconds,
        "scored": len(results),
        "kept": len(kept_task_ids),
        "dropped": len(dropped_task_ids),
        "reason_counts": dict(sorted(reason_counts.items())),
        "keep_task_ids_path": "keep_task_ids.json",
        "drop_task_ids_path": "drop_task_ids.json",
        "audit_rows_path": "oracle_audit.jsonl",
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repo_sha() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def compiler_version() -> str:
    if sandbox_backend() != "local":
        return "container-image"
    return subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]


if __name__ == "__main__":
    main()
