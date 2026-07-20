# Flood-Fill Family Remediation and Reverification

## Scope

This audit covers all 20 legacy roots at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/flood-fill/` and their v2
replacements under the parallel `aider-tasks-reverify` tree. The controlling
prompt is `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`; the
legacy tree is immutable.

## Findings

### FF-F1 — one renamed BFS template

**Severity:** major. **Scope:** all legacy roots. Every reference has the same
report state, queue traversal, neighbor loop, boundary accounting, and return
flow; nouns, source/barrier characters, and the 4/8 toggle are the substantive
differences. The primary claimed domain mechanisms were not achieved.
**Disposition:** replace every root.

### FF-F2 — family semantic duplication

**Severity:** major. **Scope:** all legacy roots. Visible and hidden tests are
the same generated oracle template and do not establish independent learning
value. Rename-only retention is prohibited. V2 binds each legacy root to one
new task ID and a unique mechanism profile.

### FF-F3 — generic traversal was not rejected

**Severity:** major. **Scope:** all legacy roots. No executed negative fixture
distinguished the advertised domain rule from unrestricted BFS. V2 emits a
private per-root `generic-bfs-substitute` fixture and the owner executes its
rejection check while validating the required mechanism marker.

### FF-F4 — evidence was host-only and unbound

**Severity:** major. **Scope:** all legacy roots. The old `--verify` mode did
not bind a locked image, owner/tree/reference hashes, discovery counts, or
network policy. V2 records structural results separately from normal/sanitizer
runtime evidence and cannot claim `local_family_verified` without the pinned,
network-disabled runtime.

### FF-F5 — v2 hard-diversity claim was invalid

**Severity:** major. **Scope:** all initial v2 replacements. The initial
verifier treated unique declared profile tuples and marker strings as proof,
which the skill explicitly forbids. It had no complete normalized all-pairs
comparison and no identifier-renamed, constants/policy-only, or opposite-end
adversarial controls; its negative fixture was not compiled or executed. The
v2 `local_family_verified` claim was withdrawn and its receipt invalidated.
V3 now records all 190 unordered pairs across emitted docs, public API,
reference, visible tests, and private tests; removes only family-common
scaffold n-grams; requires unique normalized API and reference control-flow
signatures; rejects similarity at or above 0.82; exercises all three mandatory
clone controls; and compiles and executes every per-root bad substitute.

## Per-root disposition

Every legacy root has disposition `replace`. Its binding old/new identity,
pre-change tree hash, behavior/invariant contract, role map, negative fixture,
oracle commands, and acceptance gates are in the Markdown/JSON pair under
`.state/remedy/`. No legacy generated file is modified.

## Verification commands

```bash
uv run pytest -q tests/test_moonlight_flood_fill_aider_tasks.py
bash examples/slime/moonlight_cpp_perf/prepare_flood_fill_aider_tasks.sh --force --verify-core
bash examples/slime/moonlight_cpp_perf/prepare_flood_fill_aider_tasks.sh --force --verify
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

## Recorded evidence

The final family hash is `sha256:cfe5aadc7183fd974f3c5e2a214658e41aedaca8770748bb2a363e418c23fad5` and owner hash is `sha256:5dfbabbab2f440d53c9d04b4d0f9a41118aeefaae31f6b54389e74697a4d1ec7`. The v3 hard-rule manifest records `190` unordered pairs over `docs+public-api+reference+visible-tests+private-tests`, removes `1388` family-common scaffold n-grams, and reports maximum distinctive five-gram Jaccard `0.782675` below the fail threshold `0.82`. Identifier-renamed, constants/policy-only, and opposite-end-selection controls each returned `rejected_as_duplicate_family`.

The locked receipt uses `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`, network `none`, `c++ (GCC) 13.4.0`, and `cmake version 3.25.1`. It records 20 roots, 40 passing normal tests, 40 passing fresh ASan/UBSan tests, and 20 separately compiled bad substitutes whose two discovered tests executed and rejected them. The unavailable host `cmake`/`c++` path was not used as oracle evidence.

