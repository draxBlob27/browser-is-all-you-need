# Lexical Validation And Canonicalization Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online dataset.

This curriculum develops strict recognition before normalization: a candidate must
belong to its declared language before it can be cleaned up or rendered in a
canonical form. It deliberately avoids a generic phone-number exercise.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_VALIDATION_AND_INPUT_PARSING_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

The official Aider Polyglot C++ `phone-number` task and every other benchmark
holdout are permanently excluded. Do not reuse their wording, API, examples,
tests, references, model outputs, accepted syntax, or normalization policy.
Every root below must differ from excluded families in at least three dimensions:
domain, grammar, public API, canonical output, invalid-input policy, and
cross-field semantics. Run the whole-slug denylist and semantic contamination
checks before admission; reject and backfill every near-match.

## Online Material Status

Online validators are concept study or licensed-source discovery only, never a
drop-in SFT inventory. Each root must be newly authored in C++17 with independent
provenance, text, starter API, reference, examples, and tests.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `lex-vessel-call-sign` | Vessel call-sign registry | Validate a restricted maritime identifier and return its fixed-width uppercase dispatch form. |
| `lex-library-shelf-mark` | Library shelf mark | Parse a collection prefix, decimal class, and optional cutter; emit sortable canonical components. |
| `lex-lab-sample-seal` | Laboratory sample seal | Validate a hyphenated specimen seal with a site prefix and check digit before formatting it. |
| `lex-warehouse-bin-token` | Warehouse bin token | Accept aisle/bay/level notation under exact widths and render a zero-padded storage key. |
| `lex-radio-channel-tag` | Radio channel tag | Validate service band, channel number, and permitted suffix; normalize case and padding. |
| `lex-film-archive-reel` | Film archive reel label | Parse a reel accession with constrained year and sequence fields without silently fixing bad separators. |
| `lex-garden-plot-marker` | Garden plot marker | Validate zone, row, and plant marker syntax, then produce a canonical inventory label. |
| `lex-museum-case-label` | Museum case label | Recognize an exhibit-case code with optional approved revision and reject ambiguous spacing. |
| `lex-freight-container-lite` | Freight container label | Validate a fictional container prefix, serial width, and local checksum; emit compact form. |
| `lex-classroom-seat-ticket` | Classroom seat ticket | Accept only explicit building-room-seat grammar and render a stable seat lookup key. |
| `lex-aquarium-tank-code` | Aquarium tank code | Parse tank family and numeric compartment while enforcing family-specific leading-zero rules. |
| `lex-hiking-trail-permit` | Trail permit token | Validate seasonal prefix, party class, and serial; canonicalize permitted display whitespace only. |
| `lex-rail-yard-track-id` | Rail-yard track identifier | Recognize a yard/track/siding notation and preserve meaningful suffix distinctions. |
| `lex-ambulance-unit-label` | Ambulance unit label | Validate regional unit labels, reject reserved identifiers, and return a dispatch-safe spelling. |
| `lex-orchard-row-tag` | Orchard row tag | Parse cultivar, block, and row fields with an explicit all-zero rejection rule. |
| `lex-theater-seat-pass` | Theater seat pass | Validate section/row/seat notation while canonicalizing allowed case differences. |
| `lex-drone-flight-sticker` | Drone flight sticker | Validate a mission sticker with controlled separators and a non-coercive serial policy. |
| `lex-research-freezer-box` | Research freezer box label | Parse freezer, shelf, box, and cell fields and produce a fixed-width locator. |
| `lex-event-badge-code` | Event badge code | Validate sponsor, attendee class, and sequence while rejecting trailing notes or garbage. |
| `lex-water-meter-label` | Water-meter label | Validate a district meter token and format a canonical readout identifier after complete checks. |

## Materialization Requirements

Every root needs a task-specific C++17 API, not a generic `normalize(string)`
assignment. The starter must expose typed parse result/error state and define
which whitespace, case changes, separators, and leading zeros are legal. Hidden
tests must cover empty input, each grammar boundary, one-rule violations,
trailing garbage, canonical-form idempotence, parse/format round trips where
meaningful, and no partial output after failure. Add randomized valid and
near-valid generators checked against a simple recognizer oracle.

## Admission Boundary

This document does not bypass the primary Aider SFT pipeline. Every candidate
must pass licensing, provenance, compiler-image, oracle, sanitizer,
contamination, split-family, rendering, token/mask, and release verification.
