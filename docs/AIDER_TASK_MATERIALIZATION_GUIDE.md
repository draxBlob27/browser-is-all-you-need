# Materializing Local Aider-Format C++ Tasks

This guide describes how to turn a task mentioned in any checked-in curriculum,
design note, or task proposal into a local Aider-format C++ task. It is not
specific to linked lists or to a particular model lane.

The result is a runnable local artifact under `.w8-biayn/data/aider-tasks/`.
It is useful for response-only probing and local task verification. It is not
an SFT row, release claim, training authorization, or benchmark result. The
current authoring boundary is
[`AIDER_SFT_SCOPE.md`](AIDER_SFT_SCOPE.md): work on the generated task roots
and their `docs/aider-synthetic/` source documents only.

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

The eight remediated domain-specific Gregorian-date roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATE_DIFFERENCE_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_date_difference_aider_tasks.sh --verify
```

This preserves the five-root legacy tree at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/date-difference/` and writes
the fresh family to
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/date-difference/`,
honoring the remediation input's family type while recording the discovered
legacy taxonomy mismatch. Use `--verify-core` for the exact 28-pair
seven-dimension screen: each dimension must independently pass normalized
feature-overlap and symmetric-difference gates, and focused tests require
distinct emitted semantic witnesses plus eight different executed negatives.
The first hash-inequality proof is preserved as invalidated evidence, not a
current claim. Use `--docker-sanity` for mandatory network-disabled normal plus
fresh ASan/UBSan evidence. The roots remain local diagnostics only;
`clock`, `gigasecond`, and `meetup` are permanent official Polyglot holdouts.

## Duration Formatting Curriculum

The ten generic v1 roots remain immutable under
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/duration-formatting/`. The
user-authorized 8–12 hard-rule remediation emits exactly ten distinct
replacements only under
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/duration-formatting/`:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_duration_formatting_aider_tasks.sh \
  --force --docker-sanity
```

The owner compares all 45 pairs across the exact seven mandatory dimensions,
materializes three coherent changed controls, screens all 26 official C++
holdouts, and requires those controls plus every reference and compiled false
substitute to run in normal and fresh ASan/UBSan builds in the pinned,
network-disabled Docker sanity image. A passing receipt is
`local_family_verified`, not locked-oracle or dataset-release evidence.

## Future-Date Calculations Curriculum

The ten newly authored policy-driven Gregorian roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_FUTURE_DATE_CALCULATIONS_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_future_date_aider_tasks.sh --verify
```

The legacy command historically wrote ten generic-policy roots under
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/future-date-calculations/`;
that tree is now immutable remediation input. The owner defaults to the
user-requested parallel v2 root at
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/future-date-calculations/`.
It emits eight independently implemented replacements and ten per-legacy
remedy records (eight `replace`, two `reject`). Use `--verify-core` for the
28-pair seven-dimension structural/semantic gate and `--verify-docker` for the
mandatory network-disabled normal, fresh ASan/UBSan, topic-negative, and
coherent-control evidence. See
`aider-tasks-spec/aider-text-grid-reshaping/future-date-calculations.md`.

## Overflow-Safe Date Math Remediation Curriculum

The immutable ten-root legacy generic-record template remains at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/overflow-safe-date-math/`.
The counted v2 family uses the user-authorized 8–12 bound and emits exactly ten
distinct window-classification, dependency-DAG, transactional amendment,
policy-join, recurrence-merge, milestone-expansion, retention-stage,
interval-partition, critical-path, and event-ledger mechanisms. The curriculum in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_OVERFLOW_SAFE_DATE_MATH_CURRICULUM.md`
is materialized only under the parallel re-verification root with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_overflow_safe_date_math_aider_tasks.sh \
  --force --verify-core --verify --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/overflow-safe-date-math/`.
The owner checks all 45 emitted-family pairs separately in the seven hard-rule
dimensions, constructs and rejects coherent domain/identifier-renamed,
constants-or-policy-only, and opposite-end-selection controls, executes one
strict false substitute per root, and compares every root with all 26 official
C++ holdouts. Final evidence uses the pinned network-disabled repository C++
sanity image, with four equal positive CTest entries in clean normal and fresh
ASan/UBSan modes for every root and coherent control. The evidence is
`docker_sanity`, not a family-designated locked oracle. These roots remain
local candidates only; `clock`, `gigasecond`, and `meetup` remain permanent
official Polyglot holdouts.

## Binary Search Tree Curriculum

The 20 node-owning v2 replacement roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BINARY_SEARCH_TREE_CURRICULUM.md` are
materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_bst_aider_tasks.sh --force --verify-core --verify
```

This writes `.w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree/`.
The legacy set-backed tree at `.w8-biayn/data/aider-tasks/aider-dsa/binary-search-tree/`
is preserved as audit input and must never be regenerated. `--verify-core`
rejects missing owned-node/root operations and forbidden authoritative
containers; `--verify` checks every reference in clean normal C++17 and a
separate ASan/UBSan build when CMake is available. The roots remain local diagnostics; the official Polyglot
`binary-search-tree` benchmark remains a permanent holdout.

## Trie Curriculum

The 20 legacy flat-map template roots remain immutable at
`.w8-biayn/data/aider-tasks/aider-dsa/trie/`. Materialize their 20 distinct
task-spec-v3
replacements only under `.w8-biayn/data/aider-tasks-reverify/aider-dsa/trie/`:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_trie_aider_tasks.sh \
  --force --verify-core --verify
```

`--verify-core` binds the preimplementation remedy records, validates prompt
and file-role boundaries and reference mapping, and derives five evidence
dimensions from emitted artifacts for all 190 family pairs and all 26 official
C++ holdouts. Focused controls reject identifier-renamed,
constants/policy-only, and opposite-end-selection clones. `--verify` compiles
every reference and its visible, private, and independent complete-state
hard-rule tests in clean normal and fresh ASan/UBSan configurations, then
compiles and executes one distinct topic-specific substitute per root. The
pinned image runs with network disabled and is `docker_sanity` evidence because
this family has no separately designated locked oracle. A passing family is
`local_family_verified`; it is not SFT data or a dataset-release claim.

## Priority Queue Curriculum

The legacy 20-root renamed linear-scan template remains preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/priority-queue/`. Its v2 replacements are
materialized only at
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/priority-queue/`:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_priority_queue_aider_tasks.sh --force --verify-core
```

