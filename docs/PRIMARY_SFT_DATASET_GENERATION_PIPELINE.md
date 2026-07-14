# Primary SFT Dataset Generation Pipeline

Status: **design revised; implementation not started**
Contract version: `aider-sft-pipeline-v1.3`
Initial dataset profile: `aider-sft-pilot-v1`

Contract V1.3 supersedes V1.2 and V1.1 before the pilot profile has been
implemented or frozen into a ready dataset. Therefore the profile name remains
`aider-sft-pilot-v1`. After the first checked-in profile lock or ready bundle,
any semantic change to its schema, grader, limits, rendering, tokenizer, or
review policy requires a new profile ID rather than an in-place
reinterpretation.

## Authority And Required Reading

This is the repository's **primary SFT dataset generation pipeline** for
building Aider-style C++ supervised fine-tuning data from non-benchmark
Exercism tasks and LLM-assisted task authoring. It is the normative
implementation specification for that pipeline.

An agent implementing or changing this pipeline must read, in order:

1. `AGENTS.md` (the symlink to `.agents/REPO_GUIDE.md`);
2. `README.md`;
3. `ROADMAP.md`;
4. `.agents/skills/w8-biayn-framework/SKILL.md`;
5. this document;
6. `docs/single_sample_for_sft.md` for the Aider `whole` diagnosis and row
   shape;
7. `src/w8_biayn/integrations/moonlight_aider_task_sft.py` and
   `src/w8_biayn/integrations/moonlight_aider_task_eval.py` for the existing
   one-task seed implementation;
8. `src/w8_biayn/integrations/slime_polyglot_cpp.py` for the existing
   fingerprinted Docker oracle and reference-file mapping patterns;
9. the active GLM SFT consumer in
   `examples/slime/glm47_cpp_perf/glm47_cpp_perf.sh`.

If another document conflicts with this document about the multi-task
Aider-style SFT dataset pipeline, this document wins. The two single-sample
documents remain valid smoke-test references; they are not the production
multi-task design.

This document is intentionally versioned. Future requirements must update the
contract version or dataset profile rather than silently changing the meaning
of an already admitted dataset.

## Purpose

The pipeline must reproducibly turn verified C++ task roots into an immutable,
SLIME-compatible SFT dataset bundle. The initial pilot proves data engineering,
not model quality.

The pilot succeeds when it can:

- admit exactly 96 total task roots;
- combine source-backed and LLM-assisted tasks through one canonical schema;
- create 72 train, 12 validation, and 12 internal-test roots;
- render one SFT row per training root;
- verify every starter, reference, grader, and rendered answer before
  admission;
- exclude all official Aider Polyglot C++ benchmark tasks and related copies;
- resume safely after interruption;
- reject bad tasks without weakening gates;
- backfill category deficits until the admitted quota is reached or a declared
  budget is exhausted;
- emit manifests, per-task receipts, review material, and a machine-verifiable
  readiness receipt.

## Explicit Non-Goals

The initial pipeline must not:

- run GLM-4.7-Flash or any other target model to collect task responses;
- create repair-response examples, failed-response corrections, preference
  pairs, or retry conversations;
- train a model;
- run base, SFT, GRPO, or official benchmark evaluation;
- claim or require Aider benchmark uplift;
- optimize C++ runtime or use the PIE performance reward;
- include official benchmark tasks in train, validation, or internal test;
- manufacture row count by making superficial variants of one root task;
- write a custom trainer.

An LLM API may be used only as a task-curation/authoring tool. Its task drafts
are pipeline inputs, not target-model responses and not SFT repair rows.

## Terminology

- **Candidate task**: a discovered source task or LLM-authored draft that has
  not passed admission.
- **Source-backed task**: a task derived from a pinned, explicitly enumerated
  Exercism C++ task folder.
- **LLM-assisted task**: a novel task whose blueprint or files were authored
  through an LLM API and then admitted by deterministic mechanical gates plus
  the required fingerprint-bound human semantic review.
- **Root task**: one semantic programming problem before row rendering.
- **Task family**: a root task and any translations, rewrites, ports, or other
  semantically related forms that must stay in one split.
- **Canonical task**: the source-independent, normalized representation of
  docs, starter files, solved files, grader assets, provenance, and receipts.
- **Admitted task**: a canonical task that passed all blocking gates.
- **SFT row**: the serialized user/assistant conversation for one admitted
  training root.
- **Evaluation root**: an admitted validation or internal-test task package.
  It is not a training row and its answer is never placed in `train.jsonl`.
- **Oracle/reference**: the known solved editable-file state used to verify the
  grader and construct the assistant target.
- **Readiness**: a property of the dataset bundle and its receipts, not a model
  performance claim.

The initial profile therefore has 96 total roots but only 72 SFT training
rows.

## Frozen Pilot Contract

### Counts

The default profile is:

| Provenance | Train | Validation | Internal test | Total |
|---|---:|---:|---:|---:|
| Source-backed no-deferral target | 57 | 9 | 9 | 75 |
| LLM-assisted no-deferral target | 15 | 3 | 3 | 21 |
| **Total admitted** | **72** | **12** | **12** | **96** |

The source/LLM cells are initial composition targets. The blocking release
contract is:

- `total_admitted == 96`;
- `train == 72`, `validation == 12`, and `test == 12` for the pilot profile;
- `llm_assisted_admitted >= 21`;
- every split contains at least one LLM-assisted task;
- every primary category contains at least two LLM-assisted tasks overall;
- the train split contains at least one LLM-assisted task in every primary
  category;
- all other admission gates pass.

The selected source revision contains 75 explicitly frozen non-benchmark
Exercism C++ candidates: 60 practice roots and 15 concept roots. Appendix A is
the normative list until the implementation materializes the identical
checked-in JSON manifest. The earlier planning assumption of 84 source roots
must not be reintroduced: it is not supported by the selected official source
snapshot.

Discovery does not equal admission. If a source candidate fails or the
approved taxonomy/split solver must defer it to preserve an exact category
cell, it does not count in this pilot and there is no unlisted source reserve
in V1. Generate an LLM-assisted backfill in the same category/split cell.
Consequently, 75 source and 21 LLM are a no-deferral composition target, while
21 is only the minimum LLM count. Every deferred source and composition
deviation must be explicit in the final receipt; a valid deferred source may
remain available to a later dataset version.

The LLM scheduler should normally request more than 21 drafts because rejected
drafts do not count. It continues until at least 21 LLM-assisted tasks are
admitted, all total/category/provenance-coverage constraints are satisfied, or
the configured call/cost budget is exhausted. Budget exhaustion makes the run
incomplete; it is never permission to admit a weak task.

### Primary Categories

Every root has exactly one primary category using the repository's stable
six-group Aider C++ taxonomy:

1. `Algorithms & data structures`
2. `Text & parsing`
3. `Numerical reasoning`
4. `Time & date`
5. `State & concurrency`
6. `Logic, grids & games`

The 96-task target is exactly 16 roots per primary category: 12 train, 2
validation, and 2 internal-test roots. The LLM scheduler fills category/split
deficits rather than generating arbitrary tasks.

Each task also carries non-exclusive tags such as:

- algorithms: sorting, graph search, recursion, dynamic programming;
- data model: collections, trees, grids, stateful objects, ownership;
- language surface: classes, templates, operator overloading, concurrency;
- input surface: text parsing, validation, numerical boundaries, dates;
- file surface: header-only, source/header pair, or multi-file;
- difficulty: `easy`, `medium`, or `hard` based on implementation and test
  surface, never observed model outcomes.

Difficulty and tags are stratification/reporting metadata. They must not be
derived from benchmark pass rates. Each primary category must contain all
three difficulty levels unless the final split reviewer records a blocking
exception and the profile is versioned again.

This pilot is deliberately **coverage-balanced**, not weakness-weighted. No new
target-model responses are collected, so the pipeline cannot honestly infer
where GLM-4.7-Flash currently struggles. A future weakness-weighted profile may
consume a separately frozen, pre-existing error-analysis artifact, but it must
not silently change `aider-sft-pilot-v1`.

### Official Benchmark Holdout

The following 26 official Aider Polyglot C++ task IDs are a permanent denylist
for this dataset profile:

```text
all-your-base
allergies
bank-account
binary-search-tree
circular-buffer
clock
complex-numbers
crypto-square
diamond
dnd-character
gigasecond
grade-school
kindergarten-garden
knapsack
linked-list
meetup
parallel-letter-frequency
perfect-numbers
phone-number
queen-attack
robot-name
space-age
spiral-matrix
sublist
yacht
zebra-puzzle
```

The implementation must obtain this set from one shared repository-owned
manifest/constant used by both dataset contamination checks and official
benchmark reporting. Do not create another drifting copy in implementation
code. This list is repeated here so the design remains understandable.

The denylist is broader than exact slugs. Reject:

- the exact task from any source or language;
- a renamed or lightly reworded copy;
- a port with the same behavioral contract and distinctive edge cases;
- any task whose starter, reference, tests, or normalized instructions match a
  benchmark artifact;
- a generated task that a contamination reviewer cannot confidently separate
  from a held-out benchmark root.

Generic concepts such as trees, calendars, parsing, matrices, or concurrency
remain allowed. The pipeline is meant to teach general capabilities without
copying held-out problems.

## Pinned Inputs And Run Identity

Every run begins from a versioned configuration and produces a lock. The lock
must include:

- pipeline contract and schema versions;
- dataset ID/profile and split seed;
- official Exercism C++ repository URL and exact commit;
- the enumerated 75-task candidate manifest and its SHA-256;
- Aider repository URL and exact parser/prompt commit;
- Polyglot repository URL and exact benchmark commit;
- the 26-task denylist hash;
- Docker grader image name and immutable image ID/digest;
- compiler, CMake, test harness, and grader protocol versions;
- exact CMake generator, compiler binary identities, and sandbox policy;
- GLM tokenizer repository/revision or local tokenizer file hashes;
- exact chat-template hash;
- exact chat-template invocation kwargs and final-only/thinking policy;
- raw-message SFT rollout/loss-mask adapter identity and token-evidence schema;
- maximum sequence length;
- prompt-renderer version;
- taxonomy version;
- LLM curator provider, exact model ID/revision where exposed, prompt-template
  hashes, decoding settings, and budgets;
- source and generated-task license/provenance policy;
- human-review policy.

Required upstreams:

- Exercism C++: `https://github.com/exercism/cpp`;
- Aider: `https://github.com/Aider-AI/aider`;
- Aider Polyglot: `https://github.com/Aider-AI/polyglot-benchmark`.

The future repo-owned upstream registry must expose the exact keys
`exercism-cpp`, `aider`, and `aider-polyglot`. A clean clone must be able to
acquire the pinned commits with:

```bash
uv run w8-biayn upstreams clone exercism-cpp
uv run w8-biayn upstreams clone aider
uv run w8-biayn upstreams clone aider-polyglot
```

Those commands are future implementation contracts. They must verify the
requested commit and clean-tree identity, and must never fall back to a branch
tip. Existing one-off checkouts are study material, not pipeline inputs.

The pilot profile fixes these identities:

