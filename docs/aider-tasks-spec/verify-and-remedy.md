# Method for Verifying and Remedying Aider-Format C++ Tasks

## Purpose and scope

Use this method whenever a local Aider-format C++ task or task family is
reviewed for quality, training suitability, or possible use in a benchmark
uplift experiment. It applies to a single task, a generated curriculum, or a
candidate dataset inventory.

### Repository-wide primary requirement

This policy applies recursively to every current and future task beneath
`.w8-biayn/data/aider-tasks/` and to parallel remediation materializations
beneath `.w8-biayn/data/aider-tasks-reverify/`, regardless of topic, family,
generator, or directory depth.

The **primary task-content requirement** is that the implementation genuinely
implements the concept advertised by the task. The core representation,
algorithm, state transition, or systems mechanism named by the contract must
exist in the reference and must not be replaced by a standard-library,
third-party, precomputed, hard-coded, or renamed shortcut that performs the
substantive work. This is Priority 1 in every audit and remedy. A task has not
achieved its central goal when its files build and its examples pass but its
claimed implementation is absent.

This requirement is topic-independent. Examples include, but are not limited
to: a tree task owning and manipulating the required nodes and links; a graph
task implementing the required graph state and traversal/optimization; a heap
task performing its own heap maintenance rather than delegating to
`std::priority_queue`; a parser task implementing the specified lexical and
syntactic state rather than forwarding the problem to a general parser or one
regular expression; and a concurrency task implementing the stated
synchronization protocol rather than serializing away the claimed behavior.

Incidental standard-library use remains allowed when the task contract permits
it. Output vectors, temporary buffers/worklists, strings, ownership helpers,
and metadata lookups do not violate the primary requirement unless they replace
the claimed core representation or algorithm. For example, a real tree may
return a `std::vector` traversal; it may not use `std::set` as the tree being
taught.

All other local-remediation checks are **secondary requirements relative to
this primary content goal**. They still govern the strongest status that may be
claimed: correctness/oracle proof, prompt safety, benchmark separation,
provenance, metadata, documentation, and reproducibility are not waived merely
because the primary goal is achieved. Audit reports must therefore state two
facts separately: whether the primary core objective was achieved, and which
secondary completion gates remain open.

It is a review method for the current local task-authoring scope, not a route
to dataset release. Passing a local task audit does not create SFT rows,
authorize training, or establish uplift on an official benchmark. See
[`../AIDER_SFT_SCOPE.md`](../AIDER_SFT_SCOPE.md).

The method has five separate conclusions that must never be collapsed. The
first is the major task-content conclusion; the remaining conclusions are
secondary evidence and lifecycle conclusions:

| Conclusion | Meaning |
| --- | --- |
| **Core objective implemented (primary)** | The task genuinely implements the advertised representation, algorithm, state transition, or systems mechanism without delegating the substantive work to a forbidden substitute. |
| **Structurally valid** | Files, metadata, roles, and prompt-facing starter state are internally consistent. |
| **Oracle verified** | The reference answer passes the exact normal and sanitizer grader with positive test discovery. |
| **Training-suitable** | The task has meaningful, independent learning value and is not a template/contamination risk. |
| **No release claim** | Dataset admission is outside the current local task-authoring scope. |

None of these conclusions authorizes SFT rows, training, or a benchmark-uplift claim.

## Review principles

1. **Verify the core implementation before secondary polish.** A task called
   AVL, parser, graph, heap, dynamic program, scheduler, or concurrency system
   may still be a wrapper around a library facility or a trivial template.
   Inspect the owned state and substantive operations and record an explicit
   `primary_core_objective: achieved|not_achieved` result. Judge incidental
   containers by their role, not by token presence alone: an output/work buffer
   is acceptable, while a container or library call that replaces the claimed
   concept is not.
2. **Keep evidence levels explicit.** Static inspection, source-level tests,
   local builds, locked-image builds, and finalized-release evidence have
   different strengths. Never report a stronger result than the evidence.
3. **Review the family as well as each root.** A collection can have no broken
   files yet still be poor training data because its roots are near duplicates.
4. **Treat oracle code and tests as private.** They are legitimate audit input,
   but must not be copied into model prompts, model-facing rows, or public
   summaries that would expose hidden test contents.
5. **Fix causes rather than symptoms.** Renaming a task, adding an assertion,
   or changing a status string does not correct a weak task objective,
   contamination, or missing oracle proof.

