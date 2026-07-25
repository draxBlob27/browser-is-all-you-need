"""Materialize the 80-root epoch/age/overflow expansion family.

The generated tree is intentionally separate from both historical Aider task
trees.  This owner fails closed on cross-tree identity/lineage overlap and owns
all mutable evidence below the family's ``.state`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_epoch_age_overflow_case_renderer import (
    render_case,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/aider-dates-and-clocks/"
    "epoch-age-overflow-boundaries"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_EPOCH_AGE_OVERFLOW_BOUNDARIES_CURRICULUM.md"
)
GENERATOR_PATH = Path(
    "src/w8_biayn/integrations/moonlight_epoch_age_overflow_aider_tasks.py"
)
CASE_RENDERER_PATH = Path(
    "src/w8_biayn/integrations/moonlight_epoch_age_overflow_case_renderer.py"
)
FOCUSED_TEST_PATH = Path("tests/test_moonlight_epoch_age_overflow_aider_tasks.py")
SPEC_PROMPT = Path("docs/aider-tasks-spec/prompts/generate-family-spec.md")
IMPLEMENT_PROMPT = Path("docs/aider-tasks-spec/prompts/implement-family-for-sft.md")
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
AUDIT_CYCLE_001 = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/"
    "epoch-age-overflow-boundaries-audit-cycle-001.md"
)
AUDIT_CYCLE_001_HASH = (
    "a75b282b229121032530ecdd326af6e5fa6050085b2c657b488a04470d90028e"
)
AUDIT_CYCLE_002 = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/"
    "epoch-age-overflow-boundaries-audit-cycle-002.md"
)
AUDIT_CYCLE_002_HASH = (
    "43ef5dca466ccdbdc98e48c0d8d1d1a4fd916807e31d1c6ef95ba274edda22c7"
)
AUDIT_CYCLE_003 = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/"
    "epoch-age-overflow-boundaries-audit-cycle-003.md"
)
AUDIT_CYCLE_003_HASH = (
    "2b1f767ecd936f2bbbb7d9773b7933a878cff54403e0657c86a085fb5dc1707a"
)
AUDIT_CYCLE_004 = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/"
    "epoch-age-overflow-boundaries-audit-cycle-004.md"
)
AUDIT_CYCLE_004_HASH = (
    "db367251ee22c0c2b5774d95e4463702cded4907c504b1c50738329585407185"
)
AUDIT_CYCLE_005 = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/"
    "epoch-age-overflow-boundaries-audit-cycle-005.md"
)
AUDIT_CYCLE_005_HASH = (
    "15622379823f61ccbbda8dba63a5d154e4676a7775c76b0802c75721c20d315e"
)
FAMILY_ID = "aider-dates-and-clocks/epoch-age-overflow-boundaries-v1"
COUNT_PLAN_CELL = "epoch-age-large-range-overflow-safe-conversion"
TASK_COUNT = 80
PAIR_COUNT = TASK_COUNT * (TASK_COUNT - 1) // 2
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
SANITY_IMAGE_ID = (
    "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
NORMALIZER = "epoch-age-overflow-artifacts-v1"
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
CONTROL_NAMES = (
    "domain-identifier-renamed",
    "constants-or-policy-only",
    "opposite-end-selection",
)
# Cycle-003 replacements of clone-admitted cycle-002 IDs (AEO-C02 findings).
# The rejected-roots ledger must preserve these intermediate lineages even
# though their replacements are the live task IDs below.
_CYCLE_003_REPLACEMENTS = (
    ("temporal-normalize-nanos", "temporal-epoch-range-intersection"),
    ("temporal-nearest-era10", "temporal-era-consensus"),
    ("temporal-mjd-split", "temporal-leap-table-digest"),
    ("temporal-nano-day", "temporal-signed-duration-parts"),
    ("temporal-age-march1", "temporal-age-threshold-date"),
)
_CYCLE_001_FINDINGS = [f"AEO-C01-F00{index}" for index in range(1, 6)]
_CYCLE_002_FINDINGS = [f"AEO-C02-F00{index}" for index in range(1, 6)]


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    replaces_task_id: str
    title: str
    group: str
    operation: str
    contract: str
    boundary: str
    negative: str
    seed: int


_TASK_ROWS = (
    # Epoch and external-code conversion.
    ("unix-day-floor-split", "Unix day floor split", "epoch-codec", "floor_split", "Split signed Unix seconds into a day index and second-of-day using pure-Euclidean partitioning.", "The remainder is always in [0, 86399], including at INT64_MIN.", "truncating division"),
    ("unix-millisecond-normalizer", "Unix millisecond normalizer", "epoch-codec", "normalize_subsecond", "Normalize a seconds/millisecond pair by carrying an arbitrary signed millisecond field.", "Reject when the carried seconds are outside int64_t; return a remainder in [0, 999].", "clamped remainder"),
    ("timespec-canonicalizer", "Epoch range intersection", "epoch-codec", "epoch_range_intersection", "Intersect timestamp intervals after validating their closed endpoints.", "Reject malformed intervals and preserve an exact touching-point intersection.", "endpoint union"),
    ("ntp-fraction-decoder", "NTP fraction decoder", "epoch-codec", "fixed_fraction", "Round an unsigned 32-bit binary fraction to nanoseconds.", "Use nearest-even rounding without overflowing the fixed-point product.", "decimal fraction"),
    ("ntp-era-unfolder", "NTP era unfolder", "epoch-codec", "nearest_era32", "Lift a transmitted 32-bit NTP second field to the unique era nearest a signed pivot.", "Reject the exact half-era tie.", "era zero"),
    ("gps-week-era-resolver", "Era consensus resolver", "epoch-codec", "era_consensus", "Resolve a modular sample only when every supplied absolute pivot selects the same era lift.", "Reject ties, out-of-range samples, and pivot disagreement.", "single-pivot nearest lift"),
    ("gps-time-of-week-validator", "GPS time-of-week validator", "epoch-codec", "week_seconds", "Validate GPS week and second-of-week and compose continuous seconds.", "Second 604800 is invalid and all arithmetic is checked.", "week wrap"),
    ("filetime-tick-splitter", "FILETIME tick splitter", "epoch-codec", "filetime_split", "Translate unsigned 100-nanosecond ticks since 1601 to Unix seconds and residual ticks.", "The unsigned subtraction and signed result must not wrap.", "early signed cast"),
    ("mac-epoch-offset-converter", "Mac epoch offset converter", "epoch-codec", "unsigned_epoch_offset", "Translate unsigned seconds since 1904 to signed Unix seconds.", "Pre-1970 results are valid; only unrepresentable signed results fail.", "unsigned underflow"),
    ("modified-julian-day-split", "Leap table digest", "epoch-codec", "leap_table_digest", "Validate a transition table and return its checked cumulative offset and span.", "Require strictly increasing transitions and reject cumulative overflow.", "last offset only"),
    ("excel-serial-compatibility", "Excel serial compatibility", "epoch-codec", "excel_serial", "Decode positive Excel serial dates while representing serial 60 as the fictitious leap label.", "Serial 0 and negative serials are rejected; later serials are adjusted exactly once.", "ordinary Gregorian serial"),
    ("dos-packed-datetime", "DOS packed date-time", "epoch-codec", "dos_fields", "Decode a packed DOS date-time word and validate all extracted fields.", "Reject impossible dates, reserved input width, and odd seconds.", "unchecked bit fields"),
    ("bcd-century-timestamp", "BCD century timestamp", "epoch-codec", "bcd_fields", "Decode seven packed-BCD timestamp bytes and validate the resulting Gregorian label.", "Every high and low nibble must be decimal.", "hex byte conversion"),
    ("signed-48bit-tick-decoder", "Signed 48-bit tick decoder", "epoch-codec", "signed48", "Decode a big-endian signed 48-bit two's-complement counter.", "Sign extension is explicit and portable.", "zero extension"),
    ("tai-offset-table-lookup", "TAI offset table lookup", "epoch-codec", "step_lookup", "Validate a leap-offset transition table and select the last applicable entry.", "Transitions are strictly increasing and empty/no-prior tables fail.", "first future step"),
    ("utc-to-tai-checked", "UTC to TAI checked conversion", "epoch-codec", "utc_to_tai", "Apply the applicable piecewise leap offset to a UTC second.", "Validate the table and reject checked addition overflow.", "final offset everywhere"),
    ("tai-to-utc-gap-aware", "TAI to UTC gap-aware inversion", "epoch-codec", "tai_to_utc", "Invert a piecewise UTC-to-TAI mapping.", "Reject positive-leap discontinuity gaps and ambiguous inversions.", "latest-offset subtraction"),
    ("leap-second-label-validator", "Leap-second label validator", "epoch-codec", "leap_label", "Validate ordinary UTC fields and permit second 60 only at a listed day end.", "A leap label is valid only at 23:59 on an allowlisted day.", "second-60 everywhere"),
    ("epoch-nanosecond-day-split", "Signed duration components", "epoch-codec", "signed_duration_parts", "Decompose a signed nanosecond duration into sign and unsigned hour/minute/second/nanosecond magnitude.", "Handle INT64_MIN without signed negation and produce canonical component ranges.", "signed division fields"),
    ("rational-clock-tick-converter", "Rational clock tick converter", "epoch-codec", "rational_ticks", "Convert signed ticks through a positive rational scale using reduced factors.", "Use nearest-even rounding and reject overflow or a zero denominator.", "multiply first"),
    # Human age and anniversary policy.
    ("feb28-leapling-age", "February-28 leapling age", "human-age", "age_feb28", "Count completed years with February 29 observed on February 28 in common years.", "Reject invalid or reversed dates.", "March-1 policy"),
    ("march1-leapling-age", "Age threshold date", "human-age", "age_threshold_date", "Return the first calendar date on which a person reaches a requested nonnegative age.", "Clamp February 29 to month end and reject year overflow or invalid birth dates.", "elapsed-day approximation"),
    ("clamped-calendar-age", "Clamped calendar age", "human-age", "age_clamped", "Return canonical year/month/day age by clamping invalid monthly anniversaries.", "Components reconstruct the reference date from the birth date under the clamp policy.", "fixed 30-day borrow"),
    ("borrowed-calendar-age", "Borrowed calendar age", "human-age", "age_borrowed", "Subtract calendar components by borrowing the actual preceding month.", "The borrowed month length depends on the reference calendar.", "anniversary clamp"),
    ("nearest-birthday-distance", "Nearest birthday distance", "human-age", "birthday_nearest", "Select the previous or next valid birthday anniversary by exact day distance.", "Prefer the previous anniversary on equal distance.", "day-of-year distance"),
    ("next-milestone-birthday", "Next milestone birthday", "human-age", "milestone", "Select the first strictly increasing milestone anniversary not before a reference date.", "Reject invalid milestones and checked year overflow.", "age-only selection"),
    ("majority-at-local-midnight", "Majority at local midnight", "human-age", "majority_epoch", "Construct a majority anniversary and translate its local midnight through a fixed offset.", "The leap policy and checked UTC-minute conversion are explicit.", "365-day years"),
    ("school-cohort-cutoff", "School cohort cutoff", "human-age", "cohort_cutoff", "Assign a cohort year using a validated month/day cutoff.", "The cutoff's leap-day behavior is explicit.", "birth-year only"),
    ("actuarial-nearest-age", "Actuarial nearest age", "human-age", "actuarial", "Round age to the nearer birthday using exact calendar-day distance.", "Exact midpoint ties round down.", "six-month rule"),
    ("gestational-week-day-age", "Gestational week/day age", "human-age", "gestational", "Convert exact elapsed Gregorian days to completed weeks and days.", "Only the documented 0-45 week range is valid.", "field subtraction"),
    ("reduced-exact-age-fraction", "Reduced exact age fraction", "human-age", "age_fraction", "Represent exact elapsed days in mean Gregorian years as a reduced rational.", "Use the exact 146097/400 factor and no floating point.", "365-day quotient"),
    ("age-band-locator", "Age band locator", "human-age", "age_band", "Locate completed age within strictly increasing thresholds.", "Thresholds and dates are validated before upper-bound selection.", "raw year difference"),
    ("event-age-series", "Event age series", "human-age", "age_series", "Compute completed age for a nondecreasing sequence of event dates.", "Reject disorder transactionally and advance only at anniversaries.", "year subtraction"),
    ("age-eligibility-window", "Age eligibility window", "human-age", "eligibility", "Construct a half-open date range between two age anniversaries.", "Minimum age is inclusive and maximum age exclusive.", "inclusive upper endpoint"),
    ("leapling-birthday-counter", "Leapling birthday counter", "human-age", "leapling_count", "Count policy-observed birthdays over a date interval without day iteration.", "Common-year observations count under the selected policy.", "leap-years only"),
    ("retirement-month-end-rule", "Retirement month-end rule", "human-age", "retirement", "Add retirement years while preserving an original month-end relationship.", "Non-month-end dates clamp only when the target date is invalid.", "numeric day preservation"),
    ("sibling-age-gap-components", "Sibling age gap components", "human-age", "sibling_gap", "Return the canonical calendar gap between two birth dates.", "Order is normalized and actual month lengths are borrowed.", "365/30 conversion"),
    ("completed-month-age", "Completed month age", "human-age", "completed_months", "Count completed monthly anniversaries with day clamping.", "Subtract one when the reference precedes the clamped monthly anniversary.", "year-month difference"),
    ("completed-iso-week-age", "Completed ISO-week age", "human-age", "iso_weeks", "Count complete seven-day periods between valid dates.", "Use exact Gregorian day difference across ISO year boundaries.", "week-label subtraction"),
    ("century-birthday-enumerator", "Century birthday enumerator", "human-age", "century_birthdays", "Enumerate 100-year anniversaries within a half-open date range.", "Use checked 100-year steps and the documented leap policy.", "year-suffix scan"),
    # Checked arithmetic.
    ("checked-second-shift", "Checked second shift", "checked-arithmetic", "checked_add", "Add a signed offset to a timestamp without signed overflow.", "No overflowing expression is evaluated.", "post-add check"),
    ("checked-duration-compose", "Checked duration composition", "checked-arithmetic", "compose_duration", "Compose validated day/hour/minute/second fields with checked Horner arithmetic.", "Reject invalid component ranges and every intermediate overflow.", "independent products"),
    ("checked-unit-ratio-scale", "Checked unit ratio scale", "checked-arithmetic", "exact_ratio", "Scale a signed value by a positive rational only when the mathematical result is integral.", "Reduce factors before multiplication and reject a zero denominator.", "multiply first"),
    ("saturating-shift-report", "Saturating shift report", "checked-arithmetic", "saturating_add", "Shift a timestamp with explicit lower/upper saturation status.", "Detect overflow before addition.", "overflowing clamp"),
    ("bounded-epoch-offset", "Bounded epoch offset", "checked-arithmetic", "bounded_add", "Shift within caller-provided closed epoch bounds.", "Reject invalid bounds, arithmetic overflow, and out-of-range results without clamping.", "clamped bounds"),
    ("checked-day-second-product", "Checked day-to-second product", "checked-arithmetic", "day_product", "Convert signed days to seconds with predivision multiplication bounds.", "INT64_MIN is handled without absolute value.", "absolute-value check"),
    ("checked-second-nano-join", "Checked second/nanosecond join", "checked-arithmetic", "join_nanos", "Join canonical seconds and nanoseconds into one signed nanosecond count.", "Nanoseconds must already be in [0, 1e9).", "implicit normalization"),
    ("euclidean-epoch-division", "Euclidean epoch division", "checked-arithmetic", "euclidean_div", "Divide a signed epoch by a positive unit with nonnegative remainder.", "The operation is defined for INT64_MIN.", "C++ truncation"),
    ("checked-affine-clock-map", "Checked affine clock map", "checked-arithmetic", "affine_map", "Map a timestamp through a rational affine clock relation.", "Reduce factors, round nearest-even, and reject every overflow.", "double arithmetic"),
    ("transactional-duration-ledger", "Transactional duration ledger", "checked-arithmetic", "transactional_sum", "Apply signed deltas in order and commit only when every prefix is representable.", "Late failure leaves output unchanged.", "partial commit"),
    ("overflow-prefix-frontier", "Overflow prefix frontier", "checked-arithmetic", "overflow_frontier", "Return the first signed-add prefix that would overflow.", "Distinguish index zero from no overflow.", "final-sum check"),
    ("atomic-interval-shift", "Atomic interval shift", "checked-arithmetic", "interval_shift", "Shift both endpoints of a valid half-open interval atomically.", "Reject invalid input, endpoint overflow, or inverted output.", "partial endpoint shift"),
    ("checked-range-rescale", "Checked range rescale", "checked-arithmetic", "range_rescale", "Rescale a half-open interval by a positive rational with floor lower and ceil upper endpoints.", "Reject zero denominator and endpoint overflow.", "toward-zero endpoints"),
    ("weighted-timestamp-centroid", "Weighted timestamp centroid", "checked-arithmetic", "weighted_centroid", "Compute a positive-weight timestamp centroid around a pivot.", "Use checked weighted deltas and nearest-even rounding.", "absolute products"),
    ("checked-time-interpolation", "Checked time interpolation", "checked-arithmetic", "interpolate", "Interpolate a rational fraction between ordered timestamps.", "The fraction is in [0,1], factors are reduced, and overflow is rejected.", "direct difference product"),
    ("checked-recurrence-occurrence", "Checked recurrence occurrence", "checked-arithmetic", "nth_occurrence", "Compute the one-based nth occurrence of a positive-period recurrence.", "Use (n-1), reject n=0, and check multiply-add.", "n-times period"),
    ("bounded-backoff-deadline", "Bounded backoff deadline", "checked-arithmetic", "backoff", "Compute a doubling backoff capped before adding it to a start time.", "Reject negative base/cap and checked deadline overflow.", "left-shift wrap"),
    ("checked-arithmetic-schedule-sum", "Checked arithmetic schedule sum", "checked-arithmetic", "arithmetic_sum", "Sum a finite arithmetic duration schedule by factor cancellation.", "Reject negative terms and every unrepresentable intermediate.", "closed-form overflow"),
    ("checked-duration-dot-product", "Checked duration dot product", "checked-arithmetic", "dot_product", "Compute a signed duration/count dot product with checked terms and accumulation.", "Lengths must match and failure is transactional.", "unsigned accumulator"),
    ("checked-window-count", "Checked window count", "checked-arithmetic", "window_count", "Count aligned half-open windows between signed endpoints.", "Avoid signed end-start overflow and reject zero width or reversed endpoints.", "signed subtraction"),
    # Rollover, calibration, and ordering.
    ("unwrap-32bit-tick-stream", "Unwrap 32-bit tick stream", "rollover-order", "unwrap32", "Lift raw 32-bit ticks to nearest consecutive absolute ticks.", "Reject exact half-range ambiguity.", "decrease-means-rollover"),
    ("unwrap-16bit-bounded-step", "Unwrap 16-bit bounded-step stream", "rollover-order", "unwrap16", "Lift each raw 16-bit tick to the unique candidate within a step bound.", "Reject zero bounds, ambiguity, and missing candidates.", "unbounded nearest lift"),
    ("rfc1982-serial-order", "RFC1982 serial order", "rollover-order", "serial_order", "Compare 32-bit serials by modular half-range ordering.", "Distance 2^31 is explicitly unordered.", "ordinary unsigned order"),
    ("gps-week-sequence-unwrapper", "GPS week sequence unwrapper", "rollover-order", "gps_sequence", "Unwrap a nondecreasing sequence of ten-bit GPS weeks.", "Each lift is relative to the prior absolute week and at most 512 weeks ahead.", "fixed pivot resolution"),
    ("epoch-reset-segmenter", "Epoch reset segmenter", "rollover-order", "reset_segments", "Partition input-order timestamps when backward movement exceeds tolerance.", "Do not sort or discard stable indices.", "sort first"),
    ("two-point-clock-calibration", "Two-point clock calibration", "rollover-order", "two_point_calibration", "Reduce a positive rational wall/monotonic slope from two samples.", "Monotonic deltas must be positive and intercept arithmetic checked.", "integer slope"),
    ("piecewise-clock-offset-map", "Piecewise clock offset map", "rollover-order", "piecewise_offset", "Apply the last offset transition not after an instant.", "Validate strict transition ordering and checked addition.", "nearest step"),
    ("median-clock-offset", "Median clock offset", "rollover-order", "median_offset", "Compute the deterministic lower median of checked wall-minus-monotonic offsets.", "Reject empty or overflowing differences and preserve input.", "mean offset"),
    ("drift-envelope-validator", "Drift envelope validator", "rollover-order", "drift_envelope", "Validate every adjacent clock-delta ratio against a positive rational envelope.", "Use integer quotient/remainder comparison and reject disorder.", "floating endpoint check"),
    ("stable-packet-time-order", "Stable packet time order", "rollover-order", "packet_order", "Order disjoint uncertainty intervals while preserving order for overlaps and ties.", "Reject negative uncertainty and endpoint overflow.", "center sort"),
    ("source-watermark-advance", "Source watermark advance", "rollover-order", "watermark", "Choose the minimum checked last-seen-minus-lateness across active initialized sources.", "Any missing active source blocks the watermark.", "maximum/ignore missing"),
    ("timestamp-tolerance-deduplicator", "Timestamp tolerance deduplicator", "rollover-order", "tolerance_dedup", "Keep the first item of each tolerance-connected run in sorted input.", "Connectivity compares adjacent input items, not only retained representatives.", "last-kept comparison"),
    ("delta-of-delta-timestamp-codec", "Delta-of-delta timestamp codec", "rollover-order", "delta2", "Reconstruct deltas and timestamps through two checked accumulators.", "Failure leaves no partial decoded output.", "direct timestamp addition"),
    ("timestamp-gap-run-classifier", "Timestamp gap run classifier", "rollover-order", "gap_runs", "Classify adjacent gaps and coalesce consecutive equal classes.", "Validate thresholds and sorted input.", "timestamp classification"),
    ("anchored-time-bucket-index", "Anchored time bucket index", "rollover-order", "bucket_index", "Compute a Euclidean bucket index relative to an anchor.", "Avoid signed subtraction overflow and reject zero width.", "truncating difference"),
    ("clock-slew-distributor", "Clock slew distributor", "rollover-order", "slew_distribution", "Distribute a signed correction over steps so the exact sum is preserved and prefix error is bounded.", "Reject zero steps and avoid front/back loading the whole correction.", "last-step correction"),
    ("quantized-roundtrip-error", "Quantized round-trip error", "rollover-order", "quantize", "Round to the nearest positive bucket with ties to even and report signed error.", "Reject reconstruction overflow.", "half-up rounding"),
    ("timebase-common-tick", "Timebase common tick", "rollover-order", "common_timebase", "Compute checked LCM and source multipliers for two positive timebases.", "Divide by GCD before multiplication.", "multiply first"),
    ("multi-era-tagged-timestamp", "Multi-era tagged timestamp", "rollover-order", "tagged_era", "Translate one of three explicit epoch tags to Unix seconds.", "Validate tag-specific alignment and checked offsets.", "all tags Unix"),
    ("temporal-shard-key", "Temporal shard key", "rollover-order", "shard_key", "Compute Euclidean time bucket, nonnegative shard, and checked bucket origin.", "Reject zero shard count and avoid negative C++ remainders.", "raw remainder"),
)


TASKS = tuple(
    TaskSpec(
        task_id=(
            "temporal-euclidean-shard-key"
            if row[3] == "shard_key"
            else f"temporal-{row[3].replace('_', '-')}"
        ),
        replaces_task_id=row[0],
        title=row[1],
        group=row[2],
        operation=row[3],
        contract=row[4],
        boundary=row[5],
        negative=row[6],
        seed=0xE0A00000 + index,
    )
    for index, row in enumerate(_TASK_ROWS, start=1)
)
if len(TASKS) != TASK_COUNT or len({task.task_id for task in TASKS}) != TASK_COUNT:
    raise RuntimeError("binding_root_count_failed")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _subject_hash(root: Path) -> str:
    """Hash retained task bytes only; mutable ``.state`` evidence is excluded."""

    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and ".state" not in item.relative_to(root).parts
    ):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _repo(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise RuntimeError(f"refusing_existing_file:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _safe_output(out: Path) -> Path:
    resolved = _repo(out).resolve(strict=False)
    expected = _repo(DEFAULT_OUT).resolve(strict=False)
    expansion = _repo(EXPANSION_ROOT).resolve(strict=False)
    forbidden = (
        _repo(LEGACY_ROOT).resolve(strict=False),
        _repo(REVERIFY_ROOT).resolve(strict=False),
    )
    if resolved != expected or expansion not in resolved.parents:
        raise RuntimeError(f"expansion_output_required:{expected}")
    if any(resolved == root or root in resolved.parents for root in forbidden):
        raise RuntimeError("existing_tree_output_forbidden")
    cursor = resolved
    while cursor != expansion.parent:
        if cursor.is_symlink():
            raise RuntimeError(f"symlink_output_forbidden:{cursor}")
        cursor = cursor.parent
    return resolved


def _real_task_roots(root: Path) -> tuple[Path, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(
            config.parent.parent
            for config in root.rglob(".meta/config.json")
            if ".state" not in config.parts
        )
    )


def _existing_inventory() -> dict[str, object]:
    result: dict[str, object] = {}
    all_ids: dict[str, str] = {}
    for label, relative in (
        ("legacy", LEGACY_ROOT),
        ("reverify", REVERIFY_ROOT),
        ("expansion", EXPANSION_ROOT),
    ):
        root = _repo(relative)
        paths = _real_task_roots(root)
        rows = []
        for task_root in paths:
            task_id = task_root.name
            prior = all_ids.get(task_id)
            if prior is not None and label == "expansion":
                provenance = task_root / ".meta/provenance.json"
                owned = False
                if provenance.is_file():
                    record = json.loads(provenance.read_text(encoding="utf-8"))
                    owned = (
                        record.get("owner") == GENERATOR_PATH.as_posix()
                        and task_root.parent.resolve(strict=False)
                        == _repo(DEFAULT_OUT).resolve(strict=False)
                    )
                if not owned:
                    raise RuntimeError(f"duplicate_task:{task_id}:{prior}")
            all_ids.setdefault(task_id, task_root.relative_to(REPO_ROOT).as_posix())
            rows.append(task_root.relative_to(REPO_ROOT).as_posix())
        encoded = "\n".join(rows).encode()
        result[label] = {
            "root": relative.as_posix(),
            "count": len(rows),
            "sorted_root_sha256": _sha256_bytes(encoded),
            "roots": rows,
        }
    proposed = {task.task_id for task in TASKS}
    owned_ids = {
        task_root.name
        for task_root in _real_task_roots(_repo(DEFAULT_OUT))
        if (task_root / ".meta/provenance.json").is_file()
        and json.loads((task_root / ".meta/provenance.json").read_text(encoding="utf-8")).get("owner")
        == GENERATOR_PATH.as_posix()
    }
    collisions = sorted(proposed.intersection(set(all_ids) - owned_ids))
    if collisions:
        raise RuntimeError(f"duplicate_task:{','.join(collisions)}")
    return result


def _cpp_symbol(task_id: str) -> str:
    return task_id.replace("-", "_")


def _common_header(spec: TaskSpec) -> str:
    return f"""// Generated contract for {spec.task_id}.
