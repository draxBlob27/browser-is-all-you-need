"""Declarative inventory for the lifecycle/rollback expansion family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RollbackProtocol:
    key: str
    task_prefix: str
    title: str
    query: str
    query_type: str
    private_fields: tuple[str, ...]
    mechanism: str
    mutation_rule: str
    invalid_rule: str
    control_flow: str
    oracle_rule: str
    negative_fault: str


@dataclass(frozen=True)
class LifecycleTopology:
    key: str
    task_suffix: str
    title: str
    query: str
    query_type: str
    private_fields: tuple[str, ...]
    mechanism: str
    mutation_rule: str
    invalid_rule: str
    control_flow: str
    oracle_rule: str
    valid_events: tuple[tuple[int, int, int], ...]
    invalid_events: tuple[tuple[int, int, int], ...]
    expected_query: int


@dataclass(frozen=True)
class LifecycleTask:
    task_id: str
    namespace: str
    class_name: str
    protocol: RollbackProtocol
    topology: LifecycleTopology
    strategy_index: int
    topology_index: int
    seed: int


PROTOCOLS = (
    RollbackProtocol(
        "snapshot", "snapshot", "atomic snapshot", "snapshot_restores", "std::size_t",
        ("std::size_t snapshot_restores_{0U};",),
        "one exact entry-state value snapshot",
        "copy once before replay; restore the copy after the first rejected event",
        "a rejected event restores topology state and increments the restore receipt",
        "single entry copy, forward replay, guarded restore branch",
        "compare the complete pre/post View and the restore receipt",
        "keeps the accepted prefix instead of assigning the entry snapshot",
    ),
    RollbackProtocol(
        "inverse", "inverse", "inverse compensation", "compensation_count", "std::size_t",
        ("std::vector<InverseRecord> inverse_log_{};", "std::size_t compensation_count_{0U};"),
        "reverse-ordered inverse records for accepted events",
        "derive a topology-specific inverse only after acceptance and execute inverses in reverse",
        "failure runs one compensation for every accepted event",
        "per-event capture loop followed by a reverse iterator unwind",
        "compare each reverse compensation and the cumulative compensation count",
        "returns on failure without executing the reverse compensation sequence",
    ),
    RollbackProtocol(
        "savepoint", "savepoint", "named savepoint", "savepoint_count", "std::size_t",
        (
            "std::map<std::size_t, View> savepoints_{};",
            "std::size_t next_savepoint_token_{1U};",
            "std::size_t last_savepoint_token_{0U};",
        ),
        "monotone transaction-local named savepoint stack",
        "push the entry View, replay, restore the named top, then consume it",
        "success and failure both consume the transaction savepoint",
        "push, indexed top lookup, conditional restore, pop",
        "assert zero active savepoints after both terminal paths",
        "forgets to restore the top savepoint before consuming it",
    ),
    RollbackProtocol(
        "nested", "nested", "nested transaction frames", "frame_depth", "std::size_t",
        ("std::vector<View> frames_{};",),
        "one outer frame plus one short-lived child frame per event",
        "merge each successful child frame; failure restores the outer frame",
        "no frame remains observable after a batch terminates",
        "outer push, repeated child push/pop, outer restore-or-merge",
        "assert child-frame balance and exact outer restoration",
        "pops the failing child and outer frames without restoring the outer View",
    ),
    RollbackProtocol(
        "wal", "wal", "write-ahead validation journal", "journal_size", "std::size_t",
        ("std::vector<Event> journal_{};",),
        "private write-ahead event journal plus validation replay state",
        "validate the whole journal on an isolated state before live replay",
        "an invalid journal clears without mutating live topology state",
        "journal assignment, isolated validation pass, second live commit pass",
        "compare live state before validation and after committed replay",
        "replays directly into live state before all journal records validate",
    ),
    RollbackProtocol(
        "cow", "cow", "copy-on-write shadow", "shadow_commits", "std::size_t",
        ("std::size_t shadow_commits_{0U};",),
        "isolated topology shadow committed by one View replacement",
        "apply every event to a shadow Machine and publish only its final View",
        "failure discards the shadow and leaves the live object byte-equivalent by View",
        "object clone, shadow-only replay, single restore_view publish",
        "assert one publish receipt only for successful shadows",
        "mutates the live object rather than the shadow during speculative replay",
    ),
    RollbackProtocol(
        "version", "version", "persistent version chain", "version_count", "std::size_t",
        ("std::vector<View> versions_{};",),
        "append-only immutable View versions with entry-index truncation",
        "append after each event; truncate to the entry version on failure",
        "failed batches retain neither partial versions nor partial topology state",
        "entry index, append loop, resize and restore from retained tail",
        "compare every appended View and exact post-failure chain length",
        "leaves partial versions and the final accepted-prefix state in the chain",
    ),
    RollbackProtocol(
        "undo", "undo", "field undo log", "undo_records", "std::size_t",
        ("std::vector<UndoRecord> undo_log_{};",),
        "pre-mutation field-state undo records",
        "record immediately before each mutation and restore the earliest entry on failure",
        "the temporary undo log is empty after commit or rollback",
        "pre-event append, guarded mutation, reverse erase and entry restore",
        "assert log lifetime and field-exact rollback after every mixed batch",
        "clears undo records on failure without applying their saved field state",
    ),
    RollbackProtocol(
        "saga", "saga", "saga compensation stack", "compensations_run", "std::size_t",
        ("std::vector<Compensation> compensations_{};", "std::size_t compensations_run_{0U};"),
        "topology-specific compensation stack",
        "push a compensation after acceptance and execute compensations newest first",
        "failure runs and counts every required compensation before clearing the stack",
        "accept, push, reverse compensation while-loop, clear",
        "compare intermediate reversed Views and cumulative executed compensations",
        "drops compensation actions instead of executing them on a later failure",
    ),
    RollbackProtocol(
        "epoch", "epoch", "epoch checkpoint", "generation", "std::size_t",
        ("std::map<std::size_t, View> checkpoints_{};", "std::size_t generation_{0U};"),
        "generation-fenced checkpoint map",
        "bind entry View to current generation, restore/erase it, then advance generation",
        "every terminal path invalidates its checkpoint token by advancing generation",
        "generation-key insert, replay, keyed restore-or-commit erase, fence increment",
        "assert topology restoration and stale-token generation advancement",
        "advances the fence but omits the checkpoint restoration",
    ),
)


TOPOLOGIES = (
    LifecycleTopology(
        "linear", "linear-lifecycle", "linear guarded lifecycle", "phase", "int",
        ("int phase_{0};",),
        "single terminal four-phase guarded chain",
        "only action phase+1 advances one step",
        "nonzero key/value, skipped/duplicate action, and post-terminal action reject",
        "range guard followed by equality guard and one increment",
        "scalar phase model checked after each caller-ordered batch",
        ((0, 1, 0), (0, 2, 0), (0, 3, 0)),
        ((0, 1, 0), (0, 3, 0)),
        3,
    ),
    LifecycleTopology(
        "branch", "branch-lifecycle", "branch approval lifecycle", "decision", "int",
        ("int branch_stage_{0};", "int decision_{0};"),
        "dormant/open/approved-or-rejected branch state",
        "open once, then select positive approval or negative rejection",
        "terminal changes, zero decision, and decisions before open reject",
        "stage dispatch with sign-sensitive mutually exclusive terminal branches",
        "two-field stage/decision oracle with terminal immutability",
        ((0, 1, 0), (0, 2, 5)),
        ((0, 1, 0), (0, 2, 0)),
        1,
    ),
    LifecycleTopology(
        "cyclic", "cyclic-lifecycle", "bounded cyclic retry lifecycle", "retry_count", "int",
        ("int cycle_stage_{0};", "int retries_{0};"),
        "start/fail/retry cycle with bounded retry history",
        "three ordered actions return to idle and increment retry count",
        "wrong stage and retry count beyond three reject",
        "three-way stage dispatch with bounded counter and reset edge",
        "pair model checks stage and retries through repeated cycles",
        ((0, 1, 0), (0, 2, 0), (0, 3, 0)),
        ((0, 1, 0), (0, 3, 0)),
        1,
    ),
    LifecycleTopology(
        "fork_join", "fork-join-lifecycle", "three-way fork and join lifecycle", "arrivals", "std::size_t",
        ("unsigned arrival_mask_{0U};", "bool joined_{false};"),
        "three distinct arrival bits plus a terminal join",
        "unordered unique arrivals set bits; join requires mask seven",
        "duplicate/range arrival and early or repeated join reject",
        "action split, bit-range guard, mask update, all-bits join guard",
        "set oracle compares canonical arrival keys and joined flag",
        ((0, 1, 0), (1, 1, 0), (2, 1, 0), (0, 2, 0)),
        ((0, 1, 0), (0, 1, 0)),
        3,
    ),
    LifecycleTopology(
        "keyed", "keyed-lifecycle", "keyed instance lifecycle", "instance_count", "std::size_t",
        ("std::map<int, int> instances_{};",),
        "positive-key create/advance/close state map",
        "create stage zero, advance to one, close to two",
        "duplicate create, absent transition, and post-close transition reject",
        "map lookup dispatch with per-key stage guards",
        "ascending key/stage vector model after every operation",
        ((4, 1, 0), (4, 2, 0), (4, 3, 0), (2, 1, 0)),
        ((4, 1, 0), (4, 1, 0)),
        2,
    ),
    LifecycleTopology(
        "dependency", "dependency-lifecycle", "dependency activation lifecycle", "active_nodes", "std::size_t",
        ("unsigned active_mask_{0U};",),
        "four-node prerequisite activation graph",
        "activate node zero, independent nodes one/two, then join node three",
        "duplicate/range activation and unmet prerequisite reject",
        "node dispatch computes prerequisite mask then sets one bit",
        "bitset oracle checks all prerequisite-closed active subsets",
        ((0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0)),
        ((0, 1, 0), (3, 1, 0)),
        4,
    ),
    LifecycleTopology(
        "quota", "quota-lifecycle", "quota reservation lifecycle", "available", "int",
        ("int available_{10};", "std::map<int, int> reservations_{};"),
        "capacity ten with keyed open/committed reservations",
        "reserve subtracts, commit negates ownership, release restores and erases",
        "duplicate/absent/nonpositive/over-capacity operation rejects",
        "action dispatch with checked arithmetic and map mutation",
        "ascending reservation map plus available-total conservation oracle",
        ((7, 1, 3), (7, 2, 0)),
        ((7, 1, 3), (7, 1, 2)),
        7,
    ),
)


def all_tasks() -> tuple[LifecycleTask, ...]:
    tasks: list[LifecycleTask] = []
    for strategy_index, protocol in enumerate(PROTOCOLS):
        for topology_index, topology in enumerate(TOPOLOGIES):
            task_id = f"{protocol.task_prefix}-{topology.task_suffix}"
            tasks.append(
                LifecycleTask(
                    task_id=task_id,
                    namespace=task_id.replace("-", "_"),
                    class_name="Machine",
                    protocol=protocol,
                    topology=topology,
                    strategy_index=strategy_index,
                    topology_index=topology_index,
                    seed=0x4C524200 + strategy_index * 17 + topology_index,
                )
            )
    return tuple(tasks)


TASKS = all_tasks()
