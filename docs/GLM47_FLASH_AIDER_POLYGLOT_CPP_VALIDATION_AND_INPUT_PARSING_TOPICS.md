# Validation And Input-Parsing Topics For GLM C++ SFT Planning

Status: curriculum-planning taxonomy. This is not a claim that every example
below was evaluated in the Aider benchmark.

The GLM-4.7-Flash Modal/Aider C++ evaluation identifies text/parsing as a weak
area and shows that apparently small input-normalization tasks can still need
repair feedback. This note names validation and parsing topics at useful
curriculum granularity. The official Aider tasks remain benchmark holdouts: do
not add them, their tests, their references, or close semantic copies to SFT
data.

See `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md` for the run
evidence and broader curriculum implications.

## Lexical Validation And Canonicalization

These tasks first decide whether an input belongs to a constrained language,
then produce a canonical representation only for valid input. A dependable
implementation keeps validation separate from cleanup: stripping characters or
coercing values must not turn a malformed input into an accepted one.

- **Phone-number normalization** — accept only the permitted country prefix,
  digit count, separators, and local-prefix rules; emit a normalized digit
  representation only after all checks pass.
- **Email validation** — enforce the task's local-part, separator, and domain
  grammar, including empty labels, repeated dots, forbidden characters, and
  edge-case top-level domains.
- **URL parsing** — decompose a URL into scheme, authority, host, optional
  port, path, query, and fragment while rejecting malformed delimiters,
  unsupported schemes, and incomplete authorities.
- **IPv4 and IPv6 address parsing** — validate per-octet decimal ranges for
  IPv4 and per-segment hexadecimal/compression rules for IPv6 before storing a
  normalized address.
- **Rule-violation rejection** — construct inputs that look superficially
  plausible but break exactly one contract constraint, such as an extra
  separator, disallowed leading zero, missing required field, or trailing
  garbage.
- **Canonical-form round trips** — verify that parse(format(value)) preserves
  the value and that formatting an already normalized valid input is stable.

The benchmark's `phone-number` exercise is an example of normalization with
strict rejection behavior and must remain a holdout.

## Radix, Digit, And Position-Weighted Checks

These tasks interpret a character sequence as digits under a declared numeric
system. Correctness depends on validating every symbol before arithmetic, using
wide enough intermediate types, and treating positional rules as part of the
contract rather than as an afterthought.

- **Arbitrary-base conversion** — convert a sequence of digits between source
  and target bases while rejecting invalid base ranges, empty input, negative
  digits when unsupported, and digits outside the source radix.
- **Leading-zero policy** — preserve, normalize, or reject leading zeros
  according to the public API without confusing an all-zero value with an
  empty representation.
- **Digit alphabets beyond decimal** — map symbols to values consistently,
  handle case only when allowed, and reject characters that have no digit value
  in the requested base.
- **ISBN verification** — apply the relevant weighted checksum, including a
  permitted terminal check symbol and exact position rules; reject misplaced
  separators or check symbols.
- **Luhn validation** — traverse from the correct end, alternate the doubling
  rule by position, fold doubled digits correctly, and reject non-digit or
  degenerate inputs before computing the checksum.
- **Checksum-aware normalization** — remove only explicitly permitted display
  separators; never discard an invalid character merely because the remaining
  digits happen to satisfy a checksum.

The benchmark's `all-your-base` exercise is an example of arbitrary-base
conversion and must remain a holdout.

## Structured Delimiters, Quotes, And Records

Delimited formats require a small state machine rather than a naive split.
Separators may be literal content inside a quoted field, and an opening quote
changes which characters are meaningful until an unambiguous closing state is
reached.

- **CSV row validation** — enforce the declared column count and field types,
  distinguish empty from missing fields, and handle embedded delimiters,
  escaped quotes, and unmatched quotes under the selected CSV dialect.
- **Quoted-field state machines** — model unquoted, quoted, escaped-quote,
  delimiter, and end-of-record states explicitly so trailing characters after
  a closing quote do not pass accidentally.
- **Typed record validation** — parse each field only after the row structure
  is known, then report or reject integer, boolean, date, enumeration, and
  required-field violations according to the contract.
- **JSON-lite parsing** — recognize literals, numbers, strings, arrays, and
  objects within the intentionally supported subset; reject mismatched
  brackets, missing separators, unterminated strings, and invalid escapes.
- **Nested-structure depth** — maintain a stack or recursive parser state for
  nested arrays and objects, including empty containers and a defined maximum
  depth when the API requires one.
- **Exact end-of-input checks** — after parsing one valid value or record,
  allow only permitted trailing whitespace; reject a second value or stray
  characters.

## Coordinates, Moves, And Cross-Field Constraints

Some inputs are lexically valid only when multiple fields agree with one
another. These tasks should parse each component once, map it to a canonical
internal form, and apply the semantic rule separately from character-level
validation.

- **Chess-move validation** — parse square coordinates, piece identifiers, and
  optional captures or promotions under the chosen notation, then check that
  the move obeys the relevant movement and board-consistency rules.
- **Coordinate bounds** — reject alphabetic/numeric coordinates outside the
  declared board or grid before converting them to zero-based indices.
- **Paired-field consistency** — validate relationships such as start before
  end, a declared count matching supplied entries, or an optional field being
  present only with its required companion.
- **Impossible-but-well-formed states** — reject an individually valid input
  combination that violates one global rule, such as a capture with no target,
  duplicate identifier, or contradictory flags.
- **Validation order and diagnostics** — choose a stable precedence for
  failures where the public API exposes errors, while avoiding partial output
  or mutation before the full input is known to be valid.

## Dates And Expiration Policies

Date-bearing identifiers combine strict syntax with a time-dependent semantic
rule. Correct code validates the representation first, maps it to a defined
month or instant boundary, and compares it against a supplied or injected
reference date instead of an uncontrolled system clock.

- **Credit-card expiry checks** — validate the exact month/year format and
  month range, then accept an unexpired card through the appropriate final day
  of its expiry month.
- **Two- versus four-digit year policy** — define the century mapping or
  reject ambiguous years; never rely on an incidental library pivot year.
- **Reference-date injection** — make the current date a controlled argument
  or clock dependency so boundary tests remain deterministic.
- **Calendar-valid fields** — reject month zero, month thirteen, malformed
  separators, and extra digits before applying the logical expiration test.
- **Boundary comparisons** — test the month before, current month, and month
  after the reference point, including year rollover.

## Use In Data Design

Create semantically distinct, licensed tasks that exercise one or more topics
above. Keep source families isolated across splits, retain hidden tests outside
training rows, and apply the repository's contamination and admission gates
before adding any candidate to an SFT release. In particular, do not create
near-copies of the Aider `all-your-base` or `phone-number` benchmark exercises;
vary the public API, story, accepted notation, output representation, and
edge-case combinations while preserving the intended curriculum skill.