| Input | Frozen identity |
|---|---|
| Exercism C++ | `d2babb2bd750c884abf86ce52dde274ae7de9749` |
| Aider parser/prompt | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` |
| Aider Polyglot holdout | `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f` |
| GLM tokenizer/model repository | `zai-org/GLM-4.7-Flash` |
| GLM tokenizer/model revision | `7dd20894a642a0aa287e9827cb1a1f7f91386b67` |
| SLIME | `a897e1f40357fdf3b148f1eb4ce26e1aeccfcd2c` |
| Task/grader language standard | `C++17` |
| Grader protocol | schema/protocol version `2` |
| LLM task scaffold | `aider-sft-cmake-catch-v1` |
| CMake generator | `Unix Makefiles` |
| Readiness receipt schema | `2` |
| GLM sequence length | `4096` |
| SLIME loss-mask type | `qwen`, verified against the pinned tokenizer |
| Chat-template policy | final answer only; exact kwargs include `enable_thinking=false` |
| SFT message mode | raw `messages`; dataset-loader `--apply-chat-template` forbidden |
| SFT mask adapter | repo-owned, kwargs-aware `w8-aider-sft-mask-v1` |

The pilot uses **final-answer-only supervision**: the assistant message contains
only the strict Aider `whole` file blocks and no generated rationale or private
reasoning. The checked-in profile must bind the exact tokenizer
`apply_chat_template` kwargs, including `enable_thinking=false`. If the pinned
tokenizer does not support that exact invocation, the profile is not frozen;
silently dropping the kwarg or substituting a fallback policy is forbidden.
Dataset rendering, verification, and the consuming SLIME lane must use
byte-identical template policy. No component may rely on an unstated default.

The benchmark manifest must be reconstructed from the pinned Polyglot checkout
and must match the 26 IDs in this document exactly before source discovery.
The source manifest must match Appendix A exactly before admission. A different
upstream revision, task set, tokenizer, or parser requires a new dataset
profile; it is not a resumable change.

The implementation must not fall back to `main`, `latest`, an unpinned API
model alias, or an unrecorded local checkout. If an LLM curator provider does
not expose an immutable model revision, the profile must record the most
specific dated model ID available, the provider-returned model identity, the
normalized response hash, and mark API generation as non-replayable. An
undated floating alias is not admitted for the pilot.

### Pre-Implementation Freeze Gate

Implementation may scaffold schemas and no-spend commands, but `build` must
refuse paid calls or admission until all of the following checked-in profile
inputs exist and reconcile with this document:

- `configs/aider_sft/pilot-v1.toml`;
- `manifests/aider_sft/pilot-v1-source.json`, containing Appendix A;
- `manifests/aider_sft/aider-polyglot-cpp-26.json`;
- exact compiler paths/hashes, `Unix Makefiles` generator, and sandbox runtime
  policy;
- immutable Docker image and toolchain identities;
- the approved Exercism grader-support bundle manifest and hashes;
- the repo-owned LLM CMake/test scaffold identity;
- explicit LLM provider/model, rate, token, call, wall-time, and spend caps;
- a reviewed LLM-output usage/licensing decision;
- contamination normalizers and review thresholds;
- exact chat-template kwargs and final-only/thinking policy;
- the raw-message, kwargs-aware SFT mask-adapter and token-evidence identities;
- the reviewer identity policy.

Each source-manifest entry binds source kind, slug, full source-relative path,
tree hash, task-family ID, primary category, tags, difficulty, intended split
cell, SPDX license, and enabled/disabled status. `inventory` deterministically
writes a proposed manifest under the ignored output root; it never edits the
repository. A human reviews that proposal and deliberately promotes the exact
approved file to the checked-in path before paid generation or admission.
Promotion must use the repo-owned, no-spend `inventory-promote` command defined
below; an implementation must not require an undocumented copy/edit step.

`plan` must report `profile_not_frozen` and list missing fields rather than
choosing values for the operator. The future config schema must reject unknown
keys and bind every default into `config.lock.json`.

Pinned source clones belong under `.cache/upstreams/` through the repo-owned
upstream workflow. Generated data and run state belong under `.w8-biayn/` and
must remain untracked.

## Required Future CLI Surface

These commands are an implementation contract; they do not exist yet. The
implementation must expose them through the repository CLI rather than a
one-off data-munging script:

```bash
# No-spend, no-generation plan and identity validation.
uv run w8-biayn data aider-sft plan \
  --config configs/aider_sft/pilot-v1.toml

# Discover/freeze source inventory and show category deficits.
uv run w8-biayn data aider-sft inventory \
  --config configs/aider_sft/pilot-v1.toml \
  --out .w8-biayn/data/aider-sft-pilot-v1

# Promote only an exactly approved inventory proposal into the repository.
uv run w8-biayn data aider-sft inventory-promote \
  --proposal .w8-biayn/data/aider-sft-pilot-v1/private/inventory/proposed-source.json \
  --decisions /path/to/source-inventory-decisions.jsonl \
  --out manifests/aider_sft/pilot-v1-source.json

# Build/resume the bundle. Paid LLM use requires an explicit acknowledgement.
uv run w8-biayn data aider-sft build \
  --config configs/aider_sft/pilot-v1.toml \
  --out .w8-biayn/data/aider-sft-pilot-v1 \
  --resume \
  --acknowledge-paid-llm-calls

# Export deterministic task cards and approval scopes. No API calls.
uv run w8-biayn data aider-sft review-export \
  --root .w8-biayn/data/aider-sft-pilot-v1 \
  --out .w8-biayn/data/aider-sft-pilot-v1/private/review/export

# Import structured, fingerprint-bound human decisions.
uv run w8-biayn data aider-sft review-import \
  --root .w8-biayn/data/aider-sft-pilot-v1 \
  --decisions /path/to/review-decisions.jsonl

# Render/screen the frozen split; after release review, write readiness.
uv run w8-biayn data aider-sft finalize \
  --root .w8-biayn/data/aider-sft-pilot-v1

# Recompute manifests, counts, hashes, rows, and readiness locally.
uv run w8-biayn data aider-sft verify \
  --root .w8-biayn/data/aider-sft-pilot-v1

# Export a private-asset-free, internal-research SLIME SFT consumer bundle.
uv run w8-biayn data aider-sft export \
  --root .w8-biayn/data/aider-sft-pilot-v1 \
  --audience slime-sft \
  --out .w8-biayn/data/aider-sft-pilot-v1-slime

# Consumer-side verification that needs no private graders or references.
uv run w8-biayn data aider-sft verify-export \
  --root .w8-biayn/data/aider-sft-pilot-v1-slime
```

Required command behavior:

- `plan` must never call an LLM API, start a model server, or mutate paid
  external state;
- `inventory` may inspect pinned local sources but must not author tasks;
- `inventory-promote` writes only the exact proposal named by an approving
  `source_inventory` decision and refuses stale fingerprints or other edits;
- `build` is resumable and may make curator API calls only after an approved
  `llm_usage_terms` decision, explicit paid acknowledgement, complete source
  admission, and a passing generation-capacity/budget report;
- `build` leaves each affected candidate at `awaiting_task_review`; it may
  continue independent work but cannot self-approve. After a valid decision is
  imported, a later build/resume may advance that candidate mechanically;
- `review-export` is deterministic and contains no hidden file contents in
  prompt-preview fields. It can export `llm_usage_terms` before paid calls and
  `dataset_release` only after final rendering/screening;
- `review-import` accepts only schema-valid decisions bound to the current
  scope-specific subject fingerprint and never edits canonical artifacts;
- the first eligible `finalize` invocation freezes the approved split, renders
  rows, reruns final contamination/token checks, and stops at
  `awaiting_release_review`. A rejected task invalidates the split approval and
  returns the run to pool filling; an approval-only final screen emits the
  fingerprinted `dataset_release` review package;
- a later `finalize`, after a matching `dataset_release` approval, generates
- a `dataset_release` rejection that changes only release presentation returns
  to `final_screened`, regenerates that package, and requires a new approval. A
  correction that changes any task, row, label, family, or selected set
  invalidates the split and returns to pool filling;
  `manifest.json` and writes `readiness.json` last;
- `verify` is network-free, reruns deterministic reconciliation, and validates
  existing image-bound oracle receipts by fingerprint. An explicit
  `--rerun-oracles` mode may execute Docker again but remains network-free. It
  materializes only in external scratch space, compares results with the bound
  receipts, and writes any diagnostic report outside the immutable ready root;
- `export` requires a verified ready root and emits only the audience-approved
  files plus token evidence, their manifest, dataset card, NOTICE, and license
  records. V1 refuses a public redistribution audience;
- `verify-export` is network-free and operates only on the sanitized consumer
  bundle. It verifies the export/source-readiness chain, rejects private files,
  recomputes row and token/mask hashes with the locked consumer identities, and
  never claims to have rerun private source oracles;
- all commands print paths and safe counts, never credentials or hidden task
  contents;
- any future lane wrapper remains a thin wrapper around these commands.

The expected operator loop is:

1. run `plan` and `inventory`, export/import the `source_inventory` decision,
   then run `inventory-promote` on that exact approved proposal;
2. export/import `llm_usage_terms` and finish all source mechanical gates. Let
   the capacity planner compute the exact remaining LLM cells and prove the
   explicit call/token/time/spend caps cover the configured draft reserve;
3. run paid `build` until mechanically valid LLM candidates await semantic or
   contamination review;
4. export/import candidate decisions, rerun `build` to reject/backfill, and
   repeat until all count/category cells are filled;
5. export/import the proposed `final_split` decision and run `finalize` to
   render and screen it. Any late rejection stales that decision and returns to
   step 4; an approval-only screen proceeds;
6. export/import `dataset_release`, then rerun `finalize` to write readiness;
7. run producer-side network-free `verify`, create the sanitized export, and
   run `verify-export` on the exact bytes that will be handed to SLIME.

Every loop is resumable and budget-bound. `finalize` never makes an API call.

### Automation Boundary

The V1 pilot is semi-autonomous:

| Work | Default owner |
|---|---|
| Clone verification, inventory, canonicalization, static checks | Automatic |
| Docker starter/reference/sanitizer/test-strength gates | Automatic |
| Contamination fingerprints and review-flag creation | Automatic |
| LLM scheduling, isolated authoring calls, bounded retries | Automatic after paid acknowledgement |
| Rendering, tokenizer/loss-mask checks, constraint solving | Automatic |
| Every admitted LLM-assisted task (at least 21) | Human semantic approval |
| Every contamination or family near-match | Human approval or rejection |
| Source inventory and final split manifest | Human approval |
| Provider usage terms before paid generation | Human approval |
| Final rendered rows, reports, licenses, and export policy | Human `dataset_release` approval |
| Final manifest/readiness reconciliation | Automatic after approvals |

There is no honest completely autonomous `aider-sft-pilot-v1`. A later
profile may replace full review with a calibrated sampling policy, but it must
use a new version and evidence.

The main implementation should be a focused package, not an expansion of the
one-row module into one large file. A suitable layout is:

```text
src/w8_biayn/aider_sft/
  schema.py
  config.py
  inventory.py
  source_exercism.py
  grader_support.py
  scaffold.py
  llm_curator.py
  canonicalize.py
  taxonomy.py
  contamination.py
  oracle.py
  split.py
  renderer.py
  tokenization.py
  review.py
  export.py
  handoff.py
  receipts.py
  pipeline.py
```

Wire the commands through `src/w8_biayn/cli.py`. Reuse or extract proven
helpers from `moonlight_aider_task_*` and `slime_polyglot_cpp.py`; do not fork
the same parser, reference mapper, or Docker grader into incompatible copies.

## Canonical Task Model

Both task-source adapters must emit the same canonical representation before
any split or row is created.

Canonical task packages are private evaluator assets. Recommended directory
shape:

```text
private/canonical-tasks/<task-id>/
  task.json
  docs/
    introduction.md
    instructions.md
    instructions.append.md  # optional track-specific instructions
  workspace/
    starter/
      <editable relative paths>
    reference/
      <solved editable relative paths>
    context/
      <optional model-visible read-only relative paths>
  grader/
    build/
      <CMake and approved build support>
    tests/
      <tests and fixtures>
    shared-support.json  # content-addressed references, never duplicated blobs
    negative-solutions/
      <llm-assisted wrong implementation id>/<editable relative paths>
  provenance/
    source-map.json
    generation.json
  receipts/
    static.json
    starter.json
    reference.json
    tests.json
    mutation.json
    contamination.json
    tokens.json
