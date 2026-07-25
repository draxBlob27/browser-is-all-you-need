# Independent audit: bit and set reasoning, cycle 001

## Verdict

**Status: `not_completed`.** The exact subject contains 40 selected roots, but
zero roots pass every hard gate. Thirty-eight require repair and fresh
re-verification; `bit-morton-interleave` and `bit-morton-deinterleave` require
replacement because an earlier expansion root already owns both Morton encode
and decode. This is a local-family audit only: it creates no SFT release,
training authorization, or benchmark-uplift claim.

Audit subject: `sha256:a2ab4f2de537d9910487aa46ef818418866c0dd044d4227360a59de14a5e0dbd`.
I independently recomputed the owner-defined subject serialization and the
non-state task-tree digest. They exactly match `.state/audit-subject.json`:

- task tree: `sha256:ad01ce89754b8903cc3ca858be351cec6e6077c1450ca66e66cfa76ca06bb20e`
- roots: 40; root files: 520 (13 per root)
- recorded runtime evidence: 40 normal and 40 sanitizer records, each with two
  discovered CTests; 40 nonzero negative exits
- prompt boundary: 40 role-correct prompt records; rendered prompt size
  2,026–2,231 characters (mean 2,113)
- family screen: 780 recorded passing pairs and three recorded rejected
  controls, but findings below invalidate the semantic meaning of that result
- holdout screen: 1,040 recorded comparisons over 26 official roots; upstream
  revision independently observed as `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`

## Behavior contract used for the audit

Each root must present a solvable C++17 whole-file task: exact input encoding,
output fields, invalid/absent/empty behavior, ordering, ties, overflow, and a
public boundary example. The claimed bit/set mechanism must be implemented and
rejected against a coherent task-specific false substitute. The exact tree
must have positive normal and fresh ASan/UBSan evidence, prompt-safe roles,
seven materially distinct family dimensions, coherent clone controls, and
digest-bound lineage and benchmark evidence. The generalization target is a
semantically varied 40-root numerical-anchor family, not renamed APIs or
single-vector templates.

## Findings

### cycle-001/family/public-contract-incomplete

**Severity:** blocker. **Scope:** all 40 roots. **Status:** open.

Every instruction uses the same generic sentence saying that two operands are
“masks or packed fields” and `bound` is a width, rank, count, or comparison
quantity. It never states which interpretation applies, the packed lane
layout, ignored/high-bit policy, or the exact meanings of `value` and
`auxiliary`; no root has a public example. At least 19 references rely on
undisclosed byte/nibble/upper-lower-field packing. A solver can only learn
those rules from private source/tests. Repair the owner with an explicit
per-root API/behavior table and examples, then regenerate and validate prompts.

### cycle-001/family/discriminator-not-task-specific

**Severity:** blocker. **Scope:** all 40 roots. **Status:** open.

All `.meta/negative_false_substitute.cpp` files implement the same
`{true,0,0}` zero stub. This is neither the curriculum's named wrong
implementation nor a coherent plausible substitute. CMake runs that substitute
only against the single visible vector, not the hidden production assertions.
Replace it with each root's named, compiling wrong algorithm and prove the full
designated suite rejects it in normal and sanitizer modes.

### cycle-001/family/oracle-coverage-not-independent

**Severity:** major. **Scope:** all 40 roots. **Status:** open.

Each visible file checks one result triple and each hidden file checks one
result triple; only the first 20 add a `bound == 0` assertion. No suite
systematically proves duplicate, absent, empty, ordering, tie, overflow, or
packed-lane behavior. Expected results and C++ references are emitted from the
same owner and frequently mirror the same algorithm. The focused test checks
only that one owner-oracle result is nonzero. Add independent deterministic
properties and targeted cases for every public rule.

### cycle-001/family/diversity-controls-invalid

**Severity:** blocker. **Scope:** all 40 roots and all 780 pairs. **Status:** open.

