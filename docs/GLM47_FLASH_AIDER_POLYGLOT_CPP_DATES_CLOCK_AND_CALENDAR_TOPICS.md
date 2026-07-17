# Dates, Clock, And Calendar Topics For GLM C++ SFT Planning

Status: curriculum-planning taxonomy. This is not a claim that every example
below was evaluated in the Aider benchmark.

The complete GLM-4.7-Flash Modal/Aider C++ evaluation identifies time and date
behavior as an area needing more reliable first-try implementation. This note
names the underlying topics at useful curriculum granularity. The official
Aider tasks remain benchmark holdouts: do not add them, their tests, their
references, or close semantic copies to SFT data.

See `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md` for the run
evidence and broader curriculum implications.

## Clock And Duration State Machines

These problems represent time within a bounded cycle or a non-negative
duration. Correctness depends on normalizing before formatting, defining
endpoint behavior, and keeping units separate until conversion is intentional.

- **Clock arithmetic** — add and subtract hours/minutes; normalize negative
  values and wrap at midnight on a 24-hour clock.
- **Countdown timers** — decrement durations, clamp or signal at zero as the
  contract requires, and format the remaining value without borrowing errors.
- **Duration formatting** — convert a total duration into canonical
  day/hour/minute/second components while preserving zero-valued and plural
  rules specified by the API.
- **Elapsed-time accumulation** — combine a sequence of signed or unsigned
  durations without confusing a time-of-day with an elapsed duration.
- **Cross-midnight intervals** — determine duration and containment when a
  range begins on one day and ends on the next.

The benchmark's `clock` exercise is an example of this topic and must remain a
holdout.

## Gregorian Calendar Foundations

Calendar tasks need a single authoritative calendar model. Month lengths,
leap years, and normalization must agree everywhere rather than being
reimplemented independently in each operation.

- **Leap-year rule** — years divisible by 4 are leap years, except years
  divisible by 100 unless they are also divisible by 400.
- **Month-length tables** — select the correct 28/29/30/31-day length from a
  month and year, with February bound to the leap-year rule.
- **General calendar arithmetic** — add or subtract days and months across
  month/year boundaries, including an explicit end-of-month rollover policy.
- **Date difference** — count days between two dates using the requested
  inclusive or exclusive endpoint convention.
- **Ordinal dates** — map calendar dates to day-of-year and back, especially
  around February 29 and year boundaries.
- **Future-date calculations** — compute dates far in the future from a start
  date and a large offset, without iterative overflow or assumptions about a
  short year range.

The benchmark's `gigasecond` exercise is an example of future-date arithmetic
and must remain a holdout.

## Weekday And Recurrence Rules

These tasks combine calendar arithmetic with modular weekday offsets. A robust
solution identifies the first or last valid weekday in a month, then applies a
bounded offset and verifies the result stays in range.

- **Weekday in month** — resolve expressions such as "third Monday" or "last
  Thursday" using weekday-offset arithmetic within the target month.
- **Nth and final occurrences** — distinguish a numbered occurrence from a
  final occurrence, and reject requests for nonexistent fifth occurrences when
  required.
- **Recurring events** — generate rules such as "every second Tuesday" over a
  bounded date range, with clear inclusion rules for the range endpoints.
- **Business-day offsets** — skip weekends or a supplied non-working-day set
  while moving forward or backward from a date.
- **Calendar-window intersections** — find dates satisfying multiple rules,
  such as a recurrence that also lies inside a reporting month.

The benchmark's `meetup` exercise is an example of weekday-in-month logic and
must remain a holdout.

## Civil Time, Time Zones, And Meetings

Civil-time conversion must distinguish local clock fields from an instant.
Offsets may be straightforward fixed arithmetic, but daylight-saving changes
create local times that are ambiguous or do not exist.

- **Timezone conversion** — translate between a local civil time and an
  instant using fixed UTC offsets, including date rollover in either direction.
- **Daylight-saving transitions** — define handling for skipped local times at
  spring-forward and repeated local times at fall-back; never silently treat
  an ambiguous local value as uniquely determined without a policy.
- **Meeting scheduling** — intersect participants' availability ranges after
  converting them to a common instant or offset-aware representation.
- **Offset-aware range overlap** — handle endpoints, half-open versus closed
  intervals, and ranges that cross midnight in more than one time zone.
- **Local presentation** — convert an agreed instant back to each participant's
  local date and time without changing the underlying instant.

## Age, Epoch, And Representation Boundaries

These tasks expose the difference between human calendar components and a
linear timeline. They require an explicit policy for borrowing, signs, and
range limits rather than relying on incidental behavior of a platform clock.

- **Age calculators** — derive elapsed years, months, and days from a
  birthdate to a reference date, borrowing across unequal month lengths and
  year boundaries according to a stated convention.
- **Unix timestamps** — convert between epoch seconds and calendar fields,
  including negative timestamps before 1970 and values near the supported
  integer range.
- **Epoch/calendar round trips** — preserve the represented instant through
  conversion, including leap days and dates immediately around the epoch.
- **Overflow-safe date math** — validate multiplications and additions before
  converting large day or second offsets, and report unsupported ranges rather
  than wrapping silently.
- **Parsing and canonicalization** — reject impossible dates/times before
  normalizing valid input into one unambiguous internal representation.

## Use In Data Design

Create semantically distinct, licensed tasks that exercise one or more topics
above. Keep source families isolated across splits, retain hidden tests outside
training rows, and apply the repository's contamination and admission gates
before adding any candidate to an SFT release. In particular, do not create
near-copies of the Aider `clock`, `gigasecond`, or `meetup` benchmark exercises;
vary the public API, story, input/output representation, and required edge
cases while preserving the intended curriculum skill.
