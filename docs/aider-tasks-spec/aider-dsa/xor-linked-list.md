# XOR-Linked-List Family Remediation Specification

## Scope and immutable inputs

This report controls local remediation of the 20 generated roots at
`.w8-biayn/data/aider-tasks/aider-dsa/xor-linked-list/`. The legacy tree is
immutable audit input. The owning materializer is
`src/w8_biayn/integrations/moonlight_xor_linked_list_aider_tasks.py`; new roots
are written only beneath
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/xor-linked-list/`.

The selected prompt is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`, with
`FAMILY_NAME=xor-linked-list` and `FAMILY_TYPE=aider-dsa`. The official Aider
C++ `linked-list` root is a permanent holdout. This is local remediation only:
no dataset row, split, token/mask artifact, export, training run, or uplift
claim is authorized.

## Legacy audit

The legacy family has role-correct Aider-shaped roots and prompt boundaries.
Each reference genuinely owns an integer-slot arena and recovers traversal as
`previous_slot XOR current.link`, so the primary representation is present.
However, the owner rendered one common add/remove/move API, implementation,
invalid-input policy, and test trace under 20 domain nouns. Seventeen roots
normalize to one exact reference/test template after class and verb removal;
the remaining differences are only endpoint wrapping or textual parameter
spelling. The host has `c++` but no `cmake`, so the legacy owner verifier was
recorded `not_completed`; no locked receipt exists for the legacy roots.

### XOR-F1 — semantic template duplication

**Severity:** major

**Scope:** every legacy root.

**Observed evidence:** `_ROWS` selected nouns and method names while the same
`_header`, `_reference`, `_starter`, and `_test` renderers supplied all core
logic. Every root exposed stable-handle append/remove/move plus forward/reverse
snapshots; only `xor-card-game-turns` added endpoint wrapping.

**Why it matters:** one solution transfers mechanically across the family, so
the domain labels do not provide independent learning value.

**Root cause:** curriculum blurbs were never bound to executable task-specific
contracts or a family semantic screen.

**Remedy:** repair the lexicographically smallest independently justifiable
representative, `xor-card-game-turns`, in place. Replace each of the other 19
roots with a new ID, public API, state transition, algorithm, tests, and logic
tag. Rename-only retention is forbidden.

**Verification after remedy:** the owner compares emitted documentation, API,
reference control flow, and assertions for all 190 unordered family pairs and
all available remediated DSA roots. It must reject a renamed template at
`duplicate_family`.

**Status:** v2 evidence invalidated; v3 remediation pending.

### XOR-F2 — claimed domain behavior absent

**Severity:** major

**Scope:** all roots except the narrow generic behavior actually exercised by
the old mutation template.

**Observed evidence:** blurbs promised pruning, bounded retention, dependency
readiness, range reversal, priority dispatch, weighted rotation, checkpoints,
and offset lookup, but the public APIs and tests contained none of those state
transitions.

**Why it matters:** a passing build established only the generic XOR chain,
not the task advertised to a model.

**Root cause:** no one-to-one contract registry or topic-specific private
oracle existed.

**Remedy:** each counted v3 case has a complete visible API, only the payload
and class state required by its own algorithm, a task-specific implementation,
an independent deterministic state-machine oracle, and a compiled false
substitute. Shared emitted code is limited to the safe XOR-slot mechanics.

**Verification after remedy:** `--verify-core` must report
`primary_core_objective=achieved`, the counted inventory, every per-operation
trace, every compiled false-substitute rejection, and passing prompt/role
screens.

**Status:** v2 evidence invalidated; v3 remediation pending.

### XOR-F3 — missing reproducible oracle and semantic receipts

**Severity:** moderate

**Scope:** all 20 roots.

**Observed evidence:** the legacy owner performed host builds but produced no
tree-bound positive discovery counts, fresh ASan/UBSan counts, immutable image
identity, prompt hashes, negative-fixture receipt, or benchmark semantic screen.

**Why it matters:** structural inspection and a host build cannot establish
the mandatory Docker sanity gate or `local_family_verified`.

**Root cause:** the family predates the deterministic remediation contract.

**Remedy:** run the exact generated tree in the pinned network-disabled C++
image with explicit Unix Makefiles, normal and fresh ASan/UBSan builds, three
positive CTest entries in each mode, plus a compiled task-specific false
substitute that must execute the same tests and fail. Receipts bind owner,
reference and negative-source hashes, tree, toolchain, image, commands,
negative outcome, and network policy.

**Verification after remedy:** every per-root receipt and the summary must have
equal positive counts and hashes matching the live generated roots. Missing
Docker access or image identity remains `not_completed`.

**Status:** determined only by generated receipts.

