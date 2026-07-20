"""Artifact-derived material-diversity evaluator for cross-midnight tasks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


HARD_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)

DIMENSION_ROLES = {
    "public_api": ("header",),
    "owned_state_or_algorithm": ("header", "reference"),
    "mutation_selection_rules": ("instructions", "reference"),
    "invalid_boundary_behavior": ("instructions", "hidden"),
    "reference_control_flow": ("reference",),
    "deterministic_oracle": ("visible", "hidden"),
    "topic_negative_fixture": ("reference", "negative", "hidden"),
}

MAX_NORMALIZED_SIMILARITY = {
    "public_api": 0.985,
    "owned_state_or_algorithm": 0.80,
    "mutation_selection_rules": 0.84,
    "invalid_boundary_behavior": 0.88,
    "reference_control_flow": 0.78,
    "deterministic_oracle": 0.80,
    "topic_negative_fixture": 0.80,
}


@dataclass(frozen=True)
class Probe:
    role: str
    pattern: str
    fact: str


def _p(role: str, pattern: str, fact: str) -> Probe:
    return Probe(role, pattern, fact)


# These profiles are not declarations trusted from the generator case table.
# Every label is recognized only when multiple concrete facts are present in the
# emitted header/docs/reference/tests. The evaluator tries every profile against
# every root and requires exactly one match per dimension.
MATERIAL_PROFILES: Mapping[str, Mapping[str, Sequence[Probe]]] = {
    "tariff-policy-ledger": {
        "public_api": (_p("header", r"class\s+\w+\s*\{public:explicit\s+\w+\(std::vector<", "immutable policy object owns a record collection"), _p("header", r"std::size_t\s+\w+\(\)const", "separate policy-cardinality query"), _p("header", r"\w+\s+\w+\(\w+\)const", "single-record pricing query")),
        "owned_state_or_algorithm": (_p("header", r"std::vector<\w+>\s+\w+_;", "owned tariff collection"), _p("reference", r"for\(int\s+\w+:\{-1440,0,1440\}\)", "three-shift boundary sweep"), _p("reference", r"\w+\+=std::max\(0,std::min", "intersection accumulation")),
        "mutation_selection_rules": (_p("instructions", r"ascending band ID", "output sorted by band identity"), _p("reference", r"std::sort\(\w+\.charges.*band_id<", "explicit ledger ordering"), _p("reference", r"total_cents\+=", "monetary accumulation")),
        "invalid_boundary_behavior": (_p("instructions", r"no two bands may overlap", "overlapping policy bands invalidate construction"), _p("hidden", r"band_count\(\)!=0\|\|.*\.valid", "invalid policy remains unusable"), _p("hidden", r"price\(\{-1,2\}\)\.valid", "invalid visit endpoint rejected")),
        "reference_control_flow": (_p("reference", r"for\(std::size_t\s+\w+=0;.*for\(std::size_t\s+\w+=0;", "pairwise policy-overlap validation"), _p("reference", r"for\(auto\s+\w+:\w+_\).*for\(int\s+\w+:\{-1440,0,1440\}\)", "nested band/shift pricing sweep"), _p("reference", r"int\s+cents=charged\*", "rate multiplication")),
        "deterministic_oracle": (_p("visible", r"band_count\(\)==2", "policy state assertion"), _p("visible", r"total_cents==240", "exact monetary oracle"), _p("visible", r"std::vector<BandCharge>\{\{1,60,180\},\{2,60,60\}\}", "complete ordered ledger oracle")),
        "topic_negative_fixture": (_p("reference", r"int\s+cents=charged\*", "correct per-minute multiplication"), _p("negative", r"int\s+cents=b\.cents_per_minute", "single-charge false substitute"), _p("hidden", r"total_cents!=60", "executed discriminator for multiplication")),
    },
    "coverage-union-complement": {
        "public_api": (_p("header", r"struct\s+\w+\{int\s+\w+,\w+;\};\s*struct\s+\w+\{int\s+id,", "window plus identified interval inputs"), _p("header", r"struct\s+GapReport\{bool\s+valid=true;std::vector<Gap>", "gap-only report schema"), _p("header", r"GapReport\s+\w+\(\w+,const\s+std::vector<", "stateless window/collection operation")),
        "owned_state_or_algorithm": (_p("reference", r"std::vector<std::pair<int,int>>\s+spans", "temporary interval collection"), _p("reference", r"std::sort\(spans\.begin\(\),spans\.end\(\)\)", "chronological sort"), _p("reference", r"merged\.back\(\)\.second=std::max", "maximal interval union")),
        "mutation_selection_rules": (_p("instructions", r"Union overlapping or touching patrols", "touching intervals merge"), _p("reference", r"s\.first>merged\.back\(\)\.second", "new component selection"), _p("reference", r"if\(s\.first>cursor\).*gaps\.push_back", "complement gap selection")),
        "invalid_boundary_behavior": (_p("instructions", r"outside patrol is invalid", "containment is mandatory"), _p("hidden", r"uncovered_watch\(\{0,0\},\{\}\)\.valid", "empty watch rejected"), _p("hidden", r"\{\{1,1100,0\}\}\)\.valid", "outside patrol rejected")),
        "reference_control_flow": (_p("reference", r"std::sort\(spans", "sort phase"), _p("reference", r"for\(auto\s+s:spans\).*merged", "union phase"), _p("reference", r"for\(auto\s+s:merged\).*cursor", "complement phase")),
        "deterministic_oracle": (_p("visible", r"std::vector<Gap>\{\{1320,1380\},\{120,240\}\}", "ordered cross-midnight gaps"), _p("hidden", r"nested\.gaps!=std::vector<Gap>\{\{60,120\}\}", "nested-interval union oracle"), _p("hidden", r"!r\.gaps\.empty\(\)", "complete coverage oracle")),
        "topic_negative_fixture": (_p("reference", r"merged\.back\(\)\.second=std::max", "union endpoint retains maximum"), _p("negative", r"merged\.back\(\)\.second=s\.second", "nested interval shrinks union"), _p("hidden", r"nested\.gaps!=", "nested-interval executed discriminator")),
    },
    "mutable-resource-calendar": {
        "public_api": (_p("header", r"class\s+DockCalendar", "mutable calendar class"), _p("header", r"ReserveResult\s+reserve\(Booking\)", "mutating reservation operation"), _p("header", r"int\s+next_free\(int,int,int\)const", "independent gap query"), _p("header", r"std::vector<int>\s+booking_ids\(int\)const", "observable per-resource ordering")),
        "owned_state_or_algorithm": (_p("header", r"int\s+docks_;std::vector<Booking>\s+bookings_;", "owned resource count and bookings"), _p("reference", r"bookings_\.push_back", "accepted reservation mutation"), _p("reference", r"candidate=std::max\(candidate,b\.end_minute\)", "gap-search cursor")),
        "mutation_selection_rules": (_p("instructions", r"rejects same-dock overlap without mutation", "atomic conflict rejection"), _p("reference", r"if\(x\.dock!=b\.dock\)continue", "resource-local conflict selection"), _p("reference", r"return\{false,x\.id\}", "first conflict identity")),
        "invalid_boundary_behavior": (_p("instructions", r"touching is allowed", "half-open adjacency accepted"), _p("hidden", r"booking_ids\(0\)!=std::vector<int>\{1\}", "failed reservation leaves state unchanged"), _p("hidden", r"reserve\(\{3,0,200,220\}\)", "touching reservation accepted")),
        "reference_control_flow": (_p("reference", r"for\(auto\s+x:bookings_\)if\(x\.id==", "duplicate scan"), _p("reference", r"for\(auto\s+x:bookings_\)\{if\(x\.dock", "resource conflict scan"), _p("reference", r"for\(auto\s+b:bookings_\)if\(b\.dock==dock&&b\.end_minute>candidate\)", "ordered next-gap scan")),
        "deterministic_oracle": (_p("visible", r"next_free\(0,1400,30\)==1500", "next-gap result"), _p("hidden", r"x\.conflict_id!=1", "conflict identity"), _p("hidden", r"booking_ids\(0\)!=std::vector<int>\{1\}", "complete state after rejection")),
        "topic_negative_fixture": (_p("reference", r"if\(x\.dock!=b\.dock\)continue", "per-resource filtering"), _p("negative", r"if\(false\)continue", "global-conflict false substitute"), _p("visible", r"reserve\(\{8,1,1400,1450\}\)", "cross-resource executed discriminator")),
    },
    "point-membership-policy": {
        "public_api": (_p("header", r"class\s+SilencePolicy", "immutable point-policy class"), _p("header", r"bool\s+valid_policy\(\)const", "constructor validity query"), _p("header", r"SilenceAudit\s+audit\(const\s+std::vector<Transmission>&\)const", "point-collection audit")),
        "owned_state_or_algorithm": (_p("header", r"std::vector<QuietWindow>\s+windows_;", "owned policy windows"), _p("reference", r"bool\s+contains\(QuietWindow\s+\w+,int\s+\w+\)", "direct cyclic point predicate"), _p("reference", r"for\(auto\s+\w+:windows_\)if\(contains", "point/window membership scan")),
        "mutation_selection_rules": (_p("instructions", r"smallest matching window ID", "minimum matching policy selection"), _p("reference", r"selected<0\|\|w\.id<selected", "minimum-ID tie reduction"), _p("reference", r"violations\.push_back\(\{t\.id,selected\}\)", "one result per violating point")),
        "invalid_boundary_behavior": (_p("instructions", r"point at a\s+window start violates, while a point at its end does not", "asymmetric point boundary"), _p("hidden", r"\{\{7,100\},\{8,199\},\{9,200\}\}", "start/interior/end boundary oracle"), _p("hidden", r"invalid\.valid_policy\(\)\|\|invalid\.audit", "invalid policy remains unusable")),
        "reference_control_flow": (_p("reference", r"for\(auto\s+t:transmissions\)\{int\s+selected=-1", "outer stable input scan"), _p("reference", r"for\(auto\s+w:windows_\)if\(contains", "inner membership scan"), _p("reference", r"if\(selected>0\).*push_back", "conditional single emission")),
        "deterministic_oracle": (_p("visible", r"std::vector<Violation>\{\{1,3\},\{3,9\}\}", "stable input-order violation list"), _p("hidden", r"a\.violations\.size\(\)!=2", "half-open boundary count"), _p("visible", r"valid_policy\(\)&&a\.valid", "policy and audit validity")),
        "topic_negative_fixture": (_p("reference", r"x<w\.end_minute", "half-open endpoint"), _p("negative", r"x<=w\.end_minute", "closed-end false substitute"), _p("hidden", r"\{9,200\}", "end-point executed discriminator")),
    },
    "heap-capacity-partition": {
        "public_api": (_p("header", r"BakeSchedule\s+schedule_batches\(int,const\s+std::vector<Batch>&\)", "capacity plus batch collection operation"), _p("header", r"struct\s+OvenAssignment\{int\s+batch_id,oven,start_minute,end_minute", "resource/time assignment output"), _p("header", r"struct\s+BakeSchedule\{bool\s+valid=true;std::vector<OvenAssignment>", "ordered allocation schedule")),
        "owned_state_or_algorithm": (_p("reference", r"std::priority_queue<int,std::vector<int>,std::greater<int>>\s+free", "minimum free-resource heap"), _p("reference", r"std::priority_queue<Busy,std::vector<Busy>,std::greater<Busy>>\s+busy", "minimum finish-time heap"), _p("reference", r"busy\.push\(\{end,oven\}\)", "resource release event state")),
        "mutation_selection_rules": (_p("instructions", r"assign the smallest free oven", "minimum free resource"), _p("reference", r"int\s+oven=free\.top\(\);free\.pop\(\)", "heap-selected assignment"), _p("reference", r"while\(!busy\.empty\(\)&&busy\.top\(\)\.first<=release\)", "release-before-selection")),
        "invalid_boundary_behavior": (_p("instructions", r"finish is at or before the batch release", "finish equality releases capacity"), _p("hidden", r"\{1,100,50\},\{2,150,20\}", "touching endpoint oracle"), _p("hidden", r"schedule_batches\(1,\{\{1,100,60\},\{2,120,10\}\}\)\.valid", "capacity exhaustion invalidates")),
        "reference_control_flow": (_p("reference", r"for\(int\s+i=0;i<oven_count;\+\+i\)free\.push", "initialize resource heap"), _p("reference", r"for\(auto\s+b:batches\).*while\(!busy\.empty", "stream with release loop"), _p("reference", r"if\(free\.empty\(\)\)return", "capacity gate")),
        "deterministic_oracle": (_p("visible", r"std::vector<OvenAssignment>\{\{1,0,1380,1470\},\{2,1,1400,1430\},\{3,0,1470,1490\}\}", "complete heap allocation trace"), _p("hidden", r"assignments\[1\]\.oven!=0", "resource reuse oracle"), _p("hidden", r"schedule_batches\(0,\{\}\)\.valid", "invalid capacity oracle")),
        "topic_negative_fixture": (_p("reference", r"busy\.top\(\)\.first<=release", "touching release"), _p("negative", r"busy\.top\(\)\.first<release", "strict release false substitute"), _p("hidden", r"\{2,150,20\}", "touching batch executed discriminator")),
    },
    "streaming-continuity-chain": {
        "public_api": (_p("header", r"class\s+HandoffChain", "streaming chain class"), _p("header", r"bool\s+append\(Shift\)", "atomic incremental append"), _p("header", r"HandoffAudit\s+audit\(\)const", "snapshot continuity query"), _p("header", r"bool\s+wrapped_=false", "owned wrap state")),
        "owned_state_or_algorithm": (_p("header", r"int\s+previous_start_=-1;bool\s+wrapped_=false;std::vector<Shift>\s+shifts_;", "owned streaming sequence state"), _p("reference", r"shifts_\.push_back\(s\)", "accepted append mutation"), _p("reference", r"for\(std::size_t\s+i=1;i<v\.size\(\);\+\+i\)", "adjacent-pair traversal")),
        "mutation_selection_rules": (_p("instructions", r"append.*rejects invalid input.*without mutation", "atomic streaming rejection"), _p("reference", r"if\(previous_start_>=0&&s\.start_minute<previous_start_\)", "single wrap transition"), _p("reference", r"first_unsafe_id=v\[i-1\]\.id", "first unsafe predecessor selection")),
        "invalid_boundary_behavior": (_p("instructions", r"equality is safe", "inclusive overlap threshold"), _p("hidden", r"c\.audit\(\)\.handoffs!=before", "rejected append preserves full state"), _p("hidden", r"HandoffChain\s+invalid\(-1\)", "negative threshold invalidates constructor")),
        "reference_control_flow": (_p("reference", r"bool\s+HandoffChain::append", "mutation phase"), _p("reference", r"HandoffAudit\s+HandoffChain::audit\(\)const", "separate query phase"), _p("reference", r"overlap=std::max.*gap=std::max", "adjacent continuity calculation")),
        "deterministic_oracle": (_p("visible", r"c\.append\(\{1,1320,30\}\)&&c\.append\(\{2,0,120\}\)", "streamed wrap trace"), _p("visible", r"std::vector<Handoff>\{\{1,2,30,0\}\}", "complete adjacency report"), _p("hidden", r"a\.first_unsafe_id!=1\|\|a\.handoffs\[0\]\.gap_minutes!=30", "unsafe identity and gap oracle")),
        "topic_negative_fixture": (_p("reference", r"overlap<required_", "equality accepted"), _p("negative", r"overlap<=required_", "equality-rejecting false substitute"), _p("visible", r"HandoffChain\s+c\(30\)", "threshold equality executed discriminator")),
    },
    "causal-minute-bitmap": {
        "public_api": (_p("header", r"class\s+NoiseMeter", "stateful causal meter"), _p("header", r"bool\s+record\(NoiseOperation\)", "incremental operation admission"), _p("header", r"NoiseAudit\s+report\(\)const;void\s+reset\(\)", "snapshot and reset operations"), _p("header", r"std::array<bool,1440>", "fixed minute-state representation")),
        "owned_state_or_algorithm": (_p("header", r"std::array<bool,1440>\s+protected_", "protected-minute bitmap"), _p("header", r"std::array<bool,1440>\s+charged_", "causal charged-minute bitmap"), _p("reference", r"charged_\.fill\(false\)", "explicit bitmap reset")),
        "mutation_selection_rules": (_p("instructions", r"not already charged by an earlier operation", "causal marginal selection"), _p("reference", r"protected_\[x\]&&!charged_\[x\]", "new protected-minute gate"), _p("reference", r"breach_operation_id=op\.id", "first causal breach identity")),
        "invalid_boundary_behavior": (_p("instructions", r"Invalid or duplicate.*do not mutate state", "atomic record rejection"), _p("hidden", r"m\.record\(\{2,90,100\}\)", "duplicate record rejected"), _p("hidden", r"m\.report\(\)\.charged_minutes!=90", "rejection preserves charged state")),
        "reference_control_flow": (_p("reference", r"template<class\s+F>\s+void\s+each", "cyclic per-minute traversal"), _p("reference", r"bool\s+NoiseMeter::record", "incremental update phase"), _p("reference", r"void\s+NoiseMeter::reset", "independent reset phase")),
        "deterministic_oracle": (_p("visible", r"m\.record\(\{1,1380,60\}\)&&m\.record\(\{2,30,90\}\)", "two-step causal trace"), _p("visible", r"marginal_minutes==std::vector<int>\{120,30\}", "per-operation marginal oracle"), _p("hidden", r"m\.reset\(\).*charged_minutes!=0", "reset-state oracle")),
        "topic_negative_fixture": (_p("reference", r"protected_\[x\]&&!charged_\[x\]", "unique-minute gate"), _p("negative", r"if\(protected_\[x\]\)", "double-charge false substitute"), _p("hidden", r"marginal_minutes\[1\]!=30", "overlap executed discriminator")),
    },
    "ordered-route-feasibility": {
        "public_api": (_p("header", r"DispatchChoice\s+select_dispatch\(const\s+std::vector<Curfew>&,const\s+std::vector<RouteCandidate>&\)", "two-collection feasibility selection"), _p("header", r"struct\s+RouteCandidate\{int\s+id,start_minute,duration;\}", "duration-bearing candidate"), _p("header", r"struct\s+DispatchChoice\{bool\s+valid=true,found=false;int\s+route_id=-1,start_minute=-1;\}", "optional selected identity result")),
        "owned_state_or_algorithm": (_p("reference", r"std::vector<std::pair<int,int>>\s+blocked", "shifted forbidden-interval set"), _p("reference", r"std::vector<RouteCandidate>\s+ordered=routes", "candidate working order"), _p("reference", r"bool\s+legal=true;for\(auto\s+c:blocked\)", "full-route feasibility scan")),
        "mutation_selection_rules": (_p("instructions", r"smallest unwrapped start, then smallest ID", "lexicographic feasible selection"), _p("reference", r"a\.start_minute<b\.start_minute\|\|\(a\.start_minute==b\.start_minute&&a\.id<b\.id\)", "candidate ordering comparator"), _p("reference", r"if\(legal\)return\{true,true,r\.id", "first feasible candidate")),
        "invalid_boundary_behavior": (_p("instructions", r"touching is legal", "route/curfew adjacency accepted"), _p("hidden", r"\{\{1,50,50\},\{2,200,10\}\}", "both curfew boundary touches"), _p("hidden", r"select_dispatch\(\{\{0,0\}\},\{\}\)\.valid", "empty curfew rejected")),
        "reference_control_flow": (_p("reference", r"for\(auto\s+c:curfews\).*for\(int\s+shift", "curfew expansion phase"), _p("reference", r"std::sort\(ordered\.begin", "candidate order phase"), _p("reference", r"for\(auto\s+r:ordered\).*for\(auto\s+c:blocked\)", "nested feasibility search")),
        "deterministic_oracle": (_p("visible", r"route_id==2&&c\.start_minute==60", "start/ID tie oracle"), _p("hidden", r"!c\.found\|\|c\.route_id!=1", "touching boundary selection"), _p("hidden", r"!n\.valid\|\|n\.found", "valid no-solution result")),
        "topic_negative_fixture": (_p("reference", r"int\s+re=r\.start_minute\+r\.duration", "full route endpoint"), _p("negative", r"int\s+re=r\.start_minute;", "point-only false substitute"), _p("visible", r"\{9,1370,20\}", "duration-overlap executed discriminator")),
    },
}


def _sha(data: str) -> str:
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


def _tokens(content: str) -> tuple[str, ...]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", content)
    keywords = {
        "if", "else", "for", "while", "return", "class", "struct", "const", "auto",
        "bool", "int", "long", "void", "true", "false", "public", "private",
        "namespace", "std", "vector", "array", "set", "sort", "priority_queue",
        "greater", "max", "min", "break", "continue", "template", "using",
    }
    return tuple(token if token in keywords or not token[0].isalpha() else "ID" for token in raw)


def _ngrams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    return {tokens[index : index + width] for index in range(max(0, len(tokens) - width + 1))}


def _similarity(left: str, right: str) -> float:
    a, b = _ngrams(_tokens(left)), _ngrams(_tokens(right))
    return len(a & b) / max(1, min(len(a), len(b)))


def read_artifacts(root: Path) -> dict[str, str]:
    config = __import__("json").loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    return {
        "header": (root / config["files"]["solution"][0]).read_text(encoding="utf-8"),
        "instructions": (root / ".docs/instructions.md").read_text(encoding="utf-8"),
        "reference": (root / ".meta/example.cpp").read_text(encoding="utf-8"),
        "visible": (root / "task_visible_test.cpp").read_text(encoding="utf-8"),
        "hidden": (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8"),
        "negative": (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8"),
    }


def analyze_root(root: Path) -> dict[str, object]:
    artifacts = read_artifacts(root)
    dimensions: dict[str, object] = {}
    for dimension in HARD_DIMENSIONS:
        matches = []
        for profile_name, profile in MATERIAL_PROFILES.items():
            probes = profile[dimension]
            matched = [
                {
                    "role": probe.role,
                    "fact": probe.fact,
                    "pattern_hash": _sha(probe.pattern),
                    "matched": bool(re.search(probe.pattern, artifacts[probe.role], flags=re.S)),
                }
                for probe in probes
            ]
            if all(row["matched"] for row in matched):
                matches.append((profile_name, matched))
        valid = len(matches) == 1
        dimensions[dimension] = {
            "valid": valid,
            "profile": matches[0][0] if valid else None,
            "matching_profiles": [name for name, _ in matches],
            "facts": matches[0][1] if valid else [],
            "artifact_roles": list(DIMENSION_ROLES[dimension]),
            "normalized_fingerprint": _sha("\n".join(artifacts[role] for role in DIMENSION_ROLES[dimension])),
        }
    return {"root": root.name, "dimensions": dimensions}


def compare_roots(left_root: Path, right_root: Path) -> dict[str, object]:
    left, right = analyze_root(left_root), analyze_root(right_root)
    left_artifacts, right_artifacts = read_artifacts(left_root), read_artifacts(right_root)
    decisions: dict[str, object] = {}
    for dimension in HARD_DIMENSIONS:
        le = left["dimensions"][dimension]
        revidence = right["dimensions"][dimension]
        roles = DIMENSION_ROLES[dimension]
        similarity = _similarity(
            "\n".join(left_artifacts[role] for role in roles),
            "\n".join(right_artifacts[role] for role in roles),
        )
        profile_distinct = le["profile"] != revidence["profile"]
        similarity_pass = similarity < MAX_NORMALIZED_SIMILARITY[dimension]
        passed = bool(le["valid"] and revidence["valid"] and profile_distinct and similarity_pass)
        decisions[dimension] = {
            "pass": passed,
            "left_profile": le["profile"],
            "right_profile": revidence["profile"],
            "left_evidence_valid": le["valid"],
            "right_evidence_valid": revidence["valid"],
            "material_profile_distinct": profile_distinct,
            "normalized_similarity": similarity,
            "maximum_similarity": MAX_NORMALIZED_SIMILARITY[dimension],
            "similarity_pass": similarity_pass,
            "left_fact_count": len(le["facts"]),
            "right_fact_count": len(revidence["facts"]),
        }
    return {
        "left": left_root.name,
        "right": right_root.name,
        "dimensions": decisions,
        "pass": all(row["pass"] for row in decisions.values()),
    }
