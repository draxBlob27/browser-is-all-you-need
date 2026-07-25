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

## Request Batching

Do not remediate or replace an entire large campaign in one request. For
report-driven expansion or improvement work, each request may remediate,
replace, or add only one coherent batch of 40-100 new or improved task roots.
If the family/campaign has more than 100 affected roots, select the next
coherent 40-100 root slice, give it a stable batch ID, and record every
remaining root as deferred backlog. If fewer than 40 roots are available, or
the user explicitly requested a smaller remediation, record why the batch is
below the normal request size.

The handoff must distinguish the current batch from the campaign:

- included roots and deferred roots;
- batch-local prompt-boundary, oracle, negative-fixture, duplicate, and
  benchmark-contamination results;
- current batch status;
- explicit non-claims for full-family completion, SFT release, training
  authorization, and benchmark uplift.

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
