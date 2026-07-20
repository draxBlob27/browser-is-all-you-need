# Trie Family Remediation Audit

## Scope

This audit covers all 20 roots in the immutable legacy family
`.w8-biayn/data/aider-tasks/aider-dsa/trie/`, family ID
`aider-dsa-trie-v1`. The selected workflow is
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with
`FAMILY_NAME=trie` and `FAMILY_TYPE=aider-dsa`.

Every legacy root is replaced one-to-one in `aider-dsa-trie-v2`, materialized
only under `.w8-biayn/data/aider-tasks-reverify/aider-dsa/trie/`. The legacy
trees are retained byte-for-byte as audit input. No dataset handoff was
requested or produced.

## Commands And Outcomes

| Command/check | Outcome |
|---|---|
| legacy inventory and normalized implementation audit | 20/20 roots inspected; one shared flat-map scan/sort implementation found |
| preimplementation remedy record/spec validation | 20 JSON records and 20 Markdown contracts present and hash-bound |
| `PYTHONPATH=src pytest -q tests/test_moonlight_trie_aider_tasks.py` | 8 focused tests pass, including all three mandatory adversarial controls |
| owner `--force --verify-core` | 20 roots generated; five artifact dimensions recorded for all 190 family pairs and 20 × 26 holdout pairs screened |
| host normal/sanitizer verifier | unavailable: host has neither `cmake` nor `c++`; no host result was substituted |
| owner network-disabled Docker `--verify` | final receipt is authoritative for local status; see Acceptance Evidence |

The designated local image is
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
The family specification does not designate it as a locked oracle, so passing
runtime evidence is classified `docker_sanity` with `locked_oracle: false`.

## Structural Verification Matrix

| Gate | Legacy result | V2 acceptance |
|---|---|---|
| primary core objective | fail: no trie nodes, edges, counters, caches, or pruning | named mechanism tokens plus executed behavioral/invariant tests |
| prompt boundary | weak generic contract | only docs and the two editable files are prompt-visible |
| role/reference mapping | structurally present but template-owned | exact two-file solution/example mapping and private-role exclusion |
| reference oracle | insufficiently discriminating shared trace | three positive tests in both clean normal and fresh ASan/UBSan modes per root, including an independent complete-state trace |
| topic negative | absent | 20 distinct compilable topic-specific substitutes, each rejected by three executed tests |
| family duplicates | fail: 190/190 pairs share the template | all 190 task-spec-v3 pairs pass five-dimension artifact screening and three adversarial controls |
| benchmark contamination | no direct bytes found; semantic proof incomplete | all 20 roots screened against all 26 official C++ holdouts |

## Shared Findings

### TRIE-F1 — Advertised trie representation is absent

**Severity:** major

**Scope:** every legacy root

**Observed evidence:** every legacy editable/reference source owns a
`std::map<std::string, int> entries_` and answers prefix queries by scanning or
sorting complete stored strings. No root owns trie nodes or traverses edges.

**Why it matters:** the tasks do not teach or evaluate their primary DSA
objective, so a passing solution provides no evidence of trie competence.

**Root cause:** one generic associative-container renderer was parameterized by
domain nouns.

**Remedy:** replace every root with a new ID, observable trie-specific contract,
owned representation, independent reference, and deterministic discriminator.

**Verification after remedy:** run the owner `--verify-core` mechanism screen
and the full Docker oracle including each named negative fixture.

**Status:** resolved and reverified

### TRIE-F2 — Family is a semantic template duplicate

**Severity:** major

**Scope:** every legacy root

**Observed evidence:** normalized APIs, state, mutation flow, query flow, and
test traces reduce to the same five-method flat-map template across all 190
unordered pairs.

**Why it matters:** renamed copies inflate curriculum capacity and reward
memorizing one solution shape.

**Root cause:** task identity was varied without varying authoritative state,
algorithm, transition rules, or tests.

**Remedy:** use 20 distinct mechanisms and reject noun-only, constants-only,
and shared-control-flow clones.

**Verification after remedy:** owner screening must account for all 190 v2
pairs and focused clone injection must fail with `duplicate_family`.

**Status:** resolved and reverified

### TRIE-F3 — Tests do not reject the false substitute

**Severity:** major

**Scope:** every legacy root

