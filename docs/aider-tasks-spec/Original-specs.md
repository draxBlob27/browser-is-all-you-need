# Original Aider Polyglot C++ Task Specification

## Scope and terminology

This document describes the on-disk shape of an original C++ task in the
upstream [`Aider-AI/polyglot-benchmark`](https://github.com/Aider-AI/polyglot-benchmark)
checkout. The example is the upstream `grade-school` exercise at:

```text
cpp/exercises/practice/grade-school/
```

The task is an Exercism C++ exercise adapted for file-editing evaluation. A
model receives the instructions and the editable starter files, returns whole
file replacements, and the harness builds and tests a clean copy of the task.

This is a specification of the upstream task pattern, not authorization to
modify the official benchmark. The official 26 C++ Aider Polyglot roots are
evaluation-only and must remain disjoint from locally authored tasks. Current
work is confined to the clean-room curricula in `docs/aider-synthetic/` and
their generated artifacts in `.w8-biayn/data/aider-tasks/`; see
[`AIDER_SFT_SCOPE.md`](AIDER_SFT_SCOPE.md). No local task is thereby an SFT
row, training authorization, or benchmark result.

## Canonical directory layout

```text
<task-slug>/
├── .docs/
│   └── instructions.md
├── .meta/
│   ├── config.json
│   ├── example.cpp
│   ├── example.h
│   └── tests.toml
├── CMakeLists.txt
├── <task_name>.cpp
├── <task_name>.h
├── <task_name>_test.cpp
└── test/
    ├── catch.hpp
    └── tests-main.cpp
```

Names vary by exercise. A task may be header-only, use multiple solution files,
or include `introduction.md` and `instructions.append.md`; the metadata must
declare the actual file roles. The Grade School task uses `grade_school.*`.

## Role of every file and directory

| Path | Role | Model-visible/editable? |
| --- | --- | --- |
| `.docs/` | Task documentation. The repository prompt builder concatenates `introduction.md`, `instructions.md`, and `instructions.append.md`, in that order, when present. | Visible; never editable. |
| `.docs/instructions.md` | The behavioral contract, examples, domain rules, and edge cases. It should define what correct code must do without revealing the reference implementation. | Visible; never editable. |
| `.meta/` | Metadata and oracle/reference material. It is excluded from editable files and from the generated model prompt. | Hidden; never editable. |
| `.meta/config.json` | Declares the task's `files.solution`, `files.test`, and `files.example` roles, plus the blurb, source, and attribution. It is the authoritative role map. | Hidden; never editable. |
| `.meta/example.cpp` | Correct reference implementation for the corresponding editable `.cpp` file. It is used only for the blocking oracle setup check. | Hidden; never editable. |
| `.meta/example.h` | Correct reference header for the corresponding editable `.h` file. | Hidden; never editable. |
| `.meta/tests.toml` | Stable test-case IDs and descriptions for the Exercism canonical test data. It documents coverage intent; the C++ test source is what executes. | Hidden; never editable. |
| `CMakeLists.txt` | Reproducible CMake build recipe. Upstream tasks select C++17, compile the solution and test files, and configure Catch2. The evaluation harness runs CMake and Make; the model must not edit this file. | Hidden from the prompt; never editable. |
| `<task_name>.h` | Public starter interface. It defines types and declarations the tests compile against. A model may replace it only when it appears in `files.solution`. | Visible and editable when declared as a solution file. |
| `<task_name>.cpp` | Starter implementation. It normally contains stubs or incomplete code. A model may replace it only when it appears in `files.solution`. | Visible and editable when declared as a solution file. |
| `<task_name>_test.cpp` | Canonical Catch2 assertions. It contains the executable correctness cases; some upstream tasks guard the full suite with `EXERCISM_RUN_ALL_TESTS`. | Hidden from the prompt; never editable. |
| `test/catch.hpp` | Vendored Catch2 single-header test framework. Keep it pinned and unchanged for a task. | Hidden from the prompt; never editable. |
| `test/tests-main.cpp` | Defines Catch2's `main` function for local upstream builds. | Hidden from the prompt; never editable. |

The task root can also contain support files needed by a build. Treat support,
test, metadata, documentation, build, and reference files as non-editable
unless they are explicitly listed in `files.solution`.

## Metadata contract

` .meta/config.json` must have a `files` object with three lists:

```json
{
  "files": {
    "solution": ["widget.cpp", "widget.h"],
    "test": ["widget_test.cpp"],
    "example": [".meta/example.cpp", ".meta/example.h"]
  },
  "blurb": "One-sentence behavioral description.",
  "source": "Problem provenance"
}
```

Rules enforced by the current repository integration:

- Every listed path must be a safe, relative path: no absolute paths and no
  `..` segments.
- The solution list is the complete edit allowlist. Do not put tests, CMake
  files, docs, or `.meta` files in it.
- The test and example lists are removed from the editable set. All files under
  `.docs/` and `.meta/`, and `CMakeLists.txt`, are also removed.
- At least one example file is required for oracle admission.
- Each `.meta/example.*` file must map to exactly one solution file by file
  extension. Therefore, do not declare two editable C++ files, or two editable
  headers, if the simple example-file mapping would be ambiguous.
- A header-only reference is valid: an unmatched inert starter `.cpp` remains
  in place during the oracle check.

The leading space before `.meta` in the heading above is not part of the path;
the required path is `.meta/config.json`.

## Build and test contract

For the original C++ task pattern, `CMakeLists.txt` should:

1. build one test executable from the test source, declared solution files,
   and (for local builds) `test/tests-main.cpp`;
2. use C++17 without compiler extensions;
3. enable strict warnings (`-Wall -Wextra -Wpedantic -Werror`) for GCC/Clang;
4. support `-DEXERCISM_RUN_ALL_TESTS=1` so the complete suite runs; and
5. execute the resulting binary through a named CMake test target.

The repo-owned Polyglot evaluator grades a copied task by running:

```bash
mkdir -p build
cd build
cmake -DEXERCISM_RUN_ALL_TESTS=1 -G "Unix Makefiles" ..
make
```

Consequently, a task is not admitted merely because the starter code builds.
The reference files must first be copied onto their mapped solution paths and
pass the same Docker grader. A missing reference, a wrong mapping, a build
failure, a failing test, or a zero-test build is an admission failure.

## Model interaction contract

The prompt contains only:

1. a request to edit a C++ Exercism exercise;
2. the documentation files listed above;
3. the paths of all declared solution files; and
4. the full current contents of those solution files.

Tests, reference answers, CMake configuration, and task metadata are not
shown. A valid model answer must replace every editable file and nothing else:

````text
```path
relative/path/from/exercise/root.cpp
```

```cpp
complete replacement file contents
```
````

There must be one path block followed by one C++ block for each declared
solution file, with no prose or additional fenced blocks outside that pattern.
The evaluator rejects unknown paths, omitted solution files, tests, examples,
build files, and explanations. Design a task so its intended repair is
expressible as complete replacements of the declared files.

## Guide for authoring a new, benchmark-shaped training task

### 1. Keep the task clean-room and out of the official checkout

- Do not add, edit, or copy a task under `.cache/upstreams/aider-polyglot` or
  `.w8-biayn/data/polyglot-benchmark`; those are upstream evaluation inputs.
- Do not reproduce an official task's wording, public API, tests, reference
  code, solution structure, or a near-duplicate algorithmic instance.
- Start from an independently authored problem statement and implementation.
  Record its source, author, license/terms, and creation method.
- Run clean-room benchmark-contamination and family-duplication review before
  retaining a local task. Exclude all 26 official Aider Polyglot C++ roots and
  related copies.

### 2. Define a narrow, testable behavior

- Give the task a unique kebab-case slug and a matching snake_case C++ base
  name, for example `bounded-window` and `bounded_window.{h,cpp}`.
- Write `.docs/instructions.md` in terms of inputs, outputs, invariants,
  errors, ordering, ownership, bounds, and examples. State any C++ API
  precisely enough for a solver to compile against it.
- Make the starter solution incomplete but coherent: headers compile, stubs are
  obvious, and the task has a meaningful implementation target.
- Prefer a compact, self-contained interface over environment-dependent work,
  external services, or non-deterministic timing.

### 3. Declare files correctly

- List every and only editable production file in `files.solution`.
- Put tests in `files.test` and reference replacements in `files.example`.
- Keep the reference files under `.meta/` with the same extensions as their
  mapped solution files. Ensure exactly one solution file exists per reference
  extension.
- Do not make tests, CMake files, helper tools, fixtures, or documentation
  editable. A task that needs an editable fixture does not match this
  whole-file solution contract without an integration change.
- Include meaningful `blurb`, attribution, and source fields. Do not falsely
  attribute an original task to Exercism or Aider.

### 4. Build a deterministic, complete test suite

- Use Catch2 and one `*_test.cpp` test source, with `test/tests-main.cpp` and a
  pinned `test/catch.hpp` if following the upstream layout exactly.
- Cover normal behavior, edge cases, invalid input/error semantics where the
  API defines them, and regressions that distinguish plausible incorrect
  solutions from the reference.
- Enable the full suite under `EXERCISM_RUN_ALL_TESTS`; avoid tests that only
  run in a local default configuration.
- Keep all tests deterministic and offline. Do not depend on wall-clock time,
  random seeds, network access, global machine state, or undefined behavior.
- Compile cleanly with C++17 and strict warnings. Make each test failure
  actionable from the documented contract.

### 5. Add an independent reference oracle

- Write `.meta/example.*` as a complete, readable correct solution, not a copy
  of the intended model answer or a test-specific hard-coded implementation.
- Verify that reference files can replace the declared solution files without
  changing any other file.
- Confirm that the reference passes the exact Docker/CMake grader before the
  task is admitted. This is a setup proof, not model performance.
- Keep the oracle, tests, and any hidden fixtures out of all training prompts,
  model rows, and exported model-facing bundles.

### 6. Validate before using the task for training

At minimum, perform these checks in a clean copy of the task:

```bash
cmake -S . -B build -DEXERCISM_RUN_ALL_TESTS=1 -G "Unix Makefiles"
cmake --build build
./build/<task-slug>
```

Record the strongest available local evidence under the current scope. Do not
create an ad-hoc JSONL conversion, training run, or dataset-release claim from
these task artifacts.

## Pre-admission checklist

- [ ] Task is outside both upstream Polyglot checkout locations.
- [ ] Source, authoring method, license/usage terms, and provenance are
      recorded.
- [ ] No whole-task, API, wording, test, or semantic near-match with an
      official Aider Polyglot C++ root.
- [ ] `.docs/instructions.md` fully specifies the behavior without revealing
      the reference solution.
- [ ] `files.solution`, `files.test`, and `files.example` are complete,
      safe, and mutually role-correct.
- [ ] Every reference file maps unambiguously to one solution file by suffix.
- [ ] The reference solution passes every test in the locked C++17 Docker
      grader with `EXERCISM_RUN_ALL_TESTS=1`.
- [ ] Tests are deterministic, non-empty, offline, and sufficiently
      discriminating.
- [ ] Prompts expose only documentation and starter solution files.
- [ ] The task has been reviewed against the current local authoring scope and
      has no benchmark-overlap or family-duplication finding.

## What this does not change

Creating benchmark-shaped training tasks does not extend or alter the official
Aider Polyglot benchmark. Keep evaluation reports tied to the immutable
upstream commit and its official C++ task set. Report improvements on that
benchmark separately from training-task oracle results, and do not call a
repo-owned SLIME result an official Aider leaderboard score.
