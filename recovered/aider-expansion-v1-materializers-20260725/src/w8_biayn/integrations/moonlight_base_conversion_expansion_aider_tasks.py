"""Owner for the 40-root base-conversion numerical-anchor expansion family."""

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
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
CURRICULUM = REPO_ROOT / (
    "docs/aider-synthetic/aider-synthetic-numerical-anchors/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_BASE_CONVERSION_EXPANSION_CURRICULUM.md"
)
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
DEFAULT_OUT = EXPANSION_ROOT / "numerical-anchors/base-conversion-invalid-digits"
EXISTING_ROOTS = (
    REPO_ROOT / ".w8-biayn/data/aider-tasks",
    REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify",
)
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
OWNER = "src/w8_biayn/integrations/moonlight_base_conversion_expansion_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_base_conversion_expansion_aider_tasks.py"
FAMILY_ID = "base-conversion-invalid-digits-v1"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
SANITY_IMAGE_ID = "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
CONTROLS = (
    "domain-identifier-rename",
    "constants-policy-only",
    "opposite-end-selection",
)
REMEDIATIONS = (
    ("BC-AUD-001", "basecv-balanced-ternary-ledger", "Use digit-aware signed Horner bounds and cover both int64 extrema."),
    ("BC-AUD-002", "basecv-base58-byte-envelope", "Validate the leading-zero byte count before base58 conversion."),
    ("BC-AUD-003", "basecv-carryless-polynomial-word", "Enforce canonical exponents and coherent mask/degree state."),
    ("BC-AUD-004", "basecv-residue-crt-reconstruction", "Use overflow-safe modular multiplication for the CRT correction."),
    ("BC-AUD-005", "basecv-redundant-digit-normalizer", "Check signed coefficient-plus-carry arithmetic before evaluation."),
    ("BC-AUD-006", "basecv-repeating-expansion-rational", "Check every rational weight, product, and numerator addition."),
    ("BC-AUD-007", "basecv-twos-complement-hexword", "Avoid implementation-defined uint64-to-int64 conversion."),
    ("BC-AUD-008", "basecv-zeckendorf-fibonacci-code", "Align the checked Fibonacci table with the full uint64 domain."),
    ("BC-AUD-009", "basecv-fixedpoint-base100-chunks", "Reject negative-zero and noncanonical high-zero chunk states."),
    ("BC-AUD-010", "basecv-morton-interleave-radix", "Give invalid inverse digits an explicit optional failure channel."),
    ("BC-AUD-011", "basecv-mixed-radix-timecode", "Reject unpacked day counts outside the Timecode field domain."),
)
REMEDIATION_AUDIT_HASH = "sha256:26f235608bd669c0b91a016ebf4233017b9b169eb1498f4b815f7e2feb7922ec"
REMEDIATION_SUBJECT_HASH = "sha256:68a787f7175cb49a8aee0fe4a75c5f608e8d81bd93f03fcc1a7d548ece0c3f40"
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
PAIR_THRESHOLDS = {
    "public_api": 0.95,
    "owned_state_or_algorithm": 0.68,
    "mutation_or_selection_rules": 0.66,
    "invalid_and_boundary_behavior": 0.68,
    "reference_control_flow": 0.72,
    "deterministic_oracle": 0.66,
    "topic_specific_negative_fixture": 0.72,
}


class CreatorError(RuntimeError):
    """Fail-closed creator/preflight error with a stable reason code."""


@dataclass(frozen=True)
class Spec:
    task_id: str
    title: str
    api: str
    contract: str
    mechanism: str
    forbidden: str
    reference: str
    starter: str
    visible: str
    private: str
    bad_from: str
    bad_to: str
    oracle: str

    @property
    def snake(self) -> str:
        return self.task_id.replace("-", "_")

    @property
    def stem(self) -> str:
        return "".join(word.title() for word in self.task_id.removeprefix("basecv-").split("-"))


def _fail(code: str, detail: str = "") -> None:
    raise CreatorError(f"{code}:{detail}" if detail else code)


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write-then-replace: a previous locked-image (root-in-container)
    # run can leave a non-writable receipt behind; replacing the directory
    # entry only needs directory write permission and never truncates the
    # prior receipt in place.
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(content)
    os.replace(temporary, path)


def _write_json(path: Path, value: object) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _root_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _program(
    task_id: str,
    title: str,
    api: str,
    contract: str,
    mechanism: str,
    forbidden: str,
    reference: str,
    starter: str,
    visible: str,
    private: str,
    bad_from: str,
    bad_to: str,
    oracle: str,
) -> Spec:
    return Spec(task_id, title, api, contract, mechanism, forbidden, reference, starter, visible, private, bad_from, bad_to, oracle)


COMMON_HEADER = """#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
"""

COMMON_SOURCE = """#include <algorithm>
#include <limits>
#include <map>
#include <numeric>
#include <stdexcept>
#include <unordered_map>
"""


def specs() -> tuple[Spec, ...]:
    """Return the 40 independent executable contracts.

    The references intentionally remain source-level separate programs. There
    is no mode switch, generic converter, shared C++ support file, or superset
    state object in the emitted roots.
    """
    p = _program
    rows = (
        p(
            "basecv-radix-frame-stream", "Radix frame stream",
            "struct RadixFrameResult { bool ok; std::uint64_t value; std::size_t consumed; };\nRadixFrameResult decode_radix_frame(std::string_view text, unsigned radix);",
            "Decode one canonical uppercase MSD-first frame in radix 2..16. Require 1..16 digits, reject leading zero except zero, invalid symbols, trailing input, and uint64 overflow.",
            "checked streaming Horner state with an explicit inverse alphabet", "cleanup-first parsing or deferred library conversion",
            "RadixFrameResult decode_radix_frame(std::string_view text,unsigned radix){if(radix<2||radix>16||text.empty()||text.size()>16)return {false,0,0};if(text.size()>1&&text.front()=='0')return {false,0,0};std::uint64_t value=0;std::size_t used=0;for(char c:text){unsigned d=c>='0'&&c<='9'?static_cast<unsigned>(c-'0'):c>='A'&&c<='F'?static_cast<unsigned>(c-'A'+10):99U;if(d>=radix||value>(std::numeric_limits<std::uint64_t>::max()-d)/radix)return {false,0,used};value=value*radix+d;++used;}return {true,value,used};}",
            "RadixFrameResult decode_radix_frame(std::string_view,unsigned){return {false,0,0};}",
            "auto r=decode_radix_frame(\"1A\",16);return r.ok&&r.value==26&&r.consumed==2?0:1;",
            "if(decode_radix_frame(\"2\",2).ok)return 1;if(decode_radix_frame(\"01\",10).ok)return 2;if(decode_radix_frame(\"FFFFFFFFFFFFFFFFF\",16).ok)return 3;auto r=decode_radix_frame(\"101101\",2);return r.ok&&r.value==45?0:4;",
            "if(d>=radix", "if(d>radix", "independent left-fold multiply/add with digit-range and overflow witnesses",
        ),
        p(
            "basecv-chunked-decimal-limbs", "Chunked decimal limbs",
            "std::optional<std::vector<std::uint32_t>> decimal_to_limbs(std::string_view decimal);",
            "Convert a canonical decimal spelling of at most 180 digits to little-endian base-1,000,000,000 limbs; zero is one zero limb. Reject empty, non-digits, and leading zeros.",
            "repeated long division of a mutable decimal digit vector by one billion", "stoull, floating point, or truncating after machine width",
            "std::optional<std::vector<std::uint32_t>> decimal_to_limbs(std::string_view input){std::string s(input);if(s.empty()||s.size()>180||(s.size()>1&&s[0]=='0'))return std::nullopt;for(char c:s)if(c<'0'||c>'9')return std::nullopt;std::vector<std::uint32_t> out;while(!(s.size()==1&&s[0]=='0')){std::string q;std::uint64_t rem=0;for(char c:s){rem=rem*10U+static_cast<unsigned>(c-'0');auto d=rem/1000000000U;rem%=1000000000U;if(!q.empty()||d)q.push_back(static_cast<char>('0'+d));}out.push_back(static_cast<std::uint32_t>(rem));s=q.empty()?std::string(\"0\"):q;}if(out.empty())out.push_back(0);return out;}",
            "std::optional<std::vector<std::uint32_t>> decimal_to_limbs(std::string_view){return std::nullopt;}",
            "auto v=decimal_to_limbs(\"1000000001\");return v&&*v==std::vector<std::uint32_t>({1,1})?0:1;",
            "if(decimal_to_limbs(\"\"))return 1;if(decimal_to_limbs(\"01\"))return 2;if(decimal_to_limbs(\"12x\"))return 3;auto v=decimal_to_limbs(\"999999999999999999999999999\");return v&&v->size()==3?0:4;",
            "while(!(s.size()==1&&s[0]=='0'))", "for(int rounds=0;rounds<2&&!(s.size()==1&&s[0]=='0');++rounds)", "schoolbook base-1e9 recomposition and multi-limb boundary cases",
        ),
        p(
            "basecv-binary-byte-packer", "Binary byte packer",
            "std::optional<std::vector<std::uint8_t>> pack_binary(std::string_view bits, unsigned group_width);",
            "Pack nonempty binary text in exact groups of 1, 2, 4, or 8 bits into one byte per group. Preserve leading zero groups and reject partial groups.",
            "group-bounded shift register reset at each emitted unit", "implicit zero padding or std::bitset cleanup",
            "std::optional<std::vector<std::uint8_t>> pack_binary(std::string_view bits,unsigned width){if(bits.empty()||(width!=1&&width!=2&&width!=4&&width!=8)||bits.size()%width)return std::nullopt;std::vector<std::uint8_t> out;for(std::size_t i=0;i<bits.size();i+=width){unsigned v=0;for(std::size_t j=0;j<width;++j){char c=bits[i+j];if(c!='0'&&c!='1')return std::nullopt;v=(v<<1U)+static_cast<unsigned>(c-'0');}out.push_back(static_cast<std::uint8_t>(v));}return out;}",
            "std::optional<std::vector<std::uint8_t>> pack_binary(std::string_view,unsigned){return std::nullopt;}",
            "auto v=pack_binary(\"00011011\",4);return v&&*v==std::vector<std::uint8_t>({1,11})?0:1;",
            "if(pack_binary(\"101\",2))return 1;if(pack_binary(\"10x0\",2))return 2;auto v=pack_binary(\"00000000\",8);return v&&v->size()==1&&(*v)[0]==0?0:3;",
            "if(bits.empty()||(width!=1&&width!=2&&width!=4&&width!=8)||bits.size()%width)return std::nullopt;std::vector<std::uint8_t> out;", "if(bits.empty()||(width!=1&&width!=2&&width!=4&&width!=8))return std::nullopt;std::string padded(bits);while(padded.size()%width)padded.push_back('0');bits=padded;std::vector<std::uint8_t> out;", "exact unpacked group equality including zero-width preservation",
        ),
        p(
            "basecv-balanced-ternary-ledger", "Balanced ternary ledger",
            "std::optional<std::int64_t> parse_balanced_ternary(std::string_view digits);\nstd::string format_balanced_ternary(std::int64_t value);",
            "Use digits N,0,1 with N=-1. Spell zero as 0; other forms have no leading zero. Parse and format checked signed 64-bit values.",
            "signed Horner parse and Euclidean quotient/remainder carry normalization", "ordinary ternary with a sign prefix",
            "std::optional<std::int64_t> parse_balanced_ternary(std::string_view s){if(s.empty()||(s.size()>1&&s[0]=='0'))return std::nullopt;bool negative=s[0]=='N';std::uint64_t limit=negative?static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())+1U:static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());std::uint64_t magnitude=0;for(char c:s){int d=c=='N'?-1:c=='0'?0:c=='1'?1:9;if(d==9)return std::nullopt;int adjusted=negative?-d:d;if(adjusted>=0){if(magnitude>(limit-static_cast<unsigned>(adjusted))/3U)return std::nullopt;magnitude=magnitude*3U+static_cast<unsigned>(adjusted);}else{if(magnitude>(limit+1U)/3U)return std::nullopt;magnitude=magnitude*3U-1U;}}if(!negative)return static_cast<std::int64_t>(magnitude);if(magnitude==static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())+1U)return std::numeric_limits<std::int64_t>::min();return -static_cast<std::int64_t>(magnitude);}std::string format_balanced_ternary(std::int64_t value){if(value==0)return \"0\";std::string out;while(value!=0){std::int64_t r=value%3;value/=3;if(r==2){r=-1;++value;}if(r==-2){r=1;--value;}out.push_back(r==-1?'N':r==0?'0':'1');}std::reverse(out.begin(),out.end());return out;}",
            "std::optional<std::int64_t> parse_balanced_ternary(std::string_view){return std::nullopt;}std::string format_balanced_ternary(std::int64_t){return {};}",
            "auto lo=std::numeric_limits<std::int64_t>::min();return parse_balanced_ternary(\"1N1\")==7&&format_balanced_ternary(7)==\"1N1\"&&parse_balanced_ternary(format_balanced_ternary(lo))==lo?0:1;",
            "for(int n=-4000;n<=4000;++n){auto s=format_balanced_ternary(n);if(parse_balanced_ternary(s)!=n)return 1;}for(auto n:{std::numeric_limits<std::int64_t>::min(),std::numeric_limits<std::int64_t>::max()})if(parse_balanced_ternary(format_balanced_ternary(n))!=n)return 2;return parse_balanced_ternary(\"2\")?3:0;",
            "c=='N'?-1", "c=='N'?0", "exhaustive signed round-trip over 8,001 values",
        ),
        p(
            "basecv-negabinary-route", "Negabinary route",
            "std::optional<std::int32_t> decode_negabinary(std::string_view bits);\nstd::string encode_negabinary(std::int32_t value);",
            "Use canonical base -2 with digits 0/1 and no sign. Zero is 0 and no other spelling begins with zero.",
            "negative-base Horner plus corrected negative quotient remainder", "sign-magnitude binary",
            "std::optional<std::int32_t> decode_negabinary(std::string_view s){if(s.empty()||(s.size()>1&&s[0]=='0'))return std::nullopt;std::int64_t v=0;for(char c:s){if(c!='0'&&c!='1')return std::nullopt;v=v*-2+(c-'0');if(v<std::numeric_limits<std::int32_t>::min()||v>std::numeric_limits<std::int32_t>::max())return std::nullopt;}return static_cast<std::int32_t>(v);}std::string encode_negabinary(std::int32_t n){if(n==0)return \"0\";std::string s;std::int64_t v=n;while(v){std::int64_t r=v%-2;v/=-2;if(r<0){r+=2;++v;}s.push_back(static_cast<char>('0'+r));}std::reverse(s.begin(),s.end());return s;}",
            "std::optional<std::int32_t> decode_negabinary(std::string_view){return std::nullopt;}std::string encode_negabinary(std::int32_t){return {};}",
            "return decode_negabinary(\"11010\")==6&&encode_negabinary(6)==\"11010\"?0:1;",
            "for(int n=-4096;n<=4096;++n)if(decode_negabinary(encode_negabinary(n))!=n)return 1;return decode_negabinary(\"01\")?2:0;",
            "v=v*-2", "v=v*2", "exhaustive negative-base round-trip across both signs",
        ),
        p(
            "basecv-bijective-label-index", "Bijective label index",
            "struct LabelIndex { std::uint64_t value; std::size_t source_width; };\nstd::optional<LabelIndex> label_index(std::string_view label);\nstd::string index_label(std::uint64_t index);",
            "Convert uppercase bijective A..Z labels with A=1 and no zero digit. Empty, lowercase, zero index, and overflow are invalid.",
            "one-based Horner and n-minus-one quotient correction", "zero-based base-26 with A=0",
            "std::optional<LabelIndex> label_index(std::string_view s){if(s.empty())return std::nullopt;std::uint64_t v=0;for(char c:s){if(c<'A'||c>'Z')return std::nullopt;unsigned d=static_cast<unsigned>(c-'A'+1);if(v>(std::numeric_limits<std::uint64_t>::max()-d)/26)return std::nullopt;v=v*26+d;}return LabelIndex{v,s.size()};}std::string index_label(std::uint64_t n){if(!n)return {};std::string s;while(n){--n;s.push_back(static_cast<char>('A'+n%26));n/=26;}std::reverse(s.begin(),s.end());return s;}",
            "std::optional<LabelIndex> label_index(std::string_view){return std::nullopt;}std::string index_label(std::uint64_t){return {};}",
            "auto v=label_index(\"AA\");return v&&v->value==27&&v->source_width==2&&index_label(27)==\"AA\"?0:1;",
            "for(std::uint64_t n=1;n<=20000;++n){auto v=label_index(index_label(n));if(!v||v->value!=n)return 1;}return label_index(\"a\")?2:0;",
            "c-'A'+1", "c-'A'", "twenty-thousand-value bijective round-trip and Z/AA boundary",
        ),
        p(
            "basecv-factoradic-permutation-rank", "Factoradic permutation rank",
            "std::optional<std::uint64_t> permutation_rank(const std::vector<int>& permutation);\nstd::optional<std::vector<int>> permutation_unrank(std::size_t size, std::uint64_t rank);",
            "Rank and unrank permutations of 0..n-1 for 1<=n<=12. Duplicate/out-of-range values and rank >= n! fail.",
            "Lehmer inversion counts and shrinking ordered pool", "fixed-radix interpretation or permutation enumeration",
            "std::optional<std::uint64_t> permutation_rank(const std::vector<int>& p){if(p.empty()||p.size()>12)return std::nullopt;std::vector<int> pool(p.size());std::iota(pool.begin(),pool.end(),0);std::uint64_t rank=0;for(std::size_t i=0;i<p.size();++i){auto it=std::find(pool.begin(),pool.end(),p[i]);if(it==pool.end())return std::nullopt;rank=rank*pool.size()+static_cast<std::uint64_t>(it-pool.begin());pool.erase(it);}return rank;}std::optional<std::vector<int>> permutation_unrank(std::size_t n,std::uint64_t rank){if(!n||n>12)return std::nullopt;std::uint64_t fact=1;for(std::size_t i=2;i<=n;++i)fact*=i;if(rank>=fact)return std::nullopt;std::vector<int> pool(n),out;std::iota(pool.begin(),pool.end(),0);for(std::size_t left=n;left;--left){fact/=left;std::size_t at=static_cast<std::size_t>(rank/fact);rank%=fact;out.push_back(pool[at]);pool.erase(pool.begin()+static_cast<std::ptrdiff_t>(at));}return out;}",
            "std::optional<std::uint64_t> permutation_rank(const std::vector<int>&){return std::nullopt;}std::optional<std::vector<int>> permutation_unrank(std::size_t,std::uint64_t){return std::nullopt;}",
            "auto r=permutation_rank({2,0,1});auto p=permutation_unrank(3,4);return r==4&&p&&*p==std::vector<int>({2,0,1})?0:1;",
            "for(std::uint64_t r=0;r<40320;++r){auto p=permutation_unrank(8,r);if(!p||permutation_rank(*p)!=r)return 1;}return permutation_rank({0,0})?2:0;",
            "rank=rank*pool.size()", "rank=rank*p.size()", "complete 8-element rank space checked against inverse",
        ),
        p(
            "basecv-mixed-radix-timecode", "Mixed radix timecode",
            "struct Timecode { unsigned days; unsigned hours; unsigned minutes; unsigned seconds; unsigned millis; };\nstd::optional<std::uint64_t> pack_timecode(const Timecode& value);\nstd::optional<Timecode> unpack_timecode(std::uint64_t ticks);",
            "Pack day/hour/minute/second/millisecond fields with radices unbounded/24/60/60/1000. Reject out-of-range fields and overflow.",
            "heterogeneous ordered positional products and reverse remainder extraction", "using base 60 for every field",
            "std::optional<std::uint64_t> pack_timecode(const Timecode& t){if(t.hours>=24||t.minutes>=60||t.seconds>=60||t.millis>=1000)return std::nullopt;std::uint64_t v=t.days;if(v>(std::numeric_limits<std::uint64_t>::max()-t.hours)/24)return std::nullopt;v=v*24+t.hours;v=v*60+t.minutes;v=v*60+t.seconds;if(v>(std::numeric_limits<std::uint64_t>::max()-t.millis)/1000)return std::nullopt;return v*1000+t.millis;}std::optional<Timecode> unpack_timecode(std::uint64_t v){Timecode t{};t.millis=static_cast<unsigned>(v%1000);v/=1000;t.seconds=static_cast<unsigned>(v%60);v/=60;t.minutes=static_cast<unsigned>(v%60);v/=60;t.hours=static_cast<unsigned>(v%24);v/=24;if(v>std::numeric_limits<unsigned>::max())return std::nullopt;t.days=static_cast<unsigned>(v);return t;}",
            "std::optional<std::uint64_t> pack_timecode(const Timecode&){return std::nullopt;}std::optional<Timecode> unpack_timecode(std::uint64_t){return std::nullopt;}",
            "Timecode t{2,3,4,5,6};auto p=pack_timecode(t);auto u=unpack_timecode(*p);return u&&u->days==2&&u->hours==3&&u->millis==6?0:1;",
            "if(pack_timecode({0,24,0,0,0})||unpack_timecode(std::numeric_limits<std::uint64_t>::max()))return 1;for(unsigned h=0;h<24;++h){Timecode t{1,h,59,58,999};auto p=pack_timecode(t);auto u=unpack_timecode(*p);if(!u||u->hours!=h||u->minutes!=59||u->seconds!=58||u->millis!=999)return 2;}return 0;",
            "v=v*60+t.seconds", "v=v*60+t.minutes", "field-product oracle over every hour and mixed-radix boundary",
        ),
        p(
            "basecv-dna-quaternary-packet", "DNA quaternary packet",
            "struct DnaPacket { std::vector<std::uint8_t> bytes; std::size_t bases; };\nstd::optional<DnaPacket> pack_dna(std::string_view bases);\nstd::optional<std::string> unpack_dna(const DnaPacket& packet);",
            "Map A,C,G,T to 0..3, four bases per byte, preserve length, and require unused low tail bits to be zero.",
            "two-bit alphabet cursor with explicit tail canonicality", "dropping length or merging G and T",
            "std::optional<DnaPacket> pack_dna(std::string_view s){if(s.empty())return std::nullopt;DnaPacket p{{},s.size()};std::uint8_t byte=0;for(std::size_t i=0;i<s.size();++i){unsigned d=s[i]=='A'?0:s[i]=='C'?1:s[i]=='G'?2:s[i]=='T'?3:9;if(d>3)return std::nullopt;byte=static_cast<std::uint8_t>((byte<<2U)|d);if(i%4==3){p.bytes.push_back(byte);byte=0;}}unsigned rem=static_cast<unsigned>(s.size()%4);if(rem)p.bytes.push_back(static_cast<std::uint8_t>(byte<<(2U*(4U-rem))));return p;}std::optional<std::string> unpack_dna(const DnaPacket& p){if(!p.bases||p.bytes.size()!=(p.bases+3)/4)return std::nullopt;unsigned unused=static_cast<unsigned>((4-p.bases%4)%4*2);if(unused&&((p.bytes.back()&((1U<<unused)-1U))!=0))return std::nullopt;std::string s;const char* a=\"ACGT\";for(std::size_t i=0;i<p.bases;++i)s.push_back(a[(p.bytes[i/4]>>(6U-2U*(i%4)))&3U]);return s;}",
            "std::optional<DnaPacket> pack_dna(std::string_view){return std::nullopt;}std::optional<std::string> unpack_dna(const DnaPacket&){return std::nullopt;}",
            "auto p=pack_dna(\"ACGTG\");return p&&unpack_dna(*p)==std::optional<std::string>(\"ACGTG\")?0:1;",
            "const char* alphabet=\"ACGT\";for(int mask=0;mask<16384;++mask){std::string s;int v=mask;for(int i=0;i<7;++i){s.push_back(alphabet[v&3]);v>>=2;}auto p=pack_dna(s);if(!p||unpack_dna(*p)!=s)return 1;}DnaPacket bad{{255},1};return unpack_dna(bad)?2:0;",
            "s[i]=='G'?2:s[i]=='T'?3:9", "s[i]=='G'||s[i]=='T'?2:9", "all seven-base words plus nonzero tail-bit rejection",
        ),
        p(
            "basecv-gray-word-radix", "Gray word radix",
            "struct GrayBinaryWord { std::string bits; unsigned source_nibbles; };\nstd::optional<GrayBinaryWord> gray_hex_to_binary(std::string_view hex);",
            "Convert 1..8 uppercase hexadecimal Gray-code digits to a same-width binary string; retain leading zeros and reject lowercase/invalid glyphs.",
            "nibble parsing followed by prefix-XOR Gray inversion", "ordinary hexadecimal-to-binary expansion",
            "std::optional<GrayBinaryWord> gray_hex_to_binary(std::string_view s){if(s.empty()||s.size()>8)return std::nullopt;std::uint32_t gray=0;for(char c:s){unsigned d=c>='0'&&c<='9'?c-'0':c>='A'&&c<='F'?c-'A'+10:99;if(d>15)return std::nullopt;gray=(gray<<4U)|d;}std::uint32_t binary=0;for(std::uint32_t x=gray;x;x>>=1U)binary^=x;std::string out(s.size()*4,'0');for(std::size_t i=0;i<out.size();++i)if(binary&(1U<<(out.size()-1-i)))out[i]='1';return GrayBinaryWord{out,static_cast<unsigned>(s.size())};}",
            "std::optional<GrayBinaryWord> gray_hex_to_binary(std::string_view){return std::nullopt;}",
            "auto w=gray_hex_to_binary(\"06\");return w&&w->bits==\"00000100\"&&w->source_nibbles==2?0:1;",
            "for(unsigned n=0;n<65536;++n){unsigned g=n^(n>>1U);char buf[5];std::snprintf(buf,sizeof(buf),\"%04X\",g);auto s=gray_hex_to_binary(buf);if(!s||std::stoul(s->bits,nullptr,2)!=n)return 1;}return gray_hex_to_binary(\"af\")?2:0;",
            "binary^=x", "binary=gray", "exhaustive sixteen-bit Gray inversion",
        ),
    )
    # The remaining profiles are appended by _more_specs to keep the owner
    # readable while retaining one explicit source program per root.
    rows += _more_specs()
    if len(rows) != 40 or len({row.task_id for row in rows}) != 40:
        _fail("curriculum_count_mismatch", str(len(rows)))
    curriculum_ids = re.findall(r"^\| `(basecv-[a-z0-9-]+)` \|", CURRICULUM.read_text(), re.M)
    if curriculum_ids != [row.task_id for row in rows]:
        _fail("curriculum_owner_mismatch", f"curriculum={len(curriculum_ids)} owner={len(rows)}")
    return rows


