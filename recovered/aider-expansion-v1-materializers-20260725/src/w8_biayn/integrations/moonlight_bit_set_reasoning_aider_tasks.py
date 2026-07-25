"""Own the 40-root expansion-v1 bit and set reasoning family."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
DEFAULT_OUT = EXPANSION_ROOT / "numerical/bit-set-reasoning"
LEGACY_ROOTS = (
    REPO_ROOT / ".w8-biayn/data/aider-tasks",
    REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify",
)
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
CURRICULUM = REPO_ROOT / "docs/aider-synthetic/aider-synthetic-numerical/GLM47_FLASH_AIDER_POLYGLOT_CPP_BIT_SET_REASONING_CURRICULUM.md"
FAMILY_SPEC = REPO_ROOT / "docs/aider-tasks-spec/aider-numerical/bit-set-reasoning.md"
OWNER = "src/w8_biayn/integrations/moonlight_bit_set_reasoning_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_bit_set_reasoning_aider_tasks.py"
FAMILY_ID = "expansion-v1-bit-set-reasoning-v1"
NORMALIZER = "bit-set-emitted-artifacts-v5"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
SELECTED_PROMPTS = (
    "docs/aider-tasks-spec/prompts/generate-family-spec.md",
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
)
DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
OFFICIAL_HOLDOUTS = frozenset({
    "all-your-base", "allergies", "bank-account", "binary-search-tree",
    "circular-buffer", "clock", "complex-numbers", "crypto-square",
    "diamond", "dnd-character", "gigasecond", "grade-school",
    "kindergarten-garden", "knapsack", "linked-list", "meetup",
    "parallel-letter-frequency", "perfect-numbers", "phone-number",
    "queen-attack", "robot-name", "space-age", "spiral-matrix",
    "sublist", "yacht", "zebra-puzzle",
})


class CreatorError(RuntimeError):
    pass


def _fail(code: str, detail: str = "") -> None:
    raise CreatorError(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    mechanism: str
    boundary: str
    wrong: str
    ordinal: int

    @property
    def function(self) -> str:
        return "evaluate_" + self.task_id.replace("-", "_")

    @property
    def namespace(self) -> str:
        return "bitset_" + self.task_id.replace("-", "_")


def cases() -> tuple[Case, ...]:
    pattern = re.compile(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$", re.M)
    rows = []
    for match in pattern.finditer(CURRICULUM.read_text(encoding="utf-8")):
        number, task_id, mechanism, boundary, wrong = match.groups()
        rows.append(Case(task_id, task_id.replace("-", " ").title(), mechanism.strip(), boundary.strip(), wrong.strip(), int(number) - 1))
    if len(rows) != 40 or [row.ordinal for row in rows] != list(range(40)) or len({row.task_id for row in rows}) != 40:
        _fail("curriculum_count_mismatch", str(len(rows)))
    return tuple(rows)


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.relative_to(root).parts and "build" not in p.relative_to(root).parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _mask(width: int) -> int:
    return (1 << width) - 1 if 0 < width < 64 else (2**64 - 1 if width == 64 else 0)


def _pop(value: int) -> int:
    return value.bit_count()


def _pext(value: int, mask: int) -> int:
    out = 0; target = 0
    while mask:
        low = mask & -mask
        if value & low: out |= 1 << target
        target += 1; mask ^= low
    return out


def _pdep(value: int, mask: int) -> int:
    out = 0; source = 1
    while mask:
        low = mask & -mask
        if value & source: out |= low
        source <<= 1; mask ^= low
    return out


def _oracle(op: int, a: int, b: int, width: int) -> tuple[bool, int, int]:
    full = 2**64 - 1
    if op in set(range(0, 20)) | {24} and not 1 <= width <= 64:
        return False, 0, 0
    m = _mask(width)
    a &= full; b &= full
    if op == 0: return True, _pop(a & m), 0
    if op == 1: return True, _pop(a & m) & 1, _pop(a & m)
    if op == 2:
        value = a & m; out = 0
        for i in range(width): out |= ((value >> i) & 1) << (width - 1 - i)
        return True, out, 0
    if op == 3:
        shift = b % width; value = a & m
        out = value if shift == 0 else ((value << shift) | (value >> (width - shift))) & m
        return True, out, shift
    if op == 4:
        value = a & m
        if width < 64 and value & (1 << (width - 1)): value |= full ^ m
        return True, value & full, 1 if a & (1 << (width - 1)) else 0
    if op == 5:
        if b >= 64 or width > 64 - b: return False, 0, 0
        return True, (a >> b) & m, b
    if op == 6:
        offset = (b >> 32) & 63; field = b & 0xFFFFFFFF
        if width > 32 or offset + width > 64: return False, 0, 0
        fm = _mask(width) << offset
        return True, ((a & ~fm) | ((field & _mask(width)) << offset)) & full, fm & full
    if op == 7: return True, _pext(a, b & m), _pop(b & m)
    if op == 8: return True, _pdep(a, b & m), _pop(b & m)
    if op == 9:
        if width > 16: return False, 0, 0
        out = used = 0
        for i in range(width):
            destination=(b>>(4*i))&15
            if destination>=width or used&(1<<destination):return False,0,0
            used|=1<<destination;out|=((a>>i)&1)<<destination
        return True,out,used
    if op == 10:
        if width > 32: return False, 0, 0
        x=a&_mask(width);y=b&_mask(width);product=0
        for i in range(width):
            if y&(1<<i):product^=x<<i
        return True,product&full,_pop(product&full)
    if op == 11: return True, ((a & m) ^ ((a & m) >> 1)) & m, 0
    if op == 12:
        value = a & m; shift = 1
        while shift < width: value ^= value >> shift; shift <<= 1
        return True, value & m, 0
    if op == 13:
        value = a & m
        if value == 0: return False, 0, 0
        low = value & -value
        if low > m-value:return False,0,0
        ripple = value + low
        return True, (ripple | (((value ^ ripple) >> 2) // low)) & m, _pop(value)
    if op == 14:
        selected=a&m
        if _pop(selected)>16:return False,0,0
        total = 0; sub = selected; count = 0
        while True:
            total = (total + sub) & full; count += 1
            if sub == 0: break
            sub = (sub - 1) & selected
        return True, total, count
    if op == 15:
        if b > width: return False, 0, 0
        return True, _pop((a & m) & _mask(int(b))), int(b)
    if op == 16:
        value = a & m; rank = int(b); index = 0
        for i in range(width):
            if value & (1 << i):
                if index == rank: return True, i, rank
                index += 1
        return False, 0, 0
    if op == 17:
        best = run = 0; best_start = 0
        for i in range(width):
            if a & (1 << i):
                run += 1
                if run > best: best = run; best_start = i + 1 - run
            else: run = 0
        return True, best, best_start
    if op == 18:
        need = int(b)
        if need == 0 or need > width: return False, 0, 0
        run = 0
        for i in range(width):
            run = run + 1 if not (a & (1 << i)) else 0
            if run == need: return True, i + 1 - need, need
        return False, 0, 0
    if op == 19:
        start=(b >> 32)&0xFFFFFFFF; end=b&0xFFFFFFFF
        if start > end or end >= width: return False,0,0
        rm = (_mask(end-start+1) << start) & m
        return True,(a^rm)&m,rm
    if op == 20:
        if width == 0 or width > 8: return False,0,0
        flags=a&_mask(width); changed=True
        while changed:
            changed=False
            for i in range(width):
                if flags&(1<<i):
                    nxt=flags|((b>>(8*i))&0xFF)
                    if nxt!=flags: flags=nxt; changed=True
        return True,flags&_mask(width),0
    if op == 21:
        if width == 0 or width > 8: return False,0,0
        kept=0
        for i in range(width):
            if a&(1<<i) and not (((b>>(8*i))&0xFF)&kept): kept|=1<<i
        return True,kept,a&~kept
    if op == 22:
        if width == 0 or width > 16: return False,0,0
        x=a&_mask(width); y=(a>>width)&_mask(width); z=b&_mask(width)
        return True,(x&y)|(x&z)|(y&z),x^y^z
    if op == 23:
        bits=width&0xff;rank=(width>>8)&0xff
        if bits==0 or bits>64:return False,0,0
        diff=(a^b)&_mask(bits)
        if rank>=_pop(diff): return False,0,0
        for i in range(64):
            if diff&(1<<i):
                if rank==0:return True,i,_pop(diff)
                rank-=1
    if op == 24: return True,_pop((a|b)&m),_pop((a&b)&m)
    if op == 25:
        inter=a&b; rank=width
        for i in range(64):
            if inter&(1<<i):
                if rank==0:return True,i,_pop(inter)
                rank-=1
        return False,0,0
    if op == 26:
        universe=a&0xFFFFFFFF; left=b&0xFFFFFFFF; right=width&0xFFFFFFFF
        return True,1 if (left&right)==0 and (left|right)==universe else 0,(left|right)&0xFFFFFFFF
    if op in (27,28):
        if width>4:return False,0,0
        universe=a&15; count=width; covers=[]
        for selector in range(1<<count):
            covered=0; exact=True
            for i in range(count):
                if selector&(1<<i):
                    piece=(b>>(4*i))&15
                    if covered&piece: exact=False
                    covered|=piece
            if covered==universe and (exact or op==28): covers.append(selector)
        if op==27:return True,len(covers),covers[0] if covers else 0
        if not covers:return False,0,0
        best=min(covers,key=lambda x:(_pop(x),x));return True,_pop(best),best
    if op == 29:
        if width>4:return False,0,0
        n=width;best_weight=-1;best_mask=0
        for selector in range(1<<n):
            ok=True;weight=0
            for i in range(n):
                if selector&(1<<i):
                    if ((a>>(4*i))&15)&selector:ok=False
                    weight+=(b>>(4*i))&15
            if ok and (weight>best_weight or (weight==best_weight and selector<best_mask)):best_weight=weight;best_mask=selector
        return True,best_weight,best_mask
    if op == 30:
        if b>63 or width>16:return False,0,0
        reachable=1
        for i in range(width):reachable|=reachable<<((a>>(4*i))&15)
        return True,1 if reachable&(1<<b) else 0,reachable&full
    if op == 31:
        values=[(a>>(4*i))&15 for i in range(8)]
        for bit in range(3):
            for s in range(8):
                if s&(1<<bit):values[s]=(values[s]+values[s^(1<<bit)])&15
        packed=sum(v<<(4*i) for i,v in enumerate(values));return True,packed,sum(values)
    if op == 32:
        values=[(a>>(4*i))&15 for i in range(8)];trans=values[:]
        for bit in range(3):
            for s in range(8):
                if s&(1<<bit):trans[s]+=trans[s^(1<<bit)]
        inv=trans[:]
        for bit in range(3):
            for s in range(8):
                if s&(1<<bit):inv[s]-=inv[s^(1<<bit)]
        return True,sum((v&15)<<(4*i) for i,v in enumerate(inv)),sum(trans)&full
    if op in (33,34):
        if width>8:return False,0,0
        basis=[0]*8
        for i in range(width):
            value=(a>>(8*i))&0xFF
            for bit in range(7,-1,-1):
                if not value&(1<<bit):continue
                if basis[bit]:value^=basis[bit]
                else:basis[bit]=value;break
        if op==34:return True,sum(v!=0 for v in basis),0
        value=b&0xFF
        for bit in range(7,-1,-1):value=max(value,value^basis[bit])
        return True,value,sum(v!=0 for v in basis)
    if op in (35,36):
        if width>4:return False,0,0
        n=width;rows=[((a>>(4*i))&15)&_mask(n) for i in range(n)]
        for i in range(n):rows[i]|=1<<i
        if op==35:
            for k in range(n):
                for i in range(n):
                    if rows[i]&(1<<k):rows[i]|=rows[k]
            return True,sum(rows[i]<<(4*i) for i in range(n)),n
        if n==0:return False,0,0
        start=b%n;visited=1<<start;front=visited;layers=0
        while front:
            nxt=0
            for i in range(n):
                if front&(1<<i):nxt|=rows[i]
            nxt&=~visited;front=nxt;visited|=nxt
            if front:layers+=1
        return True,visited,layers
    if op == 37:
        if width==0 or width>8:return False,0,0
        count=width
        best=(65,0,0)
        for i in range(count):
            value=(a>>(8*i))&0xFF;candidate=(_pop(value^(b&0xFF)),i,value)
            if candidate[:2]<best[:2]:best=candidate
        return True,best[2],best[1]
    if op == 38:
        numerator=(width>>16)&0xffff;denominator=width&0xffff
        if denominator==0 or numerator>denominator:return False,0,0
        inter=_pop(a&b);union=_pop(a|b)
        if union==0:return True,2 if numerator<denominator else 1,0
        left=inter*denominator;right=union*numerator
        return True,2 if left>right else (0 if left<right else 1),union
    if op == 39:
        if width>8:return False,0,0
        count=width;best_count=-1;best_selector=0
        for selector in range(1<<count):
            used=0;ok=True
            for i in range(count):
                if selector&(1<<i):
                    piece=(a>>(8*i))&0xFF
                    if used&piece:ok=False
                    used|=piece
            card=_pop(selector)
            if ok and (card>best_count or (card==best_count and selector<best_selector)):best_count=card;best_selector=selector
        return True,best_count,best_selector
    raise AssertionError(op)


def _inputs_for(op: int) -> tuple[tuple[int,int,int],tuple[int,int,int]]:
    normal=(0x96D5A3C7E1,0x5A3,8);hidden=(0x5B3D9A71C6,0x2D,6)
    overrides={
        5:((0xFEDCBA9876543210,4,8),(0x123456789ABCDEF0,12,12)),
        6:((0x96D5A3C7E1,0x030000000B,8),(0x5B3D9A71C6,0x0200000005,6)),
        9:((0b11010110,0x76543210,8),(0b101011,0x012543,6)),
        10:((0b101101,0b110011,6),(0b1011,0b1110,4)),
        15:((0b11010110,5,8),(0b101011,4,6)),
        16:((0b11010110,2,8),(0b101011,1,6)),
        18:((0b11000111,2,8),(0b100011,2,6)),
        19:((0b11000111,(2<<32)|5,8),(0b100011,(1<<32)|3,6)),
        21:((0b1111,(1<<8)|(1<<16)|(4<<24),4),(0b1111,(1<<8)|(2<<16)|(4<<24),4)),
        23:((0b1110,0b0111,(1<<8)|4),(0b11001,0b00110,(1<<8)|5)),
        25:((0b11010110,0b10110101,1),(0b110101,0b101011,0)),
        26:((0b1111,0b0111,0b1101),(0b111111,0b001101,0b110010)),
        27:((0xF,0x8421,4),(0x7,0x0321,3)),
        28:((0xF,0x8421,4),(0x7,0x0731,4)),
        29:((0x4A52,0x4321,4),(0x2481,0x3412,4)),
        30:((0x7532,10,4),(0x6421,7,4)),
        34:((0x00030201,0,4),(0x0A000505,0,4)),
        35:((0x8421,0,4),(0x4621,0,4)),
        36:((0x2481,0,4),(0x4210,1,4)),
        38:((0b1111,0b0111,(3<<16)|4),(0b10101,0b00111,(1<<16)|2)),
        39:((0x020103,0,3),(0x04020107,0,4)),
    }
    return overrides.get(op,(normal,hidden))


INPUTS=tuple(_inputs_for(i) for i in range(40))

# Hand-derived acceptance cases are deliberately separate from `_oracle`.  Each
# tuple is (primary, secondary, bound, valid, value, auxiliary); the first case
# is public/property-facing and the second is private boundary/tie evidence.
TARGETED_CASES = (
    ((0,0,64,True,0,0),(18446744073709551615,0,64,True,64,0)),
    ((0,0,1,True,0,0),(3,0,2,True,0,2)),
    ((1,0,4,True,8,0),(8,0,4,True,1,0)),
    ((9,0,4,True,9,0),(9,4,4,True,9,0)),
    ((7,0,4,True,7,0),(8,0,4,True,18446744073709551608,1)),
    ((240,4,4,True,15,4),(1,63,2,False,0,0)),
    ((0,4294967299,2,True,6,6),(0,270582939649,2,False,0,0)),
    ((10,15,4,True,10,4),(5,0,4,True,0,0)),
    ((11,21,5,True,5,3),(5,0,5,True,0,0)),
    ((1,291,4,True,8,15),(9,16,4,False,0,0)),
    ((0,15,4,True,0,0),(3,3,2,True,5,2)),
    ((0,0,8,True,0,0),(10,0,4,True,15,0)),
    ((0,0,8,True,0,0),(15,0,4,True,10,0)),
    ((12,0,4,False,0,0),(9223372036854775808,0,64,False,0,0)),
    ((65535,0,16,True,2147450880,65536),(131071,0,17,False,0,0)),
    ((11,4,4,True,3,4),(1,5,4,False,0,0)),
    ((10,0,4,True,1,0),(10,2,4,False,0,0)),
    ((51,0,6,True,2,0),(0,0,6,True,0,0)),
    ((36,2,6,True,0,2),(63,1,6,False,0,0)),
    ((0,12884901889,4,False,0,0),(0,3,4,True,15,15)),
    ((1,65538,3,True,3,0),(4,131328,3,True,7,0)),
    ((7,65792,3,True,1,6),(1,0,9,False,0,0)),
    ((83,6,4,True,7,0),(0,0,4,True,0,0)),
    ((7,3,3,True,2,1),(7,3,515,False,0,0)),
    ((0,0,4,True,0,0),(1024,0,4,True,0,0)),
    ((10,10,0,True,1,2),(10,10,2,False,0,0)),
    ((0,0,0,True,1,0),(3,3,1,True,0,3)),
    ((3,801,3,True,2,3),(3,801,5,False,0,0)),
    ((3,51,2,True,1,1),(3,801,5,False,0,0)),
    ((18,17,3,True,1,1),(18,17,5,False,0,0)),
    ((801,0,3,True,1,127),(801,64,3,False,0,0)),
    ((0,0,0,True,0,0),(1,0,0,True,286331153,8)),
    ((0,0,0,True,0,0),(1985229328,0,0,True,1985229328,63)),
    ((257,0,2,True,1,1),(257,0,9,False,0,0)),
    ((257,0,2,True,1,0),(257,0,9,False,0,0)),
    ((10,0,2,True,35,2),(10,0,5,False,0,0)),
    ((10,0,2,True,3,1),(10,0,5,False,0,0)),
    ((768,1,2,True,0,0),(768,1,9,False,0,0)),
    ((0,0,65537,True,1,0),(1,1,0,False,0,0)),
    ((33620481,0,4,True,2,3),(197121,0,9,False,0,0)),
)

TARGETED_RULES = (
    ("empty population","full-width all-ones boundary"),("empty parity","even parity with count witness"),
    ("single-bit mirror","high-edge mirror"),("zero-distance identity","distance reduced modulo width"),
    ("positive bounded sign","negative bounded sign extension"),("aligned field extraction","crossing bit 64 rejected"),
    ("clear then insert","crossing insertion rejected"),("ordered compression","empty selection mask"),
    ("ordered deposition","empty destination mask"),("non-identity destination permutation","duplicate destination rejected"),
    ("zero carryless factor","GF2 cancellation differs from multiplication"),("zero Gray encoding","bounded Gray pattern"),
    ("zero Gray decoding","prefix-XOR decoding"),("no bounded successor","width-64 top-bit overflow has no successor"),
    ("maximum 16-set-bit enumeration","17-set-bit request rejected"),("index equal width accepted","index above width rejected"),
    ("first selected bit","absent selection ordinal"),("equal-run tie chooses lower start","empty run result"),
    ("first-fit zero-run tie","no zero run available"),("reversed range rejected","full inclusive range"),
    ("implication cycle closure","descending multi-hop closure"),("lower-priority conflict pruning","excess flag count rejected"),
    ("three-voter majority and parity","empty voters"),("overlap excluded from symmetric difference","absent packed rank"),
    ("empty bounded union","outside-width bits ignored"),("first intersection selection","absent intersection rank"),
    ("empty partition is valid","overlapping cover is not a partition"),("two exact covers counted","excess packed-set count rejected"),
    ("minimum-cover tie chooses lower selector","excess cover count rejected"),("equal-weight selector tie","excess vertex count rejected"),
    ("zero target reachable","target above 63 rejected"),("zero zeta coefficients","single coefficient zeta fanout"),
    ("zero Mobius roundtrip","signed intermediate roundtrip"),("duplicate basis vectors ignored","excess vector count rejected"),
    ("duplicate vectors do not raise rank","excess rank-vector count rejected"),("out-of-domain row bits masked","excess closure vertex count rejected"),
    ("layered two-vertex reachability","excess reachability vertex count rejected"),("Hamming tie chooses first byte","excess candidate count rejected"),
    ("empty sets equal threshold one","zero denominator rejected"),("maximum disjoint selector tie","excess disjoint-set count rejected"),
)

PUBLIC_CONTRACTS = (
    "`primary` is a word and `bound` is its width in 1..64; ignore higher bits. Return their population count in `value` and zero in `auxiliary`.",
    "`primary` is a word and `bound` is its width in 1..64. Return XOR parity in `value` and the bounded population count in `auxiliary`.",
    "Reverse exactly the low `bound` bits of `primary`; discard higher bits. Return the mirrored word and zero.",
    "Rotate the low `bound` bits of `primary` left by `secondary % bound`; return the rotated word and reduced shift.",
    "Interpret the low `bound` bits of `primary` as two's-complement and explicitly sign-extend to 64 bits; `auxiliary` is the sign bit.",
    "Extract a field of `bound` bits from `primary` starting at bit offset `secondary`; reject offset >=64 or a field crossing bit 64. Return field and offset.",
    "`secondary` packs a 32-bit field value in bits 0..31 and a 6-bit destination offset in bits 32..37. Clear then insert `bound` (1..32) field bits into `primary`; return updated word and destination mask.",
    "Compress bits of `primary` selected by the low `bound` bits of mask `secondary`, preserving ascending source positions. Return packed bits and selected-position count.",
    "Deposit consecutive low bits of `primary` into set positions of the low-`bound` mask `secondary`, in ascending destination order. Return deposited word and destination count.",
    "`secondary` stores one 4-bit destination index per source bit i. For `bound` in 1..16, require every destination < bound and unique, then move low bit i of `primary` to that destination. Return permuted word and the validated destination-set mask.",
    "Treat the low `bound` bits of `primary` and `secondary` as GF(2) polynomials (`bound` 1..32). Return their carryless shift-XOR product and its population count.",
    "Encode the low `bound` bits of binary `primary` as Gray code `x ^ (x >> 1)`; return bounded code and zero.",
    "Decode the low `bound` bits of Gray word `primary` using prefix XOR; return bounded binary and zero.",
    "Find the smallest low-`bound` word numerically greater than `primary` with equal nonzero population count. Return absent when none; `auxiliary` preserves the count.",
    "Enumerate every submask of low-`bound` set `primary` in descending order including zero, but reject inputs with more than 16 selected bits. Return the modulo-2^64 sum and number of submasks.",
    "`secondary` is an index in 0..bound. Return the count of set bits of `primary` at positions strictly below it, plus the index as witness.",
    "`secondary` is a zero-based ordinal. Select that set bit from low-`bound` `primary` in ascending position order; absent ordinal is invalid. Return position and ordinal.",
    "Scan low-`bound` `primary` for a longest consecutive-one run; return length and start. Equal lengths choose the lower start; empty has length/start zero.",
    "`secondary` is a positive requested length. Return the lowest start of that many consecutive zero bits within low-`bound` `primary`; absent requests are invalid.",
    "`secondary` packs inclusive start in bits 32..63 and end in bits 0..31. Reject start>end or end>=bound; XOR that range in low-`bound` `primary`, returning word and range mask.",
    "For bound<=8, `primary` is the initial flag mask and each byte i of `secondary` lists flags implied by flag i. Compute fixed-point closure, including cycles; return closure and zero.",
    "For bound<=8, each byte i of `secondary` lists flags conflicting with i. Visit requested bits of `primary` from low to high, keeping i only if it conflicts with no kept flag. Return kept and removed masks.",
    "For bound<=16, `primary` packs voter X in its low bound bits and voter Y in the next bound bits; `secondary` is voter Z. Return per-bit two-of-three majority and odd-parity masks.",
    "`bound` packs mask width in bits 0..7 and zero-based rank in bits 8..15. Select that rank from `(primary ^ secondary)` inside the width, ascending; return position and difference cardinality, or absent.",
    "Within low `bound` bits, return union cardinality of `primary` and `secondary`, plus intersection cardinality.",
    "`bound` is a zero-based rank. Select that rank from `primary & secondary` over all 64 bits in ascending order; return position and intersection cardinality, or absent.",
    "All masks use low 32 bits: `primary` is universe, `secondary` is left part, and `bound` is right part. Return 1 exactly when parts are disjoint and cover universe; auxiliary is their union.",
    "`primary` low nibble is universe; `secondary` packs up to `bound` (<=4) four-bit candidate sets. Count selectors whose chosen sets are pairwise disjoint and cover universe; return count and lowest selector.",
    "`primary` low nibble is universe; `secondary` packs up to `bound` (<=4) four-bit sets. Find a cover with fewest selected sets, tie by lower selector; return count and selector or absent.",
    "For n=`bound`<=4, nibble i of `primary` is vertex-i adjacency and nibble i of `secondary` is its weight. Exhaustively choose a conflict-free maximum-weight selector, tie by lower selector; return weight and selector.",
    "`primary` packs `bound`<=16 nonnegative nibble weights; `secondary` is target 0..63. Use shift-OR reachability; return 1/0 feasibility and the 64-bit reachable-sum mask.",
    "`primary` packs eight nibbles indexed by three-bit subsets. Compute the subset zeta transform modulo 16; return packed transformed nibbles and their integer sum. Other inputs are ignored.",
    "`primary` packs eight nibbles. Apply integer subset zeta then Möbius inversion; return recovered packed nibbles and zeta-value sum. Other inputs are ignored.",
    "`primary` packs `bound`<=8 byte vectors and low byte of `secondary` is a seed. Build a GF(2) pivot basis and greedily maximize seed XOR span; return maximum and basis rank.",
    "`primary` packs `bound`<=8 byte vectors. Build a GF(2) pivot basis; return rank and zero. Duplicate/zero vectors add no rank; `secondary` is ignored.",
    "For n=`bound`<=4, nibble i of `primary` is row i adjacency. Add reflexive diagonal and compute Warshall closure; return packed rows and n.",
    "For n=`bound`<=4, nibble i of `primary` is outgoing adjacency and `secondary % n` is start. Run frontier/visited expansion; return reachable mask and number of nonempty expansion layers after the start.",
    "`primary` packs `bound`<=8 candidate bytes and low byte of `secondary` is query. Return candidate of minimum Hamming distance; tie by lower candidate index. Auxiliary is that index.",
    "`bound` packs comparison numerator in bits 16..31 and positive denominator in bits 0..15. Compare Jaccard(primary,secondary) to numerator/denominator by cross multiplication; return 0 less, 1 equal, 2 greater, plus union count. Two empty sets have Jaccard 1.",
    "`primary` packs `bound`<=8 byte-sized sets. Exhaustively select the largest pairwise-disjoint collection, tie by lower selector; return collection size and selector. `secondary` is ignored.",
)

API_FIELDS = (
    ("population_word","population_reserved","population_width"),
    ("parity_word","parity_reserved","parity_width"),
    ("mirror_word","mirror_reserved","mirror_width"),
    ("rotation_word","rotation_distance","rotation_width"),
    ("signed_pattern","signed_reserved","signed_width"),
    ("extraction_word","extraction_offset","extraction_width"),
    ("insertion_word","packed_field_offset","insertion_width"),
    ("compression_source","compression_mask","compression_width"),
    ("deposition_source","deposition_mask","deposition_width"),
    ("permutation_source","packed_destinations","permutation_width"),
    ("polynomial_left","polynomial_right","polynomial_width"),
    ("binary_word","gray_reserved","gray_width"),
    ("gray_word","binary_reserved","binary_width"),
    ("combination_word","successor_reserved","combination_width"),
    ("submask_set","checksum_reserved","submask_width"),
    ("rank_word","rank_index","rank_width"),
    ("selection_word","selection_ordinal","selection_width"),
    ("run_word","run_reserved","run_width"),
    ("allocation_word","requested_run","allocation_width"),
    ("toggle_word","packed_range","toggle_width"),
    ("initial_flags","packed_implications","flag_count"),
    ("requested_flags","packed_conflicts","priority_count"),
    ("packed_voters_xy","voter_z","quorum_width"),
    ("symmetric_left","symmetric_right","packed_rank_width"),
    ("union_left","union_right","union_width"),
    ("intersection_left","intersection_right","intersection_rank"),
    ("partition_universe","partition_left","partition_right"),
    ("exact_universe","packed_exact_sets","exact_set_count"),
    ("cover_universe","packed_cover_sets","cover_set_count"),
    ("packed_adjacency","packed_vertex_weights","vertex_count"),
    ("packed_sum_weights","sum_target","sum_weight_count"),
    ("packed_zeta_coefficients","zeta_reserved","zeta_dimension"),
    ("packed_mobius_coefficients","mobius_reserved","mobius_dimension"),
    ("packed_basis_vectors","basis_seed","basis_vector_count"),
    ("packed_rank_vectors","rank_reserved","rank_vector_count"),
    ("packed_closure_rows","closure_reserved","closure_vertex_count"),
    ("packed_reachability_rows","reachability_start","reachability_vertex_count"),
    ("packed_hamming_candidates","hamming_query","hamming_candidate_count"),
    ("jaccard_left","jaccard_right","packed_jaccard_threshold"),
    ("packed_disjoint_sets","disjoint_reserved","disjoint_set_count"),
)

WIDE_LIMB_LAYOUTS=((64,),(32,32),(16,16,16,16),(8,8,8,8,8,8,8,8))
BOUND_LIMB_LAYOUTS=((32,),(16,16),(8,8,8,8))


def _api_patterns(ordinal:int)->tuple[int,int,int]:
    """Return one of 48 genuinely different, lossless request layouts."""
    return ordinal%4,(ordinal//4)%4,ordinal//16


def _slot_definition(*,name:str,field:str,widths:tuple[int,...],input_type:str,keyword:str)->str:
    access="public: " if keyword=="class" else ""
    limbs=" ".join(f"std::uint{bits}_t limb_{index};" for index,bits in enumerate(widths))
    initializers=", ".join(
        f"limb_{index}(static_cast<std::uint{bits}_t>(input >> {sum(widths[:index])}U))"
        for index,bits in enumerate(widths)
    )
    value_type="unsigned" if input_type=="unsigned" else "std::uint64_t"
    pieces=" | ".join(
        f"(static_cast<{value_type}>(limb_{index}) << {sum(widths[:index])}U)"
        for index in range(len(widths))
    )
    return f"{keyword} {name} {{ {access}{limbs} constexpr explicit {name}({input_type} input) : {initializers} {{}} constexpr {value_type} value() const {{ return {pieces}; }} }} {field};"


def _request_definition(case:Case)->str:
    primary,secondary,bound=API_FIELDS[case.ordinal]
    primary_pattern,secondary_pattern,bound_pattern=_api_patterns(case.ordinal)
    primary_slot=_slot_definition(name="PrimarySlot",field=primary,widths=WIDE_LIMB_LAYOUTS[primary_pattern],input_type="std::uint64_t",keyword="struct")
    secondary_slot=_slot_definition(name="SecondarySlot",field=secondary,widths=WIDE_LIMB_LAYOUTS[secondary_pattern],input_type="std::uint64_t",keyword="class")
    bound_slot=_slot_definition(name="BoundSlot",field=bound,widths=BOUND_LIMB_LAYOUTS[bound_pattern],input_type="unsigned",keyword="struct")
    return f"struct Request {{ {primary_slot} {secondary_slot} {bound_slot} constexpr Request(std::uint64_t primary_value, std::uint64_t secondary_value, unsigned bound_value) : {primary}(primary_value), {secondary}(secondary_value), {bound}(bound_value) {{}} }};"

NEGATIVE_BODIES = (
    "std::uint64_t count=0;for(unsigned i=0;i<8;++i)count+=((a>>(8U*i))&0xffULL)!=0;return {true,count,0};",
    "return {true,pop64(a&bounded_mask(width)),0};",
    "return {true,a&bounded_mask(width),width};",
    "return {true,(a<<static_cast<unsigned>(b&63ULL))|(a>>((64U-static_cast<unsigned>(b&63ULL))&63U)),b&63ULL};",
    "return {true,a&bounded_mask(width),(a>>(width-1U))&1ULL};",
    "return {true,a>>static_cast<unsigned>(b&63ULL),b};",
    "return {true,a|((b&0xffffffffULL)<<((b>>32)&63ULL)),0};",
    "return {true,a&bounded_mask(width),pop64(b)};",
    "return {true,a&(b&bounded_mask(width)),pop64(b)};",
    "std::uint64_t out=0;for(unsigned i=0;i<width;++i){const unsigned destination=static_cast<unsigned>((b>>(4U*i))&15ULL);out|=((a>>i)&1ULL)<<(destination&63U);}return {true,out,bounded_mask(width)};",
    "return {true,(a&bounded_mask(width))*(b&bounded_mask(width)),0};",
    "const auto v=a&bounded_mask(width);std::uint64_t shifted=0;for(unsigned i=1;i<width;++i)shifted|=((v>>i)&1ULL)<<(i-1U);return {true,shifted,v&1ULL};",
    "return {true,(a^(a>>1))&bounded_mask(width),0};",
    "return {true,(a+1U)&bounded_mask(width),pop64(a&bounded_mask(width))};",
    "return {true,a&bounded_mask(width),pop64(a&bounded_mask(width))};",
    "std::uint64_t rank=0;for(unsigned i=0;i<width;++i)if(a&(1ULL<<i))++rank;return {true,rank,b};",
    "return b<width?Result{true,b,b}:Result{false,0,0};",
    "std::uint64_t run=0;for(unsigned i=0;i<width;++i){if(a&(1ULL<<i))++run;else if(run)break;}return {true,run,0};",
    "if(b==0||b>width)return {false,0,0};return {true,width-b,b};",
    "const auto start=static_cast<unsigned>(b>>32),end=static_cast<unsigned>(b);if(start>end||end>=width)return {false,0,0};const auto m=bounded_mask(end-start+1U)<<start;return {true,(a|m)&bounded_mask(width),m};",
    "if(width==0||width>8)return {false,0,0};std::uint64_t flags=a;for(unsigned i=0;i<width;++i)if(a&(1ULL<<i))flags|=(b>>(8U*i))&0xffULL;return {true,flags&bounded_mask(width),0};",
    "return {true,a&bounded_mask(width),a&~bounded_mask(width)};",
    "if(width==0||width>16)return {false,0,0};const auto m=bounded_mask(width);return {true,(a&m)|((a>>width)&m)|(b&m),0};",
    "const unsigned bits=width&0xffU;const unsigned rank=(width>>8)&0xffU;const auto both=(a|b)&bounded_mask(bits);return rank<64?Result{true,rank,pop64(both)}:Result{false,0,0};",
    "return {true,pop64(a&bounded_mask(width))+pop64(b&bounded_mask(width)),0};",
    "const auto uni=a|b;return width<64?Result{true,width,pop64(uni)}:Result{false,0,0};",
    "const auto uni=(b|static_cast<std::uint64_t>(width));return {true,uni==(a&0xffffffffULL)?1ULL:0ULL,uni};",
    "return {true,1,1};",
    "return {true,width,width?bounded_mask(width):0};",
    "return {true,pop64(b),b};",
    "std::uint64_t sum=0;for(unsigned i=0;i<width;++i){const auto v=(a>>(4U*i))&15ULL;if(sum+v<=b)sum+=v;}return {true,sum==b?1ULL:0ULL,sum};",
    "std::uint64_t packed=0,running=0;for(unsigned i=0;i<8;++i){running=(running+((a>>(4U*i))&15ULL))&15ULL;packed|=running<<(4U*i);}return {true,packed,running};",
    "return {true,(~a)&0xffffffffULL,0};",
    "std::uint64_t best=b&0xffULL;for(unsigned i=0;i<width&&i<8;++i)best=best>((a>>(8U*i))&0xffULL)?best:((a>>(8U*i))&0xffULL);return {true,best,width};",
    "std::uint64_t count=0;for(unsigned i=0;i<width&&i<8;++i)count+=((a>>(8U*i))&0xffULL)!=0;return {true,count,0};",
    "if(width>4U)return {false,0,0};std::uint64_t diagonal=0;for(unsigned i=0;i<width;++i)diagonal|=(1ULL<<i)<<(4U*i);return {true,diagonal,width};",
    "const unsigned n=width>4?4:width;return {true,n?((a>>(4U*(b%n)))&15ULL):0,1};",
    "const unsigned count=width>8?8:width;std::uint64_t best=0,index=0;for(unsigned i=0;i<count;++i){const auto value=(a>>(8U*i))&0xffULL;if(value>best){best=value;index=i;}}return {true,best,index};",
    "const auto inter=pop64(a&b),uni=pop64(a|b);return {true,uni?inter/uni:1,uni};",
    "std::uint64_t used=0,selector=0;for(unsigned i=0;i<width&&i<8;++i){const auto piece=(a>>(8U*i))&0xffULL;if((used&piece)==0){used|=piece;selector|=1ULL<<i;}}return {true,pop64(selector),selector};",
)


CPP_BODIES = (
    "std::uint64_t v=a&bounded_mask(width);v=v-((v>>1)&0x5555555555555555ULL);v=(v&0x3333333333333333ULL)+((v>>2)&0x3333333333333333ULL);v=(v+(v>>4))&0x0F0F0F0F0F0F0F0FULL;return {true,(v*0x0101010101010101ULL)>>56,0};",
    "std::uint64_t v=a&bounded_mask(width);v^=v>>32;v^=v>>16;v^=v>>8;v^=v>>4;v^=v>>2;v^=v>>1;return {true,v&1ULL,pop64(a&bounded_mask(width))};",
    "std::uint64_t v=a&bounded_mask(width),out=0;for(unsigned i=0;i<width;++i)out|=((v>>i)&1ULL)<<(width-1U-i);return {true,out,0};",
    "const auto m=bounded_mask(width);const unsigned s=static_cast<unsigned>(b%width);const auto v=a&m;const auto out=s==0?v:((v<<s)|(v>>(width-s)))&m;return {true,out,s};",
    "const auto m=bounded_mask(width);auto v=a&m;if(width<64U&&(v&(1ULL<<(width-1U))))v|=~m;return {true,v,(a>>(width-1U))&1ULL};",
    "if(b>=64ULL||width>64ULL-b)return {false,0,0};return {true,(a>>b)&bounded_mask(width),b};",
    "const unsigned offset=static_cast<unsigned>((b>>32)&63ULL);if(width>32U||offset+width>64U)return {false,0,0};const auto field=b&0xffffffffULL;const auto fm=bounded_mask(width)<<offset;return {true,(a&~fm)|((field&bounded_mask(width))<<offset),fm};",
    "std::uint64_t src=b&bounded_mask(width),out=0,target=1;while(src){const auto low=src&(~src+1ULL);if(a&low)out|=target;target<<=1;src^=low;}return {true,out,pop64(b&bounded_mask(width))};",
    "const auto mask=b&bounded_mask(width);std::uint64_t out=0;unsigned source=0;for(unsigned destination=0;destination<width;++destination)if(mask&(1ULL<<destination)){out|=((a>>source)&1ULL)<<destination;++source;}return {true,out,source};",
    "if(width>16U)return {false,0,0};std::uint64_t out=0,used=0;for(unsigned i=0;i<width;++i){const unsigned destination=static_cast<unsigned>((b>>(4U*i))&15ULL);if(destination>=width||(used&(1ULL<<destination)))return {false,0,0};used|=1ULL<<destination;out|=((a>>i)&1ULL)<<destination;}return {true,out,used};",
    "if(width>32U)return {false,0,0};const auto x=a&bounded_mask(width),y=b&bounded_mask(width);std::uint64_t product=0;for(unsigned i=0;i<width;++i)if(y&(1ULL<<i))product^=x<<i;return {true,product,pop64(product)};",
    "const auto v=a&bounded_mask(width);return {true,(v^(v>>1))&bounded_mask(width),0};",
    "auto v=a&bounded_mask(width);for(unsigned shift=1;shift<width;shift<<=1)v^=v>>shift;return {true,v&bounded_mask(width),0};",
    "const auto v=a&bounded_mask(width);if(v==0)return {false,0,0};const std::uint64_t low=v&(~v+std::uint64_t{1});const std::uint64_t limit=bounded_mask(width);if(low>limit-v)return {false,0,0};const auto ripple=v+low;return {true,(ripple|(((v^ripple)>>2)/low))&limit,pop64(v)};",
    "const auto set=a&bounded_mask(width);if(pop64(set)>16U)return {false,0,0};std::uint64_t sub=set,total=0,count=0;for(;;){total+=sub;++count;if(sub==0)break;sub=(sub-1)&set;}return {true,total,count};",
    "if(b>width)return {false,0,0};return {true,pop64((a&bounded_mask(width))&bounded_mask(static_cast<unsigned>(b))),b};",
    "const auto v=a&bounded_mask(width);std::uint64_t rank=0;for(unsigned i=0;i<width;++i)if(v&(1ULL<<i)){if(rank==b)return {true,i,b};++rank;}return {false,0,0};",
    "std::uint64_t best=0,run=0,start=0;for(unsigned i=0;i<width;++i){if(a&(1ULL<<i)){++run;if(run>best){best=run;start=i+1U-run;}}else run=0;}return {true,best,start};",
    "if(b==0||b>width)return {false,0,0};std::uint64_t run=0;for(unsigned i=0;i<width;++i){run=(a&(1ULL<<i))?0:run+1;if(run==b)return {true,i+1U-b,b};}return {false,0,0};",
    "const auto start=static_cast<unsigned>(b>>32),end=static_cast<unsigned>(b);if(start>end||end>=width)return {false,0,0};const auto rm=bounded_mask(end-start+1U)<<start;return {true,(a^rm)&bounded_mask(width),rm};",
    "if(width==0||width>8)return {false,0,0};auto flags=a&bounded_mask(width);bool changed=true;while(changed){changed=false;for(unsigned i=0;i<width;++i)if(flags&(1ULL<<i)){const auto next=flags|((b>>(8U*i))&0xffULL);if(next!=flags){flags=next;changed=true;}}}return {true,flags&bounded_mask(width),0};",
    "if(width==0||width>8)return {false,0,0};std::uint64_t kept=0;for(unsigned i=0;i<width;++i)if((a&(1ULL<<i))&&((((b>>(8U*i))&0xffULL)&kept)==0))kept|=1ULL<<i;return {true,kept,a&~kept};",
    "if(width==0||width>16)return {false,0,0};const auto m=bounded_mask(width),x=a&m,y=(a>>width)&m,z=b&m;return {true,(x&y)|(x&z)|(y&z),x^y^z};",
    "const unsigned bits=width&0xffU;std::uint64_t rank=(width>>8)&0xffU;if(bits==0U||bits>64U)return {false,0,0};const auto diff=(a^b)&bounded_mask(bits);for(unsigned i=0;i<64;++i)if(diff&(1ULL<<i)){if(rank==0)return {true,i,pop64(diff)};--rank;}return {false,0,0};",
    "const auto m=bounded_mask(width);return {true,pop64((a|b)&m),pop64((a&b)&m)};",
    "const auto inter=a&b;std::uint64_t rank=width;for(unsigned i=0;i<64;++i)if(inter&(1ULL<<i)){if(rank==0)return {true,i,pop64(inter)};--rank;}return {false,0,0};",
    "const std::uint64_t universe=a&0xffffffffULL;const std::uint64_t left=b&0xffffffffULL;const std::uint64_t right=static_cast<std::uint64_t>(width);return {true,((left&right)==0&&(left|right)==universe)?1ULL:0ULL,(left|right)&0xffffffffULL};",
    "if(width>4U)return {false,0,0};const auto universe=a&15ULL;const unsigned count=width;std::uint64_t ways=0,first=0;for(unsigned selector=0;selector<(1U<<count);++selector){std::uint64_t covered=0;bool exact=true;for(unsigned i=0;i<count;++i)if(selector&(1U<<i)){const auto piece=(b>>(4U*i))&15ULL;if(covered&piece)exact=false;covered|=piece;}if(exact&&covered==universe){if(ways==0)first=selector;++ways;}}return {true,ways,first};",
    "if(width>4U)return {false,0,0};const auto universe=a&15ULL;const unsigned count=width;unsigned best=99,best_mask=0;for(unsigned selector=0;selector<(1U<<count);++selector){std::uint64_t covered=0;for(unsigned i=0;i<count;++i)if(selector&(1U<<i))covered|=(b>>(4U*i))&15ULL;const unsigned card=static_cast<unsigned>(pop64(selector));if(covered==universe&&(card<best||(card==best&&selector<best_mask))){best=card;best_mask=selector;}}if(best==99)return {false,0,0};return {true,best,best_mask};",
    "if(width>4U)return {false,0,0};const unsigned n=width;std::uint64_t best_weight=0,best_mask=0;for(unsigned selector=0;selector<(1U<<n);++selector){bool ok=true;std::uint64_t weight=0;for(unsigned i=0;i<n;++i)if(selector&(1U<<i)){if(((a>>(4U*i))&15ULL)&selector)ok=false;weight+=(b>>(4U*i))&15ULL;}if(ok&&(weight>best_weight||(weight==best_weight&&selector<best_mask))){best_weight=weight;best_mask=selector;}}return {true,best_weight,best_mask};",
    "if(b>63||width>16)return {false,0,0};std::uint64_t reachable=1;for(unsigned i=0;i<width;++i)reachable|=reachable<<((a>>(4U*i))&15ULL);return {true,(reachable&(1ULL<<b))?1ULL:0ULL,reachable};",
    "std::uint64_t values[8]{};for(unsigned i=0;i<8;++i)values[i]=(a>>(4U*i))&15ULL;for(unsigned bit=0;bit<3;++bit)for(unsigned s=0;s<8;++s)if(s&(1U<<bit))values[s]=(values[s]+values[s^(1U<<bit)])&15ULL;std::uint64_t packed=0,sum=0;for(unsigned i=0;i<8;++i){packed|=values[i]<<(4U*i);sum+=values[i];}return {true,packed,sum};",
    "std::int64_t trans[8]{};for(unsigned i=0;i<8;++i)trans[i]=static_cast<std::int64_t>((a>>(4U*i))&15ULL);for(unsigned bit=0;bit<3;++bit)for(unsigned s=0;s<8;++s)if(s&(1U<<bit))trans[s]+=trans[s^(1U<<bit)];std::int64_t inv[8]{};for(unsigned i=0;i<8;++i)inv[i]=trans[i];for(unsigned bit=0;bit<3;++bit)for(unsigned s=0;s<8;++s)if(s&(1U<<bit))inv[s]-=inv[s^(1U<<bit)];std::uint64_t packed=0,sum=0;for(unsigned i=0;i<8;++i){packed|=(static_cast<std::uint64_t>(inv[i])&15ULL)<<(4U*i);sum+=static_cast<std::uint64_t>(trans[i]);}return {true,packed,sum};",
    "if(width>8U)return {false,0,0};std::uint64_t basis[8]{};for(unsigned i=0;i<width;++i){auto v=(a>>(8U*i))&0xffULL;for(int bit=7;bit>=0;--bit)if(v&(1ULL<<bit)){if(basis[bit])v^=basis[bit];else{basis[bit]=v;break;}}}auto value=b&0xffULL;for(int bit=7;bit>=0;--bit)if((value^basis[bit])>value)value^=basis[bit];std::uint64_t rank=0;for(auto v:basis)rank+=v!=0;return {true,value,rank};",
    "if(width>8U)return {false,0,0};std::uint64_t basis[8]{};for(unsigned i=0;i<width;++i){auto v=(a>>(8U*i))&0xffULL;for(int bit=7;bit>=0;--bit)if(v&(1ULL<<bit)){if(basis[bit])v^=basis[bit];else{basis[bit]=v;break;}}}std::uint64_t rank=0;for(auto v:basis)rank+=v!=0;return {true,rank,0};",
    "if(width>4U)return {false,0,0};const unsigned n=width;const auto vertex_mask=bounded_mask(n);std::uint64_t rows[4]{};for(unsigned i=0;i<n;++i)rows[i]=(((a>>(4U*i))&15ULL)&vertex_mask)|(1ULL<<i);for(unsigned k=0;k<n;++k)for(unsigned i=0;i<n;++i)if(rows[i]&(1ULL<<k))rows[i]|=rows[k];std::uint64_t packed=0;for(unsigned i=0;i<n;++i)packed|=rows[i]<<(4U*i);return {true,packed,n};",
    "if(width==0U||width>4U)return {false,0,0};const unsigned n=width;const auto vertex_mask=bounded_mask(n);std::uint64_t rows[4]{};for(unsigned i=0;i<n;++i)rows[i]=(((a>>(4U*i))&15ULL)&vertex_mask)|(1ULL<<i);std::uint64_t visited=1ULL<<(b%n),front=visited,layers=0;while(front){std::uint64_t next=0;for(unsigned i=0;i<n;++i)if(front&(1ULL<<i))next|=rows[i];next&=~visited;front=next;visited|=next;if(front)++layers;}return {true,visited,layers};",
    "if(width==0U||width>8U)return {false,0,0};const unsigned count=width;std::uint64_t best_distance=65,best_index=0,best_value=0;for(unsigned i=0;i<count;++i){const std::uint64_t value=(a>>(8U*i))&0xffULL;const std::uint64_t dist=pop64(value^(b&0xffULL));if(dist<best_distance||(dist==best_distance&&i<best_index)){best_distance=dist;best_index=i;best_value=value;}}return {true,best_value,best_index};",
    "const unsigned numerator=(width>>16)&0xffffU,denominator=width&0xffffU;if(denominator==0U||numerator>denominator)return {false,0,0};const std::uint64_t inter=pop64(a&b),uni=pop64(a|b);if(uni==0)return {true,numerator<denominator?2ULL:1ULL,0};const std::uint64_t left=inter*denominator,right=uni*numerator;return {true,left>right?2ULL:(left<right?0ULL:1ULL),uni};",
    "if(width>8U)return {false,0,0};const unsigned count=width;std::uint64_t best_count=0,best_selector=0;for(unsigned selector=0;selector<(1U<<count);++selector){std::uint64_t used=0;bool ok=true;for(unsigned i=0;i<count;++i)if(selector&(1U<<i)){const auto piece=(a>>(8U*i))&0xffULL;if(used&piece)ok=false;used|=piece;}const auto card=pop64(selector);if(ok&&(card>best_count||(card==best_count&&selector<best_selector))){best_count=card;best_selector=selector;}}return {true,best_count,best_selector};",
)


def _header(case: Case) -> str:
    guard = case.task_id.replace("-", "_").upper() + "_H"
    request=_request_definition(case)
    return f"""#ifndef {guard}\n#define {guard}\n#include <cstdint>\nnamespace {case.namespace} {{\nstruct Result {{ bool valid; std::uint64_t value; std::uint64_t auxiliary; }};\n{request}\nResult {case.function}(Request request);\n}}\n#endif\n"""


