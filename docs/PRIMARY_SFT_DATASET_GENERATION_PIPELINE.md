# Primary SFT Dataset Generation Pipeline

Status: **V2 design contract; implementation and release pending**

Contract version: aider-sft-pipeline-v2.0

Default dataset profile: aider-sft-hybrid-3000-v1

## Authority And Status

This document is the normative contract for generating the repository's
primary Aider-style C++ supervised fine-tuning dataset. It defines one active
profile: aider-sft-hybrid-3000-v1.

The profile targets exactly 3,000 single-turn training rows derived from 500
verified C++17 task roots. It uses a larger release-eligible pool to support
family-safe validation/test selection and late candidate replacement.

The repository does not yet implement every command and gate in this V2
contract. A profile declaration, passing unit test, or earlier dataset artifact
is not evidence that aider-sft-hybrid-3000-v1 is ready. Readiness may be
claimed only after the implementation, full producer verification, and
consumer verification described here succeed against the exact released bytes.

Required reading for implementation work:

1. AGENTS.md
2. README.md
3. ROADMAP.md
4. .agents/skills/w8-biayn-framework/SKILL.md
5. this document
6. relevant code under src/w8_biayn/aider_sft/
7. the active SLIME consumer under examples/slime/glm47_cpp_perf/

If another document conflicts with this document about the hybrid SFT dataset,
this document wins. Once a dataset is released, a semantic change to its
sources, schema, renderer, grader, tokenizer, split policy, or review policy
requires a new profile ID.

## Objective

The pipeline must reproducibly convert non-benchmark programming exercises
from pinned Exercism repositories into compile-validated,
contamination-screened C++17 tasks and then render an immutable,
SLIME-compatible SFT bundle.

The released profile must:

- contain exactly 3,000 single-turn training rows;
- derive those rows from exactly 500 train roots and six prompt styles per
  root;
- package at least 24 validation and 24 internal-test roots without answers;
- build a release-eligible pool of at least 625 roots before split review;
- preserve task-family isolation across train, validation, and internal test;
- verify starter, reference, tests, and rendered target in a pinned,
  network-disabled Docker sandbox;
- exclude all official Aider Polyglot C++ tasks and semantic copies;
- record source, license, model-assisted translation, grader, review, token,
  and release provenance;
- resume without duplicating paid calls or weakening evidence;
- export a private-asset-free consumer bundle whose rows and token evidence can
  be verified without the producer's hidden tests or references.

Dataset readiness proves data construction only. It does not prove model
quality or benchmark uplift.

## Non-Goals

This pipeline does not:

- collect target-model conversations or target-model repair trajectories;
- run multi-turn agents, Multi-SWE-bench, or repository issue resolution;
- train a model or run base, SFT, GRPO, or benchmark evaluation;
- use model-based rewards during admission;
- optimize runtime or use the PIE performance reward;
- include official benchmark tasks in any split;
- treat prompt variants as independent semantic roots;
- permit one-off scraping, conversion, or grading scripts outside the
  repo-owned CLI;
- write a custom trainer.

An LLM may translate or repair a candidate during curation. Such calls are
authoring inputs with explicit provenance, not target-model samples.

## Profile Contract

### Counts

The profile separates root diversity from row augmentation:

| Artifact | Required count |
|---|---:|
| Release-eligible root pool before split review | >= 625 |
| Selected train roots | 500 |
| Selected validation roots | >= 24 |
| Selected internal-test roots | >= 24 |
| Prompt styles per train root | 6 |
| Released training rows | 3,000 |

The 625-root pool is a capacity gate, not a promise that every eligible root
will appear in the release. Unselected roots remain fingerprinted standby
candidates. Validation and internal-test counts may grow above 24 only when
family indivisibility requires it; the exact counts are frozen in the reviewed
split.

The expected acquisition plan starts from at least 250 distinct seed concepts
and produces approximately 2.5 structurally distinct C++ roots per seed. These
are planning targets. The blocking gates are the counts above, family
diversity, and all admission evidence. Repeated superficial rewrites do not
count as distinct roots.

### Taxonomy

Every root has exactly one primary category:

1. algorithms_data_structures
2. text_parsing
3. numerical_reasoning
4. time_date
5. state_concurrency
6. logic_grids_games

Every split must contain at least four roots from each category. Remaining
capacity is allocated proportionally to the eligible pool, subject to family
isolation and difficulty coverage. This is a minimum-coverage constraint, not
an equal-cell grid.