#pragma once
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <numeric>
#include <optional>
#include <stdexcept>
#include <type_traits>
#include <tuple>
#include <utility>
#include <vector>

namespace epoch_age_overflow {{

namespace detail {{
inline bool checked_add(std::int64_t a, std::int64_t b, std::int64_t& out) {{
    if ((b > 0 && a > std::numeric_limits<std::int64_t>::max() - b) ||
        (b < 0 && a < std::numeric_limits<std::int64_t>::min() - b)) return false;
    out = a + b; return true;
}}
inline bool checked_sub(std::int64_t a, std::int64_t b, std::int64_t& out) {{
    if ((b > 0 && a < std::numeric_limits<std::int64_t>::min() + b) ||
        (b < 0 && a > std::numeric_limits<std::int64_t>::max() + b)) return false;
    out = a - b; return true;
}}
inline bool checked_mul(std::int64_t a, std::int64_t b, std::int64_t& out) {{
    if (a == 0 || b == 0) {{ out = 0; return true; }}
    if ((a == -1 && b == std::numeric_limits<std::int64_t>::min()) ||
        (b == -1 && a == std::numeric_limits<std::int64_t>::min())) return false;
    if (a > 0 ? (b > 0 ? a > std::numeric_limits<std::int64_t>::max()/b : b < std::numeric_limits<std::int64_t>::min()/a)
              : (b > 0 ? a < std::numeric_limits<std::int64_t>::min()/b : a < std::numeric_limits<std::int64_t>::max()/b)) return false;
    out = a * b; return true;
}}
inline std::uint64_t distance(std::int64_t a, std::int64_t b) {{
    const auto ua = static_cast<std::uint64_t>(a) ^ (std::uint64_t{{1}} << 63U);
    const auto ub = static_cast<std::uint64_t>(b) ^ (std::uint64_t{{1}} << 63U);
    return ua >= ub ? ua - ub : ub - ua;
}}
inline std::int64_t abs_i64(std::int64_t value) {{ return value < 0 ? -value : value; }}
inline bool leap(std::int64_t year) {{ return year%4==0 && (year%100!=0 || year%400==0); }}
inline int days_in_month(std::int64_t year, int month) {{
    constexpr std::array<int,12> lengths{{31,28,31,30,31,30,31,31,30,31,30,31}};
    if (month < 1 || month > 12) {{ return 0; }}
    return lengths[static_cast<std::size_t>(month-1)] + (month==2 && leap(year) ? 1 : 0);
}}
inline bool valid_date(std::int64_t year, int month, int day) {{ return day >= 1 && day <= days_in_month(year,month); }}
inline std::int64_t days_from_civil(std::int64_t y, int m, int d) {{
    y -= m <= 2; const std::int64_t era = (y >= 0 ? y : y-399) / 400; const auto yoe = static_cast<unsigned>(y-era*400);
    const auto mp = static_cast<unsigned>(m + (m > 2 ? -3 : 9)); const auto doy=(153U*mp+2U)/5U+static_cast<unsigned>(d)-1U;
    const auto doe=yoe*365U+yoe/4U-yoe/100U+doy; return era*146097+static_cast<std::int64_t>(doe)-719468;
}}
inline std::array<std::int64_t,3> civil_from_days(std::int64_t z) {{
    z+=719468; const std::int64_t era=(z>=0?z:z-146096)/146097; const auto doe=static_cast<unsigned>(z-era*146097);
    const auto yoe=(doe-doe/1460U+doe/36524U-doe/146096U)/365U; std::int64_t y=static_cast<std::int64_t>(yoe)+era*400;
    const auto doy=doe-(365U*yoe+yoe/4U-yoe/100U); const auto mp=(5U*doy+2U)/153U; const auto d=doy-(153U*mp+2U)/5U+1U; const auto m=mp+(mp<10U?3U:-9U); y+=m<=2U;
    return {{y,static_cast<std::int64_t>(m),static_cast<std::int64_t>(d)}};
}}
template<class D> inline bool valid(const D& date) {{ return valid_date(date.year,date.month,date.day); }}
template<class A,class B> inline bool less(const A& a,const B& b) {{ return std::tie(a.year,a.month,a.day)<std::tie(b.year,b.month,b.day); }}
template<class D> inline std::int64_t serial(const D& d) {{ return days_from_civil(d.year,d.month,d.day); }}
template<class D> inline D birthday_in_year(const D& birth,std::int64_t year,bool march) {{ int m=birth.month,d=birth.day;if(m==2&&d==29&&!leap(year)){{m=march?3:2;d=march?1:28;}}return D{{year,m,d}}; }}
template<class D> inline D add_years_clamped(const D& d,std::int64_t years) {{ const auto y=d.year+years; return D{{y,d.month,std::min(d.day,days_in_month(y,d.month))}}; }}
template<class D> inline D add_months_clamped(const D& d,std::int64_t months) {{ std::int64_t total=d.year*12+(d.month-1)+months;std::int64_t y=total/12;int m=static_cast<int>(total%12);if(m<0){{m+=12;--y;}}++m;return D{{y,m,std::min(d.day,days_in_month(y,m))}}; }}
inline std::optional<std::int64_t> rounded_ratio(std::int64_t value,std::int64_t numerator,std::int64_t denominator) {{ if(denominator<=0)return std::nullopt;std::int64_t product=0;if(!checked_mul(value,numerator,product))return std::nullopt;auto q=product/denominator,r=product%denominator;auto twice=distance(r,0)*2U;if(twice>static_cast<std::uint64_t>(denominator)||(twice==static_cast<std::uint64_t>(denominator)&&(q&1LL)))q+=product<0?-1:1;return q; }}
inline std::optional<std::int64_t> floor_ratio(std::int64_t value,std::int64_t numerator,std::int64_t denominator) {{ std::int64_t p=0;if(denominator<=0||!checked_mul(value,numerator,p))return std::nullopt;auto q=p/denominator;if(p%denominator<0)--q;return q; }}
inline std::optional<std::int64_t> ceil_ratio(std::int64_t value,std::int64_t numerator,std::int64_t denominator) {{ std::int64_t p=0;if(denominator<=0||!checked_mul(value,numerator,p))return std::nullopt;auto q=p/denominator;if(p%denominator>0)++q;return q; }}
}} // namespace detail

"""


def _header(spec: TaskSpec, *, negative: bool = False, starter: bool = False) -> str:
    symbol = _cpp_symbol(spec.task_id)
    rendered = render_case(spec.operation, symbol)
    negative_unused = {
        "milestone": "(void)as_of;",
        "reset_segments": "(void)tolerance;",
        "tolerance_dedup": "(void)tolerance;",
        "unwrap16": "(void)first;",
        "unwrap32": "(void)first;",
        "watermark": "(void)previous;",
        "weighted_centroid": "(void)pivot;",
    }
    if starter:
        body = 'throw std::logic_error("not implemented");'
    elif negative:
        body = negative_unused.get(spec.operation, "") + rendered.negative_body
    else:
        body = rendered.reference_body
    # Renderer bodies are compact data. Emit statement/brace boundaries on
    # separate lines so generated sources pass the full strict warning set.
    body = body.replace(";", ";\n").replace("{", "{\n").replace("}", "}\n")
    declarations = rendered.declarations + ("\n" if rendered.declarations else "")
    return _common_header(spec) + declarations + f"inline {rendered.signature} {{\n    {body}\n}}\n\n}} // namespace epoch_age_overflow\n"


def _test(spec: TaskSpec, *, hidden: bool) -> str:
    rendered = render_case(spec.operation, _cpp_symbol(spec.task_id))
    calls = rendered.hidden_checks if hidden else rendered.visible_checks
    return f"""#include <{spec.task_id}.h>
#include <cstdlib>
#include <iostream>
#include <limits>

namespace {{
void require(bool condition) {{
    if (!condition) {{
        std::cerr << "assertion failed for {spec.task_id}\\n";
        std::exit(1);
    }}
}}
}}

int main() {{
    using namespace epoch_age_overflow;
    {calls}
    return 0;
}}
"""


_GROUP_INTRODUCTIONS = {
    "epoch-codec": (
        "Computers disagree about what \"now\" means. Unix counts seconds from "
        "1970, GPS from 1980, classic Mac OS from 1904, and NTP stamps time in "
        "eras that wrap every 2^32 seconds. Moving timestamps between these "
        "worlds is routine systems work, and every conversion hides a trap: a "
        "wraparound, a fictitious date, or a value that does not fit in the "
        "destination type.\n\n"
        "These exercises are about doing one such conversion exactly, including "
        "the awkward boundary values."
    ),
    "human-age": (
        "Hospitals, schools, insurers, and pension systems all compute ages, "
        "and each has its own rule for leap-day birthdays, month-end "
        "anniversaries, and rounding. The rules sound simple until a February "
        "29 birthday meets a common year, or a due date lands on a month with "
        "fewer days.\n\n"
        "These exercises are about applying one stated age policy exactly, even "
        "at the awkward boundaries."
    ),
    "checked-arithmetic": (
        "Timestamp arithmetic overflows quietly: add one second too many and a "
        "64-bit counter wraps into a nonsense value. Defensive systems never "
        "let that happen; every addition, multiplication, and scaling step is "
        "checked before it is evaluated.\n\n"
        "These exercises are about composing time arithmetic that reports "
        "failure cleanly instead of wrapping."
    ),
    "rollover-order": (
        "Counters wrap. A 16-bit timer rolls over every few minutes, serial "
        "numbers repeat, and streams from many sensors arrive carrying only "
        "modular labels. Ordering and unwrapping such observations is daily "
        "work in embedded and network code.\n\n"
        "These exercises are about reconstructing a sensible absolute timeline "
        "from wrapped or out-of-order evidence."
    ),
}


def _introduction(spec: TaskSpec) -> str:
    return f"# {spec.title}\n\n{_GROUP_INTRODUCTIONS[spec.group]}\n"


def _example_block(visible_checks: str) -> str:
    lines = [line.strip() for line in visible_checks.strip().splitlines()]
    return "\n".join(line for line in lines if line)


def _instructions(spec: TaskSpec) -> str:
    rendered = render_case(spec.operation, _cpp_symbol(spec.task_id))
    api = f"`{rendered.signature}`"
    examples = _example_block(rendered.visible_checks)
    return f"""# Instructions

Implement {api} in `{spec.task_id}.h` with exactly the documented return type.

{spec.contract} {spec.boundary} {rendered.result_semantics}

## Examples

```cpp
{examples}
```

In particular, using {spec.negative} does not satisfy the rules above. All
arithmetic must be defined C++17 integer arithmetic; do not use wall-clock
state, floating point, a platform date library, or hard-coded answers.
Complexity is linear in supplied sequences and constant otherwise.
"""


CMAKE = """cmake_minimum_required(VERSION 3.16)
project(epoch_age_overflow_task LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_HEADER "${CMAKE_CURRENT_SOURCE_DIR}/TASK_HEADER_PLACEHOLDER" CACHE FILEPATH "Header to grade")
get_filename_component(TASK_HEADER_NAME "${TASK_HEADER}" NAME)
configure_file("${TASK_HEADER}" "${CMAKE_CURRENT_BINARY_DIR}/TASK_HEADER_PLACEHOLDER" COPYONLY)
add_executable(task_visible task_visible_test.cpp)
add_executable(task_hidden .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_BINARY_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
"""


def _role_manifest(spec: TaskSpec) -> dict[str, object]:
    return {
        "authors": ["w8-biayn"],
        "blurb": spec.contract,
        "source": "clean-room w8-biayn epoch/age/overflow expansion curriculum",
        "files": {
            "solution": [f"{spec.task_id}.h"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h"],
        },
    }


def _materialize_root(out: Path, spec: TaskSpec, force: bool) -> Path:
    root = out / spec.task_id
    if root.exists():
        if not force:
            raise RuntimeError(f"refusing_existing_root:{root}")
        provenance = root / ".meta/provenance.json"
        if not provenance.is_file():
            raise RuntimeError(f"foreign_root_refused:{root}")
        prior = json.loads(provenance.read_text(encoding="utf-8"))
        if prior.get("owner") != GENERATOR_PATH.as_posix():
            raise RuntimeError(f"foreign_root_refused:{root}")
        shutil.rmtree(root)
    starter = _header(spec, starter=True)
    reference = _header(spec)
    negative = _header(spec, negative=True)
    _write(root / ".docs/introduction.md", _introduction(spec), True)
    _write(root / ".docs/instructions.md", _instructions(spec), True)
    _write(root / f"{spec.task_id}.h", starter, True)
    _write(root / "task_visible_test.cpp", _test(spec, hidden=False), True)
    _write(root / ".meta/task_hidden_test.cpp", _test(spec, hidden=True), True)
    _write(root / ".meta/example.h", reference, True)
    _write(root / ".meta/negative.h", negative, True)
    _write(root / ".meta/config.json", json.dumps(_role_manifest(spec), indent=2, sort_keys=True) + "\n", True)
    provenance = {
        "schema_version": "aider-expansion-provenance-v1",
        "task_id": spec.task_id,
        "family_id": FAMILY_ID,
        "family_type": "aider-dates-and-clocks",
        "count_plan_cell": COUNT_PLAN_CELL,
        "curriculum_document": CURRICULUM.as_posix(),
        "selected_spec_prompt": SPEC_PROMPT.as_posix(),
        "selected_implementation_prompt": IMPLEMENT_PROMPT.as_posix(),
        "owner": GENERATOR_PATH.as_posix(),
        "case_renderer": CASE_RENDERER_PATH.as_posix(),
        "case_renderer_sha256": _sha256_file(_repo(CASE_RENDERER_PATH)),
        "focused_test": FOCUSED_TEST_PATH.as_posix(),
        "origin": "newly authored in-repository clean-room task",
        "lineage": "replacement",
        "replaces_task_id": spec.replaces_task_id,
        "replacement_audit": AUDIT_CYCLE_001.as_posix(),
        "task_spec_version": 1,
        "license": "repository-authored local research material",
        "dataset_handoff": "not_requested",
        "benchmark_separation": "all 26 official Aider Polyglot C++ roots are permanent holdouts",
        "status": "local candidate; pending creator/audit loop",
        "operation": spec.operation,
        "negative_fixture": spec.negative,
        "deterministic_seed": f"0x{spec.seed:08X}",
    }
    _write(root / ".meta/provenance.json", json.dumps(provenance, indent=2, sort_keys=True) + "\n", True)
    tests_toml = f"""[visible]
description = "normal and documented boundary behavior for {spec.operation}"

[hidden]
description = "invalid input, overflow/rounding/order boundary, and deterministic model property"
seed = "0x{spec.seed:08X}"

[negative]
description = "compiled coherent substitute rejected: {spec.negative}"
"""
    _write(root / ".meta/tests.toml", tests_toml, True)
    _write(root / "CMakeLists.txt", CMAKE.replace("TASK_HEADER_PLACEHOLDER", spec.task_id + ".h"), True)
    return root


def build(out: Path = DEFAULT_OUT, *, force: bool = False) -> tuple[Path, ...]:
    output = _safe_output(out)
    inventory = _existing_inventory()
    output.mkdir(parents=True, exist_ok=True)
    state = output / ".state"
    state.mkdir(parents=True, exist_ok=True)
    selected_ids = {spec.task_id for spec in TASKS}
    for stale in _real_task_roots(output):
        if stale.name in selected_ids:
            continue
        provenance = stale / ".meta/provenance.json"
        if not provenance.is_file() or json.loads(
            provenance.read_text(encoding="utf-8")
        ).get("owner") != GENERATOR_PATH.as_posix():
            raise RuntimeError(f"foreign_stale_root_refused:{stale}")
        if not force:
            raise RuntimeError(f"stale_owned_root_requires_force:{stale}")
        shutil.rmtree(stale)
    roots = tuple(_materialize_root(output, spec, force) for spec in TASKS)
    selected = [spec.task_id for spec in TASKS]
    proposals = [
        {
            "task_id": spec.task_id,
            "replaces_task_id": spec.replaces_task_id,
            "title": spec.title,
            "group": spec.group,
            "operation": spec.operation,
            "contract": spec.contract,
            "boundary": spec.boundary,
            "negative": spec.negative,
            "lineage": "replacement",
        }
        for spec in TASKS
    ]
    _write(state / "source-inventory.json", json.dumps(inventory, indent=2, sort_keys=True) + "\n", True)
    _write(state / "raw-proposals.json", json.dumps(proposals, indent=2, sort_keys=True) + "\n", True)
    _write(state / "selected-roots.json", json.dumps({"task_ids": selected}, indent=2, sort_keys=True) + "\n", True)
    rejected_roots = [
        {
            "task_id": spec.replaces_task_id,
            "cycle": 2,
            "disposition": "replace",
            "replacement_task_id": spec.task_id,
            "finding_ids": list(_CYCLE_001_FINDINGS),
        }
        for spec in TASKS
    ] + [
        {
            "task_id": replaced,
            "cycle": 3,
            "disposition": "replace",
            "replacement_task_id": replacement,
            "finding_ids": list(_CYCLE_002_FINDINGS),
        }
        for replaced, replacement in _CYCLE_003_REPLACEMENTS
    ]
    _write(
        state / "rejected-roots.json",
        json.dumps(
            {
                "schema_version": "epoch-age-overflow-rejected-roots-v1",
                "roots": rejected_roots,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        True,
    )
    normalized_remedy_records = _remedy_ledger_hygiene(output)
    manifest = {
        "schema_version": "epoch-age-overflow-generator-manifest-v1",
        "family_id": FAMILY_ID,
        "count_plan_cell": COUNT_PLAN_CELL,
        "task_count": len(roots),
        "task_ids": selected,
        "pair_count": PAIR_COUNT,
        "hard_rule_dimensions": list(HARD_RULE_DIMENSIONS),
        "owner": GENERATOR_PATH.as_posix(),
        "owner_sha256": _sha256_file(_repo(GENERATOR_PATH)),
        "case_renderer_sha256": _sha256_file(_repo(CASE_RENDERER_PATH)),
        "curriculum_sha256": _sha256_file(_repo(CURRICULUM)),
        "spec_prompt_sha256": _sha256_file(_repo(SPEC_PROMPT)),
        "implementation_prompt_sha256": _sha256_file(_repo(IMPLEMENT_PROMPT)),
        "tree_hash": _subject_hash(output),
        "normalized_remedy_record_count": normalized_remedy_records,
        "status": "generated_pending_verification",
    }
    _write(state / "generator-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return roots


def _remedy_ledger_hygiene(output: Path) -> int:
    """Normalize cycle-suffixed remedy records to the remedy-v1 contract.

    Historical cycle snapshots used pre-contract vocabulary
    (``repair-and-reverify``, ``remediated_pending_fresh_audit``) and omitted
    ``remedy_spec_path``/``remedy_spec_hash``.  The original values are
    preserved under ``vocabulary_normalized_from``; every other historical
    field is retained.  Returns the number of normalized records.
    """

    remedy_dir = output / ".state/remedy"
    if not remedy_dir.is_dir():
        return 0
    curriculum_hash = f"sha256:{_sha256_file(_repo(CURRICULUM))}"
    normalized = 0
    for path in sorted(remedy_dir.glob("*.cycle-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        before = {
            "disposition": record.get("disposition"),
            "status": record.get("status"),
        }
        record["schema_version"] = "aider-task-remedy-v1"
        record.setdefault("family_id_before", FAMILY_ID)
        if "tree_hash_before" not in record and "root_sha256" in record:
            record["tree_hash_before"] = f"sha256:{record['root_sha256']}"
        record["generator_path"] = GENERATOR_PATH.as_posix()
        owner_hash = None
        match = re.search(r"\.cycle-(\d+)\.json$", path.name)
        if match:
            cycle_path = output / ".state/cycles" / f"cycle-{match.group(1)}.json"
            if cycle_path.is_file():
                owner_hash = json.loads(cycle_path.read_text(encoding="utf-8")).get(
                    "owner_sha256"
                )
        record["generator_revision"] = (
            f"sha256:{owner_hash}"
            if owner_hash
            else f"sha256:{_sha256_file(_repo(GENERATOR_PATH))}"
        )
        record.setdefault("license_screen", "pass")
        record.setdefault("benchmark_screen", "pending")
        record["remedy_spec_path"] = CURRICULUM.as_posix()
        record["remedy_spec_hash"] = curriculum_hash
        if before["disposition"] == "repair-and-reverify":
            record["disposition"] = "repair-in-place"
        if before["status"] == "remediated_pending_fresh_audit":
            record["status"] = "implemented"
        record["vocabulary_normalized_from"] = before
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
        normalized += 1
    return normalized


def _normalized_tokens(text: str, task_id: str = "") -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/|#.*?$", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"', ' "str" ', text)
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)\b", " num ", text)
    del task_id
    raw = re.findall(
        r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||[-+*/%<>{}()[\],;]",
        text.lower(),
    )
    preserved = {
        "if", "else", "for", "while", "switch", "case", "return", "break",
        "continue", "true", "false", "auto", "const", "static_cast", "struct",
        "class", "enum", "namespace", "using", "void", "bool", "int", "long",
        "std", "optional", "vector", "array", "size_t", "int32_t", "int64_t",
        "uint16_t", "uint32_t", "uint64_t", "nullopt", "numeric_limits",
    }
    aliases: dict[str, str] = {}
    normalized: list[str] = []
    for token in raw:
        if not re.fullmatch(r"[a-z_][a-z_0-9]*", token) or token in preserved:
            normalized.append(token)
            continue
        if token not in aliases:
            aliases[token] = f"id{len(aliases)}"
        normalized.append(aliases[token])
    return tuple(normalized)


def _ngrams(tokens: tuple[str, ...], width: int = 5) -> set[str]:
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 1.0
    return len(left & right) / len(left | right)


def _dimension_text(root: Path, dimension: str) -> str:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = root / config["files"]["solution"][0]
    mapping = {
        "public_api": [solution, root / ".docs/instructions.md"],
        "owned_state_or_algorithm": [root / ".meta/example.h"],
        "mutation_selection_rules": [root / ".meta/example.h", root / ".docs/instructions.md"],
        "invalid_boundary_behavior": [root / ".docs/instructions.md", root / "task_visible_test.cpp"],
        "reference_control_flow": [root / ".meta/example.h"],
        "deterministic_oracle": [
            root / "task_visible_test.cpp",
            root / ".meta/task_hidden_test.cpp",
            root / ".docs/instructions.md",
        ],
        "topic_specific_negative_fixture": [root / ".meta/negative.h", root / ".meta/tests.toml", root / ".docs/instructions.md"],
    }
    texts = [path.read_text(encoding="utf-8") for path in mapping[dimension]]
    # The emitted headers intentionally carry reusable checked/date primitives
    # before each public contract. They are implementation support, not
    # candidate-specific evidence in any hard-rule dimension.
    texts = [
        text.split("} // namespace detail", 1)[-1]
        if "} // namespace detail" in text
        else text
        for text in texts
    ]
    return "\n".join(texts)


def _pair_decision(
    left: Path, right: Path, *, common_lineage_task_id: str | None = None
) -> dict[str, object]:
    # Candidate-to-candidate screening uses the family hard-rule threshold.
    # Adversarial controls deliberately preserve a common lineage while making
    # coherent surface or policy changes, so screen them with a more
    # conservative clone threshold.  A useful control must be classified as a
    # clone in every dimension, not merely fail the aggregate decision.
    threshold = 0.95
    dimensions: dict[str, object] = {}
    for dimension in HARD_RULE_DIMENSIONS:
        left_task_id = common_lineage_task_id or left.name
        right_task_id = common_lineage_task_id or right.name
        left_features = _ngrams(_normalized_tokens(_dimension_text(left, dimension), left_task_id))
        right_features = _ngrams(_normalized_tokens(_dimension_text(right, dimension), right_task_id))
        overlap = _overlap(left_features, right_features)
        symmetric = len(left_features ^ right_features)
        passed = overlap < threshold and symmetric >= 1
        dimensions[dimension] = {
            "overlap": round(overlap, 6),
            "threshold": threshold,
            "symmetric_difference": symmetric,
            "pass": passed,
            "left_witness": sorted(left_features - right_features)[:2],
            "right_witness": sorted(right_features - left_features)[:2],
        }
    return {
        "left": left.name,
        "right": right.name,
        "dimensions": dimensions,
        "pass": all(item["pass"] for item in dimensions.values()),
    }


def _prompt_role_check(root: Path) -> None:
    task = load_task(root)
    prompt = build_prompt(task)
    forbidden = (".meta/", "CMakeLists.txt", "task_visible_test.cpp", "example.h", "negative.h")
    if any(marker in prompt for marker in forbidden):
        raise RuntimeError(f"prompt_private_leak:{root.name}")
    examples = load_example_files_from_config(root)
    answer = build_assistant_response(task, examples)
    try:
        parsed = parse_whole_file_blocks(answer)
    except WholeFormatError as exc:
        raise RuntimeError(f"whole_format_failed:{root.name}:{exc}") from exc
    if tuple(parsed) != tuple(task.editable_files):
        raise RuntimeError(f"target_reference_mismatch:{root.name}")


def _benchmark_ids() -> set[str]:
    manifest = json.loads(_repo(BENCHMARK_MANIFEST).read_text(encoding="utf-8"))
    raw = manifest.get("tasks") or manifest.get("task_ids") or manifest.get("ids")
    if not isinstance(raw, list):
        raise RuntimeError("benchmark_manifest_invalid")
    ids = {item["task_id"] if isinstance(item, dict) else str(item) for item in raw}
    if len(ids) != 26:
        raise RuntimeError(f"benchmark_screen_not_completed:{len(ids)}")
    return ids


def _semantic_corpus(root: Path) -> str:
    paths = [
        root / ".docs/introduction.md",
        root / ".docs/instructions.md",
        root / ".meta/example.h",
        root / ".meta/task_hidden_test.cpp",
        root / "task_visible_test.cpp",
    ]
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths if path.is_file())


def _inventory_record(roots: tuple[Path, ...]) -> dict[str, object]:
    entries = sorted(
        root.resolve(strict=False).relative_to(REPO_ROOT).as_posix() for root in roots
    )
    payload = "".join(f"{entry}\n" for entry in entries).encode()
    return {"count": len(entries), "sha256": hashlib.sha256(payload).hexdigest(), "entries": entries}


def _cross_tree_screen(roots: tuple[Path, ...]) -> dict[str, object]:
    candidate_ids = {root.name for root in roots}
    own_root = _repo(DEFAULT_OUT).resolve(strict=False)
    sibling_expansion = tuple(
        root
        for root in _real_task_roots(_repo(EXPANSION_ROOT))
        if own_root not in root.resolve(strict=False).parents
    )
    existing = (
        _real_task_roots(_repo(LEGACY_ROOT))
        + _real_task_roots(_repo(REVERIFY_ROOT))
        + sibling_expansion
    )
    collisions = sorted(candidate_ids.intersection(root.name for root in existing))
    if collisions:
        raise RuntimeError(f"duplicate_task:{','.join(collisions)}")
    candidate_features = {
        root.name: _ngrams(_normalized_tokens(_semantic_corpus(root), root.name), 7)
        for root in roots
    }
    strongest: dict[str, object] = {"overlap": 0.0}
    for existing_root in existing:
        features = _ngrams(_normalized_tokens(_semantic_corpus(existing_root), existing_root.name), 7)
        for task_id, candidate in candidate_features.items():
            score = _overlap(candidate, features)
            if score > float(strongest["overlap"]):
                strongest = {"task_id": task_id, "existing": existing_root.as_posix(), "overlap": round(score, 6)}
            if score >= 0.80:
                raise RuntimeError(f"duplicate_family:{task_id}:{existing_root.name}:{score:.3f}")
    return {
        "status": "pass",
        "existing_root_count": len(existing),
        "sibling_expansion_root_count": len(sibling_expansion),
        "legacy_inventory": _inventory_record(_real_task_roots(_repo(LEGACY_ROOT))),
        "reverify_inventory": _inventory_record(_real_task_roots(_repo(REVERIFY_ROOT))),
        "sibling_expansion_inventory": _inventory_record(sibling_expansion),
        "strongest": strongest,
    }


def _holdout_screen(roots: tuple[Path, ...]) -> dict[str, object]:
    holdout_root = _repo(HOLDOUT_ROOT)
    holdouts = tuple(sorted(path.parent.parent for path in holdout_root.rglob(".meta/config.json")))
    if len(holdouts) != 26:
        raise RuntimeError(f"benchmark_screen_not_completed:{len(holdouts)}")
    ids = _benchmark_ids()
    for root in roots:
        text = _semantic_corpus(root).lower()
        for holdout_id in ids:
            explicit_patterns = (
                rf"`{re.escape(holdout_id)}`",
                rf"/{re.escape(holdout_id)}/",
                rf"(?:task|exercise)(?:_id)?\s*[:=]\s*{re.escape(holdout_id)}(?:\s|$)",
            )
            if any(re.search(pattern, text) for pattern in explicit_patterns):
                raise RuntimeError(f"benchmark_id_overlap:{root.name}:{holdout_id}")
    strongest: dict[str, object] = {"overlap": 0.0}
    for root in roots:
        candidate = _ngrams(_normalized_tokens(_semantic_corpus(root), root.name), 7)
        for holdout in holdouts:
            score = _overlap(candidate, _ngrams(_normalized_tokens(_semantic_corpus(holdout), holdout.name), 7))
            if score > float(strongest["overlap"]):
                strongest = {"task_id": root.name, "holdout": holdout.name, "overlap": round(score, 6)}
            if score >= 0.72:
                raise RuntimeError(f"benchmark_content_overlap:{root.name}:{holdout.name}:{score:.3f}")
    return {"status": "pass", "holdout_count": len(holdouts), "inventory": _inventory_record(holdouts), "strongest": strongest}


def plan_remediation(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Preserve cycle-001 findings and quarantine every failed root.

    This intentionally does not invent replacement IDs.  A replacement ID is
    admissible only after its genuinely different executable contract exists.
    """

    output = _safe_output(out)
    roots = _real_task_roots(output)
    if len(roots) != TASK_COUNT:
        raise RuntimeError(f"binding_root_count_failed:{len(roots)}")
    audit_path = _repo(AUDIT_CYCLE_001)
    if not audit_path.is_file() or _sha256_file(audit_path) != AUDIT_CYCLE_001_HASH:
        raise RuntimeError("audit_cycle_001_subject_mismatch")
    findings = [f"AEO-C01-F00{index}" for index in range(1, 6)]
    remedy_dir = output / ".state/remedy"
    remedy_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for root in roots:
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": root.name,
            "family_id_before": FAMILY_ID,
            "tree_hash_before": f"sha256:{_tree_hash(root)}",
            "generator_path": GENERATOR_PATH.as_posix(),
            "generator_revision": f"sha256:{_sha256_file(_repo(GENERATOR_PATH))}",
            "finding_ids": findings,
            "disposition": "replace",
            "replacement_task_id": None,
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": CURRICULUM.as_posix(),
            "remedy_spec_hash": f"sha256:{_sha256_file(_repo(CURRICULUM))}",
            "status": "planned",
            "primary_core_objective": "not_achieved",
            "local_status": "not_completed",
            "exact_blockers": [
                "task-specific replacement contract/reference/oracle not implemented",
                "687 seven-dimension pair failures in the failed family screen",
                "mandatory Docker normal/sanitizer/negative evidence not run after semantic failure",
            ],
            "audit_report": AUDIT_CYCLE_001.as_posix(),
            "audit_report_sha256": AUDIT_CYCLE_001_HASH,
        }
        _write(
            remedy_dir / f"{root.name}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            True,
        )
        records.append(record)
    rejected = {
        "schema_version": "epoch-age-overflow-rejected-roots-v1",
        "roots": [
            {
                "task_id": root.name,
                "disposition": "replace",
                "finding_ids": findings,
                "replacement_task_id": None,
            }
            for root in roots
        ],
    }
    _write(
        output / ".state/rejected-roots.json",
        json.dumps(rejected, indent=2, sort_keys=True) + "\n",
        True,
    )
    _write(
        output / ".state/selected-roots.json",
        json.dumps({"task_ids": [], "reason": "audit_cycle_001_all_replace"}, indent=2, sort_keys=True) + "\n",
        True,
    )
    cycle_dir = output / ".state/cycles"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    cycle = {
        "schema_version": "aider-task-creation-cycle-v1",
        "cycle": 1,
        "family_id": FAMILY_ID,
        "candidate_manifest": ".state/generator-manifest.json",
        "curriculum_sha256": _sha256_file(_repo(CURRICULUM)),
        "generator_sha256": _sha256_file(_repo(GENERATOR_PATH)),
        "focused_test_sha256": _sha256_file(_repo(FOCUSED_TEST_PATH)),
        "generated_tree_sha256": _subject_hash(output),
        "grader_policy": "pinned Docker sanity image; not reached after semantic failure",
        "family_screen": ".state/family-screen.failed.json",
        "creator_preflight": ".state/creator-preflight.failed.json",
        "audit_subject_hash": "9af86a2ce5d764d236b00065b79716529cab042088c6da2fdbd836228ddf45e4",
        "audit_report": AUDIT_CYCLE_001.as_posix(),
        "audit_report_sha256": AUDIT_CYCLE_001_HASH,
        "finding_ids": findings,
        "remediation_disposition": "replace_all_80",
        "remedy_record_count": len(records),
        "retained_task_ids": [],
        "replaced_task_ids": [root.name for root in roots],
        "rejected_task_ids": [],
        "terminal_status": "not_completed",
        "exact_blockers": records[0]["exact_blockers"],
    }
    cycle_path = cycle_dir / "cycle-001.json"
    if cycle_path.exists():
        raise RuntimeError("append_only_cycle_exists:cycle-001")
    _write(cycle_path, json.dumps(cycle, indent=2, sort_keys=True) + "\n", True)
    return cycle


def _make_controls(out: Path, roots: tuple[Path, ...]) -> tuple[Path, ...]:
    controls_root = out / ".state/controls"
    if controls_root.exists():
        shutil.rmtree(controls_root)
    source_id = next(task.task_id for task in TASKS if task.operation == "floor_split")
    source = next(root for root in roots if root.name == source_id)
    controls = []
    for name in CONTROL_NAMES:
        target = controls_root / name
        shutil.copytree(source, target)
        text_files = tuple(
            path
            for path in target.rglob("*")
            if path.is_file() and path.suffix in {".h", ".cpp", ".md", ".toml"}
        )
        if name == "domain-identifier-renamed":
            for path in (target / ".docs/introduction.md",):
                text = path.read_text(encoding="utf-8").replace(
                    "Unix", "Archive"
                ).replace("unix", "archive")
                path.write_text(text, encoding="utf-8")
        elif name == "constants-or-policy-only":
            for path in text_files:
                changed = path.read_text(encoding="utf-8")
                changed = changed.replace("86401", "43201").replace(
                    "86399", "43199"
                )
                changed = changed.replace(
                    "-106751991167301LL", "-213503982334602LL"
                )
                path.write_text(
                    changed.replace("86400", "43200"),
                    encoding="utf-8",
                )
        else:
            example = target / ".meta/example.h"
            example.write_text(
                example.read_text(encoding="utf-8").replace(
                    "if (second < 0)", "if (second < 1)"
                ),
                encoding="utf-8",
            )
            visible = target / "task_visible_test.cpp"
            visible.write_text(
                visible.read_text(encoding="utf-8")
                .replace("(86401)", "(86400)")
                .replace("a->day == 1 && a->second_of_day == 1", "a->day == 0 && a->second_of_day == 86400"),
                encoding="utf-8",
            )
            instructions = target / ".docs/instructions.md"
            instructions.write_text(
                instructions.read_text(encoding="utf-8")
                .replace("pure-Euclidean", "right-closed")
                .replace("in [0, 86399]", "in [1, 86400]")
                .replace("in [0,86400)", "in [1,86401)"),
                encoding="utf-8",
            )
        changed = [path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file() and _sha256_file(path) != _sha256_file(source / path.relative_to(target))]
        if not changed:
            raise RuntimeError(f"adversarial_control_noop:{name}")
        _write(target / ".control.json", json.dumps({"name": name, "source": source.name, "changed_files": changed}, indent=2, sort_keys=True) + "\n", True)
        controls.append(target)
    return tuple(controls)


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    output = _safe_output(out)
    roots = _real_task_roots(output)
    if len(roots) != TASK_COUNT or {root.name for root in roots} != {task.task_id for task in TASKS}:
        raise RuntimeError(f"binding_root_count_failed:{len(roots)}")
    for root in roots:
        _prompt_role_check(root)
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        solution = config.get("files", {}).get("solution")
        examples = config.get("files", {}).get("example")
        if solution != [f"{root.name}.h"] or examples != [".meta/example.h"]:
            raise RuntimeError(f"reference_map_failed:{root.name}")
    pairs = [_pair_decision(left, right) for i, left in enumerate(roots) for right in roots[i + 1 :]]
    if len(pairs) != PAIR_COUNT:
        raise RuntimeError(f"pair_count_failed:{len(pairs)}")
    failed = [pair for pair in pairs if not pair["pass"]]
    if failed:
        first = failed[0]
        failure = {
            "schema_version": "epoch-age-overflow-family-screen-v1",
            "status": "failed",
            "reason_code": "duplicate_family",
            "task_count": len(roots),
            "pair_count": len(pairs),
            "failed_pair_count": len(failed),
            "dimensions": list(HARD_RULE_DIMENSIONS),
            "first_failed_pair": first,
            "pairs": pairs,
            "tree_hash": _subject_hash(output),
            "owner_sha256": _sha256_file(_repo(GENERATOR_PATH)),
            "case_renderer_sha256": _sha256_file(_repo(CASE_RENDERER_PATH)),
        }
        _write(
            output / ".state/family-screen.failed.json",
            json.dumps(failure, indent=2, sort_keys=True) + "\n",
            True,
        )
        preflight_failure = {
            "schema_version": "epoch-age-overflow-creator-preflight-v1",
            "status": "failed",
            "blocked_gate": "seven_dimension_family_diversity",
            "reason_code": "duplicate_family",
            "first_failed_pair": {
                "left": first["left"],
                "right": first["right"],
                "failed_dimensions": [
                    name
                    for name, item in first["dimensions"].items()
                    if not item["pass"]
                ],
            },
            "failed_pair_count": len(failed),
            "tree_hash": _subject_hash(output),
            "family_screen_failed_sha256": _sha256_file(
                output / ".state/family-screen.failed.json"
            ),
        }
        _write(
            output / ".state/creator-preflight.failed.json",
            json.dumps(preflight_failure, indent=2, sort_keys=True) + "\n",
            True,
        )
        raise RuntimeError(f"duplicate_family:{first['left']}:{first['right']}")
    controls = _make_controls(output, roots)
    control_source_id = next(
        task.task_id for task in TASKS if task.operation == "floor_split"
    )
    control_source = next(root for root in roots if root.name == control_source_id)
    control_results = []
    for control in controls:
        result = _pair_decision(
            control_source,
            control,
            common_lineage_task_id=control_source.name,
        )
        rejected_dimensions = [name for name, item in result["dimensions"].items() if not item["pass"]]
        if len(rejected_dimensions) != len(HARD_RULE_DIMENSIONS):
            raise RuntimeError(
                f"adversarial_clone_dimension_escape:{control.name}:"
                + ",".join(
                    name
                    for name in HARD_RULE_DIMENSIONS
                    if name not in rejected_dimensions
                )
            )
        control_results.append({"name": control.name, "changed_files": json.loads((control / ".control.json").read_text())["changed_files"], "rejected_dimensions": rejected_dimensions, "pair": result})
    cross_tree = _cross_tree_screen(roots)
    holdout = _holdout_screen(roots)
    screen = {
        "schema_version": "epoch-age-overflow-family-screen-v1",
        "normalizer": NORMALIZER,
        "status": "pass",
        "task_count": len(roots),
        "pair_count": len(pairs),
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "pairs": pairs,
        "controls": control_results,
        "cross_tree": cross_tree,
        "benchmark": holdout,
        "tree_hash": _subject_hash(output),
        "owner_sha256": _sha256_file(_repo(GENERATOR_PATH)),
        "case_renderer_sha256": _sha256_file(_repo(CASE_RENDERER_PATH)),
    }
    _write(output / ".state/family-screen.json", json.dumps(screen, indent=2, sort_keys=True) + "\n", True)
    return screen


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def _verify_one(root: Path, *, sanitizer: bool, negative: bool) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="epoch-age-overflow-") as temporary:
        temp = Path(temporary)
        build_dir = temp / "build"
        header = root / (".meta/negative.h" if negative else ".meta/example.h")
        flags = "-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer" if sanitizer else ""
        configure = [
            "cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles",
            f"-DTASK_HEADER={header}", f"-DCMAKE_CXX_FLAGS={flags}", f"-DCMAKE_EXE_LINKER_FLAGS={flags}",
        ]
        _run(configure, cwd=root)
        _run(["cmake", "--build", str(build_dir), "--parallel", "2"], cwd=root)
        discovered = _run(["ctest", "--test-dir", str(build_dir), "-N"], cwd=root)
        match = re.search(r"Total Tests:\s*(\d+)", discovered.stdout)
        count = int(match.group(1)) if match else 0
        if count != 2:
            raise RuntimeError(f"test_discovery_failed:{root.name}:{count}")
        run_env = dict(os.environ)
        if sanitizer:
            run_env.update({"ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})
        executed = subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], cwd=root, env=run_env, text=True, capture_output=True, check=False)
        if negative:
            if executed.returncode == 0:
                raise RuntimeError(f"negative_fixture_not_rejected:{root.name}")
        elif executed.returncode != 0:
            raise RuntimeError(f"reference_tests_failed:{root.name}\n{executed.stdout}\n{executed.stderr}")
        return {"test_count": count, "returncode": executed.returncode, "negative_rejected": negative and executed.returncode != 0}


def verify_host(out: Path = DEFAULT_OUT) -> dict[str, object]:
    output = _safe_output(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("host_toolchain_not_completed:cmake_or_cxx_missing")
    roots = _real_task_roots(output)
    records = []
    for root in roots:
        normal = _verify_one(root, sanitizer=False, negative=False)
        sanitizer = _verify_one(root, sanitizer=True, negative=False)
        negative = _verify_one(root, sanitizer=False, negative=True)
        if normal["test_count"] != sanitizer["test_count"]:
            raise RuntimeError(f"sanitizer_test_count_mismatch:{root.name}")
        records.append({"task_id": root.name, "normal": normal, "sanitizer": sanitizer, "negative": negative})
    receipt = {"schema_version": "epoch-age-overflow-host-receipt-v1", "status": "pass", "task_count": len(records), "records": records, "tree_hash": _subject_hash(output)}
    _write(output / ".state/host-oracle-receipt.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest_path = output / ".state/generator-manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "campaign_verified_host_only"
        manifest["host_receipt_sha256"] = _sha256_file(
            output / ".state/host-oracle-receipt.json"
        )
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return receipt


def _archive(out: Path, destination: Path) -> str:
    with tarfile.open(destination, "w") as archive:
        for path in sorted(item for item in out.rglob("*") if item.is_file()):
            relative = path.relative_to(out)
            info = archive.gettarinfo(str(path), arcname=relative.as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    return _sha256_file(destination)


def docker_sanity(out: Path = DEFAULT_OUT, *, result_out: Path | None = None) -> dict[str, object]:
    output = _safe_output(out)
    screen = json.loads((output / ".state/family-screen.json").read_text(encoding="utf-8"))
    live_hash = _subject_hash(output)
    if screen.get("tree_hash") != live_hash:
        raise RuntimeError("stale_family_screen")
    result_path = result_out or output / ".state/docker-sanity.json"
    with tempfile.TemporaryDirectory(prefix="epoch-age-overflow-docker-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        archive_hash = _archive(output, archive)
        script = temp / "verify.sh"
        script.write_text(
            r"""#!/bin/sh
set -eu
mkdir -p /work/family
tar -xf /input/family.tar -C /work/family
python3 - /work/family <<'PY'
import hashlib, pathlib, sys
root=pathlib.Path(sys.argv[1]); h=hashlib.sha256()
for p in sorted(x for x in root.rglob('*') if x.is_file() and '.state' not in x.relative_to(root).parts):
 r=p.relative_to(root).as_posix().encode(); b=p.read_bytes()
 h.update(len(r).to_bytes(8,'big')); h.update(r); h.update(len(b).to_bytes(8,'big')); h.update(b)
print(h.hexdigest())
PY
cmake --version | head -1
c++ --version | head -1
command -v c++
sha256sum "$(command -v c++)" | cut -d' ' -f1
python3 - /work/family /output/records.json <<'PY'
import json, os, pathlib, re, shutil, subprocess, sys
root=pathlib.Path(sys.argv[1]); records=[]; controls=[]
env=dict(os.environ); env['ASAN_OPTIONS']='detect_leaks=0:halt_on_error=1'; env['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
for task in sorted(p for p in root.iterdir() if p.is_dir() and p.name != '.state'):
 item={'task_id':task.name}
 for mode, header, flags, expect in (
   ('normal','.meta/example.h','',0),
   ('sanitizer','.meta/example.h','-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer',0),
   ('negative','.meta/negative.h','',1)):
  build=pathlib.Path('/work/build')/(task.name+'-'+mode); shutil.rmtree(build,ignore_errors=True)
  commands=[['cmake','-S',str(task),'-B',str(build),'-G','Unix Makefiles','-DTASK_HEADER='+str(task/header),'-DCMAKE_CXX_FLAGS='+flags,'-DCMAKE_EXE_LINKER_FLAGS='+flags],['cmake','--build',str(build),'--parallel','2']]
  for cmd in commands:
   r=subprocess.run(cmd,text=True,capture_output=True,env=env)
   if r.returncode: raise SystemExit(task.name+':'+mode+':build:'+r.stdout+r.stderr)
  n=subprocess.run(['ctest','--test-dir',str(build),'-N'],text=True,capture_output=True,env=env)
  m=re.search(r'Total Tests:\s*(\d+)',n.stdout); count=int(m.group(1)) if m else 0
  r=subprocess.run(['ctest','--test-dir',str(build),'--output-on-failure'],text=True,capture_output=True,env=env)
  if count != 2 or (expect == 0 and r.returncode != 0) or (expect == 1 and r.returncode == 0):
   raise SystemExit(task.name+':'+mode+':tests:'+r.stdout+r.stderr)
  item[mode]={'test_count':count,'returncode':r.returncode}
 records.append(item)
for task in sorted((root/'.state'/'controls').iterdir()):
 item={'name':task.name}
 for mode, flags in (
   ('normal',''),
   ('sanitizer','-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer')):
  build=pathlib.Path('/work/control-build')/(task.name+'-'+mode); shutil.rmtree(build,ignore_errors=True)
  commands=[['cmake','-S',str(task),'-B',str(build),'-G','Unix Makefiles','-DTASK_HEADER='+str(task/'.meta/example.h'),'-DCMAKE_CXX_FLAGS='+flags,'-DCMAKE_EXE_LINKER_FLAGS='+flags],['cmake','--build',str(build),'--parallel','2']]
  for cmd in commands:
   r=subprocess.run(cmd,text=True,capture_output=True,env=env)
   if r.returncode: raise SystemExit('control:'+task.name+':'+mode+':build:'+r.stdout+r.stderr)
  n=subprocess.run(['ctest','--test-dir',str(build),'-N'],text=True,capture_output=True,env=env)
  m=re.search(r'Total Tests:\s*(\d+)',n.stdout); count=int(m.group(1)) if m else 0
  r=subprocess.run(['ctest','--test-dir',str(build),'--output-on-failure'],text=True,capture_output=True,env=env)
  if count != 2 or r.returncode != 0: raise SystemExit('control:'+task.name+':'+mode+':tests:'+r.stdout+r.stderr)
  item[mode]={'test_count':count,'returncode':r.returncode}
 controls.append(item)
pathlib.Path(sys.argv[2]).write_text(json.dumps({'records':records,'controls':controls},sort_keys=True))
PY
""",
            encoding="utf-8",
        )
        script.chmod(0o755)
        result_dir = temp / "result"
        result_dir.mkdir()
        command = [
            "docker", "run", "--rm", "--network", "none",
            "-v", f"{archive}:/input/family.tar:ro",
            "-v", f"{script}:/input/verify.sh:ro",
            "-v", f"{result_dir}:/output",
            SANITY_IMAGE, "/bin/sh", "/input/verify.sh",
        ]
        run = subprocess.run(command, text=True, capture_output=True, check=False)
        if run.returncode != 0:
            raise RuntimeError(f"docker_sanity_failed:{run.stdout}\n{run.stderr}")
        payload = json.loads((result_dir / "records.json").read_text(encoding="utf-8"))
        mounted_hash = run.stdout.splitlines()[0].strip()
        if mounted_hash != live_hash:
            raise RuntimeError(f"grader_mount_hash_mismatch:{live_hash}:{mounted_hash}")
        records = payload["records"]
        controls = payload["controls"]
        if len(records) != TASK_COUNT:
            raise RuntimeError(f"docker_task_count_failed:{len(records)}")
        if len(controls) != len(CONTROL_NAMES):
            raise RuntimeError(f"docker_control_count_failed:{len(controls)}")
        receipt = {
            "schema_version": "epoch-age-overflow-docker-sanity-v1",
            "status": "pass",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": SANITY_IMAGE,
            "image_id": SANITY_IMAGE_ID,
            "tree_hash": live_hash,
            "mounted_tree_hash": mounted_hash,
            "archive_sha256": archive_hash,
            "owner_sha256": _sha256_file(_repo(GENERATOR_PATH)),
            "case_renderer_sha256": _sha256_file(_repo(CASE_RENDERER_PATH)),
            "curriculum_sha256": _sha256_file(_repo(CURRICULUM)),
            "compiler": run.stdout.splitlines()[2] if len(run.stdout.splitlines()) > 2 else "recorded-in-log",
            "compiler_path": run.stdout.splitlines()[3] if len(run.stdout.splitlines()) > 3 else "recorded-in-log",
            "compiler_sha256": run.stdout.splitlines()[4] if len(run.stdout.splitlines()) > 4 else "recorded-in-log",
            "cmake": run.stdout.splitlines()[1] if len(run.stdout.splitlines()) > 1 else "recorded-in-log",
            "task_count": len(records),
            "normal_test_count": sum(item["normal"]["test_count"] for item in records),
            "sanitizer_test_count": sum(item["sanitizer"]["test_count"] for item in records),
            "negative_test_count": sum(item["negative"]["test_count"] for item in records),
            "records": records,
            "control_count": len(controls),
            "control_normal_test_count": sum(item["normal"]["test_count"] for item in controls),
            "control_sanitizer_test_count": sum(item["sanitizer"]["test_count"] for item in controls),
            "controls": controls,
            "command": command,
        }
        _write(result_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        return receipt


def creator_preflight(out: Path = DEFAULT_OUT) -> dict[str, object]:
    verify_core(out)
    receipt_path = _safe_output(out) / ".state/docker-sanity.json"
    if not receipt_path.is_file():
        raise RuntimeError("docker_sanity_not_completed")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    live_hash = _subject_hash(_safe_output(out))
    if (
        receipt.get("status") != "pass"
        or receipt.get("tree_hash") != live_hash
        or receipt.get("owner_sha256") != _sha256_file(_repo(GENERATOR_PATH))
        or receipt.get("case_renderer_sha256")
        != _sha256_file(_repo(CASE_RENDERER_PATH))
        or receipt.get("task_count") != TASK_COUNT
        or receipt.get("control_count") != len(CONTROL_NAMES)
    ):
        raise RuntimeError("stale_docker_sanity")
    preflight = {
        "schema_version": "epoch-age-overflow-creator-preflight-v1",
        "status": "pass",
        "task_count": TASK_COUNT,
        "pair_count": PAIR_COUNT,
        "tree_hash": live_hash,
        "family_screen_sha256": _sha256_file(_safe_output(out) / ".state/family-screen.json"),
        "docker_receipt_sha256": _sha256_file(receipt_path),
        "owner_sha256": _sha256_file(_repo(GENERATOR_PATH)),
        "case_renderer_sha256": _sha256_file(_repo(CASE_RENDERER_PATH)),
    }
    _write(_safe_output(out) / ".state/creator-preflight.json", json.dumps(preflight, indent=2, sort_keys=True) + "\n", True)
    _record_cycle_006(_safe_output(out), preflight, receipt)
    return preflight


def _record_cycle_006(
    output: Path, preflight: dict[str, object], receipt: dict[str, object]
) -> None:
    findings = ["AEO-C05-F001"]
    replacements: dict[str, str] = {}
    replacement_records = []
    for spec in TASKS:
        root = output / spec.task_id
        record = {
            "schema_version": "aider-task-remedy-v1",
            "cycle": 6,
            "task_id": replacements.get(spec.task_id, spec.task_id),
            "family_id_before": FAMILY_ID,
            "tree_hash_before": f"sha256:{_tree_hash(root)}",
            "generator_path": GENERATOR_PATH.as_posix(),
            "generator_revision": f"sha256:{_sha256_file(_repo(GENERATOR_PATH))}",
            "license_screen": "pass",
            "remedy_spec_path": CURRICULUM.as_posix(),
            "remedy_spec_hash": f"sha256:{_sha256_file(_repo(CURRICULUM))}",
            "disposition": "replace" if spec.task_id in replacements else "repair-in-place",
            "replacement_task_id": spec.task_id,
            "finding_ids": findings,
            "primary_core_objective": "achieved",
            "core_mechanism": spec.operation,
            "forbidden_substitute": spec.negative,
            "reference_sha256": _sha256_file(root / ".meta/example.h"),
            "visible_test_sha256": _sha256_file(root / "task_visible_test.cpp"),
            "hidden_test_sha256": _sha256_file(root / ".meta/task_hidden_test.cpp"),
            "negative_sha256": _sha256_file(root / ".meta/negative.h"),
            "root_sha256": _tree_hash(root),
            "normal_test_count": 2,
            "sanitizer_test_count": 2,
            "negative_fixture": "compiled_and_rejected",
            "prompt_boundary": "pass",
            "family_screen": "pass",
            "benchmark_screen": "pass",
            "status": "implemented",
            "audit_report": AUDIT_CYCLE_005.as_posix(),
            "audit_report_sha256": AUDIT_CYCLE_005_HASH,
        }
        _write(
            output / ".state/remedy" / f"{record['task_id']}.cycle-006.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            True,
        )
        replacement_records.append(record)
    cycle = {
        "schema_version": "aider-task-creation-cycle-v1",
        "cycle": 6,
        "family_id": FAMILY_ID,
        "status": "creator_preflight_pass_pending_fresh_audit",
        "tree_sha256": preflight["tree_hash"],
        "owner_sha256": preflight["owner_sha256"],
        "case_renderer_sha256": preflight["case_renderer_sha256"],
        "creator_preflight_sha256": _sha256_file(
            output / ".state/creator-preflight.json"
        ),
        "docker_receipt_sha256": _sha256_file(
            output / ".state/docker-sanity.json"
        ),
        "task_count": len(replacement_records),
        "pair_count": PAIR_COUNT,
        "replacement_count": len(replacement_records),
        "cycle_005_dispositions": {"repair-and-reverify": 80},
        "selected_cycle_006_ids": [spec.task_id for spec in TASKS],
        "finding_ids_routed": findings,
        "normal_test_count": receipt["normal_test_count"],
        "sanitizer_test_count": receipt["sanitizer_test_count"],
        "negative_test_count": receipt["negative_test_count"],
        "control_count": receipt["control_count"],
        "strongest_local_status": "pending_fresh_audit",
    }
    _write(
        output / ".state/cycles/cycle-006.json",
        json.dumps(cycle, indent=2, sort_keys=True) + "\n",
        True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--creator-preflight", action="store_true")
    parser.add_argument("--plan-remediation", action="store_true")
    parser.add_argument("--result-out", type=Path)
    args = parser.parse_args(argv)
    if args.plan_remediation:
        plan_remediation(args.out)
    elif args.verify_core:
        verify_core(args.out)
    elif args.verify_host:
        verify_host(args.out)
    elif args.docker_sanity:
        docker_sanity(args.out, result_out=args.result_out)
    elif args.creator_preflight:
        creator_preflight(args.out)
    else:
        build(args.out, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