The owner requires 20 one-to-one logic/implementation profiles, including
indexed, d-ary, radix, interval, pairing, leftist, binomial, bounded top-K, and
head-only heaps plus bucket, calendar, tournament, price-level, preemptive, and
weighted-fair mechanisms. It rejects standard heap delegation, complete-sort
selection, missing mechanism invariants, duplicate signatures, and excessive
pairwise semantic similarity. Locked normal/sanitizer evidence is imported
only from an exact deterministic archive after its family hash matches the live
generated roots. These remain local candidate tasks, not a dataset release.

## Balanced Search Tree Curriculum

The legacy materialization remains preserved at:

```text
.w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree/
```

Do not regenerate that tree while remediating the balanced-search-tree
specification. The 20 AVL and red-black roots described by
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BALANCED_SEARCH_TREE_CURRICULUM.md`
are to be materialized as a parallel re-verification family at:

```text
/data/sanil/browser-is-all-you-need/.w8-biayn/data/aider-tasks-reverify/aider-dsa/balanced-search-tree/
```

The re-verification root has the same `aider-dsa/balanced-search-tree/<task-id>`
layout and task slugs as the legacy family, but is a distinct generated tree.
This lets the generator replace, add, or remove files beneath the re-verification
root without mutating the original materialization. It is still local candidate
material, not a dataset release.

On the first materialization, use the output override and do not pass
`--force`:

```bash
REVERIFY_ROOT="$PWD/.w8-biayn/data/aider-tasks-reverify/aider-dsa/balanced-search-tree"
SLIME_BALANCED_TREE_TASKS_DIR="$REVERIFY_ROOT" \
  bash examples/slime/moonlight_cpp_perf/prepare_balanced_tree_aider_tasks.sh --verify
```

The generator owns the re-verification tree; never copy or hand-edit legacy
task directories into it. The canonical expected family shape is:

```text
.w8-biayn/data/aider-tasks-reverify/
└── aider-dsa/
    └── balanced-search-tree/
        ├── avl-api-rate-limits/
        ├── ... 18 other declared task slugs ...
        └── rb-travel-fare-table/
