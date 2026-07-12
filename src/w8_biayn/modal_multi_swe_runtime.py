"""Pure orchestration for the Modal Multi-SWE C++ lane."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.request import Request, urlopen

from w8_biayn.integrations.slime_multi_swe_cpp import parse_patch_response
from w8_biayn.modal_glm47 import MODEL_REPO, MODAL_SDK_PIN, TRANSFORMERS_COMMIT
from w8_biayn.modal_multi_swe_cpp import (
    BENCHMARK_LABEL,
    DATASET_REPO,
    EXPECTED_CPP_TASKS,
    RESULT_FAMILY,
    SCHEMA_VERSION,
    SMOKE_TASK_IDS,
    ModalMultiSweConfig,
    ModalMultiSweError,
    aggregate_records,
    classify_response,
    grader_cache_key,
    model_request,
    model_request_sha256,
    oracle_cache_key,
    render_plan,
    response_sha256,
    utc_now,
)


Persist = Callable[[dict[str, Any]], None]
Grade = Callable[[dict[str, Any], str], dict[str, Any]]


def _jsonl(rows: Sequence[Mapping[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def _oracle_response(patch: str) -> dict[str, Any]:
    fence = chr(96) * 3
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "reasoning_content": "",
                    "content": fence + "diff\n" + patch.rstrip() + "\n" + fence,
                },
            }
        ],
        "usage": {},
    }


def prepare_and_admit(
    *,
    config: ModalMultiSweConfig,
    lock: Mapping[str, Any],
    tasks: list[dict[str, Any]],
    dataset_receipt: Mapping[str, Any],
    grade: Grade,
    persist: Persist,
    resume_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all 50 fix patches before any model cache or GPU operation."""

    resume_state = resume_state or {}
    if len(tasks) != EXPECTED_CPP_TASKS:
        raise ModalMultiSweError("oracle admission requires exactly 50 tasks")
    prompts = dataset_receipt.get("prompts")
    if not isinstance(prompts, dict):
        raise ModalMultiSweError("dataset receipt has no prompt map")
    for task in tasks:
        task_id = task["instance_id"]
        task["prompt"] = prompts[task_id]["prompt"]
    prior_dataset = resume_state.get("dataset_receipt")
    if isinstance(prior_dataset, dict):
        identity_fields = (
            "dataset_repo",
            "dataset_revision",
            "raw_sha256",
            "source_rows",
            "cpp_rows",
            "task_ids",
            "image_lock_sha256",
        )
        mismatches = [
            key for key in identity_fields if prior_dataset.get(key) != dataset_receipt.get(key)
        ]
        if mismatches:
            raise ModalMultiSweError(f"resume dataset identity mismatch: {mismatches}")
    identity_files = {
        "plan.json": render_plan(config, lock),
        "config.redacted.json": config.redacted_mapping(),
        "source.receipt.json": {
            "source_commit": config.source_commit,
            "source_dirty": config.source_dirty,
            "source_file_hashes": config.source_file_hashes,
        },
        "dataset.receipt.json": dict(dataset_receipt),
        "image-lock.json": dict(lock),
        "image-lock.sha256": str(lock["sha256"]) + "\n",
    }
    source_migration = resume_state.get("oracle_source_migration")
    if isinstance(source_migration, dict):
        identity_files["data/oracle-source-migration.json"] = source_migration
    oracle_import = resume_state.get("oracle_import")
    if config.oracle_source_run_id:
        if (
            not isinstance(oracle_import, dict)
            or oracle_import.get("source_run_id") != config.oracle_source_run_id
        ):
            raise ModalMultiSweError("validated oracle import receipt is missing")
        identity_files["data/oracle-import.json"] = dict(oracle_import)
    data_files = {
        "data/sandbox-images.json": {
            "schema_version": 1,
            "mode": "checked-in-modal-lock",
            "platform": lock["platform"],
            "tasks": lock["tasks"],
        },
        "data/eval/cpp.jsonl": _jsonl(
            [{"task_id": task["instance_id"], "prompt": task["prompt"]} for task in tasks]
        ),
    }
    for task in tasks:
        data_files["data/tasks/" + task["instance_id"] + "/task.json"] = task
    if dataset_receipt.get("offline_dependencies") is not None:
        data_files["data/offline-dependencies.json"] = dataset_receipt["offline_dependencies"]
    prior_oracles = resume_state.get("oracle_records")
    if not isinstance(prior_oracles, dict):
        prior_oracles = {}
    cache_keys = {
        task["instance_id"]: oracle_cache_key(
            config,
            task,
            lock["tasks"][task["instance_id"]],
        )
        for task in tasks
    }
    if config.oracle_source_run_id:
        incompatible = sorted(
            task_id
            for task_id, cache_key in cache_keys.items()
            if not isinstance(prior_oracles.get(task_id), dict)
            or prior_oracles[task_id].get("oracle_cache_key") != cache_key
            or prior_oracles[task_id].get("setup_valid") is not True
            or prior_oracles[task_id].get("reason") != "passed"
            or int(prior_oracles[task_id].get("tests_collected") or 0) <= 0
        )
        if incompatible or set(prior_oracles) != set(cache_keys):
            raise ModalMultiSweError(
                "oracle source proof is not exact for the current run: "
                + str(incompatible or sorted(set(prior_oracles) ^ set(cache_keys)))
            )
    persist(identity_files)
    persist(data_files)
    records = []
    for index, task in enumerate(tasks, start=1):
        task_id = task["instance_id"]
        cache_key = cache_keys[task_id]
        prior = prior_oracles.get(task_id)
        reusable = (
            isinstance(prior, dict)
            and prior.get("oracle_cache_key") == cache_key
            and prior.get("setup_valid") is True
            and int(prior.get("tests_collected") or 0) > 0
        )
        if reusable:
            record = dict(prior)
        else:
            execution = grade(task, str(task["fix_patch"]))
            classified = classify_response(
                task=task,
                response=_oracle_response(str(task["fix_patch"])),
                execution=execution,
                trusted_oracle_patch=True,
            )
            setup_valid = (
                classified["all_tests_pass"]
                and int(classified.get("tests_collected") or 0) > 0
                and execution.get("returncode") == 0
            )
            record = {
                "schema_version": SCHEMA_VERSION,
                "task_id": task_id,
                "instance_id": task_id,
                "correct_answer_source": "fix_patch",
                "oracle_cache_key": cache_key,
                "setup_valid": setup_valid,
                "reason": classified["reason"],
                "tests_collected": classified.get("tests_collected"),
                "image": lock["tasks"][task_id]["digest"],
                "harness_backend": "modal-sandbox",
                "execution": execution,
            }
        records.append(record)
        ordered = sorted(records, key=lambda row: row["task_id"])
        passed = sum(bool(row["setup_valid"]) for row in ordered)
        provisional = {
            "schema_version": SCHEMA_VERSION,
            "complete": len(ordered) == EXPECTED_CPP_TASKS,
            "all_passed": passed == EXPECTED_CPP_TASKS,
            "expected_task_count": EXPECTED_CPP_TASKS,
            "record_count": len(ordered),
            "passed_count": passed,
            "correct_answer_source": "fix_patch",
            "harness_backend": "modal-sandbox",
        }
        persist(
            {
                "data/oracle.records/" + task_id + ".json": record,
                "data/oracle.records.jsonl": _jsonl(ordered),
                "data/oracle.summary.json": provisional,
                "data/manifest.json": {
                    "schema_version": 3,
                    "admitted": provisional["all_passed"],
                    "task_count": EXPECTED_CPP_TASKS,
                    "dataset_revision": config.dataset_revision,
                    "harness_backend": "modal-sandbox",
                },
            }
        )
        if reusable and config.oracle_source_run_id:
            suffix = " (imported from " + config.oracle_source_run_id + ")"
        else:
            suffix = " (reused)" if reusable else ""
        print("oracle " + str(index) + "/50 " + task_id + ": " + record["reason"] + suffix)
    records.sort(key=lambda row: row["task_id"])
    passed = sum(bool(row["setup_valid"]) for row in records)
    oracle_provenance = (
        {
            "mode": "cross-run-import",
            "source_run_id": config.oracle_source_run_id,
            "exact_oracle_cache_keys": True,
            "fallback_to_execution": False,
        }
        if config.oracle_source_run_id
        else {"mode": "current-run-execution-or-resume"}
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "complete": len(records) == EXPECTED_CPP_TASKS,
        "all_passed": passed == EXPECTED_CPP_TASKS,
        "expected_task_count": EXPECTED_CPP_TASKS,
        "record_count": len(records),
        "passed_count": passed,
        "correct_answer_source": "fix_patch",
        "harness_backend": "modal-sandbox",
        "provenance": oracle_provenance,
    }
    persist(
        {
            "data/oracle.records.jsonl": _jsonl(records),
            "data/oracle.summary.json": summary,
            "data/manifest.json": {
                "schema_version": 3,
                "admitted": summary["all_passed"],
                "task_count": EXPECTED_CPP_TASKS,
                "dataset_revision": config.dataset_revision,
                "harness_backend": "modal-sandbox",
            },
        }
    )
    if not summary["all_passed"]:
        raise ModalMultiSweError("all-task Modal oracle admission failed")
    return {"tasks": tasks, "oracle_records": records, "oracle_summary": summary}