## Evidence hierarchy and status language

Use the following wording in an audit report.

| Evidence available | Allowed statement | Forbidden statement |
| --- | --- | --- |
| Directory/file inspection only | “The task is structurally consistent/inconsistent.” | “The task passes its tests.” |
| Generator/unit test only | “The generator's structural test passed.” | “Every materialized reference passes.” |
| Clean local normal build | “The reference passed the recorded local normal build.” | “The task is sanitizer-verified or release-ready.” |
| Normal and sanitizer builds in the locked grader image | “The oracle passed the locked-image normal and sanitizer checks.” | “The task is admitted,” unless remaining gates passed. |
| Full finalized release plus producer verification | “The task is in a ready release.” | “The task proves benchmark uplift.” |

If a required tool, image, dependency, or credential is unavailable, record the
exact command, the blocking error, and the missing prerequisite. Mark that
check **not completed**, not failed and not passed. Do not silently replace a
locked-image check with a host build.

## Verification procedure

### Phase 0 — Establish scope and preserve inputs

1. Record the exact task directory or family root, revision/digest when
   available, review date, and requested purpose (local smoke, SFT candidate,
   or evaluation holdout).
2. Determine whether the artifact is generated. Find the repo-owned generator,
   materializer, manifest, and focused regression tests before inspecting
   outputs.
3. Do not edit a task while auditing it. A review report may be added
   separately; implementation changes require a follow-up change request.
4. Check the task's provenance/status metadata. “Local artifact” or “not
   admitted” is a boundary, not a cosmetic label.

### Phase 1 — Inventory and structural contract

For every root, inventory all files and compare them with the required
Aider-format shape:

```text
<task-id>/
├── .docs/                 # visible context, never editable
├── .meta/                 # provenance, references, hidden tests/fixtures
├── CMakeLists.txt          # build/grader recipe, never editable
├── <task-id>.h             # editable starter when listed in files.solution
├── <task-id>.cpp           # editable starter when listed in files.solution
└── visible-test source     # test role, never editable
```

Verify all of the following per task:

- `.meta/config.json` exists and declares `files.solution`, `files.test`, and
  `files.example`.
- Paths are unique, relative, safe, and exist. Reject absolute paths and
  `..` segments.
- `files.solution` contains every and only model-editable production file, in
  the intended response order.
- Tests, references, docs, metadata, fixtures, and build files are not in the
  editable list.
- Each declared reference maps unambiguously to its corresponding editable
  file and represents the complete correct state of that file.
- Documentation is sufficient to understand the public contract without
  exposing reference code or hidden tests.
- The starter is intentionally incomplete but coherent; it must not embed a
  hidden correct implementation.
- CMake uses C++17, strict warnings where supported, deterministic offline
  dependencies, and invokes visible plus hidden tests in the grader path.

For a generated family, also count expected roots, compare slugs with the
generator's declared task IDs, and run the focused materialization test. This
proves generator/output consistency only; it is not oracle proof.

### Phase 2 — Prompt and answer-boundary review

Construct or inspect the exact prompt path used by the task evaluator.

- Confirm that only documentation and declared starter solution files reach
  the user/model message.
- Confirm that references, hidden tests, provenance, CMake files, and support
  assets remain private.
- Confirm the answer parser accepts exactly one complete replacement for each
  editable file and rejects missing, duplicate, unknown, test, and build-file
  replacements.
- Confirm the target/reference state uses the same file order as
  `files.solution`.

This phase catches a common false result: a task may compile locally but train
the wrong behavior because the prompt hides needed API information or exposes
oracle material.

### Phase 3 — Oracle and grader proof

Run the repo-owned verifier or generator's verify mode, never an ad-hoc
substitute. In the required locked environment, it must:

1. configure a clean normal C++17 build with the locked compiler and explicit
   `Unix Makefiles` generator;
2. discover a positive test count;
3. compile and run the reference state against all visible and hidden tests;
4. configure a separate fresh ASan/UBSan build;
5. compile and run the reference again under sanitizer; and
6. retain receipts binding the task tree, reference mapping, compiler, grader
   image, generator, test framework, resource policy, and commands.

Record per-root outcomes. A single root that cannot build, has zero tests,
fails tests, or fails sanitizer is not oracle-verified. Do not infer that the
starter should build—the reference target is what this phase validates.

### Phase 4 — Primary core-objective, semantic-quality, and independence review

