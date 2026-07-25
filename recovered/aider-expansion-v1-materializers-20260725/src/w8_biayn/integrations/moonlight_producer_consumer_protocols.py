"""Protocol-specific renderers for producer-consumer behavior tasks.

This module deliberately keeps executable policies separate from the family
materializer.  Each curriculum group owns a different state representation,
and each of its ten protocols selects an explicit admission, release, control,
and false-substitute policy.  Test expectations are literal contract vectors;
they are not calculated by mirroring the C++ implementation in Python.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from w8_biayn.integrations.moonlight_producer_consumer_structures_cases import (
    CaseSpec,
)


@dataclass(frozen=True)
class ProtocolPolicy:
    admission: str
    duplicate: str
    release: str
    control: str
    result: str
    wrong_result: str
    expected_first: int
    expected_second: int


def _camel(task_id: str) -> str:
    return "".join(part.capitalize() for part in task_id.split("-"))


def _symbol(value: str) -> str:
    return value.replace("-", "_")


def _concept(case: CaseSpec) -> str:
    words = re.findall(r"[a-z]+", case.task_id)
    return "".join(word.capitalize() for word in words[:2])


def _mode(case: CaseSpec) -> int:
    groups = ("admission", "lifecycle", "fanout", "scheduling", "ownership", "batching")
    if case.group not in groups:
        raise ValueError(f"unknown producer-consumer group: {case.group}")
    return {
        group: index
        for group in groups
        for index, task in enumerate(
            item for item in _GROUP_TASKS[group]
        )
        if task == case.task_id
    }[case.group]


_GROUP_TASKS = {
    "admission": (
        "credit-window-dispatcher", "deficit-fair-ingress",
        "reservation-ticket-gate", "byte-budget-mailbox",
        "deadline-shed-buffer", "keyed-replacement-inbox",
        "burst-token-admitter", "dependency-ready-staging",
        "tenant-waterline-gate", "quorum-capacity-admitter",
    ),
    "lifecycle": (
        "half-close-duplex-handoff", "phased-drain-controller",
        "poison-free-stop-barrier", "producer-lease-shutdown",
        "epoch-sealed-inbox", "abortable-batch-handoff",
        "reopen-generation-mailbox", "cascading-stage-closure",
        "orphan-reclaim-handoff", "terminal-error-broadcast",
    ),
    "fanout": (
        "consumer-cursor-retention", "quorum-ack-reclaimer",
        "lag-budget-fanout", "snapshot-subscriber-mailbox",
        "topic-mask-fanout", "durable-offset-tracker",
        "slow-reader-evictor", "replay-window-handoff",
        "branch-barrier-delivery", "selective-redelivery-table",
    ),
    "scheduling": (
        "deficit-round-robin-mailbox", "aging-fair-consumer-pool",
        "weighted-source-drainer", "deadline-slack-dispatcher",
        "producer-turnstile", "locality-batch-scheduler",
        "anti-starvation-lane-picker", "dependency-topology-dispatcher",
        "work-steal-lease-board", "cohort-fair-release",
    ),
    "ownership": (
        "ack-timeout-retry-ledger", "idempotency-key-handoff",
        "two-phase-delivery-slot", "lease-renewal-queue",
        "nack-classification-router", "exactly-once-commit-table",
        "deduplicating-replay-ledger", "ownership-transfer-token",
        "tombstone-confirmation-log", "compensation-workflow-inbox",
    ),
    "batching": (
        "watermark-join-coordinator", "dual-threshold-batch-assembler",
        "partition-fence-merger", "sequence-gap-tolerance-gate",
        "aggregate-delta-flusher", "transactional-microbatch-log",
        "checksum-sealed-workset", "affinity-cohort-assembler",
        "causal-frontier-emitter", "monotonic-version-release",
    ),
}


_SELECTORS = (
    "candidate.arrival < chosen.arrival",
    "candidate.aux > chosen.aux || (candidate.aux == chosen.aux && candidate.arrival < chosen.arrival)",
    "candidate.key < chosen.key || (candidate.key == chosen.key && candidate.arrival < chosen.arrival)",
    "candidate.actor < chosen.actor || (candidate.actor == chosen.actor && candidate.arrival < chosen.arrival)",
    "candidate.value < chosen.value || (candidate.value == chosen.value && candidate.arrival < chosen.arrival)",
    "candidate.value > chosen.value || (candidate.value == chosen.value && candidate.arrival < chosen.arrival)",
    "candidate.actor > chosen.actor || (candidate.actor == chosen.actor && candidate.arrival < chosen.arrival)",
    "candidate.aux < chosen.aux || (candidate.aux == chosen.aux && candidate.key < chosen.key)",
    "((candidate.actor + phase_) % 7) < ((chosen.actor + phase_) % 7)",
    "candidate.arrival > chosen.arrival",
)


_RESULTS = {
    "admission": (
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.key", "chosen.value", 22, 11),
        ("chosen.key", "chosen.actor", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.key", "chosen.value", 11, 22),
        ("chosen.value", "chosen.actor", 7, 4),
        ("chosen.value", "chosen.key", 7, 4),
        ("chosen.key", "chosen.value", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.actor", "chosen.value", 2, 1),
    ),
    "lifecycle": (
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.key", "chosen.value", 22, 11),
        ("chosen.actor", "chosen.value", 1, 2),
        ("chosen.value", "chosen.actor", 4, 7),
        ("chosen.key", "chosen.actor", 11, 22),
        ("chosen.value", "chosen.key", 7, 4),
        ("chosen.actor", "chosen.value", 2, 1),
        ("chosen.key", "chosen.value", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.value", "chosen.actor", 7, 4),
    ),
    "fanout": (
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.key", "chosen.value", 22, 11),
        ("chosen.key", "chosen.actor", 11, 22),
        ("chosen.actor", "chosen.value", 1, 2),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.value", "chosen.actor", 7, 4),
        ("chosen.actor", "chosen.value", 2, 1),
        ("chosen.key", "chosen.value", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.key", "chosen.actor", 22, 11),
    ),
    "scheduling": (
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.key", "chosen.value", 11, 22),
        ("chosen.key", "chosen.actor", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.actor", "chosen.value", 1, 2),
        ("chosen.value", "chosen.actor", 7, 4),
        ("chosen.actor", "chosen.value", 2, 1),
        ("chosen.key", "chosen.value", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.value", "chosen.actor", 7, 4),
    ),
    "ownership": (
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.key", "chosen.value", 22, 11),
        ("chosen.key", "chosen.actor", 11, 22),
        ("chosen.value", "chosen.actor", 4, 7),
        ("chosen.actor", "chosen.value", 1, 2),
        ("chosen.value", "chosen.key", 7, 4),
        ("chosen.actor", "chosen.value", 2, 1),
        ("chosen.key", "chosen.value", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.value", "chosen.actor", 7, 4),
    ),
    "batching": (
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.key", "chosen.value", 22, 11),
        ("chosen.key", "chosen.actor", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.actor", "chosen.value", 1, 2),
        ("chosen.value", "chosen.actor", 7, 4),
        ("chosen.actor", "chosen.value", 2, 1),
        ("chosen.key", "chosen.value", 11, 22),
        ("chosen.value", "chosen.key", 4, 7),
        ("chosen.value", "chosen.actor", 7, 4),
    ),
}


_GROUP_AGGREGATES = {
    "admission": "requests",
    "lifecycle": "envelopes",
    "fanout": "events",
    "scheduling": "jobs",
    "ownership": "deliveries",
    "batching": "items",
}


def _role_name(text: str, fallback: str) -> str:
    words = re.findall(r"[a-z]+", text.lower())
    useful = [
        word for word in words
        if word not in {"the", "a", "an", "per", "plus", "explicit"}
    ]
    return "_".join(useful[-3:]) if useful else fallback


def _state_terms(case: CaseSpec) -> tuple[str, str, str, str]:
    parts = re.split(r"\s+plus\s+", case.state_model, maxsplit=1)
    primary = _role_name(parts[0], "protocol_ledger")
    secondary = _role_name(
        parts[1] if len(parts) > 1 else case.mechanism,
        "protocol_markers",
    )
    metric = _role_name(case.mechanism, "protocol") + "_metric"
    return _GROUP_AGGREGATES[case.group], primary, secondary, metric


_MECHANISM_EFFECTS = {
    # Admission and backpressure protocols.
    "credit-window-dispatcher": ("{ledger}_[actor] -= value; {markers}_.insert(key);", "{ledger}_[chosen.actor] += chosen.value; {markers}_.erase(chosen.key);", "{ledger}_[participant] = signal; phase_ += 1;"),
    "deficit-fair-ingress": ("{ledger}_[actor] -= value; {markers}_.insert(actor);", "{ledger}_[chosen.actor] += 1;", "{ledger}_[participant] += signal; phase_ = {ledger}_[participant];"),
    "reservation-ticket-gate": ("{ledger}_[key] = actor; {markers}_.insert(key);", "{ledger}_.erase(chosen.key); {markers}_.erase(chosen.key);", "if (signal < 0) {{ {markers}_.erase(participant); }} else {{ phase_ = signal; }}"),
    "byte-budget-mailbox": ("{ledger}_[0] += value; {ledger}_[key] = value;", "{ledger}_[0] -= chosen.value; {ledger}_.erase(chosen.key);", "{ledger}_[0] = signal; phase_ += 1;"),
    "deadline-shed-buffer": ("{ledger}_[key] = next_arrival_; {markers}_.insert(key);", "{ledger}_.erase(chosen.key); {markers}_.erase(chosen.key);", "phase_ = signal; {ledger}_[participant] = signal;"),
    "keyed-replacement-inbox": ("{ledger}_[key] = value; {markers}_.insert(key);", "{ledger}_.erase(chosen.key); {markers}_.erase(chosen.key);", "if (signal == 0) {{ sealed_ = true; }} else {{ phase_ += signal; }}"),
    "burst-token-admitter": ("{ledger}_[actor] -= 1; {markers}_.insert(key);", "{markers}_.erase(chosen.key);", "{ledger}_[participant] += signal; phase_ += signal;"),
    "dependency-ready-staging": ("{ledger}_[key] = value; if (value == 0) {{ {markers}_.insert(key); }}", "{ledger}_.erase(chosen.key); {markers}_.erase(chosen.key);", "for (auto& entry : {ledger}_) {{ if (entry.second > 0) {{ --entry.second; }} }} phase_ += 1;"),
    "tenant-waterline-gate": ("{ledger}_[actor] += 1; {markers}_.insert(key);", "{ledger}_[chosen.actor] -= 1; {markers}_.erase(chosen.key);", "phase_ = signal; {ledger}_[participant] = signal;"),
    "quorum-capacity-admitter": ("{ledger}_[actor] -= value; {markers}_.insert(key);", "{ledger}_[chosen.actor] += chosen.value; {markers}_.erase(chosen.key);", "{ledger}_[participant] = signal; phase_ = participant;"),
    # Lifecycle and closure protocols.
    "half-close-duplex-handoff": ("{ledger}_[actor] += 1;", "{ledger}_[chosen.actor] -= 1;", "if (signal < 0) {{ {markers}_.insert(participant); }} else {{ phase_ += signal; }}"),
    "phased-drain-controller": ("{ledger}_[phase_] += 1;", "{ledger}_[phase_] -= 1;", "phase_ = signal; if (signal == 3) {{ sealed_ = true; }}"),
    "poison-free-stop-barrier": ("{ledger}_[actor] = 1; {markers}_.insert(actor);", "{ledger}_[chosen.actor] = 0;", "{markers}_.erase(participant); if ({markers}_.empty()) {{ sealed_ = true; }}"),
    "producer-lease-shutdown": ("{ledger}_[actor] = phase_ + value;", "{ledger}_.erase(chosen.actor);", "phase_ += signal; {ledger}_[participant] = phase_ + signal;"),
    "epoch-sealed-inbox": ("{ledger}_[key] = phase_;", "{ledger}_.erase(chosen.key);", "phase_ = signal; if (signal == 0) {{ sealed_ = true; }}"),
    "abortable-batch-handoff": ("{ledger}_[actor] += value; {markers}_.insert(key);", "{markers}_.erase(chosen.key);", "if (signal < 0) {{ {ledger}_.erase(participant); }} else {{ {ledger}_[participant] = signal; }}"),
    "reopen-generation-mailbox": ("{ledger}_[key] = phase_;", "{ledger}_.erase(chosen.key);", "++phase_; sealed_ = false; {markers}_.insert(participant);"),
    "cascading-stage-closure": ("{ledger}_[actor] += 1;", "{ledger}_[chosen.actor] -= 1;", "{markers}_.insert(participant); if (signal == 0) {{ ++phase_; }}"),
    "orphan-reclaim-handoff": ("{ledger}_[key] = actor;", "{ledger}_.erase(chosen.key);", "if (signal < 0) {{ for (auto iterator = {ledger}_.begin(); iterator != {ledger}_.end();) {{ if (iterator->second == participant) iterator = {ledger}_.erase(iterator); else ++iterator; }} }} phase_ += 1;"),
    "terminal-error-broadcast": ("{ledger}_[actor] += 1;", "{ledger}_[participant] += 1;", "sealed_ = signal < 0; phase_ += 1; {markers}_.insert(participant);"),
    # Fanout and retention protocols.
    "consumer-cursor-retention": ("{ledger}_[key] = next_arrival_;", "", "consumer_cursors_[participant] = 0; phase_ += 1;"),
    "quorum-ack-reclaimer": ("{ledger}_[key] = 0;", "", "phase_ = signal; {markers}_.insert(participant);"),
    "lag-budget-fanout": ("{ledger}_[key] = next_arrival_;", "", "{ledger}_[participant] = signal; phase_ = signal;"),
    "snapshot-subscriber-mailbox": ("{ledger}_[key] = phase_;", "", "consumer_cursors_[participant] = 0; {markers}_.insert(participant); ++phase_;"),
    "topic-mask-fanout": ("{ledger}_[key] = actor;", "", "{ledger}_[participant] = signal; phase_ += 1;"),
    "durable-offset-tracker": ("{ledger}_[key] = arrival;", "", "{ledger}_[participant] = signal; phase_ += 1;"),
    "slow-reader-evictor": ("{ledger}_[key] = 0;", "", "if (signal < 0) {{ {markers}_.erase(participant); for (auto& entry : {ledger}_) {{ entry.second &= ~(1 << participant); }} }} else {{ {markers}_.insert(participant); }} phase_ += 1;"),
    "replay-window-handoff": ("{ledger}_[key] = next_arrival_;", "", "consumer_cursors_[participant] = 0; phase_ = signal;"),
    "branch-barrier-delivery": ("{ledger}_[key] = 0;", "", "{markers}_.insert(participant); phase_ = signal;"),
    "selective-redelivery-table": ("{ledger}_[key] = 0;", "", "if (signal < 0) {{ for (auto& item : {aggregate}_) {{ if ({ledger}_.count(item.key) != 0U && ({ledger}_.at(item.key) & (1 << participant)) != 0) {{ {ledger}_[item.key] &= ~(1 << participant); break; }} }} }} else {{ {markers}_.insert(participant); }} phase_ += 1;"),
    # Scheduling protocols.
    "deficit-round-robin-mailbox": ("{ledger}_[actor] -= value;", "{ledger}_[chosen.actor] += 1;", "{ledger}_[participant] += signal; phase_ = participant;"),
    "aging-fair-consumer-pool": ("{ledger}_[key] = next_arrival_;", "{ledger}_.erase(chosen.key);", "for (auto& entry : {ledger}_) {{ entry.second += signal; }} ++phase_;"),
    "weighted-source-drainer": ("{ledger}_[actor] += value;", "{ledger}_[chosen.actor] -= chosen.value;", "{ledger}_[participant] = signal; phase_ = (phase_ + 1) % 17;"),
    "deadline-slack-dispatcher": ("{ledger}_[key] = key - phase_;", "{ledger}_.erase(chosen.key);", "phase_ += signal; {ledger}_[participant] = phase_;"),
    "producer-turnstile": ("{markers}_.insert(actor); {ledger}_[actor] += 1;", "phase_ = chosen.actor;", "if (signal < 0) {{ {markers}_.erase(participant); }} else {{ phase_ = participant; }}"),
    "locality-batch-scheduler": ("{ledger}_[actor] += 1;", "{ledger}_[chosen.actor] -= 1;", "{ledger}_[participant] = signal; phase_ = signal;"),
    "anti-starvation-lane-picker": ("{ledger}_[actor] += 1;", "{ledger}_[chosen.actor] = 0;", "phase_ = signal; {ledger}_[participant] += 1;"),
    "dependency-topology-dispatcher": ("{ledger}_[key] = value;", "{ledger}_.erase(chosen.key);", "for (auto& entry : {ledger}_) {{ if (entry.second == participant) entry.second = signal; }} ++phase_;"),
    "work-steal-lease-board": ("{ledger}_[key] = actor;", "{ledger}_[chosen.key] = participant;", "{ledger}_.erase(participant); phase_ += signal;"),
    "cohort-fair-release": ("{ledger}_[actor] += 1;", "{ledger}_[chosen.actor] -= 1;", "{markers}_.insert(participant); phase_ = signal;"),
    # Ownership and acknowledgement protocols.
    "ack-timeout-retry-ledger": ("{ledger}_[key] = phase_ + value;", "{ledger}_.erase(chosen.key);", "phase_ += signal; {ledger}_[participant] = phase_;"),
    "idempotency-key-handoff": ("{ledger}_[key] = value;", "{markers}_.insert(chosen.key);", "if (signal < 0) {{ {ledger}_.erase(participant); {markers}_.erase(participant); }}"),
    "two-phase-delivery-slot": ("{ledger}_[key] = 0;", "{ledger}_[chosen.key] = 2;", "{ledger}_[participant] = signal == 0 ? -1 : 1; phase_ += 1;"),
    "lease-renewal-queue": ("{ledger}_[key] = phase_ + value;", "{ledger}_.erase(chosen.key);", "{ledger}_[participant] = phase_ + signal; phase_ += 1;"),
    "nack-classification-router": ("{ledger}_[key] = actor;", "{ledger}_[chosen.key] = participant;", "{ledger}_[participant] = signal; {markers}_.insert(signal);"),
    "exactly-once-commit-table": ("{ledger}_[key] = 0;", "", "for (const auto& item : {aggregate}_) {{ if ({ledger}_.count(item.key) != 0U && {ledger}_.at(item.key) == 1) {{ {markers}_.insert(item.key); }} }} phase_ += 1;"),
    "deduplicating-replay-ledger": ("{ledger}_[key] = phase_;", "", "{ledger}_.erase(participant); {markers}_.erase(participant); ++phase_; for (std::size_t retained_index = {aggregate}_.size(); retained_index > 0U; --retained_index) {{ if ({markers}_.count({aggregate}_[retained_index - 1U].key) == 0U && {ledger}_.count({aggregate}_[retained_index - 1U].key) == 0U) {{ {aggregate}_.erase({aggregate}_.begin() + static_cast<std::ptrdiff_t>(retained_index - 1U)); }} }}"),
    "ownership-transfer-token": ("{ledger}_[key] = actor;", "{ledger}_.erase(chosen.key);", "{ledger}_[participant] = signal; ++phase_;"),
    "tombstone-confirmation-log": ("{ledger}_[key] = 0;", "", "if (signal < 0) {{ {markers}_.erase(participant); }} else {{ {markers}_.insert(participant); }} phase_ += 1;"),
    "compensation-workflow-inbox": ("{ledger}_[key] = actor;", "{ledger}_[chosen.key] = -1;", "if (signal < 0) {{ {markers}_.insert(participant); }} {ledger}_[participant] = signal;"),
    # Batching and frontier protocols.
    "watermark-join-coordinator": ("{ledger}_[actor] = key;", "{ledger}_.erase(chosen.actor);", "{ledger}_[participant] = signal; phase_ = signal;"),
    "dual-threshold-batch-assembler": ("{ledger}_[0] += value; {ledger}_[1] += 1;", "{ledger}_[0] -= chosen.value; {ledger}_[1] -= 1;", "{ledger}_[participant] = signal; phase_ += 1;"),
    "partition-fence-merger": ("{ledger}_[actor] = key;", "{ledger}_[chosen.actor] = chosen.key;", "{ledger}_[participant] = signal; phase_ = std::min(phase_, signal);"),
    "sequence-gap-tolerance-gate": ("{ledger}_[key] = value;", "{ledger}_.erase(chosen.key);", "phase_ = signal; {ledger}_[participant] = signal;"),
    "aggregate-delta-flusher": ("{ledger}_[key] += value;", "{ledger}_.erase(chosen.key);", "{markers}_.insert(participant); phase_ += signal;"),
    "transactional-microbatch-log": ("{ledger}_[actor] += value;", "{ledger}_[chosen.actor] -= chosen.value;", "if (signal < 0) {{ {ledger}_.erase(participant); }} else {{ {markers}_.insert(participant); }}"),
    "checksum-sealed-workset": ("{ledger}_[0] += value; {ledger}_[key] = value;", "{ledger}_.erase(chosen.key);", "sealed_ = signal == {ledger}_[0]; phase_ = signal;"),
    "affinity-cohort-assembler": ("{ledger}_[actor] += value; {markers}_.insert(key);", "{ledger}_[chosen.actor] -= chosen.value; {markers}_.erase(chosen.key);", "{markers}_.insert(participant); phase_ = signal;"),
    "causal-frontier-emitter": ("{ledger}_[actor] = key;", "{ledger}_[chosen.actor] = chosen.key;", "{ledger}_[participant] = signal; ++phase_;"),
    "monotonic-version-release": ("{ledger}_[key] = value;", "{ledger}_.erase(chosen.key);", "{ledger}_[participant] = signal; phase_ = signal;"),
}


def _mechanism_effects(
    case: CaseSpec, aggregate: str, ledger: str, markers: str
) -> tuple[str, str, str]:
    effects = _MECHANISM_EFFECTS[case.task_id]
    return tuple(
        effect.format(aggregate=aggregate, ledger=ledger, markers=markers)
        for effect in effects
    )  # type: ignore[return-value]


# Retention-named protocols keep the released record until their named
# reclamation eligibility holds; every other root erases exactly the selected
# record on release.  Each retention root owns a distinct transition, gate,
# and control flow over its declared state.
_RETENTION_ROOTS = frozenset(
    {
        "consumer-cursor-retention", "quorum-ack-reclaimer",
        "lag-budget-fanout", "snapshot-subscriber-mailbox",
        "topic-mask-fanout", "durable-offset-tracker",
        "slow-reader-evictor", "replay-window-handoff",
        "branch-barrier-delivery", "selective-redelivery-table",
        "exactly-once-commit-table", "deduplicating-replay-ledger",
        "tombstone-confirmation-log",
    }
)

_CURSOR_ROOTS = frozenset(
    {
        "consumer-cursor-retention", "lag-budget-fanout",
        "snapshot-subscriber-mailbox", "topic-mask-fanout",
        "replay-window-handoff",
    }
)

_ERASE_SELECTED = (
    "{aggregate}_.erase({aggregate}_.begin() "
    "+ static_cast<std::ptrdiff_t>(*selected));"
)

_CURSOR_PROLOGUE = (
    "if (consumer_cursors_.count(participant) == 0U) "
    "{ consumer_cursors_[participant] = 0; }"
)

_MIN_CURSOR_RECLAIM = (
    "consumer_cursors_[participant] = chosen.arrival + 1;\n"
    "  int minimum_cursor = consumer_cursors_[participant];\n"
    "  for (const auto& cursor_entry : consumer_cursors_) {{\n"
    "    minimum_cursor = std::min(minimum_cursor, cursor_entry.second);\n"
    "  }}\n"
    "  for (std::size_t retained_index = {aggregate}_.size();"
    " retained_index > 0U; --retained_index) {{\n"
    "    if ({aggregate}_[retained_index - 1U].arrival < minimum_cursor) {{\n"
    "      {aggregate}_.erase({aggregate}_.begin()"
    " + static_cast<std::ptrdiff_t>(retained_index - 1U));\n"
    "    }}\n"
    "  }}"
)

_MASK_RECLAIM_TEMPLATE = (
    "{ledger}_[chosen.key] |= (1 << participant);\n"
    "  {markers}_.insert(participant);\n"
    "  int @MASK@ = 0;\n"
    "  for (const int @MEMBER@ : {markers}_) {{\n"
    "    @MASK@ |= (1 << @MEMBER@);\n"
    "  }}\n"
    "  for (std::size_t retained_index = {aggregate}_.size();"
    " retained_index > 0U; --retained_index) {{\n"
    "    const int @VALUE@ ="
    " {ledger}_.count({aggregate}_[retained_index - 1U].key) != 0U"
    " ? {ledger}_.at({aggregate}_[retained_index - 1U].key) : 0;\n"
    "    if ((@VALUE@ & @MASK@) == @MASK@) {{\n"
    "      {aggregate}_.erase({aggregate}_.begin()"
    " + static_cast<std::ptrdiff_t>(retained_index - 1U));\n"
    "    }}\n"
    "  }}"
)


def _mask_reclaim(mask: str, member: str, value: str) -> str:
    return (
        _MASK_RECLAIM_TEMPLATE.replace("@MASK@", mask)
        .replace("@MEMBER@", member)
        .replace("@VALUE@", value)
    )

_RELEASE_TRANSITIONS = {
    "consumer-cursor-retention": _MIN_CURSOR_RECLAIM,
    "quorum-ack-reclaimer": (
        "{ledger}_[chosen.key] |= (1 << participant);\n"
        "  int acknowledgement_count = 0;\n"
        "  for (int branch_bit = 0; branch_bit < 8; ++branch_bit) {{\n"
        "    if (({ledger}_.at(chosen.key) & (1 << branch_bit)) != 0) {{\n"
        "      acknowledgement_count += 1;\n"
        "    }}\n"
        "  }}\n"
        "  if (acknowledgement_count >= 2) {{\n"
        "    {aggregate}_.erase({aggregate}_.begin()"
        " + static_cast<std::ptrdiff_t>(*selected));\n"
        "  }}"
    ),
    "lag-budget-fanout": (
        "consumer_cursors_[participant] = chosen.arrival + 1;\n"
        "  for (std::size_t retained_index = {aggregate}_.size();"
        " retained_index > 0U; --retained_index) {{\n"
        "    if ({aggregate}_[retained_index - 1U].arrival + phase_"
        " < next_arrival_ - 1) {{\n"
        "      {aggregate}_.erase({aggregate}_.begin()"
        " + static_cast<std::ptrdiff_t>(retained_index - 1U));\n"
        "    }}\n"
        "  }}"
    ),
    "snapshot-subscriber-mailbox": (
        "consumer_cursors_[participant] = chosen.arrival + 1;"
    ),
    "topic-mask-fanout": _MIN_CURSOR_RECLAIM,
    "durable-offset-tracker": (
        "{markers}_.insert(chosen.key);\n"
        "  bool frontier_advanced = true;\n"
        "  while (frontier_advanced) {{\n"
        "    frontier_advanced = false;\n"
        "    for (const auto& item : {aggregate}_) {{\n"
        "      if (item.arrival == commit_frontier_"
        " && {markers}_.count(item.key) != 0U) {{\n"
        "        commit_frontier_ += 1;\n"
        "        frontier_advanced = true;\n"
        "      }}\n"
        "    }}\n"
        "  }}\n"
        "  for (std::size_t retained_index = {aggregate}_.size();"
        " retained_index > 0U; --retained_index) {{\n"
        "    if ({aggregate}_[retained_index - 1U].arrival"
        " < commit_frontier_) {{\n"
        "      {aggregate}_.erase({aggregate}_.begin()"
        " + static_cast<std::ptrdiff_t>(retained_index - 1U));\n"
        "    }}\n"
        "  }}"
    ),
    "slow-reader-evictor": _mask_reclaim(
        "active_reader_mask", "reader", "delivered_mask"
    ),
    "replay-window-handoff": (
        "consumer_cursors_[participant] = chosen.arrival + 1;\n"
        "  int minimum_cursor = consumer_cursors_[participant];\n"
        "  for (const auto& cursor_entry : consumer_cursors_) {{\n"
        "    minimum_cursor = std::min(minimum_cursor, cursor_entry.second);\n"
        "  }}\n"
        "  for (std::size_t retained_index = {aggregate}_.size();"
        " retained_index > 0U; --retained_index) {{\n"
        "    if ({aggregate}_[retained_index - 1U].arrival"
        " < minimum_cursor - phase_) {{\n"
        "      {aggregate}_.erase({aggregate}_.begin()"
        " + static_cast<std::ptrdiff_t>(retained_index - 1U));\n"
        "    }}\n"
        "  }}"
    ),
    "branch-barrier-delivery": _mask_reclaim(
        "branch_barrier_mask", "branch", "branch_deliveries"
    ),
    "selective-redelivery-table": _mask_reclaim(
        "target_delivery_mask", "target_consumer", "consumer_deliveries"
    ),
    "exactly-once-commit-table": (
        "{ledger}_[chosen.key] = 1;\n"
        "  for (std::size_t retained_index = {aggregate}_.size();"
        " retained_index > 0U; --retained_index) {{\n"
        "    if ({markers}_.count({aggregate}_[retained_index - 1U].key)"
        " != 0U) {{\n"
        "      {aggregate}_.erase({aggregate}_.begin()"
        " + static_cast<std::ptrdiff_t>(retained_index - 1U));\n"
        "    }}\n"
        "  }}"
    ),
    "deduplicating-replay-ledger": "{markers}_.insert(chosen.key);",
    "tombstone-confirmation-log": _mask_reclaim(
        "required_confirmation_mask", "required_consumer", "confirmed_mask"
    ),
}

_RELEASE_GATE_OVERRIDES = {
    "consumer-cursor-retention": (
        "chosen.arrival >= consumer_cursors_.at(participant)"
    ),
    "quorum-ack-reclaimer": (
        "{ledger}_.count(chosen.key) != 0U"
        " && ({ledger}_.at(chosen.key) & (1 << participant)) == 0"
    ),
    "lag-budget-fanout": (
        "chosen.arrival >= consumer_cursors_.at(participant)"
    ),
    "snapshot-subscriber-mailbox": (
        "chosen.arrival >= consumer_cursors_.at(participant)"
    ),
    "topic-mask-fanout": (
        "chosen.arrival >= consumer_cursors_.at(participant)"
        " && chosen.actor > 0"
        " && {ledger}_.count(participant) != 0U"
        " && ({ledger}_.at(participant) & (1 << (chosen.actor - 1))) != 0"
    ),
    "durable-offset-tracker": "{markers}_.count(chosen.key) == 0U",
    "slow-reader-evictor": (
        "{ledger}_.count(chosen.key) != 0U"
        " && ({ledger}_.at(chosen.key) & (1 << participant)) == 0"
    ),
    "replay-window-handoff": (
        "chosen.arrival >= consumer_cursors_.at(participant)"
    ),
    "branch-barrier-delivery": (
        "{ledger}_.count(chosen.key) != 0U"
        " && ({ledger}_.at(chosen.key) & (1 << participant)) == 0"
    ),
    "selective-redelivery-table": (
        "{ledger}_.count(chosen.key) != 0U"
        " && ({ledger}_.at(chosen.key) & (1 << participant)) == 0"
    ),
    "exactly-once-commit-table": (
        "{markers}_.count(chosen.key) == 0U"
        " && {ledger}_.count(chosen.key) != 0U"
        " && {ledger}_.at(chosen.key) == 0"
    ),
    "tombstone-confirmation-log": (
        "{ledger}_.count(chosen.key) != 0U"
        " && ({ledger}_.at(chosen.key) & (1 << participant)) == 0"
    ),
}

_RETENTION_RULES = {
    "consumer-cursor-retention": (
        "the minimum active consumer cursor passes it"
    ),
    "quorum-ack-reclaimer": (
        "two distinct consumers have acknowledged it"
    ),
    "lag-budget-fanout": (
        "it falls behind the newest arrival by more than the lag budget"
    ),
    "snapshot-subscriber-mailbox": (
        "its subscriber deregisters; the immutable snapshot is never reclaimed"
    ),
    "topic-mask-fanout": (
        "every consumer cursor has passed it in global admission order"
    ),
    "durable-offset-tracker": (
        "the contiguous acknowledged commit frontier advances past it"
    ),
    "slow-reader-evictor": (
        "every registered reader has received it or been evicted"
    ),
    "replay-window-handoff": (
        "it leaves the bounded replay window behind the minimum cursor"
    ),
    "branch-barrier-delivery": (
        "every registered branch has acknowledged the barrier item"
    ),
    "selective-redelivery-table": (
        "every targeted consumer has taken it without a negative acknowledgement"
    ),
    "exactly-once-commit-table": (
        "its delivery is durably committed; committed records suppress replay"
    ),
    "deduplicating-replay-ledger": (
        "its terminal ledger entry is compacted"
    ),
    "tombstone-confirmation-log": (
        "every required consumer has confirmed the tombstone"
    ),
}

# Expected model-suite outcomes for retention roots: results of four consume
# calls (None means std::nullopt), final retained keys, released history.
# Every other root keeps the default two-release drain shape.
_MODEL_TAILS: dict[str, tuple[list, list, list]] = {
    "consumer-cursor-retention": ([4, 7, None, None], [11, 22], [4, 7]),
    "quorum-ack-reclaimer": ([22, 11, None, None], [11, 22], [22, 11]),
    "lag-budget-fanout": ([11, 22, None, None], [11, 22], [11, 22]),
    "snapshot-subscriber-mailbox": ([1, 2, None, None], [11, 22], [1, 2]),
    "durable-offset-tracker": ([7, 4, None, None], [], [7, 4]),
    "slow-reader-evictor": ([2, 1, None, None], [11, 22], [2, 1]),
    "replay-window-handoff": ([11, 22, None, None], [11, 22], [11, 22]),
    "branch-barrier-delivery": ([4, 7, None, None], [11, 22], [4, 7]),
    "selective-redelivery-table": ([22, 11, None, None], [11, 22], [22, 11]),
    "exactly-once-commit-table": ([7, 4, None, None], [11, 22], [7, 4]),
    "deduplicating-replay-ledger": ([2, 1, None, None], [11, 22], [2, 1]),
    "tombstone-confirmation-log": ([4, 7, None, None], [11, 22], [4, 7]),
}


def _mechanism_gate(
    case: CaseSpec, aggregate: str, ledger: str, markers: str
) -> tuple[str, str, str, str]:
    """Return initializer, admission gate, release gate, and negative target."""
    mode = _mode(case)
    initializer = (
        f"{ledger}_[0] = 0; {ledger}_[1] = static_cast<int>(protocol_limit_ * 4U); "
        f"{ledger}_[2] = static_cast<int>(protocol_limit_ * 4U); phase_ = 10;"
    )
    if case.task_id == "topic-mask-fanout":
        initializer = f"{ledger}_[0] = 3; {ledger}_[1] = 3; {ledger}_[2] = 3; phase_ = 10;"
    admission = {
        "admission": (
            f"{ledger}_[actor] >= value",
            f"{ledger}_[actor] + phase_ >= value",
            f"{markers}_.count(key) == 0U",
            f"{ledger}_[0] + value <= static_cast<int>(protocol_limit_ * 4U)",
            "key >= phase_",
            f"{ledger}_.count(key) == 0U || {markers}_.count(key) != 0U",
            f"{ledger}_[actor] > 0",
            "value <= phase_",
            f"{aggregate}_.size() < static_cast<std::size_t>(phase_)",
            f"{ledger}_[actor] >= value && phase_ > 0",
        ),
        "lifecycle": (
            f"{markers}_.count(actor) == 0U",
            "phase_ >= 0 && !sealed_",
            f"{markers}_.count(actor) == 0U && !sealed_",
            f"{ledger}_[actor] >= 0 && !sealed_",
            f"{ledger}_.count(key) == 0U || {ledger}_[key] == phase_",
            f"{markers}_.count(key) == 0U",
            "!sealed_ && phase_ >= 0",
            f"{markers}_.count(actor) == 0U",
            f"{ledger}_.count(key) == 0U",
            "!sealed_",
        ),
        "fanout": tuple("!sealed_" for _ in range(10)),
        "scheduling": tuple("!sealed_" for _ in range(10)),
        "ownership": (
            f"{ledger}_.count(key) == 0U", f"{markers}_.count(key) == 0U",
            f"{ledger}_.count(key) == 0U", f"{ledger}_.count(key) == 0U",
            f"{markers}_.count(key) == 0U", f"{markers}_.count(key) == 0U",
            f"{markers}_.count(key) == 0U", f"{ledger}_.count(key) == 0U",
            f"{markers}_.count(key) == 0U", f"{markers}_.count(key) == 0U",
        ),
        "batching": tuple("!sealed_" for _ in range(10)),
    }[case.group][mode]
    release = {
        # Every gate reads the protocol's owned state before selection; a record
        # whose admission/lifecycle footprint is absent or ineligible is never
        # released.  Tautological predicates on normal state are forbidden.
        "admission": (
            f"{markers}_.count(chosen.key) != 0U",
            f"{markers}_.count(chosen.actor) != 0U",
            f"{ledger}_.count(chosen.key) != 0U",
            f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) == chosen.value",
            f"{markers}_.count(chosen.key) != 0U",
            f"{ledger}_.count(chosen.key) != 0U",
            f"{markers}_.count(chosen.key) != 0U",
            f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) <= phase_",
            f"{ledger}_.count(chosen.actor) != 0U && {ledger}_.at(chosen.actor) > 0",
            f"{markers}_.count(chosen.key) != 0U",
        ),
        # Lifecycle controls constrain future admission and terminal state, but an
        # accepted prefix remains drainable after a producer/epoch is retired;
        # each gate still requires the record's own lifecycle footprint.
        "lifecycle": (
            f"{ledger}_.count(chosen.actor) != 0U && {ledger}_.at(chosen.actor) > 0",
            f"{ledger}_.count(chosen.aux - chosen.value) != 0U && {ledger}_.at(chosen.aux - chosen.value) > 0",
            "!sealed_",
            f"{ledger}_.count(chosen.actor) != 0U",
            f"!sealed_ && {ledger}_.count(chosen.key) != 0U",
            f"{markers}_.count(chosen.key) != 0U",
            f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) <= phase_",
            f"{ledger}_.count(chosen.actor) != 0U && {ledger}_.at(chosen.actor) > 0",
            f"{ledger}_.count(chosen.key) != 0U",
            f"{ledger}_.count(chosen.actor) != 0U && !sealed_",
        ),
        "fanout": (
            f"{ledger}_.count(participant) != 0U", f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) < 2",
            f"{ledger}_.count(chosen.key) != 0U", f"{markers}_.count(participant) != 0U || {ledger}_.count(participant) != 0U",
            f"chosen.actor > 0 && ({ledger}_[participant] & (1 << (chosen.actor - 1))) != 0",
            f"{ledger}_.count(chosen.key) != 0U", f"{markers}_.count(participant) == 0U",
            f"{ledger}_.count(chosen.key) != 0U", f"{ledger}_.count(chosen.key) != 0U",
            f"{ledger}_.count(chosen.key) != 0U",
        ),
        "scheduling": (
            f"{ledger}_[chosen.actor] + phase_ >= chosen.value",
            f"{ledger}_[chosen.key] <= phase_ + chosen.arrival",
            f"{ledger}_[chosen.actor] > 0",
            f"{ledger}_[chosen.key] <= phase_ + chosen.key",
            f"{markers}_.count(chosen.actor) != 0U",
            f"{ledger}_[chosen.actor] > 0", f"{ledger}_.count(chosen.actor) != 0U",
            f"{ledger}_.count(chosen.key) != 0U", f"{ledger}_.count(chosen.key) != 0U",
            f"{ledger}_[chosen.actor] > 0",
        ),
        "ownership": (
            f"{ledger}_[chosen.key] >= phase_", f"{ledger}_.count(chosen.key) != 0U",
            f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) == 0", f"{ledger}_[chosen.key] >= phase_",
            f"{ledger}_.count(chosen.key) != 0U", f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) == 0",
            f"{markers}_.count(chosen.key) == 0U", f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) == chosen.actor",
            f"{markers}_.count(chosen.key) != 0U", f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) == chosen.actor",
        ),
        "batching": (
            f"{ledger}_[chosen.actor] >= phase_", f"{ledger}_[0] >= chosen.value",
            f"{ledger}_[chosen.actor] >= phase_", "chosen.key <= phase_ + 20",
            f"{ledger}_.count(chosen.key) != 0U", f"{ledger}_[chosen.actor] >= chosen.value",
            f"{ledger}_.count(chosen.key) != 0U && {ledger}_.at(chosen.key) >= chosen.value", f"{ledger}_[chosen.actor] > 0",
            f"chosen.key <= {ledger}_[chosen.actor] + phase_", f"{ledger}_.count(chosen.key) != 0U",
        ),
    }[case.group][mode]
    override = _RELEASE_GATE_OVERRIDES.get(case.task_id)
    if override is not None:
        release = override.format(ledger=ledger, markers=markers)
    target = "admission" if case.group in {"admission", "lifecycle"} else "release"
    return initializer, admission, release, target


def policy(case: CaseSpec) -> ProtocolPolicy:
    mode = _mode(case)
    result, wrong, first, second = _RESULTS[case.group][mode]
    admission = (
        "accept only nonnegative domain values while the protocol is open",
        "coalesce duplicate keys by the protocol's declared ownership rule",
        "apply the declared capacity boundary before mutating owned state",
        "record a monotonic protocol-local admission identity",
    )[mode % 4]
    duplicate = (
        "reject an already-retained key",
        "replace the retained value without moving its position",
        "merge the new amount into the retained value",
    )[mode % 3]
    release = case.mechanism
    control = (
        "advance the protocol frontier",
        "update actor-local allowance state",
        "seal the current protocol generation",
        "retire the addressed participant",
        "rotate the deterministic service turn",
    )[mode % 5]
    return ProtocolPolicy(admission, duplicate, release, control, result, wrong, first, second)


def _snapshot_fields(case: CaseSpec) -> tuple[str, str, str, str, str]:
    words = re.findall(r"[a-z]+", case.task_id)
    while len(words) < 4:
        words.append("protocol")
    return (
        f"{words[0]}_released",
        f"{words[1]}_retained",
        f"{words[2]}_metric",
        f"{words[3]}_phase",
        f"{words[0]}_sealed",
    )


def _extra_state_member(case: CaseSpec, concept: str) -> str:
    if case.task_id in _CURSOR_ROOTS:
        return f"  {concept}LedgerState consumer_cursors_;\n"
    if case.task_id == "durable-offset-tracker":
        return "  int commit_frontier_ = 0;\n"
    return ""


def _extra_snapshot(case: CaseSpec) -> tuple[str, str, str]:
    """Per-root extra snapshot field: (declaration, fill statements, value)."""
    words = re.findall(r"[a-z]+", case.task_id)
    while len(words) < 4:
        words.append("protocol")
    aggregate, ledger, markers, _metric = _state_terms(case)
    task = case.task_id
    if task in _CURSOR_ROOTS:
        return (
            f"  std::vector<int> {words[-1]}_cursors;\n",
            "  std::vector<int> cursor_values;\n"
            "  for (const auto& cursor_entry : consumer_cursors_) {\n"
            "    cursor_values.push_back(cursor_entry.second);\n"
            "  }\n",
            "cursor_values",
        )
    if task == "durable-offset-tracker":
        return (f"  int {words[-1]}_frontier;\n", "", "commit_frontier_")
    if task in {
        "quorum-ack-reclaimer", "slow-reader-evictor",
        "branch-barrier-delivery", "selective-redelivery-table",
        "tombstone-confirmation-log",
    }:
        return (
            f"  std::vector<int> {words[-1]}_acknowledgements;\n",
            "  std::vector<int> acknowledgement_values;\n"
            f"  for (const auto& item : {aggregate}_) {{\n"
            f"    acknowledgement_values.push_back({ledger}_.count(item.key)"
            f" != 0U ? {ledger}_.at(item.key) : 0);\n"
            "  }\n",
            "acknowledgement_values",
        )
    if task == "exactly-once-commit-table":
        return (
            f"  std::vector<int> {words[-1]}_committed;\n",
            f"  std::vector<int> committed_values({markers}_.begin(),"
            f" {markers}_.end());\n",
            "committed_values",
        )
    if task == "deduplicating-replay-ledger":
        return (
            f"  int {words[-1]}_terminal;\n",
            "",
            f"static_cast<int>({markers}_.size())",
        )
    return ("", "", "")


def render_header(case: CaseSpec) -> str:
    cls = _camel(case.task_id)
    concept = _concept(case)
    mode = _mode(case)
    released, retained, metric, phase, sealed = _snapshot_fields(case)
    record_names = {
        "admission": ("Request", "producer", "token", "demand", "reservation"),
        "lifecycle": ("Envelope", "owner", "payload", "generation", "state"),
        "fanout": ("Event", "topic", "payload", "offset", "required"),
        "scheduling": ("Job", "lane", "payload", "cost", "ready_tick"),
        "ownership": ("Delivery", "owner", "payload", "token", "deadline"),
        "batching": ("Item", "partition", "payload", "measure", "version"),
    }[case.group]
    record_base, actor, key, value, aux = record_names
    record = f"{concept}{record_base}"
    aggregate, ledger, markers, protocol_metric = _state_terms(case)
    snapshot_extra = _extra_snapshot(case)[0]
    member_extra = _extra_state_member(case, concept)
    return f"""#pragma once

