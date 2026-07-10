## Scope

Resolve the issue-31 dispatcher ambiguity with a controlled sustained A/B test
on one dedicated 8x H100 80 GB NVLink node.

This issue is experiment specification only. No provider mutation is
authorized until the Research Supervisor releases a signed Gate 0 booking
request and the Automated Sentry emits a matching expiring, single-use permit
under #34. Once the issue-owned node exists, a separate signed Gate 1
preflight must pass before A1 can start.

## Fixed baseline

- Training base SHA: `cd83e3c8780f09e38e5b58558d84580e74afbcf6`
- Actual measurement SHA: the clean runtime `pie-slime-posttraining` HEAD,
  which must be a descendant containing only the approved measurement and
  supervision files
- Miles: `01a6d7bb74befa6e97579c80a2b1add0667606f3`
- Megatron-LM: `79fc0894d0ba57acd10a9c0da507abd1dfef3bdf`
- 8x NVIDIA H100 80GB HBM3 with full NV18 connectivity
- BF16 TP4/PP1/CP1/EP8/ETP1; LoRA rank 16
- sequence 4096; dynamic balanced batches; 16,384 tokens/GPU
- microbatch 1; global/rollout batch 32; selective recompute
- `CUDA_DEVICE_MAX_CONNECTIONS=1`; resident SFT actor; no gradient-accumulation
  fusion
- exact 128-row dataset SHA-256
  `f1f5f70b1e77dbb6da51d075a35b2e48f784f4080873f356c9c4bd3c83a3d783`
- historical sustained reference: 2.069052% estimated active-model-equivalent
  MFU and 6,735.536 global actor tok/s

The historical reference has only 11 post-warmup steps and is descriptive
context. It cannot lower the new paired-run protocol.

## Exact experiment

Run four clean processes in order `A1 -> B1 -> B2 -> A2`, each from the same
immutable converted base checkpoint and each for four epochs.

Each leg must produce 16 performance steps. Discard the first two warmup steps
and retain 14 matched post-warmup steps.

- A: `moe_token_dispatcher_type=flex`, DeepEP enabled
- B: `moe_token_dispatcher_type=alltoall`, DeepEP disabled
- No other configuration or source difference is allowed.

Compare matching token/work signatures, not pooled medians. Preserve every raw
event and work vector.

## T1 promotion criteria

- Both A and B have two clean sustained replicates unless an early stop fires.
- Exact token/work signatures and all fixed variables match.
- Loss and grad norm are finite and remain inside the baseline envelope.
- Each of the two independent candidate/control process-pair aggregate ratios
  is at least 1.03 for estimated MFU and actor throughput.
- Candidate B also exceeds 2.131124% estimated MFU and 6,937.602 actor tok/s.
- The 98% throughput-retention threshold is an early-stop guardrail only; it
  is not success.
- Within-step and complete-workload-block intervals are diagnostic only.
- Passing T1 authorizes only a separately budgeted T2 confirmation issue. It
  does not authorize a final performance claim or GRPO.

Final performance acceptance requires at least four independent process-pair
aggregate log ratios across T1 and T2, a geometric-mean ratio of at least 1.03,
and a one-sided 95% Student-t lower log bound above zero for both metrics.
GRPO and independent audit follow only after that confirmation passes.

## Required evidence

- Raw per-step work vectors, FLOP numerator, timings, tokens, loss, and grad
  norm.
- Exact config diff and hardware/source/data/checkpoint receipts.
- Per-GPU clocks, power, thermals, memory, SM, tensor, HBM, and NVLink
  telemetry.
- Eight-GPU preflight and continuous operating snapshots with at least a 690 W
  configured power limit per H100.
- Adapter fingerprints before update, after update, and after SGLang
  synchronization.
- Exact OCI/Hugging Face setup attestation and model-revision marker.
- Per-leg pre/post GPU and Ray/SGLang/training process-cleanliness receipts.
- Consistent local and W&B `timing_status=verified`.
- W&B tables, cost receipt, termination receipt, and checksummed immutable
  artifact bundle.

## Early stops

- Hardware, source, runtime, data, checkpoint, or token/work mismatch.
- Baseline A1 is outside +/-5% of the historical reference or shows clock/power
  throttling.
- Any OOM, rank failure, non-finite metric, checkpoint failure, or failure
  trace.
- B1 paired throughput retention is below 98%; do not spend on B2/A2.
- One paid node-hour elapses without completed valid A1 and B1.
- Hard tranche cap or auto-termination deadline is reached.

## Budget

Supervisor tranche T1: at most 2.0 H100-node hours and at most USD 36 at the
verified USD 18/hour rate. Use a two-hour TTL. Unused budget is not transferable
to another experiment.

## Notes

Tracked under reopened #31, parent #10, and master #1. The code-controlled
contract is `examples/miles/h100_fastest_acceptance.json`. This issue must not
close as a win from a short-run result or a baseline-retention result.
