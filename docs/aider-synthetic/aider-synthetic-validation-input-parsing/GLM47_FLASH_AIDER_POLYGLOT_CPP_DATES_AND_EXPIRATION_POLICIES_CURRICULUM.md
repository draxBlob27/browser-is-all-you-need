# Dates And Expiration Policies Curriculum: Decontaminated Capability

Status: curriculum-design note. It proposes original task concepts; it does not
claim that any concept is an admitted SFT root or an online dataset.

This curriculum develops strict date syntax, deterministic injected reference
dates, month-boundary policy, and cross-field expiry decisions. It deliberately
avoids generic date arithmetic, future-date, or credit-card validation tasks.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_VALIDATION_AND_INPUT_PARSING_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

The official Aider holdouts, including date-related families, and every close
semantic copy are excluded. Do not reuse their wording, APIs, types, examples,
tests, references, or model outputs. A candidate must differ in at least three
dimensions: domain, public API, input representation, calendar rule, output,
reference-time policy, and diagnostic behavior. Apply whole-slug denylist and
semantic contamination checks; reject and backfill near-matches.

## Online Material Status

Online expiry/date validators are study or licensed-source discovery only. Each
candidate must be independently authored in C++17 with original provenance and
test assets.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `expiry-vaccine-vial` | Vaccine vial release | Validate lot expiry month/year against an injected clinic date and return release status. |
| `expiry-library-hold` | Library hold expiry | Validate a pickup date and decide whether a hold survives through its stated closing date. |
| `expiry-trail-permit-window` | Trail permit window | Validate permit dates and determine whether a hike date lies in its inclusive season. |
| `expiry-lab-reagent-shelf-life` | Reagent shelf life | Parse a batch date and shelf-life policy, rejecting invalid calendar fields before comparison. |
| `expiry-ferry-ticket` | Ferry ticket validity | Validate a sailing-date ticket with explicit same-day cut-off policy and injected reference time. |
| `expiry-food-pantry-stock` | Pantry stock rotation | Parse best-before month labels and classify stock as current, expiring, or retired. |
| `expiry-safety-inspection` | Safety inspection certificate | Validate inspection and renewal dates with a fixed grace-month policy. |
| `expiry-rental-equipment-tag` | Equipment rental tag | Validate a due date and report overdue status against a supplied calendar date. |
| `expiry-museum-loan` | Museum loan window | Validate start/end dates and decide whether an exhibit may remain on display. |
| `expiry-seed-packet` | Seed packet viability | Parse a season/year label and classify viability under a documented year-rollover policy. |
| `expiry-water-filter-cartridge` | Filter cartridge service | Validate install date and replacement interval, including month-end boundaries. |
| `expiry-school-medication` | School medication authorization | Validate authorization start/end dates and reject reversed or malformed intervals. |
| `expiry-warehouse-lease` | Warehouse lease notice | Validate lease dates and decide notice eligibility using an injected reference date. |
| `expiry-parking-pass` | Parking pass period | Parse month/year pass labels and test admission at first, middle, and final calendar day. |
| `expiry-archive-embargo` | Archive embargo release | Validate a release date and classify a request without consulting the host clock. |
| `expiry-boat-registration` | Boat registration renewal | Validate registration month and renewal-year policy with explicit two-digit-year rejection. |
| `expiry-orchard-spray-license` | Spray license validity | Validate season-bound licence dates and a grace period that cannot cross a policy cut-off. |
| `expiry-donation-voucher` | Donation voucher redemption | Validate issue/expiry pair and reject an expiry earlier than issue. |
| `expiry-facility-access-badge` | Facility badge access | Validate date fields and determine access through the final day of the printed month. |
| `expiry-conference-credential` | Conference credential window | Validate event and credential periods with deterministic boundary diagnostics. |

## Materialization Requirements

Expose domain-specific C++17 APIs with an injected reference date/clock; never
consult the host system clock. Define accepted date grammar, leap-year behavior,
two- versus four-digit year policy, inclusive/exclusive ends, and deterministic
diagnostics. Hidden tests must cover malformed fields, leap days, month zero and
thirteen, current/previous/next month, year rollover, reversed intervals,
month-end expiry, and randomized cases checked against a small calendar oracle.

## Admission Boundary

Every root remains subject to licensing, provenance, compiler-image, oracle,
sanitizer, contamination, split-family, rendering, token/mask, and release gates.