#include <cstddef>
#include <map>
#include <optional>
#include <set>
#include <vector>

namespace producer_consumer_structures {{

struct {cls}Snapshot {{
  std::vector<int> {released};
  std::vector<int> {retained};
  int {metric};
  int {phase};
  bool {sealed};
{snapshot_extra}}};

struct {concept}Submission {{
  int actor;
  int key;
  int value;
}};

struct {concept}Control {{
  int participant;
  int signal;
}};

class {cls} {{
 public:
  explicit {cls}(std::size_t protocol_limit = {4 + mode}U);
  bool {case.producer_verb}({concept}Submission submission);
  std::optional<int> {case.consumer_verb}(int participant);
  bool {case.lifecycle_verb}({concept}Control control);
  {cls}Snapshot inspect_{_symbol(case.task_id)}() const;

 private:
  using {concept}LedgerState = std::map<int, int>;
  using {concept}MarkerState = std::set<int>;
  struct {record} {{
    int actor;
    int key;
    int value;
    int aux;
    int arrival;
  }};
  std::size_t protocol_limit_;
  std::vector<{record}> {aggregate}_;
  {concept}LedgerState {ledger}_;
  {concept}MarkerState {markers}_;
{member_extra}  std::vector<int> released_values_;
  int {protocol_metric}_ = 0;
  int phase_ = 0;
  int next_arrival_ = 0;
  bool sealed_ = false;
}};

}}  // namespace producer_consumer_structures
"""


def _aux_expression(case: CaseSpec) -> str:
    mode = _mode(case)
    expressions = {
        "admission": ("value", "value - actor", "key", "value", "key", "arrival", "value + actor", "value", "actor", "value"),
        "lifecycle": ("phase_", "phase_ + value", "actor", "phase_ + key", "phase_", "value", "phase_", "actor + phase_", "key", "phase_"),
        "fanout": ("arrival", "value", "arrival - participant_bias", "phase_", "key", "arrival", "value", "arrival", "value", "key"),
        "scheduling": ("value", "phase_ - arrival", "value + actor", "key - phase_", "actor", "key", "arrival", "value", "phase_ + actor", "key"),
        "ownership": ("phase_ + value", "key", "phase_", "value + phase_", "actor", "arrival", "key", "phase_ + actor", "value", "key + phase_"),
        "batching": ("key", "value", "phase_", "key - phase_", "arrival", "phase_ + value", "value", "actor", "key + value", "key"),
    }[case.group]
    return expressions[mode].replace("participant_bias", str(mode + 1))


def render_reference(case: CaseSpec, *, starter: bool = False) -> str:
    cls = _camel(case.task_id)
    concept = _concept(case)
    mode = _mode(case)
    aggregate, ledger, markers, protocol_metric = _state_terms(case)
    record = concept + {
        "admission": "Request", "lifecycle": "Envelope", "fanout": "Event",
        "scheduling": "Job", "ownership": "Delivery", "batching": "Item",
    }[case.group]
    if starter:
        return f"""#include \"{case.task_id}.h\"

