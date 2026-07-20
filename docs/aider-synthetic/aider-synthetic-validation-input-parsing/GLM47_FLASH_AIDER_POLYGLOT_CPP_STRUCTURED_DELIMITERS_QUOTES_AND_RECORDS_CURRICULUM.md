# Structured Delimiters, Quotes, And Records Curriculum: Decontaminated Capability

Status: curriculum-design note. The concepts below are not admitted roots or
claims of online availability.

This curriculum targets explicit parser states, record structure before field
typing, nesting, and exact end-of-input checks. It avoids a generic CSV or JSON
parser assignment.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_VALIDATION_AND_INPUT_PARSING_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

All official Aider benchmark roots and close semantic copies are excluded. Do
not paraphrase an online CSV/JSON exercise. Each candidate must differ in at
least three dimensions: domain, delimiter grammar, quoting/escaping policy,
nesting model, typed schema, output representation, diagnostics, and public
API. Enforce the repository denylist and semantic screen before admission.

## Online Material Status

Online parser examples are study material or licensed-source leads only. Build
independent C++17 task text, API, reference, tests, and provenance.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `record-harbor-manifest` | Harbor manifest row | Parse pipe-delimited cargo records with quoted notes and typed weight fields. |
| `record-greenhouse-schedule` | Greenhouse schedule | Validate semicolon records with escaped labels and required irrigation ranges. |
| `record-library-import` | Library import line | Parse tab-delimited metadata where quoted titles may contain tabs and doubled quotes. |
| `record-clinic-intake` | Clinic intake packet | Parse a small key/value packet with required keys, duplicate-key rejection, and typed dates. |
| `record-kitchen-order` | Kitchen order ticket | Recognize nested modifier lists in a compact order grammar and reject unmatched brackets. |
| `record-ferry-booking` | Ferry booking feed | Parse comma records with quoted passenger fields and a declared column count. |
| `record-survey-response` | Survey response bundle | Parse JSON-lite answers with strings, booleans, and bounded arrays under a fixed schema. |
| `record-utility-meter-batch` | Utility meter batch | Parse newline records, tolerate final newline only, and reject a second value after each record. |
| `record-school-attendance` | Attendance import | Validate colon-separated rows with empty-but-present status fields and typed identifiers. |
| `record-drone-mission-plan` | Drone mission plan | Parse nested waypoint lists with a maximum depth and explicit trailing-token rejection. |
| `record-theater-cast-sheet` | Theater cast sheet | Parse slash-delimited roles with quoted alternate names and no whitespace coercion. |
| `record-warehouse-adjustment` | Warehouse adjustment | Parse action records and reject duplicate fields or quantities with invalid signs. |
| `record-weather-observation` | Weather observation | Parse compact key/value observations with literal escapes and enumeration validation. |
| `record-insurance-note` | Insurance note fragment | Extract structured fields from a bracketed mini-language while retaining free-text quotes. |
| `record-lab-reagent-log` | Reagent log row | Parse a typed row with optional concentration only when units are present. |
| `record-bus-timetable` | Bus timetable record | Parse stop lists separated by arrows while quoted stop names may contain arrow characters. |
| `record-museum-loan-form` | Museum loan form | Parse multiline sections with exact section ordering and required terminators. |
| `record-farm-delivery` | Farm delivery note | Parse nested crate entries with counts and reject malformed closing delimiters. |
| `record-voting-ballot` | Voting ballot payload | Parse a constrained object with unique choices, bounded nesting, and exact EOF. |
| `record-repair-work-order` | Repair work order | Parse typed fields after structural validation and return stable first-error locations. |

## Materialization Requirements

Expose a domain parser/result API, not `split` or a generic JSON decoder. Define
the finite-state grammar, escaping, empty-versus-missing distinction, duplicate
policy, maximum nesting, allowed trailing whitespace, and diagnostic precedence.
Hidden tests must cover quoted separators, escaped quotes, unterminated fields,
malformed delimiters, extra records, empty containers, depth limits, field-type
failures, and randomized valid records checked by a small reference state machine.

## Admission Boundary

All roots remain subject to licensing, provenance, compiler-image, oracle,
sanitizer, contamination, split, rendering, token/mask, and release checks.
