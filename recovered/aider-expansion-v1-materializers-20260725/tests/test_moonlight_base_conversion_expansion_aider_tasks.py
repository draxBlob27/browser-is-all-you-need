from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_base_conversion_expansion_aider_tasks as tasks


def _patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    expansion = repo / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "numerical-anchors/base-conversion-invalid-digits"
    curriculum = repo / tasks.CURRICULUM.relative_to(tasks.REPO_ROOT)
    curriculum.parent.mkdir(parents=True)
    curriculum.write_text(tasks.CURRICULUM.read_text())
    holdouts = repo / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
    for slug in tasks.OFFICIAL_HOLDOUTS:
        docs = holdouts / slug / ".docs"
        docs.mkdir(parents=True)
        (docs / "instructions.md").write_text(f"Independent permanent holdout contract for {slug}.\n")
    monkeypatch.setattr(tasks, "REPO_ROOT", repo)
    monkeypatch.setattr(tasks, "CURRICULUM", curriculum)
    monkeypatch.setattr(tasks, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(tasks, "DEFAULT_OUT", out)
    monkeypatch.setattr(
        tasks,
        "EXISTING_ROOTS",
        (repo / ".w8-biayn/data/aider-tasks", repo / ".w8-biayn/data/aider-tasks-reverify"),
    )
    monkeypatch.setattr(tasks, "HOLDOUT_ROOT", holdouts)
    owner = repo / tasks.OWNER
    owner.parent.mkdir(parents=True)
    owner.write_text(Path(tasks.__file__).read_text())
    focused = repo / tasks.FOCUSED_TEST
    focused.parent.mkdir(parents=True, exist_ok=True)
    focused.write_text(Path(__file__).read_text())
    return out


def _tokens(text: str) -> tuple[str, ...]:
    """Independent test-only normalizer; intentionally not the owner helper."""
    text = re.sub(r"//[^\n]*|/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STRING ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " STRING ", text)
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)\b", " NUMBER ", text)
    text = text.lower().replace("base_conversion_curriculum", "namespace")
    return tuple(re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|<<|>>|&&|\|\||[-+*/%<>{}=?:]", text))


def _grams(text: str, width: int) -> set[str]:
    tokens = _tokens(text)
    return {" ".join(tokens[i : i + width]) for i in range(max(1, len(tokens) - width + 1))}


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right)


def test_curriculum_and_owner_have_exact_40_unique_ordered_roots() -> None:
    rows = tasks.specs()
    assert len(rows) == 40
    assert len({row.task_id for row in rows}) == 40
    assert rows[0].task_id == "basecv-radix-frame-stream"
    assert rows[-1].task_id == "basecv-canonical-cantor-pair"
    curriculum_ids = re.findall(r"^\| `(basecv-[a-z0-9-]+)` \|", tasks.CURRICULUM.read_text(), re.M)
    assert curriculum_ids == [row.task_id for row in rows]
    assert len({row.api for row in rows}) == 40
    assert len({row.reference for row in rows}) == 40
    assert len({row.private for row in rows}) == 40
    assert len({(row.bad_from, row.bad_to) for row in rows}) == 40


def test_materializes_only_role_safe_owner_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    manifest = tasks.materialize(out)
    assert manifest["task_count"] == 40
    assert len(list(out.glob("basecv-*/.meta/config.json"))) == 40
    assert sorted(path.name for path in (out / ".state/hard-rule-controls").iterdir()) == sorted(tasks.CONTROLS)
    for spec in tasks.specs():
        root = out / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{spec.task_id}.h", f"{spec.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        prompt_paths = [".docs/introduction.md", ".docs/instructions.md", *config["files"]["solution"]]
        prompt = "\n".join((root / path).read_text() for path in prompt_paths)
        assert ".meta/" not in prompt
        assert "private_test" not in prompt
        assert "negative.cpp" not in prompt
        instructions = (root / ".docs/instructions.md").read_text()
        assert instructions.startswith("# Instructions\n")
        assert "## Examples" in instructions
        assert spec.forbidden in instructions
        for banned in (
            "clean-room",
            "must not be delegated",
            "Implement the required",
            "hidden test",
            "oracle",
            "grader",
            "benchmark",
        ):
            assert banned not in instructions, (spec.task_id, banned)
        introduction = (root / ".docs/introduction.md").read_text()
        assert "clean-room" not in introduction
        assert len(introduction.split("\n\n")) >= 3
        negative = (root / ".meta/negative.cpp").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        assert negative != reference
        assert spec.bad_from in reference
        assert spec.bad_to in negative


def test_rejects_existing_trees_foreign_output_and_id_collision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    with pytest.raises(tasks.CreatorError, match="invalid_output_root"):
        tasks.materialize(tasks.EXISTING_ROOTS[0])
    collision = tasks.EXISTING_ROOTS[0] / "numerical" / tasks.specs()[3].task_id / ".meta"
    collision.mkdir(parents=True)
    (collision / "config.json").write_text("{}\n")
    with pytest.raises(tasks.CreatorError, match="existing_task_id"):
        tasks.materialize(out)


def test_all_780_pairs_have_seven_independent_decisions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    report = tasks.diversity_screen(out)
    assert report["root_count"] == 40
    assert report["pair_count"] == 780
    assert tuple(report["dimensions"]) == tasks.DIMENSIONS
    assert all(row["pass"] for row in report["pairs"])
    assert all(set(row["dimensions"]) == set(tasks.DIMENSIONS) for row in report["pairs"])
    assert all(all(decision["pass"] for decision in row["dimensions"].values()) for row in report["pairs"])
    # Independent artifact checks: APIs, references, private oracles, and
    # reference-to-negative edits are genuinely non-identical for every pair.
    roots = [out / spec.task_id for spec in tasks.specs()]
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            assert (left / ".meta/example.h").read_text() != (right / ".meta/example.h").read_text()
            assert (left / ".meta/example.cpp").read_text() != (right / ".meta/example.cpp").read_text()
            assert (left / ".meta/private_test.cpp").read_text() != (right / ".meta/private_test.cpp").read_text()
            left_delta = _grams((left / ".meta/example.cpp").read_text(), 5) ^ _grams((left / ".meta/negative.cpp").read_text(), 5)
            right_delta = _grams((right / ".meta/example.cpp").read_text(), 5) ^ _grams((right / ".meta/negative.cpp").read_text(), 5)
            assert left_delta
            assert right_delta
            assert left_delta != right_delta


@pytest.mark.parametrize("variant", tasks.CONTROLS)
def test_coherent_clone_controls_change_files_but_remain_semantic_clones(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, variant: str
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    source = out / tasks.specs()[0].task_id
    control = out / ".state/hard-rule-controls" / variant
    changed = []
    for path in control.rglob("*"):
        if not path.is_file() or path.name == ".control.json":
            continue
        relative = path.relative_to(control)
        if not (source / relative).is_file() or path.read_bytes() != (source / relative).read_bytes():
            changed.append(relative.as_posix())
    assert changed
    # Separate canonicalizer confirms the reference/control remains a close
    # implementation clone even after its intended coherent change.
    source_grams = _grams((source / ".meta/example.cpp").read_text(), 4)
    control_grams = _grams((control / ".meta/example.cpp").read_text(), 4)
    assert _jaccard(source_grams, control_grams) >= 0.65
    result = tasks.diversity_screen(out)["controls"][variant]
    assert set(result["duplicate_dimensions"]) == set(tasks.DIMENSIONS)


def test_tree_hash_and_owner_drift_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    target = out / tasks.specs()[0].task_id / ".docs/instructions.md"
    target.write_text(target.read_text() + "drift\n")
    with pytest.raises(tasks.CreatorError, match="generator_output_drift"):
        tasks.verify_core(out)


def test_holdout_and_cross_tree_screen_accounts_for_exact_scope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    report = tasks.contamination_screen(out)
    assert report["holdout_inventory"] == 26
    assert report["holdout_comparisons"] == 1040
    assert len(report["cross_tree"]) == 40
    assert report["status"] == "pass"


def test_output_is_deterministic_under_owner_regeneration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    first = tasks.materialize(out)["tree_hash"]
    second = tasks.materialize(out, force=True)["tree_hash"]
    assert first == second
    assert hashlib.sha256((out / ".state/manifest.json").read_bytes()).hexdigest()


def test_audit_remedies_are_generator_owned_and_history_is_append_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    audit = out / ".state/audits/cycle-01-audit.json"
    audit.parent.mkdir(parents=True)
    immutable_bytes = b'{"immutable":true,"subject":"cycle-01"}\n'
    audit.write_bytes(immutable_bytes)
    tasks.materialize(out, force=True)
    assert audit.read_bytes() == immutable_bytes
    records = sorted((out / ".state/remedy").glob("BC-AUD-*.json"))
    assert len(records) == 11
    assert {json.loads(path.read_text())["finding_id"] for path in records} == {
        row[0] for row in tasks.REMEDIATIONS
    }
    private = {
        spec.task_id: (out / spec.task_id / ".meta/private_test.cpp").read_text()
        for spec in tasks.specs()
    }
    assert "numeric_limits<std::int64_t>::min" in private["basecv-balanced-ternary-ledger"]
    assert "std::string(65,'1')" in private["basecv-base58-byte-envelope"]
    assert "1000000000039ULL" in private["basecv-residue-crt-reconstruction"]
    assert "numeric_limits<std::uint64_t>::max" in private["basecv-zeckendorf-fibonacci-code"]
    assert "quadrants_to_xy(bad)" in private["basecv-morton-interleave-radix"]


def test_write_replaces_read_only_receipt_left_by_privileged_run(tmp_path: Path) -> None:
    # A locked-image (root-in-container) run leaves receipts the host user
    # cannot open for writing; the owner must still refresh them atomically.
    target = tmp_path / ".state" / "runtime-result.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"status":"stale"}\n')
    target.chmod(0o444)
    tasks._write(target, '{"status":"fresh"}\n')
    assert target.read_text() == '{"status":"fresh"}\n'
    assert not list(target.parent.glob("*.tmp-*"))
