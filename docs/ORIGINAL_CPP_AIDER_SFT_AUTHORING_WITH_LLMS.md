# Original C++ Aider-Style SFT Authoring

Status: **local-authoring design contract; no external provider calls are required**
Proposed profile ID: `aider-sft-authored-cpp-v1`

## Aim

Create a large, clean corpus of original C++17 whole-file editing tasks that
trains the same practical capability exercised by the Aider Polyglot C++
benchmark: read an instruction and incomplete starter files, then return the
complete header and implementation files.

The immediate target is a release-eligible pool of at least 625 original task
roots, from which a family-safe set of 500 train roots and at least 24 roots in
each validation and internal-test split can be selected. Six deterministic
prompt styles per train root yield 3,000 SFT rows. These counts match the
primary Aider SFT scale, but this is a separate source profile until its
implementation, locks, Docker evidence, and verification exist.

The project already contains 75 clean non-holdout Exercism C++ roots. The
official Aider Polyglot C++ holdout contains the remaining 26 roots in the
pinned Exercism snapshot. This profile adds **new behavioural contracts**, not
renamed, translated, or lightly altered copies of either set.

## Non-Negotiable Claim Scope

- `benchmark_derived = false`
- `distribution_scope = internal_research`
- The 26 official Aider Polyglot C++ roots remain permanent holdouts.
- No Aider Polyglot instruction, test, reference, starter, grader output, or model response may leave the repository authoring environment.
- No existing Exercism task's distinctive contract, edge-case combination,
  API, tests, or solution may be used as an authoring seed.
- Tasks are authored locally. Local provenance records source hashes and authoring inputs; they are never target-model conversations or direct SFT rows.

The resulting model may be evaluated on Aider Polyglot C++, provided every
authored root passes the required exact and semantic contamination screens.
An evaluation result remains an internal experiment result, not proof of broad
uncontaminated coding generalization.

## Intended Task Shape

Every root follows the C++ editing shape familiar from Exercism and Aider:

```text
tasks/<task-id>/
  task.json
  docs/
    instructions.md
    introduction.md                 # optional
  workspace/
    starter/
      <task_id>.h
      <task_id>.cpp
    reference/
      <task_id>.h
      <task_id>.cpp
  private/
    tests/
      <task_id>_test.cpp
    authoring/
      provenance.json               # local redaction-safe evidence
  receipts/
    normal-oracle.json
    sanitizer-oracle.json
    contamination.json
```

The public task describes a narrow C++17 API. The starter header exposes the
API and the starter implementation is incomplete or deliberately wrong. The
reference contains a complete implementation. Catch tests are private by
default; a small, sanitized example may be shown in a prompt only when the
profile explicitly permits it.

Example target shape:

````text
interval_union.cpp
```cpp
#include "interval_union.h"

namespace interval_union {
// complete implementation
}
```

interval_union.h
```cpp
#pragma once

#include <utility>
#include <vector>

namespace interval_union {
std::vector<std::pair<int, int>> merge(
    std::vector<std::pair<int, int>> intervals);
}
```
````

The user prompt contains the task instruction and the two starter files. The
assistant target contains exactly the two complete editable file listings, in
sorted path order, with no reasoning, test code, diff, or prose. Rows are raw
two-message conversations; user loss is zero and assistant loss is one.

## Originality Standard

An original task may teach a common programming technique, such as interval
merging, parsing, state machines, or date arithmetic. It must nevertheless
have an independently designed API, input model, output model, constraints,
and edge-case set. Changing names, examples, or comments on an existing
benchmark task is not original.

Before task authoring, maintain a local seed registry containing only
project-authored high-level capability goals, for example:

```json
{
  "seed_id": "range-normalization-v1",
  "capability_goal": "normalize a collection of integer ranges",
  "forbidden_features": ["benchmark-derived wording", "copied APIs"],
  "target_category": "algorithms_data_structures",
  "target_difficulty": "medium"
}
```

The registry must not contain benchmark text, benchmark test cases, or copied
task descriptions. It is versioned, hashed, and frozen before authoring.

## Local Authoring Flow

The proposed future commands are illustrative; no command is implemented by
this document alone. All local authoring operations must run through repo-owned `w8-biayn data aider-sft authored ...` commands, never notebooks or ad hoc files.

### Automation And Deferred Review Policy

The campaign is batch-first and predominantly automatic. Neither a human
decision nor a per-task manual inspection is required to generate candidate
tasks, run authoring revisions, materialize files, or execute mechanical
checks. The system writes every schema-valid local authoring record as a fingerprinted
candidate, then workers process the candidate queue asynchronously.