def _more_specs() -> tuple[Spec, ...]:
    """The other thirty independent programs."""
    p = _program
    rows = (
        p(
            "basecv-crockford-alias-decoder", "Crockford alias decoder",
            "struct CrockfordValue { std::uint64_t value; std::string canonical; };\nstd::optional<CrockfordValue> decode_crockford(std::string_view token);",
            "Decode 1..12 uppercase Crockford base32 symbols. O aliases 0 and I/L alias 1; U and lowercase reject. Return canonical spelling and checked value.",
            "table-driven aliases normalized before checked base32 Horner", "permissive RFC base32 or accepting U",
            "std::optional<CrockfordValue> decode_crockford(std::string_view s){const std::string a=\"0123456789ABCDEFGHJKMNPQRSTVWXYZ\";if(s.empty()||s.size()>12)return std::nullopt;CrockfordValue out{0,{}};for(char c:s){char n=c=='O'?'0':(c=='I'||c=='L')?'1':c;auto at=a.find(n);if(at==std::string::npos||out.value>(std::numeric_limits<std::uint64_t>::max()-at)/32)return std::nullopt;out.value=out.value*32+at;out.canonical.push_back(n);}return out;}",
            "std::optional<CrockfordValue> decode_crockford(std::string_view){return std::nullopt;}",
            "auto r=decode_crockford(\"LO\");return r&&r->value==32&&r->canonical==\"10\"?0:1;",
            "if(decode_crockford(\"U\")||decode_crockford(\"a\"))return 1;const std::string a=\"0123456789ABCDEFGHJKMNPQRSTVWXYZ\";for(char c:a)if(!decode_crockford(std::string(1,c)))return 2;return 0;",
            "std::string::npos", "false", "complete alphabet and alias canonicalization matrix",
        ),
        p(
            "basecv-base58-byte-envelope", "Base58 byte envelope",
            "std::optional<std::vector<std::uint8_t>> decode_base58_envelope(std::string_view token);",
            "Decode the Bitcoin base58 alphabet to big-endian bytes and preserve one zero byte per leading 1. Empty and invalid glyphs fail; result is at most 64 bytes.",
            "repeated multiply-58 over a base-256 byte vector", "machine-integer accumulation or leading-zero trimming",
            "std::optional<std::vector<std::uint8_t>> decode_base58_envelope(std::string_view s){const std::string a=\"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz\";if(s.empty())return std::nullopt;std::size_t zeros=0;while(zeros<s.size()&&s[zeros]=='1')++zeros;if(zeros>64)return std::nullopt;std::vector<std::uint8_t> little;for(char c:s.substr(zeros)){auto at=a.find(c);if(at==std::string::npos)return std::nullopt;unsigned carry=static_cast<unsigned>(at);for(auto& byte:little){carry+=58U*byte;byte=static_cast<std::uint8_t>(carry&255U);carry>>=8U;}while(carry){little.push_back(static_cast<std::uint8_t>(carry&255U));carry>>=8U;}if(little.size()+zeros>64)return std::nullopt;}std::vector<std::uint8_t> out(zeros,0);out.insert(out.end(),little.rbegin(),little.rend());return out;}",
            "std::optional<std::vector<std::uint8_t>> decode_base58_envelope(std::string_view){return std::nullopt;}",
            "auto v=decode_base58_envelope(\"11Ldp\");return v&&v->size()==5&&(*v)[0]==0&&(*v)[1]==0&&(*v)[2]==1&&(*v)[4]==3?0:1;",
            "auto a=decode_base58_envelope(\"1\");auto b=decode_base58_envelope(std::string(64,'1'));if(!a||a->size()!=1||!b||b->size()!=64)return 1;if(decode_base58_envelope(std::string(65,'1')))return 2;return decode_base58_envelope(\"0OIl\")?3:0;",
            "out(zeros,0)", "out(zeros?1:0,0)", "leading-one multiplicity plus independent base256 multiply oracle",
        ),
        p(
            "basecv-bcd-nibble-register", "BCD nibble register",
            "std::optional<std::vector<std::uint8_t>> pack_bcd(std::string_view decimal, std::size_t bytes);\nstd::optional<std::string> unpack_bcd(const std::vector<std::uint8_t>& packed);",
            "Pack exactly two decimal digits per requested byte, padding canonically on the left. Unpack rejects nibbles 10..15 and preserves fixed width.",
            "decimal-pair nibble packing with independent high/low validation", "hexadecimal parsing of packed bytes",
            "std::optional<std::vector<std::uint8_t>> pack_bcd(std::string_view s,std::size_t bytes){if(!bytes||bytes>32||s.empty()||s.size()>bytes*2)return std::nullopt;for(char c:s)if(c<'0'||c>'9')return std::nullopt;std::string pad(bytes*2-s.size(),'0');pad+=s;std::vector<std::uint8_t> out;for(std::size_t i=0;i<pad.size();i+=2)out.push_back(static_cast<std::uint8_t>((pad[i]-'0')*16+(pad[i+1]-'0')));return out;}std::optional<std::string> unpack_bcd(const std::vector<std::uint8_t>& p){if(p.empty()||p.size()>32)return std::nullopt;std::string s;for(auto b:p){unsigned hi=b>>4U,lo=b&15U;if(hi>9||lo>9)return std::nullopt;s.push_back(static_cast<char>('0'+hi));s.push_back(static_cast<char>('0'+lo));}return s;}",
            "std::optional<std::vector<std::uint8_t>> pack_bcd(std::string_view,std::size_t){return std::nullopt;}std::optional<std::string> unpack_bcd(const std::vector<std::uint8_t>&){return std::nullopt;}",
            "auto p=pack_bcd(\"123\",2);return p&&unpack_bcd(*p)==std::optional<std::string>(\"0123\")?0:1;",
            "for(unsigned n=0;n<10000;++n){char b[5];std::snprintf(b,sizeof(b),\"%04u\",n);auto p=pack_bcd(b,2);if(!p||unpack_bcd(*p)!=b)return 1;}if(unpack_bcd({0xA0})||unpack_bcd({0x0A})||unpack_bcd({0xFA}))return 2;return 0;",
            "if(hi>9||lo>9)", "if(hi>9&&lo>9)", "exhaustive two-byte BCD round-trip and forbidden nibble matrix",
        ),
        p(
            "basecv-little-endian-digit-vector", "Little-endian digit vector",
            "std::optional<std::uint64_t> little_digits_value(const std::vector<std::uint8_t>& digits, std::uint8_t radix);",
            "Interpret nonempty least-significant-first digits in radix 2..32. Trailing zero digits are significant width but not value; invalid digits and overflow reject.",
            "checked forward power accumulation in little-endian order", "reversing into an MSD parser",
            "std::optional<std::uint64_t> little_digits_value(const std::vector<std::uint8_t>& d,std::uint8_t radix){if(d.empty()||radix<2||radix>32)return std::nullopt;std::uint64_t value=0,power=1;for(std::size_t i=0;i<d.size();++i){if(d[i]>=radix||(d[i]&&power>(std::numeric_limits<std::uint64_t>::max()-value)/d[i]))return std::nullopt;value+=power*d[i];if(i+1<d.size()&&power>std::numeric_limits<std::uint64_t>::max()/radix)return std::nullopt;power*=radix;}return value;}",
            "std::optional<std::uint64_t> little_digits_value(const std::vector<std::uint8_t>&,std::uint8_t){return std::nullopt;}",
            "return little_digits_value({5,4,3},10)==345?0:1;",
            "if(little_digits_value({},10)||little_digits_value({2},2))return 1;if(little_digits_value({1,0,0},2)!=1)return 2;return little_digits_value({1,1,1,1},2)==15?0:3;",
            "value+=power*d[i]", "value=value*radix+d[i]", "per-position power sum including significant high zero positions",
        ),
        p(
            "basecv-sparse-power-numeral", "Sparse power numeral",
            "struct SparseTerm { unsigned exponent; unsigned digit; };\nstd::optional<std::uint64_t> sparse_numeral_value(const std::vector<SparseTerm>& terms, unsigned radix);",
            "Decode strictly decreasing unique exponent terms in radix 2..16. Missing powers are zero; exponent<=31, digits valid, and every operation checked.",
            "gap-aware checked exponentiation and sparse weighted accumulation", "dense expansion or unordered overwrite",
            "std::optional<std::uint64_t> sparse_numeral_value(const std::vector<SparseTerm>& terms,unsigned radix){if(terms.empty()||radix<2||radix>16)return std::nullopt;std::uint64_t sum=0;unsigned prior=32;for(auto t:terms){if(t.exponent>=prior||t.exponent>31||t.digit>=radix)return std::nullopt;prior=t.exponent;std::uint64_t power=1,base=radix;unsigned e=t.exponent;while(e){if(e&1U){if(power>std::numeric_limits<std::uint64_t>::max()/base)return std::nullopt;power*=base;}e>>=1U;if(e){if(base>std::numeric_limits<std::uint64_t>::max()/base)return std::nullopt;base*=base;}}if(t.digit&&power>(std::numeric_limits<std::uint64_t>::max()-sum)/t.digit)return std::nullopt;sum+=power*t.digit;}return sum;}",
            "std::optional<std::uint64_t> sparse_numeral_value(const std::vector<SparseTerm>&,unsigned){return std::nullopt;}",
            "return sparse_numeral_value({{4,2},{1,3},{0,1}},10)==20031?0:1;",
            "if(sparse_numeral_value({{1,1},{2,1}},2))return 1;if(sparse_numeral_value({{2,1},{2,0}},2))return 2;return sparse_numeral_value({{10,1},{0,1}},2)==1025?0:3;",
            "power*t.digit", "static_cast<std::uint64_t>(t.digit)*radix", "dense independent reconstruction with ordering and gap mutations",
        ),
        p(
            "basecv-redundant-digit-normalizer", "Redundant digit normalizer",
            "std::optional<std::vector<unsigned>> normalize_redundant_digits(std::vector<std::int64_t> coefficients, unsigned radix);",
            "Normalize nonempty signed little-endian coefficients into canonical digits for radix 2..16. Fail if the represented total is negative or carry exceeds 64 positions.",
            "Euclidean carry propagation with corrected negative remainder", "per-digit clamp or C++ truncating remainder",
            "std::optional<std::vector<unsigned>> normalize_redundant_digits(std::vector<std::int64_t> c,unsigned radix){if(c.empty()||radix<2||radix>16)return std::nullopt;std::vector<unsigned> out;std::int64_t carry=0;for(std::size_t i=0;i<c.size()||carry;++i){if(i==c.size())c.push_back(0);if(i>=64)return std::nullopt;auto hi=std::numeric_limits<std::int64_t>::max(),lo=std::numeric_limits<std::int64_t>::min();if((c[i]>0&&carry>hi-c[i])||(c[i]<0&&carry<lo-c[i]))return std::nullopt;std::int64_t total=c[i]+carry;std::int64_t rem=total%static_cast<std::int64_t>(radix);carry=total/static_cast<std::int64_t>(radix);if(rem<0){rem+=radix;--carry;}out.push_back(static_cast<unsigned>(rem));}if(carry<0)return std::nullopt;while(out.size()>1&&out.back()==0)out.pop_back();return out;}",
            "std::optional<std::vector<unsigned>> normalize_redundant_digits(std::vector<std::int64_t>,unsigned){return std::nullopt;}",
            "auto v=normalize_redundant_digits({15,-1},10);return v&&*v==std::vector<unsigned>({5})?0:1;",
            "auto a=normalize_redundant_digits({-1,1},10);if(!a||*a!=std::vector<unsigned>({9}))return 1;auto b=normalize_redundant_digits({25,0},10);if(!b||*b!=std::vector<unsigned>({5,2}))return 2;if(normalize_redundant_digits({15,std::numeric_limits<std::int64_t>::max()},10)||normalize_redundant_digits({-15,std::numeric_limits<std::int64_t>::min()},10))return 3;return 0;",
            "if(rem<0)", "if(false&&rem<0)", "signed polynomial equality under deterministic coefficient mutations",
        ),
        p(
            "basecv-runlength-numeral-fold", "Run-length numeral fold",
            "struct DigitRun { unsigned digit; std::uint32_t count; };\nstd::optional<std::uint64_t> fold_digit_runs(const std::vector<DigitRun>& runs, unsigned radix);",
            "Decode a nonempty MSD-first run-length numeral without expansion. Runs are positive, digits valid, total length<=1,000,000, and checked uint64 overflow fails.",
            "binary exponentiation of repeated affine digit blocks", "string expansion or treating each run as one digit",
            "std::optional<std::uint64_t> fold_digit_runs(const std::vector<DigitRun>& runs,unsigned radix){if(runs.empty()||radix<2||radix>16)return std::nullopt;struct Affine{std::optional<std::uint64_t> mul;std::uint64_t add;};auto compose=[](Affine outer,Affine inner)->std::optional<Affine>{auto max=std::numeric_limits<std::uint64_t>::max();std::uint64_t add=outer.add;if(inner.add){if(!outer.mul||*outer.mul>(max-add)/inner.add)return std::nullopt;add+=*outer.mul*inner.add;}std::optional<std::uint64_t> mul;if(outer.mul&&inner.mul&&*inner.mul<=max/ *outer.mul)mul=*outer.mul* *inner.mul;return Affine{mul,add};};std::uint64_t value=0;std::uint64_t length=0;for(auto run:runs){if(!run.count||run.digit>=radix||(length+=run.count)>1000000)return std::nullopt;if(value==0&&run.digit==0)continue;Affine acc{{1},0},power{{radix},run.digit};std::uint32_t count=run.count;while(count){if(count&1U){auto next=compose(power,acc);if(!next)return std::nullopt;acc=*next;}count>>=1U;if(count){auto next=compose(power,power);if(!next)return std::nullopt;power=*next;}}auto max=std::numeric_limits<std::uint64_t>::max();if(value&&(!acc.mul||*acc.mul>(max-acc.add)/value))return std::nullopt;value=acc.add+(value?*acc.mul*value:0);}return value;}",
            "std::optional<std::uint64_t> fold_digit_runs(const std::vector<DigitRun>&,unsigned){return std::nullopt;}",
            "return fold_digit_runs({{1,3},{0,2}},2)==28?0:1;",
            "if(fold_digit_runs({{1,0}},2)||fold_digit_runs({{2,1}},2)||fold_digit_runs({{0,1000001}},2))return 1;if(fold_digit_runs({{0,999936},{1,64}},2)!=std::numeric_limits<std::uint64_t>::max())return 2;return fold_digit_runs({{3,2},{1,1}},4)==61?0:3;",
            "value=acc.add+(value?*acc.mul*value:0)", "value=value*radix+run.digit", "expanded small-run oracle plus count/overflow boundary",
        ),
        p(
            "basecv-streaming-modulus-residue", "Streaming modulus residue",
            "std::optional<std::uint64_t> numeral_residue(std::string_view digits, unsigned radix, std::uint64_t modulus);",
            "Return the residue of up to one million uppercase digits in radix 2..36 without constructing the full value. Modulus must be nonzero.",
            "bounded modular Horner with add-and-double multiplication", "whole-value conversion or stopping at a zero digit",
            "std::optional<std::uint64_t> numeral_residue(std::string_view s,unsigned radix,std::uint64_t mod){if(s.empty()||s.size()>1000000||radix<2||radix>36||!mod)return std::nullopt;auto addmod=[mod](std::uint64_t a,std::uint64_t b){return a>=mod-b?a-(mod-b):a+b;};std::uint64_t r=0;for(char c:s){unsigned d=c>='0'&&c<='9'?c-'0':c>='A'&&c<='Z'?c-'A'+10:99;if(d>=radix)return std::nullopt;std::uint64_t a=r,b=radix,x=0;while(b){if(b&1U)x=addmod(x,a);b>>=1U;if(b)a=addmod(a,a);}r=addmod(x,d%mod);}return r;}",
            "std::optional<std::uint64_t> numeral_residue(std::string_view,unsigned,std::uint64_t){return std::nullopt;}",
            "return numeral_residue(\"12345678901234567890\",10,97)==3?0:1;",
            "if(numeral_residue(\"\",10,7)||numeral_residue(\"2\",2,7)||numeral_residue(\"1\",10,0))return 1;if(numeral_residue(\"101\",2,7)!=5)return 2;return numeral_residue(std::string(1000,'9'),10,11)==0?0:3;",
            "for(char c:s){", "for(char c:s){if(c=='0')break;", "chunked decimal modular oracle on thousand-digit inputs",
        ),
        p(
            "basecv-cross-radix-magnitude-compare", "Cross-radix magnitude compare",
            "struct MagnitudeNumeral { std::string digits; unsigned radix; };\nstd::optional<int> compare_magnitudes(const MagnitudeNumeral& left, const MagnitudeNumeral& right);",
            "Compare canonical nonnegative numerals in bases 2..16, each at most 15 digits. Return -1/0/1 and reject invalid/leading-zero spellings.",
            "dual checked Horner evaluation followed by three-way ordering", "digit-count-only or floating-log comparison",
            "std::optional<int> compare_magnitudes(const MagnitudeNumeral& a,const MagnitudeNumeral& b){auto value=[](const MagnitudeNumeral& n)->std::optional<std::uint64_t>{if(n.digits.empty()||n.digits.size()>15||n.radix<2||n.radix>16||(n.digits.size()>1&&n.digits[0]=='0'))return std::nullopt;std::uint64_t v=0;for(char c:n.digits){unsigned d=c>='0'&&c<='9'?c-'0':c>='A'&&c<='F'?c-'A'+10:99;if(d>=n.radix||v>(std::numeric_limits<std::uint64_t>::max()-d)/n.radix)return std::nullopt;v=v*n.radix+d;}return v;};auto x=value(a),y=value(b);if(!x||!y)return std::nullopt;return *x<*y?-1:*x>*y?1:0;}",
            "std::optional<int> compare_magnitudes(const MagnitudeNumeral&,const MagnitudeNumeral&){return std::nullopt;}",
            "return compare_magnitudes({\"FF\",16},{\"100000000\",2})==-1?0:1;",
            "if(compare_magnitudes({\"01\",10},{\"1\",10}))return 1;if(compare_magnitudes({\"G\",16},{\"0\",10}))return 2;return compare_magnitudes({\"1010\",2},{\"A\",16})==0?0:3;",
            "return *x<*y?-1:*x>*y?1:0;", "return a.digits.size()<b.digits.size()?-1:a.digits.size()>b.digits.size()?1:0;", "near-power and equal-value comparisons across distinct radices",
        ),
        p(
            "basecv-decimal-double-dabble", "Decimal double dabble",
            "struct DabbleDecimal { std::vector<std::uint8_t> digits; std::size_t input_bits; };\nstd::optional<DabbleDecimal> binary_to_decimal_dabble(std::string_view bits);",
            "Convert canonical binary of 1..128 bits to decimal text, retaining zero canonicality and rejecting non-bits.",
            "shift-and-add-3 packed BCD state", "uint64 Horner or omitting add-3 correction",
            "std::optional<DabbleDecimal> binary_to_decimal_dabble(std::string_view bits){if(bits.empty()||bits.size()>128||(bits.size()>1&&bits[0]=='0'))return std::nullopt;std::size_t input_bits=bits.size();std::vector<unsigned> bcd(40,0);for(char bit:bits){if(bit!='0'&&bit!='1')return std::nullopt;for(auto& d:bcd)if(d>=5)d+=3;unsigned carry=static_cast<unsigned>(bit-'0');for(auto it=bcd.rbegin();it!=bcd.rend();++it){unsigned n=(*it<<1U)|carry;*it=n&15U;carry=n>>4U;}}std::vector<std::uint8_t> out;bool seen=false;for(unsigned d:bcd){if(d||seen){if(d>9)return std::nullopt;out.push_back(static_cast<std::uint8_t>(d));seen=true;}}if(!seen)out.push_back(0);return DabbleDecimal{out,input_bits};}",
            "std::optional<DabbleDecimal> binary_to_decimal_dabble(std::string_view){return std::nullopt;}",
            "auto d=binary_to_decimal_dabble(\"11111111\");return d&&d->digits==std::vector<std::uint8_t>({2,5,5})&&d->input_bits==8?0:1;",
            "for(unsigned n=0;n<65536;++n){std::string b;unsigned v=n;do{b.push_back(static_cast<char>('0'+(v&1U)));v>>=1U;}while(v);std::reverse(b.begin(),b.end());auto d=binary_to_decimal_dabble(b);if(!d)return 1;std::string s;for(auto x:d->digits)s.push_back(static_cast<char>('0'+x));if(s!=std::to_string(n))return 2;}return binary_to_decimal_dabble(\"010\")?3:0;",
            "if(d>=5)d+=3", "if(d>=5)++d", "exhaustive sixteen-bit decimal comparison",
        ),
    )
    rows += _final_specs()
    return rows


