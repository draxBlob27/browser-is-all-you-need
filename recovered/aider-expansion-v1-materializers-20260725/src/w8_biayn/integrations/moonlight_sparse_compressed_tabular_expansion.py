"""Own the 25-root sparse/compressed/tabular count-plan expansion family."""

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
DEFAULT_OUT = EXPANSION_ROOT / "text-grid-logic/sparse-compressed-tabular"
LEGACY_ROOTS = (
    REPO_ROOT / ".w8-biayn/data/aider-tasks",
    REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify",
)
CURRICULUM = REPO_ROOT / (
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_SPARSE_COMPRESSED_TABULAR_EXPANSION_CURRICULUM.md"
)
FAMILY_SPEC = REPO_ROOT / (
    "docs/aider-tasks-spec/aider-text-grid-reshaping/sparse-compressed-tabular-expansion.md"
)
TEST_PATH = REPO_ROOT / "tests/test_moonlight_sparse_compressed_tabular_expansion.py"
OWNER = "src/w8_biayn/integrations/moonlight_sparse_compressed_tabular_expansion.py"
FAMILY_ID = "aider-expansion-v1-sparse-compressed-tabular-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
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


class CreatorError(RuntimeError):
    pass


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    mechanism: str
    contract: str
    false_substitute: str
    sample: tuple[int, ...]
    width: int
    parameter: int

    @property
    def snake(self) -> str:
        return self.task_id.replace("-", "_")

    @property
    def result_type(self) -> str:
        return "".join(part.title() for part in self.task_id.split("-")) + "Result"


CASES = (
    Case(
        "succinct-bit-rank-directory",
        "Succinct Bit Rank Directory",
        "packed words with periodic prefix-rank checkpoints",
        "Values are bits; width is the positive checkpoint stride; data stores checkpoint ranks and aux stores packed words.",
        "rescan the unpacked vector for every rank",
        (0, 1, 1, 0, 1, 0),
        2,
        5,
    ),
    Case(
        "frame-reference-integer-blocks",
        "Frame Of Reference Integer Blocks",
        "per-block minimum and checked offsets",
        "Values are nonnegative; width is a positive block length; aux stores each minimum and data stores offsets in input order.",
        "subtract one global minimum",
        (9, 7, 8, 20, 18, 19),
        3,
        0,
    ),
    Case(
        "zigzag-varint-ledger",
        "ZigZag Varint Ledger",
        "signed ZigZag mapping followed by base-128 groups",
        "Signed values are accepted; data is the canonical byte stream and aux stores exclusive byte ends.",
        "cast signed values directly to unsigned bytes",
        (-2, -1, 0, 1, 130),
        2,
        0,
    ),
    Case(
        "bounded-bitwidth-column",
        "Bounded Bitwidth Column",
        "least-significant-bit reservoir packing",
        "Width is 1..16 and every value is below two-to-width; data contains packed 30-bit-safe words and aux records value count and width.",
        "store one byte per logical value",
        (1, 2, 7, 0, 3),
        3,
        0,
    ),
    Case(
        "run-end-status-column",
        "Run End Status Column",
        "canonical values plus exclusive run ends",
        "Values are nonnegative; data stores run values and aux stores strictly increasing exclusive ends.",
        "store run lengths where ends are required",
        (2, 2, 2, 5, 5, 1),
        2,
        0,
    ),
    Case(
        "nullable-dictionary-column",
        "Nullable Dictionary Column",
        "sorted dictionary and stable ids",
        "Parameter is the null sentinel; aux is the sorted non-null dictionary and data contains ids or -1 for nulls.",
        "assign ids in first-seen order",
        (4, -1, 2, 4, 3, -1),
        2,
        -1,
    ),
    Case(
        "front-coded-path-lexicon",
        "Front Coded Path Lexicon",
        "strictly increasing delta-prefix stream",
        "Values are ordered path component ids; they must be strictly increasing; data stores first absolute then positive gaps and aux stores periodic anchors.",
        "concatenate entries without prefix boundaries",
        (3, 8, 10, 17, 25),
        2,
        0,
    ),
    Case(
        "jagged-offset-table",
        "Jagged Offset Table",
        "flat payload with terminal row offsets",
        "Width is the maximum row length and parameter is the deterministic row-length cycle; aux starts at zero and ends at the flat size.",
        "assume all rows have equal width",
        (1, 2, 3, 4, 5, 6),
        3,
        2,
    ),
    Case(
        "row-dictionary-fact-table",
        "Row Dictionary Fact Table",
        "complete-row dictionary and row-id stream",
        "Width is the positive rectangular row width; aux concatenates unique rows and data stores row ids.",
        "dictionary-encode each cell independently",
        (1, 2, 1, 2, 3, 4),
        2,
        0,
    ),
    Case(
        "nullable-columnar-record-batch",
        "Nullable Columnar Record Batch",
        "parallel value columns with row-aligned null plane",
        "Width must be two; input is flattened rows; data and aux hold the two columns without changing row positions.",
        "drop null rows while transposing",
        (1, 10, 2, -1, 3, 30),
        2,
        -1,
    ),
    Case(
        "schema-permutation-table",
        "Schema Permutation Table",
        "validated cyclic schema permutation",
        "Input is rectangular with width columns; parameter is a normalized left rotation; data preserves row order under that permutation.",
        "sort columns by their labels",
        (1, 2, 3, 4, 5, 6),
        3,
        1,
    ),
    Case(
        "table-cell-delta-patch",
        "Table Cell Delta Patch",
        "sorted changed-cell coordinate/value pairs",
        "Input contains equal-length old and new flattened tables; parameter is the half length; data stores changed index/value pairs.",
        "replace every cell in a changed row",
        (1, 2, 3, 1, 4, 3),
        3,
        3,
    ),
    Case(
        "full-outer-merge-table",
        "Full Outer Merge Table",
        "two-pointer full outer key merge",
        "Parameter splits two strictly increasing key streams; data is their union and aux stores 1/2/3 side-presence masks.",
        "perform an inner join",
        (1, 4, 8, 2, 4, 9),
        2,
        3,
    ),
    Case(
        "asof-snapshot-join",
        "As Of Snapshot Join",
        "latest-prior monotone two-pointer scan",
        "Parameter splits sorted snapshots from sorted events; data stores events and aux the latest prior snapshot or -1.",
        "select the nearest snapshot in either direction",
        (1, 5, 9, 0, 1, 6, 12),
        2,
        3,
    ),
    Case(
        "sparse-polynomial-canonicalizer",
        "Sparse Polynomial Canonicalizer",
        "exponent coalescence with zero cancellation",
        "Input is exponent/coefficient pairs; exponents are nonnegative; data emits ascending nonzero canonical pairs.",
        "retain duplicate exponents and zero terms",
        (0, 2, 1, 3, 0, -2, 4, 5),
        2,
        2,
    ),
    Case(
        "adjacency-gap-catalog",
        "Adjacency Gap Catalog",
        "per-vertex sorted neighbor gaps and offsets",
        "Input is undirected endpoint pairs; parameter is vertex count; aux is vertex offsets and data resets positive gaps per vertex.",
        "carry one delta chain across vertices",
        (0, 1, 0, 2, 2, 3),
        2,
        4,
    ),
    Case(
        "posting-skip-directory",
        "Posting Skip Directory",
        "positive posting gaps with absolute skip checkpoints",
        "Values must be strictly increasing nonnegative ids; width is checkpoint stride; data stores gaps and aux absolute checkpoints.",
        "scan every query from the first posting",
        (2, 5, 9, 14, 20, 27),
        2,
        0,
    ),
    Case(
        "quotient-remainder-membership",
        "Quotient Remainder Membership",
        "quotient bucket offsets and sorted remainders",
        "Width is a positive divisor and parameter is the exclusive universe; values are unique sorted members; aux closes every quotient bucket; query_member is tested from those emitted buckets.",
        "store quotients without bucket boundaries",
        (1, 4, 7, 9),
        3,
        12,
    ),
    Case(
        "block-coordinate-sparse-tensor",
        "Block Coordinate Sparse Tensor",
        "nonzero block catalog with payloads",
        "Width is positive block volume; data stores block indices for nonzero cells and aux stores their values in source order.",
        "materialize a second full dense tensor",
        (0, 2, 0, 3, 0, 4),
        2,
        3,
    ),
    Case(
        "symmetric-triangle-packer",
        "Symmetric Triangle Packer",
        "upper-triangle row packing",
        "Width is matrix order; input size is width squared and mirrored cells must agree; data stores the upper triangle.",
        "store only diagonal cells",
        (1, 2, 3, 2, 4, 5, 3, 5, 6),
        3,
        0,
    ),
    Case(
        "binary-quadtree-leaf-stream",
        "Binary Quadtree Leaf Stream",
        "preorder uniform-leaf/internal tags",
        "Width is a power-of-two square order and input values are bits; data is a complete preorder quadtree stream.",
        "use independent row runs",
        (0, 1, 1, 1),
        2,
        0,
    ),
    Case(
        "boolean-interval-mask",
        "Boolean Interval Mask",
        "maximal half-open true intervals",
        "Values are bits; data stores start/end pairs for maximal true runs, including a run ending at input size.",
        "store every true index independently",
        (0, 1, 1, 0, 1, 1, 1),
        2,
        0,
    ),
    Case(
        "last-write-sparse-overlay",
        "Last Write Sparse Overlay",
        "sequence-aware last-write coordinate compaction",
        "Input is coordinate/sequence/value triples; parameter is the default value; duplicate sequence numbers per coordinate reject.",
        "retain the first write per coordinate",
        (2, 0, 5, 2, 1, 7, 1, 0, 3),
        3,
        0,
    ),
    Case(
        "sparse-histogram-gap-stream",
        "Sparse Histogram Gap Stream",
        "positive-bin gaps plus explicit logical length",
        "Counts are nonnegative; data stores gap/count pairs for positive bins and aux stores the original bin count.",
        "omit trailing zero-bin length metadata",
        (0, 4, 0, 0, 2, 0, 3, 0),
        2,
        0,
    ),
    Case(
        "byte-column-bitplanes",
        "Byte Column Bitplanes",
        "eight row-aligned packed bit planes",
        "Values are bytes; data stores all eight packed planes including all-zero planes and aux stores row count.",
        "drop bit planes containing only zero bits",
        (1, 2, 3, 7),
        2,
        0,
    ),
)


def _fail(code: str, detail: str = "") -> None:
    raise CreatorError(f"{code}: {detail}" if detail else code)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        # A control root itself lives below the family's .state directory.  State
        # exclusion is relative to the subject root, not to its absolute path.
        relative = path.relative_to(root)
        if not include_state and ".state" in relative.parts:
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _safe_out(out: Path) -> Path:
    resolved = out.resolve(strict=False)
    if resolved != DEFAULT_OUT.resolve(strict=False):
        _fail("unsafe_path", str(out))
    if any(path.is_symlink() for path in (out, out.parent, out.parent.parent)):
        _fail("unsafe_path", "symlink component")
    for legacy in LEGACY_ROOTS:
        if (
            resolved == legacy.resolve(strict=False)
            or legacy.resolve(strict=False) in resolved.parents
        ):
            _fail("unsafe_path", str(legacy))
    return resolved


def _inventory(root: Path, *, exclude: Path | None = None) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    excluded = exclude.resolve(strict=False) if exclude is not None else None
    if not root.is_dir():
        return records
    for config in sorted(root.rglob(".meta/config.json")):
        if ".state" in config.parts or (excluded and excluded in config.resolve().parents):
            continue
        task_root = config.parent.parent
        records.append(
            {
                "task_id": task_root.name,
                "relative_root": task_root.relative_to(root).as_posix(),
                "tree_hash": _tree_hash(task_root),
                "config_hash": _file_sha(config),
            }
        )
    return records


def _existing_inventory(out: Path) -> dict[str, list[dict[str, str]]]:
    return {
        "legacy": _inventory(LEGACY_ROOTS[0]),
        "reverify": _inventory(LEGACY_ROOTS[1]),
        "expansion_before": _inventory(EXPANSION_ROOT, exclude=out),
    }


