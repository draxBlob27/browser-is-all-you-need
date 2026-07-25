"""Create and verify the fixed-26 circular-buffer clean-room analog batch.

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b005-circular-buffer.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b005-circular-buffer"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_circular_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_circular_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b005-circular-buffer"
FAMILY_ID = "aider-fixed26-circular-buffer-analogs-v1"
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
        "f26cbuf-waterwheel-bucket-ring",
        "f26cbuf-canal-lock-chambers",
        "f26cbuf-gondola-cabin-wheel",
        "f26cbuf-roundabout-exit-slots",
        "f26cbuf-player-piano-roll",
        "f26cbuf-engraving-lathe-grooves",
        "f26cbuf-dashcam-clip-vault",
        "f26cbuf-drone-mission-buffer",
        "f26cbuf-bucket-brigade-line",
        "f26cbuf-kiln-shelf-rotation",
        "f26cbuf-heliograph-flash-ring",
        "f26cbuf-telescope-dome-slits",
        "f26cbuf-belltower-chime-wheel",
        "f26cbuf-orrery-planet-tracks",
        "f26cbuf-pendulum-swing-arcs",
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
            "f26cbuf-seismograph-drum",
            "Seismograph drum",
            "seismograph",
            """
            class DrumConfigError : public std::invalid_argument {
            public:
                explicit DrumConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DrumEmptyError : public std::runtime_error {
            public:
                explicit DrumEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DrumFullError : public std::logic_error {
            public:
                explicit DrumFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TraceAbsentError : public std::out_of_range {
            public:
                explicit TraceAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class SeismographDrum {
            public:
                explicit SeismographDrum(std::size_t capacity);
                void capture(std::int32_t amplitude);
                std::int32_t collect();
                bool recorded(std::int32_t amplitude) const;
                std::size_t traces() const;
                std::size_t capacity() const;
                std::size_t drum_slot(std::int32_t amplitude) const;
                std::size_t oldest_slot() const;
                std::size_t free_cells() const;
            };
            """,
            """
            class DrumConfigError : public std::invalid_argument {
            public:
                explicit DrumConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DrumEmptyError : public std::runtime_error {
            public:
                explicit DrumEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DrumFullError : public std::logic_error {
            public:
                explicit DrumFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TraceAbsentError : public std::out_of_range {
            public:
                explicit TraceAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class SeismographDrum {
            public:
                explicit SeismographDrum(std::size_t capacity);
                void capture(std::int32_t amplitude);
                std::int32_t collect();
                bool recorded(std::int32_t amplitude) const;
                std::size_t traces() const;
                std::size_t capacity() const;
                std::size_t drum_slot(std::int32_t amplitude) const;
                std::size_t oldest_slot() const;
                std::size_t free_cells() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t amplitude = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            SeismographDrum::SeismographDrum(std::size_t capacity) {
                if (capacity == 0) throw DrumConfigError("drum needs at least one cell");
                cells_ = std::vector<Cell>(capacity);
            }
            std::size_t SeismographDrum::capacity() const { return cells_.size(); }
            std::size_t SeismographDrum::traces() const { return used_; }
            std::size_t SeismographDrum::free_cells() const { return cells_.size() - used_; }
            bool SeismographDrum::recorded(std::int32_t amplitude) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.amplitude == amplitude) return true;
                }
                return false;
            }
            void SeismographDrum::capture(std::int32_t amplitude) {
                if (used_ == cells_.size()) throw DrumFullError("drum is full");
                cells_[next_].occupied = true;
                cells_[next_].amplitude = amplitude;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t SeismographDrum::collect() {
                if (used_ == 0) throw DrumEmptyError("drum is empty");
                std::int32_t value = cells_[oldest_].amplitude;
                cells_[oldest_].occupied = false;
                cells_[oldest_].amplitude = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t SeismographDrum::oldest_slot() const {
                if (used_ == 0) throw DrumEmptyError("drum is empty");
                return oldest_;
            }
            std::size_t SeismographDrum::drum_slot(std::int32_t amplitude) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].amplitude == amplitude) return slot;
                }
                throw TraceAbsentError("amplitude is not recorded");
            }
            """,
            """
            SeismographDrum::SeismographDrum(std::size_t capacity) {
                if (capacity == 0) throw DrumConfigError("drum needs at least one cell");
                cells_ = std::vector<Cell>(capacity);
            }
            std::size_t SeismographDrum::capacity() const { return cells_.size(); }
            std::size_t SeismographDrum::traces() const { return used_; }
            std::size_t SeismographDrum::free_cells() const { return cells_.size() - used_; }
            bool SeismographDrum::recorded(std::int32_t amplitude) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].amplitude == amplitude) return true;
                }
                return false;
            }
            void SeismographDrum::capture(std::int32_t amplitude) {
                if (used_ == cells_.size()) throw DrumFullError("drum is full");
                cells_[used_].occupied = true;
                cells_[used_].amplitude = amplitude;
                ++used_;
            }
            std::int32_t SeismographDrum::collect() {
                if (used_ == 0) throw DrumEmptyError("drum is empty");
                std::int32_t value = cells_[0].amplitude;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].amplitude = 0;
                --used_;
                return value;
            }
            std::size_t SeismographDrum::oldest_slot() const {
                if (used_ == 0) throw DrumEmptyError("drum is empty");
                return 0;
            }
            std::size_t SeismographDrum::drum_slot(std::int32_t amplitude) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].amplitude == amplitude) return i;
                }
                throw TraceAbsentError("amplitude is not recorded");
            }
            """,
            """
            SeismographDrum drum(3);
            drum.capture(7);
            drum.capture(19);
            drum.capture(42);
            if (!drum.recorded(19) || !drum.recorded(7)) return 1;
            if (drum.traces() != 3U) return 2;
            if (drum.collect() != 7) return 3;
            if (drum.collect() != 19) return 4;
            drum.capture(58);
            drum.capture(61);
            if (drum.collect() != 42) return 5;
            if (drum.collect() != 58) return 6;
            if (drum.collect() != 61) return 7;
            if (drum.traces() != 0U) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { SeismographDrum zero(0); (void)zero; } catch (const DrumConfigError&) { threw = true; }
            if (!threw) return 1;
            SeismographDrum drum(3);
            threw = false;
            try { drum.collect(); } catch (const DrumEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { drum.oldest_slot(); } catch (const DrumEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { drum.drum_slot(11); } catch (const TraceAbsentError&) { threw = true; }
            if (!threw) return 4;
            drum.capture(11);
            drum.capture(22);
            drum.capture(33);
            if (drum.oldest_slot() != 0U) return 5;
            threw = false;
            try { drum.capture(44); } catch (const DrumFullError&) { threw = true; }
            if (!threw) return 6;
            if (drum.traces() != 3U) return 7;
            if (drum.collect() != 11) return 8;
            if (drum.collect() != 22) return 9;
            drum.capture(44);
            drum.capture(55);
            if (drum.oldest_slot() != 2U) return 10;
            if (drum.drum_slot(44) != 0U) return 11;
            if (drum.drum_slot(55) != 1U) return 12;
            if (drum.drum_slot(33) != 2U) return 13;
            if (drum.free_cells() != 0U) return 14;
            if (drum.collect() != 33) return 15;
            if (drum.collect() != 44) return 16;
            if (drum.oldest_slot() != 1U) return 17;
            if (drum.collect() != 55) return 18;
            if (drum.traces() != 0U) return 19;
            threw = false;
            try { drum.drum_slot(33); } catch (const TraceAbsentError&) { threw = true; }
            if (!threw) return 20;
            return 0;
            """,
            "a fixed drum of trace cells whose physical capture slots and oldest-cell cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical drum_slot and oldest_slot values after capture/collect sequences that wrap the drum twice, full and empty channels, absent-trace lookup, and zero-capacity rejection",
            "slot-position observables after wraparound in a two-file API",
            "exception-throwing bounded ring with slot-position queries",
        ),
        c(
            "f26cbuf-foghorn-blast-cycle",
            "Foghorn blast cycle",
            "foghorn",
            """
            class HornConfigError : public std::invalid_argument {
            public:
                explicit HornConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HornEmptyError : public std::runtime_error {
            public:
                explicit HornEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class HornFullError : public std::logic_error {
            public:
                explicit HornFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BlastAbsentError : public std::out_of_range {
            public:
                explicit BlastAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class FoghornBlastCycle {
            public:
                explicit FoghornBlastCycle(std::size_t cycle_length);
                void sound(std::int32_t code);
                std::int32_t hush();
                bool waiting(std::int32_t code) const;
                std::size_t pending() const;
                std::size_t cycle_length() const;
                std::size_t cycle_slot(std::int32_t code) const;
                std::size_t next_blast_slot() const;
            };
            """,
            """
            class HornConfigError : public std::invalid_argument {
            public:
                explicit HornConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HornEmptyError : public std::runtime_error {
            public:
                explicit HornEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class HornFullError : public std::logic_error {
            public:
                explicit HornFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BlastAbsentError : public std::out_of_range {
            public:
                explicit BlastAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class FoghornBlastCycle {
            public:
                explicit FoghornBlastCycle(std::size_t cycle_length);
                void sound(std::int32_t code);
                std::int32_t hush();
                bool waiting(std::int32_t code) const;
                std::size_t pending() const;
                std::size_t cycle_length() const;
                std::size_t cycle_slot(std::int32_t code) const;
                std::size_t next_blast_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t code = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            FoghornBlastCycle::FoghornBlastCycle(std::size_t cycle_length) {
                if (cycle_length == 0) throw HornConfigError("cycle needs at least one cell");
                cells_ = std::vector<Cell>(cycle_length);
            }
            std::size_t FoghornBlastCycle::cycle_length() const { return cells_.size(); }
            std::size_t FoghornBlastCycle::pending() const { return used_; }
            bool FoghornBlastCycle::waiting(std::int32_t code) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.code == code) return true;
                }
                return false;
            }
            void FoghornBlastCycle::sound(std::int32_t code) {
                if (used_ == cells_.size()) throw HornFullError("cycle is full");
                cells_[next_].occupied = true;
                cells_[next_].code = code;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t FoghornBlastCycle::hush() {
                if (used_ == 0) throw HornEmptyError("cycle is empty");
                std::int32_t value = cells_[oldest_].code;
                cells_[oldest_].occupied = false;
                cells_[oldest_].code = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t FoghornBlastCycle::next_blast_slot() const {
                if (used_ == 0) throw HornEmptyError("cycle is empty");
                return oldest_;
            }
            std::size_t FoghornBlastCycle::cycle_slot(std::int32_t code) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].code == code) return slot;
                }
                throw BlastAbsentError("blast code is not waiting");
            }
            """,
            """
            FoghornBlastCycle::FoghornBlastCycle(std::size_t cycle_length) {
                if (cycle_length == 0) throw HornConfigError("cycle needs at least one cell");
                cells_ = std::vector<Cell>(cycle_length);
            }
            std::size_t FoghornBlastCycle::cycle_length() const { return cells_.size(); }
            std::size_t FoghornBlastCycle::pending() const { return used_; }
            bool FoghornBlastCycle::waiting(std::int32_t code) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].code == code) return true;
                }
                return false;
            }
            void FoghornBlastCycle::sound(std::int32_t code) {
                if (used_ == cells_.size()) throw HornFullError("cycle is full");
                cells_[used_].occupied = true;
                cells_[used_].code = code;
                ++used_;
            }
            std::int32_t FoghornBlastCycle::hush() {
                if (used_ == 0) throw HornEmptyError("cycle is empty");
                std::int32_t value = cells_[0].code;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].code = 0;
                --used_;
                return value;
            }
            std::size_t FoghornBlastCycle::next_blast_slot() const {
                if (used_ == 0) throw HornEmptyError("cycle is empty");
                return 0;
            }
            std::size_t FoghornBlastCycle::cycle_slot(std::int32_t code) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].code == code) return i;
                }
                throw BlastAbsentError("blast code is not waiting");
            }
            """,
            """
            FoghornBlastCycle horn(4);
            horn.sound(2);
            horn.sound(4);
            horn.sound(6);
            if (!horn.waiting(4) || !horn.waiting(6)) return 1;
            if (horn.pending() != 3U) return 2;
            if (horn.hush() != 2) return 3;
            horn.sound(8);
            horn.sound(10);
            if (horn.hush() != 4) return 4;
            if (horn.hush() != 6) return 5;
            if (horn.hush() != 8) return 6;
            if (horn.hush() != 10) return 7;
            if (horn.pending() != 0U) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { FoghornBlastCycle zero(0); (void)zero; } catch (const HornConfigError&) { threw = true; }
            if (!threw) return 1;
            FoghornBlastCycle horn(4);
            threw = false;
            try { horn.hush(); } catch (const HornEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { horn.next_blast_slot(); } catch (const HornEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { horn.cycle_slot(10); } catch (const BlastAbsentError&) { threw = true; }
            if (!threw) return 4;
            horn.sound(10);
            horn.sound(20);
            horn.sound(30);
            horn.sound(40);
            if (horn.next_blast_slot() != 0U) return 5;
            threw = false;
            try { horn.sound(50); } catch (const HornFullError&) { threw = true; }
            if (!threw) return 6;
            if (horn.pending() != 4U) return 7;
            if (horn.hush() != 10) return 8;
            if (horn.hush() != 20) return 9;
            horn.sound(50);
            horn.sound(60);
            if (horn.next_blast_slot() != 2U) return 10;
            if (horn.cycle_slot(50) != 0U) return 11;
            if (horn.cycle_slot(60) != 1U) return 12;
            if (horn.cycle_slot(30) != 2U) return 13;
            if (horn.cycle_slot(40) != 3U) return 14;
            if (horn.hush() != 30) return 15;
            if (horn.hush() != 40) return 16;
            if (horn.next_blast_slot() != 0U) return 17;
            if (horn.hush() != 50) return 18;
            if (horn.hush() != 60) return 19;
            threw = false;
            try { horn.cycle_slot(30); } catch (const BlastAbsentError&) { threw = true; }
            if (!threw) return 20;
            return 0;
            """,
            "a fixed cycle of blast cells whose physical slots and next-blast cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical cycle_slot and next_blast_slot values after sound/hush sequences that wrap the cycle, full and empty channels, absent-blast lookup, and zero-length rejection",
            "wraparound cursor arithmetic with a distinct error taxonomy",
            "exception-throwing bounded ring with slot-position queries",
        ),
        c(
            "f26cbuf-waterwheel-bucket-ring",
            "Waterwheel bucket ring",
            "waterwheel",
            """
            class WheelConfigError : public std::invalid_argument {
            public:
                explicit WheelConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WheelEmptyError : public std::runtime_error {
            public:
                explicit WheelEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class WheelFullError : public std::logic_error {
            public:
                explicit WheelFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BucketAbsentError : public std::out_of_range {
            public:
                explicit BucketAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class WaterwheelBucketRing {
            public:
                explicit WaterwheelBucketRing(std::size_t buckets_max);
                void pour(std::int64_t litres);
                std::int64_t lift();
                bool holding(std::int64_t litres) const;
                std::size_t buckets() const;
                std::size_t buckets_max() const;
                std::size_t bucket_slot(std::int64_t litres) const;
                std::size_t lift_slot() const;
            };
            """,
            """
            class WheelConfigError : public std::invalid_argument {
            public:
                explicit WheelConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WheelEmptyError : public std::runtime_error {
            public:
                explicit WheelEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class WheelFullError : public std::logic_error {
            public:
                explicit WheelFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BucketAbsentError : public std::out_of_range {
            public:
                explicit BucketAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class WaterwheelBucketRing {
            public:
                explicit WaterwheelBucketRing(std::size_t buckets_max);
                void pour(std::int64_t litres);
                std::int64_t lift();
                bool holding(std::int64_t litres) const;
                std::size_t buckets() const;
                std::size_t buckets_max() const;
                std::size_t bucket_slot(std::int64_t litres) const;
                std::size_t lift_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t litres = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            WaterwheelBucketRing::WaterwheelBucketRing(std::size_t buckets_max) {
                if (buckets_max == 0) throw WheelConfigError("wheel needs at least one bucket");
                cells_ = std::vector<Cell>(buckets_max);
            }
            std::size_t WaterwheelBucketRing::buckets_max() const { return cells_.size(); }
            std::size_t WaterwheelBucketRing::buckets() const { return used_; }
            bool WaterwheelBucketRing::holding(std::int64_t litres) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.litres == litres) return true;
                }
                return false;
            }
            void WaterwheelBucketRing::pour(std::int64_t litres) {
                if (used_ == cells_.size()) throw WheelFullError("wheel is full");
                cells_[next_].occupied = true;
                cells_[next_].litres = litres;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t WaterwheelBucketRing::lift() {
                if (used_ == 0) throw WheelEmptyError("wheel is empty");
                std::int64_t value = cells_[oldest_].litres;
                cells_[oldest_].occupied = false;
                cells_[oldest_].litres = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t WaterwheelBucketRing::lift_slot() const {
                if (used_ == 0) throw WheelEmptyError("wheel is empty");
                return oldest_;
            }
            std::size_t WaterwheelBucketRing::bucket_slot(std::int64_t litres) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].litres == litres) return slot;
                }
                throw BucketAbsentError("litre load is not held");
            }
            """,
            """
            WaterwheelBucketRing::WaterwheelBucketRing(std::size_t buckets_max) {
                if (buckets_max == 0) throw WheelConfigError("wheel needs at least one bucket");
                cells_ = std::vector<Cell>(buckets_max);
            }
            std::size_t WaterwheelBucketRing::buckets_max() const { return cells_.size(); }
            std::size_t WaterwheelBucketRing::buckets() const { return used_; }
            bool WaterwheelBucketRing::holding(std::int64_t litres) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].litres == litres) return true;
                }
                return false;
            }
            void WaterwheelBucketRing::pour(std::int64_t litres) {
                if (used_ == cells_.size()) throw WheelFullError("wheel is full");
                cells_[used_].occupied = true;
                cells_[used_].litres = litres;
                ++used_;
            }
            std::int64_t WaterwheelBucketRing::lift() {
                if (used_ == 0) throw WheelEmptyError("wheel is empty");
                std::int64_t value = cells_[0].litres;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].litres = 0;
                --used_;
                return value;
            }
            std::size_t WaterwheelBucketRing::lift_slot() const {
                if (used_ == 0) throw WheelEmptyError("wheel is empty");
                return 0;
            }
            std::size_t WaterwheelBucketRing::bucket_slot(std::int64_t litres) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].litres == litres) return i;
                }
                throw BucketAbsentError("litre load is not held");
            }
            """,
            """
            WaterwheelBucketRing wheel(3);
            wheel.pour(1500);
            wheel.pour(2750);
            if (!wheel.holding(1500) || !wheel.holding(2750)) return 1;
            if (wheel.buckets() != 2U) return 2;
            wheel.pour(3250);
            if (wheel.lift() != 1500) return 3;
            wheel.pour(4100);
            if (wheel.lift() != 2750) return 4;
            if (wheel.lift() != 3250) return 5;
            if (wheel.lift() != 4100) return 6;
            if (wheel.buckets() != 0U) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { WaterwheelBucketRing zero(0); (void)zero; } catch (const WheelConfigError&) { threw = true; }
            if (!threw) return 1;
            WaterwheelBucketRing wheel(3);
            threw = false;
            try { wheel.lift(); } catch (const WheelEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { wheel.lift_slot(); } catch (const WheelEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { wheel.bucket_slot(900); } catch (const BucketAbsentError&) { threw = true; }
            if (!threw) return 4;
            wheel.pour(1200);
            wheel.pour(2400);
            wheel.pour(3600);
            if (wheel.lift_slot() != 0U) return 5;
            threw = false;
            try { wheel.pour(4800); } catch (const WheelFullError&) { threw = true; }
            if (!threw) return 6;
            if (wheel.buckets() != 3U) return 7;
            if (wheel.lift() != 1200) return 8;
            if (wheel.lift() != 2400) return 9;
            wheel.pour(4800);
            wheel.pour(6000);
            if (wheel.lift_slot() != 2U) return 10;
            if (wheel.bucket_slot(4800) != 0U) return 11;
            if (wheel.bucket_slot(6000) != 1U) return 12;
            if (wheel.bucket_slot(3600) != 2U) return 13;
            if (wheel.lift() != 3600) return 14;
            if (wheel.lift() != 4800) return 15;
            if (wheel.lift_slot() != 1U) return 16;
            if (wheel.lift() != 6000) return 17;
            threw = false;
            try { wheel.bucket_slot(3600); } catch (const BucketAbsentError&) { threw = true; }
            if (!threw) return 18;
            return 0;
            """,
            "a fixed wheel of litre buckets whose physical bucket slots and lift cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical bucket_slot and lift_slot values after pour/lift sequences that wrap the wheel, full and empty channels, absent-bucket lookup, and zero-bucket rejection",
            "project-context ring with 64-bit payloads and wrap traces",
            "exception-throwing bounded ring with slot-position queries",
            project_support=True,
        ),
        c(
            "f26cbuf-carousel-brass-ring",
            "Carousel brass ring",
            "carousel",
            """
            class CarouselConfigError : public std::invalid_argument {
            public:
                explicit CarouselConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CarouselEmptyError : public std::runtime_error {
            public:
                explicit CarouselEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class CarouselFullError : public std::logic_error {
            public:
                explicit CarouselFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TokenAbsentError : public std::out_of_range {
            public:
                explicit TokenAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class CarouselBrassRing {
            public:
                explicit CarouselBrassRing(std::size_t pegs);
                void hang(const std::string& token);
                std::string pluck();
                bool strung(const std::string& token) const;
                std::size_t hanging() const;
                std::size_t pegs() const;
                std::size_t peg_slot(const std::string& token) const;
                std::size_t brass_slot() const;
            };
            """,
            """
            class CarouselConfigError : public std::invalid_argument {
            public:
                explicit CarouselConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CarouselEmptyError : public std::runtime_error {
            public:
                explicit CarouselEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class CarouselFullError : public std::logic_error {
            public:
                explicit CarouselFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TokenAbsentError : public std::out_of_range {
            public:
                explicit TokenAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class CarouselBrassRing {
            public:
                explicit CarouselBrassRing(std::size_t pegs);
                void hang(const std::string& token);
                std::string pluck();
                bool strung(const std::string& token) const;
                std::size_t hanging() const;
                std::size_t pegs() const;
                std::size_t peg_slot(const std::string& token) const;
                std::size_t brass_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string token;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            CarouselBrassRing::CarouselBrassRing(std::size_t pegs) {
                if (pegs == 0) throw CarouselConfigError("carousel needs at least one peg");
                cells_ = std::vector<Cell>(pegs);
            }
            std::size_t CarouselBrassRing::pegs() const { return cells_.size(); }
            std::size_t CarouselBrassRing::hanging() const { return used_; }
            bool CarouselBrassRing::strung(const std::string& token) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.token == token) return true;
                }
                return false;
            }
            void CarouselBrassRing::hang(const std::string& token) {
                if (used_ == cells_.size()) throw CarouselFullError("carousel is full");
                cells_[next_].occupied = true;
                cells_[next_].token = token;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string CarouselBrassRing::pluck() {
                if (used_ == 0) throw CarouselEmptyError("carousel is empty");
                std::string value = cells_[oldest_].token;
                cells_[oldest_].occupied = false;
                cells_[oldest_].token.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t CarouselBrassRing::brass_slot() const {
                if (used_ == 0) throw CarouselEmptyError("carousel is empty");
                return oldest_;
            }
            std::size_t CarouselBrassRing::peg_slot(const std::string& token) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].token == token) return slot;
                }
                throw TokenAbsentError("token is not strung");
            }
            """,
            """
            CarouselBrassRing::CarouselBrassRing(std::size_t pegs) {
                if (pegs == 0) throw CarouselConfigError("carousel needs at least one peg");
                cells_ = std::vector<Cell>(pegs);
            }
            std::size_t CarouselBrassRing::pegs() const { return cells_.size(); }
            std::size_t CarouselBrassRing::hanging() const { return used_; }
            bool CarouselBrassRing::strung(const std::string& token) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].token == token) return true;
                }
                return false;
            }
            void CarouselBrassRing::hang(const std::string& token) {
                if (used_ == cells_.size()) throw CarouselFullError("carousel is full");
                cells_[used_].occupied = true;
                cells_[used_].token = token;
                ++used_;
            }
            std::string CarouselBrassRing::pluck() {
                if (used_ == 0) throw CarouselEmptyError("carousel is empty");
                std::string value = cells_[0].token;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].token.clear();
                --used_;
                return value;
            }
            std::size_t CarouselBrassRing::brass_slot() const {
                if (used_ == 0) throw CarouselEmptyError("carousel is empty");
                return 0;
            }
            std::size_t CarouselBrassRing::peg_slot(const std::string& token) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].token == token) return i;
                }
                throw TokenAbsentError("token is not strung");
            }
            """,
            """
            CarouselBrassRing carousel(3);
            carousel.hang("ruby");
            carousel.hang("opal");
            if (!carousel.strung("ruby") || !carousel.strung("opal")) return 1;
            if (carousel.hanging() != 2U) return 2;
            carousel.hang("onyx");
            if (carousel.pluck() != "ruby") return 3;
            carousel.hang("jade");
            if (carousel.pluck() != "opal") return 4;
            if (carousel.pluck() != "onyx") return 5;
            if (carousel.pluck() != "jade") return 6;
            if (carousel.hanging() != 0U) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { CarouselBrassRing zero(0); (void)zero; } catch (const CarouselConfigError&) { threw = true; }
            if (!threw) return 1;
            CarouselBrassRing carousel(3);
            threw = false;
            try { carousel.pluck(); } catch (const CarouselEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { carousel.brass_slot(); } catch (const CarouselEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { carousel.peg_slot("agate"); } catch (const TokenAbsentError&) { threw = true; }
            if (!threw) return 4;
            carousel.hang("agate");
            carousel.hang("beryl");
            carousel.hang("coral");
            if (carousel.brass_slot() != 0U) return 5;
            threw = false;
            try { carousel.hang("topaz"); } catch (const CarouselFullError&) { threw = true; }
            if (!threw) return 6;
            if (carousel.hanging() != 3U) return 7;
            if (carousel.pluck() != "agate") return 8;
            if (carousel.pluck() != "beryl") return 9;
            carousel.hang("topaz");
            carousel.hang("pearl");
            if (carousel.brass_slot() != 2U) return 10;
            if (carousel.peg_slot("topaz") != 0U) return 11;
            if (carousel.peg_slot("pearl") != 1U) return 12;
            if (carousel.peg_slot("coral") != 2U) return 13;
            if (carousel.pluck() != "coral") return 14;
            if (carousel.pluck() != "topaz") return 15;
            if (carousel.brass_slot() != 1U) return 16;
            if (carousel.pluck() != "pearl") return 17;
            threw = false;
            try { carousel.peg_slot("coral"); } catch (const TokenAbsentError&) { threw = true; }
            if (!threw) return 18;
            return 0;
            """,
            "a fixed carousel of token pegs whose physical peg slots and brass cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical peg_slot and brass_slot values after hang/pluck sequences that wrap the carousel, full and empty channels, absent-token lookup, and zero-peg rejection",
            "string-keyed ring with exact slot observables",
            "exception-throwing bounded ring with slot-position queries",
        ),
        c(
            "f26cbuf-revolving-door-wings",
            "Revolving door wings",
            "revolving_door",
            """
            class DoorConfigError : public std::invalid_argument {
            public:
                explicit DoorConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DoorEmptyError : public std::runtime_error {
            public:
                explicit DoorEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DoorFullError : public std::logic_error {
            public:
                explicit DoorFullError(const std::string& message) : std::logic_error(message) {}
            };
            class WingAbsentError : public std::out_of_range {
            public:
                explicit WingAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class RevolvingDoorWings {
            public:
                explicit RevolvingDoorWings(std::size_t wing_count);
                void admit(std::int32_t visitors);
                std::int32_t discharge();
                bool queued(std::int32_t visitors) const;
                std::size_t occupied_wings() const;
                std::size_t wing_count() const;
                std::size_t wing_slot(std::int32_t visitors) const;
                std::size_t exit_wing_slot() const;
            };
            """,
            """
            class DoorConfigError : public std::invalid_argument {
            public:
                explicit DoorConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DoorEmptyError : public std::runtime_error {
            public:
                explicit DoorEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DoorFullError : public std::logic_error {
            public:
                explicit DoorFullError(const std::string& message) : std::logic_error(message) {}
            };
            class WingAbsentError : public std::out_of_range {
            public:
                explicit WingAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class RevolvingDoorWings {
            public:
                explicit RevolvingDoorWings(std::size_t wing_count);
                void admit(std::int32_t visitors);
                std::int32_t discharge();
                bool queued(std::int32_t visitors) const;
                std::size_t occupied_wings() const;
                std::size_t wing_count() const;
                std::size_t wing_slot(std::int32_t visitors) const;
                std::size_t exit_wing_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t visitors = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            RevolvingDoorWings::RevolvingDoorWings(std::size_t wing_count) {
                if (wing_count == 0) throw DoorConfigError("door needs at least one wing");
                cells_ = std::vector<Cell>(wing_count);
            }
            std::size_t RevolvingDoorWings::wing_count() const { return cells_.size(); }
            std::size_t RevolvingDoorWings::occupied_wings() const { return used_; }
            bool RevolvingDoorWings::queued(std::int32_t visitors) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.visitors == visitors) return true;
                }
                return false;
            }
            void RevolvingDoorWings::admit(std::int32_t visitors) {
                if (used_ == cells_.size()) throw DoorFullError("door is full");
                cells_[next_].occupied = true;
                cells_[next_].visitors = visitors;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t RevolvingDoorWings::discharge() {
                if (used_ == 0) throw DoorEmptyError("door is empty");
                std::int32_t value = cells_[oldest_].visitors;
                cells_[oldest_].occupied = false;
                cells_[oldest_].visitors = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t RevolvingDoorWings::exit_wing_slot() const {
                if (used_ == 0) throw DoorEmptyError("door is empty");
                return oldest_;
            }
            std::size_t RevolvingDoorWings::wing_slot(std::int32_t visitors) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].visitors == visitors) return slot;
                }
                throw WingAbsentError("visitor group is not queued");
            }
            """,
            """
            RevolvingDoorWings::RevolvingDoorWings(std::size_t wing_count) {
                if (wing_count == 0) throw DoorConfigError("door needs at least one wing");
                cells_ = std::vector<Cell>(wing_count);
            }
            std::size_t RevolvingDoorWings::wing_count() const { return cells_.size(); }
            std::size_t RevolvingDoorWings::occupied_wings() const { return used_; }
            bool RevolvingDoorWings::queued(std::int32_t visitors) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].visitors == visitors) return true;
                }
                return false;
            }
            void RevolvingDoorWings::admit(std::int32_t visitors) {
                if (used_ == cells_.size()) throw DoorFullError("door is full");
                cells_[used_].occupied = true;
                cells_[used_].visitors = visitors;
                ++used_;
            }
            std::int32_t RevolvingDoorWings::discharge() {
                if (used_ == 0) throw DoorEmptyError("door is empty");
                std::int32_t value = cells_[0].visitors;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].visitors = 0;
                --used_;
                return value;
            }
            std::size_t RevolvingDoorWings::exit_wing_slot() const {
                if (used_ == 0) throw DoorEmptyError("door is empty");
                return 0;
            }
            std::size_t RevolvingDoorWings::wing_slot(std::int32_t visitors) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].visitors == visitors) return i;
                }
                throw WingAbsentError("visitor group is not queued");
            }
            """,
            """
            RevolvingDoorWings door(4);
            door.admit(5);
            door.admit(9);
            if (!door.queued(5) || !door.queued(9)) return 1;
            if (door.occupied_wings() != 2U) return 2;
            door.admit(13);
            if (door.discharge() != 5) return 3;
            door.admit(17);
            door.admit(21);
            if (door.discharge() != 9) return 4;
            if (door.discharge() != 13) return 5;
            if (door.discharge() != 17) return 6;
            if (door.discharge() != 21) return 7;
            if (door.occupied_wings() != 0U) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { RevolvingDoorWings zero(0); (void)zero; } catch (const DoorConfigError&) { threw = true; }
            if (!threw) return 1;
            RevolvingDoorWings door(4);
            threw = false;
            try { door.discharge(); } catch (const DoorEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { door.exit_wing_slot(); } catch (const DoorEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { door.wing_slot(5); } catch (const WingAbsentError&) { threw = true; }
            if (!threw) return 4;
            door.admit(5);
            door.admit(10);
            door.admit(15);
            door.admit(20);
            if (door.exit_wing_slot() != 0U) return 5;
            threw = false;
            try { door.admit(25); } catch (const DoorFullError&) { threw = true; }
            if (!threw) return 6;
            if (door.occupied_wings() != 4U) return 7;
            if (door.discharge() != 5) return 8;
            if (door.discharge() != 10) return 9;
            door.admit(25);
            door.admit(26);
            if (door.exit_wing_slot() != 2U) return 10;
            if (door.wing_slot(25) != 0U) return 11;
            if (door.wing_slot(26) != 1U) return 12;
            if (door.wing_slot(15) != 2U) return 13;
            if (door.wing_slot(20) != 3U) return 14;
            if (door.discharge() != 15) return 15;
            if (door.discharge() != 20) return 16;
            if (door.exit_wing_slot() != 0U) return 17;
            if (door.discharge() != 25) return 18;
            if (door.discharge() != 26) return 19;
            threw = false;
            try { door.wing_slot(15); } catch (const WingAbsentError&) { threw = true; }
            if (!threw) return 20;
            return 0;
            """,
            "a fixed door of visitor wings whose physical wing slots and exit cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical wing_slot and exit_wing_slot values after admit/discharge sequences that wrap the door, full and empty channels, absent-wing lookup, and zero-wing rejection",
            "capacity-bounded occupancy with wraparound slot math",
            "exception-throwing bounded ring with slot-position queries",
        ),
        c(
            "f26cbuf-canal-lock-chambers",
            "Canal lock chambers",
            "canal_lock",
            """
            class LockConfigError : public std::invalid_argument {
            public:
                explicit LockConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LockEmptyError : public std::runtime_error {
            public:
                explicit LockEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class LockFullError : public std::logic_error {
            public:
                explicit LockFullError(const std::string& message) : std::logic_error(message) {}
            };
            class ChamberAbsentError : public std::out_of_range {
            public:
                explicit ChamberAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class CanalLockChambers {
            public:
                explicit CanalLockChambers(std::size_t chambers_max);
                void moor(std::int64_t draught);
                std::int64_t release();
                bool berthed(std::int64_t draught) const;
                std::size_t moored() const;
                std::size_t chambers_max() const;
                std::size_t chamber_slot(std::int64_t draught) const;
                std::size_t gate_slot() const;
            };
            """,
            """
            class LockConfigError : public std::invalid_argument {
            public:
                explicit LockConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LockEmptyError : public std::runtime_error {
            public:
                explicit LockEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class LockFullError : public std::logic_error {
            public:
                explicit LockFullError(const std::string& message) : std::logic_error(message) {}
            };
            class ChamberAbsentError : public std::out_of_range {
            public:
                explicit ChamberAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class CanalLockChambers {
            public:
                explicit CanalLockChambers(std::size_t chambers_max);
                void moor(std::int64_t draught);
                std::int64_t release();
                bool berthed(std::int64_t draught) const;
                std::size_t moored() const;
                std::size_t chambers_max() const;
                std::size_t chamber_slot(std::int64_t draught) const;
                std::size_t gate_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t draught = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            CanalLockChambers::CanalLockChambers(std::size_t chambers_max) {
                if (chambers_max == 0) throw LockConfigError("lock needs at least one chamber");
                cells_ = std::vector<Cell>(chambers_max);
            }
            std::size_t CanalLockChambers::chambers_max() const { return cells_.size(); }
            std::size_t CanalLockChambers::moored() const { return used_; }
            bool CanalLockChambers::berthed(std::int64_t draught) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.draught == draught) return true;
                }
                return false;
            }
            void CanalLockChambers::moor(std::int64_t draught) {
                if (used_ == cells_.size()) throw LockFullError("lock is full");
                cells_[next_].occupied = true;
                cells_[next_].draught = draught;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t CanalLockChambers::release() {
                if (used_ == 0) throw LockEmptyError("lock is empty");
                std::int64_t value = cells_[oldest_].draught;
                cells_[oldest_].occupied = false;
                cells_[oldest_].draught = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t CanalLockChambers::gate_slot() const {
                if (used_ == 0) throw LockEmptyError("lock is empty");
                return oldest_;
            }
            std::size_t CanalLockChambers::chamber_slot(std::int64_t draught) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].draught == draught) return slot;
                }
                throw ChamberAbsentError("draught is not berthed");
            }
            """,
            """
            CanalLockChambers::CanalLockChambers(std::size_t chambers_max) {
                if (chambers_max == 0) throw LockConfigError("lock needs at least one chamber");
                cells_ = std::vector<Cell>(chambers_max);
            }
            std::size_t CanalLockChambers::chambers_max() const { return cells_.size(); }
            std::size_t CanalLockChambers::moored() const { return used_; }
            bool CanalLockChambers::berthed(std::int64_t draught) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].draught == draught) return true;
                }
                return false;
            }
            void CanalLockChambers::moor(std::int64_t draught) {
                if (used_ == cells_.size()) throw LockFullError("lock is full");
                cells_[used_].occupied = true;
                cells_[used_].draught = draught;
                ++used_;
            }
            std::int64_t CanalLockChambers::release() {
                if (used_ == 0) throw LockEmptyError("lock is empty");
                std::int64_t value = cells_[0].draught;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].draught = 0;
                --used_;
                return value;
            }
            std::size_t CanalLockChambers::gate_slot() const {
                if (used_ == 0) throw LockEmptyError("lock is empty");
                return 0;
            }
            std::size_t CanalLockChambers::chamber_slot(std::int64_t draught) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].draught == draught) return i;
                }
                throw ChamberAbsentError("draught is not berthed");
            }
            """,
            """
            CanalLockChambers lock_ring(3);
            lock_ring.moor(2100);
            lock_ring.moor(3400);
            if (!lock_ring.berthed(2100) || !lock_ring.berthed(3400)) return 1;
            if (lock_ring.moored() != 2U) return 2;
            lock_ring.moor(4700);
            if (lock_ring.release() != 2100) return 3;
            lock_ring.moor(5600);
            if (lock_ring.release() != 3400) return 4;
            if (lock_ring.release() != 4700) return 5;
            if (lock_ring.release() != 5600) return 6;
            if (lock_ring.moored() != 0U) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { CanalLockChambers zero(0); (void)zero; } catch (const LockConfigError&) { threw = true; }
            if (!threw) return 1;
            CanalLockChambers lock_ring(3);
            threw = false;
            try { lock_ring.release(); } catch (const LockEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { lock_ring.gate_slot(); } catch (const LockEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { lock_ring.chamber_slot(700); } catch (const ChamberAbsentError&) { threw = true; }
            if (!threw) return 4;
            lock_ring.moor(1100);
            lock_ring.moor(2200);
            lock_ring.moor(3300);
            if (lock_ring.gate_slot() != 0U) return 5;
            threw = false;
            try { lock_ring.moor(4400); } catch (const LockFullError&) { threw = true; }
            if (!threw) return 6;
            if (lock_ring.moored() != 3U) return 7;
            if (lock_ring.release() != 1100) return 8;
            if (lock_ring.release() != 2200) return 9;
            lock_ring.moor(4400);
            lock_ring.moor(5500);
            if (lock_ring.gate_slot() != 2U) return 10;
            if (lock_ring.chamber_slot(4400) != 0U) return 11;
            if (lock_ring.chamber_slot(5500) != 1U) return 12;
            if (lock_ring.chamber_slot(3300) != 2U) return 13;
            if (lock_ring.release() != 3300) return 14;
            if (lock_ring.release() != 4400) return 15;
            if (lock_ring.gate_slot() != 1U) return 16;
            if (lock_ring.release() != 5500) return 17;
            threw = false;
            try { lock_ring.chamber_slot(3300); } catch (const ChamberAbsentError&) { threw = true; }
            if (!threw) return 18;
            return 0;
            """,
            "a fixed lock of draught chambers whose physical chamber slots and gate cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical chamber_slot and gate_slot values after moor/release sequences that wrap the lock, full and empty channels, absent-chamber lookup, and zero-chamber rejection",
            "project-context ring with navigation-domain slot traces",
            "exception-throwing bounded ring with slot-position queries",
            project_support=True,
        ),
        c(
            "f26cbuf-comet-trail-exposures",
            "Comet trail exposures",
            "comet_trail",
            """
            class TrailConfigError : public std::invalid_argument {
            public:
                explicit TrailConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TrailEmptyError : public std::runtime_error {
            public:
                explicit TrailEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TrailFullError : public std::logic_error {
            public:
                explicit TrailFullError(const std::string& message) : std::logic_error(message) {}
            };
            class FrameAbsentError : public std::out_of_range {
            public:
                explicit FrameAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class CometTrailExposures {
            public:
                explicit CometTrailExposures(std::size_t plates);
                void expose(std::int32_t frame);
                std::int32_t develop();
                bool exposed(std::int32_t frame) const;
                std::size_t frames() const;
                std::size_t plates() const;
                std::size_t plate_slot(std::int32_t frame) const;
                std::size_t develop_slot() const;
            };
            """,
            """
            class TrailConfigError : public std::invalid_argument {
            public:
                explicit TrailConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TrailEmptyError : public std::runtime_error {
            public:
                explicit TrailEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TrailFullError : public std::logic_error {
            public:
                explicit TrailFullError(const std::string& message) : std::logic_error(message) {}
            };
            class FrameAbsentError : public std::out_of_range {
            public:
                explicit FrameAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class CometTrailExposures {
            public:
                explicit CometTrailExposures(std::size_t plates);
                void expose(std::int32_t frame);
                std::int32_t develop();
                bool exposed(std::int32_t frame) const;
                std::size_t frames() const;
                std::size_t plates() const;
                std::size_t plate_slot(std::int32_t frame) const;
                std::size_t develop_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t frame = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            CometTrailExposures::CometTrailExposures(std::size_t plates) {
                if (plates == 0) throw TrailConfigError("trail needs at least one plate");
                cells_ = std::vector<Cell>(plates);
            }
            std::size_t CometTrailExposures::plates() const { return cells_.size(); }
            std::size_t CometTrailExposures::frames() const { return used_; }
            bool CometTrailExposures::exposed(std::int32_t frame) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.frame == frame) return true;
                }
                return false;
            }
            void CometTrailExposures::expose(std::int32_t frame) {
                if (used_ == cells_.size()) throw TrailFullError("trail is full");
                cells_[next_].occupied = true;
                cells_[next_].frame = frame;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t CometTrailExposures::develop() {
                if (used_ == 0) throw TrailEmptyError("trail is empty");
                std::int32_t value = cells_[oldest_].frame;
                cells_[oldest_].occupied = false;
                cells_[oldest_].frame = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t CometTrailExposures::develop_slot() const {
                if (used_ == 0) throw TrailEmptyError("trail is empty");
                return oldest_;
            }
            std::size_t CometTrailExposures::plate_slot(std::int32_t frame) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].frame == frame) return slot;
                }
                throw FrameAbsentError("frame is not exposed");
            }
            """,
            """
            CometTrailExposures::CometTrailExposures(std::size_t plates) {
                if (plates == 0) throw TrailConfigError("trail needs at least one plate");
                cells_ = std::vector<Cell>(plates);
            }
            std::size_t CometTrailExposures::plates() const { return cells_.size(); }
            std::size_t CometTrailExposures::frames() const { return used_; }
            bool CometTrailExposures::exposed(std::int32_t frame) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].frame == frame) return true;
                }
                return false;
            }
            void CometTrailExposures::expose(std::int32_t frame) {
                if (used_ == cells_.size()) throw TrailFullError("trail is full");
                cells_[used_].occupied = true;
                cells_[used_].frame = frame;
                ++used_;
            }
            std::int32_t CometTrailExposures::develop() {
                if (used_ == 0) throw TrailEmptyError("trail is empty");
                std::int32_t value = cells_[0].frame;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].frame = 0;
                --used_;
                return value;
            }
            std::size_t CometTrailExposures::develop_slot() const {
                if (used_ == 0) throw TrailEmptyError("trail is empty");
                return 0;
            }
            std::size_t CometTrailExposures::plate_slot(std::int32_t frame) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].frame == frame) return i;
                }
                throw FrameAbsentError("frame is not exposed");
            }
            """,
            """
            CometTrailExposures trail(4);
            trail.expose(101);
            trail.expose(203);
            if (!trail.exposed(101) || !trail.exposed(203)) return 1;
            if (trail.frames() != 2U) return 2;
            trail.expose(305);
            if (trail.develop() != 101) return 3;
            trail.expose(407);
            trail.expose(509);
            if (trail.develop() != 203) return 4;
            if (trail.develop() != 305) return 5;
            if (trail.develop() != 407) return 6;
            if (trail.develop() != 509) return 7;
            if (trail.frames() != 0U) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { CometTrailExposures zero(0); (void)zero; } catch (const TrailConfigError&) { threw = true; }
            if (!threw) return 1;
            CometTrailExposures trail(4);
            threw = false;
            try { trail.develop(); } catch (const TrailEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { trail.develop_slot(); } catch (const TrailEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { trail.plate_slot(64); } catch (const FrameAbsentError&) { threw = true; }
            if (!threw) return 4;
            trail.expose(64);
            trail.expose(128);
            trail.expose(256);
            trail.expose(512);
            if (trail.develop_slot() != 0U) return 5;
            threw = false;
            try { trail.expose(1024); } catch (const TrailFullError&) { threw = true; }
            if (!threw) return 6;
            if (trail.frames() != 4U) return 7;
            if (trail.develop() != 64) return 8;
            if (trail.develop() != 128) return 9;
            trail.expose(1024);
            trail.expose(2048);
            if (trail.develop_slot() != 2U) return 10;
            if (trail.plate_slot(1024) != 0U) return 11;
            if (trail.plate_slot(2048) != 1U) return 12;
            if (trail.plate_slot(256) != 2U) return 13;
            if (trail.plate_slot(512) != 3U) return 14;
            if (trail.develop() != 256) return 15;
            if (trail.develop() != 512) return 16;
            if (trail.develop_slot() != 0U) return 17;
            if (trail.develop() != 1024) return 18;
            if (trail.develop() != 2048) return 19;
            threw = false;
            try { trail.plate_slot(256); } catch (const FrameAbsentError&) { threw = true; }
            if (!threw) return 20;
            return 0;
            """,
            "a fixed trail of exposure plates whose physical plate slots and develop cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical plate_slot and develop_slot values after expose/develop sequences that wrap the trail, full and empty channels, absent-frame lookup, and zero-plate rejection",
            "imaging-domain ring with deterministic wrap positions",
            "exception-throwing bounded ring with slot-position queries",
        ),
        c(
            "f26cbuf-radar-sweep-echoes",
            "Radar sweep echoes",
            "radar_sweep",
            """
            class SweepConfigError : public std::invalid_argument {
            public:
                explicit SweepConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SweepEmptyError : public std::runtime_error {
            public:
                explicit SweepEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class SweepFullError : public std::logic_error {
            public:
                explicit SweepFullError(const std::string& message) : std::logic_error(message) {}
            };
            class EchoAbsentError : public std::out_of_range {
            public:
                explicit EchoAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class RadarSweepEchoes {
            public:
                explicit RadarSweepEchoes(std::size_t sweep_cells);
                void ping(std::int32_t range_km);
                std::int32_t resolve();
                bool tracking(std::int32_t range_km) const;
                std::size_t echoes() const;
                std::size_t sweep_cells() const;
                std::size_t echo_slot(std::int32_t range_km) const;
                std::size_t resolve_slot() const;
            };
            """,
            """
            class SweepConfigError : public std::invalid_argument {
            public:
                explicit SweepConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SweepEmptyError : public std::runtime_error {
            public:
                explicit SweepEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class SweepFullError : public std::logic_error {
            public:
                explicit SweepFullError(const std::string& message) : std::logic_error(message) {}
            };
            class EchoAbsentError : public std::out_of_range {
            public:
                explicit EchoAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class RadarSweepEchoes {
            public:
                explicit RadarSweepEchoes(std::size_t sweep_cells);
                void ping(std::int32_t range_km);
                std::int32_t resolve();
                bool tracking(std::int32_t range_km) const;
                std::size_t echoes() const;
                std::size_t sweep_cells() const;
                std::size_t echo_slot(std::int32_t range_km) const;
                std::size_t resolve_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t range_km = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            RadarSweepEchoes::RadarSweepEchoes(std::size_t sweep_cells) {
                if (sweep_cells == 0) throw SweepConfigError("sweep needs at least one cell");
                cells_ = std::vector<Cell>(sweep_cells);
            }
            std::size_t RadarSweepEchoes::sweep_cells() const { return cells_.size(); }
            std::size_t RadarSweepEchoes::echoes() const { return used_; }
            bool RadarSweepEchoes::tracking(std::int32_t range_km) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.range_km == range_km) return true;
                }
                return false;
            }
            void RadarSweepEchoes::ping(std::int32_t range_km) {
                if (used_ == cells_.size()) throw SweepFullError("sweep is full");
                cells_[next_].occupied = true;
                cells_[next_].range_km = range_km;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t RadarSweepEchoes::resolve() {
                if (used_ == 0) throw SweepEmptyError("sweep is empty");
                std::int32_t value = cells_[oldest_].range_km;
                cells_[oldest_].occupied = false;
                cells_[oldest_].range_km = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t RadarSweepEchoes::resolve_slot() const {
                if (used_ == 0) throw SweepEmptyError("sweep is empty");
                return oldest_;
            }
            std::size_t RadarSweepEchoes::echo_slot(std::int32_t range_km) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].range_km == range_km) return slot;
                }
                throw EchoAbsentError("echo is not tracked");
            }
            """,
            """
            RadarSweepEchoes::RadarSweepEchoes(std::size_t sweep_cells) {
                if (sweep_cells == 0) throw SweepConfigError("sweep needs at least one cell");
                cells_ = std::vector<Cell>(sweep_cells);
            }
            std::size_t RadarSweepEchoes::sweep_cells() const { return cells_.size(); }
            std::size_t RadarSweepEchoes::echoes() const { return used_; }
            bool RadarSweepEchoes::tracking(std::int32_t range_km) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].range_km == range_km) return true;
                }
                return false;
            }
            void RadarSweepEchoes::ping(std::int32_t range_km) {
                if (used_ == cells_.size()) throw SweepFullError("sweep is full");
                cells_[used_].occupied = true;
                cells_[used_].range_km = range_km;
                ++used_;
            }
            std::int32_t RadarSweepEchoes::resolve() {
                if (used_ == 0) throw SweepEmptyError("sweep is empty");
                std::int32_t value = cells_[0].range_km;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].range_km = 0;
                --used_;
                return value;
            }
            std::size_t RadarSweepEchoes::resolve_slot() const {
                if (used_ == 0) throw SweepEmptyError("sweep is empty");
                return 0;
            }
            std::size_t RadarSweepEchoes::echo_slot(std::int32_t range_km) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].range_km == range_km) return i;
                }
                throw EchoAbsentError("echo is not tracked");
            }
            """,
            """
            RadarSweepEchoes radar(3);
            radar.ping(12);
            radar.ping(48);
            if (!radar.tracking(12) || !radar.tracking(48)) return 1;
            if (radar.echoes() != 2U) return 2;
            radar.ping(96);
            if (radar.resolve() != 12) return 3;
            radar.ping(120);
            if (radar.resolve() != 48) return 4;
            if (radar.resolve() != 96) return 5;
            if (radar.resolve() != 120) return 6;
            if (radar.echoes() != 0U) return 7;
            return 0;
            """,
            """
            bool threw = false;
            try { RadarSweepEchoes zero(0); (void)zero; } catch (const SweepConfigError&) { threw = true; }
            if (!threw) return 1;
            RadarSweepEchoes radar(3);
            threw = false;
            try { radar.resolve(); } catch (const SweepEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { radar.resolve_slot(); } catch (const SweepEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { radar.echo_slot(15); } catch (const EchoAbsentError&) { threw = true; }
            if (!threw) return 4;
            radar.ping(15);
            radar.ping(30);
            radar.ping(45);
            if (radar.resolve_slot() != 0U) return 5;
            threw = false;
            try { radar.ping(60); } catch (const SweepFullError&) { threw = true; }
            if (!threw) return 6;
            if (radar.echoes() != 3U) return 7;
            if (radar.resolve() != 15) return 8;
            if (radar.resolve() != 30) return 9;
            radar.ping(60);
            radar.ping(75);
            if (radar.resolve_slot() != 2U) return 10;
            if (radar.echo_slot(60) != 0U) return 11;
            if (radar.echo_slot(75) != 1U) return 12;
            if (radar.echo_slot(45) != 2U) return 13;
            if (radar.resolve() != 45) return 14;
            if (radar.resolve() != 60) return 15;
            if (radar.resolve_slot() != 1U) return 16;
            if (radar.resolve() != 75) return 17;
            threw = false;
            try { radar.echo_slot(45); } catch (const EchoAbsentError&) { threw = true; }
            if (!threw) return 18;
            return 0;
            """,
            "a fixed sweep of echo cells whose physical echo slots and resolve cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical echo_slot and resolve_slot values after ping/resolve sequences that wrap the sweep, full and empty channels, absent-echo lookup, and zero-cell rejection",
            "sensor-domain ring with physical echo positions",
            "exception-throwing bounded ring with slot-position queries",
        ),
        c(
            "f26cbuf-windmill-sail-pitches",
            "Windmill sail pitches",
            "windmill",
            """
            class SailConfigError : public std::invalid_argument {
            public:
                explicit SailConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SailEmptyError : public std::runtime_error {
            public:
                explicit SailEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class SailFullError : public std::logic_error {
            public:
                explicit SailFullError(const std::string& message) : std::logic_error(message) {}
            };
            class PitchAbsentError : public std::out_of_range {
            public:
                explicit PitchAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class WindmillSailPitches {
            public:
                explicit WindmillSailPitches(std::size_t yards);
                void reef(std::int64_t pitch);
                std::int64_t hoist();
                bool rigged(std::int64_t pitch) const;
                std::size_t sails() const;
                std::size_t yards() const;
                std::size_t yard_slot(std::int64_t pitch) const;
                std::size_t hoist_slot() const;
            };
            """,
            """
            class SailConfigError : public std::invalid_argument {
            public:
                explicit SailConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SailEmptyError : public std::runtime_error {
            public:
                explicit SailEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class SailFullError : public std::logic_error {
            public:
                explicit SailFullError(const std::string& message) : std::logic_error(message) {}
            };
            class PitchAbsentError : public std::out_of_range {
            public:
                explicit PitchAbsentError(const std::string& message) : std::out_of_range(message) {}
            };
            class WindmillSailPitches {
            public:
                explicit WindmillSailPitches(std::size_t yards);
                void reef(std::int64_t pitch);
                std::int64_t hoist();
                bool rigged(std::int64_t pitch) const;
                std::size_t sails() const;
                std::size_t yards() const;
                std::size_t yard_slot(std::int64_t pitch) const;
                std::size_t hoist_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t pitch = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            WindmillSailPitches::WindmillSailPitches(std::size_t yards) {
                if (yards == 0) throw SailConfigError("windmill needs at least one yard");
                cells_ = std::vector<Cell>(yards);
            }
            std::size_t WindmillSailPitches::yards() const { return cells_.size(); }
            std::size_t WindmillSailPitches::sails() const { return used_; }
            bool WindmillSailPitches::rigged(std::int64_t pitch) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.pitch == pitch) return true;
                }
                return false;
            }
            void WindmillSailPitches::reef(std::int64_t pitch) {
                if (used_ == cells_.size()) throw SailFullError("windmill is full");
                cells_[next_].occupied = true;
                cells_[next_].pitch = pitch;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t WindmillSailPitches::hoist() {
                if (used_ == 0) throw SailEmptyError("windmill is empty");
                std::int64_t value = cells_[oldest_].pitch;
                cells_[oldest_].occupied = false;
                cells_[oldest_].pitch = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t WindmillSailPitches::hoist_slot() const {
                if (used_ == 0) throw SailEmptyError("windmill is empty");
                return oldest_;
            }
            std::size_t WindmillSailPitches::yard_slot(std::int64_t pitch) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].pitch == pitch) return slot;
                }
                throw PitchAbsentError("pitch is not rigged");
            }
            """,
            """
            WindmillSailPitches::WindmillSailPitches(std::size_t yards) {
                if (yards == 0) throw SailConfigError("windmill needs at least one yard");
                cells_ = std::vector<Cell>(yards);
            }
            std::size_t WindmillSailPitches::yards() const { return cells_.size(); }
            std::size_t WindmillSailPitches::sails() const { return used_; }
            bool WindmillSailPitches::rigged(std::int64_t pitch) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].pitch == pitch) return true;
                }
                return false;
            }
            void WindmillSailPitches::reef(std::int64_t pitch) {
                if (used_ == cells_.size()) throw SailFullError("windmill is full");
                cells_[used_].occupied = true;
                cells_[used_].pitch = pitch;
                ++used_;
            }
            std::int64_t WindmillSailPitches::hoist() {
                if (used_ == 0) throw SailEmptyError("windmill is empty");
                std::int64_t value = cells_[0].pitch;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].pitch = 0;
                --used_;
                return value;
            }
            std::size_t WindmillSailPitches::hoist_slot() const {
                if (used_ == 0) throw SailEmptyError("windmill is empty");
                return 0;
            }
            std::size_t WindmillSailPitches::yard_slot(std::int64_t pitch) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].pitch == pitch) return i;
                }
                throw PitchAbsentError("pitch is not rigged");
            }
            """,
            """
            WindmillSailPitches mill(4);
            mill.reef(110);
            mill.reef(220);
            if (!mill.rigged(110) || !mill.rigged(220)) return 1;
            if (mill.sails() != 2U) return 2;
            mill.reef(330);
            if (mill.hoist() != 110) return 3;
            mill.reef(440);
            mill.reef(550);
            if (mill.hoist() != 220) return 4;
            if (mill.hoist() != 330) return 5;
            if (mill.hoist() != 440) return 6;
            if (mill.hoist() != 550) return 7;
            if (mill.sails() != 0U) return 8;
            return 0;
            """,
            """
            bool threw = false;
            try { WindmillSailPitches zero(0); (void)zero; } catch (const SailConfigError&) { threw = true; }
            if (!threw) return 1;
            WindmillSailPitches mill(4);
            threw = false;
            try { mill.hoist(); } catch (const SailEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { mill.hoist_slot(); } catch (const SailEmptyError&) { threw = true; }
            if (!threw) return 3;
            threw = false;
            try { mill.yard_slot(90); } catch (const PitchAbsentError&) { threw = true; }
            if (!threw) return 4;
            mill.reef(90);
            mill.reef(180);
            mill.reef(270);
            mill.reef(360);
            if (mill.hoist_slot() != 0U) return 5;
            threw = false;
            try { mill.reef(450); } catch (const SailFullError&) { threw = true; }
            if (!threw) return 6;
            if (mill.sails() != 4U) return 7;
            if (mill.hoist() != 90) return 8;
            if (mill.hoist() != 180) return 9;
            mill.reef(450);
            mill.reef(540);
            if (mill.hoist_slot() != 2U) return 10;
            if (mill.yard_slot(450) != 0U) return 11;
            if (mill.yard_slot(540) != 1U) return 12;
            if (mill.yard_slot(270) != 2U) return 13;
            if (mill.yard_slot(360) != 3U) return 14;
            if (mill.hoist() != 270) return 15;
            if (mill.hoist() != 360) return 16;
            if (mill.hoist_slot() != 0U) return 17;
            if (mill.hoist() != 450) return 18;
            if (mill.hoist() != 540) return 19;
            threw = false;
            try { mill.yard_slot(270); } catch (const PitchAbsentError&) { threw = true; }
            if (!threw) return 20;
            return 0;
            """,
            "a fixed windmill of pitch yards whose physical yard slots and hoist cursor stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical yard_slot and hoist_slot values after reef/hoist sequences that wrap the windmill, full and empty channels, absent-pitch lookup, and zero-yard rejection",
            "int64 ring with wraparound sail-yard slots",
            "exception-throwing bounded ring with slot-position queries",
        ),
        c(
            "f26cbuf-chairlift-seat-loop",
            "Chairlift seat loop",
            "chairlift",
            """
            class ChairliftSeatLoop {
            public:
                explicit ChairliftSeatLoop(std::size_t seats);
                bool board(std::int32_t pass);
                std::optional<std::int32_t> alight();
                bool riding(std::int32_t pass) const;
                std::size_t riders() const;
                std::size_t seats() const;
                std::optional<std::size_t> seat_of(std::int32_t pass) const;
                std::optional<std::size_t> alight_seat() const;
            };
            """,
            """
            class ChairliftSeatLoop {
            public:
                explicit ChairliftSeatLoop(std::size_t seats);
                bool board(std::int32_t pass);
                std::optional<std::int32_t> alight();
                bool riding(std::int32_t pass) const;
                std::size_t riders() const;
                std::size_t seats() const;
                std::optional<std::size_t> seat_of(std::int32_t pass) const;
                std::optional<std::size_t> alight_seat() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t pass = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            ChairliftSeatLoop::ChairliftSeatLoop(std::size_t seats) {
                if (seats == 0) throw std::invalid_argument("chairlift needs at least one seat");
                cells_ = std::vector<Cell>(seats);
            }
            std::size_t ChairliftSeatLoop::seats() const { return cells_.size(); }
            std::size_t ChairliftSeatLoop::riders() const { return used_; }
            bool ChairliftSeatLoop::riding(std::int32_t pass) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.pass == pass) return true;
                }
                return false;
            }
            bool ChairliftSeatLoop::board(std::int32_t pass) {
                if (used_ == cells_.size()) return false;
                cells_[next_].occupied = true;
                cells_[next_].pass = pass;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
                return true;
            }
            std::optional<std::int32_t> ChairliftSeatLoop::alight() {
                if (used_ == 0) return std::nullopt;
                std::int32_t value = cells_[oldest_].pass;
                cells_[oldest_].occupied = false;
                cells_[oldest_].pass = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::optional<std::size_t> ChairliftSeatLoop::alight_seat() const {
                if (used_ == 0) return std::nullopt;
                return oldest_;
            }
            std::optional<std::size_t> ChairliftSeatLoop::seat_of(std::int32_t pass) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].pass == pass) return slot;
                }
                return std::nullopt;
            }
            """,
            """
            ChairliftSeatLoop::ChairliftSeatLoop(std::size_t seats) {
                if (seats == 0) throw std::invalid_argument("chairlift needs at least one seat");
                cells_ = std::vector<Cell>(seats);
            }
            std::size_t ChairliftSeatLoop::seats() const { return cells_.size(); }
            std::size_t ChairliftSeatLoop::riders() const { return used_; }
            bool ChairliftSeatLoop::riding(std::int32_t pass) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].pass == pass) return true;
                }
                return false;
            }
            bool ChairliftSeatLoop::board(std::int32_t pass) {
                if (used_ == cells_.size()) return false;
                cells_[used_].occupied = true;
                cells_[used_].pass = pass;
                ++used_;
                return true;
            }
            std::optional<std::int32_t> ChairliftSeatLoop::alight() {
                if (used_ == 0) return std::nullopt;
                std::int32_t value = cells_[0].pass;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].pass = 0;
                --used_;
                return value;
            }
            std::optional<std::size_t> ChairliftSeatLoop::alight_seat() const {
                if (used_ == 0) return std::nullopt;
                return 0;
            }
            std::optional<std::size_t> ChairliftSeatLoop::seat_of(std::int32_t pass) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].pass == pass) return i;
                }
                return std::nullopt;
            }
            """,
            """
            ChairliftSeatLoop lift(2);
            if (!lift.board(101)) return 1;
            if (!lift.board(202)) return 2;
            if (lift.board(303)) return 3;
            auto first = lift.alight();
            if (!first || *first != 101) return 4;
            if (!lift.board(303)) return 5;
            auto second = lift.alight();
            if (!second || *second != 202) return 6;
            auto third = lift.alight();
            if (!third || *third != 303) return 7;
            if (lift.alight().has_value()) return 8;
            if (lift.riders() != 0U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { ChairliftSeatLoop zero(0); (void)zero; } catch (const std::invalid_argument&) { threw = true; }
            if (!threw) return 1;
            ChairliftSeatLoop lift(3);
            if (lift.alight().has_value()) return 2;
            if (lift.alight_seat().has_value()) return 3;
            if (lift.seat_of(55).has_value()) return 4;
            lift.board(11);
            lift.board(22);
            lift.board(33);
            if (lift.board(44)) return 5;
            if (lift.riders() != 3U) return 6;
            if (!lift.alight_seat() || *lift.alight_seat() != 0U) return 7;
            auto first = lift.alight();
            if (!first || *first != 11) return 8;
            auto second = lift.alight();
            if (!second || *second != 22) return 9;
            lift.board(44);
            lift.board(55);
            if (!lift.alight_seat() || *lift.alight_seat() != 2U) return 10;
            if (!lift.seat_of(44) || *lift.seat_of(44) != 0U) return 11;
            if (!lift.seat_of(55) || *lift.seat_of(55) != 1U) return 12;
            if (!lift.seat_of(33) || *lift.seat_of(33) != 2U) return 13;
            if (lift.seat_of(66).has_value()) return 14;
            auto third = lift.alight();
            if (!third || *third != 33) return 15;
            auto fourth = lift.alight();
            if (!fourth || *fourth != 44) return 16;
            if (!lift.alight_seat() || *lift.alight_seat() != 1U) return 17;
            auto fifth = lift.alight();
            if (!fifth || *fifth != 55) return 18;
            if (lift.alight().has_value()) return 19;
            return 0;
            """,
            "a fixed loop of pass seats whose physical seat slots and alight cursor stay observable across wraparound, reported through optional channels",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical seat_of and alight_seat values after board/alight sequences that wrap the loop, false and nullopt channels, absent-pass lookup, and zero-seat rejection",
            "optional-channel ring with physical seat slots",
            "status-returning bounded ring",
        ),
        c(
            "f26cbuf-gondola-cabin-wheel",
            "Gondola cabin wheel",
            "gondola_wheel",
            """
            class GondolaCabinWheel {
            public:
                explicit GondolaCabinWheel(std::size_t cabins);
                bool embark(const std::string& party);
                std::optional<std::string> disembark();
                bool aboard(const std::string& party) const;
                std::size_t cabins_used() const;
                std::size_t cabins() const;
                std::optional<std::size_t> cabin_of(const std::string& party) const;
                std::optional<std::size_t> dock_cabin() const;
            };
            """,
            """
            class GondolaCabinWheel {
            public:
                explicit GondolaCabinWheel(std::size_t cabins);
                bool embark(const std::string& party);
                std::optional<std::string> disembark();
                bool aboard(const std::string& party) const;
                std::size_t cabins_used() const;
                std::size_t cabins() const;
                std::optional<std::size_t> cabin_of(const std::string& party) const;
                std::optional<std::size_t> dock_cabin() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string party;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            GondolaCabinWheel::GondolaCabinWheel(std::size_t cabins) {
                if (cabins == 0) throw std::invalid_argument("wheel needs at least one cabin");
                cells_ = std::vector<Cell>(cabins);
            }
            std::size_t GondolaCabinWheel::cabins() const { return cells_.size(); }
            std::size_t GondolaCabinWheel::cabins_used() const { return used_; }
            bool GondolaCabinWheel::aboard(const std::string& party) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.party == party) return true;
                }
                return false;
            }
            bool GondolaCabinWheel::embark(const std::string& party) {
                if (used_ == cells_.size()) return false;
                cells_[next_].occupied = true;
                cells_[next_].party = party;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
                return true;
            }
            std::optional<std::string> GondolaCabinWheel::disembark() {
                if (used_ == 0) return std::nullopt;
                std::string value = cells_[oldest_].party;
                cells_[oldest_].occupied = false;
                cells_[oldest_].party.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::optional<std::size_t> GondolaCabinWheel::dock_cabin() const {
                if (used_ == 0) return std::nullopt;
                return oldest_;
            }
            std::optional<std::size_t> GondolaCabinWheel::cabin_of(const std::string& party) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].party == party) return slot;
                }
                return std::nullopt;
            }
            """,
            """
            GondolaCabinWheel::GondolaCabinWheel(std::size_t cabins) {
                if (cabins == 0) throw std::invalid_argument("wheel needs at least one cabin");
                cells_ = std::vector<Cell>(cabins);
            }
            std::size_t GondolaCabinWheel::cabins() const { return cells_.size(); }
            std::size_t GondolaCabinWheel::cabins_used() const { return used_; }
            bool GondolaCabinWheel::aboard(const std::string& party) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].party == party) return true;
                }
                return false;
            }
            bool GondolaCabinWheel::embark(const std::string& party) {
                if (used_ == cells_.size()) return false;
                cells_[used_].occupied = true;
                cells_[used_].party = party;
                ++used_;
                return true;
            }
            std::optional<std::string> GondolaCabinWheel::disembark() {
                if (used_ == 0) return std::nullopt;
                std::string value = cells_[0].party;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].party.clear();
                --used_;
                return value;
            }
            std::optional<std::size_t> GondolaCabinWheel::dock_cabin() const {
                if (used_ == 0) return std::nullopt;
                return 0;
            }
            std::optional<std::size_t> GondolaCabinWheel::cabin_of(const std::string& party) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].party == party) return i;
                }
                return std::nullopt;
            }
            """,
            """
            GondolaCabinWheel wheel(2);
            if (!wheel.embark("otters")) return 1;
            if (!wheel.embark("herons")) return 2;
            if (wheel.embark("foxes")) return 3;
            auto first = wheel.disembark();
            if (!first || *first != "otters") return 4;
            if (!wheel.embark("foxes")) return 5;
            auto second = wheel.disembark();
            if (!second || *second != "herons") return 6;
            auto third = wheel.disembark();
            if (!third || *third != "foxes") return 7;
            if (wheel.disembark().has_value()) return 8;
            if (wheel.cabins_used() != 0U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { GondolaCabinWheel zero(0); (void)zero; } catch (const std::invalid_argument&) { threw = true; }
            if (!threw) return 1;
            GondolaCabinWheel wheel(3);
            if (wheel.disembark().has_value()) return 2;
            if (wheel.dock_cabin().has_value()) return 3;
            if (wheel.cabin_of("moles").has_value()) return 4;
            wheel.embark("moles");
            wheel.embark("badgers");
            wheel.embark("stoats");
            if (wheel.embark("hares")) return 5;
            if (wheel.cabins_used() != 3U) return 6;
            if (!wheel.dock_cabin() || *wheel.dock_cabin() != 0U) return 7;
            auto first = wheel.disembark();
            if (!first || *first != "moles") return 8;
            auto second = wheel.disembark();
            if (!second || *second != "badgers") return 9;
            wheel.embark("hares");
            wheel.embark("voles");
            if (!wheel.dock_cabin() || *wheel.dock_cabin() != 2U) return 10;
            if (!wheel.cabin_of("hares") || *wheel.cabin_of("hares") != 0U) return 11;
            if (!wheel.cabin_of("voles") || *wheel.cabin_of("voles") != 1U) return 12;
            if (!wheel.cabin_of("stoats") || *wheel.cabin_of("stoats") != 2U) return 13;
            if (wheel.cabin_of("moles").has_value()) return 14;
            auto third = wheel.disembark();
            if (!third || *third != "stoats") return 15;
            auto fourth = wheel.disembark();
            if (!fourth || *fourth != "hares") return 16;
            if (!wheel.dock_cabin() || *wheel.dock_cabin() != 1U) return 17;
            auto fifth = wheel.disembark();
            if (!fifth || *fifth != "voles") return 18;
            if (wheel.disembark().has_value()) return 19;
            return 0;
            """,
            "a fixed wheel of party cabins whose physical cabin slots and dock cursor stay observable across wraparound, reported through optional channels",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical cabin_of and dock_cabin values after embark/disembark sequences that wrap the wheel, false and nullopt channels, absent-party lookup, and zero-cabin rejection",
            "project-context string ring with cabin slots",
            "status-returning bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-turntable-vinyl-queue",
            "Turntable vinyl queue",
            "turntable",
            """
            class TurntableVinylQueue {
            public:
                explicit TurntableVinylQueue(std::size_t platters);
                bool cue(std::int64_t catalog);
                std::optional<std::int64_t> spin();
                bool cued_up(std::int64_t catalog) const;
                std::size_t cued() const;
                std::size_t platters() const;
                std::optional<std::size_t> platter_of(std::int64_t catalog) const;
                std::optional<std::size_t> spindle_slot() const;
            };
            """,
            """
            class TurntableVinylQueue {
            public:
                explicit TurntableVinylQueue(std::size_t platters);
                bool cue(std::int64_t catalog);
                std::optional<std::int64_t> spin();
                bool cued_up(std::int64_t catalog) const;
                std::size_t cued() const;
                std::size_t platters() const;
                std::optional<std::size_t> platter_of(std::int64_t catalog) const;
                std::optional<std::size_t> spindle_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t catalog = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            TurntableVinylQueue::TurntableVinylQueue(std::size_t platters) {
                if (platters == 0) throw std::invalid_argument("turntable needs at least one platter");
                cells_ = std::vector<Cell>(platters);
            }
            std::size_t TurntableVinylQueue::platters() const { return cells_.size(); }
            std::size_t TurntableVinylQueue::cued() const { return used_; }
            bool TurntableVinylQueue::cued_up(std::int64_t catalog) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.catalog == catalog) return true;
                }
                return false;
            }
            bool TurntableVinylQueue::cue(std::int64_t catalog) {
                if (used_ == cells_.size()) return false;
                cells_[next_].occupied = true;
                cells_[next_].catalog = catalog;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
                return true;
            }
            std::optional<std::int64_t> TurntableVinylQueue::spin() {
                if (used_ == 0) return std::nullopt;
                std::int64_t value = cells_[oldest_].catalog;
                cells_[oldest_].occupied = false;
                cells_[oldest_].catalog = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::optional<std::size_t> TurntableVinylQueue::spindle_slot() const {
                if (used_ == 0) return std::nullopt;
                return oldest_;
            }
            std::optional<std::size_t> TurntableVinylQueue::platter_of(std::int64_t catalog) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].catalog == catalog) return slot;
                }
                return std::nullopt;
            }
            """,
            """
            TurntableVinylQueue::TurntableVinylQueue(std::size_t platters) {
                if (platters == 0) throw std::invalid_argument("turntable needs at least one platter");
                cells_ = std::vector<Cell>(platters);
            }
            std::size_t TurntableVinylQueue::platters() const { return cells_.size(); }
            std::size_t TurntableVinylQueue::cued() const { return used_; }
            bool TurntableVinylQueue::cued_up(std::int64_t catalog) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].catalog == catalog) return true;
                }
                return false;
            }
            bool TurntableVinylQueue::cue(std::int64_t catalog) {
                if (used_ == cells_.size()) return false;
                cells_[used_].occupied = true;
                cells_[used_].catalog = catalog;
                ++used_;
                return true;
            }
            std::optional<std::int64_t> TurntableVinylQueue::spin() {
                if (used_ == 0) return std::nullopt;
                std::int64_t value = cells_[0].catalog;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].catalog = 0;
                --used_;
                return value;
            }
            std::optional<std::size_t> TurntableVinylQueue::spindle_slot() const {
                if (used_ == 0) return std::nullopt;
                return 0;
            }
            std::optional<std::size_t> TurntableVinylQueue::platter_of(std::int64_t catalog) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].catalog == catalog) return i;
                }
                return std::nullopt;
            }
            """,
            """
            TurntableVinylQueue deck(2);
            if (!deck.cue(1001)) return 1;
            if (!deck.cue(1002)) return 2;
            if (deck.cue(1003)) return 3;
            auto first = deck.spin();
            if (!first || *first != 1001) return 4;
            if (!deck.cue(1003)) return 5;
            auto second = deck.spin();
            if (!second || *second != 1002) return 6;
            auto third = deck.spin();
            if (!third || *third != 1003) return 7;
            if (deck.spin().has_value()) return 8;
            if (deck.cued() != 0U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { TurntableVinylQueue zero(0); (void)zero; } catch (const std::invalid_argument&) { threw = true; }
            if (!threw) return 1;
            TurntableVinylQueue deck(4);
            if (deck.spin().has_value()) return 2;
            if (deck.spindle_slot().has_value()) return 3;
            if (deck.platter_of(77).has_value()) return 4;
            deck.cue(111);
            deck.cue(222);
            deck.cue(333);
            deck.cue(444);
            if (deck.cue(555)) return 5;
            if (deck.cued() != 4U) return 6;
            if (!deck.spindle_slot() || *deck.spindle_slot() != 0U) return 7;
            auto first = deck.spin();
            if (!first || *first != 111) return 8;
            auto second = deck.spin();
            if (!second || *second != 222) return 9;
            deck.cue(555);
            deck.cue(666);
            if (!deck.spindle_slot() || *deck.spindle_slot() != 2U) return 10;
            if (!deck.platter_of(555) || *deck.platter_of(555) != 0U) return 11;
            if (!deck.platter_of(666) || *deck.platter_of(666) != 1U) return 12;
            if (!deck.platter_of(333) || *deck.platter_of(333) != 2U) return 13;
            if (!deck.platter_of(444) || *deck.platter_of(444) != 3U) return 14;
            if (deck.platter_of(111).has_value()) return 15;
            auto third = deck.spin();
            if (!third || *third != 333) return 16;
            auto fourth = deck.spin();
            if (!fourth || *fourth != 444) return 17;
            if (!deck.spindle_slot() || *deck.spindle_slot() != 0U) return 18;
            auto fifth = deck.spin();
            if (!fifth || *fifth != 555) return 19;
            auto sixth = deck.spin();
            if (!sixth || *sixth != 666) return 20;
            if (deck.spin().has_value()) return 21;
            return 0;
            """,
            "a fixed deck of catalog platters whose physical platter slots and spindle cursor stay observable across wraparound, reported through optional channels",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical platter_of and spindle_slot values after cue/spin sequences that wrap the deck, false and nullopt channels, absent-catalog lookup, and zero-platter rejection",
            "int64 status ring with platter slots",
            "status-returning bounded ring",
        ),
        c(
            "f26cbuf-lazy-susan-dishes",
            "Lazy susan dishes",
            "lazy_susan",
            """
            class LazySusanDishes {
            public:
                explicit LazySusanDishes(std::size_t trays);
                bool serve(const std::string& dish);
                std::optional<std::string> remove_dish();
                bool presented(const std::string& dish) const;
                std::size_t dishes() const;
                std::size_t trays() const;
                std::optional<std::size_t> tray_of(const std::string& dish) const;
                std::optional<std::size_t> clearing_tray() const;
            };
            """,
            """
            class LazySusanDishes {
            public:
                explicit LazySusanDishes(std::size_t trays);
                bool serve(const std::string& dish);
                std::optional<std::string> remove_dish();
                bool presented(const std::string& dish) const;
                std::size_t dishes() const;
                std::size_t trays() const;
                std::optional<std::size_t> tray_of(const std::string& dish) const;
                std::optional<std::size_t> clearing_tray() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string dish;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            LazySusanDishes::LazySusanDishes(std::size_t trays) {
                if (trays == 0) throw std::invalid_argument("susan needs at least one tray");
                cells_ = std::vector<Cell>(trays);
            }
            std::size_t LazySusanDishes::trays() const { return cells_.size(); }
            std::size_t LazySusanDishes::dishes() const { return used_; }
            bool LazySusanDishes::presented(const std::string& dish) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.dish == dish) return true;
                }
                return false;
            }
            bool LazySusanDishes::serve(const std::string& dish) {
                if (used_ == cells_.size()) return false;
                cells_[next_].occupied = true;
                cells_[next_].dish = dish;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
                return true;
            }
            std::optional<std::string> LazySusanDishes::remove_dish() {
                if (used_ == 0) return std::nullopt;
                std::string value = cells_[oldest_].dish;
                cells_[oldest_].occupied = false;
                cells_[oldest_].dish.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::optional<std::size_t> LazySusanDishes::clearing_tray() const {
                if (used_ == 0) return std::nullopt;
                return oldest_;
            }
            std::optional<std::size_t> LazySusanDishes::tray_of(const std::string& dish) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].dish == dish) return slot;
                }
                return std::nullopt;
            }
            """,
            """
            LazySusanDishes::LazySusanDishes(std::size_t trays) {
                if (trays == 0) throw std::invalid_argument("susan needs at least one tray");
                cells_ = std::vector<Cell>(trays);
            }
            std::size_t LazySusanDishes::trays() const { return cells_.size(); }
            std::size_t LazySusanDishes::dishes() const { return used_; }
            bool LazySusanDishes::presented(const std::string& dish) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].dish == dish) return true;
                }
                return false;
            }
            bool LazySusanDishes::serve(const std::string& dish) {
                if (used_ == cells_.size()) return false;
                cells_[used_].occupied = true;
                cells_[used_].dish = dish;
                ++used_;
                return true;
            }
            std::optional<std::string> LazySusanDishes::remove_dish() {
                if (used_ == 0) return std::nullopt;
                std::string value = cells_[0].dish;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].dish.clear();
                --used_;
                return value;
            }
            std::optional<std::size_t> LazySusanDishes::clearing_tray() const {
                if (used_ == 0) return std::nullopt;
                return 0;
            }
            std::optional<std::size_t> LazySusanDishes::tray_of(const std::string& dish) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].dish == dish) return i;
                }
                return std::nullopt;
            }
            """,
            """
            LazySusanDishes susan(2);
            if (!susan.serve("pilaf")) return 1;
            if (!susan.serve("tagine")) return 2;
            if (susan.serve("paella")) return 3;
            auto first = susan.remove_dish();
            if (!first || *first != "pilaf") return 4;
            if (!susan.serve("paella")) return 5;
            auto second = susan.remove_dish();
            if (!second || *second != "tagine") return 6;
            auto third = susan.remove_dish();
            if (!third || *third != "paella") return 7;
            if (susan.remove_dish().has_value()) return 8;
            if (susan.dishes() != 0U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { LazySusanDishes zero(0); (void)zero; } catch (const std::invalid_argument&) { threw = true; }
            if (!threw) return 1;
            LazySusanDishes susan(3);
            if (susan.remove_dish().has_value()) return 2;
            if (susan.clearing_tray().has_value()) return 3;
            if (susan.tray_of("risotto").has_value()) return 4;
            susan.serve("risotto");
            susan.serve("gnocchi");
            susan.serve("polenta");
            if (susan.serve("lasagna")) return 5;
            if (susan.dishes() != 3U) return 6;
            if (!susan.clearing_tray() || *susan.clearing_tray() != 0U) return 7;
            auto first = susan.remove_dish();
            if (!first || *first != "risotto") return 8;
            auto second = susan.remove_dish();
            if (!second || *second != "gnocchi") return 9;
            susan.serve("lasagna");
            susan.serve("ravioli");
            if (!susan.clearing_tray() || *susan.clearing_tray() != 2U) return 10;
            if (!susan.tray_of("lasagna") || *susan.tray_of("lasagna") != 0U) return 11;
            if (!susan.tray_of("ravioli") || *susan.tray_of("ravioli") != 1U) return 12;
            if (!susan.tray_of("polenta") || *susan.tray_of("polenta") != 2U) return 13;
            if (susan.tray_of("risotto").has_value()) return 14;
            auto third = susan.remove_dish();
            if (!third || *third != "polenta") return 15;
            auto fourth = susan.remove_dish();
            if (!fourth || *fourth != "lasagna") return 16;
            if (!susan.clearing_tray() || *susan.clearing_tray() != 1U) return 17;
            auto fifth = susan.remove_dish();
            if (!fifth || *fifth != "ravioli") return 18;
            if (susan.remove_dish().has_value()) return 19;
            return 0;
            """,
            "a fixed susan of dish trays whose physical tray slots and clearing cursor stay observable across wraparound, reported through optional channels",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical tray_of and clearing_tray values after serve/remove sequences that wrap the susan, false and nullopt channels, absent-dish lookup, and zero-tray rejection",
            "string status ring with tray slots",
            "status-returning bounded ring",
        ),
        c(
            "f26cbuf-roundabout-exit-slots",
            "Roundabout exit slots",
            "roundabout",
            """
            class RoundaboutExitSlots {
            public:
                explicit RoundaboutExitSlots(std::size_t exits);
                bool enter(std::int32_t plate);
                std::optional<std::int32_t> depart();
                bool circling(std::int32_t plate) const;
                std::size_t circulating() const;
                std::size_t exits() const;
                std::optional<std::size_t> slot_of(std::int32_t plate) const;
                std::optional<std::size_t> depart_slot() const;
            };
            """,
            """
            class RoundaboutExitSlots {
            public:
                explicit RoundaboutExitSlots(std::size_t exits);
                bool enter(std::int32_t plate);
                std::optional<std::int32_t> depart();
                bool circling(std::int32_t plate) const;
                std::size_t circulating() const;
                std::size_t exits() const;
                std::optional<std::size_t> slot_of(std::int32_t plate) const;
                std::optional<std::size_t> depart_slot() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t plate = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            RoundaboutExitSlots::RoundaboutExitSlots(std::size_t exits) {
                if (exits == 0) throw std::invalid_argument("roundabout needs at least one exit");
                cells_ = std::vector<Cell>(exits);
            }
            std::size_t RoundaboutExitSlots::exits() const { return cells_.size(); }
            std::size_t RoundaboutExitSlots::circulating() const { return used_; }
            bool RoundaboutExitSlots::circling(std::int32_t plate) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.plate == plate) return true;
                }
                return false;
            }
            bool RoundaboutExitSlots::enter(std::int32_t plate) {
                if (used_ == cells_.size()) return false;
                cells_[next_].occupied = true;
                cells_[next_].plate = plate;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
                return true;
            }
            std::optional<std::int32_t> RoundaboutExitSlots::depart() {
                if (used_ == 0) return std::nullopt;
                std::int32_t value = cells_[oldest_].plate;
                cells_[oldest_].occupied = false;
                cells_[oldest_].plate = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::optional<std::size_t> RoundaboutExitSlots::depart_slot() const {
                if (used_ == 0) return std::nullopt;
                return oldest_;
            }
            std::optional<std::size_t> RoundaboutExitSlots::slot_of(std::int32_t plate) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].plate == plate) return slot;
                }
                return std::nullopt;
            }
            """,
            """
            RoundaboutExitSlots::RoundaboutExitSlots(std::size_t exits) {
                if (exits == 0) throw std::invalid_argument("roundabout needs at least one exit");
                cells_ = std::vector<Cell>(exits);
            }
            std::size_t RoundaboutExitSlots::exits() const { return cells_.size(); }
            std::size_t RoundaboutExitSlots::circulating() const { return used_; }
            bool RoundaboutExitSlots::circling(std::int32_t plate) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].plate == plate) return true;
                }
                return false;
            }
            bool RoundaboutExitSlots::enter(std::int32_t plate) {
                if (used_ == cells_.size()) return false;
                cells_[used_].occupied = true;
                cells_[used_].plate = plate;
                ++used_;
                return true;
            }
            std::optional<std::int32_t> RoundaboutExitSlots::depart() {
                if (used_ == 0) return std::nullopt;
                std::int32_t value = cells_[0].plate;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].plate = 0;
                --used_;
                return value;
            }
            std::optional<std::size_t> RoundaboutExitSlots::depart_slot() const {
                if (used_ == 0) return std::nullopt;
                return 0;
            }
            std::optional<std::size_t> RoundaboutExitSlots::slot_of(std::int32_t plate) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].plate == plate) return i;
                }
                return std::nullopt;
            }
            """,
            """
            RoundaboutExitSlots circle(2);
            if (!circle.enter(410)) return 1;
            if (!circle.enter(420)) return 2;
            if (circle.enter(430)) return 3;
            auto first = circle.depart();
            if (!first || *first != 410) return 4;
            if (!circle.enter(430)) return 5;
            auto second = circle.depart();
            if (!second || *second != 420) return 6;
            auto third = circle.depart();
            if (!third || *third != 430) return 7;
            if (circle.depart().has_value()) return 8;
            if (circle.circulating() != 0U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { RoundaboutExitSlots zero(0); (void)zero; } catch (const std::invalid_argument&) { threw = true; }
            if (!threw) return 1;
            RoundaboutExitSlots circle(4);
            if (circle.depart().has_value()) return 2;
            if (circle.depart_slot().has_value()) return 3;
            if (circle.slot_of(99).has_value()) return 4;
            circle.enter(11);
            circle.enter(22);
            circle.enter(33);
            circle.enter(44);
            if (circle.enter(55)) return 5;
            if (circle.circulating() != 4U) return 6;
            if (!circle.depart_slot() || *circle.depart_slot() != 0U) return 7;
            auto first = circle.depart();
            if (!first || *first != 11) return 8;
            auto second = circle.depart();
            if (!second || *second != 22) return 9;
            circle.enter(55);
            circle.enter(66);
            if (!circle.depart_slot() || *circle.depart_slot() != 2U) return 10;
            if (!circle.slot_of(55) || *circle.slot_of(55) != 0U) return 11;
            if (!circle.slot_of(66) || *circle.slot_of(66) != 1U) return 12;
            if (!circle.slot_of(33) || *circle.slot_of(33) != 2U) return 13;
            if (!circle.slot_of(44) || *circle.slot_of(44) != 3U) return 14;
            if (circle.slot_of(11).has_value()) return 15;
            auto third = circle.depart();
            if (!third || *third != 33) return 16;
            auto fourth = circle.depart();
            if (!fourth || *fourth != 44) return 17;
            if (!circle.depart_slot() || *circle.depart_slot() != 0U) return 18;
            auto fifth = circle.depart();
            if (!fifth || *fifth != 55) return 19;
            auto sixth = circle.depart();
            if (!sixth || *sixth != 66) return 20;
            if (circle.depart().has_value()) return 21;
            return 0;
            """,
            "a fixed circle of plate exits whose physical slots and depart cursor stay observable across wraparound, reported through optional channels",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical slot_of and depart_slot values after enter/depart sequences that wrap the circle, false and nullopt channels, absent-plate lookup, and zero-exit rejection",
            "project-context status ring with circulation slots",
            "status-returning bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-observation-wheel-pods",
            "Observation wheel pods",
            "observation_wheel",
            """
            class ObservationWheelPods {
            public:
                explicit ObservationWheelPods(std::size_t pods);
                bool load_pod(std::int64_t ticket);
                std::optional<std::int64_t> unload_pod();
                bool seated(std::int64_t ticket) const;
                std::size_t loaded() const;
                std::size_t pods() const;
                std::optional<std::size_t> pod_of(std::int64_t ticket) const;
                std::optional<std::size_t> dock_pod() const;
            };
            """,
            """
            class ObservationWheelPods {
            public:
                explicit ObservationWheelPods(std::size_t pods);
                bool load_pod(std::int64_t ticket);
                std::optional<std::int64_t> unload_pod();
                bool seated(std::int64_t ticket) const;
                std::size_t loaded() const;
                std::size_t pods() const;
                std::optional<std::size_t> pod_of(std::int64_t ticket) const;
                std::optional<std::size_t> dock_pod() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t ticket = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            ObservationWheelPods::ObservationWheelPods(std::size_t pods) {
                if (pods == 0) throw std::invalid_argument("wheel needs at least one pod");
                cells_ = std::vector<Cell>(pods);
            }
            std::size_t ObservationWheelPods::pods() const { return cells_.size(); }
            std::size_t ObservationWheelPods::loaded() const { return used_; }
            bool ObservationWheelPods::seated(std::int64_t ticket) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.ticket == ticket) return true;
                }
                return false;
            }
            bool ObservationWheelPods::load_pod(std::int64_t ticket) {
                if (used_ == cells_.size()) return false;
                cells_[next_].occupied = true;
                cells_[next_].ticket = ticket;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
                return true;
            }
            std::optional<std::int64_t> ObservationWheelPods::unload_pod() {
                if (used_ == 0) return std::nullopt;
                std::int64_t value = cells_[oldest_].ticket;
                cells_[oldest_].occupied = false;
                cells_[oldest_].ticket = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::optional<std::size_t> ObservationWheelPods::dock_pod() const {
                if (used_ == 0) return std::nullopt;
                return oldest_;
            }
            std::optional<std::size_t> ObservationWheelPods::pod_of(std::int64_t ticket) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].ticket == ticket) return slot;
                }
                return std::nullopt;
            }
            """,
            """
            ObservationWheelPods::ObservationWheelPods(std::size_t pods) {
                if (pods == 0) throw std::invalid_argument("wheel needs at least one pod");
                cells_ = std::vector<Cell>(pods);
            }
            std::size_t ObservationWheelPods::pods() const { return cells_.size(); }
            std::size_t ObservationWheelPods::loaded() const { return used_; }
            bool ObservationWheelPods::seated(std::int64_t ticket) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].ticket == ticket) return true;
                }
                return false;
            }
            bool ObservationWheelPods::load_pod(std::int64_t ticket) {
                if (used_ == cells_.size()) return false;
                cells_[used_].occupied = true;
                cells_[used_].ticket = ticket;
                ++used_;
                return true;
            }
            std::optional<std::int64_t> ObservationWheelPods::unload_pod() {
                if (used_ == 0) return std::nullopt;
                std::int64_t value = cells_[0].ticket;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].ticket = 0;
                --used_;
                return value;
            }
            std::optional<std::size_t> ObservationWheelPods::dock_pod() const {
                if (used_ == 0) return std::nullopt;
                return 0;
            }
            std::optional<std::size_t> ObservationWheelPods::pod_of(std::int64_t ticket) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].ticket == ticket) return i;
                }
                return std::nullopt;
            }
            """,
            """
            ObservationWheelPods wheel(2);
            if (!wheel.load_pod(7001)) return 1;
            if (!wheel.load_pod(7002)) return 2;
            if (wheel.load_pod(7003)) return 3;
            auto first = wheel.unload_pod();
            if (!first || *first != 7001) return 4;
            if (!wheel.load_pod(7003)) return 5;
            auto second = wheel.unload_pod();
            if (!second || *second != 7002) return 6;
            auto third = wheel.unload_pod();
            if (!third || *third != 7003) return 7;
            if (wheel.unload_pod().has_value()) return 8;
            if (wheel.loaded() != 0U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { ObservationWheelPods zero(0); (void)zero; } catch (const std::invalid_argument&) { threw = true; }
            if (!threw) return 1;
            ObservationWheelPods wheel(3);
            if (wheel.unload_pod().has_value()) return 2;
            if (wheel.dock_pod().has_value()) return 3;
            if (wheel.pod_of(88).has_value()) return 4;
            wheel.load_pod(8801);
            wheel.load_pod(8802);
            wheel.load_pod(8803);
            if (wheel.load_pod(8804)) return 5;
            if (wheel.loaded() != 3U) return 6;
            if (!wheel.dock_pod() || *wheel.dock_pod() != 0U) return 7;
            auto first = wheel.unload_pod();
            if (!first || *first != 8801) return 8;
            auto second = wheel.unload_pod();
            if (!second || *second != 8802) return 9;
            wheel.load_pod(8804);
            wheel.load_pod(8805);
            if (!wheel.dock_pod() || *wheel.dock_pod() != 2U) return 10;
            if (!wheel.pod_of(8804) || *wheel.pod_of(8804) != 0U) return 11;
            if (!wheel.pod_of(8805) || *wheel.pod_of(8805) != 1U) return 12;
            if (!wheel.pod_of(8803) || *wheel.pod_of(8803) != 2U) return 13;
            if (wheel.pod_of(8801).has_value()) return 14;
            auto third = wheel.unload_pod();
            if (!third || *third != 8803) return 15;
            auto fourth = wheel.unload_pod();
            if (!fourth || *fourth != 8804) return 16;
            if (!wheel.dock_pod() || *wheel.dock_pod() != 1U) return 17;
            auto fifth = wheel.unload_pod();
            if (!fifth || *fifth != 8805) return 18;
            if (wheel.unload_pod().has_value()) return 19;
            return 0;
            """,
            "a fixed wheel of ticket pods whose physical pod slots and dock cursor stay observable across wraparound, reported through optional channels",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical pod_of and dock_pod values after load/unload sequences that wrap the wheel, false and nullopt channels, absent-ticket lookup, and zero-pod rejection",
            "int64 status ring with pod slots",
            "status-returning bounded ring",
        ),
        c(
            "f26cbuf-paddlewheel-float-ring",
            "Paddlewheel float ring",
            "paddlewheel",
            """
            class PaddlewheelFloatRing {
            public:
                explicit PaddlewheelFloatRing(std::size_t floats);
                bool lash(std::int32_t cargo);
                std::optional<std::int32_t> unlash();
                bool lashed(std::int32_t cargo) const;
                std::size_t floats_used() const;
                std::size_t floats() const;
                std::optional<std::size_t> float_of(std::int32_t cargo) const;
                std::optional<std::size_t> dock_float() const;
            };
            """,
            """
            class PaddlewheelFloatRing {
            public:
                explicit PaddlewheelFloatRing(std::size_t floats);
                bool lash(std::int32_t cargo);
                std::optional<std::int32_t> unlash();
                bool lashed(std::int32_t cargo) const;
                std::size_t floats_used() const;
                std::size_t floats() const;
                std::optional<std::size_t> float_of(std::int32_t cargo) const;
                std::optional<std::size_t> dock_float() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t cargo = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            PaddlewheelFloatRing::PaddlewheelFloatRing(std::size_t floats) {
                if (floats == 0) throw std::invalid_argument("paddlewheel needs at least one float");
                cells_ = std::vector<Cell>(floats);
            }
            std::size_t PaddlewheelFloatRing::floats() const { return cells_.size(); }
            std::size_t PaddlewheelFloatRing::floats_used() const { return used_; }
            bool PaddlewheelFloatRing::lashed(std::int32_t cargo) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.cargo == cargo) return true;
                }
                return false;
            }
            bool PaddlewheelFloatRing::lash(std::int32_t cargo) {
                if (used_ == cells_.size()) return false;
                cells_[next_].occupied = true;
                cells_[next_].cargo = cargo;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
                return true;
            }
            std::optional<std::int32_t> PaddlewheelFloatRing::unlash() {
                if (used_ == 0) return std::nullopt;
                std::int32_t value = cells_[oldest_].cargo;
                cells_[oldest_].occupied = false;
                cells_[oldest_].cargo = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::optional<std::size_t> PaddlewheelFloatRing::dock_float() const {
                if (used_ == 0) return std::nullopt;
                return oldest_;
            }
            std::optional<std::size_t> PaddlewheelFloatRing::float_of(std::int32_t cargo) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].cargo == cargo) return slot;
                }
                return std::nullopt;
            }
            """,
            """
            PaddlewheelFloatRing::PaddlewheelFloatRing(std::size_t floats) {
                if (floats == 0) throw std::invalid_argument("paddlewheel needs at least one float");
                cells_ = std::vector<Cell>(floats);
            }
            std::size_t PaddlewheelFloatRing::floats() const { return cells_.size(); }
            std::size_t PaddlewheelFloatRing::floats_used() const { return used_; }
            bool PaddlewheelFloatRing::lashed(std::int32_t cargo) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].cargo == cargo) return true;
                }
                return false;
            }
            bool PaddlewheelFloatRing::lash(std::int32_t cargo) {
                if (used_ == cells_.size()) return false;
                cells_[used_].occupied = true;
                cells_[used_].cargo = cargo;
                ++used_;
                return true;
            }
            std::optional<std::int32_t> PaddlewheelFloatRing::unlash() {
                if (used_ == 0) return std::nullopt;
                std::int32_t value = cells_[0].cargo;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].cargo = 0;
                --used_;
                return value;
            }
            std::optional<std::size_t> PaddlewheelFloatRing::dock_float() const {
                if (used_ == 0) return std::nullopt;
                return 0;
            }
            std::optional<std::size_t> PaddlewheelFloatRing::float_of(std::int32_t cargo) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].cargo == cargo) return i;
                }
                return std::nullopt;
            }
            """,
            """
            PaddlewheelFloatRing wheel(2);
            if (!wheel.lash(31)) return 1;
            if (!wheel.lash(32)) return 2;
            if (wheel.lash(33)) return 3;
            auto first = wheel.unlash();
            if (!first || *first != 31) return 4;
            if (!wheel.lash(33)) return 5;
            auto second = wheel.unlash();
            if (!second || *second != 32) return 6;
            auto third = wheel.unlash();
            if (!third || *third != 33) return 7;
            if (wheel.unlash().has_value()) return 8;
            if (wheel.floats_used() != 0U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { PaddlewheelFloatRing zero(0); (void)zero; } catch (const std::invalid_argument&) { threw = true; }
            if (!threw) return 1;
            PaddlewheelFloatRing wheel(4);
            if (wheel.unlash().has_value()) return 2;
            if (wheel.dock_float().has_value()) return 3;
            if (wheel.float_of(64).has_value()) return 4;
            wheel.lash(64);
            wheel.lash(128);
            wheel.lash(192);
            wheel.lash(256);
            if (wheel.lash(320)) return 5;
            if (wheel.floats_used() != 4U) return 6;
            if (!wheel.dock_float() || *wheel.dock_float() != 0U) return 7;
            auto first = wheel.unlash();
            if (!first || *first != 64) return 8;
            auto second = wheel.unlash();
            if (!second || *second != 128) return 9;
            wheel.lash(320);
            wheel.lash(384);
            if (!wheel.dock_float() || *wheel.dock_float() != 2U) return 10;
            if (!wheel.float_of(320) || *wheel.float_of(320) != 0U) return 11;
            if (!wheel.float_of(384) || *wheel.float_of(384) != 1U) return 12;
            if (!wheel.float_of(192) || *wheel.float_of(192) != 2U) return 13;
            if (!wheel.float_of(256) || *wheel.float_of(256) != 3U) return 14;
            if (wheel.float_of(64).has_value()) return 15;
            auto third = wheel.unlash();
            if (!third || *third != 192) return 16;
            auto fourth = wheel.unlash();
            if (!fourth || *fourth != 256) return 17;
            if (!wheel.dock_float() || *wheel.dock_float() != 0U) return 18;
            auto fifth = wheel.unlash();
            if (!fifth || *fifth != 320) return 19;
            auto sixth = wheel.unlash();
            if (!sixth || *sixth != 384) return 20;
            if (wheel.unlash().has_value()) return 21;
            return 0;
            """,
            "a fixed wheel of cargo floats whose physical float slots and dock cursor stay observable across wraparound, reported through optional channels",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical float_of and dock_float values after lash/unlash sequences that wrap the wheel, false and nullopt channels, absent-cargo lookup, and zero-float rejection",
            "river-domain status ring with float slots",
            "status-returning bounded ring",
        ),
        c(
            "f26cbuf-turret-ring-notches",
            "Turret ring notches",
            "turret_ring",
            """
            class TurretRingNotches {
            public:
                explicit TurretRingNotches(std::size_t notches);
                bool ram(const std::string& shell);
                std::optional<std::string> extract();
                bool chambered(const std::string& shell) const;
                std::size_t loaded_notches() const;
                std::size_t notches() const;
                std::optional<std::size_t> notch_of(const std::string& shell) const;
                std::optional<std::size_t> breech_notch() const;
            };
            """,
            """
            class TurretRingNotches {
            public:
                explicit TurretRingNotches(std::size_t notches);
                bool ram(const std::string& shell);
                std::optional<std::string> extract();
                bool chambered(const std::string& shell) const;
                std::size_t loaded_notches() const;
                std::size_t notches() const;
                std::optional<std::size_t> notch_of(const std::string& shell) const;
                std::optional<std::size_t> breech_notch() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string shell;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            TurretRingNotches::TurretRingNotches(std::size_t notches) {
                if (notches == 0) throw std::invalid_argument("turret needs at least one notch");
                cells_ = std::vector<Cell>(notches);
            }
            std::size_t TurretRingNotches::notches() const { return cells_.size(); }
            std::size_t TurretRingNotches::loaded_notches() const { return used_; }
            bool TurretRingNotches::chambered(const std::string& shell) const {
                for (const Cell& cell : cells_) {
                    if (cell.occupied && cell.shell == shell) return true;
                }
                return false;
            }
            bool TurretRingNotches::ram(const std::string& shell) {
                if (used_ == cells_.size()) return false;
                cells_[next_].occupied = true;
                cells_[next_].shell = shell;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
                return true;
            }
            std::optional<std::string> TurretRingNotches::extract() {
                if (used_ == 0) return std::nullopt;
                std::string value = cells_[oldest_].shell;
                cells_[oldest_].occupied = false;
                cells_[oldest_].shell.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::optional<std::size_t> TurretRingNotches::breech_notch() const {
                if (used_ == 0) return std::nullopt;
                return oldest_;
            }
            std::optional<std::size_t> TurretRingNotches::notch_of(const std::string& shell) const {
                for (std::size_t offset = 0; offset < used_; ++offset) {
                    std::size_t slot = (oldest_ + offset) % cells_.size();
                    if (cells_[slot].shell == shell) return slot;
                }
                return std::nullopt;
            }
            """,
            """
            TurretRingNotches::TurretRingNotches(std::size_t notches) {
                if (notches == 0) throw std::invalid_argument("turret needs at least one notch");
                cells_ = std::vector<Cell>(notches);
            }
            std::size_t TurretRingNotches::notches() const { return cells_.size(); }
            std::size_t TurretRingNotches::loaded_notches() const { return used_; }
            bool TurretRingNotches::chambered(const std::string& shell) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].shell == shell) return true;
                }
                return false;
            }
            bool TurretRingNotches::ram(const std::string& shell) {
                if (used_ == cells_.size()) return false;
                cells_[used_].occupied = true;
                cells_[used_].shell = shell;
                ++used_;
                return true;
            }
            std::optional<std::string> TurretRingNotches::extract() {
                if (used_ == 0) return std::nullopt;
                std::string value = cells_[0].shell;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].shell.clear();
                --used_;
                return value;
            }
            std::optional<std::size_t> TurretRingNotches::breech_notch() const {
                if (used_ == 0) return std::nullopt;
                return 0;
            }
            std::optional<std::size_t> TurretRingNotches::notch_of(const std::string& shell) const {
                for (std::size_t i = 0; i < used_; ++i) {
                    if (cells_[i].shell == shell) return i;
                }
                return std::nullopt;
            }
            """,
            """
            TurretRingNotches turret(2);
            if (!turret.ram("ap")) return 1;
            if (!turret.ram("he")) return 2;
            if (turret.ram("smoke")) return 3;
            auto first = turret.extract();
            if (!first || *first != "ap") return 4;
            if (!turret.ram("smoke")) return 5;
            auto second = turret.extract();
            if (!second || *second != "he") return 6;
            auto third = turret.extract();
            if (!third || *third != "smoke") return 7;
            if (turret.extract().has_value()) return 8;
            if (turret.loaded_notches() != 0U) return 9;
            return 0;
            """,
            """
            bool threw = false;
            try { TurretRingNotches zero(0); (void)zero; } catch (const std::invalid_argument&) { threw = true; }
            if (!threw) return 1;
            TurretRingNotches turret(3);
            if (turret.extract().has_value()) return 2;
            if (turret.breech_notch().has_value()) return 3;
            if (turret.notch_of("ap").has_value()) return 4;
            turret.ram("ap");
            turret.ram("he");
            turret.ram("smoke");
            if (turret.ram("flare")) return 5;
            if (turret.loaded_notches() != 3U) return 6;
            if (!turret.breech_notch() || *turret.breech_notch() != 0U) return 7;
            auto first = turret.extract();
            if (!first || *first != "ap") return 8;
            auto second = turret.extract();
            if (!second || *second != "he") return 9;
            turret.ram("flare");
            turret.ram("slug");
            if (!turret.breech_notch() || *turret.breech_notch() != 2U) return 10;
            if (!turret.notch_of("flare") || *turret.notch_of("flare") != 0U) return 11;
            if (!turret.notch_of("slug") || *turret.notch_of("slug") != 1U) return 12;
            if (!turret.notch_of("smoke") || *turret.notch_of("smoke") != 2U) return 13;
            if (turret.notch_of("ap").has_value()) return 14;
            auto third = turret.extract();
            if (!third || *third != "smoke") return 15;
            auto fourth = turret.extract();
            if (!fourth || *fourth != "flare") return 16;
            if (!turret.breech_notch() || *turret.breech_notch() != 1U) return 17;
            auto fifth = turret.extract();
            if (!fifth || *fifth != "slug") return 18;
            if (turret.extract().has_value()) return 19;
            return 0;
            """,
            "a fixed turret of shell notches whose physical notch slots and breech cursor stay observable across wraparound, reported through optional channels",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical notch_of and breech_notch values after ram/extract sequences that wrap the turret, false and nullopt channels, absent-shell lookup, and zero-notch rejection",
            "string status ring with notch slots",
            "status-returning bounded ring",
        ),
        c(
            "f26cbuf-band-organ-barrel",
            "Band organ barrel",
            "band_organ",
            """
            class BarrelConfigError : public std::invalid_argument {
            public:
                explicit BarrelConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BarrelEmptyError : public std::runtime_error {
            public:
                explicit BarrelEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class BarrelFullError : public std::logic_error {
            public:
                explicit BarrelFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BandOrganBarrel {
            public:
                explicit BandOrganBarrel(std::size_t barrel_cells);
                void pin(std::int32_t note);
                std::int32_t play();
                std::size_t pinned() const;
                std::size_t barrel_cells() const;
                std::string barrel_map() const;
            };
            """,
            """
            class BarrelConfigError : public std::invalid_argument {
            public:
                explicit BarrelConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BarrelEmptyError : public std::runtime_error {
            public:
                explicit BarrelEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class BarrelFullError : public std::logic_error {
            public:
                explicit BarrelFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BandOrganBarrel {
            public:
                explicit BandOrganBarrel(std::size_t barrel_cells);
                void pin(std::int32_t note);
                std::int32_t play();
                std::size_t pinned() const;
                std::size_t barrel_cells() const;
                std::string barrel_map() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t note = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            BandOrganBarrel::BandOrganBarrel(std::size_t barrel_cells) {
                if (barrel_cells == 0) throw BarrelConfigError("barrel needs at least one cell");
                cells_ = std::vector<Cell>(barrel_cells);
            }
            std::size_t BandOrganBarrel::barrel_cells() const { return cells_.size(); }
            std::size_t BandOrganBarrel::pinned() const { return used_; }
            void BandOrganBarrel::pin(std::int32_t note) {
                if (used_ == cells_.size()) throw BarrelFullError("barrel is full");
                cells_[next_].occupied = true;
                cells_[next_].note = note;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t BandOrganBarrel::play() {
                if (used_ == 0) throw BarrelEmptyError("barrel is empty");
                std::int32_t value = cells_[oldest_].note;
                cells_[oldest_].occupied = false;
                cells_[oldest_].note = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::string BandOrganBarrel::barrel_map() const {
                std::string out = "[";
                for (const Cell& cell : cells_) {
                    out += cell.occupied ? std::to_string(cell.note) : ".";
                }
                out += "] play@" + std::to_string(oldest_) + " pin@" + std::to_string(next_);
                out += " used=" + std::to_string(used_) + "/" + std::to_string(cells_.size());
                return out;
            }
            """,
            """
            BandOrganBarrel::BandOrganBarrel(std::size_t barrel_cells) {
                if (barrel_cells == 0) throw BarrelConfigError("barrel needs at least one cell");
                cells_ = std::vector<Cell>(barrel_cells);
            }
            std::size_t BandOrganBarrel::barrel_cells() const { return cells_.size(); }
            std::size_t BandOrganBarrel::pinned() const { return used_; }
            void BandOrganBarrel::pin(std::int32_t note) {
                if (used_ == cells_.size()) throw BarrelFullError("barrel is full");
                cells_[used_].occupied = true;
                cells_[used_].note = note;
                ++used_;
            }
            std::int32_t BandOrganBarrel::play() {
                if (used_ == 0) throw BarrelEmptyError("barrel is empty");
                std::int32_t value = cells_[0].note;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].note = 0;
                --used_;
                return value;
            }
            std::string BandOrganBarrel::barrel_map() const {
                std::string out = "<";
                for (std::size_t i = 0; i < used_; ++i) {
                    if (i != 0) out += ",";
                    out += std::to_string(cells_[i].note);
                }
                out += ">";
                return out;
            }
            """,
            """
            BandOrganBarrel barrel(3);
            barrel.pin(4);
            barrel.pin(8);
            if (barrel.pinned() != 2U) return 1;
            if (barrel.play() != 4) return 2;
            barrel.pin(15);
            barrel.pin(16);
            if (barrel.play() != 8) return 3;
            if (barrel.play() != 15) return 4;
            if (barrel.play() != 16) return 5;
            if (barrel.pinned() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { BandOrganBarrel zero(0); (void)zero; } catch (const BarrelConfigError&) { threw = true; }
            if (!threw) return 1;
            BandOrganBarrel barrel(3);
            if (barrel.barrel_map() != "[...] play@0 pin@0 used=0/3") return 2;
            threw = false;
            try { barrel.play(); } catch (const BarrelEmptyError&) { threw = true; }
            if (!threw) return 3;
            barrel.pin(4);
            barrel.pin(8);
            if (barrel.barrel_map() != "[48.] play@0 pin@2 used=2/3") return 4;
            barrel.pin(15);
            if (barrel.barrel_map() != "[4815] play@0 pin@0 used=3/3") return 5;
            threw = false;
            try { barrel.pin(23); } catch (const BarrelFullError&) { threw = true; }
            if (!threw) return 6;
            if (barrel.pinned() != 3U) return 7;
            if (barrel.play() != 4) return 8;
            if (barrel.barrel_map() != "[.815] play@1 pin@0 used=2/3") return 9;
            barrel.pin(23);
            if (barrel.barrel_map() != "[23815] play@1 pin@1 used=3/3") return 10;
            if (barrel.play() != 8) return 11;
            if (barrel.barrel_map() != "[23.15] play@2 pin@1 used=2/3") return 12;
            if (barrel.play() != 15) return 13;
            if (barrel.barrel_map() != "[23..] play@0 pin@1 used=1/3") return 14;
            if (barrel.play() != 23) return 15;
            if (barrel.barrel_map() != "[...] play@1 pin@1 used=0/3") return 16;
            return 0;
            """,
            "a fixed barrel of note cells whose exact slot map with gaps and cursor positions stays observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a compact list rendering that hides physical gaps",
            "exact barrel_map strings after pin/play sequences that wrap the barrel, showing freed cells and wrapped cursors, full and empty channels, and zero-cell rejection",
            "exact physical-layout string rendering after wraparound",
            "layout-rendering bounded ring with exact snapshot output",
        ),
        c(
            "f26cbuf-player-piano-roll",
            "Player piano roll",
            "player_piano",
            """
            class RollConfigError : public std::invalid_argument {
            public:
                explicit RollConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RollEmptyError : public std::runtime_error {
            public:
                explicit RollEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class RollFullError : public std::logic_error {
            public:
                explicit RollFullError(const std::string& message) : std::logic_error(message) {}
            };
            class PlayerPianoRoll {
            public:
                explicit PlayerPianoRoll(std::size_t roll_cells);
                void punch(const std::string& note);
                std::string pedal();
                std::size_t holes() const;
                std::size_t roll_cells() const;
                std::string roll_score() const;
            };
            """,
            """
            class RollConfigError : public std::invalid_argument {
            public:
                explicit RollConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RollEmptyError : public std::runtime_error {
            public:
                explicit RollEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class RollFullError : public std::logic_error {
            public:
                explicit RollFullError(const std::string& message) : std::logic_error(message) {}
            };
            class PlayerPianoRoll {
            public:
                explicit PlayerPianoRoll(std::size_t roll_cells);
                void punch(const std::string& note);
                std::string pedal();
                std::size_t holes() const;
                std::size_t roll_cells() const;
                std::string roll_score() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string note;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            PlayerPianoRoll::PlayerPianoRoll(std::size_t roll_cells) {
                if (roll_cells == 0) throw RollConfigError("roll needs at least one cell");
                cells_ = std::vector<Cell>(roll_cells);
            }
            std::size_t PlayerPianoRoll::roll_cells() const { return cells_.size(); }
            std::size_t PlayerPianoRoll::holes() const { return used_; }
            void PlayerPianoRoll::punch(const std::string& note) {
                if (used_ == cells_.size()) throw RollFullError("roll is full");
                cells_[next_].occupied = true;
                cells_[next_].note = note;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string PlayerPianoRoll::pedal() {
                if (used_ == 0) throw RollEmptyError("roll is empty");
                std::string value = cells_[oldest_].note;
                cells_[oldest_].occupied = false;
                cells_[oldest_].note.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::string PlayerPianoRoll::roll_score() const {
                std::string out = "{";
                for (std::size_t i = 0; i < cells_.size(); ++i) {
                    if (i != 0) out += ",";
                    out += cells_[i].occupied ? cells_[i].note : ".";
                }
                out += "} pedal@" + std::to_string(oldest_) + " punch@" + std::to_string(next_);
                out += " used=" + std::to_string(used_) + "/" + std::to_string(cells_.size());
                return out;
            }
            """,
            """
            PlayerPianoRoll::PlayerPianoRoll(std::size_t roll_cells) {
                if (roll_cells == 0) throw RollConfigError("roll needs at least one cell");
                cells_ = std::vector<Cell>(roll_cells);
            }
            std::size_t PlayerPianoRoll::roll_cells() const { return cells_.size(); }
            std::size_t PlayerPianoRoll::holes() const { return used_; }
            void PlayerPianoRoll::punch(const std::string& note) {
                if (used_ == cells_.size()) throw RollFullError("roll is full");
                cells_[used_].occupied = true;
                cells_[used_].note = note;
                ++used_;
            }
            std::string PlayerPianoRoll::pedal() {
                if (used_ == 0) throw RollEmptyError("roll is empty");
                std::string value = cells_[0].note;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].note.clear();
                --used_;
                return value;
            }
            std::string PlayerPianoRoll::roll_score() const {
                std::string out = "<<";
                for (std::size_t i = 0; i < used_; ++i) {
                    if (i != 0) out += "|";
                    out += cells_[i].note;
                }
                out += ">>";
                return out;
            }
            """,
            """
            PlayerPianoRoll roll(3);
            roll.punch("do");
            roll.punch("re");
            if (roll.holes() != 2U) return 1;
            if (roll.pedal() != "do") return 2;
            roll.punch("mi");
            roll.punch("fa");
            if (roll.pedal() != "re") return 3;
            if (roll.pedal() != "mi") return 4;
            if (roll.pedal() != "fa") return 5;
            if (roll.holes() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { PlayerPianoRoll zero(0); (void)zero; } catch (const RollConfigError&) { threw = true; }
            if (!threw) return 1;
            PlayerPianoRoll roll(3);
            if (roll.roll_score() != "{.,.,.} pedal@0 punch@0 used=0/3") return 2;
            threw = false;
            try { roll.pedal(); } catch (const RollEmptyError&) { threw = true; }
            if (!threw) return 3;
            roll.punch("do");
            roll.punch("re");
            if (roll.roll_score() != "{do,re,.} pedal@0 punch@2 used=2/3") return 4;
            roll.punch("mi");
            if (roll.roll_score() != "{do,re,mi} pedal@0 punch@0 used=3/3") return 5;
            threw = false;
            try { roll.punch("fa"); } catch (const RollFullError&) { threw = true; }
            if (!threw) return 6;
            if (roll.holes() != 3U) return 7;
            if (roll.pedal() != "do") return 8;
            if (roll.roll_score() != "{.,re,mi} pedal@1 punch@0 used=2/3") return 9;
            roll.punch("fa");
            if (roll.roll_score() != "{fa,re,mi} pedal@1 punch@1 used=3/3") return 10;
            if (roll.pedal() != "re") return 11;
            if (roll.roll_score() != "{fa,.,mi} pedal@2 punch@1 used=2/3") return 12;
            if (roll.pedal() != "mi") return 13;
            if (roll.roll_score() != "{fa,.,.} pedal@0 punch@1 used=1/3") return 14;
            if (roll.pedal() != "fa") return 15;
            if (roll.roll_score() != "{.,.,.} pedal@1 punch@1 used=0/3") return 16;
            return 0;
            """,
            "a fixed roll of note holes whose exact slot score with gaps and cursor positions stays observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a compact list rendering that hides physical gaps",
            "exact roll_score strings after punch/pedal sequences that wrap the roll, showing freed cells and wrapped cursors, full and empty channels, and zero-cell rejection",
            "project-context exact slot-map rendering with string notes",
            "layout-rendering bounded ring with exact snapshot output",
            project_support=True,
        ),
        c(
            "f26cbuf-telegraph-tape-loop",
            "Telegraph tape loop",
            "telegraph",
            """
            class TapeConfigError : public std::invalid_argument {
            public:
                explicit TapeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TapeEmptyError : public std::runtime_error {
            public:
                explicit TapeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TapeFullError : public std::logic_error {
            public:
                explicit TapeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TelegraphTapeLoop {
            public:
                explicit TelegraphTapeLoop(std::size_t tape_cells);
                void stamp(std::int32_t mark);
                std::int32_t send();
                std::size_t marks() const;
                std::size_t tape_cells() const;
                std::string tape_trace() const;
            };
            """,
            """
            class TapeConfigError : public std::invalid_argument {
            public:
                explicit TapeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TapeEmptyError : public std::runtime_error {
            public:
                explicit TapeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TapeFullError : public std::logic_error {
            public:
                explicit TapeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TelegraphTapeLoop {
            public:
                explicit TelegraphTapeLoop(std::size_t tape_cells);
                void stamp(std::int32_t mark);
                std::int32_t send();
                std::size_t marks() const;
                std::size_t tape_cells() const;
                std::string tape_trace() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t mark = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            TelegraphTapeLoop::TelegraphTapeLoop(std::size_t tape_cells) {
                if (tape_cells == 0) throw TapeConfigError("tape needs at least one cell");
                cells_ = std::vector<Cell>(tape_cells);
            }
            std::size_t TelegraphTapeLoop::tape_cells() const { return cells_.size(); }
            std::size_t TelegraphTapeLoop::marks() const { return used_; }
            void TelegraphTapeLoop::stamp(std::int32_t mark) {
                if (used_ == cells_.size()) throw TapeFullError("tape is full");
                cells_[next_].occupied = true;
                cells_[next_].mark = mark;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t TelegraphTapeLoop::send() {
                if (used_ == 0) throw TapeEmptyError("tape is empty");
                std::int32_t value = cells_[oldest_].mark;
                cells_[oldest_].occupied = false;
                cells_[oldest_].mark = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::string TelegraphTapeLoop::tape_trace() const {
                std::string out = "#";
                for (std::size_t i = 0; i < cells_.size(); ++i) {
                    if (i != 0) out += "-";
                    out += cells_[i].occupied ? std::to_string(cells_[i].mark) : ".";
                }
                out += "# send@" + std::to_string(oldest_) + " stamp@" + std::to_string(next_);
                out += " used=" + std::to_string(used_) + "/" + std::to_string(cells_.size());
                return out;
            }
            """,
            """
            TelegraphTapeLoop::TelegraphTapeLoop(std::size_t tape_cells) {
                if (tape_cells == 0) throw TapeConfigError("tape needs at least one cell");
                cells_ = std::vector<Cell>(tape_cells);
            }
            std::size_t TelegraphTapeLoop::tape_cells() const { return cells_.size(); }
            std::size_t TelegraphTapeLoop::marks() const { return used_; }
            void TelegraphTapeLoop::stamp(std::int32_t mark) {
                if (used_ == cells_.size()) throw TapeFullError("tape is full");
                cells_[used_].occupied = true;
                cells_[used_].mark = mark;
                ++used_;
            }
            std::int32_t TelegraphTapeLoop::send() {
                if (used_ == 0) throw TapeEmptyError("tape is empty");
                std::int32_t value = cells_[0].mark;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].mark = 0;
                --used_;
                return value;
            }
            std::string TelegraphTapeLoop::tape_trace() const {
                std::string out = "<";
                for (std::size_t i = 0; i < used_; ++i) {
                    if (i != 0) out += ",";
                    out += std::to_string(cells_[i].mark);
                }
                out += ">";
                return out;
            }
            """,
            """
            TelegraphTapeLoop tape(4);
            tape.stamp(5);
            tape.stamp(7);
            if (tape.marks() != 2U) return 1;
            if (tape.send() != 5) return 2;
            tape.stamp(9);
            tape.stamp(11);
            if (tape.send() != 7) return 3;
            if (tape.send() != 9) return 4;
            if (tape.send() != 11) return 5;
            if (tape.marks() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { TelegraphTapeLoop zero(0); (void)zero; } catch (const TapeConfigError&) { threw = true; }
            if (!threw) return 1;
            TelegraphTapeLoop tape(4);
            if (tape.tape_trace() != "#.-.-.-.# send@0 stamp@0 used=0/4") return 2;
            threw = false;
            try { tape.send(); } catch (const TapeEmptyError&) { threw = true; }
            if (!threw) return 3;
            tape.stamp(5);
            tape.stamp(7);
            tape.stamp(9);
            if (tape.tape_trace() != "#5-7-9-.# send@0 stamp@3 used=3/4") return 4;
            tape.stamp(11);
            if (tape.tape_trace() != "#5-7-9-11# send@0 stamp@0 used=4/4") return 5;
            threw = false;
            try { tape.stamp(13); } catch (const TapeFullError&) { threw = true; }
            if (!threw) return 6;
            if (tape.marks() != 4U) return 7;
            if (tape.send() != 5) return 8;
            if (tape.tape_trace() != "#.-7-9-11# send@1 stamp@0 used=3/4") return 9;
            tape.stamp(13);
            if (tape.tape_trace() != "#13-7-9-11# send@1 stamp@1 used=4/4") return 10;
            if (tape.send() != 7) return 11;
            if (tape.tape_trace() != "#13-.-9-11# send@2 stamp@1 used=3/4") return 12;
            if (tape.send() != 9) return 13;
            if (tape.tape_trace() != "#13-.-.-11# send@3 stamp@1 used=2/4") return 14;
            if (tape.send() != 11) return 15;
            if (tape.tape_trace() != "#13-.-.-.# send@0 stamp@1 used=1/4") return 16;
            if (tape.send() != 13) return 17;
            if (tape.tape_trace() != "#.-.-.-.# send@1 stamp@1 used=0/4") return 18;
            return 0;
            """,
            "a fixed tape of mark cells whose exact slot trace with gaps and cursor positions stays observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a compact list rendering that hides physical gaps",
            "exact tape_trace strings after stamp/send sequences that wrap the tape, showing freed cells and wrapped cursors, full and empty channels, and zero-cell rejection",
            "exact tape trace with physical gap positions",
            "layout-rendering bounded ring with exact snapshot output",
        ),
        c(
            "f26cbuf-ticker-tape-window",
            "Ticker tape window",
            "ticker_tape",
            """
            class WindowConfigError : public std::invalid_argument {
            public:
                explicit WindowConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WindowEmptyError : public std::runtime_error {
            public:
                explicit WindowEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class WindowFullError : public std::logic_error {
            public:
                explicit WindowFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TickerTapeWindow {
            public:
                explicit TickerTapeWindow(std::size_t window_cells);
                void post(const std::string& symbol);
                std::string advance();
                std::size_t postings() const;
                std::size_t window_cells() const;
                std::string window_ticker() const;
            };
            """,
            """
            class WindowConfigError : public std::invalid_argument {
            public:
                explicit WindowConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class WindowEmptyError : public std::runtime_error {
            public:
                explicit WindowEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class WindowFullError : public std::logic_error {
            public:
                explicit WindowFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TickerTapeWindow {
            public:
                explicit TickerTapeWindow(std::size_t window_cells);
                void post(const std::string& symbol);
                std::string advance();
                std::size_t postings() const;
                std::size_t window_cells() const;
                std::string window_ticker() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string symbol;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            TickerTapeWindow::TickerTapeWindow(std::size_t window_cells) {
                if (window_cells == 0) throw WindowConfigError("window needs at least one cell");
                cells_ = std::vector<Cell>(window_cells);
            }
            std::size_t TickerTapeWindow::window_cells() const { return cells_.size(); }
            std::size_t TickerTapeWindow::postings() const { return used_; }
            void TickerTapeWindow::post(const std::string& symbol) {
                if (used_ == cells_.size()) throw WindowFullError("window is full");
                cells_[next_].occupied = true;
                cells_[next_].symbol = symbol;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string TickerTapeWindow::advance() {
                if (used_ == 0) throw WindowEmptyError("window is empty");
                std::string value = cells_[oldest_].symbol;
                cells_[oldest_].occupied = false;
                cells_[oldest_].symbol.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::string TickerTapeWindow::window_ticker() const {
                std::string out = "%";
                for (std::size_t i = 0; i < cells_.size(); ++i) {
                    if (i != 0) out += ";";
                    out += cells_[i].occupied ? cells_[i].symbol : ".";
                }
                out += "% advance@" + std::to_string(oldest_) + " post@" + std::to_string(next_);
                out += " used=" + std::to_string(used_) + "/" + std::to_string(cells_.size());
                return out;
            }
            """,
            """
            TickerTapeWindow::TickerTapeWindow(std::size_t window_cells) {
                if (window_cells == 0) throw WindowConfigError("window needs at least one cell");
                cells_ = std::vector<Cell>(window_cells);
            }
            std::size_t TickerTapeWindow::window_cells() const { return cells_.size(); }
            std::size_t TickerTapeWindow::postings() const { return used_; }
            void TickerTapeWindow::post(const std::string& symbol) {
                if (used_ == cells_.size()) throw WindowFullError("window is full");
                cells_[used_].occupied = true;
                cells_[used_].symbol = symbol;
                ++used_;
            }
            std::string TickerTapeWindow::advance() {
                if (used_ == 0) throw WindowEmptyError("window is empty");
                std::string value = cells_[0].symbol;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].symbol.clear();
                --used_;
                return value;
            }
            std::string TickerTapeWindow::window_ticker() const {
                std::string out = "<";
                for (std::size_t i = 0; i < used_; ++i) {
                    if (i != 0) out += ",";
                    out += cells_[i].symbol;
                }
                out += ">";
                return out;
            }
            """,
            """
            TickerTapeWindow window(3);
            window.post("xau");
            window.post("ybu");
            if (window.postings() != 2U) return 1;
            if (window.advance() != "xau") return 2;
            window.post("zcv");
            window.post("wdw");
            if (window.advance() != "ybu") return 3;
            if (window.advance() != "zcv") return 4;
            if (window.advance() != "wdw") return 5;
            if (window.postings() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { TickerTapeWindow zero(0); (void)zero; } catch (const WindowConfigError&) { threw = true; }
            if (!threw) return 1;
            TickerTapeWindow window(3);
            if (window.window_ticker() != "%.;.;.% advance@0 post@0 used=0/3") return 2;
            threw = false;
            try { window.advance(); } catch (const WindowEmptyError&) { threw = true; }
            if (!threw) return 3;
            window.post("xau");
            window.post("ybu");
            if (window.window_ticker() != "%xau;ybu;.% advance@0 post@2 used=2/3") return 4;
            window.post("zcv");
            if (window.window_ticker() != "%xau;ybu;zcv% advance@0 post@0 used=3/3") return 5;
            threw = false;
            try { window.post("wdw"); } catch (const WindowFullError&) { threw = true; }
            if (!threw) return 6;
            if (window.postings() != 3U) return 7;
            if (window.advance() != "xau") return 8;
            if (window.window_ticker() != "%.;ybu;zcv% advance@1 post@0 used=2/3") return 9;
            window.post("wdw");
            if (window.window_ticker() != "%wdw;ybu;zcv% advance@1 post@1 used=3/3") return 10;
            if (window.advance() != "ybu") return 11;
            if (window.window_ticker() != "%wdw;.;zcv% advance@2 post@1 used=2/3") return 12;
            if (window.advance() != "zcv") return 13;
            if (window.window_ticker() != "%wdw;.;.% advance@0 post@1 used=1/3") return 14;
            if (window.advance() != "wdw") return 15;
            if (window.window_ticker() != "%.;.;.% advance@1 post@1 used=0/3") return 16;
            return 0;
            """,
            "a fixed window of symbol cells whose exact slot ticker with gaps and cursor positions stays observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a compact list rendering that hides physical gaps",
            "exact window_ticker strings after post/advance sequences that wrap the window, showing freed cells and wrapped cursors, full and empty channels, and zero-cell rejection",
            "exact window rendering with string symbols",
            "layout-rendering bounded ring with exact snapshot output",
        ),
        c(
            "f26cbuf-engraving-lathe-grooves",
            "Engraving lathe grooves",
            "engraving_lathe",
            """
            class LatheConfigError : public std::invalid_argument {
            public:
                explicit LatheConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LatheEmptyError : public std::runtime_error {
            public:
                explicit LatheEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class LatheFullError : public std::logic_error {
            public:
                explicit LatheFullError(const std::string& message) : std::logic_error(message) {}
            };
            class EngravingLatheGrooves {
            public:
                explicit EngravingLatheGrooves(std::size_t lathe_cells);
                void cut(std::int64_t depth);
                std::int64_t polish();
                std::size_t grooves() const;
                std::size_t lathe_cells() const;
                std::string lathe_pattern() const;
            };
            """,
            """
            class LatheConfigError : public std::invalid_argument {
            public:
                explicit LatheConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class LatheEmptyError : public std::runtime_error {
            public:
                explicit LatheEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class LatheFullError : public std::logic_error {
            public:
                explicit LatheFullError(const std::string& message) : std::logic_error(message) {}
            };
            class EngravingLatheGrooves {
            public:
                explicit EngravingLatheGrooves(std::size_t lathe_cells);
                void cut(std::int64_t depth);
                std::int64_t polish();
                std::size_t grooves() const;
                std::size_t lathe_cells() const;
                std::string lathe_pattern() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t depth = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            EngravingLatheGrooves::EngravingLatheGrooves(std::size_t lathe_cells) {
                if (lathe_cells == 0) throw LatheConfigError("lathe needs at least one cell");
                cells_ = std::vector<Cell>(lathe_cells);
            }
            std::size_t EngravingLatheGrooves::lathe_cells() const { return cells_.size(); }
            std::size_t EngravingLatheGrooves::grooves() const { return used_; }
            void EngravingLatheGrooves::cut(std::int64_t depth) {
                if (used_ == cells_.size()) throw LatheFullError("lathe is full");
                cells_[next_].occupied = true;
                cells_[next_].depth = depth;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t EngravingLatheGrooves::polish() {
                if (used_ == 0) throw LatheEmptyError("lathe is empty");
                std::int64_t value = cells_[oldest_].depth;
                cells_[oldest_].occupied = false;
                cells_[oldest_].depth = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::string EngravingLatheGrooves::lathe_pattern() const {
                std::string out = "=";
                for (std::size_t i = 0; i < cells_.size(); ++i) {
                    if (i != 0) out += ":";
                    out += cells_[i].occupied ? std::to_string(cells_[i].depth) : ".";
                }
                out += "= polish@" + std::to_string(oldest_) + " cut@" + std::to_string(next_);
                out += " used=" + std::to_string(used_) + "/" + std::to_string(cells_.size());
                return out;
            }
            """,
            """
            EngravingLatheGrooves::EngravingLatheGrooves(std::size_t lathe_cells) {
                if (lathe_cells == 0) throw LatheConfigError("lathe needs at least one cell");
                cells_ = std::vector<Cell>(lathe_cells);
            }
            std::size_t EngravingLatheGrooves::lathe_cells() const { return cells_.size(); }
            std::size_t EngravingLatheGrooves::grooves() const { return used_; }
            void EngravingLatheGrooves::cut(std::int64_t depth) {
                if (used_ == cells_.size()) throw LatheFullError("lathe is full");
                cells_[used_].occupied = true;
                cells_[used_].depth = depth;
                ++used_;
            }
            std::int64_t EngravingLatheGrooves::polish() {
                if (used_ == 0) throw LatheEmptyError("lathe is empty");
                std::int64_t value = cells_[0].depth;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].depth = 0;
                --used_;
                return value;
            }
            std::string EngravingLatheGrooves::lathe_pattern() const {
                std::string out = "<";
                for (std::size_t i = 0; i < used_; ++i) {
                    if (i != 0) out += ",";
                    out += std::to_string(cells_[i].depth);
                }
                out += ">";
                return out;
            }
            """,
            """
            EngravingLatheGrooves lathe(3);
            lathe.cut(1200);
            lathe.cut(2400);
            if (lathe.grooves() != 2U) return 1;
            if (lathe.polish() != 1200) return 2;
            lathe.cut(3600);
            lathe.cut(4800);
            if (lathe.polish() != 2400) return 3;
            if (lathe.polish() != 3600) return 4;
            if (lathe.polish() != 4800) return 5;
            if (lathe.grooves() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { EngravingLatheGrooves zero(0); (void)zero; } catch (const LatheConfigError&) { threw = true; }
            if (!threw) return 1;
            EngravingLatheGrooves lathe(3);
            if (lathe.lathe_pattern() != "=.:.:.= polish@0 cut@0 used=0/3") return 2;
            threw = false;
            try { lathe.polish(); } catch (const LatheEmptyError&) { threw = true; }
            if (!threw) return 3;
            lathe.cut(1200);
            lathe.cut(2400);
            if (lathe.lathe_pattern() != "=1200:2400:.= polish@0 cut@2 used=2/3") return 4;
            lathe.cut(3600);
            if (lathe.lathe_pattern() != "=1200:2400:3600= polish@0 cut@0 used=3/3") return 5;
            threw = false;
            try { lathe.cut(4800); } catch (const LatheFullError&) { threw = true; }
            if (!threw) return 6;
            if (lathe.grooves() != 3U) return 7;
            if (lathe.polish() != 1200) return 8;
            if (lathe.lathe_pattern() != "=.:2400:3600= polish@1 cut@0 used=2/3") return 9;
            lathe.cut(4800);
            if (lathe.lathe_pattern() != "=4800:2400:3600= polish@1 cut@1 used=3/3") return 10;
            if (lathe.polish() != 2400) return 11;
            if (lathe.lathe_pattern() != "=4800:.:3600= polish@2 cut@1 used=2/3") return 12;
            if (lathe.polish() != 3600) return 13;
            if (lathe.lathe_pattern() != "=4800:.:.= polish@0 cut@1 used=1/3") return 14;
            if (lathe.polish() != 4800) return 15;
            if (lathe.lathe_pattern() != "=.:.:.= polish@1 cut@1 used=0/3") return 16;
            return 0;
            """,
            "a fixed lathe of depth grooves whose exact slot pattern with gaps and cursor positions stays observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a compact list rendering that hides physical gaps",
            "exact lathe_pattern strings after cut/polish sequences that wrap the lathe, showing freed cells and wrapped cursors, full and empty channels, and zero-cell rejection",
            "project-context exact pattern rendering with int64 depths",
            "layout-rendering bounded ring with exact snapshot output",
            project_support=True,
        ),
        c(
            "f26cbuf-kaleidoscope-mirror-drum",
            "Kaleidoscope mirror drum",
            "kaleidoscope",
            """
            class DrumConfigError : public std::invalid_argument {
            public:
                explicit DrumConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DrumEmptyError : public std::runtime_error {
            public:
                explicit DrumEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DrumFullError : public std::logic_error {
            public:
                explicit DrumFullError(const std::string& message) : std::logic_error(message) {}
            };
            class KaleidoscopeMirrorDrum {
            public:
                explicit KaleidoscopeMirrorDrum(std::size_t drum_cells);
                void tumble(const std::string& shard);
                std::string reflect();
                std::size_t shards() const;
                std::size_t drum_cells() const;
                std::string drum_image() const;
            };
            """,
            """
            class DrumConfigError : public std::invalid_argument {
            public:
                explicit DrumConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DrumEmptyError : public std::runtime_error {
            public:
                explicit DrumEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DrumFullError : public std::logic_error {
            public:
                explicit DrumFullError(const std::string& message) : std::logic_error(message) {}
            };
            class KaleidoscopeMirrorDrum {
            public:
                explicit KaleidoscopeMirrorDrum(std::size_t drum_cells);
                void tumble(const std::string& shard);
                std::string reflect();
                std::size_t shards() const;
                std::size_t drum_cells() const;
                std::string drum_image() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string shard;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            KaleidoscopeMirrorDrum::KaleidoscopeMirrorDrum(std::size_t drum_cells) {
                if (drum_cells == 0) throw DrumConfigError("drum needs at least one cell");
                cells_ = std::vector<Cell>(drum_cells);
            }
            std::size_t KaleidoscopeMirrorDrum::drum_cells() const { return cells_.size(); }
            std::size_t KaleidoscopeMirrorDrum::shards() const { return used_; }
            void KaleidoscopeMirrorDrum::tumble(const std::string& shard) {
                if (used_ == cells_.size()) throw DrumFullError("drum is full");
                cells_[next_].occupied = true;
                cells_[next_].shard = shard;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string KaleidoscopeMirrorDrum::reflect() {
                if (used_ == 0) throw DrumEmptyError("drum is empty");
                std::string value = cells_[oldest_].shard;
                cells_[oldest_].occupied = false;
                cells_[oldest_].shard.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::string KaleidoscopeMirrorDrum::drum_image() const {
                std::string out = "(";
                for (std::size_t i = 0; i < cells_.size(); ++i) {
                    if (i != 0) out += " ";
                    out += cells_[i].occupied ? cells_[i].shard : ".";
                }
                out += ") reflect@" + std::to_string(oldest_) + " tumble@" + std::to_string(next_);
                out += " used=" + std::to_string(used_) + "/" + std::to_string(cells_.size());
                return out;
            }
            """,
            """
            KaleidoscopeMirrorDrum::KaleidoscopeMirrorDrum(std::size_t drum_cells) {
                if (drum_cells == 0) throw DrumConfigError("drum needs at least one cell");
                cells_ = std::vector<Cell>(drum_cells);
            }
            std::size_t KaleidoscopeMirrorDrum::drum_cells() const { return cells_.size(); }
            std::size_t KaleidoscopeMirrorDrum::shards() const { return used_; }
            void KaleidoscopeMirrorDrum::tumble(const std::string& shard) {
                if (used_ == cells_.size()) throw DrumFullError("drum is full");
                cells_[used_].occupied = true;
                cells_[used_].shard = shard;
                ++used_;
            }
            std::string KaleidoscopeMirrorDrum::reflect() {
                if (used_ == 0) throw DrumEmptyError("drum is empty");
                std::string value = cells_[0].shard;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].shard.clear();
                --used_;
                return value;
            }
            std::string KaleidoscopeMirrorDrum::drum_image() const {
                std::string out = "<";
                for (std::size_t i = 0; i < used_; ++i) {
                    if (i != 0) out += ",";
                    out += cells_[i].shard;
                }
                out += ">";
                return out;
            }
            """,
            """
            KaleidoscopeMirrorDrum drum(4);
            drum.tumble("rose");
            drum.tumble("amber");
            if (drum.shards() != 2U) return 1;
            if (drum.reflect() != "rose") return 2;
            drum.tumble("teal");
            drum.tumble("jade");
            if (drum.reflect() != "amber") return 3;
            if (drum.reflect() != "teal") return 4;
            if (drum.reflect() != "jade") return 5;
            if (drum.shards() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { KaleidoscopeMirrorDrum zero(0); (void)zero; } catch (const DrumConfigError&) { threw = true; }
            if (!threw) return 1;
            KaleidoscopeMirrorDrum drum(4);
            if (drum.drum_image() != "(. . . .) reflect@0 tumble@0 used=0/4") return 2;
            threw = false;
            try { drum.reflect(); } catch (const DrumEmptyError&) { threw = true; }
            if (!threw) return 3;
            drum.tumble("rose");
            drum.tumble("amber");
            drum.tumble("teal");
            if (drum.drum_image() != "(rose amber teal .) reflect@0 tumble@3 used=3/4") return 4;
            drum.tumble("jade");
            if (drum.drum_image() != "(rose amber teal jade) reflect@0 tumble@0 used=4/4") return 5;
            threw = false;
            try { drum.tumble("onyx"); } catch (const DrumFullError&) { threw = true; }
            if (!threw) return 6;
            if (drum.shards() != 4U) return 7;
            if (drum.reflect() != "rose") return 8;
            if (drum.drum_image() != "(. amber teal jade) reflect@1 tumble@0 used=3/4") return 9;
            drum.tumble("onyx");
            if (drum.drum_image() != "(onyx amber teal jade) reflect@1 tumble@1 used=4/4") return 10;
            if (drum.reflect() != "amber") return 11;
            if (drum.drum_image() != "(onyx . teal jade) reflect@2 tumble@1 used=3/4") return 12;
            if (drum.reflect() != "teal") return 13;
            if (drum.drum_image() != "(onyx . . jade) reflect@3 tumble@1 used=2/4") return 14;
            if (drum.reflect() != "jade") return 15;
            if (drum.drum_image() != "(onyx . . .) reflect@0 tumble@1 used=1/4") return 16;
            if (drum.reflect() != "onyx") return 17;
            if (drum.drum_image() != "(. . . .) reflect@1 tumble@1 used=0/4") return 18;
            return 0;
            """,
            "a fixed drum of shard cells whose exact slot image with gaps and cursor positions stays observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a compact list rendering that hides physical gaps",
            "exact drum_image strings after tumble/reflect sequences that wrap the drum, showing freed cells and wrapped cursors, full and empty channels, and zero-cell rejection",
            "exact drum image with mirrored slot order",
            "layout-rendering bounded ring with exact snapshot output",
        ),
        c(
            "f26cbuf-zoetrope-frame-strip",
            "Zoetrope frame strip",
            "zoetrope",
            """
            class StripConfigError : public std::invalid_argument {
            public:
                explicit StripConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StripEmptyError : public std::runtime_error {
            public:
                explicit StripEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class StripFullError : public std::logic_error {
            public:
                explicit StripFullError(const std::string& message) : std::logic_error(message) {}
            };
            class ZoetropeFrameStrip {
            public:
                explicit ZoetropeFrameStrip(std::size_t strip_cells);
                void draw(std::int32_t frame);
                std::int32_t flicker();
                std::size_t frames_drawn() const;
                std::size_t strip_cells() const;
                std::string strip_reel() const;
            };
            """,
            """
            class StripConfigError : public std::invalid_argument {
            public:
                explicit StripConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class StripEmptyError : public std::runtime_error {
            public:
                explicit StripEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class StripFullError : public std::logic_error {
            public:
                explicit StripFullError(const std::string& message) : std::logic_error(message) {}
            };
            class ZoetropeFrameStrip {
            public:
                explicit ZoetropeFrameStrip(std::size_t strip_cells);
                void draw(std::int32_t frame);
                std::int32_t flicker();
                std::size_t frames_drawn() const;
                std::size_t strip_cells() const;
                std::string strip_reel() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t frame = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            ZoetropeFrameStrip::ZoetropeFrameStrip(std::size_t strip_cells) {
                if (strip_cells == 0) throw StripConfigError("strip needs at least one cell");
                cells_ = std::vector<Cell>(strip_cells);
            }
            std::size_t ZoetropeFrameStrip::strip_cells() const { return cells_.size(); }
            std::size_t ZoetropeFrameStrip::frames_drawn() const { return used_; }
            void ZoetropeFrameStrip::draw(std::int32_t frame) {
                if (used_ == cells_.size()) throw StripFullError("strip is full");
                cells_[next_].occupied = true;
                cells_[next_].frame = frame;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t ZoetropeFrameStrip::flicker() {
                if (used_ == 0) throw StripEmptyError("strip is empty");
                std::int32_t value = cells_[oldest_].frame;
                cells_[oldest_].occupied = false;
                cells_[oldest_].frame = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::string ZoetropeFrameStrip::strip_reel() const {
                std::string out = "~";
                for (const Cell& cell : cells_) {
                    out += cell.occupied ? std::to_string(cell.frame) : ".";
                    out += "~";
                }
                out += " flicker@" + std::to_string(oldest_) + " draw@" + std::to_string(next_);
                out += " used=" + std::to_string(used_) + "/" + std::to_string(cells_.size());
                return out;
            }
            """,
            """
            ZoetropeFrameStrip::ZoetropeFrameStrip(std::size_t strip_cells) {
                if (strip_cells == 0) throw StripConfigError("strip needs at least one cell");
                cells_ = std::vector<Cell>(strip_cells);
            }
            std::size_t ZoetropeFrameStrip::strip_cells() const { return cells_.size(); }
            std::size_t ZoetropeFrameStrip::frames_drawn() const { return used_; }
            void ZoetropeFrameStrip::draw(std::int32_t frame) {
                if (used_ == cells_.size()) throw StripFullError("strip is full");
                cells_[used_].occupied = true;
                cells_[used_].frame = frame;
                ++used_;
            }
            std::int32_t ZoetropeFrameStrip::flicker() {
                if (used_ == 0) throw StripEmptyError("strip is empty");
                std::int32_t value = cells_[0].frame;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].frame = 0;
                --used_;
                return value;
            }
            std::string ZoetropeFrameStrip::strip_reel() const {
                std::string out = "<";
                for (std::size_t i = 0; i < used_; ++i) {
                    if (i != 0) out += ",";
                    out += std::to_string(cells_[i].frame);
                }
                out += ">";
                return out;
            }
            """,
            """
            ZoetropeFrameStrip strip(3);
            strip.draw(7);
            strip.draw(8);
            if (strip.frames_drawn() != 2U) return 1;
            if (strip.flicker() != 7) return 2;
            strip.draw(9);
            strip.draw(10);
            if (strip.flicker() != 8) return 3;
            if (strip.flicker() != 9) return 4;
            if (strip.flicker() != 10) return 5;
            if (strip.frames_drawn() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { ZoetropeFrameStrip zero(0); (void)zero; } catch (const StripConfigError&) { threw = true; }
            if (!threw) return 1;
            ZoetropeFrameStrip strip(3);
            if (strip.strip_reel() != "~.~.~.~ flicker@0 draw@0 used=0/3") return 2;
            threw = false;
            try { strip.flicker(); } catch (const StripEmptyError&) { threw = true; }
            if (!threw) return 3;
            strip.draw(7);
            strip.draw(8);
            if (strip.strip_reel() != "~7~8~.~ flicker@0 draw@2 used=2/3") return 4;
            strip.draw(9);
            if (strip.strip_reel() != "~7~8~9~ flicker@0 draw@0 used=3/3") return 5;
            threw = false;
            try { strip.draw(10); } catch (const StripFullError&) { threw = true; }
            if (!threw) return 6;
            if (strip.frames_drawn() != 3U) return 7;
            if (strip.flicker() != 7) return 8;
            if (strip.strip_reel() != "~.~8~9~ flicker@1 draw@0 used=2/3") return 9;
            strip.draw(10);
            if (strip.strip_reel() != "~10~8~9~ flicker@1 draw@1 used=3/3") return 10;
            if (strip.flicker() != 8) return 11;
            if (strip.strip_reel() != "~10~.~9~ flicker@2 draw@1 used=2/3") return 12;
            if (strip.flicker() != 9) return 13;
            if (strip.strip_reel() != "~10~.~.~ flicker@0 draw@1 used=1/3") return 14;
            if (strip.flicker() != 10) return 15;
            if (strip.strip_reel() != "~.~.~.~ flicker@1 draw@1 used=0/3") return 16;
            return 0;
            """,
            "a fixed strip of frame cells whose exact slot reel with gaps and cursor positions stays observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a compact list rendering that hides physical gaps",
            "exact strip_reel strings after draw/flicker sequences that wrap the strip, showing freed cells and wrapped cursors, full and empty channels, and zero-cell rejection",
            "exact strip reel with physical frame gaps",
            "layout-rendering bounded ring with exact snapshot output",
        ),
        c(
            "f26cbuf-calliope-valve-barrel",
            "Calliope valve barrel",
            "calliope",
            """
            class CalliopeConfigError : public std::invalid_argument {
            public:
                explicit CalliopeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CalliopeEmptyError : public std::runtime_error {
            public:
                explicit CalliopeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class CalliopeFullError : public std::logic_error {
            public:
                explicit CalliopeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class CalliopeValveBarrel {
            public:
                explicit CalliopeValveBarrel(std::size_t calliope_cells);
                void voice(const std::string& pipe);
                std::string sound_off();
                std::size_t valves() const;
                std::size_t calliope_cells() const;
                std::string chorus_map() const;
            };
            """,
            """
            class CalliopeConfigError : public std::invalid_argument {
            public:
                explicit CalliopeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CalliopeEmptyError : public std::runtime_error {
            public:
                explicit CalliopeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class CalliopeFullError : public std::logic_error {
            public:
                explicit CalliopeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class CalliopeValveBarrel {
            public:
                explicit CalliopeValveBarrel(std::size_t calliope_cells);
                void voice(const std::string& pipe);
                std::string sound_off();
                std::size_t valves() const;
                std::size_t calliope_cells() const;
                std::string chorus_map() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string pipe;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            CalliopeValveBarrel::CalliopeValveBarrel(std::size_t calliope_cells) {
                if (calliope_cells == 0) throw CalliopeConfigError("calliope needs at least one cell");
                cells_ = std::vector<Cell>(calliope_cells);
            }
            std::size_t CalliopeValveBarrel::calliope_cells() const { return cells_.size(); }
            std::size_t CalliopeValveBarrel::valves() const { return used_; }
            void CalliopeValveBarrel::voice(const std::string& pipe) {
                if (used_ == cells_.size()) throw CalliopeFullError("calliope is full");
                cells_[next_].occupied = true;
                cells_[next_].pipe = pipe;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string CalliopeValveBarrel::sound_off() {
                if (used_ == 0) throw CalliopeEmptyError("calliope is empty");
                std::string value = cells_[oldest_].pipe;
                cells_[oldest_].occupied = false;
                cells_[oldest_].pipe.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::string CalliopeValveBarrel::chorus_map() const {
                std::string out = "!";
                for (const Cell& cell : cells_) {
                    out += cell.occupied ? cell.pipe : ".";
                    out += "!";
                }
                out += " sound@" + std::to_string(oldest_) + " voice@" + std::to_string(next_);
                out += " used=" + std::to_string(used_) + "/" + std::to_string(cells_.size());
                return out;
            }
            """,
            """
            CalliopeValveBarrel::CalliopeValveBarrel(std::size_t calliope_cells) {
                if (calliope_cells == 0) throw CalliopeConfigError("calliope needs at least one cell");
                cells_ = std::vector<Cell>(calliope_cells);
            }
            std::size_t CalliopeValveBarrel::calliope_cells() const { return cells_.size(); }
            std::size_t CalliopeValveBarrel::valves() const { return used_; }
            void CalliopeValveBarrel::voice(const std::string& pipe) {
                if (used_ == cells_.size()) throw CalliopeFullError("calliope is full");
                cells_[used_].occupied = true;
                cells_[used_].pipe = pipe;
                ++used_;
            }
            std::string CalliopeValveBarrel::sound_off() {
                if (used_ == 0) throw CalliopeEmptyError("calliope is empty");
                std::string value = cells_[0].pipe;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].pipe.clear();
                --used_;
                return value;
            }
            std::string CalliopeValveBarrel::chorus_map() const {
                std::string out = "<";
                for (std::size_t i = 0; i < used_; ++i) {
                    if (i != 0) out += ",";
                    out += cells_[i].pipe;
                }
                out += ">";
                return out;
            }
            """,
            """
            CalliopeValveBarrel calliope(3);
            calliope.voice("fa");
            calliope.voice("sol");
            if (calliope.valves() != 2U) return 1;
            if (calliope.sound_off() != "fa") return 2;
            calliope.voice("la");
            calliope.voice("ti");
            if (calliope.sound_off() != "sol") return 3;
            if (calliope.sound_off() != "la") return 4;
            if (calliope.sound_off() != "ti") return 5;
            if (calliope.valves() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { CalliopeValveBarrel zero(0); (void)zero; } catch (const CalliopeConfigError&) { threw = true; }
            if (!threw) return 1;
            CalliopeValveBarrel calliope(3);
            if (calliope.chorus_map() != "!.!.!.! sound@0 voice@0 used=0/3") return 2;
            threw = false;
            try { calliope.sound_off(); } catch (const CalliopeEmptyError&) { threw = true; }
            if (!threw) return 3;
            calliope.voice("fa");
            calliope.voice("sol");
            if (calliope.chorus_map() != "!fa!sol!.! sound@0 voice@2 used=2/3") return 4;
            calliope.voice("la");
            if (calliope.chorus_map() != "!fa!sol!la! sound@0 voice@0 used=3/3") return 5;
            threw = false;
            try { calliope.voice("ti"); } catch (const CalliopeFullError&) { threw = true; }
            if (!threw) return 6;
            if (calliope.valves() != 3U) return 7;
            if (calliope.sound_off() != "fa") return 8;
            if (calliope.chorus_map() != "!.!sol!la! sound@1 voice@0 used=2/3") return 9;
            calliope.voice("ti");
            if (calliope.chorus_map() != "!ti!sol!la! sound@1 voice@1 used=3/3") return 10;
            if (calliope.sound_off() != "sol") return 11;
            if (calliope.chorus_map() != "!ti!.!la! sound@2 voice@1 used=2/3") return 12;
            if (calliope.sound_off() != "la") return 13;
            if (calliope.chorus_map() != "!ti!.!.! sound@0 voice@1 used=1/3") return 14;
            if (calliope.sound_off() != "ti") return 15;
            if (calliope.chorus_map() != "!.!.!.! sound@1 voice@1 used=0/3") return 16;
            return 0;
            """,
            "a fixed barrel of pipe valves whose exact slot chorus with gaps and cursor positions stays observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a compact list rendering that hides physical gaps",
            "exact chorus_map strings after voice/sound_off sequences that wrap the barrel, showing freed cells and wrapped cursors, full and empty channels, and zero-cell rejection",
            "exact chorus map with string pipes",
            "layout-rendering bounded ring with exact snapshot output",
        ),
        c(
            "f26cbuf-flight-recorder-loop",
            "Flight recorder loop",
            "flight_recorder",
            """
            class RecorderConfigError : public std::invalid_argument {
            public:
                explicit RecorderConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RecorderEmptyError : public std::runtime_error {
            public:
                explicit RecorderEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class RecorderFullError : public std::logic_error {
            public:
                explicit RecorderFullError(const std::string& message) : std::logic_error(message) {}
            };
            class FlightRecorderLoop {
            public:
                explicit FlightRecorderLoop(std::size_t capacity);
                void log_sample(std::int64_t sample);
                void force_log(std::int64_t sample);
                std::int64_t dump();
                std::size_t samples() const;
                std::size_t capacity() const;
                std::size_t oldest_slot() const;
                std::optional<std::int64_t> last_dropped() const;
                std::vector<std::string> flight_log() const;
            };
            """,
            """
            class RecorderConfigError : public std::invalid_argument {
            public:
                explicit RecorderConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RecorderEmptyError : public std::runtime_error {
            public:
                explicit RecorderEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class RecorderFullError : public std::logic_error {
            public:
                explicit RecorderFullError(const std::string& message) : std::logic_error(message) {}
            };
            class FlightRecorderLoop {
            public:
                explicit FlightRecorderLoop(std::size_t capacity);
                void log_sample(std::int64_t sample);
                void force_log(std::int64_t sample);
                std::int64_t dump();
                std::size_t samples() const;
                std::size_t capacity() const;
                std::size_t oldest_slot() const;
                std::optional<std::int64_t> last_dropped() const;
                std::vector<std::string> flight_log() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t sample = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
                std::vector<std::string> journal_;
                std::optional<std::int64_t> dropped_;
            };
            """,
            """
            FlightRecorderLoop::FlightRecorderLoop(std::size_t capacity) {
                if (capacity == 0) throw RecorderConfigError("recorder needs at least one cell");
                cells_ = std::vector<Cell>(capacity);
            }
            std::size_t FlightRecorderLoop::capacity() const { return cells_.size(); }
            std::size_t FlightRecorderLoop::samples() const { return used_; }
            void FlightRecorderLoop::log_sample(std::int64_t sample) {
                if (used_ == cells_.size()) throw RecorderFullError("recorder is full");
                cells_[next_].occupied = true;
                cells_[next_].sample = sample;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            void FlightRecorderLoop::force_log(std::int64_t sample) {
                if (used_ == cells_.size()) {
                    journal_.push_back("drop slot=" + std::to_string(oldest_) + " sample=" + std::to_string(cells_[oldest_].sample));
                    dropped_ = cells_[oldest_].sample;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].sample = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                }
                log_sample(sample);
            }
            std::int64_t FlightRecorderLoop::dump() {
                if (used_ == 0) throw RecorderEmptyError("recorder is empty");
                std::int64_t value = cells_[oldest_].sample;
                cells_[oldest_].occupied = false;
                cells_[oldest_].sample = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t FlightRecorderLoop::oldest_slot() const {
                if (used_ == 0) throw RecorderEmptyError("recorder is empty");
                return oldest_;
            }
            std::optional<std::int64_t> FlightRecorderLoop::last_dropped() const { return dropped_; }
            std::vector<std::string> FlightRecorderLoop::flight_log() const { return journal_; }
            """,
            """
            FlightRecorderLoop::FlightRecorderLoop(std::size_t capacity) {
                if (capacity == 0) throw RecorderConfigError("recorder needs at least one cell");
                cells_ = std::vector<Cell>(capacity);
            }
            std::size_t FlightRecorderLoop::capacity() const { return cells_.size(); }
            std::size_t FlightRecorderLoop::samples() const { return used_; }
            void FlightRecorderLoop::log_sample(std::int64_t sample) {
                if (used_ == cells_.size()) throw RecorderFullError("recorder is full");
                cells_[used_].occupied = true;
                cells_[used_].sample = sample;
                ++used_;
            }
            void FlightRecorderLoop::force_log(std::int64_t sample) {
                if (used_ == cells_.size()) {
                    journal_.push_back("drop slot=" + std::to_string(used_ - 1) + " sample=" + std::to_string(cells_[used_ - 1].sample));
                    dropped_ = cells_[used_ - 1].sample;
                    cells_[used_ - 1].sample = sample;
                    return;
                }
                log_sample(sample);
            }
            std::int64_t FlightRecorderLoop::dump() {
                if (used_ == 0) throw RecorderEmptyError("recorder is empty");
                std::int64_t value = cells_[0].sample;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].sample = 0;
                --used_;
                return value;
            }
            std::size_t FlightRecorderLoop::oldest_slot() const {
                if (used_ == 0) throw RecorderEmptyError("recorder is empty");
                return 0;
            }
            std::optional<std::int64_t> FlightRecorderLoop::last_dropped() const { return dropped_; }
            std::vector<std::string> FlightRecorderLoop::flight_log() const { return journal_; }
            """,
            """
            FlightRecorderLoop rec(2);
            rec.log_sample(1);
            rec.log_sample(2);
            if (rec.samples() != 2U) return 1;
            if (rec.dump() != 1) return 2;
            rec.force_log(3);
            if (rec.dump() != 2) return 3;
            if (rec.dump() != 3) return 4;
            if (!rec.flight_log().empty()) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { FlightRecorderLoop zero(0); (void)zero; } catch (const RecorderConfigError&) { threw = true; }
            if (!threw) return 1;
            FlightRecorderLoop rec(3);
            threw = false;
            try { rec.dump(); } catch (const RecorderEmptyError&) { threw = true; }
            if (!threw) return 2;
            if (rec.last_dropped().has_value()) return 3;
            rec.force_log(100);
            if (!rec.flight_log().empty()) return 4;
            rec.log_sample(200);
            rec.log_sample(300);
            if (rec.oldest_slot() != 0U) return 5;
            threw = false;
            try { rec.log_sample(400); } catch (const RecorderFullError&) { threw = true; }
            if (!threw) return 6;
            if (rec.samples() != 3U) return 7;
            rec.force_log(400);
            if (rec.oldest_slot() != 1U) return 8;
            if (!rec.last_dropped() || *rec.last_dropped() != 100) return 9;
            if (rec.flight_log().size() != 1U) return 10;
            if (rec.flight_log()[0] != "drop slot=0 sample=100") return 11;
            if (rec.dump() != 200) return 12;
            rec.force_log(500);
            if (rec.flight_log().size() != 1U) return 13;
            rec.force_log(600);
            if (!rec.last_dropped() || *rec.last_dropped() != 300) return 14;
            if (rec.oldest_slot() != 0U) return 15;
            if (rec.flight_log().size() != 2U) return 16;
            if (rec.flight_log()[1] != "drop slot=2 sample=300") return 17;
            if (rec.dump() != 400) return 18;
            if (rec.dump() != 500) return 19;
            if (rec.dump() != 600) return 20;
            if (rec.samples() != 0U) return 21;
            return 0;
            """,
            "a fixed loop of sample cells whose forced logs evict the oldest physical cell and journal the exact slot and value",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a forced log that evicts the newest occupant",
            "exact flight_log entries with slot numbers after force_log sequences that wrap the loop, last_dropped values, oldest_slot positions, full and empty channels, and zero-capacity rejection",
            "forced-write eviction with exact slot-numbered journals",
            "overwrite-eviction journaling bounded ring",
        ),
        c(
            "f26cbuf-dashcam-clip-vault",
            "Dashcam clip vault",
            "dashcam",
            """
            class VaultConfigError : public std::invalid_argument {
            public:
                explicit VaultConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class VaultEmptyError : public std::runtime_error {
            public:
                explicit VaultEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class VaultFullError : public std::logic_error {
            public:
                explicit VaultFullError(const std::string& message) : std::logic_error(message) {}
            };
            class DashcamClipVault {
            public:
                explicit DashcamClipVault(std::size_t bays);
                void save_clip(const std::string& clip);
                void force_save(const std::string& clip);
                std::string eject();
                std::size_t clips() const;
                std::size_t bays() const;
                std::size_t oldest_bay() const;
                std::optional<std::string> last_overwritten() const;
                std::vector<std::string> vault_log() const;
            };
            """,
            """
            class VaultConfigError : public std::invalid_argument {
            public:
                explicit VaultConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class VaultEmptyError : public std::runtime_error {
            public:
                explicit VaultEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class VaultFullError : public std::logic_error {
            public:
                explicit VaultFullError(const std::string& message) : std::logic_error(message) {}
            };
            class DashcamClipVault {
            public:
                explicit DashcamClipVault(std::size_t bays);
                void save_clip(const std::string& clip);
                void force_save(const std::string& clip);
                std::string eject();
                std::size_t clips() const;
                std::size_t bays() const;
                std::size_t oldest_bay() const;
                std::optional<std::string> last_overwritten() const;
                std::vector<std::string> vault_log() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string clip;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
                std::vector<std::string> journal_;
                std::optional<std::string> dropped_;
            };
            """,
            """
            DashcamClipVault::DashcamClipVault(std::size_t bays) {
                if (bays == 0) throw VaultConfigError("vault needs at least one bay");
                cells_ = std::vector<Cell>(bays);
            }
            std::size_t DashcamClipVault::bays() const { return cells_.size(); }
            std::size_t DashcamClipVault::clips() const { return used_; }
            void DashcamClipVault::save_clip(const std::string& clip) {
                if (used_ == cells_.size()) throw VaultFullError("vault is full");
                cells_[next_].occupied = true;
                cells_[next_].clip = clip;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            void DashcamClipVault::force_save(const std::string& clip) {
                if (used_ == cells_.size()) {
                    journal_.push_back("overwrite bay=" + std::to_string(oldest_) + " clip=" + cells_[oldest_].clip);
                    dropped_ = cells_[oldest_].clip;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].clip.clear();
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                }
                save_clip(clip);
            }
            std::string DashcamClipVault::eject() {
                if (used_ == 0) throw VaultEmptyError("vault is empty");
                std::string value = cells_[oldest_].clip;
                cells_[oldest_].occupied = false;
                cells_[oldest_].clip.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t DashcamClipVault::oldest_bay() const {
                if (used_ == 0) throw VaultEmptyError("vault is empty");
                return oldest_;
            }
            std::optional<std::string> DashcamClipVault::last_overwritten() const { return dropped_; }
            std::vector<std::string> DashcamClipVault::vault_log() const { return journal_; }
            """,
            """
            DashcamClipVault::DashcamClipVault(std::size_t bays) {
                if (bays == 0) throw VaultConfigError("vault needs at least one bay");
                cells_ = std::vector<Cell>(bays);
            }
            std::size_t DashcamClipVault::bays() const { return cells_.size(); }
            std::size_t DashcamClipVault::clips() const { return used_; }
            void DashcamClipVault::save_clip(const std::string& clip) {
                if (used_ == cells_.size()) throw VaultFullError("vault is full");
                cells_[used_].occupied = true;
                cells_[used_].clip = clip;
                ++used_;
            }
            void DashcamClipVault::force_save(const std::string& clip) {
                if (used_ == cells_.size()) {
                    journal_.push_back("overwrite bay=" + std::to_string(used_ - 1) + " clip=" + cells_[used_ - 1].clip);
                    dropped_ = cells_[used_ - 1].clip;
                    cells_[used_ - 1].clip = clip;
                    return;
                }
                save_clip(clip);
            }
            std::string DashcamClipVault::eject() {
                if (used_ == 0) throw VaultEmptyError("vault is empty");
                std::string value = cells_[0].clip;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].clip.clear();
                --used_;
                return value;
            }
            std::size_t DashcamClipVault::oldest_bay() const {
                if (used_ == 0) throw VaultEmptyError("vault is empty");
                return 0;
            }
            std::optional<std::string> DashcamClipVault::last_overwritten() const { return dropped_; }
            std::vector<std::string> DashcamClipVault::vault_log() const { return journal_; }
            """,
            """
            DashcamClipVault vault(2);
            vault.save_clip("m1");
            vault.save_clip("m2");
            if (vault.clips() != 2U) return 1;
            if (vault.eject() != "m1") return 2;
            vault.force_save("m3");
            if (vault.eject() != "m2") return 3;
            if (vault.eject() != "m3") return 4;
            if (!vault.vault_log().empty()) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { DashcamClipVault zero(0); (void)zero; } catch (const VaultConfigError&) { threw = true; }
            if (!threw) return 1;
            DashcamClipVault vault(3);
            threw = false;
            try { vault.eject(); } catch (const VaultEmptyError&) { threw = true; }
            if (!threw) return 2;
            if (vault.last_overwritten().has_value()) return 3;
            vault.force_save("a1");
            if (!vault.vault_log().empty()) return 4;
            vault.save_clip("b2");
            vault.save_clip("c3");
            if (vault.oldest_bay() != 0U) return 5;
            threw = false;
            try { vault.save_clip("d4"); } catch (const VaultFullError&) { threw = true; }
            if (!threw) return 6;
            if (vault.clips() != 3U) return 7;
            vault.force_save("d4");
            if (vault.oldest_bay() != 1U) return 8;
            if (!vault.last_overwritten() || *vault.last_overwritten() != "a1") return 9;
            if (vault.vault_log().size() != 1U) return 10;
            if (vault.vault_log()[0] != "overwrite bay=0 clip=a1") return 11;
            if (vault.eject() != "b2") return 12;
            vault.force_save("e5");
            if (vault.vault_log().size() != 1U) return 13;
            vault.force_save("f6");
            if (!vault.last_overwritten() || *vault.last_overwritten() != "c3") return 14;
            if (vault.oldest_bay() != 0U) return 15;
            if (vault.vault_log().size() != 2U) return 16;
            if (vault.vault_log()[1] != "overwrite bay=2 clip=c3") return 17;
            if (vault.eject() != "d4") return 18;
            if (vault.eject() != "e5") return 19;
            if (vault.eject() != "f6") return 20;
            if (vault.clips() != 0U) return 21;
            return 0;
            """,
            "a fixed vault of clip bays whose forced saves evict the oldest physical bay and journal the exact bay and clip",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a forced save that evicts the newest occupant",
            "exact vault_log entries with bay numbers after force_save sequences that wrap the vault, last_overwritten values, oldest_bay positions, full and empty channels, and zero-bay rejection",
            "project-context string eviction journal",
            "overwrite-eviction journaling bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-sonar-ping-archive",
            "Sonar ping archive",
            "sonar",
            """
            class ArchiveConfigError : public std::invalid_argument {
            public:
                explicit ArchiveConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ArchiveEmptyError : public std::runtime_error {
            public:
                explicit ArchiveEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class ArchiveFullError : public std::logic_error {
            public:
                explicit ArchiveFullError(const std::string& message) : std::logic_error(message) {}
            };
            class SonarPingArchive {
            public:
                explicit SonarPingArchive(std::size_t sweeps);
                void store(std::int32_t range_km);
                void force_store(std::int32_t range_km);
                std::int32_t replay();
                std::size_t pings() const;
                std::size_t sweeps() const;
                std::size_t oldest_sweep() const;
                std::optional<std::int32_t> last_faded() const;
                std::vector<std::string> archive_log() const;
            };
            """,
            """
            class ArchiveConfigError : public std::invalid_argument {
            public:
                explicit ArchiveConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ArchiveEmptyError : public std::runtime_error {
            public:
                explicit ArchiveEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class ArchiveFullError : public std::logic_error {
            public:
                explicit ArchiveFullError(const std::string& message) : std::logic_error(message) {}
            };
            class SonarPingArchive {
            public:
                explicit SonarPingArchive(std::size_t sweeps);
                void store(std::int32_t range_km);
                void force_store(std::int32_t range_km);
                std::int32_t replay();
                std::size_t pings() const;
                std::size_t sweeps() const;
                std::size_t oldest_sweep() const;
                std::optional<std::int32_t> last_faded() const;
                std::vector<std::string> archive_log() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t range_km = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
                std::vector<std::string> journal_;
                std::optional<std::int32_t> dropped_;
            };
            """,
            """
            SonarPingArchive::SonarPingArchive(std::size_t sweeps) {
                if (sweeps == 0) throw ArchiveConfigError("archive needs at least one sweep");
                cells_ = std::vector<Cell>(sweeps);
            }
            std::size_t SonarPingArchive::sweeps() const { return cells_.size(); }
            std::size_t SonarPingArchive::pings() const { return used_; }
            void SonarPingArchive::store(std::int32_t range_km) {
                if (used_ == cells_.size()) throw ArchiveFullError("archive is full");
                cells_[next_].occupied = true;
                cells_[next_].range_km = range_km;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            void SonarPingArchive::force_store(std::int32_t range_km) {
                if (used_ == cells_.size()) {
                    journal_.push_back("fade sweep=" + std::to_string(oldest_) + " range=" + std::to_string(cells_[oldest_].range_km));
                    dropped_ = cells_[oldest_].range_km;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].range_km = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                }
                store(range_km);
            }
            std::int32_t SonarPingArchive::replay() {
                if (used_ == 0) throw ArchiveEmptyError("archive is empty");
                std::int32_t value = cells_[oldest_].range_km;
                cells_[oldest_].occupied = false;
                cells_[oldest_].range_km = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t SonarPingArchive::oldest_sweep() const {
                if (used_ == 0) throw ArchiveEmptyError("archive is empty");
                return oldest_;
            }
            std::optional<std::int32_t> SonarPingArchive::last_faded() const { return dropped_; }
            std::vector<std::string> SonarPingArchive::archive_log() const { return journal_; }
            """,
            """
            SonarPingArchive::SonarPingArchive(std::size_t sweeps) {
                if (sweeps == 0) throw ArchiveConfigError("archive needs at least one sweep");
                cells_ = std::vector<Cell>(sweeps);
            }
            std::size_t SonarPingArchive::sweeps() const { return cells_.size(); }
            std::size_t SonarPingArchive::pings() const { return used_; }
            void SonarPingArchive::store(std::int32_t range_km) {
                if (used_ == cells_.size()) throw ArchiveFullError("archive is full");
                cells_[used_].occupied = true;
                cells_[used_].range_km = range_km;
                ++used_;
            }
            void SonarPingArchive::force_store(std::int32_t range_km) {
                if (used_ == cells_.size()) {
                    journal_.push_back("fade sweep=" + std::to_string(used_ - 1) + " range=" + std::to_string(cells_[used_ - 1].range_km));
                    dropped_ = cells_[used_ - 1].range_km;
                    cells_[used_ - 1].range_km = range_km;
                    return;
                }
                store(range_km);
            }
            std::int32_t SonarPingArchive::replay() {
                if (used_ == 0) throw ArchiveEmptyError("archive is empty");
                std::int32_t value = cells_[0].range_km;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].range_km = 0;
                --used_;
                return value;
            }
            std::size_t SonarPingArchive::oldest_sweep() const {
                if (used_ == 0) throw ArchiveEmptyError("archive is empty");
                return 0;
            }
            std::optional<std::int32_t> SonarPingArchive::last_faded() const { return dropped_; }
            std::vector<std::string> SonarPingArchive::archive_log() const { return journal_; }
            """,
            """
            SonarPingArchive archive(2);
            archive.store(8);
            archive.store(16);
            if (archive.pings() != 2U) return 1;
            if (archive.replay() != 8) return 2;
            archive.force_store(24);
            if (archive.replay() != 16) return 3;
            if (archive.replay() != 24) return 4;
            if (!archive.archive_log().empty()) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { SonarPingArchive zero(0); (void)zero; } catch (const ArchiveConfigError&) { threw = true; }
            if (!threw) return 1;
            SonarPingArchive archive(4);
            threw = false;
            try { archive.replay(); } catch (const ArchiveEmptyError&) { threw = true; }
            if (!threw) return 2;
            if (archive.last_faded().has_value()) return 3;
            archive.force_store(10);
            if (!archive.archive_log().empty()) return 4;
            archive.store(20);
            archive.store(30);
            archive.store(40);
            if (archive.oldest_sweep() != 0U) return 5;
            threw = false;
            try { archive.store(50); } catch (const ArchiveFullError&) { threw = true; }
            if (!threw) return 6;
            if (archive.pings() != 4U) return 7;
            archive.force_store(50);
            if (archive.oldest_sweep() != 1U) return 8;
            if (!archive.last_faded() || *archive.last_faded() != 10) return 9;
            if (archive.archive_log().size() != 1U) return 10;
            if (archive.archive_log()[0] != "fade sweep=0 range=10") return 11;
            if (archive.replay() != 20) return 12;
            archive.force_store(60);
            if (archive.archive_log().size() != 1U) return 13;
            archive.force_store(70);
            if (!archive.last_faded() || *archive.last_faded() != 30) return 14;
            if (archive.oldest_sweep() != 3U) return 15;
            if (archive.archive_log().size() != 2U) return 16;
            if (archive.archive_log()[1] != "fade sweep=2 range=30") return 17;
            if (archive.replay() != 40) return 18;
            if (archive.replay() != 50) return 19;
            if (archive.replay() != 60) return 20;
            if (archive.replay() != 70) return 21;
            if (archive.pings() != 0U) return 22;
            return 0;
            """,
            "a fixed archive of ping sweeps whose forced stores evict the oldest physical sweep and journal the exact sweep and range",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a forced store that evicts the newest occupant",
            "exact archive_log entries with sweep numbers after force_store sequences that wrap the archive, last_faded values, oldest_sweep positions, full and empty channels, and zero-sweep rejection",
            "eviction journal with sweep-slot numbering",
            "overwrite-eviction journaling bounded ring",
        ),
        c(
            "f26cbuf-buoy-telemetry-ring",
            "Buoy telemetry ring",
            "buoy_telemetry",
            """
            class BuoyConfigError : public std::invalid_argument {
            public:
                explicit BuoyConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BuoyEmptyError : public std::runtime_error {
            public:
                explicit BuoyEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class BuoyFullError : public std::logic_error {
            public:
                explicit BuoyFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BuoyTelemetryRing {
            public:
                explicit BuoyTelemetryRing(std::size_t beacons);
                void report(std::int64_t reading);
                void force_report(std::int64_t reading);
                std::int64_t retrieve();
                std::size_t readings() const;
                std::size_t beacons() const;
                std::size_t oldest_beacon() const;
                std::optional<std::int64_t> last_sunk() const;
                std::vector<std::string> buoy_log() const;
            };
            """,
            """
            class BuoyConfigError : public std::invalid_argument {
            public:
                explicit BuoyConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BuoyEmptyError : public std::runtime_error {
            public:
                explicit BuoyEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class BuoyFullError : public std::logic_error {
            public:
                explicit BuoyFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BuoyTelemetryRing {
            public:
                explicit BuoyTelemetryRing(std::size_t beacons);
                void report(std::int64_t reading);
                void force_report(std::int64_t reading);
                std::int64_t retrieve();
                std::size_t readings() const;
                std::size_t beacons() const;
                std::size_t oldest_beacon() const;
                std::optional<std::int64_t> last_sunk() const;
                std::vector<std::string> buoy_log() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t reading = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
                std::vector<std::string> journal_;
                std::optional<std::int64_t> dropped_;
            };
            """,
            """
            BuoyTelemetryRing::BuoyTelemetryRing(std::size_t beacons) {
                if (beacons == 0) throw BuoyConfigError("ring needs at least one beacon");
                cells_ = std::vector<Cell>(beacons);
            }
            std::size_t BuoyTelemetryRing::beacons() const { return cells_.size(); }
            std::size_t BuoyTelemetryRing::readings() const { return used_; }
            void BuoyTelemetryRing::report(std::int64_t reading) {
                if (used_ == cells_.size()) throw BuoyFullError("ring is full");
                cells_[next_].occupied = true;
                cells_[next_].reading = reading;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            void BuoyTelemetryRing::force_report(std::int64_t reading) {
                if (used_ == cells_.size()) {
                    journal_.push_back("sink beacon=" + std::to_string(oldest_) + " reading=" + std::to_string(cells_[oldest_].reading));
                    dropped_ = cells_[oldest_].reading;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].reading = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                }
                report(reading);
            }
            std::int64_t BuoyTelemetryRing::retrieve() {
                if (used_ == 0) throw BuoyEmptyError("ring is empty");
                std::int64_t value = cells_[oldest_].reading;
                cells_[oldest_].occupied = false;
                cells_[oldest_].reading = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t BuoyTelemetryRing::oldest_beacon() const {
                if (used_ == 0) throw BuoyEmptyError("ring is empty");
                return oldest_;
            }
            std::optional<std::int64_t> BuoyTelemetryRing::last_sunk() const { return dropped_; }
            std::vector<std::string> BuoyTelemetryRing::buoy_log() const { return journal_; }
            """,
            """
            BuoyTelemetryRing::BuoyTelemetryRing(std::size_t beacons) {
                if (beacons == 0) throw BuoyConfigError("ring needs at least one beacon");
                cells_ = std::vector<Cell>(beacons);
            }
            std::size_t BuoyTelemetryRing::beacons() const { return cells_.size(); }
            std::size_t BuoyTelemetryRing::readings() const { return used_; }
            void BuoyTelemetryRing::report(std::int64_t reading) {
                if (used_ == cells_.size()) throw BuoyFullError("ring is full");
                cells_[used_].occupied = true;
                cells_[used_].reading = reading;
                ++used_;
            }
            void BuoyTelemetryRing::force_report(std::int64_t reading) {
                if (used_ == cells_.size()) {
                    journal_.push_back("sink beacon=" + std::to_string(used_ - 1) + " reading=" + std::to_string(cells_[used_ - 1].reading));
                    dropped_ = cells_[used_ - 1].reading;
                    cells_[used_ - 1].reading = reading;
                    return;
                }
                report(reading);
            }
            std::int64_t BuoyTelemetryRing::retrieve() {
                if (used_ == 0) throw BuoyEmptyError("ring is empty");
                std::int64_t value = cells_[0].reading;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].reading = 0;
                --used_;
                return value;
            }
            std::size_t BuoyTelemetryRing::oldest_beacon() const {
                if (used_ == 0) throw BuoyEmptyError("ring is empty");
                return 0;
            }
            std::optional<std::int64_t> BuoyTelemetryRing::last_sunk() const { return dropped_; }
            std::vector<std::string> BuoyTelemetryRing::buoy_log() const { return journal_; }
            """,
            """
            BuoyTelemetryRing buoy(2);
            buoy.report(101);
            buoy.report(202);
            if (buoy.readings() != 2U) return 1;
            if (buoy.retrieve() != 101) return 2;
            buoy.force_report(303);
            if (buoy.retrieve() != 202) return 3;
            if (buoy.retrieve() != 303) return 4;
            if (!buoy.buoy_log().empty()) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { BuoyTelemetryRing zero(0); (void)zero; } catch (const BuoyConfigError&) { threw = true; }
            if (!threw) return 1;
            BuoyTelemetryRing buoy(3);
            threw = false;
            try { buoy.retrieve(); } catch (const BuoyEmptyError&) { threw = true; }
            if (!threw) return 2;
            if (buoy.last_sunk().has_value()) return 3;
            buoy.force_report(1001);
            if (!buoy.buoy_log().empty()) return 4;
            buoy.report(1002);
            buoy.report(1003);
            if (buoy.oldest_beacon() != 0U) return 5;
            threw = false;
            try { buoy.report(1004); } catch (const BuoyFullError&) { threw = true; }
            if (!threw) return 6;
            if (buoy.readings() != 3U) return 7;
            buoy.force_report(1004);
            if (buoy.oldest_beacon() != 1U) return 8;
            if (!buoy.last_sunk() || *buoy.last_sunk() != 1001) return 9;
            if (buoy.buoy_log().size() != 1U) return 10;
            if (buoy.buoy_log()[0] != "sink beacon=0 reading=1001") return 11;
            if (buoy.retrieve() != 1002) return 12;
            buoy.force_report(1005);
            if (buoy.buoy_log().size() != 1U) return 13;
            buoy.force_report(1006);
            if (!buoy.last_sunk() || *buoy.last_sunk() != 1003) return 14;
            if (buoy.oldest_beacon() != 0U) return 15;
            if (buoy.buoy_log().size() != 2U) return 16;
            if (buoy.buoy_log()[1] != "sink beacon=2 reading=1003") return 17;
            if (buoy.retrieve() != 1004) return 18;
            if (buoy.retrieve() != 1005) return 19;
            if (buoy.retrieve() != 1006) return 20;
            if (buoy.readings() != 0U) return 21;
            return 0;
            """,
            "a fixed ring of beacon cells whose forced reports evict the oldest physical beacon and journal the exact beacon and reading",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a forced report that evicts the newest occupant",
            "exact buoy_log entries with beacon numbers after force_report sequences that wrap the ring, last_sunk values, oldest_beacon positions, full and empty channels, and zero-beacon rejection",
            "int64 eviction journal with beacon slots",
            "overwrite-eviction journaling bounded ring",
        ),
        c(
            "f26cbuf-drone-mission-buffer",
            "Drone mission buffer",
            "drone_mission",
            """
            class MissionConfigError : public std::invalid_argument {
            public:
                explicit MissionConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class MissionEmptyError : public std::runtime_error {
            public:
                explicit MissionEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class MissionFullError : public std::logic_error {
            public:
                explicit MissionFullError(const std::string& message) : std::logic_error(message) {}
            };
            class DroneMissionBuffer {
            public:
                explicit DroneMissionBuffer(std::size_t slots);
                void queue_waypoint(const std::string& waypoint);
                void force_queue(const std::string& waypoint);
                std::string dispatch();
                std::size_t waypoints() const;
                std::size_t slots() const;
                std::size_t oldest_slot() const;
                std::optional<std::string> last_scrubbed() const;
                std::vector<std::string> mission_log() const;
            };
            """,
            """
            class MissionConfigError : public std::invalid_argument {
            public:
                explicit MissionConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class MissionEmptyError : public std::runtime_error {
            public:
                explicit MissionEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class MissionFullError : public std::logic_error {
            public:
                explicit MissionFullError(const std::string& message) : std::logic_error(message) {}
            };
            class DroneMissionBuffer {
            public:
                explicit DroneMissionBuffer(std::size_t slots);
                void queue_waypoint(const std::string& waypoint);
                void force_queue(const std::string& waypoint);
                std::string dispatch();
                std::size_t waypoints() const;
                std::size_t slots() const;
                std::size_t oldest_slot() const;
                std::optional<std::string> last_scrubbed() const;
                std::vector<std::string> mission_log() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string waypoint;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
                std::vector<std::string> journal_;
                std::optional<std::string> dropped_;
            };
            """,
            """
            DroneMissionBuffer::DroneMissionBuffer(std::size_t slots) {
                if (slots == 0) throw MissionConfigError("mission needs at least one slot");
                cells_ = std::vector<Cell>(slots);
            }
            std::size_t DroneMissionBuffer::slots() const { return cells_.size(); }
            std::size_t DroneMissionBuffer::waypoints() const { return used_; }
            void DroneMissionBuffer::queue_waypoint(const std::string& waypoint) {
                if (used_ == cells_.size()) throw MissionFullError("mission is full");
                cells_[next_].occupied = true;
                cells_[next_].waypoint = waypoint;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            void DroneMissionBuffer::force_queue(const std::string& waypoint) {
                if (used_ == cells_.size()) {
                    journal_.push_back("scrub slot=" + std::to_string(oldest_) + " waypoint=" + cells_[oldest_].waypoint);
                    dropped_ = cells_[oldest_].waypoint;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].waypoint.clear();
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                }
                queue_waypoint(waypoint);
            }
            std::string DroneMissionBuffer::dispatch() {
                if (used_ == 0) throw MissionEmptyError("mission is empty");
                std::string value = cells_[oldest_].waypoint;
                cells_[oldest_].occupied = false;
                cells_[oldest_].waypoint.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t DroneMissionBuffer::oldest_slot() const {
                if (used_ == 0) throw MissionEmptyError("mission is empty");
                return oldest_;
            }
            std::optional<std::string> DroneMissionBuffer::last_scrubbed() const { return dropped_; }
            std::vector<std::string> DroneMissionBuffer::mission_log() const { return journal_; }
            """,
            """
            DroneMissionBuffer::DroneMissionBuffer(std::size_t slots) {
                if (slots == 0) throw MissionConfigError("mission needs at least one slot");
                cells_ = std::vector<Cell>(slots);
            }
            std::size_t DroneMissionBuffer::slots() const { return cells_.size(); }
            std::size_t DroneMissionBuffer::waypoints() const { return used_; }
            void DroneMissionBuffer::queue_waypoint(const std::string& waypoint) {
                if (used_ == cells_.size()) throw MissionFullError("mission is full");
                cells_[used_].occupied = true;
                cells_[used_].waypoint = waypoint;
                ++used_;
            }
            void DroneMissionBuffer::force_queue(const std::string& waypoint) {
                if (used_ == cells_.size()) {
                    journal_.push_back("scrub slot=" + std::to_string(used_ - 1) + " waypoint=" + cells_[used_ - 1].waypoint);
                    dropped_ = cells_[used_ - 1].waypoint;
                    cells_[used_ - 1].waypoint = waypoint;
                    return;
                }
                queue_waypoint(waypoint);
            }
            std::string DroneMissionBuffer::dispatch() {
                if (used_ == 0) throw MissionEmptyError("mission is empty");
                std::string value = cells_[0].waypoint;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].waypoint.clear();
                --used_;
                return value;
            }
            std::size_t DroneMissionBuffer::oldest_slot() const {
                if (used_ == 0) throw MissionEmptyError("mission is empty");
                return 0;
            }
            std::optional<std::string> DroneMissionBuffer::last_scrubbed() const { return dropped_; }
            std::vector<std::string> DroneMissionBuffer::mission_log() const { return journal_; }
            """,
            """
            DroneMissionBuffer mission(2);
            mission.queue_waypoint("alpha");
            mission.queue_waypoint("bravo");
            if (mission.waypoints() != 2U) return 1;
            if (mission.dispatch() != "alpha") return 2;
            mission.force_queue("charlie");
            if (mission.dispatch() != "bravo") return 3;
            if (mission.dispatch() != "charlie") return 4;
            if (!mission.mission_log().empty()) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { DroneMissionBuffer zero(0); (void)zero; } catch (const MissionConfigError&) { threw = true; }
            if (!threw) return 1;
            DroneMissionBuffer mission(3);
            threw = false;
            try { mission.dispatch(); } catch (const MissionEmptyError&) { threw = true; }
            if (!threw) return 2;
            if (mission.last_scrubbed().has_value()) return 3;
            mission.force_queue("alpha");
            if (!mission.mission_log().empty()) return 4;
            mission.queue_waypoint("bravo");
            mission.queue_waypoint("charlie");
            if (mission.oldest_slot() != 0U) return 5;
            threw = false;
            try { mission.queue_waypoint("delta"); } catch (const MissionFullError&) { threw = true; }
            if (!threw) return 6;
            if (mission.waypoints() != 3U) return 7;
            mission.force_queue("delta");
            if (mission.oldest_slot() != 1U) return 8;
            if (!mission.last_scrubbed() || *mission.last_scrubbed() != "alpha") return 9;
            if (mission.mission_log().size() != 1U) return 10;
            if (mission.mission_log()[0] != "scrub slot=0 waypoint=alpha") return 11;
            if (mission.dispatch() != "bravo") return 12;
            mission.force_queue("echo");
            if (mission.mission_log().size() != 1U) return 13;
            mission.force_queue("foxtrot");
            if (!mission.last_scrubbed() || *mission.last_scrubbed() != "charlie") return 14;
            if (mission.oldest_slot() != 0U) return 15;
            if (mission.mission_log().size() != 2U) return 16;
            if (mission.mission_log()[1] != "scrub slot=2 waypoint=charlie") return 17;
            if (mission.dispatch() != "delta") return 18;
            if (mission.dispatch() != "echo") return 19;
            if (mission.dispatch() != "foxtrot") return 20;
            if (mission.waypoints() != 0U) return 21;
            return 0;
            """,
            "a fixed buffer of waypoint slots whose forced queues evict the oldest physical slot and journal the exact slot and waypoint",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a forced queue that evicts the newest occupant",
            "exact mission_log entries with slot numbers after force_queue sequences that wrap the buffer, last_scrubbed values, oldest_slot positions, full and empty channels, and zero-slot rejection",
            "project-context mission eviction journal",
            "overwrite-eviction journaling bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-rover-traverse-ring",
            "Rover traverse ring",
            "rover_traverse",
            """
            class TraverseConfigError : public std::invalid_argument {
            public:
                explicit TraverseConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TraverseEmptyError : public std::runtime_error {
            public:
                explicit TraverseEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TraverseFullError : public std::logic_error {
            public:
                explicit TraverseFullError(const std::string& message) : std::logic_error(message) {}
            };
            class RoverTraverseRing {
            public:
                explicit RoverTraverseRing(std::size_t track_cells);
                void record_odo(std::int64_t odometer);
                void force_record(std::int64_t odometer);
                std::int64_t replay();
                std::size_t readings() const;
                std::size_t track_cells() const;
                std::size_t oldest_cell() const;
                std::optional<std::int64_t> last_lost() const;
                std::vector<std::string> traverse_log() const;
            };
            """,
            """
            class TraverseConfigError : public std::invalid_argument {
            public:
                explicit TraverseConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TraverseEmptyError : public std::runtime_error {
            public:
                explicit TraverseEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TraverseFullError : public std::logic_error {
            public:
                explicit TraverseFullError(const std::string& message) : std::logic_error(message) {}
            };
            class RoverTraverseRing {
            public:
                explicit RoverTraverseRing(std::size_t track_cells);
                void record_odo(std::int64_t odometer);
                void force_record(std::int64_t odometer);
                std::int64_t replay();
                std::size_t readings() const;
                std::size_t track_cells() const;
                std::size_t oldest_cell() const;
                std::optional<std::int64_t> last_lost() const;
                std::vector<std::string> traverse_log() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t odometer = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
                std::vector<std::string> journal_;
                std::optional<std::int64_t> dropped_;
            };
            """,
            """
            RoverTraverseRing::RoverTraverseRing(std::size_t track_cells) {
                if (track_cells == 0) throw TraverseConfigError("traverse needs at least one cell");
                cells_ = std::vector<Cell>(track_cells);
            }
            std::size_t RoverTraverseRing::track_cells() const { return cells_.size(); }
            std::size_t RoverTraverseRing::readings() const { return used_; }
            void RoverTraverseRing::record_odo(std::int64_t odometer) {
                if (used_ == cells_.size()) throw TraverseFullError("traverse is full");
                cells_[next_].occupied = true;
                cells_[next_].odometer = odometer;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            void RoverTraverseRing::force_record(std::int64_t odometer) {
                if (used_ == cells_.size()) {
                    journal_.push_back("lost cell=" + std::to_string(oldest_) + " odo=" + std::to_string(cells_[oldest_].odometer));
                    dropped_ = cells_[oldest_].odometer;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].odometer = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                }
                record_odo(odometer);
            }
            std::int64_t RoverTraverseRing::replay() {
                if (used_ == 0) throw TraverseEmptyError("traverse is empty");
                std::int64_t value = cells_[oldest_].odometer;
                cells_[oldest_].occupied = false;
                cells_[oldest_].odometer = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t RoverTraverseRing::oldest_cell() const {
                if (used_ == 0) throw TraverseEmptyError("traverse is empty");
                return oldest_;
            }
            std::optional<std::int64_t> RoverTraverseRing::last_lost() const { return dropped_; }
            std::vector<std::string> RoverTraverseRing::traverse_log() const { return journal_; }
            """,
            """
            RoverTraverseRing::RoverTraverseRing(std::size_t track_cells) {
                if (track_cells == 0) throw TraverseConfigError("traverse needs at least one cell");
                cells_ = std::vector<Cell>(track_cells);
            }
            std::size_t RoverTraverseRing::track_cells() const { return cells_.size(); }
            std::size_t RoverTraverseRing::readings() const { return used_; }
            void RoverTraverseRing::record_odo(std::int64_t odometer) {
                if (used_ == cells_.size()) throw TraverseFullError("traverse is full");
                cells_[used_].occupied = true;
                cells_[used_].odometer = odometer;
                ++used_;
            }
            void RoverTraverseRing::force_record(std::int64_t odometer) {
                if (used_ == cells_.size()) {
                    journal_.push_back("lost cell=" + std::to_string(used_ - 1) + " odo=" + std::to_string(cells_[used_ - 1].odometer));
                    dropped_ = cells_[used_ - 1].odometer;
                    cells_[used_ - 1].odometer = odometer;
                    return;
                }
                record_odo(odometer);
            }
            std::int64_t RoverTraverseRing::replay() {
                if (used_ == 0) throw TraverseEmptyError("traverse is empty");
                std::int64_t value = cells_[0].odometer;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].odometer = 0;
                --used_;
                return value;
            }
            std::size_t RoverTraverseRing::oldest_cell() const {
                if (used_ == 0) throw TraverseEmptyError("traverse is empty");
                return 0;
            }
            std::optional<std::int64_t> RoverTraverseRing::last_lost() const { return dropped_; }
            std::vector<std::string> RoverTraverseRing::traverse_log() const { return journal_; }
            """,
            """
            RoverTraverseRing rover(2);
            rover.record_odo(500);
            rover.record_odo(900);
            if (rover.readings() != 2U) return 1;
            if (rover.replay() != 500) return 2;
            rover.force_record(1300);
            if (rover.replay() != 900) return 3;
            if (rover.replay() != 1300) return 4;
            if (!rover.traverse_log().empty()) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { RoverTraverseRing zero(0); (void)zero; } catch (const TraverseConfigError&) { threw = true; }
            if (!threw) return 1;
            RoverTraverseRing rover(4);
            threw = false;
            try { rover.replay(); } catch (const TraverseEmptyError&) { threw = true; }
            if (!threw) return 2;
            if (rover.last_lost().has_value()) return 3;
            rover.force_record(100);
            if (!rover.traverse_log().empty()) return 4;
            rover.record_odo(200);
            rover.record_odo(300);
            rover.record_odo(400);
            if (rover.oldest_cell() != 0U) return 5;
            threw = false;
            try { rover.record_odo(500); } catch (const TraverseFullError&) { threw = true; }
            if (!threw) return 6;
            if (rover.readings() != 4U) return 7;
            rover.force_record(500);
            if (rover.oldest_cell() != 1U) return 8;
            if (!rover.last_lost() || *rover.last_lost() != 100) return 9;
            if (rover.traverse_log().size() != 1U) return 10;
            if (rover.traverse_log()[0] != "lost cell=0 odo=100") return 11;
            if (rover.replay() != 200) return 12;
            rover.force_record(600);
            if (rover.traverse_log().size() != 1U) return 13;
            rover.force_record(700);
            if (!rover.last_lost() || *rover.last_lost() != 300) return 14;
            if (rover.oldest_cell() != 3U) return 15;
            if (rover.traverse_log().size() != 2U) return 16;
            if (rover.traverse_log()[1] != "lost cell=2 odo=300") return 17;
            if (rover.replay() != 400) return 18;
            if (rover.replay() != 500) return 19;
            if (rover.replay() != 600) return 20;
            if (rover.replay() != 700) return 21;
            if (rover.readings() != 0U) return 22;
            return 0;
            """,
            "a fixed ring of odometer cells whose forced records evict the oldest physical cell and journal the exact cell and reading",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a forced record that evicts the newest occupant",
            "exact traverse_log entries with cell numbers after force_record sequences that wrap the ring, last_lost values, oldest_cell positions, full and empty channels, and zero-cell rejection",
            "int64 eviction journal with track cells",
            "overwrite-eviction journaling bounded ring",
        ),
        c(
            "f26cbuf-bathyscaphe-dive-log",
            "Bathyscaphe dive log",
            "bathyscaphe",
            """
            class DiveConfigError : public std::invalid_argument {
            public:
                explicit DiveConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DiveEmptyError : public std::runtime_error {
            public:
                explicit DiveEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DiveFullError : public std::logic_error {
            public:
                explicit DiveFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BathyscapheDiveLog {
            public:
                explicit BathyscapheDiveLog(std::size_t log_cells);
                void log_depth(std::int32_t depth);
                void force_depth(std::int32_t depth);
                std::int32_t surface();
                std::size_t depths() const;
                std::size_t log_cells() const;
                std::size_t oldest_cell() const;
                std::optional<std::int32_t> last_purged() const;
                std::vector<std::string> dive_journal() const;
            };
            """,
            """
            class DiveConfigError : public std::invalid_argument {
            public:
                explicit DiveConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DiveEmptyError : public std::runtime_error {
            public:
                explicit DiveEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DiveFullError : public std::logic_error {
            public:
                explicit DiveFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BathyscapheDiveLog {
            public:
                explicit BathyscapheDiveLog(std::size_t log_cells);
                void log_depth(std::int32_t depth);
                void force_depth(std::int32_t depth);
                std::int32_t surface();
                std::size_t depths() const;
                std::size_t log_cells() const;
                std::size_t oldest_cell() const;
                std::optional<std::int32_t> last_purged() const;
                std::vector<std::string> dive_journal() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t depth = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
                std::vector<std::string> journal_;
                std::optional<std::int32_t> dropped_;
            };
            """,
            """
            BathyscapheDiveLog::BathyscapheDiveLog(std::size_t log_cells) {
                if (log_cells == 0) throw DiveConfigError("dive log needs at least one cell");
                cells_ = std::vector<Cell>(log_cells);
            }
            std::size_t BathyscapheDiveLog::log_cells() const { return cells_.size(); }
            std::size_t BathyscapheDiveLog::depths() const { return used_; }
            void BathyscapheDiveLog::log_depth(std::int32_t depth) {
                if (used_ == cells_.size()) throw DiveFullError("dive log is full");
                cells_[next_].occupied = true;
                cells_[next_].depth = depth;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            void BathyscapheDiveLog::force_depth(std::int32_t depth) {
                if (used_ == cells_.size()) {
                    journal_.push_back("purge cell=" + std::to_string(oldest_) + " depth=" + std::to_string(cells_[oldest_].depth));
                    dropped_ = cells_[oldest_].depth;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].depth = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                }
                log_depth(depth);
            }
            std::int32_t BathyscapheDiveLog::surface() {
                if (used_ == 0) throw DiveEmptyError("dive log is empty");
                std::int32_t value = cells_[oldest_].depth;
                cells_[oldest_].occupied = false;
                cells_[oldest_].depth = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t BathyscapheDiveLog::oldest_cell() const {
                if (used_ == 0) throw DiveEmptyError("dive log is empty");
                return oldest_;
            }
            std::optional<std::int32_t> BathyscapheDiveLog::last_purged() const { return dropped_; }
            std::vector<std::string> BathyscapheDiveLog::dive_journal() const { return journal_; }
            """,
            """
            BathyscapheDiveLog::BathyscapheDiveLog(std::size_t log_cells) {
                if (log_cells == 0) throw DiveConfigError("dive log needs at least one cell");
                cells_ = std::vector<Cell>(log_cells);
            }
            std::size_t BathyscapheDiveLog::log_cells() const { return cells_.size(); }
            std::size_t BathyscapheDiveLog::depths() const { return used_; }
            void BathyscapheDiveLog::log_depth(std::int32_t depth) {
                if (used_ == cells_.size()) throw DiveFullError("dive log is full");
                cells_[used_].occupied = true;
                cells_[used_].depth = depth;
                ++used_;
            }
            void BathyscapheDiveLog::force_depth(std::int32_t depth) {
                if (used_ == cells_.size()) {
                    journal_.push_back("purge cell=" + std::to_string(used_ - 1) + " depth=" + std::to_string(cells_[used_ - 1].depth));
                    dropped_ = cells_[used_ - 1].depth;
                    cells_[used_ - 1].depth = depth;
                    return;
                }
                log_depth(depth);
            }
            std::int32_t BathyscapheDiveLog::surface() {
                if (used_ == 0) throw DiveEmptyError("dive log is empty");
                std::int32_t value = cells_[0].depth;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].depth = 0;
                --used_;
                return value;
            }
            std::size_t BathyscapheDiveLog::oldest_cell() const {
                if (used_ == 0) throw DiveEmptyError("dive log is empty");
                return 0;
            }
            std::optional<std::int32_t> BathyscapheDiveLog::last_purged() const { return dropped_; }
            std::vector<std::string> BathyscapheDiveLog::dive_journal() const { return journal_; }
            """,
            """
            BathyscapheDiveLog dive(2);
            dive.log_depth(90);
            dive.log_depth(180);
            if (dive.depths() != 2U) return 1;
            if (dive.surface() != 90) return 2;
            dive.force_depth(270);
            if (dive.surface() != 180) return 3;
            if (dive.surface() != 270) return 4;
            if (!dive.dive_journal().empty()) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { BathyscapheDiveLog zero(0); (void)zero; } catch (const DiveConfigError&) { threw = true; }
            if (!threw) return 1;
            BathyscapheDiveLog dive(3);
            threw = false;
            try { dive.surface(); } catch (const DiveEmptyError&) { threw = true; }
            if (!threw) return 2;
            if (dive.last_purged().has_value()) return 3;
            dive.force_depth(110);
            if (!dive.dive_journal().empty()) return 4;
            dive.log_depth(220);
            dive.log_depth(330);
            if (dive.oldest_cell() != 0U) return 5;
            threw = false;
            try { dive.log_depth(440); } catch (const DiveFullError&) { threw = true; }
            if (!threw) return 6;
            if (dive.depths() != 3U) return 7;
            dive.force_depth(440);
            if (dive.oldest_cell() != 1U) return 8;
            if (!dive.last_purged() || *dive.last_purged() != 110) return 9;
            if (dive.dive_journal().size() != 1U) return 10;
            if (dive.dive_journal()[0] != "purge cell=0 depth=110") return 11;
            if (dive.surface() != 220) return 12;
            dive.force_depth(550);
            if (dive.dive_journal().size() != 1U) return 13;
            dive.force_depth(660);
            if (!dive.last_purged() || *dive.last_purged() != 330) return 14;
            if (dive.oldest_cell() != 0U) return 15;
            if (dive.dive_journal().size() != 2U) return 16;
            if (dive.dive_journal()[1] != "purge cell=2 depth=330") return 17;
            if (dive.surface() != 440) return 18;
            if (dive.surface() != 550) return 19;
            if (dive.surface() != 660) return 20;
            if (dive.depths() != 0U) return 21;
            return 0;
            """,
            "a fixed log of depth cells whose forced entries evict the oldest physical cell and journal the exact cell and depth",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a forced entry that evicts the newest occupant",
            "exact dive_journal entries with cell numbers after force_depth sequences that wrap the log, last_purged values, oldest_cell positions, full and empty channels, and zero-cell rejection",
            "depth eviction journal with purge slots",
            "overwrite-eviction journaling bounded ring",
        ),
        c(
            "f26cbuf-ice-core-sample-ring",
            "Ice core sample ring",
            "ice_core",
            """
            class CoreConfigError : public std::invalid_argument {
            public:
                explicit CoreConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CoreEmptyError : public std::runtime_error {
            public:
                explicit CoreEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class CoreFullError : public std::logic_error {
            public:
                explicit CoreFullError(const std::string& message) : std::logic_error(message) {}
            };
            class IceCoreSampleRing {
            public:
                explicit IceCoreSampleRing(std::size_t rack_cells);
                void store_core(const std::string& core);
                void force_core(const std::string& core);
                std::string thaw();
                std::size_t cores() const;
                std::size_t rack_cells() const;
                std::size_t oldest_cell() const;
                std::optional<std::string> last_melted() const;
                std::vector<std::string> core_log() const;
            };
            """,
            """
            class CoreConfigError : public std::invalid_argument {
            public:
                explicit CoreConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class CoreEmptyError : public std::runtime_error {
            public:
                explicit CoreEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class CoreFullError : public std::logic_error {
            public:
                explicit CoreFullError(const std::string& message) : std::logic_error(message) {}
            };
            class IceCoreSampleRing {
            public:
                explicit IceCoreSampleRing(std::size_t rack_cells);
                void store_core(const std::string& core);
                void force_core(const std::string& core);
                std::string thaw();
                std::size_t cores() const;
                std::size_t rack_cells() const;
                std::size_t oldest_cell() const;
                std::optional<std::string> last_melted() const;
                std::vector<std::string> core_log() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string core;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
                std::vector<std::string> journal_;
                std::optional<std::string> dropped_;
            };
            """,
            """
            IceCoreSampleRing::IceCoreSampleRing(std::size_t rack_cells) {
                if (rack_cells == 0) throw CoreConfigError("rack needs at least one cell");
                cells_ = std::vector<Cell>(rack_cells);
            }
            std::size_t IceCoreSampleRing::rack_cells() const { return cells_.size(); }
            std::size_t IceCoreSampleRing::cores() const { return used_; }
            void IceCoreSampleRing::store_core(const std::string& core) {
                if (used_ == cells_.size()) throw CoreFullError("rack is full");
                cells_[next_].occupied = true;
                cells_[next_].core = core;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            void IceCoreSampleRing::force_core(const std::string& core) {
                if (used_ == cells_.size()) {
                    journal_.push_back("melt cell=" + std::to_string(oldest_) + " core=" + cells_[oldest_].core);
                    dropped_ = cells_[oldest_].core;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].core.clear();
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                }
                store_core(core);
            }
            std::string IceCoreSampleRing::thaw() {
                if (used_ == 0) throw CoreEmptyError("rack is empty");
                std::string value = cells_[oldest_].core;
                cells_[oldest_].occupied = false;
                cells_[oldest_].core.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t IceCoreSampleRing::oldest_cell() const {
                if (used_ == 0) throw CoreEmptyError("rack is empty");
                return oldest_;
            }
            std::optional<std::string> IceCoreSampleRing::last_melted() const { return dropped_; }
            std::vector<std::string> IceCoreSampleRing::core_log() const { return journal_; }
            """,
            """
            IceCoreSampleRing::IceCoreSampleRing(std::size_t rack_cells) {
                if (rack_cells == 0) throw CoreConfigError("rack needs at least one cell");
                cells_ = std::vector<Cell>(rack_cells);
            }
            std::size_t IceCoreSampleRing::rack_cells() const { return cells_.size(); }
            std::size_t IceCoreSampleRing::cores() const { return used_; }
            void IceCoreSampleRing::store_core(const std::string& core) {
                if (used_ == cells_.size()) throw CoreFullError("rack is full");
                cells_[used_].occupied = true;
                cells_[used_].core = core;
                ++used_;
            }
            void IceCoreSampleRing::force_core(const std::string& core) {
                if (used_ == cells_.size()) {
                    journal_.push_back("melt cell=" + std::to_string(used_ - 1) + " core=" + cells_[used_ - 1].core);
                    dropped_ = cells_[used_ - 1].core;
                    cells_[used_ - 1].core = core;
                    return;
                }
                store_core(core);
            }
            std::string IceCoreSampleRing::thaw() {
                if (used_ == 0) throw CoreEmptyError("rack is empty");
                std::string value = cells_[0].core;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].core.clear();
                --used_;
                return value;
            }
            std::size_t IceCoreSampleRing::oldest_cell() const {
                if (used_ == 0) throw CoreEmptyError("rack is empty");
                return 0;
            }
            std::optional<std::string> IceCoreSampleRing::last_melted() const { return dropped_; }
            std::vector<std::string> IceCoreSampleRing::core_log() const { return journal_; }
            """,
            """
            IceCoreSampleRing rack(2);
            rack.store_core("vostok");
            rack.store_core("domec");
            if (rack.cores() != 2U) return 1;
            if (rack.thaw() != "vostok") return 2;
            rack.force_core("byrd");
            if (rack.thaw() != "domec") return 3;
            if (rack.thaw() != "byrd") return 4;
            if (!rack.core_log().empty()) return 5;
            return 0;
            """,
            """
            bool threw = false;
            try { IceCoreSampleRing zero(0); (void)zero; } catch (const CoreConfigError&) { threw = true; }
            if (!threw) return 1;
            IceCoreSampleRing rack(3);
            threw = false;
            try { rack.thaw(); } catch (const CoreEmptyError&) { threw = true; }
            if (!threw) return 2;
            if (rack.last_melted().has_value()) return 3;
            rack.force_core("vostok");
            if (!rack.core_log().empty()) return 4;
            rack.store_core("domec");
            rack.store_core("byrd");
            if (rack.oldest_cell() != 0U) return 5;
            threw = false;
            try { rack.store_core("grip"); } catch (const CoreFullError&) { threw = true; }
            if (!threw) return 6;
            if (rack.cores() != 3U) return 7;
            rack.force_core("grip");
            if (rack.oldest_cell() != 1U) return 8;
            if (!rack.last_melted() || *rack.last_melted() != "vostok") return 9;
            if (rack.core_log().size() != 1U) return 10;
            if (rack.core_log()[0] != "melt cell=0 core=vostok") return 11;
            if (rack.thaw() != "domec") return 12;
            rack.force_core("law");
            if (rack.core_log().size() != 1U) return 13;
            rack.force_core("epica");
            if (!rack.last_melted() || *rack.last_melted() != "byrd") return 14;
            if (rack.oldest_cell() != 0U) return 15;
            if (rack.core_log().size() != 2U) return 16;
            if (rack.core_log()[1] != "melt cell=2 core=byrd") return 17;
            if (rack.thaw() != "grip") return 18;
            if (rack.thaw() != "law") return 19;
            if (rack.thaw() != "epica") return 20;
            if (rack.cores() != 0U) return 21;
            return 0;
            """,
            "a fixed rack of core cells whose forced stores evict the oldest physical cell and journal the exact cell and core",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, or a forced store that evicts the newest occupant",
            "exact core_log entries with cell numbers after force_core sequences that wrap the rack, last_melted values, oldest_cell positions, full and empty channels, and zero-cell rejection",
            "string eviction journal with rack cells",
            "overwrite-eviction journaling bounded ring",
        ),
        c(
            "f26cbuf-relay-baton-loop",
            "Relay baton loop",
            "relay_race",
            """
            class RelayConfigError : public std::invalid_argument {
            public:
                explicit RelayConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RelayEmptyError : public std::runtime_error {
            public:
                explicit RelayEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class RelayFullError : public std::logic_error {
            public:
                explicit RelayFullError(const std::string& message) : std::logic_error(message) {}
            };
            class RelayBatonLoop {
            public:
                explicit RelayBatonLoop(std::size_t legs);
                RelayBatonLoop(const RelayBatonLoop& other);
                RelayBatonLoop(RelayBatonLoop&& other) noexcept;
                RelayBatonLoop& operator=(const RelayBatonLoop& other);
                RelayBatonLoop& operator=(RelayBatonLoop&& other) noexcept;
                void hand_off(std::int32_t bib);
                std::int32_t finish();
                std::size_t hand_to(RelayBatonLoop& dest, std::size_t count);
                std::size_t runners() const;
                std::size_t legs() const;
                std::size_t oldest_leg() const;
            };
            """,
            """
            class RelayConfigError : public std::invalid_argument {
            public:
                explicit RelayConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class RelayEmptyError : public std::runtime_error {
            public:
                explicit RelayEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class RelayFullError : public std::logic_error {
            public:
                explicit RelayFullError(const std::string& message) : std::logic_error(message) {}
            };
            class RelayBatonLoop {
            public:
                explicit RelayBatonLoop(std::size_t legs);
                RelayBatonLoop(const RelayBatonLoop& other);
                RelayBatonLoop(RelayBatonLoop&& other) noexcept;
                RelayBatonLoop& operator=(const RelayBatonLoop& other);
                RelayBatonLoop& operator=(RelayBatonLoop&& other) noexcept;
                void hand_off(std::int32_t bib);
                std::int32_t finish();
                std::size_t hand_to(RelayBatonLoop& dest, std::size_t count);
                std::size_t runners() const;
                std::size_t legs() const;
                std::size_t oldest_leg() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t bib = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            RelayBatonLoop::RelayBatonLoop(std::size_t legs) {
                if (legs == 0) throw RelayConfigError("relay needs at least one leg");
                cells_ = std::vector<Cell>(legs);
            }
            RelayBatonLoop::RelayBatonLoop(const RelayBatonLoop& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            RelayBatonLoop::RelayBatonLoop(RelayBatonLoop&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            RelayBatonLoop& RelayBatonLoop::operator=(const RelayBatonLoop& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            RelayBatonLoop& RelayBatonLoop::operator=(RelayBatonLoop&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t RelayBatonLoop::legs() const { return cells_.size(); }
            std::size_t RelayBatonLoop::runners() const { return used_; }
            void RelayBatonLoop::hand_off(std::int32_t bib) {
                if (used_ == cells_.size()) throw RelayFullError("relay is full");
                cells_[next_].occupied = true;
                cells_[next_].bib = bib;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t RelayBatonLoop::finish() {
                if (used_ == 0) throw RelayEmptyError("relay is empty");
                std::int32_t value = cells_[oldest_].bib;
                cells_[oldest_].occupied = false;
                cells_[oldest_].bib = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t RelayBatonLoop::oldest_leg() const {
                if (used_ == 0) throw RelayEmptyError("relay is empty");
                return oldest_;
            }
            std::size_t RelayBatonLoop::hand_to(RelayBatonLoop& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.next_].occupied = true;
                    dest.cells_[dest.next_].bib = cells_[oldest_].bib;
                    dest.next_ = (dest.next_ + 1) % dest.cells_.size();
                    ++dest.used_;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].bib = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            RelayBatonLoop::RelayBatonLoop(std::size_t legs) {
                if (legs == 0) throw RelayConfigError("relay needs at least one leg");
                cells_ = std::vector<Cell>(legs);
            }
            RelayBatonLoop::RelayBatonLoop(const RelayBatonLoop& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            RelayBatonLoop::RelayBatonLoop(RelayBatonLoop&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            RelayBatonLoop& RelayBatonLoop::operator=(const RelayBatonLoop& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            RelayBatonLoop& RelayBatonLoop::operator=(RelayBatonLoop&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t RelayBatonLoop::legs() const { return cells_.size(); }
            std::size_t RelayBatonLoop::runners() const { return used_; }
            void RelayBatonLoop::hand_off(std::int32_t bib) {
                if (used_ == cells_.size()) throw RelayFullError("relay is full");
                cells_[used_].occupied = true;
                cells_[used_].bib = bib;
                ++used_;
            }
            std::int32_t RelayBatonLoop::finish() {
                if (used_ == 0) throw RelayEmptyError("relay is empty");
                std::int32_t value = cells_[0].bib;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].bib = 0;
                --used_;
                return value;
            }
            std::size_t RelayBatonLoop::oldest_leg() const {
                if (used_ == 0) throw RelayEmptyError("relay is empty");
                return 0;
            }
            std::size_t RelayBatonLoop::hand_to(RelayBatonLoop& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.used_].occupied = true;
                    dest.cells_[dest.used_].bib = cells_[used_ - 1].bib;
                    ++dest.used_;
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].bib = 0;
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            RelayBatonLoop loop(2);
            loop.hand_off(21);
            loop.hand_off(22);
            if (loop.runners() != 2U) return 1;
            if (loop.finish() != 21) return 2;
            loop.hand_off(23);
            if (loop.finish() != 22) return 3;
            if (loop.finish() != 23) return 4;
            RelayBatonLoop duo(3);
            loop.hand_off(24);
            if (loop.hand_to(duo, 1) != 1U) return 5;
            if (duo.finish() != 24) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { RelayBatonLoop zero(0); (void)zero; } catch (const RelayConfigError&) { threw = true; }
            if (!threw) return 1;
            RelayBatonLoop loop(3);
            threw = false;
            try { loop.finish(); } catch (const RelayEmptyError&) { threw = true; }
            if (!threw) return 2;
            loop.hand_off(7);
            loop.hand_off(8);
            loop.hand_off(9);
            threw = false;
            try { loop.hand_off(10); } catch (const RelayFullError&) { threw = true; }
            if (!threw) return 3;
            if (loop.finish() != 7) return 4;
            if (loop.finish() != 8) return 5;
            loop.hand_off(10);
            loop.hand_off(11);
            if (loop.oldest_leg() != 2U) return 6;
            RelayBatonLoop replica(loop);
            if (replica.oldest_leg() != 2U) return 7;
            if (replica.finish() != 9) return 8;
            if (replica.finish() != 10) return 9;
            if (replica.finish() != 11) return 10;
            if (replica.runners() != 0U) return 11;
            if (loop.runners() != 3U) return 12;
            RelayBatonLoop assigned(2);
            assigned = loop;
            if (assigned.legs() != 3U) return 13;
            if (assigned.oldest_leg() != 2U) return 14;
            RelayBatonLoop moved(std::move(loop));
            if (moved.oldest_leg() != 2U) return 15;
            if (loop.runners() != 0U) return 16;
            if (loop.legs() != 3U) return 17;
            threw = false;
            try { loop.oldest_leg(); } catch (const RelayEmptyError&) { threw = true; }
            if (!threw) return 18;
            RelayBatonLoop target(5);
            target = std::move(moved);
            if (target.legs() != 3U) return 19;
            if (target.oldest_leg() != 2U) return 20;
            if (target.finish() != 9) return 21;
            if (moved.runners() != 0U) return 22;
            RelayBatonLoop source(3);
            source.hand_off(1);
            source.hand_off(2);
            source.hand_off(3);
            if (source.finish() != 1) return 23;
            source.hand_off(4);
            RelayBatonLoop sink(2);
            if (source.hand_to(sink, 5) != 2U) return 24;
            if (source.runners() != 1U) return 25;
            if (sink.finish() != 2) return 26;
            if (sink.finish() != 3) return 27;
            if (source.finish() != 4) return 28;
            source.hand_off(5);
            source.hand_off(6);
            RelayBatonLoop cup(3);
            if (source.hand_to(cup, 1) != 1U) return 29;
            if (cup.finish() != 5) return 30;
            if (source.finish() != 6) return 31;
            return 0;
            """,
            "a fixed loop of bib cells whose copies preserve exact physical layout, whose moves empty the source, and whose transfers move oldest-first",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, a copy that repacks cells from slot zero, or a transfer that moves newest-first",
            "copy and move layout preservation after wraparound, moved-from source state, hand_to FIFO order with destination-full stop, full and empty channels, and zero-leg rejection",
            "copy/move layout semantics and FIFO transfer discipline",
            "copy/move and transfer-edge bounded ring",
        ),
        c(
            "f26cbuf-bucket-brigade-line",
            "Bucket brigade line",
            "bucket_brigade",
            """
            class BrigadeConfigError : public std::invalid_argument {
            public:
                explicit BrigadeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BrigadeEmptyError : public std::runtime_error {
            public:
                explicit BrigadeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class BrigadeFullError : public std::logic_error {
            public:
                explicit BrigadeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BucketBrigadeLine {
            public:
                explicit BucketBrigadeLine(std::size_t stations);
                BucketBrigadeLine(const BucketBrigadeLine& other);
                BucketBrigadeLine(BucketBrigadeLine&& other) noexcept;
                BucketBrigadeLine& operator=(const BucketBrigadeLine& other);
                BucketBrigadeLine& operator=(BucketBrigadeLine&& other) noexcept;
                void pass_bucket(std::int64_t pail);
                std::int64_t empty_bucket();
                std::size_t hand_to(BucketBrigadeLine& dest, std::size_t count);
                std::size_t pails() const;
                std::size_t stations() const;
                std::size_t oldest_station() const;
            };
            """,
            """
            class BrigadeConfigError : public std::invalid_argument {
            public:
                explicit BrigadeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BrigadeEmptyError : public std::runtime_error {
            public:
                explicit BrigadeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class BrigadeFullError : public std::logic_error {
            public:
                explicit BrigadeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BucketBrigadeLine {
            public:
                explicit BucketBrigadeLine(std::size_t stations);
                BucketBrigadeLine(const BucketBrigadeLine& other);
                BucketBrigadeLine(BucketBrigadeLine&& other) noexcept;
                BucketBrigadeLine& operator=(const BucketBrigadeLine& other);
                BucketBrigadeLine& operator=(BucketBrigadeLine&& other) noexcept;
                void pass_bucket(std::int64_t pail);
                std::int64_t empty_bucket();
                std::size_t hand_to(BucketBrigadeLine& dest, std::size_t count);
                std::size_t pails() const;
                std::size_t stations() const;
                std::size_t oldest_station() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t pail = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            BucketBrigadeLine::BucketBrigadeLine(std::size_t stations) {
                if (stations == 0) throw BrigadeConfigError("brigade needs at least one station");
                cells_ = std::vector<Cell>(stations);
            }
            BucketBrigadeLine::BucketBrigadeLine(const BucketBrigadeLine& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            BucketBrigadeLine::BucketBrigadeLine(BucketBrigadeLine&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            BucketBrigadeLine& BucketBrigadeLine::operator=(const BucketBrigadeLine& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            BucketBrigadeLine& BucketBrigadeLine::operator=(BucketBrigadeLine&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t BucketBrigadeLine::stations() const { return cells_.size(); }
            std::size_t BucketBrigadeLine::pails() const { return used_; }
            void BucketBrigadeLine::pass_bucket(std::int64_t pail) {
                if (used_ == cells_.size()) throw BrigadeFullError("brigade is full");
                cells_[next_].occupied = true;
                cells_[next_].pail = pail;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t BucketBrigadeLine::empty_bucket() {
                if (used_ == 0) throw BrigadeEmptyError("brigade is empty");
                std::int64_t value = cells_[oldest_].pail;
                cells_[oldest_].occupied = false;
                cells_[oldest_].pail = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t BucketBrigadeLine::oldest_station() const {
                if (used_ == 0) throw BrigadeEmptyError("brigade is empty");
                return oldest_;
            }
            std::size_t BucketBrigadeLine::hand_to(BucketBrigadeLine& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.next_].occupied = true;
                    dest.cells_[dest.next_].pail = cells_[oldest_].pail;
                    dest.next_ = (dest.next_ + 1) % dest.cells_.size();
                    ++dest.used_;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].pail = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            BucketBrigadeLine::BucketBrigadeLine(std::size_t stations) {
                if (stations == 0) throw BrigadeConfigError("brigade needs at least one station");
                cells_ = std::vector<Cell>(stations);
            }
            BucketBrigadeLine::BucketBrigadeLine(const BucketBrigadeLine& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            BucketBrigadeLine::BucketBrigadeLine(BucketBrigadeLine&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            BucketBrigadeLine& BucketBrigadeLine::operator=(const BucketBrigadeLine& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            BucketBrigadeLine& BucketBrigadeLine::operator=(BucketBrigadeLine&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t BucketBrigadeLine::stations() const { return cells_.size(); }
            std::size_t BucketBrigadeLine::pails() const { return used_; }
            void BucketBrigadeLine::pass_bucket(std::int64_t pail) {
                if (used_ == cells_.size()) throw BrigadeFullError("brigade is full");
                cells_[used_].occupied = true;
                cells_[used_].pail = pail;
                ++used_;
            }
            std::int64_t BucketBrigadeLine::empty_bucket() {
                if (used_ == 0) throw BrigadeEmptyError("brigade is empty");
                std::int64_t value = cells_[0].pail;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].pail = 0;
                --used_;
                return value;
            }
            std::size_t BucketBrigadeLine::oldest_station() const {
                if (used_ == 0) throw BrigadeEmptyError("brigade is empty");
                return 0;
            }
            std::size_t BucketBrigadeLine::hand_to(BucketBrigadeLine& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.used_].occupied = true;
                    dest.cells_[dest.used_].pail = cells_[used_ - 1].pail;
                    ++dest.used_;
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].pail = 0;
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            BucketBrigadeLine line(2);
            line.pass_bucket(300);
            line.pass_bucket(600);
            if (line.pails() != 2U) return 1;
            if (line.empty_bucket() != 300) return 2;
            line.pass_bucket(900);
            if (line.empty_bucket() != 600) return 3;
            if (line.empty_bucket() != 900) return 4;
            BucketBrigadeLine cart(3);
            line.pass_bucket(1200);
            if (line.hand_to(cart, 1) != 1U) return 5;
            if (cart.empty_bucket() != 1200) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { BucketBrigadeLine zero(0); (void)zero; } catch (const BrigadeConfigError&) { threw = true; }
            if (!threw) return 1;
            BucketBrigadeLine line(3);
            threw = false;
            try { line.empty_bucket(); } catch (const BrigadeEmptyError&) { threw = true; }
            if (!threw) return 2;
            line.pass_bucket(70);
            line.pass_bucket(80);
            line.pass_bucket(90);
            threw = false;
            try { line.pass_bucket(100); } catch (const BrigadeFullError&) { threw = true; }
            if (!threw) return 3;
            if (line.empty_bucket() != 70) return 4;
            if (line.empty_bucket() != 80) return 5;
            line.pass_bucket(100);
            line.pass_bucket(110);
            if (line.oldest_station() != 2U) return 6;
            BucketBrigadeLine replica(line);
            if (replica.oldest_station() != 2U) return 7;
            if (replica.empty_bucket() != 90) return 8;
            if (replica.empty_bucket() != 100) return 9;
            if (replica.empty_bucket() != 110) return 10;
            if (replica.pails() != 0U) return 11;
            if (line.pails() != 3U) return 12;
            BucketBrigadeLine assigned(2);
            assigned = line;
            if (assigned.stations() != 3U) return 13;
            if (assigned.oldest_station() != 2U) return 14;
            BucketBrigadeLine moved(std::move(line));
            if (moved.oldest_station() != 2U) return 15;
            if (line.pails() != 0U) return 16;
            if (line.stations() != 3U) return 17;
            threw = false;
            try { line.oldest_station(); } catch (const BrigadeEmptyError&) { threw = true; }
            if (!threw) return 18;
            BucketBrigadeLine target(5);
            target = std::move(moved);
            if (target.stations() != 3U) return 19;
            if (target.oldest_station() != 2U) return 20;
            if (target.empty_bucket() != 90) return 21;
            if (moved.pails() != 0U) return 22;
            BucketBrigadeLine source(3);
            source.pass_bucket(10);
            source.pass_bucket(20);
            source.pass_bucket(30);
            if (source.empty_bucket() != 10) return 23;
            source.pass_bucket(40);
            BucketBrigadeLine sink(2);
            if (source.hand_to(sink, 5) != 2U) return 24;
            if (source.pails() != 1U) return 25;
            if (sink.empty_bucket() != 20) return 26;
            if (sink.empty_bucket() != 30) return 27;
            if (source.empty_bucket() != 40) return 28;
            source.pass_bucket(50);
            source.pass_bucket(60);
            BucketBrigadeLine cup(3);
            if (source.hand_to(cup, 1) != 1U) return 29;
            if (cup.empty_bucket() != 50) return 30;
            if (source.empty_bucket() != 60) return 31;
            return 0;
            """,
            "a fixed line of pail stations whose copies preserve exact physical layout, whose moves empty the source, and whose transfers move oldest-first",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, a copy that repacks cells from slot zero, or a transfer that moves newest-first",
            "copy and move layout preservation after wraparound, moved-from source state, hand_to FIFO order with destination-full stop, full and empty channels, and zero-station rejection",
            "project-context int64 copy/move ring",
            "copy/move and transfer-edge bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-aqueduct-flow-windows",
            "Aqueduct flow windows",
            "aqueduct",
            """
            class AqueductConfigError : public std::invalid_argument {
            public:
                explicit AqueductConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class AqueductEmptyError : public std::runtime_error {
            public:
                explicit AqueductEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class AqueductFullError : public std::logic_error {
            public:
                explicit AqueductFullError(const std::string& message) : std::logic_error(message) {}
            };
            class AqueductFlowWindows {
            public:
                explicit AqueductFlowWindows(std::size_t arches);
                AqueductFlowWindows(const AqueductFlowWindows& other);
                AqueductFlowWindows(AqueductFlowWindows&& other) noexcept;
                AqueductFlowWindows& operator=(const AqueductFlowWindows& other);
                AqueductFlowWindows& operator=(AqueductFlowWindows&& other) noexcept;
                void pour_in(std::int64_t volume);
                std::int64_t draw_off();
                std::size_t hand_to(AqueductFlowWindows& dest, std::size_t count);
                std::size_t volumes() const;
                std::size_t arches() const;
                std::size_t oldest_arch() const;
            };
            """,
            """
            class AqueductConfigError : public std::invalid_argument {
            public:
                explicit AqueductConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class AqueductEmptyError : public std::runtime_error {
            public:
                explicit AqueductEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class AqueductFullError : public std::logic_error {
            public:
                explicit AqueductFullError(const std::string& message) : std::logic_error(message) {}
            };
            class AqueductFlowWindows {
            public:
                explicit AqueductFlowWindows(std::size_t arches);
                AqueductFlowWindows(const AqueductFlowWindows& other);
                AqueductFlowWindows(AqueductFlowWindows&& other) noexcept;
                AqueductFlowWindows& operator=(const AqueductFlowWindows& other);
                AqueductFlowWindows& operator=(AqueductFlowWindows&& other) noexcept;
                void pour_in(std::int64_t volume);
                std::int64_t draw_off();
                std::size_t hand_to(AqueductFlowWindows& dest, std::size_t count);
                std::size_t volumes() const;
                std::size_t arches() const;
                std::size_t oldest_arch() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t volume = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            AqueductFlowWindows::AqueductFlowWindows(std::size_t arches) {
                if (arches == 0) throw AqueductConfigError("aqueduct needs at least one arch");
                cells_ = std::vector<Cell>(arches);
            }
            AqueductFlowWindows::AqueductFlowWindows(const AqueductFlowWindows& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            AqueductFlowWindows::AqueductFlowWindows(AqueductFlowWindows&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            AqueductFlowWindows& AqueductFlowWindows::operator=(const AqueductFlowWindows& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            AqueductFlowWindows& AqueductFlowWindows::operator=(AqueductFlowWindows&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t AqueductFlowWindows::arches() const { return cells_.size(); }
            std::size_t AqueductFlowWindows::volumes() const { return used_; }
            void AqueductFlowWindows::pour_in(std::int64_t volume) {
                if (used_ == cells_.size()) throw AqueductFullError("aqueduct is full");
                cells_[next_].occupied = true;
                cells_[next_].volume = volume;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t AqueductFlowWindows::draw_off() {
                if (used_ == 0) throw AqueductEmptyError("aqueduct is empty");
                std::int64_t value = cells_[oldest_].volume;
                cells_[oldest_].occupied = false;
                cells_[oldest_].volume = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t AqueductFlowWindows::oldest_arch() const {
                if (used_ == 0) throw AqueductEmptyError("aqueduct is empty");
                return oldest_;
            }
            std::size_t AqueductFlowWindows::hand_to(AqueductFlowWindows& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.next_].occupied = true;
                    dest.cells_[dest.next_].volume = cells_[oldest_].volume;
                    dest.next_ = (dest.next_ + 1) % dest.cells_.size();
                    ++dest.used_;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].volume = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            AqueductFlowWindows::AqueductFlowWindows(std::size_t arches) {
                if (arches == 0) throw AqueductConfigError("aqueduct needs at least one arch");
                cells_ = std::vector<Cell>(arches);
            }
            AqueductFlowWindows::AqueductFlowWindows(const AqueductFlowWindows& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            AqueductFlowWindows::AqueductFlowWindows(AqueductFlowWindows&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            AqueductFlowWindows& AqueductFlowWindows::operator=(const AqueductFlowWindows& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            AqueductFlowWindows& AqueductFlowWindows::operator=(AqueductFlowWindows&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t AqueductFlowWindows::arches() const { return cells_.size(); }
            std::size_t AqueductFlowWindows::volumes() const { return used_; }
            void AqueductFlowWindows::pour_in(std::int64_t volume) {
                if (used_ == cells_.size()) throw AqueductFullError("aqueduct is full");
                cells_[used_].occupied = true;
                cells_[used_].volume = volume;
                ++used_;
            }
            std::int64_t AqueductFlowWindows::draw_off() {
                if (used_ == 0) throw AqueductEmptyError("aqueduct is empty");
                std::int64_t value = cells_[0].volume;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].volume = 0;
                --used_;
                return value;
            }
            std::size_t AqueductFlowWindows::oldest_arch() const {
                if (used_ == 0) throw AqueductEmptyError("aqueduct is empty");
                return 0;
            }
            std::size_t AqueductFlowWindows::hand_to(AqueductFlowWindows& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.used_].occupied = true;
                    dest.cells_[dest.used_].volume = cells_[used_ - 1].volume;
                    ++dest.used_;
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].volume = 0;
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            AqueductFlowWindows duct(2);
            duct.pour_in(250);
            duct.pour_in(500);
            if (duct.volumes() != 2U) return 1;
            if (duct.draw_off() != 250) return 2;
            duct.pour_in(750);
            if (duct.draw_off() != 500) return 3;
            if (duct.draw_off() != 750) return 4;
            AqueductFlowWindows cistern(3);
            duct.pour_in(1000);
            if (duct.hand_to(cistern, 1) != 1U) return 5;
            if (cistern.draw_off() != 1000) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { AqueductFlowWindows zero(0); (void)zero; } catch (const AqueductConfigError&) { threw = true; }
            if (!threw) return 1;
            AqueductFlowWindows duct(4);
            threw = false;
            try { duct.draw_off(); } catch (const AqueductEmptyError&) { threw = true; }
            if (!threw) return 2;
            duct.pour_in(100);
            duct.pour_in(200);
            duct.pour_in(300);
            duct.pour_in(400);
            threw = false;
            try { duct.pour_in(500); } catch (const AqueductFullError&) { threw = true; }
            if (!threw) return 3;
            if (duct.draw_off() != 100) return 4;
            if (duct.draw_off() != 200) return 5;
            duct.pour_in(500);
            duct.pour_in(600);
            if (duct.oldest_arch() != 2U) return 6;
            AqueductFlowWindows replica(duct);
            if (replica.oldest_arch() != 2U) return 7;
            if (replica.draw_off() != 300) return 8;
            if (replica.draw_off() != 400) return 9;
            if (replica.draw_off() != 500) return 10;
            if (replica.draw_off() != 600) return 11;
            if (replica.volumes() != 0U) return 12;
            if (duct.volumes() != 4U) return 13;
            AqueductFlowWindows assigned(2);
            assigned = duct;
            if (assigned.arches() != 4U) return 14;
            if (assigned.oldest_arch() != 2U) return 15;
            AqueductFlowWindows moved(std::move(duct));
            if (moved.oldest_arch() != 2U) return 16;
            if (duct.volumes() != 0U) return 17;
            if (duct.arches() != 4U) return 18;
            threw = false;
            try { duct.oldest_arch(); } catch (const AqueductEmptyError&) { threw = true; }
            if (!threw) return 19;
            AqueductFlowWindows target(6);
            target = std::move(moved);
            if (target.arches() != 4U) return 20;
            if (target.oldest_arch() != 2U) return 21;
            if (target.draw_off() != 300) return 22;
            if (moved.volumes() != 0U) return 23;
            AqueductFlowWindows source(4);
            source.pour_in(10);
            source.pour_in(20);
            source.pour_in(30);
            source.pour_in(40);
            if (source.draw_off() != 10) return 24;
            source.pour_in(50);
            AqueductFlowWindows sink(2);
            if (source.hand_to(sink, 5) != 2U) return 25;
            if (source.volumes() != 2U) return 26;
            if (sink.draw_off() != 20) return 27;
            if (sink.draw_off() != 30) return 28;
            if (source.draw_off() != 40) return 29;
            if (source.draw_off() != 50) return 30;
            source.pour_in(60);
            source.pour_in(70);
            AqueductFlowWindows cup(3);
            if (source.hand_to(cup, 1) != 1U) return 31;
            if (cup.draw_off() != 60) return 32;
            if (source.draw_off() != 70) return 33;
            return 0;
            """,
            "a fixed duct of volume arches whose copies preserve exact physical layout, whose moves empty the source, and whose transfers move oldest-first",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, a copy that repacks cells from slot zero, or a transfer that moves newest-first",
            "copy and move layout preservation after wraparound, moved-from source state, hand_to FIFO order with destination-full stop, full and empty channels, and zero-arch rejection",
            "water-flow copy/move ring with arch slots",
            "copy/move and transfer-edge bounded ring",
        ),
        c(
            "f26cbuf-conveyor-oven-trays",
            "Conveyor oven trays",
            "conveyor_oven",
            """
            class OvenConfigError : public std::invalid_argument {
            public:
                explicit OvenConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class OvenEmptyError : public std::runtime_error {
            public:
                explicit OvenEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class OvenFullError : public std::logic_error {
            public:
                explicit OvenFullError(const std::string& message) : std::logic_error(message) {}
            };
            class ConveyorOvenTrays {
            public:
                explicit ConveyorOvenTrays(std::size_t trays);
                ConveyorOvenTrays(const ConveyorOvenTrays& other);
                ConveyorOvenTrays(ConveyorOvenTrays&& other) noexcept;
                ConveyorOvenTrays& operator=(const ConveyorOvenTrays& other);
                ConveyorOvenTrays& operator=(ConveyorOvenTrays&& other) noexcept;
                void load_batch(const std::string& batch);
                std::string unload_batch();
                std::size_t hand_to(ConveyorOvenTrays& dest, std::size_t count);
                std::size_t batches() const;
                std::size_t trays() const;
                std::size_t oldest_tray() const;
            };
            """,
            """
            class OvenConfigError : public std::invalid_argument {
            public:
                explicit OvenConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class OvenEmptyError : public std::runtime_error {
            public:
                explicit OvenEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class OvenFullError : public std::logic_error {
            public:
                explicit OvenFullError(const std::string& message) : std::logic_error(message) {}
            };
            class ConveyorOvenTrays {
            public:
                explicit ConveyorOvenTrays(std::size_t trays);
                ConveyorOvenTrays(const ConveyorOvenTrays& other);
                ConveyorOvenTrays(ConveyorOvenTrays&& other) noexcept;
                ConveyorOvenTrays& operator=(const ConveyorOvenTrays& other);
                ConveyorOvenTrays& operator=(ConveyorOvenTrays&& other) noexcept;
                void load_batch(const std::string& batch);
                std::string unload_batch();
                std::size_t hand_to(ConveyorOvenTrays& dest, std::size_t count);
                std::size_t batches() const;
                std::size_t trays() const;
                std::size_t oldest_tray() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string batch;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            ConveyorOvenTrays::ConveyorOvenTrays(std::size_t trays) {
                if (trays == 0) throw OvenConfigError("oven needs at least one tray");
                cells_ = std::vector<Cell>(trays);
            }
            ConveyorOvenTrays::ConveyorOvenTrays(const ConveyorOvenTrays& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            ConveyorOvenTrays::ConveyorOvenTrays(ConveyorOvenTrays&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            ConveyorOvenTrays& ConveyorOvenTrays::operator=(const ConveyorOvenTrays& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            ConveyorOvenTrays& ConveyorOvenTrays::operator=(ConveyorOvenTrays&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t ConveyorOvenTrays::trays() const { return cells_.size(); }
            std::size_t ConveyorOvenTrays::batches() const { return used_; }
            void ConveyorOvenTrays::load_batch(const std::string& batch) {
                if (used_ == cells_.size()) throw OvenFullError("oven is full");
                cells_[next_].occupied = true;
                cells_[next_].batch = batch;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string ConveyorOvenTrays::unload_batch() {
                if (used_ == 0) throw OvenEmptyError("oven is empty");
                std::string value = cells_[oldest_].batch;
                cells_[oldest_].occupied = false;
                cells_[oldest_].batch.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t ConveyorOvenTrays::oldest_tray() const {
                if (used_ == 0) throw OvenEmptyError("oven is empty");
                return oldest_;
            }
            std::size_t ConveyorOvenTrays::hand_to(ConveyorOvenTrays& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.next_].occupied = true;
                    dest.cells_[dest.next_].batch = cells_[oldest_].batch;
                    dest.next_ = (dest.next_ + 1) % dest.cells_.size();
                    ++dest.used_;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].batch.clear();
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            ConveyorOvenTrays::ConveyorOvenTrays(std::size_t trays) {
                if (trays == 0) throw OvenConfigError("oven needs at least one tray");
                cells_ = std::vector<Cell>(trays);
            }
            ConveyorOvenTrays::ConveyorOvenTrays(const ConveyorOvenTrays& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            ConveyorOvenTrays::ConveyorOvenTrays(ConveyorOvenTrays&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            ConveyorOvenTrays& ConveyorOvenTrays::operator=(const ConveyorOvenTrays& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            ConveyorOvenTrays& ConveyorOvenTrays::operator=(ConveyorOvenTrays&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t ConveyorOvenTrays::trays() const { return cells_.size(); }
            std::size_t ConveyorOvenTrays::batches() const { return used_; }
            void ConveyorOvenTrays::load_batch(const std::string& batch) {
                if (used_ == cells_.size()) throw OvenFullError("oven is full");
                cells_[used_].occupied = true;
                cells_[used_].batch = batch;
                ++used_;
            }
            std::string ConveyorOvenTrays::unload_batch() {
                if (used_ == 0) throw OvenEmptyError("oven is empty");
                std::string value = cells_[0].batch;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].batch.clear();
                --used_;
                return value;
            }
            std::size_t ConveyorOvenTrays::oldest_tray() const {
                if (used_ == 0) throw OvenEmptyError("oven is empty");
                return 0;
            }
            std::size_t ConveyorOvenTrays::hand_to(ConveyorOvenTrays& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.used_].occupied = true;
                    dest.cells_[dest.used_].batch = cells_[used_ - 1].batch;
                    ++dest.used_;
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].batch.clear();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            ConveyorOvenTrays oven(2);
            oven.load_batch("rye");
            oven.load_batch("bran");
            if (oven.batches() != 2U) return 1;
            if (oven.unload_batch() != "rye") return 2;
            oven.load_batch("oats");
            if (oven.unload_batch() != "bran") return 3;
            if (oven.unload_batch() != "oats") return 4;
            ConveyorOvenTrays rack(3);
            oven.load_batch("corn");
            if (oven.hand_to(rack, 1) != 1U) return 5;
            if (rack.unload_batch() != "corn") return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { ConveyorOvenTrays zero(0); (void)zero; } catch (const OvenConfigError&) { threw = true; }
            if (!threw) return 1;
            ConveyorOvenTrays oven(3);
            threw = false;
            try { oven.unload_batch(); } catch (const OvenEmptyError&) { threw = true; }
            if (!threw) return 2;
            oven.load_batch("rye");
            oven.load_batch("bran");
            oven.load_batch("oats");
            threw = false;
            try { oven.load_batch("corn"); } catch (const OvenFullError&) { threw = true; }
            if (!threw) return 3;
            if (oven.unload_batch() != "rye") return 4;
            if (oven.unload_batch() != "bran") return 5;
            oven.load_batch("corn");
            oven.load_batch("rice");
            if (oven.oldest_tray() != 2U) return 6;
            ConveyorOvenTrays replica(oven);
            if (replica.oldest_tray() != 2U) return 7;
            if (replica.unload_batch() != "oats") return 8;
            if (replica.unload_batch() != "corn") return 9;
            if (replica.unload_batch() != "rice") return 10;
            if (replica.batches() != 0U) return 11;
            if (oven.batches() != 3U) return 12;
            ConveyorOvenTrays assigned(2);
            assigned = oven;
            if (assigned.trays() != 3U) return 13;
            if (assigned.oldest_tray() != 2U) return 14;
            ConveyorOvenTrays moved(std::move(oven));
            if (moved.oldest_tray() != 2U) return 15;
            if (oven.batches() != 0U) return 16;
            if (oven.trays() != 3U) return 17;
            threw = false;
            try { oven.oldest_tray(); } catch (const OvenEmptyError&) { threw = true; }
            if (!threw) return 18;
            ConveyorOvenTrays target(5);
            target = std::move(moved);
            if (target.trays() != 3U) return 19;
            if (target.oldest_tray() != 2U) return 20;
            if (target.unload_batch() != "oats") return 21;
            if (moved.batches() != 0U) return 22;
            ConveyorOvenTrays source(3);
            source.load_batch("bagel");
            source.load_batch("scone");
            source.load_batch("crepe");
            if (source.unload_batch() != "bagel") return 23;
            source.load_batch("toast");
            ConveyorOvenTrays sink(2);
            if (source.hand_to(sink, 5) != 2U) return 24;
            if (source.batches() != 1U) return 25;
            if (sink.unload_batch() != "scone") return 26;
            if (sink.unload_batch() != "crepe") return 27;
            if (source.unload_batch() != "toast") return 28;
            source.load_batch("pita");
            source.load_batch("naan");
            ConveyorOvenTrays cup(3);
            if (source.hand_to(cup, 1) != 1U) return 29;
            if (cup.unload_batch() != "pita") return 30;
            if (source.unload_batch() != "naan") return 31;
            return 0;
            """,
            "a fixed oven of batch trays whose copies preserve exact physical layout, whose moves empty the source, and whose transfers move oldest-first",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, a copy that repacks cells from slot zero, or a transfer that moves newest-first",
            "copy and move layout preservation after wraparound, moved-from source state, hand_to FIFO order with destination-full stop, full and empty channels, and zero-tray rejection",
            "string copy/move ring with tray slots",
            "copy/move and transfer-edge bounded ring",
        ),
        c(
            "f26cbuf-kiln-shelf-rotation",
            "Kiln shelf rotation",
            "kiln",
            """
            class KilnConfigError : public std::invalid_argument {
            public:
                explicit KilnConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class KilnEmptyError : public std::runtime_error {
            public:
                explicit KilnEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class KilnFullError : public std::logic_error {
            public:
                explicit KilnFullError(const std::string& message) : std::logic_error(message) {}
            };
            class KilnShelfRotation {
            public:
                explicit KilnShelfRotation(std::size_t shelves);
                KilnShelfRotation(const KilnShelfRotation& other);
                KilnShelfRotation(KilnShelfRotation&& other) noexcept;
                KilnShelfRotation& operator=(const KilnShelfRotation& other);
                KilnShelfRotation& operator=(KilnShelfRotation&& other) noexcept;
                void fire(std::int32_t cone);
                std::int32_t cool();
                std::size_t hand_to(KilnShelfRotation& dest, std::size_t count);
                std::size_t cones() const;
                std::size_t shelves() const;
                std::size_t oldest_shelf() const;
            };
            """,
            """
            class KilnConfigError : public std::invalid_argument {
            public:
                explicit KilnConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class KilnEmptyError : public std::runtime_error {
            public:
                explicit KilnEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class KilnFullError : public std::logic_error {
            public:
                explicit KilnFullError(const std::string& message) : std::logic_error(message) {}
            };
            class KilnShelfRotation {
            public:
                explicit KilnShelfRotation(std::size_t shelves);
                KilnShelfRotation(const KilnShelfRotation& other);
                KilnShelfRotation(KilnShelfRotation&& other) noexcept;
                KilnShelfRotation& operator=(const KilnShelfRotation& other);
                KilnShelfRotation& operator=(KilnShelfRotation&& other) noexcept;
                void fire(std::int32_t cone);
                std::int32_t cool();
                std::size_t hand_to(KilnShelfRotation& dest, std::size_t count);
                std::size_t cones() const;
                std::size_t shelves() const;
                std::size_t oldest_shelf() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t cone = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            KilnShelfRotation::KilnShelfRotation(std::size_t shelves) {
                if (shelves == 0) throw KilnConfigError("kiln needs at least one shelf");
                cells_ = std::vector<Cell>(shelves);
            }
            KilnShelfRotation::KilnShelfRotation(const KilnShelfRotation& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            KilnShelfRotation::KilnShelfRotation(KilnShelfRotation&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            KilnShelfRotation& KilnShelfRotation::operator=(const KilnShelfRotation& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            KilnShelfRotation& KilnShelfRotation::operator=(KilnShelfRotation&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t KilnShelfRotation::shelves() const { return cells_.size(); }
            std::size_t KilnShelfRotation::cones() const { return used_; }
            void KilnShelfRotation::fire(std::int32_t cone) {
                if (used_ == cells_.size()) throw KilnFullError("kiln is full");
                cells_[next_].occupied = true;
                cells_[next_].cone = cone;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t KilnShelfRotation::cool() {
                if (used_ == 0) throw KilnEmptyError("kiln is empty");
                std::int32_t value = cells_[oldest_].cone;
                cells_[oldest_].occupied = false;
                cells_[oldest_].cone = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t KilnShelfRotation::oldest_shelf() const {
                if (used_ == 0) throw KilnEmptyError("kiln is empty");
                return oldest_;
            }
            std::size_t KilnShelfRotation::hand_to(KilnShelfRotation& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.next_].occupied = true;
                    dest.cells_[dest.next_].cone = cells_[oldest_].cone;
                    dest.next_ = (dest.next_ + 1) % dest.cells_.size();
                    ++dest.used_;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].cone = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            KilnShelfRotation::KilnShelfRotation(std::size_t shelves) {
                if (shelves == 0) throw KilnConfigError("kiln needs at least one shelf");
                cells_ = std::vector<Cell>(shelves);
            }
            KilnShelfRotation::KilnShelfRotation(const KilnShelfRotation& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            KilnShelfRotation::KilnShelfRotation(KilnShelfRotation&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            KilnShelfRotation& KilnShelfRotation::operator=(const KilnShelfRotation& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            KilnShelfRotation& KilnShelfRotation::operator=(KilnShelfRotation&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t KilnShelfRotation::shelves() const { return cells_.size(); }
            std::size_t KilnShelfRotation::cones() const { return used_; }
            void KilnShelfRotation::fire(std::int32_t cone) {
                if (used_ == cells_.size()) throw KilnFullError("kiln is full");
                cells_[used_].occupied = true;
                cells_[used_].cone = cone;
                ++used_;
            }
            std::int32_t KilnShelfRotation::cool() {
                if (used_ == 0) throw KilnEmptyError("kiln is empty");
                std::int32_t value = cells_[0].cone;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].cone = 0;
                --used_;
                return value;
            }
            std::size_t KilnShelfRotation::oldest_shelf() const {
                if (used_ == 0) throw KilnEmptyError("kiln is empty");
                return 0;
            }
            std::size_t KilnShelfRotation::hand_to(KilnShelfRotation& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.used_].occupied = true;
                    dest.cells_[dest.used_].cone = cells_[used_ - 1].cone;
                    ++dest.used_;
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].cone = 0;
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            KilnShelfRotation kiln(2);
            kiln.fire(5);
            kiln.fire(6);
            if (kiln.cones() != 2U) return 1;
            if (kiln.cool() != 5) return 2;
            kiln.fire(7);
            if (kiln.cool() != 6) return 3;
            if (kiln.cool() != 7) return 4;
            KilnShelfRotation cart(3);
            kiln.fire(8);
            if (kiln.hand_to(cart, 1) != 1U) return 5;
            if (cart.cool() != 8) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { KilnShelfRotation zero(0); (void)zero; } catch (const KilnConfigError&) { threw = true; }
            if (!threw) return 1;
            KilnShelfRotation kiln(4);
            threw = false;
            try { kiln.cool(); } catch (const KilnEmptyError&) { threw = true; }
            if (!threw) return 2;
            kiln.fire(4);
            kiln.fire(5);
            kiln.fire(6);
            kiln.fire(7);
            threw = false;
            try { kiln.fire(8); } catch (const KilnFullError&) { threw = true; }
            if (!threw) return 3;
            if (kiln.cool() != 4) return 4;
            if (kiln.cool() != 5) return 5;
            kiln.fire(8);
            kiln.fire(9);
            if (kiln.oldest_shelf() != 2U) return 6;
            KilnShelfRotation replica(kiln);
            if (replica.oldest_shelf() != 2U) return 7;
            if (replica.cool() != 6) return 8;
            if (replica.cool() != 7) return 9;
            if (replica.cool() != 8) return 10;
            if (replica.cool() != 9) return 11;
            if (replica.cones() != 0U) return 12;
            if (kiln.cones() != 4U) return 13;
            KilnShelfRotation assigned(2);
            assigned = kiln;
            if (assigned.shelves() != 4U) return 14;
            if (assigned.oldest_shelf() != 2U) return 15;
            KilnShelfRotation moved(std::move(kiln));
            if (moved.oldest_shelf() != 2U) return 16;
            if (kiln.cones() != 0U) return 17;
            if (kiln.shelves() != 4U) return 18;
            threw = false;
            try { kiln.oldest_shelf(); } catch (const KilnEmptyError&) { threw = true; }
            if (!threw) return 19;
            KilnShelfRotation target(6);
            target = std::move(moved);
            if (target.shelves() != 4U) return 20;
            if (target.oldest_shelf() != 2U) return 21;
            if (target.cool() != 6) return 22;
            if (moved.cones() != 0U) return 23;
            KilnShelfRotation source(4);
            source.fire(1);
            source.fire(2);
            source.fire(3);
            source.fire(4);
            if (source.cool() != 1) return 24;
            source.fire(5);
            KilnShelfRotation sink(2);
            if (source.hand_to(sink, 5) != 2U) return 25;
            if (source.cones() != 2U) return 26;
            if (sink.cool() != 2) return 27;
            if (sink.cool() != 3) return 28;
            if (source.cool() != 4) return 29;
            if (source.cool() != 5) return 30;
            source.fire(6);
            source.fire(7);
            KilnShelfRotation cup(3);
            if (source.hand_to(cup, 1) != 1U) return 31;
            if (cup.cool() != 6) return 32;
            if (source.cool() != 7) return 33;
            return 0;
            """,
            "a fixed kiln of cone shelves whose copies preserve exact physical layout, whose moves empty the source, and whose transfers move oldest-first",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, a copy that repacks cells from slot zero, or a transfer that moves newest-first",
            "copy and move layout preservation after wraparound, moved-from source state, hand_to FIFO order with destination-full stop, full and empty channels, and zero-shelf rejection",
            "project-context kiln copy/move ring",
            "copy/move and transfer-edge bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-tannery-vat-cycle",
            "Tannery vat cycle",
            "tannery",
            """
            class TanneryConfigError : public std::invalid_argument {
            public:
                explicit TanneryConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TanneryEmptyError : public std::runtime_error {
            public:
                explicit TanneryEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TanneryFullError : public std::logic_error {
            public:
                explicit TanneryFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TanneryVatCycle {
            public:
                explicit TanneryVatCycle(std::size_t vats);
                TanneryVatCycle(const TanneryVatCycle& other);
                TanneryVatCycle(TanneryVatCycle&& other) noexcept;
                TanneryVatCycle& operator=(const TanneryVatCycle& other);
                TanneryVatCycle& operator=(TanneryVatCycle&& other) noexcept;
                void steep(const std::string& hide);
                std::string pull_hide();
                std::size_t hand_to(TanneryVatCycle& dest, std::size_t count);
                std::size_t hides() const;
                std::size_t vats() const;
                std::size_t oldest_vat() const;
            };
            """,
            """
            class TanneryConfigError : public std::invalid_argument {
            public:
                explicit TanneryConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TanneryEmptyError : public std::runtime_error {
            public:
                explicit TanneryEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TanneryFullError : public std::logic_error {
            public:
                explicit TanneryFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TanneryVatCycle {
            public:
                explicit TanneryVatCycle(std::size_t vats);
                TanneryVatCycle(const TanneryVatCycle& other);
                TanneryVatCycle(TanneryVatCycle&& other) noexcept;
                TanneryVatCycle& operator=(const TanneryVatCycle& other);
                TanneryVatCycle& operator=(TanneryVatCycle&& other) noexcept;
                void steep(const std::string& hide);
                std::string pull_hide();
                std::size_t hand_to(TanneryVatCycle& dest, std::size_t count);
                std::size_t hides() const;
                std::size_t vats() const;
                std::size_t oldest_vat() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string hide;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            TanneryVatCycle::TanneryVatCycle(std::size_t vats) {
                if (vats == 0) throw TanneryConfigError("tannery needs at least one vat");
                cells_ = std::vector<Cell>(vats);
            }
            TanneryVatCycle::TanneryVatCycle(const TanneryVatCycle& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            TanneryVatCycle::TanneryVatCycle(TanneryVatCycle&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            TanneryVatCycle& TanneryVatCycle::operator=(const TanneryVatCycle& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            TanneryVatCycle& TanneryVatCycle::operator=(TanneryVatCycle&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t TanneryVatCycle::vats() const { return cells_.size(); }
            std::size_t TanneryVatCycle::hides() const { return used_; }
            void TanneryVatCycle::steep(const std::string& hide) {
                if (used_ == cells_.size()) throw TanneryFullError("tannery is full");
                cells_[next_].occupied = true;
                cells_[next_].hide = hide;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string TanneryVatCycle::pull_hide() {
                if (used_ == 0) throw TanneryEmptyError("tannery is empty");
                std::string value = cells_[oldest_].hide;
                cells_[oldest_].occupied = false;
                cells_[oldest_].hide.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t TanneryVatCycle::oldest_vat() const {
                if (used_ == 0) throw TanneryEmptyError("tannery is empty");
                return oldest_;
            }
            std::size_t TanneryVatCycle::hand_to(TanneryVatCycle& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.next_].occupied = true;
                    dest.cells_[dest.next_].hide = cells_[oldest_].hide;
                    dest.next_ = (dest.next_ + 1) % dest.cells_.size();
                    ++dest.used_;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].hide.clear();
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            TanneryVatCycle::TanneryVatCycle(std::size_t vats) {
                if (vats == 0) throw TanneryConfigError("tannery needs at least one vat");
                cells_ = std::vector<Cell>(vats);
            }
            TanneryVatCycle::TanneryVatCycle(const TanneryVatCycle& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            TanneryVatCycle::TanneryVatCycle(TanneryVatCycle&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            TanneryVatCycle& TanneryVatCycle::operator=(const TanneryVatCycle& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            TanneryVatCycle& TanneryVatCycle::operator=(TanneryVatCycle&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t TanneryVatCycle::vats() const { return cells_.size(); }
            std::size_t TanneryVatCycle::hides() const { return used_; }
            void TanneryVatCycle::steep(const std::string& hide) {
                if (used_ == cells_.size()) throw TanneryFullError("tannery is full");
                cells_[used_].occupied = true;
                cells_[used_].hide = hide;
                ++used_;
            }
            std::string TanneryVatCycle::pull_hide() {
                if (used_ == 0) throw TanneryEmptyError("tannery is empty");
                std::string value = cells_[0].hide;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].hide.clear();
                --used_;
                return value;
            }
            std::size_t TanneryVatCycle::oldest_vat() const {
                if (used_ == 0) throw TanneryEmptyError("tannery is empty");
                return 0;
            }
            std::size_t TanneryVatCycle::hand_to(TanneryVatCycle& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.used_].occupied = true;
                    dest.cells_[dest.used_].hide = cells_[used_ - 1].hide;
                    ++dest.used_;
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].hide.clear();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            TanneryVatCycle yard(2);
            yard.steep("elk");
            yard.steep("deer");
            if (yard.hides() != 2U) return 1;
            if (yard.pull_hide() != "elk") return 2;
            yard.steep("moose");
            if (yard.pull_hide() != "deer") return 3;
            if (yard.pull_hide() != "moose") return 4;
            TanneryVatCycle annex(3);
            yard.steep("bison");
            if (yard.hand_to(annex, 1) != 1U) return 5;
            if (annex.pull_hide() != "bison") return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { TanneryVatCycle zero(0); (void)zero; } catch (const TanneryConfigError&) { threw = true; }
            if (!threw) return 1;
            TanneryVatCycle yard(3);
            threw = false;
            try { yard.pull_hide(); } catch (const TanneryEmptyError&) { threw = true; }
            if (!threw) return 2;
            yard.steep("elk");
            yard.steep("deer");
            yard.steep("moose");
            threw = false;
            try { yard.steep("bison"); } catch (const TanneryFullError&) { threw = true; }
            if (!threw) return 3;
            if (yard.pull_hide() != "elk") return 4;
            if (yard.pull_hide() != "deer") return 5;
            yard.steep("bison");
            yard.steep("goat");
            if (yard.oldest_vat() != 2U) return 6;
            TanneryVatCycle replica(yard);
            if (replica.oldest_vat() != 2U) return 7;
            if (replica.pull_hide() != "moose") return 8;
            if (replica.pull_hide() != "bison") return 9;
            if (replica.pull_hide() != "goat") return 10;
            if (replica.hides() != 0U) return 11;
            if (yard.hides() != 3U) return 12;
            TanneryVatCycle assigned(2);
            assigned = yard;
            if (assigned.vats() != 3U) return 13;
            if (assigned.oldest_vat() != 2U) return 14;
            TanneryVatCycle moved(std::move(yard));
            if (moved.oldest_vat() != 2U) return 15;
            if (yard.hides() != 0U) return 16;
            if (yard.vats() != 3U) return 17;
            threw = false;
            try { yard.oldest_vat(); } catch (const TanneryEmptyError&) { threw = true; }
            if (!threw) return 18;
            TanneryVatCycle target(5);
            target = std::move(moved);
            if (target.vats() != 3U) return 19;
            if (target.oldest_vat() != 2U) return 20;
            if (target.pull_hide() != "moose") return 21;
            if (moved.hides() != 0U) return 22;
            TanneryVatCycle source(3);
            source.steep("kip");
            source.steep("calf");
            source.steep("steer");
            if (source.pull_hide() != "kip") return 23;
            source.steep("bull");
            TanneryVatCycle sink(2);
            if (source.hand_to(sink, 5) != 2U) return 24;
            if (source.hides() != 1U) return 25;
            if (sink.pull_hide() != "calf") return 26;
            if (sink.pull_hide() != "steer") return 27;
            if (source.pull_hide() != "bull") return 28;
            source.steep("cow");
            source.steep("ox");
            TanneryVatCycle cup(3);
            if (source.hand_to(cup, 1) != 1U) return 29;
            if (cup.pull_hide() != "cow") return 30;
            if (source.pull_hide() != "ox") return 31;
            return 0;
            """,
            "a fixed yard of hide vats whose copies preserve exact physical layout, whose moves empty the source, and whose transfers move oldest-first",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, a copy that repacks cells from slot zero, or a transfer that moves newest-first",
            "copy and move layout preservation after wraparound, moved-from source state, hand_to FIFO order with destination-full stop, full and empty channels, and zero-vat rejection",
            "string copy/move ring with vat slots",
            "copy/move and transfer-edge bounded ring",
        ),
        c(
            "f26cbuf-cider-press-loads",
            "Cider press loads",
            "cider_press",
            """
            class PressConfigError : public std::invalid_argument {
            public:
                explicit PressConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PressEmptyError : public std::runtime_error {
            public:
                explicit PressEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class PressFullError : public std::logic_error {
            public:
                explicit PressFullError(const std::string& message) : std::logic_error(message) {}
            };
            class CiderPressLoads {
            public:
                explicit CiderPressLoads(std::size_t racks);
                CiderPressLoads(const CiderPressLoads& other);
                CiderPressLoads(CiderPressLoads&& other) noexcept;
                CiderPressLoads& operator=(const CiderPressLoads& other);
                CiderPressLoads& operator=(CiderPressLoads&& other) noexcept;
                void stack_bushels(std::int64_t bushel);
                std::int64_t press();
                std::size_t hand_to(CiderPressLoads& dest, std::size_t count);
                std::size_t bushels() const;
                std::size_t racks() const;
                std::size_t oldest_rack() const;
            };
            """,
            """
            class PressConfigError : public std::invalid_argument {
            public:
                explicit PressConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PressEmptyError : public std::runtime_error {
            public:
                explicit PressEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class PressFullError : public std::logic_error {
            public:
                explicit PressFullError(const std::string& message) : std::logic_error(message) {}
            };
            class CiderPressLoads {
            public:
                explicit CiderPressLoads(std::size_t racks);
                CiderPressLoads(const CiderPressLoads& other);
                CiderPressLoads(CiderPressLoads&& other) noexcept;
                CiderPressLoads& operator=(const CiderPressLoads& other);
                CiderPressLoads& operator=(CiderPressLoads&& other) noexcept;
                void stack_bushels(std::int64_t bushel);
                std::int64_t press();
                std::size_t hand_to(CiderPressLoads& dest, std::size_t count);
                std::size_t bushels() const;
                std::size_t racks() const;
                std::size_t oldest_rack() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t bushel = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            CiderPressLoads::CiderPressLoads(std::size_t racks) {
                if (racks == 0) throw PressConfigError("press needs at least one rack");
                cells_ = std::vector<Cell>(racks);
            }
            CiderPressLoads::CiderPressLoads(const CiderPressLoads& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            CiderPressLoads::CiderPressLoads(CiderPressLoads&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            CiderPressLoads& CiderPressLoads::operator=(const CiderPressLoads& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            CiderPressLoads& CiderPressLoads::operator=(CiderPressLoads&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t CiderPressLoads::racks() const { return cells_.size(); }
            std::size_t CiderPressLoads::bushels() const { return used_; }
            void CiderPressLoads::stack_bushels(std::int64_t bushel) {
                if (used_ == cells_.size()) throw PressFullError("press is full");
                cells_[next_].occupied = true;
                cells_[next_].bushel = bushel;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t CiderPressLoads::press() {
                if (used_ == 0) throw PressEmptyError("press is empty");
                std::int64_t value = cells_[oldest_].bushel;
                cells_[oldest_].occupied = false;
                cells_[oldest_].bushel = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t CiderPressLoads::oldest_rack() const {
                if (used_ == 0) throw PressEmptyError("press is empty");
                return oldest_;
            }
            std::size_t CiderPressLoads::hand_to(CiderPressLoads& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.next_].occupied = true;
                    dest.cells_[dest.next_].bushel = cells_[oldest_].bushel;
                    dest.next_ = (dest.next_ + 1) % dest.cells_.size();
                    ++dest.used_;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].bushel = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            CiderPressLoads::CiderPressLoads(std::size_t racks) {
                if (racks == 0) throw PressConfigError("press needs at least one rack");
                cells_ = std::vector<Cell>(racks);
            }
            CiderPressLoads::CiderPressLoads(const CiderPressLoads& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            CiderPressLoads::CiderPressLoads(CiderPressLoads&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            CiderPressLoads& CiderPressLoads::operator=(const CiderPressLoads& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            CiderPressLoads& CiderPressLoads::operator=(CiderPressLoads&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t CiderPressLoads::racks() const { return cells_.size(); }
            std::size_t CiderPressLoads::bushels() const { return used_; }
            void CiderPressLoads::stack_bushels(std::int64_t bushel) {
                if (used_ == cells_.size()) throw PressFullError("press is full");
                cells_[used_].occupied = true;
                cells_[used_].bushel = bushel;
                ++used_;
            }
            std::int64_t CiderPressLoads::press() {
                if (used_ == 0) throw PressEmptyError("press is empty");
                std::int64_t value = cells_[0].bushel;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].bushel = 0;
                --used_;
                return value;
            }
            std::size_t CiderPressLoads::oldest_rack() const {
                if (used_ == 0) throw PressEmptyError("press is empty");
                return 0;
            }
            std::size_t CiderPressLoads::hand_to(CiderPressLoads& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.used_].occupied = true;
                    dest.cells_[dest.used_].bushel = cells_[used_ - 1].bushel;
                    ++dest.used_;
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].bushel = 0;
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            CiderPressLoads press(2);
            press.stack_bushels(40);
            press.stack_bushels(80);
            if (press.bushels() != 2U) return 1;
            if (press.press() != 40) return 2;
            press.stack_bushels(120);
            if (press.press() != 80) return 3;
            if (press.press() != 120) return 4;
            CiderPressLoads wagon(3);
            press.stack_bushels(160);
            if (press.hand_to(wagon, 1) != 1U) return 5;
            if (wagon.press() != 160) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { CiderPressLoads zero(0); (void)zero; } catch (const PressConfigError&) { threw = true; }
            if (!threw) return 1;
            CiderPressLoads press(3);
            threw = false;
            try { press.press(); } catch (const PressEmptyError&) { threw = true; }
            if (!threw) return 2;
            press.stack_bushels(11);
            press.stack_bushels(22);
            press.stack_bushels(33);
            threw = false;
            try { press.stack_bushels(44); } catch (const PressFullError&) { threw = true; }
            if (!threw) return 3;
            if (press.press() != 11) return 4;
            if (press.press() != 22) return 5;
            press.stack_bushels(44);
            press.stack_bushels(55);
            if (press.oldest_rack() != 2U) return 6;
            CiderPressLoads replica(press);
            if (replica.oldest_rack() != 2U) return 7;
            if (replica.press() != 33) return 8;
            if (replica.press() != 44) return 9;
            if (replica.press() != 55) return 10;
            if (replica.bushels() != 0U) return 11;
            if (press.bushels() != 3U) return 12;
            CiderPressLoads assigned(2);
            assigned = press;
            if (assigned.racks() != 3U) return 13;
            if (assigned.oldest_rack() != 2U) return 14;
            CiderPressLoads moved(std::move(press));
            if (moved.oldest_rack() != 2U) return 15;
            if (press.bushels() != 0U) return 16;
            if (press.racks() != 3U) return 17;
            threw = false;
            try { press.oldest_rack(); } catch (const PressEmptyError&) { threw = true; }
            if (!threw) return 18;
            CiderPressLoads target(5);
            target = std::move(moved);
            if (target.racks() != 3U) return 19;
            if (target.oldest_rack() != 2U) return 20;
            if (target.press() != 33) return 21;
            if (moved.bushels() != 0U) return 22;
            CiderPressLoads source(3);
            source.stack_bushels(1);
            source.stack_bushels(2);
            source.stack_bushels(3);
            if (source.press() != 1) return 23;
            source.stack_bushels(4);
            CiderPressLoads sink(2);
            if (source.hand_to(sink, 5) != 2U) return 24;
            if (source.bushels() != 1U) return 25;
            if (sink.press() != 2) return 26;
            if (sink.press() != 3) return 27;
            if (source.press() != 4) return 28;
            source.stack_bushels(5);
            source.stack_bushels(6);
            CiderPressLoads cup(3);
            if (source.hand_to(cup, 1) != 1U) return 29;
            if (cup.press() != 5) return 30;
            if (source.press() != 6) return 31;
            return 0;
            """,
            "a fixed press of bushel racks whose copies preserve exact physical layout, whose moves empty the source, and whose transfers move oldest-first",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, a copy that repacks cells from slot zero, or a transfer that moves newest-first",
            "copy and move layout preservation after wraparound, moved-from source state, hand_to FIFO order with destination-full stop, full and empty channels, and zero-rack rejection",
            "int64 copy/move ring with press racks",
            "copy/move and transfer-edge bounded ring",
        ),
        c(
            "f26cbuf-swing-bridge-spans",
            "Swing bridge spans",
            "swing_bridge",
            """
            class BridgeConfigError : public std::invalid_argument {
            public:
                explicit BridgeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BridgeEmptyError : public std::runtime_error {
            public:
                explicit BridgeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class BridgeFullError : public std::logic_error {
            public:
                explicit BridgeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class SwingBridgeSpans {
            public:
                explicit SwingBridgeSpans(std::size_t berths);
                SwingBridgeSpans(const SwingBridgeSpans& other);
                SwingBridgeSpans(SwingBridgeSpans&& other) noexcept;
                SwingBridgeSpans& operator=(const SwingBridgeSpans& other);
                SwingBridgeSpans& operator=(SwingBridgeSpans&& other) noexcept;
                void admit_vessel(std::int32_t vessel);
                std::int32_t clear_vessel();
                std::size_t hand_to(SwingBridgeSpans& dest, std::size_t count);
                std::size_t vessels() const;
                std::size_t berths() const;
                std::size_t oldest_berth() const;
            };
            """,
            """
            class BridgeConfigError : public std::invalid_argument {
            public:
                explicit BridgeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class BridgeEmptyError : public std::runtime_error {
            public:
                explicit BridgeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class BridgeFullError : public std::logic_error {
            public:
                explicit BridgeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class SwingBridgeSpans {
            public:
                explicit SwingBridgeSpans(std::size_t berths);
                SwingBridgeSpans(const SwingBridgeSpans& other);
                SwingBridgeSpans(SwingBridgeSpans&& other) noexcept;
                SwingBridgeSpans& operator=(const SwingBridgeSpans& other);
                SwingBridgeSpans& operator=(SwingBridgeSpans&& other) noexcept;
                void admit_vessel(std::int32_t vessel);
                std::int32_t clear_vessel();
                std::size_t hand_to(SwingBridgeSpans& dest, std::size_t count);
                std::size_t vessels() const;
                std::size_t berths() const;
                std::size_t oldest_berth() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t vessel = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            SwingBridgeSpans::SwingBridgeSpans(std::size_t berths) {
                if (berths == 0) throw BridgeConfigError("bridge needs at least one berth");
                cells_ = std::vector<Cell>(berths);
            }
            SwingBridgeSpans::SwingBridgeSpans(const SwingBridgeSpans& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            SwingBridgeSpans::SwingBridgeSpans(SwingBridgeSpans&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            SwingBridgeSpans& SwingBridgeSpans::operator=(const SwingBridgeSpans& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            SwingBridgeSpans& SwingBridgeSpans::operator=(SwingBridgeSpans&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t SwingBridgeSpans::berths() const { return cells_.size(); }
            std::size_t SwingBridgeSpans::vessels() const { return used_; }
            void SwingBridgeSpans::admit_vessel(std::int32_t vessel) {
                if (used_ == cells_.size()) throw BridgeFullError("bridge is full");
                cells_[next_].occupied = true;
                cells_[next_].vessel = vessel;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t SwingBridgeSpans::clear_vessel() {
                if (used_ == 0) throw BridgeEmptyError("bridge is empty");
                std::int32_t value = cells_[oldest_].vessel;
                cells_[oldest_].occupied = false;
                cells_[oldest_].vessel = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t SwingBridgeSpans::oldest_berth() const {
                if (used_ == 0) throw BridgeEmptyError("bridge is empty");
                return oldest_;
            }
            std::size_t SwingBridgeSpans::hand_to(SwingBridgeSpans& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.next_].occupied = true;
                    dest.cells_[dest.next_].vessel = cells_[oldest_].vessel;
                    dest.next_ = (dest.next_ + 1) % dest.cells_.size();
                    ++dest.used_;
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].vessel = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            SwingBridgeSpans::SwingBridgeSpans(std::size_t berths) {
                if (berths == 0) throw BridgeConfigError("bridge needs at least one berth");
                cells_ = std::vector<Cell>(berths);
            }
            SwingBridgeSpans::SwingBridgeSpans(const SwingBridgeSpans& other)
                : cells_(other.cells_), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {}
            SwingBridgeSpans::SwingBridgeSpans(SwingBridgeSpans&& other) noexcept
                : cells_(std::move(other.cells_)), oldest_(other.oldest_), next_(other.next_), used_(other.used_) {
                other.cells_ = std::vector<Cell>(cells_.size());
                other.oldest_ = 0;
                other.next_ = 0;
                other.used_ = 0;
            }
            SwingBridgeSpans& SwingBridgeSpans::operator=(const SwingBridgeSpans& other) {
                if (this != &other) {
                    cells_ = other.cells_;
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                }
                return *this;
            }
            SwingBridgeSpans& SwingBridgeSpans::operator=(SwingBridgeSpans&& other) noexcept {
                if (this != &other) {
                    cells_ = std::move(other.cells_);
                    oldest_ = other.oldest_;
                    next_ = other.next_;
                    used_ = other.used_;
                    other.cells_ = std::vector<Cell>(cells_.size());
                    other.oldest_ = 0;
                    other.next_ = 0;
                    other.used_ = 0;
                }
                return *this;
            }
            std::size_t SwingBridgeSpans::berths() const { return cells_.size(); }
            std::size_t SwingBridgeSpans::vessels() const { return used_; }
            void SwingBridgeSpans::admit_vessel(std::int32_t vessel) {
                if (used_ == cells_.size()) throw BridgeFullError("bridge is full");
                cells_[used_].occupied = true;
                cells_[used_].vessel = vessel;
                ++used_;
            }
            std::int32_t SwingBridgeSpans::clear_vessel() {
                if (used_ == 0) throw BridgeEmptyError("bridge is empty");
                std::int32_t value = cells_[0].vessel;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].vessel = 0;
                --used_;
                return value;
            }
            std::size_t SwingBridgeSpans::oldest_berth() const {
                if (used_ == 0) throw BridgeEmptyError("bridge is empty");
                return 0;
            }
            std::size_t SwingBridgeSpans::hand_to(SwingBridgeSpans& dest, std::size_t count) {
                std::size_t moved = 0;
                while (moved < count && used_ > 0 && dest.used_ < dest.cells_.size()) {
                    dest.cells_[dest.used_].occupied = true;
                    dest.cells_[dest.used_].vessel = cells_[used_ - 1].vessel;
                    ++dest.used_;
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].vessel = 0;
                    --used_;
                    ++moved;
                }
                return moved;
            }
            """,
            """
            SwingBridgeSpans bridge(2);
            bridge.admit_vessel(14);
            bridge.admit_vessel(28);
            if (bridge.vessels() != 2U) return 1;
            if (bridge.clear_vessel() != 14) return 2;
            bridge.admit_vessel(42);
            if (bridge.clear_vessel() != 28) return 3;
            if (bridge.clear_vessel() != 42) return 4;
            SwingBridgeSpans basin(3);
            bridge.admit_vessel(56);
            if (bridge.hand_to(basin, 1) != 1U) return 5;
            if (basin.clear_vessel() != 56) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { SwingBridgeSpans zero(0); (void)zero; } catch (const BridgeConfigError&) { threw = true; }
            if (!threw) return 1;
            SwingBridgeSpans bridge(4);
            threw = false;
            try { bridge.clear_vessel(); } catch (const BridgeEmptyError&) { threw = true; }
            if (!threw) return 2;
            bridge.admit_vessel(3);
            bridge.admit_vessel(6);
            bridge.admit_vessel(9);
            bridge.admit_vessel(12);
            threw = false;
            try { bridge.admit_vessel(15); } catch (const BridgeFullError&) { threw = true; }
            if (!threw) return 3;
            if (bridge.clear_vessel() != 3) return 4;
            if (bridge.clear_vessel() != 6) return 5;
            bridge.admit_vessel(15);
            bridge.admit_vessel(18);
            if (bridge.oldest_berth() != 2U) return 6;
            SwingBridgeSpans replica(bridge);
            if (replica.oldest_berth() != 2U) return 7;
            if (replica.clear_vessel() != 9) return 8;
            if (replica.clear_vessel() != 12) return 9;
            if (replica.clear_vessel() != 15) return 10;
            if (replica.clear_vessel() != 18) return 11;
            if (replica.vessels() != 0U) return 12;
            if (bridge.vessels() != 4U) return 13;
            SwingBridgeSpans assigned(2);
            assigned = bridge;
            if (assigned.berths() != 4U) return 14;
            if (assigned.oldest_berth() != 2U) return 15;
            SwingBridgeSpans moved(std::move(bridge));
            if (moved.oldest_berth() != 2U) return 16;
            if (bridge.vessels() != 0U) return 17;
            if (bridge.berths() != 4U) return 18;
            threw = false;
            try { bridge.oldest_berth(); } catch (const BridgeEmptyError&) { threw = true; }
            if (!threw) return 19;
            SwingBridgeSpans target(6);
            target = std::move(moved);
            if (target.berths() != 4U) return 20;
            if (target.oldest_berth() != 2U) return 21;
            if (target.clear_vessel() != 9) return 22;
            if (moved.vessels() != 0U) return 23;
            SwingBridgeSpans source(4);
            source.admit_vessel(21);
            source.admit_vessel(22);
            source.admit_vessel(23);
            source.admit_vessel(24);
            if (source.clear_vessel() != 21) return 24;
            source.admit_vessel(25);
            SwingBridgeSpans sink(2);
            if (source.hand_to(sink, 5) != 2U) return 25;
            if (source.vessels() != 2U) return 26;
            if (sink.clear_vessel() != 22) return 27;
            if (sink.clear_vessel() != 23) return 28;
            if (source.clear_vessel() != 24) return 29;
            if (source.clear_vessel() != 25) return 30;
            source.admit_vessel(26);
            source.admit_vessel(27);
            SwingBridgeSpans cup(3);
            if (source.hand_to(cup, 1) != 1U) return 31;
            if (cup.clear_vessel() != 26) return 32;
            if (source.clear_vessel() != 27) return 33;
            return 0;
            """,
            "a fixed bridge of vessel berths whose copies preserve exact physical layout, whose moves empty the source, and whose transfers move oldest-first",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store, a copy that repacks cells from slot zero, or a transfer that moves newest-first",
            "copy and move layout preservation after wraparound, moved-from source state, hand_to FIFO order with destination-full stop, full and empty channels, and zero-berth rejection",
            "bridge copy/move ring with berth slots",
            "copy/move and transfer-edge bounded ring",
        ),
        c(
            "f26cbuf-heliograph-flash-ring",
            "Heliograph flash ring",
            "heliograph",
            """
            class HelioConfigError : public std::invalid_argument {
            public:
                explicit HelioConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HelioEmptyError : public std::runtime_error {
            public:
                explicit HelioEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class HelioFullError : public std::logic_error {
            public:
                explicit HelioFullError(const std::string& message) : std::logic_error(message) {}
            };
            class HeliographFlashRing {
            public:
                explicit HeliographFlashRing(std::size_t shutters);
                void flash(std::int32_t signal);
                std::int32_t acknowledge();
                std::size_t flash_burst(const std::vector<std::int32_t>& signals);
                std::size_t skip_flashes(std::size_t count);
                std::optional<std::int32_t> peek_flash(std::size_t offset) const;
                std::size_t home_slot() const;
                std::size_t slot_at(std::size_t offset) const;
                std::size_t signals() const;
                std::size_t shutters() const;
            };
            """,
            """
            class HelioConfigError : public std::invalid_argument {
            public:
                explicit HelioConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class HelioEmptyError : public std::runtime_error {
            public:
                explicit HelioEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class HelioFullError : public std::logic_error {
            public:
                explicit HelioFullError(const std::string& message) : std::logic_error(message) {}
            };
            class HeliographFlashRing {
            public:
                explicit HeliographFlashRing(std::size_t shutters);
                void flash(std::int32_t signal);
                std::int32_t acknowledge();
                std::size_t flash_burst(const std::vector<std::int32_t>& signals);
                std::size_t skip_flashes(std::size_t count);
                std::optional<std::int32_t> peek_flash(std::size_t offset) const;
                std::size_t home_slot() const;
                std::size_t slot_at(std::size_t offset) const;
                std::size_t signals() const;
                std::size_t shutters() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t signal = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            HeliographFlashRing::HeliographFlashRing(std::size_t shutters) {
                if (shutters == 0) throw HelioConfigError("ring needs at least one shutter");
                cells_ = std::vector<Cell>(shutters);
            }
            std::size_t HeliographFlashRing::shutters() const { return cells_.size(); }
            std::size_t HeliographFlashRing::signals() const { return used_; }
            void HeliographFlashRing::flash(std::int32_t signal) {
                if (used_ == cells_.size()) throw HelioFullError("ring is full");
                cells_[next_].occupied = true;
                cells_[next_].signal = signal;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t HeliographFlashRing::acknowledge() {
                if (used_ == 0) throw HelioEmptyError("ring is empty");
                std::int32_t value = cells_[oldest_].signal;
                cells_[oldest_].occupied = false;
                cells_[oldest_].signal = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t HeliographFlashRing::flash_burst(const std::vector<std::int32_t>& signals) {
                std::size_t accepted = 0;
                for (std::int32_t signal : signals) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].signal = signal;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t HeliographFlashRing::skip_flashes(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].signal = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int32_t> HeliographFlashRing::peek_flash(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].signal;
            }
            std::size_t HeliographFlashRing::home_slot() const {
                if (used_ == 0) throw HelioEmptyError("ring is empty");
                return oldest_;
            }
            std::size_t HeliographFlashRing::slot_at(std::size_t offset) const {
                if (used_ == 0) throw HelioEmptyError("ring is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued signals");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            HeliographFlashRing::HeliographFlashRing(std::size_t shutters) {
                if (shutters == 0) throw HelioConfigError("ring needs at least one shutter");
                cells_ = std::vector<Cell>(shutters);
            }
            std::size_t HeliographFlashRing::shutters() const { return cells_.size(); }
            std::size_t HeliographFlashRing::signals() const { return used_; }
            void HeliographFlashRing::flash(std::int32_t signal) {
                if (used_ == cells_.size()) throw HelioFullError("ring is full");
                cells_[used_].occupied = true;
                cells_[used_].signal = signal;
                ++used_;
            }
            std::int32_t HeliographFlashRing::acknowledge() {
                if (used_ == 0) throw HelioEmptyError("ring is empty");
                std::int32_t value = cells_[0].signal;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].signal = 0;
                --used_;
                return value;
            }
            std::size_t HeliographFlashRing::flash_burst(const std::vector<std::int32_t>& signals) {
                std::size_t accepted = 0;
                for (std::int32_t signal : signals) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].signal = signal;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t HeliographFlashRing::skip_flashes(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].signal = 0;
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int32_t> HeliographFlashRing::peek_flash(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].signal;
            }
            std::size_t HeliographFlashRing::home_slot() const {
                if (used_ == 0) throw HelioEmptyError("ring is empty");
                return 0;
            }
            std::size_t HeliographFlashRing::slot_at(std::size_t offset) const {
                if (used_ == 0) throw HelioEmptyError("ring is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued signals");
                return offset;
            }
            """,
            """
            HeliographFlashRing ring(3);
            ring.flash(5);
            ring.flash(6);
            if (ring.acknowledge() != 5) return 1;
            if (ring.flash_burst({7, 8}) != 2U) return 2;
            if (ring.acknowledge() != 6) return 3;
            if (ring.acknowledge() != 7) return 4;
            if (ring.acknowledge() != 8) return 5;
            if (ring.signals() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { HeliographFlashRing zero(0); (void)zero; } catch (const HelioConfigError&) { threw = true; }
            if (!threw) return 1;
            HeliographFlashRing ring(4);
            threw = false;
            try { ring.acknowledge(); } catch (const HelioEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { ring.home_slot(); } catch (const HelioEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (ring.peek_flash(0).has_value()) return 4;
            if (ring.flash_burst({10, 20, 30}) != 3U) return 5;
            if (ring.acknowledge() != 10) return 6;
            if (ring.flash_burst({40, 50, 60}) != 2U) return 7;
            threw = false;
            try { ring.flash(60); } catch (const HelioFullError&) { threw = true; }
            if (!threw) return 8;
            if (ring.signals() != 4U) return 9;
            if (ring.home_slot() != 1U) return 10;
            if (ring.slot_at(0) != 1U) return 11;
            if (ring.slot_at(1) != 2U) return 12;
            if (ring.slot_at(2) != 3U) return 13;
            if (ring.slot_at(3) != 0U) return 14;
            if (!ring.peek_flash(0) || *ring.peek_flash(0) != 20) return 15;
            if (!ring.peek_flash(3) || *ring.peek_flash(3) != 50) return 16;
            if (ring.peek_flash(4).has_value()) return 17;
            threw = false;
            try { ring.slot_at(4); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 18;
            if (ring.skip_flashes(2) != 2U) return 19;
            if (ring.home_slot() != 3U) return 20;
            if (ring.signals() != 2U) return 21;
            if (!ring.peek_flash(0) || *ring.peek_flash(0) != 40) return 22;
            if (!ring.peek_flash(1) || *ring.peek_flash(1) != 50) return 23;
            if (ring.skip_flashes(9) != 2U) return 24;
            if (ring.signals() != 0U) return 25;
            return 0;
            """,
            "a fixed ring of shutter cells whose offset peeks, batch bursts, skips, and physical slot arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_slot and slot_at values after bursts and skips that wrap the ring, peek order, partial burst acceptance at capacity, full and empty channels, and zero-shutter rejection",
            "offset and batch cursor arithmetic over a physical ring",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-semaphore-arm-angles",
            "Semaphore arm angles",
            "semaphore",
            """
            class ArmConfigError : public std::invalid_argument {
            public:
                explicit ArmConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ArmEmptyError : public std::runtime_error {
            public:
                explicit ArmEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class ArmFullError : public std::logic_error {
            public:
                explicit ArmFullError(const std::string& message) : std::logic_error(message) {}
            };
            class SemaphoreArmAngles {
            public:
                explicit SemaphoreArmAngles(std::size_t positions);
                void raise(std::int32_t angle);
                std::int32_t lower();
                std::size_t raise_burst(const std::vector<std::int32_t>& angles);
                std::size_t skip_angles(std::size_t count);
                std::optional<std::int32_t> peek_angle(std::size_t offset) const;
                std::size_t home_position() const;
                std::size_t position_at(std::size_t offset) const;
                std::size_t angles() const;
                std::size_t positions() const;
            };
            """,
            """
            class ArmConfigError : public std::invalid_argument {
            public:
                explicit ArmConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class ArmEmptyError : public std::runtime_error {
            public:
                explicit ArmEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class ArmFullError : public std::logic_error {
            public:
                explicit ArmFullError(const std::string& message) : std::logic_error(message) {}
            };
            class SemaphoreArmAngles {
            public:
                explicit SemaphoreArmAngles(std::size_t positions);
                void raise(std::int32_t angle);
                std::int32_t lower();
                std::size_t raise_burst(const std::vector<std::int32_t>& angles);
                std::size_t skip_angles(std::size_t count);
                std::optional<std::int32_t> peek_angle(std::size_t offset) const;
                std::size_t home_position() const;
                std::size_t position_at(std::size_t offset) const;
                std::size_t angles() const;
                std::size_t positions() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t angle = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            SemaphoreArmAngles::SemaphoreArmAngles(std::size_t positions) {
                if (positions == 0) throw ArmConfigError("semaphore needs at least one position");
                cells_ = std::vector<Cell>(positions);
            }
            std::size_t SemaphoreArmAngles::positions() const { return cells_.size(); }
            std::size_t SemaphoreArmAngles::angles() const { return used_; }
            void SemaphoreArmAngles::raise(std::int32_t angle) {
                if (used_ == cells_.size()) throw ArmFullError("semaphore is full");
                cells_[next_].occupied = true;
                cells_[next_].angle = angle;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t SemaphoreArmAngles::lower() {
                if (used_ == 0) throw ArmEmptyError("semaphore is empty");
                std::int32_t value = cells_[oldest_].angle;
                cells_[oldest_].occupied = false;
                cells_[oldest_].angle = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t SemaphoreArmAngles::raise_burst(const std::vector<std::int32_t>& angles) {
                std::size_t accepted = 0;
                for (std::int32_t angle : angles) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].angle = angle;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t SemaphoreArmAngles::skip_angles(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].angle = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int32_t> SemaphoreArmAngles::peek_angle(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].angle;
            }
            std::size_t SemaphoreArmAngles::home_position() const {
                if (used_ == 0) throw ArmEmptyError("semaphore is empty");
                return oldest_;
            }
            std::size_t SemaphoreArmAngles::position_at(std::size_t offset) const {
                if (used_ == 0) throw ArmEmptyError("semaphore is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued angles");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            SemaphoreArmAngles::SemaphoreArmAngles(std::size_t positions) {
                if (positions == 0) throw ArmConfigError("semaphore needs at least one position");
                cells_ = std::vector<Cell>(positions);
            }
            std::size_t SemaphoreArmAngles::positions() const { return cells_.size(); }
            std::size_t SemaphoreArmAngles::angles() const { return used_; }
            void SemaphoreArmAngles::raise(std::int32_t angle) {
                if (used_ == cells_.size()) throw ArmFullError("semaphore is full");
                cells_[used_].occupied = true;
                cells_[used_].angle = angle;
                ++used_;
            }
            std::int32_t SemaphoreArmAngles::lower() {
                if (used_ == 0) throw ArmEmptyError("semaphore is empty");
                std::int32_t value = cells_[0].angle;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].angle = 0;
                --used_;
                return value;
            }
            std::size_t SemaphoreArmAngles::raise_burst(const std::vector<std::int32_t>& angles) {
                std::size_t accepted = 0;
                for (std::int32_t angle : angles) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].angle = angle;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t SemaphoreArmAngles::skip_angles(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].angle = 0;
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int32_t> SemaphoreArmAngles::peek_angle(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].angle;
            }
            std::size_t SemaphoreArmAngles::home_position() const {
                if (used_ == 0) throw ArmEmptyError("semaphore is empty");
                return 0;
            }
            std::size_t SemaphoreArmAngles::position_at(std::size_t offset) const {
                if (used_ == 0) throw ArmEmptyError("semaphore is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued angles");
                return offset;
            }
            """,
            """
            SemaphoreArmAngles arms(3);
            arms.raise(15);
            arms.raise(45);
            if (arms.lower() != 15) return 1;
            if (arms.raise_burst({90, 135}) != 2U) return 2;
            if (arms.lower() != 45) return 3;
            if (arms.lower() != 90) return 4;
            if (arms.lower() != 135) return 5;
            if (arms.angles() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { SemaphoreArmAngles zero(0); (void)zero; } catch (const ArmConfigError&) { threw = true; }
            if (!threw) return 1;
            SemaphoreArmAngles arms(3);
            threw = false;
            try { arms.lower(); } catch (const ArmEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { arms.home_position(); } catch (const ArmEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (arms.peek_angle(0).has_value()) return 4;
            if (arms.raise_burst({10, 20}) != 2U) return 5;
            if (arms.lower() != 10) return 6;
            if (arms.raise_burst({30, 40, 50}) != 2U) return 7;
            threw = false;
            try { arms.raise(50); } catch (const ArmFullError&) { threw = true; }
            if (!threw) return 8;
            if (arms.angles() != 3U) return 9;
            if (arms.home_position() != 1U) return 10;
            if (arms.position_at(0) != 1U) return 11;
            if (arms.position_at(1) != 2U) return 12;
            if (arms.position_at(2) != 0U) return 13;
            if (!arms.peek_angle(0) || *arms.peek_angle(0) != 20) return 14;
            if (!arms.peek_angle(2) || *arms.peek_angle(2) != 40) return 15;
            if (arms.peek_angle(3).has_value()) return 16;
            threw = false;
            try { arms.position_at(3); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 17;
            if (arms.skip_angles(1) != 1U) return 18;
            if (arms.home_position() != 2U) return 19;
            if (arms.angles() != 2U) return 20;
            if (!arms.peek_angle(0) || *arms.peek_angle(0) != 30) return 21;
            if (!arms.peek_angle(1) || *arms.peek_angle(1) != 40) return 22;
            if (arms.skip_angles(9) != 2U) return 23;
            if (arms.angles() != 0U) return 24;
            return 0;
            """,
            "a fixed semaphore of angle positions whose offset peeks, batch bursts, skips, and physical position arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_position and position_at values after bursts and skips that wrap the semaphore, peek order, partial burst acceptance at capacity, full and empty channels, and zero-position rejection",
            "cursor arithmetic with signal-arm positions",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
        ),
        c(
            "f26cbuf-morse-sounder-queue",
            "Morse sounder queue",
            "morse_sounder",
            """
            class SounderConfigError : public std::invalid_argument {
            public:
                explicit SounderConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SounderEmptyError : public std::runtime_error {
            public:
                explicit SounderEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class SounderFullError : public std::logic_error {
            public:
                explicit SounderFullError(const std::string& message) : std::logic_error(message) {}
            };
            class MorseSounderQueue {
            public:
                explicit MorseSounderQueue(std::size_t keys);
                void key_down(const std::string& glyph);
                std::string key_up();
                std::size_t key_burst(const std::vector<std::string>& glyphs);
                std::size_t skip_glyphs(std::size_t count);
                std::optional<std::string> peek_glyph(std::size_t offset) const;
                std::size_t home_key() const;
                std::size_t key_at(std::size_t offset) const;
                std::size_t glyphs() const;
                std::size_t keys() const;
            };
            """,
            """
            class SounderConfigError : public std::invalid_argument {
            public:
                explicit SounderConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class SounderEmptyError : public std::runtime_error {
            public:
                explicit SounderEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class SounderFullError : public std::logic_error {
            public:
                explicit SounderFullError(const std::string& message) : std::logic_error(message) {}
            };
            class MorseSounderQueue {
            public:
                explicit MorseSounderQueue(std::size_t keys);
                void key_down(const std::string& glyph);
                std::string key_up();
                std::size_t key_burst(const std::vector<std::string>& glyphs);
                std::size_t skip_glyphs(std::size_t count);
                std::optional<std::string> peek_glyph(std::size_t offset) const;
                std::size_t home_key() const;
                std::size_t key_at(std::size_t offset) const;
                std::size_t glyphs() const;
                std::size_t keys() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string glyph;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            MorseSounderQueue::MorseSounderQueue(std::size_t keys) {
                if (keys == 0) throw SounderConfigError("sounder needs at least one key");
                cells_ = std::vector<Cell>(keys);
            }
            std::size_t MorseSounderQueue::keys() const { return cells_.size(); }
            std::size_t MorseSounderQueue::glyphs() const { return used_; }
            void MorseSounderQueue::key_down(const std::string& glyph) {
                if (used_ == cells_.size()) throw SounderFullError("sounder is full");
                cells_[next_].occupied = true;
                cells_[next_].glyph = glyph;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string MorseSounderQueue::key_up() {
                if (used_ == 0) throw SounderEmptyError("sounder is empty");
                std::string value = cells_[oldest_].glyph;
                cells_[oldest_].occupied = false;
                cells_[oldest_].glyph.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t MorseSounderQueue::key_burst(const std::vector<std::string>& glyphs) {
                std::size_t accepted = 0;
                for (const std::string& glyph : glyphs) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].glyph = glyph;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t MorseSounderQueue::skip_glyphs(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].glyph.clear();
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::string> MorseSounderQueue::peek_glyph(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].glyph;
            }
            std::size_t MorseSounderQueue::home_key() const {
                if (used_ == 0) throw SounderEmptyError("sounder is empty");
                return oldest_;
            }
            std::size_t MorseSounderQueue::key_at(std::size_t offset) const {
                if (used_ == 0) throw SounderEmptyError("sounder is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued glyphs");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            MorseSounderQueue::MorseSounderQueue(std::size_t keys) {
                if (keys == 0) throw SounderConfigError("sounder needs at least one key");
                cells_ = std::vector<Cell>(keys);
            }
            std::size_t MorseSounderQueue::keys() const { return cells_.size(); }
            std::size_t MorseSounderQueue::glyphs() const { return used_; }
            void MorseSounderQueue::key_down(const std::string& glyph) {
                if (used_ == cells_.size()) throw SounderFullError("sounder is full");
                cells_[used_].occupied = true;
                cells_[used_].glyph = glyph;
                ++used_;
            }
            std::string MorseSounderQueue::key_up() {
                if (used_ == 0) throw SounderEmptyError("sounder is empty");
                std::string value = cells_[0].glyph;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].glyph.clear();
                --used_;
                return value;
            }
            std::size_t MorseSounderQueue::key_burst(const std::vector<std::string>& glyphs) {
                std::size_t accepted = 0;
                for (const std::string& glyph : glyphs) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].glyph = glyph;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t MorseSounderQueue::skip_glyphs(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].glyph.clear();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::string> MorseSounderQueue::peek_glyph(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].glyph;
            }
            std::size_t MorseSounderQueue::home_key() const {
                if (used_ == 0) throw SounderEmptyError("sounder is empty");
                return 0;
            }
            std::size_t MorseSounderQueue::key_at(std::size_t offset) const {
                if (used_ == 0) throw SounderEmptyError("sounder is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued glyphs");
                return offset;
            }
            """,
            """
            MorseSounderQueue queue(3);
            queue.key_down("dit");
            queue.key_down("dah");
            if (queue.key_up() != "dit") return 1;
            if (queue.key_burst({"dit", "dit"}) != 2U) return 2;
            if (queue.key_up() != "dah") return 3;
            if (queue.key_up() != "dit") return 4;
            if (queue.key_up() != "dit") return 5;
            if (queue.glyphs() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { MorseSounderQueue zero(0); (void)zero; } catch (const SounderConfigError&) { threw = true; }
            if (!threw) return 1;
            MorseSounderQueue queue(3);
            threw = false;
            try { queue.key_up(); } catch (const SounderEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { queue.home_key(); } catch (const SounderEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (queue.peek_glyph(0).has_value()) return 4;
            if (queue.key_burst({"dit", "dah"}) != 2U) return 5;
            if (queue.key_up() != "dit") return 6;
            if (queue.key_burst({"dit", "dah", "dit"}) != 2U) return 7;
            threw = false;
            try { queue.key_down("dah"); } catch (const SounderFullError&) { threw = true; }
            if (!threw) return 8;
            if (queue.glyphs() != 3U) return 9;
            if (queue.home_key() != 1U) return 10;
            if (queue.key_at(0) != 1U) return 11;
            if (queue.key_at(1) != 2U) return 12;
            if (queue.key_at(2) != 0U) return 13;
            if (!queue.peek_glyph(0) || *queue.peek_glyph(0) != "dah") return 14;
            if (!queue.peek_glyph(2) || *queue.peek_glyph(2) != "dah") return 15;
            if (queue.peek_glyph(3).has_value()) return 16;
            threw = false;
            try { queue.key_at(3); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 17;
            if (queue.skip_glyphs(1) != 1U) return 18;
            if (queue.home_key() != 2U) return 19;
            if (queue.glyphs() != 2U) return 20;
            if (!queue.peek_glyph(0) || *queue.peek_glyph(0) != "dit") return 21;
            if (!queue.peek_glyph(1) || *queue.peek_glyph(1) != "dah") return 22;
            if (queue.skip_glyphs(9) != 2U) return 23;
            if (queue.glyphs() != 0U) return 24;
            return 0;
            """,
            "a fixed sounder of glyph keys whose offset peeks, batch bursts, skips, and physical key arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_key and key_at values after bursts and skips that wrap the sounder, peek order, partial burst acceptance at capacity, full and empty channels, and zero-key rejection",
            "string cursor/batch ring with sounder keys",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
        ),
        c(
            "f26cbuf-telescope-dome-slits",
            "Telescope dome slits",
            "telescope_dome",
            """
            class DomeConfigError : public std::invalid_argument {
            public:
                explicit DomeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DomeEmptyError : public std::runtime_error {
            public:
                explicit DomeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DomeFullError : public std::logic_error {
            public:
                explicit DomeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TelescopeDomeSlits {
            public:
                explicit TelescopeDomeSlits(std::size_t slits);
                void expose_plate(std::int64_t plate);
                std::int64_t develop_plate();
                std::size_t expose_burst(const std::vector<std::int64_t>& plates);
                std::size_t skip_plates(std::size_t count);
                std::optional<std::int64_t> peek_plate(std::size_t offset) const;
                std::size_t home_slit() const;
                std::size_t slit_at(std::size_t offset) const;
                std::size_t plates() const;
                std::size_t slits() const;
            };
            """,
            """
            class DomeConfigError : public std::invalid_argument {
            public:
                explicit DomeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DomeEmptyError : public std::runtime_error {
            public:
                explicit DomeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DomeFullError : public std::logic_error {
            public:
                explicit DomeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class TelescopeDomeSlits {
            public:
                explicit TelescopeDomeSlits(std::size_t slits);
                void expose_plate(std::int64_t plate);
                std::int64_t develop_plate();
                std::size_t expose_burst(const std::vector<std::int64_t>& plates);
                std::size_t skip_plates(std::size_t count);
                std::optional<std::int64_t> peek_plate(std::size_t offset) const;
                std::size_t home_slit() const;
                std::size_t slit_at(std::size_t offset) const;
                std::size_t plates() const;
                std::size_t slits() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t plate = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            TelescopeDomeSlits::TelescopeDomeSlits(std::size_t slits) {
                if (slits == 0) throw DomeConfigError("dome needs at least one slit");
                cells_ = std::vector<Cell>(slits);
            }
            std::size_t TelescopeDomeSlits::slits() const { return cells_.size(); }
            std::size_t TelescopeDomeSlits::plates() const { return used_; }
            void TelescopeDomeSlits::expose_plate(std::int64_t plate) {
                if (used_ == cells_.size()) throw DomeFullError("dome is full");
                cells_[next_].occupied = true;
                cells_[next_].plate = plate;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t TelescopeDomeSlits::develop_plate() {
                if (used_ == 0) throw DomeEmptyError("dome is empty");
                std::int64_t value = cells_[oldest_].plate;
                cells_[oldest_].occupied = false;
                cells_[oldest_].plate = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t TelescopeDomeSlits::expose_burst(const std::vector<std::int64_t>& plates) {
                std::size_t accepted = 0;
                for (std::int64_t plate : plates) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].plate = plate;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t TelescopeDomeSlits::skip_plates(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].plate = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int64_t> TelescopeDomeSlits::peek_plate(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].plate;
            }
            std::size_t TelescopeDomeSlits::home_slit() const {
                if (used_ == 0) throw DomeEmptyError("dome is empty");
                return oldest_;
            }
            std::size_t TelescopeDomeSlits::slit_at(std::size_t offset) const {
                if (used_ == 0) throw DomeEmptyError("dome is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued plates");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            TelescopeDomeSlits::TelescopeDomeSlits(std::size_t slits) {
                if (slits == 0) throw DomeConfigError("dome needs at least one slit");
                cells_ = std::vector<Cell>(slits);
            }
            std::size_t TelescopeDomeSlits::slits() const { return cells_.size(); }
            std::size_t TelescopeDomeSlits::plates() const { return used_; }
            void TelescopeDomeSlits::expose_plate(std::int64_t plate) {
                if (used_ == cells_.size()) throw DomeFullError("dome is full");
                cells_[used_].occupied = true;
                cells_[used_].plate = plate;
                ++used_;
            }
            std::int64_t TelescopeDomeSlits::develop_plate() {
                if (used_ == 0) throw DomeEmptyError("dome is empty");
                std::int64_t value = cells_[0].plate;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].plate = 0;
                --used_;
                return value;
            }
            std::size_t TelescopeDomeSlits::expose_burst(const std::vector<std::int64_t>& plates) {
                std::size_t accepted = 0;
                for (std::int64_t plate : plates) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].plate = plate;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t TelescopeDomeSlits::skip_plates(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].plate = 0;
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int64_t> TelescopeDomeSlits::peek_plate(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].plate;
            }
            std::size_t TelescopeDomeSlits::home_slit() const {
                if (used_ == 0) throw DomeEmptyError("dome is empty");
                return 0;
            }
            std::size_t TelescopeDomeSlits::slit_at(std::size_t offset) const {
                if (used_ == 0) throw DomeEmptyError("dome is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued plates");
                return offset;
            }
            """,
            """
            TelescopeDomeSlits dome(3);
            dome.expose_plate(700);
            dome.expose_plate(800);
            if (dome.develop_plate() != 700) return 1;
            if (dome.expose_burst({900, 1000}) != 2U) return 2;
            if (dome.develop_plate() != 800) return 3;
            if (dome.develop_plate() != 900) return 4;
            if (dome.develop_plate() != 1000) return 5;
            if (dome.plates() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { TelescopeDomeSlits zero(0); (void)zero; } catch (const DomeConfigError&) { threw = true; }
            if (!threw) return 1;
            TelescopeDomeSlits dome(4);
            threw = false;
            try { dome.develop_plate(); } catch (const DomeEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { dome.home_slit(); } catch (const DomeEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (dome.peek_plate(0).has_value()) return 4;
            if (dome.expose_burst({100, 200, 300}) != 3U) return 5;
            if (dome.develop_plate() != 100) return 6;
            if (dome.expose_burst({400, 500, 600}) != 2U) return 7;
            threw = false;
            try { dome.expose_plate(600); } catch (const DomeFullError&) { threw = true; }
            if (!threw) return 8;
            if (dome.plates() != 4U) return 9;
            if (dome.home_slit() != 1U) return 10;
            if (dome.slit_at(0) != 1U) return 11;
            if (dome.slit_at(1) != 2U) return 12;
            if (dome.slit_at(2) != 3U) return 13;
            if (dome.slit_at(3) != 0U) return 14;
            if (!dome.peek_plate(0) || *dome.peek_plate(0) != 200) return 15;
            if (!dome.peek_plate(3) || *dome.peek_plate(3) != 500) return 16;
            if (dome.peek_plate(4).has_value()) return 17;
            threw = false;
            try { dome.slit_at(4); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 18;
            if (dome.skip_plates(2) != 2U) return 19;
            if (dome.home_slit() != 3U) return 20;
            if (dome.plates() != 2U) return 21;
            if (!dome.peek_plate(0) || *dome.peek_plate(0) != 400) return 22;
            if (!dome.peek_plate(1) || *dome.peek_plate(1) != 500) return 23;
            if (dome.skip_plates(9) != 2U) return 24;
            if (dome.plates() != 0U) return 25;
            return 0;
            """,
            "a fixed dome of plate slits whose offset peeks, batch bursts, skips, and physical slit arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_slit and slit_at values after bursts and skips that wrap the dome, peek order, partial burst acceptance at capacity, full and empty channels, and zero-slit rejection",
            "project-context int64 cursor/batch ring",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-sundial-shadow-marks",
            "Sundial shadow marks",
            "sundial",
            """
            class DialConfigError : public std::invalid_argument {
            public:
                explicit DialConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DialEmptyError : public std::runtime_error {
            public:
                explicit DialEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DialFullError : public std::logic_error {
            public:
                explicit DialFullError(const std::string& message) : std::logic_error(message) {}
            };
            class SundialShadowMarks {
            public:
                explicit SundialShadowMarks(std::size_t numerals);
                void mark(std::int32_t hour);
                std::int32_t erase();
                std::size_t mark_burst(const std::vector<std::int32_t>& hours);
                std::size_t skip_marks(std::size_t count);
                std::optional<std::int32_t> peek_mark(std::size_t offset) const;
                std::size_t home_numeral() const;
                std::size_t numeral_at(std::size_t offset) const;
                std::size_t marks() const;
                std::size_t numerals() const;
            };
            """,
            """
            class DialConfigError : public std::invalid_argument {
            public:
                explicit DialConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class DialEmptyError : public std::runtime_error {
            public:
                explicit DialEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class DialFullError : public std::logic_error {
            public:
                explicit DialFullError(const std::string& message) : std::logic_error(message) {}
            };
            class SundialShadowMarks {
            public:
                explicit SundialShadowMarks(std::size_t numerals);
                void mark(std::int32_t hour);
                std::int32_t erase();
                std::size_t mark_burst(const std::vector<std::int32_t>& hours);
                std::size_t skip_marks(std::size_t count);
                std::optional<std::int32_t> peek_mark(std::size_t offset) const;
                std::size_t home_numeral() const;
                std::size_t numeral_at(std::size_t offset) const;
                std::size_t marks() const;
                std::size_t numerals() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t hour = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            SundialShadowMarks::SundialShadowMarks(std::size_t numerals) {
                if (numerals == 0) throw DialConfigError("dial needs at least one numeral");
                cells_ = std::vector<Cell>(numerals);
            }
            std::size_t SundialShadowMarks::numerals() const { return cells_.size(); }
            std::size_t SundialShadowMarks::marks() const { return used_; }
            void SundialShadowMarks::mark(std::int32_t hour) {
                if (used_ == cells_.size()) throw DialFullError("dial is full");
                cells_[next_].occupied = true;
                cells_[next_].hour = hour;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t SundialShadowMarks::erase() {
                if (used_ == 0) throw DialEmptyError("dial is empty");
                std::int32_t value = cells_[oldest_].hour;
                cells_[oldest_].occupied = false;
                cells_[oldest_].hour = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t SundialShadowMarks::mark_burst(const std::vector<std::int32_t>& hours) {
                std::size_t accepted = 0;
                for (std::int32_t hour : hours) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].hour = hour;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t SundialShadowMarks::skip_marks(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].hour = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int32_t> SundialShadowMarks::peek_mark(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].hour;
            }
            std::size_t SundialShadowMarks::home_numeral() const {
                if (used_ == 0) throw DialEmptyError("dial is empty");
                return oldest_;
            }
            std::size_t SundialShadowMarks::numeral_at(std::size_t offset) const {
                if (used_ == 0) throw DialEmptyError("dial is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued marks");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            SundialShadowMarks::SundialShadowMarks(std::size_t numerals) {
                if (numerals == 0) throw DialConfigError("dial needs at least one numeral");
                cells_ = std::vector<Cell>(numerals);
            }
            std::size_t SundialShadowMarks::numerals() const { return cells_.size(); }
            std::size_t SundialShadowMarks::marks() const { return used_; }
            void SundialShadowMarks::mark(std::int32_t hour) {
                if (used_ == cells_.size()) throw DialFullError("dial is full");
                cells_[used_].occupied = true;
                cells_[used_].hour = hour;
                ++used_;
            }
            std::int32_t SundialShadowMarks::erase() {
                if (used_ == 0) throw DialEmptyError("dial is empty");
                std::int32_t value = cells_[0].hour;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].hour = 0;
                --used_;
                return value;
            }
            std::size_t SundialShadowMarks::mark_burst(const std::vector<std::int32_t>& hours) {
                std::size_t accepted = 0;
                for (std::int32_t hour : hours) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].hour = hour;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t SundialShadowMarks::skip_marks(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].hour = 0;
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int32_t> SundialShadowMarks::peek_mark(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].hour;
            }
            std::size_t SundialShadowMarks::home_numeral() const {
                if (used_ == 0) throw DialEmptyError("dial is empty");
                return 0;
            }
            std::size_t SundialShadowMarks::numeral_at(std::size_t offset) const {
                if (used_ == 0) throw DialEmptyError("dial is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued marks");
                return offset;
            }
            """,
            """
            SundialShadowMarks dial(3);
            dial.mark(6);
            dial.mark(9);
            if (dial.erase() != 6) return 1;
            if (dial.mark_burst({12, 15}) != 2U) return 2;
            if (dial.erase() != 9) return 3;
            if (dial.erase() != 12) return 4;
            if (dial.erase() != 15) return 5;
            if (dial.marks() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { SundialShadowMarks zero(0); (void)zero; } catch (const DialConfigError&) { threw = true; }
            if (!threw) return 1;
            SundialShadowMarks dial(3);
            threw = false;
            try { dial.erase(); } catch (const DialEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { dial.home_numeral(); } catch (const DialEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (dial.peek_mark(0).has_value()) return 4;
            if (dial.mark_burst({6, 9}) != 2U) return 5;
            if (dial.erase() != 6) return 6;
            if (dial.mark_burst({12, 15, 18}) != 2U) return 7;
            threw = false;
            try { dial.mark(18); } catch (const DialFullError&) { threw = true; }
            if (!threw) return 8;
            if (dial.marks() != 3U) return 9;
            if (dial.home_numeral() != 1U) return 10;
            if (dial.numeral_at(0) != 1U) return 11;
            if (dial.numeral_at(1) != 2U) return 12;
            if (dial.numeral_at(2) != 0U) return 13;
            if (!dial.peek_mark(0) || *dial.peek_mark(0) != 9) return 14;
            if (!dial.peek_mark(2) || *dial.peek_mark(2) != 15) return 15;
            if (dial.peek_mark(3).has_value()) return 16;
            threw = false;
            try { dial.numeral_at(3); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 17;
            if (dial.skip_marks(1) != 1U) return 18;
            if (dial.home_numeral() != 2U) return 19;
            if (dial.marks() != 2U) return 20;
            if (!dial.peek_mark(0) || *dial.peek_mark(0) != 12) return 21;
            if (!dial.peek_mark(1) || *dial.peek_mark(1) != 15) return 22;
            if (dial.skip_marks(9) != 2U) return 23;
            if (dial.marks() != 0U) return 24;
            return 0;
            """,
            "a fixed dial of hour numerals whose offset peeks, batch bursts, skips, and physical numeral arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_numeral and numeral_at values after bursts and skips that wrap the dial, peek order, partial burst acceptance at capacity, full and empty channels, and zero-numeral rejection",
            "dial cursor arithmetic with physical numerals",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
        ),
        c(
            "f26cbuf-belltower-chime-wheel",
            "Belltower chime wheel",
            "belltower",
            """
            class TowerConfigError : public std::invalid_argument {
            public:
                explicit TowerConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TowerEmptyError : public std::runtime_error {
            public:
                explicit TowerEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TowerFullError : public std::logic_error {
            public:
                explicit TowerFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BelltowerChimeWheel {
            public:
                explicit BelltowerChimeWheel(std::size_t hammers);
                void toll(const std::string& note);
                std::string dampen();
                std::size_t toll_burst(const std::vector<std::string>& notes);
                std::size_t skip_tolls(std::size_t count);
                std::optional<std::string> peek_toll(std::size_t offset) const;
                std::size_t home_hammer() const;
                std::size_t hammer_at(std::size_t offset) const;
                std::size_t tolls() const;
                std::size_t hammers() const;
            };
            """,
            """
            class TowerConfigError : public std::invalid_argument {
            public:
                explicit TowerConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class TowerEmptyError : public std::runtime_error {
            public:
                explicit TowerEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class TowerFullError : public std::logic_error {
            public:
                explicit TowerFullError(const std::string& message) : std::logic_error(message) {}
            };
            class BelltowerChimeWheel {
            public:
                explicit BelltowerChimeWheel(std::size_t hammers);
                void toll(const std::string& note);
                std::string dampen();
                std::size_t toll_burst(const std::vector<std::string>& notes);
                std::size_t skip_tolls(std::size_t count);
                std::optional<std::string> peek_toll(std::size_t offset) const;
                std::size_t home_hammer() const;
                std::size_t hammer_at(std::size_t offset) const;
                std::size_t tolls() const;
                std::size_t hammers() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::string note;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            BelltowerChimeWheel::BelltowerChimeWheel(std::size_t hammers) {
                if (hammers == 0) throw TowerConfigError("tower needs at least one hammer");
                cells_ = std::vector<Cell>(hammers);
            }
            std::size_t BelltowerChimeWheel::hammers() const { return cells_.size(); }
            std::size_t BelltowerChimeWheel::tolls() const { return used_; }
            void BelltowerChimeWheel::toll(const std::string& note) {
                if (used_ == cells_.size()) throw TowerFullError("tower is full");
                cells_[next_].occupied = true;
                cells_[next_].note = note;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::string BelltowerChimeWheel::dampen() {
                if (used_ == 0) throw TowerEmptyError("tower is empty");
                std::string value = cells_[oldest_].note;
                cells_[oldest_].occupied = false;
                cells_[oldest_].note.clear();
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t BelltowerChimeWheel::toll_burst(const std::vector<std::string>& notes) {
                std::size_t accepted = 0;
                for (const std::string& note : notes) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].note = note;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t BelltowerChimeWheel::skip_tolls(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].note.clear();
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::string> BelltowerChimeWheel::peek_toll(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].note;
            }
            std::size_t BelltowerChimeWheel::home_hammer() const {
                if (used_ == 0) throw TowerEmptyError("tower is empty");
                return oldest_;
            }
            std::size_t BelltowerChimeWheel::hammer_at(std::size_t offset) const {
                if (used_ == 0) throw TowerEmptyError("tower is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued tolls");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            BelltowerChimeWheel::BelltowerChimeWheel(std::size_t hammers) {
                if (hammers == 0) throw TowerConfigError("tower needs at least one hammer");
                cells_ = std::vector<Cell>(hammers);
            }
            std::size_t BelltowerChimeWheel::hammers() const { return cells_.size(); }
            std::size_t BelltowerChimeWheel::tolls() const { return used_; }
            void BelltowerChimeWheel::toll(const std::string& note) {
                if (used_ == cells_.size()) throw TowerFullError("tower is full");
                cells_[used_].occupied = true;
                cells_[used_].note = note;
                ++used_;
            }
            std::string BelltowerChimeWheel::dampen() {
                if (used_ == 0) throw TowerEmptyError("tower is empty");
                std::string value = cells_[0].note;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].note.clear();
                --used_;
                return value;
            }
            std::size_t BelltowerChimeWheel::toll_burst(const std::vector<std::string>& notes) {
                std::size_t accepted = 0;
                for (const std::string& note : notes) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].note = note;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t BelltowerChimeWheel::skip_tolls(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].note.clear();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::string> BelltowerChimeWheel::peek_toll(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].note;
            }
            std::size_t BelltowerChimeWheel::home_hammer() const {
                if (used_ == 0) throw TowerEmptyError("tower is empty");
                return 0;
            }
            std::size_t BelltowerChimeWheel::hammer_at(std::size_t offset) const {
                if (used_ == 0) throw TowerEmptyError("tower is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued tolls");
                return offset;
            }
            """,
            """
            BelltowerChimeWheel wheel(3);
            wheel.toll("ding");
            wheel.toll("dong");
            if (wheel.dampen() != "ding") return 1;
            if (wheel.toll_burst({"clang", "bong"}) != 2U) return 2;
            if (wheel.dampen() != "dong") return 3;
            if (wheel.dampen() != "clang") return 4;
            if (wheel.dampen() != "bong") return 5;
            if (wheel.tolls() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { BelltowerChimeWheel zero(0); (void)zero; } catch (const TowerConfigError&) { threw = true; }
            if (!threw) return 1;
            BelltowerChimeWheel wheel(3);
            threw = false;
            try { wheel.dampen(); } catch (const TowerEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { wheel.home_hammer(); } catch (const TowerEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (wheel.peek_toll(0).has_value()) return 4;
            if (wheel.toll_burst({"ding", "dong"}) != 2U) return 5;
            if (wheel.dampen() != "ding") return 6;
            if (wheel.toll_burst({"clang", "bong", "knell"}) != 2U) return 7;
            threw = false;
            try { wheel.toll("knell"); } catch (const TowerFullError&) { threw = true; }
            if (!threw) return 8;
            if (wheel.tolls() != 3U) return 9;
            if (wheel.home_hammer() != 1U) return 10;
            if (wheel.hammer_at(0) != 1U) return 11;
            if (wheel.hammer_at(1) != 2U) return 12;
            if (wheel.hammer_at(2) != 0U) return 13;
            if (!wheel.peek_toll(0) || *wheel.peek_toll(0) != "dong") return 14;
            if (!wheel.peek_toll(2) || *wheel.peek_toll(2) != "bong") return 15;
            if (wheel.peek_toll(3).has_value()) return 16;
            threw = false;
            try { wheel.hammer_at(3); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 17;
            if (wheel.skip_tolls(1) != 1U) return 18;
            if (wheel.home_hammer() != 2U) return 19;
            if (wheel.tolls() != 2U) return 20;
            if (!wheel.peek_toll(0) || *wheel.peek_toll(0) != "clang") return 21;
            if (!wheel.peek_toll(1) || *wheel.peek_toll(1) != "bong") return 22;
            if (wheel.skip_tolls(9) != 2U) return 23;
            if (wheel.tolls() != 0U) return 24;
            return 0;
            """,
            "a fixed wheel of note hammers whose offset peeks, batch bursts, skips, and physical hammer arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_hammer and hammer_at values after bursts and skips that wrap the wheel, peek order, partial burst acceptance at capacity, full and empty channels, and zero-hammer rejection",
            "project-context string cursor/batch ring",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-astrolabe-plate-marks",
            "Astrolabe plate marks",
            "astrolabe",
            """
            class AstrolabeConfigError : public std::invalid_argument {
            public:
                explicit AstrolabeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class AstrolabeEmptyError : public std::runtime_error {
            public:
                explicit AstrolabeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class AstrolabeFullError : public std::logic_error {
            public:
                explicit AstrolabeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class AstrolabePlateMarks {
            public:
                explicit AstrolabePlateMarks(std::size_t tympans);
                void sight(std::int64_t star);
                std::int64_t unsight();
                std::size_t sight_burst(const std::vector<std::int64_t>& stars);
                std::size_t skip_stars(std::size_t count);
                std::optional<std::int64_t> peek_star(std::size_t offset) const;
                std::size_t home_tympan() const;
                std::size_t tympan_at(std::size_t offset) const;
                std::size_t stars() const;
                std::size_t tympans() const;
            };
            """,
            """
            class AstrolabeConfigError : public std::invalid_argument {
            public:
                explicit AstrolabeConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class AstrolabeEmptyError : public std::runtime_error {
            public:
                explicit AstrolabeEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class AstrolabeFullError : public std::logic_error {
            public:
                explicit AstrolabeFullError(const std::string& message) : std::logic_error(message) {}
            };
            class AstrolabePlateMarks {
            public:
                explicit AstrolabePlateMarks(std::size_t tympans);
                void sight(std::int64_t star);
                std::int64_t unsight();
                std::size_t sight_burst(const std::vector<std::int64_t>& stars);
                std::size_t skip_stars(std::size_t count);
                std::optional<std::int64_t> peek_star(std::size_t offset) const;
                std::size_t home_tympan() const;
                std::size_t tympan_at(std::size_t offset) const;
                std::size_t stars() const;
                std::size_t tympans() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t star = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            AstrolabePlateMarks::AstrolabePlateMarks(std::size_t tympans) {
                if (tympans == 0) throw AstrolabeConfigError("astrolabe needs at least one tympan");
                cells_ = std::vector<Cell>(tympans);
            }
            std::size_t AstrolabePlateMarks::tympans() const { return cells_.size(); }
            std::size_t AstrolabePlateMarks::stars() const { return used_; }
            void AstrolabePlateMarks::sight(std::int64_t star) {
                if (used_ == cells_.size()) throw AstrolabeFullError("astrolabe is full");
                cells_[next_].occupied = true;
                cells_[next_].star = star;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t AstrolabePlateMarks::unsight() {
                if (used_ == 0) throw AstrolabeEmptyError("astrolabe is empty");
                std::int64_t value = cells_[oldest_].star;
                cells_[oldest_].occupied = false;
                cells_[oldest_].star = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t AstrolabePlateMarks::sight_burst(const std::vector<std::int64_t>& stars) {
                std::size_t accepted = 0;
                for (std::int64_t star : stars) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].star = star;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t AstrolabePlateMarks::skip_stars(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].star = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int64_t> AstrolabePlateMarks::peek_star(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].star;
            }
            std::size_t AstrolabePlateMarks::home_tympan() const {
                if (used_ == 0) throw AstrolabeEmptyError("astrolabe is empty");
                return oldest_;
            }
            std::size_t AstrolabePlateMarks::tympan_at(std::size_t offset) const {
                if (used_ == 0) throw AstrolabeEmptyError("astrolabe is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued stars");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            AstrolabePlateMarks::AstrolabePlateMarks(std::size_t tympans) {
                if (tympans == 0) throw AstrolabeConfigError("astrolabe needs at least one tympan");
                cells_ = std::vector<Cell>(tympans);
            }
            std::size_t AstrolabePlateMarks::tympans() const { return cells_.size(); }
            std::size_t AstrolabePlateMarks::stars() const { return used_; }
            void AstrolabePlateMarks::sight(std::int64_t star) {
                if (used_ == cells_.size()) throw AstrolabeFullError("astrolabe is full");
                cells_[used_].occupied = true;
                cells_[used_].star = star;
                ++used_;
            }
            std::int64_t AstrolabePlateMarks::unsight() {
                if (used_ == 0) throw AstrolabeEmptyError("astrolabe is empty");
                std::int64_t value = cells_[0].star;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].star = 0;
                --used_;
                return value;
            }
            std::size_t AstrolabePlateMarks::sight_burst(const std::vector<std::int64_t>& stars) {
                std::size_t accepted = 0;
                for (std::int64_t star : stars) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].star = star;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t AstrolabePlateMarks::skip_stars(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].star = 0;
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int64_t> AstrolabePlateMarks::peek_star(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].star;
            }
            std::size_t AstrolabePlateMarks::home_tympan() const {
                if (used_ == 0) throw AstrolabeEmptyError("astrolabe is empty");
                return 0;
            }
            std::size_t AstrolabePlateMarks::tympan_at(std::size_t offset) const {
                if (used_ == 0) throw AstrolabeEmptyError("astrolabe is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued stars");
                return offset;
            }
            """,
            """
            AstrolabePlateMarks plate(3);
            plate.sight(210);
            plate.sight(220);
            if (plate.unsight() != 210) return 1;
            if (plate.sight_burst({230, 240}) != 2U) return 2;
            if (plate.unsight() != 220) return 3;
            if (plate.unsight() != 230) return 4;
            if (plate.unsight() != 240) return 5;
            if (plate.stars() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { AstrolabePlateMarks zero(0); (void)zero; } catch (const AstrolabeConfigError&) { threw = true; }
            if (!threw) return 1;
            AstrolabePlateMarks plate(4);
            threw = false;
            try { plate.unsight(); } catch (const AstrolabeEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { plate.home_tympan(); } catch (const AstrolabeEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (plate.peek_star(0).has_value()) return 4;
            if (plate.sight_burst({110, 120, 130}) != 3U) return 5;
            if (plate.unsight() != 110) return 6;
            if (plate.sight_burst({140, 150, 160}) != 2U) return 7;
            threw = false;
            try { plate.sight(160); } catch (const AstrolabeFullError&) { threw = true; }
            if (!threw) return 8;
            if (plate.stars() != 4U) return 9;
            if (plate.home_tympan() != 1U) return 10;
            if (plate.tympan_at(0) != 1U) return 11;
            if (plate.tympan_at(1) != 2U) return 12;
            if (plate.tympan_at(2) != 3U) return 13;
            if (plate.tympan_at(3) != 0U) return 14;
            if (!plate.peek_star(0) || *plate.peek_star(0) != 120) return 15;
            if (!plate.peek_star(3) || *plate.peek_star(3) != 150) return 16;
            if (plate.peek_star(4).has_value()) return 17;
            threw = false;
            try { plate.tympan_at(4); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 18;
            if (plate.skip_stars(2) != 2U) return 19;
            if (plate.home_tympan() != 3U) return 20;
            if (plate.stars() != 2U) return 21;
            if (!plate.peek_star(0) || *plate.peek_star(0) != 140) return 22;
            if (!plate.peek_star(1) || *plate.peek_star(1) != 150) return 23;
            if (plate.skip_stars(9) != 2U) return 24;
            if (plate.stars() != 0U) return 25;
            return 0;
            """,
            "a fixed astrolabe of star tympans whose offset peeks, batch bursts, skips, and physical tympan arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_tympan and tympan_at values after bursts and skips that wrap the astrolabe, peek order, partial burst acceptance at capacity, full and empty channels, and zero-tympan rejection",
            "int64 cursor arithmetic with tympan slots",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
        ),
        c(
            "f26cbuf-orrery-planet-tracks",
            "Orrery planet tracks",
            "orrery",
            """
            class OrreryConfigError : public std::invalid_argument {
            public:
                explicit OrreryConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class OrreryEmptyError : public std::runtime_error {
            public:
                explicit OrreryEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class OrreryFullError : public std::logic_error {
            public:
                explicit OrreryFullError(const std::string& message) : std::logic_error(message) {}
            };
            class OrreryPlanetTracks {
            public:
                explicit OrreryPlanetTracks(std::size_t tracks);
                void crank(std::int32_t orbit);
                std::int32_t release_orbit();
                std::size_t crank_burst(const std::vector<std::int32_t>& orbits);
                std::size_t skip_orbits(std::size_t count);
                std::optional<std::int32_t> peek_orbit(std::size_t offset) const;
                std::size_t home_track() const;
                std::size_t track_at(std::size_t offset) const;
                std::size_t orbits() const;
                std::size_t tracks() const;
            };
            """,
            """
            class OrreryConfigError : public std::invalid_argument {
            public:
                explicit OrreryConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class OrreryEmptyError : public std::runtime_error {
            public:
                explicit OrreryEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class OrreryFullError : public std::logic_error {
            public:
                explicit OrreryFullError(const std::string& message) : std::logic_error(message) {}
            };
            class OrreryPlanetTracks {
            public:
                explicit OrreryPlanetTracks(std::size_t tracks);
                void crank(std::int32_t orbit);
                std::int32_t release_orbit();
                std::size_t crank_burst(const std::vector<std::int32_t>& orbits);
                std::size_t skip_orbits(std::size_t count);
                std::optional<std::int32_t> peek_orbit(std::size_t offset) const;
                std::size_t home_track() const;
                std::size_t track_at(std::size_t offset) const;
                std::size_t orbits() const;
                std::size_t tracks() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int32_t orbit = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            OrreryPlanetTracks::OrreryPlanetTracks(std::size_t tracks) {
                if (tracks == 0) throw OrreryConfigError("orrery needs at least one track");
                cells_ = std::vector<Cell>(tracks);
            }
            std::size_t OrreryPlanetTracks::tracks() const { return cells_.size(); }
            std::size_t OrreryPlanetTracks::orbits() const { return used_; }
            void OrreryPlanetTracks::crank(std::int32_t orbit) {
                if (used_ == cells_.size()) throw OrreryFullError("orrery is full");
                cells_[next_].occupied = true;
                cells_[next_].orbit = orbit;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int32_t OrreryPlanetTracks::release_orbit() {
                if (used_ == 0) throw OrreryEmptyError("orrery is empty");
                std::int32_t value = cells_[oldest_].orbit;
                cells_[oldest_].occupied = false;
                cells_[oldest_].orbit = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t OrreryPlanetTracks::crank_burst(const std::vector<std::int32_t>& orbits) {
                std::size_t accepted = 0;
                for (std::int32_t orbit : orbits) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].orbit = orbit;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t OrreryPlanetTracks::skip_orbits(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].orbit = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int32_t> OrreryPlanetTracks::peek_orbit(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].orbit;
            }
            std::size_t OrreryPlanetTracks::home_track() const {
                if (used_ == 0) throw OrreryEmptyError("orrery is empty");
                return oldest_;
            }
            std::size_t OrreryPlanetTracks::track_at(std::size_t offset) const {
                if (used_ == 0) throw OrreryEmptyError("orrery is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued orbits");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            OrreryPlanetTracks::OrreryPlanetTracks(std::size_t tracks) {
                if (tracks == 0) throw OrreryConfigError("orrery needs at least one track");
                cells_ = std::vector<Cell>(tracks);
            }
            std::size_t OrreryPlanetTracks::tracks() const { return cells_.size(); }
            std::size_t OrreryPlanetTracks::orbits() const { return used_; }
            void OrreryPlanetTracks::crank(std::int32_t orbit) {
                if (used_ == cells_.size()) throw OrreryFullError("orrery is full");
                cells_[used_].occupied = true;
                cells_[used_].orbit = orbit;
                ++used_;
            }
            std::int32_t OrreryPlanetTracks::release_orbit() {
                if (used_ == 0) throw OrreryEmptyError("orrery is empty");
                std::int32_t value = cells_[0].orbit;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].orbit = 0;
                --used_;
                return value;
            }
            std::size_t OrreryPlanetTracks::crank_burst(const std::vector<std::int32_t>& orbits) {
                std::size_t accepted = 0;
                for (std::int32_t orbit : orbits) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].orbit = orbit;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t OrreryPlanetTracks::skip_orbits(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].orbit = 0;
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int32_t> OrreryPlanetTracks::peek_orbit(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].orbit;
            }
            std::size_t OrreryPlanetTracks::home_track() const {
                if (used_ == 0) throw OrreryEmptyError("orrery is empty");
                return 0;
            }
            std::size_t OrreryPlanetTracks::track_at(std::size_t offset) const {
                if (used_ == 0) throw OrreryEmptyError("orrery is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued orbits");
                return offset;
            }
            """,
            """
            OrreryPlanetTracks orrery(3);
            orrery.crank(88);
            orrery.crank(225);
            if (orrery.release_orbit() != 88) return 1;
            if (orrery.crank_burst({365, 687}) != 2U) return 2;
            if (orrery.release_orbit() != 225) return 3;
            if (orrery.release_orbit() != 365) return 4;
            if (orrery.release_orbit() != 687) return 5;
            if (orrery.orbits() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { OrreryPlanetTracks zero(0); (void)zero; } catch (const OrreryConfigError&) { threw = true; }
            if (!threw) return 1;
            OrreryPlanetTracks orrery(3);
            threw = false;
            try { orrery.release_orbit(); } catch (const OrreryEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { orrery.home_track(); } catch (const OrreryEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (orrery.peek_orbit(0).has_value()) return 4;
            if (orrery.crank_burst({88, 225}) != 2U) return 5;
            if (orrery.release_orbit() != 88) return 6;
            if (orrery.crank_burst({365, 687, 4333}) != 2U) return 7;
            threw = false;
            try { orrery.crank(4333); } catch (const OrreryFullError&) { threw = true; }
            if (!threw) return 8;
            if (orrery.orbits() != 3U) return 9;
            if (orrery.home_track() != 1U) return 10;
            if (orrery.track_at(0) != 1U) return 11;
            if (orrery.track_at(1) != 2U) return 12;
            if (orrery.track_at(2) != 0U) return 13;
            if (!orrery.peek_orbit(0) || *orrery.peek_orbit(0) != 225) return 14;
            if (!orrery.peek_orbit(2) || *orrery.peek_orbit(2) != 687) return 15;
            if (orrery.peek_orbit(3).has_value()) return 16;
            threw = false;
            try { orrery.track_at(3); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 17;
            if (orrery.skip_orbits(1) != 1U) return 18;
            if (orrery.home_track() != 2U) return 19;
            if (orrery.orbits() != 2U) return 20;
            if (!orrery.peek_orbit(0) || *orrery.peek_orbit(0) != 365) return 21;
            if (!orrery.peek_orbit(1) || *orrery.peek_orbit(1) != 687) return 22;
            if (orrery.skip_orbits(9) != 2U) return 23;
            if (orrery.orbits() != 0U) return 24;
            return 0;
            """,
            "a fixed orrery of orbit tracks whose offset peeks, batch bursts, skips, and physical track arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_track and track_at values after bursts and skips that wrap the orrery, peek order, partial burst acceptance at capacity, full and empty channels, and zero-track rejection",
            "project-context orbit cursor/batch ring",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
            project_support=True,
        ),
        c(
            "f26cbuf-pendulum-swing-arcs",
            "Pendulum swing arcs",
            "pendulum",
            """
            class PendulumConfigError : public std::invalid_argument {
            public:
                explicit PendulumConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PendulumEmptyError : public std::runtime_error {
            public:
                explicit PendulumEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class PendulumFullError : public std::logic_error {
            public:
                explicit PendulumFullError(const std::string& message) : std::logic_error(message) {}
            };
            class PendulumSwingArcs {
            public:
                explicit PendulumSwingArcs(std::size_t detents);
                void swing(std::int64_t amplitude);
                std::int64_t rest();
                std::size_t swing_burst(const std::vector<std::int64_t>& amplitudes);
                std::size_t skip_swings(std::size_t count);
                std::optional<std::int64_t> peek_swing(std::size_t offset) const;
                std::size_t home_detent() const;
                std::size_t detent_at(std::size_t offset) const;
                std::size_t swings() const;
                std::size_t detents() const;
            };
            """,
            """
            class PendulumConfigError : public std::invalid_argument {
            public:
                explicit PendulumConfigError(const std::string& message) : std::invalid_argument(message) {}
            };
            class PendulumEmptyError : public std::runtime_error {
            public:
                explicit PendulumEmptyError(const std::string& message) : std::runtime_error(message) {}
            };
            class PendulumFullError : public std::logic_error {
            public:
                explicit PendulumFullError(const std::string& message) : std::logic_error(message) {}
            };
            class PendulumSwingArcs {
            public:
                explicit PendulumSwingArcs(std::size_t detents);
                void swing(std::int64_t amplitude);
                std::int64_t rest();
                std::size_t swing_burst(const std::vector<std::int64_t>& amplitudes);
                std::size_t skip_swings(std::size_t count);
                std::optional<std::int64_t> peek_swing(std::size_t offset) const;
                std::size_t home_detent() const;
                std::size_t detent_at(std::size_t offset) const;
                std::size_t swings() const;
                std::size_t detents() const;
            private:
                struct Cell {
                    bool occupied = false;
                    std::int64_t amplitude = 0;
                };
                std::vector<Cell> cells_;
                std::size_t oldest_ = 0;
                std::size_t next_ = 0;
                std::size_t used_ = 0;
            };
            """,
            """
            PendulumSwingArcs::PendulumSwingArcs(std::size_t detents) {
                if (detents == 0) throw PendulumConfigError("pendulum needs at least one detent");
                cells_ = std::vector<Cell>(detents);
            }
            std::size_t PendulumSwingArcs::detents() const { return cells_.size(); }
            std::size_t PendulumSwingArcs::swings() const { return used_; }
            void PendulumSwingArcs::swing(std::int64_t amplitude) {
                if (used_ == cells_.size()) throw PendulumFullError("pendulum is full");
                cells_[next_].occupied = true;
                cells_[next_].amplitude = amplitude;
                next_ = (next_ + 1) % cells_.size();
                ++used_;
            }
            std::int64_t PendulumSwingArcs::rest() {
                if (used_ == 0) throw PendulumEmptyError("pendulum is empty");
                std::int64_t value = cells_[oldest_].amplitude;
                cells_[oldest_].occupied = false;
                cells_[oldest_].amplitude = 0;
                oldest_ = (oldest_ + 1) % cells_.size();
                --used_;
                return value;
            }
            std::size_t PendulumSwingArcs::swing_burst(const std::vector<std::int64_t>& amplitudes) {
                std::size_t accepted = 0;
                for (std::int64_t amplitude : amplitudes) {
                    if (used_ == cells_.size()) break;
                    cells_[next_].occupied = true;
                    cells_[next_].amplitude = amplitude;
                    next_ = (next_ + 1) % cells_.size();
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t PendulumSwingArcs::skip_swings(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    cells_[oldest_].occupied = false;
                    cells_[oldest_].amplitude = 0;
                    oldest_ = (oldest_ + 1) % cells_.size();
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int64_t> PendulumSwingArcs::peek_swing(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[(oldest_ + offset) % cells_.size()].amplitude;
            }
            std::size_t PendulumSwingArcs::home_detent() const {
                if (used_ == 0) throw PendulumEmptyError("pendulum is empty");
                return oldest_;
            }
            std::size_t PendulumSwingArcs::detent_at(std::size_t offset) const {
                if (used_ == 0) throw PendulumEmptyError("pendulum is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued swings");
                return (oldest_ + offset) % cells_.size();
            }
            """,
            """
            PendulumSwingArcs::PendulumSwingArcs(std::size_t detents) {
                if (detents == 0) throw PendulumConfigError("pendulum needs at least one detent");
                cells_ = std::vector<Cell>(detents);
            }
            std::size_t PendulumSwingArcs::detents() const { return cells_.size(); }
            std::size_t PendulumSwingArcs::swings() const { return used_; }
            void PendulumSwingArcs::swing(std::int64_t amplitude) {
                if (used_ == cells_.size()) throw PendulumFullError("pendulum is full");
                cells_[used_].occupied = true;
                cells_[used_].amplitude = amplitude;
                ++used_;
            }
            std::int64_t PendulumSwingArcs::rest() {
                if (used_ == 0) throw PendulumEmptyError("pendulum is empty");
                std::int64_t value = cells_[0].amplitude;
                for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                cells_[used_ - 1].occupied = false;
                cells_[used_ - 1].amplitude = 0;
                --used_;
                return value;
            }
            std::size_t PendulumSwingArcs::swing_burst(const std::vector<std::int64_t>& amplitudes) {
                std::size_t accepted = 0;
                for (std::int64_t amplitude : amplitudes) {
                    if (used_ == cells_.size()) break;
                    cells_[used_].occupied = true;
                    cells_[used_].amplitude = amplitude;
                    ++used_;
                    ++accepted;
                }
                return accepted;
            }
            std::size_t PendulumSwingArcs::skip_swings(std::size_t count) {
                std::size_t freed = 0;
                while (freed < count && used_ > 0) {
                    for (std::size_t i = 1; i < used_; ++i) cells_[i - 1] = cells_[i];
                    cells_[used_ - 1].occupied = false;
                    cells_[used_ - 1].amplitude = 0;
                    --used_;
                    ++freed;
                }
                return freed;
            }
            std::optional<std::int64_t> PendulumSwingArcs::peek_swing(std::size_t offset) const {
                if (offset >= used_) return std::nullopt;
                return cells_[offset].amplitude;
            }
            std::size_t PendulumSwingArcs::home_detent() const {
                if (used_ == 0) throw PendulumEmptyError("pendulum is empty");
                return 0;
            }
            std::size_t PendulumSwingArcs::detent_at(std::size_t offset) const {
                if (used_ == 0) throw PendulumEmptyError("pendulum is empty");
                if (offset >= used_) throw std::out_of_range("offset beyond queued swings");
                return offset;
            }
            """,
            """
            PendulumSwingArcs arc(3);
            arc.swing(12);
            arc.swing(24);
            if (arc.rest() != 12) return 1;
            if (arc.swing_burst({36, 48}) != 2U) return 2;
            if (arc.rest() != 24) return 3;
            if (arc.rest() != 36) return 4;
            if (arc.rest() != 48) return 5;
            if (arc.swings() != 0U) return 6;
            return 0;
            """,
            """
            bool threw = false;
            try { PendulumSwingArcs zero(0); (void)zero; } catch (const PendulumConfigError&) { threw = true; }
            if (!threw) return 1;
            PendulumSwingArcs arc(4);
            threw = false;
            try { arc.rest(); } catch (const PendulumEmptyError&) { threw = true; }
            if (!threw) return 2;
            threw = false;
            try { arc.home_detent(); } catch (const PendulumEmptyError&) { threw = true; }
            if (!threw) return 3;
            if (arc.peek_swing(0).has_value()) return 4;
            if (arc.swing_burst({10, 20, 30}) != 3U) return 5;
            if (arc.rest() != 10) return 6;
            if (arc.swing_burst({40, 50, 60}) != 2U) return 7;
            threw = false;
            try { arc.swing(60); } catch (const PendulumFullError&) { threw = true; }
            if (!threw) return 8;
            if (arc.swings() != 4U) return 9;
            if (arc.home_detent() != 1U) return 10;
            if (arc.detent_at(0) != 1U) return 11;
            if (arc.detent_at(1) != 2U) return 12;
            if (arc.detent_at(2) != 3U) return 13;
            if (arc.detent_at(3) != 0U) return 14;
            if (!arc.peek_swing(0) || *arc.peek_swing(0) != 20) return 15;
            if (!arc.peek_swing(3) || *arc.peek_swing(3) != 50) return 16;
            if (arc.peek_swing(4).has_value()) return 17;
            threw = false;
            try { arc.detent_at(4); } catch (const std::out_of_range&) { threw = true; }
            if (!threw) return 18;
            if (arc.skip_swings(2) != 2U) return 19;
            if (arc.home_detent() != 3U) return 20;
            if (arc.swings() != 2U) return 21;
            if (!arc.peek_swing(0) || *arc.peek_swing(0) != 40) return 22;
            if (!arc.peek_swing(1) || *arc.peek_swing(1) != 50) return 23;
            if (arc.skip_swings(9) != 2U) return 24;
            if (arc.swings() != 0U) return 25;
            return 0;
            """,
            "a fixed arc of amplitude detents whose offset peeks, batch bursts, skips, and physical detent arithmetic stay observable across wraparound",
            "a std::queue, std::deque, std::list, or compacting std::vector as the core store",
            "physical home_detent and detent_at values after bursts and skips that wrap the arc, peek order, partial burst acceptance at capacity, full and empty channels, and zero-detent rejection",
            "project-context int64 cursor/batch ring",
            "cursor-navigation, batch, and wraparound-arithmetic bounded ring",
            project_support=True,
        ),
    )
    return rows


CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-cbuf-seven-dimension-artifacts-v1"
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

Implement a clean-room C++17 fixed-capacity ring-store component for a local
circular-buffer analog. This root is independently authored for SFT
task-family construction and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep cell ownership, wraparound cursor arithmetic, capacity policy,
layout-dependent slot observables, and journal or trace order deterministic and
explicit for this API shape: {spec.api_shape}.

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
                "source": "w8-biayn clean-room fixed26 circular-buffer analog curriculum",
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
description = "{spec.title}: physical slots, wraparound cursors, capacity and eviction policies, layout traces, and wrong-substitute rejection"

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
            "family": "circular-buffer",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "circular-buffer",
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
        "project_context_support_note": "The source spec names 15 project-context support roots; this materializer emits private support only for those 15.",
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
    text = re.sub(r"\bf26cbuf[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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
        "schema_version": "fixed26-cbuf-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-cbuf-fresh-") as temporary:
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
        "schema_version": "fixed26-cbuf-core-v1",
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
for task_root in sorted(ROOT.glob("f26cbuf-*")):
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
            "schema_version": "fixed26-cbuf-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-cbuf-docker-") as temporary:
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
        "schema_version": "fixed26-cbuf-docker-sanity-v1",
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
        "schema_version": "fixed26-cbuf-creator-preflight-v1",
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
        "capability": "fixed26-circular-buffer-analog",
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
            "task": "implement clean-room fixed26 circular-buffer analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "owned fixed-capacity cell ring with modular cursor arithmetic; explicit empty/full and eviction policies; layout-dependent slot observables; rejected operations never mutate; deterministic snapshots, journals, and traces",
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
            "target_family": "circular-buffer",
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
