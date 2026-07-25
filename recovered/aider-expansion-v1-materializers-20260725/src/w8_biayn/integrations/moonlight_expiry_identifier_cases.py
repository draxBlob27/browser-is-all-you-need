"""Case inventory for the 90-root date-bearing identifier expansion family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParserProfile:
    key: str
    label: str
    input_fields: str
    grammar: str
    mechanism: str


@dataclass(frozen=True)
class PolicyProfile:
    key: str
    label: str
    result_shape: str
    rule: str
    negative: str


PARSERS = (
    ParserProfile(
        "month_token",
        "fixed-width year-month token",
        "std::string token",
        "exact `YYYY-MM`; expiry is the final day of that Gregorian month",
        "length-first decimal field scanner followed by month-end lookup",
    ),
    ParserProfile(
        "checked_batch",
        "issuer-scoped checked batch stamp",
        "std::string issuer; std::string stamp",
        "nonempty issuer plus exact `YYYYMMDD-C`, where C is the digit-sum modulo ten",
        "single-pass digit/checksum validation before constructing a civil date",
    ),
    ParserProfile(
        "ordinal_serial",
        "ordinal-day serial",
        "std::string serial; int minimum_year",
        "exact `YYYY-DDD`; year must meet minimum_year and DDD must exist in that year",
        "bounded ordinal conversion with leap-aware month subtraction",
    ),
    ParserProfile(
        "week_slot",
        "registry week-slot credential",
        "std::string credential; int maximum_week",
        "exact `YYYYWwwD`; W01D1 is January 1 and the bounded seven-day blocks may not leave the year",
        "week-block offset validation followed by ordinal-to-civil conversion",
    ),
    ParserProfile(
        "fiscal_quarter",
        "fiscal-quarter licence mark",
        "std::string mark; int fiscal_start_month",
        "exact `FYyyyy-Qq`; fiscal_start_month is 1..12 and q is 1..4",
        "fiscal-month rotation and quarter-end clamping across a year boundary",
    ),
    ParserProfile(
        "explicit_century",
        "explicit-century short-year tag",
        "std::string tag; int century_base",
        "exact `MM/YY`; century_base must be a multiple of 100 and supplies the century without a pivot",
        "strict short-field scanner with caller-owned century expansion",
    ),
    ParserProfile(
        "base36_offset",
        "base-36 epoch-offset identifier",
        "std::string code; CivilDate epoch",
        "one to four uppercase base-36 digits encoding 0..3660 days from a valid epoch",
        "overflow-checked positional decoding followed by bounded civil-day addition",
    ),
    ParserProfile(
        "packed_bits",
        "packed civil-date service tag",
        "std::uint32_t packed; unsigned check_byte",
        "year occupies bits 9..22, month bits 5..8, day bits 0..4; check_byte is the XOR of four packed bytes",
        "bit-field extraction plus bytewise integrity check before calendar validation",
    ),
    ParserProfile(
        "season_mark",
        "hemisphere-aware season mark",
        "std::string mark; bool southern_shift",
        "exact `Sx-YYYY`, x=1..4; each season is a quarter and southern_shift rotates it by six months",
        "season-index rotation with end-of-quarter derivation",
    ),
    ParserProfile(
        "epoch_minutes",
        "offset-adjusted epoch-minute ticket",
        "std::int64_t minute; int utc_offset_minutes",
        "signed local minutes from the 2000-01-01 epoch with an explicit offset in [-840,840]; the civil minute is minute plus utc_offset_minutes, floor-divided into a supported day",
        "floor-division normalization of signed local minutes before civil conversion",
    ),
)


POLICIES = (
    PolicyProfile(
        "warning_state",
        "warning-band classification",
        "ExpiryState",
        "expired after the encoded end; warning on the final 30 calendar dates from expiry minus 29 days through expiry; otherwise active",
        "treat equality at expiry as expired",
    ),
    PolicyProfile(
        "grace_cutoff",
        "bounded grace cutoff",
        "std::optional<CivilDate>",
        "add any nonnegative grace-day count and return the cutoff only when it remains in the supported civil range and the supplied reference date is not later",
        "subtract the grace interval",
    ),
    PolicyProfile(
        "business_grace",
        "weekday-only grace window",
        "BusinessWindow",
        "advance by any nonnegative count of Monday-Friday grace days, rejecting a result beyond the supported civil range, and report whether the supplied date remains in the resulting closed window",
        "count weekend days as business days",
    ),
    PolicyProfile(
        "shelf_months",
        "month-clamped shelf extension",
        "ShelfDecision",
        "treat the parsed date as packing date, add any positive shelf-month count with day clamping, reject a result beyond the supported civil range, and classify against the injected date",
        "add shelf days instead of shelf months",
    ),
    PolicyProfile(
        "revocation_precedence",
        "revocation-first adjudication",
        "ExpiryState",
        "an effective supplied revocation date takes precedence over ordinary expiry; malformed revocation is invalid",
        "ignore revocation on its effective day",
    ),
    PolicyProfile(
        "renewal_notice",
        "renewal notice plan",
        "RenewalPlan",
        "open any nonnegative notice_days before expiry when the derived date remains supported, close at expiry, and classify the supplied date as early, open, or closed",
        "open the notice interval after expiry",
    ),
    PolicyProfile(
        "exposure_score",
        "remaining-day exposure score",
        "ExposureScore",
        "multiply nonnegative inclusive remaining days by any positive units value with checked integer range; expired items score zero",
        "add units to remaining days instead of multiplying",
    ),
    PolicyProfile(
        "admission_window",
        "credential admission intersection",
        "AdmissionDecision",
        "require a valid caller window, a reference date in that closed window, and an identifier not expired before admission",
        "exclude the opening boundary",
    ),
    PolicyProfile(
        "remaining_days",
        "signed remaining-day report",
        "std::optional<int>",
        "return signed expiry-minus-reference days and add one only when the caller requests inclusive counting",
        "drop the inclusive endpoint day",
    ),
)


_DOMAINS = (
    ("dated-ampoule-lot", "Ampoule lot release"),
    ("dated-aquifer-sample", "Aquifer sample custody"),
    ("dated-drone-airworthiness", "Drone airworthiness tag"),
    ("dated-harbor-seal", "Harbor cargo seal"),
    ("dated-orbital-calibration", "Orbital calibration label"),
    ("dated-rail-flare", "Rail emergency flare"),
    ("dated-reef-transponder", "Reef transponder service"),
    ("dated-snowpack-probe", "Snowpack probe certificate"),
    ("dated-turbine-coupon", "Turbine inspection coupon"),
    ("dated-wetland-permit", "Wetland access permit"),
    ("dated-bioreactor-cartridge", "Bioreactor cartridge grace"),
    ("dated-cave-beacon", "Cave beacon grace"),
    ("dated-dental-cassette", "Dental cassette grace"),
    ("dated-evacuation-cache", "Evacuation cache grace"),
    ("dated-fiber-splice", "Fiber splice grace"),
    ("dated-glacier-marker", "Glacier marker grace"),
    ("dated-hydrophone-pack", "Hydrophone battery grace"),
    ("dated-irrigation-valve", "Irrigation valve grace"),
    ("dated-kiln-sensor", "Kiln sensor grace"),
    ("dated-lidar-target", "Lidar target grace"),
    ("dated-mine-respirator", "Mine respirator weekday window"),
    ("dated-nursery-graft", "Nursery graft weekday window"),
    ("dated-ocean-buoy", "Ocean buoy weekday window"),
    ("dated-pipeline-pig", "Pipeline gauge weekday window"),
    ("dated-quarry-charge", "Quarry charge weekday window"),
    ("dated-radar-calibrator", "Radar calibrator weekday window"),
    ("dated-solar-inverter", "Solar inverter weekday window"),
    ("dated-tunnel-sensor", "Tunnel sensor weekday window"),
    ("dated-vineyard-trap", "Vineyard trap weekday window"),
    ("dated-water-gauge", "Water gauge weekday window"),
    ("dated-algae-culture", "Algae culture shelf interval"),
    ("dated-battery-electrolyte", "Battery electrolyte shelf interval"),
    ("dated-ceramic-slurry", "Ceramic slurry shelf interval"),
    ("dated-dive-scrubber", "Dive scrubber shelf interval"),
    ("dated-enzyme-panel", "Enzyme panel shelf interval"),
    ("dated-foundry-binder", "Foundry binder shelf interval"),
    ("dated-geology-resin", "Geology resin shelf interval"),
    ("dated-hatchery-feed", "Hatchery feed shelf interval"),
    ("dated-ink-catalyst", "Ink catalyst shelf interval"),
    ("dated-joinery-adhesive", "Joinery adhesive shelf interval"),
    ("dated-aviary-clearance", "Aviary clearance revocation"),
    ("dated-bridge-key", "Bridge access-key revocation"),
    ("dated-canopy-pass", "Canopy pass revocation"),
    ("dated-dam-badge", "Dam badge revocation"),
    ("dated-estuary-license", "Estuary licence revocation"),
    ("dated-forestry-warrant", "Forestry warrant revocation"),
    ("dated-geothermal-pass", "Geothermal pass revocation"),
    ("dated-hangar-credential", "Hangar credential revocation"),
    ("dated-isotope-clearance", "Isotope clearance revocation"),
    ("dated-jetty-key", "Jetty key revocation"),
    ("dated-arboretum-membership", "Arboretum renewal notice"),
    ("dated-boathouse-lease", "Boathouse renewal notice"),
    ("dated-canal-franchise", "Canal renewal notice"),
    ("dated-depot-concession", "Depot renewal notice"),
    ("dated-exhibit-right", "Exhibit renewal notice"),
    ("dated-farm-tenancy", "Farm renewal notice"),
    ("dated-grazing-allotment", "Grazing renewal notice"),
    ("dated-hostel-charter", "Hostel renewal notice"),
    ("dated-island-mooring", "Island renewal notice"),
    ("dated-journal-subscription", "Journal renewal notice"),
    ("dated-avionics-spares", "Avionics exposure score"),
    ("dated-blood-bank-unit", "Blood-bank exposure score"),
    ("dated-cooling-cell", "Cooling-cell exposure score"),
    ("dated-desalination-membrane", "Desalination exposure score"),
    ("dated-emergency-ration", "Emergency-ration exposure score"),
    ("dated-fuel-additive", "Fuel-additive exposure score"),
    ("dated-greenhouse-nutrient", "Greenhouse exposure score"),
    ("dated-hydraulic-seal", "Hydraulic-seal exposure score"),
    ("dated-insulation-roll", "Insulation-roll exposure score"),
    ("dated-junction-fuse", "Junction-fuse exposure score"),
    ("dated-antenna-visitor", "Antenna-site admission"),
    ("dated-biosphere-contractor", "Biosphere admission"),
    ("dated-courier-cordon", "Courier-cordon admission"),
    ("dated-drydock-observer", "Drydock admission"),
    ("dated-embassy-vendor", "Embassy-vendor admission"),
    ("dated-floodgate-inspector", "Floodgate admission"),
    ("dated-grain-terminal", "Grain-terminal admission"),
    ("dated-heliport-escort", "Heliport admission"),
    ("dated-ice-lab-guest", "Ice-lab admission"),
    ("dated-jet-propulsion-guest", "Jet-propulsion admission"),
    ("dated-archive-film", "Archive-film remaining life"),
    ("dated-borehole-core", "Borehole-core remaining life"),
    ("dated-census-reel", "Census-reel remaining life"),
    ("dated-dendrology-slide", "Dendrology-slide remaining life"),
    ("dated-ecology-filter", "Ecology-filter remaining life"),
    ("dated-fossil-cast", "Fossil-cast remaining life"),
    ("dated-genomics-chip", "Genomics-chip remaining life"),
    ("dated-herbarium-sheet", "Herbarium-sheet remaining life"),
    ("dated-ice-core-vial", "Ice-core-vial remaining life"),
    ("dated-jellyfish-sensor", "Jellyfish-sensor remaining life"),
)


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    parser_index: int
    policy_index: int

    @property
    def parser(self) -> ParserProfile:
        return PARSERS[self.parser_index]

    @property
    def policy(self) -> PolicyProfile:
        return POLICIES[self.policy_index]


CASES = tuple(
    Case(task_id, title, index % len(PARSERS), index // len(PARSERS))
    for index, (task_id, title) in enumerate(_DOMAINS)
)

assert len(CASES) == 90
assert len({case.task_id for case in CASES}) == 90
assert len({(case.parser_index, case.policy_index) for case in CASES}) == 90
