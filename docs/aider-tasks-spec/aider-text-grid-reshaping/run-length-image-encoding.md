# Run-Length Image Encoding Family Remediation and Reverification

## Scope

This audit follows
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with
`FAMILY_NAME=run-length-image-encoding` and
`FAMILY_TYPE=aider-text-grid-reshaping`. The legacy family under
`.w8-biayn/data/aider-tasks/` is immutable. The owner generated the v2 family
only beneath `.w8-biayn/data/aider-tasks-reverify/`. Dataset handoff is
`not_requested`.

## Findings and dispositions

### IRLE-F01 — shared encoder/decoder template

**Severity:** major. **Scope:** all twenty legacy roots. Legacy references had
one raw-row encoder or record decoder, one shared report, and aggregate-policy
switches. Domain nouns and selected metrics did not establish distinct core
implementations. `primary_core_objective` was `not_achieved`.

**Disposition:** `replace` every root. The v2 mechanisms span encoding,
decoding, BFS/stack traversal, scanline merging, dynamic programming,
integral images, monotone stacks, union-find, interval algorithms, and a
maximum-bottleneck search.

### IRLE-F02 — semantic family duplication

**Severity:** major. **Scope:** all twenty legacy roots. Shared headers,
reference flow, and generated tests made the family noun-renamed capacity.

**Disposition:** `replace`. The owner compares all 190 actual emitted-artifact
pairs across seven logic/implementation dimensions after removing n-grams
shared by the complete family. The strongest combined normalized overlap is
`0.393136`; the strongest single dimension is public API at `0.775`. Both are
below the fail-closed `0.82` thresholds.

### IRLE-F03 — no executed topic discriminator

**Severity:** major. **Scope:** all twenty legacy roots. The legacy tests did
not compile and execute a deliberately wrong substitute for each advertised
algorithm.

**Disposition:** `replace`. A post-remediation audit found that the first v2
negative files were generic starter copies, so that evidence was discarded.
Every final root now has a unique task-specific false algorithm and a guarded
discriminator. The discriminator is first executed successfully against the
reference, then must reject the false algorithm with exit `1` and no sanitizer
diagnostic. The three mandatory clone classes are both rejected semantically as
`duplicate_family` and compiled/executed in clean normal and sanitizer builds.

### IRLE-F04 — host-only, unbound runtime evidence

**Severity:** blocker. **Scope:** all replacement roots until Docker proof.
Host CMake was unavailable (`zsh: command not found: cmake`), so no host oracle
claim was made. Fresh Docker rechecks exposed hidden-only negative coverage, an
untested density tie, a crashing combined negative oracle, and an ambiguous
two-symbol opposite-order clone control. Each partial attempt was discarded and
the owner/probes were corrected before the complete run.

**Disposition:** `replace`, then rerun the complete owner gate. The final
network-disabled pinned-image run passed clean normal and fresh ASan/UBSan
verification for every root.

## Per-root evidence ledger

Every row reached `local_family_verified`. Exact mutable JSON/Markdown records
remain under the generated sibling `.state/remedy/` directory.