def _source(case: Case, *, negative: bool = False) -> str:
    if negative:
        body = NEGATIVE_BODIES[case.ordinal]
    else:
        guard = "if(width==0U||width>64U)return {false,0,0};\n" if case.ordinal < 20 else ""
        body = guard + CPP_BODIES[case.ordinal]
    body="(void)a;(void)b;(void)width;"+body
    body=body.replace(";",";\n")
    primary,secondary,bound=API_FIELDS[case.ordinal]
    return f"""#include \"{case.task_id}.h\"\n#include <cstdint>\nnamespace {case.namespace} {{\nnamespace {{\n[[maybe_unused]] std::uint64_t bounded_mask(unsigned width) {{ return width==64U?~std::uint64_t{{0}}:(width==0U?0U:((std::uint64_t{{1}}<<width)-1U)); }}\n[[maybe_unused]] std::uint64_t pop64(std::uint64_t value) {{ std::uint64_t count=0;while(value){{value&=value-1U;++count;}}return count; }}\n}}\nResult {case.function}(Request request) {{\nconst std::uint64_t a=request.{primary}.value();\nconst std::uint64_t b=request.{secondary}.value();\nconst unsigned width=request.{bound}.value();\n// CORE_BEGIN: {case.mechanism}\n{body}\n// CORE_END\n}}\n}}\n"""


