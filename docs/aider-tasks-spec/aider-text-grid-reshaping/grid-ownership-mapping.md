# Grid Ownership Mapping Family Reverification Audit

## Scope

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with `FAMILY_NAME=grid-ownership-mapping` and `FAMILY_TYPE=aider-text-grid-reshaping`. The immutable legacy family is `.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/grid-ownership-mapping`; fresh output is owner-generated at `.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/grid-ownership-mapping`. This is local clean-room remediation. Dataset handoff is `not_requested`.

## Findings

### GOM-F1-template-semantic-duplicate — major

**Scope:** all 20 legacy roots.

**Observed evidence:** the legacy owner emitted every root from one seven-field row. Headers shared `GridCell`, `LegendEntry`, `OwnerTotal`, a common report layout, and one static analyzer signature. References shared legend maps, row-major counts, unknown-cell lists, boundary lists, component scans, and a `primary_metric` selector. Visible and private tests were the same trace with only the expected metric changed.

**Why it matters:** names and selected metrics do not establish materially distinct logic or implementation.

**Root cause:** one generic ownership analyzer was presented as 20 domain tasks.

**Remedy:** `replace` every legacy root with a new ID, public API, algorithm, invalid/boundary policy, ordering or tie rule, reference, and deterministic visible/private oracle.

**Verification after remedy:** the owner compares actual emitted docs, public APIs, references, visible/private tests, and task-specific false substitutes for all 190 unordered pairs. It also rejects the legacy template and real domain/identifier-renamed, constants/policy-only, opposite-end-selection, and missing-mechanism controls.

**Status:** resolved and reverified.

### GOM-F2-objective-contract-mismatch — major

**Scope:** all 20 legacy roots.

**Observed evidence:** curriculum labels promised closures, access, capacity, contacts, intervals, disconnected concessions, river junctions, and downhill ownership, but the shared implementation reduced every root to legend validation plus generic grid counts.

**Why it matters:** passing examples did not establish the advertised core algorithm.

**Root cause:** domain nouns and a selected metric substituted for task-specific state and control flow.

**Remedy:** the replacements implement distinct interval scheduling, BFS/Voronoi, edge aggregation, component flood fills, interval audits, rectangle overlays, union gaps, contact tables, ray casting, run parsing, quota allocation, topological propagation, downhill dynamic flow, serpentine scans, and weighted capacity accounting.

**Verification after remedy:** each emitted reference contains its task-specific mechanism and its visible/private oracle executes task-specific boundaries. The missing-mechanism control is rejected as `invariant_not_enforced`.

**Status:** resolved and reverified.

### GOM-F3-oracle-evidence-stale — blocker

**Scope:** all replacement roots.

**Observed evidence:** legacy host results could not bind rewritten references or tree hashes. Host iteration was unavailable because `cmake --version` returned `zsh: command not found: cmake`.

**Remedy:** archive the exact generated roots deterministically and run owner-controlled normal plus fresh ASan/UBSan verification in the repository-pinned sanity image with Docker networking disabled.

**Verification after remedy:** archive `sha256:f4393697eb3ae2bc34dd8e324206ac4fbf4cf69c08f6a8fdef3d7641f722cec3` matched inside the mount. All 20 references discovered and passed two tests in both clean normal and fresh sanitizer configurations.

**Status:** resolved and reverified as `docker_sanity`; `locked_oracle=false`.

### GOM-F4-hard-rule-executable-negative-gap — blocker

**Scope:** all 20 replacements and the three prohibited clone classes.

**Observed evidence:** the first remediation pass used text/semantic screening for false substitutes while Docker executed only correct references. That did not satisfy the skill's hard rule requiring false implementations to compile and be rejected by executed tests. The premature `local_family_verified` claim was withdrawn before remediation continued.

**Why it matters:** marker or source inspection cannot prove that the oracle distinguishes a plausible wrong implementation.

**Root cause:** the Docker receipt lacked executable negative-fixture results.

**Remedy:** the owner now emits one compiling, task-specific false implementation for every replacement and real compiling controls for domain/identifier renaming, constants/policy-only changes, and opposite-end selection. Each is built under the verifier's strict C++17 flags and both task tests are executed.

**Verification after remedy:** all 20 topic negatives compiled, discovered two tests, and were rejected by CTest with nonzero exit. All three prohibited clone controls independently compiled, discovered two tests, were rejected by executed tests, and were rejected by the semantic duplicate-family screen. The hard-rule matrix covers all 190 pairs across seven emitted-artifact dimensions.

**Status:** resolved and reverified.

## Per-root disposition and evidence ledger