| Legacy root | Replacement | Before hash | After hash | Remedy-spec hash |
| --- | --- | --- | --- | --- |
| `image-rle-circuit-layout` | `conductor-pad-connectivity-decoder` | `sha256:723c49a7ac4b52fc9462b674b844071e2f6d17444637d83853c2008512768f2c` | `sha256:d16ba71e3aa3113e84d22f5ae804ae19cde3e3c0e2f9d574e5d617c020c03f5d` | `sha256:564488e37a66635c8ed03e07cba0417e5b3b7a5da023b5f7d8273e94ecf7e08b` |
| `image-rle-coral-survey` | `coral-component-histogram-codec` | `sha256:516a1a25fa3ac14660f7cc37598a2274393a0a24a385177b611595e1c5e15bea` | `sha256:4fe3c1de413f0a23ef5e64e54a60c2580e55e910d46b775fa218e817bb4daec3` | `sha256:237a0ceff47a9cc0919c33e9fee33cb859387bfac8db918fab643ffa00656b09` |
| `image-rle-farm-map` | `crop-row-histogram-codec` | `sha256:45b027a8aaa7cb2cbf59ce410485369e5f8968d072d47423ce2d1fb9bee2dece` | `sha256:a8bf6a507fc9d56439af95ec4436cd02aec2044ae6b8836b9991d542681eba36` | `sha256:579630e20d14147bae32fe8d51bd522cf980085bc9643540528189316db90791` |
| `image-rle-fire-map` | `wildfire-border-perimeter-decoder` | `sha256:f830004be5ed92c3a8fdcd2091187ee827a4e1b14bdc450e050137bacb7c70d1` | `sha256:c9b5b3adba8500a45bf591934ff8c27ca167761d35e1f3013dabb9a5b75df572` | `sha256:7638cdb5f5bfbfc2be98918a01eef1e6030265503fff12f7400124c133ae5970` |
| `image-rle-floor-mosaic` | `mosaic-palette-row-encoder` | `sha256:1f8df756ca1fcdbcd410c84db31591f698f70276cf734ee77e2d1c35f6b05038` | `sha256:bb3067b8b6c2fd0324b74dbaf1c22545e25edfbf4a2ba5a1aeefe2d9540c5299` | `sha256:07e693c57def701375d30dc84fc6a13970627c81e26d395c2fc63036ecd2a120` |
| `image-rle-game-sprite` | `transparent-border-crop-decoder` | `sha256:55cd76418591af48f1433bc340b2155d9251b0d6b3565cc96a9cada8ead5b855` | `sha256:985c4cd1682c7f0849f74726c0a7e1b72f40275d20581c951c029453c24e0ca4` | `sha256:87bfb5e70fa2e32bee7d0d1ae7c4dbddc26065e726e4e519342b34e53dacbea4` |
| `image-rle-garden-irrigation` | `dry-bed-span-merger` | `sha256:ea12e5a794bb8dc6a3a58503f63a9e8a437cc6be1a5d960406233f9612f980f5` | `sha256:457e25f3f39ff74fc52feb0bca031e4ba263ac8aae122a036458b31eafa9620c` | `sha256:27c6cc96639af581603a14de169a36d1537831cfb1162a6bce1baeec5f4eecb2` |
| `image-rle-harbor-depth` | `safe-channel-widest-path-codec` | `sha256:75bd26ac36ac369255fb2520093a2006acd233483a53579be1c0c67d1ff84ff4` | `sha256:1e989a6b7fd326627b15ff5566e3e99f1d763d292004cad496aecbdaf7ffbeda` | `sha256:5cc8520167b409feb82c9d232dd2baf6b74cf87e2856e715e567187c2a86a63a` |
| `image-rle-library-shelves` | `shelf-empty-span-index` | `sha256:9cd556f641288ea469f23c99d7ccca15121651a6a17defd776da781db017ea15` | `sha256:55fa8e89fb98dba2cb60f5d4be668f4b35a4becb2c9994260a50e8db70333ead` | `sha256:3b03344777f71a1ac5122cfec70a1763c28cf3236c44e6e6eed6f7ed8da7b6e4` |
| `image-rle-medical-scan` | `lesion-component-boxes-codec` | `sha256:a4bf0e295779e66afaf4f783fa1195aa185a0d87f0ca39e2d0eb845417a44d68` | `sha256:e1b78e7ba3cc6104a57e0d14faae5f75e5ace51408584b3e8f85277ebcafccc7` | `sha256:0029c4d2b0041b959fbaa14c9b593c712b832dcda1d35558b83f680511371fcb` |
| `image-rle-orchard-drone` | `canopy-block-density-index` | `sha256:bec04f46a80c0f23b632a4ddeded68266bd07c18af9b8ddea436f207ca78ce00` | `sha256:27e40cb49637c2baaee6d1dff0b4cab1deb3fd83f3e4e214087ac3b57fc3ae23` | `sha256:4952e649d24a3ac8a01b4ac5bb85a074d91d9290a95f2c9dde38465be4fa7d54` |
| `image-rle-paint-inspection` | `panel-defect-interval-decoder` | `sha256:d992c744e089ea73f43326445ff9f466d09fdb65a9b8e82e8aca857ca7ffc8a5` | `sha256:41dc76c6a3fcb0bd3aac64c13b87db55d920c07d52a4dbb91b913f576610a72a` | `sha256:82104a28de123e0a25cb3c254248300f5c8ae68dd70b4a25083dafb44631853c` |
| `image-rle-quilt-pattern` | `quilt-seam-transition-canonicalizer` | `sha256:4d40e7f33598b86ac2d8950011cad9dac88ebeedd34dfa7914a1a2e49bcedb62` | `sha256:b0d3b40be4f9a960c4aada2e8a9010baf32c83ad059ad02bfcff5bf1c2ddeaa9` | `sha256:443b2d0a91e5bd8545867cfafa0e0ec211057c3da1a12af8831e4c4d53159a06` |
| `image-rle-satellite-clouds` | `cloud-clear-window-decoder` | `sha256:7cc137471a22cc42b1c0e860e4a728ca046344273f2dcc1abd21cfa6f9e89573` | `sha256:4595df8189b6a08ca6a32bbac5174259d6d9a194744c6202a46bc9c99f3d8e10` | `sha256:1f202df966e3ccfba9ecf30cb2c28d5b081360d8b0044bbd7b9290a660389fb8` |
| `image-rle-seat-chart` | `vacancy-rectangle-run-index` | `sha256:ee1ca1c6fbebee02f7cfc1cb3373f7e099ea2d85306a6afd31d2736c76d538a9` | `sha256:b3c73418400bfff6d9839ad4fbe9d17bb0f9bcda8434205385f143f522a3f0e1` | `sha256:ee651dde47b1a982eae0a7b91138ce2358724eeb0d6e898410f2044d9badccb9` |
| `image-rle-security-mask` | `mask-component-bounds-codec` | `sha256:292e0d94ade77c7ee73ec718e03488813784a0800c218bca228dc4fc4fdfa05a` | `sha256:f4f62eb33331f231c9f61c4b008ccfa9a17176abe7106bbd3eb2f71b75f1e46e` | `sha256:57536f3fa0ad2024445f427255d5ef27215f568c83c3f130909e0d6ae91c6466` |
| `image-rle-snow-cover` | `snow-map-delta-codec` | `sha256:329b7e1e4dc65ebeef7a13d0a4a9067b910a3ef6e21584e244c38e1bab4b1eff` | `sha256:0110db0a68d5b3cbc4ac882f0c7043136c6e984fb4c95802db2fe51d7aa329fd` | `sha256:975d6bd9b7de2090f4f13ba597d258572647befb0e829697bce732584eca9cb8` |
| `image-rle-traffic-camera` | `lane-blockage-run-auditor` | `sha256:6b5ca5a669bb3d8a588130e48d48a6fb0449f78c563a83eb46da781e24fec486` | `sha256:27c7e982cb5162ddb5664c7f9d2b6e4b0d7fe1e0f86096678e81f7c022cf8d91` | `sha256:b935152d2672dacb0f99341227854da4b34054a6446e2ac66204d7aa4de7fa18` |
| `image-rle-warehouse-plan` | `aisle-reachability-decoder` | `sha256:8d0b2599fbce3bb97ca80f1311abc7a4a2a27cfa33127ae61b391d30966fdce5` | `sha256:d612f97d9190a0aa0ac84efb031df0f7171442a678c8273b54bf39f8e686c739` | `sha256:f0aa16ab1f1491546236c535c6adcc3a91cfc13948cfcf7d7b95e8862427446b` |
| `image-rle-weather-radar` | `radar-column-threshold-decoder` | `sha256:ac860de7c98d792f71d6412a70bd45d3bf2351411e767cfe584913b39812357d` | `sha256:50143225ed93701632f683d8ecf20f745add412c7a209af9414487ace81be64b` | `sha256:70f4effc0d9f62c6b665ed8858c711dc39086fc091dd09ca8e65036bc3fa8d57` |

