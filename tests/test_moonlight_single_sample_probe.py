from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request

from w8_biayn.integrations import moonlight_single_sample_probe as probe


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_probe_saves_prompt_response_and_summary(tmp_path: Path) -> None:
    requests: list[Request] = []

    def opener(request: Request, timeout: int) -> FakeResponse:
        assert timeout == 120
        requests.append(request)
        if request.full_url.endswith("/v1/models"):
            return FakeResponse({"data": [{"id": "sft-export"}]})
        assert request.full_url.endswith("/v1/chat/completions")
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "two_fer.h\n```\n#pragma once\n```\n\ntwo_fer.cpp\n```\n#include \"two_fer.h\"\n```"
                        }
                    }
                ],
                "usage": {"completion_tokens": 12},
            }
        )

    out = probe.run_probe(
        base_url="http://127.0.0.1:30000",
        model="auto",
        out=tmp_path / "probe",
        max_tokens=128,
        temperature=0,
        top_p=1,
        api_key=None,
        opener=opener,
    )

    assert len(requests) == 2
    assert out == tmp_path / "probe"
    assert (out / "response.txt").read_text(encoding="utf-8").startswith("two_fer.h\n```")
    prompt = json.loads((out / "prompt.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    raw_response = json.loads((out / "response.json").read_text(encoding="utf-8"))

    assert prompt["model"] == "sft-export"
    assert prompt["request"]["messages"][0]["content"] == probe.HELDOUT_PROMPT
    assert raw_response["usage"]["completion_tokens"] == 12
    assert summary["whole_format"]["fence_count"] == 4
    assert summary["whole_format"]["missing_filename_before_fence"] == 0
    assert summary["whole_format"]["filename_lines"] == ["two_fer.h", "two_fer.cpp"]


def test_whole_format_summary_flags_missing_filenames() -> None:
    summary = probe.summarize_whole_format("Some prose\n```cpp\nint main() {}\n```")

    assert summary["fence_count"] == 2
    assert summary["missing_filename_before_fence"] == 1
    assert summary["has_text_before_first_filename"] is True



def test_probe_wrapper_and_docs_reference_saved_response() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/probe_single_sample_sft_response.sh")
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111
    wrapper_text = wrapper.read_text(encoding="utf-8")
    assert "w8_biayn.integrations.moonlight_single_sample_probe" in wrapper_text
    assert "aider-whole-heldout-two-fer" in wrapper_text

    for path in (
        Path("docs/moonlight_single_sample_sft.md"),
        Path("examples/slime/moonlight_cpp_perf/README.md"),
        Path("README.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "probe_single_sample_sft_response.sh" in text
        assert "response.txt" in text