namespace producer_consumer_structures {{

{cls}::{cls}(std::size_t protocol_limit) : protocol_limit_(protocol_limit) {{}}
bool {cls}::{case.producer_verb}({concept}Submission) {{ return false; }}
std::optional<int> {cls}::{case.consumer_verb}(int) {{ return std::nullopt; }}
bool {cls}::{case.lifecycle_verb}({concept}Control) {{ return false; }}
{cls}Snapshot {cls}::inspect_{_symbol(case.task_id)}() const {{ return {{}}; }}

}}  // namespace producer_consumer_structures
"""
    selector = _SELECTORS[mode]
    p = policy(case)
    duplicate = (
        f"++{protocol_metric}_; return false;",
        "duplicate->value = value; return true;",
        "duplicate->value += value; duplicate->aux += value; return true;",
    )[mode % 3]
    full = (
        f"++{protocol_metric}_; return false;",
        f"{markers}_.insert({aggregate}_.front().key); {aggregate}_.erase({aggregate}_.begin());",
        f"{markers}_.insert({aggregate}_.back().key); {aggregate}_.pop_back();",
        f"auto victim = std::min_element({aggregate}_.begin(), {aggregate}_.end(), [](const {record}& a, const {record}& b) {{ return a.aux < b.aux; }}); {markers}_.insert(victim->key); {aggregate}_.erase(victim);",
    )[mode % 4]
    admit_effect, release_effect, control = _mechanism_effects(
        case, aggregate, ledger, markers
    )
    initializer, admission_guard, release_guard, _negative_target = (
        _mechanism_gate(case, aggregate, ledger, markers)
    )
    # Eligibility is a per-record property: the guard reads the candidate
    # under inspection, never the previously selected record.
    candidate_guard = release_guard.replace("chosen.", "candidate.")
    result_expression = p.result
    prologue_emit = (
        f"  {_CURSOR_PROLOGUE}\n" if case.task_id in _CURSOR_ROOTS else ""
    )
    release_emit = f"  {release_effect}\n" if release_effect else ""
    transition = _RELEASE_TRANSITIONS.get(
        case.task_id, _ERASE_SELECTED
    ).format(aggregate=aggregate, ledger=ledger, markers=markers)
    _snapshot_decl, snapshot_fill, snapshot_value = _extra_snapshot(case)
    snapshot_init = f", {snapshot_value}" if snapshot_value else ""
    return f"""#include \"{case.task_id}.h\"

