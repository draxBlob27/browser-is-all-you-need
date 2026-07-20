# Pattern Printing Remediation Curriculum

Status: v4 `local_family_verified`. Dataset handoff is `not_requested`.

This curriculum follows
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with
`FAMILY_NAME=pattern-printing` and
`FAMILY_TYPE=aider-text-grid-reshaping`. The 20 legacy roots remain immutable
under `.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/pattern-printing/`.
The owner writes only the parallel family under
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/pattern-printing/`.

## Weakness and clean-room objective

The legacy family advertised theater, truss, pennant, canopy, bracket, beam,
quilt, crate, trellis, countdown, rink, and support mechanisms, but every
reference reduced to the same centered odd-width span. Ten roots used a solid
fill and ten changed only one parity predicate. Their APIs, validation rules,
tests, and diagnostic fields were otherwise noun-renamed copies. The primary
core objectives were therefore `not_achieved` despite host-buildable files.

The v4 objective is to teach twenty independently testable pattern-rendering
mechanisms. Every counted root differs in public API, input state, invalid and
boundary behavior, reference control flow, output construction, diagnostic
oracle, and executed false substitute. The family is local candidate material
only and does not authorize SFT rows, training, release, or uplift claims.

## Permanent holdout boundary

All 26 official Aider Polyglot C++ roots are permanent holdouts. In particular,
`diamond` wording, API, examples, tests, reference control flow, and semantic
contract are excluded. The v4 family uses domain records, variable input state,
diagnostic ledgers, and mechanisms other than alphabetic diamond generation.
The owner compares emitted docs, API, reference, visible tests, and private
tests against the bound 26-root checkout after identifier, literal, domain,
and endpoint normalization.

## Deterministic dispositions and v4 inventory

The lexicographically smallest legacy root with a recoverable independent
objective is repaired in place. The other nineteen roots are semantic/template
duplicates and therefore receive `replace` dispositions and new IDs.

| Legacy root | Disposition | v4 root | Required mechanism |
|---|---|---|---|
| `pattern-archway-stones` | repair-in-place | `pattern-archway-stones` | squared-distance semicircular voussoir band |
| `pattern-theater-seating` | replace | `seat-band-capacity-chart` | variable band capacities split by a fixed aisle |
| `pattern-ski-trail-sign` | replace | `ski-chevron-route-sign` | ordered signed chevron offsets plus legend |
| `pattern-roof-trusses` | replace | `roof-truss-bay-lattice` | repeated triangular bays with shared joints |
| `pattern-festival-bunting` | replace | `cyclic-pennant-bunting` | cyclic-palette tapered pennant raster |
| `pattern-orchard-canopy` | replace | `orchard-canopy-union` | multi-source Manhattan-radius union and overlap |
| `pattern-signal-cones` | replace | `striped-cone-stencil` | outline plus tip-anchored periodic stripe fills |
| `pattern-tournament-bracket` | replace | `elimination-bracket-connectors` | power-of-two sparse round connectors |
| `pattern-mountain-profile` | replace | `ridge-height-silhouette` | bottom-aligned height-column surface raster |
| `pattern-lighthouse-beam` | replace | `occluded-lighthouse-fan` | integer-slope first-obstacle ray casting |
| `pattern-quilt-medallion` | replace | `concentric-quilt-rings` | rectangular inset-distance palette rings |
| `pattern-pyramid-crates` | replace | `labeled-crate-pyramid` | token-width-aware centered tier composition |
| `pattern-garden-trellis` | replace | `blocked-trellis-vines` | two modular diagonal phases with blocked cells |
| `pattern-snowflake-banner` | replace | `eight-ray-snowflake-banner` | axial/diagonal odd-square ray overlay |
| `pattern-warehouse-stacks` | replace | `warehouse-aisle-run-map` | non-overlapping aisle-run placement plus empty-aisle ledger |
| `pattern-launch-countdown` | replace | `seven-segment-countdown-strip` | descending five-row glyph composition |
| `pattern-choir-riser` | replace | `choir-riser-voice-allocation` | ordered run consumption over ragged capacities |
| `pattern-harbor-beacons` | replace | `harbor-beacon-cadence` | dual modular flash streams and coincidences |
| `pattern-ice-rink-lines` | replace | `ice-rink-zone-overlay` | precedence-ordered boards/lines/spots overlay |
| `pattern-cave-supports` | replace | `cave-brace-triangulation` | anchor generation and alternating interpolation |

Rejected legacy proposals remain accounted for by their remedy records; they
are not copied or renamed into the v4 family.

## Family hard-diversity contract

The owner must reread the actual emitted artifacts and compare all 190
unordered root pairs separately across all seven required dimensions: public
API; owned state or algorithm; mutation and selection rules; invalid and
boundary behavior; reference control flow; deterministic oracle; and
topic-specific negative fixture. Every dimension must pass for every pair.
Unique IDs, labels, raw hashes, declared signatures, or profile tags are not
evidence. The comparison removes comments, strings, numeric literals,
clean-room domain nouns, identifiers, and endpoint direction while preserving
API arity and type shape, operators, control flow, standard algorithm calls,
assertions, and oracle structure. The false substitute is isolated to its own
dimension so it cannot manufacture diversity in the other six.

Focused tests must prove the production comparison rejects:

- a complete domain/identifier-renamed clone;
- a constants-or-policy-only clone; and
- an opposite-end-selection clone.

Every root also emits one compilable topic-specific false substitute. The
substitute executes under the same strict flags and must be rejected by its
designated test. A source grep, compile failure, or unexecuted fixture is not
evidence.

## Prompt, role, and oracle contract

Only `.docs/*.md` and the task-named header/source reach the prompt. The
header/source are the complete ordered editable allowlist. References, visible
and private tests, negative fixture, provenance, CMake, receipts, manifests,
and remedy records remain private. Example files map one-to-one by suffix and
order to both editable files.

The owner-controlled verifier uses C++17, explicit `Unix Makefiles`, strict
warnings, and the pinned repository sanity image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with `--network none`. Each root must discover three tests in a clean normal
build and the same three tests in a fresh ASan/UBSan build. The negative target
must exit 1 with no diagnostic output in both modes. The receipt binds the
deterministic archive, live and independently mounted tree hashes, owner/case
revision, reference hashes, image identity, compiler and CMake identities,
commands, counts, outcomes, and network policy. Because no family-designated
locked grader exists, the evidence class is `docker_sanity`, not
`locked_oracle`.

## Completion gate

`local_family_verified` requires generator-owned regeneration, complete remedy
records/specifications, prompt and role validation, reference mapping, twenty
executed negative fixtures, all seven dimensions passing in all 190 family
comparisons, coherent rejection of all three required clone classes, 520
passing official-holdout comparisons, and the pinned network-disabled normal
plus fresh ASan/UBSan receipt. The v4 receipt binds the hard-rule screen hash.
Host verification is iteration evidence only. Any owner, case, generated-tree,
compiler/image, or screening-policy change invalidates earlier receipts and
returns records to `planned`.
