"""Own and verify the 25-root coordinate-transformations expansion family."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
DEFAULT_OUT = EXPANSION_ROOT / "text-grid/coordinate-transformations"
LEGACY_ROOTS = (
    REPO_ROOT / ".w8-biayn/data/aider-tasks",
    REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify",
)
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
CURRICULUM = REPO_ROOT / "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_COORDINATE_TRANSFORMATIONS_EXPANSION_CURRICULUM.md"
FAMILY_SPEC = REPO_ROOT / "docs/aider-tasks-spec/aider-text-grid-reshaping/coordinate-transformations-expansion.md"
FOCUSED_TEST = REPO_ROOT / "tests/test_moonlight_coordinate_transformations_aider_tasks.py"
OWNER = "src/w8_biayn/integrations/moonlight_coordinate_transformations_aider_tasks.py"
FAMILY_ID = "coordinate-transformations-expansion-v1"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
SANITY_IMAGE_ID = "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
IMAGE_COMPILER = "/usr/local/bin/g++"
COMPILER_ENV = "W8_COORDINATE_CXX"
GRADER_ENV = "W8_COORDINATE_GRADER"
NORMALIZER = "coordinate-transform-artifact-shingles-v1"
SELECTED_PROMPTS = (
    "docs/aider-tasks-spec/prompts/generate-family-spec.md",
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
)
DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
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
CYCLE_01_AUDIT_RELATIVE = Path("docs/aider-tasks-spec/audits/coordinate-transformations-cycle-01.md")
CYCLE_01_SUBJECT = "sha256:54932ece5c9b1810b278540e5784173851ed7f8d0797c501fc514a4a2b19d62b"
CYCLE_01_FINDINGS = {
    "CT-AUD-001": {
        "disposition": "regenerate-and-reverify",
        "affected_task_ids": [],
        "remedy": "reinventory every generated tree, bind the current corpus, and rerun all collision and contamination screens",
    },
    "CT-AUD-002": {
        "disposition": "replace-and-reverify",
        "affected_task_ids": ["coord-morton-interleave", "coord-hex-ring-address"],
        "remedy": "replace the Morton representation variant with axial hex shell rank/unrank and add representation-width semantic alias regression coverage",
    },
    "CT-AUD-003": {
        "disposition": "repair-and-reverify",
        "affected_task_ids": ["coord-quarter-pose"],
        "remedy": "normalize headings before addition or inverse construction and exercise INT_MIN and INT_MAX under sanitizers",
    },
    "CT-AUD-004": {
        "disposition": "repair-and-reverify",
        "affected_task_ids": ["coord-voxel-axis-map"],
        "remedy": "range-check signed axis codes before absolute-value conversion and test INT_MIN",
    },
    "CT-AUD-005": {
        "disposition": "repair-and-reverify",
        "affected_task_ids": ["coord-cubemap-edge-step"],
        "remedy": "validate face and heading enumerators before basis or movement dispatch and test invalid casts",
    },
    "CT-AUD-006": {
        "disposition": "repair-and-reverify",
        "affected_task_ids": ["coord-polyline-frame"],
        "remedy": "return exact segment endpoints without narrowing unsigned distance and use checked coordinate addition",
    },
}
CYCLE_02_AUDIT_RELATIVE = Path("docs/aider-tasks-spec/audits/coordinate-transformations-cycle-02.md")
CYCLE_02_SUBJECT = "sha256:20263dbc7b439dfb944721fd4e691a97b9b04890af35a0a432c04b9258d97c04"
CYCLE_02_FINDINGS = {
    "CT-AUD-001": {
        "disposition": "regenerate-and-reverify",
        "affected_task_ids": [],
        "remedy": "rebind the final live inventory and repeat every external screen after concurrent expansion replacement activity stabilizes",
    },
    "CT-AUD-007": {
        "disposition": "replace-and-reverify",
        "affected_task_ids": ["coord-quadtree-path", "coord-reflective-boundary-fold"],
        "remedy": "replace paired-bit quadtree digit encoding with a periodic reflective boundary fold and add a Morton/quadtree cross-alias control",
    },
}
CYCLE_03_AUDIT_RELATIVE = Path("docs/aider-tasks-spec/audits/coordinate-transformations-cycle-03.md")
CYCLE_03_SUBJECT = "sha256:14f68d665e9c1a8c09c2a73a540acc49668b10f1eeea3b82636e6aa3609b1066"
CYCLE_03_FINDINGS = {
    "CT-AUD-001": {
        "disposition": "regenerate-and-reverify",
        "affected_task_ids": [],
        "remedy": "rebind the final live comparison inventory after concurrent foreign-family replacement activity",
    },
    "CT-AUD-008": {
        "disposition": "repair-and-reverify",
        "affected_task_ids": ["coord-polyline-frame"],
        "remedy": "validate and retain every segment length and tangent before selecting an early sample; test diagonal and zero-length suffixes",
    },
}
CYCLE_04_AUDIT_RELATIVE = Path("docs/aider-tasks-spec/audits/coordinate-transformations-cycle-04.md")
CYCLE_04_SUBJECT = "sha256:566f9fcf3ca93f7724aa064a03e329a888dcfb82e7bfb691829ba59728296671"
CYCLE_04_FINDINGS: dict[str, dict[str, object]] = {}
CYCLE_04_INVALIDATION_REASON = (
    "the live foreign expansion inventory changed after the cycle-04 report was "
    "recorded, invalidating that otherwise-passing report under its final inventory gate"
)
MECHANISM_ALIAS_GROUPS = (
    (("morton", "interleav"), ("quadtree", "quadrant", "path"), ("paired", "bit", "base-four")),
    (("hilbert", "quadrant", "reflect"),),
    (("barycentric", "weight", "denominator"),),
    (("cubemap", "face", "edge"),),
)
CROSS_ALIAS_CONTROL = {
    "control_id": "morton-quadtree-paired-bit-digit-relabel",
    "left": "Morton radix conversion interleaves paired x and y bits into base-four quadrant digits at a fixed width.",
    "right": "Quadtree quadrant path encodes top-down paired coordinate bits as digits zero through three at a dynamic depth.",
    "expected_marker": ["morton", "interleav"],
    "expected_decision": "duplicate_family",
}


class CreatorError(RuntimeError):
    """A fail-closed creator, oracle, or audit-input gate failed."""


def _fail(code: str, detail: str = "") -> None:
    raise CreatorError(f"{code}:{detail}" if detail else code)


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    mechanism: str
    header: str
    starter: str
    reference: str
    negative: str
    visible: str
    private: str
    invalid_rule: str
    tie_rule: str
    negative_reason: str


def _case(
    task_id: str,
    title: str,
    mechanism: str,
    header: str,
    starter: str,
    reference: str,
    negative: str,
    visible: str,
    private: str,
    invalid_rule: str,
    tie_rule: str,
    negative_reason: str,
) -> Case:
    return Case(task_id, title, mechanism, header.strip() + "\n", starter.strip() + "\n", reference.strip() + "\n", negative.strip() + "\n", visible.strip() + "\n", private.strip() + "\n", invalid_rule, tie_rule, negative_reason)


def _cases() -> tuple[Case, ...]:
    c: list[Case] = []
    c.append(_case(
        "coord-affine-lattice", "Checked affine lattice mapping", "six-coefficient checked multiply/add",
        r'''struct Point{long long x;long long y;}; struct Affine{long long a;long long b;long long c;long long d;long long tx;long long ty;}; std::optional<Point> apply_affine(Point point,Affine map);''',
        r'''std::optional<Point> apply_affine(Point,Affine){return std::nullopt;}''',
        r'''namespace{bool mul(long long a,long long b,long long&o){return !__builtin_mul_overflow(a,b,&o);}bool add(long long a,long long b,long long&o){return !__builtin_add_overflow(a,b,&o);}std::optional<long long> row(long long a,long long x,long long b,long long y,long long t){long long p=0,q=0,s=0,r=0;if(!mul(a,x,p)||!mul(b,y,q)||!add(p,q,s)||!add(s,t,r))return std::nullopt;return r;}} std::optional<Point> apply_affine(Point p,Affine m){auto x=row(m.a,p.x,m.b,p.y,m.tx);auto y=row(m.c,p.x,m.d,p.y,m.ty);if(!x||!y)return std::nullopt;return Point{*x,*y};}''',
        r'''std::optional<Point> apply_affine(Point p,Affine m){using U=unsigned long long;return Point{static_cast<long long>(U(m.a)*U(p.x)+U(m.b)*U(p.y)+U(m.tx)),static_cast<long long>(U(m.c)*U(p.x)+U(m.d)*U(p.y)+U(m.ty))};}''',
        r'''auto r=apply_affine({2,-1},{2,1,-1,3,4,5});if(!r||r->x!=7||r->y!=0)return 1;return 0;''',
        r'''auto a=apply_affine({-3,4},{0,-2,5,0,1,-7});if(!a||a->x!=-7||a->y!=-22)return 1;if(apply_affine({std::numeric_limits<long long>::max(),1},{2,0,0,1,0,0}))return 2;auto z=apply_affine({0,0},{0,0,0,0,std::numeric_limits<long long>::min(),std::numeric_limits<long long>::max()});if(!z||z->x!=std::numeric_limits<long long>::min()||z->y!=std::numeric_limits<long long>::max())return 3;return 0;''',
        "overflow rejects the complete mapping", "signed zero and extrema are preserved", "unchecked wraparound reports a value instead of failure",
    ))
    c.append(_case(
        "coord-hex-cube-turn", "Axial hex cube rotation", "axial-to-cube invariant and repeated sixty-degree rotation",
        r'''struct Axial{long long q;long long r;}; std::optional<Axial> rotate_hex(Axial cell,long long clockwise_turns);''',
        r'''std::optional<Axial> rotate_hex(Axial,long long){return std::nullopt;}''',
        r'''std::optional<Axial> rotate_hex(Axial p,long long turns){long long y=0;if(__builtin_add_overflow(p.q,p.r,&y)||y==std::numeric_limits<long long>::min())return std::nullopt;y=-y;long long x=p.q,z=p.r;int n=static_cast<int>((turns%6+6)%6);for(int i=0;i<n;++i){if(x==std::numeric_limits<long long>::min()||y==std::numeric_limits<long long>::min()||z==std::numeric_limits<long long>::min())return std::nullopt;long long nx=-y,ny=-z,nz=-x;x=nx;y=ny;z=nz;}return Axial{x,z};}''',
        r'''std::optional<Axial> rotate_hex(Axial p,long long turns){int n=static_cast<int>((turns%4+4)%4);while(n-->0){long long x=p.q;p.q=-p.r;p.r=x;}return p;}''',
        r'''auto r=rotate_hex({2,-1},1);if(!r||r->q!=1||r->r!=-2)return 1;return 0;''',
        r'''auto p=Axial{3,-2};auto r=rotate_hex(p,6);if(!r||r->q!=p.q||r->r!=p.r)return 1;auto n=rotate_hex(p,-1);auto f=rotate_hex(*n,1);if(!f||f->q!=p.q||f->r!=p.r)return 2;if(rotate_hex({std::numeric_limits<long long>::max(),1},0))return 3;return 0;''',
        "an unrepresentable cube component rejects", "turn count uses Euclidean modulo six", "square-grid quarter rotation breaks the cube orbit",
    ))
    c.append(_case(
        "coord-triangle-barycentric", "Exact triangle barycentric mapping", "determinant-aware checked weighted numerator evaluation",
        r'''struct Point{long long x;long long y;}; struct Weights{long long a;long long b;long long c;long long denominator;}; std::optional<Point> barycentric_point(Point p0,Point p1,Point p2,Weights weights);''',
        r'''std::optional<Point> barycentric_point(Point,Point,Point,Weights){return std::nullopt;}''',
        r'''namespace{bool term(long long a,long long b,long long c,long long d,long long e,long long f,long long&o){long long p=0,q=0,r=0,s=0;if(__builtin_mul_overflow(a,b,&p)||__builtin_mul_overflow(c,d,&q)||__builtin_mul_overflow(e,f,&r)||__builtin_add_overflow(p,q,&s)||__builtin_add_overflow(s,r,&o))return false;return true;}} std::optional<Point> barycentric_point(Point p0,Point p1,Point p2,Weights w){if(w.denominator<=0||w.a<0||w.b<0||w.c<0)return std::nullopt;long long sum=0,t=0;if(__builtin_add_overflow(w.a,w.b,&t)||__builtin_add_overflow(t,w.c,&sum)||sum!=w.denominator)return std::nullopt;long long ux=0,uy=0,vx=0,vy=0,cross=0;if(__builtin_sub_overflow(p1.x,p0.x,&ux)||__builtin_sub_overflow(p1.y,p0.y,&uy)||__builtin_sub_overflow(p2.x,p0.x,&vx)||__builtin_sub_overflow(p2.y,p0.y,&vy)||__builtin_mul_overflow(ux,vy,&t)||__builtin_mul_overflow(uy,vx,&cross)||__builtin_sub_overflow(t,cross,&cross)||cross==0)return std::nullopt;long long x=0,y=0;if(!term(w.a,p0.x,w.b,p1.x,w.c,p2.x,x)||!term(w.a,p0.y,w.b,p1.y,w.c,p2.y,y)||x%w.denominator||y%w.denominator)return std::nullopt;return Point{x/w.denominator,y/w.denominator};}''',
        r'''std::optional<Point> barycentric_point(Point p0,Point p1,Point p2,Weights){return Point{(p0.x+p1.x+p2.x)/3,(p0.y+p1.y+p2.y)/3};}''',
        r'''auto r=barycentric_point({0,0},{6,0},{0,6},{1,1,1,3});if(!r||r->x!=2||r->y!=2)return 1;return 0;''',
        r'''if(barycentric_point({0,0},{2,0},{4,0},{1,1,0,2}))return 1;if(barycentric_point({0,0},{3,0},{0,3},{1,1,1,2}))return 2;if(barycentric_point({0,0},{1,0},{0,1},{1,1,0,2}))return 3;auto v=barycentric_point({0,0},{8,0},{0,8},{0,3,1,4});if(!v||v->x!=6||v->y!=2)return 4;return 0;''',
        "reject degenerate triangles, invalid weights, overflow, and fractional lattice results", "weights are applied in vertex order", "vertex averaging ignores both weights and exact divisibility",
    ))
    c.append(_case(
        "coord-viewport-letterbox", "Aspect-preserving viewport placement", "rational limiting-axis comparison and centered padding",
        r'''struct Size{long long width;long long height;}; struct Point{long long x;long long y;}; struct Placement{Point pixel;long long scaled_width;long long scaled_height;long long pad_left;long long pad_top;}; std::optional<Placement> letterbox_point(Size source,Size viewport,Point source_pixel);''',
        r'''std::optional<Placement> letterbox_point(Size,Size,Point){return std::nullopt;}''',
        r'''std::optional<Placement> letterbox_point(Size s,Size v,Point p){if(s.width<=0||s.height<=0||v.width<=0||v.height<=0||p.x<0||p.y<0||p.x>=s.width||p.y>=s.height)return std::nullopt;long long lhs=0,rhs=0;if(__builtin_mul_overflow(v.width,s.height,&lhs)||__builtin_mul_overflow(v.height,s.width,&rhs))return std::nullopt;long long sw=0,sh=0,px=0,py=0;if(lhs<=rhs){sw=v.width;if(__builtin_mul_overflow(s.height,v.width,&sh))return std::nullopt;sh/=s.width;if(__builtin_mul_overflow(p.x,v.width,&px)||__builtin_mul_overflow(p.y,v.width,&py))return std::nullopt;px/=s.width;py/=s.width;}else{sh=v.height;if(__builtin_mul_overflow(s.width,v.height,&sw))return std::nullopt;sw/=s.height;if(__builtin_mul_overflow(p.x,v.height,&px)||__builtin_mul_overflow(p.y,v.height,&py))return std::nullopt;px/=s.height;py/=s.height;}long long left=(v.width-sw)/2,top=(v.height-sh)/2;return Placement{{left+px,top+py},sw,sh,left,top};}''',
        r'''std::optional<Placement> letterbox_point(Size s,Size v,Point p){if(s.width<=0||s.height<=0)return std::nullopt;return Placement{{p.x*v.width/s.width,p.y*v.height/s.height},v.width,v.height,0,0};}''',
        r'''auto r=letterbox_point({4,2},{8,8},{3,1});if(!r||r->pixel.x!=6||r->pixel.y!=4||r->scaled_width!=8||r->scaled_height!=4||r->pad_top!=2)return 1;return 0;''',
        r'''if(letterbox_point({0,2},{8,8},{0,0}))return 1;if(letterbox_point({4,2},{8,8},{4,0}))return 2;auto r=letterbox_point({2,4},{9,6},{1,3});if(!r||r->scaled_width!=3||r->scaled_height!=6||r->pad_left!=3||r->pixel.x!=4||r->pixel.y!=4)return 3;return 0;''',
        "all dimensions are positive and the source point is in bounds", "floor scale and floor left/top padding own odd spare pixels", "independent axis scaling destroys aspect ratio",
    ))
    c.append(_case(
        "coord-tile-pyramid-address", "Signed world-cell tile addressing", "Euclidean floor division with horizontal tile wrapping",
        r'''struct Cell{long long x;long long y;}; struct TileAddress{long long tile_x;long long tile_y;long long local_x;long long local_y;}; std::optional<TileAddress> tile_address(Cell world,long long extent,long long horizontal_tiles);''',
        r'''std::optional<TileAddress> tile_address(Cell,long long,long long){return std::nullopt;}''',
        r'''namespace{long long floor_div(long long a,long long b){long long q=a/b,r=a%b;if(r<0)--q;return q;}long long mod(long long a,long long b){long long r=a%b;return r<0?r+b:r;}} std::optional<TileAddress> tile_address(Cell p,long long e,long long count){if(e<=0||count<=0)return std::nullopt;long long tx=floor_div(p.x,e),ty=floor_div(p.y,e);long long lx=mod(p.x,e),ly=mod(p.y,e);return TileAddress{mod(tx,count),ty,lx,ly};}''',
        r'''std::optional<TileAddress> tile_address(Cell p,long long e,long long count){if(e<=0||count<=0)return std::nullopt;return TileAddress{(p.x/e)%count,p.y/e,p.x%e,p.y%e};}''',
        r'''auto r=tile_address({-1,-9},8,4);if(!r||r->tile_x!=3||r->tile_y!=-2||r->local_x!=7||r->local_y!=7)return 1;return 0;''',
        r'''if(tile_address({0,0},0,4))return 1;auto a=tile_address({32,8},8,4);if(!a||a->tile_x!=0||a->tile_y!=1||a->local_x!=0||a->local_y!=0)return 2;auto b=tile_address({-33,0},8,4);if(!b||b->tile_x!=3||b->local_x!=7)return 3;return 0;''',
        "extent and horizontal tile count must be positive", "tile x wraps after mathematical floor division", "truncating C++ division produces negative local cells",
    ))
    c.append(_case(
        "coord-hex-ring-address", "Axial hex ring addressing", "six-direction axial shell rank and inverse",
        r'''struct HexCell{long long q;long long r;}; std::optional<unsigned long long> hex_ring_index(unsigned radius,HexCell cell); std::optional<HexCell> hex_ring_cell(unsigned radius,unsigned long long index);''',
        r'''std::optional<unsigned long long> hex_ring_index(unsigned,HexCell){return std::nullopt;} std::optional<HexCell> hex_ring_cell(unsigned,unsigned long long){return std::nullopt;}''',
        r'''namespace{constexpr unsigned LIMIT=1000000U;unsigned long long through(unsigned k){return 1ULL+3ULL*k*(k+1ULL);}unsigned long long start(unsigned k){return 1ULL+3ULL*(k-1ULL)*k;}} std::optional<unsigned long long> hex_ring_index(unsigned radius,HexCell c){if(radius>LIMIT||c.q < -static_cast<long long>(radius)||c.q>static_cast<long long>(radius)||c.r < -static_cast<long long>(radius)||c.r>static_cast<long long>(radius))return std::nullopt;long long s=-c.q-c.r;if(s < -static_cast<long long>(radius)||s>static_cast<long long>(radius))return std::nullopt;unsigned k=static_cast<unsigned>(std::max({std::llabs(c.q),std::llabs(c.r),std::llabs(s)}));if(k==0)return 0ULL;unsigned long long offset=0;if(c.r==static_cast<long long>(k)&&c.q<0)offset=static_cast<unsigned long long>(c.q+static_cast<long long>(k));else if(c.q>=0&&c.q<static_cast<long long>(k)&&c.q+c.r==static_cast<long long>(k))offset=k+static_cast<unsigned long long>(c.q);else if(c.q==static_cast<long long>(k)&&c.r<=0&&c.r>-static_cast<long long>(k))offset=2ULL*k+static_cast<unsigned long long>(-c.r);else if(c.r==-static_cast<long long>(k)&&c.q>0)offset=3ULL*k+static_cast<unsigned long long>(static_cast<long long>(k)-c.q);else if(c.q<=0&&c.q>-static_cast<long long>(k)&&c.q+c.r==-static_cast<long long>(k))offset=4ULL*k+static_cast<unsigned long long>(-c.q);else if(c.q==-static_cast<long long>(k)&&c.r>=0)offset=5ULL*k+static_cast<unsigned long long>(c.r);else return std::nullopt;return start(k)+offset;} std::optional<HexCell> hex_ring_cell(unsigned radius,unsigned long long index){if(radius>LIMIT||index>=through(radius))return std::nullopt;if(index==0)return HexCell{0,0};unsigned lo=1,hi=radius;while(lo<hi){unsigned mid=lo+(hi-lo)/2;if(through(mid)>index)hi=mid;else lo=mid+1;}unsigned k=lo;unsigned long long offset=index-start(k),side=offset/k,t=offset%k;long long n=static_cast<long long>(k),u=static_cast<long long>(t);switch(side){case 0:return HexCell{-n+u,n};case 1:return HexCell{u,n-u};case 2:return HexCell{n,-u};case 3:return HexCell{n-u,-n};case 4:return HexCell{-u,-n+u};case 5:return HexCell{-n,u};default:return std::nullopt;}}''',
        r'''std::optional<unsigned long long> hex_ring_index(unsigned radius,HexCell c){long long width=2LL*radius+1;return static_cast<unsigned long long>((c.r+radius)*width+(c.q+radius));} std::optional<HexCell> hex_ring_cell(unsigned radius,unsigned long long index){long long width=2LL*radius+1;return HexCell{static_cast<long long>(index%width)-radius,static_cast<long long>(index/width)-radius};}''',
        r'''auto i=hex_ring_index(2,{-2,1});if(!i||*i!=18)return 1;auto c=hex_ring_cell(2,*i);if(!c||c->q!=-2||c->r!=1)return 2;return 0;''',
        r'''if(hex_ring_index(2,{2,2})||hex_ring_cell(2,19)||hex_ring_index(1000001U,{0,0}))return 1;for(unsigned radius=0;radius<=12;++radius){unsigned long long count=1ULL+3ULL*radius*(radius+1ULL);for(unsigned long long i=0;i<count;++i){auto c=hex_ring_cell(radius,i);auto j=c?hex_ring_index(radius,*c):std::nullopt;if(!j||*j!=i)return 2;}}auto a=hex_ring_cell(1,1);auto b=hex_ring_cell(1,6);if(!a||!b||a->q!=-1||a->r!=1||b->q!=-1||b->r!=0)return 3;return 0;''',
        "radius is at most one million, the cell lies inside that axial hexagon, and the index is below the enclosed-cell count", "ring zero is the center; each later ring starts at southwest and follows the declared six axial sides", "bounding-square row-major rank includes cells outside the hex shell order",
    ))
    c.append(_case(
        "coord-hilbert-index", "Hilbert square-grid indexing", "iterative quadrant rotation and reflection",
        r'''struct Cell{std::uint32_t x;std::uint32_t y;}; std::optional<std::uint64_t> hilbert_index(unsigned order,Cell cell); std::optional<Cell> hilbert_cell(unsigned order,std::uint64_t index);''',
        r'''std::optional<std::uint64_t> hilbert_index(unsigned,Cell){return std::nullopt;} std::optional<Cell> hilbert_cell(unsigned,std::uint64_t){return std::nullopt;}''',
        r'''namespace{void rot(std::uint32_t n,std::uint32_t&x,std::uint32_t&y,std::uint32_t rx,std::uint32_t ry){if(ry==0){if(rx==1){x=n-1-x;y=n-1-y;}std::swap(x,y);}}} std::optional<std::uint64_t> hilbert_index(unsigned order,Cell p){if(order<1||order>10)return std::nullopt;std::uint32_t n=1U<<order;if(p.x>=n||p.y>=n)return std::nullopt;std::uint32_t x=p.x,y=p.y;std::uint64_t d=0;for(std::uint32_t s=n/2;s>0;s/=2){std::uint32_t rx=(x&s)?1U:0U,ry=(y&s)?1U:0U;d+=std::uint64_t(s)*s*((3U*rx)^ry);rot(s,x,y,rx,ry);}return d;} std::optional<Cell> hilbert_cell(unsigned order,std::uint64_t d){if(order<1||order>10)return std::nullopt;std::uint32_t n=1U<<order;std::uint64_t cap=std::uint64_t(n)*n;if(d>=cap)return std::nullopt;std::uint32_t x=0,y=0;std::uint64_t t=d;for(std::uint32_t s=1;s<n;s*=2){std::uint32_t rx=std::uint32_t((t/2U)&1U),ry=std::uint32_t((t^rx)&1U);rot(s,x,y,rx,ry);x+=s*rx;y+=s*ry;t/=4U;}return Cell{x,y};}''',
        r'''std::optional<std::uint64_t> hilbert_index(unsigned order,Cell p){if(order<1||order>10)return std::nullopt;std::uint32_t n=1U<<order;if(p.x>=n||p.y>=n)return std::nullopt;return std::uint64_t(p.y)*n+p.x;} std::optional<Cell> hilbert_cell(unsigned order,std::uint64_t d){if(order<1||order>10)return std::nullopt;std::uint32_t n=1U<<order;if(d>=std::uint64_t(n)*n)return std::nullopt;return Cell{std::uint32_t(d%n),std::uint32_t(d/n)};}''',
        r'''auto a=hilbert_index(2,{0,0});auto b=hilbert_index(2,{1,0});if(!a||!b||*a!=0||*b!=1)return 1;return 0;''',
        r'''if(hilbert_index(0,{0,0})||hilbert_cell(11,0))return 1;for(unsigned o=1;o<=5;++o){std::uint32_t n=1U<<o;for(std::uint32_t y=0;y<n;++y)for(std::uint32_t x=0;x<n;++x){auto d=hilbert_index(o,{x,y});if(!d)return 2;auto p=hilbert_cell(o,*d);if(!p||p->x!=x||p->y!=y)return 3;}}auto p=hilbert_cell(2,15);if(!p||p->x!=3||p->y!=0)return 4;return 0;''',
        "orders and coordinates/distances outside the finite square reject", "quadrant orientation follows the standard lower-left Hilbert entry", "row-major rank has the wrong locality and endpoint",
    ))
    c.append(_case(
        "coord-utm-zone-band", "Geographic zone and latitude-band classification", "half-open partition with Norway and Svalbard exceptions",
        r'''struct GeoFix{long long latitude_microdegrees;long long longitude_microdegrees;}; struct ZoneBand{int zone;char band;}; std::optional<ZoneBand> classify_zone_band(GeoFix fix);''',
        r'''std::optional<ZoneBand> classify_zone_band(GeoFix){return std::nullopt;}''',
        r'''std::optional<ZoneBand> classify_zone_band(GeoFix f){constexpr long long D=1000000;if(f.latitude_microdegrees<-80*D||f.latitude_microdegrees>=84*D||f.longitude_microdegrees<-180*D||f.longitude_microdegrees>180*D)return std::nullopt;long long lon=f.longitude_microdegrees==180*D?180*D-1:f.longitude_microdegrees;int zone=int((lon+180*D)/(6*D))+1;long long lat=f.latitude_microdegrees;if(lat>=56*D&&lat<64*D&&lon>=3*D&&lon<12*D)zone=32;if(lat>=72*D&&lat<84*D){if(lon>=0&&lon<9*D)zone=31;else if(lon<21*D&&lon>=9*D)zone=33;else if(lon<33*D&&lon>=21*D)zone=35;else if(lon<42*D&&lon>=33*D)zone=37;}const std::string bands="CDEFGHJKLMNPQRSTUVWX";int index=int((lat+80*D)/(8*D));if(index>=int(bands.size()))index=int(bands.size())-1;return ZoneBand{zone,bands[std::size_t(index)]};}''',
        r'''std::optional<ZoneBand> classify_zone_band(GeoFix f){constexpr long long D=1000000;if(f.latitude_microdegrees<-80*D||f.latitude_microdegrees>=84*D)return std::nullopt;int zone=int((f.longitude_microdegrees+180*D)/(6*D))+1;return ZoneBand{zone,'N'};}''',
        r'''auto r=classify_zone_band({60'000'000,6'000'000});if(!r||r->zone!=32||r->band!='V')return 1;return 0;''',
        r'''if(classify_zone_band({84'000'000,0})||classify_zone_band({0,180'000'001}))return 1;auto edge=classify_zone_band({0,180'000'000});if(!edge||edge->zone!=60||edge->band!='N')return 2;auto polar=classify_zone_band({76'000'000,20'000'000});if(!polar||polar->zone!=33||polar->band!='X')return 3;return 0;''',
        "latitude and longitude must lie in the documented half-open geographic domain", "zone boundaries are half-open and +180 maps to zone sixty", "uniform six-degree division misses named high-latitude exceptions",
    ))
    c.append(_case(
        "coord-quarter-pose", "Integer quarter-turn pose algebra", "semidirect-product pose composition and exact inverse",
        r'''struct Point{long long x;long long y;}; struct Pose{Point translation;int quarter_turns;}; std::optional<Point> apply_pose(Pose pose,Point local); std::optional<Pose> compose_pose(Pose parent,Pose child); std::optional<Pose> inverse_pose(Pose pose);''',
        r'''std::optional<Point> apply_pose(Pose,Point){return std::nullopt;} std::optional<Pose> compose_pose(Pose,Pose){return std::nullopt;} std::optional<Pose> inverse_pose(Pose){return std::nullopt;}''',
        r'''namespace{int norm(int q){return (q%4+4)%4;}std::optional<Point> turn(Point p,int q){q=norm(q);for(int i=0;i<q;++i){if(p.y==std::numeric_limits<long long>::min())return std::nullopt;long long x=p.x;p.x=-p.y;p.y=x;}return p;}std::optional<Point> plus(Point a,Point b){Point r{};if(__builtin_add_overflow(a.x,b.x,&r.x)||__builtin_add_overflow(a.y,b.y,&r.y))return std::nullopt;return r;}} std::optional<Point> apply_pose(Pose p,Point x){auto r=turn(x,p.quarter_turns);return r?plus(p.translation,*r):std::nullopt;} std::optional<Pose> compose_pose(Pose a,Pose b){auto t=turn(b.translation,a.quarter_turns);auto sum=t?plus(a.translation,*t):std::nullopt;if(!sum)return std::nullopt;return Pose{*sum,norm(norm(a.quarter_turns)+norm(b.quarter_turns))};} std::optional<Pose> inverse_pose(Pose p){if(p.translation.x==std::numeric_limits<long long>::min()||p.translation.y==std::numeric_limits<long long>::min())return std::nullopt;int heading=(4-norm(p.quarter_turns))%4;auto t=turn({-p.translation.x,-p.translation.y},heading);return t?std::optional<Pose>(Pose{*t,heading}):std::nullopt;}''',
        r'''std::optional<Point> apply_pose(Pose p,Point x){return Point{p.translation.x+x.x,p.translation.y+x.y};} std::optional<Pose> compose_pose(Pose a,Pose b){return Pose{{a.translation.x+b.translation.x,a.translation.y+b.translation.y},(a.quarter_turns+b.quarter_turns)%4};} std::optional<Pose> inverse_pose(Pose p){return Pose{{-p.translation.x,-p.translation.y},-p.quarter_turns};}''',
        r'''auto r=apply_pose({{10,5},1},{2,3});if(!r||r->x!=7||r->y!=7)return 1;return 0;''',
        r'''Pose a{{4,-2},1},b{{3,1},3};auto c=compose_pose(a,b);if(!c||c->translation.x!=3||c->translation.y!=1||c->quarter_turns!=0)return 1;auto inv=inverse_pose(a);auto origin=inv?apply_pose(*inv,*apply_pose(a,{7,9})):std::nullopt;if(!origin||origin->x!=7||origin->y!=9)return 2;if(inverse_pose({{std::numeric_limits<long long>::min(),0},0}))return 3;auto e=compose_pose({{0,0},std::numeric_limits<int>::max()},{{0,0},1});if(!e||e->quarter_turns!=0)return 4;auto m=inverse_pose({{0,0},std::numeric_limits<int>::min()});if(!m||m->quarter_turns!=0)return 5;return 0;''',
        "overflow or unrepresentable negation rejects", "headings use Euclidean modulo four and parent orientation acts first", "translation-only composition ignores child-frame rotation",
    ))
    c.append(_case(
        "coord-isometric-diamond", "Exact isometric diamond projection", "sum/difference projection with parity-checked inverse",
        r'''struct Tile{long long column;long long row;}; struct Diamond{long long x;long long y;}; std::optional<Diamond> project_diamond(Tile tile,long long half_width,long long half_height); std::optional<Tile> unproject_diamond(Diamond point,long long half_width,long long half_height);''',
        r'''std::optional<Diamond> project_diamond(Tile,long long,long long){return std::nullopt;} std::optional<Tile> unproject_diamond(Diamond,long long,long long){return std::nullopt;}''',
        r'''std::optional<Diamond> project_diamond(Tile t,long long w,long long h){if(w<=0||h<=0)return std::nullopt;long long d=0,s=0,x=0,y=0;if(__builtin_sub_overflow(t.column,t.row,&d)||__builtin_add_overflow(t.column,t.row,&s)||__builtin_mul_overflow(d,w,&x)||__builtin_mul_overflow(s,h,&y))return std::nullopt;return Diamond{x,y};} std::optional<Tile> unproject_diamond(Diamond p,long long w,long long h){if(w<=0||h<=0||p.x%w||p.y%h)return std::nullopt;long long d=p.x/w,s=p.y/h,a=0,b=0;if(__builtin_add_overflow(s,d,&a)||__builtin_sub_overflow(s,d,&b)||a%2||b%2)return std::nullopt;return Tile{a/2,b/2};}''',
        r'''std::optional<Diamond> project_diamond(Tile t,long long w,long long h){return Diamond{(t.column-t.row)*w,(t.column+t.row)*h};} std::optional<Tile> unproject_diamond(Diamond p,long long w,long long h){if(w<=0||h<=0)return std::nullopt;long long d=p.x/w,s=p.y/h;return Tile{(s+d)/2,(s-d)/2};}''',
        r'''auto p=project_diamond({3,1},4,2);if(!p||p->x!=8||p->y!=8)return 1;auto t=unproject_diamond(*p,4,2);if(!t||t->column!=3||t->row!=1)return 2;return 0;''',
        r'''if(project_diamond({0,0},0,2)||unproject_diamond({1,0},4,2)||unproject_diamond({4,0},4,2))return 1;for(long long x=-3;x<=3;++x)for(long long y=-3;y<=3;++y){auto p=project_diamond({x,y},3,5);auto t=p?unproject_diamond(*p,3,5):std::nullopt;if(!t||t->column!=x||t->row!=y)return 2;}return 0;''',
        "positive half scales and exact inverse divisibility/parity are required", "signed tiles round-trip without truncation", "integer division silently accepts off-lattice diamonds",
    ))
    c.append(_case(
        "coord-projective-rational", "Checked rational projective point", "homogeneous checked dot products and gcd normalization",
        r'''struct Point{long long x;long long y;}; struct Matrix3{std::array<long long,9> value;}; struct RationalPoint{long long x_num;long long y_num;long long denominator;}; std::optional<RationalPoint> projective_point(Matrix3 matrix,Point point);''',
        r'''std::optional<RationalPoint> projective_point(Matrix3,Point){return std::nullopt;}''',
        r'''namespace{bool row(const std::array<long long,9>&m,int k,Point p,long long&o){long long a=0,b=0,s=0;if(__builtin_mul_overflow(m[std::size_t(k)],p.x,&a)||__builtin_mul_overflow(m[std::size_t(k+1)],p.y,&b)||__builtin_add_overflow(a,b,&s)||__builtin_add_overflow(s,m[std::size_t(k+2)],&o))return false;return true;}unsigned long long mag(long long x){return x<0?0ULL-static_cast<unsigned long long>(x):static_cast<unsigned long long>(x);}} std::optional<RationalPoint> projective_point(Matrix3 m,Point p){long long x=0,y=0,w=0;if(!row(m.value,0,p,x)||!row(m.value,3,p,y)||!row(m.value,6,p,w)||w==0)return std::nullopt;unsigned long long g=std::gcd(std::gcd(mag(x),mag(y)),mag(w));if(g>1){x/=static_cast<long long>(g);y/=static_cast<long long>(g);w/=static_cast<long long>(g);}if(w<0){if(x==std::numeric_limits<long long>::min()||y==std::numeric_limits<long long>::min()||w==std::numeric_limits<long long>::min())return std::nullopt;x=-x;y=-y;w=-w;}return RationalPoint{x,y,w};}''',
        r'''std::optional<RationalPoint> projective_point(Matrix3 m,Point p){long long x=m.value[0]*p.x+m.value[1]*p.y+m.value[2];long long y=m.value[3]*p.x+m.value[4]*p.y+m.value[5];return RationalPoint{x,y,1};}''',
        r'''Matrix3 m{{2,0,0,0,2,0,0,0,4}};auto r=projective_point(m,{3,-1});if(!r||r->x_num!=3||r->y_num!=-1||r->denominator!=2)return 1;return 0;''',
        r'''Matrix3 zero{{1,0,0,0,1,0,0,0,0}};if(projective_point(zero,{1,2}))return 1;Matrix3 neg{{1,0,0,0,1,0,0,0,-2}};auto r=projective_point(neg,{4,6});if(!r||r->x_num!=-2||r->y_num!=-3||r->denominator!=1)return 2;Matrix3 huge{{std::numeric_limits<long long>::max(),0,0,0,1,0,0,0,1}};if(projective_point(huge,{2,0}))return 3;return 0;''',
        "zero homogeneous denominator, checked overflow, and unnormalizable signs reject", "divide all three terms by their common gcd and make denominator positive", "dropping the homogeneous denominator changes the mapped point",
    ))
    c.append(_case(
        "coord-octant-ring", "Chebyshev ring and clockwise octant", "integer magnitude comparison with axis precedence",
        r'''struct Point{long long x;long long y;}; struct RingSector{unsigned long long ring;int octant;}; std::optional<RingSector> locate_ring_sector(Point point);''',
        r'''std::optional<RingSector> locate_ring_sector(Point){return std::nullopt;}''',
        r'''namespace{unsigned long long mag(long long v){return v<0?0ULL-static_cast<unsigned long long>(v):static_cast<unsigned long long>(v);}} std::optional<RingSector> locate_ring_sector(Point p){auto ax=mag(p.x),ay=mag(p.y);unsigned long long ring=std::max(ax,ay);if(ring==0)return RingSector{0,-1};int oct=0;if(p.x>0&&p.y>=0)oct=ax>=ay?0:1;else if(p.x<=0&&p.y>0)oct=ay>=ax?2:3;else if(p.x<0&&p.y<=0)oct=ax>=ay?4:5;else oct=ay>=ax?6:7;return RingSector{ring,oct};}''',
        r'''std::optional<RingSector> locate_ring_sector(Point p){double a=std::atan2(double(p.y),double(p.x));int o=int(std::floor((a+3.141592653589793)*4.0/3.141592653589793));return RingSector{static_cast<unsigned long long>(std::max(std::llabs(p.x),std::llabs(p.y))),o%8};}''',
        r'''auto r=locate_ring_sector({5,2});if(!r||r->ring!=5||r->octant!=0)return 1;return 0;''',
        r'''auto o=locate_ring_sector({0,0});if(!o||o->ring!=0||o->octant!=-1)return 1;std::vector<std::pair<Point,int>> v={{{1,1},0},{{1,2},1},{{0,2},2},{{-2,1},3},{{-2,0},4},{{-1,-2},5},{{0,-2},6},{{2,-1},7}};for(auto e:v){auto r=locate_ring_sector(e.first);if(!r||r->octant!=e.second)return 2;}auto m=locate_ring_sector({std::numeric_limits<long long>::min(),0});if(!m||m->ring!=(1ULL<<63)||m->octant!=4)return 3;return 0;''',
        "every signed integer point is valid including LLONG_MIN", "axis and diagonal boundaries use explicit clockwise precedence", "floating angle binning misclassifies exact boundary rays",
    ))
    c.append(_case(
        "coord-cubemap-edge-step", "Oriented cube-face edge stepping", "face-local three-dimensional basis remapping",
        r'''enum class Face{front,right,back,left,top,bottom}; enum class Heading{east,south,west,north}; struct FaceCell{Face face;int row;int column;Heading heading;}; std::optional<FaceCell> step_cube(FaceCell cell,int size);''',
        r'''std::optional<FaceCell> step_cube(FaceCell,int){return std::nullopt;}''',
        r'''namespace{struct V{int x,y,z;};V neg(V a){return {-a.x,-a.y,-a.z};}bool eq(V a,V b){return a.x==b.x&&a.y==b.y&&a.z==b.z;}bool valid(Face f){return f==Face::front||f==Face::right||f==Face::back||f==Face::left||f==Face::top||f==Face::bottom;}bool valid(Heading h){return h==Heading::east||h==Heading::south||h==Heading::west||h==Heading::north;}struct B{V n,u,v;};B basis(Face f){switch(f){case Face::front:return {{0,0,1},{1,0,0},{0,1,0}};case Face::right:return {{1,0,0},{0,0,-1},{0,1,0}};case Face::back:return {{0,0,-1},{-1,0,0},{0,1,0}};case Face::left:return {{-1,0,0},{0,0,1},{0,1,0}};case Face::top:return {{0,-1,0},{1,0,0},{0,0,1}};case Face::bottom:return {{0,1,0},{1,0,0},{0,0,-1}};}return {};}Face face_for(V n){for(Face f:{Face::front,Face::right,Face::back,Face::left,Face::top,Face::bottom})if(eq(basis(f).n,n))return f;return Face::front;}} std::optional<FaceCell> step_cube(FaceCell c,int size){if(!valid(c.face)||!valid(c.heading)||size<=0||c.row<0||c.column<0||c.row>=size||c.column>=size)return std::nullopt;int dr=0,dc=0;switch(c.heading){case Heading::east:dc=1;break;case Heading::south:dr=1;break;case Heading::west:dc=-1;break;case Heading::north:dr=-1;break;}int nr=c.row+dr,nc=c.column+dc;if(nr>=0&&nr<size&&nc>=0&&nc<size)return FaceCell{c.face,nr,nc,c.heading};B old=basis(c.face);V move=dc==1?old.u:dc==-1?neg(old.u):dr==1?old.v:neg(old.v);Face nf=face_for(move);B nb=basis(nf);V forward=neg(old.n);Heading h=Heading::east;if(eq(forward,nb.v))h=Heading::south;else if(eq(forward,neg(nb.u)))h=Heading::west;else if(eq(forward,neg(nb.v)))h=Heading::north;int offset=(dc!=0)?c.row:c.column;int rr=0,cc=0;if(h==Heading::east){rr=offset;cc=0;}else if(h==Heading::west){rr=offset;cc=size-1;}else if(h==Heading::south){rr=0;cc=offset;}else{rr=size-1;cc=offset;}return FaceCell{nf,rr,cc,h};}''',
        r'''std::optional<FaceCell> step_cube(FaceCell c,int size){if(size<=0)return std::nullopt;switch(c.heading){case Heading::east:c.column=(c.column+1)%size;break;case Heading::south:c.row=(c.row+1)%size;break;case Heading::west:c.column=(c.column+size-1)%size;break;case Heading::north:c.row=(c.row+size-1)%size;break;}return c;}''',
        r'''auto r=step_cube({Face::front,1,2,Heading::east},3);if(!r||r->face!=Face::right||r->row!=1||r->column!=0||r->heading!=Heading::east)return 1;return 0;''',
        r'''if(step_cube({Face::front,-1,0,Heading::east},3)||step_cube({Face::front,0,0,Heading::east},0))return 1;auto a=step_cube({Face::front,0,1,Heading::north},3);if(!a||a->face!=Face::top||a->row!=2||a->column!=1||a->heading!=Heading::north)return 2;auto b=step_cube({Face::right,2,1,Heading::south},3);if(!b||b->face!=Face::bottom)return 3;if(step_cube({static_cast<Face>(99),0,0,Heading::east},3)||step_cube({Face::front,0,0,static_cast<Heading>(99)},3))return 4;return 0;''',
        "face coordinates and size must be valid before the step", "edge offset is preserved in the destination basis", "same-face modular wrapping never changes cube face",
    ))
    c.append(_case(
        "coord-torus-nearest-delta", "Nearest toroidal displacement", "centered Euclidean modular reduction per axis",
        r'''struct Point{long long x;long long y;}; std::optional<Point> torus_delta(Point from,Point to,long long width,long long height);''',
        r'''std::optional<Point> torus_delta(Point,Point,long long,long long){return std::nullopt;}''',
        r'''namespace{std::optional<long long> axis(long long a,long long b,long long p){long long raw=0;if(__builtin_sub_overflow(b,a,&raw))return std::nullopt;long long r=raw%p;if(r<0)r+=p;if(r>p/2)r-=p;return r;}} std::optional<Point> torus_delta(Point a,Point b,long long w,long long h){if(w<=0||h<=0)return std::nullopt;auto x=axis(a.x,b.x,w),y=axis(a.y,b.y,h);return x&&y?std::optional<Point>(Point{*x,*y}):std::nullopt;}''',
        r'''std::optional<Point> torus_delta(Point a,Point b,long long w,long long h){if(w<=0||h<=0)return std::nullopt;return Point{b.x-a.x,b.y-a.y};}''',
        r'''auto r=torus_delta({9,1},{1,8},10,10);if(!r||r->x!=2||r->y!=-3)return 1;return 0;''',
        r'''if(torus_delta({0,0},{1,1},0,4))return 1;auto t=torus_delta({0,0},{5,-4},10,8);if(!t||t->x!=5||t->y!=4)return 2;auto n=torus_delta({5,5},{0,1},10,8);if(!n||n->x!=5||n->y!=4)return 3;if(torus_delta({std::numeric_limits<long long>::min(),0},{std::numeric_limits<long long>::max(),0},10,10))return 4;return 0;''',
        "periods are positive and raw subtraction must be representable", "positive displacement wins exact half-period ties", "raw subtraction ignores the torus seam",
    ))
    c.append(_case(
        "coord-voxel-axis-map", "Signed voxel-axis permutation", "validated bijective signed-axis lookup",
        r'''struct Point3{long long x;long long y;long long z;}; struct AxisMap{std::array<int,3> source_axis;}; std::optional<Point3> remap_voxel(Point3 point,AxisMap map);''',
        r'''std::optional<Point3> remap_voxel(Point3,AxisMap){return std::nullopt;}''',
        r'''std::optional<Point3> remap_voxel(Point3 p,AxisMap m){std::array<long long,3> in{p.x,p.y,p.z},out{};std::array<bool,3> used{};for(std::size_t i=0;i<3;++i){int code=m.source_axis[i];if(code < -3||code>3||code==0)return std::nullopt;int axis=(code<0?-code:code)-1;if(used[std::size_t(axis)])return std::nullopt;used[std::size_t(axis)]=true;long long v=in[std::size_t(axis)];if(code<0){if(v==std::numeric_limits<long long>::min())return std::nullopt;v=-v;}out[i]=v;}return Point3{out[0],out[1],out[2]};}''',
        r'''std::optional<Point3> remap_voxel(Point3 p,AxisMap m){std::array<long long,3> in{p.x,p.y,p.z};return Point3{in[std::size_t(std::abs(m.source_axis[0])-1)],in[std::size_t(std::abs(m.source_axis[1])-1)],in[std::size_t(std::abs(m.source_axis[2])-1)]};}''',
        r'''auto r=remap_voxel({2,-3,5},{{-3,1,-2}});if(!r||r->x!=-5||r->y!=2||r->z!=3)return 1;return 0;''',
        r'''if(remap_voxel({1,2,3},{{1,1,3}})||remap_voxel({1,2,3},{{0,2,3}})||remap_voxel({1,2,3},{{std::numeric_limits<int>::min(),2,3}}))return 1;if(remap_voxel({0,0,std::numeric_limits<long long>::min()},{{-3,1,2}}))return 2;auto i=remap_voxel({7,8,9},{{1,2,3}});if(!i||i->x!=7||i->y!=8||i->z!=9)return 3;return 0;''',
        "axis codes must be a signed permutation and negation must be representable", "output position order follows the three map entries", "absolute-axis lookup ignores reflection signs",
    ))
    c.append(_case(
        "coord-tensor-stride", "Permutation-aware tensor strides", "checked mixed-radix stride construction",
        r'''std::optional<std::uint64_t> tensor_linearize(const std::vector<std::uint32_t>& shape,const std::vector<unsigned>& fastest_to_slowest,const std::vector<std::uint32_t>& coordinate); std::optional<std::vector<std::uint32_t>> tensor_unlinearize(const std::vector<std::uint32_t>& shape,const std::vector<unsigned>& fastest_to_slowest,std::uint64_t index);''',
        r'''std::optional<std::uint64_t> tensor_linearize(const std::vector<std::uint32_t>&,const std::vector<unsigned>&,const std::vector<std::uint32_t>&){return std::nullopt;} std::optional<std::vector<std::uint32_t>> tensor_unlinearize(const std::vector<std::uint32_t>&,const std::vector<unsigned>&,std::uint64_t){return std::nullopt;}''',
        r'''namespace{std::optional<std::vector<std::uint64_t>> strides(const std::vector<std::uint32_t>&s,const std::vector<unsigned>&o,std::uint64_t&cap){if(s.empty()||s.size()!=o.size())return std::nullopt;std::vector<bool>seen(s.size());std::vector<std::uint64_t>st(s.size());cap=1;for(unsigned axis:o){if(axis>=s.size()||seen[axis]||s[axis]==0)return std::nullopt;seen[axis]=true;st[axis]=cap;if(cap>std::numeric_limits<std::uint64_t>::max()/s[axis])return std::nullopt;cap*=s[axis];}return st;}} std::optional<std::uint64_t> tensor_linearize(const std::vector<std::uint32_t>&s,const std::vector<unsigned>&o,const std::vector<std::uint32_t>&c){std::uint64_t cap=0;auto st=strides(s,o,cap);if(!st||c.size()!=s.size())return std::nullopt;std::uint64_t out=0;for(std::size_t i=0;i<s.size();++i){if(c[i]>=s[i])return std::nullopt;out+=std::uint64_t(c[i])*(*st)[i];}return out;} std::optional<std::vector<std::uint32_t>> tensor_unlinearize(const std::vector<std::uint32_t>&s,const std::vector<unsigned>&o,std::uint64_t index){std::uint64_t cap=0;auto st=strides(s,o,cap);if(!st||index>=cap)return std::nullopt;std::vector<std::uint32_t>c(s.size());for(auto it=o.rbegin();it!=o.rend();++it){unsigned a=*it;c[a]=std::uint32_t(index/(*st)[a]);index%=(*st)[a];}return c;}''',
        r'''std::optional<std::uint64_t> tensor_linearize(const std::vector<std::uint32_t>&s,const std::vector<unsigned>&,const std::vector<std::uint32_t>&c){if(s.size()!=c.size())return std::nullopt;std::uint64_t v=0;for(std::size_t i=0;i<s.size();++i)v=v*s[i]+c[i];return v;} std::optional<std::vector<std::uint32_t>> tensor_unlinearize(const std::vector<std::uint32_t>&s,const std::vector<unsigned>&,std::uint64_t i){std::vector<std::uint32_t>c(s.size());for(std::size_t n=s.size();n-->0;){c[n]=std::uint32_t(i%s[n]);i/=s[n];}return c;}''',
        r'''std::vector<std::uint32_t>s{2,3,4},p{1,2,3};std::vector<unsigned>o{1,0,2};auto i=tensor_linearize(s,o,p);if(!i||*i!=23)return 1;auto c=tensor_unlinearize(s,o,*i);if(!c||*c!=p)return 2;return 0;''',
        r'''if(tensor_linearize({}, {}, {})||tensor_linearize({2,3},{0,0},{1,1})||tensor_linearize({2,3},{0,1},{2,0})||tensor_unlinearize({2,3},{0,1},6))return 1;for(std::uint32_t a=0;a<2;++a)for(std::uint32_t b=0;b<3;++b)for(std::uint32_t d=0;d<4;++d){std::vector<std::uint32_t>p{a,b,d};auto i=tensor_linearize({2,3,4},{2,0,1},p);auto q=i?tensor_unlinearize({2,3,4},{2,0,1},*i):std::nullopt;if(!q||*q!=p)return 2;}return 0;''',
        "ranks must match, extents are positive, order is a permutation, and capacity is checked", "the supplied fastest-to-slowest order defines strides", "fixed row-major folding ignores the axis permutation",
    ))
    c.append(_case(
        "coord-ragged-linear", "Ragged row linearization", "checked prefix lengths and upper-bound row recovery",
        r'''struct RaggedCell{std::size_t row;std::size_t column;}; std::optional<std::size_t> ragged_index(const std::vector<std::size_t>& row_lengths,RaggedCell cell); std::optional<RaggedCell> ragged_cell(const std::vector<std::size_t>& row_lengths,std::size_t index);''',
        r'''std::optional<std::size_t> ragged_index(const std::vector<std::size_t>&,RaggedCell){return std::nullopt;} std::optional<RaggedCell> ragged_cell(const std::vector<std::size_t>&,std::size_t){return std::nullopt;}''',
        r'''namespace{std::optional<std::vector<std::size_t>> prefix(const std::vector<std::size_t>&r){std::vector<std::size_t>p{0};for(auto n:r){if(p.back()>std::numeric_limits<std::size_t>::max()-n)return std::nullopt;p.push_back(p.back()+n);}return p;}} std::optional<std::size_t> ragged_index(const std::vector<std::size_t>&r,RaggedCell c){auto p=prefix(r);if(!p||c.row>=r.size()||c.column>=r[c.row])return std::nullopt;return (*p)[c.row]+c.column;} std::optional<RaggedCell> ragged_cell(const std::vector<std::size_t>&r,std::size_t i){auto p=prefix(r);if(!p||i>=p->back())return std::nullopt;auto it=std::upper_bound(p->begin(),p->end(),i);std::size_t row=std::size_t(it-p->begin()-1);while(row<r.size()&&r[row]==0)++row;if(row>=r.size()||i<(*p)[row]||i>=(*p)[row+1])return std::nullopt;return RaggedCell{row,i-(*p)[row]};}''',
        r'''std::optional<std::size_t> ragged_index(const std::vector<std::size_t>&r,RaggedCell c){auto w=*std::max_element(r.begin(),r.end());return c.row*w+c.column;} std::optional<RaggedCell> ragged_cell(const std::vector<std::size_t>&r,std::size_t i){auto w=*std::max_element(r.begin(),r.end());return RaggedCell{i/w,i%w};}''',
        r'''std::vector<std::size_t>r{2,0,3};auto i=ragged_index(r,{2,1});if(!i||*i!=3)return 1;auto c=ragged_cell(r,2);if(!c||c->row!=2||c->column!=0)return 2;return 0;''',
        r'''std::vector<std::size_t>r{0,1,0,2};if(ragged_index(r,{0,0})||ragged_cell(r,3))return 1;for(std::size_t row=0;row<r.size();++row)for(std::size_t col=0;col<r[row];++col){auto i=ragged_index(r,{row,col});auto c=i?ragged_cell(r,*i):std::nullopt;if(!c||c->row!=row||c->column!=col)return 2;}if(ragged_index({std::numeric_limits<std::size_t>::max(),1},{1,0}))return 3;return 0;''',
        "row/column/index validity and prefix overflow are checked", "empty rows occupy no flat indices but remain in row numbering", "maximum-width multiplication invents padding cells",
    ))
    c.append(_case(
        "coord-upper-triangle-index", "Upper-triangle rank and unrank", "triangular row-prefix counts and monotone search",
        r'''struct UpperCell{std::uint64_t row;std::uint64_t column;}; std::optional<std::uint64_t> upper_index(std::uint64_t size,UpperCell cell); std::optional<UpperCell> upper_cell(std::uint64_t size,std::uint64_t index);''',
        r'''std::optional<std::uint64_t> upper_index(std::uint64_t,UpperCell){return std::nullopt;} std::optional<UpperCell> upper_cell(std::uint64_t,std::uint64_t){return std::nullopt;}''',
        r'''namespace{std::optional<std::uint64_t> capacity(std::uint64_t n){if(n==std::numeric_limits<std::uint64_t>::max())return std::nullopt;std::uint64_t a=n,b=n+1;if((a&1U)==0)a/=2;else b/=2;if(a&&b>std::numeric_limits<std::uint64_t>::max()/a)return std::nullopt;return a*b;}std::optional<std::uint64_t> prefix(std::uint64_t n,std::uint64_t r){auto cap=capacity(n);auto tail=capacity(n-r);return cap&&tail?std::optional<std::uint64_t>(*cap-*tail):std::nullopt;}} std::optional<std::uint64_t> upper_index(std::uint64_t n,UpperCell c){if(c.row>=n||c.column<c.row||c.column>=n)return std::nullopt;auto p=prefix(n,c.row);return p?std::optional<std::uint64_t>(*p+c.column-c.row):std::nullopt;} std::optional<UpperCell> upper_cell(std::uint64_t n,std::uint64_t i){auto cap=capacity(n);if(!cap||i>=*cap)return std::nullopt;std::uint64_t lo=0,hi=n;while(lo+1<hi){std::uint64_t mid=lo+(hi-lo)/2;auto p=prefix(n,mid);if(*p<=i)lo=mid;else hi=mid;}auto p=prefix(n,lo);return UpperCell{lo,lo+i-*p};}''',
        r'''std::optional<std::uint64_t> upper_index(std::uint64_t n,UpperCell c){if(c.row>=n||c.column>=n)return std::nullopt;return c.row*n+c.column;} std::optional<UpperCell> upper_cell(std::uint64_t n,std::uint64_t i){if(n==0||i>=n*n)return std::nullopt;return UpperCell{i/n,i%n};}''',
        r'''auto i=upper_index(4,{1,3});if(!i||*i!=6)return 1;auto c=upper_cell(4,6);if(!c||c->row!=1||c->column!=3)return 2;return 0;''',
        r'''if(upper_index(4,{3,2})||upper_cell(4,10))return 1;for(std::uint64_t r=0;r<8;++r)for(std::uint64_t col=r;col<8;++col){auto i=upper_index(8,{r,col});auto c=i?upper_cell(8,*i):std::nullopt;if(!c||c->row!=r||c->column!=col)return 2;}if(upper_index(std::numeric_limits<std::uint64_t>::max(),{0,0}))return 3;return 0;''',
        "only row-at-most-column cells and representable triangular capacities are valid", "rows precede later rows and columns ascend inside a row", "dense-square indexing includes forbidden lower-triangle cells",
    ))
    c.append(_case(
        "coord-reflective-boundary-fold", "Periodic reflective boundary fold", "Euclidean triangle-wave folding with branch direction",
        r'''struct Point{long long x;long long y;}; struct Size{long long width;long long height;}; struct ReflectedAxis{long long coordinate;int direction;}; struct ReflectedPoint{ReflectedAxis x;ReflectedAxis y;}; std::optional<ReflectedPoint> fold_reflected(Point unbounded,Size bounds);''',
        r'''std::optional<ReflectedPoint> fold_reflected(Point,Size){return std::nullopt;}''',
        r'''namespace{std::optional<ReflectedAxis> fold(long long value,long long extent){if(extent<=0||extent>1000000000LL)return std::nullopt;if(extent==1)return ReflectedAxis{0,0};long long period=2*(extent-1),phase=value%period;if(phase<0)phase+=period;if(phase<extent)return ReflectedAxis{phase,1};return ReflectedAxis{period-phase,-1};}} std::optional<ReflectedPoint> fold_reflected(Point p,Size b){auto x=fold(p.x,b.width),y=fold(p.y,b.height);if(!x||!y)return std::nullopt;return ReflectedPoint{*x,*y};}''',
        r'''std::optional<ReflectedPoint> fold_reflected(Point p,Size b){if(b.width<=0||b.height<=0)return std::nullopt;auto clamp=[](long long v,long long extent){return std::max(0LL,std::min(v,extent-1));};return ReflectedPoint{{clamp(p.x,b.width),0},{clamp(p.y,b.height),0}};}''',
        r'''auto r=fold_reflected({6,-1},{5,4});if(!r||r->x.coordinate!=2||r->x.direction!=-1||r->y.coordinate!=1||r->y.direction!=-1)return 1;return 0;''',
        r'''if(fold_reflected({0,0},{0,4})||fold_reflected({0,0},{1000000001LL,4}))return 1;auto a=fold_reflected({4,0},{5,1});if(!a||a->x.coordinate!=4||a->x.direction!=1||a->y.coordinate!=0||a->y.direction!=0)return 2;auto b=fold_reflected({std::numeric_limits<long long>::min(),std::numeric_limits<long long>::max()},{7,6});if(!b||b->x.coordinate!=4||b->x.direction!=1||b->y.coordinate!=3||b->y.direction!=-1)return 3;for(long long v=-40;v<=40;++v){auto f=fold_reflected({v,v},{8,8});if(!f||f->x.coordinate<0||f->x.coordinate>=8||f->x.coordinate!=f->y.coordinate||f->x.direction!=f->y.direction)return 4;}return 0;''',
        "both extents are in one through one billion; singleton axes fold every value to zero", "Euclidean phase uses the outward branch at both boundary phases and reports inward direction only after the far endpoint", "clamping discards repeated mirror periods and branch direction",
    ))
    c.append(_case(
        "coord-camera-crop-orient", "Crop-aware camera orientation", "crop translation then dimension-aware rotation and mirror",
        r'''struct Point{long long x;long long y;}; struct Rect{long long x;long long y;long long width;long long height;}; struct OrientedPixel{Point point;long long width;long long height;}; std::optional<OrientedPixel> orient_crop(Point sensor,Rect crop,int clockwise_quarters,bool mirror_x);''',
        r'''std::optional<OrientedPixel> orient_crop(Point,Rect,int,bool){return std::nullopt;}''',
        r'''std::optional<OrientedPixel> orient_crop(Point p,Rect c,int q,bool mirror){if(c.width<=0||c.height<=0)return std::nullopt;long long maxx=0,maxy=0;if(__builtin_add_overflow(c.x,c.width,&maxx)||__builtin_add_overflow(c.y,c.height,&maxy)||p.x<c.x||p.y<c.y||p.x>=maxx||p.y>=maxy)return std::nullopt;Point x{p.x-c.x,p.y-c.y};long long w=c.width,h=c.height;int n=(q%4+4)%4;for(int i=0;i<n;++i){x=Point{h-1-x.y,x.x};std::swap(w,h);}if(mirror)x.x=w-1-x.x;return OrientedPixel{x,w,h};}''',
        r'''std::optional<OrientedPixel> orient_crop(Point p,Rect c,int q,bool mirror){if(c.width<=0||c.height<=0)return std::nullopt;Point x{p.x-c.x,p.y-c.y};if(mirror)x.x=c.width-1-x.x;if(q%2)std::swap(x.x,x.y);return OrientedPixel{x,c.width,c.height};}''',
        r'''auto r=orient_crop({12,21},{10,20,4,3},1,true);if(!r||r->width!=3||r->height!=4||r->point.x!=1||r->point.y!=2)return 1;return 0;''',
        r'''if(orient_crop({9,20},{10,20,4,3},0,false)||orient_crop({10,20},{10,20,0,3},0,false))return 1;auto a=orient_crop({10,20},{10,20,4,3},-1,false);if(!a||a->width!=3||a->height!=4||a->point.x!=0||a->point.y!=3)return 2;auto b=orient_crop({13,22},{10,20,4,3},2,true);if(!b||b->point.x!=3||b->point.y!=0)return 3;return 0;''',
        "crop dimensions, checked crop bounds, and sensor membership are required", "rotation precedes mirror in output dimensions", "mirroring in source dimensions before rotation changes oriented pixels",
    ))
    c.append(_case(
        "coord-polyline-frame", "Orthogonal polyline local frame", "checked segment-prefix selection with vertex handoff",
        r'''struct Point{long long x;long long y;}; struct FrameSample{Point point;Point tangent;std::size_t segment;}; std::optional<FrameSample> sample_polyline(const std::vector<Point>& vertices,unsigned long long distance);''',
        r'''std::optional<FrameSample> sample_polyline(const std::vector<Point>&,unsigned long long){return std::nullopt;}''',
        r'''namespace{unsigned long long mag(long long v){return v<0?0ULL-static_cast<unsigned long long>(v):static_cast<unsigned long long>(v);}} std::optional<FrameSample> sample_polyline(const std::vector<Point>&v,unsigned long long d){if(v.size()<2)return std::nullopt;std::vector<unsigned long long>lengths;std::vector<Point>tangents;lengths.reserve(v.size()-1);tangents.reserve(v.size()-1);for(std::size_t i=0;i+1<v.size();++i){long long dx=0,dy=0;if(__builtin_sub_overflow(v[i+1].x,v[i].x,&dx)||__builtin_sub_overflow(v[i+1].y,v[i].y,&dy)||(dx!=0&&dy!=0)||(dx==0&&dy==0))return std::nullopt;lengths.push_back(mag(dx)+mag(dy));tangents.push_back({dx==0?0:(dx>0?1:-1),dy==0?0:(dy>0?1:-1)});}for(std::size_t i=0;i<lengths.size();++i){unsigned long long len=lengths[i];Point t=tangents[i];if(d==len&&i+1==lengths.size())return FrameSample{v[i+1],t,i};if(d<len){long long step=static_cast<long long>(d),ox=0,oy=0,x=0,y=0;if(__builtin_mul_overflow(t.x,step,&ox)||__builtin_mul_overflow(t.y,step,&oy)||__builtin_add_overflow(v[i].x,ox,&x)||__builtin_add_overflow(v[i].y,oy,&y))return std::nullopt;return FrameSample{{x,y},t,i};}d-=len;}return std::nullopt;}''',
        r'''std::optional<FrameSample> sample_polyline(const std::vector<Point>&v,unsigned long long d){if(v.size()<2)return std::nullopt;long long dx=v.back().x-v.front().x,dy=v.back().y-v.front().y;unsigned long long total=std::llabs(dx)+std::llabs(dy);if(d>total)return std::nullopt;return FrameSample{{v.front().x+dx*static_cast<long long>(d)/static_cast<long long>(total),v.front().y+dy*static_cast<long long>(d)/static_cast<long long>(total)},{dx,dy},0};}''',
        r'''std::vector<Point>v{{0,0},{3,0},{3,2}};auto r=sample_polyline(v,3);if(!r||r->point.x!=3||r->point.y!=0||r->tangent.x!=0||r->tangent.y!=1||r->segment!=1)return 1;return 0;''',
        r'''if(sample_polyline({{0,0}},0)||sample_polyline({{0,0},{1,1}},0)||sample_polyline({{0,0},{0,0}},0))return 1;std::vector<Point>v{{-2,0},{2,0},{2,-3}};auto a=sample_polyline(v,7);if(!a||a->point.x!=2||a->point.y!=-3||a->segment!=1)return 2;if(sample_polyline(v,8))return 3;auto e=sample_polyline({{0,0},{std::numeric_limits<long long>::min(),0}},1ULL<<63U);if(!e||e->point.x!=std::numeric_limits<long long>::min()||e->point.y!=0||e->tangent.x!=-1||e->tangent.y!=0||e->segment!=0)return 4;if(sample_polyline({{0,0},{10,0},{11,1}},1)||sample_polyline({{0,0},{10,0},{10,0}},1))return 5;return 0;''',
        "at least two nonzero orthogonal segments and an in-range checked distance are required", "internal vertex distance belongs to the following segment", "endpoint interpolation ignores bends and unit tangent state",
    ))
    c.append(_case(
        "coord-offset-hex-convert", "Signed odd-row hex conversion", "parity-correct mathematical floor-half conversion",
        r'''struct Offset{long long column;long long row;}; struct Cube{long long x;long long y;long long z;}; std::optional<Cube> odd_row_to_cube(Offset cell); std::optional<Offset> cube_to_odd_row(Cube cube);''',
        r'''std::optional<Cube> odd_row_to_cube(Offset){return std::nullopt;} std::optional<Offset> cube_to_odd_row(Cube){return std::nullopt;}''',
        r'''namespace{long long floor2(long long v){long long q=v/2;if(v<0&&v%2)--q;return q;}} std::optional<Cube> odd_row_to_cube(Offset o){long long adjust=0,x=0,y=0;if(__builtin_sub_overflow(o.row&1LL,0LL,&adjust)||__builtin_sub_overflow(o.row,adjust,&adjust)||__builtin_sub_overflow(o.column,floor2(adjust),&x)||__builtin_sub_overflow(0LL,x,&y)||__builtin_sub_overflow(y,o.row,&y))return std::nullopt;return Cube{x,y,o.row};} std::optional<Offset> cube_to_odd_row(Cube c){long long sum=0;if(__builtin_add_overflow(c.x,c.y,&sum)||__builtin_add_overflow(sum,c.z,&sum)||sum!=0)return std::nullopt;long long adjust=c.z-(c.z&1LL),column=0;if(__builtin_add_overflow(c.x,floor2(adjust),&column))return std::nullopt;return Offset{column,c.z};}''',
        r'''std::optional<Cube> odd_row_to_cube(Offset o){long long x=o.column-(o.row-(o.row&1LL))/2;return Cube{x,-x-o.row,o.row};} std::optional<Offset> cube_to_odd_row(Cube c){return Offset{c.x+(c.z-(c.z&1LL))/2,c.z};}''',
        r'''auto c=odd_row_to_cube({2,-3});if(!c||c->x!=4||c->y!=-1||c->z!=-3)return 1;auto o=cube_to_odd_row(*c);if(!o||o->column!=2||o->row!=-3)return 2;return 0;''',
        r'''if(cube_to_odd_row({1,1,1}))return 1;for(long long r=-5;r<=5;++r)for(long long q=-5;q<=5;++q){auto c=odd_row_to_cube({q,r});auto o=c?cube_to_odd_row(*c):std::nullopt;if(!o||o->column!=q||o->row!=r)return 2;}return 0;''',
        "cube coordinates must satisfy x+y+z=0 and checked arithmetic must succeed", "negative odd rows use mathematical floor-half parity", "truncating half-row shifts negative odd coordinates",
    ))
    c.append(_case(
        "coord-geofence-local", "Dateline-aware local geofence frame", "shortest longitude branch and checked rational scale",
        r'''struct GeoFix{long long latitude_microdegrees;long long longitude_microdegrees;}; struct LocalPoint{long long east;long long north;}; std::optional<LocalPoint> localize_fix(GeoFix origin,GeoFix fix,long long longitude_scale_ppm);''',
        r'''std::optional<LocalPoint> localize_fix(GeoFix,GeoFix,long long){return std::nullopt;}''',
        r'''namespace{bool valid(GeoFix p){return p.latitude_microdegrees>=-90000000&&p.latitude_microdegrees<=90000000&&p.longitude_microdegrees>=-180000000&&p.longitude_microdegrees<=180000000;}} std::optional<LocalPoint> localize_fix(GeoFix o,GeoFix p,long long scale){if(!valid(o)||!valid(p)||scale<0||scale>1000000)return std::nullopt;long long dlon=0,dlat=0;if(__builtin_sub_overflow(p.longitude_microdegrees,o.longitude_microdegrees,&dlon)||__builtin_sub_overflow(p.latitude_microdegrees,o.latitude_microdegrees,&dlat))return std::nullopt;if(dlon>180000000)dlon-=360000000;else if(dlon<-180000000)dlon+=360000000;long long east=0;if(__builtin_mul_overflow(dlon,scale,&east))return std::nullopt;east/=1000000;return LocalPoint{east,dlat};}''',
        r'''std::optional<LocalPoint> localize_fix(GeoFix o,GeoFix p,long long scale){return LocalPoint{(p.longitude_microdegrees-o.longitude_microdegrees)*scale/1000000,p.latitude_microdegrees-o.latitude_microdegrees};}''',
        r'''auto r=localize_fix({0,179000000},{1000000,-179000000},500000);if(!r||r->east!=1000000||r->north!=1000000)return 1;return 0;''',
        r'''if(localize_fix({91000000,0},{0,0},1)||localize_fix({0,0},{0,0},1000001))return 1;auto t=localize_fix({0,-180000000},{0,180000000},1000000);if(!t||t->east!=0)return 2;auto n=localize_fix({-100,10},{-200,0},0);if(!n||n->east!=0||n->north!=-100)return 3;return 0;''',
        "geographic bounds, scale bounds, subtraction, and multiplication are checked", "the shortest dateline delta wins and exact 180-degree ties preserve the raw sign", "raw longitude subtraction chooses the long path across the dateline",
    ))
    c.append(_case(
        "coord-integer-shear", "Invertible integer shear sequence", "ordered unimodular elementary transforms and reverse inverse",
        r'''struct Point{long long x;long long y;}; struct Shear{char axis;long long factor;}; std::optional<Point> apply_shears(Point point,const std::vector<Shear>& operations); std::optional<Point> invert_shears(Point point,const std::vector<Shear>& operations);''',
        r'''std::optional<Point> apply_shears(Point,const std::vector<Shear>&){return std::nullopt;} std::optional<Point> invert_shears(Point,const std::vector<Shear>&){return std::nullopt;}''',
        r'''namespace{bool one(Point&p,Shear s,bool inverse){if(s.axis!='x'&&s.axis!='y')return false;long long f=s.factor;if(inverse){if(f==std::numeric_limits<long long>::min())return false;f=-f;}long long product=0,value=0;if(s.axis=='x'){if(__builtin_mul_overflow(f,p.y,&product)||__builtin_add_overflow(p.x,product,&value))return false;p.x=value;}else{if(__builtin_mul_overflow(f,p.x,&product)||__builtin_add_overflow(p.y,product,&value))return false;p.y=value;}return true;}} std::optional<Point> apply_shears(Point p,const std::vector<Shear>&ops){for(auto s:ops)if(!one(p,s,false))return std::nullopt;return p;} std::optional<Point> invert_shears(Point p,const std::vector<Shear>&ops){for(auto it=ops.rbegin();it!=ops.rend();++it)if(!one(p,*it,true))return std::nullopt;return p;}''',
        r'''namespace{bool one(Point&p,Shear s,bool inv){long long f=inv?-s.factor:s.factor;if(s.axis=='x')p.x+=f*p.y;else if(s.axis=='y')p.y+=f*p.x;else return false;return true;}} std::optional<Point> apply_shears(Point p,const std::vector<Shear>&o){for(auto s:o)if(!one(p,s,false))return std::nullopt;return p;} std::optional<Point> invert_shears(Point p,const std::vector<Shear>&o){for(auto s:o)if(!one(p,s,true))return std::nullopt;return p;}''',
        r'''std::vector<Shear>o{{'x',2},{'y',-1}};auto p=apply_shears({3,4},o);if(!p||p->x!=11||p->y!=-7)return 1;auto q=invert_shears(*p,o);if(!q||q->x!=3||q->y!=4)return 2;return 0;''',
        r'''if(apply_shears({1,2},{{'z',1}})||invert_shears({1,2},{{'x',std::numeric_limits<long long>::min()}}))return 1;std::vector<Shear>o{{'y',3},{'x',-2},{'y',1}};for(long long x=-3;x<=3;++x)for(long long y=-3;y<=3;++y){auto p=apply_shears({x,y},o);auto q=p?invert_shears(*p,o):std::nullopt;if(!q||q->x!=x||q->y!=y)return 2;}if(apply_shears({std::numeric_limits<long long>::max(),1},{{'x',1}}))return 3;return 0;''',
        "axis codes, factor negation, multiplication, and addition are checked", "forward order is significant and inverse order is reversed", "negating operations without reversing them is not the inverse composition",
    ))
    c.append(_case(
        "coord-dihedral-canonical", "Canonical finite shape under D4", "enumerate eight symmetries, normalize, sort, and lexicographically select",
        r'''struct Point{long long x;long long y;}; struct CanonicalShape{std::vector<Point> points;int transform;}; std::optional<CanonicalShape> canonical_dihedral(std::vector<Point> points);''',
        r'''std::optional<CanonicalShape> canonical_dihedral(std::vector<Point>){return std::nullopt;}''',
        r'''namespace{std::optional<Point> image(Point p,int t){long long x=p.x,y=p.y;if((t&4)!=0){if(x==std::numeric_limits<long long>::min())return std::nullopt;x=-x;}for(int i=0;i<(t&3);++i){if(y==std::numeric_limits<long long>::min())return std::nullopt;long long q=x;x=-y;y=q;}return Point{x,y};}bool lessp(Point a,Point b){return a.y!=b.y?a.y<b.y:a.x<b.x;}bool equalp(Point a,Point b){return a.x==b.x&&a.y==b.y;}} std::optional<CanonicalShape> canonical_dihedral(std::vector<Point> in){std::sort(in.begin(),in.end(),lessp);if(std::adjacent_find(in.begin(),in.end(),equalp)!=in.end())return std::nullopt;if(in.empty())return CanonicalShape{{},0};std::optional<CanonicalShape>best;for(int t=0;t<8;++t){std::vector<Point>v;long long minx=std::numeric_limits<long long>::max(),miny=minx;for(Point p:in){auto q=image(p,t);if(!q)return std::nullopt;minx=std::min(minx,q->x);miny=std::min(miny,q->y);v.push_back(*q);}for(Point&q:v){if(__builtin_sub_overflow(q.x,minx,&q.x)||__builtin_sub_overflow(q.y,miny,&q.y))return std::nullopt;}std::sort(v.begin(),v.end(),lessp);auto as_pairs=[](const std::vector<Point>&a){std::vector<std::pair<long long,long long>>r;for(auto p:a)r.emplace_back(p.y,p.x);return r;};if(!best||as_pairs(v)<as_pairs(best->points))best=CanonicalShape{v,t};}return best;}''',
        r'''namespace{bool lessp(Point a,Point b){return a.y!=b.y?a.y<b.y:a.x<b.x;}} std::optional<CanonicalShape> canonical_dihedral(std::vector<Point> in){if(in.empty())return CanonicalShape{{},0};std::optional<CanonicalShape>best;for(int t=0;t<4;++t){std::vector<Point>v=in;for(Point&p:v)for(int i=0;i<t;++i){long long x=p.x;p.x=-p.y;p.y=x;}long long minx=v[0].x,miny=v[0].y;for(auto p:v){minx=std::min(minx,p.x);miny=std::min(miny,p.y);}for(Point&p:v){p.x-=minx;p.y-=miny;}std::sort(v.begin(),v.end(),lessp);if(!best||v.size()<best->points.size())best=CanonicalShape{v,t};}return best;}''',
        r'''auto r=canonical_dihedral({{0,0},{1,0},{0,2}});if(!r||r->points.size()!=3||r->points[0].x!=0||r->points[0].y!=0)return 1;return 0;''',
        r'''if(canonical_dihedral({{1,1},{1,1}}))return 1;auto e=canonical_dihedral({});if(!e||!e->points.empty()||e->transform!=0)return 2;std::vector<Point>a{{0,0},{2,0},{0,1},{1,1}},b{{0,0},{-2,0},{0,1},{-1,1}};auto x=canonical_dihedral(a),y=canonical_dihedral(b);if(!x||!y||x->points.size()!=y->points.size())return 3;for(std::size_t i=0;i<x->points.size();++i)if(x->points[i].x!=y->points[i].x||x->points[i].y!=y->points[i].y)return 4;return 0;''',
        "duplicate input points and unrepresentable symmetry/normalization reject", "compare row-major normalized point lists, then lowest transform index", "rotations alone omit reflected equivalence",
    ))
    if len(c) != 25 or len({case.task_id for case in c}) != 25:
        raise AssertionError("the binding coordinate-transform count is exactly 25")
    return tuple(c)


CASES = _cases()


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "sha256:absent"
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _inventory_hash(records: Sequence[tuple[str, str]]) -> str:
    return _sha("\n".join(f"{task_id}\t{path}" for task_id, path in records).encode())


def _safe_out(out: Path) -> Path:
    resolved = out.resolve(strict=False)
    if resolved != DEFAULT_OUT.resolve(strict=False):
        _fail("invalid_output_root", str(out))
    if out.is_symlink() or any(parent.is_symlink() for parent in (out.parent, out.parent.parent)):
        _fail("invalid_output_root", "symlink")
    for legacy in LEGACY_ROOTS:
        old = legacy.resolve(strict=False)
        if resolved == old or old in resolved.parents:
            _fail("invalid_output_root", str(legacy))
    return out


def _task_inventory(exclude: Path | None = None) -> dict[str, object]:
    roots = {"generated": LEGACY_ROOTS[0], "reverify": LEGACY_ROOTS[1], "expansion": EXPANSION_ROOT}
    all_ids: dict[str, list[str]] = {}
    result: dict[str, object] = {"schema_version": "coordinate-source-inventory-v1", "roots": {}}
    for label, base in roots.items():
        records: list[tuple[str, str]] = []
        if base.is_dir():
            for config in sorted(base.rglob(".meta/config.json")):
                task_root = config.parent.parent
                if ".state" in config.parts or (exclude is not None and exclude.resolve(strict=False) in task_root.resolve(strict=False).parents):
                    continue
                task_id = task_root.name
                relative = task_root.relative_to(REPO_ROOT).as_posix()
                all_ids.setdefault(task_id, []).append(relative)
                records.append((task_id, relative))
        result["roots"][label] = {"path": str(base.relative_to(REPO_ROOT)), "count": len(records), "sorted_id_path_hash": _inventory_hash(records), "records": records}
    result["total"] = len(all_ids)
    result["all_ids"] = sorted(all_ids)
    result["reserved_lineage_collisions"] = {task_id: paths for task_id, paths in sorted(all_ids.items()) if len(paths) > 1}
    result["all_ids_hash"] = _sha("\n".join(sorted(all_ids)).encode())
    return result


HEADER_INCLUDES = """#include <array>\n#include <cstddef>\n#include <cstdint>\n#include <optional>\n#include <string>\n#include <string_view>\n#include <vector>\n"""
SOURCE_INCLUDES = """#include <algorithm>\n#include <cmath>\n#include <cstdlib>\n#include <limits>\n#include <numeric>\n#include <set>\n#include <utility>\n"""
TEST_INCLUDES = """#include <array>\n#include <cstdint>\n#include <limits>\n#include <optional>\n#include <string>\n#include <utility>\n#include <vector>\n"""


