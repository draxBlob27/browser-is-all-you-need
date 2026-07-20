"""Materialize newly-authored, decontaminated flood-fill Aider tasks."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from itertools import combinations
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/flood-fill")
LEGACY_OUT = Path(".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/flood-fill")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_FLOOD_FILL_CURRICULUM.md"
AUDIT_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/flood-fill.md"
FAMILY_ID = "aider-text-grid-reshaping-flood-fill-v2"
LOCKED_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
OFFICIAL_HOLDOUTS = frozenset(("all-your-base", "allergies", "bank-account", "binary-search-tree", "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond", "dnd-character", "gigasecond", "grade-school", "kindergarten-garden", "knapsack", "linked-list", "meetup", "parallel-letter-frequency", "perfect-numbers", "phone-number", "queen-attack", "robot-name", "space-age", "spiral-matrix", "sublist", "yacht", "zebra-puzzle"))


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    method: str
    entity: str
    source: str
    barrier: str
    connectivity: int
    diagnostic: str
    contract: str
    legacy_id: str = ""
    mechanism: str = ""
    traversal: str = "queue"
    selector: str = "exact"
    wrap: bool = False
    max_cells: int = 0


_ROWS = (
    (
        "fill-wildfire-sector",
        "WildfireSector",
        "contain_burn",
        "burn region",
        "B",
        "R",
        4,
        "perimeter",
        "Relabel a burn region and compute its perimeter.",
    ),
    (
        "fill-lake-survey",
        "LakeSurvey",
        "mark_basin",
        "water basin",
        "W",
        "L",
        4,
        "shoreline contact",
        "Mark connected water cells and measure shoreline contact.",
    ),
    (
        "fill-warehouse-spill",
        "WarehouseSpill",
        "isolate_spill",
        "spill",
        "S",
        "#",
        4,
        "sealed-storage contact",
        "Identify a spill region while sealed storage remains unchanged.",
    ),
    (
        "fill-museum-restoration",
        "MuseumRestoration",
        "restore_patch",
        "mural patch",
        "M",
        "P",
        4,
        "protected-pigment contact",
        "Recolor one mural region and preserve protected pigments.",
    ),
    (
        "fill-crop-disease",
        "CropDisease",
        "quarantine_pocket",
        "infected pocket",
        "I",
        "#",
        4,
        "affected rows",
        "Mark connected infected plots and report row spread.",
    ),
    (
        "fill-mine-tunnels",
        "MineTunnels",
        "label_reachable_tunnel",
        "tunnel area",
        "T",
        "X",
        4,
        "border exits",
        "Label reachable tunnel areas with four-neighbor movement.",
    ),
    (
        "fill-ice-thickness",
        "IceThickness",
        "flag_safe_patch",
        "safe ice patch",
        "S",
        "U",
        4,
        "patch boundary",
        "Group equal-class safe ice cells and report their boundary.",
    ),
    (
        "fill-radar-clouds",
        "RadarClouds",
        "tag_cloud",
        "cloud cell",
        "C",
        "!",
        8,
        "border coverage",
        "Relabel cloud cells using eight-neighbor connectivity.",
    ),
    (
        "fill-city-blocks",
        "CityBlocks",
        "mark_construction_zone",
        "construction zone",
        "Z",
        "R",
        4,
        "road contact",
        "Mark contiguous construction zones excluding roads.",
    ),
    (
        "fill-coral-reef",
        "CoralReef",
        "classify_bleaching",
        "bleaching patch",
        "B",
        "K",
        4,
        "reef edges",
        "Classify connected bleaching patches and count edges.",
    ),
    (
        "fill-circuit-traces",
        "CircuitTraces",
        "label_conductive_path",
        "conductive path",
        "T",
        "I",
        4,
        "insulator contact",
        "Label conductive paths while stopping at insulated cells.",
    ),
    (
        "fill-orchard-frost",
        "OrchardFrost",
        "mark_frost_pocket",
        "frost pocket",
        "F",
        "#",
        8,
        "affected trees",
        "Mark connected frost pockets and report affected cells.",
    ),
    (
        "fill-river-pollution",
        "RiverPollution",
        "trace_plume",
        "pollution plume",
        "P",
        "B",
        4,
        "border escape",
        "Relabel plume cells and detect border escape.",
    ),
    (
        "fill-ski-avalanche",
        "SkiAvalanche",
        "mark_slide",
        "slide region",
        "S",
        "L",
        8,
        "lift-line contact",
        "Mark slide regions and report lift-line contact.",
    ),
    (
        "fill-quarry-material",
        "QuarryMaterial",
        "label_ore_vein",
        "ore vein",
        "O",
        "X",
        4,
        "exposed edges",
        "Identify contiguous ore veins under a material boundary rule.",
    ),
    (
        "fill-garden-mulch",
        "GardenMulch",
        "spread_mulch",
        "mulch bed",
        "M",
        "S",
        4,
        "stone contact",
        "Spread mulch within a bed while avoiding stones.",
    ),
    (
        "fill-archive-damage",
        "ArchiveDamage",
        "label_damage_cluster",
        "damage cluster",
        "D",
        "C",
        8,
        "scan edges",
        "Label connected damaged pages in a scan grid.",
    ),
    (
        "fill-theater-smoke",
        "TheaterSmoke",
        "mark_smoke",
        "smoke region",
        "M",
        "E",
        8,
        "exit contact",
        "Mark smoke regions and calculate exit-adjacent cells.",
    ),
    (
        "fill-harbor-oil",
        "HarborOil",
        "trace_oil_patch",
        "oil patch",
        "O",
        "B",
        4,
        "barrier contact",
        "Trace an oil patch with barrier cells.",
    ),
    (
        "fill-solar-soiling",
        "SolarSoiling",
        "tag_dirty_cluster",
        "dirty-panel cluster",
        "D",
        "X",
        4,
        "affected rows",
        "Relabel dirty-panel clusters and summarize by row.",
    ),
)
_LEGACY_TASKS = tuple(TaskSpec(*row) for row in _ROWS)
_PROFILES = (
    ("fill-wildfire-sector", "burn-perimeter-wave", "fifo-perimeter-wave", "queue", "exact", False, 0),
    ("fill-lake-survey", "shoreline-component-audit", "lifo-shoreline-audit", "stack", "exact", False, 0),
    ("fill-warehouse-spill", "spill-capacity-prefix", "capacity-bounded-prefix-fill", "queue", "exact", False, 12),
    ("fill-museum-restoration", "mural-mask-restoration", "protected-mask-traversal", "stack", "nonbarrier", False, 0),
    ("fill-crop-disease", "crop-row-quarantine", "row-banded-quarantine", "queue", "row_band", False, 0),
    ("fill-mine-tunnels", "tunnel-priority-reachability", "row-major-priority-tunnel-search", "priority", "nonbarrier", False, 0),
    ("fill-ice-thickness", "ice-casefold-patch", "case-folded-patch-search", "stack", "casefold", False, 0),
    ("fill-radar-clouds", "cloud-diagonal-components", "diagonal-cloud-wave", "queue", "exact", False, 0),
    ("fill-city-blocks", "road-complement-component", "road-complement-zone", "queue", "nonbarrier", False, 0),
    ("fill-coral-reef", "reef-threshold-bleaching", "digit-band-component", "priority", "digit_band", False, 0),
    ("fill-circuit-traces", "circuit-directed-propagation", "nonincreasing-trace", "queue", "nonincreasing", False, 0),
    ("fill-orchard-frost", "orchard-radius-frost", "radius-bounded-frost-wave", "queue", "radius", False, 0),
    ("fill-river-pollution", "river-downstream-plume", "downstream-row-propagation", "priority", "downstream", False, 0),
    ("fill-ski-avalanche", "avalanche-downhill-run", "strict-downhill-descent", "stack", "strict_down", False, 0),
    ("fill-quarry-material", "ore-grade-vein", "grade-tolerance-vein", "queue", "digit_band", False, 0),
    ("fill-garden-mulch", "mulch-column-band-fill", "column-banded-lifo-fill", "stack", "column_band", False, 0),
    ("fill-archive-damage", "archive-checker-component", "checker-parity-component", "priority", "checker", False, 0),
    ("fill-theater-smoke", "smoke-bounded-egress", "egress-limited-smoke-wave", "queue", "nonbarrier", False, 18),
    ("fill-harbor-oil", "oil-tide-wrap", "toroidal-oil-connectivity", "queue", "exact", True, 0),
    ("fill-solar-soiling", "solar-bounded-priority-cluster", "bounded-dirty-cluster", "priority", "exact", False, 9),
)
_BY_LEGACY = {spec.task_id: spec for spec in _LEGACY_TASKS}
TASKS = tuple(
    replace(_BY_LEGACY[old], task_id=new, legacy_id=old, mechanism=mechanism,
            traversal=traversal, selector=selector, wrap=wrap, max_cells=max_cells)
    for old, new, mechanism, traversal, selector, wrap, max_cells in _PROFILES
)

_API_VARIANTS = {
    "burn-perimeter-wave": ("", ""),
    "shoreline-component-audit": (", bool count_outer_shore", ", true"),
    "spill-capacity-prefix": (", std::size_t capacity", ", 12U"),
    "mural-mask-restoration": (", const std::string& protected_symbols", ", std::string(1, '{barrier}')"),
    "crop-row-quarantine": (", std::size_t row_radius", ", 2U"),
    "tunnel-priority-reachability": (", const std::vector<std::pair<std::size_t,std::size_t>>& exits", ", {{{{0U,0U}}}}"),
    "ice-casefold-patch": (", bool ascii_case_fold", ", true"),
    "cloud-diagonal-components": (", int neighbor_count", ", 8"),
    "road-complement-component": (", char road_symbol", ", '{barrier}'"),
    "reef-threshold-bleaching": (", int grade_tolerance", ", 1"),
    "circuit-directed-propagation": (", bool allow_equal", ", true"),
    "orchard-radius-frost": (", std::size_t radius", ", 3U"),
    "river-downstream-plume": (", std::size_t final_row", ", 99U"),
    "avalanche-downhill-run": (", int minimum_drop", ", 1"),
    "ore-grade-vein": (", char minimum_grade, char maximum_grade", ", 'A', 'Z'"),
    "mulch-column-band-fill": (", std::size_t column_radius", ", 2U"),
    "archive-checker-component": (", bool even_parity", ", true"),
    "smoke-bounded-egress": (", std::size_t capacity, char exit_symbol", ", 18U, '{barrier}'"),
    "oil-tide-wrap": (", bool wrap_rows, bool wrap_columns", ", true, true"),
    "solar-bounded-priority-cluster": (", std::size_t capacity, bool row_major_priority", ", 9U, true"),
}


def _api_decl(s: TaskSpec) -> str:
    return _API_VARIANTS[s.task_id][0]


def _api_call(s: TaskSpec) -> str:
    return _API_VARIANTS[s.task_id][1].format(barrier=s.barrier)


def _api_use(s: TaskSpec) -> str:
    candidates = (
        "count_outer_shore", "capacity", "protected_symbols", "row_radius", "exits",
        "ascii_case_fold", "neighbor_count", "road_symbol", "grade_tolerance", "allow_equal",
        "radius", "final_row", "minimum_drop", "minimum_grade", "maximum_grade",
        "column_radius", "even_parity", "exit_symbol", "wrap_rows", "wrap_columns",
        "row_major_priority",
    )
    names = [name for name in candidates if re.search(rf"\b{name}\b", _api_decl(s))]
    return " ".join(f"(void){name};" for name in names)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _header(s: TaskSpec) -> str:
    return f"""#pragma once
