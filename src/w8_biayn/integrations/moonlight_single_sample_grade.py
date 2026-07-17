"""Grade the saved Moonlight single-sample probe response with C++ tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_single_sample_probe import DEFAULT_PROMPT_ID, default_output_dir


EXPECTED_FILES = ("two_fer.h", "two_fer.cpp")

TEST_SOURCE = r'''#include "two_fer.h"

#include <iostream>
#include <string>

namespace {

int failures = 0;

void check_equal(const std::string& actual, const std::string& expected, const char* case_name) {
    if (actual != expected) {
        std::cerr << case_name << " failed\n"
                  << "expected: " << expected << "\n"
                  << "actual:   " << actual << "\n";
        ++failures;
    }
}

}  // namespace

int main() {
    check_equal(two_fer::two_fer(), "One for you, one for me.", "default_name");
    check_equal(two_fer::two_fer("Alice"), "One for Alice, one for me.", "alice");
    check_equal(two_fer::two_fer("Bob"), "One for Bob, one for me.", "bob");
    return failures == 0 ? 0 : 1;
}
'''


class WholeFormatError(ValueError):
    """The saved response does not satisfy the Aider whole-file block shape."""


@dataclass(frozen=True)
class GradeResult:
    passed: bool
    summary_path: Path
    work_dir: Path


def _validate_filename(filename: str) -> str:
    if not filename:
        raise WholeFormatError("missing filename before code fence")
    if filename.startswith("```"):
        raise WholeFormatError("code fence cannot be used as a filename")
    path = Path(filename)
    if path.is_absolute() or path.name != filename or ".." in path.parts:
        raise WholeFormatError(f"unsafe filename in response: {filename!r}")
    return filename


def parse_whole_file_blocks(content: str) -> dict[str, str]:
    """Parse Aider whole-format file listings from a model response."""

    lines = content.splitlines()
    files: dict[str, str] = {}
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith("```"):
            index += 1
            continue
        filename = _validate_filename(lines[index - 1].strip() if index > 0 else "")
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


def grade_response(
    *,
    response_path: Path,
    out: Path,
    compiler: str = "g++",
    timeout_seconds: int = 30,
) -> GradeResult:
    out.mkdir(parents=True, exist_ok=True)
    work_dir = out / "work"
    files_dir = work_dir / "files"
    response = response_path.read_text(encoding="utf-8")
    summary: dict[str, object] = {
        "created_at": datetime.now(UTC).isoformat(),
        "prompt_id": DEFAULT_PROMPT_ID,
        "response_path": str(response_path),
        "expected_files": list(EXPECTED_FILES),
        "work_dir": str(work_dir),
    }

    try:
        parsed = parse_whole_file_blocks(response)
        missing = [filename for filename in EXPECTED_FILES if filename not in parsed]
        extra = sorted(filename for filename in parsed if filename not in EXPECTED_FILES)
        summary.update(
            {
                "parse_ok": True,
                "materialized_files": sorted(parsed),
                "missing_files": missing,
                "extra_files": extra,
            }
        )
        if missing:
            summary["passed"] = False
            summary["failure_reason"] = "missing_expected_files"
            summary_path = out / "summary.json"
            _write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
            return GradeResult(False, summary_path, work_dir)
    except WholeFormatError as exc:
        summary.update({"parse_ok": False, "passed": False, "failure_reason": str(exc)})
        summary_path = out / "summary.json"
        _write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return GradeResult(False, summary_path, work_dir)

    for filename in EXPECTED_FILES:
        _write_text(files_dir / filename, parsed[filename])
    _write_text(files_dir / "test_two_fer.cpp", TEST_SOURCE)

    binary = work_dir / "two_fer_test"
    compile_command = [
        compiler,
        "-std=c++20",
        "-Wall",
        "-Wextra",
        "-pedantic",
        "two_fer.cpp",
        "test_two_fer.cpp",
        "-o",
        str(binary),
    ]
    try:
        compile_result = _run_command(compile_command, cwd=files_dir, timeout_seconds=timeout_seconds)
    except FileNotFoundError:
        summary.update({"passed": False, "failure_reason": f"compiler_not_found:{compiler}"})
        summary_path = out / "summary.json"
        _write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return GradeResult(False, summary_path, work_dir)
    _write_text(out / "compile.stdout.txt", compile_result.stdout)
    _write_text(out / "compile.stderr.txt", compile_result.stderr)
    summary.update(
        {
            "compile_command": compile_command,
            "compile_returncode": compile_result.returncode,
            "compile_stdout_path": "compile.stdout.txt",
            "compile_stderr_path": "compile.stderr.txt",
        }
    )
    if compile_result.returncode != 0:
        summary.update({"passed": False, "failure_reason": "compile_failed"})
        summary_path = out / "summary.json"
        _write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return GradeResult(False, summary_path, work_dir)

    test_result = _run_command([str(binary)], cwd=files_dir, timeout_seconds=timeout_seconds)
    _write_text(out / "test.stdout.txt", test_result.stdout)
    _write_text(out / "test.stderr.txt", test_result.stderr)
    passed = test_result.returncode == 0
    summary.update(
        {
            "test_returncode": test_result.returncode,
            "test_stdout_path": "test.stdout.txt",
            "test_stderr_path": "test.stderr.txt",
            "passed": passed,
            "failure_reason": None if passed else "tests_failed",
        }
    )
    summary_path = out / "summary.json"
    _write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return GradeResult(passed, summary_path, work_dir)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile and test the saved single-sample probe response.")
    parser.add_argument("--run-id", default=os.environ.get("SLIME_RUN_ID"))
    parser.add_argument("--probe-dir", type=Path, default=None)
    parser.add_argument("--response", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--compiler", default=os.environ.get("CXX", "g++"))
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    probe_dir = args.probe_dir or default_output_dir(args.run_id)
    response_path = args.response or probe_dir / "response.txt"
    out = args.out or probe_dir / "grade" / "two-fer"
    result = grade_response(
        response_path=response_path,
        out=out,
        compiler=args.compiler,
        timeout_seconds=args.timeout_seconds,
    )
    print(f"grade_summary={result.summary_path}")
    print(f"work_dir={result.work_dir}")
    print(f"passed={1 if result.passed else 0}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
