from pathlib import Path


MODAL_APP = Path("examples/modal/modal_app.py")


def test_modal_runner_records_complete_wandb_pipeline_lineage() -> None:
    source = MODAL_APP.read_text(encoding="utf-8")

    assert '"W8_EXPERIMENT_ID": experiment_id' in source
    assert '"W8_TIMING_STATUS": os.environ.get("W8_TIMING_STATUS", "blocked_issue_13")' in source
    assert '"MILES_WANDB_JOB_TYPE": stage' in source
    assert '"WANDB_RUN_GROUP": experiment_id' in source
    assert '"WANDB_JOB_TYPE": stage' in source
    assert 'event="started", status="started"' in source
    assert 'event="completed"' in source
    assert 'event="failed"' in source
    assert '"status": "failed"' in source
    assert '"status": "success"' in source


def test_modal_eval_passes_experiment_and_timing_metadata() -> None:
    source = MODAL_APP.read_text(encoding="utf-8")

    assert 'f"--wandb-group {env[\'W8_EXPERIMENT_ID\']} --wandb-run-id {rid} "' in source
    assert 'f"--wandb-experiment-id {env[\'W8_EXPERIMENT_ID\']} "' in source
    assert '"--wandb-job-type eval "' in source
    assert 'f"--wandb-timing-status {env[\'W8_TIMING_STATUS\']}"' in source


def test_modal_receipts_exclude_credential_shaped_environment_keys() -> None:
    source = MODAL_APP.read_text(encoding="utf-8")

    assert "and not _is_sensitive_env_key(key)" in source
    assert 'part in {"TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "CREDENTIALS"}' in source
    assert '"experiment_id": captured_env.get("W8_EXPERIMENT_ID", run_id)' in source
