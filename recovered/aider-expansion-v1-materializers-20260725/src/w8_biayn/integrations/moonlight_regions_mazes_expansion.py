"""Create and verify the 30-root regions-and-mazes expansion family."""

from __future__ import annotations

import argparse
import collections
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
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-expansion-v1/text-grid-logic/regions-mazes")
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_REGIONS_MAZES_EXPANSION_CURRICULUM.md"
)
FAMILY_SPEC = Path("docs/aider-tasks-spec/aider-text-grid-reshaping/regions-mazes-expansion.md")
GENERATOR_PATH = Path("src/w8_biayn/integrations/moonlight_regions_mazes_expansion.py")
TEST_PATH = Path("tests/test_moonlight_regions_mazes_expansion.py")
FAMILY_ID = "aider-expansion-v1-regions-mazes-v1"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
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
MODULUS = 1_000_003
INITIAL_AUDIT_REPORT = Path(".state/audits/regions-mazes-audit-20260722.md")
INITIAL_AUDIT_SHA256 = "sha256:e63a18977698dce2555589d88e608ca0ef7305112072256dfa15fc7189a9d85a"
REAUDIT_2_REPORT = Path(".state/audits/regions-mazes-independent-reaudit-2-20260722.md")
REAUDIT_2_SHA256 = "sha256:1b63c80690a516e9e348c82cdade56ddb57ebb56ead977a39d3c3732ffb0ba3c"
REAUDIT_3_REPORT = Path(".state/audits/regions-mazes-post-remediation-reaudit-3-20260722.md")
REAUDIT_3_SHA256 = "sha256:7f8f1a894d2e8bf85ae7dfec71c018587bb0e03c7c93e185374c8e5bee71983c"
REAUDIT_3_SUBJECT = "sha256:4da791c672fd70917d36946e0e46e14fae1347ce6f841e23c40cadf35a27d748"
REAUDIT_3_MANIFEST_SHA256 = (
    "sha256:8635e7170724b01c405b16d5b9998d02e813b5ae294661fbdeaf4bfc32d9ce88"
)
REAUDIT_3_OWNER_SHA256 = "sha256:c0dfbcfd91de76e4ae71230af3e5c1f44fd0821b05c8407743b58af2d42f6ac5"
REAUDIT_4_REPORT = Path(".state/audits/regions-mazes-post-remediation-reaudit-4-20260722.md")
REAUDIT_4_SHA256 = "sha256:cf1497edefca794c6fdb44bc36fdaa4b985b609d8e075b9122116df197205776"
REAUDIT_4_SUBJECT = "sha256:92c5fbb27886d92d4fb0a05fa8fe21122888d3d251fdaaa8bb9ed875ee7fa26a"
REAUDIT_4_MANIFEST_SHA256 = (
    "sha256:02c570f06efe15a5e128f805b3d57149fa8457c8ac90798ee72a1943e3bdecc7"
)
REAUDIT_4_OWNER_SHA256 = "sha256:d8ac80a7fa8dbcc131d5a0956f02605bca92bc70ecd411ec42fbada78b87378f"
AUDIT_REMEDIES = {
    "RM-AUD-001": "complete visible per-task contracts, including trapped right-hand patrol transitions",
    "RM-AUD-002": "explicit per-mechanism discriminators, including a fully trapped patrol assertion, plus independent invalid and boundary branches",
    "RM-AUD-003": "incremental descending activation with parent/rank disjoint-set unions",
    "RM-AUD-004": "atomic zero-or-two portal cardinality validation, separate ordinary/teleport transitions, and zero/one/three occurrence plus portal-state property tests",
    "RM-AUD-005": "artifact-only witnesses, noncontradictory compiling controls, exact config-declared API extraction, stale-file reconciliation, valid default CMake source mappings, exact diffs, and independent reconstruction",
    "RM-AUD-006": "pre-write link refusal plus stable per-root digest snapshots of legacy, reverify, sibling expansion, holdouts, exact artifacts, and semantic lineage",
    "RM-AUD-007": "forward/reverse shortest-path counts and exact path-count-product equality for mandatory cells",
}


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    mechanism: str
    output: str
    domain: str
    boundary: str

    @property
    def function(self) -> str:
        return self.task_id.replace("-", "_")


CASES = (
    Case(
        "scanline-span-ledger",
        "Scanline Span Ledger",
        "maximal horizontal run scan",
        "row/start/length triples",
        "region",
        "binary grid; empty land is engaged empty",
    ),
    Case(
        "column-transition-ledger",
        "Column Transition Ledger",
        "vertical transition scan",
        "column/row/from/to quadruples",
        "region",
        "binary grid; top edge has no transition",
    ),
    Case(
        "component-area-multiset",
        "Component Area Multiset",
        "four-neighbor queue labelling",
        "sorted component areas",
        "region",
        "diagonal cells are disconnected",
    ),
    Case(
        "component-perimeter-ledger",
        "Component Perimeter Ledger",
        "component flood with exposed-edge accounting",
        "seed/perimeter pairs",
        "region",
        "outside the grid counts as exposed",
    ),
    Case(
        "component-bounding-boxes",
        "Component Bounding Boxes",
        "component flood with coordinate extrema",
        "seed/min-row/min-column/max-row/max-column records",
        "region",
        "records follow row-major seeds",
    ),
    Case(
        "enclosed-void-census",
        "Enclosed Void Census",
        "boundary-background flood followed by hole flood",
        "sorted enclosed-hole areas",
        "region",
        "boundary-connected zero cells are not holes",
    ),
    Case(
        "boundary-void-frontier",
        "Boundary Void Frontier",
        "multi-source exterior-background traversal",
        "exterior zero-cell counts by distance",
        "region",
        "only boundary-connected zero cells participate",
    ),
    Case(
        "erosion-layer-histogram",
        "Erosion Layer Histogram",
        "simultaneous four-neighbor peeling",
        "land removals per round",
        "region",
        "a land cell peels when it touches exterior or zero",
    ),
    Case(
        "interior-distance-ridges",
        "Interior Distance Ridges",
        "land-only boundary distance transform",
        "ridge cell/distance pairs",
        "region",
        "ties are row-major",
    ),
    Case(
        "orthogonal-corner-census",
        "Orthogonal Corner Census",
        "local two-by-two convex/concave corner accounting",
        "convex/concave pair",
        "region",
        "diagonal patterns contribute two corners",
    ),
    Case(
        "translation-shape-classes",
        "Translation Shape Classes",
        "normalized coordinate-signature grouping",
        "sorted class multiplicities",
        "region",
        "rotation remains a different class",
    ),
    Case(
        "dihedral-shape-classes",
        "Dihedral Shape Classes",
        "eight-transform canonical coordinate signatures",
        "sorted class multiplicities",
        "region",
        "rotation and reflection merge",
    ),
    Case(
        "threshold-activation-curve",
        "Threshold Activation Curve",
        "descending activation with disjoint-set unions",
        "threshold/component-count pairs",
        "region",
        "digit cells activate from nine down to zero",
    ),
    Case(
        "label-contact-lengths",
        "Label Contact Lengths",
        "unlike-label shared-edge aggregation",
        "label-code/label-code/contact triples",
        "region",
        "dot is empty; pairs are code-ordered",
    ),
    Case(
        "region-euler-ledger",
        "Region Euler Ledger",
        "land-component and enclosed-background accounting",
        "components/holes/Euler triple",
        "region",
        "four-neighbor topology is authoritative",
    ),
    Case(
        "reachable-cell-bfs",
        "Reachable Cell BFS",
        "four-neighbor breadth-first traversal",
        "row-major reachable indices",
        "maze",
        "walls block traversal",
    ),
    Case(
        "shortest-route-length",
        "Shortest Route Length",
        "unweighted breadth-first distance",
        "one shortest distance",
        "maze",
        "unreachable is engaged empty",
    ),
    Case(
        "shortest-route-count",
        "Shortest Route Count",
        "BFS distance and modular path accumulation",
        "distance/count pair",
        "maze",
        "counts use modulus 1000003",
    ),
    Case(
        "lexicographic-route-codes",
        "Lexicographic Route Codes",
        "predecessor BFS with fixed direction priority",
        "direction-code sequence",
        "maze",
        "priority and codes are up=0,left=1,right=2,down=3",
    ),
    Case(
        "shortest-layer-widths",
        "Shortest Layer Widths",
        "goal-bounded BFS layer census",
        "layer counts through goal distance",
        "maze",
        "do not count deeper cells",
    ),
    Case(
        "mandatory-shortest-cells",
        "Mandatory Shortest Cells",
        "forward/reverse shortest-path product",
        "64-bit-overflow flag followed by row-major mandatory cells",
        "maze",
        "S and G are included",
    ),
    Case(
        "dead-end-pruning-rounds",
        "Dead-End Pruning Rounds",
        "simultaneous degree-one queue peeling",
        "removed counts per round",
        "maze",
        "S and G are never removed",
    ),
    Case(
        "minimum-wall-breaks",
        "Minimum Wall Breaks",
        "zero-one breadth-first search",
        "minimum entered walls",
        "maze",
        "S and G cost zero",
    ),
    Case(
        "wall-budget-distance",
        "Wall Budget Distance",
        "used-break product-state BFS",
        "shortest steps within parameter budget",
        "maze",
        "parameter is zero through eight",
    ),
    Case(
        "widest-clearance-route",
        "Widest Clearance Route",
        "wall-distance transform and max-min search",
        "maximum minimum clearance",
        "maze",
        "boundary outside is a wall",
    ),
    Case(
        "alternating-parity-route",
        "Alternating Parity Route",
        "orientation-parity expanded BFS",
        "shortest alternating-axis distance",
        "maze",
        "first move may use either axis",
    ),
    Case(
        "right-hand-patrol-cycle",
        "Right-Hand Patrol Cycle",
        "deterministic orientation automaton",
        "preperiod/cycle or exit/zero pair",
        "maze",
        "initial direction is east",
    ),
    Case(
        "paired-agent-swap-distance",
        "Paired Agent Swap Distance",
        "collision-free product-state BFS",
        "minimum synchronous swap steps",
        "maze",
        "no shared vertex or crossed edge",
    ),
    Case(
        "key-door-state-route",
        "Key Door State Route",
        "position and key-mask BFS",
        "shortest key-respecting distance",
        "maze",
        "only a/A and b/B are legal extras",
    ),
    Case(
        "portal-once-route",
        "Portal Once Route",
        "position and portal-use-mask BFS",
        "shortest single-use portal distance",
        "maze",
        "each digit appears exactly twice",
    ),
)

# These are visible behavioral contracts, not private oracle notes.  They are kept
# next to the case inventory so a task cannot acquire an implementation without
# also acquiring a complete prompt contract.
CONTRACTS = (
    "Scan each row left to right. For every maximal run of 1 cells append row, first column, and run length; records are row-major.",
    "Scan columns left to right and, within each column, rows 1..h-1. Whenever the bit differs from the cell above append column, row, old bit, new bit.",
    "Use four-neighbor connectivity on 1 cells, compute each component area, then return all areas in nondecreasing order; diagonal contact does not join components.",
    "Flood 1-components from row-major seeds. Each side adjacent to 0 or outside contributes one perimeter unit; append seed row-major index then perimeter in seed order.",
    "Flood 1-components from row-major seeds and append seed index, minimum row, minimum column, maximum row, maximum column in seed order.",
    "Flood boundary-connected 0 cells first, then flood every remaining four-neighbor 0-component as a hole; return hole areas sorted ascending.",
    "Start a multi-source BFS with every boundary 0 cell. Return the count of exterior-connected 0 cells at distances 0,1,...; enclosed 0 cells are excluded.",
    "Initially retain every 1 cell. In each simultaneous round remove cells having any side outside the retained set, append that round's removal count, and stop when none remain.",
    "Assign each 1 cell its four-neighbor distance from the exterior or a 0 cell, with boundary land at distance 1. Append row-major index and maximum distance for every cell attaining the maximum, in row-major order.",
    "At every grid vertex inspect the surrounding 2x2 occupancy: one occupied quadrant adds one convex corner, three add one concave corner, and two diagonal occupied quadrants add two convex corners. Return one global convex,concave pair.",
    "Flood each 1-component, translate its coordinates so both minima are zero, and use the sorted translated coordinates as its signature. Return class multiplicities sorted ascending; rotations/reflections remain distinct.",
    "Flood each 1-component and form all eight rotations/reflections. Normalize and sort each coordinate list, choose the lexicographically least signature, then return class multiplicities sorted ascending.",
    "Process thresholds 9 down through 0. Activate cells whose digit equals the threshold, union active four-neighbors in a disjoint-set structure, and append threshold then the current component count at every threshold.",
    "Dot is empty. For every horizontal or vertical shared edge between two different uppercase labels, count the unordered code-ordered pair. Append integer code of smaller label, integer code of larger label, contact length, ordered by the label pair.",
    "Using four-neighbor topology, count 1-components and enclosed 0-components. Return land component count, hole count, and their difference; boundary-connected 0 is exterior.",
    "BFS from S through every non-wall cell and return all reachable row-major indices in ascending order; reachability of G is irrelevant.",
    "BFS from S through non-walls and return the S-to-G edge distance. If G is unreachable return an engaged empty vector.",
    "During BFS accumulate counts only along shortest-distance edges modulo 1000003. Return shortest distance then route count, or engaged empty when unreachable.",
    "BFS with neighbor priority up,left,right,down encoded 0,1,2,3. The first discovery fixes each predecessor; reconstruct and return the resulting shortest direction-code sequence, or engaged empty when unreachable.",
    "BFS from S. If G is reachable, return counts of discovered non-wall cells at distances 0 through dist(G), including all cells at the goal layer but none deeper; otherwise return engaged empty.",
    "Run BFS from S and G while counting shortest paths in arbitrary-precision nonnegative integers; fixed-width wrapping is forbidden. A cell is mandatory exactly when it lies at the shortest total distance and the exact product ways(S,cell) times ways(cell,G) equals the total S-to-G shortest-path count. For a reachable goal return first 1 when the exact total exceeds 18446744073709551615, otherwise 0, followed by mandatory row-major indices in ascending order including S and G; unreachable returns engaged empty.",
    "Repeatedly and simultaneously remove non-S/non-G open cells having at most one retained four-neighbor. Append the number removed in each nonempty round and stop at the fixed point.",
    "Treat entering # as cost 1 and every other cell as cost 0, including S and G. Use 0-1 BFS and return the minimum total entered-wall cost.",
    "Parameter must be 0..8. BFS states are position and walls used; a move costs one step and entering # consumes one break. Return shortest steps using at most the parameter, or engaged empty.",
    "A cell's clearance is its minimum Manhattan distance to a # or to the outside boundary. Among non-wall S-to-G routes maximize the minimum visited clearance and return that value, or engaged empty.",
    "A valid route alternates horizontal and vertical moves; the first move may use either axis. BFS position plus prior-axis states and return shortest length, or engaged empty.",
    "Start at S facing east. At each state try right, straight, left, then back; stepping outside exits immediately. Otherwise take the first non-wall move. If all four in-bounds neighbors are walls, rotate 180 degrees in place and count one transition. Return preperiod,cycle length on a repeated position/direction state, or exit-step count,0 on exit.",
    "Two agents start at S and G and move synchronously; each may wait or move to a non-wall neighbor. Reject shared destinations and crossed-edge swaps. Return the minimum steps to exchange endpoints, or engaged empty.",
    "BFS states are position and a two-bit key mask. Entering a/b gains its key; A/B is passable only after that key. Return shortest S-to-G distance or engaged empty.",
    "Every digit that appears must occur exactly twice. Moving to an adjacent non-wall costs one step. From a digit cell, its paired cell is also a one-step destination once per digit for the route; record used digits in the BFS state. Return shortest distance or engaged empty.",
)

if len(CONTRACTS) != len(CASES):
    raise AssertionError("every regions/mazes case requires one visible contract")

