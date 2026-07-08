# Modal 8x H100 Lane (GLM-4.7-Flash Miles)

Status: planning. This directory collects everything the Modal port will do or
use; no launcher code exists yet. The goal is the fastest wall-clock
GLM-4.7-Flash SFT/GRPO cycle on a single Modal 8x H100 node, replacing the
Pipeshift 4x A100 setup used for the first SFT+GRPO pass.

## What carries over unchanged

- Miles + bridge patches: `src/w8_biayn/integrations/miles_glm47_bridge.py`
  (lazy post-import hooks, per-patch kill switches). Host-agnostic.
- Format contract: vendor GLM chat template with `enable_thinking:false`,
  assistant prefix `<|assistant|></think>`, datasets carry no think tokens.
- Training payload: the H100 fast-profile scripts in `examples/miles/`
  (`glm47_h100_convert_tp4_pp1_ep8.sh`, `glm47_cpp_perf_lora_r16_h100_sft.sh`,
  `glm47_cpp_perf_lora_r16_h100_grpo.sh`) — TP4/PP1/EP8/ETP1, DeepEP flex
  dispatch, SGLang DP attention + speculative decoding, `MILES_NO_REF=1`.
- Mini eval: `validation_mini126.jsonl` (stratified 1/10 subset) for
  in-training trend evals; the full 1259-task eval stays a standalone gate.
- Fit-probe habit: one probe run over the longest rows on the new topology
  before any long run.

## Borrowed as ideas from `origin/slime-sss` (reference only)

Sandeep's GCP/SkyPilot lane stays on its branch — not merged, not deleted,
not ported. Its provisioning layer is irrelevant on Modal (Modal owns image
build, provisioning, and teardown). What we reimplement Modal-natively is its
operational discipline:

- Fail-fast W&B auth check before any GPU minute is spent.
- Per-stage run receipts and frozen config snapshots under the run root.
- VRAM polling with per-GPU peak extraction saved as a run artifact.
- Staged pipeline (prepare-data -> base-eval -> sft -> sft-eval -> grpo ->
  grpo-eval -> compare) where each stage leaves evidence on disk.

## To do (design/build order)

1. Reward sandbox on Modal — DECIDED (2026-07-09): direct in-container
   execution via `W8_CPP_SANDBOX_BACKEND=local` in
   `src/w8_biayn/cpp_perf/sandbox.py`. Same stage scripts, same
   `timeout`/`taskset` timing semantics, cwd instead of a Docker mount; the
   Docker cgroup caps and read-only rootfs do not apply. Candidate and oracle
   still race in the same environment, so relative speedups stay fair. The
   training image must carry g++-13/python3, and the runtime preflight must
   pass with the local backend before GRPO.
2. Modal Volumes for the HF checkpoint, the converted torch_dist checkpoint
   (one-time conversion job via `glm47_h100_convert_tp4_pp1_ep8.sh`), PIE
   task data, and run outputs.
3. Modal app/entrypoint that boots Ray single-node inside one 8-GPU container
   and invokes the staged pipeline with the discipline items above.
4. Speed validation: the H100 profiles now default to the fast settings
   (selective recompute, 24576 tokens/GPU, DeepEP flex, SGLang mem 0.75 with
   256 running requests, custom allreduce on). Fit-probe the topology, try
   `MILES_RECOMPUTE_GRANULARITY=none` and `MILES_SGLANG_SPECULATIVE=1` as
   probe-gated experiments, and record the measured rollout time against the
   ~7 min/rollout A100 baseline.

## Non-goals

- No SkyPilot, no GCP. Do not port `cloud_launch.py`.
- No changes to the reward ladder, format contract, or eval anchors — results
  must stay comparable with the A100 runs recorded in issue #10.
