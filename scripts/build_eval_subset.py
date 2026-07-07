"""Build a small eval subset whose aggregate metrics track the full eval set.

Stratifies tasks on their joint outcome under one or two reference policies
(e.g. base and SFT eval records): stratum = (primary reason bucket, secondary
pass/fail). Proportional allocation preserves the outcome composition, so the
subset's pass rate / mean reward correlate with the full set by construction.
Prints subset-vs-full deltas for every reference policy as validation.

Used for in-training trend evals (Miles --eval-prompt-data), where the formal
numbers still come from the full set via eval_sglang_lora_cpp_perf.py.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from typing import Any


def read_jsonl(path: str) -> list[dict[str, Any]]:
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def reason_bucket(record: dict[str, Any]) -> str:
    if record["reason"] == "correct":
        return "correct_faster" if (record.get("runtime_speedup") or 0) > 1.0 else "correct_slower"
    return str(record["reason"])


def select_subset(
    task_ids: list[str],
    primary: dict[str, dict[str, Any]],
    secondary: dict[str, dict[str, Any]] | None,
    target: int,
    seed: int,
) -> list[str]:
    strata: dict[tuple[str, bool], list[str]] = defaultdict(list)
    for tid in task_ids:
        p = primary.get(tid)
        if p is None:
            strata[("unknown", False)].append(tid)
            continue
        s = secondary.get(tid) if secondary else None
        strata[(reason_bucket(p), bool(s and s["all_tests_pass"]))].append(tid)

    rng = random.Random(seed)
    total = len(task_ids)
    picked: list[str] = []
    remainders: list[tuple[tuple[str, bool], float]] = []
    for key, tids in sorted(strata.items()):
        share = len(tids) * target / total
        n = int(share)
        remainders.append((key, share - n))
        tids_sorted = sorted(tids)
        rng.shuffle(tids_sorted)
        picked.extend(tids_sorted[:n])
        strata[key] = tids_sorted[n:]
    remainders.sort(key=lambda item: -item[1])
    for key, _frac in remainders:
        if len(picked) >= target:
            break
        if strata[key]:
            picked.append(strata[key].pop(0))
    return picked[:target]


def metrics(records: dict[str, dict[str, Any]], tids: list[str]) -> dict[str, float]:
    rows = [records[t] for t in tids if t in records]
    n = len(rows)
    return {
        "n": n,
        "pass_rate": sum(r["all_tests_pass"] for r in rows) / n,
        "mean_reward": sum(r["reward"] for r in rows) / n,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-rows", required=True, help="Full eval prompt JSONL (Miles eval format).")
    parser.add_argument("--primary-records", required=True, help="records.jsonl of the primary policy (stratification axis).")
    parser.add_argument("--secondary-records", default=None, help="Optional records.jsonl of a second policy.")
    parser.add_argument("--target", type=int, default=126)
    parser.add_argument("--seed", type=int, default=20260707)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = read_jsonl(args.eval_rows)
    row_by_tid: dict[str, dict[str, Any]] = {}
    for row in rows:
        tid = row.get("task_id") or row.get("metadata", {}).get("task_id")
        row_by_tid[tid] = row
    if len(row_by_tid) != len(rows):
        raise SystemExit("eval rows are missing task_id (top-level or metadata)")

    primary = {r["task_id"]: r for r in read_jsonl(args.primary_records)}
    secondary = {r["task_id"]: r for r in read_jsonl(args.secondary_records)} if args.secondary_records else None

    picked = select_subset(list(row_by_tid), primary, secondary, args.target, args.seed)
    all_tids = list(row_by_tid)
    for name, rec in (("primary", primary), ("secondary", secondary)):
        if not rec:
            continue
        full, mini = metrics(rec, all_tids), metrics(rec, picked)
        print(
            f"{name}: full pass={full['pass_rate']:.4f} reward={full['mean_reward']:.4f} | "
            f"mini pass={mini['pass_rate']:.4f} reward={mini['mean_reward']:.4f} | "
            f"|dpass|={abs(full['pass_rate'] - mini['pass_rate']):.4f}"
        )

    with open(args.out, "w") as fh:
        for tid in sorted(picked):
            fh.write(json.dumps(row_by_tid[tid]) + "\n")
    print(f"wrote {len(picked)} rows to {args.out}")


if __name__ == "__main__":
    main()
