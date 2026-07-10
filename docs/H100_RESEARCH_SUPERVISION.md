# H100 Research Supervision

This document is the durable operating contract for the fastest accepted
8x H100 GLM-4.7-Flash post-training effort. The machine-readable companion is
`examples/miles/h100_fastest_acceptance.json`.

## Authority

The executing agent does not grade its own result.

- The Research Supervisor owns the scientific contract, experiment order,
  budget tranches, promotion decisions, and final claim.
- The Executor owns only the implementation and runs explicitly authorized by
  the supervisor. It cannot change the workload, metric formula, thresholds,
  or issue state.
- The Automated Sentry applies deterministic preflight, screen, promotion,
  and final gates. It can stop invalid or over-budget work but cannot select a
  scientific winner.
- The Independent Auditor recomputes the result from raw evidence. It cannot
  edit the implementation or rely on the executor's summary.

The GitHub master ledger is issue
[#31](https://github.com/tokenbender/browser-is-all-you-need/issues/31).
The current experiment is issue
[#32](https://github.com/tokenbender/browser-is-all-you-need/issues/32).
The deterministic sentry is tracked separately in issue
[#33](https://github.com/tokenbender/browser-is-all-you-need/issues/33).
Signed launch authorization is tracked in issue
[#34](https://github.com/tokenbender/browser-is-all-you-need/issues/34).

## State Machine

Every candidate moves through this sequence:

```text
BOOKING_REQUEST -> GATE0_AUTHORIZED -> ALLOCATED -> GATE1_PREFLIGHT
                -> T1_SCREEN -> PROMOTE_TO_CONFIRMATION -> T2_CONFIRMATION
                -> PERFORMANCE_ACCEPTED -> GRPO_VALIDATED
                -> INDEPENDENT_AUDIT_ACCEPT -> FINAL
```

Terminal non-success states are `INVALID`, `REJECTED`, `INCONCLUSIVE`, and
`NO_WIN`. A failed implementation path is `INVALID`; it is not evidence that
the optimization is slow.

No provider mutation begins without a signed, expiring, single-use Gate 0
permit for the exact Lium request, provider executable, source and runtime
pins, data and checkpoint intent, issue-owned allocation name, TTL, and budget.
After allocation, signed Gate 1 preflight and screen decisions bind the exact
allocation, request, parent approvals, and evidence. A preflight performed on
an already-booked node cannot retroactively authorize the booking. No candidate
is accepted without a separately signed independent audit of raw logs.

## Key Custody

The paid node receives public verification keys only. Executor phases write to
`/tmp/w8-issue32-t1`; after `prepare` and `first-pair`, that evidence tree is
mirrored to the same path on the supervisor host. The Automated Sentry
recomputes the decision and signs it on the supervisor host, then only the
signed decision is returned to the node. The Gate 1 public-key digest, derived
key ID, and sentry/executor principals are fixed in the Gate 0 parent booking
request, so the executor cannot substitute its own trust anchor. Gate 0, Gate
1, supervisor, and independent-auditor private keys remain outside the
repository and outside executor-controlled compute, with mode `0600` or
stricter. The Lium credential is supplied by the supervisor over a bounded
stdin channel; it is never placed in argv, the subprocess environment, the
repository, or a receipt. The launch permit also binds the exact SSH public-key
file by absolute path and SHA-256; the provider receives that public key
explicitly, while receipts retain only its path and digest.

## Threat Boundary

The control plane rejects stale, forged, tampered, expired, concurrently
replayed, wrong-parent, and wrong-principal artifacts. It also separates paid
provider authorization from experiment execution: only the Research
Supervisor invokes Gate 0 and supplies the Lium credential, while the Executor
receives the resulting allocation and public verification material.

The local Codex roles share one Unix account and are not claimed to be
OS-isolated adversaries. A malicious same-UID process could inspect memory,
alter same-user files, or bypass local wrappers using credentials it obtained
elsewhere; eliminating that capability requires a separately administered
credential broker or OS account. Acceptance therefore relies on cryptographic
role separation and independently auditable actions, with the local account as
the administrative trust boundary. The paid node remains outside that trust
boundary and never receives provider or private signing credentials.

## Locked Metric

The comparison metric is the existing estimated active-model-equivalent MFU:

```text
perf/actor_train_tflops / 989.0
```

The formula remains frozen during A/B comparisons. It uses Miles' active-MoE
training-work approximation and must not be described as literal measured
hardware MFU for frozen-base LoRA. Hardware tensor, SM, HBM, and NVLink
telemetry are reported separately.

The historical sustained reference is 2.069052% estimated MFU and 6,735.536
global actor tokens/s. It is descriptive context, not a substitute for a fresh
same-session control.

## Promotion Gate

A T1 candidate is promoted to confirmation only when all of these are true:

- Two clean control runs and two clean candidate runs use identical work.
- Every leg has at least 12 post-warmup matched steps.
- Candidate MFU and actor throughput each improve by at least 3%.
- Both independent T1 process-pair ratios are at least 1.03 for MFU and actor
  throughput. Step and complete-block intervals are diagnostic only.
- The candidate also exceeds 2.131124% estimated MFU and 6,937.602 actor
  tokens/s, the historical reference plus 3%.
- Loss and gradient norm are finite, no failure trace exists, and every GPU
  retains at least 4 GiB of VRAM headroom.
- Timing is marked `verified` consistently in local and W&B evidence.
- T1 does not establish final confidence or authorize a performance claim.

Final performance acceptance requires a second clean ABBA session and at
least four independent process-pair aggregate log ratios across T1 and T2.
For each metric, the geometric-mean ratio must be at least 1.03 and the
one-sided 95% Student-t lower log bound must exceed zero. Step-level and
workload-block pseudoreplicates cannot enter this test.

GRPO starts only after confirmatory performance acceptance. Final acceptance
then requires GRPO train, adapter synchronization, checkpoint/save evidence,
and a separately produced auditor artifact with an `ACCEPT` decision, bounded
claim, exact manifest and constituent checksums, auditor identity, and auditor
timestamp.

The 98% throughput-retention value is an early-stop guardrail. It is not a
success threshold.

## Current Directive

The first authorized comparison is the T1 screen `A1 -> B1 -> B2 -> A2` on
one unchanged 8x H100 node:

- A uses the TP4/EP8 flex dispatcher with DeepEP enabled.
- B changes only to standard all-to-all with DeepEP disabled.
- Each leg produces 16 performance steps; the first two are discarded and 14
  matched observations are retained. Sentry may additionally summarize 12
  complete-cycle observations, but must label those statistics diagnostic.
- Stop after B1 when candidate throughput retention is below 98%.
- Tranche T1 is capped at two node-hours and USD 36. Unused budget cannot fund
  another hypothesis.
- Gate 0 permits expire after at most ten minutes. The provider TTL remains
  two hours and is independently verified from the server-returned schedule.
- The runner accepts only `/tmp/w8-issue32-t1`; that root and the fixed Gate 0
  and Gate 1 registries must be owner-only, real directories opened without
  following symlinks. Claims are created relative to the held registry
  descriptor. The runner records GPU/Ray/SGLang/training process inventory
  before and after every leg. A surviving relevant process invalidates the leg.
- Gate 1 requires a read-only setup attestation for the exact OCI digest and
  Hugging Face revision plus a matching revision marker in the model tree.
- Preflight and continuous telemetry require all eight H100s to retain at
  least a 690 W configured power limit; lower-power evidence is invalid.

T1 can only promote all-to-all to a separately budgeted T2 confirmation issue.
TP2/EP8 with a 14K token cap remains queued behind this lower-cost ambiguity
resolution. Runtime repairs for gradient overlap, TP overlap, or scoped NVLS
require separate issues and profiler evidence.

## Required Evidence Packet

Every promotion request contains:

```text
hypothesis
exact code and configuration delta
variables held fixed
raw per-step work, MFU, throughput, timing, loss, and gradient data
paired statistics and confidence bounds
per-GPU clocks, power, thermals, memory, SM, tensor, HBM, and NVLink data
checkpoint and adapter fingerprints before update, after update, and after sync
local and W&B timing status
cost and remaining tranche
artifact paths and checksums
recommended decision
signed Gate 0 and Gate 1 parent chain, nonces, expiries, and consumption receipts
provider allocation, output, cost, TTL, and termination receipts
setup attestation and model-revision marker checksums
pre-leg and post-leg process-cleanliness receipts
```

The supervisor responds with one decision: `continue`, `stop`, `repair`,
`repeat`, `promote`, or `audit`.

## Closure

The master issue closes only when the contract JSON, signed authorization
chain, sentry output, raw artifacts, W&B evidence, independent audit, issue
ledger, cost and termination receipts, and final claim all agree. If no
candidate passes, the result is `NO_WIN`; completing a sweep or retaining the
baseline is not an optimization success.
