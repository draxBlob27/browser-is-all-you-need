# Sparse Matrix Encoding Family Remediation Specification

## Scope and immutable inputs

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
with `FAMILY_NAME=sparse-matrix-encoding` and
`FAMILY_TYPE=aider-text-grid-reshaping`. Review date: 2026-07-18. The legacy
20-root family at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/sparse-matrix-encoding/`
is immutable. Its owner may generate v2 artifacts only at
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/sparse-matrix-encoding/`.
This is local clean-room remediation; dataset handoff is `not_requested`.

Legacy owner revision:
`sha256:d774a7846d810b783fa7380c8098e7711ccee6a4e5dbe0b304ac5818b00e51a0`.
The bound holdout inventory is the 26-root C++ tree at
`.cache/upstreams/aider-polyglot/cpp/exercises/practice/`.

## Audit findings

### SME-F1 — Shared dense reconstruction replaces the advertised mechanisms

**Severity:** major

**Scope:** all 20 legacy roots

**Observed evidence:** every legacy reference allocates a complete
`rows * columns` dense vector, applies one of four duplicate policies, emits
row-major non-default coordinates, and sums one requested row. Class, method,
and domain nouns do not change the substantive algorithm.

**Why it matters:** the primary task-content objective is absent. The family
teaches one generic dense reconstruction template rather than distinct sparse
representations or algorithms.

**Root cause:** the legacy owner parameterized nouns and duplicate policy over
one `_reference` renderer.

**Remedy:** retain only the lexicographically smallest independently salvageable
root (`sparse-constellation`) as `repair-in-place`; replace every other root
with a new ID, API, state/algorithm, oracle, and topic-negative fixture.

**Verification after remedy:** owner `--verify-core` must locate each named
mechanism in emitted source and pass the complete 190-pair artifact matrix.

**Status:** resolved and reverified.

### SME-F2 — Published objectives disagree with generated contracts

**Severity:** major

**Scope:** at least the free-run, nearest-vacancy, bounding-box, maximum-load,
shore-contact, and grouping roots; the shared generator affects every root.

**Observed evidence:** curriculum rows promise behaviors such as free shelf
runs, nearest free parking bay, constellation bounds, and maximum fire-row
load, while generated APIs return only `SparseReport` with `dense`, `cells`,
and `row_total`.

**Why it matters:** prompt-visible behavior is not the learning objective named
by the family inventory.

**Root cause:** the design note was never promoted into per-root public
contracts before materialization.

**Remedy:** bind each v2 root to its complete API, boundary behavior, ordering,
tie rule, independent reference, and tests in its owner-generated remedy spec.

**Verification after remedy:** prompt/role verification plus focused tests.

**Status:** resolved and reverified.

### SME-F3 — Four normalized implementations create semantic duplicates

**Severity:** major

**Scope:** all 20 roots

**Observed evidence:** identifier/number-neutral normalization groups the
references solely by duplicate policy: reject (5), last (5), sum (5), max (4),
with the remaining reject root differing only through formatting. No all-pairs
logic-and-implementation screen existed.

**Why it matters:** renamed and policy-only copies do not provide independent
learning value.

**Root cause:** task identity and raw file hashes were treated as diversity.

**Remedy:** v2 emits 20 one-to-one mechanisms and compares all seven required
dimensions from actual docs, public APIs, references, visible/private tests,
and topic negatives over all 190 pairs. It also injects pure domain-renamed,
constants/policy, and opposite-end controls.

**Verification after remedy:** `--verify-core` requires material differences in
public API, owned state or algorithm, mutation or selection rules, invalid and
boundary behavior, reference control flow, deterministic oracle, and
topic-specific negative fixture. Each axis has a fail-closed containment limit,
the aggregate limit is 0.90, and every unordered pair must pass independently.

**Status:** resolved and reverified.

### SME-F4 — Oracle evidence is host-only and not tree-bound

**Severity:** blocker

**Scope:** all 20 roots

**Observed evidence:** legacy `--verify` ran host CMake normal/sanitizer builds
but wrote no immutable-image, network-disabled, tree/reference/owner-bound
receipt and did not require equal positive discovery counts.

**Why it matters:** host success cannot establish mandatory Docker sanity or
`local_family_verified`.

**Root cause:** the owner predates the locked-receipt contract.