Validation and internal test normally target four roots per category. A
category may contain five when an indivisible family would otherwise be
excluded. Larger families must be sub-sampled before split selection, with
discarded siblings recorded; an admitted family must never be divided across
splits.

Each root also carries non-exclusive tags for algorithm, data model, language
surface, input surface, file surface, and difficulty. Difficulty is easy,
medium, or hard and is based on the implementation and test surface, never
observed model outcomes.

## Terminology

- **Seed**: pinned instructions and source-language assets selected for C++
  translation.
- **Variant**: one structurally distinct C++ API and implementation design for
  a seed.
- **Candidate root**: a canonicalized variant that has not passed admission.
- **Task family**: a seed and every translation, rewrite, or related task with
  the same behavioral contract.
- **Release-eligible root**: a canonical root that passed all mechanical,
  semantic, licensing, and review gates.
- **Selected root**: a release-eligible root assigned to a frozen split.
- **Standby root**: a release-eligible root not selected but available for a
  policy-compliant replacement.
- **Prompt style**: one deterministic user-context representation of a train
  root. Prompt styles do not create new semantic roots.
- **SFT row**: one raw two-message conversation for one train root and prompt
  style.
- **Reference**: the solved editable-file state used to validate the grader and
  render the assistant target.
- **Readiness**: a verified property of one immutable dataset bundle and its
  receipts.

## Permanent Benchmark Holdout

The following 26 official Aider Polyglot C++ task IDs are a permanent denylist:

~~~text
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
~~~

One shared repository-owned manifest must supply this set to dataset
construction, contamination checks, and benchmark reporting. Implementation
code must not carry a second drifting copy.

Reject the exact task in any language, renamed or lightly rewritten copies,
ports with the same behavioral contract and distinctive edge cases, and roots
whose instructions, starter, reference, or tests substantially match benchmark
artifacts. Generic concepts remain allowed when the task contract and edge
cases are independently distinguishable.

No benchmark instructions, tests, references, or model responses may be sent
to a translation provider.

## Pipeline Overview

The V2 pipeline has eleven ordered stages:

1. freeze configuration and runtime identities;
2. acquire pinned source repositories;
3. harvest and license-screen seed concepts;
4. translate seeds into C++17 variants;
5. canonicalize text, paths, roles, and task families;
6. build and run the full normal and sanitizer oracles;
7. run contamination, duplication, and semantic review;
8. render six prompt styles and run target/token admission;
9. select and review the family-safe split with standby roots;
10. finalize an immutable producer bundle;
11. export and independently verify the sanitized SLIME bundle.

Stages may resume only from fingerprint-compatible evidence. A later stage may
not waive an earlier gate.

## Pinned Inputs And Run Identity

The checked-in profile configuration and generated lock must bind:

- profile and contract versions;
- all upstream repository URLs, exact commits, and normalized tree hashes;
- the shared benchmark holdout manifest hash;
- the seed inventory and license-policy hashes;
- translation provider/model revisions;
- system prompts, response schemas, decoding settings, and retry budgets;
- grader image digest, compiler path, full compiler version, and compiler
  binary hash measured inside that image;
- CMake, build-tool, Catch2, ASan, and UBSan identities;
- effective Docker isolation policy and seccomp digest;
- canonicalization, family, contamination, and split policy versions;
- tokenizer revision and local file hashes;
- Transformers and Jinja versions and exact chat-template kwargs;
- prompt renderer, whole-file parser, response-format, and loss policy
  versions;
- sequence-length limit of 8,192 tokens;
- category, difficulty, row-count, and split constraints;
- reviewer policy and allowed license identifiers;
- aggregate and per-stage paid-call budgets.

plan must fail before paid work when an identity is missing or mismatched. It
must inspect the compiler inside the exact grader image; host compiler identity
is not admissible evidence.

--re-fingerprint-grader-toolchain is allowed only as an explicit no-spend
planning operation. It writes a new proposed lock and review subject. It must
not overwrite an approved lock in place, run implicitly during build, or reuse
oracle receipts from the previous identity.

All source checkouts used for planning or finalization must be exact and clean.
Dirty trees, symbolic revisions, unpinned downloads, and mutable container tags
are blocking errors.

## Source Acquisition And Harvesting

The initial source universe is limited to pinned revisions of:

- exercism/problem-specifications for canonical exercise concepts and
  instructions;
- mature sibling tracks such as Rust, Python, Go, and Java for human-written
  APIs, tests, and reference behavior;