### XOR-F4 — v2 hard-diversity evidence was insufficient

**Severity:** blocking

**Scope:** the v2 counted family and its `local_family_verified` claim.

**Observed evidence:** v2 compared all pairs with one aggregate token score but
did not exercise the mandatory renamed-clone, constants/policy-only clone, and
opposite-end clone controls. Its emitted roots shared a superset payload node
and generic reference core, its hidden tests audited structure only after the
trace, and its two negative fixtures were source-string checks rather than
compiled substitutes rejected by the task tests.

**Why it matters:** passing compilation and an aggregate similarity threshold
cannot establish material differences in public contract, necessary state or
algorithm, mutation/selection behavior, invalid boundaries, control flow,
oracle, and negative fixture.

**Root cause:** the v2 owner treated unique logic tags and a below-threshold
whole-task score as diversity evidence instead of deriving each hard-rule
dimension from emitted files and executing adversarial controls.

**Remedy:** v3 rejects the three semantic twins identified by the re-audit,
specializes node payload/state for every counted root, extracts hard-rule
surfaces from emitted docs, headers, reference source, boundary tests,
per-operation traces, and false substitutes, and compares every unordered pair
dimension by dimension. The production pair screen must reject all three
mandatory adversarial controls in focused tests.

**Verification after remedy:** `family-screen.json` records the exact pair
count, per-dimension strongest pairs, count bounds, and adversarial-control
results. No runtime receipt can promote the family unless that receipt is
`pass` and all compiled negative substitutes execute and fail.

**Status:** pending v3 regeneration and execution.

## Remediated inventory and dispositions

| Legacy root | Disposition | Remediated root | Independent core logic |
| --- | --- | --- | --- |
| `xor-card-game-turns` | repair-in-place | `xor-card-game-turns` | quota ring, directional pass, and exhaustion deletion |
| `xor-chat-message-history` | replace | `xor-branching-chat-journal` | cursor branch pruning and deletion fallback |
| `xor-delivery-stop-chain` | replace | `xor-delivery-range-ledger` | inclusive reversal, detach, and atomic block insertion |
| `xor-device-event-log` | replace | `xor-bounded-event-window` | monotonic sequence admission and capacity eviction |
| `xor-document-revisions` | replace | `xor-revision-checkpoint-chain` | checkpoint rollback and checked tail squash |
| `xor-embedded-playlist` | replace | `xor-weighted-playback-ring` | smooth weighted selection over physical order |
| `xor-file-block-chain` | replace | `xor-block-offset-chain` | extent split, merge, and logical offset lookup |
| `xor-firmware-task-chain` | replace | `xor-dependency-ready-chain` | readiness selection and dependent-cancel guard |
| `xor-inventory-pick-chain` | replace | `xor-precedence-pick-chain` | precedence-preserving relocation and completion |
| `xor-museum-tour` | replace | `xor-accessible-tour-cursor` | access-mask filtered bidirectional cursor |
| `xor-notification-history` | replace | `xor-pinned-notification-feed` | stable pinned partition and unread scan |
| `xor-packet-reassembly-order` | replace | `xor-packet-gap-index` | interval merge, split, and first-gap query |
| `xor-parking-queue` | replace | `xor-neighbor-departure-line` | pre-removal neighbor receipt and adjacent swap |
| `xor-print-job-store` | replace | `xor-priority-print-spool` | stable priority bands and head dispatch |
| `xor-radio-station-list` | replace | `xor-band-preset-ring` | band-filtered circular seek and tune cursor |
| `xor-recipe-step-chain` | replace | `xor-recipe-dependency-chain` | multiple-prerequisite topological movement |
| `xor-route-waypoint-store` | replace | `xor-waypoint-distance-chain` | neighbor-delta Manhattan route aggregate |
| `xor-sensor-sample-history` | reject | — | policy-only bounded-window sibling of `xor-bounded-event-window` |
| `xor-support-ticket-order` | reject | — | stable-priority-band sibling of `xor-priority-print-spool` |
| `xor-train-car-store` | reject | — | range reverse/detach sibling of `xor-delivery-range-ledger` |

Every retained replacement changes its task ID. The ignored sibling `.state/remedy/`
directory contains a JSON record and a 12-section Markdown specification for
each legacy root, binding its pre-change tree hash, pre-change generator hash,
disposition, exact v3 API, invariant, tests, role map, runtime, and acceptance
commands before the owner was changed.

## Representation and prompt contract

Every counted reference owns an arena of nodes with a stable nonzero `SlotId`,
generation, a task-minimal payload, and one `link` field. The only physical neighbor encoding
is `previous_slot XOR next_slot`. Traversal derives a neighbor from the prior
slot and current link; no raw pointer is XORed or encoded as an integer.
Output vectors and task-specific metadata may observe the structure but cannot
be authoritative order.