def _header(case: Case) -> str:
    guard = case.task_id.replace("-", "_").upper() + "_H"
    return f"#ifndef {guard}\n#define {guard}\n{HEADER_INCLUDES}namespace coordinate_transform {{\n{case.header}}}\n#endif\n"


def _source(case: Case, body: str) -> str:
    return f'#include "{case.task_id}.h"\n{SOURCE_INCLUDES}namespace coordinate_transform {{\n{body}}}\n'


def _statement_lines(body: str) -> str:
    """Split top-level C++ statements without touching for headers or literals."""
    result: list[str] = []
    parentheses = 0
    quote = ""
    escaped = False
    for character in body:
        result.append(character)
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "(":
            parentheses += 1
        elif character == ")":
            parentheses -= 1
        elif character == ";" and parentheses == 0:
            result.append("\n")
    return "".join(result)


def _test_source(case: Case, body: str) -> str:
    return f'#include "{case.task_id}.h"\n{TEST_INCLUDES}using namespace coordinate_transform;\nint main(){{\n{_statement_lines(body)}\n}}\n'


def _cmake(case: Case) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({case.task_id.replace('-', '_')} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_compile_options(-Wall -Wextra -Wpedantic -Werror)
include_directories("${{CMAKE_CURRENT_SOURCE_DIR}}")
enable_testing()
add_executable(visible {case.task_id}.cpp visible_test.cpp)
add_executable(private {case.task_id}.cpp .meta/private_test.cpp)
add_executable(negative .meta/negative.cpp .meta/private_test.cpp)
add_test(NAME visible COMMAND visible)
add_test(NAME private COMMAND private)
add_test(NAME negative COMMAND negative)
set_tests_properties(negative PROPERTIES WILL_FAIL TRUE)
"""


def _instructions(case: Case) -> str:
    return f"""# {case.title}

Implement the declarations in `{case.task_id}.h` in namespace
`coordinate_transform`. The task's substantive mechanism is
**{case.mechanism}**; implement it directly with C++17 and the standard library.

Invalid behavior: {case.invalid_rule}. Ordering/tie behavior: {case.tie_rule}.
Return failure atomically: do not return a partially transformed value. The
public API and signed/unsigned widths are exact. All results must be
deterministic and offline.

The implementation must handle normal inputs, invalid inputs, absent or empty
states where the API permits them, signed and zero boundaries, exact ordering,
and ties. Use checked arithmetic whenever an intermediate can exceed its public
type. The coherent false substitute that the private evaluator rejects is:
{case.negative_reason}.

Do not delegate the core transform to a geometry, matrix, parser, or coordinate
library; do not precompute tested answers; and do not change public names.
"""


def _render(case: Case, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    _write(root / ".docs/introduction.md", f"# {case.title}\n\nA clean-room coordinate transformation exercise.\n")
    _write(root / ".docs/instructions.md", _instructions(case))
    _write(root / f"{case.task_id}.h", _header(case))
    _write(root / f"{case.task_id}.cpp", _source(case, case.starter))
    _write(root / "visible_test.cpp", _test_source(case, case.visible))
    _write(root / ".meta/example.h", _header(case))
    _write(root / ".meta/example.cpp", _source(case, case.reference))
    _write(root / ".meta/private_test.cpp", _test_source(case, case.private))
    _write(root / ".meta/negative.cpp", _source(case, case.negative))
    _write(root / "CMakeLists.txt", _cmake(case))
    _write(root / ".meta/tests.toml", f'''[visible]\ndescription = "normal {case.mechanism}"\n[private]\ndescription = "invalid, boundary, ordering, tie, round-trip, and coherent negative discrimination"\n''')
    _write_json(root / ".meta/config.json", {
        "authors": ["w8-biayn"],
        "blurb": case.title,
        "source": "Clean-room w8-biayn coordinate-transformations curriculum",
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["visible_test.cpp", ".meta/private_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    })
    _write_json(root / ".meta/provenance.json", {
        "schema_version": "coordinate-transform-provenance-v1",
        "task_id": case.task_id,
        "task_spec_revision": "v1",
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "authoring": "clean-room repository-authored",
        "license": "CC0-1.0",
        "count_plan_cell": "text/grid: grid coordinate transforms, orientation, and traversal",
        "curriculum": str(CURRICULUM.relative_to(REPO_ROOT)),
        "family_spec": str(FAMILY_SPEC.relative_to(REPO_ROOT)),
        "owner": OWNER,
        "primary_core_objective": "achieved",
        "mechanism": case.mechanism,
        "negative_fixture": case.negative_reason,
        "status": "generated_pending_creator_preflight",
        "non_claim": "local task candidate only; no SFT release, training authorization, or benchmark claim",
    })


def _replace_tree_text(root: Path, replacements: Sequence[tuple[str, str]]) -> list[str]:
    changed: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {".h", ".cpp", ".md", ".json", ".toml"}):
        before = path.read_text(encoding="utf-8")
        after = before
        for old, new in replacements:
            after = after.replace(old, new)
        if after != before:
            _write(path, after)
            changed.append(path.relative_to(root).as_posix())
    return changed


def _materialize_controls(out: Path) -> dict[str, object]:
    source_id = "coord-torus-nearest-delta"
    source = out / source_id
    controls_root = out / ".state/controls"
    records: dict[str, object] = {}
    variants = {
        "domain-identifier-rename": [
            ("coordinate_transform", "navigation_transform"), ("Point", "Offset"),
            ("torus_delta", "ring_offset"), ("toroidal", "wrapped navigation"),
        ],
        "constants-policy-only": [
            ("if(r>p/2)r-=p;", "if(r>=p/2&&r!=0)r-=p;"),
            ("positive displacement wins exact half-period ties", "negative displacement wins exact half-period ties"),
            ("t->x!=5||t->y!=4", "t->x!=-5||t->y!=-4"),
            ("n->x!=5||n->y!=4", "n->x!=-5||n->y!=-4"),
        ],
        "opposite-end-selection": [
            ("__builtin_sub_overflow(b,a,&raw)", "__builtin_sub_overflow(a,b,&raw)"),
            ("r->x!=2||r->y!=-3", "r->x!=-2||r->y!=3"),
            ("Nearest toroidal displacement", "Reverse toroidal displacement"),
            ("from,Point to", "destination,Point source"),
        ],
    }
    for name, replacements in variants.items():
        root = controls_root / name
        shutil.copytree(source, root)
        changed = _replace_tree_text(root, replacements)
        if not changed:
            _fail("adversarial_control_invalid", f"{name}:no changes")
        records[name] = {"root": str(root.relative_to(out)), "source_task": source_id, "changed_files": changed, "coherent": True, "behavior_execution": "pending_docker_sanity", "semantic_rejection": "pending_creator_preflight"}
    record = {"schema_version": "coordinate-clone-controls-v1", "source_task": source_id, "controls": records}
    _write_json(controls_root / "controls.json", record)
    _write_json(controls_root / "cross-alias-controls.json", {
        "schema_version": "coordinate-cross-alias-controls-v1",
        "controls": [CROSS_ALIAS_CONTROL],
        "status": "pending_creator_preflight",
    })
    return record


def _preserve_history(out: Path) -> dict[str, bytes]:
    saved: dict[str, bytes] = {}
    state = out / ".state"
    for folder in ("cycles", "audits", "remedy", "invalidated"):
        base = state / folder
        if base.is_dir():
            for path in base.rglob("*"):
                if path.is_file():
                    saved[path.relative_to(state).as_posix()] = path.read_bytes()
    return saved


def _materialize_remedies(out: Path) -> None:
    cycles = (
        (1, CYCLE_01_AUDIT_RELATIVE, CYCLE_01_SUBJECT, CYCLE_01_FINDINGS, Path(".")),
        (2, CYCLE_02_AUDIT_RELATIVE, CYCLE_02_SUBJECT, CYCLE_02_FINDINGS, Path("cycle-02")),
        (3, CYCLE_03_AUDIT_RELATIVE, CYCLE_03_SUBJECT, CYCLE_03_FINDINGS, Path("cycle-03")),
        (4, CYCLE_04_AUDIT_RELATIVE, CYCLE_04_SUBJECT, CYCLE_04_FINDINGS, Path("cycle-04")),
    )
    for cycle, audit_relative, subject, findings, remedy_folder in cycles:
        audit_path = REPO_ROOT / audit_relative
        if not audit_path.is_file():
            continue
        audit_hash = _file_sha(audit_path)
        for finding_id, remedy in findings.items():
            _write_json(out / ".state/remedy" / remedy_folder / f"{finding_id}.json", {
                "schema_version": "coordinate-remedy-v1",
                "finding_id": finding_id,
                "audit_cycle": cycle,
                "audit_report": audit_relative.as_posix(),
                "audit_report_hash": audit_hash,
                "audit_subject_tree_hash": subject,
                "owner": OWNER,
                **remedy,
                "status": "implemented_pending_creator_preflight_and_fresh_reaudit",
            })


def materialize(out: Path = DEFAULT_OUT, *, force: bool = False) -> dict[str, object]:
    out = _safe_out(out)
    inventory = _task_inventory(exclude=out)
    collisions = sorted(set(case.task_id for case in CASES) & set(inventory["all_ids"]))
    if collisions:
        _fail("existing_task_id", ",".join(collisions))
    preserved: dict[str, bytes] = {}
    invalidated: dict[str, object] | None = None
    if out.exists():
        manifest_path = out / ".state/manifest.json"
        if not force:
            _fail("output_exists", str(out))
        if not manifest_path.is_file() or json.loads(manifest_path.read_text()).get("owner") != OWNER:
            _fail("foreign_output_root", str(out))
        preserved = _preserve_history(out)
        old = json.loads(manifest_path.read_text())
        invalidated = {"schema_version": "coordinate-evidence-invalidation-v1", "prior_tree_hash": old.get("tree_hash"), "prior_status": old.get("status"), "reason": "owner-controlled complete regeneration invalidates all artifact-bound screens and runtime receipts"}
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for case in CASES:
        _render(case, out / case.task_id)
    for relative, data in preserved.items():
        path = out / ".state" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if invalidated:
        serial = len(list((out / ".state/invalidated").glob("regeneration-*.json"))) + 1
        _write_json(out / f".state/invalidated/regeneration-{serial:02d}.json", invalidated)
    _materialize_remedies(out)
    controls = _materialize_controls(out)
    _write_json(out / ".state/source-inventory.json", inventory)
    manifest = {
        "schema_version": "coordinate-transform-family-v1",
        "family_id": FAMILY_ID,
        "owner": OWNER,
        "curriculum": str(CURRICULUM.relative_to(REPO_ROOT)),
        "family_spec": str(FAMILY_SPEC.relative_to(REPO_ROOT)),
        "focused_test": str(FOCUSED_TEST.relative_to(REPO_ROOT)),
        "selected_prompts": list(SELECTED_PROMPTS),
        "task_count": len(CASES),
        "task_ids": [case.task_id for case in CASES],
        "source_inventory_hash": _file_sha(out / ".state/source-inventory.json"),
        "control_count": len(controls["controls"]),
        "status": "generated_pending_creator_preflight",
        "dataset_handoff": "not_requested",
    }
    _write_json(out / ".state/manifest.json", manifest)
    manifest["tree_hash"] = _tree_hash(out)
    _write_json(out / ".state/manifest.json", manifest)
    return manifest


CPP_KEYWORDS = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char class compl concept const constexpr const_cast continue co_await co_return co_yield decltype default delete do double dynamic_cast else enum explicit export extern false float for friend goto if inline int long mutable namespace new noexcept not not_eq nullptr operator or or_eq private protected public register reinterpret_cast requires return short signed sizeof static static_assert static_cast struct switch template this thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq optional vector array string string_view size_t uint32_t uint64_t numeric_limits nullopt std".split()
)
STOP_WORDS = frozenset(
    "the and with from into this that must return task implement invalid exact public coordinate transformation clean room behavior input output value values point points documented complete cplusplus standard library".split()
)


def _strip_cpp(text: str) -> str:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " STR ", text)
    return re.sub(r"\b(?:0[xX][0-9a-fA-F]+|\d[\d']*)\b", " NUM ", text)


def _canonical_tokens(text: str) -> tuple[str, ...]:
    stripped = _strip_cpp(text)
    raw = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|::|->|==|!=|<=|>=|&&|\|\||<<|>>|\S", stripped)
    result: list[str] = []
    for token in raw:
        lower = token.lower()
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", token) and lower not in CPP_KEYWORDS:
            result.append("id")
        else:
            result.append(lower)
    return tuple(result)


def _semantic_words(text: str) -> set[str]:
    text = re.sub(r"`[^`]+`|\b\d[\d']*\b", " ", text.lower())
    words = {word for word in re.findall(r"[a-z][a-z_-]{3,}", text) if word not in STOP_WORDS}
    return {word.replace("_", "-") for word in words}


def _mechanism_alias_marker(left: str, right: str) -> tuple[str, ...] | None:
    """Catch named mechanisms whose width or representation was merely varied."""
    lowered_left = left.lower()
    lowered_right = right.lower()
    for group in MECHANISM_ALIAS_GROUPS:
        left_matches = any(all(term in lowered_left for term in variant) for variant in group)
        right_matches = any(all(term in lowered_right for term in variant) for variant in group)
        if left_matches and right_matches:
            return group[0]
    return None


def _shingles(tokens: Sequence[str], size: int = 4) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def _similarity(left: str, right: str) -> dict[str, float]:
    a = _canonical_tokens(left)
    b = _canonical_tokens(right)
    structure = difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()
    aw, bw = _semantic_words(left), _semantic_words(right)
    semantic = len(aw & bw) / len(aw | bw) if aw | bw else 1.0
    ash, bsh = _shingles(a), _shingles(b)
    shingles = len(ash & bsh) / len(ash | bsh) if ash | bsh else 1.0
    return {"structure": structure, "semantic": semantic, "shingles": shingles, "combined": 0.45 * structure + 0.25 * semantic + 0.30 * shingles}


def _artifact_dimensions(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text())
    task_id = Path(config["files"]["solution"][0]).stem
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
    private = (root / ".meta/private_test.cpp").read_text(encoding="utf-8")
    visible = (root / "visible_test.cpp").read_text(encoding="utf-8")
    instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    header_text = (root / f"{task_id}.h").read_text(encoding="utf-8")
    public_api = "\n".join(
        line for line in header_text.splitlines()
        if not line.startswith("#") and line.strip() not in {"namespace coordinate_transform {", "namespace navigation_transform {", "}"}
    )
    mutation = "\n".join(line for line in reference.splitlines() if re.search(r"\b(if|for|while|switch|sort|swap|push_back)\b|(?:^|[^=!<>])=(?!=)", line))
    diff = "\n".join(difflib.unified_diff(reference.splitlines(), negative.splitlines(), lineterm=""))
    return {
        "public_api": public_api,
        "owned_state_or_algorithm": instructions + "\n" + reference,
        "mutation_or_selection_rules": mutation,
        "invalid_and_boundary_behavior": instructions + "\n" + private,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + private,
        "topic_specific_negative_fixture": diff + "\n" + negative,
    }


def _pair_decision(left_id: str, right_id: str, left: dict[str, str], right: dict[str, str], *, clone_expected: bool) -> dict[str, object]:
    per_dimension: dict[str, object] = {}
    for dimension in DIMENSIONS:
        score = _similarity(left[dimension], right[dimension])
        threshold = 0.81 if dimension == "public_api" else (0.83 if dimension == "invalid_and_boundary_behavior" else 0.82)
        materially_distinct = score["combined"] < threshold
        per_dimension[dimension] = {**score, "threshold": threshold, "pass": materially_distinct}
    passed = all(bool(value["pass"]) for value in per_dimension.values())
    if clone_expected:
        passed = not any(bool(value["pass"]) for value in per_dimension.values())
    return {"left": left_id, "right": right_id, "clone_expected": clone_expected, "dimensions": per_dimension, "pass": passed}


def diversity_screen(out: Path = DEFAULT_OUT) -> dict[str, object]:
    materials = {case.task_id: _artifact_dimensions(out / case.task_id) for case in CASES}
    decisions = [_pair_decision(a.task_id, b.task_id, materials[a.task_id], materials[b.task_id], clone_expected=False) for a, b in combinations(CASES, 2)]
    failures = [row for row in decisions if not row["pass"]]
    if len(decisions) != 300 or failures:
        _fail("duplicate_family", json.dumps(failures[:3], sort_keys=True)[:3000])
    controls_record = json.loads((out / ".state/controls/controls.json").read_text())
    source_id = controls_record["source_task"]
    controls: dict[str, object] = {}
    for name, record in controls_record["controls"].items():
        control_root = out / record["root"]
        decision = _pair_decision(source_id, name, materials[source_id], _artifact_dimensions(control_root), clone_expected=True)
        if not decision["pass"]:
            _fail("adversarial_clone_escaped", json.dumps(decision, sort_keys=True)[:2000])
        controls[name] = {**record, "decision": decision, "semantic_rejection": "pass"}
    cross_alias_path = out / ".state/controls/cross-alias-controls.json"
    cross_alias_state = json.loads(cross_alias_path.read_text())
    for control in cross_alias_state["controls"]:
        marker = _mechanism_alias_marker(control["left"], control["right"])
        if list(marker or ()) != control["expected_marker"]:
            _fail("adversarial_clone_escaped", control["control_id"])
        control["observed_marker"] = list(marker)
        control["decision"] = "duplicate_family"
        control["status"] = "pass"
    cross_alias_state["status"] = "pass"
    _write_json(cross_alias_path, cross_alias_state)
    result = {"schema_version": "coordinate-diversity-screen-v1", "normalizer": NORMALIZER, "root_count": 25, "pair_count": 300, "dimensions": list(DIMENSIONS), "decisions": decisions, "controls": controls, "cross_alias_controls": cross_alias_state["controls"], "status": "pass"}
    _write_json(out / ".state/diversity-screen.json", result)
    return result


def _role_prompt_check(out: Path, case: Case) -> dict[str, object]:
    root = out / case.task_id
    config = json.loads((root / ".meta/config.json").read_text())
    expected_solution = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
    expected_example = [".meta/example.h", ".meta/example.cpp"]
    if config.get("files", {}).get("solution") != expected_solution or config["files"].get("example") != expected_example:
        _fail("target_reference_mismatch", case.task_id)
    role_paths: list[str] = []
    for role in ("solution", "test", "example"):
        values = config["files"].get(role)
        if not isinstance(values, list) or not values:
            _fail("role_conflict", f"{case.task_id}:{role}")
        for value in values:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                _fail("unsafe_path", f"{case.task_id}:{value}")
            role_paths.append(value)
    if len(role_paths) != len(set(role_paths)):
        _fail("role_conflict", f"{case.task_id}:overlap")
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_nlink != 1:
            _fail("invalid_output_root", f"hardlink:{path}")
    task = load_task(root)
    prompt = build_prompt(task)
    forbidden = (".meta/", "CMakeLists.txt", "private_test.cpp", "negative.cpp", "example.cpp", case.reference[:80])
    if any(value and value in prompt for value in forbidden):
        _fail("prompt_contract_incomplete", case.task_id)
    response = "\n\n".join(
        f"{target}\n```cpp\n{(root / example).read_text(encoding='utf-8').rstrip()}\n```"
        for target, example in zip(expected_solution, expected_example, strict=True)
    )
    parsed = parse_whole_file_blocks(response)
    if list(parsed) != expected_solution:
        _fail("whole_format_failed", case.task_id)
    return {"task_id": case.task_id, "prompt_hash": _sha(prompt.encode()), "prompt_files": [".docs/introduction.md", ".docs/instructions.md", *expected_solution], "whole_format": "pass", "roles": "pass"}


def _corpus_document(root: Path) -> str:
    paths = [root / ".docs/instructions.md", root / ".meta/example.cpp", root / ".meta/private_test.cpp"]
    header = next(root.glob("*.h"), None)
    if header:
        paths.append(header)
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in paths if path.is_file())


def contamination_screen(out: Path = DEFAULT_OUT) -> dict[str, object]:
    inventory = json.loads((out / ".state/source-inventory.json").read_text())
    existing_roots: list[tuple[str, Path]] = []
    for value in inventory["roots"].values():
        for task_id, relative in value["records"]:
            root = REPO_ROOT / relative
            if root.is_dir():
                existing_roots.append((task_id, root))
    found_holdouts = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    if found_holdouts != OFFICIAL_HOLDOUTS:
        _fail("benchmark_screen_not_completed", f"expected=26 found={len(found_holdouts)}")
    existing_docs = [(task_id, _corpus_document(root)) for task_id, root in existing_roots]
    holdout_docs = [(task_id, "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in sorted((HOLDOUT_ROOT / task_id).rglob("*")) if p.is_file() and p.stat().st_size <= 1_000_000)) for task_id in sorted(OFFICIAL_HOLDOUTS)]
    comparisons: list[dict[str, object]] = []
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for case in CASES:
        root = out / case.task_id
        prompt_hash = _sha(build_prompt(load_task(root)).encode())
        reference_hash = _file_sha(root / ".meta/example.cpp")
        if prompt_hash in prompt_hashes or reference_hash in reference_hashes:
            _fail("duplicate_family", case.task_id)
        prompt_hashes.add(prompt_hash)
        reference_hashes.add(reference_hash)
        candidate = _corpus_document(root)
        cwords = _semantic_words(candidate)
        for kind, records in (("existing", existing_docs), ("holdout", holdout_docs)):
            for other_id, other in records:
                owords = _semantic_words(other)
                jaccard = len(cwords & owords) / len(cwords | owords) if cwords | owords else 1.0
                marker = _mechanism_alias_marker(candidate, other)
                if jaccard >= 0.70 or marker is not None:
                    detail = f"{case.task_id}:{other_id}:{jaccard:.3f}"
                    if marker is not None:
                        detail += f":mechanism-alias={'+'.join(marker)}"
                    _fail("benchmark_content_overlap" if kind == "holdout" else "duplicate_family", detail)
                comparisons.append({"task_id": case.task_id, "other_id": other_id, "scope": kind, "semantic_jaccard": jaccard, "mechanism_alias": None})
    result = {"schema_version": "coordinate-contamination-screen-v1", "normalizer": NORMALIZER, "existing_root_count": len(existing_docs), "holdout_root_count": len(holdout_docs), "comparison_count": len(comparisons), "max_similarity": max((row["semantic_jaccard"] for row in comparisons), default=0.0), "inventory_hash": inventory["all_ids_hash"], "status": "pass"}
    _write_json(out / ".state/contamination-screen.json", result)
    return result


def _root_receipt(out: Path, case: Case, prompt: dict[str, object]) -> dict[str, object]:
    root = out / case.task_id
    roles = {
        "prompt": [".docs/introduction.md", ".docs/instructions.md", f"{case.task_id}.h", f"{case.task_id}.cpp"],
        "starter": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
        "reference": [".meta/example.h", ".meta/example.cpp"],
        "tests": ["visible_test.cpp", ".meta/private_test.cpp"],
        "negative": [".meta/negative.cpp"],
        "metadata": [".meta/config.json", ".meta/provenance.json", ".meta/tests.toml"],
    }
    return {"task_id": case.task_id, "lineage": "new-root", "primary_core_objective": "achieved", "mechanism": case.mechanism, "prompt_hash": prompt["prompt_hash"], "role_hashes": {role: {path: _file_sha(root / path) for path in paths} for role, paths in roles.items()}, "tree_hash": _tree_hash(root), "discriminator": {"path": ".meta/negative.cpp", "expected": "compile_and_executed_test_rejection"}, "status": "structural_pass_pending_docker_sanity"}


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    out = _safe_out(out)
    manifest_path = out / ".state/manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "missing manifest")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("owner") != OWNER or manifest.get("task_ids") != [case.task_id for case in CASES] or manifest.get("task_count") != 25:
        _fail("generator_output_drift", "manifest inventory")
    if manifest.get("tree_hash") != _tree_hash(out):
        _fail("generator_output_drift", "tree hash")
    inventory = _task_inventory(exclude=out)
    if inventory["all_ids_hash"] != json.loads((out / ".state/source-inventory.json").read_text())["all_ids_hash"]:
        _fail("source_inventory_drift", "existing trees changed after materialization")
    if set(manifest["task_ids"]) & set(inventory["all_ids"]):
        _fail("existing_task_id", "late collision")
    prompts = [_role_prompt_check(out, case) for case in CASES]
    diversity = diversity_screen(out)
    contamination = contamination_screen(out)
    roots = [_root_receipt(out, case, prompt) for case, prompt in zip(CASES, prompts, strict=True)]
    receipt = {
        "schema_version": "coordinate-creator-preflight-v1",
        "owner": OWNER,
        "owner_hash": _file_sha(REPO_ROOT / OWNER),
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "focused_test_hash": _file_sha(FOCUSED_TEST),
        "tree_hash": _tree_hash(out),
        "root_count": 25,
        "pair_count": diversity["pair_count"],
        "control_count": len(diversity["controls"]),
        "prompt_boundary": {"count": len(prompts), "status": "pass"},
        "diversity": {"dimensions": list(DIMENSIONS), "status": "pass"},
        "contamination": contamination,
        "roots": roots,
        "runtime": "pending_mandatory_docker_sanity",
        "status": "structural_pass_pending_runtime",
    }
    _write_json(out / ".state/creator-preflight.json", receipt)
    return receipt


def _replace_reference(root: Path) -> None:
    config = json.loads((root / ".meta/config.json").read_text())
    for target, example in zip(config["files"]["solution"], config["files"]["example"], strict=True):
        shutil.copy2(root / example, root / target)


def _test_count(build: Path) -> int:
    listed = subprocess.run(["ctest", "--test-dir", str(build), "-N"], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
    match = re.search(r"Total Tests:\s*(\d+)", listed)
    if not match:
        _fail("test_discovery_failed", listed[-1000:])
    return int(match.group(1))


def _compiler_path() -> str:
    """Resolve the locked C++ compiler for the current runtime environment.

    Inside the designated sanity image the pinned `/usr/local/bin/g++` is
    required and used. On a host without that path (host-only verification),
    fall back to the `c++`/`g++` on PATH; `W8_COORDINATE_CXX` overrides both.
    """
    override = os.environ.get(COMPILER_ENV)
    if override:
        if not Path(override).is_file():
            _fail("host_compiler_not_found", f"{COMPILER_ENV}={override}")
        return override
    if Path(IMAGE_COMPILER).is_file():
        return IMAGE_COMPILER
    for name in ("c++", "g++"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    _fail("host_compiler_not_found", f"missing {IMAGE_COMPILER} and no c++/g++ on PATH")
    raise AssertionError("unreachable")


def _runtime_mode(root: Path, workspace: Path, *, sanitizer: bool) -> dict[str, object]:
    work = workspace / root.name
    shutil.copytree(root, work)
    _replace_reference(work)
    build = work / "build"
    command = ["cmake", "-S", str(work), "-B", str(build), "-G", "Unix Makefiles", f"-DCMAKE_CXX_COMPILER={_compiler_path()}"]
    if sanitizer:
        command += ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
    configured = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if configured.returncode:
        _fail("reference_compile_failed", f"{root.name}:{'sanitizer' if sanitizer else 'normal'}:{configured.stdout[-4000:]}")
    built = subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if built.returncode:
        _fail("reference_compile_failed", f"{root.name}:{'sanitizer' if sanitizer else 'normal'}:{built.stdout[-4000:]}")
    count = _test_count(build)
    if count != 3:
        _fail("test_discovery_failed", f"{root.name}:{count}")
    env = os.environ.copy()
    if sanitizer:
        env.update({"ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})
    tested = subprocess.run(["ctest", "--test-dir", str(build), "--output-on-failure"], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if tested.returncode:
        _fail("reference_sanitizer_failed" if sanitizer else "reference_tests_failed", f"{root.name}:{tested.stdout[-5000:]}")
    negative = subprocess.run([str(build / "negative")], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if negative.returncode == 0:
        _fail("negative_fixture_not_rejected", root.name)
    return {"mode": "sanitizer" if sanitizer else "normal", "discovered_tests": count, "ctest_status": "pass", "negative_exit": negative.returncode, "negative_rejected": True, "configure_command": command}


def _toolchain() -> dict[str, str]:
    compiler = Path(_compiler_path())
    compiler_version = subprocess.run([str(compiler), "--version"], check=True, text=True, stdout=subprocess.PIPE).stdout.splitlines()[0]
    cmake_version = subprocess.run(["cmake", "--version"], check=True, text=True, stdout=subprocess.PIPE).stdout.splitlines()[0]
    return {"compiler_path": str(compiler), "compiler_version": compiler_version, "compiler_hash": _file_sha(compiler), "cmake_version": cmake_version}


def verify_runtime(out: Path = DEFAULT_OUT, *, result_out: Path | None = None) -> dict[str, object]:
    preflight = verify_core(out)
    in_grader = os.environ.get(GRADER_ENV) == "docker"
    records: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="coordinate-runtime-") as temp:
        temp_root = Path(temp)
        for case in CASES:
            normal = _runtime_mode(out / case.task_id, temp_root / "tasks-normal", sanitizer=False)
            sanitizer = _runtime_mode(out / case.task_id, temp_root / "tasks-sanitizer", sanitizer=True)
            if normal["discovered_tests"] <= 0 or normal["discovered_tests"] != sanitizer["discovered_tests"]:
                _fail("sanitizer_test_count_mismatch", case.task_id)
            records.append({"task_id": case.task_id, "normal": normal, "sanitizer": sanitizer})
        control_records: list[dict[str, object]] = []
        controls = json.loads((out / ".state/controls/controls.json").read_text())["controls"]
        for name, control in controls.items():
            root = out / control["root"]
            normal = _runtime_mode(root, temp_root / "controls-normal", sanitizer=False)
            sanitizer = _runtime_mode(root, temp_root / "controls-sanitizer", sanitizer=True)
            if normal["discovered_tests"] != sanitizer["discovered_tests"]:
                _fail("sanitizer_test_count_mismatch", name)
            control_records.append({"control": name, "changed_files": control["changed_files"], "normal": normal, "sanitizer": sanitizer, "behavior_tests_pass": True, "semantic_clone_rejected": True})
    receipt = {
        "schema_version": "coordinate-runtime-v1",
        "evidence_class": "docker_sanity" if in_grader else "host_runtime",
        "locked_oracle": False,
        "network_policy": "none" if in_grader else "host_not_enforced",
        "tree_hash": _tree_hash(out),
        "owner_hash": _file_sha(REPO_ROOT / OWNER),
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "focused_test_hash": _file_sha(FOCUSED_TEST),
        "preflight_hash": _sha(json.dumps(preflight, sort_keys=True).encode()),
        "toolchain": _toolchain(),
        "root_count": len(records),
        "records": records,
        "control_count": len(control_records),
        "controls": control_records,
        "status": "pass",
    }
    destination = result_out or out / ".state/docker-runtime-unimported.json"
    _write_json(destination, receipt)
    return receipt


def _deterministic_archive(source: Path, destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for path in sorted(source.rglob("*")):
            info = archive.gettarinfo(str(path), arcname=path.relative_to(source).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            if path.is_file():
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
            else:
                archive.addfile(info)


def docker_sanity(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    out = _safe_out(out)
    verify_core(out)
    inspected = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if inspected.returncode:
        _fail("docker_sanity_not_completed", inspected.stderr.strip())
    image_id = inspected.stdout.strip()
    if image != SANITY_IMAGE or image_id != SANITY_IMAGE_ID:
        _fail("docker_sanity_receipt_invalid", f"{image}:{image_id}")
    live_hash = _tree_hash(out)
    with tempfile.TemporaryDirectory(prefix="coordinate-docker-snapshot-") as temp:
        temp_root = Path(temp)
        snapshot = temp_root / "family"
        results = temp_root / "results"
        results.mkdir()
        shutil.copytree(out, snapshot)
        if _tree_hash(snapshot) != live_hash:
            _fail("grader_mount_hash_mismatch", "host snapshot")
        archive = temp_root / "family.tar"
        _deterministic_archive(snapshot, archive)
        container_family = "/repo/.w8-biayn/data/aider-tasks-expansion-v1/text-grid/coordinate-transformations"
        command = [
            "docker", "run", "--rm", "--network", "none",
            "-v", f"{REPO_ROOT}:/repo:ro",
            "-v", f"{snapshot}:{container_family}:rw",
            "-v", f"{results}:/result:rw",
            "-w", "/repo", "-e", "PYTHONPATH=/repo/src", "-e", f"{GRADER_ENV}=docker", image,
            "python3", "-m", "w8_biayn.integrations.moonlight_coordinate_transformations_aider_tasks",
            "--verify-runtime", "--result-out", "/result/runtime.json",
        ]
        completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if completed.returncode:
            _fail("docker_sanity_failed", completed.stdout[-16000:])
        result_path = results / "runtime.json"
        if not result_path.is_file():
            _fail("docker_sanity_failed", "missing runtime result")
        receipt = json.loads(result_path.read_text())
        receipt.update({
            "image": image,
            "image_id": image_id,
            "docker_command": command[:10] + ["<snapshot-mounts>", image, "python3", "-m", "<owner>"],
            "live_tree_hash": live_hash,
            "mounted_tree_hash": receipt["tree_hash"],
            "archive_hash": _file_sha(archive),
            "snapshot_transport": "owner-created deterministic tar plus exact nested bind mount",
        })
    if receipt.get("tree_hash") != live_hash or receipt.get("owner_hash") != _file_sha(REPO_ROOT / OWNER) or receipt.get("root_count") != 25 or receipt.get("control_count") != 3:
        _fail("docker_sanity_receipt_invalid", "identity/count binding")
    for record in receipt["records"]:
        if record["normal"]["discovered_tests"] != 3 or record["sanitizer"]["discovered_tests"] != 3 or not record["normal"]["negative_rejected"] or not record["sanitizer"]["negative_rejected"]:
            _fail("docker_sanity_receipt_invalid", str(record.get("task_id")))
    for control in receipt["controls"]:
        if not control["changed_files"] or not control["behavior_tests_pass"] or not control["semantic_clone_rejected"]:
            _fail("adversarial_control_invalid", str(control.get("control")))
    _write_json(out / ".state/docker-sanity.json", receipt)
    controls_path = out / ".state/controls/controls.json"
    controls_state = json.loads(controls_path.read_text())
    for control in receipt["controls"]:
        state = controls_state["controls"][control["control"]]
        state["behavior_execution"] = "pass_normal_and_fresh_sanitizer"
        state["semantic_rejection"] = "pass_all_seven_dimensions"
    _write_json(controls_path, controls_state)
    diversity_path = out / ".state/diversity-screen.json"
    diversity_state = json.loads(diversity_path.read_text())
    for control in receipt["controls"]:
        state = diversity_state["controls"][control["control"]]
        state["behavior_execution"] = "pass_normal_and_fresh_sanitizer"
        state["semantic_rejection"] = "pass_all_seven_dimensions"
    _write_json(diversity_path, diversity_state)
    preflight_path = out / ".state/creator-preflight.json"
    preflight = json.loads(preflight_path.read_text())
    preflight.update({"runtime": {"status": "pass", "receipt_path": ".state/docker-sanity.json", "receipt_hash": _file_sha(out / ".state/docker-sanity.json"), "evidence_class": "docker_sanity", "locked_oracle": False}, "status": "creator_preflight_pass_pending_independent_audit"})
    _write_json(preflight_path, preflight)
    manifest_path = out / ".state/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update({"status": "creator_preflight_pass_pending_independent_audit", "docker_receipt": ".state/docker-sanity.json", "docker_receipt_hash": _file_sha(out / ".state/docker-sanity.json")})
    _write_json(manifest_path, manifest)
    _write_json(out / ".state/root-status.json", {"schema_version": "coordinate-root-status-v1", "tree_hash": live_hash, "roots": [{"task_id": case.task_id, "primary_core_objective": "achieved", "state": "semantically_admitted", "runtime": "pass", "independent_audit": "pending"} for case in CASES]})
    cycle_01_exists = (REPO_ROOT / CYCLE_01_AUDIT_RELATIVE).is_file()
    cycle_02_exists = (REPO_ROOT / CYCLE_02_AUDIT_RELATIVE).is_file()
    cycle_03_exists = (REPO_ROOT / CYCLE_03_AUDIT_RELATIVE).is_file()
    cycle_04_exists = (REPO_ROOT / CYCLE_04_AUDIT_RELATIVE).is_file()
    cycle = 5 if cycle_04_exists else 4 if cycle_03_exists else 3 if cycle_02_exists else 2 if cycle_01_exists else 1
    cycle_path = out / f".state/cycles/cycle-{cycle:02d}-creator-preflight.json"
    if cycle == 1 and cycle_path.exists():
        return receipt
    remedy_paths = [
        *(out / ".state/remedy" / f"{finding_id}.json" for finding_id in CYCLE_01_FINDINGS),
        *(out / ".state/remedy/cycle-02" / f"{finding_id}.json" for finding_id in CYCLE_02_FINDINGS),
        *(out / ".state/remedy/cycle-03" / f"{finding_id}.json" for finding_id in CYCLE_03_FINDINGS),
        *(out / ".state/remedy/cycle-04" / f"{finding_id}.json" for finding_id in CYCLE_04_FINDINGS),
    ]
    remedy_hashes = {
        path.relative_to(out / ".state/remedy").as_posix(): _file_sha(path)
        for path in remedy_paths
        if path.is_file()
    }
    if cycle_04_exists:
        prior_subject = CYCLE_04_SUBJECT
        prior_report = CYCLE_04_AUDIT_RELATIVE.as_posix()
        finding_ids = sorted(CYCLE_04_FINDINGS)
    elif cycle_03_exists:
        prior_subject = CYCLE_03_SUBJECT
        prior_report = CYCLE_03_AUDIT_RELATIVE.as_posix()
        finding_ids = sorted(CYCLE_03_FINDINGS)
    elif cycle_02_exists:
        prior_subject = CYCLE_02_SUBJECT
        prior_report = CYCLE_02_AUDIT_RELATIVE.as_posix()
        finding_ids = sorted(CYCLE_02_FINDINGS)
    elif cycle_01_exists:
        prior_subject = CYCLE_01_SUBJECT
        prior_report = CYCLE_01_AUDIT_RELATIVE.as_posix()
        finding_ids = sorted(CYCLE_01_FINDINGS)
    else:
        prior_subject = None
        prior_report = None
        finding_ids = []
    _write_json(cycle_path, {
        "schema_version": "aider-creation-cycle-v1",
        "cycle": cycle,
        "family_id": FAMILY_ID,
        "tree_hash": live_hash,
        "owner_hash": _file_sha(REPO_ROOT / OWNER),
        "curriculum_hash": _file_sha(CURRICULUM),
        "family_spec_hash": _file_sha(FAMILY_SPEC),
        "focused_test_hash": _file_sha(FOCUSED_TEST),
        "grader_policy_hash": _sha(json.dumps({"image": image, "network": "none", "normalizer": NORMALIZER}, sort_keys=True).encode()),
        "creator_preflight": "pass",
        "prior_audit_subject_hash": prior_subject,
        "prior_audit_report": prior_report,
        "finding_ids": finding_ids,
        "prior_audit_invalidation_reason": CYCLE_04_INVALIDATION_REASON if cycle_04_exists else None,
        "remedy_hashes": remedy_hashes,
        "audit_subject_hash": None,
        "audit_report": None,
        "status": "auditing",
        "dataset_handoff": "not_requested",
    })
    return receipt


def record_independent_audit(out: Path, report: Path, *, cycle: int, decision: str) -> dict[str, object]:
    out = _safe_out(out)
    report = report.resolve(strict=True)
    audit_root = (REPO_ROOT / "docs/aider-tasks-spec/audits").resolve(strict=True)
    if audit_root not in report.parents:
        _fail("audit_report_invalid", str(report))
    if cycle < 1 or decision not in {"not_completed", "local_family_verified"}:
        _fail("audit_report_invalid", f"cycle={cycle}:decision={decision}")
    tree_hash = _tree_hash(out)
    report_text = report.read_text(encoding="utf-8")
    if tree_hash not in report_text or f"`{decision}`" not in report_text:
        _fail("audit_subject_mismatch", f"{tree_hash}:{decision}")
    cycle_path = out / f".state/cycles/cycle-{cycle:02d}-creator-preflight.json"
    if not cycle_path.is_file():
        _fail("audit_subject_mismatch", f"missing {cycle_path.name}")
    cycle_state = json.loads(cycle_path.read_text())
    if cycle_state.get("tree_hash") != tree_hash or cycle_state.get("creator_preflight") != "pass":
        _fail("audit_subject_mismatch", "creator preflight binding")
    receipt = {
        "schema_version": "coordinate-independent-audit-v1",
        "cycle": cycle,
        "family_id": FAMILY_ID,
        "tree_hash": tree_hash,
        "report": report.relative_to(REPO_ROOT).as_posix(),
        "report_hash": _file_sha(report),
        "decision": decision,
        "status": "pass" if decision == "local_family_verified" else "findings_open",
    }
    _write_json(out / f".state/audits/cycle-{cycle:02d}.json", receipt)
    cycle_state.update({
        "audit_subject_hash": tree_hash,
        "audit_report": receipt["report"],
        "audit_report_hash": receipt["report_hash"],
        "status": "complete" if decision == "local_family_verified" else "remediation_required",
        "decision": decision,
    })
    _write_json(cycle_path, cycle_state)
    if decision == "local_family_verified":
        manifest_path = out / ".state/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("tree_hash") != tree_hash or manifest.get("status") != "creator_preflight_pass_pending_independent_audit":
            _fail("audit_subject_mismatch", "manifest binding")
        manifest.update({
            "status": "local_family_verified",
            "independent_audit": receipt["report"],
            "independent_audit_hash": receipt["report_hash"],
            "verification_cycle": cycle,
        })
        _write_json(manifest_path, manifest)
        status_path = out / ".state/root-status.json"
        root_status = json.loads(status_path.read_text())
        if root_status.get("tree_hash") != tree_hash:
            _fail("audit_subject_mismatch", "root status binding")
        for root in root_status["roots"]:
            root["state"] = "local_family_verified"
            root["independent_audit"] = "pass"
        root_status.update({"status": "local_family_verified", "audit_report_hash": receipt["report_hash"]})
        _write_json(status_path, root_status)
    return receipt


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-runtime", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--record-audit", type=Path)
    parser.add_argument("--audit-cycle", type=int)
    parser.add_argument("--audit-decision", choices=("not_completed", "local_family_verified"))
    parser.add_argument("--image", default=SANITY_IMAGE)
    parser.add_argument("--result-out", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.materialize:
        materialize(args.out, force=args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_runtime:
        verify_runtime(args.out, result_out=args.result_out)
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    if args.record_audit:
        if args.audit_cycle is None or args.audit_decision is None:
            _fail("audit_report_invalid", "--record-audit requires --audit-cycle and --audit-decision")
        record_independent_audit(args.out, args.record_audit, cycle=args.audit_cycle, decision=args.audit_decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
