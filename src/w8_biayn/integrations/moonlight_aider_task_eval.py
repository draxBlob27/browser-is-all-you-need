"""Probe an OpenAI-compatible model on one Aider-style C++ task and grade it."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.error import URLError
from urllib.request import urlopen

from w8_biayn.integrations.moonlight_single_sample_probe import (
    _request_json,
    extract_content,
    normalize_base_url,
    resolve_model,
    summarize_whole_format,
)

DEFAULT_BASE_URL = "http://127.0.0.1:30000"
DEFAULT_MODEL = "auto"

PROMPT_PREFIX = """Use Aider whole edit format. Modify the supplied editable files to solve the task. Return only complete file listings. Each fenced block must be preceded by the bare filename on the line immediately before the fence. Do not return a diff. Do not include test files, reference example files, or explanatory prose in the answer."""
PROMPT_SUFFIX = """Do not change the names of existing functions, classes, namespaces, or files, as they may be referenced from unit tests. Only use standard libraries unless the starter task already requires a provided dependency."""


class TaskEvalError(RuntimeError):
    """The local task could not be evaluated."""


class WholeFormatError(ValueError):
    """The saved response does not satisfy Aider whole-file block shape."""


@dataclass(frozen=True)
class AiderTask:
    task_dir: Path
    task_id: str
    editable_files: tuple[str, ...]
    introduction: str
    instructions: str


@dataclass(frozen=True)
class EvalResult:
    passed: bool
    summary_path: Path
    response_path: Path
    work_dir: Path


def default_output_dir(task_id: str, run_id: str | None = None) -> Path:
    resolved_run_id = run_id or os.environ.get("SLIME_RUN_ID") or "moonlight-aider-task-probe"
    return (
        Path(".w8-biayn")
        / "slime"
        / "moonlight-cpp-perf"
        / "runs"
        / resolved_run_id
        / "task-evals"
        / task_id
    )


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _load_solution_files_from_config(task_dir: Path) -> tuple[str, ...]:
    config_path = task_dir / ".meta" / "config.json"
    if not config_path.exists():
        return ()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    files = config.get("files") if isinstance(config, dict) else None
    solution = files.get("solution") if isinstance(files, dict) else None
    if not isinstance(solution, list):
        return ()
    result: list[str] = []
    for item in solution:
        if not isinstance(item, str):
            raise TaskEvalError(f"non-string solution file in {config_path}: {item!r}")
        result.append(item)
    return tuple(result)


def _validate_relative_file(filename: str) -> str:
    if not filename:
        raise WholeFormatError("missing filename before code fence")
    if filename.startswith("```"):
        raise WholeFormatError("code fence cannot be used as a filename")
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts:
        raise WholeFormatError(f"unsafe filename in response: {filename!r}")
    return path.as_posix()


def load_task(task_dir: Path | str, *, editable_files: Sequence[str] | None = None) -> AiderTask:
    root = Path(task_dir)
    if not root.exists() or not root.is_dir():
        raise TaskEvalError(f"task directory does not exist: {root}")
    files = tuple(editable_files or _load_solution_files_from_config(root))
    if not files:
        raise TaskEvalError(
            f"no editable files supplied and {root / '.meta' / 'config.json'} has no files.solution list"
        )
    normalized = tuple(_validate_relative_file(filename) for filename in files)
    missing = [filename for filename in normalized if not (root / filename).exists()]
    if missing:
        raise TaskEvalError(f"editable files missing from task directory: {missing}")
    return AiderTask(
        task_dir=root,
        task_id=root.name,
        editable_files=normalized,
        introduction=_read_optional(root / ".docs" / "introduction.md"),
        instructions=_read_optional(root / ".docs" / "instructions.md"),
    )


def _fence_language(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return "cpp" if suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"} else ""


def build_prompt(task: AiderTask) -> str:
    sections = [PROMPT_PREFIX]
    if task.introduction:
        sections.extend(["# Introduction", task.introduction])
    if task.instructions:
        sections.extend(["# Instructions", task.instructions])
    sections.append("# Supplied editable files")
    file_blocks: list[str] = []
    for filename in task.editable_files:
        language = _fence_language(filename)
        fence = f"```{language}" if language else "```"
        content = (task.task_dir / filename).read_text(encoding="utf-8").rstrip()
        file_blocks.append(f"{filename}\n{fence}\n{content}\n```")
    sections.append("\n\n".join(file_blocks))
    sections.append(PROMPT_SUFFIX)
    return "\n\n".join(sections)


def build_request(
    *,
    model: str,
    prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    top_p: float = 1.0,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }


def parse_whole_file_blocks(content: str) -> dict[str, str]:
    lines = content.splitlines()
    files: dict[str, str] = {}
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith("```"):
            index += 1
            continue
        filename = _validate_relative_file(lines[index - 1].strip() if index > 0 else "")
        body: list[str] = []
        index += 1
        while index < len(lines) and not lines[index].strip().startswith("```"):
            body.append(lines[index])
            index += 1
        if index >= len(lines):
            raise WholeFormatError(f"unclosed code fence for {filename}")
        if filename in files:
            raise WholeFormatError(f"duplicate file listing for {filename}")
        files[filename] = "\n".join(body).rstrip() + "\n"
        index += 1
    if not files:
        raise WholeFormatError("response contains no fenced file listings")
    return files


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: object) -> None:
    _write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def _run_command(command: list[str], *, cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )


def _copy_task_to_work(task: AiderTask, work_dir: Path) -> Path:
    task_work_dir = work_dir / "task"
    if task_work_dir.exists():
        shutil.rmtree(task_work_dir)
    shutil.copytree(task.task_dir, task_work_dir, ignore=shutil.ignore_patterns(".git", "build"))
    return task_work_dir


def grade_response(
    *,
    task: AiderTask,
    response_path: Path,
    out: Path,
    timeout_seconds: int = 120,
) -> EvalResult:
    out.mkdir(parents=True, exist_ok=True)
    work_dir = out / "work"
    response = response_path.read_text(encoding="utf-8")
    summary: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "task_id": task.task_id,
        "task_dir": str(task.task_dir),
        "response_path": str(response_path),
        "expected_files": list(task.editable_files),
        "whole_format": summarize_whole_format(response),
        "work_dir": str(work_dir),
    }

    try:
        parsed = parse_whole_file_blocks(response)
    except WholeFormatError as exc:
        summary.update({"parse_ok": False, "passed": False, "failure_reason": str(exc)})
        summary_path = out / "summary.json"
        _write_json(summary_path, summary)
        return EvalResult(False, summary_path, response_path, work_dir)

    missing = [filename for filename in task.editable_files if filename not in parsed]
    extra = sorted(filename for filename in parsed if filename not in task.editable_files)
    summary.update(
        {
            "parse_ok": True,
            "materialized_files": sorted(parsed),
            "missing_files": missing,
            "extra_files": extra,
        }
    )
    if missing or extra:
        summary.update(
            {
                "passed": False,
                "failure_reason": "missing_or_extra_files",
            }
        )
        summary_path = out / "summary.json"
        _write_json(summary_path, summary)
        return EvalResult(False, summary_path, response_path, work_dir)

    task_work_dir = _copy_task_to_work(task, work_dir)
    for filename in task.editable_files:
        _write_text(task_work_dir / filename, parsed[filename])

    if not (task_work_dir / "CMakeLists.txt").exists():
        summary.update({"passed": False, "failure_reason": "missing_cmake_lists"})
        summary_path = out / "summary.json"
        _write_json(summary_path, summary)
        return EvalResult(False, summary_path, response_path, work_dir)

    build_dir = task_work_dir / "build"
    configure_command = ["cmake", "-S", ".", "-B", "build", "-DEXERCISM_RUN_ALL_TESTS=ON"]
    build_command = ["cmake", "--build", "build", "--parallel", "2"]
    try:
        configure_result = _run_command(configure_command, cwd=task_work_dir, timeout_seconds=timeout_seconds)
    except FileNotFoundError:
        summary.update({"passed": False, "failure_reason": "cmake_not_found"})
        summary_path = out / "summary.json"
        _write_json(summary_path, summary)
        return EvalResult(False, summary_path, response_path, work_dir)
    _write_text(out / "configure.stdout.txt", configure_result.stdout)
    _write_text(out / "configure.stderr.txt", configure_result.stderr)
    summary.update(
        {
            "configure_command": configure_command,
            "configure_returncode": configure_result.returncode,
            "configure_stdout_path": "configure.stdout.txt",
            "configure_stderr_path": "configure.stderr.txt",
        }
    )
    if configure_result.returncode != 0:
        summary.update({"passed": False, "failure_reason": "configure_failed"})
        summary_path = out / "summary.json"
        _write_json(summary_path, summary)
        return EvalResult(False, summary_path, response_path, work_dir)

    build_result = _run_command(build_command, cwd=task_work_dir, timeout_seconds=timeout_seconds)
    _write_text(out / "build.stdout.txt", build_result.stdout)
    _write_text(out / "build.stderr.txt", build_result.stderr)
    passed = build_result.returncode == 0
    summary.update(
        {
            "build_dir": str(build_dir),
            "build_command": build_command,
            "build_returncode": build_result.returncode,
            "build_stdout_path": "build.stdout.txt",
            "build_stderr_path": "build.stderr.txt",
            "passed": passed,
            "failure_reason": None if passed else "build_or_tests_failed",
        }
    )
    summary_path = out / "summary.json"
    _write_json(summary_path, summary)
    return EvalResult(passed, summary_path, response_path, work_dir)


def run_eval(
    *,
    task_dir: Path,
    editable_files: Sequence[str] | None,
    base_url: str,
    model: str,
    out: Path | None,
    run_id: str | None,
    max_tokens: int,
    temperature: float,
    top_p: float,
    api_key: str | None,
    response_path: Path | None = None,
    timeout_seconds: int = 120,
    opener: Callable[..., Any] = urlopen,
) -> EvalResult:
    task = load_task(task_dir, editable_files=editable_files)
    output_dir = out or default_output_dir(task.task_id, run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(task)
    _write_text(output_dir / "prompt.txt", prompt)

    resolved_response_path = response_path
    resolved_model = model
    request_payload: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None
    content = response_path.read_text(encoding="utf-8") if response_path else None
    if response_path is None:
        resolved_model = resolve_model(base_url, model, api_key=api_key, opener=opener)
        request_payload = build_request(
            model=resolved_model,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        raw_response = _request_json(
            f"{normalize_base_url(base_url)}/v1/chat/completions",
            method="POST",
            payload=request_payload,
            api_key=api_key,
            opener=opener,
        )
        content = extract_content(raw_response)
        resolved_response_path = output_dir / "response.txt"
        _write_json(output_dir / "response.json", raw_response)
        _write_text(resolved_response_path, content)

    prompt_record = {
        "created_at": datetime.now(UTC).isoformat(),
        "task_id": task.task_id,
        "task_dir": str(task.task_dir),
        "editable_files": list(task.editable_files),
        "base_url": normalize_base_url(base_url),
        "model": resolved_model,
        "api_key_present": bool(api_key),
        "request": request_payload,
        "response_path": str(resolved_response_path),
    }
    _write_json(output_dir / "prompt.json", prompt_record)
    result = grade_response(
        task=task,
        response_path=resolved_response_path,
        out=output_dir / "grade",
        timeout_seconds=timeout_seconds,
    )
    return result


def _split_files(values: Sequence[str]) -> tuple[str, ...] | None:
    if not values:
        return None
    result: list[str] = []
    for value in values:
        result.extend(part for part in value.split(",") if part)
    return tuple(result)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send one Aider-style C++ task to a model, save the response, apply it, and run tests."
    )
    parser.add_argument("--task-dir", type=Path, required=True, help="Aider/Polyglot-style C++ task directory.")
    parser.add_argument(
        "--editable-file",
        action="append",
        default=[],
        help="Editable solution file. Repeat or pass comma-separated values. Defaults to .meta/config.json files.solution.",
    )
    parser.add_argument("--base-url", default=os.environ.get("SLIME_PROBE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("SLIME_PROBE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--run-id", default=os.environ.get("SLIME_RUN_ID"))
    parser.add_argument("--response", type=Path, default=None, help="Existing response.txt to grade without calling model.")
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("SLIME_PROBE_MAX_TOKENS", "2048")))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("SLIME_PROBE_TEMPERATURE", "0")))
    parser.add_argument("--top-p", type=float, default=float(os.environ.get("SLIME_PROBE_TOP_P", "1")))
    parser.add_argument("--api-key-env", default="SGLANG_API_KEY")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    try:
        result = run_eval(
            task_dir=args.task_dir,
            editable_files=_split_files(args.editable_file),
            base_url=args.base_url,
            model=args.model,
            out=args.out,
            run_id=args.run_id,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            api_key=api_key,
            response_path=args.response,
            timeout_seconds=args.timeout_seconds,
        )
    except URLError as exc:
        raise SystemExit(
            f"Could not reach {normalize_base_url(args.base_url)}. Start the OpenAI-compatible model server first."
        ) from exc
    except (TaskEvalError, WholeFormatError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"response_text={result.response_path}")
    print(f"grade_summary={result.summary_path}")
    print(f"work_dir={result.work_dir}")
    print(f"passed={1 if result.passed else 0}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
