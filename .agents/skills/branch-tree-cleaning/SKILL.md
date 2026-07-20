---
name: branch-tree-cleaning
description: Audit, organize, and safely clean dirty Git branches, worktrees, indexes, untracked files, generated artifacts, nested checkouts, and commit history without losing user work. Use when the user asks to clean a branch or working tree, reduce Git dirt, separate mixed workstreams, prepare changes for review or commit, remove stale generated state, repair branch hygiene, or explain what may be safely discarded, ignored, untracked, staged, committed, moved, or rewritten.
---

# Branch Tree Cleaning

Turn a dirty Git branch into a deliberate, reviewable state while preserving
user work. Treat an empty `git status` as one possible result, not the goal by
itself.

## Establish Authority And Scope

1. Resolve the repository root and read every applicable `AGENTS.md`, project
   guide, and repository workflow document before acting.
2. Determine whether the user requested an audit, a cleanup plan, or execution.
   An audit or status request authorizes read-only inspection only.
3. Resolve the exact scope: current worktree, current branch, all linked
   worktrees, a nested checkout, or remote history. Do not silently widen it.
4. Distinguish the desired outcome:
   - **Git-clean**: no staged, unstaged, or untracked paths.
   - **Review-clean**: one coherent, intentional diff with unrelated work
     isolated and required checks passing.
   - **Artifact-clean**: generated state is correctly ignored, untracked, or
     owner-managed while valuable local evidence remains available.
5. Ask whether the final result should remain an unstaged diff, become staged
   slices, or become commits when the user's request does not make that choice.

Never interpret “clean” as permission to discard changes.

## Inventory Before Mutation

Start with read-only commands and preserve their results in the handoff:

```bash
git rev-parse --show-toplevel
git status --short --branch --untracked-files=all
git diff --stat
git diff --cached --stat
git diff --summary
git diff --check
git diff --cached --check
git ls-files --others --exclude-standard
git branch -vv
git worktree list --porcelain
git stash list
git submodule status
```

Also inspect, when relevant:

- local branch/upstream divergence without fetching first;
- staged and unstaged diffs separately;
- type, executable-bit, and symlink changes;
- in-progress merge, rebase, revert, or cherry-pick state;
- nested repositories and pinned upstream checkouts independently;
- targeted ignore behavior with `git check-ignore -v -- <path>`;
- repository-owned manifests, generators, receipts, and provenance for files
  that appear generated.

List secret-like paths without printing their contents. Avoid broad ignored-file
enumeration when caches or datasets may be large. Do not fetch, pull, or mutate
remote-tracking refs during the initial local audit.

## Classify Every Affected Path

Assign each changed or untracked path to one of these classes before proposing
an action:

| Class | Default treatment |
|---|---|
| Intentional source/docs/tests | Keep together as one logical change and validate it. |
| Valuable but unrelated work | Preserve and isolate; ask how the user wants it represented. |
| Generated artifact or local evidence | Keep available; use precise ignore/untrack rules rather than deletion. |
| Stale generated output | Use its owner-controlled invalidation/regeneration path. |
| Secret or credential | Stop, redact output, and separate untracking from rotation/history repair. |
| Accidental mode or symlink change | Verify the canonical target and repair the source of truth. |
| Nested upstream/vendor dirt | Report it separately; never clean it from the parent repository. |
| Unknown ownership or provenance | Preserve it and ask before changing or moving it. |

Do not classify a file as disposable merely because it is untracked, ignored,
large, generated-looking, old, or reproducible in theory.

## Plan The Cleanup

Before mutation, present:

1. the exact paths and repositories affected;
2. the proposed action for each class;
3. whether index, working-tree, branch, history, remote, or external state will
   change;
4. the recovery path and what it does **not** protect;
5. the validation that will prove the result.

Read [references/permission-and-recovery.md](references/permission-and-recovery.md)
before any mutation. Ask once for a clearly bounded batch of identical actions;
do not request vague permission for “whatever cleanup is needed.”

## Permission Gates

Read-only inspection does not require permission. Bounded edits that the user
explicitly requested and that preserve all data may proceed normally.

Ask before any of the following unless the user already authorized that exact
class of action and scope:

- deleting, discarding, overwriting, or moving tracked, untracked, or ignored
  content;
- restoring paths from `HEAD`, resetting the index or worktree, or running any
  form of `git clean`;
- creating, applying, dropping, or clearing a stash;
- staging paths, creating commits, amending, squashing, rebasing, resetting,
  reverting, or cherry-picking when commit/history work was not explicitly
  requested;
- creating, renaming, deleting, or force-removing branches or worktrees;
- changing submodule state, replacing a nested checkout, or recloning a dirty
  pinned upstream;
- untracking files with `git rm --cached` or broadening ignore rules when the
  user requested only an audit;
- fetching when remote freshness matters, pulling, pushing, opening a PR, or
  changing any remote ref;
- rewriting published history or force-pushing, even when the branch appears
  to be owned by the current user;
