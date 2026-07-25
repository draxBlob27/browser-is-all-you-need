# Calendar Difference, Leap, And Month-End Expansion Curriculum

Status: generator-owned clean-room creation curriculum for the binding 90-root
time/date cell in the 2,500-task count plan. The roots are local candidate
artifacts only; this document creates no SFT rows, release, training
authorization, or benchmark-uplift claim.

## Scope and count contract

The owner is
`src/w8_biayn/integrations/moonlight_calendar_boundary_expansion_aider_tasks.py`.
It writes only beneath
`.w8-biayn/data/aider-tasks-expansion-v1/time-date/calendar-difference-leap-month-end/`.
The existing legacy and reverify trees are immutable inventory and semantic
comparison inputs. The owner must refuse ID, prompt, answer/reference, test,
or semantic-lineage overlap with either tree and all 26 official Aider C++
holdouts.

The 90 retained roots are divided into three equally sized mechanism groups:

- 30 interval metrics using signed, endpoint, partition, leap, month-capacity,
  annual-fraction, and boundary-density mechanisms;
- 30 civil-date transformations using ordinal displacement, clamp, rollover,
  end-of-month anchors, leap-anniversary policies, fiscal/quarter/semester
  projections, and bounded search; and
- 30 ordered series mechanisms using boundary enumeration, anchored schedules,
  leap-cycle projections, in-span fragment/run origins, and canonical
  month/quarter selections. Every series contains actual civil dates rather
  than dates used as integer encodings.

The complete task IDs and per-root mechanisms are normative in
[`calendar-difference-leap-month-end-expansion.md`](../../aider-tasks-spec/aider-dates-and-clocks/calendar-difference-leap-month-end-expansion.md).

## Common civil-date foundation

Every root uses caller-supplied proleptic Gregorian dates in years 1 through
9999. The shared support kernel validates dates, applies the Gregorian
divisible-by-4/100/400 rule, converts valid dates to and from a zero-based civil
ordinal, and provides clamped and rolling month movement. This kernel is
incidental support. Each root's advertised core objective is the distinct
metric, selection, partition, fold, search, schedule, or projection named in
the family specification and delimited in the emitted reference.

No root may use system clocks, locale/time-zone data, networking, files,
randomness, undefined overflow, precomputed examples, or a general date-time
library as the substantive solution. Metric roots reject invalid or reversed
spans. Transform roots reject invalid parameters and out-of-range results.
Series roots return chronological, duplicate-free output and reject invalid or
reversed spans.

## Executable task contract

Each root exposes one task-specific C++17 class/method and the shared `Date`
value. It has exactly two editable, task-ID-named files in header/source order,
complete private reference replacements, one visible executable, one private
executable, and one coherent compiling false substitute. Each executable
contains multiple exact/property assertions; together they cover 1900, 2000,
equality, reversed and invalid inputs, parameter edges, years 1 and 9999,
series ordering/uniqueness, and termination. The false substitute implements
the adjacent plausible calendar mechanism rather than a syntax error, and the
production tests must execute and reject it.

Prompts contain only `.docs/*.md` plus the two declared starter files.
References, tests, metadata, CMake, provenance, controls, receipts, and audit
state remain private. Normal and fresh ASan/UBSan builds must discover the same
two positive tests. Every false substitute must compile under the same strict
warnings and exit nonzero when executed.

## Diversity and adversarial clone contract

The owner rereads the emitted docs, public API, core reference region,
visible/private tests, and false substitute. It compares all 4,005 unordered
pairs across the exact seven dimensions required by the repository:

1. public API;
2. owned state or algorithm;
3. mutation or selection rules;
4. invalid and boundary behavior;
5. reference control flow;
6. deterministic oracle; and
7. topic-specific negative fixture.

The decision is conjunctive and also requires distinct deterministic
observable signatures over boundary probes. Unique IDs, raw hashes, or this
curriculum table are not evidence. The focused test independently reopens
every recorded per-dimension and observable decision and checks the exact
root/pair/dimension counts.

The owner also materializes three coherent, buildable controls under `.state`:
a domain/identifier rename, a constants-or-policy-only variant, and an
opposite-end variant. Each must change files, pass its internally consistent
reference tests in normal and sanitizer modes, and be rejected by the exact
production pair evaluator. Controls and rejected proposals never count as
roots.

## Inventory, provenance, and receipts

Before materialization the owner digest-binds both existing inventories and
the exact 26 holdouts, then rejects exact prompt/reference/test/ordered-semantic
collisions in addition to aggregate overlap. Raw proposals, selected
candidates, rejected clone proposals, source inventory, family screen,
benchmark screen, prompt-boundary screen, task receipts, Docker receipt, audit
subject, and append-only cycle manifests are separate artifacts below the
family `.state/` directory. Schema-v2 receipts bind every
prompt/starter/reference/test/metadata/provenance/negative role plus compiler
path, version, binary hash, image, and verifier policy. Every
task records clean-room repository authorship, Apache-2.0 terms, new-root
lineage, owner path, selected workflow prompts, and the local-only boundary.

Any owner, curriculum, specification, test, generated artifact, normalizer,
image, or policy change invalidates prior receipts. Only a fresh independent
audit of the exact final regenerated tree may close the creator loop at
`local_family_verified`.

## Required commands

```bash
uv run python -m w8_biayn.integrations.moonlight_calendar_boundary_expansion_aider_tasks \
  --out .w8-biayn/data/aider-tasks-expansion-v1/time-date/calendar-difference-leap-month-end \
  --force --verify-core

uv run python -m w8_biayn.integrations.moonlight_calendar_boundary_expansion_aider_tasks \
  --out .w8-biayn/data/aider-tasks-expansion-v1/time-date/calendar-difference-leap-month-end \
  --verify-host  # host-only campaigns: clean normal + fresh ASan/UBSan, no Docker

uv run python -m w8_biayn.integrations.moonlight_calendar_boundary_expansion_aider_tasks \
  --out .w8-biayn/data/aider-tasks-expansion-v1/time-date/calendar-difference-leap-month-end \
  --docker-sanity --creator-preflight
```

Creator preflight is not admission. It hands an immutable audit subject to a
read-only `audit-sft-data-quality` pass. Findings must be preserved, remedied
through the owner, regenerated, and sent to a fresh audit.

## Non-claims

Completion is no stronger than `local_family_verified`. It does not authorize
JSONL creation, a dataset release, SFT or GRPO, model evaluation, or an uplift
claim.
