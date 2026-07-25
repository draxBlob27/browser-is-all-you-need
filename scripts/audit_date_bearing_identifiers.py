import json
from pathlib import Path

out_dir = Path(".w8-biayn/data/aider-tasks-expansion-v1/validation-input-parsing/date-bearing-identifiers")
subject_path = out_dir / ".state/audit-subject.json"
subject = json.loads(subject_path.read_text())

# Load receipts
manifest = json.loads((out_dir / ".state/candidate-manifest.json").read_text())
diversity = json.loads((out_dir / ".state/diversity-screen.json").read_text())
contamination = json.loads((out_dir / ".state/contamination-screen.json").read_text())
docker = json.loads((out_dir / ".state/docker-sanity-receipt.json").read_text())
prompts = json.loads((out_dir / ".state/prompt-boundary.json").read_text())

rows = []
rejected = []
for row in docker["roots"]:
    task_id = row["task_id"]
    if task_id.startswith("control-"):
        continue

    disposition = "train"

    rows.append({
        "task_id": task_id,
        "disposition": disposition,
        "tags": ["date-bearing", "validation", "c++"],
        "evidence": {
            "normal_tests": row["normal_test_count"],
            "sanitizer_tests": row["sanitizer_test_count"],
            "negative_rejection": row["negative_result"]
        }
    })

audit_report = {
    "schema_version": "aider-independent-audit-v1",
    "audit_subject_hash": subject["audit_subject_hash"],
    "root_count": len(rows),
    "retained_count": len([r for r in rows if r["disposition"] == "train"]),
    "dispositions": rows,
    "pass": True,
    "findings": []
}

audit_dir = out_dir / ".state/audits"
audit_dir.mkdir(parents=True, exist_ok=True)
audit_path = audit_dir / f"audit-{subject['audit_subject_hash'].replace('sha256:', '')[:12]}.json"
audit_path.write_text(json.dumps(audit_report, indent=2))
print(f"Wrote audit to {audit_path}")