```

`task.json` must contain at least:

```json
{
  "schema_version": "aider-sft-task-v1",
  "task_id": "stable-content-bound-id",
  "root_task_id": "semantic-root-id",
  "task_family_id": "family-id",
  "title": "Human-readable title",
  "language": "cpp",
  "language_standard": "c++17",
  "source": {
    "kind": "exercism|llm_assisted",
    "repository": "source identity or project-generated",
    "revision": "exact revision or generation run id",
    "relative_path": "source-relative path or null",
    "license": "explicit reviewed value",
    "content_sha256": "sha256"
  },
  "classification": {
    "primary_category": "Text & parsing",
    "tags": ["strings", "validation"],
    "difficulty": "medium"
  },
  "files": {
    "editable": ["example.h", "example.cpp"],
    "model_context": ["example_api.h"],
    "task_specific_tests": ["grader/tests/example_test.cpp"],
    "shared_grader_support": ["exercism-catch-v1"],
    "source_reference_mapping": [
      {
        "source_reference": ".meta/example.h",
        "canonical_editable": "example.h"
      }
    ],
    "context_reference_equivalence": [
      {
        "source_reference": ".meta/exemplar.h",
        "canonical_context": "example_api.h",
        "required_relation": "byte_identical_to_starter"
      }
    ]
  },
  "grader": {
    "adapter": "exercism-cmake-catch-v1",
    "protocol_version": 2,
    "image_id": "sha256:...",
    "cmake_generator": "Unix Makefiles",
    "toolchain": {
      "cxx_path": "<locked-absolute-cxx-path>",
      "cxx_version": "<locked-full-version>",
      "cxx_binary_sha256": "sha256"
    },
    "sandbox": {
      "network": "none",
      "read_only_rootfs": true,
      "run_as_non_root": true,
      "no_new_privileges": true,
      "cap_drop": ["ALL"],
      "mount_policy": "single-rw-scratch-no-host-secrets-v1",
      "seccomp_profile_sha256": "sha256"
    },
    "working_directory": ".",
    "workspace_assembly": {
      "state_tree": "workspace/{starter|reference}",
      "context_tree": "workspace/context",
      "shared_support_manifest": "grader/shared-support.json",
      "file_mappings": [
        {"source": "grader/build/CMakeLists.txt", "destination": "CMakeLists.txt"},
        {"source": "grader/tests/example_test.cpp", "destination": "example_test.cpp"},
        {"shared_bundle": "exercism-catch-v1", "source": "test/catch.hpp", "destination": "test/catch.hpp"},
        {"shared_bundle": "exercism-catch-v1", "source": "test/tests-main.cpp", "destination": "test/tests-main.cpp"}
      ]
    },
    "environment": {"LC_ALL": "C", "TZ": "UTC"},
    "configure_argv": ["cmake", "-S", ".", "-B", "build", "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=<locked-absolute-cxx-path>", "-DEXERCISM_RUN_ALL_TESTS=1"],
    "compile_argv": ["cmake", "--build", "build", "--target", "example"],
    "test_discovery_argv": ["./build/example", "--list-tests"],
    "test_argv": ["./build/example"],
    "test_count_protocol": "catch-v1-list-and-run",
    "configure_timeout_seconds": 120,
    "compile_timeout_seconds": 300,
    "test_timeout_seconds": 180,
    "sanitizer": {
      "profile_id": "clang-asan-ubsan-v1",
      "configure_argv": ["cmake", "-S", ".", "-B", "build-sanitized", "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=<locked-absolute-cxx-path>", "-DEXERCISM_RUN_ALL_TESTS=1", "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"],
      "compile_argv": ["cmake", "--build", "build-sanitized", "--target", "example"],
      "test_discovery_argv": ["./build-sanitized/example", "--list-tests"],
      "test_argv": ["./build-sanitized/example"],
      "environment": {"ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"},
      "timeout_seconds": 300
    },
    "limits": {
      "cpus": 2,
      "memory_mib": 2048,
      "pids": 256,
      "file_size_mib": 64
    }
  },
  "generation": null,
  "distribution_scope": "internal_research"
}
```

The JSON is representative, but every field and role above is normative. The
adapter resolves the placeholder executable target from validated source or
scaffold metadata, while the frozen profile resolves the absolute compiler
identity. No placeholder string may survive canonicalization, task hashing, or
an oracle invocation.

The CMake generator, absolute compiler path, full compiler version, compiler
binary digest, and sandbox policy are global profile inputs and grader
fingerprint inputs; no task may override them. Official Aider C++ parity pins
`Unix Makefiles`, so both normal and sanitizer configurations must pass that
generator explicitly rather than accepting a host-dependent CMake default.

`language_standard` records the dialect actually enforced by the grader; it is
not an aspirational project-wide label. At the pinned Exercism revision all 75
source candidates use C++17, so the V1 source adapter preserves C++17 without
rewriting their CMake files. The LLM scaffold also uses C++17 for parity with
the official Aider/Exercism grader. A future C++20 profile may be added, but V1
must neither claim C++20 nor silently force a source task to a different
dialect.

Every grader adapter must define one collision-checked workspace assembly:

1. create a fresh scratch directory outside the canonical/ready root;
2. copy adapter-owned build support, task-specific tests, and resolved shared
   support into their declared relative paths;
3. overlay exactly one of `workspace/starter` or `workspace/reference`, plus
   model-context files, at their canonical paths;
4. reject any role collision or undeclared file before executing commands;
5. execute all argv relative to `working_directory` with only the declared
   environment, toolchain, sandbox policy, and resource limits.

Commands, environment entries, target names, and workspace mappings are
adapter-produced from checked-in templates or validated pinned source—not
accepted from LLM text or interpolated through a shell. The runner must enforce
the fingerprinted sandbox contract, not merely record it in task metadata.

At the pinned Exercism revision all 75 source CMake files set
`CXX_STANDARD 17`, do not register CTest tests, and attach the test executable
to an `ALL` custom target. The source adapter must therefore configure with
`EXERCISM_RUN_ALL_TESTS=1`, compile only the exercise executable target, run
that executable separately, and derive a positive test count through the
pinned Catch protocol. It must not use CTest or treat the default `ALL` build
as a compile-only phase.

Shared framework files are content-addressed grader support, not task-specific
semantic evidence and not 75 duplicated task files. In the pinned source,
`test/catch.hpp` is 656,882 bytes with SHA-256
`e11ac6b2994c046909c4a7c730a6a536e8f9563172563026878b7baadecdf553` and
`test/tests-main.cpp` has SHA-256
`5847fda35c1320d94f8d088aaf34229d689f66f1da235f885cbb28c8f17e4260`.
The implementation must reconstruct and verify the bundle from the pinned
checkout rather than trusting these prose values.

The sanitizer profile is blocking and uses a separate build directory. Its
exact compiler/linker flags, environment, argv, toolchain, timeout, and pass
criteria belong in the config lock. A sanitizer pass requires exit zero, no
ASan/UBSan finding, and the same full reference test set to pass. All normal
and sanitizer command inputs are part of the oracle fingerprint.

For an LLM-assisted root, `generation` must record safe provenance: provider,
exact model identity, prompt-template hashes, request/response content hashes,
decoding parameters, token usage, attempt/revision counts, and timestamps. It
must not contain an API key, authorization header, private chain of thought, or
unbounded provider response envelope.

Private generation evidence retains the exact redacted structured request
(messages, response schema, and settings) and the normalized structured output
needed to reproduce materialization. Provider headers, credentials, hidden
reasoning fields, and unrelated envelope data are discarded. Hashes alone are
not enough to audit what task-authoring material was sent.

Normalized LLM blueprints and materialized revisions required for resume live
under `private/candidates/<candidate-id>/`. The ready bundle retains the
accepted normalized blueprint, task artifacts, request/response hashes, and
bounded diagnostics. It does not retain private reasoning or an unbounded raw
provider envelope. Rejected-candidate content may be retained in the ignored
working root for deduplication, but public manifests expose only safe hashes
and reason codes.

### Identity Rules

- IDs are normalized lowercase slugs plus a content-bound suffix when needed.
- Relative paths must be POSIX, nonempty, non-absolute, traversal-free, and
  free of symlinks, hardlinks, or special files.
- V1 accepts nested POSIX relative paths. A rendered filename line contains the
  exact relative path with no Markdown decoration; “bare filename” never means
  basename-only.
- Text inputs must be valid UTF-8 without BOM, normalized to LF, and end in
  exactly one final newline. V1 rejects every model-visible fenced file body—
  editable starter/reference content and read-only model context—when it
  contains a line matching the ASCII regex `^[ ]{0,3}\x60{3,}` because the
  pinned renderer cannot represent it unambiguously. Tabs and four or more
  leading spaces do not match this particular gate.
- Canonical regular files use mode `0644`; only explicitly approved grader
  entrypoints may use `0755`. Ownership and timestamps do not enter content
  hashes.
- Content hashes use domain-separated canonical JSON plus sorted
  `path + NUL + byte_length + NUL + bytes` records.
- The source task ID, family ID, and content hash are separate fields.
- A changed source revision, grader, reference mapping, renderer, or tokenizer
  changes the relevant fingerprint and invalidates cached downstream evidence.
- Task family is assigned before splitting.
- Canonical task serialization and JSONL ordering are deterministic.

## Source-Backed Exercism Adapter

The source adapter must:

1. read only the pinned official Exercism C++ checkout;
2. load the checked-in candidate manifest and require exactly 75 unique
   non-benchmark entries from Appendix A before admission;
3. reject every denylisted ID before copying files;
4. discover `.docs/introduction.md`, `.docs/instructions.md`, optional
   `.docs/instructions.append.md`, `.meta/config.json`, declared solution,
   editor, test, example/exemplar files, `CMakeLists.txt`, and support assets;
5. map `.meta/config.json` `files.solution` entries to canonical editable
   files and `files.test` entries to task-specific private tests;
6. map `files.editor` entries that are not also solution files to model-visible
   read-only context, never silently to the editable set;
7. map `.meta/example.*` or `.meta/exemplar.*` files to solution/context roles
   by declared metadata, filename/extension, and validated content—not list
   position;
8. require an exemplar corresponding to a context-only editor file to be
   byte-identical to the starter/context copy. If it differs, reject
   `unsupported_editor_reference_change` rather than hiding a required edit;
9. preserve task-specific grader-relative structure while replacing repeated
   framework files with exact content-addressed shared-support references;
10. derive the C++17 compile target, test executable, discovery protocol,
    normal argv, and sanitizer argv from the checked-in Exercism adapter;
11. capture source revision, source-relative paths, file hashes, and license
   provenance;
12. reject missing, ambiguous, unsafe, duplicate, or unsupported file mappings;
13. produce a canonical candidate without rendering an SFT row yet.

Existing source tests should be reused and executed. They do not need to be
rewritten merely because tests will not appear in the SFT row.

The selected Exercism snapshot is MIT-licensed. Preserve its license and
attribution in the private source package and record SPDX `MIT` on every
source-backed task. Do not infer that license for LLM-assisted content.

When an official example omits an editable file because that starter file is
already correct, the canonical solved state uses the unchanged starter for
that file. The assistant target still contains the complete solved state for
every editable file. Mapping by list position alone is insufficient when file
extensions or metadata provide a safer explicit mapping.

The frozen `concept/vehicle-purchase` root exercises the `files.editor` rule:
`vehicle_purchase.cpp` is editable, `vehicle_purchase.h` is read-only model
context, and `.meta/exemplar.h` must equal the starter header. This task is a
required adapter regression fixture, not a reason to discard the source root.

## LLM-Assisted Authoring Adapter

### Boundary

The curator writes task artifacts. It never answers an admitted task as the
target GLM model, never sees target-model failures, and never creates repair
training rows.

The authoring model must not receive benchmark instructions, code, tests,
solutions, filenames, or distinctive benchmark edge cases. It may receive:

- a primary category and generic skill tags;
- desired difficulty and file/API shape;
- the profile's pinned C++17 language/scaffold constraints;
- a structured task blueprint schema;
- a list of prohibited task IDs without their contents.

Contamination checking happens in a separate offline stage that may inspect
the held-out corpus. Do not feed that corpus back into the author.

LLM-assisted pilot artifacts default to
`distribution_scope = "internal_research"`. Readiness requires a human
decision that the chosen provider terms permit the intended training use.
Public redistribution is a separate release decision and is not implied by
dataset readiness. No license is inferred merely because an API produced text.

### Repo-Owned Generated-Task Scaffold

LLM-assisted V1 tasks use the checked-in
`aider-sft-cmake-catch-v1` scaffold. The scaffold—not an LLM—creates CMake,
the test entrypoint, normal/sanitizer commands, target names, and shared-support
references. Its template bytes, allowed Catch API, toolchain, C++17 dialect,
and scaffold version are config-lock inputs.

The task author may emit docs, starter/reference C++, and declarative file/API
metadata. The stateless test author may emit only task-specific C++ tests that
conform to the approved Catch surface. Any generated CMake, shell, command
argv, dependency declaration, downloader, or alternative test runner is a
blocking schema rejection. This keeps API creativity in the task while making
execution reproducible and prevents generated build metadata from becoming a
second unreviewed program.

### Authoring Stages

Use separate, structured stages rather than one unconstrained prompt:

1. **Scheduler** selects a category/split/difficulty/API/file-shape deficit.
2. **Planner** emits a JSON blueprint containing behavior, public API,
   constraints, edge cases, and a test plan.
3. **Task author** emits docs, starter files, reference files, and declarative
   file/API metadata from the approved blueprint; it emits no build program.
4. **Test author** runs in a new stateless request and emits only task-specific
   tests for the repo-owned scaffold from the approved blueprint and public API,
   without receiving the reference implementation, prior task-author
   conversation, or benchmark material.
5. **Adversarial author/mutator** emits at least three compileable wrong
   implementations from the blueprint and starter without seeing tests or the
   reference.
6. **Static auditor** checks schema, paths, forbidden content, file limits,
   C++17/scaffold policy, and docs/API consistency.
7. **Deterministic oracle** compiles/runs starter, reference, sanitizers, and
   negative solutions.
8. **Review exporter** creates a task card. A human semantic reviewer checks
   ambiguity, originality, licensing scope, and blueprint/docs/API/test-plan
   alignment; no LLM stage may self-approve admission.
9. A failed draft may enter a bounded revision only through stage-specific
   routing:
   - blueprint/schema ambiguity returns to a fresh planner request;
   - docs, starter, API, reference-compilation, or declarative-file errors
     return to the task author with only its own artifacts and bounded safe
     diagnostics;
   - test compilation or weak negative-solution coverage returns to a fresh,
     stateless test-author request with the blueprint, public API, and bounded
     test-stage diagnostics, but never the reference or task-author history;
   - negative-implementation compilation errors return only to the adversarial
     author;
   - a reference/test semantic disagreement that cannot be mechanically
     attributed is rejected or sent to human review, not guessed by a model;
   - contamination, benchmark-similarity, and family-leak findings are never
     fed back to an author. Reject the candidate and schedule a fresh concept
     without exposing held-out evidence.

All revision prompts omit test source, hidden expected values, benchmark
content, reference diffs, and diagnostics owned by another authoring stage.
Revision artifacts never become SFT rows.

Mechanical admission and classification of the entire frozen source inventory
must complete before the first paid authoring request. The scheduler then
derives the exact missing total/category/split cells and writes a capacity
report with `required_llm_admissions`; this is the number of additional,
independent LLM roots the solver must be able to admit, not merely the nominal
21-root minimum.

The config must declare a candidate-capacity reserve of at least three times
`required_llm_admissions` and prove that every per-stage call/token limit and
the aggregate spend/time budget can service that capacity. V1 deliberately has
no fixed 64-candidate assumption. A smaller explicit cap is a blocking
`llm_capacity_insufficient` result, not permission to weaken quotas. The pilot
still defaults to at most three material revisions total per candidate, four
concurrent requests, and three retries for transient transport failures. After
the revision limit, reject and request a fresh candidate. The config must bind
per-stage and aggregate limits for:

- total candidates;
- required admissions and candidate-capacity reserve multiplier;
- calls per stage and per candidate;
- concurrency and rate limits;
- request/response token budgets;
- retries for transient transport failures;
- maximum spend or provider-reported usage;
- total wall-clock time.

There is no implicit spend default. `build` must fail before its first paid
request unless explicit total call, input-token, output-token, wall-time, and
currency spend caps are present, the paid acknowledgement is set, the approved
`llm_usage_terms` decision matches, and the capacity report proves the locked
quota can be filled with its declared reserve.

Use environment variables or a scoped secret source for credentials. Never
write credentials to config, manifests, logs, task prompts, or W&B.

### Required Blueprint Fields

At minimum:

```text
schema_version
title
proposed_slug
primary_category
tags
difficulty
learning_objectives
behavioral_contract
public_api
editable_files
constraints
edge_cases
test_plan
non_goals
```

The materialized task must contain complete docs, starter, reference, tests,
and a deterministic build recipe. A prose-only idea is not a candidate root.

## Admission Pipeline

Candidate admission and dataset release are separate state machines. A
candidate must not carry dataset-level split/release states, and final-split
review must not retroactively redefine whether its task content passed
admission.

Candidate lifecycle:

```text
discovered
  -> canonicalized
  -> static_valid
  -> starter_checked
  -> reference_checked
  -> test_strength_checked
  -> contamination_screened
  -> render_candidate
  -> whole_format_checked
  -> token_checked
  -> awaiting_task_review (when llm_task_semantics or a contamination flag applies)
  -> candidate_approved
  -> admitted_pool