#include <algorithm>
#include <stdexcept>

namespace producer_consumer_structures {{

{cls}::{cls}(std::size_t protocol_limit) : protocol_limit_(protocol_limit) {{
  if (protocol_limit == 0U) {{ throw std::invalid_argument("protocol limit must be positive"); }}
  {initializer}
}}

bool {cls}::{case.producer_verb}({concept}Submission submission) {{
  const int actor = submission.actor;
  const int key = submission.key;
  const int value = submission.value;
  if (sealed_ || actor < 0 || key < 0 || value < 0) {{
    ++{protocol_metric}_;
    return false;
  }}
  auto duplicate = std::find_if({aggregate}_.begin(), {aggregate}_.end(),
      [key](const {record}& item) {{ return item.key == key; }});
  if (duplicate != {aggregate}_.end()) {{ {duplicate} }}
  if (!({admission_guard})) {{
    ++{protocol_metric}_;
    return false;
  }}
  if ({aggregate}_.size() >= protocol_limit_) {{ {full} }}
  const int arrival = next_arrival_++;
  const int aux = {_aux_expression(case)};
  {aggregate}_.push_back({{actor, key, value, aux, arrival}});
  {admit_effect}
  return true;
}}

std::optional<int> {cls}::{case.consumer_verb}(int participant) {{
  if (participant < 0 || {aggregate}_.empty()) {{ return std::nullopt; }}
{prologue_emit}  std::optional<std::size_t> selected;
  for (std::size_t index = 0U; index < {aggregate}_.size(); ++index) {{
    const auto& candidate = {aggregate}_[index];
    if (!({candidate_guard})) {{ continue; }}
    const auto& chosen = selected.has_value() ? {aggregate}_[*selected] : candidate;
    if (!selected.has_value() || ({selector})) {{ selected = index; }}
  }}
  if (!selected.has_value()) {{ return std::nullopt; }}
  const auto chosen = {aggregate}_[*selected];
  const int protocol_result = {result_expression};
  released_values_.push_back(protocol_result);
{release_emit}  {transition}
  return protocol_result;
}}

bool {cls}::{case.lifecycle_verb}({concept}Control control) {{
  const int participant = control.participant;
  const int signal = control.signal;
  if (participant < 0 || signal < -1) {{ return false; }}
  {control}
  return true;
}}

{cls}Snapshot {cls}::inspect_{_symbol(case.task_id)}() const {{
  std::vector<int> retained_keys;
  retained_keys.reserve({aggregate}_.size());
  for (const auto& item : {aggregate}_) {{ retained_keys.push_back(item.key); }}
{snapshot_fill}  return {{released_values_, retained_keys, {protocol_metric}_, phase_, sealed_{snapshot_init}}};
}}

}}  // namespace producer_consumer_structures
"""


def render_instructions(case: CaseSpec) -> str:
    cls = _camel(case.task_id)
    concept = _concept(case)
    p = policy(case)
    mode = _mode(case)
    aggregate, ledger, markers, metric = _state_terms(case)
    selection_text = (
        "oldest protocol arrival", "largest protocol auxiliary value with arrival ties",
        "smallest key with arrival ties", "smallest actor with arrival ties",
        "smallest payload with arrival ties", "largest payload with arrival ties",
        "largest actor with arrival ties", "smallest auxiliary value with key ties",
        "smallest phase-rotated actor rank", "newest protocol arrival",
    )[mode]
    if case.task_id in _RETENTION_RULES:
        release_text = (
            "record the release, and retain the record in the protocol's "
            f"owned state until {_RETENTION_RULES[case.task_id]}"
        )
    else:
        release_text = (
            "record the release, update the actor ledger, and erase exactly "
            "that retained record"
        )
    return f"""# {case.task_id}