**Observed evidence:** the shared public/private traces accept the flat map as
the intended implementation and do not recompute node reachability, subtree
counts, caches, prefix-free constraints, pruning, or mechanism-specific state.

**Why it matters:** prose cannot establish an implementation objective that the
oracle cannot distinguish.

**Root cause:** tests target generic key/value behavior instead of the claimed
representation and algorithm.

**Remedy:** add per-root audit state, boundary/mutation traces, and a compilable
flat-map negative fixture that must fail executed tests.

**Verification after remedy:** all 20 negative builds must discover two tests
and return nonzero when executed; every reference must pass the same tests.

**Status:** resolved and reverified

### TRIE-F4 — Domain policies are not independently specified

**Severity:** moderate

**Scope:** every legacy root

**Observed evidence:** invalid-input, normalization, duplicate, deletion,
ordering, ambiguity, and empty-query behavior mostly inherit one generic
contract; several domain names imply policies absent from their tests.

**Why it matters:** hidden requirements become guesswork and the family remains
semantically homogeneous.

**Root cause:** the template supplied behavior before each domain contract was
designed.

**Remedy:** bind complete per-root C++17 APIs and behavior tables in the remedy
specifications before generation.

**Verification after remedy:** prompt-contract and public/private behavior
checks must pass for every root.

**Status:** resolved and reverified

### TRIE-F5 — Runtime and contamination evidence is not admission-grade

**Severity:** moderate

**Scope:** every legacy root

**Observed evidence:** legacy receipts do not bind fresh normal/sanitizer
results, executed false substitutes, all family pairs, and all official
holdouts to one current owner/tree/image identity.

**Why it matters:** stale structural success cannot support a local verification
claim.

**Root cause:** the prior materializer predated the deterministic remediation
evidence contract.

**Remedy:** produce one owner-controlled receipt binding owner, task-family,
reference, image, toolchain, command, test-count, negative, and screening data.

**Verification after remedy:** the receipt must report equal positive counts in
both modes, 20 rejected negative fixtures, family and benchmark screen passes,
and `local_family_verified`.

**Status:** resolved and reverified

### TRIE-F6 — Hard-diversity proof is incomplete

**Severity:** blocker

**Scope:** every v2 replacement root

**Observed evidence:** the first v2 owner compared all 190 pairs only through
one concatenated similarity score. Its focused tests did not exercise a true
identifier-renamed clone, a constants-or-policy-only clone, or an
opposite-end-selection clone. Declared required-token profiles were reported as
diversity evidence, negative fixtures shared one fixed-key substitute, and most
private traces did not compare every operation class and complete observable
state against an independent model after every mutation.

**Why it matters:** the mandatory hard rule is not established by unique IDs,
declared tokens, or one composite threshold. The earlier Docker pass proves the
references build and the old fixtures fail; it does not prove 20 materially
different roots.

**Root cause:** the v2 verification owner treated whole-artifact similarity and
runtime correctness as sufficient evidence instead of separately binding API,
state/algorithm, mutation/selection, boundary policy, control flow, oracle, and
topic-specific false-substitute dimensions.

**Remedy:** retain the 20 contracts only if the owner derives a per-dimension
matrix from emitted artifacts, rejects all three required adversarial clone
classes, generates an independent complete-state operation trace and a named
topic-specific false substitute for every root, and records exact reference,
test, negative, verifier-script, compiler, and CMake hashes.

**Verification after remedy:** the focused suite must demonstrate the three
adversarial failures, `--verify-core` must account for all 190 pairs and every
hard-rule dimension, and the complete owner-controlled Docker run must rebuild
normal, fresh ASan/UBSan, and every executed substitute from the current tree.

**Status:** resolved and reverified

## Per-Root Dispositions

All dispositions are `replace`; no legacy root is repaired in place.

