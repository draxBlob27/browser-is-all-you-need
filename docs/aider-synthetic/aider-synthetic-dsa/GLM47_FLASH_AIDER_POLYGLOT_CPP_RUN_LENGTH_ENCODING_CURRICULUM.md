# Run-Length Encoding Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum targets stateful run grouping, canonical encoding, decoding,
stream boundaries, validation, and domain-specific aggregation. It does **not**
propose renamed copies of a generic character-string run-length codec.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

The official Aider C++ benchmark holdout set remains excluded in its entirety.
Do not use any holdout wording, APIs, classes, field names, examples, tests,
references, or model outputs. Do not construct a candidate by paraphrasing an
online run-length-encoding exercise.

The existing repository source inventory also contains a `run-length-encoding`
root. Do not derive these candidates from that root, its scaffold, its tests,
or its reference. Treat it as an excluded source family for this curriculum.

Each candidate below must be independently authored and materially differ from
all excluded roots in at least three dimensions: input domain, encoding format,
run boundary rule, stream/chunk behavior, error/validation policy, output
representation, aggregation/query semantics, and visible C++ API. Run the
repository's whole-slug benchmark denylist and semantic contamination checks
before admission. Reject and backfill every near-match; do not weaken the
checker.

## Online Material Status

Run-length-encoding examples are available online, but they are useful only for
private concept study or source discovery. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `rle-telemetry-packets` | Telemetry packet codec | Encode repeated sensor states into bounded-count packets and split runs above 255. |
| `rle-monochrome-raster` | Monochrome raster codec | Encode/decode binary image rows with required row boundaries and pixel totals. |
| `rle-dna-quality` | DNA-quality compressor | Group repeated quality scores while preserving ambiguous-base markers. |
| `rle-log-severity-spans` | Log severity spans | Convert event severities into timestamped runs and query longest warning span. |
| `rle-video-frame-holds` | Video frame holds | Compress repeated frame hashes and reject invalid frame-duration totals. |
| `rle-traffic-lights` | Traffic-light timeline | Group signal phases, merge adjacent compatible phases, and calculate phase durations. |
| `rle-factory-defects` | Factory defect runs | Encode inspection outcomes and report the first run exceeding a defect threshold. |
| `rle-audio-silence` | Audio silence spans | Identify amplitude-class runs with tolerance bucketing and return silent spans. |
| `rle-weather-stations` | Weather status timeline | Compress status readings across input chunks while retaining a carry-over final run. |
| `rle-network-flags` | Network flag codec | Encode repeated bit-flag sets and validate a compact binary record format. |
| `rle-inventory-shelves` | Inventory shelf runs | Group adjacent empty/occupied shelf slots and return available run lengths. |
| `rle-document-whitespace` | Document whitespace formatter | Canonicalize whitespace runs while respecting protected verbatim regions. |
| `rle-game-terrain` | Game terrain map | Decode terrain runs into a rectangular map and reject row-width mismatches. |
| `rle-medication-adherence` | Medication adherence spans | Group daily adherence states and return missed-dose streak diagnostics. |
| `rle-power-modes` | Power-mode trace | Encode power-mode changes, coalesce zero-duration events, and calculate energy per mode. |
| `rle-chat-reactions` | Chat reaction clusters | Group adjacent matching reactions and select the largest cluster with stable ties. |
| `rle-bus-occupancy` | Bus occupancy trace | Convert passenger-count samples into plateau runs and find longest full-capacity period. |
| `rle-barcode-scans` | Barcode scan batches | Compress repeated scan IDs, reject zero counts, and decode partial batches safely. |
| `rle-access-badges` | Access-badge runs | Group consecutive access results and flag repeated denial runs by door. |
| `rle-pricing-bands` | Pricing-band timeline | Compress consecutive equal prices and answer price-at-offset queries without full expansion. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a generic
`encode(string)` / `decode(string)` assignment. Include the typed input model,
count limit, boundary behavior, validation/error policy, and domain query or
aggregate in the starter interface.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- empty input and singleton runs;
- runs at count one, maximum encodable count, and one above that count;
- consecutive compatible runs that must merge and incompatible runs that must
  remain separate;
- chunk boundaries that divide one logical run;
- malformed counts, truncated records, invalid symbols, and no-state-mutation
  behavior where the task is mutable;
- encode/decode round trips plus canonical-form checks where applicable;
- domain aggregates such as durations, row widths, offsets, or longest runs;
- randomized cases checked against a straightforward expanded-sequence oracle;
- a final contamination screen proving the candidate remains outside benchmark
  and excluded-source families.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
