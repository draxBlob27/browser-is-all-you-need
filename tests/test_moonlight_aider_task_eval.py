from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.request import Request

import pytest

from w8_biayn.integrations import moonlight_aider_task_eval as task_eval


VALID_RESPONSE = '''hello.h
```
#pragma once

#include <string>

namespace hello {

std::string greet(const std::string& name = "you");

}  // namespace hello
```

hello.cpp
```
#include "hello.h"

#include <string>

namespace hello {

std::string greet(const std::string& name) {
    return "Hello, " + name + "!";
}

}  // namespace hello
```
'''

FAILING_RESPONSE = VALID_RESPONSE.replace('"Hello, " + name + "!"', '"Hi, " + name')


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def write_task(root: Path) -> Path:
    task_dir = root / "hello-task"
    (task_dir / ".docs").mkdir(parents=True)
    (task_dir / ".meta").mkdir()
    (task_dir / ".docs" / "introduction.md").write_text("Greeting helpers are useful.\n", encoding="utf-8")
    (task_dir / ".docs" / "instructions.md").write_text(
        "Return `Hello, <name>!` and default to `you`.\n", encoding="utf-8"
    )
    (task_dir / ".meta" / "config.json").write_text(
        json.dumps({"files": {"solution": ["hello.h", "hello.cpp"], "test": ["hello_test.cpp"]}}),
        encoding="utf-8",
    )
    (task_dir / "hello.h").write_text(
        "#pragma once\n\n#include <string>\n\nnamespace hello {\n\n}  // namespace hello\n",
        encoding="utf-8",
    )
    (task_dir / "hello.cpp").write_text(
        '#include "hello.h"\n\nnamespace hello {\n\n}  // namespace hello\n',
        encoding="utf-8",
    )
    (task_dir / "hello_test.cpp").write_text(
        '''#include "hello.h"

#include <iostream>

int main() {
    if (hello::greet() != "Hello, you!") {
        std::cerr << "default case failed\\n";
        return 1;
    }
    if (hello::greet("Ada") != "Hello, Ada!") {
        std::cerr << "named case failed\\n";
        return 1;
    }
    return 0;
}
''',
        encoding="utf-8",
    )
    (task_dir / "CMakeLists.txt").write_text(
        '''cmake_minimum_required(VERSION 3.16)
project(hello_task CXX)
add_executable(hello_task hello_test.cpp hello.cpp)
set_target_properties(hello_task PROPERTIES CXX_STANDARD 20 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)
if("${CMAKE_CXX_COMPILER_ID}" MATCHES "(GNU|Clang)")
  target_compile_options(hello_task PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
add_custom_target(test_hello_task ALL DEPENDS hello_task COMMAND hello_task)
''',
        encoding="utf-8",
    )
    return task_dir


def test_load_task_and_build_prompt_include_docs_and_starter_files(tmp_path: Path) -> None:
    task_dir = write_task(tmp_path)
    task = task_eval.load_task(task_dir)

    assert task.task_id == "hello-task"
    assert task.editable_files == ("hello.h", "hello.cpp")
    prompt = task_eval.build_prompt(task)

    assert prompt.startswith("Use Aider whole edit format.")
    assert "# Introduction" in prompt
    assert "Greeting helpers are useful." in prompt
    assert "# Instructions" in prompt
    assert "Return `Hello, <name>!`" in prompt
    assert "hello.h\n```cpp\n#pragma once" in prompt
    assert "hello.cpp\n```cpp\n#include \"hello.h\"" in prompt
    assert "hello_test.cpp" not in prompt


def test_parse_whole_file_blocks_rejects_missing_filename() -> None:
    with pytest.raises(task_eval.WholeFormatError, match="missing filename"):
        task_eval.parse_whole_file_blocks("```cpp\nint main() {}\n```")


def test_grade_response_runs_task_tests_and_persists_pass(tmp_path: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("cmake/c++ is not available")
    task = task_eval.load_task(write_task(tmp_path))
    response_path = tmp_path / "response.txt"
    response_path.write_text(VALID_RESPONSE, encoding="utf-8")

    result = task_eval.grade_response(task=task, response_path=response_path, out=tmp_path / "out")

    assert result.passed
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["parse_ok"] is True
    assert summary["build_returncode"] == 0


def test_grade_response_persists_test_failure_output(tmp_path: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("cmake/c++ is not available")
    task = task_eval.load_task(write_task(tmp_path))
    response_path = tmp_path / "response.txt"
    response_path.write_text(FAILING_RESPONSE, encoding="utf-8")

    result = task_eval.grade_response(task=task, response_path=response_path, out=tmp_path / "out")

    assert not result.passed
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["failure_reason"] == "build_or_tests_failed"
    assert "build_stdout_path" in summary
    build_output = (result.summary_path.parent / summary["build_stdout_path"]).read_text(encoding="utf-8")
    build_error = (result.summary_path.parent / summary["build_stderr_path"]).read_text(encoding="utf-8")
    assert "case failed" in build_output + build_error


def test_run_eval_saves_response_from_openai_compatible_server(tmp_path: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("cmake/c++ is not available")
    task_dir = write_task(tmp_path)
    requests: list[Request] = []

    def opener(request: Request, timeout: int) -> FakeResponse:
        assert timeout == 120
        requests.append(request)
        if request.full_url.endswith("/v1/models"):
            return FakeResponse({"data": [{"id": "base-model"}]})
        assert request.full_url.endswith("/v1/chat/completions")
        return FakeResponse({"choices": [{"message": {"content": VALID_RESPONSE}}]})

    result = task_eval.run_eval(
        task_dir=task_dir,
        editable_files=None,
        base_url="http://127.0.0.1:30000",
        model="auto",
        out=tmp_path / "eval",
        run_id=None,
        max_tokens=128,
        temperature=0,
        top_p=1,
        api_key=None,
        opener=opener,
    )

    assert len(requests) == 2
    assert result.passed
    assert result.response_path.name == "response.txt"
    prompt_record = json.loads((tmp_path / "eval" / "prompt.json").read_text(encoding="utf-8"))
    assert prompt_record["model"] == "base-model"
    assert prompt_record["editable_files"] == ["hello.h", "hello.cpp"]


def test_probe_and_grade_wrapper_is_documented() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/probe_and_grade_aider_task.sh")
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111
    assert "moonlight_aider_task_eval" in wrapper.read_text(encoding="utf-8")

    for path in (
        Path("README.md"),
        Path("ROADMAP.md"),
        Path("examples/slime/moonlight_cpp_perf/README.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "probe_and_grade_aider_task.sh" in text
        assert "response.txt" in text
        assert "grade/summary.json" in text