| Legacy root | Replacement | Core discriminator |
|---|---|---|
| `trie-command-completion` | `radix-command-catalog` | compressed edge split/merge |
| `trie-product-search` | `tst-product-prefix` | ternary branches |
| `trie-contact-directory` | `contact-alias-trie` | normalized alias ownership |
| `trie-library-call-prefixes` | `digit-call-range-trie` | digit subtree counts |
| `trie-word-game-dictionary` | `rack-prefix-word-trie` | rack-budget DFS |
| `trie-url-router` | `segment-route-dispatch-trie` | longest segment ancestor |
| `trie-dns-suffixes` | `reversed-domain-policy-trie` | reversed-label policy |
| `trie-dna-motifs` | `dna-motif-counter-trie` | fixed DNA branches |
| `trie-emoji-shortcodes` | `unique-shortcode-trie` | unique terminal cardinality |
| `trie-spell-checker` | `levenshtein-spell-trie` | edit-distance row traversal |
| `trie-file-path-index` | `path-descendant-trie` | descendant file/byte aggregates |
| `trie-license-plate-index` | `normalized-plate-reservation-trie` | normalized prefix uniqueness |
| `trie-predictive-text` | `cached-topk-text-trie` | ranked node caches |
| `trie-snippet-tags` | `tag-posting-trie` | posting-set union |
| `trie-log-category-filter` | `hierarchical-log-policy-trie` | inherited category policy |
| `trie-morse-codebook` | `prefix-free-morse-trie` | prefix-free admission |
| `trie-access-token-prefixes` | `shortest-token-prefix-trie` | shortest unique prefix |
| `trie-sku-allocator` | `numeric-sku-allocation-trie` | occupancy-guided gap search |
| `trie-wildcard-dictionary` | `single-wildcard-word-trie` | exact-depth wildcard branching |
| `trie-translation-glossary` | `multilingual-glossary-trie` | language-partitioned tries |

## Per-Root Evidence Ledger

