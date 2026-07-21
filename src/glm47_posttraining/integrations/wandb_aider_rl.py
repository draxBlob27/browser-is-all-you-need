"""Aider-specific W&B payloads with no PIE runtime/speed semantics."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from glm47_posttraining.aider_rl.eval import aggregate_eval_records, zero_variance_group_fraction


AIDER_SAMPLE_TABLE_COLUMNS = (
    "label",
    "task_id",
    "family_id",
    "capability_tags",
    "sample_index",
    "rollout_id",
    "round_number",
    "score",
    "reason",
    "format_valid",
    "allowed_file_compliance",
    "configure_pass",
    "compile_pass",
    "visible_pass",
    "hidden_pass",
    "sanitizer_pass",
    "full_success",
    "candidate_bytes",
    "response",
)

FORBIDDEN_PIE_FIELDS = {
    "runtime_cpu_ns",
    "runtime_wall_ns",
    "reference_runtime_cpu_ns",
    "reference_runtime_wall_ns",
    "runtime_speedup",
    "correct_and_faster_rate",
    "missing_runtime",
}


def build_aider_wandb_payload(
    records: Iterable[dict[str, Any]],
    *,
    label: str,
) -> tuple[dict[str, Any], list[list[Any]]]:
    """Return scalar metrics and a stable sample table for one Aider stage."""

    rows = list(records)
    summary = aggregate_eval_records(rows, label=label)
    summary["zero_variance_group_fraction"] = zero_variance_group_fraction(rows)
    abort_reasons = Counter(
        str(row.get("infrastructure_reason") or row.get("reason") or "unknown")
        for row in rows
        if row.get("infrastructure_error")
    )
    metrics = {
        f"aider_eval/{key}": value
        for key, value in summary.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    metrics.update(
        {f"aider_eval/infrastructure_abort/{reason}": count for reason, count in abort_reasons.items()}
    )
    table_rows = [
        [
            label,
            row.get("task_id"),
            row.get("family_id"),
            ",".join(row.get("capability_tags") or []),
            row.get("sample_index"),
            row.get("rollout_id"),
            row.get("round_number", 1),
            row.get("score"),
            row.get("reason"),
            bool(row.get("format_valid")),
            bool(row.get("allowed_file_compliance")),
            bool(row.get("configure_pass")),
            bool(row.get("compile_pass")),
            bool(row.get("visible_pass")),
            bool(row.get("hidden_pass")),
            bool(row.get("sanitizer_pass")),
            bool(row.get("full_success")),
            row.get("candidate_bytes", 0),
            row.get("response", ""),
        ]
        for row in rows
    ]
    _assert_no_pie_fields(metrics, AIDER_SAMPLE_TABLE_COLUMNS)
    return metrics, table_rows


def publish_aider_eval(
    records: Sequence[dict[str, Any]],
    *,
    label: str,
    project: str,
    run_id: str | None = None,
    group: str | None = None,
) -> None:
    """Publish one Aider evaluation payload when explicitly requested."""

    import wandb

    metrics, rows = build_aider_wandb_payload(records, label=label)
    run = wandb.init(project=project, id=run_id, group=group, resume="allow" if run_id else None)
    run.log(
        {
            **metrics,
            "tables/aider_samples": wandb.Table(columns=list(AIDER_SAMPLE_TABLE_COLUMNS), data=rows),
        }
    )
    run.finish()


def load_aider_rollout_records(
    dump_dir: str | Path, *, max_records: int = 5000
) -> tuple[list[dict[str, Any]], int]:
    """Load Aider reward dictionaries from bounded Miles rollout dumps."""

    root = Path(dump_dir)
    if not root.is_dir():
        return [], 0
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("torch is required to read Miles rollout evidence") from exc
    records: list[dict[str, Any]] = []
    total = 0
    for path in sorted(root.glob("*.pt")):
        try:
            payload = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            payload = torch.load(path, map_location="cpu")
        if not isinstance(payload, dict) or not isinstance(payload.get("samples"), list):
            continue
        rollout_id = payload.get("rollout_id")
        for sample in payload["samples"]:
            if not isinstance(sample, dict):
                continue
            total += 1
            if len(records) >= max_records:
                continue
            reward = sample.get("reward")
            if not isinstance(reward, dict):
                continue
            metadata = sample.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            records.append(
                {
                    **reward,
                    "task_id": reward.get("task_id") or metadata.get("task_id"),
                    "family_id": reward.get("family_id") or metadata.get("family_id"),
                    "capability_tags": reward.get("capability_tags")
                    or metadata.get("capability_tags")
                    or [],
                    "sample_index": reward.get("sample_index", sample.get("index")),
                    "rollout_id": reward.get("rollout_id", rollout_id),
                    "response_tokens": reward.get(
                        "response_tokens", sample.get("response_length")
                    ),
                    "response": sample.get("response", reward.get("response", "")),
                }
            )
    return records, total


def publish_aider_stage(
    *,
    project: str,
    run_id: str,
    group: str,
    stage: str,
    status: str,
    rollout_dump_dir: str | Path,
    mode: str = "online",
    max_records: int = 5000,
) -> dict[str, Any]:
    """Finalize a Miles Aider stage without PIE tags, fields, or promotion gates."""

    import wandb

    records, total = load_aider_rollout_records(rollout_dump_dir, max_records=max_records)
    metrics, rows = build_aider_wandb_payload(records, label=stage)
    metrics.update(
        {
            "aider_stage/records_logged": len(records),
            "aider_stage/records_total": total,
            "aider_stage/success": int(status == "success"),
        }
    )
    run = wandb.init(
        project=project,
        id=run_id,
        group=group,
        job_type=stage,
        mode=mode,
        resume="allow",
        tags=["canonical", "aider-cpp", "one-shot", stage, status],
    )
    payload: dict[str, Any] = dict(metrics)
    if rows:
        payload["tables/aider_samples"] = wandb.Table(
            columns=list(AIDER_SAMPLE_TABLE_COLUMNS), data=rows
        )
    run.log(payload)
    run.finish()
    return {"run_id": run_id, "records_logged": len(records), "records_total": total}


def _assert_no_pie_fields(metrics: dict[str, Any], columns: Sequence[str]) -> None:
    names = set(columns) | {key.rsplit("/", 1)[-1] for key in metrics}
    leaked = names & FORBIDDEN_PIE_FIELDS
    if leaked:
        raise ValueError(f"PIE runtime fields are forbidden in Aider observability: {sorted(leaked)}")
