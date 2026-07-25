from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_local_scope_is_explicit_and_count_free() -> None:
    scope = _read("docs/AIDER_SFT_SCOPE.md")
    assert ".w8-biayn/data/aider-tasks/" in scope
    assert ".w8-biayn/data/aider-tasks-reverify/" in scope
    assert ".w8-biayn/data/aider-tasks-expansion-v1/" in scope
    assert "docs/aider-synthetic/" in scope
    assert "never hand-edit" in scope
    assert "local_family_verified" in scope
    assert "There is no fixed\nroot-count gate" in scope


def test_local_remediation_does_not_require_dataset_release() -> None:
    guidance = _read("AGENTS.md")
    remedy = _read("docs/aider-tasks-spec/verify-and-remedy.md")
    prompt = _read("docs/aider-tasks-spec/prompts/implement-family-for-sft.md")

    assert "It ends at\n`local_family_verified`" in guidance
    assert "Dataset handoff remains `not_requested`" in remedy
    assert "local_scope_only requires" not in remedy
    assert "Finalize:**" not in remedy
    assert "local_family_verified" in prompt


def test_balanced_tree_spec_has_unambiguous_local_completion_and_apis() -> None:
    spec = _read("docs/aider-tasks-spec/aider-dsa/balanced-search-tree.md")

    assert "Historical release evidence is not a local remediation blocker" in spec
    assert "Dataset-release artifacts are an explicit non-claim" in spec
    assert "bool remove_for_retention(std::int64_t event_id);" not in spec.split(
        "### B19. `rb-audit-event-index`", 1
    )[0]
    assert "`redacted` from false to true" not in spec.split(
        "### B19. `rb-audit-event-index`", 1
    )[0]
    assert "class MedicationSchedule" in spec


def test_task_remediation_skill_is_the_local_workflow_owner() -> None:
    skill = _read(".agents/skills/aider-task-family-remediation/SKILL.md")
    framework = _read(".agents/skills/w8-biayn-framework/SKILL.md")

    assert "name: aider-task-family-remediation" in skill
    assert "### 1. Find the weakness topic" in skill
    assert "### 5. Remediate and locally verify" in skill
    assert "## Prompt selection is mandatory" in skill
    assert "For **every** generated Aider task-family request" in skill
    assert "generate-family-spec.md" in skill
    assert "implement-family-for-sft.md" in skill
    assert "### Toolchain and execution evidence" in skill
    assert "host-only result" in skill
    assert "Never hand-edit that output." in skill
    assert "aider-task-family-remediation/SKILL.md" in framework
    assert "Historical Aider dataset-release" in framework


def test_aider_creator_owns_the_new_task_quality_loop() -> None:
    creator = _read(".agents/skills/aider-sft-task-creator/SKILL.md")
    scope = _read("docs/AIDER_SFT_SCOPE.md")

    assert "creator preflight -> independent audit" in creator
    assert "$audit-sft-data-quality" in creator
    assert "$aider-task-family-remediation" in creator
    assert "only a fresh audit" in creator
    assert ".w8-biayn/data/aider-tasks-expansion-v1/" in creator
    assert "Aider benchmark weakness-driven expansion" in creator
    assert "may not overwrite, copy, or rename tasks" in scope
