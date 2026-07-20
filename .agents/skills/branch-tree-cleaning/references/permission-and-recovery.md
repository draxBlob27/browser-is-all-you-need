# Permission And Recovery Matrix

Read this reference before mutating a dirty branch or worktree.

## Permission Matrix

| Action | Default | Permission boundary |
|---|---|---|
| Status, diff, log, reflog, worktree, submodule, or ignore inspection | Proceed | Keep output scoped and redact secrets. |
| Repository-prescribed tests, lint, compile, or dry-run checks | Proceed | Ask if they spend money, use external services, alter production, or require privilege. |
| Bounded source/docs/test edits explicitly requested by the user | Proceed | Preserve unrelated changes and avoid generated output. |
| Precise `.gitignore` correction during an authorized cleanup | Proceed cautiously | Ask if it would hide existing source, broad directories, or another user's artifacts. |
| Path-specific staging | Proceed only when staging or commit preparation was requested | Otherwise ask; staging changes the shared index. |
| Commit creation | Ask unless explicitly requested | Show the intended slice and validation first. |
| WIP checkpoint commit | Ask | Explain that it is local and may need later rewording/squashing. |
| New branch or linked worktree | Ask | State name/path, disk impact, and whether uncommitted files are captured. |
| Stash creation, application, pop, drop, or clear | Ask | List inclusion rules and conflict/data-loss risks. |
| `git rm --cached` | Ask unless untracking was explicitly requested | Confirm the working-tree file remains and add a precise ignore rule if appropriate. |
| Move or quarantine files | Ask | Provide exact old/new paths and recovery move. |
| Delete any tracked, untracked, or ignored path | Ask | Resolve exact targets; state whether recovery exists. |
| Regenerate or invalidate generated evidence | Follow the owner workflow | Ask if it replaces, archives, or removes existing evidence. |
| Restore/checkout/reset paths from a commit | Ask | Name the paths and source commit; this discards current bytes. |
| Rebase, amend, squash, reset, revert, or cherry-pick | Ask | Identify commits, conflicts, published status, and rollback point. |
| Abort an in-progress Git operation | Ask | It may discard already-resolved conflict work. |
| Delete/rename a branch or remove a worktree | Ask | Confirm it is not checked out, shared, or the only ref to commits. |
| Fetch remote refs | Follow user/repo network authority | Do not confuse fetch with a read-only filesystem action. |
| Pull, push, PR creation, tag changes, or remote branch deletion | Ask unless explicitly requested | Show destination and expected ref movement. |
| Force push, including `--force-with-lease` | Always ask directly | Verify collaborator impact and the exact lease/ref. |
| Clean/reclone a nested or pinned upstream | Ask | Preserve unknown files and use its owner command. |
| Secret untracking, rotation, or history purge | Stop and ask | Removing a file does not remove leaked history; rotation is separate. |
| Cloud/resource/cache/volume teardown outside the local repo | Ask | Local branch cleanup does not authorize external deletion. |
| Privilege escalation | Ask through the environment's approval mechanism | Explain the exact protected target and operation. |

An explicit request such as “commit these three reviewed files” authorizes that
bounded action. It does not authorize staging everything, rewriting earlier
commits, pushing, or deleting other files.

## Approval Request Template

Use a concise request containing all four elements:

> I found `<state>` at `<exact targets>`. I propose `<action/command>`, which
> will `<impact>`. Recovery is `<recovery or none>`. May I proceed?

For a batch, enumerate or attach the complete resolved path list. Never request
approval for a glob, unresolved environment variable, repository root, home
directory, or other broad destructive target.

## Recovery Reality

State recovery limits before acting:

- A commit can preserve tracked and explicitly added untracked files, but a
  local-only commit is not an off-machine backup.
- A stash may omit untracked files unless requested and normally omits ignored
  files. Applying it can conflict; dropping it removes its ordinary name.
- `git reflog` can help locate recent commit/ref movements. It does not restore
  arbitrary deleted untracked or ignored files.
- A patch generally omits untracked files and can contain secrets or binary
  limitations unless deliberately constructed and inspected.
- A new branch pointer does not snapshot dirty working-tree bytes.
- `git rm --cached` preserves the current working-tree file; a later ordinary
  delete does not.
- Regeneration recreates outputs only when the owner, inputs, pins, and
  provenance are known. It does not automatically recreate historical
  receipts or evidence.
- Removing a secret from the tip does not revoke the credential or purge Git
  history. Rotate first or in parallel, then plan history repair explicitly.
- Force-pushed commits may still exist in collaborators' clones and caches.

## If Cleanup Goes Wrong

1. Stop immediately; do not issue another reset, clean, checkout, or stash
   command.
2. Record `git status`, current `HEAD`, branch/upstream refs, `git reflog`, and
   worktree locations without modifying them.
3. Identify the last verified checkpoint and exactly which paths it covered.
4. Preserve the unexpected state if doing so will not overwrite the checkpoint.
5. Explain what is recoverable, uncertain, or unrecoverable and ask before
   applying recovery.
6. Validate recovered content byte-for-byte or with the repository's owner
   checks before resuming cleanup.

Do not use `git reset --hard` as a generic way to recover from a previous
`git reset --hard`. Do not run `git fsck --lost-found`, reflog expiration,
garbage collection, or object pruning during ordinary cleanup without an
explicit forensic recovery plan and permission.

## Completion Standard

A cleanup is complete only when the agreed target is satisfied and the report
accounts for every original path. A short `git status` is insufficient if work
was hidden, evidence was invalidated, tests failed, remote history changed
without confirmation, or recovery information is missing.