## Exact verification results

- Focused tests: `14 passed`.
- Owner `--force --verify-core`: passed prompt/role/reference checks, all 190
  pair comparisons, the three clone controls, and all 26 holdout screens.
- Docker sanity: pinned image
  `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
  network `none`, GCC 13.4.0, CMake 3.25.1.
- Runtime counts: 80/80 normal task-root tests and 80/80 fresh ASan/UBSan
  task-root tests. Each root has four positive discoveries: visible, hidden,
  discriminator-on-reference, and expected-failing false algorithm. All 20
  false algorithms exited `1` in both modes with no sanitizer diagnostic.
- Clone-control counts: 12/12 normal and 12/12 sanitizer tests. Domain/API
  rename, constants/policy-only change, and opposite-end selection each passed
  their transformed reference contract, rejected their false algorithm with
  exit `1`, and were rejected by the semantic screen. Independent focused
  assertions confirmed nonempty byte changes across every required emitted
  role; the receipt stores each exact changed-path and changed-role manifest.
- Mounted-byte reconciliation: all 20 owner tree hashes exactly matched hashes
  independently recomputed by a separate runtime process over the mounted
  task roots.
- Family screen: 190/190 pairs passed; strongest combined overlap `0.393136`
  and strongest dimension `0.775`, both below `0.82`. The strongest benchmark
  holdout overlap was `0.355932`, below `0.60`.
- Generator hash:
  `sha256:0cc49d2b4ed6bce8d57dcda9d9489c535fc9285a3808fce5654832a2bd093d8a`.
- Owner hash:
  `sha256:6ab3123b233e7dddc44bc3d737950d22f9add42289d166cba5b9f5aab02aada9`.
- Case-source hash:
  `sha256:c1dce7afc055d27fc923310fdbd70f78c11a7fd12c78db76787593e05446f221`.
- Family-screen hash:
  `sha256:ac5bffead36018fcbbe62660b24e7036fdc4170182fc9be85436e61d1e51e220`.
- Docker-sanity receipt hash:
  `sha256:3db14eae1233ecb82e914c0e09b10d03b1a21e0e37f9f4c3ea540ebbda450d14`.
- Remedy ledger: all 40 legacy/candidate records report `verified`,
  `local_family_verified`, and Docker oracle result `pass`.

## Conclusion

Every replacement has `primary_core_objective: achieved` and reached
`local_family_verified`. Prompt boundaries, reference mapping, reproducible
owner output, semantic diversity, executed false-substitute rejection,
normal/sanitizer oracle evidence, and benchmark contamination screening pass.
No JSONL row, split, export, release, training authorization, or benchmark
uplift is claimed.