Implement `{cls}`, the C++17 state machine for **{case.mechanism}**. Its owned
state is {case.state_model}; concretely, the reference maintains protocol-local
{aggregate}, {ledger}, {markers}, and a {metric} counter. These roles are part
of the behavior and must not be replaced by a generic scored queue.

## Contract

`{case.producer_verb}` validates the protocol domain before mutation and must
{p.admission}. For an existing key it must {p.duplicate}. The constructor
rejects a zero protocol limit; negative fields, sealed state, and retired
actors are invalid. Invalid operations increment only the protocol metric.

`{case.consumer_verb}` returns no value for a negative participant or empty
state. Otherwise it applies {case.mechanism}: select the {selection_text},
return `{p.result}`, {release_text}. Ties follow the stated secondary rule.
Eligibility for admission and release is decided from the owned protocol state
before any mutation or selection; an operation whose eligibility predicate
fails is rejected and leaves the retained state and released history
untouched.

`{case.lifecycle_verb}({concept}Control)` rejects a negative participant and
signals below `-1`; otherwise it must {p.control}. In policy mode `{mode}`, a
duplicate uses the explicitly documented rule and a full protocol applies its
declared rejection or replacement transition without inventing another order.

`inspect_{_symbol(case.task_id)}()` exposes released values, retained keys in
physical protocol order, the invalid/rejection metric, current phase, and seal
state through task-specific field names declared in the editable header.

