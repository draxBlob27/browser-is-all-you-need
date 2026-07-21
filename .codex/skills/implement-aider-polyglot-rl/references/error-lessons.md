# Verified Error Lessons

Use this reference as the durable error-to-guidance ledger for the Aider RL
lane. Update it after fixing every error encountered while applying the skill.
Keep entries concise, reusable, and free of private task or grader material.

## Entry Format

### Short reusable lesson title

- **Symptom:** State the failing operation and sanitized error evidence.
- **Root cause:** State the verified cause, including the affected boundary.
- **Fix:** State the smallest change or operational response that resolved it.
- **Verification:** List the focused check and proportional regressions that
  passed afterward.
- **Reusable rule:** Write the imperative instruction future agents must
  follow to prevent, detect, or correctly handle recurrence.
- **Scope:** Name the versions, environment, or conditions to which the lesson
  applies.

## Maintenance Rules

- Record only verified diagnoses and fixes. Keep unresolved hypotheses in the
  active task report, not in this reference.
- Merge recurring symptoms with the same root cause into one stronger lesson.
- Promote broadly applicable rules into `SKILL.md`; retain detailed diagnostic
  evidence here.
- Update a deterministic skill script when the prevention or validation can be
  automated reliably.
- Never include secrets, private tests, references, grader receipts or logs,
  model responses, benchmark material, or machine-specific credentials.

### Lock reproducible local grader identities

- **Symptom:** Initial Docker preflight reported a missing grader image. After
  adding a build path, two cached BuildKit builds produced different inspected
  image digests.
- **Root cause:** The repository had no executable grader build/preflight
  command, and default BuildKit provenance attestations changed the manifest
  identity independently of the filesystem layers.
- **Fix:** Pin the base image by digest, build with `--provenance=false`, record
  the grader and compiler fingerprints in a checked-in lock, and make the build
  command verify that lock.
- **Verification:** Two consecutive cached builds produced the same grader
  digest and compiler fingerprint; the explicit lock verification passed.
- **Reusable rule:** Never admit tasks from a mutable tag or an attested local
  manifest identity. Rebuild twice and verify the checked-in lock first.
- **Scope:** Docker BuildKit local Aider C++ grader images.

### Do not assume the Python default async executor progresses

- **Symptom:** Focused reward-hook tests and a minimal `asyncio.to_thread`
  probe stalled indefinitely on Python 3.13, while a direct owned
  `ThreadPoolExecutor` completed.
- **Root cause:** The process-default asyncio executor did not make observable
  progress in this runtime/test environment. The established PIE hook also
  exhibits this environment-specific stall and is outside the Aider boundary.
- **Fix:** Keep the Aider async hook shape but dispatch its Miles-supplied batch
  synchronously into an Aider-owned bounded worker pool; do not modify PIE.
- **Verification:** All focused Aider reward single/batch/retry tests pass; 70
  unaffected repository regressions pass; and the exact frozen PIE test
  `test_reward_func_invalid_format_returns_score_dict_without_running_sandbox`
  reproducibly reaches the external 10-second timeout with exit code 124.
- **Reusable rule:** Probe the exact reward-hook dispatch on the target Python
  runtime. Use an Aider-owned bounded batch pool when the default executor
  stalls, and preserve frozen infrastructure implementations.
- **Scope:** Python 3.13 environment used by this worktree and the one-shot
  Miles Aider reward bridge.

### Invoke a non-executable skill validator through Python

- **Symptom:** Direct execution of the skill creator's `quick_validate.py`
  failed with permission denied and exit code 126.
- **Root cause:** The installed validator has no executable permission bit.
- **Fix:** Invoke the same checked-in validator with the active Python runtime.
- **Verification:** The validator reports `Skill is valid!` for the updated
  Aider skill package.
- **Reusable rule:** If a skill validation script is readable but not
  executable, invoke it through its declared interpreter; do not change system
  skill permissions from a repository task.
- **Scope:** Filesystem-installed Codex skill validators.

### Use a writable dependency cache before escalating network resolution

- **Symptom:** `uv lock` first failed on a read-only default cache, then failed
  DNS resolution in the restricted sandbox.
- **Root cause:** The default uv cache was outside writable roots and dependency
  metadata required network access.
- **Fix:** Set `UV_CACHE_DIR` to a writable temporary path and rerun the same
  lock operation with approved network access.
- **Verification:** The lock resolved successfully and recorded the tokenizer
  dependency graph.
- **Reusable rule:** Point uv at a writable task cache first; if the corrected
  command then fails DNS, request network escalation rather than bypassing the
  lock update.
- **Scope:** Restricted workspace environments using uv.

### Use multiline Python for async command probes

- **Symptom:** A one-line `python -c` diagnostic failed with `SyntaxError` at
  an `async def` placed after a semicolon.
- **Root cause:** Compound statements such as `async def` cannot follow a
  semicolon in Python's simple-statement grammar.
- **Fix:** Rerun the diagnostic as a newline-delimited Python command.
- **Verification:** The multiline owned-executor probe completed successfully.
- **Reusable rule:** Express compound-statement diagnostics as multiline code,
  not semicolon-separated one-liners.
- **Scope:** Shell-based Python diagnostics.

### Migrate controlled fixtures with an admitted schema version

- **Symptom:** The focused Aider suite failed while constructing its first task
  fixture because schema-v2 curriculum, rubric, and mutant fields were absent.
- **Root cause:** Runtime schema changes and their repository-owned fixture were
  not updated in the same patch.
- **Fix:** Add catalog-bound rubric partitions, immutable mutant files, mutation
  receipts, and rubric harness evidence to the controlled fixture.
- **Verification:** All focused Aider tests pass, including draft admission,
  bundle projection, rubric reward, and mutation receipt checks.
- **Reusable rule:** When the admitted task schema changes, update the canonical
  fixture and every private receipt shape before running downstream tests.
- **Scope:** Aider task schema version 2 and later schema migrations.

### Run lint immediately after adding a module

- **Symptom:** Ruff rejected the new curriculum module for one unused schema
  import.
- **Root cause:** An imported draft type was left behind after the resolver API
  was simplified.
- **Fix:** Remove the unused import.
- **Verification:** Focused Ruff checks pass for the Aider package, Miles bridge,
  and tests.
- **Reusable rule:** Run focused lint after each new module or import rewrite,
  before broad regression tests.
- **Scope:** Python Aider lane changes.

### Inspect exact documentation context before a combined patch

- **Symptom:** Documentation patches failed because assumed README sentences did
  not exactly match the staged worktree.
- **Root cause:** The patch mixed a new document with edits against stale context
  from a nearby but non-identical README section.
- **Fix:** Inspect the exact local range, add the standalone document separately,
  and apply small context-specific README patches.
- **Verification:** The curriculum guide exists and README links and commands
  resolve to the implemented surfaces.
- **Reusable rule:** In a dirty or staged worktree, inspect exact documentation
  context and separate independent file additions from contextual edits.
- **Scope:** Documentation edits in shared or pre-modified worktrees.

### Inspect function boundaries after inserting a helper

- **Symptom:** Immediate source inspection showed a new receipt verifier had
  displaced `_public_row`'s return block into the helper.
- **Root cause:** The insertion anchor matched between local construction and
  return rather than after the complete function.
- **Fix:** Restore the public-row return before the helper and remove the
  unreachable misplaced block.
- **Verification:** Bundle projection tests and focused Ruff checks pass.
- **Reusable rule:** After inserting a top-level helper, inspect both adjacent
  function boundaries before relying on tests to reveal control-flow damage.
- **Scope:** Patch-based Python function insertion.
