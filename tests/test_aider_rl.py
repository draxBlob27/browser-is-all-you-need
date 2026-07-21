from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from glm47_posttraining.aider_rl.admission import AdmissionError, tree_sha256
from glm47_posttraining.aider_rl.dataset import (
    PUBLIC_METADATA_KEYS,
    admit_drafts,
    build_bundle,
    verify_bundle,
)
import glm47_posttraining.aider_rl.dataset as aider_dataset_module
from glm47_posttraining.aider_rl.eval import aggregate_eval_records
from glm47_posttraining.aider_rl.curriculum import (
    CurriculumCatalog,
    analyze_no_update_canary,
)
from glm47_posttraining.aider_rl.parser import WholeEditParseError, parse_whole_edit
from glm47_posttraining.aider_rl.prompt import build_prompt, render_whole_edit
from glm47_posttraining.aider_rl.reward import (
    RewardBreakdown,
    RewardInfrastructureError,
    RubricScore,
    compute_reward,
)
import glm47_posttraining.aider_rl.sandbox as sandbox_module
import glm47_posttraining.integrations.miles_aider_rl as miles_aider_module
from glm47_posttraining.aider_rl.schema import (
    AiderHarnessResult,
    AiderTask,
    CommandSpec,
    EditableFile,
    EvidenceReceipt,
    FileIdentity,
    MutantFile,
    MutantSpec,
    OracleReceipt,
    StageResult,
    RubricHarnessResult,
    RubricSpec,
    RubricTestGroup,
    TestSuiteIdentity,
    TokenEvidence,
    PARSER_FINGERPRINT,
    REWARD_FINGERPRINT,
    canonical_sha256,
    file_sha256,
)
from glm47_posttraining.integrations.miles_aider_rl import (
    AiderRewardConfigurationError,
    reward_func,
)
from glm47_posttraining.integrations.wandb_aider_rl import (
    AIDER_SAMPLE_TABLE_COLUMNS,
    FORBIDDEN_PIE_FIELDS,
    build_aider_wandb_payload,
    publish_aider_stage,
)


SHA = "0" * 64
CATALOG_PATH = Path("configs/aider_rl/failure_rubric_catalog.v1.json")
CATALOG = CurriculumCatalog.read_json(CATALOG_PATH)


class _FakeBackend:
    def to_str(self) -> str:
        return '{"fixture":"aider-tokenizer-v1"}'


class _FakeTokenizer:
    backend_tokenizer = _FakeBackend()
    chat_template = "fixture-chat-template-v1"

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize and add_generation_prompt
        return self.encode("USER:" + messages[0]["content"] + "\nASSISTANT:", add_special_tokens=False)

    def encode(self, value, *, add_special_tokens):
        assert add_special_tokens is False
        return list(value.encode("utf-8"))


TOKENIZER = _FakeTokenizer()


def _argv(name: str) -> list[str]:
    return [name, "{task}", "{build}"]


def _rubric_group(rubric: str, visibility: str, expected_count: int) -> RubricTestGroup:
    return RubricTestGroup(
        visibility=visibility,
        expected_count=expected_count,
        discover=_argv(f"discover-{visibility}-{rubric}"),
        run=_argv(f"run-{visibility}-{rubric}"),
        sanitizer_discover=_argv(f"san-discover-{visibility}-{rubric}"),
        sanitizer_run=_argv(f"san-run-{visibility}-{rubric}"),
    )


def _rubric_spec(rubric_id: str, groups: list[RubricTestGroup]) -> RubricSpec:
    definition = next(item for item in CATALOG.rubrics if item.rubric_id == rubric_id)
    return RubricSpec(**definition.model_dump(mode="json"), test_groups=groups)


