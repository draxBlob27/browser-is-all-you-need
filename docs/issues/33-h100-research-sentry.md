## Scope

Add a deterministic research sentry and durable supervision contract for the
8x H100 MFU optimization effort.

The sentry validates evidence and controls stage transitions. It does not rank
candidates, change the scientific contract, launch paid compute, or declare a
winner independently of the Research Supervisor and Independent Auditor.

## Why

The original short sweep allowed a baseline to be named the winner and checked
off repeat criteria that its own summaries contradicted. Paid experiments need
machine-enforced provenance, workload, statistics, telemetry, budget, W&B,
checkpoint, and GRPO gates.

## Acceptance criteria

- [ ] A versioned machine-readable contract fixes the baseline, metric label,
  thresholds, source lineage, hardware shape, budget, and current experiment.
- [ ] Preflight validates 8x H100 80GB NV18 hardware, source lineage, and the
  active budget tranche.
- [ ] A signed Gate 0 permit is consumed before the first Lium mutation, and
  signed Gate 1 decisions bind the resulting allocation and exact request,
  parent, and evidence hashes.
- [ ] Expiry, tampering, replay, wrong-domain, wrong-principal, wrong-parent,
  and concurrent double consumption fail closed before execution.
- [ ] Screen, T1 promotion, T2 confirmation, GRPO, and final stages emit
  deterministic JSON decisions.
- [ ] T1 promotion requires two clean A/B pairs, at least 12 matched
  post-warmup steps, complete workload blocks, per-pair 3% MFU and
  actor-throughput gains, and historical +3% hurdles.
- [ ] The 98% retention threshold is only an early-stop guardrail.
- [ ] T2 confirmation requires at least four independent process-pair log
  ratios and a process-level one-sided 95% Student-t lower bound above zero.
- [ ] GRPO follows confirmatory performance acceptance; final acceptance also
  requires a separately signed independent-auditor artifact with checksums and
  a key distinct from the sentry signer.
- [ ] Invalid implementation paths are distinguished from valid negative
  performance results and inconclusive evidence.
- [ ] Focused tests, lint, docs, and a dry-run invocation pass.

## Notes

Tracked under #31. Experiment #32 consumes this sentry but remains a separate
paid-performance work unit.
