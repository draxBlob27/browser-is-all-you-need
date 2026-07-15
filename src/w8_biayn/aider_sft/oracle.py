"""Image-bound, network-disabled executable oracle for canonical tasks."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .errors import AiderSftError
from .source_exercism import load_canonical_task
from .util import (
    fingerprint,
    hash_file_records,
    normalize_relative_path,
    read_json,
    sha256_bytes,
    sha256_file,
    tree_files,
    validate_regular_file,
    write_json,
)

_TEST_COUNT_RE = re.compile(r"(?m)^\s*(\d+)\s+test cases?\s*$")


def inspect_image_id(image: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format={{.Id}}", image],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise AiderSftError("retryable_error", f"Docker image unavailable: {image}")
    return result.stdout.strip()


def _oracle_input_files(task_root: Path) -> dict[str, bytes]:
    return {
        relative: payload
        for relative, payload in tree_files(task_root).items()
        if not relative.startswith("receipts/")
    }


def _oracle_input_tree_sha256(task_root: Path) -> str:
    return hash_file_records(
        "aider-sft-oracle-task-input-v1",
        _oracle_input_files(task_root),
    )


def assemble_workspace(
    *,
    task_root: Path,
    state: str,
    shared_support_root: Path,
    destination: Path,
) -> dict[str, Any]:
    if state not in {"starter", "reference"}:
        raise ValueError(state)
    task = load_canonical_task(task_root)
    destination.mkdir(parents=True, exist_ok=False)
    mappings = task.grader["workspace_assembly"]["file_mappings"]
    written: dict[str, bytes] = {}

    def install(relative: str, payload: bytes) -> None:
        relative = normalize_relative_path(relative)
        if relative in written:
            raise AiderSftError("static_schema_error", f"workspace role collision: {relative}")
        written[relative] = payload
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        path.chmod(0o644)

    for mapping in mappings:
        destination_path = mapping["destination"]
        if "shared_bundle" in mapping:
            source = (
                shared_support_root
                / mapping["shared_bundle"]
                / normalize_relative_path(mapping["source"])
            )
        else:
            source = task_root / normalize_relative_path(mapping["source"])
        if not source.is_file() or source.is_symlink():
            raise AiderSftError("static_schema_error", f"assembly source missing: {source}")
        install(destination_path, source.read_bytes())

    state_root = task_root / "workspace" / state
    for relative, payload in tree_files(state_root).items():
        install(relative, payload)
    context_root = task_root / "workspace/context"
    for relative, payload in tree_files(context_root).items():
        install(relative, payload)

    expected_editable = set(task.files.editable)
    if not expected_editable <= set(written):
        raise AiderSftError("missing_editable_files", "assembled state lacks editable files")
    manifest = {
        "schema_version": "aider-sft-workspace-assembly-v1",
        "task_id": task.task_id,
        "state": state,
        "files": [
            {"path": path, "bytes": len(payload), "sha256": sha256_bytes(payload)}
            for path, payload in sorted(written.items())
        ],
        "tree_sha256": hash_file_records("aider-sft-workspace-v1", written),
    }
    return manifest


def _docker_prefix(
    *,
    mount_parent: Path,
    workdir_name: str,
    task_grader: dict[str, Any],
    environment: dict[str, str],
) -> list[str]:
    sandbox = task_grader["sandbox"]
    limits = task_grader["limits"]
    if (
        sandbox["network"] != "none"
        or not sandbox["read_only_rootfs"]
        or not sandbox["run_as_non_root"]
        or not sandbox["no_new_privileges"]
        or sandbox["cap_drop"] != ["ALL"]
    ):
        raise AiderSftError("sandbox_policy_mismatch", "sandbox policy is weaker than V1")
    seccomp_value = os.environ.get("W8_AIDER_SFT_SECCOMP_PROFILE", "")
    if not seccomp_value:
        raise AiderSftError(
            "sandbox_policy_mismatch",
            "set W8_AIDER_SFT_SECCOMP_PROFILE to the fingerprinted seccomp JSON",
        )
    seccomp_path = Path(seccomp_value)
    validate_regular_file(seccomp_path)
    if sha256_file(seccomp_path) != sandbox["seccomp_profile_sha256"]:
        raise AiderSftError("sandbox_policy_mismatch", "seccomp profile hash differs")
    command = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--network",
        "none",
        "--cpus",
        str(limits["cpus"]),
        "--memory",
        f"{limits['memory_mib']}m",
        "--pids-limit",
        str(limits["pids"]),
        "--ulimit",
        (f"fsize={limits['file_size_mib'] * 1024 * 1024}:{limits['file_size_mib'] * 1024 * 1024}"),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--security-opt",
        f"seccomp={seccomp_path.resolve()}",
        "-v",
        f"{mount_parent.resolve()}:/work:rw",
        "-w",
        f"/work/{workdir_name}",
    ]
    for key, value in sorted(environment.items()):
        if key not in {"LC_ALL", "TZ", "ASAN_OPTIONS", "UBSAN_OPTIONS"}:
            raise AiderSftError("sandbox_policy_mismatch", f"undeclared environment: {key}")
        command.extend(["-e", f"{key}={value}"])
    command.append(task_grader["image"])
    return command


def _run_phase(
    argv: list[str],
    *,
    mount_parent: Path,
    workdir_name: str,
    grader: dict[str, Any],
    environment: dict[str, str],
    timeout_seconds: int,
    tail_bytes: int,
) -> dict[str, Any]:
    command = (
        _docker_prefix(
            mount_parent=mount_parent,
            workdir_name=workdir_name,
            task_grader=grader,
            environment=environment,
        )
        + argv
    )
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
        timeout = False
        returncode = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        timeout = True
        returncode = None
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
    elapsed_ms = round((time.monotonic() - started) * 1000)
    return {
        "argv": argv,
        "environment": dict(sorted(environment.items())),
        "returncode": returncode,
        "timeout": timeout,
        "elapsed_ms": elapsed_ms,
        "stdout": {
            "bytes": len(stdout),
            "sha256": sha256_bytes(stdout),
            "tail": stdout[-tail_bytes:].decode("utf-8", errors="replace"),
        },
        "stderr": {
            "bytes": len(stderr),
            "sha256": sha256_bytes(stderr),
            "tail": stderr[-tail_bytes:].decode("utf-8", errors="replace"),
        },
    }


def _test_count(receipt: dict[str, Any]) -> int:
    text = receipt["stdout"]["tail"] + "\n" + receipt["stderr"]["tail"]
    matches = _TEST_COUNT_RE.findall(text)
    if not matches:
        raise AiderSftError("test_discovery_failed", "Catch list-tests count is absent")
    count = int(matches[-1])
    if count <= 0:
        raise AiderSftError("zero_tests", "Catch discovered zero tests")
    return count


def _require_success(receipt: dict[str, Any], reason: str) -> None:
    if receipt["timeout"]:
        raise AiderSftError("reference_timeout", f"{reason}: command timed out")
    if receipt["returncode"] != 0:
        raise AiderSftError(reason, f"{reason}: command returned {receipt['returncode']}")


def _require_discovery(receipt: dict[str, Any], reason: str) -> int:
    if receipt["timeout"]:
        raise AiderSftError("reference_timeout", f"{reason}: command timed out")
    count = _test_count(receipt)
    if receipt["returncode"] not in {0, count}:
        raise AiderSftError(
            reason,
            f"{reason}: command returned {receipt['returncode']}, discovered {count}",
        )
    return count


def run_task_oracle(
    *,
    task_root: Path,
    shared_support_root: Path,
    config_lock: dict[str, Any],
    scratch_parent: Path | None = None,
) -> dict[str, Any]:
    task = load_canonical_task(task_root)
    grader = task.grader
    expected_toolchain = config_lock["config"]["toolchain"]
    if (
        grader.get("image") != expected_toolchain["docker_image"]
        or grader.get("image_id") != expected_toolchain["docker_image_id"]
        or grader.get("sandbox") != config_lock["config"]["sandbox"]
    ):
        raise AiderSftError("sandbox_policy_mismatch", "task sandbox identity differs from lock")
    if grader["cmake_generator"] != "Unix Makefiles":
        raise AiderSftError("cmake_generator_mismatch", "generator must be Unix Makefiles")
    observed_image_id = inspect_image_id(grader["image"])
    if observed_image_id != grader["image_id"]:
        raise AiderSftError("sandbox_policy_mismatch", "Docker image ID differs from lock")
    if grader["toolchain"] != {
        "cxx_path": expected_toolchain["cxx_path"],
        "cxx_version": expected_toolchain["cxx_version"],
        "cxx_binary_sha256": expected_toolchain["cxx_binary_sha256"],
    }:
        raise AiderSftError("compiler_identity_mismatch", "task compiler identity differs")
    tail_bytes = config_lock["config"]["limits"]["command_tail_bytes"]
    scratch_base = Path(
        tempfile.mkdtemp(prefix=f"aider-sft-oracle-{task.task_id}-", dir=scratch_parent)
    )
    try:
        phases: dict[str, Any] = {}
        assemblies: dict[str, Any] = {}

        starter_parent = scratch_base / "starter"
        starter_workspace = starter_parent / task.task_id
        assemblies["starter"] = assemble_workspace(
            task_root=task_root,
            state="starter",
            shared_support_root=shared_support_root,
            destination=starter_workspace,
        )
        environment = grader["environment"]
        phases["starter_configure"] = _run_phase(
            grader["configure_argv"],
            mount_parent=starter_parent,
            workdir_name=task.task_id,
            grader=grader,
            environment=environment,
            timeout_seconds=grader["configure_timeout_seconds"],
            tail_bytes=tail_bytes,
        )
        _require_success(phases["starter_configure"], "starter_harness_error")
        phases["starter_compile"] = _run_phase(
            grader["compile_argv"],
            mount_parent=starter_parent,
            workdir_name=task.task_id,
            grader=grader,
            environment=environment,
            timeout_seconds=grader["compile_timeout_seconds"],
            tail_bytes=tail_bytes,
        )
        starter_compiled = phases["starter_compile"]["returncode"] == 0
        starter_test_count = None
        if starter_compiled:
            phases["starter_discovery"] = _run_phase(
                grader["test_discovery_argv"],
                mount_parent=starter_parent,
                workdir_name=task.task_id,
                grader=grader,
                environment=environment,
                timeout_seconds=grader["test_timeout_seconds"],
                tail_bytes=tail_bytes,
            )
            starter_test_count = _require_discovery(
                phases["starter_discovery"],
                "starter_harness_error",
            )
            phases["starter_tests"] = _run_phase(
                grader["test_argv"],
                mount_parent=starter_parent,
                workdir_name=task.task_id,
                grader=grader,
                environment=environment,
                timeout_seconds=grader["test_timeout_seconds"],
                tail_bytes=tail_bytes,
            )
            if phases["starter_tests"]["timeout"]:
                raise AiderSftError("starter_harness_error", "starter tests timed out")
            if phases["starter_tests"]["returncode"] == 0:
                raise AiderSftError("starter_already_passes", "starter passes all tests")

        reference_parent = scratch_base / "reference"
        reference_workspace = reference_parent / task.task_id
        assemblies["reference"] = assemble_workspace(
            task_root=task_root,
            state="reference",
            shared_support_root=shared_support_root,
            destination=reference_workspace,
        )
        reference_count = None
        for name, argv, timeout, reason in (
            (
                "reference_configure",
                grader["configure_argv"],
                grader["configure_timeout_seconds"],
                "reference_compile_failed",
            ),
            (
                "reference_compile",
                grader["compile_argv"],
                grader["compile_timeout_seconds"],
                "reference_compile_failed",
            ),
            (
                "reference_discovery",
                grader["test_discovery_argv"],
                grader["test_timeout_seconds"],
                "test_discovery_failed",
            ),
            (
                "reference_tests",
                grader["test_argv"],
                grader["test_timeout_seconds"],
                "reference_tests_failed",
            ),
        ):
            phases[name] = _run_phase(
                argv,
                mount_parent=reference_parent,
                workdir_name=task.task_id,
                grader=grader,
                environment=environment,
                timeout_seconds=timeout,
                tail_bytes=tail_bytes,
            )
            if name == "reference_discovery":
                reference_count = _require_discovery(phases[name], reason)
            else:
                _require_success(phases[name], reason)
        if reference_count is None:
            raise AiderSftError("test_discovery_failed", "reference discovery did not run")

        sanitizer = grader["sanitizer"]
        sanitizer_parent = scratch_base / "sanitizer"
        sanitizer_workspace = sanitizer_parent / task.task_id
        assemblies["sanitizer_reference"] = assemble_workspace(
            task_root=task_root,
            state="reference",
            shared_support_root=shared_support_root,
            destination=sanitizer_workspace,
        )
        sanitizer_environment = {**environment, **sanitizer["environment"]}
        sanitizer_count = None
        for name, argv, reason in (
            (
                "sanitizer_configure",
                sanitizer["configure_argv"],
                "reference_sanitizer_failed",
            ),
            (
                "sanitizer_compile",
                sanitizer["compile_argv"],
                "reference_sanitizer_failed",
            ),
            (
                "sanitizer_discovery",
                sanitizer["test_discovery_argv"],
                "sanitizer_test_discovery_failed",
            ),
            (
                "sanitizer_tests",
                sanitizer["test_argv"],
                "reference_sanitizer_failed",
            ),
        ):
            phases[name] = _run_phase(
                argv,
                mount_parent=sanitizer_parent,
                workdir_name=task.task_id,
                grader=grader,
                environment=sanitizer_environment,
                timeout_seconds=sanitizer["timeout_seconds"],
                tail_bytes=tail_bytes,
            )
            if name == "sanitizer_discovery":
                sanitizer_count = _require_discovery(phases[name], reason)
            else:
                _require_success(phases[name], reason)
        if sanitizer_count is None:
            raise AiderSftError(
                "sanitizer_test_discovery_failed",
                "sanitizer discovery did not run",
            )
        if sanitizer_count != reference_count:
            raise AiderSftError(
                "sanitizer_test_count_mismatch",
                f"normal={reference_count}, sanitizer={sanitizer_count}",
            )

        negative_root = task_root / "grader/negative-solutions"
        negative_dirs = (
            sorted(path for path in negative_root.iterdir() if path.is_dir())
            if negative_root.is_dir()
            else []
        )
        killed_negatives: list[str] = []
        if task.source.kind.value == "llm_assisted" and len(negative_dirs) < 3:
            raise AiderSftError("weak_generated_tests", "fewer than three negative solutions")
        for negative_dir in negative_dirs:
            negative_id = normalize_relative_path(negative_dir.name)
            negative_parent = scratch_base / f"negative-{negative_id}"
            negative_workspace = negative_parent / task.task_id
            assemble_workspace(
                task_root=task_root,
                state="reference",
                shared_support_root=shared_support_root,
                destination=negative_workspace,
            )
            replacements = tree_files(negative_dir)
            if set(replacements) != set(task.files.editable):
                raise AiderSftError(
                    "weak_generated_tests",
                    f"negative {negative_id} does not replace every editable file",
                )
            for relative, payload in replacements.items():
                (negative_workspace / relative).write_bytes(payload)
            assemblies[f"negative:{negative_id}"] = {
                "schema_version": "aider-sft-workspace-assembly-v1",
                "task_id": task.task_id,
                "state": f"negative:{negative_id}",
                "tree_sha256": hash_file_records(
                    "aider-sft-negative-workspace-v1",
                    tree_files(negative_workspace),
                ),
            }
            for suffix, argv, reason in (
                ("configure", grader["configure_argv"], "weak_generated_tests"),
                ("compile", grader["compile_argv"], "weak_generated_tests"),
                ("discovery", grader["test_discovery_argv"], "weak_generated_tests"),
            ):
                name = f"negative_{negative_id}_{suffix}"
                phases[name] = _run_phase(
                    argv,
                    mount_parent=negative_parent,
                    workdir_name=task.task_id,
                    grader=grader,
                    environment=environment,
                    timeout_seconds=grader["compile_timeout_seconds"],
                    tail_bytes=tail_bytes,
                )
                if suffix == "discovery":
                    _require_discovery(phases[name], reason)
                else:
                    _require_success(phases[name], reason)
            test_name = f"negative_{negative_id}_tests"
            phases[test_name] = _run_phase(
                grader["test_argv"],
                mount_parent=negative_parent,
                workdir_name=task.task_id,
                grader=grader,
                environment=environment,
                timeout_seconds=grader["test_timeout_seconds"],
                tail_bytes=tail_bytes,
            )
            if phases[test_name]["timeout"] or phases[test_name]["returncode"] == 0:
                raise AiderSftError(
                    "weak_generated_tests",
                    f"negative {negative_id} was not killed by the full test set",
                )
            killed_negatives.append(negative_id)
        mutation = {
            "schema_version": "aider-sft-mutation-receipt-v1",
            "task_id": task.task_id,
            "status": "passed" if negative_dirs else "source_official_tests",
            "compileable_negatives": len(negative_dirs),
            "killed_negatives": killed_negatives,
        }
        mutation["mutation_fingerprint"] = fingerprint("aider-sft-mutation-receipt-v1", mutation)
        write_json(task_root / "receipts/mutation.json", mutation)

        input_fingerprint = fingerprint(
            "aider-sft-oracle-input-v1",
            read_json(task_root / "task.json"),
            _oracle_input_tree_sha256(task_root),
            read_json(shared_support_root / "manifest.json"),
            config_lock["lock_sha256"],
            observed_image_id,
        )
        receipt = {
            "schema_version": "aider-sft-oracle-receipt-v1",
            "task_id": task.task_id,
            "status": "passed",
            "input_fingerprint": input_fingerprint,
            "image_id": observed_image_id,
            "cmake_generator": grader["cmake_generator"],
            "toolchain": grader["toolchain"],
            "sandbox": grader["sandbox"],
            "assemblies": assemblies,
            "phases": phases,
            "mutation_fingerprint": mutation["mutation_fingerprint"],
            "counts": {
                "starter_compiled": starter_compiled,
                "starter_discovered": starter_test_count,
                "reference_discovered": reference_count,
                "sanitizer_discovered": sanitizer_count,
            },
        }
        receipt["oracle_fingerprint"] = fingerprint("aider-sft-oracle-receipt-v1", receipt)
        write_json(task_root / "receipts/oracle.json", receipt)
        return receipt
    finally:
        shutil.rmtree(scratch_base, ignore_errors=True)


def validate_oracle_receipt(
    *,
    task_root: Path,
    shared_support_root: Path,
    config_lock: dict[str, Any],
) -> dict[str, Any]:
    receipt = read_json(task_root / "receipts/oracle.json")
    if receipt.get("status") != "passed":
        raise AiderSftError("reference_tests_failed", "oracle receipt is not passing")
    task = load_canonical_task(task_root)
    if receipt.get("image_id") != task.grader["image_id"]:
        raise AiderSftError("sandbox_policy_mismatch", "oracle image binding is stale")
    expected = fingerprint(
        "aider-sft-oracle-input-v1",
        read_json(task_root / "task.json"),
        _oracle_input_tree_sha256(task_root),
        read_json(shared_support_root / "manifest.json"),
        config_lock["lock_sha256"],
        receipt["image_id"],
    )
    if receipt.get("input_fingerprint") != expected:
        raise AiderSftError("human_review_stale", "oracle input fingerprint is stale")
    mutation = read_json(task_root / "receipts/mutation.json")
    mutation_value = dict(mutation)
    mutation_fingerprint = mutation_value.pop("mutation_fingerprint", None)
    if mutation_fingerprint != fingerprint("aider-sft-mutation-receipt-v1", mutation_value):
        raise AiderSftError("weak_generated_tests", "mutation receipt fingerprint differs")
    if receipt.get("mutation_fingerprint") != mutation_fingerprint:
        raise AiderSftError("weak_generated_tests", "oracle mutation binding differs")
    receipt_value = dict(receipt)
    oracle_fingerprint = receipt_value.pop("oracle_fingerprint", None)
    if oracle_fingerprint != fingerprint("aider-sft-oracle-receipt-v1", receipt_value):
        raise AiderSftError("human_review_stale", "oracle receipt fingerprint differs")
    return receipt
