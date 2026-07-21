# PIE C++ GRPO environment

## Purpose

This repository trains GLM-4.7-Flash to optimize C++20 programs from the PIE
C++ performance task. The desired behavior is not simply to emit code that
looks plausible: a response must preserve the original program's behavior on
visible and hidden tests, be safe under AddressSanitizer and UndefinedBehaviorSanitizer,
and, when it is correct, execute faster than a supplied reference baseline.

The environment is therefore a program-synthesis and program-optimization
environment. A policy receives a slow program and a few visible examples,
produces a complete replacement program, and receives a scalar reward from an
isolated compile/test/benchmark harness. GRPO uses relative reward within each
group of sampled completions to improve the LoRA policy.

The main entry point is `examples/grpo.sh`, which delegates to
`scripts/train_grpo.sh`. The environment implementation is in
`src/glm47_posttraining/cpp_perf/`; the Miles adapter that turns the task data
and rewards into training inputs is
`src/glm47_posttraining/integrations/miles_cpp_perf.py`.

## What one task contains

Each PIE-derived task is validated as a `CppTask` before training data is
created. It contains:

- a task and problem identifier, a `train`, `validation`, or `test` split, and
  the slow `prompt_code` program;
- visible unit tests and hidden tests, each expressed as stdin and expected
  stdout;
- a known-correct `oracle_solution` and reference runtime metadata;
- the candidate build command and timeout; and
- line and branch coverage metadata. The schema requires at least 95% line
  coverage and 85% branch coverage, and requires both visible and hidden test
  lists to be non-empty.

The oracle is used in two distinct roles. Its source supplies the SFT target
when SFT data is made, and it is compiled and timed beside a correct GRPO
candidate to establish the runtime baseline. It is never included in a GRPO
prompt.

## Model interface

The prompt tells the model to optimize a C++20 program without changing its
exact behavior. It includes visible test cases and the full starter program.
It explicitly says not to rely on hidden tests and requires stdin/stdout
behavior.

The required answer format is:

````text
<reasoning>...</reasoning>
```cpp
// complete replacement program
```
````

There must be exactly one reasoning block followed by exactly one C++ code
block. This gives training a stable response contract while separating private
reasoning syntax from compilable source. The scorer can recover a single C++
block, or bare source that unmistakably looks like a complete C++ program, so
that near-miss formatting receives an informative but smaller reward rather
than throwing away an otherwise useful rollout.

## From task files to GRPO prompts

`build-data` loads task JSON, selects the train and requested evaluation
splits, and writes a self-contained data directory:

```text
data/
  tasks/                 copied task records
  sft/train.jsonl        prompt plus oracle answer
  grpo/train.jsonl       prompts only, for online rollouts
  eval/validation.jsonl  held-out prompts
  manifest.json          source, splits, counts, and options
```

The runner can sort training tasks by SFT size and can optionally score each
oracle first, retaining only tasks for which the oracle earns full marks. This
avoids training against task records whose reference cannot pass the same
harness. Validation and test tasks are not used as GRPO prompt data.

## Candidate evaluation lifecycle

For every sampled answer, `compute_reward` extracts the C++ candidate and
calls `run_in_sandbox`. The harness performs the following sequence:

1. Create a fresh scratch directory containing `candidate.cpp`,
   `reference.cpp`, and all visible plus hidden input/output fixtures.
2. Compile the candidate with the task's normal optimized build command.
3. Compile it again with `-fsanitize=address,undefined`; an instrumentation
   build failure is treated as a sanitizer failure.
4. Run the normal candidate against every test case, with a five-second
   default run timeout, pinned to a leased CPU core. Output is normalized for
   leading/trailing blank lines and trailing whitespace before comparison.
5. Only if every test passes, compile the reference solution using its pinned
   compiler flags.
6. Benchmark the candidate and reference on the complete test suite. The
   benchmark has one warm-up and three measured repetitions by default and
   reports CPU and wall-clock nanoseconds. Candidate output is revalidated
   while benchmarking; the known reference does not need this extra check.