Read the instructions, public API, starter, reference, visible tests, and
hidden tests together. Evaluate the primary core objective first:

1. Name the exact representation, algorithm, state transition, or systems
   mechanism the task claims to teach.
2. Locate the owned implementation state and the operations that maintain or
   execute it in the reference.
3. Identify the forbidden shortcut that would make the claim false for this
   topic. Do not use a balanced-tree-only banned list for unrelated topics.
4. Distinguish incidental library use from delegation of the substantive work.
5. Record `primary_core_objective: achieved` only when source inspection and a
   deterministic discriminating check both support the claim. Otherwise record
   `not_achieved`; successful compilation or public examples cannot upgrade it.

Then ask the secondary semantic and independence questions.

| Question | Evidence of a quality problem | Appropriate remedy |
| --- | --- | --- |
| Does the implementation teach the advertised concept? | A task labelled tree/graph/parser/concurrent system delegates all meaningful work to an unrelated library or simple container. | Either implement and test the advertised concept, or rename/re-scope the task to the behavior it actually teaches. |
| Can a trivial or wrong implementation pass? | Tests assert only happy paths, one fixed trace, or externally identical results while omitting stated invariants. | Add discriminating boundary, mutation, adversarial, and property/invariant tests. |
| Is the task independent? | Different roots have the same state model, operation sequence, error rules, tests, and solution shape under new nouns. | Deduplicate; retain one representative; author replacements with materially different APIs, data, state transitions, and tests. |
| Does the task resemble a holdout? | Wording, API, test behavior, reference structure, or task semantics substantially match an official benchmark root. | Reject the candidate; do not repair it by renaming. Author a clean-room task from a different contract. |
| Is the task solvable from its prompt? | Required behavior is absent from docs/starter, or only hidden tests reveal selection/error rules. | Specify the contract in visible docs and API; retain hidden tests only for undisclosed cases, not undisclosed rules. |
| Is the solution target robust? | Reference hard-codes visible cases, has undefined behavior, relies on non-determinism, or violates its own API. | Rewrite the reference independently; add tests that rule out the shortcut; rerun oracle proof. |

For every topic, tests must establish the property actually claimed. A
balanced-tree task needs deterministic evidence of balancing or invariants that
distinguishes it from a sorted vector, `std::set`, or a degenerate BST. A heap,
graph, parser, dynamic-programming, concurrency, storage, or networking task
needs an equivalent topic-specific discriminator against its easiest false
substitute. If that implementation property is intentionally outside the
contract, rename and scope the task to the behavior it actually teaches rather
than claiming the stronger concept.

### Phase 5 — Local task and benchmark suitability

Before recommending a task for further local authoring, review it as part of its family:

- Screen contamination over instructions, APIs, starters, references, tests,
  and semantic/family near-matches—not only task names.
- Measure duplicate family capacity. A model should not receive many roots
  whose complete solution is the same algorithm with renamed types/methods.
- Verify provenance, usage terms, authoring method, and source inventory.
- Preserve private tests, references, metadata, build files, and receipts outside
  prompt-visible material.
- Do not create JSONL rows, releases, or consumer exports from local artifacts.
- Keep benchmark roots, related copies, and benchmark-derived task families out
  of the local curriculum.

## Finding format

Every finding in a task audit should be reproducible and actionable. Use this
template:

```markdown
### <ID> — <short title>

**Severity:** blocker | major | moderate | minor | note

**Scope:** <one task / named task list / every task in family>

**Observed evidence:** <paths, command, result, and only the minimum safe
description of private material>

**Why it matters:** <effect on correctness, learning value, contamination,
release eligibility, or validity of a benchmark claim>

**Root cause:** <the design or implementation condition that creates it>

**Remedy:** <specific task/code/test/metadata change, or explicit rejection>

**Verification after remedy:** <repo-owned command and acceptance condition>

**Status:** open | blocked by prerequisite | resolved and reverified
```

Severity meanings:

- **Blocker:** the task must not enter training/evaluation; examples include
  benchmark contamination, hidden-oracle exposure, failing reference, or no
  trustworthy behavior contract.
- **Major:** the task may build but does not genuinely implement or test its
  advertised core concept, or otherwise cannot support its advertised learning
  claim. Absence/delegation of the claimed representation, algorithm, state
  transition, or systems mechanism is always at least major and is the first
  remediation priority. Template duplication and testing a different concept
  from the label are also major.
