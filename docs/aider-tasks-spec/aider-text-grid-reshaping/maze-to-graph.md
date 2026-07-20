# Maze-To-Graph Family Remediation and Reverification

## Scope

This audit covers all 20 legacy roots under
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/maze-to-graph/` and their
20 v2 replacements under the parallel `aider-tasks-reverify` tree. The
controlling prompt is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`, with
`FAMILY_NAME=maze-to-graph` and
`FAMILY_TYPE=aider-text-grid-reshaping`. The legacy tree is immutable and no
dataset release is authorized.

## Findings

### MTG-F1 — one generic graph-audit superset

**Severity:** major. **Scope:** all legacy roots. Every reference used the same
`GraphAudit`, four-neighbor indexing, edge loop, component BFS, degree summary,
and task-ID policy chain. Domain nouns and a final integer selector did not
establish different primary mechanisms. **Disposition:** replace all 20 roots.

### MTG-F2 — advertised fields were not implemented

**Severity:** major. **Scope:** the family, especially the hospital and ice
roots. The shared reference returned articulation and bridge fields without
computing them; several other advertised results were only generic component
counts. V2 uses task-specific APIs and independent control flow, including
Tarjan bridge and block-cut decompositions where those mechanisms are claimed.

### MTG-F3 — tests did not discriminate the objective

**Severity:** major. **Scope:** all legacy roots. One generated neighbor-count
test template could not reject generic cell adjacency. Every v2 root has a
separately compiled topic-specific false substitute, and the pinned runtime
executes its rejection in normal and ASan/UBSan modes.

### MTG-F4 — legacy evidence was host-only and unbound

**Severity:** major. **Scope:** all legacy roots. The legacy verifier recorded
neither immutable image identity, network policy, mounted tree hashes, nor
positive discovery counts. The v2 Docker receipt binds all of these fields.

## Replacement contracts

All APIs are C++17 in namespace `curriculum`, return owned values, accept no
borrowed state, and are pure. Empty outer grids are valid empty graphs. Ragged
grids, empty rows, duplicate labels, unknown symbols, or invalid numeric
parameters return the default report with `valid == false`. Vertices and edges
use each root's documented row-major or label order. Exact declarations and
public examples are generated from the case owner; the following table is the
normative one-to-one mechanism inventory.

| Legacy root | Replacement | Required mechanism | Named false substitute |
| --- | --- | --- | --- |
| `graph-mine-tunnels` | `tunnel-junction-contraction` | degree-two corridor contraction | retain every open cell |
| `graph-museum-rooms` | `gallery-door-region-graph` | room-region labelling plus door incidence | accept doors touching other than two regions |
| `graph-warehouse-aisles` | `aisle-segment-intersection-graph` | maximal run bipartite graph | emit incidence at walls |
| `graph-cave-survey` | `cave-bridge-block-tree` | low-link bridges plus bridge-deleted blocks | weakened bridge inequality |
| `graph-subway-map` | `subway-labelled-track-graph` | orientation-compatible station ray tracing | ignore track orientation |
| `graph-garden-paths` | `garden-visibility-graph` | blocker-terminated orthogonal visibility | see through blockers |
| `graph-data-center` | `rack-port-capacity-graph` | endpoint tracing with bottleneck capacity | choose the larger capacity |
| `graph-ski-resort` | `ski-elevation-dag` | strict downhill DAG plus memoized lodge sets | admit equal-height cycles |
| `graph-harbor-canals` | `canal-lock-state-graph` | open/closed product-state graph | traverse a closed lock |
| `graph-fire-escape` | `fire-time-expanded-egress` | hazard arrival plus time-expanded safe states | admit states at fire arrival |
| `graph-irrigation-ditches` | `ditch-flow-condensation` | Kosaraju SCC condensation | wrong finish-order pass |
| `graph-robot-factory` | `factory-conveyor-conflict-graph` | destination-bucket conflict projection | bucket by source |
| `graph-archive-stacks` | `archive-turn-cost-graph` | heading product graph with turn costs | charge straight travel |
| `graph-camp-trails` | `trail-signpost-route-graph` | signpost arrow automaton | constant cycle key |
| `graph-radar-corridors` | `radar-range-visibility-graph` | bounded octilinear visibility | exclude the inclusive range limit |
| `graph-hospital-halls` | `hospital-block-cut-forest` | edge-stack biconnected decomposition | miss non-root articulation vertices |
| `graph-orchard-roads` | `orchard-wrap-road-graph` | cylindrical seam adjacency | planar-only adjacency |
| `graph-sewer-lines` | `sewer-glyph-port-graph` | reciprocal pipe-port validation | rotated reciprocal lookup |
| `graph-airport-concourse` | `concourse-gate-distance-graph` | one BFS distance field per gate | constant distance one |
| `graph-ice-caves` | `ice-slide-stop-graph` | maximal slides between stable stops | one-cell advance |

