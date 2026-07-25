"""Create and verify the fixed-26 all-your-base clean-room analog batch.

The generated roots are local Aider-format candidates only.  This owner never
creates JSONL, token/mask evidence, exports, training runs, or benchmark-uplift
claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

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
SPEC_DOCUMENT = REPO_ROOT / "docs/aider-synthetic/aider-fixed26-analogs/fixed26-b001-all-your-base.md"
DEFAULT_OUT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1/aider-fixed26-analogs/fixed26-b001-all-your-base"
LEGACY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks"
REVERIFY_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-reverify"
EXPANSION_ROOT = REPO_ROOT / ".w8-biayn/data/aider-tasks-expansion-v1"
HOLDOUT_ROOT = REPO_ROOT / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
BENCHMARK_MANIFEST = REPO_ROOT / "manifests/aider_sft/aider-polyglot-cpp-26.json"
OWNER = "src/w8_biayn/integrations/moonlight_fixed26_radix_analogs_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_fixed26_radix_analogs_aider_tasks.py"
CREATION_PROMPT = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
IMPLEMENTATION_PROMPT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
BATCH_ID = "fixed26-b001-all-your-base"
FAMILY_ID = "aider-fixed26-all-your-base-analogs-v1"
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
        "f26rad-symbol-table-bounds",
        "f26rad-field-width-authority",
        "f26rad-capability-negotiator",
        "f26rad-sensor-glyph-ranges",
        "f26rad-cargo-sparse-digits",
        "f26rad-token-bank-digits",
        "f26rad-transponder-digit-order",
        "f26rad-padding-preserve-width",
        "f26rad-canonical-vector-form",
        "f26rad-wide-accumulator-quote",
        "f26rad-limb-route-counter",
        "f26rad-decimal-crosscheck-buckets",
        "f26rad-power-table-budget",
        "f26rad-stateful-converter-cache",
        "f26rad-format-roundtrip-journal",
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
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>
"""


