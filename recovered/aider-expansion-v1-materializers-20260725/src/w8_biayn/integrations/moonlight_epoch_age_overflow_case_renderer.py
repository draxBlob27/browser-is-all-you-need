"""Task-specific C++ renderers for the epoch/age/overflow expansion family.

This module deliberately contains no group-level fallback.  Every operation in
the binding curriculum must have an explicit public API, reference algorithm,
oracle, and coherent false substitute before the owner can materialize it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedCase:
    declarations: str
    signature: str
    reference_body: str
    negative_body: str
    visible_checks: str
    hidden_checks: str
    result_semantics: str


def _case(
    signature: str,
    reference_body: str,
    negative_body: str,
    visible_checks: str,
    hidden_checks: str,
    result_semantics: str,
    declarations: str = "",
) -> RenderedCase:
    return RenderedCase(
        declarations=declarations,
        signature=signature,
        reference_body=reference_body,
        negative_body=negative_body,
        visible_checks=visible_checks,
        hidden_checks=hidden_checks,
        result_semantics=result_semantics,
    )


def _epoch_case(operation: str, fn: str) -> RenderedCase | None:
    if operation == "epoch_range_intersection":
        return _case(f"std::optional<EpochRange> {fn}(EpochRange left, EpochRange right)","if(left.begin>left.end||right.begin>right.end)return std::nullopt;auto begin=std::max(left.begin,right.begin),end=std::min(left.end,right.end);if(begin>end)return std::nullopt;return EpochRange{begin,end};","return EpochRange{std::min(left.begin,right.begin),std::max(left.end,right.end)};",f"auto a={fn}(EpochRange{{1,5}},EpochRange{{5,9}}); require(a&&a->begin==5&&a->end==5);",f"require(!{fn}(EpochRange{{4,3}},EpochRange{{0,1}})); require(!{fn}(EpochRange{{0,1}},EpochRange{{2,3}}));","EpochRange is the exact nonempty closed intersection after independent endpoint validation.","struct EpochRange { std::int64_t begin; std::int64_t end; };")
    if operation == "era_consensus":
        return _case(f"std::optional<std::int64_t> {fn}(std::uint32_t sample, std::uint32_t modulus, const std::vector<std::int64_t>& pivots)","if(modulus<2||sample>=modulus||pivots.empty())return std::nullopt;std::optional<std::int64_t> agreed;for(auto pivot:pivots){auto m=static_cast<std::int64_t>(modulus),base=(pivot/m)*m;std::array<std::int64_t,3> choices{{base+sample-m,base+sample,base+sample+m}};auto best=choices[0];auto distance=detail::distance(best,pivot);bool tie=false;for(int i=1;i<3;++i){auto d=detail::distance(choices[i],pivot);if(d<distance){best=choices[i];distance=d;tie=false;}else if(d==distance)tie=true;}if(tie||(agreed&&*agreed!=best))return std::nullopt;agreed=best;}return agreed;","if(pivots.empty())return std::nullopt;return (pivots.front()/modulus)*modulus+sample;",f"auto a={fn}(3,16,{{18,20}}); require(a&&*a==19);",f"require(!{fn}(3,16,{{1,30}})); require(!{fn}(16,16,{{0}})); require(!{fn}(1,1,{{0}}));","The result exists only when every pivot has the same unique nearest modular lift. A modulus below 2, an out-of-range sample, an empty pivot list, a tie, or pivot disagreement is rejected.")
    if operation == "leap_table_digest":
        return _case(f"std::optional<LeapDigest> {fn}(const std::vector<LeapDelta>& table)","if(table.empty())return std::nullopt;std::int64_t total=0;for(std::size_t i=0;i<table.size();++i){if(i&&table[i-1].transition>=table[i].transition)return std::nullopt;if(!detail::checked_add(total,table[i].delta,total))return std::nullopt;}std::int64_t span=0;if(!detail::checked_sub(table.back().transition,table.front().transition,span))return std::nullopt;return LeapDigest{table.size(),total,span};","return LeapDigest{table.size(),table.back().delta,table.back().transition-table.front().transition};",f"auto a={fn}({{{{10,1}},{{20,-2}},{{40,3}}}}); require(a&&a->count==3&&a->cumulative==2&&a->span==30);",f"require(!{fn}({{}})); require(!{fn}({{{{2,1}},{{1,2}}}})); require(!{fn}({{{{0,std::numeric_limits<std::int64_t>::max()}},{{1,1}}}}));","LeapDigest binds a strictly ordered table to checked cumulative delta and endpoint span. An empty, non-increasing, or overflowing table is rejected.","struct LeapDelta { std::int64_t transition; std::int64_t delta; }; struct LeapDigest { std::size_t count; std::int64_t cumulative; std::int64_t span; };")
    if operation == "signed_duration_parts":
        return _case(f"DurationParts {fn}(std::int64_t nanoseconds)","const bool negative=nanoseconds<0;const std::uint64_t magnitude=negative?static_cast<std::uint64_t>(-(nanoseconds+1))+1U:static_cast<std::uint64_t>(nanoseconds);auto rest=magnitude;const auto hours=rest/3600000000000ULL;rest%=3600000000000ULL;const auto minutes=rest/60000000000ULL;rest%=60000000000ULL;const auto seconds=rest/1000000000ULL;rest%=1000000000ULL;return DurationParts{negative,hours,static_cast<std::uint32_t>(minutes),static_cast<std::uint32_t>(seconds),static_cast<std::uint32_t>(rest)};","return DurationParts{nanoseconds<0,static_cast<std::uint64_t>(nanoseconds/3600000000000LL),0,0,0};",f"auto a={fn}(-3661000000002LL); require(a.negative&&a.hours==1&&a.minutes==1&&a.seconds==1&&a.nanos==2);",f"auto b={fn}(std::numeric_limits<std::int64_t>::min()); require(b.negative&&b.minutes<60&&b.seconds<60&&b.nanos<1000000000U); auto z={fn}(0); require(!z.negative&&z.hours==0); auto neg={fn}(-90061000000000LL); require(neg.negative&&neg.hours==25&&neg.minutes==1&&neg.seconds==1&&neg.nanos==0);","DurationParts is a canonical unsigned magnitude decomposition with an explicit sign.","struct DurationParts { bool negative; std::uint64_t hours; std::uint32_t minutes; std::uint32_t seconds; std::uint32_t nanos; };")
    if operation == "floor_split":
        return _case(
            f"std::optional<DaySecond> {fn}(std::int64_t unix_seconds)",
            """std::int64_t day = unix_seconds / 86400;
    std::int64_t second = unix_seconds % 86400;
    if (second < 0) { second += 86400; --day; }
    return DaySecond{day, static_cast<std::int32_t>(second)};""",
            """return DaySecond{unix_seconds / 86400,
                     static_cast<std::int32_t>(unix_seconds % 86400)};""",
            f"""auto a = {fn}(86401); require(a && a->day == 1 && a->second_of_day == 1);
    auto b = {fn}(-1); require(b && b->day == -1 && b->second_of_day == 86399);""",
            f"""auto c = {fn}(std::numeric_limits<std::int64_t>::min());
    require(c && c->second_of_day >= 0 && c->second_of_day < 86400);
    require(c->day == -106751991167301LL && c->second_of_day == 30592);""",
            "DaySecond.day is the pure-Euclidean partition index satisfying `unix_seconds == day * 86400 + second_of_day`, and second_of_day is in [0,86400).",
            "struct DaySecond { std::int64_t day; std::int32_t second_of_day; };",
        )
    if operation == "normalize_subsecond":
        return _case(
            f"std::optional<SecondMillis> {fn}(std::int64_t seconds, std::int64_t millis)",
            """const std::int64_t carry = millis / 1000;
    std::int64_t rem = millis % 1000;
    std::int64_t adjusted = carry;
    if (rem < 0) { rem += 1000; --adjusted; }
    std::int64_t total = 0;
    if (!detail::checked_add(seconds, adjusted, total)) return std::nullopt;
    return SecondMillis{total, static_cast<std::int32_t>(rem)};""",
            """if (millis < 0) millis = 0;
    if (millis > 999) millis = 999;
    return SecondMillis{seconds, static_cast<std::int32_t>(millis)};""",
            f"""auto a = {fn}(7, 2501); require(a && a->seconds == 9 && a->millis == 501);
    auto b = {fn}(7, -1); require(b && b->seconds == 6 && b->millis == 999);""",
            f"""require(!{fn}(std::numeric_limits<std::int64_t>::max(), 1000));
    auto z = {fn}(0, -2000); require(z && z->seconds == -2 && z->millis == 0);""",
            "SecondMillis is canonical: millis is [0,1000), with all carry applied to seconds.",
            "struct SecondMillis { std::int64_t seconds; std::int32_t millis; };",
        )
    if operation == "normalize_nanos":
        return _case(
            f"std::optional<CanonicalTimespec> {fn}(std::int64_t seconds, std::int64_t nanos)",
            """std::int64_t carry = nanos / 1000000000;
    std::int64_t rem = nanos % 1000000000;
    if (rem < 0) { rem += 1000000000; --carry; }
    std::int64_t normalized = 0;
    if (!detail::checked_add(seconds, carry, normalized)) return std::nullopt;
    return CanonicalTimespec{normalized, static_cast<std::int32_t>(rem)};""",
            """if (nanos < 0) return CanonicalTimespec{seconds, 0};
    return CanonicalTimespec{seconds + nanos / 1000000000,
                             static_cast<std::int32_t>(nanos % 1000000000)};""",
            f"""auto a = {fn}(5, 1000000007); require(a && a->tv_sec == 6 && a->tv_nsec == 7);
    auto b = {fn}(5, -7); require(b && b->tv_sec == 4 && b->tv_nsec == 999999993);""",
            f"""require(!{fn}(std::numeric_limits<std::int64_t>::min(), -1000000000));
    auto z = {fn}(0, -2000000000); require(z && z->tv_sec == -2 && z->tv_nsec == 0);""",
            "CanonicalTimespec has a nonnegative tv_nsec below one billion.",
            "struct CanonicalTimespec { std::int64_t tv_sec; std::int32_t tv_nsec; };",
        )
    if operation == "fixed_fraction":
        return _case(
            f"std::uint32_t {fn}(std::uint32_t fraction)",
            """const std::uint64_t product = static_cast<std::uint64_t>(fraction) * 1000000000ULL;
    std::uint64_t q = product >> 32U;
    const std::uint64_t r = product & 0xffffffffULL;
    if (r > 0x80000000ULL || (r == 0x80000000ULL && (q & 1ULL))) ++q;
    return static_cast<std::uint32_t>(q);""",
            """return static_cast<std::uint32_t>((fraction / 1000U) * 233U);""",
            f"""require({fn}(0U) == 0U); require({fn}(0x80000000U) == 500000000U);""",
            f"""require({fn}(0xffffffffU) == 1000000000U);
    require({fn}(1U) == 0U);""",
            "The return is the nearest-even nanosecond count for a 32-bit binary fraction.",
        )
    if operation == "nearest_era32":
        return _case(
            f"std::optional<std::int64_t> {fn}(std::uint32_t field, std::int64_t pivot)",
            """constexpr std::int64_t era = 4294967296LL;
    std::int64_t base = pivot / era;
    if (pivot < 0 && pivot % era != 0) --base;
    std::array<std::int64_t, 3> choices{};
    for (int i = -1; i <= 1; ++i) {
        std::int64_t high = 0;
        if (!detail::checked_add(base, i, high) || !detail::checked_mul(high, era, choices[static_cast<std::size_t>(i + 1)]) ||
            !detail::checked_add(choices[static_cast<std::size_t>(i + 1)], static_cast<std::int64_t>(field), choices[static_cast<std::size_t>(i + 1)])) return std::nullopt;
    }
    std::int64_t best = choices[0]; std::uint64_t distance = detail::distance(best, pivot); bool tie = false;
    for (std::size_t i = 1; i < choices.size(); ++i) { const auto d = detail::distance(choices[i], pivot); if (d < distance) { best = choices[i]; distance = d; tie = false; } else if (d == distance) tie = true; }
    return tie ? std::nullopt : std::optional<std::int64_t>(best);""",
            """(void)pivot; return static_cast<std::int64_t>(field);""",
            f"""auto a = {fn}(7U, 4294967300LL); require(a && *a == 4294967303LL);
    auto b = {fn}(0xffffffffU, -2); require(b && *b == -1);""",
            f"""require(!{fn}(0U, 2147483648LL));
    auto c = {fn}(1U, -4294967296LL); require(c && *c == -4294967295LL);""",
            "The result is the unique 2^32-era lift nearest pivot; half-era ties are absent.",
        )
    if operation == "nearest_era10":
        return _case(
            f"std::optional<std::int64_t> {fn}(std::uint16_t transmitted_week, std::int64_t pivot_week)",
            """if (transmitted_week >= 1024U) return std::nullopt;
    std::int64_t era = pivot_week / 1024;
    if (pivot_week < 0 && pivot_week % 1024 != 0) --era;
    std::int64_t best = 0; std::uint64_t best_distance = std::numeric_limits<std::uint64_t>::max(); bool tied = false;
    for (int step = -1; step <= 1; ++step) { std::int64_t candidate = (era + step) * 1024 + transmitted_week; const auto d = detail::distance(candidate, pivot_week); if (d < best_distance) { best = candidate; best_distance = d; tied = false; } else if (d == best_distance) tied = true; }
    return tied ? std::nullopt : std::optional<std::int64_t>(best);""",
            """if (transmitted_week >= 1024U) return std::nullopt;
    return (pivot_week / 1024) * 1024 + transmitted_week;""",
            f"""auto a = {fn}(2U, 1025); require(a && *a == 1026);
    auto b = {fn}(1023U, -2); require(b && *b == -1);""",
            f"""require(!{fn}(1024U, 0)); require(!{fn}(0U, 512));""",
            "The result is the unique nearest absolute GPS week; invalid fields and exact ties fail.",
        )
    if operation == "week_seconds":
        return _case(
            f"std::optional<std::int64_t> {fn}(std::int64_t week, std::int64_t second_of_week)",
            """if (week < 0 || second_of_week < 0 || second_of_week >= 604800) return std::nullopt;
    std::int64_t base = 0; std::int64_t result = 0;
    if (!detail::checked_mul(week, 604800, base) || !detail::checked_add(base, second_of_week, result)) return std::nullopt;
    return result;""",
            """if (week < 0 || second_of_week < 0 || second_of_week > 604800) return std::nullopt;
    return week * 604800 + second_of_week;""",
            f"""auto a = {fn}(2, 5); require(a && *a == 1209605); require(!{fn}(1, 604800));""",
            f"""require(!{fn}(-1, 0)); require(!{fn}(std::numeric_limits<std::int64_t>::max(), 1));""",
            "The result is checked continuous GPS seconds; week and second-of-week must be canonical. A negative week or a second-of-week outside [0,604800) is rejected.",
        )
    if operation == "filetime_split":
        return _case(
            f"std::optional<FiletimeUnix> {fn}(std::uint64_t ticks)",
            """constexpr std::uint64_t delta = 116444736000000000ULL;
    constexpr std::uint64_t per_second = 10000000ULL;
    if (ticks >= delta) { const std::uint64_t d = ticks - delta; const std::uint64_t s = d / per_second; if (s > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) return std::nullopt; return FiletimeUnix{static_cast<std::int64_t>(s), static_cast<std::uint32_t>(d % per_second)}; }
    const std::uint64_t deficit = delta - ticks; const std::uint64_t q = deficit / per_second; const std::uint64_t r = deficit % per_second;
    const std::uint64_t magnitude = q + (r != 0U ? 1U : 0U); if (magnitude > (std::uint64_t{1} << 63U)) return std::nullopt;
    const std::int64_t seconds = magnitude == (std::uint64_t{1} << 63U) ? std::numeric_limits<std::int64_t>::min() : -static_cast<std::int64_t>(magnitude);
    return FiletimeUnix{seconds, static_cast<std::uint32_t>(r == 0U ? 0U : per_second - r)};""",
            """const auto signed_ticks = static_cast<std::int64_t>(ticks);
    return FiletimeUnix{(signed_ticks - 116444736000000000LL) / 10000000LL, 0U};""",
            f"""auto a = {fn}(116444736000000005ULL); require(a && a->unix_seconds == 0 && a->residual_ticks == 5U);
    auto b = {fn}(116444735999999999ULL); require(b && b->unix_seconds == -1 && b->residual_ticks == 9999999U);""",
            f"""auto z = {fn}(0); require(z && z->unix_seconds == -11644473600LL && z->residual_ticks == 0U);
    require({fn}(std::numeric_limits<std::uint64_t>::max()).has_value());
    auto frac = {fn}(116444735999999995ULL); require(frac && frac->unix_seconds == -1 && frac->residual_ticks == 9999995U);""",
            "FiletimeUnix is a floor Unix-second split with residual 100ns ticks in [0,10^7).",
            "struct FiletimeUnix { std::int64_t unix_seconds; std::uint32_t residual_ticks; };",
        )
    if operation == "unsigned_epoch_offset":
        return _case(
            f"std::optional<std::int64_t> {fn}(std::uint64_t mac_seconds)",
            """constexpr std::uint64_t delta = 2082844800ULL;
    if (mac_seconds >= delta) { const std::uint64_t positive = mac_seconds - delta; if (positive > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) return std::nullopt; return static_cast<std::int64_t>(positive); }
    return -static_cast<std::int64_t>(delta - mac_seconds);""",
            """if (mac_seconds < 2082844800ULL) return std::nullopt;
    return static_cast<std::int64_t>(mac_seconds - 2082844800ULL);""",
            f"""auto a = {fn}(2082844800ULL); require(a && *a == 0); auto b = {fn}(0); require(b && *b == -2082844800LL);""",
            f"""require(!{fn}(std::numeric_limits<std::uint64_t>::max()));
    auto c = {fn}(2082844801ULL); require(c && *c == 1);""",
            "The result is signed Unix seconds, including valid pre-1970 Mac epoch values.",
        )
    if operation == "mjd_split":
        return _case(
            f"MjdMillis {fn}(std::int64_t total_millis)",
            """std::int64_t day = total_millis / 86400000;
    std::int64_t rem = total_millis % 86400000;
    if (rem < 0) { rem += 86400000; --day; }
    return MjdMillis{day, static_cast<std::int32_t>(rem)};""",
            """return MjdMillis{total_millis / 86400000, static_cast<std::int32_t>(total_millis % 86400000)};""",
            f"""auto a = {fn}(86400007); require(a.day == 1 && a.millis_of_day == 7);
    auto b = {fn}(-1); require(b.day == -1 && b.millis_of_day == 86399999);""",
            f"""auto c = {fn}(std::numeric_limits<std::int64_t>::min()); require(c.millis_of_day >= 0 && c.millis_of_day < 86400000);""",
            "MjdMillis contains the Euclidean MJD day and a nonnegative millisecond-of-day.",
            "struct MjdMillis { std::int64_t day; std::int32_t millis_of_day; };",
        )
    if operation == "excel_serial":
        return _case(
            f"std::optional<ExcelSerialDate> {fn}(std::int64_t serial)",
            """if (serial < 1) return std::nullopt;
    if (serial == 60) return ExcelSerialDate{1900, 2, 29, true};
    const std::int64_t offset = serial < 60 ? serial - 1 : serial - 2;
    const auto civil = detail::civil_from_days(detail::days_from_civil(1900, 1, 1) + offset);
    return ExcelSerialDate{civil[0], static_cast<int>(civil[1]), static_cast<int>(civil[2]), false};""",
            """if (serial < 1) return std::nullopt;
    const auto civil = detail::civil_from_days(detail::days_from_civil(1899, 12, 31) + serial);
    return ExcelSerialDate{civil[0], static_cast<int>(civil[1]), static_cast<int>(civil[2]), false};""",
            f"""auto a = {fn}(1); require(a && a->year == 1900 && a->month == 1 && a->day == 1 && !a->fictitious);
    auto b = {fn}(60); require(b && b->day == 29 && b->fictitious);""",
            f"""auto c = {fn}(61); require(c && c->year == 1900 && c->month == 3 && c->day == 1);
    require(!{fn}(0));""",
            "ExcelSerialDate preserves serial 60 as an explicit fictitious label and adjusts later serials once. Serial 0 and negative serials are rejected.",
            "struct ExcelSerialDate { std::int64_t year; int month; int day; bool fictitious; };",
        )
    if operation == "dos_fields":
        return _case(
            f"std::optional<DosDateTime> {fn}(std::uint32_t packed)",
            """const int second = static_cast<int>(packed & 31U) * 2; const int minute = static_cast<int>((packed >> 5U) & 63U); const int hour = static_cast<int>((packed >> 11U) & 31U); const int day = static_cast<int>((packed >> 16U) & 31U); const int month = static_cast<int>((packed >> 21U) & 15U); const int year = 1980 + static_cast<int>((packed >> 25U) & 127U);
    if (hour > 23 || minute > 59 || second > 59 || !detail::valid_date(year, month, day)) return std::nullopt;
    return DosDateTime{year, month, day, hour, minute, second};""",
            """return DosDateTime{1980 + static_cast<int>((packed >> 25U) & 127U), static_cast<int>((packed >> 21U) & 15U), static_cast<int>((packed >> 16U) & 31U), static_cast<int>((packed >> 11U) & 31U), static_cast<int>((packed >> 5U) & 63U), static_cast<int>(packed & 31U) * 2};""",
            f"""const std::uint32_t p = (40U << 25U) | (12U << 21U) | (31U << 16U) | (23U << 11U) | (59U << 5U) | 29U;
    auto a = {fn}(p); require(a && a->year == 2020 && a->second == 58);""",
            f"""require(!{fn}(0U)); const std::uint32_t bad = (2U << 21U) | (31U << 16U); require(!{fn}(bad));""",
            "DosDateTime contains validated DOS bit fields; impossible dates and times fail.",
            "struct DosDateTime { int year; int month; int day; int hour; int minute; int second; };",
        )
    if operation == "bcd_fields":
        return _case(
            f"std::optional<BcdTimestamp> {fn}(const std::array<std::uint8_t, 7>& bytes)",
            """std::array<int, 7> v{};
    for (std::size_t i = 0; i < bytes.size(); ++i) { const int hi = bytes[i] >> 4U; const int lo = bytes[i] & 15U; if (hi > 9 || lo > 9) return std::nullopt; v[i] = hi * 10 + lo; }
    const int year = v[0] * 100 + v[1]; if (!detail::valid_date(year, v[2], v[3]) || v[4] > 23 || v[5] > 59 || v[6] > 59) return std::nullopt;
    return BcdTimestamp{year, v[2], v[3], v[4], v[5], v[6]};""",
            """const int year = static_cast<int>(bytes[0]) * 100 + bytes[1];
    return BcdTimestamp{year, bytes[2], bytes[3], bytes[4], bytes[5], bytes[6]};""",
            f"""auto a = {fn}({{{{0x20,0x24,0x02,0x29,0x23,0x59,0x58}}}}); require(a && a->year == 2024 && a->day == 29);""",
            f"""require(!{fn}({{{{0x20,0x24,0x1a,0x01,0x00,0x00,0x00}}}}));
    require(!{fn}({{{{0x20,0x23,0x02,0x29,0x00,0x00,0x00}}}}));""",
            "BcdTimestamp is produced only after every nibble and the cross-field Gregorian label validate.",
            "struct BcdTimestamp { int year; int month; int day; int hour; int minute; int second; };",
        )
    if operation == "signed48":
        return _case(
            f"std::int64_t {fn}(const std::array<std::uint8_t, 6>& bytes)",
            """std::uint64_t raw = 0; for (const auto byte : bytes) raw = (raw << 8U) | byte;
    if ((raw & (std::uint64_t{1} << 47U)) == 0U) return static_cast<std::int64_t>(raw);
    const std::uint64_t magnitude = (std::uint64_t{1} << 48U) - raw;
    return -static_cast<std::int64_t>(magnitude);""",
            """std::uint64_t raw = 0; for (const auto byte : bytes) raw = (raw << 8U) | byte; return static_cast<std::int64_t>(raw);""",
            f"""require({fn}({{{{0,0,0,0,0,1}}}}) == 1); require({fn}({{{{0xff,0xff,0xff,0xff,0xff,0xff}}}}) == -1);""",
            f"""require({fn}({{{{0x80,0,0,0,0,0}}}}) == -140737488355328LL);
    require({fn}({{{{0x7f,0xff,0xff,0xff,0xff,0xff}}}}) == 140737488355327LL);""",
            "The return is the portable sign extension of a big-endian 48-bit two's-complement word.",
        )
    if operation == "step_lookup":
        return _case(
            f"std::optional<std::int64_t> {fn}(std::int64_t utc, const std::vector<LeapStep>& steps)",
            """if (steps.empty()) return std::nullopt;
    for (std::size_t i = 1; i < steps.size(); ++i) if (steps[i - 1].utc_transition >= steps[i].utc_transition) return std::nullopt;
    const auto it = std::upper_bound(steps.begin(), steps.end(), utc, [](std::int64_t value, const LeapStep& item) { return value < item.utc_transition; });
    if (it == steps.begin()) return std::nullopt; return std::prev(it)->offset;""",
            """for (const auto& step : steps) if (step.utc_transition > utc) return step.offset; return std::nullopt;""",
            f"""std::vector<LeapStep> s{{{{10,32}},{{20,33}}}}; auto a = {fn}(20,s); require(a && *a == 33); require(!{fn}(9,s));""",
            f"""std::vector<LeapStep> bad{{{{20,33}},{{10,32}}}}; require(!{fn}(30,bad)); require(!{fn}(0,{{}}));
    std::vector<LeapStep> table{{{{10,32}},{{20,33}}}}; auto last = {fn}(25,table); require(last && *last == 33); require(!{fn}(5,table));""",
            "The result is the offset of the last applicable transition in a strictly increasing table.",
            "struct LeapStep { std::int64_t utc_transition; std::int64_t offset; };",
        )
    if operation == "utc_to_tai":
        return _case(
            f"std::optional<std::int64_t> {fn}(std::int64_t utc, const std::vector<LeapStep>& steps)",
            """if (steps.empty()) return std::nullopt;
    const LeapStep* selected = nullptr;
    for (const auto& step : steps) { if (selected && selected->utc_transition >= step.utc_transition) return std::nullopt; if (step.utc_transition <= utc) selected = &step; }
    if (!selected) return std::nullopt; std::int64_t tai = 0; if (!detail::checked_add(utc, selected->offset, tai)) return std::nullopt; return tai;""",
            """if (steps.empty()) return std::nullopt; return utc + steps.back().offset;""",
            f"""std::vector<LeapStep> s{{{{0,10}},{{100,11}}}}; auto a = {fn}(50,s); require(a && *a == 60); auto b = {fn}(100,s); require(b && *b == 111);""",
            f"""std::vector<LeapStep> bad{{{{1,2}},{{1,3}}}}; require(!{fn}(2,bad)); std::vector<LeapStep> huge{{{{0,1}}}}; require(!{fn}(std::numeric_limits<std::int64_t>::max(),huge));""",
            "The result applies the last UTC transition offset with table validation and checked addition. An instant before the first transition is rejected.",
            "struct LeapStep { std::int64_t utc_transition; std::int64_t offset; };",
        )
    if operation == "tai_to_utc":
        return _case(
            f"std::optional<std::int64_t> {fn}(std::int64_t tai, const std::vector<TaiUtcTransition>& steps)",
            """if (steps.empty()) return std::nullopt;
    std::optional<std::int64_t> answer;
    for (std::size_t i = 0; i < steps.size(); ++i) { if (i && steps[i-1].utc_transition >= steps[i].utc_transition) return std::nullopt; const std::int64_t begin = steps[i].utc_transition; const std::int64_t end = i + 1 < steps.size() ? steps[i+1].utc_transition : std::numeric_limits<std::int64_t>::max(); std::int64_t mapped_begin = 0; if (!detail::checked_add(begin,steps[i].offset,mapped_begin)) return std::nullopt; std::int64_t candidate = 0; if (!detail::checked_sub(tai,steps[i].offset,candidate)) continue; if (tai >= mapped_begin && candidate >= begin && candidate < end) { if (answer) return std::nullopt; answer = candidate; } }
    return answer;""",
            """if (steps.empty()) return std::nullopt; return tai - steps.back().offset;""",
            f"""std::vector<TaiUtcTransition> s{{{{0,10}},{{100,11}}}}; auto a = {fn}(60,s); require(a && *a == 50); auto b = {fn}(111,s); require(b && *b == 100);""",
            f"""std::vector<TaiUtcTransition> s{{{{0,10}},{{100,11}}}}; require(!{fn}(110,s)); std::vector<TaiUtcTransition> bad{{{{2,1}},{{1,2}}}}; require(!{fn}(3,bad));""",
            "The result is the unique UTC preimage; positive-leap gaps and ambiguous mappings fail. Empty or non-increasing tables are rejected.",
            "struct TaiUtcTransition { std::int64_t utc_transition; std::int64_t offset; };",
        )
    if operation == "leap_label":
        return _case(
            f"bool {fn}(const UtcLabel& label, const std::vector<std::int64_t>& leap_days)",
            """if (!detail::valid_date(label.year,label.month,label.day) || label.hour < 0 || label.hour > 23 || label.minute < 0 || label.minute > 59 || label.second < 0 || label.second > 60) return false;
    if (label.second < 60) return true; if (label.hour != 23 || label.minute != 59) return false;
    if (!std::is_sorted(leap_days.begin(),leap_days.end()) || std::adjacent_find(leap_days.begin(),leap_days.end()) != leap_days.end()) return false;
    const auto day = detail::days_from_civil(label.year,label.month,label.day); return std::binary_search(leap_days.begin(),leap_days.end(),day);""",
            """(void)leap_days; return label.second >= 0 && label.second <= 60;""",
            f"""UtcLabel a{{2016,12,31,23,59,60}}; require({fn}(a,{{detail::days_from_civil(2016,12,31)}})); UtcLabel b{{2016,12,31,12,0,60}}; require(!{fn}(b,{{detail::days_from_civil(2016,12,31)}}));""",
            f"""UtcLabel bad{{2019,2,29,0,0,0}}; require(!{fn}(bad,{{}})); UtcLabel ordinary{{2020,2,29,1,2,3}}; require({fn}(ordinary,{{}}));""",
            "True means the Gregorian UTC label is valid and a :60 label is an allowlisted day end.",
            "struct UtcLabel { std::int64_t year; int month; int day; int hour; int minute; int second; };",
        )
    if operation == "nano_day":
        return _case(
            f"NanoDay {fn}(std::int64_t epoch_nanos)",
            """constexpr std::int64_t unit = 86400000000000LL; std::int64_t day = epoch_nanos / unit; std::int64_t rem = epoch_nanos % unit; if (rem < 0) { rem += unit; --day; } return NanoDay{day,rem};""",
            """return NanoDay{epoch_nanos / 86400000000000LL, epoch_nanos % 86400000000000LL};""",
            f"""auto a = {fn}(86400000000001LL); require(a.day == 1 && a.nanos_of_day == 1); auto b = {fn}(-1); require(b.day == -1 && b.nanos_of_day == 86399999999999LL);""",
            f"""auto c = {fn}(std::numeric_limits<std::int64_t>::min()); require(c.nanos_of_day >= 0 && c.nanos_of_day < 86400000000000LL);""",
            "NanoDay is the Euclidean split without negating the input.",
            "struct NanoDay { std::int64_t day; std::int64_t nanos_of_day; };",
        )
    if operation == "rational_ticks":
        return _case(
            f"std::optional<std::int64_t> {fn}(std::int64_t ticks, std::uint64_t numerator, std::uint64_t denominator)",
            """if (denominator == 0U || numerator > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()) || denominator > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) return std::nullopt;
    const std::int64_t den = static_cast<std::int64_t>(denominator); const std::int64_t num = static_cast<std::int64_t>(numerator); const std::int64_t q = ticks / den; const std::int64_t r = ticks % den; std::int64_t whole = 0; std::int64_t part = 0; if (!detail::checked_mul(q,num,whole) || !detail::checked_mul(r,num,part)) return std::nullopt; std::int64_t rounded = part / den; const std::int64_t rem = part % den; const std::uint64_t abs_rem = detail::distance(rem,0); const std::uint64_t twice = abs_rem * 2U; if (twice > denominator || (twice == denominator && ((whole + rounded) & 1LL))) rounded += part < 0 ? -1 : 1; std::int64_t answer = 0; if (!detail::checked_add(whole,rounded,answer)) return std::nullopt; return answer;""",
            """if (denominator == 0U) return std::nullopt; return ticks * static_cast<std::int64_t>(numerator) / static_cast<std::int64_t>(denominator);""",
            f"""auto a = {fn}(3,5,2); require(a && *a == 8); auto b = {fn}(1,1,2); require(b && *b == 0);""",
            f"""auto c = {fn}(3,1,2); require(c && *c == 2); require(!{fn}(1,1,0)); require(!{fn}(std::numeric_limits<std::int64_t>::max(),2,1));""",
            "The result is the checked nearest-even rational conversion, with multiplication split around division.",
        )
    return None


_DATE_DECL = "struct Date { std::int64_t year; int month; int day; };"


def _age_case(operation: str, fn: str) -> RenderedCase | None:
    if operation == "age_threshold_date":
        return _case(f"std::optional<Date> {fn}(Date birth, std::int64_t age)","if(!detail::valid(birth)||age<0)return std::nullopt;std::int64_t year=0;if(!detail::checked_add(birth.year,age,year))return std::nullopt;return Date{year,birth.month,std::min(birth.day,detail::days_in_month(year,birth.month))};","if(age<0)return std::nullopt;return Date{birth.year+age,birth.month,birth.day};",f"auto a={fn}(Date{{2000,2,29}},21); require(a&&a->year==2021&&a->month==2&&a->day==28);",f"require(!{fn}(Date{{2020,13,1}},1)); require(!{fn}(Date{{2020,1,1}},-1)); require(!{fn}(Date{{std::numeric_limits<std::int64_t>::max(),1,1}},1));","The date is the earliest clamped calendar anniversary at the requested nonnegative age.",_DATE_DECL)
    if operation in {"age_feb28", "age_march1"}:
        feb28 = operation == "age_feb28"
        observed = "Date{year, 2, 28}" if feb28 else "Date{year, 3, 1}"
        wrong = "Date{year, 3, 1}" if feb28 else "Date{year, 2, 28}"
        policy_asof = "Date{2003,2,28}" if feb28 else "Date{2003,3,1}"
        return _case(
            f"std::optional<std::int64_t> {fn}({'FebruaryObservedBirth' if feb28 else 'MarchObservedBirth'} birth, Date as_of)",
            f"""if (!detail::valid(birth) || !detail::valid(as_of) || detail::less(as_of,birth)) return std::nullopt;
    std::int64_t years = 0; if (!detail::checked_sub(as_of.year,birth.year,years)) return std::nullopt; std::int64_t year = 0; if (!detail::checked_add(birth.year,years,year)) return std::nullopt;
    Date anniversary = birth.month == 2 && birth.day == 29 && !detail::leap(year) ? {observed} : Date{{year,birth.month,birth.day}};
    if (detail::less(as_of,anniversary)) --years; return years;""",
            f"""if (!detail::valid(birth) || !detail::valid(as_of) || detail::less(as_of,birth)) return std::nullopt;
    std::int64_t years = 0; if (!detail::checked_sub(as_of.year,birth.year,years)) return std::nullopt; std::int64_t year = 0; if (!detail::checked_add(birth.year,years,year)) return std::nullopt;
    Date anniversary = birth.month == 2 && birth.day == 29 && !detail::leap(year) ? {wrong} : Date{{year,birth.month,birth.day}};
    if (detail::less(as_of,anniversary)) --years; return years;""",
            f"""auto a = {fn}({('FebruaryObservedBirth' if feb28 else 'MarchObservedBirth')}{{2000,2,29}},Date{{2001,{2 if feb28 else 3},{28 if feb28 else 1}}}); require(a && *a == 1);
    auto b = {fn}({('FebruaryObservedBirth' if feb28 else 'MarchObservedBirth')}{{2000,2,29}},Date{{2001,{2 if feb28 else 2},{27 if feb28 else 28}}}); require(b && *b == 0);""",
            f"""require(!{fn}({('FebruaryObservedBirth' if feb28 else 'MarchObservedBirth')}{{2020,2,30}},Date{{2021,1,1}})); require(!{fn}({('FebruaryObservedBirth' if feb28 else 'MarchObservedBirth')}{{2020,1,2}},Date{{2020,1,1}}));
    auto policy = {fn}({('FebruaryObservedBirth' if feb28 else 'MarchObservedBirth')}{{2000,2,29}},{policy_asof}); require(policy && *policy == 3);""",
            "The return is completed anniversaries under the documented leapling observation policy.",
            _DATE_DECL + ("\nstruct FebruaryObservedBirth { std::int64_t year; int month; int day; };" if feb28 else "\nstruct MarchObservedBirth { std::int64_t year; int month; int day; };"),
        )
    if operation == "age_clamped":
        return _case(
            f"std::optional<AgeParts> {fn}(Date birth, Date as_of)",
            """if (!detail::valid(birth) || !detail::valid(as_of) || detail::less(as_of,birth)) return std::nullopt; if(birth.year==as_of.year&&birth.month==as_of.month&&birth.day==as_of.day)return AgeParts{0,0,0};
    std::int64_t years = 0; if (!detail::checked_sub(as_of.year,birth.year,years)) return std::nullopt; Date anchor = detail::add_years_clamped(birth,years); if (detail::less(as_of,anchor)) { --years; anchor = detail::add_years_clamped(birth,years); }
    int months = 0; while (months < 11) { Date next=anchor; if(next.month==12){if(!detail::checked_add(next.year,1,next.year))return std::nullopt;next.month=1;}else{++next.month;}next.day=std::min(next.day,detail::days_in_month(next.year,next.month)); if (detail::less(as_of,next)) break; anchor = next; ++months; }
    const auto days = detail::serial(as_of)-detail::serial(anchor); return AgeParts{years,months,static_cast<int>(days)};""",
            """if (!detail::valid(birth) || !detail::valid(as_of) || detail::less(as_of,birth)) return std::nullopt; const auto days=detail::serial(as_of)-detail::serial(birth); return AgeParts{days/365,static_cast<int>((days%365)/30),static_cast<int>((days%365)%30)};""",
            f"""auto a={fn}(Date{{2020,1,31}},Date{{2021,3,3}}); require(a && a->years==1 && a->months==1 && a->days==3);""",
            f"""auto b={fn}(Date{{2020,2,29}},Date{{2021,2,28}}); require(b && b->years==1 && b->months==0 && b->days==0); require(!{fn}(Date{{1,13,1}},Date{{2,1,1}})); auto extreme={fn}(Date{{std::numeric_limits<std::int64_t>::min(),1,1}},Date{{std::numeric_limits<std::int64_t>::min(),1,1}});require(extreme&&extreme->years==0&&extreme->months==0&&extreme->days==0); for(int day=27;day<=28;++day){{auto trace={fn}(Date{{2020,2,29}},Date{{2021,2,day}});require(trace.has_value());}} auto policy={fn}(Date{{2020,1,31}},Date{{2021,3,3}}); require(policy && policy->years==1 && policy->months==1 && policy->days==3);""",
            "AgeParts applies clamped anniversaries, then clamped whole months, then exact residual days. Invalid or reversed dates are rejected.",
            _DATE_DECL + "\nstruct AgeParts { std::int64_t years; int months; int days; };",
        )
    if operation == "age_borrowed":
        return _case(
            f"std::optional<AgeParts> {fn}(Date earlier, Date later)",
            """if (!detail::valid(earlier)||!detail::valid(later)||detail::less(later,earlier)) return std::nullopt; std::int64_t y=0; if(!detail::checked_sub(later.year,earlier.year,y)) return std::nullopt; int m=later.month-earlier.month; int d=later.day-earlier.day; if(d<0){ int pm=later.month-1; std::int64_t py=later.year; if(pm==0){pm=12;--py;} d+=detail::days_in_month(py,pm);--m;} if(m<0){m+=12;--y;} return AgeParts{y,m,d};""",
            """if (!detail::valid(earlier)||!detail::valid(later)||detail::less(later,earlier)) return std::nullopt; return AgeParts{later.year-earlier.year,later.month-earlier.month,later.day-earlier.day};""",
            f"""auto a={fn}(Date{{2020,1,20}},Date{{2021,3,2}}); require(a && a->years==1 && a->months==1 && a->days==10);""",
            f"""auto b={fn}(Date{{2020,5,30}},Date{{2021,1,4}}); require(b && b->years==0 && b->months==7 && b->days==5); require(!{fn}(Date{{2,1,1}},Date{{1,1,1}})); std::vector<Date> ordered{{Date{{2019,12,31}},Date{{2020,1,1}}}}; auto trace={fn}(ordered[0],ordered[1]); require(trace&&trace->days==1);""",
            "AgeParts is component subtraction with an actual preceding-month borrow before the year borrow. Invalid or reversed dates are rejected, and the year subtraction is checked.",
            _DATE_DECL + "\nstruct AgeParts { std::int64_t years; int months; int days; };",
        )
    if operation == "birthday_nearest":
        return _case(
            f"std::optional<BirthdayChoice> {fn}(Date birth, Date as_of)",
            """if(!detail::valid(birth)||!detail::valid(as_of)||detail::less(as_of,birth)) return std::nullopt; Date current=detail::birthday_in_year(birth,as_of.year,false); Date previous=detail::less(as_of,current)?detail::birthday_in_year(birth,as_of.year-1,false):current; Date next=detail::less(as_of,current)?current:detail::birthday_in_year(birth,as_of.year+1,false); const auto back=detail::serial(as_of)-detail::serial(previous); const auto forward=detail::serial(next)-detail::serial(as_of); return BirthdayChoice{back<=forward?previous:next,back<=forward,back<=forward?back:forward};""",
            """if(!detail::valid(birth)||!detail::valid(as_of)) return std::nullopt; const int delta=as_of.month-birth.month; return BirthdayChoice{Date{as_of.year+(delta>6?1:0),birth.month,birth.day},delta<=6,delta};""",
            f"""auto a={fn}(Date{{2000,12,31}},Date{{2020,1,2}}); require(a && a->date.year==2019 && a->previous);""",
            f"""auto b={fn}(Date{{2000,1,1}},Date{{2020,7,2}}); require(b && b->date.year==2020 && b->previous); require(!{fn}(Date{{0,2,30}},Date{{1,1,1}}));
    auto tie={fn}(Date{{2019,6,15}},Date{{2019,12,15}}); require(tie && tie->previous && tie->date.year==2019 && tie->distance_days==183); require(!{fn}(Date{{2020,6,1}},Date{{2020,5,31}}));""",
            "BirthdayChoice names the nearest valid anniversary, preferring the previous anniversary on a tie. Invalid or reversed dates are rejected.",
            _DATE_DECL + "\nstruct BirthdayChoice { Date date; bool previous; std::int64_t distance_days; };",
        )
    if operation == "milestone":
        return _case(
            f"std::optional<Date> {fn}(Date birth, Date as_of, const std::vector<int>& ages)",
            """if(!detail::valid(birth)||!detail::valid(as_of)) return std::nullopt; for(std::size_t i=0;i<ages.size();++i){ if(ages[i]<=0||(i&&ages[i-1]>=ages[i])) return std::nullopt; if(birth.year>std::numeric_limits<std::int64_t>::max()-ages[i]) return std::nullopt; Date d=detail::birthday_in_year(birth,birth.year+ages[i],false); if(!detail::less(d,as_of)) return d; } return std::nullopt;""",
            """(void)as_of; if(ages.empty()) return std::nullopt; return detail::birthday_in_year(birth,birth.year+ages.front(),false);""",
            f"""auto a={fn}(Date{{2000,2,29}},Date{{2021,1,1}},{{18,21,30}}); require(a && a->year==2021 && a->month==2 && a->day==28);""",
            f"""require(!{fn}(Date{{2000,1,1}},Date{{2050,1,1}},{{18,18}})); require(!{fn}(Date{{2000,1,1}},Date{{2100,1,1}},{{18,21}}));""",
            "The return is the first valid strictly increasing milestone anniversary not before as_of.",
            _DATE_DECL,
        )
    if operation == "majority_epoch":
        return _case(
            f"std::optional<std::int64_t> {fn}(Date birth, int majority_years, int utc_offset_minutes)",
            """if(!detail::valid(birth)||majority_years<0||utc_offset_minutes < -1440||utc_offset_minutes>1440) return std::nullopt; if(birth.year>std::numeric_limits<std::int64_t>::max()-majority_years) return std::nullopt; Date majority=detail::birthday_in_year(birth,birth.year+majority_years,false); std::int64_t minutes=0; if(!detail::checked_mul(detail::serial(majority),1440,minutes)||!detail::checked_add(minutes,-utc_offset_minutes,minutes)) return std::nullopt; return minutes;""",
            """if(!detail::valid(birth)) return std::nullopt; return detail::serial(birth)*1440+static_cast<std::int64_t>(majority_years)*365*1440-utc_offset_minutes;""",
            f"""auto a={fn}(Date{{2000,2,29}},18,60); require(a && *a==detail::serial(Date{{2018,2,28}})*1440-60);""",
            f"""require(!{fn}(Date{{2000,1,1}},-1,0)); require(!{fn}(Date{{2000,1,1}},18,2000));""",
            "The result is the checked UTC minute containing local midnight on the majority anniversary. Negative majority years, offsets outside +/-1440 minutes, and overflow are rejected.",
            _DATE_DECL,
        )
    if operation == "cohort_cutoff":
        return _case(
            f"std::optional<std::int64_t> {fn}(Date birth, int cutoff_month, int cutoff_day)",
            """if(!detail::valid(birth)||cutoff_month<1||cutoff_month>12) return std::nullopt; int day=cutoff_day; if(cutoff_month==2&&cutoff_day==29&&!detail::leap(birth.year)) day=28; if(day<1||day>detail::days_in_month(birth.year,cutoff_month)) return std::nullopt; const bool after=birth.month>cutoff_month||(birth.month==cutoff_month&&birth.day>day); if(after&&birth.year==std::numeric_limits<std::int64_t>::max()) return std::nullopt; return birth.year+(after?1:0);""",
            """(void)cutoff_month; (void)cutoff_day; return detail::valid(birth)?std::optional<std::int64_t>(birth.year):std::nullopt;""",
            f"""auto a={fn}(Date{{2020,9,1}},8,31); require(a&&*a==2021); auto b={fn}(Date{{2020,8,31}},8,31); require(b&&*b==2020);""",
            f"""auto c={fn}(Date{{2019,2,28}},2,29); require(c&&*c==2019); require(!{fn}(Date{{2019,1,1}},13,1));""",
            "The result is the school-year cohort selected by a validated cutoff, with a Feb-29 common-year policy.",
            _DATE_DECL,
        )
    if operation == "actuarial":
        return _case(
            f"std::optional<std::int64_t> {fn}(ActuarialBirth birth, Date as_of)",
            """if(!detail::valid(birth)||!detail::valid(as_of)||detail::less(as_of,birth)) return std::nullopt; std::int64_t completed=0; if(!detail::checked_sub(as_of.year,birth.year,completed)) return std::nullopt; Date this_year=detail::birthday_in_year(birth,as_of.year,false); if(detail::less(as_of,this_year)) --completed; std::int64_t previous_year=0,next_year=0; if(!detail::checked_add(birth.year,completed,previous_year)||!detail::checked_add(previous_year,1,next_year)) return std::nullopt; Date previous=detail::birthday_in_year(birth,previous_year,false); Date next=detail::birthday_in_year(birth,next_year,false); const auto back=detail::serial(as_of)-detail::serial(previous); const auto forward=detail::serial(next)-detail::serial(as_of); return completed+(forward<back?1:0);""",
            """if(!detail::valid(birth)||!detail::valid(as_of)) return std::nullopt; std::int64_t age=as_of.year-birth.year; if(as_of.month-birth.month>=6) ++age; return age;""",
            f"""auto a={fn}(ActuarialBirth{{2000,1,1}},Date{{2020,7,3}}); require(a&&*a==21); auto b={fn}(ActuarialBirth{{2000,1,1}},Date{{2020,6,30}}); require(b&&*b==20);""",
            f"""auto c={fn}(ActuarialBirth{{2000,7,1}},Date{{2021,1,1}}); require(c&&*c==21); require(!{fn}(ActuarialBirth{{2,1,1}},Date{{1,1,1}}));""",
            "The return rounds completed age upward only when the next birthday is strictly closer. Invalid or reversed dates are rejected, and all year arithmetic is checked.",
            _DATE_DECL + "\nstruct ActuarialBirth { std::int64_t year; int month; int day; operator Date() const { return Date{year,month,day}; } };",
        )
    if operation == "gestational":
        return _case(
            f"std::optional<WeekDayAge> {fn}(Date start, Date as_of)",
            """if(!detail::valid(start)||!detail::valid(as_of)) return std::nullopt; const auto days=detail::serial(as_of)-detail::serial(start); if(days<0||days>45*7) return std::nullopt; return WeekDayAge{static_cast<int>(days/7),static_cast<int>(days%7)};""",
            """if(!detail::valid(start)||!detail::valid(as_of)) return std::nullopt; return WeekDayAge{static_cast<int>((as_of.year-start.year)*52+(as_of.month-start.month)*4),as_of.day-start.day};""",
            f"""auto a={fn}(Date{{2024,1,1}},Date{{2024,2,1}}); require(a&&a->weeks==4&&a->days==3);""",
            f"""require(!{fn}(Date{{2024,1,2}},Date{{2024,1,1}})); require(!{fn}(Date{{2024,1,1}},Date{{2025,1,1}}));""",
            "WeekDayAge is the exact elapsed-day count split into weeks and days within [0,45 weeks]. Invalid or reversed dates and spans above 45 weeks are rejected.",
            _DATE_DECL + "\nstruct WeekDayAge { int weeks; int days; };",
        )
    if operation == "age_fraction":
        return _case(
            f"std::optional<Fraction> {fn}(Date birth, Date as_of)",
            """if(!detail::valid(birth)||!detail::valid(as_of)||detail::less(as_of,birth)) return std::nullopt; std::int64_t num=detail::serial(as_of)-detail::serial(birth); if(!detail::checked_mul(num,400,num)) return std::nullopt; std::int64_t den=146097; const auto g=std::gcd(num,den); return Fraction{num/g,den/g};""",
            """if(!detail::valid(birth)||!detail::valid(as_of)) return std::nullopt; return Fraction{(detail::serial(as_of)-detail::serial(birth))/365,1};""",
            f"""auto a={fn}(Date{{2000,1,1}},Date{{2001,1,1}}); require(a&&a->numerator==48800&&a->denominator==48699);""",
            f"""auto z={fn}(Date{{2020,2,29}},Date{{2020,2,29}}); require(z&&z->numerator==0&&z->denominator==1); require(!{fn}(Date{{2,1,1}},Date{{1,1,1}}));""",
            "Fraction is exact elapsed days divided by 146097/400, reduced without floating point. Invalid or reversed dates are rejected.",
            _DATE_DECL + "\nstruct Fraction { std::int64_t numerator; std::int64_t denominator; };",
        )
    if operation == "age_band":
        return _case(
            f"std::optional<std::size_t> {fn}(Date birth, Date as_of, const std::vector<std::int64_t>& thresholds)",
            """if(!detail::valid(birth)||!detail::valid(as_of)||detail::less(as_of,birth)||!std::is_sorted(thresholds.begin(),thresholds.end())||std::adjacent_find(thresholds.begin(),thresholds.end())!=thresholds.end()||(!thresholds.empty()&&thresholds.front()<0)) return std::nullopt; std::int64_t age=0; if(!detail::checked_sub(as_of.year,birth.year,age)) return std::nullopt; if(detail::less(as_of,detail::birthday_in_year(birth,as_of.year,false))) --age; return static_cast<std::size_t>(std::upper_bound(thresholds.begin(),thresholds.end(),age)-thresholds.begin());""",
            """if(!detail::valid(birth)||!detail::valid(as_of)) return std::nullopt; const auto age=as_of.year-birth.year; return static_cast<std::size_t>(std::upper_bound(thresholds.begin(),thresholds.end(),age)-thresholds.begin());""",
            f"""auto a={fn}(Date{{2000,12,31}},Date{{2020,1,1}},{{10,18,20}}); require(a&&*a==2);""",
            f"""require(!{fn}(Date{{2000,1,1}},Date{{2020,1,1}},{{10,10}})); auto b={fn}(Date{{2000,1,1}},Date{{2020,1,1}},{{10,20}}); require(b&&*b==2);""",
            "The return is the upper-bound band of completed anniversary age after threshold validation. Invalid or reversed dates, unsorted or duplicated thresholds, and negative thresholds are rejected.",
            _DATE_DECL,
        )
    if operation == "age_series":
        return _case(
            f"std::optional<std::vector<std::int64_t>> {fn}(Date birth, const std::vector<Date>& events)",
            """if(!detail::valid(birth)) return std::nullopt; std::vector<std::int64_t> result; result.reserve(events.size()); Date prior=birth; for(const auto event:events){ if(!detail::valid(event)||detail::less(event,birth)||detail::less(event,prior)) return std::nullopt; std::int64_t age=0; if(!detail::checked_sub(event.year,birth.year,age)) return std::nullopt; if(detail::less(event,detail::birthday_in_year(birth,event.year,false))) --age; result.push_back(age); prior=event;} return result;""",
            """std::vector<std::int64_t> result; for(const auto event:events) result.push_back(event.year-birth.year); return result;""",
            f"""auto a={fn}(Date{{2000,12,31}},{{Date{{2019,12,30}},Date{{2019,12,31}},Date{{2020,1,1}}}}); require(a&&*a==std::vector<std::int64_t>({{18,19,19}}));""",
            f"""require(!{fn}(Date{{2000,1,1}},{{Date{{2002,1,1}},Date{{2001,1,1}}}})); require(!{fn}(Date{{2000,2,30}},{{}}));""",
            "The vector contains transactional completed ages for nondecreasing valid events. Disordered, invalid, or pre-birth events and unrepresentable year differences are rejected.",
            _DATE_DECL,
        )
    if operation == "eligibility":
        return _case(
            f"std::optional<DateRange> {fn}(Date birth, int minimum_age, int maximum_age)",
            """if(!detail::valid(birth)||minimum_age<0||maximum_age<=minimum_age||birth.year>std::numeric_limits<std::int64_t>::max()-maximum_age) return std::nullopt; return DateRange{detail::birthday_in_year(birth,birth.year+minimum_age,false),detail::birthday_in_year(birth,birth.year+maximum_age,false)};""",
            """if(!detail::valid(birth)) return std::nullopt; return DateRange{Date{birth.year+minimum_age,birth.month,birth.day},Date{birth.year+maximum_age,birth.month,birth.day+1}};""",
            f"""auto a={fn}(Date{{2000,2,29}},18,21); require(a&&a->begin.day==28&&a->end.year==2021);""",
            f"""require(!{fn}(Date{{2000,1,1}},21,18)); require(!{fn}(Date{{2000,1,1}},-1,18));""",
            "DateRange is half-open [minimum-age anniversary, maximum-age anniversary). A negative minimum age or a maximum age not greater than the minimum is rejected.",
            _DATE_DECL + "\nstruct DateRange { Date begin; Date end; };",
        )
    if operation == "leapling_count":
        return _case(
            f"std::optional<std::int64_t> {fn}(Date birth, Date through)",
            """if(!detail::valid(birth)||birth.month!=2||birth.day!=29||!detail::valid(through)||detail::less(through,birth)) return std::nullopt; std::int64_t count=0; if(!detail::checked_sub(through.year,birth.year,count)) return std::nullopt; Date observed=detail::birthday_in_year(birth,through.year,false); if(detail::less(through,observed)) --count; return count;""",
            """if(!detail::valid(birth)||!detail::valid(through)) return std::nullopt; std::int64_t count=0; for(std::int64_t y=birth.year+4;y<=through.year;y+=4) if(detail::leap(y)) ++count; return count;""",
            f"""auto a={fn}(Date{{2000,2,29}},Date{{2003,2,28}}); require(a&&*a==3);""",
            f"""auto b={fn}(Date{{2000,2,29}},Date{{2001,2,27}}); require(b&&*b==0); require(!{fn}(Date{{2000,1,1}},Date{{2001,1,1}})); for(int year=2001;year<=2003;++year){{auto trace={fn}(Date{{2000,2,29}},Date{{year,2,28}});require(trace&&*trace==year-2000);}}""",
            "The return counts Feb-28-policy observed birthdays without iterating days. Only a valid February 29 birth date is accepted, invalid or reversed dates are rejected, and the year subtraction is checked.",
            _DATE_DECL,
        )
    if operation == "retirement":
        return _case(
            f"std::optional<Date> {fn}(Date birth, int retirement_years)",
            """if(!detail::valid(birth)||retirement_years<0||birth.year>std::numeric_limits<std::int64_t>::max()-retirement_years) return std::nullopt; const auto target=birth.year+retirement_years; const bool month_end=birth.day==detail::days_in_month(birth.year,birth.month); const int day=month_end?detail::days_in_month(target,birth.month):std::min(birth.day,detail::days_in_month(target,birth.month)); return Date{target,birth.month,day};""",
            """if(!detail::valid(birth)) return std::nullopt; return Date{birth.year+retirement_years,birth.month,birth.day};""",
            f"""auto a={fn}(Date{{2000,2,29}},1); require(a&&a->year==2001&&a->day==28); auto b={fn}(Date{{2000,4,30}},1); require(b&&b->day==30);""",
            f"""auto c={fn}(Date{{2000,2,28}},4); require(c&&c->day==28); require(!{fn}(Date{{2000,1,1}},-1));""",
            "The return preserves month-end status; otherwise it only clamps an invalid target day. Negative retirement years are rejected.",
            _DATE_DECL,
        )
    if operation == "sibling_gap":
        return _case(
            f"std::optional<AgeParts> {fn}(Date first, Date second)",
            """if(!detail::valid(first)||!detail::valid(second)) return std::nullopt; if(detail::less(second,first)) std::swap(first,second); std::int64_t y=0; if(!detail::checked_sub(second.year,first.year,y)) return std::nullopt; int m=second.month-first.month; int d=second.day-first.day; if(d<0){int pm=second.month-1;std::int64_t py=second.year;if(pm==0){pm=12;--py;}d+=detail::days_in_month(py,pm);--m;}if(m<0){m+=12;--y;}return AgeParts{y,m,d};""",
            """if(!detail::valid(first)||!detail::valid(second)) return std::nullopt; auto days=detail::distance(detail::serial(first),detail::serial(second)); return AgeParts{static_cast<std::int64_t>(days/365),static_cast<int>((days%365)/30),static_cast<int>((days%365)%30)};""",
            f"""auto a={fn}(Date{{2021,6,1}},Date{{2020,4,30}}); require(a&&a->years==1&&a->months==1&&a->days==2);""",
            f"""auto z={fn}(Date{{2020,1,1}},Date{{2020,1,1}}); require(z&&z->years==0&&z->months==0&&z->days==0); auto leap={fn}(Date{{2019,3,1}},Date{{2020,3,1}}); require(leap&&leap->years==1&&leap->months==0&&leap->days==0); require(!{fn}(Date{{1,0,1}},Date{{1,1,1}}));""",
            "AgeParts is the order-independent canonical calendar gap using actual borrowed month length. Invalid dates are rejected and the year subtraction is checked.",
            _DATE_DECL + "\nstruct AgeParts { std::int64_t years; int months; int days; };",
        )
    if operation == "completed_months":
        return _case(
            f"std::optional<std::int64_t> {fn}(MonthlyAnniversaryBirth birth, Date as_of)",
            """if(!detail::valid(birth)||!detail::valid(as_of)||detail::less(as_of,birth)) return std::nullopt; std::int64_t year_delta=0; if(!detail::checked_sub(as_of.year,birth.year,year_delta)) return std::nullopt; std::int64_t months=0; if(!detail::checked_mul(year_delta,12,months)||!detail::checked_add(months,static_cast<std::int64_t>(as_of.month-birth.month),months)) return std::nullopt; Date anniversary=detail::add_months_clamped(birth,months); if(detail::less(as_of,anniversary)) --months; return months;""",
            """if(!detail::valid(birth)||!detail::valid(as_of)) return std::nullopt; return (as_of.year-birth.year)*12+(as_of.month-birth.month);""",
            f"""auto a={fn}(MonthlyAnniversaryBirth{{2020,1,31}},Date{{2020,2,29}}); require(a&&*a==1); auto b={fn}(MonthlyAnniversaryBirth{{2020,1,31}},Date{{2020,2,28}}); require(b&&*b==0);""",
            f"""require(!{fn}(MonthlyAnniversaryBirth{{2020,1,1}},Date{{2019,1,1}})); auto z={fn}(MonthlyAnniversaryBirth{{2020,1,1}},Date{{2020,1,1}}); require(z&&*z==0);""",
            "The return is completed clamped monthly anniversaries, not raw year-month distance. Invalid or reversed dates and unrepresentable month counts are rejected.",
            _DATE_DECL + "\nstruct MonthlyAnniversaryBirth { std::int64_t year; int month; int day; operator Date() const { return Date{year,month,day}; } };",
        )
    if operation == "iso_weeks":
        return _case(
            f"std::optional<std::int64_t> {fn}(Date start, Date finish)",
            """if(!detail::valid(start)||!detail::valid(finish)||detail::less(finish,start)) return std::nullopt; return (detail::serial(finish)-detail::serial(start))/7;""",
            """if(!detail::valid(start)||!detail::valid(finish)) return std::nullopt; return (finish.year-start.year)*52+(finish.month-start.month)*4;""",
            f"""auto a={fn}(Date{{2020,12,28}},Date{{2021,1,11}}); require(a&&*a==2);""",
            f"""auto b={fn}(Date{{2020,2,28}},Date{{2020,3,6}}); require(b&&*b==1); require(!{fn}(Date{{2,1,1}},Date{{1,1,1}})); std::array<Date,3> mondays{{Date{{2020,12,28}},Date{{2021,1,4}},Date{{2021,1,11}}}}; for(std::size_t i=1;i<mondays.size();++i){{auto trace={fn}(mondays[0],mondays[i]);require(trace&&*trace==static_cast<std::int64_t>(i));}}""",
            "The return is exact complete seven-day periods across Gregorian/ISO-year boundaries. Invalid or reversed dates are rejected.",
            _DATE_DECL,
        )
    if operation == "century_birthdays":
        return _case(
            f"std::optional<std::vector<Date>> {fn}(Date birth, Date begin, Date end)",
            """if(!detail::valid(birth)||!detail::valid(begin)||!detail::valid(end)||!detail::less(begin,end)) return std::nullopt; std::vector<Date> out; std::int64_t age=100; while(true){ if(birth.year>std::numeric_limits<std::int64_t>::max()-age) break; Date anniversary=detail::birthday_in_year(birth,birth.year+age,false); if(!detail::less(anniversary,end)) break; if(!detail::less(anniversary,begin)) out.push_back(anniversary); if(age>std::numeric_limits<std::int64_t>::max()-100) break; age+=100;} return out;""",
            """std::vector<Date> out; for(std::int64_t y=begin.year;y<=end.year;++y) if(y%100==birth.year%100) out.push_back(Date{y,birth.month,birth.day}); return out;""",
            f"""auto a={fn}(Date{{1900,6,1}},Date{{1999,1,1}},Date{{2201,1,1}}); require(a&&a->size()==3&&(*a)[0].year==2000&&(*a)[2].year==2200);""",
            f"""auto b={fn}(Date{{2000,2,29}},Date{{2099,1,1}},Date{{2101,1,1}}); require(b&&b->size()==1&&(*b)[0].day==28); require(!{fn}(Date{{1,1,1}},Date{{2,1,1}},Date{{2,1,1}}));""",
            "The vector contains checked 100-year policy anniversaries in the half-open range. An empty or reversed range is rejected.",
            _DATE_DECL,
        )
    return None


def _checked_case(operation: str, fn: str) -> RenderedCase | None:
    if operation == "checked_add":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t value, std::int64_t offset)","std::int64_t out=0; if(!detail::checked_add(value,offset,out)) return std::nullopt; return out;","return value+offset;",f"auto a={fn}(10,-3); require(a&&*a==7);",f"require(!{fn}(std::numeric_limits<std::int64_t>::max(),1)); require(!{fn}(std::numeric_limits<std::int64_t>::min(),-1));","The return is the mathematical sum only when representable.")
    if operation == "compose_duration":
        return _case(f"std::optional<std::int64_t> {fn}(DurationParts parts)","if(parts.hours<0||parts.hours>=24||parts.minutes<0||parts.minutes>=60||parts.seconds<0||parts.seconds>=60) return std::nullopt; std::int64_t v=0; if(!detail::checked_mul(parts.days,24,v)||!detail::checked_add(v,parts.hours,v)||!detail::checked_mul(v,60,v)||!detail::checked_add(v,parts.minutes,v)||!detail::checked_mul(v,60,v)||!detail::checked_add(v,parts.seconds,v)) return std::nullopt; return v;","return parts.days*86400+parts.hours*3600+parts.minutes*60+parts.seconds;",f"auto a={fn}(DurationParts{{1,2,3,4}}); require(a&&*a==93784);",f"require(!{fn}(DurationParts{{0,24,0,0}})); require(!{fn}(DurationParts{{std::numeric_limits<std::int64_t>::max(),0,0,0}}));","The return is checked Horner-composed seconds after field validation.","struct DurationParts { std::int64_t days; int hours; int minutes; int seconds; };")
    if operation == "exact_ratio":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t value, std::uint64_t numerator, std::uint64_t denominator)","if(denominator==0||numerator>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())||denominator>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) return std::nullopt; auto n=static_cast<std::int64_t>(numerator); auto d=static_cast<std::int64_t>(denominator); const auto g=std::gcd(n,d); n/=g; d/=g;const std::uint64_t magnitude=value<0?static_cast<std::uint64_t>(-(value+1))+1U:static_cast<std::uint64_t>(value);const auto gv=std::gcd(magnitude,static_cast<std::uint64_t>(d));if(gv==(std::uint64_t{1}<<63U))value=-1;else value/=static_cast<std::int64_t>(gv);d/=static_cast<std::int64_t>(gv); if(d!=1) return std::nullopt; std::int64_t out=0; if(!detail::checked_mul(value,n,out)) return std::nullopt; return out;","if(denominator==0) return std::nullopt; return value*static_cast<std::int64_t>(numerator)/static_cast<std::int64_t>(denominator);",f"auto a={fn}(12,5,3); require(a&&*a==20); require(!{fn}(1,2,3));",f"auto b={fn}(std::numeric_limits<std::int64_t>::min(),1,1); require(b&&*b==std::numeric_limits<std::int64_t>::min()); require(!{fn}(1,1,0)); require(!{fn}(2,3,4)); require(!{fn}(std::numeric_limits<std::int64_t>::max(),2,1));","The exact reduced rational scale is returned only for an integral representable result.")
    if operation == "saturating_add":
        return _case(f"SaturatedShift {fn}(std::int64_t value, std::int64_t offset)","if(offset>0&&value>std::numeric_limits<std::int64_t>::max()-offset) return {std::numeric_limits<std::int64_t>::max(),1}; if(offset<0&&value<std::numeric_limits<std::int64_t>::min()-offset) return {std::numeric_limits<std::int64_t>::min(),-1}; return {value+offset,0};","const auto sum=value+offset; return {std::clamp(sum,std::numeric_limits<std::int64_t>::min(),std::numeric_limits<std::int64_t>::max()),0};",f"auto a={fn}(5,-2); require(a.value==3&&a.direction==0);",f"auto h={fn}(std::numeric_limits<std::int64_t>::max(),1); require(h.value==std::numeric_limits<std::int64_t>::max()&&h.direction==1); auto l={fn}(std::numeric_limits<std::int64_t>::min(),-1); require(l.direction==-1);","SaturatedShift distinguishes no saturation, lower saturation, and upper saturation.","struct SaturatedShift { std::int64_t value; int direction; };")
    if operation == "bounded_add":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t value, std::int64_t offset, std::int64_t lower, std::int64_t upper)","if(lower>upper) return std::nullopt; std::int64_t out=0; if(!detail::checked_add(value,offset,out)||out<lower||out>upper) return std::nullopt; return out;","if(lower>upper) return std::nullopt; return std::clamp(value+offset,lower,upper);",f"auto a={fn}(5,3,0,10); require(a&&*a==8); require(!{fn}(9,2,0,10));",f"require(!{fn}(0,0,2,1)); require(!{fn}(std::numeric_limits<std::int64_t>::max(),1,0,std::numeric_limits<std::int64_t>::max()));","The shifted result must be representable and inside the validated closed bounds.")
    if operation == "day_product":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t days)","std::int64_t out=0; if(!detail::checked_mul(days,86400,out)) return std::nullopt; return out;","if(detail::abs_i64(days)>std::numeric_limits<std::int64_t>::max()/86400) return std::nullopt; return days*86400;",f"auto a={fn}(-2); require(a&&*a==-172800);",f"require(!{fn}(std::numeric_limits<std::int64_t>::min())); auto z={fn}(0); require(z&&*z==0);","The return is a sign-aware checked day-to-second product without absolute-value overflow.")
    if operation == "join_nanos":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t seconds, std::int32_t nanos)","if(nanos<0||nanos>=1000000000) return std::nullopt; std::int64_t out=0; if(!detail::checked_mul(seconds,1000000000,out)||!detail::checked_add(out,nanos,out)) return std::nullopt; return out;","seconds+=nanos/1000000000; nanos%=1000000000; return seconds*1000000000+nanos;",f"auto a={fn}(2,3); require(a&&*a==2000000003); require(!{fn}(1,-1));",f"require(!{fn}(1,1000000000)); require(!{fn}(std::numeric_limits<std::int64_t>::max(),0));","The return joins already-canonical nanoseconds; normalization is deliberately forbidden.")
    if operation == "euclidean_div":
        return _case(f"std::optional<DivResult> {fn}(std::int64_t dividend, std::int64_t divisor)","if(divisor<=0) return std::nullopt; auto q=dividend/divisor; auto r=dividend%divisor; if(r<0){r+=divisor;--q;} return DivResult{q,r};","if(divisor<=0) return std::nullopt; return DivResult{dividend/divisor,dividend%divisor};",f"auto a={fn}(-7,3); require(a&&a->quotient==-3&&a->remainder==2);",f"auto b={fn}(std::numeric_limits<std::int64_t>::min(),7); require(b&&b->remainder>=0&&b->remainder<7); require(!{fn}(1,0));","DivResult is Euclidean for every positive divisor, including INT64_MIN.","struct DivResult { std::int64_t quotient; std::int64_t remainder; };")
    if operation == "affine_map":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t sample, std::int64_t origin, std::int64_t numerator, std::int64_t denominator)","if(denominator<=0) return std::nullopt; std::int64_t delta=0; if(!detail::checked_sub(sample,origin,delta)) return std::nullopt; auto scaled=detail::rounded_ratio(delta,numerator,denominator); if(!scaled) return std::nullopt; std::int64_t out=0; if(!detail::checked_add(origin,*scaled,out)) return std::nullopt; return out;","if(denominator<=0) return std::nullopt; return origin+(sample-origin)*numerator/denominator;",f"auto a={fn}(14,10,3,2); require(a&&*a==16);",f"auto b={fn}(11,10,1,2); require(b&&*b==10); auto c={fn}(13,10,1,2); require(c&&*c==12); require(!{fn}(0,0,1,0));","The return is a checked nearest-even rational affine mapping around origin. A nonpositive denominator or any intermediate overflow is rejected.")
    if operation == "transactional_sum":
        return _case(f"bool {fn}(std::int64_t start, const std::vector<std::int64_t>& deltas, std::int64_t& output)","std::int64_t work=start; for(auto d:deltas) if(!detail::checked_add(work,d,work)) return false; output=work; return true;","output=start; for(auto d:deltas){output+=d;} return true;",f"std::int64_t out=9; require({fn}(1,{{2,3}},out)&&out==6);",f"std::int64_t out=77; require(!{fn}(std::numeric_limits<std::int64_t>::max(),{{-1,2}},out)&&out==77);","True commits the final prefix sum; false leaves caller-owned output unchanged.")
    if operation == "overflow_frontier":
        return _case(f"std::optional<std::size_t> {fn}(std::int64_t start, const std::vector<std::int64_t>& deltas)","std::int64_t value=start; for(std::size_t i=0;i<deltas.size();++i) if(!detail::checked_add(value,deltas[i],value)) return i; return std::nullopt;","std::int64_t sum=start; for(auto d:deltas) sum+=d; return std::nullopt;",f"auto a={fn}(std::numeric_limits<std::int64_t>::max(),{{1,-1}}); require(a&&*a==0);",f"require(!{fn}(0,{{1,-1}})); auto b={fn}(0,{{1,std::numeric_limits<std::int64_t>::max()}}); require(b&&*b==1);","The optional index is the first unrepresentable prefix; absence means every prefix succeeded.")
    if operation == "interval_shift":
        return _case(f"std::optional<Interval> {fn}(Interval input, std::int64_t offset)","if(input.begin>input.end) return std::nullopt; std::int64_t b=0,e=0; if(!detail::checked_add(input.begin,offset,b)||!detail::checked_add(input.end,offset,e)) return std::nullopt; return Interval{b,e};","if(input.begin>input.end) return std::nullopt; input.begin+=offset; if(!detail::checked_add(input.end,offset,input.end)) input.end=std::numeric_limits<std::int64_t>::max(); return input;",f"auto a={fn}(Interval{{2,5}},3); require(a&&a->begin==5&&a->end==8);",f"require(!{fn}(Interval{{5,2}},0)); require(!{fn}(Interval{{0,std::numeric_limits<std::int64_t>::max()}},1));","Interval endpoints shift atomically after half-open ordering and overflow validation.","struct Interval { std::int64_t begin; std::int64_t end; };")
    if operation == "range_rescale":
        return _case(f"std::optional<Interval> {fn}(Interval input, std::int64_t numerator, std::int64_t denominator)","if(input.begin>input.end||numerator<=0||denominator<=0) return std::nullopt; auto lower=detail::floor_ratio(input.begin,numerator,denominator); auto upper=detail::ceil_ratio(input.end,numerator,denominator); if(!lower||!upper) return std::nullopt; return Interval{*lower,*upper};","if(denominator<=0) return std::nullopt; return Interval{input.begin*numerator/denominator,input.end*numerator/denominator};",f"auto a={fn}(Interval{{-3,4}},2,3); require(a&&a->begin==-2&&a->end==3);",f"require(!{fn}(Interval{{3,2}},1,1)); require(!{fn}(Interval{{0,1}},1,0));","The lower endpoint floors and the upper endpoint ceils a checked positive rational rescale.","struct Interval { std::int64_t begin; std::int64_t end; };")
    if operation == "weighted_centroid":
        return _case(f"std::optional<std::int64_t> {fn}(const std::vector<WeightedStamp>& samples, std::int64_t pivot)","if(samples.empty()) return std::nullopt; std::int64_t weighted=0,total=0; for(auto s:samples){if(s.weight<=0)return std::nullopt;std::int64_t d=0,p=0;if(!detail::checked_add(s.timestamp,-pivot,d)||!detail::checked_mul(d,s.weight,p)||!detail::checked_add(weighted,p,weighted)||!detail::checked_add(total,s.weight,total))return std::nullopt;} auto mean=detail::rounded_ratio(weighted,1,total); if(!mean)return std::nullopt;std::int64_t out=0;if(!detail::checked_add(pivot,*mean,out))return std::nullopt;return out;","std::int64_t sum=0,w=0;for(auto s:samples){sum+=s.timestamp*s.weight;w+=s.weight;}return w?std::optional<std::int64_t>(sum/w):std::nullopt;",f"auto a={fn}({{{{10,1}},{{20,3}}}},10); require(a&&*a==18);",f"require(!{fn}({{{{1,0}}}},0)); require(!{fn}({{}},0)); auto pivoted={fn}({{{{1000000,1}},{{1000010,3}}}},1000000); require(pivoted&&*pivoted==1000008); auto tie={fn}({{{{0,1}},{{3,1}}}},0); require(tie&&*tie==2);","The return is a pivoted checked positive-weight centroid rounded nearest-even. Empty samples, nonpositive weights, or overflow are rejected.","struct WeightedStamp { std::int64_t timestamp; std::int64_t weight; };")
    if operation == "interpolate":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t begin, std::int64_t end, std::uint64_t numerator, std::uint64_t denominator)","if(begin>end||denominator==0||numerator>denominator||denominator>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;std::int64_t delta=0;if(!detail::checked_sub(end,begin,delta))return std::nullopt;auto part=detail::rounded_ratio(delta,static_cast<std::int64_t>(numerator),static_cast<std::int64_t>(denominator));if(!part)return std::nullopt;std::int64_t out=0;if(!detail::checked_add(begin,*part,out))return std::nullopt;return out;","if(denominator==0)return std::nullopt;return begin+(end-begin)*static_cast<std::int64_t>(numerator)/static_cast<std::int64_t>(denominator);",f"auto a={fn}(10,20,1,4); require(a&&*a==12);",f"require(!{fn}(20,10,1,2)); require(!{fn}(0,1,2,1));","The return is a checked nearest-even point at a validated fraction of an ordered interval.")
    if operation == "nth_occurrence":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t first, std::int64_t period, std::uint64_t ordinal)","if(period<=0||ordinal==0||ordinal-1>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;std::int64_t step=0,out=0;if(!detail::checked_mul(period,static_cast<std::int64_t>(ordinal-1),step)||!detail::checked_add(first,step,out))return std::nullopt;return out;","return first+period*static_cast<std::int64_t>(ordinal);",f"auto a={fn}(10,3,1); require(a&&*a==10); auto b={fn}(10,3,4); require(b&&*b==19);",f"require(!{fn}(0,1,0)); require(!{fn}(0,-1,2));","The one-based recurrence uses (ordinal-1) with checked positive-period multiply-add.")
    if operation == "backoff":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t start, std::int64_t base, std::uint32_t attempts, std::int64_t cap)","if(base<0||cap<0)return std::nullopt;std::int64_t delay=base;for(std::uint32_t i=0;i<attempts&&delay<cap;++i){if(delay>cap-delay)delay=cap;else delay*=2;}std::int64_t out=0;if(!detail::checked_add(start,std::min(delay,cap),out))return std::nullopt;return out;","return start+std::min(base<<attempts,cap);",f"auto a={fn}(100,3,2,20); require(a&&*a==112);",f"auto b={fn}(100,8,9,20); require(b&&*b==120); require(!{fn}(0,-1,1,10));","The deadline adds a pre-capped doubling delay without shift overflow.")
    if operation == "arithmetic_sum":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t first, std::int64_t difference, std::uint64_t count)","if(first<0||difference<0||count>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;if(count==0)return 0;std::int64_t n=static_cast<std::int64_t>(count),two_first=0,last_part=0,sum_factor=0;if(!detail::checked_mul(first,2,two_first)||!detail::checked_mul(n-1,difference,last_part)||!detail::checked_add(two_first,last_part,sum_factor))return std::nullopt;if((n&1)==0)n/=2;else sum_factor/=2;std::int64_t out=0;if(!detail::checked_mul(n,sum_factor,out))return std::nullopt;return out;","return static_cast<std::int64_t>(count)*(2*first+(static_cast<std::int64_t>(count)-1)*difference)/2;",f"auto a={fn}(2,3,4); require(a&&*a==26);",f"auto z={fn}(5,2,0); require(z&&*z==0); require(!{fn}(-1,1,2));","The return is the checked nonnegative arithmetic-series sum with a factor cancelled before multiplication.")
    if operation == "dot_product":
        return _case(f"std::optional<std::int64_t> {fn}(const std::vector<std::int64_t>& durations, const std::vector<std::int64_t>& counts)","if(durations.size()!=counts.size())return std::nullopt;std::int64_t sum=0;for(std::size_t i=0;i<durations.size();++i){std::int64_t term=0;if(!detail::checked_mul(durations[i],counts[i],term)||!detail::checked_add(sum,term,sum))return std::nullopt;}return sum;","std::int64_t sum=0;for(std::size_t i=0;i<durations.size();++i)sum+=durations[i]*counts[i];return sum;",f"auto a={fn}({{2,-3}},{{4,5}}); require(a&&*a==-7);",f"require(!{fn}({{1}},{{1,2}})); require(!{fn}({{std::numeric_limits<std::int64_t>::max()}},{{2}}));","The return is a transactional checked signed dot product after exact length validation.")
    if operation == "window_count":
        return _case(f"std::optional<std::uint64_t> {fn}(std::int64_t begin, std::int64_t end, std::uint64_t width)","if(begin>end||width==0)return std::nullopt;const std::uint64_t span=detail::distance(begin,end);return span/width+(span%width!=0U?1U:0U);","if(width==0)return std::nullopt;return static_cast<std::uint64_t>(end-begin)/width;",f"auto a={fn}(-5,6,4); require(a&&*a==3);",f"require(!{fn}(2,1,1)); require(!{fn}(0,1,0)); auto b={fn}(std::numeric_limits<std::int64_t>::min(),std::numeric_limits<std::int64_t>::max(),std::numeric_limits<std::uint64_t>::max()); require(b&&*b==1);","The return is the ceiling number of aligned half-open windows, using unsigned distance to avoid subtraction overflow.")
    return None


def _rollover_case(operation: str, fn: str) -> RenderedCase | None:
    if operation == "unwrap32":
        return _case(f"std::optional<std::vector<std::int64_t>> {fn}(const std::vector<std::uint32_t>& raw, std::int64_t first)","std::vector<std::int64_t> out;std::int64_t prior=first;for(auto x:raw){const std::int64_t base=prior-(prior%4294967296LL);std::array<std::int64_t,3> c{{base+static_cast<std::int64_t>(x)-4294967296LL,base+static_cast<std::int64_t>(x),base+static_cast<std::int64_t>(x)+4294967296LL}};auto best=c[0];auto d=detail::distance(best,prior);bool tie=false;for(int i=1;i<3;++i){auto nd=detail::distance(c[i],prior);if(nd<d){best=c[i];d=nd;tie=false;}else if(nd==d)tie=true;}if(tie)return std::nullopt;out.push_back(best);prior=best;}return out;","std::vector<std::int64_t> out;std::uint32_t prior=0;std::int64_t era=0;for(auto x:raw){if(x<prior)++era;out.push_back(era*4294967296LL+x);prior=x;}return out;",f"auto a={fn}({{0xfffffffeU,1U}},4294967293LL); require(a&&(*a)[1]==4294967297LL);",f"require(!{fn}({{0x80000000U}},0));","The vector contains nearest consecutive 32-bit lifts; exact half-range ambiguity fails.")
    if operation == "unwrap16":
        return _case(f"std::optional<std::vector<std::int64_t>> {fn}(const std::vector<std::uint16_t>& raw, std::int64_t first, std::uint32_t max_step)","if(max_step==0||max_step>=32768)return std::nullopt;std::vector<std::int64_t> out;std::int64_t prior=first;for(auto x:raw){std::optional<std::int64_t> found;const auto era=prior/65536;for(int k=-1;k<=1;++k){auto c=(era+k)*65536+x;if(detail::distance(c,prior)<=max_step){if(found)return std::nullopt;found=c;}}if(!found)return std::nullopt;out.push_back(*found);prior=*found;}return out;","(void)max_step;std::vector<std::int64_t> out;for(auto x:raw)out.push_back(x);return out;",f"auto a={fn}({{65534U,2U}},65530,10); require(a&&(*a)[1]==65538);",f"require(!{fn}({{100U}},0,0)); require(!{fn}({{1000U}},0,10));","Each 16-bit sample has exactly one lift within the nonzero step bound.")
    if operation == "serial_order":
        return _case(f"SerialRelation {fn}(std::uint32_t left, std::uint32_t right)","if(left==right)return SerialRelation::equal;const auto delta=right-left;if(delta==0x80000000U)return SerialRelation::unordered;return delta<0x80000000U?SerialRelation::before:SerialRelation::after;","if(left==right)return SerialRelation::equal;return left<right?SerialRelation::before:SerialRelation::after;",f"require({fn}(0xffffffffU,0U)==SerialRelation::before); require({fn}(7,7)==SerialRelation::equal);",f"require({fn}(0,0x80000000U)==SerialRelation::unordered);","SerialRelation implements RFC1982 modular order and exposes the half-range unordered case.","enum class SerialRelation { before, equal, after, unordered };")
    if operation == "gps_sequence":
        return _case(f"std::optional<std::vector<std::int64_t>> {fn}(const std::vector<std::uint16_t>& weeks, std::int64_t first_absolute)","std::vector<std::int64_t> out;std::int64_t prior=first_absolute;for(auto w:weeks){if(w>=1024)return std::nullopt;auto era=prior/1024;std::int64_t c=era*1024+w;if(c<prior)c+=1024;if(c-prior>512)return std::nullopt;out.push_back(c);prior=c;}return out;","std::vector<std::int64_t> out;for(auto w:weeks)out.push_back((first_absolute/1024)*1024+w);return out;",f"auto a={fn}({{1023U,0U,1U}},1022); require(a&&(*a)[1]==1024);",f"require(!{fn}({{1024U}},0)); require(!{fn}({{600U}},0));","The vector is a nondecreasing ten-bit GPS-week unwrap with at most a 512-week forward step.")
    if operation == "reset_segments":
        return _case(f"std::optional<std::vector<std::size_t>> {fn}(const std::vector<std::int64_t>& timestamps, std::uint64_t tolerance)","std::vector<std::size_t> starts{0};for(std::size_t i=1;i<timestamps.size();++i)if(timestamps[i]<timestamps[i-1]&&detail::distance(timestamps[i],timestamps[i-1])>tolerance)starts.push_back(i);return starts;","auto copy=timestamps;std::sort(copy.begin(),copy.end());return std::vector<std::size_t>{0};",f"auto a={fn}({{10,9,2,3}},2); require(a&&*a==std::vector<std::size_t>({{0,2}}));",f"auto b={fn}({{}},0); require(b&&*b==std::vector<std::size_t>({{0}})); auto jumps={fn}({{5,4,1,2,8}},2); require(jumps&&*jumps==std::vector<std::size_t>({{0,2}})); auto edge={fn}({{10,8}},2); require(edge&&*edge==std::vector<std::size_t>({{0}}));","The vector records input-order segment starts only for backward jumps larger than tolerance.")
    if operation == "two_point_calibration":
        return _case(f"std::optional<Calibration> {fn}(ClockSample first, ClockSample second)","std::int64_t mono=0,wall=0;if(!detail::checked_sub(second.monotonic,first.monotonic,mono)||!detail::checked_sub(second.wall,first.wall,wall)||mono<=0||wall<=0)return std::nullopt;auto g=std::gcd(mono,wall);mono/=g;wall/=g;std::int64_t scaled=0,term=0,intercept=0;if(!detail::checked_mul(first.monotonic,wall,scaled)||scaled%mono!=0||!detail::checked_sub(first.wall,scaled/mono,term))return std::nullopt;intercept=term;return Calibration{wall,mono,intercept};","auto slope=(second.wall-first.wall)/(second.monotonic-first.monotonic);return Calibration{slope,1,first.wall-slope*first.monotonic};",f"auto a={fn}(ClockSample{{2,5}},ClockSample{{6,11}}); require(a&&a->numerator==3&&a->denominator==2&&a->intercept==2);",f"require(!{fn}(ClockSample{{2,5}},ClockSample{{2,6}})); require(!{fn}(ClockSample{{std::numeric_limits<std::int64_t>::min(),0}},ClockSample{{0,1}}));","Calibration stores a reduced positive wall/monotonic slope and exact checked intercept.","struct ClockSample { std::int64_t monotonic; std::int64_t wall; }; struct Calibration { std::int64_t numerator; std::int64_t denominator; std::int64_t intercept; };")
    if operation == "piecewise_offset":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t instant, const std::vector<OffsetStep>& steps)","const OffsetStep* selected=nullptr;for(const auto& s:steps){if(selected&&selected->at>=s.at)return std::nullopt;if(s.at<=instant)selected=&s;}if(!selected)return std::nullopt;std::int64_t out=0;if(!detail::checked_add(instant,selected->offset,out))return std::nullopt;return out;","if(steps.empty())return std::nullopt;auto it=std::min_element(steps.begin(),steps.end(),[&](auto a,auto b){return detail::distance(a.at,instant)<detail::distance(b.at,instant);});return instant+it->offset;",f"auto a={fn}(15,{{{{0,2}},{{10,3}},{{20,4}}}}); require(a&&*a==18);",f"require(!{fn}(-1,{{{{0,1}}}})); require(!{fn}(2,{{{{1,1}},{{1,2}}}}));","The result applies the last strictly ordered offset transition not after the instant. An instant before the first transition is rejected.","struct OffsetStep { std::int64_t at; std::int64_t offset; };")
    if operation == "median_offset":
        return _case(f"std::optional<std::int64_t> {fn}(const std::vector<ClockSample>& samples)","if(samples.empty())return std::nullopt;std::vector<std::int64_t> d;for(auto s:samples){std::int64_t x=0;if(!detail::checked_sub(s.wall,s.monotonic,x))return std::nullopt;d.push_back(x);}const auto k=(d.size()-1)/2;std::nth_element(d.begin(),d.begin()+static_cast<std::ptrdiff_t>(k),d.end());return d[k];","if(samples.empty())return std::nullopt;std::int64_t sum=0;for(auto s:samples)sum+=s.wall-s.monotonic;return sum/static_cast<std::int64_t>(samples.size());",f"auto a={fn}({{{{1,11}},{{2,102}},{{3,23}},{{4,34}}}}); require(a&&*a==20);",f"require(!{fn}({{}})); require(!{fn}({{{{std::numeric_limits<std::int64_t>::min(),std::numeric_limits<std::int64_t>::max()}}}}));","The return is the checked deterministic lower median of wall-minus-monotonic offsets.","struct ClockSample { std::int64_t monotonic; std::int64_t wall; };")
    if operation == "drift_envelope":
        return _case(f"bool {fn}(const std::vector<ClockSample>& samples, std::uint64_t max_ppm)","if(samples.size()<2||max_ppm>1000000U)return false;for(std::size_t i=1;i<samples.size();++i){std::int64_t dm=0,dw=0;if(!detail::checked_sub(samples[i].monotonic,samples[i-1].monotonic,dm)||!detail::checked_sub(samples[i].wall,samples[i-1].wall,dw)||dm<=0)return false;const auto error=detail::distance(dm,dw);const auto udm=static_cast<std::uint64_t>(dm);const auto allowed=(udm/1000000U)*max_ppm+((udm%1000000U)*max_ppm)/1000000U;if(error>allowed)return false;}return true;","(void)max_ppm;return std::is_sorted(samples.begin(),samples.end(),[](auto a,auto b){return a.monotonic<b.monotonic;});",f"require({fn}({{{{0,0}},{{1000000,1000001}}}},2));",f"require(!{fn}({{{{0,0}},{{1000000,1000010}}}},2)); require(!{fn}({{{{1,1}}}},2));","True means every positive monotonic interval stays inside the integer ppm drift envelope. Fewer than two samples or a bound above 1000000 ppm returns false.","struct ClockSample { std::int64_t monotonic; std::int64_t wall; };")
    if operation == "packet_order":
        return _case(f"std::optional<std::vector<std::size_t>> {fn}(const std::vector<PacketStamp>& packets)","std::vector<std::int64_t> lo,hi;for(auto p:packets){if(p.uncertainty<0)return std::nullopt;std::int64_t a=0,b=0;if(!detail::checked_sub(p.timestamp,p.uncertainty,a)||!detail::checked_add(p.timestamp,p.uncertainty,b))return std::nullopt;lo.push_back(a);hi.push_back(b);}const auto n=packets.size();std::vector<std::vector<std::size_t>> edges(n);std::vector<std::size_t> degree(n);for(std::size_t i=0;i<n;++i)for(std::size_t j=i+1;j<n;++j){std::size_t from=i,to=j;if(hi[j]<lo[i]){from=j;to=i;}edges[from].push_back(to);++degree[to];}std::vector<std::size_t> order;for(std::size_t step=0;step<n;++step){std::size_t pick=n;for(std::size_t i=0;i<n;++i)if(degree[i]==0&&std::find(order.begin(),order.end(),i)==order.end()){pick=i;break;}if(pick==n)return std::nullopt;order.push_back(pick);for(auto to:edges[pick])--degree[to];}return order;","std::vector<std::size_t> order(packets.size());std::iota(order.begin(),order.end(),0);std::stable_sort(order.begin(),order.end(),[&](auto a,auto b){return packets[a].timestamp<packets[b].timestamp;});return order;",f"auto a={fn}({{{{10,0}},{{5,1}},{{7,4}}}}); require(a&&*a==std::vector<std::size_t>({{1,0,2}}));",f"require(!{fn}({{{{0,-1}}}})); require(!{fn}({{{{std::numeric_limits<std::int64_t>::max(),1}}}})); require(!{fn}({{{{5,1}},{{3,1}},{{1,1}}}})); auto b={fn}({{{{5,3}},{{4,3}}}}); require(b&&*b==std::vector<std::size_t>({{0,1}}));","The vector topologically orders provably disjoint uncertainty intervals, preserves overlap order, and rejects contradictory constraints.","struct PacketStamp { std::int64_t timestamp; std::int64_t uncertainty; };")
    if operation == "watermark":
        return _case(f"std::optional<std::int64_t> {fn}(const std::vector<SourceTime>& sources, std::int64_t allowed_lateness, std::int64_t previous)","if(sources.empty()||allowed_lateness<0)return std::nullopt;bool any=false;std::int64_t candidate=std::numeric_limits<std::int64_t>::max();for(auto s:sources){if(!s.active)continue;any=true;if(!s.initialized)return std::nullopt;std::int64_t v=0;if(!detail::checked_sub(s.latest,allowed_lateness,v))return std::nullopt;candidate=std::min(candidate,v);}if(!any)return std::nullopt;return std::max(previous,candidate);","if(sources.empty())return std::nullopt;auto m=std::max_element(sources.begin(),sources.end(),[](auto a,auto b){return a.latest<b.latest;});return m->latest-allowed_lateness;",f"auto a={fn}({{{{1,true,true,20}},{{2,true,true,30}},{{3,false,false,0}}}},5,10); require(a&&*a==15);",f"require(!{fn}({{{{1,true,false,20}}}},5,10)); require(!{fn}({{{{1,false,false,0}}}},0,0)); auto b={fn}({{{{1,true,true,2}}}},5,10); require(b&&*b==10);","The watermark uses every active initialized source; any missing active source blocks advancement. Negative lateness and empty or all-inactive source lists are rejected.","struct SourceTime { std::uint32_t source; bool active; bool initialized; std::int64_t latest; };")
    if operation == "tolerance_dedup":
        return _case(f"std::optional<std::vector<std::int64_t>> {fn}(const std::vector<std::int64_t>& sorted, std::uint64_t tolerance)","if(!std::is_sorted(sorted.begin(),sorted.end()))return std::nullopt;std::vector<std::int64_t> out;if(sorted.empty())return out;out.push_back(sorted.front());for(std::size_t i=1;i<sorted.size();++i)if(detail::distance(sorted[i-1],sorted[i])>tolerance)out.push_back(sorted[i]);return out;","if(!std::is_sorted(sorted.begin(),sorted.end()))return std::nullopt;std::vector<std::int64_t> out;for(auto x:sorted)if(out.empty()||detail::distance(out.back(),x)>tolerance)out.push_back(x);return out;",f"auto a={fn}({{1,2,4,10}},2); require(a&&*a==std::vector<std::int64_t>({{1,10}}));",f"require(!{fn}({{2,1}},1)); auto b={fn}({{1,4,8}},2); require(b&&*b==std::vector<std::int64_t>({{1,4,8}})); auto chain={fn}({{0,1,2,10}},1); require(chain&&*chain==std::vector<std::int64_t>({{0,10}}));","The vector retains the first timestamp of each adjacent-input tolerance-connected run. Unsorted input is rejected.")
    if operation in {"delta_delta", "delta2"}:
        return _case(f"std::optional<std::vector<std::int64_t>> {fn}(std::int64_t first, std::int64_t first_delta, const std::vector<std::int64_t>& delta2)","std::vector<std::int64_t> out{first};std::int64_t timestamp=first,delta=first_delta;for(auto change:delta2){if(!detail::checked_add(delta,change,delta)||!detail::checked_add(timestamp,delta,timestamp))return std::nullopt;out.push_back(timestamp);}return out;","std::vector<std::int64_t> out{first};for(auto change:delta2){first_delta=change;first+=first_delta;out.push_back(first);}return out;",f"auto a={fn}(10,3,{{2,2}}); require(a&&*a==std::vector<std::int64_t>({{10,15,22}}));",f"require(!{fn}(std::numeric_limits<std::int64_t>::max(),1,{{0}})); auto b={fn}(0,1,{{1,1,1}}); require(b&&*b==std::vector<std::int64_t>({{0,2,5,9}}));","The vector transactionally reconstructs timestamps through checked delta and timestamp accumulators.")
    if operation == "gap_runs":
        return _case(f"std::optional<std::vector<GapRun>> {fn}(const std::vector<std::int64_t>& timestamps, std::uint64_t threshold)","if(!std::is_sorted(timestamps.begin(),timestamps.end()))return std::nullopt;std::vector<GapRun> out;for(std::size_t i=1;i<timestamps.size();++i){bool large=detail::distance(timestamps[i-1],timestamps[i])>threshold;if(out.empty()||out.back().large!=large)out.push_back({i-1,1,large});else ++out.back().count;}return out;","std::vector<GapRun> out;for(std::size_t i=1;i<timestamps.size();++i)out.push_back({i-1,1,timestamps[i]-timestamps[i-1]>static_cast<std::int64_t>(threshold)});return out;",f"auto a={fn}({{0,1,2,10,20}},3); require(a&&a->size()==2&&(*a)[0].count==2&&(*a)[1].count==2);",f"require(!{fn}({{2,1}},0));","GapRun run-length encodes adjacent small/large gap classes without signed subtraction overflow.","struct GapRun { std::size_t first_gap; std::size_t count; bool large; };")
    if operation == "bucket_index":
        return _case(f"std::optional<std::int64_t> {fn}(std::int64_t instant, std::int64_t anchor, std::uint64_t width)","if(width==0||width>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;std::int64_t delta=0;if(!detail::checked_sub(instant,anchor,delta))return std::nullopt;auto d=static_cast<std::int64_t>(width);auto q=delta/d;auto r=delta%d;if(r<0)--q;return q;","if(width==0)return std::nullopt;return (instant-anchor)/static_cast<std::int64_t>(width);",f"auto a={fn}(-1,0,10); require(a&&*a==-1);",f"require(!{fn}(0,0,0)); require(!{fn}(std::numeric_limits<std::int64_t>::max(),std::numeric_limits<std::int64_t>::min(),1));","The return is the Euclidean anchored bucket index with checked difference.")
    if operation == "slew_distribution":
        return _case(f"std::optional<std::vector<std::int64_t>> {fn}(std::int64_t correction, std::uint64_t steps)","if(steps==0||steps>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;std::vector<std::int64_t> out;auto n=static_cast<std::int64_t>(steps),q=correction/n,r=correction%n;for(std::int64_t i=0;i<n;++i){auto v=q;if(r>0&&i<r)++v;if(r<0&&i<-r)--v;out.push_back(v);}return out;","if(steps==0)return std::nullopt;std::vector<std::int64_t> out(steps,0);out.back()=correction;return out;",f"auto a={fn}(8,3); require(a&&*a==std::vector<std::int64_t>({{3,3,2}}));",f"auto b={fn}(-5,2); require(b&&*b==std::vector<std::int64_t>({{-3,-2}})); require(!{fn}(1,0));","The vector exactly sums to correction while per-step and prefix error stay balanced.")
    if operation == "quantize":
        return _case(f"std::optional<Quantized> {fn}(std::int64_t value, std::uint64_t quantum)","if(quantum==0||quantum>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;auto q=static_cast<std::int64_t>(quantum),base=value/q,rem=value%q;auto absr=detail::distance(rem,0);if(absr*2U>quantum||(absr*2U==quantum&&(base&1LL)))base+=rem<0?-1:1;std::int64_t rounded=0;if(!detail::checked_mul(base,q,rounded))return std::nullopt;std::int64_t error=0;if(!detail::checked_sub(rounded,value,error))return std::nullopt;return Quantized{rounded,error};","if(quantum==0)return std::nullopt;auto q=static_cast<std::int64_t>(quantum);auto rounded=((value+q/2)/q)*q;return Quantized{rounded,rounded-value};",f"auto a={fn}(15,10); require(a&&a->value==20); auto b={fn}(25,10); require(b&&b->value==20);",f"auto c={fn}(-15,10); require(c&&c->value==-20); require(!{fn}(1,0));","Quantized reports nearest-even bucket reconstruction and its checked signed error.","struct Quantized { std::int64_t value; std::int64_t error; };")
    if operation == "common_timebase":
        return _case(f"std::optional<CommonTick> {fn}(std::uint64_t first_hz, std::uint64_t second_hz)","if(first_hz==0||second_hz==0)return std::nullopt;auto g=std::gcd(first_hz,second_hz);auto reduced=first_hz/g;if(reduced>std::numeric_limits<std::uint64_t>::max()/second_hz)return std::nullopt;auto common=reduced*second_hz;return CommonTick{common,common/first_hz,common/second_hz};","if(first_hz==0||second_hz==0)return std::nullopt;auto common=first_hz*second_hz;return CommonTick{common,second_hz,first_hz};",f"auto a={fn}(6,8); require(a&&a->common_hz==24&&a->first_multiplier==4&&a->second_multiplier==3);",f"require(!{fn}(0,1)); require(!{fn}(std::numeric_limits<std::uint64_t>::max(),2));","CommonTick contains checked LCM frequency and exact per-source multipliers.","struct CommonTick { std::uint64_t common_hz; std::uint64_t first_multiplier; std::uint64_t second_multiplier; };")
    if operation == "tagged_era":
        return _case(f"std::optional<std::int64_t> {fn}(EraStamp stamp)","std::int64_t offset=0,alignment=1;switch(stamp.era){case Era::unix_time:break;case Era::gps_time:offset=-315964800;break;case Era::filetime_seconds:offset=-11644473600LL;alignment=2;break;}if(stamp.value%alignment!=0)return std::nullopt;std::int64_t out=0;if(!detail::checked_add(stamp.value,offset,out))return std::nullopt;return out;","return stamp.value;",f"auto a={fn}(EraStamp{{Era::gps_time,315964800}}); require(a&&*a==0);",f"require(!{fn}(EraStamp{{Era::filetime_seconds,1}})); auto b={fn}(EraStamp{{Era::unix_time,-1}}); require(b&&*b==-1);","The return applies tag-specific checked epoch offsets and alignment rules.","enum class Era { unix_time, gps_time, filetime_seconds }; struct EraStamp { Era era; std::int64_t value; };")
    if operation == "shard_key":
        return _case(f"std::optional<ShardKey> {fn}(std::int64_t instant, std::int64_t anchor, std::uint64_t width, std::uint32_t shard_count)","if(width==0||shard_count==0||width>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))return std::nullopt;std::int64_t delta=0;if(!detail::checked_sub(instant,anchor,delta))return std::nullopt;auto w=static_cast<std::int64_t>(width),bucket=delta/w,rem=delta%w;if(rem<0)--bucket;auto shard=bucket%shard_count;if(shard<0)shard+=shard_count;std::int64_t scaled=0,origin=0;if(!detail::checked_mul(bucket,w,scaled)||!detail::checked_add(anchor,scaled,origin))return std::nullopt;return ShardKey{bucket,static_cast<std::uint32_t>(shard),origin};","if(width==0||shard_count==0)return std::nullopt;auto bucket=(instant-anchor)/static_cast<std::int64_t>(width);return ShardKey{bucket,static_cast<std::uint32_t>(bucket%shard_count),anchor+bucket*static_cast<std::int64_t>(width)};",f"auto a={fn}(-1,0,10,4); require(a&&a->bucket==-1&&a->shard==3&&a->origin==-10);",f"require(!{fn}(0,0,0,1)); require(!{fn}(0,0,1,0)); require(!{fn}(0,std::numeric_limits<std::int64_t>::min(),1,1));","ShardKey combines Euclidean bucket, nonnegative shard, and checked bucket origin. Zero width, zero shard count, or overflowing arithmetic is rejected.","struct ShardKey { std::int64_t bucket; std::uint32_t shard; std::int64_t origin; };")
    return None


def render_case(operation: str, function_name: str) -> RenderedCase:
    """Return the explicit renderer for one curriculum operation."""

    rendered = (
        _epoch_case(operation, function_name)
        or _age_case(operation, function_name)
        or _checked_case(operation, function_name)
        or _rollover_case(operation, function_name)
    )
    if rendered is None:
        raise KeyError(f"unimplemented_task_operation:{operation}")
    return rendered
