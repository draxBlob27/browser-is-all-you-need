# Sliding-Window Maximum Family Reverification Audit

## Scope

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
with `FAMILY_NAME=sliding-window-maximum` and `FAMILY_TYPE=aider-dsa`. The
legacy family at `.w8-biayn/data/aider-tasks/aider-dsa/sliding-window-maximum`
is immutable audit input. The owner writes fresh replacements only beneath
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/sliding-window-maximum`. Dataset
handoff is `not_requested`.

## Frozen legacy findings

### SWM-F1-template-semantic-duplicate — major

**Scope:** all 20 legacy roots.

**Observed evidence:** one six-flag `TaskSpec` template generated every public
API, starter, reference, visible test, hidden test, and instruction. Every
reference owned the same `active_` and `candidates_` deques and ran the same
accept, monotonic-back-pop, front-expiry, and front-report flow. Root-specific
variation was limited to nouns, method names, count versus timestamp expiry,
earliest versus latest equal ties, and an optional threshold accessor.

**Why it matters:** these are renamed or policy-parameterized copies, not 20
independent implementation learning objectives.

**Root cause:** the legacy owner encoded domain labels as curriculum diversity
while retaining one authoritative state model and algorithm.

**Remedy:** `replace` every root with a new ID and one-to-one API, owned state,
algorithm, boundary behavior, and private discriminator.

**Verification after remedy:** owner `--verify-core` must compare all 190
unordered replacement pairs and execute the rename, constants/policy, opposite
end, and missing-mechanism controls.

**Status:** resolved and reverified.

### SWM-F2-objective-mechanism-collapse — major

The legacy curriculum promised missing-segment behavior, timestamp horizons,
alert policies, and different stream domains, but the implementation reduced
all roots to one monotonic deque. Each replacement must implement and test the
mechanism named below rather than merely returning a correct maximum.

### SWM-F3-oracle-evidence-stale — blocker

Legacy host builds cannot prove rewritten roots. Regeneration invalidates all
old tree hashes. Fresh, network-disabled Docker normal and ASan/UBSan builds
with positive equal discovery counts are mandatory. Until their receipt
passes, the family cannot be called `local_family_verified`.

## Per-root disposition and mechanism

| Legacy root | Replacement root | Disposition | Substantive mechanism |
| --- | --- | --- | --- |
| `swmax-stock-peaks` | `trade-tick-monotonic-peak` | replace | count deque, latest equal argmax |
| `swmax-temperature-alerts` | `thermal-duration-earliest-peak` | replace | timestamp deque, earliest equal argmax |
| `swmax-network-latency` | `latency-two-stack-max-queue` | replace | two-stack aggregate FIFO |
| `swmax-cpu-bursts` | `cpu-block-prefix-suffix-peaks` | replace | offline prefix/suffix blocks |
| `swmax-power-demand` | `demand-lazy-heap-window` | replace | indexed lazy-expiry max heap |
| `swmax-heart-rate` | `heart-rate-frequency-window` | replace | bounded frequency buckets |
| `swmax-wind-gusts` | `gust-circular-segment-tree` | replace | circular point-update segment tree |
| `swmax-video-bitrate` | `bitrate-gap-reset-peaks` | replace | optional-gap reset deque |
| `swmax-warehouse-throughput` | `warehouse-sqrt-range-peak` | replace | mutable square-root decomposition |
| `swmax-game-score-streak` | `score-sparse-table-queries` | replace | immutable sparse table RMQ |
| `swmax-web-traffic` | `traffic-tournament-ring` | replace | overwrite tournament tree |
| `swmax-log-severity` | `severity-bitmask-window` | replace | multiplicity table plus 64-bit mask |
| `swmax-machine-vibration` | `vibration-treap-window` | replace | owned deterministic-priority treap |
| `swmax-route-speed` | `route-next-greater-window` | replace | offline next-greater jump chain |
| `swmax-battery-drain` | `drain-top-two-aggregate-queue` | replace | top-two aggregate queue monoid |
| `swmax-auction-bids` | `auction-avl-bid-window` | replace | owned AVL multiset with expiry |
| `swmax-support-load` | `support-variable-width-peaks` | replace | monotone externally supplied left bounds |
| `swmax-production-defects` | `defect-grid-window-max` | replace | separable two-dimensional deque passes |
| `swmax-rainfall` | `rainfall-generation-time-wheel` | replace | generation-stamped time wheel |
| `swmax-delivery-delay` | `delivery-persistent-peak-snapshots` | replace | persistent segment-tree prefixes |

## Acceptance contract

- Exactly the 20 replacement IDs above are generated; the legacy tree is not
  changed.
- Prompt construction exposes only docs and the two declared editable files.
  References, tests, metadata, CMake, manifests, and receipts remain private.
- Every reference maps to exactly one editable file by suffix and solution
  order.
- Every replacement differs in normalized public API, state/algorithm/control
  flow, mutation/selection behavior, invalid/boundary behavior, deterministic
  oracle, and topic-specific negative fixture. The owner records all seven
  emitted-artifact dimension hashes for every one of the 190 unordered pairs.
- Stateful APIs have deterministic model traces that invoke every public
  operation and compare the complete observable state after each mutation.
- Every root emits a private topic-specific false substitute. The substitute
  is excluded from prompt roles and family similarity input, compiles with the
  same strict flags, discovers the same two tests, and must be rejected by the
  executed CTest suite.
- The complete all-pairs family comparison rejects semantic containment at or
  above the owner threshold. Emitted renamed-domain, constants/policy-only,
  and opposite-end clones fail with `duplicate_family`; a missing mechanism
  fails with `invariant_not_enforced`.
- Public API, reference, visible tests, and hidden tests are screened against
  all 26 bound official Aider C++ roots.
- The deterministic current-tree archive passes two discovered CTest targets
  per root in both clean normal and fresh ASan/UBSan modes inside the pinned
  repository sanity image with `--network none`. The container independently
  recomputes every task-tree digest with the owner's path/NUL/content/NUL
  algorithm and binds the resolved compiler path, version, and binary hash.
  This is `docker_sanity`, not a family-designated `locked_oracle` claim.

## Owner paths

- `src/w8_biayn/integrations/moonlight_sliding_window_maximum_aider_tasks.py`
- `src/w8_biayn/integrations/moonlight_sliding_window_maximum_cases.py`
- `src/w8_biayn/integrations/moonlight_sliding_window_maximum_hard_rule.py`
- `tests/test_moonlight_sliding_window_maximum_aider_tasks.py`
- `examples/slime/moonlight_cpp_perf/prepare_sliding_window_maximum_aider_tasks.sh`
- the sliding-window curriculum and this audit/specification

## Evidence ledger

The generator writes per-root planned remedy specifications and records before
materializing task files. `--verify-core` adds current tree hashes, owner
identity, prompt/reference/family/benchmark outcomes, and semantic evidence.
`--verify-core` leaves the family at `pending_execution`. `--verify-docker` may
advance a root to `local_family_verified` only after the archive-mounted
normal/sanitizer references and all 20 compiling false substitutes have the
required outcomes. Exact hashes and results are recorded under the
re-verification root's `.state/`.

The earlier v2 receipt and `local_family_verified` claim were withdrawn during
the hard-rule audit because they had only in-memory clone probes, no compiled
per-root false substitutes, incomplete stateful traces, and only an archive
SHA check inside the container. None of that evidence is reused by the v3
receipt below.

## Conclusion

All 20 primary core objectives are achieved and every local-family gate passes.
No part of this work creates dataset rows, authorizes training, or claims
benchmark uplift.

## Commands and exact results

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q tests/test_moonlight_sliding_window_maximum_aider_tasks.py tests/test_aider_sft_scope_docs.py`: 12 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...`: passed for the owner, cases, hard-rule fixtures, and focused tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -m w8_biayn.integrations.moonlight_sliding_window_maximum_aider_tasks --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/sliding-window-maximum --force --verify-docker`: passed in `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991` with Docker network `none` and CMake/CTest 3.25.1. All 20 references passed 40 normal and 40 fresh ASan/UBSan tests. All 20 false substitutes compiled strictly, discovered 40 tests, executed them, and were rejected (CTest return code 8 for every root).
- Legacy family aggregate hash immediately before and after final regeneration: `sha256:a48e2bd182b35fd7ee09df0cbe3355598bf41dcb79486acde4b13ce4ae20d8ea`; the owner never writes to that tree.
- Emitted-family screen: 190/190 unordered pairs compared and all seven normalized dimension hashes differ for every pair. Strongest normalized containment is `0.766971` (`auction-avl-bid-window` versus `vibration-treap-window`), below the `0.78` rejection threshold.
- Official-holdout screen: all 26 roots compared; inventory `sha256:0bfd7652d3c810728b181f9b47cee8d79472b77a853437fe8da528f3be1a291d`; strongest containment `0.134576` (`latency-two-stack-max-queue` versus `bank-account`), below `0.60`.

