"""Auditable MFU summaries for fixed-work Miles accelerator trials."""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Iterable

from w8_biayn.integrations.wandb_posttraining import (
    parse_miles_metric_events,
    read_key_value,
)


H100_SXM_BF16_PEAK_TFLOPS = 989.0
H100_SXM_FP8_PEAK_TFLOPS = 1979.0
DEFAULT_THROUGHPUT_FLOOR = 0.98
_FAILURE_RE = re.compile(
    r"(?:CUDA out of memory|OutOfMemoryError|RayTaskError)",
    re.IGNORECASE,
)


def summarize_miles_mfu_trial(
    *,
    log_path: str | Path,
    receipt_path: str | Path,
    round_number: int,
    name: str,
    precision: str = "bf16",
    peak_tflops_per_gpu: float = H100_SXM_BF16_PEAK_TFLOPS,
    baseline: dict[str, Any] | None = None,
    throughput_floor: float = DEFAULT_THROUGHPUT_FLOOR,
) -> dict[str, Any]:
    """Summarize one trial and apply fixed-work and train-throughput gates."""

    log_path = Path(log_path)
    receipt_path = Path(receipt_path)
    receipt = read_key_value(receipt_path) if receipt_path.is_file() else {}
    events = parse_miles_metric_events(log_path)
    perf_events = sorted(
        (
            event
            for event in events
            if event["family"] == "perf"
            and "perf/actor_train_time" in event["metrics"]
        ),
        key=lambda event: event["step"],
    )
    # Step zero includes model warmup and kernel/JIT initialization.
    steady_events = perf_events[1:]
    step_events = sorted(
        (event for event in events if event["family"] == "step"),
        key=lambda event: event["step"],
    )

    actor_times = _metric_values(steady_events, "perf/actor_train_time")
    actor_tflops = _metric_values(steady_events, "perf/actor_train_tflops")
    actor_tok_s = _metric_values(steady_events, "perf/actor_train_tok_per_s")
    step_times = _metric_values(steady_events, "perf/step_time")
    wait_ratios = _metric_values(steady_events, "perf/wait_time_ratio")
    losses = _metric_values(step_events, "train/loss")
    grad_norms = _metric_values(step_events, "train/grad_norm")
    token_signature = [
        round(float(event["metrics"]["perf/actor_train_time"])
              * float(event["metrics"]["perf/actor_train_tok_per_s"]))
        for event in steady_events
        if "perf/actor_train_tok_per_s" in event["metrics"]
    ]

    median_tflops = _median(actor_tflops)
    median_tok_s = _median(actor_tok_s)
    summary: dict[str, Any] = {
        "schema_version": 1,
        "round": round_number,
        "name": name,
        "precision": precision,
        "status": str(receipt.get("status") or "missing"),
        "ray_status": receipt.get("ray_status"),
        "wall_s": receipt.get("wall_s"),
        "peak_vram_mib": receipt.get("max_memory_used_mib"),
        "peak_tflops_per_gpu": peak_tflops_per_gpu,
        "warmup_event_count": min(1, len(perf_events)),
        "steady_event_count": len(steady_events),
        "steady_steps": [event["step"] for event in steady_events],
        "steady_token_signature": token_signature,
        "actor_time_s_median": _median(actor_times),
        "actor_time_s_mean": _mean(actor_times),
        "actor_tflops_per_gpu_median": median_tflops,
        "actor_tflops_per_gpu_mean": _mean(actor_tflops),
        "estimated_mfu_median": (
            median_tflops / peak_tflops_per_gpu
            if median_tflops is not None and peak_tflops_per_gpu > 0
            else None
        ),
        "estimated_mfu_percent_median": (
            100.0 * median_tflops / peak_tflops_per_gpu
            if median_tflops is not None and peak_tflops_per_gpu > 0
            else None
        ),
        "bf16_equivalent_mfu_percent_median": (
            100.0 * median_tflops / H100_SXM_BF16_PEAK_TFLOPS
            if median_tflops is not None
            else None
        ),
        "global_actor_tok_s_median": median_tok_s,
        "global_actor_tok_s_mean": _mean(actor_tok_s),
        "step_time_s_median": _median(step_times),
        "wait_ratio_median": _median(wait_ratios),
        "loss_values": losses,
        "grad_norm_values": grad_norms,
        "loss_median": _median(losses),
        "grad_norm_median": _median(grad_norms),
        "config": _receipt_config(receipt),
        "log_path": str(log_path),
        "receipt_path": str(receipt_path),
    }

    rejection_reasons: list[str] = []
    if summary["status"] != "success" or receipt.get("ray_status") not in (0, 0.0):
        rejection_reasons.append("stage_failed")
    if len(steady_events) < 3:
        rejection_reasons.append("insufficient_steady_steps")
    if not actor_tflops or not actor_tok_s:
        rejection_reasons.append("missing_mfu_or_throughput")
    if not _all_finite([*actor_times, *actor_tflops, *actor_tok_s, *losses, *grad_norms]):
        rejection_reasons.append("non_finite_metric")
    if not losses or not grad_norms:
        rejection_reasons.append("missing_loss_or_grad_norm")
    if log_path.is_file() and _FAILURE_RE.search(log_path.read_text(encoding="utf-8", errors="replace")):
        rejection_reasons.append("failure_trace_in_log")

    if baseline is not None:
        baseline_signature = baseline.get("steady_token_signature") or []
        if token_signature != baseline_signature:
            rejection_reasons.append("fixed_workload_mismatch")
        baseline_tok_s = _number(baseline.get("global_actor_tok_s_median"))
        if baseline_tok_s and median_tok_s is not None:
            retention = median_tok_s / baseline_tok_s
            summary["throughput_retention"] = retention
            if retention < throughput_floor:
                rejection_reasons.append("train_throughput_regression")
        else:
            summary["throughput_retention"] = None
        _apply_numerical_envelope(summary, baseline, rejection_reasons)
    else:
        summary["throughput_retention"] = 1.0

    summary["rejection_reasons"] = sorted(set(rejection_reasons))
    summary["accepted"] = not summary["rejection_reasons"]
    return summary