```

Dataset lifecycle:

```text
inventory_proposed
  -> awaiting_inventory_review
  -> inventory_frozen
  -> pool_filling
  -> split_proposed
  -> awaiting_split_review
  -> split_frozen
  -> final_rendered
  -> final_screened
  -> awaiting_release_review
  -> release_approved
  -> bundle_reconciled
  -> ready
```

Every transition writes a content-bound receipt. Stage outcomes are distinct:

- `retryable_error` for infrastructure, transport, or rate-limit failures;
- `awaiting_task_review` for a mechanically valid candidate with an open
  task-level human scope;
- `awaiting_inventory_review`, `awaiting_split_review`, and
  `awaiting_release_review` for their respective dataset-level scopes;
- `rejected_content` for a terminal content/admission failure;
- `deferred_profile` for a valid frozen source candidate intentionally left
  outside this profile to satisfy an approved category/split cell;
- `admitted` only after all mechanical and task-level scopes for that candidate
  pass;
- `ready` only after the frozen admitted pool, final split, rendered artifacts,
  complete review set, and bundle reconciliation all pass.

`source_inventory` is a prerequisite to source candidate processing;
`llm_usage_terms` is a prerequisite to paid LLM calls; `llm_task_semantics` and
`contamination_flag` are candidate-level; `final_split` and `dataset_release`
are dataset-level. An admitted candidate can still be absent from the pilot
only through an explicit `deferred_profile` record before the split is frozen.
Final-split or release approval never substitutes for task admission.

`final_split` approves placement against the admitted-pool fingerprint. After
that approval, the pipeline renders exact rows, reruns contamination over the
final model-visible bytes, validates whole-format/token evidence, and builds the
release summaries and sanitized-export preview. A newly found exact overlap,
terminal render/token failure, or task-content rejection invalidates the frozen
split and release package, removes the affected candidate from selection, and
returns the dataset to `pool_filling` for quota-preserving backfill. It must not
leave a frozen split referring to an inadmissible row.

A `dataset_release` rejection concerning only a release summary, license
artifact, or export-policy presentation stales that decision and returns to
`final_screened` to regenerate the package and await a new exact approval
without changing an otherwise valid split. If its correction changes a task,
row, family/category label, or selected set, the split is invalidated and the
full backfill path applies. Near-match flags may proceed only after their exact
`contamination_flag` decisions are imported. `dataset_release` then approves
the exact final rows, evidence summaries, license artifacts, and export policy
before bundle reconciliation can write readiness.

Budget exhaustion is a run-level `incomplete` condition, not a content
rejection. Rejected and profile-deferred candidates remain auditable but never
enter canonical admitted roots or JSONL. No stage may consume a stale upstream
receipt.

### Static Gates

Reject a task when any of the following is true:

- required docs, editable files, reference files, tests, or build recipe are
  missing;
- task/reference mapping is ambiguous;
- paths are absolute, traversing, duplicated, symlinked, or special files;
- files exceed configured per-file or per-task byte limits;
- docs and declared public API disagree;
- tests or reference material appear in starter/model-visible content;
- canonical roles collide or a shared-support reference is undeclared/stale;
- unsupported external/network dependencies are required;
- content is not compatible with its declared language standard, toolchain,
  and adapter/scaffold;
- an LLM-assisted artifact supplies build scripts, commands, or dependencies;
- source/license provenance is missing;
- the task ID or family is already present.

Pilot static limits are frozen profile fields and default to:

| Limit | V1 value |
|---|---:|
| Editable regular files | 8 |
| Model-visible context regular files | 16 |
| Total task-local regular files | 128 |
| Bytes per editable/model-context file | 256 KiB |
| Bytes per task-specific test/build file | 256 KiB |
| Total model-visible bytes | 512 KiB |
| Total task-local canonical bytes | 4 MiB |
| Bytes per shared grader-support file | 1 MiB |
| Total bytes per shared grader-support bundle | 4 MiB |
| Persisted stdout/stderr tail per command | 64 KiB |

Task-local counts and bytes exclude content-addressed shared support, which is
validated once, stored once, and referenced by digest. Shared support is still
subject to its own limits and is included in every consuming oracle
fingerprint. This role split intentionally admits the pinned 656,882-byte
`catch.hpp` without weakening limits on model-visible or task-authored files.

Changing a limit requires a new config lock; changing the pilot defaults
requires a new dataset profile. Hardlinks; lines matching the exact
Identity Rules fence-line regex in any model-visible file body; and any
dependency that needs grader-time network access are blocking rejections.

### Executable Oracle Gates

Tests are mandatory even though the trainer does not execute them. They prove
that the assistant label is usable before it enters SFT.

They are dataset-quality gates, not training-time inputs: compilation alone
cannot prove behavior, a plausible reference can still be semantically wrong,
and generated tests can be too weak to distinguish common mistakes. The
trainer receives only the verified prompt/answer row; it does not run or see
the tests. Keeping the grader privately also makes validation/internal-test
roots usable later without changing the training contract.

For every candidate:

1. materialize a clean starter workspace through the declared collision-checked
   assembly map;
2. configure the normal build in the pinned, network-disabled Docker image and
   exact sandbox policy, passing the locked `Unix Makefiles` generator and
   absolute compiler path, then compile only the declared exercise/scaffold
   executable target;
3. if the starter compiles, run the pinned discovery command and require a
   positive test count, then run the test executable and require at least one
   failure. A discovery/parser failure is a harness failure, not an expected
   starter failure;
4. if the starter does not compile, record expected incompleteness without
   claiming test execution; reject only a starter that compiles and passes all
   tests or a starter whose harness itself is invalid;
5. materialize the complete canonical reference in a separate fresh workspace
   through the same role map;
6. configure and compile only the declared reference executable target;
7. run test discovery, require a positive number of tests, then run the full
   reference test executable and require every test to pass within bounds. The
   reference discovery result is the authoritative positive-test count;
8. configure a third fresh sanitizer build directory with the exact locked
   sanitizer profile, generator, compiler, and sandbox; compile the same target;
   run its declared discovery argv; and run the same full reference test set.
   Require exit zero, no sanitizer finding, a positive discovered count, and a
   test count equal to the normal reference count;
9. record the assembly manifest, working directory, exact argv/environment,
   exit status, timeout, discovered/tested/pass/fail counts, bounded stdout and
   stderr with full-stream hashes/sizes, CMake generator, compiler
   path/version/binary hash, enforced sandbox identity, resource limits, tool
   identities, and every input/output fingerprint.

For the Exercism adapter, neither normal nor sanitizer admission may invoke the
default `ALL` target or CTest. Compile-target success and test-executable
success must remain separately observable. The adapter must regression-test
that its split phases are behaviorally equivalent to the pinned official
Aider `cpp-test.sh` configuration—including its `Unix Makefiles` generator—and
full test run.

Prefer extracting and reusing the fingerprinted Docker protocol in
`slime_polyglot_cpp.py`. The current local `moonlight_aider_task_eval.py`
grader is useful for unit fixtures but is not sufficient by itself for
dataset-level admission because it is not image-bound and does not prove all
dataset invariants.

For LLM-assisted tasks, test strength is blocking:

- define at least three meaningful, compileable wrong implementations tied to
  stated edge cases;
- require every declared wrong implementation to fail at least one test;
- optionally run deterministic mutations and record compiled/killed counts;
- reject tests that only confirm the reference's happy path or cannot
  distinguish the known wrong behaviors.

For pinned official source tasks, official tests plus the passing reference are
the primary oracle. Mutation checks may initially be diagnostic, but zero-test,
reference-failure, leakage, and stale-grader gates remain blocking.

### Whole-Format Target Gates

After the executable oracle passes but before admission, render a provisional
assistant target and require:

- only complete Aider `whole` file listings;
- editable files sorted lexicographically by exact canonical POSIX relative
  path;
- the exact editable relative path on its own line immediately before an
  opening ```` ```cpp ```` fence;