Each task declares exactly two slug-named editable files and two matching
private references. The prompt builder must expose only documentation and
starters. References, tests, provenance, CMake, Catch support, receipts, and
all `.meta` assets remain hidden.

## Family and benchmark screen

Normalizer `aider-cleanroom-hard-rule-v3` removes comments, strings, literals,
all identifiers, and direction/constant-only distinctions while retaining
types, API arity, operators, branches, loops, and assertions. The owner derives
the seven hard-rule dimensions from emitted files and compares every within-family pair, every available root
under the other remediated DSA families, and all 26 bound official C++
holdouts. A whole-slug overlap fails at `benchmark_id_overlap`; a semantic
holdout overlap fails at `benchmark_content_overlap`; a family or related-root
near-match or any mandatory adversarial control that escapes fails at
`duplicate_family`. Missing holdout content is
`not_completed`, never a pass.

## Acceptance and strongest conclusion

Run:

```bash
uv run pytest -q tests/test_moonlight_xor_linked_list_aider_tasks.py
bash examples/slime/moonlight_cpp_perf/prepare_xor_linked_list_aider_tasks.sh --force --verify-core
# In the pinned image with networking disabled:
bash examples/slime/moonlight_cpp_perf/prepare_xor_linked_list_aider_tasks.sh --force --verify-core --verify
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

`local_family_verified` requires prompt/role/core/family/benchmark screens plus
17 passing normal and fresh sanitizer receipts with equal positive discovery
counts, plus 17 executed and rejected compiled false substitutes. Otherwise
the manifest reports the strongest lower state and exact
missing prerequisite. No result here is a dataset release or benchmark-uplift
claim.

## Final re-verification evidence

Completed on 2026-07-18. The v2 claim remains invalidated historical evidence;
the owner-controlled v3 run separately reached `local_family_verified` for 17
counted roots and recorded three hard-rule rejections. All 136 unordered pairs
passed seven emitted-file dimensions, and the production screen rejected the
domain/identifier-renamed, constants/policy-only, and opposite-end-selection
controls. The strongest scores were 0.956140 for public contract, 0.669643 for
state or algorithm, 0.616477 for mutation/selection and reference control
flow, 0.666667 for invalid boundaries, 0.925532 for deterministic oracle, and
0.658590 for negative fixture. The strongest related-family pair was 0.099065
and the strongest official-holdout pair was 0.001861.

Every counted root passed three normal and three fresh ASan/UBSan CTests, for
51 plus 51 tests. Every task-specific false substitute compiled under the same
strict warning policy, executed the same suite, and failed; the negative count
is 17/17. An independent post-run audit recomputed all live legacy and v3 tree
hashes, remedy-spec hashes, reference and negative hashes, normative spec
bindings, and owner-versus-mounted hashes without discrepancy.

The run used generator content hash
`sha256:3fa4f810e3f762dbcb37e6ec02f0f8dffaa437ec6e65ca884376064a600aefac`
inside
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with networking disabled. Measured identities were GCC 13.4.0 at compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
CMake 3.25.1, CTest 3.25.1, and Catch support hash
`sha256:e11ac6b2994c046909c4a7c730a6a536e8f9563172563026878b7baadecdf553`.
This is `docker_sanity`, not locked-oracle or dataset-release evidence.

| Legacy root | Disposition | Verified root | Before tree hash | After tree hash |
| --- | --- | --- | --- | --- |
| `xor-card-game-turns` | repair-in-place | `xor-card-game-turns` | `fb4ea53c56b4a7ca725695daa23bd1870b94faff1cbfee8139fd1f833de25451` | `c7575ddf8b7edc9d5aa7d81d40670a7d9ca0ddfb56e1de06db4a4a638d2c983d` |
| `xor-chat-message-history` | replace | `xor-branching-chat-journal` | `f3891c12e6d184caee01d518e7bd31b008463d0c9d9a366f5c3dc9cc165146a3` | `5315a4746546a77e8b8ded499cee76aa3a50b15ab56648ada30229e4dac6a2d0` |
| `xor-delivery-stop-chain` | replace | `xor-delivery-range-ledger` | `8b730cc525f4e1c629675e459af520e1cc799db8f95954538a02248a9f3214c3` | `20d7906635df3b64afbf69a648f630fe0f1f829e49d74594aa8e2aeaab1be49f` |
| `xor-device-event-log` | replace | `xor-bounded-event-window` | `3695fb47bb446702d3318ea88cd1c25626bd470b6ecd46d49849077dec302204` | `87490ab98fcc0465f05d93a39be08f9161c6f5a123d5bf82e3407bab6f2e9510` |
| `xor-document-revisions` | replace | `xor-revision-checkpoint-chain` | `cf3775151747ccea39184d7b7ac070f4ffec6d1e7a8ab6590e106e2d2e47b3bd` | `f11eaf691612480944de7eeac6bc723ce0db8fcf657277301d8540b2b58ad3b5` |
| `xor-embedded-playlist` | replace | `xor-weighted-playback-ring` | `f25407a89df91f9e62e40bab5334f6990e704eee11815d247f106a7e74927cfe` | `764e2e57fd74f70c16a60ddb3f76fbda5a4f3ab3dd50239031b7a63df814ea35` |
| `xor-file-block-chain` | replace | `xor-block-offset-chain` | `08e37fcd9833f18648f7516891d9b2a2a44a078205dad1c069145fd1711571f3` | `feb9bda331fc1a2a326138bee40dafd9eaf2dab5f4c94d34fa0f7b062edd1cca` |
| `xor-firmware-task-chain` | replace | `xor-dependency-ready-chain` | `04b739f81bf0ca3774fde6dd2ae1bf1912b7e56aeea22f3927fa6ad38d31ae7d` | `42dfb7377e93dcc2a5a0a29c8dc05bded585280177dc4187a916b3d264a90fcb` |
| `xor-inventory-pick-chain` | replace | `xor-precedence-pick-chain` | `3104749f6ea310952bcb47bc2fc282d33f0b94f26e6b1ed8a4a010c1e6445d2e` | `6175e74477590788d64c889e189aeaa48d3867bb9adfb400b2e0ea8249dba930` |
| `xor-museum-tour` | replace | `xor-accessible-tour-cursor` | `caf301219891ab88272c11437cbedfdae806394bd72b9f48a6a2a0e1e30e9c3f` | `387aaff6f02e28a264b690ea4844222cb4d6af2955a43e467074f18b2171b899` |
| `xor-notification-history` | replace | `xor-pinned-notification-feed` | `0f36d7d8b2d5acb52463817238c9ffcaba8d3698455e79c725594c9a9866ed85` | `4959462133e999456f97654529aff6cbb3d2feb7bd5299af15454a74c8aa16b5` |
| `xor-packet-reassembly-order` | replace | `xor-packet-gap-index` | `b72ebff7768677a17fe5ec3e5bbb6b1696ca34d4dbb096fa245d92561479533e` | `07d1840a9eb657c7d44d5e59e65ccbbc399767e3c60fced1a77ea5aaae9a5835` |
| `xor-parking-queue` | replace | `xor-neighbor-departure-line` | `80752407dfe74164229284cbc9eea6ad2d2fb42506e4a9829e1ced557f8ad2e7` | `72fa0b5cf61f0c25a022d1eb493a2514327d5b5d85015e08217d24215023d457` |
| `xor-print-job-store` | replace | `xor-priority-print-spool` | `455997084d1290feb9e7c4358ccbcfe814a36ca6899270387d771db68e3778e5` | `b0e63a63b59b5d50e4fcb2fd6842a7c3b45828b939f53d3146a344f386d7f1d1` |
| `xor-radio-station-list` | replace | `xor-band-preset-ring` | `e33dde654482ef14a95c24c15b0798ac49ad262b095491ecaadf3c58bb68db78` | `0b62aee6ce9d92e8aea45f81299c31f69599066ee4543bf7947d6700c959b0e6` |
| `xor-recipe-step-chain` | replace | `xor-recipe-dependency-chain` | `9b6007376b3af851f77b0a646ad3060c6fc0c72db259bd2b29b6a61fe5446713` | `dd0987e9ab89bb5ef19e618b0d9cc3599418ace473c0161a4e053ce488dd3323` |
| `xor-route-waypoint-store` | replace | `xor-waypoint-distance-chain` | `6d0dc04a7102a1e2b375634253720f5563e5456363ccd951fd7e14f7370b1773` | `d4337e47302c452ce48c5f44ef5975b3146114bbb42e2de090a5759252d221e1` |
| `xor-sensor-sample-history` | reject | — | `eed764a9c3d1903167aa1ac45da4b11c133bfe5cbe0d247d70a3f757fde9cd4b` | — |
| `xor-support-ticket-order` | reject | — | `9a81e5a7ece3474b12ccf2b9465ecd6f5821f4ebf392bcc464dbf6f5339efbbe` | — |
| `xor-train-car-store` | reject | — | `9d788a6c57c58dbb4b84d19d50185411144d4b1bb07b43c8fad66a010176e17b` | — |