**Remedy:** deterministic archive, pinned image, `--network none`, explicit
compiler and `Unix Makefiles`, fresh normal and ASan/UBSan builds, independent
archive hash, and owner-imported receipt.

**Verification after remedy:** `--docker-sanity` requires two equal positive
CTest entries per mode and exact archive hash agreement.

**Status:** resolved and reverified. Host iteration was `not_completed` because
`cmake` is unavailable; the mandatory pinned Docker evidence passed.

### SME-F5 — No executed topic-negative evidence

**Severity:** major

**Scope:** all 20 roots

**Observed evidence:** legacy tests never compiled a plausible false
substitute, so passing references did not distinguish the advertised mechanism
from the shared template.

**Why it matters:** the primary mechanism lacked a deterministic discriminator.

**Root cause:** tests covered output examples only.

**Remedy:** each v2 root emits one strict-compiling, task-specific false source;
the same discovered tests must execute and reject it. The three pure clone
controls must compile and pass the behavior tests, then be rejected by the
production semantic comparator.

**Verification after remedy:** Docker `topic-negative.tsv` and
`adversarial-controls.tsv` must account for all 20+3 sources and distinguish
behavioral passage from semantic rejection.

**Status:** resolved and reverified.

### SME-F6 — The first v2 verification overclaimed the hard diversity rule

**Severity:** blocker

**Scope:** the first v2 manifest, focused tests, and Docker receipt

**Observed evidence:** the first manifest recorded only six proxy dimensions
(`public_api`, `behavior_contract`, `reference_control_flow`, two split oracle
files, and `topic_negative`). It did not name or independently gate owned
state/algorithm, mutation/selection rules, or invalid/boundary behavior. Its
three clone controls were built from a known topic-negative implementation and
were expected to fail behavior tests, so they did not prove rejection of pure
semantic clones.

**Why it matters:** unique roots and broken near-copies are not evidence that
all counted roots satisfy the skill's hard rule.

**Root cause:** the initial verifier reused a general containment screen and a
negative-fixture execution path instead of encoding the hard rule literally.

**Remedy:** the owner now names all seven required dimensions, derives each from
actual emitted artifacts, applies per-axis fail-closed thresholds to all 190
unordered pairs, and routes the three pure controls through the identical
production comparator. Constants-only source is identical, identifier renames
normalize identically, and front/back selection normalizes identically. All
three controls must pass both CTests before their semantic rejection counts.
Force regeneration deletes stale host, manifest, and Docker receipts.

**Verification after remedy:** the focused suite asserts all seven axes and all
190 pair decisions. Fresh pinned Docker evidence proves 20 references pass
normal/sanitizer tests, 20 topic negatives fail tests, and three pure controls
pass tests but receive `duplicate_family`.

**Status:** resolved and reverified.

## Per-root accounting

