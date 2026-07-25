"""Own the expansion-v1 overflow, scoring, and combinatorial arithmetic cell."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/numerical-arithmetic/"
    "overflow-scoring-combinatorial"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-numerical/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_OVERFLOW_SCORING_COMBINATORIAL_CURRICULUM.md"
)
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-numerical/overflow-scoring-combinatorial.md"
)
FAMILY_ID = "aider-expansion-v1-overflow-scoring-combinatorial-v1"
OWNER = (
    "src/w8_biayn/integrations/"
    "moonlight_overflow_scoring_combinatorial_aider_tasks.py"
)
FOCUSED_TEST = "tests/test_moonlight_overflow_scoring_combinatorial_aider_tasks.py"
CYCLE1_AUDIT_REPORT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/numerical-arithmetic/"
    "overflow-scoring-combinatorial/.state/audits/cycle-001-sha256-eead3421.json"
)
SELECTED_PROMPTS = (
    "docs/aider-tasks-spec/prompts/generate-family-spec.md",
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
)
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square",
        "diamond", "dnd-character", "gigasecond", "grade-school",
        "kindergarten-garden", "knapsack", "linked-list", "meetup",
        "parallel-letter-frequency", "perfect-numbers", "phone-number",
        "queen-attack", "robot-name", "space-age", "spiral-matrix",
        "sublist", "yacht", "zebra-puzzle",
    }
)


class VerificationError(RuntimeError):
    """A creator or verification gate failed closed."""


def _fail(code: str, detail: str = "") -> None:
    raise VerificationError(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class TaskCase:
    task_id: str
    title: str
    cluster: str
    mechanism: str
    fields: str
    visible_input: str
    visible_expected: int
    hidden_input: str
    hidden_expected: int
    invalid_input: str
    boundary: str
    forbidden: str
    kind: str

    @property
    def class_name(self) -> str:
        return "".join(part.title() for part in self.task_id.split("-"))

    @property
    def input_name(self) -> str:
        return f"{self.class_name}Input"


def _c(
    task_id: str,
    title: str,
    cluster: str,
    mechanism: str,
    fields: str,
    visible_input: str,
    visible_expected: int,
    hidden_input: str,
    hidden_expected: int,
    invalid_input: str,
    boundary: str,
    forbidden: str,
    kind: str,
) -> TaskCase:
    return TaskCase(
        task_id, title, cluster, mechanism, fields, visible_input,
        visible_expected, hidden_input, hidden_expected, invalid_input,
        boundary, forbidden, kind,
    )


TASKS = (
    _c("checked-batch-total", "Checked batch total", "overflow", "checked left-fold addition", "std::vector<std::uint64_t> terms;", "{{4, 7, 9}}", 20, "{{18446744073709551610ULL, 5}}", 18446744073709551615, "{{18446744073709551615ULL, 1}}", "empty input totals zero; the first overflowing add rejects the whole batch", "saturating or wraparound addition", "sum"),
    _c("checked-batch-product", "Checked batch product", "overflow", "checked multiplicative fold", "std::vector<std::uint64_t> factors;", "{{3, 5, 7}}", 105, "{{4294967295ULL, 4294967297ULL}}", 18446744073709551615, "{{18446744073709551615ULL, 2}}", "empty input has multiplicative identity one; zero short-circuits safely", "logarithmic estimation or wrapped multiplication", "product"),
    _c("capped-credit-ledger", "Capped credit ledger", "overflow", "transactional signed ledger with cap", "std::uint64_t opening; std::vector<std::int64_t> deltas; std::uint64_t cap;", "{40, {12, -7, 20}, 80}", 65, "{10, {-10, 8, 2}, 20}", 10, "{5, {-6}, 20}", "each debit must have funds and each credit must fit the cap; any invalid entry rejects atomically", "clamping failed transactions or applying a partial prefix", "ledger"),
    _c("checked-weighted-load", "Checked weighted load", "overflow", "checked dot product of units and rates", "std::vector<std::pair<std::uint64_t, std::uint64_t>> loads;", "{{{3, 7}, {5, 4}}}", 41, "{{{9, 11}, {2, 13}}}", 125, "{{{18446744073709551615ULL, 2}}}", "each product and the accumulated total must be representable", "summing fields independently or checking only the final add", "weighted"),
    _c("reserve-prefix-floor", "Reserve prefix floor", "overflow", "minimum reserve over a signed prefix scan", "std::uint64_t opening; std::vector<std::int64_t> changes;", "{20, {-3, 8, -11, 2}}", 14, "{9, {-4, -5, 12, -3}}", 0, "{3, {-4}}", "reject a prefix below zero or a positive step that overflows; return the minimum observed reserve", "checking only the final balance", "reserve"),
    _c("checked-arithmetic-series", "Checked arithmetic series", "overflow", "closed-form arithmetic progression with parity cancellation", "std::uint64_t first; std::uint64_t step; std::uint64_t count;", "{3, 4, 5}", 55, "{7, 9, 6}", 177, "{18446744073709551615ULL, 1, 2}", "count zero returns zero; every last-term and triangular multiplication is checked", "iterating with wrapped addition or dividing after overflow", "arithmetic_series"),
    _c("checked-geometric-series", "Checked geometric series", "overflow", "checked repeated-power accumulation", "std::uint64_t first; std::uint64_t ratio; std::uint32_t count;", "{2, 3, 4}", 80, "{5, 2, 6}", 315, "{18446744073709551615ULL, 2, 2}", "count zero returns zero; each next term and accumulation is checked", "using floating-point exponentiation", "geometric_series"),
    _c("interval-charge-fold", "Interval charge fold", "overflow", "ordered non-overlapping duration-rate charging", "struct Span { std::uint64_t begin; std::uint64_t end; std::uint64_t rate; }; std::vector<Span> spans;", "{{{0, 3, 4}, {5, 9, 2}}}", 20, "{{{2, 7, 6}, {7, 10, 9}}}", 57, "{{{5, 4, 1}}}", "spans are half-open, ordered, and non-overlapping; duration times rate and total are checked", "inclusive endpoints or sorting malformed spans", "interval_charge"),
    _c("box-volume-budget", "Box volume budget", "overflow", "checked sum of rectangular volumes", "struct Box { std::uint64_t width; std::uint64_t height; std::uint64_t depth; }; std::vector<Box> boxes; std::uint64_t budget;", "{{{2, 3, 4}, {1, 5, 2}}, 40}", 34, "{{{9, 7, 3}, {2, 2, 2}}, 200}", 197, "{{{9, 7, 3}, {2, 2, 2}}, 190}", "zero dimensions contribute zero; reject arithmetic overflow or a total above budget", "surface-area accumulation or post-hoc clamping", "box_volume"),
    _c("histogram-moment", "Histogram moment", "overflow", "checked first moment of indexed buckets", "std::vector<std::uint64_t> counts; std::uint64_t origin; std::uint64_t stride;", "{{2, 0, 3}, 5, 4}", 49, "{{1, 2, 1, 4}, 3, 7}", 136, "{{1, 1}, 18446744073709551615ULL, 1}", "bucket value is origin plus index times stride; all coordinate and weighted additions are checked", "unweighted histogram cardinality", "histogram"),
    _c("checked-horner-polynomial", "Checked Horner polynomial", "overflow", "Horner evaluation with checked multiply-add", "std::vector<std::uint64_t> coefficients; std::uint64_t x;", "{{2, 3, 4}, 5}", 69, "{{1, 0, 2, 1}, 3}", 34, "{{18446744073709551615ULL, 1}, 2}", "coefficients are highest degree first; empty input is the zero polynomial", "floating-point pow or lowest-degree-first interpretation", "horner"),
    _c("fraction-cross-sum", "Fraction cross sum", "overflow", "pairwise checked rational addition without reduction", "std::uint64_t left_num; std::uint64_t left_den; std::uint64_t right_num; std::uint64_t right_den;", "{1, 3, 2, 5}", 11, "{7, 9, 4, 11}", 113, "{1, 0, 2, 3}", "denominators must be positive; return the unreduced cross numerator and reject either cross-product overflow", "adding numerators without denominator weighting", "fraction"),
    _c("multiplicity-path-cost", "Multiplicity path cost", "overflow", "checked edge-cost expansion", "struct Edge { std::uint64_t cost; std::uint32_t traversals; }; std::vector<Edge> edges;", "{{{7, 3}, {4, 5}}}", 41, "{{{11, 8}, {13, 2}, {1, 9}}}", 123, "{{{18446744073709551615ULL, 2}}}", "zero traversals contribute zero; every edge expansion and total is checked", "counting each edge only once", "path_cost"),
    _c("depth-weighted-tree-budget", "Depth weighted tree budget", "overflow", "validated parent-array depth accumulation", "std::vector<std::int32_t> parent; std::vector<std::uint64_t> cost;", "{{-1, 0, 0, 1}, {5, 3, 7, 2}}", 31, "{{-1, 0, 1, 1, 3}, {2, 4, 6, 8, 10}}", 92, "{{-1, 2}, {1, 1}}", "node zero is the sole root; each parent precedes its child; weight is depth plus one", "flat cost sum or accepting cycles", "tree_budget"),
    _c("capped-rubric-score", "Capped rubric score", "scoring", "per-category clamp then checked aggregation", "struct Category { std::uint64_t earned; std::uint64_t maximum; }; std::vector<Category> categories;", "{{{8, 10}, {7, 6}, {3, 5}}}", 17, "{{{20, 12}, {0, 9}, {5, 5}}}", 17, "{{{1, 0}}}", "maximum zero is invalid; earned points above a maximum are clamped before summing", "clamping only the final total", "rubric"),
    _c("decaying-event-score", "Decaying event score", "scoring", "integer geometric decay by event age", "std::vector<std::uint64_t> newest_first; std::uint64_t numerator; std::uint64_t denominator;", "{{100, 80, 60}, 1, 2}", 155, "{{81, 27, 9, 3}, 2, 3}", 103, "{{1}, 2, 1}", "require numerator not greater than positive denominator; floor after each age-specific scaled contribution", "applying one decay after summation", "decay"),
    _c("streak-bonus-score", "Streak bonus score", "scoring", "run-length triangular bonus accumulation", "std::vector<bool> successes; std::uint64_t base;", "{{true, true, false, true}, 5}", 20, "{{true, true, true, false, true, true}, 2}", 18, "{{true, true}, 18446744073709551615ULL}", "each successful run scores base times 1,2,...; failure resets the run", "constant points per success", "streak"),
    _c("midrank-basis-points", "Midrank basis points", "scoring", "tie-aware empirical midrank", "std::vector<std::int64_t> population; std::int64_t value;", "{{10, 20, 20, 40}, 20}", 5000, "{{-3, -3, 0, 8, 9}, -3}", 2000, "{{}, 1}", "population must be nonempty; return floor(10000*(less + ties/2)/n) using doubled counts", "strict-less percentile without tie half-credit", "midrank"),
    _c("weighted-median-mark", "Weighted median mark", "scoring", "stable weighted median selection", "struct Mark { std::int64_t value; std::uint64_t weight; }; std::vector<Mark> marks;", "{{{30, 1}, {10, 2}, {20, 4}}}", 20, "{{{5, 10}, {7, 1}, {9, 1}}}", 5, "{{{-1, 1}}}", "mark values must be nonnegative and weights positive; sort by value and choose the first cumulative weight reaching half rounded up", "unweighted median or upper median", "weighted_median"),
    _c("trimmed-mean-mark", "Trimmed mean mark", "scoring", "symmetric order-statistic trimming", "std::vector<std::uint64_t> marks; std::size_t trim_each_side;", "{{1, 5, 7, 9, 100}, 1}", 7, "{{2, 4, 8, 10, 12, 100}, 2}", 9, "{{1, 2}, 1}", "after stable numeric sort, remove exactly k from each side and floor the remaining mean", "winsorizing endpoints instead of removing them", "trimmed_mean"),
    _c("round-robin-table-score", "Round robin table score", "scoring", "validated win-draw-loss points fold", "struct Record { std::uint32_t wins; std::uint32_t draws; std::uint32_t losses; }; std::vector<Record> rounds; std::uint64_t win_points; std::uint64_t draw_points;", "{{{2, 1, 0}, {1, 2, 1}}, 3, 1}", 12, "{{{7, 3, 2}}, 5, 2}", 41, "{{{1, 0, 0}}, 1, 2}", "win points must exceed draw points and losses score zero; all products and sums are checked", "counting games rather than weighted results", "round_robin"),
    _c("penalty-budget-score", "Penalty budget score", "scoring", "checked subtractive penalty budget", "std::uint64_t base; struct Penalty { std::uint64_t count; std::uint64_t weight; }; std::vector<Penalty> penalties;", "{100, {{2, 7}, {1, 20}}}", 66, "{250, {{9, 11}, {3, 17}}}", 100, "{10, {{2, 6}}}", "reject if weighted penalties overflow or exceed the base; otherwise return the residual", "saturating at zero", "penalty"),
    _c("progressive-tier-score", "Progressive tier score", "scoring", "progressive piecewise usage pricing", "std::uint64_t usage; std::vector<std::pair<std::uint64_t, std::uint64_t>> width_rate;", "{12, {{5, 2}, {10, 3}}}", 31, "{25, {{10, 1}, {10, 2}, {10, 4}}}", 50, "{31, {{10, 1}, {10, 2}, {10, 4}}}", "tier widths and rates must be positive and total capacity must cover usage", "charging all usage at the last reached rate", "tier"),
    _c("weighted-quorum-margin", "Weighted quorum margin", "scoring", "participation-gated weighted vote margin", "struct Ballot { bool yes; std::uint64_t weight; }; std::vector<Ballot> ballots; std::uint64_t eligible_weight; std::uint64_t quorum_weight;", "{{{true, 7}, {false, 3}, {true, 2}}, 20, 10}", 6, "{{{false, 9}, {true, 15}, {true, 1}}, 30, 20}", 7, "{{{true, 5}}, 4, 1}", "cast weight cannot exceed eligibility and must meet quorum; yes weight must be at least no weight; return the exact unsigned yes-minus-no margin", "one-person-one-vote counting", "quorum"),
    _c("harmonic-placement-score", "Harmonic placement score", "scoring", "floor-scaled reciprocal placement sum", "std::vector<std::uint32_t> placements; std::uint64_t scale;", "{{1, 2, 4}, 120}", 210, "{{3, 5, 8}, 840}", 553, "{{0}, 100}", "placements are one-based; floor scale/place independently before checked accumulation", "divide once after summing placements", "harmonic"),
    _c("trapezoid-curve-score", "Trapezoid curve score", "scoring", "ordered trapezoidal area with evenness check", "struct Point { std::uint64_t x; std::uint64_t y; }; std::vector<Point> points;", "{{{0, 2}, {3, 4}, {5, 6}}}", 19, "{{{2, 5}, {6, 9}, {10, 3}}}", 52, "{{{1, 2}, {1, 3}}}", "x coordinates strictly increase; twice-area must be even or the integer score is undefined", "left-rectangle integration", "trapezoid"),
    _c("smoothed-reliability-score", "Smoothed reliability score", "scoring", "Laplace-smoothed basis-point ratio", "std::uint64_t successes; std::uint64_t trials; std::uint64_t prior_success; std::uint64_t prior_failure;", "{8, 10, 1, 1}", 7500, "{0, 3, 2, 5}", 2000, "{4, 3, 1, 1}", "successes cannot exceed trials and prior mass must be positive; return floor basis points", "raw unsmoothed success rate", "reliability"),
    _c("exact-binomial-coefficient", "Exact binomial coefficient", "combinatorial", "gcd-cancelled binomial product", "std::uint32_t n; std::uint32_t k;", "{10, 3}", 120, "{67, 2}", 2211, "{68, 34}", "k greater than n is invalid; symmetry and gcd cancellation must avoid intermediate overflow", "factorial quotient with overflowing factorials", "binomial"),
    _c("falling-arrangement-count", "Falling arrangement count", "combinatorial", "checked falling factorial", "std::uint32_t available; std::uint32_t chosen;", "{8, 3}", 336, "{12, 5}", 95040, "{30, 30}", "chosen greater than available is invalid; zero chosen returns one", "ordinary power available^chosen", "falling"),
    _c("multiset-arrangement-count", "Multiset arrangement count", "combinatorial", "incremental multinomial interleaving", "std::vector<std::uint32_t> multiplicities;", "{{2, 1, 1}}", 12, "{{3, 2, 2}}", 210, "{{40, 40}}", "zero multiplicities are allowed; interleave each group using exact binomial factors", "factorial of total without duplicate cancellation", "multiset"),
    _c("catalan-structure-count", "Catalan structure count", "combinatorial", "Catalan dynamic convolution", "std::uint32_t nodes;", "{5}", 42, "{10}", 16796, "{37}", "zero nodes has one empty structure; every product and convolution sum is checked", "central binomial coefficient without division", "catalan"),
    _c("derangement-assignment-count", "Derangement assignment count", "combinatorial", "derangement two-term recurrence", "std::uint32_t items;", "{6}", 265, "{10}", 1334961, "{21}", "D0=1 and D1=0; recurrence is (n-1)(D[n-1]+D[n-2]) with checked arithmetic", "factorial minus one", "derangement"),
    _c("stirling-partition-count", "Stirling partition count", "combinatorial", "Stirling second-kind row dynamic program", "std::uint32_t items; std::uint32_t nonempty_groups;", "{7, 3}", 301, "{10, 4}", 34105, "{40, 20}", "zero items into zero groups is one; groups are unlabeled and nonempty", "binomial subset selection", "stirling"),
    _c("bell-partition-count", "Bell partition count", "combinatorial", "Bell triangle construction", "std::uint32_t items;", "{6}", 203, "{10}", 115975, "{26}", "B0=1; construct the Bell triangle with checked adjacent sums", "power-set count 2^n", "bell"),
    _c("rectangular-lattice-route-count", "Rectangular lattice route count", "combinatorial", "one-dimensional lattice-path dynamic program", "std::uint32_t east_steps; std::uint32_t north_steps;", "{4, 3}", 35, "{12, 8}", 125970, "{40, 40}", "only east and north unit steps are allowed; zero-by-zero has one route", "Manhattan distance rather than route count", "lattice"),
    _c("weak-composition-count", "Weak composition count", "combinatorial", "stars-and-bars via checked binomial", "std::uint32_t total; std::uint32_t parts;", "{7, 3}", 36, "{20, 5}", 10626, "{1, 0}", "parts must be positive; zero total has one composition", "positive-composition formula", "weak_composition"),
    _c("bounded-composition-count", "Bounded composition count", "combinatorial", "capacity-bounded sum dynamic program", "std::uint32_t total; std::vector<std::uint32_t> maxima;", "{5, {2, 3, 4}}", 11, "{9, {1, 4, 6, 3}}", 31, "{100, {100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100}}", "each labeled part ranges from zero through its maximum; count exact-total assignments", "unbounded stars-and-bars", "bounded_composition"),
    _c("multinomial-category-count", "Multinomial category count", "combinatorial", "sequential exact category choices", "std::uint32_t total; std::vector<std::uint32_t> category_sizes;", "{7, {2, 3, 2}}", 210, "{12, {4, 1, 3, 4}}", 138600, "{5, {2, 2}}", "category sizes must sum exactly to total; multiply sequential exact binomials", "product of independent powers", "multinomial"),
    _c("onto-mapping-count", "Onto mapping count", "combinatorial", "inclusion-exclusion count of surjections", "std::uint32_t labeled_items; std::uint32_t labeled_bins;", "{5, 3}", 150, "{8, 4}", 40824, "{3, 5}", "bins greater than positive items is invalid; alternating inclusion-exclusion uses exact integer terms", "all mappings bins^items", "onto"),
    _c("ballot-prefix-count", "Ballot prefix count", "combinatorial", "strict ballot difference formula", "std::uint32_t leader_votes; std::uint32_t trailer_votes;", "{7, 4}", 90, "{12, 5}", 2548, "{5, 5}", "leader votes must strictly exceed trailer votes; every nonempty prefix must keep the leader ahead", "unrestricted binomial interleavings", "ballot"),
)

if len(TASKS) != 40 or len({case.task_id for case in TASKS}) != 40:
    raise AssertionError("the binding numerical plan cell requires 40 unique roots")
if {case.cluster for case in TASKS} != {"overflow", "scoring", "combinatorial"}:
    raise AssertionError("the family must cover all three requested clusters")


EDGE_CASES: dict[str, tuple[str, int]] = {
    "sum": ("{{}}", 0),
    "product": ("{{18446744073709551615ULL, 2, 0}}", 0),
    "ledger": ("{17, {}, 17}", 17),
    "weighted": ("{{}}", 0),
    "reserve": ("{9, {}}", 9),
    "arithmetic_series": ("{18446744073709551615ULL, 0, 1}", 18446744073709551615),
    "geometric_series": ("{99, 7, 0}", 0),
    "interval_charge": ("{{}}", 0),
    "box_volume": ("{{}, 0}", 0),
    "histogram": ("{{}, 18446744073709551615ULL, 18446744073709551615ULL}", 0),
    "horner": ("{{}, 18446744073709551615ULL}", 0),
    "fraction": ("{0, 7, 0, 9}", 0),
    "path_cost": ("{{}}", 0),
    "tree_budget": ("{{-1}, {18446744073709551615ULL}}", 18446744073709551615),
    "rubric": ("{{}}", 0),
    "decay": ("{{}, 1, 1}", 0),
    "streak": ("{{}, 18446744073709551615ULL}", 0),
    "midrank": ("{{4, 4, 4, 4}, 4}", 5000),
    "weighted_median": ("{{{4, 2}, {4, 3}}}", 4),
    "trimmed_mean": ("{{17}, 0}", 17),
    "round_robin": ("{{}, 3, 1}", 0),
    "penalty": ("{99, {}}", 99),
    "tier": ("{0, {{1, 7}}}", 0),
    "quorum": ("{{}, 0, 0}", 0),
    "harmonic": ("{{}, 999}", 0),
    "trapezoid": ("{{{0, 0}, {2, 0}}}", 0),
    "reliability": ("{0, 0, 1, 1}", 5000),
    "binomial": ("{0, 0}", 1),
    "falling": ("{100, 0}", 1),
    "multiset": ("{{}}", 1),
    "catalan": ("{0}", 1),
    "derangement": ("{0}", 1),
    "stirling": ("{0, 0}", 1),
    "bell": ("{0}", 1),
    "lattice": ("{0, 0}", 1),
    "weak_composition": ("{0, 3}", 1),
    "bounded_composition": ("{0, {}}", 1),
    "multinomial": ("{0, {}}", 1),
    "onto": ("{0, 0}", 1),
    "ballot": ("{1, 0}", 1),
}

if set(EDGE_CASES) != {case.kind for case in TASKS}:
    raise AssertionError("every arithmetic mechanism needs an explicit identity/boundary oracle")


VECTOR_FIELDS = {
    "sum": "terms", "product": "factors", "ledger": "deltas",
    "weighted": "loads", "reserve": "changes", "interval_charge": "spans",
    "box_volume": "boxes", "histogram": "counts", "horner": "coefficients",
    "path_cost": "edges", "tree_budget": "parent", "rubric": "categories",
    "decay": "newest_first", "streak": "successes", "midrank": "population",
    "weighted_median": "marks", "trimmed_mean": "marks", "round_robin": "rounds",
    "penalty": "penalties", "tier": "width_rate", "quorum": "ballots",
    "harmonic": "placements", "trapezoid": "points", "multiset": "multiplicities",
    "bounded_composition": "maxima", "multinomial": "category_sizes",
}

DP_GUARDS = {
    "catalan": "input.nodes>4096",
    "derangement": "input.items>1000000",
    "stirling": "(U(input.items)+1)>1000000/(U(input.nonempty_groups)+1)",
    "bell": "input.items>1024",
    "lattice": "(U(input.east_steps)+1)>1000000/(U(input.north_steps)+1)",
    "bounded_composition": "(U(input.total)+1)>1000000/(U(input.maxima.size())+1)",
    "geometric_series": "input.count>1000000",
}

ADDITIONAL_INVALID_CASES = {
    "decay": ["{{1}, 1, 0}"],
    "interval_charge": ["{{{0, 5, 1}, {4, 6, 1}}}"],
    "tree_budget": ["{{-1, -1}, {1, 1}}"],
    "weighted_median": ["{{{1, 0}}}"],
    "trimmed_mean": ["{{1, 2, 3}, 9223372036854775808ULL}"],
    "tier": ["{1, {{1, 1}, {0, 1}}}"],
    "quorum": [
        "{{{false, 7}, {true, 2}}, 10, 5}",
        "{{{true, 2}}, 10, 5}",
        "{{}, 5, 6}",
    ],
    "trapezoid": ["{{{0, 0}, {1, 1}}}"],
    "reliability": ["{4, 8, 0, 0}"],
    "binomial": ["{3, 4}"],
    "falling": ["{3, 4}"],
    "bounded_composition": ["{500000, {500000}}"],
    "onto": ["{3, 0}"],
}

ADDITIONAL_VALID_CASES = {
    "arithmetic_series": [("{99, 123, 0}", 0)],
    "box_volume": [
        ("{{{18446744073709551615ULL, 18446744073709551615ULL, 0}}, 0}", 0),
    ],
    "decay": [
        ("{{0, 0}, 18446744073709551615ULL, 18446744073709551615ULL}", 0),
    ],
    "tier": [("{0, {}}", 0)],
    "multiset": [("{{2, 0, 1}}", 3)],
    "derangement": [("{1}", 0)],
    "stirling": [("{3, 4}", 0)],
    "bounded_composition": [("{499999, {499999}}", 1)],
}


def _resource_guard(case: TaskCase) -> str:
    guards: list[str] = []
    field = VECTOR_FIELDS.get(case.kind)
    if field:
        guards.append(f"input.{field}.size()>4096")
    if case.kind == "tree_budget":
        guards.append("input.cost.size()>4096")
    if case.kind in DP_GUARDS:
        guards.append(DP_GUARDS[case.kind])
    if not guards:
        return ""
    return "if(" + "||".join(f"({guard})" for guard in guards) + ")return std::nullopt;"


def _resource_test(case: TaskCase) -> str:
    field = VECTOR_FIELDS.get(case.kind)
    if field:
        return f"{case.input_name} oversized{{}}; oversized.{field}.resize(4097);"
    assignments = {
        "catalan": "oversized.nodes=4097;",
        "derangement": "oversized.items=1000001;",
        "stirling": "oversized.items=1000; oversized.nonempty_groups=1000;",
        "bell": "oversized.items=1025;",
        "lattice": "oversized.east_steps=1000; oversized.north_steps=1000;",
        "geometric_series": "oversized.count=1000001;",
    }
    statement = assignments.get(case.kind)
    if statement:
        return f"{case.input_name} oversized{{}}; {statement}"
    return ""


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "sha256:absent"
    for path in sorted(
        p for p in root.rglob("*")
        if p.is_file() and ".state" not in p.relative_to(root).parts
    ):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


CPP_PREAMBLE = r'''
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <numeric>
#include <optional>
#include <utility>
#include <vector>

namespace {
using U = std::uint64_t;
constexpr U M = std::numeric_limits<U>::max();
[[maybe_unused]] bool add(U a,U b,U& out){if(a>M-b)return false;out=a+b;return true;}
[[maybe_unused]] bool mul(U a,U b,U& out){if(a!=0&&b>M/a)return false;out=a*b;return true;}
[[maybe_unused]] U gcd_u(U a,U b){while(b){U r=a%b;a=b;b=r;}return a;}
[[maybe_unused]] bool choose_u(U n,U k,U& out){
 if(k>n){return false;}
 k=std::min(k,n-k);out=1;
 for(U i=1;i<=k;++i){U num=n-k+i,den=i;U g=gcd_u(num,den);num/=g;den/=g;g=gcd_u(out,den);out/=g;den/=g;if(den!=1||!mul(out,num,out))return false;}
 return true;
}
[[maybe_unused]] bool pow_u(U base,U exp,U& out){out=1;while(exp){if(exp&1U){if(!mul(out,base,out))return false;}exp>>=1U;if(exp&& !mul(base,base,base))return false;}return true;}
}
'''


def _core(case: TaskCase, *, wrong: bool = False) -> str:
    k = case.kind
    bodies = {
        "sum": "U s=0,t=0;for(U v:input.terms){if(!add(s,v,t))return std::nullopt;s=t;}return s;",
        "product": "if(std::find(input.factors.begin(),input.factors.end(),U{0})!=input.factors.end())return U{0};U p=1,t=0;for(U v:input.factors){if(!mul(p,v,t))return std::nullopt;p=t;}return p;",
        "ledger": "if(input.opening>input.cap)return std::nullopt;U b=input.opening;for(auto d:input.deltas){if(d<0){U x=U(-(d+1))+1;if(x>b)return std::nullopt;b-=x;}else{U x=U(d),t=0;if(!add(b,x,t)||t>input.cap)return std::nullopt;b=t;}}return b;",
        "weighted": "U s=0,p=0,t=0;for(auto [u,r]:input.loads){if(!mul(u,r,p)||!add(s,p,t))return std::nullopt;s=t;}return s;",
        "reserve": "U b=input.opening,low=b;for(auto d:input.changes){if(d<0){U x=U(-(d+1))+1;if(x>b)return std::nullopt;b-=x;}else{U t=0;if(!add(b,U(d),t))return std::nullopt;b=t;}low=std::min(low,b);}return low;",
        "arithmetic_series": "if(input.count==0)return U{0};if(input.count==1)return input.first;U span=0,last=0,p=0;if(!mul(input.step,input.count-1,span)||!add(input.first,span,last))return std::nullopt;U a=input.count,b=0;if((a&1U)==0){a/=2;if(!add(input.first,last,b))return std::nullopt;}else{U half_first=input.first/2,half_last=last/2;if(!add(half_first,half_last,b)||((input.first&1U)!=0&&!add(b,1,b)))return std::nullopt;}if(!mul(a,b,p))return std::nullopt;return p;",
        "geometric_series": "U s=0,term=input.first,t=0;for(std::uint32_t i=0;i<input.count;++i){if(!add(s,term,t))return std::nullopt;s=t;if(i+1<input.count&&!mul(term,input.ratio,term))return std::nullopt;}return s;",
        "interval_charge": "U s=0,last=0,p=0,t=0;bool first=true;for(auto x:input.spans){if(x.end<x.begin||(!first&&x.begin<last))return std::nullopt;if(!mul(x.end-x.begin,x.rate,p)||!add(s,p,t))return std::nullopt;s=t;last=x.end;first=false;}return s;",
        "box_volume": "U s=0,p=0,q=0,t=0;for(auto b:input.boxes){if(b.width==0||b.height==0||b.depth==0)continue;if(!mul(b.width,b.height,p)||!mul(p,b.depth,q)||!add(s,q,t)||t>input.budget)return std::nullopt;s=t;}return s;",
        "histogram": "U s=0,off=0,x=0,p=0,t=0;for(std::size_t i=0;i<input.counts.size();++i){if(!mul(U(i),input.stride,off)||!add(input.origin,off,x)||!mul(x,input.counts[i],p)||!add(s,p,t))return std::nullopt;s=t;}return s;",
        "horner": "U y=0,t=0;for(U c:input.coefficients){if(!mul(y,input.x,t)||!add(t,c,y))return std::nullopt;}return y;",
        "fraction": "if(input.left_den==0||input.right_den==0)return std::nullopt;U a=0,b=0,s=0;if(!mul(input.left_num,input.right_den,a)||!mul(input.right_num,input.left_den,b)||!add(a,b,s))return std::nullopt;return s;",
        "path_cost": "U s=0,p=0,t=0;for(auto e:input.edges){if(!mul(e.cost,e.traversals,p)||!add(s,p,t))return std::nullopt;s=t;}return s;",
        "tree_budget": "if(input.parent.size()!=input.cost.size()||input.parent.empty()||input.parent[0]!=-1)return std::nullopt;std::vector<U>d(input.parent.size());U s=0,p=0,t=0;for(std::size_t i=0;i<input.parent.size();++i){if(i>0&&(input.parent[i]<0||std::size_t(input.parent[i])>=i))return std::nullopt;d[i]=i?d[std::size_t(input.parent[i])]+1:0;if(!mul(input.cost[i],d[i]+1,p)||!add(s,p,t))return std::nullopt;s=t;}return s;",
        "rubric": "U s=0,t=0;for(auto c:input.categories){if(c.maximum==0)return std::nullopt;if(!add(s,std::min(c.earned,c.maximum),t))return std::nullopt;s=t;}return s;",
        "decay": "if(input.denominator==0||input.numerator>input.denominator)return std::nullopt;U s=0,pow_num=1,pow_den=1,t=0,p=0;for(std::size_t i=0;i<input.newest_first.size();++i){U v=input.newest_first[i];if(!mul(v,pow_num,p)||!add(s,p/pow_den,t))return std::nullopt;s=t;if(i+1<input.newest_first.size()&&(!mul(pow_num,input.numerator,pow_num)||!mul(pow_den,input.denominator,pow_den)))return std::nullopt;}return s;",
        "streak": "U s=0,run=0,p=0,t=0;for(bool ok:input.successes){if(!ok){run=0;continue;}++run;if(!mul(input.base,run,p)||!add(s,p,t))return std::nullopt;s=t;}return s;",
        "midrank": "if(input.population.empty())return std::nullopt;U less=0,ties=0;for(auto v:input.population){less+=v<input.value;ties+=v==input.value;}U twice=2*less+ties,n=U(input.population.size()),p=0;if(!mul(5000,twice,p))return std::nullopt;return p/n;",
        "weighted_median": "if(input.marks.empty())return std::nullopt;auto v=input.marks;U total=0,t=0;for(auto m:v){if(m.value<0||m.weight==0||!add(total,m.weight,t))return std::nullopt;total=t;}std::stable_sort(v.begin(),v.end(),[](auto a,auto b){return a.value<b.value;});U target=total/2+total%2,seen=0;for(auto m:v){if(!add(seen,m.weight,seen))return std::nullopt;if(seen>=target)return U(m.value);}return std::nullopt;",
        "trimmed_mean": "if(input.marks.empty()||input.trim_each_side>(input.marks.size()-1)/2)return std::nullopt;auto v=input.marks;std::sort(v.begin(),v.end());U s=0,t=0;for(std::size_t i=input.trim_each_side;i<v.size()-input.trim_each_side;++i){if(!add(s,v[i],t))return std::nullopt;s=t;}U kept=U(v.size()-input.trim_each_side-input.trim_each_side);return s/kept;",
        "round_robin": "if(input.win_points<=input.draw_points)return std::nullopt;U s=0,a=0,b=0,t=0;for(auto r:input.rounds){if(!mul(r.wins,input.win_points,a)||!mul(r.draws,input.draw_points,b)||!add(a,b,a)||!add(s,a,t))return std::nullopt;s=t;}return s;",
        "penalty": "U used=0,p=0,t=0;for(auto x:input.penalties){if(!mul(x.count,x.weight,p)||!add(used,p,t))return std::nullopt;used=t;}if(used>input.base)return std::nullopt;return input.base-used;",
        "tier": "for(auto [width,rate]:input.width_rate)if(width==0||rate==0)return std::nullopt;if(input.usage==0)return U{0};U left=input.usage,s=0,p=0,t=0;for(auto [width,rate]:input.width_rate){U take=std::min(left,width);if(!mul(take,rate,p)||!add(s,p,t))return std::nullopt;s=t;left-=take;if(left==0)return s;}return std::nullopt;",
        "quorum": "if(input.quorum_weight>input.eligible_weight)return std::nullopt;U yes=0,no=0,t=0;for(auto b:input.ballots){U& target=b.yes?yes:no;if(!add(target,b.weight,t))return std::nullopt;target=t;}U cast=0;if(!add(yes,no,cast)||cast>input.eligible_weight||cast<input.quorum_weight||yes<no)return std::nullopt;return yes-no;",
        "harmonic": "U s=0,t=0;for(auto p:input.placements){if(p==0)return std::nullopt;if(!add(s,input.scale/p,t))return std::nullopt;s=t;}return s;",
        "trapezoid": "if(input.points.size()<2)return std::nullopt;U twice=0,dx=0,ys=0,p=0,t=0;for(std::size_t i=1;i<input.points.size();++i){if(input.points[i].x<=input.points[i-1].x)return std::nullopt;dx=input.points[i].x-input.points[i-1].x;if(!add(input.points[i].y,input.points[i-1].y,ys)||!mul(dx,ys,p)||!add(twice,p,t))return std::nullopt;twice=t;}if(twice&1U)return std::nullopt;return twice/2;",
        "reliability": "if(input.successes>input.trials||(input.prior_success==0&&input.prior_failure==0))return std::nullopt;U num=0,den=0,p=0;if(!add(input.successes,input.prior_success,num)||!add(input.trials,input.prior_success,den)||!add(den,input.prior_failure,den)||!mul(num,10000,p))return std::nullopt;return p/den;",
        "binomial": "U out=0;if(!choose_u(input.n,input.k,out))return std::nullopt;return out;",
        "falling": "if(input.chosen>input.available)return std::nullopt;U p=1;for(U i=0;i<input.chosen;++i)if(!mul(p,input.available-i,p))return std::nullopt;return p;",
        "multiset": "U total=0,out=1,c=0,t=0;for(U m:input.multiplicities){if(!add(total,m,t))return std::nullopt;total=t;if(!choose_u(total,m,c)||!mul(out,c,out))return std::nullopt;}return out;",
        "catalan": "std::vector<U>d(input.nodes+1);d[0]=1;for(U n=1;n<=input.nodes;++n)for(U i=0;i<n;++i){U p=0,t=0;if(!mul(d[i],d[n-1-i],p)||!add(d[n],p,t))return std::nullopt;d[n]=t;}return d[input.nodes];",
        "derangement": "if(input.items==0)return U{1};if(input.items==1)return U{0};U a=1,b=0;for(U n=2;n<=input.items;++n){U s=0,c=0;if(!add(a,b,s)||!mul(n-1,s,c))return std::nullopt;a=b;b=c;}return b;",
        "stirling": "if(input.nonempty_groups>input.items)return U{0};std::vector<U>d(input.nonempty_groups+1);d[0]=1;for(U n=1;n<=input.items;++n){for(U k=std::min<U>(n,input.nonempty_groups);k>0;--k){U p=0,t=0;if(!mul(k,d[k],p)||!add(d[k-1],p,t))return std::nullopt;d[k]=t;}d[0]=0;}return d[input.nonempty_groups];",
        "bell": "std::vector<std::vector<U>>a(input.items+1,std::vector<U>(input.items+1));a[0][0]=1;for(U i=1;i<=input.items;++i){a[i][0]=a[i-1][i-1];for(U j=1;j<=i;++j)if(!add(a[i][j-1],a[i-1][j-1],a[i][j]))return std::nullopt;}return a[input.items][0];",
        "lattice": "std::vector<U>d(input.north_steps+1,1);for(U e=1;e<=input.east_steps;++e)for(U n=1;n<=input.north_steps;++n)if(!add(d[n],d[n-1],d[n]))return std::nullopt;return d[input.north_steps];",
        "weak_composition": "if(input.parts==0)return std::nullopt;U out=0;if(!choose_u(U(input.total)+input.parts-1,input.parts-1,out))return std::nullopt;return out;",
        "bounded_composition": "std::vector<U>d(input.total+1);d[0]=1;for(U cap:input.maxima){std::vector<U>n(input.total+1);U window=0,t=0;for(U s=0;s<=input.total;++s){if(!add(window,d[s],t))return std::nullopt;window=t;if(s>cap)window-=d[s-cap-1];n[s]=window;}d.swap(n);}return d[input.total];",
        "multinomial": "U remain=input.total,out=1,c=0;for(U size:input.category_sizes){if(size>remain||!choose_u(remain,size,c)||!mul(out,c,out))return std::nullopt;remain-=size;}if(remain!=0)return std::nullopt;return out;",
        "onto": "if(input.labeled_bins==0)return input.labeled_items==0?std::optional<U>(1):std::nullopt;if(input.labeled_bins>input.labeled_items)return std::nullopt;U pos=0,neg=0;for(U j=0;j<=input.labeled_bins;++j){U c=0,p=0,t=0;if(!choose_u(input.labeled_bins,j,c)||!pow_u(input.labeled_bins-j,input.labeled_items,p)||!mul(c,p,p))return std::nullopt;U& bucket=(j&1U)?neg:pos;if(!add(bucket,p,t))return std::nullopt;bucket=t;}if(neg>pos)return std::nullopt;return pos-neg;",
        "handshake": "if(input.people_around_circle&1U)return std::nullopt;U pairs=input.people_around_circle/2;std::vector<U>d(pairs+1);d[0]=1;for(U n=1;n<=pairs;++n)for(U i=0;i<n;++i){U p=0,t=0;if(!mul(d[i],d[n-1-i],p)||!add(d[n],p,t))return std::nullopt;d[n]=t;}return d[pairs];",
        "ballot": "if(input.leader_votes<=input.trailer_votes)return std::nullopt;U c=0,p=0;if(!choose_u(U(input.leader_votes)+input.trailer_votes,input.trailer_votes,c)||!mul(c,input.leader_votes-input.trailer_votes,p))return std::nullopt;return p/(U(input.leader_votes)+input.trailer_votes);",
    }
    if not wrong:
        return bodies[k]
    wrongs = {
        "sum": "U s=0;for(std::size_t i=0;i+1<input.terms.size();++i)s+=input.terms[i];return s;",
        "product": "U p=0;for(U v:input.factors)p+=v;return p;",
        "ledger": "U b=input.opening;for(auto d:input.deltas)if(d>0)b=std::min(input.cap,b+U(d));return b;",
        "weighted": "U s=0;for(auto [u,r]:input.loads)s+=u+r;return s;",
        "reserve": "U b=input.opening;for(auto d:input.changes)b=U(std::int64_t(b)+d);return b;",
        "arithmetic_series": "U s=0;for(U i=1;i<input.count;++i)s+=input.first+i*input.step;return s;",
        "geometric_series": "U p=1;for(std::uint32_t i=0;i<input.count;++i)p*=input.ratio;return input.first*p;",
        "interval_charge": "U s=0;for(auto x:input.spans)s+=(x.end-x.begin+1)*x.rate;return s;",
        "box_volume": "U s=0;for(auto b:input.boxes)s+=2*(b.width*b.height+b.height*b.depth+b.width*b.depth);return s;",
        "histogram": "return std::accumulate(input.counts.begin(),input.counts.end(),U{0});",
        "horner": "U y=0,p=1;for(U c:input.coefficients){y+=c*p;p*=input.x;}return y;",
        "fraction": "if(!input.left_den||!input.right_den)return std::nullopt;return input.left_num+input.right_num;",
        "path_cost": "U s=0;for(auto e:input.edges)s+=e.cost;return s;",
        "tree_budget": "return std::accumulate(input.cost.begin(),input.cost.end(),U{0});",
        "rubric": "U s=0;for(auto c:input.categories)s+=c.earned;return s;",
        "decay": "U s=std::accumulate(input.newest_first.begin(),input.newest_first.end(),U{0});return s*input.numerator/input.denominator;",
        "streak": "return U(std::count(input.successes.begin(),input.successes.end(),true))*input.base;",
        "midrank": "if(input.population.empty())return std::nullopt;U less=0;for(auto v:input.population)less+=v<input.value;return 10000*less/input.population.size();",
        "weighted_median": "if(input.marks.empty())return std::nullopt;auto v=input.marks;std::sort(v.begin(),v.end(),[](auto a,auto b){return a.value<b.value;});return U(v[v.size()/2].value);",
        "trimmed_mean": "if(input.marks.empty())return std::nullopt;return std::accumulate(input.marks.begin(),input.marks.end(),U{0})/input.marks.size();",
        "round_robin": "U s=0;for(auto r:input.rounds)s+=r.wins+r.draws+r.losses;return s;",
        "penalty": "U s=input.base;for(auto p:input.penalties)s=s>p.weight?s-p.weight:0;return s;",
        "tier": "if(input.width_rate.empty())return std::nullopt;return input.usage*input.width_rate.back().second;",
        "quorum": "U yes=0,no=0;for(auto b:input.ballots)(b.yes?yes:no)++;return input.eligible_weight+yes-no;",
        "harmonic": "U s=0;for(auto p:input.placements)s+=input.scale*p;return s;",
        "trapezoid": "U s=0;for(std::size_t i=1;i<input.points.size();++i)s+=(input.points[i].x-input.points[i-1].x)*input.points[i-1].y;return s;",
        "reliability": "if(!input.trials)return std::nullopt;return input.successes*10000/input.trials;",
        "binomial": "U p=1;for(U i=2;i<=input.n;++i)p*=i;return p;",
        "falling": "U p=1;for(U i=0;i<input.chosen;++i)p*=input.available;return p;",
        "multiset": "U total=std::accumulate(input.multiplicities.begin(),input.multiplicities.end(),U{0}),p=1;for(U i=2;i<=total;++i)p*=i;return p;",
        "catalan": "U c=0;if(!choose_u(2*input.nodes,input.nodes,c))return std::nullopt;return c;",
        "derangement": "U p=1;for(U i=2;i<=input.items;++i)p*=i;return p-1;",
        "stirling": "U c=0;if(!choose_u(input.items,input.nonempty_groups,c))return std::nullopt;return c;",
        "bell": "U p=0;if(!pow_u(2,input.items,p))return std::nullopt;return p;",
        "lattice": "return U(input.east_steps)+input.north_steps;",
        "weak_composition": "if(input.parts==0||input.total<input.parts)return std::nullopt;U c=0;if(!choose_u(input.total-1,input.parts-1,c))return std::nullopt;return c;",
        "bounded_composition": "if(input.maxima.empty())return std::nullopt;U c=0;if(!choose_u(input.total+input.maxima.size()-1,input.maxima.size()-1,c))return std::nullopt;return c;",
        "multinomial": "U p=1;for(U s:input.category_sizes)p*=s;return p;",
        "onto": "U p=0;if(!pow_u(input.labeled_bins,input.labeled_items,p))return std::nullopt;return p;",
        "handshake": "U p=1;for(U x=input.people_around_circle-1;x>0;x-=2)p*=x;return p;",
        "ballot": "U c=0;if(!choose_u(U(input.leader_votes)+input.trailer_votes,input.trailer_votes,c))return std::nullopt;return c;",
    }
    return wrongs[k]


def _header(case: TaskCase) -> str:
    guard = case.task_id.replace("-", "_").upper() + "_H"
    return f'''#ifndef {guard}\n#define {guard}\n#include <cstddef>\n#include <cstdint>\n#include <optional>\n#include <utility>\n#include <vector>\n\nstruct {case.input_name} {{ {case.fields} }};\n\nclass {case.class_name} {{\npublic:\n    static std::optional<std::uint64_t> evaluate(const {case.input_name}& input);\n}};\n#endif\n'''


def _source(case: TaskCase, *, wrong: bool = False) -> str:
    body = (_resource_guard(case) + _core(case, wrong=wrong)).replace(";", ";\n")
    return (
        f'#include "{case.task_id}.h"\n' + CPP_PREAMBLE
        + f'\nstd::optional<std::uint64_t> {case.class_name}::evaluate('
        + f'const {case.input_name}& input) {{\n// CORE_BEGIN {case.mechanism}\n'
        + body
        + '\n// CORE_END\n}\n'
    )


def _test_source(case: TaskCase, *, hidden: bool) -> str:
    value = case.hidden_input if hidden else case.visible_input
    expected = case.hidden_expected if hidden else case.visible_expected
    invalid_check = ""
    if hidden:
        edge_input, edge_expected = EDGE_CASES[case.kind]
        resource_setup = _resource_test(case)
        resource_check = ""
        if resource_setup:
            resource_check = f'''\n    {resource_setup}\n    if ({case.class_name}::evaluate(oversized).has_value()) return 5;'''
        additional_checks: list[str] = []
        exit_code = 6
        for literal in ADDITIONAL_INVALID_CASES.get(case.kind, []):
            additional_checks.append(
                f"    if ({case.class_name}::evaluate({case.input_name}{literal}).has_value()) "
                f"return {exit_code};"
            )
            exit_code += 1
        for literal, additional_expected in ADDITIONAL_VALID_CASES.get(case.kind, []):
            additional_checks.append(
                f"    const auto extra_{exit_code} = {case.class_name}::evaluate("
                f"{case.input_name}{literal});\n"
                f"    if (!extra_{exit_code}.has_value() || *extra_{exit_code} != "
                f"{additional_expected}ULL) return {exit_code};"
            )
            exit_code += 1
        extra_contract_checks = "\n" + "\n".join(additional_checks) if additional_checks else ""
        invalid_check = f'''\n    const auto invalid = {case.class_name}::evaluate({case.input_name}{case.invalid_input});\n    if (invalid.has_value()) return 3;\n    const auto edge = {case.class_name}::evaluate({case.input_name}{edge_input});\n    if (!edge.has_value() || *edge != {edge_expected}ULL) return 4;{resource_check}{extra_contract_checks}'''
    return f'''#include "{case.task_id}.h"\n#include <cstdint>\nint main() {{\n    const auto result = {case.class_name}::evaluate({case.input_name}{value});\n    if (!result.has_value()) return 1;\n    if (*result != {expected}ULL) return 2;{invalid_check}\n    return 0;\n}}\n'''


def _instructions(case: TaskCase) -> str:
    scalar_limit = (
        " Geometric-series counts greater than one million are rejected."
        if case.kind == "geometric_series" else ""
    )
    boundary_text = case.boundary[0].lower() + case.boundary[1:]
    if not boundary_text.endswith("."):
        boundary_text += "."
    return f'''# Instructions

Implement the complete C++17 API in `{case.task_id}.h` and `{case.task_id}.cpp`.
`{case.class_name}::evaluate(const {case.input_name}&)` returns an exact unsigned
64-bit result or `std::nullopt` when the documented input contract or an
intermediate exact-arithmetic bound is violated.

The operation is the {case.mechanism}: {boundary_text} The implementation
must detect overflow before each affected operation and must never rely on
unsigned wraparound, signed overflow, floating-point approximation, a
precomputed answer table, or hard-coded examples. Input vectors longer than
4096 elements are rejected; dynamic programs also reject the documented
one-million-cell budget (Bell triangles are capped at 1024 rows and Catalan
tables at 4096 entries).{scalar_limit} A generic approach based on
{case.forbidden} does not satisfy this contract. Empty and zero cases follow the
mechanism-specific identity stated above. The implementation must be
deterministic and offline.

## Examples

`{case.class_name}::evaluate({case.input_name}{case.visible_input})` returns `{case.visible_expected}`.
'''


def _cmake(case: TaskCase) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_library(solution STATIC {case.task_id}.cpp)
target_compile_options(solution PRIVATE -Wall -Wextra -Wpedantic -Werror)
add_executable(visible_test task_visible_test.cpp)
target_link_libraries(visible_test PRIVATE solution)
target_compile_options(visible_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
add_executable(hidden_test .meta/task_hidden_test.cpp)
target_link_libraries(hidden_test PRIVATE solution)
target_include_directories(hidden_test PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
target_compile_options(hidden_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
add_executable(negative_test .meta/negative_false_substitute.cpp .meta/task_negative_test.cpp)
target_include_directories(negative_test PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
target_compile_options(negative_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
enable_testing()
add_test(NAME visible COMMAND visible_test)
add_test(NAME hidden COMMAND hidden_test)
'''


def _task_files(case: TaskCase) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.title,
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "schema_version": "aider-local-provenance-v2",
        "task_id": case.task_id,
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "source_document": str(CURRICULUM),
        "authoring_origin": "clean-room deterministic repository generator",
        "license": "Apache-2.0",
        "generator": OWNER,
        "selected_prompts": list(SELECTED_PROMPTS),
        "status": "local candidate; not dataset admission",
    }
    return {
        ".docs/introduction.md": (
            f"# {case.title}\n\n"
            "Combinatorial counting answers questions of the form \"how many "
            "ways can this happen?\" — ballot sequences, lattice paths, "
            "partitions, and recurrence tables. The counts explode quickly, so "
            "exact arithmetic and early overflow detection matter as much as "
            "the formula itself.\n\n"
            "This exercise is about one such counting rule: "
            f"{case.mechanism}.\n"
        ),
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            f'[visible]\ndescription = "public example for {case.mechanism}"\n\n'
            f'[hidden]\ndescription = "boundary and exact arithmetic oracle: {case.boundary}"\n\n'
            f'[topic_negative]\ndescription = "compiled {case.forbidden} substitute must fail"\n'
        ),
        f"{case.task_id}.h": _header(case),
        f"{case.task_id}.cpp": (
            f'#include "{case.task_id}.h"\n\nstd::optional<std::uint64_t> '
            f'{case.class_name}::evaluate(const {case.input_name}&) {{ return std::nullopt; }}\n'
        ),
        ".meta/example.h": _header(case),
        ".meta/example.cpp": _source(case),
        "task_visible_test.cpp": _test_source(case, hidden=False),
        ".meta/task_hidden_test.cpp": _test_source(case, hidden=True),
        ".meta/negative_false_substitute.cpp": _source(case, wrong=True),
        ".meta/task_negative_test.cpp": _test_source(case, hidden=True),
        "CMakeLists.txt": _cmake(case),
    }


def _safe_output(out: Path) -> Path:
    resolved = out.resolve()
    expansion = EXPANSION_ROOT.resolve()
    if not resolved.is_relative_to(expansion):
        _fail("unsafe_output_root", f"{out} is not under {EXPANSION_ROOT}")
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or resolved.is_relative_to(forbidden):
            _fail("unsafe_output_root", str(out))
    current = resolved
    while current != expansion.parent:
        if current.exists() and current.is_symlink():
            _fail("unsafe_output_symlink", str(current))
        if current == expansion:
            break
        current = current.parent
    return resolved


def _task_inventory(root: Path) -> dict[str, Path]:
    inventory: dict[str, Path] = {}
    if not root.is_dir():
        return inventory
    for config in root.rglob(".meta/config.json"):
        if ".state" in config.parts:
            continue
        task_root = config.parent.parent
        inventory[task_root.relative_to(root).as_posix()] = task_root
    return inventory


def _prompt_hash_for_root(root: Path) -> str:
    try:
        return _sha256(build_prompt(load_task(root)).encode())
    except (OSError, KeyError, ValueError, TypeError):
        return "unavailable"


def _reference_hash_for_root(root: Path) -> str:
    try:
        config = json.loads((root / ".meta/config.json").read_text())
        digest = hashlib.sha256()
        for relative in config["files"]["example"]:
            data = (root / relative).read_bytes()
            digest.update(relative.encode())
            digest.update(data)
        return "sha256:" + digest.hexdigest()
    except (OSError, KeyError, ValueError, TypeError):
        return "unavailable"


def _candidate_exact_hashes() -> tuple[set[str], set[str]]:
    prompts: set[str] = set()
    references: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="overflow-candidate-hashes-", dir="/tmp") as temp:
        base = Path(temp)
        for case in TASKS:
            root = base / case.task_id
            for relative, content in _task_files(case).items():
                _write(root / relative, content)
            prompts.add(_prompt_hash_for_root(root))
            references.add(_reference_hash_for_root(root))
    if len(prompts) != len(TASKS) or len(references) != len(TASKS):
        _fail("duplicate_family", "candidate prompt or reference hash collision")
    return prompts, references


def _validate_cross_tree(out: Path) -> dict[str, object]:
    ids = {case.task_id for case in TASKS}
    legacy = _task_inventory(LEGACY_ROOT)
    reverify = _task_inventory(REVERIFY_ROOT)
    expansion = _task_inventory(EXPANSION_ROOT)
    own_existing = {
        p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"
    } if out.is_dir() else set()
    legacy_ids = {p.name for p in legacy.values()}
    reverify_ids = {p.name for p in reverify.values()}
    expansion_other_ids = {
        p.name for p in expansion.values()
        if not (p.parent == out and p.name in own_existing)
    }
    collisions = ids & (legacy_ids | reverify_ids | expansion_other_ids)
    if collisions:
        _fail("duplicate_task_id", ",".join(sorted(collisions)))
    comparison_roots = [
        *legacy.values(), *reverify.values(),
        *(p for p in expansion.values() if not (p.parent == out and p.name in own_existing)),
    ]
    records = [
        {
            "task_id": root.name,
            "path": str(root),
            "tree_hash": _tree_hash(root),
            "prompt_hash": _prompt_hash_for_root(root),
            "reference_hash": _reference_hash_for_root(root),
            "semantic_tokens": sorted(_root_tokens(root, _semantic_text(root))),
            "semantic_scopes": {
                name: sorted(tokens)
                for name, tokens in _external_feature_scopes(root).items()
            },
        }
        for root in comparison_roots
    ]
    candidate_prompts, candidate_references = _candidate_exact_hashes()
    prompt_collisions = sorted(candidate_prompts & {row["prompt_hash"] for row in records})
    reference_collisions = sorted(candidate_references & {row["reference_hash"] for row in records})
    if prompt_collisions:
        _fail("duplicate_prompt_hash", ",".join(prompt_collisions))
    if reference_collisions:
        _fail("duplicate_reference_hash", ",".join(reference_collisions))
    expansion_other_count = len(expansion) - len(own_existing)
    if len(records) != len(legacy) + len(reverify) + expansion_other_count:
        _fail("source_inventory_count_mismatch")
    return {
        "legacy_count": len(legacy),
        "reverify_count": len(reverify),
        "expansion_other_count": expansion_other_count,
        "candidate_count": len(TASKS),
        "id_collisions": [],
        "prompt_hash_collisions": [],
        "reference_hash_collisions": [],
        "comparison_root_count": len(records),
        "comparison_inventory_hash": _sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()),
        "records": records,
    }


def materialize(out: Path = DEFAULT_OUT, *, force: bool = False) -> dict[str, object]:
    _safe_output(out)
    inventory = _validate_cross_tree(out)
    out.mkdir(parents=True, exist_ok=True)
    foreign: list[str] = []
    for child in out.iterdir():
        if child.name == ".state":
            continue
        provenance_path = child / ".meta/provenance.json"
        if not child.is_dir() or not provenance_path.is_file():
            foreign.append(child.name)
            continue
        if json.loads(provenance_path.read_text()).get("generator") != OWNER:
            foreign.append(child.name)
    if foreign:
        _fail("foreign_generated_root", ",".join(sorted(foreign)))
    state = out / ".state"
    if force and state.is_dir():
        stale_paths = [
            state / name for name in (
                "family-screen.json", "prompt-boundary.json", "lineage-screen.json",
                "benchmark-screen.json", "holdout-inventory.json",
                "docker-sanity-receipt.json", "audit-subject.json",
            ) if (state / name).is_file()
        ]
        if stale_paths:
            cycles = state / "cycles"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            _write_json(cycles / f"evidence-invalidated-{stamp}.json", {
                "schema_version": 1,
                "state": "evidence_invalidated",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "reason": "owner or generated artifact changed before complete regeneration",
                "invalidated": [
                    {"path": path.relative_to(out).as_posix(), "hash": _sha256(path.read_bytes())}
                    for path in stale_paths
                ],
            })
        for path in stale_paths:
            path.unlink()
        for stale_dir in (state / "receipts", state / "controls"):
            if stale_dir.is_dir():
                shutil.rmtree(stale_dir)
    existing = {p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"}
    expected = {case.task_id for case in TASKS}
    if existing and existing != expected and not force:
        _fail("generator_output_drift", f"existing={len(existing)} expected=40")
    if force:
        for task_id in sorted(existing):
            shutil.rmtree(out / task_id)
    elif existing:
        _fail("output_exists", "pass --force for owner-controlled regeneration")
    for case in TASKS:
        root = out / case.task_id
        for relative, content in _task_files(case).items():
            _write(root / relative, content)
    proposals = [
        {
            "proposal_id": f"proposal-{i:03d}",
            "task_id": case.task_id,
            "cluster": case.cluster,
            "mechanism": case.mechanism,
            "decision": "selected-new-root",
        }
        for i, case in enumerate(TASKS, 1)
    ]
    rejected = [
        {"proposal_id": "control-domain-rename", "decision": "reject", "reason": "domain/identifier rename only"},
        {"proposal_id": "control-policy-only", "decision": "reject", "reason": "constants/policy-only variant"},
        {"proposal_id": "control-opposite-end", "decision": "reject", "reason": "opposite-end traversal variant"},
    ]
    _write_json(state / "raw-proposals.json", {"schema_version": 1, "proposals": proposals + rejected})
    _write_json(state / "selected-manifest.json", {"schema_version": 1, "family_id": FAMILY_ID, "requested_count": 40, "retained_count": 40, "tasks": proposals})
    _write_json(state / "rejected-proposals.json", {"schema_version": 1, "rejected": rejected})
    _write_json(state / "source-inventory.json", inventory)
    audit_reports = sorted((state / "audits").glob("cycle-*.json"))
    for audit_report in audit_reports:
        audit = json.loads(audit_report.read_text())
        audit_hash = _sha256(audit_report.read_bytes())
        for finding in audit["findings"]:
            remedy = {
                "schema_version": 1,
                "finding_id": finding["id"],
                "audit_subject_hash": audit["audit_subject_hash"],
                "audit_report_hash": audit_hash,
                "disposition": finding["disposition"],
                "affected": finding["affected"],
                "root_cause": finding["finding"],
                "repair_owner": OWNER,
                "repair_scope": [OWNER, str(CURRICULUM), str(FAMILY_SPEC), FOCUSED_TEST],
                "verification": "complete regeneration, focused tests, creator preflight, Docker normal/sanitizer/negative matrix, fresh independent audit",
                "status": "implemented_pending_regeneration_and_fresh_audit",
            }
            remedy_path = state / "remedy" / f"{finding['id']}.json"
            if remedy_path.is_file() and json.loads(remedy_path.read_text()) != remedy:
                remedy_path = (
                    state / "remedy"
                    / f"cycle-{int(audit.get('audit_cycle', 0)):03d}-{finding['id']}.json"
                )
            if remedy_path.is_file():
                if json.loads(remedy_path.read_text()) != remedy:
                    _fail("remedy_record_drift", finding["id"])
            else:
                _write_json(remedy_path, remedy)
        next_cycle = int(audit.get("audit_cycle", 0)) + 1
        plan_path = state / "cycles" / f"cycle-{next_cycle:03d}-remediation-plan.json"
        plan = {
            "schema_version": 1,
            "cycle": next_cycle,
            "state": "remediation",
            "prior_audit_subject_hash": audit["audit_subject_hash"],
            "prior_audit_report_hash": audit_hash,
            "finding_ids": [finding["id"] for finding in audit["findings"]],
            "dispositions": {finding["id"]: finding["disposition"] for finding in audit["findings"]},
            "terminal_status": "pending_complete_regeneration",
        }
        if plan_path.is_file():
            if json.loads(plan_path.read_text()) != plan:
                _fail("remediation_plan_drift", str(next_cycle))
        else:
            _write_json(plan_path, plan)
    summary = {key: value for key, value in inventory.items() if key != "records"}
    return {"out": str(out), "tasks": 40, "tree_hash": _tree_hash(out), **summary}


def _normalize(text: str) -> set[str]:
    text = re.sub(r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"", " ", text, flags=re.M | re.S)
    text = re.sub(r"\b\d+(?:ULL|UL|U|LL)?\b", " number ", text)
    text = re.sub(r"[A-Z][A-Za-z0-9_]*|[a-z][A-Za-z0-9_]*", lambda m: m.group(0).lower(), text)
    stop = {"const", "auto", "return", "input", "std", "uint64_t", "uint32_t", "size_t", "optional", "vector", "public", "class", "struct"}
    return {token for token in re.findall(r"[a-z_][a-z0-9_]*|[+*/%<>=!-]+", text) if token not in stop and len(token) > 1}


def _identity_tokens(root: Path) -> set[str]:
    slugs = {root.name.lower()}
    provenance = root / ".meta/provenance.json"
    if provenance.is_file():
        try:
            slugs.add(str(json.loads(provenance.read_text()).get("task_id", "")).lower())
        except (OSError, ValueError, TypeError):
            pass
    tokens: set[str] = set()
    for slug in slugs:
        parts = slug.split("-")
        joined = "".join(parts)
        tokens.update({slug, joined, "_".join(parts), *parts, joined + "input"})
    return tokens


def _root_tokens(root: Path, text: str) -> set[str]:
    return _normalize(text) - _identity_tokens(root)


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def _feature_scopes(root: Path) -> dict[str, set[str]]:
    header = next(root.glob("*.h")).read_text()
    docs = (root / ".docs/instructions.md").read_text()
    reference = (root / ".meta/example.cpp").read_text()
    core = reference.split("// CORE_BEGIN", 1)[1].split("// CORE_END", 1)[0]
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    test_contract = (root / ".meta/tests.toml").read_text()
    return {
        "public_api": _root_tokens(root, header + docs),
        "owned_state_or_algorithm": _root_tokens(root, core),
        "mutation_selection_rules": _root_tokens(root, docs + core),
        "invalid_boundary_behavior": _root_tokens(root, docs + hidden),
        "reference_control_flow": _root_tokens(root, core),
        "deterministic_oracle": _root_tokens(root, visible + hidden + test_contract.replace('"', "")),
        "topic_negative_fixture": _root_tokens(root, negative + test_contract.replace('"', "")),
    }


def _read_role_text(root: Path, relatives: Sequence[str]) -> str:
    parts: list[str] = []
    for relative in relatives:
        path = root / relative
        if path.is_file():
            parts.append(path.read_text(errors="replace"))
    return "\n".join(parts)


def _external_feature_scopes(root: Path) -> dict[str, set[str]]:
    """Project any Aider root onto the same seven semantic artifact scopes."""
    try:
        config = json.loads((root / ".meta/config.json").read_text())
        solution = [str(path) for path in config.get("files", {}).get("solution", [])]
        examples = [str(path) for path in config.get("files", {}).get("example", [])]
        tests = [str(path) for path in config.get("files", {}).get("test", [])]
    except (OSError, TypeError, ValueError):
        solution, examples, tests = [], [], []
    docs = [path.relative_to(root).as_posix() for path in sorted((root / ".docs").glob("*.md"))]
    headers = [path for path in solution if path.endswith((".h", ".hpp"))]
    if not headers:
        headers = [path.relative_to(root).as_posix() for path in sorted(root.glob("*.h"))]
    reference_text = _read_role_text(root, examples)
    if "// CORE_BEGIN" in reference_text and "// CORE_END" in reference_text:
        reference_core = reference_text.split("// CORE_BEGIN", 1)[1].split("// CORE_END", 1)[0]
    else:
        reference_core = reference_text
    docs_text = _read_role_text(root, docs)
    header_text = _read_role_text(root, headers)
    test_text = _read_role_text(root, tests)
    hidden_text = _read_role_text(
        root,
        [path.relative_to(root).as_posix() for path in sorted((root / ".meta").glob("*test*"))],
    )
    contract_text = _read_role_text(root, [".meta/tests.toml"])
    negative_text = _read_role_text(
        root,
        [path.relative_to(root).as_posix() for path in sorted((root / ".meta").glob("*negative*"))],
    )
    return {
        "public_api": _root_tokens(root, header_text + docs_text),
        "owned_state_or_algorithm": _root_tokens(root, reference_core),
        "mutation_selection_rules": _root_tokens(root, docs_text + reference_core),
        "invalid_boundary_behavior": _root_tokens(root, docs_text + hidden_text),
        "reference_control_flow": _root_tokens(root, reference_core),
        "deterministic_oracle": _root_tokens(root, test_text + hidden_text + contract_text),
        "topic_negative_fixture": _root_tokens(root, negative_text + contract_text),
    }


def _pair_decision(left: Path, right: Path) -> dict[str, object]:
    lf = _feature_scopes(left)
    rf = _feature_scopes(right)
    dimensions: dict[str, object] = {}
    for name in HARD_RULE_DIMENSIONS:
        score = _overlap(lf[name], rf[name])
        symmetric = len(lf[name] ^ rf[name])
        dimensions[name] = {
            "overlap": round(score, 6),
            "symmetric_difference": symmetric,
            "distinct": score < 0.98 and symmetric >= 2,
        }
    return {
        "left": left.name,
        "right": right.name,
        "dimensions": dimensions,
        "pass": all(row["distinct"] for row in dimensions.values()),
    }


def _semantic_text(root: Path) -> str:
    parts: list[str] = []
    for relative in (".docs/instructions.md", ".meta/example.cpp", ".meta/task_hidden_test.cpp"):
        path = root / relative
        if path.is_file():
            parts.append(path.read_text(errors="replace"))
    parts.extend(path.read_text(errors="replace") for path in sorted(root.glob("*.h")))
    return "\n".join(parts)


def _render_control(out: Path, name: str) -> Path:
    if name == "domain-identifier-renamed":
        base = TASKS[0]
        control = replace(base, task_id=f"control-{name}", title=f"Control {name}")
    elif name == "constants-policy-only":
        base = next(case for case in TASKS if case.kind == "rubric")
        control = replace(base, visible_input="{{{9, 10}, {8, 6}, {2, 5}}}", visible_expected=17)
    else:
        base = next(case for case in TASKS if case.kind == "weighted")
        control = base
    root = out / ".state/controls" / name
    if root.exists():
        shutil.rmtree(root)
    for relative, content in _task_files(control).items():
        _write(root / relative, content)
    if name == "opposite-end-selection":
        source = (root / ".meta/example.cpp").read_text()
        source = source.replace(
            "for(auto [u,r]:input.loads){",
            "for(auto it=input.loads.rbegin();it!=input.loads.rend();++it){auto [u,r]=*it;",
        )
        _write(root / ".meta/example.cpp", source)
    return root


def _control_base(out: Path, name: str) -> Path:
    kind = {
        "domain-identifier-renamed": "sum",
        "constants-policy-only": "rubric",
        "opposite-end-selection": "weighted",
    }[name]
    return out / next(case.task_id for case in TASKS if case.kind == kind)


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    roots = [out / case.task_id for case in TASKS]
    if any(not (root / ".meta/config.json").is_file() for root in roots):
        _fail("generator_output_drift", "missing task root")
    comparison_inventory = _validate_cross_tree(out)
    _write_json(out / ".state/source-inventory.json", comparison_inventory)
    scratch = EXPANSION_ROOT / ".state/generator-scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="overflow-scoring-fresh-", dir=scratch) as temp:
        fresh = Path(temp) / "family"
        for fresh_case in TASKS:
            for relative, content in _task_files(fresh_case).items():
                _write(fresh / fresh_case.task_id / relative, content)
        for case in TASKS:
            if _tree_hash(out / case.task_id) != _tree_hash(fresh / case.task_id):
                _fail("generator_output_drift", case.task_id)
    prompt_records = []
    for case, root in zip(TASKS, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        expected = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        if config["files"]["solution"] != expected:
            _fail("prompt_contract_incomplete", case.task_id)
        prompt = build_prompt(load_task(root))
        for private in ("CMakeLists.txt", "provenance.json", "example.cpp", "task_hidden_test", "negative_false"):
            if private in prompt:
                _fail("private_asset_leak", f"{case.task_id}:{private}")
        if not all(path in prompt for path in expected):
            _fail("prompt_contract_incomplete", case.task_id)
        prompt_records.append({"task_id": case.task_id, "prompt_hash": _sha256(prompt.encode()), "solution": expected})
    pairs = [_pair_decision(left, right) for left, right in combinations(roots, 2)]
    failed = [pair for pair in pairs if not pair["pass"]]
    if failed:
        _fail("duplicate_family", f"{len(failed)} of {len(pairs)} pairs")
    controls = {name: _render_control(out, name) for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection")}
    control_records = []
    for name, root in controls.items():
        base_root = _control_base(out, name)
        decision = _pair_decision(base_root, root)
        changed = _tree_hash(root) != _tree_hash(base_root)
        if not changed or decision["pass"]:
            _fail("adversarial_clone_not_rejected", name)
        control_records.append({"control": name, "base_task_id": base_root.name, "changed_tree": changed, "decision": decision})
    existing = [Path(row["path"]) for row in comparison_inventory["records"]]
    existing_scopes = [
        (
            Path(row["path"]),
            {name: set(tokens) for name, tokens in row["semantic_scopes"].items()},
        )
        for row in comparison_inventory["records"]
    ]
    lineage = []
    for root in roots:
        candidate_scopes = _external_feature_scopes(root)
        scored: list[tuple[float, float, Path, dict[str, float]]] = []
        for other, other_scopes in existing_scopes:
            per_dimension = {
                name: _overlap(candidate_scopes[name], other_scopes[name])
                for name in HARD_RULE_DIMENSIONS
            }
            values = list(per_dimension.values())
            scored.append((min(values), sum(values) / len(values), other, per_dimension))
        minimum, mean, existing_root, per_dimension = max(
            scored,
            key=lambda row: (row[0], row[1], str(row[2])),
            default=(0.0, 0.0, Path(), {}),
        )
        if per_dimension and all(score >= 0.82 for score in per_dimension.values()):
            _fail(
                "duplicate_family",
                f"{root.name} ~= {existing_root} across seven dimensions "
                f"(minimum={minimum:.3f}, mean={mean:.3f})",
            )
        lineage.append({
            "task_id": root.name,
            "existing_root": str(existing_root),
            "minimum_dimension_overlap": round(minimum, 6),
            "mean_dimension_overlap": round(mean, 6),
            "per_dimension_overlap": {
                name: round(score, 6) for name, score in per_dimension.items()
            },
            "rejection_threshold": 0.82,
            "all_dimensions_must_meet_threshold": True,
        })
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_content_unavailable", str(HOLDOUT_ROOT))
    holdouts = {p.name: p for p in HOLDOUT_ROOT.iterdir() if p.is_dir() and p.name in OFFICIAL_HOLDOUTS}
    if set(holdouts) != OFFICIAL_HOLDOUTS:
        _fail("benchmark_content_unavailable", str(sorted(OFFICIAL_HOLDOUTS - set(holdouts))))
    holdout_tokens = {name: _root_tokens(root, _semantic_text(root)) for name, root in holdouts.items()}
    contamination = []
    for root in roots:
        tokens = _root_tokens(root, _semantic_text(root))
        scores = {name: _overlap(tokens, value) for name, value in holdout_tokens.items()}
        name = max(scores, key=scores.get)
        if scores[name] >= 0.78:
            _fail("benchmark_content_overlap", f"{root.name}:{name}:{scores[name]:.3f}")
        contamination.append({"task_id": root.name, "strongest_holdout": name, "overlap": round(scores[name], 6)})
    state = out / ".state"
    _write_json(state / "family-screen.json", {"schema_version": 1, "normalizer": "arithmetic-artifacts-v1", "root_count": 40, "pair_count": len(pairs), "expected_pair_count": 780, "dimensions": list(HARD_RULE_DIMENSIONS), "pairs": pairs, "controls": control_records, "status": "pass"})
    _write_json(state / "prompt-boundary.json", {"status": "pass", "records": prompt_records})
    _write_json(state / "lineage-screen.json", {"status": "pass", "comparison_inventory_hash": comparison_inventory["comparison_inventory_hash"], "existing_comparison_count": len(existing) * 40, "records": lineage})
    holdout_checkout = HOLDOUT_ROOT.parents[2]
    revision = subprocess.run(["git", "-C", str(holdout_checkout), "rev-parse", "HEAD"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if revision.returncode != 0:
        _fail("benchmark_revision_unavailable", revision.stderr.strip())
    holdout_inventory = {
        "revision": revision.stdout.strip(),
        "records": [
            {"task_id": name, "tree_hash": _tree_hash(root), "prompt_hash": _prompt_hash_for_root(root), "reference_hash": _reference_hash_for_root(root)}
            for name, root in sorted(holdouts.items())
        ],
    }
    _write_json(state / "holdout-inventory.json", holdout_inventory)
    _write_json(state / "benchmark-screen.json", {"status": "pass", "holdout_revision": holdout_inventory["revision"], "holdout_inventory_hash": _sha256((state / "holdout-inventory.json").read_bytes()), "holdout_count": 26, "comparison_count": 1040, "records": contamination})
    return {"status": "pass", "root_count": 40, "pair_count": 780, "control_count": 3, "existing_comparisons": len(existing) * 40, "holdout_comparisons": 1040}


DOCKER_SCRIPT = r'''set -eu
cd /tasks
find . -type f ! -path './.state/*' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | sed 's/^/MOUNT_HASH|/'
work=/tmp/overflow-scoring-combinatorial
rm -rf "$work"
mkdir -p "$work"
find /tasks -path '*/.meta/config.json' -print | sort | while read config; do
  task=$(dirname "$(dirname "$config")")
  case "${task#/tasks/}" in .state/controls/*|[!.]*) ;; *) continue ;; esac
  id=$(basename "$task")
  stem=$(basename "$(find "$task" -maxdepth 1 -name '*.h' | head -1)" .h)
  for mode in normal sanitizer; do
    dst="$work/$id-$mode"
    cp -R "$task" "$dst"
    cp "$dst/.meta/example.h" "$dst/$stem.h"
    cp "$dst/.meta/example.cpp" "$dst/$stem.cpp"
    flags=''
    if [ "$mode" = sanitizer ]; then flags='-fsanitize=address,undefined -fno-omit-frame-pointer'; fi
    cmake -S "$dst" -B "$dst/build" -G 'Unix Makefiles' -DCMAKE_CXX_FLAGS="$flags" >/tmp/configure.log
    cmake --build "$dst/build" --parallel 2 >/tmp/build.log
    count=$(ctest --test-dir "$dst/build" -N | sed -n 's/.*Total Tests: //p')
    [ "$count" = 2 ]
    set +e
    ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$dst/build" --output-on-failure >/tmp/ctest.log 2>&1
    tests=$?
    ASAN_OPTIONS=detect_leaks=0 "$dst/build/negative_test" >/tmp/negative.log 2>&1
    negative=$?
    set -e
    echo "RESULT|$id|$mode|$count|$tests|$negative"
  done
done
'''


def _shell_tree_hash(out: Path) -> str:
    command = "find . -type f ! -path './.state/*' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum"
    completed = subprocess.run(
        ["sh", "-lc", command], cwd=out, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode != 0:
        _fail("tree_hash_failed", completed.stderr.strip())
    return completed.stdout.split()[0]


def docker_sanity(out: Path = DEFAULT_OUT) -> dict[str, object]:
    core = verify_core(out)
    host_mount_hash = _shell_tree_hash(out)
    command = [
        "docker", "run", "--rm", "--network", "none", "-v",
        f"{out.resolve()}:/tasks:ro", SANITY_IMAGE, "sh", "-lc", DOCKER_SCRIPT,
    ]
    completed = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=3600,
    )
    if completed.returncode != 0:
        _fail("docker_sanity_failed", completed.stderr[-3000:] + completed.stdout[-3000:])
    records: list[dict[str, object]] = []
    mount_hash = ""
    for line in completed.stdout.splitlines():
        if line.startswith("MOUNT_HASH|"):
            mount_hash = line.split("|", 1)[1].split()[0]
        elif line.startswith("RESULT|"):
            _, task_id, mode, count, tests, negative = line.split("|")
            records.append({"task_id": task_id, "mode": mode, "test_count": int(count), "tests_exit": int(tests), "negative_exit": int(negative)})
    if mount_hash != host_mount_hash:
        _fail("grader_mount_hash_mismatch", f"host={host_mount_hash} docker={mount_hash}")
    expected_ids = {case.task_id for case in TASKS} | {
        "domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"
    }
    if {row["task_id"] for row in records} != expected_ids or len(records) != 86:
        _fail("test_discovery_failed", f"records={len(records)} ids={len({row['task_id'] for row in records})}")
    failed_records = [
        row for row in records
        if row["test_count"] != 2 or row["tests_exit"] != 0 or row["negative_exit"] != 2
    ]
    if failed_records:
        _fail("reference_or_negative_tests_failed", json.dumps(failed_records, sort_keys=True))
    inspect = subprocess.run(["docker", "image", "inspect", SANITY_IMAGE, "--format", "{{.Id}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    compiler = subprocess.run(["docker", "run", "--rm", "--network", "none", SANITY_IMAGE, "c++", "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    cmake = subprocess.run(["docker", "run", "--rm", "--network", "none", SANITY_IMAGE, "cmake", "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    compiler_identity = subprocess.run(["docker", "run", "--rm", "--network", "none", SANITY_IMAGE, "sh", "-lc", "p=$(command -v c++); printf '%s|' \"$p\"; sha256sum \"$p\" | cut -d' ' -f1"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if inspect.returncode or compiler.returncode or cmake.returncode or compiler_identity.returncode:
        _fail("grader_identity_unavailable", (inspect.stderr + compiler.stderr + cmake.stderr + compiler_identity.stderr)[-2000:])
    compiler_path, compiler_binary_hash = compiler_identity.stdout.strip().split("|", 1)
    receipt = {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network_policy": "none",
        "image": SANITY_IMAGE,
        "image_id": inspect.stdout.strip(),
        "compiler_version": compiler.stdout.splitlines()[0],
        "compiler_path": compiler_path,
        "compiler_binary_hash": "sha256:" + compiler_binary_hash,
        "cmake_version": cmake.stdout.splitlines()[0],
        "verifier_policy_hash": _sha256(DOCKER_SCRIPT.encode()),
        "owner_hash": _sha256(Path(__file__).read_bytes()),
        "family_tree_hash": _tree_hash(out),
        "host_mount_hash": host_mount_hash,
        "docker_mount_hash": mount_hash,
        "normal_records": 43,
        "sanitizer_records": 43,
        "negative_records": 86,
        "records": records,
        "core_preflight": core,
        "command": command,
    }
    _write_json(out / ".state/docker-sanity-receipt.json", receipt)
    for case in TASKS:
        task_records = [row for row in records if row["task_id"] == case.task_id]
        root = out / case.task_id
        prompt = build_prompt(load_task(root))
        _write_json(out / ".state/receipts" / f"{case.task_id}.json", {
            "schema_version": 1,
            "task_id": case.task_id,
            "status": "local_family_verified_pending_fresh_audit",
            "disposition": "train-candidate-local-only",
            "tree_hash": _tree_hash(root),
            "prompt_hash": _sha256(prompt.encode()),
            "starter_header_hash": _sha256((root / f"{case.task_id}.h").read_bytes()),
            "starter_source_hash": _sha256((root / f"{case.task_id}.cpp").read_bytes()),
            "reference_header_hash": _sha256((root / ".meta/example.h").read_bytes()),
            "reference_hash": _sha256((root / ".meta/example.cpp").read_bytes()),
            "visible_tests_hash": _sha256((root / "task_visible_test.cpp").read_bytes()),
            "tests_hash": _sha256((root / ".meta/task_hidden_test.cpp").read_bytes()),
            "negative_hash": _sha256((root / ".meta/negative_false_substitute.cpp").read_bytes()),
            "config_hash": _sha256((root / ".meta/config.json").read_bytes()),
            "provenance_hash": _sha256((root / ".meta/provenance.json").read_bytes()),
            "cmake_hash": _sha256((root / "CMakeLists.txt").read_bytes()),
            "curriculum_hash": _sha256(CURRICULUM.read_bytes()),
            "spec_hash": _sha256(FAMILY_SPEC.read_bytes()),
            "owner_hash": receipt["owner_hash"],
            "image_id": receipt["image_id"],
            "compiler_path": receipt["compiler_path"],
            "compiler_binary_hash": receipt["compiler_binary_hash"],
            "verifier_policy_hash": receipt["verifier_policy_hash"],
            "network_policy": "none",
            "normal_sanitizer_records": task_records,
            "result_hash": _sha256(json.dumps(task_records, sort_keys=True, separators=(",", ":")).encode()),
            "prompt_boundary": "pass",
            "family_screen": "pass",
            "benchmark_screen": "pass",
            "dataset_handoff": "not_requested",
        })
    return receipt


HOST_VERIFY_POLICY = (
    "host-verify-v1: for every retained root and every adversarial control, "
    "copy the emitted tree, substitute the reference over the starter, "
    "configure a clean C++17 normal build and a separate fresh ASan/UBSan "
    "build with the host compiler and the explicit Unix Makefiles generator, "
    "require exactly two discovered CTest tests (visible and hidden) passing "
    "in each mode, and require the compiled negative false substitute to "
    "execute and exit 2 from a mismatched expected result in each mode."
)

HOST_CONTROL_NAMES = (
    "domain-identifier-renamed",
    "constants-policy-only",
    "opposite-end-selection",
)


def _host_tool_identity() -> dict[str, str]:
    tools = {name: shutil.which(name) for name in ("c++", "cmake", "ctest")}
    missing = sorted(name for name, path in tools.items() if not path)
    if missing:
        _fail("grader_identity_unavailable", f"host tools missing: {','.join(missing)}")
    compiler = subprocess.run(
        [tools["c++"], "--version"], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    cmake = subprocess.run(
        [tools["cmake"], "--version"], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if compiler.returncode or cmake.returncode:
        _fail("grader_identity_unavailable", (compiler.stderr + cmake.stderr)[-2000:])
    compiler_path = str(Path(tools["c++"]).resolve())
    return {
        "compiler_path": compiler_path,
        "compiler_version": compiler.stdout.splitlines()[0],
        "compiler_binary_hash": _sha256(Path(compiler_path).read_bytes()),
        "cmake_version": cmake.stdout.splitlines()[0],
    }


def _host_verify_root(task_root: Path, work_parent: Path) -> list[dict[str, object]]:
    """Build/run one root's reference and negative matrix on the host."""
    stem = next(task_root.glob("*.h")).stem
    task_id = task_root.name
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    records: list[dict[str, object]] = []
    for mode in ("normal", "sanitizer"):
        dst = work_parent / f"{task_id}-{mode}"
        shutil.copytree(task_root, dst)
        shutil.copy2(dst / ".meta/example.h", dst / f"{stem}.h")
        shutil.copy2(dst / ".meta/example.cpp", dst / f"{stem}.cpp")
        flags = (
            "-fsanitize=address,undefined -fno-omit-frame-pointer"
            if mode == "sanitizer" else ""
        )
        configure = subprocess.run(
            ["cmake", "-S", str(dst), "-B", str(dst / "build"),
             "-G", "Unix Makefiles", f"-DCMAKE_CXX_FLAGS={flags}"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=600,
        )
        if configure.returncode:
            _fail("host_verify_failed",
                  f"{task_id}:{mode}:configure:{configure.stderr[-2000:]}")
        build = subprocess.run(
            ["cmake", "--build", str(dst / "build"), "--parallel", "4"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=1200,
        )
        if build.returncode:
            _fail("host_verify_failed",
                  f"{task_id}:{mode}:build:{build.stderr[-2000:]}")
        discovery = subprocess.run(
            ["ctest", "--test-dir", str(dst / "build"), "-N"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=120,
        )
        match = re.search(r"Total Tests: (\d+)", discovery.stdout)
        count = int(match.group(1)) if match else 0
        if count != 2:
            _fail("test_discovery_failed", f"{task_id}:{mode}:count={count}")
        tests = subprocess.run(
            ["ctest", "--test-dir", str(dst / "build"), "--output-on-failure"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=600, env=env,
        )
        negative = subprocess.run(
            [str(dst / "build" / "negative_test")],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=300, env=env,
        )
        records.append({
            "task_id": task_id,
            "mode": mode,
            "test_count": count,
            "tests_exit": tests.returncode,
            "negative_exit": negative.returncode,
        })
    return records


def verify_host(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Owner host oracle: normal + fresh ASan/UBSan reference and negative runs."""
    core = verify_core(out)
    identity = _host_tool_identity()
    roots = [out / case.task_id for case in TASKS]
    roots += [out / ".state/controls" / name for name in HOST_CONTROL_NAMES]
    for root in roots:
        if not (root / ".meta/config.json").is_file():
            _fail("generator_output_drift", f"missing verify root {root}")
    scratch = EXPANSION_ROOT / ".state/generator-scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="overflow-host-verify-", dir=scratch) as temp:
        work_parent = Path(temp)
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
            for root_records in pool.map(
                lambda root: _host_verify_root(root, work_parent), roots,
            ):
                records.extend(root_records)
    expected_ids = {case.task_id for case in TASKS} | set(HOST_CONTROL_NAMES)
    if {row["task_id"] for row in records} != expected_ids or len(records) != 86:
        _fail("test_discovery_failed", f"records={len(records)}")
    failed_records = [
        row for row in records
        if row["test_count"] != 2 or row["tests_exit"] != 0 or row["negative_exit"] != 2
    ]
    if failed_records:
        _fail("reference_or_negative_tests_failed", json.dumps(failed_records, sort_keys=True))
    receipt = {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "status": "pass",
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "network_policy": "offline_host_build; no network access required",
        **identity,
        "verifier_policy": HOST_VERIFY_POLICY,
        "verifier_policy_hash": _sha256(HOST_VERIFY_POLICY.encode()),
        "owner_hash": _sha256(Path(__file__).read_bytes()),
        "family_tree_hash": _tree_hash(out),
        "normal_records": 43,
        "sanitizer_records": 43,
        "negative_records": 86,
        "records": records,
        "core_preflight": core,
    }
    _write_json(out / ".state/host-verify-receipt.json", receipt)
    return receipt


def _next_creator_cycle(state: Path) -> int:
    prior_creator_cycles = []
    for path in (state / "cycles").glob("cycle-*-creator-preflight.json"):
        match = re.fullmatch(r"cycle-(\d+)-creator-preflight\.json", path.name)
        if match:
            prior_creator_cycles.append(int(match.group(1)))
    return max(prior_creator_cycles, default=0) + 1


def creator_preflight(out: Path = DEFAULT_OUT) -> dict[str, object]:
    core = verify_core(out)
    receipt_path = out / ".state/docker-sanity-receipt.json"
    if not receipt_path.is_file():
        _fail("docker_sanity_not_completed", str(receipt_path))
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("family_tree_hash") != _tree_hash(out) or receipt.get("owner_hash") != _sha256(Path(__file__).read_bytes()):
        _fail("stale_receipt")
    receipt_ledger = [
        {"task_id": path.stem, "hash": _sha256(path.read_bytes())}
        for path in sorted((out / ".state/receipts").glob("*.json"))
    ]
    remedy_ledger = [
        {
            "finding_id": json.loads(path.read_text())["finding_id"],
            "path": path.name,
            "hash": _sha256(path.read_bytes()),
        }
        for path in sorted((out / ".state/remedy").glob("*.json"))
    ]
    audit_reports = sorted((out / ".state/audits").glob("cycle-*.json"))
    audit_ledger = [
        {"path": path.name, "hash": _sha256(path.read_bytes())}
        for path in audit_reports
    ]
    subject = {
        "family_id": FAMILY_ID,
        "tree_hash": _tree_hash(out),
        "owner_hash": _sha256(Path(__file__).read_bytes()),
        "curriculum_hash": _sha256(CURRICULUM.read_bytes()),
        "spec_hash": _sha256(FAMILY_SPEC.read_bytes()),
        "focused_test_hash": _sha256(Path(FOCUSED_TEST).read_bytes()),
        "selected_manifest_hash": _sha256((out / ".state/selected-manifest.json").read_bytes()),
        "raw_proposals_hash": _sha256((out / ".state/raw-proposals.json").read_bytes()),
        "rejected_proposals_hash": _sha256((out / ".state/rejected-proposals.json").read_bytes()),
        "source_inventory_hash": _sha256((out / ".state/source-inventory.json").read_bytes()),
        "family_screen_hash": _sha256((out / ".state/family-screen.json").read_bytes()),
        "prompt_boundary_hash": _sha256((out / ".state/prompt-boundary.json").read_bytes()),
        "lineage_screen_hash": _sha256((out / ".state/lineage-screen.json").read_bytes()),
        "benchmark_screen_hash": _sha256((out / ".state/benchmark-screen.json").read_bytes()),
        "holdout_inventory_hash": _sha256((out / ".state/holdout-inventory.json").read_bytes()),
        "docker_receipt_hash": _sha256(receipt_path.read_bytes()),
        "per_root_receipt_ledger_hash": _sha256(json.dumps(receipt_ledger, sort_keys=True, separators=(",", ":")).encode()),
        "per_root_receipt_count": len(receipt_ledger),
        "prior_audit_report_ledger_hash": _sha256(
            json.dumps(audit_ledger, sort_keys=True, separators=(",", ":")).encode()
        ),
        "prior_audit_report_count": len(audit_ledger),
        "remedy_ledger_hash": _sha256(json.dumps(remedy_ledger, sort_keys=True, separators=(",", ":")).encode()),
        "remedy_count": len(remedy_ledger),
        "root_count": 40,
    }
    subject_hash = _sha256(json.dumps(subject, sort_keys=True, separators=(",", ":")).encode())
    subject["audit_subject_hash"] = subject_hash
    _write_json(out / ".state/audit-subject.json", subject)
    cycle_number = _next_creator_cycle(out / ".state")
    cycle = {
        "schema_version": 1,
        "cycle": cycle_number,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": "creator_preflight",
        "audit_subject_hash": subject_hash,
        "subject": subject,
        "retained_ids": [case.task_id for case in TASKS],
        "rejected_proposals": ["control-domain-rename", "control-policy-only", "control-opposite-end"],
        "blocked_ids": [],
        "invalidated_evidence": [
            f"cycle-{cycle:03d} creator receipts and audit subject"
            for cycle in range(1, cycle_number)
        ],
        "closed_finding_ids_pending_fresh_audit": sorted(
            {row["finding_id"] for row in remedy_ledger}
        ),
        "creator_preflight": core,
        "terminal_status": "pending_fresh_independent_audit" if cycle_number > 1 else "pending_independent_audit",
    }
    _write_json(out / ".state/cycles" / f"cycle-{cycle_number:03d}-creator-preflight.json", cycle)
    return cycle


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--creator-preflight", action="store_true")
    args = parser.parse_args(argv)
    if args.force or not args.out.exists():
        print(json.dumps(materialize(args.out, force=args.force), sort_keys=True))
    if args.verify_core:
        print(json.dumps(verify_core(args.out), sort_keys=True))
    if args.verify_host:
        print(json.dumps(verify_host(args.out), sort_keys=True))
    if args.docker_sanity:
        print(json.dumps(docker_sanity(args.out), sort_keys=True))
    if args.creator_preflight:
        print(json.dumps(creator_preflight(args.out), sort_keys=True))
    if not any((args.force, args.verify_core, args.verify_host, args.docker_sanity, args.creator_preflight)):
        print(json.dumps(materialize(args.out), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
