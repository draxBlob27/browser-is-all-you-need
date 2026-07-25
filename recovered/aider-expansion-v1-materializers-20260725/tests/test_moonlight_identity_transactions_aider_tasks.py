from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_identity_transactions_aider_tasks import CASES, CONTROL_NAMES, FAMILY_ID, _validate_operation_contract_source, _validate_requirements, build, verify_core
from w8_biayn.integrations.moonlight_identity_transactions_contracts import OPERATION_CONTRACT_REQUIRED_FRAGMENTS, OPERATION_CONTRACTS
from w8_biayn.integrations.moonlight_identity_transactions_hard_rule import HARD_DIMENSIONS, file_hash, pair_decisions


_CPP_STRUCTURE = frozenset("class struct public private protected bool int long unsigned void auto const static explicit return if else for while true false nullptr optional vector map set deque pair string size_t".split())


def _independent_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " literal ", text)
    text = re.sub(r"\b\d+\b", " number ", text)
    tokens = re.findall(r"[a-z_][a-z_0-9]*|==|!=|<=|>=|&&|\|\||[{}()\[\];,:?+*/%<>=.!&|-]", text.lower())
    identifiers: dict[str, str] = {}
    return tuple(token if token in _CPP_STRUCTURE or not re.match(r"[a-z_]", token) else identifiers.setdefault(token, f"identifier_{len(identifiers)}") for token in tokens)


def _independent_dimensions(root: Path) -> dict[str, tuple[str, ...]]:
    header = next(root.glob("*.h")).read_text()
    reference = (root / ".meta/example.cpp").read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    scopes = {
        "public_api": header,
        "owned_state_algorithm": reference,
        "mutation_selection_rules": reference + visible,
        "invalid_boundary_behavior": reference + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + hidden,
        "topic_negative_fixture": negative,
    }
    return {name: _independent_tokens(text) for name, text in scopes.items()}


