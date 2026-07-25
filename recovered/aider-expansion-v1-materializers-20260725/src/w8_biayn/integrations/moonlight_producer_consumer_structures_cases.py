"""Declarative inventory for the 60 producer-consumer expansion roots.

The inventory is intentionally data-only.  The owner renders and verifies the
public contract, C++ state machine, tests, negative fixture, and diversity
witnesses from these immutable records.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaseSpec:
    task_id: str
    group: str
    mechanism: str
    producer_verb: str
    consumer_verb: str
    lifecycle_verb: str
    state_model: str


_ROWS = (
    # Admission and backpressure.
    ("credit-window-dispatcher", "admission", "per-producer credit reservation and matching completion refund", "reserve_credit", "complete_credit", "set_credit_epoch", "credit ledger plus outstanding ownership records"),
    ("deficit-fair-ingress", "admission", "signed deficit accumulation for variable-cost work", "offer_costed", "dispatch_affordable", "add_quantum", "source deficits plus stable source cursors"),
    ("reservation-ticket-gate", "admission", "monotonic reservation tickets with unclaimed cancellation compaction", "reserve_ticket", "claim_ticket", "cancel_unclaimed", "ticket intervals plus claimed bitmap"),
    ("byte-budget-mailbox", "admission", "byte-budget accounting with exact completion refunds", "store_sized", "take_sized", "resize_budget", "message extents plus used-byte counter"),
    ("deadline-shed-buffer", "admission", "stable least-urgent shedding under full admission", "offer_deadline", "take_urgent", "seal_deadlines", "deadline heap relation plus admission sequence"),
    ("keyed-replacement-inbox", "admission", "in-place replacement without a second ordering position", "upsert_pending", "take_oldest_key", "freeze_keys", "key index plus first-admission order"),
    ("burst-token-admitter", "admission", "producer-local burst tokens refilled only by explicit epochs", "spend_token", "take_tokenized", "refill_epoch", "per-producer token buckets plus pending work"),
    ("dependency-ready-staging", "admission", "prerequisite-token staging before readiness", "stage_dependencies", "take_ready", "publish_token", "dependency sets plus ready frontier"),
    ("tenant-waterline-gate", "admission", "global high/low waterline pause and resume with tenant FIFO", "offer_tenant", "take_tenant", "cross_waterline", "tenant lanes plus global occupancy phase"),
    ("quorum-capacity-admitter", "admission", "atomic reservation across a declared consumer quorum", "reserve_quorum", "consume_quorum", "release_reservation", "consumer capacity ledger plus atomic reservation journal"),
    # Closure and lifecycle.
    ("half-close-duplex-handoff", "lifecycle", "independent producer and consumer half-close with prefix drain", "send_half", "receive_half", "close_half", "two closure bits plus accepted prefix"),
    ("phased-drain-controller", "lifecycle", "open, sealing, draining, and stopped phase transitions", "submit_open", "drain_phase", "advance_phase", "explicit four-state phase machine"),
    ("poison-free-stop-barrier", "lifecycle", "producer retirement barrier without sentinel payloads", "publish_active", "consume_before_stop", "retire_producer", "active-producer set plus stop barrier"),
    ("producer-lease-shutdown", "lifecycle", "producer leases that own reservations until expiry", "publish_leased", "consume_leased", "expire_lease", "lease tokens plus reservation ownership"),
    ("epoch-sealed-inbox", "lifecycle", "independently staged epochs with immutable sealed epochs", "submit_epoch", "consume_sealed", "seal_epoch", "epoch map plus sealed frontier"),
    ("abortable-batch-handoff", "lifecycle", "atomic abort of uncommitted batches while committed batches drain", "append_batch", "consume_committed", "finish_batch", "batch journal plus commit state"),
    ("reopen-generation-mailbox", "lifecycle", "generation-scoped handles invalidated by reopen", "publish_generation", "consume_generation", "reopen_generation", "generation token plus generation-owned pending set"),
    ("cascading-stage-closure", "lifecycle", "downstream closure propagated after each stage drains", "push_stage", "pull_stage", "close_stage", "stage occupancy vector plus closure frontier"),
    ("orphan-reclaim-handoff", "lifecycle", "owner retirement reclaiming only unacknowledged work", "assign_owner", "ack_owner", "retire_owner", "ownership table plus completion history"),
    ("terminal-error-broadcast", "lifecycle", "one terminal error delivered after each consumer prefix", "publish_before_error", "observe_prefix", "broadcast_error", "consumer prefix cursors plus terminal observation bits"),
    # Multi-consumer retention.
    ("consumer-cursor-retention", "fanout", "retention through the minimum active consumer cursor", "publish_cursor", "advance_cursor", "register_cursor", "append log plus active cursor map"),
    ("quorum-ack-reclaimer", "fanout", "reclamation after a fixed acknowledgement quorum", "publish_quorum_item", "ack_quorum_item", "change_quorum", "per-item acknowledgement bitsets"),
    ("lag-budget-fanout", "fanout", "bounded lag with exact skipped-prefix diagnostics", "publish_lagged", "consume_with_gap", "set_lag_budget", "consumer lag counters plus retained suffix"),
    ("snapshot-subscriber-mailbox", "fanout", "immutable registration snapshot followed by live changes", "publish_snapshot_change", "consume_snapshot_change", "subscribe_snapshot", "versioned snapshot plus subscriber phase"),
    ("topic-mask-fanout", "fanout", "topic-filtered fanout preserving global admission order", "publish_topic", "consume_topic", "set_topic_mask", "global log plus consumer masks and cursors"),
    ("durable-offset-tracker", "fanout", "contiguous commit advancement under out-of-order acknowledgements", "publish_offset", "ack_offset", "commit_contiguous", "acknowledged-offset gaps plus durable frontier"),
    ("slow-reader-evictor", "fanout", "deterministic slow-reader eviction and reclaim recomputation", "publish_for_readers", "read_for_consumer", "evict_slowest", "reader scores plus retention frontier"),
    ("replay-window-handoff", "fanout", "bounded acknowledged suffix replay for rejoining consumers", "publish_replayable", "consume_replay", "rejoin_window", "terminal suffix plus live consumer cursor"),
    ("branch-barrier-delivery", "fanout", "branch group barrier before next-item release", "publish_branch_item", "ack_branch", "reset_branch_barrier", "per-item branch bitmap plus barrier index"),
    ("selective-redelivery-table", "fanout", "consumer-specific redelivery after negative acknowledgement", "publish_selective", "take_selective", "nack_consumer", "delivery matrix plus targeted retry rows"),
    # Deterministic scheduling.
    ("deficit-round-robin-mailbox", "scheduling", "cost-aware deficit round-robin service", "enqueue_cost", "drain_deficit", "grant_quantum", "lane deficits plus cyclic lane cursor"),
    ("aging-fair-consumer-pool", "scheduling", "waiting-age promotion of consumer claims", "offer_for_pool", "claim_aged", "age_waiters", "waiting ages plus weighted consumer claims"),
    ("weighted-source-drainer", "scheduling", "resumable finite weighted source schedule", "offer_weighted", "drain_weighted", "replace_weights", "weight schedule plus persistent schedule position"),
    ("deadline-slack-dispatcher", "scheduling", "minimum stored deadline slack with sequence ties", "offer_slack", "dispatch_slack", "advance_logical_now", "stored slack records plus sequence counter"),
    ("producer-turnstile", "scheduling", "cyclic active-producer turns that skip inactive producers", "join_turnstile", "dispatch_turn", "leave_turnstile", "active producer ring relation plus current turn"),
    ("locality-batch-scheduler", "scheduling", "bounded same-affinity batches before deterministic rotation", "offer_affinity", "dispatch_affinity", "set_batch_limit", "affinity lanes plus batch-run counter"),
    ("anti-starvation-lane-picker", "scheduling", "priority streak cap forcing oldest lower lane", "offer_priority", "pick_fair_lane", "set_streak_cap", "priority lanes plus streak and admission ages"),
    ("dependency-topology-dispatcher", "scheduling", "stable topological release with cycle rejection", "add_dependency_work", "dispatch_topology", "satisfy_dependency", "dependency graph plus stable ready set"),
    ("work-steal-lease-board", "scheduling", "oldest unleased work stealing with origin return", "post_stealable", "steal_oldest", "expire_steal_lease", "origin lanes plus lease ownership table"),
    ("cohort-fair-release", "scheduling", "age-rotated complete cohorts preserving member order", "join_cohort", "release_cohort", "seal_cohort", "cohort membership plus cohort admission ages"),
    # Acknowledgement and ownership.
    ("ack-timeout-retry-ledger", "ownership", "logical-tick acknowledgement expiry with bounded retry", "deliver_attempt", "ack_attempt", "advance_retry_tick", "attempt ledger plus logical deadlines"),
    ("idempotency-key-handoff", "ownership", "one terminal result shared by duplicate idempotency keys", "submit_idempotent", "complete_idempotent", "forget_idempotency", "key state machine plus terminal result cache"),
    ("two-phase-delivery-slot", "ownership", "prepared ownership hidden until commit with rollback", "prepare_delivery", "consume_committed_slot", "finish_prepare", "prepared slot plus committed visibility bit"),
    ("lease-renewal-queue", "ownership", "token-authenticated renew, complete, and abandon transitions", "lease_work", "complete_lease", "renew_or_abandon", "lease nonce plus expiry and owner"),
    ("nack-classification-router", "ownership", "disjoint retryable, terminal, and reroute nack transitions", "deliver_routable", "ack_routable", "classify_nack", "delivery state plus retry and alternate-route lanes"),
    ("exactly-once-commit-table", "ownership", "separate delivery and durable commit with replay suppression", "deliver_once", "commit_once", "recover_commits", "delivered set plus durable commit table"),
    ("deduplicating-replay-ledger", "ownership", "bounded terminal ledger suppressing retries until compaction", "submit_replay", "finish_replay", "compact_terminal", "terminal generation ledger plus pending identifiers"),
    ("ownership-transfer-token", "ownership", "atomic owner-token invalidation before new-owner completion", "assign_token", "complete_token", "transfer_token", "monotonic ownership token chain"),
    ("tombstone-confirmation-log", "ownership", "tombstone retention until all required confirmations", "publish_tombstone", "confirm_tombstone", "change_required_consumers", "tombstone log plus confirmation sets"),
    ("compensation-workflow-inbox", "ownership", "single lineage-linked compensation after terminal failure", "submit_workflow", "complete_workflow", "fail_and_compensate", "workflow lineage table plus compensation-emitted bit"),
    # Batch and frontier release.
    ("watermark-join-coordinator", "batching", "minimum-producer watermark release", "submit_timestamped", "release_below_watermark", "advance_watermark", "per-producer watermark map plus timestamped staging"),
    ("dual-threshold-batch-assembler", "batching", "count-or-weight batch sealing at first crossed threshold", "append_weighted_item", "take_sealed_batch", "set_batch_thresholds", "open batch counters plus sealed batch list"),
    ("partition-fence-merger", "batching", "merge through the greatest common partition fence", "append_partition", "take_merged_prefix", "advance_partition_fence", "partition prefixes plus fence vector"),
    ("sequence-gap-tolerance-gate", "batching", "bounded sequence-gap skipping with exact diagnostics", "offer_sequence", "release_sequence_prefix", "set_gap_tolerance", "sequence map plus expected sequence and skip ledger"),
    ("aggregate-delta-flusher", "batching", "keyed delta coalescing with stable first-key flush order", "add_delta", "flush_deltas", "mark_flush_barrier", "key deltas plus first-seen order"),
    ("transactional-microbatch-log", "batching", "isolated begin/append/commit/rollback with commit order", "append_transaction", "consume_committed_batch", "finish_transaction", "transaction workspace plus committed batch log"),
    ("checksum-sealed-workset", "batching", "declared-count and checksum guarded workset sealing", "append_checked", "consume_sealed_workset", "seal_with_checksum", "open workset plus running checksum and declared count"),
    ("affinity-cohort-assembler", "batching", "stable affinity cohorts with explicit incomplete policy", "append_affinity_member", "take_affinity_cohort", "close_incomplete_cohorts", "affinity buckets plus first-member order"),
    ("causal-frontier-emitter", "batching", "vector-frontier dominance release with concurrent admission ties", "submit_causal", "emit_dominated", "advance_frontier", "vector clocks plus frontier and admission sequence"),
    ("monotonic-version-release", "batching", "per-key contiguous version release with conflict rejection", "submit_version", "release_contiguous", "reset_version_key", "per-key expected versions plus staged version map"),
)


CASES = tuple(CaseSpec(*row) for row in _ROWS)

assert len(CASES) == 60
assert len({case.task_id for case in CASES}) == len(CASES)
assert len({case.mechanism for case in CASES}) == len(CASES)
assert len({case.state_model for case in CASES}) == len(CASES)