Mechanical checks are therefore **automatic filters, not interactive gates**:

- a failed static, Docker, sanitizer, contamination, render, or token check
  records a stable reason code and places that root in quarantine;
- the rest of the batch continues; a failure never pauses all authoring work;
- automatic retries are allowed only for explicitly retryable infrastructure
  failures and use the same frozen task input;
- a generated candidate dataset may be inspected before all workers finish,
  but it is labeled `auto_unverified` and cannot be represented as a verified
  training release;
- only roots whose automated evidence passes are eligible for the final
  training projection.

Human audit happens later, after the campaign has generated its candidate pool,
automatic admission report, contamination report, and token/Docker receipts.
Audit may sample task quality, inspect aggregate rejection rates, and decide
whether to publish or revise a campaign. It does not sit in the authoring loop
or block individual candidates.

```text
Frozen seed registry
        │
        ▼
1. Planner ──► structured original task proposal
        │                    │
        │              automatic schema checks
        ▼                    ▼
2. Author  ──► header, starter cpp, reference cpp, instructions, tests
        │                    │
        │              automatic static/path/private-asset checks
        ▼                    ▼
3. Critic  ──► edge-case and API consistency report
        │                    │
        └──────────► deterministic revision record (bounded)
                             │
                             ▼
              queued Docker normal + ASan/UBSan workers
                             │
                             ▼
             automatic contamination/duplicate/family screening
                             │
                             ▼
         auto-admit or quarantine → render → tokenize → verify-export
```

### 1. Planner record

Input: one approved high-level seed, category quota, difficulty target, C++17
constraints, and a JSON schema. The planner must not receive any benchmark or
Exercism task contents.

Required structured response:

```json
{
  "title": "…",
  "task_id_hint": "lowercase-kebab-case",
  "behavioural_contract": "…",
  "public_api": {"header": "…", "functions": ["…"]},
  "input_constraints": ["…"],
  "edge_cases": ["…"],
  "primary_category": "algorithms_data_structures",
  "difficulty": "medium",
  "originality_rationale": "…"
}
```

Free-form prose, unknown fields, unsafe paths, a duplicate task ID, or an API
that cannot be represented in a `.h` and `.cpp` pair are automatically
quarantined. The proposal is a candidate contract, not an admitted task.

### 2. Author record

Input: only a schema-valid accepted proposal plus the repo-owned C++17/CMake/
Catch scaffold contract. The author produces structured file contents:

```json
{
  "instructions_md": "…",
  "starter_h": "…",
  "starter_cpp": "…",
  "reference_h": "…",
  "reference_cpp": "…",
  "private_tests_cpp": "…",
  "test_rationale": ["…"]
}
```

The author may not produce a `CMakeLists.txt`, shell command, package install,
network access, executable download, compiler flag, or additional editable
file. The repository owns the build/scaffold and invokes the locked compiler.
The reference header and starter header must define the same public API.

### 3. Critic record

Input: the candidate's own instructions, API summary, starter/reference
diff-summary, and test-case descriptions. The critic proposes missing edge
cases, contradiction fixes, or safety concerns in a strict JSON report. It
does not receive benchmark material or hidden tests from any other root.

The critic cannot approve a task. Its report may cause one bounded author
revision. Every revision has a parent record ID and new source hashes; it is
not silently substituted for the original proposal.

### 4. Automated admission workers

The repository, not the author, performs the decisive checks automatically in
parallel workers:

1. strict UTF-8/path/schema/file-role validation;
2. exact duplicate and local semantic similarity screening against all authored
   roots, the 75 source-only roots, and the 26 Aider holdouts;
3. clean normal C++17 CMake/Catch build in the locked network-disabled Docker
   image;
4. reference passes complete tests twice;
5. fresh ASan/UBSan build and test pass with matching test count;
6. starter fails or is otherwise demonstrably incomplete; reference replacement
   passes;
7. target parses and applies exactly to the reference bytes;
8. token and assistant-loss-mask admission with no truncation;
9. immutable producer and sanitized-consumer verification.

Each worker writes a terminal `auto_admitted`, `auto_rejected`, or
`retryable_error` receipt. An local author claim that its solution is correct, original,
or well-tested is never admission evidence.

## Deterministic Quota Scheduler

The author does not choose the campaign category, split, or quota. Before task authoring, the scheduler freezes a campaign target matrix covering total roots,
primary category, difficulty, and intended split. The six primary categories
are `algorithms_data_structures`, `text_parsing`, `numerical_reasoning`,
`time_date`, `state_concurrency`, and `logic_grids_games`.

