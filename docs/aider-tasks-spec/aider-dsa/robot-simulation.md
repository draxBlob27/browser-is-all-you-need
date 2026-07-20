# Robot Simulation Family Reverification Audit

## Scope

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with `FAMILY_NAME=robot-simulation` and `FAMILY_TYPE=aider-dsa`. The immutable legacy family is `.w8-biayn/data/aider-tasks/aider-dsa/robot-simulation`; fresh output is owned at `.w8-biayn/data/aider-tasks-reverify/aider-dsa/robot-simulation`. This is local clean-room remediation only; dataset handoff is `not_requested`.

## Frozen legacy finding

### RS-F1-template-semantic-duplicate — major

**Scope:** all 20 legacy roots.

**Observed evidence:** the legacy owner emitted every header, reference, starter, visible test, hidden test, and instruction from one `TaskSpec` template. Every reference used the same fixed 4x4 grid, blocked cell, orientation, resource decrement, destination action, depot refill, halt rule, and trace codes.

**Why it matters:** the roots differed only in names and domain nouns, so they did not provide independent logic or implementation learning value.

**Root cause:** a row-driven rename template represented domain diversity as identifiers instead of distinct state and algorithm contracts.

**Remedy:** disposition `replace` for every root; new IDs, APIs, state representations, algorithms, and task-specific negative cases are mandatory.

**Verification after remedy:** owner `--verify-core` must produce 20 unique semantic profiles/signatures and reject the named `legacy-template-clone` fixture with `duplicate_family`.

**Status:** resolved and reverified.

### RS-F2-objective-contract-mismatch — major

The legacy curriculum promised altitude layers, stack limits, switches, cellular fire, decompression, parsing, lockout, conveyors, pressure allocation, and scheduling, but every implementation was the same coordinate command loop. Each v2 reference must own the representation and operation named in its public contract, with a source marker and task-specific behavioral discriminator.

### RS-F3-oracle-evidence-stale — blocker

Legacy host builds cannot prove the rewritten roots. Regeneration invalidates all old tree hashes and receipts. Fresh normal and ASan/UBSan evidence with equal positive discovery counts is required. A designated locked Docker run, if unavailable, remains `not_completed` rather than being inferred from host results.

## Per-root disposition and independent mechanism

| Legacy root | Replacement root | Disposition | Substantive mechanism |
| --- | --- | --- | --- |
| `sim-warehouse-picker` | `warehouse-wave-router` | replace | directed BFS capacity waves |
| `sim-greenhouse-cart` | `greenhouse-moisture-controller` | replace | event decay and longest-run scan |
| `sim-drone-delivery` | `drone-altitude-pathfinder` | replace | battery-state layered Dijkstra |
| `sim-harbor-crane` | `harbor-stack-rebalancer` | replace | bounded top-stack transfer |
| `sim-mars-rover-energy` | `mars-energy-route-planner` | replace | weighted terrain Dijkstra |
| `sim-subway-maintenance` | `subway-switch-inspector` | replace | switch-gated graph traversal |
| `sim-firefighter-bot` | `fire-spread-responder` | replace | double-buffer cellular spread |
| `sim-orchard-harvester` | `orchard-capacity-harvester` | replace | serpentine capacity traversal |
| `sim-hospital-courier` | `hospital-priority-courier` | replace | manual stable binary heap |
| `sim-ocean-survey` | `ocean-dive-profiler` | replace | depth-time decompression profile |
| `sim-construction-hauler` | `construction-load-router` | replace | load-constrained graph replay |
| `sim-library-sorter` | `library-label-sorter` | replace | lexical checksum parser |
| `sim-factory-inspector` | `factory-lockout-inspector` | replace | explicit lockout FSM |
| `sim-snowplow-route` | `snowplow-edge-router` | replace | directed Hierholzer trail |
| `sim-space-station-repair` | `station-airlock-repair` | replace | pressure-gated airlock graph |
| `sim-museum-guide` | `museum-tour-planner` | replace | closure-aware weighted tour |
| `sim-recycling-sorter` | `recycling-conveyor-controller` | replace | simultaneous conveyor pipeline |
| `sim-farm-irrigator` | `farm-pressure-irrigator` | replace | difference-array allocation |
| `sim-search-and-rescue` | `rescue-frontier-explorer` | replace | weighted marker-state frontier |
| `sim-airport-tug` | `airport-taxiway-scheduler` | replace | segment interval scheduling |

