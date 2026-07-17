# Aider v1 data preparation record

## Dataset scope

The goal is to run SFT on the Aider tasks whose sole source is:

```text
.w8-biayn/data/aider-tasks-sft/sft/train.jsonl
```

The source contains 401 rows. Stack data is not included in any Aider v1
split, package, or manifest. SFT consumes the derived training partition; the
validation and test partitions remain held out for Aider-specific evaluation.

## Deterministic family-isolated split

Derived artifacts are written beneath:

```text
.w8-biayn/data/runs/aider-v1/
```

The split unit is `metadata.purpose`. Families are ordered deterministically,
then two eligible families are assigned to validation and two to test. The
generic `aider-tasks` row remains in training.

| Split | Rows | Held-out families |
| --- | ---: | --- |
| train | 321 | — |
| validation | 40 | `circular-deque`, `robot-simulation` |
| test | 40 | `nested-structure`, `trie` |

The validation and test task fixtures are copied to `task-fixtures/validation`
and `task-fixtures/test`, respectively. The complete split policy, task IDs,
and counts are recorded in `split_manifest.json`.

## Training package and context preflight

```text
.w8-biayn/data/runs/aider-v1/modal-prepared/
  manifest.json
  sft/train.jsonl
```

The package manifest records source and training-file checksums, split
locations, the GLM-4.7-Flash tokenizer revision, a 4,096-token sequence
length, and `stack_included: false`.

The local pinned-tokenizer preflight passed for all 321 training rows:

- tokenizer: `zai-org/GLM-4.7-Flash` at
  `7dd20894a642a0aa287e9827cb1a1f7f91386b67`;
- maximum rendered conversation length: 2,208 tokens;
- overlength rows: 0.

The result is saved in `modal-prepared/tokenizer_preflight_report.json`.

### Official Modal tokenizer preflight

The CPU-only official-tokenizer preflight was run after publication and
passed. It read the active remote package from
`/workspace/assets/prepared/sft/train.jsonl` and used the official
`/root/models/GLM-4.7-Flash` checkpoint at revision
`7dd20894a642a0aa287e9827cb1a1f7f91386b67`.

| Check | Result |
| --- | --- |
| status | passed |
| rows rendered | 321 |
| sequence limit | 4,096 tokens |
| maximum rendered length | 2,208 tokens |
| overlength rows | 0 |
| chat-template SHA-256 | `d63ad536c3c81880043e22ec7fd08db42b4d8fb7c89c7138bc562bfa25281375` |

The authoritative remote report is
`glm47-assets:/prepared/official_tokenizer_preflight_report.json`.

## Modal publication

The Aider-only package was published to the active prepared-data location in
the `glm47-assets` Modal Volume:

```text
/prepared/manifest.json
/prepared/sft/train.jsonl
```

This intentionally replaced the prior 735-row Aider+Stack SFT input. A
read-back verification confirmed:

| Check | Result |
| --- | --- |
| package kind/profile | `aider-v1-sft-dataset` / `aider-v1` |
| declared counts | train 321, validation 40, test 40 |
| actual remote training rows | 321 |
| Stack included | `false` |
| remote train checksum matches manifest | yes |
| remote manifest SHA-256 | `392d7e6656cd5da48d15a6a035fe42ed89cf09eae30ec25bbb7205b09b01e39c` |
| remote training JSONL SHA-256 | `257f2aef6ccb1d3f02764eeb976c0ea233f2f36fb5b2dbd26ac8b1d4f22037a5` |

## Checkout-change policy

Do not modify existing checkout code unless a change is necessary for the
requested Aider SFT workflow. New, focused helper files may be added when they
facilitate preparation, packaging, evaluation, or execution. The existing
`.w8-biayn` source-image exclusion in `examples/modal/modal_app.py` remains
the only intended modification to existing checkout code. All generated Aider
split and package artifacts belong under `.w8-biayn/`.

## Historical PIE SFT runtime finding

The repository's verified PIE SFT result is not evidence of a reusable,
published Modal project image. `README.md` records that result as measured on
a dedicated node with eight H100 80 GB GPUs. It identifies the published SFT
adapter as `TokenBender/glm47-flash-pie-cpp-lora-r16-sft-h100` at revision
`f1ac8df367080cc040f7cf769db219ee58f20f63` and says the selected profile
completed four measured optimizer steps.