| Legacy root | Legacy tree hash | Disposition | V2 root and mechanism |
| --- | --- | --- | --- |
| `sparse-constellation` | `sha256:95f4f4e36bc1d6917616d301ff54a3a75414940d01b8fb8eec76b28db0f54ebe` | repair-in-place | `sparse-constellation`: sparse bounding box |
| `sparse-crop-yields` | `sha256:0bab5e3c1797ee8ca811bd5d966fd60ca080912398cafa942df9e22944f5353b` | replace | `yield-row-dot-product`: sparse row dot product |
| `sparse-farm-irrigation` | `sha256:f9777737ca72221ead46fd7584c46560a602c301107e03b56598730244fa7c43` | replace | `irrigation-gap-ledger`: interval union/complement |
| `sparse-fire-hotspots` | `sha256:eb37fad044208193547c5a20058759128c894c17c6db3280e0fcb0f96c850247` | replace | `hotspot-row-sweep`: difference-event sweep |
| `sparse-flood-markers` | `sha256:873bed8e56ebaeb43eaf78519ee020c81079915daf901841476e254ce70e27fd` | replace | `flood-shoreline-perimeter`: sparse edge exposure/BFS |
| `sparse-game-terrain` | `sha256:a76bb4262db08aa103abb344a95e997f465f7dd592260c902aacf98d7db82134` | replace | `terrain-morton-catalog`: bit-interleaved Morton order |
| `sparse-hospital-beds` | `sha256:e894cfc727c111a981e3589b0981b13ca14d4d2255c818d224969f22563e694e` | replace | `ward-occupancy-runs`: target-row run compression |
| `sparse-lab-assays` | `sha256:4f030ffe9f593a43a7e070f4685388da3054a96887116a20c8dcc57c61ee2a56` | replace | `assay-coordinate-transpose`: max-coalesced transpose |
| `sparse-library-shelves` | `sha256:b1a5c6af7a6ac560fa79999c7f46cb449590ffa3601ad902ddce6654f20b43da` | replace | `shelf-free-run-index`: occupied-sentinel scan |
| `sparse-museum-sensors` | `sha256:fcbce9e979a381e126269b29307d8b1f182bdd5092ddcf59779bfaaed4afc8aa` | replace | `museum-latest-snapshot`: timestamp arbitration |
| `sparse-network-failures` | `sha256:0fd28dc5d17d30a30f874b759650f4b76065ef898f39aaeff44c57deb1527d18` | replace | `failure-bipartite-index`: augmenting matching |
| `sparse-orchard-pests` | `sha256:2e0e9d3df096a60a399172264986a9171303b747a68b21bb29bdd7f4cbdd5ad3` | replace | `orchard-row-groups`: ordered row grouping/argmax |
| `sparse-paint-defects` | `sha256:7f5b2562584191ccc218479f2a74e66ebfcef5637866783ba2b0aa732001a1fe` | replace | `defect-column-compressor`: CSC construction |
| `sparse-parking-sensors` | `sha256:c082a4acaa3142ff7ec728336ee56564cb7052a565f2df833158588af820d3e5` | replace | `parking-nearest-vacancy`: bidirectional vacancy search |
| `sparse-power-outages` | `sha256:64e1dfd2a0d07c47adf480582ac79373ad434f35e3dd24f362985e8635f3aea3` | replace | `outage-component-index`: sparse DSU components |
| `sparse-radar-contacts` | `sha256:4aa7a00fd125d4c09a6c972b7b8c486bcfcd9f1d90045fbfccf2835eb3a52054` | replace | `radar-quadrant-topk`: quadrant bounded selection |
| `sparse-seat-reservations` | `sha256:683b55e940dd8d9fe5bd44a7e113a6b3523d5c19e9288e5dc272a118b597c417` | replace | `cabin-reservation-runs`: grouped run encoding |
| `sparse-solar-shade` | `sha256:af4871c3ed9e9f3e20e6c99ff065d8d6dfabcaf04586fd736448e62d4a93c1d9` | replace | `solar-rectangle-sums`: 2-D prefix queries |
| `sparse-transit-delays` | `sha256:99ebf7b0e6e209589322771f39c52b7a914934925b75e8b0970f9f79a296c4f6` | replace | `transit-csr-delays`: coalesced CSR |
| `sparse-warehouse-stock` | `sha256:c85456c499c0624a9386fc13f75167506960a77edd4abfe010a93e195e114d7b` | replace | `warehouse-delta-coalescer`: additive log fold |

## V2 tree hashes

