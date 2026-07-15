"""Thin kwargs-aware raw-message adapter for pinned SLIME SFT."""

from __future__ import annotations

import json
from typing import Any

from .config import MASK_ADAPTER
from .errors import AiderSftError
from .tokenization import KwargsTokenizerProxy

_TOKENIZER: Any = None
_MASK_GENERATOR: Any = None
_CACHE_KEY: tuple[str, str, str] | None = None
_SAMPLE_PRINTED = False


def _normalize_kwargs(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AiderSftError(
                "consumer_template_policy_mismatch", "invalid template kwargs JSON"
            ) from exc
    if value != {"enable_thinking": False}:
        raise AiderSftError(
            "consumer_template_policy_mismatch",
            "rollout requires exactly enable_thinking=false",
        )
    return value


def validate_slime_args(args: Any) -> dict[str, Any]:
    if getattr(args, "apply_chat_template", False):
        raise AiderSftError(
            "consumer_raw_messages_required",
            "dataset-loader --apply-chat-template is forbidden",
        )
    if getattr(args, "loss_mask_type", None) != "qwen":
        raise AiderSftError("consumer_loss_mask_mismatch", "loss-mask type must be qwen")
    kwargs = _normalize_kwargs(getattr(args, "apply_chat_template_kwargs", None))
    if getattr(args, "input_key", "messages") != "messages":
        raise AiderSftError("consumer_raw_messages_required", "input key must be messages")
    if getattr(args, "metadata_key", "metadata") != "metadata":
        raise AiderSftError("consumer_raw_messages_required", "metadata key must be metadata")
    if getattr(args, "seq_length", None) != 4096:
        raise AiderSftError(
            "consumer_sequence_length_mismatch", "sequence length must match the 4096 lock"
        )
    if getattr(args, "loss_type", None) != "sft_loss":
        raise AiderSftError("consumer_adapter_mismatch", "loss type must be sft_loss")
    rollout_function = getattr(args, "rollout_function_path", None)
    if rollout_function not in {
        None,
        "w8_biayn.aider_sft.handoff.generate_sft_rollout",
        "w8_biayn.aider_sft.handoff.generate_rollout",
    }:
        raise AiderSftError("consumer_adapter_mismatch", "rollout adapter identity differs")
    return kwargs


def generate_sft_rollout(args: Any, rollout_id: int, data_buffer: Any, evaluation: bool = False):
    """Populate SLIME Sample objects without changing trainer behavior."""

    del rollout_id
    if evaluation:
        raise AiderSftError("consumer_raw_messages_required", "SFT adapter is train-only")
    if not getattr(args, "rollout_global_dataset", False):
        raise AiderSftError("consumer_raw_messages_required", "global raw-message dataset required")
    kwargs = validate_slime_args(args)

    global _TOKENIZER, _MASK_GENERATOR, _CACHE_KEY, _SAMPLE_PRINTED
    key = (
        str(args.hf_checkpoint),
        json.dumps(kwargs, sort_keys=True, separators=(",", ":")),
        str(args.loss_mask_type),
    )
    if _CACHE_KEY != key:
        try:
            from slime.utils.mask_utils import MultiTurnLossMaskGenerator
            from slime.utils.processing_utils import load_tokenizer
        except ImportError as exc:
            raise AiderSftError(
                "consumer_adapter_mismatch", "pinned SLIME is not importable"
            ) from exc
        raw_tokenizer = load_tokenizer(args.hf_checkpoint, trust_remote_code=True)
        _TOKENIZER = KwargsTokenizerProxy(raw_tokenizer, kwargs)
        _MASK_GENERATOR = MultiTurnLossMaskGenerator(_TOKENIZER, tokenizer_type=args.loss_mask_type)
        _CACHE_KEY = key
        _SAMPLE_PRINTED = False

    samples = data_buffer.get_samples(args.rollout_batch_size)
    for wrapped in samples:
        (sample,) = wrapped
        messages = sample.prompt
        if not isinstance(messages, list):
            raise AiderSftError(
                "consumer_raw_messages_required", "Sample.prompt must be raw messages"
            )
        token_ids, full_mask = _MASK_GENERATOR.get_loss_mask(
            messages, tools=sample.metadata.get("tools")
        )
        if len(token_ids) != len(full_mask) or 1 not in full_mask:
            raise AiderSftError("consumer_loss_mask_mismatch", "invalid SFT token/mask evidence")
        if len(token_ids) > int(args.seq_length):
            raise AiderSftError("consumer_sequence_length_mismatch", "row exceeds sequence limit")
        response_length = _MASK_GENERATOR.get_response_lengths([full_mask])[0]
        sample.tokens = token_ids
        sample.response_length = response_length
        sample.reward = 0
        sample.loss_mask = full_mask[-response_length:]
        if not _SAMPLE_PRINTED:
            import logging

            logging.getLogger(__name__).info(
                "aider_sft rollout adapter=%s task_id=%s tokens=%d response_length=%d",
                MASK_ADAPTER,
                sample.metadata.get("task_id"),
                len(token_ids),
                response_length,
            )
            _SAMPLE_PRINTED = True
    return samples


generate_rollout = generate_sft_rollout
