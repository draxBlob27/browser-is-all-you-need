# Single Sample For SFT

## Purpose And Scope

This document records one supervised fine-tuning sample intended to improve
model output discipline for Aider's `whole` edit format. It also distinguishes
the small synthetic row currently materialized by the repository from a
prompt-faithful training example.

The sample is a format-discipline smoke only. It is not evidence of general
file-editing ability, C++ correctness, or benchmark uplift. The originating
failure came from GLM, while the checked-in one-row writer is explicitly for
the optional Moonlight smoke.

## Issue Observed In The Model Run

The issue was found in run `glm47-p8b-20260712095217`.

Primary chat artifact:

```text
.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/glm47-p8b-20260712095217/independent-pass-at-1-and-8/sample-06/2026-07-12-19-58-13--glm47-p8b-20260712095217-sample-06/cpp/exercises/practice/gigasecond/.aider.chat.history.md
```

Matching result artifact:

```text
.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/glm47-p8b-20260712095217/independent-pass-at-1-and-8/sample-06/2026-07-12-19-58-13--glm47-p8b-20260712095217-sample-06/cpp/exercises/practice/gigasecond/.aider.results.json
```

The chat log identifies the exact configuration:

```text
# aider chat started at 2026-07-12 20:24:34

> Aider v0.86.3.dev53+g5dc9490bb
> Model: openai/glm-4.7-flash with whole edit format
> Added gigasecond.cpp to the chat.
> Added gigasecond.h to the chat.
```

The first response included explanatory prose followed by two anonymous
`cpp`-fenced blocks. Neither block had a filename immediately before its
opening fence. The key parser error was:

````text
No filename provided before ``` in file listing
````

The result records one malformed response and two failed test attempts:

```json
{
  "tests_outcomes": [false, false],
  "num_malformed_responses": 1
}
```

## Corrected Diagnosis

The parser failure was caused by missing filename lines, not by explanatory
prose.

Aider's pinned `whole` prompt asks the model to explain needed changes and then
return complete file listings. Its canned example also contains an explanation
before the listing. In the saved run, the next response still contained prose,
but added `gigasecond.h` and `gigasecond.cpp` immediately before their fenced
contents; Aider applied both edits. This confirms that prose itself was not the
blocking format error.

For every changed file, Aider requires this shape:

````text
path/to/filename.ext
```
complete file contents
```
````

Returning only listings is a valid stricter policy that reduces formatting
risk, but it must be described as a synthetic training choice rather than an
exact reproduction of Aider's prompt.

The format correction also does not address the rest of the run's failure. The
two benchmark tries still failed their tests, so this one sample cannot be used
as evidence of improved C++ correctness.

## What The Model Actually Saw

The human-readable `.aider.chat.history.md` is not the complete API request. It
omits Aider's system message, canned example, and the separate message carrying
the editable file contents. The raw OpenAI `messages` payload was not persisted
for this run, so a byte-for-byte transcript is unavailable.

The message structure can nevertheless be reconstructed from the saved run
configuration and pinned source:

- Aider commit: `5dc9490bb35f9729ef2c95d00a19ccd30c26339c`.
- Polyglot commit: `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Exact Aider prompt source:
  <https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/wholefile_prompts.py>.
- Exact message assembly:
  <https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/base_coder.py>.
- Exact benchmark task assembly:
  <https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/benchmark/benchmark.py> and
  <https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/benchmark/prompts.py>.

For the first Gigasecond request, the model-facing conversation had this
logical order:

1. A system message containing the `whole` edit-format contract.
2. A canned user/assistant example of a complete file listing.
3. A short user/assistant reset indicating a new codebase.
4. A user message containing the complete current editable files.
5. An assistant acknowledgement of those files.
6. A user message containing the full exercise introduction, instructions,
   benchmark addendum, and another `whole`-format reminder.

The fourth message contained the initial files, not the versions left behind
after Aider's edit/test/retry loop:

````text
gigasecond.cpp
```
#include "gigasecond.h"

namespace gigasecond {

}  // namespace gigasecond
```

gigasecond.h
```
#if !defined(GIGASECOND_H)
#define GIGASECOND_H

namespace gigasecond {

}  // namespace gigasecond

#endif // GIGASECOND_H
```
````