def _independent_containment(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a = {left[i:i+7] for i in range(max(0, len(left)-6))}
    b = {right[i:i+7] for i in range(max(0, len(right)-6))}
    return len(a & b) / min(len(a), len(b)) if a and b else 1.0


def test_inventory_binds_exact_count_plan_cell() -> None:
    assert len(CASES) == 60
    assert len({case.task_id for case in CASES}) == 60
    assert {group: sum(case.group == group for case in CASES) for group in {case.group for case in CASES}} == {"identity": 15, "collision": 15, "reset": 15, "transactions": 15}
    assert len({case.mechanism for case in CASES}) == 60
    assert all(case.task_id.startswith("idtx-") for case in CASES)


def test_materialization_roles_prompt_and_negative_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/identity-collision-reset-transactions"
    monkeypatch.setattr("w8_biayn.integrations.moonlight_identity_transactions_aider_tasks.EXPANSION_ROOT", out.parent.parent)
    roots = build(out)
    assert len(roots) == 60
    for case, root in zip(CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        prompt = build_prompt(load_task(root))
        assert case.task_id in prompt and ".meta/" not in prompt and "CMakeLists" not in prompt
        assert "negative_false_substitute" not in prompt
        assert (root / ".meta/example.cpp").read_text() != (root / ".meta/negative_false_substitute.cpp").read_text()
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert provenance["family_id"] == FAMILY_ID
        assert provenance["lineage"] == {"relation": "new-root", "parent": None}
        assert set(provenance["semantic_profile"]) == set(HARD_DIMENSIONS)
        requirements = json.loads((root / ".meta/requirements.json").read_text())
        instructions = (root / ".docs/instructions.md").read_text()
        assert requirements["task_id"] == case.task_id
        assert len(requirements["requirements"]) == 7
        assert case.visible in instructions
        catalog = {row["assertion_id"] for row in requirements["assertion_catalog"]}
        referenced: set[str] = set()
        for requirement in requirements["requirements"]:
            assert requirement["clause"] in instructions
            assert requirement["assertion_ids"]
            referenced.update(requirement["assertion_ids"])
        assert catalog == referenced
        for role, relative in (("visible", "task_visible_test.cpp"), ("hidden", ".meta/task_hidden_test.cpp"), ("negative", ".meta/negative_false_substitute.cpp")):
            assert requirements["assertion_artifacts"][role] == {"path": relative, "sha256": file_hash(root / relative)}


def test_independent_seven_dimension_inventory_and_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/identity-collision-reset-transactions"
    monkeypatch.setattr("w8_biayn.integrations.moonlight_identity_transactions_aider_tasks.EXPANSION_ROOT", out.parent.parent)
    roots = build(out)
    signatures = {root.name: _independent_dimensions(root) for root in roots}
    for left, right in combinations(roots, 2):
        for dimension in HARD_DIMENSIONS:
            assert _independent_containment(signatures[left.name][dimension], signatures[right.name][dimension]) < 0.90, (left.name, right.name, dimension)
    source = roots[0]
    for name in CONTROL_NAMES:
        control = out / ".state/adversarial-clone-controls" / name
        changed = [path.relative_to(control) for path in control.rglob("*") if path.is_file() and (source / path.relative_to(control)).is_file() and path.read_bytes() != (source / path.relative_to(control)).read_bytes()]
        assert changed or name == "domain-identifier-renamed"
        assert not any(pair_decisions(source, control).values())
        control_signature = _independent_dimensions(control)
        assert all(_independent_containment(signatures[source.name][dimension], control_signature[dimension]) >= 0.90 for dimension in HARD_DIMENSIONS)
    renamed = out / ".state/adversarial-clone-controls/domain-identifier-renamed"
    renamed_config = json.loads((renamed/".meta/config.json").read_text())
    assert renamed_config["files"]["solution"] == ["idtx-permit-entry-ledger.h", "idtx-permit-entry-ledger.cpp"]
    assert "normalization_aliases" not in json.loads((renamed/".meta/provenance.json").read_text())
    assert "GenerationSlotPool" not in "\n".join(path.read_text() for path in renamed.rglob("*") if path.is_file())


def test_verify_core_records_all_pair_decisions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/identity-collision-reset-transactions"
    monkeypatch.setattr("w8_biayn.integrations.moonlight_identity_transactions_aider_tasks.EXPANSION_ROOT", out.parent.parent)
    build(out)
    import w8_biayn.integrations.moonlight_identity_transactions_aider_tasks as owner
    old = owner.LEGACY_ROOT, owner.REVERIFY_ROOT, owner.HOLDOUT_ROOT
    try:
        repo = Path.cwd()
        owner.LEGACY_ROOT = repo / ".w8-biayn/data/aider-tasks"
        owner.REVERIFY_ROOT = repo / ".w8-biayn/data/aider-tasks-reverify"
        owner.HOLDOUT_ROOT = repo / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
        manifest = verify_core(out)
    finally:
        owner.LEGACY_ROOT, owner.REVERIFY_ROOT, owner.HOLDOUT_ROOT = old
    diversity = manifest["screen"]["diversity"]
    assert diversity["root_count"] == 60 and diversity["pair_count"] == 1770
    assert diversity["dimensions"] == list(HARD_DIMENSIONS)
    assert all(all(row["decisions"].values()) for row in diversity["pairs"])
    assert set(diversity["controls"]) == set(CONTROL_NAMES)


def test_owner_rejects_existing_trees_as_output() -> None:
    with pytest.raises(RuntimeError, match="unsafe_path"):
        build(Path(".w8-biayn/data/aider-tasks/idtx"))
    with pytest.raises(RuntimeError, match="unsafe_path"):
        build(Path(".w8-biayn/data/aider-tasks-reverify/idtx"))


def test_requirement_clause_and_assertion_mutations_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/identity-collision-reset-transactions"
    monkeypatch.setattr("w8_biayn.integrations.moonlight_identity_transactions_aider_tasks.EXPANSION_ROOT", out.parent.parent)
    root = build(out)[0]
    case = CASES[0]
    instructions = root / ".docs/instructions.md"
    original_instructions = instructions.read_text()
    instructions.write_text(original_instructions.replace(case.boundary.capitalize()+".", ""))
    with pytest.raises(RuntimeError, match="public_requirement_unmapped"):
        _validate_requirements(root, case)
    instructions.write_text(original_instructions)
    trace = root / ".meta/requirements.json"
    payload = json.loads(trace.read_text())
    payload["requirements"][0]["assertion_ids"] = []
    trace.write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n")
    with pytest.raises(RuntimeError, match="requirement_trace_drift"):
        _validate_requirements(root, case)


def test_savepoint_get_contract_semantic_mutations_fail_closed() -> None:
    task_id = "idtx-savepoint-stack-store"
    contract = OPERATION_CONTRACTS[task_id]
    _validate_operation_contract_source(OPERATION_CONTRACTS)
    for fragment in OPERATION_CONTRACT_REQUIRED_FRAGMENTS[task_id]:
        mutated = dict(OPERATION_CONTRACTS)
        mutated[task_id] = contract.replace(fragment, "")
        with pytest.raises(RuntimeError, match=f"operation_contract_semantics_missing: {task_id}"):
            _validate_operation_contract_source(mutated)


def _require_host_toolchain() -> None:
    import shutil
    for tool in ("cmake", "ctest", "c++"):
        if shutil.which(tool) is None:
            pytest.skip(f"host toolchain missing: {tool}")


def test_verify_host_diagnostic_subset_executes_reference_and_negative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _require_host_toolchain()
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/identity-collision-reset-transactions"
    monkeypatch.setattr("w8_biayn.integrations.moonlight_identity_transactions_aider_tasks.EXPANSION_ROOT", out.parent.parent)
    from w8_biayn.integrations.moonlight_identity_transactions_aider_tasks import verify_host
    build(out)
    receipt = verify_host(out, cases=CASES[:1])
    assert receipt["evidence_class"] == "host_verify" and receipt["status"] == "pass"
    assert receipt["row_count"] == 3 and receipt["control_count"] == 0
    rows = {(row["mode"], row["source"]): row for row in receipt["records"]}
    assert rows[("normal", ".meta/example.cpp")]["outcome"] == "reference_pass"
    assert rows[("sanitizer", ".meta/example.cpp")]["outcome"] == "reference_pass"
    negative = rows[("normal", ".meta/negative_false_substitute.cpp")]
    assert negative["outcome"] == "expected_negative_rejection" and negative["rejecting_tests"]
    assert all(row["discovered_test_count"] == 2 for row in receipt["records"])
    assert receipt["compiler"]["sha256"].startswith("sha256:") and receipt["cmake"].startswith("cmake version")
    assert not (out / ".state/host-verify.json").exists()  # diagnostic subsets never persist receipts


def test_verify_host_passing_negative_fixture_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _require_host_toolchain()
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/identity-collision-reset-transactions"
    monkeypatch.setattr("w8_biayn.integrations.moonlight_identity_transactions_aider_tasks.EXPANSION_ROOT", out.parent.parent)
    from w8_biayn.integrations.moonlight_identity_transactions_aider_tasks import verify_host
    root = build(out)[0]
    (root / ".meta/negative_false_substitute.cpp").write_text((root / ".meta/example.cpp").read_text())
    with pytest.raises(RuntimeError, match="negative_fixture_not_rejected"):
        verify_host(out, cases=CASES[:1])


def test_verify_host_stale_manifest_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _require_host_toolchain()
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/identity-collision-reset-transactions"
    monkeypatch.setattr("w8_biayn.integrations.moonlight_identity_transactions_aider_tasks.EXPANSION_ROOT", out.parent.parent)
    from w8_biayn.integrations.moonlight_identity_transactions_aider_tasks import verify_host
    build(out)
    import w8_biayn.integrations.moonlight_identity_transactions_aider_tasks as owner
    old = owner.LEGACY_ROOT, owner.REVERIFY_ROOT, owner.HOLDOUT_ROOT
    try:
        repo = Path.cwd()
        owner.LEGACY_ROOT = repo / ".w8-biayn/data/aider-tasks"
        owner.REVERIFY_ROOT = repo / ".w8-biayn/data/aider-tasks-reverify"
        owner.HOLDOUT_ROOT = repo / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
        verify_core(out)
    finally:
        owner.LEGACY_ROOT, owner.REVERIFY_ROOT, owner.HOLDOUT_ROOT = old
    instructions = out / CASES[0].task_id / ".docs/instructions.md"
    instructions.write_text(instructions.read_text() + "drift\n")
    with pytest.raises(RuntimeError, match="generator_output_drift"):
        verify_host(out)
