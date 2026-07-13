"""Pure coordinator for the agentic Modal Multi-SWE C++ lane."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

from w8_biayn.modal_agentic_multi_swe_cpp import (
    BENCHMARK_LABEL,
    GRADER_CONCURRENCY,
    RESULT_FAMILY,
    SCHEMA_VERSION,
    ModalAgenticMultiSweConfig,
    ModalAgenticMultiSweError,
    aggregate_agentic_records,
    build_workspace_summary,
    classify_agentic_result,
    render_plan,
    workspace_cache_key,
)
from w8_biayn.modal_glm47 import (
    MODEL_REPO,
    MODAL_SDK_PIN,
    TRANSFORMERS_COMMIT,
)
from w8_biayn.modal_multi_swe_cpp import (
    DATASET_REPO,
    EXPECTED_CPP_TASKS,
    SMOKE_TASK_IDS,
    classify_response,
    oracle_cache_key,
)


Persist = Callable[[dict[str, Any]], None]
Grade = Callable[[dict[str, Any], str], dict[str, Any]]
WorkspaceProbe = Callable[[dict[str, Any]], dict[str, Any]]
RunTrajectory = Callable[[dict[str, Any], int], dict[str, Any]]


def _jsonl(rows: Sequence[Mapping[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def _oracle_response(patch: str) -> dict[str, Any]:
    fence = chr(96) * 3
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": fence
                    + "diff\n"
                    + patch.rstrip()
                    + "\n"
                    + fence
                },
            }
        ],
        "usage": {},
    }


def _oracle_key(
    task: Mapping[str, Any], lock_row: Mapping[str, Any]
) -> str:
    config = SimpleNamespace(
        test_timeout_seconds=1200,
        sandbox_cpu=2.0,
        sandbox_memory_mib=2048,
    )
    return oracle_cache_key(config, task, lock_row)



def _safe_task_metadata(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: task[key]
        for key in (
            "instance_id",
            "org",
            "repo",
            "repo_full_name",
            "base_ref",
            "sandbox_image_digest",
            "issue_context_sha256",
            "agent_problem_statement_sha256",
        )
        if key in task
    }


def _workspace_submodules(record: Mapping[str, Any]) -> Mapping[str, Any]:
    proof = record.get("proof")
    if not isinstance(proof, Mapping):
        return {}
    sanitizer = proof.get("sanitizer")
    if not isinstance(sanitizer, Mapping):
        return {}
    submodules = sanitizer.get("submodule_identities")
    return submodules if isinstance(submodules, Mapping) else {}

def prepare_proofs(
    *,
    config: ModalAgenticMultiSweConfig,
    lock: Mapping[str, Any],
    tasks: list[dict[str, Any]],
    dataset_receipt: Mapping[str, Any],
    grade: Grade,
    workspace_probe: WorkspaceProbe,
    persist: Persist,
    oracle_records: Mapping[str, Mapping[str, Any]] | None = None,
    workspace_records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Require all 50 oracle and sanitized-workspace proofs before GPU work."""

    if len(tasks) != EXPECTED_CPP_TASKS:
        raise ModalAgenticMultiSweError(
            "admission requires exactly 50 C++ tasks"
        )
    task_ids = {str(task["instance_id"]) for task in tasks}
    if task_ids != set(lock["tasks"]):
        raise ModalAgenticMultiSweError(
            "task set does not match checked-in image lock"
        )
    persist(
        {
            "plan.json": render_plan(config, lock),
            "config.redacted.json": config.redacted_mapping(),
            "source.receipt.json": {
                "source_commit": config.source_commit,
                "source_dirty": config.source_dirty,
                "source_file_hashes": config.source_file_hashes,
            },
            "dataset.receipt.json": dict(dataset_receipt),
            "image-lock.json": dict(lock),
            **{
                f"data/tasks/{task['instance_id']}/task.json": (
                    _safe_task_metadata(task)
                )
                for task in tasks
            },
        }
    )
    prior_oracles = dict(oracle_records or {})
    oracles: list[dict[str, Any]] = []
    for task in sorted(tasks, key=lambda row: row["instance_id"]):
        task_id = task["instance_id"]
        cache_key = _oracle_key(task, lock["tasks"][task_id])
        prior = prior_oracles.get(task_id)
        if (
            isinstance(prior, Mapping)
            and prior.get("oracle_cache_key") == cache_key
            and prior.get("setup_valid") is True
            and int(prior.get("tests_collected") or 0) > 0
        ):
            record = dict(prior)
        else:
            if config.oracle_source_run_id:
                raise ModalAgenticMultiSweError(
                    f"oracle import cache mismatch for {task_id}"
                )
            execution = grade(task, str(task["fix_patch"]))
            classified = classify_response(
                task=task,
                response=_oracle_response(str(task["fix_patch"])),
                execution=execution,
                trusted_oracle_patch=True,
            )
            record = {
                "schema_version": SCHEMA_VERSION,
                "task_id": task_id,
                "oracle_cache_key": cache_key,
                "setup_valid": (
                    classified["all_tests_pass"]
                    and int(classified.get("tests_collected") or 0) > 0
                    and execution.get("returncode") == 0
                ),
                "reason": classified["reason"],
                "tests_collected": classified.get("tests_collected"),
                "image": lock["tasks"][task_id]["digest"],
                "execution": execution,
            }
        oracles.append(record)
        persist(
            {
                f"data/oracle.records/{task_id}.json": record,
                "data/oracle.records.jsonl": _jsonl(oracles),
            }
        )
    oracle_summary = {
        "schema_version": SCHEMA_VERSION,
        "expected_task_count": EXPECTED_CPP_TASKS,
        "record_count": len(oracles),
        "passed_count": sum(
            row.get("setup_valid") is True for row in oracles
        ),
        "all_passed": (
            len(oracles) == EXPECTED_CPP_TASKS
            and all(row.get("setup_valid") is True for row in oracles)
        ),
        "correct_answer_source": "fix_patch",
        "provenance": {
            "mode": (
                "cross-run-import"
                if config.oracle_source_run_id
                else "current-run-execution-or-resume"
            ),
            "source_run_id": config.oracle_source_run_id or None,
            "exact_cache_keys": True,
            "fallback_to_execution": False,
        },
    }
    persist({"data/oracle.summary.json": oracle_summary})
    if not oracle_summary["all_passed"]:
        raise ModalAgenticMultiSweError(
            "all-task oracle admission failed"
        )

    prior_workspaces = dict(workspace_records or {})
    workspaces: list[dict[str, Any]] = []
    for task in sorted(tasks, key=lambda row: row["instance_id"]):
        task_id = task["instance_id"]
        prior = prior_workspaces.get(task_id)
        prior_submodules = (
            _workspace_submodules(prior)
            if isinstance(prior, Mapping)
            else {}
        )
        expected_prior_key = workspace_cache_key(
            {**task, "submodule_identities": prior_submodules},
            lock["tasks"][task_id]["digest"],
        )
        if (
            isinstance(prior, Mapping)
            and prior.get("workspace_cache_key") == expected_prior_key
            and prior.get("passed") is True
        ):
            record = dict(prior)
        else:
            if config.workspace_source_run_id:
                raise ModalAgenticMultiSweError(
                    f"workspace import cache mismatch for {task_id}"
                )
            proof = workspace_probe(task)
            sanitizer = proof.get("sanitizer")
            submodules = (
                sanitizer.get("submodule_identities", {})
                if isinstance(sanitizer, Mapping)
                else {}
            )
            cache_key = workspace_cache_key(
                {**task, "submodule_identities": submodules},
                lock["tasks"][task_id]["digest"],
            )
            record = {
                "schema_version": SCHEMA_VERSION,
                "task_id": task_id,
                "workspace_cache_key": cache_key,
                "passed": proof.get("passed") is True,
                "proof": proof,
            }
        workspaces.append(record)
        persist(
            {
                f"data/workspace.records/{task_id}.json": record,
                "data/workspace.records.jsonl": _jsonl(workspaces),
            }
        )
    workspace_summary = build_workspace_summary(workspaces)
    persist({"data/workspace.summary.json": workspace_summary})
    if not workspace_summary["all_passed"]:
        raise ModalAgenticMultiSweError(
            "all-task workspace admission failed"
        )
    return {
        "tasks": tasks,
        "oracle_records": oracles,
        "oracle_summary": oracle_summary,
        "workspace_records": workspaces,
        "workspace_summary": workspace_summary,
    }


