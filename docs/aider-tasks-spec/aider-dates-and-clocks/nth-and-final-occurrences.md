# Nth And Final Occurrences Remediation Audit

## Scope

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
for the canonical repository family
`aider-dates-and-clocks/nth-and-final-occurrences`. The user supplied a
misspelled name and a different family type, then explicitly confirmed use of
this canonical owner and authorized an 8–12 hard-size range. The 10 legacy
roots remain immutable under `.w8-biayn/data/aider-tasks/`; owner-generated v2
artifacts go only under `.w8-biayn/data/aider-tasks-reverify/`. Review date:
2026-07-18. Dataset handoff is `not_requested`.

## Legacy findings

### NFO-F1 — Shared selector template

**Severity:** major

**Scope:** all 10 legacy roots

**Observed evidence:** every reference has the same static
`select(records, policy, threshold, ordinal, final_match)` scan, the same
validation state, the same early nth return, and the same final accumulator.
Record nouns and predicates are the only substantive variations.

**Why it matters:** the roots do not provide independent logic-and-
implementation learning value.

**Root cause:** one parameterized generator template was counted as a family.

**Remedy:** repair the lexicographically first independently justified route
root and replace the other nine with distinct APIs, owned state, selection
mechanisms, boundaries, references, tests, and negatives.

**Verification after remedy:** the owner must compare all 45 actual emitted
pairs in each of seven dimensions and reject three coherent clone controls.

**Status:** resolved and reverified

### NFO-F2 — Advertised domain mechanisms are absent

**Severity:** major

**Scope:** all 10 legacy roots

**Observed evidence:** lifecycle, graph, run, rolling-window, record-board,
retention-ring, and periodic-cycle claims reduce to filtering a vector.

**Why it matters:** successful compilation does not establish the advertised
core objective.

**Root cause:** the generic selector replaced domain state and algorithms.

**Remedy:** implement the ten mechanisms in the curriculum inventory and
execute a topic-specific false substitute for each root.

**Verification after remedy:** source inspection plus visible/private behavior
tests and executed negative rejection.

**Status:** resolved and reverified

### NFO-F3 — Runtime evidence is not image-bound

**Severity:** blocker

**Scope:** all 10 legacy roots

**Observed evidence:** the legacy owner has a host-only normal/sanitizer helper
and no immutable-image, network-disabled, tree-bound receipt.

**Remedy:** run clean normal and fresh ASan/UBSan builds in the pinned C++
sanity image, with positive equal discovery and archive/mount reconciliation.

**Verification after remedy:** owner `--docker-sanity` receipt.

**Status:** resolved and reverified

### NFO-F4 — Hard-rule adversarial evidence is absent

**Severity:** major

**Scope:** family

**Observed evidence:** the legacy focused test checks count and file shape but
does not inspect all pair decisions or coherent rename, constants/policy, and
opposite-end controls.

**Remedy:** add production controls, exact seven-dimension decisions, and
independent focused assertions.

**Verification after remedy:** focused pytest plus Docker control builds.

**Status:** resolved and reverified

## Dispositions

| Legacy root | V2 root | Disposition | Primary mechanism |
| --- | --- | --- | --- |
| `occurrence-inspection-route` | same | repair-in-place | validated filtered-index scan |
| `occurrence-invoice-escalation` | `escalation-state-ledger` | replace | event-sourced lifecycle ledger |
| `occurrence-lab-sample` | `calibration-run-index` | replace | maximal-run segmentation |
| `occurrence-transit-stop` | `accessible-route-occurrences` | replace | BFS reachability |
| `occurrence-quality-audit` | `defect-episode-audit` | replace | episode state machine |
| `occurrence-support-breach` | `sla-window-crossings` | replace | rolling threshold crossings |
| `occurrence-sports-qualifier` | `athlete-record-board` | replace | per-key record history |
| `occurrence-library-hold` | `hold-dispatch-snapshot` | replace | stable multi-key ordering |
| `occurrence-security-alert` | `alert-retention-ring` | replace | circular retention buffer |
| `occurrence-maintenance-log` | `maintenance-cycle-ledger` | replace | periodic cycle matching |

## Acceptance

The family reaches `local_family_verified` only after focused tests, exact
owner regeneration, prompt/role/reference validation, all 45 conjunctive
seven-dimension decisions, all three coherent controls, all 26 official
holdouts, and network-disabled Docker normal/fresh-sanitizer plus executed
negative checks pass. The final update must record tree/owner hashes, exact
test counts, receipt identity, and the strongest truthful status. No result is
dataset or benchmark-uplift evidence.

## Final verification record

The final owner revision regenerated the complete family after the last
artifact-affecting edit and invalidated all earlier proof. The final family
tree is
`sha256:24059d117d9997843c38ac47c47daf4191ffbd64ee0c537c609a0275e365b2cf`;
owner hash is
`sha256:ae56a4b56e66c9bd1e698bcea3e3f4dec01f82042cbd7cd008ee5789db4cb5b8`;
case inventory hash is
`sha256:05912344b42bcabd8eab1e77ec5cd8e25867933ce27ec508c8a4be574dc367a6`.

Focused pytest passed 7 tests. Core verification passed prompt boundaries,
role/reference mapping, all 45 unordered pairs in every one of the exact seven
dimensions, all three coherent clone controls, and 260 comparisons covering
all 10 roots against all 26 official C++ holdouts. The strongest normalized
holdout containment was `0.202261`, below the `0.80` rejection threshold.

The final network-disabled Docker sanity receipt binds archive
`sha256:15e4770d05f2ae35d75e04ebcc5ea6869c9bd7dd379cb398b15f65fb7e9ae2c8`
to pinned image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
GCC 13.4.0, and CMake 3.25.1. Every root passed two normal and two fresh
ASan/UBSan CTests; all 10 topic negatives compiled, executed, and were
rejected; the three coherent controls each passed two normal and two sanitizer
tests before production semantic rejection. All 10 remedy records bind the
current tree and report `verified` / `local_family_verified`. Evidence class is
`docker_sanity`, not a family-designated locked oracle. Dataset handoff remains
`not_requested`.
