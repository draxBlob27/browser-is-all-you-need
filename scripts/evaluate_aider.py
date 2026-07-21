#!/usr/bin/env python3
"""Score or aggregate clean-room Aider rollout records."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Iterable, Sequence

from glm47_posttraining.aider_rl.dataset import load_tokenizer, verify_bundle
from glm47_posttraining.aider_rl.eval import aggregate_eval_records, zero_variance_group_fraction
from glm47_posttraining.integrations.miles_aider_rl import reward_func
from glm47_posttraining.integrations.wandb_aider_rl import publish_aider_eval


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return output


def write_json(path: str | Path, value: object) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def score_samples(
    data_root: str | Path, samples_path: str | Path, *, tokenizer_path: str
) -> list[dict[str, Any]]:
    root = Path(data_root).resolve(strict=True)
    verify_bundle(root, tokenizer=load_tokenizer(tokenizer_path))
    os.environ["MILES_AIDER_DATA_DIR"] = str(root)
    samples = read_jsonl(samples_path)
    result = asyncio.run(reward_func(None, samples))
    if not isinstance(result, list):
        raise RuntimeError("batch reward hook did not return a list")
    return result


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--records")
    source.add_argument("--samples")
    parser.add_argument("--data-root")
    parser.add_argument("--tokenizer")
    parser.add_argument("--wandb-project")
    parser.add_argument("--wandb-run-id")
    parser.add_argument("--wandb-group")
    args = parser.parse_args(argv)

    output = Path(args.out)
    if args.samples:
        if not args.data_root:
            parser.error("--samples requires --data-root")
        if not args.tokenizer:
            parser.error("--samples requires --tokenizer")
        records = score_samples(args.data_root, args.samples, tokenizer_path=args.tokenizer)
        records_path = write_jsonl(output / f"{args.label}.records.jsonl", records)
    else:
        records = read_jsonl(args.records)
        records_path = Path(args.records)
    summary = aggregate_eval_records(records, label=args.label)
    summary["zero_variance_group_fraction"] = zero_variance_group_fraction(records)
    summary["records_path"] = str(records_path)
    summary_path = write_json(output / f"{args.label}.summary.json", summary)
    if args.wandb_project:
        publish_aider_eval(
            records,
            label=args.label,
            project=args.wandb_project,
            run_id=args.wandb_run_id,
            group=args.wandb_group,
        )
    print(json.dumps({"records": str(records_path), "summary": str(summary_path)}, indent=2))


if __name__ == "__main__":
    main()
