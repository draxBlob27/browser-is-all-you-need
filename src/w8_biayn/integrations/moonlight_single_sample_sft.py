"""Build the Moonlight single-sample Aider whole-format SFT dataset."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


TASK_ID = "aider-whole-format-001"
DEFAULT_OUT = Path(".w8-biayn/data/aider-whole-single")

USER_PROMPT = (
    "Use whole edit format. Modify the supplied files `leap.cpp` and `leap.h` to "
    "implement a leap-year checker. Return only complete file listings. Each fenced "
    "block must be preceded by its filename."
)

ASSISTANT_RESPONSE = """leap.h
```
#if !defined(LEAP_H)
#define LEAP_H

namespace leap {

bool is_leap_year(int year);

}  // namespace leap

#endif
```

leap.cpp
```
#include "leap.h"

namespace leap {

bool is_leap_year(int year) {
    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
}

}  // namespace leap
```"""

TRAIN_ROW = {
    "messages": [
        {"role": "user", "content": USER_PROMPT},
        {"role": "assistant", "content": ASSISTANT_RESPONSE},
    ],
    "label": TASK_ID,
    "task_id": TASK_ID,
    "metadata": {
        "task_id": TASK_ID,
        "source": "single_sample_for_sft.md",
        "subset": "train",
        "format": "aider-whole",
        "model_family": "moonlight",
        "purpose": "single-sample-sft-smoke",
    },
}

MANIFEST = {
    "kind": "single-sample-aider-whole-sft",
    "schema_version": 1,
    "source": "single_sample_for_sft.md",
    "model_family": "moonlight",
    "train_count": 1,
    "files": {"sft_train": "sft/train.jsonl"},
}


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


def build_dataset(root: Path | str = DEFAULT_OUT, *, force: bool = False) -> DatasetPaths:
    """Write the one-row chat-message SFT dataset expected by the Moonlight lane."""

    paths = dataset_paths(root)
    train_content = _stable_json(TRAIN_ROW) + "\n"
    manifest_content = _stable_pretty_json(MANIFEST)
    _write_if_same_or_forced(paths.train_jsonl, train_content, force=force)
    _write_if_same_or_forced(paths.manifest, manifest_content, force=force)
    return paths


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the Moonlight single-sample Aider whole-format SFT data."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output dataset directory. Defaults to {DEFAULT_OUT}.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rewrite existing manifest/JSONL files if their content differs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = build_dataset(args.out, force=args.force)
    print(f"Wrote Moonlight single-sample SFT data under {paths.root}")
    print(f"manifest={paths.manifest}")
    print(f"sft_train={paths.train_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
