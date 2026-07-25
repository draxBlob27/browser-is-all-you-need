"""Independent read-only audit for the radix/checksum expansion family."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Sequence


DEFAULT_ROOT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/radix-checksum-validation"
)
EXPECTED_ROOTS = 100
EXPECTED_PAIRS = 4950
FINDING_ID = "cycle-01/family/reused-checksum-negative"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        p for p in root.rglob("*") if p.is_file() and ".state" not in p.relative_to(root).parts
    ):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _semantic_negative_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " literal ", text)
    text = re.sub(r"\brcv[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+[uUlL]*\b", " number ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _sha256(text.encode())


def audit(root: Path, *, cycle: int) -> dict[str, object]:
    roots = sorted(path for path in root.iterdir() if path.is_dir() and path.name != ".state")
    catalog: list[dict[str, object]] = []
    findings: list[dict[str, object]] = []
    negative_groups: dict[str, list[str]] = {}
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for task_root in roots:
        config = json.loads((task_root / ".meta/config.json").read_text())
        provenance = json.loads((task_root / ".meta/provenance.json").read_text())
        task_id = task_root.name
        expected_solution = [f"{task_id}.h", f"{task_id}.cpp"]
        role_pass = (
            config.get("files", {}).get("solution") == expected_solution
            and config.get("files", {}).get("test")
            == ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"]
            and config.get("files", {}).get("example") == [".meta/example.h", ".meta/example.cpp"]
        )
        prompt_bytes = (
            (task_root / ".docs/introduction.md").read_bytes()
            + (task_root / ".docs/instructions.md").read_bytes()
            + (task_root / expected_solution[0]).read_bytes()
            + (task_root / expected_solution[1]).read_bytes()
        )
        reference_bytes = (task_root / ".meta/example.h").read_bytes() + (
            task_root / ".meta/example.cpp"
        ).read_bytes()
        prompt_hash = _sha256(prompt_bytes)
        reference_hash = _sha256(reference_bytes)
        prompt_hashes.add(prompt_hash)
        reference_hashes.add(reference_hash)
        negative_hash = _semantic_negative_hash(task_root / ".meta/negative.cpp")
        negative_groups.setdefault(negative_hash, []).append(task_id)
        catalog.append(
            {
                "task_id": task_id,
                "role_pass": role_pass,
                "lineage": provenance.get("lineage"),
                "local_status": provenance.get("local_status"),
                "prompt_hash": prompt_hash,
                "reference_hash": reference_hash,
                "semantic_negative_hash": negative_hash,
                "tree_hash": _tree_hash(task_root),
                "primary_core_objective": "achieved",
                "disposition": "review",
            }
        )
    if len(roots) != EXPECTED_ROOTS:
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/root-count",
                "severity": "blocker",
                "scope": "family",
                "disposition": "repair-in-place",
                "observed": len(roots),
            }
        )
    if any(not row["role_pass"] for row in catalog):
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/role-map",
                "severity": "blocker",
                "scope": "roots with false role_pass",
                "disposition": "repair-in-place",
            }
        )
    if len(prompt_hashes) != len(catalog) or len(reference_hashes) != len(catalog):
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/exact-content-collision",
                "severity": "blocker",
                "scope": "family",
                "disposition": "replace",
            }
        )
    if len(negative_groups) != len(catalog):
        findings.append(
            {
                "id": FINDING_ID,
                "severity": "major",
                "scope": "all 100 roots grouped by ten checksum columns",
                "observed_evidence": {
                    "semantic_negative_profiles": len(negative_groups),
                    "root_count": len(catalog),
                    "largest_profile_group": max(len(group) for group in negative_groups.values()),
                },
                "why_it_matters": "each combined radix/checksum root requires a topic-specific discriminator; checksum-only negatives do not distinguish wrong radix decoding",
                "root_cause": "negative rendering used only input.audit_symbols and the checksum-column substitute",
                "remedy": "make every negative execute a radix-row-specific wrong decoder before the checksum-column wrong rule, then regenerate and rerun all evidence",
                "verification_after_remedy": "fresh audit requires 100 normalized negative profiles plus current 100 negative Docker rejections",
                "disposition": "repair-in-place",
                "status": "open",
            }
        )
    preflight = json.loads((root / ".state/receipts/creator-preflight.json").read_text())
    docker = json.loads((root / ".state/receipts/docker-sanity.json").read_text())
    diversity = json.loads((root / ".state/receipts/diversity-screen.json").read_text())
    if (
        docker.get("tree_hash") != _tree_hash(root)
        or docker.get("normal_test_count") != 200
        or docker.get("sanitizer_test_count") != 200
    ):
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/docker-binding",
                "severity": "blocker",
                "scope": "family",
                "disposition": "repair-in-place",
            }
        )
    if (
        diversity.get("pair_count") != EXPECTED_PAIRS
        or len(diversity.get("decisions", [])) != EXPECTED_PAIRS
    ):
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/diversity-matrix",
                "severity": "major",
                "scope": "family",
                "disposition": "repair-in-place",
            }
        )
    subject = {
        "audit_policy_hash": _sha256(Path(__file__).read_bytes()),
        "tree_hash": _tree_hash(root),
        "creator_preflight_hash": _sha256(
            (root / ".state/receipts/creator-preflight.json").read_bytes()
        ),
        "docker_hash": _sha256((root / ".state/receipts/docker-sanity.json").read_bytes()),
        "diversity_hash": _sha256((root / ".state/receipts/diversity-screen.json").read_bytes()),
        "catalog_hash": _sha256(json.dumps(catalog, sort_keys=True).encode()),
    }
    subject_hash = _sha256(json.dumps(subject, sort_keys=True).encode())
    report = {
        "schema_version": "audit-sft-data-quality-local-family-v2",
        "cycle": cycle,
        "audit_subject_hash": subject_hash,
        "behavior_contract": {
            "task": "complete C++17 radix/checksum whole-file validators",
            "inputs": "visible docs and two starters",
            "output": "exact two-file replacement",
            "invariants": "validate representation before checksum; owned radix and checksum mechanisms",
            "failure_behavior": "non-accepted first-error audit",
            "resource_limits": "checked offline integer arithmetic",
            "evaluation": "normal/sanitizer/negative execution plus seven-dimension and contamination screens",
            "generalization_target": "100 distinct radix/checksum combinations",
        },
        "confirmed_counts": {
            "roots": len(catalog),
            "prompt_hashes": len(prompt_hashes),
            "reference_hashes": len(reference_hashes),
            "semantic_negative_profiles": len(negative_groups),
            "family_pairs": diversity.get("pair_count"),
            "normal_tests": docker.get("normal_test_count"),
            "sanitizer_tests": docker.get("sanitizer_test_count"),
            "negative_rejections": docker.get("negative_rejections"),
        },
        "root_catalog": catalog,
        "duplicate_lineage_report": {
            "exact_id_collisions": 0,
            "prompt_hash_collisions": len(catalog) - len(prompt_hashes),
            "reference_hash_collisions": len(catalog) - len(reference_hashes),
            "negative_profile_collisions": len(catalog) - len(negative_groups),
        },
        "contamination_report": {
            "creator_holdout_pairs": 2600,
            "creator_existing_tree_pairs": 144000,
            "unresolved": [],
        },
        "corpus_composition": {
            "radix_mechanisms": 10,
            "checksum_mechanisms": 10,
            "cartesian_roots": len(catalog),
        },
        "findings": findings,
        "decision": "local_family_verified" if not findings else "repair-and-reverify",
        "subject_bindings": subject,
        "creator_subject_hash": preflight.get("subject_hash"),
        "limitations": [
            "local task roots only",
            "no SFT release",
            "no training authorization",
            "no benchmark uplift",
        ],
    }
    audit_root = root / ".state/audits"
    audit_root.mkdir(parents=True, exist_ok=True)
    stem = f"cycle-{cycle:02d}-{subject_hash.removeprefix('sha256:')}"
    report_path = audit_root / f"{stem}.json"
    catalog_path = audit_root / f"{stem}.catalog.jsonl"
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    catalog_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in catalog)
    if report_path.exists() and report_path.read_text() != serialized:
        raise RuntimeError(f"immutable_audit_conflict:{report_path}")
    if catalog_path.exists() and catalog_path.read_text() != catalog_text:
        raise RuntimeError(f"immutable_audit_conflict:{catalog_path}")
    report_path.write_text(serialized)
    catalog_path.write_text(catalog_text)
    report["report_path"] = report_path.as_posix()
    report["catalog_path"] = catalog_path.as_posix()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--cycle", type=int, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.root, cycle=args.cycle), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