def _inventory_payload(
    inventory: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    return {
        "schema_version": "sparse-compressed-tabular-inventory-v1",
        "roots": {
            name: {
                "count": len(rows),
                "sha256": _sha(json.dumps(rows, sort_keys=True).encode()),
                "records": rows,
            }
            for name, rows in inventory.items()
        },
    }


def refresh_inventory(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Refresh only the frozen sibling inventory without rewriting task bytes."""
    out = _safe_out(out)
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file() or json.loads(manifest_path.read_text()).get("owner") != OWNER:
        _fail("foreign_output_root", str(out))
    payload = _inventory_payload(_existing_inventory(out))
    _json(out / ".state/source-inventory.json", payload)
    return payload


API_FIELDS = (
    (
        "bits",
        "checkpoint_stride",
        "query_prefix",
        "rank_checkpoints",
        "packed_words",
        "decoded_bits",
        "rank_answer",
    ),
    (
        "integers",
        "block_length",
        "reserved",
        "offsets",
        "block_minima",
        "decoded_integers",
        "block_count",
    ),
    (
        "signed_entries",
        "group_hint",
        "reserved",
        "varint_bytes",
        "byte_ends",
        "decoded_entries",
        "byte_count",
    ),
    (
        "column_values",
        "bit_width",
        "reserved",
        "packed_words",
        "layout",
        "decoded_column",
        "word_count",
    ),
    (
        "statuses",
        "run_hint",
        "reserved",
        "run_values",
        "exclusive_run_ends",
        "decoded_statuses",
        "run_count",
    ),
    (
        "nullable_values",
        "validity_words",
        "null_sentinel",
        "dictionary_ids",
        "sorted_dictionary",
        "decoded_values",
        "null_count",
    ),
    (
        "ordered_paths",
        "anchor_stride",
        "reserved",
        "common_prefix_lengths",
        "anchors",
        "decoded_paths",
        "anchor_count",
    ),
    (
        "rows",
        "maximum_row_length",
        "reserved",
        "payload",
        "row_offsets",
        "decoded_rows",
        "row_count",
    ),
    (
        "flat_rows",
        "row_width",
        "reserved",
        "row_ids",
        "row_dictionary",
        "decoded_rows",
        "unique_row_count",
    ),
    (
        "ids",
        "value_validity",
        "values",
        "id_column",
        "value_column",
        "decoded_records",
        "row_count",
    ),
    (
        "flat_table",
        "source_schema",
        "requested_schema",
        "permuted_cells",
        "schema_map",
        "decoded_table",
        "row_count",
    ),
    (
        "old_and_new_cells",
        "column_count",
        "old_cell_count",
        "patch_pairs",
        "old_cells",
        "decoded_versions",
        "change_count",
    ),
    (
        "left_and_right_keys",
        "key_hint",
        "left_count",
        "merged_keys",
        "presence_masks",
        "decoded_inputs",
        "merged_count",
    ),
    (
        "snapshots_and_events",
        "join_hint",
        "snapshot_count",
        "event_keys",
        "snapshots_and_matches",
        "decoded_inputs",
        "match_count",
    ),
    (
        "term_pairs",
        "pair_width",
        "evaluation_point",
        "canonical_terms",
        "evaluation_trace",
        "decoded_terms",
        "evaluation",
    ),
    (
        "edge_pairs",
        "endpoint_width",
        "vertex_count",
        "neighbor_gaps",
        "vertex_offsets",
        "decoded_edges",
        "directed_entry_count",
    ),
    (
        "posting_ids",
        "checkpoint_stride",
        "query_id",
        "posting_gaps",
        "skip_checkpoints",
        "decoded_postings",
        "contains_query",
    ),
    (
        "members",
        "divisor",
        "universe_limit",
        "remainders",
        "bucket_offsets",
        "decoded_members",
        "bucket_count",
    ),
    (
        "dense_cells",
        "shape",
        "block_shape",
        "block_coordinates",
        "dense_block_payloads",
        "decoded_cells",
        "nonzero_block_count",
    ),
    (
        "square_matrix",
        "matrix_order",
        "reserved",
        "upper_triangle",
        "row_offsets",
        "decoded_matrix",
        "packed_count",
    ),
    (
        "binary_raster",
        "raster_order",
        "reserved",
        "preorder_stream",
        "shape_metadata",
        "decoded_raster",
        "leaf_count",
    ),
    (
        "mask_bits",
        "interval_hint",
        "query_index",
        "half_open_intervals",
        "length_metadata",
        "decoded_mask",
        "query_value",
    ),
    (
        "update_triples",
        "coordinate_limit",
        "default_value",
        "overlay_pairs",
        "sequence_metadata",
        "decoded_overlay",
        "coordinate_count",
    ),
    (
        "bin_counts",
        "gap_hint",
        "reserved",
        "gap_count_pairs",
        "length_metadata",
        "decoded_bins",
        "positive_bin_count",
    ),
    (
        "byte_values",
        "plane_hint",
        "reserved",
        "bit_planes",
        "layout_metadata",
        "decoded_bytes",
        "plane_count",
    ),
)


RULES = (
    "Reject non-bits. A query prefix is absent when negative or greater than n. Empty input accepts only prefix zero. Rank counts positions [0, query_prefix) from the nearest emitted periodic checkpoint plus packed words.",
    "Reject negative values or nonpositive block length. The final short block is allowed. Per-block subtraction must fit int; duplicates preserve their positions.",
    "Every signed int is valid. Emit the shortest base-128 form; reject overflow or an unterminated/overlong group while decoding. Empty input is valid.",
    "bit_width is 1..16; reject negative or out-of-range values. Unused tail bits are zero and malformed nonzero tail bits reject. Empty input is valid.",
    "Reject negative statuses. Runs are maximal, ends are exclusive, strictly increasing, and terminate at row count. Empty input has no runs.",
    "The null sentinel must be negative and denotes absence; all other ints are values. Dictionary order is ascending and duplicate values share an id. A missing value decodes only from id -1.",
    "IDs must be strictly increasing nonnegative values. Anchors occur at exact stride boundaries; duplicate or descending IDs reject. Empty input is valid.",
    "maximum_row_length and length_cycle are positive. Offsets begin at zero, never decrease, and end at payload size; a final short row is retained.",
    "row_width is positive and divides the cell count. Dictionary rows are lexicographically ordered and ids select whole rows; duplicate rows reuse an id.",
    "Exactly two columns are required. The first column must be nonnegative and unique; the sentinel may appear only in the value column and its row position is preserved.",
    "column_count is positive and divides the cell count. Rotation is normalized modulo width; rows never reorder. Empty tables retain a valid schema map.",
    "old_cell_count divides the two equal versions and column_count must divide it. Pairs are ascending unique coordinates; replay is failure-atomic and bounds checked.",
    "The split is in range; both sides are strictly increasing with no internal duplicates. Equal keys produce mask 3; unmatched keys use masks 1 or 2.",
    "Snapshots are strictly increasing, events nondecreasing. Equality selects that snapshot; events before the first snapshot receive -1. Empty event input is valid.",
    "Input is exponent/coefficient pairs with nonnegative exponents. Equal exponents coalesce, zero sums disappear, and checked gap-Horner evaluation rejects overflow.",
    "vertex_count is positive. Reject loops, duplicate undirected edges, and out-of-range endpoints. Neighbor rows are ascending and reset their gap origin.",
    "Postings are strictly increasing nonnegative. The query may be absent; checkpoints are absolute every stride entries and membership starts at the nearest prior checkpoint.",
    "divisor and universe are positive. Members are unique, strictly increasing, and in [0, universe). Bucket offsets include every empty bucket and a terminal offset; contains_member is derived only from the queried bucket's emitted remainders.",
    "block volume and logical length are positive and agree with the dense input. Emit lexicographic block/offset coordinates for nonzeros; zero blocks are absent.",
    "matrix_order is positive and squared size must match. Reject any asymmetric mirrored pair. Row offsets delimit the upper triangle and decoding mirrors off-diagonal cells.",
    "Order is a positive power of two and size is order squared. Values are bits. Decode must consume exactly one complete preorder tree; trailing tags reject.",
    "Values are bits. Intervals are maximal, sorted, disjoint half-open spans; touching spans merge. Query outside [0,n) is absent, including empty input.",
    "Input is coordinate/sequence/value triples. Duplicate sequence numbers per coordinate reject; greatest sequence wins and default-valued winners are erased.",
    "Counts are nonnegative. Gaps are measured after the prior positive bin and logical length is explicit, preserving all trailing zeros. Empty input is valid.",
    "Values are bytes 0..255. Emit exactly eight row-aligned planes including zero planes; tail bits are zero and decoding requires the recorded row count.",
)


BOUNDARY_EXAMPLES = (
    "Bits [1,0,1], stride 2, prefix 3 produce checkpoints [1,2], packed word [5], and rank 2.",
    "Values [8,9,20], block length 2 produce bases [8,20], offsets [0,1,0], and the original values.",
    "Values [-1,0,64] produce bytes [1,0,128,1], ends [1,2,4], and decode exactly.",
    "Value [7] at width 3 produces packed payload [7], count 1, width 3, and zero unused tail bits.",
    "Statuses [4,4,7] produce run values [4,7] and exclusive ends [2,3].",
    "Values [-1,4,2,4] with sentinel -1 produce dictionary [2,4], ids [-1,1,0,1], and validity bits [0,1,1,1].",
    'Paths ["ant","ante","anthem"] produce prefix lengths [0,3,3], suffixes ["ant","e","hem"], and the same decoded order.',
    "Rows [[1,2],[],[3]] produce payload [1,2,3] and offsets [0,2,2,3].",
    "Rows [[2,1],[2,1],[1,9]] produce dictionary [[1,9],[2,1]] and ids [1,1,0].",
    "Rows [(1,10),(2,null),(3,30)] produce ids [1,2,3], canonical values [10,0,30], and validity [1,0,1].",
    'Schema ["b","a"], request ["a","b"], and row [7,8] produce map [1,0] and row [8,7].',
    "Old row [1,2] and new row [1,5] produce patch [(1,5)] and replay [1,5].",
    "Left [1,4] and right [2,4] produce keys [1,2,4] and masks [1,2,3].",
    "Snapshots [5,9] and events [4,5,10] produce matches [-1,5,9].",
    "Terms [(0,2),(0,-2),(3,4)] at x=2 produce canonical [(3,4)] and value 32.",
    "V=3 and edges [(0,2),(0,1)] produce rows [1,2], [], [0] with offsets [0,2,2,3].",
    "Postings [2,5,9,14], stride 2 produce gaps [2,3,4,5]; query 9 is present.",
    "Members [1,7], divisor 3, universe 9 produce remainders [1,1] and offsets [0,1,1,2].",
    "Shape (2,2,2), unit blocks, and values at (0,0,1)=5 and (1,1,1)=7 produce those two ordered blocks.",
    "Matrix [[1,2],[2,3]] produces upper triangle [1,2,3], offsets [0,2,3], and the original matrix.",
    "A uniform 2x2 raster of ones produces the single leaf record [0,1].",
    "Bits [1,1,0,1] produce intervals [(0,2),(3,4)]; query 4 is absent.",
    "Updates [(2,1,5),(2,3,0),(1,2,7)] with default 0 produce overlay [(1,7)].",
    "Counts [0,4,0,0] produce pair [(1,4)], logical length 4, and preserve both trailing zeros.",
    "Bytes [0,1] produce plane-0 bits [0,1], seven all-zero planes, plane count 8, and decode exactly.",
)


# Model-facing prose for `.docs/introduction.md`, keyed by task id. One
# domain-motivating paragraph per case; it never states the contract and stays
# free of harness vocabulary, matching the official exercise documentation
# register.
INTRODUCTIONS: dict[str, str] = {
    "succinct-bit-rank-directory": (
        "How many ones appear in the first N bits? Databases and text "
        "indexes ask this rank question constantly over huge bitvectors. "
        "Answering by counting from scratch every time is too slow, so "
        "succinct structures stash periodic checkpoints and count only the "
        "remainder. The art is keeping the extra bookkeeping tiny."
    ),
    "frame-reference-integer-blocks": (
        "Sensor readings and timestamps often cluster in a narrow range "
        "even when their absolute values are large. Recording each block's "
        "minimum once and storing only the small offsets shrinks such data "
        "dramatically. The catch is that every offset must be checked so "
        "nothing overflows its block."
    ),
    "zigzag-varint-ledger": (
        "Wire protocols squeeze small integers into few bytes by folding "
        "the sign bit into the value and splitting the result into "
        "seven-bit groups. Small negative numbers become small unsigned "
        "ones, so they stay cheap. Decoding must be just as careful as "
        "encoding: truncated or padded byte groups are malformed, not "
        "creative."
    ),
    "bounded-bitwidth-column": (
        "When every value in a column fits in three bits, storing a full "
        "byte per value wastes most of the space. Bit-packing lays the "
        "values end to end inside machine words, recording only the width "
        "and the count alongside. The tail of the last word has to be "
        "accounted for so nothing invents extra values."
    ),
    "run-end-status-column": (
        "A status column often holds the same value for thousands of "
        "consecutive rows: idle, idle, idle, busy. Run-length encoding "
        "stores each distinct value once with the position where it ends. "
        "Keeping the ends strictly increasing and exclusive is what lets a "
        "reader jump straight to any row."
    ),
    "nullable-dictionary-column": (
        "Real columns have holes: unknown ages, skipped readings, optional "
        "fields. Dictionary encoding stores each distinct value once and "
        "replaces repeats with small ids, while a separate marker says "
        "which rows were missing altogether. A sorted dictionary keeps the "
        "mapping stable no matter how the rows arrive."
    ),
    "front-coded-path-lexicon": (
        "Sorted word lists share long prefixes: ant, ante, anthem. Front "
        "coding stores how much of the previous entry is reused and keeps "
        "only the new suffix, with periodic anchors so random access stays "
        "possible. It is one way dictionaries and path indexes fit on a "
        "single page."
    ),
    "jagged-offset-table": (
        "Not every table is rectangular: one order has three items, the "
        "next has none. A jagged layout flattens all the payloads into one "
        "array and remembers where each row begins and ends. The offsets, "
        "not the data, carry the shape."
    ),
    "row-dictionary-fact-table": (
        "Fact tables in warehouses repeat whole rows constantly: the same "
        "product, store, and day thousands of times. Storing each distinct "
        "row once and streaming row ids compresses the table without "
        "touching the cells. Keeping the dictionary in a canonical order "
        "makes the encoding deterministic."
    ),
    "nullable-columnar-record-batch": (
        "Columnar engines flip a table on its side: instead of keeping "
        "each row together, each column is stored as its own array. Rows "
        "with missing cells need a parallel validity marker so nothing "
        "shifts out of place. Transposing without losing track of the "
        "holes is the whole job."
    ),
    "schema-permutation-table": (
        "Two systems export the same table with columns in different "
        "orders, and someone must reconcile them. A validated permutation "
        "says where each incoming column belongs in the requested schema. "
        "Applying it row by row keeps the data intact while the layout "
        "changes."
    ),
    "table-cell-delta-patch": (
        "Replication logs do not resend whole tables; they send what "
        "changed. A cell-level patch lists only the coordinates and new "
        "values that differ, in a canonical sorted order. Replaying the "
        "patch on the old table must reproduce the new one exactly."
    ),
    "full-outer-merge-table": (
        "Merging two sorted key streams is easy until a key exists on only "
        "one side. A full outer merge keeps every key and records, for "
        "each, whether the left stream, the right stream, or both "
        "contributed it. Dropping the one-sided keys silently turns it "
        "into a different operation."
    ),
    "asof-snapshot-join": (
        "Market data and monitoring systems constantly ask: what was the "
        "most recent reading before this event? Matching each event to "
        "the latest prior snapshot is a scan that respects time's arrow, "
        "looking backward only, never forward. Picking the nearest "
        "snapshot in either direction would peek into the future."
    ),
    "sparse-polynomial-canonicalizer": (
        "Algebra systems receive polynomials in any order: duplicate "
        "exponents, cancelling terms, zeros scattered everywhere. Canonical "
        "form combines like terms, drops the zeros, and sorts what remains "
        "by exponent. Only then are two polynomials easy to compare, sign, "
        "or evaluate at a point."
    ),
    "adjacency-gap-catalog": (
        "Search engines and graph databases store adjacency lists back to "
        "back, compressing each sorted neighbor list as small gaps. Each "
        "vertex restarts its own gap chain, and an offset array says "
        "where every list begins. Sharing one chain across vertices would "
        "corrupt everything."
    ),
    "posting-skip-directory": (
        "An inverted index answers queries by walking long sorted lists "
        "of document ids. Skip checkpoints sprinkled at a fixed stride "
        "let the walk leap ahead instead of stepping one posting at a "
        "time. The checkpoints are absolute ids while the postings "
        "between them stay as gaps."
    ),
    "quotient-remainder-membership": (
        "A quotient filter answers membership questions by filing each "
        "value under its quotient bucket and keeping only the remainder. "
        "Buckets with no members still need their place in the offset "
        "table so every lookup lands in the right slot. It is a compact "
        "alternative to keeping whole values around."
    ),
    "block-coordinate-sparse-tensor": (
        "Scientific tensors are mostly zeros, and the nonzeros clump "
        "together. Storing a catalog of the nonzero blocks plus their "
        "payloads keeps the clumping without materializing the sea of "
        "zeros. A second dense copy for convenience would defeat the "
        "point."
    ),
    "symmetric-triangle-packer": (
        "A symmetric matrix stores every fact twice, once on each side of "
        "the diagonal. Packing only the upper triangle halves the space, "
        "provided the mirrored cells really agree. Checking that "
        "agreement is part of the packing job."
    ),
    "binary-quadtree-leaf-stream": (
        "A quadtree compresses a raster by noting when a whole region is "
        "uniform: one leaf record replaces a large block of identical "
        "pixels. A preorder walk of the tree, tagging leaves and internal "
        "nodes, captures the whole image in a compact stream. Uniform "
        "regions are where the savings live."
    ),
    "boolean-interval-mask": (
        "A long bitvector of flags is often a few solid stretches of true "
        "surrounded by false. Storing the start and end of each maximal "
        "true run is shorter and answers membership with a quick scan. "
        "Runs that reach the very end of the input still close properly."
    ),
    "last-write-sparse-overlay": (
        "Collaborative spreadsheets and versioned tables receive updates "
        "out of order, each stamped with a sequence number. The visible "
        "state keeps only the freshest write per cell, overlaid on a "
        "default. An older write arriving late must never overwrite a "
        "newer one."
    ),
    "sparse-histogram-gap-stream": (
        "Histograms of real data are mostly empty bins with a few spikes. "
        "Storing the distance between spikes plus each spike's count "
        "compresses the picture, as long as the original bin count, "
        "including trailing zeros, survives the round trip. Losing the "
        "tail silently shrinks the histogram."
    ),
    "byte-column-bitplanes": (
        "Bit-sliced indexes transpose a column of bytes into eight "
        "bitvectors, one per bit position, so filters become bitwise "
        "operations. Every plane is stored, even the all-zero ones, "
        "because the plane's position carries its meaning. Dropping "
        "silent planes would scramble every byte."
    ),
}

if set(INTRODUCTIONS) != {case.task_id for case in CASES}:
    raise AssertionError("every sparse/compressed/tabular case requires one introduction")


# This is an executable generation contract, not documentation-only metadata.
# `_test` emits every listed marker and a corresponding assertion/call.  The
# focused test deliberately reads this stable map independently of the rendered
# test text so a category cannot silently disappear during template changes.
_COVERAGE_BY_INDEX = (
    ("normal", "empty", "invalid", "absent_tie", "overflow_tail", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "overflow_tail", "malformed", "boundary"),
    ("normal", "empty", "invalid", "overflow_tail", "malformed", "boundary"),
    ("normal", "empty", "invalid", "overflow_tail", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "overflow_tail", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "overflow_tail", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "malformed", "boundary"),
    (
        "normal",
        "empty",
        "invalid",
        "duplicate_order",
        "absent_tie",
        "overflow_tail",
        "malformed",
        "boundary",
    ),
    ("normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"),
    ("normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"),
    (
        "normal",
        "empty",
        "invalid",
        "duplicate_order",
        "absent_tie",
        "overflow_tail",
        "malformed",
        "boundary",
    ),
    ("normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"),
    (
        "normal",
        "empty",
        "invalid",
        "duplicate_order",
        "absent_tie",
        "overflow_tail",
        "malformed",
        "boundary",
    ),
    ("normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"),
    (
        "normal",
        "empty",
        "invalid",
        "duplicate_order",
        "absent_tie",
        "overflow_tail",
        "malformed",
        "boundary",
    ),
    ("normal", "invalid", "duplicate_order", "malformed", "boundary"),
    ("normal", "invalid", "overflow_tail", "malformed", "boundary"),
    (
        "normal",
        "empty",
        "invalid",
        "duplicate_order",
        "absent_tie",
        "overflow_tail",
        "malformed",
        "boundary",
    ),
    (
        "normal",
        "empty",
        "invalid",
        "duplicate_order",
        "absent_tie",
        "overflow_tail",
        "malformed",
        "boundary",
    ),
    (
        "normal",
        "empty",
        "invalid",
        "duplicate_order",
        "absent_tie",
        "overflow_tail",
        "malformed",
        "boundary",
    ),
    ("normal", "empty", "invalid", "overflow_tail", "malformed", "boundary"),
)
CASE_COVERAGE: dict[str, tuple[str, ...]] = {
    case.task_id: _COVERAGE_BY_INDEX[index] for index, case in enumerate(CASES)
}
BEHAVIOR_CASES: dict[str, dict[str, str]] = {
    case.task_id: {
        category: (
            f"{case.title}: {RULES[index]} "
            + {
                "normal": "The canonical example fixes every emitted field and decoded result.",
                "empty": "The zero-element request preserves the task's explicit empty-state metadata.",
                "invalid": "A structurally invalid request returns the default result without partial state.",
                "duplicate_order": "A reversed or repeated element executes the published duplicate and ordering decision.",
                "absent_tie": "An absent lookup or equality edge executes the documented tie-selection rule.",
                "overflow_tail": "The largest value or final partial group executes checked arithmetic and tail handling.",
                "malformed": "A shape or representation inconsistency executes the canonical-state rejection path.",
                "boundary": "A one-element or exact-limit request executes the inclusive/exclusive boundary rule.",
            }[category]
        )
        for category in CASE_COVERAGE[case.task_id]
    }
    for index, case in enumerate(CASES)
}


def _api(index: int) -> tuple[str, ...]:
    return API_FIELDS[index]


def _header(case: Case, index: int) -> str:
    guard = case.snake.upper() + "_H"
    values, width, parameter, data, aux, restored, scalar = _api(index)
    request = case.result_type.removesuffix("Result") + "Request"
    special = {
        5: f"""struct {request} {{ std::vector<int> nullable_values; int null_sentinel=-1; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> dictionary_ids; std::vector<int> sorted_dictionary; std::vector<int> validity_words; std::vector<int> decoded_values; int null_count=0; }};""",
        6: f"""struct {request} {{ std::vector<std::string> ordered_paths; int anchor_stride=1; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> common_prefix_lengths; std::vector<std::string> suffixes; std::vector<std::string> anchors; std::vector<std::string> decoded_paths; int anchor_count=0; }};""",
        7: f"""struct {request} {{ std::vector<std::vector<int>> rows; std::size_t maximum_row_length=0; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> payload; std::vector<int> row_offsets; std::vector<std::vector<int>> decoded_rows; int row_count=0; }};""",
        9: f"""struct {request} {{ std::vector<int> ids; std::vector<int> values; std::vector<int> value_validity; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> id_column; std::vector<int> value_column; std::vector<int> validity_words; std::vector<int> decoded_records; int row_count=0; }};""",
        10: f"""struct {request} {{ std::vector<std::string> source_schema; std::vector<std::string> requested_schema; std::vector<int> flat_table; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> permuted_cells; std::vector<int> schema_map; std::vector<int> decoded_table; int row_count=0; }};""",
        17: f"""struct {request} {{ std::vector<int> members; int divisor=0; int universe_limit=0; int query_member=0; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> remainders; std::vector<int> bucket_offsets; std::vector<int> decoded_members; int bucket_count=0; bool contains_member=false; }};""",
        18: f"""struct {request} {{ std::vector<int> dense_cells; std::vector<int> shape; std::vector<int> block_shape; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> block_coordinates; std::vector<int> dense_block_payloads; std::vector<int> block_offsets; std::vector<int> decoded_cells; int nonzero_block_count=0; }};""",
        22: f"""struct {request} {{ std::vector<int> update_triples; int coordinate_limit=0; int default_value=0; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> overlay_pairs; std::vector<int> sequence_metadata; std::vector<int> decoded_overlay; int coordinate_count=0; }};""",
    }.get(index)
    includes = (
        "#include <cstddef>\n#include <string>\n#include <vector>"
        if index in {6, 7, 10}
        else "#include <vector>"
    )
    declaration = (
        special
        or f"""struct {request} {{ std::vector<int> {values}; int {width}=0; int {parameter}=0; }};
struct {case.result_type} {{ bool valid=false; std::vector<int> {data}; std::vector<int> {aux}; std::vector<int> {restored}; int {scalar}=0; }};"""
    )
    return f"""#ifndef {guard}
#define {guard}
{includes}
namespace representation_curriculum {{
{declaration}
{case.result_type} {case.snake}(const {request}& request);
bool validate_{case.snake}_encoding(const {request}& request, const {case.result_type}& encoded);
}}
#endif
"""


def _validator_name(case: Case) -> str:
    return f"validate_{case.snake}_encoding"


def _validator_body(index: int) -> str:
    """Return an independent structural validator for one emitted encoding.

    The validator consumes the public request and the mutable result fields.  It
    never calls the encoder.  Request data is used only to bind canonical form,
    decoded semantics, and query answers to the operation that emitted it.
    """
    bodies = (
        r"""if(width<=0)return false;
  for(int bit:values)if(bit<0||bit>1)return false;
  const std::size_t words=(values.size()+29U)/30U;
  if(result.aux.size()!=words||result.restored.size()!=values.size())return false;
  for(std::size_t w=0;w<words;++w){if(result.aux[w]<0||result.aux[w]>0x3fffffff)return false;for(int bit=0;bit<30;++bit){const std::size_t p=w*30U+static_cast<std::size_t>(bit);const int stored=(result.aux[w]>>bit)&1;if(p<values.size()){if(stored!=values[p]||result.restored[p]!=stored)return false;}else if(stored!=0)return false;}}
  std::vector<int> checkpoints;int rank=0;for(std::size_t i=0;i<values.size();++i){rank+=values[i];if((i+1U)%static_cast<std::size_t>(width)==0U||i+1U==values.size())checkpoints.push_back(rank);}if(result.data!=checkpoints)return false;
  int answer=-1;if(parameter>=0&&static_cast<std::size_t>(parameter)<=values.size()){const std::size_t query=static_cast<std::size_t>(parameter),completed=query/static_cast<std::size_t>(width),begin=completed*static_cast<std::size_t>(width);answer=completed==0U?0:result.data[completed-1U];for(std::size_t i=begin;i<query;++i)answer+=(result.aux[i/30U]>>static_cast<int>(i%30U))&1;}return result.scalar==answer;""",
        r"""if(width<=0)return false;for(int value:values)if(value<0)return false;if(result.data.size()!=values.size()||result.restored!=values)return false;const std::size_t blocks=(values.size()+static_cast<std::size_t>(width)-1U)/static_cast<std::size_t>(width);if(result.aux.size()!=blocks||result.scalar!=static_cast<int>(blocks))return false;for(std::size_t block=0;block<blocks;++block){const std::size_t begin=block*static_cast<std::size_t>(width),end=std::min(values.size(),begin+static_cast<std::size_t>(width));const int base=*std::min_element(values.begin()+static_cast<std::ptrdiff_t>(begin),values.begin()+static_cast<std::ptrdiff_t>(end));if(result.aux[block]!=base)return false;for(std::size_t i=begin;i<end;++i)if(result.data[i]<0||result.data[i]!=values[i]-base)return false;}return true;""",
        r"""if(result.aux.size()!=values.size()||result.restored.size()!=values.size()||result.scalar!=static_cast<int>(result.data.size()))return false;std::size_t begin=0;for(std::size_t group=0;group<result.aux.size();++group){const int end_value=result.aux[group];if(end_value<=static_cast<int>(begin)||end_value>static_cast<int>(result.data.size()))return false;const std::size_t end=static_cast<std::size_t>(end_value),length=end-begin;if(length>5U)return false;unsigned long long mapped=0;for(std::size_t p=begin;p<end;++p){const int byte=result.data[p];if(byte<0||byte>255)return false;const bool last=p+1U==end;if(last==((byte&128)!=0))return false;mapped|=static_cast<unsigned long long>(byte&127)<<(7U*(p-begin));}if(length>1U&&(result.data[end-1U]&127)==0)return false;const long long decoded=(mapped&1ULL)!=0ULL?-static_cast<long long>((mapped+1ULL)/2ULL):static_cast<long long>(mapped/2ULL);if(decoded<std::numeric_limits<int>::min()||decoded>std::numeric_limits<int>::max()||static_cast<int>(decoded)!=values[group]||result.restored[group]!=values[group])return false;begin=end;}return begin==result.data.size();""",
        r"""if(width<1||width>16||result.aux!=std::vector<int>{static_cast<int>(values.size()),width}||result.restored!=values)return false;for(int value:values)if(value<0||value>=(1<<width))return false;if(values.size()>std::numeric_limits<std::size_t>::max()/static_cast<std::size_t>(width))return false;const std::size_t total_bits=values.size()*static_cast<std::size_t>(width),words=(total_bits+29U)/30U;if(result.data.size()!=words||result.scalar!=static_cast<int>(words))return false;for(std::size_t word=0;word<words;++word)if(result.data[word]<0||result.data[word]>0x3fffffff)return false;if(total_bits%30U!=0U&&!result.data.empty()){const int used=static_cast<int>(total_bits%30U);if((result.data.back()>>used)!=0)return false;}for(std::size_t i=0;i<values.size();++i){const std::size_t bit=i*static_cast<std::size_t>(width),word=bit/30U;const int offset=static_cast<int>(bit%30U);long long joined=result.data[word];if(offset+width>30)joined|=static_cast<long long>(result.data[word+1U])<<30;if(static_cast<int>((joined>>offset)&((1LL<<width)-1LL))!=values[i])return false;}return true;""",
        r"""if(result.data.size()!=result.aux.size()||result.restored!=values||result.scalar!=static_cast<int>(result.data.size()))return false;if(values.empty())return result.data.empty();int prior=0;for(std::size_t run=0;run<result.data.size();++run){const int end=result.aux[run];if(result.data[run]<0||end<=prior||static_cast<std::size_t>(end)>values.size()||(run>0&&result.data[run]==result.data[run-1U]))return false;for(int i=prior;i<end;++i)if(values[static_cast<std::size_t>(i)]!=result.data[run])return false;prior=end;}return static_cast<std::size_t>(prior)==values.size();""",
        r"""if(parameter>=0||result.data.size()!=values.size()||result.restored!=values)return false;if(!std::is_sorted(result.aux.begin(),result.aux.end())||std::adjacent_find(result.aux.begin(),result.aux.end())!=result.aux.end())return false;const std::size_t words=(values.size()+29U)/30U;if(result.validity_words.size()!=words)return false;int nulls=0;for(std::size_t i=0;i<values.size();++i){const bool present=((result.validity_words[i/30U]>>static_cast<int>(i%30U))&1)!=0;const int id=result.data[i];if(values[i]==parameter){if(present||id!=-1)return false;++nulls;}else if(!present||id<0||static_cast<std::size_t>(id)>=result.aux.size()||result.aux[static_cast<std::size_t>(id)]!=values[i])return false;}if(!result.validity_words.empty()&&values.size()%30U!=0U&&result.validity_words.back()>>static_cast<int>(values.size()%30U)!=0)return false;return result.scalar==nulls;""",
        r"""if(width<=0||result.data.size()!=values.size()||result.suffixes.size()!=values.size()||result.restored!=values)return false;std::vector<std::string> anchors;std::string prior;for(std::size_t i=0;i<values.size();++i){if(i>0&&values[i]<=values[i-1U])return false;std::size_t prefix=0;while(prefix<prior.size()&&prefix<values[i].size()&&prior[prefix]==values[i][prefix])++prefix;if(result.data[i]!=static_cast<int>(prefix)||result.suffixes[i]!=values[i].substr(prefix))return false;if(i%static_cast<std::size_t>(width)==0U)anchors.push_back(values[i]);prior=values[i];}return result.anchors==anchors&&result.scalar==static_cast<int>(anchors.size());""",
        r"""if(width==0U||result.aux.size()!=values.size()+1U||result.aux.empty()||result.aux.front()!=0||result.aux.back()!=static_cast<int>(result.data.size())||result.restored!=values||result.scalar!=static_cast<int>(values.size()))return false;std::size_t cursor=0;for(std::size_t row=0;row<values.size();++row){if(values[row].size()>width||result.aux[row]!=static_cast<int>(cursor))return false;for(int value:values[row]){if(cursor>=result.data.size()||result.data[cursor++]!=value)return false;}if(result.aux[row+1U]!=static_cast<int>(cursor))return false;}return cursor==result.data.size();""",
        r"""if(width<=0||values.size()%static_cast<std::size_t>(width)!=0U||result.restored!=values||result.data.size()!=values.size()/static_cast<std::size_t>(width)||result.scalar<0)return false;if(result.aux.size()!=static_cast<std::size_t>(result.scalar)*static_cast<std::size_t>(width))return false;for(int row=0;row<result.scalar;++row){const auto begin=result.aux.begin()+static_cast<std::ptrdiff_t>(row*width),end=begin+width;if(row>0&&!std::lexicographical_compare(result.aux.begin()+static_cast<std::ptrdiff_t>((row-1)*width),result.aux.begin()+static_cast<std::ptrdiff_t>(row*width),begin,end))return false;}for(std::size_t row=0;row<result.data.size();++row){const int id=result.data[row];if(id<0||id>=result.scalar)return false;for(int column=0;column<width;++column)if(result.aux[static_cast<std::size_t>(id*width+column)]!=values[row*static_cast<std::size_t>(width)+static_cast<std::size_t>(column)])return false;}return true;""",
        r"""const std::size_t rows=request.ids.size();if(rows!=request.values.size()||rows!=request.value_validity.size()||result.data!=request.ids||result.data.size()!=result.aux.size()||result.scalar!=static_cast<int>(rows)||result.restored.size()!=2U*rows)return false;std::set<int> ids;const std::size_t words=(rows+29U)/30U;if(result.validity_words.size()!=words)return false;for(std::size_t i=0;i<rows;++i){if(request.ids[i]<0||!ids.insert(request.ids[i]).second||request.value_validity[i]<0||request.value_validity[i]>1)return false;const bool present=((result.validity_words[i/30U]>>static_cast<int>(i%30U))&1)!=0;if(present!=(request.value_validity[i]!=0)||result.aux[i]!=(present?request.values[i]:0)||result.restored[2U*i]!=request.ids[i]||result.restored[2U*i+1U]!=result.aux[i])return false;}if(!result.validity_words.empty()&&rows%30U!=0U&&result.validity_words.back()>>static_cast<int>(rows%30U)!=0)return false;return true;""",
        r"""const std::size_t width=request.source_schema.size();if(width==0U||request.requested_schema.size()!=width||request.flat_table.size()%width!=0U||result.data.size()!=request.flat_table.size()||result.restored!=request.flat_table||result.scalar!=static_cast<int>(request.flat_table.size()/width)||result.aux.size()!=width)return false;std::set<std::string> source,requested;std::set<int> mapped;for(const auto& name:request.source_schema)if(name.empty()||!source.insert(name).second)return false;for(std::size_t i=0;i<width;++i){if(request.requested_schema[i].empty()||!requested.insert(request.requested_schema[i]).second)return false;const int column=result.aux[i];if(column<0||static_cast<std::size_t>(column)>=width||!mapped.insert(column).second||request.source_schema[static_cast<std::size_t>(column)]!=request.requested_schema[i])return false;}if(source!=requested)return false;for(std::size_t row=0;row<request.flat_table.size();row+=width)for(std::size_t column=0;column<width;++column)if(result.data[row+column]!=request.flat_table[row+static_cast<std::size_t>(result.aux[column])])return false;return true;""",
        r"""if(width<=0||parameter<0||values.size()%2U!=0U||static_cast<std::size_t>(parameter)!=values.size()/2U||parameter%width!=0||result.aux!=std::vector<int>(values.begin(),values.begin()+parameter)||result.restored!=values||result.data.size()%2U!=0U||result.scalar!=static_cast<int>(result.data.size()/2U))return false;std::size_t patch=0;for(int i=0;i<parameter;++i){const bool changed=values[static_cast<std::size_t>(i)]!=values[static_cast<std::size_t>(parameter+i)];if(changed){if(patch+1U>=result.data.size()||result.data[patch]!=i||result.data[patch+1U]!=values[static_cast<std::size_t>(parameter+i)])return false;patch+=2U;}}return patch==result.data.size();""",
        r"""if(parameter<0||static_cast<std::size_t>(parameter)>values.size()||result.data.size()!=result.aux.size()||result.restored!=values||result.scalar!=static_cast<int>(result.data.size()))return false;for(int i=1;i<parameter;++i)if(values[static_cast<std::size_t>(i)]<=values[static_cast<std::size_t>(i-1)])return false;for(std::size_t i=static_cast<std::size_t>(parameter)+1U;i<values.size();++i)if(values[i]<=values[i-1U])return false;std::vector<int> left,right;for(std::size_t i=0;i<result.data.size();++i){if(i>0&&result.data[i]<=result.data[i-1U])return false;const int mask=result.aux[i];if(mask<1||mask>3)return false;if((mask&1)!=0)left.push_back(result.data[i]);if((mask&2)!=0)right.push_back(result.data[i]);}return left==std::vector<int>(values.begin(),values.begin()+parameter)&&right==std::vector<int>(values.begin()+parameter,values.end());""",
        r"""if(parameter<0||static_cast<std::size_t>(parameter)>values.size()||result.data!=std::vector<int>(values.begin()+parameter,values.end())||result.aux.size()!=static_cast<std::size_t>(parameter)+result.data.size()||result.restored!=values||result.scalar!=static_cast<int>(result.data.size()))return false;for(int i=1;i<parameter;++i)if(values[static_cast<std::size_t>(i)]<=values[static_cast<std::size_t>(i-1)])return false;for(std::size_t i=static_cast<std::size_t>(parameter)+1U;i<values.size();++i)if(values[i]<values[i-1U])return false;for(int i=0;i<parameter;++i)if(result.aux[static_cast<std::size_t>(i)]!=values[static_cast<std::size_t>(i)])return false;for(std::size_t e=0;e<result.data.size();++e){int expected=-1;for(int snapshot=0;snapshot<parameter&&values[static_cast<std::size_t>(snapshot)]<=result.data[e];++snapshot)expected=values[static_cast<std::size_t>(snapshot)];if(result.aux[static_cast<std::size_t>(parameter)+e]!=expected)return false;}return true;""",
        r"""if(width!=2||values.size()%2U!=0U||result.data.size()%2U!=0U||result.restored!=result.data||result.aux!=std::vector<int>{result.scalar})return false;std::map<int,long long> combined;for(std::size_t i=0;i<values.size();i+=2U){if(values[i]<0)return false;const long long sum=combined[values[i]]+static_cast<long long>(values[i+1]);if(sum<std::numeric_limits<int>::min()||sum>std::numeric_limits<int>::max())return false;combined[values[i]]=sum;}std::size_t cursor=0;for(const auto& [exponent,coefficient]:combined)if(coefficient!=0){if(cursor+1U>=result.data.size()||result.data[cursor]!=exponent||result.data[cursor+1U]!=coefficient)return false;cursor+=2U;}if(cursor!=result.data.size())return false;long long evaluation=0;for(std::size_t i=0;i<result.data.size();i+=2U){long long power=1;for(int exponent=0;exponent<result.data[i];++exponent){if(parameter!=0&&(power>std::numeric_limits<int>::max()/std::abs(static_cast<long long>(parameter))||power<std::numeric_limits<int>::min()/std::abs(static_cast<long long>(parameter))))return false;power*=parameter;}const long long term=power*static_cast<long long>(result.data[i+1U]);if(term<std::numeric_limits<int>::min()||term>std::numeric_limits<int>::max()||evaluation+term<std::numeric_limits<int>::min()||evaluation+term>std::numeric_limits<int>::max())return false;evaluation+=term;}return result.scalar==evaluation;""",
        r"""if(width!=2||parameter<=0||values.size()%2U!=0U||result.aux.size()!=static_cast<std::size_t>(parameter)+1U||result.aux.front()!=0||result.aux.back()!=static_cast<int>(result.data.size())||result.scalar!=static_cast<int>(result.data.size())||result.restored.size()%2U!=0U)return false;std::set<std::pair<int,int>> expected;for(std::size_t i=0;i<values.size();i+=2U){int a=values[i],b=values[i+1U];if(a<0||b<0||a>=parameter||b>=parameter||a==b)return false;auto edge=std::minmax(a,b);if(!expected.insert(edge).second)return false;}std::set<std::pair<int,int>> decoded;for(int vertex=0;vertex<parameter;++vertex){const int begin=result.aux[static_cast<std::size_t>(vertex)],end=result.aux[static_cast<std::size_t>(vertex+1)];if(begin<0||end<begin||end>static_cast<int>(result.data.size()))return false;int prior=-1;for(int p=begin;p<end;++p){const int neighbor=p==begin?result.data[static_cast<std::size_t>(p)]:prior+result.data[static_cast<std::size_t>(p)];if(neighbor<0||neighbor>=parameter||neighbor==vertex||neighbor<=prior)return false;if(vertex<neighbor)decoded.emplace(vertex,neighbor);prior=neighbor;}}return decoded==expected&&result.restored==std::vector<int>([&](){std::vector<int> flat;for(const auto& edge:expected)flat.insert(flat.end(),{edge.first,edge.second});return flat;}());""",
        r"""if(width<=0||result.data.size()!=values.size()||result.restored!=values||result.aux.size()!=2U*((values.size()+static_cast<std::size_t>(width)-1U)/static_cast<std::size_t>(width)))return false;int posting=0;for(std::size_t i=0;i<result.data.size();++i){if(result.data[i]<(i==0?0:1))return false;posting=i==0?result.data[i]:posting+result.data[i];if(posting!=values[i])return false;}for(std::size_t checkpoint=0;checkpoint<result.aux.size();checkpoint+=2U){const std::size_t expected=(checkpoint/2U)*static_cast<std::size_t>(width);if(result.aux[checkpoint]!=static_cast<int>(expected)||expected>=values.size()||result.aux[checkpoint+1U]!=values[expected])return false;}const bool present=std::binary_search(values.begin(),values.end(),parameter);return result.scalar==(present?1:0);""",
        r"""if(width<=0||parameter<=0||result.restored!=values)return false;const int buckets=1+(parameter-1)/width;if(result.scalar!=buckets||result.aux.size()!=static_cast<std::size_t>(buckets)+1U||result.aux.front()!=0||result.aux.back()!=static_cast<int>(result.data.size()))return false;std::vector<int> decoded;for(int bucket=0;bucket<buckets;++bucket){const int begin=result.aux[static_cast<std::size_t>(bucket)],end=result.aux[static_cast<std::size_t>(bucket+1)];if(begin<0||end<begin||end>static_cast<int>(result.data.size()))return false;int prior=-1;for(int p=begin;p<end;++p){const int remainder=result.data[static_cast<std::size_t>(p)];if(remainder<0||remainder>=width||remainder<=prior)return false;const long long member=static_cast<long long>(bucket)*width+remainder;if(member>=parameter)return false;decoded.push_back(static_cast<int>(member));prior=remainder;}}if(decoded!=values)return false;const bool present=request.query_member>=0&&request.query_member<parameter&&std::binary_search(values.begin(),values.end(),request.query_member);return result.contains_member==present;""",
        r"""if(request.shape.size()!=3U||request.block_shape.size()!=3U||result.restored!=request.dense_cells||result.data.size()%3U!=0U||result.block_offsets.empty()||result.block_offsets.front()!=0)return false;long long cells=1,volume=1;for(int extent:request.shape){if(extent<=0||cells>std::numeric_limits<long long>::max()/extent)return false;cells*=extent;}for(int extent:request.block_shape){if(extent<=0||volume>std::numeric_limits<long long>::max()/extent)return false;volume*=extent;}if(cells!=static_cast<long long>(request.dense_cells.size())||volume>std::numeric_limits<int>::max())return false;const std::size_t blocks=result.data.size()/3U;if(result.block_offsets.size()!=blocks+1U||result.scalar!=static_cast<int>(blocks)||result.dense_block_payloads.size()!=blocks*static_cast<std::size_t>(volume))return false;std::vector<int> decoded(request.dense_cells.size(),0);std::vector<int> prior;for(std::size_t block=0;block<blocks;++block){std::vector<int> coordinate(result.data.begin()+static_cast<std::ptrdiff_t>(3U*block),result.data.begin()+static_cast<std::ptrdiff_t>(3U*block+3U));for(std::size_t axis=0;axis<3U;++axis)if(coordinate[axis]<0||static_cast<long long>(coordinate[axis])*request.block_shape[axis]>=request.shape[axis])return false;if(block>0&&!std::lexicographical_compare(prior.begin(),prior.end(),coordinate.begin(),coordinate.end()))return false;prior=coordinate;if(result.block_offsets[block]!=static_cast<int>(block*static_cast<std::size_t>(volume))||result.block_offsets[block+1U]!=static_cast<int>((block+1U)*static_cast<std::size_t>(volume)))return false;bool logical_nonzero=false;std::size_t cursor=static_cast<std::size_t>(result.block_offsets[block]);for(int dz=0;dz<request.block_shape[0];++dz)for(int dy=0;dy<request.block_shape[1];++dy)for(int dx=0;dx<request.block_shape[2];++dx){const long long z=static_cast<long long>(coordinate[0])*request.block_shape[0]+dz,y=static_cast<long long>(coordinate[1])*request.block_shape[1]+dy,x=static_cast<long long>(coordinate[2])*request.block_shape[2]+dx;const int value=result.dense_block_payloads[cursor++];if(z<request.shape[0]&&y<request.shape[1]&&x<request.shape[2]){const std::size_t position=(static_cast<std::size_t>(z)*static_cast<std::size_t>(request.shape[1])+static_cast<std::size_t>(y))*static_cast<std::size_t>(request.shape[2])+static_cast<std::size_t>(x);decoded[position]=value;logical_nonzero=logical_nonzero||value!=0;}else if(value!=0)return false;}if(!logical_nonzero)return false;}return decoded==request.dense_cells;""",
        r"""if(width<=0||static_cast<std::size_t>(width)>std::numeric_limits<std::size_t>::max()/static_cast<std::size_t>(width)||static_cast<std::size_t>(width)*static_cast<std::size_t>(width)!=values.size()||result.restored!=values)return false;const std::size_t packed=static_cast<std::size_t>(width)*(static_cast<std::size_t>(width)+1U)/2U;if(result.data.size()!=packed||result.aux.size()!=static_cast<std::size_t>(width)+1U||result.aux.front()!=0||result.aux.back()!=static_cast<int>(packed)||result.scalar!=static_cast<int>(packed))return false;std::size_t cursor=0;for(int row=0;row<width;++row){if(result.aux[static_cast<std::size_t>(row)]!=static_cast<int>(cursor))return false;for(int column=row;column<width;++column){const int value=values[static_cast<std::size_t>(row*width+column)];if(value!=values[static_cast<std::size_t>(column*width+row)]||result.data[cursor++]!=value)return false;}if(result.aux[static_cast<std::size_t>(row+1)]!=static_cast<int>(cursor))return false;}return true;""",
        r"""if(width<=0||(width&(width-1))!=0||static_cast<std::size_t>(width)>std::numeric_limits<std::size_t>::max()/static_cast<std::size_t>(width)||values.size()!=static_cast<std::size_t>(width)*static_cast<std::size_t>(width)||result.aux!=std::vector<int>{width}||result.restored!=values)return false;for(int value:values)if(value<0||value>1)return false;std::size_t cursor=0;int leaves=0;std::vector<int> decoded(values.size(),0);std::function<bool(int,int,int,int&)> read=[&](int row,int column,int size,int& uniform){if(cursor>=result.data.size())return false;const int tag=result.data[cursor++];if(tag==0){if(cursor>=result.data.size())return false;const int value=result.data[cursor++];if(value<0||value>1)return false;for(int y=row;y<row+size;++y)for(int x=column;x<column+size;++x)decoded[static_cast<std::size_t>(y*width+x)]=value;uniform=value;++leaves;return true;}if(tag!=1||size==1)return false;const int half=size/2;int a=-1,b=-1,c=-1,d=-1;if(!read(row,column,half,a)||!read(row,column+half,half,b)||!read(row+half,column,half,c)||!read(row+half,column+half,half,d))return false;if(a>=0&&a==b&&a==c&&a==d)return false;uniform=-1;return true;};int uniform=-1;return read(0,0,width,uniform)&&cursor==result.data.size()&&decoded==values&&result.scalar==leaves;""",
        r"""for(int value:values)if(value<0||value>1)return false;if(result.aux!=std::vector<int>{static_cast<int>(values.size())}||result.restored!=values||result.data.size()%2U!=0U)return false;int prior_end=-1;for(std::size_t i=0;i<result.data.size();i+=2U){const int begin=result.data[i],end=result.data[i+1U];if(begin<0||begin>=end||static_cast<std::size_t>(end)>values.size()||(prior_end>=0&&begin<=prior_end))return false;for(int p=begin;p<end;++p)if(values[static_cast<std::size_t>(p)]!=1)return false;if(begin>0&&values[static_cast<std::size_t>(begin-1)]!=0)return false;if(static_cast<std::size_t>(end)<values.size()&&values[static_cast<std::size_t>(end)]!=0)return false;prior_end=end;}for(std::size_t p=0;p<values.size();++p){bool covered=false;for(std::size_t i=0;i<result.data.size();i+=2U)covered=covered||(result.data[i]<=static_cast<int>(p)&&static_cast<int>(p)<result.data[i+1U]);if(covered!=(values[p]!=0))return false;}const int query=parameter>=0&&static_cast<std::size_t>(parameter)<values.size()?values[static_cast<std::size_t>(parameter)]:0;return result.scalar==query;""",
        r"""if(width<=0||values.size()%3U!=0U||result.restored.size()!=static_cast<std::size_t>(width)||result.data.size()%2U!=0U||result.aux.size()%2U!=0U||result.scalar!=static_cast<int>(result.data.size()/2U))return false;std::map<int,std::pair<int,int>> latest;std::map<int,std::set<int>> seen;for(std::size_t i=0;i<values.size();i+=3U){const int coordinate=values[i],sequence=values[i+1U],value=values[i+2U];if(coordinate<0||coordinate>=width||!seen[coordinate].insert(sequence).second)return false;auto found=latest.find(coordinate);if(found==latest.end()||sequence>found->second.first)latest[coordinate]={sequence,value};}std::vector<int> overlay,metadata,decoded(static_cast<std::size_t>(width),parameter);for(const auto& [coordinate,winner]:latest){metadata.insert(metadata.end(),{coordinate,winner.first});if(winner.second!=parameter){overlay.insert(overlay.end(),{coordinate,winner.second});decoded[static_cast<std::size_t>(coordinate)]=winner.second;}}return result.data==overlay&&result.aux==metadata&&result.restored==decoded;""",
        r"""for(int value:values)if(value<0)return false;if(result.aux!=std::vector<int>{static_cast<int>(values.size())}||result.restored!=values||result.data.size()%2U!=0U||result.scalar!=static_cast<int>(result.data.size()/2U))return false;int prior=-1;for(std::size_t i=0;i<result.data.size();i+=2U){const int gap=result.data[i],count=result.data[i+1U];if(gap<0||count<=0||prior>std::numeric_limits<int>::max()-1-gap)return false;const int position=prior+1+gap;if(position<0||static_cast<std::size_t>(position)>=values.size()||values[static_cast<std::size_t>(position)]!=count)return false;for(int skipped=prior+1;skipped<position;++skipped)if(values[static_cast<std::size_t>(skipped)]!=0)return false;prior=position;}for(std::size_t i=static_cast<std::size_t>(prior+1);i<values.size();++i)if(values[i]!=0)return false;return true;""",
        r"""for(int value:values)if(value<0||value>255)return false;const int words=static_cast<int>((values.size()+29U)/30U);if(result.aux!=std::vector<int>{static_cast<int>(values.size()),words}||result.data.size()!=static_cast<std::size_t>(8*words)||result.restored!=values||result.scalar!=8)return false;for(int word:result.data)if(word<0||word>0x3fffffff)return false;if(words>0&&values.size()%30U!=0U){const int used=static_cast<int>(values.size()%30U);for(int bit=0;bit<8;++bit)if(result.data[static_cast<std::size_t>(bit*words+words-1)]>>used!=0)return false;}for(std::size_t row=0;row<values.size();++row)for(int bit=0;bit<8;++bit)if(((result.data[static_cast<std::size_t>(bit*words+static_cast<int>(row/30U))]>>static_cast<int>(row%30U))&1)!=((values[row]>>bit)&1))return false;return true;""",
    )
    return bodies[index]


def _validator_function(case: Case, index: int, *, opposite: bool = False) -> str:
    request = case.result_type.removesuffix("Result") + "Request"
    values_name, width_name, parameter_name, data_name, aux_name, restored_name, scalar_name = _api(
        index
    )
    declarations = {
        5: "const auto& values=request.nullable_values;const int parameter=request.null_sentinel;",
        6: "const auto& values=request.ordered_paths;const int width=request.anchor_stride;",
        7: "const auto& values=request.rows;const std::size_t width=request.maximum_row_length;",
        9: "",
        10: "",
        18: "",
    }.get(
        index,
        f"const auto& values=request.{values_name};const int width=request.{width_name};const int parameter=request.{parameter_name};",
    )
    body = _validator_body(index)
    for old, new in (
        ("result.data", f"result.{data_name}"),
        ("result.aux", f"result.{aux_name}"),
        ("result.restored", f"result.{restored_name}"),
        ("result.scalar", f"result.{scalar_name}"),
    ):
        body = body.replace(old, new)
    body = (
        body.replace(";", ";\n")
        .replace("}if", "}\nif")
        .replace("}for", "}\nfor")
        .replace("}return", "}\nreturn")
    )
    normalization = "const auto& result=encoded;"
    if opposite:
        normalization = (
            f"auto normalized=encoded;std::reverse(normalized.{data_name}.begin(),"
            f"normalized.{data_name}.end());const auto& result=normalized;"
        )
    formatted_normalization = normalization.replace(";", ";\n  ")
    formatted_declarations = declarations.replace(";", ";\n  ")
    if " width=" in declarations:
        formatted_declarations += "(void)width;\n  "
    if " parameter=" in declarations:
        formatted_declarations += "(void)parameter;\n  "
    return f"""bool {_validator_name(case)}(const {request}& request, const {case.result_type}& encoded){{
  if(!encoded.valid)return false;
  {formatted_normalization}{formatted_declarations}
  {body}
}}
"""


def _algorithm_body(index: int) -> str:
    bodies = (
        "int rank=0;for(std::size_t i=0;i<values.size();++i){if(values[i]>1)return out;rank+=values[i];if((i+1)%static_cast<std::size_t>(width)==0||i+1==values.size())out.data.push_back(rank);}for(std::size_t b=0;b<values.size();b+=30U){int word=0;for(std::size_t j=0;j<30U&&b+j<values.size();++j)word|=values[b+j]<<static_cast<int>(j);out.aux.push_back(word);}",
        "for(std::size_t b=0;b<values.size();b+=static_cast<std::size_t>(width)){std::size_t e=std::min(values.size(),b+static_cast<std::size_t>(width));int base=*std::min_element(values.begin()+static_cast<std::ptrdiff_t>(b),values.begin()+static_cast<std::ptrdiff_t>(e));out.aux.push_back(base);for(std::size_t i=b;i<e;++i)out.data.push_back(values[i]-base);}out.scalar=static_cast<int>(out.aux.size());",
        "for(int value:values){unsigned long long mapped=value>=0?2ULL*static_cast<unsigned long long>(value):2ULL*static_cast<unsigned long long>(-(static_cast<long long>(value)))-1ULL;do{int byte=static_cast<int>(mapped&127ULL);mapped>>=7U;if(mapped!=0U)byte|=128;out.data.push_back(byte);}while(mapped!=0U);out.aux.push_back(static_cast<int>(out.data.size()));}",
        "if(width>16)return out;for(int value:values)if(value>=(1<<width))return out;long long buffer=0;int bits=0;for(int value:values){buffer|=static_cast<long long>(value)<<bits;bits+=width;while(bits>=30){out.data.push_back(static_cast<int>(buffer&0x3fffffffLL));buffer>>=30;bits-=30;}}if(bits>0)out.data.push_back(static_cast<int>(buffer));out.aux={static_cast<int>(values.size()),width};",
        "for(std::size_t i=0;i<values.size();){std::size_t j=i+1;while(j<values.size()&&values[j]==values[i])++j;out.data.push_back(values[i]);out.aux.push_back(static_cast<int>(j));i=j;}out.scalar=static_cast<int>(values.size());",
        "std::vector<int> dictionary;for(int value:values)if(value!=parameter)dictionary.push_back(value);std::sort(dictionary.begin(),dictionary.end());dictionary.erase(std::unique(dictionary.begin(),dictionary.end()),dictionary.end());out.aux=dictionary;for(int value:values)out.data.push_back(value==parameter?-1:static_cast<int>(std::lower_bound(dictionary.begin(),dictionary.end(),value)-dictionary.begin()));",
        "if(values.empty()){}else{out.data.push_back(values.front());for(std::size_t i=1;i<values.size();++i){if(values[i]<=values[i-1])return out;out.data.push_back(values[i]-values[i-1]);if(i%static_cast<std::size_t>(width)==0)out.aux.push_back(values[i]);}}",
        "out.aux.push_back(0);std::size_t cursor=0;int row=0;while(cursor<values.size()){std::size_t take=static_cast<std::size_t>(1+(row%std::max(1,parameter)));take=std::min(take,values.size()-cursor);for(std::size_t i=0;i<take;++i)out.data.push_back(values[cursor+i]);cursor+=take;out.aux.push_back(static_cast<int>(cursor));++row;}out.scalar=row;",
        "if(values.size()%static_cast<std::size_t>(width)!=0)return out;std::vector<std::vector<int>> rows;for(std::size_t b=0;b<values.size();b+=static_cast<std::size_t>(width))rows.emplace_back(values.begin()+static_cast<std::ptrdiff_t>(b),values.begin()+static_cast<std::ptrdiff_t>(b+static_cast<std::size_t>(width)));std::vector<std::vector<int>> dictionary=rows;std::sort(dictionary.begin(),dictionary.end());dictionary.erase(std::unique(dictionary.begin(),dictionary.end()),dictionary.end());for(const auto& row:dictionary)out.aux.insert(out.aux.end(),row.begin(),row.end());for(const auto& row:rows)out.data.push_back(static_cast<int>(std::lower_bound(dictionary.begin(),dictionary.end(),row)-dictionary.begin()));out.scalar=static_cast<int>(dictionary.size());",
        "if(width!=2||values.size()%2U!=0)return out;std::set<int> ids;for(std::size_t i=0;i<values.size();i+=2U){if(values[i]<0||!ids.insert(values[i]).second)return out;out.data.push_back(values[i]);out.aux.push_back(values[i+1]);}out.scalar=static_cast<int>(values.size()/2U);",
        "if(values.size()%static_cast<std::size_t>(width)!=0)return out;int shift=parameter%width;for(std::size_t b=0;b<values.size();b+=static_cast<std::size_t>(width))for(int c=0;c<width;++c)out.data.push_back(values[b+static_cast<std::size_t>((c+shift)%width)]);out.aux={width,shift};",
        "if(parameter<0||values.size()%2U!=0||static_cast<std::size_t>(parameter)!=values.size()/2U||parameter%width!=0)return out;out.aux.assign(values.begin(),values.begin()+parameter);for(int i=0;i<parameter;++i)if(values[static_cast<std::size_t>(i)]!=values[static_cast<std::size_t>(parameter+i)]){out.data.push_back(i);out.data.push_back(values[static_cast<std::size_t>(parameter+i)]);}out.scalar=static_cast<int>(out.data.size()/2U);",
        "if(parameter<0||static_cast<std::size_t>(parameter)>values.size())return out;for(int p=1;p<parameter;++p)if(values[static_cast<std::size_t>(p)]<=values[static_cast<std::size_t>(p-1)])return out;for(std::size_t p=static_cast<std::size_t>(parameter)+1U;p<values.size();++p)if(values[p]<=values[p-1U])return out;std::size_t i=0,j=static_cast<std::size_t>(parameter);while(i<static_cast<std::size_t>(parameter)||j<values.size()){int key;if(j>=values.size()||(i<static_cast<std::size_t>(parameter)&&values[i]<values[j])){key=values[i++];out.aux.push_back(1);}else if(i>=static_cast<std::size_t>(parameter)||values[j]<values[i]){key=values[j++];out.aux.push_back(2);}else{key=values[i];++i;++j;out.aux.push_back(3);}out.data.push_back(key);}",
        "if(parameter<0||static_cast<std::size_t>(parameter)>values.size())return out;for(int i=1;i<parameter;++i)if(values[static_cast<std::size_t>(i)]<=values[static_cast<std::size_t>(i-1)])return out;for(std::size_t i=static_cast<std::size_t>(parameter)+1;i<values.size();++i)if(values[i]<values[i-1])return out;out.aux.insert(out.aux.end(),values.begin(),values.begin()+parameter);std::size_t s=0;for(std::size_t e=static_cast<std::size_t>(parameter);e<values.size();++e){while(s<static_cast<std::size_t>(parameter)&&values[s]<=values[e])++s;out.data.push_back(values[e]);out.aux.push_back(s==0?-1:values[s-1]);}out.scalar=static_cast<int>(out.data.size());",
        "if(width!=2||values.size()%2U!=0)return out;std::map<int,long long> terms;for(std::size_t i=0;i<values.size();i+=2U){if(values[i]<0)return out;long long sum=terms[values[i]]+static_cast<long long>(values[i+1]);if(sum<-2147483648LL||sum>2147483647LL)return out;terms[values[i]]=sum;}for(const auto& item:terms)if(item.second!=0){out.data.push_back(item.first);out.data.push_back(static_cast<int>(item.second));}long long evaluated=0;int prior=out.data.empty()?0:out.data[out.data.size()-2];auto step=[&](int factor,int add){long long product=evaluated*static_cast<long long>(factor);if(product<-2147483648LL||product>2147483647LL)return false;long long sum=product+static_cast<long long>(add);if(sum<-2147483648LL||sum>2147483647LL)return false;evaluated=sum;return true;};for(std::size_t p=out.data.size();p>0;p-=2){int exponent=out.data[p-2],coefficient=out.data[p-1];for(int gap=prior;gap>exponent;--gap)if(!step(parameter,0))return out;if(!step(1,coefficient))return out;prior=exponent;}for(int gap=prior;gap>0;--gap)if(!step(parameter,0))return out;out.scalar=static_cast<int>(evaluated);out.aux.push_back(out.scalar);",
        "if(parameter<=0||values.size()%2U!=0)return out;std::vector<std::set<int>> adj(static_cast<std::size_t>(parameter));std::set<std::pair<int,int>> edges;for(std::size_t i=0;i<values.size();i+=2U){int a=values[i],b=values[i+1];if(a<0||b<0||a>=parameter||b>=parameter||a==b)return out;const auto edge=std::minmax(a,b);if(!edges.insert(edge).second)return out;adj[static_cast<std::size_t>(a)].insert(b);adj[static_cast<std::size_t>(b)].insert(a);}out.aux.push_back(0);for(const auto& row:adj){int prior=0;bool first=true;for(int v:row){out.data.push_back(first?v:v-prior);prior=v;first=false;}out.aux.push_back(static_cast<int>(out.data.size()));}",
        "int prior=0;for(std::size_t i=0;i<values.size();++i){if(values[i]<0||(i>0&&values[i]<=values[i-1]))return out;out.data.push_back(i==0?values[i]:values[i]-prior);prior=values[i];if(i%static_cast<std::size_t>(width)==0){out.aux.push_back(static_cast<int>(i));out.aux.push_back(values[i]);}}",
        "if(parameter<=0)return out;for(std::size_t i=0;i<values.size();++i)if(values[i]<0||values[i]>=parameter||(i>0&&values[i]<=values[i-1]))return out;int buckets=1+(parameter-1)/width;out.aux.push_back(0);std::size_t cursor=0;for(int q=0;q<buckets;++q){while(cursor<values.size()&&values[cursor]/width==q){out.data.push_back(values[cursor]%width);++cursor;}out.aux.push_back(static_cast<int>(out.data.size()));}",
        "for(std::size_t i=0;i<values.size();++i)if(values[i]!=0){out.data.push_back(static_cast<int>(i/static_cast<std::size_t>(width)));out.data.push_back(static_cast<int>(i%static_cast<std::size_t>(width)));out.aux.push_back(values[i]);}out.scalar=static_cast<int>(values.size());",
        "if(static_cast<std::size_t>(width)*static_cast<std::size_t>(width)!=values.size())return out;out.aux.push_back(0);for(int r=0;r<width;++r){for(int c=r;c<width;++c){if(values[static_cast<std::size_t>(r*width+c)]!=values[static_cast<std::size_t>(c*width+r)])return out;out.data.push_back(values[static_cast<std::size_t>(r*width+c)]);}out.aux.push_back(static_cast<int>(out.data.size()));}",
        "if(static_cast<std::size_t>(width)*static_cast<std::size_t>(width)!=values.size()||(width&(width-1))!=0)return out;for(int v:values)if(v>1)return out;std::function<void(int,int,int)> visit=[&](int r,int c,int n){int first=values[static_cast<std::size_t>(r*width+c)];bool same=true;for(int y=r;y<r+n;++y)for(int x=c;x<c+n;++x)same=same&&values[static_cast<std::size_t>(y*width+x)]==first;if(same){out.data.push_back(0);out.data.push_back(first);++out.scalar;return;}out.data.push_back(1);int h=n/2;visit(r,c,h);visit(r,c+h,h);visit(r+h,c,h);visit(r+h,c+h,h);};visit(0,0,width);out.aux={width};",
        "for(std::size_t i=0;i<values.size();){if(values[i]>1)return out;if(values[i]==0){++i;continue;}std::size_t j=i+1;while(j<values.size()&&values[j]==1)++j;out.data.push_back(static_cast<int>(i));out.data.push_back(static_cast<int>(j));i=j;}out.aux={static_cast<int>(values.size())};",
        "if(values.size()%3U!=0)return out;std::map<int,std::pair<int,int>> latest;std::map<int,std::set<int>> seen;for(std::size_t i=0;i<values.size();i+=3U){int coord=values[i],seq=values[i+1],value=values[i+2];if(!seen[coord].insert(seq).second)return out;auto it=latest.find(coord);if(it==latest.end()||seq>it->second.first)latest[coord]={seq,value};}for(const auto& item:latest)if(item.second.second!=parameter){out.data.push_back(item.first);out.data.push_back(item.second.second);}out.scalar=static_cast<int>(out.data.size()/2U);",
        "int prior=-1;for(std::size_t i=0;i<values.size();++i){if(values[i]<0)return out;if(values[i]>0){out.data.push_back(static_cast<int>(i)-prior-1);out.data.push_back(values[i]);prior=static_cast<int>(i);}}out.aux={static_cast<int>(values.size())};",
        "for(int value:values)if(value>255)return out;int words=static_cast<int>((values.size()+29U)/30U);for(int bit=0;bit<8;++bit)for(int w=0;w<words;++w){int word=0;for(int j=0;j<30;++j){std::size_t i=static_cast<std::size_t>(w*30+j);if(i<values.size())word|=((values[i]>>bit)&1)<<j;}out.data.push_back(word);}out.aux={static_cast<int>(values.size()),words};",
    )
    return bodies[index]


def _decode_body(index: int) -> str:
    """Decode the emitted representation (or derive the canonical transform).

    These paths deliberately consume only encoded fields and scalar request
    metadata.  Assigning the input directly would make the round-trip oracle
    vacuous and is forbidden by the family contract.
    """
    bodies = (
        "for(std::size_t b=0;b<out.aux.size();++b)for(int j=0;j<30&&out.restored.size()<values.size();++j)out.restored.push_back((out.aux[b]>>j)&1);out.scalar=-1;if(parameter>=0&&static_cast<std::size_t>(parameter)<=values.size()){const std::size_t query=static_cast<std::size_t>(parameter);const std::size_t completed=query/static_cast<std::size_t>(width);const std::size_t begin=completed*static_cast<std::size_t>(width);out.scalar=completed==0U?0:out.data[completed-1U];for(std::size_t i=begin;i<query;++i)out.scalar+=(out.aux[i/30U]>>static_cast<int>(i%30U))&1;}",
        "for(std::size_t i=0;i<out.data.size();++i)out.restored.push_back(out.aux[i/static_cast<std::size_t>(width)]+out.data[i]);",
        "for(std::size_t begin=0,group=0;group<out.aux.size();++group){long long mapped=0;int shift=0;for(std::size_t p=begin;p<static_cast<std::size_t>(out.aux[group]);++p){mapped|=static_cast<long long>(out.data[p]&127)<<shift;shift+=7;}out.restored.push_back(mapped&1LL?static_cast<int>(-(mapped+1)/2):static_cast<int>(mapped/2));begin=static_cast<std::size_t>(out.aux[group]);}out.scalar=static_cast<int>(out.data.size());",
        "for(std::size_t i=0;i<values.size();++i){std::size_t bit=i*static_cast<std::size_t>(width);std::size_t word=bit/30U;int offset=static_cast<int>(bit%30U);long long joined=out.data[word];if(offset+width>30&&word+1<out.data.size())joined|=static_cast<long long>(out.data[word+1])<<30;out.restored.push_back(static_cast<int>((joined>>offset)&((1LL<<width)-1)));}out.scalar=static_cast<int>(out.data.size());",
        "int prior=0;for(std::size_t run=0;run<out.data.size();++run){for(int i=prior;i<out.aux[run];++i)out.restored.push_back(out.data[run]);prior=out.aux[run];}out.scalar=static_cast<int>(out.data.size());",
        "for(int id:out.data)out.restored.push_back(id<0?parameter:out.aux[static_cast<std::size_t>(id)]);out.scalar=static_cast<int>(std::count(out.data.begin(),out.data.end(),-1));",
        "if(!out.data.empty()){int current=out.data.front();out.restored.push_back(current);for(std::size_t i=1;i<out.data.size();++i){current+=out.data[i];out.restored.push_back(current);}}out.scalar=static_cast<int>(out.aux.size());",
        "for(std::size_t row=1;row<out.aux.size();++row)for(int i=out.aux[row-1];i<out.aux[row];++i)out.restored.push_back(out.data[static_cast<std::size_t>(i)]);",
        "for(int id:out.data){std::size_t begin=static_cast<std::size_t>(id*width);out.restored.insert(out.restored.end(),out.aux.begin()+static_cast<std::ptrdiff_t>(begin),out.aux.begin()+static_cast<std::ptrdiff_t>(begin+static_cast<std::size_t>(width)));}",
        "for(std::size_t i=0;i<out.data.size();++i){out.restored.push_back(out.data[i]);out.restored.push_back(out.aux[i]);}",
        "int decode_shift=out.aux[1];for(std::size_t b=0;b<out.data.size();b+=static_cast<std::size_t>(width)){std::vector<int> row(static_cast<std::size_t>(width));for(int c=0;c<width;++c)row[static_cast<std::size_t>((c+decode_shift)%width)]=out.data[b+static_cast<std::size_t>(c)];out.restored.insert(out.restored.end(),row.begin(),row.end());}",
        "std::vector<int> newer=out.aux;for(std::size_t i=0;i<out.data.size();i+=2U)newer[static_cast<std::size_t>(out.data[i])]=out.data[i+1];out.restored=out.aux;out.restored.insert(out.restored.end(),newer.begin(),newer.end());",
        "std::vector<int> left,right;for(std::size_t i=0;i<out.data.size();++i){if(out.aux[i]&1)left.push_back(out.data[i]);if(out.aux[i]&2)right.push_back(out.data[i]);}out.restored=left;out.restored.insert(out.restored.end(),right.begin(),right.end());out.scalar=static_cast<int>(out.data.size());",
        "out.restored.assign(out.aux.begin(),out.aux.begin()+parameter);out.restored.insert(out.restored.end(),out.data.begin(),out.data.end());",
        "out.restored=out.data;",
        "for(int vertex=0;vertex<parameter;++vertex){int prior=0;for(int p=out.aux[static_cast<std::size_t>(vertex)];p<out.aux[static_cast<std::size_t>(vertex+1)];++p){int neighbor=(p==out.aux[static_cast<std::size_t>(vertex)])?out.data[static_cast<std::size_t>(p)]:prior+out.data[static_cast<std::size_t>(p)];if(vertex<neighbor){out.restored.push_back(vertex);out.restored.push_back(neighbor);}prior=neighbor;}}out.scalar=static_cast<int>(out.data.size());",
        "int posting=0;for(std::size_t i=0;i<out.data.size();++i){posting=i==0?out.data[i]:posting+out.data[i];out.restored.push_back(posting);}std::size_t start=0;int current=out.data.empty()?0:out.data.front();for(std::size_t checkpoint=0;checkpoint+1<out.aux.size();checkpoint+=2U)if(out.aux[checkpoint+1U]<=parameter){start=static_cast<std::size_t>(out.aux[checkpoint]);current=out.aux[checkpoint+1U];}out.scalar=0;if(!out.data.empty()){if(current==parameter)out.scalar=1;for(std::size_t i=start+1U;i<out.data.size()&&current<parameter;++i){current+=out.data[i];if(current==parameter)out.scalar=1;}}",
        "for(std::size_t q=0;q+1<out.aux.size();++q)for(int p=out.aux[q];p<out.aux[q+1];++p)out.restored.push_back(static_cast<int>(q)*width+out.data[static_cast<std::size_t>(p)]);out.scalar=static_cast<int>(out.aux.size()-1U);out.contains_member=false;if(request.query_member>=0&&request.query_member<parameter){const std::size_t q=static_cast<std::size_t>(request.query_member/width);const int remainder=request.query_member%width;const auto first=out.data.begin()+out.aux[q];const auto last=out.data.begin()+out.aux[q+1U];out.contains_member=std::binary_search(first,last,remainder);}",
        "out.restored.assign(static_cast<std::size_t>(out.scalar),0);for(std::size_t i=0;i<out.aux.size();++i){std::size_t position=static_cast<std::size_t>(out.data[2*i]*width+out.data[2*i+1]);out.restored[position]=out.aux[i];}",
        "out.restored.assign(static_cast<std::size_t>(width*width),0);std::size_t cursor=0;for(int r=0;r<width;++r)for(int c=r;c<width;++c){int value=out.data[cursor++];out.restored[static_cast<std::size_t>(r*width+c)]=value;out.restored[static_cast<std::size_t>(c*width+r)]=value;}out.scalar=static_cast<int>(out.data.size());",
        "out.restored.assign(static_cast<std::size_t>(width*width),0);std::size_t cursor=0;std::function<bool(int,int,int)> read=[&](int r,int c,int n){if(cursor>=out.data.size())return false;int tag=out.data[cursor++];if(tag==0){if(cursor>=out.data.size())return false;int value=out.data[cursor++];for(int y=r;y<r+n;++y)for(int x=c;x<c+n;++x)out.restored[static_cast<std::size_t>(y*width+x)]=value;return true;}if(tag!=1||n==1)return false;int h=n/2;return read(r,c,h)&&read(r,c+h,h)&&read(r+h,c,h)&&read(r+h,c+h,h);};if(!read(0,0,width)||cursor!=out.data.size())return out;",
        "out.restored.assign(static_cast<std::size_t>(out.aux[0]),0);for(std::size_t i=0;i<out.data.size();i+=2U)for(int p=out.data[i];p<out.data[i+1];++p)out.restored[static_cast<std::size_t>(p)]=1;out.scalar=parameter>=0&&static_cast<std::size_t>(parameter)<out.restored.size()?out.restored[static_cast<std::size_t>(parameter)]:0;",
        "out.restored=out.data;",
        "out.restored.assign(static_cast<std::size_t>(out.aux[0]),0);int decode_prior=-1;for(std::size_t i=0;i<out.data.size();i+=2U){int position=decode_prior+1+out.data[i];out.restored[static_cast<std::size_t>(position)]=out.data[i+1];decode_prior=position;}out.scalar=static_cast<int>(out.data.size()/2U);",
        "int rows=out.aux[0],plane_words=out.aux[1];out.restored.assign(static_cast<std::size_t>(rows),0);for(int bit=0;bit<8;++bit)for(int row=0;row<rows;++row){int word=out.data[static_cast<std::size_t>(bit*plane_words+row/30)];out.restored[static_cast<std::size_t>(row)]|=((word>>(row%30))&1)<<bit;}out.scalar=8;",
    )
    return bodies[index]


def _special_source(case: Case, index: int, *, negative: bool) -> str | None:
    """Return genuinely task-shaped implementations for non-integer surfaces.

    Negative variants are standalone algorithms.  They never call, paste, or
    post-process the authoritative implementation.
    """
    request = case.result_type.removesuffix("Result") + "Request"
    common = f'''#include "{case.task_id}.h"
#include <algorithm>
#include <cstddef>
#include <limits>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>
namespace representation_curriculum {{
{case.result_type} {case.snake}(const {request}& request){{
  {case.result_type} out;
'''
    bodies: dict[int, tuple[str, str]] = {
        5: (
            r"""  if(request.null_sentinel>=0)return {};
  std::vector<int> dictionary;
  for(int value:request.nullable_values)if(value!=request.null_sentinel)dictionary.push_back(value);
  std::sort(dictionary.begin(),dictionary.end());
  dictionary.erase(std::unique(dictionary.begin(),dictionary.end()),dictionary.end());
  out.sorted_dictionary=dictionary;
  const std::size_t words=(request.nullable_values.size()+29U)/30U;
  out.validity_words.assign(words,0);
  for(std::size_t i=0;i<request.nullable_values.size();++i){
    const int value=request.nullable_values[i];
    if(value==request.null_sentinel){out.dictionary_ids.push_back(-1);++out.null_count;continue;}
    out.validity_words[i/30U]|=1<<(i%30U);
    out.dictionary_ids.push_back(static_cast<int>(std::lower_bound(dictionary.begin(),dictionary.end(),value)-dictionary.begin()));
  }
  for(std::size_t i=0;i<out.dictionary_ids.size();++i){
    const bool present=((out.validity_words[i/30U]>>(i%30U))&1)!=0;
    const int id=out.dictionary_ids[i];
    if(!present){if(id!=-1)return {};out.decoded_values.push_back(request.null_sentinel);continue;}
    if(id<0||static_cast<std::size_t>(id)>=out.sorted_dictionary.size())return {};
    out.decoded_values.push_back(out.sorted_dictionary[static_cast<std::size_t>(id)]);
  }
""",
            r"""  std::vector<int> first_seen;
  for(int value:request.nullable_values){
    if(value==request.null_sentinel){out.dictionary_ids.push_back(-1);++out.null_count;continue;}
    auto found=std::find(first_seen.begin(),first_seen.end(),value);
    if(found==first_seen.end()){first_seen.push_back(value);found=first_seen.end()-1;}
    out.dictionary_ids.push_back(static_cast<int>(found-first_seen.begin()));
    out.decoded_values.push_back(value);
  }
  out.sorted_dictionary=first_seen;
""",
        ),
        6: (
            r"""  if(request.anchor_stride<=0)return {};
  for(std::size_t i=0;i<request.ordered_paths.size();++i){
    if(i>0&&request.ordered_paths[i]<=request.ordered_paths[i-1])return {};
    const std::string& prior=i==0?std::string():request.ordered_paths[i-1];
    std::size_t prefix=0;
    while(prefix<prior.size()&&prefix<request.ordered_paths[i].size()&&prior[prefix]==request.ordered_paths[i][prefix])++prefix;
    out.common_prefix_lengths.push_back(static_cast<int>(prefix));
    out.suffixes.push_back(request.ordered_paths[i].substr(prefix));
    if(i%static_cast<std::size_t>(request.anchor_stride)==0)out.anchors.push_back(request.ordered_paths[i]);
  }
  std::string prior;
  for(std::size_t i=0;i<out.suffixes.size();++i){
    const int prefix=out.common_prefix_lengths[i];
    if(prefix<0||static_cast<std::size_t>(prefix)>prior.size())return {};
    std::string decoded=prior.substr(0,static_cast<std::size_t>(prefix))+out.suffixes[i];
    if(i>0&&decoded<=prior)return {};
    out.decoded_paths.push_back(decoded);prior=std::move(decoded);
  }
  out.anchor_count=static_cast<int>(out.anchors.size());
""",
            r"""  if(request.anchor_stride<=0)return {};
  for(const std::string& path:request.ordered_paths){
    out.common_prefix_lengths.push_back(0);
    out.suffixes.push_back(path+"/");
    out.decoded_paths.push_back(path+"/");
  }
""",
        ),
        7: (
            r"""  if(request.maximum_row_length==0)return {};
  out.row_offsets.push_back(0);
  for(const auto& row:request.rows){
    if(row.size()>request.maximum_row_length)return {};
    out.payload.insert(out.payload.end(),row.begin(),row.end());
    out.row_offsets.push_back(static_cast<int>(out.payload.size()));
  }
  if(out.row_offsets.empty()||out.row_offsets.front()!=0||out.row_offsets.back()!=static_cast<int>(out.payload.size()))return {};
  for(std::size_t row=1;row<out.row_offsets.size();++row){
    const int begin=out.row_offsets[row-1],end=out.row_offsets[row];
    if(begin<0||end<begin||static_cast<std::size_t>(end)>out.payload.size())return {};
    out.decoded_rows.emplace_back(out.payload.begin()+begin,out.payload.begin()+end);
  }
  out.row_count=static_cast<int>(out.decoded_rows.size());
""",
            r"""  if(request.maximum_row_length==0)return {};
  const std::size_t assumed=request.rows.empty()?0:request.rows.front().size();
  for(const auto& row:request.rows)if(row.size()!=assumed)return {};
  for(const auto& row:request.rows)out.payload.insert(out.payload.end(),row.begin(),row.end());
  for(std::size_t offset=0;offset<=out.payload.size();offset+=assumed==0?1:assumed)out.row_offsets.push_back(static_cast<int>(offset));
  out.decoded_rows=request.rows;out.row_count=static_cast<int>(request.rows.size());
""",
        ),
        9: (
            r"""  if(request.ids.size()!=request.values.size()||request.ids.size()!=request.value_validity.size())return {};
  std::set<int> ids;
  out.validity_words.assign((request.ids.size()+29U)/30U,0);
  for(std::size_t i=0;i<request.ids.size();++i){
    if(request.ids[i]<0||!ids.insert(request.ids[i]).second||request.value_validity[i]<0||request.value_validity[i]>1)return {};
    out.id_column.push_back(request.ids[i]);
    const bool present=request.value_validity[i]!=0;
    if(present)out.validity_words[i/30U]|=1<<(i%30U);
    out.value_column.push_back(present?request.values[i]:0);
  }
  for(std::size_t i=0;i<out.id_column.size();++i){
    const bool present=((out.validity_words[i/30U]>>(i%30U))&1)!=0;
    out.decoded_records.push_back(out.id_column[i]);
    out.decoded_records.push_back(present?out.value_column[i]:0);
  }
  out.row_count=static_cast<int>(out.id_column.size());
""",
            r"""  if(request.ids.size()!=request.values.size()||request.ids.size()!=request.value_validity.size())return {};
  for(std::size_t i=0;i<request.ids.size();++i)if(request.value_validity[i]){
    out.id_column.push_back(request.ids[i]);out.value_column.push_back(request.values[i]);
    out.decoded_records.push_back(request.ids[i]);out.decoded_records.push_back(request.values[i]);
  }
  out.row_count=static_cast<int>(out.id_column.size());
""",
        ),
        10: (
            r"""  if(request.source_schema.empty()||request.source_schema.size()!=request.requested_schema.size())return {};
  std::set<std::string> source_names,requested_names;
  for(const auto& name:request.source_schema)if(name.empty()||!source_names.insert(name).second)return {};
  for(const auto& name:request.requested_schema)if(name.empty()||!requested_names.insert(name).second)return {};
  if(source_names!=requested_names||request.flat_table.size()%request.source_schema.size()!=0)return {};
  for(const auto& name:request.requested_schema){
    auto found=std::find(request.source_schema.begin(),request.source_schema.end(),name);
    out.schema_map.push_back(static_cast<int>(found-request.source_schema.begin()));
  }
  const std::size_t width=request.source_schema.size();
  for(std::size_t row=0;row<request.flat_table.size();row+=width)
    for(int source:out.schema_map)out.permuted_cells.push_back(request.flat_table[row+static_cast<std::size_t>(source)]);
  out.decoded_table.assign(request.flat_table.size(),0);
  for(std::size_t row=0;row<out.permuted_cells.size();row+=width)
    for(std::size_t column=0;column<width;++column)out.decoded_table[row+static_cast<std::size_t>(out.schema_map[column])]=out.permuted_cells[row+column];
  out.row_count=static_cast<int>(request.flat_table.size()/width);
""",
            r"""  std::vector<std::string> sorted=request.source_schema;
  std::sort(sorted.begin(),sorted.end());
  if(sorted.empty()||request.flat_table.size()%sorted.size()!=0)return {};
  for(const auto& name:sorted)out.schema_map.push_back(static_cast<int>(std::find(request.source_schema.begin(),request.source_schema.end(),name)-request.source_schema.begin()));
  const std::size_t width=sorted.size();
  for(std::size_t row=0;row<request.flat_table.size();row+=width)for(int source:out.schema_map)out.permuted_cells.push_back(request.flat_table[row+static_cast<std::size_t>(source)]);
""",
        ),
        18: (
            r"""  if(request.shape.size()!=3U||request.block_shape.size()!=3U)return {};
  long long cells=1,block_volume=1;
  auto checked_product=[](long long& product,int extent){
    if(extent<=0||product>std::numeric_limits<long long>::max()/static_cast<long long>(extent))return false;
    product*=static_cast<long long>(extent);return true;
  };
  for(int extent:request.shape)if(!checked_product(cells,extent))return {};
  for(int extent:request.block_shape)if(!checked_product(block_volume,extent))return {};
  for(std::size_t axis=0;axis<3U;++axis)if(request.block_shape[axis]>request.shape[axis])return {};
  if(block_volume>std::numeric_limits<int>::max())return {};
  if(cells!=static_cast<long long>(request.dense_cells.size()))return {};
  const int z_count=request.shape[0],y_count=request.shape[1],x_count=request.shape[2];
  const int bz_size=request.block_shape[0],by_size=request.block_shape[1],bx_size=request.block_shape[2];
  out.block_offsets.push_back(0);
  for(int bz=0;bz<z_count;bz+=bz_size)for(int by=0;by<y_count;by+=by_size)for(int bx=0;bx<x_count;bx+=bx_size){
    bool nonzero=false;std::vector<int> payload;
    for(int dz=0;dz<bz_size;++dz)for(int dy=0;dy<by_size;++dy)for(int dx=0;dx<bx_size;++dx){
      const long long z=static_cast<long long>(bz)+dz,y=static_cast<long long>(by)+dy,x=static_cast<long long>(bx)+dx;
      const std::size_t position=(static_cast<std::size_t>(z)*static_cast<std::size_t>(y_count)+static_cast<std::size_t>(y))*static_cast<std::size_t>(x_count)+static_cast<std::size_t>(x);
      const int value=(z<z_count&&y<y_count&&x<x_count)?request.dense_cells[position]:0;
      payload.push_back(value);nonzero=nonzero||value!=0;
    }
    if(nonzero){out.block_coordinates.insert(out.block_coordinates.end(),{bz/bz_size,by/by_size,bx/bx_size});out.dense_block_payloads.insert(out.dense_block_payloads.end(),payload.begin(),payload.end());out.block_offsets.push_back(static_cast<int>(out.dense_block_payloads.size()));}
  }
  out.decoded_cells.assign(request.dense_cells.size(),0);
  for(std::size_t block=0;block+1<out.block_offsets.size();++block){
    const int bz=out.block_coordinates[3U*block]*bz_size,by=out.block_coordinates[3U*block+1U]*by_size,bx=out.block_coordinates[3U*block+2U]*bx_size;
    std::size_t cursor=static_cast<std::size_t>(out.block_offsets[block]);
    for(int dz=0;dz<bz_size;++dz)for(int dy=0;dy<by_size;++dy)for(int dx=0;dx<bx_size;++dx){
      const long long z=static_cast<long long>(bz)+dz,y=static_cast<long long>(by)+dy,x=static_cast<long long>(bx)+dx;const int value=out.dense_block_payloads[cursor++];
      if(z<z_count&&y<y_count&&x<x_count){const std::size_t position=(static_cast<std::size_t>(z)*static_cast<std::size_t>(y_count)+static_cast<std::size_t>(y))*static_cast<std::size_t>(x_count)+static_cast<std::size_t>(x);out.decoded_cells[position]=value;}
    }
  }
  out.nonzero_block_count=static_cast<int>(out.block_offsets.size()-1U);
""",
            r"""  if(request.shape.size()!=3U||request.block_shape.size()!=3U)return {};
  out.block_coordinates={0,0,0};out.dense_block_payloads=request.dense_cells;out.block_offsets={0,static_cast<int>(request.dense_cells.size())};out.decoded_cells=request.dense_cells;out.nonzero_block_count=request.dense_cells.empty()?0:1;
""",
        ),
        22: (
            r"""  if(request.coordinate_limit<=0||request.update_triples.size()%3U!=0)return {};
  std::map<int,std::pair<int,int>> latest;std::map<int,std::set<int>> seen;
  for(std::size_t i=0;i<request.update_triples.size();i+=3U){
    const int coordinate=request.update_triples[i],sequence=request.update_triples[i+1],value=request.update_triples[i+2];
    if(coordinate<0||coordinate>=request.coordinate_limit||!seen[coordinate].insert(sequence).second)return {};
    auto found=latest.find(coordinate);if(found==latest.end()||sequence>found->second.first)latest[coordinate]={sequence,value};
  }
  out.decoded_overlay.assign(static_cast<std::size_t>(request.coordinate_limit),request.default_value);
  for(const auto& [coordinate,winner]:latest){
    out.sequence_metadata.insert(out.sequence_metadata.end(),{coordinate,winner.first});
    if(winner.second!=request.default_value){out.overlay_pairs.insert(out.overlay_pairs.end(),{coordinate,winner.second});out.decoded_overlay[static_cast<std::size_t>(coordinate)]=winner.second;}
  }
  out.coordinate_count=static_cast<int>(out.overlay_pairs.size()/2U);
""",
            r"""  if(request.coordinate_limit<=0||request.update_triples.size()%3U!=0)return {};
  std::set<int> seen;
  out.decoded_overlay.assign(static_cast<std::size_t>(request.coordinate_limit),request.default_value);
  for(std::size_t i=0;i<request.update_triples.size();i+=3U){const int coordinate=request.update_triples[i];if(coordinate<0||coordinate>=request.coordinate_limit)return {};if(seen.insert(coordinate).second){out.overlay_pairs.insert(out.overlay_pairs.end(),{coordinate,request.update_triples[i+2]});out.decoded_overlay[static_cast<std::size_t>(coordinate)]=request.update_triples[i+2];}}
  out.coordinate_count=static_cast<int>(out.overlay_pairs.size()/2U);
""",
        ),
    }
    selected = bodies.get(index)
    if selected is None:
        return None
    return common + selected[1 if negative else 0] + "  out.valid=true;return out;\n}\n}\n"


def _negative_source(case: Case, index: int) -> str:
    special = _special_source(case, index, negative=True)
    if special is not None:
        return special
    values_name, width_name, parameter_name, data_name, aux_name, restored_name, scalar_name = _api(
        index
    )
    request = case.result_type.removesuffix("Result") + "Request"
    wrong = (
        "for(int bit:values){if(bit<0||bit>1)return {};out.scalar+=bit;}out.restored=values;",
        "if(values.empty())return {};int base=*std::min_element(values.begin(),values.end());out.aux={base};for(int value:values)out.data.push_back(value-base);out.restored=values;",
        "for(int value:values)out.data.push_back(value&255);out.aux.push_back(static_cast<int>(out.data.size()));out.restored=values;",
        "out.data=values;out.aux={static_cast<int>(values.size()),width};out.restored=values;",
        "for(std::size_t i=0;i<values.size();){std::size_t j=i+1;while(j<values.size()&&values[j]==values[i])++j;out.data.push_back(values[i]);out.aux.push_back(static_cast<int>(j-i));i=j;}out.restored=values;",
        "",
        "",
        "",
        "std::vector<int> cells=values;std::sort(cells.begin(),cells.end());cells.erase(std::unique(cells.begin(),cells.end()),cells.end());out.aux=cells;for(int value:values)out.data.push_back(static_cast<int>(std::lower_bound(cells.begin(),cells.end(),value)-cells.begin()));out.restored=values;",
        "",
        "",
        "if(width<=0||parameter<0||values.size()%2U!=0||static_cast<std::size_t>(parameter)!=values.size()/2U||parameter%width!=0)return {};for(int row=0;row<parameter;row+=width){bool changed=false;for(int column=0;column<width;++column)changed=changed||values[static_cast<std::size_t>(row+column)]!=values[static_cast<std::size_t>(parameter+row+column)];if(changed)for(int column=0;column<width;++column){out.data.push_back(row+column);out.data.push_back(values[static_cast<std::size_t>(parameter+row+column)]);}}out.restored=values;",
        "std::size_t split=static_cast<std::size_t>(parameter);for(std::size_t i=0;i<split;++i)for(std::size_t j=split;j<values.size();++j)if(values[i]==values[j]){out.data.push_back(values[i]);out.aux.push_back(3);}out.restored=values;",
        "for(std::size_t e=static_cast<std::size_t>(parameter);e<values.size();++e){auto found=std::min_element(values.begin(),values.begin()+parameter,[&](int a,int b){return std::abs(a-values[e])<std::abs(b-values[e]);});out.data.push_back(values[e]);out.aux.push_back(*found);}out.restored=values;",
        "out.data=values;out.restored=values;out.scalar=0;",
        "int prior=0;for(int endpoint:values){out.data.push_back(endpoint-prior);prior=endpoint;}out.aux={0,static_cast<int>(out.data.size())};out.restored=values;",
        "int posting=0;for(std::size_t i=0;i<values.size();++i){posting=values[i];out.data.push_back(i==0?posting:posting-values[i-1]);}out.scalar=std::find(values.begin(),values.end(),parameter)!=values.end();out.restored=values;",
        "for(int member:values){out.data.push_back(member/width);out.data.push_back(member%width);}out.restored=values;",
        "",
        "for(int r=0;r<width;++r)out.data.push_back(values[static_cast<std::size_t>(r*width+r)]);out.aux={0,width};out.restored=values;",
        "for(int r=0;r<width;++r){int prior=values[static_cast<std::size_t>(r*width)],count=1;for(int c=1;c<width;++c){int value=values[static_cast<std::size_t>(r*width+c)];if(value==prior)++count;else{out.data.insert(out.data.end(),{prior,count});prior=value;count=1;}}out.data.insert(out.data.end(),{prior,count});}out.restored=values;",
        "for(std::size_t i=0;i<values.size();++i)if(values[i])out.data.push_back(static_cast<int>(i));out.aux={static_cast<int>(values.size())};out.restored=values;",
        "",
        "int prior=-1;for(std::size_t i=0;i<values.size();++i)if(values[i]>0){out.data.insert(out.data.end(),{static_cast<int>(i)-prior-1,values[i]});prior=static_cast<int>(i);}out.restored=values;",
        "int words=static_cast<int>((values.size()+29U)/30U);for(int bit=0;bit<8;++bit){std::vector<int> plane(static_cast<std::size_t>(words));bool any=false;for(std::size_t i=0;i<values.size();++i)if((values[i]>>bit)&1){plane[i/30U]|=1<<(i%30U);any=true;}if(any)out.data.insert(out.data.end(),plane.begin(),plane.end());}out.aux={static_cast<int>(values.size()),words};out.restored=values;",
    )[index]
    for old, new in (
        ("out.data", f"out.{data_name}"),
        ("out.aux", f"out.{aux_name}"),
        ("out.restored", f"out.{restored_name}"),
        ("out.scalar", f"out.{scalar_name}"),
    ):
        wrong = wrong.replace(old, new)
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <vector>
namespace representation_curriculum {{
{case.result_type} {case.snake}(const {request}& request){{
  const auto& values=request.{values_name};const int width=request.{width_name};const int parameter=request.{parameter_name};
  {case.result_type} out;(void)width;(void)parameter;{wrong}
  out.valid=true;return out;
}}
}}
'''


def _source(case: Case, index: int, *, negative: bool = False, opposite: bool = False) -> str:
    if negative:
        return _negative_source(case, index)
    special = _special_source(case, index, negative=False)
    if special is not None:
        marker = "\n}\n"
        namespace_close = special.rfind(marker)
        if namespace_close < 0:
            _fail("validator_injection_failed", case.task_id)
        return (
            special[:namespace_close]
            + "\n"
            + _validator_function(case, index, opposite=opposite)
            + "}\n"
        )
    negative_tail = ""
    opposite_tail = "std::reverse(out.data.begin(),out.data.end());" if opposite else ""
    validation = (
        ""
        if index in {2, 5, 8, 9, 11, 12, 13, 14, 19}
        else "for(int value:values)if(value<0)return out;"
    )
    values_name, width_name, parameter_name, data_name, aux_name, restored_name, scalar_name = _api(
        index
    )
    request = case.result_type.removesuffix("Result") + "Request"
    substitutions = (
        ("out.data", f"out.{data_name}"),
        ("out.aux", f"out.{aux_name}"),
        ("out.restored", f"out.{restored_name}"),
        ("out.scalar", f"out.{scalar_name}"),
    )
    body = _algorithm_body(index) + _decode_body(index)
    for old, new in substitutions:
        body = body.replace(old, new)
    body = body.replace("return out;", f"return {case.result_type}{{}};")
    body = body.replace(";", ";\n").replace("}out", "}\nout")
    for old, new in substitutions:
        negative_tail = negative_tail.replace(old, new)
        opposite_tail = opposite_tail.replace(old, new)
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <cstddef>
#include <functional>
#include <limits>
#include <numeric>
#include <map>
#include <set>
#include <cstdlib>
#include <string>
#include <utility>
#include <vector>
namespace representation_curriculum {{
{case.result_type} {case.snake}(const {request}& request){{
  const auto& values=request.{values_name};const int width=request.{width_name};const int parameter=request.{parameter_name};
  {case.result_type} out;(void)width;(void)parameter;if(width<=0)return out;{validation}
  {body}
  out.valid=true;{opposite_tail}{negative_tail}return out;
}}
{_validator_function(case, index, opposite=opposite)}
}}
'''


def _starter(case: Case, index: int) -> str:
    request = case.result_type.removesuffix("Result") + "Request"
    return f'''#include "{case.task_id}.h"
namespace representation_curriculum {{
{case.result_type} {case.snake}(const {request}&){{return {{}};}}
bool {_validator_name(case)}(const {request}&, const {case.result_type}&){{return false;}}
}}
'''


def _oracle(case: Case, index: int) -> tuple[list[int], list[int]]:
    values, width, parameter = list(case.sample), case.width, case.parameter
    data: list[int] = []
    aux: list[int] = []
    if index == 0:
        rank = 0
        for i, value in enumerate(values):
            rank += value
            if (i + 1) % width == 0 or i + 1 == len(values):
                data.append(rank)
        for b in range(0, len(values), 30):
            aux.append(sum(values[b + j] << j for j in range(min(30, len(values) - b))))
    elif index == 1:
        for b in range(0, len(values), width):
            block = values[b : b + width]
            base = min(block)
            aux.append(base)
            data.extend(v - base for v in block)
    elif index == 2:
        for value in values:
            mapped = 2 * value if value >= 0 else -2 * value - 1
            while True:
                byte = mapped & 127
                mapped >>= 7
                data.append(byte | (128 if mapped else 0))
                if not mapped:
                    break
            aux.append(len(data))
    elif index == 3:
        buffer = bits = 0
        for value in values:
            buffer |= value << bits
            bits += width
            while bits >= 30:
                data.append(buffer & 0x3FFFFFFF)
                buffer >>= 30
                bits -= 30
        if bits:
            data.append(buffer)
        aux = [len(values), width]
    elif index == 4:
        i = 0
        while i < len(values):
            j = i + 1
            while j < len(values) and values[j] == values[i]:
                j += 1
            data.append(values[i])
            aux.append(j)
            i = j
    elif index == 5:
        aux = sorted(set(v for v in values if v != parameter))
        data = [-1 if v == parameter else aux.index(v) for v in values]
    elif index == 6:
        data = [values[0]] + [values[i] - values[i - 1] for i in range(1, len(values))]
        aux = [values[i] for i in range(width, len(values), width)]
    elif index == 16:
        data = [values[0]] + [values[i] - values[i - 1] for i in range(1, len(values))]
        aux = [item for i in range(0, len(values), width) for item in (i, values[i])]
    elif index == 7:
        aux = [0]
        cursor = row = 0
        while cursor < len(values):
            take = min(1 + row % max(1, parameter), len(values) - cursor)
            data.extend(values[cursor : cursor + take])
            cursor += take
            aux.append(cursor)
            row += 1
    elif index == 8:
        rows = [tuple(values[i : i + width]) for i in range(0, len(values), width)]
        dictionary = sorted(set(rows))
        for row in rows:
            data.append(dictionary.index(row))
        aux = [v for row in dictionary for v in row]
    elif index == 9:
        data = values[::2]
        aux = values[1::2]
    elif index == 10:
        for b in range(0, len(values), width):
            data.extend(values[b + (c + parameter % width) % width] for c in range(width))
        aux = [width, parameter % width]
    elif index == 11:
        aux = list(values[:parameter])
        for i in range(parameter):
            if values[i] != values[parameter + i]:
                data.extend([i, values[parameter + i]])
    elif index == 12:
        left, right = values[:parameter], values[parameter:]
        i = j = 0
        while i < len(left) or j < len(right):
            if j == len(right) or (i < len(left) and left[i] < right[j]):
                data.append(left[i])
                aux.append(1)
                i += 1
            elif i == len(left) or right[j] < left[i]:
                data.append(right[j])
                aux.append(2)
                j += 1
            else:
                data.append(left[i])
                aux.append(3)
                i += 1
                j += 1
    elif index == 13:
        snapshots, events = values[:parameter], values[parameter:]
        data = list(events)
        aux = list(snapshots)
        s = 0
        for event in events:
            while s < len(snapshots) and snapshots[s] <= event:
                s += 1
            aux.append(-1 if s == 0 else snapshots[s - 1])
    elif index == 14:
        terms: dict[int, int] = {}
        for i in range(0, len(values), 2):
            terms[values[i]] = terms.get(values[i], 0) + values[i + 1]
        for exponent in sorted(terms):
            if terms[exponent]:
                data.extend([exponent, terms[exponent]])
        aux = [sum(data[i + 1] * (parameter ** data[i]) for i in range(0, len(data), 2))]
    elif index == 15:
        rows = [set() for _ in range(parameter)]
        for i in range(0, len(values), 2):
            a, b = values[i : i + 2]
            rows[a].add(b)
            rows[b].add(a)
        aux = [0]
        for row in rows:
            prior = 0
            for pos, v in enumerate(sorted(row)):
                data.append(v if pos == 0 else v - prior)
                prior = v
            aux.append(len(data))
    elif index == 17:
        aux = [0]
        for q in range((parameter + width - 1) // width):
            data.extend(v % width for v in values if v // width == q)
            aux.append(len(data))
    elif index == 18:
        for i, v in enumerate(values):
            if v:
                data.extend([i // width, i % width])
                aux.append(v)
    elif index == 19:
        aux = [0]
        for r in range(width):
            for c in range(r, width):
                data.append(values[r * width + c])
            aux.append(len(data))
    elif index == 20:

        def visit(r: int, c: int, n: int) -> None:
            cells = [values[y * width + x] for y in range(r, r + n) for x in range(c, c + n)]
            if len(set(cells)) == 1:
                data.extend([0, cells[0]])
                return
            data.append(1)
            h = n // 2
            for rr, cc in ((r, c), (r, c + h), (r + h, c), (r + h, c + h)):
                visit(rr, cc, h)

        visit(0, 0, width)
        aux = [width]
    elif index == 21:
        i = 0
        while i < len(values):
            if not values[i]:
                i += 1
                continue
            j = i + 1
            while j < len(values) and values[j]:
                j += 1
            data.extend([i, j])
            i = j
        aux = [len(values)]
    elif index == 22:
        latest: dict[int, tuple[int, int]] = {}
        for i in range(0, len(values), 3):
            coord, seq, value = values[i : i + 3]
            if coord not in latest or seq > latest[coord][0]:
                latest[coord] = (seq, value)
        for coord, pair in sorted(latest.items()):
            if pair[1] != parameter:
                data.extend([coord, pair[1]])
    elif index == 23:
        prior = -1
        for i, v in enumerate(values):
            if v:
                data.extend([i - prior - 1, v])
                prior = i
        aux = [len(values)]
    elif index == 24:
        words = (len(values) + 29) // 30
        for bit in range(8):
            for w in range(words):
                word = 0
                for j in range(30):
                    i = w * 30 + j
                    if i < len(values):
                        word |= ((values[i] >> bit) & 1) << j
                data.append(word)
        aux = [len(values), words]
    return data, aux


def _malformed_result_mutation(index: int) -> str:
    """Corrupt a real emitted field while leaving the source request valid."""
    mutations = (
        "malformed_result.rank_checkpoints[0]+=1;",
        "malformed_result.offsets[0]+=1;",
        "malformed_result.varint_bytes.back()|=128;",
        "malformed_result.packed_words.back()|=(1<<15);",
        "malformed_result.exclusive_run_ends.back()-=1;",
        "malformed_result.sorted_dictionary.push_back(malformed_result.sorted_dictionary.back());",
        "malformed_result.common_prefix_lengths[1]=99;",
        "malformed_result.row_offsets.back()-=1;",
        "malformed_result.row_ids[0]=malformed_result.unique_row_count;",
        "malformed_result.value_column[1]=1;",
        "malformed_result.schema_map[1]=malformed_result.schema_map[0];",
        "malformed_result.patch_pairs.insert(malformed_result.patch_pairs.end(),{malformed_result.patch_pairs[0],malformed_result.patch_pairs[1]});",
        "malformed_result.presence_masks[0]=0;",
        "malformed_result.snapshots_and_matches[static_cast<std::size_t>(request.snapshot_count)]=request.snapshots_and_events[0];",
        "malformed_result.canonical_terms.insert(malformed_result.canonical_terms.end(),{malformed_result.canonical_terms[0],1});",
        "malformed_result.neighbor_gaps[1]=0;",
        "malformed_result.skip_checkpoints[1]+=1;",
        "malformed_result.bucket_offsets.back()-=1;",
        "malformed_result.dense_block_payloads.back()=1;",
        "malformed_result.row_offsets[1]-=1;",
        "malformed_result.preorder_stream.push_back(0);",
        "malformed_result.half_open_intervals[2]=malformed_result.half_open_intervals[1];",
        "malformed_result.overlay_pairs.insert(malformed_result.overlay_pairs.end(),{malformed_result.overlay_pairs[0],malformed_result.overlay_pairs[1]});",
        "malformed_result.length_metadata.clear();",
        "malformed_result.bit_planes[0]|=(1<<4);",
    )
    return mutations[index]


def _accepted_semantic_assertion(case: Case, index: int, category: str) -> str:
    """Assert an observable category result in addition to validator success."""
    primary, _, _, data, aux, restored, scalar = _api(index)
    request_primary = f"{category}_request.{primary}"
    result = f"{category}_result"
    if index == 9:
        semantic = (
            f"{result}.id_column!={category}_request.ids||"
            f"{result}.row_count!=static_cast<int>({category}_request.ids.size())||"
            f"{result}.decoded_records.size()!=2U*{category}_request.ids.size()"
        )
    elif index == 14:
        semantic = (
            f"{result}.decoded_terms!={result}.canonical_terms||"
            f"{result}.evaluation_trace!=std::vector<int>{{{result}.evaluation}}||"
            f"{result}.canonical_terms.size()%2U!=0U"
        )
    elif index == 15:
        semantic = (
            f"{result}.decoded_edges.size()%2U!=0U||"
            f"{result}.vertex_offsets.size()!=static_cast<std::size_t>({category}_request.vertex_count)+1U"
        )
    elif index == 22:
        semantic = (
            f"{result}.decoded_overlay.size()!=static_cast<std::size_t>({category}_request.coordinate_limit)||"
            f"{result}.overlay_pairs.size()!=2U*static_cast<std::size_t>({result}.coordinate_count)"
        )
    else:
        semantic = f"{result}.{restored}!={request_primary}"
    discriminator = {
        (0, "absent_tie"): f"{result}.rank_answer!=-1",
        (16, "absent_tie"): f"{result}.contains_query!=0",
        (17, "absent_tie"): f"{result}.contains_member",
        (21, "absent_tie"): f"{result}.query_value!=0",
        (11, "absent_tie"): f"!{result}.patch_pairs.empty()||{result}.change_count!=0",
        (
            12,
            "absent_tie",
        ): f"{result}.merged_keys!=std::vector<int>{{1,2,4}}||{result}.presence_masks!=std::vector<int>{{1,2,3}}",
        (
            13,
            "absent_tie",
        ): f"{result}.event_keys!=std::vector<int>{{4,5,10}}||{result}.snapshots_and_matches!=std::vector<int>{{5,9,-1,5,9}}",
        (
            14,
            "absent_tie",
        ): f"!{result}.canonical_terms.empty()||{result}.evaluation!=0",
        (
            23,
            "absent_tie",
        ): f"{result}.decoded_bins!=std::vector<int>{{0,4,0,0}}||{result}.length_metadata!=std::vector<int>{{4}}",
        (7, "empty"): f"{result}.row_offsets!=std::vector<int>{{0}}",
        (
            15,
            "empty",
        ): f"{result}.vertex_offsets.size()!=static_cast<std::size_t>({category}_request.vertex_count)+1U",
        (
            17,
            "empty",
        ): f"{result}.bucket_offsets.size()!=static_cast<std::size_t>({result}.bucket_count)+1U",
        (18, "empty"): f"{result}.nonzero_block_count!=0||!{result}.block_coordinates.empty()",
        (24, "empty"): f"{result}.plane_count!=8||!{result}.bit_planes.empty()",
    }.get((index, category))
    encoded_observable = (
        "false"
        if index == 18
        else (f"({result}.{data}.empty()&&{result}.{aux}.empty()&&!{request_primary}.empty())")
    )
    checks = [semantic, encoded_observable]
    if discriminator is not None:
        checks.append(discriminator)
    return "||".join(f"({check})" for check in checks)


def _contract_case_program(case: Case, index: int) -> str:
    """Emit distinct executable inputs for every applicable private rule."""
    primary, width, parameter, data, aux, restored, _ = _api(index)
    special_empty = {
        0: "empty_request.bits.clear();empty_request.query_prefix=0;",
        5: "empty_request.nullable_values.clear();",
        6: "empty_request.ordered_paths.clear();",
        7: "empty_request.rows.clear();",
        9: "empty_request.ids.clear();empty_request.values.clear();empty_request.value_validity.clear();",
        10: "empty_request.flat_table.clear();",
        11: "empty_request.old_and_new_cells.clear();empty_request.old_cell_count=0;",
        12: "empty_request.left_and_right_keys.clear();empty_request.left_count=0;",
        13: "empty_request.snapshots_and_events.clear();empty_request.snapshot_count=0;",
        18: "empty_request.dense_cells={0};empty_request.shape={1,1,1};empty_request.block_shape={1,1,1};",
        22: "empty_request.update_triples.clear();",
    }
    special_duplicate = {
        5: "std::reverse(duplicate_order_request.nullable_values.begin(),duplicate_order_request.nullable_values.end());",
        6: "duplicate_order_request.ordered_paths[1]=duplicate_order_request.ordered_paths[0];",
        7: "std::reverse(duplicate_order_request.rows.begin(),duplicate_order_request.rows.end());",
        9: "duplicate_order_request.ids[1]=duplicate_order_request.ids[0];",
        10: "duplicate_order_request.requested_schema[1]=duplicate_order_request.requested_schema[0];",
        15: "duplicate_order_request.edge_pairs.insert(duplicate_order_request.edge_pairs.end(),{1,0});",
        18: "std::reverse(duplicate_order_request.dense_cells.begin(),duplicate_order_request.dense_cells.end());",
        22: "duplicate_order_request.update_triples.insert(duplicate_order_request.update_triples.end(),{2,1,9});",
    }
    special_absent = {
        5: "absent_tie_request.null_sentinel=-99;",
        9: "absent_tie_request.value_validity[0]=0;",
        11: "absent_tie_request.old_and_new_cells={1,2,1,2};absent_tie_request.column_count=2;absent_tie_request.old_cell_count=2;",
        12: "absent_tie_request.left_and_right_keys={1,4,2,4};absent_tie_request.key_hint=1;absent_tie_request.left_count=2;",
        13: "absent_tie_request.snapshots_and_events={5,9,4,5,10};absent_tie_request.join_hint=1;absent_tie_request.snapshot_count=2;",
        14: "absent_tie_request.term_pairs={0,2,0,-2};absent_tie_request.pair_width=2;absent_tie_request.evaluation_point=2;",
        15: "absent_tie_request.vertex_count=5;",
        16: "absent_tie_request.posting_ids={2,5,9,14};absent_tie_request.checkpoint_stride=2;absent_tie_request.query_id=8;",
        17: "absent_tie_request.query_member=6;",
        18: "absent_tie_request.dense_cells.assign(absent_tie_request.dense_cells.size(),0);",
        22: "absent_tie_request.default_value=7;",
        23: "absent_tie_request.bin_counts={0,4,0,0};absent_tie_request.gap_hint=1;",
    }
    special_overflow = {
        6: 'overflow_tail_request.ordered_paths.push_back("zzzz/terminal");',
        7: "overflow_tail_request.maximum_row_length=overflow_tail_request.rows.back().size();",
        18: "overflow_tail_request.shape[2]=2147483647;",
        22: "overflow_tail_request.update_triples.push_back(3);overflow_tail_request.update_triples.push_back(2);overflow_tail_request.update_triples.push_back(9);",
    }
    special_malformed = {
        5: "malformed_request.null_sentinel=1;",
        6: "malformed_request.anchor_stride=-1;",
        7: "malformed_request.maximum_row_length=1;",
        9: "malformed_request.value_validity.pop_back();",
        10: 'malformed_request.requested_schema={"missing","id","score"};',
        14: "malformed_request.pair_width=3;",
        18: "malformed_request.block_shape.pop_back();",
        22: "malformed_request.update_triples.push_back(4);",
    }
    special_boundary = {
        0: "boundary_request.bits={1,0,1};boundary_request.checkpoint_stride=2;boundary_request.query_prefix=3;",
        1: "boundary_request.integers={8,9,20};boundary_request.block_length=2;",
        2: "boundary_request.signed_entries={-1,0,64};boundary_request.group_hint=1;",
        3: "boundary_request.column_values={7};boundary_request.bit_width=3;",
        4: "boundary_request.statuses={4,4,7};boundary_request.run_hint=1;",
        5: "boundary_request.nullable_values={-1,4,2,4};boundary_request.null_sentinel=-1;",
        6: 'boundary_request.ordered_paths={"ant","ante","anthem"};boundary_request.anchor_stride=2;',
        7: "boundary_request.rows={{1,2},{},{3}};boundary_request.maximum_row_length=2;",
        8: "boundary_request.flat_rows={2,1,2,1,1,9};boundary_request.row_width=2;",
        9: "boundary_request.ids={1,2,3};boundary_request.values={10,99,30};boundary_request.value_validity={1,0,1};",
        10: 'boundary_request.source_schema={"b","a"};boundary_request.requested_schema={"a","b"};boundary_request.flat_table={7,8};',
        11: "boundary_request.old_and_new_cells={1,2,1,5};boundary_request.column_count=2;boundary_request.old_cell_count=2;",
        12: "boundary_request.left_and_right_keys={1,4,2,4};boundary_request.key_hint=1;boundary_request.left_count=2;",
        13: "boundary_request.snapshots_and_events={5,9,4,5,10};boundary_request.join_hint=1;boundary_request.snapshot_count=2;",
        14: "boundary_request.term_pairs={0,2,0,-2,3,4};boundary_request.pair_width=2;boundary_request.evaluation_point=2;",
        15: "boundary_request.edge_pairs={0,2,0,1};boundary_request.endpoint_width=2;boundary_request.vertex_count=3;",
        16: "boundary_request.posting_ids={2,5,9,14};boundary_request.checkpoint_stride=2;boundary_request.query_id=9;",
        17: "boundary_request.members={1,7};boundary_request.divisor=3;boundary_request.universe_limit=9;boundary_request.query_member=7;",
        18: "boundary_request.dense_cells={0,5,0,0,0,0,0,7};boundary_request.shape={2,2,2};boundary_request.block_shape={1,1,1};",
        19: "boundary_request.square_matrix={1,2,2,3};boundary_request.matrix_order=2;",
        20: "boundary_request.binary_raster={1,1,1,1};boundary_request.raster_order=2;",
        21: "boundary_request.mask_bits={1,1,0,1};boundary_request.interval_hint=1;boundary_request.query_index=4;",
        22: "boundary_request.update_triples={2,1,5,2,3,0,1,2,7};boundary_request.coordinate_limit=3;boundary_request.default_value=0;",
        23: "boundary_request.bin_counts={0,4,0,0};boundary_request.gap_hint=1;",
        24: "boundary_request.byte_values={0,1};boundary_request.plane_hint=1;",
    }
    special_invalid = {
        5: "invalid_request=request;invalid_request.null_sentinel=0;",
        6: "invalid_request=request;invalid_request.anchor_stride=0;",
        7: "invalid_request=request;invalid_request.maximum_row_length=0;",
        9: "invalid_request=request;invalid_request.value_validity.pop_back();",
        10: 'invalid_request=request;invalid_request.requested_schema={"missing"};',
        18: "invalid_request=request;invalid_request.shape.clear();",
        22: "invalid_request=request;invalid_request.coordinate_limit=0;",
    }
    setup = {
        "empty": special_empty.get(index, f"empty_request.{primary}.clear();"),
        "invalid": special_invalid.get(
            index, f"invalid_request=request;invalid_request.{width}=0;"
        ),
        "duplicate_order": special_duplicate.get(
            index,
            f"std::reverse(duplicate_order_request.{primary}.begin(),duplicate_order_request.{primary}.end());",
        ),
        "absent_tie": special_absent.get(index, f"absent_tie_request.{parameter}=2147483647;"),
        "overflow_tail": special_overflow.get(
            index, f"overflow_tail_request.{primary}.push_back(2147483647);"
        ),
        "malformed": special_malformed.get(index, f"malformed_request.{width}=-1;"),
        "boundary": special_boundary.get(
            index,
            f"if(!boundary_request.{primary}.empty())boundary_request.{primary}.resize(1);",
        ),
    }
    duplicate_invalid = {6, 9, 10, 12, 13, 14, 15, 16, 17, 22}
    absent_invalid: set[int] = set()
    overflow_invalid = {0, 3, 8, 9, 10, 11, 14, 15, 17, 18, 19, 20, 21, 22, 24}
    blocks = []
    for ordinal, category in enumerate(CASE_COVERAGE[case.task_id]):
        if category == "normal":
            continue
        mutation = setup[category]
        if category == "malformed":
            blocks.append(
                f"// contract-case: {category}\n"
                f"auto malformed_request=request;auto malformed_result={case.snake}(malformed_request);"
                f"if(!malformed_result.valid||!{_validator_name(case)}(malformed_request,malformed_result))return {40 + ordinal};"
                f"{_malformed_result_mutation(index)}"
                f"if({_validator_name(case)}(malformed_request,malformed_result))return {40 + ordinal};"
            )
            continue
        must_reject = (
            category in {"invalid", "malformed"}
            or (category == "duplicate_order" and index in duplicate_invalid)
            or (category == "absent_tie" and index in absent_invalid)
            or (category == "overflow_tail" and index in overflow_invalid)
        )
        assertion = (
            f"if({category}_result.valid||!{category}_result.{data}.empty()||"
            f"!{category}_result.{aux}.empty()||!{category}_result.{restored}.empty())"
            if must_reject
            else (
                f"if(!{category}_result.valid||!{_validator_name(case)}({category}_request,{category}_result)||"
                f"{_accepted_semantic_assertion(case, index, category)})"
            )
        )
        blocks.append(
            f"// contract-case: {category}\n"
            f"auto {category}_request=request;{mutation}"
            f"auto {category}_result={case.snake}({category}_request);"
            f"{assertion}return {40 + ordinal};"
        )
    return "".join(blocks) + (f"auto rejected={case.snake}(request);if(!rejected.valid)return 90;")


def _special_test(case: Case, index: int, *, private: bool, include_validator: bool) -> str | None:
    request = case.result_type.removesuffix("Result") + "Request"
    specifications: dict[int, tuple[str, str]] = {
        5: (
            f"const {request} request{{{{4,-1,2,4,3,-1}},-1}};",
            "if(result.dictionary_ids!=std::vector<int>{2,-1,0,2,1,-1}||result.sorted_dictionary!=std::vector<int>{2,3,4}||result.validity_words!=std::vector<int>{29}||result.decoded_values!=request.nullable_values)return 2;",
        ),
        6: (
            f"""const {request} request{{{{"aa/a","aa/b","ab/a"}},2}};""",
            """if(result.common_prefix_lengths!=std::vector<int>{0,3,1}||result.suffixes!=std::vector<std::string>{"aa/a","b","b/a"}||result.anchors!=std::vector<std::string>{"aa/a","ab/a"}||result.decoded_paths!=request.ordered_paths)return 2;""",
        ),
        7: (
            f"const {request} request{{{{{{1,2}},{{}},{{3,4,5}}}},3U}};",
            "if(result.payload!=std::vector<int>{1,2,3,4,5}||result.row_offsets!=std::vector<int>{0,2,2,5}||result.decoded_rows!=request.rows)return 2;",
        ),
        9: (
            f"const {request} request{{{{1,2,3}},{{10,99,30}},{{1,0,1}}}};",
            "if(result.id_column!=std::vector<int>{1,2,3}||result.value_column!=std::vector<int>{10,0,30}||result.validity_words!=std::vector<int>{5}||result.decoded_records!=std::vector<int>{1,10,2,0,3,30})return 2;",
        ),
        10: (
            f"""const {request} request{{{{"id","score","flag"}},{{"flag","id","score"}},{{1,10,0,2,20,1}}}};""",
            "if(result.schema_map!=std::vector<int>{2,0,1}||result.permuted_cells!=std::vector<int>{0,1,10,1,2,20}||result.decoded_table!=request.flat_table)return 2;",
        ),
        17: (
            f"const {request} request{{{{1,4,7,9}},3,12,7}};",
            "if(result.remainders!=std::vector<int>{1,1,1,0}||result.bucket_offsets!=std::vector<int>{0,1,2,3,4}||result.decoded_members!=request.members||result.bucket_count!=4||!result.contains_member)return 2;",
        ),
        18: (
            f"const {request} request{{{{0,2,0,3,0,4}},{{1,2,3}},{{1,1,2}}}};",
            "if(result.block_coordinates!=std::vector<int>{0,0,0,0,1,0,0,1,1}||result.dense_block_payloads!=std::vector<int>{0,2,3,0,4,0}||result.block_offsets!=std::vector<int>{0,2,4,6}||result.decoded_cells!=request.dense_cells)return 2;",
        ),
        22: (
            f"const {request} request{{{{2,0,5,2,1,7,1,0,3}},3,0}};",
            "if(result.overlay_pairs!=std::vector<int>{1,3,2,7}||result.sequence_metadata!=std::vector<int>{1,0,2,1}||result.decoded_overlay!=std::vector<int>{0,3,7})return 2;",
        ),
    }
    selected = specifications.get(index)
    if selected is None:
        return None
    setup, assertion = selected
    extra = ""
    if private:
        extra = _contract_case_program(case, index)
    marker = "" if private else "// contract-case: normal\n"
    validator_using = (
        f"using representation_curriculum::{_validator_name(case)};\n" if include_validator else ""
    )
    validator_assertion = (
        f"if(!{_validator_name(case)}(request,result))return 3;" if include_validator else ""
    )
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <string>
#include <vector>
using representation_curriculum::{request};
using representation_curriculum::{case.snake};
{validator_using}int main(){{
{marker}{setup}auto result={case.snake}(request);if(!result.valid)return 1;{assertion}{validator_assertion}{extra}return 0;
}}
'''


def _test(
    case: Case,
    index: int,
    *,
    private: bool,
    opposite: bool = False,
    include_validator: bool = True,
) -> str:
    special = _special_test(case, index, private=private, include_validator=include_validator)
    if special is not None:
        return special
    data, aux = _oracle(case, index)
    if opposite:
        data = list(reversed(data))
    values_name, width_name, parameter_name, data_name, aux_name, restored_name, _ = _api(index)
    request = case.result_type.removesuffix("Result") + "Request"
    restored = data if index in {14, 22} else list(case.sample)
    sample = ",".join(str(value) for value in case.sample)
    expected_data = ",".join(str(value) for value in data)
    expected_aux = ",".join(str(value) for value in aux)
    expected_restored = ",".join(str(value) for value in restored)
    marker = "" if private else "// contract-case: normal\n"
    validator_assertion = (
        f"if(!{_validator_name(case)}(request,result))return 5;" if include_validator else ""
    )
    validator_using = (
        f"using representation_curriculum::{_validator_name(case)};\n" if include_validator else ""
    )
    common = f"""{marker}const {request} request{{{{{sample}}},{case.width},{case.parameter}}};auto result={case.snake}(request);if(!result.valid)return 1;if(result.{restored_name}!=std::vector<int>{{{expected_restored}}})return 2;if(result.{data_name}!=std::vector<int>{{{expected_data}}})return 3;if(result.{aux_name}!=std::vector<int>{{{expected_aux}}})return 4;{validator_assertion}"""
    tail = ""
    if private:
        tail = _contract_case_program(case, index)
    return f'''#include "{case.task_id}.h"\n#include <algorithm>\n#include <vector>\nusing representation_curriculum::{request};\nusing representation_curriculum::{case.snake};\n{validator_using}int main(){{{common}{tail}return 0;}}\n'''


def _negative_test(case: Case, index: int, *, opposite: bool = False) -> str:
    """Exercise the false substitute without linking the public validator."""
    return _test(
        case,
        index,
        private=False,
        opposite=opposite,
        include_validator=False,
    ).replace("// contract-case: normal\n", "")


def _cmake(case: Case) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({case.snake} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_compile_options(-Wall -Wextra -Wpedantic -Werror)
enable_testing()
add_executable(visible {case.task_id}.cpp visible_test.cpp)
add_executable(private {case.task_id}.cpp .meta/private_test.cpp)
add_executable(negative .meta/negative_false_substitute.cpp .meta/negative_test.cpp)
target_include_directories(visible PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}")
target_include_directories(private PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}")
target_include_directories(negative PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}")
add_test(NAME visible COMMAND visible)
add_test(NAME private COMMAND private)
"""


def _render(case: Case, index: int, root: Path, *, control: str | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".docs").mkdir(exist_ok=True)
    (root / ".meta").mkdir(exist_ok=True)
    opposite = control == "opposite-end-selection"
    fields = _api(index)
    header = _header(case, index)
    starter = _starter(case, index)
    reference = _source(case, index, opposite=opposite)
    negative = _source(case, index, negative=True, opposite=opposite)
    negative_test = _negative_test(case, index, opposite=opposite)
    visible = _test(case, index, private=False, opposite=opposite)
    private = _test(case, index, private=True, opposite=opposite)
    instructions = f"""# Instructions\n\nImplement `{case.snake}` in namespace `representation_curriculum` using the request and result types declared in `{case.task_id}.h`. Also implement `validate_{case.snake}_encoding(request, encoded)`: it must inspect the supplied emitted fields, reject malformed or noncanonical state, and must not call `{case.snake}` or regenerate a replacement result.\n\n{case.contract}\n\nRules: {RULES[index]} Invalid input is failure-atomic: `valid` remains false and `{fields[3]}`, `{fields[4]}`, and `{fields[5]}` remain empty. Arithmetic is checked before narrowing to `int`; duplicates, absent queries, ordering, equality ties, empty input, and overflow follow the rule stated above rather than any assumed default.\n\n## Example\n\n{BOUNDARY_EXAMPLES[index]}\n\nDerive `{fields[5]}` by decoding `{fields[3]}` plus `{fields[4]}` (or by applying the documented canonical transform) instead of copying the request's `{fields[0]}`: only a genuine decode proves the encoding round-trips. Build the encoded form with {case.mechanism}; incidental vectors, validation maps, and work buffers are fine, but choosing to {case.false_substitute} instead is not permitted.\n"""
    instructions += "\n## Public behavior table\n\n" + "".join(
        f"- `{category}`: {detail}\n" for category, detail in BEHAVIOR_CASES[case.task_id].items()
    )
    introduction = f"# {case.title}\n\n{INTRODUCTIONS[case.task_id]}\n"
    if control == "domain-identifier-renamed":
        replacement = case.snake + "_renamed"
        request_type = case.result_type.removesuffix("Result") + "Request"
        for old, new in (
            (case.snake, replacement),
            (case.result_type, case.result_type + "Renamed"),
            (request_type, request_type + "Renamed"),
        ):
            header = header.replace(old, new)
            starter = starter.replace(old, new)
            reference = reference.replace(old, new)
            negative = negative.replace(old, new)
            negative_test = negative_test.replace(old, new)
            visible = visible.replace(old, new)
            private = private.replace(old, new)
        instructions = instructions.replace(case.snake, replacement).replace(
            "representation", "storage"
        )
        introduction = introduction.replace("representation", "storage")
    elif control == "constants-policy-only":
        header = header.replace(f"int {fields[2]}=0", f"int {fields[2]}=3")
        instructions += "\nControl policy constant revision: an omitted reserved hint defaults to three; it remains semantically ignored.\n"
    elif opposite:
        instructions += (
            "\nControl endpoint policy emits the encoded stream from the opposite end.\n"
        )
    files = {
        ".docs/introduction.md": introduction,
        ".docs/instructions.md": instructions,
        f"{case.task_id}.h": header,
        f"{case.task_id}.cpp": starter,
        "visible_test.cpp": visible,
        ".meta/example.h": header,
        ".meta/example.cpp": reference,
        ".meta/private_test.cpp": private,
        ".meta/negative_false_substitute.cpp": negative,
        ".meta/negative_test.cpp": negative_test,
        "CMakeLists.txt": _cmake(case),
        ".meta/tests.toml": f'[visible]\ndescription="canonical {case.mechanism} example"\n[private]\ndescription="round trip/query, invalid boundary, canonical encoding"\n[negative]\ndescription="rejects topic-specific substitute: {case.false_substitute}"\n',
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _json(
        root / ".meta/config.json",
        {
            "authors": ["w8-biayn"],
            "blurb": case.mechanism,
            "files": {
                "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
                "test": ["visible_test.cpp", ".meta/private_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        },
    )
    _json(
        root / ".meta/provenance.json",
        {
            "schema_version": "sparse-compressed-tabular-provenance-v1",
            "task_id": case.task_id,
            "family_id": FAMILY_ID,
            "lineage": "new-root",
            "task_spec_revision": 1,
            "source": str(CURRICULUM.relative_to(REPO_ROOT)),
            "owner": OWNER,
            "authoring": "clean-room repository-authored",
            "license": "CC0-1.0",
            "count_plan_cell": "text/grid/logic: sparse, compressed, tabular, and round-trip representations / 25",
            "mechanism": case.mechanism,
            "primary_core_objective": "achieved",
            "negative_fixture": case.false_substitute,
            "control": control,
            "non_claim": "local task candidate only; no SFT release, training authorization, or benchmark claim",
        },
    )


def materialize(out: Path = DEFAULT_OUT, *, force: bool = False) -> dict[str, object]:
    out = _safe_out(out)
    inventory = _existing_inventory(out)
    existing_ids = {row["task_id"] for rows in inventory.values() for row in rows}
    collisions = sorted(existing_ids & {case.task_id for case in CASES})
    history: dict[Path, bytes] = {}
    if collisions:
        _fail("duplicate_task", ",".join(collisions))
    if out.exists():
        manifest_path = out / ".state/materialization-manifest.json"
        if not force:
            _fail("output_exists", str(out))
        if (
            not manifest_path.is_file()
            or json.loads(manifest_path.read_text()).get("owner") != OWNER
        ):
            _fail("foreign_output_root", str(out))
        state = out / ".state"
        for path in state.rglob("*") if state.is_dir() else ():
            if path.is_file() and path.relative_to(state).parts[0] in {
                "cycles",
                "audits",
                "remedy",
                "invalidated",
            }:
                history[path.relative_to(state)] = path.read_bytes()
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for index, case in enumerate(CASES):
        _render(case, index, out / case.task_id)
    for control in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        _render(CASES[4], 4, out / ".state/adversarial-clone-controls" / control, control=control)
    for relative, data in history.items():
        path = out / ".state" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    _json(out / ".state/source-inventory.json", _inventory_payload(inventory))
    manifest = {
        "schema_version": "sparse-compressed-tabular-family-v1",
        "family_id": FAMILY_ID,
        "owner": OWNER,
        "owner_hash": _file_sha(REPO_ROOT / OWNER),
        "curriculum": str(CURRICULUM.relative_to(REPO_ROOT)),
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec": str(FAMILY_SPEC.relative_to(REPO_ROOT)),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "focused_test": str(TEST_PATH.relative_to(REPO_ROOT)),
        "focused_test_hash": _file_sha(TEST_PATH),
        "task_count": 25,
        "task_ids": [case.task_id for case in CASES],
        "status": "generated_pending_creator_preflight",
        "dataset_handoff": "not_requested",
        "selected_prompts": [
            "docs/aider-tasks-spec/prompts/generate-family-spec.md",
            "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
        ],
    }
    _json(out / ".state/materialization-manifest.json", manifest)
    manifest["tree_hash"] = _tree_hash(out)
    _json(out / ".state/materialization-manifest.json", manifest)
    return manifest


def _normalized(text: str) -> set[str]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\])*\"|\b-?\d+\b", " ", text, flags=re.S)
    text = re.sub(
        r"\b(front|back|first|last|left|right|earlier|later|reverse|minimum|maximum)\b",
        " endpoint ",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"sparse|compressed|tabular|column|table|representation|storage",
        " domain ",
        text,
        flags=re.I,
    )
    return set(re.findall(r"[a-z_][a-z_0-9]{2,}|==|!=|&&|\|\|", text.lower()))


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\])*\"|\b-?\d+\b", " LIT ", text, flags=re.S)
    text = re.sub(
        r"\b(front|back|first|last|left|right|earlier|later|reverse|minimum|maximum|opposite)\b",
        " ENDPOINT ",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(sparse|compressed|tabular|column|table|representation|storage)\b",
        " DOMAIN ",
        text,
        flags=re.I,
    )
    return tuple(
        re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|&&|\|\||[-+*/%{}()[\];,?:=.]", text.lower())
    )


