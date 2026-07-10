from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path("scripts/lium_create_h100_pod.py")
EXECUTOR_HUID = "golden-shark-c6"
EXECUTOR_ID = "4f4ad1c1-7d95-41a7-bd0d-35aa950d73ac"
TEMPLATE_ID = "345273fa-4818-46f7-a8fa-32f0e331713c"
TEMPLATE_IMAGE = "daturaai/pytorch"
TEMPLATE_TAG = "2.12.0-py3.12-cuda13.0.2-devel-ubuntu24.04-dind"
TEMPLATE_STATUS = "VERIFY_SUCCESS"
INTERPRETER_PATH = "/opt/homebrew/opt/python@3.11/bin/python3.11"
INTERPRETER_SHA256 = "1" * 64
INTERPRETER_VERSION = "3.11.14"
LIUM_CLI_PATH = "/opt/homebrew/bin/lium"
LIUM_CLI_SHA256 = "2" * 64
LIUM_VERSION = "0.0.3"
SSH_PUBLIC_KEY_PATH = "/Users/tester/.ssh/id_ed25519.pub"
SSH_PUBLIC_KEY = "ssh-ed25519 AAAATEST provider-test"
SSH_PUBLIC_KEY_SHA256 = hashlib.sha256(f"{SSH_PUBLIC_KEY}\n".encode()).hexdigest()


