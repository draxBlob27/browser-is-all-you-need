# Run-Length Encoding Curriculum: Decontaminated Capability

Status: locally remediated and Docker-sanity verified. The 20 v2 roots are
generated only beneath the parallel re-verification tree and remain local task
artifacts; this document does not claim SFT admission, a dataset release,
training authorization, or benchmark uplift.

This curriculum targets stateful run grouping, canonical encoding, decoding,
stream boundaries, validation, and domain-specific aggregation. It does **not**
propose renamed copies of a generic character-string run-length codec.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

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

The legacy 20-root materialization is audit input only. It emitted one renamed
bounded-run template and is preserved unchanged. The v2 owner retains and
repairs the lexicographically smallest independently justified representative,
replaces the other 19 roots with new IDs, and enforces task-specific APIs,
state, control flow, tests, and negative fixtures.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `rle-access-badges` | Access badge denial tracker | Maintain independent per-door streams and stable longest-denial selection. |
| `packet-run-stream` | Packet run stream | Emit capped packets through distinct pending and completed state. |
| `raster-row-runs` | Raster row runs | Encode binary rows without allowing a run to cross a row boundary. |
| `quality-delta-runs` | Quality delta runs | Compress repeated signed differences and range-check reconstruction. |
| `severity-time-spans` | Severity time spans | Merge only timestamp-contiguous severity intervals and query duration. |
| `frame-duration-runs` | Frame duration runs | Coalesce equal frame hashes under a duration cap and answer time offsets. |
| `signal-phase-coalescer` | Signal phase coalescer | Validate legal cycle transitions before coalescing phase durations. |
| `defect-threshold-index` | Defect threshold index | Record the earliest start at which each defect-run length is first reached. |
| `amplitude-tolerance-runs` | Amplitude tolerance runs | Bucket samples against a fixed first-sample representative. |
| `station-chunk-carry` | Station chunk carry | Validate chunks atomically and merge them through an explicit live carry. |
| `flag-record-decoder` | Flag record decoder | Parse and canonicalize big-endian count triples with a total bound. |
| `shelf-gap-index` | Shelf gap index | Split and merge maximal free intervals under occupy/release mutations. |
| `protected-whitespace-runs` | Protected whitespace runs | Canonicalize unprotected whitespace while copying protected bytes exactly. |
| `terrain-row-decoder` | Terrain row decoder | Validate row indices, exact widths, canonical runs, and checksums. |
| `adherence-calendar-streaks` | Adherence calendar streaks | Break missed streaks at taken doses and calendar gaps. |
| `power-energy-runs` | Power energy runs | Preserve exact energy numerators while coalescing equal mode/power events. |
| `reaction-cluster-editor` | Reaction cluster editor | Insert and erase expanded ranges while restoring canonical neighboring runs. |
| `occupancy-plateau-index` | Occupancy plateau index | Close timestamped plateaus and select the longest full-capacity period. |
| `barcode-batch-cursor` | Barcode batch cursor | Decode bounded pieces of canonical runs without full expansion. |
| `price-offset-index` | Price offset index | Maintain exclusive prefix ends and answer offsets by binary search. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a generic
`encode(string)` / `decode(string)` assignment. Include the typed input model,
count limit, boundary behavior, validation/error policy, and domain query or
aggregate in the starter interface.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests and the owner-controlled family screen cover:

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

Every root additionally compiles an incomplete topic substitute and requires
the hidden behavioral test to reject it. The family screen rereads the actual
emitted docs, public header, mapped references, visible/private tests, and bad
substitute. It compares all 190 unordered pairs across public API, owned
state/algorithm, mutation/selection, invalid/boundary behavior, reference
control flow, deterministic oracle, and topic-specific negative-fixture
evidence. The bad substitute is excluded from the combined primary-logic
corpus, so negative-fixture changes cannot rescue duplicated core logic.
Production-screen tests copy an emitted root, apply each required
domain/identifier-renamed, constants/policy-only, and opposite-end-selection
clone mutation, and require `duplicate_family`. The same screen covers all
20 × 26 official-holdout pairs.

Every stateful hidden oracle invokes every emitted public operation and uses
an independent expected value/vector model to compare the complete public
state, ordering, and query results after each mutation. The owner fails closed
with `trace_contract_incomplete` if an emitted operation or state-oracle
contract is removed.

## Materialization And Evidence

The owner is
`src/w8_biayn/integrations/moonlight_run_length_encoding_aider_tasks.py`, with
task contracts in `moonlight_run_length_encoding_cases.py`. Materialize only
the parallel tree:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_run_length_encoding_aider_tasks.sh \
  --force --verify-core --verify
```

The legacy root at `.w8-biayn/data/aider-tasks/aider-dsa/run-length-encoding/`
is immutable. The v2 root is
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/run-length-encoding/`.

The pinned `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
image ran with networking disabled. All 20 references passed three clean normal
and three fresh ASan/UBSan CTests with equal positive discovery counts. The
current family result is `local_family_verified` with evidence class
`docker_sanity`; the earlier declaration-derived receipt is invalid and
`locked_oracle` remains false. See
`docs/aider-tasks-spec/aider-dsa/run-length-encoding.md` for findings,
dispositions, hashes, screens, and receipt identity.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
