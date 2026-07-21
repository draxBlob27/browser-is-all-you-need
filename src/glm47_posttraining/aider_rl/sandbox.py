"""Pinned Docker-only grader for untrusted Aider whole-file C++ edits."""

from __future__ import annotations

import os
import re
import subprocess
import time
import hashlib
from functools import lru_cache
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from .admission import AdmissionError, safe_copy_tree, verify_task_tree
from .schema import AiderHarnessResult, AiderTask, RubricHarnessResult, StageResult


DEFAULT_GRADER_IMAGE = "glm47-aider-cpp-grader:1"
GRADER_IMAGE_ENV = "GLM47_AIDER_GRADER_IMAGE"
DEFAULT_MEMORY = "2g"
DISCOVERED_RE = re.compile(r"Total Tests:\s*(\d+)")
FAILED_RE = re.compile(r"(\d+)\s+tests? failed out of\s+(\d+)", re.IGNORECASE)
DOCKER_INFRASTRUCTURE_MARKERS = (
    "cannot connect to the docker daemon",
    "error response from daemon",
    "error creating overlay mount",
    "failed to create shim task",
    "no such image",
    "pull access denied",
)


class AiderSandboxInfrastructureError(RuntimeError):
    """Docker or the locked grader image failed outside policy control."""


def docker_base_args(
    scratch: str | Path,
    *,
    image: str,
    memory: str = DEFAULT_MEMORY,
) -> list[str]:
    """Locked container prefix; scratch is the only persistent writable mount."""

    return [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--network",
        "none",
        "--cpus",
        "1",
        "--memory",
        memory,
        "--pids-limit",
        "128",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=128m,mode=1777",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--ulimit",
        "fsize=1073741824:1073741824",
        "-v",
        f"{Path(scratch).resolve()}:/work:rw",
        "-w",
        "/work",
        image,
    ]