- exactly one listing for every editable file;
- no missing, duplicate, extra, absolute, or traversing filename;
- no diff, patch, explanatory prose, tests, metadata, or reference filenames;
- acceptance by the pinned real Aider `whole` parser;
- successful application to a clean starter workspace;
- byte-for-byte equality between the applied editable state and the already
  verified canonical reference state;
- a same-grader pass after application.

The repo's stricter target policy allows no prose even though Aider itself can
accept explanatory prose. This keeps supervision deterministic and lowers
format risk.

## Contamination, Duplication, And Family Isolation

Run contamination before splitting and again over the final rendered bundle.
Comparison is role-aware. Before hashing, every file is classified as:

- semantic task content: docs, editable starter/reference files, public API,
  task-specific tests, and distinctive fixtures;
- shared grader support: exact content-addressed framework files such as
  `catch.hpp` and `tests-main.cpp`;
- adapter scaffold: repo-generated CMake/test boilerplate;
- generic source boilerplate: common licenses, includes, comments, and track
  instructions identified by the pinned normalizer.

Only semantic task content can trigger automatic content-overlap rejection.
Shared support and adapter scaffolds are verified against their allowlisted
hashes and excluded from task-similarity features. Generic boilerplate is
removed or down-weighted by config-locked, regression-tested normalizers. An
unknown shared-looking file is not silently ignored; it becomes a blocking
normalizer/review error.

Then use layered checks:

1. exact task ID/slug/path denylist;
2. normalized docs, starter, reference, task-specific test, and distinctive
   fixture hashes;
3. normalized text/token n-gram similarity;
4. normalized C++ token/AST similarity;
5. API signature and distinctive edge-case comparison;
6. semantic similarity review for flagged pairs.

Exact semantic-task or identity matches are automatic rejection. Exact shared
grader/support hashes are expected and are never evidence of task overlap by
themselves. Near semantic matches are blocking review flags; the pilot cannot
auto-admit an unresolved flag. Persist only bounded comparison evidence and
hashes where held-out content should remain private.

The pinned 26-root benchmark manifest must first reconcile exactly with the
Polyglot checkout. V1 then applies these deterministic review-flag defaults:

- normalized documentation token 5-gram Jaccard similarity `>= 0.50`;
- normalized C++ token 5-gram Jaccard similarity `>= 0.70`;
- an exact normalized public-API plus distinctive-edge-case fingerprint;
- any configured AST/semantic signal whose pinned implementation crosses its
  lock-recorded threshold.

Threshold hits are review flags, never automatic semantic clearance. Exact
semantic-content/identity matches remain automatic rejection; allowlisted
shared-support/scaffold matches remain excluded. Thresholds,
normalizers, stop-word rules, tokenizer/parser identities, and optional local
embedding model hashes belong in `config.lock.json`. Held-out instructions,
tests, references, or derived text must never be sent to an external API.

Deduplicate across:

- the 26 benchmark roots;
- all 75 source candidates;
- all accepted and rejected LLM drafts;
- train, validation, and internal test;
- future imported sources when this pipeline scales.

Assign `task_family_id` before splitting. All translations, ports, renamed
copies, shared blueprints, and generated revisions of one semantic task stay in
one family and one split. A rejected revision cannot later reappear under a new
ID without its lineage.

## Split Construction

Split only admitted root tasks, never rendered rows. Use a frozen seed and a
deterministic constraint solver or stable stratified algorithm.

Blocking constraints:

- exactly 72 train, 12 validation, and 12 internal-test roots for the pilot;
- exactly 12 train, 2 validation, and 2 internal-test roots per primary
  category;
- no family crosses splits;
- at least 21 LLM-assisted roots overall, initially targeting 15 train, 3
  validation, and 3 internal test;
- at least one LLM-assisted root in every split, at least two in every primary
  category overall, and at least one training LLM root in every category;
- source provenance and difficulty are reported and kept reasonably balanced;
- the 26 benchmark roots occur in no split;
- split manifests contain sorted IDs, family IDs, categories, provenance, and
  task fingerprints.

Source-to-cell assignments are frozen in the checked-in source manifest. LLM
category and difficulty labels require human confirmation before the solver
uses them. If constraints cannot be satisfied, generate/backfill the missing
cell. If the configured budget ends first, readiness fails. Do not move a
related family across splits or relax any blocking target.

## SFT Row Contract

### Prompt Representation

V1 uses the compact self-contained representation established by
`docs/single_sample_for_sft.md`:

```text
user: format contract + introduction + instructions + complete starter files
assistant: complete solved editable-file listings
```

Use exactly one user turn and one assistant turn. This avoids accidentally
training on Aider's canned assistant example or acknowledgement turns. If a
future exact-Aider multi-turn profile is added, canned assistant turns must use
`step_loss_mask: 0`, the desired final answer must use `step_loss_mask: 1`, and
the behavior must be verified against the pinned SLIME mask generator.

The user message includes:

- the strict Aider `whole` format instructions;
- `.docs/introduction.md` when present;
- `.docs/instructions.md`;
- `.docs/instructions.append.md` when present, after the main instructions;
- every editable starter filename and its complete pre-edit content;
- every declared model-context relative path and its complete read-only
  content, clearly separated from editable files;
- the API/file-name preservation reminder.

The user message excludes:

- all tests and fixtures;
- `.docs/hints.md`, `.docs/after.md`, templates, and other post-solution or
  non-prompt documentation;
- `.meta/config.json`, `.meta/tests.toml`, and equivalent metadata;
- reference/example files or their paths;
- hidden grader commands and receipts;
- benchmark addenda that disclose held-out task identity;
- curator prompts, critiques, and failed drafts.

The compact renderer is byte-deterministic. Its user-message section order is
format contract, introduction, main instructions, appended instructions,
editable-starter heading and blocks, read-only-context heading and blocks, then
the API/file-name reminder. It sorts editable files and model-context files
independently by exact canonical POSIX relative path; an empty context section
is omitted according to the locked golden fixture.

