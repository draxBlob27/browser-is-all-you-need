#!/usr/bin/env python3
"""Freeze rejection remedies for the contaminated legacy spiral-matrix family."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/"
    "aider-text-grid-reshaping/spiral-matrix"
)
REVERIFY_ROOT = Path(
    ".w8-biayn/data/aider-tasks-reverify/"
    "aider-text-grid-reshaping/spiral-matrix"
)
GENERATOR = Path(
    "src/w8_biayn/integrations/moonlight_spiral_matrix_aider_tasks.py"
)
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-text-grid-reshaping/spiral-matrix.md"
)
PROMPT = Path("docs/aider-tasks-spec/prompts/remediate-family-reverify.md")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_SPIRAL_MATRIX_CURRICULUM.md"
)
FINDINGS = [
    "SM-BENCHMARK-FAMILY-OVERLAP",
    "SM-RENAMED-RING-TEMPLATE",
    "SM-NONDISCRIMINATING-TESTS",
]
GENERATOR_REVISION_BEFORE = (
    "sha256:9e65ad728ce8900d9a8ef10f54f92f2372af83a409673ac2edb7eff3ed59a41e"
)


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def remedy_markdown(task_root: Path, before_hash: str) -> str:
    task_id = task_root.name
    config = json.loads((task_root / ".meta/config.json").read_text())
    header_name = config["files"]["solution"][0]
    header = (task_root / header_name).read_text().strip()
    role_map = json.dumps(config["files"], sort_keys=True)
    return f"""# Rejection remedy: `{task_id}`

## Identity

Task ID `{task_id}`; task-spec revision 1; family ID
`legacy-spiral-boundary-tour-v1`; disposition `reject`; source inventory ID
`local-legacy-spiral-matrix`; license result `pass`; generator
`{GENERATOR.as_posix()}`; benchmark screen `reject`. The selected workflow is
`{PROMPT.as_posix()}` and the user supplied family type is
`aider-text-grid-reshaping`.

## Objective

The historical root observably traverses rectangular layers from a selected
corner and direction while skipping blocked cells and accumulating a renamed
domain statistic. The mechanism exists, but it partitions the permanent
official `spiral-matrix` holdout's inward boundary-order capability. It is
therefore rejected and has no replacement objective in this family.

## Public API

The legacy C++17 editable-file order is `{config['files']['solution']}`. Its
complete public declaration is:

```cpp
{header}
```

No API from this root may be retained in a candidate family.

## Behavior table

| Operation | Valid result | Invalid/empty/ordering behavior |
| --- | --- | --- |
| boundary tour | visits unblocked cells and accumulates the root-specific statistic | ragged or dimension-mismatched grids return invalid; paired empty grids return an empty valid result; ordering is an inward corner-selected ring walk |

Duplicates and absent cells are not independent domain concepts: blocked
coordinates are skipped, each visited coordinate appears once, and some roots
stop on the first flagged value. Arithmetic uses unchecked `int` accumulation.
This shared policy is part of the rejection finding, not an acceptance target.

## Implementation invariant

The legacy reference owns four shrinking rectangle bounds and constructs the
same clockwise perimeter vector for every root. Corner, direction, predicate,
aggregate, and early-stop constants are the only substantive variations.
Retaining that ring walker under renamed domains, reversed endpoints, or
changed constants is forbidden. Because the mechanism is holdout-adjacent,
neither a standard container substitute nor a hand-written equivalent can
make this root admissible.

## Starter and reference

The starter is a coherent stub and the `.meta/example.*` files map to both
editable files. The independent-reference requirement is intentionally not
implemented after rejection. No legacy starter, reference renderer, tests, or
API may be copied into a future candidate.

## Tests

The legacy visible/private executables cover rectangularity, empty and narrow
grids, blocked cells, a first flag, and duplicate coordinates. They do not
distinguish the 20 roots' primary control flow. Required negative controls are
the full renamed-domain clone, constants/policy-only clone, and opposite-end
selection clone; all reproduce the same rejected family. Deterministic seeds
are not applicable because rejection stops before implementation.