- the Exercism C++ track only for non-benchmark compatibility lessons and
  source roots explicitly admitted by the frozen inventory.

All acquisition must use repo-owned upstream registry entries and
uv run w8-biayn upstreams clone. Do not vendor upstream repositories or
materialize generated datasets in Git.

harvest-seeds must:

- enumerate candidates deterministically from the pinned repositories;
- exclude benchmark slugs and already selected semantic families before any
  provider call;
- preserve source repository, commit, path, digest, author, and license
  evidence;
- reject missing, ambiguous, or conflicting licensing;
- reject duplicate concepts and sources whose tests cannot establish a useful
  behavioral contract;
- write a no-spend inventory and exact review fingerprint.

The license allowlist is configuration, not an inference made by the LLM.
Only identifiers approved by repository policy may proceed. Typical candidates
include MIT, Apache-2.0, BSD variants, and CC0, but the checked-in allowlist is
authoritative. Copyleft, share-alike, unknown, or incompatible assets are
rejected before translation.

## Translation And Variant Construction

### Bilingual Translation

translate-seed translates both code and prose. It must rewrite
language-specific concepts in instructions.md into precise C++17 terms while
preserving the behavioral contract. Examples include mapping optional values
to std::optional, language-specific exceptions to standard C++ exceptions, and
collection or ownership semantics to their intended STL equivalents.

A translated root must not combine C++ starter files with instructions that
still require Rust, Python, Go, or Java syntax or behavior. A mechanical
language-residue scan and human semantic review are blocking gates.

### Structural Variants

Each seed may yield multiple variants only when they provide genuinely
different C++ surfaces, such as:

- a free-function API versus an object-oriented API;
- a flat-container representation versus an encapsulated value type;
- a header-only API versus a declaration/source pair;
- iterator, operator, or template use that is natural for the task.

Variant generation must not introduce gratuitous template metaprogramming or
obscure optimizations. References must favor readable, idiomatic C++17 and the
standard library. For header/source pairs, headers contain declarations and
only intentionally inline definitions; source files contain ordinary
definitions. Duplicate bodies and declaration mismatches are rejected.

All variants of one seed share a family ID. Renaming symbols, rearranging
files, or changing prompt prose does not create a new family.

### Provider Boundary

Provider responses must conform to a strict structured schema. They may emit
instructions, editable files, references, tests, and declared metadata. They
may not emit build commands, Docker arguments, dependencies, shell scripts, or
paths outside the canonical workspace.

Every paid call requires:

- approved usage terms and data-handling policy;
- an explicit paid-call acknowledgement;
- a reserved request ID persisted before dispatch;
- per-stage and aggregate request/token/cost limits;
- prompt, response, provider, model, and decoding fingerprints;
- redacted logs that never contain credentials.

Retries use critique derived from the candidate's private build evidence, but
the full hidden suite is not sent to the provider. Three consecutive
initial-compile failures across different candidates trip a
run_level_configuration_error; the pipeline freezes state and stops paid
repairs until an operator resolves the systematic fault.

## Canonical Task Contract

Every adapter must produce the same canonical root schema:

~~~text
schema_version
task_id
family_id
seed_id
variant_id
provenance
license
primary_category
tags
difficulty
instructions
files.editable
files.context
files.reference
files.tests
files.scaffold
expected_test_count
normalization
generation
receipts
~~~

File entries contain a normalized relative POSIX path, role, size, SHA-256,
media type, and bytes reference. Paths must be unique across roles after
normalization.

Canonicalization must:

- reject absolute paths, traversal, symlinks, hardlinks, devices, sockets, and
  case-folded collisions;
- decode text as strict UTF-8;
- remove a UTF-8 BOM;
- convert CRLF and bare CR to LF;
- require exactly one terminal LF for text files;
- enforce per-role file and byte limits;
- keep tests and references private and absent from training rows;
- give repeated Catch2/scaffold assets one content-addressed support role;
- compute all digests only after normalization.

Canonical roots and receipts are immutable. New evidence creates a new
fingerprinted stage record rather than modifying an admitted record in place.

## C++17 Scaffold And Tests

The repo owns one C++17 CMake/Catch2 scaffold for translated tasks. The
pipeline standardizes all admitted tests on one pinned, content-addressed
Catch2 identity.

When adapting an older Catch suite, the migration must preserve test semantics.
The receipt must show the original and migrated reference outcomes and exercise
representative negative mutants. A mechanically converted suite is not trusted
merely because the reference passes.

Test requirements:

