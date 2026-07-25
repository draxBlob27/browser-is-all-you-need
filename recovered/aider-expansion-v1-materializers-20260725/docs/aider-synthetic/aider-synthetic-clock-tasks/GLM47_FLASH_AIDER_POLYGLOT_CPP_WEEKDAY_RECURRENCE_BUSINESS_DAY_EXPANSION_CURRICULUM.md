# Weekday, Recurrence, And Business-Day Expansion Curriculum

Status: implementation contract for 90 clean-room local task roots. These roots
are candidate task artifacts only. This document does not create SFT rows,
authorize training, or claim benchmark uplift.

## Count-plan identity and holdout boundary

This family implements the complete 90-root cell named “Weekday, nth/final
occurrence, recurrence, and business-day rules” in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`. It creates
exactly 30 weekday roots, 30 recurrence roots, and 30 business-day roots under
`.w8-biayn/data/aider-tasks-expansion-v1/time-date/weekday-recurrence-business-day/`.
Every root has `lineage: new-root`. The owner inventories both pre-existing
generated trees and refuses any ID or semantic-lineage overlap before writing.

The official Aider C++ tasks, especially `meetup`, `clock`, and `gigasecond`,
remain permanent holdouts. No benchmark prompt, API, test, reference, response,
or close semantic contract is an input. These tasks generate complete serial-day
windows from caller-supplied bounds, rule state, and explicit exclusions; none asks for
a Gregorian “nth weekday in a month” answer.

## Three independently observable eligibility models

All tasks use a `CalendarRequest` with an inclusive `start_day`/`end_day`
window, strictly increasing duplicate-free `exclusions`, and `primary`,
`interval`, and `parameter`. Endpoints and exclusions are restricted to
`[-100000,100000]`; windows contain 1–512 days; `parameter` is `[1,64]`.
Invalid requests return `std::nullopt` without partial output. A valid window
with no qualifying occurrence returns an engaged empty vector unless the
operation explicitly defines another empty result. Those public bounds make
every reference intermediate safe in signed `int`.

- `weekday-*`: compute weekday occurrences inside the bounded reporting window
  by floor-modulo-seven equality with `primary` in `[0,6]`. First, final, nth,
  reverse-nth, and absence roots cover occurrence behavior without reproducing
  Gregorian month APIs from the `meetup` holdout.
- `recurrence-*`: generate an on-or-after anchored arithmetic recurrence over
  the complete bounded window with `primary` in `[-100000,100000]` and positive `interval`, then apply explicit
  count/window/exclusion/intersection behavior.
- `business-day-*`: generate open days from the seven-bit workweek mask
  `primary` in `[1,127]` and explicit closures. First/nth and final/reverse-nth
  roots implement forward and backward business-day offsets within the window.

Every operation then applies its own direct algorithm. The reference must not
use host date/time APIs, a generic runtime mode switch, a precomputed result,
or official benchmark assets. Exclusions are material behavior, not metadata.

## Operation inventory

For every operation slug below the owner emits the three roots
`weekday-<slug>`, `recurrence-<slug>`, and `business-day-<slug>`. Thus this
table specifies all 90 stable task IDs. The output is an integer vector whose
contract is named below; pair/triple outputs are flattened in stable order.

| Slug | Required core mechanism | Output contract |
| --- | --- | --- |
| `first-occurrence` | bounded first-occurrence selection | first occurrence or empty |
| `final-occurrence` | bounded final-occurrence selection | final occurrence or empty |
| `nth-occurrence` | one-based nth-occurrence selection | parameter-th occurrence or empty |
| `nth-from-end` | one-based reverse occurrence selection | reverse parameter-th occurrence or empty |
| `occurrence-exists` | bounded occurrence-existence decision | `{1}` or `{0}` |
| `rolling-density` | fixed-width rolling density | window hit counts |
| `bounded-batches` | bounded batch endpoint partition | batch endpoint pairs |
| `stable-overlay` | stable two-stream overlay | tagged merged serials |
| `exclusion-intersection` | raw-rule/exclusion intersection | excluded raw matches |
| `symmetric-calendar` | rule/exception symmetric difference | tagged difference |
| `forward-expansion` | bounded forward occurrence expansion | deduplicated expanded days |
| `anchored-shift` | checked anchor shift and deduplication | shifted days |
| `nearest-index` | deterministic exhaustive nearest eligible lookup | query/day pairs |
| `exception-ranks` | lower-bound rank queries | query/rank pairs |
| `weekday-quota` | per-weekday bounded quota allocation | admitted days |
| `capacity-spill` | bucket capacity and spill ledger | day/spill-rank pairs |
| `transition-edges` | eligibility transition detection | transition days |
| `longest-streak` | longest consecutive eligible streak | start/length pair |
| `cyclic-rotation` | normalized cyclic rotation | rotated eligible sequence |
| `period-buckets` | floor-division period aggregation | bucket/count pairs |
| `pair-distances` | adjacent eligible-pair distance scan | left/distance pairs |
| `missing-slots` | bounded missing-slot reconstruction | absent expected days |
| `arithmetic-compression` | maximal arithmetic-run compression | start/step/count triples |
| `exception-substitution` | monotone exception replacement | substituted days |
| `collision-resolution` | forward open-address collision resolution | resolved slots |
| `checkpoint-sampling` | ordinal checkpoint sampling | every kth eligible day |
| `coverage-union` | interval expansion and union | merged endpoint pairs |
| `parity-lanes` | stable even/odd weekday partition | even lane then odd lane |
| `distance-score` | bounded distance-weight scoring | day/score pairs |
| `dual-rule-consensus` | conjunctive primary/secondary consensus | consensus days |

## Required per-root evidence

The public instructions state the exact selector, operation, validation,
ordering, and output shape. The task-named header/source are the only editable
files. Complete replacements live under `.meta/example.*`; visible and hidden
tests are deterministic and include negative serial days, exclusions, stable
ordering, exact operation-specific empty/absent results, invalid endpoints/selectors/intervals/masks,
duplicate and unsorted exclusions, parameter boundaries, and supported-range
boundaries, including exact and out-of-range recurrence anchors. Two compiled
false substitutes respectively invert raw eligibility and return a nonempty
marker when no raw occurrence exists; both must be rejected by executed tests.

The owner compares all `90 * 89 / 2 = 4,005` pairs in all seven hard
dimensions using identifier/literal/endpoint-neutral seven-gram containment
over emitted instructions, API, reference control flow, visible/private oracle,
and negative source. Every dimension must pass the recorded threshold for
every pair. It also materializes internally buildable domain/identifier,
constant/policy-only, and opposite-end controls and requires the production
screen to reject each in every dimension.

Creator preflight requires the exact pinned, network-disabled Docker sanity
image, two positive and equal normal/fresh ASan+UBSan CTest discoveries per
root, passing references in both modes, and 180 compiling but failing negative
fixtures. The receipt retains per-root/mode/source-role results and binds
source inventories, owner, curriculum, spec,
focused tests, prompts, starters, references, tests, metadata, image, compiler
path/version/hash, CMake version, policy, tree/archive/mount hashes, and
outcomes. When a campaign's gate is host verify only, the owner's
`--verify-host` mode produces the same per-root clean-normal and fresh
ASan/UBSan reference evidence plus executed negative-fixture rejection on the
host `cmake`/`c++` toolchain, receipted in `.state/host-verify.json` bound to
the current owner and tree; the strongest status that evidence supports is
`campaign_verified_host_only`, never `local_family_verified`.

## Candidate, control, and rejection separation

Only directories containing a real `.meta/config.json` directly beneath the
family root count as retained candidates. Mutable inventories, receipts,
adversarial controls, audit reports, and remedy records live beneath `.state/`
and never count. Rejected or replaced proposals must be preserved in cycle
records and quarantined below `.state/rejected/`; they must not remain in the
active task-root inventory or retained manifest. The five superseded operation
IDs per selector group are explicitly mapped to their replacement anchors.
Any count shortfall is
backfilled with a genuinely new contract and sent through the complete
creator-audit-remediation-re-audit loop.

## Non-claims

`local_family_verified` is the strongest possible conclusion. It does not
mean dataset admission, a JSONL projection, token/mask evidence, a split,
release readiness, training authorization, or benchmark uplift.