## Files and metadata

The historical role map is `{role_map}`. The pre-change tree hash is
`{before_hash}`. References, tests, metadata, CMake, and remedy evidence remain
private. No support digest is introduced for a rejected root.

## Build/oracle

The legacy recipe requests C++17, strict warnings, two CTest executables,
clean normal mode, and fresh ASan/UBSan mode. Runtime evidence is recorded
separately as historical audit evidence only; it cannot override the earlier
benchmark rejection. No replacement receipt is expected.

## Family/contamination

Comparison scope is all 190 unordered legacy pairs plus all 26 official Aider
C++ holdouts, using docs, public APIs, references, visible tests, and private
tests. The strongest result is `benchmark_content_overlap` with official
`spiral-matrix` plus `duplicate_family` across the legacy ring template.
Normalizer `spiral-matrix-rejection-v1` removes domain nouns, identifiers,
literals, corner choice, direction, predicates, and aggregate names while
preserving shrinking-boundary control flow.

## Optional dataset handoff

`not_requested`. No rows, renderer evidence, token/mask records, producer
verification, export, consumer verification, split, or release is authorized.

## Acceptance

Run `python3 scripts/plan_spiral_matrix_remedies.py --check`, then the focused
spiral-family tests. Acceptance requires this hash-bound rejection record,
zero materialized candidate roots beneath the re-verification family, the
legacy tree unchanged, and stable failures `benchmark_content_overlap` and
`duplicate_family` for every attempted retention or rename-only clone.
"""


def expected_records(legacy_root: Path, reverify_root: Path) -> dict[Path, str]:
    records: dict[Path, str] = {}
    generator_revision = GENERATOR_REVISION_BEFORE
    remedy_root = reverify_root / ".state/remedy"
    for task_root in sorted(path for path in legacy_root.iterdir() if path.is_dir()):
        task_id = task_root.name
        before_hash = tree_hash(task_root)
        markdown = remedy_markdown(task_root, before_hash)
        markdown_path = remedy_root / f"{task_id}.md"
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": task_id,
            "family_id_before": "legacy-spiral-boundary-tour-v1",
            "tree_hash_before": before_hash,
            "generator_path": GENERATOR.as_posix(),
            "generator_revision": generator_revision,
            "finding_ids": FINDINGS,
            "disposition": "reject",
            "benchmark_screen": "reject",
            "license_screen": "pass",
            "remedy_spec_path": markdown_path.as_posix(),
            "remedy_spec_hash": sha256(markdown.encode()),
            "status": "rejected",
            "primary_core_objective": "achieved",
            "local_status": "rejected_benchmark_overlap",
            "selected_prompt": PROMPT.as_posix(),
            "curriculum_path": CURRICULUM.as_posix(),
            "family_spec_path": FAMILY_SPEC.as_posix(),
            "oracle_evidence": "not_completed_before_disposition",
            "changed_owner_paths": [],
        }
        records[markdown_path] = markdown
        records[remedy_root / f"{task_id}.json"] = (
            json.dumps(record, indent=2, sort_keys=True) + "\n"
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-root", type=Path, default=LEGACY_ROOT)
    parser.add_argument("--reverify-root", type=Path, default=REVERIFY_ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    records = expected_records(args.legacy_root, args.reverify_root)
    mismatches: list[str] = []
    for path, content in records.items():
        if args.check:
            if not path.is_file():
                mismatches.append(path.as_posix())
                continue
            if path.suffix == ".md":
                if path.read_text() != content:
                    mismatches.append(path.as_posix())
                continue
            actual = json.loads(path.read_text())
            expected = json.loads(content)
            mutable = {"oracle_evidence", "changed_owner_paths"}
            if any(actual.get(key) != value for key, value in expected.items() if key not in mutable):
                mismatches.append(path.as_posix())
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    if mismatches:
        raise SystemExit("stale spiral remedy records: " + ", ".join(mismatches))
    print(f"{'Checked' if args.check else 'Wrote'} {len(records) // 2} remedies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
