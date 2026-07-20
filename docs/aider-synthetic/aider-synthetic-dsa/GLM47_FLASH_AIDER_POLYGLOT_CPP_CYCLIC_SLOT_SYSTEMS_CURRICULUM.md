# Cyclic Slot Systems Curriculum

Status: `local_family_verified` clean-room 15-root family.

Binding inventory: exactly 15 roots for this remediation, satisfying the
user-specified minimum 15 and maximum 20. Every counted root must differ in
public API, primary state or algorithm, mutation/selection rules, invalid and
boundary behavior, reference control flow, independent deterministic oracle,
and topic-specific negative fixture. A renamed domain, changed constant,
opposite-end choice, or overflow-policy toggle is not a separate root.

## Root inventory

1. `parking-permit-slot-allocator` — modulo first-fit allocation over occupancy
   bits and a search cursor; reject monotone allocation and FIFO storage.
2. `maintenance-duty-wheel` — future-duty buckets advanced tick by tick;
   reject a FIFO delay queue or immediate sorted dispatch.
3. `api-sampling-window-counter` — timestamp-tagged modular aggregate cells;
   reject an untagged ring or stale-cell accumulation.
4. `weighted-service-rotor` — smooth weighted selection using per-lane scores;
   reject plain round robin and expanded repeated-name schedules.
5. `generation-arrival-barrier` — duplicate-safe arrivals with automatic
   generation completion; reject a raw arrival counter.
6. `traffic-phase-controller` — duration-consuming phase transitions with
   residual time; reject one-transition-per-call logic.
7. `circular-signal-convolution` — modular-index numeric convolution; reject
   linear convolution or truncation.
8. `modular-arc-set` — canonical disjoint linear intervals representing
   wraparound arcs; reject a capacity-sized occupancy bitmap.
9. `clockwise-token-router` — ordered token ownership with clockwise wrap;
   reject key modulo token count.
10. `functional-cycle-index` — path-walk decomposition of a functional graph
    into cycle identity, position, and distance; reject reachability-only data.
11. `round-robin-pairing-table` — circle-method tournament rounds, including
    deterministic byes; reject repeated adjacent pairing.
12. `crc-byte-register` — streaming bitwise polynomial remainder; reject an
    additive or XOR-only checksum.
13. `epoch-stamped-sparse-table` — O(1) logical clear with generation stamps
    and explicit epoch-wrap recovery; reject clearing every value on each call.
14. `rotating-bloom-membership` — multi-slice probabilistic membership with
    deterministic hashes and slice rotation; reject an exact set.
15. `serial-replay-window` — wrap-safe 32-bit serial admission with a bounded
    seen bitmap; reject ordinary unsigned ordering or an unbounded set.

These are fifteen different algorithms, not fifteen examples of circular
buffer insertion/removal. None exposes FIFO reads, oldest-item removal,
full-buffer writes, or forced overwrite, and the official `circular-buffer`
root remains a permanent holdout.

## Verification evidence

The owner encodes `MIN_ROOTS=15` and `MAX_ROOTS=20`, materializes exactly the
inventory above, and fails closed outside that range. Fixtures reject counts 14
and 21 while accepting the 15 and 20 boundaries. Stateful roots compare
every operation return plus complete observable ordered state after every trace
operation using an independent oracle. Stateless construction roots compare
the complete result over deterministic generated inputs. Each root has a
source-level rejection fixture for its named false substitute.

The artifact-derived semantic screen reads the emitted prompts, APIs,
references, public tests, and hidden tests while discounting superficial
comments, strings, literals, and clean-room nouns. It compared all 105
unordered root pairs and all 26 bound C++ holdouts. The maximum family overlap
was 0.184049 against the blocking 0.70 threshold. Focused controls rejected a
domain/identifier rename, a constants-or-policy-only clone, and an
opposite-end-selection clone as `duplicate_family`.

All 15 roots passed 2 normal and 2 fresh ASan/UBSan tests in the pinned
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
image with `--network none`. The owner-imported receipt binds the image,
toolchain, command, current generator, task trees, and references. This is
`docker_sanity` evidence with `locked_oracle: false`.

Materialize only beneath:

```text
.w8-biayn/data/aider-tasks-reverify/aider-dsa/circular-buffer/
```

The legacy root remains untouched. This workflow creates local task artifacts
only: no JSONL, dataset admission, training authorization, release, or
benchmark-uplift claim.