def _dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    header = next(root.glob("*.h")).read_text()
    instructions = (root / ".docs/instructions.md").read_text()
    reference = (root / ".meta/example.cpp").read_text()
    visible = (root / "visible_test.cpp").read_text()
    private = (root / ".meta/private_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    provenance = json.loads((root / ".meta/provenance.json").read_text())
    mechanism = provenance["mechanism"] + " " + provenance["negative_fixture"]
    return {
        "public_api": _normalized_tokens(header + instructions + mechanism),
        "owned_state_algorithm": _normalized_tokens(reference + mechanism),
        "mutation_selection_rules": _normalized_tokens(instructions + reference + mechanism),
        "invalid_boundary_behavior": _normalized_tokens(instructions + private + mechanism),
        "reference_control_flow": _normalized_tokens(reference + mechanism),
        "deterministic_oracle": _normalized_tokens(visible + private + mechanism),
        "topic_negative_fixture": _normalized_tokens(negative + mechanism),
    }


def _token_similarity(left: tuple[str, ...], right: tuple[str, ...], width: int = 7) -> float:
    left_grams = {left[i : i + width] for i in range(max(0, len(left) - width + 1))}
    right_grams = {right[i : i + width] for i in range(max(0, len(right) - width + 1))}
    denominator = min(len(left_grams), len(right_grams))
    return len(left_grams & right_grams) / denominator if denominator else 1.0


def _pair_decisions(left: Path, right: Path) -> tuple[dict[str, bool], dict[str, float]]:
    a, b = _dimension_material(left), _dimension_material(right)
    similarities = {
        dimension: round(_token_similarity(a[dimension], b[dimension]), 6)
        for dimension in DIMENSIONS
    }
    return (
        {
            dimension: a[dimension] != b[dimension] and similarities[dimension] < 0.90
            for dimension in DIMENSIONS
        },
        similarities,
    )


def diversity_screen(out: Path = DEFAULT_OUT) -> dict[str, object]:
    out = _safe_out(out)
    pairs = []
    roots = [out / case.task_id for case in CASES]
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions, similarities = _pair_decisions(left, right)
            if not all(decisions.values()):
                _fail(
                    "duplicate_family", f"{left.name} vs {right.name}: {decisions}; {similarities}"
                )
            pairs.append(
                {
                    "left": left.name,
                    "right": right.name,
                    "decisions": decisions,
                    "similarities": similarities,
                }
            )
    if len(pairs) != 300:
        _fail("duplicate_family", f"pair count {len(pairs)}")
    base = out / CASES[4].task_id
    controls = {}
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        root = out / ".state/adversarial-clone-controls" / name
        decisions, similarities = _pair_decisions(base, root)
        changed = _tree_hash(root) != _tree_hash(base)
        production_rejected = not all(decisions.values())
        controls[name] = {
            "decisions": decisions,
            "similarities": similarities,
            "production_rejected": production_rejected,
            "tree_hash": _tree_hash(root),
            "changed_files_nonempty": changed,
        }
        if not changed or not production_rejected:
            _fail("clone_control_failed", f"{name}: {decisions}; {similarities}")
    result = {
        "schema_version": "sparse-compressed-tabular-diversity-v2",
        "status": "pass",
        "root_count": 25,
        "pair_count": 300,
        "dimensions": list(DIMENSIONS),
        "pairs": pairs,
        "controls": controls,
        "threshold": 0.90,
        "normalizer": "sct-v2-domain-literal-endpoint-neutral-seven-gram-containment",
    }
    _json(out / ".state/diversity-screen.json", result)
    return result


def _prompt_role_check(out: Path, case: Case) -> dict[str, object]:
    root = out / case.task_id
    config = json.loads((root / ".meta/config.json").read_text())
    expected = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
    if config["files"]["solution"] != expected or config["files"]["example"] != [
        ".meta/example.h",
        ".meta/example.cpp",
    ]:
        _fail("target_reference_mismatch", case.task_id)
    task = load_task(root)
    prompt = build_prompt(task)
    if any(
        marker in prompt
        for marker in (".meta/", "CMakeLists", "private_test", "negative_false", "provenance")
    ):
        _fail("prompt_contract_incomplete", case.task_id)
    answer = build_assistant_response(task, load_example_files_from_config(root))
    if not answer.startswith(f"{case.task_id}.h\n```") or f"{case.task_id}.cpp\n```" not in answer:
        _fail("target_reference_mismatch", case.task_id)
    return {
        "task_id": case.task_id,
        "prompt_hash": _sha(prompt.encode()),
        "answer_hash": _sha(answer.encode()),
    }


def _holdout_screen(out: Path) -> dict[str, object]:
    found = (
        {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()}
        if HOLDOUT_ROOT.is_dir()
        else set()
    )
    if found != OFFICIAL_HOLDOUTS:
        _fail("benchmark_screen_not_completed", f"found {len(found)} holdouts")
    strongest = 0.0
    strongest_pair = []
    comparisons = 0
    holdout_inventory = []
    for case in CASES:
        candidate_root = out / case.task_id
        candidate = _normalized(
            "\n".join(
                path.read_text(errors="ignore")
                for path in sorted(candidate_root.rglob("*"))
                if path.is_file()
                and ".state" not in path.relative_to(candidate_root).parts
                and path.stat().st_size < 1_000_000
            )
        )
        for holdout in sorted(OFFICIAL_HOLDOUTS):
            holdout_root = HOLDOUT_ROOT / holdout
            role_files = [
                path
                for path in sorted(holdout_root.rglob("*"))
                if path.is_file()
                and ".git" not in path.relative_to(holdout_root).parts
                and path.stat().st_size < 1_000_000
            ]
            other = _normalized("\n".join(path.read_text(errors="ignore") for path in role_files))
            if len(holdout_inventory) < len(OFFICIAL_HOLDOUTS):
                holdout_inventory.append(
                    {
                        "task_id": holdout,
                        "role_count": len(role_files),
                        "full_role_hash": _sha(
                            b"\0".join(
                                path.relative_to(holdout_root).as_posix().encode()
                                + b"\0"
                                + path.read_bytes()
                                for path in role_files
                            )
                        ),
                    }
                )
            score = len(candidate & other) / len(candidate | other) if candidate | other else 0.0
            comparisons += 1
            if score > strongest:
                strongest = score
                strongest_pair = [case.task_id, holdout]
            if score >= 0.55:
                _fail("benchmark_content_overlap", f"{case.task_id}:{holdout}:{score:.3f}")
    return {
        "status": "pass",
        "holdout_root_count": 26,
        "comparison_count": comparisons,
        "strongest_jaccard": round(strongest, 6),
        "strongest_pair": strongest_pair,
        "material": "complete official holdout docs, APIs, references, tests, and oracle logic",
        "inventory_hash": _sha(
            json.dumps(holdout_inventory, sort_keys=True, separators=(",", ":")).encode()
        ),
    }


def _cross_tree_screen(out: Path) -> dict[str, object]:
    strongest = 0.0
    strongest_pair = []
    comparisons = 0
    inventory = []
    inventory_path = out / ".state/source-inventory.json"
    frozen = json.loads(inventory_path.read_text())
    current_materials = {
        case.task_id: _normalized(
            "\n".join(
                path.read_text(errors="ignore")
                for path in sorted((out / case.task_id).rglob("*"))
                if path.is_file() and path.stat().st_size < 1_000_000
            )
        )
        for case in CASES
    }
    trees = (
        ("legacy", LEGACY_ROOTS[0]),
        ("reverify", LEGACY_ROOTS[1]),
        ("expansion_before", EXPANSION_ROOT),
    )
    frozen_roots = frozen.get("roots", {})
    for tree_name, legacy in trees:
        section = frozen_roots.get(tree_name)
        if not isinstance(section, dict) or not isinstance(section.get("records"), list):
            _fail("inventory_drift_retry_required", f"missing frozen {tree_name}")
        records = section["records"]
        if section.get("count") != len(records) or section.get("sha256") != _sha(
            json.dumps(records, sort_keys=True).encode()
        ):
            _fail("inventory_drift_retry_required", f"corrupt frozen {tree_name}")
        # Do not re-discover with a permissive live walk. Every frozen root must
        # still exist with the exact hashes; additions are caught by a second
        # complete inventory comparison below. rglob("*") is used only for the
        # full role material of each frozen root.
        for record in records:
            root = legacy / record["relative_root"]
            config = root / ".meta/config.json"
            if (
                not config.is_file()
                or _tree_hash(root) != record["tree_hash"]
                or _file_sha(config) != record["config_hash"]
            ):
                _fail(
                    "inventory_drift_retry_required",
                    f"changed {tree_name}:{record['relative_root']}",
                )
            material = "\n".join(
                path.read_text(errors="ignore")
                for path in sorted(root.rglob("*"))
                if path.is_file()
                and ".state" not in path.relative_to(root).parts
                and path.stat().st_size < 1_000_000
            )
            root_hash = record["tree_hash"]
            config_hash = record["config_hash"]
            other = _normalized(material)
            inventory.append(
                {
                    "tree": tree_name,
                    "root": record["relative_root"],
                    "tree_hash": root_hash,
                    "config_hash": config_hash,
                }
            )
            for case in CASES:
                current = current_materials[case.task_id]
                score = len(current & other) / len(current | other) if current | other else 0.0
                comparisons += 1
                if score > strongest:
                    strongest = score
                    strongest_pair = [
                        case.task_id,
                        f"{tree_name}:{record['relative_root']}",
                    ]
                if score >= 0.72:
                    _fail("duplicate_family", f"cross-tree {score:.3f}: {strongest_pair}")
    current = _existing_inventory(out)
    for name in ("legacy", "reverify", "expansion_before"):
        current_rows = current[name]
        frozen_rows = frozen_roots[name]["records"]
        if current_rows != frozen_rows:
            _fail(
                "inventory_drift_retry_required",
                f"{name}: frozen={len(frozen_rows)} current={len(current_rows)}",
            )
    return {
        "status": "pass",
        "comparison_count": comparisons,
        "comparator_root_count": len(inventory),
        "frozen_inventory_verified_current": True,
        "source_inventory_hash": _file_sha(inventory_path),
        "inventory_hash": _sha(
            json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
        ),
        "trees": [name for name, _ in trees],
        "material": "complete emitted docs, APIs, starters, references, tests, oracle metadata, and negatives",
        "threshold": 0.72,
        "strongest_jaccard": round(strongest, 6),
        "strongest_pair": strongest_pair,
    }


def _verify_one_host(root: Path, work: Path, *, sanitizer: bool) -> dict[str, object]:
    """Host-side equivalent of the locked docker run_one recipe for one root."""
    shutil.copytree(root, work)
    config = json.loads((work / ".meta/config.json").read_text())
    header, source = config["files"]["solution"]
    shutil.copyfile(work / ".meta/example.h", work / header)
    shutil.copyfile(work / ".meta/example.cpp", work / source)
    build = work / "build"
    configure = ["cmake", "-S", str(work), "-B", str(build), "-G", "Unix Makefiles"]
    if sanitizer:
        configure += [
            "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
            "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
        ]
    subprocess.run(configure, check=True, capture_output=True, text=True)
    subprocess.run(
        ["cmake", "--build", str(build), "--parallel", "2"],
        check=True,
        capture_output=True,
        text=True,
    )
    discovered = subprocess.run(
        ["ctest", "--test-dir", str(build), "-N"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"Total Tests: (\d+)", discovered.stdout)
    count = int(match.group(1)) if match else 0
    if count != 2:
        _fail("sanitizer_test_count_mismatch", f"{root.name}:{count}")
    env = {
        **os.environ,
        "ASAN_OPTIONS": "detect_leaks=0",
        "UBSAN_OPTIONS": "halt_on_error=1",
    }
    subprocess.run(
        ["ctest", "--test-dir", str(build), "--output-on-failure"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    negative = subprocess.run(
        [str(build / "negative")], capture_output=True, text=True, env=env
    )
    if negative.returncode == 0:
        _fail("negative_fixture_not_rejected", root.name)
    if re.search(
        r"AddressSanitizer|UndefinedBehaviorSanitizer|runtime error:",
        negative.stdout + negative.stderr,
    ):
        _fail("negative_fixture_sanitizer_noise", root.name)
    mode = "sanitizer" if sanitizer else "normal"
    return {mode: {"discovered_tests": count, "passed": True, "negative_rejected_clean": True}}


def verify_host(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Owner-designated host runtime verification (campaign gate: host only)."""
    out = _safe_out(out)
    verify_core(out)
    controls = out / ".state/adversarial-clone-controls"
    roots: list[tuple[str, Path]] = [(case.task_id, out / case.task_id) for case in CASES]
    roots += [
        (f"control:{name}", controls / name)
        for name in (
            "domain-identifier-renamed",
            "constants-policy-only",
            "opposite-end-selection",
        )
    ]
    with tempfile.TemporaryDirectory(prefix="sct-host-") as temporary:
        temp = Path(temporary)
        records: dict[str, object] = {}
        for key, root in roots:
            record: dict[str, object] = {}
            record.update(
                _verify_one_host(root, temp / f"{key.replace(':', '-')}-normal", sanitizer=False)
            )
            record.update(
                _verify_one_host(root, temp / f"{key.replace(':', '-')}-sanitizer", sanitizer=True)
            )
            records[key] = record
    compiler = subprocess.run(
        ["c++", "--version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    compiler_path = shutil.which("c++") or "c++"
    cmake_version = subprocess.run(
        ["cmake", "--version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    receipt = {
        "schema_version": "sparse-compressed-tabular-host-verify-v1",
        "status": "pass",
        "evidence_class": "host_iteration",
        "root_count": len(CASES),
        "control_count": 3,
        "records": records,
        "family_tree_hash": _tree_hash(out),
        "manifest_hash": _file_sha(out / ".state/materialization-manifest.json"),
        "owner_hash": _file_sha(REPO_ROOT / OWNER),
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "focused_test_hash": _file_sha(TEST_PATH),
        "compiler": {
            "path": compiler_path,
            "version": compiler,
            "sha256": _file_sha(Path(compiler_path)),
        },
        "cmake": cmake_version,
    }
    _json(out / ".state/host-verify.json", receipt)
    return receipt


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    out = _safe_out(out)
    if len(CASES) != 25 or len({case.task_id for case in CASES}) != 25:
        _fail("duplicate_task", "expected 25")
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("task_ids") != [case.task_id for case in CASES] or manifest.get(
        "tree_hash"
    ) != _tree_hash(out):
        _fail("generator_output_drift", "manifest/tree")
    roles = [_prompt_role_check(out, case) for case in CASES]
    if (
        len({row["prompt_hash"] for row in roles}) != 25
        or len({row["answer_hash"] for row in roles}) != 25
    ):
        _fail("duplicate_family", "prompt/answer hash")
    screen = diversity_screen(out)
    holdout = _holdout_screen(out)
    cross_tree = _cross_tree_screen(out)
    current_ids = {
        row["task_id"]
        for root in (*LEGACY_ROOTS, EXPANSION_ROOT)
        for row in _inventory(root, exclude=out)
    }
    if current_ids & set(manifest["task_ids"]):
        _fail("duplicate_task", "late collision")
    rows = []
    for case in CASES:
        root = out / case.task_id
        role = next(r for r in roles if r["task_id"] == case.task_id)
        rows.append(
            {
                "task_id": case.task_id,
                "tree_hash": _tree_hash(root),
                "prompt_hash": role["prompt_hash"],
                "starter_hash": _file_sha(root / f"{case.task_id}.cpp"),
                "reference_hash": _file_sha(root / ".meta/example.cpp"),
                "visible_test_hash": _file_sha(root / "visible_test.cpp"),
                "hidden_test_hash": _file_sha(root / ".meta/private_test.cpp"),
                "negative_hash": _file_sha(root / ".meta/negative_false_substitute.cpp"),
                "primary_core_objective": "achieved",
            }
        )
    manifest.update(
        {
            "tree_hash": _tree_hash(out),
            "tasks": rows,
            "screens": {
                "prompt_boundary": "pass",
                "reference_mapping": "pass",
                "diversity": {"status": "pass", "pair_count": screen["pair_count"]},
                "benchmark_holdout": holdout,
                "cross_tree": cross_tree,
            },
            "status": "creator_structural_preflight_pass_pending_runtime",
        }
    )
    _json(manifest_path, manifest)
    return manifest


def _archive(out: Path, target: Path) -> str:
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        roots = [out / case.task_id for case in CASES] + [
            out / ".state/adversarial-clone-controls" / name
            for name in (
                "domain-identifier-renamed",
                "constants-policy-only",
                "opposite-end-selection",
            )
        ]
        for root in roots:
            prefix = "tasks" if root.parent == out else "controls"
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                info = archive.gettarinfo(
                    str(path), arcname=f"{prefix}/{root.name}/{path.relative_to(root).as_posix()}"
                )
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
    return _file_sha(target)


def _archive_tree_hash(out: Path) -> str:
    digest = hashlib.sha256()
    roots = [out / case.task_id for case in CASES] + [
        out / ".state/adversarial-clone-controls" / name
        for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection")
    ]
    entries: list[tuple[str, Path]] = []
    for root in roots:
        prefix = "tasks" if root.parent == out else "controls"
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            relative = f"{prefix}/{root.name}/{path.relative_to(root).as_posix()}"
            entries.append((relative, path))
    for relative, path in sorted(entries):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _require_verified_core_snapshot(out: Path) -> dict[str, object]:
    manifest = json.loads((out / ".state/materialization-manifest.json").read_text())
    expected = {
        "owner_hash": _file_sha(REPO_ROOT / OWNER),
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "focused_test_hash": _file_sha(TEST_PATH),
        "tree_hash": _tree_hash(out),
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            _fail("verified_core_snapshot_stale", field)
    cross_tree = manifest.get("screens", {}).get("cross_tree", {})
    if (
        manifest.get("status") != "creator_structural_preflight_pass_pending_runtime"
        or cross_tree.get("status") != "pass"
        or cross_tree.get("frozen_inventory_verified_current") is not True
    ):
        _fail("verified_core_snapshot_stale", "status/screens")
    return manifest


def verify_docker(
    out: Path = DEFAULT_OUT,
    image: str = SANITY_IMAGE,
    *,
    reuse_verified_core: bool = False,
) -> dict[str, object]:
    out = _safe_out(out)
    if reuse_verified_core:
        _require_verified_core_snapshot(out)
    else:
        verify_core(out)
    inspected = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if inspected.returncode:
        _fail("docker_sanity_not_completed", inspected.stderr.strip())
    with tempfile.TemporaryDirectory(prefix="sct-expansion-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        result = temp / "result"
        result.mkdir()
        archive_hash = _archive(out, archive)
        expected_extracted_hash = _archive_tree_hash(out)
        script = r"""set -Eeuo pipefail
mkdir -p /work /result
tar -xf /input/family.tar -C /work
python3 - <<'PY' > /result/extracted.tree.sha256
import hashlib
from pathlib import Path
root=Path('/work');digest=hashlib.sha256()
for path in sorted(item for item in root.rglob('*') if item.is_file()):
    digest.update(path.relative_to(root).as_posix().encode());digest.update(b'\0');digest.update(path.read_bytes());digest.update(b'\0')
print('sha256:'+digest.hexdigest())
PY
sha256sum /input/family.tar | awk '{print $1}' > /result/archive.sha256
command -v c++ > /result/compiler.path
c++ --version | head -1 > /result/compiler.version
sha256sum "$(command -v c++)" | awk '{print $1}' > /result/compiler.sha256
cmake --version | head -1 > /result/cmake.version
run_one(){ kind="$1";id="$2";mode="$3";root="/work/$kind/$id";work="/tmp/$kind-$id-$mode";cp -a "$root" "$work";cfg="$work/.meta/config.json";header=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["files"]["solution"][0])' "$cfg");source=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["files"]["solution"][1])' "$cfg");cp "$work/.meta/example.h" "$work/$header";cp "$work/.meta/example.cpp" "$work/$source";flags=();if [ "$mode" = sanitizer ];then flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined");fi;cmake -S "$work" -B "$work/build" -G "Unix Makefiles" "${flags[@]}";cmake --build "$work/build" --parallel 2;count=$(ctest --test-dir "$work/build" -N|sed -n 's/^Total Tests: //p');test "$count" = 2;ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "$work/build" --output-on-failure;negative_log="$work/negative.$mode.log";set +e;ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "$work/build/negative" >"$negative_log" 2>&1;negative_status=$?;set -e;test "$negative_status" -ne 0;if grep -Eq 'AddressSanitizer|UndefinedBehaviorSanitizer|runtime error:' "$negative_log";then cat "$negative_log";return 1;fi;printf '%s\t%s\t%s\t%s\t%s\tclean\n' "$kind" "$id" "$mode" "$count" "$negative_status" >>/result/results.tsv;}
for root in /work/tasks/*;do id=${root##*/};run_one tasks "$id" normal;run_one tasks "$id" sanitizer;done
for root in /work/controls/*;do id=${root##*/};run_one controls "$id" normal;run_one controls "$id" sanitizer;done
"""
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
        if completed.returncode:
            _fail("docker_sanity_failed", (completed.stdout + completed.stderr)[-12000:])
        mounted = "sha256:" + (result / "archive.sha256").read_text().strip()
        if mounted != archive_hash:
            _fail("grader_mount_hash_mismatch", f"{mounted}!={archive_hash}")
        extracted_hash = (result / "extracted.tree.sha256").read_text().strip()
        if extracted_hash != expected_extracted_hash:
            _fail(
                "grader_mount_hash_mismatch",
                f"extracted {extracted_hash}!={expected_extracted_hash}",
            )
        rows = [line.split("\t") for line in (result / "results.tsv").read_text().splitlines()]
        task_rows = [row for row in rows if row[0] == "tasks"]
        control_rows = [row for row in rows if row[0] == "controls"]
        if (
            len(task_rows) != 50
            or len(control_rows) != 6
            or any(row[3] != "2" or row[4] == "0" or row[5] != "clean" for row in rows)
        ):
            _fail(
                "sanitizer_test_count_mismatch",
                f"tasks={len(task_rows)} controls={len(control_rows)}",
            )
        manifest = json.loads((out / ".state/materialization-manifest.json").read_text())
        task_bindings = []
        for task in manifest["tasks"]:
            task_bindings.append(
                {
                    **task,
                    "runtime": {
                        "normal": {"discovered_tests": 2, "passed": True},
                        "sanitizer": {"discovered_tests": 2, "passed": True},
                        "negative_fixture_executed_separately": True,
                        "negative_fixture_normal_clean": True,
                        "negative_fixture_sanitizer_clean": True,
                    },
                }
            )
        receipt = {
            "schema_version": "sparse-compressed-tabular-docker-sanity-v3",
            "status": "pass",
            "evidence_class": "locked_oracle",
            "locked_oracle": True,
            "network_policy": "none",
            "image": image,
            "image_id": inspected.stdout.strip(),
            "archive_hash": archive_hash,
            "mounted_archive_hash": mounted,
            "expected_extracted_tree_hash": expected_extracted_hash,
            "reconciled_extracted_tree_hash": extracted_hash,
            "family_tree_hash": _tree_hash(out),
            "manifest_hash": _file_sha(out / ".state/materialization-manifest.json"),
            "owner_hash": _file_sha(REPO_ROOT / OWNER),
            "curriculum_hash": _file_sha(CURRICULUM),
            "family_spec_hash": _file_sha(FAMILY_SPEC),
            "focused_test_hash": _file_sha(TEST_PATH),
            "compiler": {
                "path": (result / "compiler.path").read_text().strip(),
                "version": (result / "compiler.version").read_text().strip(),
                "sha256": "sha256:" + (result / "compiler.sha256").read_text().strip(),
            },
            "cmake": (result / "cmake.version").read_text().strip(),
            "commands": {
                "container": [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--mount",
                    "archive:readonly",
                    "--mount",
                    "result",
                    "IMAGE",
                    "bash",
                    "-lc",
                    "OWNER_SCRIPT",
                ],
                "configure_normal": ["cmake", "-S", "TASK", "-B", "BUILD", "-G", "Unix Makefiles"],
                "configure_sanitizer": [
                    "cmake",
                    "-S",
                    "TASK",
                    "-B",
                    "BUILD",
                    "-G",
                    "Unix Makefiles",
                    "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
                    "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                ],
                "build": ["cmake", "--build", "BUILD", "--parallel", "2"],
                "test": ["ctest", "--test-dir", "BUILD", "--output-on-failure"],
            },
            "task_results": task_bindings,
            "normal_reference_count": 25,
            "sanitizer_reference_count": 25,
            "test_count_per_root": 2,
            "negative_fixture_count": 25,
            "negative_fixture_normal_clean_count": 25,
            "negative_fixture_sanitizer_clean_count": 25,
            "control_count": 3,
        }
        _json(out / ".state/docker-sanity.json", receipt)
    manifest = json.loads((out / ".state/materialization-manifest.json").read_text())
    manifest.update(
        {
            "docker_sanity": {
                "status": "pass",
                "receipt": ".state/docker-sanity.json",
                "normal_reference_count": 25,
                "sanitizer_reference_count": 25,
                "negative_fixture_count": 25,
                "control_count": 3,
            },
            "status": "creator_preflight_passed_pending_independent_audit",
        }
    )
    _json(out / ".state/materialization-manifest.json", manifest)
    return receipt


def append_cycle(
    out: Path, status: str, *, audit: str | None = None, findings: Iterable[str] = ()
) -> Path:
    state = out / ".state/cycles"
    state.mkdir(parents=True, exist_ok=True)
    number = len(list(state.glob("cycle-*.json"))) + 1
    manifest = json.loads((out / ".state/materialization-manifest.json").read_text())
    record = {
        "schema_version": "aider-task-creator-cycle-v1",
        "cycle": number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "family_id": FAMILY_ID,
        "candidate_manifest": ".state/materialization-manifest.json",
        "family_tree_hash": _tree_hash(out),
        "curriculum_hash": _file_sha(CURRICULUM),
        "generator_hash": _file_sha(REPO_ROOT / OWNER),
        "focused_test_hash": _file_sha(TEST_PATH),
        "grader_policy_hash": _sha(
            (SANITY_IMAGE + "C++17;Unix Makefiles;ASan;UBSan;network=none").encode()
        ),
        "retained_root_ids": [case.task_id for case in CASES],
        "replaced_root_ids": [],
        "rejected_root_ids": [],
        "review_root_ids": [],
        "blocked_root_ids": [],
        "audit_report": audit,
        "finding_ids": sorted(findings),
        "audit_subject_hash": _sha(json.dumps(manifest, sort_keys=True).encode()),
        "docker_receipt": ".state/docker-sanity.json"
        if (out / ".state/docker-sanity.json").is_file()
        else None,
    }
    path = state / f"cycle-{number:02d}.json"
    _json(path, record)
    return path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--refresh-inventory", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--reuse-verified-core", action="store_true")
    parser.add_argument("--record-cycle", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.materialize:
        materialize(args.out, force=args.force)
    if args.refresh_inventory:
        refresh_inventory(args.out)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        verify_docker(args.out, args.image, reuse_verified_core=args.reuse_verified_core)
    if args.record_cycle:
        append_cycle(args.out, "creator_preflight" if args.docker_sanity else "generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
