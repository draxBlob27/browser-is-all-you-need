from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_lifecycle_rollback_aider_tasks as lifecycle
from w8_biayn.integrations import moonlight_lifecycle_rollback_cases as cases
from w8_biayn.integrations import moonlight_lifecycle_rollback_diversity as diversity


@pytest.fixture(scope="module")
def verified_family(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("lifecycle-rollback") / "family"
    lifecycle.build(root)
    lifecycle.verify_core(root)
    return root


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_count_inventory_and_owner_only_shape(verified_family: Path) -> None:
    roots = lifecycle._real_task_roots(verified_family)
    assert len(cases.PROTOCOLS) == 10
    assert len(cases.TOPOLOGIES) == 7
    assert len(cases.TASKS) == lifecycle.ROOT_COUNT == 70
    assert len(roots) == 70
    assert {root.name for root in roots} == {task.task_id for task in cases.TASKS}
    assert len({(task.protocol.key, task.topology.key) for task in cases.TASKS}) == 70
    assert lifecycle.DEFAULT_OUT == Path(
        ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/lifecycle-rollback"
    )
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == lifecycle.FAMILY_ID
        assert provenance["lineage"] == "new-root"
        assert provenance["dataset_handoff"] == "not_requested"
        assert set(provenance["semantic_dimensions"]) == set(diversity.DIMENSIONS)


def test_independent_complete_pair_and_dimension_recomputation(verified_family: Path) -> None:
    screen = json.loads((verified_family / ".state/family-screen.json").read_text())
    assert screen["root_count"] == 70
    assert screen["dimensions"] == list(diversity.DIMENSIONS)
    assert screen["comparison_count"] == screen["expected_comparison_count"] == 70 * 69 // 2
    seen: set[tuple[str, str]] = set()
    for item in screen["pairwise"]:
        pair = tuple(sorted((item["left"], item["right"])))
        assert pair not in seen
        seen.add(pair)
        assert item["all_dimensions_distinct"] is True
        assert item["duplicate_dimensions"] == []
        assert set(item["dimension_decisions"]) == set(diversity.DIMENSIONS)
        for decision in item["dimension_decisions"].values():
            assert decision["distinct"] is True
            assert decision["left_witness_count"] > 0
            assert decision["right_witness_count"] > 0
            assert decision["left_artifact_fingerprint"] != decision["right_artifact_fingerprint"]
            assert decision["jaccard_similarity"] < decision["distinct_below"]
            assert "descriptor" not in " ".join(decision)
    assert len(seen) == 2415


def test_adversarial_controls_are_changed_coherent_and_rejected(verified_family: Path) -> None:
    screen = json.loads((verified_family / ".state/family-screen.json").read_text())
    controls = screen["adversarial_clone_results"]
    assert set(controls) == set(lifecycle.CONTROL_NAMES)
    base_ids = {
        "domain-identifier-renamed": "snapshot-linear-lifecycle",
        "constants-or-policy-only": "snapshot-quota-lifecycle",
        "opposite-end-selection": "snapshot-keyed-lifecycle",
    }
    for name, result in controls.items():
        control = verified_family / ".state/controls" / name
        base = verified_family / base_ids[name]
        assert result["failure"] == "duplicate_family"
        assert result["changed_files"]
        assert set(result["duplicate_dimensions"]) == set(diversity.DIMENSIONS)
        assert all(not decision["distinct"] for decision in result["dimension_decisions"].values())
        assert all(
            decision["jaccard_similarity"] >= decision["duplicate_at_or_above"]
            for decision in result["dimension_decisions"].values()
        )
        assert any(
            not (base / path.relative_to(control)).is_file()
            or _digest(path) != _digest(base / path.relative_to(control))
            for path in control.rglob("*")
            if path.is_file()
        )
        config = json.loads((control / ".meta/config.json").read_text())
        assert all((control / relative).is_file() for values in config["files"].values() for relative in values)


def test_prompt_reference_and_whole_file_boundaries(verified_family: Path) -> None:
    for task in (cases.TASKS[0], cases.TASKS[17], cases.TASKS[-1]):
        root = verified_family / task.task_id
        record = lifecycle._validate_one(root)
        assert record["prompt_boundary"] == "pass"
        assert record["primary_core_objective"] == "achieved"
        assert set(record["whole_file_negatives"]) == {
            "omitted-file", "extra-file", "prose-prefix", "duplicate-file"
        }


def test_cross_tree_ids_and_semantic_receipt_are_current(verified_family: Path) -> None:
    repo = lifecycle._repo_root()
    proposed = {task.task_id for task in cases.TASKS}
    for root in lifecycle.LEGACY_ROOTS:
        assert not (proposed & {task_root.name for task_root in lifecycle._real_task_roots(repo / root)})
    receipt = json.loads((verified_family / ".state/creator-preflight.json").read_text())
    cross = json.loads((verified_family / ".state/cross-corpus-screen.json").read_text())
    assert receipt["task_tree_hash"] == lifecycle._tree_hash(verified_family)
    assert receipt["owner_hash"] == lifecycle._owner_hash()
    assert receipt["status"] == "pending_docker_sanity"
    assert cross["status"] == "pass"
    assert cross["holdout_count"] == 26
    assert cross["comparison_count"] > 70 * 26
    assert cross["holdout_identity"]["checkout_clean"] is True
    assert cross["holdout_identity"]["root_count"] == 26
    assert len(cross["holdout_identity"]["records"]) == 26
    assert cross["pair_witness_hash"].startswith("sha256:")
    pair_path = verified_family / cross["pair_witness_path"]
    assert pair_path.is_file()
    assert sum(1 for _ in pair_path.open(encoding="utf-8")) == cross["comparison_count"]
    assert {value["disposition"] for value in cross["semantic_clone_calibration"].values()} == {
        "duplicate"
    }


def test_private_oracles_and_rollback_records_close_cycle_01_findings(
    verified_family: Path,
) -> None:
    for task in cases.TASKS:
        root = verified_family / task.task_id
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        header = (root / f"{task.task_id}.h").read_text()
        assert "struct Model" in hidden
        assert "model_apply_batch" in hidden
        assert "operation<64" in hidden
        assert f"state={task.seed}U" in hidden
        assert "repetition" not in hidden
        if task.protocol.key == "inverse":
            assert "struct InverseRecord" in header
            assert "std::vector<InverseRecord>" in header
            assert "std::vector<View> inverse" not in reference
            assert "if(!apply_one(event))" in reference
        if task.protocol.key == "undo":
            assert "struct UndoRecord" in header
            assert "std::vector<UndoRecord>" in header
            assert "std::vector<View> undo_log" not in reference
            assert "restore_undo" in reference
        if task.protocol.key == "saga":
            assert "struct Compensation" in header
            assert "std::vector<Compensation>" in header
            assert "std::vector<View> compensations" not in reference
            assert "run_compensation" in reference
        if task.protocol.key == "savepoint":
            assert "next_savepoint_token_" in header
            assert "last_savepoint_token()" in header
            assert "last_savepoint_token()!=2U" in hidden


def test_planned_remedy_records_bind_all_roots() -> None:
    family = lifecycle._repo_root() / lifecycle.DEFAULT_OUT
    remedy = family / ".state/remedy"
    records = sorted(remedy.glob("*.json"))
    specs = sorted((remedy / "specs").glob("*.md"))
    assert len(records) == len(specs) == 70
    for path in records:
        record = json.loads(path.read_text())
        assert record["task_id"] == path.stem
        assert record["disposition"] == "repair-in-place"
        assert record["status"] in {"planned", "implemented", "verified"}
        assert record["finding_ids"]


def test_representative_references_and_false_substitutes_compile_and_execute(
    verified_family: Path, tmp_path: Path
) -> None:
    compiler = shutil.which("c++")
    if compiler is None:
        pytest.skip("c++ unavailable; mandatory Docker verification remains separate")
    representatives = {
        *(task.task_id for task in cases.TASKS if task.topology.key == "linear"),
        *(task.task_id for task in cases.TASKS if task.protocol.key == "snapshot"),
    }
    for task_id in sorted(representatives):
        root = verified_family / task_id
        good = tmp_path / f"{task_id}-good"
        bad = tmp_path / f"{task_id}-bad"
        common = [compiler, "-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-I", str(root)]
        subprocess.run(common + [str(root / ".meta/example.cpp"), str(root / "task_visible_test.cpp"), "-o", str(good)], check=True)
        subprocess.run([str(good)], check=True)
        subprocess.run(common + [str(root / ".meta/negative.cpp"), str(root / "task_visible_test.cpp"), "-o", str(bad)], check=True)
        assert subprocess.run([str(bad)], check=False).returncode != 0
    for name in lifecycle.CONTROL_NAMES:
        root = verified_family / ".state/controls" / name
        config = json.loads((root / ".meta/config.json").read_text())
        header = config["files"]["solution"][0]
        assert (root / header).is_file()
        exe = tmp_path / f"control-{name}"
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-I", str(root),
             str(root / ".meta/example.cpp"), str(root / "task_visible_test.cpp"), "-o", str(exe)],
            check=True,
        )
        subprocess.run([str(exe)], check=True)
        if name == "opposite-end-selection":
            base = verified_family / "snapshot-keyed-lifecycle"
            control = root
            probe = tmp_path / "opposite-end-probe.cpp"
            probe.write_text(
                f'''#include "{header}"
#include <iostream>
using namespace snapshot_keyed_lifecycle;
int main() {{
  Machine machine;
  if(!machine.apply_batch(std::vector<Event>{{Event{{4,1,0}},Event{{4,2,0}},Event{{4,3,0}},Event{{2,1,0}}}})) return 2;
  for(int value:machine.view().values) std::cout << value << ' ';
}}
'''
            )
            outputs = []
            for label, subject in (("base", base), ("control", control)):
                probe_exe = tmp_path / f"opposite-end-{label}"
                subprocess.run(
                    [compiler, "-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                     "-I", str(subject), str(subject / ".meta/example.cpp"), str(probe),
                     "-o", str(probe_exe)],
                    check=True,
                )
                outputs.append(subprocess.run([str(probe_exe)], check=True, text=True, stdout=subprocess.PIPE).stdout)
            assert outputs == ["2 0 4 2 ", "4 2 2 0 "]


