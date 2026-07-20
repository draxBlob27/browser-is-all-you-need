# Priority Queue Family Remediation and Reverification

## Scope

This audit covers all 20 legacy roots at
`.w8-biayn/data/aider-tasks/aider-dsa/priority-queue/` and their clean-room v2
replacements at `.w8-biayn/data/aider-tasks-reverify/aider-dsa/priority-queue/`.
The controlling prompt is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`; family type is
`aider-dsa`. The legacy tree is immutable audit input.

## Findings

### PQ-F1 — advertised priority queue absent

**Severity:** major. **Scope:** every legacy root.

Every legacy reference stores entries in the same `std::unordered_map` and
selects the winner with a complete linear scan. No heap or other advertised
priority representation exists. Compiling examples cannot upgrade the primary
core objective. **Disposition:** replace all roots.

### PQ-F2 — rename-only family duplication

**Severity:** major. **Scope:** every legacy root.

The legacy public state model, operation sequence, failure rules, reference
control flow, visible test, and hidden trace are one template. Only classes,
methods, nouns, and key prose vary. This violates the hard implementation and
logic diversity rule. **Disposition:** replace with the 20 one-to-one
mechanisms in the curriculum table.

### PQ-F3 — private discriminator absent

**Severity:** major. **Scope:** every legacy root.

Legacy tests check bounded behavior and a few selections but never reject the
linear scan or prove a heap/bucket/tree/meld invariant. V2 requires a mechanism
marker, algorithm-specific source tokens, runtime representation checks, and
focused negative fixtures that execute the rejection path for library heap,
rename-only, and missing-invariant substitutes.

### PQ-F4 — hidden traces were not independent stateful oracles

**Severity:** major. **Scope:** the initial v2 draft.

The first hidden tests exercised long sequences but did not independently
model every public operation or compare the complete observable ordering after
each mutation. V2 now owns 20 distinct deterministic value-model traces. Each
trace covers every mutation/selection class, checks each return, drains a copy
against the model after every operation, and checks public counts/accessors and
the representation invariant. The owner rejects duplicate or incomplete
oracle profiles.

### PQ-F5 — negative and receipt evidence was too weak

**Severity:** major. **Scope:** the initial v2 draft.

One generic negative check and a receipt containing only counts could not prove
the hard rule per root. Every root now materializes a different topic-specific
bad substitute and the core verifier must execute its expected rejection path.
The locked receipt binds every task tree and reference hash, both owner-source
hashes, the immutable image/compiler/CMake identities, network isolation, and
the exact configure/build/discover/execute commands for normal and sanitizer
modes.

### PQ-F6 — package delivery was a sorted-vector pseudo interval heap

**Severity:** major. **Scope:** `pq-package-delivery` in the initial v2 draft.

The earlier implementation rebuilt ordered storage and scanned for an extreme;
its interval-heap label did not match its control flow. It is replaced with an
incremental single-array min-max heap using alternating levels, grandparent
bubbling, and min/max trickle-down. Its trace independently removes the full
model from both ends after every operation, and its negative fixture rejects
two independent heaps.

## Per-root disposition

Every legacy task has disposition `replace`. The binding mechanism and public
contract live in its Markdown/JSON pair under the v2 family's
`.state/remedy/`. There are no `repair-in-place` roots: retaining the old
objective would preserve a semantic duplicate.

## Verification commands

```bash
uv run pytest -q tests/test_moonlight_priority_queue_aider_tasks.py
bash examples/slime/moonlight_cpp_perf/prepare_priority_queue_aider_tasks.sh --force --verify-core
bash examples/slime/moonlight_cpp_perf/prepare_priority_queue_aider_tasks.sh --force --verify
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

The core verifier checks owner regeneration, prompt/file-role boundaries,
reference mapping, exact whole-file targets, 20 unique mechanism/signature,
oracle, and negative-fixture profiles, pairwise normalized-token similarity,
executed per-root rejection fixtures, and benchmark whole-slug/content
separation. The oracle verifier configures explicit Unix Makefiles and
separately discovers and executes positive normal and fresh ASan/UBSan tests
for every root.

## Status rule

Host normal/sanitizer results are recorded as host evidence only. A root reaches
`local_family_verified` only after the same owner verifier succeeds in the
family-designated immutable, network-disabled runtime and records equal
positive counts bound to the current task-tree/reference hashes, owner hashes,
and exact commands. No result creates dataset rows, training authorization,
release readiness, or benchmark uplift.