def _final_specs() -> tuple[Spec, ...]:
    """Last twenty programs."""
    p = _program
    rows = (
        p(
            "basecv-decimal-repeated-halving", "Decimal repeated halving",
            "struct HalvingBinary { std::string bits; std::size_t division_rounds; };\nstd::optional<HalvingBinary> decimal_to_binary_halving(std::string_view decimal);",
            "Convert canonical decimal text of 1..200 digits to canonical binary by repeated decimal division. Reject leading zeros and invalid symbols.",
            "mutable decimal quotient with recorded remainders", "fixed-width integer or recording quotient parity",
            "std::optional<HalvingBinary> decimal_to_binary_halving(std::string_view input){std::string s(input);if(s.empty()||s.size()>200||(s.size()>1&&s[0]=='0'))return std::nullopt;for(char c:s)if(c<'0'||c>'9')return std::nullopt;if(s==\"0\")return HalvingBinary{\"0\",0};std::string bits;std::size_t rounds=0;while(s!=\"0\"){std::string q;unsigned rem=0;for(char c:s){unsigned n=rem*10U+static_cast<unsigned>(c-'0');unsigned d=n/2;rem=n%2;if(!q.empty()||d)q.push_back(static_cast<char>('0'+d));}bits.push_back(static_cast<char>('0'+rem));s=q.empty()?std::string(\"0\"):q;++rounds;}std::reverse(bits.begin(),bits.end());return HalvingBinary{bits,rounds};}",
            "std::optional<HalvingBinary> decimal_to_binary_halving(std::string_view){return std::nullopt;}",
            "auto b=decimal_to_binary_halving(\"65535\");return b&&b->bits==\"1111111111111111\"&&b->division_rounds==16?0:1;",
            "if(decimal_to_binary_halving(\"01\")||decimal_to_binary_halving(\"1x\"))return 1;auto small=decimal_to_binary_halving(\"13\");if(!small||small->bits!=\"1101\")return 2;auto b=decimal_to_binary_halving(std::string(80,'9'));return b&&b->bits.size()>260&&b->division_rounds==b->bits.size()?0:3;",
            "bits.push_back(static_cast<char>('0'+rem))", "bits.push_back(static_cast<char>('0'+(q.empty()?0:(q.back()-'0')%2)))", "decimal-string re-expansion of an eighty-digit input",
        ),
        p(
            "basecv-rational-repeating-expansion", "Rational repeating expansion",
            "struct RadixExpansion { std::vector<unsigned> integer; std::vector<unsigned> prefix; std::vector<unsigned> cycle; };\nstd::optional<RadixExpansion> expand_fraction(std::uint32_t numerator, std::uint32_t denominator, unsigned radix, std::size_t max_period);",
            "Long-divide a nonnegative fraction in radix 2..16 and split the fractional digits at the first repeated remainder. Denominator and period bound must be positive.",
            "remainder-position map and exact cycle extraction", "fixed precision or digit-repeat detection",
            "std::optional<RadixExpansion> expand_fraction(std::uint32_t n,std::uint32_t d,unsigned radix,std::size_t cap){if(!d||radix<2||radix>16||!cap)return std::nullopt;RadixExpansion out;std::uint32_t whole=n/d,rem=n%d;do{out.integer.push_back(whole%radix);whole/=radix;}while(whole);std::reverse(out.integer.begin(),out.integer.end());std::map<std::uint32_t,std::size_t> seen;std::vector<unsigned> digits;while(rem){auto found=seen.find(rem);if(found!=seen.end()){out.prefix.assign(digits.begin(),digits.begin()+static_cast<std::ptrdiff_t>(found->second));out.cycle.assign(digits.begin()+static_cast<std::ptrdiff_t>(found->second),digits.end());return out;}if(digits.size()>=cap)return std::nullopt;seen[rem]=digits.size();std::uint64_t scaled=static_cast<std::uint64_t>(rem)*radix;digits.push_back(static_cast<unsigned>(scaled/d));rem=static_cast<std::uint32_t>(scaled%d);}out.prefix=digits;return out;}",
            "std::optional<RadixExpansion> expand_fraction(std::uint32_t,std::uint32_t,unsigned,std::size_t){return std::nullopt;}",
            "auto e=expand_fraction(1,6,10,20);return e&&e->prefix==std::vector<unsigned>({1})&&e->cycle==std::vector<unsigned>({6})?0:1;",
            "auto a=expand_fraction(1,8,2,20);if(!a||!a->cycle.empty()||a->prefix!=std::vector<unsigned>({0,0,1}))return 1;auto repeat=expand_fraction(1,6,10,20);if(!repeat||repeat->prefix!=std::vector<unsigned>({1})||repeat->cycle!=std::vector<unsigned>({6}))return 2;auto b=expand_fraction(1,7,10,5);return b?3:0;",
            "seen[rem]=digits.size()", "seen[rem%2U]=digits.size()", "exact 1/6 cycle and terminating/past-cap remainder cases",
        ),
        p(
            "basecv-repeating-expansion-rational", "Repeating expansion rational",
            "struct RepeatingDigits { std::vector<unsigned> integer; std::vector<unsigned> prefix; std::vector<unsigned> cycle; };\nstruct ReducedFraction { std::int64_t numerator; std::int64_t denominator; };\nstd::optional<ReducedFraction> repeating_to_fraction(const RepeatingDigits& digits, unsigned radix);",
            "Convert bounded radix 2..10 integer/prefix/cycle digits to a reduced nonnegative fraction. Require nonempty integer and valid digits; cycle may be empty.",
            "separate prefix/cycle power weights followed by gcd reduction", "floating parsing or applying the prefix denominator to the cycle",
            "std::optional<ReducedFraction> repeating_to_fraction(const RepeatingDigits& x,unsigned radix){if(x.integer.empty()||radix<2||radix>10||x.prefix.size()>8||x.cycle.size()>8)return std::nullopt;auto fold=[radix](const std::vector<unsigned>& d)->std::optional<std::int64_t>{std::int64_t v=0;for(unsigned n:d){if(n>=radix||v>(std::numeric_limits<std::int64_t>::max()-n)/radix)return std::nullopt;v=v*radix+n;}return v;};auto mul=[](std::int64_t a,std::int64_t b)->std::optional<std::int64_t>{if(a<0||b<0||(a&&b>std::numeric_limits<std::int64_t>::max()/a))return std::nullopt;return a*b;};auto add=[](std::int64_t a,std::int64_t b)->std::optional<std::int64_t>{if(a<0||b<0||a>std::numeric_limits<std::int64_t>::max()-b)return std::nullopt;return a+b;};auto whole=fold(x.integer),pre=fold(x.prefix),cyc=fold(x.cycle);if(!whole||!pre||!cyc)return std::nullopt;std::int64_t p10=1,c10=1;for(std::size_t i=0;i<x.prefix.size();++i){auto next=mul(p10,radix);if(!next)return std::nullopt;p10=*next;}for(std::size_t i=0;i<x.cycle.size();++i){auto next=mul(c10,radix);if(!next)return std::nullopt;c10=*next;}auto den=x.cycle.empty()?std::optional<std::int64_t>(p10):mul(p10,c10-1);if(!den)return std::nullopt;auto whole_term=mul(*whole,*den),prefix_term=mul(*pre,x.cycle.empty()?1:c10-1);if(!whole_term||!prefix_term)return std::nullopt;auto partial=add(*whole_term,*prefix_term);if(!partial)return std::nullopt;auto num=add(*partial,*cyc);if(!num)return std::nullopt;auto g=std::gcd(*num,*den);return ReducedFraction{*num/g,*den/g};}",
            "std::optional<ReducedFraction> repeating_to_fraction(const RepeatingDigits&,unsigned){return std::nullopt;}",
            "auto f=repeating_to_fraction({{0},{1},{6}},10);return f&&f->numerator==1&&f->denominator==6?0:1;",
            "auto a=repeating_to_fraction({{0},{1,2,5},{}},10);if(!a||a->numerator!=1||a->denominator!=8)return 1;auto b=repeating_to_fraction({{0},{1},{6}},10);if(!b||b->numerator!=1||b->denominator!=6)return 2;if(repeating_to_fraction({{9,9,9,9,9,9,9,9,9,9},{9,9,9,9,9,9,9,9},{9,9,9,9,9,9,9,9}},10))return 3;return repeating_to_fraction({{0},{2},{}},2)?4:0;",
            "mul(p10,c10-1)", "mul(p10,c10)", "known reduced fractions for terminating and repeating expansions plus maximum-length overflow",
        ),
        p(
            "basecv-half-even-fixed-point", "Half-even fixed point",
            "struct FixedRadix { std::uint64_t units; unsigned fractional_digits; unsigned radix; };\nstd::optional<std::uint64_t> requantize_half_even(const FixedRadix& value, unsigned target_radix, unsigned target_fractional_digits);",
            "Requantize a bounded nonnegative fixed-point value between radices 2..16 with at most 8 fractional digits. Round exact ties to an even target unit.",
            "exact integer scale products with quotient/remainder tie classification", "floating point or round-half-up",
            "std::optional<std::uint64_t> requantize_half_even(const FixedRadix& v,unsigned target,unsigned places){if(v.radix<2||v.radix>16||target<2||target>16||v.fractional_digits>8||places>8)return std::nullopt;std::uint64_t den=1,num_scale=1;for(unsigned i=0;i<v.fractional_digits;++i){if(den>std::numeric_limits<std::uint64_t>::max()/v.radix)return std::nullopt;den*=v.radix;}for(unsigned i=0;i<places;++i){if(num_scale>std::numeric_limits<std::uint64_t>::max()/target)return std::nullopt;num_scale*=target;}if(v.units&&num_scale>std::numeric_limits<std::uint64_t>::max()/v.units)return std::nullopt;std::uint64_t num=v.units*num_scale,q=num/den,r=num%den;if(r>den-r||(r==den-r&&(q&1U)))++q;return q;}",
            "std::optional<std::uint64_t> requantize_half_even(const FixedRadix&,unsigned,unsigned){return std::nullopt;}",
            "return requantize_half_even({25,1,10},10,0)==2&&requantize_half_even({35,1,10},10,0)==4?0:1;",
            "for(std::uint64_t n=0;n<100;++n){auto q=requantize_half_even({n,1,10},10,0);if(!q)return 1;if(n==25&&*q!=2)return 2;if(n==45&&*q!=4)return 3;}return 0;",
            "r==den-r&&(q&1U)", "r==den-r", "exhaustive decimal tenths around all half-even ties",
        ),
        p(
            "basecv-signed-magnitude-token", "Signed magnitude token",
            "std::optional<std::int64_t> parse_signed_magnitude(std::string_view token, unsigned radix);\nstd::string format_signed_magnitude(std::int64_t value, unsigned radix);",
            "Require an explicit plus or minus and canonical uppercase magnitude in radix 2..16. Negative zero and leading-zero magnitudes reject; formatting always emits a sign.",
            "unsigned magnitude Horner with asymmetric INT64_MIN application", "signed intermediate accumulation",
            "std::optional<std::int64_t> parse_signed_magnitude(std::string_view s,unsigned radix){if(s.size()<2||radix<2||radix>16||(s[0]!='+'&&s[0]!='-')||(s.size()>2&&s[1]=='0'))return std::nullopt;std::uint64_t mag=0,limit=s[0]=='-'?std::uint64_t{1}<<63U:static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());for(char c:s.substr(1)){unsigned d=c>='0'&&c<='9'?c-'0':c>='A'&&c<='F'?c-'A'+10:99;if(d>=radix||mag>(limit-d)/radix)return std::nullopt;mag=mag*radix+d;}if(s[0]=='-'&&mag==0)return std::nullopt;if(s[0]=='-')return mag==(std::uint64_t{1}<<63U)?std::numeric_limits<std::int64_t>::min():-static_cast<std::int64_t>(mag);return static_cast<std::int64_t>(mag);}std::string format_signed_magnitude(std::int64_t value,unsigned radix){if(radix<2||radix>16)return {};bool neg=value<0;std::uint64_t mag=neg?static_cast<std::uint64_t>(-(value+1))+1:static_cast<std::uint64_t>(value);std::string s;do{s.push_back(\"0123456789ABCDEF\"[mag%radix]);mag/=radix;}while(mag);s.push_back(neg?'-':'+');std::reverse(s.begin(),s.end());return s;}",
            "std::optional<std::int64_t> parse_signed_magnitude(std::string_view,unsigned){return std::nullopt;}std::string format_signed_magnitude(std::int64_t,unsigned){return {};}",
            "auto n=std::numeric_limits<std::int64_t>::min();return parse_signed_magnitude(format_signed_magnitude(n,16),16)==n?0:1;",
            "if(parse_signed_magnitude(\"-0\",10)||parse_signed_magnitude(\"+01\",10))return 1;for(int n=-10000;n<=10000;++n)if(parse_signed_magnitude(format_signed_magnitude(n,7),7)!=n)return 2;return 0;",
            "std::uint64_t mag=neg?static_cast<std::uint64_t>(-(value+1))+1:static_cast<std::uint64_t>(value);", "std::uint64_t mag=neg?static_cast<std::uint64_t>(-(value+1)):static_cast<std::uint64_t>(value);", "INT64_MIN boundary and signed radix-seven round-trip",
        ),
        p(
            "basecv-ones-complement-word", "Ones complement word",
            "struct OnesValue { std::int64_t value; bool negative_zero; };\nstd::optional<OnesValue> decode_ones_word(std::string_view bits);",
            "Decode exact widths 4, 8, 12, 16, 24, or 32 as one's complement, preserving the distinct all-ones negative zero state.",
            "width mask plus complemented negative magnitude and dual-zero flag", "two's-complement sign extension",
            "std::optional<OnesValue> decode_ones_word(std::string_view s){if(s.size()!=4&&s.size()!=8&&s.size()!=12&&s.size()!=16&&s.size()!=24&&s.size()!=32)return std::nullopt;std::uint64_t word=0;for(char c:s){if(c!='0'&&c!='1')return std::nullopt;word=(word<<1U)+static_cast<unsigned>(c-'0');}std::uint64_t mask=(std::uint64_t{1}<<s.size())-1;if(!(word&(std::uint64_t{1}<<(s.size()-1))))return OnesValue{static_cast<std::int64_t>(word),false};std::uint64_t mag=(~word)&mask;return OnesValue{-static_cast<std::int64_t>(mag),mag==0};}",
            "std::optional<OnesValue> decode_ones_word(std::string_view){return std::nullopt;}",
            "auto z=decode_ones_word(\"1111\");auto n=decode_ones_word(\"1110\");return z&&z->value==0&&z->negative_zero&&n&&n->value==-1?0:1;",
            "for(unsigned w=0;w<4096;++w){std::string s(12,'0');for(unsigned i=0;i<12;++i)if(w&(1U<<(11U-i)))s[i]='1';if(!decode_ones_word(s))return 1;}auto z=decode_ones_word(\"111111111111\");if(!z||!z->negative_zero||z->value!=0)return 2;return decode_ones_word(\"101\")?3:0;",
            "mag==0", "false", "complete twelve-bit word space with dual-zero assertion",
        ),
        p(
            "basecv-twos-complement-hexword", "Twos complement hexword",
            "std::optional<std::int64_t> decode_twos_hex(std::string_view hex, unsigned width_bits);",
            "Decode an exact-width uppercase hexadecimal two's-complement word for widths 8,16,32,64. Text length must equal width/4.",
            "explicit unsigned parse and subtract-two-to-width sign conversion", "strtoll auto-base or sign from first textual digit alone",
            "std::optional<std::int64_t> decode_twos_hex(std::string_view s,unsigned width){if(width!=8&&width!=16&&width!=32&&width!=64)return std::nullopt;if(s.size()!=width/4)return std::nullopt;std::uint64_t word=0;for(char c:s){unsigned d=c>='0'&&c<='9'?c-'0':c>='A'&&c<='F'?c-'A'+10:99;if(d>15)return std::nullopt;word=(word<<4U)+d;}if(width==64){if(word<=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return static_cast<std::int64_t>(word);return -1-static_cast<std::int64_t>(std::numeric_limits<std::uint64_t>::max()-word);}std::uint64_t sign=std::uint64_t{1}<<(width-1);return word&sign?static_cast<std::int64_t>(word-(std::uint64_t{1}<<width)):static_cast<std::int64_t>(word);}",
            "std::optional<std::int64_t> decode_twos_hex(std::string_view,unsigned){return std::nullopt;}",
            "return decode_twos_hex(\"80\",8)==-128&&decode_twos_hex(\"7F\",8)==127?0:1;",
            "if(decode_twos_hex(\"F\",8)||decode_twos_hex(\"ff\",8))return 1;if(decode_twos_hex(\"8000000000000000\",64)!=std::numeric_limits<std::int64_t>::min())return 2;if(decode_twos_hex(\"7FFFFFFFFFFFFFFF\",64)!=std::numeric_limits<std::int64_t>::max())return 3;return decode_twos_hex(\"FFFFFFFFFFFFFFFF\",64)==-1&&decode_twos_hex(\"FFFF\",16)==-1?0:4;",
            "word-(std::uint64_t{1}<<width)", "-static_cast<std::int64_t>(word&((std::uint64_t{1}<<(width-1))-1))", "sign-transition boundary at every supported width",
        ),
        p(
            "basecv-excess-k-instrument", "Excess-k instrument",
            "std::optional<std::int64_t> decode_excess_k(const std::vector<unsigned>& digits, unsigned radix, std::uint64_t bias);",
            "Decode 1..12 MSD-first unsigned digits in radix 2..16, then subtract one whole-value bias. Invalid digits and checked-range failure reject.",
            "checked positional decode followed by one range-checked bias transform", "subtracting bias from every digit",
            "std::optional<std::int64_t> decode_excess_k(const std::vector<unsigned>& d,unsigned radix,std::uint64_t bias){if(d.empty()||d.size()>12||radix<2||radix>16)return std::nullopt;std::uint64_t value=0;for(unsigned x:d){if(x>=radix||value>(std::numeric_limits<std::uint64_t>::max()-x)/radix)return std::nullopt;value=value*radix+x;}if(value>=bias){auto positive=value-bias;if(positive>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;return static_cast<std::int64_t>(positive);}auto negative=bias-value;if(negative>std::uint64_t{1}<<63U)return std::nullopt;return negative==(std::uint64_t{1}<<63U)?std::numeric_limits<std::int64_t>::min():-static_cast<std::int64_t>(negative);}",
            "std::optional<std::int64_t> decode_excess_k(const std::vector<unsigned>&,unsigned,std::uint64_t){return std::nullopt;}",
            "return decode_excess_k({1,0,0},10,100)==0&&decode_excess_k({0,9,9},10,100)==-1?0:1;",
            "for(unsigned v=0;v<256;++v){std::vector<unsigned>d{v/16,v%16};if(decode_excess_k(d,16,128)!=static_cast<int>(v)-128)return 1;}return decode_excess_k({2},2,0)?2:0;",
            "value-bias", "value-static_cast<std::uint64_t>(d.size())*bias", "complete eight-bit excess-128 code space",
        ),
        p(
            "basecv-varint-base128-groups", "Varint base128 groups",
            "std::optional<std::uint64_t> decode_varint(const std::vector<std::uint8_t>& bytes);\nstd::vector<std::uint8_t> encode_varint(std::uint64_t value);",
            "Use little-endian 7-bit payload groups with continuation. Reject empty, unterminated, >10-byte, overflow, and nonminimal encodings.",
            "continuation-state base128 payload accumulation and canonical-length check", "base256 byte interpretation",
            "std::vector<std::uint8_t> encode_varint(std::uint64_t v){std::vector<std::uint8_t> out;do{std::uint8_t b=static_cast<std::uint8_t>(v&127U);v>>=7U;if(v)b|=128U;out.push_back(b);}while(v);return out;}std::optional<std::uint64_t> decode_varint(const std::vector<std::uint8_t>& b){if(b.empty()||b.size()>10)return std::nullopt;std::uint64_t v=0;unsigned shift=0;for(std::size_t i=0;i<b.size();++i){std::uint64_t payload=b[i]&127U;if(shift==63&&payload>1)return std::nullopt;v|=payload<<shift;if(!(b[i]&128U)){if(i+1!=b.size()||encode_varint(v)!=b)return std::nullopt;return v;}shift+=7;}return std::nullopt;}",
            "std::optional<std::uint64_t> decode_varint(const std::vector<std::uint8_t>&){return std::nullopt;}std::vector<std::uint8_t> encode_varint(std::uint64_t){return {};}",
            "auto e=encode_varint(300);return e==std::vector<std::uint8_t>({172,2})&&decode_varint(e)==300?0:1;",
            "for(std::uint64_t n=0;n<100000;n+=97)if(decode_varint(encode_varint(n))!=n)return 1;if(decode_varint({0x80,0x00})||decode_varint({0x80}))return 2;return 0;",
            "encode_varint(v)!=b", "false", "canonical re-encoding plus dense boundary sweep",
        ),
        p(
            "basecv-byteorder-base256-words", "Byteorder base256 words",
            "enum class ByteOrder { big, little };\nstd::optional<std::uint64_t> bytes_to_word(const std::vector<std::uint8_t>& bytes, ByteOrder order);\nstd::vector<std::uint8_t> word_to_bytes(std::uint64_t value, std::size_t width, ByteOrder order);",
            "Convert exact 1..8-byte base256 words in explicitly selected endian order; inverse returns empty when value does not fit width.",
            "direction-selected indexed shift accumulation and emission", "host reinterpret-cast or fixed little endian",
            "std::optional<std::uint64_t> bytes_to_word(const std::vector<std::uint8_t>& b,ByteOrder order){if(b.empty()||b.size()>8)return std::nullopt;std::uint64_t v=0;for(std::size_t i=0;i<b.size();++i){std::size_t at=order==ByteOrder::big?i:b.size()-1-i;v=(v<<8U)|b[at];}return v;}std::vector<std::uint8_t> word_to_bytes(std::uint64_t v,std::size_t width,ByteOrder order){if(!width||width>8||(width<8&&v>=(std::uint64_t{1}<<(width*8))))return {};std::vector<std::uint8_t> b(width);for(std::size_t i=0;i<width;++i){std::size_t at=order==ByteOrder::little?i:width-1-i;b[at]=static_cast<std::uint8_t>(v&255U);v>>=8U;}return b;}",
            "std::optional<std::uint64_t> bytes_to_word(const std::vector<std::uint8_t>&,ByteOrder){return std::nullopt;}std::vector<std::uint8_t> word_to_bytes(std::uint64_t,std::size_t,ByteOrder){return {};}",
            "return bytes_to_word({1,2},ByteOrder::big)==258&&bytes_to_word({1,2},ByteOrder::little)==513?0:1;",
            "for(std::size_t w=1;w<=8;++w){std::uint64_t v=w==8?0xFEDCBA9876543210ULL:(std::uint64_t{1}<<(w*8-1));for(auto o:{ByteOrder::big,ByteOrder::little})if(bytes_to_word(word_to_bytes(v,w,o),o)!=v)return 1;}return 0;",
            "std::size_t at=order==ByteOrder::big?i:b.size()-1-i", "(void)order;std::size_t at=i", "both byte orders at every supported width",
        ),
    )
    rows += _last_ten_specs()
    return rows


