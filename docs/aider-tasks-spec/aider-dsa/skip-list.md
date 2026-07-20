# Skip-List Family Remediation Specification

## Scope and authority

This specification controls the local re-verification of the generated
`aider-dsa/skip-list` family. The selected workflow prompt is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`, with
`FAMILY_NAME=skip-list` and `FAMILY_TYPE=aider-dsa`.

The legacy input is preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/skip-list/`. The owner may write task
artifacts only beneath
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/skip-list/`. The mutable audit,
remedy, screen, and oracle evidence lives in that re-verification root's
`.state/` directory. Nothing in this document authorizes dataset rows,
training, release, or benchmark-uplift claims.

## Legacy audit

The legacy inventory contains 20 roots. Every root has role-correct docs,
two editable files, a separate reference pair, visible/private tests, CMake,
and local-only provenance. Every reference owns a head sentinel and
multi-level forward-linked nodes, so the reference-level skip-list mechanism
is present.

The family nevertheless has four blocking quality findings:

### SKIP-001 — one renamed implementation across all roots

**Severity:** major

**Scope:** all 20 legacy roots.

**Observed evidence:** after substituting each generated class, method, and
task slug, all 20 `.meta/example.cpp` files are byte-identical. Every root
uses the same unique-ID CRUD, rank/select, cursor page, inclusive range, and
`links_consistent` implementation.

**Why it matters:** domain nouns and method names do not create independent
learning value. The family is a semantic template duplicate.

**Root cause:** the owner stores only names and an ordering label in `_ROWS`;
one renderer owns every API, reference control flow, and test.

**Remedy:** retain only the lexicographically smallest independently
defensible legacy ID and replace every other root with a distinct API,
representation variant, mutation rule, selection rule, boundary policy,
reference flow, and negative fixture.

**Verification after remedy:** compare every unordered pair over normalized
docs, declarations, private fields, reference control flow, visible tests, and
hidden tests. Reject renamed-domain, constants/policy-only, and
opposite-end-selection adversarial clones.

**Status:** resolved and reverified by the v3 190-pair production screen.

### SKIP-002 — task-specific contracts are not implemented

**Severity:** major

**Scope:** all legacy roots.

**Observed evidence:** curriculum capabilities such as percentile queries,
expiry invalidation, calendar availability, threshold resolution, and file
block lookup are all rendered as generic CRUD plus `rank_of`, `select`,
`page`, and `range`.

**Why it matters:** building a generic ordered registry does not implement the
advertised domain algorithms.

**Root cause:** the materializer does not encode per-root state models or
operation semantics.

**Remedy:** bind each retained/replacement root to exactly one observable
skip-list capability and a task-specific deterministic oracle.

**Verification after remedy:** focused tests require 20 unique mechanism
profiles and artifact-derived public/API/reference/test signatures.

**Status:** resolved and reverified with 20 emitted mechanism profiles and
artifact-derived dimension evidence.

### SKIP-003 — documented descending orders execute ascending

**Severity:** blocker

**Scope:** `skip-auction-price-levels`, `skip-cargo-priorities`,
`skip-live-leaderboard`, `skip-reservation-waitlist`,
`skip-search-result-pages`, and `skip-student-ranks`.

**Observed evidence:** their visible instructions declare descending primary
keys, while the shared `before` comparator always compares `a.key < b.key` and
the shared tests assert ascending order.

**Why it matters:** the prompt, reference, and oracle disagree.

**Root cause:** the per-root `order` field is interpolated into prose but not
into generated C++.

**Remedy:** replace the shared ordering renderer with mechanism-specific
comparators and explicit tie behavior.

**Verification after remedy:** public tests exercise each documented ordering
and private traces compare complete observable order after mutations.

**Status:** resolved and reverified by the v3 normal, sanitizer, and executed
negative oracle.

### SKIP-004 — the structural claim is not enforced against substitutes

**Severity:** major

**Scope:** all 20 legacy roots.

**Observed evidence:** `links_consistent()` is model-implemented and the tests
accept its boolean result. A vector/map implementation can return `true`
without exposing a trusted structural predicate.

**Why it matters:** the task cannot distinguish the advertised skip list from
the easiest forbidden substitute.

**Root cause:** tests call a public self-report instead of an owner-defined
test-only audit over owned node/tower state.

**Remedy:** emit a `CURRICULUM_TESTING` friend audit whose implementation is
owned by the task contract, reject authoritative ordered containers in the
reference, and execute a named `sorted_vector_authority` rejection path.

**Verification after remedy:** `--verify-core` must reject the vector fixture
with `invariant_not_enforced`; the Docker verifier must also execute a bad
source whose structural audit fails.

**Status:** resolved and reverified by 20 compiling topic-specific false
implementations rejected by executed task tests.

### SKIP-005 — adversarial clone controls bypass the production screen

**Severity:** blocker

**Scope:** all 20 re-verification roots.

**Observed evidence:** the first v2 verifier compared real candidate pairs with
`_similarity`, but exercised three synthetic string controls through a separate
`_clone_reason` function. A passing control therefore did not prove that the
all-pairs decision path rejected an emitted-artifact clone.

**Why it matters:** the hard diversity rule requires adversarial controls made
from emitted docs, APIs, references, and tests to pass through the same
fail-closed decision used for every counted pair.

**Root cause:** the control generator and production pair screen used
different inputs and decision functions.

**Remedy:** construct domain-renamed, constants-only, and opposite-end clones
from one emitted root's complete semantic role inventory and submit them to the
exact pair evaluator used for all 190 candidate pairs. Record per-dimension
scores for public API, owned state, mutation/selection, invalid/boundary rules,
reference control flow, deterministic oracle, and negative fixture.

**Verification after remedy:** focused tests must prove each emitted-artifact
clone returns `duplicate_family` from the production evaluator, and the family
receipt must contain 190 passing pair decisions with every required dimension.

**Status:** resolved and reverified; all three emitted-artifact controls reach
`duplicate_family` through the production pair evaluator.

### SKIP-006 — negative fixtures do not execute the task tests

**Severity:** blocker

**Scope:** all 20 re-verification roots.

**Observed evidence:** the first v2 negative sources were renamed
`std::vector<int>` marker snippets. CMake rejected the marker during configure,
so the false implementation never compiled and no visible/private test
executed.

**Why it matters:** the remediation skill explicitly excludes marker greps,
compile failures, and unused source scans from negative-fixture evidence. Each
counted root needs a topic-specific false implementation rejected by its real
tests under the reference warning policy.

**Root cause:** the verifier treated a source admission scan as though it were
an executed discriminating oracle.

**Remedy:** generate one complete, compiling, mechanism-specific false source
per root. Configure and build it with the same CMake target and strict flags,
require the same positive two-test discovery, execute the tests, and accept
only their nonzero result with the task-specific Catch case present in output.

**Verification after remedy:** Docker must report two discovered negative tests
and `topic_specific_test_rejection` for every root; configuration, compilation,
zero discovery, or an unexpectedly passing test suite fails closed.

**Status:** resolved and reverified; all 20 false sources compile, discover two
tests, execute both CTest groups, and reach `topic_specific_test_rejection`.

## Deterministic dispositions and replacement inventory

The first matching deterministic rule is template duplication. The
lexicographically smallest legacy ID is repaired in place; all other legacy
IDs are replaced with new IDs.

| Legacy ID | Disposition | Re-verified task ID | Primary mechanism |
|---|---|---|---|
| `skip-auction-price-levels` | repair-in-place | `skip-auction-price-levels` | descending price towers with FIFO orders and level quantity |
| `skip-calendar-slots` | replace | `skip-gap-calendar` | non-overlapping reservation towers and first-fit gap search |
| `skip-cargo-priorities` | replace | `skip-tower-merge-manifest` | two explicit-height towers merged by pointer-splice rebuild |
| `skip-document-anchors` | replace | `skip-snapshot-anchor-map` | version chains on position-ordered anchor towers |
| `skip-event-timeline` | replace | `skip-interval-event-index` | interval towers augmented with prefix maximum end |
| `skip-expiring-cache-index` | replace | `skip-expiry-bucket-wheel` | expiry-key towers with per-key FIFO membership buckets |
| `skip-feature-rollout` | replace | `skip-threshold-floor-map` | floor resolution over replaceable rollout thresholds |
| `skip-file-offset-index` | replace | `skip-sparse-extent-map` | disjoint extent towers with containment and truncation |
| `skip-inventory-reorder` | replace | `skip-weighted-reorder-index` | forward-span weight sums and weighted selection |
| `skip-live-leaderboard` | replace | `skip-span-leaderboard` | indexed skip list with maintained rank widths |
| `skip-log-retention` | replace | `skip-tombstone-log-index` | lazy range tombstones plus explicit physical compaction |
| `skip-metric-window` | replace | `skip-dual-window-median` | coupled time-order and value-order towers |
| `skip-notebook-lines` | replace | `skip-unrolled-line-index` | block nodes with split/merge and ordinal lookup |
| `skip-order-statistics` | replace | `skip-counted-order-statistics` | duplicate counts and multiplicity spans |
| `skip-percentile-meter` | replace | `skip-explicit-height-replay` | caller-supplied tower heights and level snapshots |
| `skip-reservation-waitlist` | replace | `skip-bidirectional-waitlist` | forward/back links at every promoted level |
| `skip-route-markers` | replace | `skip-finger-route-index` | cached finger search with monotone fast path and reset path |
| `skip-search-result-pages` | replace | `skip-prefix-search-index` | lexicographic string towers and bounded prefix scans |
| `skip-student-ranks` | replace | `skip-deterministic-student-map` | hash-derived deterministic tower heights and lookup |
| `skip-transit-departures` | replace | `skip-circular-transit-ring` | circular successor lookup with day-boundary wrap |

## Family-wide implementation contract

Every root uses C++17, task-named editable `<task-id>.h` then
`<task-id>.cpp`, Catch v1 support, one visible and one private test group, and
an owner-defined `CURRICULUM_TESTING` audit. References must own linked tower
or block nodes and must not use `std::map`, `std::set`, `std::multiset`,
`std::priority_queue`, GNU PBDS, Boost ordered containers, or a sorted vector
as authoritative state. Vectors are permitted only for returned values,
temporary update paths, audit snapshots, and unrolled-node payload blocks.
Each root also owns one complete topic-specific false source that compiles
against the same header and is rejected only after the visible and private
Catch tests execute.

Height policies are deterministic. All mutation failures leave state
unchanged. Every private trace checks the operation result, the complete
observable ordering against an independent vector/value oracle, and the
trusted structural audit after each operation class.

## Prompt, roles, and reference mapping

The public prompt contains only `.docs/introduction.md`,
`.docs/instructions.md`, and the two declared editable files. Config,
provenance, CMake, support, reference, visible tests, private tests, receipts,
and `.state` never enter the prompt. `files.solution` and `files.example` have
equal length and exact header/source order.

## Family and contamination screen

The family screen binds normalizer `aider-cleanroom-family-v3` and compares
all 190 unordered candidate pairs. Its production pair evaluator derives the
public API, owned state/algorithm, mutation/selection, invalid/boundary,
reference-control-flow, deterministic-oracle, and topic-specific-negative
dimensions from emitted roles. It removes comments, strings, literals, and
domain nouns while retaining declarations, member-state tokens, control flow,
and assertions. Domain-renamed, constants-only, and opposite-end clones are
constructed from emitted artifacts and must be rejected by this exact
evaluator. The same normalized content is separately compared with all 26
official C++ holdouts from the pinned manifest and checkout. Whole-slug overlap
or a semantic near-match fails closed. Shared Catch support and the repo-owned
CMake scaffold are excluded only by exact allowlisted role.

## Build and Docker oracle

The repository-pinned sanity image is
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
It is evidence class `docker_sanity`, not a family-designated locked oracle.
The verifier packages the exact current task tree, mounts it read-only with
`--network none`, independently matches its tree hash, and runs fresh normal
and ASan/UBSan CMake builds with `Unix Makefiles`. Both modes must discover
exactly two positive CTest entries for every root and all counts must match.

## Acceptance commands

```bash
uv run pytest -q tests/test_moonlight_skip_list_aider_tasks.py
bash examples/slime/moonlight_cpp_perf/prepare_skip_list_aider_tasks.sh --force --verify-core
bash examples/slime/moonlight_cpp_perf/prepare_skip_list_aider_tasks.sh --force --verify-core --verify
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