## Structural and semantic acceptance

- Exactly the 20 replacement IDs above are generated; no v1 root is overwritten.
- Prompt construction exposes only docs and the two declared editable files.
- Each reference maps by suffix to exactly one editable file; tests, references, metadata, CMake, manifests, and receipts remain private.
- Every profile has a unique API and normalized reference signature, contains its task-specific invariant marker, and contains fewer than two legacy-template command markers.
- Every root passes whole-slug/content screening against the 26 official Aider C++ holdouts. The bound upstream checkout is used for the strongest available semantic review.
- Each reference passes two discovered CTest targets in clean normal and separate fresh ASan/UBSan builds.

## Changed owners

- `src/w8_biayn/integrations/moonlight_robot_simulation_aider_tasks.py`
- `src/w8_biayn/integrations/moonlight_robot_simulation_cases.py`
- `tests/test_moonlight_robot_simulation_aider_tasks.py`
- `examples/slime/moonlight_cpp_perf/prepare_robot_simulation_aider_tasks.sh`
- the robot-simulation curriculum and this audit/specification

## Commands and exact results

- `bash examples/slime/moonlight_cpp_perf/prepare_robot_simulation_aider_tasks.sh --force --verify-core`: passed; regenerated 20 roots, reproduced every tree from the owner, validated prompt/role/reference mapping, rejected the legacy template fixture, and wrote the materialization manifest.
- `UV_CACHE_DIR=/tmp/w8-robot-uv-cache uv run pytest -q tests/test_moonlight_robot_simulation_aider_tasks.py tests/test_aider_sft_scope_docs.py`: 10 passed.
- Host `--verify`: not completed because host CMake is unavailable (`verification requires cmake and c++`). This was not treated as oracle evidence.
- Pinned Docker `--network none` verifier: passed in `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991` with GCC 13.4.0 and CMake/CTest 3.25.1. All 20 references discovered and passed two normal plus two fresh ASan/UBSan CTest targets; counts are positive and equal.
- Semantic holdout screen: passed against all 26 bound official C++ roots, inventory `sha256:0bfd7652d3c810728b181f9b47cee8d79472b77a853437fe8da528f3be1a291d`, normalizer `robot-semantic-v2-control-flow-9gram`. Strongest containment was 0.102632 (`airport-taxiway-scheduler` vs `sublist`), below the 0.60 rejection threshold.

## Per-root evidence ledger

Oracle receipt: `.state/oracle-receipt.json`, SHA-256 `f3ae6de8b57cf97eb700fde292d7beb4325facd442b8ed74977177371894ec63`. Every row has disposition `replace`, prompt/reference/family/benchmark screens `pass`, normal/sanitizer counts 2/2, primary core objective `achieved`, and strongest status `local_family_verified`.

