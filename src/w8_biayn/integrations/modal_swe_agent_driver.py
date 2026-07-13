"""SWE-agent adapter for one sanitized, network-blocked Modal Sandbox."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
import signal
from pathlib import Path, PurePosixPath
import shlex
import time
from typing import Any, Callable, Literal, Mapping

from w8_biayn.modal_agentic_multi_swe_cpp import (
    AGENT_CALL_LIMIT,
    AGENT_CUMULATIVE_COMPLETION_TOKENS,
    AGENT_MAX_INPUT_TOKENS,
    AGENT_TOOL_TIMEOUT_SECONDS,
    AGENT_TOTAL_TIMEOUT_SECONDS,
    AGENT_TURN_MAX_COMPLETION_TOKENS,
    FINALIZER_REVISION,
    MAX_FINAL_BYTES,
    MAX_FINAL_FILES,
    OBSERVATION_CHAR_LIMIT,
    PERSISTED_STREAM_BYTE_LIMIT,
    SANITIZER_REVISION,
    SWE_AGENT_COMMIT,
    SWE_AGENT_CONFIG_SHA256,
    TOOL_PATH_REWRITER_REVISION,
    safe_trajectory_event,
)


WORKSPACE = PurePosixPath("/workspace/repo")
AGENT_HOME = PurePosixPath("/workspace/home")
AGENT_TMP = PurePosixPath("/workspace/tmp")
AGENT_TOOLS = PurePosixPath("/workspace/tools")
TRUSTED_ROOT = PurePosixPath("/opt/w8-trusted")
OUTPUT_ROOT = PurePosixPath("/opt/w8-output")
_CWD_MARKER = "__W8_MODAL_CWD__"


class ModalSWEAgentError(RuntimeError):
    """The agent adapter, sanitizer, or finalizer failed."""


@dataclass(frozen=True)
class ExecResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


def _task_value(task: Mapping[str, Any], name: str) -> str:
    value = str(task.get(name) or "").strip()
    if not value:
        raise ModalSWEAgentError(f"task is missing {name}")
    return value


def workspace_sanitizer_program(task: Mapping[str, Any]) -> str:
    """Return the root-only sanitizer executed inside the official task image."""

    payload = json.dumps(
        {
            "repo": _task_value(task, "repo"),
            "base_ref": _task_value(task, "base_ref"),
            "instance_id": _task_value(task, "instance_id"),
            "sanitizer_revision": SANITIZER_REVISION,
        },
        sort_keys=True,
    )
    program = r"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile

config = json.loads(__W8_CONFIG__)
source = Path("/home") / config["repo"]
workspace = Path("/workspace/repo")
trusted = Path("/opt/w8-trusted")
output = Path("/opt/w8-output")
if not (source / ".git").exists():
    raise SystemExit("official image checkout is missing Git metadata")
head = subprocess.check_output(
    ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
).strip()
if head != config["base_ref"]:
    raise SystemExit("official image checkout does not match base_ref")
status = subprocess.check_output(
    [
        "git",
        "-C",
        str(source),
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--ignore-submodules=none",
    ],
    text=True,
).strip()
if status:
    raise SystemExit("official image checkout is not clean")
submodule_status = subprocess.run(
    ["git", "-C", str(source), "submodule", "status", "--recursive"],
    text=True,
    capture_output=True,
    check=False,
)
if submodule_status.returncode or any(
    line.startswith(("+", "U"))
    for line in submodule_status.stdout.splitlines()
):
    raise SystemExit("submodule state is not exact")


def tracked_entries(repo_root):
    raw = subprocess.check_output(
        ["git", "-C", str(repo_root), "ls-files", "-s", "-z"]
    )
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        header, separator, raw_path = entry.partition(b"\t")
        fields = header.split()
        if not separator or len(fields) != 3 or fields[2] != b"0":
            raise SystemExit("unexpected Git index entry")
        mode = fields[0].decode("ascii")
        object_id = fields[1].decode("ascii")
        relative = Path(os.fsdecode(raw_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit("unsafe tracked path")
        yield mode, object_id, relative


submodule_identities = {}


def materialize(repo_root, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for mode, object_id, relative in tracked_entries(repo_root):
        source_path = repo_root / relative
        target_path = destination / relative
        if mode == "120000":
            raise SystemExit("tracked symlinks are forbidden in the agent workspace")
        if mode == "160000":
            if source_path.is_symlink() or not source_path.is_dir():
                raise SystemExit("submodule gitlink path is not a directory")
            identity_path = source_path.relative_to(source).as_posix()
            if not any(source_path.iterdir()):
                target_path.mkdir(parents=True, exist_ok=True)
                submodule_identities[identity_path] = {
                    "commit": object_id,
                    "state": "uninitialized-empty",
                }
                continue
            actual = subprocess.check_output(
                ["git", "-C", str(source_path), "rev-parse", "HEAD"], text=True
            ).strip()
            if actual != object_id:
                raise SystemExit("submodule gitlink does not match checked-out commit")
            submodule_identities[identity_path] = {
                "commit": actual,
                "state": "materialized",
            }
            materialize(source_path, target_path)
            continue
        if mode not in {"100644", "100755"}:
            raise SystemExit("unsupported tracked Git mode")
        source_mode = source_path.lstat().st_mode
        if not stat.S_ISREG(source_mode):
            raise SystemExit("tracked entry is not a regular file")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path, follow_symlinks=False)
        os.chmod(target_path, 0o755 if mode == "100755" else 0o644)


for path in (
    workspace.parent,
    trusted,
    output,
    Path("/workspace/home"),
    Path("/workspace/tmp"),
    Path("/workspace/tools"),
):
    path.mkdir(parents=True, exist_ok=True)
for child in workspace.parent.iterdir():
    if child.name not in {"repo", "home", "tmp", "tools"}:
        raise SystemExit("unexpected workspace entry")
if workspace.exists():
    shutil.rmtree(workspace)
materialize(source, workspace)
manifest = []
for path in sorted(workspace.rglob("*")):
    relative = path.relative_to(workspace).as_posix()
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
        raise SystemExit("unsafe file type in sanitized workspace")
    if stat.S_ISREG(mode):
        manifest.append(
            {
                "path": relative,
                "mode": stat.S_IMODE(mode),
                "size_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
(trusted / "baseline.manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
with tarfile.open(trusted / "baseline.tar", "w") as archive:
    archive.add(workspace, arcname="repo", recursive=True)
subprocess.run(["git", "-C", str(workspace), "init", "-q"], check=True)
subprocess.run(
    ["git", "-C", str(workspace), "config", "user.email", "w8@invalid"],
    check=True,
)
subprocess.run(
    ["git", "-C", str(workspace), "config", "user.name", "w8 baseline"],
    check=True,
)
subprocess.run(["git", "-C", str(workspace), "add", "-A"], check=True)
subprocess.run(
    ["git", "-C", str(workspace), "commit", "-qm", "trusted baseline"],
    check=True,
)
commit_count = int(
    subprocess.check_output(
        ["git", "-C", str(workspace), "rev-list", "--count", "HEAD"], text=True
    ).strip()
)
if commit_count != 1:
    raise SystemExit("synthetic Git history is not exactly one commit")
for child in Path("/home").iterdir():
    mode = child.lstat().st_mode
    if stat.S_ISDIR(mode):
        shutil.rmtree(child)
    else:
        child.unlink()
canary = trusted / "agent-must-not-read"
canary.write_text("W8_TRUST_CANARY", encoding="utf-8")
for protected in (Path("/root"), Path("/home"), trusted, output):
    os.chmod(protected, 0o700)
subprocess.run(
    [
        "useradd",
        "--system",
        "--user-group",
        "--home-dir",
        "/workspace/home",
        "--shell",
        "/bin/bash",
        "w8agent",
    ],
    check=True,
)
for writable in (
    workspace,
    Path("/workspace/home"),
    Path("/workspace/tmp"),
    Path("/workspace/tools"),
):
    subprocess.run(
        ["chown", "-R", "w8agent:w8agent", str(writable)], check=True
    )
receipt = {
    "schema_version": 1,
    "kind": "agentic-workspace-sanitizer",
    "task_id": config["instance_id"],
    "base_ref": head,
    "sanitizer_revision": config["sanitizer_revision"],
    "file_count": len(manifest),
    "aggregate_size_bytes": sum(row["size_bytes"] for row in manifest),
    "manifest_sha256": hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest(),
    "submodule_identities": dict(sorted(submodule_identities.items())),
    "synthetic_commit_count": commit_count,
    "source_checkout_removed": not source.exists(),
    "agent_uid": subprocess.check_output(
        ["id", "-u", "w8agent"], text=True
    ).strip(),
    "root_canary_present": canary.is_file(),
    "network_blocked_by_controller": True,
    "secrets_mounted": False,
    "volumes_mounted": False,
}
(output / "sanitizer.receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
"""
    return program.replace("__W8_CONFIG__", repr(payload))

