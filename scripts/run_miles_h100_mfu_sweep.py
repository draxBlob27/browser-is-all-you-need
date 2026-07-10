#!/usr/bin/env python3
"""Run the fixed-work 16-round GLM-4.7-Flash Miles MFU sweep."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from w8_biayn.integrations.miles_mfu import (  # noqa: E402
    H100_SXM_BF16_PEAK_TFLOPS,
    H100_SXM_FP8_PEAK_TFLOPS,
    summarize_miles_mfu_sweep,
    summarize_miles_mfu_trial,
    write_sweep_artifacts,
    write_trial_summary,
)


@dataclass(frozen=True)
class TrialSpec:
    round: int
    name: str
    hypothesis: str
    env: dict[str, str]
    extra_args: str = ""
    precision: str = "bf16"
    peak_tflops_per_gpu: float = H100_SXM_BF16_PEAK_TFLOPS
    adaptive: bool = False


TRIAL_SPECS = (
    TrialSpec(1, "baseline", "Reproduce the selected TP4/EP8 BF16 profile.", {}),
    TrialSpec(
        2,
        "no_recompute_16k",
        "Trade activation memory for less recomputation at the selected token cap.",
        {"MILES_RECOMPUTE_GRANULARITY": "none"},
    ),
    TrialSpec(
        3,
        "selective_17k",
        "Increase packed work per microbatch within measured H100 headroom.",
        {"MILES_MAX_TOKENS_PER_GPU": "17408"},
    ),
    TrialSpec(
        4,
        "grad_accum_fusion",
        "Use Megatron's fused LoRA gradient accumulation path.",
        {"MILES_NO_GRADIENT_ACCUMULATION_FUSION": "0"},
    ),
    TrialSpec(
        5,
        "overlap_grad_reduce",
        "Overlap data-parallel gradient reduction with backward compute.",
        {},
        "--overlap-grad-reduce",
    ),
    TrialSpec(
        6,
        "ddp_overlap",
        "Overlap both required distributed-optimizer collectives with compute.",
        {},
        "--overlap-grad-reduce --overlap-param-gather",
    ),
    TrialSpec(
        7,
        "ddp_tp_overlap",
        "Test whether DP and TP communication overlap compose on one NVSwitch node.",
        {},
        "--overlap-grad-reduce --overlap-param-gather --tp-comm-overlap",
    ),
    TrialSpec(
        8,
        "moe_ep_overlap",
        "Overlap expert-parallel communication with delayed weight-gradient compute.",
        {},
        "--overlap-moe-expert-parallel-comm --delay-wgrad-compute",
    ),
    TrialSpec(
        9,
        "tp_comm_overlap",
        "Use Transformer Engine user-buffer overlap for TP4 collectives.",
        {},
        "--tp-comm-overlap",
    ),
    TrialSpec(
        10,
        "kernel_fusions",
        "Fuse shared-expert, router, and vocabulary-loss hot paths.",
        {},
        "--moe-shared-expert-overlap --moe-router-fusion --cross-entropy-loss-fusion",
    ),
    TrialSpec(
        11,
        "cuda_connections_8",
        "Allow more concurrent CUDA work queues instead of forcing one connection.",
        {"MILES_CUDA_DEVICE_MAX_CONNECTIONS": "8"},
    ),
    TrialSpec(
        12,
        "alltoall_no_deepep",
        "Measure standard all-to-all dispatch against DeepEP flex on this topology.",
        {
            "MILES_MOE_TOKEN_DISPATCHER_TYPE": "alltoall",
            "MILES_MOE_ENABLE_DEEPEP": "0",
        },
    ),
    TrialSpec(
        13,
        "tp2_ep8",
        "Reduce tensor-parallel communication and increase data parallelism.",
        {"MILES_TENSOR_MODEL_PARALLEL_SIZE": "2"},
    ),
    TrialSpec(
        14,
        "te_fp8_blockwise",
        "Use Hopper FP8 Tensor Cores through Transformer Engine blockwise training.",
        {},
        "--fp8-format e4m3 --fp8-recipe blockwise",
        precision="fp8",
        peak_tflops_per_gpu=H100_SXM_FP8_PEAK_TFLOPS,
    ),
    TrialSpec(
        15,
        "adaptive_winner_combo",
        "Combine only independently measured, compatible improvements.",
        {},
        adaptive=True,
    ),
    TrialSpec(
        16,
        "adaptive_winner_repeat",
        "Repeat the promoted candidate from a clean process and base checkpoint.",
        {},
        adaptive=True,
    ),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep-root", required=True)
    parser.add_argument("--rounds", default="1-14")
    parser.add_argument(
        "--runner",
        default=str(REPO_ROOT / "examples/miles/glm47_cpp_perf_lora_r16_h100_sft.sh"),
    )
    parser.add_argument("--data-dir", default="/data/glm47-pie-profile-long128-oracle-v2")
    parser.add_argument("--tasks-dir", default="/data/pie-tasks-full-20260706")
    parser.add_argument("--hf-checkpoint", default="/root/models/GLM-4.7-Flash")
    parser.add_argument(
        "--ref-load",
        default="/root/models/GLM-4.7-Flash_torch_dist_tp4_pp1_ep8",
    )
    parser.add_argument("--adaptive-config", default="")
    parser.add_argument("--throughput-floor", type=float, default=0.98)
    parser.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), default="offline")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-hardware-check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rounds = parse_rounds(args.rounds)
    specs = {spec.round: spec for spec in TRIAL_SPECS}
    unknown = sorted(rounds - specs.keys())
    if unknown:
        raise SystemExit(f"unknown rounds: {unknown}")
    adaptive = load_adaptive_config(args.adaptive_config) if rounds & {15, 16} else None
    if rounds & {15, 16} and adaptive is None:
        raise SystemExit("rounds 15-16 require --adaptive-config")

    sweep_root = Path(args.sweep_root).resolve()
    sweep_root.mkdir(parents=True, exist_ok=True)
    if not args.skip_hardware_check and not args.dry_run:
        write_hardware_receipt(sweep_root / "hardware.json")
    write_solution_space(sweep_root / "solution_space.json", adaptive)

    baseline: dict[str, Any] | None = load_round_summary(sweep_root, 1)
    for round_number in sorted(rounds):
        spec = specs[round_number]
        if spec.adaptive:
            spec = apply_adaptive_config(spec, adaptive or {})
        trial_root = sweep_root / f"round{round_number:02d}_{spec.name}"
        summary_path = trial_root / "trial_summary.json"
        if summary_path.is_file() and not args.rerun:
            print(f"round {round_number:02d}: preserving existing {summary_path}", flush=True)
            if round_number == 1:
                baseline = json.loads(summary_path.read_text(encoding="utf-8"))
            continue
        trial_root.mkdir(parents=True, exist_ok=True)
        write_trial_spec(trial_root / "trial_spec.json", spec)
        if args.dry_run:
            print(json.dumps(asdict(spec), sort_keys=True), flush=True)
            continue

        env = build_trial_env(args, spec, trial_root, sweep_root.name)
        print(
            f"round {round_number:02d}/16 {spec.name}: {spec.hypothesis}",
            flush=True,
        )
        completed = subprocess.run(["bash", str(Path(args.runner).resolve())], env=env, check=False)
        stage_root = trial_root / "sft_lora_r16"
        summary = summarize_miles_mfu_trial(
            log_path=stage_root / "run.log",
            receipt_path=stage_root / "run_receipt.txt",
            round_number=round_number,
            name=spec.name,
            precision=spec.precision,
            peak_tflops_per_gpu=spec.peak_tflops_per_gpu,
            baseline=baseline if round_number != 1 else None,
            throughput_floor=args.throughput_floor,
        )
        summary["launcher_exit_code"] = completed.returncode
        summary["hypothesis"] = spec.hypothesis
        summary["trial_env"] = dict(sorted(spec.env.items()))
        summary["trial_extra_args"] = spec.extra_args
        write_trial_summary(summary_path, summary)
        if round_number == 1:
            baseline = summary
            if not summary["accepted"]:
                write_current_sweep(sweep_root, args.throughput_floor)
                raise SystemExit("round 1 baseline failed its integrity gate; stop before spending more GPU time")
        write_current_sweep(sweep_root, args.throughput_floor)
        print(
            json.dumps(
                {
                    "round": round_number,
                    "accepted": summary["accepted"],
                    "mfu_percent": summary["estimated_mfu_percent_median"],
                    "global_actor_tok_s": summary["global_actor_tok_s_median"],
                    "rejection_reasons": summary["rejection_reasons"],
                },
                sort_keys=True,
            ),
            flush=True,
        )

    if not args.dry_run:
        final = write_current_sweep(sweep_root, args.throughput_floor)
        print(json.dumps({key: final[key] for key in ("trial_count", "winner_round", "winner_name")}), flush=True)
    return 0


def parse_rounds(value: str) -> set[int]:
    rounds: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start, end = (int(part) for part in item.split("-", 1))
            rounds.update(range(start, end + 1))
        else:
            rounds.add(int(item))
    return rounds


def load_adaptive_config(path: str) -> dict[str, Any] | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("env", {}), dict):
        raise SystemExit("adaptive config must be an object with an optional env object")
    return payload


def apply_adaptive_config(spec: TrialSpec, payload: dict[str, Any]) -> TrialSpec:
    return replace(
        spec,
        env={str(key): str(value) for key, value in payload.get("env", {}).items()},
        extra_args=str(payload.get("extra_args") or ""),
        precision=str(payload.get("precision") or "bf16"),
        peak_tflops_per_gpu=float(
            payload.get("peak_tflops_per_gpu") or H100_SXM_BF16_PEAK_TFLOPS
        ),
    )


def build_trial_env(
    args: argparse.Namespace,
    spec: TrialSpec,
    trial_root: Path,
    experiment_id: str,
) -> dict[str, str]:
    env = os.environ.copy()
    run_id = f"mfu-r{spec.round:02d}-{spec.name}"
    defaults = {
        "MILES_RUN_ID": run_id,
        "MILES_RUN_ROOT": str(trial_root),
        "MILES_CPP_DATA_DIR": args.data_dir,
        "MILES_CPP_TASKS_DIR": args.tasks_dir,
        "MILES_CPP_AUTO_PREPARE_DATA": "0",
        "MILES_HF_CHECKPOINT": args.hf_checkpoint,
        "MILES_REF_LOAD_DIR": args.ref_load,
        "MILES_SFT_NUM_EPOCH": "1",
        "MILES_ROLLOUT_BATCH_SIZE": "32",
        "MILES_GLOBAL_BATCH_SIZE": "32",
        "MILES_SFT_ROLLOUT_SHUFFLE": "0",
        "MILES_SAVE_INTERVAL": "1000",
        "MILES_NO_REF": "1",
        "MILES_CUDA_DEVICE_MAX_CONNECTIONS": "1",
        "MILES_EXTRA_ARGS": spec.extra_args,
        "MILES_WANDB_GROUP": experiment_id,
        "MILES_WANDB_RUN_ID": run_id,
        "MILES_WANDB_JOB_TYPE": "mfu-trial",
        "W8_EXPERIMENT_ID": experiment_id,
        "W8_TIMING_STATUS": "verified",
        "WANDB_MODE": args.wandb_mode,
        "WANDB_RUN_GROUP": experiment_id,
        "WANDB_JOB_TYPE": "mfu-trial",
        "WANDB_TAGS": f"canonical,pie-cpp,mfu-sweep,round-{spec.round:02d}",
    }
    env.update(defaults)
    env.update(spec.env)
    return env


def write_hardware_receipt(path: Path) -> None:
    query = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,driver_version,pci.bus_id",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    rows = [line.strip() for line in query.stdout.splitlines() if line.strip()]
    if len(rows) != 8 or any("H100" not in row for row in rows):
        raise SystemExit(f"expected exactly 8 H100 GPUs, got: {rows}")
    payload = {
        "gpu_rows": rows,
        "topology": _command_output(["nvidia-smi", "topo", "-m"]),
        "repo_sha": _command_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).strip(),
        "miles_sha": _optional_git_sha(Path("/root/miles")),
        "megatron_sha": _optional_git_sha(Path("/root/Megatron-LM")),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_solution_space(path: Path, adaptive: dict[str, Any] | None) -> None:
    rows = []
    for spec in TRIAL_SPECS:
        resolved = apply_adaptive_config(spec, adaptive) if spec.adaptive and adaptive else spec
        rows.append(asdict(resolved))
    path.write_text(json.dumps({"schema_version": 1, "trials": rows}, indent=2) + "\n", encoding="utf-8")


def write_trial_spec(path: Path, spec: TrialSpec) -> None:
    path.write_text(json.dumps(asdict(spec), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_round_summary(root: Path, round_number: int) -> dict[str, Any] | None:
    matches = list(root.glob(f"round{round_number:02d}_*/trial_summary.json"))
    return json.loads(matches[0].read_text(encoding="utf-8")) if matches else None


def write_current_sweep(root: Path, throughput_floor: float) -> dict[str, Any]:
    summary = summarize_miles_mfu_sweep(root, throughput_floor=throughput_floor)
    write_sweep_artifacts(root, summary)
    return summary


def _command_output(command: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def _optional_git_sha(path: Path) -> str:
    if not (path / ".git").exists():
        return ""
    return _command_output(["git", "rev-parse", "HEAD"], cwd=path).strip()


if __name__ == "__main__":
    raise SystemExit(main())