| Legacy root | Replacement | Before tree | After tree | Remedy spec |
|---|---|---|---|---|
| `trie-access-token-prefixes` | `shortest-token-prefix-trie` | `sha256:b59bc7e4b928ac96f53d564b269e07803f180bda866f8ea8f35f1617f5a22a61` | `sha256:bb7ce3ef267b3f096678b89a8e5a8cd401dfe6cdb8cd4c9a832dc8607cbe35b2` | `sha256:e66e15de85cff595f03bc6a42fc3ac4571b4a5424ecafdbf148d459eb6d52cc7` |
| `trie-command-completion` | `radix-command-catalog` | `sha256:e1ea6a89d1c1f987a9d0f5edd47e8096d838a078f92b49a0be486e996b9c1618` | `sha256:620a3f4821abc712f33ee4b7b92bdbb3b1040a4c2d063e5dd633e4e1d9e46da5` | `sha256:ae2c90eac8294a76d7de8218668c5d7e93e4d05009d323751774798312af5d0c` |
| `trie-contact-directory` | `contact-alias-trie` | `sha256:4bee69c2d5acf34c8bb481f6cbcce32bed5a4905019d539de433cb19994f0b99` | `sha256:346a71ddde29371a5e1d53548cbe3476606c4f1856f902821a598515a1b384ab` | `sha256:3a47858a86a35a35005c13f4579ae5d0f375455a0d4fd5ce1d942897cedde399` |
| `trie-dna-motifs` | `dna-motif-counter-trie` | `sha256:8e656605cc66a6bd6bd2eb3ad3261052519754bbb85b360c9760f41a056efc81` | `sha256:a852055a989e189c0f4d1b8bc7c4f82fdf0513c8d35077a45202f66d8fdfe6a6` | `sha256:0f9edb0b7ec4aa02da266d4a6afde308ef10250f26913d03e0fa8401d9dded64` |
| `trie-dns-suffixes` | `reversed-domain-policy-trie` | `sha256:c7c8a4d084572583328cc2750ec4a4b07df6934d1490a928b68a643d5008e4d0` | `sha256:4b08c7964b5f45b815822bc2133237a5940e35c90160978eb427fb67d46a51a6` | `sha256:c0f3b7e48c578abbf1409b6f3c4e45d72b89c27e9974c425d58d1798848edb99` |
| `trie-emoji-shortcodes` | `unique-shortcode-trie` | `sha256:7a22aaf989b519e981dac552bd96337759227df2a11e1c233c08fdf77eac20ce` | `sha256:c9f02e0b4946dec52836cf8ca3de4c0464ee1e480a97588890eef95ef0909895` | `sha256:2b264f67f005038ac5d0d50f22f2fea61c44e8b6f7c85b8aa28753af7cedaa07` |
| `trie-file-path-index` | `path-descendant-trie` | `sha256:a439938f7cdf9d7de78db6322d99339c1fe394f4008bc157b929567ec1f5fc60` | `sha256:04ada49136d3ef8dac98a161547d54b631e11e74d9fefa528d110b369913d5f9` | `sha256:ce0b314305e0300c20bc5e3fa093b917cb77cc88746c1395baf4e89619823757` |
| `trie-library-call-prefixes` | `digit-call-range-trie` | `sha256:85cf4d3b8d804c4807a446c7d821329b0b7d3074f275cb9ab83bb2ca1bff52e0` | `sha256:3a927cc10744c0621a949e799109386b814e190f2819bb62deb67a6748605492` | `sha256:2448028fd35e7aaa189fa23b37e8174b505fd9fca6e5d6b4e90aae8ccc5210ff` |
| `trie-license-plate-index` | `normalized-plate-reservation-trie` | `sha256:f41388083a06df2ffbae99b639807f454d8cef9d30d95f15301c05cb728a42a4` | `sha256:c350c9a6767da2a1110419893dd71fcec2b6cc5e283fa71ea5789017d6bc9032` | `sha256:a92e75545a7d95f8f90be923952d84c136d517241c671522abf331857f545a75` |
| `trie-log-category-filter` | `hierarchical-log-policy-trie` | `sha256:8bc7fa5d5f562544facb5e860d19b7323e9fa1fe55059e8843e5485a475c2e33` | `sha256:02688162bb10b851a1d1be771e7d8d80b055f3fb8239881c30293a3779197db0` | `sha256:d06bd3a1b69535e7758d7faeaee71c72790999f2f1151acdd8915c9ba609382a` |
| `trie-morse-codebook` | `prefix-free-morse-trie` | `sha256:c5af76e84eacbe2ceaddc11feb41ab05c5bd6ac4f7de1ea220e1a8d7e4b3a9e1` | `sha256:3e5c6c13093382c093c173167ce0db8455c970eb8fdbc882854265ed0970cc3d` | `sha256:12db90223c5b63a705c312df0f51ba846073f8c6dac044c767e526bd84128b49` |
| `trie-predictive-text` | `cached-topk-text-trie` | `sha256:b3f0a2f2640d6cc2391193ff0c560a373b436733f22a5199c1b40d69114b3d68` | `sha256:368ce2f4cf27af4dfb7a6a244294ca7d67656dab1b6cf5232efedc3af676c0cf` | `sha256:c75471096db5bbcd2ddf35dd2a4fee9283858784f51f52f1541db0f0f5468e52` |
| `trie-product-search` | `tst-product-prefix` | `sha256:fcae4e1cff03460f830f54cac9272031c22e151dd99a199acb67aa935cf6cada` | `sha256:b9b4bc59461c859142642f936d29740b534ae397b5b0b45dcc142a9d59b8cf0e` | `sha256:478ac9fd49aa00cf6602ff7095a5099c3e63f18da1f7d4d3353729d990c570dc` |
| `trie-sku-allocator` | `numeric-sku-allocation-trie` | `sha256:fb8c1a6e2902a9d1e41031973b782f831a8513ed22338ab859caaecaf2c92bb7` | `sha256:d2a03febb2ff2ae676aed9f91cbb6336e0ac5139bba21f4937c4fd46ba6834da` | `sha256:b35932a3356053eae190473673ea09c35ba8c71430ce355306c0fa873d8e57a7` |
| `trie-snippet-tags` | `tag-posting-trie` | `sha256:b6ce916ed85dce9cdbe84b588e3a44e4dffd90bd73f5fd7ec25b09441c1fc085` | `sha256:7851aef5e6a42c0f18d787851f11ce76937c418203805648d57fa58cf2b99cd0` | `sha256:10628984f2f4eaea0ff841154023dbcba433022c3e4dad7919a8b9df00353be1` |
| `trie-spell-checker` | `levenshtein-spell-trie` | `sha256:6a91b2e67b641926c7cc36753c3ea201888fdd83cb903a43eb2675e0e2ef75b3` | `sha256:13635ecf27f33c747af2d04564c09672afb34c4ab0bdf077be5e40bd600c272d` | `sha256:e730fa7564c885f73b8d2ebb8e903ecd9ca45a5b88aaa532070107285f99da7d` |
| `trie-translation-glossary` | `multilingual-glossary-trie` | `sha256:eab3f1f040972a27b186ca4bcabe561a10df09f04314ab96f74a453c20fc5cdb` | `sha256:a4f5751476a57b77bae8f9e7f9411a9d0bf93245be682c22ed795584f6570376` | `sha256:440541249ed6cacf3e8e8bf6b4ce1e80e0b421df40ca5099322dd6c4db656900` |
| `trie-url-router` | `segment-route-dispatch-trie` | `sha256:45b56d73cfb82d48be18a94710c99ca01ec01e0bb0650d9c19ea2bf83f265e9e` | `sha256:3533364cfa68dd8f599368bfe9224757d26d19d6bf7be98db1979e824e629e2e` | `sha256:1889fc9d806d18d8df3bd8b715bc7f91c21c9120d4c0756df6414906701713a9` |
| `trie-wildcard-dictionary` | `single-wildcard-word-trie` | `sha256:bad2f9832a38c47d877f2f88870d5b767d137ff603f6a538319076ffccbb7cd5` | `sha256:6dc48553c353f6c25f64c2abd64e0a12a38ad29cc6e5e21b154f0facda494765` | `sha256:56f454ccc71b71a488f2f37f807973a89ce42869756e047094724d555a96cd08` |
| `trie-word-game-dictionary` | `rack-prefix-word-trie` | `sha256:3481fe9ddeaae3cc277f8bfdff6aa4036a87f2d202f0a033a0a3081346ad7522` | `sha256:9f587238f84b8418b0965785585b103b69e353915b1b239cda4de6a5a2b7d8c0` | `sha256:cb1a242220c6c51a716f8dcd7fd91e1a5d0cf2b5246f6f6843671a006eec7ccd` |