def workspace_finalizer_program(task: Mapping[str, Any]) -> str:
    """Return the trusted root finalizer that synthesizes the submitted patch."""

    payload = json.dumps(
        {
            "instance_id": _task_value(task, "instance_id"),
            "finalizer_revision": FINALIZER_REVISION,
            "max_final_files": MAX_FINAL_FILES,
            "max_final_bytes": MAX_FINAL_BYTES,
        },
        sort_keys=True,
    )
    program = r"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile

config = json.loads(__W8_CONFIG__)
workspace = Path("/workspace/repo")
trusted = Path("/opt/w8-trusted")
output = Path("/opt/w8-output")
subprocess.run(["pkill", "-KILL", "-u", "w8agent"], check=False)
file_count = 0
total_bytes = 0
manifest = []
unsafe = []
for path in sorted(workspace.rglob("*")):
    relative = path.relative_to(workspace)
    if relative.parts and relative.parts[0] == ".git":
        continue
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
        unsafe.append(relative.as_posix())
        continue
    if stat.S_ISREG(mode):
        info = path.stat()
        if info.st_nlink != 1:
            unsafe.append(relative.as_posix())
            continue
        file_count += 1
        total_bytes += info.st_size
        manifest.append(
            {
                "path": relative.as_posix(),
                "mode": stat.S_IMODE(mode),
                "size_bytes": info.st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
if (
    unsafe
    or file_count > config["max_final_files"]
    or total_bytes > config["max_final_bytes"]
):
    status = "invalid_final_state"
    patch = ""
    error = "unsafe type, link, or final tree size"
    changed_paths = []
    changed_line_count = 0
else:
    roots = [
        Path("/opt/w8-reconstruct-current"),
        Path("/opt/w8-reconstruct-check"),
    ]
    for root in roots:
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        with tarfile.open(trusted / "baseline.tar") as archive:
            members = archive.getmembers()
            if any(
                member.issym()
                or member.islnk()
                or not (member.isdir() or member.isreg())
                or Path(member.name).is_absolute()
                or ".." in Path(member.name).parts
                for member in members
            ):
                raise SystemExit("trusted baseline archive became unsafe")
            try:
                archive.extractall(root, filter="fully_trusted")
            except TypeError:
                archive.extractall(root)
        repo = root / "repo"
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "w8@invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "w8 baseline"],
            check=True,
        )
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-qm", "trusted baseline"],
            check=True,
        )
    current = roots[0] / "repo"
    for child in list(current.iterdir()):
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if relative.parts and relative.parts[0] == ".git":
            continue
        destination = current / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination, follow_symlinks=False)
            shutil.copymode(path, destination, follow_symlinks=False)
    subprocess.run(["git", "-C", str(current), "add", "-A"], check=True)
    patch = subprocess.check_output(
        [
            "git",
            "-C",
            str(current),
            "diff",
            "--cached",
            "--binary",
            "--full-index",
            "-M",
        ],
        text=True,
    )
    changed_raw = subprocess.check_output(
        ["git", "-C", str(current), "diff", "--cached", "--name-only", "-z"]
    )
    changed_paths = [
        os.fsdecode(item) for item in changed_raw.split(b"\0") if item
    ]
    numstat = subprocess.check_output(
        ["git", "-C", str(current), "diff", "--cached", "--numstat"], text=True
    )
    changed_line_count = 0
    for line in numstat.splitlines():
        added, deleted, _ = line.split("\t", 2)
        if added.isdigit() and deleted.isdigit():
            changed_line_count += int(added) + int(deleted)
    if not patch.strip():
        status, error = "no_changes", ""
    elif "GIT binary patch" in patch or "Binary files " in patch:
        status, error, patch = "invalid_final_state", "binary patch", ""
    else:
        check = subprocess.run(
            ["git", "-C", str(roots[1] / "repo"), "apply", "--check", "-"],
            text=True,
            input=patch,
            capture_output=True,
        )
        if check.returncode:
            status, error, patch = (
                "invalid_final_state",
                "git apply check failed",
                "",
            )
        else:
            status, error = "valid_patch", ""