- at least one positive discovered test;
- meaningful happy-path, boundary, invalid-input, and state-transition cases
  when applicable;
- no network or wall-clock dependence;
- deterministic randomness with a pinned seed;
- approximate matchers or explicit epsilon bounds for floating-point results;
- no exact floating-point assertions whose result can vary by optimizer, CPU,
  standard library, or libc;
- complete private tests remain in the grader even when a prompt style shows a
  representative subset.

The CMake configuration and build commands are repo-owned. Generated tasks may
not replace them.

## Executable Admission Gates

Every candidate runs in a unique scratch directory such as
/tmp/w8-biayn-grader/<task-id>-<attempt-uuid>/. Concurrent attempts may not
share a writable build tree, object cache, CMake cache, or generated file.

The pinned network-disabled Docker grader must:

1. configure and compile the starter;
2. discover a positive Catch2 test count;
3. prove the starter does not already satisfy the complete task;
4. configure and compile the reference in a clean normal build;
5. discover and run the complete normal test suite;
6. configure and compile the reference in a fresh ASan/UBSan build;
7. independently discover and run the complete sanitizer suite;
8. require matching positive normal and sanitizer test counts;
9. reject sanitizer findings, timeouts, crashes, and nondeterminism;
10. apply the rendered whole-file target to a fresh starter workspace;
11. require byte equality with the canonical reference;
12. rerun the complete normal and sanitizer gates on the applied target.

Compile the exercise target separately from test discovery. Compiler warnings
belong on stderr and must not corrupt machine-readable discovery output.
Discovery acceptance is based on a successfully parsed positive Catch2 test
list, process completion without signal or timeout, and the pinned runner's
documented status policy. The exit code is recorded but must not be compared to
the parsed test count.

Receipts bind the task tree, reference mapping, grader image, compiler,
generator, Catch2, sanitizer flags, effective isolation policy, commands,
environment, test names/counts, exit statuses, durations, and stdout/stderr
hashes. A changed binding invalidates reuse.

## Sandbox Policy

Untrusted or generated C++ executes only with:

- network disabled;
- a read-only root filesystem;
- a non-root user;
- no-new-privileges;
- all capabilities dropped;
- the pinned seccomp profile;
- explicit CPU, memory, PID, file-size, output-size, and wall-time limits;
- one private writable scratch mount;
- no credentials, Docker socket, model cache, repository .git, or unrelated
  host mounts.

Task and provider data must be passed as argv/data, never interpolated shell.
The receipt records the effective isolation settings. Requested flags alone
are insufficient evidence.

## Contamination, Duplication, And Family Isolation

Contamination screening operates on instructions, public APIs, starter code,
reference code, and tests. It uses role-aware exact hashes plus normalized
lexical and AST representations.

The C++ normalizer must:

- strip comments and formatting;
- remove allowlisted standard includes and scaffold boilerplate from semantic
  comparison;
- normalize literals where appropriate;
- map user-defined variables, functions, and types to stable placeholders;
- preserve control flow, call structure, operators, public API shape, and
  distinctive constants;
- emit a versioned normalized representation and parse status.

Compare exact normalized hashes, token shingles, AST features, semantic
instruction features, and distinctive test cases. A parse failure is a
blocking error, not permission to fall back silently to a weaker check.

Shared Catch2 and repo-owned scaffold matches are excluded only when their
roles and digests match the allowlist. Task-authored tests, instructions,
starter, and reference content remain semantic evidence.

The pipeline maintains a global family index across the current pool and
released dataset versions. Exact duplicates are rejected automatically.
Near-matches and ambiguous family relationships require fingerprint-bound
human review. No family may cross train, validation, internal test, or the
official holdout.

## Code-Only Response Contract

Assistant targets contain complete editable-file blocks only. They must not
contain reasoning tags, plans, explanations, summaries, tool commentary, or
other prose before, between, or after the file blocks.

The accepted assistant target is:

~~~~text
path/to/file.h
~~~cpp
complete file bytes
~~~

path/to/file.cpp
~~~cpp
complete file bytes
~~~
~~~~

Every editable file appears exactly once in lexicographic normalized-path
order. The parser rejects missing, additional, duplicate, or undeclared paths;
non-C++ fences; reasoning tags; prose outside file contents; unclosed fences;
and content after the final closing fence.

The pinned assistant-turn terminator is the only decoding stop token. It occurs
after the final closing fence and is part of the locked tokenizer/template
contract. Fence text and file contents are never stop tokens.

