# Clock Arithmetic Family Remediation and Reverification

## Scope and immutable inputs

This audit follows
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with the user inputs
`FAMILY_NAME=clock-arithmetic`,
`FAMILY_TYPE=aider-text-grid-reshaping`, and the authorized hard-rule count
range 8–12. The requested legacy path
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/clock-arithmetic/` does not
exist. The actual owner-generated legacy family is the ten-root tree at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/clock-arithmetic/`; it is the
immutable audit input and is not modified. Fresh owner-generated output goes
only to
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/clock-arithmetic/`.

This is local clean-room remediation. Dataset handoff is `not_requested`.
Nothing here creates JSONL rows, token/mask evidence, a split, release,
training authorization, or benchmark result.

Review date: 2026-07-18. Selected owner:
`src/w8_biayn/integrations/moonlight_clock_arithmetic_aider_tasks.py`.
Focused test: `tests/test_moonlight_clock_arithmetic_aider_tasks.py`.
Wrapper:
`examples/slime/moonlight_cpp_perf/prepare_clock_arithmetic_aider_tasks.sh`.

## Legacy inventory and audit findings

The actual legacy tree contains these ten roots, which satisfy the authorized
8–12 count bound. Hashes use the owner algorithm over relative path, NUL,
file bytes, and NUL, excluding `.state/`:

| Legacy task | Tree hash before | Primary objective | Disposition |
| --- | --- | --- | --- |
| `time-parking-grace-audit` | `sha256:7097b8556c4319a2fe7f26a1d80da39c1b10d2278a3e5ece4e9587e84ac882e8` | One-day interval linearization and grace subtraction | `repair-in-place` |
| `time-rail-transfer-checker` | `sha256:4d51ec99b32d7af10a5db83f8255bdb78aec74d949b7f53ee7dbe2c697108831` | Service-sensitive adjacent layover scan | `repair-in-place` |
| `time-medication-window` | `sha256:9184a1b188f413f506808106324938bcbc4f755008cde77290790e3d4b12420c` | Cyclic window membership and dose-spacing scan | `repair-in-place` |
| `time-overnight-roster` | `sha256:64893b707cdcf1f5ed4a0b38690317ad2ce4b2651c3348bc53f5a7f262c2730d` | Shift segmentation with break and premium overlap | `repair-in-place` |
| `time-irrigation-cycle` | `sha256:39e61b99acc4c46968b00faba047f1c33034e7ad448dfaed54064c92500aad62` | Wrapped blackout normalization and anchor-ordered search | `repair-in-place` |
| `time-backup-cutover` | `sha256:75719da6e2929149e63f99e5d0e93ea7255832bba055016d8b90c59fb8391683` | Four-state transition fold with duration accounting | `repair-in-place` |
| `time-briefing-offset-board` | `sha256:9a0c82ef90490f8d78a9b11461ac4bdc4bbb8deb9730d5693ffd5def28701477` | Stable signed-offset normalization and day classification | `repair-in-place` |
| `time-satellite-phase-log` | `sha256:7b158082649f903775e78a2ad96355047f6dd70b94ca5af52b7011c27d74227e` | Modular fold and shortest signed correction | `repair-in-place` |
| `time-school-bell-repair` | `sha256:5df221bbe07a9d9a29616822f2f43e337415b5352c08c268011b5f8e1168beb0` | Stable-ID change replay and canonical ordering | `repair-in-place` |
| `time-oven-program` | `sha256:31b7f52c08cec9a22e25094e9ffbd18e41286a6e05ef2307bf985e91044c66bb` | Persistent staged-duration state machine | `repair-in-place` |

The legacy references contain ten different core mechanisms rather than a
single noun-renamed implementation. Each objective can be distinguished by a
deterministic topic-specific behavioral error, so deterministic disposition
rules retain all ten IDs as `repair-in-place`. The audit found the following
shared evidence defects:

### CA-F1 — prompt contracts omit necessary public rules

**Severity:** major

**Observed evidence:** Legacy instructions consist mostly of one-sentence
summaries. They omit exact half-open/equality rules, invalid results, collection
ordering, state preservation, and overflow policy that the implementations
implicitly choose.

**Root cause:** The v1 owner treated curriculum summaries as complete task
contracts.

**Remedy:** Emit full per-root contracts covering valid, invalid, duplicate,
absent, empty, mutation, ordering, tie, overflow, and cycle-boundary behavior.

**Verification:** `--verify-core` builds the exact prompt and requires only
docs plus both declared editable files, with every API visible and all private
roles absent.

### CA-F2 — private tests repeat visible behavior

**Severity:** major

**Observed evidence:** Every v1 private executable repeats its visible body and
adds only a tautological loop.

**Root cause:** The hidden-test scaffold was a placeholder rather than an
independent deterministic oracle.

**Remedy:** Replace every private body with root-specific invalid, equality,
wrap, ordering, overflow, and state-preservation cases.

**Verification:** The focused test reads emitted oracle material, and Docker
runs two positive tests per root in both clean normal and fresh ASan/UBSan
modes.

### CA-F3 — no executed topic-specific false substitutes

**Severity:** major

**Observed evidence:** The v1 tree has no strict-compiling deliberately wrong
implementation and no recorded rejection path.

**Root cause:** Verification covered references only.

**Remedy:** Emit one source mutation per root: grace equality, transfer
equality, closed window endpoint, premium during breaks, closed blackout
endpoint, draining-as-serving, exact-day classification, half-period tie,
ID-first ordering, or corrupted completion actions.

**Verification:** Normal and sanitizer builds must compile each substitute
under the same warnings, discover two tests, execute them, and observe failure.

### CA-F4 — no complete seven-dimensional family screen

**Severity:** major

**Observed evidence:** V1 has no 45-pair matrix and no coherent clone controls.

**Root cause:** Distinct IDs and APIs were treated as sufficient diversity
evidence.

**Remedy:** Derive public API, owned state/algorithm, mutation/selection,
invalid/boundary behavior, reference control flow, deterministic oracle, and
topic-negative dimensions from actual emitted files. Compare all 45 unordered
pairs conjunctively. Materialize and compile coherent domain/identifier,
constants/policy, and opposite-end clones; the production evaluator must mark
all seven dimensions duplicate for each control.

**Verification:** Focused tests independently inspect every pair/dimension,
exact counts, nonempty control changes, and production decisions. Docker runs
all three controls in both modes before their semantic rejection can count.

### CA-F5 — no admissible image-bound normal/sanitizer receipt

**Severity:** blocker for `local_family_verified`

**Observed evidence:** V1 `--verify` is host-only, records no test discovery,
does not bind a mounted tree hash, and has no immutable image/network receipt.

**Root cause:** The original owner predates mandatory Docker sanity evidence.

**Remedy:** Archive the exact current tasks and controls deterministically,
mount it read-only in the pinned C++ sanity image with network disabled,
independently recompute every mounted tree hash, and record compiler/CMake,
commands, reference/negative hashes, test counts, and image identity.

**Verification:** Owner `--docker-sanity`; any unavailable Docker/image is
`not_completed`, not a host-derived pass.

### CA-F6 — no bound semantic holdout screen

**Severity:** blocker for semantic admission

**Observed evidence:** V1 provenance asserts separation but no actual 26-root
content/API/source/test comparison exists.

**Root cause:** Holdout separation was declarative.

**Remedy:** Normalize emitted dimensions and all available official C++
holdout content using
`clock-arithmetic-v2-identifier-literal-endpoint-neutral-7gram`, compare all
260 candidate/holdout pairs, and fail closed if the complete bound inventory is
unavailable.

**Verification:** `--verify-core` records 26 holdouts and 260 comparisons;
Docker acceptance requires the screen to pass.

### CA-F7 — requested family type differs from actual legacy owner path

**Severity:** moderate

**Observed evidence:** The user-supplied legacy path under
`aider-text-grid-reshaping` is absent; the v1 owner writes under
`aider-dates-and-clocks`.

**Root cause:** Requested reverify classification and historical grouping do
not match.

**Remedy:** Preserve the actual legacy tree, record both paths in every remedy
record/manifest, refuse writes to either legacy path, and generate only into
the explicitly requested reverify family type.

**Verification:** Focused tests hash the real legacy roots before/after and
assert both legacy targets are immutable.

## V2 public and implementation contract

Every root keeps its v1 public class and task ID, increments to task-spec
revision 2, and uses task-named editable files. Public docs define exact input
domains and deterministic result semantics. References implement their
root-specific mechanism; incidental vectors and algorithms are permitted, but
host time, system time zones, reusable `Clock` value objects, benchmark assets,
hard-coded examples, and another root's algorithm are forbidden substitutes.

Every task root contains docs, a coherent incomplete header/source pair,
complete private reference mapping, a visible executable, an independent
private executable, one strict-compiling false source, provenance/config/test
metadata, and a C++17 CMake recipe. Only docs and `files.solution` enter the
prompt. The target is exactly the two `.meta/example.*` files in declared
solution order.

## Hard-rule and contamination acceptance

The binding count rule is 8–12 and the v2 inventory is exactly ten. All 45
unordered pairs must differ separately in all seven hard dimensions; an
aggregate score cannot pass a pair. The focused regression test independently
checks the dimension set, pair set, every per-dimension decision, actual
normalized artifact inequality, changed control files, and all-seven control
rejection.

The bound official inventory must contain exactly the 26 permanent C++
holdouts. The screen covers emitted docs, API, reference, visible/private
tests, and false substitute. `clock`, `gigasecond`, and `meetup` are called out
as especially relevant permanent holdouts, but no official root receives a
waiver.

## Oracle commands and completion state

Run:

```bash
UV_CACHE_DIR=/tmp/w8-clock-arithmetic-uv \
  uv run pytest -q tests/test_moonlight_clock_arithmetic_aider_tasks.py

