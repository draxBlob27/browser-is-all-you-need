from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path("scripts/eval_sglang_lora_cpp_perf.py")


def _load_eval_module():
    spec = importlib.util.spec_from_file_location("eval_sglang_lora_cpp_perf", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_chat_template_kwargs_requires_json_object() -> None:
    module = _load_eval_module()

    assert module.parse_chat_template_kwargs('{"enable_thinking": false}') == {"enable_thinking": False}


def test_generation_summary_counts_length_finish_reason_as_truncated() -> None:
    module = _load_eval_module()
    generations = [
        {
            "response": "x",
            "finish_reason": "length",
            "completion_tokens": 4096,
            "prompt_tokens": 512,
            "truncated": True,
        },
        {
            "response": "ok",
            "finish_reason": "stop",
            "completion_tokens": 128,
            "prompt_tokens": 512,
            "truncated": False,
        },
    ]

    summary = module.summarize_generations(generations, max_tokens=4096)

    assert summary["truncated_count"] == 1
    assert summary["truncated_ratio"] == 0.5
    assert summary["finish_reason_counts"] == {"length": 1, "stop": 1}
    assert summary["mean_completion_tokens"] == 2112.0


def test_eval_gates_raise_on_bad_truncation_or_format() -> None:
    module = _load_eval_module()

    args = SimpleNamespace(max_truncated_ratio=0.02, min_valid_format_rate=0.5)
    try:
        module.enforce_eval_gates(args, {"truncated_ratio": 1.0, "valid_format_rate": 1.0})
    except SystemExit as exc:
        assert "truncated_ratio" in str(exc)
    else:
        raise AssertionError("expected truncation gate failure")

    args = SimpleNamespace(max_truncated_ratio=1.0, min_valid_format_rate=0.5)
    try:
        module.enforce_eval_gates(args, {"truncated_ratio": 0.0, "valid_format_rate": 0.0})
    except SystemExit as exc:
        assert "valid_format_rate" in str(exc)
    else:
        raise AssertionError("expected valid-format gate failure")


def test_sglang_server_arg_filter_maps_cuda_graph_batch_alias() -> None:
    module = _load_eval_module()

    filtered = module._filter_sglang_server_args(
        {
            "model_path": "model",
            "trust_remote_code": True,
            "cuda_graph_max_bs": 1,
            "unsupported_future_arg": "drop-me",
        },
        {
            "model_path",
            "trust_remote_code",
            "cuda_graph_max_bs_decode",
            "cuda_graph_max_bs_prefill",
        },
    )

    assert filtered == {
        "model_path": "model",
        "trust_remote_code": True,
        "cuda_graph_max_bs_decode": 1,
        "cuda_graph_max_bs_prefill": 1,
    }