This is a response-format constraint, not a claim about a model's internal
computation. Dataset rows supervise only the final editable-file state, and the
chat-template kwargs must not request or emit a separate reasoning channel.

## Prompt Styles

Every selected train root renders exactly one row for each style:

1. **standard_instructions**: translated instructions plus starter files.
2. **incomplete_stub**: an admitted incomplete implementation and a request to
   complete it.
3. **tdd_subset**: a deterministic representative subset of public-facing
   tests.
4. **compiler_repair**: an admitted broken starter plus sanitized compiler
   diagnostics.
5. **test_repair**: an admitted wrong starter plus sanitized failing-test
   output.
6. **header_to_source**: declarations and a request for the corresponding
   source implementation, or an equivalent file-boundary task for roots
   without a natural header/source split.

Styles 2, 4, and 5 require deterministic defective variants. Each defect must
be generated before rendering, fail for the intended reason, and be repaired
exactly by the canonical reference. Compiler/test diagnostics must be captured
from the pinned grader and stripped of absolute paths, hidden-test content,
timestamps, addresses, and nondeterministic data.

The TDD style includes three to five representative tests selected by a
deterministic policy. It must state that additional tests are omitted. The
private grader still runs the complete suite. Test pruning changes prompt
visibility only and never weakens admission.

Instruction examples that contain Markdown fences must be parsed structurally
and re-rendered with a non-conflicting delimiter. Escaping must ensure that the
whole-file parser can identify only formal assistant file blocks as edits.

All six styles preserve one root and family ID. Dataset reports must present
both row counts and unique root/family counts.

## SFT Row Contract

Rows are final-answer-only raw message lists:

~~~json
{
  "schema_version": "aider-sft-row-v2",
  "task_id": "...",
  "root_id": "...",
  "family_id": "...",
  "prompt_style": "compiler_repair",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "metadata": {
    "format": "aider-whole",
    "language": "cpp",
    "language_standard": "c++17",
    "profile": "aider-sft-hybrid-3000-v1",
    "response_format": "code-only",
    "split": "train"
  }
}
~~~

The user message contains instructions, permitted diagnostics or representative
tests for its style, and the editable starter state. It contains no reference,
hidden test, private path, benchmark identifier, or internal receipt.

The assistant message contains exactly one complete fenced block for every
editable file, ordered by lexicographic normalized path. It contains no
reasoning, prose, or commentary outside those file blocks. Applying it to the
starter must reproduce the reference bytes exactly.

Multi-file tasks must remain coherent: declarations and definitions are not
duplicated, every required editable file appears exactly once, and no context,
test, scaffold, or undeclared path is emitted.

## Tokenization And Loss

Every row is rendered with the exact pinned tokenizer, chat template,
Transformers version, Jinja version, model family, and template kwargs used by
the SLIME consumer. The repo-owned adapter receives raw messages;
dataset-loader --apply-chat-template is forbidden.

No row may exceed 8,192 rendered tokens. Truncation is forbidden. Rows that do
not fit must be compacted through the deterministic prompt policy or rejected
and replaced before split finalization.

The token ledger records, per row:

- raw message hash;
- rendered byte and token hashes;
- token IDs or a reproducible token reference;
- assistant prefix/body/terminal spans;
- binary assistant loss mask;
- structural token weights;
- active and total token counts;
- tokenizer, template, kwargs, adapter, and policy identities.

Assistant turn-header tokens have mask 0. User and system tokens have mask 0.
Assistant filenames, fences, code-body tokens, and the formal terminal turn
token have mask 1. No other template prefix token receives loss.

w8-aider-sft-mask-v2 assigns structural weights only within active assistant
tokens:

- C++ bytes inside file fences: 2.5;
- filenames, fence markers, separators, and terminal structure: 0.5.

The implementation must align weights to tokenizer boundaries and document the
policy for tokens spanning structural regions. If the pinned SLIME/Megatron
path cannot consume these weights exactly, the profile is not releasable; do
not add a custom trainer or silently reduce the policy to a binary mask.

Producer verification recomputes every token and weight record. Consumer
verification repeats the computation from only the sanitized export and fails
on any sequence, mask, weight, or identity drift.

## Split Selection And Candidate Swapping

The split solver operates on family groups and deterministic seed material. It
selects 500 train roots and at least 24 roots for each evaluation split, then
records remaining eligible roots as ordered standbys.

Selection priorities are:

1. permanent holdout and family isolation;
2. exact train-row target;
3. category minimums;
4. difficulty coverage;
5. proportional use of the eligible pool;
6. provenance and API-surface diversity;
7. deterministic tie-breaking by stable task ID.