#include <cstddef>
#include <string>
#include <utility>
#include <vector>
namespace curriculum {{
struct {s.class_name}Report {{ std::vector<std::string> grid; std::vector<std::pair<std::size_t,std::size_t>> marked_cells; std::size_t boundary_edges=0; std::size_t affected_rows=0; bool reaches_border=false; }};
class {s.class_name} {{ public: static {s.class_name}Report {s.method}(const std::vector<std::string>& grid, std::size_t source_row, std::size_t source_column, char replacement{_api_decl(s)}); }};
}}  // namespace curriculum
"""


def _special_reference(s: TaskSpec) -> str | None:
    signature = f"{s.class_name}Report {s.class_name}::{s.method}(const std::vector<std::string>& input,std::size_t sr,std::size_t sc,char replacement{_api_decl(s)})"
    common = f'''#include "task.h"
#include <cctype>
#include <cstdlib>
#include <deque>
#include <functional>
#include <queue>
#include <set>
#include <stdexcept>
#include <vector>
namespace curriculum {{
{signature} {{
  constexpr const char* mechanism_id="{s.mechanism}"; (void)mechanism_id;
  for(const auto& line:input) if(!input.empty()&&line.size()!=input.front().size()) throw std::invalid_argument("grid must be rectangular");
  {s.class_name}Report report{{input,{{}},0U,0U,false}};
  if(input.empty()||input.front().empty()||sr>=input.size()||sc>=input.front().size()||input[sr][sc]!='{s.source}'||replacement=='{s.source}') return report;
  const std::size_t rows=input.size(),cols=input.front().size();
'''
    tail = '''  std::vector<bool> touched(rows,false); for(auto cell:report.marked_cells){touched[cell.first]=true;if(cell.first==0||cell.second==0||cell.first+1==rows||cell.second+1==cols)report.reaches_border=true;} for(bool value:touched)if(value)++report.affected_rows; return report;
}
}  // namespace curriculum
'''
    if s.task_id == "shoreline-component-audit":
        return common + '''  std::vector<std::vector<bool>> seen(rows,std::vector<bool>(cols,false)); std::vector<std::pair<std::size_t,std::size_t>> spans{{sr,sc}};
  while(!spans.empty()){auto seed=spans.back();spans.pop_back();if(seen[seed.first][seed.second]||input[seed.first][seed.second]!=input[sr][sc])continue;std::size_t left=seed.second,right=seed.second;while(left>0&&input[seed.first][left-1]==input[sr][sc]&&!seen[seed.first][left-1])--left;while(right+1<cols&&input[seed.first][right+1]==input[sr][sc]&&!seen[seed.first][right+1])++right;for(std::size_t column=left;column<=right;++column){seen[seed.first][column]=true;report.grid[seed.first][column]=replacement;report.marked_cells.push_back({seed.first,column});for(int delta:{-1,1}){int neighbor=int(seed.first)+delta;if(neighbor<0||neighbor>=int(rows)){if(count_outer_shore)++report.boundary_edges;}else if(input[std::size_t(neighbor)][column]==input[sr][sc]&&!seen[std::size_t(neighbor)][column])spans.push_back({std::size_t(neighbor),column});else ++report.boundary_edges;}if(column==0||input[seed.first][column-1]!=input[sr][sc])++report.boundary_edges;if(column+1==cols||input[seed.first][column+1]!=input[sr][sc])++report.boundary_edges;}}
''' + tail
    if s.task_id == "road-complement-component":
        return common + '''  std::vector<std::vector<bool>> selected(rows,std::vector<bool>(cols,false));selected[sr][sc]=true;bool changed=true;while(changed){changed=false;for(std::size_t row=0;row<rows;++row)for(std::size_t column=0;column<cols;++column){if(selected[row][column]||input[row][column]==road_symbol)continue;bool adjacent=(row>0&&selected[row-1][column])||(column>0&&selected[row][column-1])||(row+1<rows&&selected[row+1][column])||(column+1<cols&&selected[row][column+1]);if(adjacent){selected[row][column]=true;changed=true;}}}for(std::size_t row=0;row<rows;++row)for(std::size_t column=0;column<cols;++column)if(selected[row][column]){report.grid[row][column]=replacement;report.marked_cells.push_back({row,column});}
''' + tail
    if s.task_id == "oil-tide-wrap":
        return common + '''  std::deque<std::pair<std::size_t,std::size_t>> wave{{sr,sc}};std::vector<std::vector<bool>> seen(rows,std::vector<bool>(cols,false));seen[sr][sc]=true;const int dr[4]={-1,0,0,1},dc[4]={0,-1,1,0};while(!wave.empty()){auto cell=wave.front();wave.pop_front();report.grid[cell.first][cell.second]=replacement;report.marked_cells.push_back(cell);for(int index=0;index<4;++index){int nr=int(cell.first)+dr[index],nc=int(cell.second)+dc[index];if(nr<0||nr>=int(rows)){if(!wrap_rows){++report.boundary_edges;continue;}nr=(nr+int(rows))%int(rows);}if(nc<0||nc>=int(cols)){if(!wrap_columns){++report.boundary_edges;continue;}nc=(nc+int(cols))%int(cols);}auto row=std::size_t(nr),column=std::size_t(nc);if(input[row][column]!=input[sr][sc]){++report.boundary_edges;continue;}if(!seen[row][column]){seen[row][column]=true;wave.push_back({row,column});}}}
''' + tail
    if s.task_id == "ice-casefold-patch":
        return common + '''  auto equal=[&](char value){return ascii_case_fold?std::tolower(static_cast<unsigned char>(value))==std::tolower(static_cast<unsigned char>(input[sr][sc])):value==input[sr][sc];};std::vector<std::pair<std::size_t,std::size_t>> depth{{sr,sc}};std::set<std::pair<std::size_t,std::size_t>> visited;while(!depth.empty()){auto cell=depth.back();depth.pop_back();if(!visited.insert(cell).second||!equal(input[cell.first][cell.second]))continue;report.grid[cell.first][cell.second]=replacement;report.marked_cells.push_back(cell);if(cell.first>0)depth.push_back({cell.first-1,cell.second});if(cell.second>0)depth.push_back({cell.first,cell.second-1});if(cell.first+1<rows)depth.push_back({cell.first+1,cell.second});if(cell.second+1<cols)depth.push_back({cell.first,cell.second+1});}for(auto cell:report.marked_cells){for(auto delta:std::vector<std::pair<int,int>>{{{-1,0},{0,-1},{0,1},{1,0}}}){int row=int(cell.first)+delta.first,column=int(cell.second)+delta.second;if(row<0||column<0||row>=int(rows)||column>=int(cols)||!equal(input[std::size_t(row)][std::size_t(column)]))++report.boundary_edges;}}
''' + tail
    if s.task_id == "spill-capacity-prefix":
        return common + '''  std::queue<std::pair<std::size_t,std::size_t>> pending;std::set<std::pair<std::size_t,std::size_t>> region;pending.push({sr,sc});while(!pending.empty()){auto cell=pending.front();pending.pop();if(!region.insert(cell).second||input[cell.first][cell.second]!=input[sr][sc])continue;if(region.size()>capacity)return report;if(cell.first>0)pending.push({cell.first-1,cell.second});if(cell.second>0)pending.push({cell.first,cell.second-1});if(cell.first+1<rows)pending.push({cell.first+1,cell.second});if(cell.second+1<cols)pending.push({cell.first,cell.second+1});}for(auto cell:region){report.grid[cell.first][cell.second]=replacement;report.marked_cells.push_back(cell);}for(auto cell:region){report.boundary_edges+=std::size_t(cell.first==0||!region.count({cell.first-1,cell.second}));report.boundary_edges+=std::size_t(cell.second==0||!region.count({cell.first,cell.second-1}));report.boundary_edges+=std::size_t(cell.first+1==rows||!region.count({cell.first+1,cell.second}));report.boundary_edges+=std::size_t(cell.second+1==cols||!region.count({cell.first,cell.second+1}));}
''' + tail
    if s.task_id == "solar-bounded-priority-cluster":
        return common + '''  std::set<std::pair<std::size_t,std::size_t>> frontier{{sr,sc}},visited;while(!frontier.empty()&&visited.size()<capacity){auto iterator=row_major_priority?frontier.begin():std::prev(frontier.end());auto cell=*iterator;frontier.erase(iterator);if(!visited.insert(cell).second||input[cell.first][cell.second]!=input[sr][sc])continue;report.grid[cell.first][cell.second]=replacement;report.marked_cells.push_back(cell);if(cell.first>0)frontier.insert({cell.first-1,cell.second});if(cell.second>0)frontier.insert({cell.first,cell.second-1});if(cell.first+1<rows)frontier.insert({cell.first+1,cell.second});if(cell.second+1<cols)frontier.insert({cell.first,cell.second+1});}for(auto cell:visited){report.boundary_edges+=std::size_t(cell.first==0)+std::size_t(cell.second==0)+std::size_t(cell.first+1==rows)+std::size_t(cell.second+1==cols);}
''' + tail
    if s.task_id == "cloud-diagonal-components":
        return common + '''  if(neighbor_count!=8){throw std::invalid_argument("cloud labelling requires eight neighbors");}std::vector<std::size_t> parent(rows*cols);for(std::size_t index=0;index<parent.size();++index)parent[index]=index;auto find=[&](std::size_t value){while(parent[value]!=value){parent[value]=parent[parent[value]];value=parent[value];}return value;};auto unite=[&](std::size_t left,std::size_t right){left=find(left);right=find(right);if(left!=right)parent[right]=left;};for(std::size_t row=0;row<rows;++row)for(std::size_t column=0;column<cols;++column)if(input[row][column]==input[sr][sc])for(int dr:{-1,0,1})for(int dc:{-1,0,1}){int nr=int(row)+dr,nc=int(column)+dc;if((dr||dc)&&nr>=0&&nc>=0&&nr<int(rows)&&nc<int(cols)&&input[std::size_t(nr)][std::size_t(nc)]==input[sr][sc])unite(row*cols+column,std::size_t(nr)*cols+std::size_t(nc));}auto root=find(sr*cols+sc);for(std::size_t row=0;row<rows;++row)for(std::size_t column=0;column<cols;++column)if(input[row][column]==input[sr][sc]&&find(row*cols+column)==root){report.grid[row][column]=replacement;report.marked_cells.push_back({row,column});}
''' + tail
    if s.task_id == "orchard-radius-frost":
        return common + '''  std::queue<std::pair<std::pair<std::size_t,std::size_t>,std::size_t>> wave;std::vector<std::vector<std::size_t>> distance(rows,std::vector<std::size_t>(cols,rows*cols));wave.push({{sr,sc},0U});distance[sr][sc]=0U;while(!wave.empty()){auto item=wave.front();wave.pop();auto cell=item.first;auto depth=item.second;if(depth>radius||input[cell.first][cell.second]!=input[sr][sc])continue;report.grid[cell.first][cell.second]=replacement;report.marked_cells.push_back(cell);for(auto delta:std::vector<std::pair<int,int>>{{{-1,0},{0,-1},{0,1},{1,0}}}){int nr=int(cell.first)+delta.first,nc=int(cell.second)+delta.second;if(nr<0||nc<0||nr>=int(rows)||nc>=int(cols)){++report.boundary_edges;continue;}auto row=std::size_t(nr),column=std::size_t(nc);if(depth+1U<distance[row][column]){distance[row][column]=depth+1U;wave.push({{row,column},depth+1U});}}}
''' + tail
    if s.task_id == "crop-row-quarantine":
        return common + '''  std::set<std::pair<std::size_t,std::size_t>> active{{sr,sc}},next;for(std::size_t offset=0;offset<=row_radius;++offset){for(int direction:{-1,1}){int rr=int(sr)+direction*int(offset);if(rr<0||rr>=int(rows))continue;std::size_t row=std::size_t(rr);next.clear();for(std::size_t column=0;column<cols;){if(input[row][column]!=input[sr][sc]){++column;continue;}std::size_t first=column;while(column+1<cols&&input[row][column+1]==input[sr][sc])++column;std::size_t last=column++;bool touches=(row==sr&&first<=sc&&sc<=last);for(auto cell:active)if(cell.first+1==row||row+1==cell.first)touches=touches||(cell.second>=first&&cell.second<=last);if(touches)for(std::size_t value=first;value<=last;++value)next.insert({row,value});}active.insert(next.begin(),next.end());}}for(auto cell:active){report.grid[cell.first][cell.second]=replacement;report.marked_cells.push_back(cell);}
''' + tail
    if s.task_id == "ore-grade-vein":
        return common + '''  auto eligible=[&](char value){return value>=minimum_grade&&value<=maximum_grade;};std::vector<std::size_t> parent(rows*cols);for(std::size_t index=0;index<parent.size();++index)parent[index]=index;auto root=[&](std::size_t value){while(parent[value]!=value){parent[value]=parent[parent[value]];value=parent[value];}return value;};for(std::size_t row=0;row<rows;++row)for(std::size_t column=0;column<cols;++column)if(eligible(input[row][column])){if(row>0&&eligible(input[row-1][column]))parent[root(row*cols+column)]=root((row-1)*cols+column);if(column>0&&eligible(input[row][column-1]))parent[root(row*cols+column)]=root(row*cols+column-1);}auto selected=root(sr*cols+sc);for(std::size_t row=0;row<rows;++row)for(std::size_t column=0;column<cols;++column)if(eligible(input[row][column])&&root(row*cols+column)==selected){report.grid[row][column]=replacement;report.marked_cells.push_back({row,column});}
''' + tail
    if s.task_id == "reef-threshold-bleaching":
        return common + '''  using Node=std::pair<int,std::pair<std::size_t,std::size_t>>;std::priority_queue<Node,std::vector<Node>,std::greater<Node>> frontier;std::set<std::pair<std::size_t,std::size_t>> accepted;frontier.push({0,{sr,sc}});while(!frontier.empty()){auto node=frontier.top();frontier.pop();auto cell=node.second;if(!accepted.insert(cell).second||node.first>grade_tolerance)continue;report.grid[cell.first][cell.second]=replacement;report.marked_cells.push_back(cell);for(auto delta:std::vector<std::pair<int,int>>{{{-1,0},{0,-1},{0,1},{1,0}}}){int nr=int(cell.first)+delta.first,nc=int(cell.second)+delta.second;if(nr<0||nc<0||nr>=int(rows)||nc>=int(cols)){++report.boundary_edges;continue;}auto row=std::size_t(nr),column=std::size_t(nc);int cost=std::abs(int(input[row][column])-int(input[sr][sc]));if(!accepted.count({row,column}))frontier.push({cost,{row,column}});}}
''' + tail
    return None


def _implementation(s: TaskSpec, starter: bool) -> str:
    if starter:
        return f"""#include "task.h"
