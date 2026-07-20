"""Build and verify a reference-shaped SFT JSONL from local Aider task roots."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from w8_biayn.integrations.moonlight_aider_task_sft import (
    _stable_json,
    _stable_pretty_json,
    _write_if_same_or_forced,
    build_train_row,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_aider_task_eval import AiderTask, load_task


DEFAULT_TASKS_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify-sft")
DEFAULT_REFERENCE = Path(".w8-biayn/data/aider-tasks-sft/sft/train.jsonl")
SCHEMA_VERSION = "aider-tasks-reverify-sft-projection-v1"
EXPECTED_ROW_KEYS = {"label", "messages", "metadata", "task_id"}
EXPECTED_METADATA_KEYS = {"purpose", "subset", "task_id"}
PRIVATE_PROMPT_MARKERS = (".meta/", ".state/", "CMakeLists.txt")
BALANCED_TREE_MAINTENANCE_HEADING = (
    "## C. Deterministic build, metadata, and admission implementation"
)
BALANCED_TREE_PUBLIC_RULES_RESUME = "The index must own a real "


@dataclass(frozen=True)
class DatasetPaths:
    root: Path
    manifest: Path
    train_jsonl: Path


def dataset_paths(root: Path | str) -> DatasetPaths:
    path = Path(root)
    return DatasetPaths(
        root=path,
        manifest=path / "manifest.json",
        train_jsonl=path / "sft" / "train.jsonl",
    )


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"row must be an object at {path}:{line_number}")
        rows.append(row)
    return rows


def _validate_row_shape(row: dict[str, Any], *, context: str) -> None:
    if set(row) != EXPECTED_ROW_KEYS:
        raise ValueError(f"{context}: row keys differ from reference: {sorted(row)}")
    metadata = row.get("metadata")
    if not isinstance(metadata, dict) or set(metadata) != EXPECTED_METADATA_KEYS:
        raise ValueError(f"{context}: metadata keys differ from reference")
    messages = row.get("messages")
    if (
        not isinstance(messages, list)
        or len(messages) != 2
        or [message.get("role") for message in messages if isinstance(message, dict)]
        != ["user", "assistant"]
        or any(not isinstance(message.get("content"), str) for message in messages)
    ):
        raise ValueError(f"{context}: expected exactly user and assistant messages")
    task_id = row.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError(f"{context}: task_id must be a nonempty string")
    if row.get("label") != task_id or metadata.get("task_id") != task_id:
        raise ValueError(f"{context}: label and metadata task_id must equal task_id")
    if metadata.get("subset") != "train":
        raise ValueError(f"{context}: subset must be train")


def validate_reference_contract(reference: Path = DEFAULT_REFERENCE) -> dict[str, Any]:
    if not reference.is_file():
        raise FileNotFoundError(f"reference train JSONL does not exist: {reference}")
    rows = _read_jsonl(reference)
    if not rows:
        raise ValueError(f"reference train JSONL is empty: {reference}")
    for index, row in enumerate(rows):
        _validate_row_shape(row, context=f"reference row {index}")
    return {
        "path": str(reference),
        "row_count": len(rows),
        "sha256": _sha256(reference.read_bytes()),
        "row_keys": sorted(EXPECTED_ROW_KEYS),
        "metadata_keys": sorted(EXPECTED_METADATA_KEYS),
    }


def discover_task_roots(tasks_root: Path) -> tuple[Path, ...]:
    if not tasks_root.is_dir():
        raise FileNotFoundError(f"task root does not exist: {tasks_root}")
    roots = tuple(
        sorted(
            (path.parent.parent for path in tasks_root.rglob(".meta/config.json")
             if ".state" not in path.relative_to(tasks_root).parts),
            key=lambda path: path.relative_to(tasks_root).as_posix(),
        )
    )
    if not roots:
        raise ValueError(f"no Aider task configs found below {tasks_root}")
    if len(set(roots)) != len(roots):
        raise ValueError("duplicate task roots discovered")
    return roots


def _resolved_task_ids(tasks_root: Path, task_roots: Sequence[Path]) -> dict[Path, str]:
    by_leaf: dict[str, list[Path]] = defaultdict(list)
    for task_root in task_roots:
        by_leaf[task_root.name].append(task_root)
    resolved: dict[Path, str] = {}
    for leaf, roots in sorted(by_leaf.items()):
        for task_root in roots:
            if len(roots) == 1:
                task_id = leaf
            else:
                parts = task_root.relative_to(tasks_root).parts
                if len(parts) < 3:
                    raise ValueError(f"cannot qualify colliding task id: {task_root}")
                task_id = "--".join((*parts[:-1], leaf))
            resolved[task_root] = task_id
    if len(set(resolved.values())) != len(resolved):
        raise ValueError("task-id qualification did not resolve every collision")
    return resolved


def _task_source_hash(task_root: Path) -> str:
    digest = hashlib.sha256()
    config = json.loads((task_root / ".meta/config.json").read_text(encoding="utf-8"))
    files = config.get("files", {})
    selected = {
        ".meta/config.json",
        ".docs/introduction.md",
        ".docs/instructions.md",
        *files.get("solution", []),
        *files.get("example", []),
    }
    for relative in sorted(selected):
        path = task_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"required prompt/target file missing: {path}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _task_for_projection(task: AiderTask) -> tuple[AiderTask, tuple[str, ...]]:
    """Remove a known owner-spec appendix and reject all private-path leakage."""
    instructions = task.instructions
    sanitizations: list[str] = []
    if BALANCED_TREE_MAINTENANCE_HEADING in instructions:
        before, after_heading = instructions.split(
            BALANCED_TREE_MAINTENANCE_HEADING, 1
        )
        resume_at = after_heading.find(BALANCED_TREE_PUBLIC_RULES_RESUME)
        if resume_at < 0:
            raise ValueError(
                f"{task.task_dir}: cannot safely remove the balanced-tree "
                "maintenance appendix"
            )
        instructions = (
            before.rstrip()
            + "\n\n"
            + after_heading[resume_at:].lstrip()
        )
        sanitizations.append("balanced_tree_owner_spec_appendix_removed")

    projected = AiderTask(
        task_dir=task.task_dir,
        task_id=task.task_id,
        editable_files=task.editable_files,
        introduction=task.introduction,
        instructions=instructions,
    )
    visible_text = "\n".join((projected.introduction, projected.instructions))
    leaked = [marker for marker in PRIVATE_PROMPT_MARKERS if marker in visible_text]
    if leaked:
        raise ValueError(
            f"{task.task_dir}: private prompt markers remain: {sorted(leaked)}"
        )
    return projected, tuple(sanitizations)


def build_rows(tasks_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build deterministic reference-shaped rows and source inventory records."""
    task_roots = discover_task_roots(tasks_root)
    resolved_ids = _resolved_task_ids(tasks_root, task_roots)
    rows: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for task_root in task_roots:
        relative = task_root.relative_to(tasks_root)
        if len(relative.parts) < 3:
            raise ValueError(f"expected <family-type>/<family>/<task>: {relative}")
        task_id = resolved_ids[task_root]
        purpose = task_root.parent.name
        source_task = load_task(task_root)
        task, prompt_sanitizations = _task_for_projection(source_task)
        row = build_train_row(
            task=task,
            example_files=load_example_files_from_config(task_root),
            task_id=task_id,
            label=task_id,
            purpose=purpose,
        )
        row["metadata"] = {
            "purpose": purpose,
            "subset": "train",
            "task_id": task_id,
        }
        _validate_row_shape(row, context=str(relative))
        rows.append(row)
        inventory.append({
            "family": purpose,
            "source": relative.as_posix(),
            "source_hash": _task_source_hash(task_root),
            "source_task_id": task_root.name,
            "task_id": task_id,
            "qualified_for_collision": task_id != task_root.name,
            "prompt_sanitizations": list(prompt_sanitizations),
        })
    return rows, inventory


