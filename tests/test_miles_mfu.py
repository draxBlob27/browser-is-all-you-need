from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from w8_biayn.integrations.miles_mfu import summarize_miles_mfu_trial


SWEEP_RUNNER = Path("scripts/run_miles_h100_mfu_sweep.py")


def _write_trial(root: Path, *, tok_s: float = 1000.0) -> tuple[Path, Path]:
    log = root / "run.log"
    receipt = root / "run_receipt.txt"
    perf_rows = [
        (0, 60.0, 4.0, 200.0),
        (1, 10.0, 20.0, tok_s),
        (2, 10.0, 22.0, tok_s),
        (3, 10.0, 24.0, tok_s),
    ]
    lines = []
    for step, actor_time, tflops, tokens_per_second in perf_rows:
        lines.append(
            "train_metric_utils.py:50 - perf "
            f"{step}: {{'perf/actor_train_time': {actor_time}, "
            f"'perf/actor_train_tflops': {tflops}, "
            f"'perf/actor_train_tok_per_s': {tokens_per_second}, "
            f"'perf/step_time': {actor_time + 2}, 'perf/wait_time_ratio': 0.1}}"
        )
        lines.append(
            f"log_utils.py:463 - step {step}: "
            "{'train/loss': 0.25, 'train/grad_norm': 0.3}"
        )
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    receipt.write_text(
        "status=success\n"
        "ray_status=0\n"
        "wall_s=120\n"
        "max_memory_used_mib=72000\n"
        "seq_length=4096\n"
        "max_tokens_per_gpu=16384\n"
        "global_batch_size=32\n",
        encoding="utf-8",
    )
    return log, receipt


def test_mfu_summary_skips_warmup_and_keeps_miles_per_gpu_units(tmp_path: Path) -> None:
    log, receipt = _write_trial(tmp_path)

    summary = summarize_miles_mfu_trial(
        log_path=log,
        receipt_path=receipt,
        round_number=1,
        name="baseline",
    )

    assert summary["accepted"] is True
    assert summary["steady_steps"] == [1, 2, 3]
    assert summary["steady_token_signature"] == [10000, 10000, 10000]
    assert summary["actor_tflops_per_gpu_median"] == 22.0
    assert summary["estimated_mfu_percent_median"] == pytest.approx(100 * 22 / 989)
    assert summary["bf16_equivalent_mfu_percent_median"] == pytest.approx(100 * 22 / 989)
    assert summary["global_actor_tok_s_median"] == 1000.0


def test_mfu_summary_rejects_train_throughput_regression(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline"
    candidate_root = tmp_path / "candidate"
    baseline_root.mkdir()
    candidate_root.mkdir()
    baseline_log, baseline_receipt = _write_trial(baseline_root)
    candidate_log, candidate_receipt = _write_trial(candidate_root, tok_s=970.0)
    baseline = summarize_miles_mfu_trial(
        log_path=baseline_log,
        receipt_path=baseline_receipt,
        round_number=1,
        name="baseline",
    )

    candidate = summarize_miles_mfu_trial(
        log_path=candidate_log,
        receipt_path=candidate_receipt,
        round_number=2,
        name="candidate",
        baseline=baseline,
    )

    assert candidate["accepted"] is False
    assert candidate["throughput_retention"] == pytest.approx(0.97)
    assert "train_throughput_regression" in candidate["rejection_reasons"]
    assert "fixed_workload_mismatch" in candidate["rejection_reasons"]


def test_mfu_sweep_has_exactly_sixteen_diverse_rounds() -> None:
    namespace = runpy.run_path(str(SWEEP_RUNNER))
    specs = namespace["TRIAL_SPECS"]

    assert [spec.round for spec in specs] == list(range(1, 17))
    assert len({spec.name for spec in specs}) == 16
    assert any("overlap-grad-reduce" in spec.extra_args for spec in specs)
    param_gather = next(spec for spec in specs if "--overlap-param-gather" in spec.extra_args)
    assert "--overlap-grad-reduce" in param_gather.extra_args
    ep_overlap = next(
        spec for spec in specs if "--overlap-moe-expert-parallel-comm" in spec.extra_args
    )
    assert "--delay-wgrad-compute" in ep_overlap.extra_args
    assert any(spec.env.get("MILES_MOE_ENABLE_DEEPEP") == "0" for spec in specs)
    assert any(spec.env.get("MILES_TENSOR_MODEL_PARALLEL_SIZE") == "2" for spec in specs)
    assert any(spec.precision == "fp8" for spec in specs)
    assert specs[-1].adaptive is True


def test_miles_runners_forward_configurable_cuda_connection_count() -> None:
    for path in (
        Path("examples/miles/moonlight_cpp_perf_lora_r16_sft.sh"),
        Path("examples/miles/moonlight_cpp_perf_lora_r16_grpo.sh"),
    ):
        text = path.read_text(encoding="utf-8")
        assert 'CUDA_DEVICE_MAX_CONNECTIONS="${MILES_CUDA_DEVICE_MAX_CONNECTIONS:-1}"' in text
        assert "cuda_device_max_connections=${CUDA_DEVICE_MAX_CONNECTIONS}" in text
        assert "CUDA_DEVICE_MAX_CONNECTIONS" in text