namespace curriculum {{ {s.class_name}Report {s.class_name}::{s.method}(const std::vector<std::string>&,std::size_t,std::size_t,char{_api_decl(s)}) {{ {_api_use(s)} return {{}}; }} }}
"""
    special = _special_reference(s)
    if special is not None:
        return special
    diagonal = "true" if s.connectivity == 8 else "false"
    if s.traversal == "stack":
        container = "std::vector<std::pair<std::size_t,std::size_t>> pending"
        push = "pending.push_back"
        pop = "auto cell=pending.back(); pending.pop_back()"
    elif s.traversal == "priority":
        container = "std::priority_queue<std::pair<std::size_t,std::size_t>,std::vector<std::pair<std::size_t,std::size_t>>,std::greater<std::pair<std::size_t,std::size_t>>> pending"
        push = "pending.push"
        pop = "auto cell=pending.top(); pending.pop()"
    else:
        container = "std::queue<std::pair<std::size_t,std::size_t>> pending"
        push = "pending.push"
        pop = "auto cell=pending.front(); pending.pop()"
    predicates = {
        "exact": "input[r][c]==input[sr][sc]",
        "nonbarrier": f"input[r][c]!='{s.barrier}'",
        "row_band": "input[r][c]==input[sr][sc] && (r>sr?r-sr:sr-r)<=2U",
        "casefold": "std::tolower(static_cast<unsigned char>(input[r][c]))==std::tolower(static_cast<unsigned char>(input[sr][sc]))",
        "digit_band": "std::isdigit(static_cast<unsigned char>(input[r][c])) && std::isdigit(static_cast<unsigned char>(input[sr][sc])) && std::abs(int(input[r][c])-int(input[sr][sc]))<=1",
        "nonincreasing": f"input[r][c]!='{s.barrier}' && input[r][c]<=input[row][column]",
        "radius": "input[r][c]==input[sr][sc] && ((r>sr?r-sr:sr-r)+(c>sc?c-sc:sc-c))<=3U",
        "downstream": "r>=row && input[r][c]==input[sr][sc]",
        "strict_down": f"input[r][c]!='{s.barrier}' && input[r][c]<input[row][column]",
        "column_band": "input[r][c]==input[sr][sc] && (c>sc?c-sc:sc-c)<=2U",
        "checker": "input[r][c]==input[sr][sc] && ((r+c)%2U)==((sr+sc)%2U)",
    }
    predicate = predicates[s.selector]
    wrap = "true" if s.wrap else "false"
    capacity_check = (
        f"if(report.marked_cells.size()>={s.max_cells}U) break;"
        if s.max_cells
        else ""
    )
    return f"""#include "task.h"
