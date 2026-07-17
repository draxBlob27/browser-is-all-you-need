# Materializing Local Aider-Format C++ Tasks

This guide describes how to turn a task mentioned in any checked-in curriculum,
design note, or task proposal into a local Aider-format C++ task. It is not
specific to linked lists or to a particular model lane.

The result is a runnable local artifact under `.w8-biayn/data/aider-tasks/`.
It is useful for response-only probing and compact one-task SFT smoke data. It
is **not** an admitted primary Aider SFT root or a release claim. Promotion to
the primary dataset remains governed by
`PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Before Creating A Task

Read the source document as a task contract, not merely as a name list. For
each proposed task, record:

- a stable, descriptive task ID;
- the domain-specific public C++17 API and its return/error behavior;
- observable state transitions and edge cases;
- a provenance statement identifying the proposal document and whether the
  task is newly authored or derived from an admissible source;
- whether it can be materially confused with an official benchmark task.

Do not materialize benchmark tasks, their tests, reference code, prompts, or
close semantic copies. A domain rename alone is not a new task: the public API,
operation set, invalid-input behavior, and edge cases must differ materially.

## Required Directory Shape

Use one directory per task. Grouping directories are optional and describe a
curriculum topic only; they are not part of the task ID.

```text
.w8-biayn/data/aider-tasks/<topic>/<task-id>/
├── .docs/
│   ├── introduction.md
│   └── instructions.md
├── .meta/
│   ├── config.json
│   ├── provenance.json
│   ├── tests.toml
│   ├── example.<header-extension>
│   ├── example.cpp
│   └── <optional hidden test/support files>
├── <editable-header>.h
├── <editable-source>.cpp
├── <visible-test>.cpp
└── CMakeLists.txt
```

Use a directory name that is a stable lower-case slug, such as
`dll-tab-strip` or `graph-route-planner`. Keep every path in metadata relative
to the task directory; do not accept absolute paths or `..` components.

## File Contract

### Documentation

`.docs/introduction.md` gives short domain context. `.docs/instructions.md`
defines the complete visible contract: required functions/classes, input
validation, state changes, selection/fallback rules, ordering rules, and any
complexity expectations. It must be sufficient to solve the task without
revealing hidden tests or the reference implementation.

### Editable files

The editable header/source pair is the starter state sent to the model. It
must compile after a correct whole-file replacement and must expose only the
task-specific public API. Leave implementation gaps in the starter source;
do not hide a correct answer in a starter helper.

### Reference files

`.meta/example.*` contains the complete correct state of every editable file.
Their order must exactly match `files.solution` in `.meta/config.json`. The
local one-row SFT helper turns these files into the Aider whole-file assistant
answer, so names, count, and order are significant.

### Tests and build

Keep at least one visible test at the task root. Keep grading-only tests and
support files under `.meta/` (or an equivalent non-editable task-private
location) and include them from `CMakeLists.txt` when locally grading.

For pointer-owning or stateful tasks, hidden tests should cover empty and
singleton states, boundaries, stale IDs, repeated mutations, forward/reverse
agreement, and randomized traces checked against a simple container oracle.
The reference solution must pass both visible and hidden tests. Normal and
sanitizer builds are required before a task can move beyond local diagnostic
use.

Use C++17 and a task-local CMake project. Build the solution separately from
each test executable, enable strict warnings for GCC/Clang, and make the test
target run all visible and hidden tests. Avoid downloads and non-standard
dependencies.

## Metadata Contract

`.meta/config.json` is required. Its `files` object must name the starter,
test, and reference files:

```json
{
  "authors": ["w8-biayn"],
  "blurb": "One sentence describing the task.",
  "files": {
    "solution": ["<task-id>.h", "<task-id>.cpp"],
    "test": ["task_test.cpp"],
    "example": [".meta/example.h", ".meta/example.cpp"]
  }
}
```

`files.solution` is the authoritative ordered list of editable files. For every materialized root, use its directory slug: `<task-id>.h` and `<task-id>.cpp`, never `task.h` or `task.cpp`. Every
listed file must exist. `files.example` must be the same length and order,
with each item holding the corresponding complete reference file.

Also add:

- `.meta/provenance.json`: source document path, source task ID, authoring
  origin, version, and the statement that local materialization is not dataset
  admission;
- `.meta/tests.toml`: concise named descriptions of visible and hidden test
  groups.

## Aider Whole-File Response Contract

The local evaluator prompts with the two documentation files and only the
editable files. A model must return one complete listing for each editable
file, in this form:

````text
<task-id>.h
```cpp
// complete replacement for <task-id>.h
```

<task-id>.cpp
```cpp
// complete replacement for <task-id>.cpp
```
````

The filename is bare and appears immediately before its fence. Do not emit a
diff, prose, tests, reference files, extra files, or duplicate listings. The
grader rejects missing and extra files.

## Materialization Workflow

1. Select exactly one proposed task and give it a unique slug.
2. Write its domain-specific API and visible contract before writing tests.
3. Create the starter header/source pair and a separate complete reference
   pair under `.meta/`.
4. Author visible tests plus task-private hidden/invariant tests.
5. Add CMake and confirm the reference passes from a clean copied task tree.
6. Check the Aider prompt with
   `python -m w8_biayn.integrations.moonlight_aider_task_eval --task-dir <task-dir> --response <whole-file-response>`.
7. If a one-row local smoke dataset is desired, use
   `python -m w8_biayn.integrations.moonlight_aider_task_sft --task-dir <task-dir> --out <output-dir>`.
8. Record the task generator or repo-owned command used to create repeatable
   families of tasks. Do not rely on unrecorded one-off conversions.

The response-only evaluator writes the prompt, applied response, build logs,
and grade summary under its output directory. It does not make a task an SFT
dataset candidate.

## Date Difference Curriculum

The five newly authored domain-specific Gregorian-date roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATE_DIFFERENCE_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_date_difference_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/date-difference/` and verifies every
reference in clean normal C++17 and separate ASan/UBSan builds. The roots are
local diagnostics only; `clock`, `gigasecond`, and `meetup` remain permanent
official Polyglot holdouts.