def _dataset_content(rows: Sequence[dict[str, Any]]) -> str:
    return "".join(_stable_json(row) + "\n" for row in rows)


def build_dataset(
    *,
    tasks_root: Path,
    out: Path,
    reference: Path = DEFAULT_REFERENCE,
    force: bool = False,
) -> DatasetPaths:
    reference_contract = validate_reference_contract(reference)
    rows, inventory = build_rows(tasks_root)
    content = _dataset_content(rows)
    family_counts = Counter(item["family"] for item in inventory)
    paths = dataset_paths(out)
    manifest = {
        "collision_qualified_row_count": sum(
            bool(item["qualified_for_collision"]) for item in inventory
        ),
        "family_counts": dict(sorted(family_counts.items())),
        "family_count": len(family_counts),
        "files": {"sft_train": "sft/train.jsonl"},
        "inventory": inventory,
        "kind": "aider-task-whole-sft-projection",
        "projection_status": "user_requested_local_projection_not_dataset_release",
        "prompt_boundary": {
            "private_markers": list(PRIVATE_PROMPT_MARKERS),
            "sanitized_row_count": sum(
                bool(item["prompt_sanitizations"]) for item in inventory
            ),
            "status": "pass",
        },
        "reference_contract": reference_contract,
        "schema_version": SCHEMA_VERSION,
        "source_root": str(tasks_root),
        "train_bytes": len(content.encode("utf-8")),
        "train_count": len(rows),
        "train_sha256": _sha256(content.encode("utf-8")),
    }
    _write_if_same_or_forced(paths.train_jsonl, content, force=force)
    _write_if_same_or_forced(
        paths.manifest, _stable_pretty_json(manifest), force=force
    )
    verify_dataset(tasks_root=tasks_root, out=out, reference=reference)
    return paths


