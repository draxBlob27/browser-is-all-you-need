#!/usr/bin/env python3
"""Publish Aider-specific Miles stage evidence without PIE semantics."""

from __future__ import annotations

import argparse
import json

from glm47_posttraining.integrations.wandb_aider_rl import publish_aider_stage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--status", choices=("success", "failed"), required=True)
    parser.add_argument("--rollout-dump-dir", required=True)
    parser.add_argument("--mode", default="online")
    parser.add_argument("--max-records", type=int, default=5000)
    args = parser.parse_args()
    result = publish_aider_stage(
        project=args.project,
        run_id=args.run_id,
        group=args.group,
        stage=args.stage,
        status=args.status,
        rollout_dump_dir=args.rollout_dump_dir,
        mode=args.mode,
        max_records=max(1, args.max_records),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