## Future-Date Calculations Curriculum

The ten newly authored policy-driven Gregorian roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_FUTURE_DATE_CALCULATIONS_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_future_date_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/future-date-calculations/`
and verifies each reference in clean normal C++17 and separate ASan/UBSan
builds. The roots are local diagnostics only; `clock`, `gigasecond`, and
`meetup` remain permanent official Polyglot holdouts.

## Overflow-Safe Date Math Curriculum

The ten newly authored domain-policy Gregorian roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_OVERFLOW_SAFE_DATE_MATH_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_overflow_safe_date_math_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/overflow-safe-date-math/`
and verifies every reference in clean normal C++17 and separate ASan/UBSan
builds. These roots are local diagnostics only; `clock`, `gigasecond`, and
`meetup` remain permanent official Polyglot holdouts.

## Binary Search Tree Curriculum

The 20 newly authored roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BINARY_SEARCH_TREE_CURRICULUM.md` are
materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_bst_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/binary-search-tree/`. `--verify`
checks every reference in a clean normal C++17 build and a separate ASan/UBSan
build. The roots remain local diagnostics; the official Polyglot
`binary-search-tree` benchmark remains a permanent holdout.

## Balanced Search Tree Curriculum

The 20 newly authored AVL and red-black roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BALANCED_SEARCH_TREE_CURRICULUM.md` are
materialized reproducibly by default with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_balanced_tree_aider_tasks.sh
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree/` and does not
require CMake. The current environment has no CMake, so materialization is the
supported action now; it does not claim that the reference oracle has been
verified.

When CMake is installed later, run the separate verifier:

```bash
bash examples/slime/moonlight_cpp_perf/verify_balanced_tree_aider_tasks.sh
```

It reruns materialization idempotently, then uses the generator's `--verify`
mode to build every reference in clean normal C++17 and ASan/UBSan CMake
builds. The roots are local diagnostics only; the official Polyglot
`binary-search-tree` benchmark remains a permanent holdout.

## Circular Buffer Curriculum

