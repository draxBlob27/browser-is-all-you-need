# Sequence Pattern Curriculum: Decontaminated Sublist Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

The official Aider Polyglot C++ `sublist` task is a permanent benchmark
holdout. This document does **not** propose renamed exercises that classify two
lists as equal, sublist, superlist, or unequal. It targets broader ordered
sequence reasoning through distinct matching, alignment, span, and policy
contracts.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

Do not use the holdout task's wording, API, data model, examples, tests,
reference implementation, or four-way relationship classification. Do not
construct a source candidate by paraphrasing or translating the holdout.

Each candidate below must be independently authored from a new behavior
specification and must materially differ in at least three of these dimensions:

- input structure, such as tokens, events, typed records, or normalized text;
- matching mode, such as wildcard, tolerance, case folding, gaps, or overlap;
- returned result, such as spans, counts, diagnostics, alignment, or a policy
  decision rather than list relationship classification;
- mutation, stream, multi-pattern, or query semantics;
- visible C++ API, error behavior, and ordering rules.

Before admission, run the repository's whole-slug benchmark denylist and
semantic contamination checks against all official Aider C++ roots. A
near-match, including any straightforward two-list relationship classifier, is
rejected. Preserve rejection evidence and backfill with a new independently
designed candidate; never weaken the checker.

## Online Material Status

Sequence-matching problems are available online, but they are useful only for
private concept study or source discovery. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `seq-audit-signature` | Audit signature finder | Return all spans where a typed audit-event signature occurs in an event stream. |
| `seq-dna-motif` | DNA motif locator | Find DNA motif offsets with IUPAC wildcard symbols and overlapping matches. |
| `seq-command-policy` | Command policy checker | Detect forbidden consecutive command patterns and return the first violation diagnostic. |
| `seq-playlist-excerpt` | Playlist excerpt alignment | Locate a clip sequence in a playlist after case-normalizing track IDs. |
| `seq-sensor-anomaly` | Sensor anomaly signature | Find a tolerance-based numeric pattern in a rolling sensor stream. |
| `seq-shipment-checkpoints` | Shipment checkpoint verifier | Verify required checkpoint order with allowed timestamp gaps and report missing transition. |
| `seq-log-phrase` | Log phrase matcher | Find token phrases after punctuation folding and return line/column spans. |
| `seq-ui-workflow` | UI workflow detector | Detect an allowed or forbidden interaction trace while ignoring benign events. |
| `seq-factory-cycle` | Factory cycle detector | Count repeated production-stage cycles with overlap and reset semantics. |
| `seq-network-handshake` | Network handshake verifier | Match a typed protocol handshake and explain the first mismatched field. |
| `seq-route-detour` | Route detour detector | Find a contiguous detour segment in a route using location IDs and direction flags. |
| `seq-medication-schedule` | Medication schedule check | Detect prohibited consecutive dose classes under a time-window rule. |
| `seq-price-pattern` | Price pattern scanner | Report all windows matching relative up/down/equal movement symbols. |
| `seq-document-template` | Document template matcher | Locate a normalized heading sequence and return the best matching section span. |
| `seq-access-escalation` | Access escalation detector | Identify privilege-event sequences that require review and return implicated IDs. |
| `seq-game-combo` | Game combo recognizer | Recognize input combos with wildcard buttons and choose the longest valid match. |
| `seq-support-macro` | Support macro detector | Detect repeated response macros in a ticket conversation while skipping quoted text. |
| `seq-assembly-inspection` | Assembly inspection | Match an inspection-step pattern with optional steps and return a pass/fail reason. |
| `seq-currency-arbitrage` | Currency quote pattern | Detect a prescribed directional pattern across a sequence of exchange quotes. |
| `seq-version-migration` | Version migration checker | Validate required migration steps and report the first missing or out-of-order step. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a generic
two-vector relationship classifier. The input normalization, result type,
matching rule, invalid-input behavior, and ordering/tie policy must be part of
the starter interface and materially different between roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- empty streams and task-specific empty-pattern semantics;
- first, last, adjacent, and overlapping valid matches;
- no match, multiple matches, and deterministic span ordering;
- normalization, wildcard, tolerance, optional-step, or ignored-event rules
  where applicable;
- malformed typed events and no-state-mutation behavior for streaming tasks;
- boundary spans at the beginning and end of input;
- large adversarial inputs that distinguish intended linear/near-linear matching
  from pathological repeated rescans where the task specifies a complexity goal;
- randomized cases checked against a straightforward task-specific oracle;
- a final contamination screen proving the candidate remains outside the
  benchmark holdout family.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