- **Moderate:** an important test, boundary rule, provenance datum, or prompt
  detail is missing, but the task can be repaired without changing its central
  objective.
- **Minor:** clarity, diagnostics, naming, or maintainability issue that does
  not alter correctness or admission evidence.
- **Note:** verified context with no corrective action required.

## Remedy method

For every issue, select the smallest remedy that genuinely resolves the root
cause. Apply the following sequence.

1. **Implement the truthful core objective first.** Decide what representation,
   algorithm, state transition, or systems mechanism the task should teach and
   evaluate. Implement that substantive mechanism without a forbidden shortcut
   and add a deterministic discriminator. If the desired objective cannot be
   distinguished by a valid test, revise or reject it. Do not spend a remedy
   claiming completion from documentation, metadata, or receipt improvements
   while the advertised core implementation is still absent.
2. **Change contract before implementation.** Update the visible instructions,
   public API, error behavior, and examples so that a model can solve the task
   without secret requirements.
3. **Create an independent starter and reference.** The reference must satisfy
   the revised contract without relying on hidden shortcuts. The starter must
   be a valid incomplete state, not a copy of the answer.
4. **Strengthen tests.** Add visible behavior cases and private adversarial,
   invariant, regression, and randomized-oracle cases that reject the prior
   bad solution. Keep tests deterministic and offline.
5. **Update role metadata and provenance.** Make all solution/test/reference
   paths correct, record the authoring/source change, and update task-family
   membership as needed.
6. **Regenerate, do not hand-drift.** If the family is generated, change the
   repo-owned generator and its tests, then regenerate deterministically. Do
   not patch generated roots by hand without changing their source generator.
7. **Re-run the evidence ladder.** Run structural tests, then locked normal
   and sanitizer oracle checks, then the primary SFT release gates. A remedy is
   not complete until the finding's stated acceptance condition passes.

Some findings have only one valid remedy: reject the task. This applies to
official-benchmark copies, unresolvable license/provenance failures, and task
families whose core objective remains a near-duplicate of a holdout.

## Audit report structure

Write a report in `docs/aider-tasks-spec/<topic-name>.md` or an appropriate
subdirectory. It should contain:

1. scope, source paths, task count, and task IDs;
2. commands run and their exact outcomes;
3. a concise structural-verification matrix;
4. findings shared by the task family;
5. a per-task table that accounts for every reviewed root and gives a
   task-specific remedy or an explicit “no issue found” result;
6. remediation acceptance criteria and the next repo-owned verification
   commands; and
7. a conclusion that states the strongest conclusion actually supported by the
   evidence.

Avoid embedding full hidden tests, reference implementations, credentials, or
model outputs. Link to local source paths and summarize only the behavior
necessary to justify the finding.

## Final review checklist

- [ ] Scope, revision, purpose, and task count are recorded.
- [ ] Every task has been accounted for, including generated roots.
- [ ] Metadata/file-role checks and prompt-boundary checks are separate from
      runtime oracle proof.
- [ ] Commands, outcomes, prerequisites, and incomplete checks are explicit.
- [ ] Findings identify evidence, impact, root cause, remedy, and acceptance
      test.
- [ ] Family duplication and benchmark-contamination risks were assessed.
- [ ] Remedies change the task design/tests/reference as needed, not just its
      labels.
- [ ] No private oracle/test material has entered a model-facing artifact or
      the audit report.
- [ ] The report does not claim release readiness or benchmark uplift without
      the required independent evidence.

# Normative Deterministic Remedy Implementation Contract

This section is mandatory and supersedes the discretionary wording in “Remedy
method” when a task is changed. A remedy is a versioned implementation
contract with fixed inputs, one selected disposition, exact source files to
change, and machine-checkable acceptance evidence. It is not a list of possible
fixes or a label change.

## 1. Immutable remediation inputs

Before editing a root or generator, write one mutable record at
`<candidate-root>/.state/remedy/<task-id>.json`:

```json
{
  "schema_version": "aider-task-remedy-v1",
  "task_id": "<kebab-case task id>",
  "family_id_before": "<stable family id>",
  "tree_hash_before": "sha256:<hex>",
  "generator_path": "<repo-relative path or null>",
  "generator_revision": "<git revision or content hash>",
  "finding_ids": ["<sorted nonempty finding ids>"],
  "disposition": "reject|replace|repair-in-place",
  "benchmark_screen": "pass|reject|pending",
  "license_screen": "pass|reject|pending",
  "remedy_spec_path": "<repo-relative Markdown path>",
  "remedy_spec_hash": "sha256:<hex>",
  "status": "planned|implemented|verified|rejected"
}
```

