"""Canonical tokenizer and assistant-only loss-mask evidence."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import MASK_ADAPTER
from .errors import AiderSftError
from .schema import SftRow, TokenRecord
from .util import canonical_json_bytes, read_json, sha256_bytes


class KwargsTokenizerProxy:
    """Forward locked template kwargs on every chat-template invocation."""

    def __init__(self, tokenizer: Any, locked_kwargs: dict[str, Any]) -> None:
        self._tokenizer = tokenizer
        self._locked_kwargs = dict(locked_kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._tokenizer, name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._tokenizer(*args, **kwargs)

    def apply_chat_template(self, *args: Any, **kwargs: Any) -> Any:
        for key, expected in self._locked_kwargs.items():
            if key in kwargs and kwargs[key] != expected:
                raise AiderSftError(
                    "chat_template_policy_mismatch",
                    f"chat-template kwarg {key} conflicts with the lock",
                )
            kwargs[key] = expected
        return self._tokenizer.apply_chat_template(*args, **kwargs)


def _pinned_slime_checkout() -> tuple[Path, str]:
    from w8_biayn.constants import SLIME_PIN, UPSTREAMS
    from w8_biayn.upstreams import upstream_path

    configured = os.environ.get("SLIME_ROOT", "").strip()
    repo_root = Path(__file__).resolve().parents[3]
    checkout = (
        Path(configured).expanduser()
        if configured
        else upstream_path(UPSTREAMS["slime"], repo_root)
    ).resolve()
    mask_utils = checkout / "slime/utils/mask_utils.py"
    if not checkout.is_dir() or not mask_utils.is_file():
        raise AiderSftError(
            "profile_not_frozen",
            "pinned SLIME checkout is missing; run `uv run w8-biayn upstreams clone slime` "
            "or set SLIME_ROOT to the exact pinned checkout",
        )

    def git_output(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(checkout), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AiderSftError(
                "profile_not_frozen",
                f"cannot inspect pinned SLIME checkout at {checkout}: {exc}",
            ) from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
            raise AiderSftError(
                "profile_not_frozen",
                f"cannot inspect pinned SLIME checkout at {checkout}: {detail}",
            )
        return result.stdout.strip()

    head = git_output("rev-parse", "HEAD")
    dirty = git_output("status", "--porcelain", "--untracked-files=all")
    if head != SLIME_PIN or dirty:
        raise AiderSftError(
            "profile_not_frozen",
            f"SLIME must be exactly {SLIME_PIN} with a clean tree: {checkout}",
        )
    return checkout, SLIME_PIN


@lru_cache(maxsize=None)
def _pinned_slime_mask_generator_class(checkout_value: str, pin: str) -> type[Any]:
    checkout = Path(checkout_value)
    module_path = checkout / "slime/utils/mask_utils.py"
    module_name = f"_w8_pinned_slime_mask_utils_{pin[:12]}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise AiderSftError(
            "profile_not_frozen",
            f"cannot load pinned SLIME mask utility: {module_path}",
        )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise AiderSftError(
            "profile_not_frozen",
            f"cannot load pinned SLIME mask utility at {module_path}: {exc}",
        ) from exc
    generator_class = getattr(module, "MultiTurnLossMaskGenerator", None)
    if not isinstance(generator_class, type):
        raise AiderSftError(
            "profile_not_frozen",
            f"pinned SLIME mask utility lacks MultiTurnLossMaskGenerator: {module_path}",
        )
    return generator_class


def _slime_mask_generator(tokenizer: Any, loss_mask_type: str) -> Any:
    checkout, pin = _pinned_slime_checkout()
    MultiTurnLossMaskGenerator = _pinned_slime_mask_generator_class(str(checkout), pin)
    return MultiTurnLossMaskGenerator(tokenizer, tokenizer_type=loss_mask_type)


def _validate_consumer_token_policy(consumer_lock: dict[str, Any]) -> None:
    kwargs = consumer_lock["apply_chat_template_kwargs"]
    if kwargs != {"enable_thinking": False}:
        raise AiderSftError(
            "consumer_template_policy_mismatch", "thinking-disabled kwargs are required"
        )
    if consumer_lock["adapter"] != MASK_ADAPTER:
        raise AiderSftError("consumer_adapter_mismatch", "mask adapter identity differs")
    if consumer_lock["loss_mask_type"] != "qwen":
        raise AiderSftError("consumer_loss_mask_mismatch", "qwen loss mask is required")


def preflight_loss_mask_generator(
    *,
    consumer_lock: dict[str, Any],
    tokenizer: Any,
    mask_generator_factory: Callable[[Any, str], Any] = _slime_mask_generator,
) -> Any:
    """Build the locked SLIME mask generator before any task can be rejected."""

    _validate_consumer_token_policy(consumer_lock)
    proxy = KwargsTokenizerProxy(tokenizer, consumer_lock["apply_chat_template_kwargs"])
    try:
        return mask_generator_factory(proxy, consumer_lock["loss_mask_type"])
    except AiderSftError:
        raise
    except Exception as exc:
        raise AiderSftError(
            "consumer_loss_mask_mismatch",
            f"cannot initialize the pinned SLIME loss-mask generator: {exc}",
        ) from exc


def load_locked_tokenizer(
    consumer_lock: dict[str, Any],
    *,
    local_path: Path | None = None,
) -> Any:
    identity = consumer_lock["tokenizer"]
    configured_value = (
        str(local_path)
        if local_path is not None
        else os.environ.get("W8_AIDER_SFT_TOKENIZER_PATH") or identity.get("local_path", "")
    )
    if not configured_value:
        raise AiderSftError(
            "consumer_tokenizer_mismatch",
            "set W8_AIDER_SFT_TOKENIZER_PATH to the pinned local tokenizer snapshot",
        )
    configured = Path(configured_value)
    marker_path = configured / ".w8-aider-sft-model.json"
    if not marker_path.is_file():
        raise AiderSftError(
            "consumer_model_revision_mismatch",
            f"pinned model identity marker is missing: {marker_path}",
        )
    if read_json(marker_path) != {
        "repository": identity["repository"],
        "revision": identity["revision"],
        "schema_version": "w8-aider-sft-model-snapshot-v1",
    }:
        raise AiderSftError(
            "consumer_model_revision_mismatch", "local model identity marker differs"
        )
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise AiderSftError(
            "consumer_tokenizer_mismatch",
            "transformers is required for token-evidence validation",
        ) from exc
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            str(configured),
            local_files_only=True,
            trust_remote_code=True,
            **identity.get("load_kwargs", {}),
        )
    except Exception as exc:
        raise AiderSftError(
            "consumer_tokenizer_mismatch", f"cannot load local tokenizer: {exc}"
        ) from exc
    template = getattr(tokenizer, "chat_template", None)
    if not isinstance(template, str):
        raise AiderSftError("consumer_tokenizer_mismatch", "tokenizer lacks chat_template")
    if sha256_bytes(template.encode("utf-8")) != identity["chat_template_sha256"]:
        raise AiderSftError("consumer_tokenizer_mismatch", "chat-template hash differs")
    return tokenizer


def compute_token_record(
    row_value: dict[str, Any],
    *,
    consumer_lock: dict[str, Any],
    tokenizer: Any,
    mask_generator_factory: Callable[[Any, str], Any] = _slime_mask_generator,
) -> dict[str, Any]:
    row = SftRow.model_validate(row_value)
    identity = consumer_lock["tokenizer"]
    kwargs = consumer_lock["apply_chat_template_kwargs"]
    generator = preflight_loss_mask_generator(
        consumer_lock=consumer_lock,
        tokenizer=tokenizer,
        mask_generator_factory=mask_generator_factory,
    )
    messages = [message.model_dump(mode="json") for message in row.messages]
    try:
        token_ids, loss_mask = generator.get_loss_mask(messages)
        zero_messages = [dict(message) for message in messages]
        zero_messages[1]["step_loss_mask"] = 0
        zero_ids, zero_mask = generator.get_loss_mask(zero_messages)
    except AiderSftError:
        raise
    except Exception as exc:
        raise AiderSftError(
            "chat_template_policy_mismatch", f"token/mask generation failed: {exc}"
        ) from exc
    if token_ids != zero_ids or any(zero_mask):
        raise AiderSftError(
            "consumer_loss_mask_mismatch",
            "zero-assistant fixture changed tokens or retained trainable user tokens",
        )
    if len(token_ids) != len(loss_mask) or not token_ids:
        raise AiderSftError("consumer_loss_mask_mismatch", "token/mask lengths are invalid")
    if 1 not in loss_mask:
        raise AiderSftError("consumer_loss_mask_mismatch", "assistant loss region is empty")
    first_loss = loss_mask.index(1)
    if any(loss_mask[:first_loss]):
        raise AiderSftError("consumer_loss_mask_mismatch", "user region contributes to loss")
    sequence_length = consumer_lock["sequence_length"]
    if len(token_ids) > sequence_length:
        raise AiderSftError(
            "token_overflow", f"{row.task_id}: {len(token_ids)} > {sequence_length}"
        )
    response_length = len(loss_mask) - first_loss
    response_mask = loss_mask[-response_length:]
    counts = {
        "total": len(token_ids),
        "prompt": first_loss,
        "assistant": len(token_ids) - first_loss,
        "loss_bearing": sum(loss_mask),
    }
    record = {
        "schema_version": "aider-sft-token-record-v1",
        "task_id": row.task_id,
        "row_sha256": sha256_bytes(canonical_json_bytes(row_value)),
        "rendered_token_sha256": sha256_bytes(canonical_json_bytes(token_ids)),
        "loss_mask_sha256": sha256_bytes(canonical_json_bytes(loss_mask)),
        "response_length": response_length,
        "response_loss_mask_sha256": sha256_bytes(canonical_json_bytes(response_mask)),
        "token_counts": counts,
        "adapter": MASK_ADAPTER,
        "template_kwargs_sha256": sha256_bytes(canonical_json_bytes(kwargs)),
        "tokenizer_repository": identity["repository"],
        "tokenizer_revision": identity["revision"],
        "chat_template_sha256": identity["chat_template_sha256"],
        "sequence_length": sequence_length,
    }
    TokenRecord.model_validate(record)
    return record


def attach_token_record(row: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    if row["task_id"] != record["task_id"]:
        raise AiderSftError("consumer_loss_mask_mismatch", "row/token task IDs differ")
    updated = {**row, "metadata": dict(row["metadata"])}
    updated["metadata"].update(
        {
            "rendered_token_sha256": record["rendered_token_sha256"],
            "loss_mask_sha256": record["loss_mask_sha256"],
            "response_length": record["response_length"],
            "response_loss_mask_sha256": record["response_loss_mask_sha256"],
            "token_counts": record["token_counts"],
        }
    )
    record["row_sha256"] = sha256_bytes(canonical_json_bytes(updated))
    SftRow.model_validate(updated)
    return updated


def consumer_lock_from_config_lock(config_lock: dict[str, Any]) -> dict[str, Any]:
    tokenizer = config_lock["config"]["tokenizer"]
    return {
        "schema_version": "aider-sft-consumer-lock-v1",
        "model": {
            "repository": tokenizer["repository"],
            "revision": tokenizer["revision"],
        },
        "tokenizer": {
            "repository": tokenizer["repository"],
            "revision": tokenizer["revision"],
            "chat_template_sha256": tokenizer["chat_template_sha256"],
            "load_kwargs": tokenizer["load_kwargs"],
            "local_path": "",
        },
        "apply_chat_template_kwargs": tokenizer["apply_chat_template_kwargs"],
        "template_policy": tokenizer["policy"],
        "adapter": tokenizer["mask_adapter"],
        "loss_mask_type": tokenizer["loss_mask_type"],
        "sequence_length": tokenizer["sequence_length"],
        "message_mode": "raw_messages",
        "dataset_apply_chat_template": False,
        "rollout_function": "w8_biayn.aider_sft.handoff.generate_sft_rollout",
        "input_key": "messages",
        "metadata_key": "metadata",
        "loss_type": "sft_loss",
    }
