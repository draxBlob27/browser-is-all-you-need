from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_eval, moonlight_leap_aider_task


REFERENCE_RESPONSE = '''leap.h
```
#if !defined(LEAP_H)
#define LEAP_H

namespace leap {

bool is_leap_year(int year);

}  // namespace leap

#endif
```

leap.cpp
```
#include "leap.h"

namespace leap {

bool is_leap_year(int year) {
    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
}

}  // namespace leap
```
'''


def test_leap_task_builder_writes_aider_style_task(tmp_path: Path) -> None:
    root = tmp_path / "leap"

    paths = moonlight_leap_aider_task.build_task(root)

    assert paths.root == root
    assert paths.header == root / "leap.h"
    assert paths.source == root / "leap.cpp"
    assert paths.test == root / "leap_test.cpp"
    config = json.loads(paths.config.read_text(encoding="utf-8"))
    assert config["files"]["solution"] == ["leap.h", "leap.cpp"]
    assert config["files"]["test"] == ["leap_test.cpp"]
    assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
    assert "bool is_leap_year" not in paths.header.read_text(encoding="utf-8")
    assert "bool is_leap_year" in (root / ".meta" / "example.h").read_text(encoding="utf-8")


def test_leap_task_prompt_includes_docs_and_starter_files_not_reference(tmp_path: Path) -> None:
    root = tmp_path / "leap"
    moonlight_leap_aider_task.build_task(root)

    task = moonlight_aider_task_eval.load_task(root)
    prompt = moonlight_aider_task_eval.build_prompt(task)

    assert task.editable_files == ("leap.h", "leap.cpp")
    assert "# Introduction" in prompt
    assert "Leap years keep the calendar year synchronized" in prompt
    assert "# Instructions" in prompt
    assert "A leap year is evenly divisible by 4" in prompt
    assert "leap.h\n```cpp\n#if !defined(LEAP_H)" in prompt
    assert "leap.cpp\n```cpp\n#include \"leap.h\"" in prompt
    assert "leap_test.cpp" not in prompt
    assert ".meta/example" not in prompt
    assert "year % 4 == 0" not in prompt


def test_leap_task_reference_response_passes_grader(tmp_path: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("cmake/c++ is not available")
    root = tmp_path / "leap"
    moonlight_leap_aider_task.build_task(root)
    response = tmp_path / "response.txt"
    response.write_text(REFERENCE_RESPONSE, encoding="utf-8")

    result = moonlight_aider_task_eval.grade_response(
        task=moonlight_aider_task_eval.load_task(root),
        response_path=response,
        out=tmp_path / "grade",
    )

    assert result.passed
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["materialized_files"] == ["leap.cpp", "leap.h"]


def test_prepare_leap_task_wrapper_is_documented() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_leap_aider_task.sh")
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111
    assert "moonlight_leap_aider_task" in wrapper.read_text(encoding="utf-8")

    for path in (
        Path("README.md"),
        Path("ROADMAP.md"),
        Path("examples/slime/moonlight_cpp_perf/README.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "prepare_leap_aider_task.sh" in text
        assert ".w8-biayn/data/aider-tasks/aider-dsa/leap" in text