def _module():
    spec = importlib.util.spec_from_file_location("lium_create_h100_pod_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _executor(**overrides):
    values = {
        "id": EXECUTOR_ID,
        "huid": EXECUTOR_HUID,
        "gpu_type": "H100",
        "gpu_count": 8,
        "price_per_hour": 0,
        "price_per_gpu_hour": 0.0,
        "status": "AVAILABLE",
        "gpu_model": "NVIDIA H100 80GB HBM3",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _template(template_id: str = TEMPLATE_ID):
    return SimpleNamespace(
        id=template_id,
        name="Pytorch (Cuda + DinD)",
        huid="pytorch-cuda-dind",
        docker_image="daturaai/pytorch",
        docker_image_tag="2.12.0-py3.12-cuda13.0.2-devel-ubuntu24.04-dind",
        category="PUBLIC",
        status="VERIFY_SUCCESS",
    )


class FakeLium:
    def __init__(self, *, executor=None, fresh=None, ready=True) -> None:
        self.executor = executor or _executor()
        self.fresh = fresh or self.executor
        self.calls: list[tuple] = []
        self.active_pods: list[SimpleNamespace] = []
        self.ps_side_effects: list[object] | None = None
        self.up_error: Exception | None = None
        self.up_creates_before_error = False
        self.up_result: object = {
            "id": "pod-123",
            "name": "issue-32-e06-h100",
            "status": "CREATING",
        }
        self.down_error: Exception | None = None
        self.schedule_error: Exception | None = None
        self.wait_error: Exception | None = None
        self.ready_result = self._ready_pod() if ready else None
        self.explicit_template = _template()

    def _ready_pod(self):
        return SimpleNamespace(
            id="pod-123",
            name="issue-32-e06-h100",
            status="RUNNING",
            huid="steady-otter-42",
            ssh_cmd="ssh root@203.0.113.10 -p 2222",
            executor=self.fresh,
            removal_scheduled_at="2026-07-10T14:00:00Z",
        )

    def ls(self, **kwargs):
        self.calls.append(("ls", kwargs))
        return [self.executor]

    def get_executor(self, executor_id):
        self.calls.append(("get_executor", executor_id))
        return self.fresh

    def default_docker_template(self, executor_id):
        self.calls.append(("default_docker_template", executor_id))
        return _template()

    def get_template(self, template_id):
        self.calls.append(("get_template", template_id))
        return self.explicit_template

    def up(self, **kwargs):
        self.calls.append(("up", kwargs))
        if self.up_error is None or self.up_creates_before_error:
            self.active_pods.append(SimpleNamespace(id="pod-123", name=kwargs["name"]))
        if self.up_error is not None:
            raise self.up_error
        return self.up_result

    def schedule_termination(self, pod, *, termination_time):
        self.calls.append(("schedule_termination", pod.id, termination_time))
        if self.schedule_error is not None:
            raise self.schedule_error
        return {"removal_scheduled_at": termination_time}

    def wait_ready(self, pod, *, timeout, poll_interval):
        self.calls.append(("wait_ready", pod, timeout, poll_interval))
        if self.wait_error is not None:
            raise self.wait_error
        return self.ready_result

    def ps(self):
        self.calls.append(("ps",))
        if self.ps_side_effects is not None and self.ps_side_effects:
            result = self.ps_side_effects.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return list(self.active_pods)

    def down(self, pod):
        self.calls.append(("down", pod.id))
        if self.down_error is not None:
            raise self.down_error
        self.active_pods = [candidate for candidate in self.active_pods if candidate.id != pod.id]
        return {"removed": pod.id}


def _args(*extra: str) -> list[str]:
    return [
        "up",
        EXECUTOR_HUID,
        "--ttl",
        "2h",
        "--name",
        "issue-32-e06-h100",
        "--yes",
        "--template-id",
        TEMPLATE_ID,
        "--template-image",
        TEMPLATE_IMAGE,
        "--template-tag",
        TEMPLATE_TAG,
        "--template-status",
        TEMPLATE_STATUS,
        "--expected-provider-version",
        "1.1.0",
        "--expected-interpreter-path",
        INTERPRETER_PATH,
        "--expected-interpreter-sha256",
        INTERPRETER_SHA256,
        "--expected-interpreter-version",
        INTERPRETER_VERSION,
        "--expected-lium-sdk-version",
        LIUM_VERSION,
        "--expected-lium-cli-path",
        LIUM_CLI_PATH,
        "--expected-lium-cli-sha256",
        LIUM_CLI_SHA256,
        "--expected-lium-cli-version",
        LIUM_VERSION,
        "--ssh-public-key-path",
        SSH_PUBLIC_KEY_PATH,
        "--ssh-public-key-sha256",
        SSH_PUBLIC_KEY_SHA256,
        "--max-rate",
        "18",
        "--poll-timeout",
        "20",
        "--poll-interval",
        "2",
        *extra,
    ]


def _run(module, client: FakeLium, capsys, argv=None):
    runtime = {
        "provider_version": module.VERSION,
        "interpreter": {
            "path": INTERPRETER_PATH,
            "sha256": INTERPRETER_SHA256,
            "version": INTERPRETER_VERSION,
        },
        "lium_sdk": {"distribution": "lium.io", "version": LIUM_VERSION},
        "lium_cli": {
            "path": LIUM_CLI_PATH,
            "sha256": LIUM_CLI_SHA256,
            "version": LIUM_VERSION,
            "version_source": "wrapper_verified_cli_version",
        },
    }
    exit_code = module.main(
        argv or _args(),
        client_factory=lambda credential: client,
        now_fn=lambda: datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
        credential_reader=lambda: bytearray(b"supervisor-lium-key"),
        runtime_probe=lambda args: runtime,
        ssh_public_key_reader=lambda path, digest: SSH_PUBLIC_KEY,
    )
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    return exit_code, json.loads(lines[0])


def test_valid_sdk_flow_schedules_before_wait_and_never_enters_ssh(capsys) -> None:
    module = _module()
    client = FakeLium()

    exit_code, record = _run(module, client, capsys)

    assert exit_code == 0
    assert record["status"] == "RUNNING"
    assert record["pod"] == {
        "id": "pod-123",
        "name": "issue-32-e06-h100",
        "huid": "steady-otter-42",
        "ssh_cmd": "ssh root@203.0.113.10 -p 2222",
    }
    assert record["executor"]["huid"] == EXECUTOR_HUID
    assert record["executor"]["gpu_count"] == 8
    assert record["executor"]["gpu_model"] == "NVIDIA H100 80GB HBM3"
    assert record["executor"]["observed_rate_usd_per_hour"] == 0.0
    assert record["executor"]["observed_rate_status"] == "provider_reported_zero"
    assert record["executor"]["max_rate_usd_per_hour"] == 18.0
    assert record["template"]["id"] == TEMPLATE_ID
    assert record["template"]["docker_image"] == TEMPLATE_IMAGE
    assert record["template"]["docker_image_tag"] == TEMPLATE_TAG
    assert record["template"]["status"] == TEMPLATE_STATUS
    assert record["runtime_evidence"]["lium_sdk"]["version"] == LIUM_VERSION
    assert record["access"] == {
        "ssh_public_key_path": SSH_PUBLIC_KEY_PATH,
        "ssh_public_key_sha256": SSH_PUBLIC_KEY_SHA256,
    }
    assert record["schedule"] == {
        "confirmed": True,
        "server_removal_scheduled_at": "2026-07-10T14:00:00Z",
        "termination_time": "2026-07-10T14:00:00Z",
        "ttl_seconds": 7200,
        "verified_termination_time": "2026-07-10T14:00:00Z",
    }
    names = [call[0] for call in client.calls]
    assert names == [
        "ls",
        "get_executor",
        "get_template",
        "ps",
        "up",
        "schedule_termination",
        "wait_ready",
    ]
    up_call = next(call for call in client.calls if call[0] == "up")
    assert up_call[1]["executor_id"] == EXECUTOR_ID
    assert up_call[1]["ssh_keys"] == [SSH_PUBLIC_KEY]


def test_explicit_template_and_ports_are_forwarded(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.explicit_template = _template("explicit-template-id")

    exit_code, record = _run(
        module,
        client,
        capsys,
        _args("--template-id", "explicit-template-id", "--ports", "4"),
    )

    assert exit_code == 0
    assert record["template"]["id"] == "explicit-template-id"
    assert ("get_template", "explicit-template-id") in client.calls
    up_call = next(call for call in client.calls if call[0] == "up")
    assert up_call[1]["ports"] == 4


def test_preexisting_exact_allocation_name_rejects_before_mutation(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.active_pods = [SimpleNamespace(id="pod-existing", name="issue-32-e06-h100")]

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "allocation_name_in_use"
    assert record["details"] == {
        "cleanup_status": "NOT_REQUIRED",
        "cleanup_count": 0,
        "cleanup_pod_ids": [],
    }
    assert not any(call[0] in {"up", "down", "schedule_termination"} for call in client.calls)
    assert [pod.id for pod in client.active_pods] == ["pod-existing"]


def test_post_create_exception_recovers_and_terminates_new_exact_name(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.up_creates_before_error = True
    client.up_error = RuntimeError("LIUM_API_KEY=must-not-leak")

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "pod_create_failed"
    assert record["details"] == {
        "cleanup_status": "CONFIRMED",
        "cleanup_count": 1,
        "cleanup_pod_ids": ["pod-123"],
    }
    assert client.calls.count(("ps",)) == 3
    assert ("down", "pod-123") in client.calls
    assert not any(call[0] in {"schedule_termination", "wait_ready"} for call in client.calls)
    assert client.active_pods == []
    assert "must-not-leak" not in json.dumps(record)
    assert module.MAX_RECOVERY_LOOKUP_SECONDS == 60
    assert module.MAX_RECOVERY_LOOKUP_SECONDS < 300


def test_malformed_create_response_recovers_and_terminates(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.up_result = {"name": "issue-32-e06-h100", "status": "CREATING"}

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "pod_create_response_invalid"
    assert record["details"] == {
        "cleanup_status": "CONFIRMED",
        "cleanup_count": 1,
        "cleanup_pod_ids": ["pod-123"],
    }
    assert ("down", "pod-123") in client.calls
    assert not any(call[0] in {"schedule_termination", "wait_ready"} for call in client.calls)


def test_ambiguous_create_with_no_recovery_match_is_cleanup_unconfirmed(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.up_error = RuntimeError("provider-secret-must-not-leak")

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "pod_create_cleanup_unconfirmed"
    assert record["details"] == {
        "cleanup_status": "UNCONFIRMED",
        "cleanup_count": 0,
        "cleanup_pod_ids": [],
    }
    assert not any(call[0] == "down" for call in client.calls)
    assert not any(call[0] in {"schedule_termination", "wait_ready"} for call in client.calls)
    assert "provider-secret-must-not-leak" not in json.dumps(record)


def test_ambiguous_create_lookup_failure_is_cleanup_unconfirmed_and_redacted(
    capsys,
) -> None:
    module = _module()
    client = FakeLium()
    client.up_creates_before_error = True
    client.up_error = RuntimeError("LIUM_API_KEY=create-secret")
    client.ps_side_effects = [
        [],
        RuntimeError("LIUM_API_KEY=lookup-secret-1"),
        RuntimeError("LIUM_API_KEY=lookup-secret-2"),
    ]

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "pod_create_cleanup_unconfirmed"
    assert record["details"] == {
        "cleanup_status": "UNCONFIRMED",
        "cleanup_count": 0,
        "cleanup_pod_ids": [],
    }
    assert not any(
        call[0] in {"down", "schedule_termination", "wait_ready"} for call in client.calls
    )
    serialized = json.dumps(record)
    assert "create-secret" not in serialized
    assert "lookup-secret" not in serialized


def test_every_new_exact_name_match_is_terminated(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.up_error = RuntimeError("ambiguous create")
    matches = [
        SimpleNamespace(id="pod-new-a", name="issue-32-e06-h100"),
        SimpleNamespace(id="pod-new-b", name="issue-32-e06-h100"),
    ]
    client.ps_side_effects = [[], matches, matches]

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "pod_create_failed"
    assert record["details"] == {
        "cleanup_status": "CONFIRMED",
        "cleanup_count": 2,
        "cleanup_pod_ids": ["pod-new-a", "pod-new-b"],
    }
    assert ("down", "pod-new-a") in client.calls
    assert ("down", "pod-new-b") in client.calls


def test_live_unknown_executor_status_is_eligible_after_huid_revalidation(capsys) -> None:
    module = _module()
    unknown = _executor(status="unknown")
    client = FakeLium(executor=unknown, fresh=unknown)

    exit_code, record = _run(module, client, capsys)

    assert exit_code == 0
    assert record["status"] == "RUNNING"
    assert record["executor"]["huid"] == EXECUTOR_HUID


@pytest.mark.parametrize(
    "executor,expected_error",
    [
        (_executor(gpu_count=4), "executor_gpu_count_mismatch"),
        (_executor(gpu_type="B200", gpu_model="NVIDIA B200"), "executor_gpu_model_mismatch"),
        (_executor(price_per_hour=18.01), "executor_rate_exceeded"),
        (_executor(status="RENTED"), "executor_unavailable"),
    ],
)
def test_invalid_executor_never_creates_pod(capsys, executor, expected_error: str) -> None:
    module = _module()
    client = FakeLium(executor=executor)

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == expected_error
    assert not any(call[0] == "up" for call in client.calls)


def test_revalidation_drift_never_creates_pod(capsys) -> None:
    module = _module()
    client = FakeLium(fresh=_executor(price_per_hour=1))

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "executor_changed"
    assert not any(call[0] == "up" for call in client.calls)


def test_schedule_failure_terminates_only_created_pod_and_redacts_exception(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.schedule_error = RuntimeError("LIUM_API_KEY=must-not-leak")

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "schedule_failed"
    assert record["details"] == {"pod_id": "pod-123", "cleanup": "TERMINATED"}
    assert "must-not-leak" not in json.dumps(record)
    assert ("down", "pod-123") in client.calls
    assert not any(call[0] == "wait_ready" for call in client.calls)


def test_readiness_timeout_terminates_only_created_pod(capsys) -> None:
    module = _module()
    client = FakeLium(ready=False)

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "readiness_timeout"
    assert record["details"]["cleanup"] == "TERMINATED"
    assert ("down", "pod-123") in client.calls


@pytest.mark.parametrize(
    "server_schedule",
    [None, "2026-07-10T14:01:00Z", "not-an-iso-time"],
    ids=["missing", "mismatch", "unparseable"],
)
def test_unverified_server_schedule_rejects_and_cleans_up(capsys, server_schedule) -> None:
    module = _module()
    client = FakeLium()
    client.ready_result.removal_scheduled_at = server_schedule

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "schedule_verification_failed"
    assert record["details"] == {"pod_id": "pod-123", "cleanup": "TERMINATED"}
    assert ("down", "pod-123") in client.calls


def test_equivalent_utc_offset_schedule_is_normalized_and_recorded(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.ready_result.removal_scheduled_at = "2026-07-10T14:00:00+00:00"

    exit_code, record = _run(module, client, capsys)

    assert exit_code == 0
    assert record["schedule"]["server_removal_scheduled_at"] == ("2026-07-10T14:00:00+00:00")
    assert record["schedule"]["verified_termination_time"] == ("2026-07-10T14:00:00Z")


def test_bad_explicit_template_status_rejects_before_creation(capsys) -> None:
    module = _module()
    client = FakeLium()
    client.explicit_template.status = "VERIFY_FAILED"

    exit_code, record = _run(module, client, capsys)

    assert exit_code != 0
    assert record["error"] == "template_unusable"
    assert not any(call[0] == "up" for call in client.calls)


def test_noninteractive_yes_is_required_before_sdk_construction(capsys) -> None:
    module = _module()
    constructed = False

    def factory(credential):
        del credential
        nonlocal constructed
        constructed = True
        return FakeLium()

    argv = _args()
    argv.remove("--yes")
    exit_code = module.main(
        argv,
        client_factory=factory,
    )
    record = json.loads(capsys.readouterr().out)

    assert exit_code != 0
    assert record["error"] == "noninteractive_required"
    assert constructed is False


def test_stdin_credential_constructs_config_without_ambient_env(
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    client = FakeLium()
    credential = bytearray(b"supervisor-only-lium-key")
    captured: dict[str, object] = {}
    monkeypatch.setenv("LIUM_API_KEY", "ambient-attacker-key")

    def factory(value: bytearray):
        captured["credential"] = bytes(value)
        captured["ambient_key_present"] = "LIUM_API_KEY" in os.environ
        return client

    exit_code = module.main(
        _args(),
        client_factory=factory,
        now_fn=lambda: datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
        credential_reader=lambda: credential,
        runtime_probe=lambda args: {
            "provider_version": module.VERSION,
            "interpreter": {},
            "lium_sdk": {},
            "lium_cli": {},
        },
        ssh_public_key_reader=lambda path, digest: SSH_PUBLIC_KEY,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert captured == {
        "credential": b"supervisor-only-lium-key",
        "ambient_key_present": False,
    }
    assert credential == bytearray(len(credential))
    assert "supervisor-only-lium-key" not in output
    assert "ambient-attacker-key" not in output


def test_sdk_client_uses_config_api_key_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    captured: dict[str, object] = {}

    class Config:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key

    class Lium:
        def __init__(self, config: Config) -> None:
            captured["config"] = config

    sdk = SimpleNamespace(Config=Config, Lium=Lium)
    monkeypatch.setitem(sys.modules, "lium", SimpleNamespace(sdk=sdk))
    monkeypatch.setitem(sys.modules, "lium.sdk", sdk)

    client = module._new_lium_client(bytearray(b"stdin-api-key"))

    assert isinstance(client, Lium)
    assert captured["api_key"] == "stdin-api-key"
    assert isinstance(captured["config"], Config)


def test_version_does_not_construct_sdk(capsys) -> None:
    module = _module()

    exit_code = module.main(["--version"], client_factory=lambda credential: pytest.fail())

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == module.VERSION


def test_load_ssh_public_key_binds_one_regular_file(tmp_path: Path) -> None:
    module = _module()
    public_key = tmp_path / "id_ed25519.pub"
    public_key.write_text(f"{SSH_PUBLIC_KEY}\n", encoding="utf-8")

    loaded = module._load_ssh_public_key(
        public_key.resolve(), hashlib.sha256(public_key.read_bytes()).hexdigest()
    )

    assert loaded == SSH_PUBLIC_KEY


@pytest.mark.parametrize(
    ("content", "digest"),
    [
        ("not-a-public-key\n", None),
        ("ssh-ed25519 AAAA first\nssh-ed25519 BBBB second\n", None),
        (f"{SSH_PUBLIC_KEY}\n", "0" * 64),
    ],
)
def test_load_ssh_public_key_rejects_malformed_or_mismatched_input(
    tmp_path: Path, content: str, digest: str | None
) -> None:
    module = _module()
    public_key = tmp_path / "id_ed25519.pub"
    public_key.write_text(content, encoding="utf-8")

    with pytest.raises(module.ProviderFailure) as exc_info:
        module._load_ssh_public_key(
            public_key.resolve(), digest or hashlib.sha256(public_key.read_bytes()).hexdigest()
        )

    assert exc_info.value.code == "ssh_public_key_invalid"


def test_load_ssh_public_key_rejects_relative_and_symlink_paths(tmp_path: Path) -> None:
    module = _module()
    public_key = tmp_path / "id_ed25519.pub"
    public_key.write_text(f"{SSH_PUBLIC_KEY}\n", encoding="utf-8")
    digest = hashlib.sha256(public_key.read_bytes()).hexdigest()
    symlink = tmp_path / "linked.pub"
    symlink.symlink_to(public_key)

    with pytest.raises(module.ProviderFailure):
        module._load_ssh_public_key(Path("id_ed25519.pub"), digest)
    with pytest.raises(module.ProviderFailure):
        module._load_ssh_public_key(symlink, digest)