The tests, `.meta` files, and `.docs` files were excluded from the editable
file message. The task text was constructed from the `.docs` content and a
benchmark addendum naming only `gigasecond.cpp` and `gigasecond.h`.

## Dataset Design Consequences

An SFT example must include the pre-edit file contents somewhere in its input
context. A prompt that says "modify the supplied files" without supplying them
is underdetermined and encourages memorization of the synthetic Leap answer.

There are two defensible representations:

1. **Exact-Aider context.** Preserve the system prompt, canned example,
   separate editable-file turn, acknowledgement, and final task turn. Use this
   only after confirming that the SFT loader's loss mask does not unintentionally
   train the canned assistant and acknowledgement turns.
2. **Compact self-contained context.** Put the format contract, complete
   pre-edit files, and task in one user message, followed by only the desired
   assistant answer. This is not byte-for-byte Aider traffic, but it preserves
   the information needed to perform the edit and keeps the supervision target
   unambiguous.

For the current one-row smoke, the compact representation is the safer default.
It should still be validated on a held-out task through the actual Aider parser;
repeating the Leap training prompt only demonstrates memorization.

## Anatomy Of One Aider/Polyglot Task

Use `gigasecond` as the concrete task shape:

```text
cpp/exercises/practice/gigasecond/
  .docs/introduction.md
  .docs/instructions.md
  .meta/config.json
  .meta/tests.toml
  .meta/example.cpp
  .meta/example.h
  CMakeLists.txt
  gigasecond.cpp
  gigasecond.h
  gigasecond_test.cpp
  test/catch.hpp
  test/tests-main.cpp
```

Each file has a distinct role:

- `.docs/introduction.md`: background/story text. Include this in an
  Aider-like SFT prompt when it exists.
- `.docs/instructions.md`: the actual problem statement. Include this in the
  prompt.
- `.meta/config.json`: machine-readable task metadata. It classifies
  `gigasecond.cpp` and `gigasecond.h` as solution/editable files,
  `gigasecond_test.cpp` as the test file, and `.meta/example.cpp` plus
  `.meta/example.h` as reference examples. Do not show this to the model for
  ordinary SFT.
- `.meta/tests.toml`: test-case metadata used by Exercism tooling. It is not
  the C++ grader itself. Do not show this to the model.
- `.meta/example.cpp` and `.meta/example.h`: official/reference solution
  files. They contain the answer and are used to prove the task/grader setup is
  sane. Do not show these to the model.
- `gigasecond.cpp` and `gigasecond.h`: starter solution files. These are the
  editable files Aider adds to chat and asks the model to rewrite.
- `gigasecond_test.cpp`: the C++ tests used after the model edits the solution
  files. In the observed Aider run, this was not an editable chat file and was
  not part of the first model prompt.
- `CMakeLists.txt`: the build recipe. It compiles the solution and tests,
  links required libraries, enables warnings-as-errors, and runs the test
  executable.
- `test/catch.hpp` and `test/tests-main.cpp`: local Catch test harness support
  files used by the grader.

The task flow is:

1. The benchmark copies the task folder into an isolated working directory.
2. The task metadata identifies the editable solution files.
3. Aider starts in `whole` edit format with only those editable files.
4. Aider sends the model the `whole` edit-format contract, the editable file
   contents, and the exercise text built from `.docs/introduction.md` and
   `.docs/instructions.md`.
5. The model returns complete file listings.
6. Aider parses the response and writes the returned files to disk.
7. The grader builds and runs the tests.
8. On failure, Aider sends the compile/test feedback back to the model for the
   next attempt.

## Preferred Single-Task SFT Shape

For actual model behavior, prefer an Aider-like SFT row over a minimal
format-only row. The minimal row is useful for checking SLIME plumbing and
parser discipline; it is not a prompt-faithful training example. The Aider-like
row should train the same mapping used during evaluation:

```text
input:  format contract + docs text + editable starter files
target: complete solved file listings in Aider whole format
```

Use this wording for a compact self-contained single task:

