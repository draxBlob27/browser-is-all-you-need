# General Calendar Arithmetic Family Remediation

## Scope and decision

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
with corrected inputs `FAMILY_NAME=general-calendar-arithmetic` and
`FAMILY_TYPE=aider-dates-and-clocks`. The user authorized a hard family-size
range of 8–12 roots. Review date: 2026-07-18.

The immutable legacy family is
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/general-calendar-arithmetic/`.
The owner-generated v2 family is
`.w8-biayn/data/aider-tasks-reverify/aider-dates-and-clocks/general-calendar-arithmetic/`.
The legacy inventory has ten roots and was not modified. Dataset handoff is
`not_requested`.

## Audit findings

### GCA-F1 — Shared calendar template

**Severity:** major

**Scope:** every legacy root

**Observed evidence:** the legacy references wrap one shared `valid`,
`add_days`, and `add_months` implementation. Most root-specific bodies are
one-pass policy adapters whose substantive calendar control flow differs only
by conditions, field names, and constants.

**Why it matters:** unequal task names and raw source hashes do not establish
the required logic-and-implementation diversity.

**Root cause:** the v1 generator treated domain policy labels as the primary
family separator.

**Remedy:** retain each independently useful public objective but implement a
separate necessary algorithm and topic-specific false substitute.

**Status:** resolved and reverified.

### GCA-F2 — Nondiscriminating private checks

**Severity:** major

**Scope:** every legacy root

**Observed evidence:** the v1 hidden test added only a trivial positive-year
loop to the visible check and did not independently exercise the claimed
mechanism.

**Remedy:** emit a third hard-rule executable with a leap-century, complete
state, dependency, or multiplicity property appropriate to each root; compile
and execute a separate task-specific false source against all three tests.

**Status:** resolved and reverified.

### GCA-F3 — Missing hard-rule and runtime evidence

**Severity:** blocker

**Scope:** family

**Observed evidence:** v1 had no complete 45-pair/seven-dimension matrix, no
coherent rename/policy/opposite-end controls, and no exact-tree network-disabled
Docker receipt.

**Remedy:** add artifact-derived all-pairs and holdout screens, coherent
controls copied from an emitted root, deterministic archive transport, and
pinned normal/fresh-sanitizer Docker execution.

**Status:** resolved and reverified.

## Dispositions and primary mechanisms

All ten objectives survive as `repair-in-place`; task-spec revision is 2.

| Root | Primary core objective | v2 necessary mechanism | Disposition |
| --- | --- | --- | --- |
| `calendar-subscription-cycle` | anchored renewal selection | direct anchor projection plus earliest-due reduction | repair-in-place |
| `calendar-harvest-plan` | duration-preserving window migration | ordinal duration reconstruction from one shifted anchor | repair-in-place |
| `calendar-clinic-followup` | blackout-aware allocation | blackout interval merge plus forward free-day search | repair-in-place |
| `calendar-inventory-expiry` | lifecycle classification | recall-first event precedence | repair-in-place |
| `calendar-contract-amendment` | atomic amendment replay | full validation followed by transactional replay | repair-in-place |
| `calendar-vacation-allocation` | multi-year balance charging | inclusive year-partitioned civil-day ledger | repair-in-place |
| `calendar-maintenance-rotation` | recurrence catch-up | direct anchored occurrence search and missed count | repair-in-place |
| `calendar-licence-grace` | regulatory boundary classification | ordered inclusive boundary construction | repair-in-place |
| `calendar-release-train` | dependency-safe milestone planning | stable topological propagation | repair-in-place |
| `calendar-lease-portfolio` | occupancy aggregation | ordinal difference sweep | repair-in-place |

`primary_core_objective: achieved` is supported by each emitted reference,
its independent hard-rule test, and its compiled/executed topic negative.

## Structural and prompt matrix

Every root has exactly two task-named editable files, one visible test, two
private tests, two suffix-mapped references, one private negative source,
role-correct JSON/TOML metadata, and a strict offline C++17 CMake project.
Prompt construction exposes only `.docs` plus the two declared editable files.
References, all tests, CMake, provenance, negatives, controls, screens, and
receipts are absent from the prompt. The whole-file reference response contains
exactly one listing per editable file in declared order.

## Hard diversity and contamination

Normalizer: `general-calendar-arithmetic-v2-role-aware-7gram`.

The production screen reread actual emitted docs, headers, reference source,
visible/private/hard-rule tests, and negative source. It compared all 45 unordered pairs
separately across exactly:

1. `public_api`
2. `owned_state_algorithm`
3. `mutation_selection_rules`
4. `invalid_boundary_behavior`
5. `reference_control_flow`
6. `deterministic_oracle`
7. `topic_specific_negative_fixture`

Every dimension passed for every pair. Independent focused assertions inspect
the exact root and pair counts, the exact dimension set, and every per-dimension
decision.

Three controls were copied from the emitted subscription root and changed
multiple emitted files: a domain/identifier rename, a coherent cadence-policy
change, and earliest-to-latest selection. Each remained buildable and passed
all three behavior tests in normal and sanitizer modes. The exact production
evaluator rejected every control in all seven dimensions as `duplicate_family`.

The role-aware semantic screen compared all ten roots with all 26 official
Aider C++ holdouts (260 comparisons). Whole-slug and content screens passed;
`clock`, `gigasecond`, and `meetup` remain permanent holdouts.

## Oracle evidence

The final `.state/oracle-receipt.json` binds the exact owner and case-table
hashes, archive hash, ten current root/reference/negative hashes, controls,
commands, and network policy. Exact mutable-source hashes remain in that
machine-readable receipt so this checked-in specification does not become a
self-referential provenance input.

The network-disabled image was
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
(immutable image ID with the same digest), GCC 13.4.0, and CMake 3.25.1.
Every root and coherent control discovered and passed three normal plus three
fresh ASan/UBSan tests. Every topic negative compiled, discovered three tests,
and was rejected by executed tests. Evidence class is `docker_sanity`, not a
family-designated `locked_oracle`.

Host verification is separately `not_completed` because host CMake is absent;
that weaker prerequisite does not replace or weaken the passing Docker gate.

## Changed owner paths

- `scripts/plan_general_calendar_arithmetic_remedies.py`
- `src/w8_biayn/integrations/moonlight_calendar_arithmetic_aider_tasks.py`
- `src/w8_biayn/integrations/moonlight_calendar_arithmetic_cases.py`
- `tests/test_moonlight_calendar_arithmetic_aider_tasks.py`
- `examples/slime/moonlight_cpp_perf/prepare_calendar_arithmetic_aider_tasks.sh`
- this specification, the curriculum, and the materialization guide

## Reproduction and acceptance

```bash
python3 scripts/plan_general_calendar_arithmetic_remedies.py
PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_calendar_arithmetic_aider_tasks --force --verify-core
PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_calendar_arithmetic_aider_tasks --verify
PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_calendar_arithmetic_aider_tasks --docker-sanity
```

The third command records `not_completed` on this host because CMake is
missing. The final Docker command is the mandatory successful runtime gate.

## Conclusion

The ten roots are `local_family_verified`: primary objectives achieved,
structurally valid, Docker-sanity normal/sanitizer verified, and locally
training-suitable under the family and holdout screens. This is local candidate
evidence only. It creates no SFT rows, dataset release, training authorization,
or benchmark-uplift claim.
