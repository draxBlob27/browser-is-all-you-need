# Interval Scheduling V2 Reverification Audit

## Scope

This audit follows
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` for
`FAMILY_NAME=interval-scheduling` and `FAMILY_TYPE=aider-dsa`. It accounts for
all 20 preserved legacy roots and the 20 one-to-one v2 replacements. The
legacy tree is audit input only. No dataset handoff was requested.

## Legacy finding and dispositions

The legacy owner had only four reference bodies across 20 roots: weighted
selection, first-fit allocation, union audit, and a reservation-vector
variant. Advertised deadlines, travel matrices, cyclic endpoints, containment,
set cover, storage budgets, and other rules were absent. Therefore
`primary_core_objective: not_achieved` and template duplication were major
findings for every legacy root. The deterministic disposition is `replace` for
all 20; no root is retained by changing only its name.

| Legacy root | V2 replacement | Primary mechanism | Disposition |
| --- | --- | --- | --- |
| interval-operating-rooms | surgery-value-plan-v2 | weighted predecessor DP | replace |
| interval-delivery-windows | delivery-route-cover-v2 | farthest-reach greedy cover | replace |
| interval-broadcast-lineup | broadcast-break-stab-v2 | minimum interval stabbing | replace |
| interval-machine-maintenance | maintenance-throughput-order-v2 | Moore-Hodgson heap | replace |
| interval-court-docket | docket-lateness-order-v2 | earliest-due-date lateness | replace |
| interval-charging-stations | charging-priority-admission-v2 | capacity sweep with eviction | replace |
| interval-field-bookings | field-reservation-ledger-v2 | dual ordered mutable indexes | replace |
| interval-freight-platforms | freight-platform-peak-v2 | active-set peak sweep | replace |
| interval-ad-campaigns | campaign-budget-selection-v2 | budgeted predecessor DP | replace |
| interval-shift-coverage | shift-cost-cover-v2 | coordinate-DAG minimum-cost cover | replace |
| interval-flight-gates | flight-gate-partition-v2 | busy/free heap partition | replace |
| interval-warehouse-docks | dock-common-free-slot-v2 | multi-calendar cursor intersection | replace |
| interval-road-closures | road-closure-complement-v2 | clipped union and complement | replace |
| interval-sensor-outages | sensor-k-outage-duration-v2 | k-coverage delta sweep | replace |
| interval-stream-recording | recording-conflict-components-v2 | active sweep plus DSU | replace |
| interval-conference-tracks | conference-containment-forest-v2 | containment stack | replace |
| interval-patrol-routes | patrol-travel-chain-v2 | directed travel DAG DP | replace |
| interval-lease-audits | lease-cyclic-normalization-v2 | cyclic split/merge/rejoin | replace |
| interval-rescue-dispatch | rescue-team-matching-v2 | augmenting-path matching | replace |
| interval-data-backups | backup-checkpoint-cover-v2 | bitmask set-cover DP | replace |

## Hard-rule implementation evidence

`primary_core_objective: achieved` for every v2 root is supported by both
source inspection and executed discriminators:

- `moonlight_interval_scheduling_cases.py` owns 20 distinct public APIs and 20
  substantive references: DP, greedy, heap, event sweep, ordered indexes,
  multi-cursor intersection, DSU, stack, directed-DAG DP, cyclic
  normalization, augmenting matching, and set-cover DP are separate control
  flows rather than renamed templates.
- `moonlight_interval_scheduling_negatives.py` owns 20 complete compilable
  topic-specific false substitutes and four separately unique diversity
  dimensions per root: state model, mutation/selection rule,
  invalid/boundary policy, and discriminator identity.
- Every root has a third independent deterministic oracle executable in
  addition to visible and hidden tests. Behavior-only roots use independently
  derived direct values or bounded adversarial expectations. The mutable field
  ledger maintains a separate vector model and compares return values plus the
  full observable agenda after every book, failed book, failed reschedule,
  cancel, successful reschedule, and absent cancel operation.
- The locked verifier configures each `.meta/negative.cpp` through the same
  public header and CMake graph, requires compilation success, then requires a
  nonzero CTest status and positive failed-test count. Marker/grep/source
  presence is not accepted as discriminator evidence.

The first locked attempt correctly failed because the weighted negative
fixture triggered strict `-Werror=shift-negative-value` before tests. The owner
was corrected to use a defined negative bound, the family was regenerated,
and the complete locked matrix was restarted. Only the later clean receipt is
admissible.

## Semantic and holdout screening

Normalizer `interval-family-semantic-v3` noun-normalizes actual documentation,
public declarations, reference control flow, and test assertions. It checks
all 190 v2/v2 pairs and all 520 v2/official-holdout pairs from the available
pinned 26-root C++ checkout. Only `test/catch.hpp` and
`test/tests-main.cpp` are excluded as shared support; their exact digests are
recorded in `.state/semantic-screen.json`.

- strongest family pair: `broadcast-break-stab-v2` versus
  `maintenance-throughput-order-v2`, similarity `0.6793760831889082`, below
  the blocking limit `0.72`;
- strongest holdout pair: `backup-checkpoint-cover-v2` versus `sublist`,
  similarity `0.12594187298170076`, below the blocking limit `0.68`;
- whole-slug and content screening: pass;
- prompt boundary and role/reference mapping: pass.

## Locked oracle receipt

Command:

```bash
W8_INTERVAL_GRADER_IMAGE='w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991' \
  bash examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh \
    --force --verify-core --verify
