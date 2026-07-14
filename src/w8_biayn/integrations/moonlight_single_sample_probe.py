"""Probe a Moonlight single-sample SFT export and persist the model response."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:30000"
DEFAULT_MODEL = "auto"
DEFAULT_PROMPT_ID = "aider-whole-heldout-two-fer"
HELDOUT_PROMPT = (
    "Use whole edit format. Modify the supplied files `two_fer.cpp` and "
    "`two_fer.h` to implement a two-fer response helper. Return only complete "
    "file listings. Each fenced block must be preceded by its filename."
)


def default_output_dir(run_id: str | None = None) -> Path:
    resolved_run_id = run_id or os.environ.get("SLIME_RUN_ID") or "moonlight-aider-whole-single-sft"
    return (
        Path(".w8-biayn")
        / "slime"
        / "moonlight-cpp-perf"
        / "runs"
        / resolved_run_id
        / "probes"
        / DEFAULT_PROMPT_ID
    )


def normalize_base_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[:-3]
    return base


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=body, headers=headers, method=method)
    with opener(request, timeout=120) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def resolve_model(
    base_url: str,
    model: str,
    *,
    api_key: str | None = None,
    opener: Callable[..., Any] = urlopen,
) -> str:
    if model != "auto":
        return model
    response = _request_json(f"{normalize_base_url(base_url)}/v1/models", api_key=api_key, opener=opener)
    models = response.get("data")
    if not isinstance(models, list) or not models:
        raise RuntimeError("SGLang /v1/models response did not include any models")
    first = models[0]
    if not isinstance(first, dict) or not first.get("id"):
        raise RuntimeError("SGLang /v1/models response has no usable model id")
    return str(first["id"])


def build_request(
    *,
    model: str,
    prompt: str = HELDOUT_PROMPT,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    top_p: float = 1.0,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }


def extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(first.get("text"), str):
        return first["text"]
    return ""


def summarize_whole_format(content: str) -> dict[str, Any]:
    lines = content.splitlines()
    fence_indices = [i for i, line in enumerate(lines) if line.strip().startswith("```")]
    opening_indices = fence_indices[::2]
    filename_lines = []
    missing_filename_before_fence = 0
    for index in opening_indices:
        previous = lines[index - 1].strip() if index > 0 else ""
        filename_lines.append(previous)
        if not previous or previous.startswith("```") or " " in previous:
            missing_filename_before_fence += 1
    prefix_lines = [line.strip() for line in lines[: opening_indices[0]] if line.strip()] if opening_indices else []
    return {
        "character_count": len(content),
        "line_count": len(lines),
        "fence_count": len(fence_indices),
        "complete_fence_pairs": len(fence_indices) // 2,
        "unclosed_fence": len(fence_indices) % 2 == 1,
        "filename_lines": filename_lines,
        "missing_filename_before_fence": missing_filename_before_fence,
        "has_text_before_first_filename": bool(
            opening_indices and (len(prefix_lines) != 1 or missing_filename_before_fence)
        ),
    }


def write_probe_artifacts(
    *,
    out: Path,
    base_url: str,
    model: str,
    request_payload: dict[str, Any],
    response: dict[str, Any],
    content: str,
    api_key_present: bool,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    prompt_record = {
        "created_at": timestamp,
        "prompt_id": DEFAULT_PROMPT_ID,
        "base_url": normalize_base_url(base_url),
        "model": model,
        "api_key_present": api_key_present,
        "request": request_payload,
    }
    summary = {
        "created_at": timestamp,
        "prompt_id": DEFAULT_PROMPT_ID,
        "base_url": normalize_base_url(base_url),
        "model": model,
        "api_key_present": api_key_present,
        "content_path": "response.txt",
        "raw_response_path": "response.json",
        "whole_format": summarize_whole_format(content),
    }
    (out / "prompt.json").write_text(json.dumps(prompt_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "response.json").write_text(json.dumps(response, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "response.txt").write_text(content, encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_probe(
    *,
    base_url: str,
    model: str,
    out: Path,
    max_tokens: int,
    temperature: float,
    top_p: float,
    api_key: str | None,
    opener: Callable[..., Any] = urlopen,
) -> Path:
    resolved_model = resolve_model(base_url, model, api_key=api_key, opener=opener)
    request_payload = build_request(
        model=resolved_model,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )
    response = _request_json(
        f"{normalize_base_url(base_url)}/v1/chat/completions",
        method="POST",
        payload=request_payload,
        api_key=api_key,
        opener=opener,
    )
    content = extract_content(response)
    write_probe_artifacts(
        out=out,
        base_url=base_url,
        model=resolved_model,
        request_payload=request_payload,
        response=response,
        content=content,
        api_key_present=bool(api_key),
    )
    return out


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a held-out Aider whole-format prompt and save the model response."
    )
    parser.add_argument("--base-url", default=os.environ.get("SLIME_PROBE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("SLIME_PROBE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--run-id", default=os.environ.get("SLIME_RUN_ID"))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("SLIME_PROBE_MAX_TOKENS", "1024")))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("SLIME_PROBE_TEMPERATURE", "0")))
    parser.add_argument("--top-p", type=float, default=float(os.environ.get("SLIME_PROBE_TOP_P", "1")))
    parser.add_argument("--api-key-env", default="SGLANG_API_KEY")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    out = args.out or default_output_dir(args.run_id)
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    try:
        path = run_probe(
            base_url=args.base_url,
            model=args.model,
            out=out,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            api_key=api_key,
        )
    except URLError as exc:
        raise SystemExit(
            f"Could not reach {normalize_base_url(args.base_url)}. Start the SGLang/OpenAI-compatible "
            "server for the exported SFT checkpoint first."
        ) from exc
    print(f"Saved probe artifacts under {path}")
    print(f"response_text={path / 'response.txt'}")
    print(f"summary={path / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