The normal backend is Docker. The configured sandbox runs with a read-only
root filesystem, no network, dropped Linux capabilities, no new privileges,
and resource limits; a scratch directory is the only writable mount. Docker
also does not by itself provide a private core, so the harness leases a
host-visible CPU core and uses `taskset` to keep a candidate and reference
measurement on the same core. A `GLM47_CPP_SANDBOX_BACKEND=local` fallback
executes the same commands without Docker isolation, intended only for hosts
without a Docker daemon.

## Reward design

Correctness is a hard gate for performance credit. Let `p` be the fraction of
tests passed, `t_ref` the reference CPU runtime, and `t_candidate` the
candidate CPU runtime. For a correctly formatted answer that passes every
test, the runtime component is:

```text
relative_gain = clamp((t_ref - t_candidate) / t_ref, 0, 1)
efficiency    = tanh(2 * relative_gain)
reward        = 1 + efficiency
```

Thus a correct answer earns at least `1.0`; a faster answer receives a smooth
bonus approaching `1.0`. A correct candidate slower than the reference is not
punished below the correctness reward, but receives no speed bonus. This
choice prioritizes behavioral preservation while still making optimization
useful to the policy.

| Result | Strict-format reward |
|---|---:|
| Cannot extract a recoverable C++ submission | -1.0 |
| Compilation, sanitizer, or runtime timeout failure | -0.5 |
| Compiles but fails tests | `-0.2 + 0.2 * p` |
| All tests pass but a runtime is unavailable | 0.5 |
| All tests pass and timing is available | `1 + efficiency` |

Recoverable-but-invalid formatting is scored separately. Compile/sanitizer/
timeout failures receive `-0.75`; partial correctness receives
`-0.4 + 0.4 * p`; correct code without timing receives `0.2`; and correct,
timed code receives `0.1 + 0.3 * efficiency`. These lower values make the
format requirement meaningful without preventing the policy from learning
from code that can still be evaluated.

## GRPO training loop

The default H100 launcher runs LoRA GRPO with the Miles training stack:

- 32 prompts per rollout batch and 8 samples per prompt, or 256 sampled
  completions per rollout;
- 100 rollouts by default; evaluation every 20 rollouts and checkpoints every
  10 rollouts in the canonical example configuration;
- temperature 1.0 sampling with a 1,024-token rollout limit;
- GRPO advantage estimation, clip range 0.2 (upper clip 0.28), and zero
  explicit KL and entropy coefficients; and
- a rank-16 LoRA adapter over the selected attention and MLP projection
  modules, optimized with Adam at a default learning rate of `1e-5`.

SGLang serves rollouts across the configured eight H100 GPUs. After rewards
are calculated, Miles forms the group-relative GRPO advantages, updates the
LoRA policy, and synchronizes the serving adapter. The run records logs,
rollout dumps, checkpoints, VRAM telemetry, an execution receipt, prepared
data, and optional Weights & Biases artifacts.

## What success means

The immediate training objective is to increase the probability that a sampled
completion is a well-formed, sanitizer-safe, test-passing optimization. Among
those valid programs, it aims to improve CPU runtime relative to the PIE
reference. This is intentionally not a reward for superficial code shortening
or for exploiting visible examples: hidden tests, sanitizer checks, output
rechecking during timing, and the correctness gate make those strategies
unreliable.

The final evaluation separately generates and scores held-out tasks, produces
per-sample records and aggregate quality/runtime metrics, and can compare base,
SFT, and GRPO checkpoints. A claimed performance improvement should therefore
be grounded in the held-out evaluation summaries, not merely in training
reward.

## Operational constraints and caveats

- Timing is inherently noisy. The harness reduces noise with warm-ups,
  repeated measurements, CPU-time reporting, and same-core pinning, but a
  runtime bonus is still a local measurement rather than a universal speed
  guarantee.
- Docker is the security boundary. The local backend is useful for debugging,
  but lacks Docker cgroup limits and the read-only-root filesystem.
- The SFT oracle and the runtime reference come from task data. The optional
  oracle-full-marks filter is important when ingesting new task sets.
- The system rewards source-level behavior only through its test suites. Test
  coverage thresholds raise the bar, but do not formally prove equivalence for
  arbitrary C++ inputs.
- Evaluation labels and output directories must remain distinct for base, SFT,
  and GRPO so comparison metrics are not mixed.