The normalizer does not remove task identifiers/domain nouns as claimed; after
independent removal all 40 public headers reduce to one API shape. A pair
passes on any one-token symmetric difference. Test/negative dimensions include
unique names and strings, so they are not independent semantic proofs. Each
clone control differs from `bit-swar-popcount` only by one appended sentence in
`.docs/introduction.md`; constants, policy, identifiers, selection direction,
reference, and tests are unchanged. The owner nevertheless hard-codes
`coherent` and `production_rejected` to true. Implement real buildable
mutations and independently assert each per-dimension decision.

### cycle-001/bit-morton-pair/semantic-lineage-conflict

**Severity:** blocker. **Scope:** `bit-morton-interleave`,
`bit-morton-deinterleave`. **Status:** open.

The earlier root
`.w8-biayn/data/aider-tasks-expansion-v1/text-grid/coordinate-transformations/coord-morton-interleave`
already exposes and implements sixteen-round Morton encode and decode with x on
even bits and y on odd bits. The two candidates split that same executable
contract into separate generic roots. The stored lineage screen reports
unrelated arithmetic roots as their nearest neighbors, demonstrating that its
token-Jaccard screen missed the semantic conflict. Reject these candidate IDs
and author two genuinely new backfills through the complete creator loop.

### cycle-001/family/evidence-subject-incomplete

**Severity:** blocker. **Scope:** family evidence. **Status:** open.

The audit subject hash is internally reproducible, but its field set omits the
prompt-boundary, lineage, source-inventory, raw/rejected proposal, per-root
receipt, and explicit control hashes. `source-inventory.json` contains counts
only (and its expansion count is now stale), not frozen sorted identities and
digests. The Docker receipt has current host-computed family/control hashes,
but no independently computed in-container mount hash, compiler path/binary
hash, curriculum/spec/focused-test hashes, or per-root starter/test/prompt
digests. Therefore the recorded successful executions do not prove that the
complete final controls, policy, and audit input were exactly what ran.

### cycle-001/family/metadata-provenance-incomplete

**Severity:** moderate. **Scope:** all 40 roots. **Status:** open.

`config.json` omits the clean-room source/license field and declares only the
visible test, although CMake consumes the hidden and negative tests. Provenance
states `clean_room: true` but records no license/usage terms or immutable source
inventory ID. Regenerate complete role and provenance metadata.

### cycle-001/set-symmetric-rank/bound-double-duty

**Severity:** major. **Scope:** `set-symmetric-rank`. **Status:** open.

The reference uses `bound` both as the low-bit mask width and, indirectly, as
rank `bound - 1`; there is no independently supplied rank. This does not match
the advertised general ordered-rank operation or make absent-rank behavior
solvable from the public API. Define separate semantics/API and test them.

### cycle-001/set-jaccard-ordering/operand-double-duty

**Severity:** major. **Scope:** `set-jaccard-ordering`. **Status:** open.

The reference uses `secondary` simultaneously as the second set and its low 16
bits as a comparison numerator, while `bound` becomes a denominator; the
three-valued result code is undocumented. This is not a coherent public
Jaccard comparison contract. Repair the API/reference/oracle together.

## Duplicate, lineage, and contamination report

- Exact selected IDs: 40 unique; exact collisions with legacy/reverify: zero.
- Exact prompt/reference hashes: 40 unique each, but uniqueness is driven in
  part by task names and is not semantic-diversity evidence.
- Semantic lineage: the Morton pair conflicts with the pre-existing combined
  encode/decode root. No other exact semantic conflict was confirmed; the
  current screen is inadequate to prove absence for the remaining roots.
- Official holdouts: no exact ID or exact-content match was found. The stored
  low token-overlap scores are insufficient semantic proof because the
  normalizer preserves candidate-specific nouns/identifiers and does not bind
  the holdout inventory revision/content digest. Contamination remains open
  under `cycle-001/family/evidence-subject-incomplete` rather than being called
  a pass.

## Corpus composition

