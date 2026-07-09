"""Canonical W&B observability for PIE C++ post-training runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from w8_biayn.cpp_perf.eval import compare_eval_summaries

MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
ALLOWED_ARTIFACT_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".txt",
}
SENSITIVE_KEY_RE = re.compile(
    r"(?:^|[_-])(?:api[_-]?key|access[_-]?token|token|secret|password|credential|"
    r"private[_-]?key|ssh[_-]?key)(?:$|[_-])",
    re.IGNORECASE,
)
SENSITIVE_PATH_RE = re.compile(
    r"(?:^|[._-])(?:api[_-]?keys?|credentials?|netrc|passwords?|private[_-]?key|"
    r"secrets?|tokens?)(?:$|[._-])",
    re.IGNORECASE,
)
SENSITIVE_CONTENT_KEY_RE = re.compile(
    r"(?:^|[_-])(?:api[_-]?key|access[_-]?token|auth[_-]?token|token[_-]?secret|"
    r"secret|password|credential|private[_-]?key|ssh[_-]?key)(?:$|[_-])",
    re.IGNORECASE,
)
URL_CREDENTIAL_RE = re.compile(r"(://)[^/@\s:]+:[^/@\s]+@")
ASSIGNMENT_RE = re.compile(r"\b([a-zA-Z][a-zA-Z0-9_.-]*)\s*([=:])\s*([^\s,;]+)")

EVAL_TABLE_COLUMNS = (
    "experiment_id",
    "timing_status",
    "label",
    "task_id",
    "problem_id",
    "split",
    "sample_index",
    "reason",
    "reward",
    "all_tests_pass",
    "tests_passed",
    "tests_total",
    "compile_error",
    "sanitizer_error",
    "timeout",
    "runtime_cpu_ns",
    "reference_runtime_cpu_ns",
    "runtime_speedup",
    "completion_tokens",
    "prompt_tokens",
    "truncated",
    "finish_reason",
    "response_preview",
)

FAILURE_TABLE_COLUMNS = (
    "experiment_id",
    "label",
    "split",
    "bucket",
    "count",
    "rate",
)

COMPARISON_TABLE_COLUMNS = (
    "experiment_id",
    "timing_status",
    "label",
    "task_count",
    "sample_count",
    "pass_rate",
    "valid_format_rate",
    "correct_and_faster_rate",
    "mean_best_reward",
    "mean_correct_faster_speedup",
    "missing_runtime_count",
    "missing_runtime_rate",
    "compile_error_rate",
    "sanitizer_error_rate",
    "timeout_rate",
    "truncated_ratio",
    "mean_completion_tokens",
)

PIPELINE_TABLE_COLUMNS = (
    "experiment_id",
    "event_time_unix",
    "stage",
    "event",
    "status",
    "wall_s",
    "repo_sha",
    "image",
    "receipt",
    "error",
)

CURATED_STAGE_METRIC_TERMS = (
    "accuracy",
    "correct_and_faster",
    "entropy",
    "grad_norm",
    "kl",
    "learning_rate",
    "loss",
    "mfu",
    "pass_rate",
    "passrate",
    "response_length",
    "reward",
    "throughput",
    "tokens_per",
)


def safe_identifier(value: str, *, fallback: str = "run") -> str:
    """Return a W&B-safe stable identifier."""

    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-.")
    return (cleaned or fallback)[:120]


def resolve_experiment_id(*, explicit: str = "", run_id: str = "", label: str = "") -> str:
    value = explicit or os.environ.get("W8_EXPERIMENT_ID", "") or run_id or label
    return safe_identifier(value, fallback="pie-cpp-posttraining")


def redact_sensitive(value: Any, *, key: str = "") -> Any:
    """Recursively redact secrets while preserving metric and config structure."""

    if key and SENSITIVE_KEY_RE.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            str(item_key): redact_sensitive(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        redacted = URL_CREDENTIAL_RE.sub(r"\1<redacted>@", value)
        return ASSIGNMENT_RE.sub(_redact_assignment, redacted)
    return value


def read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"expected JSON object row: {path}")
            rows.append(row)
    return rows


def read_key_value(path: str | Path) -> dict[str, Any]:
    values: dict[str, Any] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if "=" not in line:
                continue
            key, value = line.rstrip("\n").split("=", 1)
            values[key] = _coerce_scalar(value)
    return values


def build_eval_table_rows(
    records: Iterable[dict[str, Any]],
    generations: Iterable[dict[str, Any]],
    *,
    experiment_id: str,
    timing_status: str,
) -> list[list[Any]]:
    generation_by_key = {
        _sample_key(row): row
        for row in generations
    }
    rows: list[list[Any]] = []
    for record in records:
        generation = generation_by_key.get(_sample_key(record), {})
        rows.append(
            [
                experiment_id,
                timing_status,
                record.get("label") or generation.get("label"),
                record.get("task_id") or generation.get("task_id"),
                record.get("problem_id") or generation.get("problem_id"),
                record.get("split") or generation.get("split"),
                _int_or_none(record.get("sample_index", generation.get("sample_index"))),
                record.get("reason"),
                _number_or_none(record.get("reward")),
                record.get("all_tests_pass"),
                _int_or_none(record.get("tests_passed")),
                _int_or_none(record.get("tests_total")),
                bool(record.get("compile_error", False)),
                bool(record.get("sanitizer_error", False)),
                bool(record.get("timeout", False)),
                _int_or_none(record.get("runtime_cpu_ns")),
                _int_or_none(record.get("reference_runtime_cpu_ns")),
                _number_or_none(record.get("runtime_speedup")),
                _int_or_none(generation.get("completion_tokens")),
                _int_or_none(generation.get("prompt_tokens")),
                generation.get("truncated"),
                generation.get("finish_reason"),
                _preview(generation.get("response")),
            ]
        )
    return rows


def build_failure_bucket_rows(
    records: Iterable[dict[str, Any]],
    *,
    experiment_id: str,
) -> list[list[Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    totals: Counter[tuple[str, str]] = Counter()
    for record in records:
        label = str(record.get("label") or "unknown")
        split = str(record.get("split") or "unknown")
        bucket = _failure_bucket(record)
        counts[(label, split, bucket)] += 1
        totals[(label, split)] += 1
    return [
        [
            experiment_id,
            label,
            split,
            bucket,
            count,
            count / totals[(label, split)] if totals[(label, split)] else 0.0,
        ]
        for (label, split, bucket), count in sorted(counts.items())
    ]


def build_comparison_table_rows(
    summaries: Iterable[dict[str, Any]],
    *,
    experiment_id: str,
    timing_status: str,
) -> list[list[Any]]:
    return [
        [
            experiment_id,
            timing_status,
            summary.get("label"),
            summary.get("task_count"),
            summary.get("sample_count"),
            summary.get("pass_rate"),
            summary.get("valid_format_rate"),
            summary.get("correct_and_faster_rate"),
            summary.get("mean_best_reward"),
            summary.get("mean_correct_faster_speedup"),
            summary.get("missing_runtime_count"),
            summary.get("missing_runtime_rate"),
            summary.get("compile_error_rate"),
            summary.get("sanitizer_error_rate"),
            summary.get("timeout_rate"),
            summary.get("truncated_ratio"),
            summary.get("mean_completion_tokens"),
        ]
        for summary in summaries
    ]


def select_artifact_paths(paths: Iterable[str | Path]) -> tuple[list[Path], list[dict[str, str]]]:
    selected: list[Path] = []
    skipped: list[dict[str, str]] = []
    seen: set[Path] = set()
    for item in paths:
        path = Path(item)
        if path in seen:
            continue
        seen.add(path)
        reason = _artifact_skip_reason(path)
        if reason:
            skipped.append({"name": path.name, "reason": reason})
        else:
            selected.append(path)
    return selected, skipped


def write_artifact_manifest(
    output_path: str | Path,
    paths: Iterable[str | Path],
) -> tuple[Path, list[Path]]:
    selected, skipped = select_artifact_paths(paths)
    payload = {
        "schema_version": 1,
        "files": [
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in selected
        ],
        "skipped": skipped,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output, selected


def log_eval_run(
    wandb_module: Any,
    *,
    project: str,
    entity: str | None,
    experiment_id: str,
    run_id: str,
    name: str,
    group: str,
    job_type: str,
    mode: str,
    timing_status: str,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
    generations: list[dict[str, Any]],
    config: dict[str, Any],
    artifact_paths: Iterable[str | Path],
    manifest_dir: str | Path,
    tags: Iterable[str] = (),
) -> dict[str, str]:
    safe_experiment = resolve_experiment_id(explicit=experiment_id, run_id=run_id)
    safe_run = safe_identifier(run_id, fallback=f"{safe_experiment}-eval")
    label = str(summary.get("label") or config.get("label") or "eval")
    run = wandb_module.init(
        project=project,
        entity=entity or None,
        id=safe_run,
        name=name or safe_run,
        group=group or safe_experiment,
        job_type=job_type or "eval",
        mode=mode,
        resume="allow",
        tags=sorted(set(["canonical", "pie-cpp", label, timing_status, *tags])),
        config=redact_sensitive(
            {
                **config,
                "experiment_id": safe_experiment,
                "timing_status": timing_status,
                "proof_surface_schema": 1,
            }
        ),
    )
    _define_metric(run, "eval/index")
    _define_metric(run, "eval/*", step_metric="eval/index")

    scalar_metrics = {
        key: value
        for key, value in summary.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }
    payload: dict[str, Any] = {
        "eval/index": 0,
        **{f"eval/{key}": value for key, value in scalar_metrics.items()},
        "tables/eval_samples": wandb_module.Table(
            columns=list(EVAL_TABLE_COLUMNS),
            data=build_eval_table_rows(
                records,
                generations,
                experiment_id=safe_experiment,
                timing_status=timing_status,
            ),
        ),
        "tables/failure_buckets": wandb_module.Table(
            columns=list(FAILURE_TABLE_COLUMNS),
            data=build_failure_bucket_rows(records, experiment_id=safe_experiment),
        ),
    }
    run.log(payload)
    _set_summary(
        run,
        {
            **summary,
            "observability/experiment_id": safe_experiment,
            "observability/schema_version": 1,
            "observability/timing_status": timing_status,
            "stage/job_type": job_type or "eval",
            "stage/status": summary.get("status") or "success",
        },
    )

    manifest_path, selected = write_artifact_manifest(
        Path(manifest_dir) / f"{safe_run}.artifact_manifest.json",
        artifact_paths,
    )
    artifact = wandb_module.Artifact(
        safe_identifier(f"{safe_experiment}-{label}-eval"),
        type="eval",
        metadata=redact_sensitive(
            {
                "experiment_id": safe_experiment,
                "label": label,
                "timing_status": timing_status,
            }
        ),
    )
    for path in [*selected, manifest_path]:
        artifact.add_file(str(path), name=path.name)
    run.log_artifact(artifact)
    result = {"run_id": str(getattr(run, "id", safe_run)), "url": str(getattr(run, "url", ""))}
    run.finish()
    return result


def log_comparison_run(
    wandb_module: Any,
    *,
    project: str,
    entity: str | None,
    experiment_id: str,
    run_id: str,
    mode: str,
    timing_status: str,
    summaries: list[dict[str, Any]],
    summary_paths: Iterable[str | Path],
    output_dir: str | Path,
) -> dict[str, str]:
    safe_experiment = resolve_experiment_id(explicit=experiment_id, run_id=run_id)
    safe_run = safe_identifier(run_id, fallback=f"{safe_experiment}-comparison")
    comparison = compare_eval_summaries(summaries)
    comparison["experiment_id"] = safe_experiment
    comparison["timing_status"] = timing_status
    output_path = Path(output_dir) / f"{safe_run}.comparison.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    run = wandb_module.init(
        project=project,
        entity=entity or None,
        id=safe_run,
        name=safe_run,
        group=safe_experiment,
        job_type="comparison",
        mode=mode,
        resume="allow",
        tags=["canonical", "pie-cpp", "comparison", timing_status],
        config={
            "experiment_id": safe_experiment,
            "timing_status": timing_status,
            "labels": [summary.get("label") for summary in summaries],
            "proof_surface_schema": 1,
        },
    )
    payload: dict[str, Any] = {
        "tables/checkpoint_comparison": wandb_module.Table(
            columns=list(COMPARISON_TABLE_COLUMNS),
            data=build_comparison_table_rows(
                summaries,
                experiment_id=safe_experiment,
                timing_status=timing_status,
            ),
        )
    }
    for summary in summaries:
        label = safe_identifier(str(summary.get("label") or "unknown"))
        for key, value in summary.items():
            if isinstance(value, int | float) and not isinstance(value, bool):
                payload[f"comparison/{label}/{key}"] = value
    run.log(payload)
    _set_summary(
        run,
        {
            "observability/experiment_id": safe_experiment,
            "observability/timing_status": timing_status,
            "comparison/uplift_gate": comparison.get("uplift_gate"),
            "comparison/best_correct_and_faster": comparison.get("best_correct_and_faster"),
            "comparison/best_mean_reward": comparison.get("best_mean_reward"),
        },
    )
    manifest_path, selected = write_artifact_manifest(
        Path(output_dir) / f"{safe_run}.artifact_manifest.json",
        [*summary_paths, output_path],
    )
    artifact = wandb_module.Artifact(
        safe_identifier(f"{safe_experiment}-comparison"),
        type="comparison",
        metadata={"experiment_id": safe_experiment, "timing_status": timing_status},
    )
    for path in [*selected, manifest_path]:
        artifact.add_file(str(path), name=path.name)
    run.log_artifact(artifact)
    result = {"run_id": str(getattr(run, "id", safe_run)), "url": str(getattr(run, "url", ""))}
    run.finish()
    return result


def log_stage_finalization(
    wandb_module: Any,
    *,
    project: str,
    entity: str | None,
    experiment_id: str,
    run_id: str,
    group: str,
    stage: str,
    status: str,
    mode: str,
    timing_status: str,
    receipt: str | Path,
    artifact_paths: Iterable[str | Path],
    manifest_dir: str | Path,
) -> dict[str, str]:
    safe_experiment = resolve_experiment_id(explicit=experiment_id, run_id=run_id)
    safe_run = safe_identifier(run_id, fallback=f"{safe_experiment}-{stage}")
    safe_stage = safe_identifier(stage, fallback="stage")
    receipt_path = Path(receipt)
    receipt_values = read_key_value(receipt_path)
    run = wandb_module.init(
        project=project,
        entity=entity or None,
        id=safe_run,
        name=safe_run,
        group=group or safe_experiment,
        job_type=safe_stage,
        mode=mode,
        resume="allow",
        tags=["canonical", "pie-cpp", safe_stage, status, timing_status],
        config=redact_sensitive(
            {
                "experiment_id": safe_experiment,
                "timing_status": timing_status,
                "proof_surface_schema": 1,
                "stage_receipt": receipt_values,
            }
        ),
    )
    existing_summary = dict(getattr(run, "summary", {}))
    curated_metrics = _curate_stage_metrics(existing_summary)
    wall_s = _number_or_none(receipt_values.get("wall_s"))
    peak_vram = _number_or_none(receipt_values.get("max_memory_used_mib"))
    checkpoint = str(receipt_values.get("save_dir") or "")
    run.log(
        {
            "stage/finalized": 1,
            "stage/wall_s": wall_s or 0.0,
            "stage/max_memory_used_mib": peak_vram or 0.0,
            **curated_metrics,
        }
    )
    _set_summary(
        run,
        {
            "observability/experiment_id": safe_experiment,
            "observability/schema_version": 1,
            "observability/timing_status": timing_status,
            "stage/job_type": safe_stage,
            "stage/status": status,
            "stage/wall_s": wall_s,
            "stage/max_memory_used_mib": peak_vram,
            "stage/checkpoint_or_adapter": checkpoint,
            "stage/receipt": receipt_path.name,
            **curated_metrics,
        },
    )
    manifest_path, selected = write_artifact_manifest(
        Path(manifest_dir) / f"{safe_run}.artifact_manifest.json",
        [receipt_path, *artifact_paths],
    )
    artifact = wandb_module.Artifact(
        safe_identifier(f"{safe_experiment}-{safe_stage}-run"),
        type="stage-run",
        metadata={
            "experiment_id": safe_experiment,
            "stage": safe_stage,
            "status": status,
            "timing_status": timing_status,
        },
    )
    for path in [*selected, manifest_path]:
        artifact.add_file(str(path), name=path.name)
    run.log_artifact(artifact)
    _set_summary(run, {"stage/artifact_file_count": len(selected)})
    result = {"run_id": str(getattr(run, "id", safe_run)), "url": str(getattr(run, "url", ""))}
    run.finish()
    return result


def log_pipeline_milestone(
    wandb_module: Any,
    *,
    project: str,
    entity: str | None,
    experiment_id: str,
    stage: str,
    event: str,
    status: str,
    mode: str,
    run_id: str = "",
    wall_s: float | None = None,
    repo_sha: str = "",
    image: str = "",
    receipt: str | Path | None = None,
    error: str = "",
    event_time: float | None = None,
) -> dict[str, str]:
    safe_experiment = resolve_experiment_id(explicit=experiment_id)
    safe_stage = safe_identifier(stage, fallback="stage")
    safe_event = safe_identifier(event, fallback="event")
    resolved_run_id = safe_identifier(run_id or f"{safe_experiment}-pipeline")
    now = event_time if event_time is not None else time.time()
    receipt_path = Path(receipt) if receipt else None
    receipt_name = receipt_path.name if receipt_path and receipt_path.exists() else ""
    safe_error = str(redact_sensitive(error))[:1000]
    run = wandb_module.init(
        project=project,
        entity=entity or None,
        id=resolved_run_id,
        name=resolved_run_id,
        group=safe_experiment,
        job_type="pipeline",
        mode=mode,
        resume="allow",
        tags=["canonical", "pie-cpp", "pipeline"],
        config={"experiment_id": safe_experiment, "proof_surface_schema": 1},
    )
    _define_metric(run, "pipeline/event_time_unix")
    status_code = {"started": 0, "success": 1, "failed": -1}.get(status, 0)
    run.log(
        {
            "pipeline/event_time_unix": now,
            "pipeline/wall_s": wall_s or 0.0,
            "pipeline/status_code": status_code,
            "pipeline/stage": safe_stage,
            "pipeline/event": safe_event,
            f"pipeline/events/{safe_stage}/{safe_event}": 1,
            f"tables/pipeline_{safe_stage}_{safe_event}": wandb_module.Table(
                columns=list(PIPELINE_TABLE_COLUMNS),
                data=[
                    [
                        safe_experiment,
                        now,
                        safe_stage,
                        safe_event,
                        status,
                        wall_s,
                        repo_sha,
                        image,
                        receipt_name,
                        safe_error,
                    ]
                ],
            ),
        }
    )
    _set_summary(
        run,
        {
            "observability/experiment_id": safe_experiment,
            "pipeline/latest_stage": safe_stage,
            "pipeline/latest_event": safe_event,
            "pipeline/latest_status": status,
            "pipeline/latest_event_unix": now,
            f"pipeline/{safe_stage}/status": status,
            f"pipeline/{safe_stage}/wall_s": wall_s,
            f"pipeline/{safe_stage}/repo_sha": repo_sha,
            f"pipeline/{safe_stage}/image": image,
        },
    )
    if receipt_path and receipt_path.exists():
        manifest_path, selected = write_artifact_manifest(
            receipt_path.parent / f"{safe_stage}-{safe_event}.artifact_manifest.json",
            [receipt_path],
        )
        artifact = wandb_module.Artifact(
            safe_identifier(f"{safe_experiment}-{safe_stage}-{safe_event}"),
            type="stage-receipt",
            metadata={
                "experiment_id": safe_experiment,
                "stage": safe_stage,
                "event": safe_event,
                "status": status,
            },
        )
        for path in [*selected, manifest_path]:
            artifact.add_file(str(path), name=path.name)
        run.log_artifact(artifact)
    result = {
        "run_id": str(getattr(run, "id", resolved_run_id)),
        "url": str(getattr(run, "url", "")),
    }
    run.finish()
    return result


def _sample_key(row: dict[str, Any]) -> tuple[str, int]:
    return str(row.get("task_id") or ""), int(row.get("sample_index") or 0)


def _failure_bucket(record: dict[str, Any]) -> str:
    reason = str(record.get("reason") or "").strip()
    if reason:
        return reason
    if record.get("compile_error") is True:
        return "compile_error"
    if record.get("sanitizer_error") is True:
        return "sanitizer_error"
    if record.get("timeout") is True:
        return "timeout"
    if record.get("all_tests_pass") is True:
        return "correct"
    return "tests_failed"


def _preview(value: Any, *, limit: int = 4000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _number_or_none(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_scalar(value: str) -> Any:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:e[+-]?\d+)?", stripped, re.IGNORECASE):
        return float(stripped)
    return stripped


def _curate_stage_metrics(summary: dict[str, Any]) -> dict[str, int | float]:
    curated: dict[str, int | float] = {}
    for key, value in sorted(summary.items()):
        if key.startswith("_") or isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if any(term in key.lower() for term in CURATED_STAGE_METRIC_TERMS):
            curated[f"stage/final_metrics/{safe_identifier(key)}"] = value
        if len(curated) >= 32:
            break
    return curated


def _artifact_skip_reason(path: Path) -> str:
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "not_file"
    if path.is_symlink():
        return "symlink"
    if any(SENSITIVE_PATH_RE.search(part) for part in path.parts):
        return "sensitive_name"
    if path.suffix.lower() not in ALLOWED_ARTIFACT_SUFFIXES:
        return "unsupported_suffix"
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        return "too_large"
    if _contains_sensitive_content(path):
        return "sensitive_content"
    return ""


def _contains_sensitive_content(path: Path) -> bool:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            assignments = ASSIGNMENT_RE.finditer(line)
            if URL_CREDENTIAL_RE.search(line) or any(
                SENSITIVE_CONTENT_KEY_RE.search(match.group(1)) and match.group(3) != "<redacted>"
                for match in assignments
            ):
                return True
    return False


def _redact_assignment(match: re.Match[str]) -> str:
    if SENSITIVE_KEY_RE.search(match.group(1)):
        return f"{match.group(1)}{match.group(2)}<redacted>"
    return match.group(0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _define_metric(run: Any, name: str, **kwargs: Any) -> None:
    define = getattr(run, "define_metric", None)
    if callable(define):
        define(name, **kwargs)


def _set_summary(run: Any, values: dict[str, Any]) -> None:
    for key, value in redact_sensitive(values).items():
        if value is not None:
            run.summary[key] = value