For each cell, it computes:

```text
deficit = required eligible family-safe roots − current auto-admitted roots
minimum candidate capacity = 3 × max(deficit, 0)
```

Only `auto_admitted` roots count. Generated candidates, quarantined candidates,
retryable infrastructure failures, rejected roots, and roots whose families
would cross splits do not reduce a deficit. The scheduler selects the largest
remaining eligible deficit, assigns its category/difficulty/split to the next
seed, and includes that assignment in the planner record. The planner must
echo the assigned category and difficulty; a mismatch is automatically
quarantined.

The campaign state persists the frozen target matrix, every cell count, family
assignment, scheduled seed, candidate capacity, and receipt fingerprint.
`--resume` recomputes the next record only from these records. It must never
infer progress from an local authoring note or silently count a failed task.

Example:

```text
text_parsing / medium / train: need 12 more admitted roots
→ schedule at least 36 independent candidate contracts
→ each passing root reduces the deficit by one
→ rejected/failed roots consume candidate capacity but not the deficit
```

## Local Provenance And Safety

Each local authoring record stores, without secrets or hidden benchmark assets:

- local authoring identity, task input hash, and record ID;
- system-prompt hash, response-schema hash, seed/proposal/file hashes, and
  decoding parameters;
- timestamp, attempt number, parent record ID, response hash, and cost/usage
  counters;
- decision and stable rejection reason, if any.

Do not send task material to external providers. Freeze local templates, schemas, and revision policy in the profile lock; changing any requires a new authoring fingerprint and reruns affected candidates.

Set a finite campaign budget and a maximum of one critic-driven rewrite per
candidate. Resume must reuse a response only when every relevant record and
input fingerprint matches; otherwise it creates a new attempt record.

## Suggested Campaign Plan

Start small and prove the mechanism before scaling:

| Phase | Seeds | Candidate roots | Goal |
|---|---:|---:|---|
| Offline fixture | 3 | 3 | Test schemas, parser, and receipts locally |
| Local smoke | 5 | 5 | Validate local authoring and automated Docker workers |
| Pilot | 50 | 150 | Generate automatically; review aggregate rejection rates later |
| Release pool | >=250 | >=625 | Supply 500/24/24 family-safe selection |

Use at least three candidate contracts per needed admitted root. This preserves
capacity when candidates fail originality, Docker, sanitizer, test-strength,
or token limits.

## Task Quality Checklist

The automatic static worker checks each local-authored candidate for:

- one clear behaviour and a small public API;
- C++17-only dependencies from the standard library;
- a real header/implementation boundary;
- deterministic behaviour and no filesystem, network, clock, randomness, or
  environment dependence;
- tests for nominal, boundary, malformed/empty where applicable, and at least
  one contract-distinguishing edge case;
- a starter that cannot accidentally pass the complete suite;
- no benchmark-derived language, examples, or hidden contract details;
- a task family ID that groups all variants of the same behavioural contract.

## Operator Outcome

A successful automatically admitted root produces the same form of SFT row as an Exercism
root: a user message with `*.cpp` and `*.h` starters, plus a code-only assistant
message with complete replacements. Candidate rows appear automatically during
generation; only auto-admitted rows with Docker, contamination, token, and
producer/consumer evidence can enter the verified Aider-style SFT projection.

## Pipeline Stall And Resolution Ledger

This section is append-only once implementation begins. Whenever any part of
the authoring, task-interface, scheduler, Docker, rendering, tokenization, finalization,
or verification pipeline stalls, the same logical change that resolves it must
add an entry here. A stall includes a queue that cannot advance, repeated
retryable failure, deadlock, quota cell that cannot be filled, incompatible
receipt, or a command that cannot reach a terminal outcome.

Each entry must include:

- date, profile/version, affected stage, and stable failure code;
- observable symptom and impact, including whether external calls were made;
- root cause and why existing automation did not recover;
- exact solution or operational workaround used;
- regression test, receipt, or command that proves the resolution;
- evidence invalidated by the change and the required regeneration/retry
  action.

Do not include secrets, raw benchmark assets, or private tests. Use task IDs, record IDs, hashes, redacted diagnostics,
and stable reason codes instead.

### Entries

 This document specifies
the future profile; add the first entry when its implementation encounters and
resolves a real pipeline stall.

This document does not authorize training or a claim of readiness. Implementing it requires a new profile configuration, authoring
adapter, CLI commands, schemas, tests, Docker receipts, and consumer checks in
one logical change.