The family contains 20 bounded bit primitives, three flag operations, and 17
set/combinatorial operations. All are synthetic clean-room candidates, C++17,
single-turn whole-file replacements with two editable files, one generic API
shape, one visible vector, one hidden vector, and the same zero-stub negative
strategy. This template monoculture outweighs the 40 distinct mechanism names.
Tokenizer/mask evidence is not required by the current local-family scope and
was not claimed; exact tokenizer measurement remains a future release gate.

## Root catalog and dispositions

`primary_core_objective` is `not_achieved` for every root: source inspection
often shows the named mechanism, but the required deterministic,
task-specific discriminator is absent. `R` means audit disposition
`repair-and-reverify` with remediation route `repair-in-place`; `X` means
audit disposition `reject` with remediation route `replace`.

| Root | Capability | Findings beyond all-family findings | Disposition |
| --- | --- | --- | --- |
| bit-swar-popcount | SWAR count | — | R |
| bit-fold-parity | XOR parity | — | R |
| bit-width-reversal | bounded reversal | — | R |
| bit-bounded-rotation | bounded rotate | — | R |
| bit-sign-extension | sign extension | — | R |
| bit-field-extraction | field extract | packed contract absent | R |
| bit-field-insertion | field insert | packed offset/source contract absent | R |
| bit-mask-compression | PEXT | — | R |
| bit-mask-deposition | PDEP | — | R |
| bit-morton-interleave | Morton encode | semantic-lineage-conflict | X |
| bit-morton-deinterleave | Morton decode | semantic-lineage-conflict | X |
| bit-gray-encoding | Gray encode | — | R |
| bit-gray-decoding | Gray decode | — | R |
| bit-next-combination | next combination | — | R |
| bit-submask-checksum | submask enumeration | — | R |
| bit-prefix-rank | prefix rank | — | R |
| bit-select-one | select | — | R |
| bit-longest-run | run scan | — | R |
| bit-first-zero-run | first fit | — | R |
| bit-range-toggle | range XOR | packed range absent | R |
| flag-implication-closure | flag closure | packed implication rows absent | R |
| flag-priority-conflicts | conflict pruning | packed conflict rows absent | R |
| flag-two-of-three-quorum | majority | three-voter packing absent | R |
| set-symmetric-rank | symmetric-difference select | bound-double-duty | R |
| set-union-cardinality | union count | — | R |
| set-intersection-select | intersection select | — | R |
| set-partition-validation | partition proof | third set hidden in `unsigned bound` | R |
| set-packed-exact-cover-count | exact cover | nibble packing absent | R |
| set-packed-minimum-cover | minimum cover | nibble packing absent | R |
| set-packed-independent-weight | independent set | graph/weight packing absent | R |
| set-packed-subset-sum | subset sum | nibble packing absent | R |
| set-zeta-transform-checksum | zeta transform | coefficient packing/unused args absent | R |
| set-mobius-roundtrip | Möbius inversion | coefficient packing/unused args absent | R |
| set-xor-basis-maximum | XOR basis max | byte packing/query semantics absent | R |
| set-xor-basis-rank | XOR basis rank | byte packing/unused args absent | R |
| set-packed-transitive-closure | closure | row packing/count policy absent | R |
| set-packed-reachability-layers | BFS layers | row/start packing absent | R |
| set-hamming-nearest-byte | nearest byte | byte packing/target semantics absent | R |
| set-jaccard-ordering | Jaccard compare | operand-double-duty | R |
| set-maximal-disjoint-packing | disjoint packing | byte packing absent | R |

## Next gate

Preserve this report unchanged. Route all finding IDs through
`aider-task-family-remediation`, replace the two Morton roots with genuinely
new IDs/contracts, repair the owner/curriculum/spec/focused tests, regenerate
the complete 40-root family, rerun exact Docker normal/sanitizer and coherent
controls, create a new subject, then request a fresh independent audit. Only
that later audit can close these findings or establish
`local_family_verified`.
