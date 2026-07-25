"""Create and verify the fixed-26 diamond clean-room analog batch.

The generated roots are local Aider-format candidates only.  This owner never
creates JSONL, token/mask evidence, exports, training runs, or benchmark-uplift
claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b009-diamond.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b009-diamond"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_diamond_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_diamond_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b009-diamond"
FAMILY_ID = "aider-fixed26-diamond-analogs-v1"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
SANITY_IMAGE_ID = "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
EXPECTED_ROOTS = 50
EXPECTED_PAIRS = 1225
HARD_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
DIMENSION_LIMITS = {
    "public_api": 0.999,
    "owned_state_or_algorithm": 0.999,
    "mutation_or_selection_rules": 0.999,
    "invalid_and_boundary_behavior": 0.999,
    "reference_control_flow": 0.999,
    "deterministic_oracle": 0.999,
    "topic_specific_negative_fixture": 0.999,
}
CONTROL_NAMES = (
    "domain-identifier-renamed",
    "constants-or-policy-only",
    "opposite-end-selection",
)
PRIVATE_MARKERS = (
    ".meta/",
    "example.cpp",
    "negative.cpp",
    "private_test",
    "CMakeLists.txt",
    "provenance.json",
    ".state/",
)
PROJECT_SUPPORT_IDS = frozenset(
    {
        "f26dia-anvil-forge-hourglass",
        "f26dia-market-stall-mound",
        "f26dia-sawmill-blade-teeth",
        "f26dia-depot-window-grille",
        "f26dia-hangar-bay-portal",
        "f26dia-net-loft-mesh",
        "f26dia-signal-kite-streamers",
        "f26dia-tent-pole-canopy-plan",
        "f26dia-zeppelin-mast-survey",
        "f26dia-compass-rose-needles",
    }
)


class FamilyError(RuntimeError):
    """Stable fail-closed family error."""


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    namespace: str
    api: str
    declarations: str
    implementation: str
    starter: str
    negative: str
    visible_test: str
    private_test: str
    mechanism: str
    forbidden: str
    hidden_plan: str
    improvement_reason: str
    api_shape: str
    project_support: bool = False

    @property
    def snake(self) -> str:
        return self.task_id.replace("-", "_")


def _fail(code: str, detail: str = "") -> None:
    raise FamilyError(f"{code}:{detail}" if detail else code)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha256(path.read_bytes())


def _write(path: Path, content: str, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        _fail("refuse_overwrite", str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: object, *, overwrite: bool = False) -> None:
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n", overwrite=overwrite)


def _clean(text: str) -> str:
    text = text.strip("\n")
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    indent = min((len(line) - len(line.lstrip())) for line in lines if line.strip()) if lines else 0
    return "\n".join(line[indent:] for line in lines) + "\n"


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        if "build" in path.parts:
            continue
        rel = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _safe_relative(path: str) -> bool:
    candidate = Path(path)
    return bool(path) and not candidate.is_absolute() and ".." not in candidate.parts


COMMON_HEADER = """#pragma once
#include <cstddef>
#include <stdexcept>
#include <string>
#include <vector>
"""


COMMON_SOURCE = r"""
#include <algorithm>
#include <cctype>
"""


def _case(
    task_id: str,
    title: str,
    namespace: str,
    api: str,
    declarations: str,
    implementation: str,
    negative: str,
    visible_test: str,
    private_test: str,
    mechanism: str,
    forbidden: str,
    hidden_plan: str,
    improvement_reason: str,
    api_shape: str,
    *,
    project_support: bool = False,
) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        title=title,
        namespace=namespace,
        api=_clean(api),
        declarations=_clean(declarations),
        implementation=_clean(implementation),
        starter=_clean(negative),
        negative=_clean(negative),
        visible_test=_clean(visible_test),
        private_test=_clean(private_test),
        mechanism=mechanism,
        forbidden=forbidden,
        hidden_plan=hidden_plan,
        improvement_reason=improvement_reason,
        api_shape=api_shape,
        project_support=project_support,
    )



def cases() -> tuple[TaskSpec, ...]:
    c = _case
    rows = (
        c(
            "f26dia-anvil-forge-hourglass",
            "Anvil forge hourglass",
            "anvil_forge",
            """
            class ForgeError : public std::invalid_argument {
            public:
                explicit ForgeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HourglassOutline {
            public:
                HourglassOutline(std::size_t half, char mark);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class ForgeError : public std::invalid_argument {
            public:
                explicit ForgeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HourglassOutline {
            public:
                HourglassOutline(std::size_t half, char mark);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t half_;
                char mark_;
            };
            """,
            """
            HourglassOutline::HourglassOutline(std::size_t half, char mark) : half_(half), mark_(mark) {
                if (half == 0 || half > 12) throw ForgeError("half outside 1..12");
                if (mark < 33 || mark > 126) throw ForgeError("mark must be a printable non-space ASCII character");
            }
            std::size_t HourglassOutline::half() const { return half_; }
            std::size_t HourglassOutline::width() const { return 2 * half_ + 1; }
            std::size_t HourglassOutline::height() const { return 2 * half_ + 1; }
            std::vector<std::string> HourglassOutline::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < half_ ? half_ - i : i - half_;
                    std::string row(w, ' ');
                    row[half_ - d] = mark_;
                    row[half_ + d] = mark_;
                    out.push_back(row);
                }
                return out;
            }
            std::string HourglassOutline::line(std::size_t index) const {
                if (index >= height()) throw ForgeError("line index out of range");
                return lines()[index];
            }
            std::string HourglassOutline::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            HourglassOutline::HourglassOutline(std::size_t half, char mark) : half_(half), mark_(mark) {
                if (half == 0 || half > 12) throw ForgeError("half outside 1..12");
                if (mark < 33 || mark > 126) throw ForgeError("mark must be a printable non-space ASCII character");
            }
            std::size_t HourglassOutline::half() const { return half_; }
            std::size_t HourglassOutline::width() const { return 2 * half_ + 1; }
            std::size_t HourglassOutline::height() const { return 2 * half_ + 1; }
            std::vector<std::string> HourglassOutline::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < half_ ? half_ - i : i - half_;
                    std::string row(w, ' ');
                    row[half_ - d] = mark_;
                    out.push_back(row);
                }
                return out;
            }
            std::string HourglassOutline::line(std::size_t index) const {
                if (index >= height()) throw ForgeError("line index out of range");
                return lines()[index];
            }
            std::string HourglassOutline::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            HourglassOutline h(3, '#');
            if (h.half() != 3U) return 1;
            if (h.width() != 7U) return 2;
            if (h.height() != 7U) return 3;
            if (h.lines() != std::vector<std::string>{"#     #", " #   # ", "  # #  ", "   #   ", "  # #  ", " #   # ", "#     #"}) return 4;
            if (h.line(0) != "#     #") return 5;
            if (h.render() != "#     #\\n #   # \\n  # #  \\n   #   \\n  # #  \\n #   # \\n#     #") return 6;
            HourglassOutline one(1, '*');
            if (one.lines() != std::vector<std::string>{"* *", " * ", "* *"}) return 7;
            if (one.render() != "* *\\n * \\n* *") return 8;
            bool threw = false;
            try { one.line(3); } catch (const ForgeError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { HourglassOutline bad(0, '#'); } catch (const ForgeError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { HourglassOutline bad(13, '#'); } catch (const ForgeError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { HourglassOutline bad(2, ' '); } catch (const ForgeError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { HourglassOutline bad(2, '\\n'); } catch (const ForgeError&) { threw = true; }
            if (!threw) return 4;
            HourglassOutline m(2, 'o');
            if (m.width() != 5U) return 5;
            if (m.lines() != std::vector<std::string>{"o   o", " o o ", "  o  ", " o o ", "o   o"}) return 6;
            if (m.render() != "o   o\\n o o \\n  o  \\n o o \\no   o") return 7;
            HourglassOutline maxed(12, '+');
            if (maxed.width() != 25U) return 8;
            if (maxed.height() != 25U) return 9;
            if (maxed.line(12) != std::string(12, ' ') + "+" + std::string(12, ' ')) return 10;
            if (maxed.line(0) != "+" + std::string(23, ' ') + "+") return 11;
            return 0;
            """,
            "unsigned-safe mirrored distance with two-mark outline placement",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and single-edge outlines",
            "half bounds at 0 and 13, space-mark rejection, mirror columns on both halves, tip collapse, and index rejection",
            "mirrored-column discipline and exact interior spaces in a paired .h/.cpp API",
            "mirrored outline renderer",
            project_support=True,
        ),
        c(
            "f26dia-bell-tower-lens",
            "Bell tower lens",
            "bell_tower",
            """
            class LensError : public std::domain_error {
            public:
                explicit LensError(const std::string& message) : std::domain_error(message) {}
            };
            class LensChart {
            public:
                LensChart(std::size_t radius, char fill);
                std::size_t radius() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class LensError : public std::domain_error {
            public:
                explicit LensError(const std::string& message) : std::domain_error(message) {}
            };
            class LensChart {
            public:
                LensChart(std::size_t radius, char fill);
                std::size_t radius() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t radius_;
                char fill_;
            };
            """,
            """
            LensChart::LensChart(std::size_t radius, char fill) : radius_(radius), fill_(fill) {
                if (radius == 0 || radius > 10) throw LensError("radius outside 1..10");
                if (fill < 33 || fill > 126) throw LensError("fill must be a printable non-space ASCII character");
            }
            std::size_t LensChart::radius() const { return radius_; }
            std::size_t LensChart::width() const { return 2 * radius_ + 1; }
            std::size_t LensChart::height() const { return 2 * radius_ + 1; }
            std::vector<std::string> LensChart::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < radius_ ? radius_ - i : i - radius_;
                    const std::size_t run = 2 * (radius_ - d) + 1;
                    std::string row(w, ' ');
                    for (std::size_t c = d; c < d + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string LensChart::line(std::size_t index) const {
                if (index >= height()) throw LensError("line index out of range");
                return lines()[index];
            }
            std::string LensChart::render() const {
                std::string result;
                for (const std::string& row : lines()) {
                    result += row;
                    result += '\\n';
                }
                return result;
            }
            """,
            """
            LensChart::LensChart(std::size_t radius, char fill) : radius_(radius), fill_(fill) {
                if (radius == 0 || radius > 10) throw LensError("radius outside 1..10");
                if (fill < 33 || fill > 126) throw LensError("fill must be a printable non-space ASCII character");
            }
            std::size_t LensChart::radius() const { return radius_; }
            std::size_t LensChart::width() const { return 2 * radius_ + 1; }
            std::size_t LensChart::height() const { return 2 * radius_ + 1; }
            std::vector<std::string> LensChart::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < radius_ ? radius_ - i : i - radius_;
                    const std::size_t run = 2 * d + 1;
                    const std::size_t start = radius_ - d;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string LensChart::line(std::size_t index) const {
                if (index >= height()) throw LensError("line index out of range");
                return lines()[index];
            }
            std::string LensChart::render() const {
                std::string result;
                for (const std::string& row : lines()) {
                    result += row;
                    result += '\\n';
                }
                return result;
            }
            """,
            """
            LensChart lens(2, 'o');
            if (lens.radius() != 2U) return 1;
            if (lens.width() != 5U) return 2;
            if (lens.height() != 5U) return 3;
            if (lens.lines() != std::vector<std::string>{"  o  ", " ooo ", "ooooo", " ooo ", "  o  "}) return 4;
            if (lens.line(2) != "ooooo") return 5;
            if (lens.render() != "  o  \\n ooo \\nooooo\\n ooo \\n  o  \\n") return 6;
            LensChart one(1, 'x');
            if (one.lines() != std::vector<std::string>{" x ", "xxx", " x "}) return 7;
            if (one.render() != " x \\nxxx\\n x \\n") return 8;
            bool threw = false;
            try { one.line(3); } catch (const LensError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { LensChart bad(0, 'o'); } catch (const LensError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { LensChart bad(11, 'o'); } catch (const LensError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { LensChart bad(2, ' '); } catch (const LensError&) { threw = true; }
            if (!threw) return 3;
            LensChart m(3, '+');
            if (m.width() != 7U) return 4;
            if (m.height() != 7U) return 5;
            if (m.lines() != std::vector<std::string>{"   +   ", "  +++  ", " +++++ ", "+++++++", " +++++ ", "  +++  ", "   +   "}) return 6;
            if (m.render() != "   +   \\n  +++  \\n +++++ \\n+++++++\\n +++++ \\n  +++  \\n   +   \\n") return 7;
            LensChart maxed(10, '#');
            if (maxed.width() != 21U) return 8;
            if (maxed.line(0) != std::string(10, ' ') + "#" + std::string(10, ' ')) return 9;
            if (maxed.line(10) != std::string(21, '#')) return 10;
            return 0;
            """,
            "centered solid-run fill derived from mirrored distance",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and inverted run lengths",
            "radius bounds at 0 and 11, run lengths at tip, middle, and edge rows, trailing-newline policy, and index rejection",
            "centered fill lengths as the rejection discriminator with a distinct newline policy",
            "mirrored solid fill renderer",
        ),
        c(
            "f26dia-canvas-kite-frame",
            "Canvas kite frame",
            "canvas_kite",
            """
            class FrameError : public std::invalid_argument {
            public:
                explicit FrameError(const std::string& message) : std::invalid_argument(message) {}
            };
            class KiteFrame {
            public:
                explicit KiteFrame(std::size_t span);
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class FrameError : public std::invalid_argument {
            public:
                explicit FrameError(const std::string& message) : std::invalid_argument(message) {}
            };
            class KiteFrame {
            public:
                explicit KiteFrame(std::size_t span);
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t span_;
            };
            """,
            """
            KiteFrame::KiteFrame(std::size_t span) : span_(span) {
                if (span < 2 || span > 14) throw FrameError("span outside 2..14");
            }
            std::size_t KiteFrame::span() const { return span_; }
            std::size_t KiteFrame::width() const { return 2 * span_ - 1; }
            std::size_t KiteFrame::height() const { return span_; }
            std::vector<std::string> KiteFrame::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(span_);
                for (std::size_t i = 0; i < span_; ++i) {
                    std::string row(w, ' ');
                    if (i == 0) {
                        row[span_ - 1] = '^';
                    } else {
                        row[span_ - 1 - i] = '/';
                        row[span_ - 1 + i] = '\\\\';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string KiteFrame::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            KiteFrame::KiteFrame(std::size_t span) : span_(span) {
                if (span < 2 || span > 14) throw FrameError("span outside 2..14");
            }
            std::size_t KiteFrame::span() const { return span_; }
            std::size_t KiteFrame::width() const { return 2 * span_ - 1; }
            std::size_t KiteFrame::height() const { return span_; }
            std::vector<std::string> KiteFrame::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(span_);
                for (std::size_t i = 0; i < span_; ++i) {
                    std::string row(w, ' ');
                    if (i == 0) {
                        row[span_ - 1] = '^';
                    } else {
                        row[span_ - 1 - i] = '\\\\';
                        row[span_ - 1 + i] = '/';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string KiteFrame::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            KiteFrame kite(3);
            if (kite.span() != 3U) return 1;
            if (kite.width() != 5U) return 2;
            if (kite.height() != 3U) return 3;
            if (kite.lines() != std::vector<std::string>{"  ^  ", " / \\\\ ", "/   \\\\"}) return 4;
            if (kite.render() != "  ^  \\n / \\\\ \\n/   \\\\") return 5;
            KiteFrame two(2);
            if (two.lines() != std::vector<std::string>{" ^ ", "/ \\\\"}) return 6;
            if (two.render() != " ^ \\n/ \\\\") return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { KiteFrame bad(1); } catch (const FrameError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { KiteFrame bad(15); } catch (const FrameError&) { threw = true; }
            if (!threw) return 2;
            KiteFrame m(4);
            if (m.width() != 7U) return 3;
            if (m.height() != 4U) return 4;
            if (m.lines() != std::vector<std::string>{"   ^   ", "  / \\\\  ", " /   \\\\ ", "/     \\\\"}) return 5;
            if (m.render() != "   ^   \\n  / \\\\  \\n /   \\\\ \\n/     \\\\") return 6;
            KiteFrame maxed(14);
            if (maxed.width() != 27U) return 7;
            if (maxed.height() != 14U) return 8;
            if (maxed.lines().front() != std::string(13, ' ') + "^" + std::string(13, ' ')) return 9;
            if (maxed.lines().back() != "/" + std::string(25, ' ') + "\\\\") return 10;
            return 0;
            """,
            "two-character slant outline with a distinct apex rule",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and swapped slant characters",
            "span bounds at 1 and 15, apex collapse, slant column walk on every row, and exact backslash placement",
            "per-side character assignment as the rejection discriminator",
            "two-character outline renderer",
        ),
        c(
            "f26dia-drumhead-bowtie",
            "Drumhead bowtie",
            "drumhead",
            """
            class BowError : public std::domain_error {
            public:
                explicit BowError(const std::string& message) : std::domain_error(message) {}
            };
            class BowtiePlate {
            public:
                BowtiePlate(std::size_t tiers, char fill);
                std::size_t tiers() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class BowError : public std::domain_error {
            public:
                explicit BowError(const std::string& message) : std::domain_error(message) {}
            };
            class BowtiePlate {
            public:
                BowtiePlate(std::size_t tiers, char fill);
                std::size_t tiers() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t tiers_;
                char fill_;
            };
            """,
            """
            BowtiePlate::BowtiePlate(std::size_t tiers, char fill) : tiers_(tiers), fill_(fill) {
                if (tiers == 0 || tiers > 9) throw BowError("tiers outside 1..9");
                if (fill < 33 || fill > 126) throw BowError("fill must be a printable non-space ASCII character");
            }
            std::size_t BowtiePlate::tiers() const { return tiers_; }
            std::size_t BowtiePlate::width() const { return 2 * tiers_ + 1; }
            std::size_t BowtiePlate::height() const { return 2 * tiers_ + 1; }
            std::vector<std::string> BowtiePlate::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < tiers_ ? tiers_ - i : i - tiers_;
                    std::string row(w, ' ');
                    for (std::size_t c = 0; c < w; ++c)
                        if (c <= d || c >= w - 1 - d) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string BowtiePlate::line(std::size_t index) const {
                if (index >= height()) throw BowError("line index out of range");
                return lines()[index];
            }
            std::string BowtiePlate::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BowtiePlate::BowtiePlate(std::size_t tiers, char fill) : tiers_(tiers), fill_(fill) {
                if (tiers == 0 || tiers > 9) throw BowError("tiers outside 1..9");
                if (fill < 33 || fill > 126) throw BowError("fill must be a printable non-space ASCII character");
            }
            std::size_t BowtiePlate::tiers() const { return tiers_; }
            std::size_t BowtiePlate::width() const { return 2 * tiers_ + 1; }
            std::size_t BowtiePlate::height() const { return 2 * tiers_ + 1; }
            std::vector<std::string> BowtiePlate::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < tiers_ ? tiers_ - i : i - tiers_;
                    std::string row(w, ' ');
                    for (std::size_t c = 0; c < w; ++c)
                        if (c >= tiers_ - d && c <= tiers_ + d) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string BowtiePlate::line(std::size_t index) const {
                if (index >= height()) throw BowError("line index out of range");
                return lines()[index];
            }
            std::string BowtiePlate::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BowtiePlate bow(2, '#');
            if (bow.tiers() != 2U) return 1;
            if (bow.width() != 5U) return 2;
            if (bow.height() != 5U) return 3;
            if (bow.lines() != std::vector<std::string>{"#####", "## ##", "#   #", "## ##", "#####"}) return 4;
            if (bow.line(2) != "#   #") return 5;
            if (bow.render() != "#####\\n## ##\\n#   #\\n## ##\\n#####") return 6;
            BowtiePlate one(1, 'o');
            if (one.lines() != std::vector<std::string>{"ooo", "o o", "ooo"}) return 7;
            bool threw = false;
            try { one.line(3); } catch (const BowError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { BowtiePlate bad(0, '#'); } catch (const BowError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BowtiePlate bad(10, '#'); } catch (const BowError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { BowtiePlate bad(2, ' '); } catch (const BowError&) { threw = true; }
            if (!threw) return 3;
            BowtiePlate m(3, '+');
            if (m.width() != 7U) return 4;
            if (m.lines() != std::vector<std::string>{"+++++++", "+++ +++", "++   ++", "+     +", "++   ++", "+++ +++", "+++++++"}) return 5;
            if (m.render() != "+++++++\\n+++ +++\\n++   ++\\n+     +\\n++   ++\\n+++ +++\\n+++++++") return 6;
            BowtiePlate maxed(9, 'o');
            if (maxed.width() != 19U) return 7;
            if (maxed.line(0) != std::string(19, 'o')) return 8;
            if (maxed.line(9) != "o" + std::string(17, ' ') + "o") return 9;
            return 0;
            """,
            "mirrored wing fill pinched at the center row",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and center-filled runs",
            "tier bounds at 0 and 10, wing widths at outer and center rows, and index rejection",
            "wing-versus-center fill as the rejection discriminator",
            "mirrored wing fill renderer",
        ),
        c(
            "f26dia-ember-pit-spindle",
            "Ember pit spindle",
            "ember_pit",
            """
            class SpindleError : public std::invalid_argument {
            public:
                explicit SpindleError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SpindleGauge {
            public:
                SpindleGauge(std::size_t half, char edge, char core);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class SpindleError : public std::invalid_argument {
            public:
                explicit SpindleError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SpindleGauge {
            public:
                SpindleGauge(std::size_t half, char edge, char core);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t half_;
                char edge_;
                char core_;
            };
            """,
            """
            SpindleGauge::SpindleGauge(std::size_t half, char edge, char core) : half_(half), edge_(edge), core_(core) {
                if (half == 0 || half > 11) throw SpindleError("half outside 1..11");
                if (edge < 33 || edge > 126) throw SpindleError("edge must be a printable non-space ASCII character");
                if (core < 33 || core > 126) throw SpindleError("core must be a printable non-space ASCII character");
                if (edge == core) throw SpindleError("edge and core must differ");
            }
            std::size_t SpindleGauge::half() const { return half_; }
            std::size_t SpindleGauge::width() const { return 2 * half_ + 1; }
            std::size_t SpindleGauge::height() const { return 2 * half_ + 1; }
            std::vector<std::string> SpindleGauge::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < half_ ? half_ - i : i - half_;
                    std::string row(w, ' ');
                    row[half_ - d] = edge_;
                    row[half_ + d] = edge_;
                    row[half_] = core_;
                    out.push_back(row);
                }
                return out;
            }
            std::string SpindleGauge::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            SpindleGauge::SpindleGauge(std::size_t half, char edge, char core) : half_(half), edge_(edge), core_(core) {
                if (half == 0 || half > 11) throw SpindleError("half outside 1..11");
                if (edge < 33 || edge > 126) throw SpindleError("edge must be a printable non-space ASCII character");
                if (core < 33 || core > 126) throw SpindleError("core must be a printable non-space ASCII character");
                if (edge == core) throw SpindleError("edge and core must differ");
            }
            std::size_t SpindleGauge::half() const { return half_; }
            std::size_t SpindleGauge::width() const { return 2 * half_ + 1; }
            std::size_t SpindleGauge::height() const { return 2 * half_ + 1; }
            std::vector<std::string> SpindleGauge::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < half_ ? half_ - i : i - half_;
                    std::string row(w, ' ');
                    row[half_ - d] = edge_;
                    row[half_ + d] = edge_;
                    if (d == 0) row[half_] = core_;
                    out.push_back(row);
                }
                return out;
            }
            std::string SpindleGauge::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            SpindleGauge g(2, '*', '|');
            if (g.half() != 2U) return 1;
            if (g.width() != 5U) return 2;
            if (g.height() != 5U) return 3;
            if (g.lines() != std::vector<std::string>{"* | *", " *|* ", "  |  ", " *|* ", "* | *"}) return 4;
            if (g.render() != "* | *\\n *|* \\n  |  \\n *|* \\n* | *") return 5;
            SpindleGauge one(1, '#', 'o');
            if (one.lines() != std::vector<std::string>{"#o#", " o ", "#o#"}) return 6;
            if (one.render() != "#o#\\n o \\n#o#") return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { SpindleGauge bad(0, '*', '|'); } catch (const SpindleError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { SpindleGauge bad(12, '*', '|'); } catch (const SpindleError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { SpindleGauge bad(2, '*', '*'); } catch (const SpindleError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { SpindleGauge bad(2, ' ', '|'); } catch (const SpindleError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { SpindleGauge bad(2, '*', ' '); } catch (const SpindleError&) { threw = true; }
            if (!threw) return 5;
            SpindleGauge m(3, '/', '|');
            if (m.width() != 7U) return 6;
            if (m.lines() != std::vector<std::string>{"/  |  /", " / | / ", "  /|/  ", "   |   ", "  /|/  ", " / | / ", "/  |  /"}) return 7;
            if (m.render() != "/  |  /\\n / | / \\n  /|/  \\n   |   \\n  /|/  \\n / | / \\n/  |  /") return 8;
            return 0;
            """,
            "two-character outline with a persistent center core and declared overlap precedence",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and a missing center core",
            "half bounds, equal-character rejection, core on every row, and overlap precedence at the tip row",
            "two-character precedence as the rejection discriminator",
            "outline-plus-core renderer",
        ),
        c(
            "f26dia-ferry-slip-oval",
            "Ferry slip oval",
            "ferry_slip",
            """
            class OvalError : public std::domain_error {
            public:
                explicit OvalError(const std::string& message) : std::domain_error(message) {}
            };
            class OvalSketch {
            public:
                OvalSketch(std::size_t half, char rim);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class OvalError : public std::domain_error {
            public:
                explicit OvalError(const std::string& message) : std::domain_error(message) {}
            };
            class OvalSketch {
            public:
                OvalSketch(std::size_t half, char rim);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t half_;
                char rim_;
            };
            """,
            """
            OvalSketch::OvalSketch(std::size_t half, char rim) : half_(half), rim_(rim) {
                if (half < 2 || half > 13) throw OvalError("half outside 2..13");
                if (rim < 33 || rim > 126) throw OvalError("rim must be a printable non-space ASCII character");
            }
            std::size_t OvalSketch::half() const { return half_; }
            std::size_t OvalSketch::width() const { return 2 * half_ + 1; }
            std::size_t OvalSketch::height() const { return 2 * half_ + 1; }
            std::vector<std::string> OvalSketch::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < half_ ? half_ - i : i - half_;
                    std::string row(w, ' ');
                    if (d == half_) {
                        row[half_ - 1] = rim_;
                        row[half_] = rim_;
                        row[half_ + 1] = rim_;
                    } else {
                        row[half_ - d] = rim_;
                        row[half_ + d] = rim_;
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string OvalSketch::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            OvalSketch::OvalSketch(std::size_t half, char rim) : half_(half), rim_(rim) {
                if (half < 2 || half > 13) throw OvalError("half outside 2..13");
                if (rim < 33 || rim > 126) throw OvalError("rim must be a printable non-space ASCII character");
            }
            std::size_t OvalSketch::half() const { return half_; }
            std::size_t OvalSketch::width() const { return 2 * half_ + 1; }
            std::size_t OvalSketch::height() const { return 2 * half_ + 1; }
            std::vector<std::string> OvalSketch::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    const std::size_t d = i < half_ ? half_ - i : i - half_;
                    std::string row(w, ' ');
                    row[half_ - d] = rim_;
                    row[half_ + d] = rim_;
                    out.push_back(row);
                }
                return out;
            }
            std::string OvalSketch::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            OvalSketch oval(2, 'O');
            if (oval.half() != 2U) return 1;
            if (oval.width() != 5U) return 2;
            if (oval.height() != 5U) return 3;
            if (oval.lines() != std::vector<std::string>{" OOO ", " O O ", "  O  ", " O O ", " OOO "}) return 4;
            if (oval.render() != " OOO \\n O O \\n  O  \\n O O \\n OOO ") return 5;
            OvalSketch three(3, '#');
            if (three.lines() != std::vector<std::string>{"  ###  ", " #   # ", "  # #  ", "   #   ", "  # #  ", " #   # ", "  ###  "}) return 6;
            if (three.render() != "  ###  \\n #   # \\n  # #  \\n   #   \\n  # #  \\n #   # \\n  ###  ") return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { OvalSketch bad(1, 'O'); } catch (const OvalError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { OvalSketch bad(14, 'O'); } catch (const OvalError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { OvalSketch bad(2, ' '); } catch (const OvalError&) { threw = true; }
            if (!threw) return 3;
            OvalSketch m(2, 'o');
            if (m.width() != 5U) return 4;
            if (m.render() != " ooo \\n o o \\n  o  \\n o o \\n ooo ") return 5;
            OvalSketch maxed(13, '+');
            if (maxed.width() != 27U) return 6;
            if (maxed.height() != 27U) return 7;
            if (maxed.lines().front() != std::string(12, ' ') + "+++" + std::string(12, ' ')) return 8;
            if (maxed.lines()[13] != std::string(13, ' ') + "+" + std::string(13, ' ')) return 9;
            return 0;
            """,
            "bar-tip outline policy over a mirrored distance walk",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and single-point tips",
            "half bounds at 1 and 14, three-cell tip runs on both tip rows, and slant rows between",
            "tip-policy discipline as the rejection discriminator",
            "bar-tip outline renderer",
        ),
        c(
            "f26dia-grain-silo-capsule",
            "Grain silo capsule",
            "grain_silo",
            """
            class SiloError : public std::invalid_argument {
            public:
                explicit SiloError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CapsulePlan {
            public:
                CapsulePlan(std::size_t half, char wall);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class SiloError : public std::invalid_argument {
            public:
                explicit SiloError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CapsulePlan {
            public:
                CapsulePlan(std::size_t half, char wall);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t half_;
                char wall_;
            };
            """,
            """
            CapsulePlan::CapsulePlan(std::size_t half, char wall) : half_(half), wall_(wall) {
                if (half == 0 || half > 12) throw SiloError("half outside 1..12");
                if (wall < 33 || wall > 126) throw SiloError("wall must be a printable non-space ASCII character");
            }
            std::size_t CapsulePlan::half() const { return half_; }
            std::size_t CapsulePlan::width() const { return 2 * half_ + 1; }
            std::size_t CapsulePlan::height() const { return 2 * half_ + 3; }
            std::vector<std::string> CapsulePlan::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    if (i < half_) {
                        row[half_ - 1 - i] = wall_;
                        row[half_ + 1 + i] = wall_;
                    } else if (i <= half_ + 2) {
                        row[0] = wall_;
                        row[w - 1] = wall_;
                    } else {
                        const std::size_t mirror = h - 1 - i;
                        row[half_ - 1 - mirror] = wall_;
                        row[half_ + 1 + mirror] = wall_;
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string CapsulePlan::line(std::size_t index) const {
                if (index >= height()) throw SiloError("line index out of range");
                return lines()[index];
            }
            std::string CapsulePlan::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            CapsulePlan::CapsulePlan(std::size_t half, char wall) : half_(half), wall_(wall) {
                if (half == 0 || half > 12) throw SiloError("half outside 1..12");
                if (wall < 33 || wall > 126) throw SiloError("wall must be a printable non-space ASCII character");
            }
            std::size_t CapsulePlan::half() const { return half_; }
            std::size_t CapsulePlan::width() const { return 2 * half_ + 1; }
            std::size_t CapsulePlan::height() const { return 2 * half_ + 3; }
            std::vector<std::string> CapsulePlan::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    if (i < half_) {
                        row[half_ - 1 - i] = wall_;
                        row[half_ + 1 + i] = wall_;
                    } else if (i <= half_ + 2) {
                        row[1] = wall_;
                        row[w - 2] = wall_;
                    } else {
                        const std::size_t mirror = h - 1 - i;
                        row[half_ - 1 - mirror] = wall_;
                        row[half_ + 1 + mirror] = wall_;
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string CapsulePlan::line(std::size_t index) const {
                if (index >= height()) throw SiloError("line index out of range");
                return lines()[index];
            }
            std::string CapsulePlan::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            CapsulePlan cap(2, '#');
            if (cap.half() != 2U) return 1;
            if (cap.width() != 5U) return 2;
            if (cap.height() != 7U) return 3;
            if (cap.lines() != std::vector<std::string>{" # # ", "#   #", "#   #", "#   #", "#   #", "#   #", " # # "}) return 4;
            if (cap.line(3) != "#   #") return 5;
            if (cap.render() != " # # \\n#   #\\n#   #\\n#   #\\n#   #\\n#   #\\n # # ") return 6;
            CapsulePlan one(1, 'o');
            if (one.lines() != std::vector<std::string>{"o o", "o o", "o o", "o o", "o o"}) return 7;
            bool threw = false;
            try { one.line(5); } catch (const SiloError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { CapsulePlan bad(0, '#'); } catch (const SiloError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { CapsulePlan bad(13, '#'); } catch (const SiloError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { CapsulePlan bad(2, ' '); } catch (const SiloError&) { threw = true; }
            if (!threw) return 3;
            CapsulePlan m(3, '+');
            if (m.width() != 7U) return 4;
            if (m.height() != 9U) return 5;
            if (m.lines() != std::vector<std::string>{"  + +  ", " +   + ", "+     +", "+     +", "+     +", "+     +", "+     +", " +   + ", "  + +  "}) return 6;
            if (m.render() != "  + +  \\n +   + \\n+     +\\n+     +\\n+     +\\n+     +\\n+     +\\n +   + \\n  + +  ") return 7;
            return 0;
            """,
            "taper-wall-taper outline with a straight middle section",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and inset walls",
            "half bounds, taper endpoints at both tips, wall columns on exactly three middle rows, and index rejection",
            "multi-section geometry as the rejection discriminator",
            "taper-wall outline renderer",
        ),
        c(
            "f26dia-harbor-buoy-prism",
            "Harbor buoy prism",
            "harbor_buoy",
            """
            class PrismError : public std::domain_error {
            public:
                explicit PrismError(const std::string& message) : std::domain_error(message) {}
            };
            class PrismFacet {
            public:
                PrismFacet(std::size_t half, char left, char right);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class PrismError : public std::domain_error {
            public:
                explicit PrismError(const std::string& message) : std::domain_error(message) {}
            };
            class PrismFacet {
            public:
                PrismFacet(std::size_t half, char left, char right);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t half_;
                char left_;
                char right_;
            };
            """,
            """
            PrismFacet::PrismFacet(std::size_t half, char left, char right) : half_(half), left_(left), right_(right) {
                if (half == 0 || half > 10) throw PrismError("half outside 1..10");
                if (left < 33 || left > 126) throw PrismError("left must be a printable non-space ASCII character");
                if (right < 33 || right > 126) throw PrismError("right must be a printable non-space ASCII character");
            }
            std::size_t PrismFacet::half() const { return half_; }
            std::size_t PrismFacet::width() const { return 2 * half_ + 1; }
            std::size_t PrismFacet::height() const { return half_ + 1; }
            std::vector<std::string> PrismFacet::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    row[half_ - i] = left_;
                    if (half_ + i != half_ - i) row[half_ + i] = right_;
                    out.push_back(row);
                }
                return out;
            }
            std::string PrismFacet::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PrismFacet::PrismFacet(std::size_t half, char left, char right) : half_(half), left_(left), right_(right) {
                if (half == 0 || half > 10) throw PrismError("half outside 1..10");
                if (left < 33 || left > 126) throw PrismError("left must be a printable non-space ASCII character");
                if (right < 33 || right > 126) throw PrismError("right must be a printable non-space ASCII character");
            }
            std::size_t PrismFacet::half() const { return half_; }
            std::size_t PrismFacet::width() const { return 2 * half_ + 1; }
            std::size_t PrismFacet::height() const { return half_ + 1; }
            std::vector<std::string> PrismFacet::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    row[half_ - i] = right_;
                    row[half_ + i] = right_;
                    out.push_back(row);
                }
                return out;
            }
            std::string PrismFacet::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PrismFacet prism(3, '/', '\\\\');
            if (prism.half() != 3U) return 1;
            if (prism.width() != 7U) return 2;
            if (prism.height() != 4U) return 3;
            if (prism.lines() != std::vector<std::string>{"   /   ", "  / \\\\  ", " /   \\\\ ", "/     \\\\"}) return 4;
            if (prism.render() != "   /   \\n  / \\\\  \\n /   \\\\ \\n/     \\\\") return 5;
            PrismFacet one(1, '(', ')');
            if (one.lines() != std::vector<std::string>{" ( ", "( )"}) return 6;
            if (one.render() != " ( \\n( )") return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { PrismFacet bad(0, '/', '\\\\'); } catch (const PrismError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PrismFacet bad(11, '/', '\\\\'); } catch (const PrismError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PrismFacet bad(2, ' ', '\\\\'); } catch (const PrismError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { PrismFacet bad(2, '/', ' '); } catch (const PrismError&) { threw = true; }
            if (!threw) return 4;
            PrismFacet m(2, '<', '>');
            if (m.width() != 5U) return 5;
            if (m.height() != 3U) return 6;
            if (m.lines() != std::vector<std::string>{"  <  ", " < > ", "<   >"}) return 7;
            if (m.render() != "  <  \\n < > \\n<   >") return 8;
            return 0;
            """,
            "per-side character outline with apex precedence",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and single-character sides",
            "half bounds, side characters on every row, and apex precedence",
            "side-specific characters as the rejection discriminator",
            "two-character facet renderer",
        ),
        c(
            "f26dia-ice-rink-peak",
            "Ice rink peak",
            "ice_rink",
            """
            class PeakError : public std::invalid_argument {
            public:
                explicit PeakError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PeakFill {
            public:
                PeakFill(std::size_t levels, char fill);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class PeakError : public std::invalid_argument {
            public:
                explicit PeakError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PeakFill {
            public:
                PeakFill(std::size_t levels, char fill);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t levels_;
                char fill_;
            };
            """,
            """
            PeakFill::PeakFill(std::size_t levels, char fill) : levels_(levels), fill_(fill) {
                if (levels == 0 || levels > 13) throw PeakError("levels outside 1..13");
                if (fill < 33 || fill > 126) throw PeakError("fill must be a printable non-space ASCII character");
            }
            std::size_t PeakFill::levels() const { return levels_; }
            std::size_t PeakFill::width() const { return 2 * levels_ - 1; }
            std::size_t PeakFill::height() const { return levels_; }
            std::vector<std::string> PeakFill::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * i + 1;
                    const std::size_t start = levels_ - 1 - i;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string PeakFill::line(std::size_t index) const {
                if (index >= height()) throw PeakError("line index out of range");
                return lines()[index];
            }
            std::string PeakFill::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PeakFill::PeakFill(std::size_t levels, char fill) : levels_(levels), fill_(fill) {
                if (levels == 0 || levels > 13) throw PeakError("levels outside 1..13");
                if (fill < 33 || fill > 126) throw PeakError("fill must be a printable non-space ASCII character");
            }
            std::size_t PeakFill::levels() const { return levels_; }
            std::size_t PeakFill::width() const { return 2 * levels_ - 1; }
            std::size_t PeakFill::height() const { return levels_; }
            std::vector<std::string> PeakFill::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * i + 1;
                    std::string row(w, ' ');
                    for (std::size_t c = 0; c < run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string PeakFill::line(std::size_t index) const {
                if (index >= height()) throw PeakError("line index out of range");
                return lines()[index];
            }
            std::string PeakFill::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PeakFill peak(3, '*');
            if (peak.levels() != 3U) return 1;
            if (peak.width() != 5U) return 2;
            if (peak.height() != 3U) return 3;
            if (peak.lines() != std::vector<std::string>{"  *  ", " *** ", "*****"}) return 4;
            if (peak.line(2) != "*****") return 5;
            if (peak.render() != "  *  \\n *** \\n*****") return 6;
            PeakFill one(1, 'o');
            if (one.lines() != std::vector<std::string>{"o"}) return 7;
            bool threw = false;
            try { one.line(1); } catch (const PeakError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { PeakFill bad(0, '*'); } catch (const PeakError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PeakFill bad(14, '*'); } catch (const PeakError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PeakFill bad(2, ' '); } catch (const PeakError&) { threw = true; }
            if (!threw) return 3;
            PeakFill m(4, '+');
            if (m.width() != 7U) return 4;
            if (m.lines() != std::vector<std::string>{"   +   ", "  +++  ", " +++++ ", "+++++++"}) return 5;
            if (m.render() != "   +   \\n  +++  \\n +++++ \\n+++++++") return 6;
            PeakFill maxed(13, '#');
            if (maxed.width() != 25U) return 7;
            if (maxed.line(0) != std::string(12, ' ') + "#" + std::string(12, ' ')) return 8;
            if (maxed.line(12) != std::string(25, '#')) return 9;
            return 0;
            """,
            "centered growing solid runs with exact leading spaces",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and uncentered runs",
            "level bounds at 0 and 14, run growth by two, leading-space exactness, and index rejection",
            "center alignment as the rejection discriminator",
            "centered peak fill renderer",
        ),
        c(
            "f26dia-jewel-bench-pyramid",
            "Jewel bench pyramid",
            "jewel_bench",
            """
            class GemError : public std::domain_error {
            public:
                explicit GemError(const std::string& message) : std::domain_error(message) {}
            };
            class GemPyramid {
            public:
                GemPyramid(std::size_t levels, char face, char seam);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class GemError : public std::domain_error {
            public:
                explicit GemError(const std::string& message) : std::domain_error(message) {}
            };
            class GemPyramid {
            public:
                GemPyramid(std::size_t levels, char face, char seam);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t levels_;
                char face_;
                char seam_;
            };
            """,
            """
            GemPyramid::GemPyramid(std::size_t levels, char face, char seam) : levels_(levels), face_(face), seam_(seam) {
                if (levels == 0 || levels > 12) throw GemError("levels outside 1..12");
                if (face < 33 || face > 126) throw GemError("face must be a printable non-space ASCII character");
                if (seam < 33 || seam > 126) throw GemError("seam must be a printable non-space ASCII character");
                if (face == seam) throw GemError("face and seam must differ");
            }
            std::size_t GemPyramid::levels() const { return levels_; }
            std::size_t GemPyramid::width() const { return 2 * levels_ - 1; }
            std::size_t GemPyramid::height() const { return levels_; }
            std::vector<std::string> GemPyramid::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * i + 1;
                    const std::size_t start = levels_ - 1 - i;
                    std::string row(w, ' ');
                    for (std::size_t j = 0; j < run; ++j) row[start + j] = j % 2 == 0 ? face_ : seam_;
                    out.push_back(row);
                }
                return out;
            }
            std::string GemPyramid::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            GemPyramid::GemPyramid(std::size_t levels, char face, char seam) : levels_(levels), face_(face), seam_(seam) {
                if (levels == 0 || levels > 12) throw GemError("levels outside 1..12");
                if (face < 33 || face > 126) throw GemError("face must be a printable non-space ASCII character");
                if (seam < 33 || seam > 126) throw GemError("seam must be a printable non-space ASCII character");
                if (face == seam) throw GemError("face and seam must differ");
            }
            std::size_t GemPyramid::levels() const { return levels_; }
            std::size_t GemPyramid::width() const { return 2 * levels_ - 1; }
            std::size_t GemPyramid::height() const { return levels_; }
            std::vector<std::string> GemPyramid::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * i + 1;
                    const std::size_t start = levels_ - 1 - i;
                    std::string row(w, ' ');
                    for (std::size_t j = 0; j < run; ++j) row[start + j] = j % 2 == 0 ? seam_ : face_;
                    out.push_back(row);
                }
                return out;
            }
            std::string GemPyramid::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            GemPyramid gem(3, 'o', '+');
            if (gem.levels() != 3U) return 1;
            if (gem.width() != 5U) return 2;
            if (gem.height() != 3U) return 3;
            if (gem.lines() != std::vector<std::string>{"  o  ", " o+o ", "o+o+o"}) return 4;
            if (gem.render() != "  o  \\n o+o \\no+o+o") return 5;
            GemPyramid two(2, '#', '.');
            if (two.lines() != std::vector<std::string>{" # ", "#.#"}) return 6;
            if (two.render() != " # \\n#.#") return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { GemPyramid bad(0, 'o', '+'); } catch (const GemError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { GemPyramid bad(13, 'o', '+'); } catch (const GemError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { GemPyramid bad(2, 'o', 'o'); } catch (const GemError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { GemPyramid bad(2, 'o', ' '); } catch (const GemError&) { threw = true; }
            if (!threw) return 4;
            GemPyramid m(4, '*', '-');
            if (m.width() != 7U) return 5;
            if (m.lines() != std::vector<std::string>{"   *   ", "  *-*  ", " *-*-* ", "*-*-*-*"}) return 6;
            if (m.render() != "   *   \\n  *-*  \\n *-*-* \\n*-*-*-*") return 7;
            return 0;
            """,
            "alternating two-character centered runs with a face-first phase",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and seam-first alternation",
            "level bounds, equal-character rejection, and alternation phase on every row",
            "alternation phase as the rejection discriminator",
            "alternating centered fill renderer",
        ),
        c(
            "f26dia-kite-festival-stack",
            "Kite festival stack",
            "kite_festival",
            """
            class StackError : public std::invalid_argument {
            public:
                explicit StackError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TierStack {
            public:
                explicit TierStack(std::size_t levels);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class StackError : public std::invalid_argument {
            public:
                explicit StackError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TierStack {
            public:
                explicit TierStack(std::size_t levels);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t levels_;
            };
            """,
            """
            TierStack::TierStack(std::size_t levels) : levels_(levels) {
                if (levels < 2 || levels > 14) throw StackError("levels outside 2..14");
            }
            std::size_t TierStack::levels() const { return levels_; }
            std::size_t TierStack::width() const { return 2 * levels_ - 1; }
            std::size_t TierStack::height() const { return levels_; }
            std::vector<std::string> TierStack::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * i + 1;
                    const std::size_t start = levels_ - 1 - i;
                    const char mark = i % 2 == 0 ? '*' : '#';
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = mark;
                    out.push_back(row);
                }
                return out;
            }
            std::string TierStack::render() const {
                std::string result;
                for (const std::string& row : lines()) {
                    result += row;
                    result += '\\n';
                }
                return result;
            }
            """,
            """
            TierStack::TierStack(std::size_t levels) : levels_(levels) {
                if (levels < 2 || levels > 14) throw StackError("levels outside 2..14");
            }
            std::size_t TierStack::levels() const { return levels_; }
            std::size_t TierStack::width() const { return 2 * levels_ - 1; }
            std::size_t TierStack::height() const { return levels_; }
            std::vector<std::string> TierStack::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * i + 1;
                    const std::size_t start = levels_ - 1 - i;
                    const char mark = i % 2 == 0 ? '#' : '*';
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = mark;
                    out.push_back(row);
                }
                return out;
            }
            std::string TierStack::render() const {
                std::string result;
                for (const std::string& row : lines()) {
                    result += row;
                    result += '\\n';
                }
                return result;
            }
            """,
            """
            TierStack stack(3);
            if (stack.levels() != 3U) return 1;
            if (stack.width() != 5U) return 2;
            if (stack.height() != 3U) return 3;
            if (stack.lines() != std::vector<std::string>{"  *  ", " ### ", "*****"}) return 4;
            if (stack.render() != "  *  \\n ### \\n*****\\n") return 5;
            TierStack two(2);
            if (two.lines() != std::vector<std::string>{" * ", "###"}) return 6;
            if (two.render() != " * \\n###\\n") return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { TierStack bad(1); } catch (const StackError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { TierStack bad(15); } catch (const StackError&) { threw = true; }
            if (!threw) return 2;
            TierStack m(4);
            if (m.width() != 7U) return 3;
            if (m.lines() != std::vector<std::string>{"   *   ", "  ###  ", " ***** ", "#######"}) return 4;
            if (m.render() != "   *   \\n  ###  \\n ***** \\n#######\\n") return 5;
            TierStack maxed(14);
            if (maxed.width() != 27U) return 6;
            if (maxed.lines().front() != std::string(13, ' ') + "*" + std::string(13, ' ')) return 7;
            if (maxed.lines().back() != std::string(27, '#')) return 8;
            return 0;
            """,
            "row-parity centered runs with fixed characters",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and inverted row parity",
            "level bounds at 1 and 15, parity character per row, and trailing-newline policy",
            "row-parity policy as the rejection discriminator",
            "row-parity centered fill renderer",
        ),
        c(
            "f26dia-loom-yard-gable",
            "Loom yard gable",
            "loom_yard",
            """
            class GableError : public std::domain_error {
            public:
                explicit GableError(const std::string& message) : std::domain_error(message) {}
            };
            class GableRoof {
            public:
                GableRoof(std::size_t levels, char fill);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class GableError : public std::domain_error {
            public:
                explicit GableError(const std::string& message) : std::domain_error(message) {}
            };
            class GableRoof {
            public:
                GableRoof(std::size_t levels, char fill);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t levels_;
                char fill_;
            };
            """,
            """
            GableRoof::GableRoof(std::size_t levels, char fill) : levels_(levels), fill_(fill) {
                if (levels == 0 || levels > 12) throw GableError("levels outside 1..12");
                if (fill < 33 || fill > 126) throw GableError("fill must be a printable non-space ASCII character");
            }
            std::size_t GableRoof::levels() const { return levels_; }
            std::size_t GableRoof::width() const { return 2 * levels_ - 1; }
            std::size_t GableRoof::height() const { return levels_; }
            std::vector<std::string> GableRoof::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * (levels_ - i) - 1;
                    std::string row(w, ' ');
                    for (std::size_t c = i; c < i + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string GableRoof::line(std::size_t index) const {
                if (index >= height()) throw GableError("line index out of range");
                return lines()[index];
            }
            std::string GableRoof::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            GableRoof::GableRoof(std::size_t levels, char fill) : levels_(levels), fill_(fill) {
                if (levels == 0 || levels > 12) throw GableError("levels outside 1..12");
                if (fill < 33 || fill > 126) throw GableError("fill must be a printable non-space ASCII character");
            }
            std::size_t GableRoof::levels() const { return levels_; }
            std::size_t GableRoof::width() const { return 2 * levels_ - 1; }
            std::size_t GableRoof::height() const { return levels_; }
            std::vector<std::string> GableRoof::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * (levels_ - i) - 1;
                    const std::size_t start = w - run;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < w; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string GableRoof::line(std::size_t index) const {
                if (index >= height()) throw GableError("line index out of range");
                return lines()[index];
            }
            std::string GableRoof::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            GableRoof roof(3, '=');
            if (roof.levels() != 3U) return 1;
            if (roof.width() != 5U) return 2;
            if (roof.height() != 3U) return 3;
            if (roof.lines() != std::vector<std::string>{"=====", " === ", "  =  "}) return 4;
            if (roof.line(0) != "=====") return 5;
            if (roof.render() != "=====\\n === \\n  =  ") return 6;
            GableRoof one(1, '#');
            if (one.lines() != std::vector<std::string>{"#"}) return 7;
            bool threw = false;
            try { one.line(1); } catch (const GableError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { GableRoof bad(0, '='); } catch (const GableError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { GableRoof bad(13, '='); } catch (const GableError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { GableRoof bad(2, ' '); } catch (const GableError&) { threw = true; }
            if (!threw) return 3;
            GableRoof m(4, 'o');
            if (m.width() != 7U) return 4;
            if (m.lines() != std::vector<std::string>{"ooooooo", " ooooo ", "  ooo  ", "   o   "}) return 5;
            if (m.render() != "ooooooo\\n ooooo \\n  ooo  \\n   o   ") return 6;
            GableRoof maxed(12, '+');
            if (maxed.width() != 23U) return 7;
            if (maxed.line(0) != std::string(23, '+')) return 8;
            if (maxed.line(11) != std::string(11, ' ') + "+" + std::string(11, ' ')) return 9;
            return 0;
            """,
            "centered shrinking solid runs with exact leading spaces",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and right-aligned runs",
            "level bounds, shrinking run lengths, leading-space exactness, and index rejection",
            "shrinking-run alignment as the rejection discriminator",
            "centered shrinking fill renderer",
        ),
        c(
            "f26dia-market-stall-mound",
            "Market stall mound",
            "market_stall",
            """
            class MoundError : public std::invalid_argument {
            public:
                explicit MoundError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StallMound {
            public:
                StallMound(std::size_t levels, char fill);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class MoundError : public std::invalid_argument {
            public:
                explicit MoundError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StallMound {
            public:
                StallMound(std::size_t levels, char fill);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t levels_;
                char fill_;
            };
            """,
            """
            StallMound::StallMound(std::size_t levels, char fill) : levels_(levels), fill_(fill) {
                if (levels == 0 || levels > 11) throw MoundError("levels outside 1..11");
                if (fill < 33 || fill > 126) throw MoundError("fill must be a printable non-space ASCII character");
            }
            std::size_t StallMound::levels() const { return levels_; }
            std::size_t StallMound::width() const { return 2 * levels_ + 1; }
            std::size_t StallMound::height() const { return levels_ + 2; }
            std::vector<std::string> StallMound::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::size_t run = w;
                    if (i < levels_) {
                        run = 2 * i + 3;
                        if (run > w) run = w;
                    }
                    const std::size_t start = (w - run) / 2;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string StallMound::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            StallMound::StallMound(std::size_t levels, char fill) : levels_(levels), fill_(fill) {
                if (levels == 0 || levels > 11) throw MoundError("levels outside 1..11");
                if (fill < 33 || fill > 126) throw MoundError("fill must be a printable non-space ASCII character");
            }
            std::size_t StallMound::levels() const { return levels_; }
            std::size_t StallMound::width() const { return 2 * levels_ + 1; }
            std::size_t StallMound::height() const { return levels_ + 1; }
            std::vector<std::string> StallMound::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::size_t run = w;
                    if (i < levels_) {
                        run = 2 * i + 3;
                        if (run > w) run = w;
                    }
                    const std::size_t start = (w - run) / 2;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string StallMound::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            StallMound mound(2, '#');
            if (mound.levels() != 2U) return 1;
            if (mound.width() != 5U) return 2;
            if (mound.height() != 4U) return 3;
            if (mound.lines() != std::vector<std::string>{" ### ", "#####", "#####", "#####"}) return 4;
            if (mound.render() != " ### \\n#####\\n#####\\n#####") return 5;
            StallMound three(3, 'o');
            if (three.width() != 7U) return 6;
            if (three.lines() != std::vector<std::string>{"  ooo  ", " ooooo ", "ooooooo", "ooooooo", "ooooooo"}) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { StallMound bad(0, '#'); } catch (const MoundError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { StallMound bad(12, '#'); } catch (const MoundError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { StallMound bad(2, ' '); } catch (const MoundError&) { threw = true; }
            if (!threw) return 3;
            StallMound one(1, '+');
            if (one.width() != 3U) return 4;
            if (one.height() != 3U) return 5;
            if (one.lines() != std::vector<std::string>{"+++", "+++", "+++"}) return 6;
            if (one.render() != "+++\\n+++\\n+++") return 7;
            StallMound maxed(11, 'o');
            if (maxed.width() != 23U) return 8;
            if (maxed.height() != 13U) return 9;
            return 0;
            """,
            "capped growing runs plus a two-row full-width base",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and a single-row base",
            "level bounds, cap saturation at full width, and exactly two base rows",
            "base-row policy as the rejection discriminator",
            "capped peak fill renderer",
            project_support=True,
        ),
        c(
            "f26dia-nursery-bed-terrace",
            "Nursery bed terrace",
            "nursery_bed",
            """
            class TerraceError : public std::domain_error {
            public:
                explicit TerraceError(const std::string& message) : std::domain_error(message) {}
            };
            class BedTerrace {
            public:
                BedTerrace(std::size_t levels, char fill, std::size_t step);
                std::size_t levels() const;
                std::size_t step() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class TerraceError : public std::domain_error {
            public:
                explicit TerraceError(const std::string& message) : std::domain_error(message) {}
            };
            class BedTerrace {
            public:
                BedTerrace(std::size_t levels, char fill, std::size_t step);
                std::size_t levels() const;
                std::size_t step() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t levels_;
                char fill_;
                std::size_t step_;
            };
            """,
            """
            BedTerrace::BedTerrace(std::size_t levels, char fill, std::size_t step) : levels_(levels), fill_(fill), step_(step) {
                if (levels < 2 || levels > 9) throw TerraceError("levels outside 2..9");
                if (step == 0 || step > 3) throw TerraceError("step outside 1..3");
                if (fill < 33 || fill > 126) throw TerraceError("fill must be a printable non-space ASCII character");
            }
            std::size_t BedTerrace::levels() const { return levels_; }
            std::size_t BedTerrace::step() const { return step_; }
            std::size_t BedTerrace::width() const { return (levels_ - 1) * step_ + (2 * levels_ - 1); }
            std::size_t BedTerrace::height() const { return levels_; }
            std::vector<std::string> BedTerrace::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * i + 1;
                    const std::size_t start = w - step_ * (levels_ - 1 - i) - run;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string BedTerrace::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BedTerrace::BedTerrace(std::size_t levels, char fill, std::size_t step) : levels_(levels), fill_(fill), step_(step) {
                if (levels < 2 || levels > 9) throw TerraceError("levels outside 2..9");
                if (step == 0 || step > 3) throw TerraceError("step outside 1..3");
                if (fill < 33 || fill > 126) throw TerraceError("fill must be a printable non-space ASCII character");
            }
            std::size_t BedTerrace::levels() const { return levels_; }
            std::size_t BedTerrace::step() const { return step_; }
            std::size_t BedTerrace::width() const { return (levels_ - 1) * step_ + (2 * levels_ - 1); }
            std::size_t BedTerrace::height() const { return levels_; }
            std::vector<std::string> BedTerrace::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = 2 * i + 1;
                    const std::size_t start = step_ * (levels_ - 1 - i);
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string BedTerrace::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BedTerrace bed(3, 't', 1);
            if (bed.levels() != 3U) return 1;
            if (bed.step() != 1U) return 2;
            if (bed.width() != 7U) return 3;
            if (bed.height() != 3U) return 4;
            if (bed.lines() != std::vector<std::string>{"    t  ", "   ttt ", "  ttttt"}) return 5;
            if (bed.render() != "    t  \\n   ttt \\n  ttttt") return 6;
            BedTerrace two(2, '#', 2);
            if (two.width() != 5U) return 7;
            if (two.lines() != std::vector<std::string>{"  #  ", "  ###"}) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { BedTerrace bad(1, 't', 1); } catch (const TerraceError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BedTerrace bad(10, 't', 1); } catch (const TerraceError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { BedTerrace bad(2, 't', 0); } catch (const TerraceError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { BedTerrace bad(2, 't', 4); } catch (const TerraceError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { BedTerrace bad(2, ' ', 1); } catch (const TerraceError&) { threw = true; }
            if (!threw) return 5;
            BedTerrace m(4, 'o', 1);
            if (m.width() != 10U) return 6;
            if (m.lines() != std::vector<std::string>{"      o   ", "     ooo  ", "    ooooo ", "   ooooooo"}) return 7;
            if (m.render() != "      o   \\n     ooo  \\n    ooooo \\n   ooooooo") return 8;
            return 0;
            """,
            "stepped terrace alignment with an exact right-edge walk",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and left-side steps",
            "level and step bounds, right-edge column walk, and leading-space exactness",
            "stepped alignment as the rejection discriminator",
            "stepped terrace fill renderer",
        ),
        c(
            "f26dia-observatory-dome-steps",
            "Observatory dome steps",
            "observatory",
            """
            class DomeError : public std::invalid_argument {
            public:
                explicit DomeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DomeSteps {
            public:
                DomeSteps(std::size_t levels, char fill);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class DomeError : public std::invalid_argument {
            public:
                explicit DomeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DomeSteps {
            public:
                DomeSteps(std::size_t levels, char fill);
                std::size_t levels() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t levels_;
                char fill_;
            };
            """,
            """
            DomeSteps::DomeSteps(std::size_t levels, char fill) : levels_(levels), fill_(fill) {
                if (levels < 2 || levels > 12) throw DomeError("levels outside 2..12");
                if (fill < 33 || fill > 126) throw DomeError("fill must be a printable non-space ASCII character");
            }
            std::size_t DomeSteps::levels() const { return levels_; }
            std::size_t DomeSteps::width() const { return 2 * levels_ + 1; }
            std::size_t DomeSteps::height() const { return levels_; }
            std::vector<std::string> DomeSteps::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = std::min(2 * i + 3, w);
                    const std::size_t start = (w - run) / 2;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string DomeSteps::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            DomeSteps::DomeSteps(std::size_t levels, char fill) : levels_(levels), fill_(fill) {
                if (levels < 2 || levels > 12) throw DomeError("levels outside 2..12");
                if (fill < 33 || fill > 126) throw DomeError("fill must be a printable non-space ASCII character");
            }
            std::size_t DomeSteps::levels() const { return levels_; }
            std::size_t DomeSteps::width() const { return 2 * levels_ + 1; }
            std::size_t DomeSteps::height() const { return levels_; }
            std::vector<std::string> DomeSteps::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(levels_);
                for (std::size_t i = 0; i < levels_; ++i) {
                    const std::size_t run = std::min(2 * i + 1, w);
                    const std::size_t start = (w - run) / 2;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string DomeSteps::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            DomeSteps dome(3, 'd');
            if (dome.levels() != 3U) return 1;
            if (dome.width() != 7U) return 2;
            if (dome.height() != 3U) return 3;
            if (dome.lines() != std::vector<std::string>{"  ddd  ", " ddddd ", "ddddddd"}) return 4;
            if (dome.render() != "  ddd  \\n ddddd \\nddddddd") return 5;
            DomeSteps two(2, '#');
            if (two.lines() != std::vector<std::string>{" ### ", "#####"}) return 6;
            if (two.render() != " ### \\n#####") return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { DomeSteps bad(1, 'd'); } catch (const DomeError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { DomeSteps bad(13, 'd'); } catch (const DomeError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { DomeSteps bad(2, ' '); } catch (const DomeError&) { threw = true; }
            if (!threw) return 3;
            DomeSteps m(4, 'o');
            if (m.width() != 9U) return 4;
            if (m.lines() != std::vector<std::string>{"   ooo   ", "  ooooo  ", " ooooooo ", "ooooooooo"}) return 5;
            if (m.render() != "   ooo   \\n  ooooo  \\n ooooooo \\nooooooooo") return 6;
            DomeSteps maxed(12, '+');
            if (maxed.width() != 25U) return 7;
            if (maxed.lines().back() != std::string(25, '+')) return 8;
            return 0;
            """,
            "saturating centered runs starting above one cell",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and single-cell starts",
            "level bounds at 1 and 13, initial run of three, and saturation at the width",
            "saturation policy as the rejection discriminator",
            "saturating centered fill renderer",
        ),
        c(
            "f26dia-pier-plank-chevron",
            "Pier plank chevron",
            "pier_plank",
            """
            class ChevronError : public std::invalid_argument {
            public:
                explicit ChevronError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ChevronRun {
            public:
                ChevronRun(std::size_t rows, std::size_t span);
                std::size_t rows() const;
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class ChevronError : public std::invalid_argument {
            public:
                explicit ChevronError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ChevronRun {
            public:
                ChevronRun(std::size_t rows, std::size_t span);
                std::size_t rows() const;
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t span_;
            };
            """,
            """
            static std::size_t chevron_bounce(std::size_t row, std::size_t span) {
                const std::size_t period = 2 * (span - 1);
                const std::size_t p = row % period;
                return p < span ? p : period - p;
            }
            ChevronRun::ChevronRun(std::size_t rows, std::size_t span) : rows_(rows), span_(span) {
                if (rows == 0 || rows > 12) throw ChevronError("rows outside 1..12");
                if (span < 2 || span > 9) throw ChevronError("span outside 2..9");
            }
            std::size_t ChevronRun::rows() const { return rows_; }
            std::size_t ChevronRun::span() const { return span_; }
            std::size_t ChevronRun::width() const { return span_; }
            std::size_t ChevronRun::height() const { return rows_; }
            std::vector<std::string> ChevronRun::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t period = 2 * (span_ - 1);
                    const std::size_t p = r % period;
                    const bool moving_right = p < span_;
                    const std::size_t col = chevron_bounce(r, span_);
                    std::string row(span_, ' ');
                    row[col] = moving_right ? '\\\\' : '/';
                    out.push_back(row);
                }
                return out;
            }
            std::string ChevronRun::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            static std::size_t chevron_bounce(std::size_t row, std::size_t span) {
                const std::size_t period = 2 * (span - 1);
                const std::size_t p = row % period;
                return p < span ? p : period - p;
            }
            ChevronRun::ChevronRun(std::size_t rows, std::size_t span) : rows_(rows), span_(span) {
                if (rows == 0 || rows > 12) throw ChevronError("rows outside 1..12");
                if (span < 2 || span > 9) throw ChevronError("span outside 2..9");
            }
            std::size_t ChevronRun::rows() const { return rows_; }
            std::size_t ChevronRun::span() const { return span_; }
            std::size_t ChevronRun::width() const { return span_; }
            std::size_t ChevronRun::height() const { return rows_; }
            std::vector<std::string> ChevronRun::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t col = chevron_bounce(r, span_);
                    std::string row(span_, ' ');
                    row[col] = '\\\\';
                    out.push_back(row);
                }
                return out;
            }
            std::string ChevronRun::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            ChevronRun run(4, 3);
            if (run.rows() != 4U) return 1;
            if (run.span() != 3U) return 2;
            if (run.width() != 3U) return 3;
            if (run.height() != 4U) return 4;
            if (run.lines() != std::vector<std::string>{"\\\\  ", " \\\\ ", "  \\\\", " / "}) return 5;
            if (run.render() != "\\\\  \\n \\\\ \\n  \\\\\\n / ") return 6;
            ChevronRun two(2, 2);
            if (two.lines() != std::vector<std::string>{"\\\\ ", " \\\\"}) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { ChevronRun bad(0, 3); } catch (const ChevronError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ChevronRun bad(13, 3); } catch (const ChevronError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { ChevronRun bad(2, 1); } catch (const ChevronError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { ChevronRun bad(2, 10); } catch (const ChevronError&) { threw = true; }
            if (!threw) return 4;
            ChevronRun m(6, 4);
            if (m.width() != 4U) return 5;
            if (m.lines() != std::vector<std::string>{"\\\\   ", " \\\\  ", "  \\\\ ", "   \\\\", "  / ", " /  "}) return 6;
            if (m.render() != "\\\\   \\n \\\\  \\n  \\\\ \\n   \\\\\\n  / \\n /  ") return 7;
            return 0;
            """,
            "triangle-wave bounce with direction-selected characters",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and single-direction characters",
            "row and span bounds, bounce endpoints, and direction character per phase",
            "direction-selected characters as the rejection discriminator",
            "bouncing slant mark renderer",
        ),
        c(
            "f26dia-quarry-ramp-zigzag",
            "Quarry ramp zigzag",
            "quarry_ramp",
            """
            class RampError : public std::domain_error {
            public:
                explicit RampError(const std::string& message) : std::domain_error(message) {}
            };
            class RampZigzag {
            public:
                RampZigzag(std::size_t rows, std::size_t width, char fill);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class RampError : public std::domain_error {
            public:
                explicit RampError(const std::string& message) : std::domain_error(message) {}
            };
            class RampZigzag {
            public:
                RampZigzag(std::size_t rows, std::size_t width, char fill);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                char fill_;
            };
            """,
            """
            RampZigzag::RampZigzag(std::size_t rows, std::size_t width, char fill) : rows_(rows), width_(width), fill_(fill) {
                if (rows == 0 || rows > 15) throw RampError("rows outside 1..15");
                if (width < 3 || width > 12) throw RampError("width outside 3..12");
                if (fill < 33 || fill > 126) throw RampError("fill must be a printable non-space ASCII character");
            }
            std::size_t RampZigzag::rows() const { return rows_; }
            std::size_t RampZigzag::width() const { return width_; }
            std::size_t RampZigzag::height() const { return rows_; }
            std::vector<std::string> RampZigzag::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t period = 2 * (width_ - 1);
                    const std::size_t p = r % period;
                    const std::size_t col = p < width_ ? p : period - p;
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c <= col; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string RampZigzag::line(std::size_t index) const {
                if (index >= height()) throw RampError("line index out of range");
                return lines()[index];
            }
            std::string RampZigzag::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            RampZigzag::RampZigzag(std::size_t rows, std::size_t width, char fill) : rows_(rows), width_(width), fill_(fill) {
                if (rows == 0 || rows > 15) throw RampError("rows outside 1..15");
                if (width < 3 || width > 12) throw RampError("width outside 3..12");
                if (fill < 33 || fill > 126) throw RampError("fill must be a printable non-space ASCII character");
            }
            std::size_t RampZigzag::rows() const { return rows_; }
            std::size_t RampZigzag::width() const { return width_; }
            std::size_t RampZigzag::height() const { return rows_; }
            std::vector<std::string> RampZigzag::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t period = 2 * (width_ - 1);
                    const std::size_t p = r % period;
                    const std::size_t col = p < width_ ? p : period - p;
                    std::string row(width_, ' ');
                    for (std::size_t c = width_ - 1 - col; c < width_; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string RampZigzag::line(std::size_t index) const {
                if (index >= height()) throw RampError("line index out of range");
                return lines()[index];
            }
            std::string RampZigzag::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            RampZigzag ramp(4, 3, 'r');
            if (ramp.rows() != 4U) return 1;
            if (ramp.width() != 3U) return 2;
            if (ramp.height() != 4U) return 3;
            if (ramp.lines() != std::vector<std::string>{"r  ", "rr ", "rrr", "rr "}) return 4;
            if (ramp.line(2) != "rrr") return 5;
            if (ramp.render() != "r  \\nrr \\nrrr\\nrr ") return 6;
            bool threw = false;
            try { ramp.line(4); } catch (const RampError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { RampZigzag bad(0, 3, 'r'); } catch (const RampError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RampZigzag bad(16, 3, 'r'); } catch (const RampError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { RampZigzag bad(2, 2, 'r'); } catch (const RampError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { RampZigzag bad(2, 13, 'r'); } catch (const RampError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { RampZigzag bad(2, 3, ' '); } catch (const RampError&) { threw = true; }
            if (!threw) return 5;
            RampZigzag m(5, 4, 'o');
            if (m.width() != 4U) return 6;
            if (m.lines() != std::vector<std::string>{"o   ", "oo  ", "ooo ", "oooo", "ooo "}) return 7;
            if (m.render() != "o   \\noo  \\nooo \\noooo\\nooo ") return 8;
            return 0;
            """,
            "bounce-length left fills over a triangle wave",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and right-aligned fills",
            "row and width bounds, fill length at bounce endpoints, and index rejection",
            "bounce fill alignment as the rejection discriminator",
            "bouncing left-fill renderer",
        ),
        c(
            "f26dia-river-weir-notch",
            "River weir notch",
            "river_weir",
            """
            class WeirError : public std::invalid_argument {
            public:
                explicit WeirError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WeirNotch {
            public:
                WeirNotch(std::size_t rows, std::size_t span);
                std::size_t rows() const;
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class WeirError : public std::invalid_argument {
            public:
                explicit WeirError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WeirNotch {
            public:
                WeirNotch(std::size_t rows, std::size_t span);
                std::size_t rows() const;
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t span_;
            };
            """,
            """
            WeirNotch::WeirNotch(std::size_t rows, std::size_t span) : rows_(rows), span_(span) {
                if (rows == 0 || rows > 12) throw WeirError("rows outside 1..12");
                if (span < 2 || span > 10) throw WeirError("span outside 2..10");
            }
            std::size_t WeirNotch::rows() const { return rows_; }
            std::size_t WeirNotch::span() const { return span_; }
            std::size_t WeirNotch::width() const { return 2 * span_ - 1; }
            std::size_t WeirNotch::height() const { return rows_; }
            std::vector<std::string> WeirNotch::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t period = 2 * (span_ - 1);
                    const std::size_t raw = r % period;
                    const std::size_t p = raw < span_ ? raw : period - raw;
                    std::string row(w, ' ');
                    row[span_ - 1 - p] = 'v';
                    row[span_ - 1 + p] = 'v';
                    out.push_back(row);
                }
                return out;
            }
            std::string WeirNotch::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            WeirNotch::WeirNotch(std::size_t rows, std::size_t span) : rows_(rows), span_(span) {
                if (rows == 0 || rows > 12) throw WeirError("rows outside 1..12");
                if (span < 2 || span > 10) throw WeirError("span outside 2..10");
            }
            std::size_t WeirNotch::rows() const { return rows_; }
            std::size_t WeirNotch::span() const { return span_; }
            std::size_t WeirNotch::width() const { return 2 * span_ - 1; }
            std::size_t WeirNotch::height() const { return rows_; }
            std::vector<std::string> WeirNotch::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t p = r % span_;
                    std::string row(w, ' ');
                    row[span_ - 1 - p] = 'v';
                    row[span_ - 1 + p] = 'v';
                    out.push_back(row);
                }
                return out;
            }
            std::string WeirNotch::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            WeirNotch weir(4, 3);
            if (weir.rows() != 4U) return 1;
            if (weir.span() != 3U) return 2;
            if (weir.width() != 5U) return 3;
            if (weir.height() != 4U) return 4;
            if (weir.lines() != std::vector<std::string>{"  v  ", " v v ", "v   v", " v v "}) return 5;
            if (weir.render() != "  v  \\n v v \\nv   v\\n v v ") return 6;
            WeirNotch two(2, 2);
            if (two.lines() != std::vector<std::string>{" v ", "v v"}) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { WeirNotch bad(0, 3); } catch (const WeirError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { WeirNotch bad(13, 3); } catch (const WeirError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { WeirNotch bad(2, 1); } catch (const WeirError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { WeirNotch bad(2, 11); } catch (const WeirError&) { threw = true; }
            if (!threw) return 4;
            WeirNotch m(5, 4);
            if (m.width() != 7U) return 5;
            if (m.lines() != std::vector<std::string>{"   v   ", "  v v  ", " v   v ", "v     v", " v   v "}) return 6;
            if (m.render() != "   v   \\n  v v  \\n v   v \\nv     v\\n v   v ") return 7;
            return 0;
            """,
            "mirrored bounce columns with tip collapse",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and sawtooth phases",
            "row and span bounds, mirror columns per phase, and tip collapse",
            "triangle-versus-sawtooth phase as the rejection discriminator",
            "mirrored bounce notch renderer",
        ),
        c(
            "f26dia-sawmill-blade-teeth",
            "Sawmill blade teeth",
            "sawmill",
            """
            class BladeError : public std::domain_error {
            public:
                explicit BladeError(const std::string& message) : std::domain_error(message) {}
            };
            class BladeTeeth {
            public:
                BladeTeeth(std::size_t rows, std::size_t teeth);
                std::size_t rows() const;
                std::size_t teeth() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class BladeError : public std::domain_error {
            public:
                explicit BladeError(const std::string& message) : std::domain_error(message) {}
            };
            class BladeTeeth {
            public:
                BladeTeeth(std::size_t rows, std::size_t teeth);
                std::size_t rows() const;
                std::size_t teeth() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t teeth_;
            };
            """,
            """
            BladeTeeth::BladeTeeth(std::size_t rows, std::size_t teeth) : rows_(rows), teeth_(teeth) {
                if (rows == 0 || rows > 14) throw BladeError("rows outside 1..14");
                if (teeth < 2 || teeth > 8) throw BladeError("teeth outside 2..8");
            }
            std::size_t BladeTeeth::rows() const { return rows_; }
            std::size_t BladeTeeth::teeth() const { return teeth_; }
            std::size_t BladeTeeth::width() const { return 2 * teeth_; }
            std::size_t BladeTeeth::height() const { return rows_; }
            std::vector<std::string> BladeTeeth::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row;
                    row.reserve(width());
                    for (std::size_t t = 0; t < teeth_; ++t) {
                        if (r % 2 == 0) {
                            row += '/';
                            row += '\\\\';
                        } else {
                            row += '\\\\';
                            row += '/';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string BladeTeeth::render() const {
                std::string result;
                for (const std::string& row : lines()) {
                    result += row;
                    result += '\\n';
                }
                return result;
            }
            """,
            """
            BladeTeeth::BladeTeeth(std::size_t rows, std::size_t teeth) : rows_(rows), teeth_(teeth) {
                if (rows == 0 || rows > 14) throw BladeError("rows outside 1..14");
                if (teeth < 2 || teeth > 8) throw BladeError("teeth outside 2..8");
            }
            std::size_t BladeTeeth::rows() const { return rows_; }
            std::size_t BladeTeeth::teeth() const { return teeth_; }
            std::size_t BladeTeeth::width() const { return 2 * teeth_; }
            std::size_t BladeTeeth::height() const { return rows_; }
            std::vector<std::string> BladeTeeth::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row;
                    row.reserve(width());
                    for (std::size_t t = 0; t < teeth_; ++t) {
                        row += '/';
                        row += '\\\\';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string BladeTeeth::render() const {
                std::string result;
                for (const std::string& row : lines()) {
                    result += row;
                    result += '\\n';
                }
                return result;
            }
            """,
            """
            BladeTeeth blade(3, 2);
            if (blade.rows() != 3U) return 1;
            if (blade.teeth() != 2U) return 2;
            if (blade.width() != 4U) return 3;
            if (blade.height() != 3U) return 4;
            if (blade.lines() != std::vector<std::string>{"/\\\\/\\\\", "\\\\/\\\\/", "/\\\\/\\\\"}) return 5;
            if (blade.render() != "/\\\\/\\\\\\n\\\\/\\\\/\\n/\\\\/\\\\\\n") return 6;
            BladeTeeth one(1, 3);
            if (one.lines() != std::vector<std::string>{"/\\\\/\\\\/\\\\"}) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { BladeTeeth bad(0, 2); } catch (const BladeError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BladeTeeth bad(15, 2); } catch (const BladeError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { BladeTeeth bad(2, 1); } catch (const BladeError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { BladeTeeth bad(2, 9); } catch (const BladeError&) { threw = true; }
            if (!threw) return 4;
            BladeTeeth m(4, 3);
            if (m.width() != 6U) return 5;
            if (m.lines() != std::vector<std::string>{"/\\\\/\\\\/\\\\", "\\\\/\\\\/\\\\/", "/\\\\/\\\\/\\\\", "\\\\/\\\\/\\\\/"}) return 6;
            if (m.render() != "/\\\\/\\\\/\\\\\\n\\\\/\\\\/\\\\/\\n/\\\\/\\\\/\\\\\\n\\\\/\\\\/\\\\/\\n") return 7;
            return 0;
            """,
            "alternating two-character tooth units per row",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and unalternated units",
            "row and teeth bounds, unit parity per row, exact unit boundaries, and trailing-newline policy",
            "unit alternation as the rejection discriminator",
            "alternating tooth unit renderer",
            project_support=True,
        ),
        c(
            "f26dia-trail-marker-switchback",
            "Trail marker switchback",
            "trail_marker",
            """
            class TrailError : public std::invalid_argument {
            public:
                explicit TrailError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SwitchbackMarks {
            public:
                SwitchbackMarks(std::size_t rows, std::size_t width);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class TrailError : public std::invalid_argument {
            public:
                explicit TrailError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SwitchbackMarks {
            public:
                SwitchbackMarks(std::size_t rows, std::size_t width);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
            };
            """,
            """
            SwitchbackMarks::SwitchbackMarks(std::size_t rows, std::size_t width) : rows_(rows), width_(width) {
                if (rows < 2 || rows > 16) throw TrailError("rows outside 2..16");
                if (width < 3 || width > 11) throw TrailError("width outside 3..11");
            }
            std::size_t SwitchbackMarks::rows() const { return rows_; }
            std::size_t SwitchbackMarks::width() const { return width_; }
            std::size_t SwitchbackMarks::height() const { return rows_; }
            std::vector<std::string> SwitchbackMarks::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t period = 2 * (width_ - 1);
                    const std::size_t raw = r % period;
                    const std::size_t p = raw < width_ ? raw : period - raw;
                    std::string row(width_, ' ');
                    row[p] = '<';
                    row[width_ - 1 - p] = '>';
                    out.push_back(row);
                }
                return out;
            }
            std::string SwitchbackMarks::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            SwitchbackMarks::SwitchbackMarks(std::size_t rows, std::size_t width) : rows_(rows), width_(width) {
                if (rows < 2 || rows > 16) throw TrailError("rows outside 2..16");
                if (width < 3 || width > 11) throw TrailError("width outside 3..11");
            }
            std::size_t SwitchbackMarks::rows() const { return rows_; }
            std::size_t SwitchbackMarks::width() const { return width_; }
            std::size_t SwitchbackMarks::height() const { return rows_; }
            std::vector<std::string> SwitchbackMarks::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t period = 2 * (width_ - 1);
                    const std::size_t raw = r % period;
                    const std::size_t p = raw < width_ ? raw : period - raw;
                    std::string row(width_, ' ');
                    row[p] = '>';
                    row[width_ - 1 - p] = '<';
                    out.push_back(row);
                }
                return out;
            }
            std::string SwitchbackMarks::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            SwitchbackMarks marks(3, 5);
            if (marks.rows() != 3U) return 1;
            if (marks.width() != 5U) return 2;
            if (marks.height() != 3U) return 3;
            if (marks.lines() != std::vector<std::string>{"<   >", " < > ", "  >  "}) return 4;
            if (marks.render() != "<   >\\n < > \\n  >  ") return 5;
            SwitchbackMarks two(2, 3);
            if (two.lines() != std::vector<std::string>{"< >", " > "}) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { SwitchbackMarks bad(1, 5); } catch (const TrailError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { SwitchbackMarks bad(17, 5); } catch (const TrailError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { SwitchbackMarks bad(2, 2); } catch (const TrailError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { SwitchbackMarks bad(2, 12); } catch (const TrailError&) { threw = true; }
            if (!threw) return 4;
            SwitchbackMarks m(6, 4);
            if (m.width() != 4U) return 5;
            if (m.lines() != std::vector<std::string>{"<  >", " <> ", " >< ", ">  <", " >< ", " <> "}) return 6;
            if (m.render() != "<  >\\n <> \\n >< \\n>  <\\n >< \\n <> ") return 7;
            return 0;
            """,
            "mirrored bounce marks with crossing precedence",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and swapped sides",
            "row and width bounds, side assignment per phase, and crossing precedence",
            "side assignment as the rejection discriminator",
            "mirrored bounce mark renderer",
        ),
        c(
            "f26dia-warehouse-belt-fold",
            "Warehouse belt fold",
            "warehouse_belt",
            """
            class BeltError : public std::domain_error {
            public:
                explicit BeltError(const std::string& message) : std::domain_error(message) {}
            };
            class BeltFold {
            public:
                BeltFold(std::size_t rows, std::size_t span, char fill);
                std::size_t rows() const;
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class BeltError : public std::domain_error {
            public:
                explicit BeltError(const std::string& message) : std::domain_error(message) {}
            };
            class BeltFold {
            public:
                BeltFold(std::size_t rows, std::size_t span, char fill);
                std::size_t rows() const;
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t span_;
                char fill_;
            };
            """,
            """
            BeltFold::BeltFold(std::size_t rows, std::size_t span, char fill) : rows_(rows), span_(span), fill_(fill) {
                if (rows == 0 || rows > 12) throw BeltError("rows outside 1..12");
                if (span < 2 || span > 9) throw BeltError("span outside 2..9");
                if (fill < 33 || fill > 126) throw BeltError("fill must be a printable non-space ASCII character");
            }
            std::size_t BeltFold::rows() const { return rows_; }
            std::size_t BeltFold::span() const { return span_; }
            std::size_t BeltFold::width() const { return 2 * span_ - 1; }
            std::size_t BeltFold::height() const { return rows_; }
            std::vector<std::string> BeltFold::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t period = 2 * (span_ - 1);
                    const std::size_t raw = r % period;
                    const std::size_t p = raw < span_ ? raw : period - raw;
                    const std::size_t run = 2 * p + 1;
                    const std::size_t start = span_ - 1 - p;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string BeltFold::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BeltFold::BeltFold(std::size_t rows, std::size_t span, char fill) : rows_(rows), span_(span), fill_(fill) {
                if (rows == 0 || rows > 12) throw BeltError("rows outside 1..12");
                if (span < 2 || span > 9) throw BeltError("span outside 2..9");
                if (fill < 33 || fill > 126) throw BeltError("fill must be a printable non-space ASCII character");
            }
            std::size_t BeltFold::rows() const { return rows_; }
            std::size_t BeltFold::span() const { return span_; }
            std::size_t BeltFold::width() const { return 2 * span_ - 1; }
            std::size_t BeltFold::height() const { return rows_; }
            std::vector<std::string> BeltFold::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t period = 2 * (span_ - 1);
                    const std::size_t raw = r % period;
                    const std::size_t p = raw < span_ ? raw : period - raw;
                    const std::size_t run = 2 * (span_ - 1 - p) + 1;
                    const std::size_t start = p;
                    std::string row(w, ' ');
                    for (std::size_t c = start; c < start + run; ++c) row[c] = fill_;
                    out.push_back(row);
                }
                return out;
            }
            std::string BeltFold::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BeltFold belt(4, 3, 'b');
            if (belt.rows() != 4U) return 1;
            if (belt.span() != 3U) return 2;
            if (belt.width() != 5U) return 3;
            if (belt.height() != 4U) return 4;
            if (belt.lines() != std::vector<std::string>{"  b  ", " bbb ", "bbbbb", " bbb "}) return 5;
            if (belt.render() != "  b  \\n bbb \\nbbbbb\\n bbb ") return 6;
            BeltFold two(2, 2, 'o');
            if (two.lines() != std::vector<std::string>{" o ", "ooo"}) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { BeltFold bad(0, 3, 'b'); } catch (const BeltError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BeltFold bad(13, 3, 'b'); } catch (const BeltError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { BeltFold bad(2, 1, 'b'); } catch (const BeltError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { BeltFold bad(2, 10, 'b'); } catch (const BeltError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { BeltFold bad(2, 3, ' '); } catch (const BeltError&) { threw = true; }
            if (!threw) return 5;
            BeltFold m(5, 4, 'o');
            if (m.width() != 7U) return 6;
            if (m.lines() != std::vector<std::string>{"   o   ", "  ooo  ", " ooooo ", "ooooooo", " ooooo "}) return 7;
            if (m.render() != "   o   \\n  ooo  \\n ooooo \\nooooooo\\n ooooo ") return 8;
            return 0;
            """,
            "bounce-length centered fills over a triangle wave",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and inverted bounce phases",
            "row and span bounds, run length per phase, and leading-space exactness",
            "bounce phase as the rejection discriminator",
            "bouncing centered fill renderer",
        ),
        c(
            "f26dia-yard-fence-pickets",
            "Yard fence pickets",
            "yard_fence",
            """
            class FenceError : public std::invalid_argument {
            public:
                explicit FenceError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PicketLine {
            public:
                PicketLine(std::size_t rows, std::size_t bays);
                std::size_t rows() const;
                std::size_t bays() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class FenceError : public std::invalid_argument {
            public:
                explicit FenceError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PicketLine {
            public:
                PicketLine(std::size_t rows, std::size_t bays);
                std::size_t rows() const;
                std::size_t bays() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t bays_;
            };
            """,
            """
            PicketLine::PicketLine(std::size_t rows, std::size_t bays) : rows_(rows), bays_(bays) {
                if (rows == 0 || rows > 10) throw FenceError("rows outside 1..10");
                if (bays < 2 || bays > 12) throw FenceError("bays outside 2..12");
            }
            std::size_t PicketLine::rows() const { return rows_; }
            std::size_t PicketLine::bays() const { return bays_; }
            std::size_t PicketLine::width() const { return 2 * bays_ + 1; }
            std::size_t PicketLine::height() const { return rows_; }
            std::vector<std::string> PicketLine::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(w, ' ');
                    for (std::size_t c = 0; c < w; ++c) {
                        if (c % 2 == 0) {
                            row[c] = '|';
                        } else if (r % 2 == 1) {
                            row[c] = '-';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string PicketLine::line(std::size_t index) const {
                if (index >= height()) throw FenceError("line index out of range");
                return lines()[index];
            }
            std::string PicketLine::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PicketLine::PicketLine(std::size_t rows, std::size_t bays) : rows_(rows), bays_(bays) {
                if (rows == 0 || rows > 10) throw FenceError("rows outside 1..10");
                if (bays < 2 || bays > 12) throw FenceError("bays outside 2..12");
            }
            std::size_t PicketLine::rows() const { return rows_; }
            std::size_t PicketLine::bays() const { return bays_; }
            std::size_t PicketLine::width() const { return 2 * bays_ + 1; }
            std::size_t PicketLine::height() const { return rows_; }
            std::vector<std::string> PicketLine::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(w, ' ');
                    for (std::size_t c = 0; c < w; ++c) {
                        if (r % 2 == 0 && c % 2 == 0) {
                            row[c] = '|';
                        } else if (r % 2 == 1 && c % 2 == 1) {
                            row[c] = '|';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string PicketLine::line(std::size_t index) const {
                if (index >= height()) throw FenceError("line index out of range");
                return lines()[index];
            }
            std::string PicketLine::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PicketLine fence(3, 2);
            if (fence.rows() != 3U) return 1;
            if (fence.bays() != 2U) return 2;
            if (fence.width() != 5U) return 3;
            if (fence.height() != 3U) return 4;
            if (fence.lines() != std::vector<std::string>{"| | |", "|-|-|", "| | |"}) return 5;
            if (fence.line(1) != "|-|-|") return 6;
            if (fence.render() != "| | |\\n|-|-|\\n| | |") return 7;
            bool threw = false;
            try { fence.line(3); } catch (const FenceError&) { threw = true; }
            if (!threw) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { PicketLine bad(0, 2); } catch (const FenceError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PicketLine bad(11, 2); } catch (const FenceError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PicketLine bad(2, 1); } catch (const FenceError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { PicketLine bad(2, 13); } catch (const FenceError&) { threw = true; }
            if (!threw) return 4;
            PicketLine m(4, 3);
            if (m.width() != 7U) return 5;
            if (m.lines() != std::vector<std::string>{"| | | |", "|-|-|-|", "| | | |", "|-|-|-|"}) return 6;
            if (m.render() != "| | | |\\n|-|-|-|\\n| | | |\\n|-|-|-|") return 7;
            return 0;
            """,
            "parity-dependent picket rows with rail characters",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and shifted pickets",
            "row and bay bounds, rail characters on odd rows, picket columns, and index rejection",
            "picket parity as the rejection discriminator",
            "picket parity row renderer",
        ),
        c(
            "f26dia-anchor-locker-frame",
            "Anchor locker frame",
            "anchor_locker",
            """
            class LockerError : public std::invalid_argument {
            public:
                explicit LockerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LockerFrame {
            public:
                LockerFrame(std::size_t width, std::size_t height, char edge);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class LockerError : public std::invalid_argument {
            public:
                explicit LockerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LockerFrame {
            public:
                LockerFrame(std::size_t width, std::size_t height, char edge);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t width_;
                std::size_t height_;
                char edge_;
            };
            """,
            """
            LockerFrame::LockerFrame(std::size_t width, std::size_t height, char edge) : width_(width), height_(height), edge_(edge) {
                if (width < 3 || width > 20) throw LockerError("width outside 3..20");
                if (height < 3 || height > 12) throw LockerError("height outside 3..12");
                if (edge < 33 || edge > 126) throw LockerError("edge must be a printable non-space ASCII character");
            }
            std::size_t LockerFrame::width() const { return width_; }
            std::size_t LockerFrame::height() const { return height_; }
            std::vector<std::string> LockerFrame::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c)
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1) row[c] = edge_;
                    out.push_back(row);
                }
                return out;
            }
            std::string LockerFrame::line(std::size_t index) const {
                if (index >= height()) throw LockerError("line index out of range");
                return lines()[index];
            }
            std::string LockerFrame::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            LockerFrame::LockerFrame(std::size_t width, std::size_t height, char edge) : width_(width), height_(height), edge_(edge) {
                if (width < 3 || width > 20) throw LockerError("width outside 3..20");
                if (height < 3 || height > 12) throw LockerError("height outside 3..12");
                if (edge < 33 || edge > 126) throw LockerError("edge must be a printable non-space ASCII character");
            }
            std::size_t LockerFrame::width() const { return width_; }
            std::size_t LockerFrame::height() const { return height_; }
            std::vector<std::string> LockerFrame::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c)
                        if (r == 0 || r == height_ - 1 || c == 0) row[c] = edge_;
                    out.push_back(row);
                }
                return out;
            }
            std::string LockerFrame::line(std::size_t index) const {
                if (index >= height()) throw LockerError("line index out of range");
                return lines()[index];
            }
            std::string LockerFrame::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            LockerFrame frame(5, 3, '#');
            if (frame.width() != 5U) return 1;
            if (frame.height() != 3U) return 2;
            if (frame.lines() != std::vector<std::string>{"#####", "#   #", "#####"}) return 3;
            if (frame.line(1) != "#   #") return 4;
            if (frame.render() != "#####\\n#   #\\n#####") return 5;
            LockerFrame small(3, 3, 'o');
            if (small.lines() != std::vector<std::string>{"ooo", "o o", "ooo"}) return 6;
            bool threw = false;
            try { small.line(3); } catch (const LockerError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { LockerFrame bad(2, 3, '#'); } catch (const LockerError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { LockerFrame bad(21, 3, '#'); } catch (const LockerError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { LockerFrame bad(3, 2, '#'); } catch (const LockerError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { LockerFrame bad(3, 13, '#'); } catch (const LockerError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { LockerFrame bad(3, 3, ' '); } catch (const LockerError&) { threw = true; }
            if (!threw) return 5;
            LockerFrame m(6, 4, '+');
            if (m.lines() != std::vector<std::string>{"++++++", "+    +", "+    +", "++++++"}) return 6;
            if (m.render() != "++++++\\n+    +\\n+    +\\n++++++") return 7;
            LockerFrame wide(20, 3, '#');
            if (wide.line(0) != std::string(20, '#')) return 8;
            if (wide.line(1) != "#" + std::string(18, ' ') + "#") return 9;
            return 0;
            """,
            "hollow rectangular border with exact interior spaces",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and one-sided borders",
            "width and height bounds, all four edges, interior spaces, and index rejection",
            "four-edge discipline as the rejection discriminator",
            "hollow border box renderer",
        ),
        c(
            "f26dia-bakery-tray-border",
            "Bakery tray border",
            "bakery_tray",
            """
            class TrayError : public std::domain_error {
            public:
                explicit TrayError(const std::string& message) : std::domain_error(message) {}
            };
            class TrayBorder {
            public:
                TrayBorder(std::size_t width, std::size_t height, char rim, char fill);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class TrayError : public std::domain_error {
            public:
                explicit TrayError(const std::string& message) : std::domain_error(message) {}
            };
            class TrayBorder {
            public:
                TrayBorder(std::size_t width, std::size_t height, char rim, char fill);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t width_;
                std::size_t height_;
                char rim_;
                char fill_;
            };
            """,
            """
            TrayBorder::TrayBorder(std::size_t width, std::size_t height, char rim, char fill) : width_(width), height_(height), rim_(rim), fill_(fill) {
                if (width < 3 || width > 18) throw TrayError("width outside 3..18");
                if (height < 2 || height > 10) throw TrayError("height outside 2..10");
                if (rim < 33 || rim > 126) throw TrayError("rim must be a printable non-space ASCII character");
                if (fill < 33 || fill > 126) throw TrayError("fill must be a printable non-space ASCII character");
                if (rim == fill) throw TrayError("rim and fill must differ");
            }
            std::size_t TrayBorder::width() const { return width_; }
            std::size_t TrayBorder::height() const { return height_; }
            std::vector<std::string> TrayBorder::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, fill_);
                    for (std::size_t c = 0; c < width_; ++c)
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1) row[c] = rim_;
                    out.push_back(row);
                }
                return out;
            }
            std::string TrayBorder::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            TrayBorder::TrayBorder(std::size_t width, std::size_t height, char rim, char fill) : width_(width), height_(height), rim_(rim), fill_(fill) {
                if (width < 3 || width > 18) throw TrayError("width outside 3..18");
                if (height < 2 || height > 10) throw TrayError("height outside 2..10");
                if (rim < 33 || rim > 126) throw TrayError("rim must be a printable non-space ASCII character");
                if (fill < 33 || fill > 126) throw TrayError("fill must be a printable non-space ASCII character");
                if (rim == fill) throw TrayError("rim and fill must differ");
            }
            std::size_t TrayBorder::width() const { return width_; }
            std::size_t TrayBorder::height() const { return height_; }
            std::vector<std::string> TrayBorder::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, rim_);
                    out.push_back(row);
                }
                return out;
            }
            std::string TrayBorder::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            TrayBorder tray(5, 3, '#', '.');
            if (tray.width() != 5U) return 1;
            if (tray.height() != 3U) return 2;
            if (tray.lines() != std::vector<std::string>{"#####", "#...#", "#####"}) return 3;
            if (tray.render() != "#####\\n#...#\\n#####") return 4;
            TrayBorder flat(4, 2, 'o', 'x');
            if (flat.lines() != std::vector<std::string>{"oooo", "oooo"}) return 5;
            if (flat.render() != "oooo\\noooo") return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { TrayBorder bad(2, 3, '#', '.'); } catch (const TrayError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { TrayBorder bad(19, 3, '#', '.'); } catch (const TrayError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { TrayBorder bad(3, 1, '#', '.'); } catch (const TrayError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { TrayBorder bad(3, 11, '#', '.'); } catch (const TrayError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { TrayBorder bad(3, 3, '#', '#'); } catch (const TrayError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { TrayBorder bad(3, 3, '#', ' '); } catch (const TrayError&) { threw = true; }
            if (!threw) return 6;
            TrayBorder m(6, 4, '+', '.');
            if (m.lines() != std::vector<std::string>{"++++++", "+....+", "+....+", "++++++"}) return 7;
            if (m.render() != "++++++\\n+....+\\n+....+\\n++++++") return 8;
            return 0;
            """,
            "two-character filled border with exact interior fill",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and rim-filled interiors",
            "width and height bounds, equal-character rejection, and interior fill character on every interior cell",
            "interior-character discipline as the rejection discriminator",
            "filled border box renderer",
        ),
        c(
            "f26dia-cellar-door-hatch",
            "Cellar door hatch",
            "cellar_door",
            """
            class HatchError : public std::invalid_argument {
            public:
                explicit HatchError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HatchFrame {
            public:
                explicit HatchFrame(std::size_t size);
                std::size_t size() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class HatchError : public std::invalid_argument {
            public:
                explicit HatchError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HatchFrame {
            public:
                explicit HatchFrame(std::size_t size);
                std::size_t size() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t size_;
            };
            """,
            """
            HatchFrame::HatchFrame(std::size_t size) : size_(size) {
                if (size < 3 || size > 15) throw HatchError("size outside 3..15");
            }
            std::size_t HatchFrame::size() const { return size_; }
            std::size_t HatchFrame::width() const { return size_; }
            std::size_t HatchFrame::height() const { return size_; }
            std::vector<std::string> HatchFrame::lines() const {
                std::vector<std::string> out;
                out.reserve(size_);
                for (std::size_t r = 0; r < size_; ++r) {
                    std::string row(size_, ' ');
                    for (std::size_t c = 0; c < size_; ++c) {
                        if (r == 0 || r == size_ - 1 || c == 0 || c == size_ - 1) {
                            row[c] = '#';
                        } else if (r == c && r + c == size_ - 1) {
                            row[c] = 'X';
                        } else if (r == c) {
                            row[c] = '\\\\';
                        } else if (r + c == size_ - 1) {
                            row[c] = '/';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string HatchFrame::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            HatchFrame::HatchFrame(std::size_t size) : size_(size) {
                if (size < 3 || size > 15) throw HatchError("size outside 3..15");
            }
            std::size_t HatchFrame::size() const { return size_; }
            std::size_t HatchFrame::width() const { return size_; }
            std::size_t HatchFrame::height() const { return size_; }
            std::vector<std::string> HatchFrame::lines() const {
                std::vector<std::string> out;
                out.reserve(size_);
                for (std::size_t r = 0; r < size_; ++r) {
                    std::string row(size_, ' ');
                    for (std::size_t c = 0; c < size_; ++c) {
                        if (r == 0 || r == size_ - 1 || c == 0 || c == size_ - 1) {
                            row[c] = '#';
                        } else if (r == c && r + c == size_ - 1) {
                            row[c] = 'X';
                        } else if (r == c) {
                            row[c] = '/';
                        } else if (r + c == size_ - 1) {
                            row[c] = '\\\\';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string HatchFrame::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            HatchFrame hatch(5);
            if (hatch.size() != 5U) return 1;
            if (hatch.width() != 5U) return 2;
            if (hatch.height() != 5U) return 3;
            if (hatch.lines() != std::vector<std::string>{"#####", "#\\\\ /#", "# X #", "#/ \\\\#", "#####"}) return 4;
            if (hatch.render() != "#####\\n#\\\\ /#\\n# X #\\n#/ \\\\#\\n#####") return 5;
            HatchFrame three(3);
            if (three.lines() != std::vector<std::string>{"###", "#X#", "###"}) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { HatchFrame bad(2); } catch (const HatchError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { HatchFrame bad(16); } catch (const HatchError&) { threw = true; }
            if (!threw) return 2;
            HatchFrame m(7);
            if (m.width() != 7U) return 3;
            if (m.lines() != std::vector<std::string>{"#######", "#\\\\   /#", "# \\\\ / #", "#  X  #", "# / \\\\ #", "#/   \\\\#", "#######"}) return 4;
            if (m.render() != "#######\\n#\\\\   /#\\n# \\\\ / #\\n#  X  #\\n# / \\\\ #\\n#/   \\\\#\\n#######") return 5;
            HatchFrame even(4);
            if (even.lines() != std::vector<std::string>{"####", "#\\\\/#", "#/\\\\#", "####"}) return 6;
            return 0;
            """,
            "border plus interior diagonal cross with intersection precedence",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and swapped diagonals",
            "size bounds at 2 and 16, border precedence at corners, diagonal characters, and center intersection",
            "diagonal assignment as the rejection discriminator",
            "border-plus-cross renderer",
        ),
        c(
            "f26dia-depot-window-grille",
            "Depot window grille",
            "depot_window",
            """
            class GrilleError : public std::domain_error {
            public:
                explicit GrilleError(const std::string& message) : std::domain_error(message) {}
            };
            class WindowGrille {
            public:
                WindowGrille(std::size_t width, std::size_t height, std::size_t bars);
                std::size_t width() const;
                std::size_t height() const;
                std::size_t bars() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class GrilleError : public std::domain_error {
            public:
                explicit GrilleError(const std::string& message) : std::domain_error(message) {}
            };
            class WindowGrille {
            public:
                WindowGrille(std::size_t width, std::size_t height, std::size_t bars);
                std::size_t width() const;
                std::size_t height() const;
                std::size_t bars() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t width_;
                std::size_t height_;
                std::size_t bars_;
            };
            """,
            """
            WindowGrille::WindowGrille(std::size_t width, std::size_t height, std::size_t bars) : width_(width), height_(height), bars_(bars) {
                if (width < 5 || width > 20) throw GrilleError("width outside 5..20");
                if (height < 3 || height > 10) throw GrilleError("height outside 3..10");
                if (bars == 0 || bars > 3) throw GrilleError("bars outside 1..3");
            }
            std::size_t WindowGrille::width() const { return width_; }
            std::size_t WindowGrille::height() const { return height_; }
            std::size_t WindowGrille::bars() const { return bars_; }
            std::vector<std::string> WindowGrille::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c) {
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1) {
                            row[c] = '#';
                        } else {
                            for (std::size_t k = 1; k <= bars_; ++k)
                                if (c == k * (width_ - 1) / (bars_ + 1)) row[c] = '|';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string WindowGrille::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            WindowGrille::WindowGrille(std::size_t width, std::size_t height, std::size_t bars) : width_(width), height_(height), bars_(bars) {
                if (width < 5 || width > 20) throw GrilleError("width outside 5..20");
                if (height < 3 || height > 10) throw GrilleError("height outside 3..10");
                if (bars == 0 || bars > 3) throw GrilleError("bars outside 1..3");
            }
            std::size_t WindowGrille::width() const { return width_; }
            std::size_t WindowGrille::height() const { return height_; }
            std::size_t WindowGrille::bars() const { return bars_; }
            std::vector<std::string> WindowGrille::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c) {
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1) {
                            row[c] = '#';
                        } else if (c >= 1 && c <= bars_) {
                            row[c] = '|';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string WindowGrille::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            WindowGrille grille(7, 3, 2);
            if (grille.width() != 7U) return 1;
            if (grille.height() != 3U) return 2;
            if (grille.bars() != 2U) return 3;
            if (grille.lines() != std::vector<std::string>{"#######", "# | | #", "#######"}) return 4;
            if (grille.render() != "#######\\n# | | #\\n#######") return 5;
            WindowGrille one(5, 3, 1);
            if (one.lines() != std::vector<std::string>{"#####", "# | #", "#####"}) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { WindowGrille bad(4, 3, 1); } catch (const GrilleError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { WindowGrille bad(21, 3, 1); } catch (const GrilleError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { WindowGrille bad(5, 2, 1); } catch (const GrilleError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { WindowGrille bad(5, 11, 1); } catch (const GrilleError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { WindowGrille bad(5, 3, 0); } catch (const GrilleError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { WindowGrille bad(5, 3, 4); } catch (const GrilleError&) { threw = true; }
            if (!threw) return 6;
            WindowGrille m(9, 4, 3);
            if (m.bars() != 3U) return 7;
            if (m.lines() != std::vector<std::string>{"#########", "# | | | #", "# | | | #", "#########"}) return 8;
            if (m.render() != "#########\\n# | | | #\\n# | | | #\\n#########") return 9;
            return 0;
            """,
            "integer-spaced interior bars from an exact column formula",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and left-packed bars",
            "width, height, and bar bounds, and exact bar columns from the spacing formula",
            "spacing-formula discipline as the rejection discriminator",
            "spaced-bar frame renderer",
            project_support=True,
        ),
        c(
            "f26dia-engine-shed-gate",
            "Engine shed gate",
            "engine_shed",
            """
            class GateError : public std::invalid_argument {
            public:
                explicit GateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ShedGate {
            public:
                ShedGate(std::size_t width, std::size_t height, char edge);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class GateError : public std::invalid_argument {
            public:
                explicit GateError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ShedGate {
            public:
                ShedGate(std::size_t width, std::size_t height, char edge);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t width_;
                std::size_t height_;
                char edge_;
            };
            """,
            """
            ShedGate::ShedGate(std::size_t width, std::size_t height, char edge) : width_(width), height_(height), edge_(edge) {
                if (width < 5 || width > 21 || width % 2 == 0) throw GateError("width must be odd in 5..21");
                if (height < 3 || height > 11) throw GateError("height outside 3..11");
                if (edge < 33 || edge > 126) throw GateError("edge must be a printable non-space ASCII character");
            }
            std::size_t ShedGate::width() const { return width_; }
            std::size_t ShedGate::height() const { return height_; }
            std::vector<std::string> ShedGate::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c)
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1 || c == width_ / 2 || r == height_ / 2) row[c] = edge_;
                    out.push_back(row);
                }
                return out;
            }
            std::string ShedGate::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            ShedGate::ShedGate(std::size_t width, std::size_t height, char edge) : width_(width), height_(height), edge_(edge) {
                if (width < 5 || width > 21 || width % 2 == 0) throw GateError("width must be odd in 5..21");
                if (height < 3 || height > 11) throw GateError("height outside 3..11");
                if (edge < 33 || edge > 126) throw GateError("edge must be a printable non-space ASCII character");
            }
            std::size_t ShedGate::width() const { return width_; }
            std::size_t ShedGate::height() const { return height_; }
            std::vector<std::string> ShedGate::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c)
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1 || c == width_ / 2 - 1 || r == height_ / 2) row[c] = edge_;
                    out.push_back(row);
                }
                return out;
            }
            std::string ShedGate::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            ShedGate gate(5, 5, '#');
            if (gate.width() != 5U) return 1;
            if (gate.height() != 5U) return 2;
            if (gate.lines() != std::vector<std::string>{"#####", "# # #", "#####", "# # #", "#####"}) return 3;
            if (gate.render() != "#####\\n# # #\\n#####\\n# # #\\n#####") return 4;
            ShedGate wide(7, 3, 'o');
            if (wide.lines() != std::vector<std::string>{"ooooooo", "ooooooo", "ooooooo"}) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { ShedGate bad(4, 3, '#'); } catch (const GateError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ShedGate bad(3, 3, '#'); } catch (const GateError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { ShedGate bad(23, 3, '#'); } catch (const GateError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { ShedGate bad(5, 2, '#'); } catch (const GateError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { ShedGate bad(5, 12, '#'); } catch (const GateError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { ShedGate bad(5, 3, ' '); } catch (const GateError&) { threw = true; }
            if (!threw) return 6;
            ShedGate m(7, 5, '+');
            if (m.lines() != std::vector<std::string>{"+++++++", "+  +  +", "+++++++", "+  +  +", "+++++++"}) return 7;
            if (m.render() != "+++++++\\n+  +  +\\n+++++++\\n+  +  +\\n+++++++") return 8;
            return 0;
            """,
            "odd-width border with a centered interior cross",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and off-center crosses",
            "even-width rejection, and center column and row derivation on odd and even heights",
            "center-derivation discipline as the rejection discriminator",
            "center-cross frame renderer",
        ),
        c(
            "f26dia-foundry-mold-rim",
            "Foundry mold rim",
            "foundry_mold",
            """
            class MoldError : public std::domain_error {
            public:
                explicit MoldError(const std::string& message) : std::domain_error(message) {}
            };
            class MoldRim {
            public:
                MoldRim(std::size_t width, std::size_t height, char rim, char corner);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class MoldError : public std::domain_error {
            public:
                explicit MoldError(const std::string& message) : std::domain_error(message) {}
            };
            class MoldRim {
            public:
                MoldRim(std::size_t width, std::size_t height, char rim, char corner);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t width_;
                std::size_t height_;
                char rim_;
                char corner_;
            };
            """,
            """
            MoldRim::MoldRim(std::size_t width, std::size_t height, char rim, char corner) : width_(width), height_(height), rim_(rim), corner_(corner) {
                if (width < 3 || width > 16) throw MoldError("width outside 3..16");
                if (height < 3 || height > 16) throw MoldError("height outside 3..16");
                if (rim < 33 || rim > 126) throw MoldError("rim must be a printable non-space ASCII character");
                if (corner < 33 || corner > 126) throw MoldError("corner must be a printable non-space ASCII character");
                if (rim == corner) throw MoldError("rim and corner must differ");
            }
            std::size_t MoldRim::width() const { return width_; }
            std::size_t MoldRim::height() const { return height_; }
            std::vector<std::string> MoldRim::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c) {
                        const bool on_corner = (r == 0 || r == height_ - 1) && (c == 0 || c == width_ - 1);
                        const bool on_border = r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1;
                        if (on_corner) {
                            row[c] = corner_;
                        } else if (on_border) {
                            row[c] = rim_;
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string MoldRim::line(std::size_t index) const {
                if (index >= height()) throw MoldError("line index out of range");
                return lines()[index];
            }
            std::string MoldRim::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            MoldRim::MoldRim(std::size_t width, std::size_t height, char rim, char corner) : width_(width), height_(height), rim_(rim), corner_(corner) {
                if (width < 3 || width > 16) throw MoldError("width outside 3..16");
                if (height < 3 || height > 16) throw MoldError("height outside 3..16");
                if (rim < 33 || rim > 126) throw MoldError("rim must be a printable non-space ASCII character");
                if (corner < 33 || corner > 126) throw MoldError("corner must be a printable non-space ASCII character");
                if (rim == corner) throw MoldError("rim and corner must differ");
            }
            std::size_t MoldRim::width() const { return width_; }
            std::size_t MoldRim::height() const { return height_; }
            std::vector<std::string> MoldRim::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c)
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1) row[c] = rim_;
                    out.push_back(row);
                }
                return out;
            }
            std::string MoldRim::line(std::size_t index) const {
                if (index >= height()) throw MoldError("line index out of range");
                return lines()[index];
            }
            std::string MoldRim::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            MoldRim mold(5, 4, '#', '@');
            if (mold.width() != 5U) return 1;
            if (mold.height() != 4U) return 2;
            if (mold.lines() != std::vector<std::string>{"@###@", "#   #", "#   #", "@###@"}) return 3;
            if (mold.line(0) != "@###@") return 4;
            if (mold.render() != "@###@\\n#   #\\n#   #\\n@###@") return 5;
            bool threw = false;
            try { mold.line(4); } catch (const MoldError&) { threw = true; }
            if (!threw) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { MoldRim bad(2, 3, '#', '@'); } catch (const MoldError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { MoldRim bad(17, 3, '#', '@'); } catch (const MoldError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { MoldRim bad(3, 2, '#', '@'); } catch (const MoldError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { MoldRim bad(3, 17, '#', '@'); } catch (const MoldError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { MoldRim bad(3, 3, '#', '#'); } catch (const MoldError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { MoldRim bad(3, 3, '#', ' '); } catch (const MoldError&) { threw = true; }
            if (!threw) return 6;
            MoldRim m(3, 3, 'o', '+');
            if (m.lines() != std::vector<std::string>{"+o+", "o o", "+o+"}) return 7;
            if (m.render() != "+o+\\no o\\n+o+") return 8;
            return 0;
            """,
            "two-character border with corner precedence",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and rim corners",
            "width and height bounds, equal-character rejection, exactly four corner cells, and index rejection",
            "corner precedence as the rejection discriminator",
            "cornered border box renderer",
        ),
        c(
            "f26dia-gallery-wall-plaque",
            "Gallery wall plaque",
            "gallery_wall",
            """
            class PlaqueError : public std::invalid_argument {
            public:
                explicit PlaqueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WallPlaque {
            public:
                WallPlaque(std::size_t width, std::size_t height);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class PlaqueError : public std::invalid_argument {
            public:
                explicit PlaqueError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WallPlaque {
            public:
                WallPlaque(std::size_t width, std::size_t height);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t width_;
                std::size_t height_;
            };
            """,
            """
            WallPlaque::WallPlaque(std::size_t width, std::size_t height) : width_(width), height_(height) {
                if (width < 6 || width > 18) throw PlaqueError("width outside 6..18");
                if (height < 4 || height > 12) throw PlaqueError("height outside 4..12");
            }
            std::size_t WallPlaque::width() const { return width_; }
            std::size_t WallPlaque::height() const { return height_; }
            std::vector<std::string> WallPlaque::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c) {
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1) {
                            row[c] = '#';
                        } else if (r == 1 || r == height_ - 2 || c == 1 || c == width_ - 2) {
                            row[c] = '.';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string WallPlaque::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            WallPlaque::WallPlaque(std::size_t width, std::size_t height) : width_(width), height_(height) {
                if (width < 6 || width > 18) throw PlaqueError("width outside 6..18");
                if (height < 4 || height > 12) throw PlaqueError("height outside 4..12");
            }
            std::size_t WallPlaque::width() const { return width_; }
            std::size_t WallPlaque::height() const { return height_; }
            std::vector<std::string> WallPlaque::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t c = 0; c < width_; ++c) {
                        if (r == 0 || r == height_ - 1 || c == 0 || c == width_ - 1) {
                            row[c] = '#';
                        } else if (r == 2 || r == height_ - 3 || c == 2 || c == width_ - 3) {
                            row[c] = '.';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string WallPlaque::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            WallPlaque plaque(8, 5);
            if (plaque.width() != 8U) return 1;
            if (plaque.height() != 5U) return 2;
            if (plaque.lines() != std::vector<std::string>{"########", "#......#", "#.    .#", "#......#", "########"}) return 3;
            if (plaque.render() != "########\\n#......#\\n#.    .#\\n#......#\\n########") return 4;
            WallPlaque small(6, 4);
            if (small.lines() != std::vector<std::string>{"######", "#....#", "#....#", "######"}) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { WallPlaque bad(5, 4); } catch (const PlaqueError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { WallPlaque bad(19, 4); } catch (const PlaqueError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { WallPlaque bad(6, 3); } catch (const PlaqueError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { WallPlaque bad(6, 13); } catch (const PlaqueError&) { threw = true; }
            if (!threw) return 4;
            WallPlaque m(10, 6);
            if (m.lines() != std::vector<std::string>{"##########", "#........#", "#.      .#", "#.      .#", "#........#", "##########"}) return 5;
            if (m.render() != "##########\\n#........#\\n#.      .#\\n#.      .#\\n#........#\\n##########") return 6;
            WallPlaque wide(18, 4);
            if (wide.lines()[1] != "#" + std::string(16, '.') + "#") return 7;
            return 0;
            """,
            "two-level frame with exact inner-edge distance",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and distance-two inner frames",
            "width and height bounds, and inner frame on exactly four inner edges",
            "inner-distance discipline as the rejection discriminator",
            "double frame renderer",
        ),
        c(
            "f26dia-hangar-bay-portal",
            "Hangar bay portal",
            "hangar_bay",
            """
            class PortalError : public std::domain_error {
            public:
                explicit PortalError(const std::string& message) : std::domain_error(message) {}
            };
            class BayPortal {
            public:
                BayPortal(std::size_t width, std::size_t height, char edge);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class PortalError : public std::domain_error {
            public:
                explicit PortalError(const std::string& message) : std::domain_error(message) {}
            };
            class BayPortal {
            public:
                BayPortal(std::size_t width, std::size_t height, char edge);
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t width_;
                std::size_t height_;
                char edge_;
            };
            """,
            """
            BayPortal::BayPortal(std::size_t width, std::size_t height, char edge) : width_(width), height_(height), edge_(edge) {
                if (width < 5 || width > 19 || width % 2 == 0) throw PortalError("width must be odd in 5..19");
                if (height < 4 || height > 12) throw PortalError("height outside 4..12");
                if (edge < 33 || edge > 126) throw PortalError("edge must be a printable non-space ASCII character");
            }
            std::size_t BayPortal::width() const { return width_; }
            std::size_t BayPortal::height() const { return height_; }
            std::vector<std::string> BayPortal::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    if (r == 0) {
                        for (std::size_t c = 1; c < width_ - 1; ++c) row[c] = edge_;
                    } else if (r == height_ - 1) {
                        for (std::size_t c = 0; c < width_; ++c) row[c] = edge_;
                    } else {
                        row[0] = edge_;
                        row[width_ - 1] = edge_;
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string BayPortal::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BayPortal::BayPortal(std::size_t width, std::size_t height, char edge) : width_(width), height_(height), edge_(edge) {
                if (width < 5 || width > 19 || width % 2 == 0) throw PortalError("width must be odd in 5..19");
                if (height < 4 || height > 12) throw PortalError("height outside 4..12");
                if (edge < 33 || edge > 126) throw PortalError("edge must be a printable non-space ASCII character");
            }
            std::size_t BayPortal::width() const { return width_; }
            std::size_t BayPortal::height() const { return height_; }
            std::vector<std::string> BayPortal::lines() const {
                std::vector<std::string> out;
                out.reserve(height_);
                for (std::size_t r = 0; r < height_; ++r) {
                    std::string row(width_, ' ');
                    if (r == 0 || r == height_ - 1) {
                        for (std::size_t c = 0; c < width_; ++c) row[c] = edge_;
                    } else {
                        row[0] = edge_;
                        row[width_ - 1] = edge_;
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string BayPortal::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BayPortal portal(5, 4, '#');
            if (portal.width() != 5U) return 1;
            if (portal.height() != 4U) return 2;
            if (portal.lines() != std::vector<std::string>{" ### ", "#   #", "#   #", "#####"}) return 3;
            if (portal.render() != " ### \\n#   #\\n#   #\\n#####") return 4;
            BayPortal wide(7, 5, 'o');
            if (wide.lines() != std::vector<std::string>{" ooooo ", "o     o", "o     o", "o     o", "ooooooo"}) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { BayPortal bad(4, 4, '#'); } catch (const PortalError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BayPortal bad(3, 4, '#'); } catch (const PortalError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { BayPortal bad(21, 4, '#'); } catch (const PortalError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { BayPortal bad(5, 3, '#'); } catch (const PortalError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { BayPortal bad(5, 13, '#'); } catch (const PortalError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { BayPortal bad(5, 4, ' '); } catch (const PortalError&) { threw = true; }
            if (!threw) return 6;
            BayPortal m(9, 6, '+');
            if (m.lines() != std::vector<std::string>{" +++++++ ", "+       +", "+       +", "+       +", "+       +", "+++++++++"}) return 7;
            if (m.render() != " +++++++ \\n+       +\\n+       +\\n+       +\\n+       +\\n+++++++++") return 8;
            return 0;
            """,
            "open-corner portal outline with exact wall columns",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and closed top corners",
            "even-width rejection, open top corners, wall columns, and full bottom row",
            "corner policy as the rejection discriminator",
            "open-corner portal renderer",
            project_support=True,
        ),
        c(
            "f26dia-ink-ribbon-waves",
            "Ink ribbon waves",
            "ink_ribbon",
            """
            class RibbonError : public std::invalid_argument {
            public:
                explicit RibbonError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RibbonWaves {
            public:
                RibbonWaves(std::size_t rows, std::size_t width, char mark);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class RibbonError : public std::invalid_argument {
            public:
                explicit RibbonError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RibbonWaves {
            public:
                RibbonWaves(std::size_t rows, std::size_t width, char mark);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                char mark_;
            };
            """,
            """
            RibbonWaves::RibbonWaves(std::size_t rows, std::size_t width, char mark) : rows_(rows), width_(width), mark_(mark) {
                if (rows == 0 || rows > 12) throw RibbonError("rows outside 1..12");
                if (width < 4 || width > 24) throw RibbonError("width outside 4..24");
                if (mark < 33 || mark > 126) throw RibbonError("mark must be a printable non-space ASCII character");
            }
            std::size_t RibbonWaves::rows() const { return rows_; }
            std::size_t RibbonWaves::width() const { return width_; }
            std::size_t RibbonWaves::height() const { return rows_; }
            std::vector<std::string> RibbonWaves::lines() const {
                const std::size_t offsets[4] = {0, 1, 2, 1};
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t off = offsets[r % 4];
                    std::string row(width_, ' ');
                    for (std::size_t x = off; x < width_; x += 4) row[x] = mark_;
                    out.push_back(row);
                }
                return out;
            }
            std::string RibbonWaves::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            RibbonWaves::RibbonWaves(std::size_t rows, std::size_t width, char mark) : rows_(rows), width_(width), mark_(mark) {
                if (rows == 0 || rows > 12) throw RibbonError("rows outside 1..12");
                if (width < 4 || width > 24) throw RibbonError("width outside 4..24");
                if (mark < 33 || mark > 126) throw RibbonError("mark must be a printable non-space ASCII character");
            }
            std::size_t RibbonWaves::rows() const { return rows_; }
            std::size_t RibbonWaves::width() const { return width_; }
            std::size_t RibbonWaves::height() const { return rows_; }
            std::vector<std::string> RibbonWaves::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const std::size_t off = r % 4;
                    std::string row(width_, ' ');
                    for (std::size_t x = off; x < width_; x += 4) row[x] = mark_;
                    out.push_back(row);
                }
                return out;
            }
            std::string RibbonWaves::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            RibbonWaves waves(4, 8, '~');
            if (waves.rows() != 4U) return 1;
            if (waves.width() != 8U) return 2;
            if (waves.height() != 4U) return 3;
            if (waves.lines() != std::vector<std::string>{"~   ~   ", " ~   ~  ", "  ~   ~ ", " ~   ~  "}) return 4;
            if (waves.render() != "~   ~   \\n ~   ~  \\n  ~   ~ \\n ~   ~  ") return 5;
            RibbonWaves one(1, 4, '#');
            if (one.lines() != std::vector<std::string>{"#   "}) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { RibbonWaves bad(0, 8, '~'); } catch (const RibbonError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RibbonWaves bad(13, 8, '~'); } catch (const RibbonError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { RibbonWaves bad(2, 3, '~'); } catch (const RibbonError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { RibbonWaves bad(2, 25, '~'); } catch (const RibbonError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { RibbonWaves bad(2, 8, ' '); } catch (const RibbonError&) { threw = true; }
            if (!threw) return 5;
            RibbonWaves m(6, 6, '#');
            if (m.lines() != std::vector<std::string>{"#   # ", " #   #", "  #   ", " #   #", "#   # ", " #   #"}) return 6;
            if (m.render() != "#   # \\n #   #\\n  #   \\n #   #\\n#   # \\n #   #") return 7;
            return 0;
            """,
            "triangle-offset periodic marks over a four-row cycle",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and sawtooth offsets",
            "row and width bounds, offset sequence over four rows, and mark columns",
            "offset shape as the rejection discriminator",
            "triangle-offset mark raster",
        ),
        c(
            "f26dia-lantern-glow-bands",
            "Lantern glow bands",
            "lantern_glow",
            """
            class GlowError : public std::domain_error {
            public:
                explicit GlowError(const std::string& message) : std::domain_error(message) {}
            };
            class GlowBands {
            public:
                GlowBands(std::size_t rows, std::size_t width);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class GlowError : public std::domain_error {
            public:
                explicit GlowError(const std::string& message) : std::domain_error(message) {}
            };
            class GlowBands {
            public:
                GlowBands(std::size_t rows, std::size_t width);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
            };
            """,
            """
            GlowBands::GlowBands(std::size_t rows, std::size_t width) : rows_(rows), width_(width) {
                if (rows < 2 || rows > 14) throw GlowError("rows outside 2..14");
                if (width < 3 || width > 20) throw GlowError("width outside 3..20");
            }
            std::size_t GlowBands::rows() const { return rows_; }
            std::size_t GlowBands::width() const { return width_; }
            std::size_t GlowBands::height() const { return rows_; }
            std::vector<std::string> GlowBands::lines() const {
                const char cycle[3] = {'*', '+', '.'};
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const char mark = cycle[(r / 2) % 3];
                    out.push_back(std::string(width_, mark));
                }
                return out;
            }
            std::string GlowBands::line(std::size_t index) const {
                if (index >= height()) throw GlowError("line index out of range");
                return lines()[index];
            }
            std::string GlowBands::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            GlowBands::GlowBands(std::size_t rows, std::size_t width) : rows_(rows), width_(width) {
                if (rows < 2 || rows > 14) throw GlowError("rows outside 2..14");
                if (width < 3 || width > 20) throw GlowError("width outside 3..20");
            }
            std::size_t GlowBands::rows() const { return rows_; }
            std::size_t GlowBands::width() const { return width_; }
            std::size_t GlowBands::height() const { return rows_; }
            std::vector<std::string> GlowBands::lines() const {
                const char cycle[3] = {'*', '+', '.'};
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const char mark = cycle[r % 3];
                    out.push_back(std::string(width_, mark));
                }
                return out;
            }
            std::string GlowBands::line(std::size_t index) const {
                if (index >= height()) throw GlowError("line index out of range");
                return lines()[index];
            }
            std::string GlowBands::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            GlowBands glow(6, 4);
            if (glow.rows() != 6U) return 1;
            if (glow.width() != 4U) return 2;
            if (glow.height() != 6U) return 3;
            if (glow.lines() != std::vector<std::string>{"****", "****", "++++", "++++", "....", "...."}) return 4;
            if (glow.line(2) != "++++") return 5;
            if (glow.render() != "****\\n****\\n++++\\n++++\\n....\\n....") return 6;
            bool threw = false;
            try { glow.line(6); } catch (const GlowError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { GlowBands bad(1, 4); } catch (const GlowError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { GlowBands bad(15, 4); } catch (const GlowError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { GlowBands bad(2, 2); } catch (const GlowError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { GlowBands bad(2, 21); } catch (const GlowError&) { threw = true; }
            if (!threw) return 4;
            GlowBands m(8, 3);
            if (m.lines() != std::vector<std::string>{"***", "***", "+++", "+++", "...", "...", "***", "***"}) return 5;
            if (m.render() != "***\\n***\\n+++\\n+++\\n...\\n...\\n***\\n***") return 6;
            return 0;
            """,
            "paired-row band cycling over a three-character cycle",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and unpaired bands",
            "row and width bounds, two-row band persistence, cycle order, and index rejection",
            "band pairing as the rejection discriminator",
            "paired-row band raster",
        ),
        c(
            "f26dia-meadow-row-furrows",
            "Meadow row furrows",
            "meadow_row",
            """
            class FurrowError : public std::invalid_argument {
            public:
                explicit FurrowError(const std::string& message) : std::invalid_argument(message) {}
            };
            class FurrowField {
            public:
                FurrowField(std::size_t rows, std::size_t width, char ridge);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class FurrowError : public std::invalid_argument {
            public:
                explicit FurrowError(const std::string& message) : std::invalid_argument(message) {}
            };
            class FurrowField {
            public:
                FurrowField(std::size_t rows, std::size_t width, char ridge);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                char ridge_;
            };
            """,
            """
            FurrowField::FurrowField(std::size_t rows, std::size_t width, char ridge) : rows_(rows), width_(width), ridge_(ridge) {
                if (rows == 0 || rows > 12) throw FurrowError("rows outside 1..12");
                if (width < 5 || width > 24) throw FurrowError("width outside 5..24");
                if (ridge < 33 || ridge > 126) throw FurrowError("ridge must be a printable non-space ASCII character");
                if (ridge == '~') throw FurrowError("ridge must not be the background character");
            }
            std::size_t FurrowField::rows() const { return rows_; }
            std::size_t FurrowField::width() const { return width_; }
            std::size_t FurrowField::height() const { return rows_; }
            std::vector<std::string> FurrowField::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, '~');
                    for (std::size_t x = 0; x < width_; ++x)
                        if ((x + r) % 3 == 0) row[x] = ridge_;
                    out.push_back(row);
                }
                return out;
            }
            std::string FurrowField::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            FurrowField::FurrowField(std::size_t rows, std::size_t width, char ridge) : rows_(rows), width_(width), ridge_(ridge) {
                if (rows == 0 || rows > 12) throw FurrowError("rows outside 1..12");
                if (width < 5 || width > 24) throw FurrowError("width outside 5..24");
                if (ridge < 33 || ridge > 126) throw FurrowError("ridge must be a printable non-space ASCII character");
                if (ridge == '~') throw FurrowError("ridge must not be the background character");
            }
            std::size_t FurrowField::rows() const { return rows_; }
            std::size_t FurrowField::width() const { return width_; }
            std::size_t FurrowField::height() const { return rows_; }
            std::vector<std::string> FurrowField::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, '~');
                    for (std::size_t x = 0; x < width_; ++x)
                        if ((x + 2 * r) % 3 == 0) row[x] = ridge_;
                    out.push_back(row);
                }
                return out;
            }
            std::string FurrowField::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            FurrowField field(2, 6, '#');
            if (field.rows() != 2U) return 1;
            if (field.width() != 6U) return 2;
            if (field.height() != 2U) return 3;
            if (field.lines() != std::vector<std::string>{"#~~#~~", "~~#~~#"}) return 4;
            if (field.render() != "#~~#~~\\n~~#~~#") return 5;
            FurrowField one(1, 5, 'o');
            if (one.lines() != std::vector<std::string>{"o~~o~"}) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { FurrowField bad(0, 6, '#'); } catch (const FurrowError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { FurrowField bad(13, 6, '#'); } catch (const FurrowError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { FurrowField bad(2, 4, '#'); } catch (const FurrowError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { FurrowField bad(2, 25, '#'); } catch (const FurrowError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { FurrowField bad(2, 6, ' '); } catch (const FurrowError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { FurrowField bad(2, 6, '~'); } catch (const FurrowError&) { threw = true; }
            if (!threw) return 6;
            FurrowField m(3, 8, '+');
            if (m.lines() != std::vector<std::string>{"+~~+~~+~", "~~+~~+~~", "~+~~+~~+"}) return 7;
            if (m.render() != "+~~+~~+~\\n~~+~~+~~\\n~+~~+~~+") return 8;
            return 0;
            """,
            "drifting ridge marks over a background character",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and wrong-drift ridges",
            "row and width bounds, background rejection for ridge, and drift by one column per row",
            "drift rate as the rejection discriminator",
            "drifting ridge raster",
        ),
        c(
            "f26dia-net-loft-mesh",
            "Net loft mesh",
            "net_loft",
            """
            class MeshError : public std::domain_error {
            public:
                explicit MeshError(const std::string& message) : std::domain_error(message) {}
            };
            class MeshNet {
            public:
                MeshNet(std::size_t rows, std::size_t width, char knot);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class MeshError : public std::domain_error {
            public:
                explicit MeshError(const std::string& message) : std::domain_error(message) {}
            };
            class MeshNet {
            public:
                MeshNet(std::size_t rows, std::size_t width, char knot);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                char knot_;
            };
            """,
            """
            MeshNet::MeshNet(std::size_t rows, std::size_t width, char knot) : rows_(rows), width_(width), knot_(knot) {
                if (rows == 0 || rows > 10) throw MeshError("rows outside 1..10");
                if (width < 3 || width > 18) throw MeshError("width outside 3..18");
                if (knot < 33 || knot > 126) throw MeshError("knot must be a printable non-space ASCII character");
                if (knot == '-' || knot == '|') throw MeshError("knot must not be a mesh strand character");
            }
            std::size_t MeshNet::rows() const { return rows_; }
            std::size_t MeshNet::width() const { return width_; }
            std::size_t MeshNet::height() const { return rows_; }
            std::vector<std::string> MeshNet::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) {
                        if (r % 2 == 0) {
                            row[x] = x % 2 == 0 ? knot_ : '-';
                        } else if (x % 2 == 0) {
                            row[x] = '|';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string MeshNet::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            MeshNet::MeshNet(std::size_t rows, std::size_t width, char knot) : rows_(rows), width_(width), knot_(knot) {
                if (rows == 0 || rows > 10) throw MeshError("rows outside 1..10");
                if (width < 3 || width > 18) throw MeshError("width outside 3..18");
                if (knot < 33 || knot > 126) throw MeshError("knot must be a printable non-space ASCII character");
                if (knot == '-' || knot == '|') throw MeshError("knot must not be a mesh strand character");
            }
            std::size_t MeshNet::rows() const { return rows_; }
            std::size_t MeshNet::width() const { return width_; }
            std::size_t MeshNet::height() const { return rows_; }
            std::vector<std::string> MeshNet::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) {
                        if (r % 2 == 1) {
                            row[x] = x % 2 == 1 ? knot_ : '|';
                        } else if (x % 2 == 1) {
                            row[x] = '-';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string MeshNet::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            MeshNet net(2, 5, 'o');
            if (net.rows() != 2U) return 1;
            if (net.width() != 5U) return 2;
            if (net.height() != 2U) return 3;
            if (net.lines() != std::vector<std::string>{"o-o-o", "| | |"}) return 4;
            if (net.render() != "o-o-o\\n| | |") return 5;
            MeshNet one(1, 3, '#');
            if (one.lines() != std::vector<std::string>{"#-#"}) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { MeshNet bad(0, 5, 'o'); } catch (const MeshError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { MeshNet bad(11, 5, 'o'); } catch (const MeshError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { MeshNet bad(2, 2, 'o'); } catch (const MeshError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { MeshNet bad(2, 19, 'o'); } catch (const MeshError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { MeshNet bad(2, 5, '-'); } catch (const MeshError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { MeshNet bad(2, 5, '|'); } catch (const MeshError&) { threw = true; }
            if (!threw) return 6;
            MeshNet m(3, 4, '+');
            if (m.lines() != std::vector<std::string>{"+-+-", "| | ", "+-+-"}) return 7;
            if (m.render() != "+-+-\\n| | \\n+-+-") return 8;
            return 0;
            """,
            "parity-mesh cell rules with knot and strand characters",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and shifted knots",
            "row and width bounds, knot character restrictions, and per-parity cell rules",
            "mesh parity as the rejection discriminator",
            "parity mesh raster",
            project_support=True,
        ),
        c(
            "f26dia-orchard-row-trellis",
            "Orchard row trellis",
            "orchard_row",
            """
            class TrellisError : public std::invalid_argument {
            public:
                explicit TrellisError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TrellisGrid {
            public:
                TrellisGrid(std::size_t rows, std::size_t width, std::size_t pitch);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t pitch() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class TrellisError : public std::invalid_argument {
            public:
                explicit TrellisError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TrellisGrid {
            public:
                TrellisGrid(std::size_t rows, std::size_t width, std::size_t pitch);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t pitch() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                std::size_t pitch_;
            };
            """,
            """
            TrellisGrid::TrellisGrid(std::size_t rows, std::size_t width, std::size_t pitch) : rows_(rows), width_(width), pitch_(pitch) {
                if (rows == 0 || rows > 12) throw TrellisError("rows outside 1..12");
                if (width < 4 || width > 24) throw TrellisError("width outside 4..24");
                if (pitch < 2 || pitch > 6) throw TrellisError("pitch outside 2..6");
            }
            std::size_t TrellisGrid::rows() const { return rows_; }
            std::size_t TrellisGrid::width() const { return width_; }
            std::size_t TrellisGrid::pitch() const { return pitch_; }
            std::size_t TrellisGrid::height() const { return rows_; }
            std::vector<std::string> TrellisGrid::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) {
                        const bool up = (x + r) % pitch_ == 0;
                        const bool down = (x + pitch_ - r % pitch_) % pitch_ == 0;
                        if (up && down) {
                            row[x] = 'X';
                        } else if (up) {
                            row[x] = '/';
                        } else if (down) {
                            row[x] = '\\\\';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string TrellisGrid::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            TrellisGrid::TrellisGrid(std::size_t rows, std::size_t width, std::size_t pitch) : rows_(rows), width_(width), pitch_(pitch) {
                if (rows == 0 || rows > 12) throw TrellisError("rows outside 1..12");
                if (width < 4 || width > 24) throw TrellisError("width outside 4..24");
                if (pitch < 2 || pitch > 6) throw TrellisError("pitch outside 2..6");
            }
            std::size_t TrellisGrid::rows() const { return rows_; }
            std::size_t TrellisGrid::width() const { return width_; }
            std::size_t TrellisGrid::pitch() const { return pitch_; }
            std::size_t TrellisGrid::height() const { return rows_; }
            std::vector<std::string> TrellisGrid::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) {
                        const bool up = (x + r) % pitch_ == 0;
                        if (up) row[x] = '/';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string TrellisGrid::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            TrellisGrid trellis(3, 6, 3);
            if (trellis.rows() != 3U) return 1;
            if (trellis.width() != 6U) return 2;
            if (trellis.pitch() != 3U) return 3;
            if (trellis.height() != 3U) return 4;
            if (trellis.lines() != std::vector<std::string>{"X  X  ", " \\\\/ \\\\/", " /\\\\ /\\\\"}) return 5;
            if (trellis.render() != "X  X  \\n \\\\/ \\\\/\\n /\\\\ /\\\\") return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { TrellisGrid bad(0, 6, 3); } catch (const TrellisError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { TrellisGrid bad(13, 6, 3); } catch (const TrellisError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { TrellisGrid bad(2, 3, 3); } catch (const TrellisError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { TrellisGrid bad(2, 25, 3); } catch (const TrellisError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { TrellisGrid bad(2, 6, 1); } catch (const TrellisError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { TrellisGrid bad(2, 6, 7); } catch (const TrellisError&) { threw = true; }
            if (!threw) return 6;
            TrellisGrid m(2, 5, 2);
            if (m.lines() != std::vector<std::string>{"X X X", " X X "}) return 7;
            if (m.render() != "X X X\\n X X ") return 8;
            return 0;
            """,
            "two diagonal families with intersection precedence",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and single-family lattices",
            "row, width, and pitch bounds, both diagonal families, and intersection precedence",
            "diagonal-family completeness as the rejection discriminator",
            "cross-hatch diagonal raster",
        ),
        c(
            "f26dia-pump-house-pulses",
            "Pump house pulses",
            "pump_house",
            """
            class PulseError : public std::domain_error {
            public:
                explicit PulseError(const std::string& message) : std::domain_error(message) {}
            };
            class PulseTrain {
            public:
                PulseTrain(std::size_t rows, std::size_t width, std::size_t period);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t period() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class PulseError : public std::domain_error {
            public:
                explicit PulseError(const std::string& message) : std::domain_error(message) {}
            };
            class PulseTrain {
            public:
                PulseTrain(std::size_t rows, std::size_t width, std::size_t period);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t period() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                std::size_t period_;
            };
            """,
            """
            PulseTrain::PulseTrain(std::size_t rows, std::size_t width, std::size_t period) : rows_(rows), width_(width), period_(period) {
                if (rows == 0 || rows > 10) throw PulseError("rows outside 1..10");
                if (width < 4 || width > 24) throw PulseError("width outside 4..24");
                if (period < 2 || period > 8) throw PulseError("period outside 2..8");
            }
            std::size_t PulseTrain::rows() const { return rows_; }
            std::size_t PulseTrain::width() const { return width_; }
            std::size_t PulseTrain::period() const { return period_; }
            std::size_t PulseTrain::height() const { return rows_; }
            std::vector<std::string> PulseTrain::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x)
                        row[x] = (x / period_ + r) % 2 == 0 ? '#' : '.';
                    out.push_back(row);
                }
                return out;
            }
            std::string PulseTrain::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PulseTrain::PulseTrain(std::size_t rows, std::size_t width, std::size_t period) : rows_(rows), width_(width), period_(period) {
                if (rows == 0 || rows > 10) throw PulseError("rows outside 1..10");
                if (width < 4 || width > 24) throw PulseError("width outside 4..24");
                if (period < 2 || period > 8) throw PulseError("period outside 2..8");
            }
            std::size_t PulseTrain::rows() const { return rows_; }
            std::size_t PulseTrain::width() const { return width_; }
            std::size_t PulseTrain::period() const { return period_; }
            std::size_t PulseTrain::height() const { return rows_; }
            std::vector<std::string> PulseTrain::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x)
                        row[x] = x % period_ == 0 ? '#' : '.';
                    out.push_back(row);
                }
                return out;
            }
            std::string PulseTrain::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PulseTrain pulses(2, 8, 2);
            if (pulses.rows() != 2U) return 1;
            if (pulses.width() != 8U) return 2;
            if (pulses.period() != 2U) return 3;
            if (pulses.height() != 2U) return 4;
            if (pulses.lines() != std::vector<std::string>{"##..##..", "..##..##"}) return 5;
            if (pulses.render() != "##..##..\\n..##..##") return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { PulseTrain bad(0, 8, 2); } catch (const PulseError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PulseTrain bad(11, 8, 2); } catch (const PulseError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PulseTrain bad(2, 3, 2); } catch (const PulseError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { PulseTrain bad(2, 25, 2); } catch (const PulseError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { PulseTrain bad(2, 8, 1); } catch (const PulseError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { PulseTrain bad(2, 8, 9); } catch (const PulseError&) { threw = true; }
            if (!threw) return 6;
            PulseTrain m(3, 9, 3);
            if (m.lines() != std::vector<std::string>{"###...###", "...###...", "###...###"}) return 7;
            if (m.render() != "###...###\\n...###...\\n###...###") return 8;
            return 0;
            """,
            "block-parity checkerboard over exact period blocks",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and thin stripe pulses",
            "row, width, and period bounds, block boundaries at period multiples, and row parity flip",
            "block parity as the rejection discriminator",
            "block parity raster",
        ),
        c(
            "f26dia-quay-tide-ripples",
            "Quay tide ripples",
            "quay_tide",
            """
            class RippleError : public std::invalid_argument {
            public:
                explicit RippleError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RippleField {
            public:
                RippleField(std::size_t rows, std::size_t width, char crest);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class RippleError : public std::invalid_argument {
            public:
                explicit RippleError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RippleField {
            public:
                RippleField(std::size_t rows, std::size_t width, char crest);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                char crest_;
            };
            """,
            """
            RippleField::RippleField(std::size_t rows, std::size_t width, char crest) : rows_(rows), width_(width), crest_(crest) {
                if (rows < 2 || rows > 12) throw RippleError("rows outside 2..12");
                if (width < 6 || width > 24) throw RippleError("width outside 6..24");
                if (crest < 33 || crest > 126) throw RippleError("crest must be a printable non-space ASCII character");
            }
            std::size_t RippleField::rows() const { return rows_; }
            std::size_t RippleField::width() const { return width_; }
            std::size_t RippleField::height() const { return rows_; }
            std::vector<std::string> RippleField::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x)
                        if ((x + 2 * r) % 6 < 2) row[x] = crest_;
                    out.push_back(row);
                }
                return out;
            }
            std::string RippleField::line(std::size_t index) const {
                if (index >= height()) throw RippleError("line index out of range");
                return lines()[index];
            }
            std::string RippleField::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            RippleField::RippleField(std::size_t rows, std::size_t width, char crest) : rows_(rows), width_(width), crest_(crest) {
                if (rows < 2 || rows > 12) throw RippleError("rows outside 2..12");
                if (width < 6 || width > 24) throw RippleError("width outside 6..24");
                if (crest < 33 || crest > 126) throw RippleError("crest must be a printable non-space ASCII character");
            }
            std::size_t RippleField::rows() const { return rows_; }
            std::size_t RippleField::width() const { return width_; }
            std::size_t RippleField::height() const { return rows_; }
            std::vector<std::string> RippleField::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x)
                        if ((x + 2 * r) % 6 < 4) row[x] = crest_;
                    out.push_back(row);
                }
                return out;
            }
            std::string RippleField::line(std::size_t index) const {
                if (index >= height()) throw RippleError("line index out of range");
                return lines()[index];
            }
            std::string RippleField::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            RippleField ripples(2, 8, '~');
            if (ripples.rows() != 2U) return 1;
            if (ripples.width() != 8U) return 2;
            if (ripples.height() != 2U) return 3;
            if (ripples.lines() != std::vector<std::string>{"~~    ~~", "    ~~  "}) return 4;
            if (ripples.line(1) != "    ~~  ") return 5;
            if (ripples.render() != "~~    ~~\\n    ~~  ") return 6;
            bool threw = false;
            try { ripples.line(2); } catch (const RippleError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { RippleField bad(1, 8, '~'); } catch (const RippleError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RippleField bad(13, 8, '~'); } catch (const RippleError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { RippleField bad(2, 5, '~'); } catch (const RippleError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { RippleField bad(2, 25, '~'); } catch (const RippleError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { RippleField bad(2, 8, ' '); } catch (const RippleError&) { threw = true; }
            if (!threw) return 5;
            RippleField m(3, 12, '#');
            if (m.lines() != std::vector<std::string>{"##    ##    ", "    ##    ##", "  ##    ##  "}) return 6;
            if (m.render() != "##    ##    \\n    ##    ##\\n  ##    ##  ") return 7;
            return 0;
            """,
            "drifting two-cell crest runs with an exact duty cycle",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and wrong duty cycles",
            "row and width bounds, drift by two columns per row, two-cell crests, and index rejection",
            "duty-cycle discipline as the rejection discriminator",
            "drifting crest raster",
        ),
        c(
            "f26dia-roof-ridge-shingles",
            "Roof ridge shingles",
            "roof_ridge",
            """
            class ShingleError : public std::domain_error {
            public:
                explicit ShingleError(const std::string& message) : std::domain_error(message) {}
            };
            class ShingleRows {
            public:
                ShingleRows(std::size_t rows, std::size_t width);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class ShingleError : public std::domain_error {
            public:
                explicit ShingleError(const std::string& message) : std::domain_error(message) {}
            };
            class ShingleRows {
            public:
                ShingleRows(std::size_t rows, std::size_t width);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
            };
            """,
            """
            ShingleRows::ShingleRows(std::size_t rows, std::size_t width) : rows_(rows), width_(width) {
                if (rows == 0 || rows > 10) throw ShingleError("rows outside 1..10");
                if (width < 5 || width > 25) throw ShingleError("width outside 5..25");
            }
            std::size_t ShingleRows::rows() const { return rows_; }
            std::size_t ShingleRows::width() const { return width_; }
            std::size_t ShingleRows::height() const { return rows_; }
            std::vector<std::string> ShingleRows::lines() const {
                const char even_unit[4] = {'/', '_', '_', '\\\\'};
                const char odd_unit[4] = {'\\\\', '_', '_', '/'};
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    const char* unit = r % 2 == 0 ? even_unit : odd_unit;
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) row[x] = unit[x % 4];
                    out.push_back(row);
                }
                return out;
            }
            std::string ShingleRows::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            ShingleRows::ShingleRows(std::size_t rows, std::size_t width) : rows_(rows), width_(width) {
                if (rows == 0 || rows > 10) throw ShingleError("rows outside 1..10");
                if (width < 5 || width > 25) throw ShingleError("width outside 5..25");
            }
            std::size_t ShingleRows::rows() const { return rows_; }
            std::size_t ShingleRows::width() const { return width_; }
            std::size_t ShingleRows::height() const { return rows_; }
            std::vector<std::string> ShingleRows::lines() const {
                const char unit[4] = {'/', '_', '_', '\\\\'};
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) row[x] = unit[x % 4];
                    out.push_back(row);
                }
                return out;
            }
            std::string ShingleRows::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            ShingleRows roof(2, 9);
            if (roof.rows() != 2U) return 1;
            if (roof.width() != 9U) return 2;
            if (roof.height() != 2U) return 3;
            if (roof.lines() != std::vector<std::string>{"/__\\\\/__\\\\/", "\\\\__/\\\\__/\\\\"}) return 4;
            if (roof.render() != "/__\\\\/__\\\\/\\n\\\\__/\\\\__/\\\\") return 5;
            ShingleRows one(1, 5);
            if (one.lines() != std::vector<std::string>{"/__\\\\/"}) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { ShingleRows bad(0, 9); } catch (const ShingleError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ShingleRows bad(11, 9); } catch (const ShingleError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { ShingleRows bad(2, 4); } catch (const ShingleError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { ShingleRows bad(2, 26); } catch (const ShingleError&) { threw = true; }
            if (!threw) return 4;
            ShingleRows m(3, 7);
            if (m.lines() != std::vector<std::string>{"/__\\\\/__", "\\\\__/\\\\__", "/__\\\\/__"}) return 5;
            if (m.render() != "/__\\\\/__\\n\\\\__/\\\\__\\n/__\\\\/__") return 6;
            return 0;
            """,
            "alternating four-character shingle units with exact truncation",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and unalternated units",
            "row and width bounds, unit alternation, and truncation at non-multiple widths",
            "shingle alternation as the rejection discriminator",
            "alternating shingle raster",
        ),
        c(
            "f26dia-signal-kite-streamers",
            "Signal kite streamers",
            "signal_kite",
            """
            class StreamerError : public std::invalid_argument {
            public:
                explicit StreamerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StreamerFlags {
            public:
                StreamerFlags(std::size_t rows, std::size_t width, char tail);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class StreamerError : public std::invalid_argument {
            public:
                explicit StreamerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StreamerFlags {
            public:
                StreamerFlags(std::size_t rows, std::size_t width, char tail);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                char tail_;
            };
            """,
            """
            StreamerFlags::StreamerFlags(std::size_t rows, std::size_t width, char tail) : rows_(rows), width_(width), tail_(tail) {
                if (rows == 0 || rows > 12) throw StreamerError("rows outside 1..12");
                if (width < 3 || width > 20) throw StreamerError("width outside 3..20");
                if (tail < 33 || tail > 126) throw StreamerError("tail must be a printable non-space ASCII character");
                if (tail == '.') throw StreamerError("tail must not be the background character");
            }
            std::size_t StreamerFlags::rows() const { return rows_; }
            std::size_t StreamerFlags::width() const { return width_; }
            std::size_t StreamerFlags::height() const { return rows_; }
            std::vector<std::string> StreamerFlags::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) {
                        std::size_t band = 0;
                        while ((std::size_t(1) << (band + 1)) - 2 < x) ++band;
                        row[x] = (band + r) % 2 == 0 ? tail_ : '.';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string StreamerFlags::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            StreamerFlags::StreamerFlags(std::size_t rows, std::size_t width, char tail) : rows_(rows), width_(width), tail_(tail) {
                if (rows == 0 || rows > 12) throw StreamerError("rows outside 1..12");
                if (width < 3 || width > 20) throw StreamerError("width outside 3..20");
                if (tail < 33 || tail > 126) throw StreamerError("tail must be a printable non-space ASCII character");
                if (tail == '.') throw StreamerError("tail must not be the background character");
            }
            std::size_t StreamerFlags::rows() const { return rows_; }
            std::size_t StreamerFlags::width() const { return width_; }
            std::size_t StreamerFlags::height() const { return rows_; }
            std::vector<std::string> StreamerFlags::lines() const {
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) {
                        const std::size_t band = x / 2;
                        row[x] = (band + r) % 2 == 0 ? tail_ : '.';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string StreamerFlags::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            StreamerFlags flags(2, 7, '*');
            if (flags.rows() != 2U) return 1;
            if (flags.width() != 7U) return 2;
            if (flags.height() != 2U) return 3;
            if (flags.lines() != std::vector<std::string>{"*..****", ".**...."}) return 4;
            if (flags.render() != "*..****\\n.**....") return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { StreamerFlags bad(0, 7, '*'); } catch (const StreamerError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { StreamerFlags bad(13, 7, '*'); } catch (const StreamerError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { StreamerFlags bad(2, 2, '*'); } catch (const StreamerError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { StreamerFlags bad(2, 21, '*'); } catch (const StreamerError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { StreamerFlags bad(2, 7, ' '); } catch (const StreamerError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { StreamerFlags bad(2, 7, '.'); } catch (const StreamerError&) { threw = true; }
            if (!threw) return 6;
            StreamerFlags m(3, 12, '#');
            if (m.lines() != std::vector<std::string>{"#..####.....", ".##....#####", "#..####....."}) return 7;
            if (m.render() != "#..####.....\\n.##....#####\\n#..####.....") return 8;
            return 0;
            """,
            "exponential band boundaries with band-parity characters",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and linear bands",
            "row and width bounds, band boundaries at one-short-of-powers-of-two, and band parity per row",
            "exponential band derivation as the rejection discriminator",
            "exponential band raster",
            project_support=True,
        ),
        c(
            "f26dia-tent-pole-canopy-plan",
            "Tent pole canopy plan",
            "tent_pole",
            """
            class CanopyError : public std::invalid_argument {
            public:
                explicit CanopyError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CanopyPlan {
            public:
                explicit CanopyPlan(std::size_t span);
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t pole_height() const;
                std::size_t canvas_area() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class CanopyError : public std::invalid_argument {
            public:
                explicit CanopyError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CanopyPlan {
            public:
                explicit CanopyPlan(std::size_t span);
                std::size_t span() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t pole_height() const;
                std::size_t canvas_area() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t span_;
            };
            """,
            """
            CanopyPlan::CanopyPlan(std::size_t span) : span_(span) {
                if (span == 0 || span > 12) throw CanopyError("span outside 1..12");
            }
            std::size_t CanopyPlan::span() const { return span_; }
            std::size_t CanopyPlan::width() const { return 2 * span_ + 1; }
            std::size_t CanopyPlan::height() const { return span_ + 1; }
            std::size_t CanopyPlan::pole_height() const { return span_ + 1; }
            std::size_t CanopyPlan::canvas_area() const {
                std::size_t area = 0;
                for (const std::string& row : lines())
                    for (char cell : row)
                        if (cell != ' ') ++area;
                return area;
            }
            std::vector<std::string> CanopyPlan::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(height());
                for (std::size_t i = 0; i < span_; ++i) {
                    std::string row(w, ' ');
                    row[span_ - i] = '/';
                    row[span_ + i] = '\\\\';
                    row[span_] = '|';
                    out.push_back(row);
                }
                std::string base(w, '_');
                base[span_] = '|';
                out.push_back(base);
                return out;
            }
            std::string CanopyPlan::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            CanopyPlan::CanopyPlan(std::size_t span) : span_(span) {
                if (span == 0 || span > 12) throw CanopyError("span outside 1..12");
            }
            std::size_t CanopyPlan::span() const { return span_; }
            std::size_t CanopyPlan::width() const { return 2 * span_ + 1; }
            std::size_t CanopyPlan::height() const { return span_ + 1; }
            std::size_t CanopyPlan::pole_height() const { return span_ + 1; }
            std::size_t CanopyPlan::canvas_area() const {
                std::size_t area = 0;
                for (const std::string& row : lines())
                    for (char cell : row)
                        if (cell != ' ') ++area;
                return area;
            }
            std::vector<std::string> CanopyPlan::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(height());
                for (std::size_t i = 0; i < span_; ++i) {
                    std::string row(w, ' ');
                    row[span_ - i] = '/';
                    row[span_ + i] = '\\\\';
                    out.push_back(row);
                }
                std::string base(w, '_');
                base[span_] = '|';
                out.push_back(base);
                return out;
            }
            std::string CanopyPlan::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            CanopyPlan canopy(3);
            if (canopy.span() != 3U) return 1;
            if (canopy.width() != 7U) return 2;
            if (canopy.height() != 4U) return 3;
            if (canopy.pole_height() != 4U) return 4;
            if (canopy.canvas_area() != 14U) return 5;
            if (canopy.lines() != std::vector<std::string>{"   |   ", "  /|\\\\  ", " / | \\\\ ", "___|___"}) return 6;
            if (canopy.render() != "   |   \\n  /|\\\\  \\n / | \\\\ \\n___|___") return 7;
            CanopyPlan one(1);
            if (one.lines() != std::vector<std::string>{" | ", "_|_"}) return 8;
            if (one.canvas_area() != 4U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { CanopyPlan bad(0); } catch (const CanopyError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { CanopyPlan bad(13); } catch (const CanopyError&) { threw = true; }
            if (!threw) return 2;
            CanopyPlan m(4);
            if (m.width() != 9U) return 3;
            if (m.height() != 5U) return 4;
            if (m.canvas_area() != 19U) return 5;
            if (m.lines() != std::vector<std::string>{"    |    ", "   /|\\\\   ", "  / | \\\\  ", " /  |  \\\\ ", "____|____"}) return 6;
            if (m.render() != "    |    \\n   /|\\\\   \\n  / | \\\\  \\n /  |  \\\\ \\n____|____") return 7;
            return 0;
            """,
            "canopy outline with a persistent pole and an exact cell-count plan",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and missing poles",
            "span bounds, apex precedence, base row policy, and exact area formula",
            "plan/render agreement as the rejection discriminator",
            "canopy dimension planner",
            project_support=True,
        ),
        c(
            "f26dia-underpass-arch-gauge",
            "Underpass arch gauge",
            "underpass",
            """
            class ArchError : public std::domain_error {
            public:
                explicit ArchError(const std::string& message) : std::domain_error(message) {}
            };
            class ArchGauge {
            public:
                explicit ArchGauge(std::size_t half);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t edge_count() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class ArchError : public std::domain_error {
            public:
                explicit ArchError(const std::string& message) : std::domain_error(message) {}
            };
            class ArchGauge {
            public:
                explicit ArchGauge(std::size_t half);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t edge_count() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t half_;
            };
            """,
            """
            ArchGauge::ArchGauge(std::size_t half) : half_(half) {
                if (half < 2 || half > 10) throw ArchError("half outside 2..10");
            }
            std::size_t ArchGauge::half() const { return half_; }
            std::size_t ArchGauge::width() const { return 2 * half_ + 1; }
            std::size_t ArchGauge::height() const { return half_ + 1; }
            std::size_t ArchGauge::edge_count() const {
                std::size_t count = 0;
                for (const std::string& row : lines())
                    for (char cell : row)
                        if (cell == '#') ++count;
                return count;
            }
            std::vector<std::string> ArchGauge::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    if (i == 0) {
                        row[half_ - 1] = '#';
                        row[half_] = '#';
                        row[half_ + 1] = '#';
                    } else {
                        row[0] = '#';
                        row[w - 1] = '#';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string ArchGauge::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            ArchGauge::ArchGauge(std::size_t half) : half_(half) {
                if (half < 2 || half > 10) throw ArchError("half outside 2..10");
            }
            std::size_t ArchGauge::half() const { return half_; }
            std::size_t ArchGauge::width() const { return 2 * half_ + 1; }
            std::size_t ArchGauge::height() const { return half_ + 1; }
            std::size_t ArchGauge::edge_count() const {
                std::size_t count = 0;
                for (const std::string& row : lines())
                    for (char cell : row)
                        if (cell == '#') ++count;
                return count;
            }
            std::vector<std::string> ArchGauge::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    if (i == 0) {
                        row[half_ - 1] = '#';
                        row[half_] = '#';
                        row[half_ + 1] = '#';
                    } else {
                        row[1] = '#';
                        row[w - 2] = '#';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string ArchGauge::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            ArchGauge arch(3);
            if (arch.half() != 3U) return 1;
            if (arch.width() != 7U) return 2;
            if (arch.height() != 4U) return 3;
            if (arch.edge_count() != 9U) return 4;
            if (arch.lines() != std::vector<std::string>{"  ###  ", "#     #", "#     #", "#     #"}) return 5;
            if (arch.render() != "  ###  \\n#     #\\n#     #\\n#     #") return 6;
            ArchGauge two(2);
            if (two.lines() != std::vector<std::string>{" ### ", "#   #", "#   #"}) return 7;
            if (two.edge_count() != 7U) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { ArchGauge bad(1); } catch (const ArchError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ArchGauge bad(11); } catch (const ArchError&) { threw = true; }
            if (!threw) return 2;
            ArchGauge m(4);
            if (m.width() != 9U) return 3;
            if (m.height() != 5U) return 4;
            if (m.edge_count() != 11U) return 5;
            if (m.lines() != std::vector<std::string>{"   ###   ", "#       #", "#       #", "#       #", "#       #"}) return 6;
            if (m.render() != "   ###   \\n#       #\\n#       #\\n#       #\\n#       #") return 7;
            return 0;
            """,
            "arch cap plus vertical walls with an exact edge count",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and inset walls",
            "half bounds at 1 and 11, cap run of three, wall columns, and exact edge count",
            "wall placement as the rejection discriminator",
            "arch dimension planner",
        ),
        c(
            "f26dia-viaduct-span-ledger",
            "Viaduct span ledger",
            "viaduct_span",
            """
            class LedgerError : public std::invalid_argument {
            public:
                explicit LedgerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SpanLedger {
            public:
                SpanLedger(std::size_t spans, std::size_t rise);
                std::size_t spans() const;
                std::size_t rise() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t pier_count() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class LedgerError : public std::invalid_argument {
            public:
                explicit LedgerError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SpanLedger {
            public:
                SpanLedger(std::size_t spans, std::size_t rise);
                std::size_t spans() const;
                std::size_t rise() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t pier_count() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t spans_;
                std::size_t rise_;
            };
            """,
            """
            SpanLedger::SpanLedger(std::size_t spans, std::size_t rise) : spans_(spans), rise_(rise) {
                if (spans == 0 || spans > 6) throw LedgerError("spans outside 1..6");
                if (rise == 0 || rise > 6) throw LedgerError("rise outside 1..6");
            }
            std::size_t SpanLedger::spans() const { return spans_; }
            std::size_t SpanLedger::rise() const { return rise_; }
            std::size_t SpanLedger::width() const { return spans_ * (2 * rise_ + 1); }
            std::size_t SpanLedger::height() const { return rise_ + 1; }
            std::size_t SpanLedger::pier_count() const {
                std::size_t count = 0;
                for (const std::string& row : lines())
                    for (char cell : row)
                        if (cell == '#') ++count;
                return count;
            }
            std::vector<std::string> SpanLedger::lines() const {
                const std::size_t unit = 2 * rise_ + 1;
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    for (std::size_t x = 0; x < w; ++x) {
                        const std::size_t u = x % unit;
                        if (u == rise_ - i || u == rise_ + i) row[x] = '#';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string SpanLedger::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            SpanLedger::SpanLedger(std::size_t spans, std::size_t rise) : spans_(spans), rise_(rise) {
                if (spans == 0 || spans > 6) throw LedgerError("spans outside 1..6");
                if (rise == 0 || rise > 6) throw LedgerError("rise outside 1..6");
            }
            std::size_t SpanLedger::spans() const { return spans_; }
            std::size_t SpanLedger::rise() const { return rise_; }
            std::size_t SpanLedger::width() const { return spans_ * (2 * rise_ + 1); }
            std::size_t SpanLedger::height() const { return rise_ + 1; }
            std::size_t SpanLedger::pier_count() const {
                std::size_t count = 0;
                for (const std::string& row : lines())
                    for (char cell : row)
                        if (cell == '#') ++count;
                return count;
            }
            std::vector<std::string> SpanLedger::lines() const {
                const std::size_t unit = 2 * rise_ + 1;
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    for (std::size_t x = 0; x < w; ++x) {
                        const std::size_t u = x % unit;
                        if (u == i || (i > 0 && u == 2 * rise_ - i)) row[x] = '#';
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string SpanLedger::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            SpanLedger ledger(2, 2);
            if (ledger.spans() != 2U) return 1;
            if (ledger.rise() != 2U) return 2;
            if (ledger.width() != 10U) return 3;
            if (ledger.height() != 3U) return 4;
            if (ledger.pier_count() != 10U) return 5;
            if (ledger.lines() != std::vector<std::string>{"  #    #  ", " # #  # # ", "#   ##   #"}) return 6;
            if (ledger.render() != "  #    #  \\n # #  # # \\n#   ##   #") return 7;
            SpanLedger one(1, 1);
            if (one.lines() != std::vector<std::string>{" # ", "# #"}) return 8;
            if (one.pier_count() != 3U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { SpanLedger bad(0, 2); } catch (const LedgerError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { SpanLedger bad(7, 2); } catch (const LedgerError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { SpanLedger bad(2, 0); } catch (const LedgerError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { SpanLedger bad(2, 7); } catch (const LedgerError&) { threw = true; }
            if (!threw) return 4;
            SpanLedger m(3, 1);
            if (m.width() != 9U) return 5;
            if (m.height() != 2U) return 6;
            if (m.pier_count() != 9U) return 7;
            if (m.lines() != std::vector<std::string>{" #  #  # ", "# ## ## #"}) return 8;
            if (m.render() != " #  #  # \\n# ## ## #") return 9;
            return 0;
            """,
            "per-span local-column outline replication with an exact mark count",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and sagging spans",
            "span and rise bounds, local column mapping across span boundaries, and exact pier count",
            "local-column mapping as the rejection discriminator",
            "repeated arch planner",
        ),
        c(
            "f26dia-windmill-vane-chart",
            "Windmill vane chart",
            "windmill_vane",
            """
            class VaneError : public std::domain_error {
            public:
                explicit VaneError(const std::string& message) : std::domain_error(message) {}
            };
            class VaneChart {
            public:
                explicit VaneChart(std::size_t arm);
                std::size_t arm() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t spoke_count() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class VaneError : public std::domain_error {
            public:
                explicit VaneError(const std::string& message) : std::domain_error(message) {}
            };
            class VaneChart {
            public:
                explicit VaneChart(std::size_t arm);
                std::size_t arm() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t spoke_count() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t arm_;
            };
            """,
            """
            VaneChart::VaneChart(std::size_t arm) : arm_(arm) {
                if (arm == 0 || arm > 9) throw VaneError("arm outside 1..9");
            }
            std::size_t VaneChart::arm() const { return arm_; }
            std::size_t VaneChart::width() const { return 2 * arm_ + 1; }
            std::size_t VaneChart::height() const { return 2 * arm_ + 1; }
            std::size_t VaneChart::spoke_count() const { return 8; }
            std::vector<std::string> VaneChart::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(w);
                for (std::size_t r = 0; r < w; ++r) {
                    std::string row(w, ' ');
                    for (std::size_t c = 0; c < w; ++c) {
                        if (r == arm_ && c == arm_) {
                            row[c] = 'o';
                        } else if (r == c) {
                            row[c] = '\\\\';
                        } else if (r + c == w - 1) {
                            row[c] = '/';
                        } else if (c == arm_) {
                            row[c] = '|';
                        } else if (r == arm_) {
                            row[c] = '-';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string VaneChart::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            VaneChart::VaneChart(std::size_t arm) : arm_(arm) {
                if (arm == 0 || arm > 9) throw VaneError("arm outside 1..9");
            }
            std::size_t VaneChart::arm() const { return arm_; }
            std::size_t VaneChart::width() const { return 2 * arm_ + 1; }
            std::size_t VaneChart::height() const { return 2 * arm_ + 1; }
            std::size_t VaneChart::spoke_count() const { return 4; }
            std::vector<std::string> VaneChart::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(w);
                for (std::size_t r = 0; r < w; ++r) {
                    std::string row(w, ' ');
                    for (std::size_t c = 0; c < w; ++c) {
                        if (r == arm_ && c == arm_) {
                            row[c] = 'o';
                        } else if (c == arm_) {
                            row[c] = '|';
                        } else if (r == arm_) {
                            row[c] = '-';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string VaneChart::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            VaneChart chart(2);
            if (chart.arm() != 2U) return 1;
            if (chart.width() != 5U) return 2;
            if (chart.height() != 5U) return 3;
            if (chart.spoke_count() != 8U) return 4;
            if (chart.lines() != std::vector<std::string>{"\\\\ | /", " \\\\|/ ", "--o--", " /|\\\\ ", "/ | \\\\"}) return 5;
            if (chart.render() != "\\\\ | /\\n \\\\|/ \\n--o--\\n /|\\\\ \\n/ | \\\\") return 6;
            VaneChart one(1);
            if (one.lines() != std::vector<std::string>{"\\\\|/", "-o-", "/|\\\\"}) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { VaneChart bad(0); } catch (const VaneError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { VaneChart bad(10); } catch (const VaneError&) { threw = true; }
            if (!threw) return 2;
            VaneChart m(3);
            if (m.width() != 7U) return 3;
            if (m.lines() != std::vector<std::string>{"\\\\  |  /", " \\\\ | / ", "  \\\\|/  ", "---o---", "  /|\\\\  ", " / | \\\\ ", "/  |  \\\\"}) return 4;
            if (m.render() != "\\\\  |  /\\n \\\\ | / \\n  \\\\|/  \\n---o---\\n  /|\\\\  \\n / | \\\\ \\n/  |  \\\\") return 5;
            return 0;
            """,
            "four-family spoke precedence with a center cap",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and four-spoke charts",
            "arm bounds at 0 and 10, per-family characters, center precedence, and exact spoke count",
            "spoke completeness as the rejection discriminator",
            "spoke chart planner",
        ),
        c(
            "f26dia-xylophone-bar-layout",
            "Xylophone bar layout",
            "xylophone_bar",
            """
            class BarError : public std::invalid_argument {
            public:
                explicit BarError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BarLayout {
            public:
                explicit BarLayout(std::size_t bars);
                std::size_t bars() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t longest() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class BarError : public std::invalid_argument {
            public:
                explicit BarError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BarLayout {
            public:
                explicit BarLayout(std::size_t bars);
                std::size_t bars() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t longest() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t bars_;
            };
            """,
            """
            BarLayout::BarLayout(std::size_t bars) : bars_(bars) {
                if (bars < 2 || bars > 10) throw BarError("bars outside 2..10");
            }
            std::size_t BarLayout::bars() const { return bars_; }
            std::size_t BarLayout::width() const { return 4 * bars_ - 1; }
            std::size_t BarLayout::height() const { return bars_; }
            std::size_t BarLayout::longest() const { return bars_; }
            std::vector<std::string> BarLayout::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(bars_);
                for (std::size_t r = 0; r < bars_; ++r) {
                    std::string row(w, ' ');
                    for (std::size_t k = 0; k < bars_; ++k)
                        if (r < bars_ - k)
                            for (std::size_t c = 4 * k; c <= 4 * k + 2; ++c) row[c] = '#';
                    out.push_back(row);
                }
                return out;
            }
            std::string BarLayout::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BarLayout::BarLayout(std::size_t bars) : bars_(bars) {
                if (bars < 2 || bars > 10) throw BarError("bars outside 2..10");
            }
            std::size_t BarLayout::bars() const { return bars_; }
            std::size_t BarLayout::width() const { return 4 * bars_ - 1; }
            std::size_t BarLayout::height() const { return bars_; }
            std::size_t BarLayout::longest() const { return bars_; }
            std::vector<std::string> BarLayout::lines() const {
                const std::size_t w = width();
                std::vector<std::string> out;
                out.reserve(bars_);
                for (std::size_t r = 0; r < bars_; ++r) {
                    std::string row(w, ' ');
                    for (std::size_t k = 0; k < bars_; ++k)
                        if (r < k + 1)
                            for (std::size_t c = 4 * k; c <= 4 * k + 2; ++c) row[c] = '#';
                    out.push_back(row);
                }
                return out;
            }
            std::string BarLayout::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            BarLayout layout(3);
            if (layout.bars() != 3U) return 1;
            if (layout.width() != 11U) return 2;
            if (layout.height() != 3U) return 3;
            if (layout.longest() != 3U) return 4;
            if (layout.lines() != std::vector<std::string>{"### ### ###", "### ###    ", "###        "}) return 5;
            if (layout.render() != "### ### ###\\n### ###    \\n###        ") return 6;
            BarLayout two(2);
            if (two.lines() != std::vector<std::string>{"### ###", "###    "}) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { BarLayout bad(1); } catch (const BarError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { BarLayout bad(11); } catch (const BarError&) { threw = true; }
            if (!threw) return 2;
            BarLayout m(4);
            if (m.width() != 15U) return 3;
            if (m.height() != 4U) return 4;
            if (m.longest() != 4U) return 5;
            if (m.lines() != std::vector<std::string>{"### ### ### ###", "### ### ###    ", "### ###        ", "###            "}) return 6;
            if (m.render() != "### ### ### ###\\n### ### ###    \\n### ###        \\n###            ") return 7;
            return 0;
            """,
            "per-strip length schedule with exact separators",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and increasing lengths",
            "bar bounds at 1 and 11, strip column mapping, per-strip lengths, and separator cells",
            "length schedule as the rejection discriminator",
            "strip layout planner",
        ),
        c(
            "f26dia-zeppelin-mast-survey",
            "Zeppelin mast survey",
            "zeppelin_mast",
            """
            class MastError : public std::domain_error {
            public:
                explicit MastError(const std::string& message) : std::domain_error(message) {}
            };
            class MastSurvey {
            public:
                MastSurvey(std::size_t half, char guy);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t wire_length() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class MastError : public std::domain_error {
            public:
                explicit MastError(const std::string& message) : std::domain_error(message) {}
            };
            class MastSurvey {
            public:
                MastSurvey(std::size_t half, char guy);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::size_t wire_length() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t half_;
                char guy_;
            };
            """,
            """
            MastSurvey::MastSurvey(std::size_t half, char guy) : half_(half), guy_(guy) {
                if (half < 2 || half > 11) throw MastError("half outside 2..11");
                if (guy < 33 || guy > 126) throw MastError("guy must be a printable non-space ASCII character");
                if (guy == '|' || guy == '_') throw MastError("guy must not be a mast or ground character");
            }
            std::size_t MastSurvey::half() const { return half_; }
            std::size_t MastSurvey::width() const { return 2 * half_ + 1; }
            std::size_t MastSurvey::height() const { return half_ + 2; }
            std::size_t MastSurvey::wire_length() const { return 2 * half_; }
            std::vector<std::string> MastSurvey::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    if (i == h - 1) {
                        for (std::size_t c = 0; c < w; ++c) row[c] = '_';
                        row[half_] = '|';
                    } else {
                        row[half_] = '|';
                        if (i < half_) {
                            row[half_ - 1 - i] = guy_;
                            row[half_ + 1 + i] = guy_;
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string MastSurvey::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            MastSurvey::MastSurvey(std::size_t half, char guy) : half_(half), guy_(guy) {
                if (half < 2 || half > 11) throw MastError("half outside 2..11");
                if (guy < 33 || guy > 126) throw MastError("guy must be a printable non-space ASCII character");
                if (guy == '|' || guy == '_') throw MastError("guy must not be a mast or ground character");
            }
            std::size_t MastSurvey::half() const { return half_; }
            std::size_t MastSurvey::width() const { return 2 * half_ + 1; }
            std::size_t MastSurvey::height() const { return half_ + 2; }
            std::size_t MastSurvey::wire_length() const { return 2 * half_; }
            std::vector<std::string> MastSurvey::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    if (i == h - 1) {
                        for (std::size_t c = 0; c < w; ++c) row[c] = '_';
                        row[half_] = '|';
                    } else {
                        row[half_] = '|';
                        if (i < half_) {
                            row[i] = guy_;
                            row[w - 1 - i] = guy_;
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string MastSurvey::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            MastSurvey mast(3, '/');
            if (mast.half() != 3U) return 1;
            if (mast.width() != 7U) return 2;
            if (mast.height() != 5U) return 3;
            if (mast.wire_length() != 6U) return 4;
            if (mast.lines() != std::vector<std::string>{"  /|/  ", " / | / ", "/  |  /", "   |   ", "___|___"}) return 5;
            if (mast.render() != "  /|/  \\n / | / \\n/  |  /\\n   |   \\n___|___") return 6;
            MastSurvey two(2, '#');
            if (two.lines() != std::vector<std::string>{" #|# ", "# | #", "  |  ", "__|__"}) return 7;
            if (two.wire_length() != 4U) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { MastSurvey bad(1, '/'); } catch (const MastError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { MastSurvey bad(12, '/'); } catch (const MastError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { MastSurvey bad(3, ' '); } catch (const MastError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { MastSurvey bad(3, '|'); } catch (const MastError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { MastSurvey bad(3, '_'); } catch (const MastError&) { threw = true; }
            if (!threw) return 5;
            MastSurvey m(4, 'o');
            if (m.width() != 9U) return 6;
            if (m.height() != 6U) return 7;
            if (m.wire_length() != 8U) return 8;
            if (m.lines() != std::vector<std::string>{"   o|o   ", "  o | o  ", " o  |  o ", "o   |   o", "    |    ", "____|____"}) return 9;
            if (m.render() != "   o|o   \\n  o | o  \\n o  |  o \\no   |   o\\n    |    \\n____|____") return 10;
            return 0;
            """,
            "pole, diverging wires, and ground row with an exact wire count",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and converging wires",
            "half bounds, guy character restrictions, wire divergence, and ground row policy",
            "wire direction as the rejection discriminator",
            "mast survey planner",
            project_support=True,
        ),
        c(
            "f26dia-atlas-page-crossmark",
            "Atlas page crossmark",
            "atlas_page",
            """
            class CrossError : public std::invalid_argument {
            public:
                explicit CrossError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CrossMark {
            public:
                CrossMark(std::size_t half, char mark);
                std::size_t half() const;
                std::size_t size() const;
                std::size_t arms() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class CrossError : public std::invalid_argument {
            public:
                explicit CrossError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CrossMark {
            public:
                CrossMark(std::size_t half, char mark);
                std::size_t half() const;
                std::size_t size() const;
                std::size_t arms() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t half_;
                char mark_;
            };
            """,
            """
            CrossMark::CrossMark(std::size_t half, char mark) : half_(half), mark_(mark) {
                if (half == 0 || half > 12) throw CrossError("half outside 1..12");
                if (mark < 33 || mark > 126) throw CrossError("mark must be a printable non-space ASCII character");
            }
            std::size_t CrossMark::half() const { return half_; }
            std::size_t CrossMark::size() const { return 2 * half_ + 1; }
            std::size_t CrossMark::arms() const { return 4; }
            std::vector<std::string> CrossMark::lines() const {
                const std::size_t n = size();
                std::vector<std::string> out;
                out.reserve(n);
                for (std::size_t r = 0; r < n; ++r) {
                    std::string row(n, ' ');
                    for (std::size_t c = 0; c < n; ++c)
                        if (r == c || r + c == n - 1) row[c] = mark_;
                    out.push_back(row);
                }
                return out;
            }
            std::string CrossMark::line(std::size_t index) const {
                if (index >= size()) throw CrossError("line index out of range");
                return lines()[index];
            }
            std::string CrossMark::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            CrossMark::CrossMark(std::size_t half, char mark) : half_(half), mark_(mark) {
                if (half == 0 || half > 12) throw CrossError("half outside 1..12");
                if (mark < 33 || mark > 126) throw CrossError("mark must be a printable non-space ASCII character");
            }
            std::size_t CrossMark::half() const { return half_; }
            std::size_t CrossMark::size() const { return 2 * half_ + 1; }
            std::size_t CrossMark::arms() const { return 4; }
            std::vector<std::string> CrossMark::lines() const {
                const std::size_t n = size();
                std::vector<std::string> out;
                out.reserve(n);
                for (std::size_t r = 0; r < n; ++r) {
                    std::string row(n, ' ');
                    for (std::size_t c = 0; c < n; ++c)
                        if (r == c) row[c] = mark_;
                    out.push_back(row);
                }
                return out;
            }
            std::string CrossMark::line(std::size_t index) const {
                if (index >= size()) throw CrossError("line index out of range");
                return lines()[index];
            }
            std::string CrossMark::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            CrossMark cross(2, 'x');
            if (cross.half() != 2U) return 1;
            if (cross.size() != 5U) return 2;
            if (cross.arms() != 4U) return 3;
            if (cross.lines() != std::vector<std::string>{"x   x", " x x ", "  x  ", " x x ", "x   x"}) return 4;
            if (cross.line(2) != "  x  ") return 5;
            if (cross.render() != "x   x\\n x x \\n  x  \\n x x \\nx   x") return 6;
            bool threw = false;
            try { cross.line(5); } catch (const CrossError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { CrossMark bad(0, 'x'); } catch (const CrossError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { CrossMark bad(13, 'x'); } catch (const CrossError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { CrossMark bad(2, ' '); } catch (const CrossError&) { threw = true; }
            if (!threw) return 3;
            CrossMark m(3, 'o');
            if (m.size() != 7U) return 4;
            if (m.lines() != std::vector<std::string>{"o     o", " o   o ", "  o o  ", "   o   ", "  o o  ", " o   o ", "o     o"}) return 5;
            if (m.render() != "o     o\\n o   o \\n  o o  \\n   o   \\n  o o  \\n o   o \\no     o") return 6;
            return 0;
            """,
            "two-family diagonal cross with center collapse",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and single-diagonal crosses",
            "half bounds at 0 and 13, both diagonal families, center collapse, and index rejection",
            "diagonal-family completeness as the rejection discriminator",
            "diagonal cross renderer",
        ),
        c(
            "f26dia-bridge-cable-lattice",
            "Bridge cable lattice",
            "bridge_cable",
            """
            class CableError : public std::domain_error {
            public:
                explicit CableError(const std::string& message) : std::domain_error(message) {}
            };
            class CableLattice {
            public:
                CableLattice(std::size_t panels, std::size_t rise);
                std::size_t panels() const;
                std::size_t rise() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class CableError : public std::domain_error {
            public:
                explicit CableError(const std::string& message) : std::domain_error(message) {}
            };
            class CableLattice {
            public:
                CableLattice(std::size_t panels, std::size_t rise);
                std::size_t panels() const;
                std::size_t rise() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t panels_;
                std::size_t rise_;
            };
            """,
            """
            CableLattice::CableLattice(std::size_t panels, std::size_t rise) : panels_(panels), rise_(rise) {
                if (panels < 2 || panels > 8) throw CableError("panels outside 2..8");
                if (rise == 0 || rise > 6) throw CableError("rise outside 1..6");
            }
            std::size_t CableLattice::panels() const { return panels_; }
            std::size_t CableLattice::rise() const { return rise_; }
            std::size_t CableLattice::width() const { return panels_ * 2 * rise_ + 1; }
            std::size_t CableLattice::height() const { return rise_ + 1; }
            std::vector<std::string> CableLattice::lines() const {
                const std::size_t unit = 2 * rise_;
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t r = 0; r < h; ++r) {
                    std::string row(w, ' ');
                    for (std::size_t x = 0; x < w; ++x) {
                        if (x == 0 || x == w - 1) {
                            row[x] = '|';
                        } else {
                            const std::size_t u = x % unit;
                            if (u == rise_ - r) {
                                row[x] = '/';
                            } else if (u == rise_ + r) {
                                row[x] = '\\\\';
                            }
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string CableLattice::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            CableLattice::CableLattice(std::size_t panels, std::size_t rise) : panels_(panels), rise_(rise) {
                if (panels < 2 || panels > 8) throw CableError("panels outside 2..8");
                if (rise == 0 || rise > 6) throw CableError("rise outside 1..6");
            }
            std::size_t CableLattice::panels() const { return panels_; }
            std::size_t CableLattice::rise() const { return rise_; }
            std::size_t CableLattice::width() const { return panels_ * 2 * rise_ + 1; }
            std::size_t CableLattice::height() const { return rise_ + 1; }
            std::vector<std::string> CableLattice::lines() const {
                const std::size_t unit = 2 * rise_;
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t r = 0; r < h; ++r) {
                    std::string row(w, ' ');
                    for (std::size_t x = 0; x < w; ++x) {
                        if (x == 0 || x == w - 1) {
                            row[x] = '|';
                        } else {
                            const std::size_t u = x % unit;
                            if (u == r) {
                                row[x] = '/';
                            } else if (u == 2 * rise_ - r) {
                                row[x] = '\\\\';
                            }
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string CableLattice::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            CableLattice lattice(2, 2);
            if (lattice.panels() != 2U) return 1;
            if (lattice.rise() != 2U) return 2;
            if (lattice.width() != 9U) return 3;
            if (lattice.height() != 3U) return 4;
            if (lattice.lines() != std::vector<std::string>{"| /   / |", "|/ \\\\ / \\\\|", "|   /   |"}) return 5;
            if (lattice.render() != "| /   / |\\n|/ \\\\ / \\\\|\\n|   /   |") return 6;
            CableLattice three(3, 1);
            if (three.lines() != std::vector<std::string>{"|/ / /|", "| / / |"}) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { CableLattice bad(1, 2); } catch (const CableError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { CableLattice bad(9, 2); } catch (const CableError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { CableLattice bad(2, 0); } catch (const CableError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { CableLattice bad(2, 7); } catch (const CableError&) { threw = true; }
            if (!threw) return 4;
            CableLattice m(2, 3);
            if (m.width() != 13U) return 5;
            if (m.height() != 4U) return 6;
            if (m.lines() != std::vector<std::string>{"|  /     /  |", "| / \\\\   / \\\\ |", "|/   \\\\ /   \\\\|", "|     /     |"}) return 7;
            if (m.render() != "|  /     /  |\\n| / \\\\   / \\\\ |\\n|/   \\\\ /   \\\\|\\n|     /     |") return 8;
            return 0;
            """,
            "tower-bounded zigzag cables with local column mapping",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and sagging cables",
            "panel and rise bounds, tower columns, apex precedence, and cable continuity across panel boundaries",
            "cable direction as the rejection discriminator",
            "zigzag cable lattice renderer",
        ),
        c(
            "f26dia-compass-rose-needles",
            "Compass rose needles",
            "compass_rose",
            """
            class RoseError : public std::invalid_argument {
            public:
                explicit RoseError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RoseNeedles {
            public:
                explicit RoseNeedles(std::size_t arm);
                std::size_t arm() const;
                std::size_t size() const;
                std::size_t needle_count() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class RoseError : public std::invalid_argument {
            public:
                explicit RoseError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RoseNeedles {
            public:
                explicit RoseNeedles(std::size_t arm);
                std::size_t arm() const;
                std::size_t size() const;
                std::size_t needle_count() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t arm_;
            };
            """,
            """
            RoseNeedles::RoseNeedles(std::size_t arm) : arm_(arm) {
                if (arm < 2 || arm > 10) throw RoseError("arm outside 2..10");
            }
            std::size_t RoseNeedles::arm() const { return arm_; }
            std::size_t RoseNeedles::size() const { return 2 * arm_ + 1; }
            std::size_t RoseNeedles::needle_count() const { return 8; }
            std::vector<std::string> RoseNeedles::lines() const {
                const std::size_t n = size();
                const std::size_t reach = arm_ / 2;
                std::vector<std::string> out;
                out.reserve(n);
                for (std::size_t r = 0; r < n; ++r) {
                    std::string row(n, ' ');
                    for (std::size_t c = 0; c < n; ++c) {
                        const std::size_t dist = r < arm_ ? arm_ - r : r - arm_;
                        if (r == arm_ && c == arm_) {
                            row[c] = '+';
                        } else if (r == c && dist <= reach) {
                            row[c] = '\\\\';
                        } else if (r + c == n - 1 && dist <= reach) {
                            row[c] = '/';
                        } else if (c == arm_) {
                            row[c] = '|';
                        } else if (r == arm_) {
                            row[c] = '-';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string RoseNeedles::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            RoseNeedles::RoseNeedles(std::size_t arm) : arm_(arm) {
                if (arm < 2 || arm > 10) throw RoseError("arm outside 2..10");
            }
            std::size_t RoseNeedles::arm() const { return arm_; }
            std::size_t RoseNeedles::size() const { return 2 * arm_ + 1; }
            std::size_t RoseNeedles::needle_count() const { return 8; }
            std::vector<std::string> RoseNeedles::lines() const {
                const std::size_t n = size();
                std::vector<std::string> out;
                out.reserve(n);
                for (std::size_t r = 0; r < n; ++r) {
                    std::string row(n, ' ');
                    for (std::size_t c = 0; c < n; ++c) {
                        if (r == arm_ && c == arm_) {
                            row[c] = '+';
                        } else if (r == c) {
                            row[c] = '\\\\';
                        } else if (r + c == n - 1) {
                            row[c] = '/';
                        } else if (c == arm_) {
                            row[c] = '|';
                        } else if (r == arm_) {
                            row[c] = '-';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string RoseNeedles::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            RoseNeedles rose(4);
            if (rose.arm() != 4U) return 1;
            if (rose.size() != 9U) return 2;
            if (rose.needle_count() != 8U) return 3;
            if (rose.lines() != std::vector<std::string>{"    |    ", "    |    ", "  \\\\ | /  ", "   \\\\|/   ", "----+----", "   /|\\\\   ", "  / | \\\\  ", "    |    ", "    |    "}) return 4;
            if (rose.render() != "    |    \\n    |    \\n  \\\\ | /  \\n   \\\\|/   \\n----+----\\n   /|\\\\   \\n  / | \\\\  \\n    |    \\n    |    ") return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { RoseNeedles bad(1); } catch (const RoseError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RoseNeedles bad(11); } catch (const RoseError&) { threw = true; }
            if (!threw) return 2;
            RoseNeedles m(3);
            if (m.size() != 7U) return 3;
            if (m.lines() != std::vector<std::string>{"   |   ", "   |   ", "  \\\\|/  ", "---+---", "  /|\\\\  ", "   |   ", "   |   "}) return 4;
            if (m.render() != "   |   \\n   |   \\n  \\\\|/  \\n---+---\\n  /|\\\\  \\n   |   \\n   |   ") return 5;
            RoseNeedles two(2);
            if (two.lines() != std::vector<std::string>{"  |  ", " \\\\|/ ", "--+--", " /|\\\\ ", "  |  "}) return 6;
            return 0;
            """,
            "full cardinal needles with length-limited diagonal needles",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and full-length diagonals",
            "arm bounds at 1 and 11, diagonal length limit at exactly half the arm, center precedence, and exact needle count",
            "needle length policy as the rejection discriminator",
            "needle chart renderer",
            project_support=True,
        ),
        c(
            "f26dia-drydock-keel-angle",
            "Drydock keel angle",
            "drydock_keel",
            """
            class KeelError : public std::domain_error {
            public:
                explicit KeelError(const std::string& message) : std::domain_error(message) {}
            };
            class KeelAngle {
            public:
                KeelAngle(std::size_t half, char hull);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            };
            """,
            """
            class KeelError : public std::domain_error {
            public:
                explicit KeelError(const std::string& message) : std::domain_error(message) {}
            };
            class KeelAngle {
            public:
                KeelAngle(std::size_t half, char hull);
                std::size_t half() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string line(std::size_t index) const;
                std::string render() const;
            private:
                std::size_t half_;
                char hull_;
            };
            """,
            """
            KeelAngle::KeelAngle(std::size_t half, char hull) : half_(half), hull_(hull) {
                if (half < 2 || half > 12) throw KeelError("half outside 2..12");
                if (hull < 33 || hull > 126) throw KeelError("hull must be a printable non-space ASCII character");
            }
            std::size_t KeelAngle::half() const { return half_; }
            std::size_t KeelAngle::width() const { return 2 * half_ + 2; }
            std::size_t KeelAngle::height() const { return half_ + 1; }
            std::vector<std::string> KeelAngle::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    row[i] = hull_;
                    row[i + 1] = hull_;
                    row[w - 2 - i] = hull_;
                    row[w - 1 - i] = hull_;
                    out.push_back(row);
                }
                return out;
            }
            std::string KeelAngle::line(std::size_t index) const {
                if (index >= height()) throw KeelError("line index out of range");
                return lines()[index];
            }
            std::string KeelAngle::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            KeelAngle::KeelAngle(std::size_t half, char hull) : half_(half), hull_(hull) {
                if (half < 2 || half > 12) throw KeelError("half outside 2..12");
                if (hull < 33 || hull > 126) throw KeelError("hull must be a printable non-space ASCII character");
            }
            std::size_t KeelAngle::half() const { return half_; }
            std::size_t KeelAngle::width() const { return 2 * half_ + 2; }
            std::size_t KeelAngle::height() const { return half_ + 1; }
            std::vector<std::string> KeelAngle::lines() const {
                const std::size_t w = width();
                const std::size_t h = height();
                std::vector<std::string> out;
                out.reserve(h);
                for (std::size_t i = 0; i < h; ++i) {
                    std::string row(w, ' ');
                    row[i] = hull_;
                    row[w - 1 - i] = hull_;
                    out.push_back(row);
                }
                return out;
            }
            std::string KeelAngle::line(std::size_t index) const {
                if (index >= height()) throw KeelError("line index out of range");
                return lines()[index];
            }
            std::string KeelAngle::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            KeelAngle keel(2, '#');
            if (keel.half() != 2U) return 1;
            if (keel.width() != 6U) return 2;
            if (keel.height() != 3U) return 3;
            if (keel.lines() != std::vector<std::string>{"##  ##", " #### ", "  ##  "}) return 4;
            if (keel.line(2) != "  ##  ") return 5;
            if (keel.render() != "##  ##\\n #### \\n  ##  ") return 6;
            bool threw = false;
            try { keel.line(3); } catch (const KeelError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { KeelAngle bad(1, '#'); } catch (const KeelError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { KeelAngle bad(13, '#'); } catch (const KeelError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { KeelAngle bad(2, ' '); } catch (const KeelError&) { threw = true; }
            if (!threw) return 3;
            KeelAngle m(3, 'o');
            if (m.width() != 8U) return 4;
            if (m.lines() != std::vector<std::string>{"oo    oo", " oo  oo ", "  oooo  ", "   oo   "}) return 5;
            if (m.render() != "oo    oo\\n oo  oo \\n  oooo  \\n   oo   ") return 6;
            KeelAngle maxed(4, '+');
            if (maxed.width() != 10U) return 7;
            if (maxed.lines() != std::vector<std::string>{"++      ++", " ++    ++ ", "  ++  ++  ", "   ++++   ", "    ++    "}) return 8;
            return 0;
            """,
            "double-thick converging walls with a bottom merge",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and single-thick walls",
            "half bounds at 1 and 13, wall thickness on every row, bottom merge width, and index rejection",
            "wall thickness as the rejection discriminator",
            "thick keel renderer",
        ),
        c(
            "f26dia-aviary-perch-diagonals",
            "Aviary perch diagonals",
            "aviary_perch",
            """
            class PerchError : public std::invalid_argument {
            public:
                explicit PerchError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PerchDiagonals {
            public:
                PerchDiagonals(std::size_t rows, std::size_t width, char perch);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            };
            """,
            """
            class PerchError : public std::invalid_argument {
            public:
                explicit PerchError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PerchDiagonals {
            public:
                PerchDiagonals(std::size_t rows, std::size_t width, char perch);
                std::size_t rows() const;
                std::size_t width() const;
                std::size_t height() const;
                std::vector<std::string> lines() const;
                std::string render() const;
            private:
                std::size_t rows_;
                std::size_t width_;
                char perch_;
            };
            """,
            """
            PerchDiagonals::PerchDiagonals(std::size_t rows, std::size_t width, char perch) : rows_(rows), width_(width), perch_(perch) {
                if (rows < 2 || rows > 10) throw PerchError("rows outside 2..10");
                if (width < 4 || width > 20) throw PerchError("width outside 4..20");
                if (perch < 33 || perch > 126) throw PerchError("perch must be a printable non-space ASCII character");
                if (perch == '-') throw PerchError("perch must not be the bar character");
            }
            std::size_t PerchDiagonals::rows() const { return rows_; }
            std::size_t PerchDiagonals::width() const { return width_; }
            std::size_t PerchDiagonals::height() const { return rows_; }
            std::vector<std::string> PerchDiagonals::lines() const {
                const std::size_t bar = rows_ / 2;
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) {
                        if ((x + r) % 5 == 0) {
                            row[x] = perch_;
                        } else if (r == bar) {
                            row[x] = '-';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string PerchDiagonals::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PerchDiagonals::PerchDiagonals(std::size_t rows, std::size_t width, char perch) : rows_(rows), width_(width), perch_(perch) {
                if (rows < 2 || rows > 10) throw PerchError("rows outside 2..10");
                if (width < 4 || width > 20) throw PerchError("width outside 4..20");
                if (perch < 33 || perch > 126) throw PerchError("perch must be a printable non-space ASCII character");
                if (perch == '-') throw PerchError("perch must not be the bar character");
            }
            std::size_t PerchDiagonals::rows() const { return rows_; }
            std::size_t PerchDiagonals::width() const { return width_; }
            std::size_t PerchDiagonals::height() const { return rows_; }
            std::vector<std::string> PerchDiagonals::lines() const {
                const std::size_t bar = rows_ / 2;
                std::vector<std::string> out;
                out.reserve(rows_);
                for (std::size_t r = 0; r < rows_; ++r) {
                    std::string row(width_, ' ');
                    for (std::size_t x = 0; x < width_; ++x) {
                        if ((x + 2 * r) % 5 == 0) {
                            row[x] = perch_;
                        } else if (r == bar) {
                            row[x] = '-';
                        }
                    }
                    out.push_back(row);
                }
                return out;
            }
            std::string PerchDiagonals::render() const {
                std::string result;
                const std::vector<std::string> rows = lines();
                for (std::size_t i = 0; i < rows.size(); ++i) {
                    if (i != 0) result += '\\n';
                    result += rows[i];
                }
                return result;
            }
            """,
            """
            PerchDiagonals perches(3, 7, '/');
            if (perches.rows() != 3U) return 1;
            if (perches.width() != 7U) return 2;
            if (perches.height() != 3U) return 3;
            if (perches.lines() != std::vector<std::string>{"/    / ", "----/--", "   /   "}) return 4;
            if (perches.render() != "/    / \\n----/--\\n   /   ") return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { PerchDiagonals bad(1, 7, '/'); } catch (const PerchError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PerchDiagonals bad(11, 7, '/'); } catch (const PerchError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PerchDiagonals bad(2, 3, '/'); } catch (const PerchError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { PerchDiagonals bad(2, 21, '/'); } catch (const PerchError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { PerchDiagonals bad(2, 7, ' '); } catch (const PerchError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { PerchDiagonals bad(2, 7, '-'); } catch (const PerchError&) { threw = true; }
            if (!threw) return 6;
            PerchDiagonals m(4, 8, '#');
            if (m.lines() != std::vector<std::string>{"#    #  ", "    #   ", "---#----", "  #    #"}) return 7;
            if (m.render() != "#    #  \\n    #   \\n---#----\\n  #    #") return 8;
            return 0;
            """,
            "drifting perch marks with a middle-row bar policy",
            "regex engines or third-party graphics libraries, letter-sequence pyramids, and wrong-drift perches",
            "row and width bounds, perch drift, bar only on the exact middle row, and perch precedence over the bar",
            "drift and bar policy as the rejection discriminator",
            "drifting perch raster",
        ),
    )
    return rows


TASKS = cases()

CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-dia-seven-dimension-artifacts-v1"


def _repo_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(REPO_ROOT.resolve(strict=False)).as_posix()
    except ValueError:
        return path.as_posix()


def _generator_revision() -> str:
    return _file_hash(GENERATOR_PATH)


def _header(spec: TaskSpec) -> str:
    return COMMON_HEADER + f"\nnamespace {spec.namespace} {{\n{spec.declarations}}}\n"


def _source(spec: TaskSpec, body: str) -> str:
    return f'#include "{spec.task_id}.h"\n' + COMMON_SOURCE + f"\nnamespace {spec.namespace} {{\n{body}}}\n"


def _starter_source(spec: TaskSpec) -> str:
    return _source(spec, spec.starter)


def _negative_source(spec: TaskSpec) -> str:
    return _source(spec, spec.negative)


_TEST_INCLUDES = """#include "{task_id}.h"

#include <cstddef>
#include <string>
#include <vector>
"""


def _visible_test(spec: TaskSpec) -> str:
    return _TEST_INCLUDES.format(task_id=spec.task_id) + f"""
using namespace {spec.namespace};

int main() {{
{spec.visible_test}}}
"""


def _hidden_test(spec: TaskSpec) -> str:
    return _TEST_INCLUDES.format(task_id=spec.task_id) + f"""
using namespace {spec.namespace};

int main() {{
{spec.private_test}}}
"""


def _introduction(spec: TaskSpec) -> str:
    return f"""# {spec.title}

Implement a clean-room C++17 ASCII-shape rendering component for a local
diamond skill analog. This root is independently authored for SFT
task-family construction and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep ASCII-space grid geometry exact: width, height, and line counts
derived from validated size arguments; symmetric rows mirrored exactly; center
and edge characters placed at computed columns; interior padding always the
ASCII space; typed-error rejection of invalid sizes and characters; and
byte-identical deterministic rendering for this API shape: {spec.api_shape}.

Do not copy or refer to any benchmark exercise. Do not use {spec.forbidden}.
Keep the implementation offline, standard-library only, and directly owned by
this task rather than a cross-task dispatcher.
"""


def _cmake(spec: TaskSpec) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({spec.task_id} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

function(strict_target target source test_source)
  add_executable(${{target}} ${{source}} ${{test_source}})
  target_include_directories(${{target}} PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
  target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
endfunction()

strict_target(task_visible {spec.task_id}.cpp visible_test.cpp)
strict_target(task_hidden {spec.task_id}.cpp .meta/private_test.cpp)

enable_testing()
add_test(NAME {spec.task_id}-visible COMMAND task_visible)
add_test(NAME {spec.task_id}-private COMMAND task_hidden)
"""


def _config(spec: TaskSpec) -> str:
    return (
        json.dumps(
            {
                "authors": ["w8-biayn"],
                "blurb": spec.improvement_reason,
                "files": {
                    "solution": [f"{spec.task_id}.h", f"{spec.task_id}.cpp"],
                    "test": ["visible_test.cpp", ".meta/private_test.cpp"],
                    "example": [".meta/example.h", ".meta/example.cpp"],
                },
                "source": "w8-biayn clean-room fixed26 diamond analog curriculum",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _provenance(spec: TaskSpec) -> str:
    return (
        json.dumps(
            {
                "schema_version": "aider-local-task-provenance-v2",
                "task_id": spec.task_id,
                "family_id": FAMILY_ID,
                "batch_id": BATCH_ID,
                "lineage": {"relation": "new-root", "parent": None},
                "authoring_origin": "repository-authored clean-room deterministic generator",
                "license_result": "repository-project-terms",
                "owner": OWNER_ID,
                "source_document": _repo_path(CURRICULUM),
                "source_task_id": spec.task_id,
                "task_spec_revision": "v2",
                "benchmark_holdout_separation": "required semantic and exact screens",
                "local_status": "pending_execution",
                "dataset_handoff": "not_requested",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _tests_toml(spec: TaskSpec) -> str:
    return f"""[visible]
description = "{spec.title}: public valid-case behavior"

[hidden]
description = "{spec.title}: geometry derivation, symmetry, center and edge placement, exact whitespace, invalid inputs, boundary sizes, and wrong-substitute rejection"

[negative]
description = "compiled false substitute: {spec.forbidden}"
"""


def _support_context(spec: TaskSpec) -> str:
    return f"""# Private Project Context

This private support file binds `{spec.task_id}` to the fixed26 analog support
surface. It is intentionally not included in prompts or SFT rows.

- batch_id: {BATCH_ID}
- family_id: {FAMILY_ID}
- root_id: {spec.task_id}
- support_kind: project-context-private
"""


def _render(spec: TaskSpec, *, variant: str = "base") -> dict[str, str]:
    files = {
        ".docs/introduction.md": _introduction(spec),
        ".docs/instructions.md": _instructions(spec),
        ".meta/config.json": _config(spec),
        ".meta/provenance.json": _provenance(spec),
        ".meta/tests.toml": _tests_toml(spec),
        ".meta/example.h": _header(spec),
        ".meta/example.cpp": _source(spec, spec.implementation),
        ".meta/private_test.cpp": _hidden_test(spec),
        ".meta/negative.cpp": _negative_source(spec),
        f"{spec.task_id}.h": _header(spec),
        f"{spec.task_id}.cpp": _starter_source(spec),
        "visible_test.cpp": _visible_test(spec),
        "CMakeLists.txt": _cmake(spec),
    }
    if spec.project_support:
        files[".meta/support/context.md"] = _support_context(spec)
    if variant != "base":
        files[".control.json"] = json.dumps({"control": variant, "source": spec.task_id}, sort_keys=True) + "\n"
    return files


def _inventory_roots(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not root.is_dir():
        return result
    for config in root.rglob(".meta/config.json"):
        if ".state" in config.parts:
            continue
        task_root = config.parent.parent
        inventory_id = task_root.name
        if inventory_id in result:
            continue
        result[inventory_id] = task_root
    return result


def _inventory_hash(inventory: Mapping[str, Path]) -> str:
    lines = "".join(f"{task_id}:{path.as_posix()}\n" for task_id, path in sorted(inventory.items()))
    return _sha256(lines.encode())


def _validate_output(out: Path, *, testing: bool = False) -> None:
    if out.is_symlink():
        _fail("unsafe_path", f"symlink output:{out}")
    resolved = out.resolve(strict=False)
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("unsafe_path", f"existing generated tree output:{out}")
    if not testing and resolved != DEFAULT_OUT.resolve(strict=False):
        _fail("unsafe_path", f"expected exact task family root:{DEFAULT_OUT}")


def _screen_ids(rendered: Mapping[str, Mapping[str, str]], out: Path) -> dict[str, object]:
    inventories = {
        "legacy": _inventory_roots(LEGACY_ROOT),
        "reverify": _inventory_roots(REVERIFY_ROOT),
        "expansion": _inventory_roots(EXPANSION_ROOT),
    }
    current_ids = set(rendered)
    for name, inventory in inventories.items():
        collisions = current_ids & set(inventory)
        if name == "expansion":
            allowed: set[str] = set()
            for task_id in collisions:
                provenance = inventory[task_id] / ".meta/provenance.json"
                if provenance.is_file():
                    try:
                        if json.loads(provenance.read_text()).get("owner") == OWNER_ID:
                            allowed.add(task_id)
                    except json.JSONDecodeError:
                        pass
            collisions -= allowed
        if collisions:
            _fail("duplicate_task", f"{name}:{sorted(collisions)}")
    return {
        name: {"count": len(inventory), "sorted_root_inventory_sha256": _inventory_hash(inventory)}
        for name, inventory in inventories.items()
    }


def _write_manifest(out: Path, name: str, payload: object) -> None:
    _write_json(out / ".state/manifests" / name, payload, overwrite=True)


CONTROL_MUTATION_NOTE = (
    "Each control applies its named mutation under the evaluator's normalization model: "
    "the production screen normalizes task IDs, numeric literals, and string literals "
    "away, so every control genuinely changes emitted files, remains internally "
    "coherent and buildable, and is rejected as a near-clone by that exact screen."
)


def _apply_replacements(text: str, replacements: Sequence[tuple[str, str]], *, context: str) -> str:
    for old, new in replacements:
        if old not in text:
            _fail("control_mutation_drift", f"{context}:{old[:70]}")
        text = text.replace(old, new)
    return text


def _mutate_control_files(spec: TaskSpec, name: str, files: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    if spec.task_id != "f26dia-anvil-forge-hourglass":
        _fail("control_mutation_drift", f"controls are bound to f26dia-anvil-forge-hourglass, got {spec.task_id}")
    if name == "domain-identifier-renamed":
        renamed_id = "f26dia-smithy-forge-hourglass"
        mutated: dict[str, str] = {}
        for relative, content in sorted(files.items()):
            mutated[relative.replace(spec.task_id, renamed_id)] = content.replace(spec.task_id, renamed_id)
        changed = sorted(relative for relative, content in mutated.items() if files.get(relative) != content)
        return mutated, changed
    if name == "constants-or-policy-only":
        mutated = dict(files)
        mutated[".meta/private_test.cpp"] = _apply_replacements(
            mutated[".meta/private_test.cpp"],
            (
                ("try { HourglassOutline bad(13, '#'); } catch (const ForgeError&) { threw = true; }", "try { HourglassOutline bad(14, '#'); } catch (const ForgeError&) { threw = true; }"),
                ("HourglassOutline maxed(12, '+');", "HourglassOutline maxed(12, '=');"),
                (
                    'if (maxed.line(12) != std::string(12, \' \') + "+" + std::string(12, \' \')) return 10;',
                    'if (maxed.line(12) != std::string(12, \' \') + "=" + std::string(12, \' \')) return 10;',
                ),
                (
                    'if (maxed.line(0) != "+" + std::string(23, \' \') + "+") return 11;',
                    'if (maxed.line(0) != "=" + std::string(23, \' \') + "=") return 11;',
                ),
            ),
            context="constants-or-policy-only:private",
        )
        return mutated, [".meta/private_test.cpp"]
    if name == "opposite-end-selection":
        mutated = dict(files)
        mutated["visible_test.cpp"] = _apply_replacements(
            mutated["visible_test.cpp"],
            (
                ("HourglassOutline h(3, '#');", "HourglassOutline h(4, '@');"),
                ("if (h.half() != 3U) return 1;", "if (h.half() != 4U) return 1;"),
                ("if (h.width() != 7U) return 2;", "if (h.width() != 9U) return 2;"),
                ("if (h.height() != 7U) return 3;", "if (h.height() != 9U) return 3;"),
                (
                    'if (h.lines() != std::vector<std::string>{"#     #", " #   # ", "  # #  ", "   #   ", "  # #  ", " #   # ", "#     #"}) return 4;',
                    'if (h.lines() != std::vector<std::string>{"@       @", " @     @ ", "  @   @  ", "   @ @   ", "    @    ", "   @ @   ", "  @   @  ", " @     @ ", "@       @"}) return 4;',
                ),
                ('if (h.line(0) != "#     #") return 5;', 'if (h.line(0) != "@       @") return 5;'),
                (
                    'if (h.render() != "#     #\\n #   # \\n  # #  \\n   #   \\n  # #  \\n #   # \\n#     #") return 6;',
                    'if (h.render() != "@       @\\n @     @ \\n  @   @  \\n   @ @   \\n    @    \\n   @ @   \\n  @   @  \\n @     @ \\n@       @") return 6;',
                ),
                ("HourglassOutline one(1, '*');", "HourglassOutline one(2, '%');"),
                (
                    'if (one.lines() != std::vector<std::string>{"* *", " * ", "* *"}) return 7;',
                    'if (one.lines() != std::vector<std::string>{"%   %", " % % ", "  %  ", " % % ", "%   %"}) return 7;',
                ),
                (
                    'if (one.render() != "* *\\n * \\n* *") return 8;',
                    'if (one.render() != "%   %\\n % % \\n  %  \\n % % \\n%   %") return 8;',
                ),
                (
                    "try { one.line(3); } catch (const ForgeError&) { threw = true; }",
                    "try { one.line(5); } catch (const ForgeError&) { threw = true; }",
                ),
            ),
            context="opposite-end-selection:visible",
        )
        mutated[".meta/private_test.cpp"] = _apply_replacements(
            mutated[".meta/private_test.cpp"],
            (
                ("HourglassOutline m(2, 'o');", "HourglassOutline m(3, 'o');"),
                ("if (m.width() != 5U) return 5;", "if (m.width() != 7U) return 5;"),
                (
                    'if (m.lines() != std::vector<std::string>{"o   o", " o o ", "  o  ", " o o ", "o   o"}) return 6;',
                    'if (m.lines() != std::vector<std::string>{"o     o", " o   o ", "  o o  ", "   o   ", "  o o  ", " o   o ", "o     o"}) return 6;',
                ),
                (
                    'if (m.render() != "o   o\\n o o \\n  o  \\n o o \\no   o") return 7;',
                    'if (m.render() != "o     o\\n o   o \\n  o o  \\n   o   \\n  o o  \\n o   o \\no     o") return 7;',
                ),
            ),
            context="opposite-end-selection:private",
        )
        return mutated, ["visible_test.cpp", ".meta/private_test.cpp"]
    _fail("unknown_control", name)
    raise AssertionError("unreachable")


def _control_files(spec: TaskSpec, name: str) -> tuple[dict[str, str], list[str]]:
    mutated, changed = _mutate_control_files(spec, name, _render(spec))
    if not changed:
        _fail("control_mutation_noop", name)
    descriptor = {
        "control": name,
        "source": spec.task_id,
        "mutation_note": CONTROL_MUTATION_NOTE,
        "changed_files": changed,
    }
    mutated[".control.json"] = json.dumps(descriptor, indent=2, sort_keys=True) + "\n"
    return mutated, changed


def _materialize_control(out: Path, spec: TaskSpec, name: str) -> dict[str, object]:
    root = out / ".state/controls" / name
    if root.exists():
        shutil.rmtree(root)
    files, changed = _control_files(spec, name)
    for relative, content in sorted(files.items()):
        _write(root / relative, content, overwrite=True)
    return {"name": name, "source_task_id": spec.task_id, "changed": True, "changed_files": changed}


def build(out: Path = DEFAULT_OUT, *, force: bool = False, testing: bool = False) -> dict[str, object]:
    _validate_output(out, testing=testing)
    rendered = {spec.task_id: _render(spec) for spec in TASKS}
    if len(rendered) != EXPECTED_ROOTS:
        _fail("binding_root_count_failed", str(len(rendered)))
    inventories = _screen_ids(rendered, out)
    if out.exists():
        foreign: list[str] = []
        for config in out.glob("*/.meta/config.json"):
            provenance = config.parent / "provenance.json"
            owner = json.loads(provenance.read_text()).get("owner") if provenance.is_file() else None
            if owner != OWNER_ID:
                foreign.append(config.parent.parent.name)
        if foreign:
            _fail("generator_output_drift", f"foreign roots:{sorted(foreign)}")
        if not force:
            raise FileExistsError(f"{out} exists; pass --force")
        state = out / ".state"
        prior_hash = _tree_hash(out)
        for child in out.iterdir():
            if child.name != ".state" and child.is_dir():
                shutil.rmtree(child)
        if state.is_dir():
            stale = state / "invalidated"
            stale.mkdir(parents=True, exist_ok=True)
            _write_json(
                stale / "latest.json",
                {
                    "reason": "owner regeneration invalidates exact-tree receipts",
                    "tree_hash_before": prior_hash,
                },
                overwrite=True,
            )
            for receipt in (state / "receipts").glob("*.json") if (state / "receipts").is_dir() else ():
                receipt.unlink()
    out.mkdir(parents=True, exist_ok=True)
    for task_id, files in sorted(rendered.items()):
        root = out / task_id
        for relative, content in sorted(files.items()):
            _write(root / relative, content, overwrite=True)
    controls = [_materialize_control(out, TASKS[0], name) for name in CONTROL_NAMES]
    raw = [
        {
            "task_id": spec.task_id,
            "bucket": "failed-fixed26-analog",
            "family": "diamond",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "diamond",
        "target_count": EXPECTED_ROOTS,
        "materialized_count": len(raw),
        "task_family_root": _repo_path(out),
        "spec_document_path": _repo_path(CURRICULUM),
        "owner": OWNER_ID,
        "focused_test": FOCUSED_TEST,
        "creation_prompt": CREATION_PROMPT,
        "implementation_prompt": IMPLEMENTATION_PROMPT,
        "root_ids": [spec.task_id for spec in TASKS],
        "project_context_support_count": sum(spec.project_support for spec in TASKS),
        "project_context_support_note": "The source spec names 10 project-context support roots; this materializer emits private support only for those 10.",
        "failed_roots": [],
        "deferred_roots": [],
        "deferred_backlog": "Remaining failed-family analogs, second-try-only variants, multi-file API discipline, repair-support batches, and filtered current anchors.",
        "non_claims": [
            "not_jsonl",
            "not_token_mask_evidence",
            "not_export",
            "not_training_run",
            "not_benchmark_uplift",
        ],
        "status": "generated_pending_local_verification",
    }
    _write_manifest(out, "raw-proposals.json", {"schema_version": 1, "proposals": raw})
    _write_manifest(out, "generated-candidates.json", {"schema_version": 1, "candidates": raw})
    _write_manifest(out, "selected-candidates.json", {"schema_version": 1, "selected": [row["task_id"] for row in raw]})
    _write_manifest(out, "rejected-candidates.json", {"schema_version": 1, "rejected": []})
    _write_manifest(out, "source-inventories.json", inventories)
    _write_manifest(out, "batch-ledger.json", ledger)
    return {"root_count": len(rendered), "tree_hash": _tree_hash(out), "controls": controls, "ledger_path": _repo_path(out / ".state/manifests/batch-ledger.json")}


def _role_and_prompt_check(root: Path, spec: TaskSpec) -> dict[str, object]:
    config = json.loads(_read(root, ".meta/config.json"))
    files = config.get("files", {})
    expected_solution = [f"{spec.task_id}.h", f"{spec.task_id}.cpp"]
    expected_tests = ["visible_test.cpp", ".meta/private_test.cpp"]
    expected_examples = [".meta/example.h", ".meta/example.cpp"]
    if files.get("solution") != expected_solution or files.get("test") != expected_tests or files.get("example") != expected_examples:
        _fail("target_reference_mismatch", spec.task_id)
    for path in [*expected_solution, *expected_tests, *expected_examples]:
        if not _safe_relative(path) or not (root / path).is_file():
            _fail("unsafe_path", f"{spec.task_id}:{path}")
    prompt = build_prompt(load_task(root))
    if any(marker in prompt for marker in PRIVATE_MARKERS):
        _fail("prompt_contract_incomplete", spec.task_id)
    instruction_heading_count = len(re.findall(r"^# Instructions$", prompt, re.MULTILINE))
    if instruction_heading_count != 1:
        _fail("prompt_contract_incomplete", f"{spec.task_id}:instructions_headings={instruction_heading_count}")
    assistant = build_assistant_response(load_task(root), load_example_files_from_config(root))
    try:
        blocks = parse_whole_file_blocks(assistant)
    except WholeFormatError as error:
        _fail("whole_format_failed", f"{spec.task_id}:{error}")
    if list(blocks) != expected_solution:
        _fail("target_reference_mismatch", spec.task_id)
    for bad in (
        assistant + "\nextra-prose",
        assistant.replace(expected_solution[0], "unknown.cpp", 1),
        assistant.split(f"{expected_solution[1]}\n", 1)[0],
    ):
        try:
            parsed = parse_whole_file_blocks(bad)
        except WholeFormatError:
            continue
        if set(parsed) == set(expected_solution):
            _fail("whole_format_failed", f"accepted adversarial answer:{spec.task_id}")
    return {
        "prompt_hash": _sha256(prompt.encode()),
        "prompt_instruction_heading_count": instruction_heading_count,
        "reference_response_hash": _sha256(assistant.encode()),
    }


def _semantic_tokens(text: str) -> list[str]:
    text = re.sub(r"//.*?$|/\*.*?\*/|<!--.*?-->", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " literal ", text)
    text = re.sub(r"\bf26dia[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+(?:[uUlL]*)\b", " number ", text)
    text = re.sub(r"\b(?:true|false|nullopt)\b", " boolean ", text, flags=re.IGNORECASE)
    return re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|\+\+|--|&&|\|\||[%*/+<>{}\[\]();,:.?-]", text.lower())


def _shingles(tokens: Sequence[str], width: int = 5) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def _similarity(left: str, right: str) -> float:
    a = _shingles(_semantic_tokens(left))
    b = _shingles(_semantic_tokens(right))
    return len(a & b) / max(1, min(len(a), len(b)))


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _dimension_corpora(root: Path, spec: TaskSpec, *, header_name: str | None = None) -> dict[str, str]:
    header = _read(root, header_name or f"{spec.task_id}.h")
    reference = _read(root, ".meta/example.cpp")
    instructions = _read(root, ".docs/instructions.md")
    visible = _read(root, "visible_test.cpp")
    hidden = _read(root, ".meta/private_test.cpp")
    negative = _read(root, ".meta/negative.cpp")
    return {
        "public_api": header,
        "owned_state_or_algorithm": header + "\n" + reference,
        "mutation_or_selection_rules": reference + "\n" + instructions,
        "invalid_and_boundary_behavior": instructions + "\n" + visible + "\n" + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden,
        "topic_specific_negative_fixture": reference + "\n---negative---\n" + negative,
    }


def _semantic_corpus(root: Path) -> str:
    selected: list[str] = []
    for relative in (
        ".docs/introduction.md",
        ".docs/instructions.md",
        ".meta/example.h",
        ".meta/example.cpp",
        ".meta/private_test.cpp",
        "visible_test.cpp",
    ):
        path = root / relative
        if path.is_file():
            selected.append(path.read_text(encoding="utf-8"))
    return "\n".join(selected)


def _holdout_and_lineage_screen(out: Path) -> dict[str, object]:
    manifest = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    benchmark_ids = set(manifest["task_ids"])
    found = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    if found != benchmark_ids:
        _fail("official_holdout_content_unavailable", f"expected {len(benchmark_ids)}, found {len(found)}")
    own_ids = {spec.task_id for spec in TASKS}
    comparison_roots: list[tuple[str, Path]] = []
    for tree in (LEGACY_ROOT, REVERIFY_ROOT):
        comparison_roots.extend(sorted(_inventory_roots(tree).items()))
    expansion_roots = sorted(_inventory_roots(EXPANSION_ROOT).items())
    comparison_roots.extend((task_id, path) for task_id, path in expansion_roots if task_id not in own_ids)
    holdout_profiles = {task_id: _shingles(_semantic_tokens(_semantic_corpus(HOLDOUT_ROOT / task_id))) for task_id in sorted(benchmark_ids)}
    existing_profiles = [(task_id, path, _shingles(_semantic_tokens(_semantic_corpus(path)))) for task_id, path in comparison_roots]

    def compare(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
        return len(left & right) / max(1, min(len(left), len(right)))

    per_root: dict[str, object] = {}
    for spec in TASKS:
        if spec.task_id in benchmark_ids:
            _fail("benchmark_id_overlap", spec.task_id)
        corpus = _shingles(_semantic_tokens(_semantic_corpus(out / spec.task_id)))
        strongest_holdout = ("", 0.0)
        for task_id, profile in holdout_profiles.items():
            score = compare(corpus, profile)
            if score > strongest_holdout[1]:
                strongest_holdout = (task_id, score)
            if score >= 0.90:
                _fail("benchmark_content_overlap", f"{spec.task_id}:{task_id}:{score:.4f}")
        strongest_existing = ("", 0.0)
        for task_id, path, profile in existing_profiles:
            score = compare(corpus, profile)
            if score > strongest_existing[1]:
                strongest_existing = (f"{task_id}@{_repo_path(path)}", score)
            if score >= 0.985:
                _fail("duplicate_family", f"{spec.task_id}:{task_id}:{score:.4f}")
        per_root[spec.task_id] = {
            "strongest_holdout": {"task_id": strongest_holdout[0], "similarity": strongest_holdout[1]},
            "strongest_existing": {"task": strongest_existing[0], "similarity": strongest_existing[1]},
        }
    return {
        "holdout_count": len(benchmark_ids),
        "candidate_holdout_pairs": EXPECTED_ROOTS * len(benchmark_ids),
        "candidate_existing_pairs": EXPECTED_ROOTS * len(existing_profiles),
        "per_root": per_root,
    }


def _diversity_screen(out: Path) -> dict[str, object]:
    profiles = {spec.task_id: _dimension_corpora(out / spec.task_id, spec) for spec in TASKS}
    shingle_profiles = {task_id: {dimension: _shingles(_semantic_tokens(corpus)) for dimension, corpus in dimensions.items()} for task_id, dimensions in profiles.items()}

    def compare(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
        return len(left & right) / max(1, min(len(left), len(right)))

    decisions: list[dict[str, object]] = []
    for left_index, left in enumerate(TASKS):
        for right in TASKS[left_index + 1 :]:
            dimensions: dict[str, object] = {}
            for dimension in HARD_DIMENSIONS:
                score = compare(shingle_profiles[left.task_id][dimension], shingle_profiles[right.task_id][dimension])
                passed = score < DIMENSION_LIMITS[dimension]
                dimensions[dimension] = {"similarity": score, "limit": DIMENSION_LIMITS[dimension], "pass": passed}
                if not passed:
                    _fail("duplicate_family", f"{left.task_id}:{right.task_id}:{dimension}:{score:.6f}")
            decisions.append({"left": left.task_id, "right": right.task_id, "dimensions": dimensions, "pass": True})
    if len(decisions) != EXPECTED_PAIRS:
        _fail("hard_rule_evidence_incomplete", str(len(decisions)))
    controls: list[dict[str, object]] = []
    for name in CONTROL_NAMES:
        control_root = out / ".state/controls" / name
        control_descriptor_path = control_root / ".control.json"
        if not control_descriptor_path.is_file():
            _fail("adversarial_control_not_coherent", f"missing descriptor:{name}")
        control_descriptor = json.loads(control_descriptor_path.read_text())
        control_changed = control_descriptor.get("changed_files") or []
        if not control_changed or control_descriptor.get("control") != name or control_descriptor.get("source") != TASKS[0].task_id:
            _fail("adversarial_control_not_coherent", f"bad descriptor:{name}")
        for changed_relative in control_changed:
            if not _safe_relative(changed_relative) or not (control_root / changed_relative).is_file():
                _fail("adversarial_control_not_coherent", f"missing changed file:{name}:{changed_relative}")
        control_headers = sorted(path.name for path in control_root.glob("f26dia-*.h"))
        if len(control_headers) != 1:
            _fail("adversarial_control_not_coherent", f"header count:{name}:{len(control_headers)}")
        control_profile = _dimension_corpora(control_root, TASKS[0], header_name=control_headers[0])
        control_shingles = {dimension: _shingles(_semantic_tokens(corpus)) for dimension, corpus in control_profile.items()}
        dimension_results: dict[str, object] = {}
        for dimension in HARD_DIMENSIONS:
            score = compare(shingle_profiles[TASKS[0].task_id][dimension], control_shingles[dimension])
            rejected = score >= DIMENSION_LIMITS[dimension]
            dimension_results[dimension] = {"similarity": score, "limit": DIMENSION_LIMITS[dimension], "rejected_as_duplicate": rejected}
            if not rejected:
                _fail("adversarial_control_escaped", f"{name}:{dimension}:{score:.6f}")
        controls.append(
            {
                "name": name,
                "dimensions": dimension_results,
                "changed_files": control_changed,
                "mutation_note": CONTROL_MUTATION_NOTE,
                "rejected_in_all_dimensions": True,
            }
        )
    payload = {
        "schema_version": "fixed26-dia-diversity-v1",
        "normalizer": NORMALIZER,
        "root_count": EXPECTED_ROOTS,
        "pair_count": len(decisions),
        "dimensions": list(HARD_DIMENSIONS),
        "decisions": decisions,
        "controls": controls,
        "pass": True,
    }
    _write_json(out / ".state/receipts/diversity-screen.json", payload, overwrite=True)
    return payload


def _deterministic_regeneration(out: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="fixed26-dia-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh, testing=True)
        for spec in TASKS:
            if _tree_hash(out / spec.task_id) != _tree_hash(fresh / spec.task_id):
                _fail("generator_output_drift", spec.task_id)
        return _tree_hash(fresh)


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    _validate_output(out, testing=out.resolve(strict=False) != DEFAULT_OUT.resolve(strict=False))
    roots = sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state")
    if len(roots) != EXPECTED_ROOTS or {path.name for path in roots} != {spec.task_id for spec in TASKS}:
        _fail("generator_output_drift", f"root count/ids:{len(roots)}")
    fresh_hash = _deterministic_regeneration(out)
    prompt_records: dict[str, object] = {}
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for spec in TASKS:
        record = _role_and_prompt_check(out / spec.task_id, spec)
        if record["prompt_hash"] in prompt_hashes:
            _fail("duplicate_task", f"prompt:{spec.task_id}")
        if record["reference_response_hash"] in reference_hashes:
            _fail("duplicate_task", f"reference:{spec.task_id}")
        prompt_hashes.add(str(record["prompt_hash"]))
        reference_hashes.add(str(record["reference_response_hash"]))
        prompt_records[spec.task_id] = record
    diversity = _diversity_screen(out)
    lineage = _holdout_and_lineage_screen(out)
    payload = {
        "schema_version": "fixed26-dia-core-v1",
        "status": "creator_core_verified",
        "root_count": len(roots),
        "pair_count": diversity["pair_count"],
        "tree_hash": _tree_hash(out),
        "fresh_tree_hash": fresh_hash,
        "generator_revision": _generator_revision(),
        "curriculum_hash": _file_hash(CURRICULUM),
        "focused_test_hash": _file_hash(REPO_ROOT / FOCUSED_TEST) if (REPO_ROOT / FOCUSED_TEST).is_file() else None,
        "prompt_records": prompt_records,
        "lineage_screen": lineage,
        "diversity_receipt_hash": _file_hash(out / ".state/receipts/diversity-screen.json"),
    }
    _write_json(out / ".state/receipts/core-preflight.json", payload, overwrite=True)
    return payload


def _docker_runner() -> str:
    return r"""set -eu
mkdir -p /work/family
tar -xf /input/family.tar -C /work/family
python3 - <<'PY'
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path("/work/family")


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes())


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if ".state" in path.parts:
            continue
        if "build" in path.parts:
            continue
        rel = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def run_command(argv, *, cwd=None, env=None, check=True):
    completed = subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    record = {
        "argv": [re.sub(r"/tmp/check-[^/]+", "$WORK", str(item)) for item in argv],
        "returncode": completed.returncode,
        "stdout_hash": sha256(completed.stdout.encode()),
        "stderr_hash": sha256(completed.stderr.encode()),
    }
    if check and completed.returncode != 0:
        print(completed.stdout[-4000:], file=sys.stderr)
        print(completed.stderr[-4000:], file=sys.stderr)
        raise SystemExit(completed.returncode)
    return completed, record


def discovered_test_count(build_dir: Path):
    completed, record = run_command(["ctest", "--test-dir", str(build_dir), "-N"])
    count = sum(1 for line in completed.stdout.splitlines() if re.match(r"^\s*Test #[0-9]+: ", line))
    if count != 2:
        print(completed.stdout, file=sys.stderr)
        raise SystemExit(40)
    return count, record


def copied_work(task_root: Path, prefix: str) -> Path:
    work = Path(tempfile.mkdtemp(prefix=prefix, dir="/tmp"))
    shutil.rmtree(work)
    shutil.copytree(task_root, work)
    return work


def install_reference_or_negative(work: Path, *, negative: bool) -> dict:
    config = json.loads((work / ".meta/config.json").read_text())
    header, source = config["files"]["solution"]
    shutil.copyfile(work / ".meta/example.h", work / header)
    shutil.copyfile(work / (".meta/negative.cpp" if negative else ".meta/example.cpp"), work / source)
    return config


def build_and_test(task_root: Path, *, mode: str, negative: bool = False) -> dict:
    task_id = task_root.name
    print(f"VERIFY_{mode}{'_negative' if negative else ''}={task_id}", file=sys.stderr)
    work = copied_work(task_root, f"check-{mode}{'-negative' if negative else ''}-{task_id}-")
    try:
        config = install_reference_or_negative(work, negative=negative)
        build_dir = work / "build"
        flags = []
        if mode == "sanitizer":
            flags = ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer"]
        commands = []
        _, configure = run_command(["cmake", "-S", str(work), "-B", str(build_dir), "-G", "Unix Makefiles", *flags])
        commands.append({"phase": "configure", **configure})
        _, build = run_command(["cmake", "--build", str(build_dir), "--parallel", "2"])
        commands.append({"phase": "build", **build})
        count, discover = discovered_test_count(build_dir)
        commands.append({"phase": "discover", **discover})
        env = os.environ.copy()
        env["ASAN_OPTIONS"] = "detect_leaks=1"
        env["UBSAN_OPTIONS"] = "halt_on_error=1"
        completed, ctest = run_command(
            ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
            env=env,
            check=not negative,
        )
        commands.append({"phase": "test", **ctest})
        if negative and completed.returncode == 0:
            print(f"NEGATIVE_ESCAPED={task_id}", file=sys.stderr)
            raise SystemExit(41)
        return {
            "test_count": count,
            "rejected": bool(negative and completed.returncode != 0),
            "commands": commands,
            "files_solution": config["files"]["solution"],
            "files_test": config["files"]["test"],
            "files_example": config["files"]["example"],
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


compiler_path = shutil.which("c++")
cmake_path = shutil.which("cmake")
if not compiler_path or not cmake_path:
    raise SystemExit("missing compiler or cmake")
compiler_version = run_command([compiler_path, "--version"])[0].stdout
cmake_version = run_command([cmake_path, "--version"])[0].stdout.splitlines()[0]

records = []
normal_total = 0
sanitizer_total = 0
negative_normal_total = 0
negative_sanitizer_total = 0
for task_root in sorted(ROOT.glob("f26dia-*")):
    task_id = task_root.name
    normal = build_and_test(task_root, mode="normal")
    sanitizer = build_and_test(task_root, mode="sanitizer")
    negative_normal = build_and_test(task_root, mode="normal", negative=True)
    negative_sanitizer = build_and_test(task_root, mode="sanitizer", negative=True)
    normal_total += normal["test_count"]
    sanitizer_total += sanitizer["test_count"]
    negative_normal_total += int(negative_normal["rejected"])
    negative_sanitizer_total += int(negative_sanitizer["rejected"])
    records.append(
        {
            "task_id": task_id,
            "source_tree_hash": tree_hash(task_root),
            "starter_hash": sha256((task_root / f"{task_id}.h").read_bytes() + b"\0" + (task_root / f"{task_id}.cpp").read_bytes()),
            "reference_hash": sha256((task_root / ".meta/example.h").read_bytes() + b"\0" + (task_root / ".meta/example.cpp").read_bytes()),
            "visible_test_hash": file_hash(task_root / "visible_test.cpp"),
            "private_test_hash": file_hash(task_root / ".meta/private_test.cpp"),
            "negative_fixture_hash": file_hash(task_root / ".meta/negative.cpp"),
            "normal": normal,
            "sanitizer": sanitizer,
            "negative_normal": negative_normal,
            "negative_sanitizer": negative_sanitizer,
        }
    )

control_records = []
control_normal_total = 0
control_sanitizer_total = 0
for control_root in sorted((ROOT / ".state/controls").glob("*")):
    normal = build_and_test(control_root, mode="normal")
    sanitizer = build_and_test(control_root, mode="sanitizer")
    control_normal_total += normal["test_count"]
    control_sanitizer_total += sanitizer["test_count"]
    control_records.append({"name": control_root.name, "normal": normal, "sanitizer": sanitizer})

summary = {
    "mount_tree_hash": tree_hash(ROOT),
    "compiler_path": compiler_path,
    "compiler_version": compiler_version,
    "compiler_hash": file_hash(Path(compiler_path)),
    "cmake_path": cmake_path,
    "cmake_version": cmake_version,
    "cmake_hash": file_hash(Path(cmake_path)),
    "normal_test_count": normal_total,
    "sanitizer_test_count": sanitizer_total,
    "negative_normal_rejections": negative_normal_total,
    "negative_sanitizer_rejections": negative_sanitizer_total,
    "control_normal_test_count": control_normal_total,
    "control_sanitizer_test_count": control_sanitizer_total,
    "per_root": records,
    "controls": control_records,
}
print("DOCKER_SANITY_JSON=" + json.dumps(summary, sort_keys=True))
PY
"""


def _record_not_completed(out: Path, gate: str, code: str, detail: str) -> None:
    _write_json(
        out / ".state/receipts" / f"{gate}.not_completed.json",
        {
            "schema_version": "fixed26-dia-not-completed-v1",
            "status": "not_completed",
            "gate": gate,
            "code": code,
            "detail": detail,
            "tree_hash": _tree_hash(out) if out.exists() else None,
        },
        overwrite=True,
    )


def docker_sanity(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    core = verify_core(out)
    with tempfile.TemporaryDirectory(prefix="fixed26-dia-docker-") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / "family.tar"
        with tarfile.open(archive, "w") as tar:
            for path in sorted(out.rglob("*")):
                if path.is_file() and "build" not in path.parts:
                    tar.add(path, arcname=path.relative_to(out), recursive=False)
        try:
            image_id = subprocess.run(
                ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            _record_not_completed(out, "docker-sanity", "docker_image_unavailable", str(error))
            _fail("docker_image_unavailable", str(error))
        if image_id != SANITY_IMAGE_ID:
            _record_not_completed(out, "docker-sanity", "grader_image_mismatch", f"{image_id}:{SANITY_IMAGE_ID}")
            _fail("grader_image_mismatch", f"{image_id}:{SANITY_IMAGE_ID}")
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,exec,nosuid,size=2g",
                "--tmpfs",
                "/work:rw,exec,nosuid,size=2g",
                "-v",
                f"{archive}:/input/family.tar:ro",
                image,
                "sh",
                "-lc",
                _docker_runner(),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
    if completed.returncode != 0:
        detail = completed.stdout[-3000:] + completed.stderr[-3000:]
        _record_not_completed(out, "docker-sanity", "docker_sanity_failed", detail)
        _fail("docker_sanity_failed", detail)
    values: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if line.startswith("DOCKER_SANITY_JSON="):
            values["DOCKER_SANITY_JSON"] = line.split("=", 1)[1]
        elif "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    if "DOCKER_SANITY_JSON" not in values:
        _fail("docker_sanity_failed", "missing docker summary")
    docker_summary = json.loads(values["DOCKER_SANITY_JSON"])
    expected_tree = str(core["tree_hash"])
    expected_tests = EXPECTED_ROOTS * 2
    if docker_summary.get("mount_tree_hash") != expected_tree:
        _fail("grader_mount_hash_mismatch", f"{docker_summary.get('mount_tree_hash')}:{expected_tree}")
    if int(docker_summary.get("normal_test_count", -1)) != expected_tests:
        _fail("zero_tests", str(docker_summary.get("normal_test_count", "missing")))
    if int(docker_summary.get("sanitizer_test_count", -1)) != expected_tests:
        _fail("sanitizer_test_count_mismatch", str(docker_summary.get("sanitizer_test_count", "missing")))
    if int(docker_summary.get("negative_normal_rejections", -1)) != EXPECTED_ROOTS:
        _fail("negative_fixture_not_rejected", str(docker_summary.get("negative_normal_rejections", "missing")))
    if int(docker_summary.get("negative_sanitizer_rejections", -1)) != EXPECTED_ROOTS:
        _fail("negative_fixture_not_rejected", str(docker_summary.get("negative_sanitizer_rejections", "missing")))
    if len(docker_summary.get("per_root", [])) != EXPECTED_ROOTS:
        _fail("hard_rule_evidence_incomplete", f"per-root docker receipts:{len(docker_summary.get('per_root', []))}")
    if int(docker_summary.get("control_normal_test_count", -1)) != len(CONTROL_NAMES) * 2 or int(docker_summary.get("control_sanitizer_test_count", -1)) != len(CONTROL_NAMES) * 2:
        _fail("adversarial_control_not_coherent", str(docker_summary))
    per_root = []
    prompt_records = core.get("prompt_records", {})
    for record in docker_summary["per_root"]:
        task_id = record["task_id"]
        prompt_record = prompt_records.get(task_id)
        if not prompt_record:
            _fail("hard_rule_evidence_incomplete", f"missing prompt record:{task_id}")
        record = dict(record)
        record["prompt_hash"] = prompt_record["prompt_hash"]
        record["generator_hash"] = _generator_revision()
        record["network_policy"] = "none"
        record["compiler_path"] = docker_summary["compiler_path"]
        record["compiler_version"] = docker_summary["compiler_version"]
        record["compiler_version_hash"] = _sha256(docker_summary["compiler_version"].encode())
        record["compiler_hash"] = docker_summary["compiler_hash"]
        record["cmake_path"] = docker_summary["cmake_path"]
        record["cmake_version"] = docker_summary["cmake_version"]
        record["cmake_hash"] = docker_summary["cmake_hash"]
        per_root.append(record)
    payload = {
        "schema_version": "fixed26-dia-docker-sanity-v1",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network_policy": "none",
        "image": image,
        "image_id": image_id,
        "tree_hash": expected_tree,
        "generator_revision": _generator_revision(),
        "normal_test_count": expected_tests,
        "sanitizer_test_count": expected_tests,
        "negative_rejections": EXPECTED_ROOTS,
        "negative_normal_rejections": EXPECTED_ROOTS,
        "negative_sanitizer_rejections": EXPECTED_ROOTS,
        "control_normal_test_count": len(CONTROL_NAMES) * 2,
        "control_sanitizer_test_count": len(CONTROL_NAMES) * 2,
        "stdout_hash": _sha256(completed.stdout.encode()),
        "stderr_hash": _sha256(completed.stderr.encode()),
        "compiler_path": docker_summary["compiler_path"],
        "compiler_version": docker_summary["compiler_version"],
        "compiler_version_hash": _sha256(docker_summary["compiler_version"].encode()),
        "compiler_hash": docker_summary["compiler_hash"],
        "cmake_path": docker_summary["cmake_path"],
        "cmake_version": docker_summary["cmake_version"],
        "cmake_hash": docker_summary["cmake_hash"],
        "per_root": per_root,
        "controls": docker_summary["controls"],
    }
    _write_json(out / ".state/receipts/docker-sanity.json", payload, overwrite=True)
    return payload


def creator_preflight(out: Path = DEFAULT_OUT, *, require_docker: bool = True) -> dict[str, object]:
    core = verify_core(out)
    docker_path = out / ".state/receipts/docker-sanity.json"
    docker = docker_sanity(out) if require_docker else json.loads(docker_path.read_text())
    if docker.get("tree_hash") != core.get("tree_hash") or docker.get("generator_revision") != core.get("generator_revision"):
        _fail("stale_oracle_receipt", "Docker receipt does not bind current tree/owner")
    bindings = {
        "owner": _generator_revision(),
        "curriculum": _file_hash(CURRICULUM),
        "creation_prompt": _file_hash(REPO_ROOT / CREATION_PROMPT),
        "implementation_prompt": _file_hash(REPO_ROOT / IMPLEMENTATION_PROMPT),
        "focused_test": _file_hash(REPO_ROOT / FOCUSED_TEST) if (REPO_ROOT / FOCUSED_TEST).is_file() else None,
        "tree": _tree_hash(out),
        "core_receipt": _file_hash(out / ".state/receipts/core-preflight.json"),
        "diversity_receipt": _file_hash(out / ".state/receipts/diversity-screen.json"),
        "docker_receipt": _file_hash(docker_path),
        "source_inventories": _file_hash(out / ".state/manifests/source-inventories.json"),
        "selected_manifest": _file_hash(out / ".state/manifests/selected-candidates.json"),
        "batch_ledger": _file_hash(out / ".state/manifests/batch-ledger.json"),
    }
    subject_hash = _sha256(json.dumps(bindings, sort_keys=True).encode())
    payload = {
        "schema_version": "fixed26-dia-creator-preflight-v1",
        "status": "pass",
        "root_count": EXPECTED_ROOTS,
        "pair_count": EXPECTED_PAIRS,
        "negative_rejections": EXPECTED_ROOTS,
        "subject_hash": subject_hash,
        "bindings": bindings,
    }
    _write_json(out / ".state/receipts/creator-preflight.json", payload, overwrite=True)
    return payload


def _root_catalog_entry(out: Path, spec: TaskSpec) -> dict[str, object]:
    root = out / spec.task_id
    config = json.loads(_read(root, ".meta/config.json"))
    provenance = json.loads(_read(root, ".meta/provenance.json"))
    return {
        "task_id": spec.task_id,
        "family": FAMILY_ID,
        "capability": "fixed26-diamond-analog",
        "difficulty": "intermediate",
        "interaction": "aider-whole-file",
        "statefulness": "stateful" if "class" in spec.declarations else "stateless",
        "verification": "docker_sanity",
        "disposition": "local-family-candidate",
        "tree_hash": _tree_hash(root),
        "config_hash": _sha256(json.dumps(config, sort_keys=True).encode()),
        "provenance_hash": _sha256(json.dumps(provenance, sort_keys=True).encode()),
        "primary_core_objective": "achieved",
    }


def _private_path_leaks(out: Path) -> list[str]:
    forbidden = ("/data/sanil/", "/home/ubuntu/", "/tmp/")
    leaks: list[str] = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in text for marker in forbidden):
            leaks.append(_repo_path(path))
    return leaks


def audit(out: Path = DEFAULT_OUT, *, cycle: int) -> dict[str, object]:
    preflight_path = out / ".state/receipts/creator-preflight.json"
    if not preflight_path.is_file():
        _fail("audit_missing_creator_preflight", str(preflight_path))
    preflight = json.loads(preflight_path.read_text())
    docker = json.loads((out / ".state/receipts/docker-sanity.json").read_text())
    diversity = json.loads((out / ".state/receipts/diversity-screen.json").read_text())
    ledger = json.loads((out / ".state/manifests/batch-ledger.json").read_text())
    catalog = [_root_catalog_entry(out, spec) for spec in TASKS]
    findings: list[dict[str, object]] = []
    if len(catalog) != EXPECTED_ROOTS or len({row["task_id"] for row in catalog}) != EXPECTED_ROOTS:
        findings.append({"id": f"cycle-{cycle:02d}/family/root-count-or-duplicate", "severity": "blocker", "disposition": "repair-and-reverify"})
    if docker.get("tree_hash") != _tree_hash(out):
        findings.append({"id": f"cycle-{cycle:02d}/family/stale-docker", "severity": "blocker", "disposition": "repair-and-reverify"})
    if diversity.get("pair_count") != EXPECTED_PAIRS or not diversity.get("pass"):
        findings.append({"id": f"cycle-{cycle:02d}/family/diversity", "severity": "major", "disposition": "repair-and-reverify"})
    if ledger.get("deferred_roots") or ledger.get("failed_roots"):
        findings.append({"id": f"cycle-{cycle:02d}/family/unresolved-roots", "severity": "blocker", "disposition": "repair-and-reverify"})
    duplicate_prompt_headers = [
        task_id
        for task_id, record in json.loads((out / ".state/receipts/core-preflight.json").read_text()).get("prompt_records", {}).items()
        if record.get("prompt_instruction_heading_count") != 1
    ]
    if duplicate_prompt_headers:
        findings.append({"id": f"cycle-{cycle:02d}/family/duplicate-instruction-headers", "severity": "blocker", "disposition": "repair-and-reverify", "roots": duplicate_prompt_headers})
    path_leaks = _private_path_leaks(out)
    if path_leaks:
        findings.append({"id": f"cycle-{cycle:02d}/family/private-path-leak", "severity": "blocker", "disposition": "repair-and-reverify", "files": path_leaks[:25], "file_count": len(path_leaks)})
    if len(docker.get("per_root", [])) != EXPECTED_ROOTS:
        findings.append({"id": f"cycle-{cycle:02d}/family/per-root-docker-receipts", "severity": "major", "disposition": "repair-and-reverify"})
    required_docker_fields = {
        "compiler_path",
        "compiler_version",
        "compiler_version_hash",
        "compiler_hash",
        "cmake_path",
        "cmake_version",
        "cmake_hash",
        "stdout_hash",
        "stderr_hash",
    }
    missing_docker_fields = sorted(field for field in required_docker_fields if not docker.get(field))
    required_root_fields = {
        "task_id",
        "prompt_hash",
        "source_tree_hash",
        "starter_hash",
        "reference_hash",
        "visible_test_hash",
        "private_test_hash",
        "negative_fixture_hash",
        "normal",
        "sanitizer",
        "negative_normal",
        "negative_sanitizer",
        "compiler_path",
        "compiler_version",
        "compiler_version_hash",
        "compiler_hash",
        "cmake_path",
        "cmake_version",
        "cmake_hash",
    }
    incomplete_root_receipts = []
    for record in docker.get("per_root", []):
        if not isinstance(record, dict):
            incomplete_root_receipts.append("<non-object>")
            continue
        missing = sorted(field for field in required_root_fields if not record.get(field))
        for phase in ("normal", "sanitizer", "negative_normal", "negative_sanitizer"):
            phase_record = record.get(phase)
            if not isinstance(phase_record, dict) or not phase_record.get("commands") or phase_record.get("test_count") != 2:
                missing.append(f"{phase}.commands_or_test_count")
        if missing:
            incomplete_root_receipts.append(f"{record.get('task_id', '<missing-task-id>')}:{','.join(missing)}")
    if missing_docker_fields or incomplete_root_receipts:
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/incomplete-docker-receipt-fields",
                "severity": "blocker",
                "disposition": "repair-and-reverify",
                "missing_batch_fields": missing_docker_fields,
                "incomplete_root_receipts": incomplete_root_receipts[:25],
                "incomplete_root_count": len(incomplete_root_receipts),
            }
        )
    if docker.get("negative_normal_rejections") != EXPECTED_ROOTS or docker.get("negative_sanitizer_rejections") != EXPECTED_ROOTS:
        findings.append({"id": f"cycle-{cycle:02d}/family/negative-sanitizer-rejections", "severity": "blocker", "disposition": "repair-and-reverify"})
    subject = {
        "tree_hash": _tree_hash(out),
        "preflight_hash": _file_hash(preflight_path),
        "docker_hash": _file_hash(out / ".state/receipts/docker-sanity.json"),
        "diversity_hash": _file_hash(out / ".state/receipts/diversity-screen.json"),
        "selected_hash": _file_hash(out / ".state/manifests/selected-candidates.json"),
        "ledger_hash": _file_hash(out / ".state/manifests/batch-ledger.json"),
        "catalog_hash": _sha256(json.dumps(catalog, sort_keys=True).encode()),
    }
    subject_hash = _sha256(json.dumps(subject, sort_keys=True).encode())
    report = {
        "schema_version": "audit-sft-data-quality-local-family-v1",
        "cycle": cycle,
        "audit_subject_hash": subject_hash,
        "behavior_contract": {
            "task": "implement clean-room fixed26 diamond analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "owned computed vector-of-strings grid state with task-owned width, height, and line-count derivation; exact mirror symmetry where advertised; caller-chosen printable non-space ASCII marks; interior padding always the ASCII space; byte-identical deterministic rendering; invalid sizes and characters rejected through typed errors that never mutate",
            "evaluation": "prompt-boundary validation, normal CTest, fresh ASan/UBSan CTest, executed wrong-substitute rejection, semantic duplicate screen, and benchmark contamination screen",
        },
        "confirmed_counts": {
            "roots": len(catalog),
            "pairs": diversity.get("pair_count"),
            "normal_tests": docker.get("normal_test_count"),
            "sanitizer_tests": docker.get("sanitizer_test_count"),
            "negative_rejections": docker.get("negative_rejections"),
            "negative_normal_rejections": docker.get("negative_normal_rejections"),
            "negative_sanitizer_rejections": docker.get("negative_sanitizer_rejections"),
            "per_root_docker_receipts": len(docker.get("per_root", [])),
            "project_context_support_roots": ledger.get("project_context_support_count"),
        },
        "root_catalog": catalog,
        "duplicate_lineage_report": {"exact_ids": 0, "semantic_conflicts": 0},
        "contamination_report": {"official_holdout_pairs": EXPECTED_ROOTS * 26, "dispositions": []},
        "corpus_composition": {
            "bucket": "failed-fixed26-analog",
            "target_family": "diamond",
            "root_count": EXPECTED_ROOTS,
            "project_context_support_count": ledger.get("project_context_support_count"),
        },
        "findings": findings,
        "decision": "local_family_verified" if not findings else "repair-and-reverify",
        "limitations": [
            "not an SFT row set",
            "not JSONL",
            "not token or mask evidence",
            "not an export",
            "not a training run",
            "not benchmark uplift evidence",
        ],
        "subject_bindings": subject,
        "creator_subject_hash": preflight.get("subject_hash"),
    }
    audit_root = out / ".state/audits"
    report_path = audit_root / f"cycle-{cycle:02d}-{subject_hash.removeprefix('sha256:')}.json"
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if report_path.exists() and report_path.read_text() != serialized:
        _fail("immutable_audit_conflict", str(report_path))
    _write(report_path, serialized, overwrite=report_path.exists())
    catalog_path = audit_root / f"cycle-{cycle:02d}-{subject_hash.removeprefix('sha256:')}.catalog.json"
    catalog_text = json.dumps(catalog, indent=2, sort_keys=True) + "\n"
    if catalog_path.exists() and catalog_path.read_text() != catalog_text:
        _fail("immutable_audit_conflict", str(catalog_path))
    _write(catalog_path, catalog_text, overwrite=catalog_path.exists())
    report["report_path"] = _repo_path(report_path)
    report["catalog_path"] = _repo_path(catalog_path)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true")
    group.add_argument("--verify-core", action="store_true")
    group.add_argument("--docker-sanity", action="store_true")
    group.add_argument("--creator-preflight", action="store_true")
    group.add_argument("--audit", type=int, metavar="CYCLE")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.build:
        result = build(args.out, force=args.force)
    elif args.verify_core:
        result = verify_core(args.out)
    elif args.docker_sanity:
        result = docker_sanity(args.out, args.image)
    elif args.creator_preflight:
        result = creator_preflight(args.out)
    else:
        result = audit(args.out, cycle=args.audit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
