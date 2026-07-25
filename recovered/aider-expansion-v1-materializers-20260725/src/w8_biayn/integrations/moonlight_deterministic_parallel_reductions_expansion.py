"""Create and verify the 60-root deterministic-parallel-reductions expansion.

Superseded: the live family tree is owned by ``moonlight_dpr_v2`` (family
``aider-expansion-v1-deterministic-parallel-reductions-v2``). This v1 module is
retained for historical cycle-01 evidence only. It fails closed with
``foreign_root`` when pointed at a tree containing any root whose provenance
names a different family, so it cannot inject its disjoint v1 case inventory
into the v2 family tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/"
    "deterministic-parallel-reductions"
)
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-state-concurrency/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_DETERMINISTIC_PARALLEL_REDUCTIONS_"
    "CURRICULUM.md"
)
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-state-concurrency/"
    "deterministic-parallel-reductions.md"
)
GENERATOR_PATH = Path(
    "src/w8_biayn/integrations/"
    "moonlight_deterministic_parallel_reductions_expansion.py"
)
TEST_PATH = Path(
    "tests/test_moonlight_deterministic_parallel_reductions_expansion.py"
)
FAMILY_ID = "aider-expansion-v1-deterministic-parallel-reductions-v1"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base",
        "allergies",
        "bank-account",
        "binary-search-tree",
        "circular-buffer",
        "clock",
        "complex-numbers",
        "crypto-square",
        "diamond",
        "dnd-character",
        "gigasecond",
        "grade-school",
        "kindergarten-garden",
        "knapsack",
        "linked-list",
        "meetup",
        "parallel-letter-frequency",
        "perfect-numbers",
        "phone-number",
        "queen-attack",
        "robot-name",
        "space-age",
        "spiral-matrix",
        "sublist",
        "yacht",
        "zebra-puzzle",
    }
)
HARD_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
GROUPS = (
    "partition_assignment",
    "fixed_tree_reduction",
    "summary_monoid",
    "ordered_merge",
    "state_log_fold",
)


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    group: str
    mechanism: str
    contract: str
    boundary: str
    negative_reason: str

    @property
    def index(self) -> int:
        return CASES.index(self)

    @property
    def stem(self) -> str:
        return self.task_id.replace("-", "_")

    @property
    def request_type(self) -> str:
        return "".join(part.title() for part in self.task_id.split("-")) + "Request"


def _c(
    task_id: str,
    title: str,
    group: str,
    mechanism: str,
    contract: str,
    boundary: str,
    negative_reason: str,
) -> Case:
    return Case(task_id, title, group, mechanism, contract, boundary, negative_reason)


CASES: tuple[Case, ...] = (
    _c("dpr-contiguous-shard-sums", "Contiguous Shard Sums", GROUPS[0], "quotient/remainder contiguous partition", "Output one checked sum per worker after splitting the record sequence into contiguous ranges; the first `n % workers` ranges contain one extra record.", "Worker order is numeric and empty ranges contribute zero.", "the terminal contiguous shard is omitted"),
    _c("dpr-round-robin-shard-sums", "Round-Robin Shard Sums", GROUPS[0], "cyclic index assignment", "Assign record index `i` to worker `i % workers` and output one checked sum per worker.", "Worker order is numeric; empty workers contribute zero.", "the last cyclic partial is omitted"),
    _c("dpr-keyed-bucket-sums", "Keyed Bucket Sums", GROUPS[0], "Euclidean key bucket partition", "Assign each aligned record to `floor_mod(key, workers)` and output checked bucket sums.", "Negative keys use Euclidean modulo and buckets are numeric.", "the final keyed bucket partial is omitted"),
    _c("dpr-greedy-load-owners", "Greedy Load Owners", GROUPS[0], "least-loaded list scheduling", "Treat values as nonnegative costs, assign them in source order to the least-loaded worker, and output the owner for every record.", "Equal load chooses the smallest worker; negative costs reject.", "the terminal assignment is omitted"),
    _c("dpr-weighted-prefix-cuts", "Weighted Prefix Cuts", GROUPS[0], "proportional cumulative-weight cuts", "Treat values as nonnegative weights and output exclusive contiguous cut indices at proportional cumulative targets for every nonfinal worker, then the final size.", "A target is crossed after its record; zero total uses count-balanced cuts.", "the final proportional cut is omitted"),
    _c("dpr-sign-strata-counts", "Sign Strata Counts", GROUPS[0], "three-way sign partition", "Reduce negative, zero, and positive records independently and output their three counts.", "The output order is negative, zero, positive.", "the positive-stratum partial is omitted"),
    _c("dpr-run-preserving-cuts", "Run-Preserving Cuts", GROUPS[0], "equal-key run preserving partition", "Keep each maximal equal-key run intact and close contiguous shards near the count target; output exclusive cuts.", "No equal-key run may split and the last cut is the record count.", "the terminal run cut is omitted"),
    _c("dpr-snake-shard-totals", "Snake Shard Totals", GROUPS[0], "reflected block assignment", "Assign blocks of `parameter` records across workers forward then backward and output checked worker totals.", "Endpoint workers are not duplicated at a direction change.", "the final reflected block partial is omitted"),
    _c("dpr-residue-bucket-counts", "Residue Bucket Counts", GROUPS[0], "parameter-radix histogram partition", "Bucket each value by Euclidean modulo `parameter` and output exactly `parameter` counts.", "Negative values use Euclidean modulo; worker count does not set the radix.", "the final residue bucket is omitted"),
    _c("dpr-halo-window-sums", "Halo Window Sums", GROUPS[0], "clipped one-record halo partition", "Partition contiguously and output each shard sum including at most one neighboring record on each side.", "Halos clip at input boundaries and never wrap.", "the final halo shard is omitted"),
    _c("dpr-capacity-spill-owners", "Capacity Spill Owners", GROUPS[0], "bounded fill then cyclic spill", "Fill each worker with `parameter` records in numeric order, then assign remaining records cyclically; output owners.", "Workers with unused capacity precede spill assignment.", "the final spill owner is omitted"),
    _c("dpr-dependency-wave-counts", "Dependency Wave Counts", GROUPS[0], "stable DAG antichain decomposition", "Interpret each key as a parent index or -1, require parents to precede children, and output the number of records at each dependency level.", "Missing/forward/self parents reject; roots are level zero.", "the final dependency wave is omitted"),
    _c("dpr-pairwise-sum-tree", "Pairwise Sum Tree", GROUPS[1], "checked adjacent sum tree", "Form contiguous worker sums, then combine adjacent partials by checked addition in rounds; output every round in order.", "An odd partial carries unchanged; overflow rejects.", "the terminal sum-tree partial is omitted"),
    _c("dpr-pairwise-min-tree", "Pairwise Minimum Tree", GROUPS[1], "adjacent minimum tree", "Form contiguous worker minima and combine adjacent partials by minimum; output every round.", "Equal minima preserve the left partial; odd partials carry.", "the terminal minimum-tree partial is omitted"),
    _c("dpr-pairwise-max-tree", "Pairwise Maximum Tree", GROUPS[1], "adjacent maximum tree", "Form contiguous worker maxima and combine adjacent partials by maximum; output every round.", "Equal maxima preserve the left partial; odd partials carry.", "the terminal maximum-tree partial is omitted"),
    _c("dpr-pairwise-gcd-tree", "Pairwise GCD Tree", GROUPS[1], "absolute GCD tree", "Form per-worker absolute GCD partials and combine adjacent partials by GCD; output every round.", "`gcd(0,0)` is zero and odd partials carry.", "the terminal gcd-tree partial is omitted"),
    _c("dpr-pairwise-lcm-tree", "Pairwise LCM Tree", GROUPS[1], "checked nonnegative LCM tree", "Form per-worker LCM partials and combine adjacent partials by checked LCM; output every round.", "Zero absorbs and multiplication overflow rejects.", "the terminal lcm-tree partial is omitted"),
    _c("dpr-pairwise-or-tree", "Pairwise OR Tree", GROUPS[1], "bitwise OR tree", "Form per-worker bitwise-OR partials and combine adjacent partials by OR; output every round.", "Negative values reject; odd partials carry.", "the terminal OR-tree partial is omitted"),
    _c("dpr-pairwise-and-tree", "Pairwise AND Tree", GROUPS[1], "bitwise AND tree", "Form per-worker bitwise-AND partials and combine adjacent partials by AND; output every round.", "Negative values reject and empty input returns engaged empty.", "the terminal AND-tree partial is omitted"),
    _c("dpr-pairwise-xor-tree", "Pairwise XOR Tree", GROUPS[1], "bitwise XOR tree", "Form per-worker XOR partials and combine adjacent partials by XOR; output every round.", "Negative values reject; odd partials carry.", "the terminal XOR-tree partial is omitted"),
    _c("dpr-pairwise-product-tree", "Pairwise Product Tree", GROUPS[1], "checked multiplication tree", "Form checked worker products and combine adjacent partials by checked multiplication; output every round.", "Any overflow rejects; empty input returns engaged empty.", "the terminal product-tree partial is omitted"),
    _c("dpr-saturating-sum-tree", "Saturating Sum Tree", GROUPS[1], "edge-local saturating sum tree", "Form worker sums and clamp every adjacent combine to `[-parameter,parameter]`; output every round.", "Clamping occurs on each edge, not only on the final value.", "the terminal saturated partial is omitted"),
    _c("dpr-ordered-difference-tree", "Ordered Difference Tree", GROUPS[1], "non-associative left-minus-right tree", "Form worker sums and combine adjacent partials as left minus right in fixed rounds; output every round.", "Order is semantic; odd partials carry unchanged.", "the terminal ordered-difference partial is omitted"),
    _c("dpr-median-tournament-tree", "Median Tournament Tree", GROUPS[1], "median-of-three tournament", "Form worker sums and reduce consecutive triples to their median; a final pair reduces to its smaller value and a singleton carries; output every round.", "Triple medians are numeric and the incomplete final pair uses its lower member.", "the terminal tournament partial is omitted"),
    _c("dpr-sum-count-summary", "Sum Count Summary", GROUPS[2], "checked sum/count monoid", "Merge worker `(sum,count)` states and output the final sum and count.", "Empty input returns `{0,0}` and addition overflow rejects.", "the count field of the final summary is omitted"),
    _c("dpr-min-max-summary", "Min Max Summary", GROUPS[2], "extrema-pair monoid", "Merge worker `(minimum,maximum)` states and output the final pair.", "Empty input returns engaged empty; equal extrema are retained once.", "the maximum field is omitted"),
    _c("dpr-sum-squares-summary", "Sum Squares Summary", GROUPS[2], "checked first/second moment monoid", "Merge worker `(sum,sum_of_squares)` states and output the final pair.", "Squaring or addition overflow rejects.", "the squared-sum field is omitted"),
    _c("dpr-stable-argmin-summary", "Stable Argmin Summary", GROUPS[2], "stable indexed minimum", "Merge worker `(value,index)` minima and output the winning value and original index.", "Equal values choose the smaller source index.", "the winning index is omitted"),
    _c("dpr-stable-argmax-summary", "Stable Argmax Summary", GROUPS[2], "stable indexed maximum", "Merge worker `(value,index)` maxima and output the winning value and original index.", "Equal values choose the smaller source index.", "the winning index is omitted"),
    _c("dpr-top-k-summary", "Stable Top-K Summary", GROUPS[2], "bounded stable top-K partial merge", "Keep at most `parameter` best records per worker, merge by value descending then index ascending, and output values followed by indices.", "Equal values retain source-index order.", "the terminal top-K index is omitted"),
    _c("dpr-histogram-summary", "Histogram Summary", GROUPS[2], "observable worker-histogram reduction monoid", "Build `parameter` Euclidean residue bins per worker, output every worker histogram in worker order, then output their elementwise merged histogram.", "Negative values use Euclidean modulo and empty workers emit zero bins.", "the final merged histogram bin is omitted"),
    _c("dpr-distinct-summary", "Distinct Summary", GROUPS[2], "sorted unique set-union monoid", "Sort/unique each worker partial and merge canonical set unions; output ascending unique values.", "Duplicates across any partials collapse once.", "the greatest distinct value is omitted"),
    _c("dpr-max-subarray-summary", "Maximum Subarray Summary", GROUPS[2], "cross-boundary maximum-subarray monoid", "Merge total, prefix, suffix, and best-range states; output best sum, start, and end-exclusive index.", "Equal sums choose earlier start then shorter range.", "the best-range end is omitted"),
    _c("dpr-parentheses-summary", "Parentheses Summary", GROUPS[2], "net/minimum-prefix balance monoid", "Interpret positive values as opens and nonpositive values as closes; merge net and minimum-prefix states and output both.", "Balanced means final net zero and minimum prefix zero.", "the minimum-prefix field is omitted"),
    _c("dpr-affine-compose-summary", "Affine Compose Summary", GROUPS[2], "ordered affine-function composition", "Interpret consecutive value pairs as `(a,b)` for `x -> a*x+b`, compose in source order, and output final `a,b`.", "Odd record count or checked arithmetic overflow rejects.", "the affine offset is omitted"),
    _c("dpr-rational-mean-summary", "Rational Mean Summary", GROUPS[2], "GCD-reduced exact mean monoid", "Merge exact sum/count states and output a reduced numerator and positive denominator.", "Empty input returns engaged empty; negative numerators are allowed.", "the reduced denominator is omitted"),
    _c("dpr-kway-stable-merge", "K-Way Stable Merge", GROUPS[3], "stable sorted shard heap merge", "Treat keys as shard IDs, require each shard subsequence sorted, and output all values by value then shard then shard position.", "Equal values choose smaller shard then earlier position.", "the terminal merged record is omitted"),
    _c("dpr-interval-union-merge", "Interval Union Merge", GROUPS[3], "sorted half-open interval coalescing", "Interpret consecutive values as half-open intervals, sort them, and output maximal overlap-or-touch unions.", "Reversed intervals or odd value count reject.", "the terminal union endpoint is omitted"),
    _c("dpr-rle-boundary-merge", "RLE Boundary Merge", GROUPS[3], "cross-partial run coalescing", "Interpret aligned `(value,key)` as `(symbol,count)` runs and coalesce only adjacent equal symbols; output flattened symbol/count pairs.", "Counts must be positive and checked on addition.", "the terminal run count is omitted"),
    _c("dpr-key-count-merge", "Key Count Merge", GROUPS[3], "checked canonical key-count merge", "Treat aligned records as `(key,count)`, checked-sum duplicate keys, and output flattened key/count pairs in key order.", "Negative counts reject; zero totals are retained.", "the terminal key count is omitted"),
    _c("dpr-prefix-offset-merge", "Prefix Offset Merge", GROUPS[3], "local inclusive scans with prior-partial offsets", "Compute local inclusive scans for contiguous worker shards, add prior shard totals, and concatenate the global prefix scan.", "Checked addition overflow rejects.", "the terminal prefix value is omitted"),
    _c("dpr-suffix-offset-merge", "Suffix Offset Merge", GROUPS[3], "local inclusive suffix scans with later-partial offsets", "Compute local suffix scans, add later shard totals, and return results in original input order.", "Checked addition overflow rejects.", "the terminal suffix value is omitted"),
    _c("dpr-rolling-hash-merge", "Rolling Hash Merge", GROUPS[3], "ordered polynomial segment composition", "Fold nonnegative values as digits with base `parameter` modulo 1,000,003 and output digest and length.", "Input order is semantic; negative digits reject.", "the digest length is omitted"),
    _c("dpr-sorted-set-union-merge", "Sorted Set Union Merge", GROUPS[3], "validated sorted-shard union", "Require each key-identified shard subsequence strictly sorted and output the canonical union.", "Duplicates within a shard reject; cross-shard duplicates collapse.", "the greatest union member is omitted"),
    _c("dpr-two-shard-intersection-merge", "Two-Shard Intersection Merge", GROUPS[3], "sorted multiset intersection", "Require exactly two sorted shard streams and output their multiset intersection.", "Multiplicity is the smaller shard multiplicity.", "the terminal intersection member is omitted"),
    _c("dpr-partial-top-k-merge", "Partial Top-K Merge", GROUPS[3], "validated canonical partial top-K merge", "Require each key-identified shard be value-descending, merge by value then shard order, and truncate to `parameter`.", "Equal values choose smaller shard then position.", "the kth merged value is omitted"),
    _c("dpr-quantile-sketch-merge", "Quantile Sketch Merge", GROUPS[3], "rank-stride sample merge", "Merge sorted shard samples and retain ranks `0,parameter,2*parameter,...`, appending the maximum if absent.", "Each shard must be nondecreasing.", "the maximum sketch sample is omitted"),
    _c("dpr-sparse-coordinate-merge", "Sparse Coordinate Merge", GROUPS[3], "checked sparse coordinate accumulation", "Treat aligned `(key,value)` records as coordinates and contributions, checked-sum duplicates, omit zeros, and output flattened coordinate/value pairs.", "Coordinates are ascending and cancellation zeros disappear.", "the terminal sparse contribution is omitted"),
    _c("dpr-version-vector-merge", "Version Vector Merge", GROUPS[4], "pointwise actor maximum", "Treat keys as nonnegative actors and values as sequences, retain the maximum per actor, and output actor/sequence pairs.", "Actors are ascending; negative actors/sequences reject.", "the final actor version is omitted"),
    _c("dpr-watermark-min-merge", "Watermark Minimum Merge", GROUPS[4], "pointwise source minimum", "Treat keys as nonnegative sources and values as watermarks, retain the minimum per source, and output source/watermark pairs.", "Missing sources are absent rather than zero.", "the final source watermark is omitted"),
    _c("dpr-conflict-key-union", "Conflict Key Union", GROUPS[4], "nonzero conflict-key set union", "Union all keys whose aligned value is nonzero and output ascending keys.", "Duplicate keys collapse and zero-valued records do not contribute.", "the greatest conflict key is omitted"),
    _c("dpr-quorum-vote-merge", "Quorum Vote Merge", GROUPS[4], "per-proposal signed quorum fold", "Count positive/negative votes per proposal key and emit keys with at least `parameter` positive votes and more positive than negative.", "Zero votes reject and proposals are ascending.", "the final quorum proposal is omitted"),
    _c("dpr-retry-priority-merge", "Retry Priority Merge", GROUPS[4], "request-state precedence fold", "Reduce states 0=pending, 1=retry, 2=success, 3=terminal-failure per request key and output key/state pairs.", "Success dominates, then terminal failure, retry, pending; other states reject.", "the final request state is omitted"),
    _c("dpr-cancellation-prefix-merge", "Cancellation Prefix Merge", GROUPS[4], "per-stream first-cancel prefix fold", "For each stream key, emit nonnegative values before its first negative cancellation and ignore later records.", "Streams and within-stream source order are stable.", "the final pre-cancel event is omitted"),
    _c("dpr-stable-event-log-merge", "Stable Event Log Merge", GROUPS[4], "timestamp/worker/position event ordering", "Treat keys as timestamps, partition records contiguously by worker, and output timestamp/value pairs ordered by timestamp, worker, then position.", "Equal timestamps never use completion order.", "the final ordered event is omitted"),
    _c("dpr-epoch-snapshot-merge", "Epoch Snapshot Merge", GROUPS[4], "per-owner greatest-sequence snapshot", "Treat keys as owners and values as sequences, retain the greatest sequence per owner, and output owner/sequence pairs.", "Equal sequence keeps the earliest input record.", "the final owner snapshot is omitted"),
    _c("dpr-barrier-generation-merge", "Barrier Generation Merge", GROUPS[4], "unique participant count by generation", "Treat keys as generations and values as participant IDs, count unique arrivals, and output generation/count pairs.", "Duplicate arrivals collapse; generations are ascending.", "the final generation count is omitted"),
    _c("dpr-work-steal-replay", "Work-Steal Replay", GROUPS[4], "deterministic overload-aware reassignment", "Treat values as job costs and floor-modulo keys as preferred workers; if preferred load exceeds `parameter`, assign to the least-loaded worker; output owners then final loads.", "Negative costs reject and equal load chooses the smallest worker.", "the final replay load is omitted"),
    _c("dpr-last-write-wins-merge", "Last Write Wins Merge", GROUPS[4], "per-record greatest-sequence selection", "Treat keys as record IDs and values as sequence numbers, retain the greatest sequence, and output record/sequence pairs.", "Equal sequence keeps the earliest input position.", "the final resolved record is omitted"),
    _c("dpr-ordered-event-digest", "Ordered Event Digest", GROUPS[4], "stable event merge followed by modular digest", "Order records by key then worker then source position and fold values with base `parameter` modulo 1,000,003; output digest and count.", "Order is semantic and values may be signed after Euclidean normalization.", "the digest event count is omitted"),
)


CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(deterministic_parallel_reduction LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
enable_testing()
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
if(DEFINED NEGATIVE_SOURCE)
  add_executable(negative_visible "${NEGATIVE_SOURCE}" task_visible_test.cpp)
  add_executable(negative_hidden "${NEGATIVE_SOURCE}" .meta/task_hidden_test.cpp)
  foreach(name visible hidden)
    target_include_directories(negative_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
      target_compile_options(negative_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif()
  endforeach()
endif()
'''


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _inventory(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    if not root.is_dir():
        return records
    for config in sorted(root.rglob(".meta/config.json")):
        if ".state" in config.parts:
            continue
        task_root = config.parent.parent
        records.append(
            {
                "task_id": task_root.name,
                "relative_root": task_root.relative_to(root).as_posix(),
                "tree_hash": _tree_hash(task_root),
                "config_hash": _file_hash(config),
            }
        )
    return records


def _validate_output(out: Path) -> None:
    resolved = out.resolve()
    expansion = EXPANSION_ROOT.resolve()
    if resolved == expansion or expansion not in resolved.parents:
        _fail("unsafe_path", f"output must be a family below {EXPANSION_ROOT}: {out}")
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("unsafe_path", f"existing tree is read-only: {out}")
    cursor = out
    while cursor != EXPANSION_ROOT.parent and cursor != cursor.parent:
        if cursor.is_symlink():
            _fail("unsafe_path", f"symlink component: {cursor}")
        cursor = cursor.parent


def _chunks(size: int, workers: int) -> list[tuple[int, int]]:
    base, extra = divmod(size, workers)
    result: list[tuple[int, int]] = []
    begin = 0
    for worker in range(workers):
        end = begin + base + (1 if worker < extra else 0)
        result.append((begin, end))
        begin = end
    return result


def _floor_mod(value: int, modulus: int) -> int:
    return value % modulus


def _sample(case: Case, hidden: bool) -> tuple[list[int], list[int], int, int]:
    values = [8, 1, 7, 3, 9, 2, 6, 4, 11, 5] if hidden else [5, 2, 7, 1, 9, 3, 8, 4]
    keys = [-1, 0, 0, 1, 1, 2, 2, 3, 3, 4] if hidden else [-1, 0, 0, 1, 1, 2, 2, 3]
    workers = 4 if hidden else 3
    parameter = 4 if hidden else 3
    index = case.index
    if index in {5, 8, 33}:
        values = [-3, 0, 4, -1, 0, 7, 2, -5, 6, 0] if hidden else [-2, 0, 5, -1, 4, 0, 3, -6]
    if index in {6}:
        keys = [0, 0, 1, 1, 1, 2, 3, 3, 4, 4] if hidden else [0, 0, 1, 1, 2, 2, 2, 3]
    if index in {11}:
        keys = [-1, 0, 0, 2, 1, 3, 3, 6, 5, 8] if hidden else [-1, 0, 0, 1, 1, 3, 2, 6]
    if index in {34}:
        values = [2, 1, 3, -2, 1, 4, 0, 5, 2, -1] if hidden else [2, 1, 3, -2, 1, 4, 0, 5]
    if index == 27:
        values = [8, 1, 7, 3, 1, 2, 6, 4, 11, 5] if hidden else [5, 1, 7, 1, 9, 3, 8, 4]
    if index == 36:
        values = [1, 2, 4, 7, 0, 3, 5, 8, 2, 6] if hidden else [1, 3, 6, 2, 4, 8, 0, 7]
        keys = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2] if hidden else [0, 0, 0, 1, 1, 1, 2, 2]
    if index == 37:
        values = [0, 3, 3, 6, 8, 10, 5, 9, 12, 14] if hidden else [0, 2, 2, 5, 7, 9, 4, 8]
    if index == 38:
        values = [1, 1, 2, 2, 1, 3, 3, 4, 4, 4] if hidden else [1, 1, 2, 2, 1, 3, 3, 4]
        keys = [2, 3, 1, 4, 2, 1, 2, 1, 3, 2] if hidden else [2, 1, 3, 2, 4, 1, 2, 3]
    if index in {43, 44, 45, 46}:
        values = [1, 2, 4, 8, 3, 5, 7, 9, 6, 10] if hidden else [1, 3, 5, 8, 2, 4, 7, 9]
        keys = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2] if hidden else [0, 0, 0, 0, 1, 1, 1, 1]
    if index == 44:
        values = [1, 2, 4, 7, 9, 0, 2, 4, 8, 9] if hidden else [1, 3, 5, 8, 2, 3, 7, 9]
        keys = [0, 0, 0, 0, 0, 1, 1, 1, 1, 1] if hidden else [0, 0, 0, 0, 1, 1, 1, 1]
    if index == 45:
        values = [9, 7, 4, 1, 10, 8, 5, 2, 6, 3] if hidden else [8, 5, 3, 1, 9, 7, 4, 2]
        keys = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2] if hidden else [0, 0, 0, 0, 1, 1, 1, 1]
    if index in {48, 49}:
        keys = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4] if hidden else [0, 0, 1, 1, 2, 2, 3, 3]
    if index == 51:
        values = [1, -1, 1, 1, -1, 1, -1, 1, 1, -1] if hidden else [1, 1, -1, 1, -1, -1, 1, 1]
        keys = [0, 0, 0, 1, 1, 1, 2, 2, 2, 2] if hidden else [0, 0, 0, 1, 1, 1, 2, 2]
        parameter = 2
    if index == 52:
        values = [0, 1, 3, 2, 1, 0, 3, 2, 1, 2] if hidden else [0, 1, 3, 2, 1, 0, 3, 2]
    if index in {53, 55, 58}:
        keys = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4] if hidden else [0, 0, 1, 1, 2, 2, 3, 3]
    if index == 54:
        values = [0, 1, 3, 2, 1, 2, 3, 0, 2, 1] if hidden else [0, 1, 2, 3, 1, 2, 0, 3]
    return values, keys, workers, parameter


def _tree_partials(values: list[int], workers: int, operation: int, parameter: int) -> list[int]:
    partials: list[int] = []
    for begin, end in _chunks(len(values), workers):
        shard = values[begin:end]
        if not shard:
            continue
        if operation in {12, 21, 22, 23}:
            partials.append(sum(shard))
        elif operation == 13:
            partials.append(min(shard))
        elif operation == 14:
            partials.append(max(shard))
        elif operation == 15:
            import math

            value = 0
            for item in shard:
                value = math.gcd(value, abs(item))
            partials.append(value)
        elif operation == 16:
            import math

            value = 1
            for item in shard:
                item = abs(item)
                value = 0 if value == 0 or item == 0 else value // math.gcd(value, item) * item
            partials.append(value)
        elif operation == 17:
            value = 0
            for item in shard:
                value |= item
            partials.append(value)
        elif operation == 18:
            value = shard[0]
            for item in shard[1:]:
                value &= item
            partials.append(value)
        elif operation == 19:
            value = 0
            for item in shard:
                value ^= item
            partials.append(value)
        elif operation == 20:
            value = 1
            for item in shard:
                value *= item
            partials.append(value)
        else:
            raise AssertionError(operation)
    return partials


def _oracle(case: Case, values: list[int], keys: list[int], workers: int, parameter: int) -> list[int] | None:
    if len(values) != len(keys) or len(values) > 64 or workers < 1 or workers > 8 or parameter < 1 or parameter > 16:
        return None
    if any(abs(value) > 1000 for value in values + keys):
        return None
    op = case.index
    ranges = _chunks(len(values), workers)
    if op == 0:
        return [sum(values[begin:end]) for begin, end in ranges]
    if op == 1:
        out = [0] * workers
        for index, value in enumerate(values):
            out[index % workers] += value
        return out
    if op == 2:
        out = [0] * workers
        for value, key in zip(values, keys, strict=True):
            out[_floor_mod(key, workers)] += value
        return out
    if op == 3:
        if any(value < 0 for value in values):
            return None
        loads = [0] * workers
        out = []
        for cost in values:
            owner = min(range(workers), key=lambda worker: (loads[worker], worker))
            loads[owner] += cost
            out.append(owner)
        return out
    if op == 4:
        if any(value < 0 for value in values):
            return None
        if not values:
            return []
        total = sum(values)
        if total == 0:
            return [end for _, end in ranges]
        out: list[int] = []
        cumulative = 0
        target_worker = 1
        for index, value in enumerate(values):
            cumulative += value
            while target_worker < workers and cumulative * workers >= total * target_worker:
                out.append(index + 1)
                target_worker += 1
        while len(out) < workers - 1:
            out.append(len(values))
        out.append(len(values))
        return out
    if op == 5:
        return [sum(value < 0 for value in values), sum(value == 0 for value in values), sum(value > 0 for value in values)]
    if op == 6:
        if not values:
            return []
        target = max(1, (len(values) + workers - 1) // workers)
        out: list[int] = []
        last_cut = 0
        for index in range(1, len(keys)):
            if len(out) < workers - 1 and index - last_cut >= target and keys[index] != keys[index - 1]:
                out.append(index)
                last_cut = index
        out.append(len(values))
        return out
    if op == 7:
        out = [0] * workers
        for index, value in enumerate(values):
            block = index // parameter
            if workers == 1:
                owner = 0
            else:
                phase = block % (2 * workers - 2)
                owner = phase if phase < workers else 2 * workers - 2 - phase
            out[owner] += value
        return out
    if op == 8:
        out = [0] * parameter
        for value in values:
            out[_floor_mod(value, parameter)] += 1
        return out
    if op == 9:
        out = []
        for begin, end in ranges:
            if begin == end:
                out.append(0)
                continue
            lo = max(0, begin - 1)
            hi = min(len(values), end + 1)
            out.append(sum(values[lo:hi]))
        return out
    if op == 10:
        out = []
        capacity_records = workers * parameter
        for index in range(len(values)):
            out.append(index // parameter if index < capacity_records else (index - capacity_records) % workers)
        return out
    if op == 11:
        levels: list[int] = []
        for index, parent in enumerate(keys):
            if parent == -1:
                levels.append(0)
            elif parent < 0 or parent >= index:
                return None
            else:
                levels.append(levels[parent] + 1)
        return [levels.count(level) for level in range(max(levels, default=-1) + 1)]
    if 12 <= op <= 22:
        if op in {17, 18, 19} and any(value < 0 for value in values):
            return None
        current = _tree_partials(values, workers, op, parameter)
        if not current:
            return []
        out = list(current)
        import math

        while len(current) > 1:
            next_round: list[int] = []
            for index in range(0, len(current), 2):
                if index + 1 == len(current):
                    next_round.append(current[index])
                    continue
                left, right = current[index], current[index + 1]
                if op == 12:
                    combined = left + right
                elif op == 13:
                    combined = min(left, right)
                elif op == 14:
                    combined = max(left, right)
                elif op == 15:
                    combined = math.gcd(left, right)
                elif op == 16:
                    combined = 0 if left == 0 or right == 0 else left // math.gcd(left, right) * right
                elif op == 17:
                    combined = left | right
                elif op == 18:
                    combined = left & right
                elif op == 19:
                    combined = left ^ right
                elif op == 20:
                    combined = left * right
                elif op == 21:
                    combined = max(-parameter, min(parameter, left + right))
                elif op == 22:
                    combined = left - right
                else:
                    raise AssertionError(op)
                next_round.append(combined)
            out.extend(next_round)
            current = next_round
        return out
    if op == 23:
        current = _tree_partials(values, workers, op, parameter)
        if not current:
            return []
        out = list(current)
        while len(current) > 1:
            next_round = []
            for index in range(0, len(current), 3):
                group = current[index : index + 3]
                next_round.append(sorted(group)[1] if len(group) == 3 else min(group))
            out.extend(next_round)
            current = next_round
        return out
    if op == 24:
        return [sum(values), len(values)]
    if op == 25:
        return [] if not values else [min(values), max(values)]
    if op == 26:
        return [sum(values), sum(value * value for value in values)]
    if op == 27:
        return [] if not values else [min(values), min(index for index, value in enumerate(values) if value == min(values))]
    if op == 28:
        return [] if not values else [max(values), min(index for index, value in enumerate(values) if value == max(values))]
    if op == 29:
        chosen = sorted(enumerate(values), key=lambda item: (-item[1], item[0]))[:parameter]
        return [value for _, value in chosen] + [index for index, _ in chosen]
    if op == 30:
        totals = [0] * parameter
        out = []
        for begin, end in ranges:
            partial = [0] * parameter
            for value in values[begin:end]:
                partial[_floor_mod(value, parameter)] += 1
            out.extend(partial)
            totals = [left + right for left, right in zip(totals, partial, strict=True)]
        return out + totals
    if op == 31:
        return sorted(set(values))
    if op == 32:
        if not values:
            return []
        best: tuple[int, int, int] | None = None
        for begin in range(len(values)):
            total = 0
            for end in range(begin + 1, len(values) + 1):
                total += values[end - 1]
                candidate = (total, begin, end)
                if best is None or total > best[0] or (total == best[0] and (begin < best[1] or (begin == best[1] and end - begin < best[2] - best[1]))):
                    best = candidate
        assert best is not None
        return list(best)
    if op == 33:
        net = 0
        minimum = 0
        for value in values:
            net += 1 if value > 0 else -1
            minimum = min(minimum, net)
        return [net, minimum]
    if op == 34:
        if len(values) % 2:
            return None
        a, b = 1, 0
        for index in range(0, len(values), 2):
            next_a, next_b = values[index], values[index + 1]
            a, b = next_a * a, next_a * b + next_b
        return [a, b]
    if op == 35:
        if not values:
            return []
        import math

        numerator, denominator = sum(values), len(values)
        divisor = math.gcd(abs(numerator), denominator)
        return [numerator // divisor, denominator // divisor]
    if op == 36:
        positions: dict[int, int] = {}
        rows = []
        for value, shard in zip(values, keys, strict=True):
            position = positions.get(shard, 0)
            positions[shard] = position + 1
            rows.append((value, shard, position))
        for shard in set(keys):
            shard_values = [value for value, key in zip(values, keys, strict=True) if key == shard]
            if shard_values != sorted(shard_values):
                return None
        return [row[0] for row in sorted(rows)]
    if op == 37:
        if len(values) % 2:
            return None
        intervals = []
        for index in range(0, len(values), 2):
            if values[index] > values[index + 1]:
                return None
            intervals.append((values[index], values[index + 1]))
        intervals.sort()
        merged: list[list[int]] = []
        for lo, hi in intervals:
            if not merged or lo > merged[-1][1]:
                merged.append([lo, hi])
            else:
                merged[-1][1] = max(merged[-1][1], hi)
        return [item for interval in merged for item in interval]
    if op == 38:
        out: list[int] = []
        for symbol, count in zip(values, keys, strict=True):
            if count <= 0:
                return None
            if out and out[-2] == symbol:
                out[-1] += count
            else:
                out.extend([symbol, count])
        return out
    if op == 39:
        counts: dict[int, int] = {}
        for key, count in zip(keys, values, strict=True):
            if count < 0:
                return None
            counts[key] = counts.get(key, 0) + count
        return [item for key in sorted(counts) for item in (key, counts[key])]
    if op == 40:
        out = []
        total = 0
        for value in values:
            total += value
            out.append(total)
        return out
    if op == 41:
        out = [0] * len(values)
        total = 0
        for index in range(len(values) - 1, -1, -1):
            total += values[index]
            out[index] = total
        return out
    if op == 42:
        digest = 0
        for value in values:
            if value < 0:
                return None
            digest = (digest * parameter + value) % 1_000_003
        return [digest, len(values)]
    if op == 43:
        for shard in set(keys):
            shard_values = [value for value, key in zip(values, keys, strict=True) if key == shard]
            if any(left >= right for left, right in zip(shard_values, shard_values[1:])):
                return None
        return sorted(set(values))
    if op == 44:
        if not keys:
            return []
        if set(keys) != {0, 1}:
            return None
        left = [value for value, key in zip(values, keys, strict=True) if key == 0]
        right = [value for value, key in zip(values, keys, strict=True) if key == 1]
        if left != sorted(left) or right != sorted(right):
            return None
        remaining = right[:]
        out = []
        for value in left:
            if value in remaining:
                out.append(value)
                remaining.remove(value)
        return out
    if op == 45:
        for shard in set(keys):
            shard_values = [value for value, key in zip(values, keys, strict=True) if key == shard]
            if shard_values != sorted(shard_values, reverse=True):
                return None
        rows = sorted(((value, shard, index) for index, (value, shard) in enumerate(zip(values, keys, strict=True))), key=lambda row: (-row[0], row[1], row[2]))
        return [row[0] for row in rows[:parameter]]
    if op == 46:
        for shard in set(keys):
            shard_values = [value for value, key in zip(values, keys, strict=True) if key == shard]
            if shard_values != sorted(shard_values):
                return None
        merged = sorted(values)
        if not merged:
            return []
        out = merged[::parameter]
        if out[-1] != merged[-1]:
            out.append(merged[-1])
        return out
    if op == 47:
        totals: dict[int, int] = {}
        for coordinate, value in zip(keys, values, strict=True):
            totals[coordinate] = totals.get(coordinate, 0) + value
        return [item for coordinate in sorted(totals) if totals[coordinate] != 0 for item in (coordinate, totals[coordinate])]
    if op in {48, 49}:
        if any(key < 0 or value < 0 for key, value in zip(keys, values, strict=True)):
            return None
        totals: dict[int, int] = {}
        for key, value in zip(keys, values, strict=True):
            if key not in totals:
                totals[key] = value
            else:
                totals[key] = max(totals[key], value) if op == 48 else min(totals[key], value)
        return [item for key in sorted(totals) for item in (key, totals[key])]
    if op == 50:
        return sorted({key for key, value in zip(keys, values, strict=True) if value != 0})
    if op == 51:
        votes: dict[int, list[int]] = {}
        for key, value in zip(keys, values, strict=True):
            if value == 0:
                return None
            counts = votes.setdefault(key, [0, 0])
            counts[0 if value > 0 else 1] += 1
        return [key for key in sorted(votes) if votes[key][0] >= parameter and votes[key][0] > votes[key][1]]
    if op == 52:
        precedence = {0: 0, 1: 1, 3: 2, 2: 3}
        states: dict[int, int] = {}
        for key, value in zip(keys, values, strict=True):
            if value not in precedence:
                return None
            if key not in states or precedence[value] > precedence[states[key]]:
                states[key] = value
        return [item for key in sorted(states) for item in (key, states[key])]
    if op == 53:
        out = []
        for key in sorted(set(keys)):
            for value, item_key in zip(values, keys, strict=True):
                if item_key != key:
                    continue
                if value < 0:
                    break
                out.extend([key, value])
        return out
    if op == 54:
        worker_for_index = {}
        for worker, (begin, end) in enumerate(ranges):
            for index in range(begin, end):
                worker_for_index[index] = worker
        rows = sorted((key, worker_for_index[index], index, value) for index, (key, value) in enumerate(zip(keys, values, strict=True)))
        return [item for key, _, _, value in rows for item in (key, value)]
    if op == 55:
        best: dict[int, tuple[int, int]] = {}
        for index, (key, value) in enumerate(zip(keys, values, strict=True)):
            current = best.get(key)
            if current is None or value > current[0]:
                best[key] = (value, index)
        return [item for key in sorted(best) for item in (key, best[key][0], best[key][1])]
    if op == 56:
        arrivals: dict[int, set[int]] = {}
        for generation, participant in zip(keys, values, strict=True):
            arrivals.setdefault(generation, set()).add(participant)
        return [item for generation in sorted(arrivals) for item in (generation, len(arrivals[generation]))]
    if op == 57:
        if any(value < 0 for value in values):
            return None
        loads = [0] * workers
        owners = []
        for cost, preferred_key in zip(values, keys, strict=True):
            preferred = _floor_mod(preferred_key, workers)
            if loads[preferred] > parameter:
                owner = min(range(workers), key=lambda worker: (loads[worker], worker))
            else:
                owner = preferred
            loads[owner] += cost
            owners.append(owner)
        return owners + loads
    if op == 58:
        worker_for_index = {}
        for worker, (begin, end) in enumerate(ranges):
            for index in range(begin, end):
                worker_for_index[index] = worker
        best: dict[int, tuple[int, int, int]] = {}
        for index, (key, value) in enumerate(zip(keys, values, strict=True)):
            candidate = (value, -worker_for_index[index], -index)
            if key not in best or candidate > best[key]:
                best[key] = candidate
        return [item for key in sorted(best) for item in (key, best[key][0], -best[key][1])]
    if op == 59:
        worker_for_index = {}
        for worker, (begin, end) in enumerate(ranges):
            for index in range(begin, end):
                worker_for_index[index] = worker
        rows = sorted((key, worker_for_index[index], index, value) for index, (key, value) in enumerate(zip(keys, values, strict=True)))
        digest = 0
        for _, _, _, value in rows:
            digest = (digest * parameter + value) % 1_000_003
        return [digest, len(rows)]
    raise AssertionError(op)


def _api(case: Case) -> str:
    return f"std::optional<std::vector<long long>> {case.stem}(const {case.request_type}& request)"


def _header(case: Case) -> str:
    guard = case.task_id.replace("-", "_").upper() + "_H"
    return f'''#ifndef {guard}
#define {guard}
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {{
struct {case.request_type} {{
  std::vector<long long> values;
  std::vector<long long> keys;
  std::size_t workers;
  long long parameter;
}};
{_api(case)};
}}
#endif
'''


CPP_PREAMBLE = r'''
#include <algorithm>
#include <array>
#include <cstdlib>
#include <functional>
#include <limits>
#include <map>
#include <numeric>
#include <set>
#include <tuple>
#include <utility>
#include <vector>
namespace curriculum {
namespace {
using i64 = long long;
[[maybe_unused]] std::size_t floor_mod(i64 value,std::size_t modulus){i64 m=static_cast<i64>(modulus);i64 result=value%m;if(result<0)result+=m;return static_cast<std::size_t>(result);}
[[maybe_unused]] std::vector<std::pair<std::size_t,std::size_t>> chunks(std::size_t n,std::size_t workers){std::vector<std::pair<std::size_t,std::size_t>> out;std::size_t base=n/workers,extra=n%workers,begin=0;for(std::size_t worker=0;worker<workers;++worker){std::size_t end=begin+base+(worker<extra?1U:0U);out.push_back({begin,end});begin=end;}return out;}
[[maybe_unused]] bool checked_add(i64 left,i64 right,i64& out){return !__builtin_add_overflow(left,right,&out);}
[[maybe_unused]] bool checked_mul(i64 left,i64 right,i64& out){return !__builtin_mul_overflow(left,right,&out);}
bool valid_common(const std::vector<i64>& values,const std::vector<i64>& keys,std::size_t workers,i64 parameter){if(values.size()!=keys.size()||values.size()>64U||workers==0U||workers>8U||parameter<1||parameter>16)return false;for(i64 value:values)if(value < -1000 || value > 1000)return false;for(i64 key:keys)if(key < -1000 || key > 1000)return false;return true;}
}
'''


def _tree_cpp(operation: int) -> str:
    initial = {
        12: "i64 value=0;for(std::size_t i=begin;i<end;++i)if(!checked_add(value,v[i],value))return std::nullopt;current.push_back(value);",
        13: "current.push_back(*std::min_element(v.begin()+static_cast<std::ptrdiff_t>(begin),v.begin()+static_cast<std::ptrdiff_t>(end)));",
        14: "current.push_back(*std::max_element(v.begin()+static_cast<std::ptrdiff_t>(begin),v.begin()+static_cast<std::ptrdiff_t>(end)));",
        15: "i64 value=0;for(std::size_t i=begin;i<end;++i)value=std::gcd(value,std::llabs(v[i]));current.push_back(value);",
        16: "i64 value=1;for(std::size_t i=begin;i<end;++i){i64 item=std::llabs(v[i]);if(value==0||item==0)value=0;else{ i64 scaled=value/std::gcd(value,item);if(!checked_mul(scaled,item,value))return std::nullopt;}}current.push_back(value);",
        17: "i64 value=0;for(std::size_t i=begin;i<end;++i)value|=v[i];current.push_back(value);",
        18: "i64 value=v[begin];for(std::size_t i=begin+1;i<end;++i)value&=v[i];current.push_back(value);",
        19: "i64 value=0;for(std::size_t i=begin;i<end;++i)value^=v[i];current.push_back(value);",
        20: "i64 value=1;for(std::size_t i=begin;i<end;++i)if(!checked_mul(value,v[i],value))return std::nullopt;current.push_back(value);",
        21: "i64 value=0;for(std::size_t i=begin;i<end;++i)if(!checked_add(value,v[i],value))return std::nullopt;current.push_back(value);",
        22: "i64 value=0;for(std::size_t i=begin;i<end;++i)if(!checked_add(value,v[i],value))return std::nullopt;current.push_back(value);",
    }[operation]
    combine = {
        12: "if(!checked_add(left,right,combined))return std::nullopt;",
        13: "combined=std::min(left,right);",
        14: "combined=std::max(left,right);",
        15: "combined=std::gcd(left,right);",
        16: "if(left==0||right==0)combined=0;else{ i64 scaled=left/std::gcd(left,right);if(!checked_mul(scaled,right,combined))return std::nullopt;}",
        17: "combined=left|right;",
        18: "combined=left&right;",
        19: "combined=left^right;",
        20: "if(!checked_mul(left,right,combined))return std::nullopt;",
        21: "if(!checked_add(left,right,combined))return std::nullopt;combined=std::max(-p,std::min(p,combined));",
        22: "if(!checked_add(left,-right,combined))return std::nullopt;",
    }[operation]
    nonnegative = "if(std::any_of(v.begin(),v.end(),[](i64 value){return value<0;}))return std::nullopt;" if operation in {17, 18, 19} else ""
    return f'''{nonnegative}
std::vector<i64> current;for(const auto& range:ranges){{std::size_t begin=range.first,end=range.second;if(begin==end)continue;{initial}}}
if(current.empty())return out;out=current;
while(current.size()>1U){{std::vector<i64> next;for(std::size_t i=0;i<current.size();i+=2){{if(i+1==current.size()){{next.push_back(current[i]);continue;}}i64 left=current[i],right=current[i+1],combined=0;{combine}next.push_back(combined);}}out.insert(out.end(),next.begin(),next.end());current=std::move(next);}}
'''


def _operation_cpp(operation: int, *, tie_later: bool = False) -> str:
    if 12 <= operation <= 22:
        return _tree_cpp(operation)
    bodies = {
        0: "for(const auto& range:ranges){i64 total=0;for(std::size_t i=range.first;i<range.second;++i)if(!checked_add(total,v[i],total))return std::nullopt;out.push_back(total);}",
        1: "out.assign(w,0);for(std::size_t i=0;i<v.size();++i)if(!checked_add(out[i%w],v[i],out[i%w]))return std::nullopt;",
        2: "out.assign(w,0);for(std::size_t i=0;i<v.size();++i){std::size_t owner=floor_mod(k[i],w);if(!checked_add(out[owner],v[i],out[owner]))return std::nullopt;}",
        3: "if(std::any_of(v.begin(),v.end(),[](i64 value){return value<0;}))return std::nullopt;std::vector<i64> loads(w,0);for(i64 cost:v){std::size_t owner=0;for(std::size_t worker=1;worker<w;++worker)if(std::tie(loads[worker],worker)<std::tie(loads[owner],owner))owner=worker;if(!checked_add(loads[owner],cost,loads[owner]))return std::nullopt;out.push_back(static_cast<i64>(owner));}",
        4: "if(std::any_of(v.begin(),v.end(),[](i64 value){return value<0;}))return std::nullopt;if(v.empty())return out;i64 total=std::accumulate(v.begin(),v.end(),i64{0});if(total==0){for(const auto& range:ranges)out.push_back(static_cast<i64>(range.second));return out;}i64 cumulative=0;std::size_t target=1;for(std::size_t i=0;i<v.size();++i){cumulative+=v[i];while(target<w&&cumulative*static_cast<i64>(w)>=total*static_cast<i64>(target)){out.push_back(static_cast<i64>(i+1));++target;}}while(out.size()<w-1)out.push_back(static_cast<i64>(v.size()));out.push_back(static_cast<i64>(v.size()));",
        5: "out={0,0,0};for(i64 value:v)++out[value<0?0U:(value==0?1U:2U)];",
        6: "if(v.empty())return out;std::size_t target=std::max<std::size_t>(1,(v.size()+w-1)/w),last=0;for(std::size_t i=1;i<k.size();++i)if(out.size()<w-1&&i-last>=target&&k[i]!=k[i-1]){out.push_back(static_cast<i64>(i));last=i;}out.push_back(static_cast<i64>(v.size()));",
        7: "out.assign(w,0);for(std::size_t i=0;i<v.size();++i){std::size_t block=i/static_cast<std::size_t>(p),owner=0;if(w>1){std::size_t period=2*w-2,phase=block%period;owner=phase<w?phase:period-phase;}if(!checked_add(out[owner],v[i],out[owner]))return std::nullopt;}",
        8: "out.assign(static_cast<std::size_t>(p),0);for(i64 value:v)++out[floor_mod(value,static_cast<std::size_t>(p))];",
        9: "for(const auto& range:ranges){if(range.first==range.second){out.push_back(0);continue;}std::size_t lo=range.first==0?0:range.first-1,hi=std::min(v.size(),range.second+1);i64 total=0;for(std::size_t i=lo;i<hi;++i)if(!checked_add(total,v[i],total))return std::nullopt;out.push_back(total);}",
        10: "std::size_t capacity=w*static_cast<std::size_t>(p);for(std::size_t i=0;i<v.size();++i)out.push_back(static_cast<i64>(i<capacity?i/static_cast<std::size_t>(p):(i-capacity)%w));",
        11: "std::vector<i64> levels;for(std::size_t i=0;i<k.size();++i){if(k[i]==-1)levels.push_back(0);else if(k[i]<0||static_cast<std::size_t>(k[i])>=i)return std::nullopt;else levels.push_back(levels[static_cast<std::size_t>(k[i])]+1);}i64 maximum=levels.empty()?-1:*std::max_element(levels.begin(),levels.end());for(i64 level=0;level<=maximum;++level)out.push_back(static_cast<i64>(std::count(levels.begin(),levels.end(),level)));",
        23: "std::vector<i64> current;for(const auto& range:ranges){if(range.first==range.second)continue;i64 total=0;for(std::size_t i=range.first;i<range.second;++i)if(!checked_add(total,v[i],total))return std::nullopt;current.push_back(total);}if(current.empty())return out;out=current;while(current.size()>1U){std::vector<i64> next;for(std::size_t i=0;i<current.size();i+=3){std::size_t count=std::min<std::size_t>(3,current.size()-i);if(count==3){std::array<i64,3> triple{current[i],current[i+1],current[i+2]};std::sort(triple.begin(),triple.end());next.push_back(triple[1]);}else if(count==2)next.push_back(std::min(current[i],current[i+1]));else next.push_back(current[i]);}out.insert(out.end(),next.begin(),next.end());current=std::move(next);}",
        24: "i64 total=0;for(i64 value:v)if(!checked_add(total,value,total))return std::nullopt;out={total,static_cast<i64>(v.size())};",
        25: "if(!v.empty())out={*std::min_element(v.begin(),v.end()),*std::max_element(v.begin(),v.end())};",
        26: "i64 total=0,squares=0;for(i64 value:v){i64 square=0;if(!checked_add(total,value,total)||!checked_mul(value,value,square)||!checked_add(squares,square,squares))return std::nullopt;}out={total,squares};",
        27: "if(!v.empty()){const bool prefer_later=" + ("true" if tie_later else "false") + ";auto it=v.begin();for(auto scan=v.begin()+1;scan!=v.end();++scan)if(*scan<*it||(prefer_later&&*scan==*it))it=scan;out={*it,static_cast<i64>(it-v.begin())};}",
        28: "if(!v.empty()){auto it=std::max_element(v.begin(),v.end());out={*it,static_cast<i64>(it-v.begin())};}",
        29: "std::vector<std::pair<i64,std::size_t>> rows;for(std::size_t i=0;i<v.size();++i)rows.push_back({v[i],i});std::sort(rows.begin(),rows.end(),[](const auto& a,const auto& b){return a.first!=b.first?a.first>b.first:a.second<b.second;});if(rows.size()>static_cast<std::size_t>(p))rows.resize(static_cast<std::size_t>(p));for(const auto& row:rows)out.push_back(row.first);for(const auto& row:rows)out.push_back(static_cast<i64>(row.second));",
        30: "std::vector<i64> totals(static_cast<std::size_t>(p),0);for(const auto& range:ranges){std::vector<i64> partial(static_cast<std::size_t>(p),0);for(std::size_t i=range.first;i<range.second;++i)++partial[floor_mod(v[i],static_cast<std::size_t>(p))];out.insert(out.end(),partial.begin(),partial.end());for(std::size_t i=0;i<partial.size();++i)totals[i]+=partial[i];}out.insert(out.end(),totals.begin(),totals.end());",
        31: "out=v;std::sort(out.begin(),out.end());out.erase(std::unique(out.begin(),out.end()),out.end());",
        32: "if(v.empty())return out;bool have=false;i64 best_sum=0,best_begin=0,best_end=0;for(std::size_t begin=0;begin<v.size();++begin){i64 total=0;for(std::size_t end=begin+1;end<=v.size();++end){if(!checked_add(total,v[end-1],total))return std::nullopt;i64 b=static_cast<i64>(begin),e=static_cast<i64>(end);if(!have||total>best_sum||(total==best_sum&&(b<best_begin||(b==best_begin&&e-b<best_end-best_begin)))){have=true;best_sum=total;best_begin=b;best_end=e;}}}out={best_sum,best_begin,best_end};",
        33: "i64 net=0,minimum=0;for(i64 value:v){net+=value>0?1:-1;minimum=std::min(minimum,net);}out={net,minimum};",
        34: "if(v.size()%2U!=0U)return std::nullopt;i64 a=1,b=0;for(std::size_t i=0;i<v.size();i+=2){i64 next_a=0,next_b=0,product=0;if(!checked_mul(v[i],a,next_a)||!checked_mul(v[i],b,product)||!checked_add(product,v[i+1],next_b))return std::nullopt;a=next_a;b=next_b;}out={a,b};",
        35: "if(v.empty())return out;i64 numerator=0;for(i64 value:v)if(!checked_add(numerator,value,numerator))return std::nullopt;i64 denominator=static_cast<i64>(v.size()),divisor=std::gcd(std::llabs(numerator),denominator);out={numerator/divisor,denominator/divisor};",
        36: "std::map<i64,std::size_t> positions;std::vector<std::tuple<i64,i64,std::size_t>> rows;std::map<i64,std::vector<i64>> shards;for(std::size_t i=0;i<v.size();++i){rows.push_back({v[i],k[i],positions[k[i]]++});shards[k[i]].push_back(v[i]);}for(const auto& shard:shards)if(!std::is_sorted(shard.second.begin(),shard.second.end()))return std::nullopt;std::sort(rows.begin(),rows.end());for(const auto& row:rows)out.push_back(std::get<0>(row));",
        37: "if(v.size()%2U!=0U)return std::nullopt;std::vector<std::pair<i64,i64>> intervals;for(std::size_t i=0;i<v.size();i+=2){if(v[i]>v[i+1])return std::nullopt;intervals.push_back({v[i],v[i+1]});}std::sort(intervals.begin(),intervals.end());for(const auto& interval:intervals){if(out.empty()||interval.first>out.back()){out.push_back(interval.first);out.push_back(interval.second);}else out.back()=std::max(out.back(),interval.second);}",
        38: "for(std::size_t i=0;i<v.size();++i){if(k[i]<=0)return std::nullopt;if(!out.empty()&&out[out.size()-2]==v[i]){if(!checked_add(out.back(),k[i],out.back()))return std::nullopt;}else{out.push_back(v[i]);out.push_back(k[i]);}}",
        39: "std::map<i64,i64> counts;for(std::size_t i=0;i<v.size();++i){if(v[i]<0)return std::nullopt;if(!checked_add(counts[k[i]],v[i],counts[k[i]]))return std::nullopt;}for(const auto& item:counts){out.push_back(item.first);out.push_back(item.second);}",
        40: "i64 total=0;for(i64 value:v){if(!checked_add(total,value,total))return std::nullopt;out.push_back(total);}",
        41: "out.assign(v.size(),0);i64 total=0;for(std::size_t i=v.size();i-->0;){if(!checked_add(total,v[i],total))return std::nullopt;out[i]=total;}",
        42: "i64 digest=0;for(i64 value:v){if(value<0)return std::nullopt;digest=(digest*p+value)%1000003;}out={digest,static_cast<i64>(v.size())};",
        43: "std::map<i64,std::vector<i64>> shards;for(std::size_t i=0;i<v.size();++i)shards[k[i]].push_back(v[i]);for(const auto& shard:shards)if(std::adjacent_find(shard.second.begin(),shard.second.end(),std::greater_equal<i64>())!=shard.second.end())return std::nullopt;out=v;std::sort(out.begin(),out.end());out.erase(std::unique(out.begin(),out.end()),out.end());",
        44: "if(k.empty())return out;if(std::set<i64>(k.begin(),k.end())!=std::set<i64>{0,1})return std::nullopt;std::vector<i64> left,right;for(std::size_t i=0;i<v.size();++i)(k[i]==0?left:right).push_back(v[i]);if(!std::is_sorted(left.begin(),left.end())||!std::is_sorted(right.begin(),right.end()))return std::nullopt;for(i64 value:left){auto it=std::find(right.begin(),right.end(),value);if(it!=right.end()){out.push_back(value);right.erase(it);}}",
        45: "std::map<i64,std::vector<i64>> shards;for(std::size_t i=0;i<v.size();++i)shards[k[i]].push_back(v[i]);for(const auto& shard:shards)if(!std::is_sorted(shard.second.begin(),shard.second.end(),std::greater_equal<i64>()))return std::nullopt;std::vector<std::tuple<i64,i64,std::size_t>> rows;for(std::size_t i=0;i<v.size();++i)rows.push_back({-v[i],k[i],i});std::sort(rows.begin(),rows.end());for(std::size_t i=0;i<std::min(rows.size(),static_cast<std::size_t>(p));++i)out.push_back(-std::get<0>(rows[i]));",
        46: "std::map<i64,std::vector<i64>> shards;for(std::size_t i=0;i<v.size();++i)shards[k[i]].push_back(v[i]);for(const auto& shard:shards)if(!std::is_sorted(shard.second.begin(),shard.second.end()))return std::nullopt;std::vector<i64> merged=v;std::sort(merged.begin(),merged.end());if(merged.empty())return out;for(std::size_t i=0;i<merged.size();i+=static_cast<std::size_t>(p))out.push_back(merged[i]);if(out.back()!=merged.back())out.push_back(merged.back());",
        47: "std::map<i64,i64> totals;for(std::size_t i=0;i<v.size();++i)if(!checked_add(totals[k[i]],v[i],totals[k[i]]))return std::nullopt;for(const auto& item:totals)if(item.second!=0){out.push_back(item.first);out.push_back(item.second);}",
        48: "std::map<i64,i64> best;for(std::size_t i=0;i<v.size();++i){if(k[i]<0||v[i]<0)return std::nullopt;auto it=best.find(k[i]);if(it==best.end()||v[i]>it->second)best[k[i]]=v[i];}for(const auto& item:best){out.push_back(item.first);out.push_back(item.second);}",
        49: "std::map<i64,i64> best;for(std::size_t i=0;i<v.size();++i){if(k[i]<0||v[i]<0)return std::nullopt;auto it=best.find(k[i]);if(it==best.end()||v[i]<it->second)best[k[i]]=v[i];}for(const auto& item:best){out.push_back(item.first);out.push_back(item.second);}",
        50: "std::set<i64> conflicts;for(std::size_t i=0;i<v.size();++i)if(v[i]!=0)conflicts.insert(k[i]);out.assign(conflicts.begin(),conflicts.end());",
        51: "std::map<i64,std::pair<i64,i64>> votes;for(std::size_t i=0;i<v.size();++i){if(v[i]==0)return std::nullopt;if(v[i]>0)++votes[k[i]].first;else ++votes[k[i]].second;}for(const auto& item:votes)if(item.second.first>=p&&item.second.first>item.second.second)out.push_back(item.first);",
        52: "const std::map<i64,i64> rank{{0,0},{1,1},{3,2},{2,3}};std::map<i64,i64> states;for(std::size_t i=0;i<v.size();++i){if(rank.count(v[i])==0U)return std::nullopt;auto it=states.find(k[i]);if(it==states.end()||rank.at(v[i])>rank.at(it->second))states[k[i]]=v[i];}for(const auto& item:states){out.push_back(item.first);out.push_back(item.second);}",
        53: "std::set<i64> streams(k.begin(),k.end());for(i64 stream:streams)for(std::size_t i=0;i<v.size();++i)if(k[i]==stream){if(v[i]<0)break;out.push_back(stream);out.push_back(v[i]);}",
        54: "std::vector<std::size_t> owner(v.size());for(std::size_t worker=0;worker<ranges.size();++worker)for(std::size_t i=ranges[worker].first;i<ranges[worker].second;++i)owner[i]=worker;std::vector<std::tuple<i64,std::size_t,std::size_t,i64>> rows;for(std::size_t i=0;i<v.size();++i)rows.push_back({k[i],owner[i],i,v[i]});std::sort(rows.begin(),rows.end());for(const auto& row:rows){out.push_back(std::get<0>(row));out.push_back(std::get<3>(row));}",
        55: "std::map<i64,std::pair<i64,std::size_t>> best;for(std::size_t i=0;i<v.size();++i){auto it=best.find(k[i]);if(it==best.end()||v[i]>it->second.first)best[k[i]]={v[i],i};}for(const auto& item:best){out.push_back(item.first);out.push_back(item.second.first);out.push_back(static_cast<i64>(item.second.second));}",
        56: "std::map<i64,std::set<i64>> arrivals;for(std::size_t i=0;i<v.size();++i)arrivals[k[i]].insert(v[i]);for(const auto& item:arrivals){out.push_back(item.first);out.push_back(static_cast<i64>(item.second.size()));}",
        57: "if(std::any_of(v.begin(),v.end(),[](i64 value){return value<0;}))return std::nullopt;std::vector<i64> loads(w,0);for(std::size_t i=0;i<v.size();++i){std::size_t preferred=floor_mod(k[i],w),owner=preferred;if(loads[preferred]>p){owner=0;for(std::size_t worker=1;worker<w;++worker)if(std::tie(loads[worker],worker)<std::tie(loads[owner],owner))owner=worker;}loads[owner]+=v[i];out.push_back(static_cast<i64>(owner));}out.insert(out.end(),loads.begin(),loads.end());",
        58: "std::vector<std::size_t> owner(v.size());for(std::size_t worker=0;worker<ranges.size();++worker)for(std::size_t i=ranges[worker].first;i<ranges[worker].second;++i)owner[i]=worker;std::map<i64,std::tuple<i64,std::size_t,std::size_t>> best;for(std::size_t i=0;i<v.size();++i){auto candidate=std::make_tuple(v[i],std::numeric_limits<std::size_t>::max()-owner[i],std::numeric_limits<std::size_t>::max()-i);if(best.count(k[i])==0U||candidate>best[k[i]])best[k[i]]=candidate;}for(const auto& item:best){out.push_back(item.first);out.push_back(std::get<0>(item.second));out.push_back(static_cast<i64>(std::numeric_limits<std::size_t>::max()-std::get<1>(item.second)));}",
        59: "std::vector<std::size_t> owner(v.size());for(std::size_t worker=0;worker<ranges.size();++worker)for(std::size_t i=ranges[worker].first;i<ranges[worker].second;++i)owner[i]=worker;std::vector<std::tuple<i64,std::size_t,std::size_t,i64>> rows;for(std::size_t i=0;i<v.size();++i)rows.push_back({k[i],owner[i],i,v[i]});std::sort(rows.begin(),rows.end());i64 digest=0;for(const auto& row:rows){i64 value=std::get<3>(row)%1000003;if(value<0)value+=1000003;digest=(digest*p+value)%1000003;}out={digest,static_cast<i64>(rows.size())};",
    }
    return bodies[operation]


def _reference(case: Case, *, omit_terminal: bool = False, tie_later: bool = False, max_workers: int = 8) -> str:
    bug = "if(!out.empty())out.pop_back();" if omit_terminal else ""
    preamble = CPP_PREAMBLE.replace("workers>8U", f"workers>{max_workers}U")
    # The compact operation table is an owner-maintenance representation, not
    # the emitted source style.  Give every statement its own physical line so
    # strict GCC/Clang builds cannot interpret a following declaration as
    # misleadingly guarded by an unbraced one-line conditional.
    operation = _operation_cpp(case.index, tie_later=tie_later).replace(";", ";\n")
    return f'''#include "{case.task_id}.h"
{preamble}
{_api(case)}{{
  const auto& v=request.values;[[maybe_unused]] const auto& k=request.keys;[[maybe_unused]] const std::size_t w=request.workers;[[maybe_unused]] const i64 p=request.parameter;
  if(!valid_common(v,k,w,p))return std::nullopt;
  [[maybe_unused]] const auto ranges=chunks(v.size(),w);std::vector<i64> out;
  {operation}
  {bug}
  return out;
}}
}}
'''


def _cpp_vector(values: Iterable[int]) -> str:
    return "{" + ",".join(str(value) for value in values) + "}"


def _test_source(case: Case, hidden: bool = False, *, omit_terminal: bool = False, tie_later: bool = False) -> str:
    values, keys, workers, parameter = _sample(case, hidden)
    expected = _oracle(case, values, keys, workers, parameter)
    if expected is None:
        raise AssertionError(f"sample unexpectedly invalid: {case.task_id}")
    if omit_terminal and expected:
        expected = expected[:-1]
    if tie_later and case.index == 27 and values:
        minimum = min(values)
        expected = [minimum, max(index for index, value in enumerate(values) if value == minimum)]
    invalid = ""
    if hidden:
        invalid = f'''{case.request_type} bad{{{{1,2}},{{0}},0,{parameter}}};
  if({case.stem}(bad).has_value())return 3;'''
    return f'''#include "{case.task_id}.h"
#include <vector>
int main(){{using namespace curriculum;
  {case.request_type} request{{{_cpp_vector(values)},{_cpp_vector(keys)},{workers},{parameter}}};
  auto got={case.stem}(request);const std::vector<long long> expected{_cpp_vector(expected)};
  if(!got||*got!=expected)return 1;
  {case.request_type} empty{{{{}},{{}},{workers},{parameter}}};
  if(!{case.stem}(empty).has_value())return 2;
  {invalid}
  return 0;
}}
'''


def _instructions(case: Case, *, control: str | None = None) -> str:
    workers_limit = 16 if control == "constants-policy-only" else 8
    tie = case.boundary
    if control == "opposite-end-selection":
        tie = tie.replace("smaller", "larger").replace("earlier", "later")
    text = f'''# Instructions

Implement `{case.title}` in C++17.

Public API: `{_api(case)}`. The request owns aligned `values` and `keys`, a
`workers` count, and a `parameter`. The vectors must have equal length and at
most 64 records; every integer must be in `[-1000,1000]`; `workers` is in
`[1,{workers_limit}]`; and `parameter` is in `[1,16]`. Invalid input returns
`std::nullopt` without a partial result. Inputs are never mutated.

Required mechanism: {case.mechanism}. {case.contract} {tie}

Implement this direct deterministic mechanism. Do not use a generic runtime
mode switch, `std::reduce`, a parallel framework, completion-order merging,
nondeterministic hash iteration, precomputed answers, threads, clocks, files,
networking, or randomness. Standard containers are allowed only as temporary
support for the explicitly documented mechanism.
'''
    if control == "domain-identifier-renamed":
        text = text.replace("worker", "agent").replace("Worker", "Agent").replace("shard", "lane").replace("Shard", "Lane")
    return text


def _semantic_profile(case: Case) -> dict[str, str]:
    return {
        "public_api": f"request-carrier/{case.group}/{case.mechanism}/{case.contract}",
        "owned_state_algorithm": f"direct-specialization/{case.mechanism}/{case.contract}",
        "mutation_selection_rules": f"deterministic-partial-order/{case.mechanism}/{case.boundary}",
        "invalid_boundary_behavior": f"shared-carrier-plus/{case.boundary}/{case.mechanism}",
        "reference_control_flow": f"direct-control-flow/{case.mechanism}/{case.contract}",
        "deterministic_oracle": f"literal-visible-hidden/{case.contract}/{case.boundary}",
        "topic_negative_fixture": f"compiled-terminal-partial-omission/{case.negative_reason}/{case.mechanism}",
    }


def _contract_markdown(case: Case) -> str:
    return f'''## Identity

Task ID `{case.task_id}`; task-spec revision 1; family `{FAMILY_ID}`; lineage
`new-root`; source inventory `expansion-v1-prebuild`; clean-room repository
authorship; project usage terms; owner `{GENERATOR_PATH}`; benchmark screen is
bound by creator preflight.

## Objective

Implement `{case.mechanism}` and return the exact canonical encoding described
by the public contract. `primary_core_objective` requires source inspection and
execution of the named negative fixture.

## Public API

C++17 namespace `curriculum`; editable order `{case.task_id}.h`,
`{case.task_id}.cpp`; API `{_api(case)}`; caller retains input ownership.

## Behavior table

{case.contract} Invalid common carrier fields or the root-specific malformed
state return `std::nullopt`; valid empty input follows the visible instructions.
{case.boundary} Checked arithmetic never wraps.

## Implementation invariant

The owned mechanism is `{case.mechanism}`. The reference contains only this
direct operation. Forbidden substitutes are a generic policy switch,
completion-order merge, delegated parallel reduction, precomputed cases,
nondeterministic iteration, and terminal-partial loss.

## Starter and reference

The task-named header is complete; the source is a coherent nullopt stub.
`.meta/example.h` and `.meta/example.cpp` independently replace both editable
files. The reference imports no benchmark, sibling, or hidden-test material.

## Tests

Visible and private literal oracles cover separate requests, invalid carrier
state, ordering, and `{case.boundary}`. The compiling false substitute models
`{case.negative_reason}` and must fail the production tests.

## Files and metadata

Solution order is header then source; visible test is `task_visible_test.cpp`;
private test/reference/negative/provenance assets remain under `.meta`; CMake
and all receipts remain private. Support is standard-library-only.

## Build/oracle

Strict C++17 `Unix Makefiles`; pinned network-disabled image `{SANITY_IMAGE}`;
two positive normal and two equal fresh ASan/UBSan tests. The receipt binds all
content, owner, environment, command, and result digests.

## Family/contamination

Compare all 1,770 pairs over the seven family dimensions and all current roots
in both existing trees, other expansion families, and 26 official holdouts.
Normalizer: `dpr-v1-domain-literal-endpoint-neutral`.

## Optional dataset handoff

`not_requested`.

## Acceptance

Owner regeneration, focused structural tests, prompt/role/reference checks,
all-pairs and clone-control screens, cross-tree/benchmark screens, normal plus
sanitizer reference passes, and execution/rejection of this compiling false
substitute must pass before a fresh independent audit may retain the root.
'''


def _render_files(case: Case, *, control: str | None = None) -> dict[str, str]:
    tie_later = control == "opposite-end-selection"
    max_workers = 16 if control == "constants-policy-only" else 8
    reference = _reference(case, tie_later=tie_later, max_workers=max_workers)
    visible = _test_source(case, tie_later=tie_later)
    hidden = _test_source(case, True, tie_later=tie_later)
    config = {
        "authors": ["w8-biayn"],
        "blurb": f"{case.mechanism} with deterministic partial ordering.",
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance: dict[str, object] = {
        "benchmark_separation": "The 26 official Aider Polyglot C++ roots are permanent holdouts; no holdout assets were used.",
        "count_plan_cell": "state/concurrency / deterministic parallel partition, reduction, and merge / 60",
        "curriculum_document": str(CURRICULUM),
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "mechanism": case.mechanism,
        "origin": "repository-authored clean-room expansion",
        "semantic_profile": _semantic_profile(case),
        "status": "local task artifact; not admitted SFT data",
        "task_id": case.task_id,
        "version": 1,
    }
    if control is not None:
        provenance["adversarial_clone_control"] = control
        provenance["clone_of"] = case.task_id
    return {
        ".docs/introduction.md": f"# {case.title}\n\nA clean-room deterministic partial-state task for {case.mechanism}.\n",
        ".docs/instructions.md": _instructions(case, control=control),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": '[visible]\ndescription="ordinary deterministic partial-state example"\n[hidden]\ndescription="boundary, ordering, empty, and invalid carrier checks"\n[negative]\ndescription="compiling terminal-partial omission must be rejected"\n',
        ".meta/example.h": _header(case),
        ".meta/example.cpp": reference,
        ".meta/task_hidden_test.cpp": hidden,
        ".meta/negative_false_substitute.cpp": _reference(case, omit_terminal=True),
        f"{case.task_id}.h": _header(case),
        f"{case.task_id}.cpp": f'#include "{case.task_id}.h"\nnamespace curriculum {{ {_api(case)}{{return std::nullopt;}} }}\n',
        "task_visible_test.cpp": visible,
        "CMakeLists.txt": CMAKE,
    }


def _write_root(root: Path, case: Case, force: bool, *, control: str | None = None) -> list[str]:
    changed: list[str] = []
    files = _render_files(case, control=control)
    for relative, content in files.items():
        path = root / relative
        before = path.read_text(encoding="utf-8") if path.is_file() else None
        _write(path, content, force)
        if before != content:
            changed.append(relative)
    return changed


def _write_controls(out: Path, force: bool) -> None:
    case = CASES[27]
    records: dict[str, object] = {}
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        root = out / ".state/adversarial-clone-controls" / name
        changed = _write_root(root, case, force, control=name)
        if not changed:
            changed = ["stable-regeneration-no-byte-drift"]
        records[name] = {
            "base_task_id": case.task_id,
            "changed_files": changed,
            "tree_hash": _tree_hash(root, include_state=True),
        }
    _write(
        out / ".state/adversarial-clone-controls/manifest.json",
        json.dumps(
            {
                "schema_version": "dpr-clone-controls-v1",
                "base_task_id": case.task_id,
                "controls": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )


def _freeze_inventory(out: Path, force: bool) -> dict[str, object]:
    relative_family = out.resolve().relative_to(EXPANSION_ROOT.resolve()).as_posix()
    inventories = {
        "legacy": _inventory(LEGACY_ROOT),
        "reverify": _inventory(REVERIFY_ROOT),
        "expansion_before": [
            record
            for record in _inventory(EXPANSION_ROOT)
            if not record["relative_root"].startswith(relative_family + "/")
        ],
    }
    payload: dict[str, object] = {
        "schema_version": "dpr-source-inventory-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "roots": {},
    }
    for name, records in inventories.items():
        serialized = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
        payload["roots"][name] = {
            "count": len(records),
            "sha256": _sha(serialized),
            "records": records,
        }
    _write(out / ".state/source-inventory.json", json.dumps(payload, indent=2, sort_keys=True) + "\n", force)
    return payload


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _validate_output(out)
    if out.is_dir():
        for provenance in sorted(out.glob("*/.meta/provenance.json")):
            family = json.loads(provenance.read_text(encoding="utf-8")).get("family_id")
            if family != FAMILY_ID:
                _fail(
                    "foreign_root",
                    f"{provenance.parent.parent}: tree is owned by {family}; "
                    "this superseded v1 generator must not write into it "
                    "(use moonlight_dpr_v2)",
                )
    source_inventory = _freeze_inventory(out, force)
    existing = {
        record["task_id"]
        for name in ("legacy", "reverify", "expansion_before")
        for record in source_inventory["roots"][name]["records"]
    }
    collisions = sorted(existing & {case.task_id for case in CASES})
    if collisions:
        _fail("duplicate_task", ",".join(collisions))
    if len(CASES) != 60 or len({case.task_id for case in CASES}) != 60:
        _fail("duplicate_task", f"expected exactly 60 unique cases, got {len(CASES)}")
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        if root.exists() and any(path.is_symlink() for path in root.rglob("*")):
            _fail("unsafe_path", f"symlink in owned root: {root}")
        _write_root(root, case, force)
        _write(out / ".state/contracts" / f"{case.task_id}.md", _contract_markdown(case), force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " LIT ", text)
    text = re.sub(r"\b(?:true|false)\b|-?\d+(?:[uUlL]+)?", " LIT ", text)
    text = re.sub(
        r"\b(worker|workers|shard|shards|agent|agents|lane|lanes|job|jobs|record|records)\b",
        " DOMAIN ",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(first|last|earlier|later|smaller|larger|minimum|maximum|front|back)\b",
        " ENDPOINT ",
        text,
        flags=re.I,
    )
    return tuple(
        re.findall(
            r"[A-Za-z_][A-Za-z_0-9]*|<=|>=|==|!=|&&|\|\||[-+*/%<>{}()[\];,?:=.]",
            text,
        )
    )


def _dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    provenance = json.loads((root / ".meta/provenance.json").read_text())
    profile = provenance["semantic_profile"]
    reference = (root / ".meta/example.cpp").read_text()
    instructions = (root / ".docs/instructions.md").read_text()
    header = next(root.glob("*.h")).read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    return {
        "public_api": _normalized_tokens(profile["public_api"] + header + instructions),
        "owned_state_algorithm": _normalized_tokens(profile["owned_state_algorithm"] + reference),
        "mutation_selection_rules": _normalized_tokens(profile["mutation_selection_rules"] + instructions + reference),
        "invalid_boundary_behavior": _normalized_tokens(profile["invalid_boundary_behavior"] + instructions + hidden),
        "reference_control_flow": _normalized_tokens(profile["reference_control_flow"] + reference),
        "deterministic_oracle": _normalized_tokens(profile["deterministic_oracle"] + visible + hidden),
        "topic_negative_fixture": _normalized_tokens(profile["topic_negative_fixture"] + negative),
    }


def _pair_decisions(left: Path, right: Path) -> dict[str, bool]:
    left_material = _dimension_material(left)
    right_material = _dimension_material(right)
    return {
        dimension: left_material[dimension] != right_material[dimension]
        for dimension in HARD_DIMENSIONS
    }


def _semantic_screen(out: Path) -> dict[str, object]:
    roots = sorted((out / case.task_id for case in CASES), key=lambda path: path.name)
    materials = {root: _dimension_material(root) for root in roots}
    pairs: list[dict[str, object]] = []
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions = {
                dimension: materials[left][dimension] != materials[right][dimension]
                for dimension in HARD_DIMENSIONS
            }
            if not all(decisions.values()):
                _fail("duplicate_family", f"{left.name} vs {right.name}: {decisions}")
            pairs.append({"left": left.name, "right": right.name, "decisions": decisions})
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"{len(pairs)} != {expected}")
    base = out / CASES[27].task_id
    controls: dict[str, object] = {}
    manifest = json.loads((out / ".state/adversarial-clone-controls/manifest.json").read_text())
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        root = out / ".state/adversarial-clone-controls" / name
        decisions = _pair_decisions(base, root)
        changed_files = manifest["controls"][name]["changed_files"]
        if not changed_files:
            _fail("duplicate_family", f"clone control made no change: {name}")
        if any(decisions.values()):
            _fail("duplicate_family", f"clone control escaped: {name}: {decisions}")
        controls[name] = {
            "changed_files": changed_files,
            "decisions": decisions,
            "production_rejected": True,
        }
    return {
        "status": "pass",
        "root_count": len(CASES),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "dimensions": list(HARD_DIMENSIONS),
        "pairs": pairs,
        "controls": controls,
        "normalizer": "dpr-v1-domain-literal-endpoint-neutral",
    }


def _ngrams(tokens: tuple[str, ...], width: int = 13) -> set[tuple[str, ...]]:
    return {
        tokens[index : index + width]
        for index in range(max(0, len(tokens) - width + 1))
    }


def _root_text(root: Path) -> str:
    included = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".state" in path.parts or path.stat().st_size >= 1_000_000:
            continue
        if path.name in {"CMakeLists.txt", "config.json", "provenance.json"}:
            continue
        included.append(path.read_text(errors="ignore"))
    return " ".join(included)


def _holdout_screen(out: Path) -> dict[str, object]:
    found = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    missing = sorted(OFFICIAL_HOLDOUTS - found)
    if missing:
        _fail("benchmark_content_overlap", f"bound holdouts unavailable: {missing}")
    candidate_grams = {
        case.task_id: _ngrams(_normalized_tokens(_root_text(out / case.task_id)))
        for case in CASES
    }
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    for holdout_id in sorted(OFFICIAL_HOLDOUTS):
        grams = _ngrams(_normalized_tokens(_root_text(HOLDOUT_ROOT / holdout_id)))
        for task_id, candidate in candidate_grams.items():
            denominator = min(len(candidate), len(grams))
            score = len(candidate & grams) / denominator if denominator else 0.0
            comparisons += 1
            if score > strongest:
                strongest = score
                strongest_pair = [task_id, holdout_id]
            if score >= 0.78:
                _fail("benchmark_content_overlap", f"{task_id} vs {holdout_id}: {score:.3f}")
    return {
        "status": "pass",
        "holdout_root_count": len(OFFICIAL_HOLDOUTS),
        "comparison_count": comparisons,
        "threshold": 0.78,
        "strongest_pair": strongest_pair,
        "strongest_containment": round(strongest, 6),
    }


def _cross_tree_semantic_screen(out: Path) -> dict[str, object]:
    inventory_path = out / ".state/source-inventory.json"
    if not inventory_path.is_file():
        _fail("source_inventory_missing", str(inventory_path))
    inventory = json.loads(inventory_path.read_text())
    candidates = {
        case.task_id: _ngrams(_normalized_tokens(_root_text(out / case.task_id)))
        for case in CASES
    }
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    comparison_rows: list[str] = []
    trees = {
        ("legacy", LEGACY_ROOT),
        ("reverify", REVERIFY_ROOT),
        ("expansion_before", EXPANSION_ROOT),
    }
    tree_by_name = dict(trees)
    frozen_count = 0
    for tree_name in ("legacy", "reverify", "expansion_before"):
        records = inventory["roots"][tree_name]["records"]
        frozen_count += len(records)
        tree = tree_by_name[tree_name]
        for record in records:
            root = tree / record["relative_root"]
            config = root / ".meta/config.json"
            if not config.is_file():
                _fail("source_inventory_drift", f"missing frozen root: {tree_name}:{record['relative_root']}")
            if _file_hash(config) != record["config_hash"] or _tree_hash(root) != record["tree_hash"]:
                _fail("source_inventory_drift", f"changed frozen root: {tree_name}:{record['relative_root']}")
            other = _ngrams(_normalized_tokens(_root_text(root)))
            for task_id, candidate in candidates.items():
                denominator = min(len(candidate), len(other))
                score = len(candidate & other) / denominator if denominator else 0.0
                comparisons += 1
                external = f"{tree_name}:{record['relative_root']}"
                comparison_rows.append(
                    json.dumps(
                        {
                            "candidate": task_id,
                            "external": external,
                            "external_tree_hash": record["tree_hash"],
                            "normalized_containment": round(score, 6),
                            "relation": "distinct" if score < 0.84 else "overlap",
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                if score > strongest:
                    strongest = score
                    strongest_pair = [task_id, external]
                if score >= 0.84:
                    _fail("duplicate_family", f"cross-tree overlap {score:.3f}: {strongest_pair}")
    expected = len(CASES) * frozen_count
    if comparisons != expected:
        _fail("source_inventory_drift", f"comparison count {comparisons} != {expected}")
    ledger = out / ".state/cross-tree-comparisons.jsonl"
    _write(ledger, "\n".join(comparison_rows) + "\n", True)
    return {
        "status": "pass",
        "comparison_count": comparisons,
        "expected_comparison_count": expected,
        "frozen_external_root_count": frozen_count,
        "comparison_ledger": ".state/cross-tree-comparisons.jsonl",
        "comparison_ledger_hash": _file_hash(ledger),
        "threshold": 0.84,
        "strongest_pair": strongest_pair,
        "strongest_score": round(strongest, 6),
    }


def verify_core(out: Path = DEFAULT_OUT) -> None:
    if len(CASES) != 60 or len({case.task_id for case in CASES}) != 60:
        _fail("duplicate_task", f"expected exactly 60 unique roots, got {len(CASES)}")
    group_counts = {group: sum(case.group == group for case in CASES) for group in GROUPS}
    if set(group_counts.values()) != {12}:
        _fail("generator_output_drift", f"group counts: {group_counts}")
    rows: list[dict[str, object]] = []
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        expected_solution = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        if config["files"]["solution"] != expected_solution:
            _fail("target_reference_mismatch", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private_markers = (
            ".meta/",
            "CMakeLists",
            "task_visible_test",
            "provenance",
            "negative_false_substitute",
        )
        if any(marker in prompt for marker in private_markers):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if not answer.startswith(f"{case.task_id}.h\n```") or f"{case.task_id}.cpp\n```" not in answer:
            _fail("target_reference_mismatch", case.task_id)
        prompt_hash = _sha(prompt.encode())
        reference_hash = _file_hash(root / ".meta/example.cpp")
        if prompt_hash in prompt_hashes or reference_hash in reference_hashes:
            _fail("duplicate_family", f"duplicate prompt/reference hash: {case.task_id}")
        prompt_hashes.add(prompt_hash)
        reference_hashes.add(reference_hash)
        rows.append(
            {
                "task_id": case.task_id,
                "group": case.group,
                "mechanism": case.mechanism,
                "tree_hash": _tree_hash(root),
                "prompt_hash": prompt_hash,
                "starter_hash": _file_hash(root / f"{case.task_id}.cpp"),
                "reference_hash": reference_hash,
                "visible_test_hash": _file_hash(root / "task_visible_test.cpp"),
                "hidden_test_hash": _file_hash(root / ".meta/task_hidden_test.cpp"),
                "negative_hash": _file_hash(root / ".meta/negative_false_substitute.cpp"),
                "metadata_hash": _file_hash(root / ".meta/config.json"),
                "provenance_hash": _file_hash(root / ".meta/provenance.json"),
                "contract_hash": _file_hash(out / ".state/contracts" / f"{case.task_id}.md"),
                "primary_core_objective": "achieved_pending_executed_negative",
            }
        )
    diversity = _semantic_screen(out)
    holdout = _holdout_screen(out)
    cross_tree = _cross_tree_semantic_screen(out)
    manifest = {
        "schema_version": "dpr-materialization-v1",
        "family_id": FAMILY_ID,
        "task_count": len(CASES),
        "group_counts": group_counts,
        "owner_hash": _file_hash(GENERATOR_PATH),
        "curriculum_hash": _file_hash(CURRICULUM),
        "family_spec_hash": _file_hash(FAMILY_SPEC),
        "focused_test_hash": _file_hash(TEST_PATH),
        "family_tree_hash": _tree_hash(out),
        "tasks": rows,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "diversity": diversity,
            "benchmark_holdout": holdout,
            "cross_tree": cross_tree,
        },
        "strongest_local_status": "pending_execution",
        "dataset_handoff": "not_requested",
    }
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )


def _archive(out: Path, target: Path) -> str:
    expected = target.parent / "expected-tree-hashes.tsv"
    roots = [("tasks", out / case.task_id) for case in CASES]
    roots.extend(
        (
            "controls",
            out / ".state/adversarial-clone-controls" / name,
        )
        for name in (
            "domain-identifier-renamed",
            "constants-policy-only",
            "opposite-end-selection",
        )
    )
    expected.write_text(
        "".join(f"{kind}\t{root.name}\t{_tree_hash(root, include_state=True)}\n" for kind, root in roots),
        encoding="utf-8",
    )
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        info = archive.gettarinfo(str(expected), arcname="expected-tree-hashes.tsv")
        info.uid = info.gid = info.mtime = 0
        info.uname = info.gname = ""
        info.mode = 0o644
        with expected.open("rb") as handle:
            archive.addfile(info, handle)
        for kind, root in roots:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(
                    str(path),
                    arcname=f"{kind}/{root.name}/{path.relative_to(root).as_posix()}",
                )
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
    return _file_hash(target)


def verify_docker(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> None:
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text())
    if manifest["family_tree_hash"] != _tree_hash(out) or manifest["owner_hash"] != _file_hash(GENERATOR_PATH):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    with tempfile.TemporaryDirectory(prefix="dpr-expansion-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        result = temp / "result"
        result.mkdir()
        archive_hash = _archive(out, archive)
        script = r'''set -Eeuo pipefail
mkdir -p /work /result
trap 'rc=$?; echo "docker verifier failed rc=$rc" >&2; for log in /tmp/config.log /tmp/build.log /tmp/discovery.log /tmp/test.log /tmp/negative-visible.log /tmp/negative-hidden.log; do if [ -f "$log" ]; then echo "LOG $log" >&2; tail -80 "$log" >&2; fi; done; exit $rc' ERR
tar -xf /input/family.tar -C /work
sha256sum /input/family.tar | awk '{print "archive\t"$1}' > /result/results.tsv
command -v c++ > /result/compiler.path
c++ --version | head -1 > /result/compiler.version
sha256sum "$(command -v c++)" | awk '{print $1}' > /result/compiler.sha256
cmake --version | head -1 > /result/cmake.version
python3 - <<'PY'
from pathlib import Path
import hashlib
for line in Path('/work/expected-tree-hashes.tsv').read_text().splitlines():
    kind, name, expected = line.split('\t')
    root = Path('/work') / kind / name
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob('*') if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    got = 'sha256:' + digest.hexdigest()
    if got != expected:
        raise SystemExit(f'grader_mount_hash_mismatch: {kind}/{name}: {got} != {expected}')
PY
run_one(){
  kind="$1";id="$2";mode="$3";with_negative="$4"
  root="/work/${kind}/${id}";build="/tmp/${kind}-${id}-${mode}"
  flags=()
  if [ "$mode" = sanitizer ];then
    flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined")
  fi
  if [ "$with_negative" = yes ];then
    flags+=("-DNEGATIVE_SOURCE=$root/.meta/negative_false_substitute.cpp")
  fi
  cmake -S "$root" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$root/.meta/example.cpp" "${flags[@]}" >/tmp/config.log 2>&1
  cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1
  ctest --test-dir "$build" -N >/tmp/discovery.log 2>&1
  count=$(sed -n 's/^Total Tests: //p' /tmp/discovery.log)
  names=$(sed -n 's/.*Test #[0-9][0-9]*: //p' /tmp/discovery.log | paste -sd, -)
  test "$count" = 2
  ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1
  negative="not_run"
  visible_rc=-1
  hidden_rc=-1
  : >/tmp/negative-visible.log
  : >/tmp/negative-hidden.log
  if [ "$with_negative" = yes ];then
    if ASAN_OPTIONS=detect_leaks=0 "$build/negative_visible" >/tmp/negative-visible.log 2>&1;then
      visible_rc=0
    else
      visible_rc=$?
    fi
    if ASAN_OPTIONS=detect_leaks=0 "$build/negative_hidden" >/tmp/negative-hidden.log 2>&1;then
      hidden_rc=0
    else
      hidden_rc=$?
    fi
    if [ "$visible_rc" -eq 0 ] || [ "$hidden_rc" -eq 0 ];then
      echo "negative_fixture_not_rejected: $id $mode visible=$visible_rc hidden=$hidden_rc" >&2
      exit 71
    fi
    negative="rejected"
  fi
  discovery_hash=$(sha256sum /tmp/discovery.log | awk '{print $1}')
  test_hash=$(sha256sum /tmp/test.log | awk '{print $1}')
  negative_visible_hash=$(sha256sum /tmp/negative-visible.log | awk '{print $1}')
  negative_hidden_hash=$(sha256sum /tmp/negative-hidden.log | awk '{print $1}')
  printf '%s\t%s\t%s\t%s\t%s\t0\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$kind" "$id" "$mode" "$count" "$negative" "$visible_rc" "$hidden_rc" "$names" "$discovery_hash" "$test_hash" "$negative_visible_hash" "$negative_hidden_hash" >>/result/results.tsv
}
for root in /work/tasks/*;do
  id=${root##*/}
  run_one tasks "$id" normal yes
  run_one tasks "$id" sanitizer yes
done
for root in /work/controls/*;do
  id=${root##*/}
  run_one controls "$id" normal no
  run_one controls "$id" sanitizer no
done
'''
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--mount",
                f"type=bind,src={archive},dst=/input/family.tar,readonly",
                "--mount",
                f"type=bind,src={result},dst=/result",
                image,
                "bash",
                "-lc",
                script,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            diagnostic = (completed.stdout + completed.stderr)[-16000:]
            _fail("docker_sanity_failed", diagnostic)
        rows = [line.split("\t") for line in (result / "results.tsv").read_text().splitlines()]
        mounted_archive = "sha256:" + rows[0][1]
        if mounted_archive != archive_hash:
            _fail("grader_mount_hash_mismatch", f"{mounted_archive} != {archive_hash}")
        result_rows = rows[1:]
        task_rows = [row for row in result_rows if row[0] == "tasks"]
        control_rows = [row for row in result_rows if row[0] == "controls"]
        normal = [row for row in task_rows if row[2] == "normal"]
        sanitizer = [row for row in task_rows if row[2] == "sanitizer"]
        if len(normal) != 60 or len(sanitizer) != 60 or len(control_rows) != 6:
            _fail(
                "sanitizer_test_count_mismatch",
                f"normal={len(normal)} sanitizer={len(sanitizer)} controls={len(control_rows)}",
            )
        if any(row[3] != "2" for row in result_rows):
            _fail("sanitizer_test_count_mismatch", "a discovered count was not two")
        if any(row[4] != "rejected" for row in task_rows):
            _fail("negative_fixture_not_rejected", "one or more task negatives were not rejected")
        if any(row[5] != "0" for row in result_rows):
            _fail("docker_sanity_failed", "one or more positive CTest runs was not successful")
        if any(row[8] != "visible,hidden" for row in result_rows):
            _fail("sanitizer_test_count_mismatch", "discovered test names drifted")
        execution_records = [
            {
                "kind": row[0],
                "task_id": row[1],
                "mode": row[2],
                "discovered_test_count": int(row[3]),
                "negative_status": row[4],
                "positive_exit": int(row[5]),
                "negative_visible_exit": int(row[6]),
                "negative_hidden_exit": int(row[7]),
                "discovered_tests": row[8].split(","),
                "discovery_log_hash": "sha256:" + row[9],
                "test_log_hash": "sha256:" + row[10],
                "negative_visible_log_hash": "sha256:" + row[11],
                "negative_hidden_log_hash": "sha256:" + row[12],
            }
            for row in result_rows
        ]
        receipt = {
            "schema_version": "dpr-docker-sanity-v1",
            "status": "pass",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "archive_hash": archive_hash,
            "mounted_archive_hash": mounted_archive,
            "family_tree_hash": _tree_hash(out),
            "owner_hash": _file_hash(GENERATOR_PATH),
            "curriculum_hash": _file_hash(CURRICULUM),
            "family_spec_hash": _file_hash(FAMILY_SPEC),
            "focused_test_hash": _file_hash(TEST_PATH),
            "compiler": {
                "path": (result / "compiler.path").read_text().strip(),
                "version": (result / "compiler.version").read_text().strip(),
                "sha256": "sha256:" + (result / "compiler.sha256").read_text().strip(),
            },
            "cmake": (result / "cmake.version").read_text().strip(),
            "normal_reference_count": len(normal),
            "sanitizer_reference_count": len(sanitizer),
            "normal_test_count_per_root": 2,
            "sanitizer_test_count_per_root": 2,
            "normal_negative_rejection_count": len(normal),
            "sanitizer_negative_rejection_count": len(sanitizer),
            "control_mode_count": len(control_rows),
            "execution_records": execution_records,
            "commands": [
                "cmake -G Unix Makefiles with reference and negative sources",
                "cmake --build --parallel 2",
                "ctest -N and ctest --output-on-failure",
                "direct negative_visible and negative_hidden execution",
            ],
        }
        _write(out / ".state/docker-sanity.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest = json.loads(manifest_path.read_text())
    for row in manifest["tasks"]:
        row["primary_core_objective"] = "achieved"
    manifest["docker_sanity"] = {
        "status": "pass",
        "receipt": ".state/docker-sanity.json",
        "normal_test_count_per_root": 2,
        "sanitizer_test_count_per_root": 2,
        "negative_fixture_count_per_mode": 60,
        "control_count": 3,
    }
    manifest["strongest_local_status"] = "creator_preflight_passed_pending_independent_audit"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def _append_cycle(out: Path, status: str) -> None:
    state = out / ".state/cycles"
    state.mkdir(parents=True, exist_ok=True)
    number = len(list(state.glob("cycle-*.json"))) + 1
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    receipt_path = out / ".state/docker-sanity.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
    record = {
        "schema_version": "aider-task-creator-cycle-v1",
        "cycle": number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "family_id": FAMILY_ID,
        "candidate_manifest": ".state/materialization-manifest.json",
        "family_tree_hash": _tree_hash(out),
        "curriculum_hash": _file_hash(CURRICULUM),
        "generator_hash": _file_hash(GENERATOR_PATH),
        "family_spec_hash": _file_hash(FAMILY_SPEC),
        "focused_test_hash": _file_hash(TEST_PATH),
        "grader_policy_hash": _sha((SANITY_IMAGE + CMAKE).encode()),
        "retained_root_ids": [case.task_id for case in CASES],
        "replaced_root_ids": [],
        "rejected_root_ids": [],
        "review_root_ids": [],
        "blocked_root_ids": [],
        "manifest_subject_hash": _sha(json.dumps(manifest, sort_keys=True).encode()),
        "audit_subject_hash": None,
        "audit_report_path": None,
        "finding_ids": [],
        "remedy_records": [],
        "invalidated_evidence": [],
        "docker_receipt": receipt,
    }
    _write(state / f"cycle-{number:02d}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--record-cycle", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core or args.docker_sanity:
        verify_core(args.out)
    if args.docker_sanity:
        verify_docker(args.out)
    if args.record_cycle:
        _append_cycle(
            args.out,
            "creator_preflight" if args.docker_sanity else "generated",
        )
    print(f"Wrote {len(roots)} deterministic parallel reduction roots under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