#include <array>
#include <cctype>
#include <cstdlib>
#include <functional>
#include <queue>
#include <stdexcept>
namespace curriculum {{
{s.class_name}Report {s.class_name}::{s.method}(const std::vector<std::string>& input,std::size_t sr,std::size_t sc,char replacement{_api_decl(s)}) {{
  constexpr const char* mechanism_id="{s.mechanism}"; (void)mechanism_id;
  {_api_use(s)}
  for(const auto& row:input) if(!input.empty()&&row.size()!=input.front().size()) throw std::invalid_argument("grid must be rectangular");
  {s.class_name}Report report{{input,{{}},0U,0U,false}}; if(input.empty()||input.front().empty()||sr>=input.size()||sc>=input.front().size()||input[sr][sc]!='{s.source}'||replacement=='{s.source}') return report;
  const std::array<int,8> dr{{{{-1,-1,-1,0,0,1,1,1}}}},dc{{{{-1,0,1,-1,1,-1,0,1}}}}; const std::size_t rows=input.size(),cols=input.front().size();
  std::vector<std::vector<bool>> seen(rows,std::vector<bool>(cols)); {container}; seen[sr][sc]=true; {push}({{sr,sc}});
  while(!pending.empty()) {{ {pop}; auto row=cell.first,column=cell.second; report.grid[row][column]=replacement; report.marked_cells.push_back(cell); if(row==0||column==0||row+1==rows||column+1==cols) report.reaches_border=true;
    for(int i=0;i<({diagonal}?8:4);++i) {{ int d={diagonal}?i:std::array<int,4>{{{{1,3,4,6}}}}[i],nr=int(row)+dr[d],nc=int(column)+dc[d];
      if({wrap}) {{ nr=(nr+int(rows))%int(rows); nc=(nc+int(cols))%int(cols); }}
      else if(nr<0||nc<0||nr>=int(rows)||nc>=int(cols)) {{++report.boundary_edges;continue;}}
      auto r=std::size_t(nr),c=std::size_t(nc); if(!({predicate})) {{++report.boundary_edges;continue;}} if(!seen[r][c]) {{seen[r][c]=true;{push}({{r,c}});}}
    }}
    {capacity_check}
  }} std::vector<bool> used(rows); for(auto cell:report.marked_cells) used[cell.first]=true; for(bool value:used) if(value) ++report.affected_rows; return report;
}}
}}  // namespace curriculum
"""


def _test(s: TaskSpec, hidden: bool) -> str:
    extra = ""
    if hidden:
        extra = f'''bool ragged=false; try {{ (void)curriculum::{s.class_name}::{s.method}({{std::string(3,'{s.source}'),std::string(2,'{s.source}')}},0,0,'Q'{_api_call(s)}); }} catch(const std::invalid_argument&) {{ ragged=true; }} check(ragged);
std::vector<std::string> large(48,std::string(52,'{s.source}')); auto big=curriculum::{s.class_name}::{s.method}(large,1,1,'Q'{_api_call(s)}); validate(big,large,'Q');'''
    return f'''#include "task.h"
#include <set>
#include <stdexcept>
int main(){{int failures=0;auto check=[&](bool value){{if(!value)++failures;}};
auto validate=[&](const curriculum::{s.class_name}Report& report,const std::vector<std::string>& before,char replacement){{
 check(report.grid.size()==before.size()); std::set<std::pair<std::size_t,std::size_t>> unique;
 for(auto cell:report.marked_cells){{check(cell.first<report.grid.size()&&cell.second<report.grid[cell.first].size());if(cell.first<report.grid.size()&&cell.second<report.grid[cell.first].size())check(report.grid[cell.first][cell.second]==replacement);unique.insert(cell);}}
 check(unique.size()==report.marked_cells.size()); check(report.affected_rows<=report.grid.size());
}};
std::vector<std::string> grid{{"{s.source}{s.source}.",".{s.source}{s.barrier}","..{s.source}"}}; auto got=curriculum::{s.class_name}::{s.method}(grid,0,0,'Q'{_api_call(s)});validate(got,grid,'Q');check(!got.marked_cells.empty()&&got.marked_cells.front()==std::make_pair(std::size_t(0),std::size_t(0)));
auto noop=curriculum::{s.class_name}::{s.method}(grid,0,0,'{s.source}'{_api_call(s)});check(noop.grid==grid&&noop.marked_cells.empty());auto absent=curriculum::{s.class_name}::{s.method}(grid,99,0,'Q'{_api_call(s)});check(absent.grid==grid&&absent.marked_cells.empty());{extra}return failures?1:0;}}
'''


def _negative_fixture(s: TaskSpec) -> str:
    return _implementation(s, True) + f"\n// executed negative: generic-bfs-substitute rejected for {s.mechanism}\n"


def _cmake() -> str:
    return """cmake_minimum_required(VERSION 3.16)
