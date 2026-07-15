# SFT Experimental Profile Policy

Status: guidance for adding or changing supervised fine-tuning dataset
profiles.

This document records the policy that the SFT generation pipeline and its
profiles may change when the change helps the project create more usable C++
tasks and rows. It does not weaken the active primary dataset contract in
`docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`. The primary clean profile
keeps its own source, holdout, review, and readiness rules. Experimental work
must use separate profile IDs and separate output roots.

## Purpose

The SFT pipeline should be allowed to grow. New datasets, source formats,
prompt styles, and adapters are acceptable when they increase the supply of
task roots or training rows that can be converted into the format required by
our SLIME/Megatron use case.

The central requirement is convertibility: a source dataset is useful only if
it carries enough information to render verified raw-message SFT rows with a
loss-bearing assistant target and enough provenance to describe the claims we
can and cannot make about the resulting model.

## Profile Rules

- A semantic change to sources, row shape, prompt styles, grader policy,
  tokenizer policy, split policy, or benchmark-cleanliness claims requires a
  new profile ID.
- The repository may contain any number of experimental SFT profiles and lanes
  if they are explicitly named, isolated, and documented.
- Experimental profiles must not be silently mixed into the primary clean
  dataset. Their rows, manifests, readiness files, and exported bundles must
  remain separate.
- A benchmark-derived profile is allowed for internal ablations, but it must be
  labeled as benchmark-derived and must not claim cleanliness for that
  benchmark family.
- The active training stack remains SLIME, Megatron, and SGLang. New profiles
  may add converters and adapters, but they must not introduce a custom
  trainer.
- Dataset construction must be represented by repo-owned commands or scripts.
  One-off local munging is not release evidence.

## Experimental Lane Contract

Each experimental lane should define:

- `profile_id`: stable, versioned, and descriptive.
- `source`: dataset or repository name, URL, revision, split/config, and
  license.
- `purpose`: the training question the lane answers, such as repair,
  synthesis, whole-file editing, or format warm-start.
- `claim_scope`: what benchmark or cleanliness claims are allowed and
  forbidden.
- `row_count_policy`: expected roots, rows per root, split policy, and whether
  validation/test assets contain answers.
- `conversion_policy`: how source fields become editable files, user prompts,
  assistant targets, metadata, and token records.
- `grader_policy`: how references and targets are compiled, tested, sanitized,
  and rejected.
- `export_policy`: whether the output is a full provenance-bearing bundle, a
  private internal bundle, or a reduced one-file handoff.

## Minimum Source Information

A source dataset is a good candidate only when it contains, or can be paired
with, the information below.

1. Provenance and license:
   dataset name, source URL, exact revision or immutable dataset version,
   split/config, source file hashes when available, and license.

2. Stable task identity:
   task ID, language, family or benchmark family when known, and a way to
   deduplicate near-identical tasks.

3. User-visible task material:
   instructions, declarations, starter files, allowed diagnostics, public
   examples, or representative tests that can be shown in the prompt.

4. Editable file mapping:
   the exact file path or synthesized file path that the model must return,
   plus the starter bytes for that file. Function-only datasets must be wrapped
   into a deterministic file scaffold before admission.

5. Reference target:
   a canonical solution or final editable-file state that can become the
   assistant target. The target must be renderable as complete file listings,
   not only a diff or an informal answer.

6. Grader evidence:
   tests, entry point, setup code, dependencies, compile standard, and expected
   behavior sufficient for a repo-owned grader to prove the reference passes
   and defective starters fail when the profile uses repair styles.

7. Public/private boundary:
   which tests, examples, references, and metadata are prompt-visible, which
   remain private, and what may be included in a sanitized export.

8. Benchmark and contamination metadata:
   whether the source is benchmark-derived, which benchmark families are no
   longer clean after training, and which holdouts must still be screened.

## Required Output Shape

Regardless of source format, an admitted training row for the current raw
message SFT consumer must be convertible to this shape:

```json
{
  "schema_version": "aider-sft-row-v1",
  "task_id": "...",
  "label": "...",
  "messages": [
    {"role": "user", "content": "...", "step_loss_mask": 0},
    {"role": "assistant", "content": "...", "step_loss_mask": 1}
  ],
  "metadata": {
    "format": "aider-whole",
    "subset": "train",
    "editable_files": ["solution.cpp"]
  }
}
```

The assistant content must be a code-only whole-file answer:

````text
solution.cpp
```cpp
complete file bytes
```
````

For a profile that intentionally uses a different target shape, the profile
must define a different consumer adapter and verification policy. It must not
reuse the primary `slime-sft` readiness claim.

## Admission Checklist

Before an experimental profile can be called usable for training, it should
pass these gates:

- every source row maps to deterministic starter files and editable file names;
- every assistant target parses as the declared response format;
- applying the target to the starter reproduces the reference bytes;
- the reference compiles and passes the profile's tests in a pinned
  environment;
- defective starters or buggy solutions fail when the prompt style depends on
  repair evidence;
- tokenization and loss masks are computed through the repo-owned raw-message
  path;
- rows fit the profile sequence limit without truncation;
- license and provenance are recorded in the manifest;
- benchmark-derived data is labeled and excluded from clean benchmark claims;
- the export contains only the assets allowed by its audience.

## HumanEvalPack Example

A HumanEvalPack lane may be useful as an internal ablation because the dataset
contains prompts, declarations, canonical solutions, buggy solutions, tests,
entry points, and metadata. That is enough to build a deterministic converter
for C++ synthesis or repair rows.

Such a profile should be named separately, for example
`humanevalpack-cpp-sft-ablation-v1`. It should be labeled
benchmark-derived. Training on it invalidates HumanEval-family cleanliness
claims, even if the resulting model is later evaluated only on Aider Polyglot
C++.

The converter would need to synthesize `solution.cpp`, render the prompt from
the HumanEvalPack instruction/declaration/buggy solution/test fields, render
the canonical solution as the whole-file assistant target, compile and run the
tests, then write raw-message rows and token records.

## Relationship To The Primary Profile

The primary profile remains the clean, provenance-heavy profile for released
Aider-style C++ SFT data. Experimental profiles are how we explore more task
sources, benchmark-derived ablations, alternate prompt styles, and smaller
handoffs. If an experimental lane proves useful and we want it to become a
release profile, its profile ID, source policy, grader, readiness criteria,
documentation, and tests must be promoted explicitly in one logical change.
