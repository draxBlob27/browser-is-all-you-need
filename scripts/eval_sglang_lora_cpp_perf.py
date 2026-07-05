from __future__ import annotations

import argparse
import concurrent.futures
import gc
import json
import os
import time
from pathlib import Path
from typing import Any

from w8_biayn.cpp_perf.eval import aggregate_eval_records, write_json
from w8_biayn.cpp_perf.schema import CppTask
from w8_biayn.integrations.cpp_eval_main import score_generation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PIE C++ prompts with SGLang and an optional LoRA adapter.")
    parser.add_argument("--data-dir", required=True, help="Directory produced by slime_cpp_perf build-data.")
    parser.add_argument("--model", required=True, help="Base HF model path.")
    parser.add_argument("--adapter", default=None, help="LoRA adapter directory to apply during generation.")
    parser.add_argument("--label", default="grpo")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--samples-per-task", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--mem-fraction-static", type=float, default=0.35)
    parser.add_argument("--cuda-graph-max-bs", type=int, default=16)
    parser.add_argument("--score-workers", type=int, default=16)
    parser.add_argument("--sandbox-image", default=os.environ.get("W8_CPP_SANDBOX_IMAGE", "w8-biayn-cpp-perf:latest"))
    parser.add_argument("--sandbox-cpu", default=os.environ.get("W8_CPP_SANDBOX_CPU", "1"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(data_dir / "eval" / "validation.jsonl")
    if args.max_tasks is not None:
        rows = rows[: args.max_tasks]
    if not rows:
        raise ValueError(f"No eval rows found in {data_dir}")

    generated_path = output_dir / f"{args.label}.generated.jsonl"
    records_path = output_dir / f"{args.label}.records.jsonl"
    summary_path = output_dir / f"{args.label}.summary.json"
    receipt_path = output_dir / f"{args.label}.receipt.json"

    started_at = time.time()
    print(
        f"SGLang PIE eval generation start: label={args.label} tasks={len(rows)} "
        f"samples_per_task={args.samples_per_task}",
        flush=True,
    )
    generations = generate_rows(args, rows)
    write_jsonl(generated_path, generations)
    print(
        f"SGLang PIE eval generation complete: label={args.label} samples={len(generations)} "
        f"path={generated_path}",
        flush=True,
    )
    _release_cuda_memory()

    print(
        f"SGLang PIE eval scoring start: label={args.label} samples={len(generations)} "
        f"workers={args.score_workers}",
        flush=True,
    )
    records = score_rows(args, data_dir, generations)
    write_jsonl(records_path, records)
    summary = aggregate_eval_records(records, label=args.label)
    summary.pop("best_records", None)
    write_json(summary_path, summary)
    write_json(
        receipt_path,
        {
            "label": args.label,
            "data_dir": str(data_dir),
            "model": args.model,
            "adapter": args.adapter,
            "output_dir": str(output_dir),
            "task_count": len(rows),
            "sample_count": len(generations),
            "samples_per_task": args.samples_per_task,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "tp_size": args.tp_size,
            "elapsed_seconds": time.time() - started_at,
            "summary_path": str(summary_path),
            "records_path": str(records_path),
            "generated_path": str(generated_path),
        },
    )
    print(f"SGLang PIE eval scoring complete: label={args.label} path={summary_path}", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def generate_rows(args: argparse.Namespace, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from sglang import Engine

    engine_kwargs: dict[str, Any] = {
        "model_path": args.model,
        "trust_remote_code": True,
        "tp_size": args.tp_size,
        "dtype": "bfloat16",
        "mem_fraction_static": args.mem_fraction_static,
        "cuda_graph_max_bs": args.cuda_graph_max_bs,
        "moe_runner_backend": "triton",
        "log_level": "warning",
    }
    if args.adapter:
        engine_kwargs.update(
            {
                "enable_lora": True,
                "max_lora_rank": 16,
                "lora_target_modules": ["gate_proj", "up_proj", "down_proj"],
                "lora_backend": "triton",
            }
        )

    engine = Engine(**engine_kwargs)
    try:
        if args.adapter:
            engine.load_lora_adapter(args.label, args.adapter)

        generations: list[dict[str, Any]] = []
        expanded = []
        for row in rows:
            for sample_index in range(args.samples_per_task):
                expanded.append((row, sample_index))

        sampling_params = {
            "max_new_tokens": args.max_tokens,
            "temperature": args.temperature,
            "top_p": args.top_p,
        }
        for start in range(0, len(expanded), args.batch_size):
            batch = expanded[start : start + args.batch_size]
            prompts = [str(row["prompt"]) for row, _sample_index in batch]
            lora_paths = [args.label] * len(prompts) if args.adapter else None
            outputs = engine.generate(prompts, sampling_params, lora_path=lora_paths)
            if isinstance(outputs, dict):
                outputs = [outputs]
            for (row, sample_index), output in zip(batch, outputs, strict=True):
                generations.append(
                    {
                        "label": args.label,
                        "task_id": row.get("task_id"),
                        "problem_id": row.get("problem_id"),
                        "split": row.get("split"),
                        "sample_index": sample_index,
                        "metadata": row.get("metadata", {}),
                        "response": output_text(output),
                    }
                )
            if len(generations) == len(batch) or len(generations) % 100 == 0 or len(generations) == len(expanded):
                print(
                    "SGLang PIE eval generation progress: "
                    f"{len(generations)}/{len(expanded)}",
                    flush=True,
                )
        return generations
    finally:
        engine.shutdown()


def output_text(output: Any) -> str:
    if isinstance(output, dict):
        for key in ("text", "output_text", "content"):
            value = output.get(key)
            if isinstance(value, str):
                return value
        outputs = output.get("outputs")
        if isinstance(outputs, list) and outputs:
            return output_text(outputs[0])
    return str(output)


def score_rows(args: argparse.Namespace, data_dir: Path, generations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def score_one(item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        task_path = Path(str(metadata["task_path"]))
        if not task_path.is_absolute():
            task_path = data_dir / task_path
        task = CppTask.read_json(task_path)
        record = score_generation(
            task,
            str(item.get("response", "")),
            label=args.label,
            sample_index=int(item.get("sample_index", 0)),
            image=args.sandbox_image,
            cpu=args.sandbox_cpu,
        )
        record["task_id"] = item.get("task_id") or record.get("task_id")
        record["problem_id"] = item.get("problem_id") or record.get("problem_id")
        record["split"] = item.get("split") or record.get("split")
        return record

    records: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.score_workers)) as executor:
        futures = [executor.submit(score_one, item) for item in generations]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            records.append(future.result())
            if index == 1 or index == len(futures) or index % 25 == 0:
                print(f"SGLang PIE eval scoring progress: {index}/{len(futures)}", flush=True)
    records.sort(key=lambda row: (str(row.get("task_id")), int(row.get("sample_index") or 0)))
    return records


def _release_cuda_memory() -> None:
    gc.collect()
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