COMMON_SOURCE = r"""
#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <sstream>

namespace f26rad_detail {
[[maybe_unused]] int digit36(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'Z') return c - 'A' + 10;
    return -1;
}
[[maybe_unused]] bool checked_mul_add(std::uint64_t value, unsigned radix, unsigned digit, std::uint64_t limit, std::uint64_t& out) {
    if (digit > limit) return false;
    if (radix < 2 || value > (limit - digit) / radix) return false;
    out = value * radix + digit;
    return true;
}
[[maybe_unused]] std::optional<std::uint64_t> parse_text(std::string_view text, unsigned radix, bool reject_leading = true, std::uint64_t limit = std::numeric_limits<std::uint64_t>::max(), unsigned min_radix = 2, unsigned max_radix = 36) {
    if (radix < min_radix || radix > max_radix || text.empty()) return std::nullopt;
    if (reject_leading && text.size() > 1 && text.front() == '0') return std::nullopt;
    std::uint64_t value = 0;
    for (char c : text) {
        int raw = digit36(c);
        if (raw < 0 || static_cast<unsigned>(raw) >= radix) return std::nullopt;
        std::uint64_t next = 0;
        if (!checked_mul_add(value, radix, static_cast<unsigned>(raw), limit, next)) return std::nullopt;
        value = next;
    }
    return value;
}
[[maybe_unused]] std::string format_value(std::uint64_t value, unsigned radix) {
    if (radix < 2 || radix > 36) return {};
    const char* alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    std::string out;
    do {
        out.push_back(alphabet[value % radix]);
        value /= radix;
    } while (value != 0);
    std::reverse(out.begin(), out.end());
    return out;
}
[[maybe_unused]] std::vector<unsigned> digits_of(std::uint64_t value, unsigned radix, std::size_t width = 0) {
    std::vector<unsigned> out;
    do {
        out.push_back(static_cast<unsigned>(value % radix));
        value /= radix;
    } while (value != 0);
    while (out.size() < width) out.push_back(0);
    std::reverse(out.begin(), out.end());
    return out;
}
[[maybe_unused]] std::optional<std::uint64_t> parse_digits(const std::vector<unsigned>& digits, unsigned radix, bool reject_leading = true, std::uint64_t limit = std::numeric_limits<std::uint64_t>::max()) {
    if (radix < 2 || radix > 64 || digits.empty()) return std::nullopt;
    if (reject_leading && digits.size() > 1 && digits.front() == 0) return std::nullopt;
    std::uint64_t value = 0;
    for (unsigned digit : digits) {
        if (digit >= radix) return std::nullopt;
        std::uint64_t next = 0;
        if (!checked_mul_add(value, radix, digit, limit, next)) return std::nullopt;
        value = next;
    }
    return value;
}
[[maybe_unused]] std::optional<std::uint64_t> parse_alphabet(std::string_view text, const std::string& alphabet, bool reject_leading = true) {
    if (alphabet.size() < 2 || alphabet.size() > 64 || text.empty()) return std::nullopt;
    std::array<int, 256> inverse{};
    inverse.fill(-1);
    for (std::size_t i = 0; i < alphabet.size(); ++i) {
        unsigned char symbol = static_cast<unsigned char>(alphabet[i]);
        if (symbol == ' ' || inverse[symbol] != -1) return std::nullopt;
        inverse[symbol] = static_cast<int>(i);
    }
    if (reject_leading && text.size() > 1 && text.front() == alphabet.front()) return std::nullopt;
    std::uint64_t value = 0;
    for (char c : text) {
        int digit = inverse[static_cast<unsigned char>(c)];
        if (digit < 0) return std::nullopt;
        std::uint64_t next = 0;
        if (!checked_mul_add(value, static_cast<unsigned>(alphabet.size()), static_cast<unsigned>(digit), std::numeric_limits<std::uint64_t>::max(), next)) return std::nullopt;
        value = next;
    }
    return value;
}
[[maybe_unused]] std::string format_alphabet(std::uint64_t value, const std::string& alphabet, std::size_t width = 0) {
    if (alphabet.size() < 2) return {};
    std::string out;
    do {
        out.push_back(alphabet[value % alphabet.size()]);
        value /= alphabet.size();
    } while (value != 0);
    while (out.size() < width) out.push_back(alphabet.front());
    std::reverse(out.begin(), out.end());
    return out;
}
[[maybe_unused]] std::optional<std::string> recode(std::string_view text, unsigned in_radix, unsigned out_radix, bool reject_leading = true) {
    auto value = parse_text(text, in_radix, reject_leading);
    if (!value || out_radix < 2 || out_radix > 36) return std::nullopt;
    return format_value(*value, out_radix);
}
[[maybe_unused]] bool decimal_multiply_add(std::string& decimal, unsigned radix, unsigned digit) {
    if (decimal.empty()) decimal = "0";
    unsigned carry = digit;
    for (auto it = decimal.rbegin(); it != decimal.rend(); ++it) {
        unsigned value = static_cast<unsigned>(*it - '0') * radix + carry;
        *it = static_cast<char>('0' + value % 10);
        carry = value / 10;
    }
    while (carry) {
        decimal.insert(decimal.begin(), static_cast<char>('0' + carry % 10));
        carry /= 10;
    }
    while (decimal.size() > 1 && decimal.front() == '0') decimal.erase(decimal.begin());
    return true;
}
}  // namespace f26rad_detail
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
            "f26rad-ledger-invalid-radix",
            "Ledger invalid radix",
            "ledger_radix",
            """
            struct Entry { unsigned radix; std::string amount; };
            struct Audit { bool ok; std::uint64_t value; std::string canonical; };
            Audit ingest(const Entry&);
            """,
            """
            struct Entry { unsigned radix; std::string amount; };
            struct Audit { bool ok; std::uint64_t value; std::string canonical; };
            Audit ingest(const Entry&);
            """,
            """
            Audit ingest(const Entry& entry) {
                auto value = f26rad_detail::parse_text(entry.amount, entry.radix, true, std::numeric_limits<std::uint64_t>::max(), 3, 24);
                if (!value) return {false, 0, {}};
                return {true, *value, f26rad_detail::format_value(*value, entry.radix)};
            }
            """,
            """
            Audit ingest(const Entry& entry) {
                auto value = f26rad_detail::parse_text(entry.amount, entry.radix, false, std::numeric_limits<std::uint64_t>::max(), 2, 36);
                if (!value) return {false, 0, {}};
                return {true, *value, f26rad_detail::format_value(*value, entry.radix)};
            }
            """,
            """
            auto audit = ingest({16, "1A"});
            if (!audit.ok || audit.value != 26 || audit.canonical != "1A") return 1;
            return 0;
            """,
            """
            if (ingest({2, "10"}).ok) return 1;
            if (ingest({10, "00"}).ok) return 2;
            if (!ingest({24, "N"}).ok) return 3;
            if (ingest({24, std::string(64, 'N')}).ok) return 4;
            return 0;
            """,
            "policy-first radix validation with checked Horner accumulation and canonical uppercase formatting",
            "late radix acceptance, leading-zero trimming, std::stoull, or floating conversion",
            "radix 2 rejected, digit equal to radix rejected, zero canonicalized, leading zero rejected, overflow rejected",
            "invalid-base and canonical-output coverage for a two-file API",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26rad-ticket-target-policy",
            "Ticket target policy",
            "ticket_codes",
            """
            struct Policy { unsigned input_radix; unsigned output_radix; bool preserve_zero; };
            std::optional<std::string> reissue(std::string_view ticket, const Policy&);
            """,
            """
            struct Policy { unsigned input_radix; unsigned output_radix; bool preserve_zero; };
            std::optional<std::string> reissue(std::string_view ticket, const Policy&);
            """,
            """
            std::optional<std::string> reissue(std::string_view ticket, const Policy& policy) {
                if (policy.input_radix < 4 || policy.input_radix > 18 || policy.output_radix < 4 || policy.output_radix > 18) return std::nullopt;
                if (ticket.empty()) return std::nullopt;
                auto value = f26rad_detail::parse_text(ticket, policy.input_radix, true);
                if (!value) return std::nullopt;
                if (*value == 0 && !policy.preserve_zero && ticket != "0") return std::nullopt;
                return f26rad_detail::format_value(*value, policy.output_radix);
            }
            """,
            """
            std::optional<std::string> reissue(std::string_view ticket, const Policy& policy) {
                auto value = f26rad_detail::parse_text(ticket, policy.input_radix, false);
                if (!value) return std::nullopt;
                return f26rad_detail::format_value(*value, policy.output_radix);
            }
            """,
            """
            auto out = reissue("G", {17, 4, false});
            if (!out || *out != "100") return 1;
            return 0;
            """,
            """
            if (reissue("10", {4, 3, false})) return 1;
            if (reissue("", {10, 10, true})) return 2;
            if (reissue("01", {10, 10, true})) return 3;
            return 0;
            """,
            "source and target policy validation before checked conversion",
            "generic wrapper that parses first and validates output policy afterward",
            "invalid target radix, empty tickets, leading zeros, and base-17 to base-4 conversion",
            "target-base validation and output policy coverage",
            "injected alphabet/radix policy object",
        ),
        c(
            "f26rad-symbol-table-bounds",
            "Symbol table bounds",
            "symbol_table",
            """
            class SymbolTable {
            public:
                explicit SymbolTable(std::string symbols);
                std::optional<std::uint64_t> read(std::string_view text) const;
                std::string write(std::uint64_t value) const;
            };
            """,
            """
            class SymbolTable {
            public:
                explicit SymbolTable(std::string symbols);
                std::optional<std::uint64_t> read(std::string_view text) const;
                std::string write(std::uint64_t value) const;
            private:
                std::string symbols_;
                std::array<int, 256> inverse_{};
                bool valid_ = false;
            };
            """,
            """
            SymbolTable::SymbolTable(std::string symbols) : symbols_(std::move(symbols)) {
                inverse_.fill(-1);
                if (symbols_.size() < 2 || symbols_.size() > 32) return;
                for (std::size_t i = 0; i < symbols_.size(); ++i) {
                    unsigned char c = static_cast<unsigned char>(symbols_[i]);
                    if (symbols_[i] == ' ' || inverse_[c] != -1) return;
                    inverse_[c] = static_cast<int>(i);
                }
                valid_ = true;
            }
            std::optional<std::uint64_t> SymbolTable::read(std::string_view text) const {
                if (!valid_ || text.empty() || (text.size() > 1 && text.front() == symbols_.front())) return std::nullopt;
                std::uint64_t value = 0;
                for (char c : text) {
                    int digit = inverse_[static_cast<unsigned char>(c)];
                    if (digit < 0) return std::nullopt;
                    std::uint64_t next = 0;
                    if (!f26rad_detail::checked_mul_add(value, static_cast<unsigned>(symbols_.size()), static_cast<unsigned>(digit), std::numeric_limits<std::uint64_t>::max(), next)) return std::nullopt;
                    value = next;
                }
                return value;
            }
            std::string SymbolTable::write(std::uint64_t value) const {
                return valid_ ? f26rad_detail::format_alphabet(value, symbols_) : std::string{};
            }
            """,
            """
            SymbolTable::SymbolTable(std::string symbols) : symbols_(std::move(symbols)) {
                inverse_.fill(-1);
                for (std::size_t i = 0; i < symbols_.size(); ++i) inverse_[static_cast<unsigned char>(symbols_[i])] = static_cast<int>(i);
                valid_ = symbols_.size() >= 2;
            }
            std::optional<std::uint64_t> SymbolTable::read(std::string_view text) const {
                return f26rad_detail::parse_alphabet(text, symbols_, false);
            }
            std::string SymbolTable::write(std::uint64_t value) const { return f26rad_detail::format_alphabet(value, symbols_); }
            """,
            """
            SymbolTable table("ZYXWVUT");
            auto value = table.read("YX");
            if (!value || *value != 9 || table.write(9) != "YX") return 1;
            return 0;
            """,
            """
            if (SymbolTable("AABC").read("BA")) return 1;
            if (SymbolTable("A").read("A")) return 2;
            if (SymbolTable("AB CD").read("AB")) return 3;
            if (SymbolTable("ABCDE").read("AA")) return 4;
            return 0;
            """,
            "one-time inverse alphabet table with duplicate and glyph bounds before checked Horner",
            "ASCII-order assumptions, regex cleanup, or first-duplicate lookup",
            "duplicate symbols, invalid alphabet size, spaces, leading alphabet zero, and shuffled round-trip",
            "alphabet-driven digit bounds with private support context",
            "injected alphabet/radix policy object",
            project_support=True,
        ),
        c(
            "f26rad-dual-alphabet-guard",
            "Dual alphabet guard",
            "dual_alpha",
            """
            struct Encoded { std::string text; unsigned source_id; };
            class Codec {
            public:
                Codec(std::vector<std::string> alphabets);
                std::optional<Encoded> translate(const Encoded&, unsigned target_id) const;
            };
            """,
            """
            struct Encoded { std::string text; unsigned source_id; };
            class Codec {
            public:
                Codec(std::vector<std::string> alphabets);
                std::optional<Encoded> translate(const Encoded&, unsigned target_id) const;
            private:
                std::vector<std::string> alphabets_;
                std::vector<bool> valid_;
            };
            """,
            """
            Codec::Codec(std::vector<std::string> alphabets) : alphabets_(std::move(alphabets)) {
                for (const auto& alphabet : alphabets_) valid_.push_back(static_cast<bool>(f26rad_detail::parse_alphabet(std::string(1, alphabet.empty() ? '?' : alphabet.back()), alphabet, false)));
            }
            std::optional<Encoded> Codec::translate(const Encoded& encoded, unsigned target_id) const {
                if (encoded.source_id >= alphabets_.size() || target_id >= alphabets_.size() || !valid_[encoded.source_id] || !valid_[target_id]) return std::nullopt;
                auto value = f26rad_detail::parse_alphabet(encoded.text, alphabets_[encoded.source_id], true);
                if (!value) return std::nullopt;
                return Encoded{f26rad_detail::format_alphabet(*value, alphabets_[target_id]), target_id};
            }
            """,
            """
            Codec::Codec(std::vector<std::string> alphabets) : alphabets_(std::move(alphabets)), valid_(alphabets_.size(), true) {}
            std::optional<Encoded> Codec::translate(const Encoded& encoded, unsigned target_id) const {
                if (target_id >= alphabets_.size() || alphabets_.empty()) return std::nullopt;
                auto value = f26rad_detail::parse_alphabet(encoded.text, alphabets_[0], false);
                if (!value) return std::nullopt;
                return Encoded{f26rad_detail::format_alphabet(*value, alphabets_[target_id]), target_id};
            }
            """,
            """
            Codec codec({"01", "XYZ"});
            auto out = codec.translate({"101", 0}, 1);
            if (!out || out->source_id != 1 || out->text != "YZ") return 1;
            return 0;
            """,
            """
            Codec codec({"01", "ABC", "AABC"});
            if (codec.translate({"10", 8}, 1)) return 1;
            if (codec.translate({"10", 0}, 8)) return 2;
            if (codec.translate({"02", 0}, 1)) return 3;
            if (codec.translate({"10", 2}, 1)) return 4;
            return 0;
            """,
            "per-alphabet inverse maps and ID validation before canonical translation",
            "using source_id as a radix or decoding all inputs with alphabet zero",
            "source/target ID absence, duplicate alphabets, source swaps, and rejected input preserving state",
            "multi-policy state and absent-ID handling",
            "value type with equality",
        ),
        c(
            "f26rad-range-window-parser",
            "Range window parser",
            "window_codes",
            """
            struct Window { unsigned min_radix; unsigned max_radix; };
            struct Parse { bool ok; unsigned chosen_radix; std::uint64_t value; };
            Parse parse_smallest_valid(std::string_view text, Window);
            """,
            """
            struct Window { unsigned min_radix; unsigned max_radix; };
            struct Parse { bool ok; unsigned chosen_radix; std::uint64_t value; };
            Parse parse_smallest_valid(std::string_view text, Window);
            """,
            """
            Parse parse_smallest_valid(std::string_view text, Window window) {
                if (text.empty() || window.min_radix < 2 || window.max_radix > 36 || window.min_radix > window.max_radix || (text.size() > 1 && text.front() == '0')) return {false, 0, 0};
                unsigned needed = 2;
                for (char c : text) {
                    int digit = f26rad_detail::digit36(c);
                    if (digit < 0) return {false, 0, 0};
                    needed = std::max(needed, static_cast<unsigned>(digit + 1));
                }
                unsigned chosen = std::max(window.min_radix, needed);
                if (chosen > window.max_radix) return {false, 0, 0};
                auto value = f26rad_detail::parse_text(text, chosen, true);
                return value ? Parse{true, chosen, *value} : Parse{false, 0, 0};
            }
            """,
            """
            Parse parse_smallest_valid(std::string_view text, Window window) {
                for (unsigned radix = window.max_radix; radix >= window.min_radix && radix >= 2; --radix) {
                    auto value = f26rad_detail::parse_text(text, radix, false);
                    if (value) return {true, radix, *value};
                    if (radix == 0) break;
                }
                return {false, 0, 0};
            }
            """,
            """
            auto parsed = parse_smallest_valid("10", {2, 10});
            if (!parsed.ok || parsed.chosen_radix != 2 || parsed.value != 2) return 1;
            return 0;
            """,
            """
            if (parse_smallest_valid("10", {8, 3}).ok) return 1;
            if (parse_smallest_valid("Z", {2, 10}).ok) return 2;
            if (parse_smallest_valid("01", {2, 10}).ok) return 3;
            auto parsed = parse_smallest_valid("A", {2, 36});
            if (!parsed.ok || parsed.chosen_radix != 11) return 4;
            return 0;
            """,
            "max-digit scan, deterministic smallest-radix choice, then checked accumulation",
            "coercing invalid characters or choosing the largest valid radix",
            "bad windows, out-of-range characters, tie choice, leading zeros, and overflow after choice",
            "deterministic radix selection and tie behavior",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26rad-field-width-authority",
            "Field width authority",
            "field_width",
            """
            class WidthError : public std::logic_error {
            public:
                explicit WidthError(const std::string&);
            };
            class Reader {
            public:
                Reader(unsigned radix, std::size_t width);
                std::uint64_t parse_exact(std::string_view) const;
            };
            """,
            """
            class WidthError : public std::logic_error {
            public:
                explicit WidthError(const std::string&);
            };
            class Reader {
            public:
                Reader(unsigned radix, std::size_t width);
                std::uint64_t parse_exact(std::string_view) const;
            private:
                unsigned radix_;
                std::size_t width_;
            };
            """,
            """
            WidthError::WidthError(const std::string& message) : std::logic_error(message) {}
            Reader::Reader(unsigned radix, std::size_t width) : radix_(radix), width_(width) {
                if (radix < 2 || radix > 16 || width < 1 || width > 16) throw WidthError("invalid width policy");
            }
            std::uint64_t Reader::parse_exact(std::string_view text) const {
                if (text.size() != width_) throw std::domain_error("wrong width");
                auto value = f26rad_detail::parse_text(text, radix_, false);
                if (!value) throw std::domain_error("bad field");
                return *value;
            }
            """,
            """
            WidthError::WidthError(const std::string& message) : std::logic_error(message) {}
            Reader::Reader(unsigned radix, std::size_t width) : radix_(radix), width_(width) {}
            std::uint64_t Reader::parse_exact(std::string_view text) const {
                std::string padded(text);
                while (padded.size() < width_) padded.insert(padded.begin(), '0');
                auto value = f26rad_detail::parse_text(padded, radix_, false);
                return value.value_or(0);
            }
            """,
            """
            Reader reader(16, 4);
            if (reader.parse_exact("000F") != 15) return 1;
            return 0;
            """,
            """
            try { Reader bad(17, 4); return 1; } catch (const WidthError&) {}
            Reader reader(16, 4);
            try { (void)reader.parse_exact("F"); return 2; } catch (const std::domain_error&) {}
            try { (void)reader.parse_exact("000G"); return 3; } catch (const std::domain_error&) {}
            return 0;
            """,
            "constructor-owned radix/width invariants and exact-width checked Horner",
            "trimming or padding width after accepting short input",
            "constructor exceptions, exact leading-zero width, short/long rejection, and digit bounds",
            "exception behavior and fixed-width preservation",
            "exception-throwing policy object or service class",
            project_support=True,
        ),
        c(
            "f26rad-signed-envelope-policy",
            "Signed envelope policy",
            "signed_envelope",
            """
            struct Number { bool negative; std::vector<unsigned> magnitude_digits; unsigned radix; };
            std::optional<Number> normalize(Number);
            bool less_magnitude(const Number&, const Number&);
            """,
            """
            struct Number { bool negative; std::vector<unsigned> magnitude_digits; unsigned radix; };
            std::optional<Number> normalize(Number);
            bool less_magnitude(const Number&, const Number&);
            """,
            """
            std::optional<Number> normalize(Number number) {
                if (number.radix < 2 || number.radix > 20 || number.magnitude_digits.empty()) return std::nullopt;
                for (unsigned digit : number.magnitude_digits) if (digit >= number.radix) return std::nullopt;
                while (number.magnitude_digits.size() > 1 && number.magnitude_digits.front() == 0) number.magnitude_digits.erase(number.magnitude_digits.begin());
                if (number.negative && number.magnitude_digits.size() == 1 && number.magnitude_digits.front() == 0) return std::nullopt;
                return number;
            }
            bool less_magnitude(const Number& left, const Number& right) {
                auto a = f26rad_detail::parse_digits(left.magnitude_digits, left.radix, false);
                auto b = f26rad_detail::parse_digits(right.magnitude_digits, right.radix, false);
                return a && b && *a < *b;
            }
            """,
            """
            std::optional<Number> normalize(Number number) { return number; }
            bool less_magnitude(const Number& left, const Number& right) {
                return left.magnitude_digits < right.magnitude_digits;
            }
            """,
            """
            auto n = normalize({false, {0, 0, 5}, 10});
            if (!n || n->magnitude_digits != std::vector<unsigned>({5})) return 1;
            return 0;
            """,
            """
            if (normalize({true, {0}, 10})) return 1;
            if (normalize({false, {0, 20}, 20})) return 2;
            if (less_magnitude({false, {1, 0}, 2}, {false, {2}, 10}) != false) return 3;
            if (less_magnitude({false, {1, 1}, 2}, {false, {4}, 10}) != true) return 4;
            return 0;
            """,
            "sign-separated normalization and magnitude comparison after digit validation",
            "signed machine conversion, negative zero, or lexicographic-only ordering",
            "negative zero, cross-radix equal values, large values, and leading-zero mutation",
            "sign, canonical form, and comparison without the official vector contract",
            "value type with operators",
        ),
        c(
            "f26rad-capability-negotiator",
            "Capability negotiator",
            "negotiator",
            """
            class RadixNegotiator {
            public:
                bool offer(unsigned);
                std::optional<unsigned> active() const;
                std::optional<std::string> encode(std::uint64_t) const;
                void reset();
            };
            """,
            """
            class RadixNegotiator {
            public:
                bool offer(unsigned);
                std::optional<unsigned> active() const;
                std::optional<std::string> encode(std::uint64_t) const;
                void reset();
            private:
                std::set<unsigned> offers_;
            };
            """,
            """
            bool RadixNegotiator::offer(unsigned radix) {
                if (radix < 2 || radix > 36) return false;
                offers_.insert(radix);
                return true;
            }
            std::optional<unsigned> RadixNegotiator::active() const {
                if (offers_.empty()) return std::nullopt;
                return *offers_.begin();
            }
            std::optional<std::string> RadixNegotiator::encode(std::uint64_t value) const {
                auto radix = active();
                if (!radix) return std::nullopt;
                return f26rad_detail::format_value(value, *radix);
            }
            void RadixNegotiator::reset() { offers_.clear(); }
            """,
            """
            bool RadixNegotiator::offer(unsigned radix) {
                if (radix < 2 || radix > 36) return false;
                offers_.clear();
                offers_.insert(radix);
                return true;
            }
            std::optional<unsigned> RadixNegotiator::active() const { return offers_.empty() ? std::nullopt : std::optional<unsigned>(*offers_.rbegin()); }
            std::optional<std::string> RadixNegotiator::encode(std::uint64_t value) const { auto radix = active(); return radix ? std::optional<std::string>(f26rad_detail::format_value(value, *radix)) : std::nullopt; }
            void RadixNegotiator::reset() { offers_.clear(); }
            """,
            """
            RadixNegotiator n;
            n.offer(16);
            n.offer(8);
            if (n.active() != 8 || n.encode(15) != std::optional<std::string>("17")) return 1;
            return 0;
            """,
            """
            RadixNegotiator n;
            if (n.offer(1)) return 1;
            n.offer(3);
            n.offer(20);
            if (n.active() != 3) return 2;
            if (n.encode(15) != std::optional<std::string>("120")) return 4;
            n.reset();
            if (n.active() || n.encode(5)) return 3;
            return 0;
            """,
            "ordered valid-offer state with reset and smallest-active derivation",
            "last-offer-wins state or storing invalid radices for later",
            "invalid offers, duplicates, reset, and encoding with no active radix",
            "stateful lifecycle and reset semantics around radix policy",
            "stateful class with repeated calls and reset semantics",
            project_support=True,
        ),
        c(
            "f26rad-batch-base-audit",
            "Batch base audit",
            "batch_radix",
            """
            struct Item { unsigned radix; std::string text; };
            struct BatchAudit { std::vector<bool> ok; std::vector<std::uint64_t> values; std::size_t first_error; };
            BatchAudit inspect(const std::vector<Item>&);
            """,
            """
            struct Item { unsigned radix; std::string text; };
            struct BatchAudit { std::vector<bool> ok; std::vector<std::uint64_t> values; std::size_t first_error; };
            BatchAudit inspect(const std::vector<Item>&);
            """,
            """
            BatchAudit inspect(const std::vector<Item>& items) {
                BatchAudit audit{{}, {}, items.size()};
                for (std::size_t i = 0; i < items.size(); ++i) {
                    auto value = f26rad_detail::parse_text(items[i].text, items[i].radix, true);
                    audit.ok.push_back(static_cast<bool>(value));
                    audit.values.push_back(value.value_or(0));
                    if (!value && audit.first_error == items.size()) audit.first_error = i;
                }
                return audit;
            }
            """,
            """
            BatchAudit inspect(const std::vector<Item>& items) {
                BatchAudit audit{{}, {}, items.size()};
                for (std::size_t i = 0; i < items.size(); ++i) {
                    auto value = f26rad_detail::parse_text(items[i].text, items[i].radix, true);
                    if (!value) { audit.first_error = i; return audit; }
                    audit.ok.push_back(true);
                    audit.values.push_back(*value);
                }
                return audit;
            }
            """,
            """
            auto audit = inspect({{10, "7"}, {16, "10"}});
            if (audit.ok.size() != 2 || !audit.ok[0] || audit.values[1] != 16 || audit.first_error != 2) return 1;
            return 0;
            """,
            """
            auto empty = inspect({});
            if (!empty.ok.empty() || empty.first_error != 0) return 1;
            auto audit = inspect({{10, "9"}, {2, "2"}, {10, "5"}});
            if (audit.ok.size() != 3 || audit.values.size() != 3 || audit.first_error != 1 || audit.ok[2] != true) return 2;
            return 0;
            """,
            "per-item policy-first validation with stable result slots and first-error tracking",
            "aborting the whole batch without per-item outputs",
            "empty batch, first error, later error after valid items, and overflow in later item",
            "structured output shape and batch ordering",
            "free function returning explicit result/audit struct",
        ),
        c(
            "f26rad-exception-policy-gate",
            "Exception policy gate",
            "gate_code",
            """
            class RadixPolicyError : public std::invalid_argument {
            public:
                explicit RadixPolicyError(const std::string&);
            };
            class DigitError : public std::domain_error {
            public:
                explicit DigitError(const std::string&);
            };
            std::string normalize_token(std::string_view token, unsigned radix);
            """,
            """
            class RadixPolicyError : public std::invalid_argument {
            public:
                explicit RadixPolicyError(const std::string&);
            };
            class DigitError : public std::domain_error {
            public:
                explicit DigitError(const std::string&);
            };
            std::string normalize_token(std::string_view token, unsigned radix);
            """,
            """
            RadixPolicyError::RadixPolicyError(const std::string& message) : std::invalid_argument(message) {}
            DigitError::DigitError(const std::string& message) : std::domain_error(message) {}
            std::string normalize_token(std::string_view token, unsigned radix) {
                if (radix < 2 || radix > 24) throw RadixPolicyError("bad radix");
                auto value = f26rad_detail::parse_text(token, radix, true);
                if (!value) throw DigitError("bad digit token");
                return f26rad_detail::format_value(*value, radix);
            }
            """,
            """
            RadixPolicyError::RadixPolicyError(const std::string& message) : std::invalid_argument(message) {}
            DigitError::DigitError(const std::string& message) : std::domain_error(message) {}
            std::string normalize_token(std::string_view token, unsigned radix) {
                auto value = f26rad_detail::parse_text(token, radix, false);
                if (!value) throw std::invalid_argument("bad token");
                return f26rad_detail::format_value(*value, radix);
            }
            """,
            """
            if (normalize_token("0", 10) != "0") return 1;
            return 0;
            """,
            """
            try { (void)normalize_token("10", 1); return 1; } catch (const RadixPolicyError&) {}
            try { (void)normalize_token("A", 10); return 2; } catch (const DigitError&) {}
            try { (void)normalize_token("00", 10); return 3; } catch (const DigitError&) {}
            return 0;
            """,
            "two-phase validation with distinct exception types and canonical spelling",
            "sentinel strings or one generic exception for every failure",
            "exact exception types, valid zero, digit bound, and overflow path",
            "exception discipline and exact error classes",
            "exception-throwing policy object or service class",
        ),
    )
    rows += _digit_bound_cases()
    rows += _canonical_cases()
    rows += _overflow_cases()
    rows += _stateful_output_cases()
    if len(rows) != EXPECTED_ROOTS or len({row.task_id for row in rows}) != EXPECTED_ROOTS:
        _fail("binding_root_count_failed", str(len(rows)))
    spec_ids = re.findall(r"^\| `(f26rad-[a-z0-9-]+)` \|", SPEC_DOCUMENT.read_text(encoding="utf-8"), re.M)
    if spec_ids != [row.task_id for row in rows]:
        _fail("spec_owner_mismatch", f"spec={len(spec_ids)} owner={len(rows)}")
    if {row.task_id for row in rows if row.project_support} != PROJECT_SUPPORT_IDS:
        _fail("support_count_mismatch", str(sum(row.project_support for row in rows)))
    return rows


def _digit_bound_cases() -> tuple[TaskSpec, ...]:
    c = _case
    return (
        c(
            "f26rad-manifest-digit-ceiling",
            "Manifest digit ceiling",
            "manifest_codes",
            """
            struct Manifest { unsigned radix; std::vector<int> digits; };
            std::optional<std::uint64_t> total(const Manifest&);
            """,
            """
            struct Manifest { unsigned radix; std::vector<int> digits; };
            std::optional<std::uint64_t> total(const Manifest&);
            """,
            """
            std::optional<std::uint64_t> total(const Manifest& manifest) {
                if (manifest.radix < 2 || manifest.radix > 30 || manifest.digits.empty()) return std::nullopt;
                if (manifest.digits.size() > 1 && manifest.digits.front() == 0) return std::nullopt;
                std::uint64_t value = 0;
                for (int digit : manifest.digits) {
                    if (digit < 0 || static_cast<unsigned>(digit) >= manifest.radix) return std::nullopt;
                    std::uint64_t next = 0;
                    if (!f26rad_detail::checked_mul_add(value, manifest.radix, static_cast<unsigned>(digit), std::numeric_limits<std::uint64_t>::max(), next)) return std::nullopt;
                    value = next;
                }
                return value;
            }
            """,
            """
            std::optional<std::uint64_t> total(const Manifest& manifest) {
                std::vector<unsigned> digits;
                for (int digit : manifest.digits) digits.push_back(static_cast<unsigned>(digit));
                return f26rad_detail::parse_digits(digits, manifest.radix, false);
            }
            """,
            """
            auto value = total({30, {29}});
            if (!value || *value != 29) return 1;
            return 0;
            """,
            """
            if (total({10, {-1}})) return 1;
            if (total({10, {10}})) return 2;
            if (total({10, {}})) return 3;
            if (total({10, {0, 1}})) return 4;
            return 0;
            """,
            "signed digit validation before checked accumulation",
            "casting negative digits to unsigned or trimming leading zeros first",
            "negative digits, digit equal to radix, empty manifests, leading zero, and high radix boundary",
            "signed digit-bound screening without official vector naming",
            "free function returning optional value",
        ),
        c(
            "f26rad-sensor-glyph-ranges",
            "Sensor glyph ranges",
            "sensor_glyphs",
            """
            struct GlyphPolicy { char zero; unsigned radix; };
            std::optional<std::vector<unsigned>> decode_glyphs(std::string_view, GlyphPolicy);
            """,
            """
            struct GlyphPolicy { char zero; unsigned radix; };
            std::optional<std::vector<unsigned>> decode_glyphs(std::string_view, GlyphPolicy);
            """,
            """
            std::optional<std::vector<unsigned>> decode_glyphs(std::string_view text, GlyphPolicy policy) {
                if (policy.radix < 2 || policy.radix > 12 || text.empty()) return std::nullopt;
                std::vector<unsigned> digits;
                for (char c : text) {
                    int digit = static_cast<unsigned char>(c) - static_cast<unsigned char>(policy.zero);
                    if (digit < 0 || static_cast<unsigned>(digit) >= policy.radix) return std::nullopt;
                    digits.push_back(static_cast<unsigned>(digit));
                }
                return digits;
            }
            """,
            """
            std::optional<std::vector<unsigned>> decode_glyphs(std::string_view text, GlyphPolicy policy) {
                if (policy.radix < 2 || text.empty()) return std::nullopt;
                std::vector<unsigned> digits;
                for (char c : text) {
                    if (c < '0' || c > '9') return std::nullopt;
                    digits.push_back(static_cast<unsigned>(c - '0'));
                }
                return digits;
            }
            """,
            """
            auto digits = decode_glyphs("ABAC", {'A', 4});
            if (!digits || *digits != std::vector<unsigned>({0, 1, 0, 2})) return 1;
            return 0;
            """,
            """
            if (decode_glyphs("@A", {'A', 4})) return 1;
            if (decode_glyphs("AD", {'A', 3})) return 2;
            if (decode_glyphs("", {'A', 4})) return 3;
            if (!decode_glyphs("AA", {'A', 2}) || decode_glyphs("AA", {'A', 2})->size() != 2) return 4;
            return 0;
            """,
            "contiguous glyph range validation with preserved leading digits",
            "assuming ASCII zero or converting through a magnitude",
            "custom zero glyph, glyph before zero, glyph equal to radix, empty input, and preserved leading zero",
            "non-decimal glyph policy with project support",
            "injected alphabet/radix policy object",
            project_support=True,
        ),
        c(
            "f26rad-coupon-digit-lanes",
            "Coupon digit lanes",
            "coupon_lanes",
            """
            class LaneDecoder {
            public:
                LaneDecoder(unsigned radix, std::size_t lanes);
                std::optional<std::vector<unsigned>> split(std::string_view) const;
            };
            """,
            """
            class LaneDecoder {
            public:
                LaneDecoder(unsigned radix, std::size_t lanes);
                std::optional<std::vector<unsigned>> split(std::string_view) const;
            private:
                unsigned radix_;
                std::size_t lanes_;
                bool valid_;
            };
            """,
            """
            LaneDecoder::LaneDecoder(unsigned radix, std::size_t lanes) : radix_(radix), lanes_(lanes), valid_(radix >= 2 && radix <= 16 && lanes >= 1 && lanes <= 8) {}
            std::optional<std::vector<unsigned>> LaneDecoder::split(std::string_view text) const {
                if (!valid_ || text.empty() || text.size() % lanes_ != 0) return std::nullopt;
                std::vector<unsigned> digits;
                for (char c : text) {
                    int digit = f26rad_detail::digit36(c);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix_) return std::nullopt;
                    digits.push_back(static_cast<unsigned>(digit));
                }
                return digits;
            }
            """,
            """
            LaneDecoder::LaneDecoder(unsigned radix, std::size_t lanes) : radix_(radix), lanes_(lanes), valid_(lanes > 0) {}
            std::optional<std::vector<unsigned>> LaneDecoder::split(std::string_view text) const {
                if (!valid_ || text.empty() || text.size() % lanes_ != 0) return std::nullopt;
                std::vector<unsigned> digits;
                for (std::size_t i = 0; i < text.size(); ++i) {
                    int digit = f26rad_detail::digit36(text[i]);
                    if (i % lanes_ == 0 && (digit < 0 || static_cast<unsigned>(digit) >= radix_)) return std::nullopt;
                    digits.push_back(static_cast<unsigned>(std::max(digit, 0)));
                }
                return digits;
            }
            """,
            """
            LaneDecoder decoder(10, 2);
            auto digits = decoder.split("0912");
            if (!digits || *digits != std::vector<unsigned>({0, 9, 1, 2})) return 1;
            return 0;
            """,
            """
            LaneDecoder decoder(3, 2);
            if (decoder.split("012")) return 1;
            if (decoder.split("0123")) return 2;
            if (LaneDecoder(10, 0).split("12")) return 3;
            return 0;
            """,
            "lane-stride scan with all-position digit validation",
            "validating only the first position of each lane",
            "wrong length, digit equal to radix, constructor invalid lanes, and lane ordering with leading zero",
            "multi-call constructor policy and exact output vector shape",
            "stateful class with constructor policy",
        ),
        c(
            "f26rad-cargo-sparse-digits",
            "Cargo sparse digits",
            "cargo_sparse",
            """
            struct Term { std::size_t power; int digit; };
            struct CargoCode { unsigned radix; std::vector<Term> terms; };
            std::optional<std::uint64_t> weigh(const CargoCode&);
            """,
            """
            struct Term { std::size_t power; int digit; };
            struct CargoCode { unsigned radix; std::vector<Term> terms; };
            std::optional<std::uint64_t> weigh(const CargoCode&);
            """,
            """
            std::optional<std::uint64_t> weigh(const CargoCode& code) {
                if (code.radix < 2 || code.radix > 16 || code.terms.empty()) return std::nullopt;
                std::optional<std::size_t> previous;
                std::uint64_t total = 0;
                for (const auto& term : code.terms) {
                    if (previous && term.power >= *previous) return std::nullopt;
                    previous = term.power;
                    if (term.digit < 0 || static_cast<unsigned>(term.digit) >= code.radix) return std::nullopt;
                    std::uint64_t place = 1;
                    for (std::size_t i = 0; i < term.power; ++i) {
                        if (place > std::numeric_limits<std::uint64_t>::max() / code.radix) return std::nullopt;
                        place *= code.radix;
                    }
                    if (term.digit != 0 && place > std::numeric_limits<std::uint64_t>::max() / static_cast<unsigned>(term.digit)) return std::nullopt;
                    std::uint64_t contribution = place * static_cast<unsigned>(term.digit);
                    if (total > std::numeric_limits<std::uint64_t>::max() - contribution) return std::nullopt;
                    total += contribution;
                }
                return total;
            }
            """,
            """
            std::optional<std::uint64_t> weigh(const CargoCode& code) {
                if (code.radix < 2 || code.terms.empty()) return std::nullopt;
                auto terms = code.terms;
                std::sort(terms.begin(), terms.end(), [](const Term& a, const Term& b) { return a.power > b.power; });
                std::uint64_t total = 0;
                for (const auto& term : terms) if (term.digit >= 0) total += static_cast<unsigned>(term.digit);
                return total;
            }
            """,
            """
            auto value = weigh({10, {{2, 3}, {0, 4}}});
            if (!value || *value != 304) return 1;
            return 0;
            """,
            """
            if (weigh({10, {{2, 3}, {2, 4}}})) return 1;
            if (weigh({10, {{0, 4}, {2, 3}}})) return 2;
            if (weigh({10, {{1, 10}}})) return 3;
            if (weigh({2, {{64, 1}}})) return 4;
            return 0;
            """,
            "strict sparse-power order and checked place-value accumulation",
            "sorting terms or overwriting duplicate powers silently",
            "duplicate powers, unsorted powers, digit radix boundary, and high-power overflow",
            "sparse positional representation with project support",
            "policy object with sparse terms",
            project_support=True,
        ),
        c(
            "f26rad-grid-quadrant-digits",
            "Grid quadrant digits",
            "quadrant_grid",
            """
            struct QuadrantCode { std::array<unsigned, 8> digits; bool operator==(const QuadrantCode&) const; };
            std::optional<std::pair<unsigned,unsigned>> decode(const QuadrantCode&);
            """,
            """
            struct QuadrantCode { std::array<unsigned, 8> digits; bool operator==(const QuadrantCode&) const; };
            std::optional<std::pair<unsigned,unsigned>> decode(const QuadrantCode&);
            """,
            """
            bool QuadrantCode::operator==(const QuadrantCode& other) const { return digits == other.digits; }
            std::optional<std::pair<unsigned,unsigned>> decode(const QuadrantCode& code) {
                unsigned x = 0;
                unsigned y = 0;
                for (unsigned digit : code.digits) {
                    if (digit > 3) return std::nullopt;
                    x = (x << 1U) | ((digit >> 1U) & 1U);
                    y = (y << 1U) | (digit & 1U);
                }
                return std::pair<unsigned, unsigned>{x, y};
            }
            """,
            """
            bool QuadrantCode::operator==(const QuadrantCode& other) const { return digits == other.digits; }
            std::optional<std::pair<unsigned,unsigned>> decode(const QuadrantCode& code) {
                unsigned x = 0, y = 0;
                for (std::size_t i = 0; i < code.digits.size(); ++i) {
                    if (code.digits[i] > 3) return std::nullopt;
                    if (i < 4) x = (x << 2U) | code.digits[i]; else y = (y << 2U) | code.digits[i];
                }
                return std::pair<unsigned, unsigned>{x, y};
            }
            """,
            """
            auto point = decode({{2, 2, 2, 2, 2, 2, 2, 2}});
            if (!point || point->first != 255 || point->second != 0) return 1;
            return 0;
            """,
            """
            if (decode({{0, 0, 0, 0, 0, 0, 0, 4}})) return 1;
            auto corner = decode({{3, 3, 3, 3, 3, 3, 3, 3}});
            if (!corner || corner->first != 255 || corner->second != 255) return 2;
            QuadrantCode a{{0, 1, 2, 3, 0, 1, 2, 3}};
            QuadrantCode b{{0, 1, 2, 3, 0, 1, 2, 3}};
            if (!(a == b)) return 3;
            return 0;
            """,
            "fixed base-4 digit bounds with interleaved bit decoding",
            "interpreting all digits as one integer or concatenating x/y chunks",
            "digit four rejection, x/y swap detection, equality preservation, and byte corners",
            "fixed-length coordinate output with value semantics",
            "value type with equality",
        ),
        c(
            "f26rad-mixed-ticket-digits",
            "Mixed ticket digits",
            "mixed_ticket",
            """
            struct Field { unsigned radix; unsigned digit; };
            std::optional<std::uint64_t> pack(std::vector<Field>);
            """,
            """
            struct Field { unsigned radix; unsigned digit; };
            std::optional<std::uint64_t> pack(std::vector<Field>);
            """,
            """
            std::optional<std::uint64_t> pack(std::vector<Field> fields) {
                if (fields.empty()) return std::nullopt;
                std::uint64_t value = 0;
                for (const auto& field : fields) {
                    if (field.radix < 2 || field.radix > 50 || field.digit >= field.radix) return std::nullopt;
                    std::uint64_t next = 0;
                    if (!f26rad_detail::checked_mul_add(value, field.radix, field.digit, std::numeric_limits<std::uint64_t>::max(), next)) return std::nullopt;
                    value = next;
                }
                return value;
            }
            """,
            """
            std::optional<std::uint64_t> pack(std::vector<Field> fields) {
                if (fields.empty()) return std::nullopt;
                unsigned radix = fields.back().radix;
                std::uint64_t value = 0;
                for (const auto& field : fields) {
                    if (field.radix < 2 || field.digit >= radix) return std::nullopt;
                    value = value * radix + field.digit;
                }
                return value;
            }
            """,
            """
            auto value = pack({{2, 1}, {10, 3}, {5, 4}});
            if (!value || *value != 69) return 1;
            return 0;
            """,
            """
            if (pack({{3, 0}, {4, 4}})) return 1;
            if (pack({{1, 0}})) return 2;
            if (pack({})) return 3;
            auto a = pack({{2, 1}, {10, 0}});
            auto b = pack({{10, 1}, {2, 0}});
            if (!a || !b || *a == *b) return 4;
            return 0;
            """,
            "heterogeneous positional products in declared order",
            "using one global radix for every position",
            "per-field digit overflow, radix one, empty input, order distinction, and overflow",
            "mixed-radix order and per-position bounds",
            "free function over field vector",
        ),
        c(
            "f26rad-token-bank-digits",
            "Token bank digits",
            "token_bank",
            """
            class TokenBank {
            public:
                bool define(std::string token, unsigned value);
                std::optional<std::uint64_t> read(const std::vector<std::string>&, unsigned radix) const;
            };
            """,
            """
            class TokenBank {
            public:
                bool define(std::string token, unsigned value);
                std::optional<std::uint64_t> read(const std::vector<std::string>&, unsigned radix) const;
            private:
                std::map<std::string, unsigned> values_;
                std::set<unsigned> used_;
            };
            """,
            """
            bool TokenBank::define(std::string token, unsigned value) {
                if (token.empty() || values_.count(token) || used_.count(value)) return false;
                values_[std::move(token)] = value;
                used_.insert(value);
                return true;
            }
            std::optional<std::uint64_t> TokenBank::read(const std::vector<std::string>& tokens, unsigned radix) const {
                if (radix < 2 || radix > 64 || tokens.empty()) return std::nullopt;
                std::uint64_t value = 0;
                for (const auto& token : tokens) {
                    auto found = values_.find(token);
                    if (found == values_.end() || found->second >= radix) return std::nullopt;
                    std::uint64_t next = 0;
                    if (!f26rad_detail::checked_mul_add(value, radix, found->second, std::numeric_limits<std::uint64_t>::max(), next)) return std::nullopt;
                    value = next;
                }
                return value;
            }
            """,
            """
            bool TokenBank::define(std::string token, unsigned value) {
                if (token.empty() || values_.count(token)) return false;
                values_[std::move(token)] = value;
                return true;
            }
            std::optional<std::uint64_t> TokenBank::read(const std::vector<std::string>& tokens, unsigned radix) const {
                if (radix < 2 || tokens.empty()) return std::nullopt;
                std::uint64_t value = 0;
                for (const auto& token : tokens) value = value * radix + values_.at(token);
                return value;
            }
            """,
            """
            TokenBank bank;
            bank.define("low", 0);
            bank.define("high", 9);
            auto value = bank.read({"high", "low"}, 10);
            if (!value || *value != 90) return 1;
            return 0;
            """,
            """
            TokenBank bank;
            if (!bank.define("a", 0) || bank.define("a", 1)) return 1;
            if (bank.define("b", 0)) return 2;
            if (!bank.define("c", 3)) return 3;
            if (bank.read({"c"}, 3)) return 4;
            if (bank.read({"missing"}, 10)) return 5;
            return 0;
            """,
            "token/value bijection with checked Horner over known tokens",
            "using insertion order or accepting duplicate digit values",
            "duplicate token, duplicate value, token value equal to radix, unknown token, and preserved state",
            "owned state plus collision handling",
            "stateful token bank",
            project_support=True,
        ),
        c(
            "f26rad-scorecard-digit-audit",
            "Scorecard digit audit",
            "scorecard_radix",
            """
            struct DigitAudit { bool ok; std::size_t bad_index; unsigned highest_digit; };
            DigitAudit audit(std::vector<int>, unsigned radix);
            """,
            """
            struct DigitAudit { bool ok; std::size_t bad_index; unsigned highest_digit; };
            DigitAudit audit(std::vector<int>, unsigned radix);
            """,
            """
            DigitAudit audit(std::vector<int> digits, unsigned radix) {
                if (radix < 2 || radix > 36 || digits.empty()) return {false, 0, 0};
                unsigned highest = 0;
                for (std::size_t i = 0; i < digits.size(); ++i) {
                    if (digits[i] < 0 || static_cast<unsigned>(digits[i]) >= radix) return {false, i, highest};
                    highest = std::max(highest, static_cast<unsigned>(digits[i]));
                }
                return {true, digits.size(), highest};
            }
            """,
            """
            DigitAudit audit(std::vector<int> digits, unsigned radix) {
                std::size_t bad = 0;
                unsigned highest = 0;
                for (std::size_t i = 0; i < digits.size(); ++i) {
                    if (digits[i] < 0 || static_cast<unsigned>(digits[i]) >= radix) bad = i;
                    else highest = std::max(highest, static_cast<unsigned>(digits[i]));
                }
                return {bad == 0, bad, highest};
            }
            """,
            """
            auto report = audit({1, 9, 3}, 10);
            if (!report.ok || report.highest_digit != 9) return 1;
            return 0;
            """,
            """
            if (audit({}, 10).ok || audit({}, 10).bad_index != 0) return 1;
            auto report = audit({1, 10, -1}, 10);
            if (report.ok || report.bad_index != 1) return 2;
            if (audit({1}, 37).ok) return 3;
            return 0;
            """,
            "full digit validation with first-bad-index reporting",
            "reporting the last bad digit or succeeding after one valid digit",
            "multiple bad digits, highest digit at tail, negative digit, and radix 37 rejection",
            "diagnostic output and first-error ordering",
            "audit struct",
        ),
        c(
            "f26rad-route-marker-digits",
            "Route marker digits",
            "route_marker",
            """
            class MarkerDecoder {
            public:
                explicit MarkerDecoder(unsigned radix);
                std::vector<unsigned> digits(std::string_view) const;
            };
            """,
            """
            class MarkerDecoder {
            public:
                explicit MarkerDecoder(unsigned radix);
                std::vector<unsigned> digits(std::string_view) const;
            private:
                unsigned radix_;
            };
            """,
            """
            MarkerDecoder::MarkerDecoder(unsigned radix) : radix_(radix) {
                if (radix < 2 || radix > 20) throw std::invalid_argument("bad marker radix");
            }
            std::vector<unsigned> MarkerDecoder::digits(std::string_view text) const {
                if (text.empty()) throw std::domain_error("empty marker");
                std::vector<unsigned> out;
                for (char c : text) {
                    if (c >= 'a' && c <= 'z') throw std::domain_error("lowercase marker");
                    int digit = f26rad_detail::digit36(c);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix_) throw std::domain_error("bad marker digit");
                    out.push_back(static_cast<unsigned>(digit));
                }
                return out;
            }
            """,
            """
            MarkerDecoder::MarkerDecoder(unsigned radix) : radix_(radix) {}
            std::vector<unsigned> MarkerDecoder::digits(std::string_view text) const {
                std::vector<unsigned> out;
                for (char c : text) {
                    if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
                    int digit = f26rad_detail::digit36(c);
                    if (digit >= 0) out.push_back(static_cast<unsigned>(digit));
                }
                return out;
            }
            """,
            """
            MarkerDecoder decoder(16);
            if (decoder.digits("000A") != std::vector<unsigned>({0, 0, 0, 10})) return 1;
            return 0;
            """,
            """
            try { MarkerDecoder bad(0); return 1; } catch (const std::invalid_argument&) {}
            MarkerDecoder decoder(11);
            try { (void)decoder.digits("a"); return 2; } catch (const std::domain_error&) {}
            try { (void)decoder.digits("B"); return 3; } catch (const std::domain_error&) {}
            try { (void)decoder.digits(""); return 4; } catch (const std::domain_error&) {}
            return 0;
            """,
            "uppercase digit classification with exception boundaries",
            "case-folding or accepting lowercase markers",
            "lowercase rejection, constructor radix zero, digit boundary, empty input, and leading-zero preservation",
            "case policy and exception path",
            "exception-throwing service class",
        ),
        c(
            "f26rad-transponder-digit-order",
            "Transponder digit order",
            "transponder",
            """
            class DigitView {
            public:
                DigitView(std::string text, unsigned radix, bool least_first);
                std::optional<unsigned> next();
                bool failed() const;
            };
            """,
            """
            class DigitView {
            public:
                DigitView(std::string text, unsigned radix, bool least_first);
                std::optional<unsigned> next();
                bool failed() const;
            private:
                std::string text_;
                unsigned radix_;
                bool least_first_;
                std::size_t index_ = 0;
                bool failed_ = false;
            };
            """,
            """
            DigitView::DigitView(std::string text, unsigned radix, bool least_first) : text_(std::move(text)), radix_(radix), least_first_(least_first), failed_(radix < 2 || radix > 36 || text_.empty()) {}
            std::optional<unsigned> DigitView::next() {
                if (failed_ || index_ >= text_.size()) return std::nullopt;
                std::size_t position = least_first_ ? text_.size() - 1 - index_ : index_;
                ++index_;
                int digit = f26rad_detail::digit36(text_[position]);
                if (digit < 0 || static_cast<unsigned>(digit) >= radix_) {
                    failed_ = true;
                    return std::nullopt;
                }
                return static_cast<unsigned>(digit);
            }
            bool DigitView::failed() const { return failed_; }
            """,
            """
            DigitView::DigitView(std::string text, unsigned radix, bool least_first) : text_(std::move(text)), radix_(radix), least_first_(least_first) {}
            std::optional<unsigned> DigitView::next() {
                if (index_ >= text_.size()) return std::nullopt;
                std::size_t position = least_first_ ? text_.size() - 1 - index_ : index_;
                ++index_;
                int digit = f26rad_detail::digit36(text_[position]);
                if (digit < 0 || static_cast<unsigned>(digit) >= radix_) return std::nullopt;
                return static_cast<unsigned>(digit);
            }
            bool DigitView::failed() const { return false; }
            """,
            """
            DigitView view("123", 10, true);
            if (view.next() != 3U || view.next() != 2U || view.next() != 1U || view.next()) return 1;
            return 0;
            """,
            """
            DigitView empty("", 10, false);
            if (!empty.failed() || empty.next()) return 1;
            DigitView view("12A3", 10, false);
            if (view.next() != 1U || view.next() != 2U) return 2;
            if (view.next() || !view.failed() || view.next()) return 3;
            return 0;
            """,
            "direction-aware cursor with sticky per-yield failure",
            "buffer reversal without sticky failure semantics",
            "least-first ordering, empty input, digit equal to radix, and repeated calls after failure",
            "streaming interaction and stateful failure",
            "iterator-style API",
            project_support=True,
        ),
    )


def _canonical_cases() -> tuple[TaskSpec, ...]:
    c = _case
    return (
        c(
            "f26rad-canonical-zero-frame",
            "Canonical zero frame",
            "zero_frame",
            """
            struct Frame { unsigned radix; std::vector<unsigned> digits; };
            std::optional<Frame> canonical(Frame);
            """,
            """
            struct Frame { unsigned radix; std::vector<unsigned> digits; };
            std::optional<Frame> canonical(Frame);
            """,
            """
            std::optional<Frame> canonical(Frame frame) {
                if (frame.radix < 2 || frame.radix > 36 || frame.digits.empty()) return std::nullopt;
                for (unsigned digit : frame.digits) if (digit >= frame.radix) return std::nullopt;
                auto first = std::find_if(frame.digits.begin(), frame.digits.end(), [](unsigned digit) { return digit != 0; });
                if (first == frame.digits.end()) frame.digits = {0};
                else frame.digits.erase(frame.digits.begin(), first);
                return frame;
            }
            """,
            """
            std::optional<Frame> canonical(Frame frame) {
                while (!frame.digits.empty() && frame.digits.front() == 0) frame.digits.erase(frame.digits.begin());
                return frame;
            }
            """,
            """
            auto frame = canonical({10, {0, 0, 7}});
            if (!frame || frame->digits != std::vector<unsigned>({7})) return 1;
            return 0;
            """,
            """
            if (canonical({10, {}})) return 1;
            auto zero = canonical({10, {0, 0, 0}});
            if (!zero || zero->digits != std::vector<unsigned>({0})) return 2;
            if (canonical({1, {0}})) return 3;
            if (canonical({10, {0, 12}})) return 4;
            return 0;
            """,
            "validate every digit before reducing all-zero to a single zero",
            "treating empty input as zero or returning an empty zero vector",
            "empty, single zero, all-zero, leading-zero nonzero, digit bound, and radix one",
            "precise zero normalization",
            "value type",
        ),
        c(
            "f26rad-leading-zero-policy",
            "Leading zero policy",
            "lead_policy",
            """
            enum class LeadingZero { reject, preserve_width, normalize };
            struct Result { bool ok; std::vector<unsigned> digits; std::size_t width; };
            Result apply(std::vector<unsigned>, unsigned radix, LeadingZero);
            """,
            """
            enum class LeadingZero { reject, preserve_width, normalize };
            struct Result { bool ok; std::vector<unsigned> digits; std::size_t width; };
            Result apply(std::vector<unsigned>, unsigned radix, LeadingZero);
            """,
            """
            Result apply(std::vector<unsigned> digits, unsigned radix, LeadingZero policy) {
                std::size_t width = digits.size();
                if (radix < 2 || radix > 36 || digits.empty()) return {false, {}, width};
                for (unsigned digit : digits) if (digit >= radix) return {false, {}, width};
                if (policy == LeadingZero::reject && digits.size() > 1 && digits.front() == 0) return {false, {}, width};
                if (policy == LeadingZero::normalize) {
                    auto first = std::find_if(digits.begin(), digits.end(), [](unsigned digit) { return digit != 0; });
                    if (first == digits.end()) digits = {0};
                    else digits.erase(digits.begin(), first);
                }
                return {true, digits, width};
            }
            """,
            """
            Result apply(std::vector<unsigned> digits, unsigned radix, LeadingZero) {
                std::size_t width = digits.size();
                if (radix < 2 || digits.empty()) return {false, {}, width};
                while (digits.size() > 1 && digits.front() == 0) digits.erase(digits.begin());
                return {true, digits, width};
            }
            """,
            """
            auto result = apply({0, 0, 5}, 10, LeadingZero::normalize);
            if (!result.ok || result.digits != std::vector<unsigned>({5}) || result.width != 3) return 1;
            return 0;
            """,
            """
            if (apply({0, 5}, 10, LeadingZero::reject).ok) return 1;
            auto preserved = apply({0, 5}, 10, LeadingZero::preserve_width);
            if (!preserved.ok || preserved.digits != std::vector<unsigned>({0, 5}) || preserved.width != 2) return 2;
            auto zero = apply({0, 0}, 10, LeadingZero::normalize);
            if (!zero.ok || zero.digits != std::vector<unsigned>({0})) return 3;
            if (apply({0, 11}, 10, LeadingZero::normalize).ok) return 4;
            if (apply({}, 10, LeadingZero::normalize).ok) return 5;
            return 0;
            """,
            "policy-specific canonicalization only after full digit validation",
            "hard-coding one trim policy for every mode",
            "all three modes, all-zero normalization, bad digit behind zero, and empty input",
            "explicit leading-zero policy branching",
            "injected policy enum",
        ),
        c(
            "f26rad-empty-payload-result",
            "Empty payload result",
            "payload_result",
            """
            struct Decode { bool ok; bool empty; std::uint64_t value; };
            Decode read_payload(std::string_view, unsigned radix, bool empty_is_absent);
            """,
            """
            struct Decode { bool ok; bool empty; std::uint64_t value; };
            Decode read_payload(std::string_view, unsigned radix, bool empty_is_absent);
            """,
            """
            Decode read_payload(std::string_view text, unsigned radix, bool empty_is_absent) {
                if (text.empty()) return {empty_is_absent ? false : true, true, 0};
                auto value = f26rad_detail::parse_text(text, radix, true);
                return value ? Decode{true, false, *value} : Decode{false, false, 0};
            }
            """,
            """
            Decode read_payload(std::string_view text, unsigned radix, bool) {
                if (text.empty()) return {true, true, 0};
                auto value = f26rad_detail::parse_text(text, radix, false);
                return value ? Decode{true, false, *value} : Decode{false, false, 0};
            }
            """,
            """
            auto zero = read_payload("0", 10, true);
            if (!zero.ok || zero.empty || zero.value != 0) return 1;
            return 0;
            """,
            """
            auto absent = read_payload("", 10, true);
            auto allowed = read_payload("", 10, false);
            if (absent.ok || !absent.empty || !allowed.ok || !allowed.empty) return 1;
            if (read_payload("00", 10, false).ok) return 2;
            if (read_payload("10", 1, false).ok) return 3;
            return 0;
            """,
            "empty policy branch before canonical numeric parsing",
            "conflating empty text with the zero digit",
            "both empty policies, zero digit, noncanonical zero, invalid radix, and overflow",
            "empty-input semantics",
            "free function result",
        ),
        c(
            "f26rad-padding-preserve-width",
            "Padding preserve width",
            "padded_codes",
            """
            class Formatter {
            public:
                Formatter(unsigned radix, std::size_t width);
                std::optional<std::string> format(std::uint64_t) const;
                std::optional<std::uint64_t> parse(std::string_view) const;
            };
            """,
            """
            class Formatter {
            public:
                Formatter(unsigned radix, std::size_t width);
                std::optional<std::string> format(std::uint64_t) const;
                std::optional<std::uint64_t> parse(std::string_view) const;
            private:
                unsigned radix_;
                std::size_t width_;
                bool valid_;
            };
            """,
            """
            Formatter::Formatter(unsigned radix, std::size_t width) : radix_(radix), width_(width), valid_(radix >= 2 && radix <= 36 && width >= 1 && width <= 32) {}
            std::optional<std::string> Formatter::format(std::uint64_t value) const {
                if (!valid_) return std::nullopt;
                std::string out = f26rad_detail::format_value(value, radix_);
                if (out.size() > width_) return std::nullopt;
                while (out.size() < width_) out.insert(out.begin(), '0');
                return out;
            }
            std::optional<std::uint64_t> Formatter::parse(std::string_view text) const {
                if (!valid_ || text.size() != width_) return std::nullopt;
                return f26rad_detail::parse_text(text, radix_, false);
            }
            """,
            """
            Formatter::Formatter(unsigned radix, std::size_t width) : radix_(radix), width_(width), valid_(radix >= 2) {}
            std::optional<std::string> Formatter::format(std::uint64_t value) const { return f26rad_detail::format_value(value, radix_); }
            std::optional<std::uint64_t> Formatter::parse(std::string_view text) const { return f26rad_detail::parse_text(text, radix_, false); }
            """,
            """
            Formatter formatter(16, 4);
            if (formatter.format(15) != std::optional<std::string>("000F")) return 1;
            if (formatter.parse("000F") != 15U) return 2;
            return 0;
            """,
            """
            if (Formatter(10, 0).format(0)) return 1;
            Formatter one(2, 1);
            if (one.format(0) != std::optional<std::string>("0")) return 2;
            Formatter two(2, 2);
            if (two.format(4)) return 3;
            if (two.parse("1")) return 4;
            return 0;
            """,
            "width-aware quotient emission and exact-width parsing",
            "formatting then trimming or accepting shorter parses",
            "width one, zero-width constructor rejection, max width, overflow capacity, and round-trip",
            "fixed-width canonical output",
            "stateful formatter",
            project_support=True,
        ),
        c(
            "f26rad-normalized-display-tag",
            "Normalized display tag",
            "display_tag",
            """
            std::string normalize_tag(std::string_view tag, unsigned radix);
            """,
            """
            std::string normalize_tag(std::string_view tag, unsigned radix);
            """,
            """
            std::string normalize_tag(std::string_view tag, unsigned radix) {
                if (radix < 2 || radix > 36 || tag.empty()) throw std::domain_error("bad tag");
                std::string compact;
                std::size_t group = 0;
                bool previous_hyphen = false;
                for (char c : tag) {
                    if (c == '-') {
                        if (previous_hyphen || group != 2 || compact.empty()) throw std::domain_error("bad separator");
                        previous_hyphen = true;
                        group = 0;
                        continue;
                    }
                    if (c >= 'a' && c <= 'z') throw std::domain_error("lowercase");
                    int digit = f26rad_detail::digit36(c);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix) throw std::domain_error("bad digit");
                    compact.push_back(c);
                    ++group;
                    if (group > 2) throw std::domain_error("bad group");
                    previous_hyphen = false;
                }
                if (previous_hyphen || compact.empty()) throw std::domain_error("bad separator");
                auto value = f26rad_detail::parse_text(compact, radix, false);
                if (!value) throw std::domain_error("bad value");
                return f26rad_detail::format_value(*value, radix);
            }
            """,
            """
            std::string normalize_tag(std::string_view tag, unsigned radix) {
                std::string compact;
                for (char c : tag) if (c != '-') compact.push_back(c);
                auto value = f26rad_detail::parse_text(compact, radix, false);
                return value ? f26rad_detail::format_value(*value, radix) : std::string{};
            }
            """,
            """
            if (normalize_tag("00-0A", 16) != "A") return 1;
            return 0;
            """,
            """
            try { (void)normalize_tag("-0A", 16); return 1; } catch (const std::domain_error&) {}
            try { (void)normalize_tag("0A-", 16); return 2; } catch (const std::domain_error&) {}
            try { (void)normalize_tag("0A--0B", 16); return 3; } catch (const std::domain_error&) {}
            try { (void)normalize_tag("0a", 16); return 4; } catch (const std::domain_error&) {}
            try { (void)normalize_tag("0G", 16); return 5; } catch (const std::domain_error&) {}
            return 0;
            """,
            "small lexical state machine with separator validation before canonical output",
            "blindly deleting hyphens before digit validation",
            "leading, trailing, and double hyphens, invalid digit after separator, lowercase rejection, and leading-zero normalization",
            "lexical normalization with exact rejection behavior",
            "exception policy free function",
        ),
        c(
            "f26rad-zero-run-collapse",
            "Zero run collapse",
            "zero_runs",
            """
            class Collapser {
            public:
                bool push(unsigned digit);
                std::vector<unsigned> finish(unsigned radix);
                bool failed() const;
            };
            """,
            """
            class Collapser {
            public:
                bool push(unsigned digit);
                std::vector<unsigned> finish(unsigned radix);
                bool failed() const;
            private:
                std::vector<unsigned> digits_;
                bool failed_ = false;
            };
            """,
            """
            bool Collapser::push(unsigned digit) {
                if (failed_ || digit > 63) { failed_ = true; return false; }
                digits_.push_back(digit);
                return true;
            }
            std::vector<unsigned> Collapser::finish(unsigned radix) {
                if (failed_ || radix < 2 || radix > 64 || digits_.empty()) { failed_ = true; return {}; }
                for (unsigned digit : digits_) if (digit >= radix) { failed_ = true; return {}; }
                bool any_nonzero = std::any_of(digits_.begin(), digits_.end(), [](unsigned digit) { return digit != 0; });
                return any_nonzero ? digits_ : std::vector<unsigned>{0};
            }
            bool Collapser::failed() const { return failed_; }
            """,
            """
            bool Collapser::push(unsigned digit) { digits_.push_back(digit); return true; }
            std::vector<unsigned> Collapser::finish(unsigned) {
                std::vector<unsigned> out;
                for (unsigned digit : digits_) if (digit != 0) out.push_back(digit);
                return out;
            }
            bool Collapser::failed() const { return failed_; }
            """,
            """
            Collapser c;
            c.push(0);
            c.push(0);
            if (c.finish(10) != std::vector<unsigned>({0})) return 1;
            return 0;
            """,
            """
            Collapser c;
            c.push(1);
            c.push(0);
            if (c.finish(10) != std::vector<unsigned>({1, 0})) return 1;
            Collapser bad;
            bad.push(3);
            if (!bad.finish(3).empty() || !bad.failed()) return 2;
            Collapser empty;
            if (!empty.finish(10).empty() || !empty.failed()) return 3;
            return 0;
            """,
            "incremental state machine with all-zero collapse and radix validation at finish",
            "dropping every zero digit or trimming with a generic magnitude pass",
            "all-zero runs, zeros after nonzero, bad digit before finish, empty stream, and repeated finish",
            "stateful canonicalization and repeated-call behavior",
            "streaming accumulator",
        ),
        c(
            "f26rad-trimmed-magnitude-key",
            "Trimmed magnitude key",
            "magnitude_key",
            """
            struct Key { unsigned radix; std::string canonical; };
            std::optional<Key> make_key(std::string_view, unsigned radix);
            bool same_value(const Key&, const Key&);
            """,
            """
            struct Key { unsigned radix; std::string canonical; };
            std::optional<Key> make_key(std::string_view, unsigned radix);
            bool same_value(const Key&, const Key&);
            """,
            """
            std::optional<Key> make_key(std::string_view text, unsigned radix) {
                if (text.empty()) return std::nullopt;
                auto value = f26rad_detail::parse_text(text, radix, false);
                if (!value) return std::nullopt;
                return Key{radix, f26rad_detail::format_value(*value, radix)};
            }
            bool same_value(const Key& left, const Key& right) {
                auto a = f26rad_detail::parse_text(left.canonical, left.radix, false);
                auto b = f26rad_detail::parse_text(right.canonical, right.radix, false);
                return a && b && *a == *b;
            }
            """,
            """
            std::optional<Key> make_key(std::string_view text, unsigned radix) {
                std::string stripped(text);
                while (stripped.size() > 1 && stripped.front() == '0') stripped.erase(stripped.begin());
                return Key{radix, stripped};
            }
            bool same_value(const Key& left, const Key& right) { return left.canonical == right.canonical; }
            """,
            """
            auto key = make_key("00010", 2);
            if (!key || key->canonical != "10") return 1;
            return 0;
            """,
            """
            auto binary = make_key("00010", 2);
            auto decimal = make_key("2", 10);
            if (!binary || !decimal || !same_value(*binary, *decimal)) return 1;
            if (make_key("0002", 2)) return 2;
            if (make_key("", 10)) return 3;
            return 0;
            """,
            "validate every digit and re-emit minimal spelling in the original radix",
            "comparing stripped strings across radices",
            "cross-radix equivalence, bad digit after zeros, empty input, and overflow",
            "cross-radix equivalence without generic signature",
            "value type ordering helpers",
        ),
        c(
            "f26rad-canonical-vector-form",
            "Canonical vector form",
            "vector_form",
            """
            struct Canonical { unsigned radix; std::vector<unsigned> digits; };
            std::optional<Canonical> canonicalize(unsigned radix, std::vector<unsigned> raw);
            """,
            """
            struct Canonical { unsigned radix; std::vector<unsigned> digits; };
            std::optional<Canonical> canonicalize(unsigned radix, std::vector<unsigned> raw);
            """,
            """
            std::optional<Canonical> canonicalize(unsigned radix, std::vector<unsigned> raw) {
                if (radix < 2 || radix > 36 || raw.empty()) return std::nullopt;
                for (unsigned digit : raw) if (digit >= radix) return std::nullopt;
                auto first = std::find_if(raw.begin(), raw.end(), [](unsigned digit) { return digit != 0; });
                if (first == raw.end()) raw = {0};
                else raw.erase(raw.begin(), first);
                return Canonical{radix, raw};
            }
            """,
            """
            std::optional<Canonical> canonicalize(unsigned radix, std::vector<unsigned> raw) {
                while (raw.size() > 1 && raw.front() == 0) raw.erase(raw.begin());
                for (unsigned digit : raw) if (digit >= radix) return std::nullopt;
                return Canonical{radix, raw.empty() ? std::vector<unsigned>{0} : raw};
            }
            """,
            """
            auto out = canonicalize(10, {0, 0, 5});
            if (!out || out->digits != std::vector<unsigned>({5})) return 1;
            return 0;
            """,
            """
            if (canonicalize(10, {})) return 1;
            if (canonicalize(10, {0, 12})) return 2;
            auto zero = canonicalize(36, {0, 0});
            if (!zero || zero->digits != std::vector<unsigned>({0})) return 3;
            return 0;
            """,
            "vector validation before all-zero special-case trimming",
            "mutating input before validation or treating empty vector as zero",
            "bad digit after leading-zero prefix, empty vector, all-zero vector, and radix 36",
            "vector-shaped canonical output",
            "free function result",
            project_support=True,
        ),
        c(
            "f26rad-left-pad-checkpoint",
            "Left pad checkpoint",
            "checkpoints",
            """
            class Padder {
            public:
                explicit Padder(unsigned radix);
                std::optional<std::string> checkpoint(std::uint64_t value, std::size_t width);
                std::size_t calls() const;
            };
            """,
            """
            class Padder {
            public:
                explicit Padder(unsigned radix);
                std::optional<std::string> checkpoint(std::uint64_t value, std::size_t width);
                std::size_t calls() const;
            private:
                unsigned radix_;
                std::size_t calls_ = 0;
                bool valid_;
            };
            """,
            """
            Padder::Padder(unsigned radix) : radix_(radix), valid_(radix >= 2 && radix <= 36) {}
            std::optional<std::string> Padder::checkpoint(std::uint64_t value, std::size_t width) {
                if (!valid_ || width == 0) return std::nullopt;
                std::string out = f26rad_detail::format_value(value, radix_);
                if (out.size() > width) return std::nullopt;
                while (out.size() < width) out.insert(out.begin(), '0');
                ++calls_;
                return out;
            }
            std::size_t Padder::calls() const { return calls_; }
            """,
            """
            Padder::Padder(unsigned radix) : radix_(radix), valid_(radix >= 2) {}
            std::optional<std::string> Padder::checkpoint(std::uint64_t value, std::size_t width) {
                ++calls_;
                std::string out = f26rad_detail::format_value(value, radix_);
                while (out.size() < width) out.insert(out.begin(), '0');
                return out;
            }
            std::size_t Padder::calls() const { return calls_; }
            """,
            """
            Padder padder(16);
            if (padder.checkpoint(255, 2) != std::optional<std::string>("FF")) return 1;
            if (padder.calls() != 1) return 2;
            return 0;
            """,
            """
            Padder padder(2);
            if (padder.checkpoint(4, 2)) return 1;
            if (padder.calls() != 0) return 2;
            if (padder.checkpoint(0, 1) != std::optional<std::string>("0")) return 3;
            if (padder.calls() != 1) return 4;
            if (Padder(1).checkpoint(0, 1)) return 5;
            return 0;
            """,
            "checked width fit with mutation only after success",
            "incrementing state before validating output width",
            "too-narrow width, zero width, repeated success/failure counts, and invalid radix",
            "mutation atomicity and fixed canonical output",
            "stateful class",
        ),
        c(
            "f26rad-zero-equivalence-class",
            "Zero equivalence class",
            "zero_equiv",
            """
            struct Code { unsigned radix; std::vector<unsigned> digits; };
            class Equivalence {
            public:
                bool add(Code);
                std::vector<Code> canonical_members() const;
            };
            """,
            """
            struct Code { unsigned radix; std::vector<unsigned> digits; };
            class Equivalence {
            public:
                bool add(Code);
                std::vector<Code> canonical_members() const;
            private:
                std::vector<Code> members_;
            };
            """,
            """
            bool add_unique(std::vector<Code>& members, Code code) {
                for (const auto& member : members) if (member.radix == code.radix && member.digits == code.digits) return false;
                members.push_back(std::move(code));
                std::sort(members.begin(), members.end(), [](const Code& a, const Code& b) {
                    return std::tie(a.radix, a.digits) < std::tie(b.radix, b.digits);
                });
                return true;
            }
            bool Equivalence::add(Code code) {
                auto normalized = f26rad_detail::parse_digits(code.digits, code.radix, false);
                if (!normalized) return false;
                auto digits = f26rad_detail::digits_of(*normalized, code.radix);
                return add_unique(members_, Code{code.radix, digits});
            }
            std::vector<Code> Equivalence::canonical_members() const { return members_; }
            """,
            """
            bool Equivalence::add(Code code) {
                members_.push_back(std::move(code));
                return true;
            }
            std::vector<Code> Equivalence::canonical_members() const { return members_; }
            """,
            """
            Equivalence eq;
            if (!eq.add({10, {0, 0}})) return 1;
            if (!eq.add({2, {1, 0}})) return 2;
            if (eq.canonical_members().front().radix != 2) return 3;
            return 0;
            """,
            """
            Equivalence eq;
            if (!eq.add({10, {0, 0}})) return 1;
            if (eq.add({10, {0}})) return 2;
            if (eq.add({10, {10}})) return 3;
            if (!eq.add({2, {0}})) return 4;
            if (eq.canonical_members().size() != 2) return 5;
            return 0;
            """,
            "normalize each valid code and keep deterministic canonical members",
            "retaining raw zero spellings or sorting by insertion order",
            "invalid code, duplicate zero forms, same value across radices, and stable sorted output",
            "deterministic collection behavior around canonical zero",
            "stateful collection",
        ),
    )


def _overflow_cases() -> tuple[TaskSpec, ...]:
    c = _case
    return (
        c(
            "f26rad-horner-overflow-meter",
            "Horner overflow meter",
            "overflow_meter",
            """
            struct Meter { bool ok; std::size_t digits_read; std::uint64_t value; };
            Meter read(std::string_view, unsigned radix, std::uint64_t limit);
            """,
            """
            struct Meter { bool ok; std::size_t digits_read; std::uint64_t value; };
            Meter read(std::string_view, unsigned radix, std::uint64_t limit);
            """,
            """
            Meter read(std::string_view text, unsigned radix, std::uint64_t limit) {
                if (radix < 2 || radix > 36 || text.empty()) return {false, 0, 0};
                std::uint64_t value = 0;
                for (std::size_t i = 0; i < text.size(); ++i) {
                    int digit = f26rad_detail::digit36(text[i]);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix) return {false, i, value};
                    std::uint64_t next = 0;
                    if (!f26rad_detail::checked_mul_add(value, radix, static_cast<unsigned>(digit), limit, next)) return {false, i, value};
                    value = next;
                }
                return {true, text.size(), value};
            }
            """,
            """
            Meter read(std::string_view text, unsigned radix, std::uint64_t limit) {
                std::uint64_t value = 0;
                for (std::size_t i = 0; i < text.size(); ++i) {
                    int digit = f26rad_detail::digit36(text[i]);
                    value = value * radix + static_cast<unsigned>(std::max(digit, 0));
                    if (value > limit) return {false, i + 1, value};
                }
                return {true, text.size(), value};
            }
            """,
            """
            auto meter = read("101", 2, 10);
            if (!meter.ok || meter.value != 5 || meter.digits_read != 3) return 1;
            return 0;
            """,
            """
            auto limited = read("99", 10, 50);
            if (limited.ok || limited.digits_read != 1 || limited.value != 9) return 1;
            auto bad = read("1Z", 10, 100);
            if (bad.ok || bad.digits_read != 1) return 2;
            if (read("", 10, 1).ok) return 3;
            return 0;
            """,
            "checked Horner step against a caller limit before mutating the value",
            "wrapping arithmetic and checking after the fact",
            "limit below valid prefix, UINT64_MAX, invalid digit before overflow, and empty input",
            "receipt-verifiable overflow behavior",
            "audit struct",
        ),
        c(
            "f26rad-wide-accumulator-quote",
            "Wide accumulator quote",
            "quote_code",
            """
            class QuoteParser {
            public:
                std::uint64_t parse(std::string_view, unsigned radix) const;
            };
            """,
            """
            class QuoteParser {
            public:
                std::uint64_t parse(std::string_view, unsigned radix) const;
            };
            """,
            """
            std::uint64_t QuoteParser::parse(std::string_view text, unsigned radix) const {
                if (radix < 2 || radix > 36 || text.empty() || (text.size() > 1 && text.front() == '0')) throw std::domain_error("bad quote");
                std::uint64_t value = 0;
                for (char c : text) {
                    int digit = f26rad_detail::digit36(c);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix) throw std::domain_error("bad digit");
                    std::uint64_t next = 0;
                    if (!f26rad_detail::checked_mul_add(value, radix, static_cast<unsigned>(digit), std::numeric_limits<std::uint64_t>::max(), next)) throw std::overflow_error("quote overflow");
                    value = next;
                }
                return value;
            }
            """,
            """
            std::uint64_t QuoteParser::parse(std::string_view text, unsigned radix) const {
                long double value = 0;
                for (char c : text) {
                    int digit = f26rad_detail::digit36(c);
                    if (digit < 0) throw std::domain_error("bad digit");
                    value = value * radix + digit;
                }
                return static_cast<std::uint64_t>(value);
            }
            """,
            """
            QuoteParser parser;
            if (parser.parse("FF", 16) != 255) return 1;
            return 0;
            """,
            """
            QuoteParser parser;
            if (parser.parse("18446744073709551615", 10) != std::numeric_limits<std::uint64_t>::max()) return 1;
            try { (void)parser.parse("18446744073709551616", 10); return 2; } catch (const std::overflow_error&) {}
            try { (void)parser.parse("01", 10); return 3; } catch (const std::domain_error&) {}
            try { (void)parser.parse("1G", 16); return 4; } catch (const std::domain_error&) {}
            return 0;
            """,
            "division-threshold overflow guard per digit",
            "long double or signed intermediate conversion",
            "UINT64_MAX, UINT64_MAX plus one, invalid middle digit, and leading zero",
            "large magnitude exception behavior",
            "exception class API",
            project_support=True,
        ),
        c(
            "f26rad-limb-route-counter",
            "Limb route counter",
            "route_counter",
            """
            std::optional<std::vector<std::uint32_t>> to_base1e6(std::string_view text, unsigned radix);
            """,
            """
            std::optional<std::vector<std::uint32_t>> to_base1e6(std::string_view text, unsigned radix);
            """,
            """
            std::optional<std::vector<std::uint32_t>> to_base1e6(std::string_view text, unsigned radix) {
                if (radix < 2 || radix > 20 || text.empty() || text.size() > 256 || (text.size() > 1 && text.front() == '0')) return std::nullopt;
                std::vector<std::uint32_t> limbs{0};
                for (char c : text) {
                    int digit = f26rad_detail::digit36(c);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix) return std::nullopt;
                    std::uint64_t carry = static_cast<unsigned>(digit);
                    for (auto& limb : limbs) {
                        std::uint64_t next = static_cast<std::uint64_t>(limb) * radix + carry;
                        limb = static_cast<std::uint32_t>(next % 1000000U);
                        carry = next / 1000000U;
                    }
                    while (carry) {
                        limbs.push_back(static_cast<std::uint32_t>(carry % 1000000U));
                        carry /= 1000000U;
                    }
                }
                while (limbs.size() > 1 && limbs.back() == 0) limbs.pop_back();
                return limbs;
            }
            """,
            """
            std::optional<std::vector<std::uint32_t>> to_base1e6(std::string_view text, unsigned radix) {
                auto value = f26rad_detail::parse_text(text, radix, false);
                if (!value) return std::nullopt;
                return std::vector<std::uint32_t>{static_cast<std::uint32_t>(*value % 1000000U)};
            }
            """,
            """
            auto limbs = to_base1e6("1000000", 10);
            if (!limbs || *limbs != std::vector<std::uint32_t>({0, 1})) return 1;
            return 0;
            """,
            """
            auto long_value = to_base1e6(std::string(200, '1'), 2);
            if (!long_value || long_value->size() < 2) return 1;
            if (to_base1e6("01", 10)) return 2;
            if (to_base1e6("12Z", 20)) return 3;
            if (!to_base1e6("0", 10) || *to_base1e6("0", 10) != std::vector<std::uint32_t>({0})) return 4;
            return 0;
            """,
            "big-integer multiply-add over base-one-million limbs",
            "truncating through uint64_t",
            "200-digit base values, invalid tail digit, all-zero input, and limb carry boundaries",
            "large-value handling beyond fixed-width integers",
            "project support oracle",
            project_support=True,
        ),
        c(
            "f26rad-stream-residue-converter",
            "Stream residue converter",
            "residue_stream",
            """
            class Residue {
            public:
                Residue(unsigned radix, std::uint64_t modulus);
                bool push(char);
                std::optional<std::uint64_t> value() const;
            };
            """,
            """
            class Residue {
            public:
                Residue(unsigned radix, std::uint64_t modulus);
                bool push(char);
                std::optional<std::uint64_t> value() const;
            private:
                unsigned radix_;
                std::uint64_t modulus_;
                std::uint64_t residue_ = 0;
                bool failed_ = false;
            };
            """,
            """
            Residue::Residue(unsigned radix, std::uint64_t modulus) : radix_(radix), modulus_(modulus), failed_(radix < 2 || radix > 36 || modulus <= 1) {}
            bool Residue::push(char c) {
                if (failed_) return false;
                int digit = f26rad_detail::digit36(c);
                if (digit < 0 || static_cast<unsigned>(digit) >= radix_) { failed_ = true; return false; }
                residue_ = (residue_ * radix_ + static_cast<unsigned>(digit)) % modulus_;
                return true;
            }
            std::optional<std::uint64_t> Residue::value() const { return failed_ ? std::nullopt : std::optional<std::uint64_t>(residue_); }
            """,
            """
            Residue::Residue(unsigned radix, std::uint64_t modulus) : radix_(radix), modulus_(modulus) {}
            bool Residue::push(char c) {
                int digit = f26rad_detail::digit36(c);
                if (digit == 0) return false;
                if (digit < 0) return false;
                residue_ = (residue_ * radix_ + static_cast<unsigned>(digit)) % modulus_;
                return true;
            }
            std::optional<std::uint64_t> Residue::value() const { return residue_; }
            """,
            """
            Residue residue(10, 7);
            for (char c : std::string("123")) if (!residue.push(c)) return 1;
            if (residue.value() != 4U) return 2;
            return 0;
            """,
            """
            Residue residue(2, 5);
            for (char c : std::string("1010")) if (!residue.push(c)) return 1;
            if (residue.value() != 0U) return 2;
            if (Residue(10, 1).value()) return 3;
            Residue bad(10, 7);
            if (!bad.push('9')) return 4;
            if (bad.push('A') || bad.value()) return 5;
            return 0;
            """,
            "modular Horner with sticky failure and no full-magnitude storage",
            "converting the whole string or treating zero digits as terminators",
            "long streams, invalid digit after valid pushes, modulus one rejection, and reconstruction reset",
            "resource-aware streaming conversion",
            "streaming accumulator",
        ),
        c(
            "f26rad-magnitude-compare-nooverflow",
            "Magnitude compare no overflow",
            "magnitude_compare",
            """
            struct Numeral { unsigned radix; std::string text; };
            std::optional<int> compare(const Numeral&, const Numeral&);
            """,
            """
            struct Numeral { unsigned radix; std::string text; };
            std::optional<int> compare(const Numeral&, const Numeral&);
            """,
            """
            std::optional<int> compare(const Numeral& left, const Numeral& right) {
                auto a = f26rad_detail::parse_text(left.text, left.radix, true);
                auto b = f26rad_detail::parse_text(right.text, right.radix, true);
                if (!a || !b) return std::nullopt;
                if (*a < *b) return -1;
                if (*a > *b) return 1;
                return 0;
            }
            """,
            """
            std::optional<int> compare(const Numeral& left, const Numeral& right) {
                if (left.text.size() < right.text.size()) return -1;
                if (left.text.size() > right.text.size()) return 1;
                if (left.text < right.text) return -1;
                if (left.text > right.text) return 1;
                return 0;
            }
            """,
            """
            auto result = compare({2, "1000"}, {10, "8"});
            if (!result || *result != 0) return 1;
            return 0;
            """,
            """
            auto less = compare({3, "22"}, {10, "9"});
            if (!less || *less != -1) return 1;
            if (compare({10, "01"}, {10, "1"})) return 2;
            if (compare({10, std::string(32, '9')}, {10, "1"})) return 3;
            return 0;
            """,
            "checked canonical parsing before exact comparison",
            "floating logarithms or digit-count-only comparison",
            "near powers across radices, equal values, invalid input, and long overflowing values",
            "comparison without unchecked full conversion",
            "comparator",
        ),
        c(
            "f26rad-product-boundary-pack",
            "Product boundary pack",
            "product_pack",
            """
            struct Packed { bool ok; std::uint64_t value; };
            Packed pack(std::vector<unsigned> digits, std::vector<unsigned> radices);
            """,
            """
            struct Packed { bool ok; std::uint64_t value; };
            Packed pack(std::vector<unsigned> digits, std::vector<unsigned> radices);
            """,
            """
            Packed pack(std::vector<unsigned> digits, std::vector<unsigned> radices) {
                if (digits.empty() || digits.size() != radices.size()) return {false, 0};
                std::uint64_t representable_max = 0;
                std::uint64_t value = 0;
                for (std::size_t i = 0; i < digits.size(); ++i) {
                    if (radices[i] < 2 || digits[i] >= radices[i]) return {false, 0};
                    unsigned last_digit = radices[i] - 1;
                    if (representable_max > (std::numeric_limits<std::uint64_t>::max() - last_digit) / radices[i]) return {false, 0};
                    representable_max = representable_max * radices[i] + last_digit;
                    std::uint64_t next = 0;
                    if (!f26rad_detail::checked_mul_add(value, radices[i], digits[i], std::numeric_limits<std::uint64_t>::max(), next)) return {false, 0};
                    value = next;
                }
                return {true, value};
            }
            """,
            """
            Packed pack(std::vector<unsigned> digits, std::vector<unsigned> radices) {
                if (digits.empty() || digits.size() != radices.size()) return {false, 0};
                std::uint64_t value = 0;
                for (std::size_t i = 0; i < digits.size(); ++i) value = value * radices[i] + digits[i];
                return {true, value};
            }
            """,
            """
            auto packed = pack({1, 2, 3}, {2, 10, 4});
            if (!packed.ok || packed.value != 51) return 1;
            return 0;
            """,
            """
            if (pack({0}, {1}).ok) return 1;
            if (pack({2}, {2}).ok) return 2;
            if (pack({0, 0}, {2}).ok) return 3;
            if (pack(std::vector<unsigned>(65, 0), std::vector<unsigned>(65, 2)).ok) return 4;
            return 0;
            """,
            "field product and digit contribution checks before each multiply/add",
            "multiplying all radices first in uint64_t and accepting wraparound",
            "product overflow with small digits, length mismatch, digit equal to radix, and boundary fit",
            "field-product overflow in heterogeneous bases",
            "value type",
        ),
        c(
            "f26rad-decimal-crosscheck-buckets",
            "Decimal crosscheck buckets",
            "decimal_buckets",
            """
            std::optional<std::string> recode_to_decimal(std::string_view text, unsigned radix);
            """,
            """
            std::optional<std::string> recode_to_decimal(std::string_view text, unsigned radix);
            """,
            """
            std::optional<std::string> recode_to_decimal(std::string_view text, unsigned radix) {
                if (radix < 2 || radix > 18 || text.empty() || (text.size() > 1 && text.front() == '0')) return std::nullopt;
                std::string decimal = "0";
                for (char c : text) {
                    int digit = f26rad_detail::digit36(c);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix) return std::nullopt;
                    f26rad_detail::decimal_multiply_add(decimal, radix, static_cast<unsigned>(digit));
                }
                return decimal;
            }
            """,
            """
            std::optional<std::string> recode_to_decimal(std::string_view text, unsigned radix) {
                auto value = f26rad_detail::parse_text(text, radix, false);
                if (!value) return std::nullopt;
                return std::to_string(*value);
            }
            """,
            """
            auto out = recode_to_decimal("11111111", 2);
            if (!out || *out != "255") return 1;
            return 0;
            """,
            """
            auto large = recode_to_decimal(std::string(120, '1'), 2);
            if (!large || large->size() < 30) return 1;
            if (recode_to_decimal("01", 10)) return 2;
            if (recode_to_decimal("1I", 18)) return 3;
            if (recode_to_decimal("", 10)) return 4;
            return 0;
            """,
            "decimal string multiply-add rather than machine integer conversion",
            "std::to_string after uint64_t truncation",
            "120-digit binary, base-18 carry chains, invalid digit at end, and all-zero canonicalization",
            "large exact decimal output shape",
            "project support oracle",
            project_support=True,
        ),
        c(
            "f26rad-u64-canonicalizer",
            "U64 canonicalizer",
            "u64_code",
            """
            std::optional<std::uint64_t> parse(std::string_view, unsigned radix);
            std::string format(std::uint64_t, unsigned radix);
            """,
            """
            std::optional<std::uint64_t> parse(std::string_view, unsigned radix);
            std::string format(std::uint64_t, unsigned radix);
            """,
            """
            std::optional<std::uint64_t> parse(std::string_view text, unsigned radix) {
                return f26rad_detail::parse_text(text, radix, true);
            }
            std::string format(std::uint64_t value, unsigned radix) {
                return f26rad_detail::format_value(value, radix);
            }
            """,
            """
            std::optional<std::uint64_t> parse(std::string_view text, unsigned radix) {
                std::string fixed;
                for (char c : text) {
                    if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
                    if (c != '+') fixed.push_back(c);
                }
                return f26rad_detail::parse_text(fixed, radix, false);
            }
            std::string format(std::uint64_t value, unsigned radix) { return f26rad_detail::format_value(value, radix); }
            """,
            """
            if (format(35, 36) != "Z") return 1;
            if (parse("Z", 36) != 35U) return 2;
            return 0;
            """,
            """
            if (parse("z", 36)) return 1;
            if (parse("+10", 10)) return 2;
            if (parse("01", 10)) return 3;
            if (parse("18446744073709551616", 10)) return 4;
            return 0;
            """,
            "separate checked parse and quotient-format paths",
            "strtoull-style base autodetection, lowercase, or leading plus acceptance",
            "UINT64_MAX in radix 36, lowercase rejection, leading zero, and parse/format round trip",
            "bidirectional canonicalization",
            "free functions",
        ),
        c(
            "f26rad-signed-limit-parser",
            "Signed limit parser",
            "signed_limit",
            """
            struct SignedValue { bool negative; std::uint64_t magnitude; };
            std::optional<SignedValue> parse_signed(std::string_view, unsigned radix);
            """,
            """
            struct SignedValue { bool negative; std::uint64_t magnitude; };
            std::optional<SignedValue> parse_signed(std::string_view, unsigned radix);
            """,
            """
            std::optional<SignedValue> parse_signed(std::string_view text, unsigned radix) {
                if (text.size() < 2 || (text.front() != '+' && text.front() != '-')) return std::nullopt;
                bool negative = text.front() == '-';
                std::string_view body = text.substr(1);
                if (body.empty() || (body.size() > 1 && body.front() == '0')) return std::nullopt;
                std::uint64_t limit = negative ? (static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()) + 1ULL) : static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
                auto magnitude = f26rad_detail::parse_text(body, radix, true, limit);
                if (!magnitude) return std::nullopt;
                if (negative && *magnitude == 0) return std::nullopt;
                return SignedValue{negative, *magnitude};
            }
            """,
            """
            std::optional<SignedValue> parse_signed(std::string_view text, unsigned radix) {
                bool negative = !text.empty() && text.front() == '-';
                if (!text.empty() && (text.front() == '-' || text.front() == '+')) text.remove_prefix(1);
                auto magnitude = f26rad_detail::parse_text(text, radix, false);
                if (!magnitude) return std::nullopt;
                return SignedValue{negative, *magnitude};
            }
            """,
            """
            auto value = parse_signed("-8000000000000000", 16);
            if (!value || !value->negative || value->magnitude != 9223372036854775808ULL) return 1;
            return 0;
            """,
            """
            if (parse_signed("10", 10)) return 1;
            if (parse_signed("-0", 10)) return 2;
            if (parse_signed("+9223372036854775808", 10)) return 3;
            if (!parse_signed("+9223372036854775807", 10)) return 4;
            if (parse_signed("+1G", 16)) return 5;
            return 0;
            """,
            "sign-separated magnitude parsing with asymmetric signed limits",
            "accumulating directly in int64_t or negating after parse",
            "INT64_MIN magnitude, INT64_MAX plus one, negative zero, missing sign, and bad digit",
            "signed boundary behavior",
            "exception-like optional policy",
        ),
        c(
            "f26rad-power-table-budget",
            "Power table budget",
            "power_budget",
            """
            class PowerBudget {
            public:
                PowerBudget(unsigned radix, std::uint64_t limit);
                bool reserve_width(std::size_t width);
                std::optional<std::uint64_t> parse(std::string_view);
            };
            """,
            """
            class PowerBudget {
            public:
                PowerBudget(unsigned radix, std::uint64_t limit);
                bool reserve_width(std::size_t width);
                std::optional<std::uint64_t> parse(std::string_view);
            private:
                unsigned radix_;
                std::uint64_t limit_;
                std::size_t width_ = 0;
                bool reserved_ = false;
            };
            """,
            """
            PowerBudget::PowerBudget(unsigned radix, std::uint64_t limit) : radix_(radix), limit_(limit) {}
            bool PowerBudget::reserve_width(std::size_t width) {
                if (radix_ < 2 || radix_ > 36 || width == 0) return false;
                std::uint64_t capacity = 1;
                for (std::size_t i = 0; i < width; ++i) {
                    if (capacity > (limit_ + 1) / radix_) return false;
                    capacity *= radix_;
                }
                if (capacity == 0 || capacity - 1 > limit_) return false;
                width_ = width;
                reserved_ = true;
                return true;
            }
            std::optional<std::uint64_t> PowerBudget::parse(std::string_view text) {
                if (!reserved_ || text.empty() || text.size() > width_) return std::nullopt;
                return f26rad_detail::parse_text(text, radix_, true, limit_);
            }
            """,
            """
            PowerBudget::PowerBudget(unsigned radix, std::uint64_t limit) : radix_(radix), limit_(limit) {}
            bool PowerBudget::reserve_width(std::size_t width) {
                width_ = width;
                reserved_ = true;
                return width > 0;
            }
            std::optional<std::uint64_t> PowerBudget::parse(std::string_view text) {
                if (!reserved_) return std::nullopt;
                return f26rad_detail::parse_text(text, radix_, false, limit_);
            }
            """,
            """
            PowerBudget budget(10, 999);
            if (!budget.reserve_width(3)) return 1;
            if (budget.parse("999") != 999U) return 2;
            return 0;
            """,
            """
            PowerBudget budget(10, 99);
            if (budget.parse("9")) return 1;
            if (budget.reserve_width(3)) return 2;
            if (!budget.reserve_width(2)) return 3;
            if (budget.parse("099")) return 4;
            if (budget.parse("100")) return 5;
            return 0;
            """,
            "checked exponentiation proof before enabling parse",
            "setting reservation true without capacity proof",
            "reservation overflow, parse before reservation, width zero, exact max width, and failed reservation preserving old state",
            "stateful preflight and overflow proof",
            "stateful class",
            project_support=True,
        ),
    )


def _stateful_output_cases() -> tuple[TaskSpec, ...]:
    c = _case
    return (
        c(
            "f26rad-stateful-converter-cache",
            "Stateful converter cache",
            "radix_cache",
            """
            class RadixCache {
            public:
                bool configure(unsigned source_radix, unsigned target_radix);
                std::optional<std::string> render(std::string_view);
                std::size_t hits() const;
                void clear();
            };
            """,
            """
            class RadixCache {
            public:
                bool configure(unsigned source_radix, unsigned target_radix);
                std::optional<std::string> render(std::string_view);
                std::size_t hits() const;
                void clear();
            private:
                unsigned source_ = 0;
                unsigned target_ = 0;
                std::size_t hits_ = 0;
                std::map<std::string, std::string> cache_;
            };
            """,
            """
            bool RadixCache::configure(unsigned source_radix, unsigned target_radix) {
                if (source_radix < 2 || source_radix > 36 || target_radix < 2 || target_radix > 36) return false;
                source_ = source_radix;
                target_ = target_radix;
                cache_.clear();
                return true;
            }
            std::optional<std::string> RadixCache::render(std::string_view text) {
                if (source_ == 0 || target_ == 0) return std::nullopt;
                std::string key = std::to_string(source_) + ":" + std::to_string(target_) + ":" + std::string(text);
                auto cached = cache_.find(key);
                if (cached != cache_.end()) { ++hits_; return cached->second; }
                auto out = f26rad_detail::recode(text, source_, target_, true);
                if (!out) return std::nullopt;
                cache_[key] = *out;
                return out;
            }
            std::size_t RadixCache::hits() const { return hits_; }
            void RadixCache::clear() { cache_.clear(); hits_ = 0; }
            """,
            """
            bool RadixCache::configure(unsigned source_radix, unsigned target_radix) {
                source_ = source_radix;
                target_ = target_radix;
                return true;
            }
            std::optional<std::string> RadixCache::render(std::string_view text) {
                std::string key(text);
                auto cached = cache_.find(key);
                if (cached != cache_.end()) { ++hits_; return cached->second; }
                auto out = f26rad_detail::recode(text, source_, target_, false);
                if (out) cache_[key] = *out;
                return out;
            }
            std::size_t RadixCache::hits() const { return hits_; }
            void RadixCache::clear() { cache_.clear(); }
            """,
            """
            RadixCache cache;
            if (!cache.configure(10, 16)) return 1;
            if (cache.render("15") != std::optional<std::string>("F")) return 2;
            if (cache.render("15") != std::optional<std::string>("F") || cache.hits() != 1) return 3;
            return 0;
            """,
            """
            RadixCache cache;
            if (cache.render("10")) return 1;
            if (!cache.configure(10, 2)) return 2;
            if (cache.render("01")) return 3;
            if (cache.render("10") != std::optional<std::string>("1010")) return 4;
            if (!cache.configure(16, 10)) return 5;
            if (cache.render("10") != std::optional<std::string>("16")) return 6;
            cache.clear();
            if (cache.hits() != 0) return 7;
            if (cache.configure(1, 10)) return 8;
            return 0;
            """,
            "two-radix configuration with canonical key cache and hit mutation only on cache hits",
            "caching by input text alone or accepting invalid configurations",
            "reconfiguration, same text under different radices, clear, and invalid config",
            "mutable class behavior with cache state",
            "stateful class",
            project_support=True,
        ),
        c(
            "f26rad-incremental-digit-writer",
            "Incremental digit writer",
            "digit_writer",
            """
            class Writer {
            public:
                explicit Writer(unsigned out_radix);
                void write(std::uint64_t value);
                std::vector<unsigned> take();
            };
            """,
            """
            class Writer {
            public:
                explicit Writer(unsigned out_radix);
                void write(std::uint64_t value);
                std::vector<unsigned> take();
            private:
                unsigned radix_;
                std::vector<unsigned> buffer_;
                bool has_value_ = false;
            };
            """,
            """
            Writer::Writer(unsigned out_radix) : radix_(out_radix) {
                if (out_radix < 2 || out_radix > 36) throw std::invalid_argument("bad writer radix");
            }
            void Writer::write(std::uint64_t value) {
                if (has_value_) buffer_.push_back(0);
                auto digits = f26rad_detail::digits_of(value, radix_);
                buffer_.insert(buffer_.end(), digits.begin(), digits.end());
                has_value_ = true;
            }
            std::vector<unsigned> Writer::take() {
                auto out = buffer_;
                buffer_.clear();
                has_value_ = false;
                return out;
            }
            """,
            """
            Writer::Writer(unsigned out_radix) : radix_(out_radix) {}
            void Writer::write(std::uint64_t value) {
                do {
                    buffer_.push_back(static_cast<unsigned>(value % radix_));
                    value /= radix_;
                } while (value != 0);
            }
            std::vector<unsigned> Writer::take() {
                auto out = buffer_;
                buffer_.clear();
                return out;
            }
            """,
            """
            Writer writer(10);
            writer.write(12);
            writer.write(0);
            if (writer.take() != std::vector<unsigned>({1, 2, 0, 0})) return 1;
            return 0;
            """,
            """
            Writer writer(16);
            if (!writer.take().empty()) return 1;
            writer.write(255);
            if (writer.take() != std::vector<unsigned>({15, 15})) return 2;
            if (!writer.take().empty()) return 3;
            try { Writer bad(1); return 4; } catch (const std::invalid_argument&) {}
            return 0;
            """,
            "repeated quotient emission per value with delimiter state",
            "emitting least-significant digits first or omitting value separators",
            "zero, multiple values, take twice, invalid constructor, and high-radix digits",
            "output construction and repeated-call semantics",
            "incremental writer",
        ),
        c(
            "f26rad-format-roundtrip-journal",
            "Format roundtrip journal",
            "radix_journal",
            """
            struct Record { unsigned radix; std::string text; };
            class Journal {
            public:
                bool append(Record);
                std::vector<Record> canonical() const;
            };
            """,
            """
            struct Record { unsigned radix; std::string text; };
            class Journal {
            public:
                bool append(Record);
                std::vector<Record> canonical() const;
            private:
                std::vector<std::pair<std::uint64_t, Record>> records_;
            };
            """,
            """
            bool Journal::append(Record record) {
                auto value = f26rad_detail::parse_text(record.text, record.radix, true);
                if (!value || f26rad_detail::format_value(*value, record.radix) != record.text) return false;
                records_.push_back({*value, std::move(record)});
                std::sort(records_.begin(), records_.end(), [](const auto& a, const auto& b) {
                    if (a.first != b.first) return a.first < b.first;
                    return std::tie(a.second.radix, a.second.text) < std::tie(b.second.radix, b.second.text);
                });
                return true;
            }
            std::vector<Record> Journal::canonical() const {
                std::vector<Record> out;
                for (const auto& row : records_) out.push_back(row.second);
                return out;
            }
            """,
            """
            bool Journal::append(Record record) {
                records_.push_back({0, std::move(record)});
                return true;
            }
            std::vector<Record> Journal::canonical() const {
                std::vector<Record> out;
                for (const auto& row : records_) out.push_back(row.second);
                return out;
            }
            """,
            """
            Journal journal;
            if (!journal.append({16, "10"}) || !journal.append({10, "15"})) return 1;
            auto rows = journal.canonical();
            if (rows.front().text != "15" || rows.back().text != "10") return 2;
            return 0;
            """,
            """
            Journal journal;
            if (journal.append({10, "01"})) return 1;
            if (!journal.append({10, "1"})) return 2;
            if (journal.append({2, "2"})) return 3;
            auto before = journal.canonical();
            if (journal.append({10, "01"})) return 4;
            auto after = journal.canonical();
            if (after.size() != before.size() || after.front().text != before.front().text || after.front().radix != before.front().radix) return 5;
            return 0;
            """,
            "parse-format identity check and stable sort by value then radix",
            "appending before validating or accepting parseable noncanonical text",
            "noncanonical leading zeros, equal values in different radices, invalid records preserving old state, and stable tie order",
            "canonical round-trip journal",
            "value journal",
            project_support=True,
        ),
        c(
            "f26rad-operator-coded-value",
            "Operator coded value",
            "coded_value",
            """
            class CodedValue {
            public:
                static std::optional<CodedValue> make(unsigned radix, std::string text);
                std::string str() const;
                friend bool operator==(const CodedValue&, const CodedValue&);
                friend bool operator<(const CodedValue&, const CodedValue&);
            private:
                CodedValue(unsigned radix, std::uint64_t value, std::string text);
                unsigned radix_;
                std::uint64_t value_;
                std::string text_;
            };
            """,
            """
            class CodedValue {
            public:
                static std::optional<CodedValue> make(unsigned radix, std::string text);
                std::string str() const;
                friend bool operator==(const CodedValue&, const CodedValue&);
                friend bool operator<(const CodedValue&, const CodedValue&);
            private:
                CodedValue(unsigned radix, std::uint64_t value, std::string text);
                unsigned radix_;
                std::uint64_t value_;
                std::string text_;
            };
            """,
            """
            CodedValue::CodedValue(unsigned radix, std::uint64_t value, std::string text) : radix_(radix), value_(value), text_(std::move(text)) {}
            std::optional<CodedValue> CodedValue::make(unsigned radix, std::string text) {
                auto value = f26rad_detail::parse_text(text, radix, true);
                if (!value) return std::nullopt;
                return CodedValue(radix, *value, f26rad_detail::format_value(*value, radix));
            }
            std::string CodedValue::str() const { return text_; }
            bool operator==(const CodedValue& left, const CodedValue& right) { return left.value_ == right.value_; }
            bool operator<(const CodedValue& left, const CodedValue& right) {
                if (left.value_ != right.value_) return left.value_ < right.value_;
                return std::tie(left.radix_, left.text_) < std::tie(right.radix_, right.text_);
            }
            """,
            """
            CodedValue::CodedValue(unsigned radix, std::uint64_t value, std::string text) : radix_(radix), value_(value), text_(std::move(text)) {}
            std::optional<CodedValue> CodedValue::make(unsigned radix, std::string text) {
                return CodedValue(radix, 0, std::move(text));
            }
            std::string CodedValue::str() const { return text_; }
            bool operator==(const CodedValue& left, const CodedValue& right) { return left.text_ == right.text_; }
            bool operator<(const CodedValue& left, const CodedValue& right) { return left.text_ < right.text_; }
            """,
            """
            auto a = CodedValue::make(2, "10");
            auto b = CodedValue::make(10, "2");
            if (!a || !b || !(*a == *b)) return 1;
            return 0;
            """,
            """
            if (CodedValue::make(10, "01")) return 1;
            auto zero = CodedValue::make(10, "0");
            if (!zero || zero->str() != "0") return 2;
            auto hi = CodedValue::make(16, "FF");
            auto lo = CodedValue::make(10, "16");
            if (!hi || !lo || !(*lo < *hi)) return 3;
            return 0;
            """,
            "checked value storage plus canonical spelling and value-based operators",
            "lexicographic string-only equality or ordering",
            "same value across radices, noncanonical rejection, ordering near overflow, and zero",
            "C++ operator value semantics",
            "value type operators",
        ),
        c(
            "f26rad-namespace-free-functions",
            "Namespace free functions",
            "warehouse_radix",
            """
            bool valid_code(std::string_view, unsigned);
            std::string canonical_or_empty(std::string_view, unsigned);
            std::optional<std::uint64_t> value_of(std::string_view, unsigned);
            """,
            """
            bool valid_code(std::string_view, unsigned);
            std::string canonical_or_empty(std::string_view, unsigned);
            std::optional<std::uint64_t> value_of(std::string_view, unsigned);
            """,
            """
            std::optional<std::uint64_t> value_of(std::string_view text, unsigned radix) {
                return f26rad_detail::parse_text(text, radix, true);
            }
            bool valid_code(std::string_view text, unsigned radix) { return static_cast<bool>(value_of(text, radix)); }
            std::string canonical_or_empty(std::string_view text, unsigned radix) {
                auto value = value_of(text, radix);
                return value ? f26rad_detail::format_value(*value, radix) : std::string{};
            }
            """,
            """
            std::optional<std::uint64_t> value_of(std::string_view text, unsigned radix) {
                return f26rad_detail::parse_text(text, radix, true);
            }
            bool valid_code(std::string_view text, unsigned radix) { return !text.empty() && radix >= 2; }
            std::string canonical_or_empty(std::string_view text, unsigned radix) {
                auto value = f26rad_detail::parse_text(text, radix, false);
                return value ? f26rad_detail::format_value(*value, radix) : std::string{};
            }
            """,
            """
            if (!valid_code("10", 2) || canonical_or_empty("10", 2) != "10" || value_of("10", 2) != 2U) return 1;
            return 0;
            """,
            """
            if (valid_code("", 10) || canonical_or_empty("", 10) != "" || value_of("", 10)) return 1;
            if (valid_code("01", 10) || canonical_or_empty("01", 10) != "" || value_of("01", 10)) return 2;
            if (valid_code("A", 10) || canonical_or_empty("A", 10) != "" || value_of("A", 10)) return 3;
            return 0;
            """,
            "one private validation path shared across public helpers",
            "three independent inconsistent parsers",
            "cross-call consistency for empty, leading zero, bad digit, and overflow",
            "API consistency across multiple free functions",
            "free functions",
        ),
        c(
            "f26rad-project-policy-registry",
            "Project policy registry",
            "policy_registry",
            """
            class Registry {
            public:
                bool load_default_policy(std::string_view name);
                std::optional<std::string> normalize(std::string_view text) const;
            };
            """,
            """
            class Registry {
            public:
                bool load_default_policy(std::string_view name);
                std::optional<std::string> normalize(std::string_view text) const;
            private:
                unsigned source_ = 0;
                unsigned target_ = 0;
            };
            """,
            """
            bool Registry::load_default_policy(std::string_view name) {
                if (name == "dock") { source_ = 16; target_ = 10; return true; }
                if (name == "belt") { source_ = 2; target_ = 16; return true; }
                return false;
            }
            std::optional<std::string> Registry::normalize(std::string_view text) const {
                if (source_ == 0 || target_ == 0) return std::nullopt;
                return f26rad_detail::recode(text, source_, target_, true);
            }
            """,
            """
            bool Registry::load_default_policy(std::string_view) {
                source_ = 16;
                target_ = 10;
                return true;
            }
            std::optional<std::string> Registry::normalize(std::string_view text) const {
                return f26rad_detail::recode(text, source_ ? source_ : 16, target_ ? target_ : 10, false);
            }
            """,
            """
            Registry registry;
            if (!registry.load_default_policy("dock")) return 1;
            if (registry.normalize("10") != std::optional<std::string>("16")) return 2;
            return 0;
            """,
            """
            Registry registry;
            if (registry.normalize("10")) return 1;
            if (!registry.load_default_policy("belt")) return 2;
            if (registry.normalize("1010") != std::optional<std::string>("A")) return 3;
            if (registry.load_default_policy("missing")) return 4;
            if (registry.normalize("1010") != std::optional<std::string>("A")) return 5;
            if (registry.normalize("02")) return 6;
            return 0;
            """,
            "named immutable policy lookup with mutation only on successful loads",
            "always using the first policy or mutating state on unknown names",
            "two policies, unknown policy, invalid text under one policy, and state after failed load",
            "project-style registry without exposing support assets",
            "stateful registry",
        ),
        c(
            "f26rad-exception-normalizer",
            "Exception normalizer",
            "exception_norm",
            """
            class Normalizer {
            public:
                explicit Normalizer(unsigned radix);
                std::string operator()(std::string_view text) const;
            };
            """,
            """
            class Normalizer {
            public:
                explicit Normalizer(unsigned radix);
                std::string operator()(std::string_view text) const;
            private:
                unsigned radix_;
            };
            """,
            """
            Normalizer::Normalizer(unsigned radix) : radix_(radix) {
                if (radix < 2 || radix > 36) throw std::invalid_argument("bad radix");
            }
            std::string Normalizer::operator()(std::string_view text) const {
                auto value = f26rad_detail::parse_text(text, radix_, true);
                if (!value) throw std::domain_error("bad code");
                return f26rad_detail::format_value(*value, radix_);
            }
            """,
            """
            Normalizer::Normalizer(unsigned radix) : radix_(radix) {}
            std::string Normalizer::operator()(std::string_view text) const {
                auto value = f26rad_detail::parse_text(text, radix_, false);
                return value ? f26rad_detail::format_value(*value, radix_) : std::string("0");
            }
            """,
            """
            Normalizer norm(16);
            if (norm("0") != "0" || norm("FF") != "FF") return 1;
            return 0;
            """,
            """
            try { Normalizer bad(1); return 1; } catch (const std::invalid_argument&) {}
            Normalizer norm(10);
            try { (void)norm(""); return 2; } catch (const std::domain_error&) {}
            try { (void)norm("01"); return 3; } catch (const std::domain_error&) {}
            try { (void)norm(std::string(32, '9')); return 4; } catch (const std::domain_error&) {}
            return 0;
            """,
            "constructor policy gate plus checked parse/reformat",
            "returning empty or zero strings for failures",
            "constructor exception, per-call exception, valid zero, leading zero, and overflow",
            "callable object exception normalization",
            "exception service",
        ),
        c(
            "f26rad-roundtrip-test-harness",
            "Roundtrip test harness",
            "roundtrip_harness",
            """
            struct Case { unsigned from; unsigned to; std::string text; };
            struct Outcome { bool accepted; std::string output; bool stable; };
            Outcome run_case(const Case&);
            """,
            """
            struct Case { unsigned from; unsigned to; std::string text; };
            struct Outcome { bool accepted; std::string output; bool stable; };
            Outcome run_case(const Case&);
            """,
            """
            Outcome run_case(const Case& item) {
                auto out = f26rad_detail::recode(item.text, item.from, item.to, true);
                if (!out) return {false, {}, false};
                auto source = f26rad_detail::parse_text(item.text, item.from, true);
                auto roundtrip = f26rad_detail::parse_text(*out, item.to, true);
                bool stable = source && roundtrip && *source == *roundtrip && f26rad_detail::format_value(*roundtrip, item.to) == *out;
                return {stable, *out, stable};
            }
            """,
            """
            Outcome run_case(const Case& item) {
                auto out = f26rad_detail::recode(item.text, item.from, item.to, false);
                return out ? Outcome{true, *out, true} : Outcome{false, {}, true};
            }
            """,
            """
            auto outcome = run_case({10, 2, "5"});
            if (!outcome.accepted || outcome.output != "101" || !outcome.stable) return 1;
            return 0;
            """,
            """
            if (run_case({1, 10, "5"}).accepted) return 1;
            if (run_case({10, 1, "5"}).accepted) return 2;
            if (run_case({10, 2, "05"}).accepted) return 3;
            auto zero = run_case({10, 16, "0"});
            if (!zero.accepted || zero.output != "0" || !zero.stable) return 4;
            return 0;
            """,
            "two-stage checked conversion with independent stability verification",
            "trusting the first conversion or marking every accepted output stable",
            "invalid source, invalid target, zero, noncanonical input, and overflow",
            "oracle-like self-checking output shape",
            "harness-like API",
        ),
        c(
            "f26rad-repairable-error-report",
            "Repairable error report",
            "error_report",
            """
            enum class Code { ok, bad_radix, empty, bad_digit, leading_zero, overflow };
            struct Report { Code code; std::size_t index; std::string canonical; };
            Report inspect(std::string_view, unsigned radix);
            """,
            """
            enum class Code { ok, bad_radix, empty, bad_digit, leading_zero, overflow };
            struct Report { Code code; std::size_t index; std::string canonical; };
            Report inspect(std::string_view, unsigned radix);
            """,
            """
            Report inspect(std::string_view text, unsigned radix) {
                if (radix < 2 || radix > 36) return {Code::bad_radix, 0, {}};
                if (text.empty()) return {Code::empty, 0, {}};
                std::uint64_t value = 0;
                for (std::size_t i = 0; i < text.size(); ++i) {
                    int digit = f26rad_detail::digit36(text[i]);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix) return {Code::bad_digit, i, {}};
                    std::uint64_t next = 0;
                    if (!f26rad_detail::checked_mul_add(value, radix, static_cast<unsigned>(digit), std::numeric_limits<std::uint64_t>::max(), next)) return {Code::overflow, i, {}};
                    value = next;
                }
                if (text.size() > 1 && text.front() == '0') return {Code::leading_zero, 0, {}};
                return {Code::ok, text.size(), f26rad_detail::format_value(value, radix)};
            }
            """,
            """
            Report inspect(std::string_view text, unsigned radix) {
                Code code = Code::ok;
                std::size_t index = 0;
                for (std::size_t i = 0; i < text.size(); ++i) {
                    int digit = f26rad_detail::digit36(text[i]);
                    if (digit < 0 || static_cast<unsigned>(digit) >= radix) { code = Code::bad_digit; index = i; }
                }
                if (radix < 2) code = Code::bad_radix;
                if (text.empty()) code = Code::empty;
                return {code, index, std::string(text)};
            }
            """,
            """
            auto report = inspect("10", 2);
            if (report.code != Code::ok || report.canonical != "10") return 1;
            return 0;
            """,
            """
            if (inspect("", 1).code != Code::bad_radix) return 1;
            if (inspect("0A", 10).code != Code::bad_digit || inspect("0A", 10).index != 1) return 2;
            if (inspect("00", 10).code != Code::leading_zero) return 3;
            if (inspect("18446744073709551616", 10).code != Code::overflow) return 4;
            return 0;
            """,
            "ordered validation pipeline with first-error index and canonical only on success",
            "unordered validation or leaking partial canonical output on failure",
            "bad_radix precedence, bad_digit before leading_zero when both possible, and overflow index",
            "structured repair diagnostics",
            "diagnostic enum",
        ),
        c(
            "f26rad-canonical-output-matrix",
            "Canonical output matrix",
            "output_matrix",
            """
            struct Matrix { std::vector<std::vector<unsigned>> rows; };
            std::optional<Matrix> recode_rows(std::vector<std::string> texts, unsigned in_radix, unsigned out_radix, std::size_t width);
            """,
            """
            struct Matrix { std::vector<std::vector<unsigned>> rows; };
            std::optional<Matrix> recode_rows(std::vector<std::string> texts, unsigned in_radix, unsigned out_radix, std::size_t width);
            """,
            """
            std::optional<Matrix> recode_rows(std::vector<std::string> texts, unsigned in_radix, unsigned out_radix, std::size_t width) {
                if (in_radix < 2 || in_radix > 36 || out_radix < 2 || out_radix > 36 || width == 0) return std::nullopt;
                std::vector<std::uint64_t> values;
                for (const auto& text : texts) {
                    auto value = f26rad_detail::parse_text(text, in_radix, true);
                    if (!value) return std::nullopt;
                    auto digits = f26rad_detail::digits_of(*value, out_radix);
                    if (digits.size() > width) return std::nullopt;
                    values.push_back(*value);
                }
                Matrix matrix;
                for (std::uint64_t value : values) matrix.rows.push_back(f26rad_detail::digits_of(value, out_radix, width));
                return matrix;
            }
            """,
            """
            std::optional<Matrix> recode_rows(std::vector<std::string> texts, unsigned in_radix, unsigned out_radix, std::size_t width) {
                Matrix matrix;
                for (const auto& text : texts) {
                    auto value = f26rad_detail::parse_text(text, in_radix, false);
                    if (!value) return std::nullopt;
                    matrix.rows.push_back(f26rad_detail::digits_of(*value, out_radix, width));
                }
                return matrix;
            }
            """,
            """
            auto matrix = recode_rows({"5", "10"}, 10, 2, 4);
            if (!matrix || matrix->rows != std::vector<std::vector<unsigned>>({{0, 1, 0, 1}, {1, 0, 1, 0}})) return 1;
            return 0;
            """,
            """
            auto empty = recode_rows({}, 10, 2, 3);
            if (!empty || !empty->rows.empty()) return 1;
            if (recode_rows({"1", "02"}, 10, 2, 3)) return 2;
            if (recode_rows({"1", "8"}, 10, 2, 3)) return 3;
            if (recode_rows({"1"}, 1, 2, 3)) return 4;
            return 0;
            """,
            "validate all rows and prove width before emitting fixed-width row vectors",
            "emitting partial rows before later failure or ragged output",
            "invalid middle row, width too small, empty batch, leading-zero rejection, and atomic output",
            "exact matrix output and atomic batch behavior",
            "matrix output",
        ),
    )


CURRICULUM = SPEC_DOCUMENT
GENERATOR_PATH = REPO_ROOT / OWNER
OWNER_ID = OWNER
NORMALIZER = "fixed26-all-your-base-seven-dimension-artifacts-v1"
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

Implement a clean-room C++17 radix-processing component for a local
all-your-base analog. This root is independently authored for SFT task-family
construction and is not an official benchmark exercise.
"""


