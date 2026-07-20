# Sequence Pattern Family Remediation

## Scope

This audit and deterministic implementation specification covers all 20 legacy
roots under `.w8-biayn/data/aider-tasks/aider-dsa/sequence-pattern/`.  The
legacy tree is immutable audit input.  Replacement roots are generated only
under `.w8-biayn/data/aider-tasks-reverify/aider-dsa/sequence-pattern/` by
`src/w8_biayn/integrations/moonlight_sequence_pattern_aider_tasks.py`.

The selected workflow prompt is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`, with
`FAMILY_NAME=sequence-pattern` and `FAMILY_TYPE=aider-dsa`.  The official Aider
C++ `sublist` root and all other 25 official C++ roots remain permanent
holdouts.  This work ends at `local_family_verified`; dataset handoff is
`not_requested`.

## Legacy audit

Every legacy root has the expected docs, role metadata, starter pair, reference
pair, visible/private tests, and CMake recipe.  Prompt-visible files are limited
to docs plus declared editable files.  Those structural facts do not rescue the
family's core defect:

- every public API is the same three-argument static method over a vector of a
  renamed `{token,value,ignored}` record and a vector of strings;
- every reference compacts ignored records, then performs the same nested
  start/pattern scan with a mode string controlling a few branches;
- every visible test is the same `Alpha/beta/gamma` trace and every private
  test is the same 240-element `a/b/c` trace;
- the claimed KMP-like, wildcard, gap, alignment, streaming, protocol,
  relative-movement, optional-step, and policy behaviors are absent or reduced
  to the same literal matcher; and
- no task-specific negative fixture distinguishes the advertised mechanism
  from a renamed copy of that template.

`primary_core_objective: not_achieved` for all 20 legacy roots.  Finding
`SP-F1` is a major absent-core finding; `SP-F2` is a major template/semantic
duplicate finding; `SP-F3` is a moderate prompt-contract incompleteness
finding; `SP-F4` is a major missing discriminating-test/negative-fixture
finding; and `SP-F5` records that prior host-only normal/sanitizer runs are not
the mandatory network-disabled Docker sanity evidence.  The first matching
deterministic disposition is `replace` for every root.

## Replacement inventory

| Legacy root | Replacement root | Primary mechanism | Named false substitute |
| --- | --- | --- | --- |
| `seq-audit-signature` | `audit-event-kmp-v2` | prefix-function matching over typed event keys | restart-at-every-position scan |
| `seq-dna-motif` | `dna-shift-and-v2` | bit-parallel Shift-And IUPAC masks | literal substring search |
| `seq-command-policy` | `command-aho-policy-v2` | Aho-Corasick multi-policy automaton | independent rescans per policy |
| `seq-playlist-excerpt` | `playlist-gap-alignment-v2` | minimum-gap dynamic-programming alignment | contiguous case-folded search |
| `seq-sensor-anomaly` | `sensor-stream-window-v2` | stateful bounded ring-window matcher | stateless full-history rescan |
| `seq-shipment-checkpoints` | `checkpoint-gap-dp-v2` | timestamp-bounded subsequence DP | unbounded subsequence check |
| `seq-log-phrase` | `log-lexer-kmp-v2` | punctuation lexer plus token KMP and coordinates | whitespace-only token split |
| `seq-ui-workflow` | `ui-workflow-dfa-v2` | explicit reset/ignore-aware DFA | filtered contiguous search |
| `seq-factory-cycle` | `factory-z-cycle-v2` | Z-function overlap counting | repeated nested comparison |
| `seq-network-handshake` | `handshake-schema-machine-v2` | optional/repeated-field schema machine | token equality scan |
| `seq-route-detour` | `route-rabin-karp-v2` | pair-key rolling hash with collision verification | location-only matching |
| `seq-medication-schedule` | `dose-window-deque-v2` | time-window deque and class-state transitions | adjacency-only class check |
| `seq-price-pattern` | `price-movement-prefix-v2` | derived movement alphabet plus prefix function | raw-price equality search |
| `seq-document-template` | `heading-lcs-alignment-v2` | deterministic LCS reconstruction | contiguous folded search |
| `seq-access-escalation` | `access-gap-nfa-v2` | bounded-gap NFA with implicated IDs | contiguous privilege scan |
| `seq-game-combo` | `combo-wildcard-trie-v2` | multi-combo trie with wildcard edges | one-pattern linear scan |
| `seq-support-macro` | `support-suffix-automaton-v2` | suffix automaton repeated-factor selection | fixed-length pairwise search |
| `seq-assembly-inspection` | `inspection-optional-dp-v2` | optional-step DP with witness reconstruction | unconditional optional-step skip |
| `seq-currency-arbitrage` | `quote-product-window-v2` | checked product windows with orientation rules | direction-symbol equality search |
| `seq-version-migration` | `migration-dag-validator-v2` | prerequisite DAG sequence validator | required-token subsequence scan |

Replacement IDs never overwrite legacy IDs.  The owner must emit exactly the
20 rows above and bind every replacement to its legacy root in provenance and
remedy state.

## Common public and role contract

Each replacement uses C++17 and exactly two editable files in order:
`<replacement-id>.h`, then `<replacement-id>.cpp`.  The role map declares the
visible test and both `.meta/example.*` files; the private test and named
negative source remain non-editable and prompt-hidden.  Paths must be safe,
relative, existing, and mutually role-correct.  Starters compile as incomplete
implementations but contain no correct helper.  References are independently
authored and may use incidental vectors, strings, queues, maps, or deques only
where they do not replace the mechanism named above.

Public docs must state all valid, invalid, empty, duplicate/absent, ordering,
tie, overflow, and no-mutation rules exercised by private tests.  Each API is
domain-specific; no replacement may expose two-list equal/sublist/superlist/
unequal classification.  Every result order is deterministic.  Invalid input
returns the documented empty/error result without partially mutating state,
except constructors that explicitly throw `std::invalid_argument`.

## Core and negative-fixture contract

The marker named by each replacement specification must occur in the reference
control flow and be exercised by its private tests.  Each `.meta/negative.cpp`
is a compilable task-specific false substitute.  The generated CMake project
runs it against the private test as an expected failure; a negative fixture
that exits successfully is `invariant_not_enforced`.  Removing the mechanism,
changing the negative source to the reference, or substituting the named false
implementation must fail the focused verifier.

The family screen normalizes actual emitted docs, APIs, references, visible and
private tests by removing comments, strings, literals, and domain identifiers
while retaining API arity, standard-library mechanism tokens, control flow,
and assertions.  It compares every unordered replacement pair and every bound
official C++ holdout.  An exact normalized contract or containment at/above
the owner threshold is `duplicate_family` or `benchmark_content_overlap`.
Whole-slug screening is a separate mandatory gate.

The counted family bound is exactly 20 roots and the owner fails closed outside
that bound.  Focused tests must independently demonstrate that the screen
rejects all three required adversaries: a consistent domain/identifier rename,
a constants-or-policy-only variant, and an opposite-end-selection variant.
Declared task IDs, semantic profiles, and unequal raw hashes are never accepted
as hard-diversity evidence.

## Build and oracle

The owner uses explicit `Unix Makefiles`, C++17, strict warnings, and three
positive CTest entries per root: visible, private, and an executed expected-
failure negative fixture.  It runs clean normal and separate fresh
ASan/UBSan builds, requires equal positive discovery counts, and records the
tree hash, reference hash, negative-fixture hash, owner hash, image identity,
compiler/CMake versions, exact commands, and `network_policy: none`.

The designated evidence class is `docker_sanity` using the repository-pinned
`w8-biayn-polyglot-cpp` image.  It is not a `locked_oracle` or dataset-release
claim.  Host verification is iteration evidence only and leaves the strongest
state below `local_family_verified`.

## Acceptance

Run the focused pytest, materialize only the reverify root with `--force`, run
`--verify-core`, then run/import the owner-controlled network-disabled Docker
normal/sanitizer result.  Acceptance requires:

- all 20 immutable legacy tree hashes and remedy-spec hashes match their
  records;
- fresh regeneration exactly matches every emitted task tree;
- prompt boundary, role/reference map, strict whole-file answer, and malformed
  answer controls pass;
- all 20 primary mechanisms are present and all 20 named negative fixtures are
  executed and rejected;
- all 190 unordered family comparisons and all available 26-root holdout
  comparisons pass;
- the exact 20-root owner bound passes, while focused controls reject a
  domain/identifier-renamed clone, a constants-or-policy-only clone, and an
  opposite-end-selection clone;
- normal/sanitizer CTest discovery is exactly three per root and every test
  passes in both modes; and
- every remedy record reaches `local_family_verified` with dataset handoff
  `not_requested`.

Stable failures include `remedy_spec_incomplete`,
`remedy_disposition_conflict`, `generator_output_drift`,
`prompt_contract_incomplete`, `whole_format_failed`, `unsafe_path`,
`target_reference_mismatch`, `invariant_not_enforced`, `duplicate_family`,
`family_count_out_of_bounds`,
`benchmark_id_overlap`, `benchmark_content_overlap`, `zero_tests`,
`reference_tests_failed`, `reference_sanitizer_failed`, and
`sanitizer_test_count_mismatch`.

## Strongest current conclusion

All 20 legacy roots were audited without modifying the legacy tree, and all 20
deterministic `replace` dispositions were implemented through the owning
generator.  The fresh replacement family reached `local_family_verified` in
the mandatory network-disabled Docker sanity runtime on 2026-07-18.

The materialization family hash is
`sha256:9fce2f6a118c369cc1ea33f84f703a630c490c7a8775d779f745a881c33cc7aa`.
The owner hash is
`sha256:6da90a33ed057178c29001406cb4d8662d5b2db486eec83e43f5f00915ada380`,
and the oracle receipt hash is
`sha256:9fe6c140cf8ca21d1b32607bcb8897c92356e30871d993ae5778d5cd409f204a`.
Every remedy record binds its immutable legacy tree hash, remedy-spec hash,
replacement tree hash, and this receipt.

Recorded results are 20/20 task-specific negative fixtures rejected, 190/190
unordered family comparisons clean, 520/520 comparisons against all 26
official Aider C++ holdouts clean, and exactly three passing tests per root in
both the clean normal and fresh ASan/UBSan builds.  Prompt boundary,
role/reference mapping, whole-file response controls, and whole-slug benchmark
screening all pass.  Semantic normalizer v3 derives its evidence from emitted
introductions/instructions, public APIs, references, and visible/private tests;
focused controls reject domain/identifier-renamed, constants-only, and
opposite-selection clones, and reject both 19- and 21-root inventories.  The
runtime is GCC 13.4.0 and CMake 3.25.1 in
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with `network_policy: none`; its evidence class is `docker_sanity`, not a
locked dataset-release oracle.  A separate read-only computation inside that
network-disabled image independently reproduced the 20-root family hash above.

This conclusion authorizes no JSONL, token/mask evidence, split, export,
training run, dataset release, or benchmark uplift claim.  Optional dataset
handoff remains `not_requested` for every root.
