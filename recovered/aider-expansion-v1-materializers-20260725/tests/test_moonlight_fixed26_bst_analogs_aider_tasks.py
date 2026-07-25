from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_fixed26_bst_analogs_aider_tasks as tasks
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def _patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    expansion = repo / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "aider-fixed26-analogs/fixed26-b004-binary-search-tree"
    curriculum = repo / tasks.CURRICULUM.relative_to(tasks.REPO_ROOT)
    curriculum.parent.mkdir(parents=True)
    curriculum.write_text(tasks.CURRICULUM.read_text())
    manifest = repo / tasks.BENCHMARK_MANIFEST.relative_to(tasks.REPO_ROOT)
    manifest.parent.mkdir(parents=True)
    manifest_payload = json.loads(tasks.BENCHMARK_MANIFEST.read_text())
    manifest.write_text(json.dumps(manifest_payload))
    holdouts = repo / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
    for slug in manifest_payload["task_ids"]:
        docs = holdouts / slug / ".docs"
        docs.mkdir(parents=True)
        (docs / "instructions.md").write_text(f"Independent official holdout text for {slug}.\n")
    owner = repo / tasks.OWNER
    owner.parent.mkdir(parents=True)
    owner.write_text(Path(tasks.__file__).read_text())
    focused = repo / tasks.FOCUSED_TEST
    focused.parent.mkdir(parents=True)
    focused.write_text(Path(__file__).read_text())
    monkeypatch.setattr(tasks, "REPO_ROOT", repo)
    monkeypatch.setattr(tasks, "CURRICULUM", curriculum)
    monkeypatch.setattr(tasks, "SPEC_DOCUMENT", curriculum)
    monkeypatch.setattr(tasks, "GENERATOR_PATH", owner)
    monkeypatch.setattr(tasks, "DEFAULT_OUT", out)
    monkeypatch.setattr(tasks, "LEGACY_ROOT", repo / ".w8-biayn/data/aider-tasks")
    monkeypatch.setattr(tasks, "REVERIFY_ROOT", repo / ".w8-biayn/data/aider-tasks-reverify")
    monkeypatch.setattr(tasks, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(tasks, "HOLDOUT_ROOT", holdouts)
    monkeypatch.setattr(tasks, "BENCHMARK_MANIFEST", manifest)
    return out


def test_spec_and_owner_have_exact_50_unique_ordered_roots() -> None:
    rows = tasks.TASKS
    assert len(rows) == tasks.EXPECTED_ROOTS == 50
    assert len({row.task_id for row in rows}) == 50
    assert rows[0].task_id == "f26bst-tide-gauge-ledger"
    assert rows[-1].task_id == "f26bst-desert-well-index"
    spec_ids = re.findall(r"^\| `(f26bst-[a-z0-9-]+)` \|", tasks.CURRICULUM.read_text(), re.M)
    assert spec_ids == [row.task_id for row in rows]
    assert {row.task_id for row in rows if row.project_support} == tasks.PROJECT_SUPPORT_IDS
    assert sum(row.project_support for row in rows) == 15


def test_materialization_roles_prompt_boundary_and_support_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    result = tasks.build(out, testing=True)
    assert result["root_count"] == 50
    roots = sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state")
    assert len(roots) == 50
    support_roots = []
    for spec in tasks.TASKS:
        root = out / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{spec.task_id}.h", f"{spec.task_id}.cpp"]
        assert config["files"]["test"] == ["visible_test.cpp", ".meta/private_test.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        prompt = build_prompt(load_task(root))
        assert f"{spec.task_id}.h" in prompt and f"{spec.task_id}.cpp" in prompt
        assert len(re.findall(r"^# Instructions$", prompt, re.M)) == 1
        assert ".meta/" not in prompt
        assert "negative.cpp" not in prompt
        assert "private_test" not in prompt
        assert "CMakeLists.txt" not in prompt
        assert (root / ".meta/negative.cpp").read_text() != (root / ".meta/example.cpp").read_text()
        if (root / ".meta/support").is_dir():
            support_roots.append(spec.task_id)
    assert set(support_roots) == tasks.PROJECT_SUPPORT_IDS


def test_rejects_existing_trees_and_id_collision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    with pytest.raises(tasks.FamilyError, match="unsafe_path"):
        tasks._validate_output(tasks.LEGACY_ROOT)
    collision = tasks.LEGACY_ROOT / "some-family" / tasks.TASKS[3].task_id / ".meta"
    collision.mkdir(parents=True)
    (collision / "config.json").write_text("{}\n")
    with pytest.raises(tasks.FamilyError, match="duplicate_task"):
        tasks.build(out, testing=True)


def test_core_screen_has_1225_pairs_controls_and_lineage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.build(out, testing=True)
    receipt = tasks.verify_core(out)
    assert receipt["root_count"] == 50
    assert all(record["prompt_instruction_heading_count"] == 1 for record in receipt["prompt_records"].values())
    assert "/data/sanil/" not in json.dumps(receipt)
    assert "/tmp/" not in json.dumps(receipt)
    screen = json.loads((out / ".state/receipts/diversity-screen.json").read_text())
    assert screen["pair_count"] == 1225
    assert screen["dimensions"] == list(tasks.HARD_DIMENSIONS)
    assert len(screen["decisions"]) == 1225
    assert all(row["pass"] for row in screen["decisions"])
    assert len(screen["controls"]) == 3
    assert all(control["rejected_in_all_dimensions"] for control in screen["controls"])
    assert receipt["lineage_screen"]["holdout_count"] == 26


def test_output_is_deterministic_under_owner_regeneration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    first = tasks.build(out, testing=True)["tree_hash"]
    second = tasks.build(out, force=True, testing=True)["tree_hash"]
    assert first == second
    assert json.loads((out / ".state/manifests/batch-ledger.json").read_text())["failed_roots"] == []


def test_audit_is_subject_bound_and_records_local_family_verified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.build(out, testing=True)
    tasks.verify_core(out)
    receipts = out / ".state/receipts"
    phase_receipt = {
        "commands": [{"phase": "test", "returncode": 0, "stdout_hash": "sha256:test", "stderr_hash": "sha256:test"}],
        "test_count": 2,
        "rejected": False,
    }
    negative_phase_receipt = {
        "commands": [{"phase": "test", "returncode": 8, "stdout_hash": "sha256:test", "stderr_hash": "sha256:test"}],
        "test_count": 2,
        "rejected": True,
    }
    docker = {
        "tree_hash": tasks._tree_hash(out),
        "generator_revision": tasks._generator_revision(),
        "normal_test_count": 100,
        "sanitizer_test_count": 100,
        "negative_rejections": 50,
        "negative_normal_rejections": 50,
        "negative_sanitizer_rejections": 50,
        "stdout_hash": "sha256:test",
        "stderr_hash": "sha256:test",
        "compiler_path": "/usr/local/bin/c++",
        "compiler_version": "c++ test version",
        "compiler_version_hash": "sha256:test",
        "compiler_hash": "sha256:test",
        "cmake_path": "/usr/bin/cmake",
        "cmake_version": "cmake version test",
        "cmake_hash": "sha256:test",
        "per_root": [
            {
                "task_id": spec.task_id,
                "prompt_hash": "sha256:test",
                "source_tree_hash": "sha256:test",
                "starter_hash": "sha256:test",
                "reference_hash": "sha256:test",
                "visible_test_hash": "sha256:test",
                "private_test_hash": "sha256:test",
                "negative_fixture_hash": "sha256:test",
                "normal": phase_receipt,
                "sanitizer": phase_receipt,
                "negative_normal": negative_phase_receipt,
                "negative_sanitizer": negative_phase_receipt,
                "compiler_path": "/usr/local/bin/c++",
                "compiler_version": "c++ test version",
                "compiler_version_hash": "sha256:test",
                "compiler_hash": "sha256:test",
                "cmake_path": "/usr/bin/cmake",
                "cmake_version": "cmake version test",
                "cmake_hash": "sha256:test",
            }
            for spec in tasks.TASKS
        ],
    }
    (receipts / "docker-sanity.json").write_text(json.dumps(docker, sort_keys=True))
    creator = {
        "subject_hash": "sha256:test",
        "bindings": {"selected_manifest": "sha256:selected"},
    }
    (receipts / "creator-preflight.json").write_text(json.dumps(creator, sort_keys=True))
    report = tasks.audit(out, cycle=1)
    assert report["decision"] == "local_family_verified"
    assert report["confirmed_counts"]["roots"] == 50
    assert report["confirmed_counts"]["per_root_docker_receipts"] == 50
    assert (tasks.REPO_ROOT / report["report_path"]).is_file()


def test_generated_state_has_no_private_path_leaks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.build(out, testing=True)
    receipt = tasks.verify_core(out)
    leaks = tasks._private_path_leaks(out)
    assert leaks == []
    assert not str(receipt["lineage_screen"]).count(str(tmp_path))