| Legacy / replacement | Before tree hash | After tree hash | Remedy-spec hash |
| --- | --- | --- | --- |
| `fill-archive-damage` / `archive-checker-component` | `sha256:2500522da7713862ab4a529202bcc7bfba333b1f6aa13b531d8c7bc1b077a9dc` | `sha256:cb6da32b182731305a82fd667771244700aac63a574e952252395bbcd8934323` | `sha256:0d83b0005df7f4e45c38ab65d8eff7dd021f3a8f1a46d296a4152512e0e70dcd` |
| `fill-circuit-traces` / `circuit-directed-propagation` | `sha256:bf21c257b9e8b2ce49c411a4a4811a0227bc6b0088141794ba024fb737c193c5` | `sha256:afb996dd593a115768e76c056d6f6eb341708e7ac935f49f903baa1dcabbd543` | `sha256:22af20792dfe169728a3825698cac96508d3e7be82a064cd2101f43e92a01ab4` |
| `fill-city-blocks` / `road-complement-component` | `sha256:8105e196aa7f01481ffc359771f131a2ea4fe1699507e49b27ccfe7dce75a523` | `sha256:dad80611324806dfe51ca8702b0bcbf8b4c1b5add1fef9466bf223d41fb88269` | `sha256:f3c092341ea640445aa59ac8ae644d7e9c19c841547b7a8dd6cdbab77d2d603a` |
| `fill-coral-reef` / `reef-threshold-bleaching` | `sha256:c9868000d51aee8229704673b8e6411109b9a1ea41d3cb0f49b2c7a4a5e49143` | `sha256:0d388e86c13674261e6a5b8b248d6b1d64aae99c8a97b04a3f5471fb9028e7ef` | `sha256:419383c54c2eae527fb574adac225ad9cfc4bbc43fc77fcdd544328d93d75779` |
| `fill-crop-disease` / `crop-row-quarantine` | `sha256:b0ef6a90f837b26ac799b4013249bb27fb3a84341ff2a6fc486a1e9ed90cfe98` | `sha256:d8989582805c4c113529473baa8f56e7f4677b6ad173966acaba683884ebcaa1` | `sha256:20e5c716a396aa831184cc3dd5caf7d8f20e02c9a9521a19bd71f26cf2f46ead` |
| `fill-garden-mulch` / `mulch-column-band-fill` | `sha256:aca496dd9f24095bddc471e59120e603773ae1670d0e16967a5850cc4f6fe401` | `sha256:2009c6152a097f9e1ff317085424416a729f5272727e234a64f289a3bd180ee8` | `sha256:9780aa5ec77829460c9077834968f9592409a805d5a0a0c5147454b620a11f06` |
| `fill-harbor-oil` / `oil-tide-wrap` | `sha256:47fad70d3e7fb46024882e5860de79b731402773c0cc5efcc382680a40064b07` | `sha256:42d8a77af5d389fe6eca8a79991b75b2359c108c84bcf23e67684ed57b7f917f` | `sha256:801849da10919178719fa808022202932803f9963502b1baa9fcc296cbafa0d8` |
| `fill-ice-thickness` / `ice-casefold-patch` | `sha256:8bb2dfa57edb840ac27d02cb0084a7fea54648ed0a8bcff634119324dc49474c` | `sha256:254d3be1658da9df3d4236a33438f31788b23b947ad6999f30714d3613ca7a8c` | `sha256:8888624b2d54980af23a23f7a8d146486a8792b94033ea1ac3dfba3b0ac18b39` |
| `fill-lake-survey` / `shoreline-component-audit` | `sha256:738d05d3f3e8596170e245974df3a04b2a828714e69c63beb598f8c95674473d` | `sha256:3290da02949bad7776dbbf6376e522c48c0ead32c9cd940a5cebedb5954aa013` | `sha256:4f2a23755afad6ae66ca806189fdba4492ffeb00e3bbe3ecf3cff7f1d3348b68` |
| `fill-mine-tunnels` / `tunnel-priority-reachability` | `sha256:6fd9b300d621def858e18839c45d9548fe41d72597119f6249c0c93bbe71f809` | `sha256:c68af5b15ab9efd37ec1f3c1e1e693c7548990d1668e98758205e0826c05b225` | `sha256:1840456975364112bd9f22fb4284f2a574019eeb6f22096d200b642bab1a6963` |
| `fill-museum-restoration` / `mural-mask-restoration` | `sha256:4ab78eaf243544ee50838ed5af8008969b1dc0ec465e9d61c67d8cab3b9eef47` | `sha256:5f6b2b7d096ddb35fa5961936eee5b3635774c9cbf65bcc0cad16896a53748f0` | `sha256:5ec7ddcd02e8e93fc8c375eb2884f1ee35334464110cb3b0685f80465a454a73` |
| `fill-orchard-frost` / `orchard-radius-frost` | `sha256:2807e65dd8a862e5a65486ab5acec62ca5d51315aa8fb82659614e586676cf6d` | `sha256:c55b738c747cec3fb244e2ecd5c9d61cf603186ff60658ae902489f98a60f08e` | `sha256:6cc93d5195c956e9572ecd4cdbeb2fd9262d2151e6ea61dbf693bc4e97473760` |
| `fill-quarry-material` / `ore-grade-vein` | `sha256:d7d98c55a5dd4cce5df2598924f0d7cf8270247814a4fdc96ebb994b576fb23f` | `sha256:135edd98f23863476646cd45ee8cd3813a31e32dfc131d66ad51ee07c40c1d33` | `sha256:ad098bdbd9ad74768fe1b3e0972f293d5d1490a03704b43492793797d4206182` |
| `fill-radar-clouds` / `cloud-diagonal-components` | `sha256:730a693c8b5e1f1f8f1625c365fb1dc42195e3d28a667e6a5f0be9dd3b7a3f54` | `sha256:cb436ef57402c3d04e9bd63fbbc57f6c1d8447a21aad5579a8ba822669a7b1c8` | `sha256:56e8dc10f783c9a4c3272c9b428f0e10e90b9f1658d82da3f050b1dde8b19ef4` |
| `fill-river-pollution` / `river-downstream-plume` | `sha256:4b7fab5b2cd48caf20c055cbc1a49b94ac7e77a7043f3a542cd59975bff24204` | `sha256:54f0946a563edf796bb149198f2845d3c5c1a92503dfa0fde40cb036419fa795` | `sha256:b194a610ec12e3c880ab98a2dcb2e07fc99068296ffbd64c12055bd73a0480e7` |
| `fill-ski-avalanche` / `avalanche-downhill-run` | `sha256:0f5649d7e0cf9dd130fb72cd1a4a2919336bab60e07ac0d149a9bf393731642f` | `sha256:245f6242603f347eab25703bb4e975ed40843f521ba881f6426c282fa5480e27` | `sha256:5b5d1bc3980e36c6c5741804be4185ac329adf913f7bb147f9ce6f84f2febd3f` |
| `fill-solar-soiling` / `solar-bounded-priority-cluster` | `sha256:4e6e2a1b0e5474994ba79fee0fc59041b83aef1f5363351464454ea9fa8c2bdf` | `sha256:683a02fbdb9c74bfc5073dd8485c2c3019cffa8efa6754f2c844944b2a675b74` | `sha256:4a2bfecdadb60161d9df5bb3966d890dfd6c6a23d3a099c2ae762e5073a39978` |
| `fill-theater-smoke` / `smoke-bounded-egress` | `sha256:1b7c71e32be978df9cc02bf4de52c9c2549cd13a9f9ca099aba0c7c31bf96a8c` | `sha256:163f91a7baa1d91aca7452f75660297dfd6bc07fd90317e888607b5ebfb6a877` | `sha256:da7414e2145d7eed9862592730e1a73dabb5e43f5236629636d67c50532e3972` |
| `fill-warehouse-spill` / `spill-capacity-prefix` | `sha256:880f2ac0de0337d3c6fccd4784e185d9728e491120491070769e6d9456bd5082` | `sha256:be3139bd393c62b529e25ecbe1d8bb23c022fd398ee116d9c56cb45c95129db0` | `sha256:fa93696b507b6d60fdbd89be19d22c810a108f519978d6cf15501035f81fd63a` |
| `fill-wildfire-sector` / `burn-perimeter-wave` | `sha256:eaef57a6e20394ad02b5f3712e100d3195ca580a6098cf6978133bad095ddd53` | `sha256:53fa958951c9a0095394ef09b4b9cbb62280a0015ac44543f395f6d38a185e9b` | `sha256:c2ce6d7ac7346a1dc4e7f1d26df0c359430b086e9c8f7a6d1f5c5239801b11a8` |

Changed owner/spec/test paths: `src/w8_biayn/integrations/moonlight_flood_fill_aider_tasks.py`, `tests/test_moonlight_flood_fill_aider_tasks.py`, `examples/slime/moonlight_cpp_perf/prepare_flood_fill_aider_tasks.sh`, the flood-fill curriculum, this audit report, and the materialization guide. Generated v3 roots/state live only beneath the re-verification root. Prompt boundary, reference mapping, hard diversity, executed negative fixtures, benchmark screening, focused tests, skill validation, and scope-doc tests passed. Dataset handoff remains `not_requested`.

## Status rule

`primary_core_objective: achieved` requires generator-owned mechanism code plus
the executed private discriminator. Host normal/sanitizer runs are host
evidence only. The strongest local status becomes `local_family_verified` only
after the exact pinned Docker image passes both fresh modes with network
disabled and equal positive discovery counts. No result creates dataset rows,
release readiness, training authorization, or benchmark uplift.