| Replacement | Legacy tree hash | Reverify tree hash | Remedy-spec hash |
| --- | --- | --- | --- |
| `airport-taxiway-scheduler` | `sha256:5212c0a7fa6a3c38314a1d2818991542c2bebd4216cb0c8f3c0e812083195605` | `sha256:5d36a2adf5ee5bd11b7ccbe6ec577224a2e27c5e3fd042c25bb3a3976a23cbe4` | `sha256:5477ca9de48fa3235c3599507718d62129539fd4e57cefe59973f5d1e48461f2` |
| `construction-load-router` | `sha256:b246e115f48664bd91520d94265d6f55489e9bc1d9f3ead1734b8048135c9f53` | `sha256:d5092c3a3e8ba18264f1f55e7e1d233c60fc2e2ae19edb4e26f590e883a5c5c9` | `sha256:c9fd041588dea3b7ac1c8b37daddd6fa25c42aa20a6cf0bb50632dadfc5fd639` |
| `drone-altitude-pathfinder` | `sha256:61e8ef14da4afabffa6a0856467915dd565659212b39ebefc98b2b37b02a4750` | `sha256:f40d6da3c14b5f155691efe458458f0748ffaa9fe5887494728ac3667f7c0b09` | `sha256:fd57538e241b32945c6260ab315ce99897f9806da482f329708a003df0c06413` |
| `factory-lockout-inspector` | `sha256:e08f0a8c3010f8d69cbfb89a3da79fa5831f5bc8e5c225db973364f0d15f7422` | `sha256:29b3056ecd97f25e94e1d0f95fc1abe527ae718297a9fa0414e2c9f89fa72034` | `sha256:cd5de26ce332147a586b188b092e5302a069163d8e76e132725df9aeaa6c8268` |
| `farm-pressure-irrigator` | `sha256:bada3d40d0f52f539602574f31d4d3a2364f13c79bcffdc93c973b517a8a7585` | `sha256:1bb173d4ff24d5299400bfe855696c1d46ad76862bace034b4a6a903b33dab72` | `sha256:3d43facb88a7c21f7e61a8988ff05779de65468b33079f984e9e190898d13e21` |
| `fire-spread-responder` | `sha256:e318a80975c64f3246fa340e386dd4d3e273e22631534abbdf4d1f6d1177cd2e` | `sha256:e6004e0f3e6abbf658b1f85431882470d9cc2987c6d8d9194891acd695a3cce6` | `sha256:5c3e09290cda61eded8578c166fb3fb2b3f2daa8eb7789660266dc4d2f6dba40` |
| `greenhouse-moisture-controller` | `sha256:ea8d8d796a7e7c2b5dbc40f4dcd43605dc437b6cf018d7ab3155993d26cd89d5` | `sha256:8e55b1fb378e732bd70a10464a2254488fd9bbbe58b4088e8f1c38f0765bb158` | `sha256:d3cba6e9f38459fbbbf66ff8335ceb4f7c6fd11426512278596bacd925fe4d1d` |
| `harbor-stack-rebalancer` | `sha256:fcf1654bc7c2aa31cbd19460a30b3b707366bea3f4961bd46b1f985a2c61e7b7` | `sha256:44e340833270c3bc9fec09f58a055c3977c2b4fbd2caccfa1fe493ad19df33bf` | `sha256:f83d0d6e9ca94162c20fafbc1b6dbe433553830ded49611ae24f4dd3155e0347` |
| `hospital-priority-courier` | `sha256:36167a39402788a4a9cf45a1f5fd056468661c978ac2c2d8836223535e82ff99` | `sha256:65544b026523c76669a9e2d96bad092608d27a83b946a6209874a48db185810a` | `sha256:bc876e23c8ad91a68b1c1085f92830329fbad3cd52cb65ff4ca73aa42d29275d` |
| `library-label-sorter` | `sha256:b737e4c37672f4618d00af2d264bb3647e37be7b7184c76042c9f64c6db1b676` | `sha256:5472ea7b1e2d2ad9fff4dc710fd340f8ce2eaf48683878d7b4f4fba97215b2e1` | `sha256:aba513d2730ba7f3fc0188f1282b2212adac9e3c995e5206726c21ddca610b12` |
| `mars-energy-route-planner` | `sha256:e402144e0ce905253d70f3cb746a4f9ba8bfc2c0d1116b37ba8676baf5de3cb4` | `sha256:314d2c8aa2434c97fd9f30eaad9a64b5cdd6485439fd177b926cfb99183613e6` | `sha256:180ed04ee4aaa1ff95b8787644144390f75a75d693dcdfe703ebe9c746aeb557` |
| `museum-tour-planner` | `sha256:284743afb36fb87400d47f46f1338ceafd8e3fe6094af82d2c3e29c53a9a40db` | `sha256:bdce104908f703ffb9fa1b662b50ba03b15e5bf90c56e49d5c5aca31545e2f79` | `sha256:b23bbd8ebcad50799fc18df10183006f2d1084f0c11dbdbef6719d7c6ea1a08b` |
| `ocean-dive-profiler` | `sha256:b305a0704b0b39dbe63f8eb2b8ea9fd7a35ef252c3fd3a9849e3f0df7a6179da` | `sha256:ab5d249f04dc25da4bb9ceb2af1bed4ab472731993a2d9dcd8ac7a1c90eac7ec` | `sha256:1df4ee5836c99b6be46545db9e810af1a0d1977b3a24624258b9aeeda5bf2e27` |
| `orchard-capacity-harvester` | `sha256:49b98e92b91ccb996e5a2d4a758bbb08be754e30afbae57c83b04f0d47d28c09` | `sha256:4911cb2cdb00be986bf9215a384e21bb20226515ea4b19daa570d44bcdef1c00` | `sha256:e862cc9dd368dcdb8a417d19f4d659346295fdcab28ed0e0d2e5a611af2f9e34` |
| `recycling-conveyor-controller` | `sha256:4ef15ca53466c4d6e266e4a03b5c14986965b8c7623e1b03ccbfae03517379d4` | `sha256:b56cbba2470fec58e01b244cd58c3f7ae586a5f7b20ce1660abb45a50974592a` | `sha256:a98010c0eaebae272f1dce39440c1772dc06cab69e7ce46af67ca1d6f773ecf4` |
| `rescue-frontier-explorer` | `sha256:e49397f0612ef6dfeb2fcbcf4e25cf53bafddc671082416d134842366c0d5ab2` | `sha256:3b6a8bca0cf483f43d8fefadbf1f70be2096339d0ba50fbd0e6d832d888ba268` | `sha256:802d165a777471a79b75edf323a8ae3e357ae7a0774ce12e717d88c729dfdd7c` |
| `snowplow-edge-router` | `sha256:f30c0836e2bd48aaa93dfe7c9769c81fb2f5bb7d987f289772a66680df3d800f` | `sha256:1e05ec6e7355a0bed90dcfbe97d3801843fe3977130447723a2a53c9c8c95d6d` | `sha256:e62579679f9c75e34c47989f66737342f17d4dacfcdaa480d8a871bc9b0ee7db` |
| `station-airlock-repair` | `sha256:ed0d146016b8f57c1eb83232bee8192ed51443b97eb4a2dcb71d707edd7c94a0` | `sha256:98ff5ff93fec5d3d6ef1a8533fa7f199a8d27be4c973a08b44b36e91dbdb671f` | `sha256:fde27a4074d4c24b5d5220528da1a1eac6b5f51a95032e5953b01b07307d8db5` |
| `subway-switch-inspector` | `sha256:4e81f38c2f998b8927c3e99a1ced7c618f8013d3674317471b9128acb833edd3` | `sha256:8753f1c5f78959107dd528e293ef8c4d79e5565d7c8fb09b6ee2f072b39e7869` | `sha256:e1ab23913024af53bd185d0589e7c1d5af075f70d66175435428566769e1e7be` |
| `warehouse-wave-router` | `sha256:11162c215b4777bb1e7a7ea21a0e2d254c3de7c0f4832370da2d69cf420f500b` | `sha256:f20352461491745ee9658281aa483c4be88da2048e56a6100d75d9725e7b4c61` | `sha256:a32255e0b810162a3527dd49a0b3c436258e890e56e36a9cdbe4afa9442f16a0` |

## Conclusion

All required local-family gates pass. The 20 roots are materially distinct in API, owned state, control flow, algorithm, and task-specific tests; none is a rename-only copy. Prompt/role boundaries, reference mappings, fresh regeneration, negative fixtures, duplicate-family screening, 26-root semantic holdout screening, and locked normal/ASan/UBSan oracle checks all pass. Every replacement reached `local_family_verified`. Dataset handoff remains `not_requested`; this does not create SFT rows, authorize training, or claim benchmark uplift.