def _last_ten_specs() -> tuple[Spec, ...]:
    p = _program
    return (
        p(
            "basecv-carryless-polynomial-word", "Carryless polynomial word",
            "struct Gf2PolynomialWord { std::uint64_t mask; unsigned degree; };\nstd::optional<Gf2PolynomialWord> parse_gf2_polynomial(std::string_view terms);\nstd::string format_gf2_polynomial(const Gf2PolynomialWord& word);",
            "Convert canonical descending terms x^k+x+1 (0<=k<=63) to a binary coefficient mask and back. Duplicate, ascending, malformed, and zero-polynomial spellings reject.",
            "sparse exponent parsing into GF(2) coefficient bits", "integer addition of duplicate powers",
            "std::optional<Gf2PolynomialWord> parse_gf2_polynomial(std::string_view s){if(s.empty())return std::nullopt;std::uint64_t mask=0;unsigned prior=64;std::size_t pos=0;while(pos<s.size()){std::size_t end=s.find('+',pos);auto term=s.substr(pos,end==std::string_view::npos?s.size()-pos:end-pos);unsigned e=0;if(term==\"1\")e=0;else if(term==\"x\")e=1;else if(term.size()>2&&term.substr(0,2)==\"x^\"){auto exponent=term.substr(2);if(exponent.empty()||(exponent.size()>1&&exponent[0]=='0'))return std::nullopt;for(char c:exponent){if(c<'0'||c>'9')return std::nullopt;e=e*10U+static_cast<unsigned>(c-'0');if(e>63)return std::nullopt;}if(e<2)return std::nullopt;}else return std::nullopt;if(e>=prior||(mask&(std::uint64_t{1}<<e)))return std::nullopt;prior=e;mask|=std::uint64_t{1}<<e;if(end==std::string_view::npos)break;pos=end+1;}unsigned degree=0;for(std::uint64_t copy=mask;copy>1;copy>>=1U)++degree;return Gf2PolynomialWord{mask,degree};}std::string format_gf2_polynomial(const Gf2PolynomialWord& word){if(!word.mask||word.degree>63)return {};unsigned actual=0;for(std::uint64_t copy=word.mask;copy>1;copy>>=1U)++actual;if(actual!=word.degree)return {};std::string s;for(int e=63;e>=0;--e)if(word.mask&(std::uint64_t{1}<<e)){if(!s.empty())s+='+';s+=e==0?\"1\":e==1?\"x\":\"x^\"+std::to_string(e);}return s;}",
            "std::optional<Gf2PolynomialWord> parse_gf2_polynomial(std::string_view){return std::nullopt;}std::string format_gf2_polynomial(const Gf2PolynomialWord&){return {};}",
            "auto w=parse_gf2_polynomial(\"x^5+x+1\");return w&&w->mask==35&&w->degree==5&&format_gf2_polynomial(*w)==\"x^5+x+1\"?0:1;",
            "for(std::uint64_t m=1;m<65536;++m){unsigned d=0;for(auto copy=m;copy>1;copy>>=1U)++d;Gf2PolynomialWord w{m,d};auto p=parse_gf2_polynomial(format_gf2_polynomial(w));if(!p||p->mask!=m)return 1;}if(parse_gf2_polynomial(\"x+x\")||parse_gf2_polynomial(\"x^0\")||parse_gf2_polynomial(\"x^01\"))return 2;return format_gf2_polynomial({1,5}).empty()&&format_gf2_polynomial({1,63}).empty()?0:3;",
            "if(e>=prior||(mask&(std::uint64_t{1}<<e)))", "if(e>prior)", "complete sixteen-bit coefficient-mask round-trip and duplicate rejection",
        ),
        p(
            "basecv-zeckendorf-fibonacci-code", "Zeckendorf Fibonacci code",
            "class ZeckendorfCodec { public: std::optional<std::uint64_t> decode(std::string_view bits) const; std::string encode(std::uint64_t value) const; };",
            "Use canonical Zeckendorf digits weighted by 1,2,3,5,... from right to left. Positive values only; require top one and no adjacent ones.",
            "greedy largest-Fibonacci selection and adjacency invariant", "ordinary binary positional weights",
            "std::optional<std::uint64_t> ZeckendorfCodec::decode(std::string_view s) const{if(s.empty()||s[0]!='1')return std::nullopt;std::vector<std::uint64_t> f{1,2};while(f.back()<=std::numeric_limits<std::uint64_t>::max()-f[f.size()-2])f.push_back(f.back()+f[f.size()-2]);if(s.size()>f.size())return std::nullopt;std::uint64_t v=0;for(std::size_t i=0;i<s.size();++i){if(s[i]!='0'&&s[i]!='1')return std::nullopt;if(i&&s[i]=='1'&&s[i-1]=='1')return std::nullopt;if(s[i]=='1'){auto weight=f[s.size()-1-i];if(v>std::numeric_limits<std::uint64_t>::max()-weight)return std::nullopt;v+=weight;}}return v;}std::string ZeckendorfCodec::encode(std::uint64_t n) const{if(!n)return {};std::vector<std::uint64_t> f{1,2};while(f.back()<=n&&f.back()<=std::numeric_limits<std::uint64_t>::max()-f[f.size()-2])f.push_back(f.back()+f[f.size()-2]);if(f.back()>n)f.pop_back();std::string s;for(auto it=f.rbegin();it!=f.rend();++it){if(*it<=n){s+='1';n-=*it;}else s+='0';}return s;}",
            "std::optional<std::uint64_t> ZeckendorfCodec::decode(std::string_view) const{return std::nullopt;}std::string ZeckendorfCodec::encode(std::uint64_t) const{return {};}",
            "ZeckendorfCodec c;return c.encode(100)==\"1000010100\"&&c.decode(c.encode(100))==100?0:1;",
            "ZeckendorfCodec c;for(std::uint64_t n=1;n<=100000;++n)if(c.decode(c.encode(n))!=n)return 1;for(auto n:{std::uint64_t{7540113804746346429ULL},std::numeric_limits<std::uint64_t>::max()})if(c.decode(c.encode(n))!=n)return 2;return c.decode(\"11\")?3:0;",
            "if(i&&s[i]=='1'&&s[i-1]=='1')", "if(false)", "hundred-thousand-value greedy round-trip and adjacency rejection",
        ),
        p(
            "basecv-combinadic-subset-rank", "Combinadic subset rank",
            "std::optional<std::uint64_t> rank_subset(unsigned n, const std::vector<unsigned>& sorted_subset);\nstd::optional<std::vector<unsigned>> unrank_subset(unsigned n, unsigned k, std::uint64_t rank);",
            "Rank sorted k-subsets of 0..n-1 for n<=30 by sum C(a_i,i+1), and greedily invert. Duplicates, disorder, bad rank, and overflow reject.",
            "binomial-weight sum and descending greedy combinadic inversion", "bitmask-as-integer rank",
            "static std::uint64_t choose_value(unsigned n,unsigned k){if(k>n)return 0;k=std::min(k,n-k);std::uint64_t v=1;for(unsigned i=1;i<=k;++i)v=v*(n-k+i)/i;return v;}std::optional<std::uint64_t> rank_subset(unsigned n,const std::vector<unsigned>& s){if(n>30||s.empty())return std::nullopt;std::uint64_t r=0;for(std::size_t i=0;i<s.size();++i){if(s[i]>=n||(i&&s[i]<=s[i-1]))return std::nullopt;r+=choose_value(s[i],static_cast<unsigned>(i+1));}return r;}std::optional<std::vector<unsigned>> unrank_subset(unsigned n,unsigned k,std::uint64_t rank){if(!k||k>n||n>30||rank>=choose_value(n,k))return std::nullopt;std::vector<unsigned> rev;unsigned x=n;for(unsigned i=k;i;--i){do{--x;}while(choose_value(x,i)>rank);rev.push_back(x);rank-=choose_value(x,i);}std::reverse(rev.begin(),rev.end());return rev;}",
            "std::optional<std::uint64_t> rank_subset(unsigned,const std::vector<unsigned>&){return std::nullopt;}std::optional<std::vector<unsigned>> unrank_subset(unsigned,unsigned,std::uint64_t){return std::nullopt;}",
            "auto r=rank_subset(8,{1,4,6});return r&&unrank_subset(8,3,*r)==std::optional<std::vector<unsigned>>({1,4,6})?0:1;",
            "for(unsigned n=3;n<=12;++n)for(unsigned k=1;k<=n;++k)for(std::uint64_t r=0;;++r){auto s=unrank_subset(n,k,r);if(!s)break;if(rank_subset(n,*s)!=r)return 1;}return rank_subset(4,{2,2})?2:0;",
            "choose_value(s[i],static_cast<unsigned>(i+1))", "std::uint64_t{1}<<s[i]", "exhaustive combinadic spaces through n=12",
        ),
        p(
            "basecv-residue-crt-reconstruction", "Residue CRT reconstruction",
            "struct ResidueCongruence { std::uint64_t residue; std::uint64_t modulus; };\nstd::optional<std::uint64_t> reconstruct_crt(const std::vector<ResidueCongruence>& congruences);",
            "Reconstruct the unique value in [0, product) for 1..8 pairwise-coprime congruences. Moduli>1, canonical residues, gcd and product overflow validate.",
            "incremental CRT using extended gcd and modular correction", "concatenating residues or assuming coprimality",
            "static std::int64_t egcd(std::int64_t a,std::int64_t b,std::int64_t& x,std::int64_t& y){if(!b){x=1;y=0;return a;}std::int64_t p=0,q=0,g=egcd(b,a%b,p,q);x=q;y=p-(a/b)*q;return g;}static std::uint64_t crt_addmod(std::uint64_t a,std::uint64_t b,std::uint64_t modulus){return a>=modulus-b?a-(modulus-b):a+b;}static std::uint64_t crt_mulmod(std::uint64_t a,std::uint64_t b,std::uint64_t modulus){std::uint64_t result=0;a%=modulus;while(b){if(b&1U)result=crt_addmod(result,a,modulus);b>>=1U;if(b)a=crt_addmod(a,a,modulus);}return result;}std::optional<std::uint64_t> reconstruct_crt(const std::vector<ResidueCongruence>& c){if(c.empty()||c.size()>8)return std::nullopt;std::uint64_t value=0,product=1;for(auto item:c){if(item.modulus<=1||item.residue>=item.modulus||item.modulus>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())||product>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;std::int64_t x=0,y=0;if(egcd(static_cast<std::int64_t>(product),static_cast<std::int64_t>(item.modulus),x,y)!=1)return std::nullopt;std::uint64_t delta=(item.residue+item.modulus-value%item.modulus)%item.modulus;std::int64_t inv=x%static_cast<std::int64_t>(item.modulus);if(inv<0)inv+=static_cast<std::int64_t>(item.modulus);std::uint64_t step=crt_mulmod(delta,static_cast<std::uint64_t>(inv),item.modulus);if(product>std::numeric_limits<std::uint64_t>::max()/item.modulus||(step&&product>(std::numeric_limits<std::uint64_t>::max()-value)/step))return std::nullopt;value+=product*step;product*=item.modulus;}return value;}",
            "std::optional<std::uint64_t> reconstruct_crt(const std::vector<ResidueCongruence>&){return std::nullopt;}",
            "return reconstruct_crt({{2,3},{3,5},{2,7}})==23?0:1;",
            "for(unsigned n=0;n<105;++n)if(reconstruct_crt({{n%3,3},{n%5,5},{n%7,7}})!=n)return 1;if(reconstruct_crt({{0,10000019},{1000000000038ULL,1000000000039ULL}})!=584371000022790468ULL)return 2;return reconstruct_crt({{1,4},{2,6}})?3:0;",
            "!=1)return std::nullopt", "<1)return std::nullopt", "complete modulo-105 reconstruction plus noncoprime rejection",
        ),
        p(
            "basecv-prime-exponent-product", "Prime exponent product",
            "struct PrimePower { std::uint32_t prime; std::uint32_t exponent; };\nstd::optional<std::uint64_t> prime_powers_value(const std::vector<PrimePower>& factors);",
            "Convert sorted unique prime/exponent factors to a checked uint64 product. Primes must be verified, exponents positive, and list nonempty.",
            "trial-prime validation plus exponentiation-by-squaring product", "positional interpretation of exponents",
            "static bool is_prime(std::uint32_t n){if(n<2)return false;for(std::uint32_t d=2;static_cast<std::uint64_t>(d)*d<=n;++d)if(n%d==0)return false;return true;}std::optional<std::uint64_t> prime_powers_value(const std::vector<PrimePower>& f){if(f.empty())return std::nullopt;std::uint64_t product=1;std::uint32_t prior=0;for(auto x:f){if(x.prime<=prior||!is_prime(x.prime)||!x.exponent)return std::nullopt;prior=x.prime;std::uint64_t power=1,base=x.prime;for(unsigned e=x.exponent;e;e>>=1U){if(e&1U){if(power>std::numeric_limits<std::uint64_t>::max()/base)return std::nullopt;power*=base;}if((e>>1U)&&base>std::numeric_limits<std::uint64_t>::max()/base)return std::nullopt;if(e>>1U)base*=base;}if(product>std::numeric_limits<std::uint64_t>::max()/power)return std::nullopt;product*=power;}return product;}",
            "std::optional<std::uint64_t> prime_powers_value(const std::vector<PrimePower>&){return std::nullopt;}",
            "return prime_powers_value({{2,3},{3,2},{5,1}})==360?0:1;",
            "if(prime_powers_value({{4,1}})||prime_powers_value({{3,1},{2,1}}))return 1;for(unsigned e=1;e<=20;++e){auto v=prime_powers_value({{2,e}});if(!v||*v!=(std::uint64_t{1}<<e))return 2;}return 0;",
            "power*=base", "power+=base", "prime-power product identity and invalid basis mutations",
        ),
        p(
            "basecv-unary-run-radix", "Unary run radix",
            "std::optional<std::vector<unsigned>> unary_runs_to_radix(const std::vector<std::size_t>& runs, unsigned radix);",
            "Sum positive unary run lengths, at most one million marks, then emit canonical MSD-first digits in radix 2..16. Empty means zero; a zero run rejects.",
            "checked run aggregation followed by quotient/remainder digit emission", "counting runs or separators instead of marks",
            "std::optional<std::vector<unsigned>> unary_runs_to_radix(const std::vector<std::size_t>& runs,unsigned radix){if(radix<2||radix>16)return std::nullopt;std::uint64_t total=0;for(auto n:runs){if(!n||n>1000000-total)return std::nullopt;total+=n;}std::vector<unsigned> d;do{d.push_back(static_cast<unsigned>(total%radix));total/=radix;}while(total);std::reverse(d.begin(),d.end());return d;}",
            "std::optional<std::vector<unsigned>> unary_runs_to_radix(const std::vector<std::size_t>&,unsigned){return std::nullopt;}",
            "return unary_runs_to_radix({3,4,5},5)==std::optional<std::vector<unsigned>>({2,2})?0:1;",
            "if(unary_runs_to_radix({1,0},2))return 1;auto a=unary_runs_to_radix({10},7);auto b=unary_runs_to_radix({3,2,5},7);return a==b?0:2;",
            "total+=n", "++total", "partition-invariant tally sum and zero-run rejection",
        ),
        p(
            "basecv-sexagesimal-angle", "Sexagesimal angle",
            "struct SexagesimalAngle { bool negative; unsigned degrees; unsigned minutes; unsigned seconds; unsigned micros; };\nstd::optional<std::int64_t> angle_microarcseconds(const SexagesimalAngle& angle);\nSexagesimalAngle microarcseconds_angle(std::int64_t value);",
            "Convert sign/degrees/minutes/seconds/microseconds to signed microarcseconds. Minutes/seconds<60, micros<1e6, degrees<=180, and negative zero rejects.",
            "mixed-radix magnitude accumulation with sign applied last", "decimal-degree floating point or base100 seconds",
            "std::optional<std::int64_t> angle_microarcseconds(const SexagesimalAngle& a){if(a.degrees>180||a.minutes>=60||a.seconds>=60||a.micros>=1000000)return std::nullopt;std::int64_t value=((static_cast<std::int64_t>(a.degrees)*60+a.minutes)*60+a.seconds)*1000000+a.micros;if(a.negative&&!value)return std::nullopt;return a.negative?-value:value;}SexagesimalAngle microarcseconds_angle(std::int64_t v){SexagesimalAngle a{};a.negative=v<0;std::uint64_t m=a.negative?static_cast<std::uint64_t>(-(v+1))+1:static_cast<std::uint64_t>(v);a.micros=m%1000000;m/=1000000;a.seconds=m%60;m/=60;a.minutes=m%60;m/=60;a.degrees=static_cast<unsigned>(m);return a;}",
            "std::optional<std::int64_t> angle_microarcseconds(const SexagesimalAngle&){return std::nullopt;}SexagesimalAngle microarcseconds_angle(std::int64_t){return {};}",
            "SexagesimalAngle a{true,12,34,56,789};auto v=angle_microarcseconds(a);auto b=microarcseconds_angle(*v);return b.negative&&b.degrees==12&&b.minutes==34&&b.micros==789?0:1;",
            "if(angle_microarcseconds({false,0,60,0,0})||angle_microarcseconds({true,0,0,0,0}))return 1;for(int d=-180;d<=180;++d){auto v=static_cast<std::int64_t>(d)*3600*1000000;auto a=microarcseconds_angle(v);if(angle_microarcseconds(a)!=v)return 2;}SexagesimalAngle p{false,1,12,34,56};auto v=angle_microarcseconds(p);auto q=microarcseconds_angle(*v);return q.minutes==12&&q.seconds==34?0:3;",
            "*60+a.seconds", "*60+a.minutes", "signed degree boundaries and every minute/second carry",
        ),
        p(
            "basecv-fixedpoint-base100-chunks", "Fixed point base100 chunks",
            "struct MoneyChunks { bool negative; std::vector<std::uint8_t> little_base100; };\nstd::optional<MoneyChunks> money_to_chunks(std::string_view decimal);\nstd::string chunks_to_money(const MoneyChunks& chunks);",
            "Convert explicit-sign decimal money with exactly two fractional digits to little-endian base100 pairs. Reject negative zero, leading integer zeros, and extra precision.",
            "lexical sign/scale split followed by decimal-pair chunk construction", "floating conversion or dropping an odd leading digit",
            "std::optional<MoneyChunks> money_to_chunks(std::string_view s){if(s.size()<5||(s[0]!='+'&&s[0]!='-'))return std::nullopt;auto dot=s.find('.');if(dot==std::string::npos||dot+3!=s.size()||dot<2||(dot>2&&s[1]=='0'))return std::nullopt;for(std::size_t i=1;i<s.size();++i)if(i!=dot&&(s[i]<'0'||s[i]>'9'))return std::nullopt;std::string digits(s.substr(1,dot-1));digits+=s.substr(dot+1);if(s[0]=='-'&&std::all_of(digits.begin(),digits.end(),[](char c){return c=='0';}))return std::nullopt;if(digits.size()%2)digits.insert(digits.begin(),'0');MoneyChunks out{s[0]=='-',{}};for(std::size_t i=digits.size();i;i-=2)out.little_base100.push_back(static_cast<std::uint8_t>((digits[i-2]-'0')*10+digits[i-1]-'0'));while(out.little_base100.size()>1&&out.little_base100.back()==0)out.little_base100.pop_back();return out;}std::string chunks_to_money(const MoneyChunks& c){if(c.little_base100.empty()||(c.little_base100.size()>1&&c.little_base100.back()==0)||(c.negative&&std::all_of(c.little_base100.begin(),c.little_base100.end(),[](std::uint8_t n){return n==0;})))return {};std::string d;for(auto it=c.little_base100.rbegin();it!=c.little_base100.rend();++it){if(*it>=100)return {};if(d.empty())d+=std::to_string(*it);else{d.push_back(static_cast<char>('0'+*it/10));d.push_back(static_cast<char>('0'+*it%10));}}while(d.size()<3)d.insert(d.begin(),'0');d.insert(d.end()-2,'.');return std::string(1,c.negative?'-':'+')+d;}",
            "std::optional<MoneyChunks> money_to_chunks(std::string_view){return std::nullopt;}std::string chunks_to_money(const MoneyChunks&){return {};}",
            "auto c=money_to_chunks(\"+12345.67\");return c&&chunks_to_money(*c)==\"+12345.67\"?0:1;",
            "if(money_to_chunks(\"-0.00\")||money_to_chunks(\"+01.00\"))return 1;if(!chunks_to_money({true,{0}}).empty()||!chunks_to_money({false,{1,0}}).empty())return 2;for(int n=0;n<100000;n+=137){std::string s=\"+\"+std::to_string(n/100)+\".\"+(n%100<10?\"0\":\"\")+std::to_string(n%100);auto c=money_to_chunks(s);if(!c||chunks_to_money(*c)!=s)return 3;}return 0;",
            "if(digits.size()%2)digits.insert(digits.begin(),'0');", "if(digits.size()%2)digits.erase(digits.begin());", "exact cents round-trip across odd/even decimal pair counts",
        ),
        p(
            "basecv-morton-interleave-radix", "Morton interleave radix",
            "std::array<std::uint8_t,8> xy_to_quadrants(std::uint8_t x, std::uint8_t y);\nstd::optional<std::pair<std::uint8_t,std::uint8_t>> quadrants_to_xy(const std::array<std::uint8_t,8>& digits);",
            "Convert two 8-bit coordinates to exactly eight base4 quadrant digits by interleaving one x and one y bit per level. Every inverse digit must be <4.",
            "paired-bit Morton interleave and ordered quadrant extraction", "concatenating all x bits then all y bits",
            "std::array<std::uint8_t,8> xy_to_quadrants(std::uint8_t x,std::uint8_t y){std::array<std::uint8_t,8> d{};for(unsigned i=0;i<8;++i){unsigned shift=7-i;d[i]=static_cast<std::uint8_t>(((x>>shift)&1U)*2U+((y>>shift)&1U));}return d;}std::optional<std::pair<std::uint8_t,std::uint8_t>> quadrants_to_xy(const std::array<std::uint8_t,8>& d){std::uint8_t x=0,y=0;for(auto q:d){if(q>=4)return std::nullopt;x=static_cast<std::uint8_t>((x<<1U)|(q>>1U));y=static_cast<std::uint8_t>((y<<1U)|(q&1U));}return std::pair<std::uint8_t,std::uint8_t>{x,y};}",
            "std::array<std::uint8_t,8> xy_to_quadrants(std::uint8_t,std::uint8_t){return {};}std::optional<std::pair<std::uint8_t,std::uint8_t>> quadrants_to_xy(const std::array<std::uint8_t,8>&){return std::nullopt;}",
            "auto d=xy_to_quadrants(0xA5,0x3C);return quadrants_to_xy(d)==std::optional<std::pair<std::uint8_t,std::uint8_t>>(std::pair<std::uint8_t,std::uint8_t>{0xA5,0x3C})?0:1;",
            "for(unsigned x=0;x<256;++x)for(unsigned y=0;y<256;++y)if(quadrants_to_xy(xy_to_quadrants(static_cast<std::uint8_t>(x),static_cast<std::uint8_t>(y)))!=std::optional<std::pair<std::uint8_t,std::uint8_t>>(std::make_pair(static_cast<std::uint8_t>(x),static_cast<std::uint8_t>(y))))return 1;std::array<std::uint8_t,8> bad{4,0,0,0,0,0,0,0};return quadrants_to_xy(bad)?2:0;",
            "*2U+((y>>shift)&1U)", "+((y>>shift)&1U)*2U", "complete 65,536-coordinate interleave bijection",
        ),
        p(
            "basecv-canonical-cantor-pair", "Canonical Cantor pair",
            "struct PairCoord { std::uint32_t x; std::uint32_t y; };\nstd::optional<std::string> cantor_pair_radix(const PairCoord& point, unsigned radix);\nstd::optional<PairCoord> radix_cantor_pair(std::string_view digits, unsigned radix);",
            "Cantor-pair coordinates <=1,000,000, then spell the paired value in uppercase radix 3..20. Parse requires canonical spelling and checked triangular inversion.",
            "overflow-safe diagonal pairing, integer triangular search, and bounded spelling", "delimiter concatenation or row-major x*radix+y",
            "static std::optional<std::uint64_t> pair_value(const PairCoord& p){if(p.x>1000000||p.y>1000000)return std::nullopt;std::uint64_t s=static_cast<std::uint64_t>(p.x)+p.y;return s*(s+1)/2+p.y;}std::optional<std::string> cantor_pair_radix(const PairCoord& p,unsigned radix){auto v=pair_value(p);if(!v||radix<3||radix>20)return std::nullopt;std::string s;do{s.push_back(\"0123456789ABCDEFGHIJ\"[*v%radix]);*v/=radix;}while(*v);std::reverse(s.begin(),s.end());return s;}std::optional<PairCoord> radix_cantor_pair(std::string_view s,unsigned radix){if(s.empty()||radix<3||radix>20||(s.size()>1&&s[0]=='0'))return std::nullopt;std::uint64_t v=0;for(char c:s){auto at=std::string_view(\"0123456789ABCDEFGHIJ\").find(c);if(at>=radix||v>(std::numeric_limits<std::uint64_t>::max()-at)/radix)return std::nullopt;v=v*radix+at;}std::uint64_t lo=0,hi=2000001;while(lo<hi){auto m=(lo+hi+1)/2;std::uint64_t t=m*(m+1)/2;if(t<=v)lo=m;else hi=m-1;}std::uint64_t y=v-lo*(lo+1)/2,x=lo-y;if(x>1000000||y>1000000)return std::nullopt;return PairCoord{static_cast<std::uint32_t>(x),static_cast<std::uint32_t>(y)};}",
            "std::optional<std::string> cantor_pair_radix(const PairCoord&,unsigned){return std::nullopt;}std::optional<PairCoord> radix_cantor_pair(std::string_view,unsigned){return std::nullopt;}",
            "PairCoord p{12,34};auto s=cantor_pair_radix(p,7);auto q=radix_cantor_pair(*s,7);return q&&q->x==12&&q->y==34?0:1;",
            "for(unsigned x=0;x<100;++x)for(unsigned y=0;y<100;++y){PairCoord p{x,y};auto s=cantor_pair_radix(p,19);auto q=radix_cantor_pair(*s,19);if(!q||q->x!=x||q->y!=y)return 1;}return radix_cantor_pair(\"01\",10)?2:0;",
            "return s*(s+1)/2+p.y;", "(void)s;return static_cast<std::uint64_t>(p.x)*20+p.y;", "ten-thousand coordinate bijection and triangular boundaries",
        ),
    )