Stable failures include `remedy_spec_incomplete`,
`remedy_disposition_conflict`, `prompt_contract_incomplete`,
`target_reference_mismatch`, `invariant_not_enforced`,
`duplicate_family`, `benchmark_id_overlap`, `benchmark_content_overlap`,
`zero_tests`, `sanitizer_test_count_mismatch`,
`grader_mount_hash_mismatch`, and `generator_output_drift`.

## Final re-verification evidence

Re-verification completed with `primary_core_objective: achieved` and strongest
status `local_family_verified`. The legacy tree was not regenerated or
modified. Changed owner paths are
`src/w8_biayn/integrations/moonlight_skip_list_aider_tasks.py`,
`src/w8_biayn/integrations/moonlight_skip_list_cases.py`,
`tests/test_moonlight_skip_list_aider_tasks.py`, the curriculum, this
specification, the materialization guide, and the preparation wrapper.

The exact snapshot archive is
`sha256:ad8e22a789324f743d45989b26d2036d25f07f03237ca24d545856d98caab5c6`.
The owner/cases hash is
`sha256:fe91eadf0a2eb96425da5b346a95d765219a2281d704dc12aaef786a871c9d87`
and the normative specification hash is
`sha256:69e92a22c484b8763a223f2ab74737373525dcc247e145f490de896d424da318`.

