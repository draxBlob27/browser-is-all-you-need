from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from w8_biayn.modal_aider_polyglot_cpp import (
    AIDER_MODEL_NAME,
    BENCHMARK_LABEL,
    INDEPENDENT_EVAL_MODE,
    INDEPENDENT_RESULT_LABEL,
    INDEPENDENT_TRIES,
    ModalAiderConfig,
    ModalAiderError,
    build_artifact_manifest,
    build_independent_pass_report,
    independent_config_fingerprint,
    model_settings,
    sample_seed,
    write_json,
)
from w8_biayn.modal_aider_visualization import generate_visualization_report


def valid_env(**overrides: str) -> dict[str, str]:
    env = {
        "MODAL_TOKEN_ID": "ak-test-sentinel",
        "MODAL_TOKEN_SECRET": "as-test-sentinel",
        "MODAL_PROFILE": "test-profile",
        "W8_MODAL_AIDER_RUN_ID": "glm47-p8b-test",
        "W8_MODAL_AIDER_MODEL_REPO": "zai-org/GLM-4.7-Flash",
        "W8_MODAL_AIDER_MODEL_REVISION": "a" * 40,
        "W8_MODAL_AIDER_AIDER_COMMIT": "b" * 40,
        "W8_MODAL_AIDER_POLYGLOT_COMMIT": "c" * 40,
        "W8_MODAL_AIDER_SGLANG_IMAGE": "lmsysorg/sglang@sha256:" + "d" * 64,
        "W8_MODAL_AIDER_PHASE": "full",
        "W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN": "1",
        "W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8": "1",
        "W8_MODAL_AIDER_EVAL_MODE": INDEPENDENT_EVAL_MODE,
        "W8_MODAL_AIDER_TRIES": "2",
        "W8_MODAL_AIDER_EXPECTED_CPP_TASKS": "3",
        "W8_MODAL_AIDER_MAX_RUN_SECONDS": "14400",
        "W8_MODAL_AIDER_BASE_SEED": "700",
    }
    env.update(overrides)
    return env


def config(tmp_path: Path, **overrides: str) -> ModalAiderConfig:
    return ModalAiderConfig.from_env(valid_env(**overrides), repo_root=tmp_path)


def write_result(
    root: Path,
    task: str,
    *,
    outcomes: list[bool],
    sample_index: int,
    secret: str = "",
) -> None:
    task_root = root / "cpp/exercises/practice" / task
    task_root.mkdir(parents=True)
    payload = {
        "testcase": task,
        "tests_outcomes": outcomes,
        "model": AIDER_MODEL_NAME,
        "edit_format": "whole",
        "prompt_tokens": 100 + sample_index,
        "completion_tokens": 200 + len(task),
        "duration": 30.0 + sample_index,
        "user_asks": len(outcomes),
        "error_outputs": 1 if task.endswith("b") and not any(outcomes) else 0,
        "num_exhausted_context_windows": 1 if task.endswith("c") and not any(outcomes) else 0,
        "syntax_errors": 1 if task.endswith("b") and not any(outcomes) else 0,
        "test_timeouts": 0,
    }
    write_json(task_root / ".aider.results.json", payload)
    (task_root / ".aider.chat.history.md").write_text(
        f"history is hashed only {secret}\n", encoding="utf-8"
    )


def authoritative_stats(tasks: int) -> dict[str, object]:
    return {
        "test_cases": tasks,
        "model": AIDER_MODEL_NAME,
        "edit_format": "whole",
        "pass_rate_1": 12.5,
        "pass_rate_2": 25.0,
    }