Capture the task ID, pre-change tree hash, generator identity, and sorted
finding IDs before a source edit. A change to any captured field invalidates
the record and begins a new remedy version. `verified` is forbidden until all
section-6 gates pass.

## 2. Deterministic disposition rules

Select exactly one disposition using the first matching rule. There is no
partial-accept, rename-only, or fix-later disposition.

| First matching condition | Required disposition | Prohibited action |
| --- | --- | --- |
| Exact/semantic official-benchmark overlap, use of benchmark assets, or a holdout family divided across a training candidate | `reject` | Renaming, deleting one test, or retaining an SFT candidate. |
| Missing/unacceptable license or unverifiable authoring provenance | `reject` | Adding an unverified attribution string or deferring review. |
| Objective cannot be distinguished from a trivial/banned implementation by deterministic private tests | `replace` | Calling the old root repaired by comments/examples only. |
| Template/semantic duplicate of another selected root | `replace` for all but the lexicographically smallest independently justified representative | Retaining renamed duplicates. |
| Prompt rule, roles/provenance, starter/reference/CMake, or deterministic test is missing while the objective/API survives | `repair-in-place` | Changing generated output without its source generator/tests. |
| Only normal/sanitizer, renderer, token, release, or consumer evidence is absent after all earlier gates pass | `repair-in-place` | Marking ready from a host build/manual JSONL. |

`reject` removes the root from every candidate pool and split. `replace` assigns
a new task ID and family ID; it never overwrites the rejected/duplicate root.
`repair-in-place` retains the task ID and increments its task-spec revision.

## 3. Required per-root remedy specification

Before implementation, the Markdown file named by `remedy_spec_path` must
contain these headings in this exact order. Omission is the blocking reason
code `remedy_spec_incomplete`.

1. **Identity:** task ID, task-spec revision, family ID, disposition, source
   inventory ID, license result, generator path, and benchmark-screen result.
2. **Objective:** one observable capability. It must not claim an
   implementation property that private tests cannot establish.
3. **Public API:** complete C++17 declarations, namespace, editable-file order,
   value/payload types, ownership, and every signature.
4. **Behavior table:** for each method: valid input, successful result, invalid,
   duplicate, absent, and empty result, state mutation, ordering, tie breaking,
   overflow behavior, and one public boundary example.
5. **Implementation invariant:** exact required or permitted representation.
   A structural objective must name node/state fields, forbidden substitutes,
   and the private invariant predicate. A behavior-only objective must forbid
   the structure claim in docs, metadata, and reports.
6. **Starter and reference:** each editable file's intended incomplete state,
   independent reference design, and forbidden shortcuts/containers.
7. **Tests:** named public/private cases, every deterministic seed and operation
   mapping, behavior oracle, invariant/complexity bound, and named negative
   fixture for every prior root cause.
8. **Files and metadata:** exact role/path map, solution order,
   reference-to-solution mapping, config/provenance fields, and support digest.
9. **Build/oracle:** language standard, image/compiler/Catch identities, normal
   and sanitizer commands, expected positive test counts, and receipt fields.
10. **Family/contamination:** exact comparison set, normalizer version, family
    decision, and permanent-holdout result.
11. **Optional dataset handoff:** record `not_requested` for local remediation.
    Renderer, token/mask, producer, export, and consumer evidence are required
    only by a separately authorized dataset release.
12. **Acceptance:** exact commands, expected records, and stable failure codes
    for every deliberately bad substitution.

The balanced-tree curriculum specification in
`docs/aider-tasks-spec/aider-dsa/balanced-search-tree.md` is the minimum
acceptable specificity. “Add tests,” “make distinct,” or “use a real tree” is
noncompliant unless the precise API, invariant, test input, expected outcome,
and acceptance command are supplied.

## 4. Deterministic implementation sequence

Perform these steps in order for each root. A later step must not run when an
earlier step is incomplete or its inputs are stale.

1. **Freeze and classify:** write section-1 record; apply section-2 disposition;
   write rejection receipt and stop for `reject`.
2. **Specify:** complete section-3 spec, calculate its SHA-256, and bind it to
   the record. For a generated family, specify every retained/replacement root
   before changing the generator.
