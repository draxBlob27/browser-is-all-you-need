---
name: aider-task-family-remediation
description: Create, audit, remediate, regenerate, and locally verify clean-room Aider-format C++ task families for future SFT use. Use when analyzing Aider Polyglot C++ weakness topics, authoring curriculum subtopics, implementing generated task families, writing remedy records, or improving tasks under docs/aider-synthetic and .w8-biayn/data/aider-tasks.
---

# Aider Task-Family Remediation

Use this skill for the local, clean-room task-family workflow. Its terminal
state is `local_family_verified`; it does not create SFT rows, train a model,
or claim benchmark uplift.

## Read first

1. `AGENTS.md`
2. `README.md`
3. `ROADMAP.md`
4. `docs/AIDER_SFT_SCOPE.md`
5. `docs/AIDER_TASK_MATERIALIZATION_GUIDE.md`
6. `docs/aider-tasks-spec/Original-specs.md`
7. `docs/aider-tasks-spec/verify-and-remedy.md`
8. The relevant curriculum, family specification, generator, focused tests, and
   generated family root.

Read `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md` only when the user
explicitly requests a dataset release. It is not a local-family completion gate.

## Prompt selection is mandatory

For **every** generated Aider task-family request, inspect
`docs/aider-tasks-spec/prompts/` before planning or changing files. A prompt
named by the user is mandatory. Otherwise select the prompt whose phase matches
the requested work:

- curriculum or family-spec authoring: `generate-family-spec.md`;
- implementation, regeneration, audit remediation, or verification of an
  existing family: `implement-family-for-sft.md`.

Read the selected prompt completely and follow it together with this skill,
`AGENTS.md`, and the normative family specification. Do not treat prompts as
balanced-tree-specific. If more than one prompt materially applies or their
instructions conflict, stop before making changes and ask the user which
workflow controls the request; do not silently combine or weaken them.

## Lifecycle

### 1. Find the weakness topic

Start from evidence about a model or benchmark weakness. Record the topic,
observed limitation, benchmark-holdout boundary, and a clean-room learning
objective. Do not copy an official Aider Polyglot task's wording, API, tests,
reference, or semantic contract.

Use `docs/aider-synthetic/` for the curriculum source document. A topic is not
a task until it has an observable, independently testable capability.

### 2. Define subtopics and curriculum roots

Split the topic into materially different subtopics. For each proposed root,
define a domain-specific API, state model, invalid/duplicate/absent behavior,
ordering/tie rules, examples, and a private property that distinguishes the
claimed implementation from a trivial substitute.

State the number of roots in the curriculum document as a planning inventory,
not a release quota. Do not retain roots that are renamed copies of one
algorithmic contract. Keep official benchmark roots and semantic copies out of
the curriculum.

#### User-specified root counts and the hard diversity rule

A user-specified minimum or maximum family size is binding for the local
remediation. In particular, a request for at least 15 and at most 20 tasks must
materialize 15–20 roots before handoff; a smaller representative sample is not
an acceptable completion.

Count compliance never weakens semantic quality. Every counted root must differ
materially in both primary logic and implementation: public API, owned state or
algorithm, mutation/selection rules, invalid and boundary behavior, reference
control flow, deterministic oracle, and topic-specific negative fixture.
Domain renaming, method renaming, parameter changes, different constants,
opposite-end selection, or overflow-policy toggles do not establish a distinct
root. The curriculum, owner, focused tests, and duplicate-family screen must
encode the requested count bounds and fail closed if either the count or the
logic-and-implementation diversity requirement is violated.

Derive hard-rule evidence from the actual emitted docs, public API, reference
source, and tests, and compare every unordered pair in the counted family.
Unique task IDs, kind labels, declared signatures, and unequal raw source hashes
are not diversity evidence. Focused tests must prove the screen rejects at
least a domain/identifier-renamed clone, a constants-or-policy-only clone, and
an opposite-end-selection clone. Do not claim the hard rule was reverified if
those adversarial controls or the complete all-pairs comparison are absent.

#### Mandatory AI-agent re-verification after every change

Failure to comply with the hard diversity rule is a recurrent remediation
failure. Every AI agent that creates, changes, audits, or repairs a family must
reverify its own final changes against the hard rule. Do not rely on a prior
agent's conclusion, an earlier turn's receipt, a pre-change green test, or the
agent's intent. Re-verification is a completion gate, not optional review.

