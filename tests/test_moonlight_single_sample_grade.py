from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_single_sample_grade as grade


VALID_RESPONSE = '''two_fer.h
```
#if !defined(TWO_FER_H)
#define TWO_FER_H

#include <string>

namespace two_fer {

std::string two_fer(const std::string& name = "you");

}  // namespace two_fer

#endif
```

two_fer.cpp
```
#include "two_fer.h"

#include <string>

namespace two_fer {

std::string two_fer(const std::string& name) {
    return "One for " + name + ", one for me.";
}

}  // namespace two_fer
```
'''


def test_parse_whole_file_blocks_extracts_expected_files() -> None:
    files = grade.parse_whole_file_blocks(VALID_RESPONSE)

    assert sorted(files) == ["two_fer.cpp", "two_fer.h"]
    assert "std::string two_fer" in files["two_fer.h"]
    assert "One for " in files["two_fer.cpp"]


def test_parse_whole_file_blocks_rejects_missing_filename() -> None:
    with pytest.raises(grade.WholeFormatError, match="missing filename"):
        grade.parse_whole_file_blocks("```cpp\nint main() {}\n```")


def test_grade_response_compiles_and_runs_two_fer_tests(tmp_path: Path) -> None:
    if shutil.which("g++") is None:
        pytest.skip("g++ is not available")
    response_path = tmp_path / "response.txt"
    response_path.write_text(VALID_RESPONSE, encoding="utf-8")

    result = grade.grade_response(response_path=response_path, out=tmp_path / "grade")

    assert result.passed
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["compile_returncode"] == 0
    assert summary["test_returncode"] == 0
    assert (result.work_dir / "files" / "test_two_fer.cpp").exists()


def test_grade_response_persists_parse_failure_summary(tmp_path: Path) -> None:
    response_path = tmp_path / "response.txt"
    response_path.write_text("```cpp\nint main() {}\n```", encoding="utf-8")

    result = grade.grade_response(response_path=response_path, out=tmp_path / "grade")

    assert not result.passed
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["parse_ok"] is False
    assert summary["passed"] is False
    assert "missing filename" in summary["failure_reason"]


def test_grade_wrapper_and_docs_reference_test_artifacts() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/grade_single_sample_sft_response.sh")
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111
    wrapper_text = wrapper.read_text(encoding="utf-8")
    assert "w8_biayn.integrations.moonlight_single_sample_grade" in wrapper_text
    assert "grade/two-fer" in wrapper_text

    for path in (
        Path("docs/moonlight_single_sample_sft.md"),
        Path("examples/slime/moonlight_cpp_perf/README.md"),
        Path("README.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "grade_single_sample_sft_response.sh" in text
        assert "summary.json" in text
