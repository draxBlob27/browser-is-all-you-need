"""Fail-closed admission helpers for immutable clean-room Aider task trees."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping

from .prompt import build_prompt, render_whole_edit
from .schema import AiderTask, TokenEvidence, canonical_sha256, file_sha256


PRIVATE_COMPONENTS = {
    ".meta",
    ".mutants",
    ".private",
    ".reference",
    ".state",
    "tests",
    "test",
    "CMakeLists.txt",
}


class AdmissionError(ValueError):
    """A source root cannot be safely admitted to the RL task bundle."""


def tree_sha256(root: str | Path) -> str:
    """Hash a regular-file-only tree, binding paths, modes, sizes, and bytes."""

    base = Path(root).resolve(strict=True)
    digest = hashlib.sha256()
    seen_inodes: set[tuple[int, int]] = set()
    for path in sorted(base.rglob("*"), key=lambda item: item.relative_to(base).as_posix()):
        relative = path.relative_to(base).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise AdmissionError(f"symlink is forbidden in task tree: {relative}")
        if path.is_dir():
            digest.update(f"D\0{relative}\0{stat.S_IMODE(info.st_mode):o}\0".encode())
            continue
        if not stat.S_ISREG(info.st_mode):
            raise AdmissionError(f"special file is forbidden in task tree: {relative}")
        inode = (info.st_dev, info.st_ino)
        if info.st_nlink > 1 or inode in seen_inodes:
            raise AdmissionError(f"hardlinked file is forbidden in task tree: {relative}")
        seen_inodes.add(inode)
        digest.update(
            f"F\0{relative}\0{stat.S_IMODE(info.st_mode):o}\0{info.st_size}\0".encode()
        )
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def verify_task_tree(task: AiderTask, tree_root: str | Path) -> None:
    """Verify immutable tree and starter-file identities before prompting/grading."""

    root = Path(tree_root).resolve(strict=True)
    actual_tree = tree_sha256(root)
    if actual_tree != task.tree_digest:
        raise AdmissionError("task tree digest is stale or mismatched")
    for editable in task.editable_files:
        path = _contained_path(root, editable.path)
        if not path.is_file() or path.is_symlink():
            raise AdmissionError(f"editable file is missing or unsafe: {editable.path}")
        if file_sha256(path) != editable.starter_sha256:
            raise AdmissionError(f"starter file digest mismatch: {editable.path}")
    for suite_name, suite in (("visible", task.visible_tests), ("hidden", task.hidden_tests)):
        for identity in suite.files:
            path = _contained_path(root, identity.path)
            if not path.is_file() or path.is_symlink():
                raise AdmissionError(f"{suite_name} test file is missing or unsafe: {identity.path}")
            if file_sha256(path) != identity.sha256:
                raise AdmissionError(f"{suite_name} test file digest mismatch: {identity.path}")
    for mutant in task.mutants:
        for identity in mutant.files:
            path = _contained_path(root, identity.source_path)
            if not path.is_file() or path.is_symlink():
                raise AdmissionError(f"mutant source file is missing or unsafe: {identity.source_path}")
            if file_sha256(path) != identity.sha256:
                raise AdmissionError(f"mutant source file digest mismatch: {identity.source_path}")
    if task.compute_digest() != task.task_digest:
        raise AdmissionError("task record has no valid immutable digest")


def load_starter_files(task: AiderTask, tree_root: str | Path) -> dict[str, str]:
    verify_task_tree(task, tree_root)
    root = Path(tree_root).resolve(strict=True)
    return {
        editable.path: _contained_path(root, editable.path).read_text(encoding="utf-8")
        for editable in task.editable_files
    }


def load_reference_files(task: AiderTask, tree_root: str | Path) -> dict[str, str]:
    """Load private references from ``.reference/<editable path>``."""

    verify_task_tree(task, tree_root)
    root = Path(tree_root).resolve(strict=True)
    files: dict[str, str] = {}
    for editable in task.editable_files:
        reference = _contained_path(root, editable.reference_path)
        if not reference.is_file() or reference.is_symlink():
            raise AdmissionError(f"private reference is missing: {editable.path}")
        files[editable.path] = reference.read_text(encoding="utf-8")
    return files


def verify_prompt_boundary(task: AiderTask, tree_root: str | Path) -> str:
    """Render the prompt and prove it contains no private-tree file content."""

    root = Path(tree_root).resolve(strict=True)
    prompt = build_prompt(task, load_starter_files(task, root))
    private_markers = {
        ".reference",
        "CMakeLists.txt",
        "oracle_receipt",
        "hidden_tests",
        "visible_tests",
    }
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if not any(part in PRIVATE_COMPONENTS or part.startswith("test") for part in relative.parts):
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").strip()
        if len(content) >= 24 and content in prompt:
            raise AdmissionError(f"private file content leaked into prompt: {relative.as_posix()}")
    if any(marker in prompt for marker in private_markers):
        raise AdmissionError("private metadata marker leaked into prompt")
    if canonical_sha256(prompt) != task.prompt_fingerprint:
        raise AdmissionError("prompt fingerprint is stale")
    return prompt


def verify_token_evidence(task: AiderTask, prompt: str, reference_files: Mapping[str, str]) -> None:
    answer = render_whole_edit(task, reference_files)
    evidence = task.token_evidence
    if canonical_sha256(prompt) != evidence.prompt_hash:
        raise AdmissionError("token evidence prompt hash is stale")
    if canonical_sha256(answer) != evidence.answer_hash:
        raise AdmissionError("token evidence reference-answer hash is stale")


def reference_fingerprint(task: AiderTask, tree_root: str | Path) -> str:
    """Fingerprint the exact ordered private reference files used by the oracle."""

    root = Path(tree_root).resolve(strict=True)
    identities = []
    for editable in task.editable_files:
        reference = _contained_path(root, editable.reference_path)
        if not reference.is_file() or reference.is_symlink():
            raise AdmissionError(f"private reference is missing: {editable.path}")
        identities.append((editable.path, file_sha256(reference)))
    return canonical_sha256(identities)


def tokenizer_fingerprint(tokenizer: object) -> str:
    """Return a stable fingerprint of a loaded fast-tokenizer backend."""

    backend = getattr(tokenizer, "backend_tokenizer", None)
    if backend is None or not hasattr(backend, "to_str"):
        raise AdmissionError("token admission requires a fast tokenizer backend")
    return hashlib.sha256(backend.to_str().encode("utf-8")).hexdigest()


def measure_token_evidence(
    prompt: str,
    answer: str,
    tokenizer: object,
    *,
    response_budget_margin: int,
) -> TokenEvidence:
    """Measure the immutable one-shot RL token contract with the exact tokenizer."""

    chat_template = getattr(tokenizer, "chat_template", None)
    if not isinstance(chat_template, str) or not chat_template:
        raise AdmissionError("tokenizer has no chat template")
    try:
        prompt_ids = list(
            tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=True,
                add_generation_prompt=True,
            )
        )
        answer_ids = list(tokenizer.encode(answer, add_special_tokens=False))
    except Exception as exc:
        raise AdmissionError(f"tokenizer could not measure admission evidence: {exc}") from exc
    return TokenEvidence(
        tokenizer_fingerprint=tokenizer_fingerprint(tokenizer),
        chat_template_fingerprint=canonical_sha256(chat_template),
        prompt_tokens=len(prompt_ids),
        answer_tokens=len(answer_ids),
        loss_mask_tokens=len(answer_ids),
        total_tokens=len(prompt_ids) + len(answer_ids),
        prompt_hash=canonical_sha256(prompt),
        answer_hash=canonical_sha256(answer),
        prompt_token_ids_hash=canonical_sha256(prompt_ids),
        answer_token_ids_hash=canonical_sha256(answer_ids),
        response_budget=len(answer_ids) + response_budget_margin,
    )


def verify_measured_token_evidence(
    task: AiderTask,
    prompt: str,
    reference_files: Mapping[str, str],
    tokenizer: object,
) -> None:
    """Re-tokenize the exact RL prompt/reference pair and reject stale evidence."""

    verify_token_evidence(task, prompt, reference_files)
    evidence = task.token_evidence
    chat_template = getattr(tokenizer, "chat_template", None)
    if not isinstance(chat_template, str) or not chat_template:
        raise AdmissionError("tokenizer has no chat template")
    if tokenizer_fingerprint(tokenizer) != evidence.tokenizer_fingerprint:
        raise AdmissionError("tokenizer fingerprint differs from admission evidence")
    if canonical_sha256(chat_template) != evidence.chat_template_fingerprint:
        raise AdmissionError("chat-template fingerprint differs from admission evidence")
    try:
        prompt_ids = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=True,
            add_generation_prompt=True,
        )
        answer = render_whole_edit(task, reference_files)
        answer_ids = tokenizer.encode(answer, add_special_tokens=False)
    except Exception as exc:
        raise AdmissionError(f"tokenizer could not reproduce admission evidence: {exc}") from exc
    prompt_ids = list(prompt_ids)
    answer_ids = list(answer_ids)
    if len(prompt_ids) != evidence.prompt_tokens:
        raise AdmissionError("measured prompt token count is stale")
    if len(answer_ids) != evidence.answer_tokens:
        raise AdmissionError("measured answer token count is stale")
    if evidence.loss_mask_tokens != len(answer_ids):
        raise AdmissionError("one-shot assistant loss-mask count must equal answer tokens")
    if evidence.total_tokens != len(prompt_ids) + len(answer_ids):
        raise AdmissionError("measured total token count is stale")
    if canonical_sha256(prompt_ids) != evidence.prompt_token_ids_hash:
        raise AdmissionError("prompt token IDs differ from admission evidence")
    if canonical_sha256(answer_ids) != evidence.answer_token_ids_hash:
        raise AdmissionError("answer token IDs differ from admission evidence")


def verify_split_integrity(tasks: Iterable[AiderTask]) -> None:
    """Require complete families and lineages to stay in a single split."""

    family_splits: dict[str, str] = {}
    lineage_splits: dict[str, str] = {}
    ids: set[str] = set()
    for task in tasks:
        if task.task_id in ids:
            raise AdmissionError(f"duplicate task_id: {task.task_id}")
        ids.add(task.task_id)
        for key, mapping in ((task.family_id, family_splits), (task.lineage_id, lineage_splits)):
            previous = mapping.setdefault(key, task.split)
            if previous != task.split:
                raise AdmissionError(f"family or semantic lineage crosses splits: {key}")


def safe_copy_tree(source: str | Path, destination: str | Path) -> Path:
    """Copy a verified regular-file tree without following links."""

    src = Path(source).resolve(strict=True)
    tree_sha256(src)
    dst = Path(destination)
    if dst.exists():
        raise FileExistsError(dst)
    shutil.copytree(src, dst, symlinks=False, copy_function=shutil.copy2)
    if tree_sha256(src) != tree_sha256(dst):
        raise AdmissionError("copied task tree does not match its source")
    return dst


def source_manifest_fingerprint(path: str | Path) -> str:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return canonical_sha256(payload)


def _contained_path(root: Path, relative: str) -> Path:
    if PurePosixPath(relative).is_absolute():
        raise AdmissionError("absolute task paths are forbidden")
    candidate = root.joinpath(*PurePosixPath(relative).parts).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AdmissionError("task path escapes immutable root") from exc
    return candidate
