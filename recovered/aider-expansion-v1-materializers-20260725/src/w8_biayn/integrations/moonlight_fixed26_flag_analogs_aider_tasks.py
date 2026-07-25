"""Create and verify the fixed-26 allergies clean-room analog batch.

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b002-allergies.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b002-allergies"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_flag_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_flag_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b002-allergies"
FAMILY_ID = "aider-fixed26-allergies-analogs-v1"
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
        "f26flg-conservatory-climate-zone",
        "f26flg-vineyard-canopy-practices",
        "f26flg-studio-recording-channels",
        "f26flg-orchestra-section-roster",
        "f26flg-greenhouse-vent-program",
        "f26flg-inventory-aisle-sensors",
        "f26flg-datacenter-rack-pdus",
        "f26flg-theater-stage-cues",
        "f26flg-pharmacy-compound-ingredients",
        "f26flg-pavilion-roof-panels",
        "f26flg-robotics-arm-joints",
        "f26flg-carpentry-shop-tools",
        "f26flg-api-gateway-features",
        "f26flg-brewery-batch-additives",
        "f26flg-mountain-hut-supplies",
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
#include <limits>
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

namespace f26flg_detail {
struct NameBit {
    const char* name;
    std::uint64_t bit;
};

[[maybe_unused]] bool valid_table(const NameBit* entries, std::size_t count) {
    if (entries == nullptr || count == 0) return false;
    std::uint64_t seen = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if (entries[i].name == nullptr || entries[i].name[0] == '\0') return false;
        std::uint64_t bit = entries[i].bit;
        if (bit == 0 || (bit & (bit - 1)) != 0) return false;
        if ((seen & bit) != 0) return false;
        seen |= bit;
        for (std::size_t j = 0; j < i; ++j) {
            if (std::string_view(entries[j].name) == entries[i].name) return false;
        }
    }
    return true;
}

[[maybe_unused]] std::uint64_t known_mask(const NameBit* entries, std::size_t count) {
    std::uint64_t mask = 0;
    for (std::size_t i = 0; i < count; ++i) mask |= entries[i].bit;
    return mask;
}

[[maybe_unused]] bool lookup_bit(const NameBit* entries, std::size_t count, std::string_view name, std::uint64_t& bit) {
    for (std::size_t i = 0; i < count; ++i) {
        if (name == entries[i].name) {
            bit = entries[i].bit;
            return true;
        }
    }
    return false;
}

[[maybe_unused]] std::string_view lookup_name(const NameBit* entries, std::size_t count, std::uint64_t bit) {
    for (std::size_t i = 0; i < count; ++i) {
        if (entries[i].bit == bit) return entries[i].name;
    }
    return {};
}

[[maybe_unused]] std::vector<std::string> ordered_names(const NameBit* entries, std::size_t count, std::uint64_t mask) {
    std::vector<std::string> out;
    for (std::size_t i = 0; i < count; ++i) {
        if ((mask & entries[i].bit) != 0) out.emplace_back(entries[i].name);
    }
    return out;
}

[[maybe_unused]] unsigned count_bits(std::uint64_t mask) {
    unsigned total = 0;
    while (mask != 0) {
        mask &= mask - 1;
        ++total;
    }
    return total;
}

[[maybe_unused]] std::vector<std::string_view> split_keep_empty(std::string_view text, char delim) {
    std::vector<std::string_view> tokens;
    std::size_t begin = 0;
    while (true) {
        std::size_t pos = text.find(delim, begin);
        if (pos == std::string_view::npos) {
            tokens.push_back(text.substr(begin));
            break;
        }
        tokens.push_back(text.substr(begin, pos - begin));
        begin = pos + 1;
    }
    return tokens;
}

[[maybe_unused]] std::string join_names(const std::vector<std::string>& names, std::string_view delim) {
    std::string out;
    for (std::size_t i = 0; i < names.size(); ++i) {
        if (i != 0) out.append(delim);
        out.append(names[i]);
    }
    return out;
}
}  // namespace f26flg_detail
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
            "f26flg-marina-signal-check",
            "Marina signal check",
            "marina_signals",
            """
            struct Finding {
                bool known;
                bool flying;
                std::uint32_t normalized_code;
            };
            Finding inspect(std::uint32_t code, std::string_view flag_name);
            """,
            """
            struct Finding {
                bool known;
                bool flying;
                std::uint32_t normalized_code;
            };
            Finding inspect(std::uint32_t code, std::string_view flag_name);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSignalFlags[] = {
                {"alpha", 1u}, {"bravo", 2u}, {"charlie", 4u}, {"delta", 8u},
                {"echo", 16u}, {"foxtrot", 32u}, {"golf", 64u}, {"hotel", 128u},
            };
            }  // namespace
            Finding inspect(std::uint32_t code, std::string_view flag_name) {
                const std::uint64_t known = f26flg_detail::known_mask(kSignalFlags, 8);
                const std::uint32_t normalized = static_cast<std::uint32_t>(code & known);
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSignalFlags, 8, flag_name, bit)) {
                    return {false, false, normalized};
                }
                return {true, (normalized & bit) != 0, normalized};
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSignalFlags[] = {
                {"alpha", 1u}, {"bravo", 2u}, {"charlie", 4u}, {"delta", 8u},
                {"echo", 16u}, {"foxtrot", 32u}, {"golf", 64u}, {"hotel", 128u},
            };
            }  // namespace
            Finding inspect(std::uint32_t code, std::string_view flag_name) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSignalFlags, 8, flag_name, bit)) {
                    return {false, false, code};
                }
                return {true, (code & bit) != 0, code};
            }
            """,
            """
            auto finding = inspect(0x85, "alpha");
            if (!finding.known || !finding.flying || finding.normalized_code != 0x85) return 1;
            auto missing = inspect(0x85, "bravo");
            if (!missing.known || missing.flying) return 2;
            return 0;
            """,
            """
            if (inspect(0x1A5, "alpha").normalized_code != 0xA5) return 1;
            if (!inspect(0x1A5, "alpha").flying) return 2;
            if (inspect(0x100, "alpha").flying) return 3;
            if (inspect(0x00, "zulu").known) return 4;
            if (!inspect(0xFF, "hotel").flying) return 5;
            if (inspect(0x80, "hotel").normalized_code != 0x80) return 6;
            return 0;
            """,
            "membership checked against a normalized signal mask so unknown code bits never fabricate a flying flag",
            "raw-code membership tests, foreign bits treated as flags, or hash-ordered name lookups",
            "foreign high bits dropped from the normalized report, unknown flag names, zero code, and full-mask queries",
            "membership-query discipline over a named eight-flag table in a two-file API",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26flg-rocket-preflight-gates",
            "Rocket preflight gates",
            "rocket_gates",
            """
            class GateError : public std::domain_error {
            public:
                explicit GateError(const std::string& message) : std::domain_error(message) {}
            };
            class Preflight {
            public:
                explicit Preflight(std::uint32_t ready_mask);
                bool cleared(std::string_view gate) const;
                std::uint32_t ready() const;
            };
            """,
            """
            class GateError : public std::domain_error {
            public:
                explicit GateError(const std::string& message) : std::domain_error(message) {}
            };
            class Preflight {
            public:
                explicit Preflight(std::uint32_t ready_mask);
                bool cleared(std::string_view gate) const;
                std::uint32_t ready() const;
            private:
                std::uint32_t ready_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kGates[] = {
                {"fuel", 1u}, {"oxidizer", 2u}, {"guidance", 4u},
                {"telemetry", 8u}, {"recovery", 16u}, {"payload", 32u},
            };
            }  // namespace
            Preflight::Preflight(std::uint32_t ready_mask)
                : ready_(static_cast<std::uint32_t>(ready_mask & f26flg_detail::known_mask(kGates, 6))) {}
            bool Preflight::cleared(std::string_view gate) const {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kGates, 6, gate, bit)) {
                    throw GateError("unknown preflight gate");
                }
                return (ready_ & bit) != 0;
            }
            std::uint32_t Preflight::ready() const { return ready_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kGates[] = {
                {"fuel", 1u}, {"oxidizer", 2u}, {"guidance", 4u},
                {"telemetry", 8u}, {"recovery", 16u}, {"payload", 32u},
            };
            }  // namespace
            Preflight::Preflight(std::uint32_t ready_mask) : ready_(ready_mask) {}
            bool Preflight::cleared(std::string_view gate) const {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kGates, 6, gate, bit)) return false;
                return (ready_ & bit) != 0;
            }
            std::uint32_t Preflight::ready() const { return ready_; }
            """,
            """
            Preflight board(0x0D);
            if (!board.cleared("fuel") || board.cleared("oxidizer")) return 1;
            if (board.ready() != 0x0D) return 2;
            return 0;
            """,
            """
            Preflight board(0xFFFF);
            if (board.ready() != 0x3F) return 1;
            bool threw = false;
            try {
                (void)board.cleared("engines");
            } catch (const GateError&) {
                threw = true;
            }
            if (!threw) return 2;
            if (!board.cleared("payload")) return 3;
            Preflight empty(0x40);
            if (empty.ready() != 0) return 4;
            return 0;
            """,
            "constructor-time mask normalization with a typed exception for unknown gate names",
            "storing the raw mask or answering false for unknown gates instead of throwing",
            "constructor masking of wide masks, exact GateError type, foreign-only constructor masks, and boundary gates",
            "exact exception behavior plus constructor boundary normalization",
            "exception-throwing policy object or service class",
        ),
        c(
            "f26flg-warehouse-picker-slots",
            "Warehouse picker slots",
            "warehouse_slots",
            """
            class SlotBoard {
            public:
                SlotBoard() = default;
                bool enable(std::string_view slot);
                bool disable(std::string_view slot);
                bool active(std::string_view slot) const;
                std::uint32_t mask() const;
                void reset();
            };
            """,
            """
            class SlotBoard {
            public:
                SlotBoard() = default;
                bool enable(std::string_view slot);
                bool disable(std::string_view slot);
                bool active(std::string_view slot) const;
                std::uint32_t mask() const;
                void reset();
            private:
                std::uint32_t mask_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSlots[] = {
                {"receiving", 1u}, {"storage", 2u}, {"picking", 4u}, {"packing", 8u},
                {"shipping", 16u}, {"returns", 32u}, {"quarantine", 64u}, {"overflow", 128u},
                {"cold", 256u}, {"hazmat", 512u},
            };
            }  // namespace
            bool SlotBoard::enable(std::string_view slot) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSlots, 10, slot, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool SlotBoard::disable(std::string_view slot) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSlots, 10, slot, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            bool SlotBoard::active(std::string_view slot) const {
                std::uint64_t bit = 0;
                return f26flg_detail::lookup_bit(kSlots, 10, slot, bit) && (mask_ & bit) != 0;
            }
            std::uint32_t SlotBoard::mask() const { return mask_; }
            void SlotBoard::reset() { mask_ = 0; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSlots[] = {
                {"receiving", 1u}, {"storage", 2u}, {"picking", 4u}, {"packing", 8u},
                {"shipping", 16u}, {"returns", 32u}, {"quarantine", 64u}, {"overflow", 128u},
                {"cold", 256u}, {"hazmat", 512u},
            };
            }  // namespace
            bool SlotBoard::enable(std::string_view slot) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSlots, 10, slot, bit)) {
                    mask_ |= 0x8000u;
                    return true;
                }
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool SlotBoard::disable(std::string_view slot) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSlots, 10, slot, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            bool SlotBoard::active(std::string_view slot) const {
                std::uint64_t bit = 0;
                return f26flg_detail::lookup_bit(kSlots, 10, slot, bit) && (mask_ & bit) != 0;
            }
            std::uint32_t SlotBoard::mask() const { return mask_; }
            void SlotBoard::reset() { mask_ = 0; }
            """,
            """
            SlotBoard board;
            if (!board.enable("picking") || !board.enable("shipping")) return 1;
            if (!board.active("picking") || board.active("cold")) return 2;
            if (board.mask() != 0x14) return 3;
            board.reset();
            if (board.mask() != 0 || board.active("picking")) return 4;
            return 0;
            """,
            """
            SlotBoard board;
            if (board.enable("mezzanine")) return 1;
            if (board.mask() != 0) return 2;
            if (board.disable("mezzanine")) return 3;
            if (!board.enable("hazmat") || !board.enable("receiving")) return 4;
            if (board.mask() != 0x201) return 5;
            if (!board.disable("receiving") || board.active("receiving")) return 6;
            if (board.active("mezzanine")) return 7;
            if (board.mask() != 0x200) return 8;
            return 0;
            """,
            "name-validated set and clear operations over one owned mask with reset semantics",
            "hashing unknown slot names into foreign bits or accepting them as success",
            "unknown enable and disable names, mask stability after rejections, boundary slots, and reset",
            "stateful mutation atomicity for unknown-name handling",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-conservatory-climate-zone",
            "Conservatory climate zone",
            "conservatory_climate",
            """
            class ZoneBoard {
            public:
                static std::optional<ZoneBoard> create(const std::vector<std::pair<std::string, std::uint32_t>>& zones);
                std::optional<bool> humidifying(std::string_view zone, std::uint32_t active_mask) const;
                std::uint32_t known() const;
            };
            """,
            """
            class ZoneBoard {
            public:
                static std::optional<ZoneBoard> create(const std::vector<std::pair<std::string, std::uint32_t>>& zones);
                std::optional<bool> humidifying(std::string_view zone, std::uint32_t active_mask) const;
                std::uint32_t known() const;
            private:
                ZoneBoard(std::vector<std::pair<std::string, std::uint32_t>> zones, std::uint32_t known);
                std::vector<std::pair<std::string, std::uint32_t>> zones_;
                std::uint32_t known_;
            };
            """,
            """
            std::optional<ZoneBoard> ZoneBoard::create(const std::vector<std::pair<std::string, std::uint32_t>>& zones) {
                if (zones.empty() || zones.size() > 16) return std::nullopt;
                std::uint64_t seen = 0;
                for (std::size_t i = 0; i < zones.size(); ++i) {
                    const std::uint32_t bit = zones[i].second;
                    if (zones[i].first.empty() || bit == 0 || (bit & (bit - 1)) != 0 || bit > 0x8000u) return std::nullopt;
                    if ((seen & bit) != 0) return std::nullopt;
                    seen |= bit;
                    for (std::size_t j = 0; j < i; ++j) {
                        if (zones[j].first == zones[i].first) return std::nullopt;
                    }
                }
                return ZoneBoard(zones, static_cast<std::uint32_t>(seen));
            }
            ZoneBoard::ZoneBoard(std::vector<std::pair<std::string, std::uint32_t>> zones, std::uint32_t known)
                : zones_(std::move(zones)), known_(known) {}
            std::optional<bool> ZoneBoard::humidifying(std::string_view zone, std::uint32_t active_mask) const {
                for (const auto& entry : zones_) {
                    if (entry.first == zone) return (active_mask & known_ & entry.second) != 0;
                }
                return std::nullopt;
            }
            std::uint32_t ZoneBoard::known() const { return known_; }
            """,
            """
            std::optional<ZoneBoard> ZoneBoard::create(const std::vector<std::pair<std::string, std::uint32_t>>& zones) {
                if (zones.empty() || zones.size() > 16) return std::nullopt;
                std::uint64_t seen = 0;
                for (std::size_t i = 0; i < zones.size(); ++i) {
                    const std::uint32_t bit = zones[i].second;
                    if (zones[i].first.empty() || bit == 0 || (bit & (bit - 1)) != 0 || bit > 0x8000u) return std::nullopt;
                    seen |= bit;
                    for (std::size_t j = 0; j < i; ++j) {
                        if (zones[j].first == zones[i].first) return std::nullopt;
                    }
                }
                return ZoneBoard(zones, static_cast<std::uint32_t>(seen));
            }
            ZoneBoard::ZoneBoard(std::vector<std::pair<std::string, std::uint32_t>> zones, std::uint32_t known)
                : zones_(std::move(zones)), known_(known) {}
            std::optional<bool> ZoneBoard::humidifying(std::string_view zone, std::uint32_t active_mask) const {
                for (const auto& entry : zones_) {
                    if (entry.first == zone) return (active_mask & known_ & entry.second) != 0;
                }
                return std::nullopt;
            }
            std::uint32_t ZoneBoard::known() const { return known_; }
            """,
            """
            auto board = ZoneBoard::create({{"fern_house", 1}, {"palm_court", 2}, {"orchid_room", 4}, {"cactus_bay", 8}});
            if (!board) return 1;
            auto state = board->humidifying("palm_court", 0x0A);
            if (!state || !*state) return 2;
            if (board->known() != 0x0F) return 3;
            return 0;
            """,
            """
            if (ZoneBoard::create({{"fern_house", 1}, {"palm_court", 1}})) return 1;
            if (ZoneBoard::create({{"fern_house", 3}})) return 2;
            if (ZoneBoard::create({{"fern_house", 1}, {"fern_house", 2}})) return 3;
            if (ZoneBoard::create({})) return 4;
            if (ZoneBoard::create({{"roof", 0x10000u}})) return 5;
            auto board = ZoneBoard::create({{"fern_house", 1}, {"palm_court", 2}});
            if (!board) return 6;
            if (board->humidifying("desert_wing", 0xFF)) return 7;
            auto off = board->humidifying("fern_house", 0x10);
            if (!off || *off) return 8;
            return 0;
            """,
            "one-time injected table validation with an optional membership answer against the known mask",
            "accepting duplicate bits with last-write-wins or skipping table validation",
            "duplicate bits, duplicate names, non-power-of-two bits, oversized bits, empty tables, unknown zones, and foreign active bits",
            "runtime-injected flag-table validation absent from single-file rows",
            "injected flag-table/policy object",
            project_support=True,
        ),
        c(
            "f26flg-observatory-filter-wheel",
            "Observatory filter wheel",
            "observatory_filters",
            """
            class FilterSet {
            public:
                static FilterSet of(std::uint32_t bits);
                static FilterSet named(std::string_view filter);
                bool has(FilterSet other) const;
                bool empty() const;
                FilterSet operator|(FilterSet other) const;
                FilterSet operator&(FilterSet other) const;
                std::uint32_t bits() const;
                friend bool operator==(FilterSet left, FilterSet right) { return left.bits_ == right.bits_; }
                friend bool operator!=(FilterSet left, FilterSet right) { return !(left == right); }
            };
            """,
            """
            class FilterSet {
            public:
                static FilterSet of(std::uint32_t bits);
                static FilterSet named(std::string_view filter);
                bool has(FilterSet other) const;
                bool empty() const;
                FilterSet operator|(FilterSet other) const;
                FilterSet operator&(FilterSet other) const;
                std::uint32_t bits() const;
                friend bool operator==(FilterSet left, FilterSet right) { return left.bits_ == right.bits_; }
                friend bool operator!=(FilterSet left, FilterSet right) { return !(left == right); }
            private:
                explicit FilterSet(std::uint32_t bits);
                std::uint32_t bits_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kFilters[] = {
                {"luminance", 1u}, {"red", 2u}, {"green", 4u}, {"blue", 8u},
                {"hydrogen", 16u}, {"oxygen", 32u}, {"sulfur", 64u},
            };
            }  // namespace
            FilterSet::FilterSet(std::uint32_t bits) : bits_(bits & 0x7Fu) {}
            FilterSet FilterSet::of(std::uint32_t bits) { return FilterSet(bits); }
            FilterSet FilterSet::named(std::string_view filter) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kFilters, 7, filter, bit)) return FilterSet(0);
                return FilterSet(static_cast<std::uint32_t>(bit));
            }
            bool FilterSet::has(FilterSet other) const { return (bits_ & other.bits_) == other.bits_; }
            bool FilterSet::empty() const { return bits_ == 0; }
            FilterSet FilterSet::operator|(FilterSet other) const { return FilterSet(bits_ | other.bits_); }
            FilterSet FilterSet::operator&(FilterSet other) const { return FilterSet(bits_ & other.bits_); }
            std::uint32_t FilterSet::bits() const { return bits_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kFilters[] = {
                {"luminance", 1u}, {"red", 2u}, {"green", 4u}, {"blue", 8u},
                {"hydrogen", 16u}, {"oxygen", 32u}, {"sulfur", 64u},
            };
            }  // namespace
            FilterSet::FilterSet(std::uint32_t bits) : bits_(bits) {}
            FilterSet FilterSet::of(std::uint32_t bits) { return FilterSet(bits); }
            FilterSet FilterSet::named(std::string_view filter) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kFilters, 7, filter, bit)) return FilterSet(0);
                return FilterSet(static_cast<std::uint32_t>(bit));
            }
            bool FilterSet::has(FilterSet other) const { return (bits_ & other.bits_) == other.bits_; }
            bool FilterSet::empty() const { return bits_ == 0; }
            FilterSet FilterSet::operator|(FilterSet other) const { return FilterSet(bits_ | other.bits_); }
            FilterSet FilterSet::operator&(FilterSet other) const { return FilterSet(bits_ & other.bits_); }
            std::uint32_t FilterSet::bits() const { return bits_; }
            """,
            """
            auto wide = FilterSet::named("red") | FilterSet::named("blue");
            if (!wide.has(FilterSet::named("red"))) return 1;
            if (wide.bits() != 0x0A) return 2;
            if ((wide & FilterSet::named("blue")).bits() != 0x08) return 3;
            return 0;
            """,
            """
            if (!(FilterSet::of(0xFF) == FilterSet::of(0x7F))) return 1;
            if (!FilterSet::named("ultraviolet").empty()) return 2;
            if ((FilterSet::of(0x01) | FilterSet::of(0x80)).bits() != 0x01) return 3;
            if (FilterSet::named("sulfur").bits() != 0x40) return 4;
            if (FilterSet::of(0).has(FilterSet::named("red"))) return 5;
            if (FilterSet::of(0x80).bits() != 0) return 6;
            return 0;
            """,
            "normalizing value semantics with union, intersection, and a name lookup yielding the empty set",
            "storing unnormalized bits or comparing raw masks",
            "foreign-bit construction equality, unknown filter names, union with foreign bits, and empty-set membership",
            "operator discipline and value equality over normalized masks",
            "value type with operator==, operator<, arithmetic, or formatting helpers",
        ),
        c(
            "f26flg-bakery-order-extras",
            "Bakery order extras",
            "bakery_extras",
            """
            enum class Extra : std::uint32_t {
                sprinkles = 1u,
                glaze = 2u,
                filling = 4u,
                frosting = 8u,
                nuts = 16u,
                fruit = 32u,
                chips = 64u,
                caramel = 128u,
                fluff = 256u,
            };
            struct Ticket {
                bool included;
                std::uint32_t normalized;
                std::size_t total_count;
            };
            Ticket audit(std::uint32_t code, Extra extra);
            """,
            """
            enum class Extra : std::uint32_t {
                sprinkles = 1u,
                glaze = 2u,
                filling = 4u,
                frosting = 8u,
                nuts = 16u,
                fruit = 32u,
                chips = 64u,
                caramel = 128u,
                fluff = 256u,
            };
            struct Ticket {
                bool included;
                std::uint32_t normalized;
                std::size_t total_count;
            };
            Ticket audit(std::uint32_t code, Extra extra);
            """,
            """
            Ticket audit(std::uint32_t code, Extra extra) {
                const std::uint32_t normalized = code & 0x1FFu;
                const std::uint32_t bit = static_cast<std::uint32_t>(extra);
                return {(normalized & bit) != 0, normalized, f26flg_detail::count_bits(normalized)};
            }
            """,
            """
            Ticket audit(std::uint32_t code, Extra extra) {
                const std::uint32_t bit = static_cast<std::uint32_t>(extra);
                return {(code & bit) != 0, code & 0x1FFu, f26flg_detail::count_bits(code)};
            }
            """,
            """
            auto ticket = audit(0x05, Extra::sprinkles);
            if (!ticket.included || ticket.normalized != 0x05 || ticket.total_count != 2) return 1;
            if (audit(0x05, Extra::glaze).included) return 2;
            return 0;
            """,
            """
            auto rich = audit(0x3FF, Extra::fluff);
            if (rich.normalized != 0x1FF || rich.total_count != 9) return 1;
            if (!rich.included) return 2;
            if (audit(0x200, Extra::sprinkles).included) return 3;
            if (audit(0, Extra::caramel).total_count != 0) return 4;
            if (!audit(0x180, Extra::caramel).included) return 5;
            return 0;
            """,
            "enum-keyed membership with normalized popcount reporting",
            "counting foreign bits toward the order or testing membership on raw codes",
            "a ten-bit raw code, foreign-only codes, zero code, and boundary extras",
            "enum-class flag parameters and exact audit-struct output",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26flg-aquarium-life-support",
            "Aquarium life support",
            "aquarium_support",
            """
            class Monitor {
            public:
                bool push_failure(std::string_view system);
                std::optional<bool> failed(std::string_view system) const;
                std::uint32_t failed_mask() const;
                void clear();
            };
            """,
            """
            class Monitor {
            public:
                bool push_failure(std::string_view system);
                std::optional<bool> failed(std::string_view system) const;
                std::uint32_t failed_mask() const;
                void clear();
            private:
                std::uint32_t failures_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSystems[] = {
                {"filtration", 1u}, {"aeration", 2u}, {"heating", 4u},
                {"lighting", 8u}, {"skimmer", 16u}, {"uv", 32u},
            };
            }  // namespace
            bool Monitor::push_failure(std::string_view system) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSystems, 6, system, bit)) return false;
                failures_ = static_cast<std::uint32_t>(failures_ | bit);
                return true;
            }
            std::optional<bool> Monitor::failed(std::string_view system) const {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSystems, 6, system, bit)) return std::nullopt;
                return (failures_ & bit) != 0;
            }
            std::uint32_t Monitor::failed_mask() const { return failures_; }
            void Monitor::clear() { failures_ = 0; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSystems[] = {
                {"filtration", 1u}, {"aeration", 2u}, {"heating", 4u},
                {"lighting", 8u}, {"skimmer", 16u}, {"uv", 32u},
            };
            }  // namespace
            bool Monitor::push_failure(std::string_view system) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSystems, 6, system, bit)) return false;
                failures_ = static_cast<std::uint32_t>(failures_ | bit);
                return true;
            }
            std::optional<bool> Monitor::failed(std::string_view system) const {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSystems, 6, system, bit)) return false;
                return (failures_ & bit) != 0;
            }
            std::uint32_t Monitor::failed_mask() const { return failures_; }
            void Monitor::clear() { failures_ = 0; }
            """,
            """
            Monitor monitor;
            if (!monitor.push_failure("heating") || !monitor.push_failure("uv")) return 1;
            auto heating = monitor.failed("heating");
            if (!heating || !*heating) return 2;
            if (monitor.failed_mask() != 0x24) return 3;
            monitor.clear();
            if (monitor.failed_mask() != 0) return 4;
            return 0;
            """,
            """
            Monitor monitor;
            if (monitor.push_failure("wavemaker")) return 1;
            if (monitor.failed_mask() != 0) return 2;
            if (monitor.failed("wavemaker") != std::nullopt) return 3;
            if (!monitor.push_failure("aeration")) return 4;
            auto aeration = monitor.failed("aeration");
            if (!aeration || !*aeration) return 5;
            auto lighting = monitor.failed("lighting");
            if (!lighting || *lighting) return 6;
            monitor.clear();
            auto after = monitor.failed("aeration");
            if (!after || *after) return 7;
            return 0;
            """,
            "push-based failure accumulation with three-state optional membership reporting",
            "conflating unknown systems with not-failed systems",
            "unknown push names, known and unknown failed queries, boundary systems, and clear",
            "optional-valued membership queries in a streaming shape",
            "streaming accumulator, iterator, or incremental writer",
        ),
        c(
            "f26flg-printshop-press-modes",
            "Printshop press modes",
            "press_modes",
            """
            class ModeError : public std::invalid_argument {
            public:
                explicit ModeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class Press {
            public:
                static std::uint32_t resolve(const std::vector<std::string>& requested);
                static bool included(std::uint32_t modes, std::string_view mode);
            };
            """,
            """
            class ModeError : public std::invalid_argument {
            public:
                explicit ModeError(const std::string& message) : std::invalid_argument(message) {}
            };
            class Press {
            public:
                static std::uint32_t resolve(const std::vector<std::string>& requested);
                static bool included(std::uint32_t modes, std::string_view mode);
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kModes[] = {
                {"duplex", 1u}, {"collate", 2u}, {"staple", 4u},
                {"hole_punch", 8u}, {"booklet", 16u},
            };
            }  // namespace
            std::uint32_t Press::resolve(const std::vector<std::string>& requested) {
                std::uint32_t modes = 0;
                for (const std::string& name : requested) {
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kModes, 5, name, bit)) throw ModeError("unknown press mode");
                    modes = static_cast<std::uint32_t>(modes | bit);
                }
                return modes;
            }
            bool Press::included(std::uint32_t modes, std::string_view mode) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModes, 5, mode, bit)) throw ModeError("unknown press mode");
                const std::uint32_t known = static_cast<std::uint32_t>(f26flg_detail::known_mask(kModes, 5));
                return (modes & known & bit) != 0;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kModes[] = {
                {"duplex", 1u}, {"collate", 2u}, {"staple", 4u},
                {"hole_punch", 8u}, {"booklet", 16u},
            };
            }  // namespace
            std::uint32_t Press::resolve(const std::vector<std::string>& requested) {
                std::uint32_t modes = 0;
                for (const std::string& name : requested) {
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kModes, 5, name, bit)) continue;
                    modes = static_cast<std::uint32_t>(modes | bit);
                }
                return modes;
            }
            bool Press::included(std::uint32_t modes, std::string_view mode) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModes, 5, mode, bit)) throw ModeError("unknown press mode");
                const std::uint32_t known = static_cast<std::uint32_t>(f26flg_detail::known_mask(kModes, 5));
                return (modes & known & bit) != 0;
            }
            """,
            """
            if (Press::resolve({"duplex", "staple"}) != 0x05) return 1;
            if (!Press::included(0x05, "duplex") || Press::included(0x05, "collate")) return 2;
            if (Press::resolve({}) != 0) return 3;
            return 0;
            """,
            """
            bool threw = false;
            try {
                (void)Press::resolve({"duplex", "laminating"});
            } catch (const ModeError&) {
                threw = true;
            }
            if (!threw) return 1;
            threw = false;
            try {
                (void)Press::included(0x1F, "laminating");
            } catch (const ModeError&) {
                threw = true;
            }
            if (!threw) return 2;
            if (!Press::included(0x1F, "booklet")) return 3;
            if (Press::included(0x20, "duplex")) return 4;
            if (Press::resolve({"booklet", "duplex", "booklet"}) != 0x11) return 5;
            return 0;
            """,
            "name-list resolution with typed failure and normalized membership checks",
            "silently skipping unknown mode names during resolution",
            "throws for unknown names in both APIs, idempotent duplicates, empty lists, and foreign membership bits",
            "exact exception discipline for list-to-mask conversion",
            "exception-throwing policy object or service class",
        ),
        c(
            "f26flg-vineyard-canopy-practices",
            "Vineyard canopy practices",
            "canopy_practices",
            """
            struct PracticePolicy {
                std::uint32_t allowed_mask;
            };
            class Ledger {
            public:
                explicit Ledger(PracticePolicy policy);
                bool permit(std::string_view practice);
                bool permitted(std::string_view practice) const;
                std::uint32_t permitted_mask() const;
            };
            """,
            """
            struct PracticePolicy {
                std::uint32_t allowed_mask;
            };
            class Ledger {
            public:
                explicit Ledger(PracticePolicy policy);
                bool permit(std::string_view practice);
                bool permitted(std::string_view practice) const;
                std::uint32_t permitted_mask() const;
            private:
                std::uint32_t allowed_;
                std::uint32_t recorded_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kPractices[] = {
                {"pruning", 1u}, {"leafing", 2u}, {"hedging", 4u}, {"netting", 8u},
                {"irrigation", 16u}, {"mowing", 32u}, {"spraying", 64u}, {"harvesting", 128u},
            };
            }  // namespace
            Ledger::Ledger(PracticePolicy policy)
                : allowed_(static_cast<std::uint32_t>(policy.allowed_mask & f26flg_detail::known_mask(kPractices, 8))) {}
            bool Ledger::permit(std::string_view practice) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kPractices, 8, practice, bit)) return false;
                if ((allowed_ & bit) == 0) return false;
                recorded_ = static_cast<std::uint32_t>(recorded_ | bit);
                return true;
            }
            bool Ledger::permitted(std::string_view practice) const {
                std::uint64_t bit = 0;
                return f26flg_detail::lookup_bit(kPractices, 8, practice, bit) && (recorded_ & bit) != 0;
            }
            std::uint32_t Ledger::permitted_mask() const { return recorded_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kPractices[] = {
                {"pruning", 1u}, {"leafing", 2u}, {"hedging", 4u}, {"netting", 8u},
                {"irrigation", 16u}, {"mowing", 32u}, {"spraying", 64u}, {"harvesting", 128u},
            };
            }  // namespace
            Ledger::Ledger(PracticePolicy policy)
                : allowed_(static_cast<std::uint32_t>(policy.allowed_mask & f26flg_detail::known_mask(kPractices, 8))) {}
            bool Ledger::permit(std::string_view practice) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kPractices, 8, practice, bit)) return false;
                recorded_ = static_cast<std::uint32_t>(recorded_ | bit);
                return true;
            }
            bool Ledger::permitted(std::string_view practice) const {
                std::uint64_t bit = 0;
                return f26flg_detail::lookup_bit(kPractices, 8, practice, bit) && (recorded_ & bit) != 0;
            }
            std::uint32_t Ledger::permitted_mask() const { return recorded_; }
            """,
            """
            Ledger ledger({0x09});
            if (!ledger.permit("pruning") || !ledger.permit("netting")) return 1;
            if (ledger.permit("hedging")) return 2;
            if (ledger.permitted_mask() != 0x09) return 3;
            return 0;
            """,
            """
            Ledger ledger({0x09});
            if (ledger.permit("hedging")) return 1;
            if (ledger.permit("drones")) return 2;
            if (ledger.permitted_mask() != 0) return 3;
            if (!ledger.permit("pruning")) return 4;
            if (!ledger.permitted("pruning") || ledger.permitted("leafing")) return 5;
            Ledger wide({0x1FF});
            if (wide.permit("drones")) return 6;
            if (!wide.permit("spraying")) return 7;
            if (wide.permitted_mask() != 0x40) return 8;
            return 0;
            """,
            "policy-gated recording with constructor normalization of the allowed mask",
            "recording any known practice regardless of the injected policy",
            "disallowed known practices, unknown names, policies with foreign bits, and mask stability",
            "policy-gated membership and mutation rules",
            "injected flag-table/policy object",
            project_support=True,
        ),
        c(
            "f26flg-planetarium-show-segments",
            "Planetarium show segments",
            "show_segments",
            """
            class SegmentSet {
            public:
                static SegmentSet from_bits(std::uint32_t bits);
                bool contains(std::string_view segment) const;
                std::string label() const;
                std::uint32_t bits() const;
                friend bool operator==(const SegmentSet& left, const SegmentSet& right) { return left.bits_ == right.bits_; }
                friend bool operator<(const SegmentSet& left, const SegmentSet& right) { return left.bits_ < right.bits_; }
            };
            """,
            """
            class SegmentSet {
            public:
                static SegmentSet from_bits(std::uint32_t bits);
                bool contains(std::string_view segment) const;
                std::string label() const;
                std::uint32_t bits() const;
                friend bool operator==(const SegmentSet& left, const SegmentSet& right) { return left.bits_ == right.bits_; }
                friend bool operator<(const SegmentSet& left, const SegmentSet& right) { return left.bits_ < right.bits_; }
            private:
                explicit SegmentSet(std::uint32_t bits);
                std::uint32_t bits_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSegments[] = {
                {"stars", 1u}, {"planets", 2u}, {"constellations", 4u}, {"galaxies", 8u},
                {"aurora", 16u}, {"comets", 32u}, {"meteors", 64u},
            };
            }  // namespace
            SegmentSet::SegmentSet(std::uint32_t bits) : bits_(bits & 0x7Fu) {}
            SegmentSet SegmentSet::from_bits(std::uint32_t bits) { return SegmentSet(bits); }
            bool SegmentSet::contains(std::string_view segment) const {
                std::uint64_t bit = 0;
                return f26flg_detail::lookup_bit(kSegments, 7, segment, bit) && (bits_ & bit) != 0;
            }
            std::string SegmentSet::label() const {
                auto names = f26flg_detail::ordered_names(kSegments, 7, bits_);
                if (names.empty()) return "none";
                return f26flg_detail::join_names(names, "+");
            }
            std::uint32_t SegmentSet::bits() const { return bits_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSegments[] = {
                {"stars", 1u}, {"planets", 2u}, {"constellations", 4u}, {"galaxies", 8u},
                {"aurora", 16u}, {"comets", 32u}, {"meteors", 64u},
            };
            }  // namespace
            SegmentSet::SegmentSet(std::uint32_t bits) : bits_(bits & 0x7Fu) {}
            SegmentSet SegmentSet::from_bits(std::uint32_t bits) { return SegmentSet(bits); }
            bool SegmentSet::contains(std::string_view segment) const {
                return label().find(segment) != std::string::npos;
            }
            std::string SegmentSet::label() const {
                auto names = f26flg_detail::ordered_names(kSegments, 7, bits_);
                return f26flg_detail::join_names(names, "+");
            }
            std::uint32_t SegmentSet::bits() const { return bits_; }
            """,
            """
            auto show = SegmentSet::from_bits(0x09);
            if (!show.contains("stars") || !show.contains("galaxies")) return 1;
            if (show.contains("aurora")) return 2;
            if (show.label() != "stars+galaxies") return 3;
            return 0;
            """,
            """
            if (SegmentSet::from_bits(0).label() != "none") return 1;
            if (SegmentSet::from_bits(0x80).label() != "none") return 2;
            if (SegmentSet::from_bits(0x09).contains("star")) return 3;
            if (SegmentSet::from_bits(0xFF).bits() != 0x7F) return 4;
            if (SegmentSet::from_bits(0x41).label() != "stars+meteors") return 5;
            if (!(SegmentSet::from_bits(0x02) < SegmentSet::from_bits(0x40))) return 6;
            if (SegmentSet::from_bits(0x22).contains("planet")) return 7;
            return 0;
            """,
            "normalized storage with exact-name membership and deterministic label formatting",
            "substring matching over the formatted label or dropping the empty-label default",
            "empty and foreign-only labels, prefix decoy names, normalized ordering, and exact joins",
            "exact string output and name-matching discipline",
            "value type with operator==, operator<, arithmetic, or formatting helpers",
        ),
        c(
            "f26flg-ferry-route-amenities",
            "Ferry route amenities",
            "ferry_amenities",
            """
            struct Listing {
                std::vector<std::string> available;
                std::uint32_t dropped_bits;
            };
            Listing catalog(std::uint32_t code);
            """,
            """
            struct Listing {
                std::vector<std::string> available;
                std::uint32_t dropped_bits;
            };
            Listing catalog(std::uint32_t code);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kAmenities[] = {
                {"restroom", 1u}, {"cafeteria", 2u}, {"wifi", 4u}, {"seating", 8u},
                {"deck", 16u}, {"cabin", 32u}, {"kiosk", 64u}, {"lounge", 128u},
            };
            }  // namespace
            Listing catalog(std::uint32_t code) {
                const std::uint64_t known = f26flg_detail::known_mask(kAmenities, 8);
                return {f26flg_detail::ordered_names(kAmenities, 8, code & known),
                        static_cast<std::uint32_t>(code & ~known)};
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kAmenities[] = {
                {"restroom", 1u}, {"cafeteria", 2u}, {"wifi", 4u}, {"seating", 8u},
                {"deck", 16u}, {"cabin", 32u}, {"kiosk", 64u}, {"lounge", 128u},
            };
            }  // namespace
            Listing catalog(std::uint32_t code) {
                const std::uint64_t known = f26flg_detail::known_mask(kAmenities, 8);
                return {f26flg_detail::ordered_names(kAmenities, 8, code & known), 0u};
            }
            """,
            """
            auto listing = catalog(0x05);
            if (listing.available != std::vector<std::string>({"restroom", "wifi"})) return 1;
            if (listing.dropped_bits != 0) return 2;
            return 0;
            """,
            """
            auto listing = catalog(0x1C1);
            if (listing.available != std::vector<std::string>({"restroom", "kiosk", "lounge"})) return 1;
            if (listing.dropped_bits != 0x100) return 2;
            if (!catalog(0).available.empty()) return 3;
            auto full = catalog(0xFF);
            if (full.available.size() != 8 || full.available.front() != "restroom" || full.available.back() != "lounge") return 4;
            if (catalog(0x200).dropped_bits != 0x200) return 5;
            return 0;
            """,
            "normalization with an explicit dropped-bit account and table-ordered listing",
            "hiding dropped bits or listing in hash order",
            "mixed foreign bits, foreign-only codes, empty codes, and full-mask listings",
            "explicit unknown-bit accounting beside ordered listings",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26flg-campsite-permit-features",
            "Campsite permit features",
            "campsite_permits",
            """
            class Permit {
            public:
                bool grant(std::string_view feature);
                bool revoke(std::string_view feature);
                std::vector<std::string> granted() const;
                void reset();
            };
            """,
            """
            class Permit {
            public:
                bool grant(std::string_view feature);
                bool revoke(std::string_view feature);
                std::vector<std::string> granted() const;
                void reset();
            private:
                std::uint32_t mask_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kFeatures[] = {
                {"fire_ring", 8u}, {"picnic_table", 1u}, {"water", 16u}, {"electric", 2u},
                {"shower", 32u}, {"toilet", 4u}, {"trailhead", 64u},
            };
            }  // namespace
            bool Permit::grant(std::string_view feature) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kFeatures, 7, feature, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool Permit::revoke(std::string_view feature) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kFeatures, 7, feature, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            std::vector<std::string> Permit::granted() const {
                return f26flg_detail::ordered_names(kFeatures, 7, mask_);
            }
            void Permit::reset() { mask_ = 0; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kFeatures[] = {
                {"fire_ring", 8u}, {"picnic_table", 1u}, {"water", 16u}, {"electric", 2u},
                {"shower", 32u}, {"toilet", 4u}, {"trailhead", 64u},
            };
            }  // namespace
            bool Permit::grant(std::string_view feature) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kFeatures, 7, feature, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool Permit::revoke(std::string_view feature) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kFeatures, 7, feature, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            std::vector<std::string> Permit::granted() const {
                std::vector<std::string> out;
                for (std::uint64_t bit = 1; bit <= 64; bit <<= 1) {
                    if ((mask_ & bit) != 0) {
                        std::string_view name = f26flg_detail::lookup_name(kFeatures, 7, bit);
                        if (!name.empty()) out.emplace_back(name);
                    }
                }
                return out;
            }
            void Permit::reset() { mask_ = 0; }
            """,
            """
            Permit permit;
            if (!permit.grant("water") || !permit.grant("fire_ring")) return 1;
            if (permit.granted() != std::vector<std::string>({"fire_ring", "water"})) return 2;
            if (!permit.revoke("fire_ring") || permit.granted().size() != 1) return 3;
            permit.reset();
            if (!permit.granted().empty()) return 4;
            return 0;
            """,
            """
            Permit permit;
            if (permit.grant("dump_station")) return 1;
            if (!permit.grant("fire_ring") || !permit.grant("picnic_table")) return 2;
            if (permit.granted() != std::vector<std::string>({"fire_ring", "picnic_table"})) return 3;
            if (permit.revoke("dump_station")) return 4;
            if (!permit.revoke("picnic_table")) return 5;
            if (permit.granted() != std::vector<std::string>({"fire_ring"})) return 6;
            if (!permit.grant("trailhead") || !permit.grant("electric")) return 7;
            if (permit.granted() != std::vector<std::string>({"fire_ring", "electric", "trailhead"})) return 8;
            return 0;
            """,
            "name-validated grant and revoke with declaration-ordered snapshots",
            "ascending-bit iteration used as the listing order",
            "grant pairs whose declaration order disagrees with bit order, unknown names, revoke behavior, and reset",
            "stable declared ordering when it disagrees with bit order",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-studio-recording-channels",
            "Studio recording channels",
            "studio_channels",
            """
            class ChannelCursor {
            public:
                explicit ChannelCursor(std::uint32_t active_mask);
                std::optional<std::string> next();
                bool done() const;
            };
            """,
            """
            class ChannelCursor {
            public:
                explicit ChannelCursor(std::uint32_t active_mask);
                std::optional<std::string> next();
                bool done() const;
            private:
                std::uint32_t active_;
                std::size_t index_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kChannels[] = {
                {"kick", 256u}, {"snare", 1u}, {"hihat", 16u}, {"tom", 4u},
                {"bass", 64u}, {"guitar", 2u}, {"keys", 32u}, {"vocals", 8u},
                {"strings", 1024u}, {"brass", 128u}, {"woodwind", 512u}, {"percussion", 2048u},
            };
            }  // namespace
            ChannelCursor::ChannelCursor(std::uint32_t active_mask)
                : active_(static_cast<std::uint32_t>(active_mask & f26flg_detail::known_mask(kChannels, 12))) {}
            std::optional<std::string> ChannelCursor::next() {
                while (index_ < 12) {
                    const auto& entry = kChannels[index_++];
                    if ((active_ & entry.bit) != 0) return std::string(entry.name);
                }
                return std::nullopt;
            }
            bool ChannelCursor::done() const {
                for (std::size_t i = index_; i < 12; ++i) {
                    if ((active_ & kChannels[i].bit) != 0) return false;
                }
                return true;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kChannels[] = {
                {"kick", 256u}, {"snare", 1u}, {"hihat", 16u}, {"tom", 4u},
                {"bass", 64u}, {"guitar", 2u}, {"keys", 32u}, {"vocals", 8u},
                {"strings", 1024u}, {"brass", 128u}, {"woodwind", 512u}, {"percussion", 2048u},
            };
            }  // namespace
            ChannelCursor::ChannelCursor(std::uint32_t active_mask)
                : active_(static_cast<std::uint32_t>(active_mask & f26flg_detail::known_mask(kChannels, 12))) {}
            std::optional<std::string> ChannelCursor::next() {
                while (index_ < 64) {
                    const std::uint64_t bit = std::uint64_t{1} << index_++;
                    if ((active_ & bit) != 0) {
                        std::string_view name = f26flg_detail::lookup_name(kChannels, 12, bit);
                        if (!name.empty()) return std::string(name);
                    }
                }
                return std::nullopt;
            }
            bool ChannelCursor::done() const {
                for (std::size_t i = index_; i < 64; ++i) {
                    if ((active_ & (std::uint64_t{1} << i)) != 0) return false;
                }
                return true;
            }
            """,
            """
            ChannelCursor cursor(0x05);
            auto first = cursor.next();
            if (!first || *first != "snare") return 1;
            auto second = cursor.next();
            if (!second || *second != "tom") return 2;
            if (cursor.next() != std::nullopt || !cursor.done()) return 3;
            return 0;
            """,
            """
            ChannelCursor cursor(0x101);
            auto first = cursor.next();
            if (!first || *first != "kick") return 1;
            if (cursor.done()) return 2;
            auto second = cursor.next();
            if (!second || *second != "snare") return 3;
            if (!cursor.done()) return 4;
            ChannelCursor empty(0x1000);
            if (empty.next() != std::nullopt || !empty.done()) return 5;
            ChannelCursor full(0xFFF);
            std::size_t count = 0;
            while (full.next()) ++count;
            if (count != 12) return 6;
            return 0;
            """,
            "cursor over a declaration-ordered channel table with sticky exhaustion",
            "bit-ascending traversal as the iteration order",
            "masks where declaration and bit orders disagree, foreign-only masks, full masks, and post-exhaustion reads",
            "streaming iteration with explicit ordering semantics",
            "streaming accumulator, iterator, or incremental writer",
            project_support=True,
        ),
        c(
            "f26flg-botanic-trail-markers",
            "Botanic trail markers",
            "trail_markers",
            """
            class TrailLog {
            public:
                bool visit(std::string_view marker);
                std::vector<std::string> visited() const;
                std::string describe() const;
                void reset();
            };
            """,
            """
            class TrailLog {
            public:
                bool visit(std::string_view marker);
                std::vector<std::string> visited() const;
                std::string describe() const;
                void reset();
            private:
                std::uint32_t seen_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kMarkers[] = {
                {"trailhead", 1u}, {"overlook", 2u}, {"waterfall", 4u},
                {"meadow", 8u}, {"grove", 16u}, {"summit", 32u},
            };
            }  // namespace
            bool TrailLog::visit(std::string_view marker) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kMarkers, 6, marker, bit)) return false;
                seen_ = static_cast<std::uint32_t>(seen_ | bit);
                return true;
            }
            std::vector<std::string> TrailLog::visited() const {
                return f26flg_detail::ordered_names(kMarkers, 6, seen_);
            }
            std::string TrailLog::describe() const {
                auto names = f26flg_detail::ordered_names(kMarkers, 6, seen_);
                if (names.empty()) return "unmarked";
                return f26flg_detail::join_names(names, " -> ");
            }
            void TrailLog::reset() { seen_ = 0; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kMarkers[] = {
                {"trailhead", 1u}, {"overlook", 2u}, {"waterfall", 4u},
                {"meadow", 8u}, {"grove", 16u}, {"summit", 32u},
            };
            }  // namespace
            bool TrailLog::visit(std::string_view marker) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kMarkers, 6, marker, bit)) return false;
                seen_ = static_cast<std::uint32_t>(seen_ | bit);
                return true;
            }
            std::vector<std::string> TrailLog::visited() const {
                std::vector<std::string> out;
                for (std::size_t i = 6; i-- > 0;) {
                    if ((seen_ & kMarkers[i].bit) != 0) out.emplace_back(kMarkers[i].name);
                }
                return out;
            }
            std::string TrailLog::describe() const {
                auto names = visited();
                if (names.empty()) return "unmarked";
                return f26flg_detail::join_names(names, " -> ");
            }
            void TrailLog::reset() { seen_ = 0; }
            """,
            """
            TrailLog log;
            if (!log.visit("waterfall")) return 1;
            if (log.describe() != "waterfall") return 2;
            if (!log.visit("overlook")) return 3;
            if (log.describe() != "overlook -> waterfall") return 4;
            log.reset();
            if (log.describe() != "unmarked") return 5;
            return 0;
            """,
            """
            TrailLog log;
            if (log.visit("cave")) return 1;
            if (log.describe() != "unmarked") return 2;
            if (!log.visit("summit") || !log.visit("trailhead") || !log.visit("grove")) return 3;
            if (log.visited() != std::vector<std::string>({"trailhead", "grove", "summit"})) return 4;
            if (log.describe() != "trailhead -> grove -> summit") return 5;
            if (!log.visit("meadow")) return 6;
            if (log.visited().size() != 4) return 7;
            log.reset();
            if (!log.visited().empty()) return 8;
            return 0;
            """,
            "visit recording with canonical table-ordered rendering",
            "reverse-order or visit-order rendering of the marker list",
            "out-of-order visits, unknown markers, exact joined strings, and reset",
            "exact formatted ordering over a stateful mask",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-harbor-dock-services",
            "Harbor dock services",
            "dock_services",
            """
            class ServiceError : public std::out_of_range {
            public:
                explicit ServiceError(const std::string& message) : std::out_of_range(message) {}
            };
            std::vector<std::string> billed(std::uint32_t code);
            std::string require_first(std::uint32_t code);
            """,
            """
            class ServiceError : public std::out_of_range {
            public:
                explicit ServiceError(const std::string& message) : std::out_of_range(message) {}
            };
            std::vector<std::string> billed(std::uint32_t code);
            std::string require_first(std::uint32_t code);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kServices[] = {
                {"fueling", 128u}, {"water", 1u}, {"power", 16u}, {"waste", 2u},
                {"ice", 32u}, {"bait", 4u}, {"repairs", 256u}, {"crane", 8u}, {"storage", 64u},
            };
            }  // namespace
            std::vector<std::string> billed(std::uint32_t code) {
                const std::uint64_t known = f26flg_detail::known_mask(kServices, 9);
                return f26flg_detail::ordered_names(kServices, 9, code & known);
            }
            std::string require_first(std::uint32_t code) {
                const std::uint64_t known = f26flg_detail::known_mask(kServices, 9);
                const std::uint32_t normalized = static_cast<std::uint32_t>(code & known);
                for (const auto& entry : kServices) {
                    if ((normalized & entry.bit) != 0) return entry.name;
                }
                throw ServiceError("no dock services billed");
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kServices[] = {
                {"fueling", 128u}, {"water", 1u}, {"power", 16u}, {"waste", 2u},
                {"ice", 32u}, {"bait", 4u}, {"repairs", 256u}, {"crane", 8u}, {"storage", 64u},
            };
            }  // namespace
            std::vector<std::string> billed(std::uint32_t code) {
                const std::uint64_t known = f26flg_detail::known_mask(kServices, 9);
                return f26flg_detail::ordered_names(kServices, 9, code & known);
            }
            std::string require_first(std::uint32_t code) {
                for (std::uint64_t bit = 1; bit != 0; bit <<= 1) {
                    if ((code & bit) != 0) {
                        std::string_view name = f26flg_detail::lookup_name(kServices, 9, bit);
                        if (!name.empty()) return std::string(name);
                    }
                }
                throw ServiceError("no dock services billed");
            }
            """,
            """
            if (billed(0x03) != std::vector<std::string>({"water", "waste"})) return 1;
            if (require_first(0x80) != "fueling") return 2;
            return 0;
            """,
            """
            if (billed(0x1FF).size() != 9) return 1;
            if (!billed(0x200).empty()) return 2;
            bool threw = false;
            try {
                (void)require_first(0);
            } catch (const ServiceError&) {
                threw = true;
            }
            if (!threw) return 3;
            threw = false;
            try {
                (void)require_first(0x200);
            } catch (const ServiceError&) {
                threw = true;
            }
            if (!threw) return 4;
            if (require_first(0x81) != "fueling") return 5;
            if (require_first(0x108) != "repairs") return 6;
            if (billed(0xFF) != std::vector<std::string>({"fueling", "water", "power", "waste", "ice", "bait", "crane", "storage"})) return 7;
            return 0;
            """,
            "declaration-ordered listing plus a first-match rule with a typed empty error",
            "lowest-bit selection as the first billed service",
            "first services where table order and bit order disagree, foreign-only codes, empty codes, and full listings",
            "first-match semantics decoupled from bit values",
            "exception-throwing policy object or service class",
        ),
        c(
            "f26flg-orchestra-section-roster",
            "Orchestra section roster",
            "orchestra_roster",
            """
            class Roster {
            public:
                static std::optional<Roster> create(const std::vector<std::pair<std::string, std::uint32_t>>& sections);
                std::vector<std::string> present(std::uint32_t mask) const;
                std::optional<bool> seated(std::string_view section, std::uint32_t mask) const;
            };
            """,
            """
            class Roster {
            public:
                static std::optional<Roster> create(const std::vector<std::pair<std::string, std::uint32_t>>& sections);
                std::vector<std::string> present(std::uint32_t mask) const;
                std::optional<bool> seated(std::string_view section, std::uint32_t mask) const;
            private:
                explicit Roster(std::vector<std::pair<std::string, std::uint32_t>> sections);
                std::vector<std::pair<std::string, std::uint32_t>> sections_;
            };
            """,
            """
            std::optional<Roster> Roster::create(const std::vector<std::pair<std::string, std::uint32_t>>& sections) {
                if (sections.empty() || sections.size() > 12) return std::nullopt;
                std::uint64_t seen = 0;
                for (std::size_t i = 0; i < sections.size(); ++i) {
                    const std::uint32_t bit = sections[i].second;
                    if (sections[i].first.empty() || bit == 0 || (bit & (bit - 1)) != 0 || bit > 0x800u) return std::nullopt;
                    if ((seen & bit) != 0) return std::nullopt;
                    seen |= bit;
                    for (std::size_t j = 0; j < i; ++j) {
                        if (sections[j].first == sections[i].first) return std::nullopt;
                    }
                }
                return Roster(sections);
            }
            Roster::Roster(std::vector<std::pair<std::string, std::uint32_t>> sections) : sections_(std::move(sections)) {}
            std::vector<std::string> Roster::present(std::uint32_t mask) const {
                std::vector<std::string> out;
                for (const auto& entry : sections_) {
                    if ((mask & entry.second) != 0) out.push_back(entry.first);
                }
                return out;
            }
            std::optional<bool> Roster::seated(std::string_view section, std::uint32_t mask) const {
                for (const auto& entry : sections_) {
                    if (entry.first == section) return (mask & entry.second) != 0;
                }
                return std::nullopt;
            }
            """,
            """
            std::optional<Roster> Roster::create(const std::vector<std::pair<std::string, std::uint32_t>>& sections) {
                if (sections.empty() || sections.size() > 12) return std::nullopt;
                std::uint64_t seen = 0;
                for (std::size_t i = 0; i < sections.size(); ++i) {
                    const std::uint32_t bit = sections[i].second;
                    if (sections[i].first.empty() || bit == 0 || (bit & (bit - 1)) != 0 || bit > 0x800u) return std::nullopt;
                    if ((seen & bit) != 0) return std::nullopt;
                    seen |= bit;
                    for (std::size_t j = 0; j < i; ++j) {
                        if (sections[j].first == sections[i].first) return std::nullopt;
                    }
                }
                return Roster(sections);
            }
            Roster::Roster(std::vector<std::pair<std::string, std::uint32_t>> sections) : sections_(std::move(sections)) {}
            std::vector<std::string> Roster::present(std::uint32_t mask) const {
                std::vector<std::pair<std::uint32_t, std::string>> by_bit;
                for (const auto& entry : sections_) {
                    if ((mask & entry.second) != 0) by_bit.emplace_back(entry.second, entry.first);
                }
                std::sort(by_bit.begin(), by_bit.end());
                std::vector<std::string> out;
                for (const auto& entry : by_bit) out.push_back(entry.second);
                return out;
            }
            std::optional<bool> Roster::seated(std::string_view section, std::uint32_t mask) const {
                for (const auto& entry : sections_) {
                    if (entry.first == section) return (mask & entry.second) != 0;
                }
                return std::nullopt;
            }
            """,
            """
            auto roster = Roster::create({{"brass", 16}, {"strings", 1}, {"woodwind", 4}, {"percussion", 2}});
            if (!roster) return 1;
            auto on = roster->present(0x05);
            if (on != std::vector<std::string>({"strings", "woodwind"})) return 2;
            return 0;
            """,
            """
            if (!Roster::create({{"brass", 16}, {"strings", 1}})) return 1;
            if (Roster::create({{"brass", 3}})) return 2;
            if (Roster::create({{"brass", 1}, {"brass", 2}})) return 3;
            if (Roster::create({{"brass", 1}, {"strings", 1}})) return 4;
            if (Roster::create({})) return 5;
            auto roster = Roster::create({{"brass", 16}, {"strings", 1}, {"woodwind", 4}, {"percussion", 2}});
            if (!roster) return 6;
            auto on = roster->present(0x07);
            if (on != std::vector<std::string>({"strings", "woodwind", "percussion"})) return 7;
            auto seated = roster->seated("brass", 0x10);
            if (!seated || !*seated) return 8;
            if (roster->seated("harp", 0xFF)) return 9;
            auto absent = roster->seated("brass", 0x01);
            if (!absent || *absent) return 10;
            if (!roster->present(0x20).empty()) return 11;
            return 0;
            """,
            "validated runtime tables with injection-ordered listing and optional membership",
            "re-sorting listings by ascending bit value",
            "shuffled injected bit assignments, duplicate names and bits, invalid bits, empty tables, unknown sections, and foreign mask bits",
            "runtime table ordering independent of bit assignment",
            "injected flag-table/policy object",
            project_support=True,
        ),
        c(
            "f26flg-railcar-consist-flags",
            "Railcar consist flags",
            "railcar_consist",
            """
            class Consist {
            public:
                static Consist from_code(std::uint32_t code);
                Consist add(const Consist& other) const;
                Consist without(const Consist& other) const;
                std::vector<std::string> cars() const;
                std::uint32_t code() const;
                friend bool operator==(const Consist& left, const Consist& right) { return left.mask_ == right.mask_; }
            };
            """,
            """
            class Consist {
            public:
                static Consist from_code(std::uint32_t code);
                Consist add(const Consist& other) const;
                Consist without(const Consist& other) const;
                std::vector<std::string> cars() const;
                std::uint32_t code() const;
                friend bool operator==(const Consist& left, const Consist& right) { return left.mask_ == right.mask_; }
            private:
                explicit Consist(std::uint32_t mask);
                std::uint32_t mask_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kCars[] = {
                {"locomotive", 1u}, {"tender", 2u}, {"boxcar", 4u}, {"hopper", 8u},
                {"tanker", 16u}, {"flatcar", 32u}, {"caboose", 64u}, {"sleeper", 128u},
            };
            }  // namespace
            Consist::Consist(std::uint32_t mask) : mask_(mask & 0xFFu) {}
            Consist Consist::from_code(std::uint32_t code) { return Consist(code); }
            Consist Consist::add(const Consist& other) const { return Consist(mask_ | other.mask_); }
            Consist Consist::without(const Consist& other) const { return Consist(mask_ & ~other.mask_); }
            std::vector<std::string> Consist::cars() const {
                return f26flg_detail::ordered_names(kCars, 8, mask_);
            }
            std::uint32_t Consist::code() const { return mask_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kCars[] = {
                {"locomotive", 1u}, {"tender", 2u}, {"boxcar", 4u}, {"hopper", 8u},
                {"tanker", 16u}, {"flatcar", 32u}, {"caboose", 64u}, {"sleeper", 128u},
            };
            }  // namespace
            Consist::Consist(std::uint32_t mask) : mask_(mask & 0xFFu) {}
            Consist Consist::from_code(std::uint32_t code) { return Consist(code); }
            Consist Consist::add(const Consist& other) const { return Consist(mask_ | other.mask_); }
            Consist Consist::without(const Consist& other) const { return Consist(mask_ ^ other.mask_); }
            std::vector<std::string> Consist::cars() const {
                return f26flg_detail::ordered_names(kCars, 8, mask_);
            }
            std::uint32_t Consist::code() const { return mask_; }
            """,
            """
            auto freight = Consist::from_code(0x0C);
            if (freight.cars() != std::vector<std::string>({"boxcar", "hopper"})) return 1;
            if (freight.add(Consist::from_code(0x01)).code() != 0x0D) return 2;
            if (freight.without(Consist::from_code(0x04)).code() != 0x08) return 3;
            return 0;
            """,
            """
            if (Consist::from_code(0x1FF).code() != 0xFF) return 1;
            auto freight = Consist::from_code(0x0C);
            auto extra = Consist::from_code(0x18);
            if (freight.without(extra).code() != 0x04) return 2;
            if (freight.add(extra).cars() != std::vector<std::string>({"boxcar", "hopper", "tanker"})) return 3;
            if (!(Consist::from_code(0x80) == Consist::from_code(0x180))) return 4;
            if (!Consist::from_code(0).cars().empty()) return 5;
            if (Consist::from_code(0x40).cars().front() != "caboose") return 6;
            return 0;
            """,
            "normalized value type with union, difference, and table-ordered listing",
            "xor used as set difference",
            "difference with overlapping sets, union listings, normalized equality, and empty consists",
            "exact set-algebra semantics on flag masks",
            "value type with operator==, operator<, arithmetic, or formatting helpers",
        ),
        c(
            "f26flg-greenhouse-vent-program",
            "Greenhouse vent program",
            "vent_program",
            """
            class Program {
            public:
                bool stage(std::string_view vent);
                std::vector<std::string> sequence() const;
                std::size_t staged() const;
                bool commit();
            };
            """,
            """
            class Program {
            public:
                bool stage(std::string_view vent);
                std::vector<std::string> sequence() const;
                std::size_t staged() const;
                bool commit();
            private:
                std::uint32_t mask_ = 0;
                std::vector<std::string> order_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kVents[] = {
                {"roof", 1u}, {"side", 2u}, {"louver", 4u}, {"ridge", 8u}, {"exhaust", 16u},
            };
            }  // namespace
            bool Program::stage(std::string_view vent) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kVents, 5, vent, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                order_.emplace_back(vent);
                return true;
            }
            std::vector<std::string> Program::sequence() const { return order_; }
            std::size_t Program::staged() const { return order_.size(); }
            bool Program::commit() {
                if (order_.empty()) return false;
                order_.clear();
                mask_ = 0;
                return true;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kVents[] = {
                {"roof", 1u}, {"side", 2u}, {"louver", 4u}, {"ridge", 8u}, {"exhaust", 16u},
            };
            }  // namespace
            bool Program::stage(std::string_view vent) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kVents, 5, vent, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                order_.emplace_back(vent);
                return true;
            }
            std::vector<std::string> Program::sequence() const { return order_; }
            std::size_t Program::staged() const { return order_.size(); }
            bool Program::commit() {
                if (order_.empty()) return false;
                order_.clear();
                mask_ = 0;
                return true;
            }
            """,
            """
            Program program;
            if (!program.stage("roof") || !program.stage("exhaust")) return 1;
            if (program.sequence() != std::vector<std::string>({"roof", "exhaust"})) return 2;
            if (program.staged() != 2) return 3;
            if (!program.commit() || program.staged() != 0) return 4;
            if (program.commit()) return 5;
            return 0;
            """,
            """
            Program program;
            if (program.stage("chimney")) return 1;
            if (!program.stage("roof")) return 2;
            if (program.stage("roof")) return 3;
            if (program.sequence().size() != 1) return 4;
            if (!program.stage("louver") || !program.stage("side")) return 5;
            if (program.sequence() != std::vector<std::string>({"roof", "louver", "side"})) return 6;
            if (!program.commit()) return 7;
            if (!program.sequence().empty() || program.staged() != 0) return 8;
            if (program.stage("chimney")) return 9;
            return 0;
            """,
            "insertion-ordered staging with duplicate rejection and a draining commit",
            "accepting duplicate stages or silently sorting the staging order",
            "duplicate and unknown staging, staging-order snapshots, commit drains, and post-commit state",
            "insertion-order semantics distinct from table-order roots",
            "streaming accumulator, iterator, or incremental writer",
            project_support=True,
        ),
        c(
            "f26flg-museum-gallery-wings",
            "Museum gallery wings",
            "gallery_wings",
            """
            struct Tour {
                bool any;
                std::vector<std::string> route;
                std::size_t skipped;
            };
            Tour plan(std::uint32_t wings_code);
            """,
            """
            struct Tour {
                bool any;
                std::vector<std::string> route;
                std::size_t skipped;
            };
            Tour plan(std::uint32_t wings_code);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kWings[] = {
                {"ancient", 1u}, {"medieval", 2u}, {"renaissance", 4u}, {"baroque", 8u},
                {"rococo", 16u}, {"neoclassical", 32u}, {"romantic", 64u}, {"impressionist", 128u},
                {"modern", 256u}, {"contemporary", 512u},
            };
            }  // namespace
            Tour plan(std::uint32_t wings_code) {
                const std::uint64_t known = f26flg_detail::known_mask(kWings, 10);
                const std::uint32_t normalized = static_cast<std::uint32_t>(wings_code & known);
                auto route = f26flg_detail::ordered_names(kWings, 10, normalized);
                return {!route.empty(), route, f26flg_detail::count_bits(wings_code & ~known)};
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kWings[] = {
                {"ancient", 1u}, {"medieval", 2u}, {"renaissance", 4u}, {"baroque", 8u},
                {"rococo", 16u}, {"neoclassical", 32u}, {"romantic", 64u}, {"impressionist", 128u},
                {"modern", 256u}, {"contemporary", 512u},
            };
            }  // namespace
            Tour plan(std::uint32_t wings_code) {
                const std::uint64_t known = f26flg_detail::known_mask(kWings, 10);
                const std::uint32_t normalized = static_cast<std::uint32_t>(wings_code & known);
                auto route = f26flg_detail::ordered_names(kWings, 10, normalized);
                return {!route.empty(), route, 0u};
            }
            """,
            """
            auto tour = plan(0x05);
            if (!tour.any || tour.route != std::vector<std::string>({"ancient", "renaissance"})) return 1;
            if (tour.skipped != 0) return 2;
            if (plan(0).any) return 3;
            return 0;
            """,
            """
            auto tour = plan(0xE03);
            if (tour.route != std::vector<std::string>({"ancient", "medieval", "contemporary"})) return 1;
            if (tour.skipped != 2) return 2;
            if (plan(0x400).any) return 3;
            if (plan(0x3FF).route.size() != 10) return 4;
            if (plan(0x3FF).skipped != 0) return 5;
            return 0;
            """,
            "normalization with table-ordered routing and a foreign-bit skip count",
            "dropping foreign bits silently without accounting",
            "two foreign bits, foreign-only codes, full masks, and empty codes",
            "dropped-bit counting beside ordered output",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26flg-speedway-pit-crews",
            "Speedway pit crews",
            "pit_crews",
            """
            class CrewError : public std::logic_error {
            public:
                explicit CrewError(const std::string& message) : std::logic_error(message) {}
            };
            class Board {
            public:
                void post(std::uint32_t crew_mask);
                std::vector<std::string> order() const;
                std::string chief() const;
            };
            """,
            """
            class CrewError : public std::logic_error {
            public:
                explicit CrewError(const std::string& message) : std::logic_error(message) {}
            };
            class Board {
            public:
                void post(std::uint32_t crew_mask);
                std::vector<std::string> order() const;
                std::string chief() const;
            private:
                std::uint32_t posted_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kCrews[] = {
                {"tires", 1u}, {"fuel", 2u}, {"aero", 4u},
                {"engine", 8u}, {"radio", 16u}, {"jack", 32u},
            };
            }  // namespace
            void Board::post(std::uint32_t crew_mask) {
                posted_ = static_cast<std::uint32_t>(crew_mask & f26flg_detail::known_mask(kCrews, 6));
            }
            std::vector<std::string> Board::order() const {
                return f26flg_detail::ordered_names(kCrews, 6, posted_);
            }
            std::string Board::chief() const {
                for (const auto& entry : kCrews) {
                    if ((posted_ & entry.bit) != 0) return entry.name;
                }
                throw CrewError("no pit crew posted");
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kCrews[] = {
                {"tires", 1u}, {"fuel", 2u}, {"aero", 4u},
                {"engine", 8u}, {"radio", 16u}, {"jack", 32u},
            };
            }  // namespace
            void Board::post(std::uint32_t crew_mask) {
                posted_ = static_cast<std::uint32_t>(posted_ | (crew_mask & f26flg_detail::known_mask(kCrews, 6)));
            }
            std::vector<std::string> Board::order() const {
                return f26flg_detail::ordered_names(kCrews, 6, posted_);
            }
            std::string Board::chief() const {
                for (const auto& entry : kCrews) {
                    if ((posted_ & entry.bit) != 0) return entry.name;
                }
                throw CrewError("no pit crew posted");
            }
            """,
            """
            Board board;
            board.post(0x03);
            if (board.order() != std::vector<std::string>({"tires", "fuel"})) return 1;
            if (board.chief() != "tires") return 2;
            return 0;
            """,
            """
            Board board;
            board.post(0x03);
            board.post(0x20);
            if (board.order() != std::vector<std::string>({"jack"})) return 1;
            if (board.chief() != "jack") return 2;
            board.post(0x3F);
            if (board.order().size() != 6 || board.chief() != "tires") return 3;
            board.post(0x40);
            bool threw = false;
            try {
                (void)board.chief();
            } catch (const CrewError&) {
                threw = true;
            }
            if (!threw) return 4;
            if (!board.order().empty()) return 5;
            board.post(0x10);
            if (board.order() != std::vector<std::string>({"radio"})) return 6;
            return 0;
            """,
            "replace-not-accumulate posting with declaration-ordered listing and a typed empty error",
            "union-accumulating posts across calls",
            "repeated posts, foreign-only posts, CrewError on empty boards, and table order",
            "replace semantics and empty-state errors",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-lighthouse-beam-channels",
            "Lighthouse beam channels",
            "beam_channels",
            """
            struct NormalizeResult {
                std::uint32_t normalized;
                bool had_foreign;
            };
            NormalizeResult confine(std::uint32_t raw);
            bool supported(std::uint32_t raw, std::string_view channel);
            """,
            """
            struct NormalizeResult {
                std::uint32_t normalized;
                bool had_foreign;
            };
            NormalizeResult confine(std::uint32_t raw);
            bool supported(std::uint32_t raw, std::string_view channel);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kChannels[] = {
                {"rotation", 1u}, {"intensity", 2u}, {"color", 4u}, {"foghorn", 8u},
            };
            }  // namespace
            NormalizeResult confine(std::uint32_t raw) {
                const std::uint32_t normalized = raw & 0x0Fu;
                return {normalized, normalized != raw};
            }
            bool supported(std::uint32_t raw, std::string_view channel) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kChannels, 4, channel, bit)) return false;
                return (raw & 0x0Fu & bit) != 0;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kChannels[] = {
                {"rotation", 1u}, {"intensity", 2u}, {"color", 4u}, {"foghorn", 8u},
            };
            }  // namespace
            NormalizeResult confine(std::uint32_t raw) {
                const std::uint32_t normalized = raw & 0xFFu;
                return {normalized, normalized != raw};
            }
            bool supported(std::uint32_t raw, std::string_view channel) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kChannels, 4, channel, bit)) return false;
                return (raw & bit) != 0;
            }
            """,
            """
            auto result = confine(0x0B);
            if (result.normalized != 0x0B || result.had_foreign) return 1;
            if (!supported(0x0B, "rotation") || supported(0x0B, "color")) return 2;
            if (supported(0x0B, "timer")) return 3;
            return 0;
            """,
            """
            auto result = confine(0xF4);
            if (result.normalized != 0x04 || !result.had_foreign) return 1;
            if (confine(0x0F).had_foreign) return 2;
            if (!supported(0x18, "foghorn")) return 3;
            if (supported(0x10, "rotation")) return 4;
            auto wide = confine(0x1FF);
            if (wide.normalized != 0x0F || !wide.had_foreign) return 5;
            return 0;
            """,
            "four-bit boundary confinement with foreign detection and normalized membership",
            "confining to the wrong bit width",
            "confine boundary cases, had_foreign transitions, foreign-only membership, and wide masks",
            "narrow-boundary normalization discipline",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26flg-inventory-aisle-sensors",
            "Inventory aisle sensors",
            "aisle_sensors",
            """
            class SensorGate {
            public:
                bool admit(std::uint32_t reading);
                std::uint32_t accepted() const;
                std::uint32_t rejected_bits() const;
                std::size_t rejections() const;
                void reset();
            };
            """,
            """
            class SensorGate {
            public:
                bool admit(std::uint32_t reading);
                std::uint32_t accepted() const;
                std::uint32_t rejected_bits() const;
                std::size_t rejections() const;
                void reset();
            private:
                std::uint32_t accepted_ = 0;
                std::uint32_t rejected_ = 0;
                std::size_t rejections_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSensors[] = {
                {"entry", 1u}, {"exit", 2u}, {"motion", 4u}, {"weight", 8u},
                {"temperature", 16u}, {"humidity", 32u}, {"light", 64u}, {"door", 128u},
                {"camera", 256u}, {"alarm", 512u}, {"sprinkler", 1024u}, {"vent", 2048u},
                {"scanner", 4096u}, {"beacon", 8192u}, {"counter", 16384u}, {"siren", 32768u},
            };
            }  // namespace
            bool SensorGate::admit(std::uint32_t reading) {
                accepted_ |= reading & 0xFFFFu;
                const std::uint32_t foreign = reading & ~0xFFFFu;
                rejected_ |= foreign;
                if (foreign != 0) ++rejections_;
                return true;
            }
            std::uint32_t SensorGate::accepted() const { return accepted_; }
            std::uint32_t SensorGate::rejected_bits() const { return rejected_; }
            std::size_t SensorGate::rejections() const { return rejections_; }
            void SensorGate::reset() {
                accepted_ = 0;
                rejected_ = 0;
                rejections_ = 0;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSensors[] = {
                {"entry", 1u}, {"exit", 2u}, {"motion", 4u}, {"weight", 8u},
                {"temperature", 16u}, {"humidity", 32u}, {"light", 64u}, {"door", 128u},
                {"camera", 256u}, {"alarm", 512u}, {"sprinkler", 1024u}, {"vent", 2048u},
                {"scanner", 4096u}, {"beacon", 8192u}, {"counter", 16384u}, {"siren", 32768u},
            };
            }  // namespace
            bool SensorGate::admit(std::uint32_t reading) {
                accepted_ |= reading & 0xFFFFu;
                rejected_ |= reading & ~0xFFFFu;
                return true;
            }
            std::uint32_t SensorGate::accepted() const { return accepted_; }
            std::uint32_t SensorGate::rejected_bits() const { return rejected_; }
            std::size_t SensorGate::rejections() const { return rejections_; }
            void SensorGate::reset() {
                accepted_ = 0;
                rejected_ = 0;
                rejections_ = 0;
            }
            """,
            """
            SensorGate gate;
            if (!gate.admit(0x05)) return 1;
            if (gate.accepted() != 0x05 || gate.rejected_bits() != 0) return 2;
            if (!gate.admit(0x10005)) return 3;
            if (gate.accepted() != 0x05 || gate.rejected_bits() != 0x10000) return 4;
            gate.reset();
            if (gate.accepted() != 0 || gate.rejected_bits() != 0) return 5;
            return 0;
            """,
            """
            SensorGate gate;
            if (!gate.admit(0x10005) || gate.rejections() != 1) return 1;
            if (!gate.admit(0x20000) || gate.rejections() != 2) return 2;
            if (!gate.admit(0x0003) || gate.rejections() != 2) return 3;
            if (gate.rejected_bits() != 0x30000) return 4;
            if (gate.accepted() != 0x07) return 5;
            gate.reset();
            if (gate.rejections() != 0 || gate.rejected_bits() != 0 || gate.accepted() != 0) return 6;
            if (!gate.admit(0xFFFFFFFFu)) return 7;
            if (gate.accepted() != 0xFFFF || gate.rejected_bits() != 0xFFFF0000u || gate.rejections() != 1) return 8;
            return 0;
            """,
            "wide sixteen-bit boundary with separate accepted and rejected ledgers plus a rejection counter",
            "dropping rejected-bit or rejection-count accounting",
            "clean and dirty readings, rejection counting only for dirty readings, combined foreign bits, and reset",
            "ledger-style boundary accounting over a wide mask",
            "streaming accumulator, iterator, or incremental writer",
            project_support=True,
        ),
        c(
            "f26flg-broadcast-transmission-modes",
            "Broadcast transmission modes",
            "transmission_modes",
            """
            class ModeRangeError : public std::out_of_range {
            public:
                explicit ModeRangeError(const std::string& message) : std::out_of_range(message) {}
            };
            std::uint32_t enforce(std::uint32_t raw);
            bool carries(std::uint32_t confined, std::string_view mode);
            """,
            """
            class ModeRangeError : public std::out_of_range {
            public:
                explicit ModeRangeError(const std::string& message) : std::out_of_range(message) {}
            };
            std::uint32_t enforce(std::uint32_t raw);
            bool carries(std::uint32_t confined, std::string_view mode);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kModes[] = {
                {"am", 1u}, {"fm", 2u}, {"shortwave", 4u}, {"satellite", 8u}, {"cable", 16u},
            };
            }  // namespace
            std::uint32_t enforce(std::uint32_t raw) {
                if ((raw & ~0x1Fu) != 0) throw ModeRangeError("transmission bits outside the licensed band");
                return raw;
            }
            bool carries(std::uint32_t confined, std::string_view mode) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModes, 5, mode, bit)) return false;
                return (confined & 0x1Fu & bit) != 0;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kModes[] = {
                {"am", 1u}, {"fm", 2u}, {"shortwave", 4u}, {"satellite", 8u}, {"cable", 16u},
            };
            }  // namespace
            std::uint32_t enforce(std::uint32_t raw) {
                return raw & 0x1Fu;
            }
            bool carries(std::uint32_t confined, std::string_view mode) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModes, 5, mode, bit)) return false;
                return (confined & bit) != 0;
            }
            """,
            """
            if (enforce(0x15) != 0x15) return 1;
            if (!carries(0x15, "am") || carries(0x15, "fm")) return 2;
            if (carries(0x15, "internet")) return 3;
            return 0;
            """,
            """
            bool threw = false;
            try {
                (void)enforce(0x20);
            } catch (const ModeRangeError&) {
                threw = true;
            }
            if (!threw) return 1;
            threw = false;
            try {
                (void)enforce(0x80000000u);
            } catch (const ModeRangeError&) {
                threw = true;
            }
            if (!threw) return 2;
            if (enforce(0x1F) != 0x1F) return 3;
            if (enforce(0x00) != 0x00) return 4;
            if (carries(0x20, "am")) return 5;
            if (!carries(0x10, "cable")) return 6;
            return 0;
            """,
            "boundary enforcement by exception instead of masking, with normalized membership",
            "masking away out-of-band bits instead of reporting them",
            "throws for bit five and the top bit, full in-band masks, zero masks, and unknown mode names",
            "throw-on-foreign policy contrasted with mask-on-foreign roots",
            "exception-throwing policy object or service class",
        ),
        c(
            "f26flg-ski-resort-lift-tickets",
            "Ski resort lift tickets",
            "lift_tickets",
            """
            class Ticket {
            public:
                static Ticket issue(std::uint32_t code);
                bool covers(std::string_view lift) const;
                bool subset_of(const Ticket& other) const;
                std::uint32_t code() const;
                friend bool operator==(const Ticket& left, const Ticket& right) { return left.mask_ == right.mask_; }
            };
            """,
            """
            class Ticket {
            public:
                static Ticket issue(std::uint32_t code);
                bool covers(std::string_view lift) const;
                bool subset_of(const Ticket& other) const;
                std::uint32_t code() const;
                friend bool operator==(const Ticket& left, const Ticket& right) { return left.mask_ == right.mask_; }
            private:
                explicit Ticket(std::uint32_t mask);
                std::uint32_t mask_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kLifts[] = {
                {"gondola", 1u}, {"chairlift", 2u}, {"tbar", 4u}, {"rope", 8u},
                {"carpet", 16u}, {"funicular", 32u}, {"tram", 64u},
            };
            }  // namespace
            Ticket::Ticket(std::uint32_t mask) : mask_(mask & 0x7Fu) {}
            Ticket Ticket::issue(std::uint32_t code) { return Ticket(code); }
            bool Ticket::covers(std::string_view lift) const {
                std::uint64_t bit = 0;
                return f26flg_detail::lookup_bit(kLifts, 7, lift, bit) && (mask_ & bit) != 0;
            }
            bool Ticket::subset_of(const Ticket& other) const { return (mask_ & ~other.mask_) == 0; }
            std::uint32_t Ticket::code() const { return mask_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kLifts[] = {
                {"gondola", 1u}, {"chairlift", 2u}, {"tbar", 4u}, {"rope", 8u},
                {"carpet", 16u}, {"funicular", 32u}, {"tram", 64u},
            };
            }  // namespace
            Ticket::Ticket(std::uint32_t mask) : mask_(mask) {}
            Ticket Ticket::issue(std::uint32_t code) { return Ticket(code); }
            bool Ticket::covers(std::string_view lift) const {
                std::uint64_t bit = 0;
                return f26flg_detail::lookup_bit(kLifts, 7, lift, bit) && (mask_ & bit) != 0;
            }
            bool Ticket::subset_of(const Ticket& other) const { return (mask_ & ~other.mask_) == 0; }
            std::uint32_t Ticket::code() const { return mask_; }
            """,
            """
            auto pass = Ticket::issue(0x07);
            if (!pass.covers("gondola") || !pass.covers("tbar")) return 1;
            if (pass.covers("tram")) return 2;
            if (!Ticket::issue(0x03).subset_of(pass)) return 3;
            if (pass.subset_of(Ticket::issue(0x03))) return 4;
            return 0;
            """,
            """
            if (!(Ticket::issue(0xFF) == Ticket::issue(0x7F))) return 1;
            if (!Ticket::issue(0xFF).subset_of(Ticket::issue(0x7F))) return 2;
            if (Ticket::issue(0x80).covers("gondola")) return 3;
            if (Ticket::issue(0x80).code() != 0) return 4;
            if (Ticket::issue(0).covers("rope")) return 5;
            if (!Ticket::issue(0x40).covers("tram")) return 6;
            if (!Ticket::issue(0x7F).subset_of(Ticket::issue(0x7F))) return 7;
            if (Ticket::issue(0x08).subset_of(Ticket::issue(0x07))) return 8;
            return 0;
            """,
            "normalized value semantics with cover and subset relations",
            "comparing raw codes or keeping foreign bits at issue",
            "foreign-contaminated issues, subset relations, unknown lift names, and empty passes",
            "relational queries over normalized masks",
            "value type with operator==, operator<, arithmetic, or formatting helpers",
        ),
        c(
            "f26flg-datacenter-rack-pdus",
            "Datacenter rack PDUs",
            "rack_pdus",
            """
            class PduModel {
            public:
                static std::optional<PduModel> create(const std::vector<std::pair<std::string, std::uint32_t>>& outlets, unsigned width);
                std::uint32_t confine(std::uint32_t raw) const;
                bool complete(std::uint32_t raw) const;
                unsigned width() const;
            };
            """,
            """
            class PduModel {
            public:
                static std::optional<PduModel> create(const std::vector<std::pair<std::string, std::uint32_t>>& outlets, unsigned width);
                std::uint32_t confine(std::uint32_t raw) const;
                bool complete(std::uint32_t raw) const;
                unsigned width() const;
            private:
                PduModel(std::vector<std::pair<std::string, std::uint32_t>> outlets, unsigned width, std::uint32_t known);
                std::vector<std::pair<std::string, std::uint32_t>> outlets_;
                unsigned width_;
                std::uint32_t known_;
            };
            """,
            """
            std::optional<PduModel> PduModel::create(const std::vector<std::pair<std::string, std::uint32_t>>& outlets, unsigned width) {
                if (width == 0 || width > 16 || outlets.empty() || outlets.size() > 16) return std::nullopt;
                const std::uint32_t boundary = std::uint32_t{1} << width;
                std::uint64_t seen = 0;
                for (std::size_t i = 0; i < outlets.size(); ++i) {
                    const std::uint32_t bit = outlets[i].second;
                    if (outlets[i].first.empty() || bit == 0 || (bit & (bit - 1)) != 0 || bit >= boundary) return std::nullopt;
                    if ((seen & bit) != 0) return std::nullopt;
                    seen |= bit;
                    for (std::size_t j = 0; j < i; ++j) {
                        if (outlets[j].first == outlets[i].first) return std::nullopt;
                    }
                }
                return PduModel(outlets, width, static_cast<std::uint32_t>(seen));
            }
            PduModel::PduModel(std::vector<std::pair<std::string, std::uint32_t>> outlets, unsigned width, std::uint32_t known)
                : outlets_(std::move(outlets)), width_(width), known_(known) {}
            std::uint32_t PduModel::confine(std::uint32_t raw) const {
                const std::uint32_t within = raw & ((std::uint32_t{1} << width_) - 1u);
                return within & known_;
            }
            bool PduModel::complete(std::uint32_t raw) const { return confine(raw) == raw; }
            unsigned PduModel::width() const { return width_; }
            """,
            """
            std::optional<PduModel> PduModel::create(const std::vector<std::pair<std::string, std::uint32_t>>& outlets, unsigned width) {
                if (width == 0 || width > 16 || outlets.empty() || outlets.size() > 16) return std::nullopt;
                std::uint64_t seen = 0;
                for (std::size_t i = 0; i < outlets.size(); ++i) {
                    const std::uint32_t bit = outlets[i].second;
                    if (outlets[i].first.empty() || bit == 0 || (bit & (bit - 1)) != 0) return std::nullopt;
                    if ((seen & bit) != 0) return std::nullopt;
                    seen |= bit;
                    for (std::size_t j = 0; j < i; ++j) {
                        if (outlets[j].first == outlets[i].first) return std::nullopt;
                    }
                }
                return PduModel(outlets, width, static_cast<std::uint32_t>(seen));
            }
            PduModel::PduModel(std::vector<std::pair<std::string, std::uint32_t>> outlets, unsigned width, std::uint32_t known)
                : outlets_(std::move(outlets)), width_(width), known_(known) {}
            std::uint32_t PduModel::confine(std::uint32_t raw) const {
                const std::uint32_t within = raw & ((std::uint32_t{1} << width_) - 1u);
                return within & known_;
            }
            bool PduModel::complete(std::uint32_t raw) const { return confine(raw) == raw; }
            unsigned PduModel::width() const { return width_; }
            """,
            """
            auto model = PduModel::create({{"main_a", 1}, {"main_b", 2}, {"ups", 4}}, 4);
            if (!model) return 1;
            if (model->confine(0x1F) != 0x07) return 2;
            if (!model->complete(0x07) || model->complete(0x08)) return 3;
            if (model->width() != 4) return 4;
            return 0;
            """,
            """
            if (PduModel::create({{"main_a", 16}}, 4)) return 1;
            if (PduModel::create({{"main_a", 1}}, 0)) return 2;
            if (PduModel::create({{"main_a", 1}}, 17)) return 3;
            if (PduModel::create({{"main_a", 3}}, 4)) return 4;
            if (PduModel::create({{"main_a", 1}, {"main_a", 2}}, 4)) return 5;
            if (PduModel::create({{"main_a", 1}, {"main_b", 1}}, 4)) return 6;
            auto model = PduModel::create({{"main_a", 1}, {"main_b", 2}, {"ups", 4}}, 4);
            if (!model) return 7;
            if (model->confine(0x08) != 0) return 8;
            if (model->confine(0xF0) != 0) return 9;
            if (model->complete(0x0F)) return 10;
            if (!model->complete(0x05)) return 11;
            return 0;
            """,
            "caller-declared width boundary with table validation and confine/complete queries",
            "accepting outlet bits beyond the declared width",
            "over-width bits, bad widths, duplicate names and bits, in-width unknown bits, and completeness",
            "caller-declared boundary width as policy",
            "injected flag-table/policy object",
            project_support=True,
        ),
        c(
            "f26flg-farm-irrigation-zones",
            "Farm irrigation zones",
            "irrigation_zones",
            """
            struct WateringReport {
                std::uint32_t active;
                std::uint64_t out_of_range;
                bool within_bounds;
            };
            WateringReport reconcile(std::uint64_t raw);
            """,
            """
            struct WateringReport {
                std::uint32_t active;
                std::uint64_t out_of_range;
                bool within_bounds;
            };
            WateringReport reconcile(std::uint64_t raw);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kZones[] = {
                {"north", 1u}, {"south", 2u}, {"east", 4u}, {"west", 8u},
                {"orchard", 16u}, {"vineyard", 32u}, {"pasture", 64u}, {"cropland", 128u},
                {"greenhouse", 256u}, {"nursery", 512u}, {"meadow", 1024u}, {"wetland", 2048u},
            };
            }  // namespace
            WateringReport reconcile(std::uint64_t raw) {
                const std::uint64_t known = f26flg_detail::known_mask(kZones, 12);
                const std::uint32_t active = static_cast<std::uint32_t>(raw & known);
                const std::uint64_t dropped = raw & ~known;
                return {active, dropped, dropped == 0};
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kZones[] = {
                {"north", 1u}, {"south", 2u}, {"east", 4u}, {"west", 8u},
                {"orchard", 16u}, {"vineyard", 32u}, {"pasture", 64u}, {"cropland", 128u},
                {"greenhouse", 256u}, {"nursery", 512u}, {"meadow", 1024u}, {"wetland", 2048u},
            };
            }  // namespace
            WateringReport reconcile(std::uint64_t raw) {
                const std::uint64_t known = f26flg_detail::known_mask(kZones, 12);
                const std::uint32_t narrowed = static_cast<std::uint32_t>(raw);
                const std::uint32_t active = narrowed & static_cast<std::uint32_t>(known);
                const std::uint32_t dropped = narrowed & ~static_cast<std::uint32_t>(known);
                return {active, dropped, dropped == 0};
            }
            """,
            """
            auto report = reconcile(0x05);
            if (report.active != 0x05 || report.out_of_range != 0 || !report.within_bounds) return 1;
            if (!reconcile(0).within_bounds) return 2;
            return 0;
            """,
            """
            auto report = reconcile(std::uint64_t{1} << 40);
            if (report.active != 0 || report.out_of_range != (std::uint64_t{1} << 40) || report.within_bounds) return 1;
            auto mixed = reconcile(0x0FFFu | (std::uint64_t{1} << 63));
            if (mixed.active != 0x0FFF) return 2;
            if (mixed.out_of_range != (std::uint64_t{1} << 63)) return 3;
            if (mixed.within_bounds) return 4;
            auto low = reconcile(0x3000);
            if (low.active != 0 || low.out_of_range != 0x3000 || low.within_bounds) return 5;
            if (!reconcile(0x0FFF).within_bounds) return 6;
            return 0;
            """,
            "wide-input reconciliation against a twelve-bit zone mask with no truncation",
            "narrowing the wide input before accounting for out-of-range bits",
            "bit 40 and bit 63 inputs, exact out-of-range values, low foreign bits, and full masks",
            "wide-input boundary accounting",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26flg-theater-stage-cues",
            "Theater stage cues",
            "stage_cues",
            """
            class CueStack {
            public:
                bool push(std::uint32_t raw_cues);
                std::uint32_t pending() const;
                std::uint32_t dropped() const;
                std::optional<std::uint32_t> take_pending();
            };
            """,
            """
            class CueStack {
            public:
                bool push(std::uint32_t raw_cues);
                std::uint32_t pending() const;
                std::uint32_t dropped() const;
                std::optional<std::uint32_t> take_pending();
            private:
                std::uint32_t pending_ = 0;
                std::uint32_t dropped_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kCues[] = {
                {"lights", 1u}, {"sound", 2u}, {"curtain", 4u}, {"props", 8u},
                {"orchestra", 16u}, {"spotlight", 32u}, {"fog", 64u}, {"turntable", 128u},
            };
            }  // namespace
            bool CueStack::push(std::uint32_t raw_cues) {
                if (raw_cues == 0) return false;
                pending_ |= raw_cues & 0xFFu;
                dropped_ |= raw_cues & ~0xFFu;
                return true;
            }
            std::uint32_t CueStack::pending() const { return pending_; }
            std::uint32_t CueStack::dropped() const { return dropped_; }
            std::optional<std::uint32_t> CueStack::take_pending() {
                if (pending_ == 0) return std::nullopt;
                const std::uint32_t out = pending_;
                pending_ = 0;
                return out;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kCues[] = {
                {"lights", 1u}, {"sound", 2u}, {"curtain", 4u}, {"props", 8u},
                {"orchestra", 16u}, {"spotlight", 32u}, {"fog", 64u}, {"turntable", 128u},
            };
            }  // namespace
            bool CueStack::push(std::uint32_t raw_cues) {
                if (raw_cues == 0) return false;
                pending_ |= raw_cues & 0xFFu;
                dropped_ |= raw_cues & ~0xFFFFu;
                return true;
            }
            std::uint32_t CueStack::pending() const { return pending_; }
            std::uint32_t CueStack::dropped() const { return dropped_; }
            std::optional<std::uint32_t> CueStack::take_pending() {
                if (pending_ == 0) return std::nullopt;
                const std::uint32_t out = pending_;
                pending_ = 0;
                return out;
            }
            """,
            """
            CueStack stack;
            if (!stack.push(0x05) || stack.pending() != 0x05 || stack.dropped() != 0) return 1;
            if (stack.push(0)) return 2;
            auto taken = stack.take_pending();
            if (!taken || *taken != 0x05 || stack.pending() != 0) return 3;
            if (stack.take_pending() != std::nullopt) return 4;
            return 0;
            """,
            """
            CueStack stack;
            if (!stack.push(0x1A5)) return 1;
            if (stack.pending() != 0xA5) return 2;
            if (stack.dropped() != 0x100) return 3;
            if (!stack.push(0x200) || stack.dropped() != 0x300) return 4;
            auto taken = stack.take_pending();
            if (!taken || *taken != 0xA5) return 5;
            if (stack.dropped() != 0x300) return 6;
            if (stack.take_pending() != std::nullopt) return 7;
            return 0;
            """,
            "push-based accumulation with an eight-bit boundary and a draining take",
            "wrong-width drop accounting",
            "foreign-bit pushes, dropped surviving takes, drained pending, and empty pushes",
            "drain semantics with boundary accounting",
            "streaming accumulator, iterator, or incremental writer",
            project_support=True,
        ),
        c(
            "f26flg-airport-gate-assignments",
            "Airport gate assignments",
            "gate_assignments",
            """
            class GateError : public std::domain_error {
            public:
                explicit GateError(const std::string& message) : std::domain_error(message) {}
            };
            std::uint32_t sanitize(std::uint32_t requested);
            std::vector<std::string> terminals(std::uint32_t sanitized);
            """,
            """
            class GateError : public std::domain_error {
            public:
                explicit GateError(const std::string& message) : std::domain_error(message) {}
            };
            std::uint32_t sanitize(std::uint32_t requested);
            std::vector<std::string> terminals(std::uint32_t sanitized);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kTerminals[] = {
                {"terminal_a", 1u}, {"terminal_b", 2u}, {"terminal_c", 4u},
                {"commuter", 8u}, {"international", 16u}, {"cargo", 32u},
            };
            }  // namespace
            std::uint32_t sanitize(std::uint32_t requested) {
                if (requested == 0) throw GateError("at least one terminal is required");
                return requested & 0x3Fu;
            }
            std::vector<std::string> terminals(std::uint32_t sanitized) {
                return f26flg_detail::ordered_names(kTerminals, 6, sanitized & 0x3Fu);
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kTerminals[] = {
                {"terminal_a", 1u}, {"terminal_b", 2u}, {"terminal_c", 4u},
                {"commuter", 8u}, {"international", 16u}, {"cargo", 32u},
            };
            }  // namespace
            std::uint32_t sanitize(std::uint32_t requested) {
                return requested & 0x3Fu;
            }
            std::vector<std::string> terminals(std::uint32_t sanitized) {
                return f26flg_detail::ordered_names(kTerminals, 6, sanitized & 0x3Fu);
            }
            """,
            """
            if (sanitize(0x09) != 0x09) return 1;
            if (terminals(0x09) != std::vector<std::string>({"terminal_a", "commuter"})) return 2;
            if (sanitize(0x7F) != 0x3F) return 3;
            return 0;
            """,
            """
            bool threw = false;
            try {
                (void)sanitize(0);
            } catch (const GateError&) {
                threw = true;
            }
            if (!threw) return 1;
            if (sanitize(0x40) != 0) return 2;
            if (!terminals(0x40).empty()) return 3;
            if (terminals(0x3F).size() != 6) return 4;
            if (terminals(0x3F).front() != "terminal_a" || terminals(0x3F).back() != "cargo") return 5;
            if (sanitize(0xFFFFFFC1u) != 0x01) return 6;
            return 0;
            """,
            "empty-request rejection plus normalization and table-ordered listing",
            "converting empty requests to zero masks",
            "the zero throw, foreign-only requests, full listings, and wide masks",
            "guard-clause exception behavior before normalization",
            "exception-throwing policy object or service class",
        ),
        c(
            "f26flg-submarine-ballast-tanks",
            "Submarine ballast tanks",
            "ballast_tanks",
            """
            class Tanks {
            public:
                static Tanks flood(std::uint32_t mask);
                Tanks merge(const Tanks& other) const;
                Tanks vent(const Tanks& other) const;
                bool balanced() const;
                std::uint32_t mask() const;
            };
            """,
            """
            class Tanks {
            public:
                static Tanks flood(std::uint32_t mask);
                Tanks merge(const Tanks& other) const;
                Tanks vent(const Tanks& other) const;
                bool balanced() const;
                std::uint32_t mask() const;
            private:
                explicit Tanks(std::uint32_t mask);
                std::uint32_t mask_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kTanks[] = {
                {"forward", 1u}, {"aft", 2u}, {"port", 4u}, {"starboard", 8u}, {"trim", 16u},
            };
            }  // namespace
            Tanks::Tanks(std::uint32_t mask) : mask_(mask & 0x1Fu) {}
            Tanks Tanks::flood(std::uint32_t mask) { return Tanks(mask); }
            Tanks Tanks::merge(const Tanks& other) const { return Tanks(mask_ | other.mask_); }
            Tanks Tanks::vent(const Tanks& other) const { return Tanks(mask_ & ~other.mask_); }
            bool Tanks::balanced() const { return mask_ == 0 || mask_ == 0x1Fu; }
            std::uint32_t Tanks::mask() const { return mask_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kTanks[] = {
                {"forward", 1u}, {"aft", 2u}, {"port", 4u}, {"starboard", 8u}, {"trim", 16u},
            };
            }  // namespace
            Tanks::Tanks(std::uint32_t mask) : mask_(mask) {}
            Tanks Tanks::flood(std::uint32_t mask) { return Tanks(mask); }
            Tanks Tanks::merge(const Tanks& other) const { return Tanks(mask_ | other.mask_); }
            Tanks Tanks::vent(const Tanks& other) const { return Tanks(mask_ & ~other.mask_); }
            bool Tanks::balanced() const { return mask_ == 0 || mask_ == 0x1Fu; }
            std::uint32_t Tanks::mask() const { return mask_; }
            """,
            """
            auto tanks = Tanks::flood(0x05);
            if (tanks.balanced()) return 1;
            if (!Tanks::flood(0x1F).balanced()) return 2;
            if (tanks.merge(Tanks::flood(0x1A)).mask() != 0x1F) return 3;
            if (tanks.vent(Tanks::flood(0x01)).mask() != 0x04) return 4;
            return 0;
            """,
            """
            if (!Tanks::flood(0x3F).balanced()) return 1;
            if (Tanks::flood(0x20).mask() != 0) return 2;
            if (!Tanks::flood(0x20).balanced()) return 3;
            if (!Tanks::flood(0x0F).merge(Tanks::flood(0x10)).balanced()) return 4;
            if (Tanks::flood(0x1F).vent(Tanks::flood(0x01)).balanced()) return 5;
            if (Tanks::flood(0x1F).vent(Tanks::flood(0x1F)).mask() != 0) return 6;
            if (!Tanks::flood(0x1F).vent(Tanks::flood(0x1F)).balanced()) return 7;
            return 0;
            """,
            "normalized value type with union, difference, and an all-or-none invariant",
            "balancing raw masks with foreign bits attached",
            "foreign-contaminated floods, all-or-none balance, and vent-to-empty transitions",
            "invariant queries over normalized masks",
            "value type with operator==, operator<, arithmetic, or formatting helpers",
        ),
        c(
            "f26flg-winery-cellar-barrels",
            "Winery cellar barrels",
            "cellar_barrels",
            """
            class Cellar {
            public:
                bool rack(std::string_view barrel);
                std::uint32_t traditional() const;
                std::uint32_t modern() const;
                std::size_t racked() const;
                void reset();
            };
            """,
            """
            class Cellar {
            public:
                bool rack(std::string_view barrel);
                std::uint32_t traditional() const;
                std::uint32_t modern() const;
                std::size_t racked() const;
                void reset();
            private:
                std::uint32_t racked_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kBarrels[] = {
                {"oak", 1u}, {"chestnut", 2u}, {"acacia", 4u},
                {"cherry", 8u}, {"mulberry", 16u}, {"steel", 32u},
            };
            }  // namespace
            bool Cellar::rack(std::string_view barrel) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kBarrels, 6, barrel, bit)) return false;
                racked_ = static_cast<std::uint32_t>(racked_ | bit);
                return true;
            }
            std::uint32_t Cellar::traditional() const { return racked_ & 0x0Fu; }
            std::uint32_t Cellar::modern() const { return racked_ & 0x30u; }
            std::size_t Cellar::racked() const { return f26flg_detail::count_bits(racked_); }
            void Cellar::reset() { racked_ = 0; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kBarrels[] = {
                {"oak", 1u}, {"chestnut", 2u}, {"acacia", 4u},
                {"cherry", 8u}, {"mulberry", 16u}, {"steel", 32u},
            };
            }  // namespace
            bool Cellar::rack(std::string_view barrel) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kBarrels, 6, barrel, bit)) return false;
                racked_ = static_cast<std::uint32_t>(racked_ | bit);
                return true;
            }
            std::uint32_t Cellar::traditional() const { return racked_ & 0x1Fu; }
            std::uint32_t Cellar::modern() const { return racked_ & 0x20u; }
            std::size_t Cellar::racked() const { return f26flg_detail::count_bits(racked_); }
            void Cellar::reset() { racked_ = 0; }
            """,
            """
            Cellar cellar;
            if (!cellar.rack("oak") || !cellar.rack("steel")) return 1;
            if (cellar.traditional() != 0x01 || cellar.modern() != 0x20) return 2;
            if (cellar.racked() != 2) return 3;
            cellar.reset();
            if (cellar.racked() != 0 || cellar.traditional() != 0) return 4;
            return 0;
            """,
            """
            Cellar cellar;
            if (cellar.rack("plastic")) return 1;
            if (!cellar.rack("mulberry")) return 2;
            if (cellar.traditional() != 0) return 3;
            if (cellar.modern() != 0x10) return 4;
            if (!cellar.rack("cherry") || !cellar.rack("acacia")) return 5;
            if (cellar.traditional() != 0x0C) return 6;
            if (cellar.racked() != 3) return 7;
            cellar.reset();
            if (cellar.modern() != 0 || cellar.racked() != 0) return 8;
            return 0;
            """,
            "named subset constants with name-validated racking and subset projections",
            "wrong subset boundaries between traditional and modern barrels",
            "each subset racked, unknown barrels, racked counts, and reset",
            "named-subset masking directly teaching flag-set naming",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-courier-route-options",
            "Courier route options",
            "courier_options",
            """
            struct RoutePolicy {
                bool allow_duplicates;
            };
            std::optional<std::uint32_t> encode(const std::vector<std::string>& names, RoutePolicy policy);
            std::vector<std::string> decode(std::uint32_t code);
            """,
            """
            struct RoutePolicy {
                bool allow_duplicates;
            };
            std::optional<std::uint32_t> encode(const std::vector<std::string>& names, RoutePolicy policy);
            std::vector<std::string> decode(std::uint32_t code);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kOptions[] = {
                {"express", 1u}, {"insured", 2u}, {"fragile", 4u}, {"refrigerated", 8u},
                {"signature", 16u}, {"saturday", 32u}, {"bulk", 64u},
            };
            }  // namespace
            std::optional<std::uint32_t> encode(const std::vector<std::string>& names, RoutePolicy policy) {
                std::uint32_t code = 0;
                for (const std::string& name : names) {
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kOptions, 7, name, bit)) return std::nullopt;
                    if (!policy.allow_duplicates && (code & bit) != 0) return std::nullopt;
                    code = static_cast<std::uint32_t>(code | bit);
                }
                return code;
            }
            std::vector<std::string> decode(std::uint32_t code) {
                return f26flg_detail::ordered_names(kOptions, 7, code & 0x7Fu);
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kOptions[] = {
                {"express", 1u}, {"insured", 2u}, {"fragile", 4u}, {"refrigerated", 8u},
                {"signature", 16u}, {"saturday", 32u}, {"bulk", 64u},
            };
            }  // namespace
            std::optional<std::uint32_t> encode(const std::vector<std::string>& names, RoutePolicy policy) {
                std::uint32_t code = 0;
                for (const std::string& name : names) {
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kOptions, 7, name, bit)) continue;
                    if (!policy.allow_duplicates && (code & bit) != 0) return std::nullopt;
                    code = static_cast<std::uint32_t>(code | bit);
                }
                return code;
            }
            std::vector<std::string> decode(std::uint32_t code) {
                return f26flg_detail::ordered_names(kOptions, 7, code & 0x7Fu);
            }
            """,
            """
            auto code = encode({"express", "signature"}, {false});
            if (!code || *code != 0x11) return 1;
            if (decode(0x11) != std::vector<std::string>({"express", "signature"})) return 2;
            if (decode(0xFF).size() != 7) return 3;
            return 0;
            """,
            """
            if (encode({"express", "overnight"}, {true})) return 1;
            if (encode({"express", "express"}, {false})) return 2;
            auto twice = encode({"express", "express"}, {true});
            if (!twice || *twice != 0x01) return 3;
            auto empty = encode({}, {false});
            if (!empty || *empty != 0) return 4;
            if (!decode(0x80).empty()) return 5;
            if (decode(0x41) != std::vector<std::string>({"express", "bulk"})) return 6;
            if (encode({"Fragile"}, {true})) return 7;
            return 0;
            """,
            "policy-driven name encoding with duplicate rules and normalized decoding",
            "skipping unknown option names during encoding",
            "unknown names under both policies, duplicates under both policies, empty lists, foreign decode bits, and case decoys",
            "policy-parameterized parsing",
            "injected flag-table/policy object",
        ),
        c(
            "f26flg-library-member-privileges",
            "Library member privileges",
            "member_privileges",
            """
            class PrivilegeError : public std::invalid_argument {
            public:
                explicit PrivilegeError(const std::string& message) : std::invalid_argument(message) {}
            };
            std::uint32_t parse_card(std::string_view text);
            std::string format_card(std::uint32_t privileges);
            """,
            """
            class PrivilegeError : public std::invalid_argument {
            public:
                explicit PrivilegeError(const std::string& message) : std::invalid_argument(message) {}
            };
            std::uint32_t parse_card(std::string_view text);
            std::string format_card(std::uint32_t privileges);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kPrivileges[] = {
                {"borrowing", 1u}, {"renewal", 2u}, {"interlibrary", 4u}, {"reference", 8u},
                {"archives", 16u}, {"media", 32u}, {"study_rooms", 64u}, {"printing", 128u},
            };
            }  // namespace
            std::uint32_t parse_card(std::string_view text) {
                if (text.empty()) return 0;
                std::uint32_t privileges = 0;
                for (std::string_view token : f26flg_detail::split_keep_empty(text, ',')) {
                    if (token.empty()) throw PrivilegeError("empty privilege token");
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kPrivileges, 8, token, bit)) throw PrivilegeError("unknown privilege");
                    if ((privileges & bit) != 0) throw PrivilegeError("duplicate privilege");
                    privileges = static_cast<std::uint32_t>(privileges | bit);
                }
                return privileges;
            }
            std::string format_card(std::uint32_t privileges) {
                auto names = f26flg_detail::ordered_names(kPrivileges, 8, privileges & 0xFFu);
                if (names.empty()) return "none";
                return f26flg_detail::join_names(names, ",");
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kPrivileges[] = {
                {"borrowing", 1u}, {"renewal", 2u}, {"interlibrary", 4u}, {"reference", 8u},
                {"archives", 16u}, {"media", 32u}, {"study_rooms", 64u}, {"printing", 128u},
            };
            }  // namespace
            std::uint32_t parse_card(std::string_view text) {
                if (text.empty()) return 0;
                std::uint32_t privileges = 0;
                for (std::string_view token : f26flg_detail::split_keep_empty(text, ',')) {
                    if (token.empty()) throw PrivilegeError("empty privilege token");
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kPrivileges, 8, token, bit)) throw PrivilegeError("unknown privilege");
                    privileges = static_cast<std::uint32_t>(privileges | bit);
                }
                return privileges;
            }
            std::string format_card(std::uint32_t privileges) {
                auto names = f26flg_detail::ordered_names(kPrivileges, 8, privileges & 0xFFu);
                if (names.empty()) return "none";
                return f26flg_detail::join_names(names, ",");
            }
            """,
            """
            if (parse_card("borrowing,media") != 0x21) return 1;
            if (format_card(0x21) != "borrowing,media") return 2;
            if (parse_card("") != 0) return 3;
            if (format_card(0) != "none") return 4;
            return 0;
            """,
            """
            bool threw = false;
            try {
                (void)parse_card("media,media");
            } catch (const PrivilegeError&) {
                threw = true;
            }
            if (!threw) return 1;
            threw = false;
            try {
                (void)parse_card("borrowing,gaming");
            } catch (const PrivilegeError&) {
                threw = true;
            }
            if (!threw) return 2;
            threw = false;
            try {
                (void)parse_card("borrowing,");
            } catch (const PrivilegeError&) {
                threw = true;
            }
            if (!threw) return 3;
            threw = false;
            try {
                (void)parse_card(" borrowing");
            } catch (const PrivilegeError&) {
                threw = true;
            }
            if (!threw) return 4;
            if (format_card(0x1FF) != "borrowing,renewal,interlibrary,reference,archives,media,study_rooms,printing") return 5;
            if (parse_card("printing,borrowing") != 0x81) return 6;
            if (format_card(0x100) != "none") return 7;
            return 0;
            """,
            "strict tokenized parsing with duplicate detection and canonical formatting",
            "lenient token cleanup or accepting duplicate privileges",
            "duplicate, unknown, trailing-delimiter, and whitespace tokens; canonical round trips; foreign format bits",
            "strict text-to-mask parsing discipline",
            "exception-throwing policy object or service class",
        ),
        c(
            "f26flg-climbing-wall-route-holds",
            "Climbing wall route holds",
            "route_holds",
            """
            class HoldSet {
            public:
                static std::optional<HoldSet> from_names(const std::vector<std::string>& names);
                static HoldSet from_code(std::uint32_t code);
                std::vector<std::string> names() const;
                std::uint32_t code() const;
                friend bool operator==(const HoldSet& left, const HoldSet& right) { return left.mask_ == right.mask_; }
            };
            """,
            """
            class HoldSet {
            public:
                static std::optional<HoldSet> from_names(const std::vector<std::string>& names);
                static HoldSet from_code(std::uint32_t code);
                std::vector<std::string> names() const;
                std::uint32_t code() const;
                friend bool operator==(const HoldSet& left, const HoldSet& right) { return left.mask_ == right.mask_; }
            private:
                explicit HoldSet(std::uint32_t mask);
                std::uint32_t mask_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kHolds[] = {
                {"jug", 1u}, {"crimp", 2u}, {"sloper", 4u}, {"pinch", 8u}, {"pocket", 16u},
                {"edge", 32u}, {"undercling", 64u}, {"sidepull", 128u}, {"gaston", 256u},
            };
            }  // namespace
            HoldSet::HoldSet(std::uint32_t mask) : mask_(mask) {}
            std::optional<HoldSet> HoldSet::from_names(const std::vector<std::string>& names) {
                std::uint32_t mask = 0;
                for (const std::string& name : names) {
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kHolds, 9, name, bit)) return std::nullopt;
                    mask = static_cast<std::uint32_t>(mask | bit);
                }
                return HoldSet(mask);
            }
            HoldSet HoldSet::from_code(std::uint32_t code) { return HoldSet(code & 0x1FFu); }
            std::vector<std::string> HoldSet::names() const {
                return f26flg_detail::ordered_names(kHolds, 9, mask_);
            }
            std::uint32_t HoldSet::code() const { return mask_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kHolds[] = {
                {"jug", 1u}, {"crimp", 2u}, {"sloper", 4u}, {"pinch", 8u}, {"pocket", 16u},
                {"edge", 32u}, {"undercling", 64u}, {"sidepull", 128u}, {"gaston", 256u},
            };
            }  // namespace
            HoldSet::HoldSet(std::uint32_t mask) : mask_(mask) {}
            std::optional<HoldSet> HoldSet::from_names(const std::vector<std::string>& names) {
                std::uint32_t mask = 0;
                for (const std::string& name : names) {
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kHolds, 9, name, bit)) {
                        mask |= 0x80000000u;
                        continue;
                    }
                    mask = static_cast<std::uint32_t>(mask | bit);
                }
                return HoldSet(mask);
            }
            HoldSet HoldSet::from_code(std::uint32_t code) { return HoldSet(code & 0x1FFu); }
            std::vector<std::string> HoldSet::names() const {
                return f26flg_detail::ordered_names(kHolds, 9, mask_);
            }
            std::uint32_t HoldSet::code() const { return mask_; }
            """,
            """
            auto route = HoldSet::from_names({"jug", "crimp"});
            if (!route || route->code() != 0x03) return 1;
            if (route->names() != std::vector<std::string>({"jug", "crimp"})) return 2;
            if (HoldSet::from_code(0x1FF).names().size() != 9) return 3;
            return 0;
            """,
            """
            if (HoldSet::from_names({"jug", "heel_hook"})) return 1;
            if (HoldSet::from_names({"Jug"})) return 2;
            auto route = HoldSet::from_names({"gaston", "jug"});
            if (!route || route->code() != 0x101) return 3;
            if (route->names() != std::vector<std::string>({"jug", "gaston"})) return 4;
            if (HoldSet::from_code(0x200).code() != 0) return 5;
            if (!(HoldSet::from_code(0x3FF) == HoldSet::from_code(0x1FF))) return 6;
            auto none = HoldSet::from_names({});
            if (!none || none->code() != 0 || !none->names().empty()) return 7;
            if (HoldSet::from_code(0x05).names() != std::vector<std::string>({"jug", "sloper"})) return 8;
            return 0;
            """,
            "two construction paths with name validation and normalized codes",
            "inventing bits for unknown hold names",
            "unknown and case-decoy names, table-ordered output, foreign codes, and equality",
            "dual-construction value semantics",
            "value type with operator==, operator<, arithmetic, or formatting helpers",
        ),
        c(
            "f26flg-pharmacy-compound-ingredients",
            "Pharmacy compound ingredients",
            "compound_ingredients",
            """
            struct ParsePolicy {
                bool allow_duplicates;
                char delimiter;
            };
            std::optional<std::uint32_t> parse(std::string_view text, ParsePolicy policy);
            """,
            """
            struct ParsePolicy {
                bool allow_duplicates;
                char delimiter;
            };
            std::optional<std::uint32_t> parse(std::string_view text, ParsePolicy policy);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kIngredients[] = {
                {"base", 1u}, {"binder", 2u}, {"active", 4u}, {"preservative", 8u},
                {"coloring", 16u}, {"flavoring", 32u}, {"coating", 64u}, {"filler", 128u},
            };
            }  // namespace
            std::optional<std::uint32_t> parse(std::string_view text, ParsePolicy policy) {
                if (policy.delimiter != ',' && policy.delimiter != ';' && policy.delimiter != '|') return std::nullopt;
                if (text.empty()) return 0;
                std::uint32_t mask = 0;
                for (std::string_view token : f26flg_detail::split_keep_empty(text, policy.delimiter)) {
                    if (token.empty()) return std::nullopt;
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kIngredients, 8, token, bit)) return std::nullopt;
                    if (!policy.allow_duplicates && (mask & bit) != 0) return std::nullopt;
                    mask = static_cast<std::uint32_t>(mask | bit);
                }
                return mask;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kIngredients[] = {
                {"base", 1u}, {"binder", 2u}, {"active", 4u}, {"preservative", 8u},
                {"coloring", 16u}, {"flavoring", 32u}, {"coating", 64u}, {"filler", 128u},
            };
            }  // namespace
            std::optional<std::uint32_t> parse(std::string_view text, ParsePolicy policy) {
                (void)policy;
                if (text.empty()) return 0;
                std::uint32_t mask = 0;
                std::string current;
                auto flush = [&]() -> bool {
                    if (current.empty()) return false;
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kIngredients, 8, current, bit)) return false;
                    mask = static_cast<std::uint32_t>(mask | bit);
                    current.clear();
                    return true;
                };
                for (char c : text) {
                    if ((c >= 'a' && c <= 'z') || c == '_') {
                        current.push_back(c);
                        continue;
                    }
                    if (!flush()) return std::nullopt;
                }
                if (!flush()) return std::nullopt;
                return mask;
            }
            """,
            """
            auto mask = parse("base;active", {false, ';'});
            if (!mask || *mask != 0x05) return 1;
            if (parse("", {false, ','}) != std::optional<std::uint32_t>(0)) return 2;
            if (parse("base|binder", {true, '|'}) != std::optional<std::uint32_t>(0x03)) return 3;
            return 0;
            """,
            """
            if (parse("base.binder", {true, ';'})) return 1;
            if (parse("base,binder", {true, ';'})) return 2;
            if (parse("base;base", {false, ';'})) return 3;
            if (parse("base;base", {true, ';'}) != std::optional<std::uint32_t>(0x01)) return 4;
            if (parse("base;", {true, ';'})) return 5;
            if (parse("sugar;base", {true, ';'})) return 6;
            if (parse("coating", {false, ':'})) return 7;
            if (parse("coloring;flavoring", {false, ';'}) != std::optional<std::uint32_t>(0x30)) return 8;
            return 0;
            """,
            "delimiter-validated token parsing with a duplicate policy",
            "splitting on arbitrary punctuation or ignoring the declared delimiter",
            "wrong and unsupported delimiters, trailing delimiters, duplicates under both policies, and unknown tokens",
            "policy-bound lexical parsing",
            "injected flag-table/policy object",
            project_support=True,
        ),
        c(
            "f26flg-pavilion-roof-panels",
            "Pavilion roof panels",
            "pavilion_panels",
            """
            class PanelWriter {
            public:
                void offer(std::uint32_t panel_code);
                std::string render();
                bool rendered() const;
            };
            """,
            """
            class PanelWriter {
            public:
                void offer(std::uint32_t panel_code);
                std::string render();
                bool rendered() const;
            private:
                std::uint32_t accumulated_ = 0;
                bool rendered_ = false;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kPanels[] = {
                {"north", 1u}, {"northeast", 2u}, {"southeast", 4u},
                {"south", 8u}, {"southwest", 16u}, {"northwest", 32u},
            };
            }  // namespace
            void PanelWriter::offer(std::uint32_t panel_code) {
                accumulated_ |= panel_code & 0x3Fu;
            }
            std::string PanelWriter::render() {
                rendered_ = true;
                auto names = f26flg_detail::ordered_names(kPanels, 6, accumulated_);
                accumulated_ = 0;
                if (names.empty()) return "panels: none";
                return "panels: " + f26flg_detail::join_names(names, ",");
            }
            bool PanelWriter::rendered() const { return rendered_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kPanels[] = {
                {"north", 1u}, {"northeast", 2u}, {"southeast", 4u},
                {"south", 8u}, {"southwest", 16u}, {"northwest", 32u},
            };
            }  // namespace
            void PanelWriter::offer(std::uint32_t panel_code) {
                accumulated_ |= panel_code & 0x3Fu;
            }
            std::string PanelWriter::render() {
                rendered_ = true;
                auto names = f26flg_detail::ordered_names(kPanels, 6, accumulated_);
                if (names.empty()) return "panels: none";
                return "panels: " + f26flg_detail::join_names(names, ",");
            }
            bool PanelWriter::rendered() const { return rendered_; }
            """,
            """
            PanelWriter writer;
            if (writer.rendered()) return 1;
            writer.offer(0x03);
            writer.offer(0x40);
            if (writer.render() != "panels: north,northeast") return 2;
            if (!writer.rendered()) return 3;
            return 0;
            """,
            """
            PanelWriter writer;
            writer.offer(0x05);
            if (writer.render() != "panels: north,southeast") return 1;
            if (writer.render() != "panels: none") return 2;
            writer.offer(0x3F);
            if (writer.render() != "panels: north,northeast,southeast,south,southwest,northwest") return 3;
            writer.offer(0xC0);
            if (writer.render() != "panels: none") return 4;
            if (!writer.rendered()) return 5;
            return 0;
            """,
            "accumulating writer with a draining render and exact prefixed output",
            "repeatable renders of the same offer",
            "double renders, foreign-only offers, full masks, and exact output strings",
            "draining-stream semantics and exact output shape",
            "streaming accumulator, iterator, or incremental writer",
            project_support=True,
        ),
        c(
            "f26flg-tournament-match-awards",
            "Tournament match awards",
            "match_awards",
            """
            class AwardError : public std::logic_error {
            public:
                explicit AwardError(const std::string& message) : std::logic_error(message) {}
            };
            std::uint32_t podium_of(std::uint32_t earned);
            bool champion(std::uint32_t earned);
            std::uint32_t promote(std::uint32_t earned);
            """,
            """
            class AwardError : public std::logic_error {
            public:
                explicit AwardError(const std::string& message) : std::logic_error(message) {}
            };
            std::uint32_t podium_of(std::uint32_t earned);
            bool champion(std::uint32_t earned);
            std::uint32_t promote(std::uint32_t earned);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kAwards[] = {
                {"participation", 1u}, {"bronze", 2u}, {"silver", 4u}, {"gold", 8u},
                {"mvp", 16u}, {"sportsmanship", 32u}, {"comeback", 64u}, {"perfection", 128u},
            };
            }  // namespace
            std::uint32_t podium_of(std::uint32_t earned) { return earned & 0x0Eu; }
            bool champion(std::uint32_t earned) { return (earned & 0x08u) != 0; }
            std::uint32_t promote(std::uint32_t earned) {
                if ((earned & ~0xFFu) != 0) throw AwardError("unregistered award bits");
                if ((earned & 0x08u) != 0) return earned;
                if ((earned & 0x04u) != 0) return (earned & ~0x04u) | 0x08u;
                if ((earned & 0x02u) != 0) return (earned & ~0x02u) | 0x04u;
                return earned;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kAwards[] = {
                {"participation", 1u}, {"bronze", 2u}, {"silver", 4u}, {"gold", 8u},
                {"mvp", 16u}, {"sportsmanship", 32u}, {"comeback", 64u}, {"perfection", 128u},
            };
            }  // namespace
            std::uint32_t podium_of(std::uint32_t earned) { return earned & 0x0Eu; }
            bool champion(std::uint32_t earned) { return (earned & 0x08u) != 0; }
            std::uint32_t promote(std::uint32_t earned) {
                if ((earned & ~0xFFu) != 0) throw AwardError("unregistered award bits");
                if ((earned & 0x08u) != 0) return earned;
                if ((earned & 0x04u) != 0) return (earned & ~0x04u) | 0x08u;
                if ((earned & 0x02u) != 0) return (earned & ~0x02u) | 0x08u;
                return earned;
            }
            """,
            """
            if (podium_of(0x1E) != 0x0E) return 1;
            if (!champion(0x08) || champion(0x04)) return 2;
            if (promote(0x04) != 0x08) return 3;
            if (promote(0x08) != 0x08) return 4;
            return 0;
            """,
            """
            if (promote(0x02) != 0x04) return 1;
            if (promote(0x01) != 0x01) return 2;
            if (promote(0x12) != 0x14) return 3;
            bool threw = false;
            try {
                (void)promote(0x100);
            } catch (const AwardError&) {
                threw = true;
            }
            if (!threw) return 4;
            if (podium_of(0xF1) != 0) return 5;
            if (!champion(0x88)) return 6;
            if (promote(0x06) != 0x0A) return 7;
            return 0;
            """,
            "named podium subset projection plus a one-step promotion lattice with a typed foreign-bit error",
            "skipping lattice steps during promotion",
            "single-step promotions, carried non-podium awards, foreign-bit throws, and podium projection",
            "named subsets with state-transition rules",
            "exception-throwing policy object or service class",
        ),
        c(
            "f26flg-pizzeria-shift-roles",
            "Pizzeria shift roles",
            "pizzeria_shifts",
            """
            class ShiftBoard {
            public:
                bool assign(std::string_view role);
                bool kitchen_covered() const;
                std::vector<std::string> missing_kitchen() const;
                std::uint32_t outside() const;
                void reset();
            };
            """,
            """
            class ShiftBoard {
            public:
                bool assign(std::string_view role);
                bool kitchen_covered() const;
                std::vector<std::string> missing_kitchen() const;
                std::uint32_t outside() const;
                void reset();
            private:
                std::uint32_t staffed_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kRoles[] = {
                {"dough", 1u}, {"sauce", 2u}, {"toppings", 4u}, {"oven", 8u},
                {"delivery", 16u}, {"register", 32u}, {"prep", 64u},
            };
            }  // namespace
            bool ShiftBoard::assign(std::string_view role) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kRoles, 7, role, bit)) return false;
                staffed_ = static_cast<std::uint32_t>(staffed_ | bit);
                return true;
            }
            bool ShiftBoard::kitchen_covered() const { return (staffed_ & 0x4Fu) == 0x4Fu; }
            std::vector<std::string> ShiftBoard::missing_kitchen() const {
                std::vector<std::string> missing;
                for (const auto& entry : kRoles) {
                    if ((entry.bit & 0x4Fu) != 0 && (staffed_ & entry.bit) == 0) missing.emplace_back(entry.name);
                }
                return missing;
            }
            std::uint32_t ShiftBoard::outside() const { return staffed_ & ~0x4Fu; }
            void ShiftBoard::reset() { staffed_ = 0; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kRoles[] = {
                {"dough", 1u}, {"sauce", 2u}, {"toppings", 4u}, {"oven", 8u},
                {"delivery", 16u}, {"register", 32u}, {"prep", 64u},
            };
            }  // namespace
            bool ShiftBoard::assign(std::string_view role) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kRoles, 7, role, bit)) return false;
                staffed_ = static_cast<std::uint32_t>(staffed_ | bit);
                return true;
            }
            bool ShiftBoard::kitchen_covered() const { return staffed_ == 0x4Fu; }
            std::vector<std::string> ShiftBoard::missing_kitchen() const {
                std::vector<std::string> missing;
                for (const auto& entry : kRoles) {
                    if ((entry.bit & 0x4Fu) != 0 && (staffed_ & entry.bit) == 0) missing.emplace_back(entry.name);
                }
                return missing;
            }
            std::uint32_t ShiftBoard::outside() const { return staffed_ & ~0x4Fu; }
            void ShiftBoard::reset() { staffed_ = 0; }
            """,
            """
            ShiftBoard board;
            for (const char* role : {"dough", "sauce", "toppings", "oven", "prep"}) {
                if (!board.assign(role)) return 1;
            }
            if (!board.kitchen_covered()) return 2;
            if (!board.missing_kitchen().empty()) return 3;
            board.reset();
            if (board.kitchen_covered()) return 4;
            return 0;
            """,
            """
            ShiftBoard board;
            if (board.assign("accounting")) return 1;
            if (!board.assign("delivery")) return 2;
            if (board.outside() != 0x10) return 3;
            if (board.kitchen_covered()) return 4;
            for (const char* role : {"dough", "sauce", "toppings", "oven", "prep"}) {
                if (!board.assign(role)) return 5;
            }
            if (!board.kitchen_covered()) return 6;
            if (!board.missing_kitchen().empty()) return 7;
            if (board.outside() != 0x10) return 8;
            ShiftBoard partial;
            if (!partial.assign("dough") || !partial.assign("oven")) return 9;
            if (partial.missing_kitchen() != std::vector<std::string>({"sauce", "toppings", "prep"})) return 10;
            if (partial.kitchen_covered()) return 11;
            return 0;
            """,
            "named kitchen-subset coverage with missing-role listing and outside-role accounting",
            "exact-mask equality used as coverage",
            "outside roles staffed first, partial kitchens, exact missing lists, and reset",
            "subset-coverage semantics with decoy roles",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-satellite-downlink-bands",
            "Satellite downlink bands",
            "downlink_bands",
            """
            class Bands {
            public:
                static Bands of(std::uint32_t bits);
                Bands unite(const Bands& other) const;
                Bands intersect(const Bands& other) const;
                Bands complement() const;
                bool empty() const;
                std::uint32_t bits() const;
                friend bool operator==(const Bands& left, const Bands& right) { return left.bits_ == right.bits_; }
            };
            """,
            """
            class Bands {
            public:
                static Bands of(std::uint32_t bits);
                Bands unite(const Bands& other) const;
                Bands intersect(const Bands& other) const;
                Bands complement() const;
                bool empty() const;
                std::uint32_t bits() const;
                friend bool operator==(const Bands& left, const Bands& right) { return left.bits_ == right.bits_; }
            private:
                explicit Bands(std::uint32_t bits);
                std::uint32_t bits_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kBands[] = {
                {"vhf", 1u}, {"uhf", 2u}, {"s_band", 4u}, {"x_band", 8u}, {"ka_band", 16u},
            };
            }  // namespace
            Bands::Bands(std::uint32_t bits) : bits_(bits & 0x1Fu) {}
            Bands Bands::of(std::uint32_t bits) { return Bands(bits); }
            Bands Bands::unite(const Bands& other) const { return Bands(bits_ | other.bits_); }
            Bands Bands::intersect(const Bands& other) const { return Bands(bits_ & other.bits_); }
            Bands Bands::complement() const { return Bands(0x1Fu & ~bits_); }
            bool Bands::empty() const { return bits_ == 0; }
            std::uint32_t Bands::bits() const { return bits_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kBands[] = {
                {"vhf", 1u}, {"uhf", 2u}, {"s_band", 4u}, {"x_band", 8u}, {"ka_band", 16u},
            };
            }  // namespace
            Bands::Bands(std::uint32_t bits) : bits_(bits) {}
            Bands Bands::of(std::uint32_t bits) { return Bands(bits); }
            Bands Bands::unite(const Bands& other) const { return Bands(bits_ | other.bits_); }
            Bands Bands::intersect(const Bands& other) const { return Bands(bits_ & other.bits_); }
            Bands Bands::complement() const { return Bands(~bits_); }
            bool Bands::empty() const { return bits_ == 0; }
            std::uint32_t Bands::bits() const { return bits_; }
            """,
            """
            auto bands = Bands::of(0x03);
            if (bands.unite(Bands::of(0x04)).bits() != 0x07) return 1;
            if (bands.intersect(Bands::of(0x02)).bits() != 0x02) return 2;
            if (bands.empty() || !Bands::of(0).empty()) return 3;
            if (!(Bands::of(0x05) == Bands::of(0x05))) return 4;
            return 0;
            """,
            """
            if (Bands::of(0x03).complement().bits() != 0x1C) return 1;
            if (Bands::of(0x1F).complement().bits() != 0) return 2;
            if (!Bands::of(0x1F).complement().empty()) return 3;
            if (Bands::of(0).complement().bits() != 0x1F) return 4;
            if (Bands::of(0x20).bits() != 0) return 5;
            if (!(Bands::of(0x3F) == Bands::of(0x1F))) return 6;
            if (Bands::of(0x01).unite(Bands::of(0x20)).bits() != 0x01) return 7;
            if (Bands::of(0x10).complement().intersect(Bands::of(0x18)).bits() != 0x08) return 8;
            return 0;
            """,
            "normalized set algebra with a complement bounded to the band plan",
            "an unbounded bitwise-not complement with raw storage",
            "bounded complements, foreign-bit construction, algebra chains, and empty checks",
            "bounded-complement discipline teaching mask boundaries",
            "value type with operator==, operator<, arithmetic, or formatting helpers",
        ),
        c(
            "f26flg-coffee-menu-modifiers",
            "Coffee menu modifiers",
            "coffee_modifiers",
            """
            class OrderBuilder {
            public:
                bool add(std::string_view modifier);
                bool remove(std::string_view modifier);
                std::uint32_t code() const;
                std::string ticket() const;
            };
            """,
            """
            class OrderBuilder {
            public:
                bool add(std::string_view modifier);
                bool remove(std::string_view modifier);
                std::uint32_t code() const;
                std::string ticket() const;
            private:
                std::uint32_t mask_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kModifiers[] = {
                {"oat_milk", 1u}, {"extra_shot", 2u}, {"syrup", 4u}, {"whipped", 8u},
                {"iced", 16u}, {"decaf", 32u}, {"large", 64u}, {"spice", 128u},
            };
            }  // namespace
            bool OrderBuilder::add(std::string_view modifier) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModifiers, 8, modifier, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool OrderBuilder::remove(std::string_view modifier) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModifiers, 8, modifier, bit)) return false;
                if ((mask_ & bit) == 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            std::uint32_t OrderBuilder::code() const { return mask_; }
            std::string OrderBuilder::ticket() const {
                return "[" + f26flg_detail::join_names(f26flg_detail::ordered_names(kModifiers, 8, mask_), "+") + "]";
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kModifiers[] = {
                {"oat_milk", 1u}, {"extra_shot", 2u}, {"syrup", 4u}, {"whipped", 8u},
                {"iced", 16u}, {"decaf", 32u}, {"large", 64u}, {"spice", 128u},
            };
            }  // namespace
            bool OrderBuilder::add(std::string_view modifier) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModifiers, 8, modifier, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool OrderBuilder::remove(std::string_view modifier) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModifiers, 8, modifier, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            std::uint32_t OrderBuilder::code() const { return mask_; }
            std::string OrderBuilder::ticket() const {
                return "[" + f26flg_detail::join_names(f26flg_detail::ordered_names(kModifiers, 8, mask_), "+") + "]";
            }
            """,
            """
            OrderBuilder order;
            if (!order.add("oat_milk") || !order.add("iced")) return 1;
            if (order.code() != 0x11) return 2;
            if (order.ticket() != "[oat_milk+iced]") return 3;
            if (!order.remove("iced") || order.code() != 0x01) return 4;
            if (order.ticket() != "[oat_milk]") return 5;
            return 0;
            """,
            """
            OrderBuilder order;
            if (order.remove("decaf")) return 1;
            if (order.add("almond_milk")) return 2;
            if (order.code() != 0) return 3;
            if (!order.add("syrup")) return 4;
            if (order.add("syrup")) return 5;
            if (!order.remove("syrup")) return 6;
            if (order.ticket() != "[]") return 7;
            if (!order.add("spice") || !order.add("large") || !order.add("decaf")) return 8;
            if (order.ticket() != "[decaf+large+spice]") return 9;
            if (order.code() != 0xE0) return 10;
            return 0;
            """,
            "presence-guarded add and remove with exact bracketed rendering",
            "idempotent blind removals reported as success",
            "absent removes, unknown names, duplicate adds, exact ticket strings, and table ordering",
            "guarded mutation rules with exact output",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-glacier-survey-markers",
            "Glacier survey markers",
            "glacier_markers",
            """
            class MarkerError : public std::domain_error {
            public:
                explicit MarkerError(const std::string& message) : std::domain_error(message) {}
            };
            std::uint32_t sequence(const std::vector<std::string>& ordered_markers);
            std::vector<std::string> markers_in_order(std::uint32_t code);
            """,
            """
            class MarkerError : public std::domain_error {
            public:
                explicit MarkerError(const std::string& message) : std::domain_error(message) {}
            };
            std::uint32_t sequence(const std::vector<std::string>& ordered_markers);
            std::vector<std::string> markers_in_order(std::uint32_t code);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kMarkers[] = {
                {"crevasse", 1u}, {"icefall", 2u}, {"moraine", 4u},
                {"serac", 8u}, {"nunatak", 16u}, {"bergschrund", 32u},
            };
            }  // namespace
            std::uint32_t sequence(const std::vector<std::string>& ordered_markers) {
                std::uint32_t code = 0;
                std::size_t last_index = 0;
                bool first = true;
                for (const std::string& name : ordered_markers) {
                    std::size_t index = 6;
                    for (std::size_t i = 0; i < 6; ++i) {
                        if (name == kMarkers[i].name) {
                            index = i;
                            break;
                        }
                    }
                    if (index == 6) throw MarkerError("unknown survey marker");
                    if (!first && index <= last_index) throw MarkerError("markers out of survey order");
                    last_index = index;
                    first = false;
                    code = static_cast<std::uint32_t>(code | kMarkers[index].bit);
                }
                return code;
            }
            std::vector<std::string> markers_in_order(std::uint32_t code) {
                return f26flg_detail::ordered_names(kMarkers, 6, code & 0x3Fu);
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kMarkers[] = {
                {"crevasse", 1u}, {"icefall", 2u}, {"moraine", 4u},
                {"serac", 8u}, {"nunatak", 16u}, {"bergschrund", 32u},
            };
            }  // namespace
            std::uint32_t sequence(const std::vector<std::string>& ordered_markers) {
                for (const std::string& name : ordered_markers) {
                    bool known = false;
                    for (const auto& entry : kMarkers) known = known || name == entry.name;
                    if (!known) throw MarkerError("unknown survey marker");
                }
                std::uint32_t code = 0;
                for (const auto& entry : kMarkers) {
                    for (const std::string& name : ordered_markers) {
                        if (name == entry.name) {
                            code = static_cast<std::uint32_t>(code | entry.bit);
                            break;
                        }
                    }
                }
                return code;
            }
            std::vector<std::string> markers_in_order(std::uint32_t code) {
                return f26flg_detail::ordered_names(kMarkers, 6, code & 0x3Fu);
            }
            """,
            """
            if (sequence({"crevasse", "serac"}) != 0x09) return 1;
            if (sequence({}) != 0) return 2;
            if (markers_in_order(0x09) != std::vector<std::string>({"crevasse", "serac"})) return 3;
            return 0;
            """,
            """
            bool threw = false;
            try {
                (void)sequence({"serac", "crevasse"});
            } catch (const MarkerError&) {
                threw = true;
            }
            if (!threw) return 1;
            threw = false;
            try {
                (void)sequence({"crevasse", "crevasse"});
            } catch (const MarkerError&) {
                threw = true;
            }
            if (!threw) return 2;
            threw = false;
            try {
                (void)sequence({"crevasse", "berg"});
            } catch (const MarkerError&) {
                threw = true;
            }
            if (!threw) return 3;
            if (sequence({"icefall", "moraine", "nunatak"}) != 0x16) return 4;
            if (markers_in_order(0x3F).size() != 6) return 5;
            if (!markers_in_order(0x40).empty()) return 6;
            if (sequence({"bergschrund"}) != 0x20) return 7;
            return 0;
            """,
            "order-validating sequence encoding with typed failures",
            "silently sorting caller input into table order",
            "out-of-order, duplicate, and unknown names; valid ordered sequences; foreign decode bits",
            "caller-order validation as a new ordering skill",
            "exception-throwing policy object or service class",
        ),
        c(
            "f26flg-night-train-car-classes",
            "Night train car classes",
            "night_train",
            """
            class Manifest {
            public:
                bool board(std::string_view car_class);
                bool leave(std::string_view car_class);
                std::size_t aboard() const;
                bool full_house() const;
                void reset();
            };
            """,
            """
            class Manifest {
            public:
                bool board(std::string_view car_class);
                bool leave(std::string_view car_class);
                std::size_t aboard() const;
                bool full_house() const;
                void reset();
            private:
                std::uint32_t mask_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kClasses[] = {
                {"economy", 1u}, {"standard", 2u}, {"business", 4u},
                {"first", 8u}, {"sleeper", 16u}, {"observation", 32u},
            };
            }  // namespace
            bool Manifest::board(std::string_view car_class) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kClasses, 6, car_class, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool Manifest::leave(std::string_view car_class) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kClasses, 6, car_class, bit)) return false;
                if ((mask_ & bit) == 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            std::size_t Manifest::aboard() const { return f26flg_detail::count_bits(mask_); }
            bool Manifest::full_house() const { return mask_ == 0x3Fu; }
            void Manifest::reset() { mask_ = 0; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kClasses[] = {
                {"economy", 1u}, {"standard", 2u}, {"business", 4u},
                {"first", 8u}, {"sleeper", 16u}, {"observation", 32u},
            };
            }  // namespace
            bool Manifest::board(std::string_view car_class) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kClasses, 6, car_class, bit)) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool Manifest::leave(std::string_view car_class) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kClasses, 6, car_class, bit)) return false;
                if ((mask_ & bit) == 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            std::size_t Manifest::aboard() const { return f26flg_detail::count_bits(mask_); }
            bool Manifest::full_house() const { return mask_ == 0x3Fu; }
            void Manifest::reset() { mask_ = 0; }
            """,
            """
            Manifest manifest;
            if (!manifest.board("economy") || !manifest.board("sleeper")) return 1;
            if (manifest.aboard() != 2) return 2;
            if (!manifest.leave("economy") || manifest.aboard() != 1) return 3;
            if (manifest.full_house()) return 4;
            manifest.reset();
            if (manifest.aboard() != 0) return 5;
            return 0;
            """,
            """
            Manifest manifest;
            if (manifest.board("lounge")) return 1;
            if (!manifest.board("economy")) return 2;
            if (manifest.board("economy")) return 3;
            if (manifest.leave("standard")) return 4;
            if (manifest.aboard() != 1) return 5;
            for (const char* name : {"standard", "business", "first", "sleeper", "observation"}) {
                if (!manifest.board(name)) return 6;
            }
            if (!manifest.full_house()) return 7;
            if (manifest.aboard() != 6) return 8;
            if (!manifest.leave("business") || manifest.full_house()) return 9;
            manifest.reset();
            if (manifest.full_house() || manifest.aboard() != 0) return 10;
            return 0;
            """,
            "presence-guarded boarding with popcount and capacity queries",
            "accepting duplicate boardings as successful operations",
            "duplicate and unknown boards, leaves of absent classes, full-house transitions, and reset",
            "occupancy-state discipline over a mask",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-robotics-arm-joints",
            "Robotics arm joints",
            "arm_joints",
            """
            class Controller {
            public:
                void engage(std::uint32_t joints);
                bool release(std::string_view joint);
                std::uint32_t engaged() const;
                std::optional<std::string> single() const;
            };
            """,
            """
            class Controller {
            public:
                void engage(std::uint32_t joints);
                bool release(std::string_view joint);
                std::uint32_t engaged() const;
                std::optional<std::string> single() const;
            private:
                std::uint32_t engaged_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kJoints[] = {
                {"base", 1u}, {"shoulder", 2u}, {"elbow", 4u},
                {"wrist", 8u}, {"gripper", 16u}, {"rotator", 32u},
            };
            }  // namespace
            void Controller::engage(std::uint32_t joints) {
                engaged_ |= joints & 0x3Fu;
            }
            bool Controller::release(std::string_view joint) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kJoints, 6, joint, bit)) return false;
                if ((engaged_ & bit) == 0) return false;
                engaged_ = static_cast<std::uint32_t>(engaged_ & ~bit);
                return true;
            }
            std::uint32_t Controller::engaged() const { return engaged_; }
            std::optional<std::string> Controller::single() const {
                if (engaged_ == 0 || (engaged_ & (engaged_ - 1)) != 0) return std::nullopt;
                return std::string(f26flg_detail::lookup_name(kJoints, 6, engaged_));
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kJoints[] = {
                {"base", 1u}, {"shoulder", 2u}, {"elbow", 4u},
                {"wrist", 8u}, {"gripper", 16u}, {"rotator", 32u},
            };
            }  // namespace
            void Controller::engage(std::uint32_t joints) {
                engaged_ |= joints & 0x3Fu;
            }
            bool Controller::release(std::string_view joint) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kJoints, 6, joint, bit)) return false;
                if ((engaged_ & bit) == 0) return false;
                engaged_ = static_cast<std::uint32_t>(engaged_ & ~bit);
                return true;
            }
            std::uint32_t Controller::engaged() const { return engaged_; }
            std::optional<std::string> Controller::single() const {
                if (engaged_ == 0) return std::nullopt;
                for (const auto& entry : kJoints) {
                    if ((engaged_ & entry.bit) != 0) return std::string(entry.name);
                }
                return std::nullopt;
            }
            """,
            """
            Controller arm;
            arm.engage(0x05);
            if (arm.engaged() != 0x05) return 1;
            if (!arm.release("elbow") || arm.engaged() != 0x01) return 2;
            auto single = arm.single();
            if (!single || *single != "base") return 3;
            if (!arm.release("base") || arm.single() != std::nullopt) return 4;
            return 0;
            """,
            """
            Controller arm;
            arm.engage(0x05);
            if (arm.single() != std::nullopt) return 1;
            arm.engage(0x40);
            if (arm.engaged() != 0x05) return 2;
            if (arm.release("hip")) return 3;
            if (arm.release("wrist")) return 4;
            if (!arm.release("base")) return 5;
            auto after = arm.single();
            if (!after || *after != "elbow") return 6;
            if (!arm.release("elbow")) return 7;
            arm.engage(0x20);
            auto single = arm.single();
            if (!single || *single != "rotator") return 8;
            return 0;
            """,
            "mask engagement with a power-of-two single-joint rule",
            "first-match reporting presented as a single engaged joint",
            "multiple engaged joints, foreign bits, unknown and unengaged releases, and exact single names",
            "exact-cardinality queries over masks",
            "stateful class with repeated calls and reset/clear semantics",
            project_support=True,
        ),
        c(
            "f26flg-fireworks-display-shells",
            "Fireworks display shells",
            "display_shells",
            """
            struct Salvo {
                std::uint32_t effects;
                std::size_t count;
                bool grand_finale;
            };
            Salvo plan_salvo(std::uint32_t requested);
            """,
            """
            struct Salvo {
                std::uint32_t effects;
                std::size_t count;
                bool grand_finale;
            };
            Salvo plan_salvo(std::uint32_t requested);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kEffects[] = {
                {"peony", 1u}, {"willow", 2u}, {"chrysanthemum", 4u}, {"brocade", 8u},
                {"strobe", 16u}, {"crackle", 32u}, {"waterfall", 64u},
            };
            }  // namespace
            Salvo plan_salvo(std::uint32_t requested) {
                const std::uint32_t effects = requested & 0x7Fu;
                return {effects, f26flg_detail::count_bits(effects), effects == 0x7Fu};
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kEffects[] = {
                {"peony", 1u}, {"willow", 2u}, {"chrysanthemum", 4u}, {"brocade", 8u},
                {"strobe", 16u}, {"crackle", 32u}, {"waterfall", 64u},
            };
            }  // namespace
            Salvo plan_salvo(std::uint32_t requested) {
                return {requested & 0x7Fu, f26flg_detail::count_bits(requested), requested == 0xFFu};
            }
            """,
            """
            auto salvo = plan_salvo(0x05);
            if (salvo.effects != 0x05 || salvo.count != 2 || salvo.grand_finale) return 1;
            auto finale = plan_salvo(0xFF);
            if (finale.effects != 0x7F || !finale.grand_finale) return 2;
            if (plan_salvo(0).count != 0 || plan_salvo(0).grand_finale) return 3;
            return 0;
            """,
            """
            auto finale = plan_salvo(0xFF);
            if (finale.count != 7) return 1;
            if (!plan_salvo(0x7F).grand_finale) return 2;
            auto noisy = plan_salvo(0x80);
            if (noisy.effects != 0 || noisy.count != 0 || noisy.grand_finale) return 3;
            if (plan_salvo(0x40).count != 1) return 4;
            auto partial = plan_salvo(0x3F);
            if (partial.grand_finale || partial.count != 6) return 5;
            if (plan_salvo(0xFFFF).count != 7) return 6;
            return 0;
            """,
            "normalized popcount with a full-set completion rule",
            "counting or comparing raw requested codes",
            "full requests with foreign bits, raw full-set requests, foreign-only requests, partial salvos, and wide masks",
            "completion checks decoupled from raw input",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26flg-carpentry-shop-tools",
            "Carpentry shop tools",
            "shop_tools",
            """
            class CheckoutLog {
            public:
                bool checkout(std::string_view tool);
                bool undo_last();
                std::uint32_t outstanding() const;
                std::vector<std::string> history() const;
            };
            """,
            """
            class CheckoutLog {
            public:
                bool checkout(std::string_view tool);
                bool undo_last();
                std::uint32_t outstanding() const;
                std::vector<std::string> history() const;
            private:
                std::uint32_t mask_ = 0;
                std::vector<std::string> order_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kTools[] = {
                {"saw", 1u}, {"plane", 2u}, {"chisel", 4u}, {"hammer", 8u}, {"drill", 16u},
                {"sander", 32u}, {"lathe", 64u}, {"router", 128u}, {"jigsaw", 256u}, {"grinder", 512u},
            };
            }  // namespace
            bool CheckoutLog::checkout(std::string_view tool) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kTools, 10, tool, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                order_.emplace_back(tool);
                return true;
            }
            bool CheckoutLog::undo_last() {
                if (order_.empty()) return false;
                const std::string last = order_.back();
                order_.pop_back();
                std::uint64_t bit = 0;
                (void)f26flg_detail::lookup_bit(kTools, 10, last, bit);
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return true;
            }
            std::uint32_t CheckoutLog::outstanding() const { return mask_; }
            std::vector<std::string> CheckoutLog::history() const { return order_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kTools[] = {
                {"saw", 1u}, {"plane", 2u}, {"chisel", 4u}, {"hammer", 8u}, {"drill", 16u},
                {"sander", 32u}, {"lathe", 64u}, {"router", 128u}, {"jigsaw", 256u}, {"grinder", 512u},
            };
            }  // namespace
            bool CheckoutLog::checkout(std::string_view tool) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kTools, 10, tool, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                order_.emplace_back(tool);
                return true;
            }
            bool CheckoutLog::undo_last() {
                if (order_.empty()) return false;
                order_.clear();
                mask_ = 0;
                return true;
            }
            std::uint32_t CheckoutLog::outstanding() const { return mask_; }
            std::vector<std::string> CheckoutLog::history() const { return order_; }
            """,
            """
            CheckoutLog log;
            if (!log.checkout("saw")) return 1;
            if (log.outstanding() != 0x01) return 2;
            if (!log.undo_last() || log.outstanding() != 0) return 3;
            if (!log.history().empty()) return 4;
            if (log.undo_last()) return 5;
            return 0;
            """,
            """
            CheckoutLog log;
            if (log.checkout("cnc")) return 1;
            if (!log.checkout("saw") || !log.checkout("drill") || !log.checkout("lathe")) return 2;
            if (log.checkout("drill")) return 3;
            if (!log.undo_last()) return 4;
            if (log.outstanding() != 0x11) return 5;
            if (log.history() != std::vector<std::string>({"saw", "drill"})) return 6;
            if (!log.undo_last() || log.outstanding() != 0x01) return 7;
            if (!log.checkout("lathe")) return 8;
            if (log.outstanding() != 0x41) return 9;
            if (!log.undo_last() || !log.undo_last() || log.undo_last()) return 10;
            if (log.outstanding() != 0 || !log.history().empty()) return 11;
            return 0;
            """,
            "insertion-tracked checkouts with single-step undo and outstanding masks",
            "clearing all state on a single undo",
            "duplicate checkouts, unknown tools, undo ordering, re-checkout after undo, and full drains",
            "undo semantics over flag state",
            "streaming accumulator, iterator, or incremental writer",
            project_support=True,
        ),
        c(
            "f26flg-api-gateway-features",
            "API gateway features",
            "gateway_features",
            """
            class TierSet {
            public:
                static std::optional<TierSet> define(const std::vector<std::pair<std::string, std::uint32_t>>& features, std::uint32_t standard_tier);
                bool within_standard(std::uint32_t active) const;
                std::vector<std::string> premium(std::uint32_t active) const;
                std::uint32_t standard() const;
            };
            """,
            """
            class TierSet {
            public:
                static std::optional<TierSet> define(const std::vector<std::pair<std::string, std::uint32_t>>& features, std::uint32_t standard_tier);
                bool within_standard(std::uint32_t active) const;
                std::vector<std::string> premium(std::uint32_t active) const;
                std::uint32_t standard() const;
            private:
                TierSet(std::vector<std::pair<std::string, std::uint32_t>> features, std::uint32_t standard_tier, std::uint32_t known);
                std::vector<std::pair<std::string, std::uint32_t>> features_;
                std::uint32_t standard_;
                std::uint32_t known_;
            };
            """,
            """
            std::optional<TierSet> TierSet::define(const std::vector<std::pair<std::string, std::uint32_t>>& features, std::uint32_t standard_tier) {
                if (features.empty() || features.size() > 10) return std::nullopt;
                std::uint64_t seen = 0;
                for (std::size_t i = 0; i < features.size(); ++i) {
                    const std::uint32_t bit = features[i].second;
                    if (features[i].first.empty() || bit == 0 || (bit & (bit - 1)) != 0 || bit > 0x200u) return std::nullopt;
                    if ((seen & bit) != 0) return std::nullopt;
                    seen |= bit;
                    for (std::size_t j = 0; j < i; ++j) {
                        if (features[j].first == features[i].first) return std::nullopt;
                    }
                }
                if (standard_tier == 0 || (standard_tier & ~seen) != 0) return std::nullopt;
                return TierSet(features, standard_tier, static_cast<std::uint32_t>(seen));
            }
            TierSet::TierSet(std::vector<std::pair<std::string, std::uint32_t>> features, std::uint32_t standard_tier, std::uint32_t known)
                : features_(std::move(features)), standard_(standard_tier), known_(known) {}
            bool TierSet::within_standard(std::uint32_t active) const {
                return (active & known_ & ~standard_) == 0;
            }
            std::vector<std::string> TierSet::premium(std::uint32_t active) const {
                std::vector<std::string> out;
                const std::uint32_t beyond = active & known_ & ~standard_;
                for (const auto& entry : features_) {
                    if ((beyond & entry.second) != 0) out.push_back(entry.first);
                }
                return out;
            }
            std::uint32_t TierSet::standard() const { return standard_; }
            """,
            """
            std::optional<TierSet> TierSet::define(const std::vector<std::pair<std::string, std::uint32_t>>& features, std::uint32_t standard_tier) {
                if (features.empty() || features.size() > 10) return std::nullopt;
                std::uint64_t seen = 0;
                for (std::size_t i = 0; i < features.size(); ++i) {
                    const std::uint32_t bit = features[i].second;
                    if (features[i].first.empty() || bit == 0 || (bit & (bit - 1)) != 0 || bit > 0x200u) return std::nullopt;
                    if ((seen & bit) != 0) return std::nullopt;
                    seen |= bit;
                    for (std::size_t j = 0; j < i; ++j) {
                        if (features[j].first == features[i].first) return std::nullopt;
                    }
                }
                return TierSet(features, standard_tier, static_cast<std::uint32_t>(seen));
            }
            TierSet::TierSet(std::vector<std::pair<std::string, std::uint32_t>> features, std::uint32_t standard_tier, std::uint32_t known)
                : features_(std::move(features)), standard_(standard_tier), known_(known) {}
            bool TierSet::within_standard(std::uint32_t active) const {
                return (active & known_ & ~standard_) == 0;
            }
            std::vector<std::string> TierSet::premium(std::uint32_t active) const {
                std::vector<std::string> out;
                const std::uint32_t beyond = active & known_ & ~standard_;
                for (const auto& entry : features_) {
                    if ((beyond & entry.second) != 0) out.push_back(entry.first);
                }
                return out;
            }
            std::uint32_t TierSet::standard() const { return standard_; }
            """,
            """
            auto tiers = TierSet::define({{"auth", 1}, {"logging", 2}, {"caching", 4}, {"tracing", 8}}, 0x03);
            if (!tiers) return 1;
            if (!tiers->within_standard(0x03)) return 2;
            if (tiers->within_standard(0x07)) return 3;
            if (tiers->premium(0x07) != std::vector<std::string>({"caching"})) return 4;
            if (tiers->standard() != 0x03) return 5;
            return 0;
            """,
            """
            if (TierSet::define({{"auth", 1}, {"logging", 2}}, 0x04)) return 1;
            if (TierSet::define({{"auth", 1}}, 0x00)) return 2;
            if (TierSet::define({{"auth", 3}}, 0x01)) return 3;
            if (TierSet::define({{"auth", 1}, {"auth", 2}}, 0x01)) return 4;
            if (TierSet::define({{"auth", 1}, {"logging", 1}}, 0x01)) return 5;
            if (TierSet::define({}, 0x00)) return 6;
            auto tiers = TierSet::define({{"auth", 1}, {"logging", 2}, {"caching", 4}, {"tracing", 8}}, 0x03);
            if (!tiers) return 7;
            if (!tiers->within_standard(0x13)) return 8;
            if (tiers->premium(0x1C) != std::vector<std::string>({"caching", "tracing"})) return 9;
            if (!tiers->premium(0x10).empty()) return 10;
            if (tiers->standard() != 0x03) return 11;
            return 0;
            """,
            "tier policy validated against the injected table with within/premium partition queries",
            "accepting tier bits outside the feature table",
            "out-of-table tiers, empty tiers, invalid tables, foreign active bits, and premium listings",
            "subset-validated policy objects",
            "injected flag-table/policy object",
            project_support=True,
        ),
        c(
            "f26flg-chess-club-titles",
            "Chess club titles",
            "club_titles",
            """
            class TitleCase {
            public:
                static TitleCase of(std::uint32_t bits);
                std::string highest() const;
                bool at_least(std::string_view title) const;
                std::uint32_t bits() const;
                friend bool operator==(const TitleCase& left, const TitleCase& right) { return left.bits_ == right.bits_; }
                friend bool operator<(const TitleCase& left, const TitleCase& right) { return left.bits_ < right.bits_; }
            };
            """,
            """
            class TitleCase {
            public:
                static TitleCase of(std::uint32_t bits);
                std::string highest() const;
                bool at_least(std::string_view title) const;
                std::uint32_t bits() const;
                friend bool operator==(const TitleCase& left, const TitleCase& right) { return left.bits_ == right.bits_; }
                friend bool operator<(const TitleCase& left, const TitleCase& right) { return left.bits_ < right.bits_; }
            private:
                explicit TitleCase(std::uint32_t bits);
                std::uint32_t bits_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kTitles[] = {
                {"novice", 1u}, {"club", 2u}, {"expert", 4u}, {"candidate_master", 8u},
                {"master", 16u}, {"international", 32u}, {"grandmaster", 64u}, {"legend", 128u},
            };
            }  // namespace
            TitleCase::TitleCase(std::uint32_t bits) : bits_(bits & 0xFFu) {}
            TitleCase TitleCase::of(std::uint32_t bits) { return TitleCase(bits); }
            std::string TitleCase::highest() const {
                for (std::size_t i = 8; i-- > 0;) {
                    if ((bits_ & kTitles[i].bit) != 0) return kTitles[i].name;
                }
                return "none";
            }
            bool TitleCase::at_least(std::string_view title) const {
                for (std::size_t i = 0; i < 8; ++i) {
                    if (title == kTitles[i].name) {
                        std::uint32_t threshold = 0;
                        for (std::size_t j = i; j < 8; ++j) threshold |= kTitles[j].bit;
                        return (bits_ & threshold) != 0;
                    }
                }
                return false;
            }
            std::uint32_t TitleCase::bits() const { return bits_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kTitles[] = {
                {"novice", 1u}, {"club", 2u}, {"expert", 4u}, {"candidate_master", 8u},
                {"master", 16u}, {"international", 32u}, {"grandmaster", 64u}, {"legend", 128u},
            };
            }  // namespace
            TitleCase::TitleCase(std::uint32_t bits) : bits_(bits & 0xFFu) {}
            TitleCase TitleCase::of(std::uint32_t bits) { return TitleCase(bits); }
            std::string TitleCase::highest() const {
                for (std::size_t i = 0; i < 8; ++i) {
                    if ((bits_ & kTitles[i].bit) != 0) return kTitles[i].name;
                }
                return "none";
            }
            bool TitleCase::at_least(std::string_view title) const {
                for (std::size_t i = 0; i < 8; ++i) {
                    if (title == kTitles[i].name) {
                        std::uint32_t threshold = 0;
                        for (std::size_t j = i; j < 8; ++j) threshold |= kTitles[j].bit;
                        return (bits_ & threshold) != 0;
                    }
                }
                return false;
            }
            std::uint32_t TitleCase::bits() const { return bits_; }
            """,
            """
            auto player = TitleCase::of(0x10);
            if (player.highest() != "master") return 1;
            if (!player.at_least("expert") || player.at_least("grandmaster")) return 2;
            if (TitleCase::of(0).highest() != "none") return 3;
            if (player.bits() != 0x10) return 4;
            return 0;
            """,
            """
            auto player = TitleCase::of(0x11);
            if (player.highest() != "master") return 1;
            if (TitleCase::of(0x83).highest() != "legend") return 2;
            if (TitleCase::of(0x100).highest() != "none") return 3;
            if (TitleCase::of(0x100).bits() != 0) return 4;
            if (!TitleCase::of(0x04).at_least("club")) return 5;
            if (TitleCase::of(0x04).at_least("candidate_master")) return 6;
            if (TitleCase::of(0x04).at_least("warden")) return 7;
            if (!(TitleCase::of(0x02) < TitleCase::of(0x40))) return 8;
            if (!TitleCase::of(0x80).at_least("novice")) return 9;
            if (TitleCase::of(0x01).highest() != "novice") return 10;
            return 0;
            """,
            "rank-threshold queries with normalized storage",
            "first-match or lowest-rank selection reported as the highest title",
            "mixed ranks, foreign bits, threshold queries, unknown titles, and ordering",
            "rank-threshold semantics over flags",
            "value type with operator==, operator<, arithmetic, or formatting helpers",
        ),
        c(
            "f26flg-space-station-modules",
            "Space station modules",
            "station_modules",
            """
            class Station {
            public:
                bool dock(std::string_view module);
                bool undock(std::string_view module);
                std::vector<std::string> docked() const;
                bool isolated() const;
                std::size_t cycles() const;
            };
            """,
            """
            class Station {
            public:
                bool dock(std::string_view module);
                bool undock(std::string_view module);
                std::vector<std::string> docked() const;
                bool isolated() const;
                std::size_t cycles() const;
            private:
                std::uint32_t mask_ = 0;
                std::size_t cycles_ = 0;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kModules[] = {
                {"habitat", 1u}, {"laboratory", 2u}, {"greenhouse", 4u}, {"dock", 8u},
                {"solar", 16u}, {"comms", 32u}, {"storage", 64u}, {"airlock", 128u},
            };
            }  // namespace
            bool Station::dock(std::string_view module) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModules, 8, module, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                ++cycles_;
                return true;
            }
            bool Station::undock(std::string_view module) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModules, 8, module, bit)) return false;
                if ((mask_ & bit) == 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                ++cycles_;
                return true;
            }
            std::vector<std::string> Station::docked() const {
                return f26flg_detail::ordered_names(kModules, 8, mask_);
            }
            bool Station::isolated() const { return mask_ == 0; }
            std::size_t Station::cycles() const { return cycles_; }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kModules[] = {
                {"habitat", 1u}, {"laboratory", 2u}, {"greenhouse", 4u}, {"dock", 8u},
                {"solar", 16u}, {"comms", 32u}, {"storage", 64u}, {"airlock", 128u},
            };
            }  // namespace
            bool Station::dock(std::string_view module) {
                ++cycles_;
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModules, 8, module, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                return true;
            }
            bool Station::undock(std::string_view module) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kModules, 8, module, bit)) return false;
                if ((mask_ & bit) == 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                ++cycles_;
                return true;
            }
            std::vector<std::string> Station::docked() const {
                return f26flg_detail::ordered_names(kModules, 8, mask_);
            }
            bool Station::isolated() const { return mask_ == 0; }
            std::size_t Station::cycles() const { return cycles_; }
            """,
            """
            Station station;
            if (!station.isolated()) return 1;
            if (!station.dock("habitat") || !station.dock("solar")) return 2;
            if (station.docked() != std::vector<std::string>({"habitat", "solar"})) return 3;
            if (station.cycles() != 2) return 4;
            if (!station.undock("habitat") || station.cycles() != 3) return 5;
            if (station.isolated()) return 6;
            return 0;
            """,
            """
            Station station;
            if (station.dock("lounge")) return 1;
            if (station.cycles() != 0) return 2;
            if (!station.dock("habitat")) return 3;
            if (station.dock("habitat")) return 4;
            if (station.cycles() != 1) return 5;
            if (station.undock("comms")) return 6;
            if (station.cycles() != 1) return 7;
            if (!station.dock("airlock") || !station.dock("comms")) return 8;
            if (station.docked() != std::vector<std::string>({"habitat", "comms", "airlock"})) return 9;
            if (station.isolated()) return 10;
            if (!station.undock("habitat") || !station.undock("comms") || !station.undock("airlock")) return 11;
            if (!station.isolated() || station.cycles() != 6) return 12;
            return 0;
            """,
            "presence-guarded docking with success-only operation accounting and table-ordered state",
            "counting failed attempts as cycles",
            "unknown and duplicate docks, undock of absent modules, cycle counts, ordering, and isolation",
            "attempt-versus-success accounting",
            "stateful class with repeated calls and reset/clear semantics",
        ),
        c(
            "f26flg-brewery-batch-additives",
            "Brewery batch additives",
            "batch_additives",
            """
            struct RecipeRule {
                std::uint32_t required_mask;
                std::size_t max_additives;
            };
            std::optional<std::uint32_t> recipe(const std::vector<std::string>& names, RecipeRule rule);
            bool balanced(std::uint32_t recipe_code, RecipeRule rule);
            """,
            """
            struct RecipeRule {
                std::uint32_t required_mask;
                std::size_t max_additives;
            };
            std::optional<std::uint32_t> recipe(const std::vector<std::string>& names, RecipeRule rule);
            bool balanced(std::uint32_t recipe_code, RecipeRule rule);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kAdditives[] = {
                {"hops", 1u}, {"malt", 2u}, {"yeast", 4u}, {"coriander", 8u},
                {"orange_peel", 16u}, {"honey", 32u}, {"oak_chips", 64u},
            };
            }  // namespace
            std::optional<std::uint32_t> recipe(const std::vector<std::string>& names, RecipeRule rule) {
                if ((rule.required_mask & ~0x7Fu) != 0 || rule.max_additives == 0 || rule.max_additives > 7) return std::nullopt;
                std::uint32_t code = 0;
                for (const std::string& name : names) {
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kAdditives, 7, name, bit)) return std::nullopt;
                    if ((code & bit) != 0) return std::nullopt;
                    code = static_cast<std::uint32_t>(code | bit);
                }
                if ((code & rule.required_mask) != rule.required_mask) return std::nullopt;
                if (f26flg_detail::count_bits(code) > rule.max_additives) return std::nullopt;
                return code;
            }
            bool balanced(std::uint32_t recipe_code, RecipeRule rule) {
                const std::uint32_t normalized = recipe_code & 0x7Fu;
                if ((normalized & rule.required_mask) != rule.required_mask) return false;
                const unsigned count = f26flg_detail::count_bits(normalized);
                return count >= 2 && count <= rule.max_additives;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kAdditives[] = {
                {"hops", 1u}, {"malt", 2u}, {"yeast", 4u}, {"coriander", 8u},
                {"orange_peel", 16u}, {"honey", 32u}, {"oak_chips", 64u},
            };
            }  // namespace
            std::optional<std::uint32_t> recipe(const std::vector<std::string>& names, RecipeRule rule) {
                if ((rule.required_mask & ~0x7Fu) != 0 || rule.max_additives == 0 || rule.max_additives > 7) return std::nullopt;
                std::uint32_t code = 0;
                for (const std::string& name : names) {
                    std::uint64_t bit = 0;
                    if (!f26flg_detail::lookup_bit(kAdditives, 7, name, bit)) return std::nullopt;
                    if ((code & bit) != 0) return std::nullopt;
                    code = static_cast<std::uint32_t>(code | bit);
                }
                if (f26flg_detail::count_bits(code) > rule.max_additives) return std::nullopt;
                return code;
            }
            bool balanced(std::uint32_t recipe_code, RecipeRule rule) {
                const std::uint32_t normalized = recipe_code & 0x7Fu;
                if ((normalized & rule.required_mask) != rule.required_mask) return false;
                const unsigned count = f26flg_detail::count_bits(normalized);
                return count >= 2 && count <= rule.max_additives;
            }
            """,
            """
            auto code = recipe({"hops", "yeast"}, {0x05, 4});
            if (!code || *code != 0x05) return 1;
            if (!balanced(0x05, {0x05, 4})) return 2;
            if (balanced(0x01, {0x05, 4})) return 3;
            return 0;
            """,
            """
            if (recipe({"coriander"}, {0x05, 4})) return 1;
            if (recipe({"hops", "yeast", "hops"}, {0x05, 4})) return 2;
            if (recipe({"hops", "yeast", "sugar"}, {0x05, 4})) return 3;
            if (recipe({"hops", "yeast", "coriander", "honey", "malt"}, {0x05, 4})) return 4;
            auto full = recipe({"hops", "yeast", "coriander", "honey"}, {0x05, 4});
            if (!full || *full != 0x2D) return 5;
            if (recipe({"hops", "yeast"}, {0x80, 4})) return 6;
            if (recipe({"hops", "yeast"}, {0x05, 0})) return 7;
            if (!balanced(0x85, {0x05, 4})) return 8;
            if (balanced(0x04, {0x05, 4})) return 9;
            if (!balanced(0x2D, {0x05, 4})) return 10;
            return 0;
            """,
            "rule-injected recipe validation with required-set and cardinality checks",
            "dropping the required-mask rule from recipe validation",
            "missing required additives, duplicates, unknowns, over-cap recipes, invalid rules, and balancing with foreign bits",
            "cross-flag constraint validation",
            "injected flag-table/policy object",
            project_support=True,
        ),
        c(
            "f26flg-mountain-hut-supplies",
            "Mountain hut supplies",
            "hut_supplies",
            """
            class Stockpile {
            public:
                bool deliver(std::string_view supply);
                std::optional<std::string> dispatch();
                std::uint32_t stock() const;
                std::size_t capacity_used() const;
            };
            """,
            """
            class Stockpile {
            public:
                bool deliver(std::string_view supply);
                std::optional<std::string> dispatch();
                std::uint32_t stock() const;
                std::size_t capacity_used() const;
            private:
                std::uint32_t mask_ = 0;
                std::vector<std::string> queue_;
            };
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSupplies[] = {
                {"firewood", 1u}, {"water", 2u}, {"blankets", 4u}, {"rations", 8u}, {"lanterns", 16u},
                {"medicine", 32u}, {"rope", 64u}, {"maps", 128u}, {"radio", 256u},
            };
            }  // namespace
            bool Stockpile::deliver(std::string_view supply) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSupplies, 9, supply, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                if (queue_.size() >= 4) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                queue_.emplace_back(supply);
                return true;
            }
            std::optional<std::string> Stockpile::dispatch() {
                if (queue_.empty()) return std::nullopt;
                const std::string first = queue_.front();
                queue_.erase(queue_.begin());
                std::uint64_t bit = 0;
                (void)f26flg_detail::lookup_bit(kSupplies, 9, first, bit);
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return first;
            }
            std::uint32_t Stockpile::stock() const { return mask_; }
            std::size_t Stockpile::capacity_used() const { return queue_.size(); }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kSupplies[] = {
                {"firewood", 1u}, {"water", 2u}, {"blankets", 4u}, {"rations", 8u}, {"lanterns", 16u},
                {"medicine", 32u}, {"rope", 64u}, {"maps", 128u}, {"radio", 256u},
            };
            }  // namespace
            bool Stockpile::deliver(std::string_view supply) {
                std::uint64_t bit = 0;
                if (!f26flg_detail::lookup_bit(kSupplies, 9, supply, bit)) return false;
                if ((mask_ & bit) != 0) return false;
                mask_ = static_cast<std::uint32_t>(mask_ | bit);
                queue_.emplace_back(supply);
                return true;
            }
            std::optional<std::string> Stockpile::dispatch() {
                if (queue_.empty()) return std::nullopt;
                const std::string first = queue_.front();
                queue_.erase(queue_.begin());
                std::uint64_t bit = 0;
                (void)f26flg_detail::lookup_bit(kSupplies, 9, first, bit);
                mask_ = static_cast<std::uint32_t>(mask_ & ~bit);
                return first;
            }
            std::uint32_t Stockpile::stock() const { return mask_; }
            std::size_t Stockpile::capacity_used() const { return queue_.size(); }
            """,
            """
            Stockpile pile;
            if (!pile.deliver("water") || !pile.deliver("rations")) return 1;
            if (pile.stock() != 0x0A || pile.capacity_used() != 2) return 2;
            auto first = pile.dispatch();
            if (!first || *first != "water") return 3;
            if (pile.stock() != 0x08 || pile.capacity_used() != 1) return 4;
            return 0;
            """,
            """
            Stockpile pile;
            if (pile.deliver("fuel")) return 1;
            if (pile.dispatch() != std::nullopt) return 2;
            if (!pile.deliver("firewood") || !pile.deliver("water") || !pile.deliver("blankets") || !pile.deliver("rations")) return 3;
            if (pile.deliver("lanterns")) return 4;
            if (pile.capacity_used() != 4) return 5;
            if (pile.deliver("firewood")) return 6;
            auto first = pile.dispatch();
            if (!first || *first != "firewood") return 7;
            if (!pile.deliver("lanterns")) return 8;
            if (pile.stock() != 0x1E) return 9;
            if (!pile.dispatch() || !pile.dispatch() || !pile.dispatch() || !pile.dispatch()) return 10;
            if (pile.dispatch() != std::nullopt || pile.stock() != 0 || pile.capacity_used() != 0) return 11;
            return 0;
            """,
            "capacity-bounded FIFO delivery with mask and queue views",
            "unbounded delivery past the declared capacity",
            "capacity bounds, duplicates, unknowns, dispatch order, room after dispatch, and full drains",
            "bounded FIFO semantics over flags",
            "streaming accumulator, iterator, or incremental writer",
            project_support=True,
        ),
        c(
            "f26flg-festival-stage-genres",
            "Festival stage genres",
            "festival_genres",
            """
            struct DaySplit {
                std::vector<std::string> main_stage;
                std::vector<std::string> side_stage;
            };
            DaySplit split_stages(std::uint32_t lineup);
            """,
            """
            struct DaySplit {
                std::vector<std::string> main_stage;
                std::vector<std::string> side_stage;
            };
            DaySplit split_stages(std::uint32_t lineup);
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kGenres[] = {
                {"folk", 4u}, {"jazz", 1u}, {"rock", 16u}, {"electronic", 2u},
                {"classical", 64u}, {"hiphop", 8u}, {"reggae", 128u}, {"blues", 32u},
            };
            }  // namespace
            DaySplit split_stages(std::uint32_t lineup) {
                const std::uint64_t known = f26flg_detail::known_mask(kGenres, 8);
                const std::uint32_t normalized = static_cast<std::uint32_t>(lineup & known);
                DaySplit split;
                for (std::size_t i = 0; i < 8; ++i) {
                    if ((normalized & kGenres[i].bit) == 0) continue;
                    if (i % 2 == 0) {
                        split.main_stage.emplace_back(kGenres[i].name);
                    } else {
                        split.side_stage.emplace_back(kGenres[i].name);
                    }
                }
                return split;
            }
            """,
            """
            namespace {
            constexpr f26flg_detail::NameBit kGenres[] = {
                {"folk", 4u}, {"jazz", 1u}, {"rock", 16u}, {"electronic", 2u},
                {"classical", 64u}, {"hiphop", 8u}, {"reggae", 128u}, {"blues", 32u},
            };
            }  // namespace
            DaySplit split_stages(std::uint32_t lineup) {
                const std::uint64_t known = f26flg_detail::known_mask(kGenres, 8);
                const std::uint32_t normalized = static_cast<std::uint32_t>(lineup & known);
                DaySplit split;
                for (unsigned position = 0; position < 8; ++position) {
                    const std::uint64_t bit = std::uint64_t{1} << position;
                    if ((normalized & bit) == 0) continue;
                    std::string_view name = f26flg_detail::lookup_name(kGenres, 8, bit);
                    if (name.empty()) continue;
                    if (position % 2 == 0) {
                        split.main_stage.emplace_back(name);
                    } else {
                        split.side_stage.emplace_back(name);
                    }
                }
                return split;
            }
            """,
            """
            auto split = split_stages(0x14);
            if (split.main_stage != std::vector<std::string>({"folk", "rock"})) return 1;
            if (!split.side_stage.empty()) return 2;
            if (!split_stages(0).main_stage.empty()) return 3;
            return 0;
            """,
            """
            auto split = split_stages(0xFF);
            if (split.main_stage != std::vector<std::string>({"folk", "rock", "classical", "reggae"})) return 1;
            if (split.side_stage != std::vector<std::string>({"jazz", "electronic", "hiphop", "blues"})) return 2;
            auto swapped = split_stages(0x01);
            if (!swapped.main_stage.empty() || swapped.side_stage != std::vector<std::string>({"jazz"})) return 3;
            auto foreign = split_stages(0x100);
            if (!foreign.main_stage.empty() || !foreign.side_stage.empty()) return 4;
            auto reggae = split_stages(0x80);
            if (reggae.main_stage != std::vector<std::string>({"reggae"})) return 5;
            return 0;
            """,
            "deterministic interleaved partition by declaration-index parity after normalization",
            "partitioning by bit-position parity",
            "full lineups, single genres, foreign bits, and the reggae parity decoy",
            "parity partitioning decoupled from bit values",
            "free function returning explicit result/audit struct",
        ),
    )
    return rows


CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-allergies-seven-dimension-artifacts-v1"
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

Implement a clean-room C++17 named bit-flag component for a local allergies
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
It must keep named-flag membership, declared list ordering, unknown-bit
handling, named subset boundaries, and state mutation deterministic and
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
                "source": "w8-biayn clean-room fixed26 allergies analog curriculum",
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
description = "{spec.title}: unknown names, foreign bits, ordering rules, and wrong-substitute rejection"

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
            "family": "allergies",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "allergies",
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
    text = re.sub(r"\bf26flg[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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
        "schema_version": "fixed26-allergies-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-flag-fresh-") as temporary:
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
        "schema_version": "fixed26-allergies-core-v1",
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
for task_root in sorted(ROOT.glob("f26flg-*")):
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
            "schema_version": "fixed26-allergies-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-flag-docker-") as temporary:
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
        "schema_version": "fixed26-allergies-docker-sanity-v1",
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
        "schema_version": "fixed26-allergies-creator-preflight-v1",
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
        "capability": "fixed26-allergies-analog",
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
            "task": "implement clean-room fixed26 allergies analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "membership against normalized masks; declared list ordering; unknown names rejected through declared channels; unknown bits masked, counted, or rejected as documented",
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
            "target_family": "allergies",
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
