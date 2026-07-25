# Base-Conversion And Invalid-Digit Expansion Curriculum

Status: normative local-family specification for exactly 40 new clean-room
roots. It is not an SFT release, training authorization, or benchmark claim.

## Identity and scope

This family fills the complete 40-root `Numerical anchors / Arbitrary-base
conversion and invalid-digit handling` initial-new-root cell in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`. Its generated
root is exclusively:

```text
.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/base-conversion-invalid-digits/
```

The owner is
`src/w8_biayn/integrations/moonlight_base_conversion_expansion_aider_tasks.py`.
The selected design prompt is
`docs/aider-tasks-spec/prompts/generate-family-spec.md`; implementation and
every later repair use
`docs/aider-tasks-spec/prompts/implement-family-for-sft.md` sequentially.
Every ID below has lineage `new-root`, CC0-1.0 clean-room repository authorship,
and no parent or replacement root.

The official Aider C++ `all-your-base` exercise and all other 25 official roots
are permanent holdouts. No retained root exposes its generic digits/from-base/
to-base API, wording, examples, tests, or reference structure. Existing roots
in `.w8-biayn/data/aider-tasks/`, `.w8-biayn/data/aider-tasks-reverify/`, and
other expansion families are reserved semantic lineages and read-only inputs.

## Family-wide executable contract

Every task uses C++17, strict warnings, deterministic offline tests, a coherent
incomplete starter, complete private reference replacements, a visible test,
a private test, and a compiled plausible-but-wrong implementation that the
same production tests reject. Inputs are bounded as stated; invalid symbols,
malformed width/orientation, empty required data, non-canonical encodings,
and arithmetic overflow fail atomically without partial output. Each prompt
shows only `.docs` and the exact `<task-id>.h/.cpp` editable pair.

The owner must compare all 780 unordered candidate pairs in each of these
seven dimensions independently: public API; owned state or algorithm;
mutation/selection rules; invalid/boundary behavior; reference control flow;
deterministic oracle; topic-specific negative fixture. Each decision is
conjunctive and is derived from emitted docs, declarations, reference source,
visible/private tests, and the reference-to-negative edit—not IDs, declared
kind labels, domain nouns, constants, or raw hashes. It must also materialize,
build, behavior-test, and reject domain/identifier-renamed,
constants-or-policy-only, and opposite-end-selection clones of one emitted
root using that exact evaluator.

## Forty root contracts

The API declarations in this table are the public declarations emitted by the
generator. The Behavior column defines normal, invalid, duplicate/absent, boundary,
ordering/tie, and overflow behavior. The Mechanism column is the required core
and names its forbidden substitute. The Oracle/negative column defines the
private deterministic discriminator.

| ID | Public C++17 API and behavior | Required core mechanism; forbidden substitute | Oracle and coherent negative |
| --- | --- | --- | --- |
| `basecv-radix-frame-stream` | `RadixFrameResult decode_radix_frame(string_view,unsigned)` decodes one canonical most-significant-first frame in radix 2..16, reports consumed digits, rejects empty/leading-zero/over-16-digit input, and checks `uint64_t`. | Single-pass checked Horner accumulation with explicit symbol classification; forbid cleanup-first parsing or deferred generic string conversion. | Independent multiply/add cases plus invalid-radix-digit, leading-zero, and overflow probes. This root owns the three clone controls. |
| `basecv-chunked-decimal-limbs` | `decimal_chunks_to_base1e9(string)` returns little-endian base-1e9 limbs for canonical decimal input up to 180 digits; zero is one zero limb. | Repeated decimal-string division by 1e9 with quotient compaction; forbid `stoull`, floating point, or a precomputed answer. | Recompose chunks by schoolbook decimal multiply/add; negative truncates after two limbs. |
| `basecv-binary-byte-packer` | `pack_binary_groups(string bits, unsigned group)` packs 1/2/4/8-bit groups into bytes, rejects non-binary symbols and non-multiple widths, preserves leading zero groups. | Shift-register packing with explicit group boundary; forbid bitset/string cleanup delegation. | Unpack every emitted group and compare exact width; negative silently pads a partial final group. |
| `basecv-balanced-ternary-ledger` | `parse_balanced_ternary(string)` accepts canonical `N01` digits (`N=-1`) and returns checked signed value; `format_balanced_ternary(int64_t)` emits the unique form. | Signed Horner parse plus quotient/remainder carry normalization for negative remainders; forbid ordinary ternary with a sign prefix. | Exhaustive round-trip on [-4000,4000]; negative maps `N` to zero. |
| `basecv-negabinary-route` | `decode_negabinary(string)` and `encode_negabinary(int32_t)` use base -2 with no sign character and canonical leading zeros. | Negative-base Horner and remainder correction; forbid sign-magnitude binary. | Exhaustive [-4096,4096] round-trip; negative treats the leftmost bit as a sign bit. |
| `basecv-bijective-label-index` | `optional<LabelIndex> label_index(string_view)` returns the one-based value and source width; `index_label(uint64_t)` is the inverse. Empty/lowercase/zero/overflow reject. | One-based quotient correction (`n-1`) rather than zero-based positional digits; forbid ordinary base-26 with A=0. | Boundary labels Z/AA/ZZ/AAA and 20k round-trips; negative uses A=0. |
| `basecv-factoradic-permutation-rank` | `rank_permutation(vector<int>)` and `unrank_permutation(size_t,uint64_t)` convert permutations of 0..n-1 for n<=12 to/from factoradic rank; duplicates/out-of-range/rank overflow reject. | Lehmer digits with shrinking ordered pool; forbid lexicographic enumeration or base-n interpretation. | Exhaustive n<=8 bijection; negative uses fixed radix n for every digit. |
| `basecv-mixed-radix-timecode` | `pack_timecode(const Timecode&)` and `optional<Timecode> unpack_timecode(uint64_t)` convert validated day/hour/minute/second/millisecond fields with checked multiplication; unpack rejects totals whose day field exceeds `unsigned`. | Heterogeneous positional products in declared field order; forbid treating all fields as base 60. | Boundary and random field-product oracle plus out-of-domain `uint64_t` rejection; negative applies 60 to milliseconds. |
| `basecv-dna-quaternary-packet` | `encode_bases(string ACGT)` / `decode_bases(vector<uint8_t>,size_t)` use two bits/base, preserve sequence length, reject invalid glyphs and nonzero unused tail bits. | Four-symbol inverse alphabet plus bit cursor and tail canonicality; forbid hash lookup or dropping length. | All strings through length 7; negative maps G and T to the same code. |
| `basecv-gray-word-radix` | `optional<GrayBinaryWord> gray_hex_to_binary(string_view)` converts 1..8 hexadecimal Gray-code digits to a result carrying the same-width binary bits and source nibble count; lowercase is rejected and leading zeros retained. | Nibble decode followed by prefix-XOR Gray inversion; forbid interpreting Gray bits as ordinary binary. | Exhaustive 16-bit Gray values; negative returns the raw bits. |
| `basecv-crockford-alias-decoder` | `decode_crockford_token(string)` accepts Crockford base32 with documented O/I/L aliases, rejects U and lowercase, and returns canonical spelling plus checked value. | Table-driven alias normalization before Horner arithmetic; forbid permissive standard base32. | Every alphabet/alias and overflow boundary; negative accepts U as V. |
| `basecv-base58-byte-envelope` | `decode_base58_envelope(string)` returns bytes while preserving one zero byte per leading `1`; invalid glyphs fail, empty is absent. | Repeated multiply-58 over a base-256 byte vector; forbid machine-integer accumulation or trimming leading zeros. | Independent repeated-division encoder round-trip; negative collapses all leading `1`s. |
| `basecv-bcd-nibble-register` | `pack_bcd(string decimal, size_t bytes)` / `unpack_bcd(vector<uint8_t>)` use two decimal digits per byte with exact width and canonical left zero padding; nibbles 10..15 reject. | Decimal-pair nibble packing and nibble validation; forbid hexadecimal parsing. | Exhaust all two-byte BCD values; negative accepts A..F nibbles. |
| `basecv-little-endian-digit-vector` | `little_digits_to_uint(vector<uint8_t>,uint8_t radix)` accepts least-significant-first digits with exact trailing-zero width semantics and checked result. | Reverse-direction checked power accumulation; forbid reversing then calling an MSD parser. | Per-position power oracle including repeated high zero digits; negative interprets digits MSD-first. |
| `basecv-sparse-power-numeral` | `sparse_terms_to_value(vector<Term>{exponent,digit},radix)` requires strictly decreasing unique exponents, absent powers mean zero, digits valid, exponent<=31, checked value. | Gap-aware repeated exponentiation and accumulation over sparse terms; forbid dense expansion or unordered overwrite. | Independent dense reconstruction and ordering mutations; negative ignores gaps between exponents. |
| `basecv-redundant-digit-normalizer` | `normalize_redundant(vector<int64_t> lsd_first,radix)` accepts signed/out-of-range coefficients and emits canonical nonnegative digits or failure if the total is negative/overflowing. | Euclidean carry propagation with negative remainder correction; forbid per-digit clamping. | Random coefficient polynomial equality; negative uses C++ truncating remainder directly. |
| `basecv-runlength-numeral-fold` | `fold_run_digits(vector<DigitRun>,radix)` decodes an MSD-first run-length numeral without expanding it; runs positive, digits valid, total length<=1e6, checked value. | Exponentiation-by-squaring geometric block fold; forbid materializing the million-digit string or multiplying once per repeated digit. | Small expanded oracle plus large complexity witness; negative treats each run as one digit. |
| `basecv-streaming-modulus-residue` | `numeral_residue(string,radix,modulus)` returns the residue of up to 1e6 canonical uppercase digits; invalid radix/modulus/symbol fails and full value need not fit. | Bounded modular Horner with overflow-safe add/double multiplication; forbid whole-value conversion. | Big decimal strings cross-checked by chunked modular oracle; negative stops at first zero digit. |
| `basecv-cross-radix-magnitude-compare` | `optional<int> compare_magnitudes(const MagnitudeNumeral&,const MagnitudeNumeral&)` orders canonical nonnegative numerals in bases 2..16 of at most 15 digits; invalid, leading-zero, and overflowing inputs reject. | Dual checked Horner evaluation followed by three-way ordering; forbid digit-count-only or floating-log comparison. | Adversarial near powers and exact equal values; negative compares digit counts only. |
| `basecv-decimal-double-dabble` | `optional<DabbleDecimal> binary_to_decimal_dabble(string_view)` emits canonical decimal digits plus the preserved input-bit count for canonical binary up to 128 bits. | Shift-and-add-3 double-dabble BCD state; forbid ordinary Horner into a machine integer. | Independent decimal-string doubling oracle; negative omits add-3 correction. |
| `basecv-decimal-repeated-halving` | `optional<HalvingBinary> decimal_to_binary_halving(string_view)` emits canonical binary and the number of division rounds for up to 200 decimal digits; malformed/leading-zero input rejects. | In-place decimal quotient/remainder halving; forbid floating point or fixed-width integers. | Decimal-string re-expansion; negative records quotient parity instead of remainder. |
| `basecv-rational-repeating-expansion` | `expand_fraction(numerator,denominator,radix,max_period)` returns integer digits, nonrepeating prefix, and minimal repeating cycle; denominator/radix/period limits validate. | Remainder-position map with long division and cycle extraction; forbid fixed precision truncation. | Recompose as exact rational using gcd; negative terminates when a digit repeats rather than a remainder. |
| `basecv-repeating-expansion-rational` | `parse_repeating(Expansion,radix)` converts explicit integer/nonrepeat/repeat digit sequences to a reduced signed fraction with checked bounds; empty repeat means terminating. | Power formulas and gcd reduction with separate prefix/cycle weights; forbid decimal floating parsing. | Expand-then-parse rational identity; negative gives repeat digits the prefix denominator. |
| `basecv-half-even-fixed-point` | `requantize(FixedDigits,from_radix,to_radix,out_fraction_digits)` converts a bounded fixed-point value and rounds ties to even; invalid scale/digits/overflow reject. | Exact numerator/denominator scaling, quotient/remainder tie classification, carry propagation; forbid floating point. | Exhaustive small rational oracle around half ties; negative always rounds halves upward. |
| `basecv-signed-magnitude-token` | `parse_signed_token(string,radix)` accepts explicit `+`/`-`, rejects negative zero and leading zero magnitude, and returns checked `int64_t`; formatter always emits sign. | Sign-separated magnitude Horner with asymmetric INT64_MIN boundary; forbid signed intermediate accumulation. | INT64_MIN/MAX spellings and sign mutations; negative overflows while negating INT64_MIN magnitude. |
| `basecv-ones-complement-word` | `decode_ones_complement(string bits)` decodes fixed widths 4..32, distinguishes positive and negative zero, and formatter preserves requested zero sign. | Width mask, complement magnitude, dual-zero state; forbid two's-complement cast. | Exhaust every 12-bit word; negative decodes all ones as -1. |
| `basecv-twos-complement-hexword` | `hexword_to_signed(string,unsigned width)` accepts exact uppercase hex width 8/16/32/64 and sign-extends from the declared bit; unused high bits must be canonical. | Explicit width mask and subtract-2^width conversion without implementation-defined casts; forbid `strtoll` base auto-detection. | Boundary words at sign transition; negative applies sign to the first textual hex digit regardless of width. |
| `basecv-excess-k-instrument` | `decode_biased_digits(vector<int>,radix,bias)` converts a fixed-width unsigned code then subtracts a validated bias; encoder chooses exact width and reports unrepresentable values. | Checked unsigned positional decode followed by range-checked bias transformation; forbid per-digit biasing. | Full small-code space bijection; negative subtracts bias from every digit. |
| `basecv-varint-base128-groups` | `decode_varint_groups(vector<uint8_t>)` / `encode_varint_groups(uint64_t)` use 7 payload bits plus continuation, reject unterminated/overlong/nonminimal encodings. | Little-endian base-128 payload accumulation with continuation state and canonical-length check; forbid treating full bytes as base-256. | Boundary values at each group count; negative accepts `0x80,0x00`. |
| `basecv-byteorder-base256-words` | `words_to_integer(vector<uint8_t>,ByteOrder)` and fixed-width inverse preserve every byte and distinguish endian order; width 1..8. | Direction-selected shift accumulation and indexed emission; forbid host reinterpret-cast/endian dependence. | Cross-endian byte reversal and all widths; negative always uses host/little order. |
| `basecv-carryless-polynomial-word` | `optional<Gf2PolynomialWord> parse_gf2_polynomial(string_view)` returns mask and degree; `format_gf2_polynomial(const Gf2PolynomialWord&)` emits canonical descending terms and rejects incoherent state. | Sparse exponent bit setting with canonical descending grammar; forbid integer addition of powers with duplicate ambiguity. | Exhaust 16-bit masks; negative admits duplicate exponents. |
| `basecv-zeckendorf-fibonacci-code` | `ZeckendorfCodec::decode(string_view)` / `encode(uint64_t)` use Fibonacci weights, require positive values, no adjacent ones, and a canonical top one. | Greedy largest-Fibonacci decomposition and adjacency invariant; forbid ordinary binary positional weights. | Exhaust values through 100k; negative accepts adjacent ones. |
| `basecv-combinadic-subset-rank` | `rank_subset(n,sorted_indices)` / `unrank_subset(n,k,rank)` use the combinatorial number system; duplicates/order/range invalid. | Binomial-weight sum and descending greedy unrank; forbid bitmask-as-integer ranking. | Exhaust n<=12 against lexicographic subset inventory; negative uses powers of two. |
| `basecv-residue-crt-reconstruction` | `reconstruct_residues(vector<Residue>)` accepts pairwise-coprime moduli and canonical residues, returns checked value in [0,product), rejects inconsistent/overflowing systems. | Incremental CRT using extended gcd and modular multiplication; forbid concatenating residue digits. | Exhaust small coprime systems; negative assumes moduli are always coprime. |
| `basecv-prime-exponent-product` | `exponents_to_integer(vector<PrimePower>)` / `integer_to_exponents(uint64_t,prime_basis)` convert a factor-exponent representation with sorted unique primes; residual factors reject. | Checked exponentiation-by-squaring and repeated exact division; forbid positional radix weighting. | Factor/product round-trip over bounded basis; negative treats exponents as ordinary digits. |
| `basecv-unary-run-radix` | `unary_runs_to_digits(vector<size_t> runs,radix)` converts a bounded tally represented as separated runs to canonical radix digits without concatenating a giant unary string; zero uses empty run list. | Checked run summation then repeated quotient/remainder emission; forbid using run count rather than run lengths. | Partition-invariance oracle; negative counts separators as tally marks. |
| `basecv-sexagesimal-angle` | `angle_to_microarcseconds(Sexagesimal)` / inverse validate sign, degrees, minutes, seconds, fractional micros and canonicalize negative zero. | Mixed-radix checked accumulation with sign applied after magnitude; forbid decimal-degree floating point. | Boundary carry/borrow and exact inverse; negative uses 100 seconds per minute. |
| `basecv-fixedpoint-base100-chunks` | `decimal_money_to_chunks(string)` / inverse use signed base-100 little-endian cent-pair chunks with exact two-digit scale, rejecting extra precision and noncanonical zeros. | Decimal lexical split plus pairwise chunk construction and signed canonicalization; forbid `stod` or base-10 single digits. | Exact cents round-trip including large magnitudes; negative drops an odd leading digit. |
| `basecv-morton-interleave-radix` | `xy_to_quadrants(uint8_t,uint8_t)` returns exactly eight base-4 digits; `optional<pair<uint8_t,uint8_t>> quadrants_to_xy(...)` reverses them and rejects any digit at least four. | Paired-bit extraction/interleave and ordered quadrant emission; forbid concatenating or swapping the coordinate bit streams. | Exhaust the full 8-bit coordinate grid and independently reject invalid inverse digits; negative swaps x/y bit selection. |
| `basecv-canonical-cantor-pair` | `pair_to_radix(Coord,unsigned radix)` and `radix_to_pair(string,unsigned radix)` encode a coordinate through Cantor pairing then a task-specific uppercase radix spelling; bases 3..20, checked triangular arithmetic. | Overflow-safe diagonal pairing/unpairing plus bounded spelling parser; forbid delimiter concatenation or generic two-field conversion. | Grid bijection and triangular boundaries; negative uses row-major `x*base+y`. |

## Files, build, and evidence

Each root has exactly two editable files, `<id>.h` then `<id>.cpp`; references
are `.meta/example.h/.cpp`; tests are `visible_test.cpp` and
`.meta/private_test.cpp`; `.meta/negative.cpp` is compiled as a replacement
implementation and must fail the same private contract. CMake uses explicit
Unix Makefiles, C++17, `-Wall -Wextra -Wpedantic -Werror`, positive CTest
discovery, and separate clean normal and fresh ASan/UBSan builds.

The repository pinned sanity image is diagnostic `docker_sanity`, not a
family-designated locked oracle. It must run with `--network none` and bind the
live/archive/mounted family hashes, image ID, compiler path/version/hash, CMake
version, owner/curriculum/policy hashes, per-root reference hashes, equal
normal/sanitizer counts, and executed-negative outcomes. Any owner, curriculum,
task, test, scaffold, normalizer, or policy change invalidates all prior
receipts.

## Acceptance and non-claims

Acceptance requires exactly 40 real roots, 780 passing seven-dimension pair
records, three coherent changed/buildable/behavior-passing clone controls that
the production screen rejects in all seven dimensions, 40 compiled and
executed negative fixtures, strict prompt/role/reference mapping, no ID/hash/
lineage/semantic collision across all three trees, 1,040 holdout comparisons,
and equal positive normal/fresh-sanitizer Docker counts for every root and
control. A read-only independent audit must bind the final exact tree and leave
zero retained review, repair, conflict, or contamination dispositions.

The strongest possible result is `local_family_verified`. It creates no JSONL,
split, release, export, tokenizer/mask evidence, training authorization, or
benchmark-uplift claim.

## Docs Alignment (Remediation Docs Phase)

The model-facing `.docs` follow the official Aider Polyglot C++ conventions.
`.docs/introduction.md` is a `# <Title>` header plus a domain-motivating
narrative about numeral representations; it never states the contract or
mentions the evaluation harness. `.docs/instructions.md` starts with
`# Instructions`, keeps the complete behavioral contract and Public API block,
adds a `## Examples` section rendering the visible check's concrete cases, and
expresses the mechanism requirement naturally ("Convert with <mechanism>;
<substitute> cannot produce the documented canonical form.") instead of
anti-cheat scaffolding. The generator's focused test asserts this docs shape
and rejects meta/audit vocabulary in both docs files.