# Model-facing prose for `.docs/introduction.md`, keyed by task id. One
# domain-motivating paragraph per case; it never states the contract and stays
# free of harness vocabulary, matching the official exercise documentation
# register.
INTRODUCTIONS: dict[str, str] = {
    "scanline-span-ledger": (
        "Run-length encoding is one of the oldest tricks in fax machines and "
        "bitmap fonts: instead of storing every pixel, record where each "
        "solid stretch begins and how long it lasts. Reading those spans "
        "back off a binary image is the first step of many compression "
        "pipelines. A left-to-right pass over each row is all it takes."
    ),
    "column-transition-ledger": (
        "Edge detection does not always need calculus. Watching one column "
        "of a binary image and noting every place the value flips from "
        "background to ink or back again already outlines the shapes "
        "crossing it. Collecting those flips column by column gives a "
        "compact sketch of the whole picture."
    ),
    "component-area-multiset": (
        "Blob counting shows up wherever a grid of cells clumps together: "
        "islands on a map, stars on a photographic plate, defects on a "
        "wafer. Two cells belong to the same blob only when they share an "
        "edge, and the size of each blob is often the first question asked. "
        "A census of blob sizes, sorted small to large, summarizes the "
        "whole scene."
    ),
    "component-perimeter-ledger": (
        "Fencing a pasture costs by the meter of boundary, not by the "
        "square meter of grass. For blobs on a grid, the perimeter counts "
        "every side that touches open ground or falls off the edge of the "
        "map. Reporting each blob's frontier separately keeps the "
        "bookkeeping honest."
    ),
    "component-bounding-boxes": (
        "Before a reading engine can recognize a word, it draws a rectangle "
        "around each connected clump of ink. The tightest axis-aligned "
        "rectangle around a blob is its bounding box, and a page full of "
        "blobs becomes a list of little frames. Finding each frame means "
        "tracking the extremes of every clump."
    ),
    "enclosed-void-census": (
        "A donut and a disk look alike until you notice the hole. On a "
        "binary grid, a pocket of background only counts as enclosed when "
        "no path of background cells leads off the edge of the image. "
        "Measuring the size of every such pocket tells solid regions from "
        "rings."
    ),
    "boundary-void-frontier": (
        "Flood fill starts at the edges and seeps inward. Watching how the "
        "tide of reachable background spreads from the border of an image, "
        "layer by layer, reveals how deeply the outside penetrates a "
        "shape. Cells the tide can never reach are truly enclosed."
    ),
    "erosion-layer-histogram": (
        "Peeling an onion one layer at a time shrinks it from the outside "
        "in. Applied to a blob of cells, each round strips everything "
        "touching the background until nothing is left. Counting the "
        "peelings per round sketches the blob's thickness profile."
    ),
    "interior-distance-ridges": (
        "The medial axis of a shape is its skeleton: the points furthest "
        "from any edge, like the ridge line of a mountain range. On a "
        "grid, each land cell's distance to the nearest background marks "
        "how deep inside the shape it sits. The cells attaining the "
        "greatest depth form the ridge."
    ),
    "orthogonal-corner-census": (
        "Tilers and quilters classify every vertex where four squares "
        "meet: some meetings are smooth, some jut outward, some bite "
        "inward. Counting the convex and concave corners of a pixel shape "
        "is a classic local fingerprint. Each grid vertex only needs its "
        "four neighboring cells inspected."
    ),
    "translation-shape-classes": (
        "Polyomino puzzles ask whether two clusters of squares are the "
        "same piece slid to a different spot. Sliding never changes a "
        "shape, so clusters that match after a shift belong to one class. "
        "Counting how many copies of each piece appear on the board is the "
        "natural next question."
    ),
    "dihedral-shape-classes": (
        "Physical puzzle pieces can be flipped and rotated, not just slid. "
        "Two clusters of cells are the same free piece when any rotation "
        "or reflection lines them up. Grouping a board full of clusters by "
        "that looser notion of sameness merges what rigid sliding keeps "
        "apart."
    ),
    "threshold-activation-curve": (
        "Terrain floods from the lowest ground upward; image thresholding "
        "works the other way, lighting up the brightest cells first and "
        "letting darker ones join as the bar drops. Watching connected "
        "components merge as the threshold descends draws the image's "
        "watershed curve. Each step down can unite regions that were "
        "separate above."
    ),
    "label-contact-lengths": (
        "On a painted map, borders matter: how long one country touches "
        "another decides trade routes and treaty lines. Given a grid of "
        "labeled regions, measuring every shared edge between different "
        "labels produces the contact ledger. Only true edge-sharing "
        "counts; corner touches do not."
    ),
    "region-euler-ledger": (
        "Euler's famous formula relates the pieces, holes, and connections "
        "of a shape. For a binary grid the same idea is within reach: "
        "count the separate land masses, count the pockets of background "
        "they trap, and the difference is a small invariant with a big "
        "name. Mapmakers and image libraries both rely on it."
    ),
    "reachable-cell-bfs": (
        "Before asking how far anywhere is, ask where you can get to at "
        "all. Exploring a maze outward from the entrance, ring by ring, "
        "marks every reachable floor tile. The list of reachable cells is "
        "the foundation every other maze question builds on."
    ),
    "shortest-route-length": (
        "Every maze runner wants to know the length of the quickest path "
        "from entrance to exit. Rippling outward one step at a time "
        "guarantees that the first arrival at the goal used the fewest "
        "steps possible. Sometimes the answer is that no route exists at "
        "all."
    ),
    "shortest-route-count": (
        "Knowing the shortest distance is half the story; several equally "
        "short routes may wind through the same maze. Counting them while "
        "exploring keeps the ledger exact without ever walking a path "
        "twice. Large mazes make the count grow fast, so a fixed modulus "
        "keeps it manageable."
    ),
    "lexicographic-route-codes": (
        "A maze solver's notebook records directions, not just distances: "
        "up, left, right, down as a sequence of codes. When several "
        "shortest routes exist, a fixed exploration order picks one of "
        "them deterministically. The resulting code string is a replayable "
        "recipe from start to goal."
    ),
    "shortest-layer-widths": (
        "Exploring a maze in waves raises a natural question: how wide is "
        "each wave? Counting the newly reached cells at every distance, "
        "up to the one where the goal first appears, profiles the maze "
        "from the entrance's point of view. Anything beyond the goal's "
        "wave stays uncounted."
    ),
    "mandatory-shortest-cells": (
        "Some corridor cells are bottlenecks: every quickest route from "
        "entrance to exit is forced through them. Finding those "
        "unavoidable cells means counting shortest paths exactly, even "
        "when the count overflows machine integers. The cells where every "
        "path converges are the maze's weak points."
    ),
    "dead-end-pruning-rounds": (
        "Hedge mazes are full of corridors that go nowhere. Trimming every "
        "dead end, then trimming the new dead ends that the trimming "
        "exposes, eventually leaves only the meaningful corridors. "
        "Counting how many cells fall in each round shows how much of the "
        "maze was decoration."
    ),
    "minimum-wall-breaks": (
        "When no route exists, a determined maze runner starts pricing "
        "demolition. If breaking through a wall costs one unit of effort, "
        "the cheapest way from entrance to exit is a classic search "
        "problem. Sometimes the direct corridor is already free."
    ),
    "wall-budget-distance": (
        "A demolitions expert with a limited number of charges must plan "
        "carefully: each wall broken spends one, and the walking still "
        "takes time. Searching position and remaining budget together "
        "finds the fastest route that stays within the allowance. An "
        "empty allowance means walking around like everyone else."
    ),
    "widest-clearance-route": (
        "Moving a piano through a building is not about the shortest "
        "corridor but the widest one. Every room has a clearance, meaning "
        "how far you can stay from the walls, and a route is only as good "
        "as its narrowest point. Maximizing that bottleneck keeps the "
        "piano unscratched."
    ),
    "alternating-parity-route": (
        "Some dance floors and some board games demand that every step "
        "change direction: a horizontal move must be followed by a "
        "vertical one. Finding the shortest path under that zigzag rule "
        "means remembering which way you last moved. What looks like a "
        "small twist doubles the state of the search."
    ),
    "right-hand-patrol-cycle": (
        "A night watchman pacing a building keeps one hand on the right "
        "wall and turns whenever the wall lets him. That simple rule "
        "either walks him out the door or settles into a loop he will "
        "pace forever. Telling the two outcomes apart, and measuring the "
        "loop, is a matter of careful simulation."
    ),
    "paired-agent-swap-distance": (
        "Two robots in a narrow warehouse aisle need to trade places "
        "without ever occupying the same square or squeezing past each "
        "other mid-step. Coordinating their moves is a puzzle in joint "
        "planning: every step chooses a move for both. The fastest swap "
        "respects the choreography of collision avoidance."
    ),
    "key-door-state-route": (
        "Adventure games taught a generation that a locked door is just a "
        "key you have not found yet. In a maze with lettered doors and "
        "matching keys, where you can go depends on what you carry. "
        "Searching with the current keyring as part of the position "
        "solves it cleanly."
    ),
    "portal-once-route": (
        "A pair of linked portals makes any two distant tiles neighbors, "
        "but only once per journey. Knowing when to spend that single "
        "teleport is a planning problem: the state of the search must "
        "remember which portals are already used. The shortest route may "
        "even ignore them entirely."
    ),
}

if set(INTRODUCTIONS) != {case.task_id for case in CASES}:
    raise AssertionError("every regions/mazes case requires one introduction")

REGION_VISIBLE = ("11001", "10011", "00100", "01110")
REGION_HIDDEN = ("111000", "101110", "111010", "000010", "011110")
MAZE_VISIBLE = ("S..#.", ".#...", "...#G")
MAZE_HIDDEN = ("S...#.", ".##...", "...#..", ".#...G")

PROPERTY_INPUTS: tuple[tuple[tuple[str, ...], int], ...] = (
    (("10101", "11100"), 0),
    (("010", "101", "011"), 0),
    (("101", "010", "101"), 0),
    (("11111", "10001", "10101", "10001", "11111"), 0),
    (("11001", "10001", "00111", "00101"), 0),
    (("11111", "10001", "10101", "10001", "11111"), 0),
    (("00000", "01110", "01010", "01110", "00000"), 0),
    (("11111", "11111", "11111", "11111", "11111"), 0),
    (("11111", "11111", "11111", "11111", "11111"), 0),
    (("110", "100", "111"), 0),
    (("110011", "100010", "000000", "110001", "100011"), 0),
    (("110001", "100011", "000000", "110011", "100010"), 0),
    (("99999", "95459", "54345", "95459", "99999"), 0),
    (("AAB.", "ACB.", "DCCB"), 0),
    (("11111", "10001", "10101", "10001", "11111"), 0),
    (("S#G", "..."), 0),
    (("S#G", "###", "..."), 0),
    (("S..", "...", "..G"), 0),
    (("S..", "...", "..G"), 0),
    (("S...", "....", "...G"), 0),
    (("S...G", "##.##", "....."), 0),
    (("S...G", "##.##", "##.##", "##.##"), 0),
    (("S#G",), 0),
    (("S##G", "...."), 2),
    ((".......", ".......", ".......", ".S...G.", ".......", ".......", "......."), 0),
    (("S.", ".G"), 0),
    (("#####", "#S..#", "#.#G#", "#...#", "#####"), 0),
    (("S.G", "..."), 0),
    (("S.A.G", "..a.."), 0),
    (("S1...G", "###.##", "1....#"), 0),
)

if len(PROPERTY_INPUTS) != len(CASES):
    raise AssertionError("every regions/mazes case requires one mechanism property input")


def _overflow_diamond_grid() -> tuple[str, ...]:
    """Return a 29x32 serial grid of 100 independent two-way diamonds."""
    cells = [["#"] * 32 for _ in range(29)]
    for band in range(10):
        top = 3 * band
        left_to_right = band % 2 == 0
        for diamond in range(10):
            if left_to_right:
                start_column = 3 * diamond
                columns = (start_column, start_column + 1)
                connector_column = start_column + 2
            else:
                start_column = 31 - 3 * diamond
                columns = (start_column - 1, start_column)
                connector_column = start_column - 2
            for row in (top, top + 1):
                for column in columns:
                    cells[row][column] = "."
            if diamond < 9:
                connector_row = top + (diamond % 2 == 0)
                cells[connector_row][connector_column] = "."
        tail_columns = (29, 30, 31) if left_to_right else (2, 1, 0)
        for column in tail_columns:
            cells[top][column] = "."
        if band < 9:
            connector = 31 if left_to_right else 0
            for row in (top + 1, top + 2, top + 3):
                cells[row][connector] = "."
    cells[0][0] = "S"
    cells[27][3] = "G"
    return tuple("".join(row) for row in cells)


def _exact_shortest_path_count(grid: tuple[str, ...]) -> int:
    start, goal = _maze_points(grid)
    distance = [[-1] * len(grid[0]) for _ in grid]
    ways = [[0] * len(grid[0]) for _ in grid]
    queue = collections.deque([start])
    distance[start[0]][start[1]] = 0
    ways[start[0]][start[1]] = 1
    while queue:
        r, c = queue.popleft()
        for nr, nc in _neighbors(r, c, len(grid), len(grid[0])):
            if grid[nr][nc] == "#":
                continue
            if distance[nr][nc] < 0:
                distance[nr][nc] = distance[r][c] + 1
                queue.append((nr, nc))
            if distance[nr][nc] == distance[r][c] + 1:
                ways[nr][nc] += ways[r][c]
    return ways[goal[0]][goal[1]]


CMAKE = r"""cmake_minimum_required(VERSION 3.16)
project(regions_mazes_expansion LANGUAGES CXX)
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
"""


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


def _validate_prewrite_owned_paths(out: Path) -> None:
    roots = [out / case.task_id for case in CASES]
    roots.extend(
        out / ".state/adversarial-clone-controls" / name
        for name in (
            "domain-identifier-renamed",
            "constants-policy-only",
            "opposite-end-selection",
        )
    )
    for root in roots:
        paths = [root]
        if root.is_dir() and not root.is_symlink():
            paths.extend(root.rglob("*"))
        for path in paths:
            if path.is_symlink():
                _fail("unsafe_path", f"pre-write symlink in owned root: {path}")
            if path.is_file() and path.stat().st_nlink != 1:
                _fail("unsafe_path", f"pre-write hardlink in owned root: {path}")