## Final receipt and owner identity

- Materialization manifest: `.state/materialization-manifest.json`, SHA-256 `2cb955038bcd57ad1bb7e0173253d2cf4c2476a2784e45369667f2736b42537d`.
- Docker sanity receipt: `.state/oracle-receipt.json`, SHA-256 `e591f8e288c4182f7575c1091afa0d557f971b38834ece7f67c9a515d6b6bce8`.
- Deterministic Docker-mounted archive: `sha256:ce53224eeb15789c9e160a01e244d3d2d1db06379a0ab994ee69dbd8cc85ae30`; its archive SHA and all 20 independently recomputed task-tree hashes matched owner values.
- Compiler identity: `/usr/local/bin/c++`; `c++ (GCC) 13.4.0`; binary `sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`.
- Owner SHA-256: `6cecbc0381a0c66ae4d7294b0c4a30e035ac2f6ccd205a3aeccc6511f454253c`; cases SHA-256: `df4f86fd990b80a5609c84552ffd8a986ec1318d6c5c411b7828f3870e4daef4`; hard-rule fixtures SHA-256: `d9d4ab341e32c65c255d2bf993a9b47b3fc3a106103da4f8b951d125bd81c85f`; focused-test SHA-256: `d2451eca3925f1b5bce11081ff6f8e6a8a8409ada7e164c4842e80b22c92bb9e`.
- Evidence class: `docker_sanity`; `locked_oracle: false`. This family has no separately designated locked grader, so the repository-pinned sanity image is the strongest truthful evidence.

## Per-root evidence ledger

Full SHA-256 values, negative outcomes, and receipt bindings live in the
generated manifest, remedy records, and oracle receipt. Each of the 20 roots is
`local_family_verified`; the receipt records its tree hash, reference hash,
normal/sanitizer counts, negative-fixture compile outcome, rejection return
code, and negative log hash.