If a selected root fails a late task-scoped gate, the solver may replace only
that root or its indivisible family with the first compatible reviewed standby.
Unchanged root-level approvals remain valid. The changed split fingerprint,
token ledger, manifest, and release subject require new split/release approval.
No approval may be carried across changed evidence merely because most roots
are unchanged.

Run-level failures such as a missing tokenizer or unavailable Docker daemon do
not reject roots or mutate the frozen split. They leave the run incomplete
until the environment is restored.

## Human Review

Mechanical work may run automatically, but these scopes require an authorized,
fingerprint-bound human decision:

- harvested seed inventory and license classification;
- provider usage terms and paid-call policy;
- every release-eligible translated root's semantic fidelity, language
  consistency, readability, and category/difficulty labels;
- every contamination near-match and family ambiguity;
- the exact selected split and standby ordering;
- the exact final release package.

A decision records scope, subject hash, reviewer identity, decision, timestamp,
and comment. It applies only to its exact subject. Changed source bytes,
provider identity, prompt, response, canonicalization, grader evidence,
contamination result, split, renderer, or token ledger make the affected
decision stale.

Review exports contain the evidence needed for that scope but never provider
credentials or hidden benchmark assets. Review imports validate authorization,
schema, scope, and subject fingerprints before changing state.

## CLI Contract

All material pipeline operations live under w8-biayn data aider-sft:

~~~bash
# No-spend planning and immutable identity proposal.
uv run --extra aider-sft w8-biayn data aider-sft plan \
  --config configs/aider_sft/hybrid-3000-v1.toml

# Deterministic source inventory and license review material.
uv run --extra aider-sft w8-biayn data aider-sft harvest-seeds \
  --config configs/aider_sft/hybrid-3000-v1.toml \
  --out .w8-biayn/data/aider-sft-hybrid-3000-v1

# One resumable translation unit; batch orchestration invokes this command.
uv run --extra aider-sft w8-biayn data aider-sft translate-seed \
  --root .w8-biayn/data/aider-sft-hybrid-3000-v1 \
  --seed-id <seed-id> \
  --acknowledge-paid-llm-calls

# Export/import scope-specific human decisions.
uv run --extra aider-sft w8-biayn data aider-sft review export \
  --root .w8-biayn/data/aider-sft-hybrid-3000-v1 \
  --scope <scope> \
  --out <review.json>
uv run --extra aider-sft w8-biayn data aider-sft review import \
  --root .w8-biayn/data/aider-sft-hybrid-3000-v1 \
  --decisions <decisions.json>

# Render, split, reconcile, and write readiness after release approval.
uv run --extra aider-sft w8-biayn data aider-sft finalize \
  --root .w8-biayn/data/aider-sft-hybrid-3000-v1

# Full producer verification.
uv run --extra aider-sft w8-biayn data aider-sft verify \
  --root .w8-biayn/data/aider-sft-hybrid-3000-v1

# Private-asset-free SLIME handoff and consumer verification.
uv run --extra aider-sft w8-biayn data aider-sft export \
  --root .w8-biayn/data/aider-sft-hybrid-3000-v1 \
  --format slime-sft \
  --out .w8-biayn/data/aider-sft-hybrid-3000-v1-slime
uv run --extra aider-sft w8-biayn data aider-sft verify-export \
  --root .w8-biayn/data/aider-sft-hybrid-3000-v1-slime
~~~

plan, harvest-seeds, review export, verify, and verify-export are no-spend.
Paid commands must refuse to run without explicit acknowledgement and frozen
budgets. Every command prints safe paths, counts, and status; it must not print
credentials, hidden test bodies, references, or raw provider output.

The CLI names above are normative. Until they exist with the specified
behavior, the V2 profile remains unimplemented.

## State, Resume, And Concurrency

Mutable state lives in a sibling .state/ directory. The final producer root and
sanitized export are immutable after readiness.

Resume rules:

- write stage receipts atomically after successful completion;
- append candidate, provider-call, admission, and rejection ledgers
  incrementally;
- reuse evidence only when its complete input and policy fingerprints match;
- restart only incomplete or stale stages;
- reserve provider request IDs before dispatch and reconcile ambiguous calls
  before retrying;
- never repeat a possibly billed request blindly;
- invalidate dependent evidence after source, toolchain, grader, renderer,
  tokenizer, or policy drift;