The 20 newly authored fixed-capacity FIFO roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_CIRCULAR_BUFFER_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_circular_buffer_aider_tasks.sh
```

Materialization is mandatory before any local probe, one-row smoke conversion,
or later verification. It writes `.w8-biayn/data/aider-tasks/aider-dsa/circular-buffer/`. CMake
is not required for this step.

When CMake and a C++ compiler are available, verification is mandatory before
a root moves beyond local diagnostic use. Run:

```bash
bash examples/slime/moonlight_cpp_perf/verify_circular_buffer_aider_tasks.sh
```

The verifier re-materializes idempotently, then checks every reference in a
clean C++17 build and a separate ASan/UBSan build. Each root has a domain-named
API and explicit reject, automatic-overwrite, or caller-authorized-overwrite
full-buffer policy; hidden tests use randomized `std::deque` oracle traces.
These are local diagnostics only; the official Polyglot `circular-buffer` benchmark
remains a permanent holdout.

## Bounded Blocking Queue Curriculum

The 20 newly authored roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BOUNDED_BLOCKING_QUEUE_CURRICULUM.md`
are materialized with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_bounded_blocking_queue_aider_tasks.sh
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/bounded-blocking-queue/`. When CMake
is available, add `--verify` to run every reference in clean normal C++17 and
separate ASan/UBSan builds. These remain local diagnostic artifacts, not
admitted SFT data.

## Interval Scheduling Curriculum

The 20 newly authored roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_INTERVAL_SCHEDULING_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/interval-scheduling/` and checks every
reference in clean normal C++17 and separate ASan/UBSan builds. The roots use
domain-specific selection, allocation, booking, or audit APIs with half-open
interval semantics; they are local diagnostics, not admitted SFT data.

## LFU Cache Curriculum

The 20 newly authored LFU-cache roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_LFU_CACHE_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_lfu_cache_aider_tasks.sh
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/lfu-cache/`. Add `--verify` when CMake
and a C++ compiler are available; it checks each reference in a clean C++17
normal build and a separate ASan/UBSan build. These roots are local diagnostics,
not admitted SFT data.

## Nested Structure Curriculum

The 20 newly authored nested-structure roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_NESTED_STRUCTURE_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_nested_structure_aider_tasks.sh
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/nested-structure/`. Each root has a
domain-specific grammar-aware API and diagnostic type, with escaped and quoted
token handling; it is deliberately distinct from the held-out
`matching-brackets` family. Add `--verify` when CMake and a C++ compiler are
available for clean normal C++17 plus ASan/UBSan reference builds. These are
local diagnostic artifacts, not admitted SFT data.

## Ordered Registry Curriculum

The 20 newly authored ordered-registry roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ORDERED_REGISTRY_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_ordered_registry_aider_tasks.sh
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/ordered-registry/`. Add `--verify`
when CMake and a C++ compiler are available; it checks every reference in a
clean C++17 normal build and a separate ASan/UBSan build. These roots are local
diagnostics only; the official Polyglot `grade-school` benchmark remains a
permanent holdout.

## Promotion Boundary

## Offset-Aware Range Overlap Curriculum

The ten newly authored fixed-offset policy roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_OFFSET_AWARE_RANGE_OVERLAP_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_offset_aware_range_overlap_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/offset-aware-range-overlap/`
and verifies references in clean C++17 normal and separate ASan/UBSan builds.
These are local diagnostics only; `clock`, `gigasecond`, and `meetup` remain
permanent official Polyglot holdouts.

## Clock Arithmetic Curriculum

The ten newly authored cyclic-time roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_CLOCK_ARITHMETIC_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_clock_arithmetic_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/clock-arithmetic/` and verifies every
reference in clean C++17 normal and separate ASan/UBSan builds. These are local
diagnostic artifacts only, not admitted SFT data. The official Polyglot `clock`
task, `gigasecond`, and `meetup` remain permanent holdouts.

## General Calendar Arithmetic Curriculum

The ten newly authored domain-policy Gregorian roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_GENERAL_CALENDAR_ARITHMETIC_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_calendar_arithmetic_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/general-calendar-arithmetic/`
and verifies every reference in clean C++17 normal and separate ASan/UBSan
builds. The roots use subscription, harvest, clinic, inventory, contract,
vacation, maintenance, licence, release, and lease policies; they are local
diagnostic artifacts only, not admitted SFT data. `clock`, `gigasecond`, and
`meetup` remain permanent official Polyglot holdouts.

## Leap-Year Rule Curriculum