| Legacy root | Replacement root | Disposition | Legacy tree hash | Reverify tree hash | Remedy-spec hash | Strongest status |
| --- | --- | --- | --- | --- | --- | --- |
| `ownership-airport-gates` | `airport-gate-closure-planner` | replace | `sha256:e13a1c8762a11cb21c3953eaeee3e5200e32f2eb6f54c652d9524114b55d6eb2` | `sha256:db3c04ede04c7eb0d4a691df1f18669e24926d1017383c69a9073328feb453a2` | `sha256:330037719a1e8e5ef744a447f9e5281b2abe9865949e57b2fc55b1dd3dc6e24c` | `local_family_verified` |
| `ownership-lab-benches` | `bench-contact-compatibility` | replace | `sha256:9fd4c7cddd1fcd506aae54e813f64085b7671c7577305a78a49bed7dcb19d89c` | `sha256:2022e157e7e198b15079a52fd4dabd8c147699ea5be18b73173b11b599c92219` | `sha256:4aee6496f1a079c06378f8270bcf13cbf803f1f3877185e52e2b8f2f4510b173` | `local_family_verified` |
| `ownership-campsite-map` | `campsite-access-zone-router` | replace | `sha256:d20f6831197d46420c3d8462921d29dff6ccd5e393890693bdf4744388662358` | `sha256:0cdf37857e0e4b63475c2752a115c6743ed66d98dbc204e802eb6ea288d18d51` | `sha256:988bb3ed266ea19a2457df37cb87e0aea499ad2e554d452fd9378e4dff120852` | `local_family_verified` |
| `ownership-ski-runs` | `downhill-patrol-zone-propagator` | replace | `sha256:2a4e87df30d66d57541d54cdd079c08ec09e7c7bb5b281df571f453311d6dc90` | `sha256:b03a8500499cbbb1ce3d97238e274b5a75c10bfe29dfa552636923bd5dbceab5` | `sha256:0027cdd6e32062f59bc6a10d0eb6bd3cf8240c5c564d62afb3e3b4a84c2d0952` | `local_family_verified` |
| `ownership-museum-galleries` | `gallery-room-label-audit` | replace | `sha256:d482657ec571d7c313da3d98c4f669bcab6ca7f38f42f3a9ad783d4d86b6f0c1` | `sha256:332a92a88f8b7590c8baf9ae3794bfaee22a6c9b6b8700d47167e5c2f2519550` | `sha256:49cb37519c8c3bb43719b562283313b2abf956ad503d31fc8f08cfed5e8f1a33` | `local_family_verified` |
| `ownership-city-gardens` | `garden-boundary-ledger` | replace | `sha256:084a674994365a171e09accefe86f7d65b842bb29235c6b2f9f47b2e884c4f7c` | `sha256:4234b73de7a274e5025f01719a5a5326cef07412f85774819909b60799ab55d6` | `sha256:486089ed9de83fb4f52d6eba171317d784543d1d966816e3eff06f49cb35692e` | `local_family_verified` |
| `ownership-farm-leases` | `lease-rectangle-overlay-resolver` | replace | `sha256:16a426a028453c593901959520e82a6a8ee89df351dda2dd4ba2bc01d33a0e70` | `sha256:8d17ec155b684e001753c62543c33008ef3dfd9617d8a5516831f6edbb7468e7` | `sha256:e775e53195a412ca2b86365ce7b9670b85aa1f38072228e58eb12744c59b02a2` | `local_family_verified` |
| `ownership-marina-slips` | `marina-berth-ray-attribution` | replace | `sha256:372c2b73498fad16f1c57c4c0020c2e8d67a5b2d0aa87d5d8a88a5ef6557ecc4` | `sha256:3d0be518817259174e9a9da8a00ad5444f2adb4718436571481e6d05ad7b4c36` | `sha256:450bf1054af1bf418e1d47407bf4e9703f3b9d0d57dfa2b747f1e10669411761` | `local_family_verified` |
| `ownership-market-stalls` | `market-stall-frontage-runs` | replace | `sha256:4fbd9a1ce60e0382ea676a52fc56d4c8573c5781d3275932059b7cca3e1861ec` | `sha256:b06a4c7efa9be2ed1d55455a8ef3d627ced3efb64f2e5e1bcb620429d25edcef` | `sha256:36e58c2b376000088d28a50cc27abba4f502887dcf91213aa69c524c1de775ca` | `local_family_verified` |
| `ownership-office-desks` | `office-desk-voronoi-assignment` | replace | `sha256:15a668b1591cbd6fc53adecb24b68a31a59c3188b478e9c72538955f217d969c` | `sha256:f4626feba7500a734fdb5b63080ede2ab877d73e037b7c2ad0c0bbcb618b923f` | `sha256:32077c56e1543a433f4f7e2749c6b846030b250496ea8251eb39a724cc67c8be` | `local_family_verified` |
| `ownership-orchard-blocks` | `orchard-row-quota-allocator` | replace | `sha256:02af6fe1f995a18b68771336688f7f44ae8ac15ae3af27ba2410da8e64a84af6` | `sha256:c0da99bce519d6f63799d00b67ecd2312c138b79852f84791addad5e11313caa` | `sha256:1cca2689879d97ecefb483131e70bbd4c2023c80ed7fe72290161456f275e31c` | `local_family_verified` |
| `ownership-construction-lots` | `parcel-component-perimeters` | replace | `sha256:388b1d122c8c94c68a0561f8a8bc5d6dea4bcb39fc2f831d278ea17fcdc32227` | `sha256:a023e58a84d13dffa2951978be6e567a10052e9ec04b2ca4e31467e74e139d20` | `sha256:b94f2e11e691791805736b4db7e4e0d23ff767132cfefad9bc45bca8197cd7e0` | `local_family_verified` |
| `ownership-parking-permits` | `parking-permit-occupancy-audit` | replace | `sha256:acbada242551b05db17abd3bc131542ea0ac0805e8e041443244d59d0e01047a` | `sha256:27d784dca862ead857c1753bf91408296f62cac8d4cecd863b74db2640da5c32` | `sha256:1657bb0acbde5eec532c42adeb5286dddde65d6ec2b21d675988bdd0826d6a01` | `local_family_verified` |
| `ownership-harbor-quays` | `quay-concession-component-audit` | replace | `sha256:cc0d28890621126c3d906d9af3aba9758c5c4eacf941f95f871fc99d1bfac166` | `sha256:74903e4538b2fcab5a9794e184f61a865602efcd858e55d21d28a000f7d8bf9e` | `sha256:0ad3aa2f64175a163d87ee86f67fdafc1cafd9d7f6f9cc144f1e3305f459fc83` | `local_family_verified` |
| `ownership-data-center-racks` | `rack-contiguous-allocation-audit` | replace | `sha256:480681a9e6f1f23ece0af9d6518ae6078d3814e78152161fe581e9a9e771e338` | `sha256:e4703032010efa6fb98f968fb9745eb901c660fe88f0f69761158aff2828927e` | `sha256:56cd439823a01d4f9cebbbc82f437c1ac422e6355c1fc916d43b29eec32fda2f` | `local_family_verified` |
| `ownership-rail-platforms` | `rail-platform-service-zones` | replace | `sha256:62801e83b005bdd9ab5f0b76682a537b1fbce8d587c49108e6a0eb331b2ab6a8` | `sha256:629361f33f7c210bf550575fd7c72b1453d590b54549f2533c6e20ff60fedf0e` | `sha256:690d2c0fd76201f3306fdf60111ebe236ddfb90ca30ec8f3ced1b4e26c4dc6af` | `local_family_verified` |
| `ownership-river-rights` | `river-junction-rights-propagator` | replace | `sha256:a1a7eb8026b159afe016f83436d49d454e8f5d1369d999c40003fe3d5ef00ae7` | `sha256:9e9b92027d5f98ecf564d1ff1c2eec3f15f6361ada89dcd4024ddb1a929e12da` | `sha256:f2c163f9db7f77320f2ce8b6e056fe09bcb16fd82dc5c4cc85b13fc0a447f20c` | `local_family_verified` |
| `ownership-flood-barriers` | `shoreline-barrier-coverage` | replace | `sha256:98dedfd8bd6d02f8ebea84cfa655fa3d3e3d5eba46c68d3a893d6465ca7da5f9` | `sha256:81e3bc4aaf817ac04fabe9097c64e516ad7a170fd05757cc3a46390a76285a73` | `sha256:043973cee082db02572ad85f51d69a60cac584fddc63c39d15c64f1f67fe2a99` | `local_family_verified` |
| `ownership-solar-array` | `solar-string-serpentine-audit` | replace | `sha256:d34748908756ca6ca057828c29a57a7e1dcc28f225c59c053c993192e55eeb04` | `sha256:bd7dd40ecb703f68352f0006b867c3f8dc196801ca524f05a3dd77faeccebf78` | `sha256:ced793974736533d5530a27eafc79938deb6502a995f5a7f5dc565e6a15c7af4` | `local_family_verified` |
| `ownership-warehouse-aisles` | `warehouse-zone-capacity-counter` | replace | `sha256:16c54b7dc434a6f7ec1f01423b79e7646e287e51e6266622478c1faa4eea51e8` | `sha256:254dea3f9ecf78678d61d04291225c32b9ce46e6f2197555da5c9fa2bf3c4e65` | `sha256:1754250157c2183c0233b6bdd6e720ab4e4871f19c798b4ae770d51b0fdd4199` | `local_family_verified` |

