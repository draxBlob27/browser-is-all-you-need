"""Own, materialize, and verify offset-aware range-overlap remediation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
    load_task,
)
from w8_biayn.integrations.moonlight_offset_overlap_cases import CASES, Case

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/offset-aware-range-overlap")
LEGACY_OUT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/offset-aware-range-overlap")
REQUESTED_LEGACY_OUT = Path(".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/offset-aware-range-overlap")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_OFFSET_AWARE_RANGE_OVERLAP_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/offset-aware-range-overlap.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
PLANNER = "scripts/plan_offset_aware_range_overlap_remedies.py"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
NORMALIZER = "offset-aware-range-overlap-identifier-independent-structural-v3"
FAMILY_ROOT_MIN = 8
FAMILY_ROOT_MAX = 12
HARD_RULE_DIMENSIONS = (
    "public_api", "owned_state_or_algorithm", "mutation_selection_rules",
    "invalid_boundary_behavior", "reference_control_flow",
    "deterministic_oracle", "topic_specific_negative_fixture",
)
HARD_RULE_THRESHOLDS = {name: 0.80 for name in HARD_RULE_DIMENSIONS}
ADVERSARIAL_CONTROLS = (
    "domain-identifier-renamed", "constants-or-policy-only",
    "opposite-end-selection",
)
OBSOLETE_TASK_IDS = {"offset-support-bipartite-handoff"}


class VerificationError(RuntimeError):
    pass


def _fail(code: str, detail: str = "") -> None:
    raise VerificationError(f"{code}: {detail}" if detail else code)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big")); digest.update(relative)
        digest.update(len(data).to_bytes(8, "big")); digest.update(data)
    return "sha256:" + digest.hexdigest()


def _generator_revision() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__), Path(__file__).with_name("moonlight_offset_overlap_cases.py")):
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _family_hash(out: Path) -> str:
    payload="\n".join(f"{case.task_id} {_tree_hash(out/case.task_id)}" for case in CASES)
    return _sha(payload.encode())


def invalidate_stale_evidence(out: Path, reason: str) -> Path:
    """Archive and withdraw prior verification claims through the family owner."""
    state = out / ".state"
    if not state.is_dir():
        _fail("not_completed", f"state directory missing: {state}")
    source_names = ("audit.json", "family-screen.json", "docker-sanity.json")
    sources = [state / name for name in source_names if (state / name).is_file()]
    if not sources:
        _fail("not_completed", "no prior family evidence to invalidate")
    evidence_hash = _sha("\n".join(f"{path.name} {_sha(path.read_bytes())}" for path in sources).encode())
    archive = state / "invalidated" / evidence_hash.removeprefix("sha256:")[:16]
    archive.mkdir(parents=True, exist_ok=False)
    archived = {}
    for source in sources:
        target = archive / source.name
        shutil.copy2(source, target)
        archived[source.name] = _sha(target.read_bytes())
    manifest = {
        "schema_version": "offset-aware-range-overlap-invalidation-v1",
        "reason": reason,
        "invalidated_status": "local_family_verified",
        "replacement_status": "pending_execution",
        "owner_revision_at_invalidation": _generator_revision(),
        "archived_files": archived,
    }
    (archive / "invalidation.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    audit_path = state / "audit.json"
    audit = json.loads(audit_path.read_text()) if audit_path.is_file() else {}
    audit.update({
        "docker_status": "invalidated",
        "family_screen": "invalidated",
        "strongest_local_status": "pending_execution",
        "invalidated_evidence": str(archive.relative_to(out)),
        "invalidation_reason": reason,
    })
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    for path in sorted((state / "remedy").glob("*.json")):
        record = json.loads(path.read_text())
        record.update({
            "status": "planned",
            "local_status": "pending_execution",
            "family_screen": "invalidated",
            "oracle_evidence": {"status": "invalidated", "archive": str(archive.relative_to(out))},
            "invalidation_reason": reason,
        })
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return archive


def _cmake(case: Case) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.cpp" CACHE FILEPATH "Implementation")
add_executable(task_visible "${{TASK_SOURCE}}" task_visible_test.cpp)
add_executable(task_hidden "${{TASK_SOURCE}}" .meta/task_hidden_test.cpp)
add_executable(task_negative .meta/negative.cpp task_visible_test.cpp)
foreach(target task_visible task_hidden task_negative)
 target_include_directories(${{target}} PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME negative_fixture COMMAND task_negative)
set_tests_properties(negative_fixture PROPERTIES WILL_FAIL TRUE)
'''


def _files(case: Case) -> dict[str, str]:
    config = {"authors":["w8-biayn"],"blurb":case.title,"files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp",".meta/task_hidden_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
    provenance = {
        "curriculum_document": CURRICULUM, "family_spec": FAMILY_SPEC,
        "curriculum_task_id": case.task_id,
        "legacy_task_id": case.legacy_id, "disposition": case.disposition,
        "origin": "newly-authored in-repository clean-room remediation task",
        "status": "local task artifact; not admitted SFT data", "version": 3,
        "requested_family_type": "aider-text-grid-reshaping",
        "historical_legacy_family_type": "aider-dates-and-clocks",
        "benchmark_separation": "Independent fixed-offset domain API, reference, tests, and mechanism; no official benchmark asset reused.",
    }
    instructions = f"""# {case.title}