def _task(
    root: Path,
    *,
    task_id: str = "task-1",
    split: str = "train",
    split_plan: list[tuple[str, str]] | None = None,
) -> AiderTask:
    root.mkdir(parents=True, exist_ok=True)
    (root / "curriculum.catalog.json").write_text(
        CATALOG.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    tree = root / task_id / "tree"
    (tree / "src").mkdir(parents=True)
    (tree / ".reference" / "src").mkdir(parents=True)
    (tree / ".mutants" / "reject" / "src").mkdir(parents=True)
    (tree / ".mutants" / "atomic" / "src").mkdir(parents=True)
    starter = "int answer() { return 0; }\n"
    reference = "int answer() { return 42; }\n"
    (tree / "src" / "answer.cpp").write_text(starter, encoding="utf-8")
    (tree / ".reference" / "src" / "answer.cpp").write_text(reference, encoding="utf-8")
    (tree / ".mutants" / "reject" / "src" / "answer.cpp").write_text(
        "int answer() { return 41; }\n", encoding="utf-8"
    )
    (tree / ".mutants" / "atomic" / "src" / "answer.cpp").write_text(
        "int answer() { return 43; }\n", encoding="utf-8"
    )
    (tree / "CMakeLists.txt").write_text(
        "# private build definition with a sufficiently long unique marker\n", encoding="utf-8"
    )
    (tree / "tests").mkdir()
    (tree / "tests" / "visible.cpp").write_text(
        "// private visible assertion marker 7d412093\n", encoding="utf-8"
    )
    (tree / "tests" / "hidden.cpp").write_text(
        "// private hidden assertion marker 93d2247926\n", encoding="utf-8"
    )
    commands = CommandSpec(
        configure=_argv("configure") + ["-G", "Unix Makefiles", "-DCMAKE_CXX_STANDARD=17"],
        build_solution=_argv("build-solution"),
        build_tests=_argv("build-tests"),
        discover_visible=_argv("discover-visible"),
        run_visible=_argv("run-visible"),
        discover_hidden=_argv("discover-hidden"),
        run_hidden=_argv("run-hidden"),
        sanitizer_configure=_argv("san-configure")
        + ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined"],
        sanitizer_build_solution=_argv("san-build-solution"),
        sanitizer_build_tests=_argv("san-build-tests"),
        sanitizer_discover_visible=_argv("san-discover-visible"),
        sanitizer_run_visible=_argv("san-run-visible"),
        sanitizer_discover_hidden=_argv("san-discover-hidden"),
        sanitizer_run_hidden=_argv("san-run-hidden"),
    )
    oracle = OracleReceipt(
        reference_fingerprint=canonical_sha256(
            [("src/answer.cpp", file_sha256(tree / ".reference" / "src" / "answer.cpp"))]
        ),
        grader_image_digest="sha256:" + "a" * 64,
        compiler_fingerprint="b" * 64,
        normal_visible_count=2,
        normal_hidden_count=3,
        sanitizer_visible_count=2,
        sanitizer_hidden_count=3,
    )
    base = dict(
        task_id=task_id,
        family_id=f"family-{task_id}",
        lineage_id=f"lineage-{task_id}",
        split=split,
        capability_tags=["validation_parsing"],
        curriculum_fingerprint=CATALOG.fingerprint,
        rubrics=[
            _rubric_spec(
                "validation.complete_rejection",
                [
                    _rubric_group("reject", "visible", 1),
                    _rubric_group("reject", "hidden", 1),
                ],
            ),
            _rubric_spec(
                "validation.atomic_rejection",
                [
                    _rubric_group("atomic", "visible", 1),
                    _rubric_group("atomic", "hidden", 2),
                ],
            ),
        ],
        mutants=[
            MutantSpec(
                mutant_id="reject-mutant",
                files=[
                    MutantFile(
                        target_path="src/answer.cpp",
                        source_path=".mutants/reject/src/answer.cpp",
                        sha256=file_sha256(
                            tree / ".mutants" / "reject" / "src" / "answer.cpp"
                        ),
                    )
                ],
                expected_fail_rubric_ids=["validation.complete_rejection"],
                expected_pass_rubric_ids=["validation.atomic_rejection"],
            ),
            MutantSpec(
                mutant_id="atomic-mutant",
                files=[
                    MutantFile(
                        target_path="src/answer.cpp",
                        source_path=".mutants/atomic/src/answer.cpp",
                        sha256=file_sha256(
                            tree / ".mutants" / "atomic" / "src" / "answer.cpp"
                        ),
                    )
                ],
                expected_fail_rubric_ids=["validation.atomic_rejection"],
                expected_pass_rubric_ids=["validation.complete_rejection"],
            ),
        ],
        introduction="Implement the public answer API.",
        instructions="Return forty-two without changing the function name.",
        editable_files=[
            EditableFile(
                path="src/answer.cpp",
                reference_path=".reference/src/answer.cpp",
                starter_sha256=file_sha256(tree / "src" / "answer.cpp"),
            )
        ],
        build=commands,
        visible_tests=TestSuiteIdentity(
            expected_count=2,
            files=[
                FileIdentity(
                    path="tests/visible.cpp", sha256=file_sha256(tree / "tests" / "visible.cpp")
                )
            ],
            fingerprint=canonical_sha256(
                [("tests/visible.cpp", file_sha256(tree / "tests" / "visible.cpp"))]
            ),
        ),
        hidden_tests=TestSuiteIdentity(
            expected_count=3,
            files=[
                FileIdentity(
                    path="tests/hidden.cpp", sha256=file_sha256(tree / "tests" / "hidden.cpp")
                )
            ],
            fingerprint=canonical_sha256(
                [("tests/hidden.cpp", file_sha256(tree / "tests" / "hidden.cpp"))]
            ),
        ),
        tree_digest=tree_sha256(tree),
        prompt_fingerprint=SHA,
        parser_fingerprint=PARSER_FINGERPRINT,
        reward_fingerprint=REWARD_FINGERPRINT,
        grader_image="fixture-image:1",
        grader_image_digest="sha256:" + "a" * 64,
        compiler_fingerprint="b" * 64,
        provenance_fingerprint="5" * 64,
        contamination_fingerprint="6" * 64,
        provenance_receipt=EvidenceReceipt(
            policy_version="generator-provenance-v1", fingerprint="5" * 64
        ),
        contamination_receipt=EvidenceReceipt(
            policy_version="aider-holdout-screen-v1", fingerprint="6" * 64
        ),
        split_fingerprint=canonical_sha256(
            sorted(
                (
                    planned_id,
                    f"family-{planned_id}",
                    f"lineage-{planned_id}",
                    planned_split,
                )
                for planned_id, planned_split in (split_plan or [(task_id, split)])
            )
        ),
        token_evidence=TokenEvidence(
            tokenizer_fingerprint="8" * 64,
            chat_template_fingerprint="9" * 64,
            prompt_tokens=1,
            answer_tokens=1,
            loss_mask_tokens=1,
            total_tokens=2,
            prompt_hash=SHA,
            answer_hash=SHA,
            prompt_token_ids_hash=SHA,
            answer_token_ids_hash=SHA,
            response_budget=4,
        ),
        oracle_receipt=oracle,
    )
    preliminary = AiderTask(**base)
    starters = {"src/answer.cpp": starter}
    references = {"src/answer.cpp": reference}
    prompt = build_prompt(preliminary, starters)
    answer = render_whole_edit(preliminary, references)
    prompt_ids = TOKENIZER.apply_chat_template(
        [{"role": "user", "content": prompt}], tokenize=True, add_generation_prompt=True
    )
    answer_ids = TOKENIZER.encode(answer, add_special_tokens=False)
    base["prompt_fingerprint"] = canonical_sha256(prompt)
    base["token_evidence"] = TokenEvidence(
        tokenizer_fingerprint=hashlib.sha256(
            TOKENIZER.backend_tokenizer.to_str().encode("utf-8")
        ).hexdigest(),
        chat_template_fingerprint=canonical_sha256(TOKENIZER.chat_template),
        prompt_tokens=len(prompt_ids),
        answer_tokens=len(answer_ids),
        loss_mask_tokens=len(answer_ids),
        total_tokens=len(prompt_ids) + len(answer_ids),
        prompt_hash=canonical_sha256(prompt),
        answer_hash=canonical_sha256(answer),
        prompt_token_ids_hash=canonical_sha256(prompt_ids),
        answer_token_ids_hash=canonical_sha256(answer_ids),
        response_budget=len(answer_ids) + 8,
    )
    task = AiderTask(**base).with_computed_digest()
    task.write_json(root / task_id / "task.json")
    mutation_receipts = [
        {
            "receipt_version": "aider-mutant-admission-v1",
            "task_id": task.task_id,
            "task_digest": task.task_digest,
            "mutant_id": mutant.mutant_id,
            "expected_fail_rubric_ids": mutant.expected_fail_rubric_ids,
            "expected_pass_rubric_ids": mutant.expected_pass_rubric_ids,
            "rubric_scores": {
                rubric.rubric_id: (
                    0.0 if rubric.rubric_id in mutant.expected_fail_rubric_ids else 1.0
                )
                for rubric in task.rubrics
            },
            "reward": 0.0,
            "status": "passed",
        }
        for mutant in task.mutants
    ]
    (root / task_id / "mutation.receipt.json").write_text(
        json.dumps(mutation_receipts), encoding="utf-8"
    )
    return task


def _stage(discovered: int, passed: int) -> StageResult:
    return StageResult(
        attempted=True,
        passed=passed == discovered,
        returncode=0 if passed == discovered else 1,
        discovered=discovered,
        passed_tests=passed,
    )


def _harness(*, visible: int = 2, hidden: int = 3, sanitizer: bool = True) -> AiderHarnessResult:
    reject_visible = min(visible, 1)
    reject_hidden = min(hidden, 1)
    atomic_visible = max(0, visible - reject_visible)
    atomic_hidden = max(0, hidden - reject_hidden)
    return AiderHarnessResult(
        normal_visible=_stage(2, visible),
        normal_hidden=_stage(3, hidden),
        sanitizer_visible=_stage(2, 2 if sanitizer else 1),
        sanitizer_hidden=_stage(3, 3 if sanitizer else 2),
        sanitizer_error=not sanitizer,
        rubric_results=[
            RubricHarnessResult(
                rubric_id="validation.complete_rejection",
                normal_visible=_stage(1, reject_visible),
                normal_hidden=_stage(1, reject_hidden),
                sanitizer_visible=_stage(1, 1 if sanitizer else 0),
                sanitizer_hidden=_stage(1, 1 if sanitizer else 0),
            ),
            RubricHarnessResult(
                rubric_id="validation.atomic_rejection",
                normal_visible=_stage(1, atomic_visible),
                normal_hidden=_stage(2, atomic_hidden),
                sanitizer_visible=_stage(1, 1 if sanitizer else 0),
                sanitizer_hidden=_stage(2, 2 if sanitizer else 1),
            ),
        ],
    )


def _mutant_harness(failed_rubric: str) -> AiderHarnessResult:
    result = _harness()
    target = next(item for item in result.rubric_results if item.rubric_id == failed_rubric)
    target.normal_visible = _stage(target.normal_visible.discovered, 0)
    target.normal_hidden = _stage(target.normal_hidden.discovered, 0)
    result.normal_visible = _stage(
        2, sum(item.normal_visible.passed_tests for item in result.rubric_results)
    )
    result.normal_hidden = _stage(
        3, sum(item.normal_hidden.passed_tests for item in result.rubric_results)
    )
    return result


def test_strict_named_file_parser_rejects_all_file_set_violations() -> None:
    good = "a.h\n```cpp\nint a;\n```\n\nb.cpp\n```cpp\nint b;\n```\n"
    parsed = parse_whole_edit(good, ["a.h", "b.cpp"])
    assert parsed.ordered_paths == ("a.h", "b.cpp")
    assert parsed.files["a.h"] == "int a;\n"
    bad = {
        "missing_file": "a.h\n```cpp\nint a;\n```\n",
        "extra_file": good + "x.cpp\n```cpp\nint x;\n```\n",
        "wrong_file_order": "b.cpp\n```cpp\nint b;\n```\n\na.h\n```cpp\nint a;\n```\n",
        "unsafe_path": "../a.h\n```cpp\nint a;\n```\n\nb.cpp\n```cpp\nint b;\n```\n",
        "duplicate_file": "a.h\n```cpp\nint a;\n```\n\na.h\n```cpp\nint z;\n```\n",
    }
    for reason, output in bad.items():
        with pytest.raises(WholeEditParseError) as raised:
            parse_whole_edit(output, ["a.h", "b.cpp"])
        assert raised.value.reason == reason


def test_schema_rejects_private_editable_paths(tmp_path: Path) -> None:
    task = _task(tmp_path)
    private_edit = EditableFile(
        path="tests/visible.cpp",
        reference_path=".reference/src/answer.cpp",
        starter_sha256=file_sha256(tmp_path / task.task_id / "tree" / "tests" / "visible.cpp"),
    )
    payload = task.model_dump(mode="json")
    payload["editable_files"] = [private_edit.model_dump(mode="json")]
    payload["task_digest"] = ""
    with pytest.raises(ValueError, match="editable files cannot include private"):
        AiderTask.model_validate(payload)


def test_correctness_reward_tiers_and_infrastructure_removal(tmp_path: Path) -> None:
    task = _task(tmp_path)
    answer = "src/answer.cpp\n```cpp\nint answer() { return 42; }\n```\n"

    def runner_for(result: AiderHarnessResult):
        return lambda _task, _files, _tree: result

    assert compute_reward(task, "bad", task_tree=tmp_path).reward == -1.0
    compile_fail = AiderHarnessResult(compile_error=True)
    assert compute_reward(task, answer, task_tree=tmp_path, runner=runner_for(compile_fail)).reward == -0.5
    partial = compute_reward(task, answer, task_tree=tmp_path, runner=runner_for(_harness(visible=1, hidden=2)))
    assert partial.reason == "tests_failed"
    assert partial.reward == pytest.approx(0.0)
    assert {item.rubric_id for item in partial.rubric_scores} == {
        "validation.complete_rejection",
        "validation.atomic_rejection",
    }
    sanitized = compute_reward(task, answer, task_tree=tmp_path, runner=runner_for(_harness(sanitizer=False)))
    assert sanitized.reward == 0.3
    assert compute_reward(task, answer, task_tree=tmp_path, runner=runner_for(_harness())).reward == 1.0
    repaired = compute_reward(
        task, answer, task_tree=tmp_path, runner=runner_for(_harness()), round_number=2
    )
    assert repaired.reward == 0.8
    with pytest.raises(RewardInfrastructureError):
        compute_reward(
            task,
            answer,
            task_tree=tmp_path,
            runner=runner_for(AiderHarnessResult(infrastructure_error=True, infrastructure_reason="docker")),
        )


def test_docker_grader_uses_fresh_normal_and_sanitizer_trees(
    tmp_path: Path, monkeypatch
) -> None:
    task = _task(tmp_path)
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        executable = next(
            (
                token
                for token in reversed(command)
                if token.startswith(("configure", "build", "discover", "run", "san-"))
            ),
            "",
        )
        if "discover" in executable and "atomic" in executable and "hidden" in executable:
            stdout = "Total Tests: 2\n"
        elif "discover" in executable and ("atomic" in executable or "reject" in executable):
            stdout = "Total Tests: 1\n"
        elif "discover" in executable and "visible" in executable:
            stdout = "Total Tests: 2\n"
        elif "discover" in executable and "hidden" in executable:
            stdout = "Total Tests: 3\n"
        else:
            stdout = "100% tests passed, 0 tests failed out of 3\n"
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(sandbox_module, "grader_image_id", lambda _image: "sha256:" + "a" * 64)
    monkeypatch.setattr(sandbox_module, "grader_compiler_fingerprint", lambda _image: "b" * 64)
    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)
    result = sandbox_module.run_in_sandbox(
        task,
        {"src/answer.cpp": "int answer() { return 42; }\n"},
        tmp_path / task.task_id / "tree",
    )

    assert result.full_success is True
    flattened = "\n".join(" ".join(command) for command in commands)
    assert "/work/task-normal" in flattened
    assert "/work/task-sanitizer" in flattened
    assert "--network none" in flattened
    assert "--read-only" in flattened
    assert "--cap-drop ALL" in flattened
    assert "no-new-privileges" in flattened


