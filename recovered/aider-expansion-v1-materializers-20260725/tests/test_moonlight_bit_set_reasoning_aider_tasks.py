from __future__ import annotations

import inspect
import json
import re
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_bit_set_reasoning_aider_tasks as tasks


def _audit_tokens(root: Path,text: str) -> set[str]:
    provenance=json.loads((root/".meta/provenance.json").read_text())
    stem=provenance["task_id"].replace("-","_")
    for identifier in (f"bitset_{stem}",f"evaluate_{stem}",stem,provenance["task_id"]):
        text=re.sub(re.escape(identifier)," task_identifier ",text,flags=re.I)
    text=re.sub(r"//.*?$|/\*.*?\*/"," ",text,flags=re.M|re.S)
    text=re.sub(r'"(?:\\.|[^"\\])*"'," STRING ",text)
    text=re.sub(r"\b(?:0x[0-9a-f]+|\d+)[ul]*\b"," NUMBER ",text.lower())
    return set(re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|\+\+|--|\^|&|\|",text))


def _audit_structure_tokens(text:str)->set[str]:
    language=set("alignas auto bool break case class const constexpr continue default do else enum explicit false for if long namespace noexcept public return short signed static_assert struct switch true typedef unsigned using void while".split())
    text=re.sub(r"//.*?$|/\*.*?\*/"," ",text,flags=re.M|re.S)
    text=re.sub(r'"(?:\\.|[^"\\])*"'," STRING ",text)
    text=re.sub(r"\b(?:0x[0-9a-f]+|\d+)[ul]*\b"," NUMBER ",text.lower())
    raw=re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|\+\+|--|&&|\|\||<<|>>|::|[{}();,?:+*/%^&|!<>=\[\]-]",text)
    normalized=[token if token in language or not re.fullmatch(r"[a-z_][a-z0-9_]*",token) else "IDENTIFIER" for token in raw]
    return {f"{index}:"+" ".join(normalized[index:index+3]) for index in range(max(1,len(normalized)-2))}


def _independent_features(root: Path) -> dict[str,set[str]]:
    docs=(root/".docs/instructions.md").read_text()
    contract=docs.split("Operation:",1)[-1].split("Public example:",1)[0]
    reference=(root/".meta/example.cpp").read_text()
    core=reference.split("// CORE_BEGIN",1)[1].split("// CORE_END",1)[0]
    visible=(root/"task_visible_test.cpp").read_text()
    hidden=(root/".meta/task_hidden_test.cpp").read_text()
    negative=(root/".meta/negative_false_substitute.cpp").read_text()
    header=next(root.glob("*.h")).read_text()
    return {
        "public_api":_audit_structure_tokens(header),
        "owned_state_or_algorithm":_audit_structure_tokens(core),
        "mutation_selection_rules":_audit_structure_tokens(core+visible),
        "invalid_boundary_behavior":_audit_structure_tokens(core+hidden),
        "reference_control_flow":_audit_structure_tokens(core),
        "deterministic_oracle":_audit_structure_tokens(visible+hidden),
        "topic_negative_fixture":_audit_structure_tokens(negative),
    }


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    repo=tmp_path/"repo";expansion=repo/".w8-biayn/data/aider-tasks-expansion-v1";out=expansion/"numerical/bit-set-reasoning"
    curriculum=repo/tasks.CURRICULUM.relative_to(tasks.REPO_ROOT);curriculum.parent.mkdir(parents=True);curriculum.write_text(tasks.CURRICULUM.read_text())
    spec=repo/tasks.FAMILY_SPEC.relative_to(tasks.REPO_ROOT);spec.parent.mkdir(parents=True);spec.write_text(tasks.FAMILY_SPEC.read_text())
    holdouts=repo/".cache/upstreams/aider-polyglot/cpp/exercises/practice"
    for slug in tasks.OFFICIAL_HOLDOUTS:
        docs=holdouts/slug/".docs";docs.mkdir(parents=True);(docs/"instructions.md").write_text(f"Independent holdout {slug}.\n")
    owner=repo/tasks.OWNER;owner.parent.mkdir(parents=True);owner.write_text(Path(tasks.__file__).read_text())
    focused=repo/tasks.FOCUSED_TEST;focused.parent.mkdir(parents=True);focused.write_text(Path(__file__).read_text())
    monkeypatch.setattr(tasks,"REPO_ROOT",repo);monkeypatch.setattr(tasks,"EXPANSION_ROOT",expansion);monkeypatch.setattr(tasks,"DEFAULT_OUT",out)
    monkeypatch.setattr(tasks,"CURRICULUM",curriculum);monkeypatch.setattr(tasks,"FAMILY_SPEC",spec);monkeypatch.setattr(tasks,"HOLDOUT_ROOT",holdouts)
    monkeypatch.setattr(tasks,"LEGACY_ROOTS",(repo/".w8-biayn/data/aider-tasks",repo/".w8-biayn/data/aider-tasks-reverify"))
    return out


def test_exact_40_curriculum_and_distinct_oracles() -> None:
    cases=tasks.cases()
    assert len(cases)==40
    assert len({case.task_id for case in cases})==40
    assert len(tasks.CPP_BODIES)==40
    assert len(set(tasks.CPP_BODIES))==40
    assert len(tasks.PUBLIC_CONTRACTS)==40 and len(set(tasks.PUBLIC_CONTRACTS))==40
    assert len(tasks.NEGATIVE_BODIES)==40 and len(set(tasks.NEGATIVE_BODIES))==40
    assert len(tasks.API_FIELDS)==40 and len(set(tasks.API_FIELDS))==40
    assert len({tasks._api_patterns(case.ordinal) for case in cases})==40
    assert len(tasks.TARGETED_CASES)==40
    assert len(tasks.TARGETED_RULES)==40 and len({rule for pair in tasks.TARGETED_RULES for rule in pair})==80
    assert cases[9].task_id=="bit-index-permutation"
    assert cases[10].task_id=="bit-carryless-product"
    for case in cases:
        a,b,w=tasks.INPUTS[case.ordinal][0]
        result=tasks._oracle(case.ordinal,a,b,w)
        assert result not in ((True,0,0),(False,0,0)),case.task_id
        for targeted in tasks.TARGETED_CASES[case.ordinal]:
            assert tasks._oracle(case.ordinal,*targeted[:3])==targeted[3:],case.task_id
    for ordinal,excessive in ((27,5),(28,5),(29,5),(33,9),(34,9),(35,5),(36,5),(37,9),(39,9)):
        assert tasks._oracle(ordinal,1,0,excessive)==(False,0,0)


def test_materialization_roles_prompt_and_new_lineage(monkeypatch: pytest.MonkeyPatch,tmp_path: Path) -> None:
    out=_sandbox(monkeypatch,tmp_path);receipt=tasks.materialize(out)
    assert receipt["task_count"]==40
    for case in tasks.cases():
        root=out/case.task_id;config=json.loads((root/".meta/config.json").read_text());provenance=json.loads((root/".meta/provenance.json").read_text())
        assert config["files"]["solution"]==[f"{case.task_id}.h",f"{case.task_id}.cpp"]
        assert config["files"]["example"]==[".meta/example.h",".meta/example.cpp"]
        assert provenance["dataset_handoff"]=="not_requested"
        if case.ordinal in (9,10):assert provenance["lineage"]=="replacement-backfill" and provenance["replaces"].startswith("bit-morton-")
        else:assert provenance["lineage"]=="new-root"
        assert config["license"]==provenance["license"]=="CC0-1.0"
        assert tasks.PUBLIC_CONTRACTS[case.ordinal] in (root/".docs/instructions.md").read_text()
        instructions=(root/".docs/instructions.md").read_text()
        assert instructions.startswith("# Instructions\n")
        assert "Public example:" in instructions
        for banned in ("clean-room","Core mechanism","hidden test","oracle","grader","benchmark","remediation","campaign"):
            assert banned not in instructions,(case.task_id,banned)
        introduction=(root/".docs/introduction.md").read_text()
        assert "clean-room" not in introduction
        assert len(introduction.split("\n\n"))>=3
        header=(root/f"{case.task_id}.h").read_text()
        assert "struct Request" in header and all(field in header for field in tasks.API_FIELDS[case.ordinal])
        assert (root/"task_visible_test.cpp").read_text()!=(root/".meta/task_hidden_test.cpp").read_text()
        assert "CORE_BEGIN" in (root/".meta/example.cpp").read_text()
        assert (root/".meta/negative_false_substitute.cpp").is_file()
    inventory=json.loads((out/".state/source-inventory.json").read_text())
    assert inventory["record_count"]==inventory["legacy_count"]+inventory["reverify_count"]+inventory["expansion_external_count"]==len(inventory["records"])
    assert all("semantic_tree_hash" in row and "semantic_file_count" in row for row in inventory["records"])
    catalog=json.loads((out/".state/targeted-case-catalog.json").read_text())
    assert catalog["record_count"]==40 and catalog["case_count"]==80


def test_all_780_pairs_have_seven_independent_decisions(monkeypatch: pytest.MonkeyPatch,tmp_path: Path) -> None:
    out=_sandbox(monkeypatch,tmp_path);tasks.materialize(out);screen=tasks.verify_core(out)
    assert screen["root_count"]==40 and screen["pair_count"]==780
    stored=json.loads((out/".state/family-screen.json").read_text())
    assert stored["pair_count"]==len(list(combinations(tasks.cases(),2)))==780
    assert tuple(stored["dimensions"])==tasks.DIMENSIONS
    for pair in stored["pairs"]:
        assert set(pair["dimensions"])==set(tasks.DIMENSIONS)
        assert all(value["distinct"] for value in pair["dimensions"].values())
        assert all(value["left_hash"]!=value["right_hash"] for value in pair["dimensions"].values())
        left=_independent_features(out/pair["left"]);right=_independent_features(out/pair["right"])
        for dimension in tasks.DIMENSIONS:
            union=left[dimension]|right[dimension]
            assert left[dimension]!=right[dimension],(pair["left"],pair["right"],dimension)
            assert len(left[dimension]^right[dimension])>=3,(pair["left"],pair["right"],dimension)
            ceiling=0.98 if dimension in {"public_api","reference_control_flow","deterministic_oracle"} else 0.95
            assert len(left[dimension]&right[dimension])/max(1,len(union))<ceiling,(pair["left"],pair["right"],dimension)
    assert len(stored["controls"])==3
    for control in stored["controls"]:
        assert control["changed_files"] and control["coherent"] and control["production_rejected"]
        assert control["base_task_id"] in {case.task_id for case in tasks.cases()}
        assert control["decision"]["pass"] is False


def test_output_guard_and_cross_tree_collision(monkeypatch: pytest.MonkeyPatch,tmp_path: Path) -> None:
    out=_sandbox(monkeypatch,tmp_path)
    with pytest.raises(tasks.CreatorError,match="invalid_output_root"):tasks.materialize(tasks.LEGACY_ROOTS[0])
    collision=tasks.LEGACY_ROOTS[0]/"other"/tasks.cases()[0].task_id/".meta";collision.mkdir(parents=True);(collision/"config.json").write_text("{}")
    with pytest.raises(tasks.CreatorError,match="existing_task_id"):tasks.materialize(out)


def test_docker_contract_is_network_disabled_and_fresh() -> None:
    source=inspect.getsource(tasks.docker_sanity)+tasks.DOCKER_SCRIPT
    assert '"--network","none"' in source
    assert 'Unix Makefiles' in source
    assert '-fsanitize=address,undefined' in source
    assert 'negative_test' in source
    assert 'sanitizer_test_count_mismatch' in source
    assert 'CONTROL_RESULT' in source and 'control_records' in source
    assert 'MOUNT_HASH' in source and 'grader_mount_hash_mismatch' in source
    assert 'negative_hidden_test' in source and 'compiler_hash' in source


def test_host_contract_is_fresh_and_complete() -> None:
    source=inspect.getsource(tasks.verify_host)+inspect.getsource(tasks._verify_one_host)
    assert 'verify_core(out)' in source
    assert 'Unix Makefiles' in source
    assert '-fsanitize=address,undefined' in source
    assert 'negative_test' in source and 'negative_hidden_test' in source
    assert 'zero_tests' in source and 'sanitizer_test_count_mismatch' in source
    assert 'negative_fixture_not_rejected' in source and 'clone_control_failed' in source
    assert 'host_prerequisite_missing' in source and 'compiler_hash' in source
    assert '"bit-set-host-iteration-v1"' in source and 'host_iteration' in source
    assert '"domain-identifier-renamed","constants-policy-only","opposite-end-selection"' in source
    assert 'host-iteration.json' in source and '_tree_hash(out)' in source


def test_docs_bind_count_plan_and_nonclaims() -> None:
    curriculum=tasks.CURRICULUM.read_text();spec=tasks.FAMILY_SPEC.read_text()
    assert "exactly 40" in curriculum and "780" in curriculum
    assert ".w8-biayn/data/aider-tasks-expansion-v1/" in curriculum
    assert "local_family_verified" in curriculum and "does not authorize" in curriculum
    assert "no SFT release" in spec and "not_requested" in spec