bash examples/slime/moonlight_cpp_perf/prepare_clock_arithmetic_aider_tasks.sh \
  --force --verify-core --verify

bash examples/slime/moonlight_cpp_perf/prepare_clock_arithmetic_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

Host `--verify` is iteration evidence and truthfully records missing host CMake
as `not_completed`. Final Docker evidence must use
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with network `none`, two positive equal discoveries for every task and control,
passing references and controls, rejected topic false substitutes, and exact
owner/mounted hash agreement.

## Evidence invalidation and final result

The remediation did not reuse the legacy host-only claim. Every owner,
reference, test, control, and documentation change invalidated earlier proof
through `--force`. Two attempted Docker runs were explicitly rejected rather
than imported: the first exposed a nonterminating oven false substitute and a
strict-warning failure in the roster false substitute; a later run exposed an
incoherent legacy rail fixture; another rejected an internally inconsistent
constants-policy clone. Each root cause was corrected in the owner, all prior
receipts remained absent/stale, and the complete evidence ladder restarted.

Final owner-controlled evidence after the documentation-bound rerun:

- family status: `local_family_verified`;
- family tree hash:
  `sha256:6e28ff3fa9e626f6711c6af2824b1739fdb613e42bbbc15582818f10744c414e`;
- owner hash:
  `sha256:d1b068c7f4a468e707a6dc11f411d7ab9a02717a88f17dac05c9e5eb613ec4d3`;