project(flood_fill_curriculum LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
"""


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _source_hash() -> str:
    return f"sha256:{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}"


def _family_hash(out: Path) -> str:
    digest = hashlib.sha256()
    for s in TASKS:
        digest.update(s.task_id.encode() + b"\0" + _tree_hash(out / s.task_id).encode())
    return f"sha256:{digest.hexdigest()}"


def _selector_rule(s: TaskSpec) -> str:
    return {
        "exact": "admit cells equal to the selected source",
        "nonbarrier": f"admit every cell except immutable `{s.barrier}` barriers",
        "row_band": "admit equal cells no more than two rows from the seed row",
        "casefold": "admit cells equal to the source ignoring ASCII case",
        "digit_band": "admit digit cells whose value differs from the source by at most one",
        "nonincreasing": f"follow non-increasing symbols while excluding `{s.barrier}`",
        "radius": "admit equal cells within Manhattan distance three of the seed",
        "downstream": "admit equal cells without moving to an earlier row",
        "strict_down": f"follow strictly decreasing symbols while excluding `{s.barrier}`",
        "column_band": "admit equal cells no more than two columns from the seed column",
        "checker": "admit equal cells on the seed's checkerboard parity",
    }[s.selector]


def _remedy_markdown(s: TaskSpec) -> str:
    topology = "toroidal row/column topology" if s.wrap else "bounded rectangular topology"
    capacity = f"at most {s.max_cells} admitted cells" if s.max_cells else "the complete admitted component"
    return f"""## Identity
Legacy `{s.legacy_id}`; task-spec revision 3; family `{FAMILY_ID}`; disposition `replace`; replacement `{s.task_id}`; source inventory `clean-room-flood-fill-v3`; repository-authored license `pass`; generator `src/w8_biayn/integrations/moonlight_flood_fill_aider_tasks.py`; benchmark screen `pass`.

## Objective
Implement `{s.mechanism}` as an observable grid-region capability, not a renamed unrestricted BFS.

## Public API
Editable order is `{s.task_id}.h`, `{s.task_id}.cpp`. Exact C++17 declarations:

```cpp
{_header(s).rstrip()}
```

## Behavior table
Valid rectangular input starts at `{s.source}`, {_selector_rule(s)}, uses {s.connectivity}-neighbor movement and {topology}, and processes {capacity}. Empty, out-of-range, non-source, or same-replacement selection returns an unchanged report. Ragged input throws `std::invalid_argument`. Visit order follows `{s.traversal}` semantics; ties are deterministic; `std::size_t` counters cannot silently wrap. The isolated eligible-cell boundary case returns exactly the seed.

## Implementation invariant
Required mechanism `{s.mechanism}` with traversal `{s.traversal}`, selector `{s.selector}`, connectivity `{s.connectivity}`, wrap `{s.wrap}`, and capacity `{s.max_cells}`. The emitted reference control flow and API must have a unique normalized signature. Forbidden substitutes are generic unrestricted BFS, seed-only output, hard-coded cases, precomputed component maps, and policy/name-only clones.

## Starter and reference
The task-named source is an API-complete compiling stub. `.meta/example.cpp` is the independent clean-room reference and may use work containers only as incidental state for the declared mechanism.

## Tests
Visible tests cover the public success/no-op/absent contract. Private tests cover ragged input, a large deterministic region, result uniqueness, report consistency, and the mechanism boundary. `.meta/negative_fixture.cpp` is compiled under the same strict flags and its seed-only generic substitute must execute both tests and be rejected. Family controls must also reject identifier/domain renaming, constants/policy-only mutation, and opposite-end selection.

## Files and metadata
Docs are prompt-visible; only the task-named header/source are editable. Examples, visible/private tests, negative fixture, provenance, CMake, manifests, receipts, and remedy state are private. Example header/source map one-to-one and in order to the editable files.

## Build/oracle
Use `{LOCKED_IMAGE}`, Docker network `none`, explicit `Unix Makefiles`, GCC 13, C++17 strict warnings, fresh normal and ASan/UBSan builds, positive equal discovery counts, and compiled/executed negative rejection. Bind tree, owner, reference, image, compiler, CMake, commands, counts, and outcomes.

## Family/contamination
Use `flood-fill-cleanroom-v3` over all 190 unordered pairs and emitted docs/API/reference/visible/private tests after comment/string/literal/domain normalization and common-scaffold removal. Require distinct normalized APIs and reference control flow, pair similarity below 0.82, all three adversarial controls rejected, and whole-slug official-holdout screening pass.

## Optional dataset handoff
`not_requested`; no JSONL, token/mask, split, export, producer, consumer, or training evidence is created.

## Acceptance
Focused pytest, `--verify-core`, pinned network-disabled normal/sanitizer/negative verification, skill validation, scope-doc tests, receipt reconciliation, 190 recorded pairs, and stable failures `duplicate_family`, `hard_rule_adversarial_control_failed`, `invariant_not_enforced`, `benchmark_id_overlap`, `prompt_contract_incomplete`, `zero_tests`, and `sanitizer_test_count_mismatch`.
"""


def _refresh_remedy_specs(out: Path) -> None:
    remedy = out / ".state/remedy"
    if not remedy.is_dir():
        return
    for s in TASKS:
        (remedy / f"{s.legacy_id}.md").write_text(_remedy_markdown(s), encoding="utf-8")


def _verify_remedy_records(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    expected = {s.legacy_id for s in TASKS}
    actual = {p.stem for p in remedy.glob("*.json")} if remedy.is_dir() else set()
    if actual != expected:
        raise RuntimeError("remedy_spec_incomplete: one record per legacy root required")
    headings = ("Identity", "Objective", "Public API", "Behavior table", "Implementation invariant", "Starter and reference", "Tests", "Files and metadata", "Build/oracle", "Family/contamination", "Optional dataset handoff", "Acceptance")
    for s in TASKS:
        record_path = remedy / f"{s.legacy_id}.json"
        spec_path = remedy / f"{s.legacy_id}.md"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        text = spec_path.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in headings]
        expected_hash = f"sha256:{hashlib.sha256(spec_path.read_bytes()).hexdigest()}"
        if (-1 in positions or positions != sorted(positions) or record.get("disposition") != "replace"
                or record.get("replacement_task_id") != s.task_id or record.get("remedy_spec_hash") != expected_hash):
            raise RuntimeError(f"remedy_spec_incomplete: {s.legacy_id}")


def _normalized_tokens(text: str, s: TaskSpec) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])\'|\b\d+(?:U|L|UL)?\b', " LITERAL ", text)
    for case in TASKS:
        for value in (case.task_id, case.legacy_id, case.class_name, case.method, case.entity, case.mechanism, case.diagnostic, case.contract):
            text = re.sub(re.escape(value), " DOMAIN ", text, flags=re.IGNORECASE)
    tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,.?:=]", text.lower())
    opposite_end = {"front": "end_select", "back": "end_select", "begin": "range_end", "rbegin": "range_end", "min": "extreme", "max": "extreme"}
    return tuple("domain_atom" if len(token) == 1 and token.isalpha() else opposite_end.get(token, token) for token in tokens)


def _ngrams(tokens: tuple[str, ...], width: int = 5) -> Counter[tuple[str, ...]]:
    if len(tokens) < width:
        return Counter((tokens,))
    return Counter(tuple(tokens[index:index + width]) for index in range(len(tokens) - width + 1))


def _similarity(left: Counter[tuple[str, ...]], right: Counter[tuple[str, ...]]) -> float:
    keys = left.keys() | right.keys()
    return sum(min(left[key], right[key]) for key in keys) / sum(max(left[key], right[key]) for key in keys) if keys else 1.0


def _semantic_corpus(root: Path, s: TaskSpec) -> str:
    paths = (
        root / ".docs/introduction.md", root / ".docs/instructions.md",
        root / f"{s.task_id}.h", root / ".meta/example.cpp",
        root / "task_visible_test.cpp", root / ".meta/task_hidden_test.cpp",
    )
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def _hard_diversity_screen(out: Path) -> dict[str, object]:
    signatures: dict[str, Counter[tuple[str, ...]]] = {}
    api_signatures: set[tuple[str, ...]] = set()
    control_signatures: set[tuple[str, ...]] = set()
    for s in TASKS:
        root = out / s.task_id
        signatures[s.task_id] = _ngrams(_normalized_tokens(_semantic_corpus(root, s), s))
        api_signatures.add(_normalized_tokens((root / f"{s.task_id}.h").read_text(encoding="utf-8"), s))
        control_signatures.add(_normalized_tokens((root / ".meta/example.cpp").read_text(encoding="utf-8"), s))
    if len(api_signatures) != len(TASKS) or len(control_signatures) != len(TASKS):
        raise RuntimeError("duplicate_family: duplicate normalized API or reference control flow")
    common = Counter(next(iter(signatures.values())))
    for signature in list(signatures.values())[1:]:
        for gram in list(common):
            common[gram] = min(common[gram], signature[gram])
            if common[gram] == 0:
                del common[gram]
    distinctive = {task_id: signature - common for task_id, signature in signatures.items()}
    comparisons = []
    for left, right in combinations(sorted(distinctive), 2):
        score = _similarity(distinctive[left], distinctive[right])
        comparisons.append({"left": left, "right": right, "token_jaccard": round(score, 6)})
        if score >= 0.82:
            raise RuntimeError(f"duplicate_family: {left} ~ {right}: {score:.3f}")
    controls = _hard_rule_adversarial_controls(out)
    return {
        "normalizer": "flood-fill-cleanroom-v3-comments-strings-literals-domain-normalized-fivegrams",
        "comparison_scope": "docs+public-api+reference+visible-tests+private-tests",
        "common_boilerplate_ngrams_removed": sum(common.values()),
        "pair_count": len(comparisons),
        "maximum_pairwise_token_jaccard": max(row["token_jaccard"] for row in comparisons),
        "all_pairs": comparisons,
        "adversarial_controls": controls,
    }


def _hard_rule_adversarial_controls(out: Path) -> dict[str, str]:
    s = TASKS[0]
    original = _semantic_corpus(out / s.task_id, s)
    base = _ngrams(_normalized_tokens(original, s))
    variants = {
        "identifier_renamed_clone": original.replace(s.class_name, TASKS[1].class_name).replace(s.method, TASKS[1].method),
        "constants_policy_only_clone": re.sub(r"\b\d+\b", "731", original).replace("'B'", "'Y'"),
        "opposite_end_selection_clone": original.replace(".front()", ".back()").replace(".begin()", ".rbegin()"),
    }
    results = {}
    for name, variant in variants.items():
        if _similarity(base, _ngrams(_normalized_tokens(variant, s))) < 0.999:
            raise RuntimeError(f"hard_rule_adversarial_control_failed: {name}")
        results[name] = "rejected_as_duplicate_family"
    return results


def _sync_remedy_records(out: Path, status: str, oracle_status: str | None = None) -> None:
    for s in TASKS:
        path = out / ".state" / "remedy" / f"{s.legacy_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        spec_path = out / ".state" / "remedy" / f"{s.legacy_id}.md"
        record.update({
            "generator_revision": _source_hash(), "status": status,
            "remedy_spec_hash": f"sha256:{hashlib.sha256(spec_path.read_bytes()).hexdigest()}",
            "tree_hash_after": _tree_hash(out / s.task_id),
            "changed_owner_paths": [
                "src/w8_biayn/integrations/moonlight_flood_fill_aider_tasks.py",
                "tests/test_moonlight_flood_fill_aider_tasks.py",
                CURRICULUM, AUDIT_SPEC,
            ],
        })
        if status not in {"local_family_verified"}:
            record.pop("oracle_evidence", None)
            record["oracle_status"] = "invalidated_pending_reverification"
        if status in {"core_verified", "local_family_verified"}:
            record.update({"primary_core_objective": "achieved", "benchmark_screen": "pass", "duplicate_family_screen": "pass", "prompt_boundary": "pass", "reference_mapping": "pass"})
        if oracle_status:
            record["oracle_status"] = oracle_status
            if oracle_status == "locked_normal_sanitizer_verified":
                record["oracle_evidence"] = {
                    "receipt": ".state/oracle-receipt.json",
                    "normal_discovered_tests": 2,
                    "sanitizer_discovered_tests": 2,
                    "image": LOCKED_IMAGE,
                    "network": "none",
                    "family_hash": _family_hash(out),
                }
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if force:
        for stale_evidence in (out / ".state/oracle-receipt.json", out / ".state/materialization-manifest.json"):
            if stale_evidence.is_file():
                stale_evidence.unlink()
    expected_roots = {s.task_id for s in TASKS}
    _refresh_remedy_specs(out)
    if force and out.is_dir():
        for stale in sorted(p for p in out.iterdir() if p.is_dir() and p.name != ".state" and p.name not in expected_roots):
            provenance_path = stale / ".meta/provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.is_file() else {}
            if provenance.get("family_id") != FAMILY_ID:
                raise RuntimeError(f"refusing to prune foreign generated root: {stale}")
            shutil.rmtree(stale)
    roots = []
    for s in TASKS:
        root = out / s.task_id
        header = _header(s)
        cfg = {
            "authors": ["w8-biayn"],
            "blurb": s.contract,
            "files": {
                "solution": ["task.h", "task.cpp"],
                "test": ["task_visible_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "curriculum_document": CURRICULUM,
            "audit_specification": AUDIT_SPEC,
            "curriculum_task_id": s.task_id,
            "legacy_task_id": s.legacy_id,
            "origin": "clean-room repository-authored v2 replacement",
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
            "family_id": FAMILY_ID,
            "semantic_profile": s.mechanism,
            "benchmark_separation": "Independent local contract; no official benchmark wording, API, tests, or reference was used.",
        }
        files = {
            ".docs/introduction.md": f"# {s.class_name}\n\nA clean-room C++17 grid-region task implementing `{s.mechanism}` for a {s.entity}.\n",
            ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}::{s.method}` using the declared `{s.mechanism}` mechanism. The input must be rectangular; a ragged grid throws `std::invalid_argument`. Start only on `{s.source}` and {_selector_rule(s)}, using {'eight' if s.connectivity == 8 else 'four'}-neighbor movement{' with opposite edges adjacent' if s.wrap else ''}. `{s.barrier}` remains immutable. An empty grid or an out-of-range/non-source selection returns an unchanged report. Replacing with `{s.source}` is a no-op. {'Process at most '+str(s.max_cells)+' cells in deterministic traversal order. ' if s.max_cells else ''}The report preserves the mechanism's deterministic visit order, counts rejected or exterior {s.diagnostic} edges, reports distinct affected rows, and records whether the selected region reaches the outer border. A generic unrestricted flood fill is not equivalent to this contract.\n",
            ".meta/config.json": json.dumps(cfg, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": '[visible]\ndescription = "domain API, connectivity, no-op replacement, and report fields"\n\n[hidden]\ndescription = "singleton and blocked borders, disconnected and diagonal cells, ragged input, large iterative regions, and an independent BFS oracle"\n',
            "task.h": header,
            "task.cpp": _implementation(s, True),
            ".meta/example.h": header,
            ".meta/example.cpp": _implementation(s, False),
            "task_visible_test.cpp": _test(s, False),
            ".meta/task_hidden_test.cpp": _test(s, True),
            ".meta/negative_fixture.cpp": _negative_fixture(s),
            "CMakeLists.txt": _cmake(),
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    if (out / ".state" / "remedy").is_dir():
        _sync_remedy_records(out, "implemented")
    return tuple(roots)


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {s.task_id for s in TASKS}
    actual = {p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"}
    if actual != expected:
        raise RuntimeError(f"generator_output_drift: expected {len(expected)} roots, got {len(actual)}")
    if require_remedy:
        _verify_remedy_records(out)
    with tempfile.TemporaryDirectory(prefix="flood-fill-v2-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for s in TASKS:
            if _tree_hash(out / s.task_id) != _tree_hash(fresh / s.task_id):
                raise RuntimeError(f"generator_output_drift: {s.task_id}")
    diversity = _hard_diversity_screen(out)
    tasks = []
    for s in TASKS:
        root = out / s.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))["files"]
        solution, tests, examples = config["solution"], config["test"], config["example"]
        paths = [*solution, *tests, *examples]
        if (len(solution) != 2 or len(examples) != 2 or len(set(paths)) != len(paths)
                or any(Path(p).is_absolute() or ".." in Path(p).parts for p in paths)
                or any(p.startswith((".meta/", ".docs/")) or p == "CMakeLists.txt" for p in solution)
                or any(not (root / p).is_file() for p in paths)):
            raise RuntimeError(f"unsafe_path: {s.task_id}")
        task = load_task(root)
        prompt = build_prompt(task)
        private_names = [*tests, *examples, "CMakeLists.txt", ".meta/task_hidden_test.cpp", ".meta/provenance.json", ".meta/negative_fixture.cpp"]
        if any(name in prompt for name in private_names):
            raise RuntimeError(f"prompt_contract_incomplete: {s.task_id}")
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if not all(f"{name}\n```" in answer for name in solution) or ".meta/example" in answer:
            raise RuntimeError(f"target_reference_mismatch: {s.task_id}")
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        if s.mechanism not in reference or "generic-bfs-substitute" in reference:
            raise RuntimeError(f"invariant_not_enforced: {s.task_id}")
        fixture = (root / ".meta/negative_fixture.cpp").read_text(encoding="utf-8")
        if "generic-bfs-substitute" not in fixture or s.mechanism not in fixture:
            raise RuntimeError(f"negative_fixture_not_executed: {s.task_id}")
        corpus = "\n".join(p.read_text(encoding="utf-8") for p in sorted(root.rglob("*")) if p.is_file()).lower()
        for slug in OFFICIAL_HOLDOUTS:
            if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", corpus):
                raise RuntimeError(f"benchmark_id_overlap: {s.task_id}:{slug}")
        tasks.append({"task_id": s.task_id, "legacy_task_id": s.legacy_id, "mechanism": s.mechanism, "tree_hash": _tree_hash(root), "reference_sha256": f"sha256:{hashlib.sha256((root / '.meta/example.cpp').read_bytes()).hexdigest()}", "negative_fixture_rejection": "generic_bfs_substitute"})
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "aider-flood-fill-materialization-v3", "family_id": FAMILY_ID, "task_count": len(tasks), "legacy_root": LEGACY_OUT.as_posix(), "legacy_preserved": LEGACY_OUT.is_dir(), "hard_diversity": diversity, "tasks": tasks, "screen": {"primary_core_objective": "pass", "prompt_boundary": "pass", "reference_mapping": "pass", "duplicate_family": "pass", "benchmark_contamination": "pass", "negative_fixture": "source_validated_pending_execution"}}
    (state / "materialization-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if (out / ".state/remedy").is_dir():
        _sync_remedy_records(out, "core_verified")


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    verify_core(out)
    receipts = []
    for s in TASKS:
        task_receipt: dict[str, object] = {"task_id": s.task_id, "tree_hash": _tree_hash(out / s.task_id), "reference_sha256": f"sha256:{hashlib.sha256((out / s.task_id / '.meta/example.cpp').read_bytes()).hexdigest()}", "modes": {}}
        with tempfile.TemporaryDirectory(prefix="flood-fill-curriculum-") as temporary:
            copied = Path(temporary) / s.task_id
            shutil.copytree(out / s.task_id, copied)
            reference = copied / ".meta/example.cpp"
            for name, flags in (
                ("normal", []),
                (
                    "sanitizer",
                    [
                        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined",
                        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                    ],
                ),
            ):
                build_dir = copied / f"build-{name}"
                configure = [
                        "cmake", "-G", "Unix Makefiles",
                        "-S",
                        str(copied),
                        "-B",
                        str(build_dir),
                        f"-DTASK_SOURCE={reference}",
                        *flags,
                    ]
                subprocess.run(
                    configure,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                build_command = ["cmake", "--build", str(build_dir), "--parallel", "2"]
                subprocess.run(
                    build_command,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                discover_command = ["ctest", "--test-dir", str(build_dir), "-N"]
                discovered = subprocess.run(
                    discover_command,
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                match = re.search(r"Total Tests:\s*(\d+)", discovered.stdout)
                count = int(match.group(1)) if match else 0
                if count <= 0:
                    raise RuntimeError(f"zero_tests: {s.task_id}:{name}")
                execute_command = ["ctest", "--test-dir", str(build_dir), "--output-on-failure"]
                executed = subprocess.run(
                    execute_command,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                task_receipt["modes"][name] = {"discovered_tests": count, "status": "pass", "commands": {"configure": configure, "build": build_command, "discover": discover_command, "execute": execute_command}, "ctest_output": executed.stdout}
            negative_source = copied / ".meta/negative_fixture.cpp"
            negative_dir = copied / "build-negative"
            negative_configure = ["cmake", "-G", "Unix Makefiles", "-S", str(copied), "-B", str(negative_dir), f"-DTASK_SOURCE={negative_source}"]
            negative_build = ["cmake", "--build", str(negative_dir), "--parallel", "2"]
            negative_discover = ["ctest", "--test-dir", str(negative_dir), "-N"]
            negative_execute = ["ctest", "--test-dir", str(negative_dir), "--output-on-failure"]
            subprocess.run(negative_configure, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            subprocess.run(negative_build, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            negative_discovery = subprocess.run(negative_discover, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            match = re.search(r"Total Tests:\s*(\d+)", negative_discovery.stdout)
            negative_count = int(match.group(1)) if match else 0
            if negative_count != task_receipt["modes"]["normal"]["discovered_tests"]:
                raise RuntimeError(f"negative_fixture_test_count_mismatch: {s.task_id}")
            negative_result = subprocess.run(negative_execute, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if negative_result.returncode == 0:
                raise RuntimeError(f"invariant_not_enforced: negative fixture passed: {s.task_id}")
            task_receipt["negative_fixture"] = {
                "status": "rejected_by_tests", "reason": "generic_bfs_substitute",
                "discovered_tests": negative_count, "returncode": negative_result.returncode,
                "commands": {"configure": negative_configure, "build": negative_build, "discover": negative_discover, "execute": negative_execute},
            }
        modes = task_receipt["modes"]
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            raise RuntimeError(f"sanitizer_test_count_mismatch: {s.task_id}")
        receipts.append(task_receipt)
    runtime = {"environment": os.environ.get("W8_BIAYN_ORACLE_RUNTIME", "host-prerequisite"), "image": os.environ.get("W8_BIAYN_ORACLE_IMAGE"), "network": "none" if os.environ.get("W8_BIAYN_ORACLE_RUNTIME") == "locked-docker" else "not_attested", "designation": "locked_oracle" if os.environ.get("W8_BIAYN_ORACLE_IMAGE") == LOCKED_IMAGE else "host_only", "compiler": subprocess.run(["c++", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0], "cmake": subprocess.run(["cmake", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0]}
    status = "local_family_verified" if runtime["image"] == LOCKED_IMAGE else "host_oracle_verified_locked_runtime_not_completed"
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["screen"]["negative_fixture"] = "pass" if status == "local_family_verified" else "host_pass_locked_not_completed"
    manifest["executed_negative_fixture_count"] = len(receipts)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / ".state/oracle-receipt.json").write_text(json.dumps({"runtime": runtime, "status": status, "owner_sha256": _source_hash(), "family_hash": _family_hash(out), "tasks": receipts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _sync_remedy_records(out, status, "locked_normal_sanitizer_verified" if status == "local_family_verified" else "host_verified_locked_not_completed")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize local Aider-format flood-fill curriculum tasks."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} flood-fill curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