Treat all hard-rule evidence as stale after any change to a generator, case
inventory, scaffold, normalizer, curriculum contract, emitted docs/API,
reference, visible/private tests, negative fixture, focused test, or receipt
acceptance code. After the final such change, the responsible agent must:

1. Invalidate prior `local_family_verified` states, family screens, and Docker
   receipts through the owner-controlled path. Preserve and document the
   invalidated claim and why it no longer proves the current tree.
2. Regenerate the complete family through its owner, then reread the actual
   emitted artifacts. Do not infer compliance from case tables, profile labels,
   generator branches, IDs, intended mechanisms, or raw hashes.
3. Recompute the complete `n * (n - 1) / 2` unordered-pair screen. Require
   every pair to differ materially in each of the seven dimensions separately;
   the decision is conjunctive. An aggregate score, average, or a difference
   in only six dimensions cannot pass the hard rule.
4. Materialize genuine coherent controls from an emitted root for
   domain/identifier rename, constants-or-policy-only change, and opposite-end
   selection. Verify that each control changed the intended emitted files,
   remains internally consistent and buildable, and is rejected by the exact
   production evaluator. A no-op, broken, filename-inconsistent, or
   test-inconsistent mutation is not evidence.
5. Add independent focused assertions for the exact root and pair counts, the
   exact seven-dimension set, every per-dimension decision, nonempty control
   changes, and control rejection. A test that only calls the production helper
   and repeats its top-level `pass` value is circular and insufficient.
6. After the last owner or artifact-affecting edit, rerun the exact-tree,
   network-disabled Docker normal and fresh ASan/UBSan checks for every root
   and every coherent control required by the family. Reconcile generator,
   live-tree, archive/mount, reference, and receipt hashes.
7. Reopen the written screen, audit, remedy records, and receipt from disk.
   Confirm that they describe the final revision and that no record reached
   `local_family_verified` before all hard-rule and Docker gates passed.

Before handoff, answer all of these from recorded evidence: Did the last change
invalidate earlier proof? Did all counted pairs pass all seven dimensions?
Did each adversarial control really change files, remain coherent, compile,
and get rejected? Did independent tests inspect the decisions rather than
trust one helper? Does the final receipt bind the current tree and owner? If
any answer is no or unavailable, keep the family at `pending_execution` or
`not_completed` and state the blocker; never claim strict hard-rule alignment.

### 3. Implement the curriculum through its owner

Find the owning generator/materializer under `src/w8_biayn/integrations/` and
its focused test under `tests/`. Change those sources, not generated files.

For each root, generate:

- visible docs plus exactly the declared editable files;
- an incomplete but coherent starter;
- an independent reference;
- visible and private deterministic tests;
- role-correct config/provenance and a reproducible CMake recipe.

Regenerate beneath `.w8-biayn/data/aider-tasks/`, or beneath the parallel
`.w8-biayn/data/aider-tasks-reverify/` root when preserving an existing family.
Never hand-edit that output. Never hand-edit either generated output.

### 4. Audit and write remedies

Use `docs/aider-tasks-spec/verify-and-remedy.md`. Before changing an existing
family, write its per-root remedy record and specification under the sibling
`.state/remedy/` location required by that document.

A remedy must identify the root cause, one disposition, public contract,
representation/invariant, forbidden substitutes, independent reference,
negative fixture, metadata roles, oracle commands, and benchmark/family screen.

Use `reject` for benchmark overlap or unverifiable provenance, `replace` for a
trivial or duplicate objective, and `repair-in-place` only when the objective
survives.

### 5. Remediate and locally verify

Implement the remedy in the generator, scaffold, or focused tests; regenerate
fresh output; then verify:

1. prompt and file-role boundaries expose only docs plus declared editable files;
2. references map to every editable file and private assets remain hidden;
3. a mandatory network-disabled Docker sanity run builds and executes every
   reference in clean normal and fresh ASan/UBSan modes with positive, equal
   discovery counts;
4. private tests reject banned containers, sorted vectors, degenerate trees, or
   other named negative fixtures;
5. benchmark contamination and duplicate-family screening pass.

Record unavailable Docker or locked-runtime prerequisites as `not_completed`;
never upgrade a host-only result to Docker sanity or locked-oracle evidence.
A family cannot become `local_family_verified` until the mandatory Docker
sanity run passes.

### Toolchain and execution evidence