(output / "final.patch").write_text(patch, encoding="utf-8")
(output / "final-state.manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
receipt = {
    "schema_version": 1,
    "kind": "agentic-final-state",
    "task_id": config["instance_id"],
    "status": status,
    "error": error,
    "finalizer_revision": config["finalizer_revision"],
    "file_count": file_count,
    "aggregate_size_bytes": total_bytes,
    "manifest_sha256": hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest(),
    "patch_sha256": hashlib.sha256(patch.encode()).hexdigest() if patch else None,
    "patch_bytes": len(patch.encode()),
    "changed_paths": changed_paths,
    "changed_file_count": len(changed_paths),
    "changed_line_count": changed_line_count,
    "trusted_apply_check": status == "valid_patch",
}
(output / "finalizer.receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
"""
    return program.replace("__W8_CONFIG__", repr(payload))

def _rewrite_root_paths(value: str) -> str:
    replacements = (
        ("/root/tools/", "/workspace/tools/"),
        ("/root/.swe-agent-env", "/workspace/tools/.swe-agent-env"),
        ("/root/state.json", "/workspace/tools/state.json"),
        ("/root/model.patch", "/workspace/tools/model.patch"),
    )
    for source, target in replacements:
        value = value.replace(source, target)
    return value


def _read_process(process: Any) -> ExecResult:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        stdout = pool.submit(process.stdout.read)
        stderr = pool.submit(process.stderr.read)
        returncode = int(process.wait())
        return ExecResult(
            stdout=str(stdout.result()),
            stderr=str(stderr.result()),
            returncode=returncode,
            timed_out=returncode == 124,
        )


def _bounded_stream(value: str) -> dict[str, Any]:
    encoded = value.encode(errors="replace")
    digest = hashlib.sha256(encoded).hexdigest()
    if len(encoded) <= PERSISTED_STREAM_BYTE_LIMIT:
        return {
            "byte_count": len(encoded),
            "sha256": digest,
            "truncated": False,
            "head": value,
            "tail": "",
        }
    half = PERSISTED_STREAM_BYTE_LIMIT // 2
    return {
        "byte_count": len(encoded),
        "sha256": digest,
        "truncated": True,
        "head": encoded[:half].decode(errors="replace"),
        "tail": encoded[-half:].decode(errors="replace"),
    }


def _bounded_observation(value: str) -> str:
    if len(value) <= OBSERVATION_CHAR_LIMIT:
        return value
    marker = "\n[controller output truncated]\n"
    remaining = OBSERVATION_CHAR_LIMIT - len(marker)
    head = remaining // 2
    tail = remaining - head
    return value[:head] + marker + value[-tail:]


class ModalSandboxRuntime:
    """Small SWE-ReX runtime surface backed by Modal Sandbox calls."""

    def __init__(self, sandbox: Any) -> None:
        self.sandbox = sandbox
        self.environment: ModalSandboxSWEEnv | None = None

    async def upload(
        self,
        request: Any,
        target_path: str | PurePosixPath | None = None,
    ) -> None:
        source = Path(getattr(request, "source_path", request))
        requested_target = getattr(request, "target_path", target_path)
        if requested_target is None:
            raise ModalSWEAgentError("tool upload has no target path")
        target = PurePosixPath(
            _rewrite_root_paths(str(requested_target))
        )
        if not (
            target == AGENT_TOOLS or AGENT_TOOLS in target.parents
        ):
            raise ModalSWEAgentError("tool upload escaped agent tool root")
        entries = (
            [source]
            if source.is_file()
            else [path for path in source.rglob("*") if path.is_file()]
        )
        for path in entries:
            if path.is_symlink():
                raise ModalSWEAgentError("symlinked tool files are forbidden")
            relative = Path(path.name) if source.is_file() else path.relative_to(source)
            destination = target if source.is_file() else target / relative.as_posix()
            mkdir = self.sandbox.exec(
                "mkdir",
                "-p",
                destination.parent.as_posix(),
                timeout=30,
                text=True,
            )
            if mkdir.wait():
                raise ModalSWEAgentError("tool directory creation failed")
            data = path.read_bytes()
            try:
                rewritten = _rewrite_root_paths(data.decode()).encode()
            except UnicodeDecodeError:
                rewritten = data
            self.sandbox.filesystem.write_bytes(
                rewritten, destination.as_posix()
            )
        ownership = self.sandbox.exec(
            "chown",
            "-R",
            "w8agent:w8agent",
            target.as_posix(),
            timeout=30,
            text=True,
        )
        if ownership.wait():
            raise ModalSWEAgentError("tool ownership setup failed")

    async def execute(self, action: Any) -> Any:
        if self.environment is None:
            raise ModalSWEAgentError("runtime has no environment")
        command = str(getattr(action, "command", ""))
        check = "raise" if bool(getattr(action, "check", False)) else "ignore"
        output = self.environment.communicate(
            command,
            timeout=float(
                getattr(action, "timeout", AGENT_TOOL_TIMEOUT_SECONDS)
                or AGENT_TOOL_TIMEOUT_SECONDS
            ),
            check=check,
        )
        event = self.environment.last_tool_event or {}
        return type(
            "ModalCommandResult",
            (),
            {
                "stdout": output,
                "stderr": "",
                "exit_code": int(event.get("returncode") or 0),
            },
        )()

    async def create_session(self, request: Any) -> None:
        return None

    async def run_in_session(self, action: Any) -> Any:
        raise ModalSWEAgentError(
            "persistent SWE-ReX sessions are disabled"
        )


class ModalSandboxDeployment:
    def __init__(self, sandbox: Any) -> None:
        self.runtime = ModalSandboxRuntime(sandbox)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def is_alive(self, timeout: int | float = 10) -> bool:
        process = self.runtime.sandbox.exec(
            "true", timeout=min(float(timeout), 10), text=True
        )
        return int(process.wait()) == 0


class ModalSandboxSWEEnv:
    """Duck-typed SWE-agent environment with one logical working directory."""

    def __init__(self, sandbox: Any) -> None:
        self.sandbox = sandbox
        self.deployment = ModalSandboxDeployment(sandbox)
        self.cwd = WORKSPACE
        self.deployment.runtime.environment = self
        self.name = "main"
        self.repo = None
        self.clean_multi_line_functions = lambda value: value
        self._environment: dict[str, str] = {}
        self.tool_events: list[dict[str, Any]] = []
        self.last_tool_event: dict[str, Any] | None = None

    def start(self) -> None:
        self.cwd = WORKSPACE

    def reset(self) -> None:
        self.cwd = WORKSPACE

    def hard_reset(self) -> None:
        raise ModalSWEAgentError(
            "in-place agent retries are forbidden; restart a pristine Sandbox"
        )

    def close(self) -> None:
        process = self.sandbox.exec(
            "pkill", "-KILL", "-u", "w8agent", timeout=10, text=True
        )
        process.wait()

    def set_env_variables(self, values: Mapping[str, Any]) -> None:
        for key, value in values.items():
            if key.upper().endswith(("TOKEN", "KEY", "SECRET")):
                continue
            self._environment[str(key)] = str(value)

    def _command(self, command: str) -> list[str]:
        rewritten = _rewrite_root_paths(command)
        wrapped = (
            "set +e\n"
            + rewritten
            + "\nstatus=$?\n"
            + f'printf "\\n{_CWD_MARKER}%s\\n" "$PWD"\n'
            + "exit $status\n"
        )
        env = {
            "HOME": AGENT_HOME.as_posix(),
            "TMPDIR": AGENT_TMP.as_posix(),
            "PATH": (
                "/workspace/tools/registry/bin:"
                "/workspace/tools/edit_anthropic/bin:"
                "/workspace/tools/review_on_submit_m/bin:"
                + AGENT_TOOLS.as_posix()
                + ":/usr/local/bin:/usr/bin:/bin"
            ),
            "PYTHONPATH": "/workspace/tools/registry/lib",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            **self._environment,
        }
        env_args = [
            item
            for key, value in sorted(env.items())
            for item in (key, value)
        ]
        return [
            "runuser",
            "-u",
            "w8agent",
            "--",
            "env",
            "-i",
            *[f"{env_args[index]}={env_args[index + 1]}" for index in range(0, len(env_args), 2)],
            "bash",
            "--noprofile",
            "--norc",
            "-lc",
            wrapped,
        ]

    def communicate(
        self,
        input: str,
        timeout: int | float = AGENT_TOOL_TIMEOUT_SECONDS,
        *,
        check: Literal["warn", "ignore", "raise"] = "ignore",
        error_msg: str = "Command failed",
    ) -> str:
        started = time.monotonic()
        process = self.sandbox.exec(
            *self._command(input),
            timeout=min(float(timeout), AGENT_TOOL_TIMEOUT_SECONDS),
            workdir=self.cwd.as_posix(),
            text=True,
        )
        try:
            result = _read_process(process)
        finally:
            cleanup = self.sandbox.exec(
                "pkill", "-KILL", "-u", "w8agent", timeout=10, text=True
            )
            cleanup_code = int(cleanup.wait())
        output = result.stdout
        marker = output.rfind("\n" + _CWD_MARKER)
        if marker >= 0:
            cwd_line, _, remainder = output[marker + 1 :].partition("\n")
            candidate = PurePosixPath(cwd_line[len(_CWD_MARKER) :])
            if candidate == WORKSPACE or WORKSPACE in candidate.parents:
                self.cwd = candidate
            output = output[:marker] + (
                ("\n" + remainder) if remainder else ""
            )
        event = {
            "index": len(self.tool_events),
            "command": _rewrite_root_paths(input),
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "duration_seconds": round(time.monotonic() - started, 6),
            "stdout": _bounded_stream(output),
            "stderr": _bounded_stream(result.stderr),
            "background_cleanup_ok": cleanup_code in {0, 1},
        }
        self.tool_events.append(event)
        self.last_tool_event = event
        combined = _bounded_observation(output + result.stderr)
        if result.returncode and check == "raise":
            raise ModalSWEAgentError(
                f"{error_msg}: exit {result.returncode}: {combined[-2000:]}"
            )
        return combined

    def read_file(
        self,
        path: str | PurePosixPath,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        del encoding, errors
        path = _rewrite_root_paths(str(path))
        process = self.sandbox.exec(
            *self._command(f"cat -- {shlex.quote(path)}"),
            timeout=AGENT_TOOL_TIMEOUT_SECONDS,
            workdir=self.cwd.as_posix(),
            text=True,
        )
        result = _read_process(process)
        if result.returncode:
            raise ModalSWEAgentError("agent file read failed")
        return result.stdout.split("\n" + _CWD_MARKER, 1)[0]

    def write_file(
        self, path: str | PurePosixPath, content: str
    ) -> None:
        destination = PurePosixPath(_rewrite_root_paths(str(path)))
        if destination.is_absolute() and not (
            destination == WORKSPACE
            or WORKSPACE in destination.parents
            or destination == AGENT_TOOLS
            or AGENT_TOOLS in destination.parents
        ):
            raise ModalSWEAgentError("agent write escaped workspace")
        self.sandbox.filesystem.write_text(content, destination.as_posix())
        ownership = self.sandbox.exec(
            "chown",
            "w8agent:w8agent",
            destination.as_posix(),
            timeout=30,
            text=True,
        )
        if ownership.wait():
            raise ModalSWEAgentError("agent file ownership setup failed")

    def execute_command(
        self,
        command: str,
        shell: bool = True,
        check: bool = False,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        if not shell:
            raise ModalSWEAgentError("non-shell execution is unsupported")
        previous = self.cwd
        target = WORKSPACE if cwd in {None, "/"} else PurePosixPath(
            _rewrite_root_paths(str(cwd))
        )
        if target != WORKSPACE and WORKSPACE not in target.parents:
            raise ModalSWEAgentError("independent command escaped workspace")
        if env:
            self.set_env_variables(env)
        self.cwd = target
        try:
            self.communicate(
                command,
                check="raise" if check else "ignore",
                timeout=AGENT_TOOL_TIMEOUT_SECONDS,
            )
        finally:
            self.cwd = previous

    def interrupt_session(self) -> None:
        process = self.sandbox.exec(
            "pkill",
            "-INT",
            "-u",
            "w8agent",
            timeout=10,
            text=True,
        )
        process.wait()


def run_pinned_swe_agent(
    *,
    sandbox: Any,
    problem_statement: str,
    server_url: str,
    api_key: str,
    output_dir: str | Path,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    config_path: str | Path = "/opt/swe-agent/config/default_backticks.yaml",
) -> dict[str, Any]:
    """Run the exact pinned SWE-agent and return only safe trajectory data."""

    import yaml
    from sweagent.agent.agents import (
        DefaultAgentConfig,
        get_agent_from_config,
    )
    from sweagent.agent.problem_statement import TextProblemStatement
    from sweagent.exceptions import InstanceCostLimitExceededError

    config_file = Path(config_path)
    if hashlib.sha256(config_file.read_bytes()).hexdigest() != (
        SWE_AGENT_CONFIG_SHA256
    ):
        raise ModalSWEAgentError("pinned SWE-agent config hash changed")
    payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))["agent"]
    payload["templates"]["system_template"] = (
        "You are a C++ issue-resolution agent in an offline repository. "
        "Use tools to inspect and edit source. Never reveal private reasoning."
    )
    payload["templates"]["instance_template"] = (
        "{{problem_statement}}\n\nRepository: {{working_dir}}"
    )
    payload["templates"]["max_observation_length"] = OBSERVATION_CHAR_LIMIT
    payload["tools"]["execution_timeout"] = AGENT_TOOL_TIMEOUT_SECONDS
    payload["tools"]["total_execution_timeout"] = AGENT_TOTAL_TIMEOUT_SECONDS
    payload["model"] = {
        "name": "openai/glm-4.7-flash",
        "api_base": server_url.rstrip("/") + "/v1",
        "api_key": api_key,
        "temperature": 0.0,
        "top_p": 1.0,
        "per_instance_cost_limit": 0.0,
        "total_cost_limit": 0.0,
        "per_instance_call_limit": AGENT_CALL_LIMIT,
        "max_input_tokens": AGENT_MAX_INPUT_TOKENS,
        "max_output_tokens": AGENT_TURN_MAX_COMPLETION_TOKENS,
        "completion_kwargs": {
            "max_tokens": AGENT_TURN_MAX_COMPLETION_TOKENS,
        },
        "retry": {"retries": 1, "min_wait": 1, "max_wait": 1},
        "choose_api_key_by_thread": False,
    }
    os.environ["SWE_AGENT_CONFIG_ROOT"] = "/opt/swe-agent"
    agent_config = DefaultAgentConfig.model_validate(payload)
    agent = get_agent_from_config(agent_config)
    original_update = agent.model._update_stats

    def bounded_update(
        *, input_tokens: int, output_tokens: int, cost: float
    ) -> None:
        if (
            agent.model.stats.tokens_received + output_tokens
            > AGENT_CUMULATIVE_COMPLETION_TOKENS
        ):
            raise InstanceCostLimitExceededError(
                "cumulative completion-token budget exceeded"
            )
        original_update(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )

    agent.model._update_stats = bounded_update
    environment = ModalSandboxSWEEnv(sandbox)
    if event_sink is not None:
        from sweagent.agent.hooks.abstract import AbstractAgentHook

        class SafeIncrementalHook(AbstractAgentHook):
            def __init__(self) -> None:
                self.index = 0
                self.tool_index = 0

            def on_step_done(self, *, step: Any, info: Mapping[str, Any]) -> None:
                serialized = (
                    step.model_dump()
                    if hasattr(step, "model_dump")
                    else dict(step)
                )
                event = safe_trajectory_event(serialized, self.index)
                model_stats = info.get("model_stats") or {}
                event_sink(
                    {
                        "schema_version": 1,
                        "step": self.index,
                        "event": event,
                        "tool_events": environment.tool_events[
                            self.tool_index :
                        ],
                        "exit_status": info.get("exit_status"),
                        "model_stats": {
                            key: value
                            for key, value in model_stats.items()
                            if isinstance(value, (int, float))
                            and not isinstance(value, bool)
                        },
                    }
                )
                self.index += 1
                self.tool_index = len(environment.tool_events)

        agent.add_hook(SafeIncrementalHook())
    problem = TextProblemStatement(text=problem_statement)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    from sweagent.agent.agents import _TotalExecutionTimeExceeded

    def alarm_handler(signum: int, frame: Any) -> None:
        raise _TotalExecutionTimeExceeded()

    prior_handler = signal.getsignal(signal.SIGALRM)
    prior_logging_disable = logging.root.manager.disable
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, AGENT_TOTAL_TIMEOUT_SECONDS)
    logging.disable(logging.CRITICAL)
    try:
        result = agent.run(
            env=environment,
            problem_statement=problem,
            output_dir=output,
        )
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prior_handler)
        logging.disable(prior_logging_disable)
        for path in output.rglob("*.traj"):
            path.unlink()
    events = [
        safe_trajectory_event(step, index)
        for index, step in enumerate(result.trajectory)
    ]
    stats = dict(result.info.get("model_stats") or {})
    if int(stats.get("tokens_received") or 0) > (
        AGENT_CUMULATIVE_COMPLETION_TOKENS
    ):
        raise ModalSWEAgentError(
            "cumulative completion-token budget exceeded"
        )
    return {
        "schema_version": 1,
        "swe_agent_commit": SWE_AGENT_COMMIT,
        "tool_path_rewriter_revision": TOOL_PATH_REWRITER_REVISION,
        "events": events,
        "event_count": len(events),
        "exit_status": result.info.get("exit_status"),
        "model_stats": {
            key: value
            for key, value in stats.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        },
        "tool_events": environment.tool_events,
        "tool_event_count": len(environment.tool_events),
        "nonzero_tool_exits": sum(
            event["returncode"] != 0 for event in environment.tool_events
        ),
        "tool_timeouts": sum(
            event["timed_out"] is True for event in environment.tool_events
        ),
        "raw_trajectory_persisted": False,
        "incremental_events_persisted": event_sink is not None,
        "reasoning_persisted": False,
    }