Every record reports `status=verified`, `hard_rule_status=pass`, `primary_core_objective=achieved`, prompt/reference/family/benchmark screens passing, normal and sanitizer discovery 2/2, its compiled/rejected topic negative, changed owner paths, and dataset handoff `not_requested`.

## Hard-rule and semantic evidence

- The all-pairs matrix completed 190 of 190 unordered comparisons using actual emitted docs, task-named public headers, references, visible/private tests, and false-substitute sources.
- Every pair is distinct in all seven required dimensions: public API; behavior/invalid/boundary contract; owned algorithm and reference control flow; visible deterministic oracle; private deterministic oracle; topic-specific negative fixture; mechanism/mutation-selection marker.
- The artifact screen's strongest containment is 0.66112 (`gallery-room-label-audit` vs `quay-concession-component-audit`), below its 0.78 rejection threshold.
- All 20 topic false substitutes compiled under the strict verifier flags, discovered two tests, and were rejected by executed tests.
- `domain-identifier-renamed-clone`, `constants-policy-clone`, and `opposite-end-selection-clone` each compiled, discovered two tests, failed CTest with exit 8, and were rejected as `duplicate_family`.
- `legacy-template-clone` was rejected as `duplicate_family`; `missing-mechanism-token` was rejected as `invariant_not_enforced`.
- The semantic holdout screen passed against all 26 official Aider C++ roots, inventory `sha256:0bfd7652d3c810728b181f9b47cee8d79472b77a853437fe8da528f3be1a291d`. Its strongest containment was 0.094488 (`river-junction-rights-propagator` vs `knapsack`), below the 0.6 threshold.