Run the owning generator's `--verify` mode before treating a generated family
as build-tested. It requires both `cmake` and `c++`; a focused Python
materialization test does not replace that oracle check.

#### Mandatory Docker sanity check

Every materialized or remediated C++ family must run its owner-controlled
normal and fresh ASan/UBSan reference verification inside Docker before
handoff. This check is mandatory even when the same verifier passes on the
host. Run with networking disabled, mount or archive the exact current
generated tree, require positive equal test-discovery counts in both modes,
and persist a receipt that binds the tree hashes, owner/generator hash,
reference hashes, image identity, compiler and CMake versions, commands, and
network policy.

Use the family-designated immutable grader image when its specification names
one. If a family has no designated locked grader yet, use the repository's
pinned C++ sanity image and label the result `docker_sanity`, not
`locked_oracle`. A diagnostic Docker image does not become admissible locked
evidence merely because it passes. If Docker, the required image, or permission
to run it is unavailable, record the exact blocked command and prerequisite as
`not_completed`; do not claim `local_family_verified`.

Use host CMake for quick iteration only when its installation is a documented
machine prerequisite. If it is missing, record the exact missing command and
use the project's designated locked C++ image when one is available. Run that
image with networking disabled, record its immutable image identity, compiler,
CMake version, and verifier command, and let the generator regenerate its own
output. Do not introduce a shell wrapper, substitute ad-hoc compile commands,
or report a container result as locked-oracle evidence unless the family
specification designates that image as the locked grader.

If neither a family-designated image nor the repository's pinned C++ sanity
image is available, leave Docker normal/sanitizer evidence `not_completed`.
Request the operator to provide the documented image or Docker access rather
than bypassing an interactive privilege boundary. Host CMake remains useful
for iteration but cannot satisfy this mandatory gate.

### Locked Docker receipts: snapshot-safe procedure

Treat a receipt's task-tree hash as a binding claim, not a progress marker.
Before accepting a locked normal/sanitizer result, compute the task-tree hash
in the owner and independently inside the Docker mount. Reject the result with
`grader_mount_hash_mismatch` if they differ. Never update a receipt merely
because test counts are positive.

Some agent environments run elevated Docker commands from a stale filesystem
snapshot. Symptoms are a passing Docker build with a receipt hash that differs
from the live generated root, or a privileged command appearing to use an old
owner module. Do not retry blindly and do not hand-edit the receipt. Instead:

1. Regenerate only through the owner; preserve the legacy tree.
2. Package the exact current task root into a deterministic temporary archive.
3. Run the designated, network-disabled Docker grader directly against that
   archive. For long jobs, use an isolated detached container, poll its exit
   state, and retain the terminal log.
4. Have the current owner import the direct result only after validating the
   archive-mounted tree hash, immutable image, and equal positive normal and
   sanitizer discovery counts. Record the evidence source and Docker hash.
5. Re-audit every receipt against the current root after any regeneration;
   regenerating invalidates prior tree hashes.

Direct Docker evidence is valid only when it uses the family-designated image,
locked compiler/configuration, network-disabled sandbox, fresh normal and
ASan/UBSan builds, and owner-side digest/count validation. A detached
container with a nonzero exit is a failed verification, not partial success;
inspect its logs before changing generator code.

### Stateful trace and fixture lessons

For a stateful family, a structural probe and an in-order comparison do not by
themselves establish published behavior. The deterministic trace must use an
independent vector/value oracle and, after every operation, compare both the
return value and complete observable ordering. Include every trace operation
class, not only insert/remove. Derive generated trace inputs from each API's
domain: for example, a bounded score task must not expect insertion of values
outside its documented range.

When a locked grader exposes a trace failure, treat it as a generator/spec
defect before changing evidence state. Minimize it to the generated input
rule, fix the owner, regenerate, rerun core verification, and then invalidate
and refresh locked receipts. Negative fixtures must execute a rejection path;
compiling a fixture or grepping the good reference is not sufficient evidence
that a set/map/vector/dummy-node substitute fails.

### Semantic-screen lessons

Whole-slug screening is necessary but not sufficient. When a bound upstream
checkout is available, normalize both candidate and holdout docs/APIs/source/
tests (remove comments, strings, literals, and clean-room domain nouns while
preserving API arity, control flow, invariants, and assertions). Screen all
bound holdouts and all proposed roots; record the normalizer version, source
inventory, comparison scope, and strongest result. If holdout content is not
available, record semantic screening as `not_completed` rather than `pass`.

