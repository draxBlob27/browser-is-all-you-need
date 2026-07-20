# Countdown Timers Family Remediation Specification

## Scope and immutable inputs

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
for `FAMILY_NAME=countdown-timers`. The supplied
`FAMILY_TYPE=aider-text-grid-reshaping` does not name an existing legacy root;
repository ownership resolves the family to `aider-dates-and-clocks`. The ten
legacy roots at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/countdown-timers/` remain
immutable. V2 is generated only beneath
`.w8-biayn/data/aider-tasks-reverify/aider-dates-and-clocks/countdown-timers/`.
The user-authorized hard-rule count is 8–12 roots; this remediation retains all
ten independently justified objectives. Dataset handoff is `not_requested`.

Legacy owner revision:
`sha256:2cb882831a83fa79880c7066acf32bfa8d71a9908afc12876be42ace7d118af9`.
The semantic holdout inventory is the bound 26-root official C++ tree under
`.cache/upstreams/aider-polyglot/cpp/exercises/practice/`.

## Audit findings

### CT-F1 — No complete hard-diversity proof

**Severity:** blocker

**Scope:** all ten legacy roots

**Observed evidence:** the legacy owner checked only that ten named roots were
written. It did not compare the emitted docs, APIs, references, visible/private
tests, or topic negatives over all 45 unordered pairs.

**Why it matters:** distinct IDs and domain nouns do not prove distinct logic
and implementation.

**Root cause:** the family predates the seven-dimension hard rule.

**Remedy:** retain the ten objectives as `repair-in-place`, derive all seven
dimensions from emitted artifacts, and reject domain-renamed,
constants/policy-only, and opposite-end-selection controls through the exact
production comparator.

**Verification after remedy:** `--verify-core` records ten roots, 45 pairs,
seven decisions per pair, and three rejected coherent controls.

**Status:** resolved and reverified.

### CT-F2 — No executed topic-specific false substitutes

**Severity:** major

**Scope:** all ten legacy roots

**Observed evidence:** each root had visible/private examples but no source that
implemented a plausible boundary, expiry, ordering, or transition defect and
was compiled then rejected by those tests.

**Why it matters:** a passing reference alone does not prove that the claimed
timer-state mechanism is discriminated from its easiest false substitute.

**Root cause:** the old verifier ran only the references.

**Remedy:** emit one distinct strict-compiling negative per root and require
positive discovery plus nonzero CTest exit after compilation.

**Verification after remedy:** Docker `topic-negative.tsv` accounts for all ten
roots.

**Status:** resolved and reverified.

### CT-F3 — Host-only oracle path has no binding receipt

**Severity:** blocker

**Scope:** all ten legacy roots

**Observed evidence:** legacy `--verify` used whatever host CMake/compiler was
available and wrote no image, network, tree, owner, reference, compiler, or
test-count receipt. CMake is unavailable on the current host.

**Why it matters:** host execution cannot establish mandatory Docker sanity or
`local_family_verified`.

**Root cause:** the owner predates snapshot-safe Docker evidence.

**Remedy:** archive the exact current generated family and coherent controls,
run clean normal and fresh ASan/UBSan builds in the pinned network-disabled C++
sanity image, and import results only after archive-hash and count
reconciliation.

**Verification after remedy:** `--docker-sanity` writes a current
`.state/oracle-receipt.json` or leaves status `not_completed` with the exact
blocked command.

**Status:** resolved and reverified.

### CT-F4 — Grace-band contract was not implemented

**Severity:** major

**Scope:** `timer-evacuation-drill`

**Observed evidence:** the legacy API stored `Stage::grace`, but the reference
never read it; every observation above the hard deadline became the first
failure, including observations within the promised grace band.

**Why it matters:** the emitted implementation did not achieve its advertised
primary behavior.

**Root cause:** visible and private tests did not distinguish hard-deadline,
inclusive-grace, and beyond-grace outcomes.

**Remedy:** keep the root ID and API, implement an inclusive grace endpoint,
count only hard-deadline passes as on-time, report only the first stage beyond
deadline plus grace, and add equality/beyond-grace private cases.

**Verification after remedy:** the reference passes and the `>=` boundary
negative fails executed tests.

**Status:** resolved and reverified.

## Per-root accounting

| Root | Legacy tree hash | Disposition | V2 mechanism |
| --- | --- | --- | --- |
| `timer-launch-hold` | `sha256:f7d1f9ef66f6ebcc30a164647a80889c106312010d4b5d696dac73f6a7ae2cc9` | repair-in-place | guarded transition graph and exactly-once terminal event |
| `timer-auction-extension` | `sha256:4964030487f1b86af3147d1e509259c3697789c9acee2816de79fabc5cb018c7` | repair-in-place | monotonic bid history and capped deadline extension |
| `timer-parking-credit` | `sha256:5da0a8628960b11c8d2fe145fbf379c1ec2e723a98f3fcccc76625605cfa373c` | repair-in-place | bounded credit ledger and unpaid remainder |
| `timer-chess-round` | `sha256:943f45ca8dc920b3c08841a2c34f17845db2e79dbfce18188fd3145bbb082628` | repair-in-place | turn-owned dual budget and terminal flag fall |
| `timer-incubator-checkpoints` | `sha256:71b91e622b611ae57fe6dd033b88967a77e193122c618059d7b615cb09b796d2` | repair-in-place | ordered exactly-once milestone crossing |
| `timer-evacuation-drill` | `sha256:97bb4033a6af6e6df83f996e69b89e08c5ec2fbb68733ff0d78ad62f6320a0b9` | repair-in-place | hard-deadline/inclusive-grace stage assessment |
| `timer-game-cooldown-registry` | `sha256:83dd3ad2722b4d3543b6f7b4be7ff56e77a260d2ff2f88312af4477baf4aa20c` | repair-in-place | keyed simultaneous readiness transition |
| `timer-oven-safety-lock` | `sha256:2d889e889639d8362d1927533310013c980618edbb3e017261af9655b60a2651` | repair-in-place | irreversible lock state and relock credits |
| `timer-build-lease` | `sha256:d7cbea3e5ec50a8268129e718f4815d5f00d11e6565832f158538814abf021ed` | repair-in-place | generation/sequence checked lease table |
| `timer-study-session-budget` | `sha256:2f303a1d8f506ae47d34c7ee418e288418009216a78ed6ea0c91880b7fc27ab8` | repair-in-place | atomic focus/break budget ledger |

## V2 tree hashes and final receipt

| Root | V2 tree hash |
| --- | --- |
| `timer-launch-hold` | `sha256:13ee3b0a75c363a8a814d00a3a0e15c39fd139b2e32500a3b68caf36980a2238` |
| `timer-auction-extension` | `sha256:1bcde53a2eca5532a29dee673069c9a81441706cce8b75a9f51d97b636b4b3fc` |
| `timer-parking-credit` | `sha256:4646d561ec0161946c4df3cbc4745f16ab313ce2a2487bddc5d350b65cfab9f4` |
| `timer-chess-round` | `sha256:ab982f3961ae21c80dfac830ece8cd5aae77d0eb2e38ad04b29a783e67c17c61` |
| `timer-incubator-checkpoints` | `sha256:e3491d28734933901928f56daac008ef224f4a757ce76d97db12b073a1c20c94` |
| `timer-evacuation-drill` | `sha256:ac6605a5955893a3058c7e15d3804ed6f1f3d274cdfdcf7264a6af8af9b03293` |
| `timer-game-cooldown-registry` | `sha256:829a90f106e788f6522502ca3dae5e6d17b2553b5aed357c8a2e431e1d282c29` |
| `timer-oven-safety-lock` | `sha256:9c457372debc66b53e4e0e5ef4cb2af97f8db302264e5f0995bd51c56471821e` |
| `timer-build-lease` | `sha256:06575fd2fabd37720c9983f06ef472834bc2b5a53e20297cea8c16bdc2101a80` |
| `timer-study-session-budget` | `sha256:55583cb2159d00e18be408726e02901ae19ed8cb7f8641b798eb171d089c11a1` |

The owner receipt uses pinned image
`sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
GCC 13.4.0, CMake 3.25.1, and Docker network `none`. All ten roots discovered
and passed two normal plus two fresh ASan/UBSan tests. All ten strict-compiling
topic negatives were rejected by executed tests. All three coherent clone
controls discovered and passed two tests in both modes, then received
`duplicate_family` from the exact production evaluator. The manifest records
all 45 family pairs across all seven dimensions and 260 official-holdout
comparisons. The evidence class is `docker_sanity`, not `locked_oracle`.

## Acceptance and strongest conclusion

Focused tests inspect the exact count bounds, all 45 unordered pairs, the
exact seven dimensions, every per-dimension decision, nonempty coherent control
changes, and production control rejection. The bound holdout screen must record
260 comparisons. The owner-controlled pinned-image Docker normal/sanitizer run
passed with two equal positive tests for every root and control, plus executed
rejection of all ten topic negatives. Every root therefore reached
`local_family_verified`. This remains a local-family claim only; it creates no
rows, release, training authorization, or benchmark uplift.
