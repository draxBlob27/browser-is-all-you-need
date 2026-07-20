from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_date_difference_aider_tasks as dates


INDEPENDENT_SEMANTIC_WITNESSES = {
    "dated-warranty-audit": {
        "public_api": "class WarrantyAudit",
        "owned_state_or_algorithm": "std::set<std::string> seen",
        "mutation_selection_rules": "seen.insert(claim.id).second",
        "invalid_boundary_behavior": "coverage day zero",
        "reference_control_flow": "for (const auto& claim : claims)",
        "deterministic_oracle": "ClaimStatus::expired",
        "topic_negative_fixture": "age <= policy.coverage_days ? ClaimStatus::covered",
    },
    "dated-project-burnup": {
        "public_api": "class ProjectBurnup",
        "owned_state_or_algorithm": "for (long long day=serial(start.date)+1",
        "mutation_selection_rules": "closed.insert(serial(d)).second",
        "invalid_boundary_behavior": "half-open-to-closed elapsed interval",
        "reference_control_flow": "weekday(d)<5 && !closed.count(day)",
        "deterministic_oracle": "BurnupStatus::duplicate_holiday",
        "topic_negative_fixture": "if (weekday(d)>=0 && !closed.count(day)) ++total;",
    },
    "dated-library-loan": {
        "public_api": "class LoanReconciler",
        "owned_state_or_algorithm": "int bill=overdue>fee.free_days",
        "mutation_selection_rules": "if(!closed.count(x)) ++overdue;",
        "invalid_boundary_behavior": "first billable day",
        "reference_control_flow": "for(long long x=serial(loan.due)+1",
        "deterministic_oracle": "LoanStatus::due_before_checkout",
        "topic_negative_fixture": "++x) ++overdue;",
    },
    "dated-experiment-window": {
        "public_api": "class ObservationWindow",
        "owned_state_or_algorithm": "std::sort(v.begin(),v.end())",
        "mutation_selection_rules": "m.back().second=std::max",
        "invalid_boundary_behavior": "Every span is half-open",
        "reference_control_flow": "for(auto x:m)",
        "deterministic_oracle": "WindowStatus::invalid_span",
        "topic_negative_fixture": "if(l>r)v.push_back({l,r});",
    },
    "dated-retention-review": {
        "public_api": "class RetentionReview",
        "owned_state_or_algorithm": "std::map<std::string,RetentionPolicy> by",
        "mutation_selection_rules": "by.emplace(p.category,p).second",
        "invalid_boundary_behavior": "equality with the retention duration",
        "reference_control_flow": "for(auto r:records)",
        "deterministic_oracle": "ReviewStatus::duplicate_category",
        "topic_negative_fixture": "if(age>it->second.retention_days)",
    },
    "dated-maintenance-ledger": {
        "public_api": "class MaintenanceLedger",
        "owned_state_or_algorithm": "std::map<std::string, State> state",
        "mutation_selection_rules": "it->second.last = day; ++it->second.count",
        "invalid_boundary_behavior": "independent last-service state",
        "reference_control_flow": "if (it == state.end())",
        "deterministic_oracle": "LedgerStatus::asset_time_reversal",
        "topic_negative_fixture": "state.empty() ? state.end() : state.begin()",
    },
    "dated-subscription-proration": {
        "public_api": "class SubscriptionProrater",
        "owned_state_or_algorithm": "for (long long day=first; day<last; ++day)",
        "mutation_selection_rules": "++out.days_by_band[band]",
        "invalid_boundary_behavior": "half-open active window",
        "reference_control_flow": "while (band+1<bands.size()",
        "deterministic_oracle": "ProrationStatus::missing_initial_band",
        "topic_negative_fixture": "serial(bands[band+1].effective)>day",
    },
    "dated-custody-chain": {
        "public_api": "class CustodyChain",
        "owned_state_or_algorithm": "for (std::size_t i=1;i<transfers.size();++i)",
        "mutation_selection_rules": "out.completed.push_back",
        "invalid_boundary_behavior": "breaches only when elapsed days are strictly greater",
        "reference_control_flow": "if (elapsed<0)",
        "deterministic_oracle": "CustodyStatus::chronological_reversal",
        "topic_negative_fixture": "days>=transfers[i-1].maximum_days",
    },
}