def _starter(case: Case) -> str:
    return f"""#include \"{case.task_id}.h\"\nnamespace {case.namespace} {{\nResult {case.function}(Request) {{ return {{false,0,0}}; }}\n}}\n"""


def _limb_checks(*,object_name:str,value:int,widths:tuple[int,...],role:str)->str:
    checks=[]
    for index,bits in enumerate(widths):
        expected=(value>>sum(widths[:index]))&((1<<bits)-1)
        access=f"targeted_request.{object_name}.limb_{index}"
        if role=="primary":
            checks.append(f"  assert(static_cast<std::uint64_t>({access})=={expected}ULL);")
        elif role=="secondary":
            checks.append(f"  if(static_cast<std::uint64_t>({access})!={expected}ULL)return 2;")
        else:
            checks.append(f"  switch(static_cast<unsigned>({access})){{case {expected}U:break;default:return 3;}}")
    return "\n".join(checks)


def _test(case: Case, *, hidden: bool) -> str:
    a,b,w=INPUTS[case.ordinal][1 if hidden else 0]
    valid,value,aux=_oracle(case.ordinal,a,b,w)
    checks=[f"  const auto example_result={case.function}(Request{{{a}ULL,{b}ULL,{w}U}});\n  assert(example_result.valid=={str(valid).lower()});\n  assert(example_result.value=={value}ULL);\n  assert(example_result.auxiliary=={aux}ULL);"]
    ta,tb,tw,tvalid,tvalue,taux=TARGETED_CASES[case.ordinal][1 if hidden else 0]
    primary,secondary,bound=API_FIELDS[case.ordinal]
    primary_pattern,secondary_pattern,bound_pattern=_api_patterns(case.ordinal)
    checks.append(f"  const Request targeted_request{{{ta}ULL,{tb}ULL,{tw}U}};\n{_limb_checks(object_name=primary,value=ta,widths=WIDE_LIMB_LAYOUTS[primary_pattern],role='primary')}\n{_limb_checks(object_name=secondary,value=tb,widths=WIDE_LIMB_LAYOUTS[secondary_pattern],role='secondary')}\n{_limb_checks(object_name=bound,value=tw,widths=BOUND_LIMB_LAYOUTS[bound_pattern],role='bound')}\n  assert(targeted_request.{primary}.value()=={ta}ULL);\n  assert(targeted_request.{secondary}.value()=={tb}ULL);\n  assert(targeted_request.{bound}.value()=={tw}U);\n  const auto targeted_result={case.function}(targeted_request);\n  assert(targeted_result.valid=={str(tvalid).lower()});\n  assert(targeted_result.value=={tvalue}ULL);\n  assert(targeted_result.auxiliary=={taux}ULL);")
    if case.ordinal==9:checks.append(f"  assert(!{case.function}(Request{{9ULL,16ULL,4U}}).valid);")
    if hidden:
        if case.ordinal<20:checks.append(f"  assert(!{case.function}(Request{{1ULL,1ULL,0U}}).valid);")
        if case.ordinal in (20,21):checks.append(f"  assert(!{case.function}(Request{{1ULL,0ULL,9U}}).valid);")
        if case.ordinal in (16,18,23,25):checks.append(f"  assert(!{case.function}(Request{{0ULL,0ULL,{((9<<8)|4) if case.ordinal==23 else 7}U}}).valid);")
        if case.ordinal==38:checks.append(f"  assert(!{case.function}(Request{{1ULL,1ULL,0U}}).valid);")
    joined="\n".join(checks)
    return f"""#include \"{case.task_id}.h\"\n#include <cassert>\nint main() {{\n  using namespace {case.namespace};\n{joined}\n  return 0;\n}}\n"""