def _run_trajectories(
    *,
    name: str,
    config: ModalAgenticMultiSweConfig,
    lock: Mapping[str, Any],
    tasks: list[dict[str, Any]],
    staged: Mapping[str, Any],
    run_trajectory: RunTrajectory,
    grade: Grade,
    release_gpu: Callable[[], None],
    persist: Persist,
    prior_results: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior_results = dict(prior_results or {})
    results: dict[str, dict[str, Any]] = {}

    def execute(task: dict[str, Any]) -> dict[str, Any]:
        task_id = task["instance_id"]
        prior = prior_results.get(task_id)
        prompt = str(task["agent_problem_statement"])
        prompt_sha256 = hashlib.sha256(prompt.encode()).hexdigest()
        if (
            isinstance(prior, Mapping)
            and prior.get("complete") is True
            and prior.get("task_id") == task_id
            and prior.get("identity_sha256") == config.identity_sha256()
            and prior.get("prompt_sha256") == prompt_sha256
            and isinstance(prior.get("trajectory"), Mapping)
            and isinstance(prior.get("finalization"), Mapping)
            and isinstance(prior.get("final_state_manifest"), list)
            and isinstance(prior.get("workspace_receipt"), Mapping)
        ):
            prior_finalization = prior["finalization"]
            prior_patch = str(prior_finalization.get("patch") or "")
            prior_patch_sha256 = prior_finalization.get("patch_sha256")
            if prior_patch_sha256 not in {
                None,
                hashlib.sha256(prior_patch.encode()).hexdigest(),
            }:
                raise ModalAgenticMultiSweError(
                    f"resumed final patch hash changed for {task_id}"
                )
            return dict(prior)
        failures = []
        for attempt in (1, 2):
            try:
                value = run_trajectory({**task, "_agentic_stage": name}, attempt)
                if not isinstance(value.get("trajectory"), Mapping):
                    raise ModalAgenticMultiSweError(
                        "trajectory callback returned no safe receipt"
                    )
                if not isinstance(value.get("finalization"), Mapping):
                    raise ModalAgenticMultiSweError(
                        "trajectory callback returned no finalization"
                    )
                expected_prompt_sha256 = task.get(
                    "agent_problem_statement_sha256"
                )
                if expected_prompt_sha256 not in {None, prompt_sha256}:
                    raise ModalAgenticMultiSweError(
                        "agent problem statement hash changed"
                    )
                finalization = value["finalization"]
                patch = str(finalization.get("patch") or "")
                expected_patch_sha256 = finalization.get("patch_sha256")
                if expected_patch_sha256 and expected_patch_sha256 != (
                    hashlib.sha256(patch.encode()).hexdigest()
                ):
                    raise ModalAgenticMultiSweError(
                        "trusted final patch hash changed"
                    )
                return {
                    "schema_version": SCHEMA_VERSION,
                    "task_id": task_id,
                    "identity_sha256": config.identity_sha256(),
                    "prompt_sha256": prompt_sha256,
                    "complete": True,
                    "attempt": attempt,
                    **value,
                }
            except Exception as exc:
                failures.append(
                    {
                        "attempt": attempt,
                        "exception_type": type(exc).__name__,
                        "message_sha256": hashlib.sha256(
                            str(exc).encode()
                        ).hexdigest(),
                    }
                )
                persist(
                    {
                        (
                            f"{name}/incomplete-attempts/"
                            f"{task_id}.attempt-{attempt}.json"
                        ): failures[-1]
                    }
                )
        raise ModalAgenticMultiSweError(
            f"trajectory infrastructure failed twice for {task_id}"
        )

    with ThreadPoolExecutor(
        max_workers=config.agent_concurrency
    ) as pool:
        futures = {
            pool.submit(execute, task): task for task in tasks
        }
        for future in as_completed(futures):
            task = futures[future]
            result = future.result()
            task_id = task["instance_id"]
            results[task_id] = result
            trajectory = dict(result["trajectory"])
            trajectory["task_id"] = task_id
            finalization = dict(result["finalization"])
            events = list(trajectory.get("events") or [])
            tool_events = list(trajectory.get("tool_events") or [])
            trajectory_summary = {
                key: value
                for key, value in trajectory.items()
                if key not in {"events", "tool_events"}
            }
            files: dict[str, Any] = {
                f"{name}/prompts/{task_id}.txt": str(
                    task["agent_problem_statement"]
                ),
                f"{name}/trajectory-results/{task_id}.json": result,
                f"{name}/trajectories/{task_id}/identity.json": {
                    "task_id": task_id,
                    "identity_sha256": result["identity_sha256"],
                    "prompt_sha256": result["prompt_sha256"],
                },
                f"{name}/trajectories/{task_id}/events.jsonl": _jsonl(events),
                f"{name}/trajectories/{task_id}/summary.json": trajectory_summary,
                f"{name}/trajectories/{task_id}/final.patch": str(
                    finalization.get("patch") or ""
                ),
                f"{name}/trajectories/{task_id}/final-patch.receipt.json": (
                    {key: value for key, value in finalization.items() if key != "patch"}
                ),
                f"{name}/trajectories/{task_id}/final-state.manifest.json": (
                    result.get("final_state_manifest") or []
                ),
                f"{name}/patches/{task_id}.patch": str(
                    finalization.get("patch") or ""
                ),
            }
            workspace_receipt = result.get("workspace_receipt")
            if isinstance(workspace_receipt, Mapping):
                files[
                    f"{name}/trajectories/{task_id}/workspace.receipt.json"
                ] = dict(workspace_receipt)
            for index, event in enumerate(tool_events):
                files[
                    f"{name}/trajectories/{task_id}/tool-logs/{index:04d}.json"
                ] = event
            persist(files)
    if len(results) != len(tasks):
        raise ModalAgenticMultiSweError(
            "trajectory set is incomplete"
        )
    release_gpu()

    def score(task: dict[str, Any]) -> dict[str, Any]:
        result = results[task["instance_id"]]
        finalization = result["finalization"]
        execution = None
        if finalization.get("status") == "valid_patch":
            execution = grade(task, str(finalization["patch"]))
        record = classify_agentic_result(
            task=task,
            finalization=finalization,
            execution=execution,
            trajectory=result["trajectory"],
        )
        record["infrastructure_retries"] = int(result["attempt"]) - 1
        return record

    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=GRADER_CONCURRENCY) as pool:
        futures = {pool.submit(score, task): task for task in tasks}
        for future in as_completed(futures):
            task = futures[future]
            record = future.result()
            records.append(record)
            persist(
                {
                    f"{name}/records/{task['instance_id']}.json": record
                }
            )
    records.sort(key=lambda row: row["task_id"])
    trajectories = [
        {
            "task_id": task_id,
            **results[task_id]["trajectory"],
        }
        for task_id in sorted(results)
    ]
    patches = [
        {
            "task_id": task_id,
            "patch_sha256": hashlib.sha256(
                str(results[task_id]["finalization"].get("patch") or "").encode()
            ).hexdigest(),
            "status": results[task_id]["finalization"].get("status"),
        }
        for task_id in sorted(results)
    ]
    provenance = {
        "model_repo": MODEL_REPO,
        "model_revision": config.model_revision,
        "dataset_repo": DATASET_REPO,
        "dataset_revision": config.dataset_revision,
        "sglang_image": config.sglang_image,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "modal_sdk_pin": MODAL_SDK_PIN,
        "swe_agent_commit": config.redacted_mapping()["swe_agent_commit"],
        "source_commit": config.source_commit,
        "image_lock_sha256": lock["sha256"],
        "task_ids": sorted(results),
        "one_trajectory_per_task": True,
        "harness_backend": "fresh-modal-sandbox",
        "gpu_released_before_grading": True,
    }
    summary = aggregate_agentic_records(
        records,
        oracle_summary=staged["oracle_summary"],
        workspace_summary=staged["workspace_summary"],
        provenance=provenance,
    )
    persist(
        {
            f"{name}/trajectories.jsonl": _jsonl(trajectories),
            f"{name}/patches.jsonl": _jsonl(patches),
            f"{name}/records.jsonl": _jsonl(records),
            f"{name}/summary.json": summary,
        }
    )
    return records, summary


