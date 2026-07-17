# Aider + Stack v1 data preparation record

## Completed data preparation and packaging

- User-authoritative Aider and Stack inputs were validated, context-filtered,
  split, and merged into a 735-row training JSONL.
- The Aider held-out sets contain 40 validation and 40 test rows with their
  runnable fixtures; Stack remains training-only.
- The packaged manifest and training file are in `glm47-assets` at
  `/prepared/manifest.json` and `/prepared/sft/train.jsonl`.

## Completed official-checkpoint CPU preflight

The official `zai-org/GLM-4.7-Flash` revision
`7dd20894a642a0aa287e9827cb1a1f7f91386b67` was fetched directly into
`glm47-models`. Its tokenizer/template rendered all 735 training rows within
the 4,096-token limit; the maximum was 4,067. The authoritative result is
`/prepared/official_tokenizer_preflight_report.json` in the assets Volume.

## Learnings, errors, and fixes

1. A local `.w8-biayn` tokenizer snapshot was superseded for verification;
   the successful tokenizer preflight used only the official checkpoint.

2. `.w8-biayn` is now excluded from the canonical Modal application’s source
   image payload. This prevents local artifacts entering future image builds.

3. The first official-tokenizer preflight failed because `jinja2` was missing.
   Adding `jinja2==3.1.6` fixed it.

4. `examples/modal/miles_base_probe.py` successfully started a CPU container
   from the pinned Miles base image. The base image is usable.

5. `examples/modal/miles_runtime_layer_probe.py` stalled while replacing the
   base FlashInfer packages, before a container was started. It produced no
   package error.

6. The canonical CPU runtime smoke test and a local conversion invocation both
   stopped during canonical-image construction at `Unpacking OCI image`; no
   container, H100 allocation, or converted checkpoint resulted.

7. Reuse attempt: the known-good `glm47-pie-cpp` app has 11 deployment
   versions, but Modal does not expose their image IDs through the CLI. Calling
   `modal.Function.from_name("glm47-pie-cpp", "run_stage")` failed with
   `NotFoundError`: no remotely invokable `run_stage` function exists for that
   deployed app in environment `main`. No conversion was started.

8. The generic `glm47-assets:/prepared/` path can be confused with PIE or
   other prepared datasets. The Aider package previously replaced the old
   Aider+Stack content at that shared location; it is not PIE task data, but
   the shared name creates an avoidable collision risk.

   Reviewer-directed resolution implemented in the existing
   `examples/modal/aider_sft_native.py` launcher: it now sets
   `MILES_CPP_DATA_DIR=/workspace/assets/aider-polyglot-cpp` and its smoke test
   reads the manifest and `sft/train.jsonl` from that same directory. The
   unchanged package was copied to `glm47-assets:/aider-polyglot-cpp/`
   with `manifest.json`, `sft/train.jsonl`, and
   `official_tokenizer_preflight_report.json`; no second Aider launcher was
   added.

   The existing JSONL format, 321/40/40 split, native Modal image workaround,
   `examples/sft.sh`, and `scripts/train_sft.sh` must remain unchanged. The
   PIE launcher and PIE data remain unchanged. The Aider CPU smoke test passed:
   it read 321 rows from
   `/workspace/assets/aider-polyglot-cpp/sft/train.jsonl`, and its manifest
   checksum matched
   `257f2aef6ccb1d3f02764eeb976c0ea233f2f36fb5b2dbd26ac8b1d4f22037a5`.
   The H100 command uses this isolated path through the existing Aider launcher.

## Next step — launch Aider SFT on H100

The native image workaround and isolated data-path smoke gate have passed.
Launch the Aider-only SFT stage with:

```bash
modal run examples/modal/aider_sft_native.py::sft
```

## PIE `/prepared` restoration prerequisite

The legacy generic `glm47-assets:/prepared/` directory has not been replaced
with PIE data. Inspection found no ready PIE prepared package in the local
workspace and no `glm47-assets:/data/` task directory from which to build one.
It therefore would be unsafe to overwrite `/prepared` at this point.

No new code is required to create a valid PIE package, but the existing PIE
asset-preparation step must first populate `glm47-assets:/data/tasks`. The
existing PIE data builder can then generate the required `manifest.json` and
`sft/train.jsonl` beneath `/prepared`. Only a verified output of that existing
builder should replace the legacy Aider package at the generic path. The
isolated Aider package at `/aider-polyglot-cpp` is unaffected by this future
PIE restoration.

An attempt to run the existing
`modal run examples/modal/modal_app.py::prepare` entrypoint did not reach its
asset-download function. Modal again stalled while building the module's
Dockerfile-derived training image at `Unpacking OCI image`; no function task
started, `glm47-assets:/data/` was not created, and `/prepared` was not
modified. Restoring PIE data to `/prepared` therefore remains blocked until
the existing prepare entrypoint can avoid that image-build path or a verified
PIE prepared package is supplied from another source.