| V2 root | Current tree hash |
| --- | --- |
| `assay-coordinate-transpose` | `sha256:0c71b91de0c6336e2479016e23ce3a49a5907f3bbb163b8380cb376531bdc6f7` |
| `cabin-reservation-runs` | `sha256:3ba10900871c5b7e1ab707bf4f350e962366533fab3616a7c7b0b01b596e7f94` |
| `defect-column-compressor` | `sha256:9a17d016bd69c62d71c994e9af30281720d4580eaff3944b5545c28470cf7619` |
| `failure-bipartite-index` | `sha256:b8c74e895c137a0d99779c6f6eca09195f17c51b23bbb95d9c6e76a048a2ce94` |
| `flood-shoreline-perimeter` | `sha256:79fe7649b239ad1e93c163cc786846df029f85b67e2d33d1ac112ded54f7d78b` |
| `hotspot-row-sweep` | `sha256:df2206d41a25a3d3b5b4419200def2789e6307124d874266c1012ea213a67081` |
| `irrigation-gap-ledger` | `sha256:57b60e3cdd5d7ece91c091df88281668b6b4896013c3dd50d33c22a60c60d8f4` |
| `museum-latest-snapshot` | `sha256:d3ded63bcad68cd8d4f2be155e78e35347ac3295d94565ccf63fc825915cff2b` |
| `orchard-row-groups` | `sha256:7b76e771178a1e4a05e8671b36e4a75d689b9dceb1bb2001064f088e06bfd097` |
| `outage-component-index` | `sha256:206d576126e965d92d0698794c35298beafe0f48432ef9bb6b414224089adb84` |
| `parking-nearest-vacancy` | `sha256:80379ff89b29592971ca38276616b514006ca54d4178439756fffecf1fcc86de` |
| `radar-quadrant-topk` | `sha256:a0a766fe65abd58325eb2b1ff048b322c9642d45c1685b8e6ceadfa51dfba027` |
| `shelf-free-run-index` | `sha256:18bf9aee830516231029f3ac8219455c267d49863c4a131d95f17ed65507eb46` |
| `solar-rectangle-sums` | `sha256:e221544bcf3db1e6990953d6c50e4d34ef26fbf2352265d6fe398f4cd0e870dd` |
| `sparse-constellation` | `sha256:7683496b5c581e851edcffe9cf6eedb6483ce455a2ae175fd1602423953bdc44` |
| `terrain-morton-catalog` | `sha256:44b66fa3e48ccdc5f96bfa16865bdddeaf6d011c6db5f3d8089de36115b457f4` |
| `transit-csr-delays` | `sha256:cceb2fb1514684d0fa850e7d453c871dd9ac3e1c20965305b7c3ce53f724c826` |
| `ward-occupancy-runs` | `sha256:67452c3f27ce57217cd413d1b297869fc0f1592d53e44254d0b2bc06f624488e` |
| `warehouse-delta-coalescer` | `sha256:c252100ecee1c7ac2f43062385e77e161364b6c58cc94e841d5a9dfe8d08f54c` |
| `yield-row-dot-product` | `sha256:4e11c8a248524376eb87e2aa0f1125f4f1a98e07fe1503608aa57b26d682c41c` |

## Structural and evidence matrix

| Gate | Legacy result | Required v2 result |
| --- | --- | --- |
| Primary core objective | not achieved | named mechanism present and topic negative rejected |
| Prompt boundary | structurally plausible | exact docs + two solution files only |
| Role/reference mapping | present | exact task-named files and suffix mapping |
| Family diversity | fail: shared template | 190 seven-axis artifact-derived pair decisions plus three pure clone controls |
| Benchmark screen | claim only | 520 normalized comparisons against bound 26-root holdout tree |
| Normal/sanitizer | unreceipted host run | two equal positive tests in both Docker modes |
| Negative fixtures | absent | 20 topic negatives fail tests; three pure controls pass tests and fail the semantic screen |
| Dataset handoff | not authorized | `not_requested` |

## Commands and acceptance

```bash
uv run pytest -q tests/test_moonlight_sparse_matrix_encoding_aider_tasks.py
bash examples/slime/moonlight_cpp_perf/prepare_sparse_matrix_encoding_aider_tasks.sh --force --verify-core
bash examples/slime/moonlight_cpp_perf/prepare_sparse_matrix_encoding_aider_tasks.sh --force --verify
bash examples/slime/moonlight_cpp_perf/prepare_sparse_matrix_encoding_aider_tasks.sh --force --docker-sanity
```

## Verification result

The focused suite passed 10 tests. `--verify-core` passed exact regeneration,
prompt and role boundaries, 190 replacement pairs across all seven hard-rule
dimensions, three pure semantic clone controls, and 520 comparisons against 26 official C++ holdouts. Host
`--verify` was `not_completed` because `cmake` is unavailable on the host.

The mandatory Docker run passed in
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with network `none`. Every root discovered and passed 2 normal plus 2 fresh
ASan/UBSan CTests. All 20 topic negatives compiled and were rejected by the
executed tests. All three pure clone controls compiled and passed both behavior
tests, then were rejected as `duplicate_family` by the production comparator.
The Docker archive hash
`sha256:7f58d8b6f740db2b9b5f436fdb50856ff3c916054e974533ee2989d2aadab470`
matched the mounted tree. The receipt binds final owner hash
`sha256:9a402f14453d4a59e9eee1a71b8959bdc6002250837a3abf8178dac4070dd1c1`;
receipt hash is
`sha256:283dc59493b88700d20cfcd7384125f44861dd9c3b15f89c5d0f9ecd30f59721`.
All 20 remedy records are `verified` with strongest status
`local_family_verified`.

This is `docker_sanity` evidence with `locked_oracle: false`, not a dataset
release. No result authorizes a dataset row, split, export, training run, or
benchmark-uplift claim.