```

Result: pass. Receipt ID
`sha256:5e6a68fdf5a02e171b7257b3c6c390d78854f1bf90ecb683ec2c2604874a3941`
binds archive
`sha256:b4088d2108a0f7893dc353fe1942551b23f2199f2ab3ecd274b1605004203ae9`,
generator
`sha256:ffeb960f9c5a0407e83714f566cc2d16a5fb641b3f6d06a20601ca4a410a1422`,
all owner hashes, exact Docker and per-mode commands, verifier-script hash,
task/reference hashes, and test-output hashes. Runtime identity is immutable
image `sha256:4cff5e0d...967991`, GCC 13.4.0 at `/usr/local/bin/g++` with binary
hash `sha256:152d9e7f...ebf663`, CMake 3.25.1, and `--network none`.

All 20 roots discovered and passed three normal tests and three fresh
ASan/UBSan tests. All 20 negative substitutes compiled, discovered three
tests, and were rejected by between one and three tests.

## Per-root hashes and outcomes

| V2 root | Legacy tree hash | V2 tree hash | Remedy-spec hash | Negative failed | Status |
| --- | --- | --- | --- | ---: | --- |
| backup-checkpoint-cover-v2 | c1b7c19f7b4c895fa341f80ef459b19893484bea2c24dade9672ded8e3375b63 | b11a3ea0965971d1762bcff2d33de11665017f545b8462c338a9a96fdcc9edfd | a89c64e867a2e4474dc901d6df3225b0bec208825fe8f968aef22a44d954a517 | 3 | local_family_verified |
| broadcast-break-stab-v2 | a8222b9559da6ab33a3e70111e328606b8301e5552435899d6e31e61a05fa85d | 36464f973d50aa851a88eb0f0258200dab592a0908a6bd486f4ab9e8df274ed2 | 5473acdd2e5398e809678cb67e4c04e7c26f76c7b771a62d81b15041d5414d8a | 3 | local_family_verified |
| campaign-budget-selection-v2 | de524d61dd7bfac011c4db11baa0508323d9775a30ef8a1a5f03a0f845c521c6 | 68f6f4bfa2ca9999696c16cbebaadc73e6b6d124922dd996a872e8c65c8b7947 | 0e3986af35c3bb566cd0a4464ac9d8daf4a7547ec68a748ee9d446376770e6af | 1 | local_family_verified |
| charging-priority-admission-v2 | 8cc02b2b316e9e130be5d0507b5b8154fd86f537af599bcc56b6b4c4552806b9 | 22bdad4448991423509b0f883c5e97dd27ba4950c63b4877e946bc0170dcd6c1 | 68a2d0f5bf6745e7528fdc62e68fe8e5aa6e5c5280baf61bf9c8d4422666badc | 3 | local_family_verified |
| conference-containment-forest-v2 | 5a17dd0910569144e61cc25185a19e294d53d9f7475e3210adea47407b28f275 | 94f85a5762da8e5e513c8658724ad594e2ad0decbc69100f8362ca9e53d8aaaa | 2344ee707cbd1872a347da827c8c3da6dece4c2298f3ded61678f6e98cb9ae93 | 3 | local_family_verified |
| delivery-route-cover-v2 | 404aec55b3a83364a8c752f8f97e3464771ed19059f2bb9911e1d35eedc4a928 | e00c8ad8f0d6a18fb74109699b70b27495b92794fdff358e541d953e7f952304 | 5fbc7269e0e8e275457d1500eeba4952e5a772072ae8f3d245197ffda67b14a1 | 3 | local_family_verified |
| dock-common-free-slot-v2 | bdcfc9202c7848eb0d91f883d7e5457bdfa4570f57661f8456b01b16830b22bb | e2834897f93fb3b7d78b9f04889a954ac9238f678f338d11dfd0137256772cdc | 8e50f67d28c1b252b954c86da5356e0fe6c64edb4e69ba658a697230397ca63e | 3 | local_family_verified |
| docket-lateness-order-v2 | 25d91b798aee1dd9978905d8dbf8f7f285bfcef91aac39ac0e8cd22c183d865b | 9f9b85eb4d406e250cd84150688d8da8ec6bc6cce95450ae21cf826a5d103225 | c851ba280bb73eb79d28aac490c4e2716de23f5acc7d0bfcb9a2efe3fad199df | 3 | local_family_verified |
| field-reservation-ledger-v2 | bfaf4b3d4628af049e5afa3293dd1465ad5e0c74f7105eb002600cdae999652e | b0f186436e676a1ebdd2ea7e85f61ebcfbd9a3d29be58cd6257ee88ddd75db59 | 0bddb3797e9dfe6cfbb49543248809d1a37ef6751ec0fa1b7c5e4c005aad7822 | 3 | local_family_verified |
| flight-gate-partition-v2 | fde33f463621b1633bbd88cfed76c8472412d0b4d8cf9678cf4e6aa9c7c409dc | ef273a635a93411a3e9fe1bc22c07cf49caae85f123c6822f4c5ebd7e2c819ca | fcd6c1e0b6e319d91a3d07864639b8fd85345cfaf6379e9e8f0a056051483c09 | 3 | local_family_verified |
| freight-platform-peak-v2 | 851f98533f3274978cba273f9491e7e7b86c539c5cc5e0b6ade3f14ab5bbb17f | e7091d7ecc06cbbcbb092199b4170d67408fe6928a846bf23a8a0f52c2c97126 | 47d3f47e3d45418de81cb2ce591ba88ca02f96ad3f8fbfbd1db458814ad4f3b3 | 3 | local_family_verified |
| lease-cyclic-normalization-v2 | 1faa65c7c02510d8cdc475e82c535b5a896ce272766aa57d83fcc896b43965cc | 0d1b9eee90a8d1d1f1df110bbdc371c17e0f9c9bf3937bc59c1cd300100dd4dc | 836bd34250a6419bc1f942f6a3692e703b4a10d0fc04ea0c5736fbbab7b09043 | 3 | local_family_verified |
| maintenance-throughput-order-v2 | 1d0d46caac70d74df70c3a649176e006a2a57e90fed0d01091c12c59aced86ac | f321bd85e06c590e77bc38ab9ecbd57f96de657d2facf39c0f3ef09b93c761bc | fa511f7cfabf9dccf840cef649fddff37d541adab00c531acdbd0d15d74c8c6e | 3 | local_family_verified |
| patrol-travel-chain-v2 | fcd416107ba30c1efeb43556658e275207e48d75aca2874477e7e1e423a243de | 263d4145c9673938c4cef61ba599629e5da12d1c355b46f2ee22a5ec27e00419 | bb6caf6ee336d330d33edad62f8780b791b1f4b9f9ed5fa92c605f9fdf63e6c7 | 3 | local_family_verified |
| recording-conflict-components-v2 | c79a48cf575b13ace083360fa63868927e5df42796e3c153d5b1b6fef5004a4b | fb88bcebcbe95c92aea3bfa482176858059c1b4e1b23aaf0bc21a336ffdd2791 | fea97f795c5e08fcdf1dff45dd0b97fe3e466a64f54fe741a008fb351c391d23 | 3 | local_family_verified |
| rescue-team-matching-v2 | 190aaf6d81bb6562152fca0b5fa5620396772d6d17028280588aaf6c9cebe686 | e94b0bb263c510b12b7fb23761c119be55931bbda3c65a0faadd43df08e73c31 | ab29609125691dc2763bc44bddc8c2c075223a6dea9e4ccb63da6e1d177a44e8 | 3 | local_family_verified |
| road-closure-complement-v2 | c1a882a15a44e22f1eca2eb61f10ccd17eb805437d23e7f14dc939acbb942388 | 1da52e535fbd649a598eab6c8a37c89e4b87d9a0619e6d3982db1c9df0680ae5 | e040c344342e3c65157635ba225490cc2d3730187331dc6749cd0c2e7e42a7ce | 2 | local_family_verified |
| sensor-k-outage-duration-v2 | 9d0e38e6ad3eb5f02954bc70503bc1a90a2b1cf79f51a03d517732ac916ef23c | 0b4c0418c7eac062a91324f8d3002e09f3cc8f9f04163bcb446eee657a5336e2 | ab1e0aa97df26e43aebf09556719af957b61878175c209ffda5602d96063839d | 3 | local_family_verified |
| shift-cost-cover-v2 | c7eef70c998092286487dc6e1d0dee80b0ba969d6fec5ae2474f6f28da4305f4 | a57e8caf8e070e2d779b0bb1c6b3b1bcb1836644b707423cd50cc29c5e059b8e | 4e8c3b67d212fb62812f33044e6560849744e78550b2059e9f95a931581ad14c | 3 | local_family_verified |
| surgery-value-plan-v2 | 4995c1c888ec0067477abf92903be35d7eb350895ce75a064fd25bd4b64b860b | 0e79fd6716f9d826ea37eff1abac55be050f0566add5c22b3d774f3f299531b4 | 56c2114808a596aa9630f8ee5ebc7965af955c529e0a6a9438e4d1a1a9544a1c | 2 | local_family_verified |

## Changed owner and test paths

- `docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_INTERVAL_SCHEDULING_CURRICULUM.md`
- `docs/AIDER_TASK_MATERIALIZATION_GUIDE.md`
- `docs/aider-tasks-spec/aider-dsa/interval-scheduling.md`
- `examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh`
- `src/w8_biayn/integrations/moonlight_interval_scheduling_aider_tasks.py`
- `src/w8_biayn/integrations/moonlight_interval_scheduling_cases.py`
- `src/w8_biayn/integrations/moonlight_interval_scheduling_negatives.py`
- `tests/test_moonlight_interval_scheduling_aider_tasks.py`

The owner regenerated all task files and mutable evidence under
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/interval-scheduling/`. The
preserved legacy root was reused only as immutable audit input.

## Conclusion

Every v2 root has `primary_core_objective: achieved`, is structurally valid,
passed prompt/reference mapping, passed executed topic-specific negative
fixtures, passed locked-image normal and fresh sanitizer oracle checks, and
passed normalized family and official-holdout screening. All 20 roots reached
`local_family_verified`.

This remains local candidate material only. No JSONL rows, token/mask evidence,
dataset release, training authorization, or benchmark-uplift claim is made.