- use one dataset writer lock and deterministic aggregation order;
- use private per-attempt grader workspaces for parallel workers;
- never overwrite a differing ready root with --force.

The random attempt UUID isolates scratch paths and is not part of dataset
identity. Stable task IDs, sorted aggregation, and content hashes determine
released bytes.

## Output Layout

The producer bundle contains public training data and private evidence:

~~~text
.w8-biayn/data/aider-sft-hybrid-3000-v1/
  config.lock.json
  dataset-card.md
  NOTICE
  manifest.json
  readiness.json
  inventories/
    seeds.jsonl
    licenses.jsonl
  tasks/
    <task-id>/
      canonical.json
      public/
      private/
  receipts/
    generation.jsonl
    admission.jsonl
    contamination.jsonl
    reviews.jsonl
  splits/
    selected.json
    standbys.json
  sft/
    train.jsonl
    token-records.jsonl
  eval/
    validation.jsonl
    internal-test.jsonl
  private/
    references/
    tests/
~~~

The sanitized export contains only assets required by the SLIME consumer:

~~~text
.w8-biayn/data/aider-sft-hybrid-3000-v1-slime/
  dataset-card.md
  NOTICE
  manifest.json
  consumer-readiness.json
  train.jsonl
  token-records.jsonl
  tokenizer/
  adapter-policy.json
~~~

It must contain no references, hidden tests, provider responses, review
comments, private source assets, or credentials. Validation and internal-test
prompts may be exported only through a separately reviewed evaluation bundle
that contains no answers.

## Readiness

readiness.json is written only after finalize and removed whenever a blocking
claim becomes stale. It binds at minimum:

- profile, contract, schema, and content IDs;
- exact root, family, category, difficulty, split, and row counts;
- the 500-root to 3,000-row mapping;
- source, seed, license, provider, and prompt identities;
- canonicalization, scaffold, Catch2, grader, compiler, and sandbox identities;
- contamination normalizer and benchmark manifest identities;
- code-only response-format and parser-policy hashes;
- split, standby, reviewer-policy, and final release approval subjects;
- row, token-record, loss-mask, loss-weight, and manifest hashes;
- tokenizer, template, kwargs, adapter, sequence-length, and terminal-token
  identities;
- rejection and replacement summaries;
- producer verification status and timestamp.

Producer verify must recompute manifests, counts, hashes, split/family
constraints, row application, token evidence, review subjects, and readiness.
It may rerun private oracles only in external scratch and must not mutate a
ready root.

Consumer verify-export must use only sanitized bytes. It reconciles the export
manifest, requires raw two-message rows, recomputes all token/mask/weight
evidence, checks exactly 3,000 rows from 500 roots with six styles each, and
validates the pinned SLIME adapter contract. It does not claim to rerun private
source oracles.

Training wrappers must reject absent or stale consumer readiness, mismatched
model/tokenizer/template/adapter identities, sequence drift, implicit loss
masking, unsupported structural weights, dataset-loader chat templating, and
auto-preparation that would mutate the verified bundle.

## Stable Failure Classes

The implementation must define stable machine-readable reason codes:

~~~text
profile_not_frozen
source_identity_mismatch
seed_inventory_review_stale
license_missing
license_not_allowed
benchmark_id_overlap
benchmark_content_overlap
duplicate_task
duplicate_family
family_split_conflict
translation_schema_error
language_residue
unsafe_path
normalization_failed
generated_build_metadata_rejected
header_source_incoherent
starter_already_passes
reference_compile_failed
test_discovery_failed
zero_tests
reference_tests_failed
reference_sanitizer_failed
sanitizer_test_count_mismatch
floating_point_test_policy_failed
systematic_translation_failure
contamination_normalizer_error
contamination_review_required
non_file_output_rejected
whole_format_failed
target_reference_mismatch
prompt_fence_collision
token_overflow
loss_policy_mismatch
eligible_pool_shortfall
split_constraint_unsatisfied
standby_exhausted
human_review_stale
dataset_release_review_stale
consumer_manifest_mismatch
consumer_token_evidence_mismatch
consumer_adapter_mismatch
~~~

Candidate-content failures are terminal for that candidate. Provider transport
and storage interruption are retryable within frozen budgets. Missing runtime
identity, systematic failure tripwires, pool/split shortfall, stale review, and
consumer mismatch make the run incomplete; they do not relabel failed content
as accepted.

## Required Tests

The no-spend test suite must cover:

- config, schema, lock, and reason-code validation;
- exact upstream commits, clean-tree enforcement, inventory determinism, and
  license allowlist behavior;