def evaluate(
    *,
    config: ModalAgenticMultiSweConfig,
    lock: Mapping[str, Any],
    staged: Mapping[str, Any],
    run_trajectory: RunTrajectory,
    grade: Grade,
    release_gpu: Callable[[], None],
    acquire_gpu: Callable[[], None] | None = None,
    persist: Persist,
    resume_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run fixed smoke or the one-trajectory-per-task full result."""

    resume_state = resume_state or {}
    tasks = list(staged["tasks"])
    selected = (
        tasks
        if config.phase == "full"
        else [
            task
            for task in tasks
            if task["instance_id"] in SMOKE_TASK_IDS
        ]
    )
    if config.phase == "smoke" and len(selected) != len(SMOKE_TASK_IDS):
        raise ModalAgenticMultiSweError(
            "fixed smoke task set is incomplete"
        )
    name = "full" if config.phase == "full" else "smoke"
    if config.phase == "full":
        smoke_tasks = [
            task
            for task in tasks
            if task["instance_id"] in SMOKE_TASK_IDS
        ]
        if len(smoke_tasks) != len(SMOKE_TASK_IDS):
            raise ModalAgenticMultiSweError(
                "fixed smoke task set is incomplete"
            )
        _run_trajectories(
            name="smoke",
            config=config,
            lock=lock,
            tasks=smoke_tasks,
            staged=staged,
            run_trajectory=run_trajectory,
            grade=grade,
            release_gpu=release_gpu,
            persist=persist,
            prior_results=resume_state.get("smoke"),
        )
        if acquire_gpu is None:
            raise ModalAgenticMultiSweError(
                "full evaluation requires GPU reacquisition after smoke"
            )
        acquire_gpu()
    records, summary = _run_trajectories(
        name=name,
        config=config,
        lock=lock,
        tasks=selected,
        staged=staged,
        run_trajectory=run_trajectory,
        grade=grade,
        release_gpu=release_gpu,
        persist=persist,
        prior_results=resume_state.get(name),
    )
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "complete" if config.phase == "full" else "smoke_complete"
        ),
        "benchmark": BENCHMARK_LABEL,
        "result_family": RESULT_FAMILY,
        "run_id": config.run_id,
        "model_repo": MODEL_REPO,
        "model_revision": config.model_revision,
        "dataset_repo": DATASET_REPO,
        "dataset_revision": config.dataset_revision,
        "expected_tasks": len(selected),
        "completed_tasks": len(records),
        "strict_pass_rate": summary["pass_rate"],
        "oracle_passed": staged["oracle_summary"]["passed_count"],
        "workspace_passed": staged["workspace_summary"]["passed"],
        "modal_app_name": config.app_name,
        "modal_app_stopped": False,
        "teardown_status": "pending_local_control_plane_verification",
    }
    persist({"run_receipt.json": receipt})
    return {"receipt": receipt, "summary": summary}