def test_cli_output_boundary_rejects_legacy_and_arbitrary_paths(tmp_path: Path) -> None:
    with pytest.raises(lifecycle.LifecycleRollbackError, match="unsafe_expansion_output"):
        lifecycle._assert_output_boundary(tmp_path / "other")
    with pytest.raises(lifecycle.LifecycleRollbackError, match="unsafe_expansion_output"):
        lifecycle._assert_output_boundary(Path(".w8-biayn/data/aider-tasks"))


def test_instructions_scope_cell_specific_sentences(verified_family: Path) -> None:
    linear = (verified_family / "snapshot-linear-lifecycle/.docs/instructions.md").read_text()
    assert "Keyed observations" not in linear
    assert "Quota roots" not in linear
    assert lifecycle._PROTOCOL_RECEIPT_NOTES["snapshot"] in linear
    keyed = (verified_family / "snapshot-keyed-lifecycle/.docs/instructions.md").read_text()
    assert "Keyed observations use ascending key order." in keyed
    assert "Quota roots" not in keyed
    quota = (verified_family / "snapshot-quota-lifecycle/.docs/instructions.md").read_text()
    assert "Quota roots start with exactly 10 units." in quota
    assert "Keyed observations" not in quota
    for task in cases.TASKS:
        docs = (verified_family / task.task_id / ".docs/instructions.md").read_text()
        assert lifecycle._PROTOCOL_RECEIPT_NOTES[task.protocol.key] in docs
        for key, note in lifecycle._PROTOCOL_RECEIPT_NOTES.items():
            if key != task.protocol.key:
                assert note not in docs