- benchmark slug and semantic contamination across every source language;
- bilingual instruction translation and language-residue rejection;
- structural variant and family identity rules;
- UTF-8/BOM/newline/path normalization and collision rejection;
- header/source coherence and readable C++17 scaffold constraints;
- Catch2 migration parity, positive discovery, warning separation, and status
  handling;
- separate normal and sanitizer builds with equal test counts;
- floating-point assertion policy and deterministic tests;
- isolated concurrent workspaces and stable aggregation;
- mocked provider schema, budget, redaction, request reconciliation, retries,
  and three-failure tripwire;
- role-aware lexical/AST normalization, boilerplate exclusion, exact matches,
  near-match review, and parser failure;
- deterministic 500/>=24/>=24 family-safe selection, category minimums,
  standby ordering, and local candidate replacement;
- review persistence for unchanged roots and staleness for changed split and
  release subjects;
- all six prompt styles, defective-variant intent, diagnostic sanitization,
  representative test pruning, and prompt-fence isolation;
- rejection of reasoning tags, plans, prose, and trailing content, plus exact
  terminal-stop placement after the final file block;
- exact whole-file parsing and application for single- and multi-file roots;
- 8,192-token rejection without truncation;
- assistant-prefix masking, terminal-token loss, structural weights, and token
  boundary alignment;
- exact 500-root/3,000-row reconciliation;
- interrupted resume without duplicate paid calls;
- immutable producer verification and private-asset-free export verification;
- SLIME rejection of chat-template, token, mask, weight, sequence, adapter, and
  readiness drift;
- an end-to-end fixture with no live provider or network dependency.

Unit tests must never spend money. Docker integration tests may skip with an
explicit prerequisite message, but a real release cannot be ready without its
Docker evidence.

Run the repository validation suite after implementation changes:

~~~bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/w8-biayn-framework
~~~

## Implementation Order

Implement V2 in this order:

1. profile/config/schema and immutable identity contracts;
2. pinned source registry, shared benchmark manifest, and license inventory;
3. canonicalization and family index;
4. repo-owned C++17/Catch2 scaffold and Docker oracle;
5. mocked bilingual translation with strict provider boundaries;
6. contamination normalizer and review surface;
7. six prompt styles and deterministic defective variants;
8. strict code-only target parser;
9. tokenizer, mask, structural-weight, and 8,192-token admission;
10. family-safe split, standby replacement, and review invalidation;
11. immutable finalization, producer verification, sanitized export, and
    consumer verification;
12. thin SLIME handoff with auto-prepare disabled.

Do not begin paid translation until local fixtures prove canonicalization,
grading, contamination, rendering, tokenization, resume, and review behavior.

## Definition Of Done

The profile is implemented only when:

1. every normative CLI command exists with no-spend plan/verify paths;
2. all upstream, license, provider, grader, tokenizer, and policy identities
   are exact and review-bound;
3. at least 625 distinct release-eligible roots pass full C++17 normal and
   sanitizer admission;
4. benchmark contamination and family leakage are absent;
5. the reviewed split contains 500 train roots and at least 24 roots in each
   answer-free evaluation split with required category coverage;
6. every selected train root renders six parser-valid styles for exactly 3,000
   rows and every target reapplies to the reference bytes;
7. every row fits 8,192 tokens without truncation and has recomputable mask and
   structural-weight evidence;
8. every assistant response is code-only, rejects reasoning-channel text or
   other prose, and terminates only after the final file block;
9. late replacement changes only the affected family while correctly
   invalidating split and release approval subjects;
10. an offline producer verification succeeds without mutating the ready root;
11. a private-asset-free export passes independent consumer verification;
12. the SLIME lane rejects identity or evidence drift and consumes only raw
    messages through the pinned adapter;
13. tests, lint, compile checks, and skill validation pass;
14. no training, target-model response collection, benchmark result, or uplift
    claim is included in dataset readiness.

## Documentation Synchronization

When V2 implementation lands or any normative command, schema, count, source,
split, prompt, grader, tokenizer, review, output, or readiness rule changes,
update in the same logical change:

1. this document;
2. README.md;
3. ROADMAP.md;
4. .agents/REPO_GUIDE.md;
5. .agents/skills/w8-biayn-framework/SKILL.md;
6. the active GLM/Moonlight consumer documentation and wrappers;
7. tests enforcing the contract.

Keep AGENTS.md and CLAUDE.md as symlinks to .agents/REPO_GUIDE.md.
