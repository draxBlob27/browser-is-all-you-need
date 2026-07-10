#!/usr/bin/env python3
"""Publish a completed Miles H100 MFU sweep as a canonical W&B comparison run."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from w8_biayn.integrations.wandb_posttraining import (  # noqa: E402
    safe_identifier,
    write_artifact_manifest,
)


TABLE_COLUMNS = (
    "round",
    "name",
    "hypothesis",
    "accepted",
    "rejection_reasons",
    "precision",
    "estimated_mfu_percent_median",
    "bf16_equivalent_mfu_percent_median",
    "actor_tflops_per_gpu_median",
    "global_actor_tok_s_median",
    "throughput_retention",
    "actor_time_s_median",
    "step_time_s_median",
    "wait_ratio_median",
    "peak_vram_mib",
    "loss_median",
    "grad_norm_median",
    "config_json",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep-root", required=True)
    parser.add_argument("--project", default=os.environ.get("WANDB_PROJECT", ""), required=False)
    parser.add_argument("--entity", default=os.environ.get("WANDB_ENTITY", ""))
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--group", default="")
    parser.add_argument("--mode", choices=("online", "offline"), default="online")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.project:
        raise SystemExit("--project or WANDB_PROJECT is required")
    try:
        import wandb
    except ImportError as exc:
        raise SystemExit("wandb is required to publish the MFU sweep") from exc

    root = Path(args.sweep_root).resolve()
    summary_path = root / "sweep_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    trials = sorted(summary.get("trials", []), key=lambda row: int(row["round"]))
    if len(trials) != 16:
        raise SystemExit(f"refusing incomplete sweep publication: expected 16 trials, got {len(trials)}")

    run_id = safe_identifier(args.run_id or f"{args.experiment_id}-mfu-sweep")
    run = wandb.init(
        project=args.project,
        entity=args.entity or None,
        id=run_id,
        name=run_id,
        group=args.group or args.experiment_id,
        job_type="mfu-sweep",
        mode=args.mode,
        resume="allow",
        tags=["canonical", "pie-cpp", "mfu-sweep", "8xh100"],
        config={
            "experiment_id": args.experiment_id,
            "proof_surface_schema": 1,
            "trial_count": len(trials),
            "throughput_floor": summary.get("throughput_floor"),
            "mfu_definition": "Miles active-MoE train TFLOP/s/GPU divided by measured precision peak",
        },
    )
    rows = [_table_row(trial) for trial in trials]
    run.log({"tables/mfu_trials": wandb.Table(columns=list(TABLE_COLUMNS), data=rows)})
    for trial in trials:
        run.log(
            {
                "sweep/round": trial["round"],
                "sweep/accepted": int(bool(trial.get("accepted"))),
                "sweep/estimated_mfu_percent": trial.get("estimated_mfu_percent_median"),
                "sweep/bf16_equivalent_mfu_percent": trial.get(
                    "bf16_equivalent_mfu_percent_median"
                ),
                "sweep/actor_tflops_per_gpu": trial.get("actor_tflops_per_gpu_median"),
                "sweep/global_actor_tok_s": trial.get("global_actor_tok_s_median"),
                "sweep/throughput_retention": trial.get("throughput_retention"),
                "sweep/peak_vram_mib": trial.get("peak_vram_mib"),
            }
        )
    winner = summary.get("winner") or {}
    run.summary.update(
        {
            "observability/experiment_id": args.experiment_id,
            "observability/schema_version": 1,
            "stage/status": "success",
            "sweep/trial_count": len(trials),
            "sweep/accepted_count": summary.get("accepted_count"),
            "sweep/winner_round": summary.get("winner_round"),
            "sweep/winner_name": summary.get("winner_name"),
            "sweep/winner_estimated_mfu_percent": winner.get("estimated_mfu_percent_median"),
            "sweep/winner_actor_tflops_per_gpu": winner.get("actor_tflops_per_gpu_median"),
            "sweep/winner_global_actor_tok_s": winner.get("global_actor_tok_s_median"),
            "sweep/winner_throughput_retention": winner.get("throughput_retention"),
        }
    )

    candidates = [
        root / "sweep_summary.json",
        root / "sweep_summary.csv",
        root / "best_profile.json",
        root / "solution_space.json",
        root / "hardware.json",
        *root.glob("round*/trial_summary.json"),
        *root.glob("round*/trial_spec.json"),
    ]
    manifest_path, selected = write_artifact_manifest(root / "wandb_artifact_manifest.json", candidates)
    artifact = wandb.Artifact(
        safe_identifier(f"{args.experiment_id}-mfu-sweep"),
        type="mfu-sweep",
        metadata={
            "experiment_id": args.experiment_id,
            "trial_count": len(trials),
            "winner_round": summary.get("winner_round"),
        },
    )
    for path in [*selected, manifest_path]:
        artifact.add_file(str(path), name=str(path.relative_to(root)))
    run.log_artifact(artifact)
    receipt = {"run_id": str(run.id), "url": str(run.url), "trial_count": len(trials)}
    (root / "wandb_publish_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    run.finish()
    print(json.dumps(receipt, sort_keys=True))
    return 0


def _table_row(trial: dict[str, Any]) -> list[Any]:
    values = {
        **trial,
        "rejection_reasons": ",".join(trial.get("rejection_reasons", [])),
        "config_json": json.dumps(trial.get("config", {}), sort_keys=True),
    }
    return [values.get(column) for column in TABLE_COLUMNS]


if __name__ == "__main__":
    raise SystemExit(main())