def test_cli_dispatches_build_verify_host_and_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        lifecycle, "build",
        lambda out, *, force, enforce_output: calls.setdefault("build", (out, force, enforce_output)),
    )
    monkeypatch.setattr(lifecycle, "verify_host", lambda out: calls.setdefault("verify_host", out))
    monkeypatch.setattr(
        lifecycle, "docker_sanity",
        lambda out, *, image: calls.setdefault("docker_sanity", (out, image)),
    )
    assert lifecycle.main(["--out", str(tmp_path), "--force"]) == 0
    assert calls["build"] == (tmp_path, True, True)
    assert lifecycle.main(["--out", str(tmp_path), "--verify-host"]) == 0
    assert calls["verify_host"] == tmp_path
    assert lifecycle.main(["--out", str(tmp_path), "--docker-sanity"]) == 0
    assert calls["docker_sanity"] == (tmp_path, lifecycle.SANITY_IMAGE)


def test_host_staged_reference_and_negative_single_root(verified_family: Path, tmp_path: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("host toolchain unavailable; mandatory Docker verification remains separate")
    root = verified_family / "snapshot-linear-lifecycle"
    staged = lifecycle._stage_task(root, tmp_path / "ref" / "task", negative=False)
    assert lifecycle._host_build_and_test(staged, tmp_path / "ref" / "build", sanitizer=False, expect_pass=True) == 2
    staged_negative = lifecycle._stage_task(root, tmp_path / "neg" / "task", negative=True)
    assert lifecycle._host_build_and_test(staged_negative, tmp_path / "neg" / "build", sanitizer=False, expect_pass=False) == 2