def _safe_out(out: Path) -> Path:
    resolved = out.resolve(strict=False)
    mounted = os.environ.get("W8_BASECV_DOCKER_RUNTIME") == "1" and resolved == Path("/family")
    if resolved != DEFAULT_OUT.resolve(strict=False) and not mounted:
        _fail("invalid_output_root", str(out))
    if out.is_symlink() or any(parent.is_symlink() for parent in (out, out.parent, out.parent.parent)):
        _fail("invalid_output_root", "symlink")
    for legacy in EXISTING_ROOTS:
        known = legacy.resolve(strict=False)
        if resolved == known or known in resolved.parents:
            _fail("invalid_output_root", str(legacy))
    return out


def _inventory_configs(exclude: Path | None = None) -> list[Path]:
    exclusions = {exclude.resolve(strict=False)} if exclude is not None else set()
    if os.environ.get("W8_BASECV_DOCKER_RUNTIME") == "1":
        exclusions.add(DEFAULT_OUT.resolve(strict=False))
    found: list[Path] = []
    for base in (*EXISTING_ROOTS, EXPANSION_ROOT):
        if not base.is_dir():
            continue
        for config in base.rglob(".meta/config.json"):
            if ".state" in config.parts:
                continue
            root = config.parent.parent.resolve(strict=False)
            if any(root == excluded or excluded in root.parents for excluded in exclusions):
                continue
            found.append(config)
    return sorted(found)


