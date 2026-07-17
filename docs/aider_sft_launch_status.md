# Aider-only SFT launch status

## Objective

Run one supervised fine-tuning job for GLM-4.7-Flash using only the Aider SFT
tasks from:

```text
.w8-biayn/data/aider-tasks-sft/sft/train.jsonl
```

No Stack training rows are included.

## Data preparation

The source `train.jsonl` contains 401 Aider task rows. It was split by
`metadata.purpose` family so related tasks do not cross partitions:

| Partition | Rows | Families |
| --- | ---: | --- |
| train | 321 | all remaining families plus the generic `aider-tasks` row |
| validation | 40 | `circular-deque`, `robot-simulation` |
| test | 40 | `nested-structure`, `trie` |

The held-out validation and test fixtures are preserved under:

```text
.w8-biayn/data/runs/aider-v1/task-fixtures/
```

The SFT package is:

```text
.w8-biayn/data/runs/aider-v1/modal-prepared/
  manifest.json
  sft/train.jsonl
```

## Active Modal dataset

The Aider-only package has replaced the old 735-row Aider+Stack package at:

```text
glm47-assets:/prepared/manifest.json
glm47-assets:/prepared/sft/train.jsonl
```

Remote read-back verification confirmed:

- package profile: `aider-v1`;
- training rows: 321 declared and 321 present;
- `stack_included: false`;
- uploaded training JSONL checksum matches the manifest.

This `/prepared` location was not PIE task data. The model and run Volumes
were not changed.

## Official data validation

The official Modal tokenizer preflight passed against the active remote
package:

- model/tokenizer: `zai-org/GLM-4.7-Flash` revision
  `7dd20894a642a0aa287e9827cb1a1f7f91386b67`;
- 321 rows rendered;
- sequence limit: 4,096 tokens;
- maximum rendered length: 2,208 tokens;
- overlength rows: 0.

## Runtime workaround and validation

The existing PIE Modal launcher uses `modal.Image.from_dockerfile(...)`. Modal
fails in that path at `Unpacking OCI image`, before the container starts or an
H100 is allocated. The exact backend cause was not exposed.

The pinned Miles base image and the required runtime layer work when built by
Modal’s native registry-image builder. A new, separate Aider launcher was
added at:

```text
examples/modal/aider_sft_native.py
```

It uses the same pinned Miles base, runtime package versions, model/checkpoint
Volumes, `examples/sft.sh`, and `scripts/train_sft.sh` as the PIE path. It
does not modify the existing PIE launcher.

Its CPU smoke test passed:

- native image build completed;
- editable project installation completed;
- Miles runtime preflight passed;
- expected FlashInfer, SGLang-kernel, and torch-memory-saver versions were
  verified;
- the official model revision marker was found;
- the active Aider-only package was read successfully with 321 rows.

The launcher excludes `.w8-biayn`, local caches, virtual environments, agent
state, and local credential files from its source upload.

## Current status: ready to launch SFT

All data, tokenizer, and CPU runtime gates have passed. The next command
requests the actual 8×H100 SFT run:

```bash
modal run examples/modal/aider_sft_native.py::sft
```

The run will read `glm47-assets:/prepared/sft/train.jsonl`, train the LoRA
adapter, and store logs, checkpoints, and run artifacts in the `glm47-runs`
Volume. It uses W&B project `glm47-aider-v1-sft` and tags the run
`aider-v1,modal,8xh100,sft`.