## Implementation constraints

Implement the declared {case.group} protocol directly. Hard-coded traces,
generic score policies, queue/deque adaptors, sleeps, real-time sources, threads,
network access, undefined behavior, and non-C++17 extensions are forbidden.
"""


def _snapshot_field_access(case: CaseSpec) -> tuple[str, str, str, str, str]:
    return _snapshot_fields(case)


def render_test(case: CaseSpec, suite: str) -> str:
    cls = _camel(case.task_id)
    concept = _concept(case)
    mode = _mode(case)
    p = policy(case)
    released, retained, metric, _phase, sealed = _snapshot_field_access(case)
    first = p.expected_first
    second = p.expected_second
    if suite == "visible":
        body = f"""
  assert(!subject.{case.producer_verb}({concept}Submission{{-1, 3, 5}}));
  assert(subject.{case.producer_verb}({concept}Submission{{1, 11, 4}}));
  assert(subject.{case.producer_verb}({concept}Submission{{2, 22, 7}}));
  const auto result = subject.{case.consumer_verb}(1);
  assert(result == {first});
  const auto view = subject.inspect_{_symbol(case.task_id)}();
  assert((view.{released} == std::vector<int>{{{first}}}));
  assert(view.{metric} == 1);
"""
    elif suite == "hidden":
        duplicate_accepts = mode % 3 != 0
        expected_retained = "{11, 22}" if duplicate_accepts else "{11, 22}"
        body = f"""
  assert(subject.{case.producer_verb}({concept}Submission{{1, 11, 4}}));
  assert(subject.{case.producer_verb}({concept}Submission{{2, 22, 7}}));
  assert(subject.{case.producer_verb}({concept}Submission{{1, 11, 3}}) == {'true' if duplicate_accepts else 'false'});
  assert(!subject.{case.consumer_verb}(-1).has_value());
  assert(!subject.{case.lifecycle_verb}({concept}Control{{-1, 2}}));
  const auto view = subject.inspect_{_symbol(case.task_id)}();
  assert((view.{retained} == std::vector<int>{expected_retained}));
  assert(view.{released}.empty());
  assert(view.{metric} == {0 if duplicate_accepts else 1});