### Failure patterns and recoveries

Treat these observed remediation failures as fail-closed checks:

- Reject a family built from one superset state object, shared generic
  reference, or policy-switch template whose roots merely expose different
  names or subsets. Give each counted root its own necessary state,
  topic-specific control flow, oracle, and negative fixture. Reject weak roots
  instead of padding a requested count with toggles or renamed variants.
- Never derive diversity proof from declared mode names, signatures containing
  task IDs, or hashes of source that still contains unique names and strings.
  Compare normalized emitted docs, public API, reference control flow, visible
  tests, private tests, and oracle logic. Keep deliberately wrong substitutes
  out of candidate-to-candidate similarity input so they cannot manufacture
  apparent diversity.
- Make deterministic traces exercise every public operation class and compare
  complete profile-specific observable state after every step. A generic map
  model or an operation selector that silently substitutes another store for a
  profile-only operation is incomplete oracle evidence.
- Build each false substitute under the same strict flags as the reference,
  then prove that the designated tests execute and reject it. A marker grep,
  source inspection, failure to compile, or an unused-variable warning is not
  negative-fixture evidence.
- Keep generated C++17 clean under the verifier's exact warning policy. Use
  explicit boolean conversion for optional-like values, initialize every
  aggregate field, avoid non-standard integer extensions under `-Wpedantic`,
  and compile negative fixtures without warnings before evaluating their test
  failure.
- Distinguish successful test execution from successful evidence import. Do
  not claim verification until the owner validates and writes the receipt and
  a second audit binds that receipt to the current live tree. Keep structural
  or semantic success at `pending_execution` until mandatory Docker normal,
  sanitizer, and executed-negative evidence all pass.
- Compute the mounted-tree digest independently inside Docker with the exact
  owner algorithm, including byte separators. Treat any mismatch as a failed
  receipt even when every test passed; fix the independent digest calculation
  or snapshot transport, then rerun the complete evidence path.
- Invalidate stale generated receipts and obsolete roots only through the
  owner-controlled force path. Before pruning, require matching provenance and
  refuse foreign or legacy roots. Never hand-edit, overwrite, or change
  ownership of generated evidence to get past a stale-file permission error.
- When the global `uv` cache is unreadable, use a task-specific cache under
  `/tmp`. When host CMake is absent, use the mandatory pinned Docker sanity
  path rather than inventing a compiler shortcut. When the sandbox denies the
  Docker socket, request the required execution permission and rerun the exact
  network-disabled command.
- Label a repository-pinned fallback image `docker_sanity` unless the family
  specification explicitly designates it as the locked grader. Bind the image,
  compiler path/version/hash, CMake version, exact command, owner and tree
  hashes, reference hashes, test counts, negative outcomes, and network policy
  in the receipt. Regenerate all evidence after any owner, wrapper, case, or
  generated-tree change.

Record rejected proposals separately from counted roots. Withdraw any earlier
overclaim explicitly when a re-audit disproves it; changing a manifest status
without documenting the invalidated evidence is not remediation.

## Guardrails

- Never modify generated task output by hand.
- Never create JSONL, token/mask evidence, splits, exports, or model-facing
  bundles in this workflow.
- Never claim SFT admission, training authorization, or benchmark uplift.
- Keep references, tests, metadata, CMake files, and receipts out of prompts.
- Update the curriculum/specification and focused regression test in the same
  logical change as the owning generator.
- Record the selected prompt path and any user-supplied inputs in the audit or
  remedy record so the workflow is reproducible.
- Treat an official Aider Polyglot C++ root as a permanent holdout.
- Treat explicit user root-count bounds as acceptance gates, never as optional
  planning targets; satisfy them only with roots that pass the hard diversity
  rule above.

## Handoff

Update the curriculum/specification with before/after tree hashes, changed
owner paths, remedy disposition, oracle receipt status/counts,
benchmark/family-screen result, prompt-boundary result, and the strongest
truthful local status. Future dataset construction must use a separate,
explicitly authorized intake process and may consume only
`local_family_verified` roots.

## Validation

Run the family’s focused tests, then:

```bash
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

Also run the owning generator’s structural test and its normal/sanitizer
verifier in the mandatory network-disabled Docker sanity environment. Missing
Docker access or the required image blocks `local_family_verified`.
