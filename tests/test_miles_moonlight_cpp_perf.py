from __future__ import annotations

import os
import subprocess
from pathlib import Path


EXAMPLE_ROOT = Path("examples/miles")
SFT_RUNNER = EXAMPLE_ROOT / "moonlight_cpp_perf_lora_r16_sft.sh"
GRPO_RUNNER = EXAMPLE_ROOT / "moonlight_cpp_perf_lora_r16_grpo.sh"


def test_miles_moonlight_lora_r16_scripts_are_present_and_executable() -> None:
    for script in (SFT_RUNNER, GRPO_RUNNER):
        assert script.exists(), script
        assert os.access(script, os.X_OK), script


def test_miles_moonlight_lora_r16_scripts_are_bash_syntax_valid() -> None:
    for script in (SFT_RUNNER, GRPO_RUNNER):
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_miles_grpo_defaults_match_2048_follow_up_profile() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")

    assert 'SEQ_LENGTH="${MILES_SEQ_LENGTH:-2048}"' in text
    assert 'ROLLOUT_MAX_RESPONSE_LEN="${MILES_ROLLOUT_MAX_RESPONSE_LEN:-1024}"' in text
    assert 'EVAL_MAX_RESPONSE_LEN="${MILES_EVAL_MAX_RESPONSE_LEN:-1536}"' in text
    assert "seq_length=${SEQ_LENGTH}" in text
    assert "rollout_max_response_len=${ROLLOUT_MAX_RESPONSE_LEN}" in text
    assert "eval_max_response_len=${EVAL_MAX_RESPONSE_LEN}" in text
    assert "run_receipt.txt" in text


def test_miles_sft_defaults_share_the_2048_sequence_profile() -> None:
    text = SFT_RUNNER.read_text(encoding="utf-8")

    assert 'SEQ_LENGTH="${MILES_SEQ_LENGTH:-2048}"' in text
    assert "seq_length=${SEQ_LENGTH}" in text
    assert "run_receipt.txt" in text