In both prompt file sections and the assistant target, each file is represented
as the exact relative path on its own line, an opening ```` ```cpp ```` fence,
the complete normalized file bytes, and a closing fence, with one blank line
between file blocks. Every such body has already passed the common fence-line
safety gate. The target has no leading or trailing prose and ends in one
newline. Renderer golden tests must bind the exact prose, section order,
separators, fence language, path spelling, empty-section behavior, and newline
policy; filenames may not be replaced by basenames or display labels.

### JSONL Shape

Each training row must be one stable JSON object on one line:

```json
{
  "schema_version": "aider-sft-row-v1",
  "task_id": "task-id",
  "label": "task-id",
  "messages": [
    {
      "role": "user",
      "content": "<compact prompt>",
      "step_loss_mask": 0
    },
    {
      "role": "assistant",
      "content": "<complete whole-file listings>",
      "step_loss_mask": 1
    }
  ],
  "metadata": {
    "schema_version": "aider-sft-row-v1",
    "purpose": "primary-aider-sft-dataset",
    "format": "aider-whole",
    "subset": "train",
    "task_id": "task-id",
    "root_task_id": "root-id",
    "task_family_id": "family-id",
    "source_kind": "exercism|llm_assisted",
    "source_revision": "exact-revision-or-generation-run",
    "language_standard": "c++17",
    "tokenizer_repository": "zai-org/GLM-4.7-Flash",
    "tokenizer_revision": "7dd20894a642a0aa287e9827cb1a1f7f91386b67",
    "chat_template_sha256": "sha256",
    "chat_template_policy": "final_answer_only_thinking_disabled",
    "chat_template_kwargs_sha256": "sha256",
    "sft_mask_adapter": "w8-aider-sft-mask-v1",
    "loss_mask_type": "qwen",
    "sequence_length": 4096,
    "rendered_token_sha256": "sha256",
    "loss_mask_sha256": "sha256",
    "response_length": 0,
    "response_loss_mask_sha256": "sha256",
    "token_counts": {
      "total": 0,
      "prompt": 0,
      "assistant": 0,
      "loss_bearing": 0
    },
    "primary_category": "Text & parsing",
    "tags": ["strings", "validation"],
    "difficulty": "medium",
    "editable_files": ["task.h", "task.cpp"],
    "context_files": [],
    "oracle_fingerprint": "sha256",
    "renderer_version": "aider-whole-compact-v1"
  }
}
```

The future primary-dataset handoff to the GLM SFT lane must consume this with:

```text
--rollout-function-path w8_biayn.aider_sft.handoff.generate_sft_rollout
--prompt-data <dataset>/sft/train.jsonl
--input-key messages
--metadata-key metadata
--loss-type sft_loss
--apply-chat-template-kwargs '{"enable_thinking":false}'
--loss-mask-type qwen
```

The raw `messages` list must reach the rollout function. The dataset-loader
`--apply-chat-template` flag is forbidden because pinned SLIME converts the
list to a string before its SFT rollout/mask path can use message boundaries.
The thin repo-owned rollout adapter forwards the exact locked kwargs to every
tokenizer call and invokes the explicit `qwen` mask generator. It adapts data;
it is not a custom trainer.

Only assistant target tokens may contribute to loss. The implementation must
run the pinned SLIME loss-mask generator in validation and prove each row has a
nonzero assistant loss region and a zero-loss user region.

### Token Admission

Tokenize the exact raw messages by invoking `w8-aider-sft-mask-v1` in validation
mode with the exact GLM tokenizer and chat template used by the target lane.
The adapter must preserve message boundaries and forward the config-locked
`apply_chat_template` kwargs on every tokenizer call. Its returned token IDs
and loss mask are the canonical training evidence; a separately templated
string or a stock path that drops those kwargs is not equivalent. The active
lane currently defaults to a
4096-token sequence length; the run lock, not this prose, is authoritative.
The validator must prove that the assistant content is only the expected whole
file blocks, that no implicit trainable reasoning/thinking region is inserted,
and that the exact rendered-token SHA-256 is stable across build, verification,
export, and lane preflight. If the installed tokenizer does not support the
locked thinking-policy invocation, the profile is not frozen; silently dropping
the kwarg or accepting a different template is forbidden.

Reject rather than truncate when:

- the fully templated user+assistant sequence exceeds the configured maximum;
- the assistant loss region is empty;
- tokenizer/chat-template rendering fails;
- the rendered sequence identity differs between build and verification.

Persist one deterministic `sft/token-records.jsonl` record per training row
with its task/row hash, rendered-token hash, full-length loss-mask hash aligned
one-to-one with the rendered tokens, total/prompt/assistant/loss-bearing counts,
adapter identity, exact template-kwargs hash, tokenizer/template identity, and
sequence limit. It also records SLIME's `response_length` (from the first loss
value of one through sequence end) and a hash of the exact response-suffix mask
assigned to the training sample. Both values must be derivable from the full
mask and must match the repo adapter's returned `Sample`. Copy the row-specific
values into row metadata, bind the records file in readiness/export manifests,
and emit min/median/p95/max summaries. The consumer recomputes this evidence; it
must not merely trust copied hashes. Silent truncation would corrupt labels and
is forbidden.

## GLM/SLIME Consumer Handoff

Dataset readiness still ends before training, but the implementation must make
mis-consumption difficult. The primary bundle is not admitted to the GLM lane
merely because a file named `manifest.json` exists.

Before the first SFT process starts, the thin lane handoff must:

1. while it still has the private ready root, the producer runs network-free
   `w8-biayn data aider-sft verify` and requires `readiness.json.status ==
   "ready"` plus exact full-manifest/oracle reconciliation;
2. the producer uses `aider-sft export --audience slime-sft`; its export
   manifest binds source readiness, training JSONL, token records, and the
   redacted consumer lock;
3. from only that sanitized bundle, the consumer runs network-free
   `w8-biayn data aider-sft verify-export` and requires exact reconciliation;
4. set `SLIME_CPP_DATA_DIR` to that verified consumer bundle and
   `SLIME_CPP_AUTO_PREPARE_DATA=0`; it must not run PIE `prepare_data.sh` or
   silently rebuild another dataset;
5. require the local GLM checkpoint/tokenizer to match repository
   `zai-org/GLM-4.7-Flash` at revision
   `7dd20894a642a0aa287e9827cb1a1f7f91386b67`, or match an explicitly locked
   set of equivalent local file hashes. Any Hugging Face download must pass
   that exact `revision=` to `snapshot_download`;
6. compare the checkpoint/tokenizer/template identity, exact chat-template
   kwargs, `w8-aider-sft-mask-v1` adapter identity, `qwen` loss-mask type, and
   sequence length with the consumer lock;
7. invoke SLIME through the locked repo rollout function with raw `messages`,
   explicit metadata/input keys, `sft_loss`, exact template kwargs, explicit
   `qwen` loss-mask type, and the locked sequence length;
8. reject a launch if dataset-loader `--apply-chat-template` is present or the
   rollout function does not match the locked adapter;
9. rerun the zero-user/nonzero-assistant fixture and recompute every exported
   row's token/mask hashes and counts before accepting the first training
   batch.

At design time, `examples/slime/glm47_cpp_perf/glm47_cpp_perf.sh` checks only
for `manifest.json` and its checkpoint download does not pass a model revision.
Although that stage already passes raw messages, pinned SLIME's stock SFT
mask/rollout path does not accept and forward the locked chat-template kwargs.
All three gaps are explicitly insufficient for this handoff and must be fixed
by the thin preflight/adapter during implementation. This remains a data
consumer adaptation around SLIME, not a custom trainer and not part of dataset
readiness.

## Validation And Internal-Test Artifacts

Validation and internal-test roots remain complete canonical task packages
with hidden references and graders. They are not added to SFT training JSONL.

The bundle must also emit prompt-only JSONL for tooling and inspection:

```json
{
  "task_id": "eval-opaque-content-id",
  "label": "eval-opaque-content-id",
  "messages": [{"role": "user", "content": "<compact prompt>"}],
  "metadata": {
    "schema_version": "aider-sft-eval-prompt-v1",
    "subset": "validation",
    "task_id": "eval-opaque-content-id",
    "primary_category": "Text & parsing",
    "difficulty": "medium"
  }
}
```

No assistant/reference content appears in `eval/validation.jsonl` or
`eval/test.jsonl`. Model-facing rows necessarily include the declared editable
and context POSIX relative paths, but expose no private host path, canonical
package path, evaluator path, grader command, oracle fingerprint, or
hidden-asset filename. A private
fingerprint-bound evaluator index maps each stable pseudonymous evaluation ID
to its canonical package and internal task ID. Evaluation IDs must not contain
the source repository slug or title.
These files do not imply that a model evaluation runner is part of V1.

## Output Bundle

Required layout:

```text
.w8-biayn/data/aider-sft-pilot-v1.state/
  run-state.json
  dataset.lock
  journals/
  logs/
.w8-biayn/data/aider-sft-pilot-v1/
  DATASET_CARD.md
  NOTICE
  licenses.json
  config.lock.json
  manifest.json
  source-manifest.json
  benchmark-denylist.json
  split-manifest.json
  readiness.json
  sft/
    train.jsonl
  eval/
    token-records.jsonl
    validation.jsonl
    test.jsonl
  reports/
    category-summary.json
    difficulty-summary.json
    token-summary.json
    capacity-summary.json
    release-summary.json
    license-summary.json
  private/
    evaluator-index.json
    grader-support/
      manifest.json
      <content-addressed support bundles>
    canonical-tasks/
      <96 admitted task directories>
    candidates/
      <accepted and rejected materialized candidates>
    admission/
      records.jsonl
      summary.json
    generation/
      records.jsonl
      summary.json
    rejected/
      records.jsonl
    review/
      review-manifest.json
      imported-decisions.jsonl
      export/
        source-inventory/
        llm-usage-terms/
        task-cards/
        contamination-flags/
        final-split/
        dataset-release/