def _inventory_snapshot(exclude: Path | None = None) -> dict[str, object]:
    for _attempt in range(3):
        configs = _inventory_configs(exclude)
        rows = []
        try:
            for config in configs:
                root = config.parent.parent
                rows.append({
                    "task_id": root.name,
                    "root": str(root.relative_to(REPO_ROOT)),
                    "config_hash": _file_hash(config),
                })
        except FileNotFoundError:
            continue
        if configs != _inventory_configs(exclude):
            continue
        payload = "\n".join(f"{row['task_id']}\t{row['root']}\t{row['config_hash']}" for row in rows)
        return {"count": len(rows), "rows": rows, "sha256": _sha_bytes(payload.encode())}
    _fail("source_inventory_unstable", "config path set changed during three consecutive snapshots")


def _guard(spec: Spec) -> str:
    return spec.snake.upper() + "_H"


def _header(spec: Spec) -> str:
    return (
        f"#ifndef {_guard(spec)}\n#define {_guard(spec)}\n{COMMON_HEADER}"
        f"namespace base_conversion_curriculum {{\n{spec.api}\n}}\n#endif\n"
    )


def _source(spec: Spec, *, negative: bool = False) -> str:
    body = spec.reference
    if negative:
        if body.count(spec.bad_from) != 1:
            _fail("negative_fixture_not_unique", spec.task_id)
        body = body.replace(spec.bad_from, spec.bad_to, 1)
        if body == spec.reference:
            _fail("negative_fixture_unchanged", spec.task_id)
    return (
        f'#include "{spec.task_id}.h"\n{COMMON_SOURCE}'
        f"namespace base_conversion_curriculum {{\n{body}\n}}\n"
    )


