"""No-spend tests for the primary reviewed Aider-style C++ SFT pipeline."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from w8_biayn.aider_sft.benchmark import EXPECTED_CPP_TASK_IDS, load_benchmark_manifest
from w8_biayn.aider_sft.config import (
    GLM_REPOSITORY,
    GLM_REVISION,
    SOURCE_ONLY_DATASET_PROFILE,
    inspect_container_compiler,
    inspect_local_identity,
    load_config,
    profile_contract,
)
from w8_biayn.aider_sft.contamination import (
    final_screen_policy_fingerprint,
    final_screen_rows,
)
from w8_biayn.aider_sft.errors import AiderSftError
from w8_biayn.aider_sft.handoff import validate_slime_args
from w8_biayn.aider_sft.inventory import (
    CONCEPT_SLUGS,
    EXPECTED_SOURCE_SLUGS,
    PRACTICE_SLUGS,
    build_inventory_proposal,
)
from w8_biayn.aider_sft.llm_curator import _call_stage, _check_budget, capacity_report
from w8_biayn.aider_sft.oracle import (
    _docker_prefix,
    _oracle_input_tree_sha256,
    _require_discovery,
)
from w8_biayn.aider_sft import pipeline as aider_sft_pipeline
from w8_biayn.aider_sft import tokenization as aider_sft_tokenization
from w8_biayn.aider_sft.pipeline import _invalidate_frozen_split
from w8_biayn.aider_sft.renderer import (
    FORMAT_CONTRACT,
    PRESERVATION_REMINDER,
    parse_target,
    render_prompt,
    render_target,
    renderer_policy_fingerprint,
)
from w8_biayn.aider_sft import runtime_assets
from w8_biayn.aider_sft.review import (
    export_review_package,
    import_review_decisions,
    register_subject,
    state_root,
)
from w8_biayn.aider_sft.scaffold import GeneratedFile
from w8_biayn.aider_sft.schema import (
    CandidateState,
    Decision,
    PrimaryCategory,
    ReviewScope,
    SourceManifest,
    reason_outcome,
)
from w8_biayn.aider_sft.source_exercism import (
    canonicalize_exercism_task,
    load_canonical_task,
)
from w8_biayn.aider_sft.split import _validate_release_constraints
from w8_biayn.aider_sft.taxonomy import (
    CATEGORY_SLUGS,
    source_cell_counts,
    source_split,
)
from w8_biayn.aider_sft.tokenization import (
    attach_token_record,
    compute_token_record,
    load_locked_tokenizer,
)
from w8_biayn.aider_sft.util import (
    manifest_entries,
    read_json,
    sha256_bytes,
    verify_manifest_entries,
    write_json,
    write_jsonl,
)
from w8_biayn.cli import app
from w8_biayn.constants import (
    AIDER_PIN,
    AIDER_POLYGLOT_PIN,
    EXERCISM_CPP_PIN,
    SLIME_PIN,
)

ROOT = Path(__file__).resolve().parents[1]


def test_reason_codes_have_stable_outcomes() -> None:
    assert reason_outcome("profile_not_frozen") == "incomplete"
    assert reason_outcome("benchmark_content_overlap") == "rejected_content"
    assert reason_outcome("consumer_model_revision_mismatch") == "consumer_preflight_failure"
    assert reason_outcome("llm_transport_failed") == "retryable_error"
    assert reason_outcome("not-a-code") == "failed"


def test_frozen_inventory_and_benchmark_counts() -> None:
    assert len(EXPECTED_SOURCE_SLUGS) == 75
    assert len(PRACTICE_SLUGS) == 60
    assert len(CONCEPT_SLUGS) == 15
    assert len(EXPECTED_CPP_TASK_IDS) == 26
    assert not EXPECTED_SOURCE_SLUGS & EXPECTED_CPP_TASK_IDS

    rows = []
    for category, slugs in CATEGORY_SLUGS.items():
        for slug in slugs:
            rows.append(
                {
                    "primary_category": category.value,
                    "intended_split": source_split(slug, category).value,
                    "enabled": True,
                }
            )
    counts = source_cell_counts(rows)
    assert counts[PrimaryCategory.ALGORITHMS.value] == {
        "test": 1,
        "train": 11,
        "validation": 2,
    }
    assert counts[PrimaryCategory.TIME.value] == {
        "test": 1,
        "train": 2,
        "validation": 2,
    }
    assert sum(sum(cell.values()) for cell in counts.values()) == 75
    assert sum(16 - sum(cell.values()) for cell in counts.values()) == 21


def test_pinned_upstream_and_benchmark_identities() -> None:
    assert EXERCISM_CPP_PIN == "d2babb2bd750c884abf86ce52dde274ae7de9749"
    assert AIDER_PIN == "5dc9490bb35f9729ef2c95d00a19ccd30c26339c"
    assert AIDER_POLYGLOT_PIN == "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f"
    assert SLIME_PIN == "a897e1f40357fdf3b148f1eb4ce26e1aeccfcd2c"
    manifest = load_benchmark_manifest(ROOT)
    assert manifest["revision"] == AIDER_POLYGLOT_PIN
    assert set(manifest["task_ids"]) == EXPECTED_CPP_TASK_IDS


def test_draft_profile_is_strict_and_explicitly_not_frozen(tmp_path: Path) -> None:
    config_path = ROOT / "configs/aider_sft/pilot-v1.toml"
    config = load_config(config_path)
    assert config.dataset.freeze_status == "draft"
    assert config.tokenizer.repository == GLM_REPOSITORY
    assert config.tokenizer.revision == GLM_REVISION
    assert inspect_local_identity(config, ROOT)["compiler"]["path"] == ""
    invalid = tmp_path / "invalid.toml"
    invalid.write_text(config_path.read_text(encoding="utf-8") + "\nunknown = true\n")
    with pytest.raises(AiderSftError, match="profile_not_frozen"):
        load_config(invalid)


def test_source_only_profile_is_exactly_75_0_0_and_has_no_llm() -> None:
    config = load_config(ROOT / "configs/aider_sft/source-only-75-v1.toml")
    contract = profile_contract(config.dataset.profile)
    assert config.dataset.profile == SOURCE_ONLY_DATASET_PROFILE
    assert config.dataset.freeze_status == "frozen"
    assert config.llm is None
    assert config.tokenizer.load_kwargs == {"fix_mistral_regex": True}
    assert config.tokenizer.apply_chat_template_kwargs == {"enable_thinking": False}
    assert contract.total_targets == {"train": 75, "validation": 0, "test": 0}
    assert contract.total_roots == 75
    assert contract.llm_enabled is False
    assert contract.minimum_llm_assisted == 0


def test_compiler_identity_is_read_from_the_locked_grader_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        if "sha256sum" in argv:
            return SimpleNamespace(
                returncode=0,
                stdout=f"{'a' * 64}  /usr/local/bin/g++\n",
                stderr="",
            )
        return SimpleNamespace(
            returncode=0,
            stdout="g++ (GCC) 13.4.0\nfull version evidence\n",
            stderr="",
        )

    monkeypatch.setattr("w8_biayn.aider_sft.config.subprocess.run", fake_run)
    observed = inspect_container_compiler(
        image="grader@sha256:unit",
        cxx_path="/usr/local/bin/g++",
        docker_available=True,
    )
    assert observed == {
        "path": "/usr/local/bin/g++",
        "exists": True,
        "sha256": "a" * 64,
        "version": "g++ (GCC) 13.4.0\nfull version evidence",
        "source": "docker_image",
        "error": "",
    }
    assert len(calls) == 2
    assert all("--network" in call and "none" in call for call in calls)
    assert all("--read-only" in call and "--cap-drop" in call for call in calls)
    assert calls[0][calls[0].index("--entrypoint") + 1] == "/usr/local/bin/g++"


def test_prepare_seccomp_download_is_hash_pinned_and_reusable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b'{"defaultAction":"SCMP_ACT_ERRNO","syscalls":[]}'
    expected = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(runtime_assets, "MOBY_SECCOMP_PROFILE_SHA256", expected)
    monkeypatch.setattr(
        runtime_assets.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: io.BytesIO(payload),
    )
    output = tmp_path / "seccomp.json"
    created = runtime_assets.prepare_seccomp_profile(output_path=output)
    reused = runtime_assets.prepare_seccomp_profile(output_path=output)
    assert created["sha256"] == expected
    assert created["reused"] is False
    assert reused["reused"] is True
    assert output.read_bytes() == payload


def test_source_only_release_constraints_reject_non_source_or_eval_roots() -> None:
    tasks = [
        {
            "source_kind": "exercism",
            "split": "train",
            "primary_category": PrimaryCategory.ALGORITHMS.value,
        }
        for _ in range(75)
    ]
    report = {
        "tasks": tasks,
        "counts": {
            "total": 75,
            "by_split": {"train": 75},
            "by_source_kind": {"exercism": 75},
            "by_cell": {
                category.value: {"train": 0, "validation": 0, "test": 0}
                for category in PrimaryCategory
            },
        },
    }
    _validate_release_constraints(report, profile=SOURCE_ONLY_DATASET_PROFILE)
    report["tasks"][0]["source_kind"] = "llm_assisted"
    report["counts"]["by_source_kind"] = {"exercism": 74, "llm_assisted": 1}
    with pytest.raises(AiderSftError, match="category_quota_unsatisfied"):
        _validate_release_constraints(report, profile=SOURCE_ONLY_DATASET_PROFILE)


def test_source_only_build_never_enters_llm_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source-only"
    canonical = root / "private/canonical-tasks"
    for index in range(75):
        (canonical / f"task-{index:02d}").mkdir(parents=True)
    config_lock = {
        "config": {
            "dataset": {
                "profile": SOURCE_ONLY_DATASET_PROFILE,
            }
        }
    }
    source_manifest = object()
    report = {
        "schema_version": "aider-sft-admitted-pool-report-v1",
        "tasks": [],
        "counts": {
            "total": 75,
            "by_split": {"train": 75},
            "by_source_kind": {"exercism": 75},
            "by_cell": {},
        },
        "deficit_cells": {},
        "pool_fingerprint": "a" * 64,
    }
    monkeypatch.setattr(
        aider_sft_pipeline,
        "_prepare_build_root",
        lambda **_kwargs: (config_lock, source_manifest),
    )
    monkeypatch.setattr(
        aider_sft_pipeline,
        "_process_sources",
        lambda **_kwargs: {"admitted": 75, "rejected": 0, "awaiting_review": 0},
    )
    monkeypatch.setattr(aider_sft_pipeline, "_aggregate_ledgers", lambda _root: None)
    monkeypatch.setattr(aider_sft_pipeline, "_load_candidate_records", lambda _root: [])
    monkeypatch.setattr(
        aider_sft_pipeline,
        "admitted_pool_report",
        lambda **_kwargs: report,
    )
    monkeypatch.setattr(
        aider_sft_pipeline,
        "propose_split",
        lambda **_kwargs: {
            "subject": {"subject_fingerprint": "b" * 64},
        },
    )

    def unexpected_llm_call(**_kwargs: object) -> dict[str, int]:
        pytest.fail("source-only profile entered the LLM generation path")

    monkeypatch.setattr(
        aider_sft_pipeline,
        "_generate_missing_candidates",
        unexpected_llm_call,
    )
    result = aider_sft_pipeline.build_dataset(
        config_path=tmp_path / "unused.toml",
        output_root=root,
        repo_root=ROOT,
        resume=True,
        acknowledge_paid_llm_calls=False,
    )
    assert result["status"] == "awaiting_split_review"
    assert result["admitted"] == 75
    assert read_json(root / "reports/capacity-summary.json")["llm_enabled"] is False


def test_source_only_all_rejected_returns_structured_shortfall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source-only-shortfall"
    config_lock = {
        "config": {
            "dataset": {
                "profile": SOURCE_ONLY_DATASET_PROFILE,
            }
        }
    }
    report = {
        "schema_version": "aider-sft-admitted-pool-report-v1",
        "tasks": [],
        "counts": {
            "total": 0,
            "by_split": {},
            "by_source_kind": {},
            "by_cell": {},
        },
        "deficit_cells": {
            PrimaryCategory.ALGORITHMS.value: {
                "train": 75,
                "validation": 0,
                "test": 0,
            }
        },
        "pool_fingerprint": "a" * 64,
    }
    monkeypatch.setattr(
        aider_sft_pipeline,
        "_prepare_build_root",
        lambda **_kwargs: (config_lock, object()),
    )
    monkeypatch.setattr(
        aider_sft_pipeline,
        "_process_sources",
        lambda **_kwargs: {"admitted": 0, "rejected": 75, "awaiting_review": 0},
    )
    monkeypatch.setattr(aider_sft_pipeline, "_aggregate_ledgers", lambda _root: None)
    monkeypatch.setattr(aider_sft_pipeline, "_load_candidate_records", lambda _root: [])
    monkeypatch.setattr(
        aider_sft_pipeline,
        "admitted_pool_report",
        lambda **_kwargs: report,
    )

    result = aider_sft_pipeline.build_dataset(
        config_path=tmp_path / "unused.toml",
        output_root=root,
        repo_root=ROOT,
        resume=True,
        acknowledge_paid_llm_calls=False,
    )

    assert result["status"] == "incomplete"
    assert result["reason_code"] == "source_only_shortfall"
    assert result["admitted"] == 0
    assert read_json(root / "reports/capacity-summary.json")["source_root_shortfall"] == 75


def test_cli_exposes_the_complete_operator_loop() -> None:
    result = CliRunner().invoke(app, ["data", "aider-sft", "--help"])
    assert result.exit_code == 0
    for command in (
        "plan",
        "inventory",
        "prepare-tokenizer",
        "prepare-seccomp",
        "inventory-promote",
        "build",
        "review-export",
        "review-import",
        "finalize",
        "verify",
        "export",
        "verify-export",
    ):
        assert command in result.stdout


def test_strict_whole_target_parser_accepts_only_exact_sorted_files() -> None:
    assert "Aider whole edit format" in FORMAT_CONTRACT
    assert "exact relative filename" in FORMAT_CONTRACT
    assert "C++17" in PRESERVATION_REMINDER
    assert len(FORMAT_CONTRACT) + len(PRESERVATION_REMINDER) <= 384
    target = "a.cpp\n```cpp\nint answer() { return 42; }\n```\n\nb.h\n```cpp\n#pragma once\n```\n"
    assert parse_target(target, expected_files=["a.cpp", "b.h"]) == {
        "a.cpp": "int answer() { return 42; }\n",
        "b.h": "#pragma once\n",
    }
    with pytest.raises(AiderSftError, match="whole_format_failed"):
        parse_target(target + "explanation\n", expected_files=["a.cpp", "b.h"])
    with pytest.raises(AiderSftError, match="unsafe_path"):
        parse_target(target.replace("a.cpp", "../a.cpp", 1))


def test_final_screen_matches_whole_slugs_not_compound_source_ids() -> None:
    compound = {"messages": [{"content": "source task: simple-linked-list"}]}
    result = final_screen_rows(rows=[compound], benchmark_task_ids={"linked-list"})
    assert result["benchmark_id_mentions"] == 0

    exact = {"messages": [{"content": "source task: linked-list"}]}
    with pytest.raises(AiderSftError, match="linked-list"):
        final_screen_rows(rows=[exact], benchmark_task_ids={"linked-list"})


@pytest.mark.parametrize("path", ["CMakeLists.txt", "build.sh", "nested/Makefile"])
def test_generated_tasks_cannot_supply_build_metadata(path: str) -> None:
    with pytest.raises(ValidationError):
        GeneratedFile(path=path, content="int x;\n")


def test_generated_files_reject_commands_dependencies_and_fence_ambiguity() -> None:
    with pytest.raises(ValidationError):
        GeneratedFile(path="answer.cpp", content='int x = std::system("curl x");\n')
    with pytest.raises(AiderSftError, match="whole_format_failed"):
        GeneratedFile(path="answer.cpp", content="```cpp\nint x;\n```\n")


def _consumer_lock(sequence_length: int = 4096) -> dict:
    return {
        "schema_version": "aider-sft-consumer-lock-v1",
        "model": {"repository": GLM_REPOSITORY, "revision": GLM_REVISION},
        "tokenizer": {
            "repository": GLM_REPOSITORY,
            "revision": GLM_REVISION,
            "chat_template_sha256": "a" * 64,
            "load_kwargs": {"fix_mistral_regex": True},
            "local_path": "",
        },
        "apply_chat_template_kwargs": {"enable_thinking": False},
        "template_policy": "final_answer_only_thinking_disabled",
        "adapter": "w8-aider-sft-mask-v1",
        "loss_mask_type": "qwen",
        "sequence_length": sequence_length,
        "message_mode": "raw_messages",
        "dataset_apply_chat_template": False,
        "rollout_function": "w8_biayn.aider_sft.handoff.generate_sft_rollout",
        "input_key": "messages",
        "metadata_key": "metadata",
        "loss_type": "sft_loss",
    }


class _FakeMask:
    def get_loss_mask(self, messages: list[dict]) -> tuple[list[int], list[int]]:
        enabled = int(messages[1]["step_loss_mask"])
        return [101, 102, 103, 104], [0, 0, enabled, enabled]


def test_token_evidence_forwards_policy_and_is_assistant_only() -> None:
    row = {
        "schema_version": "aider-sft-row-v1",
        "task_id": "unit-task",
        "label": "unit-task",
        "messages": [
            {"role": "user", "content": "prompt", "step_loss_mask": 0},
            {"role": "assistant", "content": "answer", "step_loss_mask": 1},
        ],
        "metadata": {},
    }
    seen = {}

    def factory(tokenizer: object, mask_type: str) -> _FakeMask:
        seen["tokenizer"] = tokenizer
        seen["mask_type"] = mask_type
        return _FakeMask()

    record = compute_token_record(
        row,
        consumer_lock=_consumer_lock(),
        tokenizer=object(),
        mask_generator_factory=factory,
    )
    assert seen["mask_type"] == "qwen"
    assert record["token_counts"] == {
        "total": 4,
        "prompt": 2,
        "assistant": 2,
        "loss_bearing": 2,
    }
    assert record["response_length"] == 2
    updated = attach_token_record(row, record)
    assert updated["metadata"]["rendered_token_sha256"] == record["rendered_token_sha256"]
    with pytest.raises(AiderSftError, match="token_overflow"):
        compute_token_record(
            row,
            consumer_lock=_consumer_lock(sequence_length=3),
            tokenizer=object(),
            mask_generator_factory=factory,
        )


def test_missing_tokenizer_path_never_falls_back_to_current_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("W8_AIDER_SFT_TOKENIZER_PATH", raising=False)
    with pytest.raises(AiderSftError) as caught:
        load_locked_tokenizer(_consumer_lock())
    assert caught.value.reason_code == "consumer_tokenizer_mismatch"


def _slime_args(**overrides: object) -> SimpleNamespace:
    values = {
        "apply_chat_template": False,
        "loss_mask_type": "qwen",
        "apply_chat_template_kwargs": {"enable_thinking": False},
        "input_key": "messages",
        "metadata_key": "metadata",
        "seq_length": 4096,
        "loss_type": "sft_loss",
        "rollout_function_path": "w8_biayn.aider_sft.handoff.generate_sft_rollout",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_slime_handoff_rejects_template_sequence_and_adapter_drift() -> None:
    assert validate_slime_args(_slime_args()) == {"enable_thinking": False}
    for args, reason in (
        (_slime_args(apply_chat_template=True), "consumer_raw_messages_required"),
        (_slime_args(seq_length=2048), "consumer_sequence_length_mismatch"),
        (_slime_args(loss_mask_type="other"), "consumer_loss_mask_mismatch"),
        (_slime_args(rollout_function_path="slime.stock"), "consumer_adapter_mismatch"),
    ):
        with pytest.raises(AiderSftError) as caught:
            validate_slime_args(args)
        assert caught.value.reason_code == reason


def test_manifest_records_role_schema_rows_and_exact_exclusions(tmp_path: Path) -> None:
    (tmp_path / "sft").mkdir()
    write_jsonl(
        tmp_path / "sft/train.jsonl",
        [{"schema_version": "aider-sft-row-v1", "task_id": "one"}],
    )
    (tmp_path / "DATASET_CARD.md").write_text("# card\n", encoding="utf-8")
    entries = manifest_entries(tmp_path)
    by_path = {entry["path"]: entry for entry in entries}
    assert by_path["sft/train.jsonl"]["role"] == "training_rows"
    assert by_path["sft/train.jsonl"]["schema_version"] == "aider-sft-row-v1"
    assert by_path["sft/train.jsonl"]["rows"] == 1
    assert by_path["DATASET_CARD.md"]["schema_version"] == "not_applicable"
    write_json(tmp_path / "manifest.json", {"entries": entries})
    verify_manifest_entries(tmp_path, entries)
    (tmp_path / "DATASET_CARD.md").write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(AiderSftError, match="consumer_export_manifest_mismatch"):
        verify_manifest_entries(tmp_path, entries)


def test_seccomp_profile_is_hash_bound_and_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = tmp_path / "seccomp.json"
    profile.write_text('{"defaultAction":"SCMP_ACT_ERRNO"}\n', encoding="utf-8")
    sandbox = {
        "network": "none",
        "read_only_rootfs": True,
        "run_as_non_root": True,
        "no_new_privileges": True,
        "cap_drop": ["ALL"],
        "mount_policy": "single-rw-scratch-no-host-secrets-v1",
        "seccomp_profile_sha256": sha256_bytes(profile.read_bytes()),
        "cpus": 2,
        "memory_mib": 2048,
        "pids": 256,
        "file_size_mib": 64,
    }
    grader = {
        "sandbox": sandbox,
        "limits": {"cpus": 2, "memory_mib": 2048, "pids": 256, "file_size_mib": 64},
        "image": "unit-image",
    }
    monkeypatch.delenv("W8_AIDER_SFT_SECCOMP_PROFILE", raising=False)
    with pytest.raises(AiderSftError, match="sandbox_policy_mismatch"):
        _docker_prefix(
            mount_parent=tmp_path,
            workdir_name="task",
            task_grader=grader,
            environment={"LC_ALL": "C", "TZ": "UTC"},
        )
    monkeypatch.setenv("W8_AIDER_SFT_SECCOMP_PROFILE", str(profile))
    command = _docker_prefix(
        mount_parent=tmp_path,
        workdir_name="task",
        task_grader=grader,
        environment={"LC_ALL": "C", "TZ": "UTC"},
    )
    assert ["--network", "none"] == command[
        command.index("--network") : command.index("--network") + 2
    ]
    assert "fsize=67108864:67108864" in command
    assert f"seccomp={profile.resolve()}" in command


@pytest.mark.parametrize("returncode", [0, 6])
def test_catch_discovery_accepts_zero_or_exact_count(returncode: int) -> None:
    receipt = {
        "timeout": False,
        "returncode": returncode,
        "stdout": {"tail": "6 test cases\n"},
        "stderr": {"tail": ""},
    }
    assert _require_discovery(receipt, "test_discovery_failed") == 6


def test_catch_discovery_rejects_a_mismatched_nonzero_exit() -> None:
    receipt = {
        "timeout": False,
        "returncode": 2,
        "stdout": {"tail": "6 test cases\n"},
        "stderr": {"tail": ""},
    }
    with pytest.raises(AiderSftError, match="returned 2, discovered 6"):
        _require_discovery(receipt, "test_discovery_failed")


def test_oracle_input_tree_hashes_bytes_and_excludes_receipts(tmp_path: Path) -> None:
    task_root = tmp_path / "task"
    (task_root / "workspace").mkdir(parents=True)
    (task_root / "workspace/source.cpp").write_bytes(b"int answer = 1;\n")
    (task_root / "receipts").mkdir()
    receipt = task_root / "receipts/debug.json"
    receipt.write_text('{"attempt":1}\n', encoding="utf-8")
    original = _oracle_input_tree_sha256(task_root)

    receipt.write_text('{"attempt":2}\n', encoding="utf-8")
    assert _oracle_input_tree_sha256(task_root) == original

    (task_root / "workspace/source.cpp").write_bytes(b"int answer = 2;\n")
    assert _oracle_input_tree_sha256(task_root) != original


def test_source_admission_retries_records_from_an_old_implementation() -> None:
    entry = SimpleNamespace(model_dump=lambda **_kwargs: {"slug": "unit"})
    current = aider_sft_pipeline._source_input_fingerprint(entry)
    record = {
        "state": CandidateState.REJECTED_CONTENT.value,
        "input_fingerprint": current,
    }
    assert aider_sft_pipeline._source_terminal_record_is_current(record, entry)
    record.update(
        {
            "reason_code": "final_screen_invalidated_split",
            "late_failure_reason_code": "profile_not_frozen",
        }
    )
    assert not aider_sft_pipeline._source_terminal_record_is_current(record, entry)
    record["late_failure_reason_code"] = "token_overflow"
    assert not aider_sft_pipeline._source_terminal_record_is_current(record, entry)
    record["late_failure_renderer_fingerprint"] = renderer_policy_fingerprint()
    assert not aider_sft_pipeline._source_terminal_record_is_current(record, entry)
    record["late_failure_final_screen_fingerprint"] = final_screen_policy_fingerprint()
    assert aider_sft_pipeline._source_terminal_record_is_current(record, entry)
    record["input_fingerprint"] = "a" * 64
    assert not aider_sft_pipeline._source_terminal_record_is_current(record, entry)


def _review_lock() -> dict:
    return {
        "config": {
            "review": {
                "authorized_reviewers": {
                    scope.value: ["reviewer@example.test"] for scope in ReviewScope
                },
                "authoring_identities": ["author@example.test"],
            }
        }
    }


def test_review_import_is_authorized_fingerprint_bound_and_non_overwriting(
    tmp_path: Path,
) -> None:
    subject = register_subject(
        tmp_path / "dataset",
        scope=ReviewScope.SOURCE_INVENTORY,
        subject_id="inventory",
        payload={"sha256": "a" * 64},
    )
    decision = {
        "schema_version": "aider-sft-review-decision-v1",
        "scope": ReviewScope.SOURCE_INVENTORY.value,
        "subject_id": "inventory",
        "subject_fingerprint": subject["subject_fingerprint"],
        "decision": Decision.APPROVE.value,
        "reason_code": "approved",
        "reviewer": "reviewer@example.test",
        "timestamp_utc": "2026-07-14T00:00:00Z",
        "comment": "",
    }
    decisions = tmp_path / "decisions.jsonl"
    write_jsonl(decisions, [decision])
    result = import_review_decisions(tmp_path / "dataset", decisions, config_lock=_review_lock())
    assert result["approvals"] == 1
    with pytest.raises(AiderSftError, match="human_review_stale"):
        import_review_decisions(tmp_path / "dataset", decisions, config_lock=_review_lock())
    replacement = register_subject(
        tmp_path / "dataset",
        scope=ReviewScope.SOURCE_INVENTORY,
        subject_id="inventory",
        payload={"sha256": "b" * 64},
    )
    replacement_decision = {
        **decision,
        "subject_fingerprint": replacement["subject_fingerprint"],
        "timestamp_utc": "2026-07-14T01:00:00Z",
    }
    replacement_path = tmp_path / "replacement.jsonl"
    write_jsonl(replacement_path, [replacement_decision])
    replaced = import_review_decisions(
        tmp_path / "dataset", replacement_path, config_lock=_review_lock()
    )
    assert replaced["total"] == 2

    export_root = tmp_path / "review-export"
    export_root.mkdir()
    sentinel = export_root / "keep.txt"
    sentinel.write_text("keep\n", encoding="utf-8")
    with pytest.raises(AiderSftError, match="destination is not empty"):
        export_review_package(tmp_path / "dataset", export_root)
    assert sentinel.read_text(encoding="utf-8") == "keep\n"


def test_late_gate_failure_invalidates_split_and_preserves_candidate_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "dataset"
    canonical = root / "private/canonical-tasks/unit-task"
    canonical.mkdir(parents=True)
    (canonical / "task.json").write_text("{}\n", encoding="utf-8")
    staging = root / "private/candidates/source-unit/canonical/unit-task"
    staging.mkdir(parents=True)
    (staging / "evidence.txt").write_text("preserved\n", encoding="utf-8")
    terminal = state_root(root) / "journals/source-unit/terminal.json"
    write_json(
        terminal,
        {
            "schema_version": "aider-sft-admission-record-v1",
            "candidate_id": "source-unit",
            "task_id": "unit-task",
            "source_kind": "exercism",
            "state": CandidateState.ADMITTED.value,
            "reason_code": None,
            "input_fingerprint": "a" * 64,
            "receipt_fingerprints": {},
            "intended_split": "train",
            "primary_category": PrimaryCategory.ALGORITHMS.value,
        },
    )
    write_json(root / "split-manifest.json", {"tasks": []})
    write_jsonl(root / "sft/train.jsonl", [{"task_id": "unit-task"}])
    write_jsonl(root / "eval/validation.jsonl", [{"task_id": "unit-eval"}])
    register_subject(
        root,
        scope=ReviewScope.FINAL_SPLIT,
        subject_id="pilot-v1-final-split",
        payload={"split": "old"},
    )
    register_subject(
        root,
        scope=ReviewScope.DATASET_RELEASE,
        subject_id="pilot-v1-dataset-release",
        payload={"release": "old"},
    )

    result = _invalidate_frozen_split(
        root=root,
        task_id="unit-task",
        failure=AiderSftError("token_overflow", "rendered sequence is too long"),
    )

    assert result["reason_code"] == "final_screen_invalidated_split"
    assert result["late_failure_reason_code"] == "token_overflow"
    assert not canonical.exists()
    assert staging.is_dir()
    assert not (root / "split-manifest.json").exists()
    assert not (root / "sft/train.jsonl").exists()
    updated = read_json(terminal)
    assert updated["state"] == CandidateState.REJECTED_CONTENT.value
    assert updated["reason_code"] == "final_screen_invalidated_split"
    assert updated["late_failure_reason_code"] == "token_overflow"
    assert updated["late_failure_renderer_fingerprint"] == renderer_policy_fingerprint()
    assert updated["late_failure_final_screen_fingerprint"] == final_screen_policy_fingerprint()
    assert read_json(state_root(root) / "run-state.json")["dataset_state"] == "pool_filling"
    assert not (state_root(root) / "review-subjects/final_split/pilot-v1-final-split.json").exists()
    assert not (
        state_root(root) / "review-subjects/dataset_release/pilot-v1-dataset-release.json"
    ).exists()


def test_run_level_late_failure_does_not_reject_an_admitted_task(tmp_path: Path) -> None:
    root = tmp_path / "dataset"
    canonical = root / "private/canonical-tasks/unit-task"
    canonical.mkdir(parents=True)
    terminal = state_root(root) / "journals/source-unit/terminal.json"
    write_json(
        terminal,
        {
            "schema_version": "aider-sft-admission-record-v1",
            "candidate_id": "source-unit",
            "task_id": "unit-task",
            "source_kind": "exercism",
            "state": CandidateState.ADMITTED.value,
            "reason_code": None,
            "input_fingerprint": "a" * 64,
            "receipt_fingerprints": {},
            "intended_split": "train",
            "primary_category": PrimaryCategory.ALGORITHMS.value,
        },
    )
    write_json(root / "split-manifest.json", {"tasks": []})

    with pytest.raises(AiderSftError) as caught:
        _invalidate_frozen_split(
            root=root,
            task_id="unit-task",
            failure=AiderSftError("profile_not_frozen", "SLIME checkout is unavailable"),
        )

    assert caught.value.reason_code == "profile_not_frozen"
    assert canonical.is_dir()
    assert (root / "split-manifest.json").is_file()
    assert read_json(terminal)["state"] == CandidateState.ADMITTED.value


def test_mask_generator_loads_the_clean_pinned_checkout_without_pythonpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout = tmp_path / "slime"
    mask_utils = checkout / "slime/utils/mask_utils.py"
    mask_utils.parent.mkdir(parents=True)
    mask_utils.write_text(
        "class MultiTurnLossMaskGenerator:\n"
        "    def __init__(self, tokenizer, tokenizer_type='qwen'):\n"
        "        self.tokenizer = tokenizer\n"
        "        self.tokenizer_type = tokenizer_type\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SLIME_ROOT", str(checkout))

    def fake_run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
        if argv[-2:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout=f"{SLIME_PIN}\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(aider_sft_tokenization.subprocess, "run", fake_run)
    generator = aider_sft_tokenization._slime_mask_generator(object(), "qwen")
    assert generator.tokenizer_type == "qwen"


def _llm_lock() -> dict:
    return {
        "config": {
            "llm": {
                "provider": "unit",
                "model": "unit-model",
                "model_revision": "unit-revision",
                "endpoint": "https://invalid.example.test",
                "credential_env": "W8_UNIT_LLM_KEY",
                "decoding": {"temperature": 0},
                "input_cost_per_million": 1.0,
                "output_cost_per_million": 1.0,
                "budgets": {
                    "total_calls": 1,
                    "input_tokens": 10,
                    "output_tokens": 10,
                    "wall_time_seconds": 10,
                    "spend_amount": 1.0,
                },
            }
        }
    }


def test_llm_budget_allows_exact_cap_and_rejects_overage() -> None:
    exact = {
        "calls": 1,
        "input_tokens": 10,
        "output_tokens": 10,
        "wall_time_seconds": 10,
        "estimated_spend": 1.0,
    }
    _check_budget(_llm_lock(), exact)
    with pytest.raises(AiderSftError, match="llm_budget_exhausted"):
        _check_budget(_llm_lock(), {**exact, "calls": 2})


def test_capacity_reserve_is_computed_from_remaining_candidates() -> None:
    lock = _llm_lock()
    lock["config"]["llm"]["budgets"].update(
        {
            "total_candidates": 4,
            "reserve_multiplier": 3.0,
            "calls_per_candidate": 4,
            "total_calls": 12,
        }
    )
    deficits = {"unit": {"train": 1}}
    insufficient = capacity_report(
        config_lock=lock,
        deficit_cells=deficits,
        used_candidates=2,
    )
    assert insufficient["remaining_candidate_capacity"] == 2
    assert insufficient["minimum_candidate_capacity"] == 3
    assert insufficient["status"] == "insufficient"
    sufficient = capacity_report(
        config_lock=lock,
        deficit_cells=deficits,
        used_candidates=1,
    )
    assert sufficient["status"] == "sufficient"


def test_missing_llm_credential_does_not_reserve_a_paid_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("W8_UNIT_LLM_KEY", raising=False)
    root = tmp_path / "dataset"
    with pytest.raises(AiderSftError, match="llm_transport_failed"):
        _call_stage(
            root=root,
            candidate_id="candidate-1",
            stage="planner",
            inputs={"cell": "unit"},
            config_lock=_llm_lock(),
        )
    assert not (tmp_path / "dataset.state/generation/requests").exists()


def test_received_invalid_llm_response_is_terminal_and_budgeted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "unit-model",
                    "choices": [{"message": {"content": "not-json"}}],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1},
                }
            ).encode("utf-8")

    monkeypatch.setenv("W8_UNIT_LLM_KEY", "secret")
    monkeypatch.setattr(
        "w8_biayn.aider_sft.llm_curator.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(),
    )
    root = tmp_path / "dataset"
    with pytest.raises(AiderSftError, match="static_schema_error"):
        _call_stage(
            root=root,
            candidate_id="candidate-invalid",
            stage="planner",
            inputs={"cell": "unit"},
            config_lock=_llm_lock(),
        )
    request_files = list((tmp_path / "dataset.state/generation/requests").glob("*.json"))
    assert len(request_files) == 1
    assert read_json(request_files[0])["status"] == "completed_invalid_response"
    budget = read_json(tmp_path / "dataset.state/generation/budget.json")
    assert budget["calls"] == 1
    assert budget["input_tokens"] == 2
    assert budget["output_tokens"] == 1


def test_invalid_provider_usage_is_terminal_and_blocks_future_paid_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "unit-model",
                    "choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": "not-an-int", "completion_tokens": 1},
                }
            ).encode("utf-8")

    monkeypatch.setenv("W8_UNIT_LLM_KEY", "secret")
    monkeypatch.setattr(
        "w8_biayn.aider_sft.llm_curator.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(),
    )
    root = tmp_path / "dataset"
    lock = _llm_lock()
    lock["config"]["llm"]["budgets"]["total_calls"] = 3
    with pytest.raises(AiderSftError, match="llm_budget_exhausted"):
        _call_stage(
            root=root,
            candidate_id="candidate-invalid-usage",
            stage="planner",
            inputs={"cell": "unit"},
            config_lock=lock,
        )

    requests_dir = tmp_path / "dataset.state/generation/requests"
    request_files = list(requests_dir.glob("*.json"))
    assert len(request_files) == 1
    request = read_json(request_files[0])
    assert request["status"] == "completed_invalid_usage"
    assert request["token_usage"] == {"input": None, "output": None}
    budget = read_json(tmp_path / "dataset.state/generation/budget.json")
    assert budget["calls"] == 1
    assert budget["usage_unreconciled"] is True

    with pytest.raises(AiderSftError, match="llm_budget_exhausted"):
        _call_stage(
            root=root,
            candidate_id="candidate-after-invalid-usage",
            stage="planner",
            inputs={"cell": "unit"},
            config_lock=lock,
        )
    assert len(list(requests_dir.glob("*.json"))) == 1


def _source_adapter_lock() -> dict:
    return {
        "lock_sha256": "f" * 64,
        "config": {
            "upstreams": {
                "exercism_cpp": {
                    "repository": "https://github.com/exercism/cpp.git",
                    "revision": EXERCISM_CPP_PIN,
                }
            },
            "toolchain": {
                "docker_image": "unit-image",
                "docker_image_id": "sha256:" + "1" * 64,
                "cxx_path": "/usr/bin/g++",
                "cxx_version": "unit",
                "cxx_binary_sha256": "2" * 64,
            },
            "sandbox": {
                "network": "none",
                "read_only_rootfs": True,
                "run_as_non_root": True,
                "no_new_privileges": True,
                "cap_drop": ["ALL"],
                "mount_policy": "single-rw-scratch-no-host-secrets-v1",
                "seccomp_profile_sha256": "3" * 64,
                "cpus": 2,
                "memory_mib": 2048,
                "pids": 256,
                "file_size_mib": 64,
            },
            "limits": {
                "editable_files": 8,
                "context_files": 16,
                "task_local_files": 128,
                "visible_file_bytes": 262144,
                "grader_file_bytes": 262144,
                "visible_total_bytes": 524288,
                "task_total_bytes": 4194304,
                "shared_file_bytes": 1048576,
                "shared_total_bytes": 4194304,
            },
        },
    }


def test_pinned_source_inventory_and_reference_mapping_fixtures(tmp_path: Path) -> None:
    checkout = ROOT / ".cache/upstreams/exercism-cpp"
    benchmark = ROOT / ".cache/upstreams/aider-polyglot"
    if not checkout.is_dir() or not benchmark.is_dir():
        pytest.skip("requires pinned ignored Exercism and Aider Polyglot checkouts")
    inventory_root = tmp_path / "inventory"
    result = build_inventory_proposal(
        config_path=ROOT / "configs/aider_sft/pilot-v1.toml",
        output_root=inventory_root,
        repo_root=ROOT,
    )
    assert result["source_candidates"] == 75
    assert result["required_llm_admissions"] == 21
    proposal = SourceManifest.model_validate(
        read_json(inventory_root / "private/inventory/proposed-source.json")
    )
    for entry in proposal.entries:
        cmake = checkout / entry.source_relative_path / "CMakeLists.txt"
        assert b"CXX_STANDARD 17" in cmake.read_bytes(), f"{entry.slug} no longer declares C++17"
    entries = {entry.slug: entry for entry in proposal.entries}
    canonical_root = tmp_path / "canonical"
    for slug in ("leap", "vehicle-purchase"):
        canonicalize_exercism_task(
            entry=entries[slug],
            checkout=checkout,
            canonical_root=canonical_root,
            config_lock=_source_adapter_lock(),
        )

    leap_root = canonical_root / "leap"
    leap = load_canonical_task(leap_root)
    assert leap.files.editable == ["leap.cpp", "leap.h"]
    assert [row.canonical_editable for row in leap.files.source_reference_mapping] == ["leap.h"]
    assert (leap_root / "workspace/starter/leap.cpp").read_bytes() == (
        leap_root / "workspace/reference/leap.cpp"
    ).read_bytes()

    vehicle_root = canonical_root / "vehicle-purchase"
    vehicle = load_canonical_task(vehicle_root)
    assert vehicle.files.editable == ["vehicle_purchase.cpp"]
    assert vehicle.files.model_context == ["vehicle_purchase.h"]
    assert vehicle.files.context_reference_equivalence[0].required_relation == (
        "byte_identical_to_starter"
    )
    prompt = render_prompt(vehicle_root, vehicle)
    target = render_target(vehicle_root, vehicle)
    assert "grader/" not in prompt
    assert ".meta/" not in prompt
    assert parse_target(target, expected_files=vehicle.files.editable)

    source_only_root = tmp_path / "source-only-inventory"
    source_only = build_inventory_proposal(
        config_path=ROOT / "configs/aider_sft/source-only-75-v1.toml",
        output_root=source_only_root,
        repo_root=ROOT,
    )
    assert source_only["source_candidates"] == 75
    assert source_only["required_llm_admissions"] == 0
    source_only_proposal = SourceManifest.model_validate(
        read_json(source_only_root / "private/inventory/proposed-source.json")
    )
    assert source_only_proposal.dataset_profile == SOURCE_ONLY_DATASET_PROFILE
    assert {entry.intended_split.value for entry in source_only_proposal.entries} == {"train"}
    capacity = read_json(source_only_root / "private/inventory/capacity-report.json")
    assert capacity["llm_enabled"] is False
    assert capacity["capacity_sufficient"] is True


def test_glm_lane_enforces_primary_bundle_handoff_contract() -> None:
    lane = (ROOT / "examples/slime/glm47_cpp_perf/glm47_cpp_perf.sh").read_text(encoding="utf-8")
    assert f'HF_MODEL_REVISION="${{SLIME_HF_MODEL_REVISION:-{GLM_REVISION}}}"' in lane
    assert "revision=revision" in lane
    assert "verify_export_bundle" in lane
    assert "SLIME_CPP_AUTO_PREPARE_DATA=0" in lane
    assert "w8_biayn.aider_sft.handoff.generate_sft_rollout" in lane
    assert "--apply-chat-template-kwargs" in lane
    assert "--loss-mask-type qwen" in lane
    assert 'if [ "${SEQ_LENGTH}" != "4096" ]' in lane


def test_oracle_rerun_uses_external_copy_and_never_ready_task_root() -> None:
    source = (ROOT / "src/w8_biayn/aider_sft/receipts.py").read_text(encoding="utf-8")
    assert "shutil.copytree(task_root, copied" in source
    assert "task_root=copied" in source
    assert "oracle-rerun-report.json" in source
    assert "task_root=task_root,\n                shared_support_root" not in source
