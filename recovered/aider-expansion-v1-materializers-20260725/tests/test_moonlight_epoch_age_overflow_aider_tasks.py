from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_epoch_age_overflow_aider_tasks as family


def test_binding_inventory_and_count_cell_are_exact() -> None:
    assert family.TASK_COUNT == 80
    assert len(family.TASKS) == 80
    assert len({task.task_id for task in family.TASKS}) == 80
    assert family.PAIR_COUNT == 3160
    assert {task.group for task in family.TASKS} == {
        "epoch-codec",
        "human-age",
        "checked-arithmetic",
        "rollover-order",
    }
    assert all(sum(task.group == group for task in family.TASKS) == 20 for group in {
        "epoch-codec", "human-age", "checked-arithmetic", "rollover-order"
    })


def test_output_owner_refuses_every_noncanonical_target(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="expansion_output_required"):
        family._safe_output(tmp_path / "aider-tasks")
    with pytest.raises(RuntimeError, match="expansion_output_required"):
        family._safe_output(family.LEGACY_ROOT / "epoch-age-overflow-boundaries")
    with pytest.raises(RuntimeError, match="expansion_output_required"):
        family._safe_output(family.REVERIFY_ROOT / "epoch-age-overflow-boundaries")


def test_rendered_roles_starters_and_negatives_are_private_and_complete() -> None:
    for task in family.TASKS:
        starter = family._header(task, starter=True)
        reference = family._header(task)
        negative = family._header(task, negative=True)
        instructions = family._instructions(task)
        assert "not implemented" in starter
        assert "not implemented" not in reference
        assert "not implemented" not in negative
        assert instructions.startswith("# Instructions\n")
        assert f"`{task.task_id}.h`" in instructions
        assert "## Examples" in instructions
        assert task.negative in instructions
        for banned in (
            "clean-room",
            "core mechanism",
            "Do not substitute",
            "hidden test",
            "oracle",
            "grader",
            "benchmark",
            "SFT",
        ):
            assert banned not in instructions, (task.task_id, banned)
        introduction = family._introduction(task)
        assert introduction.startswith(f"# {task.title}\n\n")
        assert "clean-room" not in introduction
        assert len(introduction.split("\n\n")) >= 3
        manifest = family._role_manifest(task)
        assert manifest["files"]["solution"] == [f"{task.task_id}.h"]
        assert manifest["files"]["example"] == [".meta/example.h"]
        assert not set(manifest["files"]["solution"]) & set(manifest["files"]["test"])


def test_independent_normalizer_rejects_pure_renames_and_policy_clones(tmp_path: Path) -> None:
    task = family.TASKS[0]
    left = tmp_path / "left"
    right = tmp_path / "right"
    for root in (left, right):
        (root / ".docs").mkdir(parents=True)
        (root / ".meta").mkdir(parents=True)
        (root / f"{root.name}.h").write_text(family._header(task, starter=True), encoding="utf-8")
        (root / ".meta/example.h").write_text(family._header(task), encoding="utf-8")
        (root / ".meta/negative.h").write_text(family._header(task, negative=True), encoding="utf-8")
        (root / ".meta/task_hidden_test.cpp").write_text(family._test(task, hidden=True), encoding="utf-8")
        (root / "task_visible_test.cpp").write_text(family._test(task, hidden=False), encoding="utf-8")
        (root / ".docs/instructions.md").write_text(family._instructions(task), encoding="utf-8")
        (root / ".meta/tests.toml").write_text("negative='truncating division'\n", encoding="utf-8")
        (root / ".meta/config.json").write_text(json.dumps({"files": {"solution": [f"{root.name}.h"]}}), encoding="utf-8")
    for path in right.rglob("*"):
        if path.is_file():
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "unix_day_floor_split", "unix_day_floor_split_copy"
                ),
                encoding="utf-8",
            )
    result = family._pair_decision(
        left, right, common_lineage_task_id=task.task_id
    )
    assert not result["pass"]
    assert set(result["dimensions"]) == set(family.HARD_RULE_DIMENSIONS)
    assert any(not item["pass"] for item in result["dimensions"].values())


def test_every_generated_test_is_deterministic_and_names_the_root() -> None:
    for task in family.TASKS:
        visible = family._test(task, hidden=False)
        hidden = family._test(task, hidden=True)
        assert task.task_id in visible
        assert task.task_id in hidden
        assert "rand(" not in visible + hidden
        assert "std::time(" not in visible + hidden
        assert "require(" in hidden


