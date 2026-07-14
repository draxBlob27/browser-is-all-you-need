# Single Sample For SFT

## Purpose

This document defines one supervised fine-tuning sample intended to improve
model output discipline for Aider `whole` edit format.

## Issue Faced By The Model

The model failed to follow Aider's `whole` edit format.

In `whole` edit format, each edited file must be returned as a complete file
listing, with the filename immediately before the fenced code block. The model
instead produced explanatory prose and raw C++ code fences. Aider could not map
the code block to a file and rejected the response as malformed.

## How The Issue Was Identified

The issue was found in run `glm47-p8b-20260712095217`.

Artifact:

```text
.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/glm47-p8b-20260712095217/independent-pass-at-1-and-8/sample-06/2026-07-12-19-58-13--glm47-p8b-20260712095217-sample-06/cpp/exercises/practice/gigasecond/.aider.chat.history.md
```

The chat log starts with Aider configured for `whole` edit format:

```text
# aider chat started at 2026-07-12 20:24:34

> Aider v0.86.3.dev53+g5dc9490bb
> Model: openai/glm-4.7-flash with whole edit format
> Added gigasecond.cpp to the chat.
> Added gigasecond.h to the chat.
```

The malformed response was identified by this actual log content:

```text
> Tokens: 1.2k sent, 2.0k received.
> The LLM did not conform to the edit format.
> https://aider.chat/docs/troubleshooting/edit-errors.html
> No filename provided before ``` in file listing
```

The actual model response that triggered this parser failure was:

````text
I have implemented the `add_gigasecond` function in both files.

The function takes a `std::tm` structure representing a date and time, adds 1,000,000,000 seconds (one gigasecond) to it, and returns the resulting date and time as a `std::tm` structure.

```cpp
#if !defined(GIGASECOND_H)
#define GIGASECOND_H

#include <ctime>

namespace gigasecond {

// Adds one gigasecond (1,000,000,000 seconds) to the given date.
// Returns the resulting date and time as a std::tm structure.
std::tm add_gigasecond(std::tm date);

}  // namespace gigasecond

#endif // GIGASECOND_H
```

```cpp
#include "gigasecond.h"
#include <ctime>

namespace gigasecond {

std::tm add_gigasecond(std::tm date) {
    // Convert the provided tm structure to time_t (seconds since epoch)
    std::time_t input_time = std::mktime(&date);

    // Add one gigasecond
    input_time += 1000000000;

    // Convert the resulting time_t back to a tm structure
    // using localtime to get the local time representation.
    // We return a copy of the tm to avoid issues with the static pointer
    // returned by localtime.
    std::tm* result = std::localtime(&input_time);
    return *result;
}

}  // namespace gigasecond
```
````

The matching result artifact confirms that this was counted as a malformed
response:

```text
.w8-biayn/modal/glm47-flash-aider-polyglot-cpp/runs/glm47-p8b-20260712095217/independent-pass-at-1-and-8/sample-06/2026-07-12-19-58-13--glm47-p8b-20260712095217-sample-06/cpp/exercises/practice/gigasecond/.aider.results.json
```

## Diagnosis

The failure was not primarily a C++ correctness issue. The first blocking issue
was output structure.

Aider expected this structure:

```text
filename.ext
```

followed by a fenced complete file body.

The model instead emitted prose before and between code blocks. It also emitted
fenced code without a valid filename immediately before the fence. That is why
Aider produced:

```text
No filename provided before ``` in file listing
```

## Single SFT Sample

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Use whole edit format. Modify the supplied files `leap.cpp` and `leap.h` to implement a leap-year checker. Return only complete file listings. Each fenced block must be preceded by its filename."
    },
    {
      "role": "assistant",
      "content": "leap.h\n```\n#if !defined(LEAP_H)\n#define LEAP_H\n\nnamespace leap {\n\nbool is_leap_year(int year);\n\n}  // namespace leap\n\n#endif\n```\n\nleap.cpp\n```\n#include \"leap.h\"\n\nnamespace leap {\n\nbool is_leap_year(int year) {\n    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);\n}\n\n}  // namespace leap\n```"
    }
  ]
}
```

## How This Sample Helps

This sample directly trains the desired output discipline:

- The assistant returns no explanatory prose.
- Each code fence is preceded by a filename.
- Each file body is complete, not a patch fragment.

The target behavior is that, when Aider asks for `whole` edit format, the model
responds with clean file listings only.
