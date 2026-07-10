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
- [ ] Tampered, expired, replayed, wrong-stage, wrong-principal, wrong-command,
  and concurrent-use permits fail with zero provider invocations.
- [ ] On-node preflight and screen decisions bind the exact request and evidence
  hashes, parent approval, Gate 0 digest, and provider allocation ID, and are
  domain-separated and signed for single-use verification by the runner.
- [ ] Production-boundary tests cover valid, tampered, replay, expiry,
  wrong-principal, and concurrent-use cases without mocking approval checks.
- [ ] An independent machine-readable audit returns `ACCEPT` and binds the
  reviewed artifacts and constituent checksums before the launch hold is
  released.

## Notes

Tracked under #31. Sentry implementation is coordinated with #33; paid
dispatcher execution remains tracked by #32.