```

`manifest.json` binds every file by relative path, byte size, SHA-256, row
count, schema version, and role. It also records source/grader/tokenizer/
renderer identities and category/provenance/split counts.

`DATASET_CARD.md`, `NOTICE`, and `licenses.json` are deterministic release
artifacts. They state the internal-research scope, source provenance and MIT
attribution, LLM provider/model and reviewed usage-terms decision, excluded
benchmark, task/row counts, known limitations, and the fact that tests and
references are private admission evidence. No generated/API text receives an
inferred open-source license.

The `slime-sft` export contains only those three documents, a redacted consumer
lock, source `readiness.json`, `sft/train.jsonl`, `sft/token-records.jsonl`, and
an export manifest binding the source manifest/readiness, both SFT files, and
consumer lock. `verify-export` recomputes row/token/mask evidence from those
files and the locked local tokenizer without access to private oracle assets.
It excludes canonical tasks, candidate drafts, tests, references, evaluator
indexes, review comments, and eval ID mappings. A future public export requires
a separately reviewed distribution profile; V1 must fail closed rather than
reinterpret `internal_research`.

To avoid recursive or stale claims, the manifest content set includes every
immutable final artifact except `manifest.json` itself and `readiness.json`;
it declares those two non-recursive exclusions explicitly. Mutable run state,
locks, journals, and working logs live only in the `.state/` sibling and can
never enter or modify the ready root. `readiness.json` is written last and
binds the manifest SHA-256 plus the config, source, benchmark, split, review,
token-record, and admission-ledger fingerprints. Operational state never
serves as release evidence.

At readiness, `private/admission/records.jsonl` contains one terminal record
for every candidate, including rejected and profile-deferred candidates.
During construction, per-candidate append-only journals are the source of
truth and the global ledger is a deterministic stable-sorted aggregation.
`private/rejected/records.jsonl` may be a deterministic filtered view but must
reconcile exactly with the admission ledger.

Task cards include source/provenance, category/tags/difficulty, docs/API
summary, editable/test file lists, test counts, oracle result, mutation result,
token counts, contamination result, hashes, and review status. They must not
accidentally place hidden tests or references into prompt-preview fields.
For `llm_task_semantics`, the private review package must also give the reviewer
explicit access to the normalized blueprint, docs, starter, reference, tests,
test plan, and negative-solution results; a summary-only card is insufficient
for approval.

## Readiness Receipt

The pipeline writes `readiness.json` only after recomputing the complete bundle
from disk. This representative receipt shows the no-source-rejection 75/21
composition; an actual ready run records its observed provenance counts, which
must sum to 96 with `llm_assisted >= 21`:

```json
{
  "kind": "primary-aider-sft-dataset-readiness",
  "schema_version": 2,
  "dataset_id": "aider-sft-pilot-v1-<content-id>",
  "dataset_profile": "aider-sft-pilot-v1",
  "status": "ready",
  "bindings": {
    "manifest_sha256": "sha256",
    "config_lock_sha256": "sha256",
    "source_manifest_sha256": "sha256",
    "benchmark_denylist_sha256": "sha256",
    "split_manifest_sha256": "sha256",
    "review_manifest_sha256": "sha256",
    "imported_decisions_sha256": "sha256",
    "admission_records_sha256": "sha256",
    "grader_support_manifest_sha256": "sha256",
    "tokenizer_render_policy_sha256": "sha256",
    "sft_train_jsonl_sha256": "sha256",
    "sft_token_records_sha256": "sha256",
    "dataset_release_subject_sha256": "sha256"
  },
  "counts": {
    "total_admitted": 96,
    "train_rows": 72,
    "validation_roots": 12,
    "test_roots": 12,
    "source_backed": 75,
    "llm_assisted": 21
  },
  "gates": {
    "source_inventory_frozen": true,
    "all_references_pass": true,
    "all_sanitizers_pass": true,
    "grader_identity_reconciled": true,
    "all_test_counts_positive": true,
    "all_targets_parse_and_apply": true,
    "all_rows_fit_token_budget": true,
    "tokenizer_policy_matches_consumer": true,
    "token_records_reconciled": true,
    "shared_grader_support_reconciled": true,
    "benchmark_overlap_count": 0,
    "cross_split_family_overlap_count": 0,
    "manifest_reconciled": true,
    "required_review_complete": true,
    "dataset_release_review_complete": true,
    "llm_category_coverage_complete": true
  },
  "distribution_scope": "internal_research"
}
```

Every `bindings` key shown above is mandatory and contains a lowercase SHA-256
of the exact canonical bytes for that artifact or policy record. The verifier
must reject missing, extra-meaning, stale, placeholder, or indirectly inferred
bindings. The manifest's own exclusions remain explicit and non-recursive.

`status: ready` is forbidden when any required count, artifact, oracle,
contamination check, token check, split constraint, hash reconciliation, or
human review is incomplete. Partial runs express `in_progress`, `incomplete`,
or `failed` only in the sibling `.state/run-state.json`; `readiness.json` is
absent. Once finalized, the ready root is immutable, so any bound-input change
requires a new dataset ID. If interrupted staging contains a stale temporary
readiness artifact, resume quarantines it outside the prospective ready root
before doing work; readiness cannot coexist with a non-ready operational
state.

Readiness does not contain or imply pass rate, uplift, benchmark score, model
quality, or training success.

## Human Review Policy

The pilot keeps mechanical work automated but requires semantic review where
deterministic execution cannot prove intent.

Before readiness:

- approve `llm_usage_terms` before any paid authoring call;
- review every admitted LLM-assisted task (at least 21);
- resolve every contamination/near-duplicate flag by approval or rejection;
- approve the frozen source inventory and final split manifest;
- review the exact final rows, token evidence, category/difficulty/provenance/
  split/rejection summaries, license artifacts, final contamination results,
  and sanitized-export allowlist/preview;
- approve that exact package under `dataset_release`;
- record reviewer identity, timestamp, task fingerprint, and decision without
  editing generated artifacts in place.

Imported decisions use a versioned JSONL schema with `scope`, `subject_id`,
`subject_fingerprint`, `decision` (`approve` or `reject`), stable reason code,
reviewer identity, UTC timestamp, and optional bounded comment. Required
scopes are `source_inventory`, `llm_usage_terms`, `llm_task_semantics`,
`contamination_flag`, `final_split`, and `dataset_release`. Each scope fingerprints only the bytes
and identities relevant to that decision:

| Scope | Fingerprinted subject |
|---|---|
| `source_inventory` | proposed source manifest bytes, Exercism revision/tree identities, taxonomy/classification version, and benchmark denylist |
| `llm_usage_terms` | provider/model identity, terms snapshot/hash/date, intended training use, distribution scope, and reviewed policy |
| `llm_task_semantics` | normalized blueprint, canonical docs/starter/reference/tests, negative-solution results, generation provider/model plus each stage's prompt/request/response hashes, approved `llm_usage_terms` decision hash, category/difficulty/family, and grader/scaffold fingerprint; excludes split placement |
| `contamination_flag` | both compared subject identities/fingerprints, bounded evidence, normalizer/threshold lock, and flag ID |
| `final_split` | proposed split manifest, complete admitted-pool fingerprint, seed, taxonomy, and all split constraints |
| `dataset_release` | frozen split, exact final training/eval rows, token-record ledger, final contamination receipts, release/category/difficulty/provenance/split/rejection/token/license summaries, dataset card/NOTICE/licenses, distribution scope, and sanitized-export allowlist/preview |

An approval is valid only for the exact scope-specific subject fingerprint.
Changed bytes included in that scope make its decision stale; unrelated changes
do not. In particular, a later proposed split does not stale an unchanged
`llm_task_semantics` approval, while any task/test/reference/grader/category or
family change does. Changing the admitted pool stales `final_split` but not
unchanged candidate approvals. Review import must compute these rules from the
schema rather than applying one blanket task/source/split fingerprint.

Any change to final rows, token evidence, final-screen receipts, release
summaries, license artifacts, distribution scope, or export preview stales
`dataset_release`. A release rejection follows the rollback defined by the
dataset state machine; it cannot be recorded as ready with a warning.

`config.lock.json` defines reviewer identities authorized for each scope.
Review import rejects unauthorized identities, duplicate/conflicting decisions,
and any decision emitted by the authoring provider or pipeline itself.

A reviewer may reject and request a new candidate, but review import never
mutates canonical files. Later large-scale profiles
may replace full LLM-task review with calibrated flag-based review plus random
sampling, but that is a separately versioned policy.

## Determinism, Resume, And Failure Handling

### Determinism

- Stable-sort task IDs and JSON keys.
- Bind split assignment to a recorded seed and family/category inputs.
- Serialize JSONL byte-identically across reruns.
- Give each candidate a private staging directory and append-only journal;
  workers never append directly to a shared JSONL or choose final ordering.
- Aggregate ledgers, reports, splits, and JSONL in one deterministic pass after
  stable sorting by candidate/task identity. Worker completion order cannot
  affect bytes or split placement.
- Make LLM generation non-determinism explicit through request identity and
  persisted normalized drafts; never pretend an API rerun is byte-reproducible.
- Once a draft and every required human decision are immutable inputs, each
  downstream mechanical stage is deterministic.
- Re-rendering a ready dataset from the same complete immutable input set must
  produce identical JSONL and manifests. That set includes the config lock,
  canonical tasks, shared-support manifest, persisted generation records,
  imported review decisions with their original timestamps, admitted-pool
  ledger, frozen split, token-record ledger, and exact `dataset_release`
  decision—not merely canonical tasks plus a config file.
- Keep mutable progress timestamps in the sibling `.state/run-state.json`.
  Once imported,
  generation and review timestamps are immutable provenance inputs rather
  than regenerated during verification.
- Verification, `verify-export`, and `--rerun-oracles` never regenerate
  provenance timestamps or mutate a ready/export root.

### Resume

- Write each task's stage receipt atomically after the stage completes.
- Flush candidate/generation/admission records incrementally.
- Reuse a passing stage only when its complete input fingerprint matches.
- Restart only the incomplete candidate/stage after interruption.
- Never reuse a reference/oracle result across a grader image, task tree,
  reference mapping, or protocol change.
- Keep the dataset lock in the sibling `.state/` directory to prevent two
  writers from mutating one staging state; a ready root has no writer.
- Reserve a provider request ID before a paid call and persist its terminal
  result atomically. On ambiguous interruption, reconcile that ID or require
  operator review; never blindly repeat a possibly billed request.
- Do not overwrite differing ready artifacts without an explicit new dataset
  ID; `--force` is for disposable incomplete roots, not history rewriting.

### Stable Outcome And Reason Codes

At minimum define, classify, and test outcome/reason codes for:

```text
profile_not_frozen
source_inventory_mismatch
source_inventory_review_stale
source_inventory_promotion_mismatch
source_deferred_by_profile
benchmark_id_overlap
benchmark_content_overlap
contamination_review_required
contamination_normalizer_error
shared_support_mismatch
duplicate_task
duplicate_family
missing_docs
missing_editable_files
missing_reference
missing_tests
unsafe_path
hardlink_rejected
file_limit_exceeded
reference_mapping_error
unsupported_editor_reference_change
static_schema_error
cmake_generator_mismatch
compiler_identity_mismatch
sandbox_policy_mismatch
language_standard_mismatch
generated_build_metadata_rejected
license_policy_missing
llm_usage_terms_unapproved
starter_already_passes
starter_harness_error
test_discovery_failed
zero_tests
reference_compile_failed
reference_tests_failed
reference_timeout
reference_sanitizer_failed
sanitizer_test_discovery_failed
sanitizer_test_count_mismatch
weak_generated_tests
whole_format_failed
target_apply_failed
target_reference_mismatch
token_overflow
chat_template_policy_mismatch
category_quota_unsatisfied
llm_capacity_insufficient
llm_transport_failed
llm_budget_exhausted
human_review_rejected
human_review_stale
final_screen_invalidated_split
dataset_release_review_stale
consumer_readiness_missing
consumer_model_revision_mismatch
consumer_tokenizer_mismatch
consumer_export_manifest_mismatch
consumer_template_policy_mismatch
consumer_loss_mask_mismatch
consumer_sequence_length_mismatch
consumer_raw_messages_required
consumer_adapter_mismatch
```

Classify each code in the schema. `source_deferred_by_profile` is the non-error
terminal state `deferred_profile`. Invalid/missing/overlap/oracle/format/token
conditions are terminal `rejected_content`; Docker unavailability, provider
transport/rate limits, and storage interruption are `retryable_error`;
`profile_not_frozen`, budget/capacity exhaustion, stale or unresolved review,
`final_screen_invalidated_split`, and unsatisfied quotas are run-level
`incomplete` until their defined backfill/review path succeeds. For example,
`llm_transport_failed` is
retryable until its configured retry budget is exhausted, while
`llm_budget_exhausted` never rejects the candidate. Preserve these distinctions
in CLI exit status, ledgers, summaries, and resume behavior.

All `consumer_*` codes are lane-preflight failures after dataset export;
they do not mutate or revoke an otherwise valid ready dataset. Shared-support,
language/scaffold, editor-mapping, CMake-generator/compiler/sandbox identity,
normal/sanitizer discovery, and sanitizer-count failures are candidate-content
or harness rejections unless the receipt proves a retryable infrastructure
fault.

## Security And Isolation

- Execute untrusted/generated C++ only in the pinned, network-disabled Docker
  grader with CPU, memory, PID, file-size, and wall-time limits.
- Do not mount credentials, model caches, repository `.git`, or unrelated host
  paths into the grader.
- Enforce the locked read-only-root, non-root, no-new-privileges, drop-all-caps,
  seccomp, and single-writable-scratch mount policy; receipts must bind the
  effective policy rather than only the requested flags.
- Treat task paths, archives, model output, and API structured output as
  untrusted.
- Reject traversal, symlinks, hardlinks, devices, sockets, and oversized
  trees/files.
- Use argv lists rather than interpolated shell from task data.
- Redact credentials and authorization headers from logs and errors.
- Never send benchmark contents or local hidden tests to the curator API.
- Do not send source-task reference implementations to the LLM authoring
  stages; source adaptation remains local and deterministic.
- Treat provider response text as untrusted data, never as shell, build, or
  filesystem instructions outside the canonical validator.
- Keep raw generated data, receipts, logs, and review artifacts under ignored
  `.w8-biayn/` paths.

## Scalability Beyond The Pilot

The canonical schema is the scaling boundary. Additional source or LLM
adapters must stop at canonical candidates; admission, splitting, rendering,
and verification remain shared.

To scale toward 5,000-10,000 genuinely distinct roots:

- add source adapters rather than special cases in the renderer;
- partition work by candidate with bounded worker pools;
- give workers private staging directories and one deterministic aggregator;
- cache LLM calls and oracle stages by complete fingerprints;
- enforce provider rate/concurrency/spend budgets centrally;
- maintain a global dedup/family index across dataset versions;
- shard JSONL deterministically only after the pilot format is stable;
- measure effective root/family diversity, not only row count;
- never count superficial starter variants as independent semantic roots.

Exercism alone cannot supply 5,000-10,000 distinct roots. Future adapters may
consider sources such as CodeContests after their single-file/stdin-output
shape is explicitly adapted and independently tested. CodeNet accepted/wrong
submission pairs are not a V1 source because repair tasks and weak test
availability are currently out of scope.

Any future repair-task profile, exact-Aider multi-turn profile, synthetic
response profile, or task-variant policy must use a new schema/profile and must
not be silently mixed into `aider-sft-pilot-v1`.

## Implementation Phases

An implementation agent should proceed in this order:

1. **Contracts first**: schemas, config validation, identities, reason codes,
   manifests, and golden fixtures.
2. **Shared benchmark manifest**: one 26-task denylist/taxonomy source reused by
   reporting and contamination checks.
3. **Pinned acquisition and inventory**: upstream registry keys, explicit
   75-task proposal, reviewed `inventory-promote`, and revision/tree checks.
4. **Canonical source adapter**: file roles including `files.editor`, C++17,
   reference mapping, shared-support references, and workspace assembly.
5. **Shared grader and LLM scaffold**: content-addressed Catch support plus the
   checked-in CMake/Catch generated-task scaffold; no LLM build programs.
6. **Oracle extraction/reuse**: image-bound and sandbox-bound, with the exact
   generator/compiler, separately observable compile target, normal/sanitizer
   discovery and full tests, and fresh receipts.
7. **Role-aware contamination and family index**: semantic exact checks first,
   allowlisted support/scaffold exclusions, review queue for near matches.
8. **Taxonomy and deterministic split**: separate candidate/dataset states and
   enforce 72/12/12 plus category cells, including final-screen invalidation,
   quota-preserving backfill, and release-review states.
9. **Renderer and tokenizer admission**: exact editable/context ordering,
   pinned Aider parser, raw-message kwargs-aware adapter, final-only policy,
   explicit qwen loss mask, per-row token ledger, and length checks.
10. **LLM curator adapter**: mocked provider tests and stage-specific revision
    routing first; finish source admission, compute deficit/capacity reserve,
    and import approved usage terms before any paid call; then require dry-run,
    explicit budgets, and acknowledgement.
11. **Review and readiness**: scope-specific fingerprints, task cards, review
    manifest, exact `dataset_release` package, external mutable state, full
    reconciliation, and schema-v2 immutable receipt.
12. **Licensing and sanitized export**: dataset card, NOTICE, license records,
    token records, consumer manifest, `verify-export`, and private-asset
    exclusion tests.
13. **Thin lane handoff**: verified consumer bundle, exact GLM revision/local
    hashes, raw-message adapter, matching tokenizer/template kwargs/loss mask,
    recomputed per-row evidence, no dataset-loader chat templating, and
    auto-prepare disabled; training remains outside this pipeline's acceptance.

Do not start with API generation. Prove the source adapter, oracle, renderer,
and verifier on local fixtures first so paid drafts cannot bypass an untested
admission path.

## Required Tests For The Future Implementation

At minimum add:

- schema/config validation and round-trip tests;
- exact upstream-key/commit/clean-tree and source-manifest promotion tests;
- source inventory exact-count, duplicate, denylist, and revision-drift tests,
  including a fixture proving all 75 pinned source tasks retain C++17;
- canonical path/symlink/hardlink/special-file, normalization, fence-line, and
  byte/file-count limit tests, with fence rejection covering editable and
  model-context bodies;
- role-specific size tests proving the pinned 656,882-byte shared `catch.hpp`
  is admitted by digest while an oversized task-authored/model-visible file is
  rejected;
- reference mapping tests including unchanged editable files and the
  `vehicle-purchase` `files.editor`/exemplar-header fixture;
- collision-checked workspace assembly and shared-support digest tests;
- Exercism compile-target versus default-`ALL` separation, no-CTest, Catch
  discovery/count, starter-nonpass, reference-pass, timeout, and stale
  image/fingerprint tests, including exact `Unix Makefiles` generator,
  compiler-path/version/binary identity, and effective sandbox-policy drift;
- separate sanitizer build/argv/environment, explicit sanitizer discovery,
  finding, timeout, positive count, and normal-versus-sanitizer test-count
  equality tests;
- generated-task scaffold tests rejecting LLM build scripts, commands, and
  dependencies;
- generated negative-solution/test-strength tests;
- exact/near benchmark contamination and family-leak tests, including exact
  shared Catch/tests-main/CMake matches that must not become task overlap;
- deterministic category-aware split tests;
- candidate-state versus dataset-state, proposed/frozen split review,
  final-screen rollback/backfill, and exact `dataset_release` review tests;
- golden compact-prompt and whole-target tests, including independent lexical
  ordering and empty-section behavior for read-only context files;
- pinned Aider parser acceptance plus extra/missing/duplicate/path rejection;
- apply-target/reference-byte-equality tests;
- GLM raw-message adapter/chat-template-kwargs/final-only policy tests, including
  stable rendered-token and loss-mask hashes, per-row token-record
  reconciliation, and overflow rejection;
- SLIME tests requiring raw message lists, rejecting dataset-loader
  `--apply-chat-template`, and proving zero-user/nonzero-assistant qwen loss;
- mocked LLM provider schema, retry, redaction, budget, and resume tests;
- no-call preflight tests proving complete source admission, approved usage
  terms, computed cell deficits, a capacity reserve of at least three times
  required admissions, and coherent per-stage/aggregate budgets;
- stage-specific revision-routing and contamination-non-disclosure tests;
- interrupted-build resume and stale-stage invalidation tests;
- ambiguous paid-call reconciliation, concurrent worker ordering, stale human
  decision, scope-specific review invalidation, reviewer authorization,
  generation-provenance/usage-terms fingerprinting, `dataset_release`
  staleness, and deterministic review import/export tests;
- manifest, JSONL, admission-ledger, rejection-ledger, and readiness
  reconciliation tests, including the token-record and `dataset_release`
  subject hashes plus every mandatory schema-v2 binding;
- readiness-absence and stale-readiness-removal tests for incomplete runs,
  with mutable state/locks confined to the sibling `.state/` directory;
- immutable ready-root `--rerun-oracles` external-scratch and non-mutating
  `verify-export` tests;
- dataset-card/NOTICE/license and sanitized-export private-file exclusion tests,
  including exact export-manifest reconciliation and token/mask recomputation
  from sanitized files only;
- GLM handoff tests rejecting manifest-only data, unpinned model downloads,
  tokenizer/template/kwargs mismatch, non-raw messages, wrong rollout adapter,
  dataset-loader chat templating, implicit loss-mask defaults, sequence drift,
  token/mask evidence drift, and auto-prepare;
- an end-to-end fixture with both source and LLM-assisted candidates and no
  live network/API dependency.

Normal unit tests must not spend money or require an external model endpoint.
Docker-backed integration tests may skip with an explicit prerequisite message
when Docker is unavailable; the release verifier itself must not mark a real
dataset ready without its Docker evidence.

Run the repository validation suite after implementation:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/w8-biayn-framework
```

