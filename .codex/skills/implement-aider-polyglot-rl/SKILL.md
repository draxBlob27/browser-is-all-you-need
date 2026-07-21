---
name: implement-aider-polyglot-rl
description: Implement, extend, review, or debug the Aider Polyglot C++ reinforcement-learning lane in this repository by adapting the existing PIE C++ lane at benchmark boundaries only. Use for Aider task admission, dataset projection, whole-file prompting and parsing, isolated grading, correctness rewards, Miles reward integration, launch profiles, evaluation, observability, and tests when the established GLM/Miles/Megatron/SGLang/checkpoint infrastructure must remain unchanged.
---

# Implement Aider Polyglot RL

Implement Aider Polyglot as an additive benchmark lane beside PIE C++. Preserve
the proven training infrastructure and change only benchmark-owned behavior.

## Read First

Read [references/lane-contract.md](references/lane-contract.md) completely
before changing code. Consult
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_POST_SFT_RL_ENVIRONMENT.md` when a task
requires admission policy, split strategy, reward calibration, repair credit,
promotion gates, or official evaluation details beyond the condensed contract.
Read `docs/AIDER_RL_FAILURE_DERIVED_CURRICULUM.md` before authoring or changing
failure modes, rubric tests, mutants, rubric reward weights, or no-update
curriculum gates.

Inspect `git status`, applicable `AGENTS.md` files, and the current PIE entry
points before editing. Preserve unrelated and pre-existing worktree changes.

## Learn from Every Error

Whenever any command, test, validation, launch, grader, data, or integration
step fails while applying this skill, complete this loop before finishing the
task:

1. Capture the exact failing operation, error evidence, and relevant context.
2. Diagnose the root cause. Do not promote a speculative workaround as a fix.
3. Implement the smallest in-scope fix and rerun the focused failing check.
4. Run proportional regression checks to prove the fix did not weaken the PIE
   boundary, evaluation integrity, or fail-closed behavior.
5. Update this skill package with the verified lesson immediately after the
   fix. Add or tighten the reusable instruction in `SKILL.md`, a directly
   linked reference, or a deterministic skill script as appropriate.
6. Record the symptom, root cause, fix, verification, and reusable rule in
   [references/error-lessons.md](references/error-lessons.md). Merge repeated
   instances into an existing lesson instead of accumulating duplicate notes.
7. Validate the updated skill before reporting completion.

Treat environment and infrastructure failures the same way: record their
verified scope and the correct detection, retry, or escalation behavior even
when no repository code changes. Never write secrets, private tests,
references, grader logs, model responses, or other protected task material into
the skill. If the cause or fix remains unverified, record it as an unresolved
blocker in the task report and do not encode it as established guidance.

## Enforce the Lane Boundary

Keep these established surfaces behaviorally unchanged:

- GLM model bridge and model arguments;
- checkpoint conversion and export;
- LoRA construction, loading, and synchronization;
- SGLang serving and rollout transport;
- Megatron update mechanics;
- Miles GRPO grouping, batching, and generic sample transport;
- canonical PIE scripts, defaults, environment variables, and tests.

Treat established infrastructure implementations, signatures, defaults, and
method behavior as frozen. Add Aider-specific code through sibling modules,
new wrappers, and benchmark-owned configuration. Do not rename, generalize,
refactor, or clean up proven infrastructure as part of a lane change.

If an established method lacks an extension point, first identify the exact
contract mismatch, stop, and report the blocker. Do not patch the
infrastructure without explicit user authorization that expands the task
beyond lane migration.

## Implement in This Order

1. Confirm that clean-room source task roots exist with starter files, private
   tests, build files, references, provenance, and oracle evidence. Do not infer
   executable reward assets from public SFT JSONL.
2. Bind every source task to the versioned failure-rubric catalog. Partition
   every visible and hidden test exactly once across at least two behavior
   rubrics. Require compiling model-like mutants that fail each targeted rubric
   while passing declared unrelated rubrics. Never derive a clean-room task by
   copying official semantics or protected evaluation artifacts.
3. Add `src/glm47_posttraining/aider_rl/` as a sibling of `cpp_perf`; do not add
   Aider flags or optional fields to `CppTask`.
4. Implement immutable task admission and Miles JSONL projection with strict
   public/private separation, family/lineage splits, fingerprints, and measured
   tokenizer budgets.
5. Reproduce the established Aider SFT whole-file prompt and implement a strict
   named-file parser. Reject missing, duplicate, extra, unsafe, or oversized
   paths before touching a task tree.
6. Grade a fresh task copy in the pinned Docker-only Aider grader. Run normal
   visible and hidden tests separately, then a fresh ASan/UBSan build before
   granting full credit. Treat zero discovered tests as failure. Build the
   local grader without mutable BuildKit provenance attestations, pin its base
   image by digest, and verify repeated builds against a checked-in
   image/compiler identity lock before admitting tasks.
7. Implement versioned correctness-only reward tiers. Score isolated rubrics,
   not aggregate raw test counts; validate that aggregate suite results equal
   their rubric partitions; cap partial progress when critical rubrics fail.
   Remove runtime speed from the Aider objective and keep format recovery
   diagnostic-only.
8. Add `glm47_posttraining.integrations.miles_aider_rl.reward_func` using the
   existing Miles sample/list hook shape and bounded concurrent scoring. Remove
   infrastructure failures from learning instead of returning a model penalty.
   Validate dispatch on the target Python runtime; do not assume
   `asyncio.to_thread` or the process-default executor makes progress. Keep
   concurrency inside an Aider-owned bounded pool when the runtime hook already
   supplies a batch.
9. Add Aider launch and evaluation wrappers with Aider-owned variables, data,
   reward import, eval name, grader preflight, response limits, W&B tags, and
   metrics. Leave canonical PIE entry points unchanged.
10. Add focused unit, integration, security, launch-profile, mutation-admission,
   rubric-reward, and no-update canary tests. Run the smallest relevant tests
   after each layer, then the full suite. Block update training unless the
   capability-balanced no-update analyzer reports useful reward variance.

## Keep Version 1 One-Shot

Implement one-shot whole-file GRPO first because it fits the existing Miles
custom reward hook. Do not imitate repair by concatenating independent samples
or assigning final success to a failed first response.

Add bounded repair only as a later bridge that can evaluate turn one, redact
feedback, sample turn two in the same trajectory, return exactly one trainable
sample, and mask or detach first-turn tokens from final success credit.

## Protect Evaluation Integrity

Never train on the official Aider Polyglot tasks, tests, references, model
responses, retry histories, or semantic copies. Use clean-room Aider-style
tasks for SFT and RL. Reserve the pinned official benchmark for frozen
milestone comparisons.

Resolve task metadata only inside the configured immutable Aider data root.
Reject arbitrary absolute paths, traversal, stale digests, and current working
directory fallbacks. Never expose private tests, references, build files, or
grader receipts in prompts or repair feedback.

## Publish Across Repositories

Before opening a cross-repository PR, verify that the proposed head and base
repositories belong to the same GitHub fork network and that the authenticated
account can read the head ref. If they do not share a network and direct push
access to the base repository is unavailable, create a uniquely named fork of
the target repository, push the head branch there, and open the PR from that
target-network fork. Verify the remote branch SHA and check for an existing PR
before creating one.

In a linked worktree, a relative credential-store path under `.git/` may be
invalid because `.git` is a file. Treat the resulting credential-lock warning
as non-fatal only when `git push` exits successfully and the remote branch SHA
is independently verified. Do not rewrite shared credential configuration as
part of an Aider lane change.

## Definition of Done

Complete a lane change only when:

- existing PIE tests and canonical behavior still pass;
- Aider schema, parser, dataset, grader, reward, Miles batch shape, and launch
  profile tests pass;
- oracle preflight and positive test discovery fail closed;
- the failure catalog validates, all tests are rubric-partitioned, and targeted
  mutants prove every task rubric is diagnostic;
- infrastructure aborts are distinguishable from model failures;
- public JSONL contains no private grader material;
- a no-update rollout shows valid group shape and useful reward variance; and
- the no-update curriculum report passes task-count, rubric-shape,
  infrastructure, capability-balance, and zero-variance gates;
- documentation records task, tokenizer, grader, parser, reward, model, and
  split identities;
- every encountered error has a verified disposition and the resulting lesson
  has been incorporated into this skill package;
- the updated skill passes its validation check.
