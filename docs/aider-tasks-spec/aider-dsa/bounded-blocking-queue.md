# Bounded Blocking Queue Reverification Audit

## Scope

This is the completed local remediation re-audit for the legacy bounded-blocking-queue family.
The selected workflow prompt is docs/aider-tasks-spec/prompts/remediate-family-reverify.md.
Legacy output remains audit input; only the parallel reverify tree was regenerated.
This is local task material, not a dataset release.

## Commands and results

- Materialization wrapper with force regenerated 20 v2 roots under the parallel reverify tree.
- Focused and scope tests: 8 passed.
- Prompt and role inspection: 20 roots, 20 distinct semantic profiles, no prompt or answer leak.
- Generator-owned core verification passed: strict whole-file rejection,
  role/reference mapping, fresh-materialization tree comparison, semantic
  duplicate signatures, the canonical 26-root benchmark denylist/content
  screen, and remedy-record/specification-hash validation. Its receipt is
  .state/materialization-manifest.json.
- The owner verifier completed in Docker image sha256:4cff5e0d746a with networking disabled.
- Runtime: CMake 3.25.1 and GCC 13.4.0.
- Every reference passed a clean normal C++17 build and a separate fresh ASan/UBSan build. CTest discovered two tests in both modes for every root.

## Findings

### F1-template-duplicate — resolved and reverified

The old three-shape template was replaced by 20 distinct operational extensions:
statistics, blocking batch, monotonic submission, end snapshot, close-and-drain,
exact batch, admission ceiling, queued replacement, unique pending admission,
nonblocking submit, cancellation, source accounting, nonblocking take, close
reason, resize, immediate flush, blocking peek, threshold take, ID claim, and
pending discard. Each extension has a distinct public declaration, behavior
rule, reference operation, and public negative case.

### F2-extension-contract — resolved and reverified

The prompt describes the actual extension behavior rather than a profile string.
Private tests prove both full-producer and empty-consumer blocking with bounded
future waits, close wakeup of a blocked producer, and a multithread no-loss
trace without the former shared-counter data race. The monotonic trace uses
condition-variable ordered producers to respect monotonic admission.

### F3-oracle-reverify — resolved and reverified

The network-disabled Docker owner verifier wrote the receipt at
.state/oracle-receipt.json. Every root has equal positive normal and sanitizer
discovery counts of two and passing reference executions.

### F4-enforcement-gaps — resolved and reverified

The owner now fails closed with stable reason codes for malformed whole-file
answers, unsafe roles, stale materialization output, incomplete remedy specs,
duplicate semantic signatures, benchmark ID/content overlap, missing
invariants, and oracle discovery mismatches. The mandatory checks are no
longer report-only assertions.

## Per-root evidence