"""
    else:
        tail = _MODEL_TAILS.get(case.task_id)
        if tail is None:
            releases: list = [first, second, None, None]
            retained_expected: list = []
            released_expected: list = [first, second]
        else:
            releases, retained_expected, released_expected = tail
        names = ("first", "second", "third", "fourth")
        consume_lines = "".join(
            f"  const auto {name} = subject.{case.consumer_verb}(0);\n"
            for name in names
        )
        assert_lines = "".join(
            f"  assert({name} == {value});\n"
            if value is not None
            else f"  assert(!{name}.has_value());\n"
            for name, value in zip(names, releases)
        )

        def _vec_assert(field: str, values: list) -> str:
            if not values:
                return f"  assert(view.{field}.empty());\n"
            rendered = ", ".join(str(value) for value in values)
            return f"  assert((view.{field} == std::vector<int>{{{rendered}}}));\n"

        body = f"""
  assert(subject.{case.producer_verb}({concept}Submission{{1, 11, 4}}));
  assert(subject.{case.producer_verb}({concept}Submission{{2, 22, 7}}));
  assert(subject.{case.lifecycle_verb}({concept}Control{{1, 3}}));
{consume_lines}{assert_lines}  const auto view = subject.inspect_{_symbol(case.task_id)}();
{_vec_assert(released, released_expected)}{_vec_assert(retained, retained_expected)}  assert(view.{sealed} == {'true' if case.task_id == 'phased-drain-controller' else 'false'});
  const auto final_view = subject.inspect_{_symbol(case.task_id)}();
  assert(final_view.{released} == view.{released});
  assert(final_view.{retained} == view.{retained});