def write_trial_summary(path: str | Path, summary: dict[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def summarize_miles_mfu_sweep(
    root: str | Path,
    *,
    throughput_floor: float = DEFAULT_THROUGHPUT_FLOOR,
) -> dict[str, Any]:
    """Re-gate all numbered trial summaries against round one's fixed baseline."""

    root = Path(root)
    paths = sorted(root.glob("round*/trial_summary.json"))
    trials = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    trials.sort(key=lambda row: int(row["round"]))
    baseline = next((row for row in trials if int(row["round"]) == 1), None)
    if baseline is not None:
        for trial in trials:
            if int(trial["round"]) == 1:
                continue
            _regate_trial(trial, baseline, throughput_floor)
    accepted = [row for row in trials if row.get("accepted")]
    winner = max(
        accepted,
        key=lambda row: _number(row.get("estimated_mfu_median")) or float("-inf"),
        default=None,
    )
    return {
        "schema_version": 1,
        "trial_count": len(trials),
        "accepted_count": len(accepted),
        "throughput_floor": throughput_floor,
        "baseline_round": baseline.get("round") if baseline else None,
        "winner_round": winner.get("round") if winner else None,
        "winner_name": winner.get("name") if winner else None,
        "winner": winner,
        "trials": trials,
    }


def write_sweep_artifacts(root: str | Path, summary: dict[str, Any]) -> dict[str, Path]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    summary_path = root / "sweep_summary.json"
    csv_path = root / "sweep_summary.csv"
    winner_path = root / "best_profile.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = [_flatten_trial(row) for row in summary.get("trials", [])]
    columns = sorted({key for row in rows for key in row})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    winner_path.write_text(
        json.dumps(summary.get("winner") or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"summary": summary_path, "csv": csv_path, "winner": winner_path}


def _metric_values(events: Iterable[dict[str, Any]], metric: str) -> list[float]:
    return [float(event["metrics"][metric]) for event in events if metric in event["metrics"]]


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _all_finite(values: Iterable[float]) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def _receipt_config(receipt: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "seq_length",
        "gpus_per_node",
        "tensor_model_parallel_size",
        "pipeline_model_parallel_size",
        "context_parallel_size",
        "expert_model_parallel_size",
        "expert_tensor_parallel_size",
        "max_tokens_per_gpu",
        "micro_batch_size",
        "use_dynamic_batch_size",
        "balance_data",
        "sft_rollout_shuffle",
        "rollout_batch_size",
        "global_batch_size",
        "no_gradient_accumulation_fusion",
        "recompute_granularity",
        "moe_token_dispatcher_type",
        "moe_enable_deepep",
        "cuda_device_max_connections",
        "extra_args",
    )
    return {key: receipt.get(key) for key in keys if key in receipt}


def _apply_numerical_envelope(
    trial: dict[str, Any],
    baseline: dict[str, Any],
    rejection_reasons: list[str],
) -> None:
    trial_loss = _number(trial.get("loss_median"))
    baseline_loss = _number(baseline.get("loss_median"))
    if trial_loss is not None and baseline_loss is not None:
        loss_scale = max(abs(baseline_loss), 1e-8)
        if abs(trial_loss - baseline_loss) / loss_scale > 0.10:
            rejection_reasons.append("loss_outside_baseline_envelope")
    trial_grad = _number(trial.get("grad_norm_median"))
    baseline_grad = _number(baseline.get("grad_norm_median"))
    if trial_grad is not None and baseline_grad is not None and baseline_grad > 0:
        grad_ratio = trial_grad / baseline_grad
        if not 0.5 <= grad_ratio <= 2.0:
            rejection_reasons.append("grad_norm_outside_baseline_envelope")


def _regate_trial(
    trial: dict[str, Any], baseline: dict[str, Any], throughput_floor: float
) -> None:
    reasons = [
        reason
        for reason in trial.get("rejection_reasons", [])
        if reason
        not in {
            "fixed_workload_mismatch",
            "train_throughput_regression",
            "loss_outside_baseline_envelope",
            "grad_norm_outside_baseline_envelope",
        }
    ]
    if trial.get("steady_token_signature") != baseline.get("steady_token_signature"):
        reasons.append("fixed_workload_mismatch")
    trial_tok_s = _number(trial.get("global_actor_tok_s_median"))
    baseline_tok_s = _number(baseline.get("global_actor_tok_s_median"))
    if trial_tok_s is not None and baseline_tok_s:
        trial["throughput_retention"] = trial_tok_s / baseline_tok_s
        if trial["throughput_retention"] < throughput_floor:
            reasons.append("train_throughput_regression")
    _apply_numerical_envelope(trial, baseline, reasons)
    trial["rejection_reasons"] = sorted(set(reasons))
    trial["accepted"] = not trial["rejection_reasons"]


def _flatten_trial(trial: dict[str, Any]) -> dict[str, Any]:
    row = {
        key: value
        for key, value in trial.items()
        if not isinstance(value, (dict, list))
    }
    row["rejection_reasons"] = ",".join(trial.get("rejection_reasons", []))
    row["steady_token_signature"] = ",".join(
        str(value) for value in trial.get("steady_token_signature", [])
    )
    for key, value in trial.get("config", {}).items():
        row[f"config/{key}"] = value
    return row