def test_date_difference_materializes_eight_reverify_roots(tmp_path: Path) -> None:
    roots = dates.build(tmp_path)
    assert 8 <= len(roots) == len(dates.TASKS) <= 12
    assert {root.name for root in roots} == {task.task_id for task in dates.TASKS}
    assert dates.DEFAULT_OUT.parts[-2:] == ("aider-text-grid-reshaping", "date-difference")
    assert dates.LEGACY_OUT.parts[-2:] == ("aider-dates-and-clocks", "date-difference")
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"] == {
            "solution": [f"{root.name}.h", f"{root.name}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        }
        assert provenance["curriculum_task_id"] == root.name
        assert provenance["family_id"] == dates.FAMILY_ID
        assert provenance["taxonomy_mismatch_recorded"] is True
        assert (root / ".meta/negative.cpp").is_file()
        assert "WILL_FAIL TRUE" in (root / "CMakeLists.txt").read_text()


def test_legacy_root_is_immutable() -> None:
    with pytest.raises(dates.VerificationError, match="legacy_root_immutable"):
        dates.build(dates.LEGACY_OUT, force=True)


def test_remedy_records_precede_and_account_for_every_final_root(tmp_path: Path) -> None:
    dates.build(tmp_path)
    remedy = tmp_path / ".state/remedy"
    assert {path.stem for path in remedy.glob("*.json")} == {task.task_id for task in dates.TASKS}
    for task in dates.TASKS:
        record = json.loads((remedy / f"{task.task_id}.json").read_text())
        markdown = (remedy / f"{task.task_id}.md").read_text()
        assert record["disposition"] == task.disposition
        assert record["selected_prompt"] == dates.SELECTED_PROMPT
        assert record["user_inputs"]["hard_rule_count"] == "8-12"
        assert record["tree_hash_before"].startswith("sha256:")
        assert record["remedy_spec_hash"] == dates._sha256(markdown.encode())
        headings = [line for line in markdown.splitlines() if line.startswith("## ")]
        assert headings == [
            "## Identity", "## Objective", "## Public API", "## Behavior table",
            "## Implementation invariant", "## Starter and reference", "## Tests",
            "## Files and metadata", "## Build/oracle", "## Family/contamination",
            "## Optional dataset handoff", "## Acceptance",
        ]


def test_prompt_roles_family_pairs_and_bound_holdouts(tmp_path: Path) -> None:
    dates.build(tmp_path)
    screen = dates.verify_core(tmp_path)
    hard = screen["hard_rule"]
    assert screen["root_count"] == 8
    assert hard["pair_count"] == hard["expected_pair_count"] == 28
    assert hard["dimensions"] == list(dates.HARD_RULE_DIMENSIONS)
    assert hard["thresholds"] == dates.HARD_RULE_THRESHOLDS
    assert hard["minimum_symmetric_differences"] == dates.HARD_RULE_MIN_SYMMETRIC_DIFFERENCE
    assert len(hard["pairs"]) == 28
    assert screen["benchmark"]["status"] == "pass"
    assert len(screen["benchmark"]["inventory"]) == 26
    assert len(screen["benchmark"]["comparisons"]) == 8 * 26
    assert set(hard["controls"]) == set(dates.ADVERSARIAL_CONTROLS)
    assert all(item["screen"]["failure"] == "duplicate_family" for item in hard["controls"].values())
    # Independently recompute every recorded materiality decision from the
    # persisted counts rather than calling the production feature helper.
    for pair in hard["pairs"]:
        assert set(pair["dimensions"]) == set(dates.HARD_RULE_DIMENSIONS)
        assert pair["failed_dimensions"] == []
        for dimension in dates.HARD_RULE_DIMENSIONS:
            decision = pair["dimensions"][dimension]
            assert decision["left"] != decision["right"]
            assert decision["union_count"] > 0
            assert decision["jaccard_overlap"] == pytest.approx(
                decision["intersection_count"] / decision["union_count"]
            )
            assert decision["jaccard_overlap"] < dates.HARD_RULE_THRESHOLDS[dimension]
            assert decision["symmetric_difference_count"] >= dates.HARD_RULE_MIN_SYMMETRIC_DIFFERENCE[dimension]
            assert decision["left_only_witnesses"]
            assert decision["right_only_witnesses"]
            assert decision["materially_different"] is True
    for dimension in dates.HARD_RULE_DIMENSIONS:
        assert hard["observed_extrema"][dimension] == {
            "maximum_jaccard_overlap": max(pair["dimensions"][dimension]["jaccard_overlap"] for pair in hard["pairs"]),
            "minimum_symmetric_difference": min(pair["dimensions"][dimension]["symmetric_difference_count"] for pair in hard["pairs"]),
        }
    for task in dates.TASKS:
        root = tmp_path / task.task_id
        loaded = sft.load_task(root)
        answer = sft.build_assistant_response(loaded, sft.load_example_files_from_config(root))
        assert answer.startswith(f"{root.name}.h\n```")
        assert f"{root.name}.cpp\n```" in answer
        assert ".meta/" not in answer
        assert "CMakeLists" not in answer


def test_independent_semantic_witnesses_cover_all_seven_dimensions(tmp_path: Path) -> None:
    dates.build(tmp_path)
    assert set(INDEPENDENT_SEMANTIC_WITNESSES) == {task.task_id for task in dates.TASKS}
    for dimension in dates.HARD_RULE_DIMENSIONS:
        assert len({items[dimension] for items in INDEPENDENT_SEMANTIC_WITNESSES.values()}) == 8
    for task_id, witnesses in INDEPENDENT_SEMANTIC_WITNESSES.items():
        root = tmp_path / task_id
        sources = {
            "public_api": (root / f"{task_id}.h").read_text(),
            "owned_state_or_algorithm": (root / ".meta/example.cpp").read_text(),
            "mutation_selection_rules": (root / ".meta/example.cpp").read_text(),
            "invalid_boundary_behavior": (root / ".docs/instructions.md").read_text(),
            "reference_control_flow": (root / ".meta/example.cpp").read_text(),
            "deterministic_oracle": (root / "task_visible_test.cpp").read_text() + (root / ".meta/task_hidden_test.cpp").read_text(),
            "topic_negative_fixture": (root / ".meta/negative.cpp").read_text(),
        }
        for dimension, witness in witnesses.items():
            assert witness in sources[dimension], f"{task_id}:{dimension}:{witness}"


def test_topic_negatives_are_distinct_nonempty_semantic_mutations(tmp_path: Path) -> None:
    dates.build(tmp_path)
    fingerprints = set()
    for task in dates.TASKS:
        root = tmp_path / task.task_id
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative.cpp").read_text()
        assert negative != reference
        witness = INDEPENDENT_SEMANTIC_WITNESSES[task.task_id]["topic_negative_fixture"]
        assert witness in negative
        assert dates.NEGATIVE_DESCRIPTIONS[task.task_id] in (root / ".meta/tests.toml").read_text()
        delta = dates._negative_delta_features(reference, negative)
        assert delta
        fingerprints.add(tuple(sorted(delta)))
        assert "add_executable(task_negative .meta/negative.cpp task_visible_test.cpp)" in (root / "CMakeLists.txt").read_text()
    assert len(fingerprints) == 8


def test_three_coherent_controls_change_files_and_exact_evaluator_rejects(tmp_path: Path) -> None:
    dates.build(tmp_path / "family")
    source = tmp_path / "family/dated-warranty-audit"
    for variant in dates.ADVERSARIAL_CONTROLS:
        clone, mutation = dates._make_adversarial_clone(source, variant, tmp_path / "controls")
        assert mutation["changed_files"]
        assert dates._tree_hash(clone) != dates._tree_hash(source)
        config = json.loads((clone / ".meta/config.json").read_text())
        assert dates._role_failure(clone, config["files"]) is None
        result = mutation["screen"]
        assert result["failure"] == "duplicate_family"
        assert result["failed_dimensions"]
        assert any(not item["materially_different"] for item in result["dimensions"].values())


def test_root_count_roles_and_remedy_hashes_fail_closed(tmp_path: Path) -> None:
    dates.build(tmp_path)
    shutil.rmtree(tmp_path / dates.TASKS[-1].task_id)
    with pytest.raises(dates.VerificationError, match="hard_rule_root_count"):
        dates.verify_core(tmp_path)
    dates.build(tmp_path, force=True)
    first = tmp_path / dates.TASKS[0].task_id
    config_path = first / ".meta/config.json"
    config = json.loads(config_path.read_text())
    config["files"]["solution"].append("CMakeLists.txt")
    config_path.write_text(json.dumps(config))
    with pytest.raises(dates.VerificationError, match="target_reference_mismatch"):
        dates.verify_core(tmp_path)
    dates.build(tmp_path, force=True)
    remedy = tmp_path / ".state/remedy" / f"{dates.TASKS[0].task_id}.md"
    remedy.write_text(remedy.read_text() + "\nstale\n")
    with pytest.raises(dates.VerificationError, match="remedy_spec_incomplete"):
        dates.verify_core(tmp_path)


def test_wrapper_targets_reverify_owner() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_date_difference_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    text = wrapper.read_text()
    assert "moonlight_date_difference_aider_tasks" in text
    assert "aider-tasks-reverify/aider-text-grid-reshaping/date-difference" in text


def test_default_docker_receipt_binds_current_tree_when_present() -> None:
    receipt_path = dates.DEFAULT_OUT / ".state/docker-sanity.json"
    if not receipt_path.is_file():
        pytest.skip("operator Docker sanity evidence is not materialized")
    receipt = json.loads(receipt_path.read_text())
    assert receipt["schema_version"] == "date-difference-docker-sanity-v3"
    assert receipt["status"] == "pass"
    assert receipt["evidence_class"] == "docker_sanity"
    assert receipt["locked_oracle"] is False
    assert receipt["network"] == "none"
    assert set(receipt["tasks"]) == {task.task_id for task in dates.TASKS}
    assert set(receipt["hard_rule_controls"]) == set(dates.ADVERSARIAL_CONTROLS)
    assert receipt["hard_rule_binding"] == {
        "normalizer": dates.NORMALIZER,
        "root_count": 8,
        "pair_count": 28,
        "dimensions": list(dates.HARD_RULE_DIMENSIONS),
        "thresholds": dates.HARD_RULE_THRESHOLDS,
        "minimum_symmetric_differences": dates.HARD_RULE_MIN_SYMMETRIC_DIFFERENCE,
        "result": "pass",
    }
    for task in dates.TASKS:
        item = receipt["tasks"][task.task_id]
        assert item["normal"] == item["asan_ubsan"] == 3
        assert item["negative_normal"] == item["negative_asan_ubsan"] == 1
        assert item["tree_hash"] == dates._tree_hash(dates.DEFAULT_OUT / task.task_id)
        assert item["mounted_tree_hash"] == item["tree_hash"]