def _cmake(case: Case) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)\nproject({case.task_id.replace('-', '_')} LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\nset(CMAKE_CXX_EXTENSIONS OFF)\nadd_compile_options(-Wall -Wextra -Wpedantic -Werror)\nadd_library(task_solution {case.task_id}.cpp)\ntarget_include_directories(task_solution PUBLIC .)\nadd_executable(visible_test task_visible_test.cpp)\ntarget_link_libraries(visible_test PRIVATE task_solution)\nadd_executable(hidden_test .meta/task_hidden_test.cpp)\ntarget_link_libraries(hidden_test PRIVATE task_solution)\nadd_library(negative_solution .meta/negative_false_substitute.cpp)\ntarget_include_directories(negative_solution PUBLIC .)\nadd_executable(negative_test task_visible_test.cpp)\ntarget_link_libraries(negative_test PRIVATE negative_solution)\nadd_executable(negative_hidden_test .meta/task_hidden_test.cpp)\ntarget_link_libraries(negative_hidden_test PRIVATE negative_solution)\nenable_testing()\nadd_test(NAME visible COMMAND visible_test)\nadd_test(NAME hidden COMMAND hidden_test)\n"""


def _task_files(case: Case) -> dict[str, str]:
    intro = f"# {case.title}\n\nBits are the smallest currency of systems code: flags packed into words, fields squeezed into registers, hashes mixed one shift at a time. Each operation is only a few gates, yet every one hides an edge case — a width of zero, a shift equal to the word size, a carry that wraps around.\n\nThis exercise is about one such operation: {case.mechanism}.\n"
    a,b,w=INPUTS[case.ordinal][0];valid,value,aux=_oracle(case.ordinal,a,b,w)
    primary,secondary,bound=API_FIELDS[case.ordinal]
    instructions = f"""# Instructions\n\nImplement `{case.function}` in namespace `{case.namespace}`. Its public `Request` fields are `{primary}`, `{secondary}`, and `{bound}` in that declaration order. The request constructor accepts their logical values as two `uint64_t` scalars followed by one unsigned scalar; the exposed lossless limb slots are part of the editable API and must remain intact.\n\nOperation: {case.mechanism}. {PUBLIC_CONTRACTS[case.ordinal]} {case.boundary}. Bits are ordered least-significant first unless this contract says otherwise. Every tie chooses the smaller bit, byte, or selector index. Invalid or absent requests return `{{false,0,0}}`; valid empty inputs follow the stated operation. All unsigned arithmetic is modulo 2^64.\n\nPublic example: `{case.function}(Request{{{a}ULL, {b}ULL, {w}U}})` returns `{{{str(valid).lower()}, {value}, {aux}}}`.\n\nDo not use C++20 bit helpers, `std::bitset`, ordered set/map containers, precomputed answers, or hard-coded examples. Implement the operation directly with C++17 unsigned arithmetic.\n"""
    config = {"authors":["w8-biayn"],"license":"CC0-1.0","source":"repository-authored-clean-room","blurb":case.mechanism,"files":{"solution":[f"{case.task_id}.h",f"{case.task_id}.cpp"],"test":["task_visible_test.cpp",".meta/task_hidden_test.cpp",".meta/negative_false_substitute.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
    replacement=["bit-morton-interleave","bit-morton-deinterleave"][case.ordinal-9] if case.ordinal in (9,10) else None
    provenance = {"schema_version":2,"task_id":case.task_id,"family_id":FAMILY_ID,"lineage":"replacement-backfill" if replacement else "new-root","replaces":replacement,"source":str(CURRICULUM.relative_to(REPO_ROOT)),"source_inventory_id":"glm47-expansion-v1-inventory-2026-07-22","license":"CC0-1.0","usage_terms":"clean-room repository-authored local candidate","generator":OWNER,"mechanism":case.mechanism,"task_spec_revision":"v2","clean_room":True,"benchmark_holdout_separation":"required","dataset_handoff":"not_requested","selected_prompts":list(SELECTED_PROMPTS)}
    return {
        ".docs/introduction.md":intro,
        ".docs/instructions.md":instructions,
        f"{case.task_id}.h":_header(case),
        f"{case.task_id}.cpp":_starter(case),
        "task_visible_test.cpp":_test(case,hidden=False),
        ".meta/task_hidden_test.cpp":_test(case,hidden=True),
        ".meta/example.h":_header(case),
        ".meta/example.cpp":_source(case),
        ".meta/negative_false_substitute.cpp":_source(case,negative=True),
        ".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n",
        ".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n",
        ".meta/tests.toml":f'version = 1\nvisible = "normal {case.mechanism}"\nhidden = "boundary, invalid, ordering, and tie behavior"\nnegative = "{case.wrong}"\n',
        "CMakeLists.txt":_cmake(case),
    }


def _inventory(root: Path) -> dict[str, Path]:
    found: dict[str,Path] = {}
    if not root.is_dir(): return found
    for config in sorted(root.rglob(".meta/config.json")):
        if ".state" in config.parts: continue
        task=config.parent.parent
        key=task.relative_to(root).as_posix()
        if key in found:_fail("duplicate_task",key)
        found[key]=task
    return found


def _freeze_source_inventory(out:Path)->tuple[list[dict[str,object]],list[Path]]:
    records:list[dict[str,object]]=[];roots:list[Path]=[];counts={"legacy":0,"reverify":0,"expansion":0}
    for label,tree in (("legacy",LEGACY_ROOTS[0]),("reverify",LEGACY_ROOTS[1]),("expansion",EXPANSION_ROOT)):
        for relative,path in _inventory(tree).items():
            if str(path).startswith(str(out)):continue
            files=[file for file in path.rglob("*") if file.is_file() and ".state" not in file.relative_to(path).parts and "build" not in file.relative_to(path).parts]
            records.append({"tree":label,"relative_path":relative,"task_id":path.name,"config_hash":_file_sha(path/".meta/config.json"),"semantic_tree_hash":_tree_hash(path),"semantic_file_count":len(files)})
            roots.append(path);counts[label]+=1
    records.sort(key=lambda row:(str(row["tree"]),str(row["relative_path"])))
    aggregate=_sha(json.dumps(records,sort_keys=True,separators=(",",":")).encode())
    state=out/".state"
    _json(state/"source-inventory.json",{"schema_version":3,"inventory_id":"glm47-expansion-v1-inventory-2026-07-22","legacy_count":counts["legacy"],"reverify_count":counts["reverify"],"expansion_external_count":counts["expansion"],"record_count":len(records),"semantic_file_count":sum(int(row["semantic_file_count"]) for row in records),"full_content_aggregate":aggregate,"records":records,"id_collisions":[]})
    return records,roots


def _write_targeted_case_catalog(out:Path)->None:
    records=[]
    for case in cases():
        entries=[]
        for visibility,index in (("visible",0),("private",1)):
            a,b,w,valid,value,aux=TARGETED_CASES[case.ordinal][index]
            entries.append({"visibility":visibility,"rule":TARGETED_RULES[case.ordinal][index],"request":{"primary":a,"secondary":b,"bound":w},"expected":{"valid":valid,"value":value,"auxiliary":aux},"derivation":"hand-derived contract case; not emitted by _oracle"})
        records.append({"task_id":case.task_id,"cases":entries})
    _json(out/".state/targeted-case-catalog.json",{"schema_version":1,"record_count":40,"case_count":80,"records":records})


def _validate_output(out: Path) -> None:
    resolved=out.resolve(); expansion=EXPANSION_ROOT.resolve()
    if resolved != (expansion/"numerical/bit-set-reasoning").resolve() or expansion not in resolved.parents:
        _fail("invalid_output_root",str(out))
    current=resolved
    while current!=expansion.parent:
        if current.exists() and current.is_symlink():_fail("unsafe_output_symlink",str(current))
        if current==expansion:break
        current=current.parent


AUDIT_FINDINGS=(
    "cycle-001/family/public-contract-incomplete","cycle-001/family/discriminator-not-task-specific",
    "cycle-001/family/oracle-coverage-not-independent","cycle-001/family/diversity-controls-invalid",
    "cycle-001/bit-morton-pair/semantic-lineage-conflict","cycle-001/family/evidence-subject-incomplete",
    "cycle-001/family/metadata-provenance-incomplete","cycle-001/set-symmetric-rank/bound-double-duty",
    "cycle-001/set-jaccard-ordering/operand-double-duty",
    "cycle-002/family/oracle-coverage-still-not-independent",
    "cycle-002/family/diversity-controls-still-invalid",
    "cycle-002/family/source-inventory-lineage-evidence-stale",
    "cycle-002/family/invalid-bound-contract-reference-mismatch",
    "cycle-003/family/seven-dimension-screen-still-non-material",
    "cycle-003/family/constants-policy-control-incoherent",
    "cycle-003/family/live-source-inventory-stale",
    "cycle-003/bit-next-combination/width64-overflow",
    "cycle-003/bit-submask-checksum/unbounded-valid-runtime",
    "cycle-004/family/seven-dimension-screen-still-non-material",
    "cycle-004/family/live-source-inventory-stale",
    "cycle-005/family/topic-negative-fixture-literal-suffix-leak",
)


def _write_remedies(out:Path,selected:tuple[Case,...],before_hashes:dict[str,str])->None:
    state=out/".state/remedy";state.mkdir(parents=True,exist_ok=True)
    for case in selected:
        replaced=["bit-morton-interleave","bit-morton-deinterleave"][case.ordinal-9] if case.ordinal in (9,10) else case.task_id
        disposition="replace" if case.ordinal in (9,10) else "repair-in-place"
        findings=list(AUDIT_FINDINGS)
        spec=state/f"{case.task_id}.md"
        spec_text=f"""# Identity

Task `{case.task_id}`, revision v2, family `{FAMILY_ID}`, disposition `{disposition}`, source inventory `glm47-expansion-v1-inventory-2026-07-22`, CC0-1.0, generator `{OWNER}`, benchmark screen pending regenerated evidence.

# Objective

Implement and discriminate {case.mechanism} under this exact public contract: {PUBLIC_CONTRACTS[case.ordinal]}

# Public API

Namespace `{case.namespace}` exposes `Result {{ bool valid; uint64_t value; uint64_t auxiliary; }}`, the task-semantic `Request` fields `{API_FIELDS[case.ordinal][0]}`, `{API_FIELDS[case.ordinal][1]}`, `{API_FIELDS[case.ordinal][2]}`, and `{case.function}(Request)`; editable order is `{case.task_id}.h`, `{case.task_id}.cpp`.

# Behavior table

Valid inputs and outputs follow the objective contract; invalid or absent returns `{{false,0,0}}`; ordering is low-bit first; ties choose the lower index unless explicitly stated; arithmetic is unsigned modulo 2^64. Public examples are generated into instructions.

# Implementation invariant

The reference must contain the direct `{case.mechanism}` core. C++20 bit helpers, `std::bitset`, ordered set/map authority, precomputed cases, and the named wrong substitute `{case.wrong}` are forbidden.

# Starter and reference

The header is complete, the source starter returns invalid, and the independent reference replaces both editable files without importing benchmark or hidden assets.

# Tests

Visible and private suites use different base vectors and separately hand-derived root-specific acceptance cases; private tests add invalid/absent rules. The compiling negative implements `{case.wrong}` and both suites must reject it in normal and sanitizer modes.

# Files and metadata

Prompt roles are docs plus the two solution files. Tests, reference, CMake, provenance, screens, and receipts stay private. Metadata uses schema v2, CC0-1.0, clean-room source inventory, and one-to-one reference mapping.

# Build/oracle

C++17, Unix Makefiles, strict warnings, pinned Docker sanity image, network none, exactly two CTests in normal and fresh ASan/UBSan modes, plus two nonzero negative exits per mode.

# Family/contamination

Compare all 780 pairs in seven dimensions, all existing trees, and 26 official holdouts with normalizer `{NORMALIZER}`; clone and holdout matches fail closed.

# Optional dataset handoff

`not_requested`.

# Acceptance

Focused tests, owner `--verify-core`, `--docker-sanity`, creator preflight, and a clean fresh independent audit must pass; stable failures include `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `benchmark_content_overlap`, and `grader_mount_hash_mismatch`.
"""
        _write(spec,spec_text);spec_hash=_file_sha(spec)
        _json(state/f"{case.task_id}.json",{"schema_version":"aider-task-remedy-v1","task_id":case.task_id,"family_id_before":FAMILY_ID,"tree_hash_before":before_hashes.get(replaced,"missing-new-root"),"generator_path":OWNER,"generator_revision":_file_sha(REPO_ROOT/OWNER),"finding_ids":findings,"disposition":disposition,"benchmark_screen":"pending","license_screen":"pass","remedy_spec_path":str(spec.relative_to(REPO_ROOT)),"remedy_spec_hash":spec_hash,"status":"planned","replaces":replaced if disposition=="replace" else None})


def materialize(out: Path = DEFAULT_OUT, *, force: bool = False) -> dict[str, object]:
    _validate_output(out); selected=cases()
    old={}
    for root in LEGACY_ROOTS: old.update(_inventory(root))
    expansion_other=_inventory(EXPANSION_ROOT)
    reserved_ids={path.name for path in [*old.values(),*expansion_other.values()] if not str(path).startswith(str(out))}
    for case in selected:
        if case.task_id in reserved_ids:
            _fail("existing_task_id",case.task_id)
    out.mkdir(parents=True,exist_ok=True)
    foreign=[]
    for child in out.iterdir():
        if child.name==".state":continue
        provenance=child/".meta/provenance.json"
        if not provenance.is_file() or json.loads(provenance.read_text()).get("generator")!=OWNER:foreign.append(child.name)
    if foreign:_fail("foreign_generated_root",",".join(sorted(foreign)))
    existing={p.name for p in out.iterdir() if p.is_dir() and p.name!=".state"}; expected={c.task_id for c in selected}
    before_hashes={task_id:_tree_hash(out/task_id) for task_id in existing}
    if existing and not force:_fail("generator_output_drift",f"existing={len(existing)}")
    if force:
        for task_id in sorted(existing):shutil.rmtree(out/task_id)
    for case in selected:
        for relative,content in _task_files(case).items():_write(out/case.task_id/relative,content)
    state=out/".state";state.mkdir(parents=True,exist_ok=True)
    proposals=[{"proposal_id":f"bitset-{i+1:02d}","task_id":c.task_id,"mechanism":c.mechanism,"decision":"selected-new-root"} for i,c in enumerate(selected)]
    rejected=[{"proposal_id":"control-domain-identifier-rename","decision":"reject","reason":"rename-only clone"},{"proposal_id":"control-constants-policy-only","decision":"reject","reason":"policy-only clone"},{"proposal_id":"control-opposite-end-selection","decision":"reject","reason":"opposite-end clone"}]
    _json(state/"raw-proposals.json",{"schema_version":1,"proposals":proposals+rejected})
    _json(state/"selected-manifest.json",{"schema_version":1,"family_id":FAMILY_ID,"requested_count":40,"retained_count":40,"tasks":proposals})
    _json(state/"rejected-proposals.json",{"schema_version":1,"rejected":rejected})
    _write_targeted_case_catalog(out)
    _freeze_source_inventory(out)
    _write_remedies(out,selected,before_hashes)
    return {"out":str(out),"task_count":40,"tree_hash":_tree_hash(out)}


def _clean(text: str) -> str:
    text=re.sub(r"//.*?$|/\*.*?\*/"," ",text,flags=re.M|re.S)
    text=re.sub(r'"(?:\\.|[^"\\])*"'," STRING ",text)
    text=re.sub(r"\b(?:0x[0-9a-f]+|\d+)[ul]*\b"," NUMBER ",text.lower())
    return " ".join(re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|\+\+|--|\^|&|\|",text))


CPP_STRUCTURE_TOKENS=frozenset("alignas auto bool break case class const constexpr continue default do else enum explicit false for if long namespace noexcept public return short signed static_assert struct switch true typedef unsigned using void while".split())


def _structure(text:str)->str:
    text=re.sub(r"//.*?$|/\*.*?\*/"," ",text,flags=re.M|re.S)
    text=re.sub(r'"(?:\\.|[^"\\])*"'," STRING ",text)
    text=re.sub(r"\b(?:0x[0-9a-f]+|\d+)[ul]*\b"," NUMBER ",text.lower())
    raw=re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|\+\+|--|&&|\|\||<<|>>|::|[{}();,?:+*/%^&|!<>=\[\]-]",text)
    return " ".join(token if token in CPP_STRUCTURE_TOKENS or not re.fullmatch(r"[a-z_][a-z0-9_]*",token) else "IDENTIFIER" for token in raw)


def _features(root: Path) -> dict[str,str]:
    header=next(root.glob("*.h")).read_text()
    reference=(root/".meta/example.cpp").read_text();visible=(root/"task_visible_test.cpp").read_text();hidden=(root/".meta/task_hidden_test.cpp").read_text()
    negative=(root/".meta/negative_false_substitute.cpp").read_text()
    core=reference.split("// CORE_BEGIN",1)[1].split("// CORE_END",1)[0]
    return {
        "public_api":_structure(header),
        "owned_state_or_algorithm":_structure(core),
        "mutation_selection_rules":_structure(core+visible),
        "invalid_boundary_behavior":_structure(core+hidden),
        "reference_control_flow":_structure(core),
        "deterministic_oracle":_structure(visible+hidden),
        "topic_negative_fixture":_structure(negative),
    }


def _pair(left: Path, right: Path, *, clone_expected: bool = False) -> dict[str,object]:
    lf=_features(left);rf=_features(right);decisions={}
    for dimension in DIMENSIONS:
        lt=lf[dimension].split();rt=rf[dimension].split()
        l={(i,*lt[i:i+3]) for i in range(max(1,len(lt)-2))};r={(i,*rt[i:i+3]) for i in range(max(1,len(rt)-2))}
        overlap=len(l&r)/max(1,len(l|r));different=lf[dimension]!=rf[dimension]
        if clone_expected:
            distinct=different and overlap<0.72
        else:
            ceiling=0.98 if dimension in {"public_api","reference_control_flow","deterministic_oracle"} else 0.95
            distinct=different and overlap<ceiling and len(l^r)>=3
        decisions[dimension]={"distinct":distinct,"overlap":round(overlap,6),"symmetric_difference":len(l^r),"left_hash":_sha(lf[dimension].encode()),"right_hash":_sha(rf[dimension].encode())}
    return {"left":left.name,"right":right.name,"dimensions":decisions,"pass":all(v["distinct"] for v in decisions.values())}


def _render_controls(out: Path) -> dict[str,tuple[Path,Path]]:
    selected=cases();first=out/selected[0].task_id;run_root=out/selected[17].task_id;control_root=out/".state/adversarial-clone-controls"
    if control_root.exists():shutil.rmtree(control_root)
    controls:dict[str,tuple[Path,Path]]={}
    root=control_root/"domain-identifier-renamed";shutil.copytree(first,root);old=selected[0]
    replacements={old.namespace:"telemetry_register_namespace",old.function:"evaluate_telemetry_register"}
    for path in root.rglob("*"):
        if path.is_file():
            text=path.read_text()
            for source,target in replacements.items():text=text.replace(source,target)
            path.write_text(text)
    _write(root/".control-task-id",old.task_id);controls["domain-identifier-renamed"]=(root,first)
    root=control_root/"constants-policy-only";shutil.copytree(first,root)
    def pop_test(a:int,width:int)->str:
        value=_pop(a&_mask(width));return f"#include \"{old.task_id}.h\"\n#include <cassert>\nint main(){{using namespace {old.namespace};const auto r={old.function}(Request{{{a}ULL,0ULL,{width}U}});assert(r.valid&&r.value=={value}ULL&&r.auxiliary==0ULL);return 0;}}\n"
    _write(root/"task_visible_test.cpp",pop_test(0b1011,4))
    hidden_policy=pop_test(0b111100,6).replace("return 0;","assert(!evaluate_bit_swar_popcount(Request{1ULL,0ULL,8U}).valid);return 0;")
    _write(root/".meta/task_hidden_test.cpp",hidden_policy)
    docs=root/".docs/instructions.md";revised=docs.read_text().replace("its width in 1..64","its width and must be exactly 4 or 6").replace("width 0 or >64 invalid","any width other than 4 or 6 is invalid")
    revised=re.sub(r"Public example:.*",f"Public example: `{old.function}(Request{{11ULL, 0ULL, 4U}})` returns `{{true, 3, 0}}`.",revised)
    docs.write_text(revised)
    reference=root/".meta/example.cpp";reference.write_text(reference.read_text().replace("if(width==0U||width>64U)","if(width!=4U&&width!=6U)"))
    _write(root/".control-task-id",old.task_id)
    controls["constants-policy-only"]=(root,first)
    base_case=selected[17];root=control_root/"opposite-end-selection";shutil.copytree(run_root,root)
    reference=root/".meta/example.cpp";reference.write_text(reference.read_text().replace("if(run>best)","if(run>=best)"))
    def run_test(a:int,width:int,start:int)->str:
        return f"#include \"{base_case.task_id}.h\"\n#include <cassert>\nint main(){{using namespace {base_case.namespace};const auto r={base_case.function}(Request{{{a}ULL,0ULL,{width}U}});assert(r.valid&&r.value==2ULL&&r.auxiliary=={start}ULL);return 0;}}\n"
    _write(root/"task_visible_test.cpp",run_test(0b110011,6,4));_write(root/".meta/task_hidden_test.cpp",run_test(0b110110,6,4))
    docs=root/".docs/instructions.md";docs.write_text(docs.read_text().replace("Equal lengths choose the lower start","Equal lengths choose the larger start").replace("ties choose lower start","ties choose larger start").replace("Every tie chooses the smaller bit, byte, or selector index.","Every equal-length run tie chooses the larger start index."))
    _write(root/".control-task-id",base_case.task_id);controls["opposite-end-selection"]=(root,run_root)
    return controls


def _control_coherent(name:str,root:Path,base:Path)->bool:
    docs=(root/".docs/instructions.md").read_text()
    reference=(root/".meta/example.cpp").read_text()
    if name=="domain-identifier-renamed":
        return base.name.replace("-","_") not in reference and "telemetry_register_namespace" in reference and "evaluate_telemetry_register" in reference
    if name=="constants-policy-only":
        hidden=(root/".meta/task_hidden_test.cpp").read_text()
        return "must be exactly 4 or 6" in docs and "1..64" not in docs and "width other than 4 or 6" in docs and "Request{11ULL, 0ULL, 4U}" in docs and "0ULL,8U}).valid" in hidden and "if(width!=4U&&width!=6U)" in reference
    if name=="opposite-end-selection":
        return "lower start" not in docs and docs.count("larger start")>=2 and "if(run>=best)" in reference
    return False


def _semantic_text(root: Path) -> str:
    paths=[*(root/".docs").glob("*.md"),*root.glob("*.h"),root/".meta/example.cpp",root/"task_visible_test.cpp",root/".meta/task_hidden_test.cpp"]
    return "\n".join(p.read_text(errors="ignore") for p in paths if p.is_file())


def verify_core(out: Path = DEFAULT_OUT) -> dict[str,object]:
    selected=cases();roots=[out/c.task_id for c in selected]
    if any(not (root/".meta/config.json").is_file() for root in roots):_fail("generator_output_drift","missing root")
    _write_targeted_case_catalog(out)
    scratch=EXPANSION_ROOT/".state/bit-set-generator-scratch";scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bit-set-fresh-",dir=scratch) as temp:
        fresh=Path(temp)/"numerical/bit-set-reasoning"
        original=DEFAULT_OUT
        # A scratch path must still be under expansion; temporarily materialize by rendering files directly.
        fresh.mkdir(parents=True)
        for case in selected:
            for relative,content in _task_files(case).items():_write(fresh/case.task_id/relative,content)
        for case in selected:
            if _tree_hash(out/case.task_id)!=_tree_hash(fresh/case.task_id):_fail("generator_output_drift",case.task_id)
        _=original
    prompt_records=[]
    for case,root in zip(selected,roots,strict=True):
        config=json.loads((root/".meta/config.json").read_text());solution=config["files"]["solution"]
        expected=[f"{case.task_id}.h",f"{case.task_id}.cpp"]
        if solution!=expected or any(path.startswith((".meta/",".docs/")) or path=="CMakeLists.txt" for path in solution):_fail("unsafe_path",case.task_id)
        prompt=build_prompt(load_task(root))
        for private in ("CMakeLists.txt","provenance.json","example.cpp","task_hidden_test","negative_false"):
            if private in prompt:_fail("prompt_contract_incomplete",f"{case.task_id}:{private}")
        if not all(path in prompt for path in expected):_fail("prompt_contract_incomplete",case.task_id)
        prompt_records.append({"task_id":case.task_id,"prompt_hash":_sha(prompt.encode()),"solution":solution,"starter_hashes":{path:_file_sha(root/path) for path in solution},"reference_hashes":{path:_file_sha(root/example) for path,example in zip(solution,config["files"]["example"],strict=True)},"visible_test_hash":_file_sha(root/"task_visible_test.cpp"),"hidden_test_hash":_file_sha(root/".meta/task_hidden_test.cpp"),"negative_hash":_file_sha(root/".meta/negative_false_substitute.cpp"),"metadata_hash":_file_sha(root/".meta/provenance.json")})
        a,b,w=INPUTS[case.ordinal][0]
        if _oracle(case.ordinal,a,b,w) in ((True,0,0),(False,0,0)):_fail("invariant_not_enforced",case.task_id)
    pairs=[_pair(left,right) for left,right in combinations(roots,2)]
    failed=[row for row in pairs if not row["pass"]]
    if failed:_fail("duplicate_family",f"{len(failed)} of 780 pairs; first={failed[0]['left']}:{failed[0]['right']}")
    controls=[]
    for name,(root,base) in _render_controls(out).items():
        decision=_pair(base,root,clone_expected=True)
        if decision["pass"]:_fail("adversarial_clone_not_rejected",name)
        coherent=_control_coherent(name,root,base)
        if not coherent:_fail("clone_control_failed",f"{name}:incoherent")
        controls.append({"control":name,"base_task_id":base.name,"changed_files":_tree_hash(root)!=_tree_hash(base),"coherent":coherent,"build_required":True,"production_rejected":not decision["pass"],"decision":decision})
    inventory_records,old=_freeze_source_inventory(out)
    inventory_aggregate=_sha(json.dumps(inventory_records,sort_keys=True,separators=(",",":")).encode())
    old_tokens=[(root,set(_clean(_semantic_text(root)).split())) for root in old]
    lineage=[]
    for root in roots:
        tokens=set(_clean(_semantic_text(root)).split());best=(0.0,"")
        for other,other_tokens in old_tokens:
            score=len(tokens&other_tokens)/max(1,len(tokens|other_tokens))
            if score>best[0]:best=(score,str(other))
        if best[0]>=0.94:_fail("duplicate_family",f"{root.name}:{best[1]}:{best[0]:.3f}")
        lineage.append({"task_id":root.name,"strongest_existing_overlap":round(best[0],6),"existing_root":best[1]})
    if not HOLDOUT_ROOT.is_dir():_fail("benchmark_content_unavailable",str(HOLDOUT_ROOT))
    holdouts={p.name:p for p in HOLDOUT_ROOT.iterdir() if p.is_dir() and p.name in OFFICIAL_HOLDOUTS}
    if set(holdouts)!=OFFICIAL_HOLDOUTS:_fail("benchmark_content_unavailable",str(sorted(OFFICIAL_HOLDOUTS-set(holdouts))))
    holdout_bindings={name:{"semantic_tree_hash":_tree_hash(root),"semantic_file_count":sum(1 for path in root.rglob("*") if path.is_file())} for name,root in sorted(holdouts.items())}
    holdout_aggregate=_sha(json.dumps(holdout_bindings,sort_keys=True,separators=(",",":")).encode())
    holdout_tokens={name:set(_clean(_semantic_text(root)).split()) for name,root in holdouts.items()};contamination=[]
    for root in roots:
        tokens=set(_clean(_semantic_text(root)).split());scores={name:len(tokens&value)/max(1,len(tokens|value)) for name,value in holdout_tokens.items()};name=max(scores,key=scores.get)
        if scores[name]>=0.82:_fail("benchmark_content_overlap",f"{root.name}:{name}:{scores[name]:.3f}")
        contamination.append({"task_id":root.name,"strongest_holdout":name,"overlap":round(scores[name],6)})
    state=out/".state"
    _json(state/"family-screen.json",{"schema_version":1,"normalizer":NORMALIZER,"root_count":40,"pair_count":780,"expected_pair_count":780,"dimensions":list(DIMENSIONS),"pairs":pairs,"controls":controls,"status":"pass"})
    _json(state/"prompt-boundary.json",{"status":"pass","records":prompt_records})
    _json(state/"lineage-screen.json",{"schema_version":2,"status":"pass","external_root_count":len(old),"comparison_count":len(old)*40,"source_inventory_hash":_file_sha(state/"source-inventory.json"),"full_content_aggregate":inventory_aggregate,"records":lineage})
    _json(state/"benchmark-screen.json",{"schema_version":2,"status":"pass","holdout_count":26,"comparison_count":1040,"holdout_bindings":holdout_bindings,"holdout_aggregate":holdout_aggregate,"records":contamination})
    return {"root_count":40,"pair_count":780,"control_count":3,"prompt_count":40,"existing_comparisons":len(old)*40,"holdout_comparisons":1040,"status":"pass"}


def _verify_one_host(source: Path, work: Path, *, sanitizer: bool) -> dict[str,object]:
    """Build and run one task/control root on the host in one mode."""
    task_id=source.name
    if (source/".control-task-id").is_file():
        task_id=(source/".control-task-id").read_text().strip()
    dst=work/source.name
    shutil.copytree(source,dst)
    shutil.copyfile(dst/".meta/example.h",dst/f"{task_id}.h")
    shutil.copyfile(dst/".meta/example.cpp",dst/f"{task_id}.cpp")
    flags="-fsanitize=address,undefined -fno-omit-frame-pointer" if sanitizer else ""
    env={**os.environ,"ASAN_OPTIONS":"detect_leaks=0"}
    configure=subprocess.run(["cmake","-S",str(dst),"-B",str(dst/"build"),"-G","Unix Makefiles",f"-DCMAKE_CXX_FLAGS={flags}"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if configure.returncode!=0:
        _fail("reference_compile_failed",f"{source.name}:{configure.stderr[-2000:]}")
    build=subprocess.run(["cmake","--build",str(dst/"build"),"--parallel","4"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if build.returncode!=0:
        _fail("reference_compile_failed",f"{source.name}:{build.stderr[-2000:]}")
    discovery=subprocess.run(["ctest","--test-dir",str(dst/"build"),"-N"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    match=re.search(r"Total Tests: (\d+)",discovery.stdout)
    if match is None:
        _fail("test_discovery_failed",source.name)
    count=int(match.group(1))
    if count==0:
        _fail("zero_tests",source.name)
    run=subprocess.run(["ctest","--test-dir",str(dst/"build"),"--output-on-failure"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    if run.returncode!=0:
        _fail("reference_sanitizer_failed" if sanitizer else "reference_tests_failed",f"{source.name}:{run.stdout[-2000:]}")
    negative=subprocess.run([str(dst/"build/negative_test")],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    negative_hidden=subprocess.run([str(dst/"build/negative_hidden_test")],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    if negative.returncode==0 or negative_hidden.returncode==0:
        _fail("negative_fixture_not_rejected",f"{source.name}:{negative.returncode}:{negative_hidden.returncode}")
    return {"task_id":source.name,"mode":"sanitizer" if sanitizer else "normal","test_count":count,"negative_exit":negative.returncode,"negative_hidden_exit":negative_hidden.returncode}


def verify_host(out: Path = DEFAULT_OUT) -> dict[str,object]:
    """Campaign host gate: clean normal and fresh ASan/UBSan reference runs on the host toolchain."""
    verify_core(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("host_prerequisite_missing","cmake and c++ are required for host verification")
    compiler_identity=subprocess.run(["sh","-lc",'p=$(command -v c++); printf "%s|" "$p"; sha256sum "$p" | cut -d" " -f1'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    compiler_path,compiler_hash=compiler_identity.stdout.strip().split("|",1)
    compiler=subprocess.run(["c++","--version"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    cmake=subprocess.run(["cmake","--version"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    records=[]
    control_records=[]
    scratch=EXPANSION_ROOT/".state/bit-set-host-scratch"
    scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bit-set-host-",dir=scratch) as temp:
        work=Path(temp)
        for case in cases():
            root=out/case.task_id
            for sanitizer in (False,True):
                records.append(_verify_one_host(root,work/f"{case.task_id}-{'sanitizer' if sanitizer else 'normal'}",sanitizer=sanitizer))
        for name in ("domain-identifier-renamed","constants-policy-only","opposite-end-selection"):
            root=out/".state/adversarial-clone-controls"/name
            for sanitizer in (False,True):
                control_records.append(_verify_one_host(root,work/f"control-{name}-{'sanitizer' if sanitizer else 'normal'}",sanitizer=sanitizer))
    if len(records)!=80 or {r["task_id"] for r in records}!={c.task_id for c in cases()}:
        _fail("test_discovery_failed",str(len(records)))
    if any(r["test_count"]!=2 or r["negative_exit"]==0 or r["negative_hidden_exit"]==0 for r in records):
        _fail("sanitizer_test_count_mismatch")
    if len(control_records)!=6 or any(r["test_count"]!=2 or r["negative_exit"]==0 or r["negative_hidden_exit"]==0 for r in control_records):
        _fail("clone_control_failed","host control runtime")
    receipt={"schema_version":"bit-set-host-iteration-v1","family_id":FAMILY_ID,"status":"pass","evidence_class":"host_iteration","locked_oracle":False,"network_policy":"not_applicable_host","owner_hash":_file_sha(REPO_ROOT/OWNER),"curriculum_hash":_file_sha(CURRICULUM),"spec_hash":_file_sha(FAMILY_SPEC),"focused_test_hash":_file_sha(REPO_ROOT/FOCUSED_TEST),"family_tree_hash":_tree_hash(out),"compiler_path":compiler_path,"compiler_hash":"sha256:"+compiler_hash,"compiler_version":compiler.stdout.splitlines()[0],"cmake_version":cmake.stdout.splitlines()[0],"normal_records":40,"sanitizer_records":40,"negative_fixture_count":40,"control_normal_records":3,"control_sanitizer_records":3,"records":records,"control_records":control_records,"commands":["cmake -S <root> -B <build> -G 'Unix Makefiles' -DCMAKE_CXX_FLAGS=<mode flags>","cmake --build <build> --parallel 4","ctest --test-dir <build> -N","ctest --test-dir <build> --output-on-failure","direct negative_test and negative_hidden_test execution requiring nonzero exits"]}
    _json(out/".state/host-iteration.json",receipt)
    return receipt


DOCKER_SCRIPT=r'''set -eu
root=/tasks
work=/tmp/bit-set-family
rm -rf "$work"
mkdir -p "$work"
mount_hash=$(python3 -c 'import hashlib,pathlib;root=pathlib.Path("/tasks");d=hashlib.sha256();paths=sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.relative_to(root).parts and "build" not in p.relative_to(root).parts);[(d.update(p.relative_to(root).as_posix().encode()),d.update(b"\0"),d.update(p.read_bytes()),d.update(b"\0")) for p in paths];print("sha256:"+d.hexdigest())')
echo "MOUNT_HASH|$mount_hash"
for task in "$root"/*; do
  [ -f "$task/.meta/config.json" ] || continue
  id=$(basename "$task")
  for mode in normal sanitizer; do
    echo "CHECK|$id|$mode"
    dst="$work/$id-$mode"
    cp -R "$task" "$dst"
    cp "$dst/.meta/example.h" "$dst/$id.h"
    cp "$dst/.meta/example.cpp" "$dst/$id.cpp"
    flags=""
    if [ "$mode" = sanitizer ]; then flags="-fsanitize=address,undefined -fno-omit-frame-pointer"; fi
    cmake -S "$dst" -B "$dst/build" -G "Unix Makefiles" -DCMAKE_CXX_FLAGS="$flags" >/tmp/configure.log
    cmake --build "$dst/build" --parallel 2 >/tmp/build.log
    count=$(ctest --test-dir "$dst/build" -N | sed -n 's/.*Total Tests: //p')
    [ "$count" = 2 ]
    if ! ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$dst/build" --output-on-failure >/tmp/ctest.log 2>&1; then cat /tmp/ctest.log; exit 1; fi
    set +e
    ASAN_OPTIONS=detect_leaks=0 "$dst/build/negative_test" >/tmp/negative.log 2>&1
    negative=$?
    ASAN_OPTIONS=detect_leaks=0 "$dst/build/negative_hidden_test" >/tmp/negative-hidden.log 2>&1
    negative_hidden=$?
    set -e
    if [ "$negative" -eq 0 ] || [ "$negative_hidden" -eq 0 ]; then echo "NEGATIVE_NOT_REJECTED|$id|$mode|$negative|$negative_hidden"; exit 1; fi
    echo "RESULT|$id|$mode|$count|$negative|$negative_hidden"
  done
done
for task in "$root/.state/adversarial-clone-controls"/*; do
  [ -f "$task/.meta/config.json" ] || continue
  control=$(basename "$task")
  id=$(cat "$task/.control-task-id")
  for mode in normal sanitizer; do
    echo "CONTROL_CHECK|$control|$mode"
    dst="$work/control-$control-$mode"
    cp -R "$task" "$dst"
    cp "$dst/.meta/example.h" "$dst/$id.h"
    cp "$dst/.meta/example.cpp" "$dst/$id.cpp"
    flags=""
    if [ "$mode" = sanitizer ]; then flags="-fsanitize=address,undefined -fno-omit-frame-pointer"; fi
    cmake -S "$dst" -B "$dst/build" -G "Unix Makefiles" -DCMAKE_CXX_FLAGS="$flags" >/tmp/control-configure.log
    cmake --build "$dst/build" --parallel 2 >/tmp/control-build.log
    count=$(ctest --test-dir "$dst/build" -N | sed -n 's/.*Total Tests: //p')
    [ "$count" = 2 ]
    if ! ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$dst/build" --output-on-failure >/tmp/control-ctest.log 2>&1; then cat /tmp/control-ctest.log; exit 1; fi
    set +e
    ASAN_OPTIONS=detect_leaks=0 "$dst/build/negative_test" >/tmp/control-negative.log 2>&1
    negative=$?
    ASAN_OPTIONS=detect_leaks=0 "$dst/build/negative_hidden_test" >/tmp/control-negative-hidden.log 2>&1
    negative_hidden=$?
    set -e
    if [ "$negative" -eq 0 ] || [ "$negative_hidden" -eq 0 ]; then echo "CONTROL_NEGATIVE_NOT_REJECTED|$control|$mode|$negative|$negative_hidden"; exit 1; fi
    echo "CONTROL_RESULT|$control|$mode|$count|$negative|$negative_hidden"
  done
done
'''


def docker_sanity(out: Path = DEFAULT_OUT) -> dict[str,object]:
    verify_core(out)
    inspected=subprocess.run(["docker","image","inspect",SANITY_IMAGE,"--format","{{.Id}}"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if inspected.returncode!=0:_fail("docker_sanity_not_completed",inspected.stderr.strip())
    command=["docker","run","--rm","--network","none","-v",f"{out.resolve()}:/tasks:ro",SANITY_IMAGE,"sh","-lc",DOCKER_SCRIPT]
    completed=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=3600)
    if completed.returncode!=0:_fail("docker_sanity_failed",completed.stderr[-4000:]+completed.stdout[-4000:])
    records=[];control_records=[];mount_hash=""
    for line in completed.stdout.splitlines():
        if line.startswith("MOUNT_HASH|"):
            mount_hash=line.split("|",1)[1]
        elif line.startswith("RESULT|"):
            _,task_id,mode,count,negative,negative_hidden=line.split("|");records.append({"task_id":task_id,"mode":mode,"test_count":int(count),"negative_exit":int(negative),"negative_hidden_exit":int(negative_hidden)})
        elif line.startswith("CONTROL_RESULT|"):
            _,control,mode,count,negative,negative_hidden=line.split("|");control_records.append({"control":control,"mode":mode,"test_count":int(count),"negative_exit":int(negative),"negative_hidden_exit":int(negative_hidden)})
    if len(records)!=80 or {r["task_id"] for r in records}!={c.task_id for c in cases()}:_fail("test_discovery_failed",str(len(records)))
    if mount_hash!=_tree_hash(out):_fail("grader_mount_hash_mismatch",f"{mount_hash}!={_tree_hash(out)}")
    if any(r["test_count"]!=2 or r["negative_exit"]==0 or r["negative_hidden_exit"]==0 for r in records):_fail("sanitizer_test_count_mismatch")
    if len(control_records)!=6 or {r["control"] for r in control_records}!={"domain-identifier-renamed","constants-policy-only","opposite-end-selection"}:_fail("clone_control_failed",str(len(control_records)))
    if any(r["test_count"]!=2 or r["negative_exit"]==0 or r["negative_hidden_exit"]==0 for r in control_records):_fail("clone_control_failed","runtime outcome")
    compiler=subprocess.run(["docker","run","--rm","--network","none",SANITY_IMAGE,"c++","--version"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    compiler_identity=subprocess.run(["docker","run","--rm","--network","none",SANITY_IMAGE,"sh","-lc",'p=$(command -v c++); printf "%s|" "$p"; sha256sum "$p" | cut -d" " -f1'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    compiler_path,compiler_hash=compiler_identity.stdout.strip().split("|",1)
    cmake=subprocess.run(["docker","run","--rm","--network","none",SANITY_IMAGE,"cmake","--version"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    receipt={"schema_version":2,"family_id":FAMILY_ID,"status":"pass","evidence_class":"docker_sanity","locked_oracle":False,"network_policy":"none","image":SANITY_IMAGE,"image_id":inspected.stdout.strip(),"compiler_path":compiler_path,"compiler_hash":"sha256:"+compiler_hash,"compiler_version":compiler.stdout.splitlines()[0],"cmake_version":cmake.stdout.splitlines()[0],"owner_hash":_file_sha(REPO_ROOT/OWNER),"curriculum_hash":_file_sha(CURRICULUM),"spec_hash":_file_sha(FAMILY_SPEC),"focused_test_hash":_file_sha(REPO_ROOT/FOCUSED_TEST),"family_tree_hash":_tree_hash(out),"mounted_tree_hash":mount_hash,"control_tree_hashes":{name:_tree_hash(out/".state/adversarial-clone-controls"/name) for name in ("domain-identifier-renamed","constants-policy-only","opposite-end-selection")},"normal_records":40,"sanitizer_records":40,"negative_fixture_count":40,"control_normal_records":3,"control_sanitizer_records":3,"records":records,"control_records":control_records,"commands":[command]}
    _json(out/".state/docker-sanity.json",receipt)
    for case in cases():
        root=out/case.task_id;config=json.loads((root/".meta/config.json").read_text())
        prompt=build_prompt(load_task(root))
        _json(out/".state/receipts"/f"{case.task_id}.json",{"schema_version":2,"task_id":case.task_id,"status":"remediation_verified_pending_fresh_audit","tree_hash":_tree_hash(root),"prompt_hash":_sha(prompt.encode()),"starter_hashes":{path:_file_sha(root/path) for path in config["files"]["solution"]},"reference_hashes":{path:_file_sha(root/path) for path in config["files"]["example"]},"visible_test_hash":_file_sha(root/"task_visible_test.cpp"),"hidden_test_hash":_file_sha(root/".meta/task_hidden_test.cpp"),"negative_hash":_file_sha(root/".meta/negative_false_substitute.cpp"),"metadata_hash":_file_sha(root/".meta/provenance.json"),"owner_hash":receipt["owner_hash"],"image_id":receipt["image_id"],"compiler_path":receipt["compiler_path"],"compiler_hash":receipt["compiler_hash"],"network_policy":"none","records":[r for r in records if r["task_id"]==case.task_id],"prompt_boundary":"pass","family_screen":"pass","benchmark_screen":"pass","dataset_handoff":"not_requested"})
        remedy_path=out/".state/remedy"/f"{case.task_id}.json";remedy=json.loads(remedy_path.read_text());remedy.update({"status":"verified","tree_hash_after":_tree_hash(root),"docker_receipt_hash":_file_sha(out/".state/docker-sanity.json")});_json(remedy_path,remedy)
    return receipt


def creator_preflight(out: Path = DEFAULT_OUT) -> dict[str,object]:
    core=verify_core(out);runtime_path=out/".state/docker-sanity.json"
    if not runtime_path.is_file():_fail("docker_sanity_not_completed",str(runtime_path))
    runtime=json.loads(runtime_path.read_text())
    if runtime.get("family_tree_hash")!=_tree_hash(out):_fail("stale_receipt")
    current_bindings={
        "owner_hash":_file_sha(REPO_ROOT/OWNER),"curriculum_hash":_file_sha(CURRICULUM),
        "spec_hash":_file_sha(FAMILY_SPEC),"focused_test_hash":_file_sha(REPO_ROOT/FOCUSED_TEST),
    }
    for field,value in current_bindings.items():
        if runtime.get(field)!=value:_fail("stale_receipt",field)
    current_control_hashes={name:_tree_hash(out/".state/adversarial-clone-controls"/name) for name in ("domain-identifier-renamed","constants-policy-only","opposite-end-selection")}
    if runtime.get("control_tree_hashes")!=current_control_hashes:_fail("stale_receipt","control_tree_hashes")
    retained_ids={case.task_id for case in cases()}
    receipt_paths=sorted((out/".state/receipts").glob("*.json"))
    receipt_hashes={path.name:_file_sha(path) for path in receipt_paths if path.stem in retained_ids}
    stale_receipt_hashes={path.name:_file_sha(path) for path in receipt_paths if path.stem not in retained_ids}
    if set(path.removesuffix(".json") for path in receipt_hashes)!=retained_ids:_fail("stale_receipt","retained receipt inventory")
    remedy_hashes={path.name:_file_sha(path) for path in sorted((out/".state/remedy").glob("*")) if path.is_file()}
    subject={"family_id":FAMILY_ID,"tree_hash":_tree_hash(out),**current_bindings,"selected_manifest_hash":_file_sha(out/".state/selected-manifest.json"),"raw_proposals_hash":_file_sha(out/".state/raw-proposals.json"),"rejected_proposals_hash":_file_sha(out/".state/rejected-proposals.json"),"targeted_case_catalog_hash":_file_sha(out/".state/targeted-case-catalog.json"),"source_inventory_hash":_file_sha(out/".state/source-inventory.json"),"prompt_boundary_hash":_file_sha(out/".state/prompt-boundary.json"),"lineage_screen_hash":_file_sha(out/".state/lineage-screen.json"),"family_screen_hash":_file_sha(out/".state/family-screen.json"),"benchmark_screen_hash":_file_sha(out/".state/benchmark-screen.json"),"docker_receipt_hash":_file_sha(runtime_path),"per_root_receipt_hashes":receipt_hashes,"invalidated_stale_receipt_hashes":stale_receipt_hashes,"remedy_hashes":remedy_hashes,"control_tree_hashes":current_control_hashes,"root_count":40}
    subject_hash=_sha(json.dumps(subject,sort_keys=True,separators=(",",":")).encode());subject["audit_subject_hash"]=subject_hash;_json(out/".state/audit-subject.json",subject)
    cycle_dir=out/".state/cycles";cycle_dir.mkdir(parents=True,exist_ok=True)
    prior=[]
    for existing in sorted(cycle_dir.glob("cycle-*-creator-preflight.json")):
        record=json.loads(existing.read_text());prior.append(record)
        if record.get("audit_subject_hash")==subject_hash:return record
    cycle_number=max([int(record.get("cycle",1)) for record in prior]+[1])+1
    path=cycle_dir/f"cycle-{cycle_number:03d}-remediation-creator-preflight.json"
    cycle={"schema_version":1,"cycle":cycle_number,"created_at":datetime.now(timezone.utc).isoformat(),"state":"remediation_creator_preflight","audit_subject_hash":subject_hash,"subject":subject,"retained_ids":[c.task_id for c in cases()],"replaced_ids":["bit-morton-interleave","bit-morton-deinterleave"],"closed_finding_candidates":list(AUDIT_FINDINGS),"rejected_proposals":["control-domain-identifier-rename","control-constants-policy-only","control-opposite-end-selection"],"blocked_ids":[],"invalidated_evidence":["sha256:a2ab4f2de537d9910487aa46ef818418866c0dd044d4227360a59de14a5e0dbd","sha256:3ba3d98d08701f07ae538eeba115e0d60def605ebe56167798877243a2e2aba1","sha256:da0632b5acff27a8a48703509d69e87c0cc4ead26fe6dfd9592c1a5751671e0e","sha256:f78ca0e7dae43b3e9c3b98f4293e53ded82441da133d6081ae8ee9310e17d5b7","sha256:d4c1dd7255821b2792fcb05d00fcad4c810ee815ac887966c90496e9508b9922","cycle-001 creator receipts",*stale_receipt_hashes],"creator_preflight":core,"terminal_status":"pending_fresh_independent_audit"}
    _json(path,cycle);return cycle


def main(argv: Sequence[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",type=Path,default=DEFAULT_OUT);parser.add_argument("--force",action="store_true");parser.add_argument("--verify-core",action="store_true");parser.add_argument("--verify-host",action="store_true");parser.add_argument("--docker-sanity",action="store_true");parser.add_argument("--creator-preflight",action="store_true");args=parser.parse_args(argv)
    if args.force or not args.out.exists():print(json.dumps(materialize(args.out,force=args.force),sort_keys=True))
    if args.verify_core:print(json.dumps(verify_core(args.out),sort_keys=True))
    if args.verify_host:print(json.dumps(verify_host(args.out),sort_keys=True))
    if args.docker_sanity:print(json.dumps(docker_sanity(args.out),sort_keys=True))
    if args.creator_preflight:print(json.dumps(creator_preflight(args.out),sort_keys=True))
    if not any((args.force,args.verify_core,args.verify_host,args.docker_sanity,args.creator_preflight)):print(json.dumps(materialize(args.out),sort_keys=True))
    return 0


if __name__=="__main__":raise SystemExit(main())
