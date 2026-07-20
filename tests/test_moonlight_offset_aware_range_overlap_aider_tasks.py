from __future__ import annotations

import json
import re
import shutil
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_offset_aware_range_overlap_aider_tasks as tasks
from w8_biayn.integrations.moonlight_offset_overlap_cases import CASES


INDEPENDENT_CPP_WORDS = set("""if else for while return class struct public private const auto bool int long void namespace include vector string set map pair tuple sort find_if push_back insert size empty clear static_cast true false break continue function algorithm utility functional pragma once optional explicit nullopt move""".split())


def _independent_tokens(text: str) -> list[str]:
    text=re.sub(r"//.*|/\*.*?\*/"," ",text,flags=re.S)
    text=re.sub(r'"(?:\\.|[^"\\])*"'," string_literal ",text)
    raw=re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\d+|==|!=|<=|>=|&&|\|\||[{}()\[\];,.<>+*/%=&!?:-]",text.lower())
    out=[]
    for token in raw:
        if token.isdigit():out.append("literal")
        elif token in {"<",">","<=",">="}:out.append("edge")
        elif token in {"==","!="}:out.append("equality")
        elif re.fullmatch(r"[a-z_][a-z_0-9]*",token):out.append(token if token in INDEPENDENT_CPP_WORDS else "identifier")
        else:out.append(token)
    return out


def _independent_shingles(text: str,width: int)->set[str]:
    tokens=_independent_tokens(text)
    if len(tokens)<width:return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[index:index+width]) for index in range(len(tokens)-width+1)}


def _independent_features(root: Path)->dict[str,set[str]]:
    header=next(root.glob("*.h")).read_text();source=(root/".meta/example.cpp").read_text()
    docs=(root/".docs/instructions.md").read_text();visible=(root/"task_visible_test.cpp").read_text()
    hidden=(root/".meta/task_hidden_test.cpp").read_text();negative=(root/".meta/negative.cpp").read_text()
    return {
        "public_api":_independent_shingles(header,4),
        "owned_state_or_algorithm":_independent_shingles(source,6),
        "mutation_selection_rules":_independent_shingles(docs+source,7),
        "invalid_boundary_behavior":_independent_shingles(docs+hidden,6),
        "reference_control_flow":_independent_shingles(source,8),
        "deterministic_oracle":_independent_shingles(visible+hidden,5),
        "topic_specific_negative_fixture":_independent_shingles(negative,7),
    }


def _independent_overlap(left:set[str],right:set[str])->float:
    return len(left&right)/max(1,len(left|right))