````text
Use Aider whole edit format. Modify the supplied editable files to solve the
task. Return only complete file listings. Each fenced block must be preceded by
the bare filename on the line immediately before the fence. Do not return a
diff. Do not include test files, reference example files, or explanatory prose
in the answer.

# Introduction

<contents of .docs/introduction.md, if the task has one>

# Instructions

<contents of .docs/instructions.md>

# Supplied editable files

<filename-1>
```cpp
<complete pre-edit contents of filename-1>
```

<filename-2>
```cpp
<complete pre-edit contents of filename-2>
```

Do not change the names of existing functions, classes, namespaces, or files,
as they may be referenced from unit tests. Only use standard libraries unless
the starter task already requires a provided dependency.
````

The corresponding assistant target should contain only solved file listings:

````text
<filename-1>
```cpp
<complete solved contents of filename-1>
```

<filename-2>
```cpp
<complete solved contents of filename-2>
```
````

Do not include `.meta/example.*` in the prompt. Those files are the reference
solution. Do not include hidden/reference tests unless a benchmark explicitly
defines visible tests as part of the prompt contract.

## Currently Implemented Aider-Like Row

The checked-in writer
`src/w8_biayn/integrations/moonlight_single_sample_sft.py` now emits the
compact self-contained Aider-like row below. The user message contains the task
text plus complete pre-edit `leap.h` and `leap.cpp` contents, and the assistant
message contains only parseable whole-file listings.

```json
{"label":"aider-whole-format-001","messages":[{"content":"Use Aider whole edit format. Modify the supplied editable files to solve the task. Return only complete file listings. Each fenced block must be preceded by the bare filename on the line immediately before the fence. Do not return a diff. Do not include test files, reference example files, or explanatory prose in the answer.\n\n# Introduction\n\nLeap years keep the calendar year synchronized with the astronomical year.\n\n# Instructions\n\nImplement a leap-year checker.\n\nA leap year is evenly divisible by 4, except years evenly divisible by 100 are not leap years unless they are also evenly divisible by 400.\n\n# Supplied editable files\n\nleap.h\n```cpp\n#if !defined(LEAP_H)\n#define LEAP_H\n\nnamespace leap {\n\n}  // namespace leap\n\n#endif\n```\n\nleap.cpp\n```cpp\n#include \"leap.h\"\n\nnamespace leap {\n\n}  // namespace leap\n```\n\nDo not change the names of existing functions, classes, namespaces, or files, as they may be referenced from unit tests. Only use standard libraries unless the starter task already requires a provided dependency.","role":"user"},{"content":"leap.h\n```\n#if !defined(LEAP_H)\n#define LEAP_H\n\nnamespace leap {\n\nbool is_leap_year(int year);\n\n}  // namespace leap\n\n#endif\n```\n\nleap.cpp\n```\n#include \"leap.h\"\n\nnamespace leap {\n\nbool is_leap_year(int year) {\n    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);\n}\n\n}  // namespace leap\n```","role":"assistant"}],"metadata":{"format":"aider-whole","model_family":"moonlight","purpose":"aider-like-single-sample-sft","source":"single_sample_for_sft.md","subset":"train","task_id":"aider-whole-format-001"},"task_id":"aider-whole-format-001"}
```

This row is structurally valid for the current SLIME SFT loader. It is still a
single synthetic sample, but it is no longer the old under-specified format-only
prompt. It trains the model to read the task text and starter files before
returning Aider `whole` file listings.

If exact Aider behavior is the goal, a short explanation before the listings is
also valid. If the narrower goal is maximum parser discipline, retain the
no-prose target and state that this is a stricter project policy.

## Validation And Reporting Limits

A corrected sample should satisfy all of the following:

- the input contains the complete pre-edit files;
- every changed file is returned in full;
- every opening fence has the bare filename immediately above it;
- the actual Aider `whole` parser accepts the response;
- the resulting files compile and pass the task tests;
- a held-out format task is used to probe the trained checkpoint.

The synthetic `leap` task was not one of the 26 task IDs in
`glm47-p8b-20260712095217`, so it does not directly overlap that run's task
matrix. It must still be excluded from any future evaluation set that contains
Leap.

One sample can establish that the data path and optimizer run, but it cannot
establish generalization. Report it only as a single-sample format-discipline
smoke.