def _starter(spec: Spec) -> str:
    return (
        f'#include "{spec.task_id}.h"\nnamespace base_conversion_curriculum {{\n'
        f"{spec.starter}\n}}\n"
    )


def _test(spec: Spec, *, private: bool) -> str:
    body = spec.private if private else spec.visible
    return (
        f'#include "{spec.task_id}.h"\n#include <algorithm>\n#include <cstdio>\n'
        "#include <limits>\n#include <numeric>\n#include <string>\n#include <vector>\n"
        f"using namespace base_conversion_curriculum;\nint main(){{{body}}}\n"
    )


def _cmake(spec: Spec) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({spec.snake} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_compile_options(-Wall -Wextra -Wpedantic -Werror)
include_directories(${{CMAKE_CURRENT_SOURCE_DIR}})
enable_testing()
add_executable(visible {spec.task_id}.cpp visible_test.cpp)
add_executable(private {spec.task_id}.cpp .meta/private_test.cpp)
add_executable(negative .meta/negative.cpp .meta/private_test.cpp)
add_test(NAME visible COMMAND visible)
add_test(NAME private COMMAND private)
add_test(NAME negative_fixture COMMAND negative)
set_tests_properties(negative_fixture PROPERTIES WILL_FAIL TRUE)
"""


def _provenance(spec: Spec) -> dict[str, object]:
    return {
        "schema_version": "base-conversion-provenance-v1",
        "task_id": spec.task_id,
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "parent": None,
        "source": str(CURRICULUM.relative_to(REPO_ROOT)),
        "owner": OWNER,
        "authoring": "clean-room repository-authored",
        "license": "CC0-1.0",
        "count_plan_cell": "numerical anchors / arbitrary-base conversion and invalid-digit handling / 40",
        "primary_core_objective": "achieved",
        "mechanism": spec.mechanism,
        "forbidden_substitute": spec.forbidden,
        "deterministic_oracle": spec.oracle,
        "non_claim": "local task candidate only; no SFT release, training authorization, or benchmark claim",
    }


def _render(spec: Spec, root: Path) -> None:
    root.mkdir(parents=True)
    _write(
        root / ".docs/introduction.md",
        f"# {spec.title}\n\n"
        "Numbers wear different costumes. The same value is a string of "
        "decimal digits to a human, a bit pattern to a machine, and something "
        "stranger — balanced ternary, negabinary, bijective labels — to the "
        "protocols and formats in between. Converting between these spellings "
        "is parsing and arithmetic at once, and every base has its own invalid "
        "digits, canonical forms, and overflow edges.\n\n"
        "This exercise is about one such conversion, done exactly.\n",
    )
    _write(
        root / ".docs/instructions.md",
        f"# Instructions\n\n{spec.contract}\n\nPublic API:\n\n```cpp\n{spec.api}\n```\n\n"
        f"## Examples\n\nThe visible check exercises these cases:\n\n```cpp\n{spec.visible}\n```\n\n"
        f"Convert with {spec.mechanism}; {spec.forbidden} cannot produce the documented canonical form. "
        "Validate the complete input before publishing output, keep failure atomic, use checked integer arithmetic, "
        "and preserve the documented canonical form. Inputs are deterministic and offline.\n",
    )
    _write(root / f"{spec.task_id}.h", _header(spec))
    _write(root / f"{spec.task_id}.cpp", _starter(spec))
    _write(root / "visible_test.cpp", _test(spec, private=False))
    _write(root / ".meta/example.h", _header(spec))
    _write(root / ".meta/example.cpp", _source(spec))
    _write(root / ".meta/private_test.cpp", _test(spec, private=True))
    _write(root / ".meta/negative.cpp", _source(spec, negative=True))
    _write(root / "CMakeLists.txt", _cmake(spec))
    _write(root / ".meta/tests.toml", f'[visible]\ndescription="documented canonical example"\n[private]\ndescription="{spec.oracle}"\n[negative]\ndescription="compiled coherent substitute: {spec.forbidden}"\n')
    _write_json(
        root / ".meta/config.json",
        {
            "authors": ["w8-biayn"],
            "blurb": spec.contract,
            "files": {
                "solution": [f"{spec.task_id}.h", f"{spec.task_id}.cpp"],
                "test": ["visible_test.cpp", ".meta/private_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        },
    )
    _write_json(root / ".meta/provenance.json", _provenance(spec))


def _control_spec(variant: str) -> Spec:
    source = specs()[0]
    if variant == "domain-identifier-rename":
        replacements = {
            "Radix frame stream": "Cargo seal stream",
            "RadixFrameResult": "CargoSealResult",
            "decode_radix_frame": "decode_cargo_seal",
            "frame": "seal",
        }
        values = {field: getattr(source, field) for field in source.__dataclass_fields__}
        for field in ("title", "api", "contract", "reference", "starter", "visible", "private"):
            text = values[field]
            for old, new in replacements.items():
                text = text.replace(old, new)
            values[field] = text
        values["task_id"] = source.task_id
        return Spec(**values)
    if variant == "constants-policy-only":
        values = {field: getattr(source, field) for field in source.__dataclass_fields__}
        values["contract"] = source.contract.replace("2..16", "2..15").replace("1..16 digits", "1..15 digits")
        values["reference"] = source.reference.replace("radix>16", "radix>15").replace("text.size()>16", "text.size()>15")
        values["visible"] = source.visible.replace("\"1A\",16", "\"1A\",15").replace("value==26", "value==25")
        return Spec(**values)
    if variant == "opposite-end-selection":
        values = {field: getattr(source, field) for field in source.__dataclass_fields__}
        values["contract"] = source.contract.replace("MSD-first", "LSD-first").replace("leading zero", "trailing zero")
        old = "if(text.size()>1&&text.front()=='0')return {false,0,0};std::uint64_t value=0;std::size_t used=0;for(char c:text){"
        new = "if(text.size()>1&&text.back()=='0')return {false,0,0};std::string ordered(text);std::reverse(ordered.begin(),ordered.end());std::uint64_t value=0;std::size_t used=0;for(char c:ordered){"
        body = source.reference.replace(old, new)
        values["reference"] = body
        values["visible"] = source.visible.replace("value==26", "value==161")
        values["private"] = source.private.replace("\"01\",10", "\"10\",10")
        return Spec(**values)
    _fail("unknown_control", variant)


def _render_controls(out: Path) -> None:
    base = out / ".state/hard-rule-controls"
    for variant in CONTROLS:
        root = base / variant
        _render(_control_spec(variant), root)
        _write_json(root / ".control.json", {"variant": variant, "source_task": specs()[0].task_id, "status": "generated_pending_behavior_check"})


def _saved_history(out: Path) -> dict[Path, bytes]:
    """Preserve only append-only creator/audit/remedy records across regeneration."""
    saved: dict[Path, bytes] = {}
    for name in ("audits", "cycles", "remedy"):
        base = out / ".state" / name
        if not base.exists():
            continue
        if base.is_symlink() or not base.is_dir():
            _fail("unsafe_history_path", str(base))
        for path in sorted(base.rglob("*")):
            if path.is_symlink():
                _fail("unsafe_history_path", str(path))
            if path.is_file():
                saved[path.relative_to(out)] = path.read_bytes()
    return saved


def _write_remediation_records(out: Path) -> None:
    for finding_id, task_id, remedy in REMEDIATIONS:
        _write_json(
            out / ".state/remedy" / f"{finding_id}.json",
            {
                "schema_version": "aider-task-remedy-v1",
                "finding_id": finding_id,
                "task_id": task_id,
                "source_audit": ".state/audits/cycle-01-audit.json",
                "source_audit_hash": REMEDIATION_AUDIT_HASH,
                "source_subject_hash": REMEDIATION_SUBJECT_HASH,
                "remedy": remedy,
                "owner": OWNER,
                "status": "implemented_in_owner_pending_regeneration_and_fresh_audit",
            },
        )


def materialize(out: Path = DEFAULT_OUT, *, force: bool = False) -> dict[str, object]:
    out = _safe_out(out)
    all_specs = specs()
    inventory = _inventory_snapshot(exclude=out)
    existing_ids = {str(row["task_id"]) for row in inventory["rows"]}
    collisions = sorted({spec.task_id for spec in all_specs} & existing_ids)
    if collisions:
        _fail("existing_task_id", ",".join(collisions))
    history: dict[Path, bytes] = {}
    if out.exists():
        manifest_path = out / ".state/manifest.json"
        if not force:
            _fail("output_exists", str(out))
        if not manifest_path.is_file() or json.loads(manifest_path.read_text()).get("owner") != OWNER:
            _fail("foreign_output_root", str(out))
        history = _saved_history(out)
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for spec in all_specs:
        _render(spec, out / spec.task_id)
    _render_controls(out)
    for relative, content in history.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    _write_remediation_records(out)
    state = out / ".state"
    _write_json(state / "source-inventory.json", inventory)
    manifest = {
        "schema_version": "base-conversion-family-v1",
        "family_id": FAMILY_ID,
        "owner": OWNER,
        "focused_test": FOCUSED_TEST,
        "curriculum": str(CURRICULUM.relative_to(REPO_ROOT)),
        "curriculum_hash": _file_hash(CURRICULUM),
        "task_count": 40,
        "task_ids": [spec.task_id for spec in all_specs],
        "controls": list(CONTROLS),
        "remediation_findings": [row[0] for row in REMEDIATIONS],
        "selected_prompts": [
            "docs/aider-tasks-spec/prompts/generate-family-spec.md",
            "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
        ],
        "status": "generated_pending_creator_preflight",
    }
    _write_json(state / "manifest.json", manifest)
    manifest["tree_hash"] = _tree_hash(out)
    _write_json(state / "manifest.json", manifest)
    return manifest


def _canonical_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//[^\n]*|/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STRING ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " STRING ", text)
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)\b", " NUMBER ", text)
    text = text.lower().replace("base_conversion_curriculum", " namespace ")
    text = re.sub(r"basecv_[a-z0-9_]+|basecv-[a-z0-9-]+", " task ", text)
    return tuple(re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|<<|>>|&&|\|\||[-+*/%<>{}=?:]", text))


def _ngrams(tokens: tuple[str, ...], width: int) -> set[str]:
    if not tokens:
        return set()
    if len(tokens) < width:
        return {" ".join(tokens)}
    return {" ".join(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def _control_flow(text: str) -> str:
    tokens = _canonical_tokens(text)
    keep = {
        "if", "else", "for", "while", "do", "switch", "case", "return",
        "break", "continue", "find", "push_back", "insert", "erase", "reverse",
        "nullopt", "min", "max", "gcd", "iota", "all_of",
        "==", "!=", "<=", ">=", "<", ">", "&&", "||", "%", "*", "/", "+", "-", "<<", ">>",
    }
    return " ".join(token for token in tokens if token in keep)


def _source_lines(text: str, needles: tuple[str, ...]) -> str:
    return "\n".join(line for line in text.splitlines() if any(needle in line for needle in needles))


def _api_tokens(text: str) -> tuple[str, ...]:
    """Normalize domain/identifier names while preserving API structure."""
    reserved = {
        "struct", "class", "enum", "public", "private", "const", "bool", "unsigned", "int", "long", "void",
        "std", "uint64_t", "uint32_t", "uint8_t", "int64_t", "int32_t", "size_t", "string", "string_view",
        "vector", "array", "optional", "pair", "true", "false",
    }
    text = re.sub(r"[A-Za-z_][A-Za-z0-9_]*", lambda match: match.group(0) if match.group(0) in reserved else "identifier", text)
    return _canonical_tokens(text)


def _artifact_features(root: Path) -> dict[str, set[str]]:
    config = json.loads((root / ".meta/config.json").read_text())
    header = (root / config["files"]["example"][0]).read_text()
    reference = (root / config["files"]["example"][1]).read_text()
    instructions = (root / ".docs/instructions.md").read_text()
    visible = (root / "visible_test.cpp").read_text()
    private = (root / ".meta/private_test.cpp").read_text()
    negative = (root / ".meta/negative.cpp").read_text()
    ref_tokens = _canonical_tokens(reference)
    neg_tokens = _canonical_tokens(negative)
    changed = tuple(sorted((_ngrams(ref_tokens, 4) ^ _ngrams(neg_tokens, 4))))
    declaration = header[header.find("namespace base_conversion_curriculum") :]
    boundary = "\n".join(
        sentence for sentence in re.split(r"(?<=[.!?])\s+", instructions)
        if any(word in sentence.lower() for word in ("reject", "invalid", "empty", "zero", "overflow", "canonical", "width", "bound"))
    )
    features = {
        "public_api": _ngrams(_api_tokens(declaration), 3),
        "owned_state_or_algorithm": _ngrams(_canonical_tokens(reference), 5),
        "mutation_or_selection_rules": _ngrams(_canonical_tokens(
            _source_lines(reference, ("=", "push_back", "insert", "erase", "reverse", "find", "while", "for"))
            + instructions
        ), 5),
        "invalid_and_boundary_behavior": _ngrams(_canonical_tokens(
            boundary + _source_lines(reference, ("return std::nullopt", "return {};", "if("))
        ), 4),
        "reference_control_flow": _ngrams(_canonical_tokens(_control_flow(reference)), 4),
        "deterministic_oracle": _ngrams(_canonical_tokens(visible + private), 5),
        "topic_specific_negative_fixture": set(changed),
    }
    empty = [dimension for dimension, values in features.items() if not values]
    if empty:
        _fail("hard_rule_evidence_incomplete", f"{root.name}:{','.join(empty)}")
    return features


def _overlap(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _pair_result(left: Path, right: Path) -> dict[str, object]:
    a, b = _artifact_features(left), _artifact_features(right)
    dimensions = {}
    for dimension in DIMENSIONS:
        score = _overlap(a[dimension], b[dimension])
        dimensions[dimension] = {
            "overlap": round(score, 6),
            "threshold": PAIR_THRESHOLDS[dimension],
            "pass": score < PAIR_THRESHOLDS[dimension],
            "left_feature_count": len(a[dimension]),
            "right_feature_count": len(b[dimension]),
        }
    return {"left": left.name, "right": right.name, "dimensions": dimensions, "pass": all(v["pass"] for v in dimensions.values())}


def diversity_screen(out: Path) -> dict[str, object]:
    roots = [out / spec.task_id for spec in specs()]
    pairs = [_pair_result(left, right) for i, left in enumerate(roots) for right in roots[i + 1 :]]
    if len(pairs) != 780:
        _fail("hard_rule_pair_count", str(len(pairs)))
    failed = next((pair for pair in pairs if not pair["pass"]), None)
    if failed:
        _fail("duplicate_family", json.dumps(failed, sort_keys=True)[:1000])
    controls = {}
    source = roots[0]
    for variant in CONTROLS:
        root = out / ".state/hard-rule-controls" / variant
        result = _pair_result(source, root)
        duplicate_dimensions = [dimension for dimension, decision in result["dimensions"].items() if not decision["pass"]]
        changed = [
            path.relative_to(root).as_posix() for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != ".control.json")
            if not (source / path.relative_to(root)).is_file() or path.read_bytes() != (source / path.relative_to(root)).read_bytes()
        ]
        if not changed or set(duplicate_dimensions) != set(DIMENSIONS):
            _fail("clone_control_failed", f"{variant}:changed={len(changed)} duplicate={duplicate_dimensions}")
        controls[variant] = {"changed_files": changed, "pair": result, "duplicate_dimensions": duplicate_dimensions, "status": "semantic_clone_rejected_pending_runtime"}
    result = {
        "schema_version": "base-conversion-diversity-v1",
        "root_count": 40,
        "pair_count": len(pairs),
        "dimensions": list(DIMENSIONS),
        "thresholds": PAIR_THRESHOLDS,
        "pairs": pairs,
        "controls": controls,
        "status": "pass_pending_control_runtime",
    }
    _write_json(out / ".state/diversity-screen.json", result)
    return result


def _role_prompt_check(root: Path) -> dict[str, object]:
    config = json.loads((root / ".meta/config.json").read_text())
    expected = [f"{root.name}.h", f"{root.name}.cpp"]
    if config.get("files", {}).get("solution") != expected:
        _fail("role_conflict", root.name)
    if config["files"].get("example") != [".meta/example.h", ".meta/example.cpp"]:
        _fail("target_reference_mismatch", root.name)
    seen: set[str] = set()
    for role in ("solution", "test", "example"):
        for item in config["files"][role]:
            path = Path(item)
            if path.is_absolute() or ".." in path.parts or item in seen or not (root / path).is_file():
                _fail("unsafe_path", f"{root.name}:{item}")
            seen.add(item)
    prompt_files = [".docs/introduction.md", ".docs/instructions.md", *expected]
    for item in prompt_files:
        if item.startswith(".meta") or item == "CMakeLists.txt":
            _fail("prompt_contract_incomplete", root.name)
    prompt = "\n".join((root / path).read_text() for path in prompt_files)
    for private_marker in (".meta/", "private_test", "negative.cpp", "CMakeLists.txt", "provenance.json"):
        if private_marker in prompt:
            _fail("prompt_contract_incomplete", f"{root.name}:{private_marker}")
    return {"task_id": root.name, "prompt_files": prompt_files, "prompt_hash": _sha_bytes(prompt.encode()), "status": "pass"}


def _semantic_corpus(root: Path) -> set[str]:
    contents = []
    for relative in (".docs/instructions.md", ".meta/example.h", ".meta/example.cpp", "visible_test.cpp", ".meta/private_test.cpp"):
        path = root / relative
        if path.is_file():
            contents.append(path.read_text(errors="ignore"))
    return _ngrams(_canonical_tokens("\n".join(contents)), 7)


def contamination_screen(out: Path) -> dict[str, object]:
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_screen_not_completed", str(HOLDOUT_ROOT))
    holdouts = {path.name: path for path in HOLDOUT_ROOT.iterdir() if path.is_dir()}
    if set(holdouts) != set(OFFICIAL_HOLDOUTS):
        _fail("benchmark_screen_not_completed", f"found={len(holdouts)}")
    holdout_features = {slug: _semantic_corpus(root) for slug, root in holdouts.items()}
    holdout_rows = []
    for spec in specs():
        candidate = _semantic_corpus(out / spec.task_id)
        for slug, features in sorted(holdout_features.items()):
            score = _overlap(candidate, features)
            if score >= 0.30:
                _fail("benchmark_content_overlap", f"{spec.task_id}:{slug}:{score:.4f}")
            holdout_rows.append({"task_id": spec.task_id, "holdout": slug, "overlap": round(score, 6)})
    inventory = _inventory_configs(exclude=out)
    existing_ids: set[str] = set()
    prompt_hashes: dict[str, str] = {}
    reference_hashes: dict[str, str] = {}
    existing_semantics: list[tuple[str, set[str]]] = []
    for config_path in inventory:
        root = config_path.parent.parent
        existing_ids.add(root.name)
        config = json.loads(config_path.read_text())
        docs = "\n".join(path.read_text(errors="ignore") for path in sorted((root / ".docs").glob("*.md"))) if (root / ".docs").is_dir() else ""
        prompt_hashes.setdefault(_sha_bytes(docs.encode()), str(root))
        examples = config.get("files", {}).get("example", []) if isinstance(config, dict) else []
        ref = b"".join((root / path).read_bytes() for path in examples if (root / path).is_file())
        reference_hashes.setdefault(_sha_bytes(ref), str(root))
        existing_semantics.append((str(root), _semantic_corpus(root)))
    cross_rows = []
    for spec in specs():
        root = out / spec.task_id
        if spec.task_id in existing_ids:
            _fail("existing_task_id", spec.task_id)
        role = _role_prompt_check(root)
        ref_hash = _sha_bytes((root / ".meta/example.h").read_bytes() + (root / ".meta/example.cpp").read_bytes())
        if role["prompt_hash"] in prompt_hashes:
            _fail("duplicate_task", f"prompt:{spec.task_id}:{prompt_hashes[role['prompt_hash']]}")
        if ref_hash in reference_hashes:
            _fail("duplicate_task", f"reference:{spec.task_id}:{reference_hashes[ref_hash]}")
        candidate = _semantic_corpus(root)
        maximum = ("", 0.0)
        for other, features in existing_semantics:
            score = _overlap(candidate, features)
            if score > maximum[1]:
                maximum = (other, score)
        if maximum[1] >= 0.42:
            _fail("duplicate_family", f"{spec.task_id}:{maximum[0]}:{maximum[1]:.4f}")
        cross_rows.append({"task_id": spec.task_id, "closest_existing": maximum[0], "max_overlap": round(maximum[1], 6)})
    report = {
        "schema_version": "base-conversion-contamination-v1",
        "normalizer": "artifact-token-7gram-v1",
        "holdout_inventory": 26,
        "holdout_comparisons": len(holdout_rows),
        "holdout_max_overlap": max(row["overlap"] for row in holdout_rows),
        "holdouts": holdout_rows,
        "existing_inventory": len(inventory),
        "cross_tree": cross_rows,
        "status": "pass",
    }
    _write_json(out / ".state/contamination-screen.json", report)
    return report


def _root_catalog(out: Path) -> list[dict[str, object]]:
    rows = []
    for spec in specs():
        root = out / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        rows.append({
            "task_id": spec.task_id,
            "lineage": "new-root",
            "disposition": "candidate_pending_independent_audit",
            "root_hash": _root_hash(root),
            "prompt_hash": _sha_bytes(((root / ".docs/introduction.md").read_text() + (root / ".docs/instructions.md").read_text()).encode()),
            "starter_hashes": {path: _file_hash(root / path) for path in config["files"]["solution"]},
            "reference_hashes": {path: _file_hash(root / path) for path in config["files"]["example"]},
            "test_hashes": {path: _file_hash(root / path) for path in config["files"]["test"]},
            "negative_hash": _file_hash(root / ".meta/negative.cpp"),
            "provenance_hash": _file_hash(root / ".meta/provenance.json"),
        })
    return rows


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    out = _safe_out(out)
    manifest_path = out / ".state/manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "missing manifest")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("owner") != OWNER or manifest.get("task_count") != 40 or manifest.get("task_ids") != [spec.task_id for spec in specs()]:
        _fail("generator_output_drift", "manifest inventory")
    if manifest.get("tree_hash") != _tree_hash(out):
        _fail("generator_output_drift", "tree hash")
    roles = [_role_prompt_check(out / spec.task_id) for spec in specs()]
    diversity = diversity_screen(out)
    contamination = contamination_screen(out)
    catalog = _root_catalog(out)
    _write_json(out / ".state/candidate-manifest.json", {"schema_version": "base-conversion-candidates-v1", "task_count": 40, "rows": catalog, "status": "creator_preflight_pending_runtime"})
    receipt = {
        "schema_version": "base-conversion-creator-preflight-v1",
        "owner": OWNER,
        "owner_hash": _file_hash(REPO_ROOT / OWNER),
        "focused_test_hash": _file_hash(REPO_ROOT / FOCUSED_TEST) if (REPO_ROOT / FOCUSED_TEST).is_file() else None,
        "curriculum_hash": _file_hash(CURRICULUM),
        "tree_hash": _tree_hash(out),
        "root_count": 40,
        "pair_count": diversity["pair_count"],
        "dimensions": list(DIMENSIONS),
        "roles": {"count": len(roles), "status": "pass"},
        "clone_controls": {variant: diversity["controls"][variant]["status"] for variant in CONTROLS},
        "holdout_comparisons": contamination["holdout_comparisons"],
        "cross_tree_inventory": contamination["existing_inventory"],
        "status": "structural_pass_pending_docker_runtime",
    }
    _write_json(out / ".state/creator-preflight.json", receipt)
    return receipt


def _replace_reference(root: Path) -> None:
    config = json.loads((root / ".meta/config.json").read_text())
    for target, example in zip(config["files"]["solution"], config["files"]["example"], strict=True):
        shutil.copy2(root / example, root / target)


def _runtime_one(root: Path, work_parent: Path, *, sanitizer: bool) -> int:
    work = work_parent / root.name
    shutil.copytree(root, work)
    _replace_reference(work)
    build = work / ("build-asan-ubsan" if sanitizer else "build-normal")
    configure = [
        "cmake", "-S", str(work), "-B", str(build), "-G", "Unix Makefiles",
        "-DCMAKE_CXX_COMPILER=c++", "-DCMAKE_BUILD_TYPE=Debug",
    ]
    if sanitizer:
        configure += [
            "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
            "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
        ]
    try:
        subprocess.run(configure, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        subprocess.run(["cmake", "--build", str(build), "-j2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        listing = subprocess.run(["ctest", "--test-dir", str(build), "-N"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
        match = re.search(r"Total Tests: (\d+)", listing)
        if not match:
            _fail("test_discovery_failed", root.name)
        count = int(match.group(1))
        env = os.environ.copy()
        if sanitizer:
            env["ASAN_OPTIONS"] = "detect_leaks=1:halt_on_error=1"
            env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        subprocess.run(["ctest", "--test-dir", str(build), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    except subprocess.CalledProcessError as error:
        _fail("reference_sanitizer_failed" if sanitizer else "reference_tests_failed", f"{root.name}\n{error.stdout[-8000:]}")
    if count != 3:
        _fail("test_discovery_failed", f"{root.name}:{count}")
    return count


def _toolchain_identity() -> dict[str, object]:
    compiler = shutil.which("c++")
    cmake = shutil.which("cmake")
    if not compiler or not cmake:
        _fail("runtime_prerequisite_missing", f"c++={compiler} cmake={cmake}")
    compiler_path = Path(compiler).resolve()
    return {
        "compiler_path": str(compiler_path),
        "compiler_hash": _file_hash(compiler_path),
        "compiler_version": subprocess.run([compiler, "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0],
        "cmake_path": str(Path(cmake).resolve()),
        "cmake_version": subprocess.run([cmake, "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0],
    }


def verify_runtime(out: Path = DEFAULT_OUT, *, evidence_class: str = "host_iteration") -> dict[str, object]:
    verify_core(out)
    rows = []
    failures = []
    with tempfile.TemporaryDirectory(prefix="base-conversion-runtime-") as temporary:
        scratch = Path(temporary)
        targets = [("task", out / spec.task_id) for spec in specs()]
        targets += [("control", out / ".state/hard-rule-controls" / variant) for variant in CONTROLS]
        for category, root in targets:
            try:
                normal = _runtime_one(root, scratch / "normal" / category, sanitizer=False)
            except CreatorError as error:
                failures.append({"category": category, "id": root.name, "mode": "normal", "error": str(error)[-4000:]})
                continue
            try:
                sanitizer = _runtime_one(root, scratch / "sanitizer" / category, sanitizer=True)
            except CreatorError as error:
                failures.append({"category": category, "id": root.name, "mode": "asan_ubsan", "error": str(error)[-4000:]})
                continue
            if normal <= 0 or normal != sanitizer:
                _fail("sanitizer_test_count_mismatch", f"{category}:{root.name}:{normal}:{sanitizer}")
            rows.append({
                "category": category,
                "id": root.name,
                "tree_hash": _root_hash(root),
                "normal": normal,
                "asan_ubsan": sanitizer,
                "negative_compiled_and_rejected": True,
            })
    if failures:
        _write_json(out / ".state/runtime-failures.json", {"schema_version": "base-conversion-runtime-failures-v1", "failures": failures, "status": "failed"})
        _fail("runtime_matrix_failed", json.dumps(failures, sort_keys=True)[-12000:])
    receipt = {
        "schema_version": "base-conversion-runtime-v1",
        "evidence_class": evidence_class,
        "network": "none" if evidence_class == "docker_sanity" else "host",
        "locked_oracle": False,
        "owner_hash": _file_hash(REPO_ROOT / OWNER),
        "curriculum_hash": _file_hash(CURRICULUM),
        "tree_hash": _tree_hash(out),
        "mounted_tree_hash": _tree_hash(out),
        "toolchain": _toolchain_identity(),
        "root_count": 40,
        "control_count": 3,
        "results": rows,
        "status": "pass",
    }
    _write_json(out / ".state/runtime-result.json", receipt)
    return receipt


def _append_creator_cycle(out: Path, runtime: dict[str, object]) -> None:
    state = out / ".state"
    prior = [
        int(match.group(1))
        for path in (state / "cycles").glob("cycle-*-creator.json")
        if (match := re.fullmatch(r"cycle-(\d+)-creator\.json", path.name))
    ]
    cycle_number = max(prior, default=0) + 1
    cycle = {
        "schema_version": "aider-task-creator-cycle-v1",
        "cycle": cycle_number,
        "task_family": FAMILY_ID,
        "candidate_manifest": ".state/candidate-manifest.json",
        "curriculum_hash": _file_hash(CURRICULUM),
        "generator_hash": _file_hash(REPO_ROOT / OWNER),
        "focused_test_hash": _file_hash(REPO_ROOT / FOCUSED_TEST),
        "tree_hash": _tree_hash(out),
        "grader_policy_hash": _sha_bytes(json.dumps({"image": SANITY_IMAGE, "dimensions": DIMENSIONS, "thresholds": PAIR_THRESHOLDS}, sort_keys=True).encode()),
        "root_catalog_hash": _file_hash(state / "candidate-manifest.json"),
        "normal_sanitizer_receipt": ".state/docker-sanity.json",
        "runtime_subject_hash": _sha_bytes(json.dumps(runtime, sort_keys=True).encode()),
        "negative_fixture_count": 40,
        "clone_control_count": 3,
        "benchmark_holdout_count": 26,
        "audit_subject_hash": None,
        "audit_report": None,
        "finding_ids": [row[0] for row in REMEDIATIONS],
        "remediation_records": [f".state/remedy/{row[0]}.json" for row in REMEDIATIONS],
        "retained": [spec.task_id for spec in specs()],
        "replaced": [],
        "rejected": [],
        "review": [],
        "blocked": [],
        "status": "creator_preflight_pass_pending_independent_audit",
    }
    _write_json(state / f"cycles/cycle-{cycle_number:02d}-creator.json", cycle)


def docker_sanity(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    out = _safe_out(out)
    verify_core(out)
    inspected = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if inspected.returncode:
        _fail("docker_sanity_not_completed", inspected.stderr.strip())
    image_id = inspected.stdout.strip()
    if image_id != SANITY_IMAGE_ID:
        _fail("docker_sanity_not_completed", f"unexpected_image_id:{image_id}")
    command = [
        "docker", "run", "--rm", "--network", "none",
        "-e", "PYTHONPATH=/repo/src", "-e", "W8_BASECV_DOCKER_RUNTIME=1",
        "-v", f"{REPO_ROOT}:/repo:ro", "-v", f"{out}:/family:rw",
        "-w", "/repo", image, "python3", "-m",
        "w8_biayn.integrations.moonlight_base_conversion_expansion_aider_tasks",
        "--out", "/family", "--verify-runtime", "--docker-runtime",
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if completed.returncode:
        _fail("docker_sanity_failed", completed.stdout[-12000:])
    result_path = out / ".state/runtime-result.json"
    if not result_path.is_file():
        _fail("docker_sanity_receipt_invalid", "missing runtime result")
    receipt = json.loads(result_path.read_text())
    if (
        receipt.get("status") != "pass"
        or receipt.get("evidence_class") != "docker_sanity"
        or receipt.get("network") != "none"
        or receipt.get("tree_hash") != _tree_hash(out)
        or receipt.get("mounted_tree_hash") != _tree_hash(out)
        or len(receipt.get("results", [])) != 43
    ):
        _fail("docker_sanity_receipt_invalid", "binding")
    receipt.update({"image": image, "image_id": image_id, "docker_command": command, "docker_output_hash": _sha_bytes(completed.stdout.encode()), "status": "pass"})
    _write_json(out / ".state/docker-sanity.json", receipt)
    diversity = json.loads((out / ".state/diversity-screen.json").read_text())
    diversity["status"] = "pass"
    for control in diversity["controls"].values():
        control["status"] = "coherent_buildable_behavior_passed_and_semantic_clone_rejected"
    _write_json(out / ".state/diversity-screen.json", diversity)
    manifest = json.loads((out / ".state/manifest.json").read_text())
    manifest.update({"status": "creator_preflight_pass_pending_independent_audit", "docker_receipt": ".state/docker-sanity.json"})
    _write_json(out / ".state/manifest.json", manifest)
    candidates = json.loads((out / ".state/candidate-manifest.json").read_text())
    candidates["status"] = "creator_preflight_pass_pending_independent_audit"
    for row in candidates["rows"]:
        row["disposition"] = "candidate_pending_independent_audit"
        row["docker_receipt"] = ".state/docker-sanity.json"
    _write_json(out / ".state/candidate-manifest.json", candidates)
    _append_creator_cycle(out, receipt)
    return receipt


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-runtime", action="store_true")
    parser.add_argument("--docker-runtime", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.materialize:
        materialize(args.out, force=args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_runtime:
        verify_runtime(args.out, evidence_class="docker_sanity" if args.docker_runtime else "host_iteration")
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