def _neighbors(r: int, c: int, h: int, w: int) -> Iterable[tuple[int, int]]:
    for dr, dc in ((-1, 0), (0, -1), (0, 1), (1, 0)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < h and 0 <= nc < w:
            yield nr, nc


def _components(grid: tuple[str, ...], value: str = "1") -> list[list[tuple[int, int]]]:
    h, w = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    result = []
    for r in range(h):
        for c in range(w):
            if grid[r][c] != value or (r, c) in seen:
                continue
            queue = collections.deque([(r, c)])
            seen.add((r, c))
            cells = []
            while queue:
                cell = queue.popleft()
                cells.append(cell)
                for nxt in _neighbors(*cell, h, w):
                    if grid[nxt[0]][nxt[1]] == value and nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
            result.append(cells)
    return result


def _maze_points(grid: tuple[str, ...]) -> tuple[tuple[int, int], tuple[int, int]]:
    start = goal = (-1, -1)
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            if value == "S":
                start = (r, c)
            elif value == "G":
                goal = (r, c)
    return start, goal


def _distances(grid: tuple[str, ...], source: tuple[int, int]) -> list[list[int]]:
    h, w = len(grid), len(grid[0])
    dist = [[-1] * w for _ in range(h)]
    queue = collections.deque([source])
    dist[source[0]][source[1]] = 0
    while queue:
        r, c = queue.popleft()
        for nr, nc in _neighbors(r, c, h, w):
            if grid[nr][nc] != "#" and dist[nr][nc] < 0:
                dist[nr][nc] = dist[r][c] + 1
                queue.append((nr, nc))
    return dist


def _region_oracle(index: int, grid: tuple[str, ...]) -> list[int]:
    h, w = len(grid), len(grid[0])
    comps = _components(grid)
    if index == 0:
        out = []
        for r, row in enumerate(grid):
            c = 0
            while c < w:
                if row[c] != "1":
                    c += 1
                    continue
                end = c
                while end < w and row[end] == "1":
                    end += 1
                out += [r, c, end - c]
                c = end
        return out
    if index == 1:
        return [
            value
            for c in range(w)
            for r in range(1, h)
            if grid[r][c] != grid[r - 1][c]
            for value in (c, r, int(grid[r - 1][c]), int(grid[r][c]))
        ]
    if index == 2:
        return sorted(map(len, comps))
    if index == 3:
        out = []
        for comp in comps:
            cells = set(comp)
            perimeter = sum(
                4 - sum(nxt in cells for nxt in _neighbors(r, c, h, w)) for r, c in comp
            )
            seed = min(r * w + c for r, c in comp)
            out += [seed, perimeter]
        return out
    if index == 4:
        return [
            value
            for comp in comps
            for value in (
                min(r * w + c for r, c in comp),
                min(r for r, _ in comp),
                min(c for _, c in comp),
                max(r for r, _ in comp),
                max(c for _, c in comp),
            )
        ]
    if index in (5, 6, 14):
        boundary = collections.deque()
        seen: set[tuple[int, int]] = set()
        for r in range(h):
            for c in range(w):
                if (
                    (r in (0, h - 1) or c in (0, w - 1))
                    and grid[r][c] == "0"
                    and (r, c) not in seen
                ):
                    seen.add((r, c))
                    boundary.append((r, c))
        layers: list[int] = []
        while boundary:
            layers.append(len(boundary))
            for _ in range(len(boundary)):
                cell = boundary.popleft()
                for nxt in _neighbors(*cell, h, w):
                    if grid[nxt[0]][nxt[1]] == "0" and nxt not in seen:
                        seen.add(nxt)
                        boundary.append(nxt)
        holes = []
        for r in range(h):
            for c in range(w):
                if grid[r][c] != "0" or (r, c) in seen:
                    continue
                queue = collections.deque([(r, c)])
                seen.add((r, c))
                area = 0
                while queue:
                    cell = queue.popleft()
                    area += 1
                    for nxt in _neighbors(*cell, h, w):
                        if grid[nxt[0]][nxt[1]] == "0" and nxt not in seen:
                            seen.add(nxt)
                            queue.append(nxt)
                holes.append(area)
        if index == 5:
            return sorted(holes)
        if index == 6:
            return layers
        return [len(comps), len(holes), len(comps) - len(holes)]
    if index == 7:
        alive = {(r, c) for r in range(h) for c in range(w) if grid[r][c] == "1"}
        out = []
        while alive:
            remove = {
                cell
                for cell in alive
                if any(
                    nxt not in alive
                    for nxt in (
                        (cell[0] - 1, cell[1]),
                        (cell[0] + 1, cell[1]),
                        (cell[0], cell[1] - 1),
                        (cell[0], cell[1] + 1),
                    )
                )
            }
            out.append(len(remove))
            alive -= remove
        return out
    if index == 8:
        land = {(r, c) for r in range(h) for c in range(w) if grid[r][c] == "1"}
        distance = {
            cell: 1
            for cell in land
            if any(
                nxt not in land
                for nxt in (
                    (cell[0] - 1, cell[1]),
                    (cell[0] + 1, cell[1]),
                    (cell[0], cell[1] - 1),
                    (cell[0], cell[1] + 1),
                )
            )
        }
        queue = collections.deque(distance)
        while queue:
            cell = queue.popleft()
            for nxt in _neighbors(*cell, h, w):
                if nxt in land and nxt not in distance:
                    distance[nxt] = distance[cell] + 1
                    queue.append(nxt)
        best = max(distance.values(), default=0)
        return [
            value
            for cell in sorted(distance)
            if distance[cell] == best
            for value in (cell[0] * w + cell[1], best)
        ]
    if index == 9:
        convex = concave = 0
        for r in range(h + 1):
            for c in range(w + 1):
                count = sum(
                    0 <= rr < h and 0 <= cc < w and grid[rr][cc] == "1"
                    for rr, cc in ((r - 1, c - 1), (r - 1, c), (r, c - 1), (r, c))
                )
                convex += count == 1
                concave += count == 3
                if count == 2 and (
                    (0 <= r - 1 < h and 0 <= c - 1 < w and grid[r - 1][c - 1] == "1")
                    == (0 <= r < h and 0 <= c < w and grid[r][c] == "1")
                ):
                    convex += 2
        return [convex, concave]

    def signature(comp: list[tuple[int, int]], dihedral: bool) -> tuple[tuple[int, int], ...]:
        variants = []
        transforms = range(8) if dihedral else range(1)
        for kind in transforms:
            points = []
            for r, c in comp:
                a, b = ((r, c), (r, -c), (-r, c), (-r, -c), (c, r), (c, -r), (-c, r), (-c, -r))[
                    kind
                ]
                points.append((a, b))
            mr, mc = min(r for r, _ in points), min(c for _, c in points)
            variants.append(tuple(sorted((r - mr, c - mc) for r, c in points)))
        return min(variants)

    if index in (10, 11):
        counts = collections.Counter(signature(comp, index == 11) for comp in comps)
        return sorted(counts.values())
    if index == 12:
        active: set[tuple[int, int]] = set()
        out = []
        for threshold in range(9, -1, -1):
            active |= {(r, c) for r in range(h) for c in range(w) if int(grid[r][c]) == threshold}
            count = 0
            seen: set[tuple[int, int]] = set()
            for cell in sorted(active):
                if cell in seen:
                    continue
                count += 1
                queue = collections.deque([cell])
                seen.add(cell)
                while queue:
                    for nxt in _neighbors(*queue.popleft(), h, w):
                        if nxt in active and nxt not in seen:
                            seen.add(nxt)
                            queue.append(nxt)
            out += [threshold, count]
        return out
    contacts: collections.Counter[tuple[str, str]] = collections.Counter()
    for r in range(h):
        for c in range(w):
            if grid[r][c] == ".":
                continue
            for nr, nc in ((r + 1, c), (r, c + 1)):
                if nr < h and nc < w and grid[nr][nc] not in (".", grid[r][c]):
                    contacts[tuple(sorted((grid[r][c], grid[nr][nc])))] += 1
    return [
        value
        for pair, count in sorted(contacts.items())
        for value in (ord(pair[0]), ord(pair[1]), count)
    ]


def _maze_oracle(index: int, grid: tuple[str, ...], parameter: int) -> list[int]:
    h, w = len(grid), len(grid[0])
    start, goal = _maze_points(grid)
    dist = _distances(grid, start)
    if index == 15:
        return [r * w + c for r in range(h) for c in range(w) if dist[r][c] >= 0]
    if index == 16:
        return [] if dist[goal[0]][goal[1]] < 0 else [dist[goal[0]][goal[1]]]
    if index == 17:
        ways = [[0] * w for _ in range(h)]
        ways[start[0]][start[1]] = 1
        for d in range(max(max(row) for row in dist) + 1):
            for r in range(h):
                for c in range(w):
                    if dist[r][c] == d:
                        for nr, nc in _neighbors(r, c, h, w):
                            if dist[nr][nc] == d + 1:
                                ways[nr][nc] = (ways[nr][nc] + ways[r][c]) % MODULUS
        return (
            [] if dist[goal[0]][goal[1]] < 0 else [dist[goal[0]][goal[1]], ways[goal[0]][goal[1]]]
        )
    if index == 18:
        queue = collections.deque([start])
        parent = {start: None}
        move = {}
        dirs = ((-1, 0, 0), (0, -1, 1), (0, 1, 2), (1, 0, 3))
        while queue:
            cell = queue.popleft()
            for dr, dc, code in dirs:
                nxt = (cell[0] + dr, cell[1] + dc)
                if (
                    0 <= nxt[0] < h
                    and 0 <= nxt[1] < w
                    and grid[nxt[0]][nxt[1]] != "#"
                    and nxt not in parent
                ):
                    parent[nxt] = cell
                    move[nxt] = code
                    queue.append(nxt)
        if goal not in parent:
            return []
        out = []
        while goal != start:
            out.append(move[goal])
            goal = parent[goal]
        return out[::-1]
    if index == 19:
        target = dist[goal[0]][goal[1]]
        return (
            []
            if target < 0
            else [sum(value == d for row in dist for value in row) for d in range(target + 1)]
        )
    if index == 20:

        def counted_bfs(source: tuple[int, int]) -> tuple[list[list[int]], list[list[int]]]:
            distance = [[-1] * w for _ in range(h)]
            ways = [[0] * w for _ in range(h)]
            queue = collections.deque([source])
            distance[source[0]][source[1]] = 0
            ways[source[0]][source[1]] = 1
            while queue:
                r, c = queue.popleft()
                for nr, nc in _neighbors(r, c, h, w):
                    if grid[nr][nc] == "#":
                        continue
                    if distance[nr][nc] < 0:
                        distance[nr][nc] = distance[r][c] + 1
                        queue.append((nr, nc))
                    if distance[nr][nc] == distance[r][c] + 1:
                        ways[nr][nc] += ways[r][c]
            return distance, ways

        forward, forward_ways = counted_bfs(start)
        reverse, reverse_ways = counted_bfs(goal)
        target = forward[goal[0]][goal[1]]
        if target < 0:
            return []
        total_ways = forward_ways[goal[0]][goal[1]]
        mandatory = [
            r * w + c
            for r in range(h)
            for c in range(w)
            if forward[r][c] >= 0
            and reverse[r][c] >= 0
            and forward[r][c] + reverse[r][c] == target
            and forward_ways[r][c] * reverse_ways[r][c] == total_ways
        ]
        return [int(total_ways > (1 << 64) - 1), *mandatory]
    if index == 21:
        alive = {(r, c) for r in range(h) for c in range(w) if grid[r][c] != "#"}
        out = []
        while True:
            remove = {
                cell
                for cell in alive
                if cell not in (start, goal)
                and sum(nxt in alive for nxt in _neighbors(*cell, h, w)) <= 1
            }
            if not remove:
                break
            out.append(len(remove))
            alive -= remove
        return out
    if index in (22, 23):
        best = [[10**9] * w for _ in range(h)]
        if index == 22:
            queue = collections.deque([start])
            best[start[0]][start[1]] = 0
            while queue:
                cell = queue.popleft()
                for nxt in _neighbors(*cell, h, w):
                    cost = best[cell[0]][cell[1]] + (grid[nxt[0]][nxt[1]] == "#")
                    if cost < best[nxt[0]][nxt[1]]:
                        best[nxt[0]][nxt[1]] = cost
                        (queue.append if grid[nxt[0]][nxt[1]] == "#" else queue.appendleft)(nxt)
            return [best[goal[0]][goal[1]]]
        queue = collections.deque([(start[0], start[1], 0, 0)])
        seen = {(start[0], start[1], 0)}
        while queue:
            r, c, used, steps = queue.popleft()
            if (r, c) == goal:
                return [steps]
            for nr, nc in _neighbors(r, c, h, w):
                nxt_used = used + (grid[nr][nc] == "#")
                state = (nr, nc, nxt_used)
                if nxt_used <= parameter and state not in seen:
                    seen.add(state)
                    queue.append((nr, nc, nxt_used, steps + 1))
        return []
    if index == 24:
        walls = [(r, c) for r in range(h) for c in range(w) if grid[r][c] == "#"]
        clearance = [
            [
                min([abs(r - wr) + abs(c - wc) for wr, wc in walls] + [r + 1, c + 1, h - r, w - c])
                for c in range(w)
            ]
            for r in range(h)
        ]
        score = [[-1] * w for _ in range(h)]
        score[start[0]][start[1]] = clearance[start[0]][start[1]]
        changed = True
        while changed:
            changed = False
            for r in range(h):
                for c in range(w):
                    if grid[r][c] == "#" or score[r][c] < 0:
                        continue
                    for nr, nc in _neighbors(r, c, h, w):
                        value = min(score[r][c], clearance[nr][nc])
                        if grid[nr][nc] != "#" and value > score[nr][nc]:
                            score[nr][nc] = value
                            changed = True
        return [] if score[goal[0]][goal[1]] < 0 else [score[goal[0]][goal[1]]]
    if index == 25:
        queue = collections.deque([(start[0], start[1], -1, 0)])
        seen = {(start[0], start[1], -1)}
        while queue:
            r, c, axis, steps = queue.popleft()
            if (r, c) == goal:
                return [steps]
            for nr, nc in _neighbors(r, c, h, w):
                next_axis = int(nr != r)
                state = (nr, nc, next_axis)
                if grid[nr][nc] != "#" and next_axis != axis and state not in seen:
                    seen.add(state)
                    queue.append((nr, nc, next_axis, steps + 1))
        return []
    if index == 26:
        state = (start[0], start[1], 1)
        seen = {}
        steps = 0
        dirs = ((-1, 0), (0, 1), (1, 0), (0, -1))
        while state not in seen:
            seen[state] = steps
            r, c, direction = state
            moved = False
            for turn in (1, 0, -1, 2):
                nd = (direction + turn) % 4
                nr, nc = r + dirs[nd][0], c + dirs[nd][1]
                if not (0 <= nr < h and 0 <= nc < w):
                    return [steps + 1, 0]
                if grid[nr][nc] != "#":
                    state = (nr, nc, nd)
                    moved = True
                    break
            if not moved:
                state = (r, c, (direction + 2) % 4)
            steps += 1
        return [seen[state], steps - seen[state]]
    if index == 27:
        queue = collections.deque([(start, goal, 0)])
        seen = {(start, goal)}
        while queue:
            a, b, steps = queue.popleft()
            if a == goal and b == start:
                return [steps]
            moves_a = [a] + [n for n in _neighbors(*a, h, w) if grid[n[0]][n[1]] != "#"]
            moves_b = [b] + [n for n in _neighbors(*b, h, w) if grid[n[0]][n[1]] != "#"]
            for na in moves_a:
                for nb in moves_b:
                    state = (na, nb)
                    if na != nb and not (na == b and nb == a) and state not in seen:
                        seen.add(state)
                        queue.append((na, nb, steps + 1))
        return []
    if index == 28:
        queue = collections.deque([(start[0], start[1], 0, 0)])
        seen = {(start[0], start[1], 0)}
        while queue:
            r, c, keys, steps = queue.popleft()
            if (r, c) == goal:
                return [steps]
            for nr, nc in _neighbors(r, c, h, w):
                value = grid[nr][nc]
                next_keys = keys
                if value == "#" or (value in "AB" and not (keys & (1 << (ord(value) - ord("A"))))):
                    continue
                if value in "ab":
                    next_keys |= 1 << (ord(value) - ord("a"))
                state = (nr, nc, next_keys)
                if state not in seen:
                    seen.add(state)
                    queue.append((nr, nc, next_keys, steps + 1))
        return []
    portals: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    for r in range(h):
        for c in range(w):
            if grid[r][c].isdigit():
                portals[grid[r][c]].append((r, c))
    queue = collections.deque([(start[0], start[1], 0, 0)])
    seen = {(start[0], start[1], 0)}
    while queue:
        r, c, mask, steps = queue.popleft()
        if (r, c) == goal:
            return [steps]
        targets = [(nr, nc, False) for nr, nc in _neighbors(r, c, h, w)]
        value = grid[r][c]
        if value.isdigit() and not (mask & (1 << int(value))):
            targets += [(nr, nc, True) for nr, nc in portals[value] if (nr, nc) != (r, c)]
        for nr, nc, teleported in targets:
            if grid[nr][nc] == "#":
                continue
            next_mask = mask | ((1 << int(value)) if teleported else 0)
            state = (nr, nc, next_mask)
            if state not in seen:
                seen.add(state)
                queue.append((nr, nc, next_mask, steps + 1))
    return []


def _case_input(case: Case, hidden: bool) -> tuple[tuple[str, ...], int]:
    index = CASES.index(case)
    if index == 12:
        return (("932", "151", "870") if not hidden else ("9092", "1821", "3764")), 2
    if index == 13:
        return (("AAB", "ACB", "CCB") if not hidden else ("ABBC", "ADDC", "A..C")), 2
    if index == 28:
        return (("SAG", ".#.", "a..") if not hidden else ("SB.G", ".#.#", "b..a", "##A.")), 2
    if index == 29:
        return (("S1##", "..#G", "##1.") if not hidden else ("S.2#G", "##.#.", "2....")), 2
    base = (
        (REGION_HIDDEN if hidden else REGION_VISIBLE)
        if case.domain == "region"
        else (MAZE_HIDDEN if hidden else MAZE_VISIBLE)
    )
    # Give every retained root its own literal topology.  Padding is deliberately
    # inert for reachability but changes coordinates, edge behavior, and the
    # expected oracle, preventing a large shared-fixture monoculture.
    padding = (index % 15) + 1
    fill = "0" if case.domain == "region" else "#"
    grid = tuple(row + fill * padding for row in base)
    return grid, (2 if hidden else 1)


def _oracle(case: Case, grid: tuple[str, ...], parameter: int) -> list[int]:
    index = CASES.index(case)
    return _region_oracle(index, grid) if index < 15 else _maze_oracle(index, grid, parameter)


def _cpp_strings(values: tuple[str, ...]) -> str:
    return "{" + ",".join(json.dumps(value) for value in values) + "}"


def _cpp_ints(values: Iterable[int]) -> str:
    return "{" + ",".join(str(value) for value in values) + "}"


def _header(case: Case) -> str:
    guard = case.task_id.replace("-", "_").upper() + "_H"
    return f"""#ifndef {guard}
#define {guard}
#include <optional>
#include <string>
#include <vector>
namespace regions_mazes {{
struct GridRequest {{ std::vector<std::string> grid; int parameter; }};
std::optional<std::vector<int>> {case.function}(const GridRequest& request);
}}
#endif
"""


def _cpp_bodies() -> tuple[str, ...]:
    return (
        # 0: scanline spans
        r"""for(int r=0;r<h;++r){int c=0;while(c<w){if(g[r][c]!='1'){++c;continue;}int e=c;while(e<w&&g[r][e]=='1')++e;out.insert(out.end(),{r,c,e-c});c=e;}}""",
        # 1: vertical transitions
        r"""for(int c=0;c<w;++c)for(int r=1;r<h;++r)if(g[r][c]!=g[r-1][c])out.insert(out.end(),{c,r,g[r-1][c]-'0',g[r][c]-'0'});""",
        # 2: component areas
        r"""std::vector<std::vector<int>> seen(h,std::vector<int>(w));for(int sr=0;sr<h;++sr)for(int sc=0;sc<w;++sc)if(g[sr][sc]=='1'&&!seen[sr][sc]){std::queue<std::pair<int,int>> q;q.push({sr,sc});seen[sr][sc]=1;int area=0;while(!q.empty()){auto [r,c]=q.front();q.pop();++area;for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]=='1'&&!seen[nr][nc]){seen[nr][nc]=1;q.push({nr,nc});}}}out.push_back(area);}std::sort(out.begin(),out.end());""",
        # 3: perimeters
        r"""std::vector<std::vector<int>> seen(h,std::vector<int>(w));for(int sr=0;sr<h;++sr)for(int sc=0;sc<w;++sc)if(g[sr][sc]=='1'&&!seen[sr][sc]){std::queue<std::pair<int,int>> q;q.push({sr,sc});seen[sr][sc]=1;int perimeter=0;while(!q.empty()){auto [r,c]=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(!inside(nr,nc)||g[nr][nc]!='1')++perimeter;else if(!seen[nr][nc]){seen[nr][nc]=1;q.push({nr,nc});}}}out.insert(out.end(),{sr*w+sc,perimeter});}""",
        # 4: component bounding boxes
        r"""std::vector<std::vector<int>> seen(h,std::vector<int>(w));for(int sr=0;sr<h;++sr)for(int sc=0;sc<w;++sc)if(g[sr][sc]=='1'&&!seen[sr][sc]){std::queue<std::pair<int,int>> q;q.push({sr,sc});seen[sr][sc]=1;int lo_r=sr,hi_r=sr,lo_c=sc,hi_c=sc;while(!q.empty()){auto [r,c]=q.front();q.pop();lo_r=std::min(lo_r,r);hi_r=std::max(hi_r,r);lo_c=std::min(lo_c,c);hi_c=std::max(hi_c,c);for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]=='1'&&!seen[nr][nc]){seen[nr][nc]=1;q.push({nr,nc});}}}out.insert(out.end(),{sr*w+sc,lo_r,lo_c,hi_r,hi_c});}""",
        # 5: enclosed voids
        r"""std::vector<std::vector<int>> seen(h,std::vector<int>(w));std::queue<std::pair<int,int>> q;for(int r=0;r<h;++r)for(int c=0;c<w;++c)if((r==0||c==0||r==h-1||c==w-1)&&g[r][c]=='0'&&!seen[r][c]){seen[r][c]=1;q.push({r,c});}auto flood=[&](int sr,int sc){int area=0;seen[sr][sc]=1;q.push({sr,sc});while(!q.empty()){auto [r,c]=q.front();q.pop();++area;for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]=='0'&&!seen[nr][nc]){seen[nr][nc]=1;q.push({nr,nc});}}}return area;};while(!q.empty()){auto [r,c]=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]=='0'&&!seen[nr][nc]){seen[nr][nc]=1;q.push({nr,nc});}}}for(int r=0;r<h;++r)for(int c=0;c<w;++c)if(g[r][c]=='0'&&!seen[r][c])out.push_back(flood(r,c));std::sort(out.begin(),out.end());""",
        # 6: exterior distance layers
        r"""std::vector<std::vector<int>> distance(h,std::vector<int>(w,-1));std::queue<std::pair<int,int>> q;for(int r=0;r<h;++r)for(int c=0;c<w;++c)if((r==0||c==0||r==h-1||c==w-1)&&g[r][c]=='0'&&distance[r][c]<0){distance[r][c]=0;q.push({r,c});}while(!q.empty()){auto [r,c]=q.front();q.pop();if(static_cast<int>(out.size())<=distance[r][c])out.resize(static_cast<std::size_t>(distance[r][c]+1));++out[static_cast<std::size_t>(distance[r][c])];for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]=='0'&&distance[nr][nc]<0){distance[nr][nc]=distance[r][c]+1;q.push({nr,nc});}}}""",
        # 7: simultaneous erosion
        r"""std::set<std::pair<int,int>> alive;for(int r=0;r<h;++r)for(int c=0;c<w;++c)if(g[r][c]=='1')alive.insert({r,c});while(!alive.empty()){std::vector<std::pair<int,int>> remove;for(auto cell:alive)for(auto [dr,dc]:dirs)if(alive.count({cell.first+dr,cell.second+dc})==0U){remove.push_back(cell);break;}out.push_back(static_cast<int>(remove.size()));for(auto cell:remove)alive.erase(cell);}""",
        # 8: distance ridges
        r"""std::vector<std::vector<int>> distance(h,std::vector<int>(w,-1));std::queue<std::pair<int,int>> q;for(int r=0;r<h;++r)for(int c=0;c<w;++c)if(g[r][c]=='1'){bool edge=false;for(auto [dr,dc]:dirs)if(!inside(r+dr,c+dc)||g[r+dr][c+dc]!='1')edge=true;if(edge){distance[r][c]=1;q.push({r,c});}}while(!q.empty()){auto [r,c]=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]=='1'&&distance[nr][nc]<0){distance[nr][nc]=distance[r][c]+1;q.push({nr,nc});}}}int best=0;for(const auto& row:distance)for(int value:row)best=std::max(best,value);for(int r=0;r<h;++r)for(int c=0;c<w;++c)if(distance[r][c]==best&&best>0)out.insert(out.end(),{r*w+c,best});""",
        # 9: orthogonal corner census
        r"""int convex=0,concave=0;for(int r=0;r<=h;++r)for(int c=0;c<=w;++c){std::array<int,4> bit{{r>0&&c>0&&g[r-1][c-1]=='1',r>0&&c<w&&g[r-1][c]=='1',r<h&&c>0&&g[r][c-1]=='1',r<h&&c<w&&g[r][c]=='1'}};int count=std::accumulate(bit.begin(),bit.end(),0);if(count==1)++convex;else if(count==3)++concave;else if(count==2&&bit[0]==bit[3])convex+=2;}out={convex,concave};""",
        # 10: translation-only shape grouping
        r"""std::vector<std::vector<int>> seen(h,std::vector<int>(w));std::map<std::vector<std::pair<int,int>>,int> classes;for(int sr=0;sr<h;++sr)for(int sc=0;sc<w;++sc)if(g[sr][sc]=='1'&&!seen[sr][sc]){std::queue<std::pair<int,int>> q;q.push({sr,sc});seen[sr][sc]=1;std::vector<std::pair<int,int>> shape;while(!q.empty()){auto [r,c]=q.front();q.pop();shape.push_back({r-sr,c-sc});for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]=='1'&&!seen[nr][nc]){seen[nr][nc]=1;q.push({nr,nc});}}}std::sort(shape.begin(),shape.end());++classes[shape];}for(const auto& item:classes)out.push_back(item.second);std::sort(out.begin(),out.end());""",
        # 11: dihedral shape grouping
        r"""std::vector<std::vector<int>> seen(h,std::vector<int>(w));std::map<std::vector<std::pair<int,int>>,int> classes;for(int sr=0;sr<h;++sr)for(int sc=0;sc<w;++sc)if(g[sr][sc]=='1'&&!seen[sr][sc]){std::queue<std::pair<int,int>> q;q.push({sr,sc});seen[sr][sc]=1;std::vector<std::pair<int,int>> cells;while(!q.empty()){auto cell=q.front();q.pop();cells.push_back(cell);for(auto [dr,dc]:dirs){int nr=cell.first+dr,nc=cell.second+dc;if(inside(nr,nc)&&g[nr][nc]=='1'&&!seen[nr][nc]){seen[nr][nc]=1;q.push({nr,nc});}}}std::vector<std::pair<int,int>> best;for(int kind=0;kind<8;++kind){std::vector<std::pair<int,int>> shape;for(auto [r,c]:cells){int a[8]={r,r,-r,-r,c,c,-c,-c};int b[8]={c,-c,c,-c,r,-r,r,-r};shape.push_back({a[kind],b[kind]});}int mr=shape.front().first,mc=shape.front().second;for(auto cell:shape){mr=std::min(mr,cell.first);mc=std::min(mc,cell.second);}for(auto& cell:shape){cell.first-=mr;cell.second-=mc;}std::sort(shape.begin(),shape.end());if(best.empty()||shape<best)best=shape;}++classes[best];}for(const auto& item:classes)out.push_back(item.second);std::sort(out.begin(),out.end());""",
        # 12: descending activation with incremental disjoint-set unions
        r"""std::vector<int> parent(static_cast<std::size_t>(h*w),-1),rank(static_cast<std::size_t>(h*w));auto find=[&](int node){int root=node;while(parent[root]!=root)root=parent[root];while(parent[node]!=node){int next=parent[node];parent[node]=root;node=next;}return root;};int count=0;for(int threshold=9;threshold>=0;--threshold){for(int cell=0;cell<h*w;++cell)if(g[cell/w][cell%w]-'0'==threshold){parent[cell]=cell;++count;for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(!inside(nr,nc)||parent[next]<0)continue;int a=find(cell),b=find(next);if(a==b)continue;if(rank[a]<rank[b])std::swap(a,b);parent[b]=a;if(rank[a]==rank[b])++rank[a];--count;}}out.insert(out.end(),{threshold,count});}""",
        # 13: unlike-label edge lengths
        r"""std::map<std::pair<char,char>,int> contact;for(int r=0;r<h;++r)for(int c=0;c<w;++c)if(g[r][c]!='.')for(auto [dr,dc]:std::array<std::pair<int,int>,2>{{{1,0},{0,1}}}){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]!='.'&&g[nr][nc]!=g[r][c]){char a=std::min(g[r][c],g[nr][nc]),b=std::max(g[r][c],g[nr][nc]);++contact[{a,b}];}}for(const auto& item:contact)out.insert(out.end(),{item.first.first,item.first.second,item.second});""",
        # 14: Euler ledger
        r"""auto count_components=[&](char value,bool boundary_only){std::vector<std::vector<int>> seen(h,std::vector<int>(w));int count=0;for(int sr=0;sr<h;++sr)for(int sc=0;sc<w;++sc)if(g[sr][sc]==value&&!seen[sr][sc]&&(!boundary_only||sr==0||sc==0||sr==h-1||sc==w-1)){++count;std::queue<std::pair<int,int>> q;q.push({sr,sc});seen[sr][sc]=1;while(!q.empty()){auto [r,c]=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc;if(inside(nr,nc)&&g[nr][nc]==value&&!seen[nr][nc]){seen[nr][nc]=1;q.push({nr,nc});}}}}return count;};int land=count_components('1',false);int zero=count_components('0',false);int exterior=count_components('0',true);int holes=zero-exterior;out={land,holes,land-holes};""",
        # 15: reachable indices
        r"""std::vector<int> distance(static_cast<std::size_t>(h*w),-1);std::queue<int> q;q.push(start);distance[start]=0;while(!q.empty()){int cell=q.front();q.pop();int r=cell/w,c=cell%w;for(auto [dr,dc]:dirs){int nr=r+dr,nc=c+dc,next=nr*w+nc;if(inside(nr,nc)&&g[nr][nc]!='#'&&distance[next]<0){distance[next]=distance[cell]+1;q.push(next);}}}for(int cell=0;cell<h*w;++cell)if(distance[cell]>=0)out.push_back(cell);""",
        # 16: shortest route
        r"""std::vector<int> distance(static_cast<std::size_t>(h*w),-1);std::queue<int> q;q.push(start);distance[start]=0;while(!q.empty()){int cell=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(inside(nr,nc)&&g[nr][nc]!='#'&&distance[next]<0){distance[next]=distance[cell]+1;q.push(next);}}}if(distance[goal]>=0)out.push_back(distance[goal]);""",
        # 17: shortest path count
        r"""std::vector<int> distance(static_cast<std::size_t>(h*w),-1),ways(static_cast<std::size_t>(h*w));std::queue<int> q;q.push(start);distance[start]=0;ways[start]=1;while(!q.empty()){int cell=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(!inside(nr,nc)||g[nr][nc]=='#')continue;if(distance[next]<0){distance[next]=distance[cell]+1;q.push(next);}if(distance[next]==distance[cell]+1)ways[next]=(ways[next]+ways[cell])%1000003;}}if(distance[goal]>=0)out={distance[goal],ways[goal]};""",
        # 18: lexicographic route codes
        r"""const std::array<std::pair<int,int>,4> order{{{-1,0},{0,-1},{0,1},{1,0}}};std::vector<int> parent(static_cast<std::size_t>(h*w),-2),move(static_cast<std::size_t>(h*w));std::queue<int> q;q.push(start);parent[start]=-1;while(!q.empty()){int cell=q.front();q.pop();for(int code=0;code<4;++code){int nr=cell/w+order[code].first,nc=cell%w+order[code].second,next=nr*w+nc;if(inside(nr,nc)&&g[nr][nc]!='#'&&parent[next]==-2){parent[next]=cell;move[next]=code;q.push(next);}}}if(parent[goal]!=-2){for(int cell=goal;cell!=start;cell=parent[cell])out.push_back(move[cell]);std::reverse(out.begin(),out.end());}""",
        # 19: BFS layer widths
        r"""std::vector<int> distance(static_cast<std::size_t>(h*w),-1);std::queue<int> q;q.push(start);distance[start]=0;while(!q.empty()){int cell=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(inside(nr,nc)&&g[nr][nc]!='#'&&distance[next]<0){distance[next]=distance[cell]+1;q.push(next);}}}if(distance[goal]>=0){out.assign(static_cast<std::size_t>(distance[goal]+1),0);for(int value:distance)if(value>=0&&value<=distance[goal])++out[static_cast<std::size_t>(value)];}""",
        # 20: mandatory cells by arbitrary-precision forward/reverse path counts
        r"""struct Big{std::vector<unsigned int> digit;explicit Big(unsigned int value=0){if(value!=0U)digit.push_back(value);}};constexpr unsigned long long base=1000000000ULL;auto add=[&](Big& left,const Big& right){const std::size_t size=std::max(left.digit.size(),right.digit.size());left.digit.resize(size);unsigned long long carry=0;for(std::size_t i=0;i<size;++i){const unsigned long long value=static_cast<unsigned long long>(left.digit[i])+(i<right.digit.size()?right.digit[i]:0U)+carry;left.digit[i]=static_cast<unsigned int>(value%base);carry=value/base;}if(carry!=0U)left.digit.push_back(static_cast<unsigned int>(carry));};auto multiply=[&](const Big& left,const Big& right){Big product;if(left.digit.empty()||right.digit.empty())return product;product.digit.assign(left.digit.size()+right.digit.size()+1U,0U);for(std::size_t i=0;i<left.digit.size();++i){unsigned long long carry=0;for(std::size_t j=0;j<right.digit.size()||carry!=0U;++j){const unsigned long long term=j<right.digit.size()?static_cast<unsigned long long>(left.digit[i])*right.digit[j]:0U;const unsigned long long value=product.digit[i+j]+term+carry;product.digit[i+j]=static_cast<unsigned int>(value%base);carry=value/base;}}while(!product.digit.empty()&&product.digit.back()==0U)product.digit.pop_back();return product;};auto counted_bfs=[&](int source){std::vector<int> distance(static_cast<std::size_t>(h*w),-1);std::vector<Big> ways(static_cast<std::size_t>(h*w));std::queue<int> q;q.push(source);distance[source]=0;ways[source]=Big(1);while(!q.empty()){int cell=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(!inside(nr,nc)||g[nr][nc]=='#')continue;if(distance[next]<0){distance[next]=distance[cell]+1;q.push(next);}if(distance[next]==distance[cell]+1)add(ways[next],ways[cell]);}}return std::make_pair(distance,ways);};auto from_state=counted_bfs(start),to_state=counted_bfs(goal);const auto& from=from_state.first;const auto& from_ways=from_state.second;const auto& to=to_state.first;const auto& to_ways=to_state.second;int target=from[goal];if(target>=0){const auto& total_ways=from_ways[goal];const std::vector<unsigned int> uint64_limit{{709551615U,446744073U,18U}};bool exceeds_uint64=total_ways.digit.size()>uint64_limit.size()||(total_ways.digit.size()==uint64_limit.size()&&std::lexicographical_compare(uint64_limit.rbegin(),uint64_limit.rend(),total_ways.digit.rbegin(),total_ways.digit.rend()));out.push_back(exceeds_uint64?1:0);for(int cell=0;cell<h*w;++cell)if(from[cell]>=0&&to[cell]>=0&&from[cell]+to[cell]==target&&multiply(from_ways[cell],to_ways[cell]).digit==total_ways.digit)out.push_back(cell);}""",
        # 21: dead-end peeling
        r"""std::set<int> alive;for(int cell=0;cell<h*w;++cell)if(g[cell/w][cell%w]!='#')alive.insert(cell);while(true){std::vector<int> remove;for(int cell:alive)if(cell!=start&&cell!=goal){int degree=0;for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc;if(inside(nr,nc)&&alive.count(nr*w+nc)!=0U)++degree;}if(degree<=1)remove.push_back(cell);}if(remove.empty())break;out.push_back(static_cast<int>(remove.size()));for(int cell:remove)alive.erase(cell);}""",
        # 22: 0-1 BFS wall cost
        r"""const int inf=1000000;std::vector<int> cost(static_cast<std::size_t>(h*w),inf);std::deque<int> q;q.push_back(start);cost[start]=0;while(!q.empty()){int cell=q.front();q.pop_front();for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(!inside(nr,nc))continue;int weight=g[nr][nc]=='#';if(cost[cell]+weight<cost[next]){cost[next]=cost[cell]+weight;if(weight)q.push_back(next);else q.push_front(next);}}}out.push_back(cost[goal]);""",
        # 23: break-budget product BFS
        r"""std::queue<std::array<int,4>> q;q.push({start,0,0,0});std::set<std::pair<int,int>> seen{{{start,0}}};while(!q.empty()){auto state=q.front();q.pop();int cell=state[0],used=state[1],steps=state[2];if(cell==goal){out.push_back(steps);break;}for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(!inside(nr,nc))continue;int next_used=used+(g[nr][nc]=='#');if(next_used<=request.parameter&&seen.insert({next,next_used}).second)q.push({next,next_used,steps+1,0});}}""",
        # 24: max-min clearance (relaxation)
        r"""std::vector<int> clearance(static_cast<std::size_t>(h*w),1000000);for(int cell=0;cell<h*w;++cell)for(int wall=0;wall<h*w;++wall)if(g[wall/w][wall%w]=='#')clearance[cell]=std::min(clearance[cell],std::abs(cell/w-wall/w)+std::abs(cell%w-wall%w));for(int cell=0;cell<h*w;++cell)clearance[cell]=std::min(clearance[cell],std::min({cell/w+1,cell%w+1,h-cell/w,w-cell%w}));std::vector<int> score(static_cast<std::size_t>(h*w),-1);score[start]=clearance[start];bool changed=true;while(changed){changed=false;for(int cell=0;cell<h*w;++cell)if(score[cell]>=0&&g[cell/w][cell%w]!='#')for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(inside(nr,nc)&&g[nr][nc]!='#'){int value=std::min(score[cell],clearance[next]);if(value>score[next]){score[next]=value;changed=true;}}}}if(score[goal]>=0)out.push_back(score[goal]);""",
        # 25: alternating movement axes
        r"""std::queue<std::array<int,3>> q;std::set<std::pair<int,int>> seen;for(int axis=0;axis<2;++axis){q.push({start,axis,0});seen.insert({start,axis});}while(!q.empty()){auto state=q.front();q.pop();int cell=state[0],prior=state[1],steps=state[2];if(cell==goal){out.push_back(steps);break;}for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc,axis=dr!=0;if(inside(nr,nc)&&g[nr][nc]!='#'&&axis!=prior&&seen.insert({next,axis}).second)q.push({next,axis,steps+1});}}""",
        # 26: deterministic right-hand patrol
        r"""const std::array<std::pair<int,int>,4> heading{{{-1,0},{0,1},{1,0},{0,-1}}};int cell=start,direction=1,steps=0;std::map<std::pair<int,int>,int> seen;while(seen.count({cell,direction})==0U){seen[{cell,direction}]=steps;bool moved=false;for(int turn:std::array<int,4>{{1,0,3,2}}){int nd=(direction+turn)%4,nr=cell/w+heading[nd].first,nc=cell%w+heading[nd].second;if(!inside(nr,nc)){out={steps+1,0};return out;}if(g[nr][nc]!='#'){cell=nr*w+nc;direction=nd;moved=true;break;}}if(!moved)direction=(direction+2)%4;++steps;}out={seen[{cell,direction}],steps-seen[{cell,direction}]};""",
        # 27: two-agent product state
        r"""std::queue<std::array<int,3>> q;q.push({start,goal,0});std::set<std::pair<int,int>> seen{{{start,goal}}};while(!q.empty()){auto state=q.front();q.pop();int a=state[0],b=state[1],steps=state[2];if(a==goal&&b==start){out.push_back(steps);break;}std::vector<int> ma{a},mb{b};for(auto [dr,dc]:dirs){int ar=a/w+dr,ac=a%w+dc,br=b/w+dr,bc=b%w+dc;if(inside(ar,ac)&&g[ar][ac]!='#')ma.push_back(ar*w+ac);if(inside(br,bc)&&g[br][bc]!='#')mb.push_back(br*w+bc);}for(int na:ma)for(int nb:mb)if(na!=nb&&!(na==b&&nb==a)&&seen.insert({na,nb}).second)q.push({na,nb,steps+1});}""",
        # 28: key/door state BFS
        r"""std::queue<std::array<int,3>> q;q.push({start,0,0});std::set<std::pair<int,int>> seen{{{start,0}}};while(!q.empty()){auto state=q.front();q.pop();int cell=state[0],keys=state[1],steps=state[2];if(cell==goal){out.push_back(steps);break;}for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(!inside(nr,nc))continue;char value=g[nr][nc];if(value=='#'||(value>='A'&&value<='B'&&(keys&(1<<(value-'A')))==0))continue;int next_keys=keys;if(value>='a'&&value<='b')next_keys|=1<<(value-'a');if(seen.insert({next,next_keys}).second)q.push({next,next_keys,steps+1});}}""",
        # 29: single-use paired portals
        r"""std::map<char,std::vector<int>> portal;for(int cell=0;cell<h*w;++cell)if(std::isdigit(static_cast<unsigned char>(g[cell/w][cell%w])))portal[g[cell/w][cell%w]].push_back(cell);std::queue<std::array<int,3>> q;q.push({start,0,0});std::set<std::pair<int,int>> seen{{{start,0}}};while(!q.empty()){auto state=q.front();q.pop();int cell=state[0],mask=state[1],steps=state[2];if(cell==goal){out.push_back(steps);break;}for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(inside(nr,nc)&&g[nr][nc]!='#'&&seen.insert({next,mask}).second)q.push({next,mask,steps+1});}char value=g[cell/w][cell%w];if(std::isdigit(static_cast<unsigned char>(value))&&(mask&(1<<(value-'0')))==0)for(int next:portal[value])if(next!=cell){int next_mask=mask|(1<<(value-'0'));if(seen.insert({next,next_mask}).second)q.push({next,next_mask,steps+1});}}""",
    )


def _wrapped_mandatory_body() -> str:
    return r"""auto counted_bfs=[&](int source){std::vector<int> distance(static_cast<std::size_t>(h*w),-1);std::vector<unsigned long long> ways(static_cast<std::size_t>(h*w));std::queue<int> q;q.push(source);distance[source]=0;ways[source]=1;while(!q.empty()){int cell=q.front();q.pop();for(auto [dr,dc]:dirs){int nr=cell/w+dr,nc=cell%w+dc,next=nr*w+nc;if(!inside(nr,nc)||g[nr][nc]=='#')continue;if(distance[next]<0){distance[next]=distance[cell]+1;q.push(next);}if(distance[next]==distance[cell]+1)ways[next]+=ways[cell];}}return std::make_pair(distance,ways);};auto from_state=counted_bfs(start),to_state=counted_bfs(goal);const auto& from=from_state.first;const auto& from_ways=from_state.second;const auto& to=to_state.first;const auto& to_ways=to_state.second;int target=from[goal];if(target>=0){out.push_back(0);const auto total_ways=from_ways[goal];for(int cell=0;cell<h*w;++cell)if(from[cell]>=0&&to[cell]>=0&&from[cell]+to[cell]==target&&from_ways[cell]*to_ways[cell]==total_ways)out.push_back(cell);}"""


def _alphabet(case: Case) -> str:
    index = CASES.index(case)
    if index == 12:
        return "0123456789"
    if index == 13:
        return ".ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if index == 28:
        return "#.SGabAB"
    if index == 29:
        return "#.SG0123456789"
    return "01" if case.domain == "region" else "#.SG"


def _reference(
    case: Case,
    *,
    body_index: int | None = None,
    body_override: str | None = None,
    grid_limit: int = 32,
) -> str:
    index = CASES.index(case)
    body = body_override or _cpp_bodies()[index if body_index is None else body_index]
    maze_validation = ""
    if case.domain == "maze":
        maze_validation = r"""int start=-1,goal=-1;for(int cell=0;cell<h*w;++cell){if(g[cell/w][cell%w]=='S'){if(start>=0)return std::nullopt;start=cell;}if(g[cell/w][cell%w]=='G'){if(goal>=0)return std::nullopt;goal=cell;}}if(start<0||goal<0)return std::nullopt;"""
    parameter_validation = (
        "if(request.parameter<0||request.parameter>8)return std::nullopt;" if index == 23 else ""
    )
    portal_validation = (
        r"""std::array<int,10> portal_count{};for(const auto& row:g)for(char value:row)if(std::isdigit(static_cast<unsigned char>(value)))++portal_count[static_cast<std::size_t>(value-'0')];for(int count:portal_count)if(count!=0&&count!=2)return std::nullopt;"""
        if index == 29
        else ""
    )
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <deque>
#include <map>
#include <numeric>
#include <queue>
#include <set>
#include <utility>
namespace regions_mazes {{
std::optional<std::vector<int>> {case.function}(const GridRequest& request){{
  const auto& g=request.grid;if(g.empty()||g.size()>{grid_limit}U||g.front().empty()||g.front().size()>{grid_limit}U)return std::nullopt;
  const int h=static_cast<int>(g.size()),w=static_cast<int>(g.front().size());
  const std::string allowed={json.dumps(_alphabet(case))};for(const auto& row:g)if(static_cast<int>(row.size())!=w||row.find_first_not_of(allowed)!=std::string::npos)return std::nullopt;
  {maze_validation}{parameter_validation}{portal_validation}
  [[maybe_unused]] const std::array<std::pair<int,int>,4> dirs{{std::pair<int,int>{{-1,0}},std::pair<int,int>{{0,-1}},std::pair<int,int>{{0,1}},std::pair<int,int>{{1,0}}}};
  [[maybe_unused]] auto inside=[&](int r,int c){{return r>=0&&r<h&&c>=0&&c<w;}};
  std::vector<int> out;{body}
  return out;
}}
}}
'''


def _lex_oracle(grid: tuple[str, ...], reverse: bool) -> list[int]:
    h, w = len(grid), len(grid[0])
    start, goal = _maze_points(grid)
    order = (
        ((1, 0, 0), (0, 1, 1), (0, -1, 2), (-1, 0, 3))
        if reverse
        else ((-1, 0, 0), (0, -1, 1), (0, 1, 2), (1, 0, 3))
    )
    queue = collections.deque([start])
    parent = {start: None}
    move: dict[tuple[int, int], int] = {}
    while queue:
        cell = queue.popleft()
        for dr, dc, code in order:
            nxt = (cell[0] + dr, cell[1] + dc)
            if (
                0 <= nxt[0] < h
                and 0 <= nxt[1] < w
                and grid[nxt[0]][nxt[1]] != "#"
                and nxt not in parent
            ):
                parent[nxt] = cell
                move[nxt] = code
                queue.append(nxt)
    if goal not in parent:
        return []
    result = []
    while goal != start:
        result.append(move[goal])
        goal = parent[goal]  # type: ignore[assignment]
    return result[::-1]


def _boundary_input(case: Case, limit: int) -> tuple[tuple[str, ...], int]:
    index = CASES.index(case)
    if case.domain == "region":
        fill = "0" if index != 13 else "."
        return tuple(fill * limit for _ in range(limit)), 0
    rows = [list("#" * limit) for _ in range(limit)]
    rows[0][0] = "S"
    rows[-1][-1] = "G"
    return tuple("".join(row) for row in rows), 0


def _test_source(
    case: Case,
    hidden: bool,
    *,
    opposite: bool = False,
    grid_limit: int = 32,
) -> str:
    grid, parameter = _case_input(case, hidden)
    expected = _lex_oracle(grid, True) if opposite else _oracle(case, grid, parameter)
    property_grid, property_parameter = PROPERTY_INPUTS[CASES.index(case)]
    property_expected = (
        _lex_oracle(property_grid, True)
        if opposite
        else _oracle(case, property_grid, property_parameter)
    )
    boundary, boundary_parameter = _boundary_input(case, grid_limit)
    boundary_expected = (
        _lex_oracle(boundary, True) if opposite else _oracle(case, boundary, boundary_parameter)
    )
    boundary_fill = "." if CASES.index(case) == 13 else ("0" if case.domain == "region" else "#")
    boundary_setup = f"GridRequest boundary{{std::vector<std::string>({grid_limit},std::string({grid_limit},'{boundary_fill}')),{boundary_parameter}}};"
    if case.domain == "maze":
        boundary_setup += "boundary.grid.front().front()='S';boundary.grid.back().back()='G';"
    ragged = list(grid)
    ragged[-1] = ragged[-1][:-1]
    illegal = list(grid)
    illegal[-1] = illegal[-1][:-1] + "x"
    oversize_fill = grid[0][0] if case.domain == "region" else "#"
    oversize_setup = f"GridRequest oversize{{std::vector<std::string>({grid_limit + 1},std::string(1,'{oversize_fill}')),{parameter}}};"
    if case.domain == "maze":
        oversize_setup += "oversize.grid.front().front()='S';oversize.grid.back().front()='G';"
    maze_invalid = ""
    if case.domain == "maze":
        missing = tuple(row.replace("G", ".") for row in grid)
        duplicate = list(grid)
        duplicate[-1] = "S" + duplicate[-1][1:]
        maze_invalid = f"""
  GridRequest missing_goal{{{_cpp_strings(missing)},{parameter}}};if({case.function}(missing_goal).has_value())return 8;
  GridRequest duplicate_start{{{_cpp_strings(tuple(duplicate))},{parameter}}};if({case.function}(duplicate_start).has_value())return 9;"""
    parameter_invalid = ""
    if CASES.index(case) == 23:
        parameter_invalid = f"""
  GridRequest low_budget{{{_cpp_strings(grid)},-1}};if({case.function}(low_budget).has_value())return 10;
  GridRequest high_budget{{{_cpp_strings(grid)},9}};if({case.function}(high_budget).has_value())return 11;"""
    portal_invalid = ""
    if CASES.index(case) == 29:
        portal_invalid = f"""
  GridRequest single_portal{{{_cpp_strings(("S1G",))},0}};if({case.function}(single_portal).has_value())return 12;
  GridRequest triple_portal{{{_cpp_strings(("S11", "1.G"))},0}};if({case.function}(triple_portal).has_value())return 13;
  GridRequest no_portal{{{_cpp_strings(("S.G",))},0}};auto no_portal_got={case.function}(no_portal);if(!no_portal_got||*no_portal_got!=std::vector<int>{{2}})return 14;"""
    trapped_patrol = ""
    if CASES.index(case) == 26:
        trapped_grid = ("#####", "#S###", "#####", "###G#", "#####")
        trapped_expected = _oracle(case, trapped_grid, 0)
        if trapped_expected != [0, 2]:
            raise AssertionError("fully trapped patrol oracle must form a two-transition cycle")
        trapped_patrol = f"""
  GridRequest trapped{{{_cpp_strings(trapped_grid)},0}};auto trapped_got={case.function}(trapped);if(!trapped_got||*trapped_got!=std::vector<int>{_cpp_ints(trapped_expected)})return 16;"""
    wrapped_path_counts = ""
    if CASES.index(case) == 20:
        overflow_grid = _overflow_diamond_grid()
        if _exact_shortest_path_count(overflow_grid) != 1 << 100:
            raise AssertionError("overflow diamond grid must have exactly 2^100 shortest paths")
        overflow_expected = _oracle(case, overflow_grid, 0)
        if not overflow_expected or overflow_expected[0] != 1:
            raise AssertionError("exact path-count discriminator must exceed uint64")
        wrapped_path_counts = f"""
  GridRequest wrapped_path_counts{{{_cpp_strings(overflow_grid)},0}};auto wrapped_path_counts_got={case.function}(wrapped_path_counts);if(!wrapped_path_counts_got||*wrapped_path_counts_got!=std::vector<int>{_cpp_ints(overflow_expected)})return 17;"""
    return f'''#include "{case.task_id}.h"
#include <vector>
int main(){{using namespace regions_mazes;
  GridRequest request{{{_cpp_strings(grid)},{parameter}}};
  auto got={case.function}(request);const std::vector<int> expected{_cpp_ints(expected)};
  if(!got||*got!=expected)return 1;
  GridRequest property{{{_cpp_strings(property_grid)},{property_parameter}}};
  auto property_got={case.function}(property);const std::vector<int> property_expected{_cpp_ints(property_expected)};
  if(!property_got||*property_got!=property_expected)return 15;
  {boundary_setup}
  auto boundary_got={case.function}(boundary);const std::vector<int> boundary_expected{_cpp_ints(boundary_expected)};
  if(!boundary_got||*boundary_got!=boundary_expected)return 2;
  GridRequest empty{{{{}},{parameter}}};if({case.function}(empty).has_value())return 3;
  GridRequest blank{{{{""}},{parameter}}};if({case.function}(blank).has_value())return 4;
  GridRequest ragged{{{_cpp_strings(tuple(ragged))},{parameter}}};if({case.function}(ragged).has_value())return 5;
  GridRequest illegal{{{_cpp_strings(tuple(illegal))},{parameter}}};if({case.function}(illegal).has_value())return 6;
  {oversize_setup}if({case.function}(oversize).has_value())return 7;{maze_invalid}{parameter_invalid}{portal_invalid}{trapped_patrol}{wrapped_path_counts}
  return 0;
}}
'''


def _instructions(
    case: Case,
    *,
    control: str | None = None,
    grid_limit: int = 32,
) -> str:
    mechanism = case.mechanism
    boundary = case.boundary
    exact_contract = CONTRACTS[CASES.index(case)]
    if control == "domain-identifier-renamed":
        boundary = boundary.replace("land", "occupied cell").replace("wall", "barrier")
    if control == "opposite-end-selection":
        boundary = boundary.replace("up=0,left=1,right=2,down=3", "down=0,right=1,left=2,up=3")
        exact_contract = exact_contract.replace(
            "up,left,right,down encoded 0,1,2,3",
            "down,right,left,up encoded 0,1,2,3",
        )
    alphabet = _alphabet(case)
    grid, parameter = _case_input(case, False)
    expected = _oracle(case, grid, parameter)
    grid_rows = "\n".join(grid)
    if expected:
        example_result = (
            f"`{case.function}` returns an engaged vector equal to "
            f"`{_cpp_ints(expected)}`."
        )
    else:
        example_result = f"`{case.function}` returns the engaged empty vector."
    boundary_sentence = boundary[0].upper() + boundary[1:] + "."
    return f"""# Instructions

Implement `{case.function}` in C++17.

Public API: `std::optional<std::vector<int>> {case.function}(const GridRequest& request)` in namespace `regions_mazes`. The caller retains ownership of `request`; return a new vector. The grid must be rectangular, non-empty, at most {grid_limit} by {grid_limit}, and contain only `{alphabet}`. {"Maze contracts require exactly one S and one G." if case.domain == "maze" else "Region contracts use the documented cell alphabet."} {"`parameter` must be in 0..8." if CASES.index(case) == 23 else "`parameter` is ignored."} Malformed input, including empty/ragged/oversize grids, illegal symbols, absent or duplicate S/G, invalid parameters, or invalid marker cardinality returns `std::nullopt` without partial output. A valid empty or unreachable result is an engaged empty vector. {boundary_sentence} Coordinates are encoded as `row * width + column`.

Exact behavior: {exact_contract}

## Example

For `parameter == {parameter}` and the grid

```text
{grid_rows}
```

{example_result}

Compute the answer directly from the request by {mechanism}, and return {case.output}. The result must come from the grid in front of you on every call: hard-coded answers or a general-purpose graph library that hides the traversal would only cover the inputs someone anticipated. Keep the function self-contained with only the C++17 standard library, with no files, networking, threads, timing, or randomness.
"""


def _semantic_profile(case: Case) -> dict[str, str]:
    return {
        "public_api": f"optional-vector/{case.domain}/{case.output}",
        "owned_state_algorithm": f"direct/{case.mechanism}/{case.output}",
        "mutation_selection_rules": f"{case.mechanism}/row-major/task-specific-selection",
        "invalid_boundary_behavior": f"{case.domain}/{case.boundary}/rectangular-bounded-grid",
        "reference_control_flow": f"specialized-{case.function}/{case.mechanism}",
        "deterministic_oracle": f"literal-visible-hidden/{case.output}/{case.boundary}",
        "topic_negative_fixture": f"neighbor-mechanism-substitution/{case.mechanism}/{case.output}",
    }


def _remedy_markdown(case: Case) -> str:
    index = CASES.index(case)
    special_invariant = (
        "Path counts use owned base-1,000,000,000 arbitrary-precision digits; every "
        "addition and forward/reverse product is exact, fixed-width wrapping is forbidden, "
        "and the leading result flag is one exactly when the total exceeds 2^64-1."
        if index == 20
        else (
            "When all four in-bounds patrol neighbors are walls, the orientation state rotates "
            "180 degrees in place and consumes exactly one transition."
            if index == 26
            else f"The direct owned mechanism is `{case.mechanism}`."
        )
    )
    return f"""## Identity

Task ID `{case.task_id}`; task-spec revision 3; family `{FAMILY_ID}`; disposition `repair-in-place`; source inventory `regions-mazes-source-inventory-v2`; license result `pass` (repository-authored clean room); generator `{GENERATOR_PATH}`; benchmark screen `pass`.

## Objective

Implement {case.mechanism} and return {case.output}.

## Public API

C++17 namespace `regions_mazes`; editable order `{case.task_id}.h`, `{case.task_id}.cpp`; API `std::optional<std::vector<int>> {case.function}(const GridRequest&)`; caller owns inputs and output.

## Behavior table

| Situation | Required result |
| --- | --- |
| Valid input | Execute `{case.mechanism}` and return {case.output}. |
| Invalid shape/alphabet/parameter | Return `std::nullopt` atomically without partial state. |
| Duplicate or absent required marker | Return `std::nullopt`; marker rules not used by this root are not applicable. |
| Valid empty or unreachable result | Return an engaged empty vector. |
| Mutation and ownership | Do not mutate caller-owned grid/parameter; return a new vector. |
| Ordering and ties | Deterministic row-major order plus the visible task-specific tie rule. |
| Overflow | No arithmetic wrap may affect the result; apply the exact task rule below. |
| Public boundary | A valid 32-by-32 grid executes normally; 33 rows or columns return `std::nullopt`. |

Exact task behavior: {CONTRACTS[index]} Boundary rule: {case.boundary}.

## Implementation invariant

{special_invariant} Forbidden substitutes are a runtime kind switch, sibling or benchmark code, hard-coded examples, ignored maze state, a neighboring statistic, and generic reachability when the contract requires richer state.

## Starter and reference

The task-named header is complete; the starter is a coherent nullopt stub. Both `.meta/example.*` files are complete independent replacements.

## Tests

Named cases `visible-primary`, `hidden-primary`, `mechanism-property`, `boundary-32`, `empty`, `blank`, `ragged`, `illegal`, `oversize-33`, and applicable marker/state cases use generator-literal deterministic inputs and Python-oracle outputs. `mandatory-shortest-cells` additionally runs `wrapped-path-counts`, a 29-by-32 chain of 100 two-way diamonds with exactly `2^100` shortest paths, and its compiled negative is the unsigned-64 implementation. `right-hand-patrol-cycle` runs `fully-trapped-orientation`. Other `.meta/negative_false_substitute.cpp` files compile a neighboring-mechanism fixture. Every negative must fail at least one production CTest.

## Files and metadata

Exact roles: solutions in order `{case.task_id}.h`, `{case.task_id}.cpp`; visible test `task_visible_test.cpp`; examples `.meta/example.h`, `.meta/example.cpp`; private test `.meta/task_hidden_test.cpp`; negative `.meta/negative_false_substitute.cpp`; config/provenance/tests ledger under `.meta`; docs and `CMakeLists.txt` are noneditable. Reference header/source map one-to-one to the two solutions. CMake support digest `{_sha(CMAKE.encode())}`.

## Build/oracle

Strict C++17, Unix Makefiles, `-Wall -Wextra -Wpedantic -Werror`, two positive normal and two equal fresh ASan/UBSan CTests in network-disabled `{SANITY_IMAGE}`. Run `uv run python -m w8_biayn.integrations.moonlight_regions_mazes_expansion --force --docker-sanity --record-cycle`; the receipt binds image/compiler/CMake/commands/network plus owner/tree/prompt/starter/reference/test/metadata/policy hashes. Host-only iteration uses `--force --verify-core --verify-host` on the documented host toolchain; its `host_iteration` receipt is not Docker sanity and never a locked oracle.

## Family/contamination

Compare all 435 retained pairs conjunctively across `public_api`, `owned_state_algorithm`, `mutation_selection_rules`, `invalid_boundary_behavior`, `reference_control_flow`, `deterministic_oracle`, and `topic_negative_fixture` using normalizer `regions-mazes-v1-domain-literal-endpoint-neutral`. Reject the coherent rename, constant/policy, and opposite-end controls; screen the immutable legacy/reverify/sibling-expansion snapshot and all 26 official C++ holdouts.

## Optional dataset handoff

`not_requested`.

## Acceptance

`uv run pytest -q tests/test_aider_sft_scope_docs.py tests/test_moonlight_regions_mazes_expansion.py` must pass all focused checks. Owner `--force --verify-core --record-cycle` must record 30 roots, 435 seven-dimension pairs, three rejected coherent controls, prompt/reference passes, 92,250 snapshot comparisons, and 780 holdout comparisons. Owner `--force --docker-sanity --record-cycle` must record 30 normal, 30 sanitizer, 30 negative, six control-reference, and three default-control builds. Stable failures include `remedy_spec_incomplete`, `generator_output_drift`, `duplicate_family`, `benchmark_content_overlap`, `prompt_contract_incomplete`, `target_reference_mismatch`, and `sanitizer_test_count_mismatch`. A fresh independent audit is required before `local_family_verified`.
"""


def _remedy_finding_ids(case: Case) -> list[str]:
    findings = {"RM-AUD-008"}
    if CASES.index(case) == 20:
        findings.add("RM-AUD-007")
    return sorted(findings)


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _capture_reaudit_3_inputs(out: Path) -> dict[str, object]:
    capture_path = out / ".state/remedy/audit-reaudit-03-input.json"
    report_path = out / REAUDIT_3_REPORT
    if report_path.is_file() and _file_hash(report_path) != REAUDIT_3_SHA256:
        _fail("audit_evidence_drift", str(report_path))
    if capture_path.is_file():
        captured = json.loads(capture_path.read_text())
        if (
            captured.get("audit_report_hash") != REAUDIT_3_SHA256
            or captured.get("audit_subject_hash") != REAUDIT_3_SUBJECT
        ):
            _fail("audit_evidence_drift", str(capture_path))
        return captured

    manifest_path = out / ".state/materialization-manifest.json"
    if report_path.is_file():
        if not manifest_path.is_file() or _file_hash(manifest_path) != REAUDIT_3_MANIFEST_SHA256:
            _fail("audit_evidence_drift", "re-audit-03 manifest is unavailable or changed")
        manifest = json.loads(manifest_path.read_text())
        before = {row["task_id"]: row["tree_hash"] for row in manifest["tasks"]}
    else:
        before = {
            case.task_id: (
                _tree_hash(out / case.task_id)
                if (out / case.task_id).is_dir()
                else "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            )
            for case in CASES
        }
    captured = {
        "schema_version": "regions-mazes-remediation-input-v1",
        "audit_report": str(REAUDIT_3_REPORT),
        "audit_report_hash": (
            _file_hash(report_path) if report_path.is_file() else "not_available_in_test_fixture"
        ),
        "audit_subject_hash": (
            REAUDIT_3_SUBJECT if report_path.is_file() else "not_available_in_test_fixture"
        ),
        "generator_revision_before": REAUDIT_3_OWNER_SHA256,
        "task_tree_hashes_before": before,
    }
    _write(capture_path, json.dumps(captured, indent=2, sort_keys=True) + "\n", False)
    return captured


def _capture_reaudit_4_inputs(out: Path) -> dict[str, object]:
    capture_path = out / ".state/remedy/audit-reaudit-04-input.json"
    report_path = out / REAUDIT_4_REPORT
    if report_path.is_file() and _file_hash(report_path) != REAUDIT_4_SHA256:
        _fail("audit_evidence_drift", str(report_path))
    if capture_path.is_file():
        captured = json.loads(capture_path.read_text())
        if (
            captured.get("audit_report_hash") != REAUDIT_4_SHA256
            or captured.get("audit_subject_hash") != REAUDIT_4_SUBJECT
        ):
            _fail("audit_evidence_drift", str(capture_path))
        return captured

    manifest_path = out / ".state/materialization-manifest.json"
    if report_path.is_file():
        if not manifest_path.is_file() or _file_hash(manifest_path) != REAUDIT_4_MANIFEST_SHA256:
            _fail("audit_evidence_drift", "re-audit-04 manifest is unavailable or changed")
        manifest = json.loads(manifest_path.read_text())
        before = {row["task_id"]: row["tree_hash"] for row in manifest["tasks"]}
        prior_records = {
            case.task_id: _file_hash(out / ".state/remedy" / f"{case.task_id}.json")
            for case in CASES
        }
    else:
        before = {
            case.task_id: (
                _tree_hash(out / case.task_id)
                if (out / case.task_id).is_dir()
                else "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            )
            for case in CASES
        }
        prior_records = {case.task_id: "not_available_in_test_fixture" for case in CASES}
    captured = {
        "schema_version": "regions-mazes-remediation-input-v1",
        "audit_report": str(REAUDIT_4_REPORT),
        "audit_report_hash": (
            _file_hash(report_path) if report_path.is_file() else "not_available_in_test_fixture"
        ),
        "audit_subject_hash": (
            REAUDIT_4_SUBJECT if report_path.is_file() else "not_available_in_test_fixture"
        ),
        "generator_revision_before": REAUDIT_4_OWNER_SHA256,
        "task_tree_hashes_before": before,
        "prior_remedy_record_hashes": prior_records,
    }
    _write(capture_path, json.dumps(captured, indent=2, sort_keys=True) + "\n", False)
    return captured


def _write_remedy_record(
    out: Path,
    case: Case,
    inputs: dict[str, object],
    spec: str,
    force: bool,
) -> None:
    spec_path = out / ".state/remedy" / f"{case.task_id}.md"
    record = {
        "schema_version": "aider-task-remedy-v1",
        "task_id": case.task_id,
        "family_id_before": FAMILY_ID,
        "tree_hash_before": inputs["task_tree_hashes_before"][case.task_id],
        "generator_path": str(GENERATOR_PATH),
        "generator_revision": inputs["generator_revision_before"],
        "finding_ids": _remedy_finding_ids(case),
        "disposition": "repair-in-place",
        "benchmark_screen": "pass",
        "license_screen": "pass",
        "remedy_spec_path": _repo_relative(spec_path),
        "remedy_spec_hash": _sha(spec.encode()),
        "status": "planned",
        "audit_report_hash": inputs["audit_report_hash"],
        "audit_subject_hash": inputs["audit_subject_hash"],
        "prior_remedy_record_hash": inputs.get("prior_remedy_record_hashes", {}).get(
            case.task_id, "not_available"
        ),
        "finding_lineage": {
            "resolved_prior": [
                "RM-AUD-001",
                "RM-AUD-002",
                "RM-AUD-003",
                "RM-AUD-004",
                "RM-AUD-005",
                "RM-AUD-006",
            ],
            "current": _remedy_finding_ids(case),
        },
        "primary_core_objective": "achieved",
    }
    _write(
        out / ".state/remedy" / f"{case.task_id}.json",
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        force,
    )


def _render_files(case: Case, *, control: str | None = None) -> dict[str, str]:
    index = CASES.index(case)
    grid_limit = 48 if control == "constants-policy-only" else 32
    reference = _reference(case, grid_limit=grid_limit)
    opposite = control == "opposite-end-selection"
    if opposite:
        reference = reference.replace(
            "{{{-1,0},{0,-1},{0,1},{1,0}}}",
            "{{{1,0},{0,1},{0,-1},{-1,0}}}",
        )
    negative_index = (index + 1) % 15 if index < 15 else 15 + ((index - 15 + 1) % 15)
    negative = _reference(
        case,
        body_index=negative_index,
        body_override=_wrapped_mandatory_body() if index == 20 else None,
    )
    config = {
        "authors": ["w8-biayn"],
        "blurb": f"{case.mechanism} for a clean-room {case.domain} contract.",
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "benchmark_separation": "All official Aider C++ roots are permanent holdouts; no holdout assets were used.",
        "count_plan_cell": "ownership, regions, flood behavior, mazes, and reachability / 30",
        "curriculum_document": str(CURRICULUM),
        "family_id": FAMILY_ID,
        "family_specification": str(FAMILY_SPEC),
        "lineage": "new-root",
        "mechanism": case.mechanism,
        "origin": "repository-authored clean-room expansion",
        "prompt_path": "docs/aider-tasks-spec/prompts/generate-family-spec.md then implement-family-for-sft.md",
        "semantic_profile": _semantic_profile(case),
        "status": "local task artifact; not admitted SFT data",
        "task_id": case.task_id,
        "version": 1,
    }
    cmake = CMAKE.replace(
        '"${CMAKE_CURRENT_SOURCE_DIR}/task.cpp"',
        f'"${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.cpp"',
    )
    files = {
        ".docs/introduction.md": f"# {case.title}\n\n{INTRODUCTIONS[case.task_id]}"
        + (
            " This policy accepts grids through 48 by 48."
            if control == "constants-policy-only"
            else ""
        )
        + "\n",
        ".docs/instructions.md": _instructions(case, control=control, grid_limit=grid_limit),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": '[visible]\ndescription="deterministic contract example"\n[hidden]\ndescription="second topology and malformed-input rejection"\n[negative]\ndescription="compilable neighboring mechanism must fail"\n',
        f"{case.task_id}.h": _header(case),
        f"{case.task_id}.cpp": f'#include "{case.task_id}.h"\nnamespace regions_mazes {{ std::optional<std::vector<int>> {case.function}(const GridRequest&){{return std::nullopt;}} }}\n',
        ".meta/example.h": _header(case),
        ".meta/example.cpp": reference,
        ".meta/negative_false_substitute.cpp": negative,
        "task_visible_test.cpp": _test_source(
            case, False, opposite=opposite, grid_limit=grid_limit
        ),
        ".meta/task_hidden_test.cpp": _test_source(
            case, True, opposite=opposite, grid_limit=grid_limit
        ),
        "CMakeLists.txt": cmake,
    }
    if control == "domain-identifier-renamed":
        old_id = case.task_id
        old_function = case.function
        new_id = "ordered-passage-symbols"
        new_function = "ordered_passage_symbols"
        renamed: dict[str, str] = {}
        for relative, content in files.items():
            new_relative = relative.replace(old_id, new_id)
            renamed[new_relative] = (
                content.replace(old_id, new_id)
                .replace(old_function, new_function)
                .replace("Lexicographic Route Codes", "Ordered Passage Symbols")
            )
        files = renamed
    return files


def _write_root(root: Path, case: Case, force: bool, *, control: str | None = None) -> None:
    rendered = task_named_files(root, _render_files(case, control=control))
    expected = set(rendered)
    stale = (
        sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and path.relative_to(root).as_posix() not in expected
        )
        if root.is_dir()
        else []
    )
    if stale and not force:
        raise FileExistsError(f"{root} contains stale generated files; pass --force")
    for path in stale:
        path.unlink()
    if root.is_dir():
        for directory in sorted(
            (path for path in root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not any(directory == (root / relative).parent for relative in expected):
                try:
                    directory.rmdir()
                except OSError:
                    pass
    for relative, content in rendered.items():
        _write(root / relative, content, force)


def _write_controls(out: Path, force: bool) -> None:
    case = CASES[18]
    base_root = out / case.task_id
    base_files = {
        path.relative_to(base_root).as_posix(): path.read_text()
        for path in base_root.rglob("*")
        if path.is_file()
    }
    records = {}
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        root = out / ".state/adversarial-clone-controls" / name
        _write_root(root, case, force, control=name)
        control_files = {
            path.relative_to(root).as_posix(): path.read_text()
            for path in root.rglob("*")
            if path.is_file()
        }
        records[name] = {
            "changed_files": sorted(
                relative
                for relative in set(base_files) | set(control_files)
                if base_files.get(relative) != control_files.get(relative)
            ),
            "tree_hash": _tree_hash(root, include_state=True),
        }
    _write(
        out / ".state/adversarial-clone-controls/manifest.json",
        json.dumps(
            {
                "schema_version": "regions-mazes-clone-controls-v1",
                "base_task_id": case.task_id,
                "controls": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )


def _stable_semantic_record(tree: Path, task_root: Path) -> dict[str, object]:
    for _ in range(8):
        before = _tree_hash(task_root)
        readable = [
            path
            for path in sorted(task_root.rglob("*"))
            if path.is_file() and path.stat().st_size < 1_000_000 and ".state" not in path.parts
        ]
        contents = [(path, path.read_bytes()) for path in readable]
        after = _tree_hash(task_root)
        config = task_root / ".meta/config.json"
        if before == after and config.is_file():
            text = " ".join(data.decode(errors="ignore") for _, data in contents)
            return {
                "task_id": task_root.name,
                "relative_root": task_root.relative_to(tree).as_posix(),
                "tree_hash": after,
                "config_hash": _file_hash(config),
                "artifact_hashes": sorted({_sha(data) for _, data in contents}),
                "semantic_tokens": sorted(set(_normalized_tokens(text))),
            }
    _fail("source_inventory_unstable", str(task_root))


def _semantic_inventory(
    tree: Path, *, excluded_prefix: str | None = None
) -> list[dict[str, object]]:
    if not tree.is_dir():
        return []
    configs = [
        config for config in sorted(tree.rglob(".meta/config.json")) if ".state" not in config.parts
    ]
    records = []
    for config in configs:
        task_root = config.parent.parent
        relative = task_root.relative_to(tree).as_posix()
        if excluded_prefix is not None and relative.startswith(excluded_prefix):
            continue
        if not config.is_file():
            continue
        records.append(_stable_semantic_record(tree, task_root))
    return records


def _freeze_inventory(out: Path, force: bool) -> dict[str, object]:
    family_prefix = out.relative_to(EXPANSION_ROOT).as_posix() + "/"
    inventories = {
        "legacy": _semantic_inventory(LEGACY_ROOT),
        "reverify": _semantic_inventory(REVERIFY_ROOT),
        "expansion_before": _semantic_inventory(EXPANSION_ROOT, excluded_prefix=family_prefix),
    }
    payload: dict[str, object] = {
        "schema_version": "regions-mazes-source-inventory-v2",
        "snapshot_policy": (
            "config paths enumerated at creator start; every retained source root is read "
            "between equal before/after tree hashes; later external writes do not mutate "
            "or retroactively invalidate this digest-bound semantic snapshot"
        ),
        "roots": {},
    }
    for name, records in inventories.items():
        serialized = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
        payload["roots"][name] = {
            "count": len(records),
            "sha256": _sha(serialized),
            "records": records,
        }
    _write(
        out / ".state/source-inventory.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        force,
    )
    return payload


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _validate_output(out)
    _validate_prewrite_owned_paths(out)
    reaudit_3_inputs = _capture_reaudit_3_inputs(out)
    reaudit_4_inputs = _capture_reaudit_4_inputs(out)
    source_inventory = _freeze_inventory(out, force)
    existing = {
        record["task_id"]
        for name in ("legacy", "reverify", "expansion_before")
        for record in source_inventory["roots"][name]["records"]
    }
    collisions = sorted(existing & {case.task_id for case in CASES})
    if collisions:
        _fail("duplicate_task", ",".join(collisions))
    roots = []
    for case in CASES:
        root = out / case.task_id
        if root.exists() and any(path.is_symlink() for path in root.rglob("*")):
            _fail("unsafe_path", f"symlink in owned root: {root}")
        remedy_spec = _remedy_markdown(case)
        _write(out / ".state/remedy" / f"{case.task_id}.md", remedy_spec, force)
        _write_remedy_record(out, case, reaudit_4_inputs, remedy_spec, force)
        _write_root(root, case, force)
        roots.append(root)
    _write_controls(out, force)
    audit_path = out / INITIAL_AUDIT_REPORT
    if audit_path.is_file() and _file_hash(audit_path) != INITIAL_AUDIT_SHA256:
        _fail("audit_evidence_drift", str(audit_path))
    _write(
        out / ".state/remedy/audit-cycle-01-remediation.json",
        json.dumps(
            {
                "schema_version": "regions-mazes-audit-remediation-v1",
                "audit_report": str(INITIAL_AUDIT_REPORT),
                "audit_report_hash": (
                    _file_hash(audit_path)
                    if audit_path.is_file()
                    else "not_available_in_test_fixture"
                ),
                "audit_subject_hash": "sha256:347c45da07c55dff7e3429df87d7e046577e51f27e94c0b4e3d1be797d6e9ab3",
                "disposition": "repair-in-place-then-regenerate-and-fresh-reaudit",
                "findings": AUDIT_REMEDIES,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )
    reaudit_path = out / REAUDIT_2_REPORT
    if reaudit_path.is_file() and _file_hash(reaudit_path) != REAUDIT_2_SHA256:
        _fail("audit_evidence_drift", str(reaudit_path))
    _write(
        out / ".state/remedy/audit-reaudit-02-remediation.json",
        json.dumps(
            {
                "schema_version": "regions-mazes-audit-remediation-v1",
                "audit_report": str(REAUDIT_2_REPORT),
                "audit_report_hash": (
                    _file_hash(reaudit_path)
                    if reaudit_path.is_file()
                    else "not_available_in_test_fixture"
                ),
                "audit_subject_hash": "sha256:785df1c285cd7ddf27755c2279470c489eaa41f71e85195e90a6db7f6ee2288c",
                "disposition": "repair-in-place-then-regenerate-and-fresh-reaudit",
                "findings": AUDIT_REMEDIES,
                "invalidated_status": "local_family_verified",
                "replacement_or_rejection": "none",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )
    reaudit_3_path = out / REAUDIT_3_REPORT
    if reaudit_3_path.is_file() and _file_hash(reaudit_3_path) != REAUDIT_3_SHA256:
        _fail("audit_evidence_drift", str(reaudit_3_path))
    _write(
        out / ".state/remedy/audit-reaudit-03-remediation.json",
        json.dumps(
            {
                "schema_version": "regions-mazes-audit-remediation-v1",
                "audit_report": str(REAUDIT_3_REPORT),
                "audit_report_hash": reaudit_3_inputs["audit_report_hash"],
                "audit_subject_hash": reaudit_3_inputs["audit_subject_hash"],
                "disposition": "repair-in-place-then-regenerate-and-fresh-reaudit",
                "findings": {
                    "RM-AUD-005": AUDIT_REMEDIES["RM-AUD-005"],
                    "RM-AUD-007": AUDIT_REMEDIES["RM-AUD-007"],
                    "RM-AUD-008": "versioned per-root remedy specifications and aider-task-remedy-v1 records bound to preserved before-state evidence",
                },
                "invalidated_status": "creator_preflight_passed_pending_independent_audit",
                "replacement_or_rejection": "none",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )
    reaudit_4_path = out / REAUDIT_4_REPORT
    if reaudit_4_path.is_file() and _file_hash(reaudit_4_path) != REAUDIT_4_SHA256:
        _fail("audit_evidence_drift", str(reaudit_4_path))
    _write(
        out / ".state/remedy/audit-reaudit-04-remediation.json",
        json.dumps(
            {
                "schema_version": "regions-mazes-audit-remediation-v1",
                "audit_report": str(REAUDIT_4_REPORT),
                "audit_report_hash": reaudit_4_inputs["audit_report_hash"],
                "audit_subject_hash": reaudit_4_inputs["audit_subject_hash"],
                "disposition": "repair-in-place-then-regenerate-and-fresh-reaudit",
                "findings": {
                    "RM-AUD-007": "bounded 29x32 serial-diamond discriminator with exactly 2^100 shortest paths plus an executed unsigned-64 false substitute",
                    "RM-AUD-008": "implemented pre-audit remedy state with terminal promotion deferred to a clean fresh audit",
                },
                "invalidated_status": (
                    "local_oracle_and_semantic_gates_verified_pending_fresh_independent_audit"
                ),
                "replacement_or_rejection": "none",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )
    return tuple(roots)


def _normalized_tokens(text: str) -> tuple[str, ...]:
    for case in CASES:
        text = text.replace(case.task_id, "TASK_ID").replace(case.function, "TASK_FUNCTION")
    text = text.replace("ordered-passage-symbols", "TASK_ID").replace(
        "ordered_passage_symbols", "TASK_FUNCTION"
    )
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|(?<![A-Za-z_])-?\d+\b', " LIT ", text)
    text = re.sub(
        r"\b(front|back|earlier|later|minimum|maximum|first|last|up|down|left|right|stable|reverse|tie|order|endpoint)\b",
        " ENDPOINT ",
        text,
        flags=re.I,
    )
    text = re.sub(r">=|<=|>|<", " REL ", text)
    text = re.sub(
        r"region|district|maze|passage|grid|land|occupied|wall|barrier|cell|route|lexicographic|ordered|codes|symbols",
        "DOMAIN",
        text,
        flags=re.I,
    )
    return tuple(re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|&&|\|\||[-+*/%{}()[\];,?:=.]", text))


def _dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    reference = (root / ".meta/example.cpp").read_text()
    instructions = (root / ".docs/instructions.md").read_text()
    config = json.loads((root / ".meta/config.json").read_text())
    header = (root / config["files"]["solution"][0]).read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    return {
        "public_api": _normalized_tokens(header + instructions),
        "owned_state_algorithm": _normalized_tokens(reference),
        "mutation_selection_rules": _normalized_tokens(instructions + reference),
        "invalid_boundary_behavior": _normalized_tokens(instructions + hidden),
        "reference_control_flow": _normalized_tokens(reference),
        "deterministic_oracle": _normalized_tokens(instructions + visible + hidden),
        "topic_negative_fixture": _normalized_tokens(negative),
    }


def _pair_decisions(left: Path, right: Path) -> dict[str, bool]:
    a, b = _dimension_material(left), _dimension_material(right)
    return {dimension: a[dimension] != b[dimension] for dimension in HARD_DIMENSIONS}


def _semantic_screen(out: Path) -> dict[str, object]:
    pairs = []
    roots = sorted((out / case.task_id for case in CASES), key=lambda path: path.name)
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions = _pair_decisions(left, right)
            if not all(decisions.values()):
                _fail("duplicate_family", f"{left.name} vs {right.name}: {decisions}")
            pairs.append({"left": left.name, "right": right.name, "decisions": decisions})
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"{len(pairs)} != {expected}")
    base = out / CASES[18].task_id
    controls = {}
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        root = out / ".state/adversarial-clone-controls" / name
        decisions = _pair_decisions(base, root)
        if any(decisions.values()):
            _fail("duplicate_family", f"clone control escaped: {name}: {decisions}")
        controls[name] = {"decisions": decisions, "production_rejected": True}
    return {
        "status": "pass",
        "root_count": len(CASES),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "dimensions": list(HARD_DIMENSIONS),
        "pairs": pairs,
        "controls": controls,
        "normalizer": "regions-mazes-v1-domain-literal-endpoint-neutral",
    }


def _ngrams(tokens: tuple[str, ...], width: int = 11) -> set[tuple[str, ...]]:
    return {tokens[index : index + width] for index in range(max(0, len(tokens) - width + 1))}


def _holdout_screen(out: Path) -> dict[str, object]:
    found = (
        {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()}
        if HOLDOUT_ROOT.is_dir()
        else set()
    )
    if missing := sorted(OFFICIAL_HOLDOUTS - found):
        _fail("benchmark_content_overlap", f"bound holdouts unavailable: {missing}")
    candidates = {
        case.task_id: _ngrams(
            _normalized_tokens(
                " ".join(
                    path.read_text(errors="ignore")
                    for path in sorted((out / case.task_id).rglob("*"))
                    if path.is_file() and path.stat().st_size < 1_000_000
                )
            )
        )
        for case in CASES
    }
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    for holdout_id in sorted(OFFICIAL_HOLDOUTS):
        text = " ".join(
            path.read_text(errors="ignore")
            for path in sorted((HOLDOUT_ROOT / holdout_id).rglob("*"))
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        grams = _ngrams(_normalized_tokens(text))
        for task_id, candidate in candidates.items():
            denominator = min(len(candidate), len(grams))
            score = len(candidate & grams) / denominator if denominator else 0.0
            comparisons += 1
            if score > strongest:
                strongest, strongest_pair = score, [task_id, holdout_id]
            if score >= 0.80:
                _fail("benchmark_content_overlap", f"{task_id} vs {holdout_id}: {score:.3f}")
    return {
        "status": "pass",
        "holdout_root_count": 26,
        "holdout_inventory_hash": _sha(
            json.dumps(
                [
                    [holdout_id, _tree_hash(HOLDOUT_ROOT / holdout_id)]
                    for holdout_id in sorted(OFFICIAL_HOLDOUTS)
                ],
                separators=(",", ":"),
            ).encode()
        ),
        "comparison_count": comparisons,
        "threshold": 0.80,
        "strongest_pair": strongest_pair,
        "strongest_containment": round(strongest, 6),
    }


def _cross_tree_semantic_screen(out: Path) -> dict[str, object]:
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    candidate_material = {}
    candidate_hashes = {}
    for case in CASES:
        root = out / case.task_id
        artifacts = {
            "prompt": (root / ".docs/instructions.md").read_text(),
            "api": next(root.glob("*.h")).read_text(),
            "reference": (root / ".meta/example.cpp").read_text(),
            "tests": (root / "task_visible_test.cpp").read_text()
            + (root / ".meta/task_hidden_test.cpp").read_text(),
            "starter": (root / f"{case.task_id}.cpp").read_text(),
        }
        candidate_material[case.task_id] = set(_normalized_tokens("\n".join(artifacts.values())))
        candidate_hashes[case.task_id] = {
            name: _sha(value.encode()) for name, value in artifacts.items()
        }

    frozen = json.loads((out / ".state/source-inventory.json").read_text())["roots"]
    per_tree = {}
    relations: list[dict[str, object]] = []
    exact_collisions: list[dict[str, str]] = []
    for tree_name in ("legacy", "reverify", "expansion_before"):
        records = frozen[tree_name]["records"]
        tree_count = tree_comparisons = 0
        tree_strongest = 0.0
        for record in records:
            tree_count += 1
            other = set(record["semantic_tokens"])
            other_hashes = set(record["artifact_hashes"])
            for task_id, current in candidate_material.items():
                score = (
                    len(current & other) / min(len(current), len(other))
                    if current and other
                    else 0.0
                )
                comparisons += 1
                tree_comparisons += 1
                tree_strongest = max(tree_strongest, score)
                if score > strongest:
                    strongest, strongest_pair = score, [task_id, record["relative_root"]]
                for role, digest in candidate_hashes[task_id].items():
                    if digest in other_hashes:
                        exact_collisions.append(
                            {
                                "task_id": task_id,
                                "other_root": record["relative_root"],
                                "tree": tree_name,
                                "role": role,
                            }
                        )
                if score >= 0.55:
                    relations.append(
                        {
                            "task_id": task_id,
                            "other_root": record["relative_root"],
                            "tree": tree_name,
                            "score": round(score, 6),
                            "relation": "normalized-artifact-near-match",
                            "disposition": "distinct-contract-below-rejection-threshold",
                        }
                    )
                if score >= 0.98:
                    _fail(
                        "duplicate_family",
                        f"cross-tree semantic overlap {score:.3f}: {strongest_pair}",
                    )
        per_tree[tree_name] = {
            "root_count": tree_count,
            "comparison_count": tree_comparisons,
            "strongest_score": round(tree_strongest, 6),
            "inventory_hash": frozen[tree_name]["sha256"],
        }
    if exact_collisions:
        _fail("duplicate_family", f"exact cross-tree artifact collisions: {exact_collisions[:3]}")
    for case in CASES:
        for path in (out / case.task_id).rglob("*"):
            if path.is_symlink():
                _fail("unsafe_path", f"symlink in generated root: {path}")
            if path.is_file() and path.stat().st_nlink != 1:
                _fail("unsafe_path", f"hardlink in generated root: {path}")
    lineage = {
        "schema_version": "regions-mazes-semantic-lineage-v2",
        "status": "pass",
        "comparison_count": comparisons,
        "threshold": 0.98,
        "strongest_pair": strongest_pair,
        "strongest_score": round(strongest, 6),
        "per_tree": per_tree,
        "exact_collisions": exact_collisions,
        "relations": relations,
        "symlink_hardlink_screen": "pass",
        "source_snapshot_policy": "digest-bound stable per-root snapshot; post-snapshot external mutations are out of subject",
    }
    _write(
        out / ".state/semantic-lineage-screen.json",
        json.dumps(lineage, indent=2, sort_keys=True) + "\n",
        True,
    )
    return lineage | {"report": ".state/semantic-lineage-screen.json"}


def verify_core(out: Path = DEFAULT_OUT) -> None:
    if len(CASES) != 30 or len({case.task_id for case in CASES}) != 30:
        _fail("duplicate_task", f"expected exactly 30 unique roots, got {len(CASES)}")
    rows = []
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for case in CASES:
        root = out / case.task_id
        remedy_spec_path = out / ".state/remedy" / f"{case.task_id}.md"
        remedy_record_path = out / ".state/remedy" / f"{case.task_id}.json"
        if not remedy_spec_path.is_file() or not remedy_record_path.is_file():
            _fail("remedy_spec_incomplete", case.task_id)
        remedy_record = json.loads(remedy_record_path.read_text())
        if (
            remedy_record.get("schema_version") != "aider-task-remedy-v1"
            or remedy_record.get("task_id") != case.task_id
            or remedy_record.get("disposition") != "repair-in-place"
            or remedy_record.get("finding_ids") != _remedy_finding_ids(case)
            or remedy_record.get("remedy_spec_hash") != _file_hash(remedy_spec_path)
            or remedy_record.get("status") not in ("planned", "implemented", "verified")
        ):
            _fail("remedy_spec_incomplete", case.task_id)
        config = json.loads((root / ".meta/config.json").read_text())
        if config["files"]["solution"] != [f"{case.task_id}.h", f"{case.task_id}.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        if any(
            token in prompt
            for token in (
                ".meta/",
                "CMakeLists",
                "task_visible_test",
                "provenance",
                "negative_false_substitute",
            )
        ):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if (
            not answer.startswith(f"{case.task_id}.h\n```")
            or f"{case.task_id}.cpp\n```" not in answer
        ):
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
                "domain": case.domain,
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
                "primary_core_objective": "achieved",
            }
        )
    manifest = {
        "schema_version": "regions-mazes-materialization-v1",
        "family_id": FAMILY_ID,
        "task_count": 30,
        "domain_counts": {
            domain: sum(case.domain == domain for case in CASES) for domain in ("region", "maze")
        },
        "owner_hash": _file_hash(Path(__file__)),
        "curriculum_hash": _file_hash(CURRICULUM),
        "family_spec_hash": _file_hash(FAMILY_SPEC),
        "focused_test_hash": _file_hash(TEST_PATH),
        "family_tree_hash": _tree_hash(out),
        "tasks": rows,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "diversity": _semantic_screen(out),
            "benchmark_holdout": _holdout_screen(out),
            "cross_tree": _cross_tree_semantic_screen(out),
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
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        roots = [out / case.task_id for case in CASES]
        roots += [
            out / ".state/adversarial-clone-controls" / name
            for name in (
                "domain-identifier-renamed",
                "constants-policy-only",
                "opposite-end-selection",
            )
        ]
        for root in roots:
            prefix = "tasks" if root.parent == out else "controls"
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(
                    str(path), arcname=f"{prefix}/{root.name}/{path.relative_to(root).as_posix()}"
                )
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
    return _file_hash(target)


def _complete_remedy_records(
    out: Path,
    receipt_name: str = "docker-sanity.json",
    strongest_status: str = "local_oracle_and_semantic_gates_passed_pending_fresh_independent_audit",
) -> None:
    receipt_path = out / ".state" / receipt_name
    manifest_path = out / ".state/materialization-manifest.json"
    receipt = json.loads(receipt_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    changed_paths = [
        str(GENERATOR_PATH),
        str(TEST_PATH),
        str(CURRICULUM),
        str(FAMILY_SPEC),
    ]
    for case in CASES:
        record_path = out / ".state/remedy" / f"{case.task_id}.json"
        spec_path = out / ".state/remedy" / f"{case.task_id}.md"
        record = json.loads(record_path.read_text())
        if record.get("remedy_spec_hash") != _file_hash(spec_path):
            _fail("remedy_spec_incomplete", case.task_id)
        record.update(
            {
                "status": "implemented",
                "tree_hash_after": _tree_hash(out / case.task_id),
                "generator_revision_after": _file_hash(Path(__file__)),
                "changed_generator_source_test_paths": changed_paths,
                "primary_core_objective": "achieved",
                "primary_core_evidence": {
                    "reference": f"{case.task_id}/.meta/example.cpp",
                    "tests": [
                        f"{case.task_id}/task_visible_test.cpp",
                        f"{case.task_id}/.meta/task_hidden_test.cpp",
                        f"{case.task_id}/.meta/negative_false_substitute.cpp",
                    ],
                    "mechanism": case.mechanism,
                },
                "prompt_boundary": manifest["screen"]["prompt_boundary"],
                "family_screen": manifest["screen"]["diversity"]["status"],
                "benchmark_screen": manifest["screen"]["benchmark_holdout"]["status"],
                "cross_tree_screen": manifest["screen"]["cross_tree"]["status"],
                "normal_sanitizer_receipt_id": _file_hash(receipt_path),
                "oracle_counts": {
                    "normal_reference": receipt["normal_reference_count"],
                    "sanitizer_reference": receipt["sanitizer_reference_count"],
                    "normal_tests_per_root": receipt["normal_test_count_per_root"],
                    "sanitizer_tests_per_root": receipt["sanitizer_test_count_per_root"],
                },
                "strongest_truthful_status": strongest_status,
                "dataset_handoff": "not_requested",
            }
        )
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _promote_remedy_records_after_audit(out: Path) -> None:
    report_path = out / ".state/audits/regions-mazes-post-remediation-reaudit-5-20260722.md"
    if not report_path.is_file():
        _fail("audit_evidence_drift", "terminal re-audit-05 report is unavailable")
    report = report_path.read_text()
    family_hash = _tree_hash(out)
    owner_hash = _file_hash(Path(__file__))
    if (
        "Verdict: **pass" not in report
        or family_hash not in report
        or owner_hash not in report
        or "30 pass" not in report
    ):
        _fail("audit_evidence_drift", "terminal re-audit-05 does not pass the current subject")
    for case in CASES:
        record_path = out / ".state/remedy" / f"{case.task_id}.json"
        record = json.loads(record_path.read_text())
        if record.get("status") != "implemented" or record.get("tree_hash_after") != _tree_hash(
            out / case.task_id
        ):
            _fail("audit_evidence_drift", f"unpromotable remedy record: {case.task_id}")
        record.update(
            {
                "status": "verified",
                "independent_audit_report": _repo_relative(report_path),
                "independent_audit_report_hash": _file_hash(report_path),
                "strongest_truthful_status": "local_family_verified",
            }
        )
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _host_build_and_test(
    root: Path,
    build: Path,
    *,
    source: str | None,
    sanitizer: bool,
    run_tests: bool = True,
) -> tuple[int, bool]:
    configure = ["cmake", "-S", str(root), "-B", str(build), "-G", "Unix Makefiles"]
    if source is not None:
        configure.append(f"-DTASK_SOURCE={root}/{source}")
    if sanitizer:
        configure.append("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer")
        configure.append("-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined")
    completed = subprocess.run(
        configure, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if completed.returncode != 0:
        _fail("reference_compile_failed", f"configure {root.name}: {completed.stdout[-4000:]}")
    completed = subprocess.run(
        ["cmake", "--build", str(build), "--parallel", "2"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        _fail("reference_compile_failed", f"build {root.name}: {completed.stdout[-4000:]}")
    if not run_tests:
        return 0, True
    discovery = subprocess.run(
        ["ctest", "--test-dir", str(build), "-N"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    match = re.search(r"Total Tests:\s*(\d+)", discovery.stdout)
    count = int(match.group(1)) if match else -1
    tests = subprocess.run(
        ["ctest", "--test-dir", str(build), "--output-on-failure"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=dict(os.environ, ASAN_OPTIONS="detect_leaks=0"),
    )
    return count, tests.returncode == 0


def _tool_version(command: list[str]) -> str:
    completed = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if completed.returncode != 0:
        _fail("host_prerequisite_missing", f"cannot run: {' '.join(command)}")
    return completed.stdout.splitlines()[0].strip()


def verify_host(out: Path = DEFAULT_OUT) -> None:
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text())
    if manifest["family_tree_hash"] != _tree_hash(out) or manifest["owner_hash"] != _file_hash(
        Path(__file__)
    ):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    compiler = shutil.which("c++")
    if compiler is None or shutil.which("cmake") is None or shutil.which("ctest") is None:
        _fail("host_prerequisite_missing", "cmake, ctest, and c++ are required for host iteration")
    with tempfile.TemporaryDirectory(prefix="regions-mazes-host-") as temporary:
        temp = Path(temporary)
        for case in CASES:
            root = out / case.task_id
            normal_count, normal_pass = _host_build_and_test(
                root, temp / f"{case.task_id}-normal", source=".meta/example.cpp", sanitizer=False
            )
            if normal_count == 0:
                _fail("zero_tests", case.task_id)
            if normal_count != 2:
                _fail("test_discovery_failed", f"{case.task_id}: {normal_count}")
            if not normal_pass:
                _fail("reference_tests_failed", case.task_id)
            sanitizer_count, sanitizer_pass = _host_build_and_test(
                root,
                temp / f"{case.task_id}-sanitizer",
                source=".meta/example.cpp",
                sanitizer=True,
            )
            if sanitizer_count != normal_count:
                _fail("sanitizer_test_count_mismatch", case.task_id)
            if not sanitizer_pass:
                _fail("reference_sanitizer_failed", case.task_id)
            negative_count, negative_pass = _host_build_and_test(
                root,
                temp / f"{case.task_id}-negative",
                source=".meta/negative_false_substitute.cpp",
                sanitizer=False,
            )
            if negative_count != 2:
                _fail("test_discovery_failed", f"{case.task_id} negative: {negative_count}")
            if negative_pass:
                _fail("negative_fixture_not_rejected", case.task_id)
        for name in (
            "domain-identifier-renamed",
            "constants-policy-only",
            "opposite-end-selection",
        ):
            root = out / ".state/adversarial-clone-controls" / name
            _host_build_and_test(
                root,
                temp / f"control-{name}-default",
                source=None,
                sanitizer=False,
                run_tests=False,
            )
            for mode, sanitizer in (("normal", False), ("sanitizer", True)):
                count, passed = _host_build_and_test(
                    root,
                    temp / f"control-{name}-{mode}",
                    source=".meta/example.cpp",
                    sanitizer=sanitizer,
                )
                if count != 2:
                    _fail("test_discovery_failed", f"control {name} {mode}: {count}")
                if not passed:
                    _fail(
                        "reference_sanitizer_failed" if sanitizer else "reference_tests_failed",
                        f"control {name}",
                    )
        receipt = {
            "schema_version": "regions-mazes-host-verify-v1",
            "status": "pass",
            "evidence_class": "host_iteration",
            "locked_oracle": False,
            "network_policy": "not_isolated_host_iteration",
            "compiler": {
                "path": compiler,
                "version": _tool_version(["c++", "--version"]),
                "sha256": _file_hash(Path(compiler)),
            },
            "cmake": _tool_version(["cmake", "--version"]),
            "family_tree_hash": _tree_hash(out),
            "owner_hash": _file_hash(Path(__file__)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "normal_reference_count": 30,
            "sanitizer_reference_count": 30,
            "normal_test_count_per_root": 2,
            "sanitizer_test_count_per_root": 2,
            "negative_fixture_count": 30,
            "control_reference_count": 6,
            "control_default_build_count": 3,
        }
        _write(
            out / ".state/host-verify.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
    manifest = json.loads(manifest_path.read_text())
    manifest["host_verify"] = {
        "status": "pass",
        "receipt": ".state/host-verify.json",
        "evidence_class": "host_iteration",
        "normal_test_count_per_root": 2,
        "sanitizer_test_count_per_root": 2,
        "negative_fixture_count": 30,
        "control_reference_count": 6,
        "control_default_build_count": 3,
    }
    manifest["strongest_local_status"] = (
        "host_iteration_passed_pending_fresh_docker_sanity_and_independent_audit"
    )
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _complete_remedy_records(
        out,
        receipt_name="host-verify.json",
        strongest_status="host_oracle_and_semantic_gates_passed_pending_independent_audit",
    )


def verify_docker(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> None:
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text())
    if manifest["family_tree_hash"] != _tree_hash(out) or manifest["owner_hash"] != _file_hash(
        Path(__file__)
    ):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    with tempfile.TemporaryDirectory(prefix="regions-mazes-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        result = temp / "result"
        result.mkdir()
        archive_hash = _archive(out, archive)
        script = r"""set -Eeuo pipefail
mkdir -p /work /result
tar -xf /input/family.tar -C /work
sha256sum /input/family.tar | awk '{print "archive\t"$1}' > /result/results.tsv
command -v c++ > /result/compiler.path
c++ --version | head -1 > /result/compiler.version
sha256sum "$(command -v c++)" | awk '{print $1}' > /result/compiler.sha256
cmake --version | head -1 > /result/cmake.version
run_one(){
  kind="$1"; id="$2"; mode="$3"; source="$4"; root="/work/${kind}/${id}"
  build="/tmp/${kind}-${id}-${mode}-${source##*/}"; flags=()
  if [ "$mode" = sanitizer ];then flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined");fi
  if ! cmake -S "$root" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$root/$source" "${flags[@]}" >/tmp/config.log 2>&1;then { echo "CONFIG_FAIL $kind $id $mode $source"; tail -160 /tmp/config.log; } >/result/failure.log;return 81;fi
  if ! cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1;then { echo "BUILD_FAIL $kind $id $mode $source"; tail -240 /tmp/build.log; } >/result/failure.log;return 82;fi
  count=$(ctest --test-dir "$build" -N | sed -n 's/^Total Tests: //p');test "$count" = 2
  if [ "$source" = .meta/negative_false_substitute.cpp ];then
    if ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1;then { echo "NEGATIVE_PASSED $kind $id $mode $source"; tail -160 /tmp/test.log; } >/result/failure.log;return 71;fi
  else
    if ! ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1;then { echo "TEST_FAIL $kind $id $mode $source"; tail -240 /tmp/test.log; } >/result/failure.log;return 83;fi
  fi
  printf '%s\t%s\t%s\t%s\n' "$kind" "$id" "$mode" "$source" >>/result/results.tsv
}
run_control_default(){
  id="$1"; root="/work/controls/$id"; build="/tmp/control-${id}-default"
  if ! cmake -S "$root" -B "$build" -G "Unix Makefiles" >/tmp/config.log 2>&1;then { echo "DEFAULT_CONFIG_FAIL controls $id"; tail -160 /tmp/config.log; } >/result/failure.log;return 84;fi
  if ! cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1;then { echo "DEFAULT_BUILD_FAIL controls $id"; tail -240 /tmp/build.log; } >/result/failure.log;return 85;fi
  printf 'control_default\t%s\tnormal\tconfig-editable-source\n' "$id" >>/result/results.tsv
}
for root in /work/tasks/*;do id=${root##*/};run_one tasks "$id" normal .meta/example.cpp;run_one tasks "$id" sanitizer .meta/example.cpp;run_one tasks "$id" normal .meta/negative_false_substitute.cpp;done
for root in /work/controls/*;do id=${root##*/};run_control_default "$id";run_one controls "$id" normal .meta/example.cpp;run_one controls "$id" sanitizer .meta/example.cpp;done
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
        if completed.returncode != 0:
            failure = (
                (result / "failure.log").read_text(errors="ignore")
                if (result / "failure.log").is_file()
                else ""
            )
            _fail("docker_sanity_failed", (failure + completed.stdout + completed.stderr)[-12000:])
        rows = [line.split("\t") for line in (result / "results.tsv").read_text().splitlines()]
        mounted = "sha256:" + rows[0][1]
        if mounted != archive_hash:
            _fail("grader_mount_hash_mismatch", f"{mounted} != {archive_hash}")
        refs = [row for row in rows if row[0] == "tasks" and row[3] == ".meta/example.cpp"]
        negatives = [
            row
            for row in rows
            if row[0] == "tasks" and row[3] == ".meta/negative_false_substitute.cpp"
        ]
        controls = [row for row in rows if row[0] == "controls"]
        control_defaults = [row for row in rows if row[0] == "control_default"]
        if (
            len(refs) != 60
            or len(negatives) != 30
            or len(controls) != 6
            or len(control_defaults) != 3
        ):
            _fail(
                "sanitizer_test_count_mismatch",
                f"refs={len(refs)} negatives={len(negatives)} controls={len(controls)} "
                f"control_defaults={len(control_defaults)}",
            )
        receipt = {
            "schema_version": "regions-mazes-docker-sanity-v1",
            "status": "pass",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "archive_hash": archive_hash,
            "mounted_archive_hash": mounted,
            "family_tree_hash": _tree_hash(out),
            "owner_hash": _file_hash(Path(__file__)),
            "compiler": {
                "path": (result / "compiler.path").read_text().strip(),
                "version": (result / "compiler.version").read_text().strip(),
                "sha256": "sha256:" + (result / "compiler.sha256").read_text().strip(),
            },
            "cmake": (result / "cmake.version").read_text().strip(),
            "normal_reference_count": 30,
            "sanitizer_reference_count": 30,
            "normal_test_count_per_root": 2,
            "sanitizer_test_count_per_root": 2,
            "negative_fixture_count": 30,
            "control_mode_count": 6,
            "control_default_build_count": 3,
        }
        _write(
            out / ".state/docker-sanity.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
    manifest = json.loads(manifest_path.read_text())
    manifest["docker_sanity"] = {
        "status": "pass",
        "receipt": ".state/docker-sanity.json",
        "normal_test_count_per_root": 2,
        "sanitizer_test_count_per_root": 2,
        "negative_fixture_count": 30,
        "control_count": 3,
        "control_default_build_count": 3,
    }
    manifest["strongest_local_status"] = "creator_preflight_passed_pending_independent_audit"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _complete_remedy_records(out)


def _append_cycle(out: Path, status: str) -> None:
    if status == "local_family_verified":
        _promote_remedy_records_after_audit(out)
    state = out / ".state/cycles"
    state.mkdir(parents=True, exist_ok=True)
    number = len(list(state.glob("cycle-*.json"))) + 1
    manifest = (
        json.loads((out / ".state/materialization-manifest.json").read_text())
        if (out / ".state/materialization-manifest.json").is_file()
        else {}
    )
    receipt = (
        json.loads((out / ".state/docker-sanity.json").read_text())
        if (out / ".state/docker-sanity.json").is_file()
        else None
    )
    record = {
        "schema_version": "aider-task-creator-cycle-v1",
        "cycle": number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "family_id": FAMILY_ID,
        "candidate_manifest": ".state/materialization-manifest.json",
        "family_tree_hash": _tree_hash(out),
        "curriculum_hash": _file_hash(CURRICULUM),
        "generator_hash": _file_hash(Path(__file__)),
        "focused_test_hash": _file_hash(TEST_PATH),
        "grader_policy_hash": _sha((SANITY_IMAGE + CMAKE).encode()),
        "retained_root_ids": [case.task_id for case in CASES],
        "replaced_root_ids": [],
        "rejected_root_ids": [],
        "review_root_ids": [],
        "blocked_root_ids": [],
        "manifest_subject_hash": _sha(json.dumps(manifest, sort_keys=True).encode()),
        "docker_receipt": receipt,
    }
    _write(
        state / f"cycle-{number:02d}.json",
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--record-cycle", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core or args.verify_host or args.docker_sanity:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        verify_docker(args.out)
    if args.record_cycle:
        _append_cycle(args.out, "creator_preflight" if args.docker_sanity else "generated")
    print(f"Wrote {len(roots)} regions-and-mazes roots under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