def _independent_features(root: Path, dimension: str) -> set[str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = root / config["files"]["solution"][0]
    scopes = {
        "public_api": [solution, root / ".docs/instructions.md"],
        "owned_state_or_algorithm": [root / ".meta/example.h"],
        "mutation_selection_rules": [root / ".meta/example.h", root / ".docs/instructions.md"],
        "invalid_boundary_behavior": [root / ".docs/instructions.md", root / "task_visible_test.cpp"],
        "reference_control_flow": [root / ".meta/example.h"],
        "deterministic_oracle": [root / "task_visible_test.cpp", root / ".meta/task_hidden_test.cpp", root / ".docs/instructions.md"],
        "topic_specific_negative_fixture": [root / ".meta/negative.h", root / ".meta/tests.toml", root / ".docs/instructions.md"],
    }
    text = "\n".join(path.read_text(encoding="utf-8") for path in scopes[dimension])
    text = text.split("} // namespace detail", 1)[-1]
    text = re.sub(r"//.*?$|/\*.*?\*/|#.*?$", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"', ' "str" ', text)
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)\b", " num ", text)
    raw = re.findall(
        r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||[-+*/%<>{}()[\],;]",
        text.lower(),
    )
    preserved = {"if", "else", "for", "while", "switch", "case", "return", "break", "continue", "true", "false", "auto", "const", "static_cast", "struct", "class", "enum", "namespace", "using", "void", "bool", "int", "long", "std", "optional", "vector", "array", "size_t", "int32_t", "int64_t", "uint16_t", "uint32_t", "uint64_t", "nullopt", "numeric_limits"}
    aliases: dict[str, str] = {}
    tokens = []
    for token in raw:
        if not re.fullmatch(r"[a-z_][a-z_0-9]*", token) or token in preserved:
            tokens.append(token)
        else:
            aliases.setdefault(token, f"id{len(aliases)}")
            tokens.append(aliases[token])
    return {" ".join(tokens[index : index + 5]) for index in range(max(1, len(tokens) - 4))}


def test_independent_complete_pair_matrix_and_controls(tmp_path: Path) -> None:
    root = tmp_path / "family"
    roots = tuple(family._materialize_root(root, task, True) for task in family.TASKS)
    assert len(roots) == 80
    decisions = []
    for left_index, left in enumerate(roots):
        for right in roots[left_index + 1 :]:
            per_dimension = {}
            for dimension in family.HARD_RULE_DIMENSIONS:
                left_features = _independent_features(left, dimension)
                right_features = _independent_features(right, dimension)
                overlap = len(left_features & right_features) / len(
                    left_features | right_features
                )
                per_dimension[dimension] = overlap < 0.95 and bool(
                    left_features ^ right_features
                )
            decisions.append(per_dimension)
    assert len(decisions) == 3160
    assert all(set(item) == set(family.HARD_RULE_DIMENSIONS) for item in decisions)
    assert all(all(item.values()) for item in decisions)

    controls = family._make_controls(root, roots)
    assert {control.name for control in controls} == set(family.CONTROL_NAMES)
    source_id = next(task.task_id for task in family.TASKS if task.operation == "floor_split")
    source = next(item for item in roots if item.name == source_id)
    for control in controls:
        record = json.loads((control / ".control.json").read_text(encoding="utf-8"))
        assert record["changed_files"]
        result = family._pair_decision(
            source, control, common_lineage_task_id=source.name
        )
        assert set(result["dimensions"]) == set(family.HARD_RULE_DIMENSIONS)
        assert all(not item["pass"] for item in result["dimensions"].values())


def test_cycle_003_replacements_preserve_intermediate_lineages() -> None:
    expected = {
        "temporal-normalize-nanos": "temporal-epoch-range-intersection",
        "temporal-nearest-era10": "temporal-era-consensus",
        "temporal-mjd-split": "temporal-leap-table-digest",
        "temporal-nano-day": "temporal-signed-duration-parts",
        "temporal-age-march1": "temporal-age-threshold-date",
    }
    assert dict(family._CYCLE_003_REPLACEMENTS) == expected
    current_ids = {task.task_id for task in family.TASKS}
    assert set(expected.values()) <= current_ids
    assert not set(expected) & current_ids


def test_remedy_ledger_hygiene_normalizes_cycle_records(tmp_path: Path) -> None:
    output = tmp_path / "family"
    remedy = output / ".state/remedy"
    cycles = output / ".state/cycles"
    remedy.mkdir(parents=True)
    cycles.mkdir(parents=True)
    (cycles / "cycle-002.json").write_text(
        json.dumps({"owner_sha256": "ab" * 32}), encoding="utf-8"
    )
    record = {
        "schema_version": "aider-task-remedy-v1",
        "cycle": 2,
        "task_id": "temporal-example",
        "disposition": "repair-and-reverify",
        "status": "remediated_pending_fresh_audit",
        "finding_ids": ["AEO-C02-F001"],
        "root_sha256": "cd" * 32,
    }
    target = remedy / "temporal-example.cycle-002.json"
    target.write_text(json.dumps(record), encoding="utf-8")
    assert family._remedy_ledger_hygiene(output) == 1
    normalized = json.loads(target.read_text(encoding="utf-8"))
    assert normalized["disposition"] == "repair-in-place"
    assert normalized["status"] == "implemented"
    assert normalized["remedy_spec_path"] == family.CURRICULUM.as_posix()
    assert normalized["remedy_spec_hash"].startswith("sha256:")
    assert normalized["tree_hash_before"] == f"sha256:{'cd' * 32}"
    assert normalized["generator_revision"] == f"sha256:{'ab' * 32}"
    assert normalized["license_screen"] == "pass"
    assert normalized["vocabulary_normalized_from"] == {
        "disposition": "repair-and-reverify",
        "status": "remediated_pending_fresh_audit",
    }


_INSTRUCTION_RULES = {
    "excel_serial": ["Serial 0 and negative serials are rejected."],
    "era_consensus": ["modulus below 2"],
    "week_seconds": ["negative week"],
    "leap_table_digest": ["empty"],
    "utc_to_tai": ["before the first transition"],
    "tai_to_utc": ["Empty or non-increasing tables"],
    "piecewise_offset": ["before the first transition"],
    "watermark": ["all-inactive"],
    "age_clamped": ["Invalid or reversed dates are rejected."],
    "age_borrowed": ["Invalid or reversed dates are rejected"],
    "birthday_nearest": ["Invalid or reversed dates are rejected."],
    "majority_epoch": ["Negative majority years"],
    "actuarial": ["Invalid or reversed dates are rejected"],
    "gestational": ["Invalid or reversed dates"],
    "age_fraction": ["Invalid or reversed dates are rejected."],
    "age_band": ["negative thresholds"],
    "age_series": ["Disordered"],
    "eligibility": ["negative minimum age"],
    "leapling_count": ["Only a valid February 29 birth date is accepted"],
    "retirement": ["Negative retirement years"],
    "sibling_gap": ["Invalid dates are rejected"],
    "completed_months": ["Invalid or reversed dates"],
    "iso_weeks": ["Invalid or reversed dates are rejected."],
    "century_birthdays": ["empty or reversed range"],
    "affine_map": ["nonpositive denominator"],
    "weighted_centroid": ["Empty samples"],
    "tolerance_dedup": ["Unsorted input is rejected."],
    "shard_key": ["Zero width"],
    "drift_envelope": ["Fewer than two samples"],
}


def test_instructions_document_every_hidden_rejection_rule() -> None:
    covered = set()
    for task in family.TASKS:
        instructions = family._instructions(task)
        for rule in _INSTRUCTION_RULES.get(task.operation, ()):
            assert rule in instructions, (task.task_id, rule)
            covered.add(task.operation)
    assert covered == set(_INSTRUCTION_RULES)


_HIDDEN_POLICY_PINS = {
    "age_clamped": ["policy->days==3"],
    "age_feb28": ["*policy == 3"],
    "birthday_nearest": ["tie->distance_days==183"],
    "exact_ratio": ["(2,3,4)", "(std::numeric_limits<std::int64_t>::max(),2,1)"],
    "filetime_split": ["116444735999999995ULL", "9999995U"],
    "reset_segments": ["{5,4,1,2,8}", "{10,8}"],
    "signed_duration_parts": ["-90061000000000LL", "neg.hours==25"],
    "step_lookup": ["(25,table)", "(5,table)"],
    "tolerance_dedup": ["{0,1,2,10}"],
    "weighted_centroid": ["1000008", "*tie==2"],
}


def test_hidden_suites_pin_core_policy_against_negative_fixture() -> None:
    covered = set()
    for task in family.TASKS:
        hidden = family._test(task, hidden=True)
        for pin in _HIDDEN_POLICY_PINS.get(task.operation, ()):
            assert pin in hidden, (task.task_id, pin)
            covered.add(task.operation)
    assert covered == set(_HIDDEN_POLICY_PINS)


_CHECKED_YEAR_OPS = {
    "actuarial",
    "leapling_count",
    "age_borrowed",
    "sibling_gap",
    "age_series",
    "age_band",
    "completed_months",
}


def test_year_arithmetic_uses_checked_subtraction() -> None:
    covered = set()
    for task in family.TASKS:
        if task.operation not in _CHECKED_YEAR_OPS:
            continue
        reference = family._header(task)
        assert "!detail::checked_sub(" in reference, task.task_id
        covered.add(task.operation)
    assert covered == _CHECKED_YEAR_OPS