## Structural and prompt evidence

- Exactly 20 replacement IDs are generated; all 20 legacy roots and their recorded hashes remain unchanged.
- Prompts expose only the two documentation files and the two task-named editable files. References, tests, provenance, CMake, false substitutes, manifests, and receipts stay private.
- Each reference maps by suffix to exactly one editable file in `files.solution` order. Strict whole-file answers pass; missing, unknown, duplicate, or prose-bearing answers fail.
- Remedy JSON and Markdown, the manifest, controls, and receipt are owner-generated under the reverify root's `.state/` directory.

## Changed owners

- `docs/aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_GRID_OWNERSHIP_MAPPING_CURRICULUM.md`
- this audit
- `docs/AIDER_TASK_MATERIALIZATION_GUIDE.md`
- `src/w8_biayn/integrations/moonlight_grid_ownership_mapping_aider_tasks.py`
- `src/w8_biayn/integrations/moonlight_grid_ownership_mapping_cases.py`
- `tests/test_moonlight_grid_ownership_mapping_aider_tasks.py`
- `examples/slime/moonlight_cpp_perf/prepare_grid_ownership_mapping_aider_tasks.sh`

## Commands and exact results

- Owner `--verify-core`: passed; regenerated 20 roots, reproduced every tree, validated prompt/role/reference mapping, completed the 190-pair emitted-artifact matrix, rejected all semantic controls, and passed the official holdout screen.
- Focused pytest after final documentation reconciliation: 11 passed.
- Host `cmake --version`: unavailable with `zsh: command not found: cmake`; no host oracle claim is made.
- Owner `--verify-docker`: passed with `--network none` in image `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`; compiler `c++ (GCC) 13.4.0`; CMake `cmake version 3.25.1`. All 20 references passed two normal and two fresh sanitizer tests; all 20 topic negatives and all three prohibited clone controls compiled and were rejected by two executed tests each.
- Receipt schema: `aider-grid-ownership-docker-sanity-v3`. Receipt SHA-256: `sha256:0e90565032f89c20bb9124ee6967374ffa6aeef98db933d74edd075db4588e60`. Owner SHA-256: `sha256:1160349bc3bffa6373ebb629b437fc479a51b3ee908548ca3d7f5e41a0f5c812`. Deterministic archive: `sha256:f4393697eb3ae2bc34dd8e324206ac4fbf4cf69c08f6a8fdef3d7641f722cec3`.

## Conclusion

All four findings are resolved. Every replacement has `primary_core_objective: achieved`; the manifest reports `status=local_family_verified` and `hard_rule_status=pass`. Structural validity, prompt/reference boundaries, owner reproduction, all-pairs implementation diversity, executable false-substitute rejection, clean normal/fresh ASan/UBSan reference evidence, duplicate-family screening, and official benchmark contamination screening pass.

This conclusion creates no JSONL rows, split, release, training authorization, or benchmark-uplift claim. Dataset handoff remains `not_requested`.
