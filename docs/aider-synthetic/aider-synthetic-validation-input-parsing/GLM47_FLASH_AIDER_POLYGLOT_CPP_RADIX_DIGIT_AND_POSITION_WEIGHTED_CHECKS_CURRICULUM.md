# Radix, Digit, And Position-Weighted Checks Curriculum: Decontaminated Capability

Status: curriculum-design note. These are original task concepts, not admitted
SFT roots or online-dataset claims.

This curriculum develops symbol validation before arithmetic, wide intermediate
calculations, positional weighting, and canonical numeric representations. It
does not propose a renamed arbitrary-base converter or ISBN/Luhn exercise.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_VALIDATION_AND_INPUT_PARSING_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

The official Aider `all-your-base` holdout, all benchmark roots, and their
semantic copies are excluded. Do not reuse their wording, APIs, examples,
tests, references, or digit/base policy. Each candidate must materially differ
in at least three dimensions: domain, accepted alphabet, numeric model, public
API, output form, check rule, error policy, or query behavior. Apply whole-slug
denylist and semantic contamination checks; reject and backfill near-matches.

## Online Material Status

External checksum and radix exercises are private study or licensed-source
discovery only. Author every surviving C++17 root independently.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `radix-paint-mix-ledger` | Paint-mix ledger | Parse base-12 pigment quantities and total them into a bounded decimal inventory record. |
| `radix-astronomy-star-catalog` | Star-catalog label | Validate a base-36 catalog suffix and compare identifiers without converting an unbounded whole value. |
| `radix-warehouse-pallet-count` | Pallet-count display | Convert bounded base-8 display counts to decimal while preserving a declared zero-display policy. |
| `radix-hex-color-ticket` | Hex color ticket | Validate six or eight hexadecimal channels and produce typed channel values plus alpha defaults. |
| `radix-binary-sensor-flags` | Binary sensor flags | Parse grouped bit flags, reject disallowed group widths, and report enabled named flags. |
| `radix-dice-notation-score` | Dice notation score | Interpret base-6 score strings with exact digit restrictions and checked accumulation. |
| `radix-quinary-route-marker` | Quinary route marker | Canonicalize base-5 route milestones and calculate bounded signed differences. |
| `radix-roman-supply-count` | Roman supply count | Validate a constrained subtractive numeral grammar and emit an integer only for canonical forms. |
| `check-parcel-routing-key` | Parcel routing key | Validate a weighted routing key whose final symbol is drawn from a custom alphabet. |
| `check-badge-parity-strip` | Badge parity strip | Verify grouped binary parity fields and identify the first failing group without repair. |
| `check-invoice-reference` | Invoice reference | Apply alternating positional weights to a fixed-width invoice reference with literal display separators. |
| `check-fuel-coupon` | Fuel coupon token | Validate a coupon body and modulus check symbol, preserving leading-zero semantics. |
| `check-lab-plate-well` | Lab plate well code | Validate row/column positions plus a position-weighted terminal letter. |
| `check-library-card-lite` | Library card token | Enforce an institution prefix and a weighted decimal suffix with exact length rules. |
| `check-shipment-batch` | Shipment batch stamp | Parse a mixed-radix batch stamp and verify its final residue field. |
| `check-weather-balloon-id` | Weather balloon ID | Validate a base-32 payload with excluded visual-confusion symbols and a rolling checksum. |
| `check-archive-page-mark` | Archive page mark | Validate a decimal page range and a check digit whose weights depend on position from the right. |
| `check-bus-transfer-slip` | Bus transfer slip | Validate a short numeric transfer code with a non-Luhn fold rule and expiry class. |
| `check-satellite-packet` | Satellite packet counter | Decode a bounded hexadecimal counter and verify a two-symbol additive check. |
| `check-tool-crib-loan` | Tool-crib loan tag | Validate an alphanumeric loan tag and return both normalized body and check status. |

## Materialization Requirements

Use domain-specific C++17 APIs rather than `convert(digits, from, to)`. Define
alphabet case policy, empty/all-zero behavior, overflow behavior, separator
rules, and exact check-digit direction. Hidden tests must include every radix
edge, invalid symbols, leading zeros, overflow boundaries, misplaced check
symbols, separator abuse, canonical round trips, and randomized oracle checks.

## Admission Boundary

Before release, every root must pass normal licensing, provenance, oracle,
sanitizer, contamination, split, rendering, token/mask, and release gates.