def test_bundle_projection_keeps_private_material_out_of_public_rows(tmp_path: Path) -> None:
    source = tmp_path / "source"
    plan = [
        ("task-1", "train"),
        ("task-anchor", "anchor"),
        ("task-validation", "validation"),
        ("task-internal", "internal_test"),
    ]
    tasks = {
        task_id: _task(source, task_id=task_id, split=split, split_plan=plan)
        for task_id, split in plan
    }
    task = tasks["task-1"]
    paths = build_bundle(source, tmp_path / "bundle", tokenizer=TOKENIZER)
    manifest = verify_bundle(tmp_path / "bundle", tokenizer=TOKENIZER)
    assert manifest["counts"] == {
        "anchor": 1,
        "internal_test": 1,
        "train": 1,
        "validation": 1,
    }
    row = json.loads(paths["grpo_train"].read_text(encoding="utf-8"))
    assert set(row["metadata"]) == PUBLIC_METADATA_KEYS
    assert row["metadata"]["task_digest"] == task.task_digest
    public_text = json.dumps(row)
    assert "private hidden assertion" not in public_text
    assert "oracle_receipt" not in public_text
    assert ".reference" not in public_text
    assert "CMakeLists.txt" not in public_text

    wrong_tokenizer = _FakeTokenizer()
    wrong_tokenizer.backend_tokenizer = SimpleNamespace(to_str=lambda: '{"wrong":true}')
    with pytest.raises(AdmissionError, match="tokenizer fingerprint"):
        verify_bundle(tmp_path / "bundle", tokenizer=wrong_tokenizer)

    mutation_path = paths["mutation_records"]
    original_mutations = mutation_path.read_text(encoding="utf-8")
    mutation_rows = [json.loads(line) for line in original_mutations.splitlines()]
    mutation_rows[0]["rubric_scores"][mutation_rows[0]["expected_fail_rubric_ids"][0]] = 1.0
    mutation_path.write_text(
        "".join(json.dumps(row) + "\n" for row in mutation_rows), encoding="utf-8"
    )
    with pytest.raises(AdmissionError, match="targeted rubric passed"):
        verify_bundle(tmp_path / "bundle", tokenizer=TOKENIZER)
    mutation_path.write_text(original_mutations, encoding="utf-8")

    catalog_path = tmp_path / "bundle" / "curriculum.catalog.json"
    catalog_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_payload["rubrics"][0]["weight"] += 0.25
    catalog_path.write_text(json.dumps(catalog_payload), encoding="utf-8")
    with pytest.raises(AdmissionError, match="catalog differs"):
        verify_bundle(tmp_path / "bundle", tokenizer=TOKENIZER)