def write_sample(
    cfg: ModalAiderConfig,
    protocol: Path,
    sample_index: int,
    tasks: tuple[str, ...],
    *,
    secret: str = "",
) -> Path:
    sample_root = protocol / f"sample-{sample_index:02d}"
    result_root = sample_root / f"run--{cfg.run_id}-sample-{sample_index:02d}"
    settings = model_settings(cfg, sample_index=sample_index)
    sample_root.mkdir(parents=True)
    (sample_root / "model-settings.yml").write_text(settings, encoding="utf-8")
    (sample_root / "model-settings.sha256").write_text(
        hashlib.sha256(settings.encode()).hexdigest() + "\n", encoding="utf-8"
    )
    write_json(
        sample_root / "command.json",
        {
            "sample_index": sample_index,
            "seed": sample_seed(cfg, sample_index),
            "tries": INDEPENDENT_TRIES,
            "config_fingerprint": independent_config_fingerprint(cfg),
        },
    )
    write_json(
        sample_root / "request-metadata.json",
        {"sample_index": sample_index, "seed": sample_seed(cfg, sample_index)},
    )
    write_json(
        sample_root / "fresh-tree.receipt.json",
        {"sample_index": sample_index, "copy_isolated_from_other_samples": True},
    )
    for task in tasks:
        if task == "task-a":
            outcomes = [True] if sample_index <= 2 else [False, sample_index == 3]
        elif task == "task-b":
            outcomes = [False, sample_index in {1, 4}]
        else:
            outcomes = [False, False]
        write_result(result_root, task, outcomes=outcomes, sample_index=sample_index, secret=secret)
    write_json(sample_root / "stats.json", authoritative_stats(len(tasks)))
    (sample_root / "stats.txt").write_text("stats text\n", encoding="utf-8")
    return result_root


def write_root_receipts(
    cfg: ModalAiderConfig,
    root: Path,
    *,
    summary: dict[str, object] | None = None,
) -> None:
    for name in (
        "plan.json",
        "upstreams.json",
        "model-cache.receipt.json",
        "server.receipt.json",
    ):
        write_json(root / name, {"status": "complete"})
    write_json(root / "config.redacted.json", cfg.redacted_mapping())
    write_json(root / "runner.identity.json", {"status": "complete"})
    settings = model_settings(cfg)
    (root / "model-settings.yml").write_text(settings, encoding="utf-8")
    (root / "model-settings.sha256").write_text(
        hashlib.sha256(settings.encode()).hexdigest() + "\n", encoding="utf-8"
    )
    if summary is not None:
        write_json(
            root / "run_receipt.json",
            {
                "status": "complete",
                "benchmark": BENCHMARK_LABEL,
                "eval_mode": INDEPENDENT_EVAL_MODE,
                "result_family": INDEPENDENT_RESULT_LABEL,
                "tries": INDEPENDENT_TRIES,
                "expected_tasks": cfg.expected_cpp_tasks,
                "completed_tasks": cfg.expected_cpp_tasks,
                "completed_trajectories": cfg.expected_cpp_tasks * 8,
                "maximum_edit_attempts": cfg.expected_cpp_tasks * 16,
                "independent_pass_at_1_and_8": summary,
                "modal_app_stopped": True,
                "teardown_status": "verified",
                "model_repo": cfg.model_repo,
                "model_revision": cfg.model_revision,
            },
        )
        write_json(root / "artifact_manifest.json", build_artifact_manifest(root))


def make_fixture(
    tmp_path: Path,
    *,
    sample_count: int,
    final: bool,
    secret: str = "",
) -> tuple[ModalAiderConfig, Path]:
    cfg = config(tmp_path)
    root = cfg.local_run_path(tmp_path)
    protocol = root / INDEPENDENT_EVAL_MODE
    tasks = ("task-a", "task-b", "task-c")
    result_dirs = {
        sample_index: write_sample(cfg, protocol, sample_index, tasks, secret=secret)
        for sample_index in range(1, sample_count + 1)
    }
    if final:
        report = build_independent_pass_report(
            cfg,
            sample_result_dirs=result_dirs,
            out=protocol,
            expected_tasks=len(tasks),
        )
        write_root_receipts(cfg, root, summary=report["summary"])
    else:
        write_root_receipts(cfg, root)
    return cfg, root


def test_final_visualization_generates_report_without_touching_run_tree(tmp_path: Path) -> None:
    _, run_root = make_fixture(tmp_path, sample_count=8, final=True)
    before_manifest = json.loads((run_root / "artifact_manifest.json").read_text(encoding="utf-8"))
    out = tmp_path / ".w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-test"

    report = generate_visualization_report(run_root=run_root, output_root=out)

    assert report["evidence"]["mode"] == "final"
    assert set(report["final_metrics"]) == {
        "pass@1_try1",
        "pass@1_try2",
        "pass@8_try1",
        "pass@8_try2",
    }
    assert (out / "index.html").is_file()
    assert (out / "figures/01-four-metrics.svg").is_file()
    assert (out / "figures/12-evidence-completeness.svg").is_file()
    assert (out / "data/cells.csv").is_file()
    assert json.loads((run_root / "artifact_manifest.json").read_text(encoding="utf-8")) == before_manifest
    rendered = (out / "index.html").read_text(encoding="utf-8")
    assert "pass@2" not in rendered
    manifest = json.loads((out / "visualization_manifest.json").read_text(encoding="utf-8"))
    assert manifest["evidence_mode"] == "final"
    assert all(Path(row["path"]).parts[0] in {"data", "figures"} or row["path"] in {"index.html", "report.md"} for row in manifest["files"])