def _request(
    *,
    server_url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    request = Request(
        server_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise ModalMultiSweError("model transport returned a non-object response")
    return value


def _run_stage(
    *,
    name: str,
    config: ModalMultiSweConfig,
    lock: Mapping[str, Any],
    tasks: list[dict[str, Any]],
    oracle_summary: Mapping[str, Any],
    server_url: str,
    api_key: str,
    grade: Grade,
    after_generation: Callable[[], None] | None = None,
    persist: Persist,
    resume_stage: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resume_stage = resume_stage or {}
    saved_requests = resume_stage.get("requests")
    saved_responses = resume_stage.get("responses")
    saved_records = resume_stage.get("records")
    saved_requests = saved_requests if isinstance(saved_requests, dict) else {}
    saved_responses = saved_responses if isinstance(saved_responses, dict) else {}
    saved_records = saved_records if isinstance(saved_records, dict) else {}
    generated = {}
    requests = {}
    generation_started = time.monotonic()
    with ThreadPoolExecutor(max_workers=config.generation_concurrency) as pool:
        futures = {}
        for task in tasks:
            request = model_request(config, task["prompt"])
            task_id = task["instance_id"]
            requests[task_id] = request
            saved_response = saved_responses.get(task_id)
            if saved_requests.get(task_id) == request and isinstance(saved_response, dict):
                generated[task_id] = saved_response
                persist(
                    {
                        name + "/requests/" + task_id + ".json": request,
                        name + "/responses/" + task_id + ".json": saved_response,
                    }
                )
                continue
            future = pool.submit(
                _request,
                server_url=server_url,
                api_key=api_key,
                payload=request,
                timeout=config.max_run_seconds,
            )
            futures[future] = (task, request)
        for future in as_completed(futures):
            task, request = futures[future]
            response = future.result()
            task_id = task["instance_id"]
            generated[task_id] = response
            persist(
                {
                    name + "/requests/" + task_id + ".json": request,
                    name + "/responses/" + task_id + ".json": response,
                }
            )
    if len(generated) != len(tasks):
        raise ModalMultiSweError("generation set is incomplete")

    generation_elapsed = time.monotonic() - generation_started
    if after_generation is not None:
        after_generation()

    def score(task: dict[str, Any]) -> dict[str, Any]:
        task_id = task["instance_id"]
        response = generated[task_id]
        cache_key = grader_cache_key(config, task, lock["tasks"][task_id], response)
        prior = saved_records.get(task_id)
        if (
            isinstance(prior, dict)
            and prior.get("request_sha256") == model_request_sha256(requests[task_id])
            and prior.get("response_sha256") == response_sha256(response)
            and prior.get("grader_cache_key") == cache_key
            and not prior.get("infrastructure_failure")
        ):
            return dict(prior)
        try:
            content = response["choices"][0]["message"]["content"]
            patch = parse_patch_response(content)
        except Exception:
            execution = None
        else:
            execution = grade(task, patch)
        record = classify_response(task=task, response=response, execution=execution)
        record["request_sha256"] = model_request_sha256(requests[task_id])
        record["grader_cache_key"] = cache_key
        if execution is not None and execution.get("returncode") in {86, 87}:
            record["infrastructure_failure"] = True
        return record

    records = []
    grading_started = time.monotonic()
    with ThreadPoolExecutor(max_workers=config.grader_concurrency) as pool:
        futures = {pool.submit(score, task): task for task in tasks}
        for future in as_completed(futures):
            task = futures[future]
            record = future.result()
            records.append(record)
            files = {name + "/records/" + task["instance_id"] + ".json": record}
            sandbox = record.get("sandbox")
            if isinstance(sandbox, dict):
                files[name + "/logs/" + task["instance_id"] + ".log"] = str(
                    sandbox.get("logs") or ""
                )
            persist(files)
    records.sort(key=lambda row: row["task_id"])
    grading_elapsed = time.monotonic() - grading_started
    finish_reasons: dict[str, int] = {}
    completion_tokens: list[int] = []
    for response in generated.values():
        choices = response.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices else {}
        finish_reason = str(choice.get("finish_reason") or "missing")
        finish_reasons[finish_reason] = finish_reasons.get(finish_reason, 0) + 1
        usage = response.get("usage")
        token_count = usage.get("completion_tokens") if isinstance(usage, dict) else None
        if isinstance(token_count, int) and not isinstance(token_count, bool):
            completion_tokens.append(token_count)
    provenance = {
        "model_repo": MODEL_REPO,
        "model_revision": config.model_revision,
        "dataset_repo": DATASET_REPO,
        "dataset_revision": config.dataset_revision,
        "sglang_image": config.sglang_image,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "modal_sdk_pin": MODAL_SDK_PIN,
        "gpu": config.gpu,
        "source_commit": config.source_commit,
        "source_file_hashes": config.source_file_hashes,
        "image_lock_sha256": lock["sha256"],
        "task_ids": sorted(task["instance_id"] for task in tasks),
        "prompt_sha256": {
            task["instance_id"]: hashlib.sha256(task["prompt"].encode()).hexdigest()
            for task in tasks
        },
        "image_digests": {
            task["instance_id"]: lock["tasks"][task["instance_id"]]["digest"] for task in tasks
        },
        "harness_backend": "modal-sandbox",
        "concurrency": {
            "generation": config.generation_concurrency,
            "grading": config.grader_concurrency,
        },
        "elapsed_seconds": {
            "generation": round(generation_elapsed, 3),
            "grading": round(grading_elapsed, 3),
        },
        "sampling": {
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
        },
        "sandbox": {
            "block_network": True,
            "cpu": config.sandbox_cpu,
            "memory_mib": config.sandbox_memory_mib,
            "timeout_seconds": config.test_timeout_seconds,
        },
        "response_distribution": {
            "finish_reasons": dict(sorted(finish_reasons.items())),
            "completion_tokens": {
                "count": len(completion_tokens),
                "min": min(completion_tokens) if completion_tokens else None,
                "max": max(completion_tokens) if completion_tokens else None,
                "total": sum(completion_tokens),
            },
        },
        "infrastructure_retries": sum(
            int((row.get("sandbox") or {}).get("infrastructure_retries") or 0) for row in records
        ),
    }
    summary = aggregate_records(
        records,
        oracle_summary=oracle_summary,
        provenance=provenance,
    )
    persist(
        {
            name + "/records.jsonl": _jsonl(records),
            name + "/summary.json": summary,
        }
    )
    return records, summary


def evaluate(
    *,
    config: ModalMultiSweConfig,
    lock: Mapping[str, Any],
    staged: Mapping[str, Any],
    server_url: str,
    api_key: str,
    grade: Grade,
    persist: Persist,
    release_gpu: Callable[[], None],
    resume_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the fixed smoke, then the full result when requested."""

    resume_state = resume_state or {}
    tasks = list(staged["tasks"])
    oracle_summary = staged["oracle_summary"]
    oracle_records = list(staged["oracle_records"])
    smoke_tasks = [task for task in tasks if task["instance_id"] in SMOKE_TASK_IDS]
    if len(smoke_tasks) != len(SMOKE_TASK_IDS):
        raise ModalMultiSweError("fixed smoke task set is incomplete")
    smoke_records, smoke_summary = _run_stage(
        name="smoke",
        config=config,
        lock=lock,
        tasks=smoke_tasks,
        oracle_summary=oracle_summary,
        server_url=server_url,
        api_key=api_key,
        grade=grade,
        persist=persist,
        resume_stage=resume_state.get("smoke"),
    )
    persist({"smoke/oracle.records.jsonl": _jsonl(oracle_records)})
    if config.phase == "full":
        records, summary = _run_stage(
            name="full",
            config=config,
            lock=lock,
            tasks=tasks,
            oracle_summary=oracle_summary,
            server_url=server_url,
            api_key=api_key,
            grade=grade,
            persist=persist,
            after_generation=release_gpu,
            resume_stage=resume_state.get("full"),
        )
        persist({"full/oracle.records.jsonl": _jsonl(oracle_records)})
        status = "complete"
    else:
        records, summary = smoke_records, smoke_summary
        status = "smoke_complete"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "benchmark": BENCHMARK_LABEL,
        "result_family": RESULT_FAMILY,
        "run_id": config.run_id,
        "model_repo": MODEL_REPO,
        "model_revision": config.model_revision,
        "dataset_repo": DATASET_REPO,
        "dataset_revision": config.dataset_revision,
        "expected_tasks": EXPECTED_CPP_TASKS if config.phase == "full" else len(SMOKE_TASK_IDS),
        "completed_tasks": len(records),
        "strict_pass_rate": summary["pass_rate"],
        "oracle_passed": oracle_summary["passed_count"],
        "oracle_source_run_id": config.oracle_source_run_id or None,
        "harness_backend": "modal-sandbox",
        "modal_app_name": config.app_name,
        "modal_app_stopped": False,
        "teardown_status": "pending_local_control_plane_verification",
        "completed_at_utc": utc_now(),
    }
    return {"receipt": receipt, "summary": summary}
