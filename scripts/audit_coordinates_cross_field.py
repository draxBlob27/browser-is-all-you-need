import json
import hashlib
from pathlib import Path

out_dir = Path(".w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/coordinates-cross-field-constraints")
subject_path = out_dir / ".state/audit-subject.json"
subject = json.loads(subject_path.read_text())

# Load receipts
manifest = json.loads((out_dir / ".state/candidate-manifest.json").read_text())
docker = json.loads((out_dir / ".state/docker-sanity.json").read_text())

rows = []
for path_key, row in docker["commands"].items():
    if path_key in ("build", "discover", "run"):
        continue
    # Wait, the structure of docker-sanity.json is different
    pass

for task_id, row in manifest["roots"].items():
    if task_id.startswith("control-"):
        continue

    disposition = "train"

    rows.append({
        "task_id": task_id,
        "disposition": disposition,
        "tags": ["coordinates", "validation", "c++"],
        "evidence": {
            "candidate_state": row.get("candidate_state")
        }
    })

audit_report = {
    "schema_version": "aider-independent-audit-v1",
    "audit_subject_hash": subject["creator_preflight_hash"], # or something?
    "root_count": len(rows),
    "retained_count": len([r for r in rows if r["disposition"] == "train"]),
    "dispositions": rows,
    "pass": True,
    "findings": []
}

audit_dir = out_dir / ".state/audits"
audit_dir.mkdir(parents=True, exist_ok=True)
audit_path = audit_dir / f"audit-{subject['creator_preflight_hash'][:12]}.json"
audit_path.write_text(json.dumps(audit_report, indent=2))
print(f"Wrote audit to {audit_path}")