def _instructions(spec: TaskSpec) -> str:
    return f"""Implement the public API below in `{spec.task_id}.h` and `{spec.task_id}.cpp`.

```cpp
namespace {spec.namespace} {{
{spec.api}}}
```

Behavior focus: {spec.mechanism}. The implementation must cover {spec.hidden_plan}.
It must keep invalid base policy, digit bounds, empty input handling,
leading-zero policy, overflow-safe accumulation, and canonical output behavior
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
                "source": "w8-biayn clean-room fixed26 all-your-base analog curriculum",
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
description = "{spec.title}: invalid bases, digit bounds, canonical output, and wrong-substitute rejection"

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
            "family": "all-your-base",
            "project_support": spec.project_support,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    ledger = {
        "schema_version": "aider-task-family-batch-ledger-v1",
        "batch_id": BATCH_ID,
        "bucket": "failed-fixed26-analog",
        "target_family": "all-your-base",
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
        "project_context_support_note": "The source spec table labels 18 roots project-context; this materializer emits private support for the 15 support roots named by the batch file-layout contract.",
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
    text = re.sub(r"\bf26rad[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
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
    comparison_roots: list[tuple[str, Path]] = []
    for tree in (LEGACY_ROOT, REVERIFY_ROOT):
        comparison_roots.extend(sorted(_inventory_roots(tree).items()))
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
        "schema_version": "fixed26-all-your-base-diversity-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-radix-fresh-") as temporary:
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
        "schema_version": "fixed26-all-your-base-core-v1",
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
for task_root in sorted(ROOT.glob("f26rad-*")):
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
            "schema_version": "fixed26-all-your-base-not-completed-v1",
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
    with tempfile.TemporaryDirectory(prefix="fixed26-radix-docker-") as temporary:
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
        "schema_version": "fixed26-all-your-base-docker-sanity-v1",
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
        "schema_version": "fixed26-all-your-base-creator-preflight-v1",
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
        "capability": "fixed26-all-your-base-analog",
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
            "task": "implement clean-room fixed26 all-your-base analog C++17 roots",
            "inputs": "visible docs and declared starter files only",
            "output": "exact whole-file replacements for each declared header/source pair",
            "invariants": "validate radix and digits before arithmetic; preserve explicit empty/zero policy; checked overflow; canonical output",
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
            "target_family": "all-your-base",
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
