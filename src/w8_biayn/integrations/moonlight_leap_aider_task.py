"""Materialize a local Aider-style Leap C++ task for response-only grading."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/leap")

FILES: Mapping[str, str] = {
    ".docs/introduction.md": """# Introduction

Leap years keep the calendar year synchronized with the astronomical year.
""",
    ".docs/instructions.md": """# Instructions

Implement a leap-year checker.

A leap year is evenly divisible by 4, except years evenly divisible by 100 are not leap years unless they are also evenly divisible by 400.
""",
    ".meta/config.json": json.dumps(
        {
            "authors": ["w8-biayn"],
            "files": {
                "solution": ["leap.h", "leap.cpp"],
                "test": ["leap_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
            "blurb": "Determine whether a year is a leap year.",
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    ".meta/tests.toml": """[leap_year]
description = "year divisible by 4 is leap year"

[common_year]
description = "year not divisible by 4 is common year"

[century]
description = "year divisible by 100 but not 400 is common year"

[four_hundred]
description = "year divisible by 400 is leap year"
""",
    ".meta/example.h": """#if !defined(LEAP_H)
#define LEAP_H

namespace leap {

bool is_leap_year(int year);

}  // namespace leap

#endif
""",
    ".meta/example.cpp": """#include "leap.h"

namespace leap {

bool is_leap_year(int year) {
    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
}

}  // namespace leap
""",
    "leap.h": """#if !defined(LEAP_H)
#define LEAP_H

namespace leap {

}  // namespace leap

#endif
""",
    "leap.cpp": """#include "leap.h"

namespace leap {

}  // namespace leap
""",
    "leap_test.cpp": """#include "leap.h"

#include <iostream>

namespace {

int failures = 0;

void check_equal(bool actual, bool expected, const char* case_name) {
    if (actual != expected) {
        std::cerr << case_name << " failed\n"
                  << "expected: " << expected << "\n"
                  << "actual:   " << actual << "\n";
        ++failures;
    }
}

}  // namespace

int main() {
    check_equal(leap::is_leap_year(1997), false, "common year");
    check_equal(leap::is_leap_year(1996), true, "typical leap year");
    check_equal(leap::is_leap_year(1900), false, "century common year");
    check_equal(leap::is_leap_year(2000), true, "four hundred year leap year");
    check_equal(leap::is_leap_year(2100), false, "future century common year");
    return failures == 0 ? 0 : 1;
}
""",
    "CMakeLists.txt": """cmake_minimum_required(VERSION 3.16)
project(leap_task CXX)

add_executable(leap leap_test.cpp leap.cpp leap.h)
set_target_properties(leap PROPERTIES
    CXX_STANDARD 20
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF
)

if("${CMAKE_CXX_COMPILER_ID}" MATCHES "(GNU|Clang)")
    target_compile_options(leap PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

add_custom_target(test_leap ALL DEPENDS leap COMMAND leap)
""",
}


@dataclass(frozen=True)
class TaskPaths:
    root: Path
    config: Path
    header: Path
    source: Path
    test: Path


def task_paths(root: Path | str) -> TaskPaths:
    root_path = Path(root)
    return TaskPaths(
        root=root_path,
        config=root_path / ".meta" / "config.json",
        header=root_path / "leap.h",
        source=root_path / "leap.cpp",
        test=root_path / "leap_test.cpp",
    )


def _write_if_same_or_forced(path: Path, content: str, *, force: bool) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
        if not force:
            raise FileExistsError(f"{path} already exists with different content; pass --force to rewrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def build_task(root: Path | str = DEFAULT_OUT, *, force: bool = False) -> TaskPaths:
    paths = task_paths(root)
    for relative, content in FILES.items():
        _write_if_same_or_forced(paths.root / relative, content, force=force)
    return paths


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize a local Aider-style Leap C++ task.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output task directory. Defaults to {DEFAULT_OUT}.")
    parser.add_argument("--force", action="store_true", help="Rewrite existing files if their content differs.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = build_task(args.out, force=args.force)
    print(f"Wrote Leap Aider task under {paths.root}")
    print(f"config={paths.config}")
    print(f"editable_files={paths.header},{paths.source}")
    print(f"test={paths.test}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
