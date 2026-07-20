# Future-Date Calculations v2 Remediation Audit

## Scope and inputs

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
with `FAMILY_NAME=future-date-calculations`,
`FAMILY_TYPE=aider-text-grid-reshaping`, and the user-authorized hard family
count of 8–12. The requested family-type path did not contain a legacy family;
the actual immutable v1 owner/tree is
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/future-date-calculations/`.
Fresh v2 output is generated only at
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/future-date-calculations/`.
This is local clean-room remediation. Dataset handoff is `not_requested`.

Review date: 2026-07-18. Legacy roots reviewed: 10. Counted v2 roots: 8.
The per-legacy before hashes, per-replacement after hashes, selected prompt,
and disposition live in `.state/remedy/*.json`; the narrative contract for
each disposition lives beside it as `.state/remedy/*.md`.

## Findings

### FDC-F1 — v1 is one generic policy template

**Severity:** major. **Scope:** all ten legacy roots.

The legacy roots expose the same generic `Date`, `Policy`, `Record`, `Result`,
and one-method class shape; share the same calendar helper; select a short body
by task ID; and emit effectively duplicated visible and private tests. Domain
nouns and constants do not create materially different primary logic or
implementation. The v1 family therefore fails the hard diversity rule.

**Root cause:** the owner modeled ten labels as policy branches over one
superset API instead of authoring independent contracts and mechanisms.

**Remedy:** replace eight roots with independently owned APIs/algorithms and
reject the two policy-only variants whose behavior is subsumed. Status:
resolved and reverified in v2.

### FDC-F2 — hard-rule evidence was absent

**Severity:** blocker. **Scope:** v1 family evidence.

V1 had no complete unordered-pair matrix, no seven conjunctive decisions, and
no coherent domain/identifier, constants/policy, or opposite-end adversarial
controls compiled and executed by the production evaluator.

**Remedy:** the v2 owner derives evidence from emitted docs, public headers,
references, visible/private tests, and false-substitute sources. It requires
exactly 28 pairs, all seven dimensions per pair, and three coherent controls.
Independent focused assertions inspect counts, dimensions, decisions, changed
control files, and control rejection. Status: resolved and reverified.

### FDC-F3 — v1 had no admissible Docker receipt

**Severity:** blocker. **Scope:** all v1 roots.

The legacy host verifier neither bound an immutable image nor persisted exact
tree/owner/reference hashes, test counts, network policy, executed topic
negatives, or a separate fresh sanitizer result.

**Remedy:** archive the exact v2 tree, mount it read-only in the pinned image
with networking disabled, run fresh normal and ASan/UBSan builds, execute each
topic negative and all controls, and import evidence only after owner-side hash
and count reconciliation. Status: resolved and reverified.

## Dispositions

| Legacy root | Disposition | Counted v2 root / rationale |
| --- | --- | --- |
| `future-warranty-milestones` | replace | `warranty-service-calendar`: month clamp plus repeated closure walk |
| `future-crop-treatment` | replace | `orchard-treatment-window`: stable stage ordering plus blackout interval jumps |
| `future-invoice-followups` | replace | `invoice-contact-state-machine`: event reduction with terminal precedence |
| `future-licence-renewal` | replace | `licence-renewal-boundaries`: reverse deadline arithmetic and inclusive state classification |
| `future-lab-sample` | replace | `sample-stability-ledger`: interval union and non-duplicated viability penalties |
| `future-construction-deadline` | replace | `construction-phase-network`: topological longest-path scheduling with closures |
| `future-vaccine-series` | replace | `vaccine-eligibility-window`: validated history and rule-indexed date windows |
| `future-equipment-calibration` | replace | `calibration-trigger-forecast`: usage-rate projection versus calendar trigger |
| `future-publication-embargo` | reject | policy-only accumulation is subsumed; retaining it would pad the family |
| `future-lease-notices` | reject | reverse-offset policy is subsumed by the stronger boundary classifier |

## Structural and semantic verification

Every counted root has task-named header/source files, an incomplete coherent
starter, unambiguous reference mapping, separate visible/private tests, a
compiling topic-specific false substitute, C++17 strict warnings, and
repository-authored provenance. Prompt construction exposes only `.docs/` and
the two declared editable files. References, tests, metadata, CMake, negative
fixtures, manifests, and receipts remain private.

The family evaluator compares these seven dimensions separately and
conjunctively: public API; owned state/algorithm; mutation/selection rules;
invalid/boundary behavior; reference control flow; deterministic oracle; and
topic-specific negative fixture. All 28 pairs pass. The production evaluator
rejects the coherent domain/identifier-renamed, constants/policy-only, and
opposite-end-selection controls. Each control changes emitted files, compiles
under the strict task CMake recipe, discovers two tests, and is rejected by an
executed test.

The semantic screen binds all 26 official C++ holdouts and normalizes public
API/reference material with identifiers and literals elided. Whole-slug and
semantic comparisons pass; the permanent holdouts remain untouched.

## Oracle receipt

The final owner command is:

```bash
PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_future_date_aider_tasks \
  --force --verify-docker
```

It uses
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with Docker network `none`, GCC 13.4.0, CMake 3.25.1, explicit Unix Makefiles,
and separate fresh normal and ASan/UBSan builds. Every counted root discovers
and passes two normal and two sanitizer tests. All eight topic negatives and
three coherent controls compile, discover two tests, execute, and are rejected.
The authoritative final hashes and counts are in `.state/oracle-receipt.json`;
`.state/materialization-manifest.json` binds that receipt to the current owner
and generated tree.

Host `--verify` was also attempted but this machine has no host CMake. It is
recorded only as `host_verification_not_completed`; it is not used to support
the Docker result.

## Strongest truthful status

All eight counted roots reached `local_family_verified`. The two rejected
legacy proposals remain accounted for but are not roots in v2. This status is
local task-family evidence only and does not authorize dataset rows, an SFT
release, training, or a benchmark-uplift claim.