The pinned image identity matched
`sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
It reported `/usr/local/bin/c++`, GCC 13.4.0, compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
and CMake 3.25.1 with `network_policy: none`.
All 20 roots discovered and passed two normal tests and two fresh
ASan/UBSan tests: 40 normal and 40 sanitizer entries with equal per-root
counts. All 20 v3 topic-specific false sources configured and compiled under
the same strict target, discovered two tests each (40 total), executed visible
and private CTests, and reached `topic_specific_test_rejection`. Ten failed
both groups, eight failed visible only, and two failed private only. Evidence
class is `docker_sanity` and
`locked_oracle: false`; no family-designated locked oracle was claimed.

Prompt/role/reference mapping passed for all roots. The artifact-derived
screen compared all 190 candidate pairs across all seven hard-rule dimensions
and all 520 candidate/official-holdout pairs. All three emitted-artifact clone
controls reached `duplicate_family` through the production pair evaluator. The
strongest family dimension was public API for `skip-interval-event-index`
versus `skip-weighted-reorder-index` at `0.851175`, below the `0.88` limit; the strongest holdout pair
was `skip-deterministic-student-map` versus official `spiral-matrix` at
`0.000552`. Both family and benchmark screens passed.

| Legacy ID | Re-verified task ID | Disposition | Before tree | After tree |
|---|---|---|---|---|
| `skip-auction-price-levels` | `skip-auction-price-levels` | `repair-in-place` | `sha256:aaa37585933a879dce491adf4cb367c255e70a5998e0bde6ad29e2c518bc906f` | `sha256:e9a10d2ad23f9175a1992921e21701f5911f22bbbed8d9466f7ed619da0c8bc0` |
| `skip-calendar-slots` | `skip-gap-calendar` | `replace` | `sha256:662d392e8a4e94b6dd48e080c6eee86e51a10b66435bc35cc311d83ea648da45` | `sha256:127c9922e399f6ba7de19032a5331e847ebfb8431b964a8b06e7fabf5884a4e4` |
| `skip-cargo-priorities` | `skip-tower-merge-manifest` | `replace` | `sha256:8d968cabcf0f62f1274e00efe5b4b5462ed555d2bbe37b438f5695373f25776d` | `sha256:0de09a6250f58666ddc4dbbbe1289899869e24cc428a013976fb7c42ed7e174e` |
| `skip-document-anchors` | `skip-snapshot-anchor-map` | `replace` | `sha256:e015500611962cc06f489ecaac314b06928618c791408e5592af83d95b951a5d` | `sha256:731063bd97b1355d92907a26eb888e9cd5155586600075e1635fd6dd6e9ab1f4` |
| `skip-event-timeline` | `skip-interval-event-index` | `replace` | `sha256:478ed5684f74f019d4d19ce79a330247edd11f2f7255b1f93591e5a0c429b3e5` | `sha256:fecfc158bce72488fa6fea868a48db2f9e4750122b5f291f9363df3867b648b9` |
| `skip-expiring-cache-index` | `skip-expiry-bucket-wheel` | `replace` | `sha256:8e21895eae2071f3ee35a1cd82b0d82883206fe814d4ce338b01a2452cce04d1` | `sha256:19a595ede6837eca33e6051ec7bc4207d990b781daa8e01c263825eb7f0caac0` |
| `skip-feature-rollout` | `skip-threshold-floor-map` | `replace` | `sha256:903f5e798f5b6517b947c87d983809c9ccff286116a59d9beb6abc9c854d97d9` | `sha256:a08fce0d24d3a9a9a3c2a477c191c3c9678ac64e23c835594b68fc6a53f56e9a` |
| `skip-file-offset-index` | `skip-sparse-extent-map` | `replace` | `sha256:a3476be4e95a1351d01c121b47941e5a552b2043c234d29b0cf18af37f0538c3` | `sha256:d1bcc929669cb6bb640881fba40f58fa13931eb8e8489c16334990f576ff0ebe` |
| `skip-inventory-reorder` | `skip-weighted-reorder-index` | `replace` | `sha256:7d71c0b5aa11cf0d9861945dc6eba0028136f2953cf6f8fc167dad0fb6bee471` | `sha256:334c06cadd93d7b36f9c3011da279f5a82c912cf13aff978bf7d4f38919a196b` |
| `skip-live-leaderboard` | `skip-span-leaderboard` | `replace` | `sha256:020a368bb4c1860535427d0a1f20bc6fd5a3e214bbee26b58e1802ddee2b8f70` | `sha256:74eef07e08b167f6203bbd42fc6f9239b256ca0c1dd83326cb9163c98b70dae5` |
| `skip-log-retention` | `skip-tombstone-log-index` | `replace` | `sha256:98fbca99db865a18c78c9da19f513d2094a961ba51fb7cc049ff146bb669523c` | `sha256:a0b23157be4f9d7153a923942958920498f28d3e5d147ba4858bc1a8cee157f7` |
| `skip-metric-window` | `skip-dual-window-median` | `replace` | `sha256:3b6643c2767cc3fb673b5890a62f3a6e7d8408deed03fda3081353c839fed53b` | `sha256:8f5da21fb82beb1c1e2c860ef8213ee6e9279209d99621067045c50c356e6631` |
| `skip-notebook-lines` | `skip-unrolled-line-index` | `replace` | `sha256:3493028764575449063de84b9be5d3e7dae75babbd94c892c118b2f428951b66` | `sha256:d034147bdffdde7d8dae49180dc2f849caa27afa40069a69e3c2def4c06128ed` |
| `skip-order-statistics` | `skip-counted-order-statistics` | `replace` | `sha256:978fa27520c23cc6cd62f62be9792920a93eec56edb2c6d4acaaf290803b4f99` | `sha256:1e831d3ba883b77ad0764c03591d5af4e97c02ecafaf042f65372895bf869aba` |
| `skip-percentile-meter` | `skip-explicit-height-replay` | `replace` | `sha256:bf5928aefcb76e349624f610d9daae087945ac6ff5b0ce2aceb7219a9e2e331b` | `sha256:1020fccd3e5c1b8d949f295d821a36820641207c96bc2cfc252a2b76f924d31c` |
| `skip-reservation-waitlist` | `skip-bidirectional-waitlist` | `replace` | `sha256:3dd0612e7d2449c2429038867266fb95ae00210791d6b307bf70384e7cec3502` | `sha256:f5ad00f00906cc4c04f37a48c86cfb7931491c9ff3b01c9c2bde220e27cb51c5` |
| `skip-route-markers` | `skip-finger-route-index` | `replace` | `sha256:fdf9d218bba9c40a3ef1dd44f3202c3cd3a03b4f09a9786acd4150d34bb22372` | `sha256:0eaa7df75c4441eaba205ec7783302dbc3fd1e177619da1d288656414c6ec2c4` |
| `skip-search-result-pages` | `skip-prefix-search-index` | `replace` | `sha256:45640c07b7445eec623292e7aca6812963051876cba04a798afe835865a4ca88` | `sha256:011bb951c755c090acfab8e9f380bf0b2785fc20c95643786440d4e4da370e77` |
| `skip-student-ranks` | `skip-deterministic-student-map` | `replace` | `sha256:6a8e66cad2b0d3ace34599765e15d875ae8e35bcfb3ca25f02828eb395b52868` | `sha256:4cbb88bbb224bfe356e7babc9b9900a2290c897bf36c6b1dcefa72e6ff32fc5f` |
| `skip-transit-departures` | `skip-circular-transit-ring` | `replace` | `sha256:95e40cf668730e4eea369957ff607585df55095acdcc7208ed4483462c5716a3` | `sha256:c4a7f7de2229b6229d04a9ebc82fda4ad8c82d5c255f00bb5d17e28768797699` |

All 20 remedy JSON records are `verified`, bind their Markdown specs and
per-root receipts, and report `local_family_verified`. Optional dataset
handoff remains `not_requested`; no release conclusion is made.
