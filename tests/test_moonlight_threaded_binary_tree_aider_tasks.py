from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_threaded_binary_tree_aider_tasks as tasks
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def _copy_plans(out: Path) -> None:
    source = tasks.ROOT / ".state/remedy"
    target = out / ".state/remedy"
    target.mkdir(parents=True)
    for case in tasks.CASES:
        for suffix in (".json", ".md"):
            (target / f"{case.legacy_id}{suffix}").write_bytes((source / f"{case.legacy_id}{suffix}").read_bytes())
        path = target / f"{case.legacy_id}.json"
        record = json.loads(path.read_text())
        record["status"] = "planned"
        record["primary_core_objective"] = "not_achieved"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def test_materializes_twenty_real_replacements(tmp_path: Path) -> None:
    _copy_plans(tmp_path)
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}
    assert len({case.logic_tag for case in tasks.CASES}) == 20
    assert sum(case.legacy_id == case.task_id for case in tasks.CASES) == 1
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == tasks.FAMILY_ID
        assert (root / ".meta/negative_fixture.cpp").read_text() == tasks._negative_source(
            next(case for case in tasks.CASES if case.task_id == root.name)
        )
        assert (root / ".meta/negative_fixture.json").is_file()
        prompt = build_prompt(load_task(root))
        assert f"{root.name}.h" in prompt and f"{root.name}.cpp" in prompt
        assert ".meta/example" not in prompt
        assert "task_hidden_test" not in prompt
        assert "CMakeLists.txt" not in prompt
        assert "negative_fixture" not in prompt
    core = json.loads((tmp_path / ".state/core-verification.json").read_text())
    assert core["status"] == "pass"
    assert core["primary_core_objective"] == "achieved"
    assert core["negative_fixture_result"] == "invariant_not_enforced"
    assert core["topic_negative_fixtures"]["count"] == 20
    assert core["topic_negative_fixtures"]["status"] == "pending_docker_execution"
    screen = json.loads((tmp_path / ".state/family-screen.json").read_text())
    assert screen["all_pairs_compared"] == 190
    assert screen["family_duplicate_screen"] == "pass"
    assert screen["hard_rule_status"] == "pass"
    assert set(screen["adversarial_clone_results"]) == {
        "domain-identifier-renamed-clone",
        "constants-or-policy-only-clone",
        "opposite-end-selection-clone",
    }
    assert all(
        set(row["differing_dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        and not row["same_dimensions"]
        and not row["violations"]
        for row in screen["hard_rule"]["pair_evidence"]
    )
    assert screen["prompt_boundary"] == "pass"


def test_plans_use_deterministic_dispositions() -> None:
    records = []
    for case in tasks.CASES:
        record = json.loads((tasks.ROOT / ".state/remedy" / f"{case.legacy_id}.json").read_text())
        records.append(record)
        assert record["status"] in {"planned", "implemented", "verified"}
        assert record["remediated_task_id"] == case.task_id
        assert record["tree_hash_before"].startswith("sha256:")
    assert [record["task_id"] for record in records if record["disposition"] == "repair-in-place"] == ["threaded-appointment-book"]
    assert sum(record["disposition"] == "replace" for record in records) == 19


def test_refuses_legacy_root() -> None:
    with pytest.raises(RuntimeError, match="LEGACY_ROOT"):
        tasks.build(tasks.LEGACY_ROOT, force=True)


def test_core_verifier_rejects_compilable_rebuild_fixture() -> None:
    fixture = "struct X { void erase(){ clear_all();root_=nullptr; } void clear_all(); void* root_; };"
    with pytest.raises(RuntimeError, match="invariant_not_enforced"):
        tasks._validate_reference(fixture, "legacy-rebuild-template")


@pytest.mark.parametrize(
    "clone_kind",
    [
        "domain-identifier-renamed-clone",
        "constants-or-policy-only-clone",
        "opposite-end-selection-clone",
    ],
)
def test_real_screen_rejects_required_emitted_adversarial_clones(
    tmp_path: Path, clone_kind: str
) -> None:
    family = tmp_path / "family"
    _copy_plans(family)
    tasks.build(family)
    source = family / tasks.CASES[0].task_id
    clone = tmp_path / clone_kind
    tasks._make_adversarial_clone(source, clone, clone_kind)
    evidence = tasks._pair_evidence(
        tasks._artifact_profile(source), tasks._artifact_profile(clone)
    )
    assert evidence["combined_overlap"] >= tasks.PAIR_THRESHOLD
    assert evidence["violations"]
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._screen_artifact_roots(
            [(source.name, source), (clone_kind, clone)],
            enforce_dimensions=False,
        )


def test_verify_records_unavailable_toolchain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".state/oracle").mkdir(parents=True)
    monkeypatch.setattr(tasks.shutil, "which", lambda _name: None)
    tasks.verify(tmp_path)
    receipt = json.loads((tmp_path / ".state/oracle/verification.json").read_text())
    assert receipt["status"] == "not_completed"
    assert set(receipt["missing_prerequisites"]) == {"cmake", "c++", "ctest"}
