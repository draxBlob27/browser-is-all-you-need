from __future__ import annotations

import inspect
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_reflow_layout_expansion_aider_tasks as tasks


_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
_DOMAIN = re.compile(
    r"\b(cadence|rhythm|reflow|layout|text|line|row|word|terminal|path|comment|"
    r"paragraph|annotation|margin|glyph|query|header|region|sentence|stream)\w*\b",
    re.I,
)
_ENDPOINT = re.compile(
    r"\b(left|right|first|last|earlier|later|minimum|maximum|front|back|"
    r"ascending|descending|stable|reverse|endpoint|start|end)\w*\b",
    re.I,
)


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    expansion = tmp_path / "aider-tasks-expansion-v1"
    monkeypatch.setattr(tasks, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(tasks, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(tasks, "REVERIFY_ROOT", tmp_path / "reverify")
    monkeypatch.setattr(tasks, "HOLDOUT_ROOT", tmp_path / "holdouts")
    out = expansion / "text-grid-layout/reflow-layout"
    audit = out / ".state/audits/initial-cycle-02/audit-report.json"
    audit.parent.mkdir(parents=True)
    audit.write_text('{"decision":"repair-and-reverify"}\n')
    fresh_audit = out / ".state/audits/fresh-cycle-03/audit-report.json"
    fresh_audit.parent.mkdir(parents=True)
    fresh_audit.write_text('{"finding_id":"RFL-AUD-006"}\n')
    return out


def _independent_distance(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a, b = Counter(left), Counter(right)
    shared = sum((a & b).values())
    total = sum((a | b).values())
    return 1.0 if total == 0 else 1.0 - shared / total


def _independent_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", text)
    text = _DOMAIN.sub(" DOMAIN ", text)
    text = _ENDPOINT.sub(" ENDPOINT ", text)
    text = re.sub(
        r"\b[A-Za-z_][A-Za-z_0-9]*-(?:[A-Za-z_0-9]+-)*[A-Za-z_0-9]+\b",
        " ID ",
        text,
    )
    return tuple(
        token.lower()
        for token in re.findall(
            r"[A-Za-z_][A-Za-z_0-9]*|==|!=|&&|\|\||<=|>=|[-+*/%{}()[\];,?:=<>]",
            text,
        )
    )


def _independent_material(root: Path) -> dict[str, tuple[str, ...]]:
    header = next(root.glob("*.h")).read_text()
    docs = (root / ".docs/instructions.md").read_text()
    reference = (root / ".meta/example.cpp").read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    segments = tuple(
        part.strip()
        for part in re.split(r"(?<=[;{}])", reference)
        if part.strip()
    )
    def has_control(part: str) -> re.Match[str] | None:
        return re.search(r"\b(?:if|else|for|while|switch|return)\b", part)
    state = " ".join(part for part in segments if not has_control(part))
    control = " ".join(part for part in segments if has_control(part))
    return {
        "public_api": _independent_tokens(header + docs),
        "owned_state_algorithm": _independent_tokens(header + docs + state),
        "mutation_selection_rules": _independent_tokens(docs + reference),
        "invalid_boundary_behavior": _independent_tokens(docs + hidden),
        "reference_control_flow": _independent_tokens(control),
        "deterministic_oracle": _independent_tokens(docs + visible + hidden),
        "topic_negative_fixture": _independent_tokens(negative),
    }


def test_exact_count_unique_ids_and_expansion_only_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    roots = tasks.build(out)
    assert len(roots) == 30
    assert len({root.name for root in roots}) == 30
    assert all(root.parent == out and ".state" not in root.parts for root in roots)
    assert not tasks.LEGACY_ROOT.exists()
    assert not tasks.REVERIFY_ROOT.exists()


def test_roles_references_specs_and_negatives_are_complete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    for case, root in zip(tasks.CASES, tasks.build(out), strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [
            f"{case.task_id}.h",
            f"{case.task_id}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        assert provenance["lineage"] == "new-root"
        assert provenance["mechanism"] == case.mechanism
        if case.task_id != "reflow-stream-fragments":
            assert "static_cast<void>" in (root / f"{case.task_id}.cpp").read_text()
        assert (root / ".meta/example.cpp").read_text() != (
            root / ".meta/negative_false_substitute.cpp"
        ).read_text()
        specification = out / ".state/specifications" / f"{case.task_id}.md"
        assert specification.is_file()
        headings = [
            "## Identity", "## Objective", "## Public API", "## Behavior table",
            "## Implementation invariant", "## Starter and reference", "## Tests",
            "## Files and metadata", "## Build/oracle", "## Family/contamination",
            "## Optional dataset handoff", "## Acceptance",
        ]
        text = specification.read_text()
        assert [text.index(heading) for heading in headings] == sorted(
            text.index(heading) for heading in headings
        )
    assert {
        path.stem for path in (out / ".state/remedy").glob("RFL-AUD-*.json")
    } == {f"RFL-AUD-{number:03d}" for number in range(1, 7)}


def test_negative_mutations_are_nonempty_and_task_specific() -> None:
    mutations = set()
    for case in tasks.CASES:
        negative = tasks._negative_source(case)
        assert negative != case.reference
        assert case.negative_new in negative
        mutations.add((case.negative_old, case.negative_new))
    assert len(mutations) == 30


def test_all_435_pairs_pass_all_seven_dimensions_independently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    tasks.build(out)
    roots = sorted((out / case.task_id for case in tasks.CASES), key=lambda p: p.name)
    decisions = []
    for index, left in enumerate(roots):
        left_material = _independent_material(left)
        assert set(left_material) == set(_DIMENSIONS)
        assert left_material["owned_state_algorithm"] != left_material["reference_control_flow"]
        for right in roots[index + 1 :]:
            right_material = _independent_material(right)
            per_dimension = {}
            for dimension in _DIMENSIONS:
                distance = _independent_distance(
                    left_material[dimension], right_material[dimension]
                )
                per_dimension[dimension] = distance >= 0.08
                assert per_dimension[dimension], (left.name, right.name, dimension, distance)
            decisions.append((left.name, right.name, per_dimension))
    assert len(decisions) == 435
    assert len({(left, right) for left, right, _ in decisions}) == 435
    screen = tasks._semantic_screen(out)
    assert screen["pair_count"] == screen["expected_pair_count"] == 435
    assert tuple(screen["dimensions"]) == _DIMENSIONS


def test_controls_change_files_remain_coherent_and_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    tasks.build(out)
    base = out / tasks.CONTROL_BASE_ID
    base_material = _independent_material(base)
    manifest = json.loads(
        (out / ".state/adversarial-clone-controls/manifest.json").read_text()
    )
    assert set(manifest["controls"]) == set(tasks.CONTROL_NAMES)
    for name in tasks.CONTROL_NAMES:
        root = out / ".state/adversarial-clone-controls" / name
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [
            f"{tasks.CONTROL_BASE_ID}.h",
            f"{tasks.CONTROL_BASE_ID}.cpp",
        ]
        assert manifest["controls"][name]["changed_files"]
        material = _independent_material(root)
        for dimension in _DIMENSIONS:
            distance = _independent_distance(
                base_material[dimension], material[dimension]
            )
            assert distance < 0.08, (name, dimension, distance)
        if name == "opposite-end-selection":
            assert set(manifest["controls"][name]["changed_files"]) == {
                ".docs/instructions.md",
                ".meta/example.cpp",
                "task_visible_test.cpp",
            }
    screen = tasks._semantic_screen(out)
    for name, control in screen["controls"].items():
        assert name in tasks.CONTROL_NAMES
        assert control["changed_files"]
        assert control["production_rejected"] is True
        assert not any(
            item["materially_different"] for item in control["decisions"].values()
        )


def test_output_guard_rejects_existing_tree_outside_and_links(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    tasks._validate_output(out)
    with pytest.raises(RuntimeError, match="unsafe_path"):
        tasks._validate_output(tasks.LEGACY_ROOT / "text/family")
    with pytest.raises(RuntimeError, match="unsafe_path"):
        tasks._validate_output(tmp_path / "outside")
    tasks.EXPANSION_ROOT.mkdir(parents=True, exist_ok=True)
    linked = tasks.EXPANSION_ROOT / "linked"
    linked.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(RuntimeError, match="unsafe_path"):
        tasks._validate_output(linked / "family")


def test_docker_verifier_binds_network_sanitizers_negatives_and_mount() -> None:
    source = inspect.getsource(tasks.verify_docker)
    assert '"--network", "none"' in source
    assert "Unix Makefiles" in source
    assert "-fsanitize=address,undefined" in source
    assert "compiler.sha256" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "normal_negative_count" in source
    assert "sanitizer_negative_count" in source
    assert "normal_starter_count" in source
    assert "sanitizer_starter_count" in source
    assert "docker-execution-ledger.json" in source
    assert "execution_ledger_hash" in source
    assert "command_policy_hash" in source


def test_host_verifier_binds_toolchain_negatives_and_counts() -> None:
    source = inspect.getsource(tasks.verify_host) + inspect.getsource(
        tasks._run_host_subject
    )
    assert "Unix Makefiles" in source
    assert "-fsanitize=address,undefined" in source
    assert "negative_fixture_not_rejected" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "reference_tests_failed" in source
    assert "reference_sanitizer_failed" in source
    assert "host_toolchain_missing" in source
    assert "generator_output_drift" in source
    assert "host-verify.json" in source
    assert "reflow-layout-host-verify-v1" in source
    assert "evidence_class" in source
    assert "host_verify" in source
    matrix = inspect.getsource(tasks._host_subject_matrix)
    assert matrix.count("CONTROL_NAMES") == 1
    assert '"starter"' in matrix and '"reference"' in matrix and '"negative"' in matrix


def test_cycle_uses_the_exact_bound_receipt_grader_policy_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    tasks.build(out)
    policy_hash = "sha256:" + "a" * 64
    (out / ".state/materialization-manifest.json").write_text("{}\n")
    (out / ".state/docker-sanity.json").write_text(
        json.dumps({"grader_policy_hash": policy_hash}) + "\n"
    )
    cycle = tasks._append_cycle(out, "remediated_creator_preflight")
    record = json.loads(cycle.read_text())
    assert record["grader_policy_hash"] == policy_hash
    assert record["docker_receipt"]["grader_policy_hash"] == policy_hash


def test_curriculum_binds_count_pair_gate_output_and_nonclaims() -> None:
    curriculum = tasks.CURRICULUM.read_text()
    assert "exactly\n30 new roots" in curriculum
    assert "435" in curriculum
    assert ".w8-biayn/data/aider-tasks-expansion-v1/" in curriculum
    assert "local_family_verified" in curriculum
    assert "does not authorize JSONL" in curriculum