- rotating credentials, purging secrets from history, or editing external
  secret stores;
- stopping/deleting cloud resources, caches, volumes, or artifacts outside the
  exact local Git scope;
- escalating privileges or crossing a filesystem ownership boundary.

For destructive or history-changing approval, state the exact command or
operation, targets, impact, collaborators affected, and recovery limitations.
Approval for one path or repository does not cover another.

## Commands Not To Use By Default

Do not run these merely to make status output shorter:

```text
git reset --hard
git clean -fd / git clean -fdx
git checkout -- .
git restore .
git stash clear / git stash drop
git branch -D
git worktree remove --force
git push --force / git push --force-with-lease
rm -rf <broad-or-unresolved-target>
```

Use one only after direct approval for exact resolved targets, a read-only
preview where available, and a truthful recovery assessment. Prefer safer,
path-specific alternatives. Never modify Git's internal files by hand.

Also avoid:

- `git add -A` or broad globs in a mixed worktree;
- treating a stash as a complete backup—untracked and ignored files have
  different inclusion rules, and a stash remains local;
- hand-editing or hand-deleting generated task trees, receipts, manifests, or
  immutable evidence roots;
- hiding real source changes with broad `.gitignore` patterns;
- copying a canonical symlink target into multiple divergent regular files;
- resolving conflict markers by guesswork;
- printing secret contents while investigating why a path is dirty;
- declaring success while required tests, linters, receipts, or nested
  checkouts remain invalid.

## Execute In Recoverable Slices

### Preserve Before Restructuring

For a large or mixed cleanup, ask the user to choose an appropriate checkpoint:
a reviewed WIP commit, a dedicated branch/worktree, a stash, or an external
backup. Explain that none is universal:

- a new branch name alone does not capture uncommitted files;
- a normal stash does not include all untracked or ignored files;
- a patch may omit untracked files and may expose secrets;
- a local commit is not durable against disk loss until copied elsewhere.

Verify that the selected checkpoint covers every path before restructuring.

### Separate Workstreams

1. Select one concern at a time.
2. Keep its source, tests, docs, and required metadata together.
3. Use explicit path lists or `git add -p` only when staging/commits are
   authorized.
4. Validate the slice before moving to the next concern.
5. Leave unrelated user changes untouched.

Do not use a new commit as a dumping ground for unknown files. Reword or squash
history only after the content is stable and the user approves history edits.

### Handle Generated And Ignored State

- If a generated file is tracked but should remain locally, propose
  `git rm --cached -- <exact-path>` plus a precise ignore rule. Confirm the
  working-tree file remains present.
- If an untracked artifact is legitimate local state, prefer a precise ignore
  rule or the repository's established artifact directory over deletion.
- If output is stale, invoke the owning generator's guarded cleanup,
  invalidation, or regeneration flow. Preserve old evidence when its workflow
  requires archival.
- If ownership is unknown, quarantine only with permission and record the old
  and new paths. Do not manufacture provenance.

### Repair Modes And Symlinks

Use `git diff --summary`, `git ls-files -s`, `ls -l`, and `readlink` to confirm
the intended file type. Update the canonical source and recreate compatibility
links; do not maintain divergent copies.

### Handle Nested Checkouts And In-Progress Git Operations

Audit nested repositories in their own roots. For a dirty pinned checkout,
prefer its repository-owned clone/doctor flow after preserving unknown state;
ask before cleaning or replacing it.

If a merge, rebase, revert, or cherry-pick is active, stop ordinary cleanup.
Inspect the operation and ask whether to continue or abort. An abort can discard
conflict-resolution work and is therefore not an automatic recovery action.

## Validate The Result

Run repository-prescribed checks proportional to each logical slice, then
repeat the Git inventory. At minimum inspect:

```bash
git status --short --branch --untracked-files=all
git diff --check
git diff --cached --check
git diff --stat
git diff --cached --stat
git diff --summary
```

When commits are authorized, inspect the exact staged diff, name/status list,
and secret-sensitive paths before each commit. Verify precise ignore rules with
`git check-ignore -v -- <path>`. Recheck symlinks, executable bits, nested
checkouts, generated receipts, and upstream divergence when they were in scope.

Do not call the branch clean when work was merely hidden in a stash or ignored,
when required validation is red, when generated evidence is stale, or when a
relevant nested checkout remains dirty.

## Handoff

Report:

- branch, upstream, worktree, and nested-repository scope;
- before/after path counts by staged, unstaged, untracked, deleted, and type
  change;
- what was preserved, isolated, ignored, untracked, staged, committed, moved,
  or deleted;
- every destructive action and whether it is recoverable;
- validation commands and exact outcomes;
- remaining blockers, user decisions, and remote/history work not performed.

If an action produces an unexpected result, stop. Capture read-only status and
reflog evidence, verify the checkpoint, and ask before attempting recovery. Do
not stack resets or cleanup commands on top of an unexplained state.
