## Scope

Add cryptographically signed, expiring, single-use approvals around the paid
Lium 8x H100 workflow. Gate 0 must authorize the exact provider booking before
the first mutating Lium call. The on-node preflight and screen gates must bind
their decisions to the exact runner requests and evidence.

## Why

The executor and sentry are separate principals. A JSON file that only echoes
hashes can be forged or replayed by the executor, and the existing hardware
preflight necessarily happens after a pod has already been booked. The
supervisor therefore vetoed paid execution until booking authorization and
on-node approvals fail closed under tampering, expiry, replay, and concurrency.

## Acceptance criteria

- [ ] Ed25519 approvals use canonical signed payloads; private signing keys are
  never committed or exposed to the executor.
- [ ] A pre-book permit binds the exact executor, provider/profile, `lium up`
  command, provider executable hash/version, sanitized environment, working
  directory, 8x H100 request, TTL, budget, source/runtime/data/checkpoint
  hashes, parent request digest, principals, stage, request ID, nonce, issue
  time, and expiry.
- [ ] The Lium wrapper verifies and atomically consumes the permit before any
  provider subprocess can run.
- [ ] Permit validity is at most ten minutes, the consumption registry is
  fixed rather than caller-selected, opened as an owner-only non-symlink
  directory, and used through a held descriptor. An exact active allocation
  name blocks deletion/replay during the live permit window.
- [ ] The provider credential travels only over bounded stdin and never appears
  in argv, environment, files, logs, output, or receipts.
- [ ] Raw provider `price_per_gpu * gpu_count` proves a positive rate within the
  signed cap immediately before and after the exact rent POST; missing-field
  zero, pending price changes, and pre/post drift fail closed.
- [ ] Automatic retries are disabled for the rent POST, and successful creation
  must reconcile two snapshots to one unique allocation after cleaning any
  same-name duplicates.
- [ ] The outer wrapper reserves terminal evidence before permit consumption;
  every consumed timeout, partial output, lost response, or local artifact
  failure reconciles all newly attributable exact-name IDs to confirmed absence.
- [ ] The initial terminal reservation persists the exact validated pre-snapshot,
  allocation, permit, and expected-claim bindings. A kernel-backed exclusive
  lease is held from before claim consumption through terminal finalization, so
  crash recovery cannot race a live launch wrapper and automatically becomes
  available when that wrapper exits or dies.
- [ ] Unconfirmed cleanup has an append-only, exact-parent retry chain. Cleanup
  authority survives Gate 0 expiry only when an exact consumed claim was created
  inside the permit interval and either an initial reservation or failed-cleanup
  receipt proves attribution; expired permits remain unusable for launch.
- [ ] The permit binds one absolute, regular SSH public-key file by SHA-256; the
  exact key is passed explicitly through the installed Lium SDK and only its
  path and digest appear in provider output and receipts.
- [ ] Provider script bytes execute from the verified open descriptor through
  the hash-bound interpreter; the Lium SDK/CLI versions and explicit bootstrap
  template image, tag, and status are verified before mutation.
- [ ] Artifact-bound shutdown uses an absolute hash-pinned interpreter with the
  required Lium SDK, not `env python3`, and a sterile-PATH production test proves
  exact-allocation termination plus exclusive receipt behavior.
- [ ] Tampered, expired, replayed, wrong-stage, wrong-principal, wrong-command,
  and concurrent-use permits fail with zero provider invocations.
- [ ] On-node preflight and screen decisions bind the exact request and evidence
  hashes, parent approval, Gate 0 digest, and provider allocation ID, and are
  domain-separated and signed for single-use verification by the runner.
- [ ] The booking parent binds distinct Gate 0/Gate 1 keys and external
  source/runtime/data/checkpoint intent artifacts that reconcile to prepared
  Gate 1 evidence.
- [ ] Production-boundary tests cover valid, tampered, replay, expiry,
  wrong-principal, post-rent wrapper death, terminal-receipt failure, and
  concurrent live-wrapper/cleanup exclusion without mocking approval checks.
- [ ] An independent machine-readable audit returns `ACCEPT` and binds the
  reviewed artifacts and constituent checksums before the launch hold is
  released.
- [ ] Supervisor-only shutdown binds the exact provider output and launch
  receipt, refuses ID/name conflicts, and produces a confirmed-absent receipt.

## Notes

Tracked under #31. Sentry implementation is coordinated with #33; paid
dispatcher execution remains tracked by #32.