"""
    return f"""#include \"{case.task_id}.h\"

#include <cassert>
#include <stdexcept>
#include <vector>

using namespace producer_consumer_structures;

int main() {{
  // Contract oracle: {case.mechanism}.
  // Owned-state invariant: {case.state_model}.
  bool threw = false;
  try {{ {cls} invalid(0U); }} catch (const std::invalid_argument&) {{ threw = true; }}
  assert(threw);
  {cls} subject({8 + mode}U);{body}
  return 0;
}}
"""


def _reverse_selector(selector: str) -> str:
    """Flip the primary ordering comparison of a release selector."""
    for index, char in enumerate(selector):
        if char == "<":
            return selector[:index] + ">" + selector[index + 1:]
        if char == ">":
            return selector[:index] + "<" + selector[index + 1:]
    raise ValueError(f"selector has no ordering comparison: {selector}")


def negative_mutation(case: CaseSpec) -> dict[str, str]:
    aggregate, ledger, markers, _metric = _state_terms(case)
    _initializer, admission_guard, release_guard, target = _mechanism_gate(
        case, aggregate, ledger, markers
    )
    mode = _mode(case)
    kind = mode % 3
    if kind == 0:
        # Invert the protocol's named eligibility gate (admission for
        # admission/lifecycle roots, release for the others).
        if target == "admission":
            source = f"if (!({admission_guard})) {{"
            replacement = f"if ({admission_guard}) {{"
        else:
            candidate_guard = release_guard.replace("chosen.", "candidate.")
            source = f"if (!({candidate_guard})) {{ continue; }}"
            replacement = f"if ({candidate_guard}) {{ continue; }}"
        name = f"{case.task_id}-wrong-{target}-eligibility-gate"
        invariant = f"{target} eligibility invariant"
    elif kind == 1:
        # Return the documented secondary protocol field instead of the named
        # release payload, violating the release-result contract.
        p = policy(case)
        source = f"const int protocol_result = {p.result};"
        replacement = f"const int protocol_result = {p.wrong_result};"
        name = f"{case.task_id}-wrong-release-payload"
        invariant = "release payload invariant"
    else:
        # Reverse the protocol's documented release ordering rule while
        # preserving the API, gates, and state representation.
        selector = _SELECTORS[mode]
        source = f"if (!selected.has_value() || ({selector})) {{"
        replacement = (
            f"if (!selected.has_value() || ({_reverse_selector(selector)})) {{"
        )
        name = f"{case.task_id}-wrong-release-order"
        invariant = "release ordering invariant"
    return {
        "name": name,
        "mechanism": case.mechanism,
        "from": source,
        "to": replacement,
        "reason": (
            f"preserves {case.state_model} and the public API but violates the "
            f"{invariant} for {case.mechanism}"
        ),
    }


def dimension_claims(case: CaseSpec) -> dict[str, str]:
    p = policy(case)
    return {
        "public_api": f"{case.producer_verb}|{case.consumer_verb}|{case.lifecycle_verb}",
        "owned_state": case.state_model,
        "coordination_algorithm": case.mechanism,
        "mutation_release_rules": f"{p.admission}; {p.duplicate}; {p.control}",
        "invalid_boundary_behavior": "zero limit; negative domain; retired actor; sealed generation",
        "ordering_ties": _SELECTORS[_mode(case)],
        "oracle_negative_fixture": negative_mutation(case)["name"],
    }