def test_draft_admission_computes_immutable_evidence(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "drafts"
    task = _task(source)
    draft = {
        "task_id": task.task_id,
        "family_id": task.family_id,
        "lineage_id": task.lineage_id,
        "split": task.split,
        "capability_tags": task.capability_tags,
        "rubrics": [
            {
                "rubric_id": rubric.rubric_id,
                "test_groups": [group.model_dump(mode="json") for group in rubric.test_groups],
            }
            for rubric in task.rubrics
        ],
        "mutants": [
            {
                "mutant_id": mutant.mutant_id,
                "files": [
                    {
                        "target_path": item.target_path,
                        "source_path": item.source_path,
                    }
                    for item in mutant.files
                ],
                "expected_fail_rubric_ids": mutant.expected_fail_rubric_ids,
                "expected_pass_rubric_ids": mutant.expected_pass_rubric_ids,
            }
            for mutant in task.mutants
        ],
        "introduction": task.introduction,
        "instructions": task.instructions,
        "editable_files": [
            {
                "path": item.path,
                "reference_path": item.reference_path,
                "max_bytes": item.max_bytes,
            }
            for item in task.editable_files
        ],
        "build": task.build.model_dump(mode="json"),
        "visible_tests": {
            "expected_count": task.visible_tests.expected_count,
            "files": [item.path for item in task.visible_tests.files],
        },
        "hidden_tests": {
            "expected_count": task.hidden_tests.expected_count,
            "files": [item.path for item in task.hidden_tests.files],
        },
        "provenance_receipt": task.provenance_receipt.model_dump(mode="json"),
        "contamination_receipt": task.contamination_receipt.model_dump(mode="json"),
        "response_budget_margin": 8,
    }
    (source / task.task_id / "task.draft.json").write_text(json.dumps(draft), encoding="utf-8")
    lock = {
        "image": task.grader_image,
        "grader_image_digest": task.grader_image_digest,
        "compiler_fingerprint": task.compiler_fingerprint,
    }
    lock_path = tmp_path / "grader.lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    monkeypatch.setattr(sandbox_module, "grader_image_id", lambda _image: task.grader_image_digest)
    monkeypatch.setattr(
        sandbox_module, "grader_compiler_fingerprint", lambda _image: task.compiler_fingerprint
    )
    def fake_admission_reward(_task, output, **_kwargs):
        if "return 42" in output:
            return RewardBreakdown(
                reward=1.0,
                reason="correct",
                format_valid=True,
                harness=_harness(),
            )
        failed = (
            "validation.complete_rejection"
            if "return 41" in output
            else "validation.atomic_rejection"
        )
        harness = _mutant_harness(failed)
        scores = tuple(
            RubricScore(
                rubric_id=item.rubric_id,
                score=0.0 if item.rubric_id == failed else 1.0,
                weight=1.0,
                critical=True,
            )
            for item in _task.rubrics
        )
        return RewardBreakdown(
            reward=0.0,
            reason="tests_failed",
            format_valid=True,
            harness=harness,
            rubric_scores=scores,
        )

    monkeypatch.setattr(aider_dataset_module, "compute_reward", fake_admission_reward)
    written = admit_drafts(
        source,
        tmp_path / "admitted",
        tokenizer=TOKENIZER,
        grader_lock=lock_path,
        curriculum_catalog=CATALOG_PATH,
    )
    admitted = AiderTask.read_json(written[0])
    assert admitted.task_digest
    assert admitted.visible_tests.files[0].sha256 == file_sha256(
        tmp_path / "admitted" / task.task_id / "tree" / "tests" / "visible.cpp"
    )
    assert admitted.token_evidence.response_budget == admitted.token_evidence.answer_tokens + 8


def test_failure_catalog_and_no_update_canary_gate_reward_variance() -> None:
    assert CATALOG.catalog_version == "aider-failure-rubrics-v1"
    assert len(CATALOG.failure_modes) == 15
    assert len(CATALOG.rubrics) == 15
    capability_plan = (
        ["time_date"] * 4
        + ["validation_parsing"] * 3
        + ["state_concurrency"] * 3
        + ["algorithms_data_structures"] * 2
        + ["text_grid_logic"] * 2
        + ["numerical"] * 2
    )
    records = []
    for task_index, capability in enumerate(capability_plan):
        for sample_index in range(8):
            score = 1.0 if sample_index == 0 else 0.0
            records.append(
                {
                    "task_id": f"canary-{task_index}",
                    "rollout_id": "no-update-v1",
                    "sample_index": sample_index,
                    "score": score,
                    "infrastructure_error": False,
                    "capability_tags": [capability],
                    "rubric_ids": ["fixture.behavior"],
                    "rubric_scores": {"fixture.behavior": score},
                }
            )
    ready = analyze_no_update_canary(records, CATALOG)
    assert ready["status"] == "ready"
    assert ready["gates"] == {
        "task_count": True,
        "group_shape": True,
        "rubric_shape": True,
        "reward_variance": True,
        "infrastructure": True,
        "capability_balance": True,
    }

    for row in records:
        row["score"] = 0.0
        row["rubric_scores"] = {"fixture.behavior": 0.0}
    sparse = analyze_no_update_canary(records, CATALOG)
    assert sparse["status"] == "not_ready"
    assert sparse["gates"]["reward_variance"] is False


def test_miles_single_batch_shape_and_contained_path_resolution(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    plan = [
        ("task-1", "train"),
        ("task-anchor", "anchor"),
        ("task-validation", "validation"),
        ("task-internal", "internal_test"),
    ]
    for task_id, split in plan:
        _task(source, task_id=task_id, split=split, split_plan=plan)
    paths = build_bundle(source, tmp_path / "bundle", tokenizer=TOKENIZER)
    row = json.loads(paths["grpo_train"].read_text(encoding="utf-8"))
    monkeypatch.setenv("MILES_AIDER_DATA_DIR", str(tmp_path / "bundle"))
    sample = SimpleNamespace(index=1, rollout_id=2, response="invalid", metadata=row["metadata"])
    single = asyncio.run(reward_func(None, sample))
    assert single["score"] == -1.0
    assert single["reason"] == "invalid_format"
    batch = asyncio.run(reward_func(None, [sample, sample]))
    assert [item["score"] for item in batch] == [-1.0, -1.0]
    escaped = dict(row["metadata"], task_path="../task.json")
    with pytest.raises(AiderRewardConfigurationError):
        asyncio.run(reward_func(None, SimpleNamespace(response="bad", metadata=escaped)))


def test_miles_retries_infrastructure_before_returning_reward(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    plan = [
        ("task-1", "train"),
        ("task-anchor", "anchor"),
        ("task-validation", "validation"),
        ("task-internal", "internal_test"),
    ]
    for task_id, split in plan:
        _task(source, task_id=task_id, split=split, split_plan=plan)
    paths = build_bundle(source, tmp_path / "bundle", tokenizer=TOKENIZER)
    row = json.loads(paths["grpo_train"].read_text(encoding="utf-8"))
    monkeypatch.setenv("MILES_AIDER_DATA_DIR", str(tmp_path / "bundle"))
    monkeypatch.setenv("GLM47_AIDER_INFRASTRUCTURE_RETRIES", "2")
    attempts = 0

    def fake_compute(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RewardInfrastructureError("transient docker failure")
        return RewardBreakdown(reward=-1.0, reason="invalid_format", format_valid=False)

    monkeypatch.setattr(miles_aider_module, "compute_reward", fake_compute)
    sample = SimpleNamespace(response="bad", metadata=row["metadata"])
    result = asyncio.run(reward_func(None, sample))
    assert result["score"] == -1.0
    assert attempts == 3


def test_eval_pairs_repair_rows_by_trajectory() -> None:
    records = [
        {
            "task_id": "t1",
            "rollout_id": 0,
            "sample_index": 0,
            "round_number": 1,
            "full_success": False,
        },
        {
            "task_id": "t1",
            "rollout_id": 0,
            "sample_index": 0,
            "round_number": 2,
            "full_success": True,
        },
        {
            "task_id": "t2",
            "rollout_id": 0,
            "sample_index": 0,
            "round_number": 1,
            "full_success": True,
        },
    ]
    summary = aggregate_eval_records(records, label="fixture")
    assert summary["strict_one_shot_pass_rate"] == 0.5
    assert summary["cumulative_correct_rate"] == 1.0
    assert summary["repair_conversion_rate"] == 1.0


def test_aider_launcher_is_isolated_from_pie_profile() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "scripts" / "train_aider_grpo.sh").read_text(encoding="utf-8")
    assert "glm47_posttraining.integrations.miles_aider_rl.reward_func" in text
    assert "--eval-prompt-data aider_cpp" in text
    assert "MILES_AIDER_DATA_DIR" in text
    assert "MILES_AIDER_TASKS_DIR" in text
    assert "GLM47_AIDER_GRADER_IMAGE" in text
    assert "GLM47_AIDER_REWARD_WORKERS" in text
    assert "ADMITTED_RESPONSE_BUDGET" in text
    assert "dataset ready" in text
    assert "--tokenizer" in text
    assert "ADMITTED_MAX_TOTAL_TOKENS" in text
    assert "publish_aider_results.py" in text
    assert "publish_results.py" not in text
    assert "MILES_CPP_" not in text
    assert "GLM47_CPP_" not in text
    assert "pie_cpp" not in text
    canonical = (root / "scripts" / "train_grpo.sh").read_text(encoding="utf-8")
    assert "glm47_posttraining.integrations.miles_cpp_perf.reward_func" in canonical
    publisher = (root / "scripts" / "publish_aider_results.py").read_text(encoding="utf-8")
    assert "wandb_aider_rl" in publisher
    assert "wandb_posttraining" not in publisher


def test_aider_wandb_payload_contains_no_pie_runtime_fields() -> None:
    records = [
        {
            "task_id": "t1",
            "family_id": "f1",
            "capability_tags": ["parsing"],
            "score": 1.0,
            "reason": "correct",
            "format_valid": True,
            "allowed_file_compliance": True,
            "configure_pass": True,
            "compile_pass": True,
            "visible_pass": True,
            "hidden_pass": True,
            "sanitizer_pass": True,
            "full_success": True,
        }
    ]
    metrics, rows = build_aider_wandb_payload(records, label="sft")
    assert metrics["aider_eval/strict_one_shot_pass_rate"] == 1.0
    assert len(rows) == 1
    assert not (set(AIDER_SAMPLE_TABLE_COLUMNS) & FORBIDDEN_PIE_FIELDS)
    assert all(key.rsplit("/", 1)[-1] not in FORBIDDEN_PIE_FIELDS for key in metrics)


def test_aider_stage_publisher_uses_aider_tags(tmp_path: Path, monkeypatch) -> None:
    observed: dict[str, object] = {}

    class FakeRun:
        def log(self, payload):
            observed["payload"] = payload

        def finish(self):
            observed["finished"] = True

    def fake_init(**kwargs):
        observed["init"] = kwargs
        return FakeRun()

    fake_wandb = SimpleNamespace(init=fake_init, Table=lambda **kwargs: kwargs)
    monkeypatch.setitem(sys.modules, "wandb", fake_wandb)
    publish_aider_stage(
        project="aider-project",
        run_id="run-1",
        group="group-1",
        stage="grpo",
        status="success",
        rollout_dump_dir=tmp_path / "missing",
        mode="offline",
    )
    tags = observed["init"]["tags"]
    assert "aider-cpp" in tags
    assert "pie-cpp" not in tags
    assert observed["finished"] is True