The complete per-root behavior table, declarations, role map, starter/reference
design, negative fixture, oracle command, and acceptance failures are frozen in
the corresponding Markdown remedy specification under `.state/remedy/`.

## Family and contamination contract

`maze-to-graph-hard-rule-v4-artifact-dimension-shingles` derives seven
independent emitted-artifact dimensions: public API, owned state/algorithm,
mutation/selection rules, invalid/boundary behavior, reference control flow,
deterministic oracle, and topic-specific negative fixture. Every one of the 190
unordered root pairs must remain below `0.85` in every dimension; no aggregate
score may hide a duplicate dimension. The separate aggregate artifact screen
must remain below `0.84`. The same artifact roles are compared with all 26
bound official Aider C++ holdouts; a slug match or overlap at least `0.72`
rejects the root.

The focused and owner verifiers construct coherent identifier/domain-renamed,
constants/policy-only, and opposite-end-selection clones. Each control must be
classified `duplicate_family` in all seven dimensions. The Docker oracle must
also compile and execute all three controls in clean normal and fresh
ASan/UBSan builds, binding their independently mounted tree hashes.

## Verification commands and results

```bash
uv run pytest -q tests/test_moonlight_maze_to_graph_aider_tasks.py
bash examples/slime/moonlight_cpp_perf/prepare_maze_to_graph_aider_tasks.sh --force --verify-core
bash examples/slime/moonlight_cpp_perf/prepare_maze_to_graph_aider_tasks.sh --force --verify
bash examples/slime/moonlight_cpp_perf/prepare_maze_to_graph_aider_tasks.sh --docker-sanity
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

The host oracle is `not_completed` because host CMake is unavailable. This was
not substituted for runtime evidence. The mandatory owner-controlled Docker
sanity passed with image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
network `none`, GCC 13.4.0, compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
and CMake 3.25.1. It recorded 60/60 passing normal root tests, 60/60 passing
fresh ASan/UBSan root tests, 9/9 passing tests for the three coherent controls
in each mode, and 20/20 separately compiled negative substitutions rejected in
each mode. The current deterministic archive hash, accepted owner/case
revision, per-root hashes, control hashes, and exact pairwise results are bound
in `.state/docker-sanity.json`, `.state/family-screen.json`, and the 20
`.state/remedy/*.json` records. Static hashes are intentionally not normative:
any owner, case, or generated-tree change invalidates them and requires the
complete Docker run again. The v4 family screen records 190 seven-dimensional
hard-rule decisions, 190 aggregate pairs, 520 holdout comparisons, and all
three coherent controls rejected in all seven dimensions.

## Superseded pre-hard-rule hash snapshot

The table below is the invalidated v3 snapshot retained only as an audit trail.
It is not current verification evidence and must not be used to accept a root.
The authoritative v4 bindings are the generated state files named above.

| Legacy | Replacement | Before tree hash | After tree hash | Remedy-spec hash |
| --- | --- | --- | --- | --- |
| `graph-airport-concourse` | `concourse-gate-distance-graph` | `sha256:345d84cec42f58b5f7836d724a42e3d72bee2bcce1a2a1749b298a48712ecd57` | `sha256:295dd69760bf7e94a74d7ff22f68dec4074b1e82d52fb2e5ef8c61d1771f123a` | `sha256:13f4433a29b74355cdb1a5cb68412664fae68aa60dade60627f051540ea9a6ff` |
| `graph-archive-stacks` | `archive-turn-cost-graph` | `sha256:69b4186b76168389874a0ec95d5d7142b6cc7936132fd74d1490d5cb82da8f7d` | `sha256:3ab466cb98225e2c7f6b050cd66a832f110fc884c1b2b7ca5187b57990e2a621` | `sha256:36eac63178a84ad2984ef97d7f00a82e11b8139c038a9274dbd5c31d4bd3185b` |
| `graph-camp-trails` | `trail-signpost-route-graph` | `sha256:e2cbc45eacfb546f81713b782901310cc3a922d13f1dd6743b8f7d3fc474f84c` | `sha256:881c2e5bb73695b1051f3b067151ff5c3ff49480c6509f3d9e2d2c884d4665df` | `sha256:706c0b8dfd0d12562c492dde853bea6d3b71eb77ae6f0ceb37152e43de78eb86` |
| `graph-cave-survey` | `cave-bridge-block-tree` | `sha256:4f92a850d5393a96672c8d9213d23d557207d8a87817e6f3baa7d00f7e500098` | `sha256:0f76841d6e7d910230d122d42dddbfdf3508bd92db13c4bd699a0e35847be3f3` | `sha256:9f3fb9a4c51c32cb825044d24fc20082abfc79ef0e07059dbd79f5fdd29d6b61` |
| `graph-data-center` | `rack-port-capacity-graph` | `sha256:8818aad9f6bb2e4c962466cf680a61a2c05b01a338ecd87eda239a0363a274f6` | `sha256:70fe515f76080b9b807c24ef059d555c69f0a245fb2b99fbb9be9f9760a5a863` | `sha256:19cb3be6f635ad80ad68bc5f6ea8069da8e83efc5be5036f327d05302295db23` |
| `graph-fire-escape` | `fire-time-expanded-egress` | `sha256:e0cd596bf0695e39c85a7024c11be915728ee2e76704a60dbf8128e1a6ad5f4c` | `sha256:767511bf5cf595e4e0458bf1bf96851c06b108c3d34646ba7f0abf06a36c229a` | `sha256:7631f0e2b1474e659840309e999beb867d8feaf8bf7d5f52c6a00cfa7bb2bac8` |
| `graph-garden-paths` | `garden-visibility-graph` | `sha256:817a4f1275f1dccc7eedd7e8d419cc1effac18f83f3ebe830ca8a42f5985862c` | `sha256:f5dd72067f4fac25cc4f3a40fb9430a4e7a5eadc6fc3e615decd189eaac9395b` | `sha256:95c6fc3ffc3c51ea326f083a00a7e361c5fa2cedb21cfc75c1cefd548c41301b` |
| `graph-harbor-canals` | `canal-lock-state-graph` | `sha256:f3e17d78accf827829a70c9bf8a405f4a42384cef0d076ca0a91b65e09cddccd` | `sha256:f2e7d47c519a2d10cd437d4fb381b195bb85dabf806ae0b7223871498a3a0841` | `sha256:b4a90dfdfe56f99e146c7aa35c2f5daa1bf80ebb46d7dc4116df095e84b9d1d2` |
| `graph-hospital-halls` | `hospital-block-cut-forest` | `sha256:34608dee9e9944a40db78f44a2bab1332d5494246e3aa442217203c36a480c95` | `sha256:747ffa929dd6538f353ae1e00f29b0152b330ad553dd40e813ecdc505921b37e` | `sha256:81316b0015d9cafa69df3210de78bd7a1e4cc7263fa5611505a794499559419b` |
| `graph-ice-caves` | `ice-slide-stop-graph` | `sha256:2dc6c8b360116bbda754903282c87fc77bd7dbb7ad283888e81e294034851410` | `sha256:e6bc8dd6efd89e5aaadb7ff518b0da4a4eeaaa3802ff7b90deba0c817a5a0a88` | `sha256:6b74939ba5d0338dc261eaf591ae8e2c0ed989c6f14108bc50b3debdb8a95d9d` |
| `graph-irrigation-ditches` | `ditch-flow-condensation` | `sha256:2086563c1395b94bbc9e1984dd0c63094a4dca0d47663eac28986858082f38c9` | `sha256:6154cd717b0a028cd963d2b4de3c3199fb9e855943068dabc0a2e60cf9431a7f` | `sha256:3e0c0ee2d6432534ce83984413fcdf797f9286c0b4fd6f664a6436feef2cf2fc` |
| `graph-mine-tunnels` | `tunnel-junction-contraction` | `sha256:7c739f01d8eb69d8dbb3d04509301ef4e78518996208acd2bd9cd891a9c44538` | `sha256:81548f332f304e9b6ad1a5f60a04fbe2e2c343800723dd468c24cf47e5a13894` | `sha256:303cb4bf2628421cd70fbed52cc9f1edff8e7e30477a96dab6eb10277f9e4fe7` |
| `graph-museum-rooms` | `gallery-door-region-graph` | `sha256:ac48aec0320d0a13bd00a658e0c00dc370c56c17bbe9d9060962af59efbee583` | `sha256:558ebc373796e83a8c3fcd8eb1328977c6ca31d661a0cc12c70c4135d703c862` | `sha256:3e6b4e83914b99038bcb564a25fe9cb2b65d65562acd54270da632ffcda3656e` |
| `graph-orchard-roads` | `orchard-wrap-road-graph` | `sha256:f81549a4328eeb513ccbffe3c5d77127275dc3b12ec95cef38edb90039085cd3` | `sha256:f2092b510a95fd7a8056ae5932b2648fc4584a47eda8e2afa25f0d0aacb37457` | `sha256:acef8b2a750998df3ddfb22b1fbdc917626d2861db028b48672b2eba75eeb0bb` |
| `graph-radar-corridors` | `radar-range-visibility-graph` | `sha256:83b8f5e3fe76e14a3b8794b5a668eaf13b65ea7e989950a813fb53bc4deae3ba` | `sha256:503604006621671ded4d4d2b87b5d2f087b34f7fe5ac23f99fb608f99a5b5a57` | `sha256:203b5fc4085532e44e78c7507419ddd0a8dfc2f1a80f009e37f76e6e1da9c25d` |
| `graph-robot-factory` | `factory-conveyor-conflict-graph` | `sha256:d5290ae7740634bf393a2bb9042faf2d6b19bdf00526f9043dc726524e283e98` | `sha256:5dd97ef8e2adfe11627c9b95858f87244a5075ea73e6b75b421bcc17b28197c8` | `sha256:2419c4469d6c3d9d12fcb92bc2dcfcf6bc0580d02b8740ee3d00838daeda7fe0` |
| `graph-sewer-lines` | `sewer-glyph-port-graph` | `sha256:e2d3a8ec7a14bbd6e0b5881d3bbde0a29c325b1e96d3096a69aea28810821350` | `sha256:3177dcc92d63084283ff79d06801d15ec87e13c6c349cfca061071f019420e1c` | `sha256:f34c12b64000be7b3e6256fa636202707141347902e05de56c9ab1ceac21baf6` |
| `graph-ski-resort` | `ski-elevation-dag` | `sha256:7c571cbff66b5e80e27f3f7eca5306b5bfbde8770d92c52b9fa5dcdd9d125cb4` | `sha256:c5761fcb5b36c2797c3b798afcca8f9457565ecd4f8b60b6d239ac9d92e1305a` | `sha256:96401514f1cca0692d229a307d8c6032d50d1f13d444e367b1411396484e2bd9` |
| `graph-subway-map` | `subway-labelled-track-graph` | `sha256:7c27d5c922b70713e71bdc6ba01d540315fcf039a39c87e07091d85f6da077e5` | `sha256:0611ed87b33cc51084f5a13d23ab7c6705b371d4248f29b0d55bbb3aacec1c60` | `sha256:5cb9aeefc8158e5dc5dd70ebbebff308a9ba38208006c5162bc93d32adf694ed` |
| `graph-warehouse-aisles` | `aisle-segment-intersection-graph` | `sha256:9178606f8ac578658e268fb65e37ae25163580e03434e9aeecf0a9a10bbc80ca` | `sha256:3e21045929049e159d8f6b688f3f1b4f107543c33eed707efe726cdf764c204b` | `sha256:f9988d7248a4928fbf92f070a842a7cef5e19a52906be5ec9ba18e5e9b38c62b` |

Changed owner/spec/test paths are the two maze integration modules, focused
pytest, wrapper, curriculum, this specification, and the materialization guide.
Generated roots and receipts live only under the ignored re-verification root.

## Conclusion

`primary_core_objective: achieved` for every replacement: the owner emits the
named mechanism and the task-specific compiled negative is rejected. Prompt
boundary, reference mapping, duplicate-family, and benchmark-contamination
screens pass. The mandatory Docker normal/sanitizer evidence passes with equal
positive counts and exact mounted hashes, so all 20 roots reached
`local_family_verified`. Evidence class is `docker_sanity`, not a separately
designated locked oracle. Dataset handoff remains `not_requested`; this makes
no SFT, release, training, or benchmark-uplift claim.