```

After materialization, confirm that the two family roots have the same task
slug inventory before comparing their contents:

```bash
LEGACY_ROOT="$PWD/.w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree"
REVERIFY_ROOT="$PWD/.w8-biayn/data/aider-tasks-reverify/aider-dsa/balanced-search-tree"
diff -u \
  <(find "$LEGACY_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort) \
  <(find "$REVERIFY_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
```

An empty diff proves only directory-slug alignment. It does not prove that the
new APIs, references, tests, metadata, or oracle evidence satisfy the
deterministic balanced-tree specification. If rerunning a changed generator,
`--force` may be used only with `SLIME_BALANCED_TREE_TASKS_DIR` set to the
re-verification root; it must never target the legacy root.

The command's `--verify` mode regenerates the re-verification root and runs the
generator's normal and sanitizer verifier. A missing locked-runtime prerequisite
is recorded as `not_completed`; do not substitute a host-only result for the
required local-family evidence. The official Polyglot `binary-search-tree`
benchmark remains a permanent holdout.
## Cyclic Slot Systems Curriculum

The clean-room replacement is a separate 15-root family, not a renamed or
policy-parameterized circular-buffer curriculum. Its roots cover first-fit
allocation, a timer wheel, windowed aggregates, smooth weighted selection,
generation barriers, phase transitions, modular convolution and arcs,
clockwise routing, functional-graph cycle indexing, circle-method pairings,
CRC reduction, epoch stamps, rotating Bloom membership, and serial replay
admission. They deliberately avoid FIFO and full-write/forced-overwrite
semantics. Materialize only the re-verification root required by the
circular-buffer remediation prompt at
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/circular-buffer/` with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_cyclic_slot_systems_aider_tasks.sh --force --verify-core
```

The owner enforces the binding 15–20 count and currently emits exactly 15. Its
artifact-derived screen compares all 105 unordered pairs and focused tests
reject renamed-domain, constants-or-policy-only, and opposite-end-selection
clones. Final runtime evidence uses the pinned
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
image with `--network none`; all 15 roots pass clean normal and fresh
ASan/UBSan builds. The owner-imported receipt binds the image, generator,
references, task trees, commands, and toolchain, so the family is
`local_family_verified`. The evidence class is `docker_sanity` with
`locked_oracle: false`; it is not a dataset-release or locked-oracle claim.

See `aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_CYCLIC_SLOT_SYSTEMS_CURRICULUM.md`
and `aider-tasks-spec/aider-dsa/cyclic-slot-systems.md` for the contamination
screen and local-only boundary.

## Bounded Blocking Queue Curriculum

The 20 newly authored roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BOUNDED_BLOCKING_QUEUE_CURRICULUM.md`
are materialized with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_bounded_blocking_queue_aider_tasks.sh
```

The legacy family remains preserved at `.w8-biayn/data/aider-tasks/aider-dsa/bounded-blocking-queue/`.
The v2 replacements write `.w8-biayn/data/aider-tasks-reverify/aider-dsa/bounded-blocking-queue/`.
Set `SLIME_BOUNDED_BLOCKING_QUEUE_TASKS_DIR` to that reverify root when invoking
the wrapper. When CMake is available, add `--verify` to run every reference in
clean normal C++17 and separate ASan/UBSan builds. These remain local diagnostic
artifacts, not admitted SFT data.

## Interval Scheduling Curriculum

The legacy 20-root four-template family remains preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/interval-scheduling/`. The 20 one-to-one
v2 replacements in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_INTERVAL_SCHEDULING_CURRICULUM.md`
use 20 distinct algorithms and materialize only under the parallel root with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh \
  --force --verify-core --verify
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/interval-scheduling/`, verifies
prompt/role and reference mapping, executes one compilable topic-specific false
substitute per root, compares actual normalized docs/APIs/reference control
flow/tests across all family and official-holdout pairs, and checks every
reference plus its independent oracle test in clean normal C++17 and a separate
fresh ASan/UBSan build. The mutable ledger additionally checks a complete
operation trace against an independent vector model after every operation. The family spans
weighted and budgeted DP, greedy cover/stabbing, heap scheduling/partitioning,
event and k-coverage sweeps, ordered mutable indexes, multi-calendar
intersection, DSU, containment stack, directed-DAG DP, cyclic normalization,
augmenting matching, and bitmask set cover. These are local diagnostics, not
admitted SFT data.

## LFU Cache Curriculum

The 15 counted v3 LFU replacements and five explicit duplicate rejections in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_LFU_CACHE_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_lfu_cache_aider_tasks.sh --force --verify-core --verify
```

This preserves all 20 legacy template roots under
`.w8-biayn/data/aider-tasks/aider-dsa/lfu-cache/` and writes only
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/lfu-cache/`. The owner verifies
the skill's seven hard-diversity dimensions, actual normalized pairwise source
similarity, strict prompt and role boundaries, all 26 official holdouts, and
one compiled false substitute per counted root. Each reference passes three
tests in clean C++17 normal and fresh ASan/UBSan modes in the pinned,
network-disabled Docker sanity image; each false substitute builds and is then
rejected by all three tests. The result is `docker_sanity`, not a
family-designated locked oracle. These roots are local diagnostics, not
admitted SFT data.

## Nested Structure Curriculum

The legacy token-parameterized family remains preserved under
`.w8-biayn/data/aider-tasks/aider-dsa/nested-structure/`. The 20 v2 replacement
roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_NESTED_STRUCTURE_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_nested_structure_aider_tasks.sh --force --verify-core --verify
```

This writes only `.w8-biayn/data/aider-tasks-reverify/aider-dsa/nested-structure/`.
The replacements implement 20 distinct mechanisms rather than one renamed
delimiter scanner. Set `W8_NESTED_STRUCTURE_GRADER_IMAGE` to the designated
locked C++ image for the network-disabled normal, fresh ASan/UBSan, and
executed-negative-fixture verifier. These are local diagnostic artifacts, not
admitted SFT data.

## Ordered Registry Curriculum

The legacy 20-root family remains preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/ordered-registry/`; it used one generic
register/transition/query implementation and is audit input only. The 20 v2
roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ORDERED_REGISTRY_CURRICULUM.md`
are materialized only into the parallel reverify tree with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_ordered_registry_aider_tasks.sh --force --verify-core --verify
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/ordered-registry/` and never
modifies the legacy tree. The v2 family has distinct finite-state, priority,
waitlist, interval-calendar, set, relation, consistent-hash ring, append-only
temporal history, extendable expiry-wheel, indexed-heap, FEFO, and conservation
mechanisms. `--verify-core` uses noun/literal-independent control-flow and
assertion shingles to reject renamed semantic copies, screens all 20 contracts
plus all 26 bound official C++ holdouts, and binds distinct
logic/state/mutation/selection/boundary profiles. `--verify` requires every
named false substitute to compile and be rejected by executed tests, then
requires clean C++17 normal and fresh ASan/UBSan builds with equal positive
discovery counts. Its receipt binds owner/reference/tree hashes, an
independently matched Docker mount hash, the immutable image, compiler/CMake
identities, commands, and `network_policy: none`. These roots are local diagnostics only;
the official Polyglot `grade-school` benchmark remains a permanent holdout.

## Promotion Boundary

## Word Wrap And Text Justification Curriculum

The legacy 20-root domain-record formatter template remains preserved at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/text-justification/`.
Its v2 remediation repairs the hanging-agenda root and replaces nineteen
semantic duplicates with distinct segmentation, alignment, pagination,
balancing, quote parsing, tab-stop, dynamic-programming, widow-control,
hyphenation, centering, dual-resource, page-window, scale-fit, partition,
typed-field, and run-coalescing mechanisms. The curriculum in
`aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_WORD_WRAP_TEXT_JUSTIFY_CURRICULUM.md`
is materialized only under the parallel reverify tree with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_text_justification_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/text-justification/`.
The owner verifies prompt and role boundaries, reference mapping, all 190
artifact-derived family pairs conjunctively over the exact seven hard-rule
dimensions, all 520 bound official-holdout comparisons, and the required
domain-renamed, constants/policy-only, and opposite-end controls. Each control
is a complete, coherent emitted-root mutation and is rejected by the exact
production pair evaluator. The pinned network-disabled Docker sanity gate
requires two equal positive CTest discoveries per root and per control in clean
normal and fresh ASan/UBSan modes and compiles/executes their rejected false
substitutes. The previous six-dimension receipt is invalidated. The replacement
schema-v2 receipt passed for 20 roots plus three controls, producing 40 task
rows and six control rows; all twenty v2 roots reached
`local_family_verified`. They remain local candidates, not SFT data or a
dataset-release claim.

## Grid Ownership Mapping Curriculum

The 20 remediated, clean-room ownership and spatial-attribution roots in
`aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_GRID_OWNERSHIP_MAPPING_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_grid_ownership_mapping_aider_tasks.sh --verify-docker
```

This preserves the legacy family and writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/grid-ownership-mapping/`.
The owner verifies every C++17 reference in clean normal and separate fresh
ASan/UBSan builds in the pinned network-disabled Docker sanity image. It checks
all 190 family pairs over actual emitted docs, APIs, references, visible/private
tests, and topic-negative sources; compiles and executes one false substitute
per root; and compiles and executes domain/identifier-renamed,
constants/policy-only, and opposite-end-selection clone controls. All false
implementations must be rejected by both executed tests; source inspection alone
does not satisfy the hard rule. The owner also screens the 26 official C++
holdouts. The replacements use distinct interval, traversal, component,
propagation, allocation, and audit algorithms; they are local diagnostics only,
not admitted SFT data. All official Polyglot C++ tasks remain permanent holdouts.

## Sparse Matrix Encoding Remediation Curriculum

The legacy 20-root noun/duplicate-policy dense-reconstruction template remains
immutable at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/sparse-matrix-encoding/`.
Its v2 remediation repairs one independently justified constellation root and
replaces 19 semantic duplicates with distinct sparse component, interval,
CSR/CSC, run, prefix-query, grouping, vacancy, delta-log, perimeter, Morton,
dot-product, matching, transpose, sweep, and timestamp mechanisms. The family in
`aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_SPARSE_MATRIX_ENCODING_CURRICULUM.md`
materializes only under the parallel tree with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_sparse_matrix_encoding_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/sparse-matrix-encoding/`.
The owner validates prompt/role/reference boundaries, all 190 artifact-derived
family pairs separately across the seven hard-rule dimensions, all 520 bound
official-holdout comparisons, the three required pure clone controls, and one
compiled/executed topic negative per root. Final evidence uses the pinned
network-disabled C++ sanity image and requires two equal positive CTest
discoveries in clean normal and fresh ASan/UBSan modes. All 20 references
passed, all 20 topic negatives failed the behavior tests, and all three pure
clone controls passed the behavior tests before the production semantic screen
rejected them. The family is `local_family_verified`. It is labeled `docker_sanity`, not
`locked_oracle`. The roots remain local
candidate artifacts, not admitted SFT data or release evidence.

## Table Pivot Curriculum

The immutable legacy 20-root noun/unit/duplicate-policy template remains under
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/table-pivot/`. Its v2
remediation repairs `pivot-call-center` and replaces the other nineteen roots
with distinct transition, capacity, reconciliation, pricing, Pareto,
differencing, percentile, interval, weighted, distinct-count, prefix,
classification, retention, normalization, interpolation, path-membership, and
FIFO-aging mechanisms. The curriculum in
`aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_TABLE_PIVOT_CURRICULUM.md`
is materialized only beneath the sibling reverify tree with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_table_pivot_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/table-pivot/`.
The owner verifies exact prompt/role/reference boundaries, all 190 seven-axis
family pairs, all 520 comparisons against 26 bound official C++ holdouts,
three behavior-passing adversarial clone controls, and one compiled/executed
false substitute per root. The pinned network-disabled Docker sanity run
requires two equal positive CTest discoveries in clean normal and fresh
ASan/UBSan modes for every root and control. All twenty roots are
`local_family_verified` local candidates; this is not dataset or release
evidence. See `aider-tasks-spec/aider-text-grid-reshaping/table-pivot.md`.

## Cross-Midnight Intervals Remediation Curriculum

The ten legacy roots remain immutable at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/cross-midnight-intervals/`.
For the user-selected `FAMILY_TYPE=aider-text-grid-reshaping`, plan remedies
and write only the parallel reverify family with:

```bash
python3 scripts/plan_cross_midnight_remedies.py
bash examples/slime/moonlight_cpp_perf/prepare_cross_midnight_aider_tasks.sh \
  --force --verify-core --verify --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/cross-midnight-intervals/`.
The permitted hard count is 8–12 and the owner emits ten replacements. It
checks all 45 unordered pairs separately across the exact seven hard-rule
dimensions, three coherent rename/policy/opposite-end controls, one compiled
and executed topic negative per root, strict prompt/reference roles, and all
26 official C++ holdouts. Mandatory runtime evidence uses the pinned,
network-disabled C++ sanity image for clean normal and fresh ASan/UBSan builds.
All ten roots passed two normal and two fresh ASan/UBSan tests, all ten compiled
topic negatives were rejected, and all three coherent controls passed behavior
tests before semantic rejection. The family is `local_family_verified` with
`docker_sanity` evidence (`locked_oracle: false`). These remain local
candidates, never dataset admission or release evidence.

## Offset-Aware Range Overlap Remediation Curriculum

The legacy ten-root shared fixed-offset policy template remains immutable at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/offset-aware-range-overlap/`.
Its ten corrected v3 roots (within the user-authorized hard-rule bound of 8–12) in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_OFFSET_AWARE_RANGE_OVERLAP_CURRICULUM.md`
materialize only under the requested parallel text-grid tree with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_offset_aware_range_overlap_aider_tasks.sh \
  --force --verify-core --verify --docker-sanity
```

This writes `.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/offset-aware-range-overlap/`.
The owner checks strict prompt/role/reference boundaries, all 45 emitted-family
pairs separately across the seven hard-rule dimensions, all 260 comparisons
with the 26 bound official C++ holdouts, the three coherent adversarial clone
classes, and one compiled/executed topic-specific false substitute per root.
The earlier v2 screen is archived as invalid because it retained task/domain
identifiers and allowed both relay and support augmenting-path matching. The v3
screen strips those naming signals, replaces support matching with a
farthest-frontier minimum interval cover, and records every per-dimension
decision for independent focused assertions.
Final evidence requires three equal positive CTest discoveries in clean normal
and fresh ASan/UBSan builds for every root and control in the pinned,
network-disabled Docker sanity image. The evidence is `docker_sanity`, not a
family-designated locked oracle. These are local candidates only; `clock`,
`gigasecond`, and `meetup` remain permanent official holdouts.

## Clock Arithmetic Remediation Curriculum

The ten legacy cyclic-time roots remain immutable at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/clock-arithmetic/`. The
user-authorized 8–12 hard-rule range is implemented by ten v2 repair-in-place
roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_CLOCK_ARITHMETIC_CURRICULUM.md`
and materialized only beneath the requested parallel family type with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_clock_arithmetic_aider_tasks.sh \
  --force --verify-core --verify --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/clock-arithmetic/`.
The owner validates prompt/role/reference boundaries, all 45 family pairs
separately across the seven hard-rule dimensions, all 260 comparisons with the
bound 26 official C++ holdouts, and the three required coherent adversarial
clone classes. The pinned network-disabled Docker sanity run requires two
equal positive CTest discoveries in clean normal and fresh ASan/UBSan modes for
every root and control, exact live/mounted hashes, and executed rejection of
one topic-specific false substitute per root. See
`aider-tasks-spec/aider-text-grid-reshaping/clock-arithmetic.md`. These are
local candidates only, not admitted SFT data; the official Polyglot `clock`,
`gigasecond`, and `meetup` roots remain permanent holdouts.

## General Calendar Arithmetic Remediation Curriculum

The immutable ten-root v1 policy-wrapper family remains at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/general-calendar-arithmetic/`.
The ten task-spec-v2 roots in
`aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_GENERAL_CALENDAR_ARITHMETIC_CURRICULUM.md`
are materialized only under the parallel reverify root with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_calendar_arithmetic_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-dates-and-clocks/general-calendar-arithmetic/`.
The owner enforces the user-authorized 8–12 count, rereads actual emitted
artifacts for all 45 pairs across seven separate hard-rule dimensions, rejects
three coherent clone controls in every dimension, and screens all 260
candidate/official-holdout pairs. The pinned network-disabled Docker sanity
run requires three equal positive normal and fresh ASan/UBSan CTests for every
root and coherent control, plus compiled/executed rejection of each root's
topic negative. Passing evidence is `docker_sanity`, not a family-designated
locked oracle. These are local candidates only; `clock`, `gigasecond`, and
`meetup` remain permanent official Polyglot holdouts.

## Leap-Year Rule Remediation Curriculum

The immutable five-root predecessor remains under
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/leap-year-rule/`. The user
supplied `FAMILY_TYPE=aider-text-grid-reshaping`, so the eight replacement
roots materialize only under the parallel supplied-type path:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_leap_year_rule_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/leap-year-rule/`.
The owner validates prompt/role/reference boundaries, all 28 replacement pairs
separately across the seven hard-rule dimensions, all 208 comparisons against
the 26 bound official C++ holdouts, three coherent adversarial clone classes,
and one compiling/executed topic negative per root. Final evidence uses the
pinned network-disabled repository C++ sanity image and requires three equal
positive CTest discoveries in clean normal and fresh ASan/UBSan modes for each
reference and coherent control; topic negatives must compile and be rejected
in both modes. The result is `docker_sanity`, not `locked_oracle`, and remains
local candidate evidence only.

## Doubly-Linked-List Remediation Curriculum

The legacy 20-root template family remains preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/doubly-linked-list/`. The remediated v2
family writes only
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/doubly-linked-list/` and uses 20
unique public contracts and logic tags. Materialize, structurally screen, and
run the designated locked normal plus fresh ASan/UBSan verifier with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_doubly_linked_list_aider_tasks.sh \
  --force --verify-core --verify
```

For receipt-free iteration inside the same network-disabled C++ image, use
`--quick-normal`; it never changes oracle status. The final verifier requires
two positive CTest entries in each mode for every root, exact equal counts,
tree-bound receipts, prompt-boundary pass, a `vector_authority_fixture`
rejection, a family similarity score below `0.60`, and a semantic screen
against all available bound official C++ holdouts. See
`aider-tasks-spec/aider-dsa/doubly-linked-list.md`. These roots are local
candidate material only and do not authorize a dataset release.

## Threaded Binary Tree Remediation Curriculum

The legacy 20-root noun-renamed and rebuild-on-delete family remains preserved
at `.w8-biayn/data/aider-tasks/aider-dsa/threaded-binary-tree/`. The v3 family
is generated only under the parallel re-verification root with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_threaded_binary_tree_aider_tasks.sh \
  --force --verify-core --verify
```

The owner emits one repaired representative and 19 replacement IDs with
distinct public contracts and threaded algorithms. Its core gate executes the
`legacy-rebuild-template` rejection, validates prompt and role boundaries,
requires all seven hard-rule dimensions to differ across all 190 emitted-root
pairs, injects and rejects the three required adversarial clone classes, and
screens every available official C++ holdout. Each root also emits a private
topic-specific false implementation. Final evidence uses the pinned
network-disabled C++ sanity image for clean normal and fresh ASan/UBSan builds,
then strictly compiles each false implementation and proves the same discovered
tests reject it. The earlier v2 aggregate-similarity/shared-fixture conclusion
is withdrawn. These remain local candidate tasks, not a dataset release.

## XOR Linked List Remediation Curriculum

The legacy 20-root renamed add/remove/move template remains preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/xor-linked-list/`. The v2 safe
slot-index XOR-chain family in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_XOR_LINKED_LIST_CURRICULUM.md`
is materialized only under the sibling reverify root with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_xor_linked_list_aider_tasks.sh \
  --force --verify-core --verify
```

This writes `.w8-biayn/data/aider-tasks-reverify/aider-dsa/xor-linked-list/`.
One legacy root is repaired in place, 16 roots are replaced, and three
policy/semantic twins are rejected rather than counted. `--verify-core`
derives seven hard-rule dimensions from emitted docs, APIs, necessary state,
references, boundary tests, per-operation vector/value traces, and compiled
false substitutes for all 136 counted pairs. The production screen and focused
tests reject renamed, constants/policy-only, and opposite-end clones.
`--verify` requires the pinned network-disabled C++ image and records three
positive CTest entries in both clean normal and fresh ASan/UBSan modes plus one
compiled and executed failing substitute for every counted root. These are
local candidate tasks only; the official Polyglot `linked-list` benchmark
remains a permanent holdout.

## Sequence Pattern Curriculum

The legacy 20-root generic matcher family remains preserved under
`.w8-biayn/data/aider-tasks/aider-dsa/sequence-pattern/`. The 20 v2
algorithmically distinct replacements in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SEQUENCE_PATTERN_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_sequence_pattern_aider_tasks.sh \
  --force --verify-core --verify
```

This writes only
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/sequence-pattern/`. The owner
checks strict prompt/role boundaries, 20 executed task-specific false
substitutes, all 190 family pairs, all bound official C++ holdouts, and every
reference through three positive CTest entries in clean normal and fresh
ASan/UBSan modes. Final local-family evidence must run in the pinned
network-disabled Docker sanity image; a host verifier remains iteration
evidence. These roots are local diagnostics only, and the official Polyglot
`sublist` benchmark remains a permanent holdout.

## Run-Length-Encoding Remediation Curriculum

The legacy 20-root noun-parameterized bounded-run template remains preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/run-length-encoding/`. Its v2 remediation
retains one repairable representative, replaces 19 roots with new IDs, and
materializes only the parallel tree:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_run_length_encoding_aider_tasks.sh \
  --force --verify-core --verify
```

The owner rereads each actual emitted root and compares all 190 family pairs
across seven hard-rule dimensions: public API, owned state/algorithm,
mutation/selection, invalid/boundary behavior, reference control flow,
deterministic oracle, and topic-specific negative fixture. Its focused tests
copy an emitted root, apply the required domain/identifier-renamed,
constants/policy-only, and opposite-end-selection clone mutations, and require
the production pair screen to reject each copy; changing only the bad
substitute cannot rescue duplicated primary logic. The owner also screens all
20 roots against the 26 bound official C++ holdouts, validates
prompt/role/reference boundaries, and compiles one expected-failing
task-specific substitute per root. Forced regeneration invalidates stale
owner-recognized receipts before verification. Each stateful hidden oracle
also invokes every emitted public operation and compares complete public
state/order and query results against an independent value/vector model after
each mutation; the owner rejects missing trace coverage. The pinned, network-disabled
Docker sanity run passed three normal and three fresh ASan/UBSan CTests for
every root. The corrected result is `local_family_verified` with
`docker_sanity` evidence, not a locked oracle or dataset-release claim. See
`aider-tasks-spec/aider-dsa/run-length-encoding.md`.

## Skip List Curriculum

The legacy 20-root renamed CRUD/rank/page family remains preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/skip-list/`. The 20 v3 mechanism-specific
roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SKIP_LIST_CURRICULUM.md`
are materialized only into the parallel re-verification root with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_skip_list_aider_tasks.sh \
  --force --verify-core --verify
```

This writes `.w8-biayn/data/aider-tasks-reverify/aider-dsa/skip-list/`. The
owner verifies all 190 family pairs across seven emitted-artifact hard-rule
dimensions and all 520 bound official-holdout comparisons. The required
domain-renamed, constants-only, and opposite-end clones are made from an
emitted root and rejected by the exact production pair evaluator. Every root
has a complete topic-specific false source; Docker must configure and compile
it under the reference target, discover the same two tests, execute visible and
private CTests, and observe at least one task-test failure. Marker scans and
configure/build failures are not negative evidence. The pinned
network-disabled Docker sanity image also runs exactly two normal and two fresh
ASan/UBSan tests per root with exact mount-hash agreement. The evidence class
is `docker_sanity`, not a family-designated locked oracle. Only a receipt that
satisfies all these gates may mark the roots `local_family_verified`; they
remain local candidate material and are not admitted SFT data.
The v3 receipt satisfies those gates: 40 normal, 40 fresh sanitizer, and 40
discovered negative-test entries across 20 rejected false implementations.

## Robot State-Simulation Curriculum

The 20 newly authored roots in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ROBOT_SIMULATION_CURRICULUM.md`
are materialized and verified with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_robot_simulation_aider_tasks.sh --verify
```

This preserves `.w8-biayn/data/aider-tasks/aider-dsa/robot-simulation/` as legacy
audit input and writes the algorithmically distinct v2 replacements beneath
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/robot-simulation/`. The owner
rejects rename-only copies through its semantic-profile and
`legacy-template-clone` negative-fixture screen. The roots remain local
diagnostics only; official robot-related Aider holdouts remain excluded.

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

## Sliding-Window Maximum Remediation Curriculum

The legacy 20-root monotonic-deque template remains preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/sliding-window-maximum/`. The 20 v2
one-to-one replacements in
`aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SLIDING_WINDOW_MAXIMUM_CURRICULUM.md`
materialize only under the parallel re-verification root with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_sliding_window_maximum_aider_tasks.sh \
  --force --verify-core --verify-docker
```

This writes `.w8-biayn/data/aider-tasks-reverify/aider-dsa/sliding-window-maximum/`.
The owner enforces 20 unique API/mechanism profiles, complete all-pairs
semantic comparison, four adversarial controls, prompt/reference boundaries,
and the bound official-holdout screen. Final normal and fresh ASan/UBSan
evidence uses the pinned repository C++ sanity image with `--network none` and
is labeled `docker_sanity`, not `locked_oracle`. These roots remain local
candidate material, not admitted SFT data.

Local task materialization is an authoring step only. Before using a task in
a future dataset, first publish an approved admission contract covering its licensing,
provenance, benchmark-contamination, compiler-image, normal/sanitizer oracle,
family/split, renderer/token/mask, release, producer verification, and
consumer verification gates. Never label a local task directory or one-row
smoke dataset as a ready dataset release.

## Matrix Rotation By 90 Degrees Remediation Curriculum

The legacy 20-root square-grid template remains preserved at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/matrix-rotation-90/`.
The v2 remediation repairs one independently justified in-place layer-cycle
root and replaces 19 semantic duplicates with distinct dense, rectangular,
sparse-coordinate, packed-bit, vector-field, glyph, oriented-tile, subwindow,
perimeter, voxel, RLE, region, polyline, lazy-view, dihedral-composition,
stencil, embedded-graph, planar-channel, block-sparse, and quadtree mechanisms.
Materialize only the parallel tree with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_matrix_rotation_aider_tasks.sh \
  --force --verify-core --verify --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/matrix-rotation-90/`.
The owner validates prompt and reference boundaries, executes one compilable
topic-specific false substitute per root, and compares all 190 emitted-family
pairs separately across the seven hard-rule dimensions: public API, owned
state/algorithm, mutation/selection rules, invalid/boundary behavior,
reference control flow, deterministic oracle, and topic-specific negative
fixture. One aggregate score cannot satisfy this gate. The same evaluator must
reject coherent domain/identifier-renamed, constants/policy-only, and
opposite-end-selection clones in all seven dimensions. The owner also performs
all 520 comparisons against the bound 26 official C++ holdouts and requires
three equal positive CTest discoveries for every root and every coherent clone
control in clean normal and fresh ASan/UBSan modes. Final evidence uses the
pinned network-disabled repository C++ sanity image and is labeled
`docker_sanity`, not `locked_oracle`. See
`aider-tasks-spec/aider-text-grid-reshaping/matrix-rotation-90.md`. These roots
remain local candidates, not admitted SFT data or release evidence.

## Transpose Remediation Curriculum

The immutable 20-root legacy ledger template remains under
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/transpose/`. The v2
family repairs the lexicographically smallest independently justified dense
root and replaces 19 semantic duplicates with distinct dense, in-place,
ragged-mask, CSR/CSC, coordinate, packed-bit, tiled, streaming, tensor, graph,
relation, run-encoded, planar-channel, triangular, lazy-view, anti-diagonal,
banded, common-rectangle, block-sparse, and permutation mechanisms.
Materialize only the parallel tree:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_transpose_aider_tasks.sh \
  --force --verify-core --verify --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/transpose/`.
The owner validates prompt/role/reference mapping, all 190 emitted-family pairs
in seven separate hard-rule dimensions, all 520 comparisons against the bound
26 official C++ holdouts, the three required coherent clone controls, and one
strict compiled/executed false substitute per root. The pinned,
network-disabled Docker sanity image discovers and passes three normal and
three fresh ASan/UBSan tests per root and per control with exact mounted/live
tree-hash agreement. The family is `local_family_verified` with
`docker_sanity` evidence, not a family-designated locked oracle. See
`aider-tasks-spec/aider-text-grid-reshaping/transpose.md`. These roots are
local candidates only, not admitted SFT data or release evidence.

## Nth And Final Occurrences Remediation Curriculum

The immutable 10-root legacy selector template remains at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/nth-and-final-occurrences/`.
The canonical v2 owner uses the user-authorized 8–12 hard-size range and emits
exactly 10 independently implemented roots only under the parallel tree:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_nth_final_occurrences_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

The owner compares all 45 actual emitted pairs separately across the seven
hard-rule dimensions, rejects coherent identifier/domain, constants/policy,
and opposite-end clones, screens all 26 official C++ holdouts, and compiles
and executes one false substitute per root. Final evidence requires two equal
positive CTests in clean normal and fresh ASan/UBSan modes for every root and
control in the pinned network-disabled Docker sanity image. These remain local
candidate tasks; dataset handoff is `not_requested`.

## Countdown Timers Arithmetic Curriculum

The ten legacy elapsed-duration state-machine roots remain immutable at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/countdown-timers/`. Their v2
remediation materializes only the parallel re-verification tree with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_countdown_timers_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-dates-and-clocks/countdown-timers/`.
The user-authorized hard-rule count is 8–12 and the owner emits ten roots. It
checks all 45 pairs separately across the exact seven required dimensions, all
260 comparisons with the bound 26 official C++ holdouts, one executed
topic-specific false substitute per root, and coherent domain-renamed,
constants/policy-only, and opposite-end-selection controls. The final pinned
network-disabled Docker sanity gate requires equal positive normal and fresh
ASan/UBSan discovery for every root and control. See
`aider-tasks-spec/aider-dates-and-clocks/countdown-timers.md`. These roots
remain local candidates only; official C++ benchmark families remain permanent
holdouts.

## Elapsed-Time Accumulation Arithmetic Curriculum

The legacy ten-root generic set-and-sum template remains preserved under
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/elapsed-time-accumulation/`.
The remediation retains eight independently implemented ledger, interval,
correction, state-machine, weighted-load, interval-union, latest-attempt, and
per-incident mechanisms and rejects two semantic duplicates. The user-authorized
hard family count is 8–12. Materialize only the parallel reverify tree with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_elapsed_time_accumulation_aider_tasks.sh \
  --force --verify-core --verify-docker
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/elapsed-time-accumulation/`.
The owner derives seven separate evidence dimensions from emitted artifacts for
all 28 unordered pairs, rejects coherent renamed-domain, constants/policy, and
opposite-end controls, screens the bound 26 official C++ holdouts, and requires
every reference plus topic negative to compile in the pinned network-disabled
Docker sanity image. Normal and fresh ASan/UBSan discovery counts must be equal
and positive. These are local diagnostics only, not admitted SFT data.

## Maze To Graph Curriculum

The immutable 20-root legacy `GraphAudit`/four-neighbor template remains at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/maze-to-graph/`. Its 20
v2 replacements use distinct contraction, region-incidence, visibility,
low-link, state-expansion, condensation, product-graph, and weighted-distance
mechanisms. Materialize only the parallel tree:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_maze_to_graph_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/maze-to-graph/`.
The owner validates prompt/reference roles and compares all 190 emitted-family
pairs separately across seven hard-rule dimensions, in addition to the 190
aggregate pairs and all 520 comparisons with the bound 26 official C++
holdouts. Its three required adversarial controls are coherent task clones,
not text-only mutations, and each must fail all seven dimensions. The pinned
network-disabled Docker sanity run requires three equal positive CTest
discoveries in clean normal and fresh ASan/UBSan modes, executes one strict
topic-specific false substitute per root, and compiles and executes all three
controls in both modes while binding their mounted hashes. See
`aider-tasks-spec/aider-text-grid-reshaping/maze-to-graph.md`. These are locally
verified candidates, not SFT data, a release, or benchmark uplift.

## ASCII Art Scaling Curriculum

The legacy 20-root class/domain/marker template remains preserved at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/ascii-art-scaling/`.
Its v2 remediation replaces 19 semantic duplicates and repairs the one
independently justified representative. Materialize only the parallel tree:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_ascii_art_scaling_aider_tasks.sh \
  --force --verify-core --verify
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/ascii-art-scaling/`.
The owner compares all 190 emitted-family pairs after normalizing identifiers,
literals, clean-room domain nouns, and endpoint direction, and runs all 520
comparisons against the bound 26 official C++ holdouts. The same production
pair screen must reject full copied-root domain-renamed, constants/policy-only,
and opposite-end clones. It validates prompt/role/reference boundaries and
builds 20 distinct semantic false substitutes with the exact strict reference
flags. Host verification is iteration evidence only and records
`not_completed` when CMake is absent. The mandatory final gate is the
owner-controlled `--docker-sanity` run in the pinned network-disabled C++
image; it requires three equal positive CTest discoveries in clean normal and
fresh ASan/UBSan modes, exact exit-1/empty-diagnostic direct negative execution
in both modes, and independent Docker-mounted tree hashes matching the owner
for each of 20 roots. A stale escalated filesystem uses the owner's
snapshot-safe `/tmp` result export and live import path. The resulting evidence
is `docker_sanity` with `locked_oracle: false`, because the family has no
designated locked grader. These roots are local candidates, not admitted SFT
data or release evidence.

## Run-Length Image Encoding Curriculum

The immutable legacy row-encoder/decoder template remains under
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/run-length-image-encoding/`.
Materialize its twenty algorithmically distinct replacements only beneath the
parallel reverify root:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_run_length_image_encoding_aider_tasks.sh --force --verify-core
```

The owner checks prompt and role boundaries, reference mapping, all 190
artifact-derived family pairs, all 26 official C++ holdouts, and the three
mandatory adversarial clone classes. The final network-disabled pinned-image
receipt records three equal positive normal and fresh ASan/UBSan discoveries
per root, including an executed false substitute. Passing roots are
`local_family_verified` local candidates only; dataset handoff is
`not_requested`.

## Flood Fill Curriculum

The 20 newly authored connected-region roots in
`aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_FLOOD_FILL_CURRICULUM.md`
are materialized reproducibly with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_flood_fill_aider_tasks.sh --force --verify-core --verify
```

This preserves the legacy family at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/flood-fill/` and writes
the 20 v2 replacements only beneath
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/flood-fill/`.
The owner checks the one-to-one remedy records, distinct public APIs and
reference control flow, all 190 normalized artifact pairs, the required three
adversarial clone classes, compiled/executed per-root negative fixtures, prompt
and role boundaries, reference mapping, and holdout separation before normal
and fresh ASan/UBSan verification. Host verification does not satisfy the mandatory
network-disabled locked-runtime gate. These remain local candidate tasks, not
admitted SFT data or benchmark substitutes.

## Pattern Printing Curriculum

The legacy 20-root centered-span/stripe template remains preserved under
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/pattern-printing/`. The
v4 family repairs one independently justified archway root and replaces the
other 19 semantic duplicates with distinct capacity, chevron, truss, pennant,
canopy-union, cone-stencil, bracket, silhouette, occluded-ray, quilt-ring,
token-layout, trellis, ray-overlay, aisle-run placement, glyph, allocation, cadence,
rink-overlay, and brace-interpolation mechanisms. The curriculum lives in
`aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_PATTERN_PRINTING_CURRICULUM.md`
and is materialized only under the parallel reverify root with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_pattern_printing_aider_tasks.sh \
  --force --verify-core --verify --docker-sanity
```

This writes
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/pattern-printing/`.
The owner requires one remedy record/specification per legacy root, strict
prompt/role/reference boundaries, twenty executed topic-specific false
substitutes, and all 190 emitted-family pairs compared separately across
public API, owned state/algorithm, mutation/selection rules, invalid/boundary
behavior, reference control flow, deterministic oracle, and topic-specific
negative fixture. One aggregate score cannot satisfy this gate. The focused
test constructs coherent domain/identifier-renamed, constants/policy-only,
and opposite-end-selection clones and requires all three to be rejected in all
seven dimensions. The owner also runs the aggregate duplicate screen and all
520 comparisons against the bound 26 official C++ holdouts. The final
network-disabled pinned Docker sanity gate
requires three equal positive CTest discoveries in clean normal and fresh
ASan/UBSan builds for every root with exact live/mounted tree-hash agreement.
Its v4 receipt binds the seven-dimension family-screen hash. The evidence is
`docker_sanity`, not a family-designated locked oracle. These are local
candidates only; the official Polyglot `diamond` task remains a permanent
holdout.

## Spiral Matrix Curriculum

The 20 legacy domain boundary-tour roots in
`aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_SPIRAL_MATRIX_CURRICULUM.md`
are preserved as immutable audit input. Re-verification found one shared
shrinking-ring template and semantic overlap with the permanent official
`spiral-matrix` holdout, so all 20 dispositions are `reject`. Reproduce the
rejection audit with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_spiral_matrix_aider_tasks.sh
bash examples/slime/moonlight_cpp_perf/prepare_spiral_matrix_aider_tasks.sh --docker-audit
```

This never modifies
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/spiral-matrix/` and emits
no C++ candidate roots. It writes hash-bound remedy/audit evidence only under
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/spiral-matrix/.state/`.
The owner derives seven-dimension hard-rule evidence from actual artifacts for
all 190 legacy pairs, and its focused test constructs the three required clone
classes before proving that the production screen rejects each one.
The optional Docker command audits the rejected historical references in clean
normal C++17 and fresh ASan/UBSan modes; that evidence cannot override the
earlier benchmark rejection. See
`aider-tasks-spec/aider-text-grid-reshaping/spiral-matrix.md`. No root reaches
`local_family_verified`, and no dataset-release claim is made.