The documented Modal path is a reproduction path: it starts from the pinned
Miles registry image, applies this repository's `Dockerfile` and runtime
additions, then invokes `convert` and `sft`. It is therefore expected to build
an image; the README explicitly says it does not require a separately
published project image.

The deployed `glm47-pie-cpp` Modal app has 11 historical versions (deployed
on 2026-07-08 and 2026-07-09). Modal's CLI exposed version, deployment time,
client, and source-commit short ID, but did not expose an image ID. It also
returned no retained application logs. Consequently, there is no available
immutable historical Modal image reference or callable historical SFT endpoint
to reuse from those deployments.

## Next execution step

The data is ready for SFT. The remaining prerequisite is resolving the
canonical Modal training-image failure at `Unpacking OCI image`; it occurs
before a training container starts or an H100 is allocated. The historical PIE
result does not provide a reusable Modal image reference. See
`docs/aider_stack_v1_data_preparation.md` for the existing Modal investigation.

### Candidate runtime fix

The failing image path is `modal.Image.from_dockerfile(...)`. The pinned Miles
base image itself has already started successfully through
`modal.Image.from_registry(...)`. The candidate fix is therefore to construct
an Aider-specific launcher image directly from the same pinned registry image,
apply the Dockerfile's runtime package layer through Modal image methods, and
add the repository source. This avoids Modal's Dockerfile OCI-unpacking path
without changing the pinned base image.

Validate that hypothesis first with the existing CPU-only probe:

```bash
modal run examples/modal/miles_runtime_layer_probe.py
```

It must start a container and print the installed versions of
`flashinfer-python`, `flashinfer-cubin`, `flashinfer-jit-cache`,
`sglang-kernel`, and `torch-memory-saver`. Only after it passes should a new,
focused Aider SFT launcher be added; do not alter the existing PIE launcher
before that validation.

The probe passed on Modal. It started a CPU container and reported:

```text
flashinfer-python       0.6.12
flashinfer-cubin        0.6.12
flashinfer-jit-cache    0.6.12+cu129
sglang-kernel           0.4.4+cu129
torch-memory-saver      0.0.9.post1
```

`examples/modal/aider_sft_native.py` is the resulting separate launcher. Its
first required execution is a CPU smoke test:

```bash
modal run examples/modal/aider_sft_native.py::smoke
```

The launcher excludes local caches, virtual environments, generated data,
agent state, and credential files from its source upload. This keeps the Modal
mount limited to the repository files needed for the runtime and prevents
local credentials from being included in an image build.

Only if that passes should the H100 SFT stage be launched with:

```bash
modal run examples/modal/aider_sft_native.py::sft
```

The first native-launcher smoke invocation successfully built the native image
but failed before the smoke body ran: Modal imports the function module from a
flattened `/root/aider_sft_native.py` mount, so deriving the local repository
root as `Path(__file__).parents[2]` raised `IndexError`. The launcher now uses
that derivation only when the source path has the expected local depth and
otherwise falls back safely. This is a launcher path fix, not an image or
runtime-package failure; rerun the CPU smoke before requesting H100s.

The second invocation built the corrected image, installed the editable
project, and passed `scripts/check_runtime.py`. It then found a second
launcher-only path typo while reading the model revision marker: the marker is
at `/root/models/GLM-4.7-Flash/MODEL_REVISION`, not directly under
`/root/models`. The check was corrected. No model, runtime-package, or Aider
data failure occurred; rerun the CPU smoke once more before requesting H100s.

The third invocation passed the complete native CPU smoke gate. It built the
native image, installed the editable project, passed the Miles H100 runtime
preflight, verified the model revision marker, and read the active Aider-only
SFT package. The returned report recorded 321 training rows and these runtime
versions:

```text
flashinfer-python       0.6.12
flashinfer-cubin        0.6.12
flashinfer-jit-cache    0.6.12+cu129
sglang-kernel           0.4.4+cu129
torch-memory-saver      0.0.9.post1
```

The CPU/image gate is complete. The next execution is the 8×H100 SFT stage.