The five newly authored February-policy roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_LEAP_YEAR_RULE_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_leap_year_rule_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/leap-year-rule/`
and verifies every reference in clean normal C++17 and separate ASan/UBSan
builds. The roots are local diagnostics only, not admitted SFT data; `clock`,
`gigasecond`, and `meetup` remain permanent official Polyglot holdouts.

## XOR Linked List Curriculum

The 20 newly authored safe slot-index XOR linked-list roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_XOR_LINKED_LIST_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_xor_linked_list_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/xor-linked-list/` and checks every
reference in clean C++17 normal and separate ASan/UBSan builds. Links encode
only stable nonzero arena slot IDs; raw-pointer XOR and pointer/integer address
encoding are forbidden. These are local diagnostics, not admitted SFT data;
the official Polyglot `linked-list` benchmark remains a permanent holdout.

## Sequence Pattern Curriculum

The 20 newly authored sequence-pattern roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SEQUENCE_PATTERN_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_sequence_pattern_aider_tasks.sh
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/sequence-pattern/`. Add `--verify`
when CMake and a C++ compiler are available; it checks every reference in a
clean C++17 normal build and a separate ASan/UBSan build. The roots return
domain-specific spans, counts, diagnostics, or review IDs rather than an
equal/sublist/superlist/unequal relationship classification. They are local
diagnostics only; the official Polyglot `sublist` benchmark remains a permanent
holdout.

## Skip List Curriculum

The 20 newly authored skip-list roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SKIP_LIST_CURRICULUM.md`
are materialized and verified with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_skip_list_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/skip-list/`. The roots expose
domain-specific APIs, use seeded deterministic promotion, and test level-link
invariants. They are local diagnostics only, not admitted SFT data.

## Robot State-Simulation Curriculum

The 20 newly authored roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ROBOT_SIMULATION_CURRICULUM.md`
are materialized and verified with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_robot_simulation_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/robot-simulation/`. The roots remain
local diagnostics only; official robot-related Aider holdouts remain excluded.

## LRU Cache Curriculum

The 20 newly authored LRU-cache roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_LRU_CACHE_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_lru_cache_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/lru-cache/` and checks every reference
in clean C++17 normal and separate ASan/UBSan builds. These are local
diagnostics, not admitted SFT data.

## Sliding-Window Maximum Curriculum

The 20 newly authored rolling-maximum roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SLIDING_WINDOW_MAXIMUM_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_sliding_window_maximum_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dsa/sliding-window-maximum/` and checks
every reference in clean C++17 normal and separate ASan/UBSan builds. The
roots have domain-specific APIs and explicit count- or duration-window,
equal-maximum tie, rejection, and alert semantics. They are local diagnostics,
not admitted SFT data.

Local task materialization is an authoring step only. Before using a task in
the primary Aider SFT dataset, complete the primary pipeline's licensing,
provenance, benchmark-contamination, compiler-image, normal/sanitizer oracle,
family/split, renderer/token/mask, release, producer verification, and
consumer verification gates. Never label a local task directory or one-row
smoke dataset as a ready dataset release.
## Countdown Timers Arithmetic Curriculum

The ten newly authored elapsed-duration state-machine roots in `aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_COUNTDOWN_TIMERS_ARITHMETIC_CURRICULUM.md` are materialized with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_countdown_timers_aider_tasks.sh
```

It writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/countdown-timers/`; pass `--verify` when CMake is available to run clean normal C++17 and ASan/UBSan reference builds. These roots remain local diagnostics only; the official Polyglot `clock`, `gigasecond`, and `meetup` benchmark families remain permanent holdouts.

## Elapsed-Time Accumulation Arithmetic Curriculum

The ten newly authored ledger, interval, and policy roots in `aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_ELAPSED_TIME_ACCUMULATION_ARITHMETIC_CURRICULUM.md` are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_elapsed_time_accumulation_aider_tasks.sh --verify
```

This writes `.w8-biayn/data/aider-tasks/aider-dates-and-clocks/elapsed-time-accumulation/` and verifies every reference in clean normal C++17 and separate ASan/UBSan builds. These are local diagnostics only, not admitted SFT data; `clock`, `gigasecond`, and `meetup` remain permanent holdouts.
