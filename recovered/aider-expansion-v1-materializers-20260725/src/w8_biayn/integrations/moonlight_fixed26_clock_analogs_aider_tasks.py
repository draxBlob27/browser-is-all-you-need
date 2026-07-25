"""Create and verify the fixed-26 clock clean-room analog batch.

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b006-clock.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b006-clock"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_clock_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_clock_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b006-clock"
FAMILY_ID = "aider-fixed26-clock-analogs-v1"
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
        "f26clk-airfield-runway-carousel",
        "f26clk-bakery-hearth-rotation",
        "f26clk-ferry-tide-window",
        "f26clk-marshalling-yard-lead",
        "f26clk-print-press-cylinder",
        "f26clk-rodeo-chute-gate",
        "f26clk-signal-gantry-aspect",
        "f26clk-waterworks-pump-rota",
        "f26clk-wind-farm-yaw-cycle",
        "f26clk-tollbridge-lane-cycle",
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
#include <cstdint>
#include <deque>
#include <limits>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
"""


COMMON_SOURCE = r"""
#include <algorithm>
#include <iomanip>
#include <limits>
#include <numeric>
#include <sstream>
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
            "f26clk-sluice-gate-wheel",
            "Sluice gate wheel",
            "sluice_gate",
            """
            class GateWheel {
            public:
                GateWheel(int turns, int notches);
                void advance(int notches);
                void retreat(int notches);
                int turns() const;
                int notches() const;
                long total_notches() const;
                bool at_home() const;
                bool operator==(const GateWheel& other) const;
            };
            """,
            """
            class GateWheel {
            public:
                GateWheel(int turns, int notches);
                void advance(int notches);
                void retreat(int notches);
                int turns() const;
                int notches() const;
                long total_notches() const;
                bool at_home() const;
                bool operator==(const GateWheel& other) const;
            private:
                static constexpr int kNotchesPerTurn = 40;
                static constexpr int kTurnsPerCycle = 64;
                static constexpr long kCycleNotches = 2560L;
                static long normalize(long total);
                int turns_;
                int notches_;
            };
            """,
            """
            long GateWheel::normalize(long total) {
                long wrapped = total % kCycleNotches;
                if (wrapped < 0) wrapped += kCycleNotches;
                return wrapped;
            }
            GateWheel::GateWheel(int turns, int notches) {
                long total = normalize(static_cast<long>(turns) * kNotchesPerTurn + notches);
                turns_ = static_cast<int>(total / kNotchesPerTurn);
                notches_ = static_cast<int>(total % kNotchesPerTurn);
            }
            void GateWheel::advance(int notches) {
                long total = normalize(total_notches() + notches);
                turns_ = static_cast<int>(total / kNotchesPerTurn);
                notches_ = static_cast<int>(total % kNotchesPerTurn);
            }
            void GateWheel::retreat(int notches) {
                advance(-notches);
            }
            int GateWheel::turns() const { return turns_; }
            int GateWheel::notches() const { return notches_; }
            long GateWheel::total_notches() const {
                return static_cast<long>(turns_) * kNotchesPerTurn + notches_;
            }
            bool GateWheel::at_home() const { return turns_ == 0 && notches_ == 0; }
            bool GateWheel::operator==(const GateWheel& other) const {
                return turns_ == other.turns_ && notches_ == other.notches_;
            }
            """,
            """
            long GateWheel::normalize(long total) {
                return total % kCycleNotches;
            }
            GateWheel::GateWheel(int turns, int notches) {
                long total = normalize(static_cast<long>(turns) * kNotchesPerTurn + notches);
                turns_ = static_cast<int>(total / kNotchesPerTurn);
                notches_ = static_cast<int>(total % kNotchesPerTurn);
            }
            void GateWheel::advance(int notches) {
                long total = normalize(total_notches() + notches);
                turns_ = static_cast<int>(total / kNotchesPerTurn);
                notches_ = static_cast<int>(total % kNotchesPerTurn);
            }
            void GateWheel::retreat(int notches) {
                advance(-notches);
            }
            int GateWheel::turns() const { return turns_; }
            int GateWheel::notches() const { return notches_; }
            long GateWheel::total_notches() const {
                return static_cast<long>(turns_) * kNotchesPerTurn + notches_;
            }
            bool GateWheel::at_home() const { return turns_ == 0 && notches_ == 0; }
            bool GateWheel::operator==(const GateWheel& other) const {
                return turns_ == other.turns_ && notches_ == other.notches_;
            }
            """,
            """
            GateWheel wheel(3, 20);
            if (wheel.turns() != 3 || wheel.notches() != 20) return 1;
            if (wheel.total_notches() != 140L) return 2;
            wheel.advance(50);
            if (wheel.turns() != 4 || wheel.notches() != 30) return 3;
            wheel.retreat(70);
            if (wheel.turns() != 3 || wheel.notches() != 0) return 4;
            GateWheel same(3, 0);
            if (!(wheel == same)) return 5;
            if (wheel.at_home()) return 6;
            return 0;
            """,
            """
            GateWheel neg(-1, 15);
            if (neg.turns() != 63 || neg.notches() != 15) return 1;
            GateWheel over(2, 95);
            if (over.turns() != 4 || over.notches() != 15) return 2;
            GateWheel w(0, 10);
            w.retreat(15);
            if (w.turns() != 63 || w.notches() != 35) return 3;
            w.advance(2560);
            if (w.turns() != 63 || w.notches() != 35) return 4;
            w.advance(5);
            if (!w.at_home()) return 5;
            if (w.total_notches() != 0L) return 6;
            GateWheel a(1, 0);
            GateWheel b(0, 40);
            if (!(a == b)) return 7;
            GateWheel c(64, 0);
            if (!c.at_home()) return 8;
            GateWheel d(-64, -40);
            if (d.turns() != 63 || d.notches() != 0) return 9;
            w.retreat(0);
            if (!w.at_home()) return 10;
            return 0;
            """,
            "floor-mod normalization of a 2560-notch two-field gate cycle with carry and borrow between turns and notches",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative construction and retreat borrows, multi-cycle wraps, exact total_notches after crossings, at_home boundaries at 0 and 2560, and representation-blind equality",
            "two-field carry/borrow modular normalization with negative offsets in a paired .h/.cpp API",
            "two-field carry/borrow cyclic dial",
        ),
        c(
            "f26clk-cable-capstan-gauge",
            "Cable capstan gauge",
            "capstan",
            """
            class WrapGauge {
            public:
                WrapGauge(int wraps, int fathoms);
                void veer(int fathoms);
                void haul(int fathoms);
                int wraps() const;
                int fathoms() const;
                long total_fathoms() const;
                bool paid_out() const;
                bool operator==(const WrapGauge& other) const;
            };
            """,
            """
            class WrapGauge {
            public:
                WrapGauge(int wraps, int fathoms);
                void veer(int fathoms);
                void haul(int fathoms);
                int wraps() const;
                int fathoms() const;
                long total_fathoms() const;
                bool paid_out() const;
                bool operator==(const WrapGauge& other) const;
            private:
                static constexpr int kFathomsPerWrap = 12;
                static constexpr int kWrapsPerCycle = 50;
                static constexpr long kCycleFathoms = 600L;
                static long normalize(long total);
                int wraps_;
                int fathoms_;
            };
            """,
            """
            long WrapGauge::normalize(long total) {
                long wrapped = total % kCycleFathoms;
                if (wrapped < 0) wrapped += kCycleFathoms;
                return wrapped;
            }
            WrapGauge::WrapGauge(int wraps, int fathoms) {
                long total = normalize(static_cast<long>(wraps) * kFathomsPerWrap + fathoms);
                wraps_ = static_cast<int>(total / kFathomsPerWrap);
                fathoms_ = static_cast<int>(total % kFathomsPerWrap);
            }
            void WrapGauge::veer(int fathoms) {
                long total = normalize(total_fathoms() + fathoms);
                wraps_ = static_cast<int>(total / kFathomsPerWrap);
                fathoms_ = static_cast<int>(total % kFathomsPerWrap);
            }
            void WrapGauge::haul(int fathoms) {
                veer(-fathoms);
            }
            int WrapGauge::wraps() const { return wraps_; }
            int WrapGauge::fathoms() const { return fathoms_; }
            long WrapGauge::total_fathoms() const {
                return static_cast<long>(wraps_) * kFathomsPerWrap + fathoms_;
            }
            bool WrapGauge::paid_out() const { return fathoms_ == 0; }
            bool WrapGauge::operator==(const WrapGauge& other) const {
                return wraps_ == other.wraps_ && fathoms_ == other.fathoms_;
            }
            """,
            """
            long WrapGauge::normalize(long total) {
                long minor = total % kFathomsPerWrap;
                if (minor < 0) minor += kFathomsPerWrap;
                long major = (total / kFathomsPerWrap) % kWrapsPerCycle;
                if (major < 0) major += kWrapsPerCycle;
                return major * kFathomsPerWrap + minor;
            }
            WrapGauge::WrapGauge(int wraps, int fathoms) {
                long total = normalize(static_cast<long>(wraps) * kFathomsPerWrap + fathoms);
                wraps_ = static_cast<int>(total / kFathomsPerWrap);
                fathoms_ = static_cast<int>(total % kFathomsPerWrap);
            }
            void WrapGauge::veer(int fathoms) {
                long total = normalize(total_fathoms() + fathoms);
                wraps_ = static_cast<int>(total / kFathomsPerWrap);
                fathoms_ = static_cast<int>(total % kFathomsPerWrap);
            }
            void WrapGauge::haul(int fathoms) {
                veer(-fathoms);
            }
            int WrapGauge::wraps() const { return wraps_; }
            int WrapGauge::fathoms() const { return fathoms_; }
            long WrapGauge::total_fathoms() const {
                return static_cast<long>(wraps_) * kFathomsPerWrap + fathoms_;
            }
            bool WrapGauge::paid_out() const { return fathoms_ == 0; }
            bool WrapGauge::operator==(const WrapGauge& other) const {
                return wraps_ == other.wraps_ && fathoms_ == other.fathoms_;
            }
            """,
            """
            WrapGauge gauge(2, 7);
            if (gauge.wraps() != 2 || gauge.fathoms() != 7) return 1;
            if (gauge.total_fathoms() != 31L) return 2;
            gauge.veer(9);
            if (gauge.wraps() != 3 || gauge.fathoms() != 4) return 3;
            gauge.haul(16);
            if (gauge.wraps() != 2 || gauge.fathoms() != 0) return 4;
            if (!gauge.paid_out()) return 5;
            WrapGauge twin(1, 12);
            if (!(gauge == twin)) return 6;
            if (gauge.total_fathoms() != 24L) return 7;
            return 0;
            """,
            """
            WrapGauge neg(0, 0);
            neg.veer(-1);
            if (neg.wraps() != 49 || neg.fathoms() != 11) return 1;
            if (neg.total_fathoms() != 599L) return 2;
            WrapGauge below(-1, -1);
            if (below.wraps() != 48 || below.fathoms() != 11) return 3;
            WrapGauge g(49, 11);
            g.veer(1);
            if (!g.paid_out()) return 4;
            if (g.total_fathoms() != 0L) return 5;
            g.haul(1);
            if (g.wraps() != 49 || g.fathoms() != 11) return 6;
            g.haul(598);
            if (g.wraps() != 0 || g.fathoms() != 1) return 7;
            g.veer(1199);
            if (!g.paid_out() || g.total_fathoms() != 0L) return 8;
            WrapGauge a(3, 5);
            WrapGauge b(2, 17);
            if (!(a == b)) return 9;
            WrapGauge c(50, 0);
            if (!(c == WrapGauge(0, 0))) return 10;
            if (a == c) return 11;
            WrapGauge p(2, 12);
            if (p.wraps() != 3 || p.fathoms() != 0) return 12;
            if (!p.paid_out()) return 13;
            WrapGauge m(0, 3);
            m.veer(-603);
            if (!m.paid_out()) return 14;
            m.veer(-13);
            if (m.wraps() != 48 || m.fathoms() != 11) return 15;
            return 0;
            """,
            "floor-mod normalization of a 600-fathom two-field capstan cycle with carry and borrow between 12-fathom wraps and fathoms through veer and haul verbs",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative veer borrows, multi-wrap haul crossings, exact wrap/fathom field splits after crossings, paid_out at a zero fathoms field, and representation-blind equality through different routes",
            "distinct base-12 carry/borrow dial with marine nouns",
            "two-field carry/borrow cyclic dial",
        ),
        c(
            "f26clk-potter-wheel-count",
            "Potter wheel count",
            "potter_wheel",
            """
            class WheelCount {
            public:
                WheelCount(int revolutions, int quarters);
                void spin(int quarters);
                int revolutions() const;
                int quarters() const;
                long total_quarters() const;
                bool aligned() const;
                bool equals(const WheelCount& other) const;
            };
            """,
            """
            class WheelCount {
            public:
                WheelCount(int revolutions, int quarters);
                void spin(int quarters);
                int revolutions() const;
                int quarters() const;
                long total_quarters() const;
                bool aligned() const;
                bool equals(const WheelCount& other) const;
            private:
                static constexpr int kQuartersPerRevolution = 4;
                static constexpr int kRevolutionsPerCycle = 500;
                static constexpr long kCycleQuarters = 2000L;
                static long normalize(long total);
                int revolutions_;
                int quarters_;
            };
            """,
            """
            long WheelCount::normalize(long total) {
                long wrapped = total % kCycleQuarters;
                if (wrapped < 0) wrapped += kCycleQuarters;
                return wrapped;
            }
            WheelCount::WheelCount(int revolutions, int quarters) {
                long total = normalize(static_cast<long>(revolutions) * kQuartersPerRevolution + quarters);
                revolutions_ = static_cast<int>(total / kQuartersPerRevolution);
                quarters_ = static_cast<int>(total % kQuartersPerRevolution);
            }
            void WheelCount::spin(int quarters) {
                long total = normalize(total_quarters() + quarters);
                revolutions_ = static_cast<int>(total / kQuartersPerRevolution);
                quarters_ = static_cast<int>(total % kQuartersPerRevolution);
            }
            int WheelCount::revolutions() const { return revolutions_; }
            int WheelCount::quarters() const { return quarters_; }
            long WheelCount::total_quarters() const {
                return static_cast<long>(revolutions_) * kQuartersPerRevolution + quarters_;
            }
            bool WheelCount::aligned() const { return quarters_ == 0; }
            bool WheelCount::equals(const WheelCount& other) const {
                return revolutions_ == other.revolutions_ && quarters_ == other.quarters_;
            }
            """,
            """
            WheelCount::WheelCount(int revolutions, int quarters) {
                long raw = static_cast<long>(quarters);
                long minor = raw % kQuartersPerRevolution;
                if (minor < 0) minor += kQuartersPerRevolution;
                long carry = raw / kQuartersPerRevolution;
                long major = (static_cast<long>(revolutions) + carry) % kRevolutionsPerCycle;
                if (major < 0) major += kRevolutionsPerCycle;
                revolutions_ = static_cast<int>(major);
                quarters_ = static_cast<int>(minor);
            }
            void WheelCount::spin(int quarters) {
                long raw = static_cast<long>(quarters_) + quarters;
                long minor = raw % kQuartersPerRevolution;
                if (minor < 0) minor += kQuartersPerRevolution;
                long carry = raw / kQuartersPerRevolution;
                long major = (static_cast<long>(revolutions_) + carry) % kRevolutionsPerCycle;
                if (major < 0) major += kRevolutionsPerCycle;
                revolutions_ = static_cast<int>(major);
                quarters_ = static_cast<int>(minor);
            }
            int WheelCount::revolutions() const { return revolutions_; }
            int WheelCount::quarters() const { return quarters_; }
            long WheelCount::total_quarters() const {
                return static_cast<long>(revolutions_) * kQuartersPerRevolution + quarters_;
            }
            bool WheelCount::aligned() const { return quarters_ == 0; }
            bool WheelCount::equals(const WheelCount& other) const {
                return revolutions_ == other.revolutions_ && quarters_ == other.quarters_;
            }
            """,
            """
            WheelCount count(3, 1);
            if (count.revolutions() != 3 || count.quarters() != 1) return 1;
            if (count.total_quarters() != 13L) return 2;
            count.spin(6);
            if (count.revolutions() != 4 || count.quarters() != 3) return 3;
            count.spin(-3);
            if (count.revolutions() != 4 || count.quarters() != 0) return 4;
            if (!count.aligned()) return 5;
            WheelCount twin(3, 4);
            if (!count.equals(twin)) return 6;
            if (count.total_quarters() != 16L) return 7;
            return 0;
            """,
            """
            WheelCount under(2, 0);
            under.spin(-1);
            if (under.revolutions() != 1 || under.quarters() != 3) return 1;
            WheelCount neg(-1, -1);
            if (neg.revolutions() != 498 || neg.quarters() != 3) return 2;
            WheelCount w(0, 2);
            w.spin(-2);
            if (w.revolutions() != 0 || w.quarters() != 0) return 3;
            if (!w.aligned()) return 4;
            w.spin(2000);
            if (w.total_quarters() != 0L || !w.aligned()) return 5;
            w.spin(2001);
            if (w.revolutions() != 0 || w.quarters() != 1) return 6;
            w.spin(-5);
            if (w.revolutions() != 499 || w.quarters() != 0) return 7;
            if (!w.aligned()) return 8;
            WheelCount a(7, 3);
            WheelCount b(6, 7);
            if (!a.equals(b)) return 9;
            WheelCount c(500, 0);
            WheelCount origin(0, 0);
            if (!c.equals(origin)) return 10;
            if (a.equals(c)) return 11;
            WheelCount big(-3, 9);
            if (big.revolutions() != 499 || big.quarters() != 1) return 12;
            if (big.total_quarters() != 1997L) return 13;
            WheelCount spinbig(0, 1);
            spinbig.spin(9999);
            if (!spinbig.equals(origin)) return 14;
            return 0;
            """,
            "floor-mod normalization of a 2000-quarter two-field potter-wheel cycle with carry and borrow between revolutions and quarters through one signed spin verb",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "spins past many revolutions in both directions, negative construction, aligned at exact revolution boundaries, and named equals after different spin histories",
            "small-base two-field dial with named equality and no operators",
            "two-field carry/borrow cyclic dial",
        ),
        c(
            "f26clk-observatory-dome-ring",
            "Observatory dome ring",
            "observatory_dome",
            """
            class DomeRing {
            public:
                DomeRing(int segments, int degrees);
                void slew(int degrees);
                int segments() const;
                int degrees() const;
                long total_degrees() const;
                bool at_reference() const;
                bool operator==(const DomeRing& other) const;
            };
            """,
            """
            class DomeRing {
            public:
                DomeRing(int segments, int degrees);
                void slew(int degrees);
                int segments() const;
                int degrees() const;
                long total_degrees() const;
                bool at_reference() const;
                bool operator==(const DomeRing& other) const;
            private:
                static constexpr int kDegreesPerSegment = 30;
                static constexpr int kSegmentsPerRotation = 12;
                static constexpr long kCycleDegrees = 360L;
                static long normalize(long total);
                int segments_;
                int degrees_;
            };
            """,
            """
            long DomeRing::normalize(long total) {
                long wrapped = total % kCycleDegrees;
                if (wrapped < 0) wrapped += kCycleDegrees;
                return wrapped;
            }
            DomeRing::DomeRing(int segments, int degrees) {
                long total = normalize(static_cast<long>(segments) * kDegreesPerSegment + degrees);
                segments_ = static_cast<int>(total / kDegreesPerSegment);
                degrees_ = static_cast<int>(total % kDegreesPerSegment);
            }
            void DomeRing::slew(int degrees) {
                long total = normalize(total_degrees() + degrees);
                segments_ = static_cast<int>(total / kDegreesPerSegment);
                degrees_ = static_cast<int>(total % kDegreesPerSegment);
            }
            int DomeRing::segments() const { return segments_; }
            int DomeRing::degrees() const { return degrees_; }
            long DomeRing::total_degrees() const {
                return static_cast<long>(segments_) * kDegreesPerSegment + degrees_;
            }
            bool DomeRing::at_reference() const { return segments_ == 0 && degrees_ == 0; }
            bool DomeRing::operator==(const DomeRing& other) const {
                return segments_ == other.segments_ && degrees_ == other.degrees_;
            }
            """,
            """
            DomeRing::DomeRing(int segments, int degrees) {
                long raw = static_cast<long>(degrees);
                long minor = raw % kDegreesPerSegment;
                if (minor < 0) minor += kDegreesPerSegment;
                long carry = raw / kDegreesPerSegment;
                if (raw < 0 && raw % kDegreesPerSegment != 0) carry -= 1;
                long major = (static_cast<long>(segments) - carry) % kSegmentsPerRotation;
                if (major < 0) major += kSegmentsPerRotation;
                segments_ = static_cast<int>(major);
                degrees_ = static_cast<int>(minor);
            }
            void DomeRing::slew(int degrees) {
                long raw = static_cast<long>(degrees_) + degrees;
                long minor = raw % kDegreesPerSegment;
                if (minor < 0) minor += kDegreesPerSegment;
                long carry = raw / kDegreesPerSegment;
                if (raw < 0 && raw % kDegreesPerSegment != 0) carry -= 1;
                long major = (static_cast<long>(segments_) - carry) % kSegmentsPerRotation;
                if (major < 0) major += kSegmentsPerRotation;
                segments_ = static_cast<int>(major);
                degrees_ = static_cast<int>(minor);
            }
            int DomeRing::segments() const { return segments_; }
            int DomeRing::degrees() const { return degrees_; }
            long DomeRing::total_degrees() const {
                return static_cast<long>(segments_) * kDegreesPerSegment + degrees_;
            }
            bool DomeRing::at_reference() const { return segments_ == 0 && degrees_ == 0; }
            bool DomeRing::operator==(const DomeRing& other) const {
                return segments_ == other.segments_ && degrees_ == other.degrees_;
            }
            """,
            """
            DomeRing ring(2, 10);
            if (ring.segments() != 2 || ring.degrees() != 10) return 1;
            if (ring.total_degrees() != 70L) return 2;
            ring.slew(15);
            if (ring.segments() != 2 || ring.degrees() != 25) return 3;
            ring.slew(-20);
            if (ring.segments() != 2 || ring.degrees() != 5) return 4;
            if (ring.at_reference()) return 5;
            DomeRing twin(14, 5);
            if (!(ring == twin)) return 6;
            if (ring.total_degrees() != 65L) return 7;
            DomeRing ref(0, 0);
            if (!ref.at_reference()) return 8;
            return 0;
            """,
            """
            DomeRing over(0, 20);
            over.slew(15);
            if (over.segments() != 1 || over.degrees() != 5) return 1;
            over.slew(-10);
            if (over.segments() != 0 || over.degrees() != 25) return 2;
            if (over.at_reference()) return 3;
            DomeRing full(3, 90);
            if (full.segments() != 6 || full.degrees() != 0) return 4;
            DomeRing wrap(11, 25);
            wrap.slew(10);
            if (wrap.segments() != 0 || wrap.degrees() != 5) return 5;
            wrap.slew(-5);
            if (!wrap.at_reference()) return 6;
            if (wrap.total_degrees() != 0L) return 7;
            DomeRing spin(0, 0);
            spin.slew(360);
            if (!spin.at_reference()) return 8;
            spin.slew(-360);
            if (!spin.at_reference()) return 9;
            spin.slew(359);
            if (spin.segments() != 11 || spin.degrees() != 29) return 10;
            spin.slew(1);
            if (!spin.at_reference()) return 11;
            DomeRing a(5, 15);
            DomeRing b(4, 45);
            if (!(a == b)) return 12;
            DomeRing neg1(-1, 15);
            if (neg1.segments() != 11 || neg1.degrees() != 15) return 13;
            spin.slew(-1);
            if (spin.segments() != 11 || spin.degrees() != 29) return 14;
            return 0;
            """,
            "floor-mod normalization of a 360-degree two-field dome rotation with carry and borrow between 30-degree segments and degrees through one signed slew verb",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative slew borrows across segments, full-rotation identity, exact segment/degree split at 359, at_reference at 0 and 360 totals, and equality",
            "base-30 segmented dial with dome-slew vocabulary",
            "two-field carry/borrow cyclic dial",
        ),
        c(
            "f26clk-loom-shuttle-counter",
            "Loom shuttle counter",
            "loom_shuttle",
            """
            class ShuttleCounter {
            public:
                ShuttleCounter(int passes, int picks);
                void weave(int picks);
                int passes() const;
                int picks() const;
                long total_picks() const;
                bool shed_clear() const;
                bool operator==(const ShuttleCounter& other) const;
            };
            """,
            """
            class ShuttleCounter {
            public:
                ShuttleCounter(int passes, int picks);
                void weave(int picks);
                int passes() const;
                int picks() const;
                long total_picks() const;
                bool shed_clear() const;
                bool operator==(const ShuttleCounter& other) const;
            private:
                static constexpr int kPicksPerPass = 8;
                static constexpr int kPassesPerCycle = 96;
                static constexpr long kCyclePicks = 768L;
                static long normalize(long total);
                int passes_;
                int picks_;
            };
            """,
            """
            long ShuttleCounter::normalize(long total) {
                long wrapped = total % kCyclePicks;
                if (wrapped < 0) wrapped += kCyclePicks;
                return wrapped;
            }
            ShuttleCounter::ShuttleCounter(int passes, int picks) {
                long total = normalize(static_cast<long>(passes) * kPicksPerPass + picks);
                passes_ = static_cast<int>(total / kPicksPerPass);
                picks_ = static_cast<int>(total % kPicksPerPass);
            }
            void ShuttleCounter::weave(int picks) {
                long total = normalize(total_picks() + picks);
                passes_ = static_cast<int>(total / kPicksPerPass);
                picks_ = static_cast<int>(total % kPicksPerPass);
            }
            int ShuttleCounter::passes() const { return passes_; }
            int ShuttleCounter::picks() const { return picks_; }
            long ShuttleCounter::total_picks() const {
                return static_cast<long>(passes_) * kPicksPerPass + picks_;
            }
            bool ShuttleCounter::shed_clear() const { return picks_ == 0; }
            bool ShuttleCounter::operator==(const ShuttleCounter& other) const {
                return passes_ == other.passes_ && picks_ == other.picks_;
            }
            """,
            """
            long ShuttleCounter::normalize(long total) {
                long wrapped = total % kCyclePicks;
                if (wrapped < 0) wrapped += kCyclePicks;
                return wrapped;
            }
            ShuttleCounter::ShuttleCounter(int passes, int picks) {
                long total = normalize(static_cast<long>(passes) * kPicksPerPass + picks);
                passes_ = static_cast<int>(total / 10);
                picks_ = static_cast<int>(total % 10);
            }
            void ShuttleCounter::weave(int picks) {
                long total = normalize(total_picks() + picks);
                passes_ = static_cast<int>(total / 10);
                picks_ = static_cast<int>(total % 10);
            }
            int ShuttleCounter::passes() const { return passes_; }
            int ShuttleCounter::picks() const { return picks_; }
            long ShuttleCounter::total_picks() const {
                return static_cast<long>(passes_) * kPicksPerPass + picks_;
            }
            bool ShuttleCounter::shed_clear() const { return picks_ == 0; }
            bool ShuttleCounter::operator==(const ShuttleCounter& other) const {
                return passes_ == other.passes_ && picks_ == other.picks_;
            }
            """,
            """
            ShuttleCounter counter(0, 3);
            if (counter.passes() != 0 || counter.picks() != 3) return 1;
            if (counter.total_picks() != 3L) return 2;
            counter.weave(4);
            if (counter.passes() != 0 || counter.picks() != 7) return 3;
            counter.weave(-2);
            if (counter.passes() != 0 || counter.picks() != 5) return 4;
            if (counter.shed_clear()) return 5;
            ShuttleCounter twin(0, 5);
            if (!(counter == twin)) return 6;
            ShuttleCounter clear(0, 0);
            if (!clear.shed_clear()) return 7;
            return 0;
            """,
            """
            ShuttleCounter c(1, 0);
            if (c.passes() != 1 || c.picks() != 0) return 1;
            if (c.total_picks() != 8L) return 2;
            if (!c.shed_clear()) return 3;
            ShuttleCounter w(2, 5);
            if (w.total_picks() != 21L) return 4;
            w.weave(7);
            if (w.passes() != 3 || w.picks() != 4) return 5;
            w.weave(-20);
            if (w.passes() != 1 || w.picks() != 0) return 6;
            w.weave(-9);
            if (w.passes() != 95 || w.picks() != 7) return 7;
            w.weave(768);
            if (w.passes() != 95 || w.picks() != 7) return 8;
            w.weave(1);
            if (!w.shed_clear() || w.total_picks() != 0L) return 9;
            ShuttleCounter neg(-1, 3);
            if (neg.passes() != 95 || neg.picks() != 3) return 10;
            ShuttleCounter over(96, 0);
            if (!over.shed_clear() || over.total_picks() != 0L) return 11;
            ShuttleCounter a(4, 6);
            ShuttleCounter b(3, 14);
            if (!(a == b)) return 12;
            ShuttleCounter m(0, 1);
            m.weave(1535);
            if (!m.shed_clear()) return 13;
            m.weave(-767);
            if (m.passes() != 0 || m.picks() != 1) return 14;
            return 0;
            """,
            "floor-mod normalization of a 768-pick two-field loom cycle with carry and borrow between passes and picks at base 8 through one signed weave verb",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative weave borrows across multiple passes, over-cycle wraps, shed_clear boundaries at zero picks, and equality",
            "base-8 textile counter with exact field invariants",
            "two-field carry/borrow cyclic dial",
        ),
        c(
            "f26clk-winch-drum-tally",
            "Winch drum tally",
            "winch_drum",
            """
            class DrumTally {
            public:
                DrumTally(int layers, int turns);
                void spool(int turns);
                int layers() const;
                int turns() const;
                long total_turns() const;
                bool layer_zero() const;
                bool operator==(const DrumTally& other) const;
            };
            """,
            """
            class DrumTally {
            public:
                DrumTally(int layers, int turns);
                void spool(int turns);
                int layers() const;
                int turns() const;
                long total_turns() const;
                bool layer_zero() const;
                bool operator==(const DrumTally& other) const;
            private:
                static constexpr int kTurnsPerLayer = 25;
                static constexpr int kLayersPerCycle = 40;
                static constexpr long kCycleTurns = 1000L;
                static long normalize(long total);
                int layers_;
                int turns_;
            };
            """,
            """
            long DrumTally::normalize(long total) {
                long wrapped = total % kCycleTurns;
                if (wrapped < 0) wrapped += kCycleTurns;
                return wrapped;
            }
            DrumTally::DrumTally(int layers, int turns) {
                long total = normalize(static_cast<long>(layers) * kTurnsPerLayer + turns);
                layers_ = static_cast<int>(total / kTurnsPerLayer);
                turns_ = static_cast<int>(total % kTurnsPerLayer);
            }
            void DrumTally::spool(int turns) {
                long total = normalize(total_turns() + turns);
                layers_ = static_cast<int>(total / kTurnsPerLayer);
                turns_ = static_cast<int>(total % kTurnsPerLayer);
            }
            int DrumTally::layers() const { return layers_; }
            int DrumTally::turns() const { return turns_; }
            long DrumTally::total_turns() const {
                return static_cast<long>(layers_) * kTurnsPerLayer + turns_;
            }
            bool DrumTally::layer_zero() const { return turns_ == 0; }
            bool DrumTally::operator==(const DrumTally& other) const {
                return layers_ == other.layers_ && turns_ == other.turns_;
            }
            """,
            """
            long DrumTally::normalize(long total) {
                long wrapped = total % kCycleTurns;
                if (wrapped < 0) wrapped = 0;
                return wrapped;
            }
            DrumTally::DrumTally(int layers, int turns) {
                long total = normalize(static_cast<long>(layers) * kTurnsPerLayer + turns);
                layers_ = static_cast<int>(total / kTurnsPerLayer);
                turns_ = static_cast<int>(total % kTurnsPerLayer);
            }
            void DrumTally::spool(int turns) {
                long total = normalize(total_turns() + turns);
                layers_ = static_cast<int>(total / kTurnsPerLayer);
                turns_ = static_cast<int>(total % kTurnsPerLayer);
            }
            int DrumTally::layers() const { return layers_; }
            int DrumTally::turns() const { return turns_; }
            long DrumTally::total_turns() const {
                return static_cast<long>(layers_) * kTurnsPerLayer + turns_;
            }
            bool DrumTally::layer_zero() const { return turns_ == 0; }
            bool DrumTally::operator==(const DrumTally& other) const {
                return layers_ == other.layers_ && turns_ == other.turns_;
            }
            """,
            """
            DrumTally tally(1, 10);
            if (tally.layers() != 1 || tally.turns() != 10) return 1;
            if (tally.total_turns() != 35L) return 2;
            tally.spool(20);
            if (tally.layers() != 2 || tally.turns() != 5) return 3;
            tally.spool(-30);
            if (tally.layers() != 1 || tally.turns() != 0) return 4;
            if (!tally.layer_zero()) return 5;
            DrumTally twin(0, 25);
            if (!(tally == twin)) return 6;
            return 0;
            """,
            """
            DrumTally below(0, 5);
            below.spool(-10);
            if (below.layers() != 39 || below.turns() != 20) return 1;
            if (below.total_turns() != 995L) return 2;
            DrumTally neg(-1, 0);
            if (neg.layers() != 39 || neg.turns() != 0) return 3;
            if (!neg.layer_zero()) return 4;
            DrumTally w(2, 0);
            w.spool(-75);
            if (w.layers() != 39 || w.turns() != 0) return 5;
            w.spool(1050);
            if (w.layers() != 1 || w.turns() != 0) return 6;
            if (w.total_turns() != 25L) return 7;
            w.spool(-25);
            if (!w.layer_zero() || w.total_turns() != 0L) return 8;
            w.spool(-1);
            if (w.layers() != 39 || w.turns() != 24) return 9;
            DrumTally over(40, 0);
            if (over.total_turns() != 0L) return 10;
            DrumTally a(3, 7);
            DrumTally b(2, 32);
            if (!(a == b)) return 11;
            DrumTally m(1, 1);
            m.spool(1974);
            if (!m.layer_zero() || m.layers() != 0) return 12;
            m.spool(-1001);
            if (m.layers() != 39 || m.turns() != 24) return 13;
            return 0;
            """,
            "floor-mod normalization of a 1000-turn two-field winch cycle with carry and borrow between layers and turns at base 25 through one signed spool verb",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative spool borrows across layers, multi-cycle wraps, layer_zero boundaries at zero turns, and equality",
            "base-25 tally with clamping rejected as the false substitute",
            "two-field carry/borrow cyclic dial",
        ),
        c(
            "f26clk-planetarium-gear-dial",
            "Planetarium gear dial",
            "planetarium_gear",
            """
            class GearDial {
            public:
                GearDial(int cycles, int teeth);
                void rotate(int teeth);
                int cycles() const;
                int teeth() const;
                long total_teeth() const;
                bool mesh_marks() const;
                bool operator==(const GearDial& other) const;
            };
            """,
            """
            class GearDial {
            public:
                GearDial(int cycles, int teeth);
                void rotate(int teeth);
                int cycles() const;
                int teeth() const;
                long total_teeth() const;
                bool mesh_marks() const;
                bool operator==(const GearDial& other) const;
            private:
                static constexpr int kTeethPerCycle = 45;
                static constexpr int kCyclesPerDisplay = 72;
                static constexpr long kCycleTeeth = 3240L;
                static long normalize(long total);
                int cycles_;
                int teeth_;
            };
            """,
            """
            long GearDial::normalize(long total) {
                long wrapped = total % kCycleTeeth;
                if (wrapped < 0) wrapped += kCycleTeeth;
                return wrapped;
            }
            GearDial::GearDial(int cycles, int teeth) {
                long total = normalize(static_cast<long>(cycles) * kTeethPerCycle + teeth);
                cycles_ = static_cast<int>(total / kTeethPerCycle);
                teeth_ = static_cast<int>(total % kTeethPerCycle);
            }
            void GearDial::rotate(int teeth) {
                long total = normalize(total_teeth() + teeth);
                cycles_ = static_cast<int>(total / kTeethPerCycle);
                teeth_ = static_cast<int>(total % kTeethPerCycle);
            }
            int GearDial::cycles() const { return cycles_; }
            int GearDial::teeth() const { return teeth_; }
            long GearDial::total_teeth() const {
                return static_cast<long>(cycles_) * kTeethPerCycle + teeth_;
            }
            bool GearDial::mesh_marks() const { return teeth_ == 0; }
            bool GearDial::operator==(const GearDial& other) const {
                return cycles_ == other.cycles_ && teeth_ == other.teeth_;
            }
            """,
            """
            long GearDial::normalize(long total) {
                long wrapped = total % kCycleTeeth;
                if (wrapped < 0) wrapped += kCycleTeeth;
                return wrapped;
            }
            GearDial::GearDial(int cycles, int teeth) {
                long total = static_cast<long>(cycles) * kTeethPerCycle + teeth;
                long wrapped = normalize(total);
                teeth_ = static_cast<int>(wrapped % kTeethPerCycle);
                long major = (total / kTeethPerCycle) % kCyclesPerDisplay;
                if (major < 0) major += kCyclesPerDisplay;
                cycles_ = static_cast<int>(major);
            }
            void GearDial::rotate(int teeth) {
                long total = total_teeth() + teeth;
                long wrapped = normalize(total);
                teeth_ = static_cast<int>(wrapped % kTeethPerCycle);
                long major = (total / kTeethPerCycle) % kCyclesPerDisplay;
                if (major < 0) major += kCyclesPerDisplay;
                cycles_ = static_cast<int>(major);
            }
            int GearDial::cycles() const { return cycles_; }
            int GearDial::teeth() const { return teeth_; }
            long GearDial::total_teeth() const {
                return static_cast<long>(cycles_) * kTeethPerCycle + teeth_;
            }
            bool GearDial::mesh_marks() const { return teeth_ == 0; }
            bool GearDial::operator==(const GearDial& other) const {
                return cycles_ == other.cycles_ && teeth_ == other.teeth_;
            }
            """,
            """
            GearDial dial(2, 20);
            if (dial.cycles() != 2 || dial.teeth() != 20) return 1;
            if (dial.total_teeth() != 110L) return 2;
            dial.rotate(30);
            if (dial.cycles() != 3 || dial.teeth() != 5) return 3;
            dial.rotate(-50);
            if (dial.cycles() != 2 || dial.teeth() != 0) return 4;
            if (!dial.mesh_marks()) return 5;
            GearDial twin(1, 45);
            if (!(dial == twin)) return 6;
            return 0;
            """,
            """
            GearDial below(0, 10);
            below.rotate(-20);
            if (below.cycles() != 71 || below.teeth() != 35) return 1;
            if (below.total_teeth() != 3230L) return 2;
            GearDial neg(-1, 0);
            if (neg.cycles() != 71 || neg.teeth() != 0) return 3;
            if (!neg.mesh_marks()) return 4;
            GearDial w(1, 0);
            w.rotate(3195);
            if (!w.mesh_marks() || w.cycles() != 0) return 5;
            w.rotate(3241);
            if (w.cycles() != 0 || w.teeth() != 1) return 6;
            w.rotate(-46);
            if (w.cycles() != 71 || w.teeth() != 0) return 7;
            GearDial over(72, 0);
            if (over.total_teeth() != 0L) return 8;
            GearDial a(5, 12);
            GearDial b(4, 57);
            if (!(a == b)) return 9;
            GearDial m(0, 3);
            m.rotate(6477);
            if (!m.mesh_marks() || m.total_teeth() != 0L) return 10;
            m.rotate(-6481);
            if (m.cycles() != 71 || m.teeth() != 44) return 11;
            m.rotate(44);
            if (m.cycles() != 0 || m.teeth() != 43) return 12;
            return 0;
            """,
            "floor-mod normalization of a 3240-tooth two-field planetarium display with carry and borrow between 45-tooth gear cycles and teeth through one signed rotate verb",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative rotate borrows, large positive rotations over multiple display cycles, mesh_marks boundaries at zero teeth, and equality",
            "large-base gear dial stressing carry in both directions",
            "two-field carry/borrow cyclic dial",
        ),
        c(
            "f26clk-canal-crane-slew",
            "Canal crane slew",
            "canal_crane",
            """
            class SlewGauge {
            public:
                SlewGauge(int arcs, int grads);
                void swing(int grads);
                int arcs() const;
                int grads() const;
                long total_grads() const;
                bool northbound() const;
                bool operator==(const SlewGauge& other) const;
            };
            """,
            """
            class SlewGauge {
            public:
                SlewGauge(int arcs, int grads);
                void swing(int grads);
                int arcs() const;
                int grads() const;
                long total_grads() const;
                bool northbound() const;
                bool operator==(const SlewGauge& other) const;
            private:
                static constexpr int kGradsPerArc = 100;
                static constexpr int kArcsPerCycle = 4;
                static constexpr long kCycleGrads = 400L;
                static long normalize(long total);
                int arcs_;
                int grads_;
            };
            """,
            """
            long SlewGauge::normalize(long total) {
                long wrapped = total % kCycleGrads;
                if (wrapped < 0) wrapped += kCycleGrads;
                return wrapped;
            }
            SlewGauge::SlewGauge(int arcs, int grads) {
                long total = normalize(static_cast<long>(arcs) * kGradsPerArc + grads);
                arcs_ = static_cast<int>(total / kGradsPerArc);
                grads_ = static_cast<int>(total % kGradsPerArc);
            }
            void SlewGauge::swing(int grads) {
                long total = normalize(total_grads() + grads);
                arcs_ = static_cast<int>(total / kGradsPerArc);
                grads_ = static_cast<int>(total % kGradsPerArc);
            }
            int SlewGauge::arcs() const { return arcs_; }
            int SlewGauge::grads() const { return grads_; }
            long SlewGauge::total_grads() const {
                return static_cast<long>(arcs_) * kGradsPerArc + grads_;
            }
            bool SlewGauge::northbound() const { return arcs_ == 0; }
            bool SlewGauge::operator==(const SlewGauge& other) const {
                return arcs_ == other.arcs_ && grads_ == other.grads_;
            }
            """,
            """
            long SlewGauge::normalize(long total) {
                return total % kCycleGrads;
            }
            SlewGauge::SlewGauge(int arcs, int grads) {
                long total = normalize(static_cast<long>(arcs) * kGradsPerArc + grads);
                arcs_ = static_cast<int>(total / kGradsPerArc);
                grads_ = static_cast<int>(total % kGradsPerArc);
            }
            void SlewGauge::swing(int grads) {
                long total = normalize(total_grads() + grads);
                arcs_ = static_cast<int>(total / kGradsPerArc);
                grads_ = static_cast<int>(total % kGradsPerArc);
            }
            int SlewGauge::arcs() const { return arcs_; }
            int SlewGauge::grads() const { return grads_; }
            long SlewGauge::total_grads() const {
                return static_cast<long>(arcs_) * kGradsPerArc + grads_;
            }
            bool SlewGauge::northbound() const { return arcs_ == 0; }
            bool SlewGauge::operator==(const SlewGauge& other) const {
                return arcs_ == other.arcs_ && grads_ == other.grads_;
            }
            """,
            """
            SlewGauge gauge(1, 50);
            if (gauge.arcs() != 1 || gauge.grads() != 50) return 1;
            if (gauge.total_grads() != 150L) return 2;
            gauge.swing(75);
            if (gauge.arcs() != 2 || gauge.grads() != 25) return 3;
            gauge.swing(-125);
            if (gauge.arcs() != 1 || gauge.grads() != 0) return 4;
            if (gauge.northbound()) return 5;
            gauge.swing(-100);
            if (!gauge.northbound()) return 6;
            SlewGauge twin(0, 0);
            if (!(gauge == twin)) return 7;
            return 0;
            """,
            """
            SlewGauge below(0, 10);
            below.swing(-20);
            if (below.arcs() != 3 || below.grads() != 90) return 1;
            if (below.total_grads() != 390L) return 2;
            SlewGauge neg(-1, -50);
            if (neg.arcs() != 2 || neg.grads() != 50) return 3;
            SlewGauge w(3, 75);
            w.swing(25);
            if (!w.northbound() || w.total_grads() != 0L) return 4;
            w.swing(401);
            if (w.arcs() != 0 || w.grads() != 1) return 5;
            w.swing(-2);
            if (w.arcs() != 3 || w.grads() != 99) return 6;
            if (w.northbound()) return 7;
            SlewGauge over(4, 0);
            if (over.total_grads() != 0L || !over.northbound()) return 8;
            SlewGauge a(2, 33);
            SlewGauge b(1, 133);
            if (!(a == b)) return 9;
            SlewGauge m(0, 5);
            m.swing(795);
            if (!m.northbound()) return 10;
            m.swing(-801);
            if (m.arcs() != 3 || m.grads() != 99) return 11;
            if (m.total_grads() != 399L) return 12;
            return 0;
            """,
            "floor-mod normalization of a 400-grad two-field crane swing cycle with carry and borrow between 100-grad arcs and grads through one signed swing verb",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative swing borrows across arcs, 400-grad identity, northbound boundaries at zero arcs, and equality",
            "base-100 gradian dial distinct from degree-based roots",
            "two-field carry/borrow cyclic dial",
        ),
        c(
            "f26clk-rail-turntable-index",
            "Rail turntable index",
            "rail_turntable",
            """
            class TurntableIndex {
            public:
                TurntableIndex(int quadrants, int degrees);
                void rotate(int degrees);
                int quadrants() const;
                int degrees() const;
                long total_degrees() const;
                bool on_zero() const;
                bool operator==(const TurntableIndex& other) const;
            };
            """,
            """
            class TurntableIndex {
            public:
                TurntableIndex(int quadrants, int degrees);
                void rotate(int degrees);
                int quadrants() const;
                int degrees() const;
                long total_degrees() const;
                bool on_zero() const;
                bool operator==(const TurntableIndex& other) const;
            private:
                static constexpr int kDegreesPerQuadrant = 90;
                static constexpr int kQuadrantsPerTurn = 4;
                static constexpr long kCycleDegrees = 360L;
                static long normalize(long total);
                int quadrants_;
                int degrees_;
            };
            """,
            """
            long TurntableIndex::normalize(long total) {
                long wrapped = total % kCycleDegrees;
                if (wrapped < 0) wrapped += kCycleDegrees;
                return wrapped;
            }
            TurntableIndex::TurntableIndex(int quadrants, int degrees) {
                long total = normalize(static_cast<long>(quadrants) * kDegreesPerQuadrant + degrees);
                quadrants_ = static_cast<int>(total / kDegreesPerQuadrant);
                degrees_ = static_cast<int>(total % kDegreesPerQuadrant);
            }
            void TurntableIndex::rotate(int degrees) {
                long total = normalize(total_degrees() + degrees);
                quadrants_ = static_cast<int>(total / kDegreesPerQuadrant);
                degrees_ = static_cast<int>(total % kDegreesPerQuadrant);
            }
            int TurntableIndex::quadrants() const { return quadrants_; }
            int TurntableIndex::degrees() const { return degrees_; }
            long TurntableIndex::total_degrees() const {
                return static_cast<long>(quadrants_) * kDegreesPerQuadrant + degrees_;
            }
            bool TurntableIndex::on_zero() const { return quadrants_ == 0 && degrees_ == 0; }
            bool TurntableIndex::operator==(const TurntableIndex& other) const {
                return quadrants_ == other.quadrants_ && degrees_ == other.degrees_;
            }
            """,
            """
            long TurntableIndex::normalize(long total) {
                long wrapped = total % kCycleDegrees;
                if (wrapped < 0) wrapped += kCycleDegrees;
                return wrapped;
            }
            TurntableIndex::TurntableIndex(int quadrants, int degrees) {
                long total = normalize(static_cast<long>(quadrants) * kDegreesPerQuadrant + degrees);
                quadrants_ = static_cast<int>(total / 89);
                degrees_ = static_cast<int>(total % 89);
            }
            void TurntableIndex::rotate(int degrees) {
                long total = normalize(total_degrees() + degrees);
                quadrants_ = static_cast<int>(total / 89);
                degrees_ = static_cast<int>(total % 89);
            }
            int TurntableIndex::quadrants() const { return quadrants_; }
            int TurntableIndex::degrees() const { return degrees_; }
            long TurntableIndex::total_degrees() const {
                return static_cast<long>(quadrants_) * kDegreesPerQuadrant + degrees_;
            }
            bool TurntableIndex::on_zero() const { return quadrants_ == 0 && degrees_ == 0; }
            bool TurntableIndex::operator==(const TurntableIndex& other) const {
                return quadrants_ == other.quadrants_ && degrees_ == other.degrees_;
            }
            """,
            """
            TurntableIndex index(0, 45);
            if (index.quadrants() != 0 || index.degrees() != 45) return 1;
            if (index.total_degrees() != 45L) return 2;
            index.rotate(30);
            if (index.quadrants() != 0 || index.degrees() != 75) return 3;
            index.rotate(-15);
            if (index.quadrants() != 0 || index.degrees() != 60) return 4;
            if (index.on_zero()) return 5;
            TurntableIndex twin(0, 60);
            if (!(index == twin)) return 6;
            TurntableIndex zero(0, 0);
            if (!zero.on_zero()) return 7;
            return 0;
            """,
            """
            TurntableIndex q(1, 0);
            if (q.quadrants() != 1 || q.degrees() != 0) return 1;
            if (q.total_degrees() != 90L) return 2;
            TurntableIndex w(0, 80);
            w.rotate(20);
            if (w.quadrants() != 1 || w.degrees() != 10) return 3;
            w.rotate(-100);
            if (!w.on_zero()) return 4;
            w.rotate(-1);
            if (w.quadrants() != 3 || w.degrees() != 89) return 5;
            w.rotate(271);
            if (w.quadrants() != 3 || w.degrees() != 0) return 6;
            if (w.on_zero()) return 7;
            TurntableIndex over(4, 0);
            if (!over.on_zero() || over.total_degrees() != 0L) return 8;
            TurntableIndex half(0, 180);
            if (half.quadrants() != 2 || half.degrees() != 0) return 9;
            TurntableIndex neg(-1, 45);
            if (neg.quadrants() != 3 || neg.degrees() != 45) return 10;
            TurntableIndex a(2, 30);
            TurntableIndex b(1, 120);
            if (!(a == b)) return 11;
            TurntableIndex m(0, 10);
            m.rotate(710);
            if (!m.on_zero()) return 12;
            m.rotate(-725);
            if (m.quadrants() != 3 || m.degrees() != 85) return 13;
            return 0;
            """,
            "floor-mod normalization of a 360-degree two-field turntable index with carry and borrow between 90-degree quadrants and degrees through one signed rotate verb",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative rotate borrows, exact 90/180/270 quadrant boundaries, on_zero at 0 and 360 totals, and equality after different rotation histories",
            "base-90 quadrant index with boundary-exact carry",
            "two-field carry/borrow cyclic dial",
        ),

        c(
            "f26clk-lighthouse-beam-sweep",
            "Lighthouse beam sweep",
            "lighthouse_beam",
            """
            class BeamSweep {
            public:
                explicit BeamSweep(int azimuth);
                int sweep(int degrees);
                int azimuth() const;
                int laps_forward() const;
                int laps_reverse() const;
                std::vector<std::string> journal() const;
                bool operator==(const BeamSweep& other) const;
            };
            """,
            """
            class BeamSweep {
            public:
                explicit BeamSweep(int azimuth);
                int sweep(int degrees);
                int azimuth() const;
                int laps_forward() const;
                int laps_reverse() const;
                std::vector<std::string> journal() const;
                bool operator==(const BeamSweep& other) const;
            private:
                static constexpr int kCycle = 360;
                static int normalize(int degrees);
                int azimuth_;
                int forward_;
                int reverse_;
                std::vector<std::string> journal_;
            };
            """,
            """
            int BeamSweep::normalize(int degrees) {
                int wrapped = degrees % kCycle;
                if (wrapped < 0) wrapped += kCycle;
                return wrapped;
            }
            BeamSweep::BeamSweep(int azimuth)
                : azimuth_(normalize(azimuth)), forward_(0), reverse_(0) {}
            int BeamSweep::sweep(int degrees) {
                int raw = azimuth_ + degrees;
                int crossings = raw / kCycle;
                if (raw % kCycle != 0 && raw < 0) crossings -= 1;
                azimuth_ = normalize(raw);
                for (int i = 0; i < crossings; ++i) {
                    forward_ += 1;
                    journal_.push_back("F" + std::to_string(forward_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    reverse_ += 1;
                    journal_.push_back("R" + std::to_string(reverse_));
                }
                return crossings;
            }
            int BeamSweep::azimuth() const { return azimuth_; }
            int BeamSweep::laps_forward() const { return forward_; }
            int BeamSweep::laps_reverse() const { return reverse_; }
            std::vector<std::string> BeamSweep::journal() const { return journal_; }
            bool BeamSweep::operator==(const BeamSweep& other) const {
                return azimuth_ == other.azimuth_;
            }
            """,
            """
            int BeamSweep::normalize(int degrees) {
                int wrapped = degrees % kCycle;
                if (wrapped < 0) wrapped += kCycle;
                return wrapped;
            }
            BeamSweep::BeamSweep(int azimuth)
                : azimuth_(normalize(azimuth)), forward_(0), reverse_(0) {}
            int BeamSweep::sweep(int degrees) {
                int raw = azimuth_ + degrees;
                int crossings = raw / kCycle;
                if (raw % kCycle != 0 && raw < 0) crossings -= 1;
                azimuth_ = normalize(raw);
                return crossings;
            }
            int BeamSweep::azimuth() const { return azimuth_; }
            int BeamSweep::laps_forward() const { return forward_; }
            int BeamSweep::laps_reverse() const { return reverse_; }
            std::vector<std::string> BeamSweep::journal() const { return journal_; }
            bool BeamSweep::operator==(const BeamSweep& other) const {
                return azimuth_ == other.azimuth_;
            }
            """,
            """
            BeamSweep beam(10);
            if (beam.azimuth() != 10) return 1;
            if (beam.sweep(40) != 0) return 2;
            if (beam.azimuth() != 50) return 3;
            if (beam.sweep(370) != 1) return 4;
            if (beam.azimuth() != 60) return 5;
            BeamSweep other(420);
            if (!(beam == other)) return 6;
            if (beam.sweep(-30) != 0) return 7;
            if (beam.azimuth() != 30) return 8;
            return 0;
            """,
            """
            BeamSweep beam(350);
            if (beam.sweep(20) != 1) return 1;
            if (beam.azimuth() != 10) return 2;
            if (beam.sweep(-30) != -1) return 3;
            if (beam.azimuth() != 340) return 4;
            if (beam.laps_forward() != 1) return 5;
            if (beam.laps_reverse() != 1) return 6;
            std::vector<std::string> log = beam.journal();
            if (log.size() != 2U) return 7;
            if (log[0] != "F1" || log[1] != "R1") return 8;
            if (beam.sweep(720) != 2) return 9;
            if (beam.laps_forward() != 3) return 10;
            log = beam.journal();
            if (log.size() != 4U || log[2] != "F2" || log[3] != "F3") return 11;
            BeamSweep fresh(-10);
            if (fresh.azimuth() != 350) return 12;
            if (fresh.sweep(-720) != -2) return 13;
            if (fresh.laps_reverse() != 2) return 14;
            BeamSweep twin(340);
            if (!(beam == twin)) return 15;
            return 0;
            """,
            "floor-mod 360-degree beam cycle with per-call signed crossing returns, forward/reverse lap counters, and an exact wrap journal",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or dropping wrap history",
            "multi-rotation sweeps in both directions, exact journal text and order, lap counters, and position-only equality",
            "wrap-event observability (day-wrap analog) with position-only equality in a paired .h/.cpp API",
            "single-cycle wheel with wrap-event journal",
        ),
        c(
            "f26clk-ferry-berth-rota",
            "Ferry berth rota",
            "ferry_berth",
            """
            class BerthRota {
            public:
                explicit BerthRota(int berth);
                int shift(int berths);
                int berth() const;
                int dockings() const;
                std::vector<std::string> log() const;
                bool same_berth(const BerthRota& other) const;
            };
            """,
            """
            class BerthRota {
            public:
                explicit BerthRota(int berth);
                int shift(int berths);
                int berth() const;
                int dockings() const;
                std::vector<std::string> log() const;
                bool same_berth(const BerthRota& other) const;
            private:
                static constexpr int kBerths = 10;
                static int normalize(int berth);
                int berth_;
                std::vector<std::string> log_;
            };
            """,
            """
            int BerthRota::normalize(int berth) {
                int wrapped = berth % kBerths;
                if (wrapped < 0) wrapped += kBerths;
                return wrapped;
            }
            BerthRota::BerthRota(int berth) : berth_(normalize(berth)) {}
            int BerthRota::shift(int berths) {
                int raw = berth_ + berths;
                int crossings = raw / kBerths;
                if (raw % kBerths != 0 && raw < 0) crossings -= 1;
                berth_ = normalize(raw);
                int total = crossings < 0 ? -crossings : crossings;
                for (int i = 0; i < total; ++i) {
                    log_.push_back("dock+" + std::to_string(log_.size() + 1) +
                                   "@b" + std::to_string(berth_));
                }
                return crossings;
            }
            int BerthRota::berth() const { return berth_; }
            int BerthRota::dockings() const { return static_cast<int>(log_.size()); }
            std::vector<std::string> BerthRota::log() const { return log_; }
            bool BerthRota::same_berth(const BerthRota& other) const {
                return berth_ == other.berth_;
            }
            """,
            """
            int BerthRota::normalize(int berth) {
                int wrapped = berth % kBerths;
                if (wrapped < 0) wrapped += kBerths;
                return wrapped;
            }
            BerthRota::BerthRota(int berth) : berth_(normalize(berth)) {}
            int BerthRota::shift(int berths) {
                int raw = berth_ + berths;
                int crossings = raw / kBerths;
                berth_ = normalize(raw);
                int total = crossings < 0 ? -crossings : crossings;
                for (int i = 0; i < total; ++i) {
                    log_.push_back("dock+" + std::to_string(log_.size() + 1) +
                                   "@b" + std::to_string(berth_));
                }
                return crossings;
            }
            int BerthRota::berth() const { return berth_; }
            int BerthRota::dockings() const { return static_cast<int>(log_.size()); }
            std::vector<std::string> BerthRota::log() const { return log_; }
            bool BerthRota::same_berth(const BerthRota& other) const {
                return berth_ == other.berth_;
            }
            """,
            """
            BerthRota rota(3);
            if (rota.berth() != 3) return 1;
            if (rota.shift(4) != 0) return 2;
            if (rota.berth() != 7) return 3;
            if (rota.shift(15) != 2) return 4;
            if (rota.berth() != 2) return 5;
            if (rota.dockings() != 2) return 6;
            BerthRota twin(12);
            if (!rota.same_berth(twin)) return 7;
            std::vector<std::string> log = rota.log();
            if (log.size() != 2U) return 8;
            if (log[0] != "dock+1@b2" || log[1] != "dock+2@b2") return 9;
            return 0;
            """,
            """
            BerthRota rota(4);
            if (rota.shift(-7) != -1) return 1;
            if (rota.berth() != 7) return 2;
            if (rota.dockings() != 1) return 3;
            std::vector<std::string> log = rota.log();
            if (log.size() != 1U || log[0] != "dock+1@b7") return 4;
            if (rota.shift(23) != 3) return 5;
            if (rota.berth() != 0) return 6;
            if (rota.dockings() != 4) return 7;
            log = rota.log();
            if (log.size() != 4U) return 8;
            if (log[1] != "dock+2@b0" || log[3] != "dock+4@b0") return 9;
            BerthRota fresh(-3);
            if (fresh.berth() != 7) return 10;
            if (fresh.shift(-20) != -2) return 11;
            if (fresh.berth() != 7) return 12;
            if (fresh.dockings() != 2) return 13;
            BerthRota twin(17);
            if (!fresh.same_berth(twin)) return 14;
            if (rota.same_berth(fresh)) return 15;
            return 0;
            """,
            "floor-mod 10-berth rota cycle with per-call signed docking returns, a running docking count, and an exact dock+n@b<berth> transition log",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or dropping wrap history",
            "negative shifts past the origin, multi-loop shifts, exact log text and order, docking counts, and named same_berth position equality",
            "ten-berth roster cycle with a formatted transition log and named equality in a paired .h/.cpp API",
            "single-cycle wheel with wrap-event journal",
        ),
        c(
            "f26clk-mill-stone-runner",
            "Mill stone runner",
            "mill_stone",
            """
            class StoneRunner {
            public:
                explicit StoneRunner(int grad);
                int turn(int grads);
                int grad() const;
                int circuits_forward() const;
                int circuits_reverse() const;
                std::vector<std::string> trace() const;
                bool operator==(const StoneRunner& other) const;
            };
            """,
            """
            class StoneRunner {
            public:
                explicit StoneRunner(int grad);
                int turn(int grads);
                int grad() const;
                int circuits_forward() const;
                int circuits_reverse() const;
                std::vector<std::string> trace() const;
                bool operator==(const StoneRunner& other) const;
            private:
                static constexpr int kCycle = 200;
                static int normalize(int grad);
                int grad_;
                int forward_;
                int reverse_;
                std::vector<std::string> trace_;
            };
            """,
            """
            int StoneRunner::normalize(int grad) {
                int wrapped = grad % kCycle;
                if (wrapped < 0) wrapped += kCycle;
                return wrapped;
            }
            StoneRunner::StoneRunner(int grad)
                : grad_(normalize(grad)), forward_(0), reverse_(0) {}
            int StoneRunner::turn(int grads) {
                int raw = grad_ + grads;
                int crossings = raw / kCycle;
                if (raw % kCycle != 0 && raw < 0) crossings -= 1;
                grad_ = normalize(raw);
                for (int i = 0; i < crossings; ++i) {
                    forward_ += 1;
                    trace_.push_back("fwd#" + std::to_string(forward_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    reverse_ += 1;
                    trace_.push_back("rev#" + std::to_string(reverse_));
                }
                return crossings;
            }
            int StoneRunner::grad() const { return grad_; }
            int StoneRunner::circuits_forward() const { return forward_; }
            int StoneRunner::circuits_reverse() const { return reverse_; }
            std::vector<std::string> StoneRunner::trace() const { return trace_; }
            bool StoneRunner::operator==(const StoneRunner& other) const {
                return grad_ == other.grad_;
            }
            """,
            """
            int StoneRunner::normalize(int grad) {
                int wrapped = grad % kCycle;
                if (wrapped < 0) wrapped += kCycle;
                return wrapped;
            }
            StoneRunner::StoneRunner(int grad)
                : grad_(normalize(grad)), forward_(0), reverse_(0) {}
            int StoneRunner::turn(int grads) {
                int raw = grad_ + grads;
                int crossings = raw / kCycle;
                if (raw % kCycle != 0 && raw < 0) crossings -= 1;
                grad_ = normalize(raw);
                for (int i = 0; i < crossings; ++i) {
                    forward_ += 1;
                    trace_.push_back("fwd#" + std::to_string(forward_));
                }
                return crossings;
            }
            int StoneRunner::grad() const { return grad_; }
            int StoneRunner::circuits_forward() const { return forward_; }
            int StoneRunner::circuits_reverse() const { return reverse_; }
            std::vector<std::string> StoneRunner::trace() const { return trace_; }
            bool StoneRunner::operator==(const StoneRunner& other) const {
                return grad_ == other.grad_;
            }
            """,
            """
            StoneRunner stone(40);
            if (stone.grad() != 40) return 1;
            if (stone.turn(50) != 0) return 2;
            if (stone.grad() != 90) return 3;
            if (stone.turn(210) != 1) return 4;
            if (stone.grad() != 100) return 5;
            if (stone.circuits_forward() != 1) return 6;
            StoneRunner twin(300);
            if (!(stone == twin)) return 7;
            std::vector<std::string> trace = stone.trace();
            if (trace.size() != 1U || trace[0] != "fwd#1") return 8;
            return 0;
            """,
            """
            StoneRunner stone(190);
            if (stone.turn(30) != 1) return 1;
            if (stone.grad() != 20) return 2;
            if (stone.turn(-50) != -1) return 3;
            if (stone.grad() != 170) return 4;
            if (stone.circuits_forward() != 1) return 5;
            if (stone.circuits_reverse() != 1) return 6;
            std::vector<std::string> trace = stone.trace();
            if (trace.size() != 2U) return 7;
            if (trace[0] != "fwd#1" || trace[1] != "rev#1") return 8;
            if (stone.turn(400) != 2) return 9;
            if (stone.circuits_forward() != 3) return 10;
            trace = stone.trace();
            if (trace.size() != 4U || trace[2] != "fwd#2" || trace[3] != "fwd#3") return 11;
            StoneRunner fresh(-30);
            if (fresh.grad() != 170) return 12;
            if (fresh.turn(-410) != -2) return 13;
            if (fresh.grad() != 160) return 14;
            if (fresh.circuits_reverse() != 2) return 15;
            trace = fresh.trace();
            if (trace.size() != 2U || trace[0] != "rev#1" || trace[1] != "rev#2") return 16;
            StoneRunner twin(160);
            if (!(fresh == twin)) return 17;
            return 0;
            """,
            "floor-mod 200-grad stone cycle with per-call signed circuit returns, forward/reverse circuit counters, and an exact fwd#k/rev#k wrap trace",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or dropping wrap history",
            "200-grad identity turns, negative turns, per-direction counters, exact trace text and order, and grad-only equality",
            "gradian-cycle stone with directional wrap counters in a paired .h/.cpp API",
            "single-cycle wheel with wrap-event journal",
        ),
        c(
            "f26clk-ski-patrol-loop",
            "Ski patrol loop",
            "ski_patrol",
            """
            class PatrolLoop {
            public:
                explicit PatrolLoop(int post);
                int patrol(int posts);
                int post() const;
                int rounds() const;
                std::vector<std::string> sweep_log() const;
                bool at_post(int post) const;
            };
            """,
            """
            class PatrolLoop {
            public:
                explicit PatrolLoop(int post);
                int patrol(int posts);
                int post() const;
                int rounds() const;
                std::vector<std::string> sweep_log() const;
                bool at_post(int post) const;
            private:
                static constexpr int kPosts = 14;
                static int normalize(int post);
                int post_;
                int rounds_;
                std::vector<std::string> log_;
            };
            """,
            """
            int PatrolLoop::normalize(int post) {
                int wrapped = post % kPosts;
                if (wrapped < 0) wrapped += kPosts;
                return wrapped;
            }
            PatrolLoop::PatrolLoop(int post) : post_(normalize(post)), rounds_(0) {}
            int PatrolLoop::patrol(int posts) {
                int raw = post_ + posts;
                int crossings = raw / kPosts;
                if (raw % kPosts != 0 && raw < 0) crossings -= 1;
                post_ = normalize(raw);
                for (int i = 0; i < crossings; ++i) {
                    rounds_ += 1;
                    log_.push_back("post" + std::to_string(post_) +
                                   "@round" + std::to_string(rounds_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    rounds_ -= 1;
                    log_.push_back("post" + std::to_string(post_) +
                                   "@round" + std::to_string(rounds_));
                }
                return crossings;
            }
            int PatrolLoop::post() const { return post_; }
            int PatrolLoop::rounds() const { return rounds_; }
            std::vector<std::string> PatrolLoop::sweep_log() const { return log_; }
            bool PatrolLoop::at_post(int post) const { return post_ == normalize(post); }
            """,
            """
            int PatrolLoop::normalize(int post) {
                int wrapped = post % kPosts;
                if (wrapped < 0) wrapped += kPosts;
                return wrapped;
            }
            PatrolLoop::PatrolLoop(int post) : post_(normalize(post)), rounds_(0) {}
            int PatrolLoop::patrol(int posts) {
                int raw = post_ + posts;
                int crossings = raw / kPosts;
                if (raw % kPosts != 0 && raw < 0) crossings -= 1;
                post_ = normalize(raw);
                rounds_ += 1;
                int total = crossings < 0 ? -crossings : crossings;
                for (int i = 0; i < total; ++i) {
                    log_.push_back("post" + std::to_string(post_) +
                                   "@round" + std::to_string(rounds_));
                }
                return crossings;
            }
            int PatrolLoop::post() const { return post_; }
            int PatrolLoop::rounds() const { return rounds_; }
            std::vector<std::string> PatrolLoop::sweep_log() const { return log_; }
            bool PatrolLoop::at_post(int post) const { return post_ == normalize(post); }
            """,
            """
            PatrolLoop loop(3);
            if (loop.post() != 3) return 1;
            if (loop.patrol(4) != 0) return 2;
            if (loop.post() != 7) return 3;
            if (!loop.at_post(7)) return 4;
            if (loop.at_post(8)) return 5;
            if (loop.patrol(11) != 1) return 6;
            if (loop.post() != 4) return 7;
            if (loop.patrol(-2) != 0) return 8;
            if (!loop.at_post(2)) return 9;
            return 0;
            """,
            """
            PatrolLoop loop(12);
            if (loop.patrol(5) != 1) return 1;
            if (loop.rounds() != 1) return 2;
            std::vector<std::string> log = loop.sweep_log();
            if (log.size() != 1U || log[0] != "post3@round1") return 3;
            if (loop.patrol(-6) != -1) return 4;
            if (loop.post() != 11) return 5;
            if (loop.rounds() != 0) return 6;
            log = loop.sweep_log();
            if (log.size() != 2U || log[1] != "post11@round0") return 7;
            if (loop.patrol(30) != 2) return 8;
            if (loop.post() != 13) return 9;
            if (loop.rounds() != 2) return 10;
            log = loop.sweep_log();
            if (log.size() != 4U || log[2] != "post13@round1" || log[3] != "post13@round2") return 11;
            if (!loop.at_post(13)) return 12;
            if (loop.at_post(0)) return 13;
            PatrolLoop fresh(-4);
            if (fresh.post() != 10) return 14;
            if (fresh.rounds() != 0) return 15;
            if (fresh.patrol(-11) != -1) return 16;
            if (fresh.post() != 13) return 17;
            if (fresh.rounds() != -1) return 18;
            log = fresh.sweep_log();
            if (log.size() != 1U || log[0] != "post13@round-1") return 19;
            return 0;
            """,
            "floor-mod 14-post patrol cycle with signed origin-crossing round accounting, an exact post<p>@round<r> sweep log, and a normalizing at_post query",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or dropping wrap history",
            "forward rounds across many loops, backward origin crossings, exact sweep-log text and order, and at_post boundary checks",
            "checkpoint loop with per-call round accounting in a paired .h/.cpp API",
            "single-cycle wheel with wrap-event journal",
        ),
        c(
            "f26clk-harbor-tide-bell",
            "Harbor tide bell",
            "harbor_tide",
            """
            class TideBell {
            public:
                explicit TideBell(int phase);
                void ebb(int phases);
                void flow(int phases);
                int phase() const;
                int crossings() const;
                std::vector<std::string> chime_log() const;
                bool operator==(const TideBell& other) const;
            };
            """,
            """
            class TideBell {
            public:
                explicit TideBell(int phase);
                void ebb(int phases);
                void flow(int phases);
                int phase() const;
                int crossings() const;
                std::vector<std::string> chime_log() const;
                bool operator==(const TideBell& other) const;
            private:
                static constexpr int kPhases = 8;
                static int normalize(int phase);
                void chime(int offset, const std::string& verb);
                int phase_;
                int chimes_;
                std::vector<std::string> log_;
            };
            """,
            """
            int TideBell::normalize(int phase) {
                int wrapped = phase % kPhases;
                if (wrapped < 0) wrapped += kPhases;
                return wrapped;
            }
            TideBell::TideBell(int phase) : phase_(normalize(phase)), chimes_(0) {}
            void TideBell::chime(int offset, const std::string& verb) {
                int raw = phase_ + offset;
                int crossings = raw / kPhases;
                if (raw % kPhases != 0 && raw < 0) crossings -= 1;
                phase_ = normalize(raw);
                int total = crossings < 0 ? -crossings : crossings;
                for (int i = 0; i < total; ++i) {
                    chimes_ += 1;
                    log_.push_back("chime:" + verb + ":" + std::to_string(chimes_));
                }
            }
            void TideBell::ebb(int phases) { chime(-phases, "ebb"); }
            void TideBell::flow(int phases) { chime(phases, "flow"); }
            int TideBell::phase() const { return phase_; }
            int TideBell::crossings() const { return chimes_; }
            std::vector<std::string> TideBell::chime_log() const { return log_; }
            bool TideBell::operator==(const TideBell& other) const {
                return phase_ == other.phase_;
            }
            """,
            """
            int TideBell::normalize(int phase) {
                int wrapped = phase % kPhases;
                if (wrapped < 0) wrapped += kPhases;
                return wrapped;
            }
            TideBell::TideBell(int phase) : phase_(normalize(phase)), chimes_(0) {}
            void TideBell::chime(int offset, const std::string& verb) {
                int raw = phase_ + offset;
                int crossings = raw / kPhases;
                if (raw % kPhases != 0 && raw < 0) crossings -= 1;
                phase_ = normalize(raw);
                int total = crossings < 0 ? -crossings : crossings;
                for (int i = 0; i < total; ++i) {
                    chimes_ += 1;
                    log_.push_back("chime:" + verb + ":" + std::to_string(chimes_));
                }
            }
            void TideBell::ebb(int phases) { chime(-phases, "flow"); }
            void TideBell::flow(int phases) { chime(phases, "ebb"); }
            int TideBell::phase() const { return phase_; }
            int TideBell::crossings() const { return chimes_; }
            std::vector<std::string> TideBell::chime_log() const { return log_; }
            bool TideBell::operator==(const TideBell& other) const {
                return phase_ == other.phase_;
            }
            """,
            """
            TideBell bell(2);
            if (bell.phase() != 2) return 1;
            bell.flow(3);
            if (bell.phase() != 5) return 2;
            bell.ebb(4);
            if (bell.phase() != 1) return 3;
            bell.flow(9);
            if (bell.phase() != 2) return 4;
            if (bell.crossings() != 1) return 5;
            TideBell twin(10);
            if (!(bell == twin)) return 6;
            return 0;
            """,
            """
            TideBell bell(6);
            bell.ebb(9);
            if (bell.phase() != 5) return 1;
            if (bell.crossings() != 1) return 2;
            std::vector<std::string> log = bell.chime_log();
            if (log.size() != 1U || log[0] != "chime:ebb:1") return 3;
            bell.flow(20);
            if (bell.phase() != 1) return 4;
            if (bell.crossings() != 4) return 5;
            log = bell.chime_log();
            if (log.size() != 4U) return 6;
            if (log[1] != "chime:flow:2" || log[3] != "chime:flow:4") return 7;
            bell.ebb(1);
            if (bell.phase() != 0) return 8;
            if (bell.crossings() != 4) return 9;
            bell.ebb(1);
            if (bell.phase() != 7) return 10;
            log = bell.chime_log();
            if (log.size() != 5U || log[4] != "chime:ebb:5") return 11;
            TideBell fresh(-2);
            if (fresh.phase() != 6) return 12;
            TideBell twin(14);
            if (!(fresh == twin)) return 13;
            if (fresh == bell) return 14;
            return 0;
            """,
            "floor-mod 8-phase tide cycle with ebb/flow magnitude verbs, a running chime count, and exact chime:<verb>:<k> journal text",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or dropping wrap history",
            "ebb below the origin, flow across multiple cycles, exact chime strings, order, and count, and phase-only equality",
            "dual-verb tide cycle with exact journal text in a paired .h/.cpp API",
            "single-cycle wheel with wrap-event journal",
        ),
        c(
            "f26clk-tram-depot-ring",
            "Tram depot ring",
            "tram_depot",
            """
            class DepotRing {
            public:
                explicit DepotRing(int bay);
                int shunt(int bays);
                int bay() const;
                int loops() const;
                std::vector<std::string> move_log() const;
                bool operator==(const DepotRing& other) const;
            };
            """,
            """
            class DepotRing {
            public:
                explicit DepotRing(int bay);
                int shunt(int bays);
                int bay() const;
                int loops() const;
                std::vector<std::string> move_log() const;
                bool operator==(const DepotRing& other) const;
            private:
                static constexpr int kBays = 22;
                static int normalize(int bay);
                int bay_;
                int forward_;
                int reverse_;
                std::vector<std::string> log_;
            };
            """,
            """
            int DepotRing::normalize(int bay) {
                int wrapped = bay % kBays;
                if (wrapped < 0) wrapped += kBays;
                return wrapped;
            }
            DepotRing::DepotRing(int bay)
                : bay_(normalize(bay)), forward_(0), reverse_(0) {}
            int DepotRing::shunt(int bays) {
                int raw = bay_ + bays;
                int crossings = raw / kBays;
                if (raw % kBays != 0 && raw < 0) crossings -= 1;
                bay_ = normalize(raw);
                for (int i = 0; i < crossings; ++i) {
                    forward_ += 1;
                    log_.push_back("L+" + std::to_string(forward_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    reverse_ += 1;
                    log_.push_back("L-" + std::to_string(reverse_));
                }
                return crossings;
            }
            int DepotRing::bay() const { return bay_; }
            int DepotRing::loops() const { return forward_ + reverse_; }
            std::vector<std::string> DepotRing::move_log() const { return log_; }
            bool DepotRing::operator==(const DepotRing& other) const {
                return bay_ == other.bay_;
            }
            """,
            """
            int DepotRing::normalize(int bay) {
                int wrapped = bay % kBays;
                if (wrapped < 0) wrapped += kBays;
                return wrapped;
            }
            DepotRing::DepotRing(int bay)
                : bay_(normalize(bay)), forward_(0), reverse_(0) {}
            int DepotRing::shunt(int bays) {
                int raw = bay_ + bays;
                int crossings = raw / kBays;
                if (raw % kBays != 0 && raw < 0) crossings -= 1;
                bay_ = raw % kBays;
                for (int i = 0; i < crossings; ++i) {
                    forward_ += 1;
                    log_.push_back("L+" + std::to_string(forward_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    reverse_ += 1;
                    log_.push_back("L-" + std::to_string(reverse_));
                }
                return crossings;
            }
            int DepotRing::bay() const { return bay_; }
            int DepotRing::loops() const { return forward_ + reverse_; }
            std::vector<std::string> DepotRing::move_log() const { return log_; }
            bool DepotRing::operator==(const DepotRing& other) const {
                return bay_ == other.bay_;
            }
            """,
            """
            DepotRing ring(5);
            if (ring.bay() != 5) return 1;
            if (ring.shunt(9) != 0) return 2;
            if (ring.bay() != 14) return 3;
            if (ring.shunt(30) != 2) return 4;
            if (ring.bay() != 0) return 5;
            if (ring.loops() != 2) return 6;
            DepotRing twin(22);
            if (!(ring == twin)) return 7;
            std::vector<std::string> log = ring.move_log();
            if (log.size() != 2U || log[0] != "L+1" || log[1] != "L+2") return 8;
            return 0;
            """,
            """
            DepotRing ring(3);
            if (ring.shunt(-10) != -1) return 1;
            if (ring.bay() != 15) return 2;
            if (ring.loops() != 1) return 3;
            std::vector<std::string> log = ring.move_log();
            if (log.size() != 1U || log[0] != "L-1") return 4;
            if (ring.shunt(50) != 2) return 5;
            if (ring.bay() != 21) return 6;
            log = ring.move_log();
            if (log.size() != 3U || log[1] != "L+1" || log[2] != "L+2") return 7;
            if (ring.shunt(-22) != -1) return 8;
            if (ring.bay() != 21) return 9;
            if (ring.loops() != 4) return 10;
            log = ring.move_log();
            if (log.size() != 4U || log[3] != "L-2") return 11;
            DepotRing fresh(-5);
            if (fresh.bay() != 17) return 12;
            DepotRing twin(39);
            if (!(fresh == twin)) return 13;
            if (fresh == ring) return 14;
            return 0;
            """,
            "floor-mod 22-bay depot ring with per-call signed loop returns, a per-direction L+k/L-k crossing ledger, and bay-only equality",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or dropping wrap history",
            "multi-loop shunts in both directions, exact log order and text, loop counts, and bay-only equality",
            "22-bay depot ring with a signed crossing ledger in a paired .h/.cpp API",
            "single-cycle wheel with wrap-event journal",
        ),
        c(
            "f26clk-garden-rill-wheel",
            "Garden rill wheel",
            "garden_rill",
            """
            class RillWheel {
            public:
                explicit RillWheel(int paddle);
                int spill(int paddles);
                int paddle() const;
                int revolutions() const;
                std::vector<std::string> pour_log() const;
                bool operator==(const RillWheel& other) const;
            };
            """,
            """
            class RillWheel {
            public:
                explicit RillWheel(int paddle);
                int spill(int paddles);
                int paddle() const;
                int revolutions() const;
                std::vector<std::string> pour_log() const;
                bool operator==(const RillWheel& other) const;
            private:
                static constexpr int kPaddles = 16;
                static int normalize(int paddle);
                int paddle_;
                int revolutions_;
                int forward_;
                int backward_;
                std::vector<std::string> log_;
            };
            """,
            """
            int RillWheel::normalize(int paddle) {
                int wrapped = paddle % kPaddles;
                if (wrapped < 0) wrapped += kPaddles;
                return wrapped;
            }
            RillWheel::RillWheel(int paddle)
                : paddle_(normalize(paddle)), revolutions_(0), forward_(0), backward_(0) {}
            int RillWheel::spill(int paddles) {
                int raw = paddle_ + paddles;
                int crossings = raw / kPaddles;
                if (raw % kPaddles != 0 && raw < 0) crossings -= 1;
                paddle_ = normalize(raw);
                for (int i = 0; i < crossings; ++i) {
                    forward_ += 1;
                    revolutions_ += 1;
                    log_.push_back("pour#" + std::to_string(forward_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    backward_ += 1;
                    revolutions_ -= 1;
                    log_.push_back("draw#" + std::to_string(backward_));
                }
                return crossings;
            }
            int RillWheel::paddle() const { return paddle_; }
            int RillWheel::revolutions() const { return revolutions_; }
            std::vector<std::string> RillWheel::pour_log() const { return log_; }
            bool RillWheel::operator==(const RillWheel& other) const {
                return paddle_ == other.paddle_;
            }
            """,
            """
            int RillWheel::normalize(int paddle) {
                int wrapped = paddle % kPaddles;
                if (wrapped < 0) wrapped += kPaddles;
                return wrapped;
            }
            RillWheel::RillWheel(int paddle)
                : paddle_(normalize(paddle)), revolutions_(0), forward_(0), backward_(0) {}
            int RillWheel::spill(int paddles) {
                int raw = paddle_ + paddles;
                int crossings = raw / kPaddles;
                if (raw % kPaddles != 0 && raw < 0) crossings -= 1;
                paddle_ = normalize(raw);
                for (int i = 0; i < crossings; ++i) {
                    forward_ += 1;
                    revolutions_ += 1;
                    log_.push_back("pour#" + std::to_string(forward_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    backward_ += 1;
                    revolutions_ -= 1;
                    log_.push_back("pour#" + std::to_string(forward_ + backward_));
                }
                return crossings;
            }
            int RillWheel::paddle() const { return paddle_; }
            int RillWheel::revolutions() const { return revolutions_; }
            std::vector<std::string> RillWheel::pour_log() const { return log_; }
            bool RillWheel::operator==(const RillWheel& other) const {
                return paddle_ == other.paddle_;
            }
            """,
            """
            RillWheel wheel(4);
            if (wheel.paddle() != 4) return 1;
            if (wheel.spill(7) != 0) return 2;
            if (wheel.paddle() != 11) return 3;
            if (wheel.spill(21) != 2) return 4;
            if (wheel.paddle() != 0) return 5;
            if (wheel.revolutions() != 2) return 6;
            std::vector<std::string> log = wheel.pour_log();
            if (log.size() != 2U || log[0] != "pour#1" || log[1] != "pour#2") return 7;
            RillWheel twin(32);
            if (!(wheel == twin)) return 8;
            return 0;
            """,
            """
            RillWheel wheel(14);
            if (wheel.spill(5) != 1) return 1;
            if (wheel.paddle() != 3) return 2;
            if (wheel.revolutions() != 1) return 3;
            if (wheel.spill(-9) != -1) return 4;
            if (wheel.paddle() != 10) return 5;
            if (wheel.revolutions() != 0) return 6;
            std::vector<std::string> log = wheel.pour_log();
            if (log.size() != 2U) return 7;
            if (log[0] != "pour#1" || log[1] != "draw#1") return 8;
            if (wheel.spill(-38) != -2) return 9;
            if (wheel.paddle() != 4) return 10;
            if (wheel.revolutions() != -2) return 11;
            log = wheel.pour_log();
            if (log.size() != 4U || log[2] != "draw#2" || log[3] != "draw#3") return 12;
            if (wheel.spill(48) != 3) return 13;
            if (wheel.paddle() != 4) return 14;
            if (wheel.revolutions() != 1) return 15;
            log = wheel.pour_log();
            if (log.size() != 7U || log[4] != "pour#2" || log[6] != "pour#4") return 16;
            RillWheel fresh(-3);
            if (fresh.paddle() != 13) return 17;
            RillWheel twin(29);
            if (!(fresh == twin)) return 18;
            if (fresh == wheel) return 19;
            return 0;
            """,
            "floor-mod 16-paddle water wheel with per-call signed revolution returns, a net revolution counter, and direction-sensitive pour#k/draw#k journal verbs",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or dropping wrap history",
            "forward and backward spills, exact log text and order, net revolution counts, and paddle-only equality",
            "sixteen-paddle wheel with a direction-sensitive journal in a paired .h/.cpp API",
            "single-cycle wheel with wrap-event journal",
        ),

        c(
            "f26clk-beacon-flash-signature",
            "Beacon flash signature",
            "beacon_flash",
            """
            class FlashSignature {
            public:
                FlashSignature(int group, int tick);
                void pulse(int ticks);
                int group() const;
                int tick() const;
                std::string render() const;
                bool operator==(const FlashSignature& other) const;
            };
            """,
            """
            class FlashSignature {
            public:
                FlashSignature(int group, int tick);
                void pulse(int ticks);
                int group() const;
                int tick() const;
                std::string render() const;
                bool operator==(const FlashSignature& other) const;
            private:
                static constexpr int kTicksPerGroup = 8;
                static constexpr int kGroups = 12;
                static constexpr int kCycle = 96;
                static int normalize(int ticks);
                int group_;
                int tick_;
            };
            """,
            """
            int FlashSignature::normalize(int ticks) {
                int wrapped = ticks % kCycle;
                if (wrapped < 0) wrapped += kCycle;
                return wrapped;
            }
            FlashSignature::FlashSignature(int group, int tick) {
                int total = normalize(group * kTicksPerGroup + tick);
                group_ = total / kTicksPerGroup;
                tick_ = total % kTicksPerGroup;
            }
            void FlashSignature::pulse(int ticks) {
                int total = normalize(group_ * kTicksPerGroup + tick_ + ticks);
                group_ = total / kTicksPerGroup;
                tick_ = total % kTicksPerGroup;
            }
            int FlashSignature::group() const { return group_; }
            int FlashSignature::tick() const { return tick_; }
            std::string FlashSignature::render() const {
                std::ostringstream out;
                out << "F[" << std::setw(2) << std::setfill('0') << group_ << ":"
                    << std::setw(2) << std::setfill('0') << tick_ << "]";
                return out.str();
            }
            bool FlashSignature::operator==(const FlashSignature& other) const {
                return group_ == other.group_ && tick_ == other.tick_;
            }
            """,
            """
            int FlashSignature::normalize(int ticks) {
                int wrapped = ticks % kCycle;
                if (wrapped < 0) wrapped += kCycle;
                return wrapped;
            }
            FlashSignature::FlashSignature(int group, int tick) {
                int total = normalize(group * kTicksPerGroup + tick);
                group_ = total / kTicksPerGroup;
                tick_ = total % kTicksPerGroup;
            }
            void FlashSignature::pulse(int ticks) {
                int total = normalize(group_ * kTicksPerGroup + tick_ + ticks);
                group_ = total / kTicksPerGroup;
                tick_ = total % kTicksPerGroup;
            }
            int FlashSignature::group() const { return group_; }
            int FlashSignature::tick() const { return tick_; }
            std::string FlashSignature::render() const {
                std::ostringstream out;
                out << "F[" << group_ << ":" << tick_ << "]";
                return out.str();
            }
            bool FlashSignature::operator==(const FlashSignature& other) const {
                return group_ == other.group_ && tick_ == other.tick_;
            }
            """,
            """
            FlashSignature sig(3, 7);
            if (sig.group() != 3 || sig.tick() != 7) return 1;
            sig.pulse(2);
            if (sig.group() != 4 || sig.tick() != 1) return 2;
            FlashSignature same(4, 1);
            if (!(sig == same)) return 3;
            sig.pulse(95);
            if (sig.group() != 4 || sig.tick() != 0) return 4;
            FlashSignature wrapped(12, 3);
            if (wrapped.group() != 0 || wrapped.tick() != 3) return 5;
            return 0;
            """,
            """
            FlashSignature neg(-1, 3);
            if (neg.group() != 11 || neg.tick() != 3) return 1;
            FlashSignature sig(0, 0);
            sig.pulse(-1);
            if (sig.group() != 11 || sig.tick() != 7) return 2;
            if (sig.render() != "F[11:07]") return 3;
            FlashSignature pad(0, 5);
            if (pad.render() != "F[00:05]") return 4;
            FlashSignature ten(10, 0);
            if (ten.render() != "F[10:00]") return 5;
            sig.pulse(1);
            if (sig.render() != "F[00:00]") return 6;
            FlashSignature a(1, 2);
            FlashSignature b(13, 2);
            if (!(a == b)) return 7;
            sig.pulse(288);
            if (sig.render() != "F[00:00]") return 8;
            return 0;
            """,
            "floor-mod 96-tick two-field flash cycle with an exact zero-padded F[gg:tt] rendering",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or unpadded stream-state-dependent formatting",
            "negative pulse borrows, zero-padding boundaries at 0/9/10, cycle wraps, and representation-blind equality",
            "exact fixed-width readout discipline distinct from any HH:MM rendering contract",
            "exact-readout cyclic value type",
        ),
        c(
            "f26clk-kiln-cone-witness",
            "Kiln cone witness",
            "kiln_cone",
            """
            class ConeWitness {
            public:
                ConeWitness(int shelf, int cone);
                void fire(int cones);
                int shelf() const;
                int cone() const;
                std::string render() const;
                bool operator==(const ConeWitness& other) const;
            };
            """,
            """
            class ConeWitness {
            public:
                ConeWitness(int shelf, int cone);
                void fire(int cones);
                int shelf() const;
                int cone() const;
                std::string render() const;
                bool operator==(const ConeWitness& other) const;
            private:
                static constexpr int kConesPerShelf = 32;
                static constexpr int kShelves = 9;
                static constexpr long kCycleCones = 288L;
                static long normalize(long total);
                int shelf_;
                int cone_;
            };
            """,
            """
            long ConeWitness::normalize(long total) {
                long wrapped = total % kCycleCones;
                if (wrapped < 0) wrapped += kCycleCones;
                return wrapped;
            }
            ConeWitness::ConeWitness(int shelf, int cone) {
                long total = normalize(static_cast<long>(shelf) * kConesPerShelf + cone);
                shelf_ = static_cast<int>(total / kConesPerShelf);
                cone_ = static_cast<int>(total % kConesPerShelf);
            }
            void ConeWitness::fire(int cones) {
                long total = normalize(static_cast<long>(shelf_) * kConesPerShelf + cone_ + cones);
                shelf_ = static_cast<int>(total / kConesPerShelf);
                cone_ = static_cast<int>(total % kConesPerShelf);
            }
            int ConeWitness::shelf() const { return shelf_; }
            int ConeWitness::cone() const { return cone_; }
            std::string ConeWitness::render() const {
                std::ostringstream out;
                out << "K-s" << shelf_ << "c"
                    << std::setw(2) << std::setfill('0') << cone_;
                return out.str();
            }
            bool ConeWitness::operator==(const ConeWitness& other) const {
                return shelf_ == other.shelf_ && cone_ == other.cone_;
            }
            """,
            """
            long ConeWitness::normalize(long total) {
                long wrapped = total % kCycleCones;
                if (wrapped < 0) wrapped += kCycleCones;
                return wrapped;
            }
            ConeWitness::ConeWitness(int shelf, int cone) {
                long total = normalize(static_cast<long>(shelf) * kConesPerShelf + cone);
                shelf_ = static_cast<int>(total / kConesPerShelf);
                cone_ = static_cast<int>(total % kConesPerShelf);
            }
            void ConeWitness::fire(int cones) {
                long total = normalize(static_cast<long>(shelf_) * kConesPerShelf + cone_ + cones);
                shelf_ = static_cast<int>(total / kConesPerShelf);
                cone_ = static_cast<int>(total % kConesPerShelf);
            }
            int ConeWitness::shelf() const { return shelf_; }
            int ConeWitness::cone() const { return cone_; }
            std::string ConeWitness::render() const {
                std::ostringstream out;
                out << "K-s" << std::setw(2) << std::setfill('0') << shelf_ << "c"
                    << std::setw(2) << std::setfill('0') << cone_;
                return out.str();
            }
            bool ConeWitness::operator==(const ConeWitness& other) const {
                return shelf_ == other.shelf_ && cone_ == other.cone_;
            }
            """,
            """
            ConeWitness w(2, 14);
            if (w.shelf() != 2 || w.cone() != 14) return 1;
            w.fire(20);
            if (w.shelf() != 3 || w.cone() != 2) return 2;
            ConeWitness same(3, 2);
            if (!(w == same)) return 3;
            w.fire(300);
            if (w.shelf() != 3 || w.cone() != 14) return 4;
            ConeWitness wrapped(9, 3);
            if (wrapped.shelf() != 0 || wrapped.cone() != 3) return 5;
            ConeWitness over(1, 40);
            if (over.shelf() != 2 || over.cone() != 8) return 6;
            return 0;
            """,
            """
            ConeWitness neg(-1, 7);
            if (neg.shelf() != 8 || neg.cone() != 7) return 1;
            ConeWitness w(0, 5);
            w.fire(-9);
            if (w.shelf() != 8 || w.cone() != 28) return 2;
            ConeWitness shown(2, 14);
            if (shown.render() != "K-s2c14") return 3;
            ConeWitness nine(3, 9);
            if (nine.render() != "K-s3c09") return 4;
            ConeWitness ten(3, 10);
            if (ten.render() != "K-s3c10") return 5;
            ConeWitness top(8, 31);
            top.fire(1);
            if (top.render() != "K-s0c00") return 6;
            top.fire(-1);
            if (top.render() != "K-s8c31") return 7;
            ConeWitness a(1, 2);
            ConeWitness b(10, 2);
            if (!(a == b)) return 8;
            ConeWitness c(0, 0);
            c.fire(288);
            if (!(c == ConeWitness(0, 0))) return 9;
            c.fire(1000);
            if (c.render() != "K-s4c08") return 10;
            return 0;
            """,
            "floor-mod 288-cone two-field shelf/cone cycle with a mixed-width K-s<s>c<cc> rendering",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or zero-padding the shelf field",
            "negative fire borrows, shelf rollover at 8, cone render width at 9 versus 10, and representation-blind equality",
            "mixed-width labeled readout with base-32 carry",
            "exact-readout cyclic value type",
        ),
        c(
            "f26clk-anchor-chain-tally",
            "Anchor chain tally",
            "anchor_chain",
            """
            class ChainTally {
            public:
                ChainTally(int shots, int fathoms);
                void pay_out(int fathoms);
                void heave(int fathoms);
                int shots() const;
                int fathoms() const;
                std::string render() const;
                bool operator==(const ChainTally& other) const;
            };
            """,
            """
            class ChainTally {
            public:
                ChainTally(int shots, int fathoms);
                void pay_out(int fathoms);
                void heave(int fathoms);
                int shots() const;
                int fathoms() const;
                std::string render() const;
                bool operator==(const ChainTally& other) const;
            private:
                static constexpr int kFathomsPerShot = 45;
                static constexpr int kShots = 20;
                static constexpr long kCycleFathoms = 900L;
                static long normalize(long total);
                int shots_;
                int fathoms_;
            };
            """,
            """
            long ChainTally::normalize(long total) {
                long wrapped = total % kCycleFathoms;
                if (wrapped < 0) wrapped += kCycleFathoms;
                return wrapped;
            }
            ChainTally::ChainTally(int shots, int fathoms) {
                long total = normalize(static_cast<long>(shots) * kFathomsPerShot + fathoms);
                shots_ = static_cast<int>(total / kFathomsPerShot);
                fathoms_ = static_cast<int>(total % kFathomsPerShot);
            }
            void ChainTally::pay_out(int fathoms) {
                long total = normalize(static_cast<long>(shots_) * kFathomsPerShot + fathoms_ + fathoms);
                shots_ = static_cast<int>(total / kFathomsPerShot);
                fathoms_ = static_cast<int>(total % kFathomsPerShot);
            }
            void ChainTally::heave(int fathoms) {
                long total = normalize(static_cast<long>(shots_) * kFathomsPerShot + fathoms_ - fathoms);
                shots_ = static_cast<int>(total / kFathomsPerShot);
                fathoms_ = static_cast<int>(total % kFathomsPerShot);
            }
            int ChainTally::shots() const { return shots_; }
            int ChainTally::fathoms() const { return fathoms_; }
            std::string ChainTally::render() const {
                std::ostringstream out;
                out << "S" << std::setw(2) << std::setfill('0') << shots_ << "/"
                    << std::setw(2) << std::setfill('0') << fathoms_;
                return out.str();
            }
            bool ChainTally::operator==(const ChainTally& other) const {
                return shots_ == other.shots_ && fathoms_ == other.fathoms_;
            }
            """,
            """
            long ChainTally::normalize(long total) {
                long wrapped = total % kCycleFathoms;
                if (wrapped < 0) wrapped += kCycleFathoms;
                return wrapped;
            }
            ChainTally::ChainTally(int shots, int fathoms) {
                long total = normalize(static_cast<long>(shots) * kFathomsPerShot + fathoms);
                shots_ = static_cast<int>(total / kFathomsPerShot);
                fathoms_ = static_cast<int>(total % kFathomsPerShot);
            }
            void ChainTally::pay_out(int fathoms) {
                long total = normalize(static_cast<long>(shots_) * kFathomsPerShot + fathoms_ + fathoms);
                shots_ = static_cast<int>(total / kFathomsPerShot);
                fathoms_ = static_cast<int>(total % kFathomsPerShot);
            }
            void ChainTally::heave(int fathoms) {
                long total = static_cast<long>(shots_) * kFathomsPerShot + fathoms_ - fathoms;
                if (total < 0) total = 0;
                shots_ = static_cast<int>(total / kFathomsPerShot);
                fathoms_ = static_cast<int>(total % kFathomsPerShot);
            }
            int ChainTally::shots() const { return shots_; }
            int ChainTally::fathoms() const { return fathoms_; }
            std::string ChainTally::render() const {
                std::ostringstream out;
                out << "S" << std::setw(2) << std::setfill('0') << shots_ << "/"
                    << std::setw(2) << std::setfill('0') << fathoms_;
                return out.str();
            }
            bool ChainTally::operator==(const ChainTally& other) const {
                return shots_ == other.shots_ && fathoms_ == other.fathoms_;
            }
            """,
            """
            ChainTally t(3, 20);
            if (t.shots() != 3 || t.fathoms() != 20) return 1;
            t.pay_out(30);
            if (t.shots() != 4 || t.fathoms() != 5) return 2;
            t.heave(10);
            if (t.shots() != 3 || t.fathoms() != 40) return 3;
            if (t.render() != "S03/40") return 4;
            ChainTally same(3, 40);
            if (!(t == same)) return 5;
            t.pay_out(800);
            if (t.render() != "S01/30") return 6;
            ChainTally wrapped(20, 10);
            if (wrapped.shots() != 0 || wrapped.fathoms() != 10) return 7;
            return 0;
            """,
            """
            ChainTally neg(-1, 10);
            if (neg.shots() != 19 || neg.fathoms() != 10) return 1;
            ChainTally t(0, 5);
            t.heave(10);
            if (t.shots() != 19 || t.fathoms() != 40) return 2;
            if (t.render() != "S19/40") return 3;
            ChainTally p(0, 0);
            p.pay_out(905);
            if (p.render() != "S00/05") return 4;
            ChainTally q(2, 0);
            q.heave(90);
            if (q.render() != "S00/00") return 5;
            ChainTally r(1, 0);
            r.heave(950);
            if (r.render() != "S19/40") return 6;
            ChainTally pad(0, 7);
            if (pad.render() != "S00/07") return 7;
            ChainTally nine(9, 10);
            if (nine.render() != "S09/10") return 8;
            ChainTally a(1, 5);
            ChainTally b(21, 5);
            if (!(a == b)) return 9;
            ChainTally top(19, 44);
            top.pay_out(1);
            if (top.render() != "S00/00") return 10;
            return 0;
            """,
            "floor-mod 900-fathom two-field shot/fathom cycle with dual unsigned pay_out/heave verbs and a slash-delimited Sss/ff readout",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or clamping heave at the origin",
            "heave below the origin wraps, pay_out across many shots, slash-readout padding, and representation-blind equality",
            "dual-verb chain tally with slash-delimited readout",
            "exact-readout cyclic value type",
        ),
        c(
            "f26clk-cistern-float-gauge",
            "Cistern float gauge",
            "cistern_float",
            """
            class FloatGauge {
            public:
                FloatGauge(int marks, int ticks);
                void drift(int ticks);
                int marks() const;
                int ticks() const;
                std::string render() const;
                bool operator==(const FloatGauge& other) const;
            };
            """,
            """
            class FloatGauge {
            public:
                FloatGauge(int marks, int ticks);
                void drift(int ticks);
                int marks() const;
                int ticks() const;
                std::string render() const;
                bool operator==(const FloatGauge& other) const;
            private:
                static constexpr int kTicksPerMark = 100;
                static constexpr int kMarks = 4;
                static constexpr long kCycleTicks = 400L;
                static long normalize(long total);
                int marks_;
                int ticks_;
            };
            """,
            """
            long FloatGauge::normalize(long total) {
                long wrapped = total % kCycleTicks;
                if (wrapped < 0) wrapped += kCycleTicks;
                return wrapped;
            }
            FloatGauge::FloatGauge(int marks, int ticks) {
                long total = normalize(static_cast<long>(marks) * kTicksPerMark + ticks);
                marks_ = static_cast<int>(total / kTicksPerMark);
                ticks_ = static_cast<int>(total % kTicksPerMark);
            }
            void FloatGauge::drift(int ticks) {
                long total = normalize(static_cast<long>(marks_) * kTicksPerMark + ticks_ + ticks);
                marks_ = static_cast<int>(total / kTicksPerMark);
                ticks_ = static_cast<int>(total % kTicksPerMark);
            }
            int FloatGauge::marks() const { return marks_; }
            int FloatGauge::ticks() const { return ticks_; }
            std::string FloatGauge::render() const {
                std::ostringstream out;
                out << "LVL=" << marks_ << "|"
                    << std::setw(3) << std::setfill('0') << ticks_;
                return out.str();
            }
            bool FloatGauge::operator==(const FloatGauge& other) const {
                return marks_ == other.marks_ && ticks_ == other.ticks_;
            }
            """,
            """
            long FloatGauge::normalize(long total) {
                long wrapped = total % kCycleTicks;
                if (wrapped < 0) wrapped += kCycleTicks;
                return wrapped;
            }
            FloatGauge::FloatGauge(int marks, int ticks) {
                long total = normalize(static_cast<long>(marks) * kTicksPerMark + ticks);
                marks_ = static_cast<int>(total / kTicksPerMark);
                ticks_ = static_cast<int>(total % kTicksPerMark);
            }
            void FloatGauge::drift(int ticks) {
                long total = normalize(static_cast<long>(marks_) * kTicksPerMark + ticks_ + ticks);
                marks_ = static_cast<int>(total / kTicksPerMark);
                ticks_ = static_cast<int>(total % kTicksPerMark);
            }
            int FloatGauge::marks() const { return marks_; }
            int FloatGauge::ticks() const { return ticks_; }
            std::string FloatGauge::render() const {
                std::ostringstream out;
                out << "LVL=" << marks_ << "|"
                    << std::setw(2) << std::setfill('0') << ticks_;
                return out.str();
            }
            bool FloatGauge::operator==(const FloatGauge& other) const {
                return marks_ == other.marks_ && ticks_ == other.ticks_;
            }
            """,
            """
            FloatGauge g(1, 250);
            if (g.marks() != 3 || g.ticks() != 50) return 1;
            g.drift(75);
            if (g.marks() != 0 || g.ticks() != 25) return 2;
            FloatGauge same(0, 25);
            if (!(g == same)) return 3;
            g.drift(300);
            if (g.marks() != 3 || g.ticks() != 25) return 4;
            FloatGauge wrapped(4, 12);
            if (wrapped.marks() != 0 || wrapped.ticks() != 12) return 5;
            FloatGauge over(2, 199);
            if (over.marks() != 3 || over.ticks() != 99) return 6;
            return 0;
            """,
            """
            FloatGauge neg(-1, 30);
            if (neg.marks() != 3 || neg.ticks() != 30) return 1;
            FloatGauge g(0, 20);
            g.drift(-50);
            if (g.marks() != 3 || g.ticks() != 70) return 2;
            if (g.render() != "LVL=3|070") return 3;
            FloatGauge shown(2, 73);
            if (shown.render() != "LVL=2|073") return 4;
            FloatGauge pad(0, 5);
            if (pad.render() != "LVL=0|005") return 5;
            FloatGauge top(3, 99);
            top.drift(1);
            if (top.render() != "LVL=0|000") return 6;
            FloatGauge w(0, 0);
            w.drift(-1);
            if (w.render() != "LVL=3|099") return 7;
            FloatGauge big(0, 0);
            big.drift(1000);
            if (big.render() != "LVL=2|000") return 8;
            FloatGauge a(1, 10);
            FloatGauge b(5, 10);
            if (!(a == b)) return 9;
            FloatGauge c(1, 100);
            if (c.render() != "LVL=2|000") return 10;
            return 0;
            """,
            "floor-mod 400-tick two-field mark/tick cycle at base 100 with a pipe-delimited LVL=m|ttt readout",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or two-digit tick padding",
            "negative drift borrows, three-digit tick padding, mark rollover, and representation-blind equality",
            "three-digit padding readout at base 100",
            "exact-readout cyclic value type",
        ),
        c(
            "f26clk-dredge-ladder-depth",
            "Dredge ladder depth",
            "dredge_ladder",
            """
            class LadderDepth {
            public:
                LadderDepth(int chains, int links);
                void lower(int links);
                void raise(int links);
                int chains() const;
                int links() const;
                std::string render() const;
                bool operator==(const LadderDepth& other) const;
            };
            """,
            """
            class LadderDepth {
            public:
                LadderDepth(int chains, int links);
                void lower(int links);
                void raise(int links);
                int chains() const;
                int links() const;
                std::string render() const;
                bool operator==(const LadderDepth& other) const;
            private:
                static constexpr int kLinksPerChain = 75;
                static constexpr int kChains = 16;
                static constexpr long kCycleLinks = 1200L;
                static long normalize(long total);
                int chains_;
                int links_;
            };
            """,
            """
            long LadderDepth::normalize(long total) {
                long wrapped = total % kCycleLinks;
                if (wrapped < 0) wrapped += kCycleLinks;
                return wrapped;
            }
            LadderDepth::LadderDepth(int chains, int links) {
                long total = normalize(static_cast<long>(chains) * kLinksPerChain + links);
                chains_ = static_cast<int>(total / kLinksPerChain);
                links_ = static_cast<int>(total % kLinksPerChain);
            }
            void LadderDepth::lower(int links) {
                long total = normalize(static_cast<long>(chains_) * kLinksPerChain + links_ + links);
                chains_ = static_cast<int>(total / kLinksPerChain);
                links_ = static_cast<int>(total % kLinksPerChain);
            }
            void LadderDepth::raise(int links) {
                long total = normalize(static_cast<long>(chains_) * kLinksPerChain + links_ - links);
                chains_ = static_cast<int>(total / kLinksPerChain);
                links_ = static_cast<int>(total % kLinksPerChain);
            }
            int LadderDepth::chains() const { return chains_; }
            int LadderDepth::links() const { return links_; }
            std::string LadderDepth::render() const {
                std::ostringstream out;
                out << "D" << std::setw(2) << std::setfill('0') << chains_ << "."
                    << std::setw(2) << std::setfill('0') << links_;
                return out.str();
            }
            bool LadderDepth::operator==(const LadderDepth& other) const {
                return chains_ == other.chains_ && links_ == other.links_;
            }
            """,
            """
            long LadderDepth::normalize(long total) {
                long wrapped = total % kCycleLinks;
                if (wrapped < 0) wrapped += kCycleLinks;
                return wrapped;
            }
            LadderDepth::LadderDepth(int chains, int links) {
                long total = normalize(static_cast<long>(chains) * kLinksPerChain + links);
                chains_ = static_cast<int>(total / kLinksPerChain);
                links_ = static_cast<int>(total % kLinksPerChain);
            }
            void LadderDepth::lower(int links) {
                long total = normalize(static_cast<long>(chains_) * kLinksPerChain + links_ + links);
                chains_ = static_cast<int>(total / kLinksPerChain);
                links_ = static_cast<int>(total % kLinksPerChain);
            }
            void LadderDepth::raise(int links) {
                long total = normalize(static_cast<long>(chains_) * kLinksPerChain + links_ - links);
                chains_ = static_cast<int>(total / kLinksPerChain);
                links_ = static_cast<int>(total % kLinksPerChain);
            }
            int LadderDepth::chains() const { return chains_; }
            int LadderDepth::links() const { return links_; }
            std::string LadderDepth::render() const {
                double depth = static_cast<double>(chains_) +
                               static_cast<double>(links_) / kLinksPerChain;
                int shown_chains = static_cast<int>(depth);
                int shown_links = static_cast<int>((depth - shown_chains) * kLinksPerChain);
                std::ostringstream out;
                out << "D" << std::setw(2) << std::setfill('0') << shown_chains << "."
                    << std::setw(2) << std::setfill('0') << shown_links;
                return out.str();
            }
            bool LadderDepth::operator==(const LadderDepth& other) const {
                return chains_ == other.chains_ && links_ == other.links_;
            }
            """,
            """
            LadderDepth d(2, 30);
            if (d.chains() != 2 || d.links() != 30) return 1;
            d.lower(50);
            if (d.chains() != 3 || d.links() != 5) return 2;
            d.raise(15);
            if (d.chains() != 2 || d.links() != 65) return 3;
            if (d.render() != "D02.65") return 4;
            LadderDepth same(2, 65);
            if (!(d == same)) return 5;
            d.lower(1000);
            if (d.render() != "D00.15") return 6;
            LadderDepth wrapped(16, 5);
            if (wrapped.chains() != 0 || wrapped.links() != 5) return 7;
            return 0;
            """,
            """
            LadderDepth neg(-1, 20);
            if (neg.chains() != 15 || neg.links() != 20) return 1;
            LadderDepth d(0, 10);
            d.raise(25);
            if (d.chains() != 15 || d.links() != 60) return 2;
            if (d.render() != "D15.60") return 3;
            LadderDepth nine(3, 9);
            if (nine.render() != "D03.09") return 4;
            LadderDepth ten(3, 10);
            if (ten.render() != "D03.10") return 5;
            LadderDepth last(3, 74);
            if (last.render() != "D03.74") return 6;
            LadderDepth drift_a(0, 55);
            if (drift_a.render() != "D00.55") return 7;
            LadderDepth drift_b(1, 2);
            if (drift_b.render() != "D01.02") return 8;
            LadderDepth e(15, 74);
            e.lower(2);
            if (e.render() != "D00.01") return 9;
            LadderDepth r(0, 0);
            r.raise(1300);
            if (r.render() != "D14.50") return 10;
            LadderDepth a(1, 5);
            LadderDepth b(17, 5);
            if (!(a == b)) return 11;
            LadderDepth top(15, 74);
            top.lower(1);
            if (top.render() != "D00.00") return 12;
            return 0;
            """,
            "floor-mod 1200-link two-field chain/link cycle at base 75 with a dot-delimited Dcc.ll readout",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or floating-point depth math",
            "raise below the origin, lower across chains, render width at link 9/10/74, and representation-blind equality",
            "integer-exact dot-delimited depth readout",
            "exact-readout cyclic value type",
        ),
        c(
            "f26clk-granary-chute-dial",
            "Granary chute dial",
            "granary_chute",
            """
            class ChuteDial {
            public:
                ChuteDial(int gates, int notches);
                void turn(int notches);
                int gates() const;
                int notches() const;
                std::string render() const;
                bool operator==(const ChuteDial& other) const;
            };
            """,
            """
            class ChuteDial {
            public:
                ChuteDial(int gates, int notches);
                void turn(int notches);
                int gates() const;
                int notches() const;
                std::string render() const;
                bool operator==(const ChuteDial& other) const;
            private:
                static constexpr int kNotchesPerGate = 230;
                static constexpr int kGates = 12;
                static constexpr long kCycleNotches = 2760L;
                static long normalize(long total);
                int gates_;
                int notches_;
            };
            """,
            """
            long ChuteDial::normalize(long total) {
                long wrapped = total % kCycleNotches;
                if (wrapped < 0) wrapped += kCycleNotches;
                return wrapped;
            }
            ChuteDial::ChuteDial(int gates, int notches) {
                long total = normalize(static_cast<long>(gates) * kNotchesPerGate + notches);
                gates_ = static_cast<int>(total / kNotchesPerGate);
                notches_ = static_cast<int>(total % kNotchesPerGate);
            }
            void ChuteDial::turn(int notches) {
                long total = normalize(static_cast<long>(gates_) * kNotchesPerGate + notches_ + notches);
                gates_ = static_cast<int>(total / kNotchesPerGate);
                notches_ = static_cast<int>(total % kNotchesPerGate);
            }
            int ChuteDial::gates() const { return gates_; }
            int ChuteDial::notches() const { return notches_; }
            std::string ChuteDial::render() const {
                std::ostringstream out;
                out << "CHUTE::" << std::setw(2) << std::setfill('0') << gates_ << "::"
                    << std::setw(3) << std::setfill('0') << notches_;
                return out.str();
            }
            bool ChuteDial::operator==(const ChuteDial& other) const {
                return gates_ == other.gates_ && notches_ == other.notches_;
            }
            """,
            """
            long ChuteDial::normalize(long total) {
                long wrapped = total % kCycleNotches;
                if (wrapped < 0) wrapped += kCycleNotches;
                return wrapped;
            }
            ChuteDial::ChuteDial(int gates, int notches) {
                long total = normalize(static_cast<long>(gates) * kNotchesPerGate + notches);
                gates_ = static_cast<int>(total / kNotchesPerGate);
                notches_ = static_cast<int>(total % kNotchesPerGate);
            }
            void ChuteDial::turn(int notches) {
                long total = normalize(static_cast<long>(gates_) * kNotchesPerGate + notches_ + notches);
                gates_ = static_cast<int>(total / kNotchesPerGate);
                notches_ = static_cast<int>(total % kNotchesPerGate);
            }
            int ChuteDial::gates() const { return gates_; }
            int ChuteDial::notches() const { return notches_; }
            std::string ChuteDial::render() const {
                std::ostringstream out;
                out << "CHUTE::" << std::setw(3) << std::setfill('0') << notches_ << "::"
                    << std::setw(2) << std::setfill('0') << gates_;
                return out.str();
            }
            bool ChuteDial::operator==(const ChuteDial& other) const {
                return gates_ == other.gates_ && notches_ == other.notches_;
            }
            """,
            """
            ChuteDial d(5, 100);
            if (d.gates() != 5 || d.notches() != 100) return 1;
            d.turn(150);
            if (d.gates() != 6 || d.notches() != 20) return 2;
            ChuteDial same(6, 20);
            if (!(d == same)) return 3;
            d.turn(2000);
            if (d.gates() != 2 || d.notches() != 180) return 4;
            ChuteDial wrapped(12, 5);
            if (wrapped.gates() != 0 || wrapped.notches() != 5) return 5;
            ChuteDial over(1, 300);
            if (over.gates() != 2 || over.notches() != 70) return 6;
            return 0;
            """,
            """
            ChuteDial neg(-1, 40);
            if (neg.gates() != 11 || neg.notches() != 40) return 1;
            ChuteDial d(0, 30);
            d.turn(-60);
            if (d.gates() != 11 || d.notches() != 200) return 2;
            if (d.render() != "CHUTE::11::200") return 3;
            ChuteDial shown(7, 229);
            if (shown.render() != "CHUTE::07::229") return 4;
            ChuteDial pad(0, 5);
            if (pad.render() != "CHUTE::00::005") return 5;
            ChuteDial mid(10, 10);
            if (mid.render() != "CHUTE::10::010") return 6;
            ChuteDial w(0, 0);
            w.turn(6000);
            if (w.render() != "CHUTE::02::020") return 7;
            w.turn(-6000);
            if (w.render() != "CHUTE::00::000") return 8;
            ChuteDial g(11, 229);
            g.turn(1);
            if (g.render() != "CHUTE::00::000") return 9;
            ChuteDial a(2, 15);
            ChuteDial b(14, 15);
            if (!(a == b)) return 10;
            return 0;
            """,
            "floor-mod 2760-notch two-field gate/notch cycle at base 230 with a double-colon CHUTE::gg::nnn readout",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or transposed readout fields",
            "negative turn borrows, large cycle wraps, mixed-width padding, and representation-blind equality",
            "large-base dial with transposed-field discriminator",
            "exact-readout cyclic value type",
        ),
        c(
            "f26clk-pumpjack-stroke-meter",
            "Pumpjack stroke meter",
            "pumpjack_stroke",
            """
            class StrokeMeter {
            public:
                explicit StrokeMeter(int stroke);
                void crank(int strokes);
                int stroke() const;
                bool rising() const;
                std::string render() const;
                bool operator==(const StrokeMeter& other) const;
            };
            """,
            """
            class StrokeMeter {
            public:
                explicit StrokeMeter(int stroke);
                void crank(int strokes);
                int stroke() const;
                bool rising() const;
                std::string render() const;
                bool operator==(const StrokeMeter& other) const;
            private:
                static constexpr int kStrokePositions = 99;
                static constexpr int kStrokePeriod = 196;
                static long normalize(long phase);
                int phase_;
            };
            """,
            """
            long StrokeMeter::normalize(long phase) {
                long wrapped = phase % kStrokePeriod;
                if (wrapped < 0) wrapped += kStrokePeriod;
                return wrapped;
            }
            StrokeMeter::StrokeMeter(int stroke)
                : phase_(static_cast<int>(normalize(stroke))) {}
            void StrokeMeter::crank(int strokes) {
                phase_ = static_cast<int>(normalize(static_cast<long>(phase_) + strokes));
            }
            int StrokeMeter::stroke() const {
                if (phase_ < kStrokePositions) return phase_;
                return kStrokePeriod - phase_;
            }
            bool StrokeMeter::rising() const {
                return phase_ >= 1 && phase_ < kStrokePositions;
            }
            std::string StrokeMeter::render() const {
                std::ostringstream out;
                out << "STK " << std::setw(2) << std::setfill('0') << stroke() << " "
                    << (rising() ? "UP" : "DN");
                return out.str();
            }
            bool StrokeMeter::operator==(const StrokeMeter& other) const {
                return phase_ == other.phase_;
            }
            """,
            """
            StrokeMeter::StrokeMeter(int stroke) : phase_(stroke) {}
            void StrokeMeter::crank(int strokes) {
                phase_ = static_cast<int>(static_cast<long>(phase_) + strokes);
            }
            int StrokeMeter::stroke() const {
                int wrapped = phase_ % kStrokePositions;
                if (wrapped < 0) wrapped += kStrokePositions;
                return wrapped;
            }
            bool StrokeMeter::rising() const {
                int wrapped = phase_ % kStrokePeriod;
                if (wrapped < 0) wrapped += kStrokePeriod;
                return wrapped < kStrokePositions;
            }
            std::string StrokeMeter::render() const {
                std::ostringstream out;
                out << "STK " << std::setw(2) << std::setfill('0') << stroke() << " "
                    << (rising() ? "UP" : "DN");
                return out.str();
            }
            bool StrokeMeter::operator==(const StrokeMeter& other) const {
                return stroke() == other.stroke() && rising() == other.rising();
            }
            """,
            """
            StrokeMeter m(10);
            if (m.stroke() != 10 || !m.rising()) return 1;
            m.crank(25);
            if (m.stroke() != 35 || !m.rising()) return 2;
            if (m.render() != "STK 35 UP") return 3;
            m.crank(-15);
            if (m.stroke() != 20 || !m.rising()) return 4;
            StrokeMeter same(20);
            if (!(m == same)) return 5;
            m.crank(60);
            if (m.render() != "STK 80 UP") return 6;
            StrokeMeter top(98);
            if (top.stroke() != 98 || !top.rising()) return 7;
            if (top.render() != "STK 98 UP") return 8;
            return 0;
            """,
            """
            StrokeMeter bounce(98);
            bounce.crank(1);
            if (bounce.stroke() != 97 || bounce.rising()) return 1;
            if (bounce.render() != "STK 97 DN") return 2;
            StrokeMeter multi(95);
            multi.crank(10);
            if (multi.stroke() != 91 || multi.rising()) return 3;
            if (multi.render() != "STK 91 DN") return 4;
            StrokeMeter flips(97);
            flips.crank(1);
            if (flips.render() != "STK 98 UP") return 5;
            flips.crank(1);
            if (flips.render() != "STK 97 DN") return 6;
            flips.crank(1);
            if (flips.render() != "STK 96 DN") return 7;
            flips.crank(96);
            if (flips.render() != "STK 00 DN") return 8;
            flips.crank(1);
            if (flips.render() != "STK 01 UP") return 9;
            StrokeMeter big(0);
            big.crank(400);
            if (big.render() != "STK 08 UP") return 10;
            StrokeMeter drop(10);
            drop.crank(-1000);
            if (drop.render() != "STK 10 DN") return 11;
            StrokeMeter up(97);
            StrokeMeter down(99);
            if (up == down) return 12;
            StrokeMeter cyc(20);
            StrokeMeter wrapped(216);
            if (!(cyc == wrapped)) return 13;
            return 0;
            """,
            "196-phase reflection cycle over 99 stroke positions with position-plus-direction state and an STK <nn> <UP|DN> readout",
            "std::chrono or <ctime> types, std::fmod, or wrap-mod normalization that ignores reflection",
            "single and multiple reflections at both ends, direction flips, exact render strings, and equality including direction",
            "reflection-boundary value type contrasting wrap-mod roots",
            "exact-readout cyclic value type",
        ),
        c(
            "f26clk-vault-door-tumbler",
            "Vault door tumbler",
            "vault_door",
            """
            class DialError : public std::invalid_argument {
            public:
                explicit DialError(const std::string& message) : std::invalid_argument(message) {}
            };
            class Tumbler {
            public:
                Tumbler(int left, int right, int audit);
                void twist(int wheel, int steps);
                int wheel(int index) const;
                std::string render() const;
                bool operator==(const Tumbler& other) const;
            };
            """,
            """
            class DialError : public std::invalid_argument {
            public:
                explicit DialError(const std::string& message) : std::invalid_argument(message) {}
            };
            class Tumbler {
            public:
                Tumbler(int left, int right, int audit);
                void twist(int wheel, int steps);
                int wheel(int index) const;
                std::string render() const;
                bool operator==(const Tumbler& other) const;
            private:
                static constexpr int kWheelPositions = 33;
                static constexpr int kWheelCount = 3;
                static int normalize(long value);
                int wheels_[kWheelCount];
            };
            """,
            """
            int Tumbler::normalize(long value) {
                long wrapped = value % kWheelPositions;
                if (wrapped < 0) wrapped += kWheelPositions;
                return static_cast<int>(wrapped);
            }
            Tumbler::Tumbler(int left, int right, int audit)
                : wheels_{normalize(left), normalize(right), normalize(audit)} {}
            void Tumbler::twist(int wheel, int steps) {
                if (wheel < 0 || wheel >= kWheelCount) {
                    throw DialError("tumbler wheel selector out of range");
                }
                wheels_[wheel] = normalize(static_cast<long>(wheels_[wheel]) + steps);
            }
            int Tumbler::wheel(int index) const {
                if (index < 0 || index >= kWheelCount) {
                    throw DialError("tumbler wheel index out of range");
                }
                return wheels_[index];
            }
            std::string Tumbler::render() const {
                std::ostringstream out;
                out << "T<L" << std::setw(2) << std::setfill('0') << wheels_[0]
                    << " R" << std::setw(2) << std::setfill('0') << wheels_[1]
                    << " A" << std::setw(2) << std::setfill('0') << wheels_[2] << ">";
                return out.str();
            }
            bool Tumbler::operator==(const Tumbler& other) const {
                return wheels_[0] == other.wheels_[0] && wheels_[1] == other.wheels_[1] &&
                       wheels_[2] == other.wheels_[2];
            }
            """,
            """
            int Tumbler::normalize(long value) {
                long wrapped = value % kWheelPositions;
                if (wrapped < 0) wrapped += kWheelPositions;
                return static_cast<int>(wrapped);
            }
            Tumbler::Tumbler(int left, int right, int audit)
                : wheels_{normalize(left), normalize(right), normalize(audit)} {}
            void Tumbler::twist(int wheel, int steps) {
                int target = wheel;
                if (target < 0 || target >= kWheelCount) target = 0;
                wheels_[target] = normalize(static_cast<long>(wheels_[target]) + steps);
            }
            int Tumbler::wheel(int index) const {
                int shown = index;
                if (shown < 0 || shown >= kWheelCount) shown = 0;
                return wheels_[shown];
            }
            std::string Tumbler::render() const {
                std::ostringstream out;
                out << "T<L" << std::setw(2) << std::setfill('0') << wheels_[0]
                    << " R" << std::setw(2) << std::setfill('0') << wheels_[1]
                    << " A" << std::setw(2) << std::setfill('0') << wheels_[2] << ">";
                return out.str();
            }
            bool Tumbler::operator==(const Tumbler& other) const {
                return wheels_[0] == other.wheels_[0] && wheels_[1] == other.wheels_[1] &&
                       wheels_[2] == other.wheels_[2];
            }
            """,
            """
            Tumbler t(5, 10, 15);
            if (t.wheel(0) != 5 || t.wheel(1) != 10 || t.wheel(2) != 15) return 1;
            t.twist(0, 10);
            t.twist(1, 25);
            t.twist(2, -20);
            if (t.wheel(0) != 15 || t.wheel(1) != 2 || t.wheel(2) != 28) return 2;
            if (t.render() != "T<L15 R02 A28>") return 3;
            Tumbler same(15, 2, 28);
            if (!(t == same)) return 4;
            t.twist(2, 33);
            if (t.wheel(2) != 28) return 5;
            Tumbler wrapped(33, 66, -1);
            if (wrapped.wheel(0) != 0 || wrapped.wheel(1) != 0 || wrapped.wheel(2) != 32) return 6;
            return 0;
            """,
            """
            Tumbler t(1, 2, 3);
            bool thrown = false;
            try { t.twist(3, 5); } catch (const DialError&) { thrown = true; }
            if (!thrown) return 1;
            if (t.wheel(0) != 1 || t.wheel(1) != 2 || t.wheel(2) != 3) return 2;
            thrown = false;
            try { t.twist(-1, 5); } catch (const DialError&) { thrown = true; }
            if (!thrown) return 3;
            thrown = false;
            try { t.wheel(3); } catch (const DialError&) { thrown = true; }
            if (!thrown) return 4;
            thrown = false;
            try { t.wheel(-1); } catch (const DialError&) { thrown = true; }
            if (!thrown) return 5;
            Tumbler n(0, 0, 0);
            n.twist(1, -1);
            if (n.wheel(0) != 0 || n.wheel(1) != 32 || n.wheel(2) != 0) return 6;
            if (n.render() != "T<L00 R32 A00>") return 7;
            n.twist(0, -40);
            if (n.render() != "T<L26 R32 A00>") return 8;
            n.twist(2, 100);
            if (n.render() != "T<L26 R32 A01>") return 9;
            Tumbler negc(-1, -2, -3);
            if (negc.render() != "T<L32 R31 A30>") return 10;
            Tumbler over(33, 34, 35);
            if (over.render() != "T<L00 R01 A02>") return 11;
            Tumbler pad(9, 10, 0);
            if (pad.render() != "T<L09 R10 A00>") return 12;
            Tumbler edge(32, 0, 0);
            edge.twist(0, 1);
            if (edge.render() != "T<L00 R00 A00>") return 13;
            Tumbler a(1, 2, 3);
            Tumbler b(34, 35, 36);
            if (!(a == b)) return 14;
            Tumbler diff(1, 2, 4);
            if (a == diff) return 15;
            return 0;
            """,
            "three independent floor-mod 33-position wheels with typed DialError selector validation and a T<Lnn Rnn Ann> readout",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or silent acceptance of invalid wheel selectors",
            "selector 3/-1 rejection without mutation, per-wheel independent negative twists, exact render text, and equality",
            "selector-validated multi-wheel value with typed errors",
            "exact-readout cyclic value type",
        ),

        c(
            "f26clk-semaphore-arc-value",
            "Semaphore arc value",
            "semaphore_arc",
            """
            constexpr int kArcCycle = 180;
            class ArcValue {
            public:
                explicit ArcValue(int arc);
                ArcValue& operator+=(int arc);
                ArcValue& operator-=(int arc);
                ArcValue& operator++();
                ArcValue operator++(int);
                int arc() const;
            };
            bool operator==(const ArcValue& left, const ArcValue& right);
            bool operator!=(const ArcValue& left, const ArcValue& right);
            int shortest_delta(const ArcValue& from, const ArcValue& to);
            """,
            """
            constexpr int kArcCycle = 180;
            class ArcValue {
            public:
                explicit ArcValue(int arc);
                ArcValue& operator+=(int arc);
                ArcValue& operator-=(int arc);
                ArcValue& operator++();
                ArcValue operator++(int);
                int arc() const;
            private:
                static int normalize(int arc);
                int arc_;
            };
            bool operator==(const ArcValue& left, const ArcValue& right);
            bool operator!=(const ArcValue& left, const ArcValue& right);
            int shortest_delta(const ArcValue& from, const ArcValue& to);
            """,
            """
            int ArcValue::normalize(int arc) {
                int wrapped = arc % kArcCycle;
                if (wrapped < 0) wrapped += kArcCycle;
                return wrapped;
            }
            ArcValue::ArcValue(int arc) : arc_(normalize(arc)) {}
            ArcValue& ArcValue::operator+=(int arc) {
                arc_ = normalize(arc_ + arc);
                return *this;
            }
            ArcValue& ArcValue::operator-=(int arc) {
                arc_ = normalize(arc_ - arc);
                return *this;
            }
            ArcValue& ArcValue::operator++() {
                arc_ = normalize(arc_ + 1);
                return *this;
            }
            ArcValue ArcValue::operator++(int) {
                ArcValue before(*this);
                ++(*this);
                return before;
            }
            int ArcValue::arc() const { return arc_; }
            bool operator==(const ArcValue& left, const ArcValue& right) {
                return left.arc() == right.arc();
            }
            bool operator!=(const ArcValue& left, const ArcValue& right) {
                return !(left == right);
            }
            int shortest_delta(const ArcValue& from, const ArcValue& to) {
                int forward = (to.arc() - from.arc()) % kArcCycle;
                if (forward < 0) forward += kArcCycle;
                if (forward > kArcCycle / 2) forward -= kArcCycle;
                return forward;
            }
            """,
            """
            int ArcValue::normalize(int arc) {
                int wrapped = arc % kArcCycle;
                if (wrapped < 0) wrapped += kArcCycle;
                return wrapped;
            }
            ArcValue::ArcValue(int arc) : arc_(normalize(arc)) {}
            ArcValue& ArcValue::operator+=(int arc) {
                arc_ = normalize(arc_ + arc);
                return *this;
            }
            ArcValue& ArcValue::operator-=(int arc) {
                arc_ = normalize(arc_ - arc);
                return *this;
            }
            ArcValue& ArcValue::operator++() {
                arc_ = normalize(arc_ + 1);
                return *this;
            }
            ArcValue ArcValue::operator++(int) {
                ArcValue before(*this);
                ++(*this);
                return before;
            }
            int ArcValue::arc() const { return arc_; }
            bool operator==(const ArcValue& left, const ArcValue& right) {
                return left.arc() == right.arc();
            }
            bool operator!=(const ArcValue& left, const ArcValue& right) {
                return !(left == right);
            }
            int shortest_delta(const ArcValue& from, const ArcValue& to) {
                int forward = (to.arc() - from.arc()) % kArcCycle;
                if (forward < 0) forward += kArcCycle;
                if (forward >= kArcCycle / 2) forward -= kArcCycle;
                return forward;
            }
            """,
            """
            ArcValue a(170);
            a += 20;
            if (a.arc() != 10) return 1;
            a -= 25;
            if (a.arc() != 165) return 2;
            ++a;
            if (a.arc() != 166) return 3;
            ArcValue before = a++;
            if (before.arc() != 166 || a.arc() != 167) return 4;
            ArcValue same(347);
            if (!(a == same)) return 5;
            if (a != same) return 6;
            if (shortest_delta(ArcValue(10), ArcValue(40)) != 30) return 7;
            if (shortest_delta(ArcValue(40), ArcValue(10)) != -30) return 8;
            return 0;
            """,
            """
            ArcValue neg(-25);
            if (neg.arc() != 155) return 1;
            ArcValue wrap(179);
            ++wrap;
            if (wrap.arc() != 0) return 2;
            ArcValue a(0);
            a -= 1;
            if (a.arc() != 179) return 3;
            ArcValue b(350);
            if (b.arc() != 170) return 4;
            if (shortest_delta(ArcValue(0), ArcValue(90)) != 90) return 5;
            if (shortest_delta(ArcValue(90), ArcValue(0)) != 90) return 6;
            if (shortest_delta(ArcValue(170), ArcValue(10)) != 20) return 7;
            ArcValue c(45);
            ArcValue d = c++;
            if (d.arc() != 45 || c.arc() != 46) return 8;
            ArcValue e(90);
            ArcValue f(-90);
            if (!(e == f)) return 9;
            return 0;
            """,
            "floor-mod 180-arc cycle with compound and increment operators plus a signed shortest-delta free function",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or tie-asymmetric shortest deltas",
            "operator wraps across the origin, pre/post increment semantics, signed shortest deltas including exact +90 ties",
            "operator-rich modular value semantics in a paired .h/.cpp API",
            "operator-rich modular value type",
        ),
        c(
            "f26clk-gondola-bullwheel-angle",
            "Gondola bullwheel angle",
            "gondola_bullwheel",
            """
            constexpr int kWheelCycle = 360;
            class BullwheelAngle {
            public:
                explicit BullwheelAngle(int degrees);
                BullwheelAngle& operator+=(int degrees);
                BullwheelAngle& operator-=(int degrees);
                BullwheelAngle operator-() const;
                int degrees() const;
            };
            BullwheelAngle operator+(BullwheelAngle a, int degrees);
            BullwheelAngle operator-(BullwheelAngle a, int degrees);
            bool operator==(const BullwheelAngle& left, const BullwheelAngle& right);
            bool operator!=(const BullwheelAngle& left, const BullwheelAngle& right);
            bool operator<(const BullwheelAngle& left, const BullwheelAngle& right);
            """,
            """
            constexpr int kWheelCycle = 360;
            class BullwheelAngle {
            public:
                explicit BullwheelAngle(int degrees);
                BullwheelAngle& operator+=(int degrees);
                BullwheelAngle& operator-=(int degrees);
                BullwheelAngle operator-() const;
                int degrees() const;
            private:
                friend bool operator<(const BullwheelAngle& left, const BullwheelAngle& right);
                static int normalize(int degrees);
                int degrees_;
            };
            BullwheelAngle operator+(BullwheelAngle a, int degrees);
            BullwheelAngle operator-(BullwheelAngle a, int degrees);
            bool operator==(const BullwheelAngle& left, const BullwheelAngle& right);
            bool operator!=(const BullwheelAngle& left, const BullwheelAngle& right);
            bool operator<(const BullwheelAngle& left, const BullwheelAngle& right);
            """,
            """
            int BullwheelAngle::normalize(int degrees) {
                int wrapped = degrees % kWheelCycle;
                if (wrapped < 0) wrapped += kWheelCycle;
                return wrapped;
            }
            BullwheelAngle::BullwheelAngle(int degrees) : degrees_(normalize(degrees)) {}
            BullwheelAngle& BullwheelAngle::operator+=(int degrees) {
                degrees_ = normalize(degrees_ + degrees);
                return *this;
            }
            BullwheelAngle& BullwheelAngle::operator-=(int degrees) {
                degrees_ = normalize(degrees_ - degrees);
                return *this;
            }
            BullwheelAngle BullwheelAngle::operator-() const {
                return BullwheelAngle(-degrees_);
            }
            int BullwheelAngle::degrees() const { return degrees_; }
            BullwheelAngle operator+(BullwheelAngle a, int degrees) {
                a += degrees;
                return a;
            }
            BullwheelAngle operator-(BullwheelAngle a, int degrees) {
                a -= degrees;
                return a;
            }
            bool operator==(const BullwheelAngle& left, const BullwheelAngle& right) {
                return left.degrees() == right.degrees();
            }
            bool operator!=(const BullwheelAngle& left, const BullwheelAngle& right) {
                return !(left == right);
            }
            bool operator<(const BullwheelAngle& left, const BullwheelAngle& right) {
                return left.degrees() < right.degrees();
            }
            """,
            """
            int BullwheelAngle::normalize(int degrees) {
                int wrapped = degrees % kWheelCycle;
                if (wrapped < 0) wrapped += kWheelCycle;
                return wrapped;
            }
            BullwheelAngle::BullwheelAngle(int degrees) : degrees_(degrees) {}
            BullwheelAngle& BullwheelAngle::operator+=(int degrees) {
                degrees_ += degrees;
                return *this;
            }
            BullwheelAngle& BullwheelAngle::operator-=(int degrees) {
                degrees_ -= degrees;
                return *this;
            }
            BullwheelAngle BullwheelAngle::operator-() const {
                return BullwheelAngle(-degrees_);
            }
            int BullwheelAngle::degrees() const { return normalize(degrees_); }
            BullwheelAngle operator+(BullwheelAngle a, int degrees) {
                a += degrees;
                return a;
            }
            BullwheelAngle operator-(BullwheelAngle a, int degrees) {
                a -= degrees;
                return a;
            }
            bool operator==(const BullwheelAngle& left, const BullwheelAngle& right) {
                return left.degrees() == right.degrees();
            }
            bool operator!=(const BullwheelAngle& left, const BullwheelAngle& right) {
                return !(left == right);
            }
            bool operator<(const BullwheelAngle& left, const BullwheelAngle& right) {
                return left.degrees_ < right.degrees_;
            }
            """,
            """
            BullwheelAngle a(300);
            a += 90;
            if (a.degrees() != 30) return 1;
            BullwheelAngle b = a - 50;
            if (b.degrees() != 340) return 2;
            BullwheelAngle c = -b;
            if (c.degrees() != 20) return 3;
            BullwheelAngle d = -BullwheelAngle(0);
            if (d.degrees() != 0) return 4;
            BullwheelAngle e = b + 380;
            if (e.degrees() != 0) return 5;
            if (!(e == d)) return 6;
            if (e != d) return 7;
            BullwheelAngle f(90);
            if (f < BullwheelAngle(90)) return 8;
            return 0;
            """,
            """
            BullwheelAngle low(370);
            if (low.degrees() != 10) return 1;
            BullwheelAngle high(350);
            if (high < low) return 2;
            if (!(low < high)) return 3;
            BullwheelAngle negv(-30);
            if (negv.degrees() != 330) return 4;
            if (negv < low) return 5;
            BullwheelAngle a(170);
            a += 400;
            if (a.degrees() != 210) return 6;
            BullwheelAngle b = a - 210;
            if (b.degrees() != 0) return 7;
            BullwheelAngle ref = -BullwheelAngle(180);
            if (ref.degrees() != 180) return 8;
            if (!(ref == BullwheelAngle(540))) return 9;
            if (ref != BullwheelAngle(180)) return 10;
            BullwheelAngle zero(0);
            if (!(zero < ref)) return 11;
            BullwheelAngle r = -BullwheelAngle(30);
            if (r.degrees() != 330) return 12;
            return 0;
            """,
            "floor-mod 360-degree bullwheel cycle with compound, unary, and free operators plus normalized ordering",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or ordering on unnormalized construction values",
            "chained operator expressions, unary minus reflection at 0 and 180, ordering across the origin, and representation-blind equality",
            "full operator set with normalized ordering in a paired .h/.cpp API",
            "operator-rich modular value type",
        ),
        c(
            "f26clk-furnace-damper-notch",
            "Furnace damper notch",
            "furnace_damper",
            """
            constexpr int kNotchCount = 24;
            class DamperNotch {
            public:
                explicit DamperNotch(int notch);
                DamperNotch& operator+=(int notches);
                DamperNotch& operator-=(int notches);
                DamperNotch& operator--();
                DamperNotch operator--(int);
                int notch() const;
            };
            bool operator==(const DamperNotch& left, const DamperNotch& right);
            bool operator!=(const DamperNotch& left, const DamperNotch& right);
            unsigned forward_gap(const DamperNotch& from, const DamperNotch& to);
            """,
            """
            constexpr int kNotchCount = 24;
            class DamperNotch {
            public:
                explicit DamperNotch(int notch);
                DamperNotch& operator+=(int notches);
                DamperNotch& operator-=(int notches);
                DamperNotch& operator--();
                DamperNotch operator--(int);
                int notch() const;
            private:
                static int normalize(int notch);
                int notch_;
            };
            bool operator==(const DamperNotch& left, const DamperNotch& right);
            bool operator!=(const DamperNotch& left, const DamperNotch& right);
            unsigned forward_gap(const DamperNotch& from, const DamperNotch& to);
            """,
            """
            int DamperNotch::normalize(int notch) {
                int wrapped = notch % kNotchCount;
                if (wrapped < 0) wrapped += kNotchCount;
                return wrapped;
            }
            DamperNotch::DamperNotch(int notch) : notch_(normalize(notch)) {}
            DamperNotch& DamperNotch::operator+=(int notches) {
                notch_ = normalize(notch_ + notches);
                return *this;
            }
            DamperNotch& DamperNotch::operator-=(int notches) {
                notch_ = normalize(notch_ - notches);
                return *this;
            }
            DamperNotch& DamperNotch::operator--() {
                notch_ = normalize(notch_ - 1);
                return *this;
            }
            DamperNotch DamperNotch::operator--(int) {
                DamperNotch before(*this);
                --(*this);
                return before;
            }
            int DamperNotch::notch() const { return notch_; }
            bool operator==(const DamperNotch& left, const DamperNotch& right) {
                return left.notch() == right.notch();
            }
            bool operator!=(const DamperNotch& left, const DamperNotch& right) {
                return !(left == right);
            }
            unsigned forward_gap(const DamperNotch& from, const DamperNotch& to) {
                int forward = (to.notch() - from.notch()) % kNotchCount;
                if (forward < 0) forward += kNotchCount;
                return static_cast<unsigned>(forward);
            }
            """,
            """
            int DamperNotch::normalize(int notch) {
                int wrapped = notch % kNotchCount;
                if (wrapped < 0) wrapped += kNotchCount;
                return wrapped;
            }
            DamperNotch::DamperNotch(int notch) : notch_(normalize(notch)) {}
            DamperNotch& DamperNotch::operator+=(int notches) {
                notch_ = normalize(notch_ + notches);
                return *this;
            }
            DamperNotch& DamperNotch::operator-=(int notches) {
                notch_ = normalize(notch_ - notches);
                return *this;
            }
            DamperNotch& DamperNotch::operator--() {
                notch_ = normalize(notch_ - 1);
                return *this;
            }
            DamperNotch DamperNotch::operator--(int) {
                DamperNotch before(*this);
                --(*this);
                return before;
            }
            int DamperNotch::notch() const { return notch_; }
            bool operator==(const DamperNotch& left, const DamperNotch& right) {
                return left.notch() == right.notch();
            }
            bool operator!=(const DamperNotch& left, const DamperNotch& right) {
                return !(left == right);
            }
            unsigned forward_gap(const DamperNotch& from, const DamperNotch& to) {
                int diff = to.notch() - from.notch();
                if (diff < 0) diff = -diff;
                return static_cast<unsigned>(diff);
            }
            """,
            """
            DamperNotch a(20);
            a += 10;
            if (a.notch() != 6) return 1;
            --a;
            if (a.notch() != 5) return 2;
            DamperNotch old = a--;
            if (old.notch() != 5 || a.notch() != 4) return 3;
            a -= 8;
            if (a.notch() != 20) return 4;
            DamperNotch b(20);
            if (!(a == b)) return 5;
            if (a != b) return 6;
            if (forward_gap(DamperNotch(2), DamperNotch(9)) != 7U) return 7;
            return 0;
            """,
            """
            DamperNotch neg(-1);
            if (neg.notch() != 23) return 1;
            DamperNotch a(0);
            --a;
            if (a.notch() != 23) return 2;
            DamperNotch b(0);
            DamperNotch old = b--;
            if (old.notch() != 0 || b.notch() != 23) return 3;
            if (forward_gap(DamperNotch(9), DamperNotch(2)) != 17U) return 4;
            if (forward_gap(DamperNotch(2), DamperNotch(2)) != 0U) return 5;
            DamperNotch c(5);
            if (forward_gap(c, DamperNotch(5)) != 0U) return 6;
            if (forward_gap(DamperNotch(23), DamperNotch(1)) != 2U) return 7;
            DamperNotch d(3);
            DamperNotch e(20);
            if (forward_gap(d, e) + forward_gap(e, d) != 24U) return 8;
            DamperNotch f(23);
            f += 1;
            if (f.notch() != 0) return 9;
            DamperNotch g(1);
            g -= 50;
            if (g.notch() != 23) return 10;
            if (forward_gap(DamperNotch(0), DamperNotch(0)) != 0U) return 11;
            if (forward_gap(DamperNotch(12), DamperNotch(0)) != 12U) return 12;
            DamperNotch h(47);
            if (h.notch() != 23) return 13;
            if (h != DamperNotch(23)) return 14;
            return 0;
            """,
            "floor-mod 24-notch damper cycle with compound and decrement operators plus an unsigned directed forward-gap free function",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or direction-blind absolute gaps",
            "decrements across the origin in pre and post form, compound wraps, and directed forward gaps whose complements sum to 24",
            "decrement operators with directed gap semantics in a paired .h/.cpp API",
            "operator-rich modular value type",
        ),
        c(
            "f26clk-buoy-channel-marker",
            "Buoy channel marker",
            "buoy_channel",
            """
            constexpr int kMarkerCount = 32;
            class ChannelMarker {
            public:
                explicit ChannelMarker(int marker);
                ChannelMarker& operator+=(int markers);
                ChannelMarker& operator-=(int markers);
                int marker() const;
            };
            ChannelMarker operator+(ChannelMarker m, int markers);
            ChannelMarker operator-(ChannelMarker m, int markers);
            bool operator==(const ChannelMarker& left, const ChannelMarker& right);
            bool operator!=(const ChannelMarker& left, const ChannelMarker& right);
            bool operator<(const ChannelMarker& left, const ChannelMarker& right);
            bool operator>(const ChannelMarker& left, const ChannelMarker& right);
            """,
            """
            constexpr int kMarkerCount = 32;
            class ChannelMarker {
            public:
                explicit ChannelMarker(int marker);
                ChannelMarker& operator+=(int markers);
                ChannelMarker& operator-=(int markers);
                int marker() const;
            private:
                static int normalize(int marker);
                int marker_;
            };
            ChannelMarker operator+(ChannelMarker m, int markers);
            ChannelMarker operator-(ChannelMarker m, int markers);
            bool operator==(const ChannelMarker& left, const ChannelMarker& right);
            bool operator!=(const ChannelMarker& left, const ChannelMarker& right);
            bool operator<(const ChannelMarker& left, const ChannelMarker& right);
            bool operator>(const ChannelMarker& left, const ChannelMarker& right);
            """,
            """
            int ChannelMarker::normalize(int marker) {
                int wrapped = marker % kMarkerCount;
                if (wrapped < 0) wrapped += kMarkerCount;
                return wrapped;
            }
            ChannelMarker::ChannelMarker(int marker) : marker_(normalize(marker)) {}
            ChannelMarker& ChannelMarker::operator+=(int markers) {
                marker_ = normalize(marker_ + markers);
                return *this;
            }
            ChannelMarker& ChannelMarker::operator-=(int markers) {
                marker_ = normalize(marker_ - markers);
                return *this;
            }
            int ChannelMarker::marker() const { return marker_; }
            ChannelMarker operator+(ChannelMarker m, int markers) {
                m += markers;
                return m;
            }
            ChannelMarker operator-(ChannelMarker m, int markers) {
                m -= markers;
                return m;
            }
            bool operator==(const ChannelMarker& left, const ChannelMarker& right) {
                return left.marker() == right.marker();
            }
            bool operator!=(const ChannelMarker& left, const ChannelMarker& right) {
                return !(left == right);
            }
            bool operator<(const ChannelMarker& left, const ChannelMarker& right) {
                return left.marker() < right.marker();
            }
            bool operator>(const ChannelMarker& left, const ChannelMarker& right) {
                return right < left;
            }
            """,
            """
            int ChannelMarker::normalize(int marker) {
                int wrapped = marker % kMarkerCount;
                if (wrapped < 0) wrapped += kMarkerCount;
                return wrapped;
            }
            ChannelMarker::ChannelMarker(int marker) : marker_(normalize(marker)) {}
            ChannelMarker& ChannelMarker::operator+=(int markers) {
                marker_ = normalize(marker_ + markers);
                return *this;
            }
            ChannelMarker& ChannelMarker::operator-=(int markers) {
                marker_ = normalize(marker_ - markers);
                return *this;
            }
            int ChannelMarker::marker() const { return marker_; }
            ChannelMarker operator+(ChannelMarker m, int markers) {
                m += markers;
                return m;
            }
            ChannelMarker operator-(ChannelMarker m, int markers) {
                m -= markers;
                return m;
            }
            bool operator==(const ChannelMarker& left, const ChannelMarker& right) {
                return left.marker() == right.marker();
            }
            bool operator!=(const ChannelMarker& left, const ChannelMarker& right) {
                return !(left == right);
            }
            bool operator<(const ChannelMarker& left, const ChannelMarker& right) {
                return left.marker() < right.marker();
            }
            bool operator>(const ChannelMarker& left, const ChannelMarker& right) {
                return !(left < right);
            }
            """,
            """
            ChannelMarker a(30);
            a += 5;
            if (a.marker() != 3) return 1;
            ChannelMarker b = a - 10;
            if (b.marker() != 25) return 2;
            ChannelMarker c = b + 39;
            if (c.marker() != 0) return 3;
            ChannelMarker d(64);
            if (!(c == d)) return 4;
            if (c != d) return 5;
            ChannelMarker e(7);
            ChannelMarker f(19);
            if (!(e < f)) return 6;
            if (!(f > e)) return 7;
            if (e > f) return 8;
            return 0;
            """,
            """
            ChannelMarker neg(-3);
            if (neg.marker() != 29) return 1;
            ChannelMarker a(31);
            a += 1;
            if (a.marker() != 0) return 2;
            ChannelMarker same(32);
            if (!(a == same)) return 3;
            if (a > same) return 4;
            if (a < same) return 5;
            ChannelMarker high(30);
            ChannelMarker low(2);
            if (!(high > low)) return 6;
            if (low > high) return 7;
            ChannelMarker b = ChannelMarker(25) - 60;
            if (b.marker() != 29) return 8;
            ChannelMarker c = ChannelMarker(1) + 95;
            if (c.marker() != 0) return 9;
            ChannelMarker x(5);
            ChannelMarker y(37);
            if (x > y) return 10;
            if (!(x == y)) return 11;
            ChannelMarker m(100);
            if (m.marker() != 4) return 12;
            ChannelMarker n(-100);
            if (n.marker() != 28) return 13;
            if (!(m < n)) return 14;
            return 0;
            """,
            "floor-mod 32-marker channel cycle with free operators and a full normalized ordering pair",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or negation-based ordering that collapses equality",
            "free operator chaining, ordering across the origin including equality under both directions, and wrap arithmetic",
            "free-operator value with exact ordering relations in a paired .h/.cpp API",
            "operator-rich modular value type",
        ),
        c(
            "f26clk-pedal-gear-sprocket",
            "Pedal gear sprocket",
            "pedal_gear",
            """
            constexpr int kToothCount = 44;
            class SprocketPosition {
            public:
                explicit SprocketPosition(int tooth);
                SprocketPosition& operator+=(int teeth);
                SprocketPosition& operator-=(int teeth);
                SprocketPosition& operator++();
                int tooth() const;
            };
            bool operator==(const SprocketPosition& left, const SprocketPosition& right);
            bool operator!=(const SprocketPosition& left, const SprocketPosition& right);
            int mesh_delta(const SprocketPosition& from, const SprocketPosition& to);
            """,
            """
            constexpr int kToothCount = 44;
            class SprocketPosition {
            public:
                explicit SprocketPosition(int tooth);
                SprocketPosition& operator+=(int teeth);
                SprocketPosition& operator-=(int teeth);
                SprocketPosition& operator++();
                int tooth() const;
            private:
                static int normalize(int tooth);
                int tooth_;
            };
            bool operator==(const SprocketPosition& left, const SprocketPosition& right);
            bool operator!=(const SprocketPosition& left, const SprocketPosition& right);
            int mesh_delta(const SprocketPosition& from, const SprocketPosition& to);
            """,
            """
            int SprocketPosition::normalize(int tooth) {
                int wrapped = tooth % kToothCount;
                if (wrapped < 0) wrapped += kToothCount;
                return wrapped;
            }
            SprocketPosition::SprocketPosition(int tooth) : tooth_(normalize(tooth)) {}
            SprocketPosition& SprocketPosition::operator+=(int teeth) {
                tooth_ = normalize(tooth_ + teeth);
                return *this;
            }
            SprocketPosition& SprocketPosition::operator-=(int teeth) {
                tooth_ = normalize(tooth_ - teeth);
                return *this;
            }
            SprocketPosition& SprocketPosition::operator++() {
                tooth_ = normalize(tooth_ + 1);
                return *this;
            }
            int SprocketPosition::tooth() const { return tooth_; }
            bool operator==(const SprocketPosition& left, const SprocketPosition& right) {
                return left.tooth() == right.tooth();
            }
            bool operator!=(const SprocketPosition& left, const SprocketPosition& right) {
                return !(left == right);
            }
            int mesh_delta(const SprocketPosition& from, const SprocketPosition& to) {
                int forward = (to.tooth() - from.tooth()) % kToothCount;
                if (forward < 0) forward += kToothCount;
                if (forward > kToothCount / 2) forward -= kToothCount;
                return forward;
            }
            """,
            """
            int SprocketPosition::normalize(int tooth) {
                int wrapped = tooth % kToothCount;
                if (wrapped < 0) wrapped += kToothCount;
                return wrapped;
            }
            SprocketPosition::SprocketPosition(int tooth) : tooth_(normalize(tooth)) {}
            SprocketPosition& SprocketPosition::operator+=(int teeth) {
                tooth_ = normalize(tooth_ + teeth);
                return *this;
            }
            SprocketPosition& SprocketPosition::operator-=(int teeth) {
                tooth_ = normalize(tooth_ - teeth);
                return *this;
            }
            SprocketPosition& SprocketPosition::operator++() {
                tooth_ = normalize(tooth_ + 1);
                return *this;
            }
            int SprocketPosition::tooth() const { return tooth_; }
            bool operator==(const SprocketPosition& left, const SprocketPosition& right) {
                return left.tooth() == right.tooth();
            }
            bool operator!=(const SprocketPosition& left, const SprocketPosition& right) {
                return !(left == right);
            }
            int mesh_delta(const SprocketPosition& from, const SprocketPosition& to) {
                int span = to.tooth() - from.tooth();
                return (span + kToothCount / 2) % kToothCount - kToothCount / 2;
            }
            """,
            """
            SprocketPosition a(40);
            a += 7;
            if (a.tooth() != 3) return 1;
            ++a;
            if (a.tooth() != 4) return 2;
            SprocketPosition b(4);
            if (!(a == b)) return 3;
            if (a != b) return 4;
            a -= 10;
            if (a.tooth() != 38) return 5;
            if (mesh_delta(SprocketPosition(5), SprocketPosition(17)) != 12) return 6;
            if (mesh_delta(SprocketPosition(17), SprocketPosition(5)) != -12) return 7;
            if (mesh_delta(SprocketPosition(0), SprocketPosition(21)) != 21) return 8;
            return 0;
            """,
            """
            SprocketPosition neg(-5);
            if (neg.tooth() != 39) return 1;
            SprocketPosition a(43);
            ++a;
            if (a.tooth() != 0) return 2;
            SprocketPosition b(0);
            if (!(a == b)) return 3;
            SprocketPosition c(88);
            if (c.tooth() != 0) return 4;
            if (mesh_delta(SprocketPosition(0), SprocketPosition(22)) != 22) return 5;
            if (mesh_delta(SprocketPosition(22), SprocketPosition(0)) != 22) return 6;
            if (mesh_delta(SprocketPosition(40), SprocketPosition(17)) != 21) return 7;
            if (mesh_delta(SprocketPosition(2), SprocketPosition(25)) != -21) return 8;
            if (mesh_delta(SprocketPosition(43), SprocketPosition(2)) != 3) return 9;
            if (mesh_delta(SprocketPosition(10), SprocketPosition(10)) != 0) return 10;
            SprocketPosition d(30);
            d += 100;
            if (d.tooth() != 42) return 11;
            SprocketPosition e(5);
            e -= 60;
            if (e.tooth() != 33) return 12;
            SprocketPosition pre(9);
            SprocketPosition& alias = ++pre;
            if (pre.tooth() != 10 || alias.tooth() != 10) return 13;
            if (mesh_delta(SprocketPosition(43), SprocketPosition(21)) != 22) return 14;
            return 0;
            """,
            "floor-mod 44-tooth sprocket cycle with compound and pre-increment operators plus a signed mesh-delta free function",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or truncated mid computations that flip delta signs",
            "pre-increment wrap at 43, compound wraps in both directions, and signed mesh deltas at and inside the exact 22-tooth half-cycle tie",
            "signed mesh delta with tie folding on a 44-tooth cycle in a paired .h/.cpp API",
            "operator-rich modular value type",
        ),
        c(
            "f26clk-crane-hook-swivel",
            "Crane hook swivel",
            "crane_hook",
            """
            constexpr int kGradCycle = 400;
            class SwivelHeading {
            public:
                explicit SwivelHeading(int grads);
                SwivelHeading& operator+=(int grads);
                SwivelHeading& operator-=(int grads);
                int grads() const;
            };
            bool operator==(const SwivelHeading& left, const SwivelHeading& right);
            bool operator!=(const SwivelHeading& left, const SwivelHeading& right);
            bool operator<(const SwivelHeading& left, const SwivelHeading& right);
            bool operator>(const SwivelHeading& left, const SwivelHeading& right);
            unsigned swing_between(const SwivelHeading& from, const SwivelHeading& to);
            """,
            """
            constexpr int kGradCycle = 400;
            class SwivelHeading {
            public:
                explicit SwivelHeading(int grads);
                SwivelHeading& operator+=(int grads);
                SwivelHeading& operator-=(int grads);
                int grads() const;
            private:
                static int normalize(int grads);
                int grads_;
            };
            bool operator==(const SwivelHeading& left, const SwivelHeading& right);
            bool operator!=(const SwivelHeading& left, const SwivelHeading& right);
            bool operator<(const SwivelHeading& left, const SwivelHeading& right);
            bool operator>(const SwivelHeading& left, const SwivelHeading& right);
            unsigned swing_between(const SwivelHeading& from, const SwivelHeading& to);
            """,
            """
            int SwivelHeading::normalize(int grads) {
                int wrapped = grads % kGradCycle;
                if (wrapped < 0) wrapped += kGradCycle;
                return wrapped;
            }
            SwivelHeading::SwivelHeading(int grads) : grads_(normalize(grads)) {}
            SwivelHeading& SwivelHeading::operator+=(int grads) {
                grads_ = normalize(grads_ + grads);
                return *this;
            }
            SwivelHeading& SwivelHeading::operator-=(int grads) {
                grads_ = normalize(grads_ - grads);
                return *this;
            }
            int SwivelHeading::grads() const { return grads_; }
            bool operator==(const SwivelHeading& left, const SwivelHeading& right) {
                return left.grads() == right.grads();
            }
            bool operator!=(const SwivelHeading& left, const SwivelHeading& right) {
                return !(left == right);
            }
            bool operator<(const SwivelHeading& left, const SwivelHeading& right) {
                return left.grads() < right.grads();
            }
            bool operator>(const SwivelHeading& left, const SwivelHeading& right) {
                return right < left;
            }
            unsigned swing_between(const SwivelHeading& from, const SwivelHeading& to) {
                int forward = (to.grads() - from.grads()) % kGradCycle;
                if (forward < 0) forward += kGradCycle;
                return static_cast<unsigned>(forward);
            }
            """,
            """
            int SwivelHeading::normalize(int grads) {
                int wrapped = grads % kGradCycle;
                if (wrapped < 0) wrapped += kGradCycle;
                return wrapped;
            }
            SwivelHeading::SwivelHeading(int grads) : grads_(normalize(grads)) {}
            SwivelHeading& SwivelHeading::operator+=(int grads) {
                grads_ = normalize(grads_ + grads);
                return *this;
            }
            SwivelHeading& SwivelHeading::operator-=(int grads) {
                grads_ = normalize(grads_ - grads);
                return *this;
            }
            int SwivelHeading::grads() const { return grads_; }
            bool operator==(const SwivelHeading& left, const SwivelHeading& right) {
                return left.grads() == right.grads();
            }
            bool operator!=(const SwivelHeading& left, const SwivelHeading& right) {
                return !(left == right);
            }
            bool operator<(const SwivelHeading& left, const SwivelHeading& right) {
                return left.grads() < right.grads();
            }
            bool operator>(const SwivelHeading& left, const SwivelHeading& right) {
                return right < left;
            }
            unsigned swing_between(const SwivelHeading& from, const SwivelHeading& to) {
                return static_cast<unsigned>(to.grads() - from.grads());
            }
            """,
            """
            SwivelHeading a(350);
            a += 75;
            if (a.grads() != 25) return 1;
            a -= 50;
            if (a.grads() != 375) return 2;
            SwivelHeading b(375);
            if (!(a == b)) return 3;
            if (a != b) return 4;
            SwivelHeading c(50);
            SwivelHeading d(175);
            if (!(c < d)) return 5;
            if (!(d > c)) return 6;
            if (swing_between(c, d) != 125U) return 7;
            return 0;
            """,
            """
            SwivelHeading neg(-25);
            if (neg.grads() != 375) return 1;
            SwivelHeading a(399);
            a += 1;
            if (a.grads() != 0) return 2;
            SwivelHeading b(800);
            if (b.grads() != 0) return 3;
            if (!(a == b)) return 4;
            if (swing_between(SwivelHeading(300), SwivelHeading(100)) != 200U) return 5;
            if (swing_between(SwivelHeading(0), SwivelHeading(0)) != 0U) return 6;
            if (swing_between(SwivelHeading(399), SwivelHeading(1)) != 2U) return 7;
            SwivelHeading x(120);
            SwivelHeading y(310);
            if (swing_between(x, y) + swing_between(y, x) != 400U) return 8;
            SwivelHeading z(-800);
            if (z.grads() != 0) return 9;
            SwivelHeading m(250);
            m -= 700;
            if (m.grads() != 350) return 10;
            if (!(m > SwivelHeading(10))) return 11;
            SwivelHeading n(90);
            if (!(n < m)) return 12;
            if (swing_between(SwivelHeading(350), SwivelHeading(0)) != 50U) return 13;
            return 0;
            """,
            "floor-mod 400-grad swivel cycle with compound operators, normalized ordering, and an unsigned directed swing free function",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or signed raw differences masquerading as forward swings",
            "400-grad identity wraps, normalized ordering across the origin, directed swings and their complements summing to 400",
            "gradian swivel with directed swing complement in a paired .h/.cpp API",
            "operator-rich modular value type",
        ),
        c(
            "f26clk-sluice-paddle-phase",
            "Sluice paddle phase",
            "sluice_paddle",
            """
            constexpr int kPhaseCount = 8;
            class PaddlePhase {
            public:
                explicit PaddlePhase(int phase);
                PaddlePhase& operator++();
                PaddlePhase operator++(int);
                PaddlePhase& operator--();
                PaddlePhase operator--(int);
                PaddlePhase& operator+=(int phases);
                int phase() const;
            };
            bool operator==(const PaddlePhase& left, const PaddlePhase& right);
            bool operator!=(const PaddlePhase& left, const PaddlePhase& right);
            """,
            """
            constexpr int kPhaseCount = 8;
            class PaddlePhase {
            public:
                explicit PaddlePhase(int phase);
                PaddlePhase& operator++();
                PaddlePhase operator++(int);
                PaddlePhase& operator--();
                PaddlePhase operator--(int);
                PaddlePhase& operator+=(int phases);
                int phase() const;
            private:
                static int normalize(int phase);
                int phase_;
            };
            bool operator==(const PaddlePhase& left, const PaddlePhase& right);
            bool operator!=(const PaddlePhase& left, const PaddlePhase& right);
            """,
            """
            int PaddlePhase::normalize(int phase) {
                int wrapped = phase % kPhaseCount;
                if (wrapped < 0) wrapped += kPhaseCount;
                return wrapped;
            }
            PaddlePhase::PaddlePhase(int phase) : phase_(normalize(phase)) {}
            PaddlePhase& PaddlePhase::operator++() {
                phase_ = normalize(phase_ + 1);
                return *this;
            }
            PaddlePhase PaddlePhase::operator++(int) {
                PaddlePhase before(*this);
                ++(*this);
                return before;
            }
            PaddlePhase& PaddlePhase::operator--() {
                phase_ = normalize(phase_ - 1);
                return *this;
            }
            PaddlePhase PaddlePhase::operator--(int) {
                PaddlePhase before(*this);
                --(*this);
                return before;
            }
            PaddlePhase& PaddlePhase::operator+=(int phases) {
                phase_ = normalize(phase_ + phases);
                return *this;
            }
            int PaddlePhase::phase() const { return phase_; }
            bool operator==(const PaddlePhase& left, const PaddlePhase& right) {
                return left.phase() == right.phase();
            }
            bool operator!=(const PaddlePhase& left, const PaddlePhase& right) {
                return !(left == right);
            }
            """,
            """
            int PaddlePhase::normalize(int phase) {
                int wrapped = phase % kPhaseCount;
                if (wrapped < 0) wrapped += kPhaseCount;
                return wrapped;
            }
            PaddlePhase::PaddlePhase(int phase) : phase_(normalize(phase)) {}
            PaddlePhase& PaddlePhase::operator++() {
                phase_ = normalize(phase_ + 1);
                return *this;
            }
            PaddlePhase PaddlePhase::operator++(int) {
                ++(*this);
                return *this;
            }
            PaddlePhase& PaddlePhase::operator--() {
                phase_ = normalize(phase_ - 1);
                return *this;
            }
            PaddlePhase PaddlePhase::operator--(int) {
                --(*this);
                return *this;
            }
            PaddlePhase& PaddlePhase::operator+=(int phases) {
                phase_ = normalize(phase_ + phases);
                return *this;
            }
            int PaddlePhase::phase() const { return phase_; }
            bool operator==(const PaddlePhase& left, const PaddlePhase& right) {
                return left.phase() == right.phase();
            }
            bool operator!=(const PaddlePhase& left, const PaddlePhase& right) {
                return !(left == right);
            }
            """,
            """
            PaddlePhase a(7);
            ++a;
            if (a.phase() != 0) return 1;
            a += 15;
            if (a.phase() != 7) return 2;
            PaddlePhase b(15);
            if (!(a == b)) return 3;
            if (a != b) return 4;
            --b;
            if (b.phase() != 6) return 5;
            PaddlePhase& alias = --b;
            if (alias.phase() != 5 || b.phase() != 5) return 6;
            return 0;
            """,
            """
            PaddlePhase neg(-1);
            if (neg.phase() != 7) return 1;
            PaddlePhase a(3);
            PaddlePhase old = a++;
            if (old.phase() != 3 || a.phase() != 4) return 2;
            PaddlePhase b(7);
            PaddlePhase before = b++;
            if (before.phase() != 7 || b.phase() != 0) return 3;
            PaddlePhase c(0);
            PaddlePhase prev = c--;
            if (prev.phase() != 0 || c.phase() != 7) return 4;
            PaddlePhase d(5);
            PaddlePhase back = d--;
            if (back.phase() != 5 || d.phase() != 4) return 5;
            PaddlePhase e(6);
            e += 26;
            if (e.phase() != 0) return 6;
            PaddlePhase f(40);
            if (!(e == f)) return 7;
            if (e != f) return 8;
            PaddlePhase g(1);
            g += -9;
            if (g.phase() != 0) return 9;
            PaddlePhase h(7);
            ++h;
            if (h.phase() != 0) return 10;
            PaddlePhase i(0);
            --i;
            if (i.phase() != 7) return 11;
            PaddlePhase post(2);
            if ((post++).phase() != 2) return 12;
            if (post.phase() != 3) return 13;
            return 0;
            """,
            "floor-mod 8-phase paddle cycle with pre and post increment and decrement pairs plus compound addition",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or postfix operators that return the updated value",
            "pre and post return values across the origin in both directions, compound wraps, and representation-blind equality",
            "small-cycle value stressing pre/post operator semantics in a paired .h/.cpp API",
            "operator-rich modular value type",
        ),
        c(
            "f26clk-turbine-blade-index",
            "Turbine blade index",
            "turbine_blade",
            """
            constexpr int kBladeCount = 28;
            class BladeIndex {
            public:
                explicit BladeIndex(int blade);
                BladeIndex& operator+=(int blades);
                BladeIndex& operator-=(int blades);
                int blade() const;
            };
            bool operator==(const BladeIndex& left, const BladeIndex& right);
            bool operator!=(const BladeIndex& left, const BladeIndex& right);
            unsigned blade_gap(const BladeIndex& from, const BladeIndex& to);
            int signed_gap(const BladeIndex& from, const BladeIndex& to);
            """,
            """
            constexpr int kBladeCount = 28;
            class BladeIndex {
            public:
                explicit BladeIndex(int blade);
                BladeIndex& operator+=(int blades);
                BladeIndex& operator-=(int blades);
                int blade() const;
            private:
                static int normalize(int blade);
                int blade_;
            };
            bool operator==(const BladeIndex& left, const BladeIndex& right);
            bool operator!=(const BladeIndex& left, const BladeIndex& right);
            unsigned blade_gap(const BladeIndex& from, const BladeIndex& to);
            int signed_gap(const BladeIndex& from, const BladeIndex& to);
            """,
            """
            int BladeIndex::normalize(int blade) {
                int wrapped = blade % kBladeCount;
                if (wrapped < 0) wrapped += kBladeCount;
                return wrapped;
            }
            BladeIndex::BladeIndex(int blade) : blade_(normalize(blade)) {}
            BladeIndex& BladeIndex::operator+=(int blades) {
                blade_ = normalize(blade_ + blades);
                return *this;
            }
            BladeIndex& BladeIndex::operator-=(int blades) {
                blade_ = normalize(blade_ - blades);
                return *this;
            }
            int BladeIndex::blade() const { return blade_; }
            bool operator==(const BladeIndex& left, const BladeIndex& right) {
                return left.blade() == right.blade();
            }
            bool operator!=(const BladeIndex& left, const BladeIndex& right) {
                return !(left == right);
            }
            unsigned blade_gap(const BladeIndex& from, const BladeIndex& to) {
                int forward = (to.blade() - from.blade()) % kBladeCount;
                if (forward < 0) forward += kBladeCount;
                return static_cast<unsigned>(forward);
            }
            int signed_gap(const BladeIndex& from, const BladeIndex& to) {
                int forward = (to.blade() - from.blade()) % kBladeCount;
                if (forward < 0) forward += kBladeCount;
                if (forward > kBladeCount / 2) forward -= kBladeCount;
                return forward;
            }
            """,
            """
            int BladeIndex::normalize(int blade) {
                int wrapped = blade % kBladeCount;
                if (wrapped < 0) wrapped += kBladeCount;
                return wrapped;
            }
            BladeIndex::BladeIndex(int blade) : blade_(normalize(blade)) {}
            BladeIndex& BladeIndex::operator+=(int blades) {
                blade_ = normalize(blade_ + blades);
                return *this;
            }
            BladeIndex& BladeIndex::operator-=(int blades) {
                blade_ = normalize(blade_ - blades);
                return *this;
            }
            int BladeIndex::blade() const { return blade_; }
            bool operator==(const BladeIndex& left, const BladeIndex& right) {
                return left.blade() == right.blade();
            }
            bool operator!=(const BladeIndex& left, const BladeIndex& right) {
                return !(left == right);
            }
            unsigned blade_gap(const BladeIndex& from, const BladeIndex& to) {
                int forward = (to.blade() - from.blade()) % kBladeCount;
                if (forward < 0) forward += kBladeCount;
                return static_cast<unsigned>(forward);
            }
            int signed_gap(const BladeIndex& from, const BladeIndex& to) {
                int forward = (to.blade() - from.blade()) % kBladeCount;
                if (forward < 0) forward += kBladeCount;
                if (forward >= kBladeCount / 2) forward -= kBladeCount;
                return forward;
            }
            """,
            """
            BladeIndex a(25);
            a += 5;
            if (a.blade() != 2) return 1;
            a -= 10;
            if (a.blade() != 20) return 2;
            BladeIndex b(48);
            if (!(a == b)) return 3;
            if (a != b) return 4;
            if (blade_gap(BladeIndex(3), BladeIndex(11)) != 8U) return 5;
            if (signed_gap(BladeIndex(3), BladeIndex(11)) != 8) return 6;
            if (signed_gap(BladeIndex(11), BladeIndex(3)) != -8) return 7;
            return 0;
            """,
            """
            BladeIndex neg(-2);
            if (neg.blade() != 26) return 1;
            BladeIndex a(27);
            a += 1;
            if (a.blade() != 0) return 2;
            BladeIndex b(56);
            if (!(a == b)) return 3;
            if (blade_gap(BladeIndex(20), BladeIndex(5)) != 13U) return 4;
            if (signed_gap(BladeIndex(0), BladeIndex(14)) != 14) return 5;
            if (signed_gap(BladeIndex(14), BladeIndex(0)) != 14) return 6;
            if (signed_gap(BladeIndex(1), BladeIndex(16)) != -13) return 7;
            if (blade_gap(BladeIndex(14), BladeIndex(14)) != 0U) return 8;
            if (signed_gap(BladeIndex(9), BladeIndex(9)) != 0) return 9;
            BladeIndex c(10);
            c += 100;
            if (c.blade() != 26) return 10;
            BladeIndex d(3);
            d -= 50;
            if (d.blade() != 9) return 11;
            BladeIndex e(7);
            BladeIndex f(21);
            if (blade_gap(e, f) + blade_gap(f, e) != 28U) return 12;
            if (signed_gap(e, f) != 14) return 13;
            if (signed_gap(BladeIndex(26), BladeIndex(12)) != 14) return 14;
            return 0;
            """,
            "floor-mod 28-blade turbine cycle with compound operators plus complementary unsigned forward and signed shortest gap functions",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or tie-flipped shortest gaps",
            "both gaps at exact opposite blades, gap complements summing to 28, and wrap arithmetic in both directions",
            "dual directed/shortest gap functions with exact ties in a paired .h/.cpp API",
            "operator-rich modular value type",
        ),

        c(
            "f26clk-regatta-start-sequence",
            "Regatta start sequence",
            "regatta_start",
            """
            class SequenceError : public std::invalid_argument {
            public:
                explicit SequenceError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kSignalSlots = 12;
            constexpr int kSecondsPerSlot = 30;
            int slot_of(int seconds);
            int advance_slot(int slot, int steps);
            int signals_between(int from, int to);
            bool is_gun(int slot);
            """,
            """
            class SequenceError : public std::invalid_argument {
            public:
                explicit SequenceError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kSignalSlots = 12;
            constexpr int kSecondsPerSlot = 30;
            int slot_of(int seconds);
            int advance_slot(int slot, int steps);
            int signals_between(int from, int to);
            bool is_gun(int slot);
            """,
            """
            namespace {
            int normalize_slot(int slot) {
                int wrapped = slot % kSignalSlots;
                if (wrapped < 0) wrapped += kSignalSlots;
                return wrapped;
            }
            void require_slot(int slot) {
                if (slot < 0 || slot >= kSignalSlots) throw SequenceError("slot out of range");
            }
            }
            int slot_of(int seconds) {
                if (seconds < 0 || seconds % kSecondsPerSlot != 0) {
                    throw SequenceError("seconds must be a nonnegative multiple of 30");
                }
                return (seconds / kSecondsPerSlot) % kSignalSlots;
            }
            int advance_slot(int slot, int steps) {
                require_slot(slot);
                return normalize_slot(slot + steps);
            }
            int signals_between(int from, int to) {
                require_slot(from);
                require_slot(to);
                int forward = to - from;
                if (forward < 0) forward += kSignalSlots;
                return forward == 0 ? 0 : forward - 1;
            }
            bool is_gun(int slot) {
                require_slot(slot);
                return slot == 0;
            }
            """,
            """
            namespace {
            int normalize_slot(int slot) {
                int wrapped = slot % kSignalSlots;
                if (wrapped < 0) wrapped += kSignalSlots;
                return wrapped;
            }
            void require_slot(int slot) {
                if (slot < 0 || slot >= kSignalSlots) throw SequenceError("slot out of range");
            }
            }
            int slot_of(int seconds) {
                if (seconds < 0 || seconds % kSecondsPerSlot != 0) {
                    throw SequenceError("seconds must be a nonnegative multiple of 30");
                }
                return (seconds / kSecondsPerSlot) % kSignalSlots;
            }
            int advance_slot(int slot, int steps) {
                require_slot(slot);
                return normalize_slot(slot + steps);
            }
            int signals_between(int from, int to) {
                require_slot(from);
                require_slot(to);
                int forward = to - from;
                if (forward < 0) forward += kSignalSlots;
                return forward;
            }
            bool is_gun(int slot) {
                require_slot(slot);
                return slot == 0;
            }
            """,
            """
            if (slot_of(0) != 0) return 1;
            if (slot_of(90) != 3) return 2;
            if (slot_of(360) != 0) return 3;
            if (advance_slot(10, 5) != 3) return 4;
            if (signals_between(2, 5) != 2) return 5;
            if (!is_gun(0)) return 6;
            if (is_gun(7)) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { slot_of(-30); } catch (const SequenceError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { slot_of(45); } catch (const SequenceError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { advance_slot(12, 1); } catch (const SequenceError&) { threw = true; }
            if (!threw) return 3;
            if (advance_slot(11, -3) != 8) return 4;
            if (advance_slot(2, 24) != 2) return 5;
            if (signals_between(10, 2) != 3) return 6;
            if (signals_between(5, 5) != 0) return 7;
            if (signals_between(5, 6) != 0) return 8;
            if (signals_between(0, 11) != 10) return 9;
            threw = false;
            try { is_gun(-1); } catch (const SequenceError&) { threw = true; }
            if (!threw) return 10;
            if (slot_of(750) != 1) return 11;
            return 0;
            """,
            "stateless floor-mod signal-slot math with typed argument validation and strictly-between forward counting",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or inclusive endpoint counting",
            "rejection channels, multi-cycle slot advances in both directions, forward strictly-between counts across slot 0",
            "stateless validated cycle math with an off-by-one discriminator",
            "free-function modular calculator with exceptions",
        ),
        c(
            "f26clk-switchback-rail-milepost",
            "Switchback rail milepost",
            "switchback_rail",
            """
            class RailError : public std::invalid_argument {
            public:
                explicit RailError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kPosts = 100;
            constexpr int kLegs = 5;
            constexpr int kPostsPerLeg = 20;
            int post_after(int post, int chains);
            int posts_between(int from, int to);
            int leg_of(int post);
            bool climbs(int leg);
            """,
            """
            class RailError : public std::invalid_argument {
            public:
                explicit RailError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kPosts = 100;
            constexpr int kLegs = 5;
            constexpr int kPostsPerLeg = 20;
            int post_after(int post, int chains);
            int posts_between(int from, int to);
            int leg_of(int post);
            bool climbs(int leg);
            """,
            """
            namespace {
            int normalize_post(int post) {
                int wrapped = post % kPosts;
                if (wrapped < 0) wrapped += kPosts;
                return wrapped;
            }
            void require_post(int post) {
                if (post < 0 || post >= kPosts) throw RailError("post out of range");
            }
            void require_leg(int leg) {
                if (leg < 0 || leg >= kLegs) throw RailError("leg out of range");
            }
            int fold_leg(int index) {
                int leg = index / kPostsPerLeg;
                int offset = index % kPostsPerLeg;
                return climbs(leg) ? leg * kPostsPerLeg + offset
                                   : leg * kPostsPerLeg + (kPostsPerLeg - 1 - offset);
            }
            }
            int post_after(int post, int chains) {
                require_post(post);
                return fold_leg(normalize_post(fold_leg(post) + chains));
            }
            int posts_between(int from, int to) {
                require_post(from);
                require_post(to);
                int forward = fold_leg(to) - fold_leg(from);
                if (forward < 0) forward += kPosts;
                return forward;
            }
            int leg_of(int post) {
                require_post(post);
                return post / kPostsPerLeg;
            }
            bool climbs(int leg) {
                require_leg(leg);
                return leg % 2 == 0;
            }
            """,
            """
            namespace {
            int normalize_post(int post) {
                int wrapped = post % kPosts;
                if (wrapped < 0) wrapped += kPosts;
                return wrapped;
            }
            void require_post(int post) {
                if (post < 0 || post >= kPosts) throw RailError("post out of range");
            }
            void require_leg(int leg) {
                if (leg < 0 || leg >= kLegs) throw RailError("leg out of range");
            }
            }
            int post_after(int post, int chains) {
                require_post(post);
                return normalize_post(post + chains);
            }
            int posts_between(int from, int to) {
                require_post(from);
                require_post(to);
                int forward = to - from;
                if (forward < 0) forward += kPosts;
                return forward;
            }
            int leg_of(int post) {
                require_post(post);
                return post / kPostsPerLeg;
            }
            bool climbs(int leg) {
                require_leg(leg);
                return leg % 2 == 0;
            }
            """,
            """
            if (post_after(5, 3) != 8) return 1;
            if (post_after(95, 12) != 7) return 2;
            if (posts_between(40, 55) != 15) return 3;
            if (posts_between(90, 10) != 20) return 4;
            if (leg_of(60) != 3) return 5;
            if (!climbs(0)) return 6;
            if (climbs(1)) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { post_after(100, 1); } catch (const RailError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { post_after(-1, 1); } catch (const RailError&) { threw = true; }
            if (!threw) return 2;
            if (post_after(17, 6) != 36) return 3;
            if (post_after(36, -8) != 15) return 4;
            if (post_after(36, 250) != 66) return 5;
            if (post_after(99, 1) != 0) return 6;
            if (post_after(0, -1) != 99) return 7;
            if (posts_between(36, 17) != 94) return 8;
            if (posts_between(20, 39) != 81) return 9;
            if (posts_between(7, 7) != 0) return 10;
            threw = false;
            try { posts_between(0, 100); } catch (const RailError&) { threw = true; }
            if (!threw) return 11;
            threw = false;
            try { posts_between(-4, 0); } catch (const RailError&) { threw = true; }
            if (!threw) return 12;
            if (leg_of(0) != 0) return 13;
            if (leg_of(19) != 0) return 14;
            if (leg_of(20) != 1) return 15;
            if (leg_of(99) != 4) return 16;
            threw = false;
            try { leg_of(100); } catch (const RailError&) { threw = true; }
            if (!threw) return 17;
            if (!climbs(0)) return 18;
            if (climbs(1)) return 19;
            if (!climbs(2)) return 20;
            if (climbs(3)) return 21;
            if (!climbs(4)) return 22;
            threw = false;
            try { climbs(5); } catch (const RailError&) { threw = true; }
            if (!threw) return 23;
            threw = false;
            try { climbs(-1); } catch (const RailError&) { threw = true; }
            if (!threw) return 24;
            return 0;
            """,
            "stateless zigzag walk over 100 posts in 5 legs of 20 where even legs climb forward and odd legs descend, folding the path index per leg parity",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or a fixed-direction modulo walk that ignores leg parity",
            "walks crossing multiple leg boundaries in both directions, leg_of band boundaries, climbs parity, rejection of out-of-range posts and legs",
            "direction-alternating walk, materially distinct from plain wrap roots",
            "free-function modular calculator with exceptions",
        ),
        c(
            "f26clk-orbit-ground-track",
            "Orbit ground track",
            "orbit_track",
            """
            class TrackError : public std::invalid_argument {
            public:
                explicit TrackError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kSlots = 96;
            constexpr int kMinutesPerSlot = 15;
            int slot_at(int minutes);
            int slots_until(int from, int to);
            int dawn_crossings(int from, int forward_steps);
            bool over_dawn(int slot);
            """,
            """
            class TrackError : public std::invalid_argument {
            public:
                explicit TrackError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kSlots = 96;
            constexpr int kMinutesPerSlot = 15;
            int slot_at(int minutes);
            int slots_until(int from, int to);
            int dawn_crossings(int from, int forward_steps);
            bool over_dawn(int slot);
            """,
            """
            namespace {
            void require_slot(int slot) {
                if (slot < 0 || slot >= kSlots) throw TrackError("slot out of range");
            }
            }
            int slot_at(int minutes) {
                if (minutes < 0 || minutes % kMinutesPerSlot != 0) {
                    throw TrackError("minutes must be a nonnegative multiple of 15");
                }
                return (minutes / kMinutesPerSlot) % kSlots;
            }
            int slots_until(int from, int to) {
                require_slot(from);
                require_slot(to);
                int forward = to - from;
                if (forward < 0) forward += kSlots;
                return forward;
            }
            int dawn_crossings(int from, int forward_steps) {
                require_slot(from);
                if (forward_steps < 0) throw TrackError("forward steps must be nonnegative");
                int first = from == 0 ? kSlots : kSlots - from;
                if (forward_steps < first) return 0;
                return 1 + (forward_steps - first) / kSlots;
            }
            bool over_dawn(int slot) {
                require_slot(slot);
                return slot == 0;
            }
            """,
            """
            namespace {
            void require_slot(int slot) {
                if (slot < 0 || slot >= kSlots) throw TrackError("slot out of range");
            }
            }
            int slot_at(int minutes) {
                if (minutes < 0 || minutes % kMinutesPerSlot != 0) {
                    throw TrackError("minutes must be a nonnegative multiple of 15");
                }
                return (minutes / kMinutesPerSlot) % kSlots;
            }
            int slots_until(int from, int to) {
                require_slot(from);
                require_slot(to);
                int forward = to - from;
                if (forward < 0) forward += kSlots;
                return forward;
            }
            int dawn_crossings(int from, int forward_steps) {
                require_slot(from);
                if (forward_steps < 0) throw TrackError("forward steps must be nonnegative");
                int first = from == 0 ? kSlots : kSlots - from;
                int count = from == 0 ? 1 : 0;
                if (forward_steps >= first) count += 1 + (forward_steps - first) / kSlots;
                return count;
            }
            bool over_dawn(int slot) {
                require_slot(slot);
                return slot == 0;
            }
            """,
            """
            if (slot_at(0) != 0) return 1;
            if (slot_at(210) != 14) return 2;
            if (slot_at(1440) != 0) return 3;
            if (slots_until(80, 20) != 36) return 4;
            if (slots_until(30, 30) != 0) return 5;
            if (dawn_crossings(90, 20) != 1) return 6;
            if (dawn_crossings(40, 200) != 2) return 7;
            if (!over_dawn(0)) return 8;
            if (over_dawn(55)) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { slot_at(-15); } catch (const TrackError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { slot_at(7); } catch (const TrackError&) { threw = true; }
            if (!threw) return 2;
            if (slot_at(1440) != 0) return 3;
            if (slot_at(1455) != 1) return 4;
            if (slot_at(30) != 2) return 5;
            if (slots_until(95, 0) != 1) return 6;
            if (slots_until(0, 95) != 95) return 7;
            if (slots_until(50, 50) != 0) return 8;
            threw = false;
            try { slots_until(96, 0); } catch (const TrackError&) { threw = true; }
            if (!threw) return 9;
            threw = false;
            try { slots_until(0, -1); } catch (const TrackError&) { threw = true; }
            if (!threw) return 10;
            if (dawn_crossings(0, 10) != 0) return 11;
            if (dawn_crossings(0, 96) != 1) return 12;
            if (dawn_crossings(0, 192) != 2) return 13;
            if (dawn_crossings(48, 96) != 1) return 14;
            if (dawn_crossings(20, 300) != 3) return 15;
            threw = false;
            try { dawn_crossings(5, -1); } catch (const TrackError&) { threw = true; }
            if (!threw) return 16;
            if (!over_dawn(0)) return 17;
            if (over_dawn(95)) return 18;
            threw = false;
            try { over_dawn(96); } catch (const TrackError&) { threw = true; }
            if (!threw) return 19;
            return 0;
            """,
            "stateless floor-mod slot math over 96 ground slots of 15 minutes with exact slot-0 dawn-crossing counts",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or counting the departure slot as a crossing",
            "rejection channels, wrap forward distances, dawn-crossing counts over multiple orbits including a slot-0 start",
            "slot-cycle math with exact crossing counting",
            "free-function modular calculator with exceptions",
        ),
        c(
            "f26clk-belfry-pull-order",
            "Belfry pull order",
            "belfry_pull",
            """
            class BellError : public std::invalid_argument {
            public:
                explicit BellError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kBells = 6;
            int lead_after(int bell, int pulls);
            int pull_distance(int from, int to);
            std::vector<int> pull_order(int start, int count);
            """,
            """
            class BellError : public std::invalid_argument {
            public:
                explicit BellError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kBells = 6;
            int lead_after(int bell, int pulls);
            int pull_distance(int from, int to);
            std::vector<int> pull_order(int start, int count);
            """,
            """
            namespace {
            int normalize_bell(int bell) {
                int wrapped = bell % kBells;
                if (wrapped < 0) wrapped += kBells;
                return wrapped;
            }
            void require_bell(int bell) {
                if (bell < 0 || bell >= kBells) throw BellError("bell out of range");
            }
            }
            int lead_after(int bell, int pulls) {
                require_bell(bell);
                return normalize_bell(bell + pulls);
            }
            int pull_distance(int from, int to) {
                require_bell(from);
                require_bell(to);
                int forward = to - from;
                if (forward < 0) forward += kBells;
                return forward;
            }
            std::vector<int> pull_order(int start, int count) {
                require_bell(start);
                if (count < 0) throw BellError("count must be nonnegative");
                std::vector<int> order;
                order.reserve(static_cast<std::size_t>(count));
                for (int i = 1; i <= count; ++i) order.push_back(normalize_bell(start + i));
                return order;
            }
            """,
            """
            namespace {
            int normalize_bell(int bell) {
                int wrapped = bell % kBells;
                if (wrapped < 0) wrapped += kBells;
                return wrapped;
            }
            void require_bell(int bell) {
                if (bell < 0 || bell >= kBells) throw BellError("bell out of range");
            }
            }
            int lead_after(int bell, int pulls) {
                require_bell(bell);
                return normalize_bell(bell + pulls);
            }
            int pull_distance(int from, int to) {
                require_bell(from);
                require_bell(to);
                int forward = to - from;
                if (forward < 0) forward += kBells;
                return forward;
            }
            std::vector<int> pull_order(int start, int count) {
                require_bell(start);
                if (count < 0) throw BellError("count must be nonnegative");
                std::vector<int> order;
                order.reserve(static_cast<std::size_t>(count));
                for (int i = 0; i < count; ++i) order.push_back(normalize_bell(start + i));
                return order;
            }
            """,
            """
            if (lead_after(4, 5) != 3) return 1;
            if (lead_after(1, -2) != 5) return 2;
            if (lead_after(3, 12) != 3) return 3;
            if (pull_distance(5, 2) != 3) return 4;
            if (pull_distance(2, 5) != 3) return 5;
            if (pull_distance(0, 0) != 0) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { lead_after(6, 1); } catch (const BellError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { lead_after(-1, 1); } catch (const BellError&) { threw = true; }
            if (!threw) return 2;
            if (lead_after(3, 12) != 3) return 3;
            if (lead_after(0, -7) != 5) return 4;
            threw = false;
            try { pull_distance(0, 6); } catch (const BellError&) { threw = true; }
            if (!threw) return 5;
            threw = false;
            try { pull_distance(-2, 0); } catch (const BellError&) { threw = true; }
            if (!threw) return 6;
            if (pull_distance(3, 3) != 0) return 7;
            if (pull_distance(5, 0) != 1) return 8;
            threw = false;
            try { pull_order(6, 3); } catch (const BellError&) { threw = true; }
            if (!threw) return 9;
            threw = false;
            try { pull_order(0, -1); } catch (const BellError&) { threw = true; }
            if (!threw) return 10;
            if (pull_order(2, 4) != std::vector<int>({3, 4, 5, 0})) return 11;
            if (pull_order(5, 6) != std::vector<int>({0, 1, 2, 3, 4, 5})) return 12;
            if (pull_order(4, 8) != std::vector<int>({5, 0, 1, 2, 3, 4, 5, 0})) return 13;
            if (!pull_order(0, 0).empty()) return 14;
            if (pull_order(1, 13).size() != 13U) return 15;
            if (pull_order(1, 13) != std::vector<int>({2, 3, 4, 5, 0, 1, 2, 3, 4, 5, 0, 1, 2})) return 16;
            return 0;
            """,
            "stateless forward cycle math over 6 bells plus exact pull-sequence generation that starts after the lead bell",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or sequences that include the starting bell",
            "sequences wrapping multiple rounds, exact order content, forward distance complement, rejection of bell 6/-1 and count -1",
            "deterministic sequence generation with exact order assertions",
            "free-function modular calculator with exceptions",
        ),
        c(
            "f26clk-carousel-ride-ticket",
            "Carousel ride ticket",
            "carousel_ticket",
            """
            class TicketError : public std::invalid_argument {
            public:
                explicit TicketError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kMounts = 18;
            int mount_for(int ticket);
            int spins_to(int from, int to);
            int tickets_between(int from, int to);
            bool is_lead_mount(int mount);
            """,
            """
            class TicketError : public std::invalid_argument {
            public:
                explicit TicketError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kMounts = 18;
            int mount_for(int ticket);
            int spins_to(int from, int to);
            int tickets_between(int from, int to);
            bool is_lead_mount(int mount);
            """,
            """
            namespace {
            void require_mount(int mount) {
                if (mount < 0 || mount >= kMounts) throw TicketError("mount out of range");
            }
            }
            int mount_for(int ticket) {
                if (ticket < 1) throw TicketError("ticket numbers start at 1");
                return (ticket - 1) % kMounts;
            }
            int spins_to(int from, int to) {
                require_mount(from);
                require_mount(to);
                int forward = to - from;
                if (forward < 0) forward += kMounts;
                return forward;
            }
            int tickets_between(int from, int to) {
                int forward = spins_to(from, to);
                return forward == 0 ? 0 : forward - 1;
            }
            bool is_lead_mount(int mount) {
                require_mount(mount);
                return mount == 0;
            }
            """,
            """
            namespace {
            void require_mount(int mount) {
                if (mount < 0 || mount >= kMounts) throw TicketError("mount out of range");
            }
            }
            int mount_for(int ticket) {
                if (ticket < 1) throw TicketError("ticket numbers start at 1");
                return ticket % kMounts;
            }
            int spins_to(int from, int to) {
                require_mount(from);
                require_mount(to);
                int forward = to - from;
                if (forward < 0) forward += kMounts;
                return forward;
            }
            int tickets_between(int from, int to) {
                int forward = spins_to(from, to);
                return forward == 0 ? 0 : forward - 1;
            }
            bool is_lead_mount(int mount) {
                require_mount(mount);
                return mount == 0;
            }
            """,
            """
            if (spins_to(3, 9) != 6) return 1;
            if (spins_to(15, 2) != 5) return 2;
            if (spins_to(17, 0) != 1) return 3;
            if (tickets_between(2, 7) != 4) return 4;
            if (tickets_between(9, 9) != 0) return 5;
            if (!is_lead_mount(0)) return 6;
            if (is_lead_mount(11)) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { mount_for(0); } catch (const TicketError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { mount_for(-3); } catch (const TicketError&) { threw = true; }
            if (!threw) return 2;
            if (mount_for(1) != 0) return 3;
            if (mount_for(18) != 17) return 4;
            if (mount_for(19) != 0) return 5;
            if (mount_for(37) != 0) return 6;
            if (mount_for(20) != 1) return 7;
            if (spins_to(4, 4) != 0) return 8;
            if (spins_to(0, 17) != 17) return 9;
            threw = false;
            try { spins_to(0, 18); } catch (const TicketError&) { threw = true; }
            if (!threw) return 10;
            threw = false;
            try { spins_to(-1, 0); } catch (const TicketError&) { threw = true; }
            if (!threw) return 11;
            if (tickets_between(16, 3) != 4) return 12;
            if (tickets_between(3, 3) != 0) return 13;
            if (tickets_between(3, 4) != 0) return 14;
            if (tickets_between(5, 4) != 16) return 15;
            if (!is_lead_mount(0)) return 16;
            if (is_lead_mount(17)) return 17;
            threw = false;
            try { is_lead_mount(18); } catch (const TicketError&) { threw = true; }
            if (!threw) return 18;
            threw = false;
            try { is_lead_mount(-1); } catch (const TicketError&) { threw = true; }
            if (!threw) return 19;
            return 0;
            """,
            "stateless cycle math over 18 mounts with a 1-based ticket-to-mount mapping and exact rejection for ticket 0",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or 0-based ticket mapping",
            "ticket 0/-3 rejection, 1-based wrap at tickets 18/19, forward distances, strictly-between counts, lead-mount marking",
            "one-based cyclic mapping with exact rejection channel",
            "free-function modular calculator with exceptions",
        ),
        c(
            "f26clk-paddock-show-round",
            "Paddock show round",
            "paddock_show",
            """
            class PaddockError : public std::invalid_argument {
            public:
                explicit PaddockError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kStalls = 15;
            int stall_after(int stall, int walks);
            int stalls_between(int from, int to);
            std::vector<int> walk_order(int start, int count);
            """,
            """
            class PaddockError : public std::invalid_argument {
            public:
                explicit PaddockError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kStalls = 15;
            int stall_after(int stall, int walks);
            int stalls_between(int from, int to);
            std::vector<int> walk_order(int start, int count);
            """,
            """
            namespace {
            int normalize_stall(int stall) {
                int wrapped = stall % kStalls;
                if (wrapped < 0) wrapped += kStalls;
                return wrapped;
            }
            void require_stall(int stall) {
                if (stall < 0 || stall >= kStalls) throw PaddockError("stall out of range");
            }
            }
            int stall_after(int stall, int walks) {
                require_stall(stall);
                return normalize_stall(stall + walks);
            }
            int stalls_between(int from, int to) {
                require_stall(from);
                require_stall(to);
                int forward = to - from;
                if (forward < 0) forward += kStalls;
                return forward;
            }
            std::vector<int> walk_order(int start, int count) {
                require_stall(start);
                if (count < 0) throw PaddockError("count must be nonnegative");
                std::vector<int> order;
                order.reserve(static_cast<std::size_t>(count));
                for (int i = 0; i < count; ++i) order.push_back(normalize_stall(start + i));
                return order;
            }
            """,
            """
            namespace {
            int normalize_stall(int stall) {
                int wrapped = stall % kStalls;
                if (wrapped < 0) wrapped += kStalls;
                return wrapped;
            }
            void require_stall(int stall) {
                if (stall < 0 || stall >= kStalls) throw PaddockError("stall out of range");
            }
            }
            int stall_after(int stall, int walks) {
                require_stall(stall);
                return normalize_stall(stall + walks);
            }
            int stalls_between(int from, int to) {
                require_stall(from);
                require_stall(to);
                int forward = to - from;
                if (forward < 0) forward += kStalls;
                int backward = kStalls - forward;
                return forward < backward ? forward : backward;
            }
            std::vector<int> walk_order(int start, int count) {
                require_stall(start);
                if (count < 0) throw PaddockError("count must be nonnegative");
                std::vector<int> order;
                order.reserve(static_cast<std::size_t>(count));
                for (int i = 0; i < count; ++i) order.push_back(normalize_stall(start + i));
                return order;
            }
            """,
            """
            if (stall_after(13, 5) != 3) return 1;
            if (stall_after(2, -4) != 13) return 2;
            if (stall_after(0, 31) != 1) return 3;
            if (stalls_between(3, 9) != 6) return 4;
            if (stalls_between(11, 2) != 6) return 5;
            if (stalls_between(4, 4) != 0) return 6;
            if (walk_order(12, 4) != std::vector<int>({12, 13, 14, 0})) return 7;
            if (walk_order(0, 3) != std::vector<int>({0, 1, 2})) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { stall_after(15, 1); } catch (const PaddockError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { stall_after(-1, 1); } catch (const PaddockError&) { threw = true; }
            if (!threw) return 2;
            if (stall_after(0, 31) != 1) return 3;
            if (stall_after(5, -32) != 3) return 4;
            if (stall_after(14, 1) != 0) return 5;
            if (stall_after(0, -1) != 14) return 6;
            if (stalls_between(2, 10) != 8) return 7;
            if (stalls_between(1, 13) != 12) return 8;
            if (stalls_between(6, 6) != 0) return 9;
            threw = false;
            try { stalls_between(0, 15); } catch (const PaddockError&) { threw = true; }
            if (!threw) return 10;
            threw = false;
            try { stalls_between(16, 0); } catch (const PaddockError&) { threw = true; }
            if (!threw) return 11;
            threw = false;
            try { walk_order(15, 2); } catch (const PaddockError&) { threw = true; }
            if (!threw) return 12;
            threw = false;
            try { walk_order(0, -1); } catch (const PaddockError&) { threw = true; }
            if (!threw) return 13;
            if (walk_order(7, 15) != std::vector<int>({7, 8, 9, 10, 11, 12, 13, 14, 0, 1, 2, 3, 4, 5, 6})) return 14;
            if (!walk_order(9, 0).empty()) return 15;
            if (walk_order(3, 17) != std::vector<int>({3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 0, 1, 2, 3, 4})) return 16;
            return 0;
            """,
            "stateless forward-only distance discipline over a 15-stall round plus inclusive walk-sequence generation",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or shortest-direction distances",
            "multi-round sequences, forward wrap distances that reject the shorter-direction substitute, rejection channels",
            "forward-only distance discipline on a 15-stall round",
            "free-function modular calculator with exceptions",
        ),
        c(
            "f26clk-beacon-rota-keeper",
            "Beacon rota keeper",
            "beacon_rota",
            """
            class RotaError : public std::invalid_argument {
            public:
                explicit RotaError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kKeepers = 5;
            constexpr int kNights = 28;
            constexpr int kBandNights = 6;
            int keeper_on(int night);
            int nights_until(int keeper, int night);
            std::vector<int> schedule(int keeper, int nights);
            """,
            """
            class RotaError : public std::invalid_argument {
            public:
                explicit RotaError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kKeepers = 5;
            constexpr int kNights = 28;
            constexpr int kBandNights = 6;
            int keeper_on(int night);
            int nights_until(int keeper, int night);
            std::vector<int> schedule(int keeper, int nights);
            """,
            """
            namespace {
            void require_keeper(int keeper) {
                if (keeper < 0 || keeper >= kKeepers) throw RotaError("keeper out of range");
            }
            void require_night(int night) {
                if (night < 0 || night >= kNights) throw RotaError("night out of range");
            }
            }
            int keeper_on(int night) {
                require_night(night);
                return night / kBandNights;
            }
            int nights_until(int keeper, int night) {
                require_keeper(keeper);
                require_night(night);
                for (int ahead = 0; ahead < kNights; ++ahead) {
                    if (keeper_on((night + ahead) % kNights) == keeper) return ahead;
                }
                return kNights;
            }
            std::vector<int> schedule(int keeper, int nights) {
                require_keeper(keeper);
                if (nights < 0) throw RotaError("nights must be nonnegative");
                std::vector<int> duty;
                for (int night = 0; night < nights; ++night) {
                    if (keeper_on(night % kNights) == keeper) duty.push_back(night);
                }
                return duty;
            }
            """,
            """
            namespace {
            void require_keeper(int keeper) {
                if (keeper < 0 || keeper >= kKeepers) throw RotaError("keeper out of range");
            }
            void require_night(int night) {
                if (night < 0 || night >= kNights) throw RotaError("night out of range");
            }
            }
            int keeper_on(int night) {
                require_night(night);
                return night % kKeepers;
            }
            int nights_until(int keeper, int night) {
                require_keeper(keeper);
                require_night(night);
                for (int ahead = 0; ahead < kNights; ++ahead) {
                    if (keeper_on((night + ahead) % kNights) == keeper) return ahead;
                }
                return kNights;
            }
            std::vector<int> schedule(int keeper, int nights) {
                require_keeper(keeper);
                if (nights < 0) throw RotaError("nights must be nonnegative");
                std::vector<int> duty;
                for (int night = 0; night < nights; ++night) {
                    if (keeper_on(night % kNights) == keeper) duty.push_back(night);
                }
                return duty;
            }
            """,
            """
            if (keeper_on(0) != 0) return 1;
            if (keeper_on(6) != 1) return 2;
            if (keeper_on(12) != 2) return 3;
            if (keeper_on(18) != 3) return 4;
            if (keeper_on(24) != 4) return 5;
            if (nights_until(0, 0) != 0) return 6;
            if (nights_until(2, 12) != 0) return 7;
            if (nights_until(4, 24) != 0) return 8;
            if (schedule(0, 1) != std::vector<int>({0})) return 9;
            if (!schedule(2, 0).empty()) return 10;
            return 0;
            """,
            """
            bool threw = false;
            try { keeper_on(28); } catch (const RotaError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { keeper_on(-1); } catch (const RotaError&) { threw = true; }
            if (!threw) return 2;
            if (keeper_on(1) != 0) return 3;
            if (keeper_on(5) != 0) return 4;
            if (keeper_on(11) != 1) return 5;
            if (keeper_on(13) != 2) return 6;
            if (keeper_on(17) != 2) return 7;
            if (keeper_on(23) != 3) return 8;
            if (keeper_on(27) != 4) return 9;
            threw = false;
            try { nights_until(5, 0); } catch (const RotaError&) { threw = true; }
            if (!threw) return 10;
            threw = false;
            try { nights_until(0, 28); } catch (const RotaError&) { threw = true; }
            if (!threw) return 11;
            threw = false;
            try { nights_until(-1, 3); } catch (const RotaError&) { threw = true; }
            if (!threw) return 12;
            if (nights_until(1, 0) != 6) return 13;
            if (nights_until(3, 25) != 21) return 14;
            if (nights_until(0, 26) != 2) return 15;
            if (nights_until(4, 20) != 4) return 16;
            if (nights_until(2, 14) != 0) return 17;
            if (nights_until(4, 27) != 0) return 18;
            threw = false;
            try { schedule(-1, 5); } catch (const RotaError&) { threw = true; }
            if (!threw) return 19;
            threw = false;
            try { schedule(0, -1); } catch (const RotaError&) { threw = true; }
            if (!threw) return 20;
            if (schedule(4, 28) != std::vector<int>({24, 25, 26, 27})) return 21;
            if (schedule(1, 13) != std::vector<int>({6, 7, 8, 9, 10, 11})) return 22;
            if (schedule(0, 34) != std::vector<int>({0, 1, 2, 3, 4, 5, 28, 29, 30, 31, 32, 33})) return 23;
            if (!schedule(2, 0).empty()) return 24;
            return 0;
            """,
            "stateless banded cycle mapping over a 28-night rota of 5 keepers in night/6 blocks with a final short band",
            "std::chrono or <ctime> types, std::fmod, plain night % keepers assignment, or lookup tables that skip the band computation",
            "exact band boundaries, forward nights_until across the rota end, schedule content over repeated rotas, rejection channels",
            "banded rota cycle rejecting the plain-mod substitute",
            "free-function modular calculator with exceptions",
        ),
        c(
            "f26clk-courier-loop-manifest",
            "Courier loop manifest",
            "courier_loop",
            """
            class ManifestError : public std::invalid_argument {
            public:
                explicit ManifestError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kStops = 36;
            int stop_after(int stop, int parcels);
            int hops_between(int from, int to);
            std::vector<int> manifest(int start, int parcels, int per_stop);
            """,
            """
            class ManifestError : public std::invalid_argument {
            public:
                explicit ManifestError(const std::string& message) : std::invalid_argument(message) {}
            };
            constexpr int kStops = 36;
            int stop_after(int stop, int parcels);
            int hops_between(int from, int to);
            std::vector<int> manifest(int start, int parcels, int per_stop);
            """,
            """
            namespace {
            int normalize_stop(int stop) {
                int wrapped = stop % kStops;
                if (wrapped < 0) wrapped += kStops;
                return wrapped;
            }
            void require_stop(int stop) {
                if (stop < 0 || stop >= kStops) throw ManifestError("stop out of range");
            }
            }
            int stop_after(int stop, int parcels) {
                require_stop(stop);
                return normalize_stop(stop + parcels);
            }
            int hops_between(int from, int to) {
                require_stop(from);
                require_stop(to);
                int forward = to - from;
                if (forward < 0) forward += kStops;
                return forward;
            }
            std::vector<int> manifest(int start, int parcels, int per_stop) {
                require_stop(start);
                if (parcels < 0) throw ManifestError("parcels must be nonnegative");
                if (per_stop < 1) throw ManifestError("per stop capacity must be positive");
                int needed = (parcels + per_stop - 1) / per_stop;
                std::vector<int> stops;
                stops.reserve(static_cast<std::size_t>(needed));
                for (int i = 0; i < needed; ++i) stops.push_back(normalize_stop(start + i));
                return stops;
            }
            """,
            """
            namespace {
            int normalize_stop(int stop) {
                int wrapped = stop % kStops;
                if (wrapped < 0) wrapped += kStops;
                return wrapped;
            }
            void require_stop(int stop) {
                if (stop < 0 || stop >= kStops) throw ManifestError("stop out of range");
            }
            }
            int stop_after(int stop, int parcels) {
                require_stop(stop);
                return normalize_stop(stop + parcels);
            }
            int hops_between(int from, int to) {
                require_stop(from);
                require_stop(to);
                int forward = to - from;
                if (forward < 0) forward += kStops;
                return forward;
            }
            std::vector<int> manifest(int start, int parcels, int per_stop) {
                require_stop(start);
                if (parcels < 0) throw ManifestError("parcels must be nonnegative");
                if (per_stop < 1) throw ManifestError("per stop capacity must be positive");
                int needed = parcels / per_stop;
                std::vector<int> stops;
                stops.reserve(static_cast<std::size_t>(needed));
                for (int i = 0; i < needed; ++i) stops.push_back(normalize_stop(start + i));
                return stops;
            }
            """,
            """
            if (stop_after(33, 5) != 2) return 1;
            if (stop_after(10, -14) != 32) return 2;
            if (stop_after(20, 90) != 2) return 3;
            if (hops_between(30, 4) != 10) return 4;
            if (hops_between(7, 7) != 0) return 5;
            if (manifest(5, 20, 5) != std::vector<int>({5, 6, 7, 8})) return 6;
            if (!manifest(9, 0, 3).empty()) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { stop_after(36, 1); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { stop_after(-1, 2); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 2;
            if (stop_after(20, 90) != 2) return 3;
            if (stop_after(3, -75) != 0) return 4;
            if (stop_after(35, 1) != 0) return 5;
            threw = false;
            try { hops_between(0, 36); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 6;
            threw = false;
            try { hops_between(-3, 0); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 7;
            if (hops_between(35, 1) != 2) return 8;
            if (hops_between(12, 12) != 0) return 9;
            threw = false;
            try { manifest(36, 5, 1); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 10;
            threw = false;
            try { manifest(0, -1, 2); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 11;
            threw = false;
            try { manifest(0, 5, 0); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 12;
            threw = false;
            try { manifest(0, 5, -2); } catch (const ManifestError&) { threw = true; }
            if (!threw) return 13;
            if (manifest(30, 25, 10) != std::vector<int>({30, 31, 32})) return 14;
            if (manifest(34, 7, 3) != std::vector<int>({34, 35, 0})) return 15;
            if (manifest(2, 1, 9) != std::vector<int>({2})) return 16;
            if (manifest(0, 72, 4) != std::vector<int>({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17})) return 17;
            if (manifest(8, 12, 6) != std::vector<int>({8, 9})) return 18;
            return 0;
            """,
            "stateless cycle math over 36 stops plus capacity-bounded manifest generation that keeps the final partial stop",
            "std::chrono or <ctime> types, std::fmod, truncated remainder arithmetic on negative values, or dropping the final partial stop",
            "multi-loop manifests, exact visited-stop content, capacity edge at exact multiples, rejection channels",
            "capacity-bounded manifest cycle with partial-stop edge",
            "free-function modular calculator with exceptions",
        ),

        c(
            "f26clk-airfield-runway-carousel",
            "Airfield runway carousel",
            "airfield_runway",
            """
            class CarouselError : public std::logic_error {
            public:
                explicit CarouselError(const std::string& message) : std::logic_error(message) {}
            };
            class RunwayCarousel {
            public:
                explicit RunwayCarousel(int strips);
                int assign(const std::string& flight);
                bool release(const std::string& flight);
                void rotate(int strips);
                int active() const;
                int cycles() const;
                std::vector<std::string> trace() const;
            };
            """,
            """
            class CarouselError : public std::logic_error {
            public:
                explicit CarouselError(const std::string& message) : std::logic_error(message) {}
            };
            class RunwayCarousel {
            public:
                explicit RunwayCarousel(int strips);
                int assign(const std::string& flight);
                bool release(const std::string& flight);
                void rotate(int strips);
                int active() const;
                int cycles() const;
                std::vector<std::string> trace() const;
            private:
                int strips_;
                int active_;
                int cycles_;
                std::vector<std::string> assigned_;
                std::vector<std::string> trace_;
            };
            """,
            """
            RunwayCarousel::RunwayCarousel(int strips)
                : strips_(strips),
                  active_(0),
                  cycles_(0),
                  assigned_(strips > 0 ? static_cast<std::size_t>(strips) : 0U) {
                if (strips < 1 || strips > 12) throw CarouselError("carousel needs 1..12 strips");
            }
            int RunwayCarousel::assign(const std::string& flight) {
                for (const std::string& held : assigned_) {
                    if (held == flight) throw CarouselError("flight already assigned");
                }
                if (!assigned_[static_cast<std::size_t>(active_)].empty()) {
                    throw CarouselError("active strip occupied");
                }
                assigned_[static_cast<std::size_t>(active_)] = flight;
                trace_.push_back("assign:" + flight + "@s" + std::to_string(active_));
                return active_;
            }
            bool RunwayCarousel::release(const std::string& flight) {
                for (std::size_t i = 0; i < assigned_.size(); ++i) {
                    if (assigned_[i] == flight) {
                        assigned_[i].clear();
                        trace_.push_back("release:" + flight + "@s" + std::to_string(i));
                        return true;
                    }
                }
                return false;
            }
            void RunwayCarousel::rotate(int strips) {
                int raw = active_ + strips;
                int crossings = raw / strips_;
                if (raw % strips_ != 0 && raw < 0) crossings -= 1;
                active_ = raw % strips_;
                if (active_ < 0) active_ += strips_;
                for (int i = 0; i < crossings; ++i) {
                    cycles_ += 1;
                    trace_.push_back("rot+" + std::to_string(cycles_) + "@s" + std::to_string(active_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    cycles_ -= 1;
                    trace_.push_back("rot-" + std::to_string(cycles_) + "@s" + std::to_string(active_));
                }
            }
            int RunwayCarousel::active() const { return active_; }
            int RunwayCarousel::cycles() const { return cycles_; }
            std::vector<std::string> RunwayCarousel::trace() const { return trace_; }
            """,
            """
            RunwayCarousel::RunwayCarousel(int strips)
                : strips_(strips),
                  active_(0),
                  cycles_(0),
                  assigned_(strips > 0 ? static_cast<std::size_t>(strips) : 0U) {
                if (strips < 1 || strips > 12) throw CarouselError("carousel needs 1..12 strips");
            }
            int RunwayCarousel::assign(const std::string& flight) {
                for (const std::string& held : assigned_) {
                    if (held == flight) throw CarouselError("flight already assigned");
                }
                if (!assigned_[static_cast<std::size_t>(active_)].empty()) {
                    throw CarouselError("active strip occupied");
                }
                assigned_[static_cast<std::size_t>(active_)] = flight;
                trace_.push_back("assign:" + flight + "@s" + std::to_string(active_));
                return active_;
            }
            bool RunwayCarousel::release(const std::string& flight) {
                for (std::size_t i = 0; i < assigned_.size(); ++i) {
                    if (assigned_[i] == flight) {
                        assigned_[i].clear();
                        trace_.push_back("release:" + flight + "@s" + std::to_string(i));
                        return true;
                    }
                }
                return false;
            }
            void RunwayCarousel::rotate(int strips) {
                int raw = active_ + strips;
                int crossings = raw / strips_;
                active_ = raw % strips_;
                cycles_ += crossings;
                for (int i = 0; i < crossings; ++i) {
                    trace_.push_back("rot+" + std::to_string(cycles_ - crossings + i + 1) + "@s" + std::to_string(active_));
                }
            }
            int RunwayCarousel::active() const { return active_; }
            int RunwayCarousel::cycles() const { return cycles_; }
            std::vector<std::string> RunwayCarousel::trace() const { return trace_; }
            """,
            """
            RunwayCarousel car(4);
            if (car.assign("ABL101") != 0) return 1;
            car.rotate(1);
            if (car.assign("CDM202") != 1) return 2;
            if (car.active() != 1) return 3;
            if (!car.release("ABL101")) return 4;
            if (car.release("ABL101")) return 5;
            car.rotate(3);
            if (car.active() != 0) return 6;
            std::vector<std::string> log = car.trace();
            if (log.size() != 4U) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { RunwayCarousel bad(0); (void)bad; } catch (const CarouselError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { RunwayCarousel bad(13); (void)bad; } catch (const CarouselError&) { threw = true; }
            if (!threw) return 2;
            RunwayCarousel car(3);
            if (car.assign("F001") != 0) return 3;
            threw = false;
            try { car.assign("F001"); } catch (const CarouselError&) { threw = true; }
            if (!threw) return 4;
            car.rotate(2);
            if (car.assign("F002") != 2) return 5;
            threw = false;
            try { car.assign("F003"); } catch (const CarouselError&) { threw = true; }
            if (!threw) return 6;
            if (car.cycles() != 0) return 7;
            car.rotate(4);
            if (car.active() != 0) return 8;
            if (car.cycles() != 2) return 9;
            std::vector<std::string> log = car.trace();
            if (log.size() != 4U) return 10;
            if (log[2] != "rot+1@s0" || log[3] != "rot+2@s0") return 11;
            car.rotate(-1);
            if (car.active() != 2) return 12;
            if (car.cycles() != 1) return 13;
            log = car.trace();
            if (log.size() != 5U) return 14;
            if (log[4] != "rot-1@s2") return 15;
            if (!car.release("F001")) return 16;
            if (car.release("ZZZ")) return 17;
            return 0;
            """,
            "rotating active-strip window with floor-mod rotation, a cycle-crossing journal, and assign/release channels",
            "sequential-container stores that hide the window pointer, std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "rotation wrap counting in both directions, duplicate and absent channels, exact trace text and order, and mutation-free rejections",
            "rotating schedule window with an exact transition journal in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-bakery-hearth-rotation",
            "Bakery hearth rotation",
            "bakery_hearth",
            """
            class HearthError : public std::logic_error {
            public:
                explicit HearthError(const std::string& message) : std::logic_error(message) {}
            };
            class HearthRotation {
            public:
                explicit HearthRotation(int decks);
                int load(const std::string& loaf);
                bool draw(const std::string& loaf);
                void rotate();
                int front() const;
                int turns() const;
                std::vector<std::string> turn_log() const;
            };
            """,
            """
            class HearthError : public std::logic_error {
            public:
                explicit HearthError(const std::string& message) : std::logic_error(message) {}
            };
            class HearthRotation {
            public:
                explicit HearthRotation(int decks);
                int load(const std::string& loaf);
                bool draw(const std::string& loaf);
                void rotate();
                int front() const;
                int turns() const;
                std::vector<std::string> turn_log() const;
            private:
                int decks_;
                int front_;
                int turns_;
                std::vector<std::string> loaves_;
                std::vector<std::string> log_;
            };
            """,
            """
            HearthRotation::HearthRotation(int decks)
                : decks_(decks),
                  front_(0),
                  turns_(0),
                  loaves_(decks > 0 ? static_cast<std::size_t>(decks) : 0U) {
                if (decks < 1 || decks > 10) throw HearthError("hearth needs 1..10 decks");
            }
            int HearthRotation::load(const std::string& loaf) {
                for (const std::string& held : loaves_) {
                    if (held == loaf) throw HearthError("loaf already loaded");
                }
                if (!loaves_[static_cast<std::size_t>(front_)].empty()) {
                    throw HearthError("front deck occupied");
                }
                loaves_[static_cast<std::size_t>(front_)] = loaf;
                log_.push_back("load:" + loaf + "@d" + std::to_string(front_));
                return front_;
            }
            bool HearthRotation::draw(const std::string& loaf) {
                std::string& held = loaves_[static_cast<std::size_t>(front_)];
                if (held.empty() || held != loaf) return false;
                held.clear();
                log_.push_back("draw:" + loaf + "@d" + std::to_string(front_));
                return true;
            }
            void HearthRotation::rotate() {
                front_ += 1;
                if (front_ == decks_) {
                    front_ = 0;
                    turns_ += 1;
                    log_.push_back("turn" + std::to_string(turns_) + "->d" + std::to_string(front_));
                }
            }
            int HearthRotation::front() const { return front_; }
            int HearthRotation::turns() const { return turns_; }
            std::vector<std::string> HearthRotation::turn_log() const { return log_; }
            """,
            """
            HearthRotation::HearthRotation(int decks)
                : decks_(decks),
                  front_(0),
                  turns_(0),
                  loaves_(decks > 0 ? static_cast<std::size_t>(decks) : 0U) {
                if (decks < 1 || decks > 10) throw HearthError("hearth needs 1..10 decks");
            }
            int HearthRotation::load(const std::string& loaf) {
                for (const std::string& held : loaves_) {
                    if (held == loaf) throw HearthError("loaf already loaded");
                }
                if (!loaves_[static_cast<std::size_t>(front_)].empty()) {
                    throw HearthError("front deck occupied");
                }
                loaves_[static_cast<std::size_t>(front_)] = loaf;
                log_.push_back("load:" + loaf + "@d" + std::to_string(front_));
                return front_;
            }
            bool HearthRotation::draw(const std::string& loaf) {
                std::string& held = loaves_[static_cast<std::size_t>(front_)];
                if (held.empty() || held != loaf) return false;
                held.clear();
                log_.push_back("draw:" + loaf + "@d" + std::to_string(front_));
                return true;
            }
            void HearthRotation::rotate() {
                front_ += 1;
                if (front_ == decks_) front_ = 0;
            }
            int HearthRotation::front() const { return front_; }
            int HearthRotation::turns() const { return turns_; }
            std::vector<std::string> HearthRotation::turn_log() const { return log_; }
            """,
            """
            HearthRotation hearth(4);
            if (hearth.load("rye") != 0) return 1;
            hearth.rotate();
            if (hearth.front() != 1) return 2;
            if (hearth.load("wheat") != 1) return 3;
            if (!hearth.draw("wheat")) return 4;
            if (hearth.draw("rye")) return 5;
            hearth.rotate();
            if (hearth.front() != 2) return 6;
            if (hearth.turns() != 0) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { HearthRotation bad(0); (void)bad; } catch (const HearthError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { HearthRotation bad(11); (void)bad; } catch (const HearthError&) { threw = true; }
            if (!threw) return 2;
            HearthRotation hearth(3);
            if (hearth.load("boule") != 0) return 3;
            threw = false;
            try { hearth.load("boule"); } catch (const HearthError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { hearth.load("soda"); } catch (const HearthError&) { threw = true; }
            if (!threw) return 5;
            hearth.rotate();
            if (hearth.load("soda") != 1) return 6;
            hearth.rotate();
            hearth.rotate();
            if (hearth.front() != 0) return 7;
            if (hearth.turns() != 1) return 8;
            std::vector<std::string> log = hearth.turn_log();
            if (log.size() != 3U) return 9;
            if (log[2] != "turn1->d0") return 10;
            if (!hearth.draw("boule")) return 11;
            if (hearth.draw("soda")) return 12;
            hearth.rotate();
            hearth.rotate();
            hearth.rotate();
            if (hearth.turns() != 2) return 13;
            log = hearth.turn_log();
            if (log.size() != 5U) return 14;
            if (log[3] != "draw:boule@d0" || log[4] != "turn2->d0") return 15;
            return 0;
            """,
            "single-step rotating front-deck pointer with floor-mod wrap, per-turn accounting, and front-only load/draw channels",
            "sequential-container stores that hide the front pointer, std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "multi-turn rotations, load/draw at the front only, exact turn log text and order, and duplicate/occupied error channels",
            "single-step hearth pointer with turn accounting in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-ferry-tide-window",
            "Ferry tide window",
            "ferry_tide",
            """
            class TideError : public std::logic_error {
            public:
                explicit TideError(const std::string& message) : std::logic_error(message) {}
            };
            class TideWindow {
            public:
                explicit TideWindow(int windows);
                int depart(const std::string& vessel);
                bool arrive(const std::string& vessel);
                void advance(int windows);
                int open_window() const;
                int cycles() const;
                std::vector<std::string> sailing_log() const;
            };
            """,
            """
            class TideError : public std::logic_error {
            public:
                explicit TideError(const std::string& message) : std::logic_error(message) {}
            };
            class TideWindow {
            public:
                explicit TideWindow(int windows);
                int depart(const std::string& vessel);
                bool arrive(const std::string& vessel);
                void advance(int windows);
                int open_window() const;
                int cycles() const;
                std::vector<std::string> sailing_log() const;
            private:
                int windows_;
                int open_;
                int cycles_;
                std::vector<std::string> booked_;
                std::vector<std::string> log_;
            };
            """,
            """
            TideWindow::TideWindow(int windows)
                : windows_(windows),
                  open_(0),
                  cycles_(0),
                  booked_(windows > 0 ? static_cast<std::size_t>(windows) : 0U) {
                if (windows < 2 || windows > 12) throw TideError("tide needs 2..12 windows");
            }
            int TideWindow::depart(const std::string& vessel) {
                for (const std::string& held : booked_) {
                    if (held == vessel) throw TideError("vessel already booked");
                }
                if (!booked_[static_cast<std::size_t>(open_)].empty()) {
                    throw TideError("open window booked");
                }
                booked_[static_cast<std::size_t>(open_)] = vessel;
                log_.push_back("depart:" + vessel + "@w" + std::to_string(open_));
                return open_;
            }
            bool TideWindow::arrive(const std::string& vessel) {
                for (std::size_t i = 0; i < booked_.size(); ++i) {
                    if (booked_[i] == vessel) {
                        booked_[i].clear();
                        log_.push_back("arrive:" + vessel + "@w" + std::to_string(i));
                        return true;
                    }
                }
                return false;
            }
            void TideWindow::advance(int windows) {
                int raw = open_ + windows;
                int crossings = raw / windows_;
                if (raw % windows_ != 0 && raw < 0) crossings -= 1;
                open_ = raw % windows_;
                if (open_ < 0) open_ += windows_;
                for (int i = 0; i < crossings; ++i) {
                    cycles_ += 1;
                    log_.push_back("cycle+" + std::to_string(cycles_) + "@w" + std::to_string(open_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    cycles_ -= 1;
                    log_.push_back("cycle-" + std::to_string(cycles_) + "@w" + std::to_string(open_));
                }
            }
            int TideWindow::open_window() const { return open_; }
            int TideWindow::cycles() const { return cycles_; }
            std::vector<std::string> TideWindow::sailing_log() const { return log_; }
            """,
            """
            TideWindow::TideWindow(int windows)
                : windows_(windows),
                  open_(0),
                  cycles_(0),
                  booked_(windows > 0 ? static_cast<std::size_t>(windows) : 0U) {
                if (windows < 2 || windows > 12) throw TideError("tide needs 2..12 windows");
            }
            int TideWindow::depart(const std::string& vessel) {
                for (const std::string& held : booked_) {
                    if (held == vessel) throw TideError("vessel already booked");
                }
                if (!booked_[static_cast<std::size_t>(open_)].empty()) {
                    throw TideError("open window booked");
                }
                booked_[static_cast<std::size_t>(open_)] = vessel;
                log_.push_back("depart:" + vessel + "@w" + std::to_string(open_));
                return open_;
            }
            bool TideWindow::arrive(const std::string& vessel) {
                for (std::size_t i = 0; i < booked_.size(); ++i) {
                    if (booked_[i] == vessel) {
                        booked_[i].clear();
                        log_.push_back("arrive:" + vessel + "@w" + std::to_string(i));
                        return true;
                    }
                }
                return false;
            }
            void TideWindow::advance(int windows) {
                int raw = open_ + windows;
                if (raw < 0) raw = 0;
                int crossings = raw / windows_;
                open_ = raw % windows_;
                cycles_ += crossings;
                for (int i = 0; i < crossings; ++i) {
                    log_.push_back("cycle+" + std::to_string(cycles_ - crossings + i + 1) + "@w" + std::to_string(open_));
                }
            }
            int TideWindow::open_window() const { return open_; }
            int TideWindow::cycles() const { return cycles_; }
            std::vector<std::string> TideWindow::sailing_log() const { return log_; }
            """,
            """
            TideWindow tide(4);
            if (tide.depart("MV-Auk") != 0) return 1;
            tide.advance(1);
            if (tide.open_window() != 1) return 2;
            if (tide.depart("SS-Brant") != 1) return 3;
            if (!tide.arrive("MV-Auk")) return 4;
            if (tide.arrive("MV-Auk")) return 5;
            tide.advance(2);
            if (tide.open_window() != 3) return 6;
            std::vector<std::string> log = tide.sailing_log();
            if (log.size() != 3U) return 7;
            if (tide.cycles() != 0) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { TideWindow bad(1); (void)bad; } catch (const TideError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { TideWindow bad(13); (void)bad; } catch (const TideError&) { threw = true; }
            if (!threw) return 2;
            TideWindow tide(3);
            if (tide.depart("FV-Cormorant") != 0) return 3;
            threw = false;
            try { tide.depart("FV-Cormorant"); } catch (const TideError&) { threw = true; }
            if (!threw) return 4;
            tide.advance(2);
            if (tide.depart("MS-Petrel") != 2) return 5;
            threw = false;
            try { tide.depart("FV-Gannet"); } catch (const TideError&) { threw = true; }
            if (!threw) return 6;
            if (tide.cycles() != 0) return 7;
            tide.advance(4);
            if (tide.open_window() != 0) return 8;
            if (tide.cycles() != 2) return 9;
            std::vector<std::string> log = tide.sailing_log();
            if (log.size() != 4U) return 10;
            if (log[2] != "cycle+1@w0" || log[3] != "cycle+2@w0") return 11;
            tide.advance(-1);
            if (tide.open_window() != 2) return 12;
            if (tide.cycles() != 1) return 13;
            log = tide.sailing_log();
            if (log.size() != 5U) return 14;
            if (log[4] != "cycle-1@w2") return 15;
            if (!tide.arrive("FV-Cormorant")) return 16;
            if (tide.arrive("ZZ-None")) return 17;
            return 0;
            """,
            "rotating booking window with floor-mod advance in both directions, a cycle-crossing ledger, and depart/arrive channels",
            "sequential-container stores that hide the booking window pointer, std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative advance borrow across the window origin, duplicate and absent channels, cycle counts, and exact sailing log text and order",
            "booking-window cycle with an exact crossing ledger in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-marshalling-yard-lead",
            "Marshalling yard lead",
            "marshalling_yard",
            """
            class YardError : public std::logic_error {
            public:
                explicit YardError(const std::string& message) : std::logic_error(message) {}
            };
            class YardLead {
            public:
                explicit YardLead(int leads);
                int shove(const std::string& cut);
                bool pull(const std::string& cut);
                void advance(int leads);
                int lead() const;
                int rounds() const;
                std::vector<std::string> lead_log() const;
            };
            """,
            """
            class YardError : public std::logic_error {
            public:
                explicit YardError(const std::string& message) : std::logic_error(message) {}
            };
            class YardLead {
            public:
                explicit YardLead(int leads);
                int shove(const std::string& cut);
                bool pull(const std::string& cut);
                void advance(int leads);
                int lead() const;
                int rounds() const;
                std::vector<std::string> lead_log() const;
            private:
                int leads_;
                int lead_;
                int rounds_;
                std::vector<std::string> parked_;
                std::vector<std::string> log_;
            };
            """,
            """
            YardLead::YardLead(int leads)
                : leads_(leads),
                  lead_(0),
                  rounds_(0),
                  parked_(leads > 0 ? static_cast<std::size_t>(leads) : 0U) {
                if (leads < 1 || leads > 8) throw YardError("yard needs 1..8 leads");
            }
            int YardLead::shove(const std::string& cut) {
                for (const std::string& held : parked_) {
                    if (held == cut) throw YardError("cut already parked");
                }
                if (!parked_[static_cast<std::size_t>(lead_)].empty()) {
                    throw YardError("lead occupied");
                }
                parked_[static_cast<std::size_t>(lead_)] = cut;
                log_.push_back("shove:" + cut + "@l" + std::to_string(lead_));
                return lead_;
            }
            bool YardLead::pull(const std::string& cut) {
                for (std::size_t i = 0; i < parked_.size(); ++i) {
                    if (parked_[i] == cut) {
                        parked_[i].clear();
                        log_.push_back("pull:" + cut + "@l" + std::to_string(i));
                        return true;
                    }
                }
                return false;
            }
            void YardLead::advance(int leads) {
                int raw = lead_ + leads;
                int crossings = raw / leads_;
                if (raw % leads_ != 0 && raw < 0) crossings -= 1;
                lead_ = raw % leads_;
                if (lead_ < 0) lead_ += leads_;
                for (int i = 0; i < crossings; ++i) {
                    rounds_ += 1;
                    log_.push_back("round+" + std::to_string(rounds_) + "@l" + std::to_string(lead_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    rounds_ -= 1;
                    log_.push_back("round-" + std::to_string(rounds_) + "@l" + std::to_string(lead_));
                }
            }
            int YardLead::lead() const { return lead_; }
            int YardLead::rounds() const { return rounds_; }
            std::vector<std::string> YardLead::lead_log() const { return log_; }
            """,
            """
            YardLead::YardLead(int leads)
                : leads_(leads),
                  lead_(0),
                  rounds_(0),
                  parked_(leads > 0 ? static_cast<std::size_t>(leads) : 0U) {
                if (leads < 1 || leads > 8) throw YardError("yard needs 1..8 leads");
            }
            int YardLead::shove(const std::string& cut) {
                for (const std::string& held : parked_) {
                    if (held == cut) throw YardError("cut already parked");
                }
                if (!parked_[static_cast<std::size_t>(lead_)].empty()) {
                    throw YardError("lead occupied");
                }
                parked_[static_cast<std::size_t>(lead_)] = cut;
                log_.push_back("shove:" + cut + "@l" + std::to_string(lead_));
                return lead_;
            }
            bool YardLead::pull(const std::string& cut) {
                for (std::size_t i = 0; i < parked_.size(); ++i) {
                    if (parked_[i] == cut) {
                        parked_[i].clear();
                        log_.push_back("pull:" + cut + "@l" + std::to_string(i));
                        return true;
                    }
                }
                return false;
            }
            void YardLead::advance(int leads) {
                lead_ += leads;
                int crossings = lead_ / leads_;
                if (lead_ % leads_ != 0 && lead_ < 0) crossings -= 1;
                rounds_ += crossings;
                for (int i = 0; i < crossings; ++i) {
                    log_.push_back("round+" + std::to_string(rounds_ - crossings + i + 1) + "@l" + std::to_string(lead_));
                }
            }
            int YardLead::lead() const { return lead_; }
            int YardLead::rounds() const { return rounds_; }
            std::vector<std::string> YardLead::lead_log() const { return log_; }
            """,
            """
            YardLead yard(4);
            if (yard.shove("BOX410") != 0) return 1;
            yard.advance(1);
            if (yard.lead() != 1) return 2;
            if (yard.shove("TANK7") != 1) return 3;
            if (!yard.pull("BOX410")) return 4;
            if (yard.pull("BOX410")) return 5;
            yard.advance(2);
            if (yard.lead() != 3) return 6;
            if (yard.rounds() != 0) return 7;
            std::vector<std::string> log = yard.lead_log();
            if (log.size() != 3U) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { YardLead bad(0); (void)bad; } catch (const YardError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { YardLead bad(9); (void)bad; } catch (const YardError&) { threw = true; }
            if (!threw) return 2;
            YardLead yard(3);
            if (yard.shove("BOX410") != 0) return 3;
            threw = false;
            try { yard.shove("BOX410"); } catch (const YardError&) { threw = true; }
            if (!threw) return 4;
            yard.advance(2);
            if (yard.lead() != 2) return 5;
            if (yard.shove("TANK7") != 2) return 6;
            threw = false;
            try { yard.shove("FLAT3"); } catch (const YardError&) { threw = true; }
            if (!threw) return 7;
            if (yard.rounds() != 0) return 8;
            yard.advance(4);
            if (yard.lead() != 0) return 9;
            if (yard.rounds() != 2) return 10;
            std::vector<std::string> log = yard.lead_log();
            if (log.size() != 4U) return 11;
            if (log[2] != "round+1@l0" || log[3] != "round+2@l0") return 12;
            yard.advance(-1);
            if (yard.lead() != 2) return 13;
            if (yard.rounds() != 1) return 14;
            log = yard.lead_log();
            if (log.size() != 5U) return 15;
            if (log[4] != "round-1@l2") return 16;
            if (!yard.pull("BOX410")) return 17;
            if (yard.pull("HOPPER9")) return 18;
            return 0;
            """,
            "rotating lead pointer with floor-mod advance in both directions, a round ledger, and shove/pull channels",
            "sequential-container stores that hide the lead pointer, std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "negative advance borrow, duplicate and absent channels, round counts, exact lead log text and order, and lead pointer range proof",
            "yard-lead rotation with range-safe pointer proof in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-print-press-cylinder",
            "Print press cylinder",
            "print_press",
            """
            class PressError : public std::logic_error {
            public:
                explicit PressError(const std::string& message) : std::logic_error(message) {}
            };
            class PressCylinder {
            public:
                PressCylinder(int cylinders, int impressions);
                int print(int copies);
                int blanket() const;
                int revolutions() const;
                std::vector<std::string> impression_log() const;
            };
            """,
            """
            class PressError : public std::logic_error {
            public:
                explicit PressError(const std::string& message) : std::logic_error(message) {}
            };
            class PressCylinder {
            public:
                PressCylinder(int cylinders, int impressions);
                int print(int copies);
                int blanket() const;
                int revolutions() const;
                std::vector<std::string> impression_log() const;
            private:
                int cylinders_;
                int impressions_;
                int blanket_;
                int left_;
                int revolutions_;
                std::vector<std::string> log_;
            };
            """,
            """
            PressCylinder::PressCylinder(int cylinders, int impressions)
                : cylinders_(cylinders),
                  impressions_(impressions),
                  blanket_(0),
                  left_(impressions),
                  revolutions_(0) {
                if (cylinders < 1 || cylinders > 6) throw PressError("press needs 1..6 cylinders");
                if (impressions < 1 || impressions > 90) throw PressError("press needs 1..90 impressions");
            }
            int PressCylinder::print(int copies) {
                if (copies <= 0) throw PressError("copies must be positive");
                for (int i = 0; i < copies; ++i) {
                    left_ -= 1;
                    if (left_ == 0) {
                        blanket_ += 1;
                        if (blanket_ == cylinders_) {
                            blanket_ = 0;
                            revolutions_ += 1;
                            log_.push_back("rev" + std::to_string(revolutions_) + "@c" + std::to_string(blanket_));
                        }
                        left_ = impressions_;
                    }
                }
                return blanket_;
            }
            int PressCylinder::blanket() const { return blanket_; }
            int PressCylinder::revolutions() const { return revolutions_; }
            std::vector<std::string> PressCylinder::impression_log() const { return log_; }
            """,
            """
            PressCylinder::PressCylinder(int cylinders, int impressions)
                : cylinders_(cylinders),
                  impressions_(impressions),
                  blanket_(0),
                  left_(impressions),
                  revolutions_(0) {
                if (cylinders < 1 || cylinders > 6) throw PressError("press needs 1..6 cylinders");
                if (impressions < 1 || impressions > 90) throw PressError("press needs 1..90 impressions");
            }
            int PressCylinder::print(int copies) {
                if (copies <= 0) throw PressError("copies must be positive");
                for (int i = 0; i < copies; ++i) {
                    left_ -= 1;
                    if (left_ == 0) left_ = impressions_;
                }
                return blanket_;
            }
            int PressCylinder::blanket() const { return blanket_; }
            int PressCylinder::revolutions() const { return revolutions_; }
            std::vector<std::string> PressCylinder::impression_log() const { return log_; }
            """,
            """
            PressCylinder press(3, 10);
            if (press.print(4) != 0) return 1;
            if (press.blanket() != 0) return 2;
            if (press.revolutions() != 0) return 3;
            if (press.print(5) != 0) return 4;
            if (press.blanket() != 0) return 5;
            std::vector<std::string> log = press.impression_log();
            if (!log.empty()) return 6;
            bool threw = false;
            try { press.print(0); } catch (const PressError&) { threw = true; }
            if (!threw) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { PressCylinder bad(0, 10); (void)bad; } catch (const PressError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PressCylinder bad(7, 10); (void)bad; } catch (const PressError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { PressCylinder bad(2, 0); (void)bad; } catch (const PressError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { PressCylinder bad(2, 91); (void)bad; } catch (const PressError&) { threw = true; }
            if (!threw) return 4;
            PressCylinder press(2, 5);
            if (press.print(7) != 1) return 5;
            if (press.blanket() != 1) return 6;
            if (press.revolutions() != 0) return 7;
            threw = false;
            try { press.print(-3); } catch (const PressError&) { threw = true; }
            if (!threw) return 8;
            if (press.blanket() != 1) return 9;
            std::vector<std::string> log = press.impression_log();
            if (!log.empty()) return 10;
            if (press.print(3) != 0) return 11;
            if (press.revolutions() != 1) return 12;
            log = press.impression_log();
            if (log.size() != 1U) return 13;
            if (log[0] != "rev1@c0") return 14;
            if (press.print(12) != 0) return 15;
            if (press.revolutions() != 2) return 16;
            log = press.impression_log();
            if (log.size() != 2U) return 17;
            if (log[1] != "rev2@c0") return 18;
            return 0;
            """,
            "two-level cylinder/impression consumption cycle with floor-mod rollover, a revolution ledger, and positive-copy validation",
            "std::chrono or <ctime> types, std::fmod, floating-point impression math, or truncated remainder arithmetic on negative values",
            "multi-revolution print runs, blanket rollover order, revolution counts, exact impression log text and order, and nonpositive copy rejection without mutation",
            "two-level consumption cycle distinct from pointer-only schedulers in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-rodeo-chute-gate",
            "Rodeo chute gate",
            "rodeo_chute",
            """
            class ChuteError : public std::logic_error {
            public:
                explicit ChuteError(const std::string& message) : std::logic_error(message) {}
            };
            class ChuteGate {
            public:
                explicit ChuteGate(int chutes);
                int load(const std::string& rider);
                bool open();
                void advance(int chutes);
                int gate() const;
                int rounds() const;
                std::vector<std::string> gate_log() const;
            };
            """,
            """
            class ChuteError : public std::logic_error {
            public:
                explicit ChuteError(const std::string& message) : std::logic_error(message) {}
            };
            class ChuteGate {
            public:
                explicit ChuteGate(int chutes);
                int load(const std::string& rider);
                bool open();
                void advance(int chutes);
                int gate() const;
                int rounds() const;
                std::vector<std::string> gate_log() const;
            private:
                int chutes_;
                int gate_;
                int rounds_;
                std::vector<std::string> penned_;
                std::vector<std::string> log_;
            };
            """,
            """
            ChuteGate::ChuteGate(int chutes)
                : chutes_(chutes),
                  gate_(0),
                  rounds_(0),
                  penned_(chutes > 0 ? static_cast<std::size_t>(chutes) : 0U) {
                if (chutes < 2 || chutes > 8) throw ChuteError("gate needs 2..8 chutes");
            }
            int ChuteGate::load(const std::string& rider) {
                for (const std::string& held : penned_) {
                    if (held == rider) throw ChuteError("rider already penned");
                }
                if (!penned_[static_cast<std::size_t>(gate_)].empty()) {
                    throw ChuteError("chute occupied");
                }
                penned_[static_cast<std::size_t>(gate_)] = rider;
                log_.push_back("load:" + rider + "@g" + std::to_string(gate_));
                return gate_;
            }
            bool ChuteGate::open() {
                std::string& held = penned_[static_cast<std::size_t>(gate_)];
                if (held.empty()) return false;
                log_.push_back("open:" + held + "@g" + std::to_string(gate_));
                held.clear();
                return true;
            }
            void ChuteGate::advance(int chutes) {
                int raw = gate_ + chutes;
                int crossings = raw / chutes_;
                if (raw % chutes_ != 0 && raw < 0) crossings -= 1;
                gate_ = raw % chutes_;
                if (gate_ < 0) gate_ += chutes_;
                for (int i = 0; i < crossings; ++i) {
                    rounds_ += 1;
                    log_.push_back("round+" + std::to_string(rounds_) + "@g" + std::to_string(gate_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    rounds_ -= 1;
                    log_.push_back("round-" + std::to_string(rounds_) + "@g" + std::to_string(gate_));
                }
            }
            int ChuteGate::gate() const { return gate_; }
            int ChuteGate::rounds() const { return rounds_; }
            std::vector<std::string> ChuteGate::gate_log() const { return log_; }
            """,
            """
            ChuteGate::ChuteGate(int chutes)
                : chutes_(chutes),
                  gate_(0),
                  rounds_(0),
                  penned_(chutes > 0 ? static_cast<std::size_t>(chutes) : 0U) {
                if (chutes < 2 || chutes > 8) throw ChuteError("gate needs 2..8 chutes");
            }
            int ChuteGate::load(const std::string& rider) {
                for (const std::string& held : penned_) {
                    if (held == rider) throw ChuteError("rider already penned");
                }
                if (!penned_[static_cast<std::size_t>(gate_)].empty()) {
                    throw ChuteError("chute occupied");
                }
                penned_[static_cast<std::size_t>(gate_)] = rider;
                log_.push_back("load:" + rider + "@g" + std::to_string(gate_));
                return gate_;
            }
            bool ChuteGate::open() {
                std::string& held = penned_[0];
                if (held.empty()) return false;
                log_.push_back("open:" + held + "@g0");
                held.clear();
                return true;
            }
            void ChuteGate::advance(int chutes) {
                int raw = gate_ + chutes;
                int crossings = raw / chutes_;
                if (raw % chutes_ != 0 && raw < 0) crossings -= 1;
                gate_ = raw % chutes_;
                if (gate_ < 0) gate_ += chutes_;
                for (int i = 0; i < crossings; ++i) {
                    rounds_ += 1;
                    log_.push_back("round+" + std::to_string(rounds_) + "@g" + std::to_string(gate_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    rounds_ -= 1;
                    log_.push_back("round-" + std::to_string(rounds_) + "@g" + std::to_string(gate_));
                }
            }
            int ChuteGate::gate() const { return gate_; }
            int ChuteGate::rounds() const { return rounds_; }
            std::vector<std::string> ChuteGate::gate_log() const { return log_; }
            """,
            """
            ChuteGate gate(4);
            if (gate.load("R7-Dusty") != 0) return 1;
            if (!gate.open()) return 2;
            if (gate.open()) return 3;
            gate.advance(2);
            if (gate.gate() != 2) return 4;
            if (gate.load("R9-Slate") != 2) return 5;
            if (gate.rounds() != 0) return 6;
            std::vector<std::string> log = gate.gate_log();
            if (log.size() != 3U) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { ChuteGate bad(1); (void)bad; } catch (const ChuteError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { ChuteGate bad(9); (void)bad; } catch (const ChuteError&) { threw = true; }
            if (!threw) return 2;
            ChuteGate gate(3);
            if (gate.load("R1-Bravo") != 0) return 3;
            threw = false;
            try { gate.load("R1-Bravo"); } catch (const ChuteError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { gate.load("R2-Cisco"); } catch (const ChuteError&) { threw = true; }
            if (!threw) return 5;
            gate.advance(1);
            if (gate.load("R2-Cisco") != 1) return 6;
            if (!gate.open()) return 7;
            std::vector<std::string> log = gate.gate_log();
            if (log.size() != 3U) return 8;
            if (log[2] != "open:R2-Cisco@g1") return 9;
            gate.advance(-1);
            if (gate.gate() != 0) return 10;
            if (!gate.open()) return 11;
            gate.advance(5);
            if (gate.gate() != 2) return 12;
            if (gate.rounds() != 1) return 13;
            log = gate.gate_log();
            if (log.size() != 5U) return 14;
            if (log[3] != "open:R1-Bravo@g0" || log[4] != "round+1@g2") return 15;
            if (gate.open()) return 16;
            return 0;
            """,
            "rotating gate pointer with per-chute occupancy, floor-mod advance in both directions, a round ledger, and load/open channels",
            "sequential-container stores that hide the gate pointer, std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "load/open pairing at the current gate, full and empty channels, negative advance borrow, round counts, and exact gate log text and order",
            "occupancy-aware gate rotation with exact channels in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-signal-gantry-aspect",
            "Signal gantry aspect",
            "signal_gantry",
            """
            class AspectError : public std::logic_error {
            public:
                explicit AspectError(const std::string& message) : std::logic_error(message) {}
            };
            class GantryAspect {
            public:
                explicit GantryAspect(int blocks);
                int clear(int blocks);
                std::string aspect() const;
                int block() const;
                int sweeps() const;
                std::vector<std::string> aspect_log() const;
            };
            """,
            """
            class AspectError : public std::logic_error {
            public:
                explicit AspectError(const std::string& message) : std::logic_error(message) {}
            };
            class GantryAspect {
            public:
                explicit GantryAspect(int blocks);
                int clear(int blocks);
                std::string aspect() const;
                int block() const;
                int sweeps() const;
                std::vector<std::string> aspect_log() const;
            private:
                static std::string band_name(int band);
                int band_of(int block) const;
                int blocks_;
                int head_;
                int sweeps_;
                std::vector<std::string> log_;
            };
            """,
            """
            std::string GantryAspect::band_name(int band) {
                if (band == 0) return "clear";
                if (band == 1) return "caution";
                return "stop";
            }
            int GantryAspect::band_of(int block) const {
                return (block * 3) / blocks_;
            }
            GantryAspect::GantryAspect(int blocks)
                : blocks_(blocks), head_(0), sweeps_(0) {
                if (blocks < 2 || blocks > 40) throw AspectError("gantry needs 2..40 blocks");
            }
            int GantryAspect::clear(int blocks) {
                if (blocks <= 0) throw AspectError("clear count must be positive");
                int raw = head_ + blocks;
                int crossings = raw / blocks_;
                int previous = band_of(head_);
                for (int step = head_ + 1; step <= raw; ++step) {
                    int position = step % blocks_;
                    int band = band_of(position);
                    if (band != previous) {
                        log_.push_back(band_name(band) + "@b" + std::to_string(position));
                        previous = band;
                    }
                }
                head_ = raw % blocks_;
                sweeps_ += crossings;
                return crossings;
            }
            std::string GantryAspect::aspect() const { return band_name(band_of(head_)); }
            int GantryAspect::block() const { return head_; }
            int GantryAspect::sweeps() const { return sweeps_; }
            std::vector<std::string> GantryAspect::aspect_log() const { return log_; }
            """,
            """
            std::string GantryAspect::band_name(int band) {
                if (band == 0) return "clear";
                if (band == 1) return "caution";
                return "stop";
            }
            int GantryAspect::band_of(int block) const {
                return (block * 3) / blocks_;
            }
            GantryAspect::GantryAspect(int blocks)
                : blocks_(blocks), head_(0), sweeps_(0) {
                if (blocks < 2 || blocks > 40) throw AspectError("gantry needs 2..40 blocks");
            }
            int GantryAspect::clear(int blocks) {
                if (blocks <= 0) throw AspectError("clear count must be positive");
                int raw = head_ + blocks;
                int crossings = raw / blocks_;
                for (int step = head_ + 1; step <= raw; ++step) {
                    int position = step % blocks_;
                    log_.push_back(band_name(band_of(position)) + "@b" + std::to_string(position));
                }
                head_ = raw % blocks_;
                sweeps_ += crossings;
                return crossings;
            }
            std::string GantryAspect::aspect() const { return band_name(band_of(head_)); }
            int GantryAspect::block() const { return head_; }
            int GantryAspect::sweeps() const { return sweeps_; }
            std::vector<std::string> GantryAspect::aspect_log() const { return log_; }
            """,
            """
            GantryAspect gantry(6);
            if (gantry.aspect() != "clear") return 1;
            if (gantry.clear(2) != 0) return 2;
            if (gantry.block() != 2) return 3;
            if (gantry.aspect() != "caution") return 4;
            if (gantry.clear(6) != 1) return 5;
            if (gantry.block() != 2) return 6;
            if (gantry.aspect() != "caution") return 7;
            if (gantry.sweeps() != 1) return 8;
            bool threw = false;
            try { gantry.clear(0); } catch (const AspectError&) { threw = true; }
            if (!threw) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { GantryAspect bad(1); (void)bad; } catch (const AspectError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { GantryAspect bad(41); (void)bad; } catch (const AspectError&) { threw = true; }
            if (!threw) return 2;
            GantryAspect gantry(6);
            threw = false;
            try { gantry.clear(-2); } catch (const AspectError&) { threw = true; }
            if (!threw) return 3;
            if (gantry.block() != 0) return 4;
            if (!gantry.aspect_log().empty()) return 5;
            if (gantry.clear(1) != 0) return 6;
            std::vector<std::string> log = gantry.aspect_log();
            if (!log.empty()) return 7;
            if (gantry.clear(1) != 0) return 8;
            log = gantry.aspect_log();
            if (log.size() != 1U) return 9;
            if (log[0] != "caution@b2") return 10;
            if (gantry.clear(4) != 1) return 11;
            if (gantry.sweeps() != 1) return 12;
            if (gantry.block() != 0) return 13;
            if (gantry.aspect() != "clear") return 14;
            log = gantry.aspect_log();
            if (log.size() != 3U) return 15;
            if (log[1] != "stop@b4" || log[2] != "clear@b0") return 16;
            if (gantry.clear(12) != 2) return 17;
            if (gantry.sweeps() != 3) return 18;
            log = gantry.aspect_log();
            if (log.size() != 9U) return 19;
            if (log[8] != "clear@b0") return 20;
            return 0;
            """,
            "block pointer driving a derived three-state aspect cycle with floor-mod advance, transition-only logging, and sweep counting",
            "std::chrono or <ctime> types, std::fmod, logging without aspect transitions, or truncated remainder arithmetic on negative values",
            "exact aspect sequence over many blocks, transition-only log content, sweep counts, and nonpositive clear rejection without mutation",
            "derived-state aspect cycle with a transition-only journal in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-waterworks-pump-rota",
            "Waterworks pump rota",
            "waterworks_pump",
            """
            class PumpError : public std::logic_error {
            public:
                explicit PumpError(const std::string& message) : std::logic_error(message) {}
            };
            class PumpRota {
            public:
                explicit PumpRota(int pumps);
                int duty_at(int slot) const;
                void rotate(int slots);
                int slot() const;
                int cycles() const;
                std::vector<std::string> rota_log() const;
            };
            """,
            """
            class PumpError : public std::logic_error {
            public:
                explicit PumpError(const std::string& message) : std::logic_error(message) {}
            };
            class PumpRota {
            public:
                explicit PumpRota(int pumps);
                int duty_at(int slot) const;
                void rotate(int slots);
                int slot() const;
                int cycles() const;
                std::vector<std::string> rota_log() const;
            private:
                static constexpr int kBoardSlots = 24;
                int pumps_;
                int slot_;
                int cycles_;
                std::vector<std::string> log_;
            };
            """,
            """
            PumpRota::PumpRota(int pumps)
                : pumps_(pumps), slot_(0), cycles_(0) {
                if (pumps < 2 || pumps > 8) throw PumpError("rota needs 2..8 pumps");
            }
            int PumpRota::duty_at(int slot) const {
                if (slot < 0 || slot >= kBoardSlots) throw PumpError("slot off the board");
                return slot % pumps_;
            }
            void PumpRota::rotate(int slots) {
                int raw = slot_ + slots;
                int crossings = raw / kBoardSlots;
                if (raw % kBoardSlots != 0 && raw < 0) crossings -= 1;
                slot_ = raw % kBoardSlots;
                if (slot_ < 0) slot_ += kBoardSlots;
                for (int i = 0; i < crossings; ++i) {
                    cycles_ += 1;
                    log_.push_back("cycle+" + std::to_string(cycles_) + "@s" + std::to_string(slot_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    cycles_ -= 1;
                    log_.push_back("cycle-" + std::to_string(cycles_) + "@s" + std::to_string(slot_));
                }
            }
            int PumpRota::slot() const { return slot_; }
            int PumpRota::cycles() const { return cycles_; }
            std::vector<std::string> PumpRota::rota_log() const { return log_; }
            """,
            """
            PumpRota::PumpRota(int pumps)
                : pumps_(pumps), slot_(0), cycles_(0) {
                if (pumps < 2 || pumps > 8) throw PumpError("rota needs 2..8 pumps");
            }
            int PumpRota::duty_at(int slot) const {
                if (slot < 0 || slot >= kBoardSlots) throw PumpError("slot off the board");
                return slot / pumps_;
            }
            void PumpRota::rotate(int slots) {
                int raw = slot_ + slots;
                int crossings = raw / kBoardSlots;
                if (raw % kBoardSlots != 0 && raw < 0) crossings -= 1;
                slot_ = raw % kBoardSlots;
                if (slot_ < 0) slot_ += kBoardSlots;
                for (int i = 0; i < crossings; ++i) {
                    cycles_ += 1;
                    log_.push_back("cycle+" + std::to_string(cycles_) + "@s" + std::to_string(slot_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    cycles_ -= 1;
                    log_.push_back("cycle-" + std::to_string(cycles_) + "@s" + std::to_string(slot_));
                }
            }
            int PumpRota::slot() const { return slot_; }
            int PumpRota::cycles() const { return cycles_; }
            std::vector<std::string> PumpRota::rota_log() const { return log_; }
            """,
            """
            PumpRota rota(3);
            if (rota.duty_at(0) != 0) return 1;
            rota.rotate(5);
            if (rota.slot() != 5) return 2;
            if (rota.cycles() != 0) return 3;
            bool threw = false;
            try { rota.duty_at(24); } catch (const PumpError&) { threw = true; }
            if (!threw) return 4;
            threw = false;
            try { rota.duty_at(-1); } catch (const PumpError&) { threw = true; }
            if (!threw) return 5;
            std::vector<std::string> log = rota.rota_log();
            if (!log.empty()) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { PumpRota bad(1); (void)bad; } catch (const PumpError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { PumpRota bad(9); (void)bad; } catch (const PumpError&) { threw = true; }
            if (!threw) return 2;
            PumpRota rota(4);
            if (rota.duty_at(0) != 0) return 3;
            if (rota.duty_at(1) != 1) return 4;
            if (rota.duty_at(3) != 3) return 5;
            if (rota.duty_at(4) != 0) return 6;
            if (rota.duty_at(7) != 3) return 7;
            if (rota.duty_at(23) != 3) return 8;
            rota.rotate(30);
            if (rota.slot() != 6) return 9;
            if (rota.cycles() != 1) return 10;
            std::vector<std::string> log = rota.rota_log();
            if (log.size() != 1U) return 11;
            if (log[0] != "cycle+1@s6") return 12;
            rota.rotate(30);
            if (rota.slot() != 12) return 13;
            if (rota.cycles() != 2) return 14;
            rota.rotate(-20);
            if (rota.slot() != 16) return 15;
            if (rota.cycles() != 1) return 16;
            log = rota.rota_log();
            if (log.size() != 3U) return 17;
            if (log[1] != "cycle+2@s12" || log[2] != "cycle-1@s16") return 18;
            return 0;
            """,
            "board-slot pointer with round-robin banded duty mapping, floor-mod rotation in both directions, and a cycle ledger",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "band boundaries over the 24-slot board, negative rotate borrow, cycle counts, exact rota log text and order, and duty_at range rejection",
            "round-robin duty board with a band-mapping discriminator in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-wind-farm-yaw-cycle",
            "Wind farm yaw cycle",
            "wind_farm_yaw",
            """
            class YawError : public std::logic_error {
            public:
                explicit YawError(const std::string& message) : std::logic_error(message) {}
            };
            class YawCycle {
            public:
                explicit YawCycle(int heading);
                void yaw(int degrees);
                int heading() const;
                int full_turns() const;
                std::vector<std::string> gust_log() const;
            };
            """,
            """
            class YawError : public std::logic_error {
            public:
                explicit YawError(const std::string& message) : std::logic_error(message) {}
            };
            class YawCycle {
            public:
                explicit YawCycle(int heading);
                void yaw(int degrees);
                int heading() const;
                int full_turns() const;
                std::vector<std::string> gust_log() const;
            private:
                static constexpr int kDegreesPerTurn = 360;
                static constexpr int kMaxCommand = 720;
                int heading_;
                int full_turns_;
                std::vector<std::string> log_;
            };
            """,
            """
            YawCycle::YawCycle(int heading)
                : heading_(0), full_turns_(0) {
                int wrapped = heading % kDegreesPerTurn;
                if (wrapped < 0) wrapped += kDegreesPerTurn;
                heading_ = wrapped;
            }
            void YawCycle::yaw(int degrees) {
                if (degrees > kMaxCommand || degrees < -kMaxCommand) {
                    throw YawError("yaw command over 720 degrees");
                }
                int raw = heading_ + degrees;
                int crossings = raw / kDegreesPerTurn;
                if (raw % kDegreesPerTurn != 0 && raw < 0) crossings -= 1;
                heading_ = raw % kDegreesPerTurn;
                if (heading_ < 0) heading_ += kDegreesPerTurn;
                for (int i = 0; i < crossings; ++i) {
                    full_turns_ += 1;
                    log_.push_back("turn+" + std::to_string(full_turns_) + "@h" + std::to_string(heading_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    full_turns_ -= 1;
                    log_.push_back("turn-" + std::to_string(full_turns_) + "@h" + std::to_string(heading_));
                }
            }
            int YawCycle::heading() const { return heading_; }
            int YawCycle::full_turns() const { return full_turns_; }
            std::vector<std::string> YawCycle::gust_log() const { return log_; }
            """,
            """
            YawCycle::YawCycle(int heading)
                : heading_(0), full_turns_(0) {
                int wrapped = heading % kDegreesPerTurn;
                if (wrapped < 0) wrapped += kDegreesPerTurn;
                heading_ = wrapped;
            }
            void YawCycle::yaw(int degrees) {
                int raw = heading_ + degrees;
                int crossings = raw / kDegreesPerTurn;
                if (raw % kDegreesPerTurn != 0 && raw < 0) crossings -= 1;
                heading_ = raw % kDegreesPerTurn;
                if (heading_ < 0) heading_ += kDegreesPerTurn;
                for (int i = 0; i < crossings; ++i) {
                    full_turns_ += 1;
                    log_.push_back("turn+" + std::to_string(full_turns_) + "@h" + std::to_string(heading_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    full_turns_ -= 1;
                    log_.push_back("turn-" + std::to_string(full_turns_) + "@h" + std::to_string(heading_));
                }
                if (degrees > kMaxCommand || degrees < -kMaxCommand) {
                    throw YawError("yaw command over 720 degrees");
                }
            }
            int YawCycle::heading() const { return heading_; }
            int YawCycle::full_turns() const { return full_turns_; }
            std::vector<std::string> YawCycle::gust_log() const { return log_; }
            """,
            """
            YawCycle cycle(90);
            if (cycle.heading() != 90) return 1;
            cycle.yaw(100);
            if (cycle.heading() != 190) return 2;
            if (cycle.full_turns() != 0) return 3;
            cycle.yaw(-40);
            if (cycle.heading() != 150) return 4;
            if (cycle.full_turns() != 0) return 5;
            bool threw = false;
            try { cycle.yaw(721); } catch (const YawError&) { threw = true; }
            if (!threw) return 6;
            return 0;
            """,
            """
            YawCycle cycle(-30);
            if (cycle.heading() != 330) return 1;
            if (cycle.full_turns() != 0) return 2;
            cycle.yaw(45);
            if (cycle.heading() != 15) return 3;
            if (cycle.full_turns() != 1) return 4;
            std::vector<std::string> log = cycle.gust_log();
            if (log.size() != 1U) return 5;
            if (log[0] != "turn+1@h15") return 6;
            cycle.yaw(720);
            if (cycle.heading() != 15) return 7;
            if (cycle.full_turns() != 3) return 8;
            log = cycle.gust_log();
            if (log.size() != 3U) return 9;
            if (log[1] != "turn+2@h15" || log[2] != "turn+3@h15") return 10;
            cycle.yaw(-45);
            if (cycle.heading() != 330) return 11;
            if (cycle.full_turns() != 2) return 12;
            log = cycle.gust_log();
            if (log.size() != 4U) return 13;
            if (log[3] != "turn-2@h330") return 14;
            bool threw = false;
            try { cycle.yaw(721); } catch (const YawError&) { threw = true; }
            if (!threw) return 15;
            if (cycle.heading() != 330) return 16;
            if (cycle.full_turns() != 2) return 17;
            if (cycle.gust_log().size() != 4U) return 18;
            threw = false;
            try { cycle.yaw(-721); } catch (const YawError&) { threw = true; }
            if (!threw) return 19;
            if (cycle.heading() != 330) return 20;
            return 0;
            """,
            "heading cycle with magnitude-limited signed yaw commands, floor-mod normalization, and a full-turn crossing ledger",
            "std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "over-limit command rejection without mutation, multi-turn commands inside the limit, turn counts, and exact gust log text and order",
            "command-limited heading cycle with mutation-free rejection proof in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),
        c(
            "f26clk-tollbridge-lane-cycle",
            "Tollbridge lane cycle",
            "tollbridge_lane",
            """
            class LaneError : public std::logic_error {
            public:
                explicit LaneError(const std::string& message) : std::logic_error(message) {}
            };
            class LaneCycle {
            public:
                LaneCycle(int lanes, int vehicles);
                int admit(const std::string& plate);
                std::optional<std::string> release();
                void advance(int lanes);
                int booth() const;
                int sweeps() const;
                std::vector<std::string> lane_log() const;
            };
            """,
            """
            class LaneError : public std::logic_error {
            public:
                explicit LaneError(const std::string& message) : std::logic_error(message) {}
            };
            class LaneCycle {
            public:
                LaneCycle(int lanes, int vehicles);
                int admit(const std::string& plate);
                std::optional<std::string> release();
                void advance(int lanes);
                int booth() const;
                int sweeps() const;
                std::vector<std::string> lane_log() const;
            private:
                int lanes_;
                int vehicles_;
                int booth_;
                int sweeps_;
                std::vector<std::deque<std::string>> queues_;
                std::vector<std::string> log_;
            };
            """,
            """
            LaneCycle::LaneCycle(int lanes, int vehicles)
                : lanes_(lanes),
                  vehicles_(vehicles),
                  booth_(0),
                  sweeps_(0),
                  queues_(lanes > 0 ? static_cast<std::size_t>(lanes) : 0U) {
                if (lanes < 2 || lanes > 6) throw LaneError("bridge needs 2..6 lanes");
                if (vehicles < 1 || vehicles > 30) throw LaneError("bridge needs 1..30 vehicles");
            }
            int LaneCycle::admit(const std::string& plate) {
                std::deque<std::string>& lane = queues_[static_cast<std::size_t>(booth_)];
                if (static_cast<int>(lane.size()) >= vehicles_) throw LaneError("lane full");
                lane.push_back(plate);
                log_.push_back("admit:" + plate + "@l" + std::to_string(booth_));
                return booth_;
            }
            std::optional<std::string> LaneCycle::release() {
                std::deque<std::string>& lane = queues_[static_cast<std::size_t>(booth_)];
                if (lane.empty()) return std::nullopt;
                std::string plate = lane.front();
                lane.pop_front();
                log_.push_back("release:" + plate + "@l" + std::to_string(booth_));
                return plate;
            }
            void LaneCycle::advance(int lanes) {
                int raw = booth_ + lanes;
                int crossings = raw / lanes_;
                if (raw % lanes_ != 0 && raw < 0) crossings -= 1;
                booth_ = raw % lanes_;
                if (booth_ < 0) booth_ += lanes_;
                for (int i = 0; i < crossings; ++i) {
                    sweeps_ += 1;
                    log_.push_back("sweep+" + std::to_string(sweeps_) + "@l" + std::to_string(booth_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    sweeps_ -= 1;
                    log_.push_back("sweep-" + std::to_string(sweeps_) + "@l" + std::to_string(booth_));
                }
            }
            int LaneCycle::booth() const { return booth_; }
            int LaneCycle::sweeps() const { return sweeps_; }
            std::vector<std::string> LaneCycle::lane_log() const { return log_; }
            """,
            """
            LaneCycle::LaneCycle(int lanes, int vehicles)
                : lanes_(lanes),
                  vehicles_(vehicles),
                  booth_(0),
                  sweeps_(0),
                  queues_(lanes > 0 ? static_cast<std::size_t>(lanes) : 0U) {
                if (lanes < 2 || lanes > 6) throw LaneError("bridge needs 2..6 lanes");
                if (vehicles < 1 || vehicles > 30) throw LaneError("bridge needs 1..30 vehicles");
            }
            int LaneCycle::admit(const std::string& plate) {
                std::deque<std::string>& lane = queues_[static_cast<std::size_t>(booth_)];
                if (static_cast<int>(lane.size()) >= vehicles_) throw LaneError("lane full");
                lane.push_back(plate);
                log_.push_back("admit:" + plate + "@l" + std::to_string(booth_));
                return booth_;
            }
            std::optional<std::string> LaneCycle::release() {
                std::deque<std::string>& lane = queues_[0];
                if (lane.empty()) return std::nullopt;
                std::string plate = lane.front();
                lane.pop_front();
                log_.push_back("release:" + plate + "@l0");
                return plate;
            }
            void LaneCycle::advance(int lanes) {
                int raw = booth_ + lanes;
                int crossings = raw / lanes_;
                if (raw % lanes_ != 0 && raw < 0) crossings -= 1;
                booth_ = raw % lanes_;
                if (booth_ < 0) booth_ += lanes_;
                for (int i = 0; i < crossings; ++i) {
                    sweeps_ += 1;
                    log_.push_back("sweep+" + std::to_string(sweeps_) + "@l" + std::to_string(booth_));
                }
                for (int i = 0; i < -crossings; ++i) {
                    sweeps_ -= 1;
                    log_.push_back("sweep-" + std::to_string(sweeps_) + "@l" + std::to_string(booth_));
                }
            }
            int LaneCycle::booth() const { return booth_; }
            int LaneCycle::sweeps() const { return sweeps_; }
            std::vector<std::string> LaneCycle::lane_log() const { return log_; }
            """,
            """
            LaneCycle toll(3, 2);
            if (toll.admit("ABC-123") != 0) return 1;
            std::optional<std::string> out = toll.release();
            if (!out.has_value() || *out != "ABC-123") return 2;
            out = toll.release();
            if (out.has_value()) return 3;
            toll.advance(1);
            if (toll.booth() != 1) return 4;
            if (toll.sweeps() != 0) return 5;
            std::vector<std::string> log = toll.lane_log();
            if (log.size() != 2U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { LaneCycle bad(1, 5); (void)bad; } catch (const LaneError&) { threw = true; }
            if (!threw) return 1;
            threw = false;
            try { LaneCycle bad(7, 5); (void)bad; } catch (const LaneError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { LaneCycle bad(2, 0); (void)bad; } catch (const LaneError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { LaneCycle bad(2, 31); (void)bad; } catch (const LaneError&) { threw = true; }
            if (!threw) return 4;
            LaneCycle toll(3, 2);
            if (toll.admit("P-001") != 0) return 5;
            if (toll.admit("P-002") != 0) return 6;
            threw = false;
            try { toll.admit("P-003"); } catch (const LaneError&) { threw = true; }
            if (!threw) return 7;
            toll.advance(1);
            if (toll.admit("P-101") != 1) return 8;
            std::optional<std::string> out = toll.release();
            if (!out.has_value()) return 9;
            if (*out != "P-101") return 10;
            out = toll.release();
            if (out.has_value()) return 11;
            toll.advance(4);
            if (toll.booth() != 2) return 12;
            if (toll.sweeps() != 1) return 13;
            std::vector<std::string> log = toll.lane_log();
            if (log.size() != 5U) return 14;
            if (log[3] != "release:P-101@l1" || log[4] != "sweep+1@l2") return 15;
            toll.advance(-2);
            if (toll.booth() != 0) return 16;
            out = toll.release();
            if (!out.has_value() || *out != "P-001") return 17;
            out = toll.release();
            if (!out.has_value() || *out != "P-002") return 18;
            return 0;
            """,
            "rotating booth pointer over fixed lane queues with per-lane capacity, floor-mod advance in both directions, and a sweep ledger",
            "sequential-container stores that hide the booth pointer, std::chrono or <ctime> types, std::fmod, or truncated remainder arithmetic on negative values",
            "per-lane capacity rejection, dry-lane empty release, negative advance borrow, sweep counts, and exact lane log text and order",
            "capacity-bounded booth cycle with optional-draining release in a project-context root",
            "project-context cyclic scheduler with transition trace",
            project_support=True,
        ),

    )
    return rows


CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-clk-seven-dimension-artifacts-v1"
TASKS = cases()


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


def _visible_test(spec: TaskSpec) -> str:
    return f'''#include "{spec.task_id}.h"

using namespace {spec.namespace};

int main() {{
{spec.visible_test}}}
'''


def _hidden_test(spec: TaskSpec) -> str:
    return f'''#include "{spec.task_id}.h"

using namespace {spec.namespace};

int main() {{
{spec.private_test}}}
'''


def _introduction(spec: TaskSpec) -> str:
    return f"""# {spec.title}

Implement a clean-room C++17 modular-cycle component for a local clock
analog. This root is independently authored for SFT task-family construction
and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep floor-mod normalization, carry/borrow or wrap-event accounting,
boundary transitions, readout and journal shapes, and error channels
deterministic and explicit for this API shape: {spec.api_shape}.

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
                "source": "w8-biayn clean-room fixed26 clock analog curriculum",
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
description = "{spec.title}: normalization, negative offsets, wrap events, boundary transitions, readout shapes, and wrong-substitute rejection"

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


def _materialize_control(out: Path, spec: TaskSpec, name: str) -> dict[str, object]:
    root = out / ".state/controls" / name
    if root.exists():
        shutil.rmtree(root)
    for relative, content in sorted(_render(spec, variant=name).items()):
        _write(root / relative, content, overwrite=True)
    return {"name": name, "source_task_id": spec.task_id, "changed": True}


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
            "family": "clock",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "clock",
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
    text = re.sub(r"\bf26clk[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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


def _dimension_corpora(root: Path, spec: TaskSpec) -> dict[str, str]:
    header = _read(root, f"{spec.task_id}.h")
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
        control_profile = _dimension_corpora(out / ".state/controls" / name, TASKS[0])
        control_shingles = {dimension: _shingles(_semantic_tokens(corpus)) for dimension, corpus in control_profile.items()}
        dimension_results: dict[str, object] = {}
        for dimension in HARD_DIMENSIONS:
            score = compare(shingle_profiles[TASKS[0].task_id][dimension], control_shingles[dimension])
            rejected = score >= DIMENSION_LIMITS[dimension]
            dimension_results[dimension] = {"similarity": score, "limit": DIMENSION_LIMITS[dimension], "rejected_as_duplicate": rejected}
            if not rejected:
                _fail("adversarial_control_escaped", f"{name}:{dimension}:{score:.6f}")
        controls.append({"name": name, "dimensions": dimension_results, "rejected_in_all_dimensions": True})
    payload = {
        "schema_version": "fixed26-clk-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-clk-fresh-") as temporary:
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
        "schema_version": "fixed26-clk-core-v1",
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
for task_root in sorted(ROOT.glob("f26clk-*")):
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
            "schema_version": "fixed26-clk-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-clk-docker-") as temporary:
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
        "schema_version": "fixed26-clk-docker-sanity-v1",
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
        "schema_version": "fixed26-clk-creator-preflight-v1",
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
        "capability": "fixed26-clock-analog",
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
            "task": "implement clean-room fixed26 clock analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "owned integer cyclic state normalized by floor-mod in both directions; carry/borrow between coupled fields; observable wrap events; representation-blind equality; exact deterministic readouts and journals; rejected operations never mutate",
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
            "target_family": "clock",
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