## Acceptance Evidence

`primary_core_objective: achieved` for every task-spec-v3 replacement. The
owner source is
`src/w8_biayn/integrations/moonlight_trie_aider_task_materializer.py`, with
case definitions in `moonlight_trie_cases.py` and independent trace/substitute
definitions in `moonlight_trie_hard_rule_cases.py`; focused evidence is in
`tests/test_moonlight_trie_aider_tasks.py`. Per-root before/after tree hashes,
remedy-spec hashes, changed-owner paths, and oracle receipt data are retained in
the 20 `.state/remedy/*.json` records. The family receipt is
`.state/oracle-receipt.json` beneath the re-verification root.

The final receipt must be read as local family evidence only: it does not imply
JSONL generation, split admission, token/mask verification, producer or
consumer verification, training, release readiness, or benchmark uplift.

The current receipt has status `pass`, family hash
`sha256:367aed2f69fb4c1c6bdbf6b455b9c1b91e87e4ffd8a3d0ee4d46b8778e3abc3d`,
owner hash
`sha256:9c72250f9ee2cd200f375743775250f99212ceb08d151eea512eb720d1f3b122`,
receipt hash
`sha256:f1ac7ffd0480813418e97b8522f68e75187b5555044d1e03467e6f64304e7a08`,
and verifier-script hash
`sha256:146699b51e8f6a38c641abaa93e72913c241a0af05ed9cec154aa9dfb3782254`.
It binds every reference, public/private/hard-rule test, topic-specific
substitute, task tree, exact Docker command, image identity, compiler/CMake
path/version/binary hash, and network policy. GCC 13.4.0 and CMake 3.25.1
discovered and passed three tests per root in normal mode and the same three
tests per root in fresh ASan/UBSan mode: 60 positive discoveries in each mode.
All 20 distinct substitutes compiled with three discovered tests and were
rejected by execution. The five-dimension artifact screen records all 190
family decisions with five distinct dimensions per pair; its strongest
combined family similarity is 0.537667. All 520 candidate/official-holdout
comparisons pass, with strongest similarity 0.003526. Prompt boundary,
reference mapping, family duplicate, and benchmark screens report `pass`.
All 20 records report `verified`, `local_family_verified`, and current oracle
evidence. A second owner-side live audit rechecked every bound byte and passed
with hash
`sha256:bd1071d3da1ce03ce5a7af6cfe9fc0bfeea287a17f610f2725da25537847a6c4`.

## Conclusion

The legacy family did not achieve its primary objective and remains immutable.
Every task-spec-v3 replacement reached `local_family_verified` after TRIE-F6's
complete hard-rule evidence path passed. This remains `docker_sanity` with
`locked_oracle: false`, not dataset admission or release evidence. Dataset
handoff is `not_requested`.