- receipt hash:
  `sha256:fb60ffe6b357aaa3ad2ed1723349f7dc4ebfe07bc61b8ffbf28219ffcffdff3a`;
- image ID:
  `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`;
- toolchain: `/usr/local/bin/g++`, GCC 13.4.0, compiler hash
  `sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
  CMake 3.25.1;
- exact 10-root inventory inside the authorized 8–12 bound, all 45 unordered
  pairs passing all seven dimensions;
- all three adversarial controls changed emitted files, compiled, passed two
  normal and two sanitizer tests, matched mounted hashes, and were rejected by
  all seven production decisions;
- every root passed two normal and two fresh sanitizer discoveries, and its
  strict-compiling topic false substitute was rejected in both modes;
- prompt boundary and reference mapping: pass;
- benchmark screen: 26 holdouts, 260 comparisons, pass;
- evidence class: `docker_sanity`; `locked_oracle=false`; network `none`;
- host iteration: `not_completed` because host CMake is unavailable; it is not
  used to support the final status;
- dataset handoff: `not_requested`.

The owner-generated `.state/materialization-manifest.json`, all ten reopened
remedy records/specifications, and `.state/docker-sanity.json` bind the exact
per-root after hashes, control hashes, reference/negative hashes, commands,
counts, and final status. This is the strongest truthful local conclusion; it
is not a dataset-release, training, locked-oracle, or benchmark-uplift claim.