Implement the API declared in `{case.task_id}.h`. {case.instructions}

All ranges are half-open and local minute values are within `[0, 20160]`.
Normalize a local minute by subtracting its caller-supplied fixed UTC offset.
Supported offsets are whole minutes in `[-840, 840]`; touching endpoints have
zero overlap. Validate the complete input before returning any partial output.
Do not use host clocks, time-zone/DST databases, files, network, threads, or
randomness. Required mechanism: {case.profile}. A renamed generic overlap
helper or another family root's mechanism is not an implementation.
"""
    return task_named_files(Path(case.task_id), {
        ".docs/introduction.md": f"# {case.title}\n\nA clean-room local C++17 fixed-offset range task.\n",
        ".docs/instructions.md": instructions,
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True)+"\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True)+"\n",
        ".meta/tests.toml": "[visible]\ndescription=\"public mechanism and offset boundary\"\n[hidden]\ndescription=\"invalid, duplicate, empty, endpoint, tie, and adversarial rules\"\n[negative]\ndescription=\"topic-specific false substitute compiles and is rejected\"\n",
        "task.h": case.header, "task.cpp": case.starter,
        ".meta/example.h": case.header, ".meta/example.cpp": case.source,
        ".meta/negative.cpp": case.negative,
        "task_visible_test.cpp": case.visible,
        ".meta/task_hidden_test.cpp": case.hidden,
        "CMakeLists.txt": _cmake(case),
    })


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state/remedy"
    expected = {case.task_id for case in CASES}
    records = {path.stem for path in remedy.glob("*.json")}
    if records != expected:
        _fail("remedy_spec_incomplete", f"expected {sorted(expected)}, got {sorted(records)}")
    headings = ["Identity","Objective","Public API","Behavior table","Implementation invariant","Starter and reference","Tests","Files and metadata","Build/oracle","Family/contamination","Optional dataset handoff","Acceptance"]
    for case in CASES:
        record = json.loads((remedy/f"{case.task_id}.json").read_text())
        spec = remedy/f"{case.task_id}.md"; text = spec.read_text()
        positions = [text.find(f"## {heading}") for heading in headings]
        if any(value < 0 for value in positions) or positions != sorted(positions):
            _fail("remedy_spec_incomplete", case.task_id)
        if record.get("remedy_spec_hash") != _sha(text.encode()) or record.get("disposition") != case.disposition:
            _fail("remedy_disposition_conflict", case.task_id)
        if record.get("tree_hash_before") != _tree_hash(LEGACY_OUT/case.legacy_id):
            _fail("generator_output_drift", f"legacy changed: {case.legacy_id}")


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() in {LEGACY_OUT.resolve(), REQUESTED_LEGACY_OUT.resolve()}:
        _fail("legacy_root_immutable", str(out))
    if not (out/".state/remedy").is_dir() and out.resolve()!=DEFAULT_OUT.resolve():
        source=DEFAULT_OUT/".state/remedy"
        if not source.is_dir():
            _fail("remedy_spec_incomplete", "run the preimplementation planner")
        shutil.copytree(source,out/".state/remedy")
    _verify_remedies(out)
    expected = {case.task_id for case in CASES}
    foreign = {p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"} - expected if out.is_dir() else set()
    removable = foreign & OBSOLETE_TASK_IDS if force else set()
    for task_id in removable:
        root = out / task_id
        provenance_path = root / ".meta/provenance.json"
        provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
        if provenance.get("family_spec") != FAMILY_SPEC or provenance.get("legacy_task_id") != "offset-remote-support":
            _fail("generator_output_drift", f"refuse obsolete root without matching provenance: {task_id}")
        shutil.rmtree(root)
    foreign -= removable
    if foreign:
        _fail("generator_output_drift", f"foreign roots: {sorted(foreign)}")
    if force:
        for task_id in expected:
            root = out/task_id
            if root.exists(): shutil.rmtree(root)
        for stale in (out/".state").glob("*.json"):
            stale.unlink()
    roots=[]
    for case in CASES:
        root=out/case.task_id
        for relative, content in _files(case).items():
            _write(root/relative, content, force)
        roots.append(root)
    return tuple(roots)


CPP_KEEP = {
    "if","else","for","while","return","class","struct","public","private",
    "const","auto","bool","int","long","void","namespace","include","vector",
    "string","set","map","pair","tuple","sort","find_if","push_back","insert",
    "size","empty","clear","static_cast","true","false","break","continue",
    "function","algorithm","utility","functional","pragma","once",
}
SEMANTIC_KEEP = {
    "validate","invalid","duplicate","atomic","half","open","touching","offset",
    "normalize","normalized","intersection","intersect","union","merge","merged",
    "subtract","subtraction","clip","filter","weighted","weight","threshold","quorum",
    "event","sweep","slot","capacity","augmenting","reassignment","recurse","matching",
    "dynamic","program","predecessor","schedule","frontier","cover","coverage","gap",
    "ledger","count","score","duration","liquidity","lot","local","day","lexicographic",
    "stable","tie","reject","ignore","unknown","positive","negative","nonpositive",
    "overlap","containing","continuous","complete","incomplete","maximum","minimum",
}
EDGE_WORDS = {"first","last","lowest","highest","earliest","latest","minimum","maximum","min","max","front","back","begin","end"}


def _normalized(text: str) -> list[str]:
    text = re.sub(r"//.*|/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " string_literal ", text)
    tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\d+|==|!=|<=|>=|&&|\|\||[{}()\[\];,.<>+*/%=-]", text.lower())
    out=[]
    for token in tokens:
        if token.isdigit(): out.append("literal")
        elif token in EDGE_WORDS or token in {"<",">","<=",">="}: out.append("edge")
        elif token in {"==","!="}: out.append("equality")
        elif re.fullmatch(r"[a-z_][a-z_0-9]*",token):
            out.append(token if token in CPP_KEEP or token in SEMANTIC_KEEP else "identifier")
        else: out.append(token)
    return out


def _shingles(text: str, width: int = 5) -> set[str]:
    tokens=_normalized(text)
    if len(tokens)<width:return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i+width]) for i in range(len(tokens)-width+1)}


def _features(root: Path) -> dict[str,set[str]]:
    header=next(root.glob("*.h")).read_text(); source=(root/".meta/example.cpp").read_text()
    docs=(root/".docs/instructions.md").read_text(); visible=(root/"task_visible_test.cpp").read_text()
    hidden=(root/".meta/task_hidden_test.cpp").read_text(); negative=(root/".meta/negative.cpp").read_text()
    values={
        "public_api":_shingles(header,4),
        "owned_state_or_algorithm":_shingles(source,6),
        "mutation_selection_rules":_shingles(docs+source,7),
        "invalid_boundary_behavior":_shingles(docs+hidden,6),
        "reference_control_flow":_shingles(source,8),
        "deterministic_oracle":_shingles(visible+hidden,5),
        "topic_specific_negative_fixture":_shingles(negative,7),
    }
    if any(not value for value in values.values()): _fail("hard_rule_evidence_incomplete", root.name)
    return values


def _overlap(a:set[str],b:set[str])->float:
    return len(a&b)/max(1,len(a|b))


def _pair(left:Path,right:Path)->dict[str,object]:
    lf,rf=_features(left),_features(right)
    overlaps={name:round(_overlap(lf[name],rf[name]),6) for name in HARD_RULE_DIMENSIONS}
    failed=[name for name in HARD_RULE_DIMENSIONS if overlaps[name]>=HARD_RULE_THRESHOLDS[name]]
    decisions={name:{
        "overlap":overlaps[name],
        "threshold":HARD_RULE_THRESHOLDS[name],
        "materially_distinct":name not in failed,
        "left_fingerprint":_sha("\n".join(sorted(lf[name])).encode()),
        "right_fingerprint":_sha("\n".join(sorted(rf[name])).encode()),
    } for name in HARD_RULE_DIMENSIONS}
    return {"dimension_overlaps":overlaps,"dimension_decisions":decisions,"failed_dimensions":failed,"failure":"duplicate_family" if failed else None}


def _role_failure(root:Path, files:dict[str,list[str]])->str|None:
    all_paths=files.get("solution",[])+files.get("test",[])+files.get("example",[])
    if len(all_paths)!=len(set(all_paths)):return "unsafe_path"
    if any(Path(x).is_absolute() or ".." in Path(x).parts or not (root/x).is_file() for x in all_paths):return "unsafe_path"
    if any(x.startswith((".meta/",".docs/")) or x=="CMakeLists.txt" for x in files["solution"]):return "unsafe_path"
    if len(files["solution"])!=2 or [Path(x).suffix for x in files["solution"]]!=[Path(x).suffix for x in files["example"]]:return "target_reference_mismatch"
    return None


def _control_paths(root:Path)->list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix in {".h",".cpp",".md",".json",".toml",".txt"}]


def _make_control(root:Path, variant:str, parent:Path)->tuple[Path,dict[str,object]]:
    clone=parent/variant;shutil.copytree(root,clone); changed=[]
    replacements={
        "domain-identifier-renamed":(("BuildFreezeAudit","EmbargoLedger"),("Freeze","Embargo"),("freeze","embargo"),("classify","inspect"),("Release","Candidate"),("release","candidate"),("jurisdiction","region")),
        "constants-or-policy-only":(("840","720"),("900","780")),
        "opposite-end-selection":(("lowest precedence","highest precedence"),("w.precedence<best","w.precedence>best"),("r.jurisdiction_id!=3","r.jurisdiction_id!=9")),
    }[variant]
    for path in _control_paths(clone):
        before=path.read_text();after=before
        for old,new in replacements:after=after.replace(old,new)
        if after!=before:path.write_text(after);changed.append(path.relative_to(clone).as_posix())
    if variant=="domain-identifier-renamed":
        for suffix in (".h",".cpp"):
            old=clone/f"offset-build-freeze{suffix}"
            new=clone/f"offset-build-embargo{suffix}"
            old.rename(new);changed.append(f"{old.name} -> {new.name}")
    if variant=="opposite-end-selection":
        negative=clone/".meta/negative.cpp";before=negative.read_text()
        after=before.replace("w.precedence>best","w.precedence<best")
        if after==before:_fail("adversarial_control_invalid","opposite negative drift")
        negative.write_text(after);changed.append(".meta/negative.cpp")
    if len(changed)<3:_fail("adversarial_control_invalid",f"{variant}: {changed}")
    config=json.loads((clone/".meta/config.json").read_text())
    role_failure=_role_failure(clone,config["files"])
    if role_failure:_fail("adversarial_control_invalid",f"{variant}: {role_failure}")
    solution_header=clone/config["files"]["solution"][0]
    if solution_header.read_text()!=(clone/config["files"]["example"][0]).read_text():
        _fail("adversarial_control_invalid",f"{variant}: reference header mismatch")
    result=_pair(root,clone)
    return clone,{"base_tree_hash":_tree_hash(root),"changed_files":sorted(changed),"tree_hash":_tree_hash(clone),"role_mapping":"pass",**result}


def _bound_holdouts(repo_root:Path)->list[Path]:
    base=repo_root/".cache/upstreams/aider-polyglot/cpp/exercises"
    roots=sorted(path.parent.parent for path in base.glob("*/*/.meta/config.json"))
    if len(roots)!=26:_fail("benchmark_screen_not_completed",f"expected 26, got {len(roots)}")
    return roots


def _artifact_text(root:Path)->str:
    files=[p for p in root.rglob("*") if p.is_file() and p.suffix in {".h",".cpp",".md"}]
    return "\n".join(p.read_text(errors="ignore") for p in sorted(files))


def _update_records(out:Path,evidence:dict[str,dict[str,object]],status:str)->None:
    receipt=out/".state/docker-sanity.json"
    for case in CASES:
        path=out/".state/remedy"/f"{case.task_id}.json";record=json.loads(path.read_text())
        record.update({"status":status,"primary_core_objective":"achieved","local_status":"local_family_verified" if status=="verified" else "pending_execution","tree_hash_after":_tree_hash(out/case.task_id),"generator_revision_after":_generator_revision(),"prompt_boundary":"pass","family_screen":"pass","benchmark_screen":"pass","semantic_evidence":evidence[case.task_id],"changed_owner_paths":[CURRICULUM,FAMILY_SPEC,"docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",PLANNER,"src/w8_biayn/integrations/moonlight_offset_overlap_cases.py",str(Path(__file__).relative_to(Path.cwd())),"tests/test_moonlight_offset_aware_range_overlap_aider_tasks.py","examples/slime/moonlight_cpp_perf/prepare_offset_aware_range_overlap_aider_tasks.sh"]})
        if status=="verified":record["oracle_evidence"]={"receipt":str(receipt.relative_to(out)),"evidence_class":"docker_sanity","locked_oracle":False}
        path.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")


def verify_core(out:Path,*,repo_root:Path|None=None)->dict[str,dict[str,object]]:
    repo_root=repo_root or Path.cwd();_verify_remedies(out)
    emitted={p.name for p in out.iterdir() if p.is_dir() and p.name!=".state"};expected={c.task_id for c in CASES}
    if not FAMILY_ROOT_MIN<=len(emitted)<=FAMILY_ROOT_MAX:_fail("hard_rule_root_count",str(len(emitted)))
    if emitted!=expected:_fail("generator_output_drift",f"{sorted(emitted^expected)}")
    evidence={};features={}
    for case in CASES:
        root=out/case.task_id;config=json.loads((root/".meta/config.json").read_text())
        failure=_role_failure(root,config["files"])
        if failure:_fail(failure,case.task_id)
        task=load_task(root);response=build_assistant_response(task,load_example_files_from_config(root))
        if not response.startswith(f"{case.task_id}.h\n```") or ".meta/" in response or "CMakeLists" in response:_fail("whole_format_failed",case.task_id)
        if (root/".meta/example.h").read_text()!=next(root.glob("*.h")).read_text():_fail("target_reference_mismatch",case.task_id)
        if (root/".meta/example.cpp").read_text()==(root/".meta/negative.cpp").read_text():_fail("invariant_not_enforced",case.task_id)
        features[case.task_id]=_features(root)
        evidence[case.task_id]={"tree_hash":_tree_hash(root),"reference_hash":_sha((root/".meta/example.cpp").read_bytes()),"prompt_boundary":"pass","hard_rule_dimensions":{name:{"feature_count":len(features[case.task_id][name]),"fingerprint":_sha("\n".join(sorted(features[case.task_id][name])).encode())} for name in HARD_RULE_DIMENSIONS}}
    pairwise=[]
    for left,right in combinations(CASES,2):
        result=_pair(out/left.task_id,out/right.task_id);pairwise.append({"left":left.task_id,"right":right.task_id,**result})
        if result["failure"]:_fail("duplicate_family",f"{left.task_id} vs {right.task_id}: {result['failed_dimensions']}")
    with tempfile.TemporaryDirectory(prefix="offset-overlap-controls-") as tmp:
        controls={}
        base=out/"offset-build-freeze"
        for variant in ADVERSARIAL_CONTROLS:
            _,controls[variant]=_make_control(base,variant,Path(tmp))
        if any(item["failure"]!="duplicate_family" or set(item["failed_dimensions"])!=set(HARD_RULE_DIMENSIONS) for item in controls.values()):_fail("duplicate_family",f"controls: {controls}")
    holdouts=_bound_holdouts(repo_root);benchmark=[]
    for case in CASES:
        candidate=_shingles(_artifact_text(out/case.task_id),7)
        for holdout in holdouts:
            score=round(_overlap(candidate,_shingles(_artifact_text(holdout),7)),6);benchmark.append({"task_id":case.task_id,"holdout":holdout.name,"overlap":score})
            if case.task_id==holdout.name or score>=0.72:_fail("benchmark_content_overlap",f"{case.task_id} vs {holdout.name}: {score}")
    screen={"schema_version":"offset-aware-range-overlap-family-screen-v3","normalizer":NORMALIZER,"root_count":len(CASES),"root_count_bounds":{"minimum":FAMILY_ROOT_MIN,"maximum":FAMILY_ROOT_MAX},"benchmark_inventory":[h.name for h in holdouts],"benchmark_comparisons":benchmark,"adversarial_clone_results":controls,"hard_rule":{"dimensions":list(HARD_RULE_DIMENSIONS),"thresholds":HARD_RULE_THRESHOLDS,"comparison_count":len(pairwise),"expected_comparison_count":len(CASES)*(len(CASES)-1)//2,"decision_rule":"every pair must be below the clone threshold in every dimension; decisions are conjunctive","pairwise":pairwise,"result":"pass"}}
    state=out/".state";state.mkdir(parents=True,exist_ok=True);(state/"family-screen.json").write_text(json.dumps(screen,indent=2,sort_keys=True)+"\n")
    invalidations=sorted(str(path.relative_to(out)) for path in (out/".state/invalidated").glob("*/invalidation.json"))
    previous_audit=json.loads((state/"audit.json").read_text()) if (state/"audit.json").is_file() else {}
    audit={"schema_version":"offset-aware-range-overlap-audit-v3","selected_prompt":PROMPT_PATH,"user_inputs":{"FAMILY_NAME":"offset-aware-range-overlap","FAMILY_TYPE":"aider-text-grid-reshaping","hard_rule_count":"8-12"},"legacy_root_requested":str(REQUESTED_LEGACY_OUT),"legacy_root_audited":str(LEGACY_OUT),"legacy_tree_hash":_tree_hash(LEGACY_OUT),"legacy_finding":"one generic record/result/reference/test template across ten roots","invalidated_prior_evidence":invalidations,"v3_correction":"identifier-independent structural normalizer plus support interval-cover replacement","primary_core_objective":"achieved","prompt_boundary":"pass","family_screen":"pass","benchmark_screen":"pass","docker_status":"pending_execution","strongest_local_status":"pending_execution"}
    if "host_verification" in previous_audit:audit["host_verification"]=previous_audit["host_verification"]
    (state/"audit.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n");_update_records(out,evidence,"implemented")
    return evidence


def _run_build(root:Path,mode:str)->int:
    build_dir=root/f"build-{mode}";flags=[]
    if mode=="asan_ubsan":flags=["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
    subprocess.run(["cmake","-S",str(root),"-B",str(build_dir),"-G","Unix Makefiles",f"-DTASK_SOURCE={root/'.meta/example.cpp'}",*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    subprocess.run(["cmake","--build",str(build_dir),"--parallel","2"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    listed=subprocess.run(["ctest","--test-dir",str(build_dir),"-N"],check=True,capture_output=True,text=True).stdout
    count=len(re.findall(r"Test\s+#\d+:",listed));
    if count<=0:_fail("zero_tests",root.name)
    subprocess.run(["ctest","--test-dir",str(build_dir),"--output-on-failure"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    return count


def verify(out:Path)->dict[str,dict[str,int]]:
    missing=[tool for tool in ("cmake","c++") if not shutil.which(tool)]
    if missing:
        audit_path=out/".state/audit.json"
        audit=json.loads(audit_path.read_text()) if audit_path.is_file() else {}
        audit["host_verification"]={"status":"not_completed","missing":missing,"command":"--verify","next_action":"use the mandatory pinned network-disabled Docker sanity verifier"}
        audit_path.write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n")
        _fail("not_completed",f"verification requires {', '.join(missing)}")
    results={}
    for case in CASES:
        with tempfile.TemporaryDirectory(prefix="offset-overlap-host-") as tmp:
            root=Path(tmp)/case.task_id;shutil.copytree(out/case.task_id,root)
            normal=_run_build(root,"normal");san=_run_build(root,"asan_ubsan")
            if normal!=san:_fail("sanitizer_test_count_mismatch",case.task_id)
            results[case.task_id]={"normal":normal,"asan_ubsan":san}
    return results


def _docker_command(root:Path)->list[str]:
    script='''set -eu
cp -a /input /work
cd /work
python3 -c 'import hashlib,pathlib; r=pathlib.Path("/work"); d=hashlib.sha256(); [(d.update(len((q:=p.relative_to(r).as_posix().encode())).to_bytes(8,"big")),d.update(q),d.update(len((b:=p.read_bytes())).to_bytes(8,"big")),d.update(b)) for p in sorted(x for x in r.rglob("*") if x.is_file())]; print("TREE_HASH sha256:"+d.hexdigest())'
cmake -S . -B build-normal -G "Unix Makefiles" -DTASK_SOURCE=/work/.meta/example.cpp >/tmp/c1
cmake --build build-normal --parallel 2 >/tmp/b1
echo NORMAL_COUNT "$(ctest --test-dir build-normal -N | grep -c 'Test #')"
ctest --test-dir build-normal --output-on-failure
cmake -S . -B build-san -G "Unix Makefiles" -DTASK_SOURCE=/work/.meta/example.cpp "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined" >/tmp/c2
cmake --build build-san --parallel 2 >/tmp/b2
echo SAN_COUNT "$(ctest --test-dir build-san -N | grep -c 'Test #')"
ctest --test-dir build-san --output-on-failure
echo CXX_PATH "$(command -v c++)"
echo CXX_HASH "sha256:$(sha256sum "$(command -v c++)" | cut -d' ' -f1)"
echo CXX_VERSION "$(c++ --version | head -1)"
echo CMAKE_VERSION "$(cmake --version | head -1)"'''
    return ["docker","run","--rm","--network","none","-v",f"{root.resolve()}:/input:ro",SANITY_IMAGE,"bash","-lc",script]


def _docker_result(root:Path)->dict[str,object]:
    command=_docker_command(root);result=subprocess.run(command,check=True,capture_output=True,text=True)
    output=result.stdout+result.stderr
    tree=re.search(r"^TREE_HASH (sha256:[0-9a-f]{64})$",output,re.M)
    normal=re.search(r"^NORMAL_COUNT (\d+)$",output,re.M)
    sanitizer=re.search(r"^SAN_COUNT (\d+)$",output,re.M)
    cxx_path=re.search(r"^CXX_PATH (.+)$",output,re.M);cxx_hash=re.search(r"^CXX_HASH (sha256:[0-9a-f]{64})$",output,re.M)
    cxx_version=re.search(r"^CXX_VERSION (.+)$",output,re.M);cmake_version=re.search(r"^CMAKE_VERSION (.+)$",output,re.M)
    if not tree or not normal or not sanitizer or not cxx_path or not cxx_hash or not cxx_version or not cmake_version:_fail("test_discovery_failed",root.name)
    normal_count=int(normal.group(1));sanitizer_count=int(sanitizer.group(1));live=_tree_hash(root)
    if tree.group(1)!=live:_fail("grader_mount_hash_mismatch",root.name)
    if normal_count<=0:_fail("zero_tests",root.name)
    if normal_count!=sanitizer_count:_fail("sanitizer_test_count_mismatch",root.name)
    if output.count("negative_fixture")<2:_fail("negative_fixture_not_rejected",root.name)
    return {"normal":normal_count,"asan_ubsan":sanitizer_count,"tree_hash":live,"mounted_tree_hash":tree.group(1),"reference_hash":_sha((root/".meta/example.cpp").read_bytes()),"negative_fixture":"executed_and_rejected_in_both_modes","compiler_path":cxx_path.group(1),"compiler_hash":cxx_hash.group(1),"compiler_version":cxx_version.group(1),"cmake_version":cmake_version.group(1),"command_hash":_sha("\0".join(command).encode()),"log_hash":_sha(output.encode())}


def docker_sanity(out:Path)->dict[str,object]:
    evidence=verify_core(out);records={}
    for case in CASES:
        records[case.task_id]=_docker_result(out/case.task_id)
    control_records={}
    with tempfile.TemporaryDirectory(prefix="offset-overlap-docker-controls-") as tmp:
        for variant in ADVERSARIAL_CONTROLS:
            clone,mutation=_make_control(out/"offset-build-freeze",variant,Path(tmp));control_records[variant]={**_docker_result(clone),"changed_files":mutation["changed_files"],"semantic_rejection":mutation["failure"]}
    receipt={"schema_version":"offset-aware-range-overlap-docker-sanity-v3","status":"pass","evidence_class":"docker_sanity","locked_oracle":False,"image":SANITY_IMAGE,"network":"none","generator_revision":_generator_revision(),"family_tree_hash":_family_hash(out),"family_screen_hash":_sha((out/".state/family-screen.json").read_bytes()),"tasks":records,"hard_rule_controls":control_records,"commands":{"root":"docker run --rm --network none ... clean normal and fresh ASan/UBSan","generator":"--force --verify-core --docker-sanity"}}
    (out/".state/docker-sanity.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    audit=json.loads((out/".state/audit.json").read_text());audit["docker_status"]="pass";audit["strongest_local_status"]="local_family_verified";(out/".state/audit.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n");_update_records(out,evidence,"verified")
    return receipt


def main(argv:Sequence[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",type=Path,default=DEFAULT_OUT);parser.add_argument("--force",action="store_true");parser.add_argument("--verify-core",action="store_true");parser.add_argument("--verify",action="store_true");parser.add_argument("--docker-sanity",action="store_true");parser.add_argument("--invalidate-stale-evidence",metavar="REASON");args=parser.parse_args(argv)
    if args.invalidate_stale_evidence:
        archive=invalidate_stale_evidence(args.out,args.invalidate_stale_evidence)
        print(f"Invalidated prior evidence under {archive}")
        return 0
    roots=build(args.out,args.force)
    if args.verify_core:verify_core(args.out)
    if args.verify:verify(args.out)
    if args.docker_sanity:docker_sanity(args.out)
    print(f"Wrote {len(roots)} offset-aware range-overlap tasks under {args.out}");return 0


if __name__=="__main__":raise SystemExit(main())