3. **Change owned source:** modify the generator/scaffold/config/renderer that
   owns the artifact and focused regression tests in the same change. Generate
   into fresh scratch and compare normalized tree hash with its output manifest.
4. **Implement prompt contract:** write docs, headers, coherent starters; build
   exact prompt and prove only docs plus `files.solution` are exposed.
5. **Implement independent reference:** do not import old-family renderers,
   benchmark assets, banned containers, hard-coded cases, or hidden fixtures.
6. **Implement tests:** add named public/private cases and one negative fixture
   per prior root cause; private invariant checks run after every mutation.
7. **Fix roles/provenance:** validate paths, mappings, source/license data,
   revisions, family ID, and benchmark separation; regenerate affected roots.
8. **Prove oracle:** run locked normal and fresh sanitizer builds; require
   nonzero equal discovery counts and a passing reference in both modes.
9. **Prove semantic admission:** run family/duplicate and benchmark screens;
   a near-match rejects/replaces the root and is never waived.
10. **Complete local remediation:** record prompt-boundary validation, normal and
    sanitizer evidence, benchmark/family screening, and `local_family_verified`.
    Dataset handoff remains `not_requested`.

## 5. Mandatory implementation checks

The owning implementation and focused tests must fail closed for every row in
this table.

| Deliberate substitution | Required failure |
| --- | --- |
| Omit an editable file, add an unknown file, or put prose outside whole-file blocks | Whole-file parser or target-application failure. |
| Put test/reference/docs/CMake in `files.solution` | Unsafe-path or role-conflict failure. |
| Reference fails to reproduce every declared solution file | Reference-map or target-reference mismatch. |
| Replace the claimed core representation, algorithm, state transition, or systems mechanism with a library shortcut, generic container, precomputed answer, hard-coded cases, degenerate implementation, or other topic-specific false substitute | Topic-specific private invariant, property, complexity, or adversarial failure. |
| Remove a public rule from docs while retaining it in private tests | Prompt-contract completeness failure. |
| Duplicate a root under new noun/API spelling | Duplicate-family failure. |
| Introduce benchmark slug/content/semantic contract | Benchmark-overlap failure and `reject` disposition. |
| Normal/sanitizer discovery is zero or counts differ | Oracle discovery/count-mismatch failure. |

Use existing primary-pipeline reason codes where applicable:
`benchmark_id_overlap`, `benchmark_content_overlap`, `duplicate_task`,
`duplicate_family`, `unsafe_path`, `header_source_incoherent`,
`reference_compile_failed`, `test_discovery_failed`, `zero_tests`,
`reference_tests_failed`, `reference_sanitizer_failed`,
`sanitizer_test_count_mismatch`, `whole_format_failed`,
`target_reference_mismatch`. Add and test these remedy-specific codes:
`remedy_spec_incomplete`, `prompt_contract_incomplete`,
`invariant_not_enforced`, `generator_output_drift`, and
`remedy_disposition_conflict`.

## 6. Completion state machine

Only these states and transitions are valid:

```text
unreviewed -> audited -> planned -> implemented -> oracle_verified
  -> semantically_admitted -> local_family_verified

planned -> rejected
implemented|oracle_verified|semantically_admitted|local_family_verified -> planned
```

Any change to source, generator, reference, tests, docs, metadata, compiler/image,
or contamination policy forces the root back to `planned`. A rejected root has
no outgoing transition. `local_family_verified` requires no dataset-release
artifact.

The transition from `planned` to `implemented` is forbidden unless the audit
records `primary_core_objective: achieved`. In other words, `implemented` means
the major advertised mechanism is present; it must not mean only that files
were generated, documentation was written, or a wrapper compiled. Oracle,
prompt-boundary, provenance, family, contamination, and reproducibility checks
remain secondary gates on later states and on `local_family_verified`.

## 7. Strict audit-report update requirement

The implementation change must update its audit report with
`primary_core_objective: achieved|not_achieved` and the exact source/test
evidence for that conclusion, followed separately by the before/after tree
hashes, remedy-spec hash, disposition, every changed source/generator/test path,
normal and sanitizer receipt IDs plus discovered counts, family/benchmark
screen result, prompt-boundary result, and the strongest truthful conclusion
from the five conclusion levels.

An open finding changes to “resolved and reverified” only after its named
negative fixture, locked oracle proof, semantic screen, and every required
downstream gate pass. “Fixed,” “looks good,” or a passing host build is not a
valid conclusion.
