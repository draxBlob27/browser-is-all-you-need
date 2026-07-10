from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path("scripts/lium_terminate_h100_pod.py")
ALLOCATION_ID = "pod-issue32-001"
ALLOCATION_NAME = "issue-32-dispatcher-abba"


def _module():
    spec = importlib.util.spec_from_file_location("lium_terminate_h100_pod_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeLium:
    def __init__(self, *, present: bool = True, down_removes: bool = True) -> None:
        self.pods = (
            [SimpleNamespace(id=ALLOCATION_ID, name=ALLOCATION_NAME)] if present else []
        )
        self.down_removes = down_removes
        self.calls: list[tuple] = []

    def ps(self):
        self.calls.append(("ps",))
        return list(self.pods)

    def down(self, pod):
        self.calls.append(("down", pod.id))
        if self.down_removes:
            self.pods = [item for item in self.pods if item.id != pod.id]
        return {"removed": pod.id}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifacts(root: Path) -> tuple[Path, Path]:
    provider = root / "provider.json"
    provider.write_text(
        json.dumps(
            {
                "schema": "lium-h100-pod-create/v2",
                "status": "RUNNING",
                "pod": {"id": ALLOCATION_ID, "name": ALLOCATION_NAME},
                "create_reconciliation": {
                    "status": "CONFIRMED_UNIQUE",
                    "pod_id": ALLOCATION_ID,
                    "allocation_name": ALLOCATION_NAME,
                    "final_active_pod_ids": [ALLOCATION_ID],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    receipt = root / "launch.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "h100-lium-launch-receipt/v2",
                "status": "COMPLETED",
                "provider_output": {
                    "path": str(provider.resolve()),
                    "sha256": _sha256(provider),
                    "size_bytes": provider.stat().st_size,
                },
                "allocation": {"issue_number": 32, "name": ALLOCATION_NAME},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return provider, receipt


def _run(module, root: Path, client: FakeLium, capsys):
    provider, launch = _artifacts(root)
    output = root / "termination.json"
    code = module.main(
        [
            "--provider-output",
            str(provider),
            "--launch-receipt",
            str(launch),
            "--allocation-id",
            ALLOCATION_ID,
            "--allocation-name",
            ALLOCATION_NAME,
            "--receipt",
            str(output.resolve()),
            "--yes",
        ],
        client_factory=lambda credential: client,
        credential_reader=lambda: bytearray(b"supervisor-lium-key"),
        sleep_fn=lambda seconds: None,
    )
    rendered = json.loads(capsys.readouterr().out)
    return code, rendered, json.loads(output.read_text(encoding="utf-8"))


def test_terminates_only_bound_allocation_and_confirms_absence(tmp_path: Path, capsys) -> None:
    module = _module()
    client = FakeLium()
    client.pods.append(SimpleNamespace(id="pod-unrelated", name="issue-99-other"))

    code, rendered, receipt = _run(module, tmp_path, client, capsys)

    assert code == 0
    assert rendered["status"] == "TERMINATED"
    assert receipt["postflight"]["confirmed_absent"] is True
    assert ("down", ALLOCATION_ID) in client.calls
    assert all(call != ("down", "pod-unrelated") for call in client.calls)


def test_already_absent_is_successfully_receipted(tmp_path: Path, capsys) -> None:
    module = _module()
    code, rendered, _ = _run(module, tmp_path, FakeLium(present=False), capsys)

    assert code == 0
    assert rendered["status"] == "ALREADY_ABSENT"


def test_persistent_target_fails_closed(tmp_path: Path, capsys) -> None:
    module = _module()
    code, rendered, _ = _run(
        module,
        tmp_path,
        FakeLium(down_removes=False),
        capsys,
    )

    assert code == 2
    assert rendered["status"] == "ERROR"
    assert rendered["error"] == "termination_unconfirmed"


def test_same_name_other_id_is_never_terminated(tmp_path: Path, capsys) -> None:
    module = _module()
    client = FakeLium(present=False)
    client.pods = [SimpleNamespace(id="pod-conflict", name=ALLOCATION_NAME)]

    code, rendered, _ = _run(module, tmp_path, client, capsys)

    assert code == 2
    assert rendered["error"] == "allocation_identity_conflict"
    assert not any(call[0] == "down" for call in client.calls)
