"""Case inventory for the coordinate and cross-field expansion family.

The inventory is deliberately data-only.  The owning materializer derives a
unique executable contract from each domain together with a unique ordered
triple of independently witnessable cross-field predicates.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class Domain:
    task_id: str
    title: str
    fields: tuple[str, str, str, str, str, str]
    capability: str


@dataclass(frozen=True)
class Predicate:
    """One published, executable, domain-role-aware rejection rule."""

    kind: str
    error: str
    description: str


COORDINATE_DOMAINS = (
    ("constraint-crane-yard-move", "Crane yard move", ("source_lane", "target_lane", "declared_span", "blocked_lane", "lift_budget", "route_check")),
    ("constraint-greenhouse-transfer", "Greenhouse transfer", ("source_bed", "target_bed", "cultivar_zone", "occupied_bed", "tray_count", "transfer_check")),
    ("constraint-robot-warehouse-step", "Robot warehouse step", ("start_cell", "finish_cell", "step_count", "reserved_cell", "energy_units", "path_check")),
    ("constraint-canoe-portage-route", "Canoe portage route", ("launch_mark", "landing_mark", "leg_count", "closed_mark", "carry_limit", "route_check")),
    ("constraint-orchard-sprayer-pass", "Orchard sprayer pass", ("first_row", "last_row", "nozzle_count", "no_spray_row", "fluid_units", "wind_check")),
    ("constraint-factory-arm-command", "Factory arm command", ("start_axis", "target_axis", "motion_count", "collision_axis", "torque_limit", "mode_check")),
    ("constraint-solar-array-inspection", "Solar array inspection", ("first_panel", "last_panel", "visit_count", "isolated_panel", "charge_units", "sequence_check")),
    ("constraint-classroom-desk-layout", "Classroom desk layout", ("entry_column", "exit_column", "desk_count", "blocked_column", "aisle_width", "access_check")),
    ("constraint-emergency-supply-drop", "Emergency supply drop", ("origin_cell", "drop_cell", "package_count", "excluded_cell", "weight_limit", "manifest_check")),
    ("constraint-rail-switch-plan", "Rail switch plan", ("entry_track", "exit_track", "switch_count", "occupied_track", "axle_limit", "route_check")),
    ("constraint-drone-corridor-hop", "Drone corridor hop", ("launch_node", "recovery_node", "hop_count", "restricted_node", "battery_limit", "flight_check")),
    ("constraint-elevator-car-transfer", "Elevator car transfer", ("source_floor", "target_floor", "stop_count", "locked_floor", "load_limit", "dispatch_check")),
    ("constraint-rover-slope-traverse", "Rover slope traverse", ("start_marker", "goal_marker", "segment_count", "hazard_marker", "traction_limit", "survey_check")),
    ("constraint-cargo-conveyor-switch", "Cargo conveyor switch", ("input_belt", "output_belt", "diverter_count", "jammed_belt", "crate_limit", "routing_check")),
    ("constraint-camera-pan-tilt", "Camera pan and tilt", ("start_angle", "target_angle", "keyframe_count", "blind_angle", "speed_limit", "motion_check")),
    ("constraint-forklift-pallet-shift", "Forklift pallet shift", ("source_slot", "target_slot", "turn_count", "blocked_slot", "mass_limit", "fork_check")),
    ("constraint-rescue-ladder-placement", "Rescue ladder placement", ("base_mark", "top_mark", "rung_count", "unsafe_mark", "reach_limit", "anchor_check")),
    ("constraint-telescope-scan-strip", "Telescope scan strip", ("first_sector", "last_sector", "exposure_count", "masked_sector", "time_limit", "scan_check")),
    ("constraint-irrigation-gate-route", "Irrigation gate route", ("inlet_gate", "outlet_gate", "gate_count", "closed_gate", "flow_limit", "channel_check")),
    ("constraint-mining-cart-junction", "Mining cart junction", ("entry_tunnel", "exit_tunnel", "junction_count", "sealed_tunnel", "ore_limit", "signal_check")),
    ("constraint-harbor-buoy-course", "Harbor buoy course", ("first_buoy", "last_buoy", "turn_count", "closed_buoy", "draft_limit", "course_check")),
    ("constraint-freezer-aisle-pick", "Freezer aisle pick", ("start_aisle", "finish_aisle", "pick_count", "closed_aisle", "cold_limit", "batch_check")),
    ("constraint-stadium-vendor-route", "Stadium vendor route", ("entry_section", "exit_section", "visit_count", "closed_section", "stock_limit", "route_check")),
    ("constraint-pipeline-inspection-crawl", "Pipeline inspection crawl", ("entry_joint", "exit_joint", "segment_count", "sealed_joint", "oxygen_limit", "crawl_check")),
    ("constraint-wind-turbine-service-hop", "Wind turbine service hop", ("base_turbine", "target_turbine", "hop_count", "offline_turbine", "crew_limit", "service_check")),
)

PAIRED_DOMAINS = (
    ("constraint-airfield-gate-swap", "Airfield gate swap", ("first_gate", "second_gate", "aircraft_count", "class_limit", "turnaround_slot", "assignment_check")),
    ("constraint-theater-seat-relocation", "Theater seat relocation", ("source_seat", "target_seat", "party_count", "row_limit", "companion_count", "booking_check")),
    ("constraint-lab-plate-transfer", "Lab plate transfer", ("source_well", "target_well", "sample_count", "volume_limit", "batch_number", "transfer_check")),
    ("constraint-marina-berth-assignment", "Marina berth assignment", ("vessel_length", "berth_length", "vessel_count", "draft_limit", "tide_slot", "assignment_check")),
    ("constraint-volunteer-shift-swap", "Volunteer shift swap", ("first_shift", "second_shift", "worker_count", "role_limit", "coverage_count", "swap_check")),
    ("constraint-aquarium-fish-transfer", "Aquarium fish transfer", ("source_tank", "target_tank", "fish_count", "capacity_limit", "species_code", "transfer_check")),
    ("constraint-delivery-locker-route", "Delivery locker route", ("first_locker", "last_locker", "parcel_count", "temperature_limit", "visit_count", "route_check")),
    ("constraint-hiking-checkpoint-route", "Hiking checkpoint route", ("first_checkpoint", "last_checkpoint", "declared_count", "distance_limit", "visited_count", "route_check")),
    ("constraint-library-cart-sort", "Library cart sort", ("first_section", "last_section", "book_count", "shelf_limit", "sorted_count", "cart_check")),
    ("constraint-satellite-panel-command", "Satellite panel command", ("first_panel", "second_panel", "command_count", "power_limit", "deployed_count", "command_check")),
    ("constraint-hotel-room-link", "Hotel room link", ("primary_room", "companion_room", "guest_count", "floor_limit", "key_count", "booking_check")),
    ("constraint-blood-sample-chain", "Blood sample chain", ("draw_station", "analysis_station", "tube_count", "time_limit", "scan_count", "custody_check")),
    ("constraint-pharmacy-batch-release", "Pharmacy batch release", ("mix_batch", "pack_batch", "dose_count", "variance_limit", "seal_count", "release_check")),
    ("constraint-cargo-manifest-count", "Cargo manifest count", ("loaded_units", "declared_units", "container_count", "mass_limit", "seal_count", "manifest_check")),
    ("constraint-tournament-pairing", "Tournament pairing", ("home_seed", "away_seed", "player_count", "round_limit", "pair_count", "pairing_check")),
    ("constraint-exam-seat-allocation", "Exam seat allocation", ("first_candidate", "second_candidate", "candidate_count", "room_limit", "seat_count", "allocation_check")),
    ("constraint-invoice-tax-reconciliation", "Invoice tax reconciliation", ("net_amount", "gross_amount", "line_count", "tax_limit", "paid_count", "invoice_check")),
    ("constraint-parcel-dimension-weight", "Parcel dimension and weight", ("short_edge", "long_edge", "item_count", "weight_limit", "label_count", "parcel_check")),
    ("constraint-sensor-range-calibration", "Sensor range calibration", ("low_reading", "high_reading", "sample_count", "drift_limit", "reference_count", "calibration_check")),
    ("constraint-network-port-binding", "Network port binding", ("source_port", "target_port", "mapping_count", "range_limit", "lease_count", "binding_check")),
    ("constraint-clinic-referral-window", "Clinic referral window", ("request_day", "visit_day", "referral_count", "window_limit", "approval_count", "referral_check")),
    ("constraint-rental-key-handoff", "Rental key handoff", ("checkout_slot", "return_slot", "key_count", "window_limit", "signature_count", "handoff_check")),
    ("constraint-bakery-batch-split", "Bakery batch split", ("dough_units", "tray_units", "loaf_count", "oven_limit", "label_count", "batch_check")),
    ("constraint-museum-loan-return", "Museum loan return", ("loan_day", "return_day", "object_count", "term_limit", "condition_count", "loan_check")),
    ("constraint-fleet-driver-assignment", "Fleet driver assignment", ("shift_start", "shift_end", "vehicle_count", "hours_limit", "driver_count", "assignment_check")),
)

IMPOSSIBLE_DOMAINS = (
    ("constraint-substation-breaker-state", "Substation breaker state", ("open_breakers", "closed_breakers", "declared_total", "capacity_limit", "phase_code", "state_check")),
    ("constraint-reservoir-valve-balance", "Reservoir valve balance", ("inlet_flow", "outlet_flow", "valve_count", "storage_limit", "level_code", "balance_check")),
    ("constraint-battery-pack-topology", "Battery pack topology", ("series_cells", "parallel_cells", "declared_cells", "current_limit", "fuse_count", "topology_check")),
    ("constraint-elevator-door-motion", "Elevator door motion", ("door_position", "car_position", "sensor_count", "motion_limit", "lock_count", "interlock_check")),
    ("constraint-runway-occupancy-plan", "Runway occupancy plan", ("arrival_slot", "departure_slot", "aircraft_count", "separation_limit", "clearance_count", "occupancy_check")),
    ("constraint-cold-chain-seal-state", "Cold chain seal state", ("opened_seals", "closed_seals", "declared_seals", "temperature_limit", "scan_count", "chain_check")),
    ("constraint-bridge-lane-reversal", "Bridge lane reversal", ("eastbound_lanes", "westbound_lanes", "declared_lanes", "capacity_limit", "signal_count", "reversal_check")),
    ("constraint-reactor-interlock-state", "Reactor interlock state", ("armed_rods", "withdrawn_rods", "declared_rods", "power_limit", "trip_count", "interlock_check")),
    ("constraint-greenhouse-irrigation-cycle", "Greenhouse irrigation cycle", ("open_zones", "closed_zones", "declared_zones", "flow_limit", "timer_count", "cycle_check")),
    ("constraint-warehouse-inventory-conservation", "Warehouse inventory conservation", ("received_units", "shipped_units", "declared_units", "storage_limit", "audit_count", "inventory_check")),
    ("constraint-transit-card-journey", "Transit card journey", ("entry_taps", "exit_taps", "declared_trips", "fare_limit", "transfer_count", "journey_check")),
    ("constraint-voting-ballot-consistency", "Voting ballot consistency", ("issued_ballots", "returned_ballots", "declared_ballots", "box_limit", "spoiled_count", "ballot_check")),
    ("constraint-insurance-claim-status", "Insurance claim status", ("open_claims", "closed_claims", "declared_claims", "reserve_limit", "appeal_count", "status_check")),
    ("constraint-build-pipeline-dependency", "Build pipeline dependency", ("ready_steps", "blocked_steps", "declared_steps", "worker_limit", "edge_count", "dependency_check")),
    ("constraint-course-prerequisite-plan", "Course prerequisite plan", ("completed_courses", "pending_courses", "declared_courses", "credit_limit", "edge_count", "plan_check")),
    ("constraint-hospital-bed-transfer", "Hospital bed transfer", ("occupied_beds", "free_beds", "declared_beds", "ward_limit", "transfer_count", "bed_check")),
    ("constraint-network-route-loop", "Network route loop", ("forward_edges", "return_edges", "declared_edges", "hop_limit", "route_count", "loop_check")),
    ("constraint-payroll-period-ledger", "Payroll period ledger", ("credited_hours", "debited_hours", "declared_hours", "period_limit", "entry_count", "ledger_check")),
    ("constraint-package-custody-chain", "Package custody chain", ("accepted_events", "released_events", "declared_events", "custody_limit", "signature_count", "chain_check")),
    ("constraint-lab-sample-lineage", "Lab sample lineage", ("parent_samples", "child_samples", "declared_samples", "depth_limit", "link_count", "lineage_check")),
    ("constraint-parking-zone-occupancy", "Parking zone occupancy", ("occupied_spaces", "free_spaces", "declared_spaces", "zone_limit", "permit_count", "occupancy_check")),
    ("constraint-fire-alarm-sector", "Fire alarm sector", ("armed_sensors", "bypassed_sensors", "declared_sensors", "sector_limit", "fault_count", "alarm_check")),
    ("constraint-drone-swarm-formation", "Drone swarm formation", ("active_drones", "reserve_drones", "declared_drones", "radius_limit", "link_count", "formation_check")),
    ("constraint-water-meter-rollover", "Water meter rollover", ("prior_reading", "current_reading", "declared_units", "dial_limit", "rollover_count", "meter_check")),
    ("constraint-cinema-screening-capacity", "Cinema screening capacity", ("reserved_seats", "open_seats", "declared_seats", "room_limit", "ticket_count", "capacity_check")),
)

ATOMIC_DOMAINS = (
    ("constraint-permit-application-review", "Permit application review", ("old_revision", "new_revision", "declared_fields", "field_limit", "attachment_count", "review_check")),
    ("constraint-customs-declaration-review", "Customs declaration review", ("declared_value", "assessed_value", "item_count", "value_limit", "document_count", "declaration_check")),
    ("constraint-scholarship-eligibility-review", "Scholarship eligibility review", ("earned_points", "required_points", "course_count", "credit_limit", "evidence_count", "eligibility_check")),
    ("constraint-medication-order-review", "Medication order review", ("ordered_dose", "dispensed_dose", "day_count", "dose_limit", "approval_count", "order_check")),
    ("constraint-construction-lift-plan", "Construction lift plan", ("planned_load", "measured_load", "lift_count", "load_limit", "inspection_count", "plan_check")),
    ("constraint-data-center-maintenance-window", "Data center maintenance window", ("window_start", "window_end", "host_count", "outage_limit", "approval_count", "window_check")),
    ("constraint-railway-timetable-change", "Railway timetable change", ("old_departure", "new_departure", "stop_count", "delay_limit", "notice_count", "timetable_check")),
    ("constraint-food-allergen-label", "Food allergen label", ("recipe_codes", "label_codes", "ingredient_count", "code_limit", "warning_count", "label_check")),
    ("constraint-shipment-insurance-quote", "Shipment insurance quote", ("declared_value", "covered_value", "package_count", "policy_limit", "rider_count", "quote_check")),
    ("constraint-conference-registration-bundle", "Conference registration bundle", ("selected_sessions", "available_sessions", "attendee_count", "session_limit", "ticket_count", "bundle_check")),
    ("constraint-utility-tariff-selection", "Utility tariff selection", ("prior_usage", "projected_usage", "month_count", "usage_limit", "meter_count", "tariff_check")),
    ("constraint-warehouse-return-authorization", "Warehouse return authorization", ("shipped_units", "returned_units", "line_count", "return_limit", "reason_count", "authorization_check")),
    ("constraint-clinic-appointment-reschedule", "Clinic appointment reschedule", ("old_slot", "new_slot", "visit_count", "window_limit", "consent_count", "reschedule_check")),
    ("constraint-school-bus-route-change", "School bus route change", ("old_stops", "new_stops", "rider_count", "route_limit", "notice_count", "change_check")),
    ("constraint-cloud-resource-reservation", "Cloud resource reservation", ("requested_units", "granted_units", "hour_count", "quota_limit", "approval_count", "reservation_check")),
    ("constraint-sports-roster-submission", "Sports roster submission", ("eligible_players", "listed_players", "team_count", "roster_limit", "signature_count", "roster_check")),
    ("constraint-election-district-update", "Election district update", ("prior_voters", "revised_voters", "precinct_count", "variance_limit", "review_count", "district_check")),
    ("constraint-manufacturing-work-order", "Manufacturing work order", ("planned_units", "released_units", "operation_count", "capacity_limit", "inspection_count", "order_check")),
    ("constraint-airline-itinerary-change", "Airline itinerary change", ("old_segment", "new_segment", "traveler_count", "connection_limit", "ticket_count", "itinerary_check")),
    ("constraint-laboratory-calibration-record", "Laboratory calibration record", ("prior_value", "measured_value", "sample_count", "tolerance_limit", "standard_count", "record_check")),
    ("constraint-municipal-event-permit", "Municipal event permit", ("requested_capacity", "approved_capacity", "day_count", "venue_limit", "certificate_count", "permit_check")),
    ("constraint-loan-repayment-amendment", "Loan repayment amendment", ("old_payment", "new_payment", "term_count", "payment_limit", "consent_count", "amendment_check")),
    ("constraint-subscription-plan-migration", "Subscription plan migration", ("old_units", "new_units", "account_count", "plan_limit", "feature_count", "migration_check")),
    ("constraint-habitat-restoration-survey", "Habitat restoration survey", ("prior_score", "current_score", "plot_count", "score_limit", "sample_count", "survey_check")),
    ("constraint-emergency-crew-dispatch", "Emergency crew dispatch", ("available_crews", "assigned_crews", "incident_count", "crew_limit", "ack_count", "dispatch_check")),
)


DOMAINS = tuple(
    Domain(task_id, title, fields, capability)
    for capability, rows in (
        ("coordinate_bounds_and_routes", COORDINATE_DOMAINS),
        ("paired_field_consistency", PAIRED_DOMAINS),
        ("impossible_state_rejection", IMPOSSIBLE_DOMAINS),
        ("atomic_validation_and_diagnostics", ATOMIC_DOMAINS),
    )
    for task_id, title, fields in rows
)

assert len(DOMAINS) == 100
assert len({domain.task_id for domain in DOMAINS}) == 100
assert all(len(set(domain.fields)) == 6 for domain in DOMAINS)


BASELINE = (1, 2, 3, 4, 5, 6)


# Each capability owns three separate policy axes.  A task takes one rule from
# each axis.  The 5 x 5 schedule below gives every task in a capability a
# unique semantic contract without assigning an arbitrary triple from a global
# positional vocabulary.  Expressions operate on values normalized by the
# documented policy shift, so the constants-policy adversarial control remains
# an internally coherent buildable clone.
POLICY_AXES: dict[str, tuple[tuple[tuple[str, str], ...], ...]] = {
    "coordinate_bounds_and_routes": (
        (
            ("coord_forward", "the target coordinate must be after the source coordinate"),
            ("coord_distinct", "the source and target coordinates must be different"),
            ("coord_adjacent", "the target must be exactly one coordinate after the source"),
            ("coord_declared_span", "the declared span must equal source plus target"),
            ("coord_span_limit", "the target-source distance must not exceed the declared span"),
        ),
        (
            ("coord_endpoint_blocked", "neither endpoint may equal the blocked coordinate"),
            ("coord_blocked_between", "the blocked coordinate may not lie on or between the endpoints"),
            ("coord_budget", "the declared route count must not exceed the resource limit"),
            ("coord_positive_count", "the declared route count must be positive"),
            ("coord_marker_after_count", "the blocked or reserved marker must be after the declared count"),
        ),
        (
            ("coord_route_checksum", "the route check must equal declared count plus blocked marker minus one"),
            ("coord_terminal_budget", "the route check must be greater than the resource limit"),
            ("coord_terminal_count", "the route check must be at least the declared count"),
            ("coord_even_check", "the route check must be even"),
            ("coord_endpoint_check", "source coordinate plus resource limit must equal the route check"),
        ),
    ),
    "paired_field_consistency": (
        (
            ("pair_ordered", "the second identifier or value must be greater than the first"),
            ("pair_distinct", "the paired identifiers or values must differ"),
            ("pair_adjacent", "the paired identifiers or values must be consecutive"),
            ("pair_declared_total", "the declared count must equal the sum of the pair"),
            ("pair_within_limit", "the first paired value must not exceed the published limit"),
        ),
        (
            ("pair_count_limit", "the declared count must not exceed its limit"),
            ("pair_count_evidence", "declared count plus evidence count must fit the final consistency budget"),
            ("pair_evidence_check", "the evidence count must not exceed declared count plus limit"),
            ("pair_combined_capacity", "declared count plus limit must cover the evidence count"),
            ("pair_limit_before_evidence", "the limit must be strictly below the evidence count"),
        ),
        (
            ("pair_evidence_offset", "the evidence count must be two above the declared count"),
            ("pair_check_successor", "the final check must be one above the evidence count"),
            ("pair_first_evidence_check", "first paired value plus evidence count must equal the final check"),
            ("pair_second_limit_check", "second paired value plus limit must equal the final check"),
            ("pair_doubled_count_check", "twice the declared count must equal the final check"),
        ),
    ),
    "impossible_state_rejection": (
        (
            ("state_conservation", "the two component counts must sum to the declared total"),
            ("state_component_order", "the first component count must be smaller than the second"),
            ("state_components_distinct", "the component counts must differ"),
            ("state_component_delta", "the second component count must be exactly one above the first"),
            ("state_nonnegative", "the first component count must be non-negative"),
        ),
        (
            ("state_capacity", "the declared total must not exceed capacity"),
            ("state_aux_total", "the auxiliary count must not exceed second component plus capacity"),
            ("state_first_plus_total", "first component plus declared total must not exceed capacity"),
            ("state_second_plus_aux", "second component plus auxiliary count must cover the declared total"),
            ("state_capacity_successor", "capacity must be exactly one above the declared total"),
        ),
        (
            ("state_aux_capacity_window", "the auxiliary count may be at most one above capacity"),
            ("state_check_successor", "the final state check must be one above the auxiliary count"),
            ("state_first_aux_check", "first component plus auxiliary count must equal the final check"),
            ("state_double_total_check", "twice the declared total must equal the final check"),
            ("state_second_capacity_check", "second component plus capacity must equal the final check"),
        ),
    ),
    "atomic_validation_and_diagnostics": (
        (
            ("review_monotone", "the revised value must not precede the original value"),
            ("review_changed", "the revised value must differ from the original value"),
            ("review_single_step", "the revised value must be exactly one above the original value"),
            ("review_declared_total", "the declared review count must equal original plus revised value"),
            ("review_within_limit", "the revised value must not exceed the review limit"),
        ),
        (
            ("review_count_limit", "declared count plus evidence must not exceed limit plus final check"),
            ("review_count_evidence", "the declared count must not exceed limit plus evidence"),
            ("review_evidence_check", "original plus evidence must not exceed revised plus final check"),
            ("review_combined_capacity", "declared count, limit, and evidence must cover the final check"),
            ("review_limit_before_evidence", "limit plus original value must remain below the final check"),
        ),
        (
            ("review_evidence_offset", "the evidence count must be one above the review limit"),
            ("review_check_successor", "the final review check must be two above the review limit"),
            ("review_original_evidence_check", "original, revised, and declared counts must sum to the final check"),
            ("review_revised_limit_check", "revised plus declared count must equal the evidence count"),
            ("review_doubled_count_check", "original plus review limit must equal the evidence count"),
        ),
    ),
}


def predicates_for(domain: Domain, local_index: int) -> tuple[Predicate, Predicate, Predicate]:
    first = local_index % 5
    second = local_index // 5
    third = (2 * first + second) % 5
    axes = POLICY_AXES[domain.capability]
    selected = (axes[0][first], axes[1][second], axes[2][third])
    return tuple(
        Predicate(
            kind=kind,
            error=kind,
            description=description,
        )
        for axis, (kind, description) in enumerate(selected)
    )


def predicate_fails(kind: str, values: tuple[int, ...], shift: int = 0) -> bool:
    a, b, c, d, e, f = (value - shift for value in values)
    checks = {
        "coord_forward": b <= a,
        "coord_distinct": b == a,
        "coord_adjacent": b - a != 1,
        "coord_declared_span": c != a + b,
        "coord_span_limit": b - a > c,
        "coord_endpoint_blocked": a == d or b == d,
        "coord_blocked_between": a <= d <= b,
        "coord_budget": c > e,
        "coord_positive_count": c < 1,
        "coord_marker_after_count": d <= c,
        "coord_route_checksum": f != c + d - 1,
        "coord_terminal_budget": f <= e,
        "coord_terminal_count": f < c,
        "coord_even_check": f % 2 != 0,
        "coord_endpoint_check": a + e != f,
        "pair_ordered": b <= a,
        "pair_distinct": b == a,
        "pair_adjacent": b - a != 1,
        "pair_declared_total": c != a + b,
        "pair_within_limit": a > d,
        "pair_count_limit": c > d,
        "pair_count_evidence": c + e > f + 3,
        "pair_evidence_check": e > c + d,
        "pair_combined_capacity": c + d < e,
        "pair_limit_before_evidence": d >= e,
        "pair_evidence_offset": e != c + 2,
        "pair_check_successor": f != e + 1,
        "pair_first_evidence_check": a + e != f,
        "pair_second_limit_check": b + d != f,
        "pair_doubled_count_check": c * 2 != f,
        "state_conservation": a + b != c,
        "state_component_order": a >= b,
        "state_components_distinct": a == b,
        "state_component_delta": b - a != 1,
        "state_nonnegative": a < 0,
        "state_capacity": c > d,
        "state_aux_total": e > b + d,
        "state_first_plus_total": a + c > d,
        "state_second_plus_aux": b + e < c,
        "state_capacity_successor": d != c + 1,
        "state_aux_capacity_window": e > d + 1,
        "state_check_successor": f != e + 1,
        "state_first_aux_check": a + e != f,
        "state_double_total_check": c * 2 != f,
        "state_second_capacity_check": b + d != f,
        "review_monotone": b < a,
        "review_changed": b == a,
        "review_single_step": b - a != 1,
        "review_declared_total": c != a + b,
        "review_within_limit": b > d,
        "review_count_limit": c + e > d + f,
        "review_count_evidence": c > d + e,
        "review_evidence_check": e + a > f + b,
        "review_combined_capacity": c + d + e < f,
        "review_limit_before_evidence": d + a >= f,
        "review_evidence_offset": e != d + 1,
        "review_check_successor": f != d + 2,
        "review_original_evidence_check": a + b + c != f,
        "review_revised_limit_check": b + c != e,
        "review_doubled_count_check": a + d != e,
    }
    return checks[kind]


def _candidate_values(shift: int = 0) -> tuple[tuple[int, ...], ...]:
    base = tuple(value + shift for value in BASELINE)
    values = list(range(-3 + shift, 11 + shift))
    candidates: list[tuple[int, ...]] = [base]
    for first in range(6):
        for value in values:
            row = list(base)
            row[first] = value
            candidates.append(tuple(row))
    for first, second in combinations(range(6), 2):
        for left in values:
            for right in values:
                row = list(base)
                row[first], row[second] = left, right
                candidates.append(tuple(row))
    return tuple(dict.fromkeys(candidates))


def witness_for(primary: Predicate, others: tuple[Predicate, Predicate], shift: int = 0) -> tuple[int, ...] | None:
    for values in _candidate_values(shift):
        if predicate_fails(primary.kind, values, shift) and not any(
            predicate_fails(rule.kind, values, shift) for rule in others
        ):
            return values
    return None


def multi_failure_witness(rules: tuple[Predicate, Predicate, Predicate], shift: int = 0) -> tuple[int, ...]:
    for values in _candidate_values(shift):
        if sum(predicate_fails(rule.kind, values, shift) for rule in rules) >= 2:
            return values
    raise RuntimeError(f"no multiple-failure witness for {rules}")


PREDICATE_TRIPLES = tuple(
    predicates_for(domain, index % 25) for index, domain in enumerate(DOMAINS)
)
assert len(PREDICATE_TRIPLES) == 100
assert len({tuple(rule.kind for rule in triple) for triple in PREDICATE_TRIPLES}) == 100
assert all(
    witness_for(rule, tuple(other for other in triple if other != rule)) is not None
    for triple in PREDICATE_TRIPLES
    for rule in triple
)
