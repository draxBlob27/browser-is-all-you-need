# Sparse Matrix Encoding Curriculum: Remediated Capability Family

Status: `local_family_verified` with `docker_sanity` evidence. Dataset handoff
is `not_requested`.

This curriculum follows
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` for
`FAMILY_NAME=sparse-matrix-encoding` and
`FAMILY_TYPE=aider-text-grid-reshaping`. The 20-root legacy family remains
immutable under `.w8-biayn/data/aider-tasks/`; the owner writes v2 roots only
under `.w8-biayn/data/aider-tasks-reverify/`.

## Legacy finding and disposition

The legacy owner rendered one dense reconstruction/row-total algorithm with
domain nouns and four duplicate policies. It did not implement published
objectives such as free-run selection, nearest vacancy, constellation bounds,
shoreline contact, or maximum row heat. The family therefore failed the
primary core-objective and semantic-diversity requirements.

The deterministic duplicate rule preserves the lexicographically smallest
independently salvageable root, `sparse-constellation`, as
`repair-in-place`. The other 19 legacy roots are `replace`; every replacement
has a new ID, materially different API and algorithm, independent reference,
deterministic private oracle, and compiled topic-negative fixture. Complete
legacy hashes and findings are recorded in
`docs/aider-tasks-spec/aider-text-grid-reshaping/sparse-matrix-encoding.md`.

## V2 inventory

| V2 root | Legacy root | Disposition | Primary mechanism |
| --- | --- | --- | --- |
| `sparse-constellation` | same | repair-in-place | sparse coordinate validation and bounding box |
| `outage-component-index` | `sparse-power-outages` | replace | sparse four-neighbor DSU components |
| `irrigation-gap-ledger` | `sparse-farm-irrigation` | replace | interval union and uncovered complement |
| `shelf-free-run-index` | `sparse-library-shelves` | replace | ordered occupied-sentinel scan |
| `transit-csr-delays` | `sparse-transit-delays` | replace | duplicate-summing CSR construction |
| `radar-quadrant-topk` | `sparse-radar-contacts` | replace | geometric quadrant top-K selection |
| `defect-column-compressor` | `sparse-paint-defects` | replace | canonical CSC construction |
| `ward-occupancy-runs` | `sparse-hospital-beds` | replace | target-row run-length compression |
| `solar-rectangle-sums` | `sparse-solar-shade` | replace | two-dimensional prefix query table |
| `orchard-row-groups` | `sparse-orchard-pests` | replace | ordered coordinate grouping and stable argmax |
| `parking-nearest-vacancy` | `sparse-parking-sensors` | replace | bidirectional sparse vacancy search |
| `warehouse-delta-coalescer` | `sparse-warehouse-stock` | replace | additive coordinate-log fold |
| `flood-shoreline-perimeter` | `sparse-flood-markers` | replace | sparse edge exposure and BFS components |
| `terrain-morton-catalog` | `sparse-game-terrain` | replace | Morton bit interleaving |
| `yield-row-dot-product` | `sparse-crop-yields` | replace | duplicate-coalesced sparse row dot products |
| `failure-bipartite-index` | `sparse-network-failures` | replace | augmenting-path bipartite matching |
| `cabin-reservation-runs` | `sparse-seat-reservations` | replace | two-level grouped run encoding |
| `assay-coordinate-transpose` | `sparse-lab-assays` | replace | max-coalesced coordinate transpose |
| `hotspot-row-sweep` | `sparse-fire-hotspots` | replace | sparse difference-event sweep |
| `museum-latest-snapshot` | `sparse-museum-sensors` | replace | timestamp arbitration and canonical snapshot |

## Binding quality gates

The owner derives evidence from emitted docs, public headers, references,
visible tests, private tests, and topic-negative sources. It compares all 190
unordered v2 pairs separately across public API, owned state or algorithm,
mutation or selection rules, invalid and boundary behavior, reference control
flow, deterministic oracle, and topic-specific negative fixture after
neutralizing identifiers, literals, and endpoint direction. Focused tests
inject pure domain/identifier-renamed, constants-or-policy-only, and
opposite-end-selection copies through the production comparator. Each clone
must compile and pass both behavior tests before the semantic screen rejects it;
each topic negative must compile and fail the executed tests.

Prompt construction must expose only documentation and the exact task-named
header/source pair. References, tests, negative fixtures, provenance, CMake,
manifests, and receipts remain private. The bound semantic screen covers all
20 roots against all 26 official C++ holdouts.

Final local verification used the repository-pinned C++ sanity image with
Docker network disabled. Each reference must discover and pass two tests in a
clean normal C++17 build and a separate fresh ASan/UBSan build. The deterministic
archive hash seen inside Docker must match the owner hash. This is
`docker_sanity`, not a family-designated locked oracle.

The completed receipt records 20/20 roots with two normal and two sanitizer
tests each, 20/20 compiled and rejected topic negatives, all three pure clones
compiled with passing behavior tests and semantic rejection, 190/190
seven-axis family comparisons, and 520/520 holdout comparisons. Host
verification was `not_completed` because host CMake is absent; the mandatory
Docker result supplies the completion evidence.

## Local-only boundary

These roots are local candidate material only. They are not JSONL rows, a
dataset release, training authorization, benchmark evidence, or an uplift
claim. Future intake requires a separately authorized admission contract.