def test_partial_visualization_is_labeled_and_has_no_final_metric_keys(tmp_path: Path) -> None:
    _, run_root = make_fixture(tmp_path, sample_count=7, final=False)
    out = tmp_path / ".w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-test"

    with pytest.raises(ModalAiderError, match="allow-partial"):
        generate_visualization_report(run_root=run_root, output_root=out)
    report = generate_visualization_report(run_root=run_root, output_root=out, allow_partial=True)

    assert report["evidence"]["mode"] == "partial"
    assert report["final_metrics"] is None
    assert set(report["partial_diagnostics"]) == {
        "observed_trajectory_success_rate_try1",
        "observed_trajectory_success_rate_try2",
        "observed_task_coverage_try1",
        "observed_task_coverage_try2",
    }
    assert "PARTIAL DIAGNOSTIC - 7 OF 8 TRAJECTORIES COMPLETE - NOT PASS@8" in (
        out / "index.html"
    ).read_text(encoding="utf-8")
    assert not (out / "figures/01-four-metrics.svg").exists()
    assert "pass@2" not in (out / "report.md").read_text(encoding="utf-8")


def test_partial_visualization_ignores_incomplete_suffix_sample(tmp_path: Path) -> None:
    _, run_root = make_fixture(tmp_path, sample_count=3, final=False)
    (
        run_root
        / INDEPENDENT_EVAL_MODE
        / "sample-03"
        / "stats.json"
    ).unlink()
    out = tmp_path / ".w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/incomplete-suffix"

    report = generate_visualization_report(run_root=run_root, output_root=out, allow_partial=True)

    assert report["evidence"]["mode"] == "partial"
    assert report["evidence"]["completed_sample_indices"] == [1, 2]
    assert "2 OF 8 TRAJECTORIES COMPLETE" in (out / "index.html").read_text(encoding="utf-8")


def test_visualization_rejects_noncontiguous_prefix_and_run_tree_output(tmp_path: Path) -> None:
    _, run_root = make_fixture(tmp_path, sample_count=3, final=False)
    shutil_target = run_root / INDEPENDENT_EVAL_MODE / "sample-02"
    for path in sorted(shutil_target.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    shutil_target.rmdir()

    with pytest.raises(ModalAiderError, match="contiguous"):
        generate_visualization_report(
            run_root=run_root,
            output_root=tmp_path / ".w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/out",
            allow_partial=True,
        )
    with pytest.raises(ModalAiderError, match="canonical run tree"):
        generate_visualization_report(
            run_root=run_root,
            output_root=run_root / "reports",
            allow_partial=True,
        )


def test_visualization_does_not_embed_chat_history_or_overwrite_arbitrary_output(
    tmp_path: Path,
) -> None:
    secret = "SECRET_SENTINEL_VALUE"
    _, run_root = make_fixture(tmp_path, sample_count=1, final=False, secret=secret)
    out = tmp_path / ".w8-biayn/modal/glm47-flash-aider-polyglot-cpp/reports/glm47-p8b-test"
    report = generate_visualization_report(
        run_root=run_root,
        output_root=out,
        allow_partial=True,
        secret_sentinels=[secret],
    )
    assert report["evidence"]["completed_samples"] == 1
    for path in out.rglob("*"):
        if path.is_file():
            assert secret not in path.read_text(encoding="utf-8")

    with pytest.raises(ModalAiderError, match="already exists"):
        generate_visualization_report(run_root=run_root, output_root=out, allow_partial=True)
    (tmp_path / "not-a-report").mkdir()
    (tmp_path / "not-a-report/file.txt").write_text("user data\n", encoding="utf-8")
    with pytest.raises(ModalAiderError, match="visualization manifest"):
        generate_visualization_report(
            run_root=run_root,
            output_root=tmp_path / "not-a-report",
            allow_partial=True,
            overwrite=True,
        )