def verify_dataset(
    *, tasks_root: Path, out: Path, reference: Path = DEFAULT_REFERENCE
) -> dict[str, Any]:
    paths = dataset_paths(out)
    if not paths.train_jsonl.is_file() or not paths.manifest.is_file():
        raise FileNotFoundError(f"dataset is incomplete under {out}")
    reference_contract = validate_reference_contract(reference)
    expected_rows, expected_inventory = build_rows(tasks_root)
    expected_content = _dataset_content(expected_rows)
    observed_content = paths.train_jsonl.read_text(encoding="utf-8")
    if observed_content != expected_content:
        raise ValueError("train.jsonl does not exactly match current source tasks")
    observed_rows = _read_jsonl(paths.train_jsonl)
    if len(observed_rows) != len(expected_rows):
        raise ValueError("train row count mismatch")
    if len({row["task_id"] for row in observed_rows}) != len(observed_rows):
        raise ValueError("train task IDs are not unique")
    for index, row in enumerate(observed_rows):
        _validate_row_shape(row, context=f"output row {index}")
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    checks = {
        "schema": manifest.get("schema_version") == SCHEMA_VERSION,
        "train_count": manifest.get("train_count") == len(expected_rows),
        "train_sha256": manifest.get("train_sha256") == _sha256(paths.train_jsonl.read_bytes()),
        "train_bytes": manifest.get("train_bytes") == len(paths.train_jsonl.read_bytes()),
        "inventory": manifest.get("inventory") == expected_inventory,
        "reference": manifest.get("reference_contract") == reference_contract,
        "state_excluded": all(".state" not in item["source"].split("/")
                              for item in expected_inventory),
        "prompt_boundary": manifest.get("prompt_boundary") == {
            "private_markers": list(PRIVATE_PROMPT_MARKERS),
            "sanitized_row_count": sum(
                bool(item["prompt_sanitizations"]) for item in expected_inventory
            ),
            "status": "pass",
        },
    }
    if not all(checks.values()):
        raise ValueError(f"dataset manifest verification failed: {checks}")
    return {
        "status": "pass",
        "schema_version": SCHEMA_VERSION,
        "tasks_root": str(tasks_root),
        "output_root": str(out),
        "train_jsonl": str(paths.train_jsonl),
        "train_count": len(expected_rows),
        "family_count": len({item["family"] for item in expected_inventory}),
        "collision_qualified_row_count": sum(
            bool(item["qualified_for_collision"]) for item in expected_inventory
        ),
        "train_sha256": _sha256(paths.train_jsonl.read_bytes()),
        "reference_sha256": reference_contract["sha256"],
        "row_shape_matches_reference": True,
        "private_state_excluded": True,
        "private_prompt_markers_excluded": True,
        "prompt_sanitized_row_count": sum(
            bool(item["prompt_sanitizations"]) for item in expected_inventory
        ),
        "release_claim": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, default=DEFAULT_TASKS_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        result = verify_dataset(
            tasks_root=args.tasks_root, out=args.out, reference=args.reference
        )
        print(_stable_pretty_json(result), end="")
    else:
        paths = build_dataset(
            tasks_root=args.tasks_root,
            out=args.out,
            reference=args.reference,
            force=args.force,
        )
        print(paths.train_jsonl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