For CLI/setup changes, also run the fresh-machine checks required by
`AGENTS.md`.

## Documentation Synchronization Contract

When this pipeline's commands, config, task schema, row schema, source count,
split policy, taxonomy, prompt, reference mapping, test gates, LLM policy,
security model, output layout, or readiness semantics change, update in the
same logical change:

1. this document;
2. `README.md`;
3. `ROADMAP.md`;
4. `.agents/REPO_GUIDE.md` (therefore both `AGENTS.md` and `CLAUDE.md`);
5. `.agents/skills/w8-biayn-framework/SKILL.md`;
6. `docs/single_sample_for_sft.md` when Aider row semantics change;
7. `docs/moonlight_single_sample_sft.md` when the smoke/handoff relationship
   changes;
8. `examples/slime/glm47_cpp_perf/README.md` and the consuming lane when the
   data handoff changes;
9. `examples/slime/moonlight_cpp_perf/README.md` when the one-row seed helpers
   or shared contracts change;
10. tests that enforce the changed contract.

Keep `AGENTS.md` and `CLAUDE.md` as symlinks to `.agents/REPO_GUIDE.md`; never
fork their contents.

## Definition Of Done For Pipeline Implementation

The implementation is complete only when:

1. all future CLI commands above—including `inventory-promote` and sanitized
   `export`/`verify-export`—exist and have no-spend plan/verify paths;
2. a clean clone can acquire all three exact upstream pins through the named
   repo-owned registry keys;
3. the exact Appendix A inventory of 75 source candidates is explicit,
   revision-checked, and hash-bound;
4. the source adapter preserves C++17, maps `files.editor`, resolves references,
   splits compile/test phases, and references one verified shared-support bundle;
5. the LLM adapter uses the repo-owned C++17 CMake/Catch scaffold and rejects
   generated build commands/dependencies, and paid calls remain blocked until
   source admission is complete, usage terms are approved, exact deficits are
   computed, and candidate capacity is at least three times required admissions;
6. source and LLM adapters produce the same role-complete canonical schema and
   collision-checked workspace assembly;
7. every admitted reference passes separately observable configure, compile,
   positive normal/sanitizer discovery and full tests, and fresh ASan/UBSan
   image-bound gates under the exact `Unix Makefiles` generator, compiler
   binary identity, and enforced sandbox policy;
8. role-aware contamination excludes allowlisted shared support/scaffolds while
   proving all 26 benchmark roots and related semantic copies are absent both
   before splitting and over the exact final rendered bundle;
9. split/family/category constraints reconcile to 72/12/12 and 96 total through
   separate admitted-pool, reviewed/frozen-split, final-screen, and
   `dataset_release` states, with any late invalidation rolling back to
   quota-preserving backfill;
10. `sft/train.jsonl` has exactly 72 deterministic, parser-valid, token-fit
    final-answer-only rows consumed as raw messages by the locked kwargs-aware
    adapter, while `sft/token-records.jsonl` reconciles every rendered-token and
    loss-mask hash/count and proves assistant-only explicit qwen loss without
    dataset-loader chat templating;
11. validation/test prompt artifacts contain no answers or hidden identifiers;
12. at least 21 human-approved LLM-assisted roots are admitted, occur in every
    split, cover every category at least twice overall, and include at least
    one training root per category;
13. source, usage-terms, task, contamination, split, and `dataset_release`
    reviews use authorized reviewers and exact scope-specific fingerprints,
    including generation provider/model and prompt/request/response provenance
    for every LLM task;
14. interrupted execution resumes without duplicating calls or weakening
    evidence, with all mutable state/locks/journals outside the immutable ready
    root;
15. an offline `verify` recomputes every manifest/readiness claim, validates all
    schema-v2 bindings including token records and the release-review subject,
    and reruns optional oracles only in external scratch;
16. deterministic dataset-card/NOTICE/license artifacts and a private-asset-free
    `slime-sft` export reconcile to the ready root, and consumer-side
    `verify-export` independently reconciles its manifest and recomputes every
    row's token/mask evidence without the private root;
17. the GLM lane rejects manifest-only/unready data and mismatched model,
    tokenizer, template/kwargs, rollout-adapter, loss-mask, sequence, or
    token-record identities; requires raw messages; rejects dataset-loader chat
    templating; pins the HF revision; recomputes all exported row evidence; and
    disables auto-prepare;
18. standard tests, lint, compile, skill validation, and relevant fresh-machine
    checks pass;
19. no training, target-model response collection, repair rows, or uplift
    requirement has been smuggled into dataset readiness.

## Appendix A: Frozen Exercism Source Candidate Inventory

This appendix is normative for `aider-sft-pilot-v1`. At Exercism C++ commit
`d2babb2bd750c884abf86ce52dde274ae7de9749`, the source adapter must find
exactly these 75 roots and no additional source candidate. Discovery must join
these paths with the 26-root benchmark denylist before copying task content.
Absence, duplication, kind drift, or an unexpected extra manifest entry is
`source_inventory_mismatch`.

### Practice roots (60)

Each slug below denotes `exercises/practice/<slug>`:

```text
acronym
affine-cipher
alphametics
anagram
armstrong-numbers
atbash-cipher
beer-song
binary
binary-search
bob
collatz-conjecture
darts
difference-of-squares
eliuds-eggs
etl
flower-field
food-chain
grains
hamming
hello-world
hexadecimal
high-scores
isbn-verifier
isogram
largest-series-product
leap
list-ops
luhn
matching-brackets
minesweeper
nth-prime
nucleotide-count
pangram
pascals-triangle
pig-latin
prime-factors
protein-translation
rail-fence-cipher
raindrops
resistor-color
resistor-color-duo
reverse-string
rna-transcription
robot-simulator
roman-numerals
rotational-cipher
run-length-encoding
say
scrabble-score
secret-handshake
series
sieve
simple-linked-list
sum-of-multiples
triangle
trinary
twelve-days
two-bucket
two-fer
word-count
```

### Concept roots (15)

Each slug below denotes `exercises/concept/<slug>`:

```text
doctor-data
election-day
ellens-alien-game
freelancer-rates
interest-is-interesting
lasagna
lasagna-master
last-will
log-levels
making-the-grade
pacman-rules
power-of-troy
speedywagon
troll-the-trolls
vehicle-purchase
```