def grader_image_id(image: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise AiderSandboxInfrastructureError(result.stderr.strip() or f"cannot inspect {image}")
    return result.stdout.strip()


@lru_cache(maxsize=8)
def grader_compiler_fingerprint(image_digest: str) -> str:
    """Fingerprint the compiler in the immutable grader image."""

    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            image_digest,
            "g++",
            "--version",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise AiderSandboxInfrastructureError(
            result.stderr.strip() or "cannot fingerprint grader compiler"
        )
    normalized = "\n".join(line.rstrip() for line in result.stdout.strip().splitlines()) + "\n"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def run_in_sandbox(
    task: AiderTask,
    files: Mapping[str, str],
    task_tree: Path,
) -> AiderHarnessResult:
    """Grade one complete candidate in fresh normal and sanitizer task copies."""

    try:
        verify_task_tree(task, task_tree)
        _validate_candidate_files(task, files)
    except (AdmissionError, ValueError, OSError) as exc:
        return AiderHarnessResult(
            unsafe_edit=True,
            logs={"validation": str(exc)},
            task_digest=task.task_digest,
            grader_image_digest=task.grader_image_digest,
        )

    image = os.environ.get(GRADER_IMAGE_ENV, task.grader_image or DEFAULT_GRADER_IMAGE)
    try:
        actual_image = grader_image_id(image)
    except (AiderSandboxInfrastructureError, OSError, subprocess.SubprocessError) as exc:
        return _infrastructure_result(task, str(exc))
    if actual_image != task.grader_image_digest:
        return _infrastructure_result(task, "grader image digest does not match admitted task")
    try:
        actual_compiler = grader_compiler_fingerprint(actual_image)
    except (AiderSandboxInfrastructureError, OSError, subprocess.SubprocessError) as exc:
        return _infrastructure_result(task, str(exc))
    if actual_compiler != task.compiler_fingerprint:
        return _infrastructure_result(task, "compiler fingerprint does not match admitted task")

    try:
        with TemporaryDirectory(prefix="glm47-aider-grade-") as temp:
            scratch = Path(temp)
            normal_task = safe_copy_tree(task_tree, scratch / "task-normal")
            _apply_files(normal_task, files)
            result = AiderHarnessResult(
                grader_image_digest=actual_image,
                task_digest=task.task_digest,
            )
            if not _run_normal(task, result, scratch, normal_task, actual_image):
                return result
            sanitizer_task = safe_copy_tree(task_tree, scratch / "task-sanitizer")
            _apply_files(sanitizer_task, files)
            _run_sanitizer(task, result, scratch, sanitizer_task, actual_image)
            return result
    except AiderSandboxInfrastructureError as exc:
        return _infrastructure_result(task, str(exc))
    except (OSError, subprocess.SubprocessError) as exc:
        return _infrastructure_result(task, f"grader host failure: {exc}")


def _run_normal(
    task: AiderTask,
    result: AiderHarnessResult,
    scratch: Path,
    tree: Path,
    image: str,
) -> bool:
    build = scratch / "build-normal"
    configure = _run(task.build.configure, scratch, tree, build, image, task.build.configure_timeout_s)
    result.logs["normal_configure"] = configure[1]
    if configure[0] != 0:
        result.configure_error = True
        result.timeout = configure[2]
        return False
    solution_build = _run(
        task.build.build_solution, scratch, tree, build, image, task.build.build_timeout_s
    )
    result.logs["normal_build_solution"] = solution_build[1]
    if solution_build[0] != 0:
        result.compile_error = True
        result.timeout = solution_build[2]
        return False
    test_build = _run(
        task.build.build_tests, scratch, tree, build, image, task.build.build_timeout_s
    )
    result.logs["normal_build_tests"] = test_build[1]
    if test_build[0] != 0:
        result.compile_error = True
        result.timeout = test_build[2]
        return False
    visible = _run_suite(
        task.build.discover_visible,
        task.build.run_visible,
        task.visible_tests.expected_count,
        scratch,
        tree,
        build,
        image,
        task.build.test_timeout_s,
    )
    result.normal_visible, result.logs["normal_visible"] = visible
    if result.normal_visible.discovered != task.visible_tests.expected_count:
        result.infrastructure_error = True
        result.infrastructure_reason = "normal visible test discovery mismatch"
        return False
    hidden = _run_suite(
        task.build.discover_hidden,
        task.build.run_hidden,
        task.hidden_tests.expected_count,
        scratch,
        tree,
        build,
        image,
        task.build.test_timeout_s,
    )
    result.normal_hidden, result.logs["normal_hidden"] = hidden
    if result.normal_hidden.discovered != task.hidden_tests.expected_count:
        result.infrastructure_error = True
        result.infrastructure_reason = "normal hidden test discovery mismatch"
        return False
    result.timeout = visible[0].timed_out or hidden[0].timed_out
    if not _run_rubrics(task, result, scratch, tree, build, image, sanitizer=False):
        return False
    return result.normal_all_pass


def _run_sanitizer(
    task: AiderTask,
    result: AiderHarnessResult,
    scratch: Path,
    tree: Path,
    image: str,
) -> None:
    build = scratch / "build-sanitizer"
    configure = _run(
        task.build.sanitizer_configure,
        scratch,
        tree,
        build,
        image,
        task.build.configure_timeout_s,
    )
    result.logs["sanitizer_configure"] = configure[1]
    if configure[0] != 0:
        result.sanitizer_error = True
        result.timeout = configure[2]
        return
    solution_build = _run(
        task.build.sanitizer_build_solution,
        scratch,
        tree,
        build,
        image,
        task.build.build_timeout_s,
    )
    result.logs["sanitizer_build_solution"] = solution_build[1]
    if solution_build[0] != 0:
        result.sanitizer_error = True
        result.timeout = solution_build[2]
        return
    test_build = _run(
        task.build.sanitizer_build_tests,
        scratch,
        tree,
        build,
        image,
        task.build.build_timeout_s,
    )
    result.logs["sanitizer_build_tests"] = test_build[1]
    if test_build[0] != 0:
        result.sanitizer_error = True
        result.timeout = test_build[2]
        return
    visible = _run_suite(
        task.build.sanitizer_discover_visible,
        task.build.sanitizer_run_visible,
        task.visible_tests.expected_count,
        scratch,
        tree,
        build,
        image,
        task.build.test_timeout_s,
    )
    hidden = _run_suite(
        task.build.sanitizer_discover_hidden,
        task.build.sanitizer_run_hidden,
        task.hidden_tests.expected_count,
        scratch,
        tree,
        build,
        image,
        task.build.test_timeout_s,
    )
    result.sanitizer_visible, result.logs["sanitizer_visible"] = visible
    result.sanitizer_hidden, result.logs["sanitizer_hidden"] = hidden
    if (
        result.sanitizer_visible.discovered != task.visible_tests.expected_count
        or result.sanitizer_hidden.discovered != task.hidden_tests.expected_count
    ):
        result.infrastructure_error = True
        result.infrastructure_reason = "sanitizer test discovery mismatch"
        return
    result.timeout = result.timeout or visible[0].timed_out or hidden[0].timed_out
    if not _run_rubrics(task, result, scratch, tree, build, image, sanitizer=True):
        return
    result.sanitizer_error = not (
        visible[0].passed
        and hidden[0].passed
        and visible[0].discovered == result.normal_visible.discovered
        and hidden[0].discovered == result.normal_hidden.discovered
    )


def _run_rubrics(
    task: AiderTask,
    result: AiderHarnessResult,
    scratch: Path,
    tree: Path,
    build: Path,
    image: str,
    *,
    sanitizer: bool,
) -> bool:
    """Run every private rubric partition independently for diagnostic reward."""

    existing = {item.rubric_id: item for item in result.rubric_results}
    for rubric in task.rubrics:
        rubric_result = existing.get(rubric.rubric_id)
        if rubric_result is None:
            rubric_result = RubricHarnessResult(rubric_id=rubric.rubric_id)
            result.rubric_results.append(rubric_result)
        for group in rubric.test_groups:
            discover = group.sanitizer_discover if sanitizer else group.discover
            run = group.sanitizer_run if sanitizer else group.run
            stage, log = _run_suite(
                discover,
                run,
                group.expected_count,
                scratch,
                tree,
                build,
                image,
                task.build.test_timeout_s,
            )
            stage_name = f"{'sanitizer' if sanitizer else 'normal'}_{group.visibility}"
            setattr(rubric_result, stage_name, stage)
            result.logs[f"rubric:{rubric.rubric_id}:{stage_name}"] = log
            if stage.discovered != group.expected_count:
                result.infrastructure_error = True
                result.infrastructure_reason = (
                    f"{stage_name} rubric test discovery mismatch: {rubric.rubric_id}"
                )
                return False
            result.timeout = result.timeout or stage.timed_out
    return True


def _run_suite(
    discover_argv: Sequence[str],
    run_argv: Sequence[str],
    expected_count: int,
    scratch: Path,
    tree: Path,
    build: Path,
    image: str,
    timeout_s: int,
) -> tuple[StageResult, str]:
    started = time.monotonic()
    discovery = _run(discover_argv, scratch, tree, build, image, timeout_s)
    match = DISCOVERED_RE.search(discovery[1])
    discovered = int(match.group(1)) if match else 0
    if discovery[0] != 0 or discovered <= 0 or discovered != expected_count:
        return (
            StageResult(
                attempted=True,
                returncode=discovery[0],
                timed_out=discovery[2],
                discovered=discovered,
                duration_s=time.monotonic() - started,
            ),
            discovery[1],
        )
    execution = _run(run_argv, scratch, tree, build, image, timeout_s)
    failed_match = FAILED_RE.search(execution[1])
    failed = int(failed_match.group(1)) if failed_match else (0 if execution[0] == 0 else discovered)
    passed = max(0, discovered - failed)
    stage = StageResult(
        attempted=True,
        passed=execution[0] == 0 and passed == discovered,
        timed_out=execution[2],
        returncode=execution[0],
        discovered=discovered,
        passed_tests=passed,
        duration_s=time.monotonic() - started,
    )
    return stage, discovery[1] + "\n" + execution[1]


def _run(
    argv: Sequence[str],
    scratch: Path,
    tree: Path,
    build: Path,
    image: str,
    timeout_s: int,
) -> tuple[int, str, bool]:
    expanded = [
        token.replace("{task}", f"/work/{tree.relative_to(scratch).as_posix()}").replace(
            "{build}", f"/work/{build.relative_to(scratch).as_posix()}"
        )
        for token in argv
    ]
    command = docker_base_args(scratch, image=image) + expanded
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return 124, output[-16_384:], True
    output = (completed.stdout + "\n" + completed.stderr)[-16_384:]
    lowered = output.lower()
    if any(marker in lowered for marker in DOCKER_INFRASTRUCTURE_MARKERS):
        raise AiderSandboxInfrastructureError(output.strip())
    return completed.returncode, output, False


def _validate_candidate_files(task: AiderTask, files: Mapping[str, str]) -> None:
    if tuple(files) != task.allowed_paths:
        raise ValueError("candidate file set or order differs from task allowlist")
    for editable in task.editable_files:
        if len(files[editable.path].encode("utf-8")) > editable.max_bytes:
            raise ValueError(f"candidate file is oversized: {editable.path}")


def _apply_files(root: Path, files: Mapping[str, str]) -> None:
    for relative, content in files.items():
        target = (root / relative).resolve(strict=False)
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise AdmissionError("candidate path escapes fresh task copy") from exc
        if not target.is_file() or target.is_symlink():
            raise AdmissionError(f"candidate target is not a trusted regular file: {relative}")
        target.write_text(content, encoding="utf-8")


def _infrastructure_result(task: AiderTask, reason: str) -> AiderHarnessResult:
    return AiderHarnessResult(
        infrastructure_error=True,
        infrastructure_reason=reason,
        logs={"infrastructure": reason},
        grader_image_digest=task.grader_image_digest,
        task_digest=task.task_digest,
    )
