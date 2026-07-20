# Remediate and Reverify a Local Aider Task Family

Inputs:

```text
FAMILY_NAME=<family-name>
FAMILY_TYPE=<family-type>
LEGACY_FAMILY_ROOT=.w8-biayn/data/aider-tasks/<family-type>/<family-name>
REVERIFY_FAMILY_ROOT=.w8-biayn/data/aider-tasks-reverify/<family-type>/<family-name>
```

Remediate and locally reverify the generated Aider C++ task family named by
these inputs. Use the `aider-task-family-remediation` skill and follow
`docs/aider-tasks-spec/verify-and-remedy.md`. This is a single continuous,
gated remediation workflow; it is not permission to hand-edit generated task
output or create a dataset release.

1. Audit every legacy root for its primary core objective, prompt and file-role
   boundaries, reference mapping, oracle status, semantic duplicates, and
   benchmark contamination.
2. Do not modify `LEGACY_FAMILY_ROOT`.
3. Before implementation, create a record and Markdown remedy specification
   for every affected root:

   ```text
   <REVERIFY_FAMILY_ROOT>/.state/remedy/<task-id>.json
   <REVERIFY_FAMILY_ROOT>/.state/remedy/<task-id>.md
   ```

4. Select one disposition per root using the deterministic rules: `reject`,
   `replace`, or `repair-in-place`. Replace template or semantic duplicates;
   do not retain them through a rename-only change.
5. Update the owning curriculum/specification, generator or materializer, and
   focused tests. Do not edit generated task files by hand.
6. Materialize a fresh family only under `REVERIFY_FAMILY_ROOT`.
7. Run and record prompt-boundary, role/reference-mapping, normal and fresh
   ASan/UBSan reference, topic-specific negative-fixture, duplicate-family,
   and benchmark-contamination checks. If the designated locked runtime is
   unavailable, record the exact blocked command and mark the oracle evidence
   `not_completed`; do not replace it with a host-only claim.
8. Update the remedy records with tree hashes, changed owner paths,
   receipt/test counts, screening outcomes, and the strongest truthful local
   status.
9. Do not create dataset rows, token/mask evidence, exports, training runs, or
   release claims.

At handoff, report every finding and disposition; files created, updated,
regenerated, and reused; exact verifier results and unavailable prerequisites;
and whether each root reached `local_family_verified`.