def test_materializes_ten_distinct_reverify_roots(tmp_path: Path) -> None:
    roots=tasks.build(tmp_path)
    assert len(roots)==len(CASES)==10
    assert 8<=len(roots)<=12
    assert {root.name for root in roots}=={case.task_id for case in CASES}
    assert {case.legacy_id for case in CASES}=={p.name for p in tasks.LEGACY_OUT.iterdir() if p.is_dir()}
    assert sum(case.task_id==case.legacy_id for case in CASES)==1
    assert len({case.profile for case in CASES})==10
    for case in CASES:
        root=tmp_path/case.task_id
        files=json.loads((root/".meta/config.json").read_text())["files"]
        assert files=={"solution":[f"{case.task_id}.h",f"{case.task_id}.cpp"],"test":["task_visible_test.cpp",".meta/task_hidden_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}
        assert (root/".meta/negative.cpp").read_text()!=(root/".meta/example.cpp").read_text()
        assert "WILL_FAIL TRUE" in (root/"CMakeLists.txt").read_text()


def test_legacy_roots_are_immutable() -> None:
    with pytest.raises(tasks.VerificationError,match="legacy_root_immutable"):
        tasks.build(tasks.LEGACY_OUT,force=True)
    with pytest.raises(tasks.VerificationError,match="legacy_root_immutable"):
        tasks.build(tasks.REQUESTED_LEGACY_OUT,force=True)


def test_prompt_roles_and_complete_hard_rule(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    evidence=tasks.verify_core(tmp_path)
    assert set(evidence)=={case.task_id for case in CASES}
    screen=json.loads((tmp_path/".state/family-screen.json").read_text())
    hard=screen["hard_rule"]
    assert screen["schema_version"]=="offset-aware-range-overlap-family-screen-v3"
    assert screen["normalizer"]==tasks.NORMALIZER
    assert screen["root_count"]==10
    assert hard["dimensions"]==list(tasks.HARD_RULE_DIMENSIONS)
    assert hard["comparison_count"]==hard["expected_comparison_count"]==45
    assert len(hard["pairwise"])==45
    expected_pairs={tuple(sorted((left.task_id,right.task_id))) for left,right in combinations(CASES,2)}
    assert {tuple(sorted((item["left"],item["right"]))) for item in hard["pairwise"]}==expected_pairs
    for decision in hard["pairwise"]:
        assert decision["failure"] is None
        assert decision["failed_dimensions"]==[]
        assert set(decision["dimension_overlaps"])==set(tasks.HARD_RULE_DIMENSIONS)
        assert set(decision["dimension_decisions"])==set(tasks.HARD_RULE_DIMENSIONS)
        for dimension,overlap in decision["dimension_overlaps"].items():
            assert overlap<tasks.HARD_RULE_THRESHOLDS[dimension]
            item=decision["dimension_decisions"][dimension]
            assert item["overlap"]==overlap and item["materially_distinct"] is True
            assert item["left_fingerprint"]!=item["right_fingerprint"]
    assert len(screen["benchmark_inventory"])==26
    assert len(screen["benchmark_comparisons"])==260
    for case in CASES:
        root=tmp_path/case.task_id
        answer=sft.build_assistant_response(sft.load_task(root),sft.load_example_files_from_config(root))
        assert answer.startswith(f"{case.task_id}.h\n```")
        assert f"{case.task_id}.cpp\n```" in answer
        assert ".meta/" not in answer and "CMakeLists" not in answer
        dimensions=evidence[case.task_id]["hard_rule_dimensions"]
        assert set(dimensions)==set(tasks.HARD_RULE_DIMENSIONS)
        assert all(item["feature_count"]>0 for item in dimensions.values())
        assert all(re.fullmatch(r"sha256:[0-9a-f]{64}",item["fingerprint"]) for item in dimensions.values())
    independent={case.task_id:_independent_features(tmp_path/case.task_id) for case in CASES}
    for left,right in combinations(CASES,2):
        for dimension in tasks.HARD_RULE_DIMENSIONS:
            assert _independent_overlap(independent[left.task_id][dimension],independent[right.task_id][dimension])<0.90,(left.task_id,right.task_id,dimension)


def test_coherent_controls_change_build_inputs_and_fail_all_dimensions(tmp_path: Path) -> None:
    tasks.build(tmp_path/"family")
    root=tmp_path/"family/offset-build-freeze"
    for variant in tasks.ADVERSARIAL_CONTROLS:
        clone,result=tasks._make_control(root,variant,tmp_path/"controls")
        assert clone.is_dir()
        assert len(result["changed_files"])>=3
        assert result["failure"]=="duplicate_family"
        assert set(result["failed_dimensions"])==set(tasks.HARD_RULE_DIMENSIONS)
        assert all(value>=tasks.HARD_RULE_THRESHOLDS[name] for name,value in result["dimension_overlaps"].items())
        assert result["base_tree_hash"]!=result["tree_hash"] and result["role_mapping"]=="pass"
        base_features=_independent_features(root);clone_features=_independent_features(clone)
        assert all(base_features[name]==clone_features[name] for name in tasks.HARD_RULE_DIMENSIONS)


def test_root_count_and_roles_fail_closed(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    shutil.rmtree(tmp_path/CASES[-1].task_id)
    with pytest.raises(tasks.VerificationError,match="generator_output_drift"):
        tasks.verify_core(tmp_path)
    tasks.build(tmp_path,force=True)
    root=tmp_path/CASES[0].task_id
    config=json.loads((root/".meta/config.json").read_text())
    config["files"]["solution"].append("CMakeLists.txt")
    (root/".meta/config.json").write_text(json.dumps(config))
    with pytest.raises(tasks.VerificationError,match="unsafe_path"):
        tasks.verify_core(tmp_path)


def test_wrapper_and_planner_are_present() -> None:
    wrapper=Path("examples/slime/moonlight_cpp_perf/prepare_offset_aware_range_overlap_aider_tasks.sh")
    planner=Path(tasks.PLANNER)
    assert wrapper.is_file() and wrapper.stat().st_mode&0o111
    assert "aider-tasks-reverify/aider-text-grid-reshaping" in wrapper.read_text()
    assert planner.is_file()


def test_default_receipt_binds_current_tree_when_present() -> None:
    receipt_path=tasks.DEFAULT_OUT/".state/docker-sanity.json"
    if not receipt_path.is_file():pytest.skip("operator Docker receipt not generated")
    receipt=json.loads(receipt_path.read_text())
    assert receipt["status"]=="pass"
    assert receipt["evidence_class"]=="docker_sanity" and receipt["locked_oracle"] is False
    assert receipt["network"]=="none" and receipt["image"]==tasks.SANITY_IMAGE
    assert receipt["generator_revision"]==tasks._generator_revision()
    assert set(receipt["tasks"])=={case.task_id for case in CASES}
    assert set(receipt["hard_rule_controls"])==set(tasks.ADVERSARIAL_CONTROLS)
    for item in list(receipt["tasks"].values())+list(receipt["hard_rule_controls"].values()):
        assert item["normal"]==item["asan_ubsan"]==3
        assert item["tree_hash"]==item["mounted_tree_hash"]
        assert re.fullmatch(r"sha256:[0-9a-f]{64}",item["reference_hash"])
        assert re.fullmatch(r"sha256:[0-9a-f]{64}",item["compiler_hash"])
        assert item["compiler_path"].startswith("/") and item["compiler_version"] and item["cmake_version"]
        assert item["negative_fixture"]=="executed_and_rejected_in_both_modes"
