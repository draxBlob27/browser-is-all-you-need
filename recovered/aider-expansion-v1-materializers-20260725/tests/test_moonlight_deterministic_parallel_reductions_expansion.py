from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import (
    moonlight_deterministic_parallel_reductions_expansion as dpr,
)
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory):
    temporary = tmp_path_factory.mktemp("dpr-expansion")
    old = (dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT)
    dpr.EXPANSION_ROOT = temporary / "expansion"
    dpr.LEGACY_ROOT = temporary / "legacy"
    dpr.REVERIFY_ROOT = temporary / "reverify"
    dpr.LEGACY_ROOT.mkdir()
    dpr.REVERIFY_ROOT.mkdir()
    out = dpr.EXPANSION_ROOT / "state-concurrency" / "deterministic-parallel-reductions"
    roots = dpr.build(out, force=True)
    try:
        yield out, roots
    finally:
        dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT = old


def _digest(parts: tuple[str, ...]) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def test_case_inventory_is_exact_and_mechanisms_are_unique():
    assert len(dpr.CASES) == 60
    assert len({case.task_id for case in dpr.CASES}) == 60
    assert {case.group for case in dpr.CASES} == set(dpr.GROUPS)
    assert {
        group: sum(case.group == group for case in dpr.CASES)
        for group in dpr.GROUPS
    } == {group: 12 for group in dpr.GROUPS}
    assert len({case.mechanism for case in dpr.CASES}) == 60
    assert all(case.task_id.startswith("dpr-") for case in dpr.CASES)
    assert all(dpr._oracle(case, [], [], 1, 1) is not None for case in dpr.CASES)


def test_materialization_roles_prompts_and_oracles(generated):
    out, roots = generated
    assert len(roots) == 60
    for case, root in zip(dpr.CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [
            f"{case.task_id}.h",
            f"{case.task_id}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        task = load_task(root)
        prompt = build_prompt(task)
        assert case.task_id + ".h" in prompt
        assert case.task_id + ".cpp" in prompt
        assert not any(
            marker in prompt
            for marker in (
                ".meta/",
                "CMakeLists",
                "task_visible_test",
                "negative_false_substitute",
                "provenance",
            )
        )
        answer = build_assistant_response(task, load_example_files_from_config(root))
        assert answer.startswith(f"{case.task_id}.h\n```")
        assert f"{case.task_id}.cpp\n```" in answer
        visible = dpr._sample(case, False)
        hidden = dpr._sample(case, True)
        for values, keys, workers, parameter in (visible, hidden):
            expected = dpr._oracle(case, values, keys, workers, parameter)
            assert expected is not None and expected
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert reference != negative
        assert "out.pop_back()" not in reference
        assert "out.pop_back()" in negative
        assert "switch(" not in reference and "switch (" not in reference
    assert len(list((out / ".state/contracts").glob("dpr-*.md"))) == 60


def test_all_pairs_and_controls_are_independently_accounted(generated):
    out, roots = generated
    screen = dpr._semantic_screen(out)
    assert screen["pair_count"] == 1770
    assert screen["expected_pair_count"] == 1770
    assert tuple(screen["dimensions"]) == dpr.HARD_DIMENSIONS
    expected_pairs = {
        (left.name, right.name)
        for index, left in enumerate(sorted(roots, key=lambda path: path.name))
        for right in sorted(roots, key=lambda path: path.name)[index + 1 :]
    }
    recorded_pairs = {(row["left"], row["right"]) for row in screen["pairs"]}
    assert recorded_pairs == expected_pairs
    assert all(
        set(row["decisions"]) == set(dpr.HARD_DIMENSIONS)
        and all(row["decisions"].values())
        for row in screen["pairs"]
    )
    # Independent profile uniqueness: this does not call the production pair
    # decision helper and catches a receipt manufactured from IDs alone.
    for dimension in dpr.HARD_DIMENSIONS:
        profiles = []
        for root in roots:
            provenance = json.loads((root / ".meta/provenance.json").read_text())
            profiles.append(provenance["semantic_profile"][dimension])
        assert len({_digest((value,)) for value in profiles}) == 60
    base = out / dpr.CASES[27].task_id
    base_hashes = {
        path.relative_to(base).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in base.rglob("*")
        if path.is_file()
    }
    controls_manifest = json.loads(
        (out / ".state/adversarial-clone-controls/manifest.json").read_text()
    )
    for name, record in screen["controls"].items():
        control = out / ".state/adversarial-clone-controls" / name
        control_hashes = {
            path.relative_to(control).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in control.rglob("*")
            if path.is_file()
        }
        assert base_hashes != control_hashes
        assert controls_manifest["controls"][name]["changed_files"]
        assert set(record["decisions"]) == set(dpr.HARD_DIMENSIONS)
        assert not any(record["decisions"].values())
        config = json.loads((control / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [
            f"{dpr.CASES[27].task_id}.h",
            f"{dpr.CASES[27].task_id}.cpp",
        ]


def test_output_and_collision_guards(tmp_path: Path):
    with pytest.raises(RuntimeError, match="unsafe_path"):
        dpr._validate_output(dpr.LEGACY_ROOT)
    with pytest.raises(RuntimeError, match="unsafe_path"):
        dpr._validate_output(dpr.REVERIFY_ROOT)
    with pytest.raises(RuntimeError, match="unsafe_path"):
        dpr._validate_output(dpr.EXPANSION_ROOT)

    expansion = tmp_path / "expansion"
    legacy = tmp_path / "legacy"
    reverify = tmp_path / "reverify"
    collision = legacy / "topic" / dpr.CASES[0].task_id / ".meta/config.json"
    collision.parent.mkdir(parents=True)
    collision.write_text('{"files":{"solution":[],"test":[],"example":[]}}\n')
    old = (dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT)
    dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT = expansion, legacy, reverify
    reverify.mkdir()
    try:
        with pytest.raises(RuntimeError, match="duplicate_task"):
            dpr.build(expansion / "state-concurrency" / "family", force=True)
    finally:
        dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT = old


def test_foreign_family_tree_fails_closed(tmp_path: Path):
    expansion = tmp_path / "expansion"
    legacy = tmp_path / "legacy"
    reverify = tmp_path / "reverify"
    out = expansion / "state-concurrency" / "deterministic-parallel-reductions"
    provenance = out / "v2-owned-root" / ".meta" / "provenance.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text(
        json.dumps({"family_id": "aider-expansion-v1-deterministic-parallel-reductions-v2"}) + "\n"
    )
    legacy.mkdir()
    reverify.mkdir()
    old = (dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT)
    dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT = expansion, legacy, reverify
    try:
        with pytest.raises(RuntimeError, match="foreign_root"):
            dpr.build(out, force=True)
    finally:
        dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT = old
