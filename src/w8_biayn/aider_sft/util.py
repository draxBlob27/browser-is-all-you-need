"""Deterministic I/O, hashing, path, and locking helpers."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import AiderSftError

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FENCE_LINE_RE = re.compile(r"^[ ]{0,3}`{3,}", re.MULTILINE)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the one canonical JSON representation used by this pipeline."""

    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha256(value: str, field: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise AiderSftError("static_schema_error", f"{field} is not a lowercase SHA-256")
    return value


def fingerprint(domain: str, *values: bytes | str | Mapping[str, Any] | Sequence[Any]) -> str:
    digest = hashlib.sha256()
    digest.update(domain.encode("utf-8"))
    digest.update(b"\0")
    for value in values:
        if isinstance(value, bytes):
            payload = value
        elif isinstance(value, str):
            payload = value.encode("utf-8")
        else:
            payload = canonical_json_bytes(value)
        digest.update(str(len(payload)).encode("ascii"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def normalize_relative_path(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise AiderSftError("unsafe_path", f"unsafe relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or value != path.as_posix():
        raise AiderSftError("unsafe_path", f"path is not canonical POSIX: {value!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise AiderSftError("unsafe_path", f"path contains an unsafe component: {value!r}")
    return value


def resolve_under(root: Path, relative: str) -> Path:
    relative = normalize_relative_path(relative)
    root_resolved = root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise AiderSftError("unsafe_path", f"path escapes root: {relative}")
    return candidate


def validate_regular_file(path: Path, *, root: Path | None = None) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise AiderSftError("static_schema_error", f"missing file: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise AiderSftError("unsafe_path", f"not a regular non-symlink file: {path}")
    if info.st_nlink != 1:
        raise AiderSftError("hardlink_rejected", f"hardlinked file: {path}")
    if root is not None:
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise AiderSftError("unsafe_path", f"file escapes root: {path}") from exc


def normalize_text_bytes(raw: bytes, *, label: str) -> bytes:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise AiderSftError("static_schema_error", f"UTF-8 BOM is forbidden: {label}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AiderSftError("static_schema_error", f"invalid UTF-8: {label}") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
    return text.encode("utf-8")


def validate_fence_safe(raw: bytes, *, label: str) -> None:
    text = normalize_text_bytes(raw, label=label).decode("utf-8")
    if _FENCE_LINE_RE.search(text):
        raise AiderSftError(
            "whole_format_failed",
            f"model-visible file contains an unrepresentable fence line: {label}",
        )


def hash_file_records(domain: str, files: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    digest.update(domain.encode("utf-8"))
    digest.update(b"\0")
    for relative in sorted(files):
        normalize_relative_path(relative)
        payload = files[relative]
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(payload)).encode("ascii"))
        digest.update(b"\0")
        digest.update(payload)
    return digest.hexdigest()


def tree_files(root: Path, *, exclude: Iterable[str] = ()) -> dict[str, bytes]:
    excluded = set(exclude)
    result: dict[str, bytes] = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        validate_regular_file(path, root=root)
        result[normalize_relative_path(relative)] = path.read_bytes()
    return result


def atomic_write(path: Path, data: bytes, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def write_json(path: Path, value: Any, *, pretty: bool = True) -> None:
    atomic_write(path, pretty_json_bytes(value) if pretty else canonical_json_bytes(value))


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AiderSftError("static_schema_error", f"cannot read JSON {path}: {exc}") from exc


def read_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise AiderSftError(
                        "static_schema_error", f"invalid JSONL at {path}:{line_number}"
                    ) from exc
    except OSError as exc:
        raise AiderSftError("static_schema_error", f"cannot read JSONL {path}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    payload = b"".join(canonical_json_bytes(row) for row in rows)
    atomic_write(path, payload)


def manifest_entries(
    root: Path,
    *,
    exclude: Iterable[str] = ("manifest.json", "readiness.json"),
) -> list[dict[str, Any]]:
    excluded = set(exclude)
    entries: list[dict[str, Any]] = []
    for relative, content in tree_files(root, exclude=excluded).items():
        entries.append(
            {
                "path": relative,
                "bytes": len(content),
                "sha256": sha256_bytes(content),
                "rows": content.count(b"\n") if relative.endswith(".jsonl") else None,
                "schema_version": _manifest_schema_version(relative, content),
                "role": _manifest_role(relative),
            }
        )
    return entries


def _manifest_schema_version(relative: str, content: bytes) -> str | int:
    if relative.endswith(".json"):
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AiderSftError(
                "static_schema_error", f"invalid JSON artifact: {relative}"
            ) from exc
        if isinstance(value, dict) and isinstance(value.get("schema_version"), (str, int)):
            return value["schema_version"]
    elif relative.endswith(".jsonl"):
        versions: set[str | int] = set()
        try:
            for line in content.splitlines():
                if not line.strip():
                    continue
                value = json.loads(line)
                if isinstance(value, dict) and isinstance(value.get("schema_version"), (str, int)):
                    versions.add(value["schema_version"])
        except json.JSONDecodeError as exc:
            raise AiderSftError(
                "static_schema_error", f"invalid JSONL artifact: {relative}"
            ) from exc
        if len(versions) == 1:
            return next(iter(versions))
        if len(versions) > 1:
            return "mixed"
    return "not_applicable"


def _manifest_role(relative: str) -> str:
    exact = {
        "DATASET_CARD.md": "documentation",
        "NOTICE": "legal_notice",
        "licenses.json": "license_manifest",
        "config.lock.json": "configuration_lock",
        "source-manifest.json": "source_inventory",
        "benchmark-denylist.json": "benchmark_denylist",
        "split-manifest.json": "split_manifest",
        "consumer-lock.json": "consumer_contract",
        "tokenizer-render-policy.json": "tokenizer_policy",
        "sft/train.jsonl": "training_rows",
        "sft/token-records.jsonl": "token_evidence",
    }
    if relative in exact:
        return exact[relative]
    prefixes = (
        ("eval/", "evaluation_prompt"),
        ("reports/", "release_report"),
        ("private/canonical-tasks/", "private_canonical_task"),
        ("private/candidates/", "private_candidate"),
        ("private/evaluator-index", "private_evaluator_index"),
        ("private/grader-support/", "private_grader_support"),
        ("private/admission/", "private_admission_evidence"),
        ("private/generation/", "private_generation_evidence"),
        ("private/rejected/", "private_rejection_evidence"),
        ("private/review/", "private_review_evidence"),
    )
    for prefix, role in prefixes:
        if relative.startswith(prefix):
            return role
    return "immutable_release_artifact"


def verify_manifest_entries(
    root: Path,
    entries: Sequence[Mapping[str, Any]],
    *,
    exclude: Iterable[str] = ("manifest.json", "readiness.json"),
) -> None:
    observed = manifest_entries(root, exclude=exclude)
    if list(entries) != observed:
        raise AiderSftError(
            "consumer_export_manifest_mismatch",
            "manifest content does not match files, sizes, hashes, and row counts",
        )


@contextlib.contextmanager
def run_lock(root: Path) -> Iterator[Path]:
    """Hold the only mutable lock, in the sibling state directory."""

    state_root = root.parent / f"{root.name}.state"
    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = state_root / "dataset.lock"
    with lock_path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AiderSftError("retryable_error", f"another writer owns {lock_path}") from exc
        yield state_root


def require_empty_or_incomplete_root(root: Path, *, resume: bool) -> None:
    readiness = root / "readiness.json"
    if readiness.exists():
        raise AiderSftError("human_review_stale", f"ready root is immutable: {root}")
    if root.exists() and any(root.iterdir()) and not resume:
        raise AiderSftError("static_schema_error", f"non-empty root requires --resume: {root}")


def chmod_tree_readonly(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            path.chmod(0o444)
        elif path.is_dir():
            path.chmod(0o555)
    root.chmod(0o555)