| Replacement root | Operational mode | Legacy tree SHA-256 | Reverify tree SHA-256 | Strongest status |
| --- | --- | --- | --- | --- |
| bbq-print-dispatch-v2 | stats | 7bd45c801ec40bfa5a5c74a774aa3ad04f7b9ce1b207e5a7f4b0c9faa9b4fb38 | 8acda0736aa560df1b1624514199e1128c37efea226bb406330d581f605af015 | local_family_verified |
| bbq-image-upload-v2 | block_batch | 15faf301464716cd98084b57d7c46e9fe9597c6c71d52317ed3dceaa96392e81 | 0222dc067f80a3b8f62ba695b69a31ebef18a0082fc57b630e466282654c482d | local_family_verified |
| bbq-telemetry-ingest-v2 | monotonic | c6032fd1e3f8b72096ffbf3777e57ce8108989aea89e71b67639eeaee3fdb1b7 | 6d22ccb36139a28ec522159db5a744499a7da788c44f650f554d055c0a35d398 | local_family_verified |
| bbq-audio-processing-v2 | end_snapshot | 4a854ee7223a42c402cee275ff7722ebf60bfde72028dd99bcbeddffdc9be12c | 6e72b3261c3ffc298452dcece7ea9a2d6ba20bd134b116786455316916e9c06e | local_family_verified |
| bbq-log-writer-v2 | close_drain | fc55a40507967d6cda05024f566b4235eb8c48063259789ba159e5ebe7ec5af9 | 85fe8b4e483004d7cf93897cbe1c536ed9942e587a39bc80793f3314f5618769 | local_family_verified |
| bbq-order-kitchen-v2 | exact_batch | 3fef6b09180ce09c09bffe1a67884a9dc8f81e7d0698aa28488af94615900167 | 5150e9fd8d86e16f96d8fcdb006f174552adb229eebcdcb874184bdb49ca4453 | local_family_verified |
| bbq-build-worker-pool-v2 | ceiling | d19dcd6b9580ccc725d3ad25d21a8f46e8e50797d22592f6ee8a97c4badb0a8e | a1d8b2b2f64542751d81cecb83673ab8639cf2baf0395b69b8c370b72ed73d6d | local_family_verified |
| bbq-email-delivery-v2 | replace | 4ea1f47e87b061a1e06f0a0d7313a8d58cc572a15ede1b0629fd113f80244588 | 12f789fee6769d8a0d38a8d6747d7c99e5e689c1e4206ac546d9bb106e6be3d5 | local_family_verified |
| bbq-document-indexer-v2 | unique | 3da8d68561258b97e067eaf1d44ba9b0d5bbf7f877b6161ded66002f8d6a7852 | ec5ba347b57ea23e0d4b8aac31efb18d7fe3f77ee0ab964d93e2de60bf5393e1 | local_family_verified |
| bbq-network-message-pump-v2 | try_submit | 403f09ba4679ab24ef31b8f3450ebb83f0224f1c8bb49b4393e91e4caada6fda | 73769d4217c14dd4ab064311db09f237dcd26025243c4027a7b6c16bf8e88ddb | local_family_verified |
| bbq-customer-support-v2 | cancel | 6371fea7cb6a4aae1996e0363534dfd059b9dc6a2e1bbe345df634a501afdbf3 | 35d3830daed2f173dd6686b9cc0793f855bc46c53e8e9a9821f70fbfdb41a8f1 | local_family_verified |
| bbq-sensor-fusion-v2 | source | f1b46a6efd7b029076827dc3ecfc9f08beec333fa373d78174f5807cb2dc1b5f | 35bb62c1216c1d1f544ddebe0b14f7b2c82c7812570f93b39cbfe83b613351ab | local_family_verified |
| bbq-video-transcode-v2 | try_take | 630c4e0a8d7826365324e086e8126b0a5f0af3c0bf891d7e4b35bf7d8ddd6f4c | b8fc7f547dff8a1492297c2df3259244377d48925507fb0a687c03e6388a94bf | local_family_verified |
| bbq-payment-retry-v2 | close_reason | 52c60ec26d1143768272d4bc6c59b8ca34f82c9de10d80456a118f6a1ab3f5e4 | 6e016ee872e3571a7a98be2c285ffdcaa56c1d01cf63e6585468ba9c8c47e546 | local_family_verified |
| bbq-route-calculation-v2 | resize | 60ac4d84c6a7acd71e335cd2489276c58c9c397aa56b75f496e0a11a63d2e41a | 847a0f2194f347d45720e788bd61196ff100a995890bcc4158feb9e67cf7707e | local_family_verified |
| bbq-database-write-behind-v2 | flush | 2e724a479e6bb5b6715721025fe0335d532bd83798008582ecb92aec8e70b42b | 2a7cd58554245c71dd6a3cf2ca14e80f1ca2f96cb84e560e0db466e5c87c3c8e | local_family_verified |
| bbq-notification-delivery-v2 | peek | ee8046ba0e018ef06cd8737ba229b695c1a7f5ecc0179bd958a9f73794c70068 | 9fb5c9a12043a2c0b9b433b2a3a1c85ee3bb72eaf234c80371fe6006466bb70c | local_family_verified |
| bbq-file-scan-v2 | threshold | 082f8c81fb911c551ab40a270e49cf0ed9d75ef88bec866f5035fd3d9c7ffbe4 | 716e1b982342de9fac1f6edf38e53f802508d741e75fbef5cc19ea6a387ad6a2 | local_family_verified |
| bbq-fraud-review-v2 | claim | 28c9246b386c7454e3bf86fa50fb7898cc883b8369808862053b2694ade35c5e | 900dc7eac4535f42d80ccd016f60c9080acbd26b46a09c69f5b6f971d79aa844 | local_family_verified |
| bbq-warehouse-pick-v2 | discard | 395618733836472e3db69bdfbd3d7ed97e389feeac4a79d2fa76d07cc3379f5c | cc0cd57e21e187dcb8579eee1a58e3a86b414f354309acffaab7f0aaeac10d6f | local_family_verified |

## Conclusion

All required local-family gates pass: prompt/role boundaries, reference mapping,
normal and fresh ASan/UBSan oracle proof, negative fixtures, duplicate-family
screen, and benchmark separation. Each v2 root is local_family_verified.
No dataset handoff is requested.